"""
M9 Intent Router -- Pydantic v2 models.

Three frozen, extra=forbid models:
- RouterContext (AC1.2, AC1.9) -- input to route(); carries identity, archetype.
- LlmClassification (AC3.3) -- provider-level output; Inf/-Inf/NaN rejected.
- RoutingDecision (AC9.1-9.6) -- public output; audit_payload() emits 12 keys.

See `.kiro/specs/m9-intent-router.md` R1, R3, R9.
"""

from __future__ import annotations

from typing import Any, Optional

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

from m1_identity import AidClaims  # Fix 8 + Fix 1 (ARCH-09)
from m5_config_loader import Archetype, Runtime  # Fix 4 -- firm-level
from m9_intent_router.errors import VALID_REASON_CODES
from m9_intent_router.taxonomy import IntentCategory, SelectedTarget


class RouterContext(BaseModel):
    """Context passed to route() by M12 (AC1.2 -- v0.2.0 includes identity).

    The archetype field MUST match identity.archetype (AC1.9 self-consistency --
    defends against Supervisor misconstruction).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_id: str = Field(min_length=1)
    runtime: Runtime
    archetype: Archetype  # firm-level, NOT M3 client-level
    tenant_id: str = Field(min_length=1)
    identity: AidClaims  # Fix 8 -- from M1
    prior_turns_summary: Optional[str] = None  # Phase 2 ignores (AC1.7)

    @model_validator(mode="after")
    def _aid_self_consistency(self) -> "RouterContext":  # AC1.9
        if self.identity.archetype != self.archetype.value:
            raise ValueError(
                "AID archetype must equal RouterContext archetype "
                f"(got identity={self.identity.archetype!r}, "
                f"ctx={self.archetype.value!r})"
            )
        return self


class LlmClassification(BaseModel):
    """Provider-level classification result (AC3.3).

    confidence bounds 0.0..1.0 inclusive reject Inf/-Inf/NaN at construction
    (AC5.7, Recommended Fix 4).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    intent: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)
    entities: dict[str, str] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    model: str
    provider: str


class RoutingDecision(BaseModel):
    """M9 public output (AC9.1 -- v0.2.0 adds tenant_id).

    reason_code drawn from VALID_REASON_CODES or None (R11 AC11.2).
    """

    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_id: str
    utterance_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    intent: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    entities: dict[str, str] = Field(default_factory=dict)
    selected_target: SelectedTarget
    fallback_used: bool
    llm_latency_ms: int = Field(ge=0)
    llm_model: str
    llm_provider: str
    reason_code: Optional[str] = None
    tenant_id: str = Field(min_length=1)  # v0.2.0 Recommended Fix 1

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocabulary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_REASON_CODES:
            raise ValueError(f"reason_code {v!r} not in VALID_REASON_CODES")
        return v

    def audit_payload(self) -> dict[str, Any]:
        """M10-safe audit dict -- exactly 12 keys in v0.2.0 (AC9.1).

        entities redacted to keys-only (AC6.8, AC9.2). No raw values.
        """
        return {
            "trace_id": self.trace_id,
            "utterance_sha256": self.utterance_sha256,
            "intent": self.intent.value,
            "confidence": self.confidence,
            "selected_target": {
                "kind": self.selected_target.kind,
                "name": self.selected_target.name,
            },
            "fallback_used": self.fallback_used,
            "llm_latency_ms": self.llm_latency_ms,
            "llm_model": self.llm_model,
            "llm_provider": self.llm_provider,
            "reason_code": self.reason_code,
            "entities_present": sorted(self.entities.keys()),
            "tenant_id": self.tenant_id,
        }
