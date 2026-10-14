"""
Portfolio rebalancing calculator.

Runs inside OpenClaw's Python sandbox.
Allowed imports: math, random, json, csv, numpy, pandas, scipy.
No external API calls — all data is passed in as parameters.
"""

import pandas as pd


# Assumed commission per trade (flat fee model)
_COMMISSION_PER_TRADE = 4.95


def calculate_rebalance(
    holdings: list[dict],
    target_allocation: dict,
    total_portfolio_value: float,
    commission_per_trade: float = 4.95,
) -> dict:
    """
    Calculate trades needed to rebalance a portfolio toward target
    sector weights.

    Parameters
    ----------
    holdings : list[dict]
        Each dict must contain:
        ``ticker``, ``shares``, ``current_price``, ``sector``.
    target_allocation : dict
        Mapping of sector → target weight (e.g. {"Technology": 0.35}).
        Weights should sum to 1.0 (or close).  Sectors not listed
        have an implicit target of 0.
    total_portfolio_value : float
        Total portfolio value used to compute target dollar amounts.
    commission_per_trade : float
        Flat commission per trade in dollars (default $4.95).

    Returns
    -------
    dict
        current_allocation, drift, trades,
        post_rebalance_allocation, estimated_commissions, warnings.
    """
    # ── Input validation ────────────────────────────────────────────
    if not holdings:
        return _error("holdings list is empty")
    if not target_allocation:
        return _error("target_allocation is required")
    if total_portfolio_value <= 0:
        return _error("total_portfolio_value must be positive")

    warnings: list[str] = []

    # Warn if target allocation doesn't sum to ~100%
    target_sum = sum(target_allocation.values())
    if abs(target_sum - 1.0) > 0.05:
        warnings.append(f"Target allocation sums to {target_sum:.2%}, not 100%")

    df = pd.DataFrame(holdings)
    required = {"ticker", "shares", "current_price", "sector"}
    missing = required - set(df.columns)
    if missing:
        return _error(f"holdings missing required fields: {missing}")

    # ── Current allocation by sector ────────────────────────────────
    df["current_value"] = df["shares"] * df["current_price"]
    sector_values = df.groupby("sector")["current_value"].sum()
    actual_total = sector_values.sum()

    if actual_total <= 0:
        return _error("total holdings value is zero or negative")

    # Gather all sectors (from holdings + targets)
    all_sectors = sorted(
        set(sector_values.index) | set(target_allocation.keys())
    )

    current_allocation = {}
    drift = {}
    for sector in all_sectors:
        current_val = float(sector_values.get(sector, 0.0))
        current_weight = current_val / actual_total
        target_weight = target_allocation.get(sector, 0.0)
        current_allocation[sector] = round(current_weight, 4)
        drift[sector] = {
            "current_pct": round(current_weight * 100, 2),
            "target_pct": round(target_weight * 100, 2),
            "drift_pct": round((current_weight - target_weight) * 100, 2),
        }

    # ── Compute required trades ─────────────────────────────────────
    trades = []
    post_values = dict(sector_values)  # mutable copy

    for sector in all_sectors:
        target_value = total_portfolio_value * target_allocation.get(sector, 0.0)
        current_val = float(sector_values.get(sector, 0.0))
        delta = target_value - current_val

        if abs(delta) < 1.0:
            continue  # skip negligible rebalances

        # Pick a representative ticker from this sector
        sector_holdings = df[df["sector"] == sector].copy()

        if delta > 0:
            # Need to BUY more of this sector
            if sector_holdings.empty:
                trades.append({
                    "sector": sector,
                    "ticker": "NEW_POSITION",
                    "action": "BUY",
                    "shares": None,
                    "estimated_value": round(delta, 2),
                    "note": "No existing position — new ticker needed",
                })
            else:
                # Distribute buy across existing tickers by weight
                sector_total = sector_holdings["current_value"].sum()
                for _, row in sector_holdings.iterrows():
                    if sector_total > 0:
                        weight = row["current_value"] / sector_total
                    else:
                        weight = 1.0 / len(sector_holdings)
                    alloc = delta * weight
                    if row["current_price"] > 0:
                        share_count = int(alloc / row["current_price"])
                    else:
                        share_count = 0
                    if share_count > 0:
                        trades.append({
                            "sector": sector,
                            "ticker": row["ticker"],
                            "action": "BUY",
                            "shares": share_count,
                            "estimated_value": round(
                                share_count * row["current_price"], 2
                            ),
                        })
        else:
            # Need to SELL from this sector
            sell_amount = abs(delta)
            if not sector_holdings.empty:
                sector_total = sector_holdings["current_value"].sum()
                for _, row in sector_holdings.iterrows():
                    if sector_total > 0:
                        weight = row["current_value"] / sector_total
                    else:
                        weight = 1.0 / len(sector_holdings)
                    alloc = sell_amount * weight
                    if row["current_price"] > 0:
                        share_count = int(alloc / row["current_price"])
                    else:
                        share_count = 0
                    if share_count > 0:
                        trades.append({
                            "sector": sector,
                            "ticker": row["ticker"],
                            "action": "SELL",
                            "shares": share_count,
                            "estimated_value": round(
                                share_count * row["current_price"], 2
                            ),
                        })

        post_values[sector] = target_value

    # Filter out trades below minimum value threshold
    MIN_TRADE_VALUE = 100.0
    trades = [t for t in trades if t.get("estimated_value", 0) >= MIN_TRADE_VALUE or t.get("shares") is None]

    # ── Post-rebalance allocation ───────────────────────────────────
    post_total = sum(post_values.values())
    post_rebalance_allocation = {}
    for sector in all_sectors:
        pv = post_values.get(sector, 0.0)
        post_rebalance_allocation[sector] = (
            round(pv / post_total * 100, 2) if post_total > 0 else 0.0
        )

    # ── Estimated commissions ───────────────────────────────────────
    trade_count = len([t for t in trades if t.get("shares")])
    estimated_commissions = round(trade_count * commission_per_trade, 2)

    return {
        "current_allocation": current_allocation,
        "drift": drift,
        "trades": trades,
        "post_rebalance_allocation": post_rebalance_allocation,
        "estimated_commissions": estimated_commissions,
        "warnings": warnings,
    }


# ── Private helpers ─────────────────────────────────────────────────


def _error(msg: str) -> dict:
    """Return a standardised error envelope."""
    return {"error": True, "message": msg}
