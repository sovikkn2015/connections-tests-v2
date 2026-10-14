"""Round-trip tests for Smarsh Archive interaction-summary translator."""

from __future__ import annotations

from uuid import uuid4

from m3_schema_registry import InteractionSummary

from m7_schema_translators.smarsh.interaction_summary import (
    from_canonical_interaction_summary,
    to_canonical_interaction_summary,
)


def _smarsh_payload() -> dict:
    return {
        "interaction_id": "SM-2026-001",
        "client_ref": str(uuid4()),
        "advisor_ref": str(uuid4()),
        "household_ref": None,
        "channel": "email",
        "interaction_type": "email",
        "interaction_date": "2026-04-30",
        "start_time": "2026-04-30T09:00:00Z",
        "end_time": "2026-04-30T09:10:00Z",
        "duration_minutes": 10,
        "summary": "Quarterly review email with performance update.",
        "topics_discussed": ["performance", "retirement"],
        "action_items": [
            {
                "description": "Send updated proposal",
                "owner": "Alice Advisor",
                "due_date": "2026-05-07",
            }
        ],
        "attendees": [
            {"name": "Bob Client", "email": None, "role": "client"},
            {"name": "Alice Advisor", "email": None, "role": "advisor"},
        ],
        "sentiment": "positive",
        "next_meeting_date": "2026-08-01",
        "trace_id": "trace-xyz",
        "created_at": "2026-04-30T09:00:00Z",
        "updated_at": "2026-04-30T09:10:00Z",
    }


class TestSmarshInteractionSummaryRoundtrip:
    def test_forward_produces_canonical(self) -> None:
        canonical, note = to_canonical_interaction_summary(_smarsh_payload())
        assert isinstance(canonical, InteractionSummary)
        assert canonical.source_system == "smarsh"
        assert canonical.source_id == "SM-2026-001"
        assert canonical.summary.startswith("Quarterly")
        assert len(canonical.action_items) == 1
        assert canonical.action_items[0].assigned_to == "Alice Advisor"
        assert len(canonical.attendees) == 2
        assert canonical.attendees[0].role == "client"
        assert note.direction == "to_canonical"
        assert note.canonical_type == "InteractionSummary"

    def test_roundtrip_preserves_core_fields(self) -> None:
        canonical, _ = to_canonical_interaction_summary(_smarsh_payload())
        vendor, note = from_canonical_interaction_summary(canonical)
        assert vendor.interaction_id == "SM-2026-001"
        assert vendor.summary == canonical.summary
        assert vendor.trace_id == canonical.trace_id
        assert note.direction == "from_canonical"
        assert "compliance_review_vendor_has_no_equivalent" in note.fields_dropped

    def test_missing_owner_on_action_item_defaults_to_unassigned(
        self,
    ) -> None:
        payload = _smarsh_payload()
        payload["action_items"][0]["owner"] = None
        canonical, _ = to_canonical_interaction_summary(payload)
        assert canonical.action_items[0].assigned_to == "unassigned"
