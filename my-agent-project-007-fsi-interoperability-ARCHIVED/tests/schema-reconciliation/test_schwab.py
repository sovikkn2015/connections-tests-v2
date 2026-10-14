"""Schema Reconciliation Tests — Schwab Translator (Rule 9)
Includes critical cost_basis_method validation (Rule 7).
"""

import pytest
from uuid import uuid4

from m7_schema_translators.schwab import SchwabTranslator


@pytest.fixture
def translator():
    return SchwabTranslator(is_sftp=False)


@pytest.fixture
def sftp_translator():
    return SchwabTranslator(is_sftp=True)


@pytest.fixture
def schwab_client():
    return {
        "accountHolderId": "SCHW-H-001", "displayName": "Robert Martinez",
        "firstName": "Robert", "lastName": "Martinez", "accountType": "Individual",
        "email": "[email protected]", "phone": "555-0300",
        "dateOfBirth": "1970-11-08", "firmId": str(uuid4()), "jurisdiction": "US",
        "createdDate": "2024-01-01T00:00:00Z", "lastModifiedDate": "2024-06-01T00:00:00Z",
    }


@pytest.fixture
def schwab_position():
    return {
        "positionId": "SCHW-P-001", "ticker": "MSFT", "cusip": "594918104",
        "description": "Microsoft Corp", "assetType": "Common Stock",
        "quantity": 200, "marketValue": 84000.00, "costBasis": 50000.00,
        "unrealizedGainLoss": 34000.00, "accountNumber": "SCHW-A-001",
        "asOfDate": "2024-06-01",
    }


@pytest.fixture
def schwab_tax_lot():
    return {
        "lotId": str(uuid4()), "positionId": "SCHW-P-001",
        "acquiredDate": "2022-03-15", "acquiredPrice": 250.00,
        "quantity": 100, "costBasis": 25000.00, "costBasisMethod": "SpecID",
        "unrealizedGainLoss": 17000.00,
    }


@pytest.fixture
def schwab_tax_lot_no_method():
    return {
        "lotId": str(uuid4()), "positionId": "SCHW-P-001",
        "acquiredDate": "2023-01-10", "quantity": 50, "costBasis": 12500.00,
    }


@pytest.fixture
def schwab_transaction():
    return {
        "transactionId": "SCHW-T-001", "type": "Buy", "ticker": "MSFT",
        "cusip": "594918104", "description": "Microsoft Corp",
        "quantity": 50, "price": 420.00, "amount": 21000.00,
        "commission": 0, "tradeDate": "2024-05-20",
        "settlementDate": "2024-05-21", "settlementStatus": "settled",
        "accountNumber": str(uuid4()), "createdDate": "2024-05-20T10:00:00Z",
    }


@pytest.fixture
def schwab_balance():
    return {
        "accountNumber": str(uuid4()), "totalValue": 250000.00,
        "cashBalance": 15000.00, "unsettledCash": 2000.00,
        "longMarketValue": 235000.00, "buyingPower": 30000.00,
        "accruedInterest": 150.00, "accountType": "Individual",
        "asOfDate": "2024-06-01",
    }


@pytest.fixture
def schwab_household():
    return {
        "masterAccount": "SCHW-MA-001", "displayName": "Martinez Family",
        "members": [{"accountHolderId": "SCHW-H-001", "role": "primary"}],
        "accounts": [{"accountNumber": "SCHW-A-001"}, {"accountNumber": "SCHW-A-002"}],
    }


class TestSchwabClientTranslation:
    def test_required_fields(self, translator, schwab_client):
        client = translator.client_to_canonical(schwab_client)
        assert client.display_name == "Robert Martinez"
        assert client.source_system == "schwab"

    def test_vendor_mappings(self, translator, schwab_client):
        client = translator.client_to_canonical(schwab_client)
        assert client.vendor_mappings.schwab.account_holder_id == "SCHW-H-001"

    def test_round_trip(self, translator, schwab_client):
        canonical = translator.client_to_canonical(schwab_client)
        vendor_back = translator.client_from_canonical(canonical)
        assert vendor_back["displayName"] == "Robert Martinez"
        assert vendor_back["accountHolderId"] == "SCHW-H-001"
        assert vendor_back["firstName"] == "Robert"
        assert vendor_back["lastName"] == "Martinez"
        assert vendor_back["email"] == "[email protected]"
        assert vendor_back["phone"] == "555-0300"
        assert vendor_back["dateOfBirth"] == "1970-11-08"


class TestSchwabHoldingTranslation:
    def test_required_fields(self, translator, schwab_position):
        holding = translator.holding_to_canonical(schwab_position)
        assert holding.quantity == 200
        assert holding.market_value == 84000.00

    def test_excludes_accrued(self, translator, schwab_position):
        holding = translator.holding_to_canonical(schwab_position)
        assert holding.market_value_includes_accrued is False

    def test_round_trip(self, translator, schwab_position):
        canonical = translator.holding_to_canonical(schwab_position)
        vendor_back = translator.holding_from_canonical(canonical)
        assert vendor_back["quantity"] == 200
        assert vendor_back["marketValue"] == 84000.00
        assert vendor_back["ticker"] == "MSFT"
        assert vendor_back["cusip"] == "594918104"
        assert vendor_back["description"] == "Microsoft Corp"
        assert vendor_back["costBasis"] == 50000.00
        assert "asOfDate" in vendor_back


class TestSchwabTaxLotTranslation:
    """CRITICAL: cost_basis_method must NEVER be null (Rule 7)."""

    def test_cost_basis_method_mapped(self, translator, schwab_tax_lot):
        lot = translator.tax_lot_to_canonical(schwab_tax_lot)
        assert lot.cost_basis_method.value == "specific_lot"
        assert lot.cost_basis_method is not None

    def test_cost_basis_default_specific_lot(self, translator, schwab_tax_lot_no_method):
        lot = translator.tax_lot_to_canonical(schwab_tax_lot_no_method)
        assert lot.cost_basis_method.value == "specific_lot"
        assert lot.cost_basis_method is not None

    def test_cost_basis_never_null(self, translator):
        minimal = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                    "quantity": 10, "costBasis": 1000}
        lot = translator.tax_lot_to_canonical(minimal)
        assert lot.cost_basis_method is not None
        assert lot.cost_basis_method.value == "specific_lot"

    def test_source_method_preserved(self, translator, schwab_tax_lot):
        lot = translator.tax_lot_to_canonical(schwab_tax_lot)
        assert lot.source_cost_basis_method == "SpecID"
        assert lot.source_custodian == "schwab"

    def test_round_trip(self, translator, schwab_tax_lot):
        canonical = translator.tax_lot_to_canonical(schwab_tax_lot)
        vendor_back = translator.tax_lot_from_canonical(canonical)
        assert vendor_back["quantity"] == 100
        assert vendor_back["costBasis"] == 25000.00
        assert vendor_back["acquiredPrice"] == 250.00
        assert "acquiredDate" in vendor_back
        assert "lotId" in vendor_back
        assert vendor_back["unrealizedGainLoss"] == 17000.00
        # Reverse map may return either "SpecID" or "Specific Identification"
        # — both are valid Schwab representations of specific_lot
        assert vendor_back["costBasisMethod"] in {"SpecID", "Specific Identification"}

    def test_fifo_mapped(self, translator):
        data = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                "quantity": 10, "costBasis": 1000, "costBasisMethod": "FIFO"}
        lot = translator.tax_lot_to_canonical(data)
        assert lot.cost_basis_method.value == "fifo"

    def test_average_cost_mapped(self, translator):
        data = {"lotId": str(uuid4()), "acquiredDate": "2024-01-01",
                "quantity": 10, "costBasis": 1000, "costBasisMethod": "Average Cost"}
        lot = translator.tax_lot_to_canonical(data)
        assert lot.cost_basis_method.value == "average_cost"


class TestSchwabTransactionTranslation:
    def test_required_fields(self, translator, schwab_transaction):
        tx = translator.transaction_to_canonical(schwab_transaction)
        assert tx.transaction_type.value == "buy"
        assert tx.amount == 21000.00

    def test_round_trip(self, translator, schwab_transaction):
        canonical = translator.transaction_to_canonical(schwab_transaction)
        vendor_back = translator.transaction_from_canonical(canonical)
        assert vendor_back["type"] == "Buy"
        assert vendor_back["amount"] == 21000.00
        assert vendor_back["tradeDate"] == "2024-05-20"
        assert vendor_back["description"] == "Microsoft Corp"
        assert vendor_back["ticker"] == "MSFT"
        assert vendor_back["cusip"] == "594918104"
        assert vendor_back["quantity"] == 50
        assert vendor_back["price"] == 420.00
        assert vendor_back["settlementDate"] == "2024-05-21"


class TestSchwabBalanceTranslation:
    def test_required_fields(self, translator, schwab_balance):
        balance = translator.balance_to_canonical(schwab_balance)
        assert balance.total_value == 250000.00

    def test_api_real_time(self, translator, schwab_balance):
        balance = translator.balance_to_canonical(schwab_balance)
        assert balance.is_real_time is True

    def test_sftp_not_real_time(self, sftp_translator, schwab_balance):
        balance = sftp_translator.balance_to_canonical(schwab_balance)
        assert balance.is_real_time is False
        assert balance.source_system == "schwab_sftp"

    def test_round_trip(self, translator, schwab_balance):
        canonical = translator.balance_to_canonical(schwab_balance)
        vendor_back = translator.balance_from_canonical(canonical)
        assert vendor_back["totalValue"] == 250000.00
        assert vendor_back["cashBalance"] == 15000.00
        assert vendor_back["longMarketValue"] == 235000.00
        assert vendor_back["buyingPower"] == 30000.00
        assert "asOfDate" in vendor_back


class TestSchwabHouseholdTranslation:
    def test_custodial_grouping(self, translator, schwab_household):
        hh = translator.household_to_canonical(schwab_household)
        assert hh.vendor_mappings.schwab.grouping_type == "custodial"
        assert hh.vendor_mappings.schwab.master_account == "SCHW-MA-001"

    def test_round_trip(self, translator, schwab_household):
        canonical = translator.household_to_canonical(schwab_household)
        vendor_back = translator.household_from_canonical(canonical)
        assert vendor_back["masterAccount"] == "SCHW-MA-001"
        assert vendor_back["displayName"] == "Martinez Family"
        assert len(vendor_back["members"]) == 1
        assert vendor_back["members"][0]["accountHolderId"] == "SCHW-H-001"
        assert len(vendor_back["accounts"]) == 2
