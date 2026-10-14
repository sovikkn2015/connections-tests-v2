"""
Salesforce FSC → canonical Household translator (T2).

Container model. `grouping_type="relationship"` CONST.
Members at canonical top level (NOT inside vendor_mappings).
`client_ref` / `account_ref` are `str` per M3.
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
    HouseholdVendorSFSC,
)

from m7_schema_translators.errors import UnknownEnumValue
from m7_schema_translators.salesforce_fsc.models import (
    SalesforceFSCHousehold,
    SalesforceFSCHouseholdMember,
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
VENDOR_API_VERSION: str = "v59.0"

LOSSY_FIELDS: frozenset[str] = frozenset(
    {"sf_internal_fields", "sf_household_record_type_metadata"}
)

REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "FinServ__Household__c.internal_metadata",
        "FinServ__Household__c.record_type_info",
    }
)


_ROLE_FWD: dict[str, str] = {
    "Primary": "primary",
    "Spouse": "spouse",
    "Dependent": "dependent",
    "Trustee": "trustee",
    "Beneficiary": "beneficiary",
    "Authorized Signer": "authorized_signer",
    "Power Of Attorney": "power_of_attorney",
}
_ROLE_REV: dict[str, str] = {v: k for k, v in _ROLE_FWD.items()}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType[str, str]] = (
    MappingProxyType({"role": MappingProxyType(_ROLE_FWD)})
)
REVERSE_ENUM_MAPPINGS: MappingProxyType[
    str, MappingProxyType[str, str]
] = MappingProxyType({"role": MappingProxyType(_ROLE_REV)})


def _map_role(vendor_role: str) -> str:
    mapping = ENUM_MAPPINGS["role"]
    if vendor_role not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor="salesforce_fsc",
            canonical_type="Household",
            field_path="members[].role",
            details={
                "vendor_value": vendor_role,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[vendor_role]


def _split_picklist(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [s.strip() for s in value.split(";") if s.strip()]


def to_canonical_household(
    vendor_payload: dict,
) -> tuple[Household, ReconciliationNote]:
    """Single-vendor SF FSC → canonical Household. `reconciliation=None` (AC7.8)."""
    vendor = SalesforceFSCHousehold(**vendor_payload)
    validate_vendor_id_chars(
        vendor.household_id,
        vendor="salesforce_fsc",
        canonical_type="Household",
        field_path="FinServ__Household__c.Id",
    )
    canonical_id = uuid5(HOUSEHOLD_NS, f"salesforce_fsc:{vendor.household_id}")

    members: list[HouseholdMember] = []
    for m in vendor.members:
        validate_vendor_id_chars(
            m.account_id,
            vendor="salesforce_fsc",
            canonical_type="Household",
            field_path="members[].AccountId",
        )
        members.append(
            HouseholdMember(
                client_ref=str(
                    uuid5(CLIENT_NS, f"salesforce_fsc:{m.account_id}")
                ),
                role=_map_role(m.role),
                source="salesforce_fsc",
            )
        )

    accounts: list[HouseholdAccount] = []
    for aid in _split_picklist(vendor.account_ids):
        accounts.append(
            HouseholdAccount(
                account_ref=str(
                    uuid5(ACCOUNT_NS, f"salesforce_fsc:{aid}")
                ),
                source="salesforce_fsc",
            )
        )

    vendor_mappings = HouseholdVendorMappings(
        salesforce_fsc=HouseholdVendorSFSC(
            household_id=vendor.household_id,
            grouping_type="relationship",
        )
    )

    canonical = Household(
        canonical_id=canonical_id,
        display_name=vendor.name,
        primary_source="salesforce_fsc",
        members=members,
        accounts=accounts,
        vendor_mappings=vendor_mappings,
        reconciliation=None,
    )
    note = ReconciliationNote(
        vendor="salesforce_fsc",
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
    vendor: str = "salesforce_fsc",
) -> tuple[Optional[SalesforceFSCHousehold], ReconciliationNote]:
    """Reverse. Returns `(None, note)` if SF vendor_mappings absent."""
    sf = (
        canonical.vendor_mappings.salesforce_fsc
        if canonical.vendor_mappings
        else None
    )
    note = ReconciliationNote(
        vendor="salesforce_fsc",
        canonical_type="Household",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    if sf is None:
        return None, note

    sf_members = [
        SalesforceFSCHouseholdMember(
            account_id=m.client_ref,
            role=REVERSE_ENUM_MAPPINGS["role"][m.role],
        )
        for m in canonical.members
        if m.source == "salesforce_fsc"
    ]
    sf_account_ids: Optional[str] = None
    sf_accounts = [
        a for a in canonical.accounts if a.source == "salesforce_fsc"
    ]
    if sf_accounts:
        sf_account_ids = ";".join(a.account_ref for a in sf_accounts)

    vendor_model = SalesforceFSCHousehold(
        household_id=sf.household_id,
        name=canonical.display_name,
        members=sf_members,
        account_ids=sf_account_ids,
    )
    return vendor_model, note
