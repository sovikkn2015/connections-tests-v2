"""Round-trip tests for SF FSC translators (Client, Household, Goal)."""

from __future__ import annotations

import copy
import math
from datetime import date
from uuid import UUID

import pytest

from m3_schema_registry import Client, Goal, GoalStatus, GoalType, Household

from m7_schema_translators import (
    MissingRequiredField,
    TypeCoercionError,
    UnknownEnumValue,
)
from m7_schema_translators.salesforce_fsc.client import (
    REVERSE_LOSSY_FIELDS as CLIENT_REV_LOSSY,
)
from m7_schema_translators.salesforce_fsc.client import (
    from_canonical_client,
    to_canonical_client,
)
from m7_schema_translators.salesforce_fsc.goal import (
    REVERSE_LOSSY_FIELDS as GOAL_REV_LOSSY,
)
from m7_schema_translators.salesforce_fsc.goal import (
    from_canonical_goal,
    to_canonical_goal,
)
from m7_schema_translators.salesforce_fsc.household import (
    from_canonical_household,
    to_canonical_household,
)


def _sf_client_minimal() -> dict:
    return {
        "account_id": "001AAAAAAAAAAAA",
        "name": "Minimal Example",
        "record_type_name": "PersonAccount",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-01-02T00:00:00Z",
        "firm_id": "FIRM-001",
        "jurisdiction": "US",
    }


def _sf_client_fully_populated() -> dict:
    return {
        "account_id": "001FULLPOPULATED",
        "name": "Alice Example",
        "record_type_name": "PersonAccount",
        "owner_id": "005OWNER0000001",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-06-01T00:00:00Z",
        "firm_id": "FIRM-001",
        "household_id": "HH001",
        "client_archetype": "hnw",
        "jurisdiction": "US-CA",
        "account_ids": "A1;A2;A3",
        "kyc_status": "Verified",
        "kyc_last_completed": "2024-02-15",
        "last_ssn_digits": "1234",
        "risk_tolerance": "moderate",
        "investment_objectives": "growth;income",
        "time_horizon": "long_term",
        "annual_income": "100k-250k",
        "net_worth": "1m-5m",
        "liquid_net_worth": "500k-1m",
        "tax_bracket": "32",
        "pii_classification": "confidential",
        "person_account": True,
        "contact_id": "003CON000000001",
        "first_name": "Alice",
        "last_name": "Example",
        "email": "alice@example.test",
        "phone": "555-555-1212",
        "birthdate": "1980-03-15",
    }


def _sf_client_business_account() -> dict:
    return {
        "account_id": "001BIZACCOUNT1",
        "name": "Acme Holdings LLC",
        "record_type_name": "Business Account",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-02-01T00:00:00Z",
        "firm_id": "FIRM-002",
        "jurisdiction": "US",
        "tax_id": "12-3456789",
    }


def _sf_client_edge_case() -> dict:
    d = _sf_client_minimal()
    d["client_archetype"] = "unusual_but_valid"
    return d


@pytest.mark.parametrize(
    "fixture",
    [
        _sf_client_minimal(),
        _sf_client_fully_populated(),
        _sf_client_business_account(),
        _sf_client_edge_case(),
    ],
)
def test_client_to_canonical_type_invariants(fixture):
    """Appendix A T1 — type invariants."""
    c, note = to_canonical_client(fixture)
    assert isinstance(c, Client)
    assert isinstance(c.canonical_id, UUID)
    assert isinstance(c.firm_id, UUID)
    assert c.advisor_ref is None or isinstance(c.advisor_ref, UUID)
    assert c.household_ref is None or isinstance(c.household_ref, UUID)
    assert isinstance(c.accounts, list)
    assert all(isinstance(a, UUID) for a in c.accounts)
    assert isinstance(c.source_id, str) and len(c.source_id) > 0
    assert c.source_system == "salesforce_fsc"
    assert c.archetype is None or isinstance(c.archetype, str)


def test_client_idempotent():
    """AC1.3 — two calls, identical input, byte-identical canonical JSON."""
    fixture = _sf_client_fully_populated()
    c1, n1 = to_canonical_client(fixture)
    c2, n2 = to_canonical_client(fixture)
    assert c1.model_dump_json() == c2.model_dump_json()
    assert (
        n1.sorted_copy().model_dump_json()
        == n2.sorted_copy().model_dump_json()
    )


def test_client_no_input_mutation():
    """AC1.6 — input dict not mutated."""
    fixture = _sf_client_fully_populated()
    snapshot = copy.deepcopy(fixture)
    _ = to_canonical_client(fixture)
    assert fixture == snapshot


def test_client_pii_passthrough():
    """AC14.5 — PII fields carried through unchanged."""
    fixture = _sf_client_fully_populated()
    c, _ = to_canonical_client(fixture)
    assert c.email == "alice@example.test"
    assert c.phone == "555-555-1212"
    assert c.date_of_birth == date(1980, 3, 15)
    assert c.ssn_last_four == "1234"


def test_client_business_account_no_contact_fields():
    """T1 — Business Account → individual-PII fields must be None."""
    c, _ = to_canonical_client(_sf_client_business_account())
    assert c.first_name is None
    assert c.last_name is None
    assert c.email is None
    assert c.phone is None
    assert c.date_of_birth is None


def test_client_unknown_record_type_raises():
    fixture = _sf_client_minimal()
    fixture["record_type_name"] = "MadeUpType"
    with pytest.raises(UnknownEnumValue) as exc:
        to_canonical_client(fixture)
    assert exc.value.reason_code == "unknown_enum_value"


def test_client_vendor_id_invalid_chars():
    """AC10.8 — vendor ID with `:` triggers vendor_id_invalid_chars."""
    fixture = _sf_client_minimal()
    fixture["account_id"] = "bad:id:with:colons"
    with pytest.raises(TypeCoercionError) as exc:
        to_canonical_client(fixture)
    assert exc.value.reason_code == "vendor_id_invalid_chars"


def test_client_archetype_unknown_passes_through():
    """v0.2.0 — archetype has NO validator. Unknown string passes through."""
    fixture = _sf_client_minimal()
    fixture["client_archetype"] = "rogue_value_that_isnt_validated"
    c, _ = to_canonical_client(fixture)
    assert c.archetype == "rogue_value_that_isnt_validated"


def test_client_from_canonical_pii_preserved():
    fixture = _sf_client_fully_populated()
    c, _ = to_canonical_client(fixture)
    v, note = from_canonical_client(c)
    assert v.email == "alice@example.test"
    assert v.phone == "555-555-1212"
    assert v.birthdate == date(1980, 3, 15)
    assert note.direction == "from_canonical"
    assert set(note.fields_dropped) == CLIENT_REV_LOSSY


def _sf_household_simple() -> dict:
    return {
        "household_id": "HH-SF-001",
        "name": "Example Family",
        "members": [
            {"account_id": "001AAAAAAAAAA01", "role": "Primary"},
            {"account_id": "001AAAAAAAAAA02", "role": "Spouse"},
        ],
        "account_ids": "A1;A2",
    }


def test_household_sf_type_invariants():
    """Appendix A T2 — client_ref / account_ref are str per M3."""
    canonical, note = to_canonical_household(_sf_household_simple())
    assert isinstance(canonical, Household)
    assert isinstance(canonical.canonical_id, UUID)
    assert canonical.primary_source == "salesforce_fsc"
    for m in canonical.members:
        assert isinstance(m.client_ref, str)
        assert m.source == "salesforce_fsc"
    for a in canonical.accounts:
        assert isinstance(a.account_ref, str)
    assert (
        canonical.vendor_mappings.salesforce_fsc.grouping_type == "relationship"
    )
    assert canonical.reconciliation is None  # AC7.8


def test_household_sf_single_vendor_no_reconciliation_note():
    _, note = to_canonical_household(_sf_household_simple())
    assert "single_vendor_no_reconciliation" in note.notes


def test_household_sf_reverse_returns_none_when_no_mapping():
    """AC7.6 — reverse returns (None, note) when SF mapping absent."""
    canonical, _ = to_canonical_household(_sf_household_simple())
    c2 = canonical.model_copy(
        update={
            "vendor_mappings": canonical.vendor_mappings.model_copy(
                update={"salesforce_fsc": None}
            )
        }
    )
    v, note = from_canonical_household(c2)
    assert v is None
    assert note.direction == "from_canonical"


def test_household_sf_reverse_roundtrip():
    canonical, _ = to_canonical_household(_sf_household_simple())
    v, _ = from_canonical_household(canonical)
    assert v is not None
    assert v.household_id == "HH-SF-001"
    assert len(v.members) == 2


def _sf_goal_minimal() -> dict:
    return {
        "goal_id": "FG001",
        "name": "Retire at 65",
        "goal_type": "Retirement",
        "status": "On Track",
        "target_amount": 2000000.0,
        "current_amount": 500000.0,
        "target_date": "2050-01-01",
        "priority": "high",
        "client_account_id": "001CLIENT00001",
        "as_of_date": "2024-06-01",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-06-01T00:00:00Z",
    }


def test_goal_type_invariants():
    g, _ = to_canonical_goal(_sf_goal_minimal())
    assert isinstance(g, Goal)
    assert isinstance(g.canonical_id, UUID)
    assert isinstance(g.client_ref, UUID)
    assert g.household_ref is None or isinstance(g.household_ref, UUID)
    assert isinstance(g.goal_type, GoalType)
    assert isinstance(g.status, GoalStatus)
    assert g.funding_pct is not None
    assert math.isclose(g.funding_pct, 25.0, abs_tol=1e-9)


def test_goal_all_types_roundtrip():
    goal_types = [
        "Retirement",
        "Education",
        "Home Purchase",
        "Emergency Fund",
        "Wealth Transfer",
        "Charitable Giving",
        "Debt Payoff",
        "Major Purchase",
        "Income Replacement",
        "Legacy",
        "Custom",
    ]
    statuses = ["On Track", "At Risk", "Behind", "Achieved", "Abandoned"]
    for gt in goal_types:
        for st in statuses:
            fixture = _sf_goal_minimal()
            fixture["goal_type"] = gt
            fixture["status"] = st
            g, _ = to_canonical_goal(fixture)
            assert isinstance(g.goal_type, GoalType)
            assert isinstance(g.status, GoalStatus)


def test_goal_funding_pct_reverse_lossy():
    assert "funding_pct" in GOAL_REV_LOSSY


def test_goal_reverse_money_precision():
    g, _ = to_canonical_goal(_sf_goal_minimal())
    v, _ = from_canonical_goal(g)
    assert math.isclose(v.target_amount, 2000000.0, abs_tol=1e-6)
    assert math.isclose(v.current_amount, 500000.0, abs_tol=1e-6)
