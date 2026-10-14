"""
M12 Supervisor Runtime -- Phase 2 lighthouse glue.

Thin wrapper connecting channel -> M9 intent router -> M8 research
pipeline -> M10 audit (via M8's own AuditClient). No Strands runtime
switch here -- deferred to Phase 3 per ARCH-10 Decision 2.

Public API -- 6 names:
  - dispatch
  - SupervisorResult
  - build_router_context
  - build_pipeline_state
  - SCHEMA_VERSION
  - VALID_REASON_CODES

Usage:
    from m12_supervisor import dispatch
    result = dispatch(utterance, aid_claims, trace_id,
                      _provider=prov, _config=cfg)

See the user task prompt for the full contract. DECISION-LOG.md holds
the v0.1.0 design notes.
"""

from __future__ import annotations

from m12_supervisor.context import build_pipeline_state, build_router_context
from m12_supervisor.dispatch import dispatch
from m12_supervisor.errors import VALID_REASON_CODES
from m12_supervisor.models import SupervisorResult
from m12_supervisor.specialists import (
    SPECIALIST_DISPATCH,
    get_specialist,
)

#: SemVer of the M12 public contract.
#:   v0.1.0 -- Phase 2 lighthouse (dispatch + M9 + M8).
#:   v0.2.0 -- Phase 3 Execution + Onboarding specialists registered.
SCHEMA_VERSION: str = "0.2.0"

__all__ = [
    "dispatch",
    "SupervisorResult",
    "build_router_context",
    "build_pipeline_state",
    "SCHEMA_VERSION",
    "VALID_REASON_CODES",
    "SPECIALIST_DISPATCH",
    "get_specialist",
]
