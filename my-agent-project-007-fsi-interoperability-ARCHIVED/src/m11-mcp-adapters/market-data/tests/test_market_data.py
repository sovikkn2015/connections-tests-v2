"""Tests for Alpha Vantage Market Data MCP adapter."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("ALPHA_VANTAGE_API_KEY", "test-key-for-unit-tests")

from src.server import app

client = TestClient(app)


def test_health_check() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "market-data-adapter"
    assert data["vendor"] == "alpha_vantage"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 3
    names = {t["name"] for t in tools}
    assert names == {"get_quote", "get_daily_prices", "get_company_overview"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"
        assert "required" in tool["inputSchema"]


def test_get_quote_mock() -> None:
    mock_resp = {"Global Quote": {"01. symbol": "AAPL", "05. price": "189.84"}}
    with patch("src.server._av_get", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/tools/call", json={
            "name": "get_quote", "arguments": {"ticker": "AAPL"},
        })
    data = resp.json()
    assert "isError" not in data or not data.get("isError")
    parsed = json.loads(data["content"][0]["text"])
    assert "Global Quote" in parsed


def test_get_daily_prices_mock() -> None:
    mock_resp = {
        "Meta Data": {"2. Symbol": "AAPL"},
        "Time Series (Daily)": {
            "2026-01-15": {"4. close": "189.84"},
            "2026-01-14": {"4. close": "189.00"},
            "2026-01-13": {"4. close": "188.00"},
        },
    }
    with patch("src.server._av_get", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/tools/call", json={
            "name": "get_daily_prices", "arguments": {"ticker": "AAPL", "days": 2},
        })
    data = resp.json()
    assert "isError" not in data or not data.get("isError")
    parsed = json.loads(data["content"][0]["text"])
    assert len(parsed["Time Series (Daily)"]) == 2


def test_get_company_overview_mock() -> None:
    mock_resp = {"Symbol": "AAPL", "Name": "Apple Inc", "Sector": "Technology"}
    with patch("src.server._av_get", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/tools/call", json={
            "name": "get_company_overview", "arguments": {"ticker": "AAPL"},
        })
    data = resp.json()
    assert "isError" not in data or not data.get("isError")
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["Symbol"] == "AAPL"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"


def test_missing_ticker() -> None:
    resp = client.post("/tools/call", json={"name": "get_quote", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"
