"""
M7 SFDC PascalCase alias handling — regression guards for v0.3.1.

Covers three contract rules on `SalesforceFSCAccountContact`,
`SalesforceFSCHousehold`, `SalesforceFSCHouseholdMember`, and
`SalesforceFSCFinancialGoal`:

1. Happy path — raw SFDC PascalCase payloads construct successfully.
2. `extra="forbid"` still rejects unknown top-level keys (Steering Rule 32).
3. Backward-compat — canonical snake_case field names still accepted
   (code that already uses snake_case keeps working).

See `src/m7_schema_translators/DECISION-LOG.md` for the v0.3.1 decision.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from m7_schema_translators.salesforce_fsc.models import (
    SalesforceFSCAccountContact,
    SalesforceFSCFinancialGoal,
    SalesforceFSCHousehold,
    SalesforceFSCHouseholdMember,
)


# ---------------------------------------------------------------------------
# SalesforceFSCAccountContact
# ---------------------------------------------------------------------------


def _account_pascal() -> dict[str, object]:
    return {
        "Id": "001A000001234567",
        "Name": "Placeholder Name",
        "RecordTypeName": "PersonAccount",
        "OwnerId": "005A000000000001",
        "CreatedDate": "2024-01-01T00:00:00Z",
        "LastModifiedDate": "2024-06-01T00:00:00Z",
        "FinServ__FirmId__c": "firm-42",
        "FinServ__HouseholdId__c": "001H000000000001",
        "FinServ__Jurisdiction__c": "US",
        "FirstName": "Jane",
        "LastName": "Doe",
        "Email": "jane@example.com",
    }


def _account_snake() -> dict[str, object]:
    return {
        "account_id": "001A000001234567",
        "name": "Placeholder Name",
        "record_type_name": "PersonAccount",
        "owner_id": "005A000000000001",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-06-01T00:00:00Z",
        "firm_id": "firm-42",
        "household_id": "001H000000000001",
        "jurisdiction": "US",
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane@example.com",
    }


def test_account_accepts_pascal_case_payload() -> None:
    m = SalesforceFSCAccountContact(**_account_pascal())
    assert m.account_id == "001A000001234567"
    assert m.first_name == "Jane"
    assert m.household_id == "001H000000000001"
    assert m.email == "jane@example.com"


def test_account_accepts_snake_case_payload_backward_compat() -> None:
    m = SalesforceFSCAccountContact(**_account_snake())
    assert m.account_id == "001A000001234567"
    assert m.first_name == "Jane"
    assert m.household_id == "001H000000000001"


def test_account_pascal_and_snake_produce_equivalent_model() -> None:
    p = SalesforceFSCAccountContact(**_account_pascal())
    s = SalesforceFSCAccountContact(**_account_snake())
    assert p.model_dump() == s.model_dump()


def test_account_rejects_unknown_field_extra_forbid() -> None:
    payload = _account_pascal()
    payload["RandomField"] = "surprise"
    with pytest.raises(ValidationError) as exc_info:
        SalesforceFSCAccountContact(**payload)
    assert any(
        err["type"] == "extra_forbidden" for err in exc_info.value.errors()
    )


def test_account_rejects_unknown_snake_case_field() -> None:
    payload = _account_snake()
    payload["totally_unknown"] = "nope"
    with pytest.raises(ValidationError) as exc_info:
        SalesforceFSCAccountContact(**payload)
    assert any(
        err["type"] == "extra_forbidden" for err in exc_info.value.errors()
    )


# ---------------------------------------------------------------------------
# SalesforceFSCHousehold + SalesforceFSCHouseholdMember
# ---------------------------------------------------------------------------


def test_household_accepts_pascal_case() -> None:
    h = SalesforceFSCHousehold(
        **{
            "Id": "001H000000000001",
            "Name": "Smith Family",
            "Members": [{"AccountId": "001A00000000A001", "Role": "Primary"}],
            "FinServ__AccountIds__c": "001A00000000A001;001A00000000A002",
        }
    )
    assert h.household_id == "001H000000000001"
    assert h.members[0].account_id == "001A00000000A001"
    assert h.members[0].role == "Primary"


def test_household_member_snake_case_backward_compat() -> None:
    m = SalesforceFSCHouseholdMember(account_id="001A00000000A001", role="Spouse")
    assert m.account_id == "001A00000000A001"


def test_household_rejects_unknown_field() -> None:
    with pytest.raises(ValidationError):
        SalesforceFSCHousehold(
            **{
                "Id": "001H000000000001",
                "Name": "Smith Family",
                "Members": [],
                "SurpriseField__c": "boom",
            }
        )


# ---------------------------------------------------------------------------
# SalesforceFSCFinancialGoal
# ---------------------------------------------------------------------------


def test_goal_accepts_pascal_case() -> None:
    g = SalesforceFSCFinancialGoal(
        **{
            "Id": "a0G000000000001",
            "Name": "Retirement",
            "FinServ__GoalType__c": "Retirement",
            "FinServ__Status__c": "On Track",
            "FinServ__TargetAmount__c": 1000000.0,
            "FinServ__TargetDate__c": "2045-01-01",
            "FinServ__Priority__c": "high",
            "FinServ__ClientAccountId__c": "001A000000000001",
            "FinServ__AsOfDate__c": "2024-06-01",
            "CreatedDate": "2024-01-01T00:00:00Z",
            "LastModifiedDate": "2024-06-01T00:00:00Z",
        }
    )
    assert g.goal_id == "a0G000000000001"
    assert g.goal_type == "Retirement"
    assert g.client_account_id == "001A000000000001"


def test_goal_snake_case_backward_compat() -> None:
    g = SalesforceFSCFinancialGoal(
        goal_id="a0G000000000001",
        name="Retirement",
        goal_type="Retirement",
        status="On Track",
        target_amount=1000000.0,
        target_date="2045-01-01",
        priority="high",
        client_account_id="001A000000000001",
        as_of_date="2024-06-01",
        created_date="2024-01-01T00:00:00Z",
        last_modified_date="2024-06-01T00:00:00Z",
    )
    assert g.goal_id == "a0G000000000001"
