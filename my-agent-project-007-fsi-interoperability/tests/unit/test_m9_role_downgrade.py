"""
M9 Task 8 -- Role=agent + TRADE_INQUIRY downgrade (AC5.8, Fix 8).

Agent role with high-confidence TRADE_INQUIRY classification gets downgraded
to the mid-confidence bucket (reason_code="llm_assisted_plan") for extra
scrutiny. Advisor role is unaffected.
"""

from __future__ import annotations

from m9_intent_router import IntentCategory, route
from m9_intent_router.models import LlmClassification


def _make(intent, confidence):
    return LlmClassification(
        intent=intent,
        confidence=confidence,
        entities={},
        latency_ms=50,
        model="fake",
        provider="fake",
    )


def test_agent_trade_inquiry_high_confidence_downgrades_to_mid(
    fixture_aid_agent,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """AC5.8 -- agent + TRADE_INQUIRY @ 0.98 -> reason_code=llm_assisted_plan."""
    utter = "what's the current ask on NVDA"
    ctx = fixture_router_context_factory(fixture_aid_agent)
    provider = fixture_fake_llm_factory(
        {utter: _make(IntentCategory.TRADE_INQUIRY, 0.98)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.confidence == 0.98
    assert decision.reason_code == "llm_assisted_plan"
    assert decision.intent == IntentCategory.TRADE_INQUIRY


def test_agent_trade_inquiry_low_confidence_still_escalates(
    fixture_aid_agent,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """AC5.8 negative path: 0.70 below mid, still escalates."""
    utter = "buy nvda"
    ctx = fixture_router_context_factory(fixture_aid_agent)
    provider = fixture_fake_llm_factory(
        {utter: _make(IntentCategory.TRADE_INQUIRY, 0.70)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "low_confidence"
    assert decision.intent == IntentCategory.ESCALATE_TO_HUMAN


def test_advisor_trade_inquiry_high_confidence_no_downgrade(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """AC5.8 negative -- advisor unaffected."""
    utter = "what's the ask on NVDA"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    provider = fixture_fake_llm_factory(
        {utter: _make(IntentCategory.TRADE_INQUIRY, 0.98)}
    )
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code is None
    assert decision.intent == IntentCategory.TRADE_INQUIRY
