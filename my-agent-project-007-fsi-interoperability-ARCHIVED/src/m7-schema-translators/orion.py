"""
M7 Schema Translator — Orion Advisor Solutions

Maps Orion objects to canonical types:
  - Orion Client → Client
  - Orion Position → Holding (market_value_includes_accrued flag)
  - Orion Portfolio/Household → Household (portfolio_management grouping)
  - Orion Transaction → Transaction
  - Orion Performance → Performance (daily_valuation methodology)

Key issues handled:
  - Hierarchical data model: Representative→Client→Portfolio→Account→Position→TaxLot
  - MarketValue may include accrued interest (PENDING SME — flag set explicitly)
  - portfolio_management grouping for Household (Rule 6)
  - vendor_mappings preserved on all types (Rule 12)

Source system: "orion"
Python 3.12+ / Pydantic v2.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from m7_schema_translators._m3_imports import (
    AccountType,
    Client,
    ClientVendorMappings,
    ClientVendorOrion,
    CostBasisImpact,
    Holding,
    Household,
    HouseholdAccount,
    HouseholdMember,
    HouseholdVendorMappings,
    HouseholdVendorOrion,
    Performance,
    PerformanceMethodology,
    PerformancePeriod,
    SecurityIdentifier,
    Transaction,
    TransactionType,
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
# Mapping tables — Orion field values → canonical enums
# ---------------------------------------------------------------------------

_ORION_ACCOUNT_TYPE_MAP: dict[str, AccountType] = {
    "Individual": AccountType.TAXABLE,
    "Joint": AccountType.TAXABLE,
    "Traditional IRA": AccountType.TRADITIONAL_IRA,
    "Roth IRA": AccountType.ROTH_IRA,
    "SEP IRA": AccountType.SEP_IRA,
    "SIMPLE IRA": AccountType.SIMPLE_IRA,
    "401(k)": AccountType.K401,
    "403(b)": AccountType.B403,
    "457": AccountType.B457,
    "Trust": AccountType.TRUST_REVOCABLE,
    "Irrevocable Trust": AccountType.TRUST_IRREVOCABLE,
    "UTMA": AccountType.CUSTODIAL_UTMA,
    "UGMA": AccountType.CUSTODIAL_UGMA,
    "Pension": AccountType.ERISA_PENSION,
    "Profit Sharing": AccountType.ERISA_PROFIT_SHARING,
    "529": AccountType.PLAN_529,
    "HSA": AccountType.HSA,
}

_ORION_TRANSACTION_TYPE_MAP: dict[str, TransactionType] = {
    "Buy": TransactionType.BUY,
    "Sell": TransactionType.SELL,
    "Short Sell": TransactionType.SELL_SHORT,
    "Buy to Cover": TransactionType.BUY_TO_COVER,
    "Dividend": TransactionType.DIVIDEND,
    "Interest": TransactionType.INTEREST,
    "Fee": TransactionType.FEE,
    "Advisory Fee": TransactionType.MANAGEMENT_FEE,
    "Management Fee": TransactionType.MANAGEMENT_FEE,
    "Transfer In": TransactionType.TRANSFER_IN,
    "Transfer Out": TransactionType.TRANSFER_OUT,
    "Distribution": TransactionType.DISTRIBUTION,
    "Contribution": TransactionType.CONTRIBUTION,
    "Wire In": TransactionType.WIRE_IN,
    "Wire Out": TransactionType.WIRE_OUT,
    "Journal": TransactionType.JOURNAL,
    "Reinvestment": TransactionType.REINVESTMENT,
    "Return of Capital": TransactionType.RETURN_OF_CAPITAL,
    "Corporate Action": TransactionType.CORPORATE_ACTION,
    "Margin Interest": TransactionType.MARGIN_INTEREST,
}

_ORION_PERFORMANCE_PERIOD_MAP: dict[str, PerformancePeriod] = {
    "MTD": PerformancePeriod.MTD,
    "QTD": PerformancePeriod.QTD,
    "YTD": PerformancePeriod.YTD,
    "1 Year": PerformancePeriod.Y1,
    "3 Year": PerformancePeriod.Y3,
    "5 Year": PerformancePeriod.Y5,
    "10 Year": PerformancePeriod.Y10,
    "ITD": PerformancePeriod.ITD,
    "Since Inception": PerformancePeriod.ITD,
    "Custom": PerformancePeriod.CUSTOM,
}

_ORION_SECURITY_TYPE_MAP: dict[str, str] = {
    "Equity": "equity",
    "Stock": "equity",
    "Fixed Income": "fixed_income",
    "Bond": "fixed_income",
    "Mutual Fund": "mutual_fund",
    "ETF": "etf",
    "Option": "option",
    "Cash": "cash",
    "Money Market": "cash",
    "Alternative": "alternative",
}

_ORION_MEMBER_ROLE_MAP: dict[str, str] = {
    "Primary": "primary",
    "Spouse": "spouse",
    "Dependent": "dependent",
    "Trustee": "trustee",
    "Beneficiary": "beneficiary",
}

# Reverse maps for from_canonical
_CANONICAL_ACCOUNT_TYPE_TO_ORION = {v.value: k for k, v in _ORION_ACCOUNT_TYPE_MAP.items()}
_CANONICAL_TX_TYPE_TO_ORION = {v.value: k for k, v in _ORION_TRANSACTION_TYPE_MAP.items()}
_CANONICAL_PERIOD_TO_ORION = {v.value: k for k, v in _ORION_PERFORMANCE_PERIOD_MAP.items()}
_CANONICAL_SECURITY_TYPE_TO_ORION = {v: k for k, v in _ORION_SECURITY_TYPE_MAP.items()}


# ---------------------------------------------------------------------------
# Orion Translator
# ---------------------------------------------------------------------------

class OrionTranslator(MultiTypeTranslator):
    """Translates Orion Advisor Solutions data to/from canonical types.

    Orion uses a hierarchical data model:
      Representative → Client → Portfolio → Account → Position → TaxLot

    MarketValue may include accrued interest — the market_value_includes_accrued
    flag is set explicitly based on the Orion feed configuration.
    """

    @property
    def source_system(self) -> str:
        return "orion"

    # -----------------------------------------------------------------------
    # Client: Orion Client → canonical Client
    # -----------------------------------------------------------------------

    def client_to_canonical(self, orion_data: dict[str, Any]) -> Client:
        """Convert Orion Client to canonical Client."""
        client_id = str(self._require_field(orion_data, "id", "Orion Client.id"))
        canonical_id = parse_uuid(orion_data.get("canonical_id")) or uuid4()

        first_name = orion_data.get("firstName")
        last_name = orion_data.get("lastName")
        display_name = orion_data.get("name", "")
        if not display_name and first_name and last_name:
            display_name = f"{first_name} {last_name}"

        entity_type = orion_data.get("entityType", "Individual")
        if "trust" in entity_type.lower():
            client_type = "trust"
        elif entity_type.lower() in {"individual", "joint"}:
            client_type = "individual"
        else:
            client_type = "entity"

        risk_profile = orion_data.get("riskProfile", {})
        risk_tolerance = (
            risk_profile.get("riskTolerance", "").lower() or None
            if isinstance(risk_profile, dict)
            else None
        )

        return Client(
            canonical_id=canonical_id,
            display_name=display_name or "Unknown",
            client_type=client_type,
            first_name=first_name,
            last_name=last_name,
            email=orion_data.get("email"),
            phone=orion_data.get("phone"),
            date_of_birth=parse_date(orion_data.get("dateOfBirth")),
            ssn_last_four=orion_data.get("ssnLastFour"),
            tax_id=orion_data.get("taxId"),
            risk_tolerance=risk_tolerance,
            investment_objectives=orion_data.get("investmentObjectives", []),
            time_horizon=map_time_horizon(orion_data.get("timeHorizon")),
            annual_income_range=orion_data.get("annualIncomeRange"),
            net_worth_range=orion_data.get("netWorthRange"),
            liquid_net_worth_range=orion_data.get("liquidNetWorthRange"),
            tax_bracket=orion_data.get("taxBracket"),
            advisor_ref=parse_uuid(orion_data.get("advisorRef")),
            firm_id=parse_uuid(orion_data.get("firmId")) or uuid4(),
            household_ref=parse_uuid(orion_data.get("householdId")),
            archetype=orion_data.get("archetype"),
            jurisdiction=orion_data.get("jurisdiction", "US"),
            accounts=[UUID(a) for a in orion_data.get("accountIds", []) if parse_uuid(a)],
            kyc_status=orion_data.get("kycStatus"),
            kyc_verified_date=parse_date(orion_data.get("kycVerifiedDate")),
            pii_classification=orion_data.get("piiClassification", "confidential"),
            vendor_mappings=ClientVendorMappings(
                orion=ClientVendorOrion(
                    client_id=client_id,
                    representative_id=orion_data.get("representativeId"),
                ),
            ),
            reconciliation=None,
            source_system=self.source_system,
            source_id=client_id,
            created_at=parse_datetime(orion_data.get("createdDate")) or utcnow(),
            updated_at=parse_datetime(orion_data.get("lastModifiedDate")) or utcnow(),
        )

    def client_from_canonical(self, client: Client) -> dict[str, Any]:
        """Convert canonical Client back to Orion Client format."""
        orion_mapping = client.vendor_mappings.orion if client.vendor_mappings else None
        result: dict[str, Any] = {
            "name": client.display_name,
            "firstName": client.first_name,
            "lastName": client.last_name,
            "email": client.email,
            "phone": client.phone,
        }
        if orion_mapping:
            result["id"] = orion_mapping.client_id
            if orion_mapping.representative_id:
                result["representativeId"] = orion_mapping.representative_id
        if client.date_of_birth:
            result["dateOfBirth"] = client.date_of_birth.isoformat()
        if client.risk_tolerance:
            result["riskProfile"] = {"riskTolerance": client.risk_tolerance}
        return result

    # -----------------------------------------------------------------------
    # Holding: Orion Position → canonical Holding
    # -----------------------------------------------------------------------

    def holding_to_canonical(self, orion_data: dict[str, Any]) -> Holding:
        """Convert Orion Position to canonical Holding.

        CRITICAL: Orion MarketValue may include accrued interest for fixed income.
        The market_value_includes_accrued flag is set based on asset class.
        """
        position_id = str(self._require_field(orion_data, "id", "Orion Position.id"))
        canonical_id = parse_uuid(orion_data.get("canonical_id")) or uuid4()

        ticker = orion_data.get("ticker") or orion_data.get("symbol")
        cusip = orion_data.get("cusip")
        security_identifier = (
            SecurityIdentifier(
                ticker=ticker, cusip=cusip,
                isin=orion_data.get("isin"), figi=orion_data.get("figi"),
                sedol=orion_data.get("sedol"),
            )
            if any([ticker, cusip])
            else None
        )

        quantity = float(orion_data.get("units", 0) or orion_data.get("shares", 0))
        market_value = float(orion_data.get("marketValue", 0))

        asset_class = orion_data.get("assetClass", "")
        includes_accrued = orion_data.get(
            "marketValueIncludesAccrued",
            asset_class.lower() in {"fixed income", "bond"},
        )
        security_type = _ORION_SECURITY_TYPE_MAP.get(asset_class, "other")
        account_type_raw = orion_data.get("accountType")
        account_type = _ORION_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        return Holding(
            canonical_id=canonical_id,
            account_ref=str(orion_data.get("accountId", "")),
            client_ref=orion_data.get("clientId"),
            security_identifier=security_identifier,
            security_name=orion_data.get("securityName") or orion_data.get("description"),
            security_type=security_type,
            quantity=quantity,
            market_value=market_value,
            market_value_includes_accrued=includes_accrued,
            cost_basis=safe_float(orion_data.get("costBasis")),
            unrealized_gain_loss=safe_float(orion_data.get("unrealizedGainLoss")),
            unrealized_gain_loss_pct=safe_float(orion_data.get("unrealizedGainLossPct")),
            weight_in_account=safe_float(orion_data.get("weight")),
            currency=orion_data.get("currency", "USD"),
            as_of_date=parse_date(orion_data.get("asOfDate")) or date.today(),
            account_type=account_type,
            source_system=self.source_system,
            source_id=position_id,
            tax_lots=[],
        )

    def holding_from_canonical(self, holding: Holding) -> dict[str, Any]:
        """Convert canonical Holding back to Orion Position format."""
        result: dict[str, Any] = {
            "units": holding.quantity,
            "marketValue": holding.market_value,
            "description": holding.security_name,
            "marketValueIncludesAccrued": holding.market_value_includes_accrued,
        }
        if holding.security_identifier:
            result["ticker"] = holding.security_identifier.ticker
            result["cusip"] = holding.security_identifier.cusip
        if holding.cost_basis is not None:
            result["costBasis"] = holding.cost_basis
        if holding.unrealized_gain_loss is not None:
            result["unrealizedGainLoss"] = holding.unrealized_gain_loss
        result["assetClass"] = _CANONICAL_SECURITY_TYPE_TO_ORION.get(
            holding.security_type or "", holding.security_type
        )
        result["asOfDate"] = holding.as_of_date.isoformat()
        return result

    # -----------------------------------------------------------------------
    # Household: Orion Household → canonical Household (CONTAINER)
    # -----------------------------------------------------------------------

    def household_to_canonical(self, orion_data: dict[str, Any]) -> Household:
        """Convert Orion Household to canonical Household.
        Orion uses "portfolio_management" grouping (Rule 6).
        """
        household_id = str(self._require_field(orion_data, "id", "Orion Household.id"))
        canonical_id = parse_uuid(orion_data.get("canonical_id")) or uuid4()

        members_raw = orion_data.get("members", [])
        members = [
            HouseholdMember(
                client_ref=str(m.get("clientId", "")),
                role=_ORION_MEMBER_ROLE_MAP.get(m.get("role", "Primary"), m.get("role", "primary").lower()),
                source=self.source_system,
            )
            for m in members_raw
        ]

        accounts_raw = orion_data.get("accounts", [])
        accounts = [
            HouseholdAccount(
                account_ref=str(a.get("accountId", a.get("id", ""))),
                source=self.source_system,
            )
            for a in accounts_raw
        ]

        return Household(
            canonical_id=canonical_id,
            display_name=orion_data.get("name", ""),
            primary_source=self.source_system,
            members=members,
            accounts=accounts,
            vendor_mappings=HouseholdVendorMappings(
                orion=HouseholdVendorOrion(
                    household_id=household_id,
                    grouping_type="portfolio_management",
                ),
            ),
            reconciliation=None,
        )

    def household_from_canonical(self, household: Household) -> dict[str, Any]:
        """Convert canonical Household back to Orion format."""
        orion_mapping = household.vendor_mappings.orion if household.vendor_mappings else None
        result: dict[str, Any] = {"name": household.display_name}
        if orion_mapping:
            result["id"] = orion_mapping.household_id
        result["members"] = [
            {"clientId": m.client_ref, "role": m.role.capitalize()}
            for m in household.members
            if m.source == self.source_system or orion_mapping
        ]
        result["accounts"] = [
            {"accountId": a.account_ref}
            for a in household.accounts
            if a.source == self.source_system or orion_mapping
        ]
        return result

    # -----------------------------------------------------------------------
    # Transaction: Orion Transaction → canonical Transaction
    # -----------------------------------------------------------------------

    def transaction_to_canonical(self, orion_data: dict[str, Any]) -> Transaction:
        """Convert Orion Transaction to canonical Transaction."""
        tx_id = str(self._require_field(orion_data, "id", "Orion Transaction.id"))
        orion_type = orion_data.get("transactionType", "")
        tx_type = _ORION_TRANSACTION_TYPE_MAP.get(orion_type, TransactionType.JOURNAL)

        account_type_raw = orion_data.get("accountType")
        account_type = _ORION_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        cost_basis_impact = None
        if orion_data.get("realizedGainLoss") is not None:
            cost_basis_impact = CostBasisImpact(
                realized_gain_loss=safe_float(orion_data.get("realizedGainLoss")),
                holding_period=orion_data.get("holdingPeriod"),
                wash_sale_disallowed=safe_float(orion_data.get("washSaleDisallowed")),
            )

        ticker = orion_data.get("ticker") or orion_data.get("symbol")
        cusip = orion_data.get("cusip")
        security_identifier = (
            SecurityIdentifier(ticker=ticker, cusip=cusip) if any([ticker, cusip]) else None
        )

        return Transaction(
            transaction_id=parse_uuid(orion_data.get("canonical_id")) or uuid4(),
            account_ref=parse_uuid(orion_data.get("accountId")) or uuid4(),
            client_ref=parse_uuid(orion_data.get("clientId")),
            order_ref=None,
            transaction_type=tx_type,
            security_identifier=security_identifier,
            security_name=orion_data.get("securityName"),
            quantity=safe_float(orion_data.get("units") or orion_data.get("shares")),
            price=safe_float(orion_data.get("price")),
            amount=float(orion_data.get("amount", 0)),
            commission=safe_float(orion_data.get("commission")),
            fees=safe_float(orion_data.get("fees")),
            net_amount=safe_float(orion_data.get("netAmount")),
            trade_date=parse_date(orion_data.get("tradeDate")) or date.today(),
            settlement_date=parse_date(orion_data.get("settlementDate")),
            settlement_status=orion_data.get("settlementStatus", "settled"),
            currency=orion_data.get("currency", "USD"),
            description=orion_data.get("description"),
            tax_lot_ref=orion_data.get("taxLotId"),
            cost_basis_impact=cost_basis_impact,
            account_type=account_type,
            source_system=self.source_system,
            source_id=tx_id,
            source_transaction_type=orion_type,
            trace_id=orion_data.get("traceId"),
            created_at=parse_datetime(orion_data.get("createdDate")) or utcnow(),
        )

    def transaction_from_canonical(self, tx: Transaction) -> dict[str, Any]:
        """Convert canonical Transaction back to Orion format."""
        result: dict[str, Any] = {
            "transactionType": _CANONICAL_TX_TYPE_TO_ORION.get(
                tx.transaction_type.value if isinstance(tx.transaction_type, TransactionType) else tx.transaction_type,
                "Journal",
            ),
            "amount": tx.amount,
            "tradeDate": tx.trade_date.isoformat(),
            "description": tx.description,
        }
        if tx.security_identifier:
            result["ticker"] = tx.security_identifier.ticker
            result["cusip"] = tx.security_identifier.cusip
        if tx.quantity is not None:
            result["units"] = tx.quantity
        if tx.price is not None:
            result["price"] = tx.price
        if tx.commission is not None:
            result["commission"] = tx.commission
        if tx.settlement_date:
            result["settlementDate"] = tx.settlement_date.isoformat()
        return result

    # -----------------------------------------------------------------------
    # Performance: Orion Performance → canonical Performance
    # -----------------------------------------------------------------------

    def performance_to_canonical(self, orion_data: dict[str, Any]) -> Performance:
        """Convert Orion Performance to canonical Performance.
        Orion uses daily_valuation methodology for TWR (GIPS-compliant).
        """
        perf_id = str(self._require_field(orion_data, "id", "Orion Performance.id"))
        period_raw = orion_data.get("period", "Custom")
        period = _ORION_PERFORMANCE_PERIOD_MAP.get(period_raw, PerformancePeriod.CUSTOM)

        methodology_raw = orion_data.get("methodology", "daily_valuation")
        methodology_map = {
            "daily_valuation": PerformanceMethodology.DAILY_VALUATION,
            "modified_dietz": PerformanceMethodology.MODIFIED_DIETZ,
            "irr_only": PerformanceMethodology.IRR_ONLY,
        }
        methodology = methodology_map.get(methodology_raw, PerformanceMethodology.DAILY_VALUATION)

        return Performance(
            performance_id=parse_uuid(orion_data.get("canonical_id")) or uuid4(),
            account_ref=parse_uuid(orion_data.get("accountId")) or uuid4(),
            client_ref=parse_uuid(orion_data.get("clientId")),
            household_ref=parse_uuid(orion_data.get("householdId")),
            period=period,
            twr_return=float(orion_data.get("twrReturn", 0)),
            irr_return=safe_float(orion_data.get("irrReturn")),
            gross_return=safe_float(orion_data.get("grossReturn")),
            net_return=safe_float(orion_data.get("netReturn")),
            benchmark_return=safe_float(orion_data.get("benchmarkReturn")),
            benchmark_name=orion_data.get("benchmarkName"),
            benchmark_ticker=orion_data.get("benchmarkTicker"),
            alpha=safe_float(orion_data.get("alpha")),
            sharpe_ratio=safe_float(orion_data.get("sharpeRatio")),
            standard_deviation=safe_float(orion_data.get("standardDeviation")),
            max_drawdown=safe_float(orion_data.get("maxDrawdown")),
            start_date=parse_date(orion_data.get("startDate")) or date.today(),
            end_date=parse_date(orion_data.get("endDate")) or date.today(),
            start_value=safe_float(orion_data.get("startValue")),
            end_value=safe_float(orion_data.get("endValue")),
            net_flows=safe_float(orion_data.get("netFlows")),
            income_earned=safe_float(orion_data.get("incomeEarned")),
            realized_gains=safe_float(orion_data.get("realizedGains")),
            fees_paid=safe_float(orion_data.get("feesPaid")),
            methodology=methodology,
            is_gips_compliant=orion_data.get("isGipsCompliant", False),
            source_system=self.source_system,
            source_id=perf_id,
            as_of_date=parse_date(orion_data.get("asOfDate")) or date.today(),
        )

    def performance_from_canonical(self, perf: Performance) -> dict[str, Any]:
        """Convert canonical Performance back to Orion format."""
        result: dict[str, Any] = {
            "period": _CANONICAL_PERIOD_TO_ORION.get(
                perf.period.value if isinstance(perf.period, PerformancePeriod) else perf.period,
                "Custom",
            ),
            "twrReturn": perf.twr_return,
            "startDate": perf.start_date.isoformat(),
            "endDate": perf.end_date.isoformat(),
            "methodology": perf.methodology.value if isinstance(perf.methodology, PerformanceMethodology) else perf.methodology,
            "isGipsCompliant": perf.is_gips_compliant,
        }
        if perf.irr_return is not None:
            result["irrReturn"] = perf.irr_return
        if perf.benchmark_return is not None:
            result["benchmarkReturn"] = perf.benchmark_return
            result["benchmarkName"] = perf.benchmark_name
        if perf.sharpe_ratio is not None:
            result["sharpeRatio"] = perf.sharpe_ratio
        if perf.start_value is not None:
            result["startValue"] = perf.start_value
        if perf.end_value is not None:
            result["endValue"] = perf.end_value
        return result
