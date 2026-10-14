"""Tests for Envestnet REST MCP adapter."""

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
    assert data["name"] == "envestnet-adapter"
    assert data["vendor"] == "envestnet"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_accounts", "get_holdings", "get_performance", "get_billing"}


def test_get_accounts_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_accounts", "arguments": {"advisor_id": "ADV-001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "accounts" in parsed


def test_get_holdings_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_holdings", "arguments": {"account_id": "ENV-A001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "holdings" in parsed
    for h in parsed["holdings"]:
        assert h["cost_basis_method"] is not None


def test_get_performance_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_performance", "arguments": {"account_id": "ENV-A001", "period": "ytd"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "twr" in parsed


def test_get_billing_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_billing", "arguments": {"account_id": "ENV-A001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "billing" in parsed


def test_missing_advisor_id() -> None:
    resp = client.post("/tools/call", json={"name": "get_accounts", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
