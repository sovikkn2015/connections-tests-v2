"""mcp_invoke skill — generic MCP server proxy for research specialists.

Lets a specialist call any tool on any allowlisted MCP server via one
toolConfig entry rather than one per tool. Returns the raw MCP response.

Intentionally thin: no normalization, no caching, no retry (the MCP
client handles retries). Specialists are expected to format the
resulting JSON into their output shape.
"""

from .actions import McpInvokeInput, McpInvokeOutput, run

__all__ = ["McpInvokeInput", "McpInvokeOutput", "run"]
