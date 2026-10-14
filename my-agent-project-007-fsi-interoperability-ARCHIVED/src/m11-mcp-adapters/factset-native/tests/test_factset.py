"""Tests for FactSet MCP-Native passthrough adapter."""

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
    assert data["name"] == "factset-native-adapter"
    assert data["vendor"] == "factset"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"proxy_tools_list", "proxy_tool_call"}


def test_proxy_tools_list_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "proxy_tools_list", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "tools" in parsed
    assert len(parsed["tools"]) >= 1


def test_proxy_tool_call_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "proxy_tool_call", "arguments": {"tool_name": "factset_company_data", "tool_arguments": {"ticker": "AAPL"}}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert parsed["proxied_tool"] == "factset_company_data"


def test_proxy_tool_call_missing_name() -> None:
    resp = client.post("/tools/call", json={"name": "proxy_tool_call", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
