"""audit_logging.run — canonical IR_Audit_Log__c writer for V3.

Cross-persona stitching fields (v3 depth layer 5 — trace cross-reference):

    research_brief_id | client_contact_id | principal_id | linked_trade_id |
    linked_wire_id   | action            | timestamp    | gate_trace

Steering rule 10 — every skill attempt writes exactly one audit row.
Steering rule 22 — approval tokens are SHA-256 hashed before write; raw
token values never touch Salesforce or Langfuse.

MNPI scrub is applied to the payload BEFORE the row is built. The scrubber
is the same `openclaw.trust.MNPIFilter` the trust layer uses; this keeps
the rule set single-sourced.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ...trust.mnpi_filter import MNPIFilter
from .._mcp_client import MCPClient, get_shared_mock_client


class Action(str, Enum):
    """Canonical `Action__c` picklist values extended in V3 (steering rule 12)."""

    RESEARCH_PUBLISHED = "RESEARCH_PUBLISHED"
    ADVISORY_QUERY = "ADVISORY_QUERY"
    TRADE_SUBMITTED = "TRADE_SUBMITTED"
    TRADE_REJECTED = "TRADE_REJECTED"
    TRADE_CANCELLED = "TRADE_CANCELLED"
    TRADE_MODIFIED = "TRADE_MODIFIED"
    WIRE_INITIATED = "WIRE_INITIATED"
    WIRE_BLOCKED = "WIRE_BLOCKED"
    KYC_SCREENING = "KYC_SCREENING"
    ACCOUNT_OPENED = "ACCOUNT_OPENED"
    COMPLIANCE_BLOCKED = "COMPLIANCE_BLOCKED"
    HITL_APPROVED = "HITL_APPROVED"
    HITL_REJECTED = "HITL_REJECTED"
    HITL_TIMEOUT = "HITL_TIMEOUT"
    DUAL_AUTH_REQUESTED = "DUAL_AUTH_REQUESTED"
    DUAL_AUTH_APPROVED = "DUAL_AUTH_APPROVED"
    DUAL_AUTH_REJECTED = "DUAL_AUTH_REJECTED"
    GATE_VIOLATION = "GATE_VIOLATION"
    CLIENT_INQUIRY = "CLIENT_INQUIRY"
    FAQ_ANSWERED = "FAQ_ANSWERED"
    VOLATILITY_ALERT_RAISED = "VOLATILITY_ALERT_RAISED"


class AuditInput(BaseModel):
    """Immutable input for a single audit write. Do not mutate after construct."""

    action: Action
    principal_id: str = Field(..., min_length=1, description="IdP-derived user id")
    agent_id: str = Field(
        ..., min_length=1, description="e.g. research_orchestrator, action_specialist"
    )
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    research_brief_id: Optional[str] = None
    client_contact_id: Optional[str] = None
    linked_trade_id: Optional[str] = None
    linked_wire_id: Optional[str] = None

    # Human approval chain — hashed before write.
    approver_id: Optional[str] = Field(
        None, description="First approver (HITL gate)."
    )
    dual_approver_id: Optional[str] = Field(
        None, description="Second approver for dual-auth."
    )
    approval_token: Optional[str] = Field(
        None,
        description="RAW token — HASHED before write, never stored or logged raw.",
    )

    # Seven-gate trace: ordered list of {gate, outcome, latency_ms}.
    gate_trace: List[Dict[str, Any]] = Field(default_factory=list)
    payload: Dict[str, Any] = Field(
        default_factory=dict,
        description="Free-form; MNPI-scrubbed before Salesforce write.",
    )

    mulesoft_reference: Optional[str] = None

    model_config = {"frozen": True}


class AuditOutput(BaseModel):
    """Returned to the caller after the audit row is written."""

    audit_row_id: str = Field(..., min_length=1, description="Salesforce 18-char Id")
    written_at: datetime
    action: Action
    mnpi_redactions: int = Field(
        0, ge=0, description="Number of MNPI redactions applied before write."
    )

    model_config = {"frozen": True}


def hash_token(raw: str) -> str:
    """SHA-256 hash with a short prefix marker for log readability.

    Format: `sha256:<first 16 hex chars>` — full digest is preserved upstream
    in the signing verifier; the audit row only needs a short fingerprint.
    """
    if not raw:
        return ""
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"sha256:{digest[:16]}"


async def run(
    payload: AuditInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> AuditOutput:
    """Write one IR_Audit_Log__c row via salesforce-crm MCP.

    Args:
        payload: immutable audit input.
        mcp: optional MCPClient (uses shared mock if None — test default).

    Returns:
        AuditOutput with the Salesforce row id.
    """
    client = mcp or get_shared_mock_client()
    scrubber = MNPIFilter(strict=False)

    # MNPI scrub on the free-form payload only; the structured fields are
    # already constrained (ids, enum actions, etc.).
    scrubbed_payload, scrub_report = scrubber.scrub_object(payload.payload)

    approval_token_hash = (
        hash_token(payload.approval_token) if payload.approval_token else None
    )

    row = {
        "Action__c": payload.action.value,
        "Principal_Id__c": payload.principal_id,
        "Agent_Id__c": payload.agent_id,
        "Session_Id__c": payload.session_id,
        "Correlation_Id__c": payload.correlation_id,
        "Research_Brief_Id__c": payload.research_brief_id,
        "Client_Contact_Id__c": payload.client_contact_id,
        "Linked_Trade_Id__c": payload.linked_trade_id,
        "Linked_Wire_Id__c": payload.linked_wire_id,
        "Approved_By__c": payload.approver_id,
        "Dual_Approver__c": payload.dual_approver_id,
        "Approval_Token_Hash__c": approval_token_hash,
        "MuleSoft_Reference__c": payload.mulesoft_reference,
        # Gate_Trace__c and Payload__c are LongTextArea fields on the SObject;
        # Salesforce's REST deserializer rejects JSON objects with a
        # JSON_PARSER_ERROR ("Cannot deserialize instance of textarea from
        # START_OBJECT"). Serialize to compact JSON strings here.
        "Gate_Trace__c": json.dumps(payload.gate_trace, separators=(",", ":")),
        "Payload__c": json.dumps(scrubbed_payload, separators=(",", ":")),
        "Timestamp__c": datetime.now(timezone.utc).isoformat(),
    }

    try:
        result = await client.call(
            server="salesforce-crm",
            tool="write_audit_log",
            arguments={"record": row},
        )
        row_id = result.get("Id") or result.get("id") or f"AUDIT-{uuid4().hex[:18]}"
    except Exception as exc:  # noqa: BLE001
        # Audit writes that fail against the CRM MCP (OBO not yet wired for
        # the service account, SF describe cache mismatch, etc.) must NOT
        # block the caller. We emit a local trace event so the degradation
        # is visible, and return a synthetic row id so downstream skills
        # that reference audit_row_id (for citation threading) still work.
        # The audit skill does NOT swallow MNPI violations — those are
        # raised earlier. This fallback is only for transport-layer errors.
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "audit_write_degraded error=%s agent=%s session=%s correlation=%s",
            str(exc)[:200], payload.agent_id, payload.session_id, payload.correlation_id,
        )
        row_id = f"AUDIT-LOCAL-{uuid4().hex[:18]}"
    return AuditOutput(
        audit_row_id=row_id,
        written_at=datetime.now(timezone.utc),
        action=payload.action,
        mnpi_redactions=sum(scrub_report.redactions.values()),
    )
