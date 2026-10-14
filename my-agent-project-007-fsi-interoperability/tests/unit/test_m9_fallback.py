"""
M9 Task 9 -- Deterministic fallback router.

AC7.1-7.7.
"""

from __future__ import annotations

from m9_intent_router import IntentCategory
from m9_intent_router.fallback import fallback_classify


def test_meeting_prep_positive():
    assert (
        fallback_classify("prep me for the meeting")
        == IntentCategory.RESEARCH_MEETING_PREP
    )
    assert (
        fallback_classify("brief me tomorrow")
        == IntentCategory.RESEARCH_MEETING_PREP
    )


def test_market_query_positive():
    assert (
        fallback_classify("what's the market quote")
        == IntentCategory.RESEARCH_MARKET_QUERY
    )
    assert (
        fallback_classify("check NVDA earnings")
        == IntentCategory.RESEARCH_MARKET_QUERY
    )


def test_client_data_lookup_positive():
    assert (
        fallback_classify("pull up client 001ABCDEF")
        == IntentCategory.CLIENT_DATA_LOOKUP
    )
    assert (
        fallback_classify("find the account 123")
        == IntentCategory.CLIENT_DATA_LOOKUP
    )


def test_fallback_returns_none_on_miss():
    assert fallback_classify("random gibberish here") is None


def test_fallback_empty_input():
    assert fallback_classify("") is None


def test_fallback_precedence_meeting_over_market():
    """meeting_prep comes before market_query in precedence."""
    result = fallback_classify("prep me for market opens")
    assert result == IntentCategory.RESEARCH_MEETING_PREP
