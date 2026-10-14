"""Tests for ComplySci REST MCP adapter."""

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
    assert data["name"] == "complysci-adapter"
    assert data["vendor"] == "complysci"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_holdings_reports", "get_preclearance_requests", "submit_preclearance", "get_restricted_list"}


def test_get_holdings_reports_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_holdings_reports", "arguments": {"employee_id": "EMP-001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "holdings" in parsed


def test_get_preclearance_requests_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_preclearance_requests", "arguments": {"employee_id": "EMP-001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "requests" in parsed


def test_submit_preclearance_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "submit_preclearance", "arguments": {
        "employee_id": "EMP-001", "symbol": "AAPL", "side": "buy", "quantity": 100, "account_type": "personal",
    }})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["status"] == "pending"


def test_get_restricted_list_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_restricted_list", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "restricted_securities" in parsed


def test_missing_employee_id() -> None:
    resp = client.post("/tools/call", json={"name": "get_holdings_reports", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_submit_preclearance_missing_fields() -> None:
    resp = client.post("/tools/call", json={"name": "submit_preclearance", "arguments": {"employee_id": "EMP-001"}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
