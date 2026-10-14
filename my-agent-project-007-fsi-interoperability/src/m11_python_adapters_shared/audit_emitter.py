"""Stdout-only structured audit emitter.

The Python adapter family never imports M10 directly (Steering Rule 33). Instead
it writes one line of JSON per tool invocation to stdout; the M10 sidecar tails
the pod's log stream and forwards `*.tool_audit` events to the 3-tier WORM.

This keeps the adapter → audit boundary decoupled and means we can unit-test
auditing by capturing stdout without mocking M10.
"""

from __future__ import annotations

import json
import sys
import threading
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol


@dataclass(frozen=True)
class AuditEvent:
    """Audit event envelope emitted to stdout.

    Fields common to every Python adapter. Vendor-specific fields pass through
    `fields` unchanged (e.g. ``security_count``, ``capture_id``). The emitter
    flattens ``fields`` into the top-level JSON object before writing.
    """

    event: str  # e.g. "bloomberg.tool_audit", "ice.tool_audit"
    tool: str
    firm_id: str
    outcome: str  # "success" | "failure"
    duration_ms: int
    adapter_name: str
    vendor: str
    timestamp_ms: int
    error_code: str | None = None
    vendor_status: object | None = None
    retryable: bool | None = None
    fields: Mapping[str, Any] | None = None


class _Logger(Protocol):
    """Minimal structured-logger shape used by AuditEmitter.

    The real structlog logger and the test double both implement this.
    """

    def info(self, event_dict: Mapping[str, Any]) -> None: ...
    def warning(self, event_dict: Mapping[str, Any]) -> None: ...


class AuditEmitter:
    """Emits one audit event to stdout per tool invocation.

    Writes raw newline-delimited JSON to `sys.stdout` by default (configurable
    stream for tests). Also logs a structured info entry via the provided
    logger for local observability, so both the stdout pipeline (sidecar →
    WORM) and the in-pod log stream show the event.

    Emit failures are swallowed — the adapter must never fail a tool call
    because an audit write hit a closed stream. A warning is logged in that
    case so ops can correlate.
    """

    def __init__(
        self,
        logger: _Logger | None = None,
        *,
        stream: Any = None,
        clock: Callable[[], int] | None = None,
    ) -> None:
        self._logger = logger
        self._stream = stream if stream is not None else sys.stdout
        self._clock = clock
        # stdout.write must be newline-atomic — serialize under a lock so two
        # concurrent tool calls don't interleave a single JSON record.
        self._write_lock = threading.Lock()

    def emit(self, ev: AuditEvent) -> None:
        """Write one JSON line and (if logger provided) a mirrored info event."""
        record: dict[str, Any] = {
            "event": ev.event,
            "tool": ev.tool,
            "firm_id": ev.firm_id,
            "outcome": ev.outcome,
            "duration_ms": int(ev.duration_ms),
            "adapter_name": ev.adapter_name,
            "vendor": ev.vendor,
            "timestamp_ms": int(ev.timestamp_ms),
        }
        if ev.error_code is not None:
            record["error_code"] = ev.error_code
        if ev.vendor_status is not None:
            # Vendor status may be int (HTTP / blpapi) or str (gRPC status code
            # enum name). JSON-encode whichever shape the caller supplied.
            record["vendor_status"] = ev.vendor_status
        if ev.retryable is not None:
            record["retryable"] = bool(ev.retryable)
        if ev.fields:
            # Explicitly NOT overwriting top-level keys — caller controls its
            # own field namespace.
            for k, v in ev.fields.items():
                record[k] = v

        try:
            line = json.dumps(record, separators=(",", ":"), sort_keys=False) + "\n"
            with self._write_lock:
                self._stream.write(line)
                self._stream.flush()
        except Exception as err:  # pragma: no cover — rare stream failure
            if self._logger is not None:
                try:
                    self._logger.warning(
                        {
                            "event": "audit.emit_failed",
                            "tool": ev.tool,
                            "err": repr(err),
                        }
                    )
                except Exception:
                    pass
            return

        if self._logger is not None:
            try:
                self._logger.info(record)
            except Exception:  # pragma: no cover — logger must never kill a tool call
                pass
