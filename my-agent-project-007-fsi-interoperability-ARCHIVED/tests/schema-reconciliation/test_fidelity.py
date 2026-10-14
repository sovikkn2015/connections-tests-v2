"""Schema Reconciliation Tests — Fidelity Translator (Rule 9)
CRITICAL: cost_basis_method per asset class validation (Rule 7).
  - Mutual funds → average_cost (Fidelity default)
  - Equities/ETFs/other → specific_lot
"""

import pytest
from uuid import uuid4

from m7_schema_translators.fidelity import FidelityTranslator


@pytest.fixture
def translator():
    return FidelityTranslator(is_sftp=False)


@pytest.fixture
def sftp_translator():
    return FidelityTranslator(is_sftp=True)


@pytest.fixture
def fidelity_client():
    return {
        "customerId": "FID-C-001", "displayName": "Sarah Chen",
        "firstName": "Sarah", "lastName": "Chen", "accountType": "Individual",
        "email": "[email protected]", "phone": "555-0400",
        "dateOfBirth": "1975-03-22", "firmId": str(uuid4()), "jurisdiction": "US",
        "createdDate": "2024-01-01T00:00:00Z", "lastModifiedDate": "2024-06-01T00:00:00Z",
    }


@pytest.fixture
def fidelity_position():
    return {
        "positionId": "FID-P-001", "ticker": "AAPL", "cusip": "037833100",
        "description": "Apple Inc", "assetType": "Common Stock",
        "quantity": 150, "marketValue": 28500.00, "costBasis": 18000.00,
        "unrealizedGainLoss": 10500.00, "accountNumber": "FID-A-001",
        "asOfDate": "2024-06-01",
    }


@pytest.fixture
def fidelity_mutual_fund_position():
    return {
        "positionId": "FID-P-002", "ticker": "FXAIX", "cusip": "315911750",
        "description": "Fidelity 500 Index Fund", "assetType": "Mutual Fund",
        "quantity": 500, "marketValue": 85000.00, "costBasis": 70000.00,
        "accountNumber": "FID-A-001", "asOfDate": "2024-06-01",
    }


@pytest.fixture
def fidelity_equity_tax_lot():
    return {
        "lotId": str(uuid4()), "positionId": "FID-P-001",
        "acquiredDate": "2022-06-15", "acquiredPrice": 120.00,
        "quantity": 150, "costBasis": 18000.00, "assetType": "Common Stock",
        "unrealizedGainLoss": 10500.00,
    }


@pytest.fixture
def fidelity_mutual_fund_tax_lot():
    return {
        "lotId": str(uuid4()), "positionId": "FID-P-002",
        "acquiredDate": "2023-01-10", "acquiredPrice": 140.00,
        "quantity": 500, "costBasis": 70000.00, "assetType": "Mutual Fund",
    }


@pytest.fixture
def fidelity_tax_lot_no_method_no_type():
    return {
        "lotId": str(uuid4()), "positionId": "FID-P-003",
        "acquiredDate": "2024-01-01", "quantity": 10, "costBasis": 1000,
    }


@pytest.fixture
def fidelity_transaction():
    return {
        "transactionId": "FID-T-001", "type": "Buy", "ticker": "AAPL",
        "cusip": "037833100", "description": "Apple Inc",
        "quantity": 50, "price": 190.00, "amount": 9500.00,
        "commission": 0, "tradeDate": "2024-05-20",
        "settlementDate": "2024-05-21", "settlementStatus": "settled",
        "accountNumber": str(uuid4()), "createdDate": "2024-05-20T10:00:00Z",
    }


@pytest.fixture
def fidelity_balance():
    return {
        "accountNumber": str(uuid4()), "totalValue": 180000.00,
        "cashBalance": 12000.00, "unsettledCash": 1500.00,
        "longMarketValue": 168000.00, "buyingPower": 24000.00,
        "accruedInterest": 75.00, "accountType": "Individual",
        "asOfDate": "2024-06-01",
    }


# -----------------------------------------------------------------------
# Client Tests
# -----------------------------------------------------------------------

class TestFidelityClientTranslation:
    def test_required_fields(self, translator, fidelity_client):
        client = translator.client_to_canonical(fidelity_client)
        assert client.display_name == "Sarah Chen"
        assert client.source_system == "fidelity"
        assert client.source_id == "FID-C-001"
        assert client.client_type == "individual"

    def test_vendor_mappings(self, translator, fidelity_client):
        client = translator.client_to_canonical(fidelity_client)
        assert client.vendor_mappings.fidelity is not None
        assert client.vendor_mappings.fidelity.customer_id == "FID-C-001"

    def test_round_trip(self, translator, fidelity_client):
        canonical = translator.client_to_canonical(fidelity_client)
        vendor_back = translator.client_from_canonical(canonical)
        assert vendor_back["displayName"] == "Sarah Chen"
        assert vendor_back["customerId"] == "FID-C-001"
        assert vendor_back["firstName"] == "Sarah"
        assert vendor_back["lastName"] == "Chen"
        assert vendor_back["email"] == "[email protected]"

    def test_missing_customer_id_raises(self, translator):
        with pytest.raises(ValueError, match="customerId"):
            translator.client_to_canonical({"firstName": "Test"})


# -----------------------------------------------------------------------
# Holding Tests
# -----------------------------------------------------------------------

class TestFidelityHoldingTranslation:
    def test_required_fields(self, translator, fidelity_position):
        holding = translator.holding_to_canonical(fidelity_position)
        assert holding.quantity == 150
        assert holding.market_value == 28500.00
        assert holding.source_system == "fidelity"

    def test_excludes_accrued(self, translator, fidelity_position):
        holding = translator.holding_to_canonical(fidelity_position)
        assert holding.market_value_includes_accrued is False

    def test_security_identifier(self, translator, fidelity_position):
        holding = translator.holding_to_canonical(fidelity_position)
        assert holding.security_identifier is not None
        assert holding.security_identifier.ticker == "AAPL"
        assert holding.security_identifier.cusip == "037833100"

    def test_round_trip(self, translator, fidelity_position):
        canonical = translator.holding_to_canonical(fidelity_position)
        vendor_back = translator.holding_from_canonical(canonical)
        assert vendor_back["quantity"] == 150
        assert vendor_back["marketValue"] == 28500.00
        assert vendor_back["ticker"] == "AAPL"
        assert vendor_back["cusip"] == "037833100"
        assert vendor_back["description"] == "Apple Inc"


# -----------------------------------------------------------------------
# TaxLot Tests — CRITICAL: cost_basis_method per asset class (Rule 7)
# -----------------------------------------------------------------------

class TestFidelityTaxLotTranslation:
    """CRITICAL: cost_basis_method must NEVER be null (Rule 7).
    Fidelity defaults: average_cost for mutual funds, specific_lot for equities.
    """

    def test_equity_defaults_to_specific_lot(self, translator, fidelity_equity_tax_lot):
        """Equities without explicit method → specific_lot."""
        lot = translator.tax_lot_to_canonical(fidelity_equity_tax_lot)
        assert lot.cost_basis_method is not None
        assert lot.cost_basis_method.value == "specific_lot"

    def test_mutual_fund_defaults_to_average_cost(self, translator, fidelity_mutual_fund_tax_lot):
        """Mutual funds without explicit method → average_cost."""
        lot = translator.tax_lot_to_canonical(fidelity_mutual_fund_tax_lot)
        assert lot.cost_basis_method is not None
        assert lot.cost_basis_method.value == "average_cost"

    def test_no_method_no_type_defaults_specific_lot(self, translator, fidelity_tax_lot_no_method_no_type):
        """No method AND no asset type → specific_lot (safe default)."""
        lot = translator.tax_lot_to_canonical(fidelity_tax_lot_no_method_no_type)
        assert lot.cost_basis_method is not None
        assert lot.cost_basis_method.value == "specific_lot"

    def test_explicit_fifo_overrides_default(self, translator):
        """Explicit FIFO method overrides asset-class default."""
        data = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                "quantity": 10, "costBasis": 1000, "costBasisMethod": "FIFO",
                "assetType": "Mutual Fund"}
        lot = translator.tax_lot_to_canonical(data)
        assert lot.cost_basis_method.value == "fifo"

    def test_explicit_average_cost_on_equity(self, translator):
        """Explicit Average Cost on equity is respected."""
        data = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                "quantity": 10, "costBasis": 1000, "costBasisMethod": "Average Cost",
                "assetType": "Common Stock"}
        lot = translator.tax_lot_to_canonical(data)
        assert lot.cost_basis_method.value == "average_cost"

    def test_hifo_mapped(self, translator):
        data = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                "quantity": 10, "costBasis": 1000, "costBasisMethod": "HIFO"}
        lot = translator.tax_lot_to_canonical(data)
        assert lot.cost_basis_method.value == "hifo"

    def test_lifo_mapped(self, translator):
        data = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                "quantity": 10, "costBasis": 1000, "costBasisMethod": "LIFO"}
        lot = translator.tax_lot_to_canonical(data)
        assert lot.cost_basis_method.value == "lifo"

    def test_source_custodian_is_fidelity(self, translator, fidelity_equity_tax_lot):
        lot = translator.tax_lot_to_canonical(fidelity_equity_tax_lot)
        assert lot.source_custodian == "fidelity"

    def test_round_trip_equity(self, translator, fidelity_equity_tax_lot):
        canonical = translator.tax_lot_to_canonical(fidelity_equity_tax_lot)
        vendor_back = translator.tax_lot_from_canonical(canonical)
        assert vendor_back["quantity"] == 150
        assert vendor_back["costBasis"] == 18000.00
        assert vendor_back["costBasisMethod"] in {"SpecID", "Specific Identification"}
        assert "acquiredDate" in vendor_back
        assert vendor_back["acquiredPrice"] == 120.00
        assert vendor_back["unrealizedGainLoss"] == 10500.00

    def test_round_trip_mutual_fund(self, translator, fidelity_mutual_fund_tax_lot):
        canonical = translator.tax_lot_to_canonical(fidelity_mutual_fund_tax_lot)
        vendor_back = translator.tax_lot_from_canonical(canonical)
        assert vendor_back["quantity"] == 500
        assert vendor_back["costBasis"] == 70000.00
        assert vendor_back["costBasisMethod"] in {"Average Cost", "AvgCost"}


# -----------------------------------------------------------------------
# Transaction Tests
# -----------------------------------------------------------------------

class TestFidelityTransactionTranslation:
    def test_required_fields(self, translator, fidelity_transaction):
        tx = translator.transaction_to_canonical(fidelity_transaction)
        assert tx.transaction_type.value == "buy"
        assert tx.amount == 9500.00
        assert tx.source_system == "fidelity"

    def test_round_trip(self, translator, fidelity_transaction):
        canonical = translator.transaction_to_canonical(fidelity_transaction)
        vendor_back = translator.transaction_from_canonical(canonical)
        assert vendor_back["type"] == "Buy"
        assert vendor_back["amount"] == 9500.00
        assert vendor_back["tradeDate"] == "2024-05-20"
        assert vendor_back["ticker"] == "AAPL"
        assert vendor_back["quantity"] == 50
        assert vendor_back["price"] == 190.00


# -----------------------------------------------------------------------
# Balance Tests
# -----------------------------------------------------------------------

class TestFidelityBalanceTranslation:
    def test_required_fields(self, translator, fidelity_balance):
        balance = translator.balance_to_canonical(fidelity_balance)
        assert balance.total_value == 180000.00
        assert balance.source_system == "fidelity"

    def test_api_real_time(self, translator, fidelity_balance):
        balance = translator.balance_to_canonical(fidelity_balance)
        assert balance.is_real_time is True

    def test_sftp_not_real_time(self, sftp_translator, fidelity_balance):
        balance = sftp_translator.balance_to_canonical(fidelity_balance)
        assert balance.is_real_time is False
        assert balance.source_system == "fidelity_sftp"

    def test_round_trip(self, translator, fidelity_balance):
        canonical = translator.balance_to_canonical(fidelity_balance)
        vendor_back = translator.balance_from_canonical(canonical)
        assert vendor_back["totalValue"] == 180000.00
        assert vendor_back["cashBalance"] == 12000.00
        assert vendor_back["longMarketValue"] == 168000.00
        assert vendor_back["buyingPower"] == 24000.00
