"""Abstract FIX engine protocol.

The bridge talks to FIX venues through an engine; tests inject
``FakeFixEngine`` (deterministic, in-memory), production uses
``RealFixEngine`` (simplefix + asyncio TCP). Both implement this
protocol.

The protocol is tuned for the six MCP tools + drop-copy ingestion:

* ``send_order_*`` methods build the FIX message, send, bump seqnum.
* ``session_state`` returns the per-venue state tuple for the
  ``fix.session_status`` tool.
* ``simulate_inbound_*`` is the test hook — ``RealFixEngine`` raises
  ``NotImplementedError`` because real inbound flows through the TCP
  reader loop.
* ``set_inbound_callback`` registers the hook the drop-copy path uses
  to receive ExecReports / CancelRejects.
"""

from __future__ import annotations

from typing import Any, Awaitable, Callable, Protocol, Sequence, TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover — typing only
    from m13_fix_bridge.models import (
        OrderResponse,
        SessionStatusResponse,
        VenueConfig,
    )


InboundCallback = Callable[[str, str, dict[str, Any]], Awaitable[None]]
"""Signature: ``callback(venue, kind, msg_dict)``. ``kind`` is one of
``"exec_report"`` / ``"cancel_reject"``."""


class FixEngineProtocol(Protocol):
    async def open(self, venue_configs: "Sequence[VenueConfig]") -> None: ...

    async def close(self) -> None: ...

    async def send_order_new(
        self, venue: str, msg: dict[str, Any]
    ) -> "OrderResponse": ...

    async def send_order_cancel(
        self, venue: str, msg: dict[str, Any]
    ) -> "OrderResponse": ...

    async def send_order_cancel_replace(
        self, venue: str, msg: dict[str, Any]
    ) -> "OrderResponse": ...

    async def send_order_status(
        self, venue: str, msg: dict[str, Any]
    ) -> "OrderResponse": ...

    def session_state(self, venue: str) -> "SessionStatusResponse": ...

    def venues(self) -> list[str]: ...

    def has_venue(self, venue: str) -> bool: ...

    async def simulate_inbound_exec_report(
        self, venue: str, report: dict[str, Any]
    ) -> None: ...

    async def simulate_inbound_cancel_reject(
        self, venue: str, reject: dict[str, Any]
    ) -> None: ...

    def set_inbound_callback(self, callback: InboundCallback) -> None: ...


__all__ = ["FixEngineProtocol", "InboundCallback"]
