"""V3 mulesoft-actions MCP server.

Tools: submit_order, cancel_order, modify_order, initiate_wire.

Every tool call REQUIRES plan_hash + approval_token. The skill layer
(openclaw.skills.mulesoft_api) is the single caller per steering rule 1;
we also verify plan_hash and approval_token presence here as defense
in depth.

MULESOFT_MODE=sandbox by default (CloudHub is live). Lambda runs in VPC
with NAT so Anypoint can allowlist the NAT EIP (steering 19). Raw tokens
never leave this Lambda — we pass only the hash downstream (steering 22).

The skill layer writes IR_Audit_Log__c with Action__c = TRADE_SUBMITTED /
WIRE_INITIATED / etc. after a successful call (steering 10, 13).
"""

from __future__ import annotations

import hashlib
import os
import sys
from typing import Any

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from _base import (  # noqa: E402
    McpAuthError,
    McpServer,
    McpUpstreamError,
    McpValidationError,
    ToolSpec,
)
from _mock_responses import (  # noqa: E402
    mock_cancel_order,
    mock_initiate_wire,
    mock_modify_order,
    mock_order_status_webhook,
    mock_submit_order,
)
from _mulesoft_client import MulesoftClient  # noqa: E402

MULESOFT_MODE = os.environ.get("MULESOFT_MODE", "sandbox").lower()


def _require_principal(ctx: dict) -> str:
    pid = ctx.get("principal_id", "")
    if not pid:
        raise McpAuthError("Missing X-Principal-Id header")
    return pid


def _require_plan_hash_and_token(args: dict[str, Any]) -> tuple[str, str]:
    ph = args.get("plan_hash")
    tok = args.get("approval_token")
    if not isinstance(ph, str) or not ph.strip():
        raise McpValidationError("'plan_hash' required (SHA-256 of canonical ActionPlan)")
    if not isinstance(tok, str) or not tok.strip():
        raise McpValidationError("'approval_token' required (HMAC-SHA256, 5-min TTL)")
    if len(ph) < 32 or len(tok) < 32:
        raise McpValidationError("plan_hash / approval_token look malformed")
    return ph, tok


def _hash_token(token: str) -> str:
    """Steering rule 22: never log raw approval tokens."""
    return hashlib.sha256(token.encode()).hexdigest()


_CLIENT = MulesoftClient()


def _dispatch(endpoint: str, payload: dict, principal_id: str, mock_fn):
    if MULESOFT_MODE == "mock":
        return mock_fn(payload)
    try:
        return _CLIENT.call("POST", endpoint, payload, principal_id)
    except RuntimeError as exc:
        raise McpUpstreamError(str(exc)) from exc


def handle_submit_order(args: dict, ctx: dict) -> dict:
    pid = _require_principal(ctx)
    _require_plan_hash_and_token(args)

    for field in ("ticker", "side", "quantity", "account_id"):
        if args.get(field) in (None, ""):
            raise McpValidationError(f"'{field}' required")
    side = str(args.get("side", "")).lower()
    if side not in {"buy", "sell"}:
        raise McpValidationError("'side' must be 'buy' or 'sell'")
    qty = args.get("quantity")
    if not isinstance(qty, (int, float)) or qty <= 0:
        raise McpValidationError("'quantity' must be positive number")

    payload = {
        "ticker": args["ticker"],
        "side": side,
        "quantity": qty,
        "account_id": args["account_id"],
        "order_type": args.get("order_type", "market"),
        "limit_price": args.get("limit_price"),
        "plan_hash": args["plan_hash"],
        "approval_token_hash": _hash_token(args["approval_token"]),
    }
    return _dispatch("/orders", payload, pid, mock_submit_order)


def handle_cancel_order(args: dict, ctx: dict) -> dict:
    pid = _require_principal(ctx)
    _require_plan_hash_and_token(args)
    order_id = args.get("order_id")
    if not isinstance(order_id, str) or not order_id.strip():
        raise McpValidationError("'order_id' required")
    payload = {
        "order_id": order_id,
        "plan_hash": args["plan_hash"],
        "approval_token_hash": _hash_token(args["approval_token"]),
    }
    return _dispatch(f"/orders/{order_id}/cancel", payload, pid, mock_cancel_order)


def handle_modify_order(args: dict, ctx: dict) -> dict:
    pid = _require_principal(ctx)
    _require_plan_hash_and_token(args)
    order_id = args.get("order_id")
    limit_price = args.get("limit_price")
    if not isinstance(order_id, str) or not order_id.strip():
        raise McpValidationError("'order_id' required")
    if not isinstance(limit_price, (int, float)) or limit_price <= 0:
        raise McpValidationError("'limit_price' must be positive number")
    payload = {
        "order_id": order_id,
        "limit_price": limit_price,
        "plan_hash": args["plan_hash"],
        "approval_token_hash": _hash_token(args["approval_token"]),
    }
    return _dispatch(f"/orders/{order_id}/modify", payload, pid, mock_modify_order)


def handle_initiate_wire(args: dict, ctx: dict) -> dict:
    pid = _require_principal(ctx)
    _require_plan_hash_and_token(args)
    for field in ("amount_usd", "beneficiary_bank", "beneficiary_account", "source_account_id"):
        if args.get(field) in (None, ""):
            raise McpValidationError(f"'{field}' required")
    amt = args.get("amount_usd")
    if not isinstance(amt, (int, float)) or amt <= 0:
        raise McpValidationError("'amount_usd' must be positive number")

    payload = {
        "amount_usd": amt,
        "currency": args.get("currency", "USD"),
        "beneficiary_bank": args["beneficiary_bank"],
        "beneficiary_account": args["beneficiary_account"],
        "source_account_id": args["source_account_id"],
        "reference_memo": args.get("reference_memo", ""),
        "plan_hash": args["plan_hash"],
        "approval_token_hash": _hash_token(args["approval_token"]),
    }
    return _dispatch("/wires", payload, pid, mock_initiate_wire)


def handle_order_status_webhook(args: dict, ctx: dict) -> dict:
    """Inbound order-status webhook callback.

    This is a fan-out path: the Mulesoft webhook receives an Alpaca callback
    and posts it here so the skill layer can audit and update the Salesforce
    Position/Order record. Callbacks are authenticated at the API Gateway
    edge via a shared-secret signature; they do NOT carry plan_hash /
    approval_token because they are not RM-initiated writes.
    """
    pid = _require_principal(ctx)
    for field in ("order_id", "status", "timestamp"):
        if args.get(field) in (None, ""):
            raise McpValidationError(f"'{field}' required")
    filled_qty = args.get("filled_quantity")
    if filled_qty is not None and (
        not isinstance(filled_qty, (int, float)) or filled_qty < 0
    ):
        raise McpValidationError("'filled_quantity' must be non-negative number")
    avg_px = args.get("avg_fill_price")
    if avg_px is not None and (
        not isinstance(avg_px, (int, float)) or avg_px <= 0
    ):
        raise McpValidationError("'avg_fill_price' must be positive number")

    payload = {
        "order_id": args["order_id"],
        "status": args["status"],
        "filled_quantity": filled_qty,
        "avg_fill_price": avg_px,
        "timestamp": args["timestamp"],
    }
    return _dispatch(
        f"/orders/{args['order_id']}/webhook",
        payload,
        pid,
        mock_order_status_webhook,
    )


server = McpServer(
    name="mulesoft-actions",
    version="3.0.0",
    description=(
        "MuleSoft Process APIs for regulated writes: trades and wires. "
        f"Mode: {MULESOFT_MODE}. Requires plan_hash + approval_token on every call."
    ),
)


def _base_schema(extra: dict) -> dict:
    base = {
        "plan_hash": {"type": "string", "description": "SHA-256 of canonical ActionPlan"},
        "approval_token": {
            "type": "string",
            "description": "HMAC-SHA256 approval token, 5-min TTL, bound to plan_hash",
        },
    }
    base.update(extra)
    return base


server.register(
    ToolSpec(
        name="submit_order",
        description="Submit a trade order via MuleSoft submit-order Process API (Alpaca paper).",
        input_schema={
            "type": "object",
            "properties": _base_schema(
                {
                    "ticker": {"type": "string"},
                    "side": {"type": "string", "enum": ["buy", "sell"]},
                    "quantity": {"type": "number"},
                    "account_id": {"type": "string"},
                    "order_type": {"type": "string", "enum": ["market", "limit"], "default": "market"},
                    "limit_price": {"type": "number"},
                }
            ),
            "required": ["ticker", "side", "quantity", "account_id", "plan_hash", "approval_token"],
        },
    ),
    handle_submit_order,
)
server.register(
    ToolSpec(
        name="cancel_order",
        description="Cancel an in-flight order.",
        input_schema={
            "type": "object",
            "properties": _base_schema({"order_id": {"type": "string"}}),
            "required": ["order_id", "plan_hash", "approval_token"],
        },
    ),
    handle_cancel_order,
)
server.register(
    ToolSpec(
        name="modify_order",
        description="Modify an in-flight limit order (new limit price).",
        input_schema={
            "type": "object",
            "properties": _base_schema(
                {
                    "order_id": {"type": "string"},
                    "limit_price": {"type": "number"},
                }
            ),
            "required": ["order_id", "limit_price", "plan_hash", "approval_token"],
        },
    ),
    handle_modify_order,
)
server.register(
    ToolSpec(
        name="initiate_wire",
        description="Initiate a wire transfer (OFAC SDN screening before Dwolla sandbox).",
        input_schema={
            "type": "object",
            "properties": _base_schema(
                {
                    "amount_usd": {"type": "number"},
                    "currency": {"type": "string", "default": "USD"},
                    "beneficiary_bank": {"type": "string"},
                    "beneficiary_account": {"type": "string"},
                    "source_account_id": {"type": "string"},
                    "reference_memo": {"type": "string"},
                }
            ),
            "required": [
                "amount_usd",
                "beneficiary_bank",
                "beneficiary_account",
                "source_account_id",
                "plan_hash",
                "approval_token",
            ],
        },
    ),
    handle_initiate_wire,
)


server.register(
    ToolSpec(
        name="order_status_webhook",
        description=(
            "Inbound Alpaca order-status callback fan-out. Called by the "
            "Mulesoft webhook endpoint; no plan_hash/approval_token required "
            "because the callback is not RM-initiated."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": [
                        "filled",
                        "partially_filled",
                        "canceled",
                        "replaced",
                        "rejected",
                        "expired",
                    ],
                },
                "filled_quantity": {"type": "number"},
                "avg_fill_price": {"type": "number"},
                "timestamp": {"type": "string"},
            },
            "required": ["order_id", "status", "timestamp"],
        },
    ),
    handle_order_status_webhook,
)


def lambda_handler(event, context):
    return server.handle(event, context)
