"""
Orion Portfolio Management MCP Adapter — M11-REST (Phase 2).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via ORION_CLIENT_ID / ORION_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_clients, get_accounts, get_positions, get_performance.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8004
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
ORION_CLIENT_ID = os.environ.get("ORION_CLIENT_ID", "")
ORION_CLIENT_SECRET = os.environ.get("ORION_CLIENT_SECRET", "")
ORION_BASE_URL = os.environ.get("ORION_BASE_URL", "https://api.orionadvisor.com/api/v1")
_DEV_MODE = not ORION_CLIENT_ID

_rpm = int(os.environ.get("ORION_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("ORION_RATE_LIMIT_BURST", "10"))
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
            base_url=ORION_BASE_URL,
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
        "/security/token",
        data={"grant_type": "client_credentials"},
        auth=(ORION_CLIENT_ID, ORION_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


async def _orion_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Orion rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"Orion returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data — Orion portfolio management
# ---------------------------------------------------------------------------
_MOCK_CLIENTS = [
    {
        "id": "CLT-1001",
        "firstName": "John",
        "lastName": "Smith",
        "household": {"id": "HH-500", "name": "Smith Household"},
        "representativeId": "REP-100",
        "status": "Active",
        "clientType": "Individual",
        "accounts": ["ACCT-2001", "ACCT-2002"],
    },
    {
        "id": "CLT-1002",
        "firstName": "Jane",
        "lastName": "Smith",
        "household": {"id": "HH-500", "name": "Smith Household"},
        "representativeId": "REP-100",
        "status": "Active",
        "clientType": "Individual",
        "accounts": ["ACCT-2003"],
    },
]

_MOCK_ACCOUNTS = [
    {
        "id": "ACCT-2001",
        "name": "Smith IRA",
        "accountType": "IRA",
        "custodian": "Schwab",
        "clientId": "CLT-1001",
        "householdId": "HH-500",
        "portfolioId": "PORT-3001",
        "status": "Active",
        "totalValue": 485000.00,
        "cashBalance": 12500.00,
    },
    {
        "id": "ACCT-2002",
        "name": "Smith Joint Brokerage",
        "accountType": "Joint",
        "custodian": "Schwab",
        "clientId": "CLT-1001",
        "householdId": "HH-500",
        "portfolioId": "PORT-3002",
        "status": "Active",
        "totalValue": 320000.00,
        "cashBalance": 8750.00,
    },
]

_MOCK_POSITIONS = [
    {"symbol": "AAPL", "cusip": "037833100", "quantity": 150, "marketValue": 32250.00, "costBasis": 22500.00, "costBasisMethod": "FIFO", "unrealizedGL": 9750.00, "securityType": "Equity"},
    {"symbol": "MSFT", "cusip": "594918104", "quantity": 75, "marketValue": 31875.00, "costBasis": 24000.00, "costBasisMethod": "FIFO", "unrealizedGL": 7875.00, "securityType": "Equity"},
    {"symbol": "VTI", "cusip": "922908769", "quantity": 200, "marketValue": 54000.00, "costBasis": 48000.00, "costBasisMethod": "AVG_COST", "unrealizedGL": 6000.00, "securityType": "ETF"},
    {"symbol": "BND", "cusip": "921937835", "quantity": 300, "marketValue": 23100.00, "costBasis": 24000.00, "costBasisMethod": "SPEC_ID", "unrealizedGL": -900.00, "securityType": "ETF"},
]

_MOCK_PERFORMANCE = {
    "accountId": "ACCT-2001",
    "period": "ytd",
    "twr": 8.45,
    "irr": 7.92,
    "benchmarkReturn": 10.12,
    "benchmarkName": "S&P 500",
    "alpha": -1.67,
    "startDate": "2025-01-01",
    "endDate": "2025-07-15",
    "startValue": 447000.00,
    "endValue": 485000.00,
    "netFlows": 0.00,
}


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_get_clients(args: dict[str, Any]) -> dict[str, Any]:
    representative_id = args.get("representative_id")
    if not representative_id:
        return canonical_error("'representative_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        page = args.get("page", 1)
        page_size = args.get("page_size", 50)
        return tool_result({
            "clients": _MOCK_CLIENTS,
            "page": page,
            "pageSize": page_size,
            "totalRecords": len(_MOCK_CLIENTS),
            "_dev_mode": True,
        })
    params: dict[str, Any] = {"representativeId": representative_id}
    if args.get("page"):
        params["page"] = args["page"]
    if args.get("page_size"):
        params["pageSize"] = args["page_size"]
    result = await _orion_get("/clients", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_accounts(args: dict[str, Any]) -> dict[str, Any]:
    client_id = args.get("client_id")
    if not client_id:
        return canonical_error("'client_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        accounts = [a for a in _MOCK_ACCOUNTS if a["clientId"] == client_id] or _MOCK_ACCOUNTS
        return tool_result({"accounts": accounts, "_dev_mode": True})
    result = await _orion_get(f"/clients/{client_id}/accounts")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_positions(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"accountId": account_id, "positions": _MOCK_POSITIONS, "_dev_mode": True})
    params: dict[str, Any] = {}
    if args.get("include_tax_lots"):
        params["includeTaxLots"] = True
    result = await _orion_get(f"/accounts/{account_id}/positions", params=params or None)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_performance(args: dict[str, Any]) -> dict[str, Any]:
    account_id = args.get("account_id")
    if not account_id:
        return canonical_error("'account_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        perf = {**_MOCK_PERFORMANCE, "accountId": account_id, "period": args.get("period", "ytd")}
        if args.get("benchmark"):
            perf["benchmarkName"] = args["benchmark"]
        return tool_result({**perf, "_dev_mode": True})
    params: dict[str, Any] = {"period": args.get("period", "ytd")}
    if args.get("benchmark"):
        params["benchmark"] = args["benchmark"]
    result = await _orion_get(f"/accounts/{account_id}/performance", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="orion-adapter",
    version="1.0.0",
    vendor="orion",
    description="Orion Advisor Solutions portfolio management adapter. OAuth 2.0 auth. Dev mode returns mock data when credentials absent.",
)

_server.register_tool(
    ToolDefinition(
        name="get_clients",
        description="Get clients/households for a representative (advisor).",
        inputSchema={
            "type": "object",
            "properties": {
                "representative_id": {"type": "string", "description": "Orion representative (advisor) ID"},
                "include_households": {"type": "boolean", "description": "Include household groupings", "default": True},
                "page": {"type": "integer", "description": "Page number", "minimum": 1, "default": 1},
                "page_size": {"type": "integer", "description": "Results per page (1-100)", "minimum": 1, "maximum": 100, "default": 50},
            },
            "required": ["representative_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_clients,
)

_server.register_tool(
    ToolDefinition(
        name="get_accounts",
        description="Get accounts for an Orion client.",
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "Orion client ID"},
            },
            "required": ["client_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_accounts,
)

_server.register_tool(
    ToolDefinition(
        name="get_positions",
        description="Get current positions (holdings) for an Orion account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Orion account ID"},
                "include_tax_lots": {"type": "boolean", "description": "Include tax lot detail", "default": False},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_positions,
)

_server.register_tool(
    ToolDefinition(
        name="get_performance",
        description="Get performance metrics (TWR, IRR) for an Orion account.",
        inputSchema={
            "type": "object",
            "properties": {
                "account_id": {"type": "string", "description": "Orion account ID"},
                "period": {"type": "string", "description": "Performance period", "enum": ["mtd", "qtd", "ytd", "1y", "3y", "5y", "inception"], "default": "ytd"},
                "benchmark": {"type": "string", "description": "Benchmark index (e.g. 'SPX', 'AGG')"},
            },
            "required": ["account_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_performance,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
