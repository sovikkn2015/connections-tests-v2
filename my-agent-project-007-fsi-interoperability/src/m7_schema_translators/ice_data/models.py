"""ICE Data vendor payload models."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class IceSecurityProfile(BaseModel):
    """One ICE Consolidated Feed reference-data row."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    symbol: str = Field(description="ICE canonical symbol e.g. 'IBM.N'.")
    long_name: str
    asset_type: str = Field(
        description=(
            "ICE asset-type code: STOCK, ETF, BOND, MUNI_BOND, GOVT_BOND, "
            "MUTUAL_FUND, OPTION, FUTURE, COMMODITY, INDEX, PREFERRED, REIT."
        )
    )
    cusip: Optional[str] = None
    isin: Optional[str] = None
    figi: Optional[str] = None
    sedol: Optional[str] = None
    primary_exchange: Optional[str] = Field(default=None, alias="exchange")
    gics_sector: Optional[str] = Field(default=None, alias="sector")
    gics_industry: Optional[str] = Field(default=None, alias="industry")
    market_cap: Optional[float] = Field(default=None, ge=0)
    pe_ratio: Optional[float] = None
    eps: Optional[float] = None
    dividend_yield: Optional[float] = Field(default=None, ge=0)
    beta: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    avg_volume_30d: Optional[int] = Field(default=None, ge=0)
    shares_outstanding: Optional[int] = Field(default=None, ge=0)
    description: Optional[str] = None
    country: Optional[str] = None
    currency: str
    is_restricted: Optional[bool] = False
    restricted_since: Optional[datetime] = None
    mnpi_flag: Optional[bool] = False
    last_updated: datetime
    source_id: str = Field(description="ICE CF entitlement ID.")


class IceQuote(BaseModel):
    """One ICE Consolidated Feed quote snapshot."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    symbol: str
    security_source_id: str
    last_price: float = Field(alias="price")
    bid_price: Optional[float] = Field(default=None, alias="bid")
    ask_price: Optional[float] = Field(default=None, alias="ask")
    bid_size: Optional[int] = None
    ask_size: Optional[int] = None
    session_volume: Optional[int] = Field(default=None, alias="volume", ge=0)
    session_open: Optional[float] = Field(default=None, alias="open")
    session_high: Optional[float] = Field(default=None, alias="high")
    session_low: Optional[float] = Field(default=None, alias="low")
    prev_close: Optional[float] = Field(default=None, alias="previous_close")
    change: Optional[float] = None
    change_pct: Optional[float] = None
    vwap: Optional[float] = None
    as_of: datetime = Field(alias="as_of_timestamp")
    delayed: bool = Field(alias="is_delayed")
    delay_minutes: Optional[int] = Field(default=None, ge=0)
    market_status: Optional[str] = None
    currency: str


__all__ = ["IceSecurityProfile", "IceQuote"]
