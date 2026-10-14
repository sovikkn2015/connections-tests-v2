"""
Orion → canonical Household translator (T6).

Container model. `grouping_type="portfolio_management"` CONST.
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
    HouseholdVendorOrion,
)

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.orion.models import (
    OrionHousehold,
    OrionHouseholdMember,
    OrionLinkedAccount,
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
VENDOR_API_VERSION: str = "v2.0"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "orion_portfolio_ids",
        "orion_benchmark_assignment",
        "orion_composite_membership",
    }
)
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "OrionHousehold.portfolioIds",
        "OrionHousehold.benchmarkAssignment",
        "OrionHousehold.compositeMembership",
    }
)


# Orion uses lowercase role names.
_ROLE_FWD: dict[str, str] = {
    "primary": "primary",
    "spouse": "spouse",
    "dependent": "dependent",
    "trustee": "trustee",
    "beneficiary": "beneficiary",
    "authorized_signer": "authorized_signer",
    "power_of_attorney": "power_of_attorney",
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
            vendor="orion",
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
    """Single-vendor Orion → canonical Household. `reconciliation=None`."""
    vendor = OrionHousehold(**vendor_payload)
    validate_vendor_id_chars(
        vendor.householdId,
        vendor="orion",
        canonical_type="Household",
        field_path="OrionHousehold.householdId",
    )

    canonical_id = uuid5(HOUSEHOLD_NS, f"orion:{vendor.householdId}")

    members: list[HouseholdMember] = []
    for m in vendor.members:
        validate_vendor_id_chars(
            m.clientId,
            vendor="orion",
            canonical_type="Household",
            field_path="members[].clientId",
        )
        members.append(
            HouseholdMember(
                client_ref=str(uuid5(CLIENT_NS, f"orion:{m.clientId}")),
                role=_map_role(m.role),
                source="orion",
            )
        )

    accounts: list[HouseholdAccount] = []
    for a in vendor.linkedAccounts:
        validate_vendor_id_chars(
            a.accountId,
            vendor="orion",
            canonical_type="Household",
            field_path="linkedAccounts[].accountId",
        )
        accounts.append(
            HouseholdAccount(
                account_ref=str(
                    uuid5(ACCOUNT_NS, f"orion:{a.accountId}")
                ),
                source="orion",
            )
        )

    vendor_mappings = HouseholdVendorMappings(
        orion=HouseholdVendorOrion(
            household_id=vendor.householdId,
            grouping_type="portfolio_management",
        )
    )

    canonical = Household(
        canonical_id=canonical_id,
        display_name=vendor.householdName,
        primary_source="orion",
        members=members,
        accounts=accounts,
        vendor_mappings=vendor_mappings,
        reconciliation=None,
    )
    note = ReconciliationNote(
        vendor="orion",
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
    vendor: str = "orion",
) -> tuple[Optional[OrionHousehold], ReconciliationNote]:
    """Reverse. Returns `(None, note)` if Orion mapping absent."""
    orion = (
        canonical.vendor_mappings.orion
        if canonical.vendor_mappings
        else None
    )
    note = ReconciliationNote(
        vendor="orion",
        canonical_type="Household",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    if orion is None:
        return None, note

    orion_members = [
        OrionHouseholdMember(
            clientId=m.client_ref,
            role=REVERSE_ENUM_MAPPINGS["role"][m.role],
        )
        for m in canonical.members
        if m.source == "orion"
    ]
    orion_accounts = [
        OrionLinkedAccount(accountId=a.account_ref)
        for a in canonical.accounts
        if a.source == "orion"
    ]
    vendor_model = OrionHousehold(
        householdId=orion.household_id,
        householdName=canonical.display_name,
        members=orion_members,
        linkedAccounts=orion_accounts,
    )
    return vendor_model, note
