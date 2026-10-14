"""
Pershing (BNY Mellon) Integration Hub MCP Adapter — M11-REST (Phase 3).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via PERSHING_CLIENT_ID / PERSHING_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_accounts, get_positions, get_balances, get_transactions.
BD custodian — primary broker-dealer integration via Integration Hub.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8051
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

# ---------------------------------------------------------------------------
# Config from env (Rule 3)
# ---------------------------------------------------------------------------
PERSHING_CLIENT_ID = os.environ.get("PERSHING_CLIENT_ID", "")
PERSHING_CLIENT_SECRET = os.environ.get("PERSHING_CLIENT_SECRET", "")
PERSHING_BASE_URL = os.environ.get("PERSHING_BASE_URL", "https://api.pershing.com/integration-hub/v1")
_DEV_MODE = not PERSHING_CLIENT_ID

_rpm = int(os.environ.get("PERSHING_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("PERSHING_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_http_client: httpx.AsyncClient | None = None
_access_token: str | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=PERSHING_BASE_URL, headers={"Accept": "application/json"}, timeout=30.0,
        )
    return _http_client


async def _ensure_token() -> str | None:
    global _access_token
    if _access_token:
        return _access_token
    client = _get_http_client()
    resp = await client.post(
        "/oauth/token",
        data={"grant_type": "client_credentials"},
        auth=(PERSHING_CLIENT_ID, PERSHING_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


async def _pershing_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Pershing rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"Pershing returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data
# ---------------------------------------------------------------------------
_MOCK_ACCOUNTS = [
    {"account_id": "PSH-10001", "account_type": "individual", "registration": "Individual", "rep_code": "ABC", "status": "active", "custodian": "pershing"},
    {"account_id": "PSH-10002", "account_type": "ira", "registration": "Traditional IRA", "rep_code": "ABC", "status": "active", "custodian": "pershing"},
]

_MOCK_POSITIONS = [
    {"symbol": "SPY", "cusip": "78462F103", "quantity": 100, "market_value": 55000.00, "cost_basis": 45000.00, "cost_basis_method": "FIFO", "security_type": "ETF"},
    {"symbol": "BND", "cusip": "921937835", "quantity": 200, "market_value": 15400.00, "cost_basis": 16000.00, "cost_basis_method": "AVG_COST", "security_type": "ETF"},
]

_MOCK_BALANCES = {"total_value": 75832.00, "cash_balance": 5432.00, "margin_balance": 0.0, "settled_cash": 5432.00, "unsettled_cash": 0.0}

_MOCK_TRANSACTIONS = [
    {"transaction_id": "PTXN-001", "settle_date": "2025-01-13", "trade_date": "2025-01-10", "type": "buy", "symbol": "SPY", "quantity": 25, "price": 550.00, "net_amount": -13750.00},
    {"transaction_id": "PTXN-002", "settle_date": "2025-01-14", "trade_date": "2025-01-12", "type": "dividend", "symbol": "BND", "quantity": 0, "price": 0, "net_amount": 42.50},
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_get_accounts(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        return tool_result({"accounts": _MOCK_ACCOUNTS, "_dev_mode": True})
    result = await _pershing_get("/accounts")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_positions(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, "positions": _MOCK_POSITIONS, "_dev_mode": True})
    result = await _pershing_get(f"/accounts/{account_id}/positions")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_balances(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, **_MOCK_BALANCES, "_dev_mode": True})
    result = await _pershing_get(f"/accounts/{account_id}/balances")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_transactions(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    start_date = args.get("start_date")
    end_date = args.get("end_date")
    if not start_date or not end_date:
        return canonical_error("'start_date' and 'end_date' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, "transactions": _MOCK_TRANSACTIONS, "_dev_mode": True})
    result = await _pershing_get(f"/accounts/{account_id}/transactions", params={"startDate": start_date, "endDate": end_date})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="pershing-adapter",
    version="1.0.0",
    vendor="pershing",
    description="Pershing (BNY Mellon) Integration Hub adapter. BD custodian. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="get_accounts", description="List accounts from Pershing Integration Hub.",
    inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
), _handle_get_accounts)

_server.register_tool(ToolDefinition(
    name="get_positions", description="Get current positions for a Pershing account. cost_basis_method is NEVER null.",
    inputSchema={"type": "object", "properties": {"account_id": {"type": "string", "description": "Pershing account ID"}}, "required": ["account_id"], "additionalProperties": False},
), _handle_get_positions)

_server.register_tool(ToolDefinition(
    name="get_balances", description="Get account balances for a Pershing account.",
    inputSchema={"type": "object", "properties": {"account_id": {"type": "string", "description": "Pershing account ID"}}, "required": ["account_id"], "additionalProperties": False},
), _handle_get_balances)

_server.register_tool(ToolDefinition(
    name="get_transactions", description="Get transaction history for a Pershing account.",
    inputSchema={"type": "object", "properties": {
        "account_id": {"type": "string", "description": "Pershing account ID"},
        "start_date": {"type": "string", "description": "Start date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
        "end_date": {"type": "string", "description": "End date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    }, "required": ["account_id", "start_date", "end_date"], "additionalProperties": False},
), _handle_get_transactions)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
