"""
M9 Intent Router -- Deterministic fallback router (R7, AC7.1-7.7).

On LLM timeout/5xx/malformed, a keyword-regex router classifies the utterance
to one of three canonical intents. If none match, escalate. 4xx skips fallback
entirely (config defect, never transient).

See `.kiro/specs/m9-intent-router.md` R7 Deterministic Fallback Router.
"""

from __future__ import annotations

import re
from typing import Optional

from m9_intent_router.taxonomy import IntentCategory

_MEETING_PREP = re.compile(
    r"\b(prep|prepare|prep me|meeting|brief me|get ready)\b", re.IGNORECASE
)
_MARKET_QUERY = re.compile(
    r"\b(market|quote|price|research|earnings|fundamentals)\b", re.IGNORECASE
)
# Client data lookup: trigger + (client|account|household) within short window.
_CLIENT_DATA = re.compile(
    r"\b(show|lookup|find|get|fetch|pull\s+up)\s+(?:\w+\s+){0,3}"
    r"(client|account|household)\b",
    re.IGNORECASE,
)


def fallback_classify(utterance: str) -> Optional[IntentCategory]:
    """Deterministic regex fallback (AC7.1).

    Returns the matched IntentCategory or None. Pure, no I/O. Never raises.

    Precedence: meeting_prep -> client_data_lookup -> market_query.
    (meeting_prep first because 'prep me for meeting' is more specific than
    generic 'market' keywords.)
    """
    if not utterance:
        return None
    if _MEETING_PREP.search(utterance):
        return IntentCategory.RESEARCH_MEETING_PREP
    if _CLIENT_DATA.search(utterance):
        return IntentCategory.CLIENT_DATA_LOOKUP
    if _MARKET_QUERY.search(utterance):
        return IntentCategory.RESEARCH_MARKET_QUERY
    return None
