"""
M12 Supervisor -- helpers that build M9 RouterContext and M8 PipelineState.

Both helpers are pure. They centralise the field-mapping contract between
M12 and the two downstream modules so dispatch.py stays short.
"""

from __future__ import annotations

import uuid
from typing import Any

from m1_identity import AidClaims
from m5_config_loader import Archetype, Runtime

from m9_intent_router import RouterContext
from m9_intent_router.models import RoutingDecision


def build_router_context(aid_claims: AidClaims, trace_id: str) -> RouterContext:
    """Construct an M9 RouterContext from pre-verified AID claims.

    The channel already verified the AID via M1; M12 only reprojects the
    fields M9 needs. Archetype is read from the AID (Phase 2 RIA
    lighthouse -> tier4_independent_ria). Runtime defaults to
    managed_agents (cloud) per ARCH-07; on-prem/Strands is a Helm toggle
    outside M12's knowledge.
    """
    archetype = Archetype(aid_claims.archetype)
    return RouterContext(
        trace_id=trace_id,
        runtime=Runtime.managed_agents,
        archetype=archetype,
        tenant_id=aid_claims.firm_id,
        identity=aid_claims,
        prior_turns_summary=None,
    )


def build_pipeline_state(
    aid_claims: AidClaims,
    trace_id: str,
    user_utterance: str,
    routing_decision: RoutingDecision,
) -> dict[str, Any]:
    """Construct an M8 PipelineState entry dict from the routing decision.

    Returns a plain dict (LangGraph TypedDict does not support
    isinstance checks; M8's _validate_initial_state walks required keys).
    Populates every required-at-entry key from M8's state.py:
    trace_id, thread_id, pipeline_run_id, tenant_id, firm_id,
    routing_decision, user_utterance, runtime, archetype.
    """
    thread_id = "thread-" + uuid.uuid4().hex[:16]
    return {
        "trace_id": trace_id,
        "thread_id": thread_id,
        "pipeline_run_id": "run-" + uuid.uuid4().hex[:12],
        "tenant_id": aid_claims.firm_id,
        "firm_id": aid_claims.firm_id,
        "routing_decision": routing_decision,
        "user_utterance": user_utterance,
        "runtime": "managed_agents",
        "archetype": aid_claims.archetype,
        "supervisor_aid_token": aid_claims.jti,
    }


__all__ = ["build_router_context", "build_pipeline_state"]
