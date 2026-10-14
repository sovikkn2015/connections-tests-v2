"""
M9 Task 5 -- Hypothesis property tests for regex library.

AC6.7: extract_entities never raises re.error over >=500 examples.
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from m9_intent_router.regex_library import extract_entities


@given(utterance=st.text(min_size=0, max_size=500))
@settings(max_examples=500, deadline=None)
def test_extract_entities_never_raises(utterance):
    # Must not raise ANY exception.
    result = extract_entities(utterance)
    assert isinstance(result, dict)


@given(utterance=st.text(min_size=1, max_size=200))
@settings(max_examples=200, deadline=None)
def test_no_ambiguous_ticker_leak(utterance):
    """Utterances with letters 'I', 'A' alone must not populate ticker."""
    result = extract_entities(utterance)
    # If ticker was populated, it must be in the whitelist.
    if "ticker" in result:
        assert result["ticker"] not in {"I", "A", "F"}
