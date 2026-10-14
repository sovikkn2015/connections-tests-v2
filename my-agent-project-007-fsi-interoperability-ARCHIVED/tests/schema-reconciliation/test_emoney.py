"""Schema Reconciliation Tests — eMoney Translator (Rule 9)"""

import pytest
from uuid import uuid4

from m7_schema_translators.emoney import EMoneyTranslator


@pytest.fixture
def translator():
    return EMoneyTranslator()


@pytest.fixture
def emoney_plan():
    return {
        "planId": "EM-PLAN-001", "planName": "Henderson Comprehensive Plan",
        "planType": "Comprehensive", "probabilityOfSuccess": 0.82,
        "clientRef": str(uuid4()), "asOfDate": "2024-06-01",
        "totalAssets": 2500000, "totalLiabilities": 350000, "netWorth": 2150000,
        "retirementGoalAmount": 3000000, "retirementTargetDate": "2030-03-15",
        "retirementIncomeGap": -15000,
        "monteCarloSuccessPct": 0.78, "monteCarloIterations": 5000,
        "annualSavingsRate": 0.15, "annualSpending": 120000,
        "socialSecurityEstimate": 36000, "pensionIncome": 0,
        "assumptions": {"inflationRate": 0.03, "returnAssumption": 0.07,
                        "lifeExpectancy": 92, "retirementAge": 65},
        "scenarioId": "SCENARIO-BASE",
        "createdDate": "2024-01-01T00:00:00Z",
        "lastModifiedDate": "2024-06-01T00:00:00Z",
    }


@pytest.fixture
def emoney_goal():
    return {
        "goalId": "EM-GOAL-001", "goalName": "Retire at 65",
        "goalCategory": "Retirement", "status": "On Track",
        "targetAmount": 3000000, "currentAmount": 1200000,
        "targetDate": "2030-03-15", "priority": "Critical",
        "monthlyContribution": 5000,
        "clientRef": str(uuid4()),
        "assumptions": {"inflationRate": 0.03, "returnRate": 0.07},
        "createdDate": "2024-01-01T00:00:00Z",
        "lastModifiedDate": "2024-06-01T00:00:00Z",
    }


class TestEMoneyPlanSummaryTranslation:
    def test_required_fields(self, translator, emoney_plan):
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.plan_name == "Henderson Comprehensive Plan"
        assert plan.source_system == "emoney"
        assert plan.source_id == "EM-PLAN-001"

    def test_probability_normalized(self, translator, emoney_plan):
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.probability_of_success == 82.0

    def test_probability_already_pct(self, translator, emoney_plan):
        emoney_plan["probabilityOfSuccess"] = 82.0
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.probability_of_success == 82.0

    def test_monte_carlo(self, translator, emoney_plan):
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.monte_carlo_success_pct == 78.0
        assert plan.monte_carlo_iterations == 5000

    def test_assumptions(self, translator, emoney_plan):
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.assumptions.inflation_rate == 0.03
        assert plan.assumptions.return_assumption == 0.07
        assert plan.assumptions.life_expectancy == 92

    def test_vendor_mappings(self, translator, emoney_plan):
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.vendor_mappings.emoney.plan_id == "EM-PLAN-001"
        assert plan.vendor_mappings.emoney.scenario_id == "SCENARIO-BASE"

    def test_plan_type(self, translator, emoney_plan):
        plan = translator.plan_summary_to_canonical(emoney_plan)
        assert plan.plan_type == "comprehensive"

    def test_round_trip(self, translator, emoney_plan):
        canonical = translator.plan_summary_to_canonical(emoney_plan)
        vendor_back = translator.plan_summary_from_canonical(canonical)
        assert vendor_back["planName"] == "Henderson Comprehensive Plan"
        assert vendor_back["planId"] == "EM-PLAN-001"
        assert vendor_back["probabilityOfSuccess"] == 82.0

    def test_missing_plan_id_raises(self, translator):
        with pytest.raises(ValueError, match="planId"):
            translator.plan_summary_to_canonical({"planName": "No ID"})


class TestEMoneyGoalTranslation:
    def test_required_fields(self, translator, emoney_goal):
        goal = translator.goal_to_canonical(emoney_goal)
        assert goal.goal_name == "Retire at 65"
        assert goal.target_amount == 3000000
        assert goal.source_system == "emoney"

    def test_goal_type(self, translator, emoney_goal):
        goal = translator.goal_to_canonical(emoney_goal)
        assert goal.goal_type.value == "retirement"

    def test_goal_status(self, translator, emoney_goal):
        goal = translator.goal_to_canonical(emoney_goal)
        assert goal.status.value == "on_track"

    def test_funding_pct(self, translator, emoney_goal):
        goal = translator.goal_to_canonical(emoney_goal)
        assert goal.funding_pct == 40.0

    def test_assumptions(self, translator, emoney_goal):
        goal = translator.goal_to_canonical(emoney_goal)
        assert goal.assumptions.inflation_rate == 0.03
        assert goal.assumptions.return_rate == 0.07

    def test_vendor_mappings(self, translator, emoney_goal):
        goal = translator.goal_to_canonical(emoney_goal)
        assert goal.vendor_mappings.emoney.goal_id == "EM-GOAL-001"
        assert goal.vendor_mappings.emoney.goal_category == "Retirement"

    def test_round_trip(self, translator, emoney_goal):
        canonical = translator.goal_to_canonical(emoney_goal)
        vendor_back = translator.goal_from_canonical(canonical)
        assert vendor_back["goalName"] == "Retire at 65"
        assert vendor_back["goalId"] == "EM-GOAL-001"
        assert vendor_back["targetAmount"] == 3000000
        assert vendor_back["goalCategory"] == "Retirement"

    def test_color_status(self, translator, emoney_goal):
        emoney_goal["status"] = "green"
        assert translator.goal_to_canonical(emoney_goal).status.value == "on_track"
        emoney_goal["status"] = "yellow"
        assert translator.goal_to_canonical(emoney_goal).status.value == "at_risk"
        emoney_goal["status"] = "red"
        assert translator.goal_to_canonical(emoney_goal).status.value == "behind"
