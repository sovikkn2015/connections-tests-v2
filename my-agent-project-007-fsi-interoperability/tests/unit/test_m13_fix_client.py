"""Unit tests for ``m13_fix_bridge.dispatcher`` — Spec §R1-R3, R7, R8, R13.

Exercises the full tool-dispatch path with ``FakeFixEngine``.
Every test uses the high-level ``Dispatcher.call`` interface so the
same call shape HTTP clients use is tested here.
"""

from __future__ import annotations

import asyncio
import io
import json
import time
from datetime import datetime, timezone

import pytest

from m13_fix_bridge.aid_verify import HmacAidVerifier, StaticAidVerifier
from m13_fix_bridge.audit import StdoutAuditEmitter
from m13_fix_bridge.client.fake_engine import FakeFixEngine
from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.session import FileSeqnumStore
from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.dispatcher import Dispatcher
from m13_fix_bridge.drop_copy import DropCopyEmitter
from m13_fix_bridge.models import VenueConfig


_SALT = b"m13-test-salt-32-bytes-exactly!!"


def _vc(venue: str = "brokerx") -> VenueConfig:
    return VenueConfig(
        venue=venue,
        sender_comp_id_vault_path=f"secret/data/007/m13/{venue}/sender",
        target_comp_id_vault_path=f"secret/data/007/m13/{venue}/target",
        host=f"fix.{venue}.example",
        port=9876,
        heartbeat_interval_s=30,
        reset_on_logon=False,
        use_tls=False,
    )


def _make_dispatcher(
    tmp_path,
    *,
    fix_enabled: bool = True,
    aid_tokens: dict[str, dict] | None = None,
    venues: list[str] | None = None,
):
    """Build a fully wired Dispatcher for testing.

    Returns (dispatcher, audit_buf, kill_switch, engine, session_manager).
    """
    buf = io.StringIO()
    audit = StdoutAuditEmitter(stream=buf)
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    engine = FakeFixEngine()
    sm = SessionManager(engine=engine, seqnum_store=store, kill_switch=ks)
    drop_copy = DropCopyEmitter(audit=audit, account_salt=_SALT)

    verify = StaticAidVerifier(aid_tokens or _default_tokens())
    disp = Dispatcher(
        session_manager=sm,
        kill_switch=ks,
        audit=audit,
        verify_aid=verify,
        drop_copy=drop_copy,
        fix_enabled=fix_enabled,
    )

    # Open the engine sessions before tests run.
    async def _o() -> None:
        await sm.open([_vc(v) for v in (venues or ["brokerx"])])

    asyncio.run(_o())
    return disp, buf, ks, engine, sm


def _default_tokens() -> dict[str, dict]:
    now = int(time.time())
    return {
        "tok-trader": {
            "sub": "user-001",
            "aid": "aid-trader-001",
            "role": "trader",
            "tenant_id": "tenant-001",
            "firm_id": "firm-001",
            "iat": now,
            "exp": now + 3600,
        },
        "tok-supervisor": {
            "sub": "user-002",
            "aid": "aid-sup-001",
            "role": "trading_supervisor",
            "tenant_id": "tenant-001",
            "firm_id": "firm-001",
            "iat": now,
            "exp": now + 3600,
        },
    }


def _utc() -> datetime:
    return datetime(2026, 4, 29, 14, 30, 0, tzinfo=timezone.utc)


def _order_args(cl: str = "X-1") -> dict:
    return {
        "cl_ord_id": cl,
        "venue": "brokerx",
        "symbol": "AAPL",
        "side": "1",
        "ord_type": "2",
        "order_qty": "100",
        "price": "183.50",
        "time_in_force": "0",
        "transact_time": _utc().isoformat(),
        "account": "ACCT_1",
    }


def _read_lines(buf: io.StringIO) -> list[dict]:
    return [json.loads(line) for line in buf.getvalue().splitlines() if line]


# ---------------------------------------------------------------------------
# Happy path per tool
# ---------------------------------------------------------------------------


def test_order_new_happy_path(tmp_path) -> None:
    disp, buf, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="tok-trader",
        )
        assert env["isError"] is False
        assert env["content"]["cl_ord_id"] == "X-1"
        assert env["content"]["bridge_status"] == "sent"

    asyncio.run(_run())
    audits = _read_lines(buf)
    assert any(a["kind"] == "fix.tool_audit" and a["outcome"] == "success" for a in audits)


def test_order_cancel_happy_path(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        args = {
            "orig_cl_ord_id": "X-1",
            "cl_ord_id": "X-1-CXL",
            "venue": "brokerx",
            "symbol": "AAPL",
            "side": "1",
            "transact_time": _utc().isoformat(),
        }
        env = await disp.call(
            tool="fix.order_cancel",
            arguments=args,
            aid_token="tok-trader",
        )
        assert env["isError"] is False

    asyncio.run(_run())


def test_order_cancel_replace_happy_path(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        args = {
            "orig_cl_ord_id": "X-1",
            "cl_ord_id": "X-1-R",
            "venue": "brokerx",
            "symbol": "AAPL",
            "side": "1",
            "ord_type": "2",
            "order_qty": "50",
            "price": "185.00",
            "time_in_force": "0",
            "transact_time": _utc().isoformat(),
        }
        env = await disp.call(
            tool="fix.order_cancel_replace",
            arguments=args,
            aid_token="tok-trader",
        )
        assert env["isError"] is False

    asyncio.run(_run())


def test_order_status_happy_path(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        args = {
            "cl_ord_id": "X-1",
            "venue": "brokerx",
            "symbol": "AAPL",
            "side": "1",
        }
        env = await disp.call(
            tool="fix.order_status",
            arguments=args,
            aid_token="tok-trader",
        )
        assert env["isError"] is False

    asyncio.run(_run())


def test_session_status_happy_path(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.session_status",
            arguments={"venue": "brokerx"},
            aid_token="tok-trader",
        )
        assert env["isError"] is False
        assert env["content"]["logon_status"] == "ACTIVE"

    asyncio.run(_run())


def test_session_status_unknown_venue(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.session_status",
            arguments={"venue": "nowhere"},
            aid_token="tok-trader",
        )
        assert env["isError"] is True
        assert env["errorCode"] == "session_not_found"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Auth & role
# ---------------------------------------------------------------------------


def test_missing_aid_header(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token=None,
        )
        assert env["isError"] is True
        assert env["errorCode"] == "unauthorized"

    asyncio.run(_run())


def test_unknown_token(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="invalid-token",
        )
        assert env["errorCode"] == "unauthorized"

    asyncio.run(_run())


def test_kill_switch_requires_role(tmp_path) -> None:
    """R13.4 — trader role cannot toggle kill switch."""
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.kill_switch",
            arguments={
                "scope": "global",
                "venue": None,
                "state": "on",
                "reason": "unauthorized-test-0001",
            },
            aid_token="tok-trader",
        )
        assert env["errorCode"] == "unauthorized"

    asyncio.run(_run())


def test_kill_switch_accepts_supervisor(tmp_path) -> None:
    disp, _, ks, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.kill_switch",
            arguments={
                "scope": "global",
                "venue": None,
                "state": "on",
                "reason": "authorized-halt-0001",
            },
            aid_token="tok-supervisor",
        )
        assert env["isError"] is False
        assert ks.global_state()["on"] is True

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Kill switch behavior
# ---------------------------------------------------------------------------


def test_kill_switch_blocks_order(tmp_path) -> None:
    disp, _, ks, *_ = _make_dispatcher(tmp_path)
    ks.set_venue(
        "brokerx", True, reason="venue-halted-ops", actor_aid="aid-sup-x"
    )

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="tok-trader",
        )
        assert env["errorCode"] == "kill_switch_active"

    asyncio.run(_run())


def test_kill_switch_lets_session_status_through(tmp_path) -> None:
    """R7.4 — only order_* are blocked; status still works."""
    disp, _, ks, *_ = _make_dispatcher(tmp_path)
    ks.set_global(True, reason="global-halt-ops", actor_aid="aid-sup-x")

    async def _run() -> None:
        env = await disp.call(
            tool="fix.session_status",
            arguments={"venue": "brokerx"},
            aid_token="tok-trader",
        )
        assert env["isError"] is False

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# FIX_ENABLED=false
# ---------------------------------------------------------------------------


def test_fix_disabled_order_returns_error(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path, fix_enabled=False)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="tok-trader",
        )
        assert env["errorCode"] == "fix_enabled_false"

    asyncio.run(_run())


def test_fix_disabled_session_status_still_works(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path, fix_enabled=False)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.session_status",
            arguments={"venue": "brokerx"},
            aid_token="tok-trader",
        )
        assert env["isError"] is False

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Validation + errors
# ---------------------------------------------------------------------------


def test_invalid_arguments(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments={"cl_ord_id": "X", "symbol": "lowercase"},
            aid_token="tok-trader",
        )
        assert env["errorCode"] == "invalid_arguments"

    asyncio.run(_run())


def test_unknown_tool(tmp_path) -> None:
    disp, _, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        env = await disp.call(
            tool="fix.nonsense", arguments={}, aid_token="tok-trader"
        )
        assert env["errorCode"] == "unknown_tool"

    asyncio.run(_run())


def test_venue_rejection_surfaces(tmp_path) -> None:
    disp, _, _ks, engine, _ = _make_dispatcher(tmp_path)
    engine.set_venue_reject("brokerx", on=True, reason="venue_rejected")

    async def _run() -> None:
        env = await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="tok-trader",
        )
        assert env["errorCode"] == "venue_rejected"

    asyncio.run(_run())


# ---------------------------------------------------------------------------
# Audit event shape
# ---------------------------------------------------------------------------


def test_audit_includes_firm_tenant_trader(tmp_path) -> None:
    disp, buf, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="tok-trader",
        )

    asyncio.run(_run())
    lines = _read_lines(buf)
    tool_line = [l for l in lines if l["kind"] == "fix.tool_audit"][0]
    # Tenant and firm come from verified AID claims — not from client.
    assert tool_line["tenant_id"] == "tenant-001"
    assert tool_line["firm_id"] == "firm-001"
    assert tool_line["trader_aid"] == "aid-trader-001"
    assert "duration_ms" in tool_line


def test_audit_failure_has_error_code(tmp_path) -> None:
    disp, buf, *_ = _make_dispatcher(tmp_path)

    async def _run() -> None:
        await disp.call(
            tool="fix.unknown", arguments={}, aid_token="tok-trader"
        )

    asyncio.run(_run())
    lines = _read_lines(buf)
    fail = [l for l in lines if l["kind"] == "fix.tool_audit"][0]
    assert fail["outcome"] == "failure"
    assert fail["error_code"] == "unknown_tool"


def test_catalog_returns_six_tools() -> None:
    cat = Dispatcher.catalog()
    names = {t["name"] for t in cat}
    assert names == {
        "fix.order_new",
        "fix.order_cancel",
        "fix.order_cancel_replace",
        "fix.order_status",
        "fix.session_status",
        "fix.kill_switch",
    }


def test_dropcopy_correlates_on_order_new(tmp_path) -> None:
    """R6.1 — order_new should register cl_ord_id → trader_aid."""
    disp, _, _ks, engine, _ = _make_dispatcher(tmp_path)
    dc = disp._drop_copy  # test-only access
    assert dc.correlator.lookup("X-1") is None

    async def _run() -> None:
        await disp.call(
            tool="fix.order_new",
            arguments=_order_args(),
            aid_token="tok-trader",
        )

    asyncio.run(_run())
    assert dc.correlator.lookup("X-1") == "aid-trader-001"


def test_aid_hmac_verifier_end_to_end(tmp_path) -> None:
    """Integration between HmacAidVerifier and Dispatcher."""
    secret = b"m13-shared-secret-32-bytes-xxxxxx"
    claims = {
        "sub": "u",
        "aid": "aid-t",
        "role": "trader",
        "tenant_id": "t",
        "firm_id": "f",
        "iat": int(time.time()),
        "exp": int(time.time()) + 600,
    }
    token = HmacAidVerifier.make_token(secret, claims)

    audit_buf = io.StringIO()
    audit = StdoutAuditEmitter(stream=audit_buf)
    ks = KillSwitch(str(tmp_path / "ks.json"))
    store = FileSeqnumStore(str(tmp_path / "seq"))
    engine = FakeFixEngine()
    sm = SessionManager(engine=engine, seqnum_store=store, kill_switch=ks)
    drop_copy = DropCopyEmitter(audit=audit, account_salt=_SALT)
    disp = Dispatcher(
        session_manager=sm,
        kill_switch=ks,
        audit=audit,
        verify_aid=HmacAidVerifier(secret),
        drop_copy=drop_copy,
        fix_enabled=True,
    )

    async def _run() -> None:
        await sm.open([_vc()])
        env = await disp.call(
            tool="fix.session_status",
            arguments={"venue": "brokerx"},
            aid_token=token,
        )
        assert env["isError"] is False

    asyncio.run(_run())
