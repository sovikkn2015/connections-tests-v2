"""Round-trip tests for eMoney PlanSummary translator."""

from __future__ import annotations

import math
from uuid import UUID

import pytest
from pydantic import ValidationError

from m3_schema_registry import PlanSummary

from m7_schema_translators import MissingRequiredField, UnknownEnumValue
from m7_schema_translators.emoney.plan_summary import (
    REVERSE_LOSSY_FIELDS,
    from_canonical_plan_summary,
    to_canonical_plan_summary,
)


def _emoney_plan_fully_populated() -> dict:
    return {
        "planId": "PL-001",
        "scenarioId": "SC-001",
        "clientId": "CLI-001",
        "householdId": "HH-001",
        "planName": "Alice Example Plan",
        "planType": "Comprehensive",
        "probabilityOfSuccess": 82.5,
        "asOfDate": "2024-06-01",
        "totalAssets": 1200000.0,
        "totalLiabilities": 200000.0,
        "retirementGoal": {
            "amount": 2000000.0,
            "targetDate": "2050-01-01",
            "incomeGap": -5000.0,
        },
        "monteCarlo": {"successPct": 82.5, "iterations": 10000},
        "annualSavingsRate": 0.15,
        "annualSpending": 80000.0,
        "socialSecurityEstimate": 30000.0,
        "pensionIncome": 0.0,
        "goalIds": ["G001", "G002"],
        "assumptions": {
            "inflation": 0.025,
            "returnAssumption": 0.07,
            "lifeExpectancy": 90,
            "retirementAge": 65,
            "taxRate": 0.24,
        },
        "recommendations": [
            {
                "category": "retirement",
                "description": "Increase 401k contribution",
                "priority": "high",
            }
        ],
        "createdAt": "2024-01-01T00:00:00Z",
        "updatedAt": "2024-06-01T00:00:00Z",
    }


def test_emoney_type_invariants():
    """Appendix A T7."""
    p, _ = to_canonical_plan_summary(_emoney_plan_fully_populated())
    assert isinstance(p, PlanSummary)
    assert isinstance(p.canonical_id, UUID)
    assert isinstance(p.client_ref, UUID)
    assert p.household_ref is None or isinstance(p.household_ref, UUID)
    assert all(isinstance(g, UUID) for g in p.goals)
    assert 0.0 <= p.probability_of_success <= 100.0
    assert p.vendor_mappings.emoney is not None


def test_emoney_net_worth_derived():
    p, note = to_canonical_plan_summary(_emoney_plan_fully_populated())
    assert p.net_worth == 1000000.0
    assert "net_worth" in note.fields_derived
    assert "emoney_net_worth_derived" in note.notes


def test_emoney_net_worth_reverse_lossy():
    assert "net_worth" in REVERSE_LOSSY_FIELDS


def test_emoney_rejects_raw_plan_body():
    """M4 MNPI policy — raw plan body rejected at vendor model (extra=forbid)."""
    fixture = _emoney_plan_fully_populated()
    fixture["fullPlanBody"] = {"detailed_cashflow": "raw_mnpi_data"}
    with pytest.raises(ValidationError):
        to_canonical_plan_summary(fixture)


def test_emoney_missing_client_id_raises():
    fixture = _emoney_plan_fully_populated()
    fixture["clientId"] = ""
    with pytest.raises((ValidationError, MissingRequiredField)):
        to_canonical_plan_summary(fixture)


def test_emoney_all_plan_types_map():
    for pt in [
        "Comprehensive",
        "Retirement",
        "Education",
        "Estate",
        "Tax",
        "Insurance",
    ]:
        fixture = _emoney_plan_fully_populated()
        fixture["planType"] = pt
        p, _ = to_canonical_plan_summary(fixture)
        assert p.plan_type is not None


def test_emoney_unknown_plan_type_raises():
    fixture = _emoney_plan_fully_populated()
    fixture["planType"] = "MadeUp"
    with pytest.raises(UnknownEnumValue):
        to_canonical_plan_summary(fixture)


def test_emoney_reverse():
    p, _ = to_canonical_plan_summary(_emoney_plan_fully_populated())
    v, note = from_canonical_plan_summary(p)
    assert v.planId == "PL-001"
    assert math.isclose(v.probabilityOfSuccess, 82.5, abs_tol=1e-9)
    assert set(note.fields_dropped) == REVERSE_LOSSY_FIELDS
