"""
M1 AID (Agent Identity Document) Pydantic v2 models.

The AID is a JWT RS256 token with FSI-specific claims. Every request
through M6 carries an AID. M2 checks authority_scope. M4 checks
archetype + role for MNPI filtering. M10 logs actor_id (AID hash).

5 archetypes matching ARCH-09:
  - tier1_investment_bank
  - tier2_asset_manager
  - tier3_broker_dealer
  - tier4_independent_ria
  - tier5_hedge_fund

Actor types: human, agent, system.
Agent actors MUST have explicit authority_scope (zero-scope not permitted).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, field_validator


# ── Enums ────────────────────────────────────────────────────────


class Archetype(str, Enum):
    """5 enterprise archetypes from ARCH-09 / consolidated design."""

    tier1_investment_bank = "tier1_investment_bank"
    tier2_asset_manager = "tier2_asset_manager"
    tier3_broker_dealer = "tier3_broker_dealer"
    tier4_independent_ria = "tier4_independent_ria"
    tier5_hedge_fund = "tier5_hedge_fund"


class Role(str, Enum):
    """
    Operational roles. Human roles + agent specialist roles.
    Agent roles map to the 5 specialists in ARCH-09.
    """

    # Human roles
    advisor = "advisor"
    compliance_officer = "compliance_officer"
    principal = "principal"
    portfolio_manager = "portfolio_manager"
    analyst = "analyst"
    operations = "operations"
    admin = "admin"
    # Agent specialist roles (ARCH-09: 5 specialists + supervisor)
    agent_supervisor = "agent_supervisor"
    agent_research = "agent_research"
    agent_client_service = "agent_client_service"
    agent_execution = "agent_execution"
    agent_onboarding = "agent_onboarding"
    agent_compliance = "agent_compliance"


class ActorType(str, Enum):
    """Human advisors, AI agent specialists, or system processes."""

    human = "human"
    agent = "agent"
    system = "system"


class AIDStatus(str, Enum):
    """AID lifecycle states."""

    active = "active"
    suspended = "suspended"
    revoked = "revoked"
    expired = "expired"


# ── AID Claims (embedded in JWT) ────────────────────────────────


class AIDClaims(BaseModel):
    """
    FSI-specific JWT claims for an Agent Identity Document.

    Standard JWT fields (iss, sub, exp, iat, jti) are handled by
    the JWT library. These are the CUSTOM claims that travel with
    every request through M6.

    M2 evaluates authority_scope + authority_excludes.
    M4 evaluates archetype + role for MNPI filtering.
    M10 logs the AID hash (never the raw AID) for privacy.
    """

    # Identity
    actor_type: ActorType = Field(..., description="human, agent, or system")
    display_name: str = Field(..., min_length=1, max_length=255)
    firm_id: str = Field(..., description="Canonical firm identifier")

    # FSI registration
    lei: Optional[str] = Field(
        None,
        pattern=r"^[A-Z0-9]{20}$",
        description="ISO 17442 Legal Entity Identifier",
    )
    crd_number: Optional[str] = Field(
        None,
        pattern=r"^\d{1,7}$",
        description="FINRA CRD number",
    )

    # Authorization context
    archetype: Archetype
    role: Role
    jurisdiction: str = Field(
        "US",
        pattern=r"^[A-Z]{2}(-[A-Z]{2,3})?$",
        description="Primary regulatory jurisdiction (ISO 3166-1 alpha-2)",
    )

    # Authority boundaries (M2 evaluates these via OPA)
    authority_scope: list[str] = Field(
        default_factory=list,
        description=(
            "Allowed action patterns: e.g. "
            "['client.read', 'portfolio.read', 'order.draft']"
        ),
    )
    authority_excludes: list[str] = Field(
        default_factory=list,
        description=(
            "Explicitly denied actions: e.g. "
            "['order.submit'] for read-only agents"
        ),
    )

    # Client scope (advisor sees own clients only — tier3/tier4)
    client_scope: list[str] = Field(
        default_factory=list,
        description=(
            "Canonical Client IDs this actor can access. "
            "Empty = all (admin/system only)."
        ),
    )

    # Pod isolation (Tier 5 hedge funds — Chinese wall enforcement)
    pod_id: Optional[str] = Field(
        None,
        description="Pod/strategy identifier for Chinese wall enforcement",
    )

    @field_validator("authority_scope")
    @classmethod
    def scope_not_empty_for_agents(cls, v: list[str], info) -> list[str]:
        """Agent actors MUST have explicit authority_scope. Zero-scope agents not permitted."""
        actor_type = info.data.get("actor_type")
        if actor_type == ActorType.agent and not v:
            raise ValueError(
                "Agent actors MUST have explicit authority_scope. "
                "Zero-scope agents are not permitted."
            )
        return v


# ── AID Record (stored in registry) ─────────────────────────────


class AIDRecord(BaseModel):
    """
    Full AID record stored in the identity registry.
    In-memory for dev/test, PostgreSQL in production.
    Includes lifecycle metadata not present in the JWT.
    """

    aid_id: str = Field(..., description="Unique AID identifier (JWT jti)")
    actor_type: ActorType
    display_name: str
    firm_id: str
    archetype: Archetype
    role: Role
    status: AIDStatus = AIDStatus.active
    claims: AIDClaims

    # Lifecycle
    issued_at: datetime
    expires_at: datetime
    revoked_at: Optional[datetime] = None
    revoked_by: Optional[str] = None
    revocation_reason: Optional[str] = None

    # Audit
    issued_by: str = Field(..., description="Who/what issued this AID")
    last_verified_at: Optional[datetime] = None
    verification_count: int = 0


# ── API request/response models ─────────────────────────────────


class IssueAIDRequest(BaseModel):
    """Request to issue a new AID."""

    actor_type: ActorType
    display_name: str = Field(..., min_length=1, max_length=255)
    firm_id: str
    lei: Optional[str] = None
    crd_number: Optional[str] = None
    archetype: Archetype
    role: Role
    jurisdiction: str = "US"
    authority_scope: list[str] = Field(default_factory=list)
    authority_excludes: list[str] = Field(default_factory=list)
    client_scope: list[str] = Field(default_factory=list)
    pod_id: Optional[str] = None
    ttl_hours: int = Field(
        8, ge=1, le=720, description="Token TTL in hours (default 8h)"
    )


class IssueAIDResponse(BaseModel):
    """Response after issuing a new AID."""

    aid_id: str
    token: str = Field(..., description="Signed JWT RS256 token")
    expires_at: datetime
    claims: AIDClaims


class VerifyAIDRequest(BaseModel):
    """Request to verify an AID token. Called by M6 on every request."""

    token: str = Field(..., min_length=1, description="JWT token to verify")


class VerifyAIDResponse(BaseModel):
    """
    Verification result. Never throws — always returns a response.
    M6 checks valid=True before proceeding.
    """

    valid: bool
    aid_id: Optional[str] = None
    claims: Optional[AIDClaims] = None
    status: Optional[AIDStatus] = None
    reason: Optional[str] = None
    cached: bool = Field(False, description="True if result came from verify cache")


class RevokeAIDRequest(BaseModel):
    """Request to revoke an AID. Immediate effect."""

    aid_id: str
    reason: str = Field(..., min_length=1, max_length=500)


class RevokeAIDResponse(BaseModel):
    """Confirmation of AID revocation."""

    aid_id: str
    status: AIDStatus
    revoked_at: datetime
