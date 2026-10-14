"""
Charles Schwab REST MCP Adapter — M11-REST (Phase 2).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via SCHWAB_CLIENT_ID / SCHWAB_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_accounts, get_positions, get_balances, get_transactions, get_orders.

CRITICAL: cost_basis_method is NEVER null in position output (Rule 16).
Note: 6-8 week vendor approval per ARCH-09.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8014
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
SCHWAB_CLIENT_ID = os.environ.get("SCHWAB_CLIENT_ID", "")
SCHWAB_CLIENT_SECRET = os.environ.get("SCHWAB_CLIENT_SECRET", "")
SCHWAB_BASE_URL = os.environ.get("SCHWAB_BASE_URL", "https://api.schwabapi.com/trader/v1")
_DEV_MODE = not SCHWAB_CLIENT_ID

_rpm = int(os.environ.get("SCHWAB_RATE_LIMIT_RPM", "120"))
_burst = int(os.environ.get("SCHWAB_RATE_LIMIT_BURST", "5"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

# ---------------------------------------------------------------------------
# HTTP client + OAuth 2.0
# ---------------------------------------------------------------------------
_http_client: httpx.AsyncClient | None = None
_access_token: str | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=SCHWAB_BASE_URL,
            headers={"Accept": "application/json"},
            timeout=30.0,
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
        auth=(SCHWAB_CLIENT_ID, SCHWAB_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


async def _schwab_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Schwab rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"Schwab returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data
# ---------------------------------------------------------------------------
_MOCK_ACCOUNTS = [
    {"accountId": "SCHW-001", "accountType": "individual", "name": "Smith Individual Brokerage", "status": "active", "isClosedAccount": False},
    {"accountId": "SCHW-002", "accountType": "ira", "name": "Smith Traditional IRA", "status": "active", "isClosedAccount": False},
    {"accountId": "SCHW-003", "accountType": "roth_ira", "name": "Smith Roth IRA", "status": "active", "isClosedAccount": False},
]

_MOCK_POSITIONS = [
    {"symbol": "AAPL", "cusip": "037833100", "quantity": 200, "marketValue": 43000.00, "costBasis": 30000.00, "costBasisMethod": "FIFO", "unrealizedPL": 13000.00, "assetType": "EQUITY"},
    {"symbol": "MSFT", "cusip": "594918104", "quantity": 100, "marketValue": 42500.00, "costBasis": 32000.00, "costBasisMethod": "FIFO", "unrealizedPL": 10500.00, "assetType": "EQUITY"},
    {"symbol": "VTI", "cusip": "922908769", "quantity": 300, "marketValue": 81000.00, "costBasis": 72000.00, "costBasisMethod": "AVG_COST", "unrealizedPL": 9000.00, "assetType": "ETF"},
    {"symbol": "BND", "cusip": "921937835", "quantity": 400, "marketValue": 30800.00, "costBasis": 32000.00, "costBasisMethod": "SPEC_ID", "unrealizedPL": -1200.00, "assetType": "ETF"},
    {"symbol": "SCHD", "cusip": "808524805", "quantity": 250, "marketValue": 20750.00, "costBasis": 18000.00, "costBasisMethod": "FIFO", "unrealizedPL": 2750.00, "assetType": "ETF"},
]

_MOCK_BALANCES = {
    "totalValue": 218050.00,
    "cashBalance": 15432.50,
    "marginBalance": 0.0,
    "buyingPower": 15432.50,
    "pendingDeposits": 0.0,
    "pendingWithdrawals": 0.0,
    "longMarketValue": 218050.00,
    "shortMarketValue": 0.0,
}

_MOCK_TRANSACTIONS = [
    {"transactionId": "STXN-001", "date": "2025-01-10", "type": "BUY", "symbol": "AAPL", "quantity": 50, "price": 215.00, "amount": -10750.00, "status": "SETTLED"},
    {"transactionId": "STXN-002", "date": "2025-01-12", "type": "DIVIDEND", "symbol": "VTI", "quantity": 0, "price": 0, "amount": 187.50, "status": "SETTLED"},
    {"transactionId": "STXN-003", "date": "2025-01-15", "type": "BUY", "symbol": "SCHD", "quantity": 50, "price": 83.00, "amount": -4150.00, "status": "SETTLED"},
]

_MOCK_ORDERS = [
    {"orderId": "ORD-001", "symbol": "AAPL", "side": "BUY", "quantity": 25, "orderType": "LIMIT", "limitPrice": 210.00, "status": "PENDING", "enteredTime": "2025-07-15T10:30:00Z"},
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_get_accounts(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        return tool_result({"accounts": _MOCK_ACCOUNTS, "_dev_mode": True})
    result = await _schwab_get("/accounts")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_positions(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"accountId": account_id, "positions": _MOCK_POSITIONS, "_dev_mode": True})
    result = await _schwab_get(f"/accounts/{account_id}/positions")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_balances(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"accountId": account_id, **_MOCK_BALANCES, "_dev_mode": True})
    result = await _schwab_get(f"/accounts/{account_id}/balances")
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
        return tool_result({"accountId": account_id, "transactions": _MOCK_TRANSACTIONS, "_dev_mode": True})
    result = await _schwab_get(f"/accounts/{account_id}/transactions", params={"startDate": start_date, "endDate": end_date})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_orders(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"accountId": account_id, "orders": _MOCK_ORDERS, "_dev_mode": True})
    params: dict[str, Any] = {}
    if args.get("status"):
        params["status"] = args["status"]
    result = await _schwab_get(f"/accounts/{account_id}/orders", params=params or None)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="schwab-rest-adapter",
    version="1.0.0",
    vendor="schwab",
    description="Charles Schwab REST API adapter. OAuth 2.0 auth. Dev mode returns mock data when credentials absent.",
)

_server.register_tool(
    ToolDefinition(
        name="get_accounts",
        description="List accounts for the authenticated Schwab user.",
        inputSchema={
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        },
    ),
    _handle_get_accounts,
)

_server.register_tool(
    ToolDefinition(
        name="get_positions",
        description="Get current positions (holdings) for a Schwab account. cost_basis_method is NEVER null.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Schwab account ID"},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_positions,
)

_server.register_tool(
    ToolDefinition(
        name="get_balances",
        description="Get account balances for a Schwab account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Schwab account ID"},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_balances,
)

_server.register_tool(
    ToolDefinition(
        name="get_transactions",
        description="Get transaction history for a Schwab account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Schwab account ID"},
                "start_date": {"type": "string", "description": "Start date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "end_date": {"type": "string", "description": "End date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            },
            "required": ["account_id", "start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    _handle_get_transactions,
)

_server.register_tool(
    ToolDefinition(
        name="get_orders",
        description="Get open/recent orders for a Schwab account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Schwab account ID"},
                "status": {"type": "string", "description": "Filter by order status", "enum": ["PENDING", "FILLED", "CANCELED", "EXPIRED", "ALL"], "default": "ALL"},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_orders,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
