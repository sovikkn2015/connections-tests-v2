"""SessionManager — multi-session coordinator for M13.

Responsibilities (Spec §R3, §R4, §2.3):

* Wraps a :class:`FixEngineProtocol` implementation.
* Holds the ``FileSeqnumStore`` so seqnums survive pod restarts.
* Registers the inbound callback on the engine so drop-copy wires up.
* Drives the SIGTERM handler: send Logout on every active session and
  fsync seqnums.
* Exposes per-venue ``SessionStatusResponse`` lookups for the
  ``fix.session_status`` tool.

This class does NOT talk FIX directly — it is a policy/plumbing layer
on top of the engine. The engine handles protocol semantics
(Heartbeat, TestRequest, ResendRequest). With ``FakeFixEngine`` those
are no-ops; with ``RealFixEngine`` they drive the socket.
"""

from __future__ import annotations

import asyncio
from typing import Any, Awaitable, Callable, Sequence

from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.protocol import FixEngineProtocol, InboundCallback
from m13_fix_bridge.client.session import FileSeqnumStore, SessionState
from m13_fix_bridge.models import SessionStatusResponse, VenueConfig


InboundHandler = Callable[[str, str, dict[str, Any]], Awaitable[None]]
"""User-level inbound handler — ``handler(venue, kind, msg)``."""


class SessionManager:
    """Lifecycle + state-query wrapper around a FIX engine."""

    def __init__(
        self,
        *,
        engine: FixEngineProtocol,
        seqnum_store: FileSeqnumStore,
        kill_switch: KillSwitch,
        inbound_handler: InboundHandler | None = None,
    ) -> None:
        self._engine = engine
        self._store = seqnum_store
        self._kill_switch = kill_switch
        self._configs: list[VenueConfig] = []
        self._inbound: InboundHandler | None = inbound_handler
        # Wire the engine's inbound callback through to the user's handler.
        self._engine.set_inbound_callback(self._on_inbound)

    @property
    def engine(self) -> FixEngineProtocol:
        return self._engine

    async def open(self, configs: Sequence[VenueConfig]) -> None:
        self._configs = list(configs)
        await self._engine.open(self._configs)
        # Persist starting seqnums if reset_on_logon was requested.
        for vc in self._configs:
            try:
                st = self._engine.session_state(vc.venue)
            except KeyError:
                continue
            if vc.reset_on_logon:
                self._store.reset(st.sender_comp_id, st.target_comp_id)
            else:
                # Ensure the file exists (load creates on read-miss).
                _ = self._store.load(st.sender_comp_id, st.target_comp_id)

    async def close(self, *, graceful: bool = True) -> None:
        """Shut down.

        When ``graceful=True`` we:
         1. Send Logout on every ACTIVE session (engine.close handles it).
         2. Fsync every session's seqnums.
        When ``graceful=False`` we close the engine immediately without
        persisting.
        """
        if graceful:
            for vc in self._configs:
                try:
                    st = self._engine.session_state(vc.venue)
                except KeyError:
                    continue
                self._store.save(
                    st.sender_comp_id,
                    st.target_comp_id,
                    int(st.seq_num_in),
                    int(st.seq_num_out),
                )
        await self._engine.close()

    async def kill_all_sessions(self, *, reason: str, actor_aid: str) -> None:
        """Send Logout on every active session (Spec §R7.2)."""
        self._kill_switch.set_global(True, reason=reason, actor_aid=actor_aid)
        await self._engine.close()

    # ------------------------------------------------------------------
    # Status queries
    # ------------------------------------------------------------------

    def session_status(self, venue: str) -> SessionStatusResponse | None:
        """Return a SessionStatusResponse or None if the venue is unknown.

        Unknown venue maps to ``session_not_found`` at dispatcher level.
        Known venue whose engine has not yet produced a state returns a
        DISCONNECTED stub.
        """
        # If we have a config but engine hasn't instantiated the session,
        # return a DISCONNECTED stub so the dispatcher can surface it.
        cfg = next((c for c in self._configs if c.venue == venue), None)
        if cfg is None:
            return None
        try:
            return self._engine.session_state(venue)
        except KeyError:
            return SessionStatusResponse(
                venue=venue,
                logon_status=SessionState.DISCONNECTED.value,  # type: ignore[arg-type]
                seq_num_in=0,
                seq_num_out=0,
                last_heartbeat_ts=None,
                sender_comp_id="",
                target_comp_id="",
            )

    def known_venues(self) -> list[str]:
        return sorted({c.venue for c in self._configs})

    def has_any_active_session(self) -> bool:
        for v in self.known_venues():
            st = self.session_status(v)
            if st is not None and st.logon_status == SessionState.ACTIVE.value:
                return True
        return False

    # ------------------------------------------------------------------
    # Inbound handler bridging
    # ------------------------------------------------------------------

    def set_inbound_handler(self, handler: InboundHandler) -> None:
        self._inbound = handler

    async def _on_inbound(self, venue: str, kind: str, msg: dict[str, Any]) -> None:
        if self._inbound is None:
            return
        await self._inbound(venue, kind, msg)


__all__ = ["SessionManager", "InboundHandler"]
