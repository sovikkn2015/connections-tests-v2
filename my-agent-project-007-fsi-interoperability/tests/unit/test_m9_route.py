"""
M9 Task 8 -- route() dispatcher happy paths.

AC1.1-1.9, AC5.1-5.5, AC9.7.
"""

from __future__ import annotations

from m9_intent_router import IntentCategory, RoutingDecision, route
from m9_intent_router.models import LlmClassification


def _make_classification(intent, confidence, entities=None):
    return LlmClassification(
        intent=intent,
        confidence=confidence,
        entities=entities or {},
        latency_ms=50,
        model="fake",
        provider="fake",
    )


def test_happy_path_high_confidence(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    utter = "prep me for the meeting with 003xx0000012ABCAA2"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.RESEARCH_MEETING_PREP, 0.97)}
    )
    decision = route(
        utter,
        ctx,
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert isinstance(decision, RoutingDecision)
    assert decision.intent == IntentCategory.RESEARCH_MEETING_PREP
    assert decision.confidence == 0.97
    assert decision.reason_code is None
    assert decision.fallback_used is False
    assert decision.selected_target.name == "m8.research_pipeline_1"


def test_mnpi_short_circuit_no_llm_call(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    utter = "wire $50k to routing 021000021 account 1234567890"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory({})
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "mnpi_shape_suspected"
    assert decision.intent == IntentCategory.ESCALATE_TO_HUMAN
    assert decision.llm_latency_ms == 0
    assert decision.llm_provider == "n/a"


def test_invalid_length_empty_utterance(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory({})
    decision = route(
        "", ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "invalid_utterance_length"
    assert decision.intent == IntentCategory.UNSUPPORTED


def test_invalid_length_oversize_utterance(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory({})
    decision = route(
        "x" * 5000,
        ctx,
        _provider=provider,
        _config=fixture_intent_router_config,
    )
    assert decision.reason_code == "invalid_utterance_length"


def test_confidence_high_bucket_095(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """AC5.5 -- 0.95 is inclusive lower bound of high bucket."""
    utter = "prep me for meeting"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.RESEARCH_MEETING_PREP, 0.95)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code is None
    assert decision.intent == IntentCategory.RESEARCH_MEETING_PREP


def test_confidence_mid_bucket_080(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """AC5.5 -- 0.80 is inclusive lower bound of mid bucket."""
    utter = "find the client"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.CLIENT_DATA_LOOKUP, 0.80)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "llm_assisted_plan"


def test_confidence_low_bucket_escalates(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    utter = "vague"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.RESEARCH_MARKET_QUERY, 0.50)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "low_confidence"
    assert decision.intent == IntentCategory.ESCALATE_TO_HUMAN
    assert decision.confidence == 0.50


def test_unsupported_intent_stub(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    utter = "tell me a joke"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.UNSUPPORTED, 0.99)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "unsupported_intent_stub"
    assert decision.intent == IntentCategory.UNSUPPORTED


def test_input_immutability_ac1_6(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    import copy

    utter = "prep me for meeting"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    ctx_snapshot = copy.deepcopy(ctx.model_dump())
    utter_snapshot = utter
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.RESEARCH_MEETING_PREP, 0.98)}
    )
    route(utter, ctx, _provider=provider, _config=fixture_intent_router_config)
    assert ctx.model_dump() == ctx_snapshot
    assert utter == utter_snapshot


def test_audit_emitted_on_stdout(
    capsys,
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """AC9.7 -- one JSON line per route() call."""
    import json

    utter = "prep me for meeting"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make_classification(IntentCategory.RESEARCH_MEETING_PREP, 0.98)}
    )
    route(utter, ctx, _provider=provider, _config=fixture_intent_router_config)
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1
    payload = json.loads(out[0])
    assert payload["source"] == "m9"
    assert payload["intent"] == "research.meeting_prep"
    assert "meeting" not in payload["utterance_sha256"]
    assert isinstance(payload["entities_present"], list)
