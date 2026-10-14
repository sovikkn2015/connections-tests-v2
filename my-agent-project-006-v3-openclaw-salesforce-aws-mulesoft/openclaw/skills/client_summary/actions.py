"""client_summary.run — 30-second RM meeting prep. MNPI-filtered.

Fetches household + recent activity via salesforce-crm MCP and returns only
percentage-level exposure (no shares, no market value, no $).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


class ClientSummaryInput(BaseModel):
    household_id: str = Field(..., min_length=1, description="FSC household id")
    principal_id: str = Field(..., min_length=1, description="RM's principal id")
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    model_config = {"frozen": True}


class PositionPct(BaseModel):
    ticker: str
    pct: float = Field(..., ge=0.0, le=100.0)
    asset_class: str = "equity"
    model_config = {"frozen": True}


class RecentChange(BaseModel):
    ticker: str
    change_pct_30d: float
    model_config = {"frozen": True}


class NextEvent(BaseModel):
    kind: str
    date: datetime
    summary: str
    model_config = {"frozen": True}


class FamilyEvent(BaseModel):
    kind: str
    date: Optional[datetime] = None
    summary: str
    model_config = {"frozen": True}


class ClientSummaryOutput(BaseModel):
    household_id: str
    household_name: str
    positions_pct: List[PositionPct] = Field(default_factory=list)
    recent_changes_pct: List[RecentChange] = Field(default_factory=list)
    next_events: List[NextEvent] = Field(default_factory=list)
    open_items: List[str] = Field(default_factory=list)
    last_contact_at: Optional[datetime] = None
    family_events: List[FamilyEvent] = Field(default_factory=list)
    audit_row_id: str
    model_config = {"frozen": True}


def _scrub_position(row: Dict[str, Any]) -> Optional[PositionPct]:
    """Produce a MNPI-safe position record.

    Accepts pct_of_portfolio only; explicitly refuses shares/market_value.
    """
    pct = row.get("pct_of_portfolio") or row.get("Pct_Of_Portfolio__c")
    if pct is None:
        return None
    return PositionPct(
        ticker=row.get("ticker") or row.get("Ticker__c", "UNKNOWN"),
        pct=float(pct),
        asset_class=row.get("asset_class") or row.get("Asset_Class__c", "equity"),
    )


async def run(
    payload: ClientSummaryInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> ClientSummaryOutput:
    """Fetch MNPI-filtered household summary via salesforce-crm MCP."""
    client = mcp or get_shared_mock_client()

    result = await client.call(
        server="salesforce-crm",
        tool="read_household_summary",
        arguments={
            "household_id": payload.household_id,
            "principal_id": payload.principal_id,
            "mnpi_filtered": True,
        },
    )

    positions = [p for p in (_scrub_position(r) for r in result.get("positions", [])) if p]

    changes = [
        RecentChange(
            ticker=c.get("ticker", ""),
            change_pct_30d=float(c.get("change_pct_30d", 0.0)),
        )
        for c in result.get("recent_changes_pct", [])
    ]

    events = [
        NextEvent(
            kind=e.get("kind", "review"),
            date=(
                datetime.fromisoformat(e["date"])
                if isinstance(e.get("date"), str)
                else e.get("date", datetime.utcnow())
            ),
            summary=e.get("summary", ""),
        )
        for e in result.get("next_events", [])
    ]

    family_events = [
        FamilyEvent(
            kind=e.get("kind", "life_event"),
            date=(
                datetime.fromisoformat(e["date"])
                if isinstance(e.get("date"), str)
                else e.get("date")
            ),
            summary=e.get("summary", ""),
        )
        for e in result.get("family_events", [])
    ]

    last_contact = result.get("last_contact_at")
    if isinstance(last_contact, str):
        last_contact = datetime.fromisoformat(last_contact)

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="client_summary",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            client_contact_id=result.get("primary_contact_id"),
            gate_trace=[{"gate": "crm_read", "outcome": "ok", "mnpi_filtered": True}],
            payload={
                "household_id": payload.household_id,
                "position_count": len(positions),
                "open_item_count": len(result.get("open_items", [])),
            },
        ),
        mcp=client,
    )

    return ClientSummaryOutput(
        household_id=payload.household_id,
        household_name=result.get("household_name", ""),
        positions_pct=positions,
        recent_changes_pct=changes,
        next_events=events,
        open_items=list(result.get("open_items", [])),
        last_contact_at=last_contact,
        family_events=family_events,
        audit_row_id=audit.audit_row_id,
    )
