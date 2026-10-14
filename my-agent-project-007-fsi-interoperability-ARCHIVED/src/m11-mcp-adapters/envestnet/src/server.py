"""
Envestnet REST MCP Adapter — M11-REST (Phase 4).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via ENVESTNET_CLIENT_ID / ENVESTNET_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_accounts, get_holdings, get_performance, get_billing.
Envestnet serves 110K+ advisors — competitor risk per ARCH-09.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8054
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import httpx

_here = Path(__file__).resolve().parent
for _ancestor in [_here.parent, _here.parent.parent, *_here.parents]:
    if (_ancestor / "_shared").is_dir():
        sys.path.insert(0, str(_ancestor))
        break

from _shared.mcp_server import MCPAdapterServer, ToolDefinition
from _shared.rate_limiter import TokenBucket
from _shared.errors import canonical_error, tool_result

ENVESTNET_CLIENT_ID = os.environ.get("ENVESTNET_CLIENT_ID", "")
ENVESTNET_CLIENT_SECRET = os.environ.get("ENVESTNET_CLIENT_SECRET", "")
ENVESTNET_BASE_URL = os.environ.get("ENVESTNET_BASE_URL", "https://api.envestnet.com/v3")
_DEV_MODE = not ENVESTNET_CLIENT_ID

_rpm = int(os.environ.get("ENVESTNET_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("ENVESTNET_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_http_client: httpx.AsyncClient | None = None
_access_token: str | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=ENVESTNET_BASE_URL, headers={"Accept": "application/json"}, timeout=30.0,
        )
    return _http_client


async def _ensure_token() -> str | None:
    global _access_token
    if _access_token:
        return _access_token
    client = _get_http_client()
    resp = await client.post("/oauth/token", data={"grant_type": "client_credentials"}, auth=(ENVESTNET_CLIENT_ID, ENVESTNET_CLIENT_SECRET))
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


async def _envestnet_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Envestnet rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"Envestnet returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# Dev-mode mock data
_MOCK_ACCOUNTS = [
    {"account_id": "ENV-A001", "account_name": "Smith Growth Portfolio", "model": "Moderate Growth", "advisor_id": "ADV-001", "status": "active", "aum": 450000.00},
    {"account_id": "ENV-A002", "account_name": "Smith Income Portfolio", "model": "Conservative Income", "advisor_id": "ADV-001", "status": "active", "aum": 275000.00},
]

_MOCK_HOLDINGS = [
    {"symbol": "VTI", "name": "Vanguard Total Stock Market ETF", "quantity": 500, "market_value": 135000.00, "weight": 30.0, "asset_class": "US Equity", "cost_basis_method": "AVG_COST"},
    {"symbol": "VXUS", "name": "Vanguard Total Intl Stock ETF", "quantity": 400, "market_value": 22000.00, "weight": 4.9, "asset_class": "Intl Equity", "cost_basis_method": "AVG_COST"},
    {"symbol": "BND", "name": "Vanguard Total Bond Market ETF", "quantity": 600, "market_value": 46200.00, "weight": 10.3, "asset_class": "Fixed Income", "cost_basis_method": "AVG_COST"},
]

_MOCK_PERFORMANCE = {
    "account_id": "ENV-A001", "period": "ytd",
    "twr": 8.45, "irr": 8.12, "benchmark_return": 7.89, "alpha": 0.56,
    "start_value": 415000.00, "end_value": 450000.00, "net_flows": 0.0,
}

_MOCK_BILLING = [
    {"period": "2025-Q1", "account_id": "ENV-A001", "fee_type": "advisory", "rate_bps": 75, "amount": 843.75, "aum_basis": 450000.00},
]


async def _handle_get_accounts(args: dict[str, Any]) -> dict[str, Any]:
    advisor_id = args.get("advisor_id")
    if not advisor_id:
        return canonical_error("'advisor_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"accounts": _MOCK_ACCOUNTS, "_dev_mode": True})
    result = await _envestnet_get("/accounts", params={"advisorId": advisor_id, "page": args.get("page", 1), "pageSize": args.get("page_size", 50)})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_holdings(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, "holdings": _MOCK_HOLDINGS, "_dev_mode": True})
    result = await _envestnet_get(f"/accounts/{account_id}/holdings")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_performance(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        perf = {**_MOCK_PERFORMANCE, "account_id": account_id, "period": args.get("period", "ytd")}
        return tool_result({**perf, "_dev_mode": True})
    result = await _envestnet_get(f"/accounts/{account_id}/performance", params={"period": args.get("period", "ytd")})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_billing(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, "billing": _MOCK_BILLING, "_dev_mode": True})
    params: dict[str, Any] = {}
    if args.get("period"):
        params["period"] = args["period"]
    result = await _envestnet_get(f"/accounts/{account_id}/billing", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


_server = MCPAdapterServer(
    name="envestnet-adapter", version="1.0.0", vendor="envestnet",
    description="Envestnet platform adapter (110K+ advisors). OAuth 2.0. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="get_accounts", description="Get managed accounts for an advisor on the Envestnet platform.",
    inputSchema={"type": "object", "properties": {
        "advisor_id": {"type": "string", "description": "Envestnet advisor ID"},
        "page": {"type": "integer", "description": "Page number", "minimum": 1, "default": 1},
        "page_size": {"type": "integer", "description": "Results per page (1-100)", "minimum": 1, "maximum": 100, "default": 50},
    }, "required": ["advisor_id"], "additionalProperties": False},
), _handle_get_accounts)

_server.register_tool(ToolDefinition(
    name="get_holdings", description="Get current holdings for an Envestnet account. cost_basis_method is NEVER null.",
    inputSchema={"type": "object", "properties": {
        "account_id": {"type": "string", "description": "Envestnet account ID"},
    }, "required": ["account_id"], "additionalProperties": False},
), _handle_get_holdings)

_server.register_tool(ToolDefinition(
    name="get_performance", description="Get performance metrics (TWR, IRR, alpha) for an Envestnet account.",
    inputSchema={"type": "object", "properties": {
        "account_id": {"type": "string", "description": "Envestnet account ID"},
        "period": {"type": "string", "description": "Performance period", "enum": ["mtd", "qtd", "ytd", "1y", "3y", "5y", "inception"], "default": "ytd"},
    }, "required": ["account_id"], "additionalProperties": False},
), _handle_get_performance)

_server.register_tool(ToolDefinition(
    name="get_billing", description="Get billing/fee data for an Envestnet account.",
    inputSchema={"type": "object", "properties": {
        "account_id": {"type": "string", "description": "Envestnet account ID"},
        "period": {"type": "string", "description": "Billing period (e.g. '2025-Q1')"},
    }, "required": ["account_id"], "additionalProperties": False},
), _handle_get_billing)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
