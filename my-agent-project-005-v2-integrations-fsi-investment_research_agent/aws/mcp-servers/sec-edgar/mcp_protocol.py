"""
MCP Protocol Helper — Shared module for MCP server spec compliance.

Implements the Model Context Protocol endpoints:
    GET  /           — Server info and capabilities
    POST /tools/list — Tool catalog with JSON Schema
    POST /tools/call — Invoke a tool by name with arguments

Response format follows MCP spec:
    {"content": [{"type": "text", "text": "..."}]}

Usage:
    from mcp_protocol import McpServer

    server = McpServer(name="sec-edgar", version="2.0.0", description="...")
    server.register_tool(name="get_10k", description="...", input_schema={...}, handler=fn)
    response = server.handle_mcp_request(event)
"""

import json
import logging

logger = logging.getLogger(__name__)


class McpServer:
    """MCP protocol server implementation for Lambda handlers."""

    def __init__(self, name, version="2.0.0", description=""):
        self.name = name
        self.version = version
        self.description = description
        self.tools = {}

    def register_tool(self, name, description, input_schema, handler):
        """Register a tool with the MCP server.

        Args:
            name: Tool name (used in tools/call).
            description: Human-readable tool description.
            input_schema: JSON Schema dict for the tool's input.
            handler: Callable that accepts arguments dict and returns result.
        """
        self.tools[name] = {
            "name": name,
            "description": description,
            "inputSchema": input_schema,
            "handler": handler,
        }

    def handle_mcp_request(self, event):
        """Route an MCP protocol request. Returns None if not an MCP request.

        Args:
            event: API Gateway proxy event.

        Returns:
            API Gateway proxy response dict, or None if not MCP.
        """
        method = event.get("httpMethod", "").upper()
        proxy = event.get("pathParameters", {}).get("proxy", "")
        segments = [s for s in proxy.strip("/").split("/") if s]

        if method == "GET" and (not segments or segments == [""]):
            return self._server_info()
        if method == "POST" and segments == ["tools", "list"]:
            return self._tools_list()
        if method == "POST" and segments == ["tools", "call"]:
            return self._tools_call(event)
        return None

    def _server_info(self):
        return _build_response(200, {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "protocol": "mcp",
            "capabilities": {"tools": True, "resources": False, "prompts": False},
            "tool_count": len(self.tools),
        })

    def _tools_list(self):
        tool_list = []
        for t in self.tools.values():
            tool_list.append({
                "name": t["name"],
                "description": t["description"],
                "inputSchema": t["inputSchema"],
            })
        return _build_response(200, {"tools": tool_list})

    def _tools_call(self, event):
        try:
            body = json.loads(event.get("body", "{}"))
        except (json.JSONDecodeError, TypeError):
            return _build_response(400, {
                "content": [{"type": "text", "text": "Invalid JSON body"}],
                "isError": True,
            })

        tool_name = body.get("name", "")
        arguments = body.get("arguments", {})

        if tool_name not in self.tools:
            return _build_response(404, {
                "content": [{"type": "text", "text": f"Unknown tool: {tool_name}"}],
                "isError": True,
                "available_tools": list(self.tools.keys()),
            })

        try:
            handler = self.tools[tool_name]["handler"]
            result = handler(arguments)
            result_text = json.dumps(result, default=str) if isinstance(result, dict) else str(result)
            return _build_response(200, {
                "content": [{"type": "text", "text": result_text}],
            })
        except Exception as exc:
            logger.exception("MCP tool %s failed", tool_name)
            return _build_response(500, {
                "content": [{"type": "text", "text": f"Tool execution error: {exc}"}],
                "isError": True,
            })


def _build_response(status_code, body):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=str),
    }
