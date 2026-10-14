"""
Pydantic v2 models for M2/M4 policy input/output.

PolicyInput / PolicyOutput — authority evaluation (M2).
MnpiFilterInput / MnpiFilterOutput — MNPI field filtering (M4).

All models align with:
  - schemas/canonical/compliance-check.json
  - schemas/canonical/audit-entry.json
  - M1 AIDClaims (consumed via REST, not imported)
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────


class AuthorityDecision(str, Enum):
    """Policy evaluation outcomes — matches compliance-check.json."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"


class Archetype(str, Enum):
    """5 enterprise archetypes from ARCH-09."""

    tier1_investment_bank = "tier1_investment_bank"
    tier2_asset_manager = "tier2_asset_manager"
    tier3_broker_dealer = "tier3_broker_dealer"
    tier4_independent_ria = "tier4_independent_ria"
    tier5_hedge_fund = "tier5_hedge_fund"


class Role(str, Enum):
    """Operational roles — human + agent specialist roles."""

    advisor = "advisor"
    compliance_officer = "compliance_officer"
    principal = "principal"
    portfolio_manager = "portfolio_manager"
    analyst = "analyst"
    operations = "operations"
    admin = "admin"
    agent_supervisor = "agent_supervisor"
    agent_research = "agent_research"
    agent_client_service = "agent_client_service"
    agent_execution = "agent_execution"
    agent_onboarding = "agent_onboarding"
    agent_compliance = "agent_compliance"



# ── Identity Context (AID claims subset for policy eval) ────────


class IdentityContext(BaseModel):
    """AID claims relevant to policy evaluation. Received via REST from M1."""

    actor_type: str = Field(..., description="human | agent | system")
    archetype: Archetype
    role: Role
    firm_id: str
    jurisdiction: str = "US"
    authority_scope: list[str] = Field(default_factory=list)
    authority_excludes: list[str] = Field(default_factory=list)
    client_scope: list[str] = Field(default_factory=list)
    pod_id: Optional[str] = None
    lei: Optional[str] = None
    crd_number: Optional[str] = None


# ── M2 Authority Models ─────────────────────────────────────────


class PolicyInput(BaseModel):
    """
    Input to M2 authority evaluation.
    Evaluates: (identity, action, target, context) -> ALLOW/DENY/ESCALATE.
    """

    identity: IdentityContext
    action: str = Field(
        ...,
        min_length=1,
        description="Action requested: e.g. 'client.read', 'order.submit'",
    )
    target_type: Optional[str] = Field(
        None, description="Entity type: client, account, security, order"
    )
    target_id: Optional[str] = Field(None, description="Canonical ID of target entity")
    context: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional context: client_id, security_id, amount, etc.",
    )


class PolicyOutput(BaseModel):
    """
    Output from M2 authority evaluation.
    Matches compliance-check.json schema.
    """

    decision: AuthorityDecision
    reason: str
    rule_applied: str = Field(
        ..., description="OPA rule path: e.g. authority/main.rego:check_authority"
    )
    wsp_section: str = Field(
        ..., description="WSP section reference (steering rule 19)"
    )
    policy_bundle_version: str = "authority/v0.1.0"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: Optional[dict[str, Any]] = None


# ── M4 MNPI Filter Models ───────────────────────────────────────


class MnpiFilterInput(BaseModel):
    """
    Input to M4 MNPI field filtering.
    Filters data payload based on archetype, role, and jurisdiction.
    """

    data_payload: dict[str, Any] = Field(
        ..., description="Raw data to be filtered (canonical type fields)"
    )
    archetype: Archetype
    role: Role
    jurisdiction: str = "US"
    client_scope: list[str] = Field(
        default_factory=list,
        description="Client IDs this actor can access (empty = all for admin)",
    )
    pod_id: Optional[str] = Field(
        None, description="Pod ID for Tier 5 HF pod isolation"
    )
    target_client_id: Optional[str] = Field(
        None, description="Client ID of the data subject"
    )
    target_pod_id: Optional[str] = Field(
        None, description="Pod ID of the data being accessed"
    )

    @field_validator("data_payload")
    @classmethod
    def payload_not_empty(cls, v: dict) -> dict:
        if not v:
            raise ValueError("data_payload must not be empty")
        return v


class FieldFilterEntry(BaseModel):
    """Record of a single field that was stripped."""

    field_path: str
    original_value: Optional[str] = Field(
        None, description="Hashed or redacted original value for filter log"
    )
    mnpi_category: str = Field(
        ..., description="pii | position_size | position_value | cross_pod"
    )


class MnpiFilterOutput(BaseModel):
    """
    Output from M4 MNPI filtering.
    Contains filtered payload + filter log for audit.
    MNPI filter log is REQUIRED for regulatory compliance.
    """

    filtered_payload: dict[str, Any] = Field(
        ..., description="Data with MNPI fields stripped"
    )
    fields_removed: list[str] = Field(
        default_factory=list, description="List of field paths removed"
    )
    filter_log: list[FieldFilterEntry] = Field(
        default_factory=list,
        description="Detailed filter log — REQUIRED for regulatory compliance",
    )
    rule_applied: str = Field(
        ..., description="OPA rule path: e.g. mnpi/main.rego:filter_fields"
    )
    wsp_section: str = Field(
        ..., description="WSP section reference (steering rule 19)"
    )
    policy_bundle_version: str = "mnpi/v0.1.0"
    evaluated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Bundle Info ──────────────────────────────────────────────────


class BundleInfo(BaseModel):
    """Information about a loaded OPA policy bundle."""

    name: str
    version: str
    path: str
    rule_count: int = 0
    last_updated: Optional[datetime] = None


class BundleListResponse(BaseModel):
    """Response for GET /policy/bundles."""

    bundles: list[BundleInfo]


# ── Health Check ─────────────────────────────────────────────────


class HealthResponse(BaseModel):
    """Response for GET /health."""

    status: str = Field(..., description="healthy | degraded | unhealthy")
    opa_reachable: bool
    module: str = "m2-m4-policy-engine"
    version: str = "0.1.0"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
