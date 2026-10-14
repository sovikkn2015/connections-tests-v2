"""
Salesforce FSC vendor Pydantic models.

Phase 2 Lighthouse: Client (Account+Contact), Household
(FinServ__Household__c with members), Goal (FinServ__FinancialGoal__c).

v0.3.1: Added populate_by_name + PascalCase aliases on every field so raw
SFDC REST/SOQL payloads construct without manual rename. Snake_case remains
valid for backward compat. See DECISION-LOG entry 2026-05-06.

Field names remain PENDING-VERIFICATION for FinServ__* custom fields --
assumed per generic FSC extension convention. Real-org SOQL verification
is a pre-GA task.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SalesforceFSCAccountContact(BaseModel):
    """SF FSC Account joined with Contact on PrimaryContactId. v59.0 shape."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    account_id: str = Field(alias="Id", description="SF Account.Id (18-char).")
    name: str = Field(
        alias="Name",
        min_length=1,
        description="SF Account.Name -- display name (required).",
    )
    record_type_name: str = Field(
        alias="RecordTypeName",
        description=(
            "SF Account.RecordType.Name -- PersonAccount, Business Account, Trust."
        ),
    )
    owner_id: Optional[str] = Field(
        default=None,
        alias="OwnerId",
        description="SF Account.OwnerId -- advisor ID.",
    )
    created_date: datetime = Field(
        alias="CreatedDate",
        description="SF Account.CreatedDate -- ISO 8601.",
    )
    last_modified_date: datetime = Field(
        alias="LastModifiedDate",
        description="SF Account.LastModifiedDate -- ISO 8601.",
    )

    firm_id: str = Field(
        alias="FinServ__FirmId__c",
        description="SF Account.FinServ__FirmId__c -- canonical firm ID seed.",
    )
    household_id: Optional[str] = Field(
        default=None,
        alias="FinServ__HouseholdId__c",
        description="SF Account.FinServ__HouseholdId__c.",
    )
    client_archetype: Optional[str] = Field(
        default=None,
        alias="FinServ__ClientArchetype__c",
        description=(
            "SF Account.FinServ__ClientArchetype__c -- passed through, "
            "NO validation."
        ),
    )
    jurisdiction: str = Field(
        alias="FinServ__Jurisdiction__c",
        description=(
            "SF Account.FinServ__Jurisdiction__c -- ISO-3166 or subdivision."
        ),
    )
    account_ids: Optional[str] = Field(
        default=None,
        alias="FinServ__AccountIds__c",
        description=(
            "SF Account.FinServ__AccountIds__c -- SF multi-picklist, "
            "';'-separated."
        ),
    )
    kyc_status: Optional[str] = Field(
        default=None,
        alias="FinServ__KYCStatus__c",
        description="SF Account.FinServ__KYCStatus__c.",
    )
    kyc_last_completed: Optional[date] = Field(
        default=None,
        alias="FinServ__KYCLastCompleted__c",
        description="SF Account.FinServ__KYCLastCompleted__c -- date.",
    )
    last_ssn_digits: Optional[str] = Field(
        default=None,
        alias="FinServ__LastSSNDigits__c",
        description=(
            "SF Account.FinServ__LastSSNDigits__c -- 4-digit SSN (PII)."
        ),
    )
    tax_id: Optional[str] = Field(
        default=None,
        alias="FinServ__TaxID__c",
        description="SF Account.FinServ__TaxID__c -- EIN (PII).",
    )
    risk_tolerance: Optional[str] = Field(
        default=None,
        alias="FinServ__RiskTolerance__c",
        description="SF Account.FinServ__RiskTolerance__c.",
    )
    investment_objectives: Optional[str] = Field(
        default=None,
        alias="FinServ__InvestmentObjectives__c",
        description=(
            "SF Account.FinServ__InvestmentObjectives__c -- multi-picklist "
            "';'-separated."
        ),
    )
    time_horizon: Optional[str] = Field(
        default=None,
        alias="FinServ__TimeHorizon__c",
        description="SF Account.FinServ__TimeHorizon__c.",
    )
    annual_income: Optional[str] = Field(
        default=None,
        alias="FinServ__AnnualIncome__c",
        description="SF Account.FinServ__AnnualIncome__c -- bucket.",
    )
    net_worth: Optional[str] = Field(
        default=None,
        alias="FinServ__NetWorth__c",
        description="SF Account.FinServ__NetWorth__c -- bucket.",
    )
    liquid_net_worth: Optional[str] = Field(
        default=None,
        alias="FinServ__LiquidNetWorth__c",
        description="SF Account.FinServ__LiquidNetWorth__c -- bucket.",
    )
    tax_bracket: Optional[str] = Field(
        default=None,
        alias="FinServ__TaxBracket__c",
        description="SF Account.FinServ__TaxBracket__c.",
    )
    pii_classification: Optional[str] = Field(
        default=None,
        alias="FinServ__PIIClassification__c",
        description=(
            "SF Account.FinServ__PIIClassification__c -- classification tag."
        ),
    )
    person_account: Optional[bool] = Field(
        default=None,
        alias="FinServ__PersonAccount__c",
        description=(
            "SF Account.FinServ__PersonAccount__c -- True for Person Account."
        ),
    )

    contact_id: Optional[str] = Field(
        default=None,
        alias="ContactId",
        description="SF Contact.Id -- None for Business Account.",
    )
    first_name: Optional[str] = Field(
        default=None,
        alias="FirstName",
        description="SF Contact.FirstName -- individual only.",
    )
    last_name: Optional[str] = Field(
        default=None,
        alias="LastName",
        description="SF Contact.LastName -- individual only.",
    )
    email: Optional[str] = Field(
        default=None,
        alias="Email",
        description="SF Contact.Email -- PII, passed through unchanged for M4.",
    )
    phone: Optional[str] = Field(
        default=None,
        alias="Phone",
        description="SF Contact.Phone -- PII, passed through unchanged for M4.",
    )
    birthdate: Optional[date] = Field(
        default=None,
        alias="Birthdate",
        description="SF Contact.Birthdate -- date of birth (PII).",
    )

    @model_validator(mode="after")
    def _business_account_branching(self) -> "SalesforceFSCAccountContact":
        """`record_type_name in {Business Account, Trust}` -> no individual-PII fields."""
        if self.record_type_name in {"Business Account", "Trust"}:
            if any(
                (
                    self.contact_id,
                    self.first_name,
                    self.last_name,
                    self.email,
                    self.phone,
                    self.birthdate,
                )
            ):
                raise ValueError(
                    "Business Account / Trust must have no Contact-level "
                    "individual fields"
                )
        return self


class SalesforceFSCHouseholdMember(BaseModel):
    """Member row on FinServ__HouseholdMember__c."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    account_id: str = Field(
        alias="AccountId",
        description="Member AccountId (maps to client_ref).",
    )
    role: str = Field(
        alias="Role",
        description="Role picklist -- Primary, Spouse, etc.",
    )


class SalesforceFSCHousehold(BaseModel):
    """FinServ__Household__c + FinServ__HouseholdMember__c list."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    household_id: str = Field(
        alias="Id",
        description="FinServ__Household__c.Id (18-char).",
    )
    name: str = Field(
        alias="Name",
        min_length=1,
        description="FinServ__Household__c.Name.",
    )
    members: list[SalesforceFSCHouseholdMember] = Field(
        default_factory=list,
        alias="Members",
        description="FinServ__HouseholdMember__c rows.",
    )
    account_ids: Optional[str] = Field(
        default=None,
        alias="FinServ__AccountIds__c",
        description=(
            "FinServ__Household__c.FinServ__AccountIds__c -- ';'-separated."
        ),
    )


class SalesforceFSCFinancialGoal(BaseModel):
    """FinServ__FinancialGoal__c (v59.0 shape)."""

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        str_strip_whitespace=True,
        populate_by_name=True,
    )

    goal_id: str = Field(
        alias="Id",
        description="FinServ__FinancialGoal__c.Id.",
    )
    name: str = Field(
        alias="Name",
        min_length=1,
        description="Goal display name.",
    )
    goal_type: str = Field(
        alias="FinServ__GoalType__c",
        description="FinServ__GoalType__c picklist.",
    )
    status: str = Field(
        alias="FinServ__Status__c",
        description="FinServ__Status__c picklist.",
    )
    target_amount: float = Field(
        alias="FinServ__TargetAmount__c",
        ge=0,
        description="FinServ__TargetAmount__c.",
    )
    current_amount: Optional[float] = Field(
        default=None,
        alias="FinServ__CurrentAmount__c",
        ge=0,
        description="FinServ__CurrentAmount__c.",
    )
    target_date: date = Field(
        alias="FinServ__TargetDate__c",
        description="FinServ__TargetDate__c.",
    )
    priority: str = Field(
        alias="FinServ__Priority__c",
        description="FinServ__Priority__c -- critical/high/medium/low.",
    )
    client_account_id: str = Field(
        alias="FinServ__ClientAccountId__c",
        description="FinServ__ClientAccountId__c -- client ref seed.",
    )
    household_id: Optional[str] = Field(
        default=None,
        alias="FinServ__HouseholdId__c",
        description="FinServ__HouseholdId__c if household-level goal.",
    )
    monthly_contribution: Optional[float] = Field(
        default=None,
        alias="FinServ__MonthlyContribution__c",
        ge=0,
        description="FinServ__MonthlyContribution__c.",
    )
    linked_account_ids: Optional[str] = Field(
        default=None,
        alias="FinServ__LinkedAccountIds__c",
        description=(
            "FinServ__LinkedAccountIds__c -- ';'-separated Account IDs."
        ),
    )
    inflation_rate: Optional[float] = Field(
        default=None,
        alias="FinServ__InflationRate__c",
        description="FinServ__InflationRate__c.",
    )
    return_rate: Optional[float] = Field(
        default=None,
        alias="FinServ__ReturnRate__c",
        description="FinServ__ReturnRate__c.",
    )
    tax_rate: Optional[float] = Field(
        default=None,
        alias="FinServ__TaxRate__c",
        description="FinServ__TaxRate__c.",
    )
    as_of_date: date = Field(
        alias="FinServ__AsOfDate__c",
        description="FinServ__AsOfDate__c.",
    )
    created_date: datetime = Field(
        alias="CreatedDate",
        description="CreatedDate.",
    )
    last_modified_date: datetime = Field(
        alias="LastModifiedDate",
        description="LastModifiedDate.",
    )
