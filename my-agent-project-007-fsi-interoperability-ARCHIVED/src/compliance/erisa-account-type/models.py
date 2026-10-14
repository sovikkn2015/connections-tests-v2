"""
Gap 5: ERISA Account-Type — Pydantic v2 Models.

16 account types with per-type compliance rules.
Deterministic tax impact calculator.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class AccountType(str, Enum):
    """16 supported account types."""
    individual_taxable = "individual_taxable"
    joint_wros = "joint_wros"
    joint_tic = "joint_tic"
    joint_community_property = "joint_community_property"
    traditional_ira = "traditional_ira"
    roth_ira = "roth_ira"
    sep_ira = "sep_ira"
    simple_ira = "simple_ira"
    k401 = "401k"
    b403 = "403b"
    b457 = "457b"
    erisa_pension = "erisa_pension"
    ugma = "ugma"
    utma = "utma"
    trust_revocable = "trust_revocable"
    trust_irrevocable = "trust_irrevocable"
    estate = "estate"


class TaxStatus(str, Enum):
    taxable = "taxable"
    tax_deferred = "tax_deferred"
    tax_exempt = "tax_exempt"
    tax_advantaged = "tax_advantaged"


class CostBasisMethod(str, Enum):
    """Cost basis method — NEVER null (steering rule 16)."""
    specific_lot = "specific_lot"
    average_cost = "average_cost"
    fifo = "fifo"
    lifo = "lifo"
    hifo = "hifo"


class CapitalGainsType(str, Enum):
    short_term = "short_term"
    long_term = "long_term"


# ── Account Type Metadata ────────────────────────────────────────

ACCOUNT_TAX_STATUS: dict[str, TaxStatus] = {
    "individual_taxable": TaxStatus.taxable,
    "joint_wros": TaxStatus.taxable,
    "joint_tic": TaxStatus.taxable,
    "joint_community_property": TaxStatus.taxable,
    "traditional_ira": TaxStatus.tax_deferred,
    "roth_ira": TaxStatus.tax_exempt,
    "sep_ira": TaxStatus.tax_deferred,
    "simple_ira": TaxStatus.tax_deferred,
    "401k": TaxStatus.tax_deferred,
    "403b": TaxStatus.tax_deferred,
    "457b": TaxStatus.tax_deferred,
    "erisa_pension": TaxStatus.tax_deferred,
    "ugma": TaxStatus.taxable,
    "utma": TaxStatus.taxable,
    "trust_revocable": TaxStatus.taxable,
    "trust_irrevocable": TaxStatus.taxable,
    "estate": TaxStatus.taxable,
}

ERISA_GOVERNED_TYPES = frozenset({"401k", "403b", "457b", "erisa_pension"})

CONCENTRATION_LIMITS: dict[str, float] = {
    "401k": 10.0,
    "403b": 10.0,
    "457b": 10.0,
    "erisa_pension": 10.0,
    "estate": 10.0,
    # All others default to 15.0
}

DEFAULT_CONCENTRATION_LIMIT = 15.0


# ── Tax Lot ──────────────────────────────────────────────────────


class TaxLot(BaseModel):
    """Single tax lot — cost_basis_method is REQUIRED (never null)."""
    lot_id: str
    security_id: str
    quantity: float
    cost_basis_per_share: float
    cost_basis_method: CostBasisMethod  # REQUIRED — steering rule 16
    acquisition_date: date
    source_custodian: str = ""

    @property
    def total_cost_basis(self) -> float:
        return self.quantity * self.cost_basis_per_share

    @property
    def holding_period_days(self) -> int:
        return (date.today() - self.acquisition_date).days

    @property
    def is_long_term(self) -> bool:
        return self.holding_period_days > 365


# ── Tax Impact ───────────────────────────────────────────────────


class TaxImpact(BaseModel):
    """Deterministic tax impact calculation result."""
    account_type: str
    tax_status: TaxStatus
    security_id: str
    action: str  # buy or sell
    quantity: float
    current_price: float
    # Capital gains (sell only)
    capital_gains_type: Optional[CapitalGainsType] = None
    realized_gain_loss: float = 0.0
    cost_basis_used: float = 0.0
    holding_period_days: int = 0
    # Wash sale detection
    wash_sale_risk: bool = False
    wash_sale_reason: str = ""
    # Tax-deferred accounts have no immediate tax impact
    tax_deferred: bool = False
    tax_exempt: bool = False
    summary: str = ""


# ── Account-Type Check Input/Output ─────────────────────────────


class AccountTypeCheckInput(BaseModel):
    """Input for account-type compliance check via OPA."""
    account_type: str
    action: str = "buy"
    security_id: str = ""
    security_type: str = ""
    counterparty_id: Optional[str] = None
    proposed_position_pct: float = 0.0
    plan_id: Optional[str] = None
    client_age: float = 0.0
    rmd_taken_this_year: bool = True
    current_month: int = 1
    roth_account_age_years: int = 10
    trust_has_income_beneficiary: bool = False
    trust_has_remainder_beneficiary: bool = False
    portfolio_income_yield: float = 0.03
    security_yield: float = 0.02


class AccountTypeCheckResult(BaseModel):
    """Result from account-type OPA evaluation."""
    decision: str  # PASS, WARN, DENY
    reason: str
    rule_applied: str
    wsp_section: str
    account_type: str
    details: dict = Field(default_factory=dict)
