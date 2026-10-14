"""
M12 Supervisor -- Pydantic v2 models.

SupervisorResult is the single public return shape of dispatch().

Frozen, extra=forbid. Never raised -- every error path returns a
SupervisorResult with a status and optional reason_code.
"""

from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m8_pipeline_engine.models import PipelineResult
from m9_intent_router.models import RoutingDecision

from m12_supervisor.errors import VALID_REASON_CODES


class SupervisorResult(BaseModel):
    """Public output of m12_supervisor.dispatch().

    Fields:
      status             Terminal status of the dispatch. Mirrors M8
                         terminal states plus "escalated" for M9
                         escalate-kind targets.
      routing_decision   RoutingDecision from M9 (always present unless M9
                         itself raised before emitting a decision).
      pipeline_result    PipelineResult from M8 (populated only for
                         pipeline-kind dispatch).
      escalation_target  Specialist name when M9 returned kind="escalate".
      tool_target        Tool name when M9 returned kind="tool". Channel
                         dispatches the tool via M6 directly -- M12 never
                         touches M6.
      trace_id, tenant_id, wall_clock_seconds, reason_code
    """

    model_config = ConfigDict(frozen=True, extra="forbid")

    status: Literal[
        "completed",
        "paused",
        "rejected",
        "escalated",
        "timed_out",
        "failed",
    ]
    routing_decision: Optional[RoutingDecision] = None
    pipeline_result: Optional[PipelineResult] = None
    escalation_target: Optional[str] = None
    tool_target: Optional[str] = None
    trace_id: str = Field(min_length=1)
    wall_clock_seconds: float = Field(ge=0.0)
    reason_code: Optional[str] = None
    tenant_id: str = Field(min_length=1)

    @field_validator("reason_code")
    @classmethod
    def _reason_code_permitted(cls, v: Optional[str]) -> Optional[str]:
        """reason_code must be M12's own code, or an m8_/m9_/llm_ code
        that flowed up from a child, or a known passthrough string from
        M9's closed vocabulary.
        """
        if v is None:
            return v
        if v in VALID_REASON_CODES:
            return v
        if v.startswith("m8_") or v.startswith("m9_") or v.startswith("llm_"):
            return v
        allowed_passthrough = {
            "invalid_utterance_length",
            "mnpi_shape_suspected",
            "low_confidence",
            "aid_authority_denied",
            "unsupported_intent_stub",
            "regex_fallback_miss",
            "provider_unconfigured",
            "taxonomy_mismatch",
        }
        if v in allowed_passthrough:
            return v
        raise ValueError(f"reason_code {v!r} not permitted by M12")


__all__ = ["SupervisorResult"]
