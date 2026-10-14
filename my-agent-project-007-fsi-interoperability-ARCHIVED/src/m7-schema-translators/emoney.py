"""
M7 Schema Translator — eMoney Advisor (Fidelity-owned)

Maps eMoney objects to canonical types:
  - eMoney Plan → PlanSummary
  - eMoney Goal → Goal

Key issues handled:
  - Fidelity-owned, poorly documented API
  - probability_of_success mapping (0-100 scale)
  - Monte Carlo iterations tracking
  - Raw plan data NEVER sent to LLM — M4 filters to summary-level only
  - vendor_mappings preserved (Rule 12)

Source system: "emoney"
Python 3.12+ / Pydantic v2.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from m7_schema_translators._m3_imports import (
    Goal,
    GoalAssumptions,
    GoalStatus,
    GoalType,
    GoalVendorEMoney,
    GoalVendorMappings,
    PlanAssumptions,
    PlanSummary,
    PlanVendorEMoney,
    PlanVendorMappings,
)
from m7_schema_translators.base import (
    MultiTypeTranslator,
    parse_uuid,
    parse_date,
    parse_datetime,
    safe_float,
    utcnow,
)


# ---------------------------------------------------------------------------
# Mapping tables — eMoney values → canonical enums
# ---------------------------------------------------------------------------

_EMONEY_GOAL_TYPE_MAP: dict[str, GoalType] = {
    "Retirement": GoalType.RETIREMENT, "retirement": GoalType.RETIREMENT,
    "Education": GoalType.EDUCATION, "education": GoalType.EDUCATION,
    "Home Purchase": GoalType.HOME_PURCHASE, "home_purchase": GoalType.HOME_PURCHASE,
    "Emergency Fund": GoalType.EMERGENCY_FUND, "emergency": GoalType.EMERGENCY_FUND,
    "Wealth Transfer": GoalType.WEALTH_TRANSFER, "estate": GoalType.WEALTH_TRANSFER,
    "Charitable": GoalType.CHARITABLE_GIVING, "charitable_giving": GoalType.CHARITABLE_GIVING,
    "Debt Payoff": GoalType.DEBT_PAYOFF, "debt": GoalType.DEBT_PAYOFF,
    "Major Purchase": GoalType.MAJOR_PURCHASE, "major_purchase": GoalType.MAJOR_PURCHASE,
    "Income Replacement": GoalType.INCOME_REPLACEMENT,
    "Legacy": GoalType.LEGACY, "legacy": GoalType.LEGACY,
}

_EMONEY_GOAL_STATUS_MAP: dict[str, GoalStatus] = {
    "On Track": GoalStatus.ON_TRACK, "on_track": GoalStatus.ON_TRACK, "green": GoalStatus.ON_TRACK,
    "At Risk": GoalStatus.AT_RISK, "at_risk": GoalStatus.AT_RISK, "yellow": GoalStatus.AT_RISK,
    "Behind": GoalStatus.BEHIND, "behind": GoalStatus.BEHIND, "red": GoalStatus.BEHIND,
    "Achieved": GoalStatus.ACHIEVED, "achieved": GoalStatus.ACHIEVED,
    "Abandoned": GoalStatus.ABANDONED, "abandoned": GoalStatus.ABANDONED, "inactive": GoalStatus.ABANDONED,
}

_EMONEY_PLAN_TYPE_MAP: dict[str, str] = {
    "Comprehensive": "comprehensive", "comprehensive": "comprehensive",
    "Retirement": "retirement_only", "retirement": "retirement_only",
    "Education": "education_only", "education": "education_only",
    "Estate": "estate", "estate": "estate",
    "Tax": "tax", "tax": "tax",
    "Insurance": "insurance", "insurance": "insurance",
}

_CANONICAL_GOAL_TYPE_TO_EMONEY = {v.value: k for k, v in _EMONEY_GOAL_TYPE_MAP.items() if k[0].isupper()}
_CANONICAL_GOAL_STATUS_TO_EMONEY = {
    "on_track": "On Track", "at_risk": "At Risk", "behind": "Behind",
    "achieved": "Achieved", "abandoned": "Abandoned",
}


class EMoneyTranslator(MultiTypeTranslator):
    """Translates eMoney Advisor data to/from canonical types.

    eMoney is Fidelity-owned. This translator handles:
      - Plan → PlanSummary (summary-level only — raw data NEVER to LLM)
      - Goal → Goal (linked to PlanSummary)
    """

    @property
    def source_system(self) -> str:
        return "emoney"

    # -----------------------------------------------------------------------
    # PlanSummary
    # -----------------------------------------------------------------------

    def plan_summary_to_canonical(self, emoney_data: dict[str, Any]) -> PlanSummary:
        """Convert eMoney Plan to canonical PlanSummary.
        Raw plan data NEVER sent to LLM — M4 filters enforce this.
        """
        plan_id = str(self._require_field(emoney_data, "planId", "eMoney planId"))
        canonical_id = parse_uuid(emoney_data.get("canonical_id")) or uuid4()

        prob_raw = float(emoney_data.get("probabilityOfSuccess", 0))
        probability_of_success = prob_raw * 100 if prob_raw <= 1.0 else prob_raw

        mc_pct_raw = emoney_data.get("monteCarloSuccessPct")
        mc_pct = None
        if mc_pct_raw is not None:
            mc_pct = float(mc_pct_raw) * 100 if float(mc_pct_raw) <= 1.0 else float(mc_pct_raw)

        plan_type_raw = emoney_data.get("planType", "")
        plan_type = _EMONEY_PLAN_TYPE_MAP.get(plan_type_raw, plan_type_raw.lower() if plan_type_raw else None)

        assumptions = None
        assumptions_raw = emoney_data.get("assumptions", {})
        if isinstance(assumptions_raw, dict) and assumptions_raw:
            assumptions = PlanAssumptions(
                inflation_rate=float(assumptions_raw.get("inflationRate", 0.03)),
                return_assumption=float(assumptions_raw.get("returnAssumption", 0.07)),
                life_expectancy=int(assumptions_raw.get("lifeExpectancy", 90)),
                retirement_age=assumptions_raw.get("retirementAge"),
                tax_rate_assumption=safe_float(assumptions_raw.get("taxRateAssumption")),
            )

        goal_ids = [UUID(g) for g in emoney_data.get("goalIds", []) if parse_uuid(g)]

        return PlanSummary(
            canonical_id=canonical_id,
            client_ref=parse_uuid(emoney_data.get("clientRef")) or uuid4(),
            household_ref=parse_uuid(emoney_data.get("householdRef")),
            plan_name=emoney_data.get("planName", "eMoney Plan"),
            plan_type=plan_type,
            probability_of_success=probability_of_success,
            as_of_date=parse_date(emoney_data.get("asOfDate")) or date.today(),
            total_assets=safe_float(emoney_data.get("totalAssets")),
            total_liabilities=safe_float(emoney_data.get("totalLiabilities")),
            net_worth=safe_float(emoney_data.get("netWorth")),
            retirement_goal_amount=safe_float(emoney_data.get("retirementGoalAmount")),
            retirement_target_date=parse_date(emoney_data.get("retirementTargetDate")),
            retirement_income_gap=safe_float(emoney_data.get("retirementIncomeGap")),
            monte_carlo_success_pct=mc_pct,
            monte_carlo_iterations=emoney_data.get("monteCarloIterations"),
            annual_savings_rate=safe_float(emoney_data.get("annualSavingsRate")),
            annual_spending=safe_float(emoney_data.get("annualSpending")),
            social_security_estimate=safe_float(emoney_data.get("socialSecurityEstimate")),
            pension_income=safe_float(emoney_data.get("pensionIncome")),
            goals=goal_ids,
            assumptions=assumptions,
            recommendations=None,
            vendor_mappings=PlanVendorMappings(
                emoney=PlanVendorEMoney(plan_id=plan_id, scenario_id=emoney_data.get("scenarioId")),
            ),
            source_system=self.source_system,
            source_id=plan_id,
            created_at=parse_datetime(emoney_data.get("createdDate")) or utcnow(),
            updated_at=parse_datetime(emoney_data.get("lastModifiedDate")) or utcnow(),
        )

    def plan_summary_from_canonical(self, plan: PlanSummary) -> dict[str, Any]:
        emoney_mapping = plan.vendor_mappings.emoney if plan.vendor_mappings else None
        result: dict[str, Any] = {
            "planName": plan.plan_name,
            "probabilityOfSuccess": plan.probability_of_success,
            "asOfDate": plan.as_of_date.isoformat(),
        }
        if emoney_mapping:
            result["planId"] = emoney_mapping.plan_id
            if emoney_mapping.scenario_id:
                result["scenarioId"] = emoney_mapping.scenario_id
        if plan.total_assets is not None:
            result["totalAssets"] = plan.total_assets
        if plan.net_worth is not None:
            result["netWorth"] = plan.net_worth
        if plan.monte_carlo_success_pct is not None:
            result["monteCarloSuccessPct"] = plan.monte_carlo_success_pct
        if plan.monte_carlo_iterations is not None:
            result["monteCarloIterations"] = plan.monte_carlo_iterations
        if plan.assumptions:
            result["assumptions"] = {
                "inflationRate": plan.assumptions.inflation_rate,
                "returnAssumption": plan.assumptions.return_assumption,
                "lifeExpectancy": plan.assumptions.life_expectancy,
            }
        return result

    # -----------------------------------------------------------------------
    # Goal
    # -----------------------------------------------------------------------

    def goal_to_canonical(self, emoney_data: dict[str, Any]) -> Goal:
        goal_id = str(self._require_field(emoney_data, "goalId", "eMoney goalId"))
        canonical_id = parse_uuid(emoney_data.get("canonical_id")) or uuid4()

        emoney_type = emoney_data.get("goalCategory", "") or emoney_data.get("goalType", "")
        goal_type = _EMONEY_GOAL_TYPE_MAP.get(emoney_type, GoalType.CUSTOM)

        emoney_status = emoney_data.get("status", "On Track")
        status = _EMONEY_GOAL_STATUS_MAP.get(emoney_status, GoalStatus.ON_TRACK)

        target_amount = float(emoney_data.get("targetAmount", 0))
        current_amount = safe_float(emoney_data.get("currentAmount"))
        funding_pct = None
        if current_amount is not None and target_amount > 0:
            funding_pct = round((current_amount / target_amount) * 100, 2)

        assumptions = None
        assumptions_raw = emoney_data.get("assumptions", {})
        if isinstance(assumptions_raw, dict) and assumptions_raw:
            assumptions = GoalAssumptions(
                inflation_rate=float(assumptions_raw.get("inflationRate", 0.03)),
                return_rate=float(assumptions_raw.get("returnRate", 0.07)),
                tax_rate=safe_float(assumptions_raw.get("taxRate")),
            )

        linked_accounts = [UUID(a) for a in emoney_data.get("linkedAccountIds", []) if parse_uuid(a)]

        return Goal(
            canonical_id=canonical_id,
            client_ref=parse_uuid(emoney_data.get("clientRef")) or uuid4(),
            household_ref=parse_uuid(emoney_data.get("householdRef")),
            plan_ref=parse_uuid(emoney_data.get("planRef")),
            goal_type=goal_type,
            goal_name=emoney_data.get("goalName", emoney_type or "eMoney Goal"),
            target_amount=target_amount,
            current_amount=current_amount,
            funding_pct=funding_pct,
            target_date=parse_date(emoney_data.get("targetDate")) or date.today(),
            priority=emoney_data.get("priority", "medium").lower(),
            status=status,
            monthly_contribution=safe_float(emoney_data.get("monthlyContribution")),
            linked_accounts=linked_accounts,
            assumptions=assumptions,
            vendor_mappings=GoalVendorMappings(
                emoney=GoalVendorEMoney(goal_id=goal_id, goal_category=emoney_type or None),
            ),
            as_of_date=parse_date(emoney_data.get("asOfDate")) or date.today(),
            source_system=self.source_system,
            source_id=goal_id,
            created_at=parse_datetime(emoney_data.get("createdDate")) or utcnow(),
            updated_at=parse_datetime(emoney_data.get("lastModifiedDate")) or utcnow(),
        )

    def goal_from_canonical(self, goal: Goal) -> dict[str, Any]:
        emoney_mapping = goal.vendor_mappings.emoney if goal.vendor_mappings else None
        result: dict[str, Any] = {
            "goalName": goal.goal_name,
            "targetAmount": goal.target_amount,
            "targetDate": goal.target_date.isoformat(),
            "goalCategory": _CANONICAL_GOAL_TYPE_TO_EMONEY.get(
                goal.goal_type.value if isinstance(goal.goal_type, GoalType) else goal.goal_type, "Custom"),
            "status": _CANONICAL_GOAL_STATUS_TO_EMONEY.get(
                goal.status.value if isinstance(goal.status, GoalStatus) else goal.status, "On Track"),
        }
        if emoney_mapping:
            result["goalId"] = emoney_mapping.goal_id
        if goal.current_amount is not None:
            result["currentAmount"] = goal.current_amount
        if goal.monthly_contribution is not None:
            result["monthlyContribution"] = goal.monthly_contribution
        return result
