"""Tests for SEC EDGAR MCP adapter."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.server import app


client = TestClient(app)


# ---- Test 1: Health check / server info (GET /) ----

def test_health_check() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "sec-edgar-adapter"
    assert data["version"] == "1.0.0"
    assert data["vendor"] == "sec_edgar"
    assert data["status"] == "healthy"
    assert data["capabilities"]["tools"] is True


# ---- Test 2: Tools list (POST /tools/list) ----

def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    data = resp.json()
    tools = data["tools"]
    assert len(tools) == 3
    names = {t["name"] for t in tools}
    assert names == {"search_filings", "get_filing", "get_company_facts"}
    for tool in tools:
        schema = tool["inputSchema"]
        assert schema["type"] == "object"
        assert "properties" in schema
        assert "required" in schema


# ---- Test 3: Tool call — search_filings with mock ----

def test_search_filings_mock() -> None:
    mock_response = {
        "hits": {"hits": [{"_source": {"file_num": "001-36743", "form_type": "10-K"}}]},
        "total": {"value": 1},
    }
    with patch("src.server._sec_get", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/tools/call", json={
            "name": "search_filings",
            "arguments": {"query": "AAPL", "filing_type": "10-K", "limit": 5},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "isError" not in data or data.get("isError") is not True
    assert "content" in data
    parsed = json.loads(data["content"][0]["text"])
    assert "hits" in parsed


# ---- Test 4: Tool call — get_filing with mock ----

def test_get_filing_mock() -> None:
    mock_response = {"cik": "320193", "entityType": "operating", "name": "Apple Inc."}
    with patch("src.server._sec_get", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/tools/call", json={
            "name": "get_filing",
            "arguments": {"accession_number": "0000320193-23-000106"},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "isError" not in data or data.get("isError") is not True
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["name"] == "Apple Inc."


# ---- Test 5: Tool call — get_company_facts with mock ----

def test_get_company_facts_mock() -> None:
    mock_response = {"cik": 320193, "entityName": "Apple Inc.", "facts": {}}
    with patch("src.server._sec_get", new_callable=AsyncMock, return_value=mock_response):
        resp = client.post("/tools/call", json={
            "name": "get_company_facts",
            "arguments": {"cik": "320193"},
        })
    assert resp.status_code == 200
    data = resp.json()
    assert "isError" not in data or data.get("isError") is not True
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["entityName"] == "Apple Inc."


# ---- Test 6: Unknown tool returns canonical error ----

def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={
        "name": "nonexistent_tool",
        "arguments": {},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"


# ---- Test 7: Missing required param returns canonical error ----

def test_missing_required_param() -> None:
    resp = client.post("/tools/call", json={
        "name": "search_filings",
        "arguments": {},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"
