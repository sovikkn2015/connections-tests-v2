"""
M7 Schema Translator — Charles Schwab Advisor Services

Maps Schwab objects to canonical types:
  - Schwab Account → Client
  - Schwab Position → Holding
  - Schwab TaxLot → TaxLot (cost_basis_method=specific_lot default — Rule 7)
  - Schwab Transaction → Transaction
  - Schwab Balance → Balance (real-time API vs SFTP)
  - Schwab master_account → Household (custodial grouping)

Key issues handled:
  - cost_basis_method defaults to specific_lot (Rule 7 — NEVER null)
  - Dual source: real-time REST API ("schwab") vs daily SFTP files ("schwab_sftp")
  - is_real_time flag on Balance distinguishes API vs file source
  - master_account grouping for Household (custodial — Rule 6)
  - vendor_mappings preserved on all types (Rule 12)

Source system: "schwab" (API) or "schwab_sftp" (daily files)
Python 3.12+ / Pydantic v2.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from m7_schema_translators._m3_imports import (
    AccountType,
    Balance,
    Client,
    ClientVendorMappings,
    ClientVendorSchwab,
    CostBasisImpact,
    CostBasisMethod,
    Holding,
    Household,
    HouseholdAccount,
    HouseholdMember,
    HouseholdVendorMappings,
    HouseholdVendorSchwab,
    SecurityIdentifier,
    TaxLot,
    Transaction,
    TransactionType,
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
# Mapping tables — Schwab field values → canonical enums
# ---------------------------------------------------------------------------

_SCHWAB_ACCOUNT_TYPE_MAP: dict[str, AccountType] = {
    "Individual": AccountType.TAXABLE,
    "Joint WROS": AccountType.TAXABLE,
    "Joint TIC": AccountType.TAXABLE,
    "Traditional IRA": AccountType.TRADITIONAL_IRA,
    "Roth IRA": AccountType.ROTH_IRA,
    "Rollover IRA": AccountType.TRADITIONAL_IRA,
    "SEP IRA": AccountType.SEP_IRA,
    "SIMPLE IRA": AccountType.SIMPLE_IRA,
    "401(k)": AccountType.K401,
    "403(b)": AccountType.B403,
    "457(b)": AccountType.B457,
    "Trust": AccountType.TRUST_REVOCABLE,
    "Irrevocable Trust": AccountType.TRUST_IRREVOCABLE,
    "UTMA": AccountType.CUSTODIAL_UTMA,
    "UGMA": AccountType.CUSTODIAL_UGMA,
    "Pension": AccountType.ERISA_PENSION,
    "Profit Sharing": AccountType.ERISA_PROFIT_SHARING,
    "529": AccountType.PLAN_529,
    "HSA": AccountType.HSA,
}

_SCHWAB_TRANSACTION_TYPE_MAP: dict[str, TransactionType] = {
    "Buy": TransactionType.BUY,
    "Sell": TransactionType.SELL,
    "Short Sale": TransactionType.SELL_SHORT,
    "Buy to Cover": TransactionType.BUY_TO_COVER,
    "Qualified Dividend": TransactionType.DIVIDEND,
    "Cash Dividend": TransactionType.DIVIDEND,
    "Dividend": TransactionType.DIVIDEND,
    "Interest": TransactionType.INTEREST,
    "Bond Interest": TransactionType.INTEREST,
    "Misc Fee": TransactionType.FEE,
    "Advisory Fee": TransactionType.MANAGEMENT_FEE,
    "Transfer In": TransactionType.TRANSFER_IN,
    "Transfer Out": TransactionType.TRANSFER_OUT,
    "MoneyLink Transfer": TransactionType.TRANSFER_IN,
    "Distribution": TransactionType.DISTRIBUTION,
    "Contribution": TransactionType.CONTRIBUTION,
    "Wire Sent": TransactionType.WIRE_OUT,
    "Wire Received": TransactionType.WIRE_IN,
    "Wire Funds": TransactionType.WIRE_OUT,
    "Journal": TransactionType.JOURNAL,
    "Reinvest Dividend": TransactionType.REINVESTMENT,
    "Reinvest Shares": TransactionType.REINVESTMENT,
    "Return of Capital": TransactionType.RETURN_OF_CAPITAL,
    "Spin Off": TransactionType.CORPORATE_ACTION,
    "Stock Split": TransactionType.CORPORATE_ACTION,
    "Merger": TransactionType.CORPORATE_ACTION,
    "Margin Interest": TransactionType.MARGIN_INTEREST,
}

_SCHWAB_COST_BASIS_MAP: dict[str, CostBasisMethod] = {
    "SpecID": CostBasisMethod.SPECIFIC_LOT,
    "Specific Identification": CostBasisMethod.SPECIFIC_LOT,
    "FIFO": CostBasisMethod.FIFO,
    "LIFO": CostBasisMethod.LIFO,
    "HIFO": CostBasisMethod.HIFO,
    "Average Cost": CostBasisMethod.AVERAGE_COST,
    "AvgCost": CostBasisMethod.AVERAGE_COST,
}

_SCHWAB_SECURITY_TYPE_MAP: dict[str, str] = {
    "Equity": "equity", "Common Stock": "equity", "Preferred Stock": "equity",
    "Fixed Income": "fixed_income", "Corporate Bond": "fixed_income",
    "Municipal Bond": "fixed_income", "Treasury": "fixed_income",
    "Mutual Fund": "mutual_fund", "ETF": "etf", "Option": "option",
    "Cash Equivalent": "cash", "Money Market": "cash",
}

# Reverse maps
_CANONICAL_ACCOUNT_TYPE_TO_SCHWAB = {v.value: k for k, v in _SCHWAB_ACCOUNT_TYPE_MAP.items()}
_CANONICAL_TX_TYPE_TO_SCHWAB = {v.value: k for k, v in _SCHWAB_TRANSACTION_TYPE_MAP.items()}
_CANONICAL_COST_BASIS_TO_SCHWAB = {v.value: k for k, v in _SCHWAB_COST_BASIS_MAP.items()}


# ---------------------------------------------------------------------------
# Schwab Translator
# ---------------------------------------------------------------------------

class SchwabTranslator(MultiTypeTranslator):
    """Translates Charles Schwab Advisor Services data to/from canonical types.

    Supports dual source systems:
      - "schwab" for real-time REST API data
      - "schwab_sftp" for daily SFTP file data

    CRITICAL: cost_basis_method defaults to specific_lot for Schwab (Rule 7).
    This is Schwab's default method. NEVER null after translation.
    """

    def __init__(self, *, is_sftp: bool = False):
        self._is_sftp = is_sftp

    @property
    def source_system(self) -> str:
        return "schwab_sftp" if self._is_sftp else "schwab"

    # -----------------------------------------------------------------------
    # Client
    # -----------------------------------------------------------------------

    def client_to_canonical(self, schwab_data: dict[str, Any]) -> Client:
        """Convert Schwab Account holder to canonical Client."""
        holder_id = str(self._require_field(schwab_data, "accountHolderId", "Schwab accountHolderId"))
        canonical_id = parse_uuid(schwab_data.get("canonical_id")) or uuid4()

        first_name = schwab_data.get("firstName")
        last_name = schwab_data.get("lastName")
        display_name = schwab_data.get("displayName", "")
        if not display_name and first_name and last_name:
            display_name = f"{first_name} {last_name}"

        entity_type = schwab_data.get("accountType", "Individual")
        if "trust" in entity_type.lower():
            client_type = "trust"
        elif entity_type.lower() in {"individual", "joint wros", "joint tic"}:
            client_type = "individual"
        else:
            client_type = "entity"

        return Client(
            canonical_id=canonical_id,
            display_name=display_name or "Unknown",
            client_type=client_type,
            first_name=first_name,
            last_name=last_name,
            email=schwab_data.get("email"),
            phone=schwab_data.get("phone"),
            date_of_birth=parse_date(schwab_data.get("dateOfBirth")),
            ssn_last_four=schwab_data.get("ssnLastFour"),
            tax_id=schwab_data.get("taxId"),
            risk_tolerance=schwab_data.get("riskTolerance"),
            investment_objectives=schwab_data.get("investmentObjectives", []),
            time_horizon=schwab_data.get("timeHorizon"),
            annual_income_range=schwab_data.get("annualIncomeRange"),
            net_worth_range=schwab_data.get("netWorthRange"),
            liquid_net_worth_range=schwab_data.get("liquidNetWorthRange"),
            tax_bracket=schwab_data.get("taxBracket"),
            advisor_ref=parse_uuid(schwab_data.get("advisorRef")),
            firm_id=parse_uuid(schwab_data.get("firmId")) or uuid4(),
            household_ref=parse_uuid(schwab_data.get("householdRef")),
            archetype=schwab_data.get("archetype"),
            jurisdiction=schwab_data.get("jurisdiction", "US"),
            accounts=[UUID(a) for a in schwab_data.get("accountIds", []) if parse_uuid(a)],
            kyc_status=schwab_data.get("kycStatus"),
            kyc_verified_date=parse_date(schwab_data.get("kycVerifiedDate")),
            pii_classification=schwab_data.get("piiClassification", "confidential"),
            vendor_mappings=ClientVendorMappings(
                schwab=ClientVendorSchwab(account_holder_id=holder_id),
            ),
            reconciliation=None,
            source_system=self.source_system,
            source_id=holder_id,
            created_at=parse_datetime(schwab_data.get("createdDate")) or utcnow(),
            updated_at=parse_datetime(schwab_data.get("lastModifiedDate")) or utcnow(),
        )

    def client_from_canonical(self, client: Client) -> dict[str, Any]:
        schwab_mapping = client.vendor_mappings.schwab if client.vendor_mappings else None
        result: dict[str, Any] = {
            "displayName": client.display_name,
            "firstName": client.first_name,
            "lastName": client.last_name,
            "email": client.email,
            "phone": client.phone,
        }
        if schwab_mapping:
            result["accountHolderId"] = schwab_mapping.account_holder_id
        if client.date_of_birth:
            result["dateOfBirth"] = client.date_of_birth.isoformat()
        return result

    # -----------------------------------------------------------------------
    # Holding
    # -----------------------------------------------------------------------

    def holding_to_canonical(self, schwab_data: dict[str, Any]) -> Holding:
        """Schwab excludes accrued interest from market value."""
        position_id = str(self._require_field(schwab_data, "positionId", "Schwab positionId"))
        canonical_id = parse_uuid(schwab_data.get("canonical_id")) or uuid4()

        ticker = schwab_data.get("ticker") or schwab_data.get("symbol")
        cusip = schwab_data.get("cusip")
        security_identifier = (
            SecurityIdentifier(ticker=ticker, cusip=cusip, isin=schwab_data.get("isin"),
                               figi=schwab_data.get("figi"), sedol=schwab_data.get("sedol"))
            if any([ticker, cusip]) else None
        )
        security_type = _SCHWAB_SECURITY_TYPE_MAP.get(schwab_data.get("assetType", ""), "other")
        account_type_raw = schwab_data.get("accountType")
        account_type = _SCHWAB_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        return Holding(
            canonical_id=canonical_id,
            account_ref=str(schwab_data.get("accountNumber", "")),
            client_ref=schwab_data.get("clientRef"),
            security_identifier=security_identifier,
            security_name=schwab_data.get("description") or schwab_data.get("securityName"),
            security_type=security_type,
            quantity=float(schwab_data.get("quantity", 0)),
            market_value=float(schwab_data.get("marketValue", 0)),
            market_value_includes_accrued=False,
            cost_basis=safe_float(schwab_data.get("costBasis")),
            unrealized_gain_loss=safe_float(schwab_data.get("unrealizedGainLoss")),
            unrealized_gain_loss_pct=safe_float(schwab_data.get("unrealizedGainLossPct")),
            weight_in_account=safe_float(schwab_data.get("percentOfAccount")),
            currency=schwab_data.get("currency", "USD"),
            as_of_date=parse_date(schwab_data.get("asOfDate")) or date.today(),
            account_type=account_type,
            source_system=self.source_system,
            source_id=position_id,
            tax_lots=[],
        )

    def holding_from_canonical(self, holding: Holding) -> dict[str, Any]:
        result: dict[str, Any] = {
            "quantity": holding.quantity, "marketValue": holding.market_value,
            "description": holding.security_name, "asOfDate": holding.as_of_date.isoformat(),
        }
        if holding.security_identifier:
            result["ticker"] = holding.security_identifier.ticker
            result["cusip"] = holding.security_identifier.cusip
        if holding.cost_basis is not None:
            result["costBasis"] = holding.cost_basis
        return result

    # -----------------------------------------------------------------------
    # TaxLot — CRITICAL: cost_basis_method NEVER null (Rule 7)
    # -----------------------------------------------------------------------

    def tax_lot_to_canonical(self, schwab_data: dict[str, Any]) -> TaxLot:
        """Convert Schwab TaxLot to canonical TaxLot.

        RULE 7: cost_basis_method is REQUIRED and NEVER null.
        Schwab default = specific_lot.
        Wrong cost basis method = wrong tax reporting = regulatory violation.
        """
        lot_id = parse_uuid(schwab_data.get("lotId")) or uuid4()

        # CRITICAL: cost_basis_method — NEVER null (Rule 7)
        schwab_method = schwab_data.get("costBasisMethod") or schwab_data.get("taxLotMethod")
        cost_basis_method = (
            _SCHWAB_COST_BASIS_MAP.get(schwab_method, CostBasisMethod.SPECIFIC_LOT)
            if schwab_method
            else CostBasisMethod.SPECIFIC_LOT  # Schwab default
        )

        acquisition_date_raw = schwab_data.get("acquiredDate") or schwab_data.get("openDate")
        acquisition_date = parse_date(acquisition_date_raw) or date.today()
        quantity = float(schwab_data.get("quantity", 0) or schwab_data.get("shares", 0))
        cost_basis_amount = float(schwab_data.get("costBasis", 0) or schwab_data.get("totalCost", 0))

        days_held = (date.today() - acquisition_date).days if acquisition_date else 0
        holding_period = "long_term" if days_held > 365 else "short_term"

        return TaxLot(
            lot_id=lot_id,
            holding_ref=str(schwab_data.get("positionId", schwab_data.get("holdingRef", ""))),
            security_ref=schwab_data.get("securityRef"),
            acquisition_date=acquisition_date,
            acquisition_price=safe_float(schwab_data.get("acquiredPrice") or schwab_data.get("unitCost")),
            quantity=quantity,
            cost_basis_method=cost_basis_method,  # NEVER null — Rule 7
            cost_basis_amount=cost_basis_amount,
            holding_period=holding_period,
            unrealized_gain_loss=safe_float(schwab_data.get("unrealizedGainLoss")),
            wash_sale_disallowed=safe_float(schwab_data.get("washSaleDisallowed")),
            source_custodian="schwab",
            source_cost_basis_method=schwab_method,
        )

    def tax_lot_from_canonical(self, tax_lot: TaxLot) -> dict[str, Any]:
        result: dict[str, Any] = {
            "lotId": str(tax_lot.lot_id),
            "quantity": tax_lot.quantity,
            "costBasis": tax_lot.cost_basis_amount,
            "acquiredDate": tax_lot.acquisition_date.isoformat(),
            "costBasisMethod": _CANONICAL_COST_BASIS_TO_SCHWAB.get(
                tax_lot.cost_basis_method.value if isinstance(tax_lot.cost_basis_method, CostBasisMethod) else tax_lot.cost_basis_method,
                "SpecID",
            ),
        }
        if tax_lot.acquisition_price is not None:
            result["acquiredPrice"] = tax_lot.acquisition_price
        if tax_lot.unrealized_gain_loss is not None:
            result["unrealizedGainLoss"] = tax_lot.unrealized_gain_loss
        return result

    # -----------------------------------------------------------------------
    # Transaction
    # -----------------------------------------------------------------------

    def transaction_to_canonical(self, schwab_data: dict[str, Any]) -> Transaction:
        tx_id = str(self._require_field(schwab_data, "transactionId", "Schwab transactionId"))
        schwab_type = schwab_data.get("type", "") or schwab_data.get("transactionType", "")
        tx_type = _SCHWAB_TRANSACTION_TYPE_MAP.get(schwab_type, TransactionType.JOURNAL)
        account_type_raw = schwab_data.get("accountType")
        account_type = _SCHWAB_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        cost_basis_impact = None
        if schwab_data.get("realizedGainLoss") is not None:
            cost_basis_impact = CostBasisImpact(
                realized_gain_loss=safe_float(schwab_data.get("realizedGainLoss")),
                holding_period=schwab_data.get("holdingPeriod"),
                wash_sale_disallowed=safe_float(schwab_data.get("washSaleDisallowed")),
            )

        ticker = schwab_data.get("ticker") or schwab_data.get("symbol")
        cusip = schwab_data.get("cusip")
        security_identifier = SecurityIdentifier(ticker=ticker, cusip=cusip) if any([ticker, cusip]) else None

        return Transaction(
            transaction_id=parse_uuid(schwab_data.get("canonical_id")) or uuid4(),
            account_ref=parse_uuid(schwab_data.get("accountNumber")) or uuid4(),
            client_ref=parse_uuid(schwab_data.get("clientRef")),
            order_ref=None,
            transaction_type=tx_type,
            security_identifier=security_identifier,
            security_name=schwab_data.get("description"),
            quantity=safe_float(schwab_data.get("quantity") or schwab_data.get("shares")),
            price=safe_float(schwab_data.get("price")),
            amount=float(schwab_data.get("amount", 0) or schwab_data.get("netAmount", 0)),
            commission=safe_float(schwab_data.get("commission")),
            fees=safe_float(schwab_data.get("fees")),
            net_amount=safe_float(schwab_data.get("netAmount")),
            trade_date=parse_date(schwab_data.get("tradeDate")) or date.today(),
            settlement_date=parse_date(schwab_data.get("settlementDate")),
            settlement_status=schwab_data.get("settlementStatus", "settled"),
            currency=schwab_data.get("currency", "USD"),
            description=schwab_data.get("description"),
            tax_lot_ref=schwab_data.get("taxLotId"),
            cost_basis_impact=cost_basis_impact,
            account_type=account_type,
            source_system=self.source_system,
            source_id=tx_id,
            source_transaction_type=schwab_type,
            trace_id=schwab_data.get("traceId"),
            created_at=parse_datetime(schwab_data.get("createdDate")) or utcnow(),
        )

    def transaction_from_canonical(self, tx: Transaction) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": _CANONICAL_TX_TYPE_TO_SCHWAB.get(
                tx.transaction_type.value if isinstance(tx.transaction_type, TransactionType) else tx.transaction_type, "Journal"),
            "amount": tx.amount, "tradeDate": tx.trade_date.isoformat(), "description": tx.description,
        }
        if tx.security_identifier:
            result["ticker"] = tx.security_identifier.ticker
            result["cusip"] = tx.security_identifier.cusip
        if tx.quantity is not None:
            result["quantity"] = tx.quantity
        if tx.price is not None:
            result["price"] = tx.price
        if tx.settlement_date:
            result["settlementDate"] = tx.settlement_date.isoformat()
        return result

    # -----------------------------------------------------------------------
    # Balance
    # -----------------------------------------------------------------------

    def balance_to_canonical(self, schwab_data: dict[str, Any]) -> Balance:
        """is_real_time: True for API, False for SFTP."""
        balance_id = parse_uuid(schwab_data.get("balanceId")) or uuid4()
        account_type_raw = schwab_data.get("accountType")
        account_type = _SCHWAB_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        return Balance(
            balance_id=balance_id,
            account_ref=parse_uuid(schwab_data.get("accountNumber")) or uuid4(),
            client_ref=parse_uuid(schwab_data.get("clientRef")),
            total_value=float(schwab_data.get("totalValue", 0) or schwab_data.get("accountValue", 0)),
            cash_balance=safe_float(schwab_data.get("cashBalance") or schwab_data.get("settledCash")),
            cash_unsettled=safe_float(schwab_data.get("unsettledCash")),
            money_market_balance=safe_float(schwab_data.get("moneyMarketBalance")),
            long_market_value=safe_float(schwab_data.get("longMarketValue")),
            short_market_value=safe_float(schwab_data.get("shortMarketValue")),
            margin_balance=safe_float(schwab_data.get("marginBalance")),
            margin_equity=safe_float(schwab_data.get("marginEquity")),
            buying_power=safe_float(schwab_data.get("buyingPower")),
            accrued_interest=safe_float(schwab_data.get("accruedInterest")),
            pending_activity=safe_float(schwab_data.get("pendingActivity")),
            account_type=account_type,
            currency=schwab_data.get("currency", "USD"),
            as_of_date=parse_date(schwab_data.get("asOfDate")) or date.today(),
            as_of_time=parse_datetime(schwab_data.get("asOfTime")),
            is_real_time=not self._is_sftp,
            source_system=self.source_system,
            source_id=str(schwab_data.get("accountNumber", "")),
            source_balance_components=schwab_data.get("balanceComponents"),
        )

    def balance_from_canonical(self, balance: Balance) -> dict[str, Any]:
        result: dict[str, Any] = {"totalValue": balance.total_value, "asOfDate": balance.as_of_date.isoformat()}
        if balance.cash_balance is not None:
            result["cashBalance"] = balance.cash_balance
        if balance.long_market_value is not None:
            result["longMarketValue"] = balance.long_market_value
        if balance.buying_power is not None:
            result["buyingPower"] = balance.buying_power
        return result

    # -----------------------------------------------------------------------
    # Household (custodial grouping via master_account)
    # -----------------------------------------------------------------------

    def household_to_canonical(self, schwab_data: dict[str, Any]) -> Household:
        """Schwab uses custodial grouping via master_account (Rule 6)."""
        master_account = str(self._require_field(schwab_data, "masterAccount", "Schwab masterAccount"))
        canonical_id = parse_uuid(schwab_data.get("canonical_id")) or uuid4()

        members = [
            HouseholdMember(client_ref=str(m.get("accountHolderId", "")),
                            role=m.get("role", "primary").lower(), source=self.source_system)
            for m in schwab_data.get("members", [])
        ]
        accounts = [
            HouseholdAccount(account_ref=str(a.get("accountNumber", "")), source=self.source_system)
            for a in schwab_data.get("accounts", [])
        ]

        return Household(
            canonical_id=canonical_id,
            display_name=schwab_data.get("displayName", f"Schwab HH {master_account}"),
            primary_source=self.source_system,
            members=members, accounts=accounts,
            vendor_mappings=HouseholdVendorMappings(
                schwab=HouseholdVendorSchwab(master_account=master_account, grouping_type="custodial"),
            ),
            reconciliation=None,
        )

    def household_from_canonical(self, household: Household) -> dict[str, Any]:
        schwab_mapping = household.vendor_mappings.schwab if household.vendor_mappings else None
        result: dict[str, Any] = {"displayName": household.display_name}
        if schwab_mapping:
            result["masterAccount"] = schwab_mapping.master_account
        result["members"] = [{"accountHolderId": m.client_ref, "role": m.role}
                             for m in household.members if m.source == self.source_system or schwab_mapping]
        result["accounts"] = [{"accountNumber": a.account_ref}
                              for a in household.accounts if a.source == self.source_system or schwab_mapping]
        return result
