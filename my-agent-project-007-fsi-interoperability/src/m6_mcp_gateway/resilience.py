"""
M6 MCP Gateway — CircuitBreaker + RateLimiter.

Phase 1 in-memory implementations with injectable monotonic clocks.
Phase 1 is single-threaded / NOT thread-safe. Phase 2 will move state
to Redis; the public surface is stable across the migration.

See `.kiro/specs/m6-mcp-gateway.md` §R4 and §R5.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Optional

# GatewayError is imported lazily inside methods to avoid a cycle.


# =============================================================================
# Internal state dataclasses.
# =============================================================================


@dataclass
class _BreakerState:
    state: str                  # "CLOSED" | "OPEN" | "HALF_OPEN"
    consecutive_failures: int
    opened_at: Optional[float]


@dataclass
class _BucketState:
    tokens: float
    last: float


# =============================================================================
# CircuitBreaker (spec R4).
# =============================================================================


class CircuitBreaker:
    """Per-key circuit breaker (CLOSED/OPEN/HALF_OPEN).

    Keyed by `mcp_server`. Rationale (spec R4.2): breaker protects the
    downstream SERVER from cascading calls; one failing server trips
    one breaker. All of that server's tools share the bulkhead.
    Matches Hystrix / Resilience4j.

    Phase 1 is NOT thread-safe. Do not share a single instance across
    threads. Phase 2 replaces state with Redis.
    """

    def __init__(
        self,
        *,
        failure_threshold: int = 5,
        recovery_seconds: float = 30.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(failure_threshold, int) or failure_threshold < 1:
            raise ValueError("failure_threshold must be >= 1")
        if recovery_seconds <= 0.0:
            raise ValueError("recovery_seconds must be > 0")
        self._threshold = failure_threshold
        self._recovery = recovery_seconds
        self._clock = clock
        self._states: dict[str, _BreakerState] = {}

    def _get(self, key: str) -> _BreakerState:
        st = self._states.get(key)
        if st is None:
            st = _BreakerState(
                state="CLOSED", consecutive_failures=0, opened_at=None
            )
            self._states[key] = st
        return st

    def check(self, key: str) -> None:
        """Raise GatewayError('circuit_open') if `key` is OPEN.

        OPEN -> HALF_OPEN advance when cooldown has elapsed.
        """
        from m6_mcp_gateway.gateway import GatewayError

        st = self._get(key)
        if st.state == "OPEN":
            assert st.opened_at is not None
            elapsed = self._clock() - st.opened_at
            if elapsed >= self._recovery:
                st.state = "HALF_OPEN"
                return
            raise GatewayError("circuit_open")
        # CLOSED and HALF_OPEN both allow a call through.

    def record_success(self, key: str) -> None:
        st = self._get(key)
        st.state = "CLOSED"
        st.consecutive_failures = 0
        st.opened_at = None

    def record_failure(self, key: str) -> None:
        st = self._get(key)
        if st.state == "HALF_OPEN":
            st.state = "OPEN"
            st.consecutive_failures = self._threshold
            st.opened_at = self._clock()
            return
        st.consecutive_failures += 1
        if st.consecutive_failures >= self._threshold:
            st.state = "OPEN"
            st.opened_at = self._clock()

    def state(self, key: str) -> str:
        return self._get(key).state

    def keys(self) -> list[str]:
        """Snapshot of known keys. Debug / health only."""
        return list(self._states.keys())


# =============================================================================
# RateLimiter (spec R5).
# =============================================================================


class RateLimiter:
    """Token-bucket rate limiter, one bucket per key.

    Buckets start full (tokens = capacity). `refill_per_second` may
    be 0 (hard cap). Phase 1 is NOT thread-safe. Phase 2 moves state
    to Redis.
    """

    def __init__(
        self,
        *,
        capacity: int,
        refill_per_second: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(capacity, int) or capacity < 1:
            raise ValueError("capacity must be an integer >= 1")
        if refill_per_second < 0.0:
            raise ValueError("refill_per_second must be >= 0")
        self._capacity = capacity
        self._refill = refill_per_second
        self._clock = clock
        self._buckets: dict[str, _BucketState] = {}

    def _get(self, key: str) -> _BucketState:
        b = self._buckets.get(key)
        if b is None:
            b = _BucketState(
                tokens=self._capacity * 1.0, last=self._clock()
            )
            self._buckets[key] = b
        return b

    def check(self, key: str) -> None:
        """Consume one token. Raise GatewayError('rate_limited') if empty."""
        from m6_mcp_gateway.gateway import GatewayError

        b = self._get(key)
        now = self._clock()
        elapsed = max(0.0, now - b.last)
        refilled = b.tokens + elapsed * self._refill
        if refilled > self._capacity:
            refilled = self._capacity * 1.0
        b.tokens = refilled
        b.last = now

        if b.tokens < 1.0:
            raise GatewayError("rate_limited")
        b.tokens -= 1.0

    def tokens(self, key: str) -> float:
        return self._get(key).tokens


__all__ = ["CircuitBreaker", "RateLimiter"]
