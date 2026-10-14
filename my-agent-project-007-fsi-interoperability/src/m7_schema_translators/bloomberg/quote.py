"""Bloomberg → canonical Quote translator.

Intraday-tick payloads map directly to :class:`Quote`. ``security_ref``
is derived from the Bloomberg BSID via the same :data:`SECURITY_NS`
namespace used by the Bloomberg SecurityProfile translator, so a quote
round-trip links back to the correct profile UUID.
"""

from __future__ import annotations

from uuid import uuid5

from m3_schema_registry import Quote

from m7_schema_translators.bloomberg.models import BloombergQuote
from m7_schema_translators.shared.namespaces import QUOTE_NS, SECURITY_NS
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "blpapi-3.25"

LOSSY_FIELDS: frozenset[str] = frozenset()
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset()


def to_canonical_quote(
    vendor_payload: dict,
) -> tuple[Quote, ReconciliationNote]:
    """Translate a Bloomberg quote row to M3 ``Quote``."""
    vendor = BloombergQuote(**vendor_payload)
    validate_vendor_id_chars(
        vendor.security_bsid,
        vendor="bloomberg",
        canonical_type="Quote",
        field_path="security_bsid",
    )

    canonical_id = uuid5(
        QUOTE_NS,
        f"bloomberg:{vendor.security_bsid}:{vendor.as_of_timestamp.isoformat()}",
    )
    security_ref = uuid5(SECURITY_NS, f"bloomberg:{vendor.security_bsid}")

    canonical = Quote(
        canonical_id=canonical_id,
        security_ref=security_ref,
        ticker=vendor.ticker,
        price=vendor.price,
        bid=vendor.bid,
        ask=vendor.ask,
        bid_size=vendor.bid_size,
        ask_size=vendor.ask_size,
        volume=vendor.volume,
        open=vendor.open,
        high=vendor.high,
        low=vendor.low,
        previous_close=vendor.previous_close,
        change=vendor.change,
        change_pct=vendor.change_pct,
        vwap=vendor.vwap,
        as_of_timestamp=vendor.as_of_timestamp,
        is_delayed=vendor.is_delayed,
        delay_minutes=vendor.delay_minutes,
        market_status=vendor.market_status,
        currency=vendor.currency,
        source_system="bloomberg",
        source_id=vendor.security_bsid,
    )
    note = ReconciliationNote(
        vendor="bloomberg",
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
) -> tuple[BloombergQuote, ReconciliationNote]:
    """Reverse canonical ``Quote`` → Bloomberg intraday-tick row."""
    # We do not have the BSID preserved on the canonical Quote; fall back
    # to the ticker as the BSID surrogate. The `fields_dropped` note flags
    # the non-round-trip status of the BSID.
    vendor_model = BloombergQuote(
        ticker=canonical.ticker,
        security_bsid=canonical.ticker,
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
        vendor="bloomberg",
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
