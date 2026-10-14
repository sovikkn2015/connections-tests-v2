"""
Execution Specialist — Trade order lifecycle state machine.

STRICT state transitions — invalid ones raise ValueError.
HITL MANDATORY — cannot submit without approval.
Approval token = SHA-256(order_id + approver_id + timestamp).
24-hour timeout on PENDING_APPROVAL → auto-cancel.
T+1 settlement: settlement_date_expected = trade_date + 1 business day.

No cross-module imports. M2/M4 checks via REST (not imported).
All compliance decisions deterministic — no LLM.

Backends:
  In-memory (default) for dev/test.
  DynamoDB for production (EXEC_STORE_BACKEND=dynamodb).
"""

import hashlib
import logging
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

try:
    from .models import (
        ComplianceCheckResult,
        ExecutionOrder,
        HITLApproval,
        OrderRequest,
        OrderState,
        SettlementStatus,
    )
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _models_path = _pathlib.Path(__file__).parent / "models.py"
    _spec = importlib.util.spec_from_file_location("execution_models_local", _models_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ComplianceCheckResult = _mod.ComplianceCheckResult
    ExecutionOrder = _mod.ExecutionOrder
    HITLApproval = _mod.HITLApproval
    OrderRequest = _mod.OrderRequest
    OrderState = _mod.OrderState
    SettlementStatus = _mod.SettlementStatus

logger = logging.getLogger("execution_specialist.state_machine")

# 24-hour timeout for PENDING_APPROVAL
APPROVAL_TIMEOUT_HOURS = 24

# Valid state transitions — strict enforcement
VALID_TRANSITIONS: dict[OrderState, list[OrderState]] = {
    OrderState.DRAFT: [OrderState.COMPLIANCE_CHECK, OrderState.CANCELLED],
    OrderState.COMPLIANCE_CHECK: [OrderState.PENDING_APPROVAL, OrderState.CANCELLED],
    OrderState.PENDING_APPROVAL: [OrderState.APPROVED, OrderState.CANCELLED, OrderState.TIMED_OUT],
    OrderState.APPROVED: [OrderState.SUBMITTED, OrderState.CANCELLED],
    OrderState.SUBMITTED: [OrderState.CONFIRMED, OrderState.CANCELLED],
    OrderState.CONFIRMED: [OrderState.PENDING_SETTLEMENT],
    OrderState.PENDING_SETTLEMENT: [OrderState.SETTLED, OrderState.SETTLEMENT_FAILED],
    OrderState.SETTLEMENT_FAILED: [OrderState.ESCALATED],
    # Terminal states — no transitions out
    OrderState.SETTLED: [],
    OrderState.ESCALATED: [],
    OrderState.CANCELLED: [],
    OrderState.TIMED_OUT: [],
}


# ── Order Store Backends ─────────────────────────────────────────


class InMemoryOrderStore:
    """In-memory order store. Default for dev/test."""

    def __init__(self) -> None:
        self._orders: dict[str, ExecutionOrder] = {}

    def put(self, order: ExecutionOrder) -> None:
        self._orders[order.order_id] = order

    def get(self, order_id: str) -> Optional[ExecutionOrder]:
        return self._orders.get(order_id)

    def query_by_client(self, client_id: str) -> list[ExecutionOrder]:
        return [o for o in self._orders.values() if o.client_id == client_id]


class DynamoDBOrderStore:
    """
    DynamoDB-backed order store for production.

    Activated when EXEC_STORE_BACKEND=dynamodb and EXEC_DYNAMODB_TABLE is set.
    Uses boto3 DynamoDB (put_item, get_item, query).
    Credentials from IAM role / env (Rule 20). No credentials in code.

    Falls back to in-memory on connection failure.
    """

    def __init__(self, table_name: str, dynamodb_client: Any = None) -> None:
        self._table_name = table_name
        if dynamodb_client is not None:
            self._client = dynamodb_client
        else:
            try:
                import boto3
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for DynamoDB order store. "
                    "Install with: pip install boto3"
                )
            self._client = boto3.resource("dynamodb").Table(table_name)
        self._fallback: InMemoryOrderStore | None = None
        logger.info("DynamoDBOrderStore initialized: table=%s", table_name)

    def _get_fallback(self) -> InMemoryOrderStore:
        if self._fallback is None:
            self._fallback = InMemoryOrderStore()
            logger.warning("DynamoDBOrderStore: activated in-memory fallback")
        return self._fallback

    def put(self, order: ExecutionOrder) -> None:
        try:
            self._client.put_item(Item={
                "order_id": order.order_id,
                "client_id": order.client_id,
                "order_json": order.model_dump_json(),
            })
        except Exception as exc:
            logger.error("DynamoDB put_item failed: %s. Using fallback.", exc)
            self._get_fallback().put(order)

    def get(self, order_id: str) -> Optional[ExecutionOrder]:
        try:
            resp = self._client.get_item(Key={"order_id": order_id})
            item = resp.get("Item")
            if item is None:
                if self._fallback:
                    return self._fallback.get(order_id)
                return None
            return ExecutionOrder.model_validate_json(item["order_json"])
        except Exception as exc:
            logger.error("DynamoDB get_item failed: %s. Using fallback.", exc)
            return self._get_fallback().get(order_id)

    def query_by_client(self, client_id: str) -> list[ExecutionOrder]:
        try:
            resp = self._client.query(
                IndexName="client_id-index",
                KeyConditionExpression="client_id = :cid",
                ExpressionAttributeValues={":cid": client_id},
            )
            return [
                ExecutionOrder.model_validate_json(item["order_json"])
                for item in resp.get("Items", [])
            ]
        except Exception as exc:
            logger.error("DynamoDB query failed: %s. Using fallback.", exc)
            return self._get_fallback().query_by_client(client_id)


def create_order_store() -> InMemoryOrderStore | DynamoDBOrderStore:
    """
    Factory: select order store backend based on env var.

    EXEC_STORE_BACKEND: "memory" (default) or "dynamodb"
    EXEC_DYNAMODB_TABLE: DynamoDB table name (required for dynamodb)
    """
    backend = os.environ.get("EXEC_STORE_BACKEND", "memory").lower()
    if backend == "dynamodb":
        table_name = os.environ.get("EXEC_DYNAMODB_TABLE")
        if not table_name:
            logger.warning(
                "EXEC_STORE_BACKEND=dynamodb but EXEC_DYNAMODB_TABLE not set. "
                "Falling back to in-memory order store."
            )
            return InMemoryOrderStore()
        try:
            store = DynamoDBOrderStore(table_name=table_name)
            logger.info("Execution order store backend: dynamodb (table=%s)", table_name)
            return store
        except Exception as exc:
            logger.error(
                "Failed to initialize DynamoDB order store: %s. "
                "Falling back to in-memory.",
                exc,
            )
            return InMemoryOrderStore()
    logger.info("Execution order store backend: memory")
    return InMemoryOrderStore()


def _next_business_day(from_date: date) -> date:
    """Calculate T+1 settlement date (next business day, skipping weekends)."""
    next_day = from_date + timedelta(days=1)
    # Skip Saturday (5) and Sunday (6)
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    return next_day


class ExecutionStateMachine:
    """
    Trade order lifecycle state machine with mandatory HITL.

    In-memory store for dev/test. DynamoDB for production.
    Backend selected via EXEC_STORE_BACKEND env var (default: memory).
    No cross-module imports — M2/M4 compliance checks arrive as data.
    """

    def __init__(self, store: InMemoryOrderStore | DynamoDBOrderStore | None = None) -> None:
        self._store = store or InMemoryOrderStore()

    @property
    def _orders(self) -> "dict[str, ExecutionOrder]":
        """Backward-compatible access to underlying store dict (for tests)."""
        if isinstance(self._store, InMemoryOrderStore):
            return self._store._orders
        raise AttributeError("_orders not available on non-memory backends")

    def _validate_transition(self, order: ExecutionOrder, target: OrderState) -> None:
        """Validate state transition. Raises ValueError if invalid."""
        allowed = VALID_TRANSITIONS.get(order.state, [])
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {order.state.value} → {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

    def _update_order(self, order: ExecutionOrder, **kwargs) -> ExecutionOrder:
        """Update order fields and persist."""
        now = datetime.now(timezone.utc).isoformat()
        updated = order.model_copy(update={**kwargs, "updated_at": now})
        self._store.put(updated)
        return updated

    # ── Create ───────────────────────────────────────────────────

    def create_order(self, request: OrderRequest) -> ExecutionOrder:
        """Create a new order in DRAFT state."""
        order = ExecutionOrder(
            client_id=request.client_id,
            account_id=request.account_id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            order_type=request.order_type,
            limit_price=request.limit_price,
            requestor_id=request.requestor_id,
            state=OrderState.DRAFT,
        )
        self._store.put(order)
        logger.info("Order created: %s for client %s", order.order_id, order.client_id)
        return order

    # ── Compliance ───────────────────────────────────────────────

    def run_compliance_checks(
        self, order_id: str, checks: list[ComplianceCheckResult]
    ) -> ExecutionOrder:
        """
        Run compliance checks on an order. Transitions DRAFT → COMPLIANCE_CHECK.
        If any check is DENY, transitions to CANCELLED.
        If all pass, transitions to PENDING_APPROVAL.
        """
        order = self._get_order_or_raise(order_id)
        self._validate_transition(order, OrderState.COMPLIANCE_CHECK)

        order = self._update_order(order, state=OrderState.COMPLIANCE_CHECK, compliance_checks=checks)

        # Check for DENY — deterministic, no LLM
        denied = [c for c in checks if c.result == "DENY"]
        if denied:
            self._validate_transition(order, OrderState.CANCELLED)
            order = self._update_order(order, state=OrderState.CANCELLED)
            logger.info("Order %s CANCELLED — compliance DENY: %s", order_id, denied[0].reason)
            return order

        # All passed — move to PENDING_APPROVAL (HITL mandatory)
        self._validate_transition(order, OrderState.PENDING_APPROVAL)
        now = datetime.now(timezone.utc).isoformat()
        order = self._update_order(
            order, state=OrderState.PENDING_APPROVAL, pending_approval_at=now
        )
        logger.info("Order %s awaiting HITL approval", order_id)
        return order

    # ── HITL Approval ────────────────────────────────────────────

    @staticmethod
    def generate_approval_token(order_id: str, approver_id: str, timestamp: str) -> str:
        """Generate SHA-256 approval token: SHA-256(order_id + approver_id + timestamp)."""
        payload = f"{order_id}{approver_id}{timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def approve_order(self, order_id: str, approver_id: str) -> ExecutionOrder:
        """
        Approve an order (HITL). Generates SHA-256 token.
        PENDING_APPROVAL → APPROVED.
        """
        order = self._get_order_or_raise(order_id)
        self._validate_transition(order, OrderState.APPROVED)

        now = datetime.now(timezone.utc).isoformat()
        token = self.generate_approval_token(order_id, approver_id, now)

        approval = HITLApproval(
            approver_id=approver_id,
            approval_token=token,
            approved_at=now,
        )
        order = self._update_order(order, state=OrderState.APPROVED, hitl_approval=approval)
        logger.info("Order %s APPROVED by %s", order_id, approver_id)
        return order

    def reject_order(self, order_id: str, approver_id: str) -> ExecutionOrder:
        """Reject an order (HITL). PENDING_APPROVAL → CANCELLED."""
        order = self._get_order_or_raise(order_id)
        self._validate_transition(order, OrderState.CANCELLED)
        order = self._update_order(order, state=OrderState.CANCELLED)
        logger.info("Order %s REJECTED by %s → CANCELLED", order_id, approver_id)
        return order

    # ── Submit / Confirm ─────────────────────────────────────────

    def submit_order(self, order_id: str) -> ExecutionOrder:
        """
        Submit order for execution. APPROVED → SUBMITTED.
        HITL MANDATORY — cannot submit without approval.
        """
        order = self._get_order_or_raise(order_id)

        # HITL mandatory check
        if order.hitl_approval is None:
            raise ValueError(
                f"Cannot submit order {order_id}: HITL approval is MANDATORY. "
                f"Current state: {order.state.value}"
            )

        self._validate_transition(order, OrderState.SUBMITTED)
        now = datetime.now(timezone.utc).isoformat()
        order = self._update_order(order, state=OrderState.SUBMITTED, submitted_at=now)
        logger.info("Order %s SUBMITTED", order_id)
        return order

    def confirm_order(self, order_id: str) -> ExecutionOrder:
        """
        Confirm execution. SUBMITTED → CONFIRMED → PENDING_SETTLEMENT.
        Sets T+1 settlement date.
        """
        order = self._get_order_or_raise(order_id)
        self._validate_transition(order, OrderState.CONFIRMED)

        now = datetime.now(timezone.utc)
        trade_date = now.date()
        settlement_expected = _next_business_day(trade_date)

        settlement = SettlementStatus(settlement_date_expected=settlement_expected)

        order = self._update_order(
            order,
            state=OrderState.CONFIRMED,
            confirmed_at=now.isoformat(),
            settlement=settlement,
        )

        # Auto-transition to PENDING_SETTLEMENT
        self._validate_transition(order, OrderState.PENDING_SETTLEMENT)
        order = self._update_order(order, state=OrderState.PENDING_SETTLEMENT)
        logger.info("Order %s CONFIRMED, settlement expected %s", order_id, settlement_expected)
        return order

    # ── Settlement ───────────────────────────────────────────────

    def settle_order(self, order_id: str) -> ExecutionOrder:
        """Settle order. PENDING_SETTLEMENT → SETTLED."""
        order = self._get_order_or_raise(order_id)
        self._validate_transition(order, OrderState.SETTLED)

        settlement = order.settlement
        if settlement:
            settlement = settlement.model_copy(update={
                "settled": True,
                "settlement_date_actual": date.today(),
            })

        order = self._update_order(order, state=OrderState.SETTLED, settlement=settlement)
        logger.info("Order %s SETTLED", order_id)
        return order

    def fail_settlement(self, order_id: str, reason: str) -> ExecutionOrder:
        """
        Settlement failure. PENDING_SETTLEMENT → SETTLEMENT_FAILED → ESCALATED.
        """
        order = self._get_order_or_raise(order_id)
        self._validate_transition(order, OrderState.SETTLEMENT_FAILED)

        settlement = order.settlement
        if settlement:
            settlement = settlement.model_copy(update={"failure_reason": reason})

        order = self._update_order(
            order, state=OrderState.SETTLEMENT_FAILED, settlement=settlement
        )

        # Auto-escalate
        self._validate_transition(order, OrderState.ESCALATED)
        order = self._update_order(order, state=OrderState.ESCALATED)
        logger.info("Order %s SETTLEMENT_FAILED → ESCALATED: %s", order_id, reason)
        return order

    # ── Timeout ──────────────────────────────────────────────────

    def check_timeout(self, order_id: str) -> ExecutionOrder:
        """
        Check 24-hour timeout on PENDING_APPROVAL.
        If expired, transitions to TIMED_OUT.
        """
        order = self._get_order_or_raise(order_id)

        if order.state != OrderState.PENDING_APPROVAL:
            return order

        if not order.pending_approval_at:
            return order

        pending_since = datetime.fromisoformat(order.pending_approval_at)
        if pending_since.tzinfo is None:
            pending_since = pending_since.replace(tzinfo=timezone.utc)

        deadline = pending_since + timedelta(hours=APPROVAL_TIMEOUT_HOURS)
        now = datetime.now(timezone.utc)

        if now > deadline:
            self._validate_transition(order, OrderState.TIMED_OUT)
            order = self._update_order(order, state=OrderState.TIMED_OUT)
            logger.warning("Order %s TIMED_OUT after %dh", order_id, APPROVAL_TIMEOUT_HOURS)

        return order

    # ── Queries ──────────────────────────────────────────────────

    def get_order(self, order_id: str) -> Optional[ExecutionOrder]:
        """Get order by ID. Returns None if not found."""
        return self._store.get(order_id)

    def get_orders_by_client(self, client_id: str) -> list[ExecutionOrder]:
        """Get all orders for a client."""
        return self._store.query_by_client(client_id)

    # ── Internal ─────────────────────────────────────────────────

    def _get_order_or_raise(self, order_id: str) -> ExecutionOrder:
        """Get order or raise ValueError."""
        order = self._store.get(order_id)
        if order is None:
            raise ValueError(f"Order not found: {order_id}")
        return order
