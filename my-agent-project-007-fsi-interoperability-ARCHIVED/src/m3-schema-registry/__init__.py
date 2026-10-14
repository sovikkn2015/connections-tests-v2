"""
M3 Canonical Schema Registry — Module Exports

All 18 canonical types + shared enums and sub-models for the 007 FSI Interoperability Platform.
M7 translators and other modules import from here.
"""

from m3_schema_registry.types import (
    # Shared enums
    AccountType,
    SourceSystem,
    # Shared sub-models
    SecurityIdentifier,
    Reconciliation,
    PII,
    HitlApproval,
    # 1. Client
    Client,
    ClientVendorMappings,
    ClientVendorSalesforceFSC,
    ClientVendorOrion,
    ClientVendorSchwab,
    ClientVendorFidelity,
    # 2. Holding
    Holding,
    # 3. TaxLot
    TaxLot,
    CostBasisMethod,
    # 4. Order
    Order,
    OrderStatus,
    TaxImpact,
    # 5. Transaction
    Transaction,
    TransactionType,
    CostBasisImpact,
    # 6. Balance
    Balance,
    # 7. Household
    Household,
    HouseholdMember,
    HouseholdAccount,
    HouseholdVendorMappings,
    HouseholdVendorSFSC,
    HouseholdVendorOrion,
    HouseholdVendorSchwab,
    # 8. ComplianceCheck
    ComplianceCheck,
    ComplianceCheckType,
    ComplianceDecision,
    ComplianceCheckInputContext,
    # 9. ComplianceAlert
    ComplianceAlert,
    AlertType,
    AlertSeverity,
    AlertStatus,
    EscalationEntry,
    AlertResolution,
    AlertEvidence,
    # 10. AuditEntry
    AuditEntry,
    ProvenanceStage,
    # 11. Performance
    Performance,
    PerformanceMethodology,
    PerformancePeriod,
    # 12. SecurityProfile
    SecurityProfile,
    AssetClass,
    # 13. Quote
    Quote,
    # 14. PlanSummary
    PlanSummary,
    PlanRecommendation,
    PlanAssumptions,
    PlanVendorMappings,
    PlanVendorEMoney,
    PlanVendorMoneyGuidePro,
    PlanVendorRightCapital,
    # 15. Goal
    Goal,
    GoalType,
    GoalStatus,
    GoalAssumptions,
    GoalVendorMappings,
    GoalVendorSFSC,
    GoalVendorEMoney,
    GoalVendorMoneyGuidePro,
    # 16. InteractionSummary
    InteractionSummary,
    ActionItem,
    Attendee,
    CrmWriteBack,
    CrmWriteBackEntry,
    ComplianceReview,
    # 17. ResearchBrief
    ResearchBrief,
    ResearchSource,
    Valuation,
    # 18. PaymentInstruction
    PaymentInstruction,
    PaymentType,
    PaymentStatus,
    Beneficiary,
    BsaAml,
    Iso20022Mapping,
)

__all__ = [
    # Shared
    "AccountType", "SourceSystem", "SecurityIdentifier", "Reconciliation",
    "PII", "HitlApproval",
    # 18 canonical types
    "Client", "Holding", "TaxLot", "Order", "Transaction", "Balance",
    "Household", "ComplianceCheck", "ComplianceAlert", "AuditEntry",
    "Performance", "SecurityProfile", "Quote", "PlanSummary", "Goal",
    "InteractionSummary", "ResearchBrief", "PaymentInstruction",
    # Enums
    "CostBasisMethod", "OrderStatus", "TransactionType", "ComplianceCheckType",
    "ComplianceDecision", "AlertType", "AlertSeverity", "AlertStatus",
    "PerformanceMethodology", "PerformancePeriod", "AssetClass", "GoalType",
    "GoalStatus", "PaymentType", "PaymentStatus",
    # Sub-models
    "ClientVendorMappings", "ClientVendorSalesforceFSC", "ClientVendorOrion",
    "ClientVendorSchwab", "ClientVendorFidelity",
    "TaxImpact", "CostBasisImpact",
    "HouseholdMember", "HouseholdAccount", "HouseholdVendorMappings",
    "HouseholdVendorSFSC", "HouseholdVendorOrion", "HouseholdVendorSchwab",
    "ComplianceCheckInputContext", "EscalationEntry", "AlertResolution",
    "AlertEvidence", "ProvenanceStage",
    "PlanRecommendation", "PlanAssumptions", "PlanVendorMappings",
    "PlanVendorEMoney", "PlanVendorMoneyGuidePro", "PlanVendorRightCapital",
    "GoalAssumptions", "GoalVendorMappings", "GoalVendorSFSC",
    "GoalVendorEMoney", "GoalVendorMoneyGuidePro",
    "ActionItem", "Attendee", "CrmWriteBack", "CrmWriteBackEntry",
    "ComplianceReview", "ResearchSource", "Valuation",
    "Beneficiary", "BsaAml", "Iso20022Mapping",
]
