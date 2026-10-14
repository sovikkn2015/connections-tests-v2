"""Round-trip tests for ICE Data M7 translators."""

from __future__ import annotations

import pytest

from m3_schema_registry import AssetClass, Quote, SecurityProfile

from m7_schema_translators import UnknownEnumValue
from m7_schema_translators.ice_data.quote import (
    from_canonical_quote,
    to_canonical_quote,
)
from m7_schema_translators.ice_data.security_profile import (
    from_canonical_security_profile,
    to_canonical_security_profile,
)


def _ice_refdata_payload() -> dict:
    return {
        "symbol": "IBM.N",
        "long_name": "International Business Machines",
        "asset_type": "STOCK",
        "cusip": "459200101",
        "isin": "US4592001014",
        "figi": "BBG000BLNNH6",
        "sedol": "2005973",
        "exchange": "NYSE",
        "sector": "Technology",
        "industry": "IT Services",
        "market_cap": 200_000_000_000.0,
        "pe_ratio": 22.1,
        "eps": 7.1,
        "dividend_yield": 0.035,
        "beta": 0.8,
        "high_52w": 228.00,
        "low_52w": 150.00,
        "avg_volume_30d": 5_000_000,
        "shares_outstanding": 910_000_000,
        "description": "Global tech services",
        "country": "US",
        "currency": "USD",
        "is_restricted": False,
        "restricted_since": None,
        "mnpi_flag": False,
        "last_updated": "2026-04-30T00:00:00Z",
        "source_id": "ICE-IBM-001",
    }


def _ice_quote_payload() -> dict:
    return {
        "symbol": "IBM.N",
        "security_source_id": "ICE-IBM-001",
        "price": 210.50,
        "bid": 210.45,
        "ask": 210.55,
        "bid_size": 100,
        "ask_size": 150,
        "volume": 2_500_000,
        "open": 209.00,
        "high": 212.00,
        "low": 208.50,
        "previous_close": 209.50,
        "change": 1.00,
        "change_pct": 0.477,
        "vwap": 210.10,
        "as_of_timestamp": "2026-04-30T15:30:00Z",
        "is_delayed": False,
        "delay_minutes": None,
        "market_status": "open",
        "currency": "USD",
    }


class TestIceDataSecurityProfileRoundtrip:
    def test_forward_produces_canonical(self) -> None:
        canonical, note = to_canonical_security_profile(_ice_refdata_payload())
        assert isinstance(canonical, SecurityProfile)
        assert canonical.ticker == "IBM.N"
        assert canonical.asset_class == AssetClass.EQUITY
        assert canonical.source_system == "ice_data"
        assert canonical.source_id == "ICE-IBM-001"
        assert note.vendor == "ice_data"
        assert note.canonical_type == "SecurityProfile"

    def test_roundtrip_preserves_identifiers(self) -> None:
        canonical, _ = to_canonical_security_profile(_ice_refdata_payload())
        vendor, _ = from_canonical_security_profile(canonical)
        assert vendor.symbol == "IBM.N"
        assert vendor.cusip == "459200101"
        assert vendor.currency == "USD"

    def test_bond_maps_to_fixed_income(self) -> None:
        payload = _ice_refdata_payload()
        payload["asset_type"] = "BOND"
        canonical, _ = to_canonical_security_profile(payload)
        assert canonical.asset_class == AssetClass.FIXED_INCOME

    def test_unknown_asset_type_fails_closed(self) -> None:
        payload = _ice_refdata_payload()
        payload["asset_type"] = "WARP_DRIVE"
        with pytest.raises(UnknownEnumValue):
            to_canonical_security_profile(payload)


class TestIceDataQuoteRoundtrip:
    def test_forward_produces_canonical(self) -> None:
        canonical, note = to_canonical_quote(_ice_quote_payload())
        assert isinstance(canonical, Quote)
        assert canonical.ticker == "IBM.N"
        assert canonical.price == 210.50
        assert canonical.is_delayed is False
        assert note.canonical_type == "Quote"

    def test_roundtrip_preserves_numbers(self) -> None:
        canonical, _ = to_canonical_quote(_ice_quote_payload())
        vendor, _ = from_canonical_quote(canonical)
        assert vendor.last_price == 210.50
        assert vendor.bid_price == 210.45
        assert vendor.ask_price == 210.55
