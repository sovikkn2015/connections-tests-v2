"""Shared MCP server base — protocol handler, schemas, errors, tracing.

Layered under aws/mcp-servers/_base/ so every V3 MCP server Lambda imports
the identical protocol implementation. Bundled as a Lambda layer at deploy
time; mounted at /opt/python/_base/ so `from _base import ...` resolves
both locally (sys.path hack in each app.py) and in Lambda.
"""

from .schemas import ToolSpec, ToolCall, ToolResult, ToolError
from .errors import McpError, McpAuthError, McpValidationError, McpUpstreamError
from .mcp_server import McpServer, build_response

__all__ = [
    "ToolSpec",
    "ToolCall",
    "ToolResult",
    "ToolError",
    "McpError",
    "McpAuthError",
    "McpValidationError",
    "McpUpstreamError",
    "McpServer",
    "build_response",
]
