"""
M12 Supervisor Specialists -- shared Protocol clients + Fake impls.

This module defines six Protocols that every specialist uses to reach
out of its boundary. Each Protocol is duck-typed -- a concrete impl
adapts a real trust-module (M2, M4, M6, M10) at the call site, NEVER
via a direct import from the specialist body. This matches the M8
precedent (see `src/m8_pipeline_engine/gateway_client.py` and
`audit_client.py`).

Why: `src/m12_supervisor/` has a strict import allowlist enforced by
`tests/security/test_m12_module_boundary.py` and its sibling
`test_m12_specialists_module_boundary.py`. Specialists need M6/M10
trust chain access WITHOUT importing those modules. Protocols give us
the seam.

Public surface -- grouped:

Protocols:
- PolicyClient          -- M2 AuthorityPolicy.evaluate shape
- MnpiSanitizer         -- M4 MnpiPolicy.filter shape
- GatewayClient         -- M6 TrustAwareGateway.call shape
- AuditClient           -- M10 AuditLogger.write shape (via dict entry)
- LLMProvider           -- Haiku call shape (routing / conversational)
- HitlApprovalVerifier  -- M8 hitl helpers shape

Shapes:
- PolicyResultShape     -- duck of M2's PolicyDecision
- GatewayResultShape    -- duck of M6's GatewayResponse

Fakes (for unit tests):
- FakePolicyClient / FakeMnpiSanitizer / FakeGatewayClient /
  FakeAuditClient / FakeLLMProvider / FakeHitlVerifier

Helper:
- canonical_sha256(obj) -- sorted-keys + compact-separators SHA-256 hex.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Protocol, runtime_checkable


# =============================================================================
# Result shapes (duck-typed over upstream module types)
# =============================================================================


@dataclass(frozen=True)
class PolicyResultShape:
    """Duck-typed copy of `m2_m4_policy_engine.PolicyDecision`.

    Field-for-field compatible so a thin adapter can produce a real
    `PolicyDecision` and return it verbatim when
    `PolicyResultShape = m2_m4_policy_engine.PolicyDecision`.

    `decision` is a string in {"ALLOW", "DENY", "ESCALATE"} to keep
    the Protocol dependency-free.
    """

    decision: str
    reason: str
    rule_applied: str
    wsp_section: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GatewayResultShape:
    """Duck-typed copy of M6 TrustAwareGateway's GatewayResponse.

    `decision` is str in {"ALLOW", "DENY", "ESCALATE"}; `result` is
    whatever the vendor returned (typically a dict).
    """

    decision: str
    result: Any
    trace_id: str
    latency_ms: int
    provenance_head: str
    rule_applied: Optional[str] = None
    wsp_section: Optional[str] = None
    reason: Optional[str] = None


# =============================================================================
# Protocols
# =============================================================================


@runtime_checkable
class PolicyClient(Protocol):
    """M2 AuthorityPolicy.evaluate shape.

    Implementations MUST return a PolicyResultShape (or a
    `m2_m4_policy_engine.PolicyDecision` -- field-compatible) and MUST
    NOT raise on normal denial paths. A raised exception is treated
    by the specialist as `reason_code="exec_unknown"` / fail-closed.
    """

    def evaluate(
        self,
        *,
        action: str,
        aid_claims: Any,
        target: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> PolicyResultShape:
        ...


@runtime_checkable
class MnpiSanitizer(Protocol):
    """M4 MnpiPolicy.filter shape.

    sanitize(claims, instance) -> sanitized_instance. Implementations
    MUST return the same Pydantic class (type-stable) or a plain dict
    for non-Pydantic inputs. Fail-closed: raising is the specialist's
    signal to return `reason_code="exec_mnpi_sanitize_failed"`.
    """

    def sanitize(self, aid_claims: Any, instance: Any) -> Any:
        ...


@runtime_checkable
class GatewayClient(Protocol):
    """M6 TrustAwareGateway.call shape.

    Implementations MUST return a GatewayResultShape on every call
    (including DENY/ESCALATE decisions). Network failures raise
    `GatewayUnavailable` which the specialist converts to
    `reason_code="exec_gateway_unavailable"`.
    """

    def call(
        self,
        *,
        tool_name: str,
        action: str,
        payload: Mapping[str, Any],
        aid_token: str,
        trace_id: str,
        firm_id: str,
        target: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> GatewayResultShape:
        ...


class GatewayUnavailable(Exception):
    """Raised by GatewayClient impls on network / mTLS failure.

    Specialists catch this and convert to a reason_code. NOT raised by
    the Protocol itself; raised by concrete impls (Fake or production
    adapter). Carries no request content.
    """


@runtime_checkable
class AuditClient(Protocol):
    """M10 AuditLogger / M10AuditClient shape.

    emit(entry_dict) MUST persist the entry to all tiers. Raising a
    normal `Exception` means the audit write failed -- the specialist
    surfaces `reason_code="*_audit_failed"`. The Protocol takes a
    `dict` (not a Pydantic model) so that specialists don't have to
    import `m3_schema_registry.AuditEntry`.
    """

    def emit(self, entry: Mapping[str, Any]) -> None:
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Haiku routing / conversational provider shape.

    generate(prompt, max_tokens, model) -> str. Specialists use this
    ONLY for order-intent extraction and conversational form filling.
    NO compliance decision is made by this path (Rule 5).
    """

    def generate(
        self,
        *,
        prompt: str,
        max_tokens: int,
        model: str,
    ) -> str:
        ...


@runtime_checkable
class HitlApprovalVerifier(Protocol):
    """Wraps M8's hitl.verify_approval_token + build_gate_payload.

    verify() returns None on success or a reason_code string on
    failure (matches M8's existing return-a-reason contract).
    build_gate_payload() returns an M8 HitlGatePayload Pydantic
    instance (re-used verbatim so downstream consumers keep one
    canonical shape).
    """

    def verify(
        self,
        approval: Any,
        *,
        gate_id: int,
        thread_id: str,
    ) -> Optional[str]:
        ...

    def build_gate_payload(
        self,
        *,
        gate_id: int,
        pipeline_run_id: str,
        thread_id: str,
        summary: Mapping[str, Any],
    ) -> Any:
        ...


# =============================================================================
# Helpers
# =============================================================================


def canonical_sha256(obj: Any) -> str:
    """Return SHA-256 hex of the canonical JSON of obj.

    Canonical JSON: sort_keys=True, separators=(',', ':'), ensure_ascii
    =False. Non-JSON-native types (UUID, datetime, Enum) are rendered
    via a fallback that mirrors M10's `_json_default` so hashes
    reconcile across modules.
    """

    def _default(v: Any) -> Any:
        # Keep in lockstep with M10 audit logger's _json_default.
        if isinstance(v, datetime):
            return v.isoformat()
        if hasattr(v, "isoformat"):  # date
            return v.isoformat()
        if hasattr(v, "value") and not isinstance(v, type):  # Enum-like
            return v.value
        if hasattr(v, "hex") and not callable(v.hex):  # UUID
            return str(v)
        raise TypeError(f"not serializable: {type(v).__name__}")

    if obj is None:
        payload = "null"
    else:
        payload = json.dumps(
            obj,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            default=_default,
        )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# =============================================================================
# Fakes (unit-test doubles)
# =============================================================================


class FakePolicyClient:
    """Seeded PolicyClient. Returns ALLOW by default."""

    def __init__(
        self,
        *,
        responses: Optional[dict[str, PolicyResultShape]] = None,
    ) -> None:
        self.responses: dict[str, PolicyResultShape] = dict(responses or {})
        self.recorded_calls: list[dict] = []

    def evaluate(
        self,
        *,
        action: str,
        aid_claims: Any,
        target: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> PolicyResultShape:
        self.recorded_calls.append(
            {
                "action": action,
                "target": dict(target),
                "context": dict(context),
            }
        )
        if action in self.responses:
            return self.responses[action]
        return PolicyResultShape(
            decision="ALLOW",
            reason="fake_allow",
            rule_applied="fake/allow.v1",
            wsp_section="WSP-FAKE-0.0",
        )


class FakeMnpiSanitizer:
    """Pass-through sanitizer.

    In tests that want to prove the sanitizer is called, use
    `fail_once=True` and inspect `.recorded_calls`. In tests that want
    to simulate MNPI-redaction failure, construct with
    `raise_on_call=True`.
    """

    def __init__(
        self,
        *,
        raise_on_call: bool = False,
        redact_fields: tuple[str, ...] = (),
    ) -> None:
        self.raise_on_call = raise_on_call
        self.redact_fields = redact_fields
        self.recorded_calls: list[Any] = []

    def sanitize(self, aid_claims: Any, instance: Any) -> Any:
        self.recorded_calls.append(instance)
        if self.raise_on_call:
            raise RuntimeError("simulated_sanitizer_failure")
        if not self.redact_fields or not hasattr(instance, "model_copy"):
            return instance
        # For Pydantic models, redact specific fields to None.
        updates = {f: None for f in self.redact_fields}
        return instance.model_copy(update=updates)


class FakeGatewayClient:
    """Seeded GatewayClient.

    - responses keyed by tool_name -> GatewayResultShape.
    - unavailable_tools set -> raises GatewayUnavailable.
    - Default: ALLOW with an empty result dict.
    """

    def __init__(
        self,
        *,
        responses: Optional[dict[str, GatewayResultShape]] = None,
        unavailable_tools: Optional[set[str]] = None,
    ) -> None:
        self.responses: dict[str, GatewayResultShape] = dict(responses or {})
        self.unavailable_tools: set[str] = set(unavailable_tools or ())
        self.recorded_calls: list[dict] = []

    def call(
        self,
        *,
        tool_name: str,
        action: str,
        payload: Mapping[str, Any],
        aid_token: str,
        trace_id: str,
        firm_id: str,
        target: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> GatewayResultShape:
        self.recorded_calls.append(
            {
                "tool_name": tool_name,
                "action": action,
                "payload": dict(payload),
                "trace_id": trace_id,
                "firm_id": firm_id,
                "target": dict(target),
                "context": dict(context),
            }
        )
        if tool_name in self.unavailable_tools:
            raise GatewayUnavailable("simulated_vendor_down")
        if tool_name in self.responses:
            return self.responses[tool_name]
        return GatewayResultShape(
            decision="ALLOW",
            result={"ok": True, "tool": tool_name},
            trace_id=trace_id,
            latency_ms=5,
            provenance_head="0" * 64,
            rule_applied=None,
            wsp_section=None,
            reason=None,
        )


class FakeAuditClient:
    """Records every emit into `.entries`. Optional fail_at index."""

    def __init__(self, *, fail_at: int = -1) -> None:
        self.entries: list[Mapping[str, Any]] = []
        self._fail_at = fail_at
        self._count = 0

    def emit(self, entry: Mapping[str, Any]) -> None:
        self._count += 1
        if self._count == self._fail_at:
            raise RuntimeError("simulated_audit_failure")
        # defensive copy
        self.entries.append(dict(entry))


class FakeLLMProvider:
    """Seeded LLM. Keyed by prompt prefix -> canned response."""

    def __init__(
        self,
        *,
        responses: Optional[dict[str, str]] = None,
        raise_on_call: bool = False,
    ) -> None:
        self.responses: dict[str, str] = dict(responses or {})
        self.raise_on_call = raise_on_call
        self.recorded_calls: list[dict] = []

    def generate(
        self,
        *,
        prompt: str,
        max_tokens: int,
        model: str,
    ) -> str:
        self.recorded_calls.append(
            {"prompt": prompt, "max_tokens": max_tokens, "model": model}
        )
        if self.raise_on_call:
            raise RuntimeError("simulated_llm_failure")
        for prefix, response in self.responses.items():
            if prompt.startswith(prefix):
                return response
        return "{}"


class FakeHitlVerifier:
    """Test HitlApprovalVerifier. Returns None by default (valid)."""

    def __init__(
        self,
        *,
        verify_result: Optional[str] = None,
    ) -> None:
        self.verify_result = verify_result  # None => valid
        self.recorded_verifies: list[dict] = []
        self.recorded_builds: list[dict] = []

    def verify(
        self,
        approval: Any,
        *,
        gate_id: int,
        thread_id: str,
    ) -> Optional[str]:
        self.recorded_verifies.append(
            {
                "gate_id": gate_id,
                "thread_id": thread_id,
                "approver_sub": getattr(approval, "approver_aid_sub", None),
            }
        )
        return self.verify_result

    def build_gate_payload(
        self,
        *,
        gate_id: int,
        pipeline_run_id: str,
        thread_id: str,
        summary: Mapping[str, Any],
    ) -> Any:
        # Import M8's real payload type so downstream consumers get the
        # canonical shape. m8_pipeline_engine is on the specialist's
        # positive allowlist (specialists may consume M8 models).
        from m8_pipeline_engine.models import HitlGatePayload

        self.recorded_builds.append(
            {
                "gate_id": gate_id,
                "pipeline_run_id": pipeline_run_id,
                "thread_id": thread_id,
            }
        )
        # M8 HitlGatePayload insists on gate_id in {1,2,3} and
        # stage_number in {7,13,21}. We re-use gate_id=1 mapping to
        # stage_number=7 for specialist gates (execution + onboarding
        # both use gate 1 semantics: review-before-commit).
        stage_map = {1: 7, 2: 13, 3: 21}
        role_map = {
            1: "supervising_advisor",
            2: "compliance_officer",
            3: "principal",
        }
        return HitlGatePayload(
            gate_id=gate_id,  # type: ignore[arg-type]
            pipeline_run_id=pipeline_run_id,
            thread_id=thread_id,
            stage_number=stage_map.get(gate_id, 7),  # type: ignore[arg-type]
            approver_role_required=role_map.get(
                gate_id, "supervising_advisor"
            ),
            summary=dict(summary),
            emitted_at=datetime.now(timezone.utc),
        )


__all__ = [
    # Shapes
    "PolicyResultShape",
    "GatewayResultShape",
    # Protocols
    "PolicyClient",
    "MnpiSanitizer",
    "GatewayClient",
    "AuditClient",
    "LLMProvider",
    "HitlApprovalVerifier",
    "GatewayUnavailable",
    # Fakes
    "FakePolicyClient",
    "FakeMnpiSanitizer",
    "FakeGatewayClient",
    "FakeAuditClient",
    "FakeLLMProvider",
    "FakeHitlVerifier",
    # Helpers
    "canonical_sha256",
]
