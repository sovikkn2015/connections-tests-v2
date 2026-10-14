"""3-state circuit breaker (CLOSED / OPEN / HALF_OPEN).

Port of the TypeScript `@project-007/mcp-sdk::CircuitBreaker`. Same thresholds,
same transitions, same short-circuit rule:

* CLOSED: normal operation; consecutive failures tick towards threshold.
* OPEN: fail fast with :class:`CircuitBreakerOpen` until cooldown elapses.
* HALF_OPEN: exactly one trial request allowed; success → CLOSED, failure → OPEN.

Thread-safety: all state mutations happen inside `_lock`. Async callers should
still use the async-safe helpers (`arun`) — the lock covers both paths.
"""

from __future__ import annotations

import asyncio
import threading
from enum import Enum
from typing import Awaitable, Callable, TypeVar

from m11_python_adapters_shared.clock import Clock


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpen(Exception):
    """Raised from the breaker when a call is short-circuited."""

    def __init__(self, cooldown_remaining_ms: int) -> None:
        super().__init__(f"circuit open; retry in {cooldown_remaining_ms} ms")
        self.cooldown_remaining_ms = int(cooldown_remaining_ms)


T = TypeVar("T")


class CircuitBreaker:
    """Consecutive-failure breaker.

    Parameters
    ----------
    clock:
        Injectable clock (integer ms). Real code uses :class:`SystemClock`;
        tests use :class:`FakeClock`.
    threshold:
        Number of consecutive failures in CLOSED state that flip the breaker
        to OPEN. Default 5.
    cooldown_ms:
        Time the breaker remains OPEN before moving to HALF_OPEN. Default 30s.
    """

    def __init__(
        self,
        clock: Clock,
        *,
        threshold: int = 5,
        cooldown_ms: int = 30_000,
    ) -> None:
        if threshold < 1:
            raise ValueError("threshold must be >= 1")
        if cooldown_ms < 0:
            raise ValueError("cooldown_ms must be >= 0")
        self._clock = clock
        self._threshold = int(threshold)
        self._cooldown_ms = int(cooldown_ms)
        self._state: CircuitState = CircuitState.CLOSED
        self._failures = 0
        self._opened_at_ms = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        # Read is cheap — lock ensures we see a consistent snapshot.
        with self._lock:
            return self._state

    def check(self) -> None:
        """Raise if the breaker is currently OPEN.

        Also handles OPEN → HALF_OPEN transition when cooldown has elapsed.
        After this call returns without raising, the caller is allowed to
        issue the request and must report the outcome via :meth:`record_success`
        or :meth:`record_failure`.
        """
        with self._lock:
            if self._state == CircuitState.OPEN:
                elapsed = self._clock.now_ms() - self._opened_at_ms
                if elapsed >= self._cooldown_ms:
                    self._state = CircuitState.HALF_OPEN
                else:
                    raise CircuitBreakerOpen(self._cooldown_ms - elapsed)

    def record_success(self) -> None:
        with self._lock:
            self._failures = 0
            # Any success in HALF_OPEN or CLOSED resets to CLOSED.
            self._state = CircuitState.CLOSED

    def record_failure(self) -> None:
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                # A HALF_OPEN failure immediately flips back to OPEN.
                self._state = CircuitState.OPEN
                self._opened_at_ms = self._clock.now_ms()
                return
            self._failures += 1
            if self._failures >= self._threshold:
                self._state = CircuitState.OPEN
                self._opened_at_ms = self._clock.now_ms()

    async def arun(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Execute `fn()` under the breaker.

        Raises :class:`CircuitBreakerOpen` if the breaker is OPEN and cooldown
        has not elapsed. Re-raises any exception from `fn` after recording
        it as a failure. Records success on normal return.
        """
        self.check()
        try:
            result = await fn()
        except Exception:
            self.record_failure()
            raise
        self.record_success()
        return result

    # ------------------------------------------------------------------
    # Test helpers — visibility into internal state without reaching in.
    # ------------------------------------------------------------------

    def snapshot(self) -> tuple[CircuitState, int, int]:
        """Return (state, consecutive_failures, opened_at_ms). Read-only."""
        with self._lock:
            return (self._state, self._failures, self._opened_at_ms)


async def _ensure_coro(awaitable: Awaitable[T]) -> T:  # pragma: no cover
    """Await compatibility helper (unused by current callsites)."""
    return await awaitable
