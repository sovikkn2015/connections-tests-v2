"""Tests for the news-search MCP server in mock mode."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_app():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "news-search" / "app.py"
    spec = importlib.util.spec_from_file_location("news_search_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(body):
    return {
        "httpMethod": "POST",
        "path": "/mcp/news-search/tools/call",
        "body": json.dumps(body),
        "headers": {},
    }


def test_search_news_mock_returns_results():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "search_news", "arguments": {"query": "NVDA earnings", "days_back": 7}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    results = body["result"]["results"]
    assert len(results) >= 3
    for r in results:
        assert {"title", "url", "snippet"}.issubset(r.keys())


def test_search_news_rejects_empty_query():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "search_news", "arguments": {"query": "", "days_back": 7}}),
        None,
    )
    assert resp["statusCode"] == 400


def test_search_news_rejects_bad_days_back():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "search_news", "arguments": {"query": "NVDA", "days_back": 99}}),
        None,
    )
    assert resp["statusCode"] == 400


def test_score_sentiment_positive_wording():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "score_sentiment", "arguments": {"text": "strong beat, upgrade to bullish, record growth"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["label"] == "positive"
    assert body["result"]["score"] > 0


def test_score_sentiment_negative_wording():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "score_sentiment", "arguments": {"text": "miss, concern, weak decline, downgrade, bearish"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["result"]["label"] == "negative"
    assert body["result"]["score"] < 0


def test_score_sentiment_requires_text():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "score_sentiment", "arguments": {"text": ""}}),
        None,
    )
    assert resp["statusCode"] == 400
