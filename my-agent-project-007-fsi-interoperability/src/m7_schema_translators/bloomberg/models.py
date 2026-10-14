"""Bloomberg vendor payload models (input to translators).

Mirrors the BLPAPI ReferenceDataResponse shape the M11-BLPAPI adapter emits
via ``bloomberg.reference_data`` and ``bloomberg.intraday_tick`` tools.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class BloombergRefData(BaseModel):
    """One security's reference-data row."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str = Field(description="Bloomberg ticker, e.g. 'AAPL US Equity'.")
    name: str = Field(description="Security long name.")
    asset_class: str = Field(
        description=(
            "Bloomberg asset class code: Equity, Corp, Govt, Muni, Mtge, "
            "Pfd, Comdty, Index, Curncy, Alt."
        )
    )
    cusip: Optional[str] = None
    isin: Optional[str] = None
    figi: Optional[str] = None
    sedol: Optional[str] = None
    exchange: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    market_cap: Optional[float] = Field(default=None, ge=0)
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = Field(default=None, ge=0)
    beta: Optional[float] = None
    fifty_two_week_high: Optional[float] = Field(default=None, alias="52w_high")
    fifty_two_week_low: Optional[float] = Field(default=None, alias="52w_low")
    avg_volume_30d: Optional[int] = Field(default=None, ge=0)
    shares_outstanding: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None
    country: Optional[str] = None
    currency: str = Field(description="ISO 4217 currency code.")
    is_restricted: Optional[bool] = False
    restricted_since: Optional[datetime] = None
    mnpi_flag: Optional[bool] = False
    last_updated: datetime = Field(description="Last-update timestamp.")
    source_id: str = Field(
        description="Vendor's reference-data ID (BSID or similar)."
    )


class BloombergQuote(BaseModel):
    """One intraday tick / L1 quote row."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    ticker: str
    security_bsid: str = Field(
        description=(
            "Bloomberg security ID -- links back to the reference-data row "
            "via SecurityProfile.source_id."
        )
    )
    price: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    volume: Optional[int] = Field(default=None, ge=0)
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    previous_close: Optional[float] = None
    change: Optional[float] = None
    change_pct: Optional[float] = None
    vwap: Optional[float] = None
    as_of_timestamp: datetime
    is_delayed: bool = Field(
        description="True if the tenant's BLPAPI license is delayed."
    )
    delay_minutes: Optional[int] = Field(default=None, ge=0)
    market_status: Optional[str] = None
    currency: str


__all__ = ["BloombergRefData", "BloombergQuote"]
