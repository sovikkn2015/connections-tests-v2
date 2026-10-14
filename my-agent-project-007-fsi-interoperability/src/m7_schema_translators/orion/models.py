"""
Orion vendor Pydantic models — Portfolio accounting platform.

Phase 2 Lighthouse: Position, Transaction, Household (portfolio_management
grouping), TaxLot (nested in Position).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class OrionTaxLot(BaseModel):
    """Orion tax lot (nested in OrionPosition.taxLots[])."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    lotId: str = Field(description="Orion lot ID.")
    symbol: Optional[str] = Field(default=None, description="Security ticker.")
    acquisitionDate: date = Field(description="Lot acquisition date.")
    acquisitionPrice: Optional[float] = Field(
        default=None, description="Price per unit at acquisition."
    )
    quantity: float = Field(description="Units in this lot.")
    costBasisMethod: Optional[str] = Field(
        default=None,
        description="Orion cost basis method — SPECIFIC_LOT, AVG_COST, FIFO, LIFO, HIFO.",
    )
    costBasisAmount: float = Field(description="Total cost basis for this lot.")
    holdingPeriod: Optional[str] = Field(
        default=None,
        description="Orion: SHORT_TERM, LONG_TERM, UNKNOWN.",
    )
    unrealizedGainLoss: Optional[float] = Field(
        default=None, description="Unrealized gain/loss."
    )
    washSaleDisallowed: Optional[float] = Field(
        default=None, description="Disallowed loss if wash sale."
    )


class OrionPosition(BaseModel):
    """Orion position — v2.0."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    positionId: str = Field(description="Orion position ID.")
    accountId: str = Field(description="Orion account ID.")
    clientId: Optional[str] = Field(
        default=None, description="Orion client ID."
    )
    symbol: Optional[str] = Field(default=None, description="Security ticker.")
    cusip: Optional[str] = Field(default=None, description="CUSIP.")
    isin: Optional[str] = Field(default=None, description="ISIN.")
    securityName: Optional[str] = Field(
        default=None, description="Security display name."
    )
    securityType: Optional[str] = Field(
        default=None,
        description="Classification — equity, fixed_income, mutual_fund, etf.",
    )
    quantity: float = Field(description="Units held.")
    marketValue: float = Field(description="Current market value.")
    includesAccruedInterest: Optional[bool] = Field(
        default=None,
        description="Orion explicit flag — whether marketValue includes accrued interest.",
    )
    costBasis: Optional[float] = Field(
        default=None, description="Total cost basis."
    )
    unrealizedGainLoss: Optional[float] = Field(
        default=None, description="Unrealized gain/loss."
    )
    unrealizedGainLossPct: Optional[float] = Field(
        default=None, description="Unrealized gain/loss percentage."
    )
    weightInAccount: Optional[float] = Field(
        default=None, description="Percentage of account."
    )
    currency: Optional[str] = Field(
        default="USD", description="ISO 4217 code."
    )
    asOfDate: date = Field(description="Position valid-for date.")
    accountType: Optional[str] = Field(
        default=None,
        description="Orion account type string (TAXABLE, TRADITIONAL_IRA, etc.).",
    )
    taxLots: list[OrionTaxLot] = Field(
        default_factory=list, description="Embedded tax lots."
    )


class OrionTransaction(BaseModel):
    """Orion transaction — v2.0."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    transactionId: str = Field(description="Orion transaction ID.")
    accountId: str = Field(description="Orion account ID.")
    clientId: Optional[str] = Field(
        default=None, description="Orion client ID."
    )
    type: str = Field(description="Orion transaction type abbreviation.")
    symbol: Optional[str] = Field(default=None, description="Security ticker.")
    cusip: Optional[str] = Field(default=None, description="CUSIP.")
    securityName: Optional[str] = Field(
        default=None, description="Security name."
    )
    quantity: Optional[float] = Field(
        default=None, description="Units (None for cash transactions)."
    )
    price: Optional[float] = Field(
        default=None, description="Price per unit."
    )
    amount: float = Field(description="Total transaction amount.")
    commission: Optional[float] = Field(
        default=None, description="Commission charged."
    )
    fees: Optional[float] = Field(
        default=None, description="SEC/exchange fees."
    )
    netAmount: Optional[float] = Field(
        default=None, description="Net after commissions and fees."
    )
    tradeDate: date = Field(description="Trade date.")
    settlementDate: Optional[date] = Field(
        default=None, description="Settlement date."
    )
    settlementStatus: Optional[str] = Field(
        default=None, description="PENDING, SETTLED, FAILED."
    )
    currency: Optional[str] = Field(default="USD", description="Currency.")
    description: Optional[str] = Field(
        default=None, description="Transaction description."
    )
    taxLotId: Optional[str] = Field(
        default=None, description="Linked tax-lot ID."
    )
    realizedGainLoss: Optional[float] = Field(
        default=None, description="Realized gain/loss."
    )
    holdingPeriod: Optional[str] = Field(
        default=None, description="Holding period category."
    )
    washSaleDisallowed: Optional[float] = Field(
        default=None, description="Disallowed wash sale loss."
    )
    accountType: Optional[str] = Field(
        default=None, description="Orion account type string."
    )
    customAttributes: Optional[dict] = Field(
        default=None,
        description=(
            "Vendor extension dict — reverse uses this to preserve order_ref."
        ),
    )
    createdAt: datetime = Field(description="Record creation timestamp.")


class OrionHouseholdMember(BaseModel):
    """Orion household member row."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    clientId: str = Field(description="Member client ID.")
    role: str = Field(description="Lowercase role — primary/spouse/etc.")


class OrionLinkedAccount(BaseModel):
    """Orion linked account row."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    accountId: str = Field(description="Linked account ID.")


class OrionHousehold(BaseModel):
    """Orion Household — portfolio_management grouping, v2.0."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    householdId: str = Field(description="Orion household ID.")
    householdName: str = Field(
        min_length=1, description="Household display name."
    )
    members: list[OrionHouseholdMember] = Field(
        default_factory=list, description="Member list."
    )
    linkedAccounts: list[OrionLinkedAccount] = Field(
        default_factory=list, description="Linked accounts."
    )
