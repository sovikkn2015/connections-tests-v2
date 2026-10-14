"""Shared async MCP client used by all 13 skills.

Follows MCP protocol primitives over HTTP transport:

  - `GET  /`             health/handshake, returns server name + version
  - `POST /tools/list`   returns the tool catalog exposed by the server
  - `POST /tools/call`   invokes a named tool with arguments

Two modes, selected at construction time:

  - `mock=True` -> MockMCPRouter returns canned deterministic shapes so every
    skill's unit tests run without network. Default for tests.
  - `mock=False` -> real `httpx.AsyncClient` with retry (3 attempts,
    exponential backoff) + per-call timeout + structured error wrapping.

This module is the ONLY place MCP transport lives. Skills never call httpx
directly. That keeps retry/timeout/error-shape invariants centrally owned
and makes it trivial to swap transports later (stdio, SSE, WebSocket) without
touching business logic.
"""

from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional

try:
    import httpx  # type: ignore
except ImportError:  # pragma: no cover - degrade gracefully in offline tests
    httpx = None  # type: ignore


class MCPError(Exception):
    """Structured MCP error. Skills wrap this or surface it upstream.

    Attributes:
        server: logical MCP server name (e.g. "salesforce-crm").
        tool:   tool name that failed (or "" for protocol-level errors).
        retryable: whether a retry could plausibly succeed (timeouts yes,
                   authz no). Skills treat non-retryable as hard-stop.
        status: optional HTTP status if the failure was transport-level.
    """

    def __init__(
        self,
        *,
        server: str,
        tool: str,
        reason: str,
        retryable: bool = False,
        status: Optional[int] = None,
    ) -> None:
        self.server = server
        self.tool = tool
        self.retryable = retryable
        self.status = status
        super().__init__(
            f"mcp_error server={server!r} tool={tool!r} retryable={retryable} "
            f"status={status} reason={reason}"
        )


# A MockHandler is an async callable that takes tool arguments and returns
# a result dict (same shape the real server would return).
MockHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


@dataclass
class MockMCPRouter:
    """In-memory MCP router used by tests and by MULESOFT_MODE=mock flows.

    Handlers are registered per (server, tool) key. An unregistered call
    raises `MCPError(retryable=False)` so tests catch missing stubs loudly.
    """

    handlers: Dict[str, MockHandler] = field(default_factory=dict)
    call_log: List[Dict[str, Any]] = field(default_factory=list)

    def register(self, server: str, tool: str, handler: MockHandler) -> None:
        """Install a mock handler. Later `register` calls overwrite."""
        self.handlers[f"{server}::{tool}"] = handler

    async def call(
        self, *, server: str, tool: str, arguments: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Invoke a registered mock handler. Records the call for assertions."""
        self.call_log.append({"server": server, "tool": tool, "arguments": arguments})
        key = f"{server}::{tool}"
        handler = self.handlers.get(key)
        if handler is None:
            raise MCPError(
                server=server,
                tool=tool,
                reason=f"no mock handler registered for {key!r}",
                retryable=False,
            )
        return await handler(arguments)


class MCPClient:
    """Async MCP client with retry + timeout + structured errors.

    Usage:
        client = MCPClient(mock=True)
        client.mock_router.register("salesforce-crm", "read_brief", handler)
        result = await client.call("salesforce-crm", "read_brief", {"id": "a0X..."})
    """

    DEFAULT_TIMEOUT_S = 10.0
    DEFAULT_RETRIES = 3
    BACKOFF_BASE_S = 0.25

    def __init__(
        self,
        *,
        mock: bool = True,
        server_urls: Optional[Dict[str, str]] = None,
        timeout_s: float = DEFAULT_TIMEOUT_S,
        max_retries: int = DEFAULT_RETRIES,
    ) -> None:
        self.mock = mock
        self._server_urls = server_urls or {}
        self._timeout_s = timeout_s
        self._max_retries = max_retries
        self.mock_router: MockMCPRouter = MockMCPRouter()

        if not mock:
            if httpx is None:
                raise RuntimeError(
                    "httpx is required for non-mock MCPClient; install httpx"
                )
            api_key = os.getenv("MCP_API_KEY")
            if not api_key:
                raise RuntimeError(
                    "MCP_API_KEY env var required for real MCP transport "
                    "(mock=False); seed via AWS Secrets Manager"
                )
            self._api_key = api_key
            self._http: Optional["httpx.AsyncClient"] = None

    async def __aenter__(self) -> "MCPClient":
        if not self.mock and httpx is not None:
            self._http = httpx.AsyncClient(timeout=self._timeout_s)
        return self

    async def __aexit__(self, *_exc: Any) -> None:
        if not self.mock and self._http is not None:
            await self._http.aclose()
            self._http = None

    async def list_tools(self, server: str) -> List[Dict[str, Any]]:
        """POST /tools/list on a named server. Returns the tool catalog."""
        if self.mock:
            return [
                {"name": k.split("::", 1)[1]}
                for k in self.mock_router.handlers
                if k.startswith(f"{server}::")
            ]
        return await self._post(server=server, path="/tools/list", body={})

    async def call(
        self, server: str, tool: str, arguments: Dict[str, Any],
        *,
        principal_id: str = "dev-principal",
        agent_id: str = "dev-agent",
        persona: str = "fsi_research",
        session_id: str = "dev-session",
    ) -> Dict[str, Any]:
        """POST /tools/call. Retries on retryable failures with jittered backoff.

        Raises:
            MCPError: structured failure; `retryable` indicates whether the
                caller could try again under different conditions.
        """
        if self.mock:
            return await self.mock_router.call(
                server=server, tool=tool, arguments=arguments
            )

        last_exc: Optional[MCPError] = None
        for attempt in range(self._max_retries):
            try:
                return await self._post(
                    server=server,
                    path="/tools/call",
                    body={"name": tool, "arguments": arguments},
                    ctx_headers={
                        "X-Principal-Id": principal_id,
                        "X-Agent-Id": agent_id,
                        "X-Persona": persona,
                        "X-Session-Id": session_id,
                    },
                )
            except MCPError as exc:
                last_exc = exc
                if not exc.retryable:
                    raise
                await asyncio.sleep(
                    self.BACKOFF_BASE_S * (2**attempt) + random.random() * 0.1
                )
        assert last_exc is not None
        raise last_exc

    async def _post(
        self, *, server: str, path: str, body: Dict[str, Any],
        ctx_headers: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Transport-level POST. Converts transport errors to MCPError."""
        if self._http is None:
            # Lazy-init the http client when not used with `async with`.
            # This is the production/demo path — skills don't wrap calls in
            # a context manager; they just invoke `.call()`.
            if httpx is None:
                raise MCPError(
                    server=server,
                    tool=body.get("name", ""),
                    reason="httpx not installed",
                    retryable=False,
                )
            self._http = httpx.AsyncClient(timeout=self._timeout_s)
        base = self._server_urls.get(server)
        if base is None:
            raise MCPError(
                server=server,
                tool="",
                reason=f"no base URL configured for server {server!r}",
                retryable=False,
            )
        url = f"{base.rstrip('/')}{path}"
        headers = {
            "X-MCP-API-Key": self._api_key,
            "Content-Type": "application/json",
        }
        if ctx_headers:
            headers.update(ctx_headers)
        try:
            resp = await self._http.post(url, headers=headers, json=body)
        except httpx.TimeoutException as exc:  # type: ignore[attr-defined]
            raise MCPError(
                server=server,
                tool=body.get("name", ""),
                reason=f"timeout: {exc}",
                retryable=True,
            )
        except httpx.HTTPError as exc:  # type: ignore[attr-defined]
            raise MCPError(
                server=server,
                tool=body.get("name", ""),
                reason=f"transport_error: {exc}",
                retryable=True,
            )
        if resp.status_code >= 500:
            raise MCPError(
                server=server,
                tool=body.get("name", ""),
                reason=f"server_error body={resp.text[:200]}",
                retryable=True,
                status=resp.status_code,
            )
        if resp.status_code >= 400:
            raise MCPError(
                server=server,
                tool=body.get("name", ""),
                reason=f"client_error body={resp.text[:200]}",
                retryable=False,
                status=resp.status_code,
            )
        try:
            return resp.json()
        except ValueError as exc:
            raise MCPError(
                server=server,
                tool=body.get("name", ""),
                reason=f"non_json_response: {exc}",
                retryable=False,
            )


_SHARED: Optional[MCPClient] = None


def get_shared_mock_client() -> MCPClient:
    """Return a module-level MCP client for skills.

    When ``MCP_API_URL`` is set (production / demo), this returns a REAL
    live MCP client pointing at the deployed API Gateway, not a mock.
    Server URLs are derived as ``{MCP_API_URL}/mcp/{server_name}``.

    The function is kept named ``get_shared_mock_client`` for backwards
    compatibility with the skills that already call it; the behavior is
    live-first, mock-fallback.

    Tests can still override with ``reset_shared_mock_client()`` + inject.
    """
    global _SHARED
    if _SHARED is not None:
        return _SHARED

    api_url = os.getenv("MCP_API_URL", "").rstrip("/")
    if api_url:
        # Build URL map for the 5 MCP servers the skills can call.
        servers = [
            "market-data",
            "sec-edgar",
            "news-search",
            "salesforce-crm",
            "mulesoft-actions",
        ]
        server_urls = {s: f"{api_url}/mcp/{s}" for s in servers}
        try:
            _SHARED = MCPClient(mock=False, server_urls=server_urls, timeout_s=30.0)
            return _SHARED
        except RuntimeError:
            # Missing MCP_API_KEY — fall through to mock so code still loads.
            pass

    _SHARED = MCPClient(mock=True)
    return _SHARED


def reset_shared_mock_client() -> None:
    """Wipe the module-level mock client (test teardown helper)."""
    global _SHARED
    _SHARED = None
