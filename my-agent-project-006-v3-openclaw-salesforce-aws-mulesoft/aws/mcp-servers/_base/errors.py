"""Structured MCP errors.

MCP error codes follow JSON-RPC 2.0 conventions — negative integers for
protocol errors, 400-series for client mistakes, 500-series for server/
upstream failures. Every handler that raises one of these ends up in a
structured ToolError on the wire, never a raw Python traceback.
"""

from __future__ import annotations


class McpError(Exception):
    """Base class — always carries a code + message."""

    code: int = -32000
    http_status: int = 500

    def __init__(self, message: str, *, code: int | None = None, details: dict | None = None) -> None:
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict:
        payload = {"code": self.code, "message": self.message}
        if self.details:
            payload["details"] = self.details
        return payload


class McpAuthError(McpError):
    """401 — bad or missing X-MCP-API-Key."""

    code = -32001
    http_status = 401


class McpValidationError(McpError):
    """400 — input parameter validation failed."""

    code = -32602  # JSON-RPC: "invalid params"
    http_status = 400


class McpToolNotFoundError(McpError):
    """404 — tool name not registered on this server."""

    code = -32601  # JSON-RPC: "method not found"
    http_status = 404


class McpUpstreamError(McpError):
    """502 — a downstream vendor / SF / MuleSoft call failed."""

    code = -32010
    http_status = 502


class McpRateLimitError(McpError):
    """429 — vendor rate limit hit."""

    code = -32011
    http_status = 429
