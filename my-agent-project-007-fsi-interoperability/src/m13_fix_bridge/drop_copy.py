"""ExecutionReport + OrderCancelReject drop-copy to stdout audit (Spec §R6).

Drop-copy emits canonicalised inbound events with:

* ``account_hash`` = HMAC-SHA256(account, tenant_salt)[:16] (hex).
* ``trader_aid`` correlated from the outbound-order dispatcher (LRU
  capped at 10k entries, 24h TTL semantics via capacity eviction).
* NO raw PII, NO MNPI (Rule 7).

On drop-copy failure, a synchronous ``fix.drop_copy_failed`` audit is
emitted and the ingestion returns normally — Rule 8 forbids silent
drops.
"""

from __future__ import annotations

import hashlib
import hmac
import threading
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Mapping

from m13_fix_bridge.audit import AuditEvent, StdoutAuditEmitter


_MAX_TRADER_AID_MAP = 10_000


def _iso_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def hash_account(account: str, salt: bytes) -> str:
    """HMAC-SHA256 of ``account`` with tenant-salt; first 16 hex chars."""
    if not isinstance(account, str) or not account:
        raise ValueError("account must be non-empty str")
    if not isinstance(salt, (bytes, bytearray)) or len(salt) < 16:
        raise ValueError("salt must be bytes (>=16 bytes)")
    mac = hmac.new(bytes(salt), account.encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:16]


class TraderAidCorrelation:
    """LRU map from ``cl_ord_id`` to the ``trader_aid`` of the submitter.

    Drop-copy events correlate inbound ExecReports back to the AID that
    sent the parent order. When the map overflows, oldest entries are
    evicted — these become ``drop_copy_orphan`` events until another
    outbound references the cl_ord_id.
    """

    def __init__(self, *, max_size: int = _MAX_TRADER_AID_MAP) -> None:
        if max_size <= 0:
            raise ValueError("max_size must be > 0")
        self._max = max_size
        self._lock = threading.Lock()
        self._m: "OrderedDict[str, str]" = OrderedDict()

    def remember(self, cl_ord_id: str, trader_aid: str) -> None:
        if not cl_ord_id or not trader_aid:
            return
        with self._lock:
            if cl_ord_id in self._m:
                self._m.move_to_end(cl_ord_id)
                self._m[cl_ord_id] = trader_aid
                return
            self._m[cl_ord_id] = trader_aid
            if len(self._m) > self._max:
                self._m.popitem(last=False)

    def lookup(self, cl_ord_id: str) -> str | None:
        if not cl_ord_id:
            return None
        with self._lock:
            val = self._m.get(cl_ord_id)
            if val is not None:
                self._m.move_to_end(cl_ord_id)
            return val


class DropCopyEmitter:
    """Emit canonicalised ExecReport + CancelReject events to stdout."""

    def __init__(
        self,
        *,
        audit: StdoutAuditEmitter,
        account_salt: bytes,
        correlator: TraderAidCorrelation | None = None,
        enabled: bool = True,
    ) -> None:
        if not isinstance(account_salt, (bytes, bytearray)) or len(account_salt) < 16:
            raise ValueError("account_salt must be >= 16 bytes")
        self._audit = audit
        self._salt = bytes(account_salt)
        self._corr = correlator or TraderAidCorrelation()
        self._enabled = enabled

    @property
    def correlator(self) -> TraderAidCorrelation:
        return self._corr

    def set_enabled(self, on: bool) -> None:
        self._enabled = bool(on)

    # ------------------------------------------------------------------
    # Public entrypoints (called by SessionManager.inbound_handler)
    # ------------------------------------------------------------------

    def on_exec_report(
        self,
        *,
        venue: str,
        report: Mapping[str, Any],
        tenant_id: str,
    ) -> None:
        if not self._enabled:
            return
        self._emit_canonical(
            kind="fix.exec_report",
            venue=venue,
            msg=report,
            tenant_id=tenant_id,
        )

    def on_cancel_reject(
        self,
        *,
        venue: str,
        reject: Mapping[str, Any],
        tenant_id: str,
    ) -> None:
        if not self._enabled:
            return
        self._emit_canonical(
            kind="fix.cancel_reject",
            venue=venue,
            msg=reject,
            tenant_id=tenant_id,
        )

    # ------------------------------------------------------------------
    # Implementation
    # ------------------------------------------------------------------

    def _emit_canonical(
        self,
        *,
        kind: str,
        venue: str,
        msg: Mapping[str, Any],
        tenant_id: str,
    ) -> None:
        try:
            cl_ord_id = str(msg.get("cl_ord_id", ""))
            order_id = str(msg.get("order_id", ""))
            account = str(msg.get("account", ""))
            # Account hash; raw account MUST NOT leave this fn.
            acct_hash = hash_account(account, self._salt) if account else ""
            trader_aid = self._corr.lookup(cl_ord_id)

            fields: dict[str, Any] = {
                "venue": venue,
                "cl_ord_id": cl_ord_id,
                "order_id": order_id,
                "tenant_id": tenant_id,
                "trader_aid": trader_aid,
                "account_hash": acct_hash,
            }
            # Canonicalise the common FIX ExecReport fields. We accept
            # either the raw FIX field name or the canonical snake-case
            # form — whichever the engine handed us.
            passthrough_keys = (
                "exec_type",
                "ord_status",
                "last_qty",
                "last_px",
                "cum_qty",
                "avg_px",
                "cxl_rej_reason",
                "cxl_rej_response_to",
                "text",
            )
            for k in passthrough_keys:
                if k in msg:
                    fields[k] = _jsonable(msg[k])
            if "transact_time" in msg:
                fields["transact_time"] = _coerce_ts(msg["transact_time"])
            # Orphan event if we couldn't correlate — Spec §R6.1.
            if trader_aid is None and cl_ord_id:
                self._audit.emit(
                    AuditEvent(
                        kind="fix.drop_copy_orphan",
                        fields={
                            "venue": venue,
                            "cl_ord_id": cl_ord_id,
                            "tenant_id": tenant_id,
                        },
                    )
                )
            self._audit.emit(AuditEvent(kind=kind, fields=fields))
        except Exception as exc:  # pragma: no cover — defensive
            # Rule 8 — do not silently drop.
            self._audit.emit(
                AuditEvent(
                    kind="fix.drop_copy_failed",
                    fields={
                        "venue": venue,
                        "tenant_id": tenant_id,
                        "reason": type(exc).__name__,
                    },
                )
            )


def _jsonable(v: Any) -> Any:
    if isinstance(v, datetime):
        return _iso_z(v)
    cls_name = type(v).__name__
    if cls_name == "Decimal":
        return str(v)
    return v


def _coerce_ts(v: Any) -> str | None:
    if isinstance(v, datetime):
        if v.tzinfo is None:
            v = v.replace(tzinfo=timezone.utc)
        return _iso_z(v)
    if isinstance(v, str):
        return v
    return None


__all__ = [
    "DropCopyEmitter",
    "TraderAidCorrelation",
    "hash_account",
]
