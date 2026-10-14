"""
M13 FIX Bridge — Tests (~30 tests).

Uses importlib pattern for module loading (prefix: fix_).
Covers: session lifecycle, sequence numbers, NewOrderSingle, ExecutionReport,
OrderCancelRequest, heartbeat, resend request, MCP tools (dev mode handlers),
QuickFIX engine dev mode, invalid state errors.

No cross-module imports. No credentials. No LLM.
"""

from __future__ import annotations

import importlib.util
import json
import sys
import types
from datetime import datetime, timezone
from pathlib import Path

import pytest

# ── importlib pattern ────────────────────────────────────────────

_HERE = Path(__file__).parent


def _load_module(name: str, file_name: str) -> types.ModuleType:
    """Load a module from the m13-fix-bridge package using importlib."""
    spec = importlib.util.spec_from_file_location(name, _HERE / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


fix_models = _load_module("fix_models", "models.py")
fix_session_mgr = _load_module("fix_session_manager", "session_manager.py")

FIXSessionState = fix_models.FIXSessionState
FIXMessageType = fix_models.FIXMessageType
FIXSession = fix_models.FIXSession
FIXBridgeConfig = fix_models.FIXBridgeConfig
NewOrderSingle = fix_models.NewOrderSingle
ExecutionReport = fix_models.ExecutionReport
OrderCancelRequest = fix_models.OrderCancelRequest
FIXSessionManager = fix_session_mgr.FIXSessionManager


# ── Fixtures ─────────────────────────────────────────────────────


def _make_config(**overrides) -> FIXBridgeConfig:
    defaults = {
        "broker_host": "fix.broker.example.com",
        "broker_port": 9876,
        "sender_comp_id": "007_BRIDGE",
        "target_comp_id": "BROKER_A",
    }
    defaults.update(overrides)
    return FIXBridgeConfig(**defaults)


def _make_order(**overrides) -> NewOrderSingle:
    defaults = {
        "symbol": "AAPL",
        "side": "1",
        "order_type": "2",
        "quantity": 100,
        "price": 150.50,
        "account": "ACC-001",
    }
    defaults.update(overrides)
    return NewOrderSingle(**defaults)


def _make_exec_report(**overrides) -> ExecutionReport:
    defaults = {
        "exec_id": "EXEC-001",
        "cl_ord_id": "ORD-001",
        "order_id": "EXCH-001",
        "exec_type": "2",
        "ord_status": "2",
        "symbol": "AAPL",
        "side": "1",
        "quantity": 100,
        "price": 150.50,
        "leaves_qty": 0,
        "cum_qty": 100,
        "avg_px": 150.50,
    }
    defaults.update(overrides)
    return ExecutionReport(**defaults)


@pytest.fixture
def mgr() -> FIXSessionManager:
    return FIXSessionManager()


@pytest.fixture
def connected_session(mgr: FIXSessionManager) -> tuple[FIXSessionManager, str]:
    """Return (manager, session_id) with session in LOGGED_ON state."""
    config = _make_config()
    session = mgr.create_session(config)
    mgr.connect(session.session_id)
    return mgr, session.session_id


# ── 1. Session lifecycle tests ───────────────────────────────────


def test_fix_create_session_disconnected(mgr: FIXSessionManager) -> None:
    """New session starts in DISCONNECTED state."""
    config = _make_config()
    session = mgr.create_session(config)
    assert session.state == FIXSessionState.DISCONNECTED
    assert session.seq_num_out == 1
    assert session.seq_num_in == 1
    assert session.sender_comp_id == "007_BRIDGE"
    assert session.target_comp_id == "BROKER_A"


def test_fix_connect_transitions_to_logged_on(mgr: FIXSessionManager) -> None:
    """Connect: DISCONNECTED → LOGGED_ON, seq_num_out incremented for Logon."""
    config = _make_config()
    session = mgr.create_session(config)
    result = mgr.connect(session.session_id)
    assert result.state == FIXSessionState.LOGGED_ON
    assert result.seq_num_out == 2  # Logon message sent
    assert result.connected_at is not None
    assert result.last_heartbeat_at is not None


def test_fix_full_lifecycle(mgr: FIXSessionManager) -> None:
    """Full lifecycle: DISCONNECTED → LOGGED_ON → ACTIVE → LOGGED_OUT."""
    config = _make_config()
    session = mgr.create_session(config)

    # Connect
    session = mgr.connect(session.session_id)
    assert session.state == FIXSessionState.LOGGED_ON

    # Send order → transitions to ACTIVE
    order = _make_order()
    mgr.send_new_order(session.session_id, order)
    session = mgr.get_session(session.session_id)
    assert session.state == FIXSessionState.ACTIVE

    # Disconnect
    session = mgr.disconnect(session.session_id)
    assert session.state == FIXSessionState.LOGGED_OUT


def test_fix_disconnect_from_logged_on(connected_session) -> None:
    """Can disconnect directly from LOGGED_ON."""
    mgr, sid = connected_session
    session = mgr.disconnect(sid)
    assert session.state == FIXSessionState.LOGGED_OUT


# ── 2. Sequence number tests ─────────────────────────────────────


def test_fix_seq_num_increments_on_send(connected_session) -> None:
    """seq_num_out increments on each outbound message."""
    mgr, sid = connected_session
    session = mgr.get_session(sid)
    initial_out = session.seq_num_out  # 2 after Logon

    order = _make_order()
    mgr.send_new_order(sid, order)
    assert mgr.get_session(sid).seq_num_out == initial_out + 1

    mgr.heartbeat(sid)
    assert mgr.get_session(sid).seq_num_out == initial_out + 2


def test_fix_seq_num_increments_on_receive(connected_session) -> None:
    """seq_num_in increments on each inbound message."""
    mgr, sid = connected_session
    session = mgr.get_session(sid)
    initial_in = session.seq_num_in  # 1

    report = _make_exec_report()
    mgr.receive_execution_report(sid, report)
    assert mgr.get_session(sid).seq_num_in == initial_in + 1


def test_fix_seq_nums_independent(connected_session) -> None:
    """Outbound and inbound sequence numbers are independent."""
    mgr, sid = connected_session
    order = _make_order()
    mgr.send_new_order(sid, order)
    mgr.send_new_order(sid, _make_order())

    report = _make_exec_report()
    mgr.receive_execution_report(sid, report)

    session = mgr.get_session(sid)
    assert session.seq_num_out == 4  # Logon + 2 orders
    assert session.seq_num_in == 2   # 1 report


# ── 3. NewOrderSingle tests ─────────────────────────────────────


def test_fix_new_order_returns_cl_ord_id(connected_session) -> None:
    """send_new_order returns the cl_ord_id."""
    mgr, sid = connected_session
    order = _make_order()
    cl_ord_id = mgr.send_new_order(sid, order)
    assert cl_ord_id == order.cl_ord_id
    assert cl_ord_id  # non-empty UUID


def test_fix_new_order_transitions_to_active(connected_session) -> None:
    """First order transitions session from LOGGED_ON → ACTIVE."""
    mgr, sid = connected_session
    assert mgr.get_session(sid).state == FIXSessionState.LOGGED_ON

    order = _make_order()
    mgr.send_new_order(sid, order)
    assert mgr.get_session(sid).state == FIXSessionState.ACTIVE


def test_fix_new_order_model_validation() -> None:
    """NewOrderSingle validates side and order_type patterns."""
    order = _make_order()
    assert order.side in ("1", "2")
    assert order.order_type in ("1", "2")
    assert order.quantity > 0

    with pytest.raises(Exception):
        NewOrderSingle(symbol="AAPL", side="3", order_type="1", quantity=100, account="ACC")


# ── 4. ExecutionReport tests ────────────────────────────────────


def test_fix_execution_report_fill(connected_session) -> None:
    """Process a fill ExecutionReport (exec_type=2)."""
    mgr, sid = connected_session
    report = _make_exec_report(exec_type="2", leaves_qty=0, cum_qty=100)
    result = mgr.receive_execution_report(sid, report)
    assert result.exec_type == "2"
    assert result.cum_qty == 100
    assert result.leaves_qty == 0


def test_fix_execution_report_reject(connected_session) -> None:
    """Process a reject ExecutionReport (exec_type=8)."""
    mgr, sid = connected_session
    report = _make_exec_report(exec_type="8", ord_status="8", leaves_qty=0, cum_qty=0, avg_px=0)
    result = mgr.receive_execution_report(sid, report)
    assert result.exec_type == "8"


def test_fix_execution_report_partial_fill(connected_session) -> None:
    """Process a partial fill ExecutionReport (exec_type=1)."""
    mgr, sid = connected_session
    report = _make_exec_report(exec_type="1", leaves_qty=50, cum_qty=50, avg_px=150.25)
    result = mgr.receive_execution_report(sid, report)
    assert result.exec_type == "1"
    assert result.leaves_qty == 50
    assert result.cum_qty == 50


# ── 5. OrderCancelRequest tests ─────────────────────────────────


def test_fix_cancel_order(connected_session) -> None:
    """send_cancel increments seq_num_out and returns cl_ord_id."""
    mgr, sid = connected_session
    initial_out = mgr.get_session(sid).seq_num_out

    cancel = OrderCancelRequest(orig_cl_ord_id="ORD-001", symbol="AAPL", side="1")
    cl_ord_id = mgr.send_cancel(sid, cancel)
    assert cl_ord_id == cancel.cl_ord_id
    assert mgr.get_session(sid).seq_num_out == initial_out + 1


# ── 6. Heartbeat tests ──────────────────────────────────────────


def test_fix_heartbeat_updates_timestamp(connected_session) -> None:
    """Heartbeat updates last_heartbeat_at and increments seq_num_out."""
    mgr, sid = connected_session
    before = mgr.get_session(sid).last_heartbeat_at
    initial_out = mgr.get_session(sid).seq_num_out

    session = mgr.heartbeat(sid)
    assert session.last_heartbeat_at >= before
    assert session.seq_num_out == initial_out + 1


# ── 7. Resend request tests ─────────────────────────────────────


def test_fix_resend_request_transitions_to_resending(connected_session) -> None:
    """request_resend transitions to RESENDING state."""
    mgr, sid = connected_session
    session = mgr.request_resend(sid, begin_seq=1, end_seq=5)
    assert session.state == FIXSessionState.RESENDING


def test_fix_resend_request_infinity(connected_session) -> None:
    """end_seq=0 means request all from begin_seq onward."""
    mgr, sid = connected_session
    session = mgr.request_resend(sid, begin_seq=3, end_seq=0)
    assert session.state == FIXSessionState.RESENDING


# ── 8. Get execution reports ────────────────────────────────────


def test_fix_get_execution_reports_by_cl_ord_id(connected_session) -> None:
    """get_execution_reports returns reports for a specific cl_ord_id."""
    mgr, sid = connected_session
    cl_ord_id = "ORD-TEST-123"

    r1 = _make_exec_report(exec_id="E1", cl_ord_id=cl_ord_id, exec_type="0")
    r2 = _make_exec_report(exec_id="E2", cl_ord_id=cl_ord_id, exec_type="2")
    mgr.receive_execution_report(sid, r1)
    mgr.receive_execution_report(sid, r2)

    reports = mgr.get_execution_reports(sid, cl_ord_id)
    assert len(reports) == 2
    assert reports[0].exec_id == "E1"
    assert reports[1].exec_id == "E2"


def test_fix_get_execution_reports_empty(connected_session) -> None:
    """get_execution_reports returns empty list for unknown cl_ord_id."""
    mgr, sid = connected_session
    reports = mgr.get_execution_reports(sid, "NONEXISTENT")
    assert reports == []



# ── 9. MCP tools list + server info ─────────────────────────────


def _ensure_shared_on_path() -> None:
    """Add _shared to sys.path so mcp_wrapper can import it."""
    shared_dir = _HERE.parent / "m11-mcp-adapters"
    if str(shared_dir) not in sys.path:
        sys.path.insert(0, str(shared_dir))


def _get_mcp_client():
    """Build a TestClient for the MCP server. Returns (client, mcp_module)."""
    _ensure_shared_on_path()
    # Use unique module name to avoid caching issues across tests
    import uuid as _uuid
    mod_name = f"fix_mcp_{_uuid.uuid4().hex[:8]}"
    fix_mcp = _load_module(mod_name, "mcp_wrapper.py")
    server = fix_mcp.create_mcp_server()
    app = server.build_app()

    from fastapi.testclient import TestClient
    return TestClient(app), fix_mcp


def test_fix_mcp_tools_list() -> None:
    """MCP tools/list returns exactly 4 FIX bridge tools, all active (not pending)."""
    client, _ = _get_mcp_client()

    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"fix_submit_order", "fix_cancel_order", "fix_get_session_status", "fix_get_execution_reports"}
    # Tools should be active (not pending_vendor_approval) — dev mode works
    for tool in tools:
        assert tool["status"] == "active"


def test_fix_mcp_server_info() -> None:
    """GET / returns server info with fix-bridge name."""
    client, _ = _get_mcp_client()

    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "fix-bridge"
    assert data["vendor"] == "fix-4.2"
    assert data["status"] == "healthy"


# ── 10. MCP tool handler tests (dev mode) ───────────────────────


def _create_dev_session(fix_mcp_mod) -> str:
    """Create and connect a session via the module-level session manager."""
    mgr = fix_mcp_mod._session_mgr
    config = _make_config()
    session = mgr.create_session(config)
    mgr.connect(session.session_id)
    return session.session_id


def test_fix_submit_order_dev_mode() -> None:
    """Submit order in dev mode — get mock execution report."""
    client, fix_mcp = _get_mcp_client()
    session_id = _create_dev_session(fix_mcp)

    resp = client.post("/tools/call", json={
        "name": "fix_submit_order",
        "arguments": {
            "session_id": session_id,
            "symbol": "AAPL",
            "side": "1",
            "order_type": "2",
            "quantity": 100,
            "price": 150.50,
            "account": "ACC-001",
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "isError" not in data or data.get("isError") is not True
    parsed = json.loads(data["content"][0]["text"])
    assert "cl_ord_id" in parsed
    assert parsed["seq_num_out"] >= 3  # Logon + order
    assert parsed["session_state"] == "ACTIVE"
    assert parsed["_dev_mode"] is True
    assert "execution_report" in parsed
    assert parsed["execution_report"]["exec_type"] == "2"  # Fill
    assert parsed["execution_report"]["symbol"] == "AAPL"


def test_fix_cancel_order_dev_mode() -> None:
    """Cancel order in dev mode — get mock cancel ack."""
    client, fix_mcp = _get_mcp_client()
    session_id = _create_dev_session(fix_mcp)

    resp = client.post("/tools/call", json={
        "name": "fix_cancel_order",
        "arguments": {
            "session_id": session_id,
            "orig_cl_ord_id": "ORD-ORIG-001",
            "symbol": "MSFT",
            "side": "2",
        },
    })
    assert resp.status_code == 200
    data = resp.json()
    assert "isError" not in data or data.get("isError") is not True
    parsed = json.loads(data["content"][0]["text"])
    assert "cl_ord_id" in parsed
    assert parsed["orig_cl_ord_id"] == "ORD-ORIG-001"
    assert parsed["_dev_mode"] is True
    assert "cancel_ack" in parsed
    assert parsed["cancel_ack"]["exec_type"] == "4"  # Canceled


def test_fix_get_session_status() -> None:
    """Get session status — returns state, seq nums, connection info."""
    client, fix_mcp = _get_mcp_client()
    session_id = _create_dev_session(fix_mcp)

    resp = client.post("/tools/call", json={
        "name": "fix_get_session_status",
        "arguments": {"session_id": session_id},
    })
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["session_id"] == session_id
    assert parsed["state"] == "LOGGED_ON"
    assert parsed["sender_comp_id"] == "007_BRIDGE"
    assert parsed["target_comp_id"] == "BROKER_A"
    assert parsed["seq_num_out"] == 2  # After Logon
    assert parsed["seq_num_in"] == 1
    assert parsed["connected_at"] is not None
    assert parsed["last_heartbeat_at"] is not None
    assert parsed["_dev_mode"] is True


def test_fix_get_execution_reports() -> None:
    """Submit order in dev mode, then query execution reports for that cl_ord_id."""
    client, fix_mcp = _get_mcp_client()
    session_id = _create_dev_session(fix_mcp)

    # Submit order first (generates mock exec report in dev mode)
    submit_resp = client.post("/tools/call", json={
        "name": "fix_submit_order",
        "arguments": {
            "session_id": session_id,
            "symbol": "GOOG",
            "side": "1",
            "order_type": "2",
            "quantity": 50,
            "price": 175.00,
            "account": "ACC-002",
        },
    })
    submit_data = json.loads(submit_resp.json()["content"][0]["text"])
    cl_ord_id = submit_data["cl_ord_id"]

    # Now query reports
    resp = client.post("/tools/call", json={
        "name": "fix_get_execution_reports",
        "arguments": {"session_id": session_id, "cl_ord_id": cl_ord_id},
    })
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["cl_ord_id"] == cl_ord_id
    assert parsed["count"] == 1
    assert len(parsed["reports"]) == 1
    assert parsed["reports"][0]["symbol"] == "GOOG"
    assert parsed["reports"][0]["exec_type"] == "2"
    assert parsed["_dev_mode"] is True


def test_fix_submit_order_requires_active_session() -> None:
    """Submit order without connecting session first — returns error."""
    client, fix_mcp = _get_mcp_client()

    # Create session but do NOT connect
    mgr = fix_mcp._session_mgr
    config = _make_config()
    session = mgr.create_session(config)

    resp = client.post("/tools/call", json={
        "name": "fix_submit_order",
        "arguments": {
            "session_id": session.session_id,
            "symbol": "AAPL",
            "side": "1",
            "order_type": "2",
            "quantity": 100,
            "price": 150.50,
            "account": "ACC-001",
        },
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "SESSION_ERROR"


def test_fix_sequence_numbers_increment() -> None:
    """Verify seq nums increment correctly after multiple MCP tool operations."""
    client, fix_mcp = _get_mcp_client()
    session_id = _create_dev_session(fix_mcp)

    # Check initial state: seq_num_out=2 (after Logon)
    resp = client.post("/tools/call", json={
        "name": "fix_get_session_status",
        "arguments": {"session_id": session_id},
    })
    status = json.loads(resp.json()["content"][0]["text"])
    assert status["seq_num_out"] == 2

    # Submit first order: seq_num_out should be 3
    resp = client.post("/tools/call", json={
        "name": "fix_submit_order",
        "arguments": {
            "session_id": session_id,
            "symbol": "AAPL",
            "side": "1",
            "order_type": "1",
            "quantity": 50,
            "account": "ACC-001",
        },
    })
    order1 = json.loads(resp.json()["content"][0]["text"])
    assert order1["seq_num_out"] == 3

    # Submit second order: seq_num_out should be 4
    resp = client.post("/tools/call", json={
        "name": "fix_submit_order",
        "arguments": {
            "session_id": session_id,
            "symbol": "MSFT",
            "side": "2",
            "order_type": "2",
            "quantity": 25,
            "price": 400.00,
            "account": "ACC-001",
        },
    })
    order2 = json.loads(resp.json()["content"][0]["text"])
    assert order2["seq_num_out"] == 4

    # Cancel order: seq_num_out should be 5
    resp = client.post("/tools/call", json={
        "name": "fix_cancel_order",
        "arguments": {
            "session_id": session_id,
            "orig_cl_ord_id": order1["cl_ord_id"],
            "symbol": "AAPL",
            "side": "1",
        },
    })
    cancel = json.loads(resp.json()["content"][0]["text"])
    assert cancel["seq_num_out"] == 5

    # Final status check
    resp = client.post("/tools/call", json={
        "name": "fix_get_session_status",
        "arguments": {"session_id": session_id},
    })
    final = json.loads(resp.json()["content"][0]["text"])
    assert final["seq_num_out"] == 5
    # seq_num_in: 3 mock exec reports (2 orders + 1 cancel ack in dev mode)
    assert final["seq_num_in"] == 4


# ── 11. MCP tool validation errors ──────────────────────────────


def test_fix_submit_order_missing_params() -> None:
    """Submit order with missing required params returns INVALID_PARAMS."""
    client, _ = _get_mcp_client()

    resp = client.post("/tools/call", json={
        "name": "fix_submit_order",
        "arguments": {"session_id": "some-id"},
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_fix_cancel_order_missing_params() -> None:
    """Cancel order with missing required params returns INVALID_PARAMS."""
    client, _ = _get_mcp_client()

    resp = client.post("/tools/call", json={
        "name": "fix_cancel_order",
        "arguments": {"session_id": "some-id"},
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_fix_get_session_status_not_found() -> None:
    """Get status for nonexistent session returns SESSION_NOT_FOUND."""
    client, _ = _get_mcp_client()

    resp = client.post("/tools/call", json={
        "name": "fix_get_session_status",
        "arguments": {"session_id": "nonexistent-session"},
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "SESSION_NOT_FOUND"


def test_fix_get_execution_reports_missing_cl_ord_id() -> None:
    """Get reports without cl_ord_id returns INVALID_PARAMS."""
    client, _ = _get_mcp_client()

    resp = client.post("/tools/call", json={
        "name": "fix_get_execution_reports",
        "arguments": {"session_id": "some-id"},
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


# ── 12. Invalid state error tests ───────────────────────────────


def test_fix_connect_already_connected_raises(connected_session) -> None:
    """Cannot connect a session that is already LOGGED_ON."""
    mgr, sid = connected_session
    with pytest.raises(ValueError, match="expected one of"):
        mgr.connect(sid)


def test_fix_send_order_on_disconnected_raises(mgr: FIXSessionManager) -> None:
    """Cannot send order on DISCONNECTED session."""
    config = _make_config()
    session = mgr.create_session(config)
    order = _make_order()
    with pytest.raises(ValueError, match="expected one of"):
        mgr.send_new_order(session.session_id, order)


def test_fix_disconnect_on_disconnected_raises(mgr: FIXSessionManager) -> None:
    """Cannot disconnect a DISCONNECTED session."""
    config = _make_config()
    session = mgr.create_session(config)
    with pytest.raises(ValueError, match="expected one of"):
        mgr.disconnect(session.session_id)


def test_fix_heartbeat_on_logged_out_raises(connected_session) -> None:
    """Cannot heartbeat a LOGGED_OUT session."""
    mgr, sid = connected_session
    mgr.disconnect(sid)
    with pytest.raises(ValueError, match="expected one of"):
        mgr.heartbeat(sid)


def test_fix_session_not_found_raises(mgr: FIXSessionManager) -> None:
    """Operations on nonexistent session raise ValueError."""
    with pytest.raises(ValueError, match="Session not found"):
        mgr.connect("nonexistent-id")


# ── 13. QuickFIX engine dev mode ────────────────────────────────


def test_fix_engine_dev_mode_noop() -> None:
    """FIXEngine in dev mode is a no-op — start/stop return without error."""
    fix_qf = _load_module("fix_quickfix_engine", "quickfix_engine.py")
    FIXEngine = fix_qf.FIXEngine

    mgr = FIXSessionManager()
    engine = FIXEngine(mgr)

    # start returns None in dev mode
    result = engine.start(_make_config())
    assert result is None
    assert engine.is_running is False

    # stop is also a no-op
    engine.stop()
    assert engine.is_running is False


def test_fix_engine_dev_mode_callbacks_noop() -> None:
    """QuickFIX Application callbacks are no-ops in dev mode."""
    fix_qf = _load_module("fix_quickfix_engine2", "quickfix_engine.py")
    FIXEngine = fix_qf.FIXEngine

    mgr = FIXSessionManager()
    engine = FIXEngine(mgr)

    # All callbacks should execute without error in dev mode
    engine.onCreate("FIX.4.2:SENDER->TARGET")
    engine.onLogon("FIX.4.2:SENDER->TARGET")
    engine.onLogout("FIX.4.2:SENDER->TARGET")
    engine.toAdmin(None, "FIX.4.2:SENDER->TARGET")
    engine.fromAdmin(None, "FIX.4.2:SENDER->TARGET")
    engine.toApp(None, "FIX.4.2:SENDER->TARGET")
    engine.fromApp(None, "FIX.4.2:SENDER->TARGET")
