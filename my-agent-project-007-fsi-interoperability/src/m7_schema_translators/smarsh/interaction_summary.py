"""Smarsh → canonical InteractionSummary translator.

Round-trip rules:

* ``canonical_id`` is UUID5 over Smarsh ``interaction_id`` so the same
  vendor record yields the same canonical UUID across replays.
* Attendee + action-item lists round-trip shape-equivalently.
* ``compliance_review`` is left ``None`` -- M4 fills it after the
  canonical record is produced (Rule 17 -- principal review queue).
"""

from __future__ import annotations

from uuid import uuid5

from m3_schema_registry import (
    ActionItem,
    Attendee,
    InteractionSummary,
)

from m7_schema_translators.shared.namespaces import INTERACTION_NS
from m7_schema_translators.shared.reconciliation_note import (
    ReconciliationNote,
)
from m7_schema_translators.shared.vendor_id_validator import (
    validate_vendor_id_chars,
)
from m7_schema_translators.smarsh.models import SmarshInteraction


SCHEMA_VERSION: str = "0.1.0"
VENDOR_API_VERSION: str = "smarsh-archive-v3"

LOSSY_FIELDS: frozenset[str] = frozenset()
REVERSE_LOSSY_FIELDS: frozenset[str] = frozenset(
    {"compliance_review_vendor_has_no_equivalent"}
)


def to_canonical_interaction_summary(
    vendor_payload: dict,
) -> tuple[InteractionSummary, ReconciliationNote]:
    """Translate a Smarsh interaction row to M3 ``InteractionSummary``."""
    vendor = SmarshInteraction(**vendor_payload)
    validate_vendor_id_chars(
        vendor.interaction_id,
        vendor="smarsh",
        canonical_type="InteractionSummary",
        field_path="interaction_id",
    )

    canonical_id = uuid5(INTERACTION_NS, f"smarsh:{vendor.interaction_id}")

    attendees = [
        Attendee(
            name=a.name,
            role=a.role or "other",
        )
        for a in vendor.attendees
    ]
    actions = [
        ActionItem(
            description=ai.description,
            assigned_to=ai.owner or "unassigned",
            due_date=ai.due_date,
        )
        for ai in vendor.action_items
    ]

    canonical = InteractionSummary(
        canonical_id=canonical_id,
        client_ref=vendor.client_ref,
        household_ref=vendor.household_ref,
        advisor_ref=vendor.advisor_ref,
        interaction_type=vendor.interaction_type,
        interaction_date=vendor.interaction_date,
        start_time=vendor.start_time,
        end_time=vendor.end_time,
        duration_minutes=vendor.duration_minutes,
        summary=vendor.summary,
        topics_discussed=list(vendor.topics_discussed),
        action_items=actions,
        attendees=attendees,
        sentiment=vendor.sentiment,
        next_meeting_date=vendor.next_meeting_date,
        crm_write_back=None,
        compliance_review=None,
        channel=vendor.channel,
        trace_id=vendor.trace_id,
        source_system="smarsh",
        source_id=vendor.interaction_id,
        created_at=vendor.created_at,
        updated_at=vendor.updated_at,
    )
    note = ReconciliationNote(
        vendor="smarsh",
        canonical_type="InteractionSummary",
        direction="to_canonical",
        fields_dropped=[],
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return canonical, note


def from_canonical_interaction_summary(
    canonical: InteractionSummary,
) -> tuple[SmarshInteraction, ReconciliationNote]:
    """Reverse canonical ``InteractionSummary`` → Smarsh vendor row."""
    from m7_schema_translators.smarsh.models import (
        SmarshActionItem,
        SmarshAttendee,
    )

    attendees = [
        SmarshAttendee(name=a.name, email=None, role=a.role)
        for a in canonical.attendees
    ]
    actions = [
        SmarshActionItem(
            description=ai.description,
            owner=ai.assigned_to,
            due_date=ai.due_date,
        )
        for ai in canonical.action_items
    ]

    # Smarsh requires an interaction_id; fall back to source_id (round-trip-safe).
    interaction_id = canonical.source_id or str(canonical.canonical_id)

    vendor_model = SmarshInteraction(
        interaction_id=interaction_id,
        client_ref=canonical.client_ref,
        advisor_ref=canonical.advisor_ref,
        household_ref=canonical.household_ref,
        channel=canonical.channel or "email",
        interaction_type=canonical.interaction_type,
        interaction_date=canonical.interaction_date,
        start_time=canonical.start_time,
        end_time=canonical.end_time,
        duration_minutes=canonical.duration_minutes,
        summary=canonical.summary,
        topics_discussed=list(canonical.topics_discussed),
        action_items=actions,
        attendees=attendees,
        sentiment=canonical.sentiment,
        next_meeting_date=canonical.next_meeting_date,
        trace_id=canonical.trace_id,
        created_at=canonical.created_at,
        updated_at=canonical.updated_at,
    )
    note = ReconciliationNote(
        vendor="smarsh",
        canonical_type="InteractionSummary",
        direction="from_canonical",
        fields_dropped=sorted(REVERSE_LOSSY_FIELDS),
        fields_derived=[],
        vendor_schema_version=VENDOR_API_VERSION,
        translator_schema_version=SCHEMA_VERSION,
        notes=[],
    )
    return vendor_model, note


__all__ = [
    "SCHEMA_VERSION",
    "VENDOR_API_VERSION",
    "to_canonical_interaction_summary",
    "from_canonical_interaction_summary",
]
