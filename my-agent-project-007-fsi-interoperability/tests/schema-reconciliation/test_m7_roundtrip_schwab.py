"""Round-trip tests for Schwab translators (Holding, TaxLot, Household)."""

from __future__ import annotations

import math
from uuid import UUID

import pytest
from pydantic import ValidationError

from m3_schema_registry import (
    AccountType,
    CostBasisMethod,
    Holding,
    Household,
)

from m7_schema_translators import CostBasisUnmappable
from m7_schema_translators.schwab.holding import (
    from_canonical_holding,
    to_canonical_holding,
)
from m7_schema_translators.schwab.household import (
    from_canonical_household,
    to_canonical_household,
)
from m7_schema_translators.schwab.taxlot import (
    from_canonical_taxlot,
    to_canonical_taxlot,
)


def _schwab_taxlot_minimal() -> dict:
    return {
        "lotId": "SCH-LOT-001",
        "symbol": "AAPL",
        "acquisitionDate": "2022-01-15",
        "acquisitionPrice": 150.0,
        "quantity": 100.0,
        "costBasisMethod": "SpecificLot",
        "costBasisAmount": 15000.0,
        "holdingPeriod": "LT",
    }


def _schwab_position_fully_populated() -> dict:
    return {
        "id": "SCH-POS-001",
        "accountNumber": "12345678",
        "accountHolderId": "ACH-001",
        "symbol": "AAPL",
        "cusip": "037833100",
        "description": "Apple Inc.",
        "assetClass": "EQUITY",
        "quantity": 100.0,
        "marketValue": 18000.0,
        "costBasis": 15000.0,
        "unrealizedGainLoss": 3000.0,
        "unrealizedGainLossPct": 0.2,
        "currency": "USD",
        "asOfDate": "2024-06-01",
        "accountType": "INDIVIDUAL",
        "jurisdiction": "US",
        "taxLots": [_schwab_taxlot_minimal()],
    }


def _schwab_position_dollar_prefixed() -> dict:
    fixture = _schwab_position_fully_populated()
    fixture["marketValue"] = "$18,000.00"
    fixture["costBasis"] = "$15,000.00"
    return fixture


def _schwab_master_account() -> dict:
    return {
        "masterAccountNumber": "MA-001",
        "name": "Example Master Account",
        "linkedAccountHolders": [
            {"accountHolderId": "H-001", "role": "PRIMARY"},
            {"accountHolderId": "H-002", "role": "SPOUSE"},
        ],
        "linkedAccounts": [
            {"accountNumber": "12345678"},
            {"accountNumber": "87654321"},
        ],
    }


def test_schwab_holding_type_invariants():
    h, _ = to_canonical_holding(_schwab_position_fully_populated())
    assert isinstance(h, Holding)
    assert isinstance(h.canonical_id, UUID)
    assert isinstance(h.account_ref, str)
    assert h.client_ref is None or isinstance(h.client_ref, str)
    assert h.market_value_includes_accrued is False
    assert h.account_type == AccountType.TAXABLE


def test_schwab_holding_dollar_prefix_stripped():
    h, _ = to_canonical_holding(_schwab_position_dollar_prefixed())
    assert math.isclose(h.market_value, 18000.0, abs_tol=1e-6)
    assert math.isclose(h.cost_basis, 15000.0, abs_tol=1e-6)


def test_schwab_holding_ugl_pct_derived():
    h, note = to_canonical_holding(_schwab_position_fully_populated())
    assert math.isclose(h.unrealized_gain_loss_pct, 20.0, abs_tol=1e-9)
    assert "unrealized_gain_loss_pct" in note.fields_derived


def test_schwab_holding_ira_label_ambiguous_note():
    fixture = _schwab_position_fully_populated()
    fixture["accountType"] = "IRA"
    _, note = to_canonical_holding(fixture)
    assert "schwab_ira_label_ambiguous" in note.notes


def test_schwab_holding_8_digit_pattern():
    fixture = _schwab_position_fully_populated()
    fixture["accountNumber"] = "123"
    with pytest.raises(ValidationError):
        to_canonical_holding(fixture)


def test_schwab_taxlot_cost_basis_never_null():
    lot, note = to_canonical_taxlot(
        _schwab_taxlot_minimal(),
        parent_position_id="SCH-POS-001",
        parent_account_type="taxable",
        parent_security_class="equity",
    )
    assert lot.cost_basis_method == CostBasisMethod.SPECIFIC_LOT
    assert lot.source_cost_basis_method == "SpecificLot"
    assert note.cost_basis_source.method_origin == "vendor_reported"


def test_schwab_taxlot_vendor_silent_uses_default():
    fixture = _schwab_taxlot_minimal()
    fixture["costBasisMethod"] = None
    lot, note = to_canonical_taxlot(
        fixture,
        parent_position_id="SCH-POS-001",
        parent_account_type="taxable",
        parent_security_class="equity",
    )
    assert lot.cost_basis_method == CostBasisMethod.SPECIFIC_LOT
    assert lot.source_cost_basis_method is None
    assert note.cost_basis_source.method_origin == "vendor_default"


def test_schwab_taxlot_holding_ref_is_str():
    lot, _ = to_canonical_taxlot(
        _schwab_taxlot_minimal(),
        parent_position_id="SCH-POS-001",
        parent_account_type="taxable",
        parent_security_class="equity",
    )
    assert isinstance(lot.holding_ref, str)
    assert isinstance(lot.lot_id, UUID)


@pytest.mark.xfail(
    reason="Schwab UK cost-basis PENDING SME — IMPL-06 follow-up"
)
def test_schwab_uk_specific_lot_ambiguous():
    fixture = _schwab_taxlot_minimal()
    with pytest.raises(CostBasisUnmappable) as exc:
        to_canonical_taxlot(
            fixture,
            parent_position_id="SCH-POS-UK",
            parent_account_type="taxable",
            parent_security_class="equity",
            parent_jurisdiction="UK",
        )
    assert exc.value.reason_code == "ambiguous_mapping"


def test_schwab_household_type_invariants():
    canonical, _ = to_canonical_household(_schwab_master_account())
    assert isinstance(canonical, Household)
    assert canonical.primary_source == "schwab"
    assert all(isinstance(m.client_ref, str) for m in canonical.members)
    assert all(isinstance(a.account_ref, str) for a in canonical.accounts)
    assert canonical.vendor_mappings.schwab.grouping_type == "custodial"


def test_schwab_household_reverse():
    canonical, _ = to_canonical_household(_schwab_master_account())
    v, _ = from_canonical_household(canonical)
    assert v is not None
    assert v.masterAccountNumber == "MA-001"
    assert len(v.linkedAccountHolders) == 2
