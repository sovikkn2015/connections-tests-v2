"""Health check helper for ``GET /`` (Spec §R1.1).

Rules:

* ``FIX_ENABLED=false`` → always OK (graceful-disabled mode).
* ``FIX_ENABLED=true`` and at least one session ACTIVE → OK.
* ``FIX_ENABLED=true`` and no session ACTIVE → DEGRADED (503).

The status includes a small ``checks`` map to surface the session
manager's view of per-venue state without exposing CompIDs or other
identifiers (those are already in ``fix.session_status`` which is
role-gated via the dispatcher).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from m13_fix_bridge.client.session_manager import SessionManager


@dataclass(frozen=True)
class HealthStatus:
    ok: bool
    checks: Mapping[str, str]


def health_status(
    *,
    session_manager: SessionManager,
    fix_enabled: bool,
) -> HealthStatus:
    if not fix_enabled:
        return HealthStatus(ok=True, checks={"fix": "disabled"})
    venues = session_manager.known_venues()
    if not venues:
        return HealthStatus(ok=False, checks={"fix": "no_venues_configured"})
    states: dict[str, str] = {}
    any_active = False
    for v in venues:
        st = session_manager.session_status(v)
        if st is None:
            states[v] = "unknown"
        else:
            states[v] = st.logon_status
            if st.logon_status == "ACTIVE":
                any_active = True
    return HealthStatus(ok=any_active, checks=states)


__all__ = ["HealthStatus", "health_status"]
