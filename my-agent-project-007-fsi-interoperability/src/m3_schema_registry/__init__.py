"""
M3 Canonical Schema Registry — Public API

18 canonical FSI data types for Project 007 FSI Interoperability Platform.
Version 0.1.0 (pre-SME review).

Usage:
    from m3_schema_registry import Client, Household, TaxLot, CANONICAL_TYPES
    from m3_schema_registry import export_all_schemas, SCHEMA_VERSION
"""

from __future__ import annotations

from m3_schema_registry.types import (
    # Version
    SCHEMA_VERSION,
    # PII
    PII,
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
    # Shared sub-models
    HitlApproval,
    Reconciliation,
    SecurityIdentifier,
    # Vendor mapping sub-models
    ClientVendorFidelity,
    ClientVendorMappings,
    ClientVendorOrion,
    ClientVendorSalesforceFSC,
    ClientVendorSchwab,
    CrmWriteBack,
    CrmWriteBackEntry,
    GoalVendorEMoney,
    GoalVendorMappings,
    GoalVendorMoneyGuidePro,
    GoalVendorSFSC,
    HouseholdAccount,
    HouseholdMember,
    HouseholdVendorMappings,
    HouseholdVendorOrion,
    HouseholdVendorSchwab,
    HouseholdVendorSFSC,
    PlanVendorEMoney,
    PlanVendorMappings,
    PlanVendorMoneyGuidePro,
    PlanVendorRightCapital,
)
from m3_schema_registry.types import (
    # Type-specific sub-models
    ActionItem,
    AlertEvidence,
    AlertResolution,
    Attendee,
    Beneficiary,
    BsaAml,
    ComplianceCheckInputContext,
    ComplianceReview,
    CostBasisImpact,
    EscalationEntry,
    GoalAssumptions,
    Iso20022Mapping,
    PlanAssumptions,
    PlanRecommendation,
    ProvenanceStage,
    ResearchSource,
    TaxImpact,
    Valuation,
    # 18 Canonical Types
    AuditEntry,
    Balance,
    Client,
    ComplianceAlert,
    ComplianceCheck,
    Goal,
    Holding,
    Household,
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
)

from pydantic import BaseModel

# =============================================================================
# CANONICAL_TYPES registry — 18 entries
# =============================================================================

CANONICAL_TYPES: dict[str, type[BaseModel]] = {
    "Client": Client,
    "Household": Household,
    "TaxLot": TaxLot,
    "Holding": Holding,
    "Order": Order,
    "Transaction": Transaction,
    "Balance": Balance,
    "Performance": Performance,
    "SecurityProfile": SecurityProfile,
    "Quote": Quote,
    "PlanSummary": PlanSummary,
    "Goal": Goal,
    "InteractionSummary": InteractionSummary,
    "ComplianceCheck": ComplianceCheck,
    "ComplianceAlert": ComplianceAlert,
    "AuditEntry": AuditEntry,
    "ResearchBrief": ResearchBrief,
    "PaymentInstruction": PaymentInstruction,
}


# =============================================================================
# PII_FIELDS — (type_name, field_name) -> description
# =============================================================================

def _build_pii_fields() -> dict[tuple[str, str], str]:
    """Scan all canonical types for fields with x-pii annotation."""
    pii: dict[tuple[str, str], str] = {}
    for type_name, model_cls in CANONICAL_TYPES.items():
        schema = model_cls.model_json_schema()
        props = schema.get("properties", {})
        for field_name, field_schema in props.items():
            if field_schema.get("x-pii") is True:
                pii[(type_name, field_name)] = field_schema.get("description", "")
    # Also scan nested sub-models that have PII (Beneficiary in PaymentInstruction)
    ben_schema = Beneficiary.model_json_schema()
    for field_name, field_schema in ben_schema.get("properties", {}).items():
        if field_schema.get("x-pii") is True:
            pii[("Beneficiary", field_name)] = field_schema.get("description", "")
    return pii


PII_FIELDS: dict[tuple[str, str], str] = _build_pii_fields()


# =============================================================================
# Schema export functions
# =============================================================================

def export_all_schemas() -> dict[str, dict]:
    """Export JSON Schema for all 18 canonical types."""
    return {name: cls.model_json_schema() for name, cls in CANONICAL_TYPES.items()}


def get_schema(type_name: str) -> dict:
    """Get JSON Schema for a single canonical type."""
    if type_name not in CANONICAL_TYPES:
        raise KeyError(f"Unknown canonical type: {type_name}. Valid types: {list(CANONICAL_TYPES.keys())}")
    return CANONICAL_TYPES[type_name].model_json_schema()


__all__ = [
    # Constants
    "SCHEMA_VERSION",
    "CANONICAL_TYPES",
    "PII_FIELDS",
    # Functions
    "export_all_schemas",
    "get_schema",
    # PII
    "PII",
    # Enums
    "AccountType", "AlertSeverity", "AlertStatus", "AlertType", "AssetClass",
    "ComplianceCheckType", "ComplianceDecision", "CostBasisMethod", "GoalStatus",
    "GoalType", "OrderStatus", "PaymentStatus", "PaymentType",
    "PerformanceMethodology", "PerformancePeriod", "SourceSystem", "TransactionType",
    # Shared sub-models
    "HitlApproval", "Reconciliation", "SecurityIdentifier",
    # 18 Canonical Types
    "AuditEntry", "Balance", "Client", "ComplianceAlert", "ComplianceCheck",
    "Goal", "Holding", "Household", "InteractionSummary", "Order",
    "PaymentInstruction", "Performance", "PlanSummary", "Quote",
    "ResearchBrief", "SecurityProfile", "TaxLot", "Transaction",
]
