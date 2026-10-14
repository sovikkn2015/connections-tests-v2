"""Global + per-venue kill switch (Spec §R7).

* State persisted at ``kill_switch.json`` (survives restart).
* Atomic updates via ``os.replace(tmp, final)``.
* ``is_blocked(venue)`` is the single source of truth the dispatcher
  consults before every outbound order tool.
* Role gate (``trading_supervisor``) is enforced BY THE DISPATCHER,
  not here — this class is pure mechanism.
"""

from __future__ import annotations

import json
import os
import threading
from datetime import datetime, timezone
from typing import Any


def _now_iso_z() -> str:
    return (
        datetime.now(tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


class KillSwitch:
    """File-backed global + per-venue toggle.

    File shape::

        {
          "global": {"on": false, "reason": "", "actor_aid": "", "set_at": "..."},
          "venues": {
             "<venue>": {"on": true, "reason": "...", "actor_aid": "...", "set_at": "..."}
          }
        }
    """

    def __init__(self, state_path: str) -> None:
        self._path = state_path
        self._lock = threading.Lock()
        os.makedirs(os.path.dirname(self._path) or ".", exist_ok=True)
        if not os.path.exists(self._path):
            self._write_atomic(
                {
                    "global": {"on": False, "reason": "", "actor_aid": "", "set_at": ""},
                    "venues": {},
                }
            )

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def is_blocked(self, venue: str) -> bool:
        """Return True iff global is on OR the given venue is on."""
        state = self._load()
        if state["global"]["on"]:
            return True
        v = state["venues"].get(venue)
        return bool(v and v.get("on"))

    def global_state(self) -> dict[str, Any]:
        return dict(self._load()["global"])

    def venue_state(self, venue: str) -> dict[str, Any]:
        st = self._load()
        v = st["venues"].get(venue)
        return dict(v) if v else {
            "on": False,
            "reason": "",
            "actor_aid": "",
            "set_at": "",
        }

    def snapshot(self) -> dict[str, Any]:
        return self._load()

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def set_global(self, on: bool, *, reason: str, actor_aid: str) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            state["global"] = {
                "on": bool(on),
                "reason": reason,
                "actor_aid": actor_aid,
                "set_at": _now_iso_z(),
            }
            self._write_atomic(state)
            return state["global"]

    def set_venue(
        self,
        venue: str,
        on: bool,
        *,
        reason: str,
        actor_aid: str,
    ) -> dict[str, Any]:
        with self._lock:
            state = self._load()
            state["venues"][venue] = {
                "on": bool(on),
                "reason": reason,
                "actor_aid": actor_aid,
                "set_at": _now_iso_z(),
            }
            self._write_atomic(state)
            return state["venues"][venue]

    # ------------------------------------------------------------------
    # I/O
    # ------------------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        try:
            with open(self._path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            # Defensive shape fill-in.
            if "global" not in data:
                data["global"] = {
                    "on": False,
                    "reason": "",
                    "actor_aid": "",
                    "set_at": "",
                }
            if "venues" not in data or not isinstance(data["venues"], dict):
                data["venues"] = {}
            return data
        except (OSError, json.JSONDecodeError):
            return {
                "global": {"on": False, "reason": "", "actor_aid": "", "set_at": ""},
                "venues": {},
            }

    def _write_atomic(self, data: dict[str, Any]) -> None:
        tmp = self._path + ".tmp"
        payload = json.dumps(data, separators=(",", ":"), sort_keys=True)
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(payload)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self._path)


__all__ = ["KillSwitch"]
