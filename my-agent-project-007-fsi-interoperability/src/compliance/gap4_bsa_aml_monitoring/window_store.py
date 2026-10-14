"""
Gap 4 — WindowStore Protocol + implementations.

InMemoryWindowStore is the Phase-3 runtime. Thread-safe via
threading.Lock(). RedisWindowStore is a Phase-4 stub that raises
NotImplementedError on every method — it exists so imports do not
break when the real backend lands.

See .kiro/specs/gap4-bsa-aml-monitoring.md R4.
"""

from __future__ import annotations

import bisect
import threading
from datetime import datetime
from typing import Optional, Protocol, runtime_checkable
from uuid import UUID

from compliance.gap4_bsa_aml_monitoring.models import (
    CashTransaction,
    CashTransactionCategory,
)


# =============================================================================
# Protocol (spec R4.1)
# =============================================================================


@runtime_checkable
class WindowStore(Protocol):
    """Rolling-window transaction store.

    Implementations must be thread-safe (Phase 3: threading.Lock()).
    """

    def record(
        self,
        key: tuple[str, UUID],
        txn: CashTransaction,
    ) -> None: ...

    def within(
        self,
        key: tuple[str, UUID],
        *,
        start: datetime,
        end: datetime,
        categories: Optional[frozenset[CashTransactionCategory]] = None,
    ) -> tuple[CashTransaction, ...]: ...

    def purge_before(self, threshold: datetime) -> int: ...


# =============================================================================
# InMemoryWindowStore (spec R4.2)
# =============================================================================


class InMemoryWindowStore:
    """Thread-safe in-memory window store.

    Backing store: dict[(firm_id, client_id) -> list[CashTransaction]]
    kept sorted by occurred_at ASC via bisect.insort (stable for
    equal timestamps — order of insertion preserved).
    """

    def __init__(self) -> None:
        self._store: dict[tuple[str, UUID], list[CashTransaction]] = {}
        self._lock = threading.Lock()

    def record(
        self,
        key: tuple[str, UUID],
        txn: CashTransaction,
    ) -> None:
        """Insert `txn` under `key`, maintaining sort by occurred_at."""
        if not isinstance(txn, CashTransaction):
            raise TypeError("txn must be CashTransaction")
        with self._lock:
            entries = self._store.setdefault(key, [])
            # Stable sort by occurred_at. bisect.insort_right on a list
            # of CashTransaction requires an accessor — use keys.
            times = [t.occurred_at for t in entries]
            idx = bisect.bisect_right(times, txn.occurred_at)
            entries.insert(idx, txn)

    def within(
        self,
        key: tuple[str, UUID],
        *,
        start: datetime,
        end: datetime,
        categories: Optional[frozenset[CashTransactionCategory]] = None,
    ) -> tuple[CashTransaction, ...]:
        """Return txns with `start < occurred_at <= end` (R4.5).

        Optional category filter. Order: ascending by occurred_at.
        """
        if start >= end:
            # Empty window — defensive, avoids accidental full-table
            # scans when caller math is off.
            return ()
        with self._lock:
            entries = list(self._store.get(key, ()))
        out = [
            t
            for t in entries
            if start < t.occurred_at <= end
            and (categories is None or t.category in categories)
        ]
        return tuple(out)

    def purge_before(self, threshold: datetime) -> int:
        """Remove txns with occurred_at < threshold. Returns removed count."""
        removed = 0
        with self._lock:
            for key, entries in self._store.items():
                kept = [t for t in entries if t.occurred_at >= threshold]
                removed += len(entries) - len(kept)
                self._store[key] = kept
        return removed

    def size(self) -> int:
        """Total txn count across all keys. For tests and metrics."""
        with self._lock:
            return sum(len(v) for v in self._store.values())


# =============================================================================
# RedisWindowStore (spec R4.4 — Phase 4 stub)
# =============================================================================


class RedisWindowStore:
    """Phase-4 stub. Every method raises NotImplementedError.

    Exists so Phase-4 code that imports `RedisWindowStore` doesn't
    break. Wiring against Vault-backed Redis URL happens when Phase 4
    lands.
    """

    _STUB_MSG = (
        "redis backend is Phase 4 — see .kiro/specs/gap4-bsa-aml-monitoring.md §0.1"
    )

    def __init__(self, redis_url: str) -> None:
        if not isinstance(redis_url, str) or not redis_url:
            raise ValueError("redis_url must be non-empty string")
        self._redis_url = redis_url

    def record(
        self,
        key: tuple[str, UUID],
        txn: CashTransaction,
    ) -> None:
        raise NotImplementedError(self._STUB_MSG)

    def within(
        self,
        key: tuple[str, UUID],
        *,
        start: datetime,
        end: datetime,
        categories: Optional[frozenset[CashTransactionCategory]] = None,
    ) -> tuple[CashTransaction, ...]:
        raise NotImplementedError(self._STUB_MSG)

    def purge_before(self, threshold: datetime) -> int:
        raise NotImplementedError(self._STUB_MSG)
