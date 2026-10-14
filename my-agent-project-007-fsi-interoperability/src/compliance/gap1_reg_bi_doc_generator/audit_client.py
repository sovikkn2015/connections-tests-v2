"""
Gap 1 — Audit client Protocol + stub + error.

We intentionally DO NOT import ``m10_audit_logger`` here — cross-module
imports are forbidden (steering rule 9). The hosting service wires the
real M10 client in via the Protocol.

See .kiro/specs/gap1-reg-bi-doc-generator.md R8.

v3 delta over v2:
    - ``AuditClient.write`` accepts ``RegBiDocument | GenerationSkipped``
      (R8.1). SKIP paths also write to audit per R7.3 step 2b.
    - ``InMemoryAuditClient`` exposes ``records_docs`` and
      ``records_skips`` separately (R8.2).
"""

from __future__ import annotations

from typing import Protocol, Union, runtime_checkable

from compliance.gap1_reg_bi_doc_generator.document import (
    GenerationSkipped,
    RegBiDocument,
)

AuditRecord = Union[RegBiDocument, GenerationSkipped]

# =============================================================================
# Error vocabulary (R8.3)
# =============================================================================

_AUDIT_WRITE_FAILED_REASONS: frozenset[str] = frozenset(
    {"audit_write_failed"}
)


class AuditWriteFailed(RuntimeError):
    """Raised when the injected AuditClient's write(...) raises.

    ``reason`` is always ``"audit_write_failed"``.
    ``str(exc) == exc.reason``. No PII, no stack trace string.
    """

    def __init__(self, reason: str = "audit_write_failed") -> None:
        if reason not in _AUDIT_WRITE_FAILED_REASONS:
            raise ValueError(
                f"AuditWriteFailed.reason must be one of "
                f"{sorted(_AUDIT_WRITE_FAILED_REASONS)}"
            )
        super().__init__(reason)
        self.reason = reason


# =============================================================================
# Protocol (R8.1)
# =============================================================================


@runtime_checkable
class AuditClient(Protocol):
    """Fire-and-forget audit sink for Reg BI documents and skips.

    Dedupe by ``(trace_id, trigger)`` is the caller's responsibility;
    Gap 1 simply writes once per ``generate()`` call (including SKIP).
    """

    def write(self, record: AuditRecord) -> None: ...


# =============================================================================
# InMemoryAuditClient (R8.2)
# =============================================================================


class InMemoryAuditClient:
    """Appends each written record to in-memory lists.

    Construct a fresh instance per test/pod. Not thread-safe.
    """

    def __init__(self) -> None:
        self._records_docs: list[RegBiDocument] = []
        self._records_skips: list[GenerationSkipped] = []

    def write(self, record: AuditRecord) -> None:
        if isinstance(record, RegBiDocument):
            self._records_docs.append(record)
        elif isinstance(record, GenerationSkipped):
            self._records_skips.append(record)
        else:  # pragma: no cover — extra="forbid" upstream guards
            raise TypeError(
                f"AuditClient.write: unsupported record type "
                f"{type(record).__name__}"
            )

    @property
    def records_docs(self) -> tuple[RegBiDocument, ...]:
        return tuple(self._records_docs)

    @property
    def records_skips(self) -> tuple[GenerationSkipped, ...]:
        return tuple(self._records_skips)

    @property
    def records(self) -> tuple[AuditRecord, ...]:
        """Backward-compat: combined (docs + skips) view."""
        return (*self._records_docs, *self._records_skips)
