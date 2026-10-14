"""
Schema Reconciliation Tests — Salesforce FSC Translator

Rule 9: Automated reconciliation tests for every translator.
Verifies:
  - to_canonical produces valid canonical types (all required fields populated)
  - from_canonical(to_canonical(vendor_data)) round-trips without data loss
  - vendor_mappings are preserved
  - Enum values are valid after translation
"""

import pytest
from uuid import uuid4
from datetime import date

from m7_schema_translators.salesforce_fsc import SalesforceFSCTranslator


@pytest.fixture
def translator():
    return SalesforceFSCTranslator()


@pytest.fixture
def sf_client_person_account():
    return {
        "Id": "001ABC123DEF456",
        "Name": "John Henderson",
        "IsPersonAccount": True,
        "FirstName": "John",
        "LastName": "Henderson",
        "PersonEmail": "[email protected]",
        "Phone": "555-0100",
        "PersonBirthdate": "1965-03-15",
        "SSN_Last_Four__c": "1234",
        "Risk_Tolerance__c": "Moderate",
        "Investment_Objectives__c": "Growth;Income",
        "Time_Horizon__c": "Long Term",
        "KYC_Status__c": "Verified",
        "Jurisdiction__c": "US",
        "Firm_Id__c": str(uuid4()),
        "CreatedDate": "2024-01-15T10:30:00.000+0000",
        "LastModifiedDate": "2024-06-01T14:00:00.000+0000",
    }


@pytest.fixture
def sf_holding():
    return {
        "Id": "a0BABC123DEF456",
        "Name": "NVIDIA Corp",
        "Ticker__c": "NVDA",
        "CUSIP__c": "67066G104",
        "FinServ__Shares__c": 100,
        "FinServ__MarketValue__c": 125000.00,
        "FinServ__CostBasis__c": 45000.00,
        "FinServ__GainLoss__c": 80000.00,
        "Security_Type__c": "Stock",
        "FinServ__FinancialAccount__c": "acct-001",
        "As_Of_Date__c": "2024-06-01",
    }


@pytest.fixture
def sf_household():
    return {
        "Id": "001HH123DEF456",
        "Name": "Henderson Household",
        "Members": [
            {"ContactId": "003C001", "Role": "Primary"},
            {"ContactId": "003C002", "Role": "Spouse"},
        ],
        "Accounts": [{"Id": "acct-001"}, {"Id": "acct-002"}],
    }


@pytest.fixture
def sf_goal():
    return {
        "Id": "a0GGOAL123",
        "Name": "Retire at 65",
        "Type__c": "Retirement",
        "Status__c": "On Track",
        "Priority__c": "Critical",
        "FinServ__TargetValue__c": 2000000,
        "FinServ__ActualValue__c": 850000,
        "FinServ__TargetDate__c": "2030-03-15",
        "FinServ__PrimaryOwner__c": str(uuid4()),
        "CreatedDate": "2024-01-01T00:00:00Z",
        "LastModifiedDate": "2024-06-01T00:00:00Z",
    }


class TestSFClientTranslation:
    def test_to_canonical_required_fields(self, translator, sf_client_person_account):
        client = translator.client_to_canonical(sf_client_person_account)
        assert client.canonical_id is not None
        assert client.display_name == "John Henderson"
        assert client.client_type == "individual"
        assert client.source_system == "salesforce_fsc"
        assert client.source_id == "001ABC123DEF456"

    def test_pii_preserved(self, translator, sf_client_person_account):
        client = translator.client_to_canonical(sf_client_person_account)
        assert client.email == "[email protected]"
        assert client.ssn_last_four == "1234"
        assert client.date_of_birth == date(1965, 3, 15)

    def test_risk_tolerance_mapped(self, translator, sf_client_person_account):
        client = translator.client_to_canonical(sf_client_person_account)
        assert client.risk_tolerance == "moderate"

    def test_investment_objectives_parsed(self, translator, sf_client_person_account):
        client = translator.client_to_canonical(sf_client_person_account)
        assert "growth" in client.investment_objectives
        assert "income" in client.investment_objectives

    def test_vendor_mappings_preserved(self, translator, sf_client_person_account):
        client = translator.client_to_canonical(sf_client_person_account)
        assert client.vendor_mappings.salesforce_fsc is not None
        assert client.vendor_mappings.salesforce_fsc.account_id == "001ABC123DEF456"
        assert client.vendor_mappings.salesforce_fsc.person_account is True

    def test_round_trip(self, translator, sf_client_person_account):
        canonical = translator.client_to_canonical(sf_client_person_account)
        vendor_back = translator.client_from_canonical(canonical)
        assert vendor_back["Name"] == "John Henderson"
        assert vendor_back["Id"] == "001ABC123DEF456"
        assert vendor_back["IsPersonAccount"] is True

    def test_missing_id_raises(self, translator):
        with pytest.raises(ValueError, match="Id"):
            translator.client_to_canonical({"Name": "No ID"})


class TestSFHoldingTranslation:
    def test_to_canonical_required_fields(self, translator, sf_holding):
        holding = translator.holding_to_canonical(sf_holding)
        assert holding.quantity == 100
        assert holding.market_value == 125000.00
        assert holding.source_system == "salesforce_fsc"

    def test_market_value_excludes_accrued(self, translator, sf_holding):
        holding = translator.holding_to_canonical(sf_holding)
        assert holding.market_value_includes_accrued is False

    def test_security_identifier(self, translator, sf_holding):
        holding = translator.holding_to_canonical(sf_holding)
        assert holding.security_identifier.ticker == "NVDA"
        assert holding.security_identifier.cusip == "67066G104"

    def test_round_trip(self, translator, sf_holding):
        canonical = translator.holding_to_canonical(sf_holding)
        vendor_back = translator.holding_from_canonical(canonical)
        assert vendor_back["FinServ__Shares__c"] == 100
        assert vendor_back["FinServ__MarketValue__c"] == 125000.00

    def test_tax_lots_empty(self, translator, sf_holding):
        holding = translator.holding_to_canonical(sf_holding)
        assert holding.tax_lots == []


class TestSFHouseholdTranslation:
    def test_container_model(self, translator, sf_household):
        hh = translator.household_to_canonical(sf_household)
        assert hh.primary_source == "salesforce_fsc"

    def test_relationship_grouping(self, translator, sf_household):
        hh = translator.household_to_canonical(sf_household)
        assert hh.vendor_mappings.salesforce_fsc.grouping_type == "relationship"

    def test_members_mapped(self, translator, sf_household):
        hh = translator.household_to_canonical(sf_household)
        assert len(hh.members) == 2
        assert {m.role for m in hh.members} == {"primary", "spouse"}

    def test_round_trip(self, translator, sf_household):
        canonical = translator.household_to_canonical(sf_household)
        vendor_back = translator.household_from_canonical(canonical)
        assert vendor_back["Name"] == "Henderson Household"
        assert vendor_back["Id"] == "001HH123DEF456"


class TestSFGoalTranslation:
    def test_to_canonical_required_fields(self, translator, sf_goal):
        goal = translator.goal_to_canonical(sf_goal)
        assert goal.goal_name == "Retire at 65"
        assert goal.target_amount == 2000000

    def test_goal_type_mapped(self, translator, sf_goal):
        goal = translator.goal_to_canonical(sf_goal)
        assert goal.goal_type.value == "retirement"

    def test_goal_status_mapped(self, translator, sf_goal):
        goal = translator.goal_to_canonical(sf_goal)
        assert goal.status.value == "on_track"

    def test_funding_pct(self, translator, sf_goal):
        goal = translator.goal_to_canonical(sf_goal)
        assert goal.funding_pct == 42.5

    def test_vendor_mappings(self, translator, sf_goal):
        goal = translator.goal_to_canonical(sf_goal)
        assert goal.vendor_mappings.salesforce_fsc.financial_goal_id == "a0GGOAL123"

    def test_round_trip(self, translator, sf_goal):
        canonical = translator.goal_to_canonical(sf_goal)
        vendor_back = translator.goal_from_canonical(canonical)
        assert vendor_back["Name"] == "Retire at 65"
        assert vendor_back["Type__c"] == "Retirement"
        assert vendor_back["Status__c"] == "On Track"
        assert vendor_back["Id"] == "a0GGOAL123"
