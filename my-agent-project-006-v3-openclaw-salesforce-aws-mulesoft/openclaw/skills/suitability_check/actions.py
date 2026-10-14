"""suitability_check.run — DETERMINISTIC suitability rules. Never LLM.

Regulated surface. A junior team would run the math through an LLM and let
it "decide"; V3 does not. Every decision is reproducible from the input
alone — given the same payload, the same reason codes come back.

Rule matrix (concentration after proposed trade x risk profile x horizon):

  Conservative | 0-3y  | max single-ticker weight 5%,  max equity 60%
  Conservative | 3y+   | max single-ticker weight 7%,  max equity 70%
  Moderate     | 0-3y  | max single-ticker weight 8%,  max equity 70%
  Moderate     | 3y+   | max single-ticker weight 10%, max equity 85%
  Aggressive   | 0-3y  | max single-ticker weight 12%, max equity 85%
  Aggressive   | 3y+   | max single-ticker weight 15%, max equity 100%

  Any age>70 client: cap single-ticker 2 percentage points tighter.

  REVIEW band (within 1 pp of limit) — flag for RM but do not auto-FAIL.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


class RiskProfile(str, Enum):
    CONSERVATIVE = "conservative"
    MODERATE = "moderate"
    AGGRESSIVE = "aggressive"


class SuitabilityDecision(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class ProposedTrade(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=12)
    side: str = Field(..., description="buy | sell")
    delta_pct_of_portfolio: float = Field(
        ...,
        description="Pct points added to ticker weight (+buy, -sell).",
        ge=-100.0,
        le=100.0,
    )
    asset_class: str = Field("equity", description="equity | fixed_income | cash | alt")
    model_config = {"frozen": True}


class PortfolioSummary(BaseModel):
    current_ticker_pct: float = Field(0.0, ge=0.0, le=100.0)
    current_equity_pct: float = Field(0.0, ge=0.0, le=100.0)
    model_config = {"frozen": True}


class SuitabilityInput(BaseModel):
    client_risk_profile: RiskProfile
    time_horizon_years: float = Field(..., ge=0.0, le=60.0)
    age: Optional[int] = Field(None, ge=0, le=120)

    current_portfolio: PortfolioSummary
    proposed_trade: ProposedTrade

    principal_id: str = Field(..., min_length=1)
    client_contact_id: Optional[str] = None
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    model_config = {"frozen": True}


class SuitabilityOutput(BaseModel):
    status: SuitabilityDecision
    reasons: List[str] = Field(default_factory=list)
    risk_profile_matched: bool
    time_horizon_matched: bool
    concentration_compatible: bool
    projected_ticker_pct: float
    projected_equity_pct: float
    audit_row_id: str
    model_config = {"frozen": True}


_MATRIX = {
    (RiskProfile.CONSERVATIVE, "short"): (5.0, 60.0),
    (RiskProfile.CONSERVATIVE, "long"): (7.0, 70.0),
    (RiskProfile.MODERATE, "short"): (8.0, 70.0),
    (RiskProfile.MODERATE, "long"): (10.0, 85.0),
    (RiskProfile.AGGRESSIVE, "short"): (12.0, 85.0),
    (RiskProfile.AGGRESSIVE, "long"): (15.0, 100.0),
}


def _horizon_band(horizon_years: float) -> str:
    return "short" if horizon_years < 3.0 else "long"


def _limits_for(
    profile: RiskProfile, horizon_years: float, age: Optional[int]
) -> Tuple[float, float]:
    band = _horizon_band(horizon_years)
    max_ticker, max_equity = _MATRIX[(profile, band)]
    if age is not None and age > 70:
        max_ticker = max(1.0, max_ticker - 2.0)
    return max_ticker, max_equity


def _evaluate(payload: SuitabilityInput) -> Tuple[
    SuitabilityDecision, List[str], bool, bool, bool, float, float
]:
    """Pure evaluation — returns all output components. No side effects."""
    reasons: List[str] = []
    max_ticker, max_equity = _limits_for(
        payload.client_risk_profile, payload.time_horizon_years, payload.age
    )

    projected_ticker = (
        payload.current_portfolio.current_ticker_pct
        + payload.proposed_trade.delta_pct_of_portfolio
    )
    projected_equity = payload.current_portfolio.current_equity_pct + (
        payload.proposed_trade.delta_pct_of_portfolio
        if payload.proposed_trade.asset_class == "equity"
        else 0.0
    )

    profile_ok = True
    if (
        payload.client_risk_profile is RiskProfile.CONSERVATIVE
        and payload.proposed_trade.asset_class == "alt"
    ):
        profile_ok = False
        reasons.append("alt_assets_not_suitable_for_conservative_profile")

    horizon_ok = True
    if (
        payload.proposed_trade.side == "buy"
        and payload.proposed_trade.asset_class == "equity"
        and payload.time_horizon_years < 1.0
    ):
        horizon_ok = False
        reasons.append("equity_buy_with_time_horizon_under_1y")

    concentration_ok = True
    ticker_slack = max_ticker - projected_ticker
    if projected_ticker > max_ticker:
        concentration_ok = False
        reasons.append(
            f"single_ticker_concentration_{projected_ticker:.2f}pct_exceeds_"
            f"{max_ticker:.2f}pct"
        )
    equity_slack = max_equity - projected_equity
    if projected_equity > max_equity:
        concentration_ok = False
        reasons.append(
            f"equity_allocation_{projected_equity:.2f}pct_exceeds_"
            f"{max_equity:.2f}pct"
        )

    if not profile_ok or not horizon_ok or not concentration_ok:
        status = SuitabilityDecision.FAIL
    elif (
        (projected_ticker > 0 and ticker_slack <= 1.0)
        or (projected_equity > 0 and equity_slack <= 1.0)
    ):
        status = SuitabilityDecision.REVIEW
        reasons.append("within_1pp_of_concentration_limit")
    else:
        status = SuitabilityDecision.PASS

    return (
        status,
        reasons,
        profile_ok,
        horizon_ok,
        concentration_ok,
        projected_ticker,
        projected_equity,
    )


async def run(
    payload: SuitabilityInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> SuitabilityOutput:
    """Evaluate deterministically + write audit row."""
    client = mcp or get_shared_mock_client()
    (
        status,
        reasons,
        profile_ok,
        horizon_ok,
        conc_ok,
        proj_t,
        proj_e,
    ) = _evaluate(payload)

    audit = await audit_run(
        AuditInput(
            action=AuditAction.ADVISORY_QUERY,
            principal_id=payload.principal_id,
            agent_id="suitability_check",
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            client_contact_id=payload.client_contact_id,
            gate_trace=[
                {"gate": "suitability", "outcome": status.value, "reasons": reasons}
            ],
            payload={
                "ticker": payload.proposed_trade.ticker,
                "profile": payload.client_risk_profile.value,
                "horizon_years": payload.time_horizon_years,
                "projected_ticker_pct": proj_t,
                "projected_equity_pct": proj_e,
            },
        ),
        mcp=client,
    )

    return SuitabilityOutput(
        status=status,
        reasons=reasons,
        risk_profile_matched=profile_ok,
        time_horizon_matched=horizon_ok,
        concentration_compatible=conc_ok,
        projected_ticker_pct=proj_t,
        projected_equity_pct=proj_e,
        audit_row_id=audit.audit_row_id,
    )
