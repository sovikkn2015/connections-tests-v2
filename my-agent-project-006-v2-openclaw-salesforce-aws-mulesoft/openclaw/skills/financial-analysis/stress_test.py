"""
Scenario stress testing for multi-client portfolios.

Runs inside OpenClaw's Python sandbox.
Allowed imports: math, random, json, csv, numpy, pandas, scipy.
No external API calls — all data is passed in as parameters.
"""

import pandas as pd


# ── Pre-built scenarios ─────────────────────────────────────────────

SCENARIOS = {
    "tech_crash": {
        "name": "Tech Crash",
        "sector_shocks": {
            "Technology": -0.20,
            "Communication Services": -0.12,
        },
        "market_shock": -0.05,
    },
    "rate_hike": {
        "name": "Rate Hike",
        "sector_shocks": {
            "Financials": 0.05,
            "Real Estate": -0.15,
            "Technology": -0.10,
            "Utilities": -0.08,
        },
        "market_shock": -0.03,
    },
    "oil_spike": {
        "name": "Oil Price Spike",
        "sector_shocks": {
            "Energy": 0.15,
            "Industrials": -0.05,
            "Consumer Discretionary": -0.05,
            "Consumer Staples": -0.03,
        },
        "market_shock": -0.02,
    },
    "recession": {
        "name": "Recession",
        "sector_shocks": {
            "Technology": -0.25,
            "Consumer Discretionary": -0.25,
            "Financials": -0.20,
            "Industrials": -0.20,
            "Real Estate": -0.20,
            "Communication Services": -0.18,
            "Materials": -0.18,
            "Energy": -0.15,
        },
        "market_shock": -0.15,
    },
    "black_swan": {
        "name": "Black Swan",
        "sector_shocks": {},
        "market_shock": -0.30,
    },
}


def get_scenario(name: str) -> dict:
    """Return a pre-built scenario by key, or None if not found."""
    return SCENARIOS.get(name)


def list_scenarios() -> list:
    """Return the names of all pre-built scenarios."""
    return list(SCENARIOS.keys())


def run_stress_test(
    holdings: list[dict],
    scenario: dict,
) -> dict:
    """
    Apply a stress scenario to a multi-client portfolio.

    Note: Sector-specific shocks and market_shock are NOT compounding.
    A stock gets EITHER its sector shock OR the market_shock (if its
    sector is not explicitly listed). This is a simplification — in
    reality, sector and market shocks compound.

    Parameters
    ----------
    holdings : list[dict]
        Each dict must contain:
        ``ticker``, ``shares``, ``current_price``, ``sector``,
        ``client_name``.
    scenario : dict
        Must contain:
        ``name`` (str), ``sector_shocks`` (dict mapping sector →
        pct_change), ``market_shock`` (float, applied to sectors
        not explicitly listed).

    Returns
    -------
    dict
        per_client_results, worst_hit_clients,
        total_portfolio_impact, scenario_summary.
    """
    # ── Input validation ────────────────────────────────────────────
    if not holdings:
        return _error("holdings list is empty")
    if not scenario or not isinstance(scenario, dict):
        return _error("scenario must be a non-empty dict")

    # Allow passing a scenario key string
    if isinstance(scenario.get("name"), str) and "sector_shocks" not in scenario:
        preset = SCENARIOS.get(scenario["name"])
        if preset:
            scenario = preset
        else:
            return _error(
                f"Unknown scenario '{scenario['name']}'. "
                f"Available: {list(SCENARIOS.keys())}"
            )

    sector_shocks = scenario.get("sector_shocks", {})
    market_shock = scenario.get("market_shock", 0.0)
    scenario_name = scenario.get("name", "Custom")

    df = pd.DataFrame(holdings)
    required = {"ticker", "shares", "current_price", "sector", "client_name"}
    missing = required - set(df.columns)
    if missing:
        return _error(f"holdings missing required fields: {missing}")

    # ── Apply shocks ────────────────────────────────────────────────
    # Guard against NaN in numeric columns
    for col in ["shares", "current_price"]:
        if df[col].isna().any():
            return _error(f"holdings contain NaN values in '{col}'")

    df["current_value"] = df["shares"] * df["current_price"]
    df["shock"] = df["sector"].map(sector_shocks).fillna(market_shock)
    df["stressed_price"] = df["current_price"] * (1.0 + df["shock"])
    df["stressed_value"] = df["shares"] * df["stressed_price"]
    df["loss"] = df["stressed_value"] - df["current_value"]

    # ── Per-client results ──────────────────────────────────────────
    per_client_results = []
    for client, group in df.groupby("client_name"):
        cv = group["current_value"].sum()
        sv = group["stressed_value"].sum()
        drawdown = (sv - cv) / cv if cv > 0 else 0.0

        per_client_results.append({
            "client_name": client,
            "current_value": round(cv, 2),
            "stressed_value": round(sv, 2),
            "pnl": round(sv - cv, 2),
            "drawdown_pct": round(drawdown * 100, 2),
        })

    # ── Worst-hit clients (top 5 by drawdown) ──────────────────────
    sorted_clients = sorted(
        per_client_results, key=lambda x: x["drawdown_pct"],
    )
    worst_hit_clients = sorted_clients[:5]

    # ── Total portfolio impact ──────────────────────────────────────
    total_current = df["current_value"].sum()
    total_stressed = df["stressed_value"].sum()
    total_loss = total_stressed - total_current
    total_drawdown = total_loss / total_current if total_current > 0 else 0.0

    total_portfolio_impact = {
        "total_current_value": round(total_current, 2),
        "total_stressed_value": round(total_stressed, 2),
        "total_pnl": round(total_loss, 2),
        "total_drawdown_pct": round(total_drawdown * 100, 2),
        "clients_affected": len(per_client_results),
        "positions_affected": len(df),
    }

    # ── Scenario summary ────────────────────────────────────────────
    shock_desc = ", ".join(
        f"{s} {v:+.0%}" for s, v in sector_shocks.items()
    )
    if not shock_desc:
        shock_desc = "none"

    if worst_hit_clients:
        scenario_summary = (
            f"Scenario: {scenario_name}. "
            f"Sector shocks: {shock_desc}. "
            f"Market-wide shock: {market_shock:+.0%}. "
            f"Total portfolio drawdown: {total_drawdown:.1%} "
            f"(${total_loss:,.0f}). "
            f"Worst-hit client: {worst_hit_clients[0]['client_name']} "
            f"({worst_hit_clients[0]['drawdown_pct']:.1f}%)."
        )
    else:
        scenario_summary = (
            f"Scenario: {scenario_name}. No clients affected."
        )

    return {
        "per_client_results": per_client_results,
        "worst_hit_clients": worst_hit_clients,
        "total_portfolio_impact": total_portfolio_impact,
        "scenario_summary": scenario_summary,
    }


# ── Private helpers ─────────────────────────────────────────────────


def _error(msg: str) -> dict:
    """Return a standardised error envelope."""
    return {"error": True, "message": msg}
