"""research_awareness.run — brief catalog joined against RM's book.

Given principal_id (RM) + optional ticker filter, return recent
`Research_Brief__c` rows AND which of the RM's clients have exposure.
The CRM MCP does the DLM join (Research_Brief__c <-> Position <-> Client
<-> Contact.LastActivityDate) filtered by the RM's sharing rules; this
skill is a thin formatter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


class AffectedClient(BaseModel):
    contact_id: str
    household_id: str
    pct_exposure: float = Field(..., ge=0.0, le=100.0)
    last_contact_at: Optional[datetime] = None
    days_since_contact: Optional[int] = None
    model_config = {"frozen": True}


class BriefAwarenessRow(BaseModel):
    brief_id: str
    ticker: str
    thesis_summary: str = Field(..., description="First 240 chars of thesis.")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    compliance_status: str
    published_at: datetime
    author_agent_id: str
    affected_clients: List[AffectedClient] = Field(default_factory=list)
    citations: List[str] = Field(default_factory=list)
    model_config = {"frozen": True}


class ResearchAwarenessInput(BaseModel):
    principal_id: str = Field(..., min_length=1, description="RM's IdP id")
    ticker_filter: Optional[str] = Field(None, max_length=12)
    min_exposure_pct: float = Field(
        5.0, ge=0.0, le=100.0,
        description="Only include clients whose exposure >= this threshold.",
    )
    no_contact_days: Optional[int] = Field(
        None, ge=0, le=3650,
        description="Only include clients last-contacted >= N days ago.",
    )
    lookback_days: int = Field(7, ge=1, le=90, description="Brief published window.")
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    model_config = {"frozen": True}


class ResearchAwarenessOutput(BaseModel):
    briefs: List[BriefAwarenessRow]
    audit_row_id: str
    total_affected_clients: int
    model_config = {"frozen": True}


def _truncate_thesis(text: str, limit: int = 240) -> str:
    if text is None:
        return ""
    if len(text) <= limit:
        return text
    return text[: limit - 3].rstrip() + "..."


async def run(
    payload: ResearchAwarenessInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> ResearchAwarenessOutput:
    """DLM join of Research_Brief__c with RM's client book + contact freshness."""
    client = mcp or get_shared_mock_client()
    cutoff_date = datetime.now(timezone.utc) - timedelta(days=payload.lookback_days)

    result = await client.call(
        server="salesforce-crm",
        tool="read_research_briefs_with_exposure",
        arguments={
            "principal_id": payload.principal_id,
            "ticker_filter": payload.ticker_filter,
            "min_exposure_pct": payload.min_exposure_pct,
            "published_since": cutoff_date.isoformat(),
        },
    )

    briefs_out: List[BriefAwarenessRow] = []
    total_affected = 0
    now = datetime.now(timezone.utc)

    for b in result.get("briefs", []):
        clients_out: List[AffectedClient] = []
        for c in b.get("affected_clients", []):
            last_contact = c.get("last_contact_at")
            if isinstance(last_contact, str):
                last_contact = datetime.fromisoformat(last_contact)
            days_since = None
            if last_contact is not None:
                if last_contact.tzinfo is None:
                    last_contact = last_contact.replace(tzinfo=timezone.utc)
                days_since = (now - last_contact).days
            if (
                payload.no_contact_days is not None
                and days_since is not None
                and days_since < payload.no_contact_days
            ):
                continue
            clients_out.append(
                AffectedClient(
                    contact_id=c.get("contact_id", ""),
                    household_id=c.get("household_id", ""),
                    pct_exposure=float(c.get("pct_exposure", 0.0)),
                    last_contact_at=last_contact,
                    days_since_contact=days_since,
                )
            )

        published_at = b.get("published_at")
        if isinstance(published_at, str):
            published_at = datetime.fromisoformat(published_at)
        elif published_at is None:
            published_at = datetime.now(timezone.utc)

        briefs_out.append(
            BriefAwarenessRow(
                brief_id=b.get("brief_id", ""),
                ticker=b.get("ticker", ""),
                thesis_summary=_truncate_thesis(b.get("thesis", "")),
                sentiment_score=float(b.get("sentiment_score", 0.0)),
                compliance_status=b.get("compliance_status", "ALLOW"),
                published_at=published_at,
                author_agent_id=b.get("author_agent_id", ""),
                affected_clients=clients_out,
                citations=list(b.get("citations", [])),
            )
        )
        total_affected += len(clients_out)

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="research_awareness",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            gate_trace=[{"gate": "crm_join", "outcome": "ok"}],
            payload={
                "ticker_filter": payload.ticker_filter,
                "min_exposure_pct": payload.min_exposure_pct,
                "briefs_returned": len(briefs_out),
                "affected_clients": total_affected,
            },
        ),
        mcp=client,
    )

    return ResearchAwarenessOutput(
        briefs=briefs_out,
        audit_row_id=audit.audit_row_id,
        total_affected_clients=total_affected,
    )
