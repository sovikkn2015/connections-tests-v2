"""
Comparable Company Analysis.

Runs inside OpenClaw's Python sandbox.
Allowed imports: math, random, json, csv, numpy, pandas, scipy.
No external API calls — all data is passed in as parameters.
"""

import pandas as pd


# Metrics used for comparison (must exist in both target and peer dicts)
_COMP_METRICS = ["pe", "ev_ebitda", "ps", "pb", "ev_revenue"]


def run_comps(
    target_ticker: str,
    target_metrics: dict,
    peer_data: list[dict],
) -> dict:
    """
    Compare a target company against a peer group on valuation multiples.

    Parameters
    ----------
    target_ticker : str
        Ticker symbol of the target company (e.g. "CRM").
    target_metrics : dict
        Target's valuation metrics.  Expected keys:
        ``pe``, ``ev_ebitda``, ``ps``, ``price``, ``market_cap``.
        Values may be ``None`` for unavailable metrics.
    peer_data : list[dict]
        List of peer dicts, each containing at minimum:
        ``ticker``, ``name``, ``pe``, ``ev_ebitda``, ``ps``,
        ``price``, ``market_cap``.

    Returns
    -------
    dict
        relative_valuation, peer_ranking, implied_prices,
        sector_averages, narrative.
    """
    # ── Input validation ────────────────────────────────────────────
    if not target_ticker:
        return _error("target_ticker is required")
    if not target_metrics:
        return _error("target_metrics dict is required")
    if not peer_data:
        return _error("peer_data must contain at least one peer")

    df = pd.DataFrame(peer_data)

    # ── Sector averages (mean & median) ─────────────────────────────
    sector_averages = {}
    for metric in _COMP_METRICS:
        if metric not in df.columns:
            continue
        valid = df[metric].dropna()
        if valid.empty:
            sector_averages[metric] = {"mean": None, "median": None}
        else:
            sector_averages[metric] = {
                "mean": round(float(valid.mean()), 2),
                "median": round(float(valid.median()), 2),
            }

    # ── Relative valuation (premium / discount) ─────────────────────
    relative_valuation = {}
    for metric in _COMP_METRICS:
        target_val = target_metrics.get(metric)
        avg = sector_averages.get(metric, {})
        median = avg.get("median")
        if target_val is None or median is None or median == 0:
            relative_valuation[metric] = {
                "target": target_val,
                "peer_median": median,
                "premium_pct": None,
                "assessment": "insufficient data",
            }
            continue

        premium = (target_val - median) / abs(median)
        label = (
            "premium" if premium > 0.05
            else ("discount" if premium < -0.05 else "in-line")
        )
        relative_valuation[metric] = {
            "target": round(target_val, 2),
            "peer_median": round(median, 2),
            "premium_pct": round(premium * 100, 1),
            "assessment": label,
        }

    # ── Peer ranking per metric ─────────────────────────────────────
    peer_ranking = {}
    for metric in _COMP_METRICS:
        if metric not in df.columns:
            continue
        ranked = (
            df[["ticker", "name", metric]]
            .dropna(subset=[metric])
            .sort_values(metric, ascending=True)
            .reset_index(drop=True)
        )
        ranked.index = ranked.index + 1  # 1-based rank
        ranking_list = ranked.to_dict(orient="records")
        # Add target to ranking for context
        target_val = target_metrics.get(metric)
        if target_val is not None:
            target_entry = {"ticker": target_ticker, "name": f"{target_ticker} (TARGET)", metric: target_val}
            ranking_list.append(target_entry)
            ranking_list.sort(key=lambda x: x.get(metric) if x.get(metric) is not None else float("inf"))
        peer_ranking[metric] = ranking_list

    # ── Implied prices from peer median multiples ───────────────────
    implied_prices = _calculate_implied_prices(target_metrics, sector_averages)

    # ── Narrative summary ───────────────────────────────────────────
    narrative = _build_narrative(
        target_ticker, target_metrics, relative_valuation, implied_prices, len(peer_data),
    )

    return {
        "relative_valuation": relative_valuation,
        "peer_ranking": peer_ranking,
        "implied_prices": implied_prices,
        "sector_averages": sector_averages,
        "narrative": narrative,
    }


# ── Private helpers ─────────────────────────────────────────────────


def _error(msg: str) -> dict:
    return {"error": True, "message": msg}


def _calculate_implied_prices(
    target_metrics: dict,
    sector_averages: dict,
) -> dict:
    """
    Derive implied share prices by applying peer median multiples
    to the target's underlying fundamentals.
    """
    target_price = target_metrics.get("price")
    if target_price is None or target_price <= 0:
        return {"note": "target price unavailable — cannot compute implied prices"}

    implied = {}

    # P/E implied price
    target_pe = target_metrics.get("pe")
    median_pe = (sector_averages.get("pe") or {}).get("median")
    if target_pe and target_pe > 0 and median_pe and median_pe > 0:
        eps = target_price / target_pe
        implied["pe_implied_price"] = round(median_pe * eps, 2)
    else:
        implied["pe_implied_price"] = None

    # EV/EBITDA implied price
    target_ev_ebitda = target_metrics.get("ev_ebitda")
    median_ev_ebitda = (sector_averages.get("ev_ebitda") or {}).get("median")
    if (
        target_ev_ebitda
        and target_ev_ebitda > 0
        and median_ev_ebitda
        and median_ev_ebitda > 0
    ):
        ratio = median_ev_ebitda / target_ev_ebitda
        implied["ev_ebitda_implied_price"] = round(target_price * ratio, 2)
    else:
        implied["ev_ebitda_implied_price"] = None

    # P/S implied price
    target_ps = target_metrics.get("ps")
    median_ps = (sector_averages.get("ps") or {}).get("median")
    if target_ps and target_ps > 0 and median_ps and median_ps > 0:
        revenue_per_share = target_price / target_ps
        implied["ps_implied_price"] = round(median_ps * revenue_per_share, 2)
    else:
        implied["ps_implied_price"] = None

    # Composite (average of available implied prices)
    values = [v for v in implied.values() if isinstance(v, (int, float))]
    implied["composite_implied_price"] = (
        round(sum(values) / len(values), 2) if values else None
    )

    return implied


def _build_narrative(
    ticker: str,
    target_metrics: dict,
    relative_valuation: dict,
    implied_prices: dict,
    peer_count: int,
) -> str:
    """Generate a human-readable summary of the comps analysis."""
    parts = [f"{ticker} compared against {peer_count} peers:"]

    for metric, info in relative_valuation.items():
        target_val = target_metrics.get(metric)
        # Flag negative multiples
        if target_val is not None and target_val < 0:
            parts.append(f"  • {metric.upper()}: excluded (negative — company is loss-making on this metric)")
            continue
        prem = info.get("premium_pct")
        if prem is not None:
            direction = "premium" if prem > 0 else "discount"
            parts.append(
                f"  • {metric.upper()}: {abs(prem):.1f}% {direction} "
                f"vs peer median ({info['assessment']})"
            )
        else:
            parts.append(f"  • {metric.upper()}: insufficient data")

    composite = implied_prices.get("composite_implied_price")
    if composite is not None:
        parts.append(
            f"Composite implied price from peer multiples: ${composite:.2f}"
        )

    return "\n".join(parts)
