"""
M10 Audit Logger -- Legal Hold model + exceptions (v0.5.0).

FINRA 4511.04 allows an SEC 17a-4 record's retention to be extended
under legal hold. This module defines the strict ``HoldEntry`` Pydantic
model that the WORM backend writes to its separate registry bucket,
plus the ``LegalHoldError`` + frozen reason vocabulary.

Spec: .kiro/specs/m10-legal-hold-api.md §2.2.

Security invariants:
* ``extra="forbid"`` -- unknown fields rejected.
* ``strict=True`` -- no silent type coercions.
* ``frozen=True`` -- HoldEntry is immutable once constructed.
* ``placed_at`` / ``released_at`` must be timezone-aware UTC.
* ``placed_by`` / ``released_by`` must be SHA-256 hex (actor_id shape).
* ``hold_id`` shape bounded by ``HOLD_ID_PATTERN``.
* ``repr`` / ``str`` redacts ``reason`` so case-detail strings never
  land in logs.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

HOLD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{3,128}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")

# Frozen reason vocabulary. Mirrors the AuditWriteError pattern in
# logger.py.
VALID_LEGAL_HOLD_REASONS: frozenset[str] = frozenset({
    "duplicate_hold_id",
    "target_not_found",
    "hold_not_found",
    "hold_already_released",
    "legal_hold_write_failed",
    "legal_hold_registry_failed",
})


class LegalHoldError(Exception):
    """FINRA 4511.04 legal-hold failure.

    ``reason`` is always one of ``VALID_LEGAL_HOLD_REASONS``.
    ``str(exc) == exc.reason``. No PII, no entry contents, no stack
    trace strings in the message (same discipline as AuditWriteError).
    """

    def __init__(self, reason: str) -> None:
        if reason not in VALID_LEGAL_HOLD_REASONS:
            # Defensive: caller bugs manifest here. Normalise the
            # shape rather than leaking the bad reason string.
            reason = "legal_hold_write_failed"
        super().__init__(reason)
        self.reason = reason


class HoldEntry(BaseModel):
    """Strict registry record for a single legal hold on one audit entry.

    Persisted as canonical JSON under the key
    ``{canonical_id}/{hold_id}.json`` in the registry bucket.
    MinIO Object Lock + 6-year retention applies to the registry too,
    so the audit of the tamper record is itself tamper-evident.
    """

    model_config = ConfigDict(
        extra="forbid",
        strict=True,
        frozen=True,
    )

    hold_id: str = Field(...)
    canonical_id: UUID = Field(...)
    reason: str = Field(..., min_length=3, max_length=1024)
    placed_by: str = Field(...)
    placed_at: datetime = Field(...)
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None

    @field_validator("hold_id")
    @classmethod
    def _validate_hold_id(cls, v: str) -> str:
        if not HOLD_ID_PATTERN.fullmatch(v):
            raise ValueError("hold_id shape invalid")
        return v

    @field_validator("placed_by")
    @classmethod
    def _validate_placed_by(cls, v: str) -> str:
        if not _SHA256_HEX.fullmatch(v):
            raise ValueError("placed_by must be sha256-hex (64 hex chars)")
        return v

    @field_validator("released_by")
    @classmethod
    def _validate_released_by(cls, v):
        if v is None:
            return v
        if not _SHA256_HEX.fullmatch(v):
            raise ValueError(
                "released_by must be sha256-hex (64 hex chars)"
            )
        return v

    @field_validator("placed_at", "released_at")
    @classmethod
    def _validate_tz(cls, v):
        if v is None:
            return v
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return v.astimezone(timezone.utc)

    @property
    def is_active(self) -> bool:
        """True while the hold is in force (not yet released)."""
        return self.released_at is None

    def __repr__(self) -> str:
        # Redact reason -- case details never land in logs.
        return (
            f"HoldEntry(hold_id={self.hold_id!r}, "
            f"canonical_id={self.canonical_id!r}, "
            f"reason='[REDACTED]', "
            f"placed_at={self.placed_at!r}, "
            f"is_active={self.is_active})"
        )

    __str__ = __repr__
