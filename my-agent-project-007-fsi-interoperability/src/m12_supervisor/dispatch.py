"""
M12 Supervisor -- dispatch() entry point.

Thin glue between channel (OpenClaw/Managed Agents) -> M9 intent router
-> M8 research pipeline. M12 does NOT orchestrate; the channel drives
the agent loop. M12 does NOT call M6; tool dispatch is the channel's
job (returns tool_target for the channel to forward via M6).

Contract: dispatch() NEVER raises. Every failure path returns a
SupervisorResult with a status in
{completed, paused, rejected, escalated, timed_out, failed}.
"""

from __future__ import annotations

import time
from typing import Any

from m1_identity import AidClaims

from m8_pipeline_engine import PipelineResult, run
from m9_intent_router import route

from m12_supervisor.context import build_pipeline_state, build_router_context
from m12_supervisor.models import SupervisorResult


def dispatch(
    user_utterance: str,
    aid_claims: Any,
    trace_id: str,
    *,
    _provider: Any = None,
    _config: Any = None,
) -> SupervisorResult:
    """Dispatch a user utterance through M9 -> M8 and return a result.

    Args:
        user_utterance: Raw user text from the channel.
        aid_claims: Pre-verified AidClaims from M1 (duck-typed).
        trace_id: Request-scoped trace id propagated by the channel.
        _provider: LLMProvider for M9 (dependency-injected for tests).
        _config: IntentRouterConfig-shaped config (duck-typed).

    Returns:
        SupervisorResult. Never raises.
    """
    start = time.perf_counter()
    tenant_id = getattr(aid_claims, "firm_id", None) or "unknown"

    # Step 1: validate AID shape.
    if not isinstance(aid_claims, AidClaims):
        return SupervisorResult(
            status="failed",
            routing_decision=None,
            trace_id=trace_id,
            wall_clock_seconds=time.perf_counter() - start,
            reason_code="m12_invalid_aid",
            tenant_id=tenant_id,
        )

    # Step 2: build M9 RouterContext + classify.
    try:
        router_context = build_router_context(aid_claims, trace_id)
        decision = route(
            user_utterance,
            router_context,
            _provider=_provider,
            _config=_config,
        )
    except Exception:
        return SupervisorResult(
            status="failed",
            routing_decision=None,
            trace_id=trace_id,
            wall_clock_seconds=time.perf_counter() - start,
            reason_code="m12_routing_failed",
            tenant_id=aid_claims.firm_id,
        )

    target = decision.selected_target

    # Step 3a: escalate -> the specialist owns the conversation now.
    if target.kind == "escalate":
        return SupervisorResult(
            status="escalated",
            routing_decision=decision,
            escalation_target=target.name,
            trace_id=trace_id,
            wall_clock_seconds=time.perf_counter() - start,
            reason_code=decision.reason_code,
            tenant_id=aid_claims.firm_id,
        )

    # Step 3b: tool -> return the tool name; channel dispatches via M6.
    if target.kind == "tool":
        return SupervisorResult(
            status="completed",
            routing_decision=decision,
            tool_target=target.name,
            trace_id=trace_id,
            wall_clock_seconds=time.perf_counter() - start,
            reason_code=decision.reason_code,
            tenant_id=aid_claims.firm_id,
        )

    # Step 3c: pipeline -> build state, run M8, map result.
    try:
        state = build_pipeline_state(
            aid_claims, trace_id, user_utterance, decision
        )
        pipeline_result = run(state, state["thread_id"])
    except Exception:
        return SupervisorResult(
            status="failed",
            routing_decision=decision,
            trace_id=trace_id,
            wall_clock_seconds=time.perf_counter() - start,
            reason_code="m12_dispatch_failed",
            tenant_id=aid_claims.firm_id,
        )

    if not isinstance(pipeline_result, PipelineResult):
        return SupervisorResult(
            status="failed",
            routing_decision=decision,
            trace_id=trace_id,
            wall_clock_seconds=time.perf_counter() - start,
            reason_code="m12_invalid_pipeline_result",
            tenant_id=aid_claims.firm_id,
        )

    return SupervisorResult(
        status=_map_pipeline_status(pipeline_result.status),
        routing_decision=decision,
        pipeline_result=pipeline_result,
        trace_id=trace_id,
        wall_clock_seconds=time.perf_counter() - start,
        reason_code=pipeline_result.reason_code,
        tenant_id=aid_claims.firm_id,
    )


def _map_pipeline_status(m8_status: str) -> str:
    """Map M8 terminal statuses onto SupervisorResult.status vocabulary.

    M8 uses 'terminated' for checkpoint-write failures; M12 surfaces that
    as 'failed'. Everything else passes through verbatim.
    """
    if m8_status == "terminated":
        return "failed"
    return m8_status


__all__ = ["dispatch"]
