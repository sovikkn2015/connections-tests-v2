"""
eMoney Advisor MCP Adapter — M11-REST (Phase 2).
Returns raw vendor data. M6 gateway calls M7 translator to convert to canonical types.

OAuth 2.0 auth via EMONEY_CLIENT_ID / EMONEY_CLIENT_SECRET env vars.
Dev mode: returns realistic mock data when credentials are not configured.
Tools: get_clients, get_plans, get_goals, get_plan_summary.

Note: eMoney is Fidelity-owned with a poorly documented API (per ARCH-09).

Run: uvicorn src.server:app --host 0.0.0.0 --port 8015
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
EMONEY_CLIENT_ID = os.environ.get("EMONEY_CLIENT_ID", "")
EMONEY_CLIENT_SECRET = os.environ.get("EMONEY_CLIENT_SECRET", "")
EMONEY_BASE_URL = os.environ.get("EMONEY_BASE_URL", "https://api.emoneyadvisor.com/api/v1")
_DEV_MODE = not EMONEY_CLIENT_ID

_rpm = int(os.environ.get("EMONEY_RATE_LIMIT_RPM", "120"))
_burst = int(os.environ.get("EMONEY_RATE_LIMIT_BURST", "5"))
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
            base_url=EMONEY_BASE_URL,
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
        auth=(EMONEY_CLIENT_ID, EMONEY_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


async def _emoney_get(path: str, params: dict[str, Any] | None = None) -> Any:
    if not await rate_limiter.acquire():
        return canonical_error("eMoney rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.get(path, params=params, headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"eMoney returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


# ---------------------------------------------------------------------------
# Dev-mode mock data — eMoney financial planning
# ---------------------------------------------------------------------------
_MOCK_CLIENTS = [
    {
        "clientId": "EM-1001",
        "firstName": "John",
        "lastName": "Smith",
        "email": "[email]",
        "advisorId": "ADV-100",
        "status": "Active",
        "planCount": 2,
        "lastLoginDate": "2025-06-15",
    },
    {
        "clientId": "EM-1002",
        "firstName": "Jane",
        "lastName": "Smith",
        "email": "[email]",
        "advisorId": "ADV-100",
        "status": "Active",
        "planCount": 1,
        "lastLoginDate": "2025-07-01",
    },
]

_MOCK_PLANS = [
    {
        "planId": "PLN-5001",
        "clientId": "EM-1001",
        "name": "Smith Retirement Plan",
        "planType": "Retirement",
        "status": "Active",
        "createdDate": "2023-01-15",
        "lastModified": "2025-06-20",
        "assumptions": {
            "inflationRate": 2.5,
            "returnRate": 6.5,
            "retirementAge": 65,
            "lifeExpectancy": 92,
            "socialSecurityStartAge": 67,
        },
    },
    {
        "planId": "PLN-5002",
        "clientId": "EM-1001",
        "name": "Smith Education Plan",
        "planType": "Education",
        "status": "Active",
        "createdDate": "2024-03-10",
        "lastModified": "2025-05-12",
        "assumptions": {
            "inflationRate": 3.0,
            "returnRate": 5.0,
            "educationStartYear": 2030,
            "yearsOfEducation": 4,
        },
    },
]

_MOCK_GOALS = [
    {
        "goalId": "GOAL-7001",
        "planId": "PLN-5001",
        "name": "Retirement Income",
        "goalType": "Retirement",
        "targetAmount": 120000.00,
        "targetDate": "2035-01-01",
        "currentFunding": 805000.00,
        "requiredFunding": 2400000.00,
        "probabilityOfSuccess": 82.5,
        "status": "On Track",
        "priority": "High",
    },
    {
        "goalId": "GOAL-7002",
        "planId": "PLN-5001",
        "name": "Legacy / Estate",
        "goalType": "Estate",
        "targetAmount": 500000.00,
        "targetDate": "2060-01-01",
        "currentFunding": 805000.00,
        "requiredFunding": 500000.00,
        "probabilityOfSuccess": 91.0,
        "status": "On Track",
        "priority": "Medium",
    },
    {
        "goalId": "GOAL-7003",
        "planId": "PLN-5002",
        "name": "College Fund — Child 1",
        "goalType": "Education",
        "targetAmount": 200000.00,
        "targetDate": "2030-09-01",
        "currentFunding": 85000.00,
        "requiredFunding": 200000.00,
        "probabilityOfSuccess": 68.0,
        "status": "Needs Attention",
        "priority": "High",
    },
]

_MOCK_PLAN_SUMMARY = {
    "planId": "PLN-5001",
    "clientName": "John Smith",
    "totalNetWorth": 1850000.00,
    "totalAssets": 2100000.00,
    "totalLiabilities": 250000.00,
    "projectedRetirementIncome": 120000.00,
    "socialSecurityBenefit": 36000.00,
    "overallProbabilityOfSuccess": 82.5,
    "fundingStatus": "On Track",
    "goalCount": 2,
    "nextReviewDate": "2025-09-15",
    "monteCarloSimulations": 1000,
}


# ---------------------------------------------------------------------------
# Tool handlers
# ---------------------------------------------------------------------------
async def _handle_get_clients(args: dict[str, Any]) -> dict[str, Any]:
    advisor_id = args.get("advisor_id")
    if not advisor_id:
        return canonical_error("'advisor_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"clients": _MOCK_CLIENTS, "_dev_mode": True})
    result = await _emoney_get("/clients", params={"advisorId": advisor_id})
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_plans(args: dict[str, Any]) -> dict[str, Any]:
    client_id = args.get("client_id")
    if not client_id:
        return canonical_error("'client_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        plans = [p for p in _MOCK_PLANS if p["clientId"] == client_id] or _MOCK_PLANS
        return tool_result({"plans": plans, "_dev_mode": True})
    result = await _emoney_get(f"/clients/{client_id}/plans")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_goals(args: dict[str, Any]) -> dict[str, Any]:
    plan_id = args.get("plan_id")
    if not plan_id:
        return canonical_error("'plan_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        goals = [g for g in _MOCK_GOALS if g["planId"] == plan_id] or _MOCK_GOALS
        return tool_result({"planId": plan_id, "goals": goals, "_dev_mode": True})
    result = await _emoney_get(f"/plans/{plan_id}/goals")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


async def _handle_get_plan_summary(args: dict[str, Any]) -> dict[str, Any]:
    plan_id = args.get("plan_id")
    if not plan_id:
        return canonical_error("'plan_id' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({**_MOCK_PLAN_SUMMARY, "planId": plan_id, "_dev_mode": True})
    result = await _emoney_get(f"/plans/{plan_id}/summary")
    if isinstance(result, dict) and result.get("isError"):
        return result
    return tool_result(result)


# ---------------------------------------------------------------------------
# MCP server assembly
# ---------------------------------------------------------------------------
_server = MCPAdapterServer(
    name="emoney-adapter",
    version="1.0.0",
    vendor="emoney",
    description="eMoney Advisor financial planning adapter. OAuth 2.0 auth. Dev mode returns mock data when credentials absent. Fidelity-owned, limited API docs.",
)

_server.register_tool(
    ToolDefinition(
        name="get_clients",
        description="Get eMoney clients for an advisor.",
        inputSchema={
            "type": "object",
            "properties": {
                "advisor_id": {"type": "string", "description": "eMoney advisor ID"},
            },
            "required": ["advisor_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_clients,
)

_server.register_tool(
    ToolDefinition(
        name="get_plans",
        description="Get financial plans for an eMoney client.",
        inputSchema={
            "type": "object",
            "properties": {
                "client_id": {"type": "string", "description": "eMoney client ID"},
            },
            "required": ["client_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_plans,
)

_server.register_tool(
    ToolDefinition(
        name="get_goals",
        description="Get financial goals for a plan. Returns goal list with target amounts, timelines, and probability of success.",
        inputSchema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "eMoney financial plan ID"},
            },
            "required": ["plan_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_goals,
)

_server.register_tool(
    ToolDefinition(
        name="get_plan_summary",
        description="Get financial plan summary. Returns plan overview including net worth, projected outcomes, funding status, and Monte Carlo probability.",
        inputSchema={
            "type": "object",
            "properties": {
                "plan_id": {"type": "string", "description": "eMoney financial plan ID"},
            },
            "required": ["plan_id"],
            "additionalProperties": False,
        },
    ),
    _handle_get_plan_summary,
)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
