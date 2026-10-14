"""
Gap 1 — Narrative layer (LLM wrapper, OPTIONAL).

The narrative is COSMETIC. Compliance decisions (applicability,
four-obligation populate, min-bullet enforcement, advisor-review gate)
are 100% deterministic. The LLM only stitches bullets into prose.

Two stock implementations:
    - StubNarrativeClient: always returns "" (no prose).
    - BulletConcatNarrativeClient: deterministic, no LLM —
      `"; ".join(bullets)[:2000]`.

A real Bedrock / Anthropic client is injected by the hosting service
in Phase 3; the SDK import lives OUTSIDE Gap 1 (module boundary).

See .kiro/specs/gap1-reg-bi-doc-generator.md R4.
"""

from __future__ import annotations

import re
from typing import Protocol, runtime_checkable

from compliance.gap1_reg_bi_doc_generator._types import ObligationCode

# =============================================================================
# populated_by regex (R3.5)
# =============================================================================

#: Matches ``reg_bi/{obligation}/populate.v{N}`` paths. Each populator
#: versions INDEPENDENTLY (F4 from v1 review).
POPULATED_BY_RE: re.Pattern[str] = re.compile(
    r"^reg_bi/(disclosure|care|coi|compliance)/populate\.v[1-9]\d*$"
)


# =============================================================================
# NarrativeClient Protocol
# =============================================================================


@runtime_checkable
class NarrativeClient(Protocol):
    """Stitches bullets into narrative prose. Cosmetic only."""

    def stitch(
        self,
        *,
        obligation: ObligationCode,
        bullets: tuple[str, ...],
        reason_trace: tuple[str, ...],
    ) -> str: ...


# =============================================================================
# Stock implementations
# =============================================================================


class StubNarrativeClient:
    """Always returns empty narrative. Phase 2 default."""

    def stitch(
        self,
        *,
        obligation: ObligationCode,
        bullets: tuple[str, ...],
        reason_trace: tuple[str, ...],
    ) -> str:
        return ""


class BulletConcatNarrativeClient:
    """Deterministic, no-LLM bullet concatenator.

    `"; ".join(bullets)` hard-cut at 2000 bytes (R4.3). Used when a
    RegBiConfig requests a narrative but no LLM has been wired in
    (e.g., local dev / tests). Tests lock this behaviour.
    """

    _MAX_CHARS = 2000

    def stitch(
        self,
        *,
        obligation: ObligationCode,
        bullets: tuple[str, ...],
        reason_trace: tuple[str, ...],
    ) -> str:
        joined = "; ".join(bullets)
        return joined[: self._MAX_CHARS]


class FakeLLMNarrativeClient:
    """Deterministic canned-response client for integration tests (R4.4).

    Keyed by ``(obligation, bullets_hash)``. If no canned response is
    provided, returns an empty string. Used to avoid wiring a real
    Bedrock SDK from tests.
    """

    def __init__(
        self,
        responses: dict[tuple[ObligationCode, str], str] | None = None,
        default: str = "",
    ) -> None:
        self._responses: dict[tuple[ObligationCode, str], str] = (
            dict(responses) if responses else {}
        )
        self._default = default

    @staticmethod
    def bullets_hash(bullets: tuple[str, ...]) -> str:
        """Deterministic hash of bullets — SHA-256 hex (8 chars prefix)."""
        import hashlib

        joined = "\u241e".join(bullets)  # record-separator
        return hashlib.sha256(joined.encode("utf-8")).hexdigest()[:8]

    def stitch(
        self,
        *,
        obligation: ObligationCode,
        bullets: tuple[str, ...],
        reason_trace: tuple[str, ...],
    ) -> str:
        key = (obligation, self.bullets_hash(bullets))
        return self._responses.get(key, self._default)
