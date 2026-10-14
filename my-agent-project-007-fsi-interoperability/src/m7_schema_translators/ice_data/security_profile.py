"""ICE Data → canonical SecurityProfile translator."""

from __future__ import annotations

from types import MappingProxyType
from uuid import uuid5

from m3_schema_registry import AssetClass, SecurityProfile

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.ice_data.models import IceSecurityProfile
from m7_schema_translators.shared.namespaces import SECURITY_NS
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "ice-cf-v2"

LOSSY_FIELDS: frozenset[str] = frozenset()
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset()


_ASSET_TYPE_FWD: dict[str, AssetClass] = {
    "STOCK": AssetClass.EQUITY,
    "ETF": AssetClass.ETF,
    "BOND": AssetClass.FIXED_INCOME,
    "MUNI_BOND": AssetClass.FIXED_INCOME,
    "GOVT_BOND": AssetClass.FIXED_INCOME,
    "MUTUAL_FUND": AssetClass.MUTUAL_FUND,
    "OPTION": AssetClass.OPTION,
    "FUTURE": AssetClass.FUTURE,
    "COMMODITY": AssetClass.COMMODITY,
    "INDEX": AssetClass.ETF,
    "PREFERRED": AssetClass.PREFERRED_STOCK,
    "REIT": AssetClass.REIT,
}

_ASSET_TYPE_REV: dict[AssetClass, str] = {
    AssetClass.EQUITY: "STOCK",
    AssetClass.ETF: "ETF",
    AssetClass.FIXED_INCOME: "BOND",
    AssetClass.MUTUAL_FUND: "MUTUAL_FUND",
    AssetClass.OPTION: "OPTION",
    AssetClass.FUTURE: "FUTURE",
    AssetClass.COMMODITY: "COMMODITY",
    AssetClass.PREFERRED_STOCK: "PREFERRED",
    AssetClass.REIT: "REIT",
    AssetClass.ALTERNATIVE: "STOCK",
    AssetClass.MONEY_MARKET: "BOND",
    AssetClass.CRYPTO: "COMMODITY",
}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"asset_type": MappingProxyType(_ASSET_TYPE_FWD)}
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"asset_type": MappingProxyType(_ASSET_TYPE_REV)}
)


def _map_asset_type(v: str) -> AssetClass:
    mapping = ENUM_MAPPINGS["asset_type"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="ice_data",
            canonical_type="SecurityProfile",
            field_path="asset_type",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_security_profile(
    vendor_payload: dict,
) -> tuple[SecurityProfile, ReconciliationNote]:
    """Translate ICE Data reference-data row to M3 ``SecurityProfile``."""
    vendor = IceSecurityProfile(**vendor_payload)
    validate_vendor_id_chars(
        vendor.source_id,
        vendor="ice_data",
        canonical_type="SecurityProfile",
        field_path="source_id",
    )

    canonical_id = uuid5(SECURITY_NS, f"ice_data:{vendor.source_id}")
    asset_class = _map_asset_type(vendor.asset_type)

    restricted_since = (
        vendor.restricted_since.date() if vendor.restricted_since else None
    )

    canonical = SecurityProfile(
        canonical_id=canonical_id,
        ticker=vendor.symbol,
        security_name=vendor.long_name,
        asset_class=asset_class,
        cusip=vendor.cusip,
        isin=vendor.isin,
        figi=vendor.figi,
        sedol=vendor.sedol,
        bloomberg_id=None,
        exchange=vendor.primary_exchange,
        sector=vendor.gics_sector,
        industry=vendor.gics_industry,
        market_cap=vendor.market_cap,
        pe_ratio=vendor.pe_ratio,
        eps=vendor.eps,
        dividend_yield=vendor.dividend_yield,
        beta=vendor.beta,
        fifty_two_week_high=vendor.high_52w,
        fifty_two_week_low=vendor.low_52w,
        avg_volume_30d=vendor.avg_volume_30d,
        shares_outstanding=vendor.shares_outstanding,
        description=vendor.description,
        country=vendor.country,
        currency=vendor.currency,
        is_restricted=bool(vendor.is_restricted),
        restricted_since=restricted_since,
        mnpi_flag=bool(vendor.mnpi_flag),
        last_updated=vendor.last_updated,
        source_system="ice_data",
        source_id=vendor.source_id,
    )
    note = ReconciliationNote(
        vendor="ice_data",
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
) -> tuple[IceSecurityProfile, ReconciliationNote]:
    """Reverse canonical ``SecurityProfile`` → ICE Data row."""
    ice_asset_type = REVERSE_ENUM_MAPPINGS["asset_type"].get(
        canonical.asset_class, "STOCK"
    )

    restricted_since_dt = None
    if canonical.restricted_since is not None:
        from datetime import datetime as _dt, time as _t, timezone as _tz
        restricted_since_dt = _dt.combine(
            canonical.restricted_since, _t.min, tzinfo=_tz.utc
        )

    vendor_model = IceSecurityProfile(
        symbol=canonical.ticker,
        long_name=canonical.security_name,
        asset_type=ice_asset_type,
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
        high_52w=canonical.fifty_two_week_high,
        low_52w=canonical.fifty_two_week_low,
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
        vendor="ice_data",
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
