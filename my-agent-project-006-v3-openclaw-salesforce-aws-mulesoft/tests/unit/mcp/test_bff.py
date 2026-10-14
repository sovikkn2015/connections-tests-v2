"""Tests for the BFF Lambda — routes, client delegation, validation."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path


def _load_bff():
    """Load the BFF app module with its sibling client shims on the path.

    Each import is fresh so monkeypatches to ``call_tool`` on the client
    modules land on the same instance the BFF re-imports inside its
    handlers.
    """
    root = Path(__file__).resolve().parents[3]
    bff_dir = root / "aws" / "mcp-servers" / "bff"
    if str(bff_dir) not in sys.path:
        sys.path.insert(0, str(bff_dir))

    # Drop any stale copy so each test gets a clean module (its handlers
    # import the client shims lazily, so reloading the BFF picks up the
    # monkeypatched client functions transparently).
    for mod_name in ("bff_app", "salesforce_crm_client", "sec_edgar_client"):
        sys.modules.pop(mod_name, None)

    path = bff_dir / "app.py"
    spec = importlib.util.spec_from_file_location("bff_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(method: str, path: str, *, body: dict | None = None, qs: str = "") -> dict:
    return {
        "httpMethod": method,
        "path": path,
        "rawQueryString": qs,
        "headers": {"Authorization": "Bearer dev-token"},
        "body": json.dumps(body) if body is not None else "",
    }


def test_handle_inquiries_returns_rows(monkeypatch):
    bff = _load_bff()
    import salesforce_crm_client  # noqa: WPS433 — loaded via sys.path above

    captured: dict = {}

    def fake_call(*, tool: str, arguments: dict, principal_id: str = "bff-proxy") -> dict:
        captured["tool"] = tool
        captured["arguments"] = arguments
        return {
            "records": [
                {
                    "Id": "a01",
                    "Ticker_Mentions__c": "NVDA",
                    "Client_Contact_Id__c": "c1",
                    "Client_Contact_Name__c": "Alice",
                    "Auto_Send_Eligible__c": True,
                    "Concentration_Pct__c": 12.5,
                    "CreatedDate": "2025-01-15T10:00:00Z",
                },
                {
                    "Id": "a02",
                    "Ticker_Mentions__c": "AMD",
                    "Client_Contact_Id__c": "c2",
                    "Client_Contact_Name__c": "Bob",
                    "Auto_Send_Eligible__c": False,
                    "Concentration_Pct__c": 7.0,
                    "CreatedDate": "2025-01-15T11:00:00Z",
                },
            ]
        }

    monkeypatch.setattr(salesforce_crm_client, "call_tool", fake_call)

    resp = bff.lambda_handler(
        _event("GET", "/api/inquiries", qs="type=alert&status=open"),
        None,
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert len(body["items"]) == 2
    first = body["items"][0]
    assert first["ticker"] == "NVDA"
    assert first["concentration_pct"] == 12.5
    assert first["auto_send_eligible"] is True
    assert captured["tool"] == "read_object"
    assert captured["arguments"]["object_type"] == "Client_Inquiry__c"


def test_handle_source_table_delegates_to_sec_edgar(monkeypatch):
    bff = _load_bff()
    import sec_edgar_client  # noqa: WPS433

    captured: dict = {}

    def fake_call(*, tool: str, arguments: dict, principal_id: str = "bff-proxy") -> dict:
        captured["tool"] = tool
        captured["arguments"] = arguments
        return {
            "source_id": arguments["source_id"],
            "title": "NVDA segment revenue",
            "columns": ["Segment", "FY2024"],
            "rows": [{"key": "dc", "label": "Data Center", "values": {"FY2024": 47525}}],
            "as_of": "2024-FY",
            "citation": {
                "span_id": "x",
                "source_id": arguments["source_id"],
                "source_type": "filing",
                "label": "NVDA 10-K",
            },
        }

    monkeypatch.setattr(sec_edgar_client, "call_tool", fake_call)

    resp = bff.lambda_handler(
        _event("GET", "/api/source_tables/nvda-0001045810-24-000316-tab-1"),
        None,
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert captured["tool"] == "get_source_table"
    assert captured["arguments"]["source_id"] == "nvda-0001045810-24-000316-tab-1"
    assert body["columns"] == ["Segment", "FY2024"]
    assert len(body["rows"]) == 1


def test_handle_source_chunk_delegates_to_sec_edgar(monkeypatch):
    bff = _load_bff()
    import sec_edgar_client  # noqa: WPS433

    captured: dict = {}

    def fake_call(*, tool: str, arguments: dict, principal_id: str = "bff-proxy") -> dict:
        captured["tool"] = tool
        captured["arguments"] = arguments
        return {
            "source_id": arguments["source_id"],
            "title": "NVDA 10-K — Risk Factors",
            "filing_type": "10-K",
            "filing_date": "2024-02-21",
            "section": "Item 1A. Risk Factors",
            "page": 17,
            "text": "Our results depend on continued demand for accelerated computing.",
            "url": "https://www.sec.gov/Archives/edgar/data/1045810/x.htm",
        }

    monkeypatch.setattr(sec_edgar_client, "call_tool", fake_call)

    resp = bff.lambda_handler(
        _event("GET", "/api/source_chunk/nvda-0001045810-24-000316-chunk-1"),
        None,
    )
    assert resp["statusCode"] == 200
    body = json.loads(resp["body"])
    assert captured["tool"] == "get_source_chunk"
    assert captured["arguments"]["source_id"] == "nvda-0001045810-24-000316-chunk-1"
    assert body["text"].startswith("Our results")
    assert body["section"] == "Item 1A. Risk Factors"


def test_handle_session_warm_validates_ticker():
    bff = _load_bff()
    resp = bff.lambda_handler(
        _event("POST", "/api/session/warm", body={"persona": "fsi-research", "ticker": ""}),
        None,
    )
    assert resp["statusCode"] == 400
    body = json.loads(resp["body"])
    assert body["error"] == "validation_error"
    assert "ticker" in body["message"].lower()
