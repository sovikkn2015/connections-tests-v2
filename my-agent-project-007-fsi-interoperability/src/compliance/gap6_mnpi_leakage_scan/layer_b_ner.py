"""
Gap 6 — Layer B (NER).

Named-entity recognizer Protocol + Phase 1 stub. Runs second in the
3-layer pipeline; only reached if Layer A ALLOWs.

Phase 2 swaps `StubNamedEntityRecognizer` for a real NER impl (spaCy,
cloud NER) behind the same Protocol. Gap 6 code does NOT import any
NER library.

Stub behavior is intentionally aggressive (spec R3.2). Two
consecutive Title-Case words ("John Smith", "Federal Reserve", "New
York", "Wall Street") all trigger DENY. Fail-closed cost; locked in
by T6.7b.

See `.kiro/specs/gap6-mnpi-leakage-scan.md` R3 for the contract.
"""

from __future__ import annotations

import re
from typing import Protocol

from compliance.gap6_mnpi_leakage_scan._types import ScanDecision


_MAX_INPUT_BYTES = 10 * 1024 * 1024


# =============================================================================
# Stub patterns.
# =============================================================================


_NAME_PATTERN = re.compile(r"\b[A-Z][a-z]+\s+[A-Z][a-z]+\b")
# 8-11 digits: catches account-candidate tokens that Layer A's >=12
# threshold missed.
_ACCT_CANDIDATE_PATTERN = re.compile(r"\b\d{8,11}\b")


# =============================================================================
# Protocol (spec R3.1).
# =============================================================================


class NamedEntityRecognizer(Protocol):
    """NER Protocol. Phase 1 stub + Phase 2 impls both satisfy this."""

    def scan(
        self, text: str
    ) -> tuple[ScanDecision, tuple[str, ...]]:  # pragma: no cover - protocol
        ...


# =============================================================================
# Phase 1 stub (spec R3.2).
# =============================================================================


class StubNamedEntityRecognizer:
    """Phase 1 stub NER. Intentionally aggressive.

    Blocks:
        - Any two consecutive Title-Case words (personal name
          candidate).
        - Any 8-11 consecutive digits (account-number candidate that
          Layer A's >=12 threshold missed).

    Common non-PII capitalized phrases ("Federal Reserve", "New
    York", "Wall Street", etc.) WILL be blocked. This is by design
    (fail-closed). Phase 2 NER (spaCy) replaces and relaxes.
    """

    _MAX_BYTES = _MAX_INPUT_BYTES

    def scan(self, text: str) -> tuple[ScanDecision, tuple[str, ...]]:
        if text is None:
            raise TypeError("text must be str (not None)")
        if not isinstance(text, str):
            raise TypeError("text must be str")
        if len(text.encode("utf-8")) > self._MAX_BYTES:
            raise ValueError("input too large for ner scan")

        if not text:
            return ScanDecision.ALLOW, ()

        hits: list[str] = []
        if _NAME_PATTERN.search(text):
            hits.append("ner:name")
        if _ACCT_CANDIDATE_PATTERN.search(text):
            hits.append("ner:account_candidate")

        if not hits:
            return ScanDecision.ALLOW, ()
        return ScanDecision.DENY, tuple(sorted(hits))


__all__ = ["NamedEntityRecognizer", "StubNamedEntityRecognizer"]
