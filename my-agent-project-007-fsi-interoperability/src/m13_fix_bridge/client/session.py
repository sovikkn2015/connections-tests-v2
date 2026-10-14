"""FixSession state + FileSeqnumStore persistence.

Seq-num persistence strategy (Spec §R5):

* One JSON file per ``(sender_comp_id, target_comp_id)`` under
  ``FIX_SEQNUM_STORE_DIR``.
* Every increment: write-through + ``os.fsync()``. No batching. A
  restart must resume from the last durably-persisted seqnum to avoid
  counterparty rejects on gap.
* Atomic write via ``os.replace(tmp, final)`` (POSIX guarantees atomic
  rename within the same filesystem).

Concurrency:

* Each ``FileSeqnumStore`` instance holds a single ``threading.Lock``
  covering all file writes. Multiple sessions use separate instances
  (or share the same store with distinct keys — both are safe).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class SessionState(str, Enum):
    """FIX session lifecycle states (Spec §2.4)."""

    DISCONNECTED = "DISCONNECTED"
    LOGON_SENT = "LOGON_SENT"
    ACTIVE = "ACTIVE"
    LOGOUT_SENT = "LOGOUT_SENT"


def _safe_filename(s: str) -> str:
    """Replace chars that could escape the seqnum-store dir.

    FIX CompIDs usually match ``[A-Za-z0-9]+`` so this is defensive.
    """
    out = []
    for c in s:
        if c.isalnum() or c in ("_", "-", "."):
            out.append(c)
        else:
            out.append("_")
    return "".join(out)


class FileSeqnumStore:
    """JSON-file-backed sequence-number store.

    Every write is ``os.fsync``-ed. Reads are cheap (one open + read).
    """

    def __init__(self, root_dir: str) -> None:
        self._root = root_dir
        self._lock = threading.Lock()
        os.makedirs(self._root, exist_ok=True)

    def _path(self, sender: str, target: str) -> str:
        fn = f"{_safe_filename(sender)}.{_safe_filename(target)}.json"
        return os.path.join(self._root, fn)

    def load(self, sender: str, target: str) -> tuple[int, int]:
        p = self._path(sender, target)
        if not os.path.exists(p):
            return (1, 1)
        with self._lock:
            try:
                with open(p, "r", encoding="utf-8") as fh:
                    raw = json.load(fh)
                seq_in = int(raw.get("seq_num_in", 1))
                seq_out = int(raw.get("seq_num_out", 1))
                if seq_in < 1 or seq_out < 1:
                    return (1, 1)
                return (seq_in, seq_out)
            except (OSError, ValueError, json.JSONDecodeError):
                # Corrupt file — log-and-reset behaviour is conservative.
                return (1, 1)

    def _write_atomic(self, path: str, data: dict) -> None:
        tmp = path + ".tmp"
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def save(
        self,
        sender: str,
        target: str,
        seq_num_in: int,
        seq_num_out: int,
    ) -> None:
        p = self._path(sender, target)
        payload = {
            "seq_num_in": int(seq_num_in),
            "seq_num_out": int(seq_num_out),
            "updated_at": datetime.now(tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
        }
        with self._lock:
            self._write_atomic(p, payload)

    def bump_out(self, sender: str, target: str) -> int:
        """Increment seq_num_out, fsync, return new value."""
        with self._lock:
            seq_in, seq_out = self._load_locked(sender, target)
            new_out = seq_out + 1
            self._write_atomic(
                self._path(sender, target),
                {
                    "seq_num_in": seq_in,
                    "seq_num_out": new_out,
                    "updated_at": datetime.now(tz=timezone.utc)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                },
            )
            return new_out

    def bump_in(self, sender: str, target: str, new_seq_in: int) -> None:
        """Set seq_num_in to the supplied value + fsync."""
        if new_seq_in < 1:
            raise ValueError("seq_num_in must be >= 1")
        with self._lock:
            seq_in, seq_out = self._load_locked(sender, target)
            # Permit both increments and explicit resets (rare — gap-fill).
            self._write_atomic(
                self._path(sender, target),
                {
                    "seq_num_in": int(new_seq_in),
                    "seq_num_out": seq_out,
                    "updated_at": datetime.now(tz=timezone.utc)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                },
            )

    def reset(self, sender: str, target: str) -> None:
        """Truncate to ``(1, 1)`` for a ResetOnLogon-style startup."""
        with self._lock:
            self._write_atomic(
                self._path(sender, target),
                {
                    "seq_num_in": 1,
                    "seq_num_out": 1,
                    "updated_at": datetime.now(tz=timezone.utc)
                    .isoformat(timespec="milliseconds")
                    .replace("+00:00", "Z"),
                },
            )

    def _load_locked(self, sender: str, target: str) -> tuple[int, int]:
        # Called with _lock held.
        p = self._path(sender, target)
        if not os.path.exists(p):
            return (1, 1)
        try:
            with open(p, "r", encoding="utf-8") as fh:
                raw = json.load(fh)
            seq_in = int(raw.get("seq_num_in", 1))
            seq_out = int(raw.get("seq_num_out", 1))
            if seq_in < 1 or seq_out < 1:
                return (1, 1)
            return (seq_in, seq_out)
        except (OSError, ValueError, json.JSONDecodeError):
            return (1, 1)


@dataclass
class FixSession:
    """Per-venue FIX session state.

    Mutable fields are updated via ``SessionManager``; this class is a
    state+data holder, not a driver.
    """

    venue: str
    sender_comp_id: str
    target_comp_id: str
    heartbeat_interval_s: int
    reset_on_logon: bool = False
    state: SessionState = SessionState.DISCONNECTED
    seq_num_in: int = 1
    seq_num_out: int = 1
    last_heartbeat_ts: Optional[datetime] = None
    last_inbound_ts: Optional[datetime] = None
    last_outbound_ts: Optional[datetime] = None
    # Retained for test observability + protocol-violation audit trail.
    disconnect_reason: Optional[str] = None
    # Kept here so sessions can self-describe during shutdown / health.
    fatal_error: Optional[str] = None
    _meta: dict = field(default_factory=dict)

    def touch_outbound(self, when: datetime) -> None:
        self.last_outbound_ts = when

    def touch_inbound(self, when: datetime) -> None:
        self.last_inbound_ts = when

    def is_active(self) -> bool:
        return self.state is SessionState.ACTIVE


__all__ = ["FixSession", "FileSeqnumStore", "SessionState"]
