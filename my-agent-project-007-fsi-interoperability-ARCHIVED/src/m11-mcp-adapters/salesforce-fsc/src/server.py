"""
Salesforce Financial Services Cloud MCP Adapter — M11-REST (Phase 2).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via SF_CLIENT_ID / SF_CLIENT_SECRET / SF_INSTANCE_URL env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: query_soql, get_record, create_record, update_record.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8003
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
SF_CLIENT_ID = os.environ.get("SF_CLIENT_ID", "")
SF_CLIENT_SECRET = os.environ.get("SF_CLIENT_SECRET", "")
SF_INSTANCE_URL = os.environ.get("SF_INSTANCE_URL", "https://login.salesforce.com")
_DEV_MODE = not SF_CLIENT_ID

_rpm = int(os.environ.get("SALESFORCE_FSC_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("SALESFORCE_FSC_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

# ---------------------------------------------------------------------------
# HTTP client + OAuth 2.0
# ---------------------------------------------------------------------------
_http_client: httpx.AsyncClient | None = None
_access_token: str | None = None
_instance_url: str | None = None
_API_VERSION = "v62.0"


def _get_http_client(base_url: str = "") -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=base_url,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
            timeout=30.0,
        )
    return _http_client


async def _ensure_token() -> str | None:
    global _access_token, _instance_url
    if _access_token and _instance_url:
        return _access_token
    client = httpx.AsyncClient(timeout=30.0)
    try:
        resp = await client.post(
            f"{SF_INSTANCE_URL}/services/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "client_id": SF_CLIENT_ID,
                "client_secret": SF_CLIENT_SECRET,
            },
        )
        if resp.status_code != 200:
            return None
        body = resp.json()
        _access_token = body.get("access_token")
        _instance_url = body.get("instance_url", SF_INSTANCE_URL)
        return _access_token
    finally:
        await client.aclose()


async def _sf_request(
    method: str, path: str, params: dict[str, Any] | None = None, json_body: dict[str, Any] | None = None,
) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Salesforce rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client(base_url=_instance_url or SF_INSTANCE_URL)
    headers = {"Authorization": f"Bearer {token}"}
    resp = await client.request(method, path, params=params, json=json_body, headers=headers)
    if resp.status_code >= 400:
        return canonical_error(
            f"Salesforce returned HTTP {resp.status_code}: {resp.text[:500]}",
            error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code,
            retryable=resp.status_code >= 500,
        )
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data — FSC-specific fields
# ---------------------------------------------------------------------------
_MOCK_ACCOUNTS = [
    {
        "Id": "001000000000001AAA",
        "Name": "Smith Household",
        "Type": "Client",
        "RecordType": {"Name": "IndustriesIndividual"},
        "FinServ__TotalFinancialAccounts__c": 3,
        "FinServ__TotalNonfinancialAssets__c": 1250000.00,
        "FinServ__InvestmentObjectives__c": "Growth",
        "FinServ__Status__c": "Active",
    },
    {
        "Id": "001000000000002AAA",
        "Name": "Johnson Family Trust",
        "Type": "Client",
        "RecordType": {"Name": "IndustriesHousehold"},
        "FinServ__TotalFinancialAccounts__c": 5,
        "FinServ__TotalNonfinancialAssets__c": 3400000.00,
        "FinServ__InvestmentObjectives__c": "Balanced",
        "FinServ__Status__c": "Active",
    },
]

_MOCK_FINANCIAL_ACCOUNT = {
    "Id": "a0B000000000001AAA",
    "Name": "Smith IRA",
    "FinServ__FinancialAccountType__c": "Individual Retirement Account",
    "FinServ__Balance__c": 485000.00,
    "FinServ__PrimaryOwner__c": "001000000000001AAA",
    "FinServ__Status__c": "Open",
    "FinServ__OpenDate__c": "2019-03-15",
    "FinServ__HeldAway__c": False,
    "FinServ__CashBalance__c": 12500.00,
}

_MOCK_HOUSEHOLD_MEMBERS = {
    "totalSize": 2,
    "records": [
        {
            "Id": "001000000000001AAA",
            "Name": "John Smith",
            "FinServ__PrimaryContact__c": "003000000000001AAA",
            "FinServ__RoleName__c": "Primary",
        },
        {
            "Id": "001000000000003AAA",
            "Name": "Jane Smith",
            "FinServ__PrimaryContact__c": "003000000000002AAA",
            "FinServ__RoleName__c": "Spouse",
        },
    ],
}


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_query_soql(args: dict[str, Any]) -> dict[str, Any]:
    soql = args.get("soql")
    if not soql:
        return canonical_error("'soql' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        if "FinServ__FinancialAccount__c" in soql:
            return tool_result({"totalSize": 1, "done": True, "records": [_MOCK_FINANCIAL_ACCOUNT], "_dev_mode": True})
        if "AccountContactRelation" in soql or "Household" in soql:
            return tool_result({**_MOCK_HOUSEHOLD_MEMBERS, "done": True, "_dev_mode": True})
        return tool_result({"totalSize": len(_MOCK_ACCOUNTS), "done": True, "records": _MOCK_ACCOUNTS, "_dev_mode": True})
    result = await _sf_request("GET", f"/services/data/{_API_VERSION}/query", params={"q": soql})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_record(args: dict[str, Any]) -> dict[str, Any]:
    object_type = args.get("object_type")
    record_id = args.get("record_id")
    if not object_type or not record_id:
        return canonical_error("'object_type' and 'record_id' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        if object_type == "FinServ__FinancialAccount__c":
            return tool_result({**_MOCK_FINANCIAL_ACCOUNT, "_dev_mode": True})
        return tool_result({**_MOCK_ACCOUNTS[0], "_dev_mode": True})
    result = await _sf_request("GET", f"/services/data/{_API_VERSION}/sobjects/{object_type}/{record_id}")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_create_record(args: dict[str, Any]) -> dict[str, Any]:
    object_type = args.get("object_type")
    fields = args.get("fields")
    if not object_type or not fields:
        return canonical_error("'object_type' and 'fields' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"id": "001000000000099AAA", "success": True, "errors": [], "_dev_mode": True})
    result = await _sf_request("POST", f"/services/data/{_API_VERSION}/sobjects/{object_type}", json_body=fields)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_update_record(args: dict[str, Any]) -> dict[str, Any]:
    object_type = args.get("object_type")
    record_id = args.get("record_id")
    fields = args.get("fields")
    if not object_type or not record_id or not fields:
        return canonical_error("'object_type', 'record_id', and 'fields' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"success": True, "record_id": record_id, "_dev_mode": True})
    result = await _sf_request("PATCH", f"/services/data/{_API_VERSION}/sobjects/{object_type}/{record_id}", json_body=fields)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result({"success": True, "record_id": record_id})


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="salesforce-fsc-adapter",
    version="1.0.0",
    vendor="salesforce_fsc",
    description="Salesforce Financial Services Cloud adapter. OAuth 2.0 auth. Dev mode returns mock data when credentials absent.",
)

_server.register_tool(
    ToolDefinition(
        name="query_soql",
        description="Execute a SOQL query against Salesforce FSC. Returns matching records.",
        inputSchema={
            "type": "object",
            "properties": {
                "soql": {
                    "type": "string",
                    "description": "SOQL query string (e.g. \"SELECT Id, Name FROM Account WHERE Type = 'Client'\")",
                },
            },
            "required": ["soql"],
            "additionalProperties": False,
        },
    ),
    _handle_query_soql,
)

_server.register_tool(
    ToolDefinition(
        name="get_record",
        description="Get a single Salesforce record by object type and record ID.",
        inputSchema={
            "type": "object",
            "properties": {
                "object_type": {
                    "type": "string",
                    "description": "Salesforce object API name (e.g. 'Account', 'Contact', 'FinServ__FinancialAccount__c')",
                },
                "record_id": {
                    "type": "string",
                    "description": "Salesforce record ID (18-char)",
                    "pattern": "^[a-zA-Z0-9]{18}$",
                },
            },
            "required": ["object_type", "record_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_record,
)

_server.register_tool(
    ToolDefinition(
        name="create_record",
        description="Create a new Salesforce record.",
        inputSchema={
            "type": "object",
            "properties": {
                "object_type": {
                    "type": "string",
                    "description": "Salesforce object API name",
                },
                "fields": {
                    "type": "object",
                    "description": "Field name-value pairs for the new record",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["object_type", "fields"],
            "additionalProperties": False,
        },
    ),
    _handle_create_record,
)

_server.register_tool(
    ToolDefinition(
        name="update_record",
        description="Update an existing Salesforce record.",
        inputSchema={
            "type": "object",
            "properties": {
                "object_type": {
                    "type": "string",
                    "description": "Salesforce object API name",
                },
                "record_id": {
                    "type": "string",
                    "description": "Salesforce record ID (18-char)",
                    "pattern": "^[a-zA-Z0-9]{18}$",
                },
                "fields": {
                    "type": "object",
                    "description": "Field name-value pairs to update",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["object_type", "record_id", "fields"],
            "additionalProperties": False,
        },
    ),
    _handle_update_record,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
