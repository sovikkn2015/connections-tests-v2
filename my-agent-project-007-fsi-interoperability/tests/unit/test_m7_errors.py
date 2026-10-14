"""Test M7 errors module — AC4.1-AC4.8, NI-2 fix."""

from __future__ import annotations

import json

import pytest

from m7_schema_translators.errors import (
    VALID_REASON_CODES,
    CostBasisUnmappable,
    CostBasisUnmappableDetails,
    MissingRequiredDetails,
    MissingRequiredField,
    RoundTripDivergence,
    TranslationError,
    TypeCoercionError,
    UnknownEnumDetails,
    UnknownEnumValue,
    UnregisteredTranslator,
    VendorSchemaVersionMismatch,
)


def test_valid_reason_codes_is_frozenset():
    assert isinstance(VALID_REASON_CODES, frozenset)
    assert len(VALID_REASON_CODES) == 11
    assert "unknown_enum_value" in VALID_REASON_CODES
    assert "cost_basis_unmappable" in VALID_REASON_CODES
    assert "vendor_id_invalid_chars" in VALID_REASON_CODES


def test_translation_error_rejects_invalid_reason_code():
    with pytest.raises(ValueError):
        TranslationError(
            reason_code="nope",
            vendor="schwab",
            canonical_type="Client",
            field_path="x",
            details={},
        )


def test_all_subclasses_inherit_from_translation_error():
    for cls in [
        UnknownEnumValue,
        MissingRequiredField,
        TypeCoercionError,
        CostBasisUnmappable,
        VendorSchemaVersionMismatch,
        RoundTripDivergence,
        UnregisteredTranslator,
    ]:
        assert issubclass(cls, TranslationError)


def test_unknown_enum_value_format():
    exc = UnknownEnumValue(
        reason_code="unknown_enum_value",
        vendor="schwab",
        canonical_type="Holding",
        field_path="accountType",
        details={"vendor_value": "WEIRD", "valid_values": ["a", "b"]},
    )
    s = str(exc)
    assert s.startswith("[unknown_enum_value] schwab.Holding.accountType:")
    assert "vendor_value=WEIRD" in s


def test_format_excludes_non_allowlisted_keys():
    """NI-2 fix — unknown `details` keys must NOT appear in the rendered string."""
    exc = TypeCoercionError(
        reason_code="type_coercion_failed",
        vendor="schwab",
        canonical_type="Holding",
        field_path="costBasis",
        details={
            "expected_type": "float",
            "got_type": "str",
            "raw_email_from_caller": "evil@example.com",
        },
    )
    s = str(exc)
    assert "expected_type=float" in s
    assert "got_type=str" in s
    assert "evil@example.com" not in s
    assert "raw_email_from_caller" not in s


def test_details_json_serializable():
    """AC16.4 — every subclass `details` is JSON-serializable."""
    for cls, reason, details in [
        (
            UnknownEnumValue,
            "unknown_enum_value",
            {"vendor_value": "X", "valid_values": ["a"]},
        ),
        (MissingRequiredField, "missing_required_field", {"field_name": "x"}),
        (
            TypeCoercionError,
            "type_coercion_failed",
            {"expected_type": "float", "got_type": "str"},
        ),
        (
            CostBasisUnmappable,
            "cost_basis_unmappable",
            {
                "vendor_value": None,
                "account_type_group": "trust",
                "security_class": None,
                "jurisdiction": "UK",
            },
        ),
        (
            UnregisteredTranslator,
            "unregistered_translator",
            {"valid_source_systems": ["a"], "valid_canonical_types": ["b"]},
        ),
    ]:
        exc = cls(
            reason_code=reason,
            vendor="v",
            canonical_type="T",
            field_path="x",
            details=details,
        )
        json.dumps(exc.details)


def test_typed_dicts_exist():
    """AC4.8 — per-subclass TypedDicts are defined (smoke)."""
    assert UnknownEnumDetails is not None
    assert MissingRequiredDetails is not None
    assert CostBasisUnmappableDetails is not None
