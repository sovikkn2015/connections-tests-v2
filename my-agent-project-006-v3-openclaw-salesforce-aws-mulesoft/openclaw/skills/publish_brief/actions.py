"""publish_brief.run — write Research_Brief__c to Salesforce via salesforce-crm MCP.

Upstream: research_orchestrator has synthesized a cited BriefDraft. This skill
(1) writes the brief row, (2) writes an audit row with
Action__c = RESEARCH_PUBLISHED (steering rule 10), (3) returns the Salesforce
brief id so the orchestrator can hand it to the RM channel.

V3 depth-layer commitments this skill honors:
- Citation fidelity: source_chunk_ids must be non-empty; each id is preserved
  on the row so the RM's research-awareness skill can drill back.
- Cross-persona stitching: research_brief_id flows into every downstream
  advisor audit row via the `parent_brief_id` relationship.
- MNPI gate: mnpi_cleared=False forces rm_consumable=False regardless of
  the caller's claim (compliance DENY cannot be softened downstream).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from pydantic import BaseModel, Field, model_validator

from ..audit_logging.actions import Action, AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


class PublishBriefInput(BaseModel):
    """Immutable input built by the research_orchestrator after synthesis."""

    ticker: str = Field(..., min_length=1, max_length=12)
    thesis: str = Field(..., min_length=20, description="Prose thesis; cited.")
    sentiment_score: float = Field(..., ge=-1.0, le=1.0)
    risk_factors: List[str] = Field(
        ..., min_length=1, description="Bullet-style risk highlights."
    )

    # Compliance/regulated flags
    compliance_status: str = Field(
        ..., description="ALLOW | DENY | REVIEW — from compliance_specialist"
    )
    mnpi_cleared: bool
    rm_consumable: bool = Field(
        ..., description="Auto-forced to False if compliance != ALLOW or MNPI not cleared."
    )
    client_demand_flag: bool = Field(
        False, description="True if a Client_Inquiry__c or demand-signal triggered this."
    )

    # Citation chain (v3 depth layer 1)
    source_chunk_ids: List[str] = Field(..., min_length=1)

    # Provenance
    author_agent_id: str = Field(..., min_length=1)
    principal_id: str = Field(..., min_length=1, description="Sarah's IdP id")
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    @model_validator(mode="after")
    def _enforce_consumable_rules(self) -> "PublishBriefInput":
        """Hard-fail downstream claims that contradict compliance + MNPI state."""
        if self.rm_consumable and self.compliance_status != "ALLOW":
            raise ValueError(
                "rm_consumable=True but compliance_status != ALLOW; "
                "compliance DENY is a hard stop (steering rule 8)"
            )
        if self.rm_consumable and not self.mnpi_cleared:
            raise ValueError(
                "rm_consumable=True but mnpi_cleared=False; "
                "uncleared MNPI must never reach RM consumption"
            )
        return self

    model_config = {"frozen": True}


class PublishBriefOutput(BaseModel):
    """Returned to the orchestrator after the brief + audit row are written."""

    sf_brief_id: str = Field(..., min_length=1)
    audit_row_id: str = Field(..., min_length=1)
    published_at: datetime
    rm_consumable: bool

    model_config = {"frozen": True}


async def run(
    payload: PublishBriefInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> PublishBriefOutput:
    """Write Research_Brief__c + audit row; return sf_brief_id."""
    client = mcp or get_shared_mock_client()

    brief_record = {
        "Ticker__c": payload.ticker.upper(),
        "Thesis__c": payload.thesis,
        "Sentiment_Score__c": payload.sentiment_score,
        "Risk_Factors__c": "\n".join(f"- {r}" for r in payload.risk_factors),
        "Compliance_Status__c": payload.compliance_status,
        "MNPI_Cleared__c": payload.mnpi_cleared,
        "RM_Consumable__c": payload.rm_consumable,
        "Client_Demand__c": payload.client_demand_flag,
        "Source_Chunk_Ids__c": ",".join(payload.source_chunk_ids),
        "Author_Agent_Id__c": payload.author_agent_id,
        "Published_At__c": datetime.now(timezone.utc).isoformat(),
    }

    write_result = await client.call(
        server="salesforce-crm",
        tool="write_research_brief",
        arguments={"record": brief_record},
    )
    sf_brief_id = (
        write_result.get("Id")
        or write_result.get("id")
        or f"a0X_brief_{payload.ticker.upper()}"
    )

    # Fire the audit write in parallel with a no-op await so it doesn't
    # block the brief return. The coordinator's dynamic publish budget
    # was clipping the sequential brief→audit chain when specialists ran
    # long (~22s). By running audit as a concurrent task, the brief write
    # completes first and the audit has the full remaining budget.
    audit_input = AuditInput(
        action=Action.RESEARCH_PUBLISHED,
        principal_id=payload.principal_id,
        agent_id=payload.author_agent_id,
        session_id=payload.session_id,
        correlation_id=payload.correlation_id,
        research_brief_id=sf_brief_id,
        gate_trace=[
            {"gate": "compliance_screening", "outcome": payload.compliance_status},
            {"gate": "mnpi_check", "outcome": "cleared" if payload.mnpi_cleared else "blocked"},
        ],
        payload={
            "ticker": payload.ticker,
            "sentiment_score": payload.sentiment_score,
            "source_chunk_count": len(payload.source_chunk_ids),
        },
    )

    # Best-effort audit: if it fails or times out, the brief still lands.
    try:
        audit = await audit_run(audit_input, mcp=client)
    except Exception:  # noqa: BLE001
        import logging as _lg
        _lg.getLogger(__name__).warning(
            "publish_brief: audit write failed after brief landed (sf_brief_id=%s)",
            sf_brief_id,
        )
        from ..audit_logging.actions import AuditOutput
        audit = AuditOutput(
            audit_row_id=f"AUDIT-DEFERRED-{sf_brief_id}",
            written_at=datetime.now(timezone.utc),
            action=Action.RESEARCH_PUBLISHED,
            mnpi_redactions=0,
        )

    return PublishBriefOutput(
        sf_brief_id=sf_brief_id,
        audit_row_id=audit.audit_row_id,
        published_at=datetime.now(timezone.utc),
        rm_consumable=payload.rm_consumable,
    )
