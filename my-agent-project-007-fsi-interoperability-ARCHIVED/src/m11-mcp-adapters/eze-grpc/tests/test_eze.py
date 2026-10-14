"""Tests for SS&C Eze gRPC MCP adapter."""

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
    assert data["name"] == "eze-grpc-adapter"
    assert data["vendor"] == "eze"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_orders", "get_positions", "get_executions", "submit_order"}


def test_get_orders_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_orders", "arguments": {"portfolio_id": "HF-001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "orders" in parsed


def test_get_positions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {"portfolio_id": "HF-001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "positions" in parsed


def test_get_executions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_executions", "arguments": {"order_id": "EZE-O001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "executions" in parsed


def test_submit_order_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "submit_order", "arguments": {
        "portfolio_id": "HF-001", "security_id": "AAPL", "side": "BUY", "quantity": 100, "order_type": "MARKET",
    }})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["status"] == "OPEN"


def test_missing_portfolio_id() -> None:
    resp = client.post("/tools/call", json={"name": "get_orders", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_get_executions_missing_params() -> None:
    resp = client.post("/tools/call", json={"name": "get_executions", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
