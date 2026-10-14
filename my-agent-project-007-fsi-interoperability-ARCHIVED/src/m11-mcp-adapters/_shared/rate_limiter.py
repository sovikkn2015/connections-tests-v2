"""
Token-bucket rate limiter for M11 MCP adapters.
Respects per-vendor API limits (Rule 4).
Configuration via environment variables: {VENDOR}_RATE_LIMIT_RPM, {VENDOR}_RATE_LIMIT_BURST.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field


@dataclass
class TokenBucket:
    """Token-bucket rate limiter with async support."""

    rate_per_second: float
    burst: int
    _tokens: float = field(init=False)
    _last_refill: float = field(init=False)
    _lock: asyncio.Lock = field(init=False, default_factory=asyncio.Lock)

    def __post_init__(self) -> None:
        self._tokens = float(self.burst)
        self._last_refill = time.monotonic()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        self._tokens = min(self.burst, self._tokens + elapsed * self.rate_per_second)
        self._last_refill = now

    async def acquire(self, timeout: float = 30.0) -> bool:
        """Acquire a token. Returns True if acquired, False if timed out."""
        deadline = time.monotonic() + timeout
        while True:
            async with self._lock:
                self._refill()
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return True
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.05)
