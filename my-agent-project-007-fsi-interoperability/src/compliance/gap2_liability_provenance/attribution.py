"""
Gap 2 — ErrorAttribution + LiabilityReport.

Frozen Pydantic models that bundle a provenance chain, warranty
classifications, and optional error attribution into a deterministic,
regulator-ready liability artifact.

See `.kiro/specs/gap2-liability-provenance.md` R2-R3 for the contract.

No I/O, no clock, no random. Canonical JSON is the SOLE public
serialization contract (R3.4).
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional, Sequence
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m3_schema_registry import ProvenanceStage
from compliance.gap2_liability_provenance.warranty import (
    WarrantyBoundary,
    WarrantyCategory,
    WarrantyClassification,
)


# =============================================================================
# Error taxonomy (spec R2.1).
# =============================================================================


class ErrorCategory(str, Enum):
    """6-category error taxonomy from ARCH-06 Gap 2."""

    source_data_error = "source_data_error"
    schema_translation_error = "schema_translation_error"
    policy_evaluation_error = "policy_evaluation_error"
    llm_synthesis_error = "llm_synthesis_error"
    human_approval_error = "human_approval_error"
    compliance_rule_error = "compliance_rule_error"


# =============================================================================
# PII regex set for `ErrorAttribution.reason` (spec R2.4).
# Duplicated locally from Gap 6 (the two gaps are intentionally decoupled).
# =============================================================================

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account_number", re.compile(r"\b\d{12,}\b")),
    ("email", re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
)


def _reject_pii(value: str) -> str:
    """Raise ValueError if `value` matches any PII regex. Else echo."""
    for code, pattern in _PII_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"reason contains potential PII pattern: {code}"
            )
    return value


# =============================================================================
# Canonical JSON helpers (spec R3.4).
# =============================================================================


def _json_default(obj: Any) -> Any:
    """JSON default handler — mirrors M10's `_canonical_json` contract.

    Overlapping types (datetime, Enum, UUID) MUST serialize
    identically across modules. See M10 `_canonical_json` for the
    reference implementation.
    """
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise TypeError("naive datetime not serializable")
        return obj.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")


def _canonical_json(data: Any) -> str:
    """Canonical JSON: key-sorted, compact, deterministic."""
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


# =============================================================================
# ErrorAttribution (spec R2).
# =============================================================================


class ErrorAttribution(BaseModel):
    """Attributes a pipeline failure to a stage + module + category.

    See spec R2.2-R2.5. `reason` is validated against the PII regex
    set at construction (R2.4). Phase 1 is free-text up to 500 chars;
    Phase 2 will add structured `reason_codes` (forward-compatible via
    `extra="forbid"`).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    category: ErrorCategory
    stage: str = Field(min_length=1, max_length=200)
    module: str = Field(min_length=1, max_length=20)
    reason: str = Field(max_length=500)
    occurred_at: datetime

    @field_validator("occurred_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("occurred_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("reason")
    @classmethod
    def _validate_reason_pii(cls, v: str) -> str:
        return _reject_pii(v)

    @classmethod
    def attribute_from_chain(
        cls,
        *,
        chain: Sequence[ProvenanceStage],
        failing_stage_name: str,
        category: ErrorCategory,
        reason: str,
        occurred_at: datetime,
    ) -> "ErrorAttribution":
        """Build an ErrorAttribution by looking up the failing stage in a chain.

        Raises ValueError on empty chain / stage-not-found / duplicate.
        """
        if not chain:
            raise ValueError("chain is empty")
        matches = [s for s in chain if s.stage == failing_stage_name]
        if not matches:
            raise ValueError(
                f"stage {failing_stage_name!r} not in chain"
            )
        if len(matches) > 1:
            raise ValueError(
                f"stage {failing_stage_name!r} appears more than once in chain"
            )
        return cls(
            category=category,
            stage=failing_stage_name,
            module=matches[0].module,
            reason=reason,
            occurred_at=occurred_at,
        )


# =============================================================================
# StageClassification + LiabilitySummary (spec R3.1).
# =============================================================================


class StageClassification(BaseModel):
    """One stage + its warranty classification + is_failing flag."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage: ProvenanceStage
    classification: WarrantyClassification
    is_failing: bool = False


class LiabilitySummary(BaseModel):
    """Counters derived from stage_classifications + error_attribution."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_count: int
    warranted_count: int
    best_effort_count: int
    unknown_count: int
    failing_stage: Optional[str] = None
    failing_module: Optional[str] = None
    failing_category: Optional[ErrorCategory] = None


# =============================================================================
# LiabilityReport (spec R3).
# =============================================================================


REPORT_SCHEMA_VERSION = "1.0.0"


class LiabilityReport(BaseModel):
    """Deterministic, regulator-ready liability artifact.

    Built via `LiabilityReport.build(...)`. See spec R3.

    Construction failures (empty chain, naive datetime, attribution
    referencing unknown stage) raise ValueError. `is_clean()` is the
    fail-closed gate for callers deciding whether an output is
    deliverable.
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    report_schema_version: Literal["1.0.0"] = REPORT_SCHEMA_VERSION
    trace_id: str = Field(min_length=1, max_length=200)
    generated_at: datetime
    chain: tuple[ProvenanceStage, ...]
    chain_verified: bool
    stage_classifications: tuple[StageClassification, ...]
    overall_warranty: WarrantyCategory
    error_attribution: Optional[ErrorAttribution] = None
    summary: LiabilitySummary

    @field_validator("generated_at")
    @classmethod
    def _require_tz_aware_generated_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("chain")
    @classmethod
    def _chain_nonempty(
        cls, v: tuple[ProvenanceStage, ...]
    ) -> tuple[ProvenanceStage, ...]:
        if not v:
            raise ValueError("chain must be non-empty")
        return v

    # ---------------------------------------------------------------------
    # Construction (spec R3.2)
    # ---------------------------------------------------------------------

    @classmethod
    def build(
        cls,
        *,
        trace_id: str,
        chain: Sequence[ProvenanceStage],
        chain_verified: bool,
        generated_at: datetime,
        error: Optional[ErrorAttribution] = None,
        boundary: Optional[WarrantyBoundary] = None,
    ) -> "LiabilityReport":
        """Build a LiabilityReport from a chain + optional error.

        See spec R3.2 for validation rules.
        """
        if not isinstance(trace_id, str) or not trace_id:
            raise ValueError("trace_id must be a non-empty string")
        if not isinstance(generated_at, datetime):
            raise ValueError("generated_at must be a datetime")
        if generated_at.tzinfo is None or generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")

        chain_tuple: tuple[ProvenanceStage, ...] = tuple(chain)
        if not chain_tuple:
            raise ValueError("chain must be non-empty")

        if error is not None:
            matches = [s for s in chain_tuple if s.stage == error.stage]
            if not matches:
                raise ValueError(
                    f"attribution references unknown stage: {error.stage!r}"
                )
            if len(matches) > 1:
                raise ValueError(
                    f"attribution stage {error.stage!r} appears more than once"
                )

        bound = boundary or WarrantyBoundary()

        stage_classifications: list[StageClassification] = []
        for s in chain_tuple:
            classification = bound.classify(s.module)
            is_failing = (error is not None) and (s.stage == error.stage)
            stage_classifications.append(
                StageClassification(
                    stage=s,
                    classification=classification,
                    is_failing=is_failing,
                )
            )

        overall = _compute_overall_warranty(
            stage_classifications=tuple(stage_classifications),
            chain_verified=chain_verified,
            has_error=error is not None,
        )

        summary = _build_summary(
            stage_classifications=tuple(stage_classifications),
            error=error,
        )

        return cls(
            trace_id=trace_id,
            generated_at=generated_at,
            chain=chain_tuple,
            chain_verified=chain_verified,
            stage_classifications=tuple(stage_classifications),
            overall_warranty=overall,
            error_attribution=error,
            summary=summary,
        )

    # ---------------------------------------------------------------------
    # Public API (spec R3.3-R3.6)
    # ---------------------------------------------------------------------

    def is_clean(self) -> bool:
        """Fail-closed cleanliness gate (spec R3.6).

        True iff `chain_verified` AND no error AND
        `overall_warranty != unknown`. `best_effort` IS clean —
        callers SHOULD surface the warranty level to end users.
        """
        return (
            self.chain_verified
            and self.error_attribution is None
            and self.overall_warranty is not WarrantyCategory.unknown
        )

    def to_canonical_json(self) -> str:
        """Canonical JSON (key-sorted, compact, deterministic)."""
        dumped = self.model_dump(mode="json", exclude_none=False)
        return _canonical_json(dumped)

    def sha256_digest(self) -> str:
        """SHA-256 hex of `to_canonical_json()`."""
        return hashlib.sha256(
            self.to_canonical_json().encode("utf-8")
        ).hexdigest()


# =============================================================================
# Helpers
# =============================================================================


def _compute_overall_warranty(
    *,
    stage_classifications: tuple[StageClassification, ...],
    chain_verified: bool,
    has_error: bool,
) -> WarrantyCategory:
    """Overall warranty precedence ladder (spec R3.7).

    First match wins:
    1. chain_verified == False        -> unknown
    2. any stage classified unknown   -> unknown
    3. has_error                      -> max(max(stage rank), best_effort)
    4. else                           -> max(stage rank)
    """
    if not chain_verified:
        return WarrantyCategory.unknown

    max_rank = max(
        sc.classification.category.ordered_rank()
        for sc in stage_classifications
    )
    if max_rank == WarrantyCategory.unknown.ordered_rank():
        return WarrantyCategory.unknown

    if has_error:
        if max_rank < WarrantyCategory.best_effort.ordered_rank():
            max_rank = WarrantyCategory.best_effort.ordered_rank()

    return _rank_to_category(max_rank)


_RANK_TO_CATEGORY: dict[int, WarrantyCategory] = {
    0: WarrantyCategory.warranted,
    1: WarrantyCategory.best_effort,
    2: WarrantyCategory.unknown,
}


def _rank_to_category(rank: int) -> WarrantyCategory:
    return _RANK_TO_CATEGORY[rank]


def _build_summary(
    *,
    stage_classifications: tuple[StageClassification, ...],
    error: Optional[ErrorAttribution],
) -> LiabilitySummary:
    warranted = sum(
        1
        for sc in stage_classifications
        if sc.classification.category is WarrantyCategory.warranted
    )
    best_effort = sum(
        1
        for sc in stage_classifications
        if sc.classification.category is WarrantyCategory.best_effort
    )
    unknown = sum(
        1
        for sc in stage_classifications
        if sc.classification.category is WarrantyCategory.unknown
    )
    return LiabilitySummary(
        stage_count=len(stage_classifications),
        warranted_count=warranted,
        best_effort_count=best_effort,
        unknown_count=unknown,
        failing_stage=error.stage if error is not None else None,
        failing_module=error.module if error is not None else None,
        failing_category=error.category if error is not None else None,
    )
