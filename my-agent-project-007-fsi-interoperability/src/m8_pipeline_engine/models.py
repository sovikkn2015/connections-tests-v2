"""
M8 Pipeline Engine -- Pydantic v2 models.

Frozen, extra=forbid models:
- HitlApproval (R4 AC4.3)
- HitlGatePayload (R4 AC4.2)
- PipelineResult (R1 AC1.8)
- StageAuditPayload (R8 AC8.1)
- PipelineTerminalAuditPayload (AC8.8)
- LlmGeneration (R6 AC6.2)

See `.kiro/specs/m8-pipeline-engine.md` R1, R4, R6, R8.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m8_pipeline_engine.errors import VALID_REASON_CODES


class LlmGeneration(BaseModel):
    """Provider-level result (AC6.2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    text: str
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    model: str = Field(min_length=1)
    provider: Literal["bedrock", "azure_openai", "vertex", "vllm", "fake"]
    stop_reason: str = Field(min_length=1)


class HitlGatePayload(BaseModel):
    """Payload persisted when a HITL gate pauses (R4 AC4.2)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    gate_id: Literal[1, 2, 3]
    pipeline_run_id: str = Field(min_length=1)
    thread_id: str = Field(min_length=1)
    stage_number: Literal[7, 13, 21]
    approver_role_required: str = Field(min_length=1)
    summary: dict[str, Any] = Field(default_factory=dict)
    emitted_at: datetime


class HitlApproval(BaseModel):
    """Human approver response (R4 AC4.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    approver_aid_sub: str = Field(min_length=1)
    approved: bool
    approval_token: str = Field(pattern=r"^[0-9a-f]{64}$")
    approver_timestamp: datetime
    notes: Optional[str] = None


class PipelineResult(BaseModel):
    """Public return shape of run() / resume_from_gate() (R1 AC1.8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal[
        "completed", "paused", "rejected", "timed_out", "terminated", "failed"
    ]
    pipeline_run_id: str
    thread_id: str
    research_brief: Optional[Any] = None
    final_stage: int = Field(ge=0, le=23)
    paused_gate: Optional[Literal[1, 2, 3]] = None
    wall_clock_seconds: float = Field(ge=0.0)
    total_tokens: int = Field(ge=0)
    reason_code: Optional[str] = None
    dropped_instruments: list[str] = Field(default_factory=list)

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocabulary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_REASON_CODES:
            raise ValueError(f"reason_code {v!r} not in VALID_REASON_CODES")
        return v


class StageAuditPayload(BaseModel):
    """ARCH-06 v3 Gap 2 row: per-stage audit (AC8.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    source: Literal["m8"] = "m8"
    event_type: str = Field(min_length=1)
    pipeline_run_id: str
    thread_id: str
    tenant_id: str
    firm_id: str
    stage_number: int = Field(ge=0, le=23)
    stage_name: str = Field(min_length=1)
    trace_id: str = Field(min_length=1)
    timestamp: datetime
    model_version: Optional[str] = None
    prompt_template_version: Optional[str] = None
    input_sha256: str = Field(pattern=r"^[0-9a-f]{64}$|^$")
    output_sha256: str = Field(pattern=r"^[0-9a-f]{64}$|^$")
    latency_ms: int = Field(ge=0)
    input_tokens: int = Field(ge=0, default=0)
    output_tokens: int = Field(ge=0, default=0)
    reason_code: Optional[str] = None
    tool_name: Optional[str] = None
    gateway_decision: Optional[str] = None
    rule_applied: Optional[str] = None
    wsp_section: Optional[str] = None

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocabulary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_REASON_CODES:
            raise ValueError(f"reason_code {v!r} not in VALID_REASON_CODES")
        return v


class PipelineTerminalAuditPayload(BaseModel):
    """Terminal audit emitted at end of run() (AC8.8)."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    source: Literal["m8"] = "m8"
    event_type: str = Field(min_length=1)
    pipeline_run_id: str
    thread_id: str
    tenant_id: str
    firm_id: str
    trace_id: str
    timestamp: datetime
    status: Literal[
        "completed", "paused", "rejected", "timed_out", "terminated", "failed"
    ]
    final_stage: int = Field(ge=0, le=23)
    wall_clock_seconds: float = Field(ge=0.0)
    total_input_tokens: int = Field(ge=0, default=0)
    total_output_tokens: int = Field(ge=0, default=0)
    reason_code: Optional[str] = None
    dropped_instruments: list[str] = Field(default_factory=list)

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocabulary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_REASON_CODES:
            raise ValueError(f"reason_code {v!r} not in VALID_REASON_CODES")
        return v


__all__ = [
    "HitlApproval",
    "HitlGatePayload",
    "PipelineResult",
    "StageAuditPayload",
    "PipelineTerminalAuditPayload",
    "LlmGeneration",
]
