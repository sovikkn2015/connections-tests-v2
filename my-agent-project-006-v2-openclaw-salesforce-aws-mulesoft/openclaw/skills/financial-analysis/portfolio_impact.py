"""
Portfolio impact calculator.

Runs inside OpenClaw's Python sandbox.
Allowed imports: math, random, json, csv, numpy, pandas, scipy.
No external API calls — all data is passed in as parameters.
"""

import pandas as pd


def calculate_portfolio_impact(
    holdings: list[dict],
    price_changes: dict,
    concentration_limit: float = 0.10,
    sector_limit: float = 0.25,
) -> dict:
    """
    Calculate the P&L impact of hypothetical price changes across
    a multi-client book and flag concentration violations.

    Parameters
    ----------
    holdings : list[dict]
        Each dict must contain:
        ``ticker``, ``shares``, ``cost_basis``, ``current_price``,
        ``client_name``.  Optional: ``sector``.
    price_changes : dict
        Mapping of ticker → percentage change (e.g. {"AAPL": -0.05}).
    concentration_limit : float
        Maximum single-stock weight per client (default 10 %).
    sector_limit : float
        Maximum sector weight per client (default 25 %).

    Returns
    -------
    dict
        per_client_impact, concentration_violations, sector_exposure,
        total_exposure, affected_clients_count.
    """
    # ── Input validation ────────────────────────────────────────────
    if not holdings:
        return _error("holdings list is empty")
    if not isinstance(price_changes, dict):
        return _error("price_changes must be a dict")

    df = pd.DataFrame(holdings)
    required = {"ticker", "shares", "current_price", "client_name"}
    missing = required - set(df.columns)
    if missing:
        return _error(f"holdings missing required fields: {missing}")

    if "sector" not in df.columns:
        df["sector"] = "Unknown"

    # ── Compute current and new values ──────────────────────────────
    df["current_value"] = df["shares"] * df["current_price"]
    df["pct_change"] = df["ticker"].map(price_changes).fillna(0.0)
    df["new_price"] = df["current_price"] * (1.0 + df["pct_change"])
    df["new_value"] = df["shares"] * df["new_price"]
    df["pnl"] = df["new_value"] - df["current_value"]

    # ── Per-client impact ───────────────────────────────────────────
    client_groups = df.groupby("client_name")
    per_client_impact = []
    concentration_violations = []

    for client, group in client_groups:
        total_current = group["current_value"].sum()
        total_new = group["new_value"].sum()
        total_pnl = group["pnl"].sum()

        if total_current == 0:
            client_pct = 0.0
        else:
            client_pct = total_pnl / total_current

        per_client_impact.append({
            "client_name": client,
            "current_value": round(total_current, 2),
            "new_value": round(total_new, 2),
            "pnl": round(total_pnl, 2),
            "pct_change": round(client_pct * 100, 2),
        })

        # Check concentration limits (post-change)
        if total_new > 0:
            for _, row in group.iterrows():
                weight = row["new_value"] / total_new
                if weight > concentration_limit:
                    concentration_violations.append({
                        "client_name": client,
                        "ticker": row["ticker"],
                        "weight_pct": round(weight * 100, 2),
                        "limit_pct": round(concentration_limit * 100, 2),
                        "violation_type": "single_stock",
                    })

            # Sector concentration
            sector_weights = (
                group.groupby("sector")["new_value"].sum() / total_new
            )
            for sector, sw in sector_weights.items():
                if sw > sector_limit:
                    concentration_violations.append({
                        "client_name": client,
                        "sector": sector,
                        "weight_pct": round(sw * 100, 2),
                        "limit_pct": round(sector_limit * 100, 2),
                        "violation_type": "sector",
                    })

    # ── Sector exposure (aggregate) ─────────────────────────────────
    total_new_value = df["new_value"].sum()
    sector_exposure = {}
    if total_new_value > 0:
        for sector, grp in df.groupby("sector"):
            sv = grp["new_value"].sum()
            sector_exposure[sector] = {
                "value": round(sv, 2),
                "weight_pct": round(sv / total_new_value * 100, 2),
            }

    # ── Total exposure ──────────────────────────────────────────────
    total_current_value = df["current_value"].sum()
    total_pnl = df["pnl"].sum()
    affected_tickers = set(price_changes.keys()) & set(df["ticker"].unique())

    total_exposure = {
        "total_current_value": round(total_current_value, 2),
        "total_new_value": round(total_new_value, 2),
        "total_pnl": round(total_pnl, 2),
        "total_pct_change": (
            round(total_pnl / total_current_value * 100, 2)
            if total_current_value > 0 else 0.0
        ),
        "tickers_affected": sorted(affected_tickers),
    }

    affected_clients = {
        row["client_name"]
        for _, row in df.iterrows()
        if row["ticker"] in price_changes
    }

    return {
        "per_client_impact": per_client_impact,
        "concentration_violations": concentration_violations,
        "sector_exposure": sector_exposure,
        "total_exposure": total_exposure,
        "affected_clients_count": len(affected_clients),
    }


# ── Private helpers ─────────────────────────────────────────────────


def _error(msg: str) -> dict:
    """Return a standardised error envelope."""
    return {"error": True, "message": msg}
