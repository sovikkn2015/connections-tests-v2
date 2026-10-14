"""Tests for eMoney Advisor MCP adapter."""

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
    assert data["name"] == "emoney-adapter"
    assert data["vendor"] == "emoney"
    assert data["status"] == "healthy"
    assert data["capabilities"]["tools"] is True


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_clients", "get_plans", "get_goals", "get_plan_summary"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert "required" in tool["inputSchema"]
        assert tool["status"] == "active"


def test_get_clients_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_clients", "arguments": {"advisor_id": "ADV-100"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "clients" in parsed
    assert len(parsed["clients"]) >= 1


def test_get_plans_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_plans", "arguments": {"client_id": "EM-1001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "plans" in parsed
    plan = parsed["plans"][0]
    assert "assumptions" in plan


def test_get_goals_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_goals", "arguments": {"plan_id": "PLN-5001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "goals" in parsed
    goal = parsed["goals"][0]
    assert "probabilityOfSuccess" in goal
    assert "targetAmount" in goal


def test_get_plan_summary_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_plan_summary", "arguments": {"plan_id": "PLN-5001"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "totalNetWorth" in parsed
    assert "overallProbabilityOfSuccess" in parsed
    assert "monteCarloSimulations" in parsed


def test_get_clients_missing_param() -> None:
    resp = client.post("/tools/call", json={"name": "get_clients", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_get_goals_missing_param() -> None:
    resp = client.post("/tools/call", json={"name": "get_goals", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
