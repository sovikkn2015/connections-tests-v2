"""Schema Reconciliation Tests — Orion Translator (Rule 9)"""

import pytest
from uuid import uuid4

from m7_schema_translators.orion import OrionTranslator


@pytest.fixture
def translator():
    return OrionTranslator()


@pytest.fixture
def orion_client():
    return {
        "id": "ORN-C-12345", "name": "Sarah Chen", "firstName": "Sarah",
        "lastName": "Chen", "entityType": "Individual", "email": "[email protected]",
        "phone": "555-0200", "dateOfBirth": "1978-07-22", "representativeId": "REP-001",
        "firmId": str(uuid4()), "jurisdiction": "US",
        "riskProfile": {"riskTolerance": "moderate_aggressive"},
        "createdDate": "2024-01-01T00:00:00Z", "lastModifiedDate": "2024-06-01T00:00:00Z",
    }


@pytest.fixture
def orion_position():
    return {
        "id": "ORN-P-67890", "ticker": "AAPL", "cusip": "037833100",
        "securityName": "Apple Inc", "assetClass": "Equity", "units": 250,
        "marketValue": 52500.00, "costBasis": 35000.00, "unrealizedGainLoss": 17500.00,
        "accountId": "ORN-A-001", "asOfDate": "2024-06-01",
    }


@pytest.fixture
def orion_household():
    return {
        "id": "ORN-H-111", "name": "Chen Family",
        "members": [{"clientId": "ORN-C-12345", "role": "Primary"},
                     {"clientId": "ORN-C-12346", "role": "Spouse"}],
        "accounts": [{"accountId": "ORN-A-001"}, {"accountId": "ORN-A-002"}],
    }


@pytest.fixture
def orion_transaction():
    return {
        "id": "ORN-T-99999", "transactionType": "Buy", "ticker": "AAPL",
        "cusip": "037833100", "securityName": "Apple Inc", "units": 50,
        "price": 210.00, "amount": 10500.00, "commission": 0,
        "tradeDate": "2024-05-15", "settlementDate": "2024-05-16",
        "settlementStatus": "settled", "accountId": str(uuid4()),
        "createdDate": "2024-05-15T10:00:00Z",
    }


@pytest.fixture
def orion_performance():
    return {
        "id": "ORN-PERF-001", "accountId": str(uuid4()), "period": "YTD",
        "twrReturn": 0.085, "irrReturn": 0.082, "benchmarkReturn": 0.075,
        "benchmarkName": "S&P 500", "sharpeRatio": 1.2,
        "startDate": "2024-01-01", "endDate": "2024-06-01",
        "startValue": 100000, "endValue": 108500,
        "methodology": "daily_valuation", "isGipsCompliant": True,
        "asOfDate": "2024-06-01",
    }


class TestOrionClientTranslation:
    def test_required_fields(self, translator, orion_client):
        client = translator.client_to_canonical(orion_client)
        assert client.display_name == "Sarah Chen"
        assert client.client_type == "individual"
        assert client.source_system == "orion"
        assert client.source_id == "ORN-C-12345"

    def test_vendor_mappings(self, translator, orion_client):
        client = translator.client_to_canonical(orion_client)
        assert client.vendor_mappings.orion.client_id == "ORN-C-12345"
        assert client.vendor_mappings.orion.representative_id == "REP-001"

    def test_round_trip(self, translator, orion_client):
        canonical = translator.client_to_canonical(orion_client)
        vendor_back = translator.client_from_canonical(canonical)
        assert vendor_back["name"] == "Sarah Chen"
        assert vendor_back["id"] == "ORN-C-12345"


class TestOrionHoldingTranslation:
    def test_required_fields(self, translator, orion_position):
        holding = translator.holding_to_canonical(orion_position)
        assert holding.quantity == 250
        assert holding.market_value == 52500.00
        assert holding.source_system == "orion"

    def test_equity_no_accrued(self, translator, orion_position):
        holding = translator.holding_to_canonical(orion_position)
        assert holding.market_value_includes_accrued is False

    def test_fixed_income_accrued(self, translator):
        fi = {"id": "FI-1", "assetClass": "Fixed Income", "units": 10,
              "marketValue": 10500, "accountId": "A1", "asOfDate": "2024-06-01"}
        holding = translator.holding_to_canonical(fi)
        assert holding.market_value_includes_accrued is True

    def test_round_trip(self, translator, orion_position):
        canonical = translator.holding_to_canonical(orion_position)
        vendor_back = translator.holding_from_canonical(canonical)
        assert vendor_back["units"] == 250
        assert vendor_back["marketValue"] == 52500.00


class TestOrionHouseholdTranslation:
    def test_portfolio_management_grouping(self, translator, orion_household):
        hh = translator.household_to_canonical(orion_household)
        assert hh.vendor_mappings.orion.grouping_type == "portfolio_management"

    def test_members(self, translator, orion_household):
        hh = translator.household_to_canonical(orion_household)
        assert len(hh.members) == 2

    def test_round_trip(self, translator, orion_household):
        canonical = translator.household_to_canonical(orion_household)
        vendor_back = translator.household_from_canonical(canonical)
        assert vendor_back["name"] == "Chen Family"
        assert vendor_back["id"] == "ORN-H-111"


class TestOrionTransactionTranslation:
    def test_required_fields(self, translator, orion_transaction):
        tx = translator.transaction_to_canonical(orion_transaction)
        assert tx.transaction_type.value == "buy"
        assert tx.amount == 10500.00
        assert tx.source_system == "orion"

    def test_round_trip(self, translator, orion_transaction):
        canonical = translator.transaction_to_canonical(orion_transaction)
        vendor_back = translator.transaction_from_canonical(canonical)
        assert vendor_back["transactionType"] == "Buy"
        assert vendor_back["amount"] == 10500.00


class TestOrionPerformanceTranslation:
    def test_required_fields(self, translator, orion_performance):
        perf = translator.performance_to_canonical(orion_performance)
        assert perf.twr_return == 0.085
        assert perf.period.value == "ytd"

    def test_daily_valuation(self, translator, orion_performance):
        perf = translator.performance_to_canonical(orion_performance)
        assert perf.methodology.value == "daily_valuation"
        assert perf.is_gips_compliant is True

    def test_round_trip(self, translator, orion_performance):
        canonical = translator.performance_to_canonical(orion_performance)
        vendor_back = translator.performance_from_canonical(canonical)
        assert vendor_back["twrReturn"] == 0.085
        assert vendor_back["period"] == "YTD"
