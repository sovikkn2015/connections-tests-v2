"""
Memory Service — Pydantic v2 models for 6-layer memory architecture.

MemoryLayer: L1-L6 enum.
MemoryEntry: entry with layer, client/advisor IDs, MNPI tags, TTL.
MemoryQuery: query with layer filter, archetype/role filter for MNPI.

MNPI filtering: entries tagged with mnpi_tags, filtered on read
based on caller's archetype/role.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class MemoryLayer(str, Enum):
    """6-layer memory architecture per ARCH-09."""
    L1 = "L1"  # Working Memory — Redis, 8hr TTL
    L2 = "L2"  # Short-Term Memory — DynamoDB/PostgreSQL, 7 days
    L3 = "L3"  # Episodic Memory — DynamoDB+vector, 2 years
    L4 = "L4"  # Semantic Memory — pgvector/Pinecone, permanent
    L5 = "L5"  # Procedural Memory — file-based JSON/S3, permanent
    L6 = "L6"  # Compliance Memory — S3 Object Lock WORM, 6+ years (via M10)


class MemoryEntry(BaseModel):
    """Single memory entry with MNPI tagging for filtered reads."""
    entry_id: str = Field(
        default_factory=lambda: str(uuid.uuid4()),
        description="Unique entry identifier",
    )
    layer: MemoryLayer = Field(..., description="Memory layer (L1-L6)")
    client_id: Optional[str] = Field(default=None, description="Client this entry relates to")
    advisor_id: Optional[str] = Field(default=None, description="Advisor who created/owns this entry")
    content: str = Field(..., min_length=1, description="Memory content")
    metadata: dict = Field(default_factory=dict, description="Additional metadata")
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(),
        description="Entry creation timestamp",
    )
    expires_at: Optional[str] = Field(
        default=None,
        description="Expiry timestamp (L1: 8hr, L2: 7d, L3+: None)",
    )
    archetype: Optional[str] = Field(
        default=None,
        description="Required archetype to read this entry (MNPI filter)",
    )
    role: Optional[str] = Field(
        default=None,
        description="Required role to read this entry (MNPI filter)",
    )
    mnpi_tags: list[str] = Field(
        default_factory=list,
        description="MNPI classification tags for filtering on read",
    )
    channel: Optional[str] = Field(
        default=None,
        description="Channel this entry was created from (cross-channel support)",
    )


class MemoryQuery(BaseModel):
    """Query for reading memory entries with MNPI filtering."""
    client_id: str = Field(..., min_length=1, description="Client to query")
    layers: list[MemoryLayer] = Field(
        default_factory=lambda: [MemoryLayer.L1],
        description="Layers to query",
    )
    limit: int = Field(default=10, ge=1, le=100, description="Max entries to return")
    archetype_filter: Optional[str] = Field(
        default=None,
        description="Caller's archetype for MNPI filtering",
    )
    role_filter: Optional[str] = Field(
        default=None,
        description="Caller's role for MNPI filtering",
    )
    channel_filter: Optional[str] = Field(
        default=None,
        description="Filter by channel",
    )
