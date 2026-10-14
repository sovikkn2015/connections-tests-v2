"""
eMoney → canonical PlanSummary translator (T7).

Raw plan body REJECTED at vendor-model boundary (extra="forbid"). M4 owns
MNPI filtering AFTER translation. `net_worth` is DERIVED from assets/liabilities
— REVERSE-lossy.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import UUID, uuid5

from m3_schema_registry import (
    PlanAssumptions,
    PlanRecommendation,
    PlanSummary,
    PlanVendorEMoney,
    PlanVendorMappings,
)

from m7_schema_translators.emoney.models import (
    EMoneyAssumptions,
    EMoneyMonteCarlo,
    EMoneyPlanSummary,
    EMoneyRecommendation,
    EMoneyRetirementGoal,
)
from m7_schema_translators.errors import (
    MissingRequiredField,
    UnknownEnumValue,
)
from m7_schema_translators.shared.namespaces import (
    CLIENT_NS,
    GOAL_NS,
    HOUSEHOLD_NS,
    PLAN_NS,
)
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "v2"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "emoney_full_plan_body",
        "emoney_scenarios_detail",
        "emoney_cashflow_projection_yearly",
        "emoney_asset_allocation_history",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "net_worth",
        "EMoney.scenariosDetail",
        "EMoney.cashflowProjection",
    }
)


_PLAN_TYPE_FWD: dict[str, str] = {
    "Comprehensive": "comprehensive",
    "Retirement": "retirement_only",
    "Education": "education_only",
    "Estate": "estate",
    "Tax": "tax",
    "Insurance": "insurance",
}
_PLAN_TYPE_REV: dict[str, str] = {v: k for k, v in _PLAN_TYPE_FWD.items()}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"plan_type": MappingProxyType(_PLAN_TYPE_FWD)}
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"plan_type": MappingProxyType(_PLAN_TYPE_REV)}
)


def _map_plan_type(v: str) -> str:
    mapping = ENUM_MAPPINGS["plan_type"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="emoney",
            canonical_type="PlanSummary",
            field_path="planType",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_plan_summary(
    vendor_payload: dict,
) -> tuple[PlanSummary, ReconciliationNote]:
    """Translate eMoney plan SUMMARY → canonical PlanSummary."""
    vendor = EMoneyPlanSummary(**vendor_payload)
    validate_vendor_id_chars(
        vendor.planId,
        vendor="emoney",
        canonical_type="PlanSummary",
        field_path="Plan.planId",
    )
    if not vendor.clientId:
        raise MissingRequiredField(
            reason_code="missing_required_field",
            vendor="emoney",
            canonical_type="PlanSummary",
            field_path="Plan.clientId",
            details={"field_name": "clientId"},
        )
    validate_vendor_id_chars(
        vendor.clientId,
        vendor="emoney",
        canonical_type="PlanSummary",
        field_path="Plan.clientId",
    )

    canonical_id = uuid5(PLAN_NS, f"emoney:{vendor.planId}")
    client_ref = uuid5(CLIENT_NS, f"emoney:{vendor.clientId}")
    household_ref: Optional[UUID] = None
    if vendor.householdId:
        household_ref = uuid5(
            HOUSEHOLD_NS, f"emoney:{vendor.householdId}"
        )

    goals: list[UUID] = []
    for gid in vendor.goalIds:
        validate_vendor_id_chars(
            gid,
            vendor="emoney",
            canonical_type="PlanSummary",
            field_path="Plan.goalIds[]",
        )
        goals.append(uuid5(GOAL_NS, f"emoney:{gid}"))

    plan_type: Optional[str] = None
    if vendor.planType is not None:
        plan_type = _map_plan_type(vendor.planType)

    net_worth: Optional[float] = None
    derived: list[str] = []
    notes: list[str] = []
    if (
        vendor.totalAssets is not None
        and vendor.totalLiabilities is not None
    ):
        net_worth = vendor.totalAssets - vendor.totalLiabilities
        derived.append("net_worth")
        notes.append("emoney_net_worth_derived")

    assumptions: Optional[PlanAssumptions] = None
    if vendor.assumptions is not None:
        a = vendor.assumptions
        assumptions = PlanAssumptions(
            inflation_rate=a.inflation,
            return_assumption=a.returnAssumption,
            life_expectancy=a.lifeExpectancy,
            retirement_age=a.retirementAge,
            tax_rate_assumption=a.taxRate,
        )

    recommendations = [
        PlanRecommendation(
            category=r.category,
            description=r.description,
            priority=r.priority,
        )
        for r in vendor.recommendations
    ]

    rg = vendor.retirementGoal
    mc = vendor.monteCarlo

    vendor_mappings = PlanVendorMappings(
        emoney=PlanVendorEMoney(
            plan_id=vendor.planId, scenario_id=vendor.scenarioId
        )
    )

    canonical = PlanSummary(
        canonical_id=canonical_id,
        client_ref=client_ref,
        household_ref=household_ref,
        plan_name=vendor.planName,
        plan_type=plan_type,
        probability_of_success=vendor.probabilityOfSuccess,
        as_of_date=vendor.asOfDate,
        total_assets=vendor.totalAssets,
        total_liabilities=vendor.totalLiabilities,
        net_worth=net_worth,
        retirement_goal_amount=rg.amount if rg else None,
        retirement_target_date=rg.targetDate if rg else None,
        retirement_income_gap=rg.incomeGap if rg else None,
        monte_carlo_success_pct=mc.successPct if mc else None,
        monte_carlo_iterations=mc.iterations if mc else None,
        annual_savings_rate=vendor.annualSavingsRate,
        annual_spending=vendor.annualSpending,
        social_security_estimate=vendor.socialSecurityEstimate,
        pension_income=vendor.pensionIncome,
        goals=goals,
        assumptions=assumptions,
        recommendations=recommendations,
        vendor_mappings=vendor_mappings,
        source_system="emoney",
        source_id=vendor.planId,
        created_at=vendor.createdAt,
        updated_at=vendor.updatedAt,
    )

    note = ReconciliationNote(
        vendor="emoney",
        canonical_type="PlanSummary",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=sorted(derived),
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return canonical, note


def from_canonical_plan_summary(
    canonical: PlanSummary,
) -> tuple[EMoneyPlanSummary, ReconciliationNote]:
    """Reverse canonical PlanSummary → eMoney SUMMARY. `net_worth` is REVERSE-lossy."""
    em = (
        canonical.vendor_mappings.emoney if canonical.vendor_mappings else None
    )
    plan_id = (em.plan_id if em else None) or canonical.source_id
    scenario_id = em.scenario_id if em else None

    plan_type_rev: Optional[str] = None
    if canonical.plan_type is not None:
        plan_type_rev = REVERSE_ENUM_MAPPINGS["plan_type"].get(canonical.plan_type)

    retirement_goal = None
    if (
        canonical.retirement_goal_amount is not None
        or canonical.retirement_target_date is not None
        or canonical.retirement_income_gap is not None
    ):
        retirement_goal = EMoneyRetirementGoal(
            amount=canonical.retirement_goal_amount,
            targetDate=canonical.retirement_target_date,
            incomeGap=canonical.retirement_income_gap,
        )

    monte_carlo = None
    if (
        canonical.monte_carlo_success_pct is not None
        or canonical.monte_carlo_iterations is not None
    ):
        monte_carlo = EMoneyMonteCarlo(
            successPct=canonical.monte_carlo_success_pct,
            iterations=canonical.monte_carlo_iterations,
        )

    assumptions = None
    if canonical.assumptions is not None:
        a = canonical.assumptions
        assumptions = EMoneyAssumptions(
            inflation=a.inflation_rate,
            returnAssumption=a.return_assumption,
            lifeExpectancy=a.life_expectancy,
            retirementAge=a.retirement_age,
            taxRate=a.tax_rate_assumption,
        )

    recommendations = [
        EMoneyRecommendation(
            category=r.category,
            description=r.description,
            priority=r.priority,
        )
        for r in canonical.recommendations
    ]

    vendor_model = EMoneyPlanSummary(
        planId=plan_id,
        scenarioId=scenario_id,
        clientId=str(canonical.client_ref),
        householdId=str(canonical.household_ref)
        if canonical.household_ref
        else None,
        planName=canonical.plan_name,
        planType=plan_type_rev,
        probabilityOfSuccess=canonical.probability_of_success,
        asOfDate=canonical.as_of_date,
        totalAssets=canonical.total_assets,
        totalLiabilities=canonical.total_liabilities,
        retirementGoal=retirement_goal,
        monteCarlo=monte_carlo,
        annualSavingsRate=canonical.annual_savings_rate,
        annualSpending=canonical.annual_spending,
        socialSecurityEstimate=canonical.social_security_estimate,
        pensionIncome=canonical.pension_income,
        goalIds=[str(g) for g in canonical.goals],
        assumptions=assumptions,
        recommendations=recommendations,
        createdAt=canonical.created_at,
        updatedAt=canonical.updated_at,
    )
    note = ReconciliationNote(
        vendor="emoney",
        canonical_type="PlanSummary",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note
