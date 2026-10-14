"""
Schwab → canonical TaxLot translator (T9).

CRITICAL: `cost_basis_method` NEVER null. Schwab US default is `specific_lot`
for taxable equity. Schwab UK + `SpecificLot` → `ambiguous_mapping` (PENDING SME).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import uuid5

from m3_schema_registry import CostBasisMethod, TaxLot

from m7_schema_translators.cost_basis import normalize_cost_basis_method
from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.schwab.models import SchwabTaxLot
from m7_schema_translators.shared.namespaces import HOLDING_NS, TAXLOT_NS
from m7_schema_translators.shared.reconciliation_note import (
    CostBasisSource,
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "v1"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {"schwab_lot_internal_id", "schwab_lot_source_trade_ref"}
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {"TaxLot.internalLotId", "TaxLot.sourceTradeRef"}
)


_HOLDING_PERIOD_FWD: dict[str, str] = {
    "ST": "short_term",
    "LT": "long_term",
    "UNKNOWN": "unknown",
}
_HOLDING_PERIOD_REV: dict[str, str] = {
    v: k for k, v in _HOLDING_PERIOD_FWD.items()
}

_COST_BASIS_CANONICAL_TO_SCHWAB: dict[CostBasisMethod, str] = {
    CostBasisMethod.SPECIFIC_LOT: "SpecificLot",
    CostBasisMethod.AVERAGE_COST: "AverageCost",
    CostBasisMethod.FIFO: "FIFO",
    CostBasisMethod.LIFO: "LIFO",
    CostBasisMethod.HIFO: "HIFO",
}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"holding_period": MappingProxyType(_HOLDING_PERIOD_FWD)}
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"holding_period": MappingProxyType(_HOLDING_PERIOD_REV)}
)


def _map_holding_period(v: str) -> str:
    mapping = ENUM_MAPPINGS["holding_period"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="schwab",
            canonical_type="TaxLot",
            field_path="holdingPeriod",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_taxlot(
    vendor_payload: dict,
    *,
    parent_position_id: Optional[str] = None,
    parent_account_type: Optional[str] = None,
    parent_security_class: Optional[str] = None,
    parent_jurisdiction: Optional[str] = None,
) -> tuple[TaxLot, ReconciliationNote]:
    """Translate Schwab tax lot → canonical TaxLot (Steering Rule 16)."""
    payload = dict(vendor_payload)
    if parent_position_id is None:
        parent_position_id = payload.pop("_parent_position_id", None)
    else:
        payload.pop("_parent_position_id", None)
    if parent_account_type is None:
        parent_account_type = payload.pop("_parent_account_type", None)
    else:
        payload.pop("_parent_account_type", None)
    if parent_security_class is None:
        parent_security_class = payload.pop("_parent_security_class", None)
    else:
        payload.pop("_parent_security_class", None)
    if parent_jurisdiction is None:
        parent_jurisdiction = payload.pop("_parent_jurisdiction", None)
    else:
        payload.pop("_parent_jurisdiction", None)
    if parent_position_id is None:
        parent_position_id = "unknown-parent"

    vendor = SchwabTaxLot(**payload)
    validate_vendor_id_chars(
        vendor.lotId,
        vendor="schwab",
        canonical_type="TaxLot",
        field_path="SchwabTaxLot.lotId",
    )

    lot_id = uuid5(TAXLOT_NS, f"schwab:{vendor.lotId}")
    holding_ref = str(uuid5(HOLDING_NS, f"schwab:{parent_position_id}"))

    method, origin = normalize_cost_basis_method(
        vendor.costBasisMethod,
        vendor="schwab",
        account_type=parent_account_type,
        security_class=parent_security_class,
        jurisdiction=parent_jurisdiction,
    )

    holding_period: Optional[str] = None
    if vendor.holdingPeriod is not None:
        holding_period = _map_holding_period(vendor.holdingPeriod)

    source_cost_basis_method: Optional[str] = vendor.costBasisMethod

    cb_source = CostBasisSource(
        vendor_field="costBasisMethod",
        vendor_value=vendor.costBasisMethod,
        canonical_value=method.value,
        method_origin=origin,
        confidence="high" if origin == "vendor_reported" else "medium",
    )

    notes: list[str] = []
    if origin == "vendor_reported":
        notes.append("cost_basis_vendor_reported")
    elif origin == "vendor_default":
        notes.append("cost_basis_vendor_default_applied")

    canonical = TaxLot(
        lot_id=lot_id,
        holding_ref=holding_ref,
        security_ref=vendor.symbol,
        acquisition_date=vendor.acquisitionDate,
        acquisition_price=vendor.acquisitionPrice,
        quantity=vendor.quantity,
        cost_basis_method=method,
        cost_basis_amount=vendor.costBasisAmount,
        holding_period=holding_period,
        unrealized_gain_loss=vendor.unrealizedGainLoss,
        wash_sale_disallowed=vendor.washSaleDisallowed,
        source_custodian="schwab",
        source_cost_basis_method=source_cost_basis_method,
    )

    note = ReconciliationNote(
        vendor="schwab",
        canonical_type="TaxLot",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        cost_basis_source=cb_source,
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return canonical, note


def from_canonical_taxlot(
    canonical: TaxLot,
) -> tuple[SchwabTaxLot, ReconciliationNote]:
    """Reverse canonical TaxLot → Schwab tax lot."""
    source_method = canonical.source_cost_basis_method
    if source_method is None:
        source_method = _COST_BASIS_CANONICAL_TO_SCHWAB[
            canonical.cost_basis_method
        ]
    holding_period_rev: Optional[str] = None
    if canonical.holding_period is not None:
        holding_period_rev = REVERSE_ENUM_MAPPINGS["holding_period"].get(
            canonical.holding_period
        )

    vendor_model = SchwabTaxLot(
        lotId=str(canonical.lot_id),
        symbol=canonical.security_ref,
        acquisitionDate=canonical.acquisition_date,
        acquisitionPrice=canonical.acquisition_price,
        quantity=canonical.quantity,
        costBasisMethod=source_method,
        costBasisAmount=canonical.cost_basis_amount,
        holdingPeriod=holding_period_rev,
        unrealizedGainLoss=canonical.unrealized_gain_loss,
        washSaleDisallowed=canonical.wash_sale_disallowed,
    )
    note = ReconciliationNote(
        vendor="schwab",
        canonical_type="TaxLot",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note
