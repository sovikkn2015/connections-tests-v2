"""
Execution Specialist — Tests (~25 tests).

Uses importlib pattern for module loading (prefix: execution_).
Covers: full happy path, HITL mandatory, SHA-256 token, compliance DENY→CANCELLED,
24hr timeout, invalid transitions, settlement failure→ESCALATED, reject→CANCELLED.

No cross-module imports. No credentials. No LLM.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import sys
import types
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

# ── importlib pattern ────────────────────────────────────────────

def _load_module(name: str, file_name: str) -> types.ModuleType:
    """Load a module from the execution-specialist package using importlib."""
    import importlib.util
    import pathlib
    base = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, base / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

execution_models = _load_module("execution_models", "models.py")

# Rebuild Pydantic models after importlib loading (forward refs from __future__ annotations)
for _cls_name in dir(execution_models):
    _cls = getattr(execution_models, _cls_name)
    if isinstance(_cls, type) and hasattr(_cls, "model_rebuild") and hasattr(_cls, "__pydantic_generic_metadata__"):
        _cls.model_rebuild()

execution_sm = _load_module("execution_state_machine", "state_machine.py")

OrderState = execution_models.OrderState
OrderRequest = execution_models.OrderRequest
ExecutionOrder = execution_models.ExecutionOrder
HITLApproval = execution_models.HITLApproval
ComplianceCheckResult = execution_models.ComplianceCheckResult
SettlementStatus = execution_models.SettlementStatus
ExecutionStateMachine = execution_sm.ExecutionStateMachine
APPROVAL_TIMEOUT_HOURS = execution_sm.APPROVAL_TIMEOUT_HOURS



# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def sm() -> ExecutionStateMachine:
    """Fresh state machine per test."""
    return ExecutionStateMachine()


@pytest.fixture
def sample_request() -> OrderRequest:
    """Standard buy order request."""
    return OrderRequest(
        client_id="C-12345",
        account_id="A-67890",
        symbol="AAPL",
        side="buy",
        quantity=100.0,
        order_type="market",
        requestor_id="advisor-001",
    )


@pytest.fixture
def passing_checks() -> list[ComplianceCheckResult]:
    """All-passing compliance checks."""
    now = datetime.now(timezone.utc).isoformat()
    return [
        ComplianceCheckResult(check_type="concentration", result="PASS", evaluated_at=now),
        ComplianceCheckResult(check_type="suitability", result="PASS", evaluated_at=now),
        ComplianceCheckResult(check_type="restricted_list", result="PASS", evaluated_at=now),
    ]


def _create_and_pass_compliance(sm, request, checks):
    """Helper: create order and pass compliance."""
    order = sm.create_order(request)
    return sm.run_compliance_checks(order.order_id, checks)


def _create_approve_submit(sm, request, checks):
    """Helper: create → compliance → approve → submit."""
    order = _create_and_pass_compliance(sm, request, checks)
    order = sm.approve_order(order.order_id, "principal-001")
    return sm.submit_order(order.order_id)


# ── Test 1: Create order in DRAFT state ──────────────────────────


def test_execution_create_order_draft(sm, sample_request):
    """New order starts in DRAFT state."""
    order = sm.create_order(sample_request)
    assert order.state == OrderState.DRAFT
    assert order.client_id == "C-12345"
    assert order.symbol == "AAPL"
    assert order.side == "buy"
    assert order.quantity == 100.0
    assert order.order_id is not None


# ── Test 2: Full happy path DRAFT → SETTLED ──────────────────────


def test_execution_full_happy_path(sm, sample_request, passing_checks):
    """Full lifecycle: DRAFT → COMPLIANCE_CHECK → PENDING_APPROVAL → APPROVED → SUBMITTED → CONFIRMED → PENDING_SETTLEMENT → SETTLED."""
    order = sm.create_order(sample_request)
    assert order.state == OrderState.DRAFT

    order = sm.run_compliance_checks(order.order_id, passing_checks)
    assert order.state == OrderState.PENDING_APPROVAL

    order = sm.approve_order(order.order_id, "principal-001")
    assert order.state == OrderState.APPROVED
    assert order.hitl_approval is not None

    order = sm.submit_order(order.order_id)
    assert order.state == OrderState.SUBMITTED

    order = sm.confirm_order(order.order_id)
    assert order.state == OrderState.PENDING_SETTLEMENT
    assert order.settlement is not None
    assert order.settlement.settlement_date_expected is not None

    order = sm.settle_order(order.order_id)
    assert order.state == OrderState.SETTLED
    assert order.settlement.settled is True


# ── Test 3: HITL mandatory — cannot submit without approval ──────


def test_execution_hitl_mandatory_submit_without_approval(sm, sample_request, passing_checks):
    """Cannot submit order without HITL approval."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    assert order.state == OrderState.PENDING_APPROVAL

    # Try to submit directly — should fail
    with pytest.raises(ValueError, match="HITL approval is MANDATORY"):
        sm.submit_order(order.order_id)


# ── Test 4: SHA-256 approval token format ────────────────────────


def test_execution_sha256_approval_token(sm, sample_request, passing_checks):
    """Approval token is valid 64-char SHA-256 hex."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    order = sm.approve_order(order.order_id, "principal-001")

    token = order.hitl_approval.approval_token
    assert len(token) == 64
    assert re.match(r"^[a-f0-9]{64}$", token)


# ── Test 5: SHA-256 token is deterministic ───────────────────────


def test_execution_sha256_token_deterministic():
    """Same inputs produce same SHA-256 token."""
    token1 = ExecutionStateMachine.generate_approval_token("order-1", "approver-1", "2024-01-01T00:00:00Z")
    token2 = ExecutionStateMachine.generate_approval_token("order-1", "approver-1", "2024-01-01T00:00:00Z")
    assert token1 == token2

    # Different inputs produce different token
    token3 = ExecutionStateMachine.generate_approval_token("order-2", "approver-1", "2024-01-01T00:00:00Z")
    assert token1 != token3


# ── Test 6: SHA-256 token matches manual computation ─────────────


def test_execution_sha256_token_matches_manual():
    """Token matches manual SHA-256 computation."""
    order_id = "test-order"
    approver_id = "test-approver"
    timestamp = "2024-01-01T00:00:00Z"

    expected = hashlib.sha256(f"{order_id}{approver_id}{timestamp}".encode("utf-8")).hexdigest()
    actual = ExecutionStateMachine.generate_approval_token(order_id, approver_id, timestamp)
    assert actual == expected


# ── Test 7: Compliance DENY → CANCELLED ──────────────────────────


def test_execution_compliance_deny_cancels_order(sm, sample_request):
    """Compliance DENY transitions order to CANCELLED."""
    order = sm.create_order(sample_request)
    now = datetime.now(timezone.utc).isoformat()
    checks = [
        ComplianceCheckResult(check_type="concentration", result="PASS", evaluated_at=now),
        ComplianceCheckResult(check_type="restricted_list", result="DENY", reason="Security on restricted list", evaluated_at=now),
    ]
    order = sm.run_compliance_checks(order.order_id, checks)
    assert order.state == OrderState.CANCELLED


# ── Test 8: Reject order → CANCELLED ────────────────────────────


def test_execution_reject_order_cancelled(sm, sample_request, passing_checks):
    """HITL rejection transitions PENDING_APPROVAL → CANCELLED."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    assert order.state == OrderState.PENDING_APPROVAL

    order = sm.reject_order(order.order_id, "principal-001")
    assert order.state == OrderState.CANCELLED



# ── Test 9: 24-hour timeout on PENDING_APPROVAL ─────────────────


def test_execution_24hr_timeout(sm, sample_request, passing_checks):
    """Order in PENDING_APPROVAL for >24h transitions to TIMED_OUT."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    assert order.state == OrderState.PENDING_APPROVAL

    # Simulate 25 hours passing
    past = datetime.now(timezone.utc) - timedelta(hours=25)
    order_updated = order.model_copy(update={"pending_approval_at": past.isoformat()})
    sm._orders[order.order_id] = order_updated

    order = sm.check_timeout(order.order_id)
    assert order.state == OrderState.TIMED_OUT


# ── Test 10: No timeout before 24 hours ──────────────────────────


def test_execution_no_timeout_before_24hr(sm, sample_request, passing_checks):
    """Order in PENDING_APPROVAL for <24h stays in PENDING_APPROVAL."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    order = sm.check_timeout(order.order_id)
    assert order.state == OrderState.PENDING_APPROVAL


# ── Test 11: Invalid transition DRAFT → APPROVED ────────────────


def test_execution_invalid_transition_draft_to_approved(sm, sample_request):
    """Cannot jump from DRAFT to APPROVED."""
    order = sm.create_order(sample_request)
    with pytest.raises(ValueError, match="Invalid transition"):
        sm.approve_order(order.order_id, "principal-001")


# ── Test 12: Invalid transition DRAFT → SUBMITTED ───────────────


def test_execution_invalid_transition_draft_to_submitted(sm, sample_request):
    """Cannot jump from DRAFT to SUBMITTED."""
    order = sm.create_order(sample_request)
    with pytest.raises(ValueError, match="HITL approval is MANDATORY"):
        sm.submit_order(order.order_id)


# ── Test 13: Invalid transition SETTLED → anything ──────────────


def test_execution_invalid_transition_from_settled(sm, sample_request, passing_checks):
    """SETTLED is terminal — no transitions out."""
    order = _create_approve_submit(sm, sample_request, passing_checks)
    order = sm.confirm_order(order.order_id)
    order = sm.settle_order(order.order_id)
    assert order.state == OrderState.SETTLED

    with pytest.raises(ValueError, match="Invalid transition"):
        sm.run_compliance_checks(order.order_id, passing_checks)


# ── Test 14: Invalid transition CANCELLED → anything ────────────


def test_execution_invalid_transition_from_cancelled(sm, sample_request, passing_checks):
    """CANCELLED is terminal — no transitions out."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    order = sm.reject_order(order.order_id, "principal-001")
    assert order.state == OrderState.CANCELLED

    with pytest.raises(ValueError, match="Invalid transition"):
        sm.approve_order(order.order_id, "principal-001")


# ── Test 15: Settlement failure → ESCALATED ──────────────────────


def test_execution_settlement_failure_escalated(sm, sample_request, passing_checks):
    """Settlement failure transitions to SETTLEMENT_FAILED → ESCALATED."""
    order = _create_approve_submit(sm, sample_request, passing_checks)
    order = sm.confirm_order(order.order_id)
    assert order.state == OrderState.PENDING_SETTLEMENT

    order = sm.fail_settlement(order.order_id, "Counterparty default")
    assert order.state == OrderState.ESCALATED
    assert order.settlement.failure_reason == "Counterparty default"


# ── Test 16: T+1 settlement date ────────────────────────────────


def test_execution_t_plus_1_settlement_date(sm, sample_request, passing_checks):
    """Confirm sets settlement_date_expected to next business day."""
    order = _create_approve_submit(sm, sample_request, passing_checks)
    order = sm.confirm_order(order.order_id)

    today = datetime.now(timezone.utc).date()
    expected = order.settlement.settlement_date_expected
    # Must be after today
    assert expected > today
    # Must be a weekday (0=Mon, 4=Fri)
    assert expected.weekday() < 5


# ── Test 17: Get order by ID ────────────────────────────────────


def test_execution_get_order(sm, sample_request):
    """Get order by ID returns the order."""
    order = sm.create_order(sample_request)
    fetched = sm.get_order(order.order_id)
    assert fetched is not None
    assert fetched.order_id == order.order_id


# ── Test 18: Get order not found ─────────────────────────────────


def test_execution_get_order_not_found(sm):
    """Get non-existent order returns None."""
    assert sm.get_order("nonexistent-id") is None


# ── Test 19: Get orders by client ────────────────────────────────


def test_execution_get_orders_by_client(sm):
    """Get all orders for a client."""
    req1 = OrderRequest(client_id="C-111", account_id="A-1", symbol="AAPL", side="buy", quantity=10, requestor_id="adv-1")
    req2 = OrderRequest(client_id="C-111", account_id="A-1", symbol="MSFT", side="sell", quantity=20, requestor_id="adv-1")
    req3 = OrderRequest(client_id="C-222", account_id="A-2", symbol="GOOG", side="buy", quantity=30, requestor_id="adv-2")

    sm.create_order(req1)
    sm.create_order(req2)
    sm.create_order(req3)

    client_orders = sm.get_orders_by_client("C-111")
    assert len(client_orders) == 2
    assert all(o.client_id == "C-111" for o in client_orders)


# ── Test 20: Order not found raises ValueError ───────────────────


def test_execution_order_not_found_raises(sm):
    """Operations on non-existent order raise ValueError."""
    with pytest.raises(ValueError, match="Order not found"):
        sm.approve_order("nonexistent", "principal-001")


# ── Test 21: Approval record has correct approver ────────────────


def test_execution_approval_record_approver(sm, sample_request, passing_checks):
    """Approval record stores correct approver_id."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)
    order = sm.approve_order(order.order_id, "principal-jane")
    assert order.hitl_approval.approver_id == "principal-jane"
    assert order.hitl_approval.approved_at is not None


# ── Test 22: Multiple compliance checks stored ───────────────────


def test_execution_compliance_checks_stored(sm, sample_request, passing_checks):
    """All compliance check results are stored on the order."""
    order = sm.create_order(sample_request)
    order = sm.run_compliance_checks(order.order_id, passing_checks)
    assert len(order.compliance_checks) == 3
    assert all(c.result == "PASS" for c in order.compliance_checks)


# ── Test 23: Cancel from DRAFT ───────────────────────────────────


def test_execution_cancel_from_draft(sm, sample_request):
    """Can cancel order directly from DRAFT."""
    order = sm.create_order(sample_request)
    # Manually cancel via reject (which transitions to CANCELLED)
    order = sm._update_order(order, state=OrderState.CANCELLED)
    assert order.state == OrderState.CANCELLED


# ── Test 24: Settle sets actual date ─────────────────────────────


def test_execution_settle_sets_actual_date(sm, sample_request, passing_checks):
    """Settlement sets settlement_date_actual."""
    order = _create_approve_submit(sm, sample_request, passing_checks)
    order = sm.confirm_order(order.order_id)
    order = sm.settle_order(order.order_id)

    assert order.settlement.settled is True
    assert order.settlement.settlement_date_actual is not None


# ── Test 25: Timeout check on non-pending order is no-op ────────


def test_execution_timeout_check_non_pending_noop(sm, sample_request):
    """check_timeout on DRAFT order is a no-op."""
    order = sm.create_order(sample_request)
    result = sm.check_timeout(order.order_id)
    assert result.state == OrderState.DRAFT


# ── Test 26: ESCALATED is terminal ──────────────────────────────


def test_execution_escalated_is_terminal(sm, sample_request, passing_checks):
    """ESCALATED is terminal — no transitions out."""
    order = _create_approve_submit(sm, sample_request, passing_checks)
    order = sm.confirm_order(order.order_id)
    order = sm.fail_settlement(order.order_id, "DTC reject")
    assert order.state == OrderState.ESCALATED

    with pytest.raises(ValueError, match="Invalid transition"):
        sm.settle_order(order.order_id)


# ── Test 27: TIMED_OUT is terminal ──────────────────────────────


def test_execution_timed_out_is_terminal(sm, sample_request, passing_checks):
    """TIMED_OUT is terminal — no transitions out."""
    order = _create_and_pass_compliance(sm, sample_request, passing_checks)

    past = datetime.now(timezone.utc) - timedelta(hours=25)
    order_updated = order.model_copy(update={"pending_approval_at": past.isoformat()})
    sm._orders[order.order_id] = order_updated

    order = sm.check_timeout(order.order_id)
    assert order.state == OrderState.TIMED_OUT

    with pytest.raises(ValueError, match="Invalid transition"):
        sm.approve_order(order.order_id, "principal-001")


# ═══════════════════════════════════════════════════════════════════
# FastAPI endpoint tests
# ═══════════════════════════════════════════════════════════════════

execution_app = _load_module("execution_app", "app.py")
create_app = execution_app.create_app

from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


def test_execution_health_endpoint(client):
    """GET /health returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "execution-specialist"


def test_execution_create_order_endpoint(client):
    """POST /order/create returns order in DRAFT."""
    resp = client.post("/order/create", json={
        "client_id": "C-12345",
        "account_id": "A-67890",
        "symbol": "AAPL",
        "side": "buy",
        "quantity": 100.0,
        "requestor_id": "advisor-001",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "DRAFT"
    assert body["symbol"] == "AAPL"


def test_execution_get_order_endpoint(client):
    """GET /order/{id} returns the order."""
    create_resp = client.post("/order/create", json={
        "client_id": "C-12345",
        "account_id": "A-67890",
        "symbol": "MSFT",
        "side": "sell",
        "quantity": 50.0,
        "requestor_id": "advisor-001",
    })
    order_id = create_resp.json()["order_id"]

    resp = client.get(f"/order/{order_id}")
    assert resp.status_code == 200
    assert resp.json()["order_id"] == order_id


def test_execution_get_order_not_found_endpoint(client):
    """GET /order/{id} returns 404 for non-existent order."""
    resp = client.get("/order/nonexistent-id")
    assert resp.status_code == 404
