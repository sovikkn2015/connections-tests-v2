"""
Smarsh Archiver — Pydantic v2 models for FINRA Rule 17a-4 archiving.

SmarshConfig: API endpoint, key reference, firm ID, archive types.
ArchiveRecord: Immutable record with SHA-256 content hash.
ArchiveResult: Success/failure from archive operation.

No credentials in code (Rule 20). api_key_ref points to Vault path.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class ContentType(str, Enum):
    """Archivable communication types per FINRA 17a-4."""
    agent_response = "agent_response"
    meeting_summary = "meeting_summary"
    research_brief = "research_brief"
    trade_confirmation = "trade_confirmation"


class SmarshConfig(BaseModel):
    """Smarsh API configuration. No credentials — api_key_ref is a Vault path."""
    api_endpoint: str = Field(
        default="https://api.smarsh.com/v2/archive",
        description="Smarsh REST API endpoint",
    )
    api_key_ref: str = Field(
        default="vault://secrets/smarsh/api-key",
        description="Vault path to Smarsh API key (Rule 20: no creds in code)",
    )
    firm_id: str = Field(..., min_length=1, description="Firm identifier for Smarsh")
    archive_types: list[ContentType] = Field(
        default_factory=lambda: list(ContentType),
        description="Content types to archive",
    )


class ArchiveRecord(BaseModel):
    """Immutable archive record with SHA-256 integrity hash."""
    record_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Internal archive record ID",
    )
    content_hash: str = Field(
        ...,
        pattern=r"^[a-f0-9]{64}$",
        description="SHA-256 hash of archived content",
    )
    content_type: ContentType = Field(..., description="Type of archived communication")
    archived_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="ISO 8601 archive timestamp",
    )
    retention_years: int = Field(default=6, ge=1, description="Retention period (FINRA 17a-4: 6yr min)")
    smarsh_receipt_id: Optional[str] = Field(
        default=None, description="Receipt ID from Smarsh API confirmation",
    )
    firm_id: Optional[str] = Field(default=None, description="Firm that owns this record")
    metadata: Optional[dict] = Field(default=None, description="Additional metadata")


class ArchiveResult(BaseModel):
    """Result of an archive operation."""
    success: bool = Field(..., description="Whether archiving succeeded")
    receipt_id: Optional[str] = Field(default=None, description="Smarsh receipt ID on success")
    record_id: Optional[str] = Field(default=None, description="Internal record ID")
    error: Optional[str] = Field(default=None, description="Error message on failure")
