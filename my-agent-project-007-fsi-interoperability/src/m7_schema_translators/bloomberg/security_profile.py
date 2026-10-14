"""Bloomberg → canonical SecurityProfile translator.

Bloomberg asset-class codes are mapped to M3 :class:`AssetClass`. Unknown
values raise :class:`UnknownEnumValue`. Restricted / MNPI flags flow
through unchanged so M2 / M4 can honour them.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import uuid5

from m3_schema_registry import AssetClass, SecurityProfile

from m7_schema_translators.bloomberg.models import BloombergRefData
from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.shared.namespaces import SECURITY_NS
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "blpapi-3.25"

LOSSY_FIELDS: frozenset[str] = frozenset()
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {"bloomberg_bsid_not_in_canonical"}
)

_ASSET_CLASS_FWD: dict[str, AssetClass] = {
    "Equity": AssetClass.EQUITY,
    "Corp": AssetClass.FIXED_INCOME,
    "Govt": AssetClass.FIXED_INCOME,
    "Muni": AssetClass.FIXED_INCOME,
    "Mtge": AssetClass.FIXED_INCOME,
    "Pfd": AssetClass.PREFERRED_STOCK,
    "Comdty": AssetClass.COMMODITY,
    "Index": AssetClass.ETF,
    "Curncy": AssetClass.MONEY_MARKET,
    "Alt": AssetClass.ALTERNATIVE,
    "Fund": AssetClass.MUTUAL_FUND,
    "ETF": AssetClass.ETF,
    "REIT": AssetClass.REIT,
}

_ASSET_CLASS_REV: dict[AssetClass, str] = {
    AssetClass.EQUITY: "Equity",
    AssetClass.FIXED_INCOME: "Corp",
    AssetClass.PREFERRED_STOCK: "Pfd",
    AssetClass.COMMODITY: "Comdty",
    AssetClass.ETF: "ETF",
    AssetClass.MONEY_MARKET: "Curncy",
    AssetClass.ALTERNATIVE: "Alt",
    AssetClass.MUTUAL_FUND: "Fund",
    AssetClass.REIT: "REIT",
    AssetClass.OPTION: "Equity",
    AssetClass.FUTURE: "Comdty",
    AssetClass.CRYPTO: "Alt",
}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"asset_class": MappingProxyType(_ASSET_CLASS_FWD)}
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"asset_class": MappingProxyType(_ASSET_CLASS_REV)}
)


def _map_asset_class(v: str) -> AssetClass:
    mapping = ENUM_MAPPINGS["asset_class"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="bloomberg",
            canonical_type="SecurityProfile",
            field_path="asset_class",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_security_profile(
    vendor_payload: dict,
) -> tuple[SecurityProfile, ReconciliationNote]:
    """Translate a Bloomberg reference-data row to M3 ``SecurityProfile``."""
    vendor = BloombergRefData(**vendor_payload)
    validate_vendor_id_chars(
        vendor.source_id,
        vendor="bloomberg",
        canonical_type="SecurityProfile",
        field_path="source_id",
    )

    canonical_id = uuid5(SECURITY_NS, f"bloomberg:{vendor.source_id}")
    asset_class = _map_asset_class(vendor.asset_class)

    # `restricted_since` in vendor payload is a full datetime; M3 field is
    # date-only.
    restricted_since = None
    if vendor.restricted_since is not None:
        restricted_since = vendor.restricted_since.date()

    canonical = SecurityProfile(
        canonical_id=canonical_id,
        ticker=vendor.ticker,
        security_name=vendor.name,
        asset_class=asset_class,
        cusip=vendor.cusip,
        isin=vendor.isin,
        figi=vendor.figi,
        sedol=vendor.sedol,
        bloomberg_id=vendor.ticker,  # Bloomberg ticker IS the Bloomberg ID.
        exchange=vendor.exchange,
        sector=vendor.sector,
        industry=vendor.industry,
        market_cap=vendor.market_cap,
        pe_ratio=vendor.pe_ratio,
        eps=vendor.eps,
        dividend_yield=vendor.dividend_yield,
        beta=vendor.beta,
        fifty_two_week_high=vendor.fifty_two_week_high,
        fifty_two_week_low=vendor.fifty_two_week_low,
        avg_volume_30d=vendor.avg_volume_30d,
        shares_outstanding=vendor.shares_outstanding,
        description=vendor.description,
        country=vendor.country,
        currency=vendor.currency,
        is_restricted=bool(vendor.is_restricted),
        restricted_since=restricted_since,
        mnpi_flag=bool(vendor.mnpi_flag),
        last_updated=vendor.last_updated,
        source_system="bloomberg",
        source_id=vendor.source_id,
    )
    note = ReconciliationNote(
        vendor="bloomberg",
        canonical_type="SecurityProfile",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return canonical, note


def from_canonical_security_profile(
    canonical: SecurityProfile,
) -> tuple[BloombergRefData, ReconciliationNote]:
    """Reverse canonical ``SecurityProfile`` → Bloomberg vendor row."""
    bloomberg_asset_class = REVERSE_ENUM_MAPPINGS["asset_class"].get(
        canonical.asset_class, "Equity"
    )

    # Vendor requires datetime; M3 stores date. Promote to UTC midnight.
    restricted_since_dt = None
    if canonical.restricted_since is not None:
        from datetime import datetime as _dt, time as _t, timezone as _tz
        restricted_since_dt = _dt.combine(
            canonical.restricted_since, _t.min, tzinfo=_tz.utc
        )

    vendor_model = BloombergRefData(
        ticker=canonical.ticker,
        name=canonical.security_name,
        asset_class=bloomberg_asset_class,
        cusip=canonical.cusip,
        isin=canonical.isin,
        figi=canonical.figi,
        sedol=canonical.sedol,
        exchange=canonical.exchange,
        sector=canonical.sector,
        industry=canonical.industry,
        market_cap=canonical.market_cap,
        pe_ratio=canonical.pe_ratio,
        eps=canonical.eps,
        dividend_yield=canonical.dividend_yield,
        beta=canonical.beta,
        **{
            "52w_high": canonical.fifty_two_week_high,
            "52w_low": canonical.fifty_two_week_low,
        },
        avg_volume_30d=canonical.avg_volume_30d,
        shares_outstanding=canonical.shares_outstanding,
        description=canonical.description,
        country=canonical.country,
        currency=canonical.currency,
        is_restricted=bool(canonical.is_restricted),
        restricted_since=restricted_since_dt,
        mnpi_flag=bool(canonical.mnpi_flag),
        last_updated=canonical.last_updated,
        source_id=canonical.source_id,
    )
    note = ReconciliationNote(
        vendor="bloomberg",
        canonical_type="SecurityProfile",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note


__all__ = [
    "SCHEMA_VERSION",
    "VENDOR_API_VERSION",
    "ENUM_MAPPINGS",
    "REVERSE_ENUM_MAPPINGS",
    "to_canonical_security_profile",
    "from_canonical_security_profile",
]
