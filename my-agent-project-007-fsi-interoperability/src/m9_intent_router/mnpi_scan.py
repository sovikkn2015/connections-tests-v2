"""
M9 Intent Router -- MNPI-shape pre-scan (R8, AC8.2-8.9).

scan_mnpi_shape(utterance) returns the matched MNPI category name if any
pattern hits, else None. Category name is for unit-test introspection only
-- NEVER surfaced in reason_code (AC8.6).

Precedence (first-hit wins):
1. wire_instruction (compound signal, lowest FP)
2. routing_number (ABA-validated)
3. ssn dashed form
4. ssn bare 9-digit (anti-ZIP+4)
5. bank_account (10-17 digits)

See `.kiro/specs/m9-intent-router.md` MNPI-Shape Patterns.
"""

from __future__ import annotations

import re
from typing import Optional

_SSN_DASHED = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_NINE_DIGITS = re.compile(r"\b\d{9}\b")
_ZIP_PLUS4 = re.compile(r"\b\d{5}-\d{4}\b")
_BANK_10_17 = re.compile(r"\b\d{10,17}\b")
_WIRE_KW = re.compile(r"\b(wire|ACH|swift|BIC)\b", re.IGNORECASE)

# ABA routing checksum: positional weights 3,7,1 repeating.
_ABA_WEIGHTS = (3, 7, 1, 3, 7, 1, 3, 7, 1)


def _aba_valid(nine: str) -> bool:
    """Return True iff the 9-digit string passes ABA routing checksum."""
    if len(nine) != 9 or not nine.isdigit():
        return False
    return sum(int(d) * w for d, w in zip(nine, _ABA_WEIGHTS)) % 10 == 0


def scan_mnpi_shape(utterance: str) -> Optional[str]:
    """Return matched MNPI category name, or None. Precedence-ordered.

    Pure, no I/O. NEVER raises. Category names returned here are for
    unit-test introspection; reason_code always generic "mnpi_shape_suspected".
    """
    if not utterance:
        return None

    # 1. wire_instruction: compound keyword + numeric signal.
    if _WIRE_KW.search(utterance) and (
        _NINE_DIGITS.search(utterance) or _BANK_10_17.search(utterance)
    ):
        return "wire_instruction"

    # 2. routing_number: 9 digits with valid ABA checksum.
    for m in _NINE_DIGITS.finditer(utterance):
        if _aba_valid(m.group(0)):
            return "routing_number"

    # 3. ssn dashed form: anchored, low FP.
    if _SSN_DASHED.search(utterance):
        return "ssn"

    # 4. ssn bare 9-digit with anti-ZIP+4 filter.
    for m in _NINE_DIGITS.finditer(utterance):
        start = m.start()
        # Anti-ZIP+4: skip if 9 digits immediately follow a "12345-" pattern.
        preceding_6 = utterance[max(0, start - 6):start]
        if re.match(r"^\d{5}-$", preceding_6):
            continue
        # If utterance contains an explicit ZIP+4 anywhere, prefer fail-closed
        # -- we still flag this as ssn (Known Blockers row 10 acknowledges FP).
        _ = _ZIP_PLUS4.search(utterance)
        return "ssn"

    # 5. bank_account: 10-17 digits, runs last (highest FP).
    if _BANK_10_17.search(utterance):
        return "bank_account"

    return None
