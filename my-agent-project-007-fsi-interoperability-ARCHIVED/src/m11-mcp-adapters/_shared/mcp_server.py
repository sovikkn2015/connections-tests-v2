"""
Base MCP server factory for M11 adapters.
Creates a FastAPI app with the three mandatory endpoints (Rule 1):
  GET  /          — Server info + health check (Rule 16)
  POST /tools/list — Capability discovery with JSON Schema (Rule 2)
  POST /tools/call — Tool execution

All adapters MUST use this factory to eliminate boilerplate.
Vendor-specific logic lives in each adapter's server.py as tool definitions + handlers.
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable, Awaitable

import structlog
from fastapi import FastAPI, Request, Response
from pydantic import BaseModel

from .errors import canonical_error
from .logging import get_logger


class ToolCallRequest(BaseModel):
    """Request body for POST /tools/call."""
    name: str
    arguments: dict[str, Any] = {}


class ToolDefinition(BaseModel):
    """A tool exposed by this MCP adapter."""
    name: str
    description: str
    inputSchema: dict[str, Any]
    status: str = "active"


ToolHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]


class MCPAdapterServer:
    """Factory that builds a FastAPI app implementing the MCP interface contract."""

    def __init__(
        self,
        name: str,
        version: str,
        vendor: str,
        description: str,
    ) -> None:
        self.name = name
        self.version = version
        self.vendor = vendor
        self.description = description
        self._tools: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}
        self.logger = get_logger(adapter_name=name, vendor=vendor)

    def register_tool(
        self,
        definition: ToolDefinition,
        handler: ToolHandler,
    ) -> None:
        """Register a tool with its definition and async handler."""
        self._tools[definition.name] = definition
        self._handlers[definition.name] = handler

    def build_app(self) -> FastAPI:
        """Build and return the FastAPI application."""
        app = FastAPI(title=self.name, version=self.version)
        server = self

        @app.middleware("http")
        async def request_context(request: Request, call_next: Any) -> Response:
            request_id = request.headers.get("x-request-id", str(uuid.uuid4()))
            structlog.contextvars.clear_contextvars()
            structlog.contextvars.bind_contextvars(request_id=request_id)
            start = time.monotonic()
            response: Response = await call_next(request)
            duration_ms = round((time.monotonic() - start) * 1000, 2)
            server.logger.info(
                "request_completed",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
            response.headers["x-request-id"] = request_id
            return response

        @app.get("/")
        async def server_info() -> dict[str, Any]:
            return {
                "name": server.name,
                "version": server.version,
                "vendor": server.vendor,
                "description": server.description,
                "capabilities": {"tools": True},
                "status": "healthy",
            }

        @app.post("/tools/list")
        async def tools_list() -> dict[str, Any]:
            return {
                "tools": [t.model_dump() for t in server._tools.values()],
            }

        @app.post("/tools/call")
        async def tools_call(req: ToolCallRequest) -> dict[str, Any]:
            if req.name not in server._tools:
                return canonical_error(
                    f"Unknown tool: {req.name}",
                    error_code="TOOL_NOT_FOUND",
                    vendor_status_code=404,
                    retryable=False,
                )
            tool_def = server._tools[req.name]
            if tool_def.status == "pending_vendor_approval":
                return canonical_error(
                    f"Tool '{req.name}' is pending vendor API approval.",
                    error_code="PENDING_VENDOR_APPROVAL",
                    retryable=False,
                )
            handler = server._handlers[req.name]
            start = time.monotonic()
            try:
                result = await handler(req.arguments)
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                server.logger.info(
                    "tool_call_success",
                    tool_name=req.name,
                    duration_ms=duration_ms,
                )
                return result
            except Exception as exc:
                duration_ms = round((time.monotonic() - start) * 1000, 2)
                server.logger.error(
                    "tool_call_error",
                    tool_name=req.name,
                    duration_ms=duration_ms,
                    error=str(exc),
                )
                return canonical_error(
                    str(exc),
                    error_code="TOOL_EXECUTION_ERROR",
                    retryable=False,
                )

        return app
