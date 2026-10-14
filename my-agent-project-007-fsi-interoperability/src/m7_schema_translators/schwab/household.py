"""
Schwab → canonical Household translator (T11).

Container model. `grouping_type="custodial"` CONST.
`client_ref` / `account_ref` are str per M3.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import uuid5

from m3_schema_registry import (
    Household,
    HouseholdAccount,
    HouseholdMember,
    HouseholdVendorMappings,
    HouseholdVendorSchwab,
)

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.schwab.models import (
    SchwabLinkedAccount,
    SchwabLinkedAccountHolder,
    SchwabMasterAccount,
)
from m7_schema_translators.shared.namespaces import (
    ACCOUNT_NS,
    CLIENT_NS,
    HOUSEHOLD_NS,
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
        "schwab_master_account_metadata",
        "schwab_master_account_title_code",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {"MasterAccount.metadata", "MasterAccount.titleCode"}
)


_ROLE_FWD: dict[str, str] = {
    "PRIMARY": "primary",
    "SPOUSE": "spouse",
    "DEPENDENT": "dependent",
    "TRUSTEE": "trustee",
    "BENEFICIARY": "beneficiary",
    "AUTHORIZED_SIGNER": "authorized_signer",
    "POWER_OF_ATTORNEY": "power_of_attorney",
}
_ROLE_REV: dict[str, str] = {v: k for k, v in _ROLE_FWD.items()}

ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"role": MappingProxyType(_ROLE_FWD)}
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType] = MappingProxyType(
    {"role": MappingProxyType(_ROLE_REV)}
)


def _map_role(v: str) -> str:
    mapping = ENUM_MAPPINGS["role"]
    if v not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="schwab",
            canonical_type="Household",
            field_path="members[].role",
            details={
                "vendor_value": v,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[v]


def to_canonical_household(
    vendor_payload: dict,
) -> tuple[Household, ReconciliationNote]:
    """Single-vendor Schwab → canonical Household. `reconciliation=None`."""
    vendor = SchwabMasterAccount(**vendor_payload)
    validate_vendor_id_chars(
        vendor.masterAccountNumber,
        vendor="schwab",
        canonical_type="Household",
        field_path="MasterAccount.masterAccountNumber",
    )

    canonical_id = uuid5(
        HOUSEHOLD_NS, f"schwab:{vendor.masterAccountNumber}"
    )

    members: list[HouseholdMember] = []
    for h in vendor.linkedAccountHolders:
        validate_vendor_id_chars(
            h.accountHolderId,
            vendor="schwab",
            canonical_type="Household",
            field_path="linkedAccountHolders[].accountHolderId",
        )
        members.append(
            HouseholdMember(
                client_ref=str(
                    uuid5(CLIENT_NS, f"schwab:{h.accountHolderId}")
                ),
                role=_map_role(h.role),
                source="schwab",
            )
        )

    accounts: list[HouseholdAccount] = []
    for a in vendor.linkedAccounts:
        accounts.append(
            HouseholdAccount(
                account_ref=str(
                    uuid5(ACCOUNT_NS, f"schwab:{a.accountNumber}")
                ),
                source="schwab",
            )
        )

    vendor_mappings = HouseholdVendorMappings(
        schwab=HouseholdVendorSchwab(
            master_account=vendor.masterAccountNumber,
            grouping_type="custodial",
        )
    )

    canonical = Household(
        canonical_id=canonical_id,
        display_name=vendor.name,
        primary_source="schwab",
        members=members,
        accounts=accounts,
        vendor_mappings=vendor_mappings,
        reconciliation=None,
    )
    note = ReconciliationNote(
        vendor="schwab",
        canonical_type="Household",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=["single_vendor_no_reconciliation"],
    )
    return canonical, note


def from_canonical_household(
    canonical: Household,
    vendor: str = "schwab",
) -> tuple[Optional[SchwabMasterAccount], ReconciliationNote]:
    """Reverse. Returns `(None, note)` if Schwab mapping absent."""
    sc = (
        canonical.vendor_mappings.schwab
        if canonical.vendor_mappings
        else None
    )
    note = ReconciliationNote(
        vendor="schwab",
        canonical_type="Household",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    if sc is None:
        return None, note

    holders = [
        SchwabLinkedAccountHolder(
            accountHolderId=m.client_ref,
            role=REVERSE_ENUM_MAPPINGS["role"][m.role],
        )
        for m in canonical.members
        if m.source == "schwab"
    ]

    def _digits_8(ref: str) -> str:
        d = "".join(c for c in ref if c.isdigit())[:8]
        return d.rjust(8, "0") if d else "00000000"

    accts = [
        SchwabLinkedAccount(accountNumber=_digits_8(a.account_ref))
        for a in canonical.accounts
        if a.source == "schwab"
    ]
    vendor_model = SchwabMasterAccount(
        masterAccountNumber=sc.master_account,
        name=canonical.display_name,
        linkedAccountHolders=holders,
        linkedAccounts=accts,
    )
    return vendor_model, note
