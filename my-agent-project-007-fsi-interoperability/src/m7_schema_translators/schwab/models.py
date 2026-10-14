"""
Schwab vendor Pydantic models — Trader API v1.

Phase 2 Lighthouse: Position, TaxLot, MasterAccount (custodial Household grouping).

Schwab quirks:
- Market-value numerics may return with '$' and ',' in the string form — the
  vendor model strips them in a `mode="before"` field validator.
- AccountNumber is 8-digit (pattern-enforced).
- `unrealized_gain_loss_pct` is returned as a decimal (multiply by 100 at
  translator time).
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _strip_dollar(value: Any) -> Any:
    """Strip '$' and ',' from numeric vendor strings before pydantic type-coerces."""
    if isinstance(value, str):
        stripped = value.replace("$", "").replace(",", "").strip()
        if stripped == "":
            return None
        return stripped
    return value


class SchwabTaxLot(BaseModel):
    """Schwab tax lot (nested in SchwabPosition.taxLots[])."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    lotId: str = Field(description="Schwab lot ID.")
    symbol: Optional[str] = Field(default=None, description="Ticker.")
    acquisitionDate: date = Field(description="Acquisition date.")
    acquisitionPrice: Optional[float] = Field(
        default=None, description="Price per unit at acquisition."
    )
    quantity: float = Field(description="Units in this lot.")
    costBasisMethod: Optional[str] = Field(
        default=None,
        description="Schwab cost basis label (SpecificLot, SL, AverageCost, AC, FIFO, LIFO, HIFO, MinTax).",
    )
    costBasisAmount: float = Field(description="Total cost basis.")
    holdingPeriod: Optional[str] = Field(
        default=None, description="Schwab: ST, LT, UNKNOWN."
    )
    unrealizedGainLoss: Optional[float] = Field(
        default=None, description="Unrealized gain/loss."
    )
    washSaleDisallowed: Optional[float] = Field(
        default=None, description="Disallowed wash sale loss."
    )

    @field_validator(
        "acquisitionPrice",
        "costBasisAmount",
        "unrealizedGainLoss",
        "washSaleDisallowed",
        mode="before",
    )
    @classmethod
    def _strip_money(cls, v: Any) -> Any:  # noqa: N805
        return _strip_dollar(v)


class SchwabPosition(BaseModel):
    """Schwab position — Trader API v1."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    id: str = Field(description="Schwab position ID.")
    accountNumber: str = Field(
        pattern=r"^\d{8}$",
        description="Schwab 8-digit account number.",
    )
    accountHolderId: Optional[str] = Field(
        default=None, description="Schwab account holder ID."
    )
    symbol: Optional[str] = Field(default=None, description="Ticker.")
    cusip: Optional[str] = Field(default=None, description="CUSIP.")
    isin: Optional[str] = Field(default=None, description="ISIN.")
    description: Optional[str] = Field(
        default=None, description="Security description / display name."
    )
    assetClass: Optional[str] = Field(
        default=None,
        description="EQUITY, FIXED_INCOME, MUTUAL_FUND, ETF, OPTION, CASH.",
    )
    quantity: float = Field(description="Units held.")
    marketValue: float = Field(
        description="Market value (excludes accrued interest per Schwab convention)."
    )
    costBasis: Optional[float] = Field(
        default=None, description="Total cost basis."
    )
    unrealizedGainLoss: Optional[float] = Field(
        default=None, description="Unrealized gain/loss."
    )
    unrealizedGainLossPct: Optional[float] = Field(
        default=None,
        description=(
            "Schwab returns decimal (e.g. 0.085); translator multiplies by 100."
        ),
    )
    currency: Optional[str] = Field(default="USD", description="Currency.")
    asOfDate: date = Field(description="Position valid-for date.")
    accountType: Optional[str] = Field(
        default=None,
        description=(
            "Schwab label: INDIVIDUAL, JOINT_TOS, IRA, ROTH_IRA, SEP, SIMPLE, 401K, TRUST, UTMA, UGMA."
        ),
    )
    jurisdiction: Optional[str] = Field(
        default=None,
        description="Client jurisdiction (US or UK) — cost-basis input.",
    )
    taxLots: list[SchwabTaxLot] = Field(
        default_factory=list, description="Embedded tax lots."
    )

    @field_validator(
        "marketValue",
        "costBasis",
        "unrealizedGainLoss",
        mode="before",
    )
    @classmethod
    def _strip_money(cls, v: Any) -> Any:  # noqa: N805
        return _strip_dollar(v)


class SchwabLinkedAccountHolder(BaseModel):
    """Schwab master-account linked holder."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    accountHolderId: str = Field(description="Holder ID.")
    role: str = Field(description="PRIMARY, SPOUSE, etc (upper case).")


class SchwabLinkedAccount(BaseModel):
    """Schwab master-account linked sub-account."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    accountNumber: str = Field(
        pattern=r"^\d{8}$", description="8-digit account number."
    )


class SchwabMasterAccount(BaseModel):
    """Schwab master account — custodial Household grouping."""

    model_config = ConfigDict(
        extra="forbid", frozen=True, str_strip_whitespace=True
    )

    masterAccountNumber: str = Field(description="Master account number.")
    name: str = Field(min_length=1, description="Master account display name.")
    linkedAccountHolders: list[SchwabLinkedAccountHolder] = Field(
        default_factory=list, description="Linked holders."
    )
    linkedAccounts: list[SchwabLinkedAccount] = Field(
        default_factory=list, description="Linked sub-accounts."
    )
