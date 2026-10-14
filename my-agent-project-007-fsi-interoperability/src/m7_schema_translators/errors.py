"""
M7 Translation Errors.

Closed set of translation-failure reason codes plus one exception class per
failure category. Every `TranslationError` carries a per-subclass TypedDict
`details` with an allow-list of safe keys (AC4.8 + NI-2 fix).

NO PII. NO raw vendor payload. NO canonical model in `details` — the
`_format` method only renders an allow-listed subset of keys into the string
representation (NI-2 fix: do not blindly stringify `details.items()`).
"""

from __future__ import annotations

from typing import Any, Mapping, Optional, TypedDict

# =============================================================================
# VALID REASON CODES — closed set (AC4.3)
# =============================================================================

VALID_REASON_CODES: frozenset[str] = frozenset(
    {
        "unknown_enum_value",
        "missing_required_field",
        "type_coercion_failed",
        "vendor_id_invalid_chars",
        "cost_basis_unmappable",
        "unsupported_vendor_value",
        "ambiguous_mapping",
        "vendor_schema_version_mismatch",
        "round_trip_divergence",
        "unregistered_translator",
        "vendor_payload_validation_failed",
    }
)


# =============================================================================
# PER-SUBCLASS TypedDicts (AC4.8)
# =============================================================================


class UnknownEnumDetails(TypedDict):
    vendor_value: str
    valid_values: list[str]


class MissingRequiredDetails(TypedDict):
    field_name: str


class TypeCoercionDetails(TypedDict):
    expected_type: str
    got_type: str


class CostBasisUnmappableDetails(TypedDict):
    vendor_value: Optional[str]
    account_type_group: Optional[str]
    security_class: Optional[str]
    jurisdiction: Optional[str]


class VendorSchemaVersionMismatchDetails(TypedDict):
    observed_version: str
    min_supported: str
    max_supported: str


class RoundTripDivergenceDetails(TypedDict):
    field_path: str
    forward_hash: str
    roundtrip_hash: str


class UnregisteredTranslatorDetails(TypedDict):
    valid_source_systems: list[str]
    valid_canonical_types: list[str]


# =============================================================================
# SAFE-KEY ALLOW-LIST (NI-2 fix)
# =============================================================================

# Per AC14.2 + NI-2: only these keys may appear in the rendered string.
# Anything else in `details` is stored but NOT rendered. This prevents
# accidental PII leakage if a caller puts a PII value into `details`.
_SAFE_DETAIL_KEYS: frozenset[str] = frozenset(
    {
        "vendor_value",
        "valid_values",
        "field_name",
        "expected_type",
        "got_type",
        "account_type_group",
        "security_class",
        "jurisdiction",
        "observed_version",
        "min_supported",
        "max_supported",
        "field_path",
        "forward_hash",
        "roundtrip_hash",
        "valid_source_systems",
        "valid_canonical_types",
    }
)


# =============================================================================
# BASE EXCEPTION + 7 SUBCLASSES (AC4.1, AC4.2)
# =============================================================================


class TranslationError(Exception):
    """Base class for all M7 translation failures.

    Carries a `reason_code` (drawn from `VALID_REASON_CODES`), `vendor`,
    `canonical_type`, `field_path`, and a `details` TypedDict. All fields
    are sanitized in the string representation.
    """

    def __init__(
        self,
        *,
        reason_code: str,
        vendor: str,
        canonical_type: str,
        field_path: str,
        details: Mapping[str, Any],
    ) -> None:
        if reason_code not in VALID_REASON_CODES:
            raise ValueError(
                f"invalid reason_code {reason_code!r} (not in VALID_REASON_CODES)"
            )
        self.reason_code: str = reason_code
        self.vendor: str = vendor
        self.canonical_type: str = canonical_type
        self.field_path: str = field_path
        # store a shallow-copied plain dict — details is otherwise-read-only
        self.details: dict[str, Any] = dict(details)
        super().__init__(self._format())

    def _format(self) -> str:
        # NI-2 fix: only render allow-listed keys. Unknown keys are dropped
        # from the string to prevent PII leaks. Sort for determinism.
        safe_items: list[tuple[str, Any]] = sorted(
            (k, v) for k, v in self.details.items() if k in _SAFE_DETAIL_KEYS
        )
        summary = ", ".join(f"{k}={v}" for k, v in safe_items)
        return (
            f"[{self.reason_code}] "
            f"{self.vendor}.{self.canonical_type}.{self.field_path}"
            f": {summary}"
        )


class UnknownEnumValue(TranslationError):
    """Vendor returned an enum value not in the translator's ENUM_MAPPINGS."""


class MissingRequiredField(TranslationError):
    """Required vendor field is absent or empty."""


class TypeCoercionError(TranslationError):
    """Vendor value cannot be coerced to the expected canonical type."""


class CostBasisUnmappable(TranslationError):
    """TaxLot cost basis cannot be determined from vendor data + defaults.

    Per Steering Rule 16 / AC5.6: M7 NEVER falls back to a safe default.
    Unknown cost basis = regulatory risk = fail-closed.
    """


class VendorSchemaVersionMismatch(TranslationError):
    """Vendor payload schema version is outside supported window (Phase 3+)."""


class RoundTripDivergence(TranslationError):
    """`from_canonical(to_canonical(x))` diverged — round-trip failure."""


class UnregisteredTranslator(TranslationError):
    """No translator registered for the given (source_system, canonical_type)."""
