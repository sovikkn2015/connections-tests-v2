"""
M12 Supervisor -- closed reason-code vocabulary.

M12 is a thin dispatch wrapper, so its codes cover only the glue-layer
failure modes. Downstream reason codes (m8_*, m9_*) flow through
untouched on SupervisorResult when the child module populated them.
"""

from __future__ import annotations

#: Closed reason_code vocabulary for M12's own decisions.
VALID_REASON_CODES: frozenset[str] = frozenset({
    "m12_invalid_aid",             # aid_claims missing or wrong duck-type
    "m12_invalid_pipeline_result",  # M8 returned an unexpected shape
    "m12_routing_failed",           # M9 raised unexpectedly
    "m12_dispatch_failed",          # generic glue failure
})
