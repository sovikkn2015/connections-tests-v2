"""Tests for research_awareness skill — DLM join of briefs with RM book."""

from __future__ import annotations

import pytest

from openclaw.skills.research_awareness import ResearchAwarenessInput, run


@pytest.mark.asyncio
async def test_awareness_returns_briefs_and_affected(mock_mcp) -> None:
    out = await run(
        ResearchAwarenessInput(
            principal_id="u_rm",
            min_exposure_pct=5.0,
            session_id="s",
            correlation_id="c",
        )
    )
    assert len(out.briefs) == 1
    brief = out.briefs[0]
    assert brief.ticker == "NVDA"
    assert len(brief.affected_clients) == 1
    assert brief.affected_clients[0].pct_exposure == 6.2
    assert out.total_affected_clients == 1


@pytest.mark.asyncio
async def test_thesis_truncated(mock_mcp) -> None:
    async def long_thesis(args):
        return {
            "briefs": [
                {
                    "brief_id": "a",
                    "ticker": "X",
                    "thesis": "word " * 200,
                    "sentiment_score": 0.0,
                    "compliance_status": "ALLOW",
                    "published_at": "2026-03-10T00:00:00+00:00",
                    "author_agent_id": "ro",
                    "affected_clients": [],
                    "citations": [],
                }
            ]
        }

    mock_mcp.mock_router.register(
        "salesforce-crm", "read_research_briefs_with_exposure", long_thesis
    )
    out = await run(
        ResearchAwarenessInput(
            principal_id="u", session_id="s", correlation_id="c"
        )
    )
    assert len(out.briefs[0].thesis_summary) <= 240


@pytest.mark.asyncio
async def test_no_contact_filter(mock_mcp) -> None:
    out = await run(
        ResearchAwarenessInput(
            principal_id="u_rm",
            no_contact_days=3000,
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.briefs[0].affected_clients == []
