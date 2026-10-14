"""
Multi-vendor Household merger (Task 14).

Combines SF FSC + Orion + Schwab single-vendor Households into one canonical
Household with populated `reconciliation`. Per AC7.2, AC7.5, AC7.7-AC7.9.

Caller provides `last_reconciled` — M7 NEVER calls `datetime.utcnow()`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from m3_schema_registry import (
    Household,
    HouseholdAccount,
    HouseholdMember,
    HouseholdVendorMappings,
    Reconciliation,
)

from m7_schema_translators.orion.household import (
    to_canonical_household as _or_to_hh,
)
from m7_schema_translators.salesforce_fsc.household import (
    to_canonical_household as _sf_to_hh,
)
from m7_schema_translators.schwab.household import (
    to_canonical_household as _sc_to_hh,
)
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)


SCHEMA_VERSION: str = "0.1.0"


def _format_missing(client_ref: str, role: str, vendor_a: str, vendor_b: str) -> str:
    """AC7.5 exact literal — missing member."""
    return (
        f"member (client:{client_ref}, role:{role}) "
        f"present in {vendor_a} but missing in {vendor_b}"
    )


def _format_role_mismatch(
    client_ref: str, vendor_a: str, role_a: str, vendor_b: str, role_b: str
) -> str:
    """AC7.5 exact literal — role mismatch (em-dash)."""
    return (
        f"role mismatch for client:{client_ref} "
        f"— {vendor_a}:{role_a} vs {vendor_b}:{role_b}"
    )


def _compare_household_members(
    per_vendor: Mapping[str, list[HouseholdMember]],
) -> list[str]:
    """Return sorted discrepancies across the given vendors. vendor_a < vendor_b."""
    vendors = sorted(per_vendor.keys())
    discrepancies: list[str] = []

    for i, va in enumerate(vendors):
        for vb in vendors[i + 1 :]:
            members_a = per_vendor[va]
            members_b = per_vendor[vb]
            by_ref_a = {m.client_ref: m for m in members_a}
            by_ref_b = {m.client_ref: m for m in members_b}

            for ref, ma in by_ref_a.items():
                if ref not in by_ref_b:
                    discrepancies.append(_format_missing(ref, ma.role, va, vb))
            for ref, mb in by_ref_b.items():
                if ref not in by_ref_a:
                    discrepancies.append(_format_missing(ref, mb.role, vb, va))
            shared = set(by_ref_a) & set(by_ref_b)
            for ref in shared:
                ma = by_ref_a[ref]
                mb = by_ref_b[ref]
                if ma.role != mb.role:
                    discrepancies.append(
                        _format_role_mismatch(ref, va, ma.role, vb, mb.role)
                    )

    return sorted(discrepancies)


def to_canonical_household_multi(
    payloads: Mapping[str, dict],
    last_reconciled: datetime,
) -> tuple[Household, ReconciliationNote]:
    """Merge any subset of {salesforce_fsc, orion, schwab} → canonical Household.

    Multi-vendor → `reconciliation` populated (AC7.4, AC7.8).
    Caller provides `last_reconciled`. M7 never reads the clock.
    """
    valid_vendors = {"salesforce_fsc", "orion", "schwab"}
    bad = set(payloads) - valid_vendors
    if bad:
        raise ValueError(f"unsupported vendor(s) in payloads: {sorted(bad)}")
    if not payloads:
        raise ValueError("at least one vendor payload required")

    per_vendor_hh: dict[str, Household] = {}
    for vendor, payload in payloads.items():
        if vendor == "salesforce_fsc":
            hh, _ = _sf_to_hh(payload)
        elif vendor == "orion":
            hh, _ = _or_to_hh(payload)
        else:
            hh, _ = _sc_to_hh(payload)
        per_vendor_hh[vendor] = hh

    all_members: list[HouseholdMember] = []
    per_vendor_members: dict[str, list[HouseholdMember]] = {}
    for vendor, hh in per_vendor_hh.items():
        per_vendor_members[vendor] = list(hh.members)
        all_members.extend(hh.members)
    all_members.sort(key=lambda m: (m.client_ref, m.source))

    all_accounts: list[HouseholdAccount] = []
    for hh in per_vendor_hh.values():
        all_accounts.extend(hh.accounts)
    all_accounts.sort(key=lambda a: (a.account_ref, a.source))

    merged_mappings = HouseholdVendorMappings(
        salesforce_fsc=(
            per_vendor_hh["salesforce_fsc"].vendor_mappings.salesforce_fsc
            if "salesforce_fsc" in per_vendor_hh
            else None
        ),
        orion=(
            per_vendor_hh["orion"].vendor_mappings.orion
            if "orion" in per_vendor_hh
            else None
        ),
        schwab=(
            per_vendor_hh["schwab"].vendor_mappings.schwab
            if "schwab" in per_vendor_hh
            else None
        ),
    )

    primary_source = sorted(per_vendor_hh.keys())[0]
    primary_hh = per_vendor_hh[primary_source]

    discrepancies = _compare_household_members(per_vendor_members)
    sources_agree = not discrepancies

    reconciliation = Reconciliation(
        sources_agree=sources_agree,
        discrepancies=discrepancies,
        last_reconciled=last_reconciled,
    )

    canonical = Household(
        canonical_id=primary_hh.canonical_id,
        display_name=primary_hh.display_name,
        primary_source=primary_source,
        members=all_members,
        accounts=all_accounts,
        vendor_mappings=merged_mappings,
        reconciliation=reconciliation,
    )
    note = ReconciliationNote(
        vendor="multi",
        canonical_type="Household",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version="multi",
        translator_schema_version=SCHEMA_VERSION,
        notes=["multi_vendor_reconciliation_performed"],
    )
    return canonical, note
