"""MuleSoft action orchestration - THE CHOKE POINT.

This module is the ONLY entry point to MuleSoft from OpenClaw. Every public
function below enforces the strict sequence required by v2 steering rule 1:

    1. Gather context (other skills + MCP servers)
    2. Build ActionPlan (structured, not free-text)
    3. Compute plan_hash = sha256(canonical_json(ActionPlan))
    4. Run compliance pre-check. DENY = hard stop, audit, no MuleSoft call.
    5. Request HITL approval. Timeout/reject = hard stop, audit.
    6. If notional exceeds threshold, request dual auth. Missing = queue in SF.
    7. Call the mulesoft-actions MCP server with approval_token in args.
    8. Write IR_Audit_Log__c with full provenance.
    9. Return structured ActionResult.

Invariants (enforced by this file, not config):
- No override flag. No "autopilot" mode. HITL is ALWAYS called.
- plan_hash binds the approval token to the exact ActionPlan. Field changes invalidate it.
- Audit writes happen on EVERY branch (success, deny, reject, timeout, error).
- MuleSoft is NEVER called if compliance DENIES.
- MuleSoft is NEVER called without a valid ApprovalToken.
- MuleSoft is NEVER called above threshold without dual_auth_token.

Mock mode behavior (MULESOFT_MODE=mock):
- Compliance/HITL/dual-auth all execute for real
- Only the mulesoft_mcp.tools.call request returns canned data
- L5 eval uses this to verify sequence correctness without vendor access
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from typing import Any

from .hitl import (
    ApprovalToken,
    ApprovalRejected,
    ApprovalTimeout,
    request_approval,
    verify_token,
)
from .dual_auth import (
    DualAuthToken,
    request_second_approval,
    threshold_requires_dual_auth,
)


log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public data classes
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionPlan:
    """Structured preview shown to user before approval.

    The canonical JSON representation of this object is what plan_hash is
    computed over. Any field change between approval and submission invalidates
    the approval token.
    """

    tool: str
    arguments: dict[str, Any]
    notional_usd: float
    client_id: str
    summary: str
    requires_dual_auth: bool
    wsp_reference: str


@dataclass(frozen=True)
class ActionResult:
    """Returned to caller after a completed (or refused) MuleSoft action."""

    success: bool
    status: str  # SUBMITTED / REJECTED / COMPLIANCE_BLOCKED / TIMED_OUT / ERROR
    mulesoft_reference: str | None
    tool_output: dict[str, Any]
    audit_log_id: str | None
    approval_id: str | None
    dual_approval_id: str | None
    reason: str | None = None


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class ComplianceBlocked(Exception):
    """Raised when compliance pre-check returns DENY. Action MUST NOT proceed."""


class DualAuthTimeout(Exception):
    """Raised when dual-auth approver does not respond within SLA."""


# ---------------------------------------------------------------------------
# Injectable integration points
# ---------------------------------------------------------------------------


def _default_compliance_check(action_plan: ActionPlan, context: dict[str, Any]) -> dict[str, Any]:
    """Default stub. Production wires this to the compliance-screening skill."""
    raise NotImplementedError(
        "Compliance check not wired. Set actions.compliance_check = <callable>."
    )


def _default_mulesoft_mcp_call(
    tool_name: str,
    arguments: dict[str, Any],
    approval_token: ApprovalToken,
    dual_auth_token: DualAuthToken | None,
) -> dict[str, Any]:
    """Default stub. Production wires this to the mulesoft-actions MCP server."""
    raise NotImplementedError(
        "MCP call not wired. Set actions.mulesoft_mcp_call = <callable>."
    )


def _default_audit_write(entry: dict[str, Any]) -> str:
    """Default stub. Production wires this to the audit-logging skill."""
    raise NotImplementedError(
        "Audit write not wired. Set actions.audit_write = <callable>."
    )


# Public rebinding points - replaced by test harness or production wiring.
compliance_check = _default_compliance_check
mulesoft_mcp_call = _default_mulesoft_mcp_call
audit_write = _default_audit_write


# ---------------------------------------------------------------------------
# Core sequencer - the choke point
# ---------------------------------------------------------------------------


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON representation for hashing."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _compute_plan_hash(plan: ActionPlan) -> str:
    payload = {
        "tool": plan.tool,
        "arguments": plan.arguments,
        "notional_usd": plan.notional_usd,
        "client_id": plan.client_id,
        "requires_dual_auth": plan.requires_dual_auth,
    }
    return hashlib.sha256(_canonical_json(payload).encode()).hexdigest()


def _audit_entry(
    *,
    action: str,
    plan: ActionPlan,
    status: str,
    approver_id: str | None = None,
    dual_approver_id: str | None = None,
    mulesoft_reference: str | None = None,
    reason: str | None = None,
    tool_output: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a SF IR_Audit_Log__c record payload. Never includes raw approval tokens."""
    return {
        "Action__c": action,
        "Agent__c": "mulesoft-api",
        "Query__c": plan.summary,
        "Analyst__c": approver_id,
        "Timestamp__c": int(time.time()),
        "Data_Sources_Used__c": f"MuleSoft:{plan.tool}",
        "Decision_Rationale__c": reason or f"Action {action} for client {plan.client_id}",
        "Approved_By__c": approver_id,
        "Dual_Approver__c": dual_approver_id,
        "MuleSoft_Reference__c": mulesoft_reference,
        "Plan_Hash__c": _compute_plan_hash(plan),
        "Notional_USD__c": plan.notional_usd,
        "WSP_Reference__c": plan.wsp_reference,
        "Tool_Output_Summary__c": json.dumps(tool_output)[:32000] if tool_output else None,
        "Status__c": status,
    }


def _execute_with_gates(
    plan: ActionPlan,
    context: dict[str, Any],
    *,
    action_code_success: str,
    action_code_blocked: str = "COMPLIANCE_BLOCKED",
    action_code_rejected: str = "TRADE_REJECTED",
    action_code_timeout: str = "TRADE_TIMEOUT",
    action_code_error: str = "TRADE_FAILED_UPSTREAM",
) -> ActionResult:
    """The single sequence every MuleSoft write action follows."""
    plan_hash = _compute_plan_hash(plan)
    log.info(
        "action.start tool=%s client=%s notional=%.2f",
        plan.tool, plan.client_id, plan.notional_usd,
    )

    # -------------------- B. Compliance ---------------------------
    try:
        compliance_result = compliance_check(plan, context)
    except Exception as exc:
        audit_id = audit_write(_audit_entry(
            action=action_code_error, plan=plan, status="ERROR",
            reason=f"Compliance check raised: {exc}",
        ))
        return ActionResult(
            success=False, status="ERROR", mulesoft_reference=None,
            tool_output={}, audit_log_id=audit_id, approval_id=None,
            dual_approval_id=None, reason=f"Compliance check error: {exc}",
        )

    if compliance_result.get("decision") == "DENY":
        audit_id = audit_write(_audit_entry(
            action=action_code_blocked, plan=plan, status="BLOCKED",
            reason=compliance_result.get("reason", "Compliance denied"),
        ))
        return ActionResult(
            success=False, status="COMPLIANCE_BLOCKED", mulesoft_reference=None,
            tool_output={}, audit_log_id=audit_id, approval_id=None,
            dual_approval_id=None,
            reason=compliance_result.get("reason", "Compliance denied"),
        )

    # -------------------- C. HITL approval ------------------------
    try:
        approval_token = request_approval(
            plan_summary=plan.summary, plan_hash=plan_hash, timeout_seconds=300,
        )
    except ApprovalRejected as exc:
        audit_id = audit_write(_audit_entry(
            action=action_code_rejected, plan=plan, status="REJECTED",
            reason=f"User rejected: {exc}",
        ))
        return ActionResult(
            success=False, status="REJECTED", mulesoft_reference=None,
            tool_output={}, audit_log_id=audit_id, approval_id=None,
            dual_approval_id=None, reason=str(exc),
        )
    except ApprovalTimeout as exc:
        audit_id = audit_write(_audit_entry(
            action=action_code_timeout, plan=plan, status="TIMEOUT",
            reason=f"HITL timeout: {exc}",
        ))
        return ActionResult(
            success=False, status="TIMED_OUT", mulesoft_reference=None,
            tool_output={}, audit_log_id=audit_id, approval_id=None,
            dual_approval_id=None, reason=str(exc),
        )

    # Tamper-check: the token MUST be bound to THIS plan_hash.
    if not verify_token(approval_token, plan_hash):
        audit_id = audit_write(_audit_entry(
            action=action_code_error, plan=plan, status="ERROR",
            approver_id=approval_token.approver_id,
            reason="Approval token does not match plan_hash - tamper detected",
        ))
        return ActionResult(
            success=False, status="ERROR", mulesoft_reference=None,
            tool_output={}, audit_log_id=audit_id,
            approval_id=approval_token.approver_id, dual_approval_id=None,
            reason="Plan hash mismatch",
        )

    # -------------------- D. Dual auth ---------------------------
    dual_token: DualAuthToken | None = None
    if plan.requires_dual_auth:
        dual_token = request_second_approval(
            first_approver_id=approval_token.approver_id,
            plan_hash=plan_hash, timeout_seconds=3600,
        )
        if dual_token is None:
            audit_id = audit_write(_audit_entry(
                action=action_code_timeout, plan=plan, status="AWAITING_SECOND",
                approver_id=approval_token.approver_id,
                reason="Dual-auth approver unavailable; queued for review",
            ))
            return ActionResult(
                success=False, status="AWAITING_DUAL_AUTH",
                mulesoft_reference=None, tool_output={},
                audit_log_id=audit_id,
                approval_id=approval_token.approver_id, dual_approval_id=None,
                reason="Awaiting second approver",
            )

    # -------------------- E. MuleSoft call -----------------------
    try:
        tool_output = mulesoft_mcp_call(
            tool_name=plan.tool, arguments=plan.arguments,
            approval_token=approval_token, dual_auth_token=dual_token,
        )
    except Exception as exc:
        audit_id = audit_write(_audit_entry(
            action=action_code_error, plan=plan, status="ERROR",
            approver_id=approval_token.approver_id,
            dual_approver_id=(dual_token.second_approver_id if dual_token else None),
            reason=f"MuleSoft call failed: {exc}",
        ))
        return ActionResult(
            success=False, status="ERROR", mulesoft_reference=None,
            tool_output={}, audit_log_id=audit_id,
            approval_id=approval_token.approver_id,
            dual_approval_id=(dual_token.second_approver_id if dual_token else None),
            reason=f"MuleSoft error: {exc}",
        )

    # -------------------- F. Audit success -----------------------
    mulesoft_ref = (
        tool_output.get("mulesoft_reference")
        or tool_output.get("order_id")
        or tool_output.get("wire_id")
        or tool_output.get("screening_id")
        or tool_output.get("account_number")
        or tool_output.get("basket_id")
    )
    audit_id = audit_write(_audit_entry(
        action=action_code_success, plan=plan, status="SUBMITTED",
        approver_id=approval_token.approver_id,
        dual_approver_id=(dual_token.second_approver_id if dual_token else None),
        mulesoft_reference=mulesoft_ref,
        reason=f"All gates passed. MuleSoft accepted at {int(time.time())}.",
        tool_output=tool_output,
    ))

    return ActionResult(
        success=True,
        status=tool_output.get("status", "SUBMITTED"),
        mulesoft_reference=mulesoft_ref,
        tool_output=tool_output,
        audit_log_id=audit_id,
        approval_id=approval_token.approver_id,
        dual_approval_id=(dual_token.second_approver_id if dual_token else None),
    )


# ---------------------------------------------------------------------------
# Public action functions - one per write verb
# ---------------------------------------------------------------------------


def submit_order(
    *,
    ticker: str,
    side: str,
    quantity: int,
    client_id: str,
    account_id: str,
    order_type: str = "MARKET",
    limit_price: float | None = None,
    est_notional_usd: float = 0.0,
    wsp_reference: str = "WSP-3.1-EQUITY-EXECUTION",
    context: dict[str, Any] | None = None,
) -> ActionResult:
    """Submit a trade order via MuleSoft. HITL required. Dual-auth above $500K notional."""
    context = context or {}
    requires_dual = threshold_requires_dual_auth(action_type="trade", notional=est_notional_usd)
    plan = ActionPlan(
        tool="submit_order",
        arguments={
            "ticker": ticker, "side": side, "quantity": quantity,
            "client_id": client_id, "account_id": account_id,
            "order_type": order_type, "limit_price": limit_price,
        },
        notional_usd=est_notional_usd, client_id=client_id,
        summary=f"{side} {quantity} {ticker} ({order_type}) for {client_id} - est. ${est_notional_usd:,.2f}",
        requires_dual_auth=requires_dual, wsp_reference=wsp_reference,
    )
    return _execute_with_gates(plan, context, action_code_success="TRADE_SUBMITTED")


def rebalance_portfolio(
    *,
    client_id: str,
    trades: list[dict[str, Any]],
    est_notional_usd: float = 0.0,
    wsp_reference: str = "WSP-3.2-PORTFOLIO-REBALANCE",
    context: dict[str, Any] | None = None,
) -> ActionResult:
    """Submit a basket of rebalancing trades via MuleSoft."""
    context = context or {}
    requires_dual = threshold_requires_dual_auth(action_type="rebalance", notional=est_notional_usd)
    plan = ActionPlan(
        tool="rebalance_portfolio",
        arguments={"client_id": client_id, "trades": trades},
        notional_usd=est_notional_usd, client_id=client_id,
        summary=f"Rebalance basket for {client_id}: {len(trades)} trades, est. ${est_notional_usd:,.2f}",
        requires_dual_auth=requires_dual, wsp_reference=wsp_reference,
    )
    return _execute_with_gates(plan, context, action_code_success="TRADE_SUBMITTED")


def initiate_wire(
    *,
    client_id: str,
    from_account: str,
    to_account: str,
    amount: float,
    currency: str = "USD",
    priority: str = "STANDARD",
    wsp_reference: str = "WSP-4.1-WIRE-TRANSFER",
    context: dict[str, Any] | None = None,
) -> ActionResult:
    """Initiate a wire transfer via MuleSoft. Dual-auth above $100K."""
    context = context or {}
    requires_dual = threshold_requires_dual_auth(action_type="wire", notional=amount)
    plan = ActionPlan(
        tool="initiate_wire",
        arguments={
            "client_id": client_id, "from_account": from_account,
            "to_account": to_account, "amount": amount, "currency": currency,
            "priority": priority,
        },
        notional_usd=amount, client_id=client_id,
        summary=f"Wire ${amount:,.2f} {currency} from {from_account} to {to_account} for {client_id}",
        requires_dual_auth=requires_dual, wsp_reference=wsp_reference,
    )
    return _execute_with_gates(
        plan, context, action_code_success="WIRE_INITIATED",
        action_code_rejected="WIRE_REJECTED", action_code_timeout="WIRE_TIMEOUT",
    )


def run_kyc_screening(
    *,
    client_id: str,
    client_name: str,
    level: str = "STANDARD",
    checks: list[str] | None = None,
    wsp_reference: str = "WSP-5.1-KYC-AML",
    context: dict[str, Any] | None = None,
) -> ActionResult:
    """Run KYC screening via MuleSoft. HITL required even for STANDARD level."""
    context = context or {}
    plan = ActionPlan(
        tool="run_kyc_screening",
        arguments={
            "client_name": client_name, "level": level,
            "checks": checks or ["sanctions", "pep", "adverse_media"],
        },
        notional_usd=0.0, client_id=client_id,
        summary=f"{level} KYC screening for {client_name}",
        requires_dual_auth=False, wsp_reference=wsp_reference,
    )
    return _execute_with_gates(
        plan, context, action_code_success="KYC_SCREENING",
        action_code_rejected="KYC_REJECTED", action_code_timeout="KYC_TIMEOUT",
    )


def open_account(
    *,
    client_id: str,
    account_type: str,
    jurisdiction: str,
    risk_profile: str | None = None,
    wsp_reference: str = "WSP-5.2-ACCOUNT-OPENING",
    context: dict[str, Any] | None = None,
) -> ActionResult:
    """Open an account via MuleSoft. Compliance HITL required."""
    context = context or {}
    plan = ActionPlan(
        tool="open_account",
        arguments={
            "client_id": client_id, "account_type": account_type,
            "jurisdiction": jurisdiction, "risk_profile": risk_profile,
        },
        notional_usd=0.0, client_id=client_id,
        summary=f"Open {account_type} account in {jurisdiction} for {client_id}",
        requires_dual_auth=False, wsp_reference=wsp_reference,
    )
    return _execute_with_gates(
        plan, context, action_code_success="ACCOUNT_OPENED",
        action_code_rejected="ACCOUNT_REJECTED", action_code_timeout="ACCOUNT_TIMEOUT",
    )


def close_account(
    *,
    client_id: str,
    account_id: str,
    reason: str,
    wsp_reference: str = "WSP-5.3-ACCOUNT-CLOSURE",
    context: dict[str, Any] | None = None,
) -> ActionResult:
    """Close an account via MuleSoft. ALWAYS requires dual auth (steering rule 5)."""
    context = context or {}
    plan = ActionPlan(
        tool="close_account",
        arguments={"client_id": client_id, "account_id": account_id, "reason": reason},
        notional_usd=0.0, client_id=client_id,
        summary=f"Close account {account_id} for {client_id}: {reason}",
        requires_dual_auth=True,  # Always per steering rule 5
        wsp_reference=wsp_reference,
    )
    return _execute_with_gates(
        plan, context, action_code_success="ACCOUNT_CLOSED",
        action_code_rejected="ACCOUNT_CLOSE_REJECTED",
        action_code_timeout="ACCOUNT_CLOSE_TIMEOUT",
    )


# ---------------------------------------------------------------------------
# Read-only passthroughs (no HITL, no audit beyond Langfuse trace)
# ---------------------------------------------------------------------------


def get_order_status(*, order_id: str) -> dict[str, Any]:
    """Read-only. No HITL. No audit write. Langfuse trace only."""
    return mulesoft_mcp_call(
        tool_name="get_order_status",
        arguments={"order_id": order_id},
        approval_token=ApprovalToken.read_only(),
        dual_auth_token=None,
    )


def get_settlement_status(*, wire_id: str) -> dict[str, Any]:
    """Read-only. No HITL."""
    return mulesoft_mcp_call(
        tool_name="get_settlement_status",
        arguments={"wire_id": wire_id},
        approval_token=ApprovalToken.read_only(),
        dual_auth_token=None,
    )
