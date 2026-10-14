"""
Gap 6 — Layer A (regex).

Fast-path regex scanner for PII/MNPI patterns. Covers >95% of real
cases. Runs first in the 3-layer pipeline (A -> B -> C).

All patterns are linear-time (no nested quantifiers on overlapping
classes, no backreferences). ReDoS-safe. See T6.26.

Layer A is intentionally trigger-happy (email regex fires on benign
mentions; account_number fires on any 12+ digits). That is the fail-
closed cost. Phase 2 NER (Layer B) + Bedrock classifier (Layer C)
refine the signal.

See `.kiro/specs/gap6-mnpi-leakage-scan.md` R2 for the contract.
"""

from __future__ import annotations

import re
from typing import Pattern

from compliance.gap6_mnpi_leakage_scan._types import ScanDecision


_MAX_INPUT_BYTES = 10 * 1024 * 1024  # 10 MB DoS cap


# =============================================================================
# Patterns (spec R2.1, R2.2).
# =============================================================================


PATTERNS: tuple[tuple[str, Pattern[str]], ...] = (
    # US SSN, dashed form only. Undashed 9-digit SSN is NOT matched
    # here (would cause catastrophic FP on order IDs). Phase 2 NER
    # catches undashed form.
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    # Any 12+ consecutive digits. Intentionally broad - catches
    # account numbers, timestamps (Unix ms/ns), tracking IDs. Fail-
    # closed cost.
    ("account_number", re.compile(r"\b\d{12,}\b")),
    # IBAN shape (2 letters + 2 digits + 11-30 alphanumeric).
    # Mod-97-10 checksum validation is Phase 2.
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
    # Email. Pattern is linear-time; no nested quantifiers on the
    # same class. ReDoS-safe per T6.26.
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
)


class LayerARegexScanner:
    """Layer A - regex scanner. Stateless, thread-safe.

    Input validation:
        - None -> TypeError
        - non-str -> TypeError
        - >10MB -> ValueError

    Returns a tuple `(decision, match_codes)`. Match codes are
    deduplicated and sorted (deterministic output).

    Never emits raw matched text - only the code that identified the
    pattern (spec R2.4).
    """

    PATTERNS = PATTERNS
    _MAX_BYTES = _MAX_INPUT_BYTES

    def scan(self, text: str) -> tuple[ScanDecision, tuple[str, ...]]:
        if text is None:
            raise TypeError("text must be str (not None)")
        if not isinstance(text, str):
            raise TypeError("text must be str")
        if len(text.encode("utf-8")) > self._MAX_BYTES:
            raise ValueError("input too large for regex scan")

        if not text:
            return ScanDecision.ALLOW, ()

        hits: set[str] = set()
        for code, pattern in self.PATTERNS:
            if pattern.search(text):
                hits.add(code)

        if not hits:
            return ScanDecision.ALLOW, ()
        return ScanDecision.DENY, tuple(sorted(hits))


__all__ = ["LayerARegexScanner", "PATTERNS"]
