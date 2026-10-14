"""
Gap 7 — Audit client Protocol + in-memory reference impl.

Same contract as Gap 5 audit_client: fire-and-forget, sink raise is
translated to `AuditWriteFailed` by the egress gate, not here.

See .kiro/specs/gap7-cross-border.md §R6.3, §R8.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditClient(Protocol):
    def write(self, payload: dict[str, Any]) -> None: ...


class InMemoryAuditClient:
    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, payload: dict[str, Any]) -> None:
        self._records.append(payload)

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._records)

    def clear(self) -> None:
        self._records.clear()
