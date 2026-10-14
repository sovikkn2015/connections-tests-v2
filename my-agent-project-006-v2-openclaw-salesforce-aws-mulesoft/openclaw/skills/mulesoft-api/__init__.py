"""mulesoft-api skill - the choke point for all MuleSoft writes from OpenClaw.

Public API:
    actions.submit_order(...)
    actions.initiate_wire(...)
    actions.rebalance_portfolio(...)
    actions.run_kyc_screening(...)
    actions.open_account(...)
    actions.close_account(...)
    actions.get_order_status(...)
    actions.get_settlement_status(...)

All write actions enforce: compliance -> HITL -> dual-auth (if required) -> MCP -> audit.
See docs/v2-how-mulesoft-stitches-to-openclaw.md for the full sequence.
"""

from .actions import (
    ActionPlan,
    ActionResult,
    ComplianceBlocked,
    submit_order,
    rebalance_portfolio,
    initiate_wire,
    run_kyc_screening,
    open_account,
    close_account,
    get_order_status,
    get_settlement_status,
)
from .hitl import (
    ApprovalToken,
    ApprovalRejected,
    ApprovalTimeout,
    request_approval,
    verify_token,
)
from .dual_auth import (
    DualAuthToken,
    threshold_requires_dual_auth,
    request_second_approval,
    WIRE_THRESHOLD_USD,
    TRADE_NOTIONAL_THRESHOLD_USD,
)

__all__ = [
    "ActionPlan",
    "ActionResult",
    "ComplianceBlocked",
    "submit_order",
    "rebalance_portfolio",
    "initiate_wire",
    "run_kyc_screening",
    "open_account",
    "close_account",
    "get_order_status",
    "get_settlement_status",
    "ApprovalToken",
    "ApprovalRejected",
    "ApprovalTimeout",
    "request_approval",
    "verify_token",
    "DualAuthToken",
    "threshold_requires_dual_auth",
    "request_second_approval",
    "WIRE_THRESHOLD_USD",
    "TRADE_NOTIONAL_THRESHOLD_USD",
]
