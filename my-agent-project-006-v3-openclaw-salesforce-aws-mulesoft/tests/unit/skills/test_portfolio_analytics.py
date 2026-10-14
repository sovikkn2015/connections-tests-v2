"""Tests for portfolio_analytics skill — attribution + concentration + beta."""

from __future__ import annotations

import pytest

from openclaw.skills.portfolio_analytics import (
    PortfolioAnalyticsInput,
    PositionRow,
    run,
)


@pytest.mark.asyncio
async def test_analytics_from_crm_fixture(mock_mcp) -> None:
    out = await run(
        PortfolioAnalyticsInput(
            household_id="H001",
            principal_id="u_rm",
            session_id="s",
            correlation_id="c",
        )
    )
    assert "30d" in out.returns_pct
    assert "ytd" in out.returns_pct
    assert "1y" in out.returns_pct
    assert out.concentration["top_position_pct"] == 6.2
    assert out.beta_weighted > 0


@pytest.mark.asyncio
async def test_analytics_from_override(mock_mcp) -> None:
    rows = [
        PositionRow(ticker="A", pct=60.0, sector="tech", beta=1.5, ret_30d_pct=5.0),
        PositionRow(ticker="B", pct=40.0, sector="tech", beta=1.2, ret_30d_pct=-2.0),
    ]
    out = await run(
        PortfolioAnalyticsInput(
            household_id="H002",
            principal_id="u",
            positions_override=rows,
            session_id="s",
            correlation_id="c",
        )
    )
    # Weighted 30d = 0.6*5 + 0.4*(-2) = 2.2
    assert out.returns_pct["30d"] == pytest.approx(2.2, abs=1e-4)
    # Weighted beta = 0.6*1.5 + 0.4*1.2 = 1.38
    assert out.beta_weighted == pytest.approx(1.38, abs=1e-4)


@pytest.mark.asyncio
async def test_analytics_concentration_herfindahl(mock_mcp) -> None:
    rows = [
        PositionRow(ticker="A", pct=50.0, beta=1.0),
        PositionRow(ticker="B", pct=50.0, beta=1.0),
    ]
    out = await run(
        PortfolioAnalyticsInput(
            household_id="H",
            principal_id="u",
            positions_override=rows,
            session_id="s",
            correlation_id="c",
        )
    )
    # HHI = 50^2 + 50^2 = 5000
    assert out.concentration["herfindahl"] == pytest.approx(5000.0, abs=0.5)


@pytest.mark.asyncio
async def test_analytics_correlation_matrix_same_sector_high(mock_mcp) -> None:
    rows = [
        PositionRow(ticker="A", pct=30.0, sector="tech", beta=1.0),
        PositionRow(ticker="B", pct=30.0, sector="tech", beta=1.0),
        PositionRow(ticker="C", pct=40.0, sector="energy", beta=0.5),
    ]
    out = await run(
        PortfolioAnalyticsInput(
            household_id="H",
            principal_id="u",
            positions_override=rows,
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.correlation_matrix["A"]["B"] == pytest.approx(0.7, abs=1e-4)
    assert out.correlation_matrix["A"]["C"] == pytest.approx(0.15, abs=1e-4)
