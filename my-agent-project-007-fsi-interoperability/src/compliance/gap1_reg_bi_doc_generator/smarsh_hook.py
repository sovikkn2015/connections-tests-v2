"""
Gap 1 — Smarsh archive hook (steering rule 18).

See .kiro/specs/gap1-reg-bi-doc-generator.md R10.

Interface only. The real Smarsh adapter lives in
``src/m11_rest_adapters/smarsh_archive/`` (Phase 3, separate task).
Gap 1 ships the Protocol + an in-memory stub.

Fail-closed: archive failure raises ``SmarshArchiveFailed`` — same
pattern as ``AuditWriteFailed``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from compliance.gap1_reg_bi_doc_generator.document import RegBiDocument
from compliance.gap1_reg_bi_doc_generator.renderer import RenderedDocument

# =============================================================================
# Error vocabulary (R10.3)
# =============================================================================


_SMARSH_ARCHIVE_FAILED_REASONS: frozenset[str] = frozenset(
    {"smarsh_archive_failed"}
)


class SmarshArchiveFailed(RuntimeError):
    """Raised when the injected Smarsh client's archive() raises."""

    def __init__(self, reason: str = "smarsh_archive_failed") -> None:
        if reason not in _SMARSH_ARCHIVE_FAILED_REASONS:
            raise ValueError(
                f"SmarshArchiveFailed.reason must be one of "
                f"{sorted(_SMARSH_ARCHIVE_FAILED_REASONS)}"
            )
        super().__init__(reason)
        self.reason = reason


# =============================================================================
# Protocol + stub
# =============================================================================


@runtime_checkable
class SmarshArchiveClient(Protocol):
    """Smarsh communications archive interface."""

    def archive(
        self,
        *,
        document: RegBiDocument,
        rendered: RenderedDocument,
    ) -> None: ...


class InMemorySmarshClient:
    """Thread-naive in-memory archive stub (fresh per test / pod)."""

    def __init__(self) -> None:
        self._records: list[tuple[RegBiDocument, RenderedDocument]] = []

    def archive(
        self,
        *,
        document: RegBiDocument,
        rendered: RenderedDocument,
    ) -> None:
        self._records.append((document, rendered))

    @property
    def records(
        self,
    ) -> tuple[tuple[RegBiDocument, RenderedDocument], ...]:
        return tuple(self._records)
