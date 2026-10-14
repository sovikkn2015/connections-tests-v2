"""
M6 MCP Proxy — Forwards calls to downstream MCP servers.

Uses httpx async with configurable timeouts (Rule 6).
Circuit breaker wraps each call (Rule 4).
Retry with exponential backoff on transient failures (Rule 5).
Bulkhead isolation per server category (Rule 8).

All calls go through M6. No direct vendor API calls allowed (Rule 1).
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

import httpx
from opentelemetry import trace

from .models import GatewayConfig, ProvenanceEntry, PipelineStage, ServerConfig
from .resilience import (
    BulkheadFullError,
    BulkheadRegistry,
    CircuitBreakerRegistry,
    CircuitOpenError,
    NonTransientError,
    RateLimitExceededError,
    RateLimiter,
    RedisCircuitBreakerStateStore,
    RedisRateLimiter,
    TransientError,
    create_redis_client,
    is_transient_http_error,
    retry_with_backoff,
)

logger = logging.getLogger("m6.mcp_proxy")

_tracer = trace.get_tracer("m6.mcp-gateway")


class MCPProxy:
    """
    Async MCP proxy that forwards tool calls to downstream MCP servers.

    Wraps each call with:
      - Circuit breaker (per server)
      - Retry with exponential backoff (transient errors only)
      - Bulkhead isolation (per server category)
      - Rate limiting (per user per tool)
      - Configurable timeout (per server, default 30s)
    """

    def __init__(self, config: GatewayConfig, redis_client: Any = None) -> None:
        self.config = config
        self._redis_client = redis_client

        # Use Redis-backed implementations if a Redis client is provided
        if redis_client is not None:
            cb_store = RedisCircuitBreakerStateStore(redis_client)
            self.circuit_breakers = CircuitBreakerRegistry(state_store=cb_store)
            self.rate_limiter = RedisRateLimiter(redis_client)
            logger.info("MCPProxy initialized with Redis-backed resilience")
        else:
            self.circuit_breakers = CircuitBreakerRegistry()
            self.rate_limiter = RateLimiter()
            logger.info("MCPProxy initialized with in-memory resilience")

        self.bulkheads = BulkheadRegistry()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazy-init httpx async client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient()
        return self._client

    async def close(self) -> None:
        """Close the httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def forward_mcp_call(
        self,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        user_id: str = "system",
    ) -> dict[str, Any]:
        """
        Forward an MCP tool call to a downstream server.

        Full resilience pipeline:
          1. Rate limit check
          2. Circuit breaker check
          3. Bulkhead acquire
          4. HTTP call with retry + timeout
          5. Record success/failure to circuit breaker

        Args:
            server_url: Target MCP server URL.
            tool_name: MCP tool to invoke.
            arguments: Tool arguments.
            user_id: User ID for rate limiting.

        Returns:
            Raw response dict from the MCP server.

        Raises:
            RateLimitExceededError: Rate limit exceeded (429).
            CircuitOpenError: Circuit breaker is open.
            BulkheadFullError: Bulkhead semaphore full.
            TransientError: Transient failure after all retries exhausted.
            NonTransientError: Non-transient failure (4xx, trust).
        """
        server_config = self.config.get_server_config(server_url)

        with _tracer.start_as_current_span(
            "forward_mcp_call",
            attributes={"m6.server_url": server_url, "m6.tool_name": tool_name},
        ) as span:
            t0 = time.monotonic()

            # 1. Rate limit check (Rule 7)
            allowed, retry_after = await self.rate_limiter.check_rate_limit(
                user_id=user_id,
                tool_name=tool_name,
                max_requests=server_config.rate_limit_per_user,
                window_seconds=server_config.rate_limit_window_seconds,
            )
            if not allowed:
                raise RateLimitExceededError(retry_after=retry_after or 1)

            # 2. Circuit breaker check (Rule 4)
            cb = await self.circuit_breakers.get(server_url, server_config)
            if not await cb.can_execute():
                raise CircuitOpenError(
                    f"Circuit breaker open for {server_url}"
                )

            # 3. Bulkhead acquire (Rule 8)
            semaphore = await self.bulkheads.acquire(
                category=server_config.category,
                max_concurrent=server_config.bulkhead_max_concurrent,
            )

            async with semaphore:
                # 4. HTTP call with retry (Rule 5) + timeout (Rule 6)
                try:
                    result = await retry_with_backoff(
                        self._do_mcp_call,
                        server_url,
                        tool_name,
                        arguments,
                        server_config,
                        max_retries=server_config.max_retries,
                    )
                    # 5. Record success
                    await cb.record_success()
                    span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    return result
                except (TransientError, NonTransientError):
                    await cb.record_failure()
                    span.set_attribute("m6.duration_ms", int((time.monotonic() - t0) * 1000))
                    raise

    async def _do_mcp_call(
        self,
        server_url: str,
        tool_name: str,
        arguments: dict[str, Any],
        config: ServerConfig,
    ) -> dict[str, Any]:
        """
        Execute a single MCP call via httpx.

        POST {server_url}/tools/call with MCP protocol payload.
        Raises TransientError for 5xx/timeout, NonTransientError for 4xx.
        """
        client = await self._get_client()
        url = f"{server_url.rstrip('/')}/tools/call"
        payload = {
            "name": tool_name,
            "arguments": arguments,
        }

        try:
            response = await client.post(
                url,
                json=payload,
                timeout=config.timeout_seconds,
            )
        except httpx.TimeoutException as e:
            logger.warning("Timeout calling %s: %s", url, str(e))
            raise TransientError(f"Timeout calling {server_url}") from e
        except httpx.ConnectError as e:
            logger.warning("Connection error calling %s: %s", url, str(e))
            raise TransientError(f"Connection error: {server_url}") from e
        except httpx.HTTPError as e:
            logger.warning("HTTP error calling %s: %s", url, str(e))
            raise TransientError(f"HTTP error: {server_url}") from e

        if is_transient_http_error(response.status_code):
            raise TransientError(
                f"Server error {response.status_code} from {server_url}"
            )

        if 400 <= response.status_code < 500:
            raise NonTransientError(
                f"Client error {response.status_code} from {server_url}"
            )

        return response.json()

    async def list_tools(
        self,
        server_url: str,
        timeout: Optional[float] = None,
    ) -> list[dict[str, Any]]:
        """
        List available tools from a downstream MCP server.

        POST {server_url}/tools/list per MCP protocol.
        """
        client = await self._get_client()
        url = f"{server_url.rstrip('/')}/tools/list"
        t = timeout or self.config.default_timeout_seconds

        try:
            response = await client.post(url, json={}, timeout=t)
            response.raise_for_status()
            data = response.json()
            return data.get("tools", [])
        except Exception as e:
            logger.error("Failed to list tools from %s: %s", server_url, str(e))
            raise TransientError(f"Failed to list tools from {server_url}") from e

    async def check_server_health(self, server_url: str) -> bool:
        """Check if a downstream MCP server is reachable (GET /)."""
        client = await self._get_client()
        try:
            response = await client.get(
                f"{server_url.rstrip('/')}/",
                timeout=5.0,
            )
            return response.status_code == 200
        except Exception:
            return False
