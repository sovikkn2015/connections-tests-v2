"""Tests for Charles Schwab REST MCP adapter."""

from __future__ import annotations

import json

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
    assert data["capabilities"]["tools"] is True


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 5
    names = {t["name"] for t in tools}
    assert names == {"get_accounts", "get_positions", "get_balances", "get_transactions", "get_orders"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert "required" in tool["inputSchema"]
        assert tool["status"] == "active"


def test_get_accounts_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_accounts", "arguments": {}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "accounts" in parsed
    assert len(parsed["accounts"]) >= 1


def test_get_positions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {"account_id": "SCHW-001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "positions" in parsed
    for pos in parsed["positions"]:
        assert "costBasisMethod" in pos
        assert pos["costBasisMethod"] is not None
        assert pos["costBasisMethod"] != ""


def test_get_balances_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_balances", "arguments": {"account_id": "SCHW-001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "totalValue" in parsed


def test_get_transactions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_transactions", "arguments": {"account_id": "SCHW-001", "start_date": "2025-01-01", "end_date": "2025-01-31"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "transactions" in parsed


def test_get_orders_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_orders", "arguments": {"account_id": "SCHW-001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "orders" in parsed


def test_get_positions_missing_param() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_get_transactions_missing_dates() -> None:
    resp = client.post("/tools/call", json={"name": "get_transactions", "arguments": {"account_id": "SCHW-001"}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
