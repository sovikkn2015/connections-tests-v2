"""dual_auth.run — second-approver flow for high-value writes.

Thresholds (steering rule 5):
  - wire notional > $100,000 USD, OR
  - trade notional > $500,000 USD, OR
  - any account-closure

Any of those -> dual_auth_required = True. The RM's first approval (HITL)
is not sufficient; a second approval is required before mulesoft_api fires.

Rules (steering rules 6-7):
  - Second approver MUST be distinct from the first (`approver_id !=
    second_approver_id`). The skill enforces this.
  - Second approver MUST hold the Senior_Compliance_Approver permission set.
    Salesforce enforces at the record layer; this skill double-enforces via
    the `senior_permset_held` boolean the CRM MCP handler pre-checks.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


class DualAuthThreshold(str, Enum):
    """Why dual-auth was triggered (for audit + UI)."""

    WIRE_OVER_100K = "wire_over_100k"
    TRADE_OVER_500K = "trade_over_500k"
    ACCOUNT_CLOSURE = "account_closure"


class DualAuthDecision(str, Enum):
    """Output state."""

    NOT_REQUIRED = "not_required"
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


WIRE_THRESHOLD_USD = 100_000.0
TRADE_THRESHOLD_USD = 500_000.0


def threshold_required(
    *,
    action_type: str,
    notional_usd: float = 0.0,
    is_account_closure: bool = False,
) -> List[DualAuthThreshold]:
    """Deterministic threshold check. Pure function — import in tests freely."""
    triggers: List[DualAuthThreshold] = []
    if is_account_closure:
        triggers.append(DualAuthThreshold.ACCOUNT_CLOSURE)
    if action_type == "initiate_wire" and notional_usd > WIRE_THRESHOLD_USD:
        triggers.append(DualAuthThreshold.WIRE_OVER_100K)
    if action_type == "submit_order" and notional_usd > TRADE_THRESHOLD_USD:
        triggers.append(DualAuthThreshold.TRADE_OVER_500K)
    return triggers


class DualAuthInput(BaseModel):
    """Single input model covering both request and resolve phases."""

    action_type: str = Field(
        ..., description="submit_order | initiate_wire | close_account | ..."
    )
    notional_usd: float = Field(0.0, ge=0.0)
    is_account_closure: bool = False

    plan_hash: str = Field(..., min_length=16, description="Binds to HITL token")
    first_approver_id: str = Field(..., min_length=1)

    pending_approval_id: Optional[str] = Field(
        None, description="If None, create new pending row; if set, resolve it."
    )

    second_approver_id: Optional[str] = Field(
        None, description="Distinct from first approver (steering rule 6)."
    )
    senior_permset_held: bool = Field(
        False,
        description=(
            "CRM MCP pre-checks this; skill double-enforces (steering rule 7). "
            "If False, decision is REJECTED regardless of the approver's intent."
        ),
    )
    second_approver_decision: Optional[str] = Field(
        None, description="approve | reject — omit to leave pending."
    )

    principal_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _guard_distinct(self) -> "DualAuthInput":
        if (
            self.second_approver_id is not None
            and self.second_approver_id == self.first_approver_id
        ):
            raise ValueError(
                "second_approver_id must differ from first_approver_id "
                "(steering rule 6)"
            )
        return self

    model_config = {"frozen": True}


class DualAuthOutput(BaseModel):
    """Dual-auth decision + Salesforce pending-row id if one was created."""

    decision: DualAuthDecision
    thresholds_triggered: List[DualAuthThreshold] = Field(default_factory=list)
    pending_approval_id: Optional[str] = None
    audit_row_id: str

    model_config = {"frozen": True}


async def _request_phase(
    payload: DualAuthInput,
    triggers: List[DualAuthThreshold],
    client: MCPClient,
) -> DualAuthOutput:
    """Create IR_Pending_Approval__c row and return PENDING."""
    pending_row = {
        "Action_Type__c": payload.action_type,
        "Notional_Usd__c": payload.notional_usd,
        "Plan_Hash__c": payload.plan_hash,
        "First_Approver__c": payload.first_approver_id,
        "Thresholds__c": ",".join(t.value for t in triggers),
        "Status__c": "PENDING",
        "Requested_At__c": datetime.now(timezone.utc).isoformat(),
    }
    result = await client.call(
        server="salesforce-crm",
        tool="write_pending_approval",
        arguments={"record": pending_row},
    )
    pending_id = (
        result.get("Id")
        or result.get("id")
        or f"a0Y_pend_{uuid4().hex[:14]}"
    )

    audit = await audit_run(
        AuditInput(
            action=AuditAction.DUAL_AUTH_REQUESTED,
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            approver_id=payload.first_approver_id,
            gate_trace=[
                {"gate": "dual_auth", "outcome": "requested",
                 "triggers": [t.value for t in triggers]}
            ],
            payload={
                "action_type": payload.action_type,
                "notional_usd": payload.notional_usd,
                "pending_approval_id": pending_id,
            },
        ),
        mcp=client,
    )

    return DualAuthOutput(
        decision=DualAuthDecision.PENDING,
        thresholds_triggered=triggers,
        pending_approval_id=pending_id,
        audit_row_id=audit.audit_row_id,
    )


async def _resolve_phase(
    payload: DualAuthInput,
    triggers: List[DualAuthThreshold],
    client: MCPClient,
) -> DualAuthOutput:
    """Evaluate second approver's decision; update pending row; audit."""
    approved = (
        payload.second_approver_decision == "approve"
        and payload.senior_permset_held
    )
    decision = DualAuthDecision.APPROVED if approved else DualAuthDecision.REJECTED
    new_status = "APPROVED" if approved else "REJECTED"

    await client.call(
        server="salesforce-crm",
        tool="update_pending_approval",
        arguments={
            "id": payload.pending_approval_id,
            "fields": {
                "Status__c": new_status,
                "Second_Approver__c": payload.second_approver_id,
                "Senior_Permset_Held__c": payload.senior_permset_held,
                "Resolved_At__c": datetime.now(timezone.utc).isoformat(),
            },
        },
    )

    audit = await audit_run(
        AuditInput(
            action=(
                AuditAction.DUAL_AUTH_APPROVED
                if approved
                else AuditAction.DUAL_AUTH_REJECTED
            ),
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            approver_id=payload.first_approver_id,
            dual_approver_id=payload.second_approver_id,
            gate_trace=[
                {
                    "gate": "dual_auth",
                    "outcome": new_status,
                    "senior_permset_held": payload.senior_permset_held,
                }
            ],
            payload={
                "pending_approval_id": payload.pending_approval_id,
                "triggers": [t.value for t in triggers],
            },
        ),
        mcp=client,
    )

    return DualAuthOutput(
        decision=decision,
        thresholds_triggered=triggers,
        pending_approval_id=payload.pending_approval_id,
        audit_row_id=audit.audit_row_id,
    )


async def run(
    payload: DualAuthInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> DualAuthOutput:
    """Entry point. Dispatches request vs resolve by pending_approval_id."""
    client = mcp or get_shared_mock_client()
    triggers = threshold_required(
        action_type=payload.action_type,
        notional_usd=payload.notional_usd,
        is_account_closure=payload.is_account_closure,
    )

    if not triggers:
        audit = await audit_run(
            AuditInput(
                action=AuditAction.DUAL_AUTH_APPROVED,
                principal_id=payload.principal_id,
                agent_id=payload.agent_id,
                session_id=payload.session_id,
                correlation_id=payload.correlation_id,
                approver_id=payload.first_approver_id,
                gate_trace=[{"gate": "dual_auth", "outcome": "not_required"}],
                payload={
                    "action_type": payload.action_type,
                    "notional_usd": payload.notional_usd,
                },
            ),
            mcp=client,
        )
        return DualAuthOutput(
            decision=DualAuthDecision.NOT_REQUIRED,
            thresholds_triggered=[],
            pending_approval_id=None,
            audit_row_id=audit.audit_row_id,
        )

    if payload.pending_approval_id is None:
        return await _request_phase(payload, triggers, client)

    if payload.second_approver_decision is None:
        return DualAuthOutput(
            decision=DualAuthDecision.PENDING,
            thresholds_triggered=triggers,
            pending_approval_id=payload.pending_approval_id,
            audit_row_id="",
        )

    return await _resolve_phase(payload, triggers, client)
