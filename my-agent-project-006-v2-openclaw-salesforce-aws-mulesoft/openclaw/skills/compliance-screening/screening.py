"""
Compliance Screening — FINRA pre-trade compliance checks.

Implements the 4 checks from compliance-screening/SKILL.md:
  1. Restricted list check
  2. MNPI check (30-day lookback)
  3. Trading window check (14-day earnings blackout)
  4. Concentration check (single-stock >10%, sector >25%)

Architecture rules:
  - No credentials in code — all via function parameters
  - No LLM imports — pure Salesforce REST API calls
  - Every check wrapped in try/except — no crashes
  - SOQL uses proper escaping (no raw string interpolation)
"""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote as url_quote

import requests

from .bypass_detector import scan_for_bypass

logger = logging.getLogger("compliance-screening")

SF_API_VERSION = "v66.0"


def _escape_soql(value: str) -> str:
    """
    Escape a string value for safe SOQL injection.

    Removes characters that could break SOQL queries and escapes
    single quotes per SOQL spec.
    """
    # Strip anything that isn't alphanumeric, dot, dash, or underscore
    sanitized = re.sub(r"[^a-zA-Z0-9._\-]", "", value)
    # Escape single quotes for SOQL
    return sanitized.replace("'", "\\'")


def _sf_soql(query: str, sf_instance_url: str, sf_access_token: str) -> dict:
    """Execute a SOQL query via Salesforce REST API."""
    encoded = url_quote(query, safe="")
    url = f"{sf_instance_url}/services/data/{SF_API_VERSION}/query/?q={encoded}"
    try:
        resp = requests.get(
            url,
            headers={"Authorization": f"Bearer {sf_access_token}"},
            timeout=15,
        )
        resp.raise_for_status()
        return resp.json()
    except requests.RequestException as exc:
        logger.error("SOQL query failed: %s — %s", query[:100], exc)
        return {"records": [], "error": str(exc)}


# ── Individual checks ───────────────────────────────────────────────


def _check_restricted_list(
    ticker: str, sf_instance_url: str, sf_access_token: str,
) -> tuple[str, list[str]]:
    """Check if ticker is on the restricted list. Returns (status, blocks)."""
    try:
        safe_ticker = _escape_soql(ticker)
        query = (
            "SELECT Action__c, Query__c, Timestamp__c "
            "FROM IR_Audit_Log__c "
            f"WHERE Action__c = 'RESTRICTED_LIST_ADD' AND Query__c LIKE '%{safe_ticker}%' "
            "ORDER BY Timestamp__c DESC LIMIT 1"
        )
        resp = _sf_soql(query, sf_instance_url, sf_access_token)
        if resp.get("records"):
            return "BLOCK", [f"{ticker} is on the restricted list"]
        return "CLEAR", []
    except Exception as exc:
        logger.error("Restricted list check failed: %s", exc)
        return "ERROR", [f"Restricted list check error: {exc}"]


def _check_mnpi(
    ticker: str, sf_instance_url: str, sf_access_token: str,
) -> tuple[str, list[str]]:
    """Check for MNPI flags in last 30 days. Returns (status, warnings)."""
    try:
        safe_ticker = _escape_soql(ticker)
        query = (
            "SELECT MNPI_Flag__c, Query__c, Timestamp__c "
            "FROM IR_Audit_Log__c "
            f"WHERE MNPI_Flag__c = true AND Query__c LIKE '%{safe_ticker}%' "
            "AND Timestamp__c >= LAST_N_DAYS:30 "
            "ORDER BY Timestamp__c DESC"
        )
        resp = _sf_soql(query, sf_instance_url, sf_access_token)
        if resp.get("records"):
            count = len(resp["records"])
            return "WARN", [f"MNPI flags found for {ticker} in last 30 days ({count} record(s))"]
        return "CLEAR", []
    except Exception as exc:
        logger.error("MNPI check failed: %s", exc)
        return "ERROR", [f"MNPI check error: {exc}"]


def _check_trading_window(
    ticker: str, sf_instance_url: str, sf_access_token: str,
) -> tuple[str, list[str]]:
    """Check if ticker is in earnings blackout (14 days before earnings). Returns (status, warnings)."""
    try:
        safe_ticker = _escape_soql(ticker)
        query = (
            "SELECT Earnings_Date__c, Reason__c "
            "FROM IR_Watchlist__c "
            f"WHERE Company__r.Ticker__c = '{safe_ticker}'"
        )
        resp = _sf_soql(query, sf_instance_url, sf_access_token)
        for entry in resp.get("records", []):
            earnings_date = entry.get("Earnings_Date__c")
            if not earnings_date:
                continue
            try:
                ed = datetime.fromisoformat(earnings_date.replace("Z", "+00:00"))
                days_until = (ed - datetime.now(timezone.utc)).days
                if 0 <= days_until <= 14:
                    return "BLACKOUT", [
                        f"{ticker} is in earnings blackout period "
                        f"(earnings in {days_until} day(s))"
                    ]
            except (ValueError, TypeError):
                continue
        return "OPEN", []
    except Exception as exc:
        logger.error("Trading window check failed: %s", exc)
        return "ERROR", [f"Trading window check error: {exc}"]


def _check_concentration(
    ticker: str,
    holdings_summary: dict[str, Any] | None = None,
) -> tuple[str, list[str]]:
    """
    Check portfolio concentration limits.

    Parameters
    ----------
    ticker : str
        The ticker being evaluated.
    holdings_summary : dict | None
        LLM-safe holdings summary from mnpi_filter.summarize_holdings_safe().
        Expected keys: client_count, sector_exposure, record_count, top_holdings.
        If None, skip concentration check (no holdings data available).

    Returns
    -------
    tuple[str, list[str]]
        (status, warnings) — status is WITHIN_LIMITS, WARN, or SKIPPED.
    """
    if not holdings_summary:
        return "SKIPPED", []

    try:
        warnings: list[str] = []
        record_count = holdings_summary.get("record_count", 0)

        if record_count == 0:
            return "SKIPPED", []

        # Single-stock concentration: if ticker appears in >10% of holding records
        top_holdings = holdings_summary.get("top_holdings", [])
        client_count = holdings_summary.get("client_count", 0)

        # Approximate single-stock concentration by record frequency
        if ticker in top_holdings and record_count > 0:
            if client_count > 0:
                ticker_rank = top_holdings.index(ticker) if ticker in top_holdings else -1
                if ticker_rank == 0 and client_count >= 10:
                    warnings.append(
                        f"{ticker} is the #1 held ticker across {client_count} client(s) — "
                        f"review single-stock concentration (>10% threshold)"
                    )

        # Sector concentration: if any sector has >25% of total records
        sector_exposure = holdings_summary.get("sector_exposure", {})
        for sector, count in sector_exposure.items():
            if record_count > 0 and (count / record_count) > 0.25:
                pct = round((count / record_count) * 100, 1)
                warnings.append(
                    f"Sector '{sector}' represents {pct}% of holdings "
                    f"({count}/{record_count}) — exceeds 25% threshold"
                )

        status = "WARN" if warnings else "WITHIN_LIMITS"
        return status, warnings

    except Exception as exc:
        logger.error("Concentration check failed: %s", exc)
        return "ERROR", [f"Concentration check error: {exc}"]


# ── Main entry point ────────────────────────────────────────────────


def run_compliance_screening(
    ticker: str,
    sf_instance_url: str,
    sf_access_token: str,
    analyst: str,
    holdings_summary: dict[str, Any] | None = None,
) -> dict:
    """
    Run all 4 FINRA compliance checks for a ticker.

    Parameters
    ----------
    ticker : str
        Stock ticker symbol.
    sf_instance_url : str
        Salesforce instance URL.
    sf_access_token : str
        Salesforce OAuth bearer token.
    analyst : str
        Analyst name for audit trail.
    holdings_summary : dict | None
        Optional LLM-safe holdings summary for concentration check.
        Should come from mnpi_filter.summarize_holdings_safe().

    Returns
    -------
    dict
        {
            "ticker": "NVDA",
            "restricted_list": "CLEAR",
            "mnpi_check": "CLEAR",
            "trading_window": "OPEN",
            "concentration": "WITHIN_LIMITS",
            "overall": "PASS",
            "warnings": [],
            "blocks": [],
        }
    """
    safe_ticker = ticker.upper().strip()
    all_warnings: list[str] = []
    all_blocks: list[str] = []

    # 1. Restricted list
    restricted_status, restricted_blocks = _check_restricted_list(
        safe_ticker, sf_instance_url, sf_access_token,
    )
    all_blocks.extend(restricted_blocks)

    # 2. MNPI check
    mnpi_status, mnpi_warnings = _check_mnpi(
        safe_ticker, sf_instance_url, sf_access_token,
    )
    all_warnings.extend(mnpi_warnings)

    # 3. Trading window
    window_status, window_warnings = _check_trading_window(
        safe_ticker, sf_instance_url, sf_access_token,
    )
    all_warnings.extend(window_warnings)

    # 4. Concentration
    conc_status, conc_warnings = _check_concentration(
        safe_ticker, holdings_summary,
    )
    all_warnings.extend(conc_warnings)

    # Determine overall status
    overall = "PASS"
    if all_blocks:
        overall = "FAIL"
    elif all_warnings:
        overall = "WARN"

    return {
        "ticker": safe_ticker,
        "restricted_list": restricted_status,
        "mnpi_check": mnpi_status,
        "trading_window": window_status,
        "concentration": conc_status,
        "overall": overall,
        "warnings": all_warnings,
        "blocks": all_blocks,
    }


__all__ = ["run_compliance_screening"]


# ── Phase 6 entry point for mulesoft-api skill ──────────────────────


def mulesoft_action_precheck(action_plan: Any, context: dict[str, Any]) -> dict[str, Any]:
    """Phase 6 integration point — called by openclaw/skills/mulesoft-api/actions.py.

    This is the compliance gate that runs BEFORE HITL, BEFORE any MuleSoft call.
    Returns a dict shaped for actions._execute_with_gates:

        {"decision": "ALLOW" | "DENY", "reason": str}

    Sequence:
      1. Bypass-phrase scan on plan.summary (v2 steering rule 8, 20).
         If detected -> DENY immediately, no SOQL calls.
      2. Full SOQL-based screening if bypass scan is clean.

    The bypass scan runs first because it is fast (regex only) and catches
    adversarial text before we burn SOQL queries on it.

    Parameters
    ----------
    action_plan : ActionPlan (duck-typed from mulesoft-api skill)
        Expected attributes: summary, arguments (dict with optional ticker), client_id.
    context : dict
        Expected keys (all optional, skip checks if missing):
            sf_instance_url, sf_access_token, analyst, holdings_summary
    """
    # Step 1 — bypass scan (fail-fast, no network calls)
    scan = scan_for_bypass(getattr(action_plan, "summary", "") or "")
    if scan.detected:
        logger.warning(
            "compliance.bypass_detected phrase='%s' reason='%s' client=%s",
            scan.matched_phrase, scan.reason, getattr(action_plan, "client_id", "?"),
        )
        return scan.as_compliance_result()

    # Step 2 — SOQL-based screening (only if we have SF credentials + a ticker)
    sf_url = context.get("sf_instance_url")
    sf_token = context.get("sf_access_token")
    ticker = (getattr(action_plan, "arguments", {}) or {}).get("ticker")

    if not (sf_url and sf_token and ticker):
        # No SF context -> cannot run full screening. This is ALLOW-with-caveat:
        # HITL is still required (actions.py enforces that), audit still runs.
        # This path is used by the mock test harness.
        return {
            "decision": "ALLOW",
            "reason": "Bypass scan clean; SOQL screening skipped (no SF context)",
        }

    screening = run_compliance_screening(
        ticker=ticker,
        sf_instance_url=sf_url,
        sf_access_token=sf_token,
        analyst=context.get("analyst", "unknown"),
        holdings_summary=context.get("holdings_summary"),
    )

    if screening.get("overall") == "FAIL":
        reason = "; ".join(screening.get("blocks", ["unknown"]))
        return {"decision": "DENY", "reason": f"Compliance FAIL: {reason}"}

    if screening.get("overall") == "WARN":
        warnings = "; ".join(screening.get("warnings", []))
        # WARN does NOT deny — HITL still runs so the human can decide.
        # We return ALLOW but include warnings in the reason for audit visibility.
        return {
            "decision": "ALLOW",
            "reason": f"Compliance WARN (HITL must weigh): {warnings}",
        }

    return {"decision": "ALLOW", "reason": "All compliance checks passed"}


__all__.append("mulesoft_action_precheck")
