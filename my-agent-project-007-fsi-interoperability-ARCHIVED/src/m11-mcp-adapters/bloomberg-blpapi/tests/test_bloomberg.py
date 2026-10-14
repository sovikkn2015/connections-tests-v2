"""Tests for Bloomberg BLPAPI MCP adapter."""

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
    assert data["name"] == "bloomberg-blpapi-adapter"
    assert data["vendor"] == "bloomberg"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"get_reference_data", "get_historical_data", "subscribe_realtime", "get_intraday_bars"}


def test_get_reference_data_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_reference_data", "arguments": {"securities": ["AAPL US Equity"], "fields": ["PX_LAST"]}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "reference_data" in parsed


def test_get_historical_data_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_historical_data", "arguments": {"security": "AAPL US Equity", "start_date": "20250101", "end_date": "20250115", "fields": ["PX_LAST"]}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "historical_data" in parsed


def test_subscribe_realtime_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "subscribe_realtime", "arguments": {"securities": ["AAPL US Equity"], "fields": ["LAST_PRICE"]}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "snapshots" in parsed


def test_get_intraday_bars_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "get_intraday_bars", "arguments": {"security": "AAPL US Equity", "interval": 5, "start_datetime": "2025-01-15T09:30:00", "end_datetime": "2025-01-15T16:00:00"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "bars" in parsed


def test_missing_securities() -> None:
    resp = client.post("/tools/call", json={"name": "get_reference_data", "arguments": {"securities": [], "fields": ["PX_LAST"]}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_missing_fields() -> None:
    resp = client.post("/tools/call", json={"name": "get_reference_data", "arguments": {"securities": ["AAPL US Equity"], "fields": []}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
