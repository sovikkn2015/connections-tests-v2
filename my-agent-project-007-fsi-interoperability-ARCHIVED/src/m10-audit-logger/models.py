"""
M10 Pydantic v2 models — matches schemas/canonical/audit-entry.json.

Every audit entry includes:
  - SHA-256 integrity hash over canonical payload (Rule 3)
  - Provenance chain with per-stage hashes (Rule 13 / ARCH-06 Gap 2)
  - WORM record ID for S3 Object Lock reference
  - Langfuse trace URL for operational observability
  - CRM record ID for business-accessible audit trail
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


class AuditModule(str, Enum):
    """Modules that generate audit entries (from canonical schema)."""
    m1 = "m1"
    m2 = "m2"
    m4 = "m4"
    m6 = "m6"
    m7 = "m7"
    m8 = "m8"
    m9 = "m9"
    m10 = "m10"
    m11 = "m11"
    m12 = "m12"
    m13 = "m13"


class AuditDecision(str, Enum):
    """Outcome of the audited operation."""
    allow = "allow"
    deny = "deny"
    warn = "warn"
    escalate = "escalate"
    error = "error"


# ── Provenance Chain (ARCH-06 Gap 2) ────────────────────────────


class ProvenanceStage(BaseModel):
    """
    Single stage in the liability provenance chain.
    Each processing stage appends its SHA-256 hash, creating
    an immutable record of data lineage for error attribution.
    """
    stage: str = Field(..., description="Stage name, e.g. identity_verification")
    module: str = Field(..., description="Module that executed this stage")
    hash: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hash of stage input+output",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Core Audit Entry ────────────────────────────────────────────


class AuditEntry(BaseModel):
    """
    Immutable audit trail entry matching schemas/canonical/audit-entry.json.

    Written to M10 3-tier storage:
      Tier 1: Langfuse (operational, 90-day)
      Tier 2: S3 Object Lock WORM (regulatory, 6-year, SEC 17a-4)
      Tier 3: CRM (business-accessible)

    sha256_integrity is computed automatically via model_validator
    over the canonical payload (Rule 3). Never set manually.
    """
    # Identity
    canonical_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique audit entry ID",
    )
    trace_id: str = Field(
        ..., description="Distributed trace ID linking all entries for one request",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )

    # Actor
    actor_id: str = Field(..., description="AID hash of the actor")
    action: str = Field(..., description="What was done")
    module: AuditModule = Field(..., description="Module that generated this entry")

    # Target
    target_type: Optional[str] = Field(None, description="Entity type acted upon")
    target_id: Optional[str] = Field(None, description="Canonical ID of entity")

    # Decision
    decision: AuditDecision
    reason: Optional[str] = None

    # Integrity hashes
    input_hash: str = Field(
        ..., pattern=r"^[a-f0-9]{64}$", description="SHA-256 of input payload",
    )
    output_hash: str = Field(
        ..., pattern=r"^[a-f0-9]{64}$", description="SHA-256 of output payload",
    )

    # Policy context
    policy_bundle_version: Optional[str] = None
    rule_applied: Optional[str] = None
    wsp_section: Optional[str] = None

    # Operational context
    data_sources_used: list[str] = Field(default_factory=list)
    latency_ms: int = Field(0, ge=0)
    archetype: Optional[str] = None
    role: Optional[str] = None
    firm_id: str = Field(..., description="Firm context for multi-tenant")
    jurisdiction: Optional[str] = None

    # Provenance chain (ARCH-06 Gap 2)
    provenance_chain: Optional[list[ProvenanceStage]] = None

    # Storage references (populated after tier writes)
    worm_record_id: str = Field("", description="S3 Object Lock key")
    sha256_integrity: str = Field(
        "", description="SHA-256 of entire entry",
    )
    langfuse_trace_url: Optional[str] = None
    crm_record_id: Optional[str] = None
    retention_years: int = Field(6, description="Minimum retention (SEC 17a-4)")

    @model_validator(mode="after")
    def compute_integrity_hash(self) -> "AuditEntry":
        """Compute SHA-256 integrity hash over canonical payload (Rule 3)."""
        self.sha256_integrity = self._compute_hash()
        return self

    def _compute_hash(self) -> str:
        """Deterministic SHA-256 over the canonical audit payload.

        Includes provenance_chain to prevent chain tampering (BLOCKER 7).
        """
        # Serialize provenance_chain deterministically
        chain_serialized: list[dict] | None = None
        if self.provenance_chain:
            chain_serialized = [
                {
                    "stage": s.stage,
                    "module": s.module,
                    "hash": s.hash,
                    "timestamp": s.timestamp.isoformat(),
                }
                for s in self.provenance_chain
            ]

        canonical = {
            "canonical_id": self.canonical_id,
            "trace_id": self.trace_id,
            "timestamp": self.timestamp.isoformat(),
            "actor_id": self.actor_id,
            "action": self.action,
            "module": self.module.value,
            "decision": self.decision.value,
            "input_hash": self.input_hash,
            "output_hash": self.output_hash,
            "firm_id": self.firm_id,
            "provenance_chain": chain_serialized,
        }
        payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ── Tier Write Result ────────────────────────────────────────────


class TierWriteResult(BaseModel):
    """Result of writing to a single audit tier."""
    tier: str = Field(..., description="langfuse | worm | crm")
    success: bool
    record_id: Optional[str] = None
    error: Optional[str] = None


# ── API Models ───────────────────────────────────────────────────


class WriteAuditRequest(BaseModel):
    """Request body for POST /audit/write."""
    trace_id: str
    actor_id: str
    action: str
    module: AuditModule
    target_type: Optional[str] = None
    target_id: Optional[str] = None
    decision: AuditDecision
    reason: Optional[str] = None
    input_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    output_hash: str = Field(..., pattern=r"^[a-f0-9]{64}$")
    policy_bundle_version: Optional[str] = None
    rule_applied: Optional[str] = None
    wsp_section: Optional[str] = None
    data_sources_used: list[str] = Field(default_factory=list)
    latency_ms: int = Field(0, ge=0)
    archetype: Optional[str] = None
    role: Optional[str] = None
    firm_id: str
    jurisdiction: Optional[str] = None
    provenance_chain: Optional[list[ProvenanceStage]] = None
    retention_years: int = 6


class WriteAuditResponse(BaseModel):
    """Response from POST /audit/write."""
    canonical_id: str
    sha256_integrity: str
    tier_results: list[TierWriteResult]
    worm_record_id: str


class QueryAuditResponse(BaseModel):
    """Response from GET /audit/query."""
    entries: list[AuditEntry]
    count: int
