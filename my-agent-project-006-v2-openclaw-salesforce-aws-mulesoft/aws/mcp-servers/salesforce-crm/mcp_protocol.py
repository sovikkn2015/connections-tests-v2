"""
Shared MCP Protocol handler for all MCP servers.
Implements GET / (server info), POST /tools/list, POST /tools/call.
"""

import json
import logging
import os

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Fix #4: CORS — read allowed origin from env, no wildcard
# ---------------------------------------------------------------------------
def _cors_headers():
    origin = os.environ.get("CORS_ALLOW_ORIGIN", "http://localhost:5173")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": "Content-Type,x-api-key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def _response(status_code: int, body: dict) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body),
    }


# ---------------------------------------------------------------------------
# Fix #1: Content boundary markers to mitigate indirect prompt injection
# ---------------------------------------------------------------------------
def _mcp_text(text: str, source: str = "") -> dict:
    """Standard MCP content response with boundary markers and source attribution."""
    clean = text.replace("[TOOL_OUTPUT_START]", "").replace("[TOOL_OUTPUT_END]", "")
    clean = clean.replace("[SYSTEM]", "").replace("[/SYSTEM]", "")
    clean = clean.replace("<system>", "").replace("</system>", "")
    # Prepend source attribution for auditability (FINRA requirement)
    if source:
        clean = f"[Source: {source}]\nIMPORTANT: Include 'Source: {source}' in your response when citing this data.\n{clean}"
    bounded = f"[TOOL_OUTPUT_START]\n{clean}\n[TOOL_OUTPUT_END]"
    return {"content": [{"type": "text", "text": bounded}]}


def _mcp_error(message: str, code: int = -1) -> dict:
    """Standard MCP error response."""
    return {"error": {"code": code, "message": message}}


# ---------------------------------------------------------------------------
# Fix #3: Input sanitization to prevent injection via tool parameters
# ---------------------------------------------------------------------------
def _sanitize_value(value):
    """Sanitize a single value."""
    if isinstance(value, str):
        clean = ''.join(c for c in value if c.isprintable() or c in '\n\t')
        return clean[:10000]  # Max 10K chars per string param
    return value


def _sanitize_params(params: dict) -> dict:
    """Sanitize tool input parameters to prevent injection."""
    sanitized = {}
    for key, value in params.items():
        if isinstance(value, str):
            clean = ''.join(c for c in value if c.isprintable() or c in '\n\t')
            sanitized[key] = clean[:10000]
        elif isinstance(value, (int, float, bool)):
            sanitized[key] = value
        elif isinstance(value, list):
            sanitized[key] = [_sanitize_value(v) for v in value[:100]]  # Max 100 items
        elif isinstance(value, dict):
            sanitized[key] = _sanitize_params(value)
        else:
            sanitized[key] = value
    return sanitized


def _validate_params(params: dict, schema: dict) -> str | None:
    """
    Lightweight JSON Schema validation for tool inputs.
    Returns an error message string if invalid, None if valid.
    Checks: required fields, basic type matching.
    """
    required = schema.get("required", [])
    properties = schema.get("properties", {})

    for field in required:
        if field not in params:
            return f"Missing required parameter: {field}"

    type_map = {
        "string": str,
        "integer": int,
        "number": (int, float),
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    for key, value in params.items():
        if key in properties:
            expected_type = properties[key].get("type")
            if expected_type and expected_type in type_map:
                if not isinstance(value, type_map[expected_type]):
                    return f"Parameter '{key}' must be of type {expected_type}"

    return None


class McpServer:
    """
    Generic MCP server that routes Lambda events to the correct handler.

    Usage:
        server = McpServer(name="my-server", version="1.0.0")
        server.register_tool("tool_name", schema_dict, handler_fn)
        # In lambda_handler:
        return server.handle(event)
    """

    def __init__(self, name: str, version: str = "1.0.0", description: str = ""):
        self.name = name
        self.version = version
        self.description = description
        self._tools: dict[str, dict] = {}
        self._handlers: dict[str, callable] = {}

    def register_tool(self, name: str, schema: dict, handler: callable):
        """Register a tool with its JSON Schema and handler function."""
        self._tools[name] = schema
        self._handlers[name] = handler

    def handle(self, event: dict) -> dict:
        """Route an API Gateway proxy event to the correct MCP endpoint."""
        method = event.get("httpMethod", "GET").upper()
        path = event.get("path", "/")

        # OPTIONS — CORS preflight
        if method == "OPTIONS":
            return _response(200, {})

        # GET / — server info
        if method == "GET":
            return self._handle_info()

        # POST routes
        if method == "POST":
            if path.endswith("/tools/list"):
                return self._handle_tools_list()
            if path.endswith("/tools/call"):
                return self._handle_tools_call(event)

        return _response(404, _mcp_error("Not found"))

    # ------------------------------------------------------------------
    def _handle_info(self) -> dict:
        return _response(200, {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "protocol": "mcp",
            "endpoints": {
                "tools_list": "POST /tools/list",
                "tools_call": "POST /tools/call",
            },
        })

    def _handle_tools_list(self) -> dict:
        tools = []
        for name, schema in self._tools.items():
            tools.append({
                "name": name,
                "description": schema.get("description", ""),
                "inputSchema": {
                    "type": "object",
                    "properties": schema.get("properties", {}),
                    "required": schema.get("required", []),
                },
            })
        return _response(200, {"tools": tools})

    def _handle_tools_call(self, event: dict) -> dict:
        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return _response(400, _mcp_error("Invalid JSON body"))

        tool_name = body.get("name")
        if not tool_name:
            return _response(400, _mcp_error("Missing 'name' in request body"))

        if tool_name not in self._handlers:
            return _response(404, _mcp_error(f"Unknown tool: {tool_name}"))

        params = body.get("arguments", {})
        schema = self._tools[tool_name]

        # Fix #3: sanitize inputs before validation and execution
        params = _sanitize_params(params)

        # Validate inputs
        validation_error = _validate_params(params, schema)
        if validation_error:
            return _response(400, _mcp_error(validation_error))

        # Execute handler
        try:
            result = self._handlers[tool_name](params)
            if isinstance(result, str):
                return _response(200, _mcp_text(result, source=self.name))
            if isinstance(result, dict) and "content" in result:
                return _response(200, result)
            return _response(200, _mcp_text(json.dumps(result, default=str), source=self.name))
        except Exception as exc:
            # Fix #5: log full error server-side, return generic message to client
            logger.exception("Tool %s execution failed", tool_name)
            return _response(500, _mcp_error("Tool execution failed. Check server logs for details."))
