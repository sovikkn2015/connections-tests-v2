"""
M7 Schema Translator — Salesforce Financial Services Cloud (FSC)

Maps SF FSC objects to canonical types:
  - SF Account/Contact → Client
  - SF FinancialHolding → Holding
  - SF Household → Household (relationship grouping)
  - SF FinancialGoal → Goal

Key issues handled:
  - Person Account vs Account+Contact model
  - Household uses "relationship" grouping (Rule 6)
  - FinancialGoal picklist mapping to canonical GoalType enum
  - PII fields preserved with x-pii markers for M4 filtering
  - vendor_mappings preserved on all types (Rule 12)

Source system: "salesforce_fsc"
Python 3.12+ / Pydantic v2.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from m7_schema_translators._m3_imports import (
    Client,
    ClientVendorMappings,
    ClientVendorSalesforceFSC,
    Goal,
    GoalStatus,
    GoalType,
    GoalVendorMappings,
    GoalVendorSFSC,
    Holding,
    Household,
    HouseholdAccount,
    HouseholdMember,
    HouseholdVendorMappings,
    HouseholdVendorSFSC,
    SecurityIdentifier,
)
from m7_schema_translators.base import (
    MultiTypeTranslator,
    parse_uuid,
    parse_date,
    parse_datetime,
    safe_float,
    map_time_horizon,
    utcnow,
)


# ---------------------------------------------------------------------------
# Mapping tables — SF FSC picklist values → canonical enums
# ---------------------------------------------------------------------------

_SF_RISK_TOLERANCE_MAP: dict[str, str] = {
    "Conservative": "conservative",
    "Moderately Conservative": "moderate_conservative",
    "Moderate": "moderate",
    "Moderately Aggressive": "moderate_aggressive",
    "Aggressive": "aggressive",
}

_SF_GOAL_TYPE_MAP: dict[str, GoalType] = {
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
}

_SF_GOAL_STATUS_MAP: dict[str, GoalStatus] = {
    "On Track": GoalStatus.ON_TRACK,
    "At Risk": GoalStatus.AT_RISK,
    "Behind": GoalStatus.BEHIND,
    "Achieved": GoalStatus.ACHIEVED,
    "Abandoned": GoalStatus.ABANDONED,
    "Not Started": GoalStatus.BEHIND,
    "In Progress": GoalStatus.ON_TRACK,
    "Completed": GoalStatus.ACHIEVED,
}

_SF_GOAL_PRIORITY_MAP: dict[str, str] = {
    "Critical": "critical",
    "High": "high",
    "Medium": "medium",
    "Low": "low",
}

_SF_SECURITY_TYPE_MAP: dict[str, str] = {
    "Stock": "equity",
    "Equity": "equity",
    "Bond": "fixed_income",
    "Fixed Income": "fixed_income",
    "Mutual Fund": "mutual_fund",
    "ETF": "etf",
    "Option": "option",
    "Cash": "cash",
    "Alternative": "alternative",
}

_SF_MEMBER_ROLE_MAP: dict[str, str] = {
    "Primary": "primary",
    "Spouse": "spouse",
    "Dependent": "dependent",
    "Trustee": "trustee",
    "Beneficiary": "beneficiary",
    "Authorized Signer": "authorized_signer",
    "Power of Attorney": "power_of_attorney",
}

# Reverse maps for from_canonical write-back
_CANONICAL_RISK_TO_SF = {v: k for k, v in _SF_RISK_TOLERANCE_MAP.items()}
_CANONICAL_GOAL_TYPE_TO_SF = {v.value: k for k, v in _SF_GOAL_TYPE_MAP.items()}
_CANONICAL_GOAL_STATUS_TO_SF = {
    "on_track": "On Track", "at_risk": "At Risk", "behind": "Behind",
    "achieved": "Achieved", "abandoned": "Abandoned",
}
_CANONICAL_SECURITY_TYPE_TO_SF = {
    "equity": "Stock", "fixed_income": "Bond", "mutual_fund": "Mutual Fund",
    "etf": "ETF", "option": "Option", "cash": "Cash", "alternative": "Alternative",
}
_CANONICAL_MEMBER_ROLE_TO_SF = {v: k for k, v in _SF_MEMBER_ROLE_MAP.items()}


# ---------------------------------------------------------------------------
# Salesforce FSC Translator
# ---------------------------------------------------------------------------

class SalesforceFSCTranslator(MultiTypeTranslator):
    """Translates Salesforce Financial Services Cloud data to/from canonical types.

    Handles the Person Account vs Account+Contact model distinction.
    Preserves vendor_mappings for all types per Rule 12.
    """

    @property
    def source_system(self) -> str:
        return "salesforce_fsc"

    # -----------------------------------------------------------------------
    # Client: SF Account/Contact → canonical Client
    # -----------------------------------------------------------------------

    def client_to_canonical(self, sf_data: dict[str, Any]) -> Client:
        """Convert SF FSC Account/Contact to canonical Client."""
        account_id = self._require_field(sf_data, "Id", "SF Account.Id")
        is_person_account = sf_data.get("IsPersonAccount", False)

        record_type = (
            sf_data.get("RecordType", {}).get("Name", "")
            if isinstance(sf_data.get("RecordType"), dict)
            else ""
        )
        if "Trust" in record_type:
            client_type = "trust"
        elif is_person_account or sf_data.get("FirstName"):
            client_type = "individual"
        else:
            client_type = "entity"

        first_name = sf_data.get("FirstName") or sf_data.get("PersonFirstName")
        last_name = sf_data.get("LastName") or sf_data.get("PersonLastName")
        display_name = sf_data.get("Name", "")
        if not display_name and first_name and last_name:
            display_name = f"{first_name} {last_name}"

        email = sf_data.get("PersonEmail") or sf_data.get("Email__c")
        phone = sf_data.get("Phone") or sf_data.get("PersonMobilePhone")
        dob_raw = sf_data.get("PersonBirthdate") or sf_data.get("Date_of_Birth__c")
        dob = parse_date(dob_raw) if dob_raw else None

        sf_risk = sf_data.get("Risk_Tolerance__c") or sf_data.get("FinServ__RiskTolerance__c")
        risk_tolerance = _SF_RISK_TOLERANCE_MAP.get(sf_risk) if sf_risk else None

        objectives_raw = sf_data.get("Investment_Objectives__c") or sf_data.get(
            "FinServ__InvestmentObjectives__c", ""
        )
        investment_objectives = (
            [o.strip().lower().replace(" ", "_") for o in objectives_raw.split(";") if o.strip()]
            if objectives_raw
            else []
        )

        kyc_raw = sf_data.get("KYC_Status__c")
        kyc_status = (
            kyc_raw.lower()
            if kyc_raw and kyc_raw.lower() in {"pending", "verified", "expired", "failed"}
            else None
        )

        canonical_id = parse_uuid(sf_data.get("Canonical_Id__c")) or uuid4()

        return Client(
            canonical_id=canonical_id,
            display_name=display_name or "Unknown",
            client_type=client_type,
            first_name=first_name,
            last_name=last_name,
            email=email,
            phone=phone,
            date_of_birth=dob,
            ssn_last_four=sf_data.get("SSN_Last_Four__c"),
            tax_id=sf_data.get("Tax_Id__c"),
            risk_tolerance=risk_tolerance,
            investment_objectives=investment_objectives,
            time_horizon=map_time_horizon(sf_data.get("Time_Horizon__c")),
            annual_income_range=sf_data.get("Annual_Income_Range__c"),
            net_worth_range=sf_data.get("Net_Worth_Range__c"),
            liquid_net_worth_range=sf_data.get("Liquid_Net_Worth_Range__c"),
            tax_bracket=sf_data.get("Tax_Bracket__c"),
            advisor_ref=parse_uuid(sf_data.get("Advisor_Ref__c")),
            firm_id=parse_uuid(sf_data.get("Firm_Id__c")) or uuid4(),
            household_ref=parse_uuid(sf_data.get("FinServ__Household__c")),
            archetype=sf_data.get("Archetype__c"),
            jurisdiction=sf_data.get("Jurisdiction__c", "US"),
            accounts=[UUID(a) for a in sf_data.get("Account_Ids__c", []) if parse_uuid(a)],
            kyc_status=kyc_status,
            kyc_verified_date=parse_date(sf_data.get("KYC_Verified_Date__c")),
            pii_classification=sf_data.get("PII_Classification__c", "confidential"),
            vendor_mappings=ClientVendorMappings(
                salesforce_fsc=ClientVendorSalesforceFSC(
                    account_id=account_id,
                    contact_id=sf_data.get("PersonContactId") or sf_data.get("Contact_Id__c"),
                    person_account=is_person_account,
                ),
            ),
            reconciliation=None,
            source_system=self.source_system,
            source_id=account_id,
            created_at=parse_datetime(sf_data.get("CreatedDate")) or utcnow(),
            updated_at=parse_datetime(sf_data.get("LastModifiedDate")) or utcnow(),
        )

    def client_from_canonical(self, client: Client) -> dict[str, Any]:
        """Convert canonical Client back to SF FSC Account format for write-back."""
        sf_mapping = client.vendor_mappings.salesforce_fsc if client.vendor_mappings else None
        is_person = sf_mapping.person_account if sf_mapping else (client.client_type == "individual")

        result: dict[str, Any] = {
            "Name": client.display_name,
            "Phone": client.phone,
            "IsPersonAccount": is_person,
        }
        if sf_mapping:
            result["Id"] = sf_mapping.account_id

        if is_person:
            result["FirstName"] = client.first_name
            result["LastName"] = client.last_name
            result["PersonEmail"] = client.email
            if client.date_of_birth:
                result["PersonBirthdate"] = client.date_of_birth.isoformat()
        else:
            result["Email__c"] = client.email

        if client.risk_tolerance:
            result["Risk_Tolerance__c"] = _CANONICAL_RISK_TO_SF.get(
                client.risk_tolerance, client.risk_tolerance
            )
        if client.investment_objectives:
            result["Investment_Objectives__c"] = ";".join(client.investment_objectives)
        if client.kyc_status:
            result["KYC_Status__c"] = client.kyc_status.capitalize()

        return result

    # -----------------------------------------------------------------------
    # Holding: SF FinancialHolding → canonical Holding
    # -----------------------------------------------------------------------

    def holding_to_canonical(self, sf_data: dict[str, Any]) -> Holding:
        """Convert SF FSC FinancialHolding to canonical Holding."""
        holding_id = self._require_field(sf_data, "Id", "SF FinancialHolding.Id")
        canonical_id = parse_uuid(sf_data.get("Canonical_Id__c")) or uuid4()

        ticker = sf_data.get("Ticker__c") or sf_data.get("FinServ__Symbol__c")
        cusip = sf_data.get("CUSIP__c")
        security_identifier = (
            SecurityIdentifier(
                ticker=ticker, cusip=cusip,
                isin=sf_data.get("ISIN__c"), figi=sf_data.get("FIGI__c"),
                sedol=sf_data.get("SEDOL__c"),
            )
            if any([ticker, cusip])
            else None
        )

        quantity = float(sf_data.get("FinServ__Shares__c", 0) or sf_data.get("Quantity__c", 0))
        market_value = float(
            sf_data.get("FinServ__MarketValue__c", 0) or sf_data.get("Market_Value__c", 0)
        )
        cost_basis_raw = sf_data.get("FinServ__CostBasis__c") or sf_data.get("Cost_Basis__c")

        security_type_raw = sf_data.get("Security_Type__c") or sf_data.get(
            "FinServ__AssetClass__c", ""
        )
        security_type = _SF_SECURITY_TYPE_MAP.get(security_type_raw, "other")
        as_of_raw = sf_data.get("As_Of_Date__c") or sf_data.get("FinServ__AsOfDate__c")

        return Holding(
            canonical_id=canonical_id,
            account_ref=sf_data.get("FinServ__FinancialAccount__c", ""),
            client_ref=sf_data.get("Client_Ref__c"),
            security_identifier=security_identifier,
            security_name=sf_data.get("Name") or sf_data.get("FinServ__Securities__c"),
            security_type=security_type,
            quantity=quantity,
            market_value=market_value,
            market_value_includes_accrued=False,
            cost_basis=float(cost_basis_raw) if cost_basis_raw is not None else None,
            unrealized_gain_loss=safe_float(sf_data.get("FinServ__GainLoss__c")),
            unrealized_gain_loss_pct=safe_float(sf_data.get("Gain_Loss_Pct__c")),
            weight_in_account=safe_float(sf_data.get("Weight__c")),
            currency=sf_data.get("CurrencyIsoCode", "USD"),
            as_of_date=parse_date(as_of_raw) or date.today(),
            account_type=None,
            source_system=self.source_system,
            source_id=holding_id,
            tax_lots=[],
        )

    def holding_from_canonical(self, holding: Holding) -> dict[str, Any]:
        """Convert canonical Holding back to SF FSC FinancialHolding for write-back."""
        result: dict[str, Any] = {
            "FinServ__Shares__c": holding.quantity,
            "FinServ__MarketValue__c": holding.market_value,
            "Name": holding.security_name,
        }
        if holding.security_identifier:
            result["Ticker__c"] = holding.security_identifier.ticker
            result["CUSIP__c"] = holding.security_identifier.cusip
        if holding.cost_basis is not None:
            result["FinServ__CostBasis__c"] = holding.cost_basis
        if holding.unrealized_gain_loss is not None:
            result["FinServ__GainLoss__c"] = holding.unrealized_gain_loss
        result["Security_Type__c"] = _CANONICAL_SECURITY_TYPE_TO_SF.get(
            holding.security_type or "", holding.security_type
        )
        result["As_Of_Date__c"] = holding.as_of_date.isoformat()
        return result

    # -----------------------------------------------------------------------
    # Household: SF FSC Household → canonical Household (CONTAINER)
    # -----------------------------------------------------------------------

    def household_to_canonical(self, sf_data: dict[str, Any]) -> Household:
        """SF FSC Household uses "relationship" grouping (Rule 6)."""
        household_id = self._require_field(sf_data, "Id", "SF Household.Id")
        canonical_id = parse_uuid(sf_data.get("Canonical_Id__c")) or uuid4()

        members_raw = sf_data.get("Members", [])
        members = []
        for m in members_raw:
            role_raw = m.get("Role", m.get("FinServ__Role__c", "primary"))
            role = _SF_MEMBER_ROLE_MAP.get(role_raw, role_raw.lower().replace(" ", "_"))
            members.append(HouseholdMember(
                client_ref=m.get("Client_Ref__c", m.get("ContactId", "")),
                role=role,
                source=self.source_system,
            ))

        accounts_raw = sf_data.get("Accounts", [])
        accounts = [
            HouseholdAccount(
                account_ref=a.get("Account_Ref__c", a.get("Id", "")),
                source=self.source_system,
            )
            for a in accounts_raw
        ]

        return Household(
            canonical_id=canonical_id,
            display_name=sf_data.get("Name", ""),
            primary_source=self.source_system,
            members=members,
            accounts=accounts,
            vendor_mappings=HouseholdVendorMappings(
                salesforce_fsc=HouseholdVendorSFSC(
                    household_id=household_id,
                    grouping_type="relationship",
                ),
            ),
            reconciliation=None,
        )

    def household_from_canonical(self, household: Household) -> dict[str, Any]:
        """Convert canonical Household back to SF FSC format."""
        sf_mapping = (
            household.vendor_mappings.salesforce_fsc if household.vendor_mappings else None
        )
        result: dict[str, Any] = {"Name": household.display_name}
        if sf_mapping:
            result["Id"] = sf_mapping.household_id

        result["Members"] = [
            {
                "Client_Ref__c": m.client_ref,
                "FinServ__Role__c": _CANONICAL_MEMBER_ROLE_TO_SF.get(m.role, m.role),
            }
            for m in household.members
            if m.source == self.source_system or sf_mapping
        ]
        result["Accounts"] = [
            {"Account_Ref__c": a.account_ref}
            for a in household.accounts
            if a.source == self.source_system or sf_mapping
        ]
        return result

    # -----------------------------------------------------------------------
    # Goal: SF FSC FinancialGoal → canonical Goal
    # -----------------------------------------------------------------------

    def goal_to_canonical(self, sf_data: dict[str, Any]) -> Goal:
        """Convert SF FSC FinancialGoal to canonical Goal."""
        goal_id = self._require_field(sf_data, "Id", "SF FinancialGoal.Id")
        canonical_id = parse_uuid(sf_data.get("Canonical_Id__c")) or uuid4()

        sf_goal_type = sf_data.get("Type__c") or sf_data.get("FinServ__GoalType__c", "Custom")
        goal_type = _SF_GOAL_TYPE_MAP.get(sf_goal_type, GoalType.CUSTOM)

        sf_status = sf_data.get("Status__c") or sf_data.get("FinServ__Status__c", "On Track")
        status = _SF_GOAL_STATUS_MAP.get(sf_status, GoalStatus.ON_TRACK)

        sf_priority = sf_data.get("Priority__c", "Medium")
        priority = _SF_GOAL_PRIORITY_MAP.get(sf_priority, "medium")

        target_amount = float(
            sf_data.get("FinServ__TargetValue__c", 0) or sf_data.get("Target_Amount__c", 0)
        )
        current_amount = safe_float(
            sf_data.get("FinServ__ActualValue__c") or sf_data.get("Current_Amount__c")
        )
        funding_pct = None
        if current_amount is not None and target_amount > 0:
            funding_pct = round((current_amount / target_amount) * 100, 2)

        target_date_raw = sf_data.get("FinServ__TargetDate__c") or sf_data.get("Target_Date__c")
        linked_raw = sf_data.get("Linked_Account_Ids__c", [])
        linked_accounts = [UUID(a) for a in linked_raw if parse_uuid(a)]

        return Goal(
            canonical_id=canonical_id,
            client_ref=parse_uuid(
                sf_data.get("FinServ__PrimaryOwner__c") or sf_data.get("Client_Ref__c")
            ) or uuid4(),
            household_ref=parse_uuid(sf_data.get("Household_Ref__c")),
            plan_ref=parse_uuid(sf_data.get("Plan_Ref__c")),
            goal_type=goal_type,
            goal_name=sf_data.get("Name", sf_goal_type),
            target_amount=target_amount,
            current_amount=current_amount,
            funding_pct=funding_pct,
            target_date=parse_date(target_date_raw) or date.today(),
            priority=priority,
            status=status,
            monthly_contribution=safe_float(sf_data.get("Monthly_Contribution__c")),
            linked_accounts=linked_accounts,
            assumptions=None,
            vendor_mappings=GoalVendorMappings(
                salesforce_fsc=GoalVendorSFSC(
                    financial_goal_id=goal_id,
                    goal_type_picklist=sf_goal_type,
                ),
            ),
            as_of_date=parse_date(sf_data.get("As_Of_Date__c")) or date.today(),
            source_system=self.source_system,
            source_id=goal_id,
            created_at=parse_datetime(sf_data.get("CreatedDate")) or utcnow(),
            updated_at=parse_datetime(sf_data.get("LastModifiedDate")) or utcnow(),
        )

    def goal_from_canonical(self, goal: Goal) -> dict[str, Any]:
        """Convert canonical Goal back to SF FSC FinancialGoal for write-back."""
        sf_mapping = goal.vendor_mappings.salesforce_fsc if goal.vendor_mappings else None

        result: dict[str, Any] = {
            "Name": goal.goal_name,
            "FinServ__TargetValue__c": goal.target_amount,
            "FinServ__TargetDate__c": goal.target_date.isoformat(),
            "Type__c": _CANONICAL_GOAL_TYPE_TO_SF.get(
                goal.goal_type.value if isinstance(goal.goal_type, GoalType) else goal.goal_type,
                "Custom",
            ),
            "Status__c": _CANONICAL_GOAL_STATUS_TO_SF.get(
                goal.status.value if isinstance(goal.status, GoalStatus) else goal.status,
                "On Track",
            ),
        }
        if sf_mapping:
            result["Id"] = sf_mapping.financial_goal_id
        if goal.current_amount is not None:
            result["FinServ__ActualValue__c"] = goal.current_amount
        if goal.monthly_contribution is not None:
            result["Monthly_Contribution__c"] = goal.monthly_contribution
        return result
