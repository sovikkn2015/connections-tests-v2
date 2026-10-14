"""
Gap 5 — Audit client Protocol + in-memory reference implementation.

We DO NOT import `m10_audit_logger` here (steering rule 9). The
hosting service wires the real M10 client via the Protocol.

See .kiro/specs/gap5-erisa-account-type.md R7, R8.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class AuditClient(Protocol):
    """Fire-and-forget audit sink for Gap 5 decisions.

    The caller invokes `write(payload)` with a dict. Gap 5's engine
    serialises the `AccountTypeDecision` via `model_dump(mode="json")`
    and stamps `gap="gap5"` + `schema_version` before calling this.
    """

    def write(self, payload: dict[str, Any]) -> None: ...


class InMemoryAuditClient:
    """Appends each written payload to a list. Test / Phase-2 default.

    Not thread-safe across forks; construct a fresh instance per
    pod / test.
    """

    def __init__(self) -> None:
        self._records: list[dict[str, Any]] = []

    def write(self, payload: dict[str, Any]) -> None:
        # Defensive deep-copy would be overkill; the engine hands us
        # a fresh dict per call (serialised from a frozen Pydantic).
        self._records.append(payload)

    @property
    def records(self) -> tuple[dict[str, Any], ...]:
        return tuple(self._records)

    def clear(self) -> None:
        self._records.clear()
