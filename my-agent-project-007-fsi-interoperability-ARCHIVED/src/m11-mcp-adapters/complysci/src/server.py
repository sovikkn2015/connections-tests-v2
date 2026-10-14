"""
ComplySci REST MCP Adapter — M11-REST (Phase 4).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

API key auth via COMPLYSCI_API_KEY env var.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_holdings_reports, get_preclearance_requests, submit_preclearance, get_restricted_list.

NOTE: This adapter fetches compliance DATA from ComplySci.
Compliance DECISIONS are made by M2/M4 via OPA/Rego — never by this adapter.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8055
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

COMPLYSCI_API_KEY = os.environ.get("COMPLYSCI_API_KEY", "")
COMPLYSCI_BASE_URL = os.environ.get("COMPLYSCI_BASE_URL", "https://api.complysci.com/v2")
_DEV_MODE = not COMPLYSCI_API_KEY

_rpm = int(os.environ.get("COMPLYSCI_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("COMPLYSCI_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=COMPLYSCI_BASE_URL,
            headers={"Accept": "application/json", "X-API-Key": COMPLYSCI_API_KEY},
            timeout=30.0,
        )
    return _http_client


async def _complysci_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("ComplySci rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params)
    if resp.status_code != 200:
        return canonical_error(f"ComplySci returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


async def _complysci_post(path: str, json_body: dict[str, Any]) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("ComplySci rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    client = _get_http_client()
    resp = await client.post(path, json=json_body)
    if resp.status_code not in (200, 201):
        return canonical_error(f"ComplySci returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# Dev-mode mock data
_MOCK_HOLDINGS_REPORT = {
    "employee_id": "EMP-001", "report_date": "2025-01-15", "status": "submitted",
    "holdings": [
        {"symbol": "AAPL", "quantity": 100, "account_type": "personal", "broker": "Schwab"},
        {"symbol": "MSFT", "quantity": 50, "account_type": "spouse", "broker": "Fidelity"},
    ],
}

_MOCK_PRECLEARANCE = [
    {"request_id": "PCR-001", "employee_id": "EMP-001", "symbol": "GOOGL", "side": "buy", "quantity": 25, "status": "approved", "submitted_at": "2025-01-14T10:00:00Z", "decided_at": "2025-01-14T10:05:00Z"},
    {"request_id": "PCR-002", "employee_id": "EMP-001", "symbol": "JPM", "side": "sell", "quantity": 50, "status": "pending", "submitted_at": "2025-01-15T09:00:00Z", "decided_at": None},
]

_MOCK_RESTRICTED_LIST = [
    {"symbol": "GS", "reason": "firm_coverage", "added_date": "2025-01-01", "expiry_date": None},
    {"symbol": "MS", "reason": "firm_coverage", "added_date": "2025-01-01", "expiry_date": None},
    {"symbol": "ACME", "reason": "material_nonpublic", "added_date": "2025-01-10", "expiry_date": "2025-02-10"},
]


async def _handle_get_holdings_reports(args: dict[str, Any]) -> dict[str, Any]:
    employee_id = args.get("employee_id")
    if not employee_id:
        return canonical_error("'employee_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        report = {**_MOCK_HOLDINGS_REPORT, "employee_id": employee_id}
        if args.get("report_date"):
            report["report_date"] = args["report_date"]
        return tool_result({**report, "_dev_mode": True})
    params: dict[str, Any] = {"employeeId": employee_id}
    if args.get("report_date"):
        params["reportDate"] = args["report_date"]
    result = await _complysci_get("/holdings-reports", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_preclearance_requests(args: dict[str, Any]) -> dict[str, Any]:
    employee_id = args.get("employee_id")
    if not employee_id:
        return canonical_error("'employee_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        reqs = [r for r in _MOCK_PRECLEARANCE if r["employee_id"] == employee_id or employee_id == "EMP-001"]
        status_filter = args.get("status")
        if status_filter and status_filter != "all":
            reqs = [r for r in reqs if r["status"] == status_filter]
        return tool_result({"requests": reqs, "_dev_mode": True})
    params: dict[str, Any] = {"employeeId": employee_id}
    if args.get("status") and args["status"] != "all":
        params["status"] = args["status"]
    result = await _complysci_get("/preclearance", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_submit_preclearance(args: dict[str, Any]) -> dict[str, Any]:
    employee_id = args.get("employee_id")
    symbol = args.get("symbol")
    side = args.get("side")
    quantity = args.get("quantity")
    account_type = args.get("account_type")
    if not all([employee_id, symbol, side, quantity, account_type]):
        return canonical_error("'employee_id', 'symbol', 'side', 'quantity', and 'account_type' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"request_id": "PCR-003", "employee_id": employee_id, "symbol": symbol, "side": side, "quantity": quantity, "account_type": account_type, "status": "pending", "submitted_at": "2025-01-15T10:00:00Z", "_dev_mode": True})
    result = await _complysci_post("/preclearance", {"employee_id": employee_id, "symbol": symbol, "side": side, "quantity": quantity, "account_type": account_type})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_restricted_list(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        return tool_result({"restricted_securities": _MOCK_RESTRICTED_LIST, "_dev_mode": True})
    result = await _complysci_get("/restricted-list")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


_server = MCPAdapterServer(
    name="complysci-adapter", version="1.0.0", vendor="complysci",
    description="ComplySci personal trading compliance adapter. API key auth. Dev mode returns mock data. NOTE: fetches compliance DATA only — decisions via M2/M4 OPA.",
)

_server.register_tool(ToolDefinition(
    name="get_holdings_reports", description="Get holdings disclosure report for an employee.",
    inputSchema={"type": "object", "properties": {
        "employee_id": {"type": "string", "description": "ComplySci employee ID"},
        "report_date": {"type": "string", "description": "Report date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    }, "required": ["employee_id"], "additionalProperties": False},
), _handle_get_holdings_reports)

_server.register_tool(ToolDefinition(
    name="get_preclearance_requests", description="Get preclearance requests for an employee.",
    inputSchema={"type": "object", "properties": {
        "employee_id": {"type": "string", "description": "ComplySci employee ID"},
        "status": {"type": "string", "description": "Filter by status", "enum": ["pending", "approved", "denied", "expired", "all"], "default": "all"},
    }, "required": ["employee_id"], "additionalProperties": False},
), _handle_get_preclearance_requests)

_server.register_tool(ToolDefinition(
    name="submit_preclearance", description="Submit a preclearance request for a proposed personal trade.",
    inputSchema={"type": "object", "properties": {
        "employee_id": {"type": "string", "description": "ComplySci employee ID"},
        "symbol": {"type": "string", "description": "Ticker symbol (e.g. 'AAPL')"},
        "side": {"type": "string", "description": "Trade direction", "enum": ["buy", "sell"]},
        "quantity": {"type": "number", "description": "Number of shares", "exclusiveMinimum": 0},
        "account_type": {"type": "string", "description": "Account type", "enum": ["personal", "spouse", "dependent", "trust"]},
    }, "required": ["employee_id", "symbol", "side", "quantity", "account_type"], "additionalProperties": False},
), _handle_submit_preclearance)

_server.register_tool(ToolDefinition(
    name="get_restricted_list", description="Get the firm's restricted securities list.",
    inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
), _handle_get_restricted_list)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
