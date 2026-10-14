"""
Client Service Specialist — Pydantic v2 models.

ClientServiceRequest: incoming request with type routing.
ClientServiceResponse: response with MNPI-filtered flag and sources.
MeetingPrepBrief: structured meeting preparation output.

All data access via M6 gateway REST calls (no direct vendor access).
All responses MNPI-filtered (M4 runs in M6 pipeline).
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class RequestType(str, Enum):
    """Client service request types."""
    meeting_prep = "meeting_prep"
    portfolio_review = "portfolio_review"
    client_summary = "client_summary"
    general = "general"


class ClientServiceRequest(BaseModel):
    """Incoming client service request."""
    client_id: str = Field(..., min_length=1, description="Client identifier")
    request_type: RequestType = Field(..., description="Type of service request")
    channel: str = Field(default="web", description="Originating channel (slack, teams, web, whatsapp)")
    advisor_id: str = Field(..., min_length=1, description="Requesting advisor ID")
    query: Optional[str] = Field(default=None, description="Free-text query for general requests")
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Distributed trace ID",
    )


class ClientServiceResponse(BaseModel):
    """Client service response with MNPI-filtered flag."""
    response_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique response identifier",
    )
    content: str = Field(..., description="Response content (MNPI-filtered)")
    sources_used: list[str] = Field(
        default_factory=list,
        description="Data sources accessed via M6 gateway",
    )
    mnpi_filtered: bool = Field(
        default=True,
        description="True — all responses pass through M4 MNPI filter in M6 pipeline",
    )
    channel: str = Field(default="web", description="Channel this response is for")
    trace_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Links to M10 audit trail",
    )
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Response timestamp",
    )


class MeetingPrepBrief(BaseModel):
    """Structured meeting preparation brief."""
    client_name: str = Field(..., description="Client display name")
    upcoming_meetings: list[str] = Field(
        default_factory=list,
        description="Upcoming meeting descriptions",
    )
    portfolio_highlights: list[str] = Field(
        default_factory=list,
        description="Key portfolio highlights (MNPI-filtered)",
    )
    action_items: list[str] = Field(
        default_factory=list,
        description="Recommended action items for the meeting",
    )
    compliance_flags: list[str] = Field(
        default_factory=list,
        description="Compliance items to address (from M2 OPA, not LLM)",
    )
