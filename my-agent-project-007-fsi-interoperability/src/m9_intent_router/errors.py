"""
M9 Intent Router -- Error classes + closed reason-code vocabulary (R11).

VALID_REASON_CODES is a frozenset of exactly 13 codes in v0.2.0
(added aid_authority_denied per Fix 8 / R12 AC12.9).

See `.kiro/specs/m9-intent-router.md` Error Code Map.
"""

from __future__ import annotations

#: Closed reason_code vocabulary (AC11.1). Adding a code is a MINOR bump;
#: removing/renaming is a MAJOR bump. 13 codes in v0.2.0.
VALID_REASON_CODES: frozenset[str] = frozenset({
    "llm_timeout",
    "llm_error_5xx",
    "llm_error_4xx",
    "llm_malformed_output",
    "mnpi_shape_suspected",
    "low_confidence",
    "regex_fallback_miss",
    "provider_unconfigured",
    "taxonomy_mismatch",
    "llm_assisted_plan",
    "invalid_utterance_length",
    "unsupported_intent_stub",
    "aid_authority_denied",  # v0.2.0 -- Fix 8 (AID scope denial)
})


class LlmProviderError(Exception):
    """Bedrock/provider returned a non-2xx status. status_code pinned to exc."""

    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        super().__init__(message or f"LLM provider error: HTTP {status_code}")


class LlmTimeoutError(Exception):
    """classify() exceeded provider.timeout_ms (AC3.4)."""


class LlmMalformedOutputError(Exception):
    """Provider returned unparseable tool output (AC3.4 / AC5.7)."""
