"""
Gap 2: Liability Provenance — Pydantic v2 Models.

Per-stage SHA-256 hash chain creating immutable provenance for every agent output.
Warranty boundary classification: deterministic | probabilistic | shared.
Error attribution: 6-category taxonomy for liability tracing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class WarrantyCategory(str, Enum):
    """Warranty boundary classification per ARCH-06 §2.2."""
    DETERMINISTIC = "deterministic"
    PROBABILISTIC = "probabilistic"
    SHARED = "shared"


class ErrorCategory(str, Enum):
    """6-category error attribution taxonomy per ARCH-06 §2.4."""
    SOURCE_DATA = "source_data"
    SCHEMA_TRANSLATION = "schema_translation"
    POLICY_EVALUATION = "policy_evaluation"
    LLM_SYNTHESIS = "llm_synthesis"
    HUMAN_APPROVAL = "human_approval"
    COMPLIANCE_RULE = "compliance_rule"


# ── Warranty boundary mapping ────────────────────────────────────

MODULE_WARRANTY: dict[str, WarrantyCategory] = {
    "M1": WarrantyCategory.DETERMINISTIC,
    "M2": WarrantyCategory.DETERMINISTIC,
    "M3": WarrantyCategory.DETERMINISTIC,
    "M4": WarrantyCategory.DETERMINISTIC,
    "M5": WarrantyCategory.DETERMINISTIC,
    "M7": WarrantyCategory.DETERMINISTIC,
    "M10": WarrantyCategory.DETERMINISTIC,
    "M8": WarrantyCategory.PROBABILISTIC,
    "M9": WarrantyCategory.PROBABILISTIC,
    "LLM": WarrantyCategory.PROBABILISTIC,
    "M6": WarrantyCategory.SHARED,
    "M11": WarrantyCategory.SHARED,
}

# ── Error attribution liable party mapping ───────────────────────

ERROR_LIABLE_PARTY: dict[str, str] = {
    ErrorCategory.SOURCE_DATA: "vendor",
    ErrorCategory.SCHEMA_TRANSLATION: "platform",
    ErrorCategory.POLICY_EVALUATION: "platform",
    ErrorCategory.LLM_SYNTHESIS: "llm_provider_shared",
    ErrorCategory.HUMAN_APPROVAL: "firm_user",
    ErrorCategory.COMPLIANCE_RULE: "sme_firm",
}

ERROR_DETECTION_METHOD: dict[str, str] = {
    ErrorCategory.SOURCE_DATA: "schema_reconciliation_test",
    ErrorCategory.SCHEMA_TRANSLATION: "reconciliation_test_manual_review",
    ErrorCategory.POLICY_EVALUATION: "compliance_audit_adversarial_test",
    ErrorCategory.LLM_SYNTHESIS: "advisor_review_hitl_output_guardrail",
    ErrorCategory.HUMAN_APPROVAL: "post_hoc_review_client_complaint",
    ErrorCategory.COMPLIANCE_RULE: "regulatory_examination_compliance_audit",
}


# ── Provenance Stage ─────────────────────────────────────────────


class ProvenanceStage(BaseModel):
    """Single processing stage in the provenance chain."""
    stage_number: int
    module: str  # M1-M13 or LLM
    operation: str
    version: str = "0.0.0"
    input_hash: Optional[str] = None
    output_hash: str
    metadata: dict = Field(default_factory=dict)
    latency_ms: float = 0.0
    warranty_category: WarrantyCategory = WarrantyCategory.DETERMINISTIC
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )


# ── Provenance Chain ─────────────────────────────────────────────


class ProvenanceChain(BaseModel):
    """Complete provenance chain for a single trace — stored in WORM."""
    trace_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    stages: list[ProvenanceStage] = Field(default_factory=list)
    final_output_hash: Optional[str] = None
    worm_record_id: Optional[str] = None
    finalized: bool = False


# ── Error Attribution ────────────────────────────────────────────


class ErrorAttribution(BaseModel):
    """Classifies an error to a liable party with evidence."""
    category: ErrorCategory
    liable_party: str
    detection_method: str
    evidence: dict = Field(default_factory=dict)
    stage_number: Optional[int] = None
    trace_id: Optional[str] = None


# ── Indemnification Record ───────────────────────────────────────


class IndemnificationRecord(BaseModel):
    """E&O insurance documentation package per trace."""
    trace_id: str
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
    )
    stages_captured: int = 0
    hitl_gates: list[dict] = Field(default_factory=list)
    warranty_boundary_snapshot: dict = Field(default_factory=dict)
    deterministic_stages: int = 0
    probabilistic_stages: int = 0
    shared_stages: int = 0
    chain_hash: Optional[str] = None
