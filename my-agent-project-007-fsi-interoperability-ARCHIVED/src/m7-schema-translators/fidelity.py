"""
M7 Schema Translator — Fidelity Institutional

Maps Fidelity objects to canonical types:
  - Fidelity Customer → Client (with ClientVendorFidelity mapping)
  - Fidelity Position → Holding
  - Fidelity TaxLot → TaxLot — CRITICAL: cost_basis_method defaults differ by
    asset class: average_cost for mutual funds, specific_lot for equities (Rule 7)
  - Fidelity Balance → Balance (is_real_time for API vs SFTP)
  - Fidelity Activity → Transaction

Key issues handled:
  - cost_basis_method defaults vary by asset class (Rule 7 — NEVER null):
      * Mutual funds → average_cost (Fidelity default)
      * Equities/ETFs/other → specific_lot
  - Dual source: real-time API ("fidelity") vs daily SFTP files ("fidelity_sftp")
  - is_real_time flag on Balance distinguishes API vs file source
  - vendor_mappings preserved on all types (Rule 12)

Source system: "fidelity" (API) or "fidelity_sftp" (daily files)
Python 3.12+ / Pydantic v2.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID, uuid4

from m7_schema_translators._m3_imports import (
    AccountType,
    Balance,
    Client,
    ClientVendorFidelity,
    ClientVendorMappings,
    CostBasisImpact,
    CostBasisMethod,
    Holding,
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
# Mapping tables — Fidelity field values → canonical enums
# ---------------------------------------------------------------------------

_FIDELITY_ACCOUNT_TYPE_MAP: dict[str, AccountType] = {
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

_FIDELITY_TRANSACTION_TYPE_MAP: dict[str, TransactionType] = {
    "Buy": TransactionType.BUY,
    "Sell": TransactionType.SELL,
    "Short Sale": TransactionType.SELL_SHORT,
    "Buy to Cover": TransactionType.BUY_TO_COVER,
    "Dividend": TransactionType.DIVIDEND,
    "Qualified Dividend": TransactionType.DIVIDEND,
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
    "Reinvest Dividend": TransactionType.REINVESTMENT,
    "Return of Capital": TransactionType.RETURN_OF_CAPITAL,
    "Corporate Action": TransactionType.CORPORATE_ACTION,
    "Margin Interest": TransactionType.MARGIN_INTEREST,
}

_FIDELITY_COST_BASIS_MAP: dict[str, CostBasisMethod] = {
    "SpecID": CostBasisMethod.SPECIFIC_LOT,
    "Specific Identification": CostBasisMethod.SPECIFIC_LOT,
    "FIFO": CostBasisMethod.FIFO,
    "LIFO": CostBasisMethod.LIFO,
    "HIFO": CostBasisMethod.HIFO,
    "Average Cost": CostBasisMethod.AVERAGE_COST,
    "AvgCost": CostBasisMethod.AVERAGE_COST,
}

_FIDELITY_SECURITY_TYPE_MAP: dict[str, str] = {
    "Equity": "equity", "Common Stock": "equity", "Preferred Stock": "equity",
    "Fixed Income": "fixed_income", "Corporate Bond": "fixed_income",
    "Municipal Bond": "fixed_income", "Treasury": "fixed_income",
    "Mutual Fund": "mutual_fund", "ETF": "etf", "Option": "option",
    "Cash Equivalent": "cash", "Money Market": "cash",
}

# Asset types that default to average_cost at Fidelity (Rule 7)
_FIDELITY_AVERAGE_COST_ASSET_TYPES: set[str] = {
    "Mutual Fund", "mutual_fund",
}

# Reverse maps
_CANONICAL_ACCOUNT_TYPE_TO_FIDELITY = {v.value: k for k, v in _FIDELITY_ACCOUNT_TYPE_MAP.items()}
_CANONICAL_TX_TYPE_TO_FIDELITY = {v.value: k for k, v in _FIDELITY_TRANSACTION_TYPE_MAP.items()}
_CANONICAL_COST_BASIS_TO_FIDELITY = {v.value: k for k, v in _FIDELITY_COST_BASIS_MAP.items()}


def _fidelity_default_cost_basis(asset_type: str | None) -> CostBasisMethod:
    """Determine Fidelity's default cost basis method by asset class.

    RULE 7 — CRITICAL:
      - Mutual funds → average_cost (Fidelity default for pooled vehicles)
      - Equities/ETFs/other → specific_lot
    Wrong cost basis method = wrong tax reporting = regulatory violation.
    """
    if asset_type and asset_type in _FIDELITY_AVERAGE_COST_ASSET_TYPES:
        return CostBasisMethod.AVERAGE_COST
    return CostBasisMethod.SPECIFIC_LOT


# ---------------------------------------------------------------------------
# Fidelity Translator
# ---------------------------------------------------------------------------

class FidelityTranslator(MultiTypeTranslator):
    """Translates Fidelity Institutional data to/from canonical types.

    Supports dual source systems:
      - "fidelity" for real-time API data
      - "fidelity_sftp" for daily SFTP file data

    CRITICAL: cost_basis_method defaults differ by asset class (Rule 7):
      - Mutual funds → average_cost
      - Equities/ETFs/other → specific_lot
    NEVER null after translation.
    """

    def __init__(self, *, is_sftp: bool = False):
        self._is_sftp = is_sftp

    @property
    def source_system(self) -> str:
        return "fidelity_sftp" if self._is_sftp else "fidelity"

    # -----------------------------------------------------------------------
    # Client
    # -----------------------------------------------------------------------

    def client_to_canonical(self, fidelity_data: dict[str, Any]) -> Client:
        """Convert Fidelity Customer to canonical Client."""
        customer_id = str(self._require_field(fidelity_data, "customerId", "Fidelity customerId"))
        canonical_id = parse_uuid(fidelity_data.get("canonical_id")) or uuid4()

        first_name = fidelity_data.get("firstName")
        last_name = fidelity_data.get("lastName")
        display_name = fidelity_data.get("displayName", "")
        if not display_name and first_name and last_name:
            display_name = f"{first_name} {last_name}"

        entity_type = fidelity_data.get("accountType", "Individual")
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
            email=fidelity_data.get("email"),
            phone=fidelity_data.get("phone"),
            date_of_birth=parse_date(fidelity_data.get("dateOfBirth")),
            ssn_last_four=fidelity_data.get("ssnLastFour"),
            tax_id=fidelity_data.get("taxId"),
            risk_tolerance=fidelity_data.get("riskTolerance"),
            investment_objectives=fidelity_data.get("investmentObjectives", []),
            time_horizon=fidelity_data.get("timeHorizon"),
            annual_income_range=fidelity_data.get("annualIncomeRange"),
            net_worth_range=fidelity_data.get("netWorthRange"),
            liquid_net_worth_range=fidelity_data.get("liquidNetWorthRange"),
            tax_bracket=fidelity_data.get("taxBracket"),
            advisor_ref=parse_uuid(fidelity_data.get("advisorRef")),
            firm_id=parse_uuid(fidelity_data.get("firmId")) or uuid4(),
            household_ref=parse_uuid(fidelity_data.get("householdRef")),
            archetype=fidelity_data.get("archetype"),
            jurisdiction=fidelity_data.get("jurisdiction", "US"),
            accounts=[UUID(a) for a in fidelity_data.get("accountIds", []) if parse_uuid(a)],
            kyc_status=fidelity_data.get("kycStatus"),
            kyc_verified_date=parse_date(fidelity_data.get("kycVerifiedDate")),
            pii_classification=fidelity_data.get("piiClassification", "confidential"),
            vendor_mappings=ClientVendorMappings(
                fidelity=ClientVendorFidelity(customer_id=customer_id),
            ),
            reconciliation=None,
            source_system=self.source_system,
            source_id=customer_id,
            created_at=parse_datetime(fidelity_data.get("createdDate")) or utcnow(),
            updated_at=parse_datetime(fidelity_data.get("lastModifiedDate")) or utcnow(),
        )

    def client_from_canonical(self, client: Client) -> dict[str, Any]:
        fidelity_mapping = client.vendor_mappings.fidelity if client.vendor_mappings else None
        result: dict[str, Any] = {
            "displayName": client.display_name,
            "firstName": client.first_name,
            "lastName": client.last_name,
            "email": client.email,
            "phone": client.phone,
        }
        if fidelity_mapping:
            result["customerId"] = fidelity_mapping.customer_id
        if client.date_of_birth:
            result["dateOfBirth"] = client.date_of_birth.isoformat()
        return result

    # -----------------------------------------------------------------------
    # Holding
    # -----------------------------------------------------------------------

    def holding_to_canonical(self, fidelity_data: dict[str, Any]) -> Holding:
        """Fidelity excludes accrued interest from market value for equities."""
        position_id = str(self._require_field(fidelity_data, "positionId", "Fidelity positionId"))
        canonical_id = parse_uuid(fidelity_data.get("canonical_id")) or uuid4()

        ticker = fidelity_data.get("ticker") or fidelity_data.get("symbol")
        cusip = fidelity_data.get("cusip")
        security_identifier = (
            SecurityIdentifier(ticker=ticker, cusip=cusip, isin=fidelity_data.get("isin"),
                               figi=fidelity_data.get("figi"), sedol=fidelity_data.get("sedol"))
            if any([ticker, cusip]) else None
        )
        asset_type = fidelity_data.get("assetType", "")
        security_type = _FIDELITY_SECURITY_TYPE_MAP.get(asset_type, "other")
        account_type_raw = fidelity_data.get("accountType")
        account_type = _FIDELITY_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        return Holding(
            canonical_id=canonical_id,
            account_ref=str(fidelity_data.get("accountNumber", "")),
            client_ref=fidelity_data.get("clientRef"),
            security_identifier=security_identifier,
            security_name=fidelity_data.get("description") or fidelity_data.get("securityName"),
            security_type=security_type,
            quantity=float(fidelity_data.get("quantity", 0)),
            market_value=float(fidelity_data.get("marketValue", 0)),
            market_value_includes_accrued=False,
            cost_basis=safe_float(fidelity_data.get("costBasis")),
            unrealized_gain_loss=safe_float(fidelity_data.get("unrealizedGainLoss")),
            unrealized_gain_loss_pct=safe_float(fidelity_data.get("unrealizedGainLossPct")),
            weight_in_account=safe_float(fidelity_data.get("percentOfAccount")),
            currency=fidelity_data.get("currency", "USD"),
            as_of_date=parse_date(fidelity_data.get("asOfDate")) or date.today(),
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
    # Fidelity defaults: average_cost for mutual funds, specific_lot for equities
    # -----------------------------------------------------------------------

    def tax_lot_to_canonical(self, fidelity_data: dict[str, Any]) -> TaxLot:
        """Convert Fidelity TaxLot to canonical TaxLot.

        RULE 7: cost_basis_method is REQUIRED and NEVER null.
        Fidelity defaults:
          - Mutual funds → average_cost
          - Equities/ETFs/other → specific_lot
        Wrong cost basis method = wrong tax reporting = regulatory violation.
        """
        lot_id = parse_uuid(fidelity_data.get("lotId")) or uuid4()

        # CRITICAL: cost_basis_method — NEVER null (Rule 7)
        fidelity_method = fidelity_data.get("costBasisMethod") or fidelity_data.get("taxLotMethod")
        asset_type = fidelity_data.get("assetType") or fidelity_data.get("securityType")
        if fidelity_method:
            cost_basis_method = _FIDELITY_COST_BASIS_MAP.get(
                fidelity_method, _fidelity_default_cost_basis(asset_type)
            )
        else:
            # No method specified — use Fidelity's asset-class-based default
            cost_basis_method = _fidelity_default_cost_basis(asset_type)

        acquisition_date_raw = fidelity_data.get("acquiredDate") or fidelity_data.get("openDate")
        acquisition_date = parse_date(acquisition_date_raw) or date.today()
        quantity = float(fidelity_data.get("quantity", 0) or fidelity_data.get("shares", 0))
        cost_basis_amount = float(fidelity_data.get("costBasis", 0) or fidelity_data.get("totalCost", 0))

        days_held = (date.today() - acquisition_date).days if acquisition_date else 0
        holding_period = "long_term" if days_held > 365 else "short_term"

        return TaxLot(
            lot_id=lot_id,
            holding_ref=str(fidelity_data.get("positionId", fidelity_data.get("holdingRef", ""))),
            security_ref=fidelity_data.get("securityRef"),
            acquisition_date=acquisition_date,
            acquisition_price=safe_float(fidelity_data.get("acquiredPrice") or fidelity_data.get("unitCost")),
            quantity=quantity,
            cost_basis_method=cost_basis_method,  # NEVER null — Rule 7
            cost_basis_amount=cost_basis_amount,
            holding_period=holding_period,
            unrealized_gain_loss=safe_float(fidelity_data.get("unrealizedGainLoss")),
            wash_sale_disallowed=safe_float(fidelity_data.get("washSaleDisallowed")),
            source_custodian="fidelity",
            source_cost_basis_method=fidelity_method,
        )

    def tax_lot_from_canonical(self, tax_lot: TaxLot) -> dict[str, Any]:
        result: dict[str, Any] = {
            "lotId": str(tax_lot.lot_id),
            "quantity": tax_lot.quantity,
            "costBasis": tax_lot.cost_basis_amount,
            "acquiredDate": tax_lot.acquisition_date.isoformat(),
            "costBasisMethod": _CANONICAL_COST_BASIS_TO_FIDELITY.get(
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
    # Balance
    # -----------------------------------------------------------------------

    def balance_to_canonical(self, fidelity_data: dict[str, Any]) -> Balance:
        """is_real_time: True for API, False for SFTP."""
        balance_id = parse_uuid(fidelity_data.get("balanceId")) or uuid4()
        account_type_raw = fidelity_data.get("accountType")
        account_type = _FIDELITY_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        return Balance(
            balance_id=balance_id,
            account_ref=parse_uuid(fidelity_data.get("accountNumber")) or uuid4(),
            client_ref=parse_uuid(fidelity_data.get("clientRef")),
            total_value=float(fidelity_data.get("totalValue", 0) or fidelity_data.get("accountValue", 0)),
            cash_balance=safe_float(fidelity_data.get("cashBalance") or fidelity_data.get("settledCash")),
            cash_unsettled=safe_float(fidelity_data.get("unsettledCash")),
            money_market_balance=safe_float(fidelity_data.get("moneyMarketBalance")),
            long_market_value=safe_float(fidelity_data.get("longMarketValue")),
            short_market_value=safe_float(fidelity_data.get("shortMarketValue")),
            margin_balance=safe_float(fidelity_data.get("marginBalance")),
            margin_equity=safe_float(fidelity_data.get("marginEquity")),
            buying_power=safe_float(fidelity_data.get("buyingPower")),
            accrued_interest=safe_float(fidelity_data.get("accruedInterest")),
            pending_activity=safe_float(fidelity_data.get("pendingActivity")),
            account_type=account_type,
            currency=fidelity_data.get("currency", "USD"),
            as_of_date=parse_date(fidelity_data.get("asOfDate")) or date.today(),
            as_of_time=parse_datetime(fidelity_data.get("asOfTime")),
            is_real_time=not self._is_sftp,
            source_system=self.source_system,
            source_id=str(fidelity_data.get("accountNumber", "")),
            source_balance_components=fidelity_data.get("balanceComponents"),
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
    # Transaction
    # -----------------------------------------------------------------------

    def transaction_to_canonical(self, fidelity_data: dict[str, Any]) -> Transaction:
        tx_id = str(self._require_field(fidelity_data, "transactionId", "Fidelity transactionId"))
        fidelity_type = fidelity_data.get("type", "") or fidelity_data.get("transactionType", "")
        tx_type = _FIDELITY_TRANSACTION_TYPE_MAP.get(fidelity_type, TransactionType.JOURNAL)
        account_type_raw = fidelity_data.get("accountType")
        account_type = _FIDELITY_ACCOUNT_TYPE_MAP.get(account_type_raw) if account_type_raw else None

        cost_basis_impact = None
        if fidelity_data.get("realizedGainLoss") is not None:
            cost_basis_impact = CostBasisImpact(
                realized_gain_loss=safe_float(fidelity_data.get("realizedGainLoss")),
                holding_period=fidelity_data.get("holdingPeriod"),
                wash_sale_disallowed=safe_float(fidelity_data.get("washSaleDisallowed")),
            )

        ticker = fidelity_data.get("ticker") or fidelity_data.get("symbol")
        cusip = fidelity_data.get("cusip")
        security_identifier = SecurityIdentifier(ticker=ticker, cusip=cusip) if any([ticker, cusip]) else None

        return Transaction(
            transaction_id=parse_uuid(fidelity_data.get("canonical_id")) or uuid4(),
            account_ref=parse_uuid(fidelity_data.get("accountNumber")) or uuid4(),
            client_ref=parse_uuid(fidelity_data.get("clientRef")),
            order_ref=None,
            transaction_type=tx_type,
            security_identifier=security_identifier,
            security_name=fidelity_data.get("description"),
            quantity=safe_float(fidelity_data.get("quantity") or fidelity_data.get("shares")),
            price=safe_float(fidelity_data.get("price")),
            amount=float(fidelity_data.get("amount", 0) or fidelity_data.get("netAmount", 0)),
            commission=safe_float(fidelity_data.get("commission")),
            fees=safe_float(fidelity_data.get("fees")),
            net_amount=safe_float(fidelity_data.get("netAmount")),
            trade_date=parse_date(fidelity_data.get("tradeDate")) or date.today(),
            settlement_date=parse_date(fidelity_data.get("settlementDate")),
            settlement_status=fidelity_data.get("settlementStatus", "settled"),
            currency=fidelity_data.get("currency", "USD"),
            description=fidelity_data.get("description"),
            tax_lot_ref=fidelity_data.get("taxLotId"),
            cost_basis_impact=cost_basis_impact,
            account_type=account_type,
            source_system=self.source_system,
            source_id=tx_id,
            source_transaction_type=fidelity_type,
            trace_id=fidelity_data.get("traceId"),
            created_at=parse_datetime(fidelity_data.get("createdDate")) or utcnow(),
        )

    def transaction_from_canonical(self, tx: Transaction) -> dict[str, Any]:
        result: dict[str, Any] = {
            "type": _CANONICAL_TX_TYPE_TO_FIDELITY.get(
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
