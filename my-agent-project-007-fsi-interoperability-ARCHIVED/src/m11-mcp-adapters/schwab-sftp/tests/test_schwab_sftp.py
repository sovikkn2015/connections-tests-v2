"""Tests for Schwab SFTP MCP adapter."""

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
    assert data["name"] == "schwab-sftp-adapter"
    assert data["vendor"] == "schwab_sftp"
    assert data["status"] == "healthy"


def test_tools_list() -> None:
    resp = client.post("/tools/list")
    assert resp.status_code == 200
    tools = resp.json()["tools"]
    assert len(tools) == 4
    names = {t["name"] for t in tools}
    assert names == {"list_files", "download_positions", "download_transactions", "parse_daily_file"}
    for tool in tools:
        assert tool["status"] == "active"


def test_list_files_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "list_files", "arguments": {}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "_dev_mode" in parsed
    assert "files" in parsed


def test_download_positions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "download_positions", "arguments": {"date": "20250115"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "positions" in parsed
    for pos in parsed["positions"]:
        assert "cost_basis_method" in pos
        assert pos["cost_basis_method"] is not None
        assert pos["cost_basis_method"] != ""


def test_download_transactions_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "download_transactions", "arguments": {"date": "20250115"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "transactions" in parsed


def test_parse_daily_file_dev_mode() -> None:
    resp = client.post("/tools/call", json={"name": "parse_daily_file", "arguments": {"date": "20250115", "file_type": "positions"}})
    data = resp.json()
    parsed = json.loads(data["content"][0]["text"])
    assert "positions" in parsed


def test_download_positions_missing_date() -> None:
    resp = client.post("/tools/call", json={"name": "download_positions", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "INVALID_PARAMS"


def test_unknown_tool() -> None:
    resp = client.post("/tools/call", json={"name": "nope", "arguments": {}})
    data = resp.json()
    assert data["isError"] is True
    assert data["errorCode"] == "TOOL_NOT_FOUND"
