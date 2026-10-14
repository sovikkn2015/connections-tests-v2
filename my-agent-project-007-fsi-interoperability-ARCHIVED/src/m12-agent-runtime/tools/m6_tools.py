"""
M12 Tool Wrappers — @tool functions that call M6 gateway.

Every tool POSTs to M6_GATEWAY_URL/mcp/call with the MCPRequest format.
M6 runs the full trust pipeline (M1→M2→M4→M10) on every call.
MNPI is filtered by M4 BEFORE data reaches the LLM.

No direct vendor API calls (Rule 4).
No credentials in code (Rule 20).
No cross-module imports (Rule 9) — HTTP to M6 only.
"""

from __future__ import annotations

import json
import logging
import os
from contextvars import ContextVar
from typing import Any

import httpx
from strands import tool

logger = logging.getLogger("m12.tools.m6")

# ── Context: AID token for current request ──────────────────────

current_aid_token: ContextVar[str] = ContextVar(
    "current_aid_token", default=""
)

# ── M6 gateway URL (env var, no hardcoded creds) ────────────────

_M6_URL = os.environ.get("M6_GATEWAY_URL", "http://localhost:8000")
_HTTP_TIMEOUT = float(os.environ.get("M12_TOOL_TIMEOUT", "30.0"))


def _call_m6(
    server_url: str, tool_name: str, arguments: dict[str, Any]
) -> str:
    """
    Call M6 gateway synchronously. Every vendor call goes through here.

    M6 runs: M1 verify → M2 authority → M4 MNPI filter → forward →
             M4 filter response → leakage scan → M10 audit.

    Returns the result as a string for the LLM to read.
    On 403 (denied): returns generic "Access denied" (Rule 9).
    On error: returns "Service temporarily unavailable".
    """
    aid_token = current_aid_token.get()
    if not aid_token:
        # Fallback: some agent runtimes run tools in a thread pool that does
        # not propagate the ContextVar. Honor FSI_AID_TOKEN env as a backup.
        aid_token = os.environ.get("FSI_AID_TOKEN", "")
    if not aid_token:
        aid_token = "dev-token"
        logger.warning("No AID token in context, using dev-token")

    payload = {
        "aid_token": aid_token,
        "server_url": server_url,
        "tool_name": tool_name,
        "arguments": arguments,
    }

    try:
        with httpx.Client(timeout=_HTTP_TIMEOUT) as client:
            resp = client.post(f"{_M6_URL}/mcp/call", json=payload)

        if resp.status_code == 403:
            logger.warning("M6 denied access for %s/%s", server_url, tool_name)
            return "Access denied"

        if resp.status_code >= 400:
            logger.error(
                "M6 error %d for %s/%s", resp.status_code, server_url, tool_name
            )
            return "Service temporarily unavailable"

        data = resp.json()
        result = data.get("result", data)
        return json.dumps(result, indent=2) if isinstance(result, (dict, list)) else str(result)

    except httpx.HTTPError as exc:
        logger.error("M6 HTTP error for %s/%s: %s", server_url, tool_name, exc)
        return "Service temporarily unavailable"


# ── M11 Adapter Server URLs (configured per deployment) ─────────

_SALESFORCE_SERVER = os.environ.get(
    "M11_SALESFORCE_URL", "http://m11-salesforce:8000"
)
_ORION_SERVER = os.environ.get(
    "M11_ORION_URL", "http://m11-orion:8000"
)
_EMONEY_SERVER = os.environ.get(
    "M11_EMONEY_URL", "http://m11-emoney:8000"
)
_SCHWAB_SERVER = os.environ.get(
    "M11_SCHWAB_URL", "http://m11-schwab:8000"
)
_SEC_EDGAR_SERVER = os.environ.get(
    "M11_SEC_EDGAR_URL", "http://m11-sec-edgar:8000"
)
_MARKET_DATA_SERVER = os.environ.get(
    "M11_MARKET_DATA_URL", "http://m11-market-data:8000"
)
_NEWS_SERVER = os.environ.get(
    "M11_NEWS_URL", "http://m11-news:8000"
)
_EXECUTION_SERVER = os.environ.get(
    "M11_EXECUTION_URL", "http://m11-execution:8000"
)


# ── @tool definitions (LLM reads docstrings) ────────────────────


@tool
def get_client_profile(client_id: str) -> str:
    """Get a client's profile from Salesforce Financial Services Cloud.
    Returns client demographics, accounts, relationships, and preferences.
    Use this for any request about a specific client's information.
    Data is MNPI-filtered by the trust layer before you see it."""
    return _call_m6(_SALESFORCE_SERVER, "get_client_profile", {
        "client_id": client_id,
    })


@tool
def get_holdings(client_id: str) -> str:
    """Get a client's current investment holdings from Orion portfolio system.
    Returns positions, asset allocation, and performance data.
    Data is MNPI-filtered by the trust layer before you see it."""
    return _call_m6(_ORION_SERVER, "get_holdings", {
        "client_id": client_id,
    })


@tool
def get_financial_plan(client_id: str) -> str:
    """Get a client's financial plan from eMoney planning system.
    Returns goals, projections, insurance, and estate planning data.
    Data is MNPI-filtered by the trust layer before you see it."""
    return _call_m6(_EMONEY_SERVER, "get_financial_plan", {
        "client_id": client_id,
    })


@tool
def get_account_balances(account_id: str) -> str:
    """Get account balances and cash positions from Schwab custodian.
    Returns current balances, pending transactions, and margin data.
    Data is MNPI-filtered by the trust layer before you see it."""
    return _call_m6(_SCHWAB_SERVER, "get_account_balances", {
        "account_id": account_id,
    })


@tool
def search_sec_filings(ticker: str, filing_type: str) -> str:
    """Search SEC EDGAR for company filings (10-K, 10-Q, 8-K, etc).
    Returns filing summaries, dates, and key financial data.
    Use for research on public companies."""
    return _call_m6(_SEC_EDGAR_SERVER, "search_sec_filings", {
        "ticker": ticker,
        "filing_type": filing_type,
    })


@tool
def get_market_data(ticker: str) -> str:
    """Get current market data for a security: price, volume, changes,
    52-week range, market cap, P/E ratio, and dividend yield.
    Use for real-time market information."""
    return _call_m6(_MARKET_DATA_SERVER, "get_market_data", {
        "ticker": ticker,
    })


@tool
def get_news(query: str) -> str:
    """Search financial news for a company, sector, or topic.
    Returns recent headlines, summaries, and sources.
    Use for current events and sentiment analysis."""
    return _call_m6(_NEWS_SERVER, "search_news", {
        "query": query,
    })


@tool
def submit_order(order_spec: str) -> str:
    """Submit a trade order for execution. Orders require human approval
    (HITL enforced by M6 gateway). You prepare the order, humans approve.
    order_spec should be JSON with: client_id, account_id, symbol, side
    (buy/sell), quantity, order_type (market/limit), limit_price (optional).
    Always run compliance checks BEFORE calling this tool."""
    return _call_m6(_EXECUTION_SERVER, "submit_order", {
        "order_spec": order_spec,
    })
