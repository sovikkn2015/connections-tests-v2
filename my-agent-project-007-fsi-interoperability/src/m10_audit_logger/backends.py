"""
M10 Audit Logger — Backends.

AuditBackend and AuditDLQ Protocols + in-memory implementations used in
Phase 1 (dev/test). Phase 2 swaps in real Langfuse / boto3 S3 Object
Lock / Salesforce implementations without touching AuditLogger.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from m3_schema_registry import AuditEntry

VALID_TIERS: tuple[str, ...] = ("langfuse", "worm", "crm")


@runtime_checkable
class AuditBackend(Protocol):
    """3-tier audit sink contract.

    Each concrete backend carries a ``tier`` attribute identifying its
    slot ("langfuse", "worm", or "crm"). AuditLogger validates tier
    assignment at construction.

    ``write`` MUST raise any exception to signal failure; return value
    is ignored. ``query_by_trace_id`` is provided for debug use; Phase
    2 production backends (S3 Object Lock) MAY raise
    ``NotImplementedError``.
    """

    tier: str

    def write(self, entry: AuditEntry) -> None: ...

    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]: ...


@runtime_checkable
class AuditDLQ(Protocol):
    """Dead letter queue for failed tier writes.

    AuditLogger enqueues the (sealed_entry, reason) pair whenever any
    tier write fails, BEFORE re-raising AuditWriteError. The DLQ is a
    recovery side channel and MUST NOT mask the original tier failure.
    """

    def enqueue(self, entry: AuditEntry, reason: str) -> None: ...


class InMemoryAuditBackend:
    """Deterministic in-memory AuditBackend for Phase 1 dev + tests.

    Not thread-safe. Not bounded. Do NOT use in production.

    Args:
        tier: One of VALID_TIERS. ValueError otherwise.
        fail_on_nth: If set, the Nth call to ``write`` raises
            ``RuntimeError(fail_message)``. Counter increments before
            the check, so ``fail_on_nth=1`` fails the first call.
            Entries are appended only AFTER the check, so failing
            writes do NOT add to ``entries``.
        fail_message: Message used by the injected failure.
    """

    tier: str
    entries: list[AuditEntry]

    def __init__(
        self,
        *,
        tier: str,
        fail_on_nth: Optional[int] = None,
        fail_message: str = "injected_failure",
    ) -> None:
        if tier not in VALID_TIERS:
            raise ValueError(
                f"tier must be one of {VALID_TIERS}, got {tier!r}"
            )
        self.tier = tier
        self.entries = []
        self._counter = 0
        self._fail_on_nth = fail_on_nth
        self._fail_message = fail_message

    def write(self, entry: AuditEntry) -> None:
        self._counter += 1
        if self._fail_on_nth is not None and self._counter == self._fail_on_nth:
            raise RuntimeError(self._fail_message)
        self.entries.append(entry)

    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]:
        """Exact-match, case-sensitive, preserving insertion order."""
        return [e for e in self.entries if e.trace_id == trace_id]

    def reset(self) -> None:
        self.entries = []
        self._counter = 0


class InMemoryAuditDLQ:
    """Deterministic in-memory AuditDLQ for Phase 1 dev + tests.

    Not thread-safe. Not bounded. Do NOT use in production.

    ``records`` accumulates ``(entry, reason)`` tuples.
    """

    records: list[tuple[AuditEntry, str]]

    def __init__(self) -> None:
        self.records = []

    def enqueue(self, entry: AuditEntry, reason: str) -> None:
        self.records.append((entry, reason))

    def reset(self) -> None:
        self.records = []
