"""
M9 Task 8 extension -- AID authority scope matrix (Fix 8).

AC5.8, AC12.9. Tests _check_authority_scope + end-to-end authority_denied.
"""

from __future__ import annotations

import pytest

from m9_intent_router import IntentCategory
from m9_intent_router.route import _check_authority_scope

_MATRIX = [
    ("research.meeting_prep", {"research.read"}, True),
    ("research.meeting_prep", {"client.read"}, False),
    ("research.meeting_prep", {"research.execute"}, True),
    ("client.plan_summary", {"plan.read", "client.read"}, True),
    ("client.plan_summary", {"client.read"}, False),
    ("client.data_lookup", {"client.read"}, True),
    ("client.goal_tracking", {"client.read", "goal.read"}, True),
    ("client.goal_tracking", {"client.read"}, False),
    ("trade.inquiry", {"trade.read"}, True),
    ("trade.inquiry", set(), False),
    ("compliance.question", set(), True),
    ("escalate_to_human", set(), True),
    ("unsupported", set(), True),
]


@pytest.mark.parametrize("intent_val,scopes,expected", _MATRIX)
def test_authority_matrix_enforced(intent_val, scopes, expected):
    result = _check_authority_scope(IntentCategory(intent_val), scopes, set())
    assert result is expected


def test_wildcard_scope_grants_everything_except_excludes():
    """authority_scope=['*'] + excludes allows research, denies trade.execute."""
    allowed = _check_authority_scope(
        IntentCategory.TRADE_INQUIRY, {"*"}, {"trade.execute"}
    )
    # trade.inquiry needs trade.read, * covers it; trade.execute exclusion
    # does not touch trade.read.
    assert allowed is True


def test_wildcard_scope_denied_when_required_in_excludes():
    allowed = _check_authority_scope(
        IntentCategory.CLIENT_DATA_LOOKUP, {"*"}, {"client.read"}
    )
    assert allowed is False


def test_route_authority_denied(
    fixture_aid_agent,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    """Agent lacks plan.read -> CLIENT_PLAN_SUMMARY classification denied."""
    from m9_intent_router import route
    from m9_intent_router.models import LlmClassification

    utter = "summarize the plan for 003xx0000099ZZZAAA"
    ctx = fixture_router_context_factory(fixture_aid_agent)
    classification = LlmClassification(
        intent=IntentCategory.CLIENT_PLAN_SUMMARY,
        confidence=0.94,
        entities={},
        latency_ms=50,
        model="fake",
        provider="fake",
    )
    provider = fixture_fake_llm_factory({utter: classification})
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code == "aid_authority_denied"
    assert decision.intent == IntentCategory.ESCALATE_TO_HUMAN
    assert decision.confidence == 0.94


def test_route_authority_allowed_for_advisor(
    fixture_aid_advisor,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    from m9_intent_router import route
    from m9_intent_router.models import LlmClassification

    utter = "summarize plan"
    ctx = fixture_router_context_factory(fixture_aid_advisor)
    classification = LlmClassification(
        intent=IntentCategory.CLIENT_PLAN_SUMMARY,
        confidence=0.98,
        entities={},
        latency_ms=50,
        model="fake",
        provider="fake",
    )
    provider = fixture_fake_llm_factory({utter: classification})
    decision = route(
        utter, ctx, _provider=provider, _config=fixture_intent_router_config
    )
    assert decision.reason_code is None
    assert decision.intent == IntentCategory.CLIENT_PLAN_SUMMARY
