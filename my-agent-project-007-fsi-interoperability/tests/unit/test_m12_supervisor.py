"""
M12 Supervisor -- unit tests.

Covers:
- happy path (pipeline intent) -> SupervisorResult(status="completed")
- tool intent -> tool_target populated, no M8 call
- escalate intent -> escalation_target populated
- invalid AID -> status="failed" + reason_code="m12_invalid_aid"
- M9 failure (raising provider) -> m12_routing_failed
- M8 failure (raising run) -> m12_dispatch_failed
- SupervisorResult is frozen and extra=forbid
- build_router_context / build_pipeline_state key coverage
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest
from pydantic import ValidationError

from m9_intent_router import IntentCategory
from m9_intent_router.models import LlmClassification, RoutingDecision
from m9_intent_router.taxonomy import SelectedTarget

from m12_supervisor import (
    SCHEMA_VERSION,
    SupervisorResult,
    VALID_REASON_CODES,
    build_pipeline_state,
    build_router_context,
    dispatch,
)


# -----------------------------------------------------------------------------
# Schema + public-API shape checks.
# -----------------------------------------------------------------------------


def test_schema_version_is_v0_2_0():
    """v0.2.0 adds Execution + Onboarding specialist registration."""
    assert SCHEMA_VERSION == "0.2.0"


def test_valid_reason_codes_frozen_and_scoped():
    assert isinstance(VALID_REASON_CODES, frozenset)
    assert VALID_REASON_CODES == frozenset({
        "m12_invalid_aid",
        "m12_invalid_pipeline_result",
        "m12_routing_failed",
        "m12_dispatch_failed",
    })


def test_supervisor_result_frozen():
    r = SupervisorResult(
        status="completed",
        trace_id="t-1",
        wall_clock_seconds=0.1,
        tenant_id="firm-1",
    )
    with pytest.raises((ValidationError, TypeError)):
        r.status = "failed"  # type: ignore[misc]


def test_supervisor_result_extra_forbidden():
    with pytest.raises(ValidationError):
        SupervisorResult(
            status="completed",
            trace_id="t-1",
            wall_clock_seconds=0.1,
            tenant_id="firm-1",
            bogus_field="nope",  # type: ignore[call-arg]
        )


def test_supervisor_result_rejects_unknown_reason_code():
    with pytest.raises(ValidationError):
        SupervisorResult(
            status="failed",
            trace_id="t-1",
            wall_clock_seconds=0.1,
            tenant_id="firm-1",
            reason_code="not_a_real_code",
        )


# -----------------------------------------------------------------------------
# Context builder tests.
# -----------------------------------------------------------------------------


def test_build_router_context_maps_aid_fields(fixture_aid_advisor):
    ctx = build_router_context(fixture_aid_advisor, "trace-abc")
    assert ctx.trace_id == "trace-abc"
    assert ctx.tenant_id == fixture_aid_advisor.firm_id
    assert ctx.identity is fixture_aid_advisor
    assert ctx.archetype.value == fixture_aid_advisor.archetype


def test_build_pipeline_state_populates_required_keys(
    fixture_aid_advisor,
):
    from m8_pipeline_engine.graph import _REQUIRED_ENTRY_KEYS

    decision = _routing_decision(
        kind="pipeline",
        name="m8.research_pipeline_1",
        intent=IntentCategory.RESEARCH_MEETING_PREP,
        tenant_id=fixture_aid_advisor.firm_id,
    )
    state = build_pipeline_state(
        fixture_aid_advisor,
        "trace-xyz",
        "prep me for tomorrow's meeting",
        decision,
    )
    # Every M8-required key present.
    assert _REQUIRED_ENTRY_KEYS.issubset(state.keys())
    # thread_id shape matches M8's regex.
    import re

    assert re.match(r"^[a-z0-9][a-z0-9\-]{7,63}$", state["thread_id"])
    assert state["tenant_id"] == fixture_aid_advisor.firm_id
    assert state["runtime"] == "managed_agents"


# -----------------------------------------------------------------------------
# dispatch() behavioural tests.
# -----------------------------------------------------------------------------


def _routing_decision(
    *,
    kind: str,
    name: str,
    intent: IntentCategory,
    tenant_id: str = "firm-hyp-fixture",
) -> RoutingDecision:
    return RoutingDecision(
        trace_id="t-" + uuid.uuid4().hex[:8],
        utterance_sha256="a" * 64,
        intent=intent,
        confidence=0.97,
        entities={},
        selected_target=SelectedTarget(kind=kind, name=name),
        fallback_used=False,
        llm_latency_ms=10,
        llm_model="fake",
        llm_provider="fake",
        reason_code=None,
        tenant_id=tenant_id,
    )


def test_dispatch_pipeline_happy_path(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    utter = "prep me for tomorrow's meeting"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=0.97,
            entities={},
            latency_ms=200,
            model="fake",
            provider="fake",
        )
    })
    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-pipe-1",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert isinstance(result, SupervisorResult)
    assert result.status == "completed"
    assert result.routing_decision is not None
    assert result.routing_decision.intent == IntentCategory.RESEARCH_MEETING_PREP
    assert result.pipeline_result is not None
    assert result.pipeline_result.status == "completed"
    assert result.tool_target is None
    assert result.escalation_target is None
    assert result.trace_id == "trace-pipe-1"


def test_dispatch_tool_intent_returns_tool_target(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    utter = "look up client Henderson"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.CLIENT_DATA_LOOKUP,
            confidence=0.97,
            entities={},
            latency_ms=120,
            model="fake",
            provider="fake",
        )
    })
    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-tool-1",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.status == "completed"
    assert result.tool_target == "sfdc.fetch_client"
    assert result.pipeline_result is None
    assert result.escalation_target is None


def test_dispatch_escalate_intent_returns_escalation_target(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    utter = "is NVDA on the restricted list"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.COMPLIANCE_QUESTION,
            confidence=0.97,
            entities={},
            latency_ms=80,
            model="fake",
            provider="fake",
        )
    })
    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-esc-1",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.status == "escalated"
    assert result.escalation_target == "compliance_specialist"
    assert result.pipeline_result is None
    assert result.tool_target is None


def test_dispatch_invalid_aid_returns_failed(
    fixture_intent_router_config,
):
    result = dispatch(
        "hello",
        aid_claims=None,  # not an AidClaims
        trace_id="trace-bad-aid",
        _provider=None,
        _config=fixture_intent_router_config,
    )
    assert result.status == "failed"
    assert result.reason_code == "m12_invalid_aid"
    assert result.routing_decision is None


def test_dispatch_invalid_aid_dict_also_rejected(
    fixture_intent_router_config,
):
    result = dispatch(
        "hello",
        aid_claims={"sub": "sneaky"},  # plain dict
        trace_id="trace-bad-aid-2",
        _provider=None,
        _config=fixture_intent_router_config,
    )
    assert result.status == "failed"
    assert result.reason_code == "m12_invalid_aid"


def test_dispatch_m9_unexpected_exception_is_caught(
    fixture_aid_advisor,
    fixture_intent_router_config,
    monkeypatch,
):
    """If M9 route() itself raised, M12 catches it and returns
    m12_routing_failed. route() normally never raises, so we force it by
    monkeypatching the route() symbol M12 imported.
    """
    import importlib

    m12_disp = importlib.import_module("m12_supervisor.dispatch")

    def _boom(*a, **kw):
        raise RuntimeError("simulated route() crash")

    monkeypatch.setattr(m12_disp, "route", _boom)

    result = dispatch(
        "hello",
        fixture_aid_advisor,
        "trace-crash-1",
        _provider=None,
        _config=fixture_intent_router_config,
    )
    assert result.status == "failed"
    assert result.reason_code == "m12_routing_failed"
    assert result.routing_decision is None


def test_dispatch_m8_failure_mapped_to_m12_dispatch_failed(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
    monkeypatch,
):
    """If M8 run() raises, M12 returns m12_dispatch_failed."""
    utter = "research my portfolio"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.RESEARCH_PORTFOLIO_REVIEW,
            confidence=0.97,
            entities={},
            latency_ms=200,
            model="fake",
            provider="fake",
        )
    })
    import importlib

    m12_disp = importlib.import_module("m12_supervisor.dispatch")

    def _boom(*a, **kw):
        raise RuntimeError("simulated M8 crash")

    monkeypatch.setattr(m12_disp, "run", _boom)

    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-m8-fail",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.status == "failed"
    assert result.reason_code == "m12_dispatch_failed"
    assert result.routing_decision is not None
    assert result.pipeline_result is None


def test_dispatch_m8_wrong_shape_mapped_to_invalid_pipeline_result(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
    monkeypatch,
):
    utter = "research NVDA"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.RESEARCH_MARKET_QUERY,
            confidence=0.97,
            entities={},
            latency_ms=200,
            model="fake",
            provider="fake",
        )
    })
    import importlib

    m12_disp = importlib.import_module("m12_supervisor.dispatch")

    def _wrong_shape(*a, **kw):
        return {"not": "a pipeline result"}

    monkeypatch.setattr(m12_disp, "run", _wrong_shape)

    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-shape",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.status == "failed"
    assert result.reason_code == "m12_invalid_pipeline_result"
    assert result.routing_decision is not None


def test_dispatch_wall_clock_is_populated(
    fixture_aid_advisor,
    fixture_fake_llm_factory,
    fixture_intent_router_config,
):
    utter = "look up client"
    provider = fixture_fake_llm_factory({
        utter: LlmClassification(
            intent=IntentCategory.CLIENT_DATA_LOOKUP,
            confidence=0.97,
            entities={},
            latency_ms=10,
            model="fake",
            provider="fake",
        )
    })
    result = dispatch(
        utter,
        fixture_aid_advisor,
        "trace-wc",
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert result.wall_clock_seconds >= 0.0
