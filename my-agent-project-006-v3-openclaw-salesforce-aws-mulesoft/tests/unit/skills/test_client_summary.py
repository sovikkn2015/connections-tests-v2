"""Tests for client_summary skill — MNPI-filtered household summary."""

from __future__ import annotations

import pytest

from openclaw.skills.client_summary import ClientSummaryInput, run


@pytest.mark.asyncio
async def test_summary_returns_percent_positions(mock_mcp) -> None:
    out = await run(
        ClientSummaryInput(
            household_id="H001",
            principal_id="u_rm",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.household_name == "Patel Household"
    assert len(out.positions_pct) == 3
    assert all(0.0 <= p.pct <= 100.0 for p in out.positions_pct)
    assert out.last_contact_at is not None


@pytest.mark.asyncio
async def test_summary_calls_crm_with_mnpi_filter_flag(mock_mcp) -> None:
    await run(
        ClientSummaryInput(
            household_id="H001",
            principal_id="u_rm",
            session_id="s",
            correlation_id="c",
        )
    )
    call = next(
        c for c in mock_mcp.mock_router.call_log
        if c["tool"] == "read_household_summary"
    )
    assert call["arguments"]["mnpi_filtered"] is True


@pytest.mark.asyncio
async def test_summary_writes_audit(mock_mcp) -> None:
    out = await run(
        ClientSummaryInput(
            household_id="H001",
            principal_id="u_rm",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.audit_row_id.startswith("AUDIT_")


@pytest.mark.asyncio
async def test_summary_drops_positions_without_pct(mock_mcp) -> None:
    async def bad_summary(args):
        return {
            "household_name": "X",
            "positions": [
                {"ticker": "NVDA", "pct_of_portfolio": 5.0},
                {"ticker": "SHARES_LEAK", "shares": 100},  # no pct -> dropped
            ],
            "recent_changes_pct": [],
            "next_events": [],
            "open_items": [],
            "family_events": [],
        }

    mock_mcp.mock_router.register(
        "salesforce-crm", "read_household_summary", bad_summary
    )
    out = await run(
        ClientSummaryInput(
            household_id="H001",
            principal_id="u_rm",
            session_id="s",
            correlation_id="c",
        )
    )
    tickers = [p.ticker for p in out.positions_pct]
    assert tickers == ["NVDA"]
