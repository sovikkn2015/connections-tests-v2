"""
Onboarding Specialist — Pydantic v2 models for multi-session KYC workflow.

OnboardingState enum tracks the full workflow: INITIATED → COLLECTING_INFO →
KYC_PENDING → KYC_VERIFIED → SANCTIONS_SCREENING → SANCTIONS_CLEAR →
RISK_PROFILING → RISK_PROFILED → ACCOUNT_OPENING → DOCUSIGN_PENDING →
DOCUSIGN_SIGNED → COMPLIANCE_REVIEW → APPROVED.
Failure paths: REJECTED, ABANDONED.

HITL mandatory at COMPLIANCE_REVIEW stage.
Sanctions screening deterministic (not LLM).
Multi-session: sessions persist across days.
30-day abandonment timeout.

No cross-module imports. No credentials. No LLM for compliance.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class OnboardingState(str, Enum):
    """Client onboarding workflow states."""

    INITIATED = "INITIATED"
    COLLECTING_INFO = "COLLECTING_INFO"
    KYC_PENDING = "KYC_PENDING"
    KYC_VERIFIED = "KYC_VERIFIED"
    SANCTIONS_SCREENING = "SANCTIONS_SCREENING"
    SANCTIONS_CLEAR = "SANCTIONS_CLEAR"
    RISK_PROFILING = "RISK_PROFILING"
    RISK_PROFILED = "RISK_PROFILED"
    ACCOUNT_OPENING = "ACCOUNT_OPENING"
    DOCUSIGN_PENDING = "DOCUSIGN_PENDING"
    DOCUSIGN_SIGNED = "DOCUSIGN_SIGNED"
    COMPLIANCE_REVIEW = "COMPLIANCE_REVIEW"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    ABANDONED = "ABANDONED"


# ── Request / Data Models ────────────────────────────────────────


class OnboardingRequest(BaseModel):
    """Request to start a new onboarding session."""

    client_name: str = Field(..., min_length=1, description="Client full name")
    client_type: str = Field(default="individual", description="individual or entity")
    advisor_id: str = Field(..., min_length=1, description="Assigned advisor ID")
    firm_id: str = Field(..., min_length=1, description="Firm identifier")
    jurisdiction: str = Field(default="US", description="Regulatory jurisdiction")


class KYCResult(BaseModel):
    """KYC verification result. Deterministic — no LLM."""

    kyc_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique KYC check ID")
    verified: bool = Field(..., description="Whether KYC passed")
    verification_method: str = Field(default="document_review", description="How KYC was verified")
    reason: Optional[str] = Field(default=None, description="Reason for failure")
    verified_at: str = Field(..., description="ISO 8601 timestamp")
    document_hash: Optional[str] = Field(default=None, description="SHA-256 hash of submitted documents")


class SanctionsResult(BaseModel):
    """Sanctions screening result. Deterministic — no LLM (Rule 14)."""

    screening_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique screening ID")
    clear: bool = Field(..., description="Whether sanctions screening passed")
    lists_checked: list[str] = Field(
        default_factory=lambda: ["OFAC_SDN", "OFAC_CONSOLIDATED", "UN_SANCTIONS", "EU_SANCTIONS"],
        description="Sanctions lists checked",
    )
    hits: list[str] = Field(default_factory=list, description="Any sanctions hits found")
    screened_at: str = Field(..., description="ISO 8601 timestamp")


class RiskProfile(BaseModel):
    """Client risk profile. Deterministic scoring."""

    risk_score: int = Field(..., ge=1, le=100, description="Risk score 1-100")
    risk_category: str = Field(..., description="low, medium, high, prohibited")
    factors: list[str] = Field(default_factory=list, description="Risk factors identified")
    profiled_at: str = Field(..., description="ISO 8601 timestamp")


class ComplianceReview(BaseModel):
    """HITL compliance review record."""

    reviewer_id: str = Field(..., min_length=1, description="Who reviewed")
    approved: bool = Field(..., description="Whether compliance approved")
    approval_token: Optional[str] = Field(default=None, description="SHA-256 approval token")
    reason: Optional[str] = Field(default=None, description="Reason for rejection")
    reviewed_at: str = Field(..., description="ISO 8601 timestamp")


class OnboardingSession(BaseModel):
    """Full onboarding session with workflow state. Persists across days."""

    session_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique session ID")
    client_name: str = Field(..., description="Client full name")
    client_type: str = Field(default="individual", description="individual or entity")
    advisor_id: str = Field(..., description="Assigned advisor ID")
    firm_id: str = Field(..., description="Firm identifier")
    jurisdiction: str = Field(default="US", description="Regulatory jurisdiction")
    state: OnboardingState = Field(default=OnboardingState.INITIATED, description="Current workflow state")
    kyc_result: Optional[KYCResult] = Field(default=None, description="KYC verification result")
    sanctions_result: Optional[SanctionsResult] = Field(default=None, description="Sanctions screening result")
    risk_profile: Optional[RiskProfile] = Field(default=None, description="Client risk profile")
    compliance_review: Optional[ComplianceReview] = Field(default=None, description="HITL compliance review")
    client_info: Optional[dict] = Field(default=None, description="Collected client information")
    account_id: Optional[str] = Field(default=None, description="Opened account ID")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Session creation timestamp")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Last update timestamp")
    last_activity_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Last activity for abandonment check")
    trace_id: Optional[str] = Field(default=None, description="Links to M10 audit trail")
