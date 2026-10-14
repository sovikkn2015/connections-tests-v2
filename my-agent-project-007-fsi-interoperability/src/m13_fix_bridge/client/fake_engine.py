"""FakeFixEngine — deterministic in-memory FIX engine for tests.

The engine implements :class:`FixEngineProtocol`. It maintains a map
``{venue: FakeVenueState}`` where each venue has a ``FixSession`` and a
reference to an ``_inbound_callback`` the session manager registers for
drop-copy.

All state transitions are synchronous and deterministic. Tests drive
inbound ExecReports / CancelRejects via ``simulate_inbound_*``.

Behaviours:

* ``open(venue_configs)`` flips every venue to ``ACTIVE`` after sending
  a simulated Logon-accepted transition (sessions immediately active in
  this engine — the session manager on top is free to overlay real-state
  semantics when wired to a real engine).
* Seqnums are in-memory only — tests assert against them directly
  without touching the disk. A separate ``FileSeqnumStore`` is used by
  integration tests when they want to assert persistence.
* ``close()`` flips every venue to DISCONNECTED (after LOGOUT_SENT).
* Outbound tools always succeed unless the ``reject_next`` flag is set,
  in which case they raise ``FakeRejectError`` — used to test error
  paths in the dispatcher.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Sequence

from m13_fix_bridge.client.protocol import FixEngineProtocol, InboundCallback
from m13_fix_bridge.client.session import FixSession, SessionState
from m13_fix_bridge.models import (
    OrderResponse,
    SessionStatusResponse,
    VenueConfig,
)


class FakeRejectError(Exception):
    """Raised by FakeFixEngine.send_* when configured to reject."""


@dataclass
class FakeVenueState:
    session: FixSession
    # Per-venue reject flags — tests set them to trigger error paths.
    reject_next: bool = False
    reject_reason: str = "venue_rejected"
    # Pre-resolved CompIDs (tests supply these directly; production
    # resolves from Vault before calling `open()`).
    sender_comp_id_resolved: str = ""
    target_comp_id_resolved: str = ""
    # Per-venue async lock for seqnum-bump ordering.
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)


class FakeFixEngine(FixEngineProtocol):
    """In-memory deterministic FIX engine used by all M13 tests."""

    def __init__(
        self,
        *,
        resolved_comp_ids: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        """``resolved_comp_ids`` maps ``venue -> (sender, target)``.

        When ``open()`` is called with a sequence of ``VenueConfig`` the
        engine looks up pre-resolved CompIDs from this map (tests don't
        have a real Vault). In production the wiring passes the resolved
        values directly.
        """
        self._venues: dict[str, FakeVenueState] = {}
        self._resolved = dict(resolved_comp_ids or {})
        self._inbound: InboundCallback | None = None
        self._is_open = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def open(self, venue_configs: Sequence[VenueConfig]) -> None:
        for vc in venue_configs:
            comp_ids = self._resolved.get(vc.venue)
            if comp_ids is None:
                # Default: derive deterministic fake IDs so tests don't
                # have to pre-populate the resolved map every time.
                sender = f"FAKE_SENDER_{vc.venue.upper()}"
                target = f"FAKE_TARGET_{vc.venue.upper()}"
            else:
                sender, target = comp_ids
            sess = FixSession(
                venue=vc.venue,
                sender_comp_id=sender,
                target_comp_id=target,
                heartbeat_interval_s=vc.heartbeat_interval_s,
                reset_on_logon=vc.reset_on_logon,
                state=SessionState.ACTIVE,
                seq_num_in=1 if vc.reset_on_logon else 1,
                seq_num_out=1 if vc.reset_on_logon else 1,
                last_heartbeat_ts=datetime.now(tz=timezone.utc),
            )
            self._venues[vc.venue] = FakeVenueState(
                session=sess,
                sender_comp_id_resolved=sender,
                target_comp_id_resolved=target,
            )
        self._is_open = True

    async def close(self) -> None:
        for vs in self._venues.values():
            vs.session.state = SessionState.DISCONNECTED
        self._is_open = False

    # ------------------------------------------------------------------
    # Outbound tool helpers
    # ------------------------------------------------------------------

    def set_venue_reject(
        self,
        venue: str,
        *,
        on: bool = True,
        reason: str = "venue_rejected",
    ) -> None:
        vs = self._require(venue)
        vs.reject_next = on
        vs.reject_reason = reason

    async def send_order_new(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        return await self._send(venue, msg, tool="fix.order_new")

    async def send_order_cancel(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        return await self._send(venue, msg, tool="fix.order_cancel")

    async def send_order_cancel_replace(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        return await self._send(venue, msg, tool="fix.order_cancel_replace")

    async def send_order_status(
        self, venue: str, msg: dict[str, Any]
    ) -> OrderResponse:
        return await self._send(venue, msg, tool="fix.order_status")

    async def _send(
        self,
        venue: str,
        msg: dict[str, Any],
        *,
        tool: str,
    ) -> OrderResponse:
        if venue not in self._venues:
            raise FakeRejectError(f"session_not_found: {venue!r}")
        vs = self._venues[venue]
        if vs.session.state is not SessionState.ACTIVE:
            raise FakeRejectError("session_not_authorized")
        if vs.reject_next:
            # Consume one-shot reject.
            vs.reject_next = False
            raise FakeRejectError(vs.reject_reason)
        async with vs.lock:
            vs.session.seq_num_out += 1
            vs.session.last_outbound_ts = datetime.now(tz=timezone.utc)
            return OrderResponse(
                cl_ord_id=str(msg.get("cl_ord_id", "")),
                venue=venue,
                sender_comp_id=vs.sender_comp_id_resolved,
                target_comp_id=vs.target_comp_id_resolved,
                seq_num_out=vs.session.seq_num_out,
                accepted_at=vs.session.last_outbound_ts,
                bridge_status="sent",
            )

    # ------------------------------------------------------------------
    # Session-state query
    # ------------------------------------------------------------------

    def session_state(self, venue: str) -> SessionStatusResponse:
        if venue not in self._venues:
            # Session manager distinguishes "unknown" from "disconnected";
            # the engine raises to let the caller choose.
            raise KeyError(venue)
        s = self._venues[venue].session
        return SessionStatusResponse(
            venue=venue,
            logon_status=s.state.value,  # type: ignore[arg-type]
            seq_num_in=int(s.seq_num_in),
            seq_num_out=int(s.seq_num_out),
            last_heartbeat_ts=s.last_heartbeat_ts,
            sender_comp_id=s.sender_comp_id,
            target_comp_id=s.target_comp_id,
        )

    def venues(self) -> list[str]:
        return sorted(self._venues.keys())

    def has_venue(self, venue: str) -> bool:
        return venue in self._venues

    # ------------------------------------------------------------------
    # Drop-copy inbound hooks
    # ------------------------------------------------------------------

    def set_inbound_callback(self, callback: InboundCallback) -> None:
        self._inbound = callback

    async def simulate_inbound_exec_report(
        self, venue: str, report: dict[str, Any]
    ) -> None:
        self._require(venue)
        if self._inbound is None:
            return
        await self._inbound(venue, "exec_report", report)
        vs = self._venues[venue]
        async with vs.lock:
            vs.session.seq_num_in += 1
            vs.session.last_inbound_ts = datetime.now(tz=timezone.utc)

    async def simulate_inbound_cancel_reject(
        self, venue: str, reject: dict[str, Any]
    ) -> None:
        self._require(venue)
        if self._inbound is None:
            return
        await self._inbound(venue, "cancel_reject", reject)
        vs = self._venues[venue]
        async with vs.lock:
            vs.session.seq_num_in += 1
            vs.session.last_inbound_ts = datetime.now(tz=timezone.utc)

    # ------------------------------------------------------------------
    # Test helpers (not part of the Protocol)
    # ------------------------------------------------------------------

    def force_state(self, venue: str, state: SessionState) -> None:
        """Test helper to drive the state machine directly."""
        vs = self._require(venue)
        vs.session.state = state

    def get_session(self, venue: str) -> FixSession:
        """Return the underlying session object (tests only)."""
        return self._require(venue).session

    def _require(self, venue: str) -> FakeVenueState:
        vs = self._venues.get(venue)
        if vs is None:
            raise KeyError(venue)
        return vs


__all__ = ["FakeFixEngine", "FakeRejectError"]
