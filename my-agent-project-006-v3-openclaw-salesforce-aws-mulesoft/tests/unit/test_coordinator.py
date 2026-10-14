"""Coordinator + base Orchestrator tests using StubBedrockClient."""

from __future__ import annotations

import asyncio
from typing import Any, Dict, List

import pytest

from openclaw.orchestration.coordinator import (
    BedrockConverseClient,
    Orchestrator,
    PersonaCoordinator,
    resolve_model_id,
)
from openclaw.orchestration.messages import (
    OrchestratorDispatch,
    SessionContext,
    WorkerResponse,
)
from openclaw.orchestration.topology import ModelTier, orchestrator_for_persona
from openclaw.orchestration._stubs import StubBedrockClient, StubLangfuseClient


pytestmark = pytest.mark.asyncio


def make_session(persona: str = "fsi_research", turn: int = 1) -> SessionContext:
    return SessionContext(
        session_id="sess_test_001",
        principal_id="user_sarah",
        persona=persona,
        correlation_id="corr_001",
        turn_number=turn,
    )


async def test_resolve_model_id_reads_env() -> None:
    assert resolve_model_id(ModelTier.SONNET) == "anthropic.stub-sonnet-v1"
    assert resolve_model_id(ModelTier.HAIKU) == "anthropic.stub-haiku-v1"


async def test_coordinator_routes_research() -> None:
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    ctx = make_session("fsi_research")
    result = await pc.run_turn("Research NVDA ahead of earnings", ctx)
    assert "text" in result
    assert result["had_errors"] is False
    assert len(result["responses"]) >= 3


async def test_coordinator_routes_advisor() -> None:
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    ctx = make_session("fsi_advisor")
    result = await pc.run_turn(
        "Which of my clients have NVDA exposure above 5%?", ctx
    )
    assert result["responses"]


async def test_coordinator_routes_liaison_escalation() -> None:
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    ctx = make_session("fsi_client_liaison")
    result = await pc.run_turn("Should I be worried about NVDA?", ctx)
    text = result["text"].lower()
    assert "rm" in text or "escalat" in text or "reach out" in text


async def test_coordinator_routes_liaison_faq() -> None:
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    ctx = make_session("fsi_client_liaison")
    result = await pc.run_turn("What are market hours?", ctx)
    assert "RM" in result["text"] or "informational" in result["text"]


async def test_coordinator_missing_factory_raises() -> None:
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    pc._factories.pop("fsi_research", None)
    ctx = make_session("fsi_research")
    with pytest.raises(ValueError, match="no orchestrator factory"):
        await pc.run_turn("Research NVDA", ctx)


class _MiniOrchestrator(Orchestrator):
    """Minimal orchestrator used to exercise the fanout machinery."""

    async def plan(
        self, query: str, ctx: SessionContext
    ) -> List[OrchestratorDispatch]:
        return [
            OrchestratorDispatch(
                target_agent_id="market_specialist",
                task="get NVDA quote",
                context_subset={"ticker": "NVDA"},
                timeout_s=5.0,
            ),
            OrchestratorDispatch(
                target_agent_id="sentiment_specialist",
                task="score NVDA sentiment",
                context_subset={"ticker": "NVDA"},
                timeout_s=5.0,
            ),
        ]

    async def synthesize(
        self,
        query: str,
        ctx: SessionContext,
        responses: List[WorkerResponse],
    ) -> str:
        return f"synthesized {len(responses)} responses"


async def test_parallel_fanout_runs() -> None:
    orch = _MiniOrchestrator(
        definition=orchestrator_for_persona("fsi_research"),
        bedrock=StubBedrockClient(),
    )
    ctx = make_session()
    dispatches = await orch.plan("query", ctx)
    responses = await orch.fanout(dispatches, ctx, serial=False)
    assert len(responses) == 2
    assert all(r.errors == [] for r in responses)


async def test_timeout_wraps_as_agent_error() -> None:
    class _SlowBedrock(StubBedrockClient):
        async def converse(self, **kwargs: Any) -> Dict[str, Any]:
            await asyncio.sleep(1.0)
            return await super().converse(**kwargs)

    orch = _MiniOrchestrator(
        definition=orchestrator_for_persona("fsi_research"),
        bedrock=_SlowBedrock(),
    )
    dispatch = OrchestratorDispatch(
        target_agent_id="market_specialist",
        task="slow",
        timeout_s=0.05,
    )
    ctx = make_session()
    responses = await orch.fanout([dispatch], ctx, serial=False)
    assert len(responses) == 1
    assert responses[0].errors
    assert responses[0].errors[0].error_type.value == "timeout"


async def test_unknown_agent_id_becomes_validation_error() -> None:
    orch = _MiniOrchestrator(
        definition=orchestrator_for_persona("fsi_research"),
        bedrock=StubBedrockClient(),
    )
    ctx = make_session()
    dispatch = OrchestratorDispatch(target_agent_id="does_not_exist", task="nope")
    responses = await orch.fanout([dispatch], ctx, serial=False)
    assert len(responses) == 1
    assert not responses[0].succeeded
    assert responses[0].errors[0].error_type.value == "validation"
    assert responses[0].errors[0].recoverable is False


async def test_langfuse_span_captures_children() -> None:
    lf = StubLangfuseClient()
    pc = PersonaCoordinator(bedrock=StubBedrockClient(), langfuse=lf)
    ctx = make_session("fsi_research")
    await pc.run_turn("Research NVDA", ctx)
    assert lf.spans
    trace = lf.spans[0]
    assert trace.ended
    child_names = [c.name for c in trace.children]
    assert any("market_specialist" in n for n in child_names)


async def test_bedrock_converse_client_without_boto3_raises_on_use() -> None:
    c = BedrockConverseClient()
    if not c._available:
        with pytest.raises(RuntimeError, match="boto3 not installed"):
            await c.converse(model_id="x", system_prompt="y", messages=[])


async def test_action_write_triggers_serial_fanout(monkeypatch: pytest.MonkeyPatch) -> None:
    """Advisor action_write dispatch should be forced serial in the coordinator."""
    from openclaw.orchestration import coordinator as c

    recorded: Dict[str, bool] = {"serial": False}
    real_fanout = c.Orchestrator.fanout

    async def spy(self, dispatches, ctx, parent_span=None, *, serial=False):
        recorded["serial"] = serial
        return await real_fanout(self, dispatches, ctx, parent_span, serial=serial)

    monkeypatch.setattr(c.Orchestrator, "fanout", spy)
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    ctx = make_session("fsi_advisor")
    await pc.run_turn("Sell 100 NVDA from Patel household", ctx)
    assert recorded["serial"] is True



# ---------------------------------------------------------------------------
# Wave 2: P1.4 + P1.5 + P2.12 tests
# ---------------------------------------------------------------------------

from openclaw.orchestration.coordinator import (  # noqa: E402
    GuardrailInterventionError,
    build_langfuse_client,
    scrub_before_write,
)


def test_scrub_before_write_mnpi_pii_and_tokens():
    """P1.4: scrubbers applied recursively before Langfuse write."""
    payload = {
        "ticker": "NVDA",
        "shares_held": 150,
        "market_value": 24322.50,
        "ssn": "123-45-6789",
        "approval_token": "raw-hmac-please-hide-me",
        "nested": {
            "wire_amount": 150000.0,
            "cost_basis": 10000,
            "phone_number": "+1-555-0100",
            "bearer_token": "eyJhbGciOi...",
        },
        "safe_field": "visible",
    }
    out = scrub_before_write(payload)
    assert out["ticker"] == "NVDA"
    assert out["safe_field"] == "visible"
    assert out["shares_held"] == "[REDACTED:mnpi]"
    assert out["market_value"] == "[REDACTED:mnpi]"
    assert out["ssn"] == "[REDACTED:pii]"
    assert out["approval_token"] == "[REDACTED:raw_approval_tokens]"
    assert out["nested"]["wire_amount"] == "[REDACTED:mnpi]"
    assert out["nested"]["cost_basis"] == "[REDACTED:mnpi]"
    assert out["nested"]["phone_number"] == "[REDACTED:pii]"
    assert out["nested"]["bearer_token"] == "[REDACTED:raw_approval_tokens]"


def test_build_langfuse_client_stub_when_env_missing(monkeypatch):
    """Without LANGFUSE_* env vars, return StubLangfuseClient."""
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_SECRET_KEY", raising=False)
    monkeypatch.delenv("LANGFUSE_HOST", raising=False)
    client = build_langfuse_client()
    assert isinstance(client, StubLangfuseClient)


async def test_coordinator_emits_span_and_no_mnpi_leak(monkeypatch):
    """P1.4: a span is emitted via the coordinator's Langfuse client, and the
    payload does NOT contain raw MNPI (`$` or `shares`) after scrubbing.
    """
    monkeypatch.delenv("LANGFUSE_PUBLIC_KEY", raising=False)
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    assert isinstance(pc.langfuse, StubLangfuseClient)

    ctx = make_session("fsi_research")
    result = await pc.run_turn("Research NVDA", ctx)
    assert result["text"]
    assert len(pc.langfuse.spans) == 1
    joined = ""
    for span in pc.langfuse.spans:
        joined += str(span.metadata) + "|"
        for child in span.children:
            joined += str(child.metadata) + "|"
    assert "shares" not in joined.lower()
    assert "$" not in joined


async def test_coordinator_guardrail_error_becomes_safety(monkeypatch):
    """P1.5: guardrail intervention surfaces as AgentError(SAFETY, recoverable=False)
    without reaching the specialist downstream logic.
    """

    class _GuardrailTrippingClient:
        async def converse(self, **_kwargs: Any) -> Dict[str, Any]:
            raise GuardrailInterventionError("blocked")

    pc = PersonaCoordinator(
        bedrock=_GuardrailTrippingClient(),
        langfuse=StubLangfuseClient(),
    )
    ctx = make_session("fsi_research")
    result = await pc.run_turn("Tell me insider info about NVDA", ctx)
    errors = []
    for r in result["responses"]:
        errors.extend(r.errors)
    assert any(
        e.error_type.value == "safety" and e.recoverable is False for e in errors
    ), (
        "expected SAFETY non-recoverable error, got "
        f"{[(e.error_type, e.recoverable) for e in errors]}"
    )


def test_persona_coordinator_boot_time_model_id_audit_tolerant_in_dev(monkeypatch):
    """P2.12: missing model-id env vars are tolerated in dev (no AWS_REGION_BEDROCK)."""
    monkeypatch.delenv("AWS_REGION_BEDROCK", raising=False)
    monkeypatch.delenv("BEDROCK_SONNET_MODEL_ID", raising=False)
    monkeypatch.delenv("BEDROCK_HAIKU_MODEL_ID", raising=False)
    pc = PersonaCoordinator(bedrock=StubBedrockClient())
    assert pc is not None


def test_persona_coordinator_boot_time_model_id_raises_in_prod(monkeypatch):
    """P2.12: in production (AWS_REGION_BEDROCK set), missing model ids raise."""
    monkeypatch.setenv("AWS_REGION_BEDROCK", "us-east-1")
    monkeypatch.delenv("BEDROCK_SONNET_MODEL_ID", raising=False)
    monkeypatch.delenv("BEDROCK_HAIKU_MODEL_ID", raising=False)
    with pytest.raises(RuntimeError, match="BEDROCK_SONNET_MODEL_ID"):
        PersonaCoordinator(bedrock=StubBedrockClient())
