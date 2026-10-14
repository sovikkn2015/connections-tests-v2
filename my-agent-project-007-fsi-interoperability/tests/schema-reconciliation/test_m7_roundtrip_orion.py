"""Round-trip tests for Orion translators (Holding, Transaction, TaxLot, Household)."""

from __future__ import annotations

import math
from uuid import UUID

import pytest

from m3_schema_registry import (
    AccountType,
    CostBasisMethod,
    Holding,
    Household,
    Transaction,
    TransactionType,
)

from m7_schema_translators import UnknownEnumValue
from m7_schema_translators.orion.holding import (
    from_canonical_holding,
    to_canonical_holding,
)
from m7_schema_translators.orion.household import (
    from_canonical_household,
    to_canonical_household,
)
from m7_schema_translators.orion.taxlot import (
    from_canonical_taxlot,
    to_canonical_taxlot,
)
from m7_schema_translators.orion.transaction import (
    from_canonical_transaction,
    to_canonical_transaction,
)


def _orion_taxlot_minimal() -> dict:
    return {
        "lotId": "LOT-001",
        "symbol": "AAPL",
        "acquisitionDate": "2022-01-15",
        "acquisitionPrice": 150.0,
        "quantity": 100.0,
        "costBasisMethod": "SPECIFIC_LOT",
        "costBasisAmount": 15000.0,
        "holdingPeriod": "LONG_TERM",
        "unrealizedGainLoss": 5000.0,
    }


def _orion_position_fully_populated() -> dict:
    return {
        "positionId": "POS-001",
        "accountId": "ORION-ACCT-001",
        "clientId": "ORION-CLI-001",
        "symbol": "AAPL",
        "cusip": "037833100",
        "securityName": "Apple Inc.",
        "securityType": "equity",
        "quantity": 100.0,
        "marketValue": 18000.0,
        "includesAccruedInterest": False,
        "costBasis": 15000.0,
        "unrealizedGainLoss": 3000.0,
        "unrealizedGainLossPct": 20.0,
        "currency": "USD",
        "asOfDate": "2024-06-01",
        "accountType": "TAXABLE",
        "taxLots": [_orion_taxlot_minimal()],
    }


def _orion_position_minimal() -> dict:
    return {
        "positionId": "POS-002",
        "accountId": "ORION-ACCT-002",
        "symbol": None,
        "quantity": 0.0,
        "marketValue": 0.0,
        "asOfDate": "2024-06-01",
        "taxLots": [],
    }


def _orion_transaction_buy() -> dict:
    return {
        "transactionId": "TX-001",
        "accountId": "ORION-ACCT-001",
        "clientId": "ORION-CLI-001",
        "type": "BUY",
        "symbol": "AAPL",
        "cusip": "037833100",
        "securityName": "Apple Inc.",
        "quantity": 100.0,
        "price": 150.0,
        "amount": 15000.0,
        "commission": 5.0,
        "fees": 0.1,
        "netAmount": 15005.1,
        "tradeDate": "2022-01-15",
        "settlementDate": "2022-01-17",
        "settlementStatus": "SETTLED",
        "currency": "USD",
        "accountType": "TAXABLE",
        "createdAt": "2022-01-15T10:00:00Z",
    }


def _orion_household_simple() -> dict:
    return {
        "householdId": "ORIONHH-001",
        "householdName": "Example Household",
        "members": [
            {"clientId": "CLI-001", "role": "primary"},
            {"clientId": "CLI-002", "role": "spouse"},
        ],
        "linkedAccounts": [{"accountId": "A001"}, {"accountId": "A002"}],
    }


def test_orion_holding_type_invariants():
    """Appendix A T4."""
    h, _ = to_canonical_holding(_orion_position_fully_populated())
    assert isinstance(h, Holding)
    assert isinstance(h.canonical_id, UUID)
    assert isinstance(h.account_ref, str)
    assert h.client_ref is None or isinstance(h.client_ref, str)
    assert h.source_system == "orion"
    assert isinstance(h.market_value_includes_accrued, bool)
    assert h.account_type == AccountType.TAXABLE


def test_orion_holding_empty_taxlots():
    """Partial-data: empty taxLots[] → canonical tax_lots=[]."""
    h, _ = to_canonical_holding(_orion_position_minimal())
    assert h.tax_lots == []


def test_orion_holding_embedded_taxlots_translate():
    h, _ = to_canonical_holding(_orion_position_fully_populated())
    assert len(h.tax_lots) == 1
    assert h.tax_lots[0].cost_basis_method == CostBasisMethod.SPECIFIC_LOT
    assert h.tax_lots[0].source_cost_basis_method == "SPECIFIC_LOT"


def test_orion_holding_reverse():
    h, _ = to_canonical_holding(_orion_position_fully_populated())
    v, _ = from_canonical_holding(h)
    assert v.positionId == "POS-001"
    assert math.isclose(v.marketValue, 18000.0, abs_tol=1e-6)
    assert len(v.taxLots) == 1


def test_orion_transaction_id_and_source_id_are_separate():
    """v0.2.0 CRITICAL — transaction_id (UUID) ≠ source_id (str vendor ID)."""
    tx, _ = to_canonical_transaction(_orion_transaction_buy())
    assert isinstance(tx.transaction_id, UUID)
    assert isinstance(tx.source_id, str)
    assert tx.source_id == "TX-001"
    assert str(tx.transaction_id) != tx.source_id


def test_orion_transaction_type_invariants():
    """Appendix A T5 — account_ref is UUID."""
    tx, _ = to_canonical_transaction(_orion_transaction_buy())
    assert isinstance(tx, Transaction)
    assert isinstance(tx.transaction_id, UUID)
    assert isinstance(tx.account_ref, UUID)
    assert tx.client_ref is None or isinstance(tx.client_ref, UUID)
    assert tx.order_ref is None
    assert isinstance(tx.transaction_type, TransactionType)
    assert tx.source_transaction_type == "BUY"
    assert tx.trace_id is None


def test_orion_transaction_all_19_types_map():
    types = [
        "BUY", "SELL", "SELL_SHORT", "BUY_TO_COVER",
        "DIV", "INT", "FEE", "MGMT_FEE",
        "TRANSFER_IN", "TRANSFER_OUT", "DISTRIBUTION", "CONTRIBUTION",
        "WIRE_IN", "WIRE_OUT", "JOURNAL", "REINVEST",
        "ROC", "CORP_ACTION", "MARGIN_INT",
    ]
    for t in types:
        fixture = _orion_transaction_buy()
        fixture["transactionId"] = f"TX-{t}"
        fixture["type"] = t
        tx, _ = to_canonical_transaction(fixture)
        assert isinstance(tx.transaction_type, TransactionType)


def test_orion_transaction_reverse_preserves_source_id():
    tx, _ = to_canonical_transaction(_orion_transaction_buy())
    v, _ = from_canonical_transaction(tx)
    assert v.transactionId == "TX-001"
    assert v.type == "BUY"


def test_orion_transaction_order_ref_preserved_via_custom_attributes():
    """T5 — order_ref preserved in customAttributes."""
    import uuid

    from m7_schema_translators.shared.namespaces import ORDER_NS

    tx, _ = to_canonical_transaction(_orion_transaction_buy())
    order_uuid = uuid.uuid5(ORDER_NS, "orion:ORDER-001")
    tx2 = tx.model_copy(update={"order_ref": order_uuid})
    v, note = from_canonical_transaction(tx2)
    assert v.customAttributes is not None
    assert v.customAttributes["order_ref"] == str(order_uuid)
    assert "canonical_order_ref_preserved_in_custom_attributes" in note.notes


def test_orion_transaction_unknown_type_raises():
    fixture = _orion_transaction_buy()
    fixture["type"] = "INVENTED_TYPE"
    with pytest.raises(UnknownEnumValue):
        to_canonical_transaction(fixture)


def test_orion_taxlot_cost_basis_never_null():
    lot, note = to_canonical_taxlot(
        _orion_taxlot_minimal(),
        parent_position_id="POS-001",
        parent_account_type="taxable",
        parent_security_class="equity",
    )
    assert lot.cost_basis_method == CostBasisMethod.SPECIFIC_LOT
    assert lot.source_cost_basis_method == "SPECIFIC_LOT"
    assert note.cost_basis_source.method_origin == "vendor_reported"


def test_orion_taxlot_silent_vendor_uses_default():
    fixture = _orion_taxlot_minimal()
    fixture["costBasisMethod"] = None
    lot, note = to_canonical_taxlot(
        fixture,
        parent_position_id="POS-001",
        parent_account_type="taxable",
        parent_security_class="equity",
    )
    assert lot.cost_basis_method == CostBasisMethod.SPECIFIC_LOT
    assert lot.source_cost_basis_method is None
    assert note.cost_basis_source.method_origin == "vendor_default"


def test_orion_taxlot_holding_ref_is_str():
    """Appendix A T10 — holding_ref is str."""
    lot, _ = to_canonical_taxlot(
        _orion_taxlot_minimal(),
        parent_position_id="POS-001",
        parent_account_type="taxable",
        parent_security_class="equity",
    )
    assert isinstance(lot.holding_ref, str)
    assert isinstance(lot.lot_id, UUID)


def test_orion_household_type_invariants():
    canonical, _ = to_canonical_household(_orion_household_simple())
    assert isinstance(canonical, Household)
    assert canonical.primary_source == "orion"
    assert all(isinstance(m.client_ref, str) for m in canonical.members)
    assert all(isinstance(a.account_ref, str) for a in canonical.accounts)
    assert (
        canonical.vendor_mappings.orion.grouping_type == "portfolio_management"
    )
    assert canonical.reconciliation is None


def test_orion_household_reverse():
    canonical, _ = to_canonical_household(_orion_household_simple())
    v, _ = from_canonical_household(canonical)
    assert v is not None
    assert v.householdId == "ORIONHH-001"
    assert len(v.members) == 2
