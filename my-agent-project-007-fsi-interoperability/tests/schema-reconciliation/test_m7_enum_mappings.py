"""Enum-mapping meta-tests — AC6.5.

Iterates TRANSLATOR_REGISTRY to discover translators (no hard-coded list).
"""

from __future__ import annotations

import importlib
from types import MappingProxyType

import pytest

from m7_schema_translators import TRANSLATOR_REGISTRY


def _translator_modules():
    seen = set()
    for pair in TRANSLATOR_REGISTRY.values():
        if pair.module_path in seen:
            continue
        seen.add(pair.module_path)
        yield importlib.import_module(pair.module_path)


def test_enum_mappings_are_mappingproxytype():
    for mod in _translator_modules():
        em = getattr(mod, "ENUM_MAPPINGS", None)
        if em is None:
            continue
        assert isinstance(em, MappingProxyType)
        with pytest.raises(TypeError):
            em["bogus"] = None
        rev = getattr(mod, "REVERSE_ENUM_MAPPINGS", None)
        assert isinstance(rev, MappingProxyType)
        with pytest.raises(TypeError):
            rev["bogus"] = None


def test_reverse_mappings_cover_canonical_values():
    """AC6.5(a) — every canonical value has ≥1 reverse entry."""
    for mod in _translator_modules():
        em = getattr(mod, "ENUM_MAPPINGS", None)
        rev = getattr(mod, "REVERSE_ENUM_MAPPINGS", None)
        if em is None or rev is None:
            continue
        for field_name, fwd in em.items():
            rev_field = rev.get(field_name)
            if rev_field is None:
                continue
            canonical_values = set(fwd.values())
            reverse_keys = set(rev_field.keys())
            missing = canonical_values - reverse_keys
            assert not missing, (
                f"{mod.__name__}.{field_name}: reverse missing for {missing}"
            )


def test_lossy_and_reverse_lossy_declared():
    """AC11.4 — every translator declares both frozensets."""
    for mod in _translator_modules():
        lossy = getattr(mod, "LOSSY_FIELDS", None)
        rev_lossy = getattr(mod, "REVERSE_LOSSY_FIELDS", None)
        assert lossy is not None, f"{mod.__name__} missing LOSSY_FIELDS"
        assert rev_lossy is not None, (
            f"{mod.__name__} missing REVERSE_LOSSY_FIELDS"
        )
        assert isinstance(lossy, frozenset)
        assert isinstance(rev_lossy, frozenset)


def test_schema_version_declared():
    for mod in _translator_modules():
        assert getattr(mod, "SCHEMA_VERSION", None) is not None
        assert getattr(mod, "VENDOR_API_VERSION", None) is not None
