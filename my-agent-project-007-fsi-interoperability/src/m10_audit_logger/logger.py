"""
M10 Audit Logger — Core logger.

AuditLogger orchestrates 3-tier writes (Langfuse + S3 Object Lock WORM +
CRM) with SHA-256 integrity hashing, fail-closed semantics, and a dead
letter queue fallback.

Security invariants (enforced by tests):
- Zero credentials in code or env reads.
- No entry contents in logs or error messages.
- Pre-populated ``sha256_integrity`` on input is REJECTED (tamper guard).
- Every error path raises AuditWriteError with a reason from the frozen
  VALID_REASONS vocabulary.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID

from m3_schema_registry import AuditEntry

from m10_audit_logger.backends import (
    VALID_TIERS,
    AuditBackend,
    AuditDLQ,
    InMemoryAuditDLQ,
)

MIN_RETENTION_YEARS: int = 6

VALID_REASONS: frozenset[str] = frozenset(
    {
        "invalid_entry",
        "retention_too_short",
        "langfuse_write_failed",
        "worm_write_failed",
        "crm_write_failed",
        "invalid_backend_tier",
    }
)


class AuditWriteError(Exception):
    """Fail-closed audit write error.

    ``reason`` is always one of VALID_REASONS. ``str(exc) == exc.reason``.
    No PII, no entry contents, no stack trace strings in the message.
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


# =============================================================================
# Hash helpers
# =============================================================================

def _json_default(v: Any) -> Any:
    """JSON fallback for non-primitive values.

    NOTE: This fallback is only exercised by the provenance-payload
    hash path (where callers may pass raw dicts containing UUID /
    datetime / Enum). The AuditEntry hash path pre-dumps the entry via
    ``model_dump(mode="json", exclude=...)``, which already emits
    strings — so ``_json_default`` is defensive only on that path.
    """
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Enum):
        return v.value
    raise TypeError(f"not serializable: {type(v).__name__}")


def _canonical_json(obj: Any) -> str:
    """Deterministic JSON: sorted keys, compact separators, UTF-8."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=_json_default,
    )


def _compute_integrity_hash(entry: AuditEntry) -> str:
    """SHA-256 over canonicalised entry, excluding sha256_integrity itself."""
    dumped = entry.model_dump(mode="json", exclude={"sha256_integrity"})
    return hashlib.sha256(_canonical_json(dumped).encode("utf-8")).hexdigest()


# =============================================================================
# AuditLogger
# =============================================================================

class AuditLogger:
    """3-tier audit orchestrator.

    Writes every audit entry to Langfuse + S3 WORM + CRM backends in
    sequence. If ANY tier raises, the write fails with AuditWriteError
    and the sealed entry is appended to the DLQ for recovery.

    DLQ is shared by reference if passed in. Callers passing the same
    DLQ to multiple AuditLogger instances are responsible for isolation.

    If the DLQ ``enqueue`` itself raises, the sealed entry is instead
    captured in ``lost_entries()`` as a last-ditch fallback. The
    raised AuditWriteError always carries the ORIGINAL tier reason —
    the DLQ failure does not mask it.

    Args:
        langfuse: AuditBackend with ``.tier == "langfuse"``.
        worm: AuditBackend with ``.tier == "worm"``.
        crm: AuditBackend with ``.tier == "crm"``.
        dlq: Optional AuditDLQ. A fresh InMemoryAuditDLQ is created if
            not provided.
        min_retention_years: Enforced floor on ``entry.retention_years``.
            Must be >= MIN_RETENTION_YEARS (6, SEC 17a-4). ValueError
            otherwise.
    """

    def __init__(
        self,
        *,
        langfuse: AuditBackend,
        worm: AuditBackend,
        crm: AuditBackend,
        dlq: Optional[AuditDLQ] = None,
        min_retention_years: int = MIN_RETENTION_YEARS,
    ) -> None:
        if min_retention_years < MIN_RETENTION_YEARS:
            raise ValueError(
                f"min_retention_years must be >= {MIN_RETENTION_YEARS}, "
                f"got {min_retention_years}"
            )

        # Validate each backend.tier matches its slot using getattr so a
        # missing attribute raises AuditWriteError, not AttributeError.
        for slot, backend in (
            ("langfuse", langfuse),
            ("worm", worm),
            ("crm", crm),
        ):
            if getattr(backend, "tier", None) != slot:
                raise AuditWriteError("invalid_backend_tier")

        self._langfuse = langfuse
        self._worm = worm
        self._crm = crm
        self._dlq: AuditDLQ = dlq if dlq is not None else InMemoryAuditDLQ()
        self._min_retention_years = min_retention_years
        self._lost_entries: list[tuple[AuditEntry, str]] = []

    # -------------------------------------------------------------------------
    # Write pipeline
    # -------------------------------------------------------------------------

    def write(self, entry: AuditEntry) -> AuditEntry:
        """Write entry to all three tiers. Returns sealed entry.

        Raises:
            AuditWriteError: on any validation failure or tier failure.
                Reason is one of VALID_REASONS.
        """
        # Step 1: strict type check (no duck-typing)
        if not isinstance(entry, AuditEntry):
            raise AuditWriteError("invalid_entry")

        # Step 2: reject pre-populated sha256_integrity (tamper guard)
        if entry.sha256_integrity != "":
            raise AuditWriteError("invalid_entry")

        # Step 3: enforce retention floor (SEC 17a-4)
        if (
            entry.retention_years is None
            or entry.retention_years < self._min_retention_years
        ):
            raise AuditWriteError("retention_too_short")

        # Step 4-5: compute and attach integrity hash (input not mutated)
        integrity = _compute_integrity_hash(entry)
        sealed = entry.model_copy(update={"sha256_integrity": integrity})

        # Step 6-8: fan out to three tiers sequentially, fail-closed
        self._write_tier(self._langfuse, sealed, "langfuse_write_failed")
        self._write_tier(self._worm, sealed, "worm_write_failed")
        self._write_tier(self._crm, sealed, "crm_write_failed")

        return sealed

    def _write_tier(
        self,
        backend: AuditBackend,
        sealed: AuditEntry,
        reason: str,
    ) -> None:
        """Invoke one tier; on failure, DLQ + raise."""
        try:
            backend.write(sealed)
        except Exception:  # narrow: never catches BaseException
            # Send to DLQ. If the DLQ itself fails, capture in
            # lost_entries as last-ditch fallback — but always raise
            # with the ORIGINAL tier reason so the caller sees the
            # real failure.
            try:
                self._dlq.enqueue(sealed, reason)
            except Exception:
                self._lost_entries.append((sealed, reason))
            raise AuditWriteError(reason)

    # -------------------------------------------------------------------------
    # Verification and query
    # -------------------------------------------------------------------------

    def verify_integrity(self, entry: AuditEntry) -> bool:
        """Recompute and compare sha256_integrity. Never raises."""
        if not isinstance(entry, AuditEntry):
            return False
        if entry.sha256_integrity == "":
            return False
        expected = _compute_integrity_hash(entry)
        return expected == entry.sha256_integrity

    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]:
        """Debug-only query. Delegates to the WORM backend.

        Production reads should go to Langfuse / S3 / CRM directly.
        If the WORM backend raises NotImplementedError (e.g., Phase 2
        S3 Object Lock), returns an empty list.
        """
        try:
            return self._worm.query_by_trace_id(trace_id)
        except NotImplementedError:
            return []

    # -------------------------------------------------------------------------
    # Introspection
    # -------------------------------------------------------------------------

    def health(self) -> dict:
        """Metadata-only health. No secrets, no entry contents."""
        dlq_depth = len(getattr(self._dlq, "records", []))
        return {
            "status": "ok",
            "tiers": list(VALID_TIERS),
            "dlq_depth": dlq_depth,
            "lost_depth": len(self._lost_entries),
            "min_retention_years": self._min_retention_years,
        }

    def backends_by_tier(self) -> dict[str, AuditBackend]:
        """Public handle for health probes + boot-time readiness checks.

        Health probes (M10 ``/health``, readiness sidecars) MUST call
        this method -- they MUST NOT read ``self._langfuse``,
        ``self._worm``, or ``self._crm`` directly. The private slots
        can be rearranged in Phase 2 without breaking public callers.

        Returns a fresh dict each call -- callers may not mutate the
        backend map from the outside.
        """
        return {
            "langfuse": self._langfuse,
            "worm": self._worm,
            "crm": self._crm,
        }

    def lost_entries(self) -> list[tuple[AuditEntry, str]]:
        """Entries that could not be DLQ'd because DLQ itself failed.

        Unbounded in Phase 1. A Phase 2 implementation MUST bound this
        (disk overflow, TTL).
        """
        return list(self._lost_entries)
