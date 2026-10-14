"""
Orion → canonical Holding translator (T4).

`account_ref` is **str** per M3 (NOT UUID). `client_ref` is **Optional[str]**.
Tax lots in Position.taxLots[] are embedded — each translated via Orion TaxLot
translator, passing parent context (account_type, security_class).
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import uuid5

from m3_schema_registry import AccountType, Holding, SecurityIdentifier, TaxLot

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.orion.models import OrionPosition
from m7_schema_translators.orion.taxlot import (
    REVERSE_LOSSY_FIELDS as TAXLOT_REVERSE_LOSSY,
)
from m7_schema_translators.orion.taxlot import (
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
VENDOR_API_VERSION: str = "v2.0"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "orion_position_custom_fields",
        "orion_position_strategy_tag",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {"OrionPosition.customFields", "OrionPosition.strategyTag"}
)


# Orion AccountType → M3 AccountType value
_ACCOUNT_TYPE_FWD: dict[str, AccountType] = {
    "TAXABLE": AccountType.TAXABLE,
    "TRADITIONAL_IRA": AccountType.TRADITIONAL_IRA,
    "ROTH_IRA": AccountType.ROTH_IRA,
    "401K": AccountType.K401,
    "403B": AccountType.B403,
    "SEP_IRA": AccountType.SEP_IRA,
    "SIMPLE_IRA": AccountType.SIMPLE_IRA,
    "TRUST": AccountType.TRUST_REVOCABLE,  # default with recon note
    "UTMA": AccountType.CUSTODIAL_UTMA,
    "UGMA": AccountType.CUSTODIAL_UGMA,
}
_ACCOUNT_TYPE_REV: dict[AccountType, str] = {
    AccountType.TAXABLE: "TAXABLE",
    AccountType.TRADITIONAL_IRA: "TRADITIONAL_IRA",
    AccountType.ROTH_IRA: "ROTH_IRA",
    AccountType.K401: "401K",
    AccountType.B403: "403B",
    AccountType.SEP_IRA: "SEP_IRA",
    AccountType.SIMPLE_IRA: "SIMPLE_IRA",
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
            vendor="orion",
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
    """Translate Orion Position → canonical Holding (with embedded TaxLots)."""
    vendor = OrionPosition(**vendor_payload)
    validate_vendor_id_chars(
        vendor.positionId,
        vendor="orion",
        canonical_type="Holding",
        field_path="OrionPosition.positionId",
    )
    validate_vendor_id_chars(
        vendor.accountId,
        vendor="orion",
        canonical_type="Holding",
        field_path="OrionPosition.accountId",
    )

    canonical_id = uuid5(HOLDING_NS, f"orion:{vendor.positionId}")
    account_ref = str(uuid5(ACCOUNT_NS, f"orion:{vendor.accountId}"))
    client_ref: Optional[str] = None
    if vendor.clientId:
        client_ref = str(uuid5(CLIENT_NS, f"orion:{vendor.clientId}"))

    sec_id: Optional[SecurityIdentifier] = None
    if any((vendor.symbol, vendor.cusip, vendor.isin)):
        sec_id = SecurityIdentifier(
            ticker=vendor.symbol,
            cusip=vendor.cusip,
            isin=vendor.isin,
        )

    account_type: Optional[AccountType] = None
    notes: list[str] = []
    if vendor.accountType is not None:
        account_type = _map_account_type(vendor.accountType)
        if vendor.accountType == "TRUST":
            notes.append("orion_trust_label_ambiguous")

    # Translate embedded tax lots
    canonical_lots: list[TaxLot] = []
    for lot_payload in vendor.taxLots:
        lot_dict = lot_payload.model_dump(mode="json")
        lot_canonical, _ = to_canonical_taxlot(
            lot_dict,
            parent_position_id=vendor.positionId,
            parent_account_type=(
                account_type.value if account_type else None
            ),
            parent_security_class=vendor.securityType,
            parent_jurisdiction=None,
        )
        canonical_lots.append(lot_canonical)

    canonical = Holding(
        canonical_id=canonical_id,
        account_ref=account_ref,
        client_ref=client_ref,
        security_identifier=sec_id,
        security_name=vendor.securityName,
        security_type=vendor.securityType,
        quantity=vendor.quantity,
        market_value=vendor.marketValue,
        market_value_includes_accrued=vendor.includesAccruedInterest,
        cost_basis=vendor.costBasis,
        unrealized_gain_loss=vendor.unrealizedGainLoss,
        unrealized_gain_loss_pct=vendor.unrealizedGainLossPct,
        weight_in_account=vendor.weightInAccount,
        currency=vendor.currency or "USD",
        as_of_date=vendor.asOfDate,
        account_type=account_type,
        source_system="orion",
        source_id=vendor.positionId,
        tax_lots=canonical_lots,
    )

    note = ReconciliationNote(
        vendor="orion",
        canonical_type="Holding",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return canonical, note


def from_canonical_holding(
    canonical: Holding,
) -> tuple[OrionPosition, ReconciliationNote]:
    """Reverse canonical Holding → Orion Position."""
    account_type_rev: Optional[str] = None
    if canonical.account_type is not None:
        account_type_rev = REVERSE_ENUM_MAPPINGS["account_type"].get(
            canonical.account_type
        )

    vendor_lots = []
    for lot in canonical.tax_lots:
        v_lot, _ = from_canonical_taxlot(lot)
        vendor_lots.append(v_lot)

    sec = canonical.security_identifier
    vendor_model = OrionPosition(
        positionId=canonical.source_id,
        accountId=str(canonical.account_ref),  # canonical is UUID-string form
        clientId=str(canonical.client_ref) if canonical.client_ref else None,
        symbol=sec.ticker if sec else None,
        cusip=sec.cusip if sec else None,
        isin=sec.isin if sec else None,
        securityName=canonical.security_name,
        securityType=canonical.security_type,
        quantity=canonical.quantity,
        marketValue=canonical.market_value,
        includesAccruedInterest=canonical.market_value_includes_accrued,
        costBasis=canonical.cost_basis,
        unrealizedGainLoss=canonical.unrealized_gain_loss,
        unrealizedGainLossPct=canonical.unrealized_gain_loss_pct,
        weightInAccount=canonical.weight_in_account,
        currency=canonical.currency or "USD",
        asOfDate=canonical.as_of_date,
        accountType=account_type_rev,
        taxLots=vendor_lots,
    )
    note = ReconciliationNote(
        vendor="orion",
        canonical_type="Holding",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS | TAXLOT_REVERSE_LOSSY),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note
