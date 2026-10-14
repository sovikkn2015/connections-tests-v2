"""
Redtail CRM MCP Adapter — M11-REST (Phase 3).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

API key auth via REDTAIL_API_KEY env var.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_contacts, get_activities, get_notes, create_activity.
Small RIA CRM — REST API with API key auth.

Run: uvicorn src.server:app --host 0.0.0.0 --port 8053
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
REDTAIL_API_KEY = os.environ.get("REDTAIL_API_KEY", "")
REDTAIL_BASE_URL = os.environ.get("REDTAIL_BASE_URL", "https://api.redtailtechnology.com/crm/v1")
_DEV_MODE = not REDTAIL_API_KEY

_rpm = int(os.environ.get("REDTAIL_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("REDTAIL_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(
            base_url=REDTAIL_BASE_URL,
            headers={"Accept": "application/json", "Authorization": f"Userkeyauth {REDTAIL_API_KEY}"},
            timeout=30.0,
        )
    return _http_client


async def _redtail_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Redtail rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params)
    if resp.status_code != 200:
        return canonical_error(f"Redtail returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


async def _redtail_post(path: str, json_body: dict[str, Any]) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("Redtail rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    client = _get_http_client()
    resp = await client.post(path, json=json_body)
    if resp.status_code not in (200, 201):
        return canonical_error(f"Redtail returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data
# ---------------------------------------------------------------------------
_MOCK_CONTACTS = [
    {"id": "RT-C001", "first_name": "Alice", "last_name": "Johnson", "email": "alice.j@example.com", "phone": "555-0201", "type": "client", "category": "A"},
    {"id": "RT-C002", "first_name": "Bob", "last_name": "Williams", "email": "bob.w@example.com", "phone": "555-0202", "type": "prospect", "category": "B"},
]

_MOCK_ACTIVITIES = [
    {"id": "RT-A001", "activity_type": "meeting", "subject": "Quarterly review", "status": "pending", "due_date": "2025-02-20", "contact_id": "RT-C001"},
    {"id": "RT-A002", "activity_type": "call", "subject": "Follow-up on rollover", "status": "completed", "due_date": "2025-01-10", "contact_id": "RT-C002"},
]

_MOCK_NOTES = [
    {"id": "RT-N001", "contact_id": "RT-C001", "content": "Client interested in increasing equity allocation.", "created_at": "2025-01-08T14:30:00Z"},
    {"id": "RT-N002", "contact_id": "RT-C001", "content": "Discussed beneficiary update for IRA.", "created_at": "2025-01-05T09:15:00Z"},
]


async def _handle_get_contacts(args: dict[str, Any]) -> dict[str, Any]:
    query = args.get("query")
    if not query:
        return canonical_error("'query' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        filtered = [c for c in _MOCK_CONTACTS if query.lower() in (c["first_name"] + " " + c["last_name"]).lower()]
        return tool_result({"contacts": filtered or _MOCK_CONTACTS, "_dev_mode": True})
    result = await _redtail_get("/contacts/search", params={"query": query, "page": args.get("page", 1), "per_page": args.get("per_page", 25)})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_activities(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        activities = _MOCK_ACTIVITIES
        cid = args.get("contact_id")
        if cid:
            activities = [a for a in activities if a["contact_id"] == cid]
        atype = args.get("activity_type")
        if atype and atype != "all":
            activities = [a for a in activities if a["activity_type"] == atype]
        return tool_result({"activities": activities, "_dev_mode": True})
    params: dict[str, Any] = {}
    if args.get("contact_id"):
        params["contact_id"] = args["contact_id"]
    if args.get("activity_type") and args["activity_type"] != "all":
        params["type"] = args["activity_type"]
    if args.get("status") and args["status"] != "all":
        params["status"] = args["status"]
    result = await _redtail_get("/activities", params=params)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_notes(args: dict[str, Any]) -> dict[str, Any]:
    contact_id = args.get("contact_id")
    if not contact_id:
        return canonical_error("'contact_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        notes = [n for n in _MOCK_NOTES if n["contact_id"] == contact_id]
        return tool_result({"notes": notes, "_dev_mode": True})
    result = await _redtail_get(f"/contacts/{contact_id}/notes")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_create_activity(args: dict[str, Any]) -> dict[str, Any]:
    contact_id = args.get("contact_id")
    activity_type = args.get("activity_type")
    subject = args.get("subject")
    if not contact_id or not activity_type or not subject:
        return canonical_error("'contact_id', 'activity_type', and 'subject' are required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"id": "RT-A003", "contact_id": contact_id, "activity_type": activity_type, "subject": subject, "status": "pending", "created_at": "2025-01-15T10:00:00Z", "_dev_mode": True})
    body: dict[str, Any] = {"contact_id": contact_id, "type": activity_type, "subject": subject}
    if args.get("description"):
        body["description"] = args["description"]
    if args.get("due_date"):
        body["due_date"] = args["due_date"]
    result = await _redtail_post("/activities", body)
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="redtail-adapter",
    version="1.0.0",
    vendor="redtail",
    description="Redtail CRM adapter for small RIAs. API key auth. Dev mode returns mock data.",
)

_server.register_tool(ToolDefinition(
    name="get_contacts", description="Search contacts (clients/prospects) in Redtail CRM.",
    inputSchema={"type": "object", "properties": {
        "query": {"type": "string", "description": "Search query (name, email, phone)"},
        "page": {"type": "integer", "description": "Page number", "minimum": 1, "default": 1},
        "per_page": {"type": "integer", "description": "Results per page (1-100)", "minimum": 1, "maximum": 100, "default": 25},
    }, "required": ["query"], "additionalProperties": False},
), _handle_get_contacts)

_server.register_tool(ToolDefinition(
    name="get_activities", description="Get activities (meetings, calls, tasks) from Redtail CRM.",
    inputSchema={"type": "object", "properties": {
        "contact_id": {"type": "string", "description": "Redtail contact ID (optional)"},
        "activity_type": {"type": "string", "description": "Filter by activity type", "enum": ["meeting", "call", "task", "email", "all"], "default": "all"},
        "status": {"type": "string", "description": "Filter by status", "enum": ["pending", "completed", "all"], "default": "pending"},
    }, "required": [], "additionalProperties": False},
), _handle_get_activities)

_server.register_tool(ToolDefinition(
    name="get_notes", description="Get notes for a contact from Redtail CRM.",
    inputSchema={"type": "object", "properties": {
        "contact_id": {"type": "string", "description": "Redtail contact ID"},
    }, "required": ["contact_id"], "additionalProperties": False},
), _handle_get_notes)

_server.register_tool(ToolDefinition(
    name="create_activity", description="Create an activity (meeting, call, task) in Redtail CRM.",
    inputSchema={"type": "object", "properties": {
        "contact_id": {"type": "string", "description": "Redtail contact ID"},
        "activity_type": {"type": "string", "description": "Activity type", "enum": ["meeting", "call", "task", "email"]},
        "subject": {"type": "string", "description": "Activity subject line", "maxLength": 255},
        "description": {"type": "string", "description": "Activity description", "maxLength": 10000},
        "due_date": {"type": "string", "description": "Due date ISO 8601 (YYYY-MM-DD)", "pattern": "^\\d{4}-\\d{2}-\\d{2}$"},
    }, "required": ["contact_id", "activity_type", "subject"], "additionalProperties": False},
), _handle_create_activity)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
