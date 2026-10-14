"""Integration test for Narrative 3 — system-originated volatility alert.

Exercises the full in-process pipeline:

  ComplianceSweepInput(shock event)
    -> compliance_sweep.run()
    -> fans out to 3 households
    -> per-household compliance_screening ALLOW decisions
    -> writes 3 Client_Inquiry__c rows (2 auto-send, 1 RM-review)
    -> writes 3 VOLATILITY_ALERT_RAISED audit rows
    -> writes DynamoDB idempotency marker

The SQS/EventBridge side (monitor.py + sweep_dispatcher.py) is covered in
`tests/unit/lambdas/` by dedicated unit tests that mock boto3. This
integration test is the "sweep actually runs end-to-end on the skill
layer" proof — one live path, no LLM mocks, real Pydantic validation,
real MNPI scrubbing, real compliance rules.
"""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from openclaw.skills import get_shared_mock_client, reset_shared_mock_client
from openclaw.skills.compliance_sweep import ComplianceSweepInput, run


@pytest.mark.asyncio
async def test_narrative_3_full_sweep_writes_3_inquiries_and_3_audit_rows():
    """Full Narrative 3 trace: shock -> 3 households -> 2 auto / 1 review."""
    reset_shared_mock_client()
    shared = get_shared_mock_client()

    audit_rows_written: List[Dict[str, Any]] = []
    inquiry_rows_written: List[Dict[str, Any]] = []
    dynamo_items: Dict[str, Dict[str, Any]] = {}

    async def _soql_positions(_args):
        return {
            "records": [
                # All below the 10% house concentration limit so compliance
                # ALLOWs each — tests the happy-path pipeline end-to-end.
                {
                    "Household__c": "HH_PATEL",
                    "Client_Contact__c": "003_PATEL",
                    "Position_Size_Pct__c": 8.5,
                },
                {
                    "Household__c": "HH_OKAFOR",
                    "Client_Contact__c": "003_OKAFOR",
                    "Position_Size_Pct__c": 7.8,
                },
                {
                    "Household__c": "HH_LEE",
                    "Client_Contact__c": "003_LEE",
                    "Position_Size_Pct__c": 6.1,
                },
            ]
        }

    async def _read_prefs(args):
        household = args.get("where", {}).get("Household__c")
        prefs = {
            "HH_PATEL": True,
            "HH_OKAFOR": True,
            "HH_LEE": False,
        }
        if household in prefs:
            return {
                "record": {
                    "Household__c": household,
                    "auto_send_volatility_alert__c": prefs[household],
                }
            }
        return {"record": None}

    async def _create_inquiry(args):
        fields = dict(args.get("fields", {}))
        new_id = f"a0I_inq_{len(inquiry_rows_written) + 1:03d}"
        inquiry_rows_written.append({"Id": new_id, **fields})
        return {"Id": new_id}

    async def _write_audit(args):
        row = dict(args.get("record", {}))
        audit_id = f"AUDIT_{len(audit_rows_written) + 1:04d}"
        audit_rows_written.append({"Id": audit_id, **row})
        return {"Id": audit_id, "success": True}

    async def _ddb_get(args):
        key = args.get("key", {}).get("event_id")
        if key in dynamo_items:
            return {"Item": dynamo_items[key]}
        return {}

    async def _ddb_put(args):
        item = dict(args.get("item", {}))
        dynamo_items[item["event_id"]] = item
        return {"ok": True}

    shared.mock_router.register("salesforce-crm", "run_soql", _soql_positions)
    shared.mock_router.register("salesforce-crm", "read_object", _read_prefs)
    shared.mock_router.register("salesforce-crm", "create_object", _create_inquiry)
    shared.mock_router.register("salesforce-crm", "write_audit_log", _write_audit)
    shared.mock_router.register("dynamodb", "get_item", _ddb_get)
    shared.mock_router.register("dynamodb", "put_item", _ddb_put)

    # First firing: NVDA -6.8% — all three households above 5% threshold.
    out = await run(
        ComplianceSweepInput(
            ticker="NVDA",
            price_change_pct=-6.8,
            threshold_pct=5.0,
            event_id="narr3_evt_001",
            session_id="sess_narr3",
            correlation_id="corr_narr3",
        ),
        mcp=shared,
    )

    # End-to-end expectations.
    assert out.skipped_idempotent is False
    assert out.households_scanned == 3
    assert out.alerts_raised == 3
    assert out.auto_send_count == 2
    assert out.rm_review_count == 1
    assert len(out.inquiry_ids) == 3
    assert out.errors == []

    # All three inquiries went to SF with the right picklist values.
    assert len(inquiry_rows_written) == 3
    for inq in inquiry_rows_written:
        assert inq["Type__c"] == "alert"
        assert inq["Channel__c"] in {"Email", "WhatsApp", "SMS", "Web"}
        assert inq["Ticker_Mentions__c"] == "NVDA"
        assert "NVDA" in inq["Inquiry_Text__c"]
        assert "-6.8%" in inq["Inquiry_Text__c"]

    # Auto-send flag split.
    auto_send_ids = [
        inq["Client_Contact_Id__c"]
        for inq in inquiry_rows_written
        if inq["Auto_Send_Eligible__c"]
    ]
    rm_review_ids = [
        inq["Client_Contact_Id__c"]
        for inq in inquiry_rows_written
        if not inq["Auto_Send_Eligible__c"]
    ]
    assert sorted(auto_send_ids) == ["003_OKAFOR", "003_PATEL"]
    assert rm_review_ids == ["003_LEE"]

    # Three audit rows, one per inquiry. All with Action__c=VOLATILITY_ALERT_RAISED.
    assert len(audit_rows_written) == 3
    for audit in audit_rows_written:
        assert audit["Action__c"] == "VOLATILITY_ALERT_RAISED"
        assert audit["Gate_Trace__c"] == [
            {"gate": "compliance_sweep", "outcome": "ok"}
        ]
        assert audit["Payload__c"]["ticker"] == "NVDA"
        assert audit["Payload__c"]["auto_send_eligible"] in {True, False}

    # Idempotency marker was written.
    assert "narr3_evt_001" in dynamo_items
    assert dynamo_items["narr3_evt_001"]["alerts"] == 3

    # Second firing (replay, same event_id) — no new writes, no new audit rows.
    out2 = await run(
        ComplianceSweepInput(
            ticker="NVDA",
            price_change_pct=-6.8,
            threshold_pct=5.0,
            event_id="narr3_evt_001",
            session_id="sess_narr3_replay",
            correlation_id="corr_narr3_replay",
        ),
        mcp=shared,
    )
    assert out2.skipped_idempotent is True
    assert out2.households_scanned == 0
    assert len(inquiry_rows_written) == 3  # unchanged
    assert len(audit_rows_written) == 3  # unchanged
