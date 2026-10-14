"""portfolio_analytics.run — percentage-only book analytics for the RM.

Given a household_id, fetches MNPI-filtered positions via salesforce-crm MCP
and computes analytics that keep every number expressed as a percentage or
a dimensionless ratio. No dollar amounts. No shares.

Analytics:
  - position_weighted_returns (30d, YTD, 1y)
  - attribution (by sector, ticker)
  - concentration (top-5 weight, Herfindahl index)
  - beta_exposure (weighted average)
  - drawdown (pseudo max drawdown from synthesized series)
  - correlation_matrix (top-10 tickers by weight; sector/beta proxy)
  - risk_parity_decomposition (numpy if available, inverse-beta fallback)

Pure percentages. A junior team surfaces dollar P&L; we deliberately do not.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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


class PositionRow(BaseModel):
    """Percentage-only position representation."""

    ticker: str
    pct: float = Field(..., ge=0.0, le=100.0)
    sector: str = "unknown"
    beta: float = Field(1.0, ge=-5.0, le=5.0)
    ret_30d_pct: float = 0.0
    ret_ytd_pct: float = 0.0
    ret_1y_pct: float = 0.0
    model_config = {"frozen": True}


class PortfolioAnalyticsInput(BaseModel):
    household_id: str = Field(..., min_length=1)
    principal_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    positions_override: Optional[List[PositionRow]] = Field(
        None,
        description=(
            "If provided, skip the CRM fetch (useful for orchestrator-"
            "supplied rows or tests)."
        ),
    )
    model_config = {"frozen": True}


class PortfolioAnalyticsOutput(BaseModel):
    returns_pct: Dict[str, float] = Field(default_factory=dict)
    attribution: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    concentration: Dict[str, float] = Field(default_factory=dict)
    beta_weighted: float = 0.0
    max_drawdown_pct: float = 0.0
    correlation_matrix: Dict[str, Dict[str, float]] = Field(default_factory=dict)
    risk_parity: Dict[str, float] = Field(default_factory=dict)
    audit_row_id: str
    model_config = {"frozen": True}


def _weighted(rows: List[PositionRow], attr: str) -> float:
    total_weight = sum(r.pct for r in rows)
    if total_weight <= 0:
        return 0.0
    return sum(getattr(r, attr) * r.pct for r in rows) / total_weight


def _concentration(rows: List[PositionRow]) -> Dict[str, float]:
    sorted_rows = sorted(rows, key=lambda r: r.pct, reverse=True)
    top5 = sum(r.pct for r in sorted_rows[:5])
    hhi = sum(r.pct**2 for r in rows)
    return {
        "top_5_pct": round(top5, 4),
        "herfindahl": round(hhi, 4),
        "top_position_pct": round(sorted_rows[0].pct, 4) if sorted_rows else 0.0,
    }


def _attribution(rows: List[PositionRow]) -> Dict[str, Dict[str, float]]:
    """pct-point contribution to weighted 30d return, by sector and ticker."""
    total_pct = sum(r.pct for r in rows) or 1.0
    by_sector: Dict[str, float] = {}
    by_ticker: Dict[str, float] = {}
    for r in rows:
        contrib = (r.pct / total_pct) * r.ret_30d_pct
        by_sector[r.sector] = by_sector.get(r.sector, 0.0) + contrib
        by_ticker[r.ticker] = round(contrib, 4)
    return {
        "sector": {k: round(v, 4) for k, v in by_sector.items()},
        "ticker": by_ticker,
    }


def _max_drawdown(series: List[float]) -> float:
    if not series:
        return 0.0
    peak = series[0]
    max_dd = 0.0
    for v in series:
        if v > peak:
            peak = v
        if peak > 0:
            dd = (v - peak) / peak * 100.0
            if dd < max_dd:
                max_dd = dd
    return round(max_dd, 4)


def _synthesize_series(rows: List[PositionRow]) -> List[float]:
    """Lightweight pseudo-series for demo drawdown calc.

    Monthly snapshots only; we build a 4-point series {baseline, +1y/2,
    +1y - 30d, +1y} anchored to weighted returns so drawdown shape is
    repeatable.
    """
    baseline = 100.0
    ret30 = _weighted(rows, "ret_30d_pct") / 100.0
    ret1y = _weighted(rows, "ret_1y_pct") / 100.0
    mid = baseline * (1 + ret1y / 2.0)
    recent = baseline * (1 + ret1y - ret30)
    now = baseline * (1 + ret1y)
    return [baseline, mid, recent, now]


def _corr_matrix(rows: List[PositionRow]) -> Dict[str, Dict[str, float]]:
    """Proxy correlation matrix from sector + beta similarity.

    Same sector -> 0.70; same beta band (+/- 0.2) -> 0.35; else 0.15.
    Used as visualization aid, not portfolio optimization input.
    """
    top = sorted(rows, key=lambda r: r.pct, reverse=True)[:10]
    out: Dict[str, Dict[str, float]] = {}
    for ri in top:
        out[ri.ticker] = {}
        for rj in top:
            if ri.ticker == rj.ticker:
                out[ri.ticker][rj.ticker] = 1.0
                continue
            sector_match = ri.sector == rj.sector
            beta_match = abs(ri.beta - rj.beta) <= 0.2
            corr = 0.7 if sector_match else 0.35 if beta_match else 0.15
            out[ri.ticker][rj.ticker] = corr
    return out


def _risk_parity(rows: List[PositionRow]) -> Dict[str, float]:
    """Inverse-volatility-proxy risk-parity weights, normalized to 100."""
    if not rows:
        return {}
    top = sorted(rows, key=lambda r: r.pct, reverse=True)[:10]
    if _HAS_NUMPY:
        betas = np.array([max(abs(r.beta), 0.1) for r in top])
        inv = 1.0 / betas
        w = inv / inv.sum() * 100.0
        return {t.ticker: round(float(w[i]), 4) for i, t in enumerate(top)}
    betas = [max(abs(r.beta), 0.1) for r in top]
    inv_sum = sum(1.0 / b for b in betas)
    return {
        t.ticker: round((1.0 / betas[i]) / inv_sum * 100.0, 4)
        for i, t in enumerate(top)
    }


def _parse_position(row: Dict[str, Any]) -> Optional[PositionRow]:
    pct = row.get("pct_of_portfolio") or row.get("Pct_Of_Portfolio__c")
    if pct is None:
        return None
    return PositionRow(
        ticker=row.get("ticker") or row.get("Ticker__c", "UNKNOWN"),
        pct=float(pct),
        sector=row.get("sector") or row.get("Sector__c", "unknown"),
        beta=float(row.get("beta", 1.0)),
        ret_30d_pct=float(row.get("ret_30d_pct", 0.0)),
        ret_ytd_pct=float(row.get("ret_ytd_pct", 0.0)),
        ret_1y_pct=float(row.get("ret_1y_pct", 0.0)),
    )


async def run(
    payload: PortfolioAnalyticsInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> PortfolioAnalyticsOutput:
    """Fetch MNPI-filtered positions + compute analytics."""
    client = mcp or get_shared_mock_client()

    rows: List[PositionRow]
    if payload.positions_override is not None:
        rows = list(payload.positions_override)
    else:
        result = await client.call(
            server="salesforce-crm",
            tool="read_household_positions",
            arguments={
                "household_id": payload.household_id,
                "principal_id": payload.principal_id,
                "mnpi_filtered": True,
            },
        )
        rows = [
            p for p in (_parse_position(r) for r in result.get("positions", [])) if p
        ]

    returns = {
        "30d": round(_weighted(rows, "ret_30d_pct"), 4),
        "ytd": round(_weighted(rows, "ret_ytd_pct"), 4),
        "1y": round(_weighted(rows, "ret_1y_pct"), 4),
    }
    concentration = _concentration(rows)
    attribution = _attribution(rows)
    beta_w = round(_weighted(rows, "beta"), 4)
    max_dd = _max_drawdown(_synthesize_series(rows))
    corr = _corr_matrix(rows)
    rp = _risk_parity(rows)

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="portfolio_analytics",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            gate_trace=[
                {"gate": "crm_read", "outcome": "ok", "mnpi_filtered": True}
            ],
            payload={
                "household_id": payload.household_id,
                "position_count": len(rows),
                "top_concentration_pct": concentration.get("top_position_pct", 0.0),
            },
        ),
        mcp=client,
    )

    return PortfolioAnalyticsOutput(
        returns_pct=returns,
        attribution=attribution,
        concentration=concentration,
        beta_weighted=beta_w,
        max_drawdown_pct=max_dd,
        correlation_matrix=corr,
        risk_parity=rp,
        audit_row_id=audit.audit_row_id,
    )
