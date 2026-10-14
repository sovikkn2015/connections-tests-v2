"""
Wealthbox CRM MCP Adapter — M11-REST (Phase 3).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

API key auth via WEALTHBOX_API_KEY env var.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_contacts, get_tasks, get_opportunities, create_note.
Small RIA CRM — lightweight REST API.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8052
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
WEALTHBOX_API_KEY = os.environ.get("WEALTHBOX_API_KEY", "")
WEALTHBOX_BASE_URL = os.environ.get("WEALTHBOX_BASE_URL", "https://api.crmworkspace.com/v1")
_DEV_MODE = not WEALTHBOX_API_KEY

_rpm = int(os.environ.get("WEALTHBOX_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("WEALTHBOX_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=WEALTHBOX_BASE_URL,
            headers={"Accept": "application/json", "ACCESS_TOKEN": WEALTHBOX_API_KEY},
            timeout=30.0,
        )
    return _http_client


async def _wealthbox_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Wealthbox rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params)
    if resp.status_code != 200:
        return canonical_error(f"Wealthbox returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


async def _wealthbox_post(path: str, json_body: dict[str, Any]) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Wealthbox rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    client = _get_http_client()
    resp = await client.post(path, json=json_body)
    if resp.status_code not in (200, 201):
        return canonical_error(f"Wealthbox returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data
# ---------------------------------------------------------------------------
_MOCK_CONTACTS = [
    {"id": "WB-C001", "first_name": "Jane", "last_name": "Doe", "email": "jane.doe@example.com", "phone": "555-0101", "type": "client", "tags": ["high-net-worth"]},
    {"id": "WB-C002", "first_name": "Robert", "last_name": "Smith", "email": "r.smith@example.com", "phone": "555-0102", "type": "prospect", "tags": ["referral"]},
]

_MOCK_TASKS = [
    {"id": "WB-T001", "subject": "Annual review meeting", "status": "pending", "due_date": "2025-02-15", "contact_id": "WB-C001", "assignee": "advisor@example.com"},
    {"id": "WB-T002", "subject": "Send IPS document", "status": "pending", "due_date": "2025-02-10", "contact_id": "WB-C001", "assignee": "advisor@example.com"},
]

_MOCK_OPPORTUNITIES = [
    {"id": "WB-O001", "name": "Smith Rollover IRA", "stage": "proposal", "amount": 250000.00, "contact_id": "WB-C002", "close_date": "2025-03-01"},
]


async def _handle_get_contacts(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not query:
        return canonical_error("'query' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        filtered = [c for c in _MOCK_CONTACTS if query.lower() in (c["first_name"] + " " + c["last_name"]).lower()]
        return tool_result({"contacts": filtered or _MOCK_CONTACTS, "_dev_mode": True})
    result = await _wealthbox_get("/contacts", params={"query": query, "page": args.get("page", 1), "per_page": args.get("per_page", 25)})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_tasks(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        tasks = _MOCK_TASKS
        contact_id = args.get("contact_id")
        if contact_id:
            tasks = [t for t in tasks if t["contact_id"] == contact_id]
        return tool_result({"tasks": tasks, "_dev_mode": True})
    params: dict[str, Any] = {}
    if args.get("contact_id"):
        params["contact_id"] = args["contact_id"]
    if args.get("status") and args["status"] != "all":
        params["status"] = args["status"]
    result = await _wealthbox_get("/tasks", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_opportunities(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        opps = _MOCK_OPPORTUNITIES
        contact_id = args.get("contact_id")
        if contact_id:
            opps = [o for o in opps if o["contact_id"] == contact_id]
        return tool_result({"opportunities": opps, "_dev_mode": True})
    params: dict[str, Any] = {}
    if args.get("contact_id"):
        params["contact_id"] = args["contact_id"]
    if args.get("stage") and args["stage"] != "all":
        params["stage"] = args["stage"]
    result = await _wealthbox_get("/opportunities", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_create_note(args: dict[str, Any]) -> dict[str, Any]:
    contact_id = args.get("contact_id")
    content = args.get("content")
    if not contact_id or not content:
        return canonical_error("'contact_id' and 'content' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"id": "WB-N001", "contact_id": contact_id, "content": content, "created_at": "2025-01-15T10:00:00Z", "_dev_mode": True})
    result = await _wealthbox_post(f"/contacts/{contact_id}/notes", {"content": content})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="wealthbox-adapter",
    version="1.0.0",
    vendor="wealthbox",
    description="Wealthbox CRM adapter for small RIAs. API key auth. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="get_contacts", description="Search contacts (clients/prospects) in Wealthbox CRM.",
    inputSchema={"type": "object", "properties": {
        "query": {"type": "string", "description": "Search query (name, email, phone)"},
        "page": {"type": "integer", "description": "Page number", "minimum": 1, "default": 1},
        "per_page": {"type": "integer", "description": "Results per page (1-100)", "minimum": 1, "maximum": 100, "default": 25},
    }, "required": ["query"], "additionalProperties": False},
), _handle_get_contacts)

_server.register_tool(ToolDefinition(
    name="get_tasks", description="Get tasks assigned to the current user or a specific contact.",
    inputSchema={"type": "object", "properties": {
        "contact_id": {"type": "string", "description": "Wealthbox contact ID (optional)"},
        "status": {"type": "string", "description": "Filter by task status", "enum": ["pending", "completed", "all"], "default": "pending"},
    }, "required": [], "additionalProperties": False},
), _handle_get_tasks)

_server.register_tool(ToolDefinition(
    name="get_opportunities", description="Get sales opportunities (pipeline) from Wealthbox CRM.",
    inputSchema={"type": "object", "properties": {
        "contact_id": {"type": "string", "description": "Wealthbox contact ID (optional)"},
        "stage": {"type": "string", "description": "Filter by pipeline stage", "enum": ["prospect", "qualified", "proposal", "won", "lost", "all"], "default": "all"},
    }, "required": [], "additionalProperties": False},
), _handle_get_opportunities)

_server.register_tool(ToolDefinition(
    name="create_note", description="Create a note on a Wealthbox contact record.",
    inputSchema={"type": "object", "properties": {
        "contact_id": {"type": "string", "description": "Wealthbox contact ID"},
        "content": {"type": "string", "description": "Note content (plain text)", "maxLength": 10000},
    }, "required": ["contact_id", "content"], "additionalProperties": False},
), _handle_create_note)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
