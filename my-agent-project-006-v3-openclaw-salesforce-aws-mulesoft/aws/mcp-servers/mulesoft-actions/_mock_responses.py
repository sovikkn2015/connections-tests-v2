"""Realistic mock responses for MuleSoft Process APIs (V3).

Steering rule 14/15: MCP server defaults to mock mode until vendor
sandbox is approved. Mock shapes must match the live contract so eval
pipelines catch shape regressions before the first vendor call.
"""

from __future__ import annotations

import hashlib
import time
import uuid
from datetime import datetime, timezone
from typing import Any


def _ref(prefix: str, payload: dict) -> str:
    h = hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest()[:12]
    return f"{prefix}-{h}"


def mock_submit_order(payload: dict[str, Any]) -> dict:
    ticker = payload.get("ticker", "XXX")
    qty = payload.get("quantity", 0)
    side = (payload.get("side") or "buy").upper()
    px = 100.0 + (sum(ord(c) for c in ticker) % 500) + (time.time() % 1)
    return {
        "status": "filled",
        "mulesoft_reference": _ref("MS-TRD", payload),
        "alpaca_order_id": f"ALPACA-{uuid.uuid4().hex[:8]}",
        "ticker": ticker,
        "side": side,
        "quantity": qty,
        "avg_fill_price": round(px, 2),
        "notional": round(px * qty, 2),
        "filled_at": datetime.now(tz=timezone.utc).isoformat(),
        "dataSource": "mock",
    }


def mock_cancel_order(payload: dict[str, Any]) -> dict:
    return {
        "status": "cancelled",
        "mulesoft_reference": _ref("MS-CXL", payload),
        "original_order_id": payload.get("order_id"),
        "cancelled_at": datetime.now(tz=timezone.utc).isoformat(),
        "dataSource": "mock",
    }


def mock_modify_order(payload: dict[str, Any]) -> dict:
    return {
        "status": "replaced",
        "mulesoft_reference": _ref("MS-MOD", payload),
        "original_order_id": payload.get("order_id"),
        "new_order_id": f"ALPACA-{uuid.uuid4().hex[:8]}",
        "new_limit_price": payload.get("limit_price"),
        "modified_at": datetime.now(tz=timezone.utc).isoformat(),
        "dataSource": "mock",
    }


def mock_initiate_wire(payload: dict[str, Any]) -> dict:
    return {
        "status": "initiated",
        "mulesoft_reference": _ref("MS-WIRE", payload),
        "dwolla_transfer_id": f"DWOLLA-{uuid.uuid4().hex[:8]}",
        "amount_usd": payload.get("amount_usd"),
        "currency": payload.get("currency", "USD"),
        "ofac_screen": "CLEAR",
        "beneficiary_bank": payload.get("beneficiary_bank"),
        "settles_on": "T+1",
        "initiated_at": datetime.now(tz=timezone.utc).isoformat(),
        "dataSource": "mock",
    }



def mock_order_status_webhook(payload: dict[str, Any]) -> dict:
    """Inbound webhook fan-out - records an order-status update.

    Skill layer forwards the Alpaca callback shape (order_id, status,
    filled_quantity, avg_fill_price, timestamp); the MCP server echoes a
    Mulesoft reference so the audit log can pin the inbound event to the
    trust spine.
    """
    return {
        "status": "ack",
        "mulesoft_reference": _ref("MS-HOOK", payload),
        "order_id": payload.get("order_id"),
        "order_status": payload.get("status"),
        "filled_quantity": payload.get("filled_quantity"),
        "avg_fill_price": payload.get("avg_fill_price"),
        "received_at": datetime.now(tz=timezone.utc).isoformat(),
        "callback_timestamp": payload.get("timestamp"),
        "dataSource": "mock",
    }
