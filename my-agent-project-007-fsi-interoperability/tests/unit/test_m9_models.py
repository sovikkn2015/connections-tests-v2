"""
M9 Task 4 -- Pydantic v2 models.

AC1.2, AC1.9, AC3.3, AC5.7, AC9.1-9.6, AC11.1-11.6.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from m5_config_loader import Archetype, Runtime
from m9_intent_router import IntentCategory, RouterContext, RoutingDecision
from m9_intent_router.models import LlmClassification
from m9_intent_router.taxonomy import SelectedTarget


# -----------------------------------------------------------------------------
# RouterContext
# -----------------------------------------------------------------------------


def test_router_context_frozen(fixture_aid_advisor, fixture_router_context_factory):
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    with pytest.raises(Exception):
        ctx.trace_id = "mutated"  # type: ignore[misc]


def test_router_context_rejects_extra_fields(fixture_aid_advisor):
    with pytest.raises(ValidationError):
        RouterContext(
            trace_id="t",
            runtime=Runtime.managed_agents,
            archetype=Archetype.tier4_independent_ria,
            tenant_id="firm-hyp-fixture",
            identity=fixture_aid_advisor,
            extra_field="oops",  # type: ignore[call-arg]
        )


def test_router_context_rejects_empty_trace_id(fixture_aid_advisor):
    with pytest.raises(ValidationError):
        RouterContext(
            trace_id="",
            runtime=Runtime.managed_agents,
            archetype=Archetype.tier4_independent_ria,
            tenant_id="firm-hyp-fixture",
            identity=fixture_aid_advisor,
        )


def test_ac1_9_self_consistency_mismatch_rejected(fixture_aid_advisor):
    """identity.archetype must match RouterContext.archetype."""
    with pytest.raises(ValidationError) as exc_info:
        RouterContext(
            trace_id="t",
            runtime=Runtime.managed_agents,
            archetype=Archetype.tier1_investment_bank,  # mismatch!
            tenant_id="firm-hyp-fixture",
            identity=fixture_aid_advisor,
        )
    assert "archetype" in str(exc_info.value).lower()


def test_ac1_9_self_consistency_pass(fixture_aid_advisor):
    """Matching archetype succeeds."""
    ctx = RouterContext(
        trace_id="t",
        runtime=Runtime.managed_agents,
        archetype=Archetype.tier4_independent_ria,
        tenant_id="firm-hyp-fixture",
        identity=fixture_aid_advisor,
    )
    assert ctx.archetype.value == fixture_aid_advisor.archetype


# -----------------------------------------------------------------------------
# LlmClassification
# -----------------------------------------------------------------------------


def test_llm_classification_accepts_valid_confidence():
    c = LlmClassification(
        intent=IntentCategory.RESEARCH_MEETING_PREP,
        confidence=0.5,
        entities={},
        latency_ms=100,
        model="m",
        provider="fake",
    )
    assert c.confidence == 0.5


def test_llm_classification_rejects_inf():
    with pytest.raises(ValidationError):
        LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=float("inf"),
            entities={},
            latency_ms=0,
            model="m",
            provider="fake",
        )


def test_llm_classification_rejects_neg_inf():
    with pytest.raises(ValidationError):
        LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=float("-inf"),
            entities={},
            latency_ms=0,
            model="m",
            provider="fake",
        )


def test_llm_classification_rejects_nan():
    with pytest.raises(ValidationError):
        LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=float("nan"),
            entities={},
            latency_ms=0,
            model="m",
            provider="fake",
        )


def test_llm_classification_rejects_out_of_range():
    with pytest.raises(ValidationError):
        LlmClassification(
            intent=IntentCategory.RESEARCH_MEETING_PREP,
            confidence=1.5,
            entities={},
            latency_ms=0,
            model="m",
            provider="fake",
        )


# -----------------------------------------------------------------------------
# RoutingDecision.audit_payload
# -----------------------------------------------------------------------------


def _make_decision(**overrides) -> RoutingDecision:
    defaults = dict(
        trace_id="t1",
        utterance_sha256="a" * 64,
        intent=IntentCategory.RESEARCH_MEETING_PREP,
        confidence=0.97,
        entities={"ticker": "NVDA", "client_id": "003xx"},
        selected_target=SelectedTarget(
            kind="pipeline", name="m8.research_pipeline_1"
        ),
        fallback_used=False,
        llm_latency_ms=300,
        llm_model="anthropic.claude-3-5-haiku-20241022-v1:0",
        llm_provider="bedrock",
        reason_code=None,
        tenant_id="firm-hyp-fixture",
    )
    defaults.update(overrides)
    return RoutingDecision(**defaults)


def test_audit_payload_has_exactly_12_keys():
    d = _make_decision()
    payload = d.audit_payload()
    assert len(payload) == 12
    assert set(payload.keys()) == {
        "trace_id",
        "utterance_sha256",
        "intent",
        "confidence",
        "selected_target",
        "fallback_used",
        "llm_latency_ms",
        "llm_model",
        "llm_provider",
        "reason_code",
        "entities_present",
        "tenant_id",
    }


def test_audit_payload_entities_present_keys_only():
    """AC9.2 -- keys only, never values."""
    d = _make_decision()
    payload = d.audit_payload()
    assert payload["entities_present"] == ["client_id", "ticker"]
    assert "NVDA" not in str(payload["entities_present"])
    assert "003xx" not in str(payload["entities_present"])


def test_audit_payload_selected_target_is_dict():
    d = _make_decision()
    payload = d.audit_payload()
    assert payload["selected_target"] == {
        "kind": "pipeline",
        "name": "m8.research_pipeline_1",
    }


def test_audit_payload_tenant_id_present():
    """AC9.1 v0.2.0 -- tenant_id in audit payload."""
    d = _make_decision(tenant_id="firm-xyz")
    payload = d.audit_payload()
    assert payload["tenant_id"] == "firm-xyz"


def test_routing_decision_rejects_bad_sha_pattern():
    with pytest.raises(ValidationError):
        _make_decision(utterance_sha256="not-a-hash")


def test_routing_decision_rejects_unknown_reason_code():
    with pytest.raises(ValidationError):
        _make_decision(reason_code="made_up_code")


def test_routing_decision_accepts_none_reason_code():
    d = _make_decision(reason_code=None)
    assert d.reason_code is None


def test_routing_decision_accepts_valid_reason_code():
    d = _make_decision(reason_code="llm_assisted_plan")
    assert d.reason_code == "llm_assisted_plan"


def test_routing_decision_rejects_empty_tenant_id():
    with pytest.raises(ValidationError):
        _make_decision(tenant_id="")


def test_routing_decision_frozen():
    d = _make_decision()
    with pytest.raises(Exception):
        d.confidence = 0.5  # type: ignore[misc]
