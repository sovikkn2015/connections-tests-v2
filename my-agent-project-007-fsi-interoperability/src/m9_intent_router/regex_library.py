"""
M9 Intent Router -- Entity extraction regex library (R6, AC6.1-6.8).

Pure, no I/O, no module-level mutable state. Never raises (AC6.7 asserted via
Hypothesis >=500 examples). Missing slots absent from returned dict (AC6.1).

Slots:
- ticker: whitelist-filtered \\b[A-Z]{1,5}\\b
- client_id: SF 18-char with base-32 checksum
- household_id: \\bHH-[A-Z0-9]{10,16}\\b
- account_id: \\bACC-[A-Z0-9]{8,12}\\b
- date_range: ISO-8601 absolute OR relative whitelist

See `.kiro/specs/m9-intent-router.md` Entity Extraction Regex Library.
"""

from __future__ import annotations

import re
from datetime import date
from types import MappingProxyType

# Phase 2 ticker whitelist -- 50 most-queried NYSE/NASDAQ large-caps.
# Single-letter confusables like A, F deliberately excluded.
_TICKER_WHITELIST: frozenset[str] = frozenset({
    "NVDA", "AAPL", "MSFT", "GOOGL", "GOOG", "AMZN", "META", "TSLA", "BRK", "BRKB",
    "JPM", "BAC", "WFC", "GS", "MS", "C", "SCHW", "AXP", "BLK", "V",
    "MA", "PG", "KO", "PEP", "WMT", "COST", "HD", "MCD", "NKE", "DIS",
    "XOM", "CVX", "COP", "SLB", "PFE", "MRK", "JNJ", "UNH", "LLY", "ABBV",
    "BA", "CAT", "GE", "HON", "UPS", "FDX", "NEE", "T", "VZ", "CRM",
})

# Relative date-range whitelist (case-insensitive match; canonical form emitted).
_DATE_RELATIVE_WHITELIST: dict[str, str] = {
    "last quarter": "last_quarter",
    "last_quarter": "last_quarter",
    "ytd": "YTD",
    "last 30 days": "last_30_days",
    "last_30_days": "last_30_days",
    "last 90 days": "last_90_days",
    "last_90_days": "last_90_days",
    "last 12 months": "last_12_months",
    "last_12_months": "last_12_months",
}


# Compile-once regex patterns (cached in MappingProxyType for immutability).
_PATTERNS = MappingProxyType({
    "ticker": re.compile(r"\b[A-Z]{1,5}\b"),
    "client_id": re.compile(r"\b[a-zA-Z0-9]{18}\b"),
    "household_id": re.compile(r"\bHH-[A-Z0-9]{10,16}\b"),
    "account_id": re.compile(r"\bACC-[A-Z0-9]{8,12}\b"),
    "date_range_abs": re.compile(
        r"\b(\d{4}-\d{2}-\d{2})\s*(?:to|-|through|\u2014)\s*(\d{4}-\d{2}-\d{2})\b"
    ),
})


# Salesforce 18-char checksum algorithm (AC6.3, Recommended Fix 11).
_SF_B32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"


def _validate_sf_id(s: str) -> bool:
    """Validate the trailing 3-char base-32 checksum of an SF 18-char id.

    - Split first 15 chars into three 5-char groups.
    - Per group: build 5-bit number where bit i = 1 iff char i is uppercase.
    - Map each 5-bit int (0-31) into base-32 alphabet A-Z0-5.
    - The 3-char sequence IS the trailing checksum.
    """
    if len(s) != 18:
        return False
    try:
        check = ""
        for group in (s[0:5], s[5:10], s[10:15]):
            n = 0
            for i, ch in enumerate(group):
                if ch.isupper():
                    n |= 1 << i
            check += _SF_B32_ALPHABET[n]
        return s[15:18].upper() == check
    except (IndexError, ValueError):
        return False


def _parse_date(s: str) -> bool:
    """Return True if s parses as a valid YYYY-MM-DD date."""
    try:
        y, m, d = s.split("-")
        date(int(y), int(m), int(d))
        return True
    except (ValueError, AttributeError):
        return False


def extract_entities(utterance: str) -> dict[str, str]:
    """Extract entities from an utterance (AC6.1).

    Returns a dict with only populated slots; missing slots are absent (not None).
    Never raises.

    Keys: ticker, client_id, household_id, account_id, date_range.
    """
    out: dict[str, str] = {}
    if not utterance:
        return out

    # ticker -- whitelist intersection.
    for m in _PATTERNS["ticker"].finditer(utterance):
        tok = m.group(0)
        if tok in _TICKER_WHITELIST:
            out["ticker"] = tok
            break

    # client_id -- SF 18-char + checksum.
    for m in _PATTERNS["client_id"].finditer(utterance):
        candidate = m.group(0)
        if _validate_sf_id(candidate):
            out["client_id"] = candidate
            break

    # household_id -- HH- prefix.
    m = _PATTERNS["household_id"].search(utterance)
    if m and len(m.group(0)) <= 19:
        out["household_id"] = m.group(0)

    # account_id -- ACC- prefix.
    m = _PATTERNS["account_id"].search(utterance)
    if m and len(m.group(0)) <= 16:
        out["account_id"] = m.group(0)

    # date_range absolute -- ISO 8601 range, Pydantic-parseable, start<=end.
    m = _PATTERNS["date_range_abs"].search(utterance)
    if m:
        start, end = m.group(1), m.group(2)
        if _parse_date(start) and _parse_date(end) and start <= end:
            out["date_range"] = f"{start} to {end}"
    # relative whitelist -- only if absolute did not hit.
    if "date_range" not in out:
        lowered = utterance.lower()
        for key, canonical in _DATE_RELATIVE_WHITELIST.items():
            if key in lowered:
                out["date_range"] = canonical
                break

    return out
