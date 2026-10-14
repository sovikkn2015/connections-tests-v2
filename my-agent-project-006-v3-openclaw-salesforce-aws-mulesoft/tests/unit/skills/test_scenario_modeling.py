"""Tests for scenario_modeling skill — Monte Carlo VaR/CVaR determinism."""

from __future__ import annotations

import pytest

from openclaw.skills.scenario_modeling import (
    PortfolioRow,
    ScenarioModelingInput,
    run,
)


def _base_portfolio():
    return [
        PortfolioRow(ticker="A", pct=50.0, beta=1.2, sector="tech"),
        PortfolioRow(ticker="B", pct=30.0, beta=0.8, sector="energy"),
        PortfolioRow(ticker="C", pct=20.0, beta=1.5, sector="tech"),
    ]


@pytest.mark.asyncio
async def test_mc_deterministic_with_seed(mock_mcp) -> None:
    payload = ScenarioModelingInput(
        portfolio=_base_portfolio(),
        paths=1000,
        seed=42,
        principal_id="u",
        session_id="s",
        correlation_id="c",
    )
    out1 = await run(payload)
    out2 = await run(payload)
    assert out1.var95_pct == out2.var95_pct
    assert out1.cvar95_pct == out2.cvar95_pct
    assert out1.percentiles == out2.percentiles


@pytest.mark.asyncio
async def test_mc_var_below_cvar_magnitude(mock_mcp) -> None:
    """CVaR95 (mean of worst 5%) magnitude >= VaR95 magnitude."""
    out = await run(
        ScenarioModelingInput(
            portfolio=_base_portfolio(),
            paths=2000,
            seed=7,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    assert abs(out.cvar95_pct) >= abs(out.var95_pct) - 1e-6


@pytest.mark.asyncio
async def test_mc_percentile_order(mock_mcp) -> None:
    out = await run(
        ScenarioModelingInput(
            portfolio=_base_portfolio(),
            paths=2000,
            seed=7,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    p = out.percentiles
    assert p["p1"] <= p["p5"] <= p["p50"] <= p["p95"] <= p["p99"]


@pytest.mark.asyncio
async def test_mc_worst_cases_count(mock_mcp) -> None:
    out = await run(
        ScenarioModelingInput(
            portfolio=_base_portfolio(),
            paths=500,
            seed=1,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    assert len(out.worst_case_scenarios) == 3
    pnls = [w["pnl_pct"] for w in out.worst_case_scenarios]
    assert pnls == sorted(pnls)


@pytest.mark.asyncio
async def test_mc_summary_shape(mock_mcp) -> None:
    out = await run(
        ScenarioModelingInput(
            portfolio=_base_portfolio(),
            paths=500,
            seed=1,
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    for k in ("paths", "mean_pct", "stdev_pct", "skew", "kurtosis_excess"):
        assert k in out.summary
