"""
M9 Intent Router -- route() dispatcher (R1, R5, R7, R8, R19).

This is the sole public entry point. Pure apart from the provider call,
the Vault HMAC-key fetch (cached), and the stdout audit emit.

Key invariants:
- print() appears EXACTLY ONCE in the whole M9 source tree: in _emit_audit.
- MNPI pre-scan runs BEFORE any LLM call (Steering Rule 8 fail-closed).
- AID authority-scope check runs POST-LLM but PRE-dispatch (AC12.9).
- Role=agent + TRADE_INQUIRY downgrades to med bucket (AC5.8, Fix 8).
- threading.Semaphore(16) caps concurrent classify() calls (R19).

See `.kiro/specs/m9-intent-router.md` R1, R5, R7, R8, R12, R19.
"""

from __future__ import annotations

import json
import math
import threading
import time
from typing import Any

from m1_identity import Role

from m9_intent_router.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m9_intent_router.fallback import fallback_classify
from m9_intent_router.hmac_util import (
    _resolve_tenant_hmac_key,
    compute_utterance_digest,
)
from m9_intent_router.llm_client import LLMProvider
from m9_intent_router.mnpi_scan import scan_mnpi_shape
from m9_intent_router.models import LlmClassification, RouterContext, RoutingDecision
from m9_intent_router.regex_library import extract_entities
from m9_intent_router.taxonomy import (
    TAXONOMY_DISPATCH,
    IntentCategory,
    build_tool_schema,
    required_scopes,
)

_UTTERANCE_MIN = 1
_UTTERANCE_MAX = 4096

# Defense-in-depth cap (R19 AC19.1). Module-level, thread-safe.
_INFLIGHT = threading.Semaphore(16)
_INFLIGHT_COUNT_LOCK = threading.Lock()
_INFLIGHT_COUNTER = [0]  # mutable single-element list for ref-semantics


def _inflight_count() -> int:
    """Debug helper for concurrency tests (AC19.4). Not exported."""
    with _INFLIGHT_COUNT_LOCK:
        return _INFLIGHT_COUNTER[0]


def _empty_tenant_key() -> bytes:
    """32-byte zeroed key for short-circuit paths (invalid utterance length)."""
    return b"\x00" * 32


def route(
    utterance: str,
    context: RouterContext,
    *,
    _provider: LLMProvider,
    _config: Any,
) -> RoutingDecision:
    """Public entry point. Pure apart from provider call + audit emit.

    Args:
        utterance: Raw user input. Length 1..4096 inclusive (AC1.3).
        context: RouterContext with verified AidClaims. M12 constructs this.
        _provider: LLMProvider instance (injected -- no global state).
        _config: Duck-typed config with .confidence_high, .confidence_med,
            .fallback_enabled, .tenant_hmac_key_vault_path.

    Returns:
        RoutingDecision. NEVER raises.
    """
    # AC1.3: length gate. No HMAC, no MNPI scan, no LLM call.
    if not (_UTTERANCE_MIN <= len(utterance) <= _UTTERANCE_MAX):
        decision = _build_escalate_decision(
            context=context,
            digest=compute_utterance_digest("", _empty_tenant_key()),
            intent=IntentCategory.UNSUPPORTED,
            reason_code="invalid_utterance_length",
            confidence=0.0,
            llm_latency_ms=0,
            llm_model="n/a",
            llm_provider="n/a",
            fallback_used=False,
            entities={},
        )
        _emit_audit(decision)
        return decision

    # HMAC the utterance (Fix 10).
    tenant_key = _resolve_tenant_hmac_key(
        context.tenant_id, _config.tenant_hmac_key_vault_path
    )
    digest = compute_utterance_digest(utterance, tenant_key)

    # MNPI pre-scan (Steering Rule 8 fail-closed, AC8.4).
    if scan_mnpi_shape(utterance) is not None:
        decision = _build_escalate_decision(
            context=context,
            digest=digest,
            intent=IntentCategory.ESCALATE_TO_HUMAN,
            reason_code="mnpi_shape_suspected",
            confidence=0.0,
            llm_latency_ms=0,
            llm_model="n/a",
            llm_provider="n/a",
            fallback_used=False,
            entities={},
        )
        _emit_audit(decision)
        return decision

    entities = extract_entities(utterance)

    # LLM call inside the inflight cap (R19).
    _acquire_inflight()
    try:
        try:
            start = time.perf_counter()
            classification = _provider.classify(utterance, build_tool_schema())
            latency_ms = int((time.perf_counter() - start) * 1000)
            decision = _dispatch_classification(
                classification=classification,
                entities=entities,
                digest=digest,
                context=context,
                latency_ms=latency_ms,
                config=_config,
            )
        except (
            LlmTimeoutError,
            LlmProviderError,
            LlmMalformedOutputError,
        ) as exc:
            decision = _handle_llm_error(
                exc=exc,
                utterance=utterance,
                digest=digest,
                entities=entities,
                context=context,
                config=_config,
            )
    finally:
        _release_inflight()

    _emit_audit(decision)
    return decision


# -----------------------------------------------------------------------------
# Core dispatch + error-path helpers.
# -----------------------------------------------------------------------------


def _dispatch_classification(
    *,
    classification: LlmClassification,
    entities: dict,
    digest: str,
    context: RouterContext,
    latency_ms: int,
    config: Any,
) -> RoutingDecision:
    """Apply confidence gating + AID authority scope check."""
    intent = classification.intent
    confidence = classification.confidence
    merged_entities = {**entities, **classification.entities}

    # AC5.7 NaN handling (confidence < med -> escalate). Pydantic rejects
    # Inf/-Inf at LlmClassification construction; NaN cannot arrive here
    # because allow_inf_nan=False on the field. Defensive clamp kept anyway.
    if isinstance(confidence, float) and math.isnan(confidence):
        return _build_escalate_decision(
            context=context,
            digest=digest,
            intent=IntentCategory.ESCALATE_TO_HUMAN,
            reason_code="low_confidence",
            confidence=0.0,
            llm_latency_ms=latency_ms,
            llm_model=classification.model,
            llm_provider=classification.provider,
            fallback_used=False,
            entities=merged_entities,
        )

    # AC5.8 Fix 8: Role=agent + TRADE_INQUIRY -> downgrade to med bucket.
    downgrade = (
        context.identity.role == Role.agent
        and intent == IntentCategory.TRADE_INQUIRY
    )

    high = getattr(config, "confidence_high", 0.95)
    med = getattr(config, "confidence_med", 0.80)

    # Below mid -> escalate (AC5.3).
    if confidence < med:
        return _build_escalate_decision(
            context=context,
            digest=digest,
            intent=IntentCategory.ESCALATE_TO_HUMAN,
            reason_code="low_confidence",
            confidence=confidence,
            llm_latency_ms=latency_ms,
            llm_model=classification.model,
            llm_provider=classification.provider,
            fallback_used=False,
            entities=merged_entities,
        )

    # Reason code: llm_assisted_plan for mid bucket OR downgraded agent-trade.
    if downgrade or (med <= confidence < high):
        reason_code: "str | None" = "llm_assisted_plan"
    else:
        reason_code = None

    # UNSUPPORTED dispatch -> escalate stub.
    if intent == IntentCategory.UNSUPPORTED:
        return _build_escalate_decision(
            context=context,
            digest=digest,
            intent=IntentCategory.UNSUPPORTED,
            reason_code="unsupported_intent_stub",
            confidence=confidence,
            llm_latency_ms=latency_ms,
            llm_model=classification.model,
            llm_provider=classification.provider,
            fallback_used=False,
            entities=merged_entities,
        )

    # AC12.9 post-LLM authority scope check (Fix 8).
    if not _check_authority_scope(
        intent,
        set(context.identity.authority_scope),
        set(context.identity.authority_excludes),
    ):
        return _build_escalate_decision(
            context=context,
            digest=digest,
            intent=IntentCategory.ESCALATE_TO_HUMAN,
            reason_code="aid_authority_denied",
            confidence=confidence,
            llm_latency_ms=latency_ms,
            llm_model=classification.model,
            llm_provider=classification.provider,
            fallback_used=False,
            entities=merged_entities,
        )

    # Normal dispatch.
    target = TAXONOMY_DISPATCH[intent]
    return RoutingDecision(
        trace_id=context.trace_id,
        utterance_sha256=digest,
        intent=intent,
        confidence=confidence,
        entities=merged_entities,
        selected_target=target,
        fallback_used=False,
        llm_latency_ms=latency_ms,
        llm_model=classification.model,
        llm_provider=classification.provider,
        reason_code=reason_code,
        tenant_id=context.tenant_id,
    )


def _handle_llm_error(
    *,
    exc: Exception,
    utterance: str,
    digest: str,
    entities: dict,
    context: RouterContext,
    config: Any,
) -> RoutingDecision:
    """Map provider errors to reason_code and engage fallback if configured."""
    fallback_enabled = getattr(config, "fallback_enabled", True)

    # Classify the error.
    if isinstance(exc, LlmTimeoutError):
        reason_code = "llm_timeout"
        retryable = True
    elif isinstance(exc, LlmProviderError):
        if 400 <= exc.status_code < 500:
            reason_code = "llm_error_4xx"
            retryable = False  # AC7.6 -- 4xx never falls back
        else:
            reason_code = "llm_error_5xx"
            retryable = True
    elif isinstance(exc, LlmMalformedOutputError):
        reason_code = "llm_malformed_output"
        retryable = True
    else:
        reason_code = "llm_malformed_output"
        retryable = True

    # Engage fallback if allowed.
    if retryable and fallback_enabled:
        fb_intent = fallback_classify(utterance)
        if fb_intent is not None:
            # Re-check scope for the fallback-classified intent.
            if _check_authority_scope(
                fb_intent,
                set(context.identity.authority_scope),
                set(context.identity.authority_excludes),
            ):
                target = TAXONOMY_DISPATCH[fb_intent]
                return RoutingDecision(
                    trace_id=context.trace_id,
                    utterance_sha256=digest,
                    intent=fb_intent,
                    confidence=0.5,
                    entities=entities,
                    selected_target=target,
                    fallback_used=True,
                    llm_latency_ms=0,
                    llm_model="fallback",
                    llm_provider="regex",
                    reason_code=reason_code,
                    tenant_id=context.tenant_id,
                )
        # Fallback attempted but missed OR scope-blocked.
        final_reason = (
            "regex_fallback_miss" if reason_code == "llm_timeout" else reason_code
        )
        return _build_escalate_decision(
            context=context,
            digest=digest,
            intent=IntentCategory.ESCALATE_TO_HUMAN,
            reason_code=final_reason,
            confidence=0.0,
            llm_latency_ms=0,
            llm_model="fallback",
            llm_provider="regex",
            fallback_used=True,
            entities=entities,
        )

    # No fallback (4xx OR fallback_enabled=False).
    return _build_escalate_decision(
        context=context,
        digest=digest,
        intent=IntentCategory.ESCALATE_TO_HUMAN,
        reason_code=reason_code,
        confidence=0.0,
        llm_latency_ms=0,
        llm_model="n/a",
        llm_provider="n/a",
        fallback_used=False,
        entities=entities,
    )


def _check_authority_scope(
    intent: IntentCategory,
    scopes: set[str],
    excludes: set[str],
) -> bool:
    """Return True if the identity may proceed with this intent.

    Fix 8 semantics:
    - required_scopes(intent) == () -> always allowed.
    - "*" in scopes AND required scope not in excludes -> allowed.
    - Any one required-scope-set fully covered by scopes -> allowed.
    - Otherwise denied.
    """
    req = required_scopes(intent)
    if not req:
        return True

    # "*" wildcard covers everything NOT in excludes.
    if "*" in scopes:
        for req_set in req:
            if not req_set & excludes:
                return True
        return False

    # Standard: any one required-scope-set fully satisfied, and NONE of the
    # scopes in that set are in excludes.
    for req_set in req:
        if req_set.issubset(scopes) and not (req_set & excludes):
            return True
    return False


# -----------------------------------------------------------------------------
# Builders.
# -----------------------------------------------------------------------------


def _build_escalate_decision(
    *,
    context: RouterContext,
    digest: str,
    intent: IntentCategory,
    reason_code: str,
    confidence: float,
    llm_latency_ms: int,
    llm_model: str,
    llm_provider: str,
    fallback_used: bool,
    entities: dict,
) -> RoutingDecision:
    """Build a RoutingDecision for any escalate-kind outcome."""
    target = TAXONOMY_DISPATCH[intent]
    # NaN confidence clamped to 0.0 for Pydantic acceptance.
    if isinstance(confidence, float) and math.isnan(confidence):
        confidence = 0.0
    return RoutingDecision(
        trace_id=context.trace_id,
        utterance_sha256=digest,
        intent=intent,
        confidence=confidence,
        entities=entities,
        selected_target=target,
        fallback_used=fallback_used,
        llm_latency_ms=llm_latency_ms,
        llm_model=llm_model,
        llm_provider=llm_provider,
        reason_code=reason_code,
        tenant_id=context.tenant_id,
    )


# -----------------------------------------------------------------------------
# Semaphore accounting.
# -----------------------------------------------------------------------------


def _acquire_inflight() -> None:
    _INFLIGHT.acquire()
    with _INFLIGHT_COUNT_LOCK:
        _INFLIGHT_COUNTER[0] += 1


def _release_inflight() -> None:
    with _INFLIGHT_COUNT_LOCK:
        _INFLIGHT_COUNTER[0] -= 1
    _INFLIGHT.release()


# -----------------------------------------------------------------------------
# Audit emission (R9, AC9.7, AC13.5).
# -----------------------------------------------------------------------------


def _emit_audit(decision: RoutingDecision) -> None:
    """R9 AC9.7 / AC13.5 -- the ONLY print() call site in M9."""
    print(  # noqa: T201 (intentional -- AC13.5 single-call audit emit)
        json.dumps(
            {"source": "m9", **decision.audit_payload()},
            sort_keys=True,
        )
    )
