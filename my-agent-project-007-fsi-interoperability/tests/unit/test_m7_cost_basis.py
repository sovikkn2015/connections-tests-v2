"""Test M7 cost_basis — AC5.1-AC5.8, Steering Rule 16."""

from __future__ import annotations

from types import MappingProxyType

import pytest

from m3_schema_registry import CostBasisMethod

from m7_schema_translators.cost_basis import (
    COST_BASIS_DEFAULTS,
    COST_BASIS_VENDOR_MAP,
    normalize_cost_basis_method,
)
from m7_schema_translators.errors import CostBasisUnmappable


def test_maps_are_mappingproxytype():
    assert isinstance(COST_BASIS_VENDOR_MAP, MappingProxyType)
    assert isinstance(COST_BASIS_DEFAULTS, MappingProxyType)
    with pytest.raises(TypeError):
        COST_BASIS_VENDOR_MAP[("bogus", "X")] = CostBasisMethod.FIFO
    with pytest.raises(TypeError):
        COST_BASIS_DEFAULTS[("bogus", "x", "y")] = CostBasisMethod.FIFO


def test_schwab_specific_lot_vendor_reported():
    m, origin = normalize_cost_basis_method(
        "SpecificLot",
        vendor="schwab",
        account_type="taxable",
        security_class="equity",
        jurisdiction="US",
    )
    assert m == CostBasisMethod.SPECIFIC_LOT
    assert origin == "vendor_reported"


def test_every_vendor_map_entry_resolves():
    for (vendor, vs), expected in COST_BASIS_VENDOR_MAP.items():
        m, origin = normalize_cost_basis_method(
            vs,
            vendor=vendor,
            account_type="taxable",
            security_class="equity",
            jurisdiction=None,
        )
        assert m == expected
        assert origin == "vendor_reported"


def test_schwab_us_taxable_equity_default():
    m, origin = normalize_cost_basis_method(
        None,
        vendor="schwab",
        account_type="taxable",
        security_class="equity",
        jurisdiction="US",
    )
    assert m == CostBasisMethod.SPECIFIC_LOT
    assert origin == "vendor_default"


def test_schwab_retirement_wild_default():
    m, origin = normalize_cost_basis_method(
        None,
        vendor="schwab",
        account_type="traditional_ira",
        security_class="equity",
        jurisdiction=None,
    )
    assert m == CostBasisMethod.FIFO
    assert origin == "vendor_default"


def test_unknown_vendor_string_raises():
    with pytest.raises(CostBasisUnmappable) as exc_info:
        normalize_cost_basis_method(
            "UnknownMethod",
            vendor="schwab",
            account_type="taxable",
            security_class="equity",
            jurisdiction="US",
        )
    assert exc_info.value.reason_code == "unsupported_vendor_value"


def test_vendor_silent_unmappable_raises():
    with pytest.raises(CostBasisUnmappable) as exc_info:
        normalize_cost_basis_method(
            None,
            vendor="schwab",
            account_type=None,
            security_class=None,
            jurisdiction=None,
        )
    assert exc_info.value.reason_code == "cost_basis_unmappable"


def test_schwab_uk_specific_lot_ambiguous():
    """Schwab UK + SpecificLot → ambiguous_mapping (PENDING SME)."""
    with pytest.raises(CostBasisUnmappable) as exc_info:
        normalize_cost_basis_method(
            "SpecificLot",
            vendor="schwab",
            account_type="taxable",
            security_class="equity",
            jurisdiction="UK",
        )
    assert exc_info.value.reason_code == "ambiguous_mapping"
    assert exc_info.value.details["jurisdiction"] == "UK"


def test_orion_specific_lot():
    m, origin = normalize_cost_basis_method(
        "SPECIFIC_LOT",
        vendor="orion",
        account_type="taxable",
        security_class="equity",
        jurisdiction=None,
    )
    assert m == CostBasisMethod.SPECIFIC_LOT
    assert origin == "vendor_reported"


def test_schwab_mintax_maps_to_hifo():
    m, _ = normalize_cost_basis_method(
        "MinTax",
        vendor="schwab",
        account_type="taxable",
        security_class="equity",
        jurisdiction=None,
    )
    assert m == CostBasisMethod.HIFO
