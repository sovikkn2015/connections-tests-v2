"""Test M7 public API — AC13.1-AC13.7."""

from __future__ import annotations

import importlib
import re
from types import MappingProxyType

import pytest

import m7_schema_translators as m7


def test_schema_version():
    assert m7.SCHEMA_VERSION == "0.1.0"


def test_all_contains_expected_symbols():
    expected = {
        "TRANSLATOR_REGISTRY",
        "translate_to_canonical",
        "translate_from_canonical",
        "to_canonical_household_multi",
        "TranslationError",
        "UnknownEnumValue",
        "MissingRequiredField",
        "TypeCoercionError",
        "CostBasisUnmappable",
        "VendorSchemaVersionMismatch",
        "RoundTripDivergence",
        "UnregisteredTranslator",
        "ReconciliationNote",
        "CostBasisSource",
        "TranslatorPair",
        "SCHEMA_VERSION",
        "VALID_REASON_CODES",
    }
    assert expected == set(m7.__all__)


def test_registry_is_mappingproxytype():
    assert isinstance(m7.TRANSLATOR_REGISTRY, MappingProxyType)
    with pytest.raises(TypeError):
        m7.TRANSLATOR_REGISTRY[("bogus", "X")] = None  # type: ignore[index]


def test_registry_has_11_pairs():
    # Remediation M9 (2026 Q2): +Bloomberg + ICE Data + Smarsh = 16 pairs.
    # Keep the `>= 11` floor so the test doesn't regress when additional
    # vendors are added in later waves.
    assert len(m7.TRANSLATOR_REGISTRY) >= 11


def test_registry_keys_match_spec():
    # Remediation M9 (2026 Q2): the spec registry now covers 5 vendor
    # families (SF FSC / Orion / Schwab / eMoney + Bloomberg / ICE Data /
    # Smarsh) -- 16 translator pairs.
    expected = {
        ("salesforce_fsc", "Client"),
        ("salesforce_fsc", "Household"),
        ("salesforce_fsc", "Goal"),
        ("orion", "Holding"),
        ("orion", "Transaction"),
        ("orion", "Household"),
        ("orion", "TaxLot"),
        ("emoney", "PlanSummary"),
        ("schwab", "Holding"),
        ("schwab", "TaxLot"),
        ("schwab", "Household"),
        ("bloomberg", "SecurityProfile"),
        ("bloomberg", "Quote"),
        ("ice_data", "SecurityProfile"),
        ("ice_data", "Quote"),
        ("smarsh", "InteractionSummary"),
    }
    assert set(m7.TRANSLATOR_REGISTRY.keys()) == expected


def test_registry_entries_are_importable():
    """AC2.5 — every entry's module_path must be importable."""
    for pair in m7.TRANSLATOR_REGISTRY.values():
        mod = importlib.import_module(pair.module_path)
        assert mod is not None


def test_translate_to_canonical_unknown_pair_raises():
    with pytest.raises(m7.UnregisteredTranslator) as exc:
        m7.translate_to_canonical("bogus_vendor", "Client", {})
    assert exc.value.reason_code == "unregistered_translator"


def test_translate_to_canonical_unknown_type_raises():
    with pytest.raises(m7.UnregisteredTranslator):
        m7.translate_to_canonical("salesforce_fsc", "NotAType", {})


def test_schwab_vendor_api_version_is_v1():
    """v0.2.0 regression guard — Schwab uses URL-path `v1`."""
    for (vendor, _), pair in m7.TRANSLATOR_REGISTRY.items():
        if vendor == "schwab":
            assert pair.vendor_api_version == "v1"


def test_schema_version_regex():
    """AC8.5 — every translator SCHEMA_VERSION matches ^\\d+\\.\\d+\\.\\d+$."""
    semver = re.compile(r"^\d+\.\d+\.\d+$")
    for pair in m7.TRANSLATOR_REGISTRY.values():
        assert semver.match(pair.schema_version)


def test_registry_is_eagerly_constructed():
    """AC13.7 — reimport and confirm keys unchanged."""
    import m7_schema_translators

    keys_before = set(m7_schema_translators.TRANSLATOR_REGISTRY.keys())
    importlib.reload(m7_schema_translators)
    keys_after = set(m7_schema_translators.TRANSLATOR_REGISTRY.keys())
    assert keys_before == keys_after
