"""
FactSet MCP-Native Passthrough Adapter — M11-MCP-NATIVE (Phase 4).
Minimal passthrough proxy to FactSet's own production MCP server.

Auth: FACTSET_MCP_ENDPOINT, FACTSET_OAUTH_CLIENT_ID, FACTSET_OAUTH_CLIENT_SECRET env vars.
Dev mode: returns mock passthrough responses when credentials are not configured.
Tools: proxy_tools_list, proxy_tool_call.

This adapter validates the 007 thesis: vendor-native MCP servers integrate
through M6 with near-zero custom adapter code. The adapter handles:
  1. Health check for container orchestration
  2. OAuth credential relay to FactSet's MCP endpoint
  3. Transparent proxy of tools/list and tools/call

Run: uvicorn src.server:app --host 0.0.0.0 --port 8042
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

FACTSET_MCP_ENDPOINT = os.environ.get("FACTSET_MCP_ENDPOINT", "")
FACTSET_OAUTH_CLIENT_ID = os.environ.get("FACTSET_OAUTH_CLIENT_ID", "")
FACTSET_OAUTH_CLIENT_SECRET = os.environ.get("FACTSET_OAUTH_CLIENT_SECRET", "")
_DEV_MODE = not FACTSET_MCP_ENDPOINT

_rpm = int(os.environ.get("FACTSET_RATE_LIMIT_RPM", "300"))
_burst = int(os.environ.get("FACTSET_RATE_LIMIT_BURST", "10"))
rate_limiter = TokenBucket(rate_per_second=_rpm / 60.0, burst=_burst)

_http_client: httpx.AsyncClient | None = None
_access_token: str | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(headers={"Accept": "application/json"}, timeout=30.0)
    return _http_client


async def _ensure_token() -> str | None:
    global _access_token
    if _access_token:
        return _access_token
    client = _get_http_client()
    resp = await client.post(
        f"{FACTSET_MCP_ENDPOINT}/oauth/token",
        data={"grant_type": "client_credentials"},
        auth=(FACTSET_OAUTH_CLIENT_ID, FACTSET_OAUTH_CLIENT_SECRET),
    )
    if resp.status_code != 200:
        return None
    _access_token = resp.json().get("access_token")
    return _access_token


# Dev-mode mock — simulates FactSet's MCP server response
_MOCK_FACTSET_TOOLS = [
    {"name": "factset_company_data", "description": "Get company fundamentals from FactSet", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "factset_estimates", "description": "Get consensus estimates from FactSet", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"}}, "required": ["ticker"]}},
    {"name": "factset_prices", "description": "Get price history from FactSet", "inputSchema": {"type": "object", "properties": {"ticker": {"type": "string"}, "start_date": {"type": "string"}, "end_date": {"type": "string"}}, "required": ["ticker"]}},
]


async def _handle_proxy_tools_list(args: dict[str, Any]) -> dict[str, Any]:
    if _DEV_MODE:
        return tool_result({"tools": _MOCK_FACTSET_TOOLS, "_dev_mode": True, "_note": "Mock FactSet MCP tools — real tools discovered from FACTSET_MCP_ENDPOINT"})
    if not await rate_limiter.acquire():
        return canonical_error("FactSet rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("FactSet OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.post(f"{FACTSET_MCP_ENDPOINT}/tools/list", headers={"Authorization": f"Bearer {token}"})
    if resp.status_code != 200:
        return canonical_error(f"FactSet MCP returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return tool_result(resp.json())


async def _handle_proxy_tool_call(args: dict[str, Any]) -> dict[str, Any]:
    tool_name = args.get("tool_name")
    tool_arguments = args.get("tool_arguments", {})
    if not tool_name:
        return canonical_error("'tool_name' is required.", error_code="INVALID_PARAMS")
    if _DEV_MODE:
        return tool_result({"proxied_tool": tool_name, "proxied_arguments": tool_arguments, "result": {"message": f"Mock response for {tool_name}"}, "_dev_mode": True})
    if not await rate_limiter.acquire():
        return canonical_error("FactSet rate limit exceeded.", error_code="RATE_LIMIT_EXCEEDED", vendor_status_code=429, retryable=True)
    token = await _ensure_token()
    if not token:
        return canonical_error("FactSet OAuth token acquisition failed.", error_code="AUTH_FAILED", retryable=True)
    client = _get_http_client()
    resp = await client.post(f"{FACTSET_MCP_ENDPOINT}/tools/call", headers={"Authorization": f"Bearer {token}"}, json={"name": tool_name, "arguments": tool_arguments})
    if resp.status_code != 200:
        return canonical_error(f"FactSet MCP returned HTTP {resp.status_code}", error_code="VENDOR_HTTP_ERROR", vendor_status_code=resp.status_code, retryable=resp.status_code >= 500)
    return resp.json()


_server = MCPAdapterServer(
    name="factset-native-adapter", version="1.0.0", vendor="factset",
    description="FactSet MCP-Native passthrough. Near-zero adapter code. Proxies to FactSet's own MCP server.",
)

_server.register_tool(ToolDefinition(
    name="proxy_tools_list",
    description="Proxy tools/list to FactSet's native MCP server. Returns FactSet's own tool catalog.",
    inputSchema={"type": "object", "properties": {}, "required": [], "additionalProperties": False},
), _handle_proxy_tools_list)

_server.register_tool(ToolDefinition(
    name="proxy_tool_call",
    description="Proxy a tool call to FactSet's native MCP server with OAuth credential relay.",
    inputSchema={"type": "object", "properties": {
        "tool_name": {"type": "string", "description": "Name of the FactSet MCP tool to call"},
        "tool_arguments": {"type": "object", "description": "Arguments to pass to the FactSet tool"},
    }, "required": ["tool_name"], "additionalProperties": False},
), _handle_proxy_tool_call)

app = _server.build_app()


@app.on_event("shutdown")
async def shutdown() -> None:
    global _http_client
    if _http_client:
        await _http_client.aclose()
        _http_client = None
