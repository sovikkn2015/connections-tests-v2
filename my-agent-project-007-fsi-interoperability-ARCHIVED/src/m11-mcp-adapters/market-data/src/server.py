"""
Alpha Vantage Market Data MCP Adapter — M11-REST (Phase 2).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

API key auth via ALPHA_VANTAGE_API_KEY env var.
Rate limit: 5 req/min free tier, 75 req/min premium (configurable).
Bloomberg fallback for Tier 3/4 firms without Bloomberg.
Tools: get_quote, get_daily_prices, get_company_overview.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8001
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx

# Add parent dir so _shared is importable (works both locally and in Docker)
_here = Path(__file__).resolve().parent
for _ancestor in [_here.parent, _here.parent.parent, *_here.parents]:
    if (_ancestor / "_shared").is_dir():
        sys.path.insert(0, str(_ancestor))
        break

from _shared.mcp_server import MCPAdapterServer, ToolDefinition
from _shared.rate_limiter import TokenBucket
from _shared.errors import canonical_error, tool_result

# ---------------------------------------------------------------------------
# Rate limiter (Rule 4)
# ---------------------------------------------------------------------------
_rpm = int(os.environ.get("ALPHA_VANTAGE_RATE_LIMIT_RPM", "5"))
_burst = int(os.environ.get("ALPHA_VANTAGE_RATE_LIMIT_BURST", "5"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

# ---------------------------------------------------------------------------
# Alpha Vantage HTTP client (Rule 3 — API key from env)
# ---------------------------------------------------------------------------
AV_BASE = "https://www.alphavantage.co/query"
_http_client: httpx.AsyncClient | None = None


def _get_api_key() -> str:
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not key:
        raise ValueError("ALPHA_VANTAGE_API_KEY environment variable is required.")
    return key


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=30.0)
    return _http_client


async def _av_get(params: dict[str, Any]) -> Any:
    """Rate-limited GET to Alpha Vantage API."""
    acquired = await rate_limiter.acquire()
    if not acquired:
        return canonical_error(
            "Alpha Vantage rate limit exceeded.",
            error_code="RATE_LIMIT_EXCEEDED",
            vendor_status_code=429,
            retryable=True,
        )
    try:
        api_key = _get_api_key()
    except ValueError as e:
        return canonical_error(str(e), error_code="AUTH_MISSING", retryable=False)

    params["apikey"] = api_key
    client = _get_http_client()
    resp = await client.get(AV_BASE, params=params)
    if resp.status_code != 200:
        return canonical_error(
            f"Alpha Vantage returned HTTP {resp.status_code}",
            error_code="VENDOR_HTTP_ERROR",
            vendor_status_code=resp.status_code,
            retryable=resp.status_code >= 500,
        )
    data = resp.json()
    if "Error Message" in data:
        return canonical_error(data["Error Message"], error_code="VENDOR_API_ERROR",
                               vendor_status_code=200, retryable=False)
    if "Note" in data:
        return canonical_error(data["Note"], error_code="RATE_LIMIT_EXCEEDED",
                               vendor_status_code=200, retryable=True)
    return data


# ---------------------------------------------------------------------------
# Tool handlers (vendor-specific logic only)
# ---------------------------------------------------------------------------
async def _handle_get_quote(args: dict[str, Any]) -> dict[str, Any]:
    ticker = args.get("ticker")
    if not ticker:
        return canonical_error("'ticker' is required.", error_code="INVALID_PARAMS")
    result = await _av_get({"function": "GLOBAL_QUOTE", "symbol": ticker})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_daily_prices(args: dict[str, Any]) -> dict[str, Any]:
    ticker = args.get("ticker")
    if not ticker:
        return canonical_error("'ticker' is required.", error_code="INVALID_PARAMS")
    days = args.get("days", 30)
    outputsize = "compact" if days <= 100 else "full"
    result = await _av_get({
        "function": "TIME_SERIES_DAILY",
        "symbol": ticker,
        "outputsize": outputsize,
    })
    if isinstance(result, dict) and result.get("isError"):
        return result
    ts_key = "Time Series (Daily)"
    if ts_key in result:
        dates = sorted(result[ts_key].keys(), reverse=True)[:days]
        result[ts_key] = {d: result[ts_key][d] for d in dates}
    return tool_result(result)


async def _handle_get_company_overview(args: dict[str, Any]) -> dict[str, Any]:
    ticker = args.get("ticker")
    if not ticker:
        return canonical_error("'ticker' is required.", error_code="INVALID_PARAMS")
    result = await _av_get({"function": "OVERVIEW", "symbol": ticker})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly via _shared factory
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="market-data-adapter",
    version="1.0.0",
    vendor="alpha_vantage",
    description="Alpha Vantage market data: quotes, daily prices, company overview. Bloomberg fallback for Tier 3/4.",
)

_server.register_tool(
    ToolDefinition(
        name="get_quote",
        description="Get real-time stock quote for a ticker symbol.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. 'AAPL', 'MSFT')",
                },
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    ),
    _handle_get_quote,
)

_server.register_tool(
    ToolDefinition(
        name="get_daily_prices",
        description="Get daily OHLCV price history for a ticker.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. 'AAPL')",
                },
                "days": {
                    "type": "integer",
                    "description": "Number of recent trading days (1-100)",
                    "minimum": 1,
                    "maximum": 100,
                    "default": 30,
                },
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    ),
    _handle_get_daily_prices,
)

_server.register_tool(
    ToolDefinition(
        name="get_company_overview",
        description="Get company fundamentals: sector, market cap, P/E, EPS, dividend yield.",
        inputSchema={
            "type": "object",
            "properties": {
                "ticker": {
                    "type": "string",
                    "description": "Stock ticker symbol (e.g. 'AAPL')",
                },
            },
            "required": ["ticker"],
            "additionalProperties": False,
        },
    ),
    _handle_get_company_overview,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
