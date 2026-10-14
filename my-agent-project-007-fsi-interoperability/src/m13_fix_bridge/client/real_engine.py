"""RealFixEngine — production FIX engine using ``simplefix`` + asyncio.

This engine is gated behind ``FIX_ENABLED=true`` + a reachable
counterparty (per Spec §R12 and §2.3). In the v1 build the actual
socket + session-layer wiring is intentionally stubbed with
``NotImplementedError`` so:

* production deployments MUST explicitly opt in,
* tests always use ``FakeFixEngine``,
* the module-boundary test (Rule 33) passes regardless of whether
  ``simplefix`` is installed.

``simplefix`` is imported LAZILY inside ``open()``. The message-build
helpers are referenced in comments for v2 work.
"""

from __future__ import annotations

from typing import Any, Sequence

from m13_fix_bridge.client.protocol import FixEngineProtocol, InboundCallback
from m13_fix_bridge.models import (
    OrderResponse,
    SessionStatusResponse,
    VenueConfig,
)


_FIX_VERSION = "FIX.4.4"


class RealFixEngine(FixEngineProtocol):
    """Production FIX engine.

    Constructed without args; caller supplies venue configs via
    :meth:`open`. Raises :class:`NotImplementedError` from ``open`` in
    v1 — the actual socket + session reader loop lives in v2 ops work.
    """

    def __init__(self) -> None:
        self._open = False
        self._inbound: InboundCallback | None = None
        self._venues: set[str] = set()

    async def open(self, venue_configs: Sequence[VenueConfig]) -> None:
        """Open all sessions.

        v1: the live socket/session path is not wired. This method
        raises ``NotImplementedError`` to make live-mode failures
        loud rather than silent. Production rollout enables this in a
        follow-up (spec §R12).
        """
        # Lazy import — only here so the module boundary test doesn't
        # need simplefix installed in CI.
        try:
            import simplefix  # noqa: F401  (lazy import — kept for prod wiring)
        except ImportError as exc:  # pragma: no cover — CI has no simplefix
            raise NotImplementedError(
                "simplefix not installed; RealFixEngine requires simplefix>=1.0.17"
            ) from exc
        raise NotImplementedError(
            "RealFixEngine.open() is stubbed in v1. FIX live socket wiring "
            "is scheduled for v2 ops hardening. Use FakeFixEngine for tests."
        )

    async def close(self) -> None:
        self._open = False

    async def send_order_new(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        raise NotImplementedError("RealFixEngine v1 stub — see docstring")

    async def send_order_cancel(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        raise NotImplementedError("RealFixEngine v1 stub — see docstring")

    async def send_order_cancel_replace(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        raise NotImplementedError("RealFixEngine v1 stub — see docstring")

    async def send_order_status(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        raise NotImplementedError("RealFixEngine v1 stub — see docstring")

    def session_state(self, venue: str) -> SessionStatusResponse:
        raise NotImplementedError("RealFixEngine v1 stub — see docstring")

    def venues(self) -> list[str]:
        return sorted(self._venues)

    def has_venue(self, venue: str) -> bool:
        return venue in self._venues

    async def simulate_inbound_exec_report(
        self, venue: str, report: dict[str, Any]
    ) -> None:
        raise NotImplementedError("simulate_* is a FakeFixEngine hook only")

    async def simulate_inbound_cancel_reject(
        self, venue: str, reject: dict[str, Any]
    ) -> None:
        raise NotImplementedError("simulate_* is a FakeFixEngine hook only")

    def set_inbound_callback(self, callback: InboundCallback) -> None:
        self._inbound = callback


__all__ = ["RealFixEngine"]
