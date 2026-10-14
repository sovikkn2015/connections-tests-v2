"""
Salesforce FSC → canonical Goal translator (T3).

Goal picklist → canonical enum. funding_pct is REVERSE-lossy (derived).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import UUID, uuid5

from m3_schema_registry import (
    Goal,
    GoalAssumptions,
    GoalStatus,
    GoalType,
    GoalVendorMappings,
    GoalVendorSFSC,
)

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.salesforce_fsc.models import (
    SalesforceFSCFinancialGoal,
)
from m7_schema_translators.shared.namespaces import (
    ACCOUNT_NS,
    CLIENT_NS,
    GOAL_NS,
    HOUSEHOLD_NS,
)
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "v59.0"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "sf_goal_created_by",
        "sf_goal_last_modified_by",
        "sf_custom_picklist_raw",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset({"funding_pct"})


_GOAL_TYPE_FWD: dict[str, GoalType] = {
    "Retirement": GoalType.RETIREMENT,
    "Education": GoalType.EDUCATION,
    "Home Purchase": GoalType.HOME_PURCHASE,
    "Emergency Fund": GoalType.EMERGENCY_FUND,
    "Wealth Transfer": GoalType.WEALTH_TRANSFER,
    "Charitable Giving": GoalType.CHARITABLE_GIVING,
    "Debt Payoff": GoalType.DEBT_PAYOFF,
    "Major Purchase": GoalType.MAJOR_PURCHASE,
    "Income Replacement": GoalType.INCOME_REPLACEMENT,
    "Legacy": GoalType.LEGACY,
    "Custom": GoalType.CUSTOM,
}
_GOAL_TYPE_REV: dict[GoalType, str] = {v: k for k, v in _GOAL_TYPE_FWD.items()}

_GOAL_STATUS_FWD: dict[str, GoalStatus] = {
    "On Track": GoalStatus.ON_TRACK,
    "At Risk": GoalStatus.AT_RISK,
    "Behind": GoalStatus.BEHIND,
    "Achieved": GoalStatus.ACHIEVED,
    "Abandoned": GoalStatus.ABANDONED,
}
_GOAL_STATUS_REV: dict[GoalStatus, str] = {
    v: k for k, v in _GOAL_STATUS_FWD.items()
}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {
        "goal_type": MappingProxyType(_GOAL_TYPE_FWD),
        "status": MappingProxyType(_GOAL_STATUS_FWD),
    }
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {
        "goal_type": MappingProxyType(_GOAL_TYPE_REV),
        "status": MappingProxyType(_GOAL_STATUS_REV),
    }
)


def _map_goal_type(vendor_value: str) -> GoalType:
    mapping = ENUM_MAPPINGS["goal_type"]
    if vendor_value not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="salesforce_fsc",
            canonical_type="Goal",
            field_path="FinServ__GoalType__c",
            details={
                "vendor_value": vendor_value,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[vendor_value]


def _map_goal_status(vendor_value: str) -> GoalStatus:
    mapping = ENUM_MAPPINGS["status"]
    if vendor_value not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="salesforce_fsc",
            canonical_type="Goal",
            field_path="FinServ__Status__c",
            details={
                "vendor_value": vendor_value,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[vendor_value]


def _split_picklist(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [s.strip() for s in value.split(";") if s.strip()]


def to_canonical_goal(
    vendor_payload: dict,
) -> tuple[Goal, ReconciliationNote]:
    """Translate SF FSC FinancialGoal → canonical Goal."""
    vendor = SalesforceFSCFinancialGoal(**vendor_payload)
    validate_vendor_id_chars(
        vendor.goal_id,
        vendor="salesforce_fsc",
        canonical_type="Goal",
        field_path="FinServ__FinancialGoal__c.Id",
    )

    canonical_id = uuid5(GOAL_NS, f"salesforce_fsc:{vendor.goal_id}")
    client_ref = uuid5(
        CLIENT_NS, f"salesforce_fsc:{vendor.client_account_id}"
    )
    household_ref: Optional[UUID] = None
    if vendor.household_id:
        household_ref = uuid5(
            HOUSEHOLD_NS, f"salesforce_fsc:{vendor.household_id}"
        )

    linked_accounts: list[UUID] = []
    for aid in _split_picklist(vendor.linked_account_ids):
        linked_accounts.append(uuid5(ACCOUNT_NS, f"salesforce_fsc:{aid}"))

    goal_type = _map_goal_type(vendor.goal_type)
    status = _map_goal_status(vendor.status)

    funding_pct: Optional[float] = None
    derived: list[str] = []
    if vendor.target_amount > 0 and vendor.current_amount is not None:
        funding_pct = min(
            100.0, (vendor.current_amount / vendor.target_amount) * 100.0
        )
        derived.append("funding_pct")

    assumptions: Optional[GoalAssumptions] = None
    if any(
        v is not None
        for v in (
            vendor.inflation_rate,
            vendor.return_rate,
            vendor.tax_rate,
        )
    ):
        assumptions = GoalAssumptions(
            inflation_rate=vendor.inflation_rate,
            return_rate=vendor.return_rate,
            tax_rate=vendor.tax_rate,
        )

    vendor_mappings = GoalVendorMappings(
        salesforce_fsc=GoalVendorSFSC(
            financial_goal_id=vendor.goal_id,
            goal_type_picklist=vendor.goal_type,
        )
    )

    canonical = Goal(
        canonical_id=canonical_id,
        client_ref=client_ref,
        household_ref=household_ref,
        plan_ref=None,
        goal_type=goal_type,
        goal_name=vendor.name,
        target_amount=vendor.target_amount,
        current_amount=vendor.current_amount,
        funding_pct=funding_pct,
        target_date=vendor.target_date,
        priority=vendor.priority,
        status=status,
        monthly_contribution=vendor.monthly_contribution,
        linked_accounts=linked_accounts,
        assumptions=assumptions,
        vendor_mappings=vendor_mappings,
        as_of_date=vendor.as_of_date,
        source_system="salesforce_fsc",
        source_id=vendor.goal_id,
        created_at=vendor.created_date,
        updated_at=vendor.last_modified_date,
    )
    note = ReconciliationNote(
        vendor="salesforce_fsc",
        canonical_type="Goal",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=sorted(derived),
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return canonical, note


def from_canonical_goal(
    canonical: Goal,
) -> tuple[SalesforceFSCFinancialGoal, ReconciliationNote]:
    """Reverse — funding_pct is REVERSE-lossy (derived from target/current)."""
    sf = (
        canonical.vendor_mappings.salesforce_fsc
        if canonical.vendor_mappings
        else None
    )
    goal_id = (sf.financial_goal_id if sf else None) or canonical.source_id

    linked_str: Optional[str] = None
    if canonical.linked_accounts:
        linked_str = ";".join(str(a) for a in canonical.linked_accounts)

    vendor_goal_type_picklist = (
        sf.goal_type_picklist
        if sf and sf.goal_type_picklist
        else REVERSE_ENUM_MAPPINGS["goal_type"][canonical.goal_type]
    )
    assumptions = canonical.assumptions

    vendor_model = SalesforceFSCFinancialGoal(
        goal_id=goal_id,
        name=canonical.goal_name,
        goal_type=vendor_goal_type_picklist,
        status=REVERSE_ENUM_MAPPINGS["status"][canonical.status],
        target_amount=canonical.target_amount,
        current_amount=canonical.current_amount,
        target_date=canonical.target_date,
        priority=canonical.priority,
        client_account_id=str(canonical.client_ref),
        household_id=str(canonical.household_ref)
        if canonical.household_ref
        else None,
        monthly_contribution=canonical.monthly_contribution,
        linked_account_ids=linked_str,
        inflation_rate=assumptions.inflation_rate if assumptions else None,
        return_rate=assumptions.return_rate if assumptions else None,
        tax_rate=assumptions.tax_rate if assumptions else None,
        as_of_date=canonical.as_of_date,
        created_date=canonical.created_at,
        last_modified_date=canonical.updated_at,
    )
    note = ReconciliationNote(
        vendor="salesforce_fsc",
        canonical_type="Goal",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note
