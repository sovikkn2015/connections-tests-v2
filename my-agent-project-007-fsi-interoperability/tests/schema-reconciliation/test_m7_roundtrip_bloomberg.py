"""Round-trip tests for Bloomberg M7 translators.

Covers SecurityProfile + Quote. Exercises enum mapping + asset-class
coverage for the 13 Bloomberg codes.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from m3_schema_registry import AssetClass, Quote, SecurityProfile

from m7_schema_translators import UnknownEnumValue
from m7_schema_translators.bloomberg.quote import (
    from_canonical_quote,
    to_canonical_quote,
)
from m7_schema_translators.bloomberg.security_profile import (
    from_canonical_security_profile,
    to_canonical_security_profile,
)


def _bloomberg_refdata_payload() -> dict:
    return {
        "ticker": "AAPL US Equity",
        "name": "Apple Inc",
        "asset_class": "Equity",
        "cusip": "037833100",
        "isin": "US0378331005",
        "figi": "BBG000B9XRY4",
        "sedol": "2046251",
        "exchange": "UN",
        "sector": "Information Technology",
        "industry": "Technology Hardware",
        "market_cap": 3_000_000_000_000.0,
        "pe_ratio": 29.5,
        "eps": 6.05,
        "dividend_yield": 0.005,
        "beta": 1.15,
        "52w_high": 237.49,
        "52w_low": 164.08,
        "avg_volume_30d": 52_000_000,
        "shares_outstanding": 15_500_000_000,
        "description": "Consumer electronics and services.",
        "country": "US",
        "currency": "USD",
        "is_restricted": False,
        "restricted_since": None,
        "mnpi_flag": False,
        "last_updated": "2026-04-30T00:00:00Z",
        "source_id": "BBG-AAPL-001",
    }


def _bloomberg_quote_payload() -> dict:
    return {
        "ticker": "AAPL US Equity",
        "security_bsid": "BBG-AAPL-001",
        "price": 225.10,
        "bid": 225.09,
        "ask": 225.11,
        "bid_size": 200,
        "ask_size": 300,
        "volume": 42_000_000,
        "open": 224.00,
        "high": 226.50,
        "low": 223.80,
        "previous_close": 224.50,
        "change": 0.60,
        "change_pct": 0.267,
        "vwap": 225.00,
        "as_of_timestamp": "2026-04-30T15:30:00Z",
        "is_delayed": False,
        "delay_minutes": None,
        "market_status": "open",
        "currency": "USD",
    }


class TestBloombergSecurityProfileRoundtrip:
    def test_forward_produces_canonical(self) -> None:
        canonical, note = to_canonical_security_profile(
            _bloomberg_refdata_payload()
        )
        assert isinstance(canonical, SecurityProfile)
        assert canonical.ticker == "AAPL US Equity"
        assert canonical.asset_class == AssetClass.EQUITY
        assert canonical.bloomberg_id == "AAPL US Equity"
        assert canonical.source_system == "bloomberg"
        assert canonical.source_id == "BBG-AAPL-001"
        assert note.direction == "to_canonical"
        assert note.vendor == "bloomberg"
        assert note.canonical_type == "SecurityProfile"

    def test_roundtrip_preserves_round_trippable_fields(self) -> None:
        canonical, _ = to_canonical_security_profile(
            _bloomberg_refdata_payload()
        )
        vendor, note = from_canonical_security_profile(canonical)
        assert vendor.ticker == "AAPL US Equity"
        assert vendor.name == "Apple Inc"
        assert vendor.asset_class == "Equity"
        assert vendor.cusip == "037833100"
        assert vendor.currency == "USD"
        assert note.direction == "from_canonical"

    def test_unknown_asset_class_fails_closed(self) -> None:
        payload = _bloomberg_refdata_payload()
        payload["asset_class"] = "not_a_real_class"
        with pytest.raises(UnknownEnumValue) as exc:
            to_canonical_security_profile(payload)
        assert exc.value.reason_code == "unknown_enum_value"
        assert exc.value.field_path == "asset_class"

    def test_restricted_since_promotes_to_date(self) -> None:
        payload = _bloomberg_refdata_payload()
        payload["is_restricted"] = True
        payload["restricted_since"] = "2024-01-15T12:34:56Z"
        canonical, _ = to_canonical_security_profile(payload)
        assert canonical.is_restricted is True
        assert canonical.restricted_since.isoformat() == "2024-01-15"


class TestBloombergQuoteRoundtrip:
    def test_forward_produces_canonical(self) -> None:
        canonical, note = to_canonical_quote(_bloomberg_quote_payload())
        assert isinstance(canonical, Quote)
        assert canonical.ticker == "AAPL US Equity"
        assert canonical.price == 225.10
        assert canonical.is_delayed is False
        assert canonical.currency == "USD"
        assert note.direction == "to_canonical"
        assert note.canonical_type == "Quote"

    def test_roundtrip_preserves_numbers(self) -> None:
        canonical, _ = to_canonical_quote(_bloomberg_quote_payload())
        vendor, _ = from_canonical_quote(canonical)
        assert vendor.price == 225.10
        assert vendor.bid == 225.09
        assert vendor.ask == 225.11

    def test_delayed_quote_carries_delay_minutes(self) -> None:
        payload = _bloomberg_quote_payload()
        payload["is_delayed"] = True
        payload["delay_minutes"] = 15
        canonical, _ = to_canonical_quote(payload)
        assert canonical.is_delayed is True
        assert canonical.delay_minutes == 15
