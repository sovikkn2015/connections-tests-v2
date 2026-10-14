"""
Cost basis normalization (Steering Rule 16 / R5).

`cost_basis_method` on canonical TaxLot is NEVER null. This module is the
authoritative source of vendor-string → canonical-enum mappings AND default
rules when the vendor is silent.

Fail-closed: unknown inputs raise `CostBasisUnmappable`. Never returns
`specific_lot` as a safe fallback.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional

from m3_schema_registry import CostBasisMethod

from m7_schema_translators.errors import CostBasisUnmappable


# =============================================================================
# VENDOR STRING → CANONICAL ENUM (AC5.2)
# =============================================================================

_COST_BASIS_VENDOR_MAP_RAW: dict[tuple[str, str], CostBasisMethod] = {
    # Schwab
    ("schwab", "SpecificLot"): CostBasisMethod.SPECIFIC_LOT,
    ("schwab", "SL"): CostBasisMethod.SPECIFIC_LOT,
    ("schwab", "AverageCost"): CostBasisMethod.AVERAGE_COST,
    ("schwab", "AC"): CostBasisMethod.AVERAGE_COST,
    ("schwab", "FIFO"): CostBasisMethod.FIFO,
    ("schwab", "LIFO"): CostBasisMethod.LIFO,
    ("schwab", "HIFO"): CostBasisMethod.HIFO,
    ("schwab", "MinTax"): CostBasisMethod.HIFO,
    # Orion
    ("orion", "SPECIFIC_LOT"): CostBasisMethod.SPECIFIC_LOT,
    ("orion", "AVG_COST"): CostBasisMethod.AVERAGE_COST,
    ("orion", "FIFO"): CostBasisMethod.FIFO,
    ("orion", "LIFO"): CostBasisMethod.LIFO,
    ("orion", "HIFO"): CostBasisMethod.HIFO,
}

COST_BASIS_VENDOR_MAP: MappingProxyType[
    tuple[str, str], CostBasisMethod
] = MappingProxyType(_COST_BASIS_VENDOR_MAP_RAW)


# =============================================================================
# VENDOR DEFAULTS (AC5.3)
# =============================================================================

# Keyed by (vendor, account_type_group, security_class).
_COST_BASIS_DEFAULTS_RAW: dict[
    tuple[str, str, str], CostBasisMethod
] = {
    # Schwab
    ("schwab", "taxable", "equity"): CostBasisMethod.SPECIFIC_LOT,
    ("schwab", "taxable", "mutual_fund"): CostBasisMethod.AVERAGE_COST,
    ("schwab", "taxable", "etf"): CostBasisMethod.SPECIFIC_LOT,
    ("schwab", "retirement", "*"): CostBasisMethod.FIFO,
    # Orion
    ("orion", "taxable", "equity"): CostBasisMethod.SPECIFIC_LOT,
    ("orion", "taxable", "mutual_fund"): CostBasisMethod.AVERAGE_COST,
    ("orion", "retirement", "*"): CostBasisMethod.FIFO,
}

COST_BASIS_DEFAULTS: MappingProxyType[
    tuple[str, str, str], CostBasisMethod
] = MappingProxyType(_COST_BASIS_DEFAULTS_RAW)


# =============================================================================
# ACCOUNT TYPE → GROUP mapping
# =============================================================================

_RETIREMENT_TYPES: frozenset[str] = frozenset(
    {
        "traditional_ira",
        "roth_ira",
        "401k",
        "403b",
        "457",
        "sep_ira",
        "simple_ira",
        "erisa_pension",
        "erisa_profit_sharing",
    }
)
_TRUST_TYPES: frozenset[str] = frozenset(
    {"trust_revocable", "trust_irrevocable"}
)
_CUSTODIAL_TYPES: frozenset[str] = frozenset(
    {"custodial_utma", "custodial_ugma"}
)


def _account_type_group(account_type: Optional[str]) -> Optional[str]:
    """Map M3 AccountType string value to group slug."""
    if account_type is None:
        return None
    if account_type == "taxable":
        return "taxable"
    if account_type in _RETIREMENT_TYPES:
        return "retirement"
    if account_type in _TRUST_TYPES:
        return "trust"
    if account_type in _CUSTODIAL_TYPES:
        return "custodial"
    return None  # 529, HSA


def _security_class_slug(security_class: Optional[str]) -> Optional[str]:
    """Normalize security class to one of {equity, mutual_fund, etf, fixed_income}."""
    if security_class is None:
        return None
    s = security_class.lower().strip()
    if s in {"equity", "stock"}:
        return "equity"
    if s in {"mutual_fund", "mutualfund", "mf"}:
        return "mutual_fund"
    if s == "etf":
        return "etf"
    if s in {"fixed_income", "bond", "fixedincome"}:
        return "fixed_income"
    return None


# =============================================================================
# PUBLIC NORMALIZER (AC5.1)
# =============================================================================


def normalize_cost_basis_method(
    vendor_string: Optional[str],
    *,
    vendor: str,
    account_type: Optional[str],
    security_class: Optional[str],
    jurisdiction: Optional[str],
) -> tuple[CostBasisMethod, str]:
    """Return `(method, origin)` where origin ∈ {vendor_reported, vendor_default}.

    Fail-closed per AC5.6 — `CostBasisUnmappable` on any unmapped input.
    """
    # PENDING SME: Schwab UK ambiguity
    if (
        vendor == "schwab"
        and vendor_string == "SpecificLot"
        and jurisdiction == "UK"
    ):
        raise CostBasisUnmappable(
            reason_code="ambiguous_mapping",
            vendor=vendor,
            canonical_type="TaxLot",
            field_path="costBasisMethod",
            details={
                "vendor_value": vendor_string,
                "account_type_group": _account_type_group(account_type),
                "security_class": _security_class_slug(security_class),
                "jurisdiction": jurisdiction,
            },
        )

    # Path 1 — vendor reported a string
    if vendor_string is not None:
        key = (vendor, vendor_string)
        if key in COST_BASIS_VENDOR_MAP:
            return COST_BASIS_VENDOR_MAP[key], "vendor_reported"
        raise CostBasisUnmappable(
            reason_code="unsupported_vendor_value",
            vendor=vendor,
            canonical_type="TaxLot",
            field_path="costBasisMethod",
            details={
                "vendor_value": vendor_string,
                "account_type_group": _account_type_group(account_type),
                "security_class": _security_class_slug(security_class),
                "jurisdiction": jurisdiction,
            },
        )

    # Path 2 — vendor silent, try defaults
    group = _account_type_group(account_type)
    sec = _security_class_slug(security_class)
    if group is None or sec is None:
        raise CostBasisUnmappable(
            reason_code="cost_basis_unmappable",
            vendor=vendor,
            canonical_type="TaxLot",
            field_path="costBasisMethod",
            details={
                "vendor_value": None,
                "account_type_group": group,
                "security_class": sec,
                "jurisdiction": jurisdiction,
            },
        )

    exact_key = (vendor, group, sec)
    if exact_key in COST_BASIS_DEFAULTS:
        return COST_BASIS_DEFAULTS[exact_key], "vendor_default"
    wild_key = (vendor, group, "*")
    if wild_key in COST_BASIS_DEFAULTS:
        return COST_BASIS_DEFAULTS[wild_key], "vendor_default"

    raise CostBasisUnmappable(
        reason_code="cost_basis_unmappable",
        vendor=vendor,
        canonical_type="TaxLot",
        field_path="costBasisMethod",
        details={
            "vendor_value": None,
            "account_type_group": group,
            "security_class": sec,
            "jurisdiction": jurisdiction,
        },
    )
