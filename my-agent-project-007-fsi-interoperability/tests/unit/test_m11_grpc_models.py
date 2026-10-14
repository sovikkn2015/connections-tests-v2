"""Pydantic input-model tests for ICE Data tools."""

from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from m11_grpc_adapters.ice_data.src.models import (
    IceReferenceDataInput,
    IceSecurityRef,
    MarketDataSnapshotInput,
    TradeTapeInput,
)


def _sec() -> IceSecurityRef:
    return IceSecurityRef(identifier_type="SYMBOL", value="SPY", venue="ARCA")


def test_security_ref_symbol_happy() -> None:
    s = IceSecurityRef(identifier_type="SYMBOL", value="SPY")
    assert s.value == "SPY"
    assert s.venue is None


def test_security_ref_isin_wrong_length_rejected() -> None:
    with pytest.raises(ValidationError):
        IceSecurityRef(identifier_type="ISIN", value="BADISIN")


def test_security_ref_cusip_wrong_length_rejected() -> None:
    with pytest.raises(ValidationError):
        IceSecurityRef(identifier_type="CUSIP", value="12345")


def test_security_ref_extras_rejected() -> None:
    with pytest.raises(ValidationError):
        IceSecurityRef(identifier_type="SYMBOL", value="SPY", foo="bar")  # type: ignore[call-arg]


def test_security_ref_rejects_empty_venue() -> None:
    with pytest.raises(ValidationError):
        IceSecurityRef(identifier_type="SYMBOL", value="SPY", venue="")


def test_market_data_snapshot_happy() -> None:
    inp = MarketDataSnapshotInput(securities=[_sec()], include_depth=True)
    assert len(inp.securities) == 1
    assert inp.include_depth is True


def test_market_data_snapshot_rejects_empty_list() -> None:
    with pytest.raises(ValidationError):
        MarketDataSnapshotInput(securities=[])


def test_market_data_snapshot_rejects_over_100() -> None:
    with pytest.raises(ValidationError):
        MarketDataSnapshotInput(securities=[_sec()] * 101)


def test_trade_tape_happy() -> None:
    inp = TradeTapeInput(
        security=_sec(),
        start_time=datetime(2026, 5, 20, 13, 30, tzinfo=timezone.utc),
        end_time=datetime(2026, 5, 20, 20, 0, tzinfo=timezone.utc),
        max_ticks=5000,
    )
    assert inp.max_ticks == 5000


def test_trade_tape_rejects_inverted_window() -> None:
    with pytest.raises(ValidationError):
        TradeTapeInput(
            security=_sec(),
            start_time=datetime(2026, 5, 20, 20, 0, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 20, 13, 30, tzinfo=timezone.utc),
        )


def test_trade_tape_rejects_over_30d_window() -> None:
    with pytest.raises(ValidationError):
        TradeTapeInput(
            security=_sec(),
            start_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
            end_time=datetime(2026, 3, 1, tzinfo=timezone.utc),
        )


def test_trade_tape_max_ticks_bounds() -> None:
    with pytest.raises(ValidationError):
        TradeTapeInput(
            security=_sec(),
            start_time=datetime(2026, 5, 20, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 21, tzinfo=timezone.utc),
            max_ticks=0,
        )
    with pytest.raises(ValidationError):
        TradeTapeInput(
            security=_sec(),
            start_time=datetime(2026, 5, 20, tzinfo=timezone.utc),
            end_time=datetime(2026, 5, 21, tzinfo=timezone.utc),
            max_ticks=1_000_000,
        )


def test_reference_data_happy() -> None:
    inp = IceReferenceDataInput(securities=[_sec()], as_of_date=date(2026, 5, 20))
    assert inp.as_of_date == date(2026, 5, 20)


def test_reference_data_rejects_over_500() -> None:
    with pytest.raises(ValidationError):
        IceReferenceDataInput(securities=[_sec()] * 501)


def test_reference_data_as_of_optional() -> None:
    inp = IceReferenceDataInput(securities=[_sec()])
    assert inp.as_of_date is None
