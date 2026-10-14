"""
Salesforce FSC → canonical Client translator (T1).

Bidirectional: `to_canonical_client` and `from_canonical_client`.

UUID namespace: `CLIENT_NS` — `Client.canonical_id = uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")`.

M3 type alignment:
- Client.canonical_id: UUID (bare uuid5)
- Client.firm_id:      UUID (bare uuid5)
- Client.advisor_ref:  Optional[UUID]
- Client.household_ref: Optional[UUID]
- Client.accounts:     list[UUID]
- Client.source_id:    str (raw vendor ID)
"""

from __future__ import annotations

from types import MappingProxyType
from typing import Optional
from uuid import UUID, uuid5

from m3_schema_registry import (
    Client,
    ClientVendorMappings,
    ClientVendorSalesforceFSC,
)

from m7_schema_translators.errors import (
    MissingRequiredField,
    UnknownEnumValue,
)
from m7_schema_translators.salesforce_fsc.models import (
    SalesforceFSCAccountContact,
)
from m7_schema_translators.shared.namespaces import (
    ACCOUNT_NS,
    ADVISOR_NS,
    CLIENT_NS,
    FIRM_NS,
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
    {
        "salesforce_fsc_metadata",
        "created_by_salesforce",
        "last_activity_date_salesforce",
    }
)

REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {
        "Account.FinServ__CreatedBy.Name",
        "Account.LastActivityDate",
        "Account.FinServ__InternalMetadata__c",
    }
)


_CLIENT_TYPE_FWD: dict[str, str] = {
    "PersonAccount": "individual",
    "Business Account": "entity",
    "Trust": "trust",
}
_CLIENT_TYPE_REV: dict[str, str] = {v: k for k, v in _CLIENT_TYPE_FWD.items()}

_KYC_STATUS_FWD: dict[str, str] = {
    "Verified": "verified",
    "Pending": "pending",
    "Expired": "expired",
    "Failed": "failed",
}
_KYC_STATUS_REV: dict[str, str] = {v: k for k, v in _KYC_STATUS_FWD.items()}


ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType[str, str]] = (
    MappingProxyType(
        {
            "client_type": MappingProxyType(_CLIENT_TYPE_FWD),
            "kyc_status": MappingProxyType(_KYC_STATUS_FWD),
        }
    )
)

REVERSE_ENUM_MAPPINGS: MappingProxyType[
    str, MappingProxyType[str, str]
] = MappingProxyType(
    {
        "client_type": MappingProxyType(_CLIENT_TYPE_REV),
        "kyc_status": MappingProxyType(_KYC_STATUS_REV),
    }
)


def _split_picklist(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [s.strip() for s in value.split(";") if s.strip()]


def _map_enum(
    field: str, vendor_value: str, vendor: str, canonical_type: str
) -> str:
    mapping = ENUM_MAPPINGS[field]
    if vendor_value not in mapping:
        raise UnknownEnumValue(
            reason_code="unknown_enum_value",
            vendor=vendor,
            canonical_type=canonical_type,
            field_path=field,
            details={
                "vendor_value": vendor_value,
                "valid_values": sorted(mapping.keys()),
            },
        )
    return mapping[vendor_value]


def to_canonical_client(
    vendor_payload: dict,
) -> tuple[Client, ReconciliationNote]:
    """Translate SF FSC Account+Contact payload → canonical Client."""
    vendor = SalesforceFSCAccountContact(**vendor_payload)

    validate_vendor_id_chars(
        vendor.account_id,
        vendor="salesforce_fsc",
        canonical_type="Client",
        field_path="Account.Id",
    )
    if not vendor.firm_id:
        raise MissingRequiredField(
            reason_code="missing_required_field",
            vendor="salesforce_fsc",
            canonical_type="Client",
            field_path="Account.FinServ__FirmId__c",
            details={"field_name": "firm_id"},
        )

    canonical_id = uuid5(CLIENT_NS, f"salesforce_fsc:{vendor.account_id}")
    firm_id = uuid5(FIRM_NS, vendor.firm_id)

    advisor_ref: Optional[UUID] = None
    if vendor.owner_id:
        advisor_ref = uuid5(ADVISOR_NS, f"salesforce_fsc:{vendor.owner_id}")

    household_ref: Optional[UUID] = None
    if vendor.household_id:
        household_ref = uuid5(
            HOUSEHOLD_NS, f"salesforce_fsc:{vendor.household_id}"
        )

    accounts_list: list[UUID] = []
    notes: list[str] = []
    for aid in _split_picklist(vendor.account_ids):
        accounts_list.append(uuid5(ACCOUNT_NS, f"salesforce_fsc:{aid}"))
    if accounts_list:
        notes.append("salesforce_fsc_multi_picklist_split")

    client_type = _map_enum(
        "client_type", vendor.record_type_name, "salesforce_fsc", "Client"
    )
    kyc_status: Optional[str] = None
    if vendor.kyc_status is not None:
        kyc_status = _map_enum(
            "kyc_status", vendor.kyc_status, "salesforce_fsc", "Client"
        )

    investment_objectives = _split_picklist(vendor.investment_objectives)

    vendor_mappings = ClientVendorMappings(
        salesforce_fsc=ClientVendorSalesforceFSC(
            account_id=vendor.account_id,
            contact_id=vendor.contact_id,
            person_account=vendor.person_account,
        )
    )

    if vendor.record_type_name in {"Business Account", "Trust"}:
        notes.append("salesforce_fsc_business_account_no_contact")

    canonical = Client(
        canonical_id=canonical_id,
        display_name=vendor.name,
        client_type=client_type,
        first_name=vendor.first_name,
        last_name=vendor.last_name,
        email=vendor.email,
        phone=vendor.phone,
        date_of_birth=vendor.birthdate,
        ssn_last_four=vendor.last_ssn_digits,
        tax_id=vendor.tax_id,
        risk_tolerance=vendor.risk_tolerance,
        investment_objectives=investment_objectives,
        time_horizon=vendor.time_horizon,
        annual_income_range=vendor.annual_income,
        net_worth_range=vendor.net_worth,
        liquid_net_worth_range=vendor.liquid_net_worth,
        tax_bracket=vendor.tax_bracket,
        advisor_ref=advisor_ref,
        firm_id=firm_id,
        household_ref=household_ref,
        archetype=vendor.client_archetype,
        jurisdiction=vendor.jurisdiction,
        accounts=accounts_list,
        kyc_status=kyc_status,
        kyc_verified_date=vendor.kyc_last_completed,
        pii_classification=vendor.pii_classification or "confidential",
        vendor_mappings=vendor_mappings,
        reconciliation=None,
        source_system="salesforce_fsc",
        source_id=vendor.account_id,
        created_at=vendor.created_date,
        updated_at=vendor.last_modified_date,
    )

    note = ReconciliationNote(
        vendor="salesforce_fsc",
        canonical_type="Client",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=sorted(notes),
    )
    return canonical, note


def _rev_enum(field: str, canonical_value: str) -> str:
    return REVERSE_ENUM_MAPPINGS[field][canonical_value]


def from_canonical_client(
    canonical: Client,
) -> tuple[SalesforceFSCAccountContact, ReconciliationNote]:
    """Translate canonical Client → SF FSC Account+Contact shape (reverse)."""
    sf = (
        canonical.vendor_mappings.salesforce_fsc
        if canonical.vendor_mappings
        else None
    )
    account_id = (sf.account_id if sf else None) or canonical.source_id

    record_type_name = _rev_enum("client_type", canonical.client_type)

    kyc_rev: Optional[str] = None
    if canonical.kyc_status is not None:
        kyc_rev = _rev_enum("kyc_status", canonical.kyc_status)

    account_ids_str: Optional[str] = None
    if canonical.accounts:
        account_ids_str = ";".join(str(a) for a in canonical.accounts)

    inv_obj = ";".join(canonical.investment_objectives) or None

    vendor_model = SalesforceFSCAccountContact(
        account_id=account_id,
        name=canonical.display_name,
        record_type_name=record_type_name,
        owner_id=None,
        created_date=canonical.created_at,
        last_modified_date=canonical.updated_at,
        firm_id=str(canonical.firm_id),
        household_id=str(canonical.household_ref)
        if canonical.household_ref
        else None,
        client_archetype=canonical.archetype,
        jurisdiction=canonical.jurisdiction,
        account_ids=account_ids_str,
        kyc_status=kyc_rev,
        kyc_last_completed=canonical.kyc_verified_date,
        last_ssn_digits=canonical.ssn_last_four,
        tax_id=canonical.tax_id,
        risk_tolerance=canonical.risk_tolerance,
        investment_objectives=inv_obj,
        time_horizon=canonical.time_horizon,
        annual_income=canonical.annual_income_range,
        net_worth=canonical.net_worth_range,
        liquid_net_worth=canonical.liquid_net_worth_range,
        tax_bracket=canonical.tax_bracket,
        pii_classification=canonical.pii_classification,
        person_account=sf.person_account if sf else None,
        contact_id=sf.contact_id if sf else None,
        first_name=canonical.first_name,
        last_name=canonical.last_name,
        email=canonical.email,
        phone=canonical.phone,
        birthdate=canonical.date_of_birth,
    )

    note = ReconciliationNote(
        vendor="salesforce_fsc",
        canonical_type="Client",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note
