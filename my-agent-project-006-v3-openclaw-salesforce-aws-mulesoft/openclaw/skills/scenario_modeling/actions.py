"""scenario_modeling.run — Monte Carlo stress scenarios across a portfolio.

Inputs:
  - portfolio: list of {ticker, pct, beta, sector}
  - assumption distributions: rate_shock, ticker_drop, fx_move
  - paths: default 10000, deterministic with seed

Output:
  - var95_pct, cvar95_pct (5-pct-tail VaR/CVaR of portfolio % change)
  - percentiles: p1, p5, p50, p95, p99
  - worst_case_scenarios: top-3 scenarios by loss magnitude (with shock values)
  - summary: {paths, mean_pct, stdev_pct, skew, kurtosis_excess}

Pure numpy when available; stdlib-only fallback (slower but still deterministic).
"""

from __future__ import annotations

import math
import random
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client

try:
    import numpy as np  # type: ignore
    _HAS_NUMPY = True
except ImportError:  # pragma: no cover
    _HAS_NUMPY = False


class PortfolioRow(BaseModel):
    ticker: str
    pct: float = Field(..., ge=0.0, le=100.0)
    beta: float = Field(1.0, ge=-5.0, le=5.0)
    sector: str = "unknown"
    model_config = {"frozen": True}


class AssumptionDistribution(BaseModel):
    """Normal-ish shocks (mean, stdev) expressed in % or basis points."""

    rate_shock_bps_mean: float = 0.0
    rate_shock_bps_stdev: float = 50.0
    ticker_drop_pct_mean: float = 0.0
    ticker_drop_pct_stdev: float = 4.0
    fx_move_pct_mean: float = 0.0
    fx_move_pct_stdev: float = 2.0
    sector_rotation_pct_stdev: float = 3.0
    model_config = {"frozen": True}


class ScenarioModelingInput(BaseModel):
    portfolio: List[PortfolioRow] = Field(..., min_length=1)
    assumptions: AssumptionDistribution = Field(default_factory=AssumptionDistribution)
    paths: int = Field(10_000, ge=100, le=100_000)
    seed: Optional[int] = Field(42, description="Deterministic seed for tests.")

    principal_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    model_config = {"frozen": True}


class ScenarioModelingOutput(BaseModel):
    var95_pct: float
    cvar95_pct: float
    percentiles: Dict[str, float] = Field(default_factory=dict)
    worst_case_scenarios: List[Dict[str, Any]] = Field(default_factory=list)
    summary: Dict[str, float] = Field(default_factory=dict)
    paths_run: int
    used_numpy: bool
    audit_row_id: str
    model_config = {"frozen": True}


def _scenario_pnl_pct(
    portfolio: List[PortfolioRow],
    rate_bps: float,
    market_drop_pct: float,
    fx_pct: float,
) -> float:
    """Single-scenario portfolio % change.

    Model (deliberately simple, regulator-explainable):
      Δ_ticker = -beta_i * market_drop_pct                     (market beta)
                - 0.15 * (rate_bps / 100)                      (duration proxy)
                + 0.2 * fx_pct                                 (FX passthrough)
      Δ_portfolio = Σ_i (pct_i / 100) * Δ_ticker_i
    """
    total = 0.0
    for p in portfolio:
        delta = (
            -p.beta * market_drop_pct
            - 0.15 * (rate_bps / 100.0)
            + 0.2 * fx_pct
        )
        total += (p.pct / 100.0) * delta
    return total


def _run_mc_numpy(
    portfolio: List[PortfolioRow],
    a: AssumptionDistribution,
    paths: int,
    seed: Optional[int],
) -> Tuple[List[float], List[Dict[str, Any]]]:
    assert _HAS_NUMPY
    rng = np.random.default_rng(seed)
    rate = rng.normal(a.rate_shock_bps_mean, a.rate_shock_bps_stdev, paths)
    mkt = rng.normal(a.ticker_drop_pct_mean, a.ticker_drop_pct_stdev, paths)
    fx = rng.normal(a.fx_move_pct_mean, a.fx_move_pct_stdev, paths)

    betas = np.array([p.beta for p in portfolio])
    weights = np.array([p.pct / 100.0 for p in portfolio])

    market_term = -np.outer(mkt, betas)  # (paths, n)
    rate_term = -0.15 * (rate / 100.0)
    fx_term = 0.2 * fx
    delta_ticker = market_term + rate_term[:, None] + fx_term[:, None]
    pnl_pct = delta_ticker @ weights
    pnl_list = pnl_pct.tolist()

    idx_sorted = np.argsort(pnl_pct)[:3]
    worst = [
        {
            "path_index": int(i),
            "pnl_pct": round(float(pnl_pct[i]), 4),
            "rate_shock_bps": round(float(rate[i]), 2),
            "market_drop_pct": round(float(mkt[i]), 4),
            "fx_move_pct": round(float(fx[i]), 4),
        }
        for i in idx_sorted
    ]
    return pnl_list, worst


def _run_mc_stdlib(
    portfolio: List[PortfolioRow],
    a: AssumptionDistribution,
    paths: int,
    seed: Optional[int],
) -> Tuple[List[float], List[Dict[str, Any]]]:
    rng = random.Random(seed)
    pnls: List[float] = []
    trace: List[Tuple[int, float, float, float, float]] = []
    for i in range(paths):
        rate = rng.gauss(a.rate_shock_bps_mean, a.rate_shock_bps_stdev)
        mkt = rng.gauss(a.ticker_drop_pct_mean, a.ticker_drop_pct_stdev)
        fx = rng.gauss(a.fx_move_pct_mean, a.fx_move_pct_stdev)
        pnl = _scenario_pnl_pct(portfolio, rate, mkt, fx)
        pnls.append(pnl)
        trace.append((i, pnl, rate, mkt, fx))
    trace_sorted = sorted(trace, key=lambda t: t[1])[:3]
    worst = [
        {
            "path_index": t[0],
            "pnl_pct": round(t[1], 4),
            "rate_shock_bps": round(t[2], 2),
            "market_drop_pct": round(t[3], 4),
            "fx_move_pct": round(t[4], 4),
        }
        for t in trace_sorted
    ]
    return pnls, worst


def _percentile_sorted(sorted_vals: List[float], p: float) -> float:
    """p-th percentile of a pre-sorted list (0 <= p <= 100)."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * p / 100.0
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


async def run(
    payload: ScenarioModelingInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> ScenarioModelingOutput:
    """Run Monte Carlo; return VaR/CVaR + percentiles + worst scenarios."""
    client = mcp or get_shared_mock_client()
    runner = _run_mc_numpy if _HAS_NUMPY else _run_mc_stdlib
    pnls, worst_cases = runner(
        list(payload.portfolio), payload.assumptions, payload.paths, payload.seed
    )
    sorted_pnls = sorted(pnls)

    var95 = _percentile_sorted(sorted_pnls, 5.0)
    cutoff_idx = max(1, int(len(sorted_pnls) * 0.05))
    cvar95 = sum(sorted_pnls[:cutoff_idx]) / cutoff_idx

    percentiles = {
        "p1": round(_percentile_sorted(sorted_pnls, 1.0), 4),
        "p5": round(_percentile_sorted(sorted_pnls, 5.0), 4),
        "p50": round(_percentile_sorted(sorted_pnls, 50.0), 4),
        "p95": round(_percentile_sorted(sorted_pnls, 95.0), 4),
        "p99": round(_percentile_sorted(sorted_pnls, 99.0), 4),
    }

    mean = sum(pnls) / len(pnls)
    var = sum((x - mean) ** 2 for x in pnls) / len(pnls)
    stdev = math.sqrt(var) if var > 0 else 0.0
    if stdev > 0:
        skew = sum((x - mean) ** 3 for x in pnls) / (len(pnls) * stdev**3)
        kurt = sum((x - mean) ** 4 for x in pnls) / (len(pnls) * stdev**4) - 3.0
    else:
        skew = 0.0
        kurt = 0.0

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="scenario_modeling",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            gate_trace=[
                {"gate": "monte_carlo", "outcome": "ok", "paths": payload.paths}
            ],
            payload={
                "var95_pct": round(var95, 4),
                "cvar95_pct": round(cvar95, 4),
                "portfolio_size": len(payload.portfolio),
                "used_numpy": _HAS_NUMPY,
            },
        ),
        mcp=client,
    )

    return ScenarioModelingOutput(
        var95_pct=round(var95, 4),
        cvar95_pct=round(cvar95, 4),
        percentiles=percentiles,
        worst_case_scenarios=worst_cases,
        summary={
            "paths": float(payload.paths),
            "mean_pct": round(mean, 4),
            "stdev_pct": round(stdev, 4),
            "skew": round(skew, 4),
            "kurtosis_excess": round(kurt, 4),
        },
        paths_run=payload.paths,
        used_numpy=_HAS_NUMPY,
        audit_row_id=audit.audit_row_id,
    )
