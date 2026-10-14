"""Multi-vendor Household merger tests — Task 14.

AC7.2, AC7.4, AC7.5, AC7.7, AC7.8, AC7.9.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from m7_schema_translators import to_canonical_household_multi
from m7_schema_translators.household_multi import (
    _format_missing,
    _format_role_mismatch,
)


def _sf() -> dict:
    return {
        "household_id": "HH-SF-001",
        "name": "Example Household",
        "members": [
            {"account_id": "001CLIENT0001", "role": "Primary"},
            {"account_id": "001CLIENT0002", "role": "Spouse"},
        ],
        "account_ids": "A1;A2",
    }


def _orion() -> dict:
    return {
        "householdId": "ORIONHH-001",
        "householdName": "Example Household",
        "members": [
            {"clientId": "CLI-001", "role": "primary"},
            {"clientId": "CLI-002", "role": "spouse"},
        ],
        "linkedAccounts": [{"accountId": "A-001"}, {"accountId": "A-002"}],
    }


def _schwab() -> dict:
    return {
        "masterAccountNumber": "MA-001",
        "name": "Example Household",
        "linkedAccountHolders": [
            {"accountHolderId": "H-001", "role": "PRIMARY"},
            {"accountHolderId": "H-002", "role": "SPOUSE"},
        ],
        "linkedAccounts": [
            {"accountNumber": "11111111"},
            {"accountNumber": "22222222"},
        ],
    }


_TS = datetime(2026, 4, 26, 12, 0, 0, tzinfo=timezone.utc)


def test_sf_only_multi_entry_populates_reconciliation():
    """Multi-vendor entry point always populates `reconciliation` (sources_agree=True with one vendor)."""
    hh, note = to_canonical_household_multi({"salesforce_fsc": _sf()}, _TS)
    assert hh.reconciliation is not None
    assert hh.reconciliation.sources_agree is True
    assert hh.reconciliation.discrepancies == []
    assert "multi_vendor_reconciliation_performed" in note.notes


def test_all_three_vendors_discrepancies():
    """Three vendors × 2 members each × 3 pairs × 2 directions = 12 missing discrepancies."""
    hh, _ = to_canonical_household_multi(
        {"salesforce_fsc": _sf(), "orion": _orion(), "schwab": _schwab()},
        _TS,
    )
    assert hh.reconciliation is not None
    assert len(hh.reconciliation.discrepancies) == 12
    # Sorted
    assert hh.reconciliation.discrepancies == sorted(
        hh.reconciliation.discrepancies
    )


def test_format_literals_exact_match():
    """AC7.5 — exact missing / role-mismatch format literals."""
    assert (
        _format_missing("c1", "primary", "orion", "schwab")
        == "member (client:c1, role:primary) present in orion but missing in schwab"
    )
    assert (
        _format_role_mismatch(
            "c1", "orion", "primary", "salesforce_fsc", "spouse"
        )
        == "role mismatch for client:c1 — orion:primary vs salesforce_fsc:spouse"
    )


def test_caller_provides_timestamp():
    """AC7.2 — caller provides `last_reconciled`; M7 does NOT read the clock."""
    hh, _ = to_canonical_household_multi({"salesforce_fsc": _sf()}, _TS)
    assert hh.reconciliation.last_reconciled == _TS


def test_rejects_unknown_vendor():
    with pytest.raises(ValueError):
        to_canonical_household_multi({"fidelity": {}}, _TS)


def test_rejects_empty_payloads():
    with pytest.raises(ValueError):
        to_canonical_household_multi({}, _TS)


def test_six_scenarios_coverage():
    """AC7.7 — 6 scenarios: {sfsc, orion, schwab, sfsc+orion, sfsc+schwab, all_three}."""
    scenarios = [
        {"salesforce_fsc": _sf()},
        {"orion": _orion()},
        {"schwab": _schwab()},
        {"salesforce_fsc": _sf(), "orion": _orion()},
        {"salesforce_fsc": _sf(), "schwab": _schwab()},
        {
            "salesforce_fsc": _sf(),
            "orion": _orion(),
            "schwab": _schwab(),
        },
    ]
    for payloads in scenarios:
        hh, note = to_canonical_household_multi(payloads, _TS)
        assert hh.reconciliation is not None
