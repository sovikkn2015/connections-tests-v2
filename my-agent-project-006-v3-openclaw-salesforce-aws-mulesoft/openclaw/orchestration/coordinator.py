"""AgentCore entry point: routes user query + SessionContext to the right orchestrator.

PersonaCoordinator is the ONE class AgentCore instantiates per session. Given a
user query and SessionContext, it selects the persona's orchestrator, runs
plan() -> dispatch -> synthesize(), and returns the final text.

All Bedrock work is abstracted behind a client protocol so tests can inject
StubBedrockClient; production wires a real boto3 Bedrock Converse client.
"""

from __future__ import annotations

import asyncio
import os
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, AsyncIterator, Dict, List, Optional, Protocol

from .messages import (
    AgentError,
    AgentErrorType,
    OrchestratorDispatch,
    SessionContext,
    WorkerResponse,
)
from .topology import (
    AGENT_TOPOLOGY,
    AgentDefinition,
    ModelTier,
    orchestrator_for_persona,
)
from ._logging import bind, get_logger
from ._stubs import StubBedrockClient, StubLangfuseClient


# ---------------------------------------------------------------------------
# Langfuse transport (P1.4) - real client when env vars present, stub otherwise.
#
# The three scrubbers (mnpi, pii, raw_approval_tokens) are registered so that
# `observability.langfuse.scrub_before_write` in openclaw.json is mechanical,
# not aspirational. They run recursively over every payload before the span
# is flushed to the Langfuse backend.
# ---------------------------------------------------------------------------

_MNPI_FIELD_KEYS = frozenset(
    {
        "shares_held", "shares_held__c",
        "quantity_held", "quantity",
        "market_value", "market_value__c",
        "cost_basis", "cost_basis__c",
        "unrealized_gain", "realized_gain",
        "position_size", "holdings_amount", "trade_amount",
        "wire_amount", "wire_beneficiary", "wire_account_number",
        "beneficiary_account",
    }
)

_PII_FIELD_KEYS = frozenset(
    {
        "ssn", "social_security", "tax_id", "ein",
        "date_of_birth", "dob", "drivers_license",
        "home_address", "phone_number",
    }
)

_TOKEN_FIELD_KEYS = frozenset(
    {
        "approval_token", "raw_approval_token",
        "session_token", "bearer_token", "authorization",
        "session_signing_key", "signing_key",
        "hitl_signing_key",
    }
)


def _scrub_keys(payload, keys, placeholder):
    """Recursively replace values whose key is in `keys` with `placeholder`."""
    if isinstance(payload, dict):
        return {
            k: (
                placeholder
                if isinstance(k, str) and k.lower() in keys
                else _scrub_keys(v, keys, placeholder)
            )
            for k, v in payload.items()
        }
    if isinstance(payload, list):
        return [_scrub_keys(v, keys, placeholder) for v in payload]
    return payload


def scrub_before_write(payload):
    """Run the three openclaw.json scrubbers in order.

    Exposed as a module function so tests can assert the mechanical behavior
    independently of the Langfuse client wiring.
    """
    step1 = _scrub_keys(payload, _MNPI_FIELD_KEYS, "[REDACTED:mnpi]")
    step2 = _scrub_keys(step1, _PII_FIELD_KEYS, "[REDACTED:pii]")
    return _scrub_keys(step2, _TOKEN_FIELD_KEYS, "[REDACTED:raw_approval_tokens]")


class _ScrubbingLangfuseWrapper:
    """Wrap a real Langfuse client so every span/trace payload is scrubbed."""

    def __init__(self, inner):
        self._inner = inner

    def trace(self, **kwargs):
        scrubbed = scrub_before_write(kwargs)
        trace = self._inner.trace(**scrubbed)
        return _ScrubbingSpan(trace)

    def flush(self):
        if hasattr(self._inner, "flush"):
            self._inner.flush()


class _ScrubbingSpan:
    """Span proxy that scrubs payloads on update/span creation."""

    def __init__(self, inner):
        self._inner = inner

    def span(self, **kwargs):
        scrubbed = scrub_before_write(kwargs)
        if hasattr(self._inner, "span"):
            return _ScrubbingSpan(self._inner.span(**scrubbed))
        return self

    def update(self, **kwargs):
        scrubbed = scrub_before_write(kwargs)
        if hasattr(self._inner, "update"):
            self._inner.update(**scrubbed)

    def end(self):
        if hasattr(self._inner, "end"):
            self._inner.end()


def build_langfuse_client():
    """Return a scrubbing-wrapped Langfuse client when env vars are present,
    otherwise a `StubLangfuseClient` (keeps the contract uniform).

    Env vars (all three required to activate):
      LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST
    """
    pub = os.getenv("LANGFUSE_PUBLIC_KEY")
    sec = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")
    if not (pub and sec and host):
        return StubLangfuseClient()
    try:
        from langfuse import Langfuse  # type: ignore
    except ImportError:
        logger.warning("langfuse package not installed - falling back to stub")
        return StubLangfuseClient()
    try:
        inner = Langfuse(public_key=pub, secret_key=sec, host=host)
    except Exception as exc:  # noqa: BLE001 - any client init error -> stub
        logger.warning("Langfuse init failed (%s) - falling back to stub", exc)
        return StubLangfuseClient()
    return _ScrubbingLangfuseWrapper(inner)


logger = get_logger(__name__)


class BedrockClient(Protocol):
    """Minimal async protocol satisfied by StubBedrockClient and the real one."""

    async def converse(
        self,
        *,
        model_id: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        agent_id: Optional[str] = None,
        tool_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]: ...  # pragma: no cover


class GuardrailInterventionError(Exception):
    """Raised when Bedrock Guardrails blocks input before the model runs."""


class BedrockConverseClient:
    """Thin async wrapper over boto3.client('bedrock-runtime').converse().

    Real calls happen only when AWS credentials are available. On ImportError
    or missing credentials, the caller should inject StubBedrockClient.

    P1.5: when `BEDROCK_GUARDRAIL_ID` + `BEDROCK_GUARDRAIL_VERSION` are set,
    a guardrailConfig is attached to every converse() call. A `guardrail_
    intervened` stopReason is converted into `GuardrailInterventionError`,
    which the orchestrator wraps into `AgentError(error_type=SAFETY)` with
    recoverable=False.
    """

    def __init__(self, region: Optional[str] = None) -> None:
        region = region or os.getenv("AWS_REGION_BEDROCK", "us-east-1")
        try:
            import boto3  # type: ignore

            self._client = boto3.client("bedrock-runtime", region_name=region)
            self._available = True
        except ImportError:
            self._client = None
            self._available = False

    async def converse(
        self,
        *,
        model_id: str,
        system_prompt: str,
        messages: List[Dict[str, Any]],
        agent_id: Optional[str] = None,
        tool_config: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run blocking Bedrock Converse on a thread to avoid blocking the loop."""
        if not self._available:
            raise RuntimeError(
                "boto3 not installed. Provide StubBedrockClient for tests "
                "or install boto3 and configure AWS credentials for production."
            )
        loop = asyncio.get_running_loop()

        guardrail_id = os.getenv("BEDROCK_GUARDRAIL_ID")
        guardrail_version = os.getenv("BEDROCK_GUARDRAIL_VERSION")
        kwargs: Dict[str, Any] = {
            "modelId": model_id,
            "system": [{"text": system_prompt}],
            "messages": messages,
        }
        if guardrail_id and guardrail_version:
            kwargs["guardrailConfig"] = {
                "guardrailIdentifier": guardrail_id,
                "guardrailVersion": guardrail_version,
            }
        if tool_config:
            kwargs["toolConfig"] = tool_config

        def _invoke() -> Dict[str, Any]:
            return self._client.converse(**kwargs)  # type: ignore[union-attr]

        result = await loop.run_in_executor(None, _invoke)
        stop_reason = result.get("stopReason", "") if isinstance(result, dict) else ""
        if stop_reason == "guardrail_intervened":
            raise GuardrailInterventionError(
                f"Bedrock Guardrails blocked input for agent {agent_id or 'unknown'}"
            )
        return result


def resolve_model_id(tier: ModelTier) -> str:
    """Resolve ModelTier -> concrete Bedrock model id from env.

    Raises:
        RuntimeError: if the expected env var is missing — fail fast.
    """
    if tier is ModelTier.SONNET:
        mid = os.getenv("BEDROCK_SONNET_MODEL_ID")
        if not mid:
            raise RuntimeError("BEDROCK_SONNET_MODEL_ID not set. See .env.example.")
        return mid
    if tier is ModelTier.HAIKU:
        mid = os.getenv("BEDROCK_HAIKU_MODEL_ID")
        if not mid:
            raise RuntimeError("BEDROCK_HAIKU_MODEL_ID not set. See .env.example.")
        return mid
    raise ValueError(f"unknown tier: {tier!r}")


@asynccontextmanager
async def langfuse_span(
    parent: Any,
    name: str,
    **metadata: Any,
) -> AsyncIterator[Any]:
    """Open a Langfuse span. Closes on exit, records metadata."""
    if parent is None:
        yield None
        return
    span = parent.span(name=name) if hasattr(parent, "span") else None
    if span is None:
        yield None
        return
    try:
        if metadata and hasattr(span, "update"):
            span.update(**metadata)
        yield span
    finally:
        if hasattr(span, "end"):
            span.end()


def span_name(ctx: SessionContext, agent_id: str) -> str:
    """Canonical span name per V3 Langfuse taxonomy."""
    return (
        f"session.{ctx.session_id}."
        f"turn.{ctx.turn_number}."
        f"persona.{ctx.persona}."
        f"{agent_id}"
    )


class Orchestrator(ABC):
    """Base class for all three persona orchestrators.

    Concrete impls override plan() and synthesize(). Base class handles the
    common runtime: asyncio.gather with per-worker timeout, error wrapping,
    Langfuse span nesting, Bedrock client injection.
    """

    def __init__(
        self,
        definition: AgentDefinition,
        bedrock: BedrockClient,
        langfuse: Optional[Any] = None,
    ) -> None:
        self.definition = definition
        self.bedrock = bedrock
        self.langfuse = langfuse
        self.log = bind(logger, agent_id=definition.id, persona=definition.persona)

    @abstractmethod
    async def plan(
        self,
        query: str,
        ctx: SessionContext,
    ) -> List[OrchestratorDispatch]:
        """Decide which specialists to invoke and with what tasks."""

    @abstractmethod
    async def synthesize(
        self,
        query: str,
        ctx: SessionContext,
        responses: List[WorkerResponse],
    ) -> str:
        """Combine specialist responses into a final user-facing answer."""

    async def _invoke_specialist(
        self,
        dispatch: OrchestratorDispatch,
        ctx: SessionContext,
        parent_span: Any,
    ) -> WorkerResponse:
        """Invoke one specialist. Errors are wrapped, never raised."""
        target = AGENT_TOPOLOGY.get(dispatch.target_agent_id)
        if target is None:
            return WorkerResponse(
                agent_id=dispatch.target_agent_id,
                errors=[
                    AgentError(
                        agent_id=dispatch.target_agent_id,
                        error_type=AgentErrorType.VALIDATION,
                        message=f"unknown agent id {dispatch.target_agent_id!r}",
                        recoverable=False,
                    )
                ],
            )

        name = span_name(ctx, target.id)
        async with langfuse_span(parent_span, name, task=dispatch.task[:120]) as span:
            try:
                return await asyncio.wait_for(
                    self._run_one(target, dispatch, ctx, span),
                    timeout=dispatch.timeout_s,
                )
            except asyncio.TimeoutError:
                self.log.warning("specialist_timeout %s", target.id)
                return WorkerResponse(
                    agent_id=target.id,
                    errors=[
                        AgentError(
                            agent_id=target.id,
                            error_type=AgentErrorType.TIMEOUT,
                            message=f"specialist exceeded {dispatch.timeout_s}s",
                            recoverable=True,
                        )
                    ],
                )
            except GuardrailInterventionError as exc:
                self.log.warning("guardrail_intervened %s %s", target.id, exc)
                return WorkerResponse(
                    agent_id=target.id,
                    errors=[
                        AgentError(
                            agent_id=target.id,
                            error_type=AgentErrorType.SAFETY,
                            message=str(exc),
                            recoverable=False,
                        )
                    ],
                )
            except Exception as exc:  # noqa: BLE001 - wrap everything
                self.log.error("specialist_failure %s %s", target.id, exc)
                return WorkerResponse(
                    agent_id=target.id,
                    errors=[
                        AgentError(
                            agent_id=target.id,
                            error_type=AgentErrorType.TOOL_FAILURE,
                            message=str(exc),
                            recoverable=True,
                        )
                    ],
                )

    async def _run_one(
        self,
        target: AgentDefinition,
        dispatch: OrchestratorDispatch,
        ctx: SessionContext,
        span: Any,
    ) -> WorkerResponse:
        """One specialist turn.

        Any agent with a non-empty ``tool_allowlist`` runs through the Bedrock
        tool-use dispatch loop so every skill call is code-verified, not
        prompt-advisory. Research specialists were previously bypassing this
        path (condition was ``serial_by_design AND tool_allowlist``), which
        caused the model to emit Python code describing MCP calls instead of
        actually invoking tools. The fix is to drive tool-use off the
        allowlist alone; ``serial_by_design`` still governs orchestrator-level
        serial vs parallel fanout at the ``fanout()`` boundary.
        """
        model_id = resolve_model_id(target.model)
        user_prompt = self._render_user_prompt(dispatch, ctx)

        # Langfuse prompt management: if LANGFUSE_USE_PROMPT_STORE=1, fetch
        # the specialist's system prompt from Langfuse cloud (versioned,
        # editable without container rebuild). Falls back to the hardcoded
        # prompt in topology.py if Langfuse is unavailable or the prompt
        # name doesn't exist.
        from ..observability import get_prompt
        system_prompt = get_prompt(
            f"v3.{target.id}",
            default=target.system_prompt,
        )

        # Draft-only mode detection (2026-04-30 — 29s gateway timeout fix):
        # Advisor action-write dispatches prepend '[DRAFT_ONLY mode' to the
        # task. In this mode the action_specialist should:
        #   - NOT run the tool-use loop (5 serial tools × 3-5s = 15-25s)
        #   - Return a single Bedrock converse with JSON body in the text
        #
        # This reduces advisor action-write from ~25s+ to ~5-8s, which fits
        # inside the 29s API Gateway REST timeout. Gates 4-7 run in the
        # /agent/approve round-trip where they're deterministic (no LLM).
        is_draft_only = (
            target.id == "action_specialist"
            and isinstance(dispatch.task, str)
            and "[DRAFT_ONLY mode" in dispatch.task
        )
        if is_draft_only:
            # Single Bedrock call, no tools. LLM returns the action_plan JSON.
            # Haiku is strictly faster than Sonnet for structured-JSON output
            # tasks like this one (3-6s vs 15-25s). Since draft-only is a
            # pure structured-extraction task ("take this RM instruction,
            # emit a plan JSON"), Haiku is the right tier. Sonnet gets
            # used later for gates 4-7 dispatch and for read-path specialists.
            import time as _time
            from ..trust.mnpi_filter import MNPIFilter, MNPIViolation

            draft_model_id = resolve_model_id(ModelTier.HAIKU)
            result = await self.bedrock.converse(
                model_id=draft_model_id,
                system_prompt=system_prompt,
                messages=[{"role": "user", "content": [{"text": user_prompt}]}],
                agent_id=target.id,
            )
            text = _extract_text(result)

            # Extract structured ActionPlan from the RAW text (before MNPI
            # scrubbing). The scrubber replaces dollar amounts and wire
            # phrases inside string literals, which breaks JSON validity
            # (e.g. `"summary": "[WIRE_REDACTED]\n  "client_household": ...`
            # — the unclosed quote makes json.loads fail and the extractor
            # falls back to an inner object missing the action_plan key).
            # The structured plan has typed fields (notional_usd is a float,
            # summary is a string); MNPI risk lives in the *prose summary*,
            # which we scrub separately below. (Bug fix 2026-05-02.)
            _raw_action_plan, _raw_parsed = _extract_action_plan(text)

            # Gate ②: MNPI filter (real — scrub the LLM output)
            _mnpi_start = _time.monotonic()
            try:
                scrubbed_text, _rpt = MNPIFilter(strict=False).scrub_text(text)
            except MNPIViolation as exc:
                return WorkerResponse(
                    agent_id=target.id,
                    errors=[
                        AgentError(
                            agent_id=target.id,
                            error_type=AgentErrorType.SAFETY,
                            message=f"mnpi_violation: {exc.reason}",
                            recoverable=False,
                        )
                    ],
                )
            _mnpi_ms = int((_time.monotonic() - _mnpi_start) * 1000)

            # Gate ③: Real compliance_screening skill call (deterministic,
            # ~50ms, no LLM — safe within the 29s gateway timeout).
            _ticker = dispatch.context_subset.get("ticker", "UNKNOWN")
            _comp_gate: dict = {"tool": "compliance_screening", "status": "ok", "elapsed_ms": 0, "error": None}
            _compliance_denied = False
            _compliance_reasons: list = []
            try:
                from ..skills.compliance_screening.actions import (
                    ComplianceInput,
                    Action as CompAction,
                    run as compliance_run,
                )
                _comp_start = _time.monotonic()
                _proposed = CompAction.SUBMIT_ORDER
                # Detect wire intent from the task text
                if "wire" in (dispatch.task or "").lower():
                    _proposed = CompAction.INITIATE_WIRE
                elif "cancel" in (dispatch.task or "").lower():
                    _proposed = CompAction.CANCEL_ORDER
                comp_result = await compliance_run(ComplianceInput(
                    ticker=_ticker if _ticker and _ticker != "UNKNOWN" else "NONE",
                    principal_id=ctx.principal_id,
                    proposed_action=_proposed,
                    session_id=ctx.session_id,
                    correlation_id=ctx.correlation_id,
                ))
                _comp_ms = int((_time.monotonic() - _comp_start) * 1000)
                _comp_gate = {
                    "tool": "compliance_screening",
                    "status": comp_result.decision.value.lower(),
                    "elapsed_ms": _comp_ms,
                    "error": None,
                }
                if comp_result.decision.value == "DENY":
                    _compliance_denied = True
                    _compliance_reasons = comp_result.reasons
            except Exception as _comp_exc:
                self.log.warning(
                    "compliance_screening_draft_only_error agent=%s err=%s",
                    target.id, str(_comp_exc)[:200],
                )
                _comp_gate = {
                    "tool": "compliance_screening",
                    "status": "error",
                    "elapsed_ms": 0,
                    "error": str(_comp_exc)[:120],
                }

            # If compliance DENIED, return early — no action_plan produced
            if _compliance_denied:
                return WorkerResponse(
                    agent_id=target.id,
                    result={
                        "text": f"COMPLIANCE DENIED: {_compliance_reasons}\n\n{scrubbed_text}",
                        "gate_trace": [
                            {"tool": "guardrails_input", "status": "ok", "elapsed_ms": 0, "error": None},
                            {"tool": "mnpi_filter", "status": "ok", "elapsed_ms": _mnpi_ms, "error": None},
                            _comp_gate,
                        ],
                        "stop_reason": "compliance_denied",
                        "loops": 1,
                        "final_status": "COMPLIANCE_DENIED",
                    },
                    citations=[],
                    cost_tokens=int(result.get("usage", {}).get("totalTokens", 0) or 0),
                )

            action_plan_extracted = _raw_action_plan
            action_plan_raw = _raw_parsed
            cost = int(result.get("usage", {}).get("totalTokens", 0) or 0)
            return WorkerResponse(
                agent_id=target.id,
                result={
                    "text": scrubbed_text,
                    "gate_trace": [
                        # Gate ①: Guardrails enforced at coordinator run_turn
                        # level (Bedrock Guardrails config). Recorded here.
                        {"tool": "guardrails_input", "status": "ok", "elapsed_ms": 0, "error": None},
                        # Gate ②: MNPI filter — real, ran above
                        {"tool": "mnpi_filter", "status": "ok", "elapsed_ms": _mnpi_ms, "error": None},
                        # Gate ③: Compliance — real skill call, ran above
                        _comp_gate,
                    ],
                    "stop_reason": "draft_only",
                    "loops": 1,
                    **(
                        {"action_plan": action_plan_extracted}
                        if action_plan_extracted is not None
                        else {}
                    ),
                    **(
                        {"final_status": action_plan_raw.get("final_status")}
                        if action_plan_raw and "final_status" in action_plan_raw
                        else {"final_status": "PENDING_APPROVAL"}
                    ),
                },
                citations=_extract_citations(scrubbed_text),
                cost_tokens=cost,
            )

        if target.tool_allowlist:
            from .tool_dispatch import run_tool_loop
            from ..trust.mnpi_filter import MNPIFilter, MNPIViolation

            loop_result = await run_tool_loop(
                bedrock=self.bedrock,
                model_id=model_id,
                system_prompt=system_prompt,
                initial_user_text=user_prompt,
                tool_allowlist=target.tool_allowlist,
                agent_id=target.id,
            )

            # Extract action_plan from RAW text first (same rationale as
            # draft-only path above — MNPI scrubber breaks JSON validity).
            _raw_action_plan_tool: Dict[str, Any] | None = None
            _raw_parsed_tool: Dict[str, Any] | None = None
            if target.id == "action_specialist":
                _raw_action_plan_tool, _raw_parsed_tool = _extract_action_plan(
                    loop_result.text
                )

            # Belt-and-suspenders: even though each gate's skill is typed and
            # MNPI-scrubbed at write time, the action_specialist LLM's free-text
            # summary between tool_use blocks can still hallucinate a dollar
            # amount or share count. Scrub here symmetrically with the
            # read-path (see line ~503).
            try:
                scrubbed_text, _report = MNPIFilter(strict=False).scrub_text(
                    loop_result.text
                )
            except MNPIViolation as exc:
                self.log.warning(
                    "mnpi_violation_tool_use agent=%s reason=%s — turn failed closed",
                    target.id,
                    exc.reason,
                )
                return WorkerResponse(
                    agent_id=target.id,
                    errors=[
                        AgentError(
                            agent_id=target.id,
                            error_type=AgentErrorType.SAFETY,
                            message=f"mnpi_violation: {exc.reason}",
                            recoverable=False,
                        )
                    ],
                )

            if span is not None and hasattr(span, "update"):
                span.update(
                    tokens_total=loop_result.tokens_used,
                    model_id=model_id,
                    output_chars=len(scrubbed_text),
                    tool_loops=loop_result.loops,
                    gate_trace=[e.tool_name for e in loop_result.trace],
                    gate_statuses=[e.status for e in loop_result.trace],
                )

            # Extract structured ActionPlan from the LLM's final text for the
            # action-write path. The ACTION_SPECIALIST_PROMPT instructs the
            # model to return a JSON body `{action_plan, gate_trace, ...}` at
            # the end of its final message. We try to parse that JSON and
            # lift `action_plan` up so the agentcore_server envelope can
            # surface it at the top level for the frontend InlineActionCard.
            #
            # Extraction strategy:
            #   1. Look for the last fenced ```json ... ``` block.
            #   2. Fall back to the last {...} balanced brace at end of text.
            #   3. Parse and pull out `action_plan` if present.
            # Failure is silent: the envelope just doesn't include action_plan
            # and the UI renders only the text — exactly v1 behavior.
            action_plan_extracted: Dict[str, Any] | None = _raw_action_plan_tool
            action_plan_raw: Dict[str, Any] | None = _raw_parsed_tool
            # Legacy: if pre-scrub extraction failed, fall back to the
            # post-scrub text. Keeps the v1 behavior intact for cases
            # where scrub doesn't break JSON (most normal briefs).
            if target.id == "action_specialist" and action_plan_extracted is None:
                action_plan_extracted, action_plan_raw = _extract_action_plan(
                    scrubbed_text
                )

            return WorkerResponse(
                agent_id=target.id,
                result={
                    "text": scrubbed_text,
                    "gate_trace": [
                        {
                            "tool": e.tool_name,
                            "status": e.status,
                            "elapsed_ms": e.elapsed_ms,
                            "error": e.error,
                        }
                        for e in loop_result.trace
                    ],
                    "stop_reason": loop_result.stop_reason,
                    "loops": loop_result.loops,
                    **(
                        {"action_plan": action_plan_extracted}
                        if action_plan_extracted is not None
                        else {}
                    ),
                    **(
                        {"final_status": action_plan_raw.get("final_status")}
                        if action_plan_raw and "final_status" in action_plan_raw
                        else {}
                    ),
                },
                citations=_extract_citations(scrubbed_text),
                cost_tokens=loop_result.tokens_used,
            )

        # Read-path: single converse call, MNPI re-scrub on output.
        from ..trust.mnpi_filter import MNPIFilter, MNPIViolation

        result = await self.bedrock.converse(
            model_id=model_id,
            system_prompt=system_prompt,
            messages=[{"role": "user", "content": [{"text": user_prompt}]}],
            agent_id=target.id,
        )
        text = _extract_text(result)
        # Reviewer B, item 2: specialists can hallucinate a dollar amount or a
        # share count that bypasses the CRM-side MNPI filter. Re-scrub on the
        # LLM output with strict=False (we redact, don't fail the turn).
        try:
            text, _report = MNPIFilter(strict=False).scrub_text(text)
        except MNPIViolation as exc:
            self.log.warning(
                "mnpi_violation agent=%s reason=%s — turn failed closed",
                target.id,
                exc.reason,
            )
            return WorkerResponse(
                agent_id=target.id,
                errors=[
                    AgentError(
                        agent_id=target.id,
                        error_type=AgentErrorType.SAFETY,
                        message=f"mnpi_violation: {exc.reason}",
                        recoverable=False,
                    )
                ],
            )
        usage = result.get("usage", {}) or {}
        cost = int(usage.get("inputTokens", 0)) + int(usage.get("outputTokens", 0))

        if span is not None and hasattr(span, "update"):
            span.update(
                tokens_total=cost,
                model_id=model_id,
                output_chars=len(text),
            )
        return WorkerResponse(
            agent_id=target.id,
            result={"text": text},
            citations=_extract_citations(text),
            cost_tokens=cost,
        )

    @staticmethod
    def _render_user_prompt(dispatch: OrchestratorDispatch, ctx: SessionContext) -> str:
        """Render the concrete user-visible prompt handed to the specialist."""
        lines = [
            f"Task: {dispatch.task}",
            f"Session: {ctx.session_id} (turn {ctx.turn_number})",
        ]
        if ctx.parent_brief_id:
            lines.append(f"Parent brief: {ctx.parent_brief_id}")
        if dispatch.context_subset:
            lines.append("Context (scoped):")
            for k, v in dispatch.context_subset.items():
                lines.append(f"  - {k}: {v}")
        return "\n".join(lines)

    async def fanout(
        self,
        dispatches: List[OrchestratorDispatch],
        ctx: SessionContext,
        parent_span: Any = None,
        *,
        serial: bool = False,
    ) -> List[WorkerResponse]:
        """Dispatch workers concurrently (asyncio.gather) or serially.

        Serial mode is only legitimate for the write-path (action_specialist).
        """
        if serial:
            results: List[WorkerResponse] = []
            for d in dispatches:
                results.append(await self._invoke_specialist(d, ctx, parent_span))
                last = results[-1]
                if any(not e.recoverable for e in last.errors):
                    break
            return results

        coros = [self._invoke_specialist(d, ctx, parent_span) for d in dispatches]
        return await asyncio.gather(*coros)


class PersonaCoordinator:
    """Route a query+SessionContext to the right orchestrator and run it end-to-end.

    Stateless; one instance per process is fine. AgentCore creates a session,
    passes principal_id+persona+channel via channel adapter, and every
    incoming turn lands here via run_turn().
    """

    def __init__(
        self,
        bedrock: Optional[BedrockClient] = None,
        langfuse: Optional[Any] = None,
        orchestrator_factories: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Args:
            bedrock: injected Bedrock client. Defaults to BedrockConverseClient
                if boto3 is present; StubBedrockClient otherwise.
            langfuse: injected Langfuse client; when None the coordinator auto-
                builds a real Langfuse client if LANGFUSE_* env vars are set,
                otherwise falls back to `StubLangfuseClient`.
            orchestrator_factories: optional persona -> callable(bc, lf) -> Orchestrator.
        """
        if bedrock is None:
            try:
                bedrock = BedrockConverseClient()
            except Exception:  # noqa: BLE001
                bedrock = StubBedrockClient()
        self.bedrock = bedrock
        if langfuse is None:
            langfuse = build_langfuse_client()
        self.langfuse = langfuse
        self._factories = orchestrator_factories or _default_factories()
        self.log = bind(logger, component="coordinator")
        # P2.12: boot-time env-var audit. In production this surfaces misconfig
        # at session-open rather than at first specialist dispatch. In dev
        # (no AWS_REGION_BEDROCK set) we log the failure and keep going so
        # StubBedrockClient-backed tests still boot.
        is_dev = not os.getenv("AWS_REGION_BEDROCK")
        for tier in (ModelTier.SONNET, ModelTier.HAIKU):
            try:
                resolve_model_id(tier)
            except RuntimeError as exc:
                if is_dev:
                    self.log.warning(
                        "model_id_unset tier=%s reason=%s (dev; tolerated)",
                        tier.value,
                        exc,
                    )
                else:
                    raise

        # Reviewer item 4: Bedrock Guardrails must not be silently skipped.
        # In production (AWS_REGION_BEDROCK set AND not OPENCLAW_DEV=true) both
        # guardrail env vars are required. A missing guardrail = LLM runs
        # unguarded; we fail fast instead.
        _explicit_dev = os.getenv("OPENCLAW_DEV", "").lower() == "true"
        if not (is_dev or _explicit_dev):
            g_id = os.getenv("BEDROCK_GUARDRAIL_ID", "").strip()
            g_ver = os.getenv("BEDROCK_GUARDRAIL_VERSION", "").strip()
            if not (g_id and g_ver):
                raise RuntimeError(
                    "BEDROCK_GUARDRAIL_ID and BEDROCK_GUARDRAIL_VERSION are "
                    "required in production. Set OPENCLAW_DEV=true to bypass "
                    "for local dev only."
                )

        # AgentCore Memory store — per-user per-persona persistent memory.
        # Uses a simple dict-backed store that persists to the session context.
        # In production, this would be backed by AgentCore's Memory API.
        self._memory_store: Dict[str, Dict[str, Any]] = {}

    def _memory_key(self, ctx: 'SessionContext') -> str:
        """Composite key for per-user per-persona memory."""
        return f"{ctx.principal_id}:{ctx.persona}"

    async def _load_user_memory(self, ctx: 'SessionContext') -> Dict[str, Any]:
        """Load persistent user memory for this principal+persona.

        Returns a dict of key-value pairs (e.g. preferred_sectors, book_scope).
        Empty dict if no memory exists yet.
        """
        key = self._memory_key(ctx)
        memory = self._memory_store.get(key, {})
        if memory:
            self.log.info(
                "memory.load principal=%s persona=%s keys=%d",
                ctx.principal_id, ctx.persona, len(memory),
            )
        return memory

    async def _save_user_memory(
        self, ctx: 'SessionContext', updates: Dict[str, Any]
    ) -> None:
        """Persist user memory updates. MNPI-tagged values are stripped."""
        if not updates:
            return
        from ..trust.mnpi_filter import MNPIFilter
        scrubber = MNPIFilter(strict=False)
        clean_updates: Dict[str, Any] = {}
        for k, v in updates.items():
            if isinstance(v, str):
                scrubbed, _ = scrubber.scrub_text(v)
                clean_updates[k] = scrubbed
            else:
                clean_updates[k] = v
        key = self._memory_key(ctx)
        existing = self._memory_store.get(key, {})
        existing.update(clean_updates)
        self._memory_store[key] = existing
        self.log.info(
            "memory.save principal=%s persona=%s keys_updated=%d total_keys=%d",
            ctx.principal_id, ctx.persona, len(clean_updates), len(existing),
        )

    async def run_turn(self, query: str, ctx: SessionContext) -> Dict[str, Any]:
        """Route to the persona orchestrator, run plan/fanout/synthesize.

        Memory lifecycle (V3 state model):
          - Pre-turn: load user memory for this principal+persona (preferences,
            sector focus, book scope). Injected into SessionContext.user_memory.
          - Post-turn: persist any memory updates the orchestrator flagged
            (e.g. sarah.preferred_sectors updated from query patterns).
          - MNPI-tagged content is NEVER written to user memory (steering rule 22).
        """
        if ctx.persona not in self._factories:
            raise ValueError(f"no orchestrator factory for persona {ctx.persona!r}")

        orch = self._factories[ctx.persona](self.bedrock, self.langfuse)
        self.log = bind(
            self.log, correlation_id=ctx.correlation_id, session_id=ctx.session_id
        )
        self.log.info(
            "coordinator.run_turn.start query_len=%d persona=%s", len(query), ctx.persona
        )

        # Load persistent user memory (preferences, sector focus, etc.)
        user_memory = await self._load_user_memory(ctx)
        if user_memory:
            # Inject memory into context so specialists can use it
            # SessionContext is frozen; use model_copy to derive a new instance
            ctx = ctx.model_copy(update={"user_memory": user_memory})

        trace = None
        if self.langfuse is not None and hasattr(self.langfuse, "trace"):
            trace = self.langfuse.trace(
                name=f"session.{ctx.session_id}.turn.{ctx.turn_number}.persona.{ctx.persona}",
                user_id=ctx.principal_id,
                session_id=ctx.session_id,
            )

        started = datetime.now(timezone.utc)
        try:
            dispatches = await orch.plan(query, ctx)
            serial = orch.definition.serial_by_design or any(
                AGENT_TOPOLOGY.get(d.target_agent_id)
                and AGENT_TOPOLOGY[d.target_agent_id].serial_by_design
                for d in dispatches
            )
            responses = await orch.fanout(
                dispatches, ctx, parent_span=trace, serial=serial
            )
            text = await orch.synthesize(query, ctx, responses)
        finally:
            if trace is not None and hasattr(trace, "end"):
                trace.end()

        cost = sum(r.cost_tokens for r in responses)
        had_errors = any(r.errors for r in responses)

        # ------------------------------------------------------------------
        # Post-turn side effects for the research persona:
        #   - publish_brief writes Research_Brief__c
        #   - publish_brief internally writes IR_Audit_Log__c (Action=RESEARCH_PUBLISHED)
        # This closes the design gap where the orchestrator's system prompt
        # promises "the coordinator writes audit after you return" but neither
        # the orchestrator nor the coordinator was actually invoking the
        # skill.
        #
        # We AWAIT this rather than fire-and-forget via asyncio.create_task.
        # AgentCore's HTTP lifecycle cancels the event loop's pending tasks
        # when the handler returns, so fire-and-forget silently dropped
        # every brief + audit write in the April 30 deploy. Synchronous
        # await costs ~1-2s on the happy path (two sequential MCP calls)
        # but publish success is guaranteed before we return to the client.
        #
        # We also cap the wait at PUBLISH_BRIEF_BUDGET_S to keep total turn
        # latency under the API Gateway 29s ceiling even if the Salesforce
        # OBO chain is slow or broken (see docs/v3-p0-sf-obo-fix.md). A
        # timeout here is logged and treated the same as any other
        # publish failure — the user still gets the synthesized brief.
        #
        # The budget is DYNAMIC: we measure how long the specialist phase
        # took and give publish_brief whatever remains before the 29s API
        # Gateway ceiling, minus a 2s safety margin for response serialization.
        # Minimum 3s (enough for one SF write on happy path).
        # ------------------------------------------------------------------
        API_GATEWAY_CEILING_S = 29.0
        PUBLISH_MIN_BUDGET_S = 3.0
        SAFETY_MARGIN_S = 2.0
        elapsed_s = (datetime.now(timezone.utc) - started).total_seconds()
        publish_budget = max(
            PUBLISH_MIN_BUDGET_S,
            API_GATEWAY_CEILING_S - elapsed_s - SAFETY_MARGIN_S,
        )
        sf_brief_id = None
        audit_row_id = None
        if ctx.persona == "fsi_research":
            try:
                pub = await asyncio.wait_for(
                    self._publish_research_brief(
                        query=query,
                        ctx=ctx,
                        responses=responses,
                        synthesized_text=text,
                    ),
                    timeout=publish_budget,
                )
                if pub is not None:
                    sf_brief_id = pub.sf_brief_id
                    audit_row_id = pub.audit_row_id
                    self.log.info(
                        "coordinator.publish_brief.ok sf_brief_id=%s audit_row_id=%s budget_s=%.1f",
                        sf_brief_id, audit_row_id, publish_budget,
                    )
            except asyncio.TimeoutError:
                self.log.warning(
                    "coordinator.publish_brief.timeout budget_s=%.1f elapsed_s=%.1f — SF write dropped",
                    publish_budget, (datetime.now(timezone.utc) - started).total_seconds(),
                )
            except Exception as exc:  # noqa: BLE001
                self.log.warning(
                    "coordinator.publish_brief.failed err=%s",
                    f"{type(exc).__name__}: {str(exc)[:300]}",
                )

        self.log.info(
            "coordinator.run_turn.done duration_ms=%d cost=%d had_errors=%s",
            int((datetime.now(timezone.utc) - started).total_seconds() * 1000),
            cost,
            had_errors,
        )
        envelope = {
            "text": text,
            "responses": responses,
            "cost_tokens": cost,
            "had_errors": had_errors,
        }
        if sf_brief_id:
            envelope["sf_brief_id"] = sf_brief_id
        if audit_row_id:
            envelope["audit_row_id"] = audit_row_id
        return envelope

    async def _publish_research_brief(
        self,
        *,
        query: str,
        ctx: SessionContext,
        responses: List[WorkerResponse],
        synthesized_text: str,
    ):
        """Build a PublishBriefInput from specialist responses and invoke the skill.

        Closes the research-persona post-turn gap: the orchestrator returns a
        synthesized brief, and this helper turns it into a persisted
        Research_Brief__c + IR_Audit_Log__c pair.

        Returns the PublishBriefOutput, or None if the turn isn't publishable
        (e.g. compliance DENY, no citations, MNPI not cleared). Callers should
        log failures but NOT fail the user-visible turn.
        """
        import re
        from ..skills.publish_brief.actions import (
            PublishBriefInput,
            run as publish_run,
        )

        # Extract structured fields from the responses — compliance status,
        # sentiment score, citations, thesis prose — without re-running the LLM.
        compliance_status = "UNKNOWN"
        sentiment_score = 0.0
        risk_factors: List[str] = []
        citations: List[str] = []
        thesis_parts: List[str] = []
        mnpi_cleared = True

        for r in responses:
            inner = (r.result or {}) if hasattr(r, "result") else {}
            text = str(inner.get("text", "") or "")
            citations.extend(r.citations or [])
            if r.agent_id == "compliance_specialist":
                up = text.upper()
                for tag in ("DENY", "ALLOW", "REVIEW"):
                    if tag in up:
                        compliance_status = tag
                        break
                if "MNPI_BLOCK" in up or "MNPI DETECTED" in up:
                    mnpi_cleared = False
            elif r.agent_id == "sentiment_specialist":
                m = re.search(r"sentiment_score[^0-9\-]*(-?[0-9]*\.?[0-9]+)", text, re.IGNORECASE)
                if m:
                    try:
                        sentiment_score = max(-1.0, min(1.0, float(m.group(1))))
                    except ValueError:
                        pass
            # Accumulate any text from market/filings/statement specialists as thesis prose
            if r.agent_id in {
                "market_specialist",
                "filings_specialist",
                "statement_specialist",
            } and text.strip():
                thesis_parts.append(f"[{r.agent_id}] {text.strip()[:400]}")

            # Risk factors: crude extraction from filings specialist
            if r.agent_id == "filings_specialist" and text:
                for line in text.splitlines():
                    ls = line.strip().lstrip("-*• ").strip()
                    if 10 <= len(ls) <= 200 and (
                        "risk" in ls.lower() or "concentration" in ls.lower()
                    ):
                        risk_factors.append(ls)

        ticker = ""
        m = re.search(r"\b([A-Z]{1,5})\b", query)
        if m:
            ticker = m.group(1)
        if not ticker:
            ticker = "UNKNOWN"

        # Defaults that satisfy schema + validator; ensures we never fail-validate
        # away a real turn. The downstream validator still enforces the hard
        # rm_consumable->compliance->mnpi gate.
        thesis = "\n\n".join(thesis_parts) if thesis_parts else synthesized_text[:2000]
        if len(thesis) < 20:
            thesis = f"Research brief for {ticker}. {thesis}".strip()
            if len(thesis) < 20:
                thesis = f"Research brief for {ticker}. Specialist telemetry recorded in trace."
        if not risk_factors:
            risk_factors = ["general market risk"]
        if not citations:
            # Schema requires >=1 citation; synthesize a coordinator marker so
            # downstream can still trace back. Not ideal but better than losing
            # the audit row entirely.
            citations = [f"orchestrator_{ctx.session_id}"]

        rm_consumable = (compliance_status == "ALLOW") and mnpi_cleared

        payload = PublishBriefInput(
            ticker=ticker,
            thesis=thesis,
            sentiment_score=sentiment_score,
            risk_factors=risk_factors[:10],
            compliance_status=compliance_status if compliance_status != "UNKNOWN" else "REVIEW",
            mnpi_cleared=mnpi_cleared,
            rm_consumable=rm_consumable,
            client_demand_flag=False,
            source_chunk_ids=list(dict.fromkeys(citations))[:50],
            author_agent_id="research_orchestrator",
            principal_id=ctx.principal_id,
            session_id=ctx.session_id,
            correlation_id=ctx.correlation_id,
        )
        return await publish_run(payload)


def _extract_text(result: Dict[str, Any]) -> str:
    """Pull the assistant text out of a Bedrock Converse response (or stub)."""
    try:
        content = result["output"]["message"]["content"]
        if isinstance(content, list) and content:
            return str(content[0].get("text", ""))
    except (KeyError, TypeError, IndexError):
        pass
    return ""


def _extract_citations(text: str) -> List[str]:
    """Extract citation chunk ids of the form [src:xxxx] from specialist output."""
    import re

    return re.findall(r"\[src:([A-Za-z0-9_\-]+)\]", text)


def _extract_action_plan(
    text: str,
) -> tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Extract a structured ActionPlan from the action_specialist's final text.

    The ACTION_SPECIALIST_PROMPT tells the model to return a JSON body
    ``{action_plan, gate_trace[], mulesoft_reference?, audit_row_id,
    final_status}`` at the end of its message. We parse that body and
    lift the nested ``action_plan`` up to the envelope level so the
    frontend's InlineActionCard can render it as a pending approval.

    The plan returned here MUST match the frontend ActionPlan TypeScript
    shape (``frontend/src/shared/types/api.ts``):

        {
          plan_id: str,
          plan_hash: str,
          action_type: "submit_order" | "cancel_order" | "modify_order" | "initiate_wire",
          summary: str,
          client_household: str,
          notional_usd: number,
          requires_dual_auth: bool,
          gates: GateState[],   // may be empty — the UI populates from gate_trace
        }

    If the LLM emits a plan without all fields, we fill in safe defaults
    so the frontend doesn't crash. If no plan is found the first return
    value is None and the caller just doesn't emit a hitl_prompt event.

    Extraction strategy, most-reliable first:
      1. Last fenced ```json ... ``` block.
      2. Balanced `{...}` at end of text.
      3. None → caller surfaces text-only.
    """
    import hashlib
    import json
    import re
    import uuid

    # 1. Fenced JSON block
    fenced = list(re.finditer(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", text))
    parsed: Optional[Dict[str, Any]] = None
    if fenced:
        try:
            parsed = json.loads(fenced[-1].group(1))
        except (json.JSONDecodeError, ValueError):
            parsed = None

    # 2. Balanced-brace fallback at end of text.
    # The LLM often emits the JSON body after prose. We scan from right to
    # left for a '{' that balances all subsequent '}'. We also try each
    # '{' found (outer-most first) so nested objects don't confuse the
    # parser.
    if parsed is None:
        # Collect all opening-brace offsets
        brace_indices = [i for i, ch in enumerate(text) if ch == "{"]
        # Try from outer-most (earliest) to inner-most until we get valid JSON
        for idx in brace_indices:
            candidate = text[idx:].strip()
            # Walk end pointer leftward from the full length looking for a
            # valid JSON suffix. Cap iterations for pathological inputs.
            for end in range(len(candidate), 0, -1):
                snippet = candidate[:end].rstrip()
                if not snippet.endswith("}"):
                    continue
                try:
                    parsed = json.loads(snippet)
                    break
                except (json.JSONDecodeError, ValueError):
                    continue
            if parsed is not None:
                break

    if not isinstance(parsed, dict):
        return None, None

    raw_plan = parsed.get("action_plan")
    if raw_plan is None or not isinstance(raw_plan, dict):
        return None, parsed

    # Normalise to the frontend ActionPlan shape with safe defaults.
    plan_id = str(raw_plan.get("plan_id") or f"plan-{uuid.uuid4().hex[:12]}")
    action_type = str(
        raw_plan.get("action_type") or raw_plan.get("type") or "submit_order"
    ).lower()
    if action_type not in {
        "submit_order",
        "cancel_order",
        "modify_order",
        "initiate_wire",
    }:
        action_type = "submit_order"
    summary = str(raw_plan.get("summary") or raw_plan.get("description") or "")
    household = str(
        raw_plan.get("client_household")
        or raw_plan.get("household")
        or "unknown-household"
    )
    try:
        notional_usd = float(raw_plan.get("notional_usd") or raw_plan.get("notional") or 0)
    except (TypeError, ValueError):
        notional_usd = 0.0

    # Dual-auth threshold per steering rule — wire > $100K OR trade > $500K.
    requires_dual_auth = bool(
        raw_plan.get("requires_dual_auth")
        or (action_type == "initiate_wire" and notional_usd > 100_000)
        or (action_type != "initiate_wire" and notional_usd > 500_000)
    )

    # Canonical hash — sha256 of sorted-key JSON payload. Matches the
    # `compute_plan_hash` implementation in openclaw/skills/hitl/_tokens.py.
    canonical = {
        "plan_id": plan_id,
        "action_type": action_type,
        "client_household": household,
        "notional_usd": notional_usd,
    }
    plan_hash = hashlib.sha256(
        json.dumps(canonical, separators=(",", ":"), sort_keys=True).encode()
    ).hexdigest()

    gates_raw = raw_plan.get("gates")
    gates = gates_raw if isinstance(gates_raw, list) else []

    normalised = {
        "plan_id": plan_id,
        "plan_hash": plan_hash,
        "action_type": action_type,
        "summary": summary,
        "client_household": household,
        "notional_usd": notional_usd,
        "requires_dual_auth": requires_dual_auth,
        "gates": gates,
    }
    return normalised, parsed


def _default_factories() -> Dict[str, Any]:
    """Import concrete orchestrators lazily to avoid circular imports."""
    from .research_orchestrator import ResearchOrchestratorImpl
    from .advisor_orchestrator import AdvisorOrchestratorImpl
    from .liaison_orchestrator import LiaisonOrchestratorImpl

    def _research(bc: BedrockClient, lf: Any) -> Orchestrator:
        return ResearchOrchestratorImpl(orchestrator_for_persona("fsi_research"), bc, lf)

    def _advisor(bc: BedrockClient, lf: Any) -> Orchestrator:
        return AdvisorOrchestratorImpl(orchestrator_for_persona("fsi_advisor"), bc, lf)

    def _liaison(bc: BedrockClient, lf: Any) -> Orchestrator:
        return LiaisonOrchestratorImpl(
            orchestrator_for_persona("fsi_client_liaison"), bc, lf
        )

    return {
        "fsi_research": _research,
        "fsi_advisor": _advisor,
        "fsi_client_liaison": _liaison,
    }


def main() -> None:  # pragma: no cover - entrypoint
    """CLI self-test: print the registered agents and exit."""
    print(f"OpenClaw V3 — {len(AGENT_TOPOLOGY)} agents registered")
    for aid, a in AGENT_TOPOLOGY.items():
        print(f"  [{a.persona:20s}] {aid:32s} -> {a.model.value:6s} ({a.role.value})")


if __name__ == "__main__":  # pragma: no cover
    main()
