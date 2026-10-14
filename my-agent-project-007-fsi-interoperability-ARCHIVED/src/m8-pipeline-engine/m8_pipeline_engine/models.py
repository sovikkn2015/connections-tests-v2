"""
M8 Pydantic v2 models — Pipeline Engine.

Defines:
  - PipelineState: full state flowing through the 23-stage graph
  - StageResult: output of each individual stage
  - HITLGate: gate state with tamper-proof SHA-256 approval tokens
  - ResearchQuery: parsed input (ticker, topic, date_range, depth)
  - PipelineSummary: final output matching ResearchBrief canonical type (M3)
  - TokenBudget: per-stage token budget configuration
  - LLM provider protocol reused from M9 pattern (Rule 9)
"""

from __future__ import annotations

import enum
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class PipelineStatus(str, enum.Enum):
    """Pipeline execution status."""
    queued = "queued"
    running = "running"
    paused_hitl = "paused_hitl"
    completed = "completed"
    failed = "failed"
    timed_out = "timed_out"
    cancelled = "cancelled"


class GateStatus(str, enum.Enum):
    """HITL gate status (Rule 3)."""
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    timed_out = "timed_out"


class SourceType(str, enum.Enum):
    """Research source types for map-reduce (Rule 10)."""
    sec_filing = "sec_filing"
    market_data = "market_data"
    news = "news"
    financial_model = "financial_model"


class StageModel(str, enum.Enum):
    """LLM model assignment per stage (Rule 8)."""
    sonnet = "sonnet"
    haiku = "haiku"


# ── Token Budget Config (Rule 4) ────────────────────────────────


class TokenBudget(BaseModel):
    """Per-stage token budget configuration."""
    stage_name: str
    max_tokens: int = Field(..., gt=0)
    model: StageModel = StageModel.sonnet


# Default token budgets from ARCH-05 Section 3.3
DEFAULT_TOKEN_BUDGETS: dict[str, TokenBudget] = {
    "sec_filing_analysis": TokenBudget(
        stage_name="sec_filing_analysis", max_tokens=20_000, model=StageModel.sonnet,
    ),
    "market_data": TokenBudget(
        stage_name="market_data", max_tokens=5_000, model=StageModel.sonnet,
    ),
    "news_scan": TokenBudget(
        stage_name="news_scan", max_tokens=10_000, model=StageModel.haiku,
    ),
    "financial_modeling": TokenBudget(
        stage_name="financial_modeling", max_tokens=8_000, model=StageModel.sonnet,
    ),
    "cross_source_synthesis": TokenBudget(
        stage_name="cross_source_synthesis", max_tokens=15_000, model=StageModel.sonnet,
    ),
    "brief_generation": TokenBudget(
        stage_name="brief_generation", max_tokens=12_000, model=StageModel.sonnet,
    ),
    "intent_classification": TokenBudget(
        stage_name="intent_classification", max_tokens=2_000, model=StageModel.haiku,
    ),
}

PIPELINE_MAX_DURATION_SECONDS: int = 20 * 60  # 20 minutes (Rule 4)
PIPELINE_ALERT_THRESHOLD_SECONDS: int = 15 * 60  # Alert at 15 minutes
DEFAULT_HITL_TIMEOUT_SECONDS: int = 4 * 60 * 60  # 4 hours (Rule 3)
MAX_CONCURRENT_PIPELINES_PER_TENANT: int = 3  # Rule 11


# ── Security Identifier ─────────────────────────────────────────


class SecurityIdentifier(BaseModel):
    """Security being researched — matches M3 canonical schema."""
    ticker: str = Field(..., min_length=1, max_length=10)
    cusip: Optional[str] = Field(default=None, max_length=9)
    company_name: str = ""


# ── Research Query ───────────────────────────────────────────────


class ResearchQuery(BaseModel):
    """Parsed research input from user query."""
    raw_query: str = Field(..., min_length=1)
    ticker: Optional[str] = None
    topic: Optional[str] = None
    date_range_start: Optional[str] = None
    date_range_end: Optional[str] = None
    depth: str = Field(default="standard", pattern=r"^(quick|standard|deep)$")
    requesting_user_id: str = ""
    tenant_id: str = ""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))


# ── Source Data ──────────────────────────────────────────────────


class SourceData(BaseModel):
    """Data gathered from a single source (map phase input)."""
    source_type: SourceType
    raw_data: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    tokens_used: int = 0
    retrieved_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    source_url: Optional[str] = None
    source_date: Optional[str] = None


# ── Stage Result ─────────────────────────────────────────────────


class StageResult(BaseModel):
    """Output of each pipeline stage."""
    stage_name: str
    stage_number: int = Field(..., ge=1, le=23)
    data: dict[str, Any] = Field(default_factory=dict)
    tokens_used: int = Field(default=0, ge=0)
    duration_ms: float = Field(default=0.0, ge=0.0)
    model_used: Optional[str] = None
    error: Optional[str] = None
    completed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ── HITL Gate (Rule 3) ──────────────────────────────────────────


class HITLGate(BaseModel):
    """
    HITL gate state with tamper-proof approval tokens.

    Token = SHA-256(gate_id + approver_id + timestamp).
    3 gates: after data gathering (stage 6), after analysis (stage 14),
    before final output (stage 22).
    """
    gate_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    gate_name: str
    gate_number: int = Field(..., ge=1, le=3)
    status: GateStatus = GateStatus.pending
    approver_id: Optional[str] = None
    approval_token: Optional[str] = None
    rejection_reason: Optional[str] = None
    requested_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    deadline: Optional[str] = None
    resolved_at: Optional[str] = None
    context_summary: str = ""


# ── Provenance Entry ─────────────────────────────────────────────


class ProvenanceEntry(BaseModel):
    """SHA-256 hash chain entry for liability provenance (Gap 2)."""
    stage_name: str
    stage_number: int
    hash: str
    previous_hash: str = ""
    timestamp: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )


# ── Pipeline State (the graph state object) ─────────────────────


class PipelineState(BaseModel):
    """
    Full state object flowing through the 23-stage LangGraph pipeline.

    This is the single state object that every node reads/writes.
    Checkpointed after every stage to DynamoDB/PostgreSQL.
    """
    # Identity
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str = ""
    requesting_user_id: str = ""
    trace_id: str = Field(default_factory=lambda: str(uuid.uuid4()))

    # Status
    status: PipelineStatus = PipelineStatus.queued
    current_stage: int = 0
    current_stage_name: str = ""

    # Input
    query: Optional[ResearchQuery] = None
    securities: list[SecurityIdentifier] = Field(default_factory=list)

    # Data gathering (stages 1-6)
    sources: list[SourceData] = Field(default_factory=list)

    # Analysis (stages 7-14)
    source_analyses: list[dict[str, Any]] = Field(default_factory=list)
    synthesis: dict[str, Any] = Field(default_factory=dict)
    financial_model: dict[str, Any] = Field(default_factory=dict)
    risk_assessment: dict[str, Any] = Field(default_factory=dict)
    compliance_check: dict[str, Any] = Field(default_factory=dict)

    # Brief generation (stages 15-22)
    brief: dict[str, Any] = Field(default_factory=dict)
    source_attributions: list[dict[str, Any]] = Field(default_factory=list)
    anti_fabrication_score: float = Field(default=0.0, ge=0.0, le=1.0)
    output_guardrails_passed: bool = False

    # HITL gates (Rule 3)
    hitl_gates: list[HITLGate] = Field(default_factory=list)

    # Provenance chain (Gap 2 — liability provenance)
    provenance: list[ProvenanceEntry] = Field(default_factory=list)

    # Token tracking (Rule 4)
    token_usage: dict[str, int] = Field(default_factory=dict)
    total_tokens_used: int = 0

    # Stage results
    stage_results: list[StageResult] = Field(default_factory=list)

    # Timing
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    total_duration_ms: float = 0.0

    # Error
    error: Optional[str] = None


# ── Pipeline Summary (matches ResearchBrief canonical type) ──────


class PipelineSummary(BaseModel):
    """
    Final pipeline output matching M3 ResearchBrief canonical type.

    Fields align with schemas/canonical/research-brief.json.
    """
    brief_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    security_identifier: SecurityIdentifier
    analyst_id: str = ""
    rating: str = Field(
        default="hold",
        pattern=r"^(strong_buy|buy|hold|sell|strong_sell)$",
    )
    target_price: Optional[float] = None
    current_price: Optional[float] = None
    summary: str = ""
    thesis: str = ""
    catalysts: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    valuation: dict[str, Any] = Field(default_factory=dict)
    sources: list[dict[str, Any]] = Field(default_factory=list)
    pipeline_run_id: str = ""
    hitl_gates_passed: list[str] = Field(default_factory=list)
    anti_fabrication_score: float = Field(default=0.0, ge=0.0, le=1.0)
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
    )
    trace_id: str = ""


# ── LLM Provider Protocol (Rule 9 — same pattern as M9) ─────────


class Message(BaseModel):
    """Chat message for LLM provider."""
    role: str
    content: str


class ToolDefinition(BaseModel):
    """Tool/function definition for LLM function calling."""
    name: str
    description: str
    input_schema: dict[str, Any]


class CompletionResponse(BaseModel):
    """Unified LLM completion response."""
    content: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    model: str = ""
    usage: dict[str, int] = Field(default_factory=dict)


@runtime_checkable
class LLMProvider(Protocol):
    """
    Unified LLM provider interface (ARCH-04 Section 4).

    No module directly imports a provider-specific SDK.
    Provider swappable via config: Bedrock, Azure OpenAI, GCP Vertex, vLLM.
    """

    async def complete(
        self,
        messages: list[Message],
        tools: list[ToolDefinition] | None = None,
        model: str = "default",
        temperature: float = 0.0,
        max_tokens: int = 4096,
    ) -> CompletionResponse: ...
