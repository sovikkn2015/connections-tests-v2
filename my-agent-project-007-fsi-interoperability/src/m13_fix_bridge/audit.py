"""Stdout JSON audit emitter for M13.

Writes newline-delimited JSON to ``sys.stdout``. The M10 sidecar tails the
pod's log stream and forwards every ``module=="m13"`` line to the 3-tier
WORM (Steering Rule 6).

No direct M10 import (Rule 33). No M11 shared-infra import (Rule 33 +
design decision D9 in the M13 spec).

The emitter is newline-atomic: ``threading.Lock`` serialises concurrent
writes so two tool calls can't interleave a JSON record.
"""

from __future__ import annotations

import json
import sys
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Mapping


def _now_iso_z() -> str:
    """UTC ISO-8601 with trailing Z, millisecond precision."""
    n = datetime.now(tz=timezone.utc)
    # Replace +00:00 suffix with Z per the project convention.
    return n.isoformat(timespec="milliseconds").replace("+00:00", "Z")


@dataclass(frozen=True)
class AuditEvent:
    """Audit envelope for a single M13 stdout record.

    ``kind`` is a hierarchical event type:
        * ``fix.tool_audit``       — one per tool call
        * ``fix.session_event``    — Logon/Logout/Heartbeat/etc
        * ``fix.exec_report``      — inbound ExecReport drop-copy
        * ``fix.cancel_reject``    — inbound OrderCancelReject drop-copy
        * ``fix.drop_copy_failed`` — synchronous signal on drop-copy failure
        * ``fix.drop_copy_orphan`` — inbound ExecReport w/o matching outbound

    Fields pass through ``fields`` flattened into the top-level JSON object.
    """

    kind: str
    fields: Mapping[str, Any] = field(default_factory=dict)


class StdoutAuditEmitter:
    """Emits M13 audit events to stdout (and optionally a file stream for
    tests).

    The emitter is the ONLY path from M13 to M10 — keeping this in one
    place keeps the module boundary (Rule 33) mechanically enforceable by
    the AST-scan boundary test.
    """

    _MODULE_NAME = "m13"

    def __init__(
        self,
        *,
        stream: Any = None,
        clock: Callable[[], str] | None = None,
    ) -> None:
        self._stream = stream if stream is not None else sys.stdout
        self._clock = clock or _now_iso_z
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def emit(self, event: AuditEvent) -> None:
        """Write one ``{module,kind,ts,...fields}`` JSON line to stdout.

        Emit failures are swallowed — the adapter MUST NOT fail a tool
        call because stdout is closed (which in production means the
        sidecar is down, not a reason to drop real order flow).
        """
        record: dict[str, Any] = {
            "module": self._MODULE_NAME,
            "kind": event.kind,
            "ts": self._clock(),
        }
        for k, v in event.fields.items():
            if k in record:
                # Caller cannot override reserved keys.
                continue
            record[k] = _jsonable(v)

        try:
            line = json.dumps(record, separators=(",", ":"), sort_keys=False) + "\n"
            with self._lock:
                self._stream.write(line)
                self._stream.flush()
        except Exception:
            # Stream closed or similar. Nothing to fall back to — caller
            # MUST NOT raise.
            return

    # Convenience helpers used by dispatcher / session manager.

    def tool_audit(
        self,
        *,
        tool: str,
        outcome: str,
        duration_ms: int,
        trader_aid: str | None,
        firm_id: str | None,
        tenant_id: str | None,
        venue: str | None = None,
        cl_ord_id: str | None = None,
        seq_num_out: int | None = None,
        error_code: str | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "tool": tool,
            "outcome": outcome,
            "duration_ms": int(duration_ms),
            "trader_aid": trader_aid,
            "firm_id": firm_id,
            "tenant_id": tenant_id,
        }
        if venue is not None:
            fields["venue"] = venue
        if cl_ord_id is not None:
            fields["cl_ord_id"] = cl_ord_id
        if seq_num_out is not None:
            fields["seq_num_out"] = int(seq_num_out)
        if error_code is not None:
            fields["error_code"] = error_code
        if extra:
            for k, v in extra.items():
                fields[k] = v
        self.emit(AuditEvent(kind="fix.tool_audit", fields=fields))

    def session_event(
        self,
        *,
        event: str,
        venue: str,
        sender_comp_id: str | None = None,
        target_comp_id: str | None = None,
        seq_num_in: int | None = None,
        seq_num_out: int | None = None,
        extra: Mapping[str, Any] | None = None,
    ) -> None:
        fields: dict[str, Any] = {
            "event": event,
            "venue": venue,
        }
        if sender_comp_id is not None:
            fields["sender_comp_id"] = sender_comp_id
        if target_comp_id is not None:
            fields["target_comp_id"] = target_comp_id
        if seq_num_in is not None:
            fields["seq_num_in"] = int(seq_num_in)
        if seq_num_out is not None:
            fields["seq_num_out"] = int(seq_num_out)
        if extra:
            for k, v in extra.items():
                fields[k] = v
        self.emit(AuditEvent(kind="fix.session_event", fields=fields))


def _jsonable(v: Any) -> Any:
    """Convert common non-JSON-safe values (datetimes, Decimals) to str."""
    if isinstance(v, datetime):
        return v.isoformat().replace("+00:00", "Z")
    # Decimals round-trip via str (preserves precision).
    cls_name = type(v).__name__
    if cls_name == "Decimal":
        return str(v)
    return v


__all__ = ["AuditEvent", "StdoutAuditEmitter"]
