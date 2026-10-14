"""Tests for the sec-edgar MCP server in mock mode + parser."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_app():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "sec-edgar" / "app.py"
    spec = importlib.util.spec_from_file_location("sec_edgar_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_parser():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "sec-edgar" / "_parser.py"
    spec = importlib.util.spec_from_file_location("sec_edgar_parser", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(body):
    return {
        "httpMethod": "POST",
        "path": "/mcp/sec-edgar/tools/call",
        "body": json.dumps(body),
        "headers": {},
    }


def test_get_latest_filing_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "get_latest_filing", "arguments": {"symbol": "NVDA", "type": "10-Q"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["symbol"] == "NVDA"
    assert body["result"]["dataSource"] == "mock"


def test_get_latest_filing_rejects_bad_type():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "get_latest_filing", "arguments": {"symbol": "NVDA", "type": "S-1"}}),
        None,
    )
    assert resp["statusCode"] == 400


def test_get_filing_sections_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "get_filing_sections", "arguments": {"accession_num": "0001045810-26-000042"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    items = [s["item"] for s in body["result"]["sections"]]
    assert "1A" in items and "7" in items


def test_get_financial_statements_mock_has_income_statement():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "get_financial_statements",
                "arguments": {"symbol": "NVDA", "period": "2026-Q1"},
            }
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["income_statement"]["revenue"]["value"] > 0


def test_parser_extracts_item_1a():
    parser = _load_parser()
    html = (
        "<p>Item 1. Business</p>Nothing to see."
        "<p>Item 1A. Risk Factors</p>Supply chain risk is material."
        "<p>Item 1B. Other</p>Done."
    )
    section = parser.extract_item(html, "1A")
    assert section is not None
    assert "Supply chain" in section.text


def test_parser_handles_no_match():
    parser = _load_parser()
    section = parser.extract_item("nothing relevant here", "1A")
    assert section is None


def test_parser_to_float_negative_parens():
    parser = _load_parser()
    assert parser._to_float("(1,234.56)") == -1234.56
    assert parser._to_float("$500") == 500.0
    assert parser._to_float(None) is None


def test_get_source_table_mock_known_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "get_source_table",
                "arguments": {"source_id": "nvda-0001045810-24-000316-tab-1"},
            }
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    result = body["result"]
    assert result["source_id"] == "nvda-0001045810-24-000316-tab-1"
    assert len(result["columns"]) > 0
    assert len(result["rows"]) > 0
    assert result["citation"]["source_type"] == "filing"
    # Each row has the required SourceTableRow shape.
    for row in result["rows"]:
        assert "key" in row and "label" in row and "values" in row


def test_get_source_table_mock_unknown_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "get_source_table",
                "arguments": {"source_id": "does-not-exist-tab-99"},
            }
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    result = body["result"]
    assert result["source_id"] == "does-not-exist-tab-99"
    assert result["columns"] == []
    assert result["rows"] == []
    assert result["title"].startswith("(")


def test_get_source_chunk_mock_known_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "get_source_chunk",
                "arguments": {"source_id": "nvda-0001045810-24-000316-chunk-1"},
            }
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    result = body["result"]
    assert result["source_id"] == "nvda-0001045810-24-000316-chunk-1"
    assert result["text"]
    assert result["section"]
    assert result["filing_type"] == "10-K"


def test_get_source_chunk_missing_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "get_source_chunk", "arguments": {}}),
        None,
    )
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["status"] == "error"
    assert "source_id" in body["error"]["message"]
