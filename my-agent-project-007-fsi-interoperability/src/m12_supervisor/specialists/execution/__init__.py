"""
M12 Execution Specialist -- public surface.

The 4th specialist in the M12 supervisor dispatch map. Haiku-driven
order-ticket drafting with MANDATORY HITL before any `order.submit`
call through M6. See `.kiro/specs/m12-execution-specialist.md`.
"""

from __future__ import annotations

from m12_supervisor.specialists.execution.models import (
    ExecutionDecision,
    ExecutionRequest,
    OrderTicket,
    VALID_EXECUTION_REASONS,
    build_idempotency_key,
)
from m12_supervisor.specialists.execution.specialist import (
    DefaultHitlApprovalVerifier,
    ExecutionSpecialist,
)

#: Stable name used by `SPECIALIST_DISPATCH`.
SPECIALIST_NAME: str = "execution"

__all__ = [
    "ExecutionSpecialist",
    "ExecutionRequest",
    "ExecutionDecision",
    "OrderTicket",
    "VALID_EXECUTION_REASONS",
    "DefaultHitlApprovalVerifier",
    "build_idempotency_key",
    "SPECIALIST_NAME",
]
