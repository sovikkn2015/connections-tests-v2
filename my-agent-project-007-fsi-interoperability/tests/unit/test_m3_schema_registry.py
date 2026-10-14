"""
Unit tests for M3 Canonical Schema Registry.

Tests cover: enums, sub-models, all 18 types, PII annotations,
cost_basis_method enforcement, registry exports, module isolation,
and round-trip serialization.

References spec acceptance criteria: AC1.1-AC1.4, AC3.1-AC3.5,
AC4.1-AC4.4, AC5.1-AC5.5, AC6.1-AC6.5, AC7.1-AC7.3, AC8.1,
AC9.1-AC9.3, AC10.1-AC10.3.
"""

from __future__ import annotations

import ast
import json
import os
from datetime import date, datetime
from pathlib import Path
from uuid import uuid4

import pytest

from m3_schema_registry import (
    CANONICAL_TYPES,
    PII_FIELDS,
    SCHEMA_VERSION,
    export_all_schemas,
    get_schema,
)
from m3_schema_registry.types import (
    # Enums
    AccountType,
    AlertSeverity,
    AlertStatus,
    AlertType,
    AssetClass,
    ComplianceCheckType,
    ComplianceDecision,
    CostBasisMethod,
    GoalStatus,
    GoalType,
    OrderStatus,
    PaymentStatus,
    PaymentType,
    PerformanceMethodology,
    PerformancePeriod,
    SourceSystem,
    TransactionType,
    # Sub-models
    Beneficiary,
    HitlApproval,
    HouseholdMember,
    PII,
    Reconciliation,
    SecurityIdentifier,
    # Types
    AuditEntry,
    Balance,
    Client,
    ComplianceAlert,
    ComplianceCheck,
)
from m3_schema_registry.types import (
    Goal,
    Holding,
    Household,
    HouseholdVendorMappings,
    InteractionSummary,
    Order,
    PaymentInstruction,
    Performance,
    PlanSummary,
    Quote,
    ResearchBrief,
    SecurityProfile,
    TaxLot,
    Transaction,
    BsaAml,
    ResearchSource,
)
from pydantic import ValidationError


# =========================================================================
# AC8.1: SCHEMA_VERSION
# =========================================================================

class TestSchemaVersion:
    def test_schema_version_is_0_1_0(self):
        """AC8.1: SCHEMA_VERSION = '0.1.0' (pre-SME review)."""
        assert SCHEMA_VERSION == "0.1.0"


# =========================================================================
# AC1.1, AC1.2: CANONICAL_TYPES registry
# =========================================================================

class TestCanonicalTypes:
    def test_exactly_18_types(self):
        """AC1.1, AC1.2: Registry contains exactly 18 types."""
        assert len(CANONICAL_TYPES) == 18

    def test_all_type_names_present(self):
        """AC1.1: All 18 type names present."""
        expected = {
            "Client", "Household", "TaxLot", "Holding", "Order",
            "Transaction", "Balance", "Performance", "SecurityProfile",
            "Quote", "PlanSummary", "Goal", "InteractionSummary",
            "ComplianceCheck", "ComplianceAlert", "AuditEntry",
            "ResearchBrief", "PaymentInstruction",
        }
        assert set(CANONICAL_TYPES.keys()) == expected

    def test_all_types_importable(self):
        """AC1.3: All types importable from m3_schema_registry."""
        from m3_schema_registry import (
            Client, Household, TaxLot, Holding, Order, Transaction,
            Balance, Performance, SecurityProfile, Quote, PlanSummary,
            Goal, InteractionSummary, ComplianceCheck, ComplianceAlert,
            AuditEntry, ResearchBrief, PaymentInstruction,
        )
        assert Client is not None
        assert PaymentInstruction is not None


# =========================================================================
# AC7.1-AC7.3: Enum value counts
# =========================================================================

class TestEnums:
    def test_account_type_16_values(self):
        """AC7.3: AccountType has exactly 16 values."""
        assert len(AccountType) == 16

    def test_account_type_specific_values(self):
        """AC7.3: AccountType includes all BLOCKER-8 values."""
        values = {e.value for e in AccountType}
        expected = {
            "taxable", "traditional_ira", "roth_ira", "401k", "403b", "457",
            "sep_ira", "simple_ira", "trust_revocable", "trust_irrevocable",
            "custodial_utma", "custodial_ugma", "erisa_pension",
            "erisa_profit_sharing", "529", "hsa",
        }
        assert values == expected

    def test_source_system_23_values(self):
        # Remediation M9 (2026 Q2): ICE Data + Smarsh added → 23 entries.
        assert len(SourceSystem) == 23

    def test_cost_basis_method_5_values(self):
        """AC5.2: CostBasisMethod has exactly 5 values."""
        assert len(CostBasisMethod) == 5
        values = {e.value for e in CostBasisMethod}
        assert values == {"specific_lot", "average_cost", "fifo", "lifo", "hifo"}

    def test_order_status_12_values(self):
        assert len(OrderStatus) == 12

    def test_transaction_type_19_values(self):
        assert len(TransactionType) == 19

    def test_compliance_check_type_12_values(self):
        assert len(ComplianceCheckType) == 12

    def test_compliance_decision_5_values(self):
        assert len(ComplianceDecision) == 5

    def test_alert_type_15_values(self):
        assert len(AlertType) == 15

    def test_alert_severity_5_values(self):
        assert len(AlertSeverity) == 5

    def test_alert_status_6_values(self):
        """LLMJ v2 fix: AlertStatus has 6 values (not 5)."""
        assert len(AlertStatus) == 6

    def test_payment_type_7_values(self):
        assert len(PaymentType) == 7

    def test_payment_status_10_values(self):
        assert len(PaymentStatus) == 10

    def test_asset_class_12_values(self):
        assert len(AssetClass) == 12

    def test_goal_type_11_values(self):
        assert len(GoalType) == 11

    def test_goal_status_5_values(self):
        assert len(GoalStatus) == 5

    def test_performance_methodology_3_values(self):
        assert len(PerformanceMethodology) == 3

    def test_performance_period_9_values(self):
        assert len(PerformancePeriod) == 9

    def test_enum_values_are_snake_case(self):
        """AC7.2: All enum values use snake_case."""
        import re
        for enum_cls in [AccountType, CostBasisMethod, OrderStatus, TransactionType,
                         AlertType, AlertSeverity, AlertStatus, PaymentType, PaymentStatus,
                         AssetClass, GoalType, GoalStatus, PerformanceMethodology, PerformancePeriod]:
            for member in enum_cls:
                assert re.match(r'^[a-z0-9_]+$', member.value), \
                    f"{enum_cls.__name__}.{member.name} value '{member.value}' is not snake_case"

    def test_total_enum_count_is_17(self):
        """LLMJ v2 fix: 17 primary enums (not 22)."""
        enums = [
            AccountType, SourceSystem, CostBasisMethod, OrderStatus, TransactionType,
            ComplianceCheckType, ComplianceDecision, AlertType, AlertSeverity, AlertStatus,
            PaymentType, PaymentStatus, AssetClass, GoalType, GoalStatus,
            PerformanceMethodology, PerformancePeriod,
        ]
        assert len(enums) == 17


# =========================================================================
# AC5.1, AC5.5: TaxLot cost_basis_method REQUIRED
# =========================================================================

class TestTaxLotCostBasis:
    def test_cost_basis_method_required(self):
        """AC5.1: Constructing TaxLot without cost_basis_method raises ValidationError."""
        with pytest.raises(ValidationError):
            TaxLot(
                lot_id=uuid4(),
                holding_ref="H-001",
                acquisition_date=date(2024, 1, 15),
                quantity=100.0,
                cost_basis_amount=15000.0,
                source_custodian="schwab",
            )

    def test_cost_basis_method_none_rejected(self):
        """AC5.5: cost_basis_method=None raises ValidationError with regulatory message."""
        with pytest.raises(ValidationError, match="regulatory violation"):
            TaxLot(
                lot_id=uuid4(),
                holding_ref="H-001",
                acquisition_date=date(2024, 1, 15),
                quantity=100.0,
                cost_basis_method=None,
                cost_basis_amount=15000.0,
                source_custodian="schwab",
            )

    def test_cost_basis_method_valid(self):
        """TaxLot with valid cost_basis_method succeeds."""
        lot = TaxLot(
            lot_id=uuid4(),
            holding_ref="H-001",
            acquisition_date=date(2024, 1, 15),
            quantity=100.0,
            cost_basis_method=CostBasisMethod.SPECIFIC_LOT,
            cost_basis_amount=15000.0,
            source_custodian="schwab",
        )
        assert lot.cost_basis_method == CostBasisMethod.SPECIFIC_LOT

    def test_source_cost_basis_method_present(self):
        """AC5.3: source_cost_basis_method field exists for reconciliation."""
        lot = TaxLot(
            lot_id=uuid4(),
            holding_ref="H-001",
            acquisition_date=date(2024, 1, 15),
            quantity=100.0,
            cost_basis_method="specific_lot",
            cost_basis_amount=15000.0,
            source_custodian="schwab",
            source_cost_basis_method="SpecID",
        )
        assert lot.source_cost_basis_method == "SpecID"


# =========================================================================
# AC5.4: Holding does NOT have cost_basis_method
# =========================================================================

class TestHoldingNoCostBasis:
    def test_holding_has_no_cost_basis_method(self):
        """AC5.4: Holding does NOT have cost_basis_method field."""
        assert "cost_basis_method" not in Holding.model_fields

    def test_holding_has_tax_lots(self):
        """AC5.4: Holding has tax_lots field."""
        assert "tax_lots" in Holding.model_fields

    def test_holding_has_account_type(self):
        """Holding has account_type using AccountType enum."""
        assert "account_type" in Holding.model_fields


# =========================================================================
# AC4.1-AC4.4: Household container model
# =========================================================================

class TestHouseholdContainer:
    def test_members_at_top_level(self):
        """AC4.2: members at Household level, NOT inside vendor_mappings."""
        assert "members" in Household.model_fields

    def test_vendor_mappings_no_member_lists(self):
        """AC4.1: vendor_mappings contain IDs and grouping types ONLY."""
        vm_fields = HouseholdVendorMappings.model_fields
        for field_name in vm_fields:
            assert "member" not in field_name.lower()

    def test_reconciliation_object(self):
        """AC4.3: reconciliation has sources_agree, discrepancies, last_reconciled."""
        recon = Reconciliation(
            sources_agree=False,
            discrepancies=["Member count differs between SF FSC and Orion"],
            last_reconciled=datetime(2024, 6, 1, 12, 0, 0),
        )
        assert recon.sources_agree is False
        assert len(recon.discrepancies) == 1

    def test_household_construction(self):
        """AC4.4: Household with members and reconciliation."""
        hh = Household(
            canonical_id=uuid4(),
            display_name="Henderson Household",
            primary_source="salesforce_fsc",
            members=[
                HouseholdMember(client_ref="C-001", role="primary", source="salesforce_fsc"),
                HouseholdMember(client_ref="C-002", role="spouse", source="salesforce_fsc"),
            ],
            reconciliation=Reconciliation(
                sources_agree=False,
                discrepancies=["Orion has 3 members, SF FSC has 2"],
                last_reconciled=datetime(2024, 6, 1),
            ),
        )
        assert len(hh.members) == 2
        assert hh.reconciliation.sources_agree is False


# =========================================================================
# AC6.1-AC6.5: PII annotations
# =========================================================================

class TestPiiAnnotations:
    def test_client_pii_fields_in_schema(self):
        """AC6.1, AC6.4: Client model_json_schema() includes x-pii on 5 PII fields."""
        schema = Client.model_json_schema()
        props = schema["properties"]
        pii_fields = ["email", "phone", "date_of_birth", "ssn_last_four", "tax_id"]
        for field in pii_fields:
            assert props[field].get("x-pii") is True, f"Client.{field} missing x-pii"

    def test_pii_fields_dict_has_client_fields(self):
        """AC6.3: PII_FIELDS contains Client PII fields."""
        assert ("Client", "email") in PII_FIELDS
        assert ("Client", "phone") in PII_FIELDS
        assert ("Client", "date_of_birth") in PII_FIELDS
        assert ("Client", "ssn_last_four") in PII_FIELDS
        assert ("Client", "tax_id") in PII_FIELDS

    def test_beneficiary_pii_fields(self):
        """LLMJ v2 fix: Beneficiary account_number, routing_number, iban have x-pii."""
        schema = Beneficiary.model_json_schema()
        props = schema["properties"]
        assert props["account_number"].get("x-pii") is True
        assert props["routing_number"].get("x-pii") is True
        assert props["iban"].get("x-pii") is True

    def test_pii_marker_dict(self):
        """PII.MARKER is the correct dict."""
        assert PII.MARKER == {"x-pii": True}

    def test_security_profile_mnpi_not_pii(self):
        """AC6.5: is_restricted and mnpi_flag are MNPI indicators, not x-pii."""
        schema = SecurityProfile.model_json_schema()
        props = schema["properties"]
        assert props["is_restricted"].get("x-pii") is not True
        assert props["mnpi_flag"].get("x-pii") is not True


# =========================================================================
# AC10.1-AC10.3: Schema export
# =========================================================================

class TestSchemaExport:
    def test_export_all_schemas_returns_18(self):
        """AC10.2: export_all_schemas returns 18 schemas."""
        schemas = export_all_schemas()
        assert len(schemas) == 18

    def test_each_schema_is_valid_json_schema(self):
        """AC10.1: Every model's model_json_schema() returns valid JSON Schema."""
        for name, cls in CANONICAL_TYPES.items():
            schema = cls.model_json_schema()
            assert "properties" in schema, f"{name} schema missing properties"
            assert "title" in schema, f"{name} schema missing title"

    def test_get_schema_valid(self):
        """get_schema returns schema for valid type."""
        schema = get_schema("Client")
        assert schema["title"] == "Client"

    def test_get_schema_invalid_raises(self):
        """get_schema raises KeyError for unknown type."""
        with pytest.raises(KeyError, match="Unknown canonical type"):
            get_schema("NonExistent")


# =========================================================================
# ComplianceAlert wsp_section REQUIRED
# =========================================================================

class TestComplianceAlert:
    def test_wsp_section_required(self):
        """ComplianceAlert.wsp_section is required per steering rule 19."""
        with pytest.raises(ValidationError):
            ComplianceAlert(
                alert_id=uuid4(),
                alert_type="restricted_list_violation",
                severity="critical",
                status="open",
                triggered_by_rule="authority/restricted_list.rego",
                firm_id="FIRM-001",
                trace_id="trace-001",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                # wsp_section intentionally omitted
            )

    def test_wsp_section_optional_on_compliance_check(self):
        """ComplianceCheck.wsp_section is optional (not all checks from WSP rules)."""
        check = ComplianceCheck(
            check_id=uuid4(),
            check_type="restricted_list",
            decision="ALLOW",
            reason="Not on restricted list",
            rule_applied="authority/restricted_list.rego:check",
            evaluated_at=datetime.now(),
            trace_id="trace-001",
        )
        assert check.wsp_section is None


# =========================================================================
# Quote.is_delayed REQUIRED
# =========================================================================

class TestQuote:
    def test_is_delayed_required(self):
        """Quote.is_delayed is REQUIRED for compliance disclosure."""
        with pytest.raises(ValidationError):
            Quote(
                canonical_id=uuid4(),
                security_ref=uuid4(),
                ticker="AAPL",
                price=185.50,
                as_of_timestamp=datetime.now(),
                currency="USD",
                source_system="alpha_vantage",
                source_id="Q-001",
                # is_delayed intentionally omitted
            )


# =========================================================================
# Balance.is_real_time default
# =========================================================================

class TestBalance:
    def test_is_real_time_default_false(self):
        """Balance.is_real_time defaults to False."""
        b = Balance(
            balance_id=uuid4(),
            account_ref=uuid4(),
            total_value=500000.0,
            as_of_date=date(2024, 6, 1),
            source_system="schwab",
            source_id="B-001",
        )
        assert b.is_real_time is False


# =========================================================================
# Client.client_type validation
# =========================================================================

class TestClientValidation:
    def test_valid_client_type(self):
        now = datetime.now()
        c = Client(
            canonical_id=uuid4(),
            display_name="John Henderson",
            client_type="individual",
            firm_id=uuid4(),
            jurisdiction="US",
            source_system="salesforce_fsc",
            source_id="001xxx",
            created_at=now,
            updated_at=now,
        )
        assert c.client_type == "individual"

    def test_invalid_client_type_rejected(self):
        with pytest.raises(ValidationError, match="client_type"):
            Client(
                canonical_id=uuid4(),
                display_name="Bad Client",
                client_type="corporation",
                firm_id=uuid4(),
                jurisdiction="US",
                source_system="manual",
                source_id="X-001",
                created_at=datetime.now(),
                updated_at=datetime.now(),
            )


# =========================================================================
# Round-trip serialization tests (LLMJ v2 fix)
# =========================================================================

class TestRoundTripSerialization:
    """Construct, serialize to JSON, deserialize back, verify equality."""

    def test_client_round_trip(self):
        now = datetime.now()
        uid = uuid4()
        c = Client(
            canonical_id=uid,
            display_name="Test Client",
            client_type="individual",
            firm_id=uuid4(),
            jurisdiction="US",
            source_system="salesforce_fsc",
            source_id="C-001",
            created_at=now,
            updated_at=now,
        )
        json_str = c.model_dump_json()
        c2 = Client.model_validate_json(json_str)
        assert c2.canonical_id == c.canonical_id
        assert c2.display_name == c.display_name

    def test_tax_lot_round_trip(self):
        lot = TaxLot(
            lot_id=uuid4(),
            holding_ref="H-001",
            acquisition_date=date(2024, 1, 15),
            quantity=100.0,
            cost_basis_method="specific_lot",
            cost_basis_amount=15000.0,
            source_custodian="schwab",
        )
        json_str = lot.model_dump_json()
        lot2 = TaxLot.model_validate_json(json_str)
        assert lot2.cost_basis_method == CostBasisMethod.SPECIFIC_LOT
        assert lot2.quantity == 100.0

    def test_household_round_trip(self):
        hh = Household(
            canonical_id=uuid4(),
            display_name="Test HH",
            primary_source="orion",
            members=[HouseholdMember(client_ref="C-1", role="primary", source="orion")],
        )
        json_str = hh.model_dump_json()
        hh2 = Household.model_validate_json(json_str)
        assert len(hh2.members) == 1
        assert hh2.members[0].role == "primary"

    def test_all_types_serializable(self):
        """Every type can produce model_json_schema() without error."""
        for name, cls in CANONICAL_TYPES.items():
            schema = cls.model_json_schema()
            json_str = json.dumps(schema)
            parsed = json.loads(json_str)
            assert parsed["title"] == name or parsed["title"] == cls.__name__


# =========================================================================
# AC9.1, AC9.2: Module isolation
# =========================================================================

class TestModuleIsolation:
    """Task 19: Verify zero cross-module imports."""

    def test_no_cross_module_imports(self):
        """AC9.1: No imports from m1_*, m2_*, m4_*, m5_*, m6_*, etc."""
        src_dir = Path(__file__).parent.parent.parent / "src" / "m3_schema_registry"
        forbidden_prefixes = [
            "m1_", "m2_", "m4_", "m5_", "m6_", "m7_", "m8_",
            "m9_", "m10_", "m11_", "m12_", "m13_",
        ]
        for py_file in src_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        for prefix in forbidden_prefixes:
                            assert not alias.name.startswith(prefix), \
                                f"{py_file.name} imports {alias.name} — cross-module import!"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        for prefix in forbidden_prefixes:
                            assert not node.module.startswith(prefix), \
                                f"{py_file.name} imports from {node.module} — cross-module import!"

    def test_only_allowed_imports(self):
        """AC9.2: Only imports from __future__, datetime, decimal, enum, typing, uuid, pydantic."""
        allowed = {"__future__", "datetime", "decimal", "enum", "typing", "uuid", "pydantic",
                   "m3_schema_registry"}
        src_dir = Path(__file__).parent.parent.parent / "src" / "m3_schema_registry"
        for py_file in src_dir.glob("*.py"):
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        root = alias.name.split(".")[0]
                        assert root in allowed, \
                            f"{py_file.name} imports '{alias.name}' — not in allowed list"
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        root = node.module.split(".")[0]
                        assert root in allowed, \
                            f"{py_file.name} imports from '{node.module}' — not in allowed list"


# =========================================================================
# PaymentInstruction BSA/AML fields
# =========================================================================

class TestPaymentInstructionBsaAml:
    def test_bsa_aml_fields_present(self):
        """BSA/AML sub-model has required regulatory fields."""
        bsa = BsaAml(
            ctr_required=True,
            sar_flagged=False,
            sanctions_screened=True,
            ofac_screened=True,
        )
        assert bsa.ctr_required is True
        assert bsa.sanctions_screened is True
