"""Inter-agent message schemas — Pydantic, schema-validated at every hop.

Every orchestrator->worker dispatch, every worker->orchestrator response, and
every error surfaced across agents is one of these four models. Shapes are
frozen: a violation at runtime raises ValidationError and is treated as a
safety-grade fault (fail-closed, audit row, no retry).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AgentErrorType(str, Enum):
    """Canonical error taxonomy across the agent mesh."""

    TIMEOUT = "timeout"
    TOOL_FAILURE = "tool_failure"
    SAFETY = "safety"          # MNPI filter hit, guardrail trip, compliance DENY
    VALIDATION = "validation"  # schema mismatch on a hop


class SessionContext(BaseModel):
    """Per-session context flowing through every hop.

    Minted by the AgentCore channel adapter when a WebSocket opens, carried
    verbatim through every dispatch/response. Do not mutate; derive.
    """

    session_id: str = Field(..., min_length=1)
    principal_id: str = Field(..., min_length=1, description="IdP-derived user id")
    persona: str = Field(..., description="fsi_research | fsi_advisor | fsi_client_liaison")
    correlation_id: str = Field(
        ...,
        min_length=1,
        description="Threaded through structlog + Langfuse spans for replay.",
    )
    parent_brief_id: Optional[str] = Field(
        None,
        description="If this turn is cross-persona (RM consuming Sarah's brief), the SF id.",
    )
    turn_number: int = Field(1, ge=1)
    opened_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    channel: str = Field("web", description="web | whatsapp | wechat | sms | slack")
    user_memory: Dict[str, Any] = Field(
        default_factory=dict,
        description="Per-user per-persona persistent memory loaded by coordinator pre-turn.",
    )

    @field_validator("persona")
    @classmethod
    def _valid_persona(cls, v: str) -> str:
        if v not in {"fsi_research", "fsi_advisor", "fsi_client_liaison"}:
            raise ValueError(f"unknown persona: {v!r}")
        return v

    model_config = {"frozen": True}


class OrchestratorDispatch(BaseModel):
    """Orchestrator -> worker message. One per specialist invocation."""

    target_agent_id: str = Field(..., min_length=1)
    task: str = Field(..., min_length=1, description="Concrete instruction for the specialist")
    context_subset: Dict[str, Any] = Field(
        default_factory=dict,
        description="The narrowed slice of the session context the worker needs. "
                    "Do not pass the full SessionContext — dispatches must be scope-bounded.",
    )
    timeout_s: float = Field(25.0, gt=0, le=600)
    dispatched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class AgentError(BaseModel):
    """Structured error surfaced across agents. Never a bare exception."""

    agent_id: str = Field(..., min_length=1)
    error_type: AgentErrorType
    message: str = Field(..., min_length=1)
    recoverable: bool = Field(
        True,
        description="If False, the orchestrator must NOT synthesize around this worker — "
                    "surface the failure to the user verbatim. E.g. compliance DENY.",
    )
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    model_config = {"frozen": True}


class WorkerResponse(BaseModel):
    """Worker -> orchestrator response. One per dispatch, even on error.

    If the worker failed, `errors` is non-empty and `result` may be partial or
    empty. Orchestrators must handle partial-success; the brief synthesis still
    runs, with the gap noted, rather than failing the whole turn.
    """

    agent_id: str = Field(..., min_length=1)
    result: Dict[str, Any] = Field(default_factory=dict)
    citations: List[str] = Field(
        default_factory=list,
        description="source_chunk_id values — one per factual claim in result.",
    )
    cost_tokens: int = Field(0, ge=0, description="Total input+output tokens for this worker")
    errors: List[AgentError] = Field(default_factory=list)
    completed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def succeeded(self) -> bool:
        """True if no errors were raised. Partial results without errors are successes."""
        return not self.errors

    model_config = {"frozen": False}  # orchestrators may append errors on synthesis-time checks
