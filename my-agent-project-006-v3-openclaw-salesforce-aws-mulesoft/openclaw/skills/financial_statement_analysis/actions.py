"""financial_statement_analysis.run — tool dispatcher for deterministic analytics.

The caller (statement_specialist sub-agent) picks an `analysis_type` enum;
this skill routes to the corresponding calculator in `_calculators.py`.

No LLM calls. Every number is deterministic and reproducible from the
statements alone.
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client
from . import _calculators as calc
from ._xbrl_parser import BalanceSheet, CashFlow, IncomeStatement


class AnalysisType(str, Enum):
    GROWTH_RATE = "growth_rate"
    MARGINS = "margins"
    RETURNS = "returns"
    COMMON_SIZE = "common_size"
    DCF = "dcf"
    MONTE_CARLO_VALUATION = "monte_carlo_valuation"
    ALTMAN_Z = "altman_z"
    PIOTROSKI_F = "piotroski_f"
    BENEISH_M = "beneish_m"
    COMPARE_PEERS = "compare_peers"


class FSAInput(BaseModel):
    """Tool dispatcher input. Fields populated per analysis_type."""

    analysis_type: AnalysisType
    ticker: str = Field(..., min_length=1, max_length=12)

    income_current: Optional[IncomeStatement] = None
    income_prior: Optional[IncomeStatement] = None
    balance_current: Optional[BalanceSheet] = None
    balance_prior: Optional[BalanceSheet] = None
    cashflow_current: Optional[CashFlow] = None

    series: Optional[List[float]] = None

    dcf_assumptions: Optional[Dict[str, float]] = None
    mc_assumptions: Optional[Dict[str, float]] = None

    peer_tickers: Optional[List[str]] = None
    peer_metrics: Optional[List[str]] = None
    peer_as_of: Optional[str] = None
    peer_statements: Optional[
        Dict[str, Tuple[IncomeStatement, BalanceSheet, CashFlow]]
    ] = Field(
        None,
        description=(
            "Map ticker -> (income, balance, cashflow). The caller pre-fetches "
            "these from sec-edgar MCP and passes them through."
        ),
    )

    principal_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    model_config = {"frozen": True, "arbitrary_types_allowed": True}


class FSAOutput(BaseModel):
    analysis_type: AnalysisType
    ticker: str
    result: Dict[str, Any]
    audit_row_id: str
    model_config = {"frozen": True}


def _require(value: Any, name: str) -> Any:
    if value is None:
        raise ValueError(f"{name} is required for this analysis_type")
    return value


def _dispatch(payload: FSAInput) -> Dict[str, Any]:
    """Pure dispatcher — no audit here. Called by `run()` under audit."""
    t = payload.analysis_type

    if t is AnalysisType.GROWTH_RATE:
        return {"growth_rate": calc.growth_rate(_require(payload.series, "series"))}

    if t is AnalysisType.MARGINS:
        inc = _require(payload.income_current, "income_current")
        return {
            "gross_margin": calc.gross_margin(inc),
            "operating_margin": calc.operating_margin(inc),
            "net_margin": calc.net_margin(inc),
        }

    if t is AnalysisType.RETURNS:
        inc = _require(payload.income_current, "income_current")
        bs = _require(payload.balance_current, "balance_current")
        return {
            "roe": calc.roe(inc, bs),
            "roa": calc.roa(inc, bs),
            "roic": calc.roic(inc, bs),
        }

    if t is AnalysisType.COMMON_SIZE:
        inc = _require(payload.income_current, "income_current")
        bs = _require(payload.balance_current, "balance_current")
        return {
            "income_pct": calc.common_size_income(inc),
            "balance_pct": calc.common_size_balance(bs),
        }

    if t is AnalysisType.DCF:
        a = _require(payload.dcf_assumptions, "dcf_assumptions")
        return calc.dcf(
            fcf_year_1=float(a["fcf_year_1"]),
            growth_rate_pct=float(a["growth_rate_pct"]),
            discount_rate_pct=float(a["discount_rate_pct"]),
            terminal_growth_pct=float(a.get("terminal_growth_pct", 2.5)),
            years=int(a.get("years", 10)),
        )

    if t is AnalysisType.MONTE_CARLO_VALUATION:
        a = _require(payload.mc_assumptions, "mc_assumptions")
        return calc.monte_carlo_valuation(
            fcf_year_1_mean=float(a["fcf_year_1_mean"]),
            fcf_year_1_stdev=float(a.get("fcf_year_1_stdev", 0.0)),
            growth_rate_mean_pct=float(a["growth_rate_mean_pct"]),
            growth_rate_stdev_pct=float(a.get("growth_rate_stdev_pct", 1.0)),
            discount_rate_mean_pct=float(a["discount_rate_mean_pct"]),
            discount_rate_stdev_pct=float(a.get("discount_rate_stdev_pct", 0.5)),
            paths=int(a.get("paths", 10_000)),
            seed=int(a.get("seed", 42)),
            years=int(a.get("years", 10)),
            terminal_growth_pct=float(a.get("terminal_growth_pct", 2.5)),
        )

    if t is AnalysisType.ALTMAN_Z:
        inc = _require(payload.income_current, "income_current")
        bs = _require(payload.balance_current, "balance_current")
        return {"z_score": calc.altman_z_score(inc, bs)}

    if t is AnalysisType.PIOTROSKI_F:
        return {"f_score": calc.piotroski_f_score(
            _require(payload.income_current, "income_current"),
            _require(payload.income_prior, "income_prior"),
            _require(payload.balance_current, "balance_current"),
            _require(payload.balance_prior, "balance_prior"),
            _require(payload.cashflow_current, "cashflow_current"),
        )}

    if t is AnalysisType.BENEISH_M:
        return {"m_score": calc.beneish_m_score(
            _require(payload.income_current, "income_current"),
            _require(payload.income_prior, "income_prior"),
            _require(payload.balance_current, "balance_current"),
            _require(payload.balance_prior, "balance_prior"),
            _require(payload.cashflow_current, "cashflow_current"),
        )}

    if t is AnalysisType.COMPARE_PEERS:
        return {"matrix": calc.compare_peers(
            _require(payload.peer_tickers, "peer_tickers"),
            _require(payload.peer_metrics, "peer_metrics"),
            payload.peer_as_of or "",
            _require(payload.peer_statements, "peer_statements"),
        )}

    raise ValueError(f"unsupported analysis_type {t!r}")


async def run(
    payload: FSAInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> FSAOutput:
    """Dispatch to the correct calculator + write an advisory-query audit row."""
    client = mcp or get_shared_mock_client()
    result = _dispatch(payload)

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="financial_statement_analysis",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            gate_trace=[{"gate": "fsa", "analysis": payload.analysis_type.value}],
            payload={
                "ticker": payload.ticker,
                "analysis_type": payload.analysis_type.value,
                "result_keys": sorted(result.keys()),
            },
        ),
        mcp=client,
    )

    return FSAOutput(
        analysis_type=payload.analysis_type,
        ticker=payload.ticker.upper(),
        result=result,
        audit_row_id=audit.audit_row_id,
    )
