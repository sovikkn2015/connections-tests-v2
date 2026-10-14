"""compliance_screening.run — deterministic ALLOW/DENY/REVIEW for any proposed write.

DETERMINISTIC RULES, never LLM (steering rule 8). Four independent checks:

  1. Restricted list (static JSON, reloaded at skill init)
  2. MNPI watchlist (static JSON subset; raises the bar to REVIEW)
  3. Trading-window (business-day + market hours in America/New_York)
  4. Concentration limit (if current portfolio weight passed in)

Any DENY is a hard stop with no override flag. A DENY writes an audit row with
Action__c = COMPLIANCE_BLOCKED (steering rule 9) even though no MuleSoft call
was made.

The restricted list file is loaded once per process at module import via
`_load_list()`. Tests can point at a different file via `RESTRICTED_LIST_PATH`
env var.
"""

from __future__ import annotations

import json
import os
from datetime import date, datetime, time, timezone
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client


_DEFAULT_LIST_PATH = Path(__file__).parent / "restricted_list.json"


def _load_list(path: Optional[Path] = None) -> dict:
    """Read the restricted-list JSON. Env override honored for tests."""
    env_override = os.getenv("RESTRICTED_LIST_PATH")
    target = path or (Path(env_override) if env_override else _DEFAULT_LIST_PATH)
    with open(target, "r", encoding="utf-8") as fh:
        return json.load(fh)


_RESTRICTED = _load_list()


def reload_restricted_list(path: Optional[Path] = None) -> None:
    """Reload the restricted list from disk (test/runtime hot-reload)."""
    global _RESTRICTED
    _RESTRICTED = _load_list(path)


class Action(str, Enum):
    """The proposed action being screened."""

    PUBLISH_BRIEF = "publish_brief"
    SUBMIT_ORDER = "submit_order"
    CANCEL_ORDER = "cancel_order"
    MODIFY_ORDER = "modify_order"
    INITIATE_WIRE = "initiate_wire"


class ComplianceDecision(str, Enum):
    """Three-valued outcome. DENY is a hard stop with no override."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REVIEW = "REVIEW"


class ComplianceInput(BaseModel):
    """Payload for a single screening call."""

    ticker: str = Field(..., min_length=1, max_length=12)
    principal_id: str = Field(..., min_length=1)
    proposed_action: Action
    current_concentration_pct: Optional[float] = Field(
        None,
        ge=0.0,
        le=100.0,
        description="Current portfolio weight of `ticker` for the household, 0..100.",
    )

    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)
    client_contact_id: Optional[str] = None
    as_of: Optional[datetime] = None

    model_config = {"frozen": True}


class ComplianceOutput(BaseModel):
    """Decision + reasons + linkage back to the audit row (if DENY)."""

    decision: ComplianceDecision
    reasons: List[str] = Field(default_factory=list)
    restricted_list_hit: bool = False
    mnpi_flag: bool = False
    trading_window_open: bool = True
    concentration_ok: bool = True
    audit_row_id: Optional[str] = Field(
        None,
        description="Populated only when decision == DENY (steering rule 9).",
    )

    model_config = {"frozen": True}


_NY_TZ = ZoneInfo("America/New_York")


def _is_trading_window_open(now_utc: datetime) -> bool:
    """True on US business days between 9:30-16:00 America/New_York.

    Uses stdlib `zoneinfo` for DST-correct conversion (handles the spring-
    forward and fall-back Sundays without calendar-month approximations).
    """
    ny = now_utc.astimezone(_NY_TZ)
    if ny.weekday() >= 5:  # Sat/Sun
        return False
    return time(9, 30) <= ny.time() <= time(16, 0)


def _check_restricted(ticker: str, as_of_date: date) -> Tuple[bool, Optional[str]]:
    """Return (hit, reason) if ticker is in the restricted list today."""
    upper = ticker.upper()
    for entry in _RESTRICTED.get("entries", []):
        if entry["ticker"].upper() != upper:
            continue
        try:
            start = date.fromisoformat(entry["effective_from"])
            end = date.fromisoformat(entry["effective_until"])
        except (KeyError, ValueError):
            return True, entry.get("reason", "restricted")
        if start <= as_of_date <= end:
            return True, entry.get("reason", "restricted")
    return False, None


def _check_mnpi(ticker: str) -> bool:
    """Return True if ticker is on the MNPI watchlist."""
    return ticker.upper() in {t.upper() for t in _RESTRICTED.get("mnpi_watchlist", [])}


def _check_concentration(current_pct: Optional[float]) -> Tuple[bool, Optional[str]]:
    """Return (ok, reason) per house concentration limit."""
    limit = float(_RESTRICTED.get("house_concentration_limit_pct", 10.0))
    if current_pct is None:
        return True, None
    if current_pct > limit:
        return False, f"concentration {current_pct:.2f}% exceeds limit {limit:.2f}%"
    return True, None


async def run(
    payload: ComplianceInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> ComplianceOutput:
    """Evaluate all four deterministic checks; DENY writes an audit row."""
    client = mcp or get_shared_mock_client()
    now = payload.as_of or datetime.now(timezone.utc)

    reasons: List[str] = []

    restricted_hit, restricted_reason = _check_restricted(payload.ticker, now.date())
    if restricted_hit:
        reasons.append(f"restricted_list:{restricted_reason}")

    mnpi_flag = _check_mnpi(payload.ticker)
    if mnpi_flag:
        reasons.append("mnpi_watchlist_hit")

    trading_open = _is_trading_window_open(now)
    if not trading_open and payload.proposed_action in (
        Action.SUBMIT_ORDER,
        Action.MODIFY_ORDER,
    ):
        reasons.append("trading_window_closed")

    conc_ok, conc_reason = _check_concentration(payload.current_concentration_pct)
    if not conc_ok:
        reasons.append(conc_reason or "concentration_exceeded")

    # Decision lattice:
    # - restricted -> DENY
    # - concentration exceeded -> DENY
    # - trading window closed AND submit/modify order -> DENY
    # - mnpi_flag alone -> REVIEW
    # - otherwise -> ALLOW
    if restricted_hit:
        decision = ComplianceDecision.DENY
    elif not conc_ok:
        decision = ComplianceDecision.DENY
    elif not trading_open and payload.proposed_action in (
        Action.SUBMIT_ORDER,
        Action.MODIFY_ORDER,
    ):
        decision = ComplianceDecision.DENY
    elif mnpi_flag:
        decision = ComplianceDecision.REVIEW
    else:
        decision = ComplianceDecision.ALLOW

    audit_row_id: Optional[str] = None
    if decision is ComplianceDecision.DENY:
        audit = await audit_run(
            AuditInput(
                action=AuditAction.COMPLIANCE_BLOCKED,
                principal_id=payload.principal_id,
                agent_id="compliance_screening",
                session_id=payload.session_id,
                correlation_id=payload.correlation_id,
                client_contact_id=payload.client_contact_id,
                gate_trace=[
                    {"gate": "restricted_list", "outcome": restricted_hit},
                    {"gate": "mnpi_watchlist", "outcome": mnpi_flag},
                    {"gate": "trading_window", "outcome": trading_open},
                    {"gate": "concentration", "outcome": conc_ok},
                ],
                payload={
                    "ticker": payload.ticker,
                    "proposed_action": payload.proposed_action.value,
                    "reasons": reasons,
                },
            ),
            mcp=client,
        )
        audit_row_id = audit.audit_row_id

    return ComplianceOutput(
        decision=decision,
        reasons=reasons,
        restricted_list_hit=restricted_hit,
        mnpi_flag=mnpi_flag,
        trading_window_open=trading_open,
        concentration_ok=conc_ok,
        audit_row_id=audit_row_id,
    )
