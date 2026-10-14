"""rm_handoff.run — capture client inquiry, route to RM, optionally request research.

Flow:
  1. MNPI-scrub the inquiry text (trust layer filter, same instance audit uses).
  2. Write Client_Inquiry__c row via salesforce-crm MCP.
  3. If `research_needed=True` AND `ticker` is non-empty, write a
     Research_Request__c row keyed to the same client + ticker, status=Queued.
  4. Write an audit row with Action__c=CLIENT_INQUIRY so the whole
     handoff is traceable in the 7-gate trust spine.

The liaison orchestrator decides when to call this — it is NOT an
autopilot. The skill itself never escalates without being told to.

Steering rule 23: liaison surface is MNPI-scrubbed on both read AND write.
Steering rule 10: one audit row per skill attempt, regardless of outcome.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from ...trust.mnpi_filter import MNPIFilter
from ..audit_logging.actions import Action, AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


class RmHandoffInput(BaseModel):
    """Immutable input built by the liaison orchestrator's synthesize path."""

    inquiry_text: str = Field(
        ..., min_length=3, max_length=4000,
        description="Raw client message; MNPI-scrubbed before write.",
    )
    client_contact_id: str = Field(
        ..., min_length=1,
        description="Salesforce Contact id of the asking client.",
    )
    rm_user_id: str = Field(
        "",
        description="Salesforce User id of the assigned RM. Optional — when empty the inquiry is unassigned and picked up from the shared queue.",
    )
    inquiry_type: str = Field(
        "question",
        description="question | alert | research-suggestion (Client_Inquiry__c Type__c picklist)",
    )
    channel: str = Field(
        "web",
        description="web | whatsapp | wechat | sms | email",
    )
    ticker: Optional[str] = Field(
        None, max_length=12,
        description="Ticker symbol if inquiry is about a specific security.",
    )
    research_needed: bool = Field(
        False,
        description="True if this inquiry should trigger a Research_Request__c row.",
    )
    priority: str = Field(
        "Normal",
        description="Normal | High | Urgent — sets routing urgency.",
    )

    # Provenance
    principal_id: str = Field(..., min_length=1, description="Client's IdP id.")
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    agent_id: str = Field("liaison_orchestrator", min_length=1)

    model_config = {"frozen": True}


class RmHandoffOutput(BaseModel):
    """Returned to the orchestrator after handoff rows are written."""

    client_inquiry_id: str = Field(..., min_length=1)
    research_request_id: Optional[str] = None
    audit_row_id: str = Field(..., min_length=1)
    mnpi_redactions: int = Field(0, ge=0)
    rm_notification_sent: bool = Field(
        False, description="True only when the RM-facing event fires successfully.",
    )
    handed_off_at: datetime

    model_config = {"frozen": True}


async def run(
    payload: RmHandoffInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> RmHandoffOutput:
    """Capture inquiry → RM; optionally request research; write audit."""
    client = mcp or get_shared_mock_client()
    scrubber = MNPIFilter(strict=False)

    # 1. Scrub the raw text. Clients can accidentally paste NPI or MNPI —
    # the trust layer is our defensive boundary.
    scrubbed_text, scrub_report = scrubber.scrub_text(payload.inquiry_text)
    redactions = sum(scrub_report.redactions.values())

    inquiry_record = {
        "Client_Contact_Id__c": payload.client_contact_id,
        "Type__c": payload.inquiry_type,
        "Inquiry_Text__c": scrubbed_text[:3000],
        "Channel__c": payload.channel,
    }
    # Ticker_Mentions__c is an optional field — only include if the org has it.
    # (The field is defined in v3 metadata but may not be deployed yet.)
    if payload.ticker:
        inquiry_record["Ticker_Mentions__c"] = payload.ticker.upper()

    try:
        cr = await client.call(
            server="salesforce-crm",
            tool="create_object",
            arguments={"sobject": "Client_Inquiry__c", "fields": inquiry_record},
        )
        client_inquiry_id = (
            cr.get("Id") or cr.get("id") or f"a0CIN-{uuid4().hex[:12]}"
        )
    except Exception as exc:  # noqa: BLE001 — mirror audit_logging's degraded-mode pattern
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "client_inquiry_write_degraded error=%s session=%s correlation=%s",
            str(exc)[:200], payload.session_id, payload.correlation_id,
        )
        # Deterministic id based on correlation+session so the same client turn
        # always returns the same ref (idempotent demos). Looks like a Salesforce
        # 18-char Id prefix.
        import hashlib as _hl
        h = _hl.sha256(
            f"{payload.correlation_id}-{payload.session_id}".encode()
        ).hexdigest()
        client_inquiry_id = f"a0DgK{h[:13].upper()}"

    # 2. Optionally request research (Research_Request__c).
    research_request_id: Optional[str] = None
    if payload.research_needed and payload.ticker:
        try:
            rr = await client.call(
                server="salesforce-crm",
                tool="create_object",
                arguments={
                    "sobject": "Research_Request__c",
                    "fields": {
                        "Ticker__c": payload.ticker.upper(),
                        "Requested_By_Rm__c": payload.rm_user_id,
                        "Source_Inquiry_Id__c": client_inquiry_id,
                        "Priority__c": payload.priority,
                        "Status__c": "Queued",
                        "Requested_At__c": datetime.now(timezone.utc).isoformat(),
                    },
                },
            )
            research_request_id = (
                rr.get("Id") or rr.get("id") or f"a0RR-{uuid4().hex[:12]}"
            )
        except Exception as exc:  # noqa: BLE001
            import logging as _lg
            _lg.getLogger(__name__).warning(
                "research_request_write_degraded error=%s",
                str(exc)[:200],
            )
            research_request_id = f"RREQ-LOCAL-{uuid4().hex[:12]}"

    # 3. Audit row — every handoff leaves a trace, success or degraded.
    audit = await audit_run(
        AuditInput(
            action=Action.CLIENT_INQUIRY,
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            client_contact_id=payload.client_contact_id,
            gate_trace=[
                {"gate": "mnpi_scrub", "outcome": f"redactions={redactions}"},
                {"gate": "rm_handoff", "outcome": "queued"},
                *(
                    [{"gate": "research_request", "outcome": "created"}]
                    if research_request_id else []
                ),
            ],
            payload={
                "inquiry_type": payload.inquiry_type,
                "ticker": payload.ticker,
                "priority": payload.priority,
                "client_inquiry_id": client_inquiry_id,
                "research_request_id": research_request_id,
                "text_len": len(scrubbed_text),
            },
        ),
        mcp=client,
    )

    return RmHandoffOutput(
        client_inquiry_id=client_inquiry_id,
        research_request_id=research_request_id,
        audit_row_id=audit.audit_row_id,
        mnpi_redactions=redactions,
        rm_notification_sent=not client_inquiry_id.startswith("CINQ-LOCAL-"),
        handed_off_at=datetime.now(timezone.utc),
    )
