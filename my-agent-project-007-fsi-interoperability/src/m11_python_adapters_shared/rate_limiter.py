"""Token-bucket rate limiter (per-firm + default).

Each `firm_id` (tenant) keeps its own bucket. Calls to :meth:`acquire` subtract
one token; if none available, raise :class:`RateLimitExceeded`. Tokens refill
linearly at ``rpm / 60_000`` per ms until the burst ceiling is reached.

This is the Python port of the TS ``RateLimiterRegistry``. Same token-bucket
algorithm (not sliding-window — token bucket gives nicer backoff signal to the
caller).
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Dict

from m11_python_adapters_shared.clock import Clock


class RateLimitExceeded(Exception):
    """Raised when the per-firm bucket is empty.

    `retry_after_ms` is the minimum time to wait before a call MIGHT succeed.
    """

    def __init__(self, retry_after_ms: int) -> None:
        super().__init__(f"rate limit exceeded; retry after {retry_after_ms} ms")
        self.retry_after_ms = int(retry_after_ms)


@dataclass
class _Bucket:
    tokens: float
    last_refill_ms: int


class RateLimiter:
    """Token bucket, one logical bucket per firm.

    Parameters
    ----------
    rpm:
        Requests per minute — equals burst capacity refill per minute.
    burst:
        Max tokens in the bucket. Controls peak concurrency / spike tolerance.
    clock:
        Injectable clock (integer ms).
    """

    def __init__(self, clock: Clock, *, rpm: int, burst: int) -> None:
        if rpm < 1:
            raise ValueError("rpm must be >= 1")
        if burst < 1:
            raise ValueError("burst must be >= 1")
        self._clock = clock
        self._rpm = int(rpm)
        self._burst = int(burst)
        # tokens per ms, pre-computed.
        self._refill_per_ms = float(rpm) / 60_000.0
        self._buckets: Dict[str, _Bucket] = {}
        self._lock = threading.Lock()

    def _get_or_init(self, firm_id: str, now_ms: int) -> _Bucket:
        b = self._buckets.get(firm_id)
        if b is None:
            b = _Bucket(tokens=float(self._burst), last_refill_ms=now_ms)
            self._buckets[firm_id] = b
        return b

    def _refill(self, b: _Bucket, now_ms: int) -> None:
        elapsed_ms = now_ms - b.last_refill_ms
        if elapsed_ms <= 0:
            return
        b.tokens = min(float(self._burst), b.tokens + elapsed_ms * self._refill_per_ms)
        b.last_refill_ms = now_ms

    def acquire(self, firm_id: str = "_default") -> None:
        """Consume one token or raise :class:`RateLimitExceeded`."""
        now_ms = self._clock.now_ms()
        with self._lock:
            b = self._get_or_init(firm_id, now_ms)
            self._refill(b, now_ms)
            if b.tokens >= 1.0:
                b.tokens -= 1.0
                return
            # Compute wait for the next full token.
            if self._refill_per_ms <= 0:  # pragma: no cover — rpm >= 1 guard
                raise RateLimitExceeded(retry_after_ms=60_000)
            deficit = 1.0 - b.tokens
            retry_ms = max(1, int(deficit / self._refill_per_ms))
            raise RateLimitExceeded(retry_after_ms=retry_ms)

    def snapshot_tokens(self, firm_id: str = "_default") -> float:
        """Test helper — current token count for a firm, post-refill."""
        now_ms = self._clock.now_ms()
        with self._lock:
            b = self._get_or_init(firm_id, now_ms)
            self._refill(b, now_ms)
            return b.tokens
