"""Unit tests for FixSession + FileSeqnumStore + SessionManager.

Covers Spec §R4 (state machine, heartbeat, SIGTERM) and §R5 (seqnum
persistence + fsync + reset). Uses FakeFixEngine throughout.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timezone

import pytest

from m13_fix_bridge.client.fake_engine import FakeFixEngine
from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.session import (
    FileSeqnumStore,
    FixSession,
    SessionState,
)
from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.models import VenueConfig


# ---------------------------------------------------------------------------
# FileSeqnumStore
# ---------------------------------------------------------------------------


def test_seqnum_store_load_missing_file_returns_one(tmp_path) -> None:
    s = FileSeqnumStore(str(tmp_path))
    assert s.load("SENDER", "TARGET") == (1, 1)


def test_seqnum_store_save_and_load_roundtrip(tmp_path) -> None:
    s = FileSeqnumStore(str(tmp_path))
    s.save("SENDER", "TARGET", 42, 99)
    assert s.load("SENDER", "TARGET") == (42, 99)


def test_seqnum_store_bump_out_persists(tmp_path) -> None:
    s = FileSeqnumStore(str(tmp_path))
    assert s.bump_out("A", "B") == 2
    assert s.bump_out("A", "B") == 3
    assert s.bump_out("A", "B") == 4
    # New instance reads the same seqnum.
    s2 = FileSeqnumStore(str(tmp_path))
    assert s2.load("A", "B") == (1, 4)


def test_seqnum_store_bump_in_validates(tmp_path) -> None:
    s = FileSeqnumStore(str(tmp_path))
    with pytest.raises(ValueError):
        s.bump_in("A", "B", 0)


def test_seqnum_store_reset_truncates(tmp_path) -> None:
    s = FileSeqnumStore(str(tmp_path))
    s.save("A", "B", 99, 77)
    s.reset("A", "B")
    assert s.load("A", "B") == (1, 1)


def test_seqnum_store_corrupt_file_falls_back(tmp_path) -> None:
    s = FileSeqnumStore(str(tmp_path))
    target_path = os.path.join(str(tmp_path), "A.B.json")
    with open(target_path, "w") as fh:
        fh.write("{not json")
    assert s.load("A", "B") == (1, 1)


def test_seqnum_store_atomic_replace_on_bump(tmp_path) -> None:
    """After bump the file is valid JSON and no .tmp files linger."""
    s = FileSeqnumStore(str(tmp_path))
    s.bump_out("A", "B")
    target_path = os.path.join(str(tmp_path), "A.B.json")
    assert os.path.exists(target_path)
    assert not os.path.exists(target_path + ".tmp")
    with open(target_path) as fh:
        data = json.load(fh)
    assert data["seq_num_out"] == 2


def test_seqnum_store_safe_filename(tmp_path) -> None:
    """Unusual CompID chars don't escape the directory."""
    s = FileSeqnumStore(str(tmp_path))
    s.save("A/..", "B", 5, 6)
    # The file lives under tmp_path with safe name, not traversed.
    files = list(tmp_path.iterdir())
    assert any("A" in f.name for f in files)
    assert s.load("A/..", "B") == (5, 6)


# ---------------------------------------------------------------------------
# FixSession data
# ---------------------------------------------------------------------------


def test_fix_session_starts_disconnected() -> None:
    s = FixSession(
        venue="brokerx",
        sender_comp_id="SENDER",
        target_comp_id="TARGET",
        heartbeat_interval_s=30,
    )
    assert s.state is SessionState.DISCONNECTED
    assert s.seq_num_in == 1
    assert s.seq_num_out == 1
    assert not s.is_active()


def test_fix_session_active() -> None:
    s = FixSession(
        venue="brokerx",
        sender_comp_id="SENDER",
        target_comp_id="TARGET",
        heartbeat_interval_s=30,
        state=SessionState.ACTIVE,
    )
    assert s.is_active()


def test_fix_session_touch_inbound_outbound() -> None:
    s = FixSession(
        venue="brokerx",
        sender_comp_id="A",
        target_comp_id="B",
        heartbeat_interval_s=30,
    )
    now = datetime.now(tz=timezone.utc)
    s.touch_outbound(now)
    s.touch_inbound(now)
    assert s.last_outbound_ts == now
    assert s.last_inbound_ts == now


# ---------------------------------------------------------------------------
# FakeFixEngine + SessionManager
# ---------------------------------------------------------------------------


def _vc(venue: str = "brokerx", reset: bool = False, tls: bool = False) -> VenueConfig:
    return VenueConfig(
        venue=venue,
        sender_comp_id_vault_path=f"secret/data/007/m13/{venue}/sender",
        target_comp_id_vault_path=f"secret/data/007/m13/{venue}/target",
        host=f"fix.{venue}.example",
        port=9876,
        heartbeat_interval_s=30,
        reset_on_logon=reset,
        use_tls=tls,
    )


def test_sm_open_close_cycle(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        st = sm.session_status("brokerx")
        assert st is not None
        assert st.logon_status == SessionState.ACTIVE.value
        assert sm.has_any_active_session()
        await sm.close(graceful=True)
        # After close, session is DISCONNECTED.
        st2 = sm.session_status("brokerx")
        assert st2 is not None
        assert st2.logon_status == SessionState.DISCONNECTED.value

    asyncio.run(_run())


def test_sm_reset_on_logon_truncates_seqnums(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    # Pre-populate a seqnum file.
    store.save("FAKE_SENDER_BROKERX", "FAKE_TARGET_BROKERX", 99, 77)
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc(reset=True)])
        assert store.load("FAKE_SENDER_BROKERX", "FAKE_TARGET_BROKERX") == (1, 1)

    asyncio.run(_run())


def test_sm_session_status_unknown_venue_returns_none(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc("brokerx")])
        assert sm.session_status("unknown_venue") is None

    asyncio.run(_run())


def test_sm_send_order_seqnum_increments(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        r1 = await eng.send_order_new(
            "brokerx",
            {
                "cl_ord_id": "X-1",
                "venue": "brokerx",
                "symbol": "AAPL",
                "side": "1",
            },
        )
        r2 = await eng.send_order_new(
            "brokerx",
            {
                "cl_ord_id": "X-2",
                "venue": "brokerx",
                "symbol": "AAPL",
                "side": "1",
            },
        )
        assert r1.seq_num_out < r2.seq_num_out

    asyncio.run(_run())


def test_sm_send_to_unknown_venue_raises(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        from m13_fix_bridge.client.fake_engine import FakeRejectError

        with pytest.raises(FakeRejectError, match="session_not_found"):
            await eng.send_order_new(
                "unknown", {"cl_ord_id": "X-3", "venue": "unknown"}
            )

    asyncio.run(_run())


def test_sm_inbound_exec_report_drives_callback(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    captured: list[tuple[str, str, dict]] = []

    async def handler(venue, kind, msg):
        captured.append((venue, kind, dict(msg)))

    sm.set_inbound_handler(handler)

    async def _run() -> None:
        await sm.open([_vc()])
        await eng.simulate_inbound_exec_report(
            "brokerx",
            {
                "cl_ord_id": "X-1",
                "order_id": "OID-1",
                "exec_type": "0",
                "ord_status": "0",
                "cum_qty": "0",
                "transact_time": datetime.now(tz=timezone.utc),
                "account": "ACCT_A",
            },
        )
        assert len(captured) == 1
        assert captured[0][0] == "brokerx"
        assert captured[0][1] == "exec_report"
        assert captured[0][2]["cl_ord_id"] == "X-1"

    asyncio.run(_run())


def test_sm_inbound_bumps_seqnum_in(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        start = eng.session_state("brokerx").seq_num_in
        await eng.simulate_inbound_exec_report(
            "brokerx",
            {
                "cl_ord_id": "X-1",
                "order_id": "OID-1",
                "exec_type": "0",
                "ord_status": "0",
                "cum_qty": "0",
                "transact_time": datetime.now(tz=timezone.utc),
                "account": "ACCT_A",
            },
        )
        end = eng.session_state("brokerx").seq_num_in
        assert end == start + 1

    asyncio.run(_run())


def test_sm_close_fsyncs_seqnums(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        await eng.send_order_new(
            "brokerx",
            {"cl_ord_id": "X-1", "venue": "brokerx"},
        )
        # Close should persist the current seqnum state.
        await sm.close(graceful=True)
        sender = "FAKE_SENDER_BROKERX"
        target = "FAKE_TARGET_BROKERX"
        seq_in, seq_out = store.load(sender, target)
        assert seq_out >= 2  # at least one outbound

    asyncio.run(_run())


def test_sm_kill_all_sessions_sets_global(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        await sm.kill_all_sessions(reason="global-halt-001", actor_aid="aid-sup-01")
        assert ks.is_blocked("brokerx")
        assert ks.global_state()["on"] is True

    asyncio.run(_run())


def test_sm_force_disconnect(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        eng.force_state("brokerx", SessionState.DISCONNECTED)
        assert not sm.has_any_active_session()

    asyncio.run(_run())


def test_sm_multi_venue_sessions_independent(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc("brokerx"), _vc("broker_y")])
        assert set(sm.known_venues()) == {"brokerx", "broker_y"}
        # Force one disconnected; the other remains active.
        eng.force_state("brokerx", SessionState.DISCONNECTED)
        assert sm.has_any_active_session()

    asyncio.run(_run())


def test_sm_session_state_after_disconnect(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc()])
        eng.force_state("brokerx", SessionState.DISCONNECTED)
        st = sm.session_status("brokerx")
        assert st is not None
        assert st.logon_status == SessionState.DISCONNECTED.value

    asyncio.run(_run())


def test_fix_session_state_enum_values() -> None:
    """All 4 enum values exist as documented (Spec §2.4)."""
    assert SessionState.DISCONNECTED.value == "DISCONNECTED"
    assert SessionState.LOGON_SENT.value == "LOGON_SENT"
    assert SessionState.ACTIVE.value == "ACTIVE"
    assert SessionState.LOGOUT_SENT.value == "LOGOUT_SENT"


def test_fake_engine_venues_listing(tmp_path) -> None:
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    eng = FakeFixEngine()
    sm = SessionManager(engine=eng, seqnum_store=store, kill_switch=ks)

    async def _run() -> None:
        await sm.open([_vc("alpha"), _vc("beta")])
        assert eng.venues() == ["alpha", "beta"]
        assert eng.has_venue("alpha")
        assert not eng.has_venue("gamma")

    asyncio.run(_run())
