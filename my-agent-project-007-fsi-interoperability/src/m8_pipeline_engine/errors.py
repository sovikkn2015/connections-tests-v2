"""
M8 Pipeline Engine -- Error vocabulary.

Exposes:
- VALID_REASON_CODES: frozenset[str] -- exactly 20 lowercase snake_case codes.
- LlmProviderError / LlmTimeoutError / LlmMalformedOutputError -- the error
  classes that SonnetClient.generate() raises (AC6.5).

See `.kiro/specs/m8-pipeline-engine.md` R11.
"""

from __future__ import annotations


# =============================================================================
# 20-code closed reason vocabulary (AC11.1).
# =============================================================================

VALID_REASON_CODES: frozenset[str] = frozenset(
    {
        "m8_stage_failed",
        "m8_llm_timeout",
        "m8_llm_5xx",
        "m8_llm_4xx",
        "m8_llm_malformed_output",
        "m8_checkpoint_write_failed",
        "m8_hitl_denied",
        "m8_hitl_timeout",
        "m8_hitl_role_mismatch",
        "m8_hitl_token_expired",
        "m8_compliance_denied",
        "m8_audit_write_failed",
        "m8_mnpi_leaked_through_gateway",
        "m8_map_reduce_too_wide",
        "m8_map_reduce_all_failed",
        "m8_token_budget_exceeded",
        "m8_wall_clock_exceeded",
        "m8_tenant_concurrency_exceeded",
        "m8_anti_fabrication_failed",
        "m8_invalid_state",
    }
)

assert len(VALID_REASON_CODES) == 20, (
    f"VALID_REASON_CODES must have exactly 20 codes (got {len(VALID_REASON_CODES)})"
)


# =============================================================================
# LLM provider exception classes (AC6.5).
# =============================================================================


class LlmProviderError(Exception):
    """Bedrock (or other provider) 4xx / 5xx response.

    ``status_code`` is the HTTP-level status when available.
    """

    def __init__(self, status_code: int, message: str = "") -> None:
        super().__init__(
            f"{status_code}: {message}" if message else str(status_code)
        )
        self.status_code = status_code


class LlmTimeoutError(Exception):
    """Bedrock call exceeded the configured timeout."""


class LlmMalformedOutputError(Exception):
    """Bedrock returned output that could not be parsed."""


__all__ = [
    "VALID_REASON_CODES",
    "LlmProviderError",
    "LlmTimeoutError",
    "LlmMalformedOutputError",
]
