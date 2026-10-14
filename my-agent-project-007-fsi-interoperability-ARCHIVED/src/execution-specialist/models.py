"""
Execution Specialist — Pydantic v2 models for trade order lifecycle.

OrderState enum tracks the full lifecycle: DRAFT → COMPLIANCE_CHECK →
PENDING_APPROVAL → APPROVED → SUBMITTED → CONFIRMED → PENDING_SETTLEMENT →
SETTLED. With failure paths: SETTLEMENT_FAILED → ESCALATED, CANCELLED, TIMED_OUT.

HITL mandatory — approval token = SHA-256(order_id + approver_id + timestamp).
T+1 settlement: settlement_date_expected = trade_date + 1 business day.

No cross-module imports. No credentials. No LLM for compliance.
"""

import uuid
from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


# ── Enums ────────────────────────────────────────────────────────


class OrderState(str, Enum):
    """Trade order lifecycle states per Execution Specialist state machine."""

    DRAFT = "DRAFT"
    COMPLIANCE_CHECK = "COMPLIANCE_CHECK"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    SUBMITTED = "SUBMITTED"
    CONFIRMED = "CONFIRMED"
    PENDING_SETTLEMENT = "PENDING_SETTLEMENT"
    SETTLED = "SETTLED"
    SETTLEMENT_FAILED = "SETTLEMENT_FAILED"
    ESCALATED = "ESCALATED"
    CANCELLED = "CANCELLED"
    TIMED_OUT = "TIMED_OUT"


# ── Request / Response Models ────────────────────────────────────


class OrderRequest(BaseModel):
    """Request to create a new trade order."""

    client_id: str = Field(..., min_length=1, description="Canonical Client ID")
    account_id: str = Field(..., min_length=1, description="Canonical Account ID")
    symbol: str = Field(..., min_length=1, description="Security symbol (e.g. AAPL)")
    side: str = Field(..., pattern=r"^(buy|sell)$", description="Trade side: buy or sell")
    quantity: float = Field(..., gt=0, description="Number of shares/units")
    order_type: str = Field(default="market", description="Order type: market or limit")
    limit_price: Optional[float] = Field(default=None, ge=0, description="Limit price (required for limit orders)")
    requestor_id: str = Field(..., min_length=1, description="Who is requesting this order")


class HITLApproval(BaseModel):
    """HITL approval record. Token = SHA-256(order_id + approver_id + timestamp)."""

    approver_id: str = Field(..., min_length=1, description="Who approved")
    approval_token: str = Field(..., min_length=64, max_length=64, description="SHA-256 approval token")
    approved_at: str = Field(..., description="ISO 8601 timestamp of approval")


class ComplianceCheckResult(BaseModel):
    """Result of a compliance check from M2/M4 via REST."""

    check_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique check ID")
    check_type: str = Field(..., description="Type of check: concentration, suitability, restricted_list, etc.")
    result: str = Field(..., pattern=r"^(PASS|DENY|WARN)$", description="Check result")
    reason: Optional[str] = Field(default=None, description="Reason for DENY or WARN")
    evaluated_at: str = Field(..., description="ISO 8601 timestamp")


class SettlementStatus(BaseModel):
    """Settlement tracking for T+1."""

    settlement_date_expected: date = Field(..., description="Expected settlement date (T+1)")
    settlement_date_actual: Optional[date] = Field(default=None, description="Actual settlement date")
    settled: bool = Field(default=False, description="Whether settlement completed")
    failure_reason: Optional[str] = Field(default=None, description="Reason for settlement failure")


class ExecutionOrder(BaseModel):
    """Full execution order with lifecycle state."""

    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="Unique order ID")
    client_id: str = Field(..., description="Canonical Client ID")
    account_id: str = Field(..., description="Canonical Account ID")
    symbol: str = Field(..., description="Security symbol")
    side: str = Field(..., description="Trade side: buy or sell")
    quantity: float = Field(..., description="Number of shares/units")
    order_type: str = Field(default="market", description="Order type")
    limit_price: Optional[float] = Field(default=None, description="Limit price")
    state: OrderState = Field(default=OrderState.DRAFT, description="Current lifecycle state")
    requestor_id: str = Field(..., description="Who requested this order")
    compliance_checks: list[ComplianceCheckResult] = Field(default_factory=list, description="Compliance check results")
    hitl_approval: Optional[HITLApproval] = Field(default=None, description="HITL approval record")
    settlement: Optional[SettlementStatus] = Field(default=None, description="Settlement tracking")
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Creation timestamp")
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(), description="Last update timestamp")
    pending_approval_at: Optional[str] = Field(default=None, description="When order entered PENDING_APPROVAL")
    submitted_at: Optional[str] = Field(default=None, description="When order was submitted")
    confirmed_at: Optional[str] = Field(default=None, description="When execution was confirmed")
    trace_id: Optional[str] = Field(default=None, description="Links to M10 audit trail")
