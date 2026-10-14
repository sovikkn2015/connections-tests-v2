"""Tests for the salesforce-crm MCP server in mock mode."""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path


def _load_app():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "salesforce-crm" / "app.py"
    spec = importlib.util.spec_from_file_location("sf_crm_app", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_mnpi():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "salesforce-crm" / "_mnpi_redact.py"
    spec = importlib.util.spec_from_file_location("mnpi_redact", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _load_soql():
    root = Path(__file__).resolve().parents[3]
    path = root / "aws" / "mcp-servers" / "salesforce-crm" / "_soql_safe.py"
    spec = importlib.util.spec_from_file_location("soql_safe", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _event(body, principal="sarah@firm.com", persona="fsi-research"):
    return {
        "httpMethod": "POST",
        "path": "/mcp/salesforce-crm/tools/call",
        "body": json.dumps(body),
        "headers": {"X-Principal-Id": principal, "X-Persona": persona},
    }


@contextmanager
def _raises(exc_type):
    try:
        yield
        raise AssertionError(f"expected {exc_type}")
    except exc_type:
        pass


def test_query_soql_requires_principal():
    app = _load_app()
    resp = app.lambda_handler(
        {
            "httpMethod": "POST",
            "path": "/mcp/salesforce-crm/tools/call",
            "body": json.dumps({"name": "query_soql", "arguments": {"soql": "SELECT Id FROM Research_Brief__c"}}),
            "headers": {},
        },
        None,
    )
    assert resp["statusCode"] == 401


def test_query_soql_mock_returns_brief():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "query_soql", "arguments": {"soql": "SELECT Id, Thesis__c FROM Research_Brief__c"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert len(body["result"]["records"]) == 1
    assert body["result"]["records"][0]["Ticker__c"] == "NVDA"


def test_query_soql_rejects_write_keyword():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "query_soql", "arguments": {"soql": "UPDATE Research_Brief__c SET Thesis__c='x'"}}),
        None,
    )
    assert resp["statusCode"] == 400


def test_get_object_mnpi_redaction_on_position():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "get_object", "arguments": {"sobject": "Position", "record_id": "p00000000000001AAC"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert "REDACTED" in str(body["result"]["Shares_Held__c"])
    assert "REDACTED" in str(body["result"]["Market_Value__c"])
    assert body["result"]["Portfolio_Pct"] == 6.2


def test_create_object_blocked_for_client_liaison():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "create_object",
                "arguments": {
                    "sobject": "Research_Brief__c",
                    "fields": {"Ticker__c": "NVDA", "Thesis__c": "x"},
                },
            },
            persona="fsi_client_liaison",
        ),
        None,
    )
    body = json.loads(resp["body"])
    # McpError default http_status is 500 (not 4xx) — persona violation is a security boundary
    assert body["error"]["code"] == -32003


def test_create_object_ok_for_research_persona():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "create_object",
                "arguments": {
                    "sobject": "Research_Brief__c",
                    "fields": {"Ticker__c": "NVDA", "Thesis__c": "AI momentum"},
                },
            },
            persona="fsi-research",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["success"] is True


def test_soql_safe_identifier_validation():
    soql = _load_soql()
    assert soql.validate_identifier("Research_Brief__c") == "Research_Brief__c"
    with _raises(soql.SoqlSafeError):
        soql.validate_identifier("DROP TABLE; --")


def test_soql_safe_escape_literal():
    soql = _load_soql()
    assert soql.escape_literal("O'Reilly") == "'O\\'Reilly'"
    assert soql.escape_literal(None) == "null"
    assert soql.escape_literal(True) == "true"
    assert soql.escape_literal(42) == "42"


def test_soql_safe_ensure_read_only_rejects_delete():
    soql = _load_soql()
    with _raises(soql.SoqlSafeError):
        soql.ensure_read_only("SELECT Id FROM X; DELETE FROM X")


def test_soql_safe_build_select():
    soql = _load_soql()
    query = soql.build_select(
        "Research_Brief__c",
        ["Id", "Ticker__c"],
        where={"Ticker__c": "NVDA"},
        limit=10,
    )
    assert "SELECT Id, Ticker__c FROM Research_Brief__c" in query
    assert "WHERE Ticker__c = 'NVDA'" in query
    assert "LIMIT 10" in query


def test_mnpi_redaction_replaces_shares_held():
    mnpi = _load_mnpi()
    rec = {"Id": "x", "Shares_Held__c": 150, "Market_Value__c": 24000, "Portfolio_Pct": 6.2}
    out = mnpi.redact_record(rec)
    assert "REDACTED" in out["Shares_Held__c"]
    assert out["Portfolio_Pct"] == 6.2
    assert out["Id"] == "x"


def test_mnpi_redaction_band_selection():
    mnpi = _load_mnpi()
    rec = {"Shares_Held__c": 1000, "Portfolio_Pct": 6.2}
    out = mnpi.redact_record(rec)
    assert "5-10%" in out["Shares_Held__c"]
    rec2 = {"Shares_Held__c": 99999, "Portfolio_Pct": 26.0}
    out2 = mnpi.redact_record(rec2)
    assert "25%+" in out2["Shares_Held__c"]


def test_query_data_cloud_dlm_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event({"name": "query_data_cloud_dlm", "arguments": {"query": "SELECT * FROM Research_Brief_Stream"}}),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert len(body["result"]["records"]) == 2
    assert body["result"]["records"][0]["Client_Name"] == "Patel Household"



# ---------------------------------------------------------------------------
# Wave 2 regression: P0.1 lock - underscore form IS the blocked form.
# Writing this test after the fix prevents the one-character typo from
# silently reverting on a future refactor.
# ---------------------------------------------------------------------------

def test_create_object_blocked_for_underscore_client_liaison():
    """Canonical wire persona `fsi_client_liaison` must trigger the gate."""
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "create_object",
                "arguments": {
                    "sobject": "Research_Brief__c",
                    "fields": {"Ticker__c": "NVDA", "Thesis__c": "x"},
                },
            },
            persona="fsi_client_liaison",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "error"
    assert body["error"]["code"] == -32003
    msg = body["error"]["message"].lower()
    assert "client-liaison" in msg or "read-only" in msg


def test_update_object_blocked_for_underscore_client_liaison():
    """Update path also enforces underscore-form gate."""
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "update_object",
                "arguments": {
                    "sobject": "Research_Brief__c",
                    "record_id": "a0B000000000001AAC",
                    "fields": {"Thesis__c": "updated"},
                },
            },
            persona="fsi_client_liaison",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["error"]["code"] == -32003


# ---------------------------------------------------------------------------
# Wave 2: P0.2 tests - 7 high-level domain tools.
# ---------------------------------------------------------------------------

def test_write_audit_log_mock_returns_id_and_stamps_timestamp():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "write_audit_log",
                "arguments": {
                    "record": {
                        "Action__c": "RESEARCH_PUBLISHED",
                        "Principal_Id__c": "sarah@firm.com",
                        "Agent_Id__c": "research_orchestrator",
                        "Session_Id__c": "sess-1",
                        "Correlation_Id__c": "corr-1",
                    }
                },
            },
            persona="fsi_research",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["Id"].startswith("AUDIT")
    assert body["result"]["dataSource"] == "mock"


def test_write_audit_log_blocked_for_client_liaison():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "write_audit_log",
                "arguments": {"record": {"Action__c": "FAQ_ANSWERED"}},
            },
            persona="fsi_client_liaison",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["error"]["code"] == -32003


def test_write_research_brief_mock_returns_brief_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "write_research_brief",
                "arguments": {
                    "record": {
                        "Ticker__c": "NVDA",
                        "Thesis__c": "AI demand sustained.",
                        "Sentiment_Score__c": 0.2,
                        "Compliance_Status__c": "ALLOW",
                        "MNPI_Cleared__c": True,
                        "RM_Consumable__c": True,
                        "Author_Agent_Id__c": "research_orchestrator",
                    }
                },
            },
            persona="fsi_research",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["Id"].startswith("a0X")


def test_write_research_brief_flat_args_requires_ticker_format():
    """When `record` is absent, the handler enforces ticker format."""
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "write_research_brief",
                "arguments": {
                    "ticker": "not-a-ticker",
                    "thesis": "Detailed thesis text >20 chars",
                    "sentiment_score": 0.1,
                    "compliance_status": "ALLOW",
                    "mnpi_cleared": True,
                    "rm_consumable": True,
                    "source_chunk_ids": ["c1"],
                    "author_agent_id": "research_orchestrator",
                },
            },
            persona="fsi_research",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "error"
    assert body["error"]["code"] == -32602


def test_write_pending_approval_mock_returns_pending_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "write_pending_approval",
                "arguments": {
                    "record": {
                        "Plan_Hash__c": "a" * 32,
                        "Requested_By__c": "rm@firm.com",
                        "Status__c": "PENDING",
                        "Expires_At__c": "2026-03-10T08:00:00+00:00",
                    }
                },
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["Id"].startswith("a0Y")


def test_update_pending_approval_mock_ok():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "update_pending_approval",
                "arguments": {
                    "id": "a0Y000000000001AAC",
                    "fields": {
                        "Status__c": "APPROVED",
                        "Senior_Approver__c": "compliance@firm.com",
                    },
                },
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["ok"] is True
    assert body["result"]["id"] == "a0Y000000000001AAC"


def test_update_pending_approval_requires_id():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "update_pending_approval",
                "arguments": {"status": "APPROVED"},
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["error"]["code"] == -32602


def test_read_household_summary_mock_shape_matches_skill():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "read_household_summary",
                "arguments": {
                    "household_id": "H001",
                    "principal_id": "rm@firm.com",
                    "mnpi_filtered": True,
                },
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["household_name"] == "Patel Household"
    assert any(p["ticker"] == "NVDA" for p in body["result"]["positions"])
    for p in body["result"]["positions"]:
        assert "pct_of_portfolio" in p
        assert "shares" not in p
        assert "market_value" not in p


def test_read_household_positions_mock_has_percentages_only():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "read_household_positions",
                "arguments": {"household_id": "H001"},
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    positions = body["result"]["positions"]
    assert len(positions) >= 1
    for p in positions:
        assert "pct_of_portfolio" in p
        assert "shares" not in p
        assert "market_value" not in p


def test_read_research_briefs_with_exposure_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "read_research_briefs_with_exposure",
                "arguments": {"principal_id": "rm@firm.com"},
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    briefs = body["result"]["briefs"]
    assert len(briefs) == 1
    assert briefs[0]["ticker"] == "NVDA"
    assert briefs[0]["affected_clients"][0]["pct_exposure"] == 6.2


def test_read_research_briefs_with_exposure_ticker_filter_mock():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "read_research_briefs_with_exposure",
                "arguments": {"ticker_filter": "AAPL"},
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["status"] == "ok"
    assert body["result"]["briefs"] == []


def test_read_research_briefs_with_exposure_rejects_invalid_pct():
    app = _load_app()
    resp = app.lambda_handler(
        _event(
            {
                "name": "read_research_briefs_with_exposure",
                "arguments": {"min_exposure_pct": 120},
            },
            persona="fsi_advisor",
        ),
        None,
    )
    body = json.loads(resp["body"])
    assert body["error"]["code"] == -32602
