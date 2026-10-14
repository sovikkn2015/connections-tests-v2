"""PII-free scans — AC9.5, AC14.2, AC14.6, AC14.8 (Task 19)."""

from __future__ import annotations

import json
import re

import pytest

from m7_schema_translators import TRANSLATOR_REGISTRY, UnknownEnumValue
from m7_schema_translators.salesforce_fsc.client import to_canonical_client


def test_reconciliation_note_has_no_pii():
    """Feed synthetic PII; assert note does not contain it."""
    fixture = {
        "account_id": "001BBBBBBBBBBBB",
        "name": "Alice Example",
        "record_type_name": "PersonAccount",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-06-01T00:00:00Z",
        "firm_id": "FIRM-001",
        "jurisdiction": "US",
        "last_ssn_digits": "9876",
        "contact_id": "003C000000001",
        "first_name": "Alice",
        "last_name": "Example",
        "email": "alice@example.invalid",
        "phone": "555-555-0100",
        "birthdate": "1980-03-15",
    }
    _, note = to_canonical_client(fixture)
    note_dump = note.model_dump_json()
    for pii_literal in [
        "alice@example.invalid",
        "555-555-0100",
        "9876",
        "1980-03-15",
        "Alice",
    ]:
        assert pii_literal not in note_dump, f"PII leak: {pii_literal}"


def test_translation_error_has_no_pii_in_details():
    """AC14.6 — trigger UnknownEnumValue, scan str(exc) AND details JSON."""
    fixture = {
        "account_id": "001XXXXXXXXXX01",
        "name": "Alice Example",
        "record_type_name": "MadeUpRecordType",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-01-01T00:00:00Z",
        "firm_id": "FIRM-001",
        "jurisdiction": "US",
        "email": "alice@example.invalid",
        "phone": "555-555-0100",
    }
    with pytest.raises(UnknownEnumValue) as exc_info:
        to_canonical_client(fixture)
    as_str = str(exc_info.value)
    as_json = json.dumps(exc_info.value.details)
    for pii in ["alice@example.invalid", "555-555-0100"]:
        assert pii not in as_str
        assert pii not in as_json


def test_vendor_value_enum_friendly_regex():
    """AC14.8 — UnknownEnumDetails.vendor_value must match ^[A-Za-z0-9_ .\\-]+$."""
    pattern = re.compile(r"^[A-Za-z0-9_ .\-]+$")
    fixture = {
        "account_id": "001YYYYYYYYYY01",
        "name": "Test",
        "record_type_name": "MadeUpRecordType",
        "created_date": "2024-01-01T00:00:00Z",
        "last_modified_date": "2024-01-01T00:00:00Z",
        "firm_id": "FIRM-001",
        "jurisdiction": "US",
    }
    with pytest.raises(UnknownEnumValue) as exc_info:
        to_canonical_client(fixture)
    v = exc_info.value.details["vendor_value"]
    assert pattern.match(v), f"vendor_value {v!r} not enum-friendly"


def test_registry_covers_all_11():
    # Remediation M9 (2026 Q2): registry expanded to 16 translator pairs
    # (5 vendor families). Keep the lower bound to catch accidental drops.
    assert len(TRANSLATOR_REGISTRY) >= 11
