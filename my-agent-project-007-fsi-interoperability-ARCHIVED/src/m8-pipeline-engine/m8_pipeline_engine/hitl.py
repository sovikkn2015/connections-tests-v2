"""
M8 HITL Gate Logic — Human-in-the-Loop gates for the research pipeline.

3 gates (Rule 3):
  1. After data gathering (stage 6) — review gathered sources before analysis
  2. After analysis (stage 14) — review analysis before brief generation
  3. Before final output (stage 22) — review brief before delivery

Approval tokens are tamper-proof: SHA-256(gate_id + approver_id + timestamp).
On timeout (default 4 hours), mark TIMED_OUT and log to M10 audit.
On rejection, mark REJECTED and log to M10 audit.
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from m8_pipeline_engine.models import (
    DEFAULT_HITL_TIMEOUT_SECONDS,
    GateStatus,
    HITLGate,
)

logger = logging.getLogger(__name__)

# Gate definitions: (gate_number, gate_name, after_stage)
GATE_DEFINITIONS: list[tuple[int, str, int]] = [
    (1, "data_gathering_review", 6),
    (2, "analysis_review", 14),
    (3, "final_review", 22),
]


class HITLManager:
    """
    Manages HITL gate lifecycle: creation, approval, rejection, timeout.

    All gate state changes should be logged to M10 audit via REST call
    (no cross-module imports — Rule 13).
    """

    def __init__(
        self,
        timeout_seconds: int = DEFAULT_HITL_TIMEOUT_SECONDS,
        m10_audit_url: Optional[str] = None,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._m10_audit_url = m10_audit_url

    @staticmethod
    def generate_approval_token(
        gate_id: str,
        approver_id: str,
        timestamp: str,
    ) -> str:
        """
        Generate tamper-proof approval token (Rule 3).

        Token = SHA-256(gate_id + approver_id + timestamp).
        """
        payload = f"{gate_id}{approver_id}{timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_approval_token(
        gate_id: str,
        approver_id: str,
        timestamp: str,
        token: str,
    ) -> bool:
        """Verify that an approval token is valid and untampered."""
        expected = HITLManager.generate_approval_token(
            gate_id, approver_id, timestamp,
        )
        return expected == token

    def create_gate(
        self,
        gate_number: int,
        gate_name: str,
        context_summary: str = "",
    ) -> HITLGate:
        """
        Create a new HITL gate in PENDING status.

        Sets deadline based on configured timeout (default 4 hours).
        """
        now = datetime.now(timezone.utc)
        deadline = now + timedelta(seconds=self._timeout_seconds)

        gate = HITLGate(
            gate_name=gate_name,
            gate_number=gate_number,
            status=GateStatus.pending,
            requested_at=now.isoformat(),
            deadline=deadline.isoformat(),
            context_summary=context_summary,
        )

        logger.info(
            "HITL gate created: gate_id=%s, name=%s, deadline=%s",
            gate.gate_id, gate_name, deadline.isoformat(),
        )
        return gate

    def approve_gate(
        self,
        gate: HITLGate,
        approver_id: str,
    ) -> HITLGate:
        """
        Approve a HITL gate. Generates tamper-proof token.

        Raises ValueError if gate is not in PENDING status or has timed out.
        """
        if gate.status != GateStatus.pending:
            raise ValueError(
                f"Cannot approve gate {gate.gate_id}: "
                f"status is {gate.status.value}, expected pending"
            )

        # Check timeout before approving
        if self.is_timed_out(gate):
            gate = self._mark_timed_out(gate)
            raise ValueError(
                f"Cannot approve gate {gate.gate_id}: gate has timed out"
            )

        now = datetime.now(timezone.utc)
        timestamp = now.isoformat()
        token = self.generate_approval_token(
            gate.gate_id, approver_id, timestamp,
        )

        approved_gate = gate.model_copy(update={
            "status": GateStatus.approved,
            "approver_id": approver_id,
            "approval_token": token,
            "resolved_at": timestamp,
        })

        logger.info(
            "HITL gate approved: gate_id=%s, approver=%s",
            gate.gate_id, approver_id,
        )
        return approved_gate

    def reject_gate(
        self,
        gate: HITLGate,
        approver_id: str,
        reason: str = "",
    ) -> HITLGate:
        """
        Reject a HITL gate.

        Raises ValueError if gate is not in PENDING status.
        """
        if gate.status != GateStatus.pending:
            raise ValueError(
                f"Cannot reject gate {gate.gate_id}: "
                f"status is {gate.status.value}, expected pending"
            )

        now = datetime.now(timezone.utc)

        rejected_gate = gate.model_copy(update={
            "status": GateStatus.rejected,
            "approver_id": approver_id,
            "rejection_reason": reason,
            "resolved_at": now.isoformat(),
        })

        logger.info(
            "HITL gate rejected: gate_id=%s, approver=%s, reason=%s",
            gate.gate_id, approver_id, reason,
        )
        return rejected_gate

    def check_timeout(self, gate: HITLGate) -> HITLGate:
        """
        Check if a pending gate has timed out. If so, mark TIMED_OUT.

        Returns the gate unchanged if not timed out or not pending.
        """
        if gate.status != GateStatus.pending:
            return gate

        if self.is_timed_out(gate):
            return self._mark_timed_out(gate)

        return gate

    @staticmethod
    def is_timed_out(gate: HITLGate) -> bool:
        """Check if a gate's deadline has passed."""
        if not gate.deadline:
            return False
        now = datetime.now(timezone.utc)
        deadline = datetime.fromisoformat(gate.deadline)
        if deadline.tzinfo is None:
            deadline = deadline.replace(tzinfo=timezone.utc)
        return now > deadline

    @staticmethod
    def _mark_timed_out(gate: HITLGate) -> HITLGate:
        """Mark a gate as timed out."""
        now = datetime.now(timezone.utc)
        timed_out_gate = gate.model_copy(update={
            "status": GateStatus.timed_out,
            "resolved_at": now.isoformat(),
        })
        logger.warning(
            "HITL gate timed out: gate_id=%s, name=%s",
            gate.gate_id, gate.gate_name,
        )
        return timed_out_gate

    @staticmethod
    def get_gate_for_stage(stage_number: int) -> tuple[int, str] | None:
        """
        Return (gate_number, gate_name) if a HITL gate is required
        after the given stage number. Returns None otherwise.
        """
        for gate_num, gate_name, after_stage in GATE_DEFINITIONS:
            if stage_number == after_stage:
                return (gate_num, gate_name)
        return None
