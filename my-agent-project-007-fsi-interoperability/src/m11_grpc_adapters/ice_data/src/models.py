"""Pydantic input models for ICE Data tools."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from typing_extensions import Self


class IceSecurityRef(BaseModel):
    """ICE-identified security.

    Identifier types: SYMBOL (listed exchange symbol), ISIN, CUSIP, or the
    ICE-native OpaqueID. Format validation is lenient since ICE supports more
    identifier surfaces than Bloomberg.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier_type: Literal["SYMBOL", "ISIN", "CUSIP", "ICE_OPAQUE_ID"]
    value: str = Field(min_length=1, max_length=64)
    venue: str | None = Field(default=None, max_length=16)

    @model_validator(mode="after")
    def _check(self) -> Self:
        if self.identifier_type == "ISIN" and (len(self.value) != 12 or not self.value.isalnum()):
            raise ValueError("ISIN must be 12 alphanumeric chars")
        if self.identifier_type == "CUSIP" and (len(self.value) != 9 or not self.value.isalnum()):
            raise ValueError("CUSIP must be 9 alphanumeric chars")
        if self.identifier_type == "SYMBOL" and not any(c.isalnum() for c in self.value):
            raise ValueError("SYMBOL must contain at least one alphanumeric char")
        if self.venue is not None and not self.venue:
            raise ValueError("venue cannot be empty when provided")
        return self


class MarketDataSnapshotInput(BaseModel):
    """Current NBBO snapshot for N securities."""

    model_config = ConfigDict(extra="forbid")

    securities: list[IceSecurityRef] = Field(min_length=1, max_length=100)
    include_depth: bool = False


class TradeTapeInput(BaseModel):
    """Historical trade ticks for a single security within a time window."""

    model_config = ConfigDict(extra="forbid")

    security: IceSecurityRef
    start_time: datetime
    end_time: datetime
    max_ticks: int = Field(default=10_000, ge=1, le=100_000)

    @model_validator(mode="after")
    def _window(self) -> Self:
        start = self.start_time
        end = self.end_time
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end <= start:
            raise ValueError("end_time must be > start_time")
        if (end - start).total_seconds() > 30 * 86_400:
            raise ValueError("window exceeds 30-day retention ceiling")
        return self


class IceReferenceDataInput(BaseModel):
    """Security master for up to 500 securities."""

    model_config = ConfigDict(extra="forbid")

    securities: list[IceSecurityRef] = Field(min_length=1, max_length=500)
    as_of_date: date | None = None
