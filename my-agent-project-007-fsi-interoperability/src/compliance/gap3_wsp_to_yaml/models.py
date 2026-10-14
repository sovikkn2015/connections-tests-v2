"""
Gap 3 — Pydantic v2 models.

WspSection (ingest), RuleAnchor (OPA address), WspMapping (join),
CoverageReport (CI output). All frozen, extra='forbid'. PII regex
applied to every free-text field.

See .kiro/specs/gap3-wsp-to-yaml.md R1-R4.
"""

from __future__ import annotations

import re
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

# =============================================================================
# Constants (spec R1.2)
# =============================================================================

SECTION_SCHEMA_VERSION: str = "1.0.0"

#: WSP section identifier regex. Coupled to M2's WSP_SECTION_RE (R1.2).
#: Coupling is enforced at construction: T3.3 asserts pattern-string
#: equality with m2_m4_policy_engine.WSP_SECTION_RE.
WSP_SECTION_RE: re.Pattern[str] = re.compile(r"^WSP-[A-Z]+-\d+(\.\d+)?$")

#: Rule identifier regex. Copied verbatim from M2 (R2.1).
#: Same coupling test pattern as WSP_SECTION_RE.
RULE_APPLIED_RE: re.Pattern[str] = re.compile(
    r"^(authority|mnpi)/[a-z_]+/[a-z_]+\.v\d+$"
)

#: Rego file path regex.
_REGO_FILE_RE: re.Pattern[str] = re.compile(r"^[a-z_][a-z_0-9/]*\.rego$")

# =============================================================================
# PII regex set (spec R5.1). Same set as Gap 2/6, duplicated locally
# so this module does not import from sibling gaps.
# =============================================================================

_PII_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("account_number", re.compile(r"\b\d{12,}\b")),
    ("email", re.compile(
        r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"
    )),
    ("iban", re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b")),
)


def _reject_pii(value: str, field_name: str) -> str:
    for code, pattern in _PII_PATTERNS:
        if pattern.search(value):
            raise ValueError(
                f"{field_name} contains potential PII pattern: {code}"
            )
    return value


# =============================================================================
# Enums (spec R1.3, R1.4)
# =============================================================================


class SupervisoryRole(str, Enum):
    """7 canonical supervisory roles (WSP author must use these exact
    values in escalation_path and supervisory_role fields)."""

    chief_compliance_officer = "chief_compliance_officer"
    compliance_officer = "compliance_officer"
    principal = "principal"
    registered_rep = "registered_rep"
    operations = "operations"
    cco_designee = "cco_designee"
    audit_committee = "audit_committee"


class SupervisoryFrequency(str, Enum):
    """7 cadences at which a WSP procedure is executed."""

    real_time = "real_time"
    intraday = "intraday"
    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    ad_hoc = "ad_hoc"


_VALID_ROLE_VALUES: frozenset[str] = frozenset(r.value for r in SupervisoryRole)


# =============================================================================
# WspSection (spec R1)
# =============================================================================


class WspSection(BaseModel):
    """One structured WSP procedure. Frozen, PII-filtered."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0.0"] = SECTION_SCHEMA_VERSION
    wsp_id: str = Field(min_length=1, max_length=40)
    section_id: str = Field(min_length=1, max_length=40)
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)
    supervisory_role: SupervisoryRole
    frequency: SupervisoryFrequency
    escalation_path: tuple[str, ...]
    last_reviewed: date | None = None

    @field_validator("section_id")
    @classmethod
    def _validate_section_id(cls, v: str) -> str:
        if not WSP_SECTION_RE.match(v):
            raise ValueError(
                f"section_id {v!r} does not match WSP_SECTION_RE"
            )
        return v

    @field_validator("title")
    @classmethod
    def _validate_title(cls, v: str) -> str:
        return _reject_pii(v, "title")

    @field_validator("body")
    @classmethod
    def _validate_body(cls, v: str) -> str:
        return _reject_pii(v, "body")

    @field_validator("escalation_path")
    @classmethod
    def _validate_escalation_path(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        if not isinstance(v, tuple):
            v = tuple(v)
        if len(v) < 1:
            raise ValueError("escalation_path must have at least 1 role")
        if len(v) > 10:
            raise ValueError("escalation_path must have at most 10 roles")
        for role in v:
            if role not in _VALID_ROLE_VALUES:
                raise ValueError(
                    f"escalation_path role {role!r} is not a valid "
                    f"SupervisoryRole value"
                )
        return v


# =============================================================================
# RuleAnchor (spec R2.1)
# =============================================================================


class RuleAnchor(BaseModel):
    """Machine-readable address of a single OPA/Rego rule."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rule_applied: str = Field(min_length=1, max_length=120)
    opa_bundle: str = Field(min_length=1, max_length=100)
    rego_file: str = Field(min_length=1, max_length=200)
    rego_rule: str = Field(min_length=1, max_length=80)

    @field_validator("rule_applied")
    @classmethod
    def _validate_rule_applied(cls, v: str) -> str:
        if not RULE_APPLIED_RE.match(v):
            raise ValueError(
                f"rule_applied {v!r} does not match RULE_APPLIED_RE"
            )
        return v

    @field_validator("rego_file")
    @classmethod
    def _validate_rego_file(cls, v: str) -> str:
        if not _REGO_FILE_RE.match(v):
            raise ValueError(
                f"rego_file {v!r} must be lowercase [a-z_0-9/]+ ending in .rego"
            )
        return v


# =============================================================================
# WspMapping (spec R2.2)
# =============================================================================


class WspMapping(BaseModel):
    """One WspSection plus its anchors (may be empty = coverage gap)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    wsp_section: WspSection
    rules: tuple[RuleAnchor, ...] = ()


# =============================================================================
# CoverageReport (spec R4.1)
# =============================================================================


class CoverageReport(BaseModel):
    """CI-blocking coverage report. Exit code drives the CLI."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    schema_version: Literal["1.0.0"] = "1.0.0"
    total_wsp_sections: int = Field(ge=0)
    total_rules: int = Field(ge=0)
    mapped_sections: int = Field(ge=0)
    unmapped_sections: tuple[str, ...] = ()
    orphan_rules: tuple[str, ...] = ()
    coverage_pct: float = Field(ge=0.0, le=100.0)
    orphan_pct: float = Field(ge=0.0, le=100.0)
    exit_code: int = Field(ge=0, le=2)

    @model_validator(mode="after")
    def _check_counts(self) -> "CoverageReport":
        if self.mapped_sections > self.total_wsp_sections:
            raise ValueError(
                "mapped_sections cannot exceed total_wsp_sections"
            )
        if len(self.unmapped_sections) > self.total_wsp_sections:
            raise ValueError(
                "unmapped_sections cannot exceed total_wsp_sections"
            )
        if len(self.orphan_rules) > self.total_rules:
            raise ValueError(
                "orphan_rules cannot exceed total_rules"
            )
        return self
