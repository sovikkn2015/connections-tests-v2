"""
Schwab → canonical Holding translator (T8).

`account_ref` is **str**, `client_ref` is **Optional[str]** (M3).
`market_value_includes_accrued` DERIVED = False (Schwab convention).
`unrealized_gain_loss_pct` DERIVED from decimal × 100.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import uuid5

from m3_schema_registry import AccountType, Holding, SecurityIdentifier, TaxLot

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.schwab.models import SchwabPosition
from m7_schema_translators.schwab.taxlot import (
    REVERSE_LOSSY_FIELDS as TAXLOT_REVERSE_LOSSY,
)
from m7_schema_translators.schwab.taxlot import (
    from_canonical_taxlot,
    to_canonical_taxlot,
)
from m7_schema_translators.shared.namespaces import (
    ACCOUNT_NS,
    CLIENT_NS,
    HOLDING_NS,
)
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "v1"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "schwab_internal_position_metadata",
        "schwab_asset_subclass",
        "schwab_symbol_type_code",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "position.internalMetadata",
        "position.assetSubclass",
        "position.symbolTypeCode",
        "market_value_includes_accrued",
    }
)


_ACCOUNT_TYPE_FWD: dict[str, AccountType] = {
    "INDIVIDUAL": AccountType.TAXABLE,
    "JOINT_TOS": AccountType.TAXABLE,
    "IRA": AccountType.TRADITIONAL_IRA,
    "ROTH_IRA": AccountType.ROTH_IRA,
    "SEP": AccountType.SEP_IRA,
    "SIMPLE": AccountType.SIMPLE_IRA,
    "401K": AccountType.K401,
    "TRUST": AccountType.TRUST_REVOCABLE,
    "UTMA": AccountType.CUSTODIAL_UTMA,
    "UGMA": AccountType.CUSTODIAL_UGMA,
}
_ACCOUNT_TYPE_REV: dict[AccountType, str] = {
    AccountType.TAXABLE: "INDIVIDUAL",
    AccountType.TRADITIONAL_IRA: "IRA",
    AccountType.ROTH_IRA: "ROTH_IRA",
    AccountType.SEP_IRA: "SEP",
    AccountType.SIMPLE_IRA: "SIMPLE",
    AccountType.K401: "401K",
    AccountType.TRUST_REVOCABLE: "TRUST",
    AccountType.TRUST_IRREVOCABLE: "TRUST",
    AccountType.CUSTODIAL_UTMA: "UTMA",
    AccountType.CUSTODIAL_UGMA: "UGMA",
}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"account_type": MappingProxyType(_ACCOUNT_TYPE_FWD)}
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"account_type": MappingProxyType(_ACCOUNT_TYPE_REV)}
)


def _map_account_type(v: str) -> AccountType:
    mapping = ENUM_MAPPINGS["account_type"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="schwab",
            canonical_type="Holding",
            field_path="accountType",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_holding(
    vendor_payload: dict,
) -> tuple[Holding, ReconciliationNote]:
    """Translate Schwab Position → canonical Holding with embedded TaxLots."""
    vendor = SchwabPosition(**vendor_payload)
    validate_vendor_id_chars(
        vendor.id,
        vendor="schwab",
        canonical_type="Holding",
        field_path="position.id",
    )
    validate_vendor_id_chars(
        vendor.accountNumber,
        vendor="schwab",
        canonical_type="Holding",
        field_path="position.accountNumber",
    )

    canonical_id = uuid5(HOLDING_NS, f"schwab:{vendor.id}")
    account_ref = str(uuid5(ACCOUNT_NS, f"schwab:{vendor.accountNumber}"))
    client_ref: Optional[str] = None
    if vendor.accountHolderId:
        client_ref = str(
            uuid5(CLIENT_NS, f"schwab:{vendor.accountHolderId}")
        )

    sec_id: Optional[SecurityIdentifier] = None
    if any((vendor.symbol, vendor.cusip, vendor.isin)):
        sec_id = SecurityIdentifier(
            ticker=vendor.symbol,
            cusip=vendor.cusip,
            isin=vendor.isin,
        )

    account_type: Optional[AccountType] = None
    notes: list[str] = ["schwab_market_value_excludes_accrued"]
    derived: list[str] = ["market_value_includes_accrued"]
    if vendor.accountType is not None:
        account_type = _map_account_type(vendor.accountType)
        if vendor.accountType == "IRA":
            notes.append("schwab_ira_label_ambiguous")
        if vendor.accountType == "TRUST":
            notes.append("schwab_trust_label_ambiguous")

    ugl_pct: Optional[float] = None
    if vendor.unrealizedGainLossPct is not None:
        ugl_pct = vendor.unrealizedGainLossPct * 100.0
        derived.append("unrealized_gain_loss_pct")
        notes.append("schwab_unrealized_gain_loss_pct_derived")

    canonical_lots: list[TaxLot] = []
    sec_class = (
        vendor.assetClass.lower() if vendor.assetClass else None
    )
    for lot in vendor.taxLots:
        lot_dict = lot.model_dump(mode="json")
        lot_canonical, _ = to_canonical_taxlot(
            lot_dict,
            parent_position_id=vendor.id,
            parent_account_type=(
                account_type.value if account_type else None
            ),
            parent_security_class=sec_class,
            parent_jurisdiction=vendor.jurisdiction,
        )
        canonical_lots.append(lot_canonical)

    canonical = Holding(
        canonical_id=canonical_id,
        account_ref=account_ref,
        client_ref=client_ref,
        security_identifier=sec_id,
        security_name=vendor.description,
        security_type=(
            vendor.assetClass.lower() if vendor.assetClass else None
        ),
        quantity=vendor.quantity,
        market_value=vendor.marketValue,
        market_value_includes_accrued=False,
        cost_basis=vendor.costBasis,
        unrealized_gain_loss=vendor.unrealizedGainLoss,
        unrealized_gain_loss_pct=ugl_pct,
        weight_in_account=None,
        currency=vendor.currency or "USD",
        as_of_date=vendor.asOfDate,
        account_type=account_type,
        source_system="schwab",
        source_id=vendor.id,
        tax_lots=canonical_lots,
    )

    note = ReconciliationNote(
        vendor="schwab",
        canonical_type="Holding",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=sorted(derived),
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return canonical, note


def from_canonical_holding(
    canonical: Holding,
) -> tuple[SchwabPosition, ReconciliationNote]:
    """Reverse canonical Holding → Schwab Position."""
    account_type_rev: Optional[str] = None
    if canonical.account_type is not None:
        account_type_rev = REVERSE_ENUM_MAPPINGS["account_type"].get(
            canonical.account_type
        )

    pct_rev: Optional[float] = None
    if canonical.unrealized_gain_loss_pct is not None:
        pct_rev = canonical.unrealized_gain_loss_pct / 100.0

    sec = canonical.security_identifier
    asset_class_rev: Optional[str] = None
    if canonical.security_type is not None:
        asset_class_rev = canonical.security_type.upper()

    vendor_lots = []
    for lot in canonical.tax_lots:
        v_lot, _ = from_canonical_taxlot(lot)
        vendor_lots.append(v_lot)

    # Reverse-lossy: account_ref UUID → 8-digit placeholder.
    account_number_placeholder = "".join(
        c for c in canonical.account_ref if c.isdigit()
    )[:8].rjust(8, "0") or "00000000"

    vendor_model = SchwabPosition(
        id=canonical.source_id,
        accountNumber=account_number_placeholder,
        accountHolderId=(
            canonical.client_ref if canonical.client_ref else None
        ),
        symbol=sec.ticker if sec else None,
        cusip=sec.cusip if sec else None,
        isin=sec.isin if sec else None,
        description=canonical.security_name,
        assetClass=asset_class_rev,
        quantity=canonical.quantity,
        marketValue=canonical.market_value,
        costBasis=canonical.cost_basis,
        unrealizedGainLoss=canonical.unrealized_gain_loss,
        unrealizedGainLossPct=pct_rev,
        currency=canonical.currency or "USD",
        asOfDate=canonical.as_of_date,
        accountType=account_type_rev,
        jurisdiction=None,
        taxLots=vendor_lots,
    )
    note = ReconciliationNote(
        vendor="schwab",
        canonical_type="Holding",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS | TAXLOT_REVERSE_LOSSY),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note
