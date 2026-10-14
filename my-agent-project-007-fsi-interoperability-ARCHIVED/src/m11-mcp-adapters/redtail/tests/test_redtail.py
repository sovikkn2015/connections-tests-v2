"""Tests for Redtail CRM MCP adapter."""

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
    assert data["name"] == "redtail-adapter"
    assert data["vendor"] == "redtail"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_contacts", "get_activities", "get_notes", "create_activity"}


def test_get_contacts_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_contacts", "arguments": {"query": "Alice"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "contacts" in parsed


def test_get_activities_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_activities", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "activities" in parsed


def test_get_notes_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_notes", "arguments": {"contact_id": "RT-C001"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "notes" in parsed


def test_create_activity_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "create_activity", "arguments": {"contact_id": "RT-C001", "activity_type": "call", "subject": "Follow-up"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["activity_type"] == "call"


def test_get_contacts_missing_query() -> None:
    resp = client.post("/tools/call", json={"name": "get_contacts", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_get_notes_missing_contact() -> None:
    resp = client.post("/tools/call", json={"name": "get_notes", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
