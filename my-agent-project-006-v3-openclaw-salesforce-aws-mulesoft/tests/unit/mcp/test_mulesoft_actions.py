"""Tests for the mulesoft-actions MCP server in mock mode."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

# Fake test fixtures — NOT real secrets.
FAKE_PLAN_HASH = "a" * 64
FAKE_APPROVAL_TOKEN = "b" * 64


def _load_app():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "mulesoft-actions" / "app.py"
    spec = importlib.util.spec_from_file_location("mulesoft_actions_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(name, arguments, principal="rm@firm.com"):
    return {
        "httpMethod": "POST",
        "path": "/mcp/mulesoft-actions/tools/call",
        "body": json.dumps({"name": name, "arguments": arguments}),
        "headers": {"X-Principal-Id": principal, "X-Persona": "fsi-advisor"},
    }


def test_submit_order_mock_fills():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "submit_order",
            {
                "ticker": "NVDA",
                "side": "sell",
                "quantity": 150,
                "account_id": "ACCT-PATEL-001",
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["mulesoft_reference"].startswith("MS-TRD-")
    assert body["result"]["alpaca_order_id"].startswith("ALPACA-")
    assert body["result"]["status"] == "filled"


def test_submit_order_requires_plan_hash():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "submit_order",
            {
                "ticker": "NVDA",
                "side": "sell",
                "quantity": 150,
                "account_id": "ACCT-PATEL-001",
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    assert resp["statusCode"] == 400


def test_submit_order_requires_approval_token():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "submit_order",
            {
                "ticker": "NVDA",
                "side": "sell",
                "quantity": 150,
                "account_id": "ACCT-PATEL-001",
                "plan_hash": FAKE_PLAN_HASH,
            },
        ),
        None,
    )
    assert resp["statusCode"] == 400


def test_submit_order_rejects_invalid_side():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "submit_order",
            {
                "ticker": "NVDA",
                "side": "short",
                "quantity": 100,
                "account_id": "ACCT-1",
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    assert resp["statusCode"] == 400


def test_submit_order_rejects_zero_quantity():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "submit_order",
            {
                "ticker": "NVDA",
                "side": "buy",
                "quantity": 0,
                "account_id": "ACCT-1",
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    assert resp["statusCode"] == 400


def test_cancel_order_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "cancel_order",
            {
                "order_id": "ALPACA-7f2a",
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["status"] == "cancelled"


def test_modify_order_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "modify_order",
            {
                "order_id": "ALPACA-7f2a",
                "limit_price": 163.50,
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["new_limit_price"] == 163.50


def test_initiate_wire_mock_ofac_clear():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "initiate_wire",
            {
                "amount_usd": 24322.50,
                "beneficiary_bank": "HSBC Singapore",
                "beneficiary_account": "SGXXXXXX",
                "source_account_id": "ACCT-PATEL-001",
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["status"] == "initiated"
    assert body["result"]["ofac_screen"] == "CLEAR"
    assert body["result"]["mulesoft_reference"].startswith("MS-WIRE-")


def test_initiate_wire_rejects_missing_beneficiary():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "initiate_wire",
            {
                "amount_usd": 1000,
                "beneficiary_account": "SGXXXX",
                "source_account_id": "ACCT-1",
                "plan_hash": FAKE_PLAN_HASH,
                "approval_token": FAKE_APPROVAL_TOKEN,
            },
        ),
        None,
    )
    assert resp["statusCode"] == 400


def test_requires_principal_header():
    app = _load_app()
    resp = app.lambda_handler(
        {
            "httpMethod": "POST",
            "path": "/mcp/mulesoft-actions/tools/call",
            "body": json.dumps({
                "name": "submit_order",
                "arguments": {
                    "ticker": "NVDA",
                    "side": "buy",
                    "quantity": 10,
                    "account_id": "a",
                    "plan_hash": FAKE_PLAN_HASH,
                    "approval_token": FAKE_APPROVAL_TOKEN,
                },
            }),
            "headers": {},
        },
        None,
    )
    assert resp["statusCode"] == 401



# ---------------------------------------------------------------------------
# Wave 2: P0.3 tests - order_status_webhook (B4 closure).
# ---------------------------------------------------------------------------

def test_order_status_webhook_mock_happy_path():
    """Webhook callback does NOT require plan_hash/approval_token."""
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "order_status_webhook",
            {
                "order_id": "ALPACA-7f2a9c11",
                "status": "filled",
                "filled_quantity": 150,
                "avg_fill_price": 162.15,
                "timestamp": "2026-03-10T09:35:12+00:00",
            },
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["order_id"] == "ALPACA-7f2a9c11"
    assert body["result"]["order_status"] == "filled"
    assert body["result"]["mulesoft_reference"].startswith("MS-HOOK-")


def test_order_status_webhook_rejects_missing_order_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "order_status_webhook",
            {"status": "filled", "timestamp": "2026-03-10T09:35:12+00:00"},
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["error"]["code"] == -32602


def test_order_status_webhook_tool_name_matches_skill_enum():
    """B4: MuleSoftMethod.ORDER_STATUS_WEBHOOK.value == MCP tool name."""
    import sys
    from pathlib import Path
    root = Path(__file__).resolve().parents[3]
    sys.path.insert(0, str(root))
    from openclaw.skills.mulesoft_api.actions import MuleSoftMethod  # noqa: E402

    assert MuleSoftMethod.ORDER_STATUS_WEBHOOK.value == "order_status_webhook"

    app = _load_app()
    listed = list(app.server._specs.keys())  # type: ignore[attr-defined]
    assert "order_status_webhook" in listed
