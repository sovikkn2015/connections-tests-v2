"""mcp_invoke.run — call any MCP server tool by name.

Usage from a specialist via Bedrock tool-use:
  {"server": "market-data", "tool": "get_quote", "arguments": {"symbol": "NVDA"}}

Returns the raw MCP result dict plus a `_meta` block with timing.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from .._mcp_client import MCPClient, MCPError, get_shared_mock_client


_ALLOWED_SERVERS = {
    "market-data",
    "sec-edgar",
    "news-search",
    "salesforce-crm",
    "mulesoft-actions",
}


class McpInvokeInput(BaseModel):
    """Invoke a tool on a named MCP server."""

    server: str = Field(..., description="MCP server name (e.g. market-data, sec-edgar, news-search, salesforce-crm)")
    tool: str = Field(..., min_length=1, description="Tool name within the server (e.g. get_quote, get_latest_filing)")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool arguments as per the MCP tools/list schema")
    principal_id: str = Field("dev-principal", description="Principal id to pass in X-Principal-Id header")
    agent_id: str = Field("dev-agent", description="Agent id")
    persona: str = Field("fsi_research", description="Persona")
    session_id: str = Field("dev-session", description="Session id")

    model_config = {"frozen": True}


class McpInvokeOutput(BaseModel):
    """Raw MCP response plus meta."""

    server: str
    tool: str
    result: Dict[str, Any]
    status: str
    elapsed_ms: int
    ran_at: datetime

    model_config = {"frozen": True}


async def run(
    payload: McpInvokeInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> McpInvokeOutput:
    """Proxy the call to the MCP client."""
    if payload.server not in _ALLOWED_SERVERS:
        raise ValueError(f"server {payload.server!r} not in allowlist")

    client = mcp or get_shared_mock_client()
    started = datetime.now(timezone.utc)
    try:
        result = await client.call(
            server=payload.server,
            tool=payload.tool,
            arguments=payload.arguments,
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            persona=payload.persona,
            session_id=payload.session_id,
        )
        status = "ok"
    except MCPError as exc:
        result = {"error_code": exc.code if hasattr(exc, "code") else None, "error_reason": str(exc)[:400]}
        status = "error"

    elapsed_ms = int((datetime.now(timezone.utc) - started).total_seconds() * 1000)
    return McpInvokeOutput(
        server=payload.server,
        tool=payload.tool,
        result=result if isinstance(result, dict) else {"value": result},
        status=status,
        elapsed_ms=elapsed_ms,
        ran_at=started,
    )
