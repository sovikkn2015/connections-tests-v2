"""
Gap 3: WSP-to-YAML Mapping — Pydantic v2 Models.

Bidirectional cross-reference between human-readable WSP sections
and OPA/Rego rules. Version synchronization, change audit trail,
FINRA examination report generation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class SyncStatus(str, Enum):
    IN_SYNC = "IN_SYNC"
    PENDING_REVIEW = "PENDING_REVIEW"
    OUT_OF_SYNC = "OUT_OF_SYNC"


class ChangeType(str, Enum):
    WSP_UPDATE = "wsp_update"
    REGO_UPDATE = "rego_update"
    MAPPING_CREATE = "mapping_create"
    MAPPING_UPDATE = "mapping_update"
    REVIEW_COMPLETE = "review_complete"


class EnforcementType(str, Enum):
    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"


# ── Core Mapping Entry ───────────────────────────────────────────


class WSPMapping(BaseModel):
    """Single mapping between a WSP section and an OPA/Rego rule."""
    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    wsp_section: str = Field(..., description="WSP section number, e.g. '4.2'")
    wsp_title: str = Field(..., description="Human-readable title")
    wsp_text: str = Field("", description="Full WSP section text")
    opa_bundle: str = Field(..., description="OPA bundle name, e.g. 'authority'")
    rego_file: str = Field(..., description="Rego file path, e.g. 'authority/main.rego'")
    rego_rule: str = Field(..., description="Rule name, e.g. 'check_authority'")
    enforcement_type: EnforcementType = EnforcementType.DETERMINISTIC
    test_cases: list[str] = Field(default_factory=list)
    evidence_query: str = Field("", description="SQL/query to retrieve enforcement evidence")
    last_wsp_review: Optional[datetime] = None
    last_rego_review: Optional[datetime] = None
    reviewer: str = ""
    sync_status: SyncStatus = SyncStatus.IN_SYNC
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Change Audit Trail ───────────────────────────────────────────


class MappingChange(BaseModel):
    """Audit trail entry for any mapping change."""
    change_id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    changed_by: str
    change_type: ChangeType
    wsp_section: str
    linked_rego_rules: list[str] = Field(default_factory=list)
    reason: str = ""
    review_status: SyncStatus = SyncStatus.PENDING_REVIEW
    git_commit: str = ""


# ── FINRA Report Models ─────────────────────────────────────────


class WSPCoverageEntry(BaseModel):
    """Per-WSP-section detail in FINRA report."""
    wsp_section: str
    wsp_title: str
    sync_status: SyncStatus
    opa_rule: str
    enforcement_type: EnforcementType
    last_wsp_review: Optional[datetime] = None
    last_rego_review: Optional[datetime] = None
    test_cases_count: int = 0
    test_cases_passing: int = 0
    enforcement_count_30d: int = 0
    deny_count_30d: int = 0
    allow_count_30d: int = 0
    bypass_count: int = 0


class FINRAExaminationReport(BaseModel):
    """Complete FINRA examination report."""
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    firm_id: str
    firm_name: str = ""
    total_wsp_sections: int = 0
    total_opa_rules: int = 0
    total_mappings: int = 0
    mappings_in_sync: int = 0
    mappings_pending_review: int = 0
    sync_percentage: float = 0.0
    coverage_details: list[WSPCoverageEntry] = Field(default_factory=list)
    change_history: list[MappingChange] = Field(default_factory=list)


# ── Annotation Validation ────────────────────────────────────────


class RegoAnnotationResult(BaseModel):
    """Result of validating wsp_section annotations in Rego files."""
    file_path: str
    rule_name: str
    has_wsp_section: bool
    wsp_section_value: str = ""
    line_number: int = 0


class AnnotationValidationReport(BaseModel):
    """CI validation report for wsp_section annotations."""
    total_rules: int = 0
    rules_with_annotation: int = 0
    rules_missing_annotation: int = 0
    results: list[RegoAnnotationResult] = Field(default_factory=list)
    passed: bool = True
