"""Tests for compliance_sweep skill — Narrative 3 volatility fanout."""

from __future__ import annotations

from typing import Any, Dict, List

import pytest

from openclaw.skills.compliance_sweep import ComplianceSweepInput, run


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _register_dynamo(
    mock_mcp,
    *,
    seen_event_ids: set,
) -> List[Dict[str, Any]]:
    """Wire a simple in-memory DynamoDB shim onto the shared mock MCP.

    Returns the list of put_item bodies for assertion convenience.
    """
    put_log: List[Dict[str, Any]] = []

    async def _get_item(args):
        event_id = args.get("key", {}).get("event_id")
        if event_id in seen_event_ids:
            return {"Item": {"event_id": event_id}}
        return {}

    async def _put_item(args):
        item = args.get("item", {})
        seen_event_ids.add(item.get("event_id"))
        put_log.append(item)
        return {"ok": True}

    mock_mcp.mock_router.register("dynamodb", "get_item", _get_item)
    mock_mcp.mock_router.register("dynamodb", "put_item", _put_item)
    return put_log


def _register_positions(
    mock_mcp, rows: List[Dict[str, Any]]
) -> None:
    async def _run_soql(_args):
        return {"records": rows}

    mock_mcp.mock_router.register("salesforce-crm", "run_soql", _run_soql)


def _register_prefs(
    mock_mcp, prefs_by_household: Dict[str, bool]
) -> None:
    async def _read_object(args):
        where = args.get("where", {})
        hh = where.get("Household__c")
        if hh in prefs_by_household:
            return {
                "record": {
                    "Household__c": hh,
                    "auto_send_volatility_alert__c": prefs_by_household[hh],
                }
            }
        return {"record": None}

    mock_mcp.mock_router.register("salesforce-crm", "read_object", _read_object)


def _register_inquiry_writer(mock_mcp) -> List[Dict[str, Any]]:
    """Capture every Client_Inquiry__c create; return the list of fields."""
    captured: List[Dict[str, Any]] = []

    async def _create_object(args):
        fields = dict(args.get("fields", {}))
        captured.append(fields)
        return {"Id": f"a0I_inq_{len(captured):03d}"}

    mock_mcp.mock_router.register("salesforce-crm", "create_object", _create_object)
    return captured


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_idempotent_replay_returns_skipped_true(mock_mcp) -> None:
    """Second call with the same event_id must be a no-op."""
    seen: set = set()
    put_log = _register_dynamo(mock_mcp, seen_event_ids=seen)
    _register_positions(
        mock_mcp,
        [
            {
                "Household__c": "H001",
                "Client_Contact__c": "003_H001",
                "Position_Size_Pct__c": 6.0,
            }
        ],
    )
    _register_prefs(mock_mcp, {"H001": True})
    _register_inquiry_writer(mock_mcp)

    payload = ComplianceSweepInput(
        ticker="NVDA",
        price_change_pct=-7.5,
        threshold_pct=5.0,
        event_id="evt_dup_001",
        session_id="s",
        correlation_id="c",
    )

    first = await run(payload, mcp=mock_mcp)
    assert first.skipped_idempotent is False
    assert first.alerts_raised == 1
    assert first.households_scanned == 1
    assert len(put_log) == 1  # marker written

    second = await run(payload, mcp=mock_mcp)
    assert second.skipped_idempotent is True
    assert second.alerts_raised == 0
    assert second.households_scanned == 0
    assert second.inquiry_ids == []
    # Marker log is unchanged — no additional put_item on replay.
    assert len(put_log) == 1


@pytest.mark.asyncio
async def test_three_households_two_auto_send_one_review(mock_mcp) -> None:
    """Three matching households; two opted-in, one not. Count split."""
    _register_dynamo(mock_mcp, seen_event_ids=set())
    _register_positions(
        mock_mcp,
        [
            {
                "Household__c": "H001",
                "Client_Contact__c": "003_H001",
                "Position_Size_Pct__c": 6.0,
            },
            {
                "Household__c": "H002",
                "Client_Contact__c": "003_H002",
                "Position_Size_Pct__c": 7.5,
            },
            {
                "Household__c": "H003",
                "Client_Contact__c": "003_H003",
                "Position_Size_Pct__c": 8.2,
            },
        ],
    )
    _register_prefs(
        mock_mcp,
        {"H001": True, "H002": True, "H003": False},
    )
    captured = _register_inquiry_writer(mock_mcp)

    out = await run(
        ComplianceSweepInput(
            ticker="NVDA",
            price_change_pct=-6.3,
            threshold_pct=5.0,
            event_id="evt_three_001",
            session_id="s",
            correlation_id="c",
        ),
        mcp=mock_mcp,
    )

    assert out.households_scanned == 3
    assert out.alerts_raised == 3
    assert out.auto_send_count == 2
    assert out.rm_review_count == 1
    assert len(out.inquiry_ids) == 3

    # Every captured inquiry is of type 'alert' via the system_alert channel.
    assert all(f["Type__c"] == "alert" for f in captured)
    assert all(f["Channel__c"] == "Email" for f in captured)
    assert all(f["Ticker_Mentions__c"] == "NVDA" for f in captured)

    # Auto_Send_Eligible__c mirrors the preference map.
    auto_flags = {f["Client_Contact_Id__c"]: f["Auto_Send_Eligible__c"] for f in captured}
    assert auto_flags == {
        "003_H001": True,
        "003_H002": True,
        "003_H003": False,
    }


@pytest.mark.asyncio
async def test_compliance_deny_skips_household(mock_mcp, monkeypatch) -> None:
    """A DENY from compliance_screening must short-circuit the household.

    Patch the compliance_screening.run reference imported by compliance_sweep
    to return DENY for one specific household and ALLOW for others.
    """
    _register_dynamo(mock_mcp, seen_event_ids=set())
    _register_positions(
        mock_mcp,
        [
            {
                "Household__c": "H001",
                "Client_Contact__c": "003_H001",
                "Position_Size_Pct__c": 6.0,
            },
            {
                "Household__c": "H002",
                "Client_Contact__c": "003_H002_DENY",
                "Position_Size_Pct__c": 7.0,
            },
        ],
    )
    _register_prefs(mock_mcp, {"H001": True, "H002": True})
    captured = _register_inquiry_writer(mock_mcp)

    from openclaw.skills.compliance_screening.actions import (
        ComplianceDecision,
        ComplianceOutput,
    )
    from openclaw.skills import compliance_sweep as sweep_pkg

    async def _fake_compliance(payload, *, mcp=None):  # noqa: ARG001
        if payload.client_contact_id == "003_H002_DENY":
            return ComplianceOutput(
                decision=ComplianceDecision.DENY,
                reasons=["restricted_list:test"],
                restricted_list_hit=True,
                mnpi_flag=False,
                trading_window_open=True,
                concentration_ok=True,
                audit_row_id="AUDIT_DENY_001",
            )
        return ComplianceOutput(
            decision=ComplianceDecision.ALLOW,
            reasons=[],
            restricted_list_hit=False,
            mnpi_flag=False,
            trading_window_open=True,
            concentration_ok=True,
            audit_row_id=None,
        )

    monkeypatch.setattr(sweep_pkg.actions, "compliance_run", _fake_compliance)

    out = await run(
        ComplianceSweepInput(
            ticker="NVDA",
            price_change_pct=-5.5,
            threshold_pct=5.0,
            event_id="evt_deny_001",
            session_id="s",
            correlation_id="c",
        ),
        mcp=mock_mcp,
    )

    assert out.households_scanned == 2
    assert out.alerts_raised == 1
    # Only H001 was written. H002 was DENY-skipped.
    assert len(captured) == 1
    assert captured[0]["Client_Contact_Id__c"] == "003_H001"


@pytest.mark.asyncio
async def test_mnpi_redaction_on_notes(mock_mcp) -> None:
    """Free-form notes containing a dollar amount are scrubbed in Inquiry_Text__c."""
    _register_dynamo(mock_mcp, seen_event_ids=set())
    _register_positions(
        mock_mcp,
        [
            {
                "Household__c": "H001",
                "Client_Contact__c": "003_H001",
                "Position_Size_Pct__c": 6.0,
            }
        ],
    )
    _register_prefs(mock_mcp, {"H001": True})
    captured = _register_inquiry_writer(mock_mcp)

    out = await run(
        ComplianceSweepInput(
            ticker="NVDA",
            price_change_pct=-9.9,
            threshold_pct=5.0,
            event_id="evt_mnpi_001",
            session_id="s",
            correlation_id="c",
            notes="Desk chatter suggests $2.5M exposure across the book.",
        ),
        mcp=mock_mcp,
    )

    assert out.alerts_raised == 1
    assert len(captured) == 1
    body = captured[0]["Inquiry_Text__c"]
    # Dollar amount is scrubbed to sentinel.
    assert "$2.5M" not in body
    assert "[$REDACTED]" in body
    # The templated volatility header is still present.
    assert "Volatility alert: NVDA" in body
    assert "-9.9%" in body
