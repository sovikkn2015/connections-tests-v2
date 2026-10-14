"""Tests for Orion Portfolio Management MCP adapter."""

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
    assert data["name"] == "orion-adapter"
    assert data["vendor"] == "orion"
    assert data["status"] == "healthy"
    assert data["capabilities"]["tools"] is True


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_clients", "get_accounts", "get_positions", "get_performance"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert "required" in tool["inputSchema"]
        assert tool["status"] == "active"


def test_get_clients_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_clients", "arguments": {"representative_id": "REP-100"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "clients" in parsed
    assert len(parsed["clients"]) >= 1
    assert "household" in parsed["clients"][0]


def test_get_accounts_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_accounts", "arguments": {"client_id": "CLT-1001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "accounts" in parsed


def test_get_positions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {"account_id": "ACCT-2001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "positions" in parsed
    for pos in parsed["positions"]:
        assert "costBasisMethod" in pos
        assert pos["costBasisMethod"] is not None


def test_get_performance_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_performance", "arguments": {"account_id": "ACCT-2001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "twr" in parsed
    assert "irr" in parsed


def test_get_clients_missing_param() -> None:
    resp = client.post("/tools/call", json={"name": "get_clients", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_get_positions_missing_param() -> None:
    resp = client.post("/tools/call", json={"name": "get_positions", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
