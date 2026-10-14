"""Tests for Wealthbox CRM MCP adapter."""

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
    assert data["name"] == "wealthbox-adapter"
    assert data["vendor"] == "wealthbox"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_contacts", "get_tasks", "get_opportunities", "create_note"}


def test_get_contacts_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_contacts", "arguments": {"query": "Jane"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "contacts" in parsed


def test_get_tasks_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_tasks", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "tasks" in parsed


def test_get_opportunities_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_opportunities", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "opportunities" in parsed


def test_create_note_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "create_note", "arguments": {"contact_id": "WB-C001", "content": "Test note"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["contact_id"] == "WB-C001"


def test_get_contacts_missing_query() -> None:
    resp = client.post("/tools/call", json={"name": "get_contacts", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
