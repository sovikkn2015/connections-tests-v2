"""ICE Data → canonical Quote translator."""

from __future__ import annotations

from uuid import uuid5

from m3_schema_registry import Quote

from m7_schema_translators.ice_data.models import IceQuote
from m7_schema_translators.shared.namespaces import QUOTE_NS, SECURITY_NS
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


def to_canonical_quote(
    vendor_payload: dict,
) -> tuple[Quote, ReconciliationNote]:
    """Translate an ICE Data quote snapshot to M3 ``Quote``."""
    vendor = IceQuote(**vendor_payload)
    validate_vendor_id_chars(
        vendor.security_source_id,
        vendor="ice_data",
        canonical_type="Quote",
        field_path="security_source_id",
    )

    canonical_id = uuid5(
        QUOTE_NS,
        f"ice_data:{vendor.security_source_id}:{vendor.as_of.isoformat()}",
    )
    security_ref = uuid5(SECURITY_NS, f"ice_data:{vendor.security_source_id}")

    canonical = Quote(
        canonical_id=canonical_id,
        security_ref=security_ref,
        ticker=vendor.symbol,
        price=vendor.last_price,
        bid=vendor.bid_price,
        ask=vendor.ask_price,
        bid_size=vendor.bid_size,
        ask_size=vendor.ask_size,
        volume=vendor.session_volume,
        open=vendor.session_open,
        high=vendor.session_high,
        low=vendor.session_low,
        previous_close=vendor.prev_close,
        change=vendor.change,
        change_pct=vendor.change_pct,
        vwap=vendor.vwap,
        as_of_timestamp=vendor.as_of,
        is_delayed=vendor.delayed,
        delay_minutes=vendor.delay_minutes,
        market_status=vendor.market_status,
        currency=vendor.currency,
        source_system="ice_data",
        source_id=vendor.security_source_id,
    )
    note = ReconciliationNote(
        vendor="ice_data",
        canonical_type="Quote",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return canonical, note


def from_canonical_quote(
    canonical: Quote,
) -> tuple[IceQuote, ReconciliationNote]:
    """Reverse canonical ``Quote`` → ICE Data quote snapshot."""
    vendor_model = IceQuote(
        symbol=canonical.ticker,
        security_source_id=canonical.ticker,
        price=canonical.price,
        bid=canonical.bid,
        ask=canonical.ask,
        bid_size=canonical.bid_size,
        ask_size=canonical.ask_size,
        volume=canonical.volume,
        open=canonical.open,
        high=canonical.high,
        low=canonical.low,
        previous_close=canonical.previous_close,
        change=canonical.change,
        change_pct=canonical.change_pct,
        vwap=canonical.vwap,
        as_of_timestamp=canonical.as_of_timestamp,
        is_delayed=canonical.is_delayed,
        delay_minutes=canonical.delay_minutes,
        market_status=canonical.market_status,
        currency=canonical.currency,
    )
    note = ReconciliationNote(
        vendor="ice_data",
        canonical_type="Quote",
        direction="from_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note


__all__ = [
    "SCHEMA_VERSION",
    "VENDOR_API_VERSION",
    "to_canonical_quote",
    "from_canonical_quote",
]
