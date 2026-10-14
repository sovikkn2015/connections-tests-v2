"""
Gap 1 — M4 MNPI preflight gate.

Runs BEFORE every ``NarrativeClient.stitch`` call. Fail-closed: any
filter exception OR ``passed=False`` ABORTS the narrative for that
section (steering rule 7 / rule 8).

See .kiro/specs/gap1-reg-bi-doc-generator.md R4b.

Design notes:
    - ``MnpiFilter`` is a Protocol — the real M4 ``MnpiPolicy`` from
      ``m2_m4_policy_engine`` is wired by the hosting service. Gap 1
      does NOT import M4 (module boundary, steering rule 9).
    - ``RegexMnpiFilter`` is the Phase-3 default when no real M4 is
      wired. To avoid drift, the scrub patterns are imported from
      ``document._PII_PATTERNS`` — single source of truth (R4b.2 / F6).
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from m1_identity import AidClaims

from compliance.gap1_reg_bi_doc_generator.document import _PII_PATTERNS

# =============================================================================
# Result record
# =============================================================================


class MnpiPreflightResult(BaseModel):
    """Frozen result returned by ``MnpiFilter.preflight``."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    passed: bool
    reason: str = Field(default="", max_length=200)
    #: Filtered bullets — non-empty iff ``passed=True`` AND the filter
    #: chose to substitute a scrubbed form.
    filtered_bullets: tuple[str, ...] = Field(default_factory=tuple)


# =============================================================================
# Protocol
# =============================================================================


@runtime_checkable
class MnpiFilter(Protocol):
    """M4 MNPI preflight filter interface.

    Implementations must be deterministic and fast (target < 10 ms for
    the regex path). The real M4 ``MnpiPolicy`` is wired in by the
    hosting service; Gap 1 provides ``StubMnpiFilter`` and
    ``RegexMnpiFilter`` as defaults.
    """

    def preflight(
        self,
        *,
        bullets: tuple[str, ...],
        claims: AidClaims,
    ) -> MnpiPreflightResult: ...


# =============================================================================
# Stock implementations
# =============================================================================


class StubMnpiFilter:
    """Pass-through stub for unit tests that do not exercise the gate.

    ``pass_all=True`` → always returns ``passed=True`` (no filtering).
    ``pass_all=False`` → always returns ``passed=False``. Useful for
    locking fail-closed behaviour in tests without wiring a raising
    filter.
    """

    def __init__(self, *, pass_all: bool = True) -> None:
        self._pass_all = pass_all

    def preflight(
        self,
        *,
        bullets: tuple[str, ...],
        claims: AidClaims,
    ) -> MnpiPreflightResult:
        if self._pass_all:
            return MnpiPreflightResult(passed=True, reason="stub_pass")
        return MnpiPreflightResult(
            passed=False, reason="stub_block"
        )


class RegexMnpiFilter:
    """Deterministic regex-based MNPI filter.

    Applies the 4 module-local PII patterns (SSN, long-digit
    account, email, IBAN) to every bullet. If any pattern matches in
    any bullet, returns ``passed=False``. No scrubbing — this is a
    gate, not a mutator. No LLM.
    """

    def preflight(
        self,
        *,
        bullets: tuple[str, ...],
        claims: AidClaims,
    ) -> MnpiPreflightResult:
        for bullet in bullets:
            for name, pat in _PII_PATTERNS:
                if pat.search(bullet):
                    return MnpiPreflightResult(
                        passed=False,
                        reason=f"pattern_match:{name}",
                    )
        return MnpiPreflightResult(
            passed=True, reason="regex_clean"
        )
