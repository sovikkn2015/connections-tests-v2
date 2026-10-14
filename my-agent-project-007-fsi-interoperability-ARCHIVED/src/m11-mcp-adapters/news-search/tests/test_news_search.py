"""Tests for News API MCP adapter."""

from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("NEWS_API_KEY", "test-key-for-unit-tests")

from src.server import app

client = TestClient(app)


def test_health_check() -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    data = resp.json()
    assert data["name"] == "news-search-adapter"
    assert data["vendor"] == "news_api"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 2
    names = {t["name"] for t in tools}
    assert names == {"search_news", "get_headlines"}
    for tool in tools:
        assert tool["inputSchema"]["type"] == "object"


def test_search_news_mock() -> None:
    mock_resp = {
        "status": "ok",
        "totalResults": 1,
        "articles": [{"title": "Apple Q4 Earnings Beat", "source": {"name": "Reuters"}}],
    }
    with patch("src.server._news_get", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/tools/call", json={
            "name": "search_news",
            "arguments": {"query": "Apple earnings", "sort_by": "relevancy"},
        })
    data = resp.json()
    assert "isError" not in data or not data.get("isError")
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["totalResults"] == 1


def test_get_headlines_mock() -> None:
    mock_resp = {
        "status": "ok",
        "totalResults": 5,
        "articles": [{"title": "Markets Rally on Fed Decision"}],
    }
    with patch("src.server._news_get", new_callable=AsyncMock, return_value=mock_resp):
        resp = client.post("/tools/call", json={
            "name": "get_headlines",
            "arguments": {"category": "business", "country": "us"},
        })
    data = resp.json()
    assert "isError" not in data or not data.get("isError")
    parsed = json.loads(data["content"][0]["text"])
    assert parsed["status"] == "ok"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"


def test_missing_query() -> None:
    resp = client.post("/tools/call", json={"name": "search_news", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"
