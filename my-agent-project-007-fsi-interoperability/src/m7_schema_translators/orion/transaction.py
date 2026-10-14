"""
Orion → canonical Transaction translator (T5).

v0.2.0 CRITICAL: `transaction_id` (UUID, primary key) and `source_id` (str, raw vendor)
are TWO SEPARATE fields — never collapsed.

M3: `Transaction.account_ref: UUID`, `client_ref: Optional[UUID]`, `order_ref: Optional[UUID]`.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import UUID, uuid5

from m3_schema_registry import (
    AccountType,
    CostBasisImpact,
    SecurityIdentifier,
    Transaction,
    TransactionType,
)

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.orion.models import OrionTransaction
from m7_schema_translators.shared.namespaces import (
    ACCOUNT_NS,
    CLIENT_NS,
    TRANSACTION_NS,
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
        "orion_transaction_custom_attributes_other",
        "orion_transaction_strategy_tag",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "OrionTransaction.strategyTag",
        "trace_id_external",
    }
)


_TX_TYPE_FWD: dict[str, TransactionType] = {
    "BUY": TransactionType.BUY,
    "SELL": TransactionType.SELL,
    "SELL_SHORT": TransactionType.SELL_SHORT,
    "BUY_TO_COVER": TransactionType.BUY_TO_COVER,
    "DIV": TransactionType.DIVIDEND,
    "INT": TransactionType.INTEREST,
    "FEE": TransactionType.FEE,
    "MGMT_FEE": TransactionType.MANAGEMENT_FEE,
    "TRANSFER_IN": TransactionType.TRANSFER_IN,
    "TRANSFER_OUT": TransactionType.TRANSFER_OUT,
    "DISTRIBUTION": TransactionType.DISTRIBUTION,
    "CONTRIBUTION": TransactionType.CONTRIBUTION,
    "WIRE_IN": TransactionType.WIRE_IN,
    "WIRE_OUT": TransactionType.WIRE_OUT,
    "JOURNAL": TransactionType.JOURNAL,
    "REINVEST": TransactionType.REINVESTMENT,
    "ROC": TransactionType.RETURN_OF_CAPITAL,
    "CORP_ACTION": TransactionType.CORPORATE_ACTION,
    "MARGIN_INT": TransactionType.MARGIN_INTEREST,
}
_TX_TYPE_REV: dict[TransactionType, str] = {v: k for k, v in _TX_TYPE_FWD.items()}

_SETTLEMENT_FWD: dict[str, str] = {
    "PENDING": "pending",
    "SETTLED": "settled",
    "FAILED": "failed",
}
_SETTLEMENT_REV: dict[str, str] = {v: k for k, v in _SETTLEMENT_FWD.items()}

_ACCOUNT_TYPE_FWD: dict[str, AccountType] = {
    "TAXABLE": AccountType.TAXABLE,
    "TRADITIONAL_IRA": AccountType.TRADITIONAL_IRA,
    "ROTH_IRA": AccountType.ROTH_IRA,
    "401K": AccountType.K401,
    "403B": AccountType.B403,
    "SEP_IRA": AccountType.SEP_IRA,
    "SIMPLE_IRA": AccountType.SIMPLE_IRA,
    "TRUST": AccountType.TRUST_REVOCABLE,
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
    {
        "transaction_type": MappingProxyType(_TX_TYPE_FWD),
        "settlement_status": MappingProxyType(_SETTLEMENT_FWD),
        "account_type": MappingProxyType(_ACCOUNT_TYPE_FWD),
    }
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[
    str, MappingProxyType
] = MappingProxyType(
    {
        "transaction_type": MappingProxyType(_TX_TYPE_REV),
        "settlement_status": MappingProxyType(_SETTLEMENT_REV),
        "account_type": MappingProxyType(_ACCOUNT_TYPE_REV),
    }
)


def _map_tx_type(v: str) -> TransactionType:
    mapping = ENUM_MAPPINGS["transaction_type"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="orion",
            canonical_type="Transaction",
            field_path="OrionTransaction.type",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def _map_settlement(v: str) -> str:
    mapping = ENUM_MAPPINGS["settlement_status"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="orion",
            canonical_type="Transaction",
            field_path="OrionTransaction.settlementStatus",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def _map_account_type(v: str) -> AccountType:
    mapping = ENUM_MAPPINGS["account_type"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="orion",
            canonical_type="Transaction",
            field_path="OrionTransaction.accountType",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_transaction(
    vendor_payload: dict,
) -> tuple[Transaction, ReconciliationNote]:
    """Translate Orion transaction → canonical Transaction."""
    vendor = OrionTransaction(**vendor_payload)
    validate_vendor_id_chars(
        vendor.transactionId,
        vendor="orion",
        canonical_type="Transaction",
        field_path="OrionTransaction.transactionId",
    )
    validate_vendor_id_chars(
        vendor.accountId,
        vendor="orion",
        canonical_type="Transaction",
        field_path="OrionTransaction.accountId",
    )

    # v0.2.0: TWO separate fields
    transaction_id = uuid5(
        TRANSACTION_NS, f"orion:{vendor.transactionId}"
    )
    source_id = vendor.transactionId

    account_ref = uuid5(ACCOUNT_NS, f"orion:{vendor.accountId}")
    client_ref: Optional[UUID] = None
    if vendor.clientId:
        client_ref = uuid5(CLIENT_NS, f"orion:{vendor.clientId}")

    tx_type = _map_tx_type(vendor.type)

    settlement_status: Optional[str] = None
    if vendor.settlementStatus is not None:
        settlement_status = _map_settlement(vendor.settlementStatus)

    account_type: Optional[AccountType] = None
    if vendor.accountType is not None:
        account_type = _map_account_type(vendor.accountType)

    sec_id: Optional[SecurityIdentifier] = None
    if any((vendor.symbol, vendor.cusip)):
        sec_id = SecurityIdentifier(
            ticker=vendor.symbol, cusip=vendor.cusip
        )

    cost_basis_impact: Optional[CostBasisImpact] = None
    if any(
        v is not None
        for v in (
            vendor.realizedGainLoss,
            vendor.holdingPeriod,
            vendor.washSaleDisallowed,
        )
    ):
        # Map holding_period from Orion short-form to canonical format
        hp = vendor.holdingPeriod
        if hp == "SHORT_TERM":
            hp = "short_term"
        elif hp == "LONG_TERM":
            hp = "long_term"
        cost_basis_impact = CostBasisImpact(
            realized_gain_loss=vendor.realizedGainLoss,
            holding_period=hp,
            wash_sale_disallowed=vendor.washSaleDisallowed,
        )

    # order_ref from customAttributes (reverse may have stored it)
    order_ref: Optional[UUID] = None
    notes: list[str] = []
    if vendor.customAttributes and "order_ref" in vendor.customAttributes:
        try:
            order_ref = UUID(str(vendor.customAttributes["order_ref"]))
            notes.append("canonical_order_ref_preserved_in_custom_attributes")
        except (ValueError, TypeError):
            order_ref = None

    canonical = Transaction(
        transaction_id=transaction_id,
        account_ref=account_ref,
        client_ref=client_ref,
        order_ref=order_ref,
        transaction_type=tx_type,
        security_identifier=sec_id,
        security_name=vendor.securityName,
        quantity=vendor.quantity,
        price=vendor.price,
        amount=vendor.amount,
        commission=vendor.commission,
        fees=vendor.fees,
        net_amount=vendor.netAmount,
        trade_date=vendor.tradeDate,
        settlement_date=vendor.settlementDate,
        settlement_status=settlement_status,
        currency=vendor.currency or "USD",
        description=vendor.description,
        tax_lot_ref=vendor.taxLotId,
        cost_basis_impact=cost_basis_impact,
        account_type=account_type,
        source_system="orion",
        source_id=source_id,
        source_transaction_type=vendor.type,
        trace_id=None,  # M7 does NOT set trace_id; M6 attaches it externally
        created_at=vendor.createdAt,
    )

    note = ReconciliationNote(
        vendor="orion",
        canonical_type="Transaction",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return canonical, note


def from_canonical_transaction(
    canonical: Transaction,
) -> tuple[OrionTransaction, ReconciliationNote]:
    """Reverse canonical Transaction → Orion transaction."""
    vendor_type = (
        canonical.source_transaction_type
        or REVERSE_ENUM_MAPPINGS["transaction_type"][canonical.transaction_type]
    )
    settlement_rev: Optional[str] = None
    if canonical.settlement_status is not None:
        settlement_rev = REVERSE_ENUM_MAPPINGS["settlement_status"].get(
            canonical.settlement_status
        )

    account_type_rev: Optional[str] = None
    if canonical.account_type is not None:
        account_type_rev = REVERSE_ENUM_MAPPINGS["account_type"].get(
            canonical.account_type
        )

    sec = canonical.security_identifier
    cbi = canonical.cost_basis_impact
    # Map canonical holding_period back to Orion's upper-case form
    orion_hp = None
    if cbi and cbi.holding_period == "short_term":
        orion_hp = "SHORT_TERM"
    elif cbi and cbi.holding_period == "long_term":
        orion_hp = "LONG_TERM"

    custom_attrs: Optional[dict] = None
    notes: list[str] = []
    if canonical.order_ref is not None:
        custom_attrs = {"order_ref": str(canonical.order_ref)}
        notes.append("canonical_order_ref_preserved_in_custom_attributes")

    vendor_model = OrionTransaction(
        transactionId=canonical.source_id,
        accountId=str(canonical.account_ref),
        clientId=str(canonical.client_ref) if canonical.client_ref else None,
        type=vendor_type,
        symbol=sec.ticker if sec else None,
        cusip=sec.cusip if sec else None,
        securityName=canonical.security_name,
        quantity=canonical.quantity,
        price=canonical.price,
        amount=canonical.amount,
        commission=canonical.commission,
        fees=canonical.fees,
        netAmount=canonical.net_amount,
        tradeDate=canonical.trade_date,
        settlementDate=canonical.settlement_date,
        settlementStatus=settlement_rev,
        currency=canonical.currency or "USD",
        description=canonical.description,
        taxLotId=canonical.tax_lot_ref,
        realizedGainLoss=cbi.realized_gain_loss if cbi else None,
        holdingPeriod=orion_hp,
        washSaleDisallowed=cbi.wash_sale_disallowed if cbi else None,
        accountType=account_type_rev,
        customAttributes=custom_attrs,
        createdAt=canonical.created_at,
    )
    note = ReconciliationNote(
        vendor="orion",
        canonical_type="Transaction",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return vendor_model, note
