"""Tests for publish_brief skill."""

from __future__ import annotations

import pytest

from openclaw.skills.publish_brief import PublishBriefInput, run


def _base_payload(**overrides):
    base = dict(
        ticker="NVDA",
        thesis=(
            "NVDA pre-earnings thesis intact; supply chain watched.[src:nvda_1]"
        ),
        sentiment_score=0.15,
        risk_factors=["supply_chain", "export_controls"],
        compliance_status="ALLOW",
        mnpi_cleared=True,
        rm_consumable=True,
        client_demand_flag=False,
        source_chunk_ids=["chunk_001", "chunk_002"],
        author_agent_id="research_orchestrator",
        principal_id="u_sarah",
        session_id="sess_1",
        correlation_id="corr_1",
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_publish_brief_happy_path(mock_mcp) -> None:
    out = await run(PublishBriefInput(**_base_payload()))
    assert out.sf_brief_id == "a0X_test_brief_001"
    assert out.audit_row_id.startswith("AUDIT_")
    assert out.rm_consumable is True


def test_publish_brief_rejects_consumable_with_deny_compliance() -> None:
    with pytest.raises(Exception):
        PublishBriefInput(
            **_base_payload(compliance_status="DENY", rm_consumable=True)
        )


def test_publish_brief_rejects_consumable_with_mnpi_uncleared() -> None:
    with pytest.raises(Exception):
        PublishBriefInput(**_base_payload(mnpi_cleared=False, rm_consumable=True))


@pytest.mark.asyncio
async def test_publish_brief_writes_brief_and_audit(mock_mcp) -> None:
    await run(PublishBriefInput(**_base_payload()))
    tool_names = [c["tool"] for c in mock_mcp.mock_router.call_log]
    assert "write_research_brief" in tool_names
    assert "write_audit_log" in tool_names


@pytest.mark.asyncio
async def test_publish_brief_preserves_source_chunks(mock_mcp) -> None:
    await run(PublishBriefInput(**_base_payload()))
    brief_call = next(
        c for c in mock_mcp.mock_router.call_log if c["tool"] == "write_research_brief"
    )
    record = brief_call["arguments"]["record"]
    assert "chunk_001" in record["Source_Chunk_Ids__c"]
    assert "chunk_002" in record["Source_Chunk_Ids__c"]
