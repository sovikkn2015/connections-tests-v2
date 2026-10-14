"""Pydantic input models for Bloomberg refdata tools.

Every model uses ``extra="forbid"`` (Rule 32) and explicit range bounds.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from typing_extensions import Self


_IDENT_TYPES = ("ISIN", "CUSIP", "TICKER")


class SecurityRef(BaseModel):
    """Security identifier.

    ``identifier_type`` constrains the ``value`` format:
    * ``ISIN`` — 12 chars, alphanumeric (ISO 6166).
    * ``CUSIP`` — 9 chars, alphanumeric.
    * ``TICKER`` — Bloomberg-style (``"AAPL US Equity"``); ≤ 64 chars.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    identifier_type: Literal["ISIN", "CUSIP", "TICKER"]
    value: str = Field(min_length=1, max_length=64)

    @model_validator(mode="after")
    def _check_identifier(self) -> Self:
        v = self.value
        if self.identifier_type == "ISIN":
            if len(v) != 12 or not v.isalnum():
                raise ValueError("ISIN must be 12 alphanumeric chars")
        elif self.identifier_type == "CUSIP":
            if len(v) != 9 or not v.isalnum():
                raise ValueError("CUSIP must be 9 alphanumeric chars")
        elif self.identifier_type == "TICKER":
            if not any(c.isalnum() for c in v):
                raise ValueError("TICKER must contain at least one alphanumeric char")
        return self


_FIELD_RX_MAX = 32
_FIELD_MIN_LEN = 1


def _validate_fields(fields: list[str]) -> list[str]:
    # Bloomberg vendor field names are ASCII, upper-case, digits, underscore.
    for f in fields:
        if not f or len(f) > _FIELD_RX_MAX:
            raise ValueError(f"field name invalid length: {f!r}")
        if not all(c.isalnum() or c == "_" for c in f):
            raise ValueError(f"field name contains illegal char: {f!r}")
        if f != f.upper():
            raise ValueError(f"field name must be upper-case: {f!r}")
    return fields


class ReferenceDataInput(BaseModel):
    """Input for ``bloomberg.reference_data`` — static fields for N securities."""

    model_config = ConfigDict(extra="forbid")

    securities: list[SecurityRef] = Field(min_length=1, max_length=200)
    fields: list[str] = Field(min_length=1, max_length=50)

    @field_validator("fields")
    @classmethod
    def _fields_shape(cls, v: list[str]) -> list[str]:
        return _validate_fields(v)


class HistoricalDataInput(BaseModel):
    """Input for ``bloomberg.historical_data`` — daily / weekly / monthly series."""

    model_config = ConfigDict(extra="forbid")

    securities: list[SecurityRef] = Field(min_length=1, max_length=50)
    fields: list[str] = Field(min_length=1, max_length=25)
    start_date: date
    end_date: date
    periodicity: Literal["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"] = "DAILY"
    adjustment_normal: bool = False
    adjustment_abnormal: bool = False
    adjustment_split: bool = False

    @field_validator("fields")
    @classmethod
    def _fields_shape(cls, v: list[str]) -> list[str]:
        return _validate_fields(v)

    @model_validator(mode="after")
    def _date_window(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        span = (self.end_date - self.start_date).days
        if span > 10 * 365:
            raise ValueError("date window exceeds 10-year ceiling")
        return self


class IntradayTickInput(BaseModel):
    """Input for ``bloomberg.intraday_tick``."""

    model_config = ConfigDict(extra="forbid")

    security: SecurityRef
    event_types: list[Literal["TRADE", "BID", "ASK", "BEST_BID", "BEST_ASK"]] = Field(
        min_length=1, max_length=5
    )
    start_datetime: datetime
    end_datetime: datetime
    include_condition_codes: bool = False

    @model_validator(mode="after")
    def _window(self) -> Self:
        # Accept naive / tz-aware and coerce to UTC for comparison.
        start = self.start_datetime
        end = self.end_datetime
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        if end <= start:
            raise ValueError("end_datetime must be > start_datetime")
        if (end - start).total_seconds() > 140 * 86_400:
            raise ValueError("intraday window exceeds 140-day archive ceiling")
        return self


class CorporateActionsInput(BaseModel):
    """Input for ``bloomberg.corporate_actions``."""

    model_config = ConfigDict(extra="forbid")

    securities: list[SecurityRef] = Field(min_length=1, max_length=50)
    action_types: list[Literal["DVD_CASH", "DVD_STOCK", "SPLIT", "RIGHTS"]] = Field(
        min_length=1, max_length=4
    )
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def _dates(self) -> Self:
        if self.end_date < self.start_date:
            raise ValueError("end_date must be >= start_date")
        return self
