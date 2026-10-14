"""Pure-Python financial calculators. No LLM, no side effects.

Every function takes typed inputs and returns a plain value or dict so the
results serialize cleanly into a Pydantic `FSAOutput`. Formulas here are
textbook GAAP.
"""

from __future__ import annotations

import random
from typing import Dict, List, Optional, Sequence, Tuple

from ._xbrl_parser import BalanceSheet, CashFlow, IncomeStatement


# ---------- Ratios & margins ---------------------------------------------

def growth_rate(series: Sequence[float]) -> float:
    """Compound annual growth (or period-over-period if 2 values)."""
    n = len(series)
    if n < 2 or series[0] <= 0:
        return 0.0
    return (series[-1] / series[0]) ** (1.0 / (n - 1)) - 1.0


def gross_margin(inc: IncomeStatement) -> float:
    if inc.revenue <= 0:
        return 0.0
    return inc.gross_profit_computed / inc.revenue


def operating_margin(inc: IncomeStatement) -> float:
    if inc.revenue <= 0:
        return 0.0
    return inc.operating_income / inc.revenue


def net_margin(inc: IncomeStatement) -> float:
    if inc.revenue <= 0:
        return 0.0
    return inc.net_income / inc.revenue


def roe(inc: IncomeStatement, bs: BalanceSheet) -> float:
    if bs.total_equity <= 0:
        return 0.0
    return inc.net_income / bs.total_equity


def roa(inc: IncomeStatement, bs: BalanceSheet) -> float:
    if bs.total_assets <= 0:
        return 0.0
    return inc.net_income / bs.total_assets


def roic(inc: IncomeStatement, bs: BalanceSheet) -> float:
    """Return on invested capital = NOPAT / (equity + long-term debt).

    NOPAT approximated as operating_income * (1 - effective_tax_rate).
    """
    invested = bs.total_equity + bs.long_term_debt
    if invested <= 0:
        return 0.0
    etr = 0.0
    pretax = inc.operating_income - inc.interest_expense
    if pretax > 0:
        etr = max(0.0, min(0.5, inc.income_tax_expense / pretax))
    nopat = inc.operating_income * (1.0 - etr)
    return nopat / invested


# ---------- Common-size --------------------------------------------------

def common_size_income(inc: IncomeStatement) -> Dict[str, float]:
    if inc.revenue <= 0:
        return {}
    return {
        "revenue_pct": 1.0,
        "cogs_pct": inc.cost_of_revenue / inc.revenue,
        "gross_profit_pct": inc.gross_profit_computed / inc.revenue,
        "operating_expenses_pct": inc.operating_expenses / inc.revenue,
        "operating_income_pct": inc.operating_income / inc.revenue,
        "net_income_pct": inc.net_income / inc.revenue,
    }


def common_size_balance(bs: BalanceSheet) -> Dict[str, float]:
    if bs.total_assets <= 0:
        return {}
    return {
        "cash_pct": bs.cash_and_equivalents / bs.total_assets,
        "current_assets_pct": bs.current_assets / bs.total_assets,
        "current_liabilities_pct": bs.current_liabilities / bs.total_assets,
        "long_term_debt_pct": bs.long_term_debt / bs.total_assets,
        "total_liabilities_pct": bs.total_liabilities / bs.total_assets,
        "total_equity_pct": bs.total_equity / bs.total_assets,
    }


# ---------- DCF ----------------------------------------------------------

def dcf(
    *,
    fcf_year_1: float,
    growth_rate_pct: float,
    discount_rate_pct: float,
    terminal_growth_pct: float = 2.5,
    years: int = 10,
) -> Dict[str, float]:
    """2-stage DCF with Gordon-growth terminal value. Returns fair_value + sens."""
    r = discount_rate_pct / 100.0
    g = growth_rate_pct / 100.0
    tg = terminal_growth_pct / 100.0
    if r <= tg:
        raise ValueError("discount_rate_pct must exceed terminal_growth_pct")

    def _calc(r_in: float, g_in: float, tg_in: float) -> float:
        fcf_local = fcf_year_1
        pv_local = 0.0
        for y in range(1, years + 1):
            pv_local += fcf_local / ((1.0 + r_in) ** y)
            fcf_local *= 1.0 + g_in
        if r_in <= tg_in:
            return pv_local
        tv = fcf_local / (r_in - tg_in)
        return pv_local + tv / ((1.0 + r_in) ** years)

    base = _calc(r, g, tg)
    return {
        "base": round(base, 2),
        "r_plus_1pp": round(_calc(r + 0.01, g, tg), 2),
        "r_minus_1pp": round(_calc(max(tg + 0.001, r - 0.01), g, tg), 2),
        "tg_plus_1pp": round(_calc(r, g, min(r - 0.001, tg + 0.01)), 2),
        "tg_minus_1pp": round(_calc(r, g, tg - 0.01), 2),
    }


# ---------- Monte Carlo valuation ----------------------------------------

def monte_carlo_valuation(
    *,
    fcf_year_1_mean: float,
    fcf_year_1_stdev: float,
    growth_rate_mean_pct: float,
    growth_rate_stdev_pct: float,
    discount_rate_mean_pct: float,
    discount_rate_stdev_pct: float,
    paths: int = 10_000,
    seed: Optional[int] = 42,
    years: int = 10,
    terminal_growth_pct: float = 2.5,
) -> Dict[str, float]:
    """Monte Carlo valuation. Returns {mean, median, p5, p95, paths}."""
    rng = random.Random(seed)
    values: List[float] = []
    for _ in range(paths):
        fcf0 = rng.gauss(fcf_year_1_mean, fcf_year_1_stdev)
        g = rng.gauss(growth_rate_mean_pct, growth_rate_stdev_pct) / 100.0
        r = rng.gauss(discount_rate_mean_pct, discount_rate_stdev_pct) / 100.0
        tg = terminal_growth_pct / 100.0
        if r <= tg or fcf0 <= 0:
            continue
        pv = 0.0
        fcf = fcf0
        for year in range(1, years + 1):
            pv += fcf / ((1.0 + r) ** year)
            fcf *= 1.0 + g
        tv = fcf / (r - tg)
        values.append(pv + tv / ((1.0 + r) ** years))

    if not values:
        return {"mean": 0.0, "median": 0.0, "p5": 0.0, "p95": 0.0, "paths": 0.0}
    values.sort()
    n = len(values)

    def _pct(p: float) -> float:
        idx = max(0, min(n - 1, int(n * p / 100.0)))
        return values[idx]

    mean = sum(values) / n
    return {
        "mean": round(mean, 2),
        "median": round(_pct(50.0), 2),
        "p5": round(_pct(5.0), 2),
        "p95": round(_pct(95.0), 2),
        "paths": float(n),
    }


# ---------- Altman Z, Piotroski F, Beneish M -----------------------------

def altman_z_score(inc: IncomeStatement, bs: BalanceSheet) -> float:
    """Altman Z for public manufacturers (1968 formulation).

    Z = 1.2*A + 1.4*B + 3.3*C + 0.6*D + 1.0*E
      A = working capital / total assets
      B = retained earnings / total assets
      C = EBIT / total assets
      D = book equity / total liabilities (proxy for market-cap/liab)
      E = sales / total assets
    """
    if bs.total_assets <= 0 or bs.total_liabilities <= 0:
        return 0.0
    wc = bs.current_assets - bs.current_liabilities
    a = wc / bs.total_assets
    b = bs.retained_earnings / bs.total_assets
    c = inc.operating_income / bs.total_assets
    d = bs.total_equity / bs.total_liabilities
    e = inc.revenue / bs.total_assets
    return round(1.2 * a + 1.4 * b + 3.3 * c + 0.6 * d + 1.0 * e, 4)


def piotroski_f_score(
    inc_cur: IncomeStatement,
    inc_prev: IncomeStatement,
    bs_cur: BalanceSheet,
    bs_prev: BalanceSheet,
    cf_cur: CashFlow,
) -> int:
    """Piotroski F (0..9) — financial strength score."""
    score = 0
    # Profitability
    if inc_cur.net_income > 0:
        score += 1
    if cf_cur.operating_cash_flow > 0:
        score += 1
    if bs_prev.total_assets > 0 and bs_cur.total_assets > 0:
        roa_cur = inc_cur.net_income / bs_cur.total_assets
        roa_prev = inc_prev.net_income / bs_prev.total_assets
        if roa_cur > roa_prev:
            score += 1
    if cf_cur.operating_cash_flow > inc_cur.net_income:
        score += 1
    # Leverage, liquidity, funding
    if bs_prev.long_term_debt > 0 and bs_cur.long_term_debt < bs_prev.long_term_debt:
        score += 1
    if bs_cur.current_liabilities > 0 and bs_prev.current_liabilities > 0:
        cr_cur = bs_cur.current_assets / bs_cur.current_liabilities
        cr_prev = bs_prev.current_assets / bs_prev.current_liabilities
        if cr_cur > cr_prev:
            score += 1
    if bs_cur.shares_outstanding <= bs_prev.shares_outstanding:
        score += 1
    # Operating efficiency
    if inc_prev.revenue > 0:
        if gross_margin(inc_cur) > gross_margin(inc_prev):
            score += 1
    if bs_prev.total_assets > 0 and bs_cur.total_assets > 0:
        at_cur = inc_cur.revenue / bs_cur.total_assets
        at_prev = inc_prev.revenue / bs_prev.total_assets
        if at_cur > at_prev:
            score += 1
    return score


def beneish_m_score(
    inc_cur: IncomeStatement,
    inc_prev: IncomeStatement,
    bs_cur: BalanceSheet,
    bs_prev: BalanceSheet,
    cf_cur: CashFlow,
) -> float:
    """Beneish M. Values > -1.78 flag likely earnings manipulation.

    Simplified 4-factor approximation using fields we have. Full 8-variable
    Beneish requires DSRI, GMI, AQI, SGI, DEPI, SGAI, LVGI, TATA.
    """
    if (
        inc_prev.revenue <= 0
        or bs_prev.total_assets <= 0
        or bs_cur.total_assets <= 0
    ):
        return 0.0

    sgi = inc_cur.revenue / inc_prev.revenue
    gm_cur = gross_margin(inc_cur)
    gmi = gross_margin(inc_prev) / gm_cur if gm_cur > 0 else 1.0
    lvgi_cur = bs_cur.total_liabilities / bs_cur.total_assets
    lvgi_prev = bs_prev.total_liabilities / bs_prev.total_assets
    lvgi = lvgi_cur / lvgi_prev if lvgi_prev > 0 else 1.0
    tata = (inc_cur.net_income - cf_cur.operating_cash_flow) / bs_cur.total_assets

    m = (
        -4.84
        + 0.528 * gmi
        + 0.892 * sgi
        - 0.172 * (1 / max(lvgi, 0.01))
        + 4.679 * tata
    )
    return round(m, 4)


# ---------- Peer comparison ----------------------------------------------

def compare_peers(
    tickers: Sequence[str],
    metrics: Sequence[str],
    as_of: str,
    statements: Dict[str, Tuple[IncomeStatement, BalanceSheet, CashFlow]],
) -> Dict[str, Dict[str, float]]:
    """Peer matrix. Unknown metrics/missing tickers produce NaN."""
    out: Dict[str, Dict[str, float]] = {}
    for ticker in tickers:
        row: Dict[str, float] = {}
        trio = statements.get(ticker.upper())
        if trio is None:
            for m in metrics:
                row[m] = float("nan")
            out[ticker.upper()] = row
            continue
        inc, bs, _cf = trio
        for m in metrics:
            if m == "gross_margin":
                row[m] = gross_margin(inc)
            elif m == "operating_margin":
                row[m] = operating_margin(inc)
            elif m == "net_margin":
                row[m] = net_margin(inc)
            elif m == "roe":
                row[m] = roe(inc, bs)
            elif m == "roa":
                row[m] = roa(inc, bs)
            elif m == "roic":
                row[m] = roic(inc, bs)
            elif m == "rd_intensity":
                row[m] = (
                    inc.operating_expenses / inc.revenue if inc.revenue > 0 else 0.0
                )
            elif m == "gross_margin_trend_5y":
                row[m] = gross_margin(inc)
            else:
                row[m] = float("nan")
        out[ticker.upper()] = row
    if as_of:
        out["_meta"] = {"as_of": 0.0}
    return out
