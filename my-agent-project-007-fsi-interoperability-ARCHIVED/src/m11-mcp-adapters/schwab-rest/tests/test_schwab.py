"""Tests for Schwab REST MCP adapter stub."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from src.server import app

client = TestClient(app)


def test_health_check() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "schwab-rest-adapter"
    assert data["vendor"] == "schwab"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_positions", "get_balances", "get_transactions", "submit_order"}
    for tool in tools:
        assert tool["status"] == "pending_vendor_approval"
        assert tool["inputSchema"]["type"] == "object"
        assert "required" in tool["inputSchema"]


def test_get_positions_returns_pending() -> None:
    resp = client.post("/tools/call", json={
        "name": "get_positions",
        "arguments": {"account_id": "ACC-001"},
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "PENDING_VENDOR_APPROVAL"


def test_get_balances_returns_pending() -> None:
    resp = client.post("/tools/call", json={
        "name": "get_balances",
        "arguments": {"account_id": "ACC-001"},
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "PENDING_VENDOR_APPROVAL"


def test_submit_order_returns_pending() -> None:
    resp = client.post("/tools/call", json={
        "name": "submit_order",
        "arguments": {
            "account_id": "ACC-001",
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 100,
            "order_type": "market",
        },
    })
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "PENDING_VENDOR_APPROVAL"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
