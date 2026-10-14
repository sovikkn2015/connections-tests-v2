"""Tests for Pershing REST MCP adapter."""

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
    assert data["name"] == "pershing-adapter"
    assert data["vendor"] == "pershing"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_accounts", "get_positions", "get_balances", "get_transactions"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"


def test_get_accounts_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_accounts", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "accounts" in parsed


def test_get_positions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {"account_id": "PSH-10001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "positions" in parsed
    for pos in parsed["positions"]:
        assert pos["cost_basis_method"] is not None


def test_get_balances_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_balances", "arguments": {"account_id": "PSH-10001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "total_value" in parsed


def test_get_transactions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_transactions", "arguments": {"account_id": "PSH-10001", "start_date": "2025-01-01", "end_date": "2025-01-31"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "transactions" in parsed


def test_missing_account_id() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
