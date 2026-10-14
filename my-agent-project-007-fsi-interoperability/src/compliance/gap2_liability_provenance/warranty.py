"""
Gap 2 — WarrantyBoundary.

Deterministic module-to-warranty mapping for Project 007 modules
M1..M13. Unknown modules classify as `unknown`, which downgrades the
overall chain warranty (fail-closed).

See `.kiro/specs/gap2-liability-provenance.md` R1 for the contract.

Coupling: `WarrantyBoundary.TABLE.keys()` MUST equal {m1..m13}. This
mirrors M10's `_MODULE_PATTERN`. If M10 expands the module namespace,
this table MUST be updated in the same PR (T2.7 enforces).
"""

from __future__ import annotations

from enum import Enum
from types import MappingProxyType
from typing import Mapping

from pydantic import BaseModel, ConfigDict


class WarrantyCategory(str, Enum):
    """Warranty classification category (fail-closed ordering)."""

    warranted = "warranted"
    best_effort = "best_effort"
    unknown = "unknown"

    def ordered_rank(self) -> int:
        """Return 0 (best) to 2 (worst). Used for max-rank aggregation."""
        return _CATEGORY_RANKS[self.value]


_CATEGORY_RANKS: Mapping[str, int] = MappingProxyType(
    {
        "warranted": 0,
        "best_effort": 1,
        "unknown": 2,
    }
)


class WarrantyReason(str, Enum):
    """Why a module carries its warranty category."""

    deterministic_code_007 = "deterministic_code_007"
    deterministic_opa_007 = "deterministic_opa_007"
    llm_007 = "llm_007"
    external_vendor = "external_vendor"
    unknown_module = "unknown_module"


class WarrantyClassification(BaseModel):
    """Frozen classification for a single module."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    module: str
    category: WarrantyCategory
    reason: WarrantyReason


# =============================================================================
# The warranty table (Phase 1, per spec R1.3).
# =============================================================================

_WARRANTY_TABLE: Mapping[str, tuple[WarrantyCategory, WarrantyReason]] = (
    MappingProxyType(
        {
            "m1": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
            "m2": (WarrantyCategory.warranted, WarrantyReason.deterministic_opa_007),
            "m3": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
            "m4": (WarrantyCategory.warranted, WarrantyReason.deterministic_opa_007),
            "m5": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
            "m6": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
            "m7": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
            "m8": (WarrantyCategory.best_effort, WarrantyReason.llm_007),
            "m9": (WarrantyCategory.best_effort, WarrantyReason.llm_007),
            "m10": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
            "m11": (WarrantyCategory.best_effort, WarrantyReason.external_vendor),
            "m12": (WarrantyCategory.best_effort, WarrantyReason.llm_007),
            "m13": (WarrantyCategory.warranted, WarrantyReason.deterministic_code_007),
        }
    )
)


class WarrantyBoundary:
    """Classifies a module string into a WarrantyClassification.

    Deterministic, pure (no I/O, no clock, no randomness). Thread-safe
    (TABLE is an immutable MappingProxyType).

    Classification for unknown modules defaults to `unknown` /
    `unknown_module` — this is the fail-closed contract. Callers
    SHOULD NOT mask this by forcing a warranted classification.
    """

    TABLE = _WARRANTY_TABLE

    def classify(self, module: str) -> WarrantyClassification:
        """Return a WarrantyClassification for the given module name.

        Module names are case-sensitive. Only lowercase m1..m13 are
        recognized. Everything else classifies as `unknown`.
        """
        entry = self.TABLE.get(module)
        if entry is None:
            return WarrantyClassification(
                module=module,
                category=WarrantyCategory.unknown,
                reason=WarrantyReason.unknown_module,
            )
        category, reason = entry
        return WarrantyClassification(
            module=module, category=category, reason=reason
        )

    def classify_all(self) -> Mapping[str, WarrantyClassification]:
        """Immutable mapping of every recognized module's classification.

        Used for regulator disclosure — the full warranty table MUST
        be showable. Returns a read-only MappingProxyType; mutation
        attempts raise TypeError.
        """
        result = {
            module: self.classify(module) for module in self.TABLE.keys()
        }
        return MappingProxyType(result)
