"""Deterministic clock abstraction.

`Clock.now_ms()` returns integer milliseconds since epoch. `FakeClock` is
driven manually in tests; `SystemClock` reads the real wall clock.

The integer-ms contract (vs. float seconds) avoids floating-point drift when
the breaker computes cooldown deadlines.
"""

from __future__ import annotations

import time
from abc import ABC, abstractmethod


class Clock(ABC):
    """Abstract monotonic/wall-clock source in integer milliseconds."""

    @abstractmethod
    def now_ms(self) -> int:
        """Return current time as integer milliseconds since epoch."""


class SystemClock(Clock):
    """Real wall-clock backed by `time.time()`."""

    def now_ms(self) -> int:
        return int(time.time() * 1000)


class FakeClock(Clock):
    """Manually advanced clock for deterministic tests."""

    def __init__(self, start_ms: int = 0) -> None:
        self._now_ms = int(start_ms)

    def now_ms(self) -> int:
        return self._now_ms

    def advance_ms(self, delta_ms: int) -> None:
        if delta_ms < 0:
            raise ValueError("FakeClock.advance_ms requires non-negative delta")
        self._now_ms += int(delta_ms)

    def set_ms(self, when_ms: int) -> None:
        if when_ms < self._now_ms:
            raise ValueError("FakeClock cannot go backwards")
        self._now_ms = int(when_ms)
