"""
Gap 1 — Document models + canonical JSON + PII scrubber.

See .kiro/specs/gap1-reg-bi-doc-generator.md R1, R5, R6.

Security:
    - ``_scrub_pii`` uses the same 4 patterns as Gap 2 + Gap 6.
    - ``_PII_PATTERNS`` is the SINGLE source of truth: ``mnpi_preflight.py``
      imports from here (R4b.2 / F6).
    - ``REDACTION_TOKEN`` is the single module-level constant used by
      all scrub callsites.
    - ``GenerationInput.reason_trace`` is scrubbed AT construction; cap
      applies POST-scrub.

v3 delta over v2:
    - ``DOCUMENT_SCHEMA_VERSION`` bumped 1.0.0 → 1.1.0.
    - ``ProductType`` enum added for OPA matrix overlays.
    - ``GenerationInput`` adds ``principal_review_config`` + ``product_type``.
    - ``RegBiDocument`` adds 8 new fields
      (``canonical_disclosures``, ``matched_rules``,
      ``matched_wsp_sections``, ``required_disclosures``, ``is_retail``,
      ``narrative_model_configured``, ``any_mnpi_preflight_failed``,
      ``rendered_content_sha256``).
    - ``RegBiDocument.with_rendered_hash()`` for immutable copy-with-update.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from m1_identity import AidClaims
from m3_schema_registry import Client, Order, ResearchBrief
from m5_config_loader import (
    PrincipalReviewConfig,
    RegBiConfig,
    RegistrationType,
)

from compliance.gap1_reg_bi_doc_generator._types import (
    ApplicabilityResult,
    ObligationCode,
    TriggerEventType,
)

# =============================================================================
# PII scrubber (R5.2)
# =============================================================================

REDACTION_TOKEN = "[REDACTED]"
DOCUMENT_SCHEMA_VERSION = "1.1.0"

#: Single source of truth for PII patterns. Imported by
#: ``mnpi_preflight.py`` to keep the two scanners in sync (R4b.2 / F6).
_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account", re.compile(r"\b\d{12,}\b")),
    (
        "email",
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    ),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
)


def _scrub_pii(text: str) -> str:
    """Deterministic, idempotent PII redaction."""
    for _, pat in _PII_PATTERNS:
        text = pat.sub(REDACTION_TOKEN, text)
    return text


def _has_pii(text: str) -> bool:
    """True iff any of the 4 PII patterns would match."""
    for _, pat in _PII_PATTERNS:
        if pat.search(text):
            return True
    return False


# =============================================================================
# ProductType (R1.2)
# =============================================================================


class ProductType(str, Enum):
    """Product-type enum used by the OPA required-sections matrix."""

    mutual_fund = "mutual_fund"
    etf = "etf"
    equity = "equity"
    option = "option"
    annuity = "annuity"
    private = "private"


# =============================================================================
# Canonical JSON helpers (R6.2)
# =============================================================================


def _json_default(obj: Any) -> Any:
    """Mirror Gap 2 ``_json_default`` — cross-gap serialization contract."""
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
    if isinstance(obj, frozenset):
        return sorted(obj)
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")


def _canonical_json(data: Any) -> str:
    return json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )


# =============================================================================
# GenerationInput (R1.2)
# =============================================================================


class GenerationInput(BaseModel):
    """Frozen input envelope for Reg BI generation."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=False
    )

    trigger: TriggerEventType
    trace_id: str = Field(min_length=1, max_length=200)
    generated_at: datetime
    client: Client
    advisor: AidClaims
    research_brief: Optional[ResearchBrief] = None
    order: Optional[Order] = None
    reason_trace: tuple[str, ...] = Field(default_factory=tuple)
    config: RegBiConfig
    principal_review_config: Optional[PrincipalReviewConfig] = None
    product_type: Optional[ProductType] = None

    @field_validator("generated_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("reason_trace")
    @classmethod
    def _scrub_and_cap_reason_trace(
        cls, v: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(v) > 50:
            raise ValueError("reason_trace exceeds 50-entry cap")
        scrubbed: list[str] = []
        for entry in v:
            if not isinstance(entry, str):
                raise ValueError("reason_trace entries must be strings")
            cleaned = _scrub_pii(entry)
            if len(cleaned) > 500:
                raise ValueError(
                    "reason_trace entry exceeds 500-char cap post-scrub"
                )
            scrubbed.append(cleaned)
        return tuple(scrubbed)

    @model_validator(mode="after")
    def _require_research_or_order(self) -> "GenerationInput":
        if self.research_brief is None and self.order is None:
            raise ValueError(
                "at least one of research_brief / order required"
            )
        return self


# =============================================================================
# GenerationSkipped (R7.2)
# =============================================================================


class GenerationSkipped(BaseModel):
    """Returned when applicability evaluates to a SKIP_* outcome."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    reason: ApplicabilityResult
    trace_id: str = Field(min_length=1, max_length=200)
    trigger: TriggerEventType

    @field_validator("reason")
    @classmethod
    def _reject_applicable(
        cls, v: ApplicabilityResult
    ) -> ApplicabilityResult:
        if v is ApplicabilityResult.APPLICABLE:
            raise ValueError(
                "GenerationSkipped.reason must be a SKIP_* value"
            )
        return v


# =============================================================================
# RegBiSection (R3a)
# =============================================================================


class RegBiSection(BaseModel):
    """One of the four Reg BI obligations, populated deterministically."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    obligation_code: ObligationCode
    bullets: tuple[str, ...] = Field(min_length=1, max_length=20)
    narrative: str = Field(default="", max_length=2000)
    populated_by: str = Field(min_length=1, max_length=200)
    force_review: bool = False

    @field_validator("bullets")
    @classmethod
    def _bullets_shape(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        for b in v:
            if not isinstance(b, str):
                raise ValueError("bullet must be a string")
            if not (1 <= len(b) <= 500):
                raise ValueError(
                    "bullet length must be 1..500 chars"
                )
        return v


# =============================================================================
# RegBiDocument (R6)
# =============================================================================


class RegBiDocument(BaseModel):
    """Deterministic Reg BI Recommendation Disclosure document."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    # ----- v2 fields (all retained) -----
    document_schema_version: Literal["1.1.0"] = DOCUMENT_SCHEMA_VERSION
    document_id: UUID
    trace_id: str = Field(min_length=1, max_length=200)
    generated_at: datetime
    trigger: TriggerEventType
    client_ref: UUID
    advisor_sub: str = Field(min_length=1, max_length=128)
    firm_id: str = Field(min_length=1, max_length=128)
    registration_type: RegistrationType
    disclosure: RegBiSection
    care: RegBiSection
    coi: RegBiSection
    compliance: RegBiSection
    advisor_review_required: bool
    llm_narrative_failed: bool = False
    reason_trace_redacted: tuple[str, ...] = Field(default_factory=tuple)
    research_brief_ref: Optional[UUID] = None
    order_ref: Optional[UUID] = None
    liability_report_sha256: Optional[str] = None

    # ----- v3 additions -----
    #: ``CanonicalDisclosures`` duck-typed to avoid import cycle; the
    #: concrete type is imported at module scope by the generator and
    #: round-trips via ``model_dump``.
    canonical_disclosures: "CanonicalDisclosures"  # type: ignore[name-defined]
    matched_rules: tuple[str, ...] = Field(default_factory=tuple)
    matched_wsp_sections: tuple[str, ...] = Field(default_factory=tuple)
    required_disclosures: tuple[str, ...] = Field(default_factory=tuple)
    is_retail: bool = False
    narrative_model_configured: str = Field(min_length=1, max_length=60)
    any_mnpi_preflight_failed: bool = False
    rendered_content_sha256: Optional[str] = None

    @field_validator("generated_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return v.astimezone(timezone.utc)

    @field_validator("disclosure")
    @classmethod
    def _check_disclosure_code(cls, v: RegBiSection) -> RegBiSection:
        if v.obligation_code is not ObligationCode.DISCLOSURE:
            raise ValueError("disclosure slot must hold DISCLOSURE section")
        return v

    @field_validator("care")
    @classmethod
    def _check_care_code(cls, v: RegBiSection) -> RegBiSection:
        if v.obligation_code is not ObligationCode.CARE:
            raise ValueError("care slot must hold CARE section")
        return v

    @field_validator("coi")
    @classmethod
    def _check_coi_code(cls, v: RegBiSection) -> RegBiSection:
        if v.obligation_code is not ObligationCode.COI:
            raise ValueError("coi slot must hold COI section")
        return v

    @field_validator("compliance")
    @classmethod
    def _check_compliance_code(cls, v: RegBiSection) -> RegBiSection:
        if v.obligation_code is not ObligationCode.COMPLIANCE:
            raise ValueError(
                "compliance slot must hold COMPLIANCE section"
            )
        return v

    @field_validator("rendered_content_sha256")
    @classmethod
    def _validate_rendered_hash(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if len(v) != 64 or not re.fullmatch(r"[0-9a-f]{64}", v):
            raise ValueError(
                "rendered_content_sha256 must be 64 lowercase hex chars"
            )
        return v

    # ---------------------------------------------------------------------
    # Copy-with-update (R7.3 step 10)
    # ---------------------------------------------------------------------

    def with_rendered_hash(self, content_sha256: str) -> "RegBiDocument":
        """Return an immutable copy with ``rendered_content_sha256`` set."""
        return self.model_copy(
            update={"rendered_content_sha256": content_sha256}
        )

    # ---------------------------------------------------------------------
    # Serialization (R6.2 / R6.3)
    # ---------------------------------------------------------------------

    def to_canonical_json(self) -> str:
        """Canonical JSON: sorted keys, compact, deterministic."""
        dumped = self.model_dump(mode="json", exclude_none=False)
        return _canonical_json(dumped)

    def sha256_digest(self) -> str:
        """SHA-256 hex of ``to_canonical_json()``."""
        return hashlib.sha256(
            self.to_canonical_json().encode("utf-8")
        ).hexdigest()


# =============================================================================
# Resolve forward references
# =============================================================================

# Rebuild RegBiDocument with CanonicalDisclosures resolved. Imported at
# the bottom to break the document ↔ disclosures module cycle.
from compliance.gap1_reg_bi_doc_generator.disclosures import (  # noqa: E402
    CanonicalDisclosures,
)

RegBiDocument.model_rebuild()
