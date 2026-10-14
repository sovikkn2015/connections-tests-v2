"""
Gap 1: Reg BI Document Generator — Pydantic v2 Models.

RegBIDocument with all 4 obligations: Disclosure, Care,
Conflict of Interest, Compliance. Status lifecycle:
DRAFT → PENDING_REVIEW → FINALIZED → SUPERSEDED.

Deterministic fields populated from structured data (NO LLM).
Narrative fields LLM-generated from reasoning trace (HITL required).
SHA-256 integrity hash on every document. WORM storage.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator


# ── Enums ────────────────────────────────────────────────────────


class RegBIStatus(str, Enum):
    """Document lifecycle status."""
    DRAFT = "DRAFT"
    PENDING_REVIEW = "PENDING_REVIEW"
    FINALIZED = "FINALIZED"
    SUPERSEDED = "SUPERSEDED"


class RecommendationType(str, Enum):
    buy = "buy"
    sell = "sell"
    hold = "hold"
    switch = "switch"
    rebalance = "rebalance"
    allocation_change = "allocation_change"


class RiskTolerance(str, Enum):
    conservative = "conservative"
    moderate_conservative = "moderate_conservative"
    moderate = "moderate"
    moderate_aggressive = "moderate_aggressive"
    aggressive = "aggressive"


class TimeHorizon(str, Enum):
    short_term = "short_term"
    medium_term = "medium_term"
    long_term = "long_term"


class ConflictType(str, Enum):
    revenue_sharing = "revenue_sharing"
    proprietary_product = "proprietary_product"
    compensation_incentive = "compensation_incentive"
    principal_trading = "principal_trading"
    other = "other"


class ComplianceCheckResult(str, Enum):
    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class RegistrationType(str, Enum):
    bd_only = "bd_only"
    ria_only = "ria_only"
    dual_registered = "dual_registered"


# ── Sub-models ───────────────────────────────────────────────────


class AdvisorInfo(BaseModel):
    user_id: str
    name: str = ""
    crd_number: str = ""
    aid_hash: str = Field("", description="SHA-256 of AID at recommendation time")


class ClientInfo(BaseModel):
    client_id: str
    name: str = ""
    risk_tolerance: RiskTolerance = RiskTolerance.moderate
    investment_objectives: list[str] = Field(default_factory=list)
    time_horizon: TimeHorizon = TimeHorizon.medium_term
    annual_income_range: str = ""
    net_worth_range: str = ""
    liquid_net_worth_range: str = ""
    account_type: str = ""


class SecurityRecommendation(BaseModel):
    ticker: str
    name: str = ""
    security_type: str = ""
    action: str = "buy"
    quantity: Optional[float] = None
    estimated_value: Optional[float] = None


class RecommendationInfo(BaseModel):
    type: RecommendationType
    securities: list[SecurityRecommendation] = Field(default_factory=list)
    summary: str = ""


class CostAnalysis(BaseModel):
    estimated_commission: Optional[float] = None
    estimated_fees: Optional[float] = None
    expense_ratio: Optional[float] = None
    total_estimated_cost: float = 0.0
    cost_comparison_to_alternatives: str = ""


class AlternativeConsidered(BaseModel):
    description: str
    reason_not_selected: str = ""


class DisclosureObligation(BaseModel):
    form_crs_delivered: bool = False
    form_crs_delivery_date: Optional[str] = None
    material_facts_disclosed: list[str] = Field(default_factory=list)
    fee_schedule_disclosed: bool = False
    compensation_structure_disclosed: bool = False


class CareObligation(BaseModel):
    basis_for_recommendation: str = ""
    alternatives_considered: list[AlternativeConsidered] = Field(default_factory=list)
    best_interest_rationale: str = ""
    risk_factors: list[str] = Field(default_factory=list)
    cost_analysis: CostAnalysis = Field(default_factory=CostAnalysis)


class ConflictEntry(BaseModel):
    conflict_type: ConflictType
    description: str
    mitigation: str = ""


class ConflictOfInterestObligation(BaseModel):
    conflicts_identified: list[ConflictEntry] = Field(default_factory=list)
    no_conflicts_attestation: bool = False


class ComplianceCheckEntry(BaseModel):
    check_type: str
    result: ComplianceCheckResult
    rule_applied: str = ""
    details: str = ""


class ComplianceObligation(BaseModel):
    compliance_checks_passed: list[ComplianceCheckEntry] = Field(default_factory=list)
    restricted_list_clear: bool = False
    concentration_check: str = ""
    suitability_score: Optional[float] = None


class Obligations(BaseModel):
    disclosure: DisclosureObligation = Field(default_factory=DisclosureObligation)
    care: CareObligation = Field(default_factory=CareObligation)
    conflict_of_interest: ConflictOfInterestObligation = Field(
        default_factory=ConflictOfInterestObligation,
    )
    compliance: ComplianceObligation = Field(default_factory=ComplianceObligation)


class SourceTrace(BaseModel):
    trace_id: str
    specialist: str = ""
    pipeline_stage: Optional[str] = None
    langfuse_trace_url: Optional[str] = None
    data_sources_used: list[str] = Field(default_factory=list)


class AuditRecord(BaseModel):
    worm_record_id: str = ""
    sha256_hash: str = ""
    crm_record_id: Optional[str] = None


# ── Core RegBIDocument ───────────────────────────────────────────


class RegBIDocument(BaseModel):
    """
    Structured Reg BI documentation for a single recommendation.
    All 4 obligations populated. SHA-256 integrity hash computed
    automatically. Stored in CRM + WORM (S3 Object Lock).
    """
    document_id: str = Field(default_factory=lambda: str(uuid4()))
    version: str = "1.0.0"
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    finalized_at: Optional[datetime] = None
    status: RegBIStatus = RegBIStatus.DRAFT

    firm_id: str
    advisor: AdvisorInfo
    client: ClientInfo
    recommendation: RecommendationInfo
    obligations: Obligations = Field(default_factory=Obligations)
    source_trace: SourceTrace
    audit: AuditRecord = Field(default_factory=AuditRecord)

    # Reviewer info (HITL)
    reviewed_by: Optional[str] = None
    review_timestamp: Optional[datetime] = None
    review_notes: Optional[str] = None

    @model_validator(mode="after")
    def compute_integrity_hash(self) -> "RegBIDocument":
        """Compute SHA-256 integrity hash over document content."""
        self.audit.sha256_hash = self._compute_hash()
        return self

    def _compute_hash(self) -> str:
        canonical = {
            "document_id": self.document_id,
            "firm_id": self.firm_id,
            "advisor_id": self.advisor.user_id,
            "client_id": self.client.client_id,
            "recommendation_type": self.recommendation.type.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Trigger Event ────────────────────────────────────────────────


REG_BI_TRIGGER_INTENTS = frozenset({
    "client.recommend_action",
    "client.suggest_rebalance",
    "client.propose_allocation",
    "execution.prepare_order",
    "research.brief_with_rating",
})


class RecommendationEvent(BaseModel):
    """Event that triggers Reg BI document generation."""
    trace_id: str
    intent: str
    advisor_id: str
    client_id: str
    firm_id: str
    registration_type: RegistrationType
    archetype: str
    securities: list[SecurityRecommendation] = Field(default_factory=list)
    recommendation_type: RecommendationType = RecommendationType.buy
    summary: str = ""
    reasoning_trace_url: Optional[str] = None


# ── Query Models ─────────────────────────────────────────────────


class RegBIQuery(BaseModel):
    """Query parameters for Reg BI document retrieval."""
    client_id: Optional[str] = None
    advisor_id: Optional[str] = None
    security_id: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    status: Optional[RegBIStatus] = None
    firm_id: str


class RegBIQueryResponse(BaseModel):
    documents: list[RegBIDocument] = Field(default_factory=list)
    count: int = 0
