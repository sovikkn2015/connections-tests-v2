"""MCP Lambda handler — wraps a Server instance.

Responsibilities:
- Parse API Gateway proxy event into (method, path, body, headers).
- Validate X-MCP-API-Key header against MCP_API_KEY env var.
- Route to GET / (health), POST /tools/list, POST /tools/call.
- Emit an OpenTelemetry-compatible span + Langfuse event per tool call.
- Extract principal_id, agent_id, persona, session_id from MCP headers
  and attach them to every span for cross-persona trace stitching.
- Convert McpError subclasses to structured ToolResult errors.

Kept deliberately small (~200 lines). The tracing adapters (OTel, Langfuse)
degrade silently when the env vars are absent, so tests don't need creds.
"""

from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import Any, Callable

from pydantic import ValidationError

from .errors import (
    McpAuthError,
    McpError,
    McpToolNotFoundError,
    McpValidationError,
)
from .schemas import ToolCall, ToolError, ToolResult, ToolSpec

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


# ---------------------------------------------------------------------------
# Response builders
# ---------------------------------------------------------------------------

def _cors_headers() -> dict[str, str]:
    origin = os.environ.get("CORS_ALLOW_ORIGIN", "https://agentcore.local")
    return {
        "Access-Control-Allow-Origin": origin,
        "Access-Control-Allow-Headers": (
            "Content-Type,X-MCP-API-Key,X-Principal-Id,X-Agent-Id,"
            "X-Persona,X-Session-Id"
        ),
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    }


def build_response(status_code: int, body: Any) -> dict:
    return {
        "statusCode": status_code,
        "headers": {**_cors_headers(), "Content-Type": "application/json"},
        "body": json.dumps(body, default=str),
    }


# ---------------------------------------------------------------------------
# Tracing shim — emits structured logs; real OTel / Langfuse adapters wrap
# this in deployment via a layer. Absence of creds is non-fatal.
# ---------------------------------------------------------------------------

def _emit_span(event: dict) -> None:
    """Structured-log a span. Langfuse ingester reads these via CloudWatch subscription."""
    logger.info("mcp.span %s", json.dumps(event, default=str))


# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

ToolHandler = Callable[[dict[str, Any], dict[str, str]], Any]


class McpServer:
    """
    Minimal MCP server — register tools, handle Lambda events.

    Each handler receives (arguments, context_headers) and returns any
    JSON-serializable value OR raises an McpError subclass.
    """

    def __init__(self, name: str, version: str = "1.0.0", description: str = "") -> None:
        self.name = name
        self.version = version
        self.description = description
        self._specs: dict[str, ToolSpec] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(self, spec: ToolSpec, handler: ToolHandler) -> None:
        self._specs[spec.name] = spec
        self._handlers[spec.name] = handler

    # ------------------------------------------------------------------
    def handle(self, event: dict, context: Any | None = None) -> dict:
        method = (event.get("httpMethod") or "GET").upper()
        path = event.get("path") or "/"
        headers = {k.lower(): v for k, v in (event.get("headers") or {}).items()}

        if method == "OPTIONS":
            return build_response(200, {})

        if method == "GET":
            # Health check — no auth required so load balancers can probe.
            return self._handle_info()

        try:
            self._require_api_key(headers)
        except McpAuthError as exc:
            return self._error_response(exc)

        if method != "POST":
            return self._error_response(McpError("Method not allowed", code=-32601))

        try:
            body = json.loads(event.get("body") or "{}")
        except json.JSONDecodeError:
            return self._error_response(
                McpValidationError("Body must be valid JSON")
            )

        if path.endswith("/tools/list"):
            return self._handle_list()

        if path.endswith("/tools/call"):
            return self._handle_call(body, headers)

        return self._error_response(McpError("Not found", code=-32601))

    # ------------------------------------------------------------------
    def _require_api_key(self, headers: dict[str, str]) -> None:
        expected = os.environ.get("MCP_API_KEY")
        dev_mode = os.environ.get("MCP_DEV_MODE", "").lower() == "true"
        if not expected:
            # Fail-closed: missing MCP_API_KEY is a prod misconfig, not auth bypass.
            # Only dev mode (explicit MCP_DEV_MODE=true) allows unauthenticated calls.
            if dev_mode:
                return
            raise McpAuthError(
                "MCP_API_KEY env var required; set MCP_DEV_MODE=true only for local dev"
            )
        supplied = headers.get("x-mcp-api-key")
        if not supplied or supplied != expected:
            raise McpAuthError("Missing or invalid X-MCP-API-Key")

    def _handle_info(self) -> dict:
        return build_response(
            200,
            {
                "name": self.name,
                "version": self.version,
                "description": self.description,
                "protocol": "mcp/1.0",
                "tools": [spec.name for spec in self._specs.values()],
            },
        )

    def _handle_list(self) -> dict:
        return build_response(
            200,
            {
                "tools": [
                    {
                        "name": spec.name,
                        "description": spec.description,
                        "inputSchema": spec.input_schema,
                    }
                    for spec in self._specs.values()
                ]
            },
        )

    def _handle_call(self, body: dict, headers: dict[str, str]) -> dict:
        try:
            call = ToolCall(**body)
        except ValidationError as exc:
            return self._error_response(
                McpValidationError("Invalid tool call payload", details={"errors": exc.errors()})
            )

        call_id = call.tool_call_id or f"tc_{uuid.uuid4().hex[:12]}"

        if call.name not in self._handlers:
            return self._error_response(
                McpToolNotFoundError(f"Unknown tool: {call.name}"),
                tool_call_id=call_id,
            )

        context_headers = {
            "principal_id": headers.get("x-principal-id", ""),
            "agent_id": headers.get("x-agent-id", ""),
            "persona": headers.get("x-persona", ""),
            "session_id": headers.get("x-session-id", ""),
        }

        span_start = time.time()
        span_event = {
            "span": "mcp.tool_call",
            "server": self.name,
            "tool": call.name,
            "tool_call_id": call_id,
            **context_headers,
        }

        try:
            raw = self._handlers[call.name](call.arguments, context_headers)
            duration_ms = int((time.time() - span_start) * 1000)
            _emit_span({**span_event, "status": "ok", "duration_ms": duration_ms})
            result = ToolResult(
                tool_call_id=call_id,
                status="ok",
                result=raw if isinstance(raw, (dict, list, str)) else {"value": raw},
            )
            return build_response(200, result.model_dump(exclude_none=True))

        except McpError as exc:
            duration_ms = int((time.time() - span_start) * 1000)
            _emit_span({
                **span_event,
                "status": "error",
                "duration_ms": duration_ms,
                "error_code": exc.code,
                "error_message": exc.message,
            })
            return self._error_response(exc, tool_call_id=call_id)

        except Exception as exc:
            logger.exception("Unhandled error in tool %s", call.name)
            duration_ms = int((time.time() - span_start) * 1000)
            _emit_span({
                **span_event,
                "status": "error",
                "duration_ms": duration_ms,
                "error_code": -32000,
                "error_message": str(exc)[:200],
            })
            return self._error_response(
                McpError("Internal server error", code=-32000),
                tool_call_id=call_id,
            )

    # ------------------------------------------------------------------
    def _error_response(self, exc: McpError, tool_call_id: str = "") -> dict:
        result = ToolResult(
            tool_call_id=tool_call_id,
            status="error",
            error=ToolError(code=exc.code, message=exc.message, details=exc.details or None),
        )
        return build_response(exc.http_status, result.model_dump(exclude_none=True))
