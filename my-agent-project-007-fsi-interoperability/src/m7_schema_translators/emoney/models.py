"""
eMoney vendor Pydantic models — Financial planning.

SUMMARY-only fields. Raw plan body NEVER crosses the translator boundary
(M4 owns MNPI filtering AFTER translation; M7 rejects raw body at Pydantic
validation via `extra="forbid"`).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class EMoneyRetirementGoal(BaseModel):
    """eMoney plan retirement goal summary."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    amount: Optional[float] = Field(
        default=None, ge=0, description="Retirement goal target amount."
    )
    targetDate: Optional[date] = Field(
        default=None, description="Retirement target date."
    )
    incomeGap: Optional[float] = Field(
        default=None, description="Annual income shortfall (negative = surplus)."
    )


class EMoneyMonteCarlo(BaseModel):
    """eMoney plan Monte Carlo results."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    successPct: Optional[float] = Field(
        default=None, ge=0, le=100, description="Success percentage (0-100)."
    )
    iterations: Optional[int] = Field(
        default=None, description="Number of simulation iterations."
    )


class EMoneyAssumptions(BaseModel):
    """eMoney plan assumptions."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    inflation: Optional[float] = Field(
        default=None, description="Inflation rate (decimal)."
    )
    returnAssumption: Optional[float] = Field(
        default=None, description="Return rate (decimal)."
    )
    lifeExpectancy: Optional[int] = Field(
        default=None, ge=0, description="Life expectancy in years."
    )
    retirementAge: Optional[int] = Field(
        default=None, description="Retirement age."
    )
    taxRate: Optional[float] = Field(
        default=None, description="Tax rate (decimal)."
    )


class EMoneyRecommendation(BaseModel):
    """eMoney plan recommendation — SUMMARY ONLY (no raw plan data)."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    category: str = Field(description="Recommendation category.")
    description: str = Field(description="Recommendation description.")
    priority: str = Field(description="Priority — high, medium, low.")


class EMoneyPlanSummary(BaseModel):
    """eMoney Plan SUMMARY — v2. `extra='forbid'` rejects raw plan body."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    planId: str = Field(description="eMoney plan ID.")
    scenarioId: Optional[str] = Field(
        default=None, description="eMoney scenario ID."
    )
    clientId: str = Field(description="eMoney client ID (REQUIRED).")
    householdId: Optional[str] = Field(
        default=None, description="eMoney household ID."
    )
    planName: str = Field(min_length=1, description="Plan display name.")
    planType: Optional[str] = Field(
        default=None,
        description=(
            "Plan type: Comprehensive, Retirement, Education, Estate, Tax, Insurance."
        ),
    )
    probabilityOfSuccess: float = Field(
        ge=0, le=100, description="Plan success probability (0-100)."
    )
    asOfDate: date = Field(description="Plan as-of date.")
    totalAssets: Optional[float] = Field(
        default=None, ge=0, description="Total assets."
    )
    totalLiabilities: Optional[float] = Field(
        default=None, ge=0, description="Total liabilities."
    )
    retirementGoal: Optional[EMoneyRetirementGoal] = Field(
        default=None, description="Retirement goal summary."
    )
    monteCarlo: Optional[EMoneyMonteCarlo] = Field(
        default=None, description="Monte Carlo results."
    )
    annualSavingsRate: Optional[float] = Field(
        default=None, ge=0, description="Savings rate (decimal)."
    )
    annualSpending: Optional[float] = Field(
        default=None, ge=0, description="Annual spending."
    )
    socialSecurityEstimate: Optional[float] = Field(
        default=None, ge=0, description="Annual SS benefit estimate."
    )
    pensionIncome: Optional[float] = Field(
        default=None, ge=0, description="Annual pension income."
    )
    goalIds: list[str] = Field(
        default_factory=list, description="Linked eMoney goal IDs."
    )
    assumptions: Optional[EMoneyAssumptions] = Field(
        default=None, description="Plan assumptions."
    )
    recommendations: list[EMoneyRecommendation] = Field(
        default_factory=list, description="Plan recommendations (summary)."
    )
    createdAt: datetime = Field(description="Plan creation timestamp.")
    updatedAt: datetime = Field(description="Plan last update timestamp.")
