"""
Gap 1 — Principal review queue (FINRA 2210, steering rule 17).

See .kiro/specs/gap1-reg-bi-doc-generator.md R9.

The real queue bus (SQS / Kafka) lives in a separate module. Gap 1
exposes a ``PrincipalReviewQueue`` Protocol; the hosting service wires
the real bus. ``InMemoryPrincipalReviewQueue`` is the Phase-3 test
default.

Anti-tipping-off: queue entries NEVER contain advisor-visible flags
beyond what ``AidClaims`` already expose (see R9.5). SAR / BSA/AML
routing is Gap 4's concern.
"""

from __future__ import annotations

from datetime import datetime
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from m5_config_loader import (
    PrincipalReviewMode,
    RegistrationType,
    TimeoutAction,
)


class PrincipalReviewQueueEntry(BaseModel):
    """Frozen queue entry shape (R9.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    entry_id: UUID
    trace_id: str = Field(min_length=1, max_length=200)
    document_id: UUID
    firm_id: str = Field(min_length=1, max_length=128)
    registration_type: RegistrationType
    is_retail: bool
    mode: PrincipalReviewMode
    sla_hours: int = Field(ge=1)
    timeout_action: TimeoutAction
    rendered_content_sha256: Optional[str] = None
    submitted_at: datetime

    @field_validator("submitted_at")
    @classmethod
    def _require_tz_aware(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("submitted_at must be timezone-aware")
        return v

    @field_validator("rendered_content_sha256")
    @classmethod
    def _validate_hex(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if len(v) != 64 or not all(c in "0123456789abcdef" for c in v):
            raise ValueError(
                "rendered_content_sha256 must be 64 lowercase hex chars"
            )
        return v


@runtime_checkable
class PrincipalReviewQueue(Protocol):
    """FINRA 2210 principal review queue interface."""

    def enqueue(self, entry: PrincipalReviewQueueEntry) -> None: ...


class InMemoryPrincipalReviewQueue:
    """Thread-naive in-memory queue stub (fresh per test / pod)."""

    def __init__(self) -> None:
        self._entries: list[PrincipalReviewQueueEntry] = []

    def enqueue(self, entry: PrincipalReviewQueueEntry) -> None:
        self._entries.append(entry)

    @property
    def entries(self) -> tuple[PrincipalReviewQueueEntry, ...]:
        return tuple(self._entries)
