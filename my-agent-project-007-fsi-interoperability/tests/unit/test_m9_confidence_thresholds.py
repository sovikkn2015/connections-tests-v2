"""
M9 Task 13 -- parametrized confidence-threshold table.

Per Confidence Threshold Table. Covers AC5.1-5.8, AC7.3-7.7.
"""

from __future__ import annotations

import pytest

from m9_intent_router import IntentCategory, route
from m9_intent_router.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m9_intent_router.models import LlmClassification


def _lc(intent_value, confidence):
    return LlmClassification(
        intent=IntentCategory(intent_value),
        confidence=confidence,
        entities={},
        latency_ms=50,
        model="fake",
        provider="fake",
    )


# case_id, conf, intent, role, fallback_enabled, err, exp_intent, exp_reason, exp_fb
_CASES = [
    ("row01_happy_high", 0.97, "research.meeting_prep", "advisor", True, None,
     "research.meeting_prep", None, False),
    ("row02_boundary_high", 0.95, "research.meeting_prep", "advisor", True, None,
     "research.meeting_prep", None, False),
    ("row03_just_below_high", 0.94999, "research.meeting_prep", "advisor", True, None,
     "research.meeting_prep", "llm_assisted_plan", False),
    ("row04_mid", 0.87, "client.data_lookup", "advisor", True, None,
     "client.data_lookup", "llm_assisted_plan", False),
    ("row05_lower_mid", 0.80, "client.data_lookup", "advisor", True, None,
     "client.data_lookup", "llm_assisted_plan", False),
    ("row06_just_below_mid", 0.79999, "client.data_lookup", "advisor", True, None,
     "escalate_to_human", "low_confidence", False),
    ("row07_deep_low", 0.05, "trade.inquiry", "advisor", True, None,
     "escalate_to_human", "low_confidence", False),
    ("row11_agent_trade_high", 0.98, "trade.inquiry", "agent", True, None,
     "trade.inquiry", "llm_assisted_plan", False),
    ("row12_agent_trade_low", 0.70, "trade.inquiry", "agent", True, None,
     "escalate_to_human", "low_confidence", False),
    ("row13_advisor_trade_high_no_downgrade", 0.98, "trade.inquiry", "advisor", True, None,
     "trade.inquiry", None, False),
    ("row14_timeout_fallback_hits", None, None, "advisor", True, "timeout",
     "research.meeting_prep", "llm_timeout", True),
    ("row15_timeout_fallback_miss", None, None, "advisor", True, "timeout_miss",
     "escalate_to_human", "regex_fallback_miss", True),
    ("row16_5xx_fallback_hits", None, None, "advisor", True, "5xx",
     "client.data_lookup", "llm_error_5xx", True),
    ("row17_4xx_no_fallback", None, None, "advisor", True, "4xx",
     "escalate_to_human", "llm_error_4xx", False),
    ("row18_nofb_timeout", None, None, "advisor", False, "timeout",
     "escalate_to_human", "llm_timeout", False),
    ("row19_nofb_4xx", None, None, "advisor", False, "4xx",
     "escalate_to_human", "llm_error_4xx", False),
    ("row20_malformed_fallback_hits", None, None, "advisor", True, "malformed",
     "research.meeting_prep", "llm_malformed_output", True),
    ("row21_malformed_fallback_miss", None, None, "advisor", True, "malformed_miss",
     "escalate_to_human", "llm_malformed_output", True),
]


@pytest.mark.parametrize(
    "case_id,conf,intent_val,role,fb,err,exp_intent,exp_reason,exp_fb",
    _CASES,
    ids=[c[0] for c in _CASES],
)
def test_confidence_thresholds(
    case_id,
    conf,
    intent_val,
    role,
    fb,
    err,
    exp_intent,
    exp_reason,
    exp_fb,
    fixture_aid_advisor,
    fixture_aid_agent,
    fixture_router_context_factory,
    fixture_intent_router_config,
    fixture_fake_llm_factory,
):
    utterance_map = {
        "timeout": "prep me for a meeting",  # fallback regex hits meeting_prep
        "timeout_miss": "zzzzzz nothing here",
        "5xx": "find the client",
        "4xx": "prep me for a meeting",
        "malformed": "prep me for a meeting",
        "malformed_miss": "zzzzzz nothing here",
    }
    utter = (
        utterance_map.get(err, "find the client")
        if err is not None
        else "some utterance"
    )

    aid = fixture_aid_agent if role == "agent" else fixture_aid_advisor
    ctx = fixture_router_context_factory(aid)
    cfg = fixture_intent_router_config.model_copy(update={"fallback_enabled": fb})

    if err in ("timeout", "timeout_miss"):
        provider = fixture_fake_llm_factory({utter: LlmTimeoutError("slow")})
    elif err == "5xx":
        provider = fixture_fake_llm_factory({utter: LlmProviderError(503, "down")})
    elif err == "4xx":
        provider = fixture_fake_llm_factory({utter: LlmProviderError(400, "bad")})
    elif err in ("malformed", "malformed_miss"):
        provider = fixture_fake_llm_factory({utter: LlmMalformedOutputError("bad")})
    else:
        provider = fixture_fake_llm_factory({utter: _lc(intent_val, conf)})

    decision = route(utter, ctx, _provider=provider, _config=cfg)
    assert decision.intent.value == exp_intent, (
        f"{case_id}: intent={decision.intent.value!r} vs {exp_intent!r}"
    )
    assert decision.reason_code == exp_reason, (
        f"{case_id}: reason_code={decision.reason_code!r} vs {exp_reason!r}"
    )
    assert decision.fallback_used is exp_fb, (
        f"{case_id}: fallback_used={decision.fallback_used} vs {exp_fb}"
    )
