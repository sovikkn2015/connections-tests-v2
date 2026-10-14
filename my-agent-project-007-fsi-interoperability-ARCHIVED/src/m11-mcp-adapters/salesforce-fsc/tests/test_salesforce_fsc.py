"""Tests for Salesforce FSC MCP adapter."""

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
    assert data["name"] == "salesforce-fsc-adapter"
    assert data["vendor"] == "salesforce_fsc"
    assert data["status"] == "healthy"
    assert data["capabilities"]["tools"] is True


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"query_soql", "get_record", "create_record", "update_record"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert "required" in tool["inputSchema"]
        assert tool["status"] == "active"


def test_query_soql_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "query_soql", "arguments": {"soql": "SELECT Id, Name FROM Account"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "records" in parsed
    assert parsed["done"] is True
    assert len(parsed["records"]) >= 1


def test_query_soql_fsc_fields() -> None:
    resp = client.post("/tools/call", json={"name": "query_soql", "arguments": {"soql": "SELECT Id FROM FinServ__FinancialAccount__c"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "records" in parsed
    record = parsed["records"][0]
    assert "FinServ__FinancialAccountType__c" in record


def test_get_record_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_record", "arguments": {"object_type": "Account", "record_id": "001000000000001AAA"}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "Id" in parsed


def test_create_record_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "create_record", "arguments": {"object_type": "Account", "fields": {"Name": "Test"}}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["success"] is True
    assert "id" in parsed


def test_update_record_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "update_record", "arguments": {"object_type": "Account", "record_id": "001000000000001AAA", "fields": {"Name": "Updated"}}})
    assert resp.status_code == 200
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["success"] is True


def test_query_soql_missing_param() -> None:
    resp = client.post("/tools/call", json={"name": "query_soql", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_get_record_missing_params() -> None:
    resp = client.post("/tools/call", json={"name": "get_record", "arguments": {"object_type": "Account"}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
