"""Pydantic-input validation for Bloomberg refdata tools.

Covers Rule 32 (inputs validated, ``extra="forbid"``) + every invariant
documented in spec §4.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from m11_blpapi_adapters.bloomberg_refdata.src.models import (
    CorporateActionsInput,
    HistoricalDataInput,
    IntradayTickInput,
    ReferenceDataInput,
    SecurityRef,
)


# ---------------------------------------------------------------------------
# SecurityRef
# ---------------------------------------------------------------------------


def test_security_ref_isin_valid() -> None:
    s = SecurityRef(identifier_type="ISIN", value="US0378331005")
    assert s.value == "US0378331005"


def test_security_ref_isin_wrong_length_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityRef(identifier_type="ISIN", value="US03783310")


def test_security_ref_cusip_valid() -> None:
    s = SecurityRef(identifier_type="CUSIP", value="037833100")
    assert s.value == "037833100"


def test_security_ref_cusip_wrong_length_rejected() -> None:
    with pytest.raises(ValidationError):
        SecurityRef(identifier_type="CUSIP", value="03783310")


def test_security_ref_ticker_allows_spaces() -> None:
    s = SecurityRef(identifier_type="TICKER", value="AAPL US Equity")
    assert s.value == "AAPL US Equity"


def test_security_ref_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        SecurityRef(identifier_type="ISIN", value="US0378331005", extra="x")  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# ReferenceDataInput
# ---------------------------------------------------------------------------


def _aapl() -> SecurityRef:
    return SecurityRef(identifier_type="TICKER", value="AAPL US Equity")


def test_reference_data_happy_path() -> None:
    inp = ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST", "MKT_CAP"])
    assert len(inp.securities) == 1
    assert inp.fields == ["PX_LAST", "MKT_CAP"]


def test_reference_data_extra_field_rejected() -> None:
    with pytest.raises(ValidationError):
        ReferenceDataInput(securities=[_aapl()], fields=["PX_LAST"], fizz="buzz")  # type: ignore[call-arg]


def test_reference_data_rejects_empty_securities() -> None:
    with pytest.raises(ValidationError):
        ReferenceDataInput(securities=[], fields=["PX_LAST"])


def test_reference_data_rejects_lowercase_field() -> None:
    with pytest.raises(ValidationError):
        ReferenceDataInput(securities=[_aapl()], fields=["px_last"])


def test_reference_data_rejects_illegal_field_char() -> None:
    with pytest.raises(ValidationError):
        ReferenceDataInput(securities=[_aapl()], fields=["PX-LAST"])


def test_reference_data_rejects_too_many_securities() -> None:
    many = [_aapl()] * 201
    with pytest.raises(ValidationError):
        ReferenceDataInput(securities=many, fields=["PX_LAST"])


# ---------------------------------------------------------------------------
# HistoricalDataInput
# ---------------------------------------------------------------------------


def test_historical_data_happy_path() -> None:
    inp = HistoricalDataInput(
        securities=[_aapl()],
        fields=["PX_LAST", "VOLUME"],
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
        periodicity="DAILY",
    )
    assert inp.periodicity == "DAILY"


def test_historical_data_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        HistoricalDataInput(
            securities=[_aapl()],
            fields=["PX_LAST"],
            start_date=date(2024, 1, 1),
            end_date=date(2023, 1, 1),
        )


def test_historical_data_rejects_over_10y_window() -> None:
    with pytest.raises(ValidationError):
        HistoricalDataInput(
            securities=[_aapl()],
            fields=["PX_LAST"],
            start_date=date(2000, 1, 1),
            end_date=date(2020, 1, 2),  # 20y+
        )


def test_historical_data_accepts_split_adjustment_flags() -> None:
    inp = HistoricalDataInput(
        securities=[_aapl()],
        fields=["PX_LAST"],
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
        adjustment_split=True,
        adjustment_normal=True,
    )
    assert inp.adjustment_split is True
    assert inp.adjustment_normal is True


# ---------------------------------------------------------------------------
# IntradayTickInput
# ---------------------------------------------------------------------------


def test_intraday_tick_happy_path() -> None:
    inp = IntradayTickInput(
        security=_aapl(),
        event_types=["TRADE", "BID"],
        start_datetime=datetime(2026, 5, 20, 13, 30, tzinfo=timezone.utc),
        end_datetime=datetime(2026, 5, 20, 14, 30, tzinfo=timezone.utc),
    )
    assert inp.event_types == ["TRADE", "BID"]


def test_intraday_tick_rejects_inverted_window() -> None:
    with pytest.raises(ValidationError):
        IntradayTickInput(
            security=_aapl(),
            event_types=["TRADE"],
            start_datetime=datetime(2026, 5, 20, 14, 0, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 5, 20, 13, 0, tzinfo=timezone.utc),
        )


def test_intraday_tick_rejects_over_140d_window() -> None:
    with pytest.raises(ValidationError):
        IntradayTickInput(
            security=_aapl(),
            event_types=["TRADE"],
            start_datetime=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 8, 1, tzinfo=timezone.utc),  # > 140d
        )


def test_intraday_tick_accepts_naive_datetime() -> None:
    # Naive datetimes are coerced to UTC in the validator.
    inp = IntradayTickInput(
        security=_aapl(),
        event_types=["TRADE"],
        start_datetime=datetime(2026, 5, 20, 13, 30),
        end_datetime=datetime(2026, 5, 20, 14, 30),
    )
    assert inp.security.value == "AAPL US Equity"


def test_intraday_tick_rejects_invalid_event_type() -> None:
    with pytest.raises(ValidationError):
        IntradayTickInput(
            security=_aapl(),
            event_types=["TRADE", "FOO"],  # type: ignore[list-item]
            start_datetime=datetime(2026, 5, 20, 13, 30, tzinfo=timezone.utc),
            end_datetime=datetime(2026, 5, 20, 14, 30, tzinfo=timezone.utc),
        )


# ---------------------------------------------------------------------------
# CorporateActionsInput
# ---------------------------------------------------------------------------


def test_corporate_actions_happy_path() -> None:
    inp = CorporateActionsInput(
        securities=[_aapl()],
        action_types=["DVD_CASH", "SPLIT"],
        start_date=date(2020, 1, 1),
        end_date=date(2024, 12, 31),
    )
    assert inp.action_types == ["DVD_CASH", "SPLIT"]


def test_corporate_actions_rejects_inverted_range() -> None:
    with pytest.raises(ValidationError):
        CorporateActionsInput(
            securities=[_aapl()],
            action_types=["DVD_CASH"],
            start_date=date(2025, 1, 1),
            end_date=date(2020, 1, 1),
        )


def test_corporate_actions_rejects_unknown_action_type() -> None:
    with pytest.raises(ValidationError):
        CorporateActionsInput(
            securities=[_aapl()],
            action_types=["MERGER"],  # type: ignore[list-item]
            start_date=date(2020, 1, 1),
            end_date=date(2023, 1, 1),
        )
