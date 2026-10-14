"""Tests for suitability_check skill — rule-matrix combinations."""

from __future__ import annotations

import pytest

from openclaw.skills.suitability_check import (
    PortfolioSummary,
    ProposedTrade,
    RiskProfile,
    SuitabilityDecision,
    SuitabilityInput,
    run,
)


def _build(**overrides):
    base = dict(
        client_risk_profile=RiskProfile.MODERATE,
        time_horizon_years=10.0,
        age=50,
        current_portfolio=PortfolioSummary(
            current_ticker_pct=3.0, current_equity_pct=60.0
        ),
        proposed_trade=ProposedTrade(
            ticker="NVDA", side="buy", delta_pct_of_portfolio=2.0, asset_class="equity",
        ),
        principal_id="u",
        session_id="s",
        correlation_id="c",
    )
    base.update(overrides)
    return SuitabilityInput(**base)


@pytest.mark.asyncio
async def test_pass_moderate_buy(mock_mcp) -> None:
    out = await run(_build())
    assert out.status is SuitabilityDecision.PASS


@pytest.mark.asyncio
async def test_fail_conservative_alt(mock_mcp) -> None:
    out = await run(_build(
        client_risk_profile=RiskProfile.CONSERVATIVE,
        proposed_trade=ProposedTrade(
            ticker="PE", side="buy", delta_pct_of_portfolio=1.0, asset_class="alt",
        ),
    ))
    assert out.status is SuitabilityDecision.FAIL
    assert not out.risk_profile_matched


@pytest.mark.asyncio
async def test_fail_equity_buy_short_horizon(mock_mcp) -> None:
    out = await run(_build(time_horizon_years=0.5))
    assert out.status is SuitabilityDecision.FAIL
    assert not out.time_horizon_matched


@pytest.mark.asyncio
async def test_fail_concentration_exceeded(mock_mcp) -> None:
    out = await run(_build(
        current_portfolio=PortfolioSummary(
            current_ticker_pct=9.0, current_equity_pct=60.0
        ),
        proposed_trade=ProposedTrade(
            ticker="NVDA", side="buy", delta_pct_of_portfolio=5.0, asset_class="equity",
        ),
    ))
    assert out.status is SuitabilityDecision.FAIL
    assert not out.concentration_compatible


@pytest.mark.asyncio
async def test_review_band(mock_mcp) -> None:
    out = await run(_build(
        current_portfolio=PortfolioSummary(
            current_ticker_pct=8.0, current_equity_pct=50.0
        ),
        proposed_trade=ProposedTrade(
            ticker="NVDA", side="buy", delta_pct_of_portfolio=1.5, asset_class="equity",
        ),
    ))
    assert out.status is SuitabilityDecision.REVIEW


@pytest.mark.asyncio
async def test_age_over_70_tightens(mock_mcp) -> None:
    out = await run(_build(
        age=75,
        current_portfolio=PortfolioSummary(
            current_ticker_pct=6.0, current_equity_pct=50.0
        ),
        proposed_trade=ProposedTrade(
            ticker="NVDA", side="buy", delta_pct_of_portfolio=3.0, asset_class="equity",
        ),
    ))
    assert out.status is SuitabilityDecision.FAIL


@pytest.mark.asyncio
async def test_aggressive_long_higher_limits(mock_mcp) -> None:
    out = await run(_build(
        client_risk_profile=RiskProfile.AGGRESSIVE,
        time_horizon_years=10.0,
        current_portfolio=PortfolioSummary(
            current_ticker_pct=10.0, current_equity_pct=70.0
        ),
        proposed_trade=ProposedTrade(
            ticker="NVDA", side="buy", delta_pct_of_portfolio=3.0, asset_class="equity",
        ),
    ))
    assert out.status in (SuitabilityDecision.PASS, SuitabilityDecision.REVIEW)
