"""Smarsh vendor payload models.

The M11-REST Smarsh Archive adapter exposes ``smarsh.search`` (unstructured
transcripts, no canonical shape) and ``smarsh.get_interaction_summary`` which
returns a structured meeting / email / chat record. This module models the
latter.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SmarshAttendee(BaseModel):
    """Attendee row in the archive summary."""

    model_config = ConfigDict(extra="forbid")


    name: str
    email: Optional[str] = None
    role: Optional[str] = None


class SmarshActionItem(BaseModel):
    """Action item extracted by Smarsh transcription or advisor entry."""

    model_config = ConfigDict(extra="forbid")

    description: str
    owner: Optional[str] = None
    due_date: Optional[date] = None


class SmarshInteraction(BaseModel):
    """Smarsh Archive interaction record."""

    model_config = ConfigDict(extra="forbid")

    interaction_id: str = Field(description="Smarsh native interaction ID.")
    client_ref: UUID = Field(description="Canonical Client UUID.")
    advisor_ref: UUID = Field(description="Canonical Advisor UUID.")
    household_ref: Optional[UUID] = None
    channel: str = Field(
        description=(
            "Smarsh channel id: email, slack, teams, whatsapp, sms, voice, "
            "video, chat."
        )
    )
    interaction_type: str = Field(
        description=(
            "meeting, phone_call, email, chat, video_call, in_person."
        )
    )
    interaction_date: date
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    duration_minutes: Optional[int] = Field(default=None, ge=0)
    summary: str = Field(
        description=(
            "Agent-generated summary (already MNPI-filtered upstream)."
        )
    )
    topics_discussed: list[str] = Field(default_factory=list)
    action_items: list[SmarshActionItem] = Field(default_factory=list)
    attendees: list[SmarshAttendee] = Field(default_factory=list)
    sentiment: Optional[str] = None
    next_meeting_date: Optional[date] = None
    trace_id: str
    created_at: datetime
    updated_at: datetime


__all__ = ["SmarshInteraction", "SmarshAttendee", "SmarshActionItem"]
