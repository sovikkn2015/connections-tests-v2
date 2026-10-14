"""
PHASE 1 STUB - MUST NOT BE DEPLOYED TO PRODUCTION.

Replace with Bedrock Haiku classifier (Phase 2) before any customer
deployment. This stub uses a small English-phrase keyword list as a
placeholder; it is not a real MNPI classifier.

Gap 6 - Layer C (LLM classifier) - Protocol + Phase 1 stub.

Runs third in the 3-layer pipeline; only reached if Layers A and B
both ALLOW.

Phase 2 implementation lives OUTSIDE Gap 6 (e.g.,
src/m6_mcp_gateway/bedrock_guardrail.py) and is injected as an
`LlmClassifier`. Gap 6 Phase 1 code MUST NOT import `anthropic`,
`openai`, `boto3`, `langchain`, `spacy`, `transformers` (enforced by
T6.24).

See `.kiro/specs/gap6-mnpi-leakage-scan.md` R4 for the contract.
"""

from __future__ import annotations

from typing import Protocol

from compliance.gap6_mnpi_leakage_scan._types import ScanDecision


_MAX_INPUT_BYTES = 10 * 1024 * 1024


# =============================================================================
# Keyword list (spec R4.2) - 25 entries across 4 categories.
# Phase 1 stub ONLY. Phase 2 replaces with Bedrock Haiku classifier.
# Categories are documentation-only; runtime uses a flat tuple.
# =============================================================================
#
# earnings_terms (7): earnings surprise, pre-announcement,
#   beat consensus, will beat consensus, missed earnings,
#   guidance revision, preliminary results
# deal_terms (7):     merger discussions, takeover talks,
#   acquisition target, tender offer, spin-off,
#   strategic review, exclusive negotiations
# insider_terms (5):  insider, material non-public, mnpi,
#   confidential information, non-public information
# timing_terms (6):   before the announcement,
#   ahead of the press release, embargo, blackout period,
#   prior to disclosure, pre-release

_KEYWORDS: tuple[str, ...] = (
    "earnings surprise",
    "pre-announcement",
    "beat consensus",
    "will beat consensus",
    "missed earnings",
    "guidance revision",
    "preliminary results",
    "merger discussions",
    "takeover talks",
    "acquisition target",
    "tender offer",
    "spin-off",
    "strategic review",
    "exclusive negotiations",
    "insider",
    "material non-public",
    "mnpi",
    "confidential information",
    "non-public information",
    "before the announcement",
    "ahead of the press release",
    "embargo",
    "blackout period",
    "prior to disclosure",
    "pre-release",
)


# =============================================================================
# Protocol (spec R4.1).
# =============================================================================


class LlmClassifier(Protocol):
    """LLM classifier Protocol. Phase 1 stub + Phase 2 impls both satisfy."""

    def scan(
        self, text: str
    ) -> tuple[ScanDecision, tuple[str, ...]]:  # pragma: no cover - protocol
        ...


# =============================================================================
# Phase 1 stub (spec R4.2).
# =============================================================================


class StubLlmClassifier:
    """Phase 1 stub classifier. NOT a production classifier.

    Scans for a small hard-coded keyword list. First hit -> DENY
    `("llm:mnpi_keyword",)`. Else ALLOW.

    The KEYWORDS attribute is exposed for Phase 1 testability.
    Phase 2 Bedrock classifier has no such attribute - the Protocol
    is the ONLY stable contract.
    """

    KEYWORDS: tuple[str, ...] = _KEYWORDS
    _MAX_BYTES = _MAX_INPUT_BYTES

    def scan(self, text: str) -> tuple[ScanDecision, tuple[str, ...]]:
        if text is None:
            raise TypeError("text must be str (not None)")
        if not isinstance(text, str):
            raise TypeError("text must be str")
        if len(text.encode("utf-8")) > self._MAX_BYTES:
            raise ValueError("input too large for llm classifier scan")

        if not text:
            return ScanDecision.ALLOW, ()

        lowered = text.lower()
        for kw in self.KEYWORDS:
            if kw in lowered:
                return ScanDecision.DENY, ("llm:mnpi_keyword",)
        return ScanDecision.ALLOW, ()


__all__ = ["LlmClassifier", "StubLlmClassifier"]
