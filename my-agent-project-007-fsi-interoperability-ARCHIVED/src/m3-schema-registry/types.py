"""
M3 Canonical Schema Registry — Pydantic v2 Models

All 18 canonical types for the 007 FSI Interoperability Platform.
Each model matches its corresponding JSON Schema in schemas/canonical/.
Python 3.10+ / Pydantic v2.

BLOCKER 1 resolution: M7 translators import these models.
BLOCKER 8 resolution: account_type enum unified across Balance, Order, Holding, Transaction.
"""

import enum
from datetime import date, datetime
from typing import Any, Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# ---------------------------------------------------------------------------
# Shared Enums
# ---------------------------------------------------------------------------

class AccountType(str, enum.Enum):
    """Canonical 16-value account type enum (ERISA + tax-advantaged).
    Unified per DECISION-LOG 2026-04-15 BLOCKER-8 resolution.
    Used by Balance, Order, Holding, Transaction."""
    TAXABLE = "taxable"
    TRADITIONAL_IRA = "traditional_ira"
    ROTH_IRA = "roth_ira"
    K401 = "401k"
    B403 = "403b"
    B457 = "457"
    SEP_IRA = "sep_ira"
    SIMPLE_IRA = "simple_ira"
    TRUST_REVOCABLE = "trust_revocable"
    TRUST_IRREVOCABLE = "trust_irrevocable"
    CUSTODIAL_UTMA = "custodial_utma"
    CUSTODIAL_UGMA = "custodial_ugma"
    ERISA_PENSION = "erisa_pension"
    ERISA_PROFIT_SHARING = "erisa_profit_sharing"
    PLAN_529 = "529"
    HSA = "hsa"


class SourceSystem(str, enum.Enum):
    """Common source systems across the platform."""
    SALESFORCE_FSC = "salesforce_fsc"
    ORION = "orion"
    SCHWAB = "schwab"
    SCHWAB_SFTP = "schwab_sftp"
    FIDELITY = "fidelity"
    FIDELITY_SFTP = "fidelity_sftp"
    PERSHING = "pershing"
    ENVESTNET = "envestnet"
    BLOOMBERG = "bloomberg"
    FACTSET = "factset"

    ALPHA_VANTAGE = "alpha_vantage"
    IEX = "iex"
    SEC_EDGAR = "sec_edgar"
    EMONEY = "emoney"
    MONEYGUIDEPRO = "moneyguidepro"
    RIGHTCAPITAL = "rightcapital"
    WEALTHBOX = "wealthbox"
    REDTAIL = "redtail"
    SWIFT_GATEWAY = "swift_gateway"
    AGENT_GENERATED = "agent_generated"
    MANUAL = "manual"


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------

class SecurityIdentifier(BaseModel):
    """Cross-reference: multiple identifiers for the same security."""
    ticker: Optional[str] = Field(default=None, description="Exchange ticker symbol")
    cusip: Optional[str] = Field(default=None, description="CUSIP identifier (9-char alphanumeric)")
    isin: Optional[str] = Field(default=None, description="ISIN identifier (2-letter country + 10 alphanum)")
    figi: Optional[str] = Field(default=None, description="FIGI identifier (12-char alphanumeric)")
    sedol: Optional[str] = Field(default=None, description="SEDOL identifier (7-char alphanumeric)")
    bloomberg_id: Optional[str] = Field(default=None, description="Bloomberg ticker format: 'NVDA US Equity'")


class Reconciliation(BaseModel):
    """Tracks cross-vendor agreement for types with multiple vendor sources."""
    sources_agree: bool = Field(description="True if all vendor sources agree on data")
    discrepancies: list[str] = Field(default_factory=list, description="List of disagreements between sources — flagged for SME review")
    last_reconciled: datetime = Field(description="When reconciliation last ran")


class PII:
    """Marker for x-pii fields. Used as Pydantic Field json_schema_extra."""
    MARKER: dict[str, bool] = {"x-pii": True}


class HitlApproval(BaseModel):
    """Human-in-the-loop approval record."""
    approver_id: str = Field(description="ID of the human approver")
    approved_at: datetime = Field(description="Timestamp of approval")
    approval_token: str = Field(description="SHA-256(entity_id + approver_id + timestamp) — tamper-proof")


# ---------------------------------------------------------------------------
# 1. Client
# ---------------------------------------------------------------------------

class ClientVendorSalesforceFSC(BaseModel):
    account_id: str = Field(description="SF Account Record ID")
    contact_id: Optional[str] = Field(default=None, description="SF Contact Record ID")
    person_account: bool = Field(default=False, description="True if SF Person Account model")

class ClientVendorOrion(BaseModel):
    client_id: str = Field(description="Orion Client ID")
    representative_id: Optional[str] = Field(default=None, description="Orion Representative (advisor) ID")

class ClientVendorSchwab(BaseModel):
    account_holder_id: str = Field(description="Schwab account holder ID")

class ClientVendorFidelity(BaseModel):
    customer_id: str = Field(description="Fidelity customer ID")

class ClientVendorMappings(BaseModel):
    salesforce_fsc: Optional[ClientVendorSalesforceFSC] = None
    orion: Optional[ClientVendorOrion] = None
    schwab: Optional[ClientVendorSchwab] = None
    fidelity: Optional[ClientVendorFidelity] = None

class Client(BaseModel):
    """Canonical FSI client profile. PII fields marked with x-pii for M4 MNPI filtering."""
    canonical_id: UUID = Field(description="Primary key for canonical client record")
    display_name: str = Field(min_length=1, max_length=255, description="Human-readable display name")
    client_type: str = Field(description="Legal classification: individual, entity, or trust")
    first_name: Optional[str] = Field(default=None, max_length=100, description="Given name (individual only)")
    last_name: Optional[str] = Field(default=None, max_length=100, description="Family name (individual only)")
    email: Optional[str] = Field(default=None, json_schema_extra=PII.MARKER, description="Client email. PII — M4 strips for non-authorized roles")
    phone: Optional[str] = Field(default=None, json_schema_extra=PII.MARKER, description="Client phone. PII — M4 strips for non-authorized roles")
    date_of_birth: Optional[date] = Field(default=None, json_schema_extra=PII.MARKER, description="Date of birth. PII — M4 strips for non-authorized roles")
    ssn_last_four: Optional[str] = Field(default=None, pattern=r"^[0-9]{4}$", json_schema_extra=PII.MARKER, description="Last four SSN digits. PII")
    tax_id: Optional[str] = Field(default=None, json_schema_extra=PII.MARKER, description="EIN for entities/trusts. PII")
    risk_tolerance: Optional[str] = Field(default=None, description="Suitability result: conservative to aggressive")
    investment_objectives: list[str] = Field(default_factory=list, description="Investment objectives: growth, income, capital_preservation, speculation, balanced")
    time_horizon: Optional[str] = Field(default=None, description="short_term (<3y), medium_term (3-10y), long_term (>10y)")
    annual_income_range: Optional[str] = Field(default=None, description="Self-reported income bracket")
    net_worth_range: Optional[str] = Field(default=None, description="Self-reported total net worth bracket")
    liquid_net_worth_range: Optional[str] = Field(default=None, description="Excludes primary residence")
    tax_bracket: Optional[str] = Field(default=None, description="Client tax bracket")
    advisor_ref: Optional[UUID] = Field(default=None, description="Canonical Advisor ID")
    firm_id: UUID = Field(description="Canonical Firm ID")
    household_ref: Optional[UUID] = Field(default=None, description="Canonical Household ID")
    archetype: Optional[str] = Field(default=None, description="Client segmentation: mass_affluent, hnw, uhnw")
    jurisdiction: str = Field(description="Primary regulatory jurisdiction (US, US-CA, UK, EU, SG, HK)")
    accounts: list[UUID] = Field(default_factory=list, description="Canonical Account IDs linked to this client")
    kyc_status: Optional[str] = Field(default=None, description="KYC verification status: pending, verified, expired, failed")
    kyc_verified_date: Optional[date] = Field(default=None, description="Date KYC was last verified")
    pii_classification: str = Field(default="confidential", description="Data classification: public, internal, confidential, restricted")
    vendor_mappings: Optional[ClientVendorMappings] = Field(default=None, description="Preserves vendor-specific client identifiers")
    reconciliation: Optional[Reconciliation] = Field(default=None, description="Cross-vendor agreement tracking")
    source_system: str = Field(description="Source system that provided this client record")
    source_id: str = Field(description="Vendor-specific client ID")
    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Record last update timestamp")

    @field_validator("client_type")
    @classmethod
    def validate_client_type(cls, v: str) -> str:
        allowed = {"individual", "entity", "trust"}
        if v not in allowed:
            raise ValueError(f"client_type must be one of {allowed}")
        return v


# ---------------------------------------------------------------------------
# 2. TaxLot (BEFORE Holding — Holding references TaxLot)
# ---------------------------------------------------------------------------

class CostBasisMethod(str, enum.Enum):
    """Cost basis method. REQUIRED on TaxLot — regulatory risk if missing."""
    SPECIFIC_LOT = "specific_lot"
    AVERAGE_COST = "average_cost"
    FIFO = "fifo"
    LIFO = "lifo"
    HIFO = "hifo"

class TaxLot(BaseModel):
    """Individual tax lot within a holding. cost_basis_method is REQUIRED — regulatory risk if missing."""
    lot_id: UUID = Field(description="Primary key for this tax lot")
    holding_ref: str = Field(description="Canonical Holding ID this lot belongs to")
    security_ref: Optional[str] = Field(default=None, description="Canonical security identifier")
    acquisition_date: date = Field(description="Date the lot was acquired")
    acquisition_price: Optional[float] = Field(default=None, description="Price per unit at acquisition")
    quantity: float = Field(description="Number of shares/units in this lot")
    cost_basis_method: CostBasisMethod = Field(description="REQUIRED. Custodian default varies: Schwab=specific_lot, Fidelity=average_cost (mutual funds)/specific_lot (equities). NEVER null.")
    cost_basis_amount: float = Field(description="Total cost basis for this lot")
    holding_period: Optional[str] = Field(default=None, description="short_term, long_term, or unknown")
    unrealized_gain_loss: Optional[float] = Field(default=None, description="Unrealized gain/loss for this lot")
    wash_sale_disallowed: Optional[float] = Field(default=None, description="Disallowed loss amount if wash sale applies")
    source_custodian: str = Field(description="Which custodian provided this data")
    source_cost_basis_method: Optional[str] = Field(default=None, description="Custodian's native method name (for reconciliation)")

    @field_validator("cost_basis_method", mode="before")
    @classmethod
    def cost_basis_method_never_null(cls, v: Any) -> Any:
        if v is None:
            raise ValueError("cost_basis_method is REQUIRED and must never be null — regulatory violation risk")
        return v


# ---------------------------------------------------------------------------
# 3. Holding (references TaxLot)
# ---------------------------------------------------------------------------

class Holding(BaseModel):
    """Canonical position/holding. Maps from Orion Position, SF FSC FinancialHolding, custodian positions."""
    canonical_id: UUID = Field(description="Primary key for canonical holding record")
    account_ref: str = Field(description="Canonical Account ID")
    client_ref: Optional[str] = Field(default=None, description="Canonical Client ID")
    security_identifier: Optional[SecurityIdentifier] = Field(default=None, description="Cross-reference: multiple identifiers for the same security")
    security_name: Optional[str] = Field(default=None, description="Security display name")
    security_type: Optional[str] = Field(default=None, description="Security classification: equity, fixed_income, mutual_fund, etf, option, cash, alternative, other")
    quantity: float = Field(description="Number of shares/units held")
    market_value: float = Field(description="Current market value. Excludes accrued interest by default (Schwab convention).")
    market_value_includes_accrued: bool = Field(default=False, description="Explicit flag — M7 translator sets based on custodian feed")
    cost_basis: Optional[float] = Field(default=None, description="Total cost basis for this holding position")
    unrealized_gain_loss: Optional[float] = Field(default=None, description="Unrealized gain/loss amount")
    unrealized_gain_loss_pct: Optional[float] = Field(default=None, description="Unrealized gain/loss as percentage")
    weight_in_account: Optional[float] = Field(default=None, description="Percentage of account this holding represents")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    as_of_date: date = Field(description="Date this position data is valid for")
    account_type: Optional[AccountType] = Field(default=None, description="Account type for ERISA/tax rules. Unified enum per BLOCKER-8.")
    source_system: str = Field(description="Source system that provided this holding data")
    source_id: str = Field(description="Vendor-specific holding/position ID")
    tax_lots: list[TaxLot] = Field(default_factory=list, description="Individual tax lots for this holding")



# ---------------------------------------------------------------------------
# 4. ComplianceCheck (BEFORE Order — Order references ComplianceCheck)
# ---------------------------------------------------------------------------

class ComplianceCheckType(str, enum.Enum):
    RESTRICTED_LIST = "restricted_list"
    CONCENTRATION_LIMIT = "concentration_limit"
    TRADING_WINDOW = "trading_window"
    SUITABILITY = "suitability"
    CHINESE_WALL = "chinese_wall"
    POD_ISOLATION = "pod_isolation"
    MNPI_FILTER = "mnpi_filter"
    ERISA_PROHIBITED_TRANSACTION = "erisa_prohibited_transaction"
    RMD_CHECK = "rmd_check"
    BSA_AML_CTR = "bsa_aml_ctr"
    BSA_AML_SAR = "bsa_aml_sar"
    SANCTIONS_SCREEN = "sanctions_screen"

class ComplianceDecision(str, enum.Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    WARN = "WARN"
    REQUIRE_APPROVAL = "REQUIRE_APPROVAL"
    ESCALATE = "ESCALATE"

class ComplianceCheckInputContext(BaseModel):
    """What was checked (security, client, action)."""
    security_id: Optional[str] = Field(default=None, description="Security identifier checked")
    client_id: Optional[str] = Field(default=None, description="Client identifier checked")
    action: Optional[str] = Field(default=None, description="Action being checked")
    archetype: Optional[str] = Field(default=None, description="Firm archetype context")
    account_type: Optional[str] = Field(default=None, description="Account type context")

class ComplianceCheck(BaseModel):
    """Result of a deterministic OPA compliance check. NOT LLM-generated."""
    check_id: UUID = Field(description="Primary key for this compliance check result")
    check_type: ComplianceCheckType = Field(description="Type of compliance check performed")
    decision: ComplianceDecision = Field(description="Compliance decision: ALLOW, DENY, WARN, REQUIRE_APPROVAL, ESCALATE")
    reason: str = Field(description="Human-readable reason for the decision")
    rule_applied: str = Field(description="OPA rule path: e.g., authority/restricted_list.rego:check_restricted_list")
    policy_bundle_version: Optional[str] = Field(default=None, description="OPA bundle version for audit trail")
    wsp_section: Optional[str] = Field(default=None, description="WSP section this rule maps to (ARCH-06 Gap 3)")
    input_context: Optional[ComplianceCheckInputContext] = Field(default=None, description="What was checked")
    details: Optional[dict[str, Any]] = Field(default=None, description="Additional context (e.g., concentration percentage)")
    evaluated_at: datetime = Field(description="When the check was evaluated")
    trace_id: str = Field(description="Links to M10 audit trail")


# ---------------------------------------------------------------------------
# 5. Order (references ComplianceCheck)
# ---------------------------------------------------------------------------

class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLIANCE_CHECK = "compliance_check"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    CONFIRMED = "confirmed"
    PENDING_SETTLEMENT = "pending_settlement"
    SETTLED = "settled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    SETTLEMENT_FAILED = "settlement_failed"
    ESCALATED = "escalated"

class TaxImpact(BaseModel):
    """Estimated tax impact shown at HITL gate."""
    estimated_gain_loss: float = Field(description="Estimated gain or loss amount")
    holding_period: str = Field(description="short_term or long_term")
    tax_rate_estimate: Optional[float] = Field(default=None, description="Estimated applicable tax rate")
    wash_sale_risk: bool = Field(default=False, description="True if wash sale risk detected")

class Order(BaseModel):
    """Canonical trade order. Used by Execution Specialist state machine."""
    order_id: UUID = Field(description="Primary key for canonical order")
    client_ref: str = Field(description="Canonical Client ID")
    account_ref: str = Field(description="Canonical Account ID")
    security_identifier: Optional[SecurityIdentifier] = Field(default=None, description="Security being traded")
    side: str = Field(description="Trade side: buy, sell, sell_short, buy_to_cover")
    order_type: Optional[str] = Field(default=None, description="Order type: market, limit, stop, stop_limit")
    quantity: float = Field(description="Number of shares/units to trade")
    limit_price: Optional[float] = Field(default=None, description="Limit price for limit/stop_limit orders")
    stop_price: Optional[float] = Field(default=None, description="Stop price for stop/stop_limit orders")
    time_in_force: str = Field(default="day", description="Time in force: day, gtc, ioc, fok")
    status: OrderStatus = Field(description="Order lifecycle status per Execution Specialist state machine")
    compliance_checks: list[ComplianceCheck] = Field(default_factory=list, description="Compliance check results for this order")
    hitl_approval: Optional[HitlApproval] = Field(default=None, description="HITL approval record if approved")
    submitted_at: Optional[datetime] = Field(default=None, description="When order was submitted to execution venue")
    confirmed_at: Optional[datetime] = Field(default=None, description="When order execution was confirmed")
    settled_at: Optional[datetime] = Field(default=None, description="When order settlement completed")
    settlement_date_expected: Optional[date] = Field(default=None, description="Expected settlement date (T+1 from trade date)")
    execution_venue: Optional[str] = Field(default=None, description="Custodian API, FIX broker, OMS")
    fill_price: Optional[float] = Field(default=None, description="Actual execution price")
    fill_quantity: Optional[float] = Field(default=None, description="Actual filled quantity")
    commission: Optional[float] = Field(default=None, description="Commission charged")
    account_type: Optional[AccountType] = Field(default=None, description="Account type for ERISA/tax rules. Unified enum per BLOCKER-8.")
    tax_impact: Optional[TaxImpact] = Field(default=None, description="Estimated tax impact shown at HITL gate")
    trace_id: Optional[str] = Field(default=None, description="Links to M10 audit trail")
    created_at: datetime = Field(description="Order creation timestamp")


# ---------------------------------------------------------------------------
# 6. Transaction
# ---------------------------------------------------------------------------

class TransactionType(str, enum.Enum):
    BUY = "buy"
    SELL = "sell"
    SELL_SHORT = "sell_short"
    BUY_TO_COVER = "buy_to_cover"
    DIVIDEND = "dividend"
    INTEREST = "interest"
    FEE = "fee"
    MANAGEMENT_FEE = "management_fee"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    DISTRIBUTION = "distribution"
    CONTRIBUTION = "contribution"
    WIRE_IN = "wire_in"
    WIRE_OUT = "wire_out"
    JOURNAL = "journal"
    REINVESTMENT = "reinvestment"
    RETURN_OF_CAPITAL = "return_of_capital"
    CORPORATE_ACTION = "corporate_action"
    MARGIN_INTEREST = "margin_interest"

class CostBasisImpact(BaseModel):
    """Tax impact of a transaction."""
    realized_gain_loss: Optional[float] = Field(default=None, description="Realized gain or loss from this transaction")
    holding_period: Optional[str] = Field(default=None, description="short_term or long_term")
    wash_sale_disallowed: Optional[float] = Field(default=None, description="Disallowed loss if wash sale applies")

class Transaction(BaseModel):
    """Canonical transaction record. Trade history, dividends, fees, transfers."""
    transaction_id: UUID = Field(description="Primary key for canonical transaction")
    account_ref: UUID = Field(description="Canonical Account ID")
    client_ref: Optional[UUID] = Field(default=None, description="Canonical Client ID")
    order_ref: Optional[UUID] = Field(default=None, description="Canonical Order ID if trade originated from 007")
    transaction_type: TransactionType = Field(description="Transaction classification normalized by M7 translator.")
    security_identifier: Optional[SecurityIdentifier] = Field(default=None, description="Null for cash transactions (fees, wires)")
    security_name: Optional[str] = Field(default=None, description="Security display name")
    quantity: Optional[float] = Field(default=None, description="Number of shares/units. Null for cash transactions.")
    price: Optional[float] = Field(default=None, description="Price per unit at execution")
    amount: float = Field(description="Total transaction amount")
    commission: Optional[float] = Field(default=None, description="Commission charged")
    fees: Optional[float] = Field(default=None, description="SEC fees, exchange fees, etc.")
    net_amount: Optional[float] = Field(default=None, description="Amount after commissions and fees")
    trade_date: date = Field(description="Date the trade was executed")
    settlement_date: Optional[date] = Field(default=None, description="Settlement date (T+1 for equities since May 2024)")
    settlement_status: Optional[str] = Field(default=None, description="Settlement lifecycle: pending, settled, failed")
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")
    description: Optional[str] = Field(default=None, description="Custodian-provided transaction description")
    tax_lot_ref: Optional[str] = Field(default=None, description="Tax lot ID if this transaction created/closed a lot")
    cost_basis_impact: Optional[CostBasisImpact] = Field(default=None, description="Tax impact of this transaction")
    account_type: Optional[AccountType] = Field(default=None, description="Account type for ERISA/tax rules. Unified enum per BLOCKER-8.")
    source_system: str = Field(description="Source system that provided this transaction")
    source_id: str = Field(description="Custodian transaction ID")
    source_transaction_type: Optional[str] = Field(default=None, description="Custodian's native transaction type code (for reconciliation)")
    trace_id: Optional[str] = Field(default=None, description="Links to M10 audit trail")
    created_at: datetime = Field(description="Transaction record creation timestamp")


# ---------------------------------------------------------------------------
# 7. Balance
# ---------------------------------------------------------------------------

class Balance(BaseModel):
    """Canonical account balance. Maps from custodian balance feeds (Schwab, Fidelity, Pershing)."""
    balance_id: UUID = Field(description="Primary key for canonical balance snapshot")
    account_ref: UUID = Field(description="Canonical Account ID")
    client_ref: Optional[UUID] = Field(default=None, description="Canonical Client ID")
    total_value: float = Field(description="Total account value (long_market_value + cash_balance - short_market_value)")
    cash_balance: Optional[float] = Field(default=None, description="Available cash (settled)")
    cash_unsettled: Optional[float] = Field(default=None, description="Cash from unsettled trades")
    money_market_balance: Optional[float] = Field(default=None, description="Sweep/money market balance")
    long_market_value: Optional[float] = Field(default=None, description="Market value of long positions")
    short_market_value: Optional[float] = Field(default=None, description="Market value of short positions (absolute value)")
    margin_balance: Optional[float] = Field(default=None, description="Margin debit balance")
    margin_equity: Optional[float] = Field(default=None, description="Equity in margin account")
    buying_power: Optional[float] = Field(default=None, description="Available buying power")
    accrued_interest: Optional[float] = Field(default=None, description="Accrued interest on fixed income holdings")
    pending_activity: Optional[float] = Field(default=None, description="Pending deposits/withdrawals")
    account_type: Optional[AccountType] = Field(default=None, description="Account type for ERISA/tax rules (ARCH-06 Gap 5). Unified enum per BLOCKER-8.")
    currency: str = Field(default="USD", pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")
    as_of_date: date = Field(description="Date this balance snapshot is valid for")
    as_of_time: Optional[datetime] = Field(default=None, description="Intraday timestamp if real-time balance")
    is_real_time: bool = Field(default=False, description="True if from real-time API, false if from daily file")
    source_system: str = Field(description="Source system that provided this balance data")
    source_id: str = Field(description="Vendor-specific balance record ID")
    source_balance_components: Optional[dict[str, Any]] = Field(default=None, description="Custodian's native balance breakdown (for reconciliation).")


# ---------------------------------------------------------------------------
# 8. Household (CONTAINER model — NOT unified)
# ---------------------------------------------------------------------------

class HouseholdMember(BaseModel):
    client_ref: str = Field(description="Canonical Client ID")
    role: str = Field(description="Member role: primary, spouse, dependent, trustee, beneficiary, authorized_signer, power_of_attorney")
    source: str = Field(description="Which vendor system defined this membership")

class HouseholdAccount(BaseModel):
    account_ref: str = Field(description="Canonical Account ID")
    source: str = Field(description="Which vendor system linked this account")

class HouseholdVendorSFSC(BaseModel):
    household_id: str = Field(description="SF Record ID")
    grouping_type: str = Field(default="relationship", description="SF FSC uses relationship grouping")

class HouseholdVendorOrion(BaseModel):
    household_id: str = Field(description="Orion Household ID")
    grouping_type: str = Field(default="portfolio_management", description="Orion uses portfolio_management grouping")

class HouseholdVendorSchwab(BaseModel):
    master_account: str = Field(description="Schwab master account number")
    grouping_type: str = Field(default="custodial", description="Schwab uses custodial grouping")

class HouseholdVendorMappings(BaseModel):
    salesforce_fsc: Optional[HouseholdVendorSFSC] = None
    orion: Optional[HouseholdVendorOrion] = None
    schwab: Optional[HouseholdVendorSchwab] = None

class Household(BaseModel):
    """CONTAINER model — holds vendor-specific groupings, not a unified model."""
    canonical_id: UUID = Field(description="Primary key for canonical household")
    display_name: str = Field(description="Human-readable household display name")
    primary_source: str = Field(description="Primary source system: salesforce_fsc, orion, schwab, fidelity, pershing, manual")
    members: list[HouseholdMember] = Field(description="Household members with roles and source attribution")
    accounts: list[HouseholdAccount] = Field(default_factory=list, description="Accounts linked to this household")
    vendor_mappings: Optional[HouseholdVendorMappings] = Field(default=None, description="Preserves vendor-specific grouping semantics")
    reconciliation: Optional[Reconciliation] = Field(default=None, description="Cross-vendor agreement tracking")


# ---------------------------------------------------------------------------
# 9. ComplianceAlert
# ---------------------------------------------------------------------------

class AlertType(str, enum.Enum):
    RESTRICTED_LIST_VIOLATION = "restricted_list_violation"
    CONCENTRATION_BREACH = "concentration_breach"
    SUITABILITY_DRIFT = "suitability_drift"
    MNPI_LEAKAGE_DETECTED = "mnpi_leakage_detected"
    CHINESE_WALL_BREACH = "chinese_wall_breach"
    BSA_AML_CTR = "bsa_aml_ctr"
    BSA_AML_SAR = "bsa_aml_sar"
    SANCTIONS_MATCH = "sanctions_match"
    ERISA_PROHIBITED_TRANSACTION = "erisa_prohibited_transaction"
    TRADING_WINDOW_VIOLATION = "trading_window_violation"
    RMD_MISSED = "rmd_missed"
    WASH_SALE_DETECTED = "wash_sale_detected"
    PRINCIPAL_REVIEW_OVERDUE = "principal_review_overdue"
    CROSS_BORDER_VIOLATION = "cross_border_violation"
    POD_ISOLATION_BREACH = "pod_isolation_breach"

class AlertSeverity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"

class AlertStatus(str, enum.Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    INVESTIGATING = "investigating"
    RESOLVED = "resolved"
    ESCALATED = "escalated"
    FALSE_POSITIVE = "false_positive"

class EscalationEntry(BaseModel):
    escalated_to: str = Field(description="Who the alert was escalated to")
    escalated_at: datetime = Field(description="When the escalation occurred")
    reason: str = Field(description="Reason for escalation")

class AlertResolution(BaseModel):
    resolved_by: str = Field(description="Who resolved the alert")
    resolved_at: datetime = Field(description="When the alert was resolved")
    resolution_type: str = Field(description="Resolution type: action_taken, false_positive, risk_accepted, referred_to_regulator")
    resolution_notes: str = Field(description="Notes on the resolution")

class AlertEvidence(BaseModel):
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$", description="SHA-256 of input data")
    threshold_value: Optional[float] = Field(default=None, description="Threshold that was breached")
    actual_value: Optional[float] = Field(default=None, description="Actual value that triggered the alert")
    details: Optional[str] = Field(default=None, description="Additional evidence details")

class ComplianceAlert(BaseModel):
    """Proactive compliance alert generated by OPA rules (M2/M4). NOT LLM-generated."""
    alert_id: UUID = Field(description="Primary key for this compliance alert")
    alert_type: AlertType = Field(description="Classification of the compliance alert")
    severity: AlertSeverity = Field(description="Alert severity. Critical = immediate action required.")
    status: AlertStatus = Field(description="Current alert lifecycle status")
    title: Optional[str] = Field(default=None, description="Human-readable alert title")
    description: Optional[str] = Field(default=None, description="Detailed description of what triggered the alert")
    triggered_by_rule: str = Field(description="OPA rule path that triggered this alert")
    policy_bundle_version: Optional[str] = Field(default=None, description="OPA bundle version for reproducibility")
    wsp_section: str = Field(description="Written Supervisory Procedures section reference (REQUIRED per steering rule 19)")
    client_ref: Optional[UUID] = Field(default=None, description="Canonical Client ID if client-specific")
    account_ref: Optional[UUID] = Field(default=None, description="Canonical Account ID if account-specific")
    security_ref: Optional[str] = Field(default=None, description="Security identifier if security-specific")
    advisor_ref: Optional[UUID] = Field(default=None, description="Advisor whose action triggered the alert")
    firm_id: str = Field(description="Firm context for multi-tenant routing")
    archetype: Optional[str] = Field(default=None, description="Firm archetype (tier3_bd, tier4_ria, etc.)")
    jurisdiction: Optional[str] = Field(default=None, description="Regulatory jurisdiction (US, UK, EU, SG, HK)")
    assigned_to: Optional[str] = Field(default=None, description="Compliance officer or principal assigned to review")
    escalation_chain: list[EscalationEntry] = Field(default_factory=list, description="Escalation history")
    resolution: Optional[AlertResolution] = Field(default=None, description="Resolution details if resolved")
    sla_deadline: Optional[datetime] = Field(default=None, description="Deadline for acknowledgment/resolution. BSA/AML SAR = 30 days.")
    related_alerts: list[UUID] = Field(default_factory=list, description="Related alert IDs for pattern detection")
    evidence: Optional[AlertEvidence] = Field(default=None, description="Supporting evidence for the alert")
    trace_id: str = Field(description="Links to M10 audit trail")
    created_at: datetime = Field(description="Alert creation timestamp")
    updated_at: datetime = Field(description="Alert last update timestamp")


# ---------------------------------------------------------------------------
# 10. AuditEntry
# ---------------------------------------------------------------------------

class ProvenanceStage(BaseModel):
    stage: str = Field(description="Stage name in the processing pipeline")
    module: str = Field(description="Module that processed this stage")
    hash: str = Field(pattern=r"^[a-f0-9]{64}$", description="SHA-256 hash for this stage")
    timestamp: datetime = Field(description="When this stage was processed")

class AuditEntry(BaseModel):
    """Immutable audit trail entry. Written to M10 3-tier storage. 6-year retention minimum (SEC 17a-4)."""
    canonical_id: UUID = Field(description="Primary key for this audit entry")
    trace_id: str = Field(description="Distributed trace ID linking all entries for one request across all modules")
    timestamp: datetime = Field(description="When this audit entry was created")
    actor_id: str = Field(description="AID hash of the actor (agent, advisor, system)")
    action: str = Field(description="What was done (e.g., portfolio_rebalance_proposed)")
    module: str = Field(description="Module that generated this entry: m1-m13")
    target_type: Optional[str] = Field(default=None, description="Entity type acted upon")
    target_id: Optional[str] = Field(default=None, description="Canonical ID of the entity acted upon")
    decision: str = Field(description="Decision outcome: allow, deny, warn, escalate, error")
    reason: Optional[str] = Field(default=None, description="Reason for the decision")
    input_hash: str = Field(pattern=r"^[a-f0-9]{64}$", description="SHA-256 of input payload for reproducibility")
    output_hash: str = Field(pattern=r"^[a-f0-9]{64}$", description="SHA-256 of output payload for reproducibility")
    policy_bundle_version: Optional[str] = Field(default=None, description="OPA bundle version used")
    rule_applied: Optional[str] = Field(default=None, description="Rego rule path evaluated")
    wsp_section: Optional[str] = Field(default=None, description="WSP section reference (steering rule 19)")
    data_sources_used: list[str] = Field(default_factory=list, description="Data sources consulted")
    latency_ms: int = Field(ge=0, description="Operation latency in milliseconds")
    archetype: Optional[str] = Field(default=None, description="Client archetype classification")
    role: Optional[str] = Field(default=None, description="Actor role (advisor, compliance_officer, agent)")
    firm_id: str = Field(description="Firm context for multi-tenant")
    jurisdiction: Optional[str] = Field(default=None, description="Regulatory jurisdiction")
    provenance_chain: Optional[list[ProvenanceStage]] = Field(default=None, description="Liability provenance chain (ARCH-06 Gap 2)")
    worm_record_id: str = Field(description="S3 Object Lock key for WORM copy")
    sha256_integrity: str = Field(pattern=r"^[a-f0-9]{64}$", description="SHA-256 of entire entry for tamper detection")
    langfuse_trace_url: Optional[str] = Field(default=None, description="Langfuse trace URL for LLM observability")
    crm_record_id: Optional[str] = Field(default=None, description="SF Record ID if written to CRM")
    retention_years: int = Field(default=6, description="Minimum retention period. 6 years default (SEC 17a-4).")



# ---------------------------------------------------------------------------
# 11. Performance
# ---------------------------------------------------------------------------

class PerformanceMethodology(str, enum.Enum):
    MODIFIED_DIETZ = "modified_dietz"
    DAILY_VALUATION = "daily_valuation"
    IRR_ONLY = "irr_only"

class PerformancePeriod(str, enum.Enum):
    MTD = "mtd"
    QTD = "qtd"
    YTD = "ytd"
    Y1 = "1y"
    Y3 = "3y"
    Y5 = "5y"
    Y10 = "10y"
    ITD = "itd"
    CUSTOM = "custom"

class Performance(BaseModel):
    """Canonical portfolio performance metrics. TWR vs IRR methodology must be explicit."""
    performance_id: UUID = Field(description="Primary key for this performance record")
    account_ref: UUID = Field(description="Canonical Account ID")
    client_ref: Optional[UUID] = Field(default=None, description="Canonical Client ID")
    household_ref: Optional[UUID] = Field(default=None, description="Canonical Household ID for household-level performance")
    period: PerformancePeriod = Field(description="Performance measurement period")
    twr_return: float = Field(description="Time-weighted return as decimal (e.g., 0.085 = 8.5%).")
    irr_return: Optional[float] = Field(default=None, description="Internal rate of return as decimal")
    gross_return: Optional[float] = Field(default=None, description="Return before fees")
    net_return: Optional[float] = Field(default=None, description="Return after fees")
    benchmark_return: Optional[float] = Field(default=None, description="Benchmark return for same period")
    benchmark_name: Optional[str] = Field(default=None, description="Benchmark index name")
    benchmark_ticker: Optional[str] = Field(default=None, description="Benchmark ticker")
    alpha: Optional[float] = Field(default=None, description="Excess return over benchmark")
    sharpe_ratio: Optional[float] = Field(default=None, description="Risk-adjusted return metric")
    standard_deviation: Optional[float] = Field(default=None, description="Portfolio volatility")
    max_drawdown: Optional[float] = Field(default=None, description="Maximum peak-to-trough decline")
    start_date: date = Field(description="Period start date")
    end_date: date = Field(description="Period end date")
    start_value: Optional[float] = Field(default=None, description="Portfolio value at period start")
    end_value: Optional[float] = Field(default=None, description="Portfolio value at period end")
    net_flows: Optional[float] = Field(default=None, description="Net cash flows during period")
    income_earned: Optional[float] = Field(default=None, description="Dividends + interest earned during period")
    realized_gains: Optional[float] = Field(default=None, description="Realized capital gains during period")
    fees_paid: Optional[float] = Field(default=None, description="Total fees paid during period")
    methodology: PerformanceMethodology = Field(description="TWR calculation methodology.")
    is_gips_compliant: bool = Field(default=False, description="True if follows GIPS standards")
    source_system: str = Field(description="Source system that provided this performance data")
    source_id: str = Field(description="Vendor-specific performance record ID")
    as_of_date: date = Field(description="Date this performance data is valid for")


# ---------------------------------------------------------------------------
# 12. SecurityProfile
# ---------------------------------------------------------------------------

class AssetClass(str, enum.Enum):
    EQUITY = "equity"
    FIXED_INCOME = "fixed_income"
    ETF = "etf"
    MUTUAL_FUND = "mutual_fund"
    OPTION = "option"
    FUTURE = "future"
    COMMODITY = "commodity"
    CRYPTO = "crypto"
    ALTERNATIVE = "alternative"
    MONEY_MARKET = "money_market"
    PREFERRED_STOCK = "preferred_stock"
    REIT = "reit"

class SecurityProfile(BaseModel):
    """Canonical security/instrument reference data."""
    canonical_id: UUID = Field(description="Primary key for this security profile")
    ticker: str = Field(description="Exchange ticker symbol")
    security_name: str = Field(description="Full legal or display name")
    asset_class: AssetClass = Field(description="Broad asset classification")
    cusip: Optional[str] = Field(default=None, pattern=r"^[A-Z0-9]{9}$", description="CUSIP identifier")
    isin: Optional[str] = Field(default=None, pattern=r"^[A-Z]{2}[A-Z0-9]{10}$", description="ISIN identifier")
    figi: Optional[str] = Field(default=None, pattern=r"^[A-Z0-9]{12}$", description="FIGI identifier")
    sedol: Optional[str] = Field(default=None, pattern=r"^[A-Z0-9]{7}$", description="SEDOL identifier")
    bloomberg_id: Optional[str] = Field(default=None, description="Bloomberg ticker format")
    exchange: Optional[str] = Field(default=None, description="Primary exchange MIC code")
    sector: Optional[str] = Field(default=None, description="GICS sector")
    industry: Optional[str] = Field(default=None, description="GICS industry")
    market_cap: Optional[float] = Field(default=None, ge=0, description="Market capitalization")
    pe_ratio: Optional[float] = Field(default=None, description="Price-to-earnings ratio")
    eps: Optional[float] = Field(default=None, description="Earnings per share")
    dividend_yield: Optional[float] = Field(default=None, ge=0, description="Annual yield as decimal")
    beta: Optional[float] = Field(default=None, description="Beta relative to market")
    fifty_two_week_high: Optional[float] = Field(default=None, description="52-week high price")
    fifty_two_week_low: Optional[float] = Field(default=None, description="52-week low price")
    avg_volume_30d: Optional[int] = Field(default=None, ge=0, description="30-day average trading volume")
    shares_outstanding: Optional[int] = Field(default=None, ge=0, description="Total shares outstanding")
    description: Optional[str] = Field(default=None, description="Business description")
    country: Optional[str] = Field(default=None, pattern=r"^[A-Z]{2}$", description="ISO-3166-1 alpha-2 domicile")
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")
    is_restricted: bool = Field(default=False, description="True if on firm restricted list (M2 OPA check)")
    restricted_since: Optional[date] = Field(default=None, description="Date added to restricted list")
    mnpi_flag: bool = Field(default=False, description="True if MNPI exists for this security (M4 filters before LLM)")
    last_updated: datetime = Field(description="When this profile was last updated")
    source_system: str = Field(description="Source system that provided this security data")
    source_id: str = Field(description="Vendor-specific security ID")


# ---------------------------------------------------------------------------
# 13. Quote
# ---------------------------------------------------------------------------

class Quote(BaseModel):
    """Canonical price quote. is_delayed is REQUIRED for compliance disclosure."""
    canonical_id: UUID = Field(description="Primary key for this quote")
    security_ref: UUID = Field(description="Canonical SecurityProfile ID")
    ticker: str = Field(description="Ticker for quick reference")
    price: float = Field(description="Last traded or latest quoted price")
    bid: Optional[float] = Field(default=None, description="Current bid price")
    ask: Optional[float] = Field(default=None, description="Current ask price")
    bid_size: Optional[int] = Field(default=None, description="Bid size in lots")
    ask_size: Optional[int] = Field(default=None, description="Ask size in lots")
    volume: Optional[int] = Field(default=None, ge=0, description="Session trading volume")
    open: Optional[float] = Field(default=None, description="Session open price")
    high: Optional[float] = Field(default=None, description="Session high price")
    low: Optional[float] = Field(default=None, description="Session low price")
    previous_close: Optional[float] = Field(default=None, description="Previous session close price")
    change: Optional[float] = Field(default=None, description="Absolute change from previous close")
    change_pct: Optional[float] = Field(default=None, description="Percentage change")
    vwap: Optional[float] = Field(default=None, description="Volume-weighted average price")
    as_of_timestamp: datetime = Field(description="Timestamp of this quote")
    is_delayed: bool = Field(description="True if delayed. Compliance must disclose. REQUIRED.")
    delay_minutes: Optional[int] = Field(default=None, ge=0, description="Minutes delayed (null if real-time)")
    market_status: Optional[str] = Field(default=None, description="Market status: pre_market, open, post_market, closed")
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")
    source_system: str = Field(description="Source system")
    source_id: str = Field(description="Vendor-specific quote ID")


# ---------------------------------------------------------------------------
# 14. PlanSummary
# ---------------------------------------------------------------------------

class PlanRecommendation(BaseModel):
    category: str = Field(description="Category: savings, investment, insurance, estate, tax, debt, other")
    description: str = Field(description="Recommendation description")
    priority: str = Field(description="Priority: high, medium, low")

class PlanAssumptions(BaseModel):
    inflation_rate: float = Field(description="As decimal (0.03 = 3%)")
    return_assumption: float = Field(description="As decimal (0.07 = 7%)")
    life_expectancy: int = Field(ge=0, description="Assumed life expectancy in years")
    retirement_age: Optional[int] = Field(default=None, description="Assumed retirement age")
    tax_rate_assumption: Optional[float] = Field(default=None, description="Assumed tax rate as decimal")

class PlanVendorEMoney(BaseModel):
    plan_id: str = Field(description="eMoney plan ID")
    scenario_id: Optional[str] = Field(default=None, description="eMoney scenario ID")

class PlanVendorMoneyGuidePro(BaseModel):
    plan_id: str = Field(description="MoneyGuidePro plan ID")
    scenario_name: Optional[str] = Field(default=None, description="MoneyGuidePro scenario name")

class PlanVendorRightCapital(BaseModel):
    plan_id: str = Field(description="RightCapital plan ID")

class PlanVendorMappings(BaseModel):
    emoney: Optional[PlanVendorEMoney] = None
    moneyguidepro: Optional[PlanVendorMoneyGuidePro] = None
    rightcapital: Optional[PlanVendorRightCapital] = None

class PlanSummary(BaseModel):
    """Canonical financial plan summary. Raw plan data NEVER sent to LLM (M4 filters)."""
    canonical_id: UUID = Field(description="Primary key for this plan summary")
    client_ref: UUID = Field(description="Canonical Client ID")
    household_ref: Optional[UUID] = Field(default=None, description="Canonical Household ID")
    plan_name: str = Field(description="Plan display name")
    plan_type: Optional[str] = Field(default=None, description="Plan type: comprehensive, retirement_only, education_only, estate, tax, insurance")
    probability_of_success: float = Field(ge=0, le=100, description="Overall plan success probability (0-100)")
    as_of_date: date = Field(description="Date this plan summary is valid for")
    total_assets: Optional[float] = Field(default=None, ge=0, description="Total assets in plan")
    total_liabilities: Optional[float] = Field(default=None, ge=0, description="Total liabilities in plan")
    net_worth: Optional[float] = Field(default=None, description="Net worth (assets - liabilities)")
    retirement_goal_amount: Optional[float] = Field(default=None, ge=0, description="Retirement goal target amount")
    retirement_target_date: Optional[date] = Field(default=None, description="Retirement target date")
    retirement_income_gap: Optional[float] = Field(default=None, description="Annual income shortfall in retirement (negative = surplus)")
    monte_carlo_success_pct: Optional[float] = Field(default=None, ge=0, le=100, description="Monte Carlo success percentage")
    monte_carlo_iterations: Optional[int] = Field(default=None, description="Number of Monte Carlo iterations")
    annual_savings_rate: Optional[float] = Field(default=None, ge=0, description="As decimal (0.15 = 15%)")
    annual_spending: Optional[float] = Field(default=None, ge=0, description="Annual spending amount")
    social_security_estimate: Optional[float] = Field(default=None, ge=0, description="Estimated annual SS benefit")
    pension_income: Optional[float] = Field(default=None, ge=0, description="Annual pension income")
    goals: list[UUID] = Field(default_factory=list, description="Canonical Goal IDs linked to this plan")
    assumptions: Optional[PlanAssumptions] = Field(default=None, description="Plan assumptions")
    recommendations: Optional[list[PlanRecommendation]] = Field(default=None, description="Plan recommendations (summary level)")
    vendor_mappings: Optional[PlanVendorMappings] = Field(default=None, description="Preserves vendor-specific plan identifiers")
    source_system: str = Field(description="Source system: emoney, moneyguidepro, rightcapital, manual")
    source_id: str = Field(description="Vendor-specific plan ID")
    created_at: datetime = Field(description="Plan creation timestamp")
    updated_at: datetime = Field(description="Plan last update timestamp")


# ---------------------------------------------------------------------------
# 15. Goal
# ---------------------------------------------------------------------------

class GoalType(str, enum.Enum):
    RETIREMENT = "retirement"
    EDUCATION = "education"
    HOME_PURCHASE = "home_purchase"
    EMERGENCY_FUND = "emergency_fund"
    WEALTH_TRANSFER = "wealth_transfer"
    CHARITABLE_GIVING = "charitable_giving"
    DEBT_PAYOFF = "debt_payoff"
    MAJOR_PURCHASE = "major_purchase"
    INCOME_REPLACEMENT = "income_replacement"
    LEGACY = "legacy"
    CUSTOM = "custom"

class GoalStatus(str, enum.Enum):
    ON_TRACK = "on_track"
    AT_RISK = "at_risk"
    BEHIND = "behind"
    ACHIEVED = "achieved"
    ABANDONED = "abandoned"

class GoalAssumptions(BaseModel):
    inflation_rate: float = Field(description="Assumed inflation rate as decimal")
    return_rate: float = Field(description="Assumed return rate as decimal")
    tax_rate: Optional[float] = Field(default=None, description="Assumed tax rate as decimal")

class GoalVendorSFSC(BaseModel):
    financial_goal_id: str = Field(description="SF FinancialGoal Record ID")
    goal_type_picklist: Optional[str] = Field(default=None, description="SF FSC picklist value")

class GoalVendorEMoney(BaseModel):
    goal_id: str = Field(description="eMoney goal ID")
    goal_category: Optional[str] = Field(default=None, description="eMoney goal category")

class GoalVendorMoneyGuidePro(BaseModel):
    goal_id: str = Field(description="MoneyGuidePro goal ID")
    goal_type: Optional[str] = Field(default=None, description="MoneyGuidePro goal type")

class GoalVendorMappings(BaseModel):
    salesforce_fsc: Optional[GoalVendorSFSC] = None
    emoney: Optional[GoalVendorEMoney] = None
    moneyguidepro: Optional[GoalVendorMoneyGuidePro] = None

class Goal(BaseModel):
    """Canonical financial goal. Maps from SF FSC FinancialGoal, eMoney, MoneyGuidePro."""
    canonical_id: UUID = Field(description="Primary key for this goal")
    client_ref: UUID = Field(description="Canonical Client ID")
    household_ref: Optional[UUID] = Field(default=None, description="Canonical Household ID if goal is household-level")
    plan_ref: Optional[UUID] = Field(default=None, description="Canonical PlanSummary ID this goal belongs to")
    goal_type: GoalType = Field(description="Goal classification")
    goal_name: str = Field(description="Display name (e.g., 'Retire at 65')")
    target_amount: float = Field(ge=0, description="Target dollar amount for the goal")
    current_amount: Optional[float] = Field(default=None, ge=0, description="Current funded amount toward the goal")
    funding_pct: Optional[float] = Field(default=None, ge=0, le=100, description="Percentage funded")
    target_date: date = Field(description="Target completion date")
    priority: str = Field(description="Goal priority: critical, high, medium, low")
    status: GoalStatus = Field(description="Current goal status based on latest plan run")
    monthly_contribution: Optional[float] = Field(default=None, ge=0, description="Monthly savings allocated to this goal")
    linked_accounts: list[UUID] = Field(default_factory=list, description="Canonical Account IDs funding this goal")
    assumptions: Optional[GoalAssumptions] = Field(default=None, description="Goal planning assumptions")
    vendor_mappings: Optional[GoalVendorMappings] = Field(default=None, description="Preserves vendor-specific goal semantics")
    as_of_date: date = Field(description="Date this goal data is valid for")
    source_system: str = Field(description="Source system")
    source_id: str = Field(description="Vendor-specific goal ID")
    created_at: datetime = Field(description="Goal creation timestamp")
    updated_at: datetime = Field(description="Goal last update timestamp")


# ---------------------------------------------------------------------------
# 16. InteractionSummary
# ---------------------------------------------------------------------------

class ActionItem(BaseModel):
    description: str = Field(description="Action item description")
    assigned_to: str = Field(description="Canonical ID of assignee")
    due_date: Optional[date] = Field(default=None, description="Due date for the action item")
    status: str = Field(description="Status: pending, in_progress, completed, cancelled")

class Attendee(BaseModel):
    name: str = Field(description="Attendee name")
    role: str = Field(description="Role: client, spouse, advisor, associate, specialist, attorney, cpa, other")
    canonical_ref: Optional[UUID] = Field(default=None, description="Canonical ID if known")

class CrmWriteBackEntry(BaseModel):
    record_id: str = Field(description="CRM record ID after write-back")
    written_at: datetime = Field(description="When the write-back occurred")
    status: str = Field(description="Write-back status: pending, written, failed")

class CrmWriteBack(BaseModel):
    salesforce_fsc: Optional[CrmWriteBackEntry] = None
    wealthbox: Optional[CrmWriteBackEntry] = None
    redtail: Optional[CrmWriteBackEntry] = None

class ComplianceReview(BaseModel):
    required: bool = Field(description="True if principal review required (BD under FINRA 2210)")
    review_id: Optional[str] = Field(default=None, description="Review record ID")
    status: str = Field(description="Review status: not_required, pending, approved, rejected")

class InteractionSummary(BaseModel):
    """Canonical meeting/interaction summary. Client Service Specialist output. Write-back to CRM."""
    model_config = {"populate_by_name": True}

    canonical_id: UUID = Field(description="Primary key for this interaction summary")
    client_ref: UUID = Field(description="Canonical Client ID")
    household_ref: Optional[UUID] = Field(default=None, description="Canonical Household ID")
    advisor_ref: UUID = Field(description="Canonical Advisor ID (from M1 AID)")
    interaction_type: str = Field(description="Type of client interaction")
    interaction_date: date = Field(alias="date", description="Date of the interaction")
    start_time: Optional[datetime] = Field(default=None, description="Interaction start time")
    end_time: Optional[datetime] = Field(default=None, description="Interaction end time")
    duration_minutes: Optional[int] = Field(default=None, ge=0, description="Duration in minutes")
    summary: str = Field(description="Agent-generated summary (MNPI-filtered before storage)")
    topics_discussed: list[str] = Field(default_factory=list, description="Topics discussed")
    action_items: list[ActionItem] = Field(default_factory=list, description="Action items from the interaction")
    attendees: list[Attendee] = Field(default_factory=list, description="People who attended")
    sentiment: Optional[str] = Field(default=None, description="Client sentiment: positive, neutral, concerned, negative")
    next_meeting_date: Optional[date] = Field(default=None, description="Scheduled next meeting date")
    crm_write_back: Optional[CrmWriteBack] = Field(default=None, description="Status of write-back to CRM systems")
    compliance_review: Optional[ComplianceReview] = Field(default=None, description="Principal review status if BD (FINRA 2210)")
    channel: Optional[str] = Field(default=None, description="Channel: slack, teams, whatsapp, web, email, phone, in_person")
    trace_id: str = Field(description="Links to M10 audit trail")
    source_system: str = Field(description="Source system")
    source_id: Optional[str] = Field(default=None, description="Vendor-specific interaction ID")
    created_at: datetime = Field(description="Record creation timestamp")
    updated_at: datetime = Field(description="Record last update timestamp")


# ---------------------------------------------------------------------------
# 17. ResearchBrief
# ---------------------------------------------------------------------------

class ResearchSource(BaseModel):
    source_type: str = Field(description="Source type: sec_filing, market_data, news, earnings_transcript, analyst_consensus, crm_data")
    description: str = Field(description="Description of the source")
    url: Optional[str] = Field(default=None, description="URL to the source")
    source_date: Optional[date] = Field(default=None, description="Date of the source material")

class Valuation(BaseModel):
    dcf_fair_value: Optional[float] = Field(default=None, description="DCF-derived fair value")
    comps_implied_value: Optional[float] = Field(default=None, description="Comparable companies implied value")
    monte_carlo_p5: Optional[float] = Field(default=None, description="Monte Carlo 5th percentile")
    monte_carlo_median: Optional[float] = Field(default=None, description="Monte Carlo median")
    monte_carlo_p95: Optional[float] = Field(default=None, description="Monte Carlo 95th percentile")

class ResearchBrief(BaseModel):
    """Structured output from Research Specialist (LangGraph pipeline). Source-attributed."""
    brief_id: UUID = Field(description="Primary key for this research brief")
    security_identifier: Optional[SecurityIdentifier] = Field(default=None, description="Security being researched")
    analyst_id: str = Field(description="Analyst or agent ID that produced this brief")
    rating: str = Field(description="Rating: strong_buy, buy, hold, sell, strong_sell")
    target_price: Optional[float] = Field(default=None, description="Analyst target price")
    current_price: Optional[float] = Field(default=None, description="Current market price at time of brief")
    summary: str = Field(description="Executive summary (2-3 paragraphs)")
    thesis: str = Field(description="Investment thesis")
    catalysts: list[str] = Field(default_factory=list, description="Potential catalysts")
    risks: list[str] = Field(default_factory=list, description="Key risks")
    valuation: Optional[Valuation] = Field(default=None, description="Valuation analysis")
    sources: list[ResearchSource] = Field(description="Sources used in the research")
    pipeline_run_id: str = Field(description="LangGraph pipeline execution ID")
    hitl_gates_passed: list[str] = Field(default_factory=list, description="HITL gates passed during pipeline")
    anti_fabrication_score: float = Field(ge=0, le=1, description="Anti-fabrication confidence score (0-1)")
    created_at: datetime = Field(description="Brief creation timestamp")
    trace_id: str = Field(description="Links to M10 audit trail")


# ---------------------------------------------------------------------------
# 18. PaymentInstruction
# ---------------------------------------------------------------------------

class PaymentType(str, enum.Enum):
    WIRE_DOMESTIC = "wire_domestic"
    WIRE_INTERNATIONAL = "wire_international"
    ACH_TRANSFER = "ach_transfer"
    CHECK_REQUEST = "check_request"
    JOURNAL_TRANSFER = "journal_transfer"
    STANDING_INSTRUCTION = "standing_instruction"
    DISTRIBUTION = "distribution"

class PaymentStatus(str, enum.Enum):
    DRAFT = "draft"
    COMPLIANCE_CHECK = "compliance_check"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    SUBMITTED = "submitted"
    PROCESSING = "processing"
    COMPLETED = "completed"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    FAILED = "failed"

class Beneficiary(BaseModel):
    name: str = Field(description="Beneficiary name")
    account_number: str = Field(description="Beneficiary account number (masked in logs)")
    routing_number: Optional[str] = Field(default=None, description="ABA routing number (domestic)")
    swift_bic: Optional[str] = Field(default=None, pattern=r"^[A-Z]{6}[A-Z0-9]{2}([A-Z0-9]{3})?$", description="SWIFT/BIC code (international)")
    iban: Optional[str] = Field(default=None, description="IBAN (international)")
    bank_name: Optional[str] = Field(default=None, description="Beneficiary bank name")
    bank_address: Optional[str] = Field(default=None, description="Beneficiary bank address")
    intermediary_bank: Optional[str] = Field(default=None, description="Intermediary/correspondent bank if required")

class BsaAml(BaseModel):
    """BSA/AML specific fields for payment compliance."""
    ctr_required: bool = Field(description="True if amount >= $10,000 (CTR threshold)")
    ctr_filed: Optional[bool] = Field(default=None, description="True if CTR has been filed")
    sar_flagged: bool = Field(description="True if structuring or suspicious pattern detected")
    sanctions_screened: bool = Field(description="True if sanctions screening completed")
    sanctions_result: Optional[str] = Field(default=None, description="Sanctions result: clear, potential_match, confirmed_match")
    ofac_screened: bool = Field(description="True if OFAC screening completed")
    ofac_result: Optional[str] = Field(default=None, description="OFAC result: clear, potential_match, confirmed_match")

class Iso20022Mapping(BaseModel):
    """ISO 20022 pain.001 message mapping (Phase 5)."""
    message_id: str = Field(description="pain.001 MsgId")
    payment_info_id: str = Field(description="pain.001 PmtInfId")
    end_to_end_id: str = Field(description="pain.001 EndToEndId")
    charge_bearer: str = Field(description="ISO 20022 ChrgBr: DEBT, CRED, SHAR, SLEV")

class PaymentInstruction(BaseModel):
    """Canonical payment/wire instruction. Maps to ISO 20022 pain.001. HITL mandatory."""
    instruction_id: UUID = Field(description="Primary key for this payment instruction")
    client_ref: UUID = Field(description="Canonical Client ID")
    account_ref: UUID = Field(description="Source account canonical ID")
    payment_type: PaymentType = Field(description="Payment classification")
    amount: float = Field(ge=0, description="Payment amount")
    currency: str = Field(pattern=r"^[A-Z]{3}$", description="ISO 4217 currency code")
    beneficiary: Beneficiary = Field(description="Beneficiary details")
    purpose: Optional[str] = Field(default=None, description="Payment purpose/memo")
    reference: Optional[str] = Field(default=None, description="Client or firm reference number")
    value_date: Optional[date] = Field(default=None, description="Requested value/settlement date")
    status: PaymentStatus = Field(description="Payment lifecycle status. HITL mandatory before submission.")
    compliance_checks: list[ComplianceCheck] = Field(default_factory=list, description="BSA/AML, sanctions, OFAC screening results")
    bsa_aml: Optional[BsaAml] = Field(default=None, description="BSA/AML specific fields")
    hitl_approval: Optional[HitlApproval] = Field(default=None, description="HITL approval record")
    iso20022_mapping: Optional[Iso20022Mapping] = Field(default=None, description="ISO 20022 pain.001 message mapping (Phase 5)")
    trace_id: str = Field(description="Links to M10 audit trail")
    source_system: str = Field(description="Source system: schwab, fidelity, pershing, swift_gateway, manual")
    source_id: Optional[str] = Field(default=None, description="Vendor-specific payment ID")
    created_at: datetime = Field(description="Payment creation timestamp")
    updated_at: datetime = Field(description="Payment last update timestamp")
