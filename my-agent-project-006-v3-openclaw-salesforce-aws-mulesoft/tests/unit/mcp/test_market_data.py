"""Tests for the market-data MCP server in mock mode."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_app():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "market-data" / "app.py"
    spec = importlib.util.spec_from_file_location("market_data_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(path, body):
    return {
        "httpMethod": "POST",
        "path": path,
        "body": json.dumps(body),
        "headers": {},
    }


def test_get_quote_mock_returns_shape():
    app = _load_app()
    resp = app.lambda_handler(
        _event("/mcp/market-data/tools/call", {"name": "get_quote", "arguments": {"symbol": "NVDA"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 200
    result = body["result"]
    assert result["symbol"] == "NVDA"
    assert result["dataSource"] == "mock"
    assert result["price"] > 0


def test_get_quote_rejects_empty_symbol():
    app = _load_app()
    resp = app.lambda_handler(
        _event("/mcp/market-data/tools/call", {"name": "get_quote", "arguments": {"symbol": ""}}),
        None,
    )
    body = json.loads(resp["body"])
    assert resp["statusCode"] == 400
    assert body["error"]["code"] == -32602


def test_get_historical_returns_price_series():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "/mcp/market-data/tools/call",
            {"name": "get_historical", "arguments": {"symbol": "NVDA", "period": "3mo"}},
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    prices = body["result"]["prices"]
    assert len(prices) == 66
    assert all("close" in p for p in prices)


def test_get_historical_rejects_bad_period():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "/mcp/market-data/tools/call",
            {"name": "get_historical", "arguments": {"symbol": "NVDA", "period": "10y"}},
        ),
        None,
    )
    assert resp["statusCode"] == 400


def test_get_technicals_returns_rsi():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            "/mcp/market-data/tools/call",
            {"name": "get_technicals", "arguments": {"symbol": "AAPL"}},
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["rsi_14"] > 0


def test_health_endpoint_lists_tools():
    app = _load_app()
    resp = app.lambda_handler({"httpMethod": "GET", "path": "/", "headers": {}}, None)
    body = json.loads(resp["body"])
    assert body["name"] == "market-data"
    assert set(body["tools"]) == {"get_quote", "get_historical", "get_technicals"}
