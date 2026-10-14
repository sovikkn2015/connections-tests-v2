"""
M6 Resilience Patterns — Circuit Breaker, Retry, Rate Limiter, Bulkhead.

Rule 4: Circuit breaker per MCP server (5 failures → open 30s)
Rule 5: Retry with exponential backoff (3 retries, 1s/2s/4s)
Rule 7: Rate limiting per user per tool (sliding window, Redis or in-memory)
Rule 8: Bulkhead isolation per MCP server category (async semaphores)

All state stored in Redis for cross-instance consistency in production.
In-memory fallback for dev/test without Redis.
"""

from __future__ import annotations

import abc
import asyncio
import logging
import time
from typing import Any, Callable, Optional

import httpx
from tenacity import (
    RetryError,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .models import CircuitState, ServerConfig

logger = logging.getLogger("m6.resilience")


# ── Abstract State Store for Circuit Breaker ─────────────────────


class CircuitBreakerStateStore(abc.ABC):
    """Abstract interface for circuit breaker state persistence."""

    @abc.abstractmethod
    async def get_state(self, server_url: str) -> tuple[CircuitState, int, float]:
        """Return (state, failure_count, last_failure_time) for a server."""

    @abc.abstractmethod
    async def set_state(
        self,
        server_url: str,
        state: CircuitState,
        failure_count: int,
        last_failure_time: float,
    ) -> None:
        """Persist circuit breaker state for a server."""


class InMemoryCircuitBreakerStateStore(CircuitBreakerStateStore):
    """In-memory state store — default for dev/test (single instance)."""

    def __init__(self) -> None:
        self._data: dict[str, tuple[CircuitState, int, float]] = {}

    async def get_state(self, server_url: str) -> tuple[CircuitState, int, float]:
        return self._data.get(server_url, (CircuitState.closed, 0, 0.0))

    async def set_state(
        self,
        server_url: str,
        state: CircuitState,
        failure_count: int,
        last_failure_time: float,
    ) -> None:
        self._data[server_url] = (state, failure_count, last_failure_time)


class RedisCircuitBreakerStateStore(CircuitBreakerStateStore):
    """
    Redis-backed circuit breaker state for cross-instance consistency.

    Stores per-server state as a Redis hash:
      m6:cb:{server_url} → {state, failure_count, last_failure_time}

    Falls back to in-memory if Redis is unavailable.
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._fallback = InMemoryCircuitBreakerStateStore()
        self._using_fallback = False

    def _key(self, server_url: str) -> str:
        return f"m6:cb:{server_url}"

    async def get_state(self, server_url: str) -> tuple[CircuitState, int, float]:
        try:
            data = await self._redis.hgetall(self._key(server_url))
            if not data:
                return CircuitState.closed, 0, 0.0
            state_str = data.get(b"state", data.get("state", b"closed"))
            if isinstance(state_str, bytes):
                state_str = state_str.decode()
            fc = data.get(b"failure_count", data.get("failure_count", b"0"))
            if isinstance(fc, bytes):
                fc = fc.decode()
            lft = data.get(b"last_failure_time", data.get("last_failure_time", b"0.0"))
            if isinstance(lft, bytes):
                lft = lft.decode()
            return CircuitState(state_str), int(fc), float(lft)
        except Exception as exc:
            if not self._using_fallback:
                logger.warning(
                    "Redis unavailable for circuit breaker state, falling back to in-memory: %s",
                    exc,
                )
                self._using_fallback = True
            return await self._fallback.get_state(server_url)

    async def set_state(
        self,
        server_url: str,
        state: CircuitState,
        failure_count: int,
        last_failure_time: float,
    ) -> None:
        try:
            await self._redis.hset(
                self._key(server_url),
                mapping={
                    "state": state.value,
                    "failure_count": str(failure_count),
                    "last_failure_time": str(last_failure_time),
                },
            )
            self._using_fallback = False
        except Exception as exc:
            if not self._using_fallback:
                logger.warning(
                    "Redis unavailable for circuit breaker state, falling back to in-memory: %s",
                    exc,
                )
                self._using_fallback = True
            await self._fallback.set_state(server_url, state, failure_count, last_failure_time)


# ── Circuit Breaker (Rule 4) ────────────────────────────────────


class CircuitBreaker:
    """
    Per-MCP-server circuit breaker.

    States: closed → open → half_open → closed (or back to open).
    - closed: requests flow normally, failures counted.
    - open: all requests rejected immediately for recovery_timeout seconds.
    - half_open: one probe request allowed; success → closed, failure → open.

    Accepts an optional state_store for Redis-backed persistence.
    Default: in-memory (current behavior preserved).
    Thread-safe via asyncio.Lock.
    """

    def __init__(
        self,
        server_url: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        state_store: Optional[CircuitBreakerStateStore] = None,
    ) -> None:
        self.server_url = server_url
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._state_store = state_store
        # In-memory fields used when no external state store is provided
        self._state = CircuitState.closed
        self._failure_count = 0
        self._last_failure_time: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def _load_state(self) -> None:
        """Load state from external store if configured."""
        if self._state_store is not None:
            self._state, self._failure_count, self._last_failure_time = (
                await self._state_store.get_state(self.server_url)
            )

    async def _save_state(self) -> None:
        """Persist state to external store if configured."""
        if self._state_store is not None:
            await self._state_store.set_state(
                self.server_url,
                self._state,
                self._failure_count,
                self._last_failure_time,
            )

    async def can_execute(self) -> bool:
        """Check if a request can proceed through this circuit breaker."""
        async with self._lock:
            await self._load_state()
            if self._state == CircuitState.closed:
                return True
            if self._state == CircuitState.open:
                elapsed = time.monotonic() - self._last_failure_time
                if elapsed >= self.recovery_timeout:
                    self._state = CircuitState.half_open
                    await self._save_state()
                    logger.info(
                        "Circuit breaker half-open for %s", self.server_url
                    )
                    return True
                return False
            # half_open: allow one probe
            return True

    async def record_success(self) -> None:
        """Record a successful call — reset failure count."""
        async with self._lock:
            await self._load_state()
            self._failure_count = 0
            if self._state == CircuitState.half_open:
                self._state = CircuitState.closed
                logger.info(
                    "Circuit breaker closed for %s", self.server_url
                )
            await self._save_state()

    async def record_failure(self) -> None:
        """Record a failed call — increment count, possibly open circuit."""
        async with self._lock:
            await self._load_state()
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._state == CircuitState.half_open:
                self._state = CircuitState.open
                logger.warning(
                    "Circuit breaker re-opened for %s (half-open probe failed)",
                    self.server_url,
                )
            elif self._failure_count >= self.failure_threshold:
                self._state = CircuitState.open
                logger.warning(
                    "Circuit breaker opened for %s (%d consecutive failures)",
                    self.server_url,
                    self._failure_count,
                )
            await self._save_state()


class CircuitBreakerRegistry:
    """
    Registry of per-server circuit breakers.
    Creates circuit breakers on demand with server-specific config.
    Accepts an optional state_store for Redis-backed persistence.
    """

    def __init__(self, state_store: Optional[CircuitBreakerStateStore] = None) -> None:
        self._breakers: dict[str, CircuitBreaker] = {}
        self._state_store = state_store
        self._lock = asyncio.Lock()

    async def get(self, server_url: str, config: Optional[ServerConfig] = None) -> CircuitBreaker:
        """Get or create a circuit breaker for a server."""
        async with self._lock:
            if server_url not in self._breakers:
                threshold = config.circuit_breaker_threshold if config else 5
                recovery = config.circuit_breaker_recovery_seconds if config else 30.0
                self._breakers[server_url] = CircuitBreaker(
                    server_url=server_url,
                    failure_threshold=threshold,
                    recovery_timeout=recovery,
                    state_store=self._state_store,
                )
            return self._breakers[server_url]

    def get_all_states(self) -> dict[str, str]:
        """Get all circuit breaker states (for health check)."""
        return {url: cb.state.value for url, cb in self._breakers.items()}


# ── Retry with Exponential Backoff (Rule 5) ──────────────────────


class TransientError(Exception):
    """Raised for transient failures that should be retried (5xx, timeouts)."""
    pass


class NonTransientError(Exception):
    """Raised for non-transient failures that must NOT be retried (4xx, trust)."""
    pass


def is_transient_http_error(status_code: int) -> bool:
    """Check if an HTTP status code indicates a transient error."""
    return status_code >= 500 or status_code == 429


async def retry_with_backoff(
    func: Callable,
    *args: Any,
    max_retries: int = 3,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function with tenacity retry logic.

    Retries on TransientError only (5xx, timeouts, connection errors).
    Never retries on 4xx or trust failures (NonTransientError).

    Backoff: 1s → 2s → 4s (exponential, multiplier=1, min=1, max=4).
    """

    @retry(
        retry=retry_if_exception_type(TransientError),
        stop=stop_after_attempt(max_retries + 1),  # +1 because first attempt counts
        wait=wait_exponential(multiplier=1, min=1, max=4),
        reraise=True,
    )
    async def _execute() -> Any:
        return await func(*args, **kwargs)

    try:
        return await _execute()
    except RetryError as e:
        raise e.last_attempt.result() if e.last_attempt.failed else e


# ── Rate Limiter (Rule 7) ────────────────────────────────────────


class RateLimiter:
    """
    Per-user-per-tool sliding window rate limiter.

    In-memory implementation for dev/test.
    Production uses Redis (same interface, swap implementation).
    """

    def __init__(self) -> None:
        # Key: "user_id:tool_name" → list of request timestamps
        self._windows: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(
        self,
        user_id: str,
        tool_name: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> tuple[bool, Optional[int]]:
        """
        Check if a request is within rate limits.

        Returns:
            (allowed, retry_after_seconds)
            If allowed=False, retry_after is seconds until window slides.
        """
        key = f"{user_id}:{tool_name}"
        now = time.monotonic()
        window_start = now - window_seconds

        async with self._lock:
            if key not in self._windows:
                self._windows[key] = []

            # Slide window: remove expired entries
            self._windows[key] = [
                ts for ts in self._windows[key] if ts > window_start
            ]

            if len(self._windows[key]) >= max_requests:
                # Calculate retry-after from oldest entry in window
                oldest = self._windows[key][0]
                retry_after = int(oldest - window_start) + 1
                return False, max(retry_after, 1)

            self._windows[key].append(now)
            return True, None


class RedisRateLimiter:
    """
    Redis-backed sliding window rate limiter using sorted sets.

    Each user:tool combination is a sorted set where:
      - Members are unique request IDs (timestamp-based)
      - Scores are request timestamps

    Uses ZRANGEBYSCORE to count requests in the window, ZADD to record.
    Falls back to in-memory RateLimiter if Redis is unavailable.
    """

    def __init__(self, redis_client: Any) -> None:
        self._redis = redis_client
        self._fallback = RateLimiter()
        self._using_fallback = False

    def _key(self, user_id: str, tool_name: str) -> str:
        return f"m6:rl:{user_id}:{tool_name}"

    async def check_rate_limit(
        self,
        user_id: str,
        tool_name: str,
        max_requests: int = 100,
        window_seconds: int = 60,
    ) -> tuple[bool, Optional[int]]:
        """
        Check rate limit using Redis sorted set sliding window.

        Falls back to in-memory if Redis is unavailable.
        """
        try:
            return await self._check_redis(
                user_id, tool_name, max_requests, window_seconds,
            )
        except Exception as exc:
            if not self._using_fallback:
                logger.warning(
                    "Redis unavailable for rate limiting, falling back to in-memory: %s",
                    exc,
                )
                self._using_fallback = True
            return await self._fallback.check_rate_limit(
                user_id, tool_name, max_requests, window_seconds,
            )

    async def _check_redis(
        self,
        user_id: str,
        tool_name: str,
        max_requests: int,
        window_seconds: int,
    ) -> tuple[bool, Optional[int]]:
        key = self._key(user_id, tool_name)
        now = time.time()
        window_start = now - window_seconds

        pipe = self._redis.pipeline()
        # Remove expired entries
        pipe.zremrangebyscore(key, 0, window_start)
        # Count current entries in window
        pipe.zcard(key)
        results = await pipe.execute()
        current_count = results[1]

        if current_count >= max_requests:
            # Get oldest entry to calculate retry-after
            oldest = await self._redis.zrange(key, 0, 0, withscores=True)
            if oldest:
                oldest_time = oldest[0][1]
                retry_after = int((oldest_time + window_seconds) - now) + 1
                return False, max(retry_after, 1)
            return False, 1

        # Record this request — use timestamp as score, unique member
        member = f"{now}:{id(object())}"
        pipe2 = self._redis.pipeline()
        pipe2.zadd(key, {member: now})
        pipe2.expire(key, window_seconds + 1)
        await pipe2.execute()

        self._using_fallback = False
        return True, None


# ── Bulkhead Isolation (Rule 8) ──────────────────────────────────


class BulkheadRegistry:
    """
    Per-server-category bulkhead using async semaphores.
    A slow/failing vendor cannot starve other vendors of resources.
    """

    def __init__(self) -> None:
        self._semaphores: dict[str, asyncio.Semaphore] = {}
        self._lock = asyncio.Lock()

    async def acquire(self, category: str, max_concurrent: int = 10) -> asyncio.Semaphore:
        """Get the semaphore for a server category, creating if needed."""
        async with self._lock:
            if category not in self._semaphores:
                self._semaphores[category] = asyncio.Semaphore(max_concurrent)
        return self._semaphores[category]


class CircuitOpenError(Exception):
    """Raised when circuit breaker is open — request rejected immediately."""
    pass


class RateLimitExceededError(Exception):
    """Raised when rate limit is exceeded."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limit exceeded. Retry after {retry_after}s")


class BulkheadFullError(Exception):
    """Raised when bulkhead semaphore cannot be acquired."""
    pass


# ── Redis Client Factory ─────────────────────────────────────────


async def create_redis_client(redis_url: str) -> Optional[Any]:
    """
    Create an async Redis client. Returns None if connection fails.

    Uses redis.asyncio for non-blocking operations.
    Caller should handle None gracefully (fall back to in-memory).
    """
    try:
        import redis.asyncio as aioredis
        client = aioredis.from_url(redis_url, decode_responses=False)
        await client.ping()
        logger.info("Redis connected at %s", redis_url)
        return client
    except Exception as exc:
        logger.warning(
            "Failed to connect to Redis at %s, using in-memory fallback: %s",
            redis_url,
            exc,
        )
        return None
