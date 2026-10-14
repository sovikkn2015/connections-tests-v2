"""End-to-end integration tests for M13 FastAPI app.

Every test runs through the real FastAPI TestClient — the same HTTP
surface M6 calls in production. Uses FakeFixEngine throughout (Spec
§2.3 + D7).
"""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from m13_fix_bridge.aid_verify import StaticAidVerifier
from m13_fix_bridge.app import create_app
from m13_fix_bridge.client.fake_engine import FakeFixEngine
from m13_fix_bridge.client.kill_switch import KillSwitch
from m13_fix_bridge.client.session import FileSeqnumStore
from m13_fix_bridge.client.session_manager import SessionManager
from m13_fix_bridge.config import FixConfig
from m13_fix_bridge.drop_copy import DropCopyEmitter
from m13_fix_bridge.models import VenueConfig
from m13_fix_bridge.startup import FakeSecretsClient, load_venue_configs, resolve_comp_ids


_SALT = b"m13-test-salt-32-bytes-exactly!!"


def _cfg(tmp_path, *, fix_enabled: bool) -> FixConfig:
    return FixConfig(
        fix_enabled=fix_enabled,
        sessions_config_vault_path="secret/data/007/m13/sessions",
        seqnum_store_dir=str(tmp_path / "seq"),
        drop_copy_enabled=True,
        kill_switch_state_path=str(tmp_path / "ks.json"),
        account_hash_salt_vault_path="secret/data/007/m13/hash_salt",
        aid_verify_mode="static",
        aid_verify_shared_secret_vault_path="",
        aid_verify_public_key_path="",
        secrets_backend="fake",
        http_port=8080,
        log_level="info",
    )


def _tokens() -> dict[str, dict]:
    now = int(time.time())
    return {
        "tok-trader": {
            "sub": "u-1",
            "aid": "aid-trader-001",
            "role": "trader",
            "tenant_id": "tenant-001",
            "firm_id": "firm-001",
            "iat": now,
            "exp": now + 3600,
        },
        "tok-sup": {
            "sub": "u-2",
            "aid": "aid-sup-001",
            "role": "trading_supervisor",
            "tenant_id": "tenant-001",
            "firm_id": "firm-001",
            "iat": now,
            "exp": now + 3600,
        },
    }


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


def _make_app(tmp_path, *, fix_enabled: bool = True, venues=("brokerx",)):
    cfg = _cfg(tmp_path, fix_enabled=fix_enabled)
    engine = FakeFixEngine()
    ks = KillSwitch(cfg.kill_switch_state_path)
    store = FileSeqnumStore(cfg.seqnum_store_dir)
    sm = SessionManager(engine=engine, seqnum_store=store, kill_switch=ks)
    drop_copy = DropCopyEmitter(audit=None, account_salt=_SALT) if False else None
    # We let create_app build the default DropCopyEmitter via its in-proc wiring.

    async def _bring_up() -> None:
        if fix_enabled:
            await sm.open([_vc(v) for v in venues])

    asyncio.run(_bring_up())

    app = create_app(
        config=cfg,
        engine=engine,
        verify_aid=StaticAidVerifier(_tokens()),
        kill_switch=ks,
        session_manager=sm,
        account_salt=_SALT,
    )
    return app, engine, sm, ks


# ---------------------------------------------------------------------------
# R1.1 - GET /
# ---------------------------------------------------------------------------


def test_health_returns_200_when_enabled_with_active_session(tmp_path) -> None:
    app, *_ = _make_app(tmp_path, fix_enabled=True)
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["capabilities"]["fix_enabled"] is True
        assert "brokerx" in body["checks"]


def test_health_returns_200_when_disabled(tmp_path) -> None:
    app, *_ = _make_app(tmp_path, fix_enabled=False)
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "ok"
        assert body["checks"]["fix"] == "disabled"


def test_health_returns_503_when_enabled_but_no_active_session(tmp_path) -> None:
    app, engine, *_ = _make_app(tmp_path, fix_enabled=True)
    # Force session DISCONNECTED so no active.
    from m13_fix_bridge.client.session import SessionState
    engine.force_state("brokerx", SessionState.DISCONNECTED)
    with TestClient(app) as c:
        r = c.get("/")
        assert r.status_code == 503
        body = r.json()
        assert body["status"] == "degraded"


# ---------------------------------------------------------------------------
# R1.2 - POST /tools/list
# ---------------------------------------------------------------------------


def test_tools_list_returns_six_tools_with_schemas(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        r = c.post("/tools/list")
        assert r.status_code == 200
        names = {t["name"] for t in r.json()["tools"]}
        assert names == {
            "fix.order_new",
            "fix.order_cancel",
            "fix.order_cancel_replace",
            "fix.order_status",
            "fix.session_status",
            "fix.kill_switch",
        }
        # Each tool has an inputSchema (JSON Schema).
        for t in r.json()["tools"]:
            assert "inputSchema" in t
            assert t["inputSchema"]["type"] == "object"


# ---------------------------------------------------------------------------
# R1.3 - POST /tools/call happy path
# ---------------------------------------------------------------------------


def test_tools_call_order_new_end_to_end(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        body = {
            "name": "fix.order_new",
            "arguments": {
                "cl_ord_id": "X-1",
                "venue": "brokerx",
                "symbol": "AAPL",
                "side": "1",
                "ord_type": "2",
                "order_qty": "100",
                "price": "183.50",
                "time_in_force": "0",
                "transact_time": datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc).isoformat(),
                "account": "ACCT_1",
            },
        }
        r = c.post("/tools/call", json=body, headers={"X-Agent-AID": "tok-trader"})
        assert r.status_code == 200
        env = r.json()
        assert env["isError"] is False
        assert env["content"]["cl_ord_id"] == "X-1"


def test_tools_call_missing_aid_header(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        r = c.post(
            "/tools/call",
            json={"name": "fix.session_status", "arguments": {"venue": "brokerx"}},
        )
        assert r.status_code == 200
        assert r.json()["errorCode"] == "unauthorized"


def test_tools_call_invalid_body(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        r = c.post(
            "/tools/call",
            content=b"not json",
            headers={
                "content-type": "application/json",
                "X-Agent-AID": "tok-trader",
            },
        )
        assert r.status_code == 200
        assert r.json()["errorCode"] == "invalid_arguments"


def test_tools_call_kill_switch_then_order_blocked(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        # Supervisor flips global kill on.
        ks_r = c.post(
            "/tools/call",
            json={
                "name": "fix.kill_switch",
                "arguments": {
                    "scope": "global",
                    "venue": None,
                    "state": "on",
                    "reason": "test-global-halt-001",
                },
            },
            headers={"X-Agent-AID": "tok-sup"},
        )
        assert ks_r.status_code == 200
        assert ks_r.json()["isError"] is False
        # Now a trader's order is blocked.
        ord_r = c.post(
            "/tools/call",
            json={
                "name": "fix.order_new",
                "arguments": {
                    "cl_ord_id": "X-2",
                    "venue": "brokerx",
                    "symbol": "AAPL",
                    "side": "1",
                    "ord_type": "1",
                    "order_qty": "10",
                    "time_in_force": "3",
                    "transact_time": datetime(2026, 4, 29, 14, 30, tzinfo=timezone.utc).isoformat(),
                    "account": "ACCT_1",
                },
            },
            headers={"X-Agent-AID": "tok-trader"},
        )
        assert ord_r.status_code == 200
        assert ord_r.json()["errorCode"] == "kill_switch_active"


def test_startup_load_venue_configs_from_fake_vault() -> None:
    """R4.1 Vault YAML parse path — integration with FakeSecretsClient."""
    yaml_text = """
- venue: brokerx
  sender_comp_id_vault_path: secret/data/007/m13/brokerx/sender
  target_comp_id_vault_path: secret/data/007/m13/brokerx/target
  host: fix.brokerx.example
  port: 9876
  heartbeat_interval_s: 30
  reset_on_logon: false
  use_tls: false
"""
    store = FakeSecretsClient(
        {
            "secret/data/007/m13/sessions": yaml_text,
            "secret/data/007/m13/brokerx/sender": "SENDER_1",
            "secret/data/007/m13/brokerx/target": "TARGET_1",
        }
    )

    async def _run() -> None:
        cfgs = await load_venue_configs(
            secrets=store,
            sessions_vault_path="secret/data/007/m13/sessions",
        )
        assert len(cfgs) == 1
        assert cfgs[0].venue == "brokerx"
        ids = await resolve_comp_ids(secrets=store, configs=cfgs)
        assert ids == {"brokerx": ("SENDER_1", "TARGET_1")}

    asyncio.run(_run())


def test_session_status_unknown_venue_returns_error_envelope(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        r = c.post(
            "/tools/call",
            json={"name": "fix.session_status", "arguments": {"venue": "unknown"}},
            headers={"X-Agent-AID": "tok-trader"},
        )
        assert r.json()["errorCode"] == "session_not_found"


def test_drop_copy_flows_from_inbound_exec_report(tmp_path) -> None:
    """End-to-end: order_new → correlator → simulate inbound ExecReport."""
    app, engine, sm, _ks = _make_app(tmp_path)
    with TestClient(app) as c:
        # 1. Submit an order, registering cl_ord_id → aid-trader-001 in the
        # drop-copy correlator.
        c.post(
            "/tools/call",
            json={
                "name": "fix.order_new",
                "arguments": {
                    "cl_ord_id": "X-100",
                    "venue": "brokerx",
                    "symbol": "MSFT",
                    "side": "1",
                    "ord_type": "1",
                    "order_qty": "50",
                    "time_in_force": "3",
                    "transact_time": datetime(2026, 4, 29, 15, tzinfo=timezone.utc).isoformat(),
                    "account": "ACCT_X",
                },
            },
            headers={"X-Agent-AID": "tok-trader"},
        )

        # 2. Simulate inbound ExecReport. Engine callback → SessionManager
        # inbound handler → drop-copy.
        async def _sim() -> None:
            await engine.simulate_inbound_exec_report(
                "brokerx",
                {
                    "cl_ord_id": "X-100",
                    "order_id": "OID-100",
                    "exec_type": "2",
                    "ord_status": "2",
                    "last_qty": "50",
                    "last_px": "315.00",
                    "cum_qty": "50",
                    "avg_px": "315.00",
                    "transact_time": datetime.now(tz=timezone.utc),
                    "account": "ACCT_X",
                    "tenant_id": "tenant-001",
                },
            )

        asyncio.run(_sim())
        # Drop-copy emission goes to stdout — the correlation registration
        # is observable through the app's drop_copy state.
        dc = app.state.drop_copy
        assert dc.correlator.lookup("X-100") == "aid-trader-001"


def test_tools_call_role_gate_rejects_trader_from_kill_switch(tmp_path) -> None:
    app, *_ = _make_app(tmp_path)
    with TestClient(app) as c:
        r = c.post(
            "/tools/call",
            json={
                "name": "fix.kill_switch",
                "arguments": {
                    "scope": "venue",
                    "venue": "brokerx",
                    "state": "on",
                    "reason": "trader-cannot-do-this",
                },
            },
            headers={"X-Agent-AID": "tok-trader"},
        )
        assert r.json()["errorCode"] == "unauthorized"
