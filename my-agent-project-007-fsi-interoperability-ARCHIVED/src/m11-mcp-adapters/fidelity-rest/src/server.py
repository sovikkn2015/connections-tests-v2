"""
Fidelity REST MCP Adapter — M11-REST (Phase 3).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via FIDELITY_CLIENT_ID / FIDELITY_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_accounts, get_positions, get_balances, get_transactions.

CRITICAL: cost_basis_method is NEVER null in position output (Rule 16).

Run: uvicorn src.server:app --host 0.0.0.0 --port 8050
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
FIDELITY_CLIENT_ID = os.environ.get("FIDELITY_CLIENT_ID", "")
FIDELITY_CLIENT_SECRET = os.environ.get("FIDELITY_CLIENT_SECRET", "")
FIDELITY_BASE_URL = os.environ.get("FIDELITY_BASE_URL", "https://api.fidelity.com/v1")
_DEV_MODE = not FIDELITY_CLIENT_ID

_rpm = int(os.environ.get("FIDELITY_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("FIDELITY_RATE_LIMIT_BURST", "10"))
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
            base_url=FIDELITY_BASE_URL,
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
        auth=(FIDELITY_CLIENT_ID, FIDELITY_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


async def _fidelity_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Fidelity rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"Fidelity returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data
# ---------------------------------------------------------------------------
_MOCK_ACCOUNTS = [
    {"account_id": "FID-001", "account_type": "individual", "name": "John Smith IRA", "status": "active"},
    {"account_id": "FID-002", "account_type": "joint", "name": "Smith Joint Brokerage", "status": "active"},
]

_MOCK_POSITIONS = [
    {"symbol": "AAPL", "quantity": 150, "market_value": 32250.00, "cost_basis": 22500.00, "cost_basis_method": "FIFO", "unrealized_gl": 9750.00},
    {"symbol": "MSFT", "quantity": 75, "market_value": 31875.00, "cost_basis": 24000.00, "cost_basis_method": "FIFO", "unrealized_gl": 7875.00},
    {"symbol": "VTI", "quantity": 200, "market_value": 54000.00, "cost_basis": 48000.00, "cost_basis_method": "AVG_COST", "unrealized_gl": 6000.00},
]

_MOCK_BALANCES = {
    "total_value": 118125.00, "cash_balance": 5432.10, "margin_balance": 0.0,
    "buying_power": 5432.10, "pending_deposits": 0.0, "pending_withdrawals": 0.0,
}

_MOCK_TRANSACTIONS = [
    {"transaction_id": "TXN-001", "date": "2025-01-10", "type": "buy", "symbol": "AAPL", "quantity": 50, "price": 150.00, "amount": -7500.00},
    {"transaction_id": "TXN-002", "date": "2025-01-12", "type": "dividend", "symbol": "VTI", "quantity": 0, "price": 0, "amount": 125.50},
]


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_get_accounts(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        return tool_result({"accounts": _MOCK_ACCOUNTS, "_dev_mode": True})
    result = await _fidelity_get("/accounts")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_positions(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, "positions": _MOCK_POSITIONS, "_dev_mode": True})
    result = await _fidelity_get(f"/accounts/{account_id}/positions")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_balances(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"account_id": account_id, **_MOCK_BALANCES, "_dev_mode": True})
    result = await _fidelity_get(f"/accounts/{account_id}/balances")
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
    result = await _fidelity_get(f"/accounts/{account_id}/transactions", params={"startDate": start_date, "endDate": end_date})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="fidelity-rest-adapter",
    version="1.0.0",
    vendor="fidelity",
    description="Fidelity REST API adapter. OAuth 2.0 auth. Dev mode returns mock data when credentials absent.",
)

_server.register_tool(
    ToolDefinition(
        name="get_accounts",
        description="List accounts for the authenticated Fidelity user.",
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
        description="Get current positions (holdings) for a Fidelity account. cost_basis_method is NEVER null.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Fidelity account ID"},
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
        description="Get account balances for a Fidelity account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Fidelity account ID"},
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
        description="Get transaction history for a Fidelity account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Fidelity account ID"},
                "start_date": {"type": "string", "description": "Start date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
                "end_date": {"type": "string", "description": "End date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
            },
            "required": ["account_id", "start_date", "end_date"],
            "additionalProperties": False,
        },
    ),
    _handle_get_transactions,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
