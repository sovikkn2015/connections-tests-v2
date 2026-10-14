"""
Discounted Cash Flow (DCF) valuation model.

Runs inside OpenClaw's Python sandbox.
Allowed imports: math, random, json, csv, numpy, pandas, scipy.
No external API calls — all data is passed in as parameters.
"""

import math

import numpy as np


def run_dcf(
    revenue_ttm: float,
    revenue_growth_rates: list[float],
    operating_margin: float,
    margin_expansion: float,
    tax_rate: float,
    capex_pct_revenue: float,
    wacc: float,
    terminal_growth: float,
    shares_outstanding: float,
    net_debt: float,
) -> dict:
    """
    Build a 5-year DCF model and return fair value per share.

    Parameters
    ----------
    revenue_ttm : float
        Trailing 12-month revenue in billions.
    revenue_growth_rates : list[float]
        Projected revenue growth rates for the next 5 years
        (e.g. [0.25, 0.20, 0.18, 0.15, 0.12]).
    operating_margin : float
        Current operating margin (e.g. 0.35 for 35 %).
    margin_expansion : float
        Annual margin improvement (e.g. 0.01 for +1 pp/year).
    tax_rate : float
        Effective tax rate (e.g. 0.21).
    capex_pct_revenue : float
        Capital expenditure as a percentage of revenue (e.g. 0.08).
    wacc : float
        Weighted average cost of capital (e.g. 0.10).
    terminal_growth : float
        Perpetual growth rate for terminal value (e.g. 0.03).
    shares_outstanding : float
        Diluted shares outstanding in billions.
    net_debt : float
        Net debt in billions (total debt minus cash & equivalents).

    Returns
    -------
    dict
        fair_value_per_share, enterprise_value, equity_value,
        fcf_projections, sensitivity_table, methodology.
    """
    # ── Input validation ────────────────────────────────────────────
    # NaN / Inf guard on all float inputs
    for name, val in [
        ("revenue_ttm", revenue_ttm),
        ("operating_margin", operating_margin),
        ("margin_expansion", margin_expansion),
        ("tax_rate", tax_rate),
        ("capex_pct_revenue", capex_pct_revenue),
        ("wacc", wacc),
        ("terminal_growth", terminal_growth),
        ("shares_outstanding", shares_outstanding),
        ("net_debt", net_debt),
    ]:
        if math.isnan(val) or math.isinf(val):
            return _error(f"{name} must be a finite number")

    if revenue_ttm <= 0:
        return _error("revenue_ttm must be positive")
    if not revenue_growth_rates:
        return _error("revenue_growth_rates must be a non-empty list")
    for i, g in enumerate(revenue_growth_rates):
        if math.isnan(g) or math.isinf(g):
            return _error(f"revenue_growth_rates[{i}] must be a finite number")
    if shares_outstanding <= 0:
        return _error("shares_outstanding must be positive")
    if wacc <= 0:
        return _error("wacc must be positive")
    if wacc <= terminal_growth:
        return _error("wacc must exceed terminal_growth to avoid infinite value")
    if not (0 <= tax_rate < 1):
        return _error("tax_rate must be between 0 and 1")
    if not (0 <= capex_pct_revenue <= 1):
        return _error("capex_pct_revenue must be between 0 and 1")

    # Pad or trim growth rates to exactly 5 years
    growth = list(revenue_growth_rates)[:5]
    while len(growth) < 5:
        growth.append(growth[-1])

    # ── Project free cash flows ─────────────────────────────────────
    fcf_projections = []
    revenue = revenue_ttm
    margin = operating_margin

    for year_idx, g in enumerate(growth, start=1):
        revenue *= (1.0 + g)
        margin = min(margin + margin_expansion, 0.95)  # cap at 95 %
        operating_income = revenue * margin
        nopat = operating_income * (1.0 - tax_rate)
        capex = revenue * capex_pct_revenue
        fcf = nopat - capex

        fcf_projections.append({
            "year": year_idx,
            "revenue": round(revenue, 4),
            "operating_margin": round(margin, 4),
            "operating_income": round(operating_income, 4),
            "nopat": round(nopat, 4),
            "capex": round(capex, 4),
            "fcf": round(fcf, 4),
        })

    # ── Discount projected FCFs ─────────────────────────────────────
    pv_fcfs = 0.0
    for proj in fcf_projections:
        pv_fcfs += proj["fcf"] / ((1.0 + wacc) ** proj["year"])

    # ── Terminal value (Gordon Growth) ──────────────────────────────
    terminal_fcf = fcf_projections[-1]["fcf"] * (1.0 + terminal_growth)
    terminal_value = terminal_fcf / (wacc - terminal_growth)
    pv_terminal = terminal_value / ((1.0 + wacc) ** 5)

    # ── Enterprise → equity → per-share ─────────────────────────────
    enterprise_value = pv_fcfs + pv_terminal
    equity_value = enterprise_value - net_debt
    fair_value_per_share = max(equity_value / shares_outstanding, 0.0)

    # ── Sensitivity table ───────────────────────────────────────────
    sensitivity_table = _build_sensitivity_table(
        fcf_projections=fcf_projections,
        base_wacc=wacc,
        base_terminal_growth=terminal_growth,
        net_debt=net_debt,
        shares_outstanding=shares_outstanding,
    )

    methodology = (
        f"5-year DCF using projected revenue growth rates {growth}, "
        f"starting operating margin {operating_margin:.1%} with "
        f"{margin_expansion:.1%}/yr expansion, tax rate {tax_rate:.1%}, "
        f"CapEx at {capex_pct_revenue:.1%} of revenue. "
        f"Terminal value via Gordon Growth Model "
        f"(g={terminal_growth:.2%}, WACC={wacc:.2%}). "
        f"Net debt of ${net_debt:.2f}B subtracted to arrive at equity value."
    )

    return {
        "fair_value_per_share": round(fair_value_per_share, 2),
        "enterprise_value": round(enterprise_value, 4),
        "equity_value": round(equity_value, 4),
        "fcf_projections": fcf_projections,
        "sensitivity_table": sensitivity_table,
        "methodology": methodology,
    }


# ── Private helpers ─────────────────────────────────────────────────


def _error(msg: str) -> dict:
    """Return a standardised error envelope."""
    return {"error": True, "message": msg}


def _build_sensitivity_table(
    fcf_projections: list,
    base_wacc: float,
    base_terminal_growth: float,
    net_debt: float,
    shares_outstanding: float,
) -> dict:
    """
    Build a WACC-vs-terminal-growth sensitivity matrix.

    WACC varies ±2 % in 0.5 % steps (9 values).
    Terminal growth varies ±1 % in 0.25 % steps (9 values).
    """
    wacc_steps = [round(base_wacc + (i - 4) * 0.005, 4) for i in range(9)]
    tg_steps = [round(base_terminal_growth + (i - 4) * 0.0025, 4) for i in range(9)]

    # Filter out invalid combos (wacc <= 0)
    wacc_steps = [w for w in wacc_steps if w > 0]

    matrix = {}
    for w in wacc_steps:
        row = {}
        for tg in tg_steps:
            if w <= tg:
                row[str(tg)] = None  # undefined
                continue

            # Re-discount the same FCF stream at the new WACC
            pv = 0.0
            for proj in fcf_projections:
                pv += proj["fcf"] / ((1.0 + w) ** proj["year"])

            t_fcf = fcf_projections[-1]["fcf"] * (1.0 + tg)
            tv = t_fcf / (w - tg)
            pv_tv = tv / ((1.0 + w) ** 5)

            ev = pv + pv_tv
            eq = ev - net_debt
            fv = max(eq / shares_outstanding, 0.0)
            row[str(tg)] = round(fv, 2)

        matrix[str(w)] = row

    return {
        "wacc_values": wacc_steps,
        "terminal_growth_values": tg_steps,
        "fair_value_matrix": matrix,
    }
