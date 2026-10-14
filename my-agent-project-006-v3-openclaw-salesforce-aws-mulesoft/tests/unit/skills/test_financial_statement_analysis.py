"""Tests for financial_statement_analysis — calculator correctness.

Anchor values are approximations of Apple FY2023 10-K (in USD):
  Revenue       383.29B
  COGS          214.14B
  Gross Profit  169.15B
  OpEx           54.85B
  Op Income     114.30B
  Net Income     97.00B
  Total Assets  352.58B
  Equity         62.15B
  LT Debt        95.28B
  CFO           110.54B
  CapEx          10.96B

Calculator outputs asserted to known ratios.
"""

from __future__ import annotations

import math

import pytest

from openclaw.skills.financial_statement_analysis import (
    AnalysisType,
    BalanceSheet,
    CashFlow,
    FSAInput,
    IncomeStatement,
    calc,
    run,
)


def _apple_income() -> IncomeStatement:
    return IncomeStatement(
        fiscal_period="2023-FY",
        revenue=383_290_000_000,
        cost_of_revenue=214_140_000_000,
        gross_profit=169_150_000_000,
        operating_expenses=54_847_000_000,
        operating_income=114_301_000_000,
        interest_expense=3_933_000_000,
        income_tax_expense=16_741_000_000,
        net_income=96_995_000_000,
    )


def _apple_income_prev() -> IncomeStatement:
    return IncomeStatement(
        fiscal_period="2022-FY",
        revenue=394_328_000_000,
        cost_of_revenue=223_546_000_000,
        gross_profit=170_782_000_000,
        operating_expenses=51_345_000_000,
        operating_income=119_437_000_000,
        interest_expense=2_931_000_000,
        income_tax_expense=19_300_000_000,
        net_income=99_803_000_000,
    )


def _apple_balance() -> BalanceSheet:
    return BalanceSheet(
        fiscal_period="2023-FY",
        cash_and_equivalents=29_965_000_000,
        current_assets=143_566_000_000,
        total_assets=352_583_000_000,
        current_liabilities=133_973_000_000,
        long_term_debt=95_281_000_000,
        total_liabilities=290_437_000_000,
        total_equity=62_146_000_000,
        shares_outstanding=15_550_000_000,
        retained_earnings=-214_000_000,
    )


def _apple_balance_prev() -> BalanceSheet:
    return BalanceSheet(
        fiscal_period="2022-FY",
        cash_and_equivalents=23_646_000_000,
        current_assets=135_405_000_000,
        total_assets=352_755_000_000,
        current_liabilities=153_982_000_000,
        long_term_debt=98_959_000_000,
        total_liabilities=302_083_000_000,
        total_equity=50_672_000_000,
        shares_outstanding=15_943_000_000,
        retained_earnings=-3_068_000_000,
    )


def _apple_cash() -> CashFlow:
    return CashFlow(
        fiscal_period="2023-FY",
        operating_cash_flow=110_543_000_000,
        capex=10_959_000_000,
        free_cash_flow=99_584_000_000,
    )


def test_gross_margin_apple() -> None:
    assert calc.gross_margin(_apple_income()) == pytest.approx(0.4413, abs=0.001)


def test_net_margin_apple() -> None:
    assert calc.net_margin(_apple_income()) == pytest.approx(0.253, abs=0.002)


def test_roe_apple() -> None:
    assert calc.roe(_apple_income(), _apple_balance()) == pytest.approx(1.56, abs=0.05)


def test_roa_apple() -> None:
    assert calc.roa(_apple_income(), _apple_balance()) == pytest.approx(0.275, abs=0.005)


def test_dcf_sensitivity_shape() -> None:
    result = calc.dcf(
        fcf_year_1=100_000_000_000,
        growth_rate_pct=6.0,
        discount_rate_pct=9.0,
        terminal_growth_pct=2.5,
        years=10,
    )
    keys = {"base", "r_plus_1pp", "r_minus_1pp", "tg_plus_1pp", "tg_minus_1pp"}
    assert set(result.keys()) >= keys
    assert result["r_plus_1pp"] < result["base"]
    assert result["r_minus_1pp"] > result["base"]


def test_monte_carlo_deterministic() -> None:
    args = dict(
        fcf_year_1_mean=100e9,
        fcf_year_1_stdev=10e9,
        growth_rate_mean_pct=6.0,
        growth_rate_stdev_pct=1.0,
        discount_rate_mean_pct=9.0,
        discount_rate_stdev_pct=0.5,
        paths=500,
        seed=42,
    )
    a = calc.monte_carlo_valuation(**args)
    b = calc.monte_carlo_valuation(**args)
    assert a == b
    assert a["p5"] <= a["median"] <= a["p95"]


def test_altman_z_apple() -> None:
    z = calc.altman_z_score(_apple_income(), _apple_balance())
    # Apple is not a distressed firm — Z should be comfortably positive even
    # with the book-equity proxy for variable D.
    assert z > 1.5


def test_piotroski_f_apple() -> None:
    score = calc.piotroski_f_score(
        _apple_income(),
        _apple_income_prev(),
        _apple_balance(),
        _apple_balance_prev(),
        _apple_cash(),
    )
    assert 0 <= score <= 9


def test_beneish_m_apple_is_float() -> None:
    m = calc.beneish_m_score(
        _apple_income(),
        _apple_income_prev(),
        _apple_balance(),
        _apple_balance_prev(),
        _apple_cash(),
    )
    assert isinstance(m, float)


@pytest.mark.asyncio
async def test_run_dispatcher_margins(mock_mcp) -> None:
    out = await run(
        FSAInput(
            analysis_type=AnalysisType.MARGINS,
            ticker="AAPL",
            income_current=_apple_income(),
            principal_id="u",
            session_id="s",
            correlation_id="c",
        )
    )
    assert out.result["gross_margin"] == pytest.approx(0.4413, abs=0.001)
    assert out.analysis_type is AnalysisType.MARGINS


@pytest.mark.asyncio
async def test_run_dispatcher_requires_fields(mock_mcp) -> None:
    with pytest.raises(ValueError):
        await run(
            FSAInput(
                analysis_type=AnalysisType.MARGINS,
                ticker="AAPL",
                income_current=None,
                principal_id="u",
                session_id="s",
                correlation_id="c",
            )
        )


def test_compare_peers_shape() -> None:
    matrix = calc.compare_peers(
        tickers=["AAPL", "MISSING"],
        metrics=["gross_margin", "roe"],
        as_of="2023-FY",
        statements={"AAPL": (_apple_income(), _apple_balance(), _apple_cash())},
    )
    assert "AAPL" in matrix
    assert matrix["AAPL"]["gross_margin"] == pytest.approx(0.4413, abs=0.001)
    assert math.isnan(matrix["MISSING"]["gross_margin"])
