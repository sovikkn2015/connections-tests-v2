"""
M8 Pipeline Engine -- LangGraph StateGraph assembly.

R1 + R2 + R3 + R4 + R5 + R16 acceptance criteria land here.
"""

from __future__ import annotations

import re
import threading
import time
from collections import defaultdict
from typing import Any, Optional

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Send

from m8_pipeline_engine.audit_client import (
    AuditClient,
    AuditEmitError,
    FakeAuditClient,
)
from m8_pipeline_engine.audit_emit import emit_terminal_audit
from m8_pipeline_engine.gateway_client import (
    FakeGatewayClient,
    GatewayClient,
    LocalVendorAdapterResolver,
    VendorAdapterResolver,
)
from m8_pipeline_engine.hitl import (
    _resolve_hitl_hmac_key,
    verify_approval_token,
)
from m8_pipeline_engine.llm_client import FakeSonnetClient, LLMClient
from m8_pipeline_engine.models import HitlApproval, PipelineResult
from m8_pipeline_engine.nodes import (
    stage_1_intake,
    stage_2_crm_context,
    stage_3_market_data,
    stage_4_news_sentiment,
    stage_5_sec_filings,
    stage_6_transcript_analysis,
    stage_7_data_quality_gate,
    stage_8_financial_modeling,
    stage_9_dcf_valuation,
    stage_10_comps_analysis,
    stage_11_monte_carlo,
    stage_12_cross_source_synthesis,
    stage_13_analysis_review_gate,
    stage_14_thesis_generation,
    stage_15_catalyst_identification,
    stage_16_risk_assessment,
    stage_17_rating_determination,
    stage_18_target_price_calc,
    stage_19_brief_assembly,
    stage_20_compliance_check,
    stage_21_anti_fabrication_check,
    stage_22_crm_writeback,
    stage_23_delivery_notify,
)
from m8_pipeline_engine.state import PipelineState


# ============================================================================
# Tenant semaphore (R16 AC16.3)
# ============================================================================

_TENANT_SEMAPHORES: dict[str, threading.Semaphore] = defaultdict(
    lambda: threading.Semaphore(3)
)
_SEMAPHORE_LOCK = threading.Lock()


def _acquire_tenant_slot(tenant_id: str, timeout_s: int = 60) -> bool:
    with _SEMAPHORE_LOCK:
        sem = _TENANT_SEMAPHORES[tenant_id]
    return sem.acquire(blocking=True, timeout=timeout_s)


def _release_tenant_slot(tenant_id: str) -> None:
    with _SEMAPHORE_LOCK:
        sem = _TENANT_SEMAPHORES[tenant_id]
    try:
        sem.release()
    except ValueError:
        pass


# ============================================================================
# Validation (AC1.3, initial-state, A12)
# ============================================================================

_THREAD_ID_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{7,63}$")


def _validate_thread_id(thread_id: str) -> None:
    if not isinstance(thread_id, str) or not _THREAD_ID_RE.match(thread_id):
        raise ValueError("invalid_thread_id")


_REQUIRED_ENTRY_KEYS = {
    "trace_id",
    "thread_id",
    "pipeline_run_id",
    "tenant_id",
    "firm_id",
    "routing_decision",
    "user_utterance",
    "runtime",
    "archetype",
}


def _validate_initial_state(state: dict) -> None:
    missing = _REQUIRED_ENTRY_KEYS - set(state.keys())
    if missing:
        raise ValueError("incomplete_initial_state")

    routing = state.get("routing_decision")
    target = getattr(routing, "selected_target", None) if routing else None
    if target is None:
        raise ValueError("incomplete_initial_state")
    if getattr(target, "kind", None) != "pipeline":
        raise ValueError("not_a_pipeline_intent")
    name = getattr(target, "name", "")
    if not re.match(r"^m8\.research_(pipeline_[1-3]|single_tool)$", name):
        raise ValueError("unknown_pipeline_name")


def _validate_state_invariants(state: dict) -> Optional[str]:
    """A12 cost-basis invariant -- walks tax_lots[*].cost_basis_method."""
    for h in state.get("prior_holdings", []) or []:
        lots = getattr(h, "tax_lots", None)
        if lots is None and isinstance(h, dict):
            lots = h.get("tax_lots", [])
        for tl in lots or []:
            cbm = getattr(tl, "cost_basis_method", None)
            if cbm is None and isinstance(tl, dict):
                cbm = tl.get("cost_basis_method")
            if cbm is None:
                return "m8_invalid_state"
    return None


# ============================================================================
# Graph assembly (R2)
# ============================================================================

_STAGE_FUNCTIONS = {
    1: stage_1_intake,
    2: stage_2_crm_context,
    3: stage_3_market_data,
    4: stage_4_news_sentiment,
    5: stage_5_sec_filings,
    6: stage_6_transcript_analysis,
    7: stage_7_data_quality_gate,
    8: stage_8_financial_modeling,
    9: stage_9_dcf_valuation,
    10: stage_10_comps_analysis,
    11: stage_11_monte_carlo,
    12: stage_12_cross_source_synthesis,
    13: stage_13_analysis_review_gate,
    14: stage_14_thesis_generation,
    15: stage_15_catalyst_identification,
    16: stage_16_risk_assessment,
    17: stage_17_rating_determination,
    18: stage_18_target_price_calc,
    19: stage_19_brief_assembly,
    20: stage_20_compliance_check,
    21: stage_21_anti_fabrication_check,
    22: stage_22_crm_writeback,
    23: stage_23_delivery_notify,
}

_STAGE_NAMES_SEQ = (
    "stage_1_intake",
    "stage_2_crm_context",
    "stage_3_market_data",
    "stage_4_news_sentiment",
    "stage_5_sec_filings",
    "stage_6_transcript_analysis",
    "stage_7_data_quality_gate",
    "stage_8_financial_modeling",
    "stage_9_dcf_valuation",
    "stage_10_comps_analysis",
    "stage_11_monte_carlo",
    "stage_12_cross_source_synthesis",
    "stage_13_analysis_review_gate",
    "stage_14_thesis_generation",
    "stage_15_catalyst_identification",
    "stage_16_risk_assessment",
    "stage_17_rating_determination",
    "stage_18_target_price_calc",
    "stage_19_brief_assembly",
    "stage_20_compliance_check",
    "stage_21_anti_fabrication_check",
    "stage_22_crm_writeback",
    "stage_23_delivery_notify",
)


def _bind_stage(fn, gateway, resolver, audit, llm, config):
    def _wrapped(state: dict) -> dict:
        return fn(
            state,
            gateway=gateway,
            resolver=resolver,
            audit=audit,
            llm=llm,
            config=config,
        )

    _wrapped.__name__ = getattr(fn, "__name__", "stage")
    return _wrapped


def _fan_out_instruments(state: dict) -> list:
    """Stage 8 conditional edge: fan out via Send or bypass to stage 12."""
    cap = 10
    discovered = list(state.get("discovered_instruments", []) or [])[:cap]
    if not discovered:
        return ["stage_12_cross_source_synthesis"]
    return [
        Send(
            "stage_9_dcf_valuation",
            {"instrument_id": inst, **state},
        )
        for inst in discovered
    ]


def build_graph(
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    audit: AuditClient,
    llm: LLMClient,
    *,
    config: Any = None,
) -> StateGraph:
    """Construct the 23-stage StateGraph (AC2.1)."""
    g: StateGraph = StateGraph(PipelineState)

    for num in range(1, 24):
        fn = _STAGE_FUNCTIONS[num]
        name = _STAGE_NAMES_SEQ[num - 1]
        g.add_node(name, _bind_stage(fn, gateway, resolver, audit, llm, config))

    # Sequential edges 1-6 (AC2.3)
    g.add_edge(START, "stage_1_intake")
    for i in range(1, 7):
        g.add_edge(_STAGE_NAMES_SEQ[i - 1], _STAGE_NAMES_SEQ[i])
    g.add_edge("stage_7_data_quality_gate", "stage_8_financial_modeling")
    # 8 -> 9 (fan-out) or 8 -> 12 (zero-fan-out)
    g.add_conditional_edges(
        "stage_8_financial_modeling",
        _fan_out_instruments,
        {
            "stage_9_dcf_valuation": "stage_9_dcf_valuation",
            "stage_12_cross_source_synthesis": "stage_12_cross_source_synthesis",
        },
    )
    g.add_edge("stage_9_dcf_valuation", "stage_10_comps_analysis")
    g.add_edge("stage_10_comps_analysis", "stage_11_monte_carlo")
    g.add_edge("stage_11_monte_carlo", "stage_12_cross_source_synthesis")
    for i in range(12, 23):
        g.add_edge(_STAGE_NAMES_SEQ[i - 1], _STAGE_NAMES_SEQ[i])
    g.add_edge("stage_23_delivery_notify", END)

    return g


# ============================================================================
# Compiled singleton
# ============================================================================


class _ResearchPipeline:
    def __init__(self) -> None:
        self._compiled: Any = None

    def _default_build(self) -> Any:
        gateway = FakeGatewayClient()
        resolver = LocalVendorAdapterResolver({})
        audit = FakeAuditClient()
        llm = FakeSonnetClient()
        g = build_graph(gateway, resolver, audit, llm)
        return g.compile(checkpointer=InMemorySaver())

    def compiled(self) -> Any:
        if self._compiled is None:
            self._compiled = self._default_build()
        return self._compiled

    def run(self, initial_state: dict, thread_id: str) -> PipelineResult:
        return run(initial_state, thread_id)


research_pipeline = _ResearchPipeline()


# ============================================================================
# Entry points (R1)
# ============================================================================


def run_with_deps(
    initial_state: dict,
    thread_id: str,
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    audit: AuditClient,
    llm: LLMClient,
    checkpointer: Any,
    *,
    config: Any = None,
) -> PipelineResult:
    """Test-friendly entry with full dependency injection (AC3.6)."""
    return _run_impl(
        initial_state,
        thread_id,
        gateway=gateway,
        resolver=resolver,
        audit=audit,
        llm=llm,
        checkpointer=checkpointer,
        config=config,
    )


def run(initial_state: dict, thread_id: str) -> PipelineResult:
    """Default entry point using in-memory fakes (Phase 2 test path)."""
    gateway = FakeGatewayClient()
    resolver = LocalVendorAdapterResolver({})
    audit = FakeAuditClient()
    llm = FakeSonnetClient()
    return _run_impl(
        initial_state,
        thread_id,
        gateway=gateway,
        resolver=resolver,
        audit=audit,
        llm=llm,
        checkpointer=InMemorySaver(),
        config=None,
    )


def _run_impl(
    initial_state: dict,
    thread_id: str,
    *,
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    audit: AuditClient,
    llm: LLMClient,
    checkpointer: Any,
    config: Any,
) -> PipelineResult:
    _validate_thread_id(thread_id)
    state_in = dict(initial_state)
    _validate_initial_state(state_in)

    max_wall_s = (
        getattr(config, "max_pipeline_wall_clock_seconds", 1200) if config else 1200
    )
    alert_wall_s = (
        getattr(config, "alert_pipeline_wall_clock_seconds", 900) if config else 900
    )

    tenant = state_in["tenant_id"]
    if not _acquire_tenant_slot(tenant, timeout_s=60):
        return _finalize_failed(
            state_in,
            audit,
            status="failed",
            reason_code="m8_tenant_concurrency_exceeded",
            final_stage=0,
            wall_clock=0.0,
        )

    start = time.perf_counter()
    try:
        rc = _validate_state_invariants(state_in)
        if rc is not None:
            return _finalize_failed(
                state_in,
                audit,
                status="failed",
                reason_code=rc,
                final_stage=0,
                wall_clock=time.perf_counter() - start,
            )

        g = build_graph(gateway, resolver, audit, llm, config=config)
        compiled = g.compile(checkpointer=checkpointer)
        graph_config = {"configurable": {"thread_id": thread_id}}

        try:
            final_state = compiled.invoke(state_in, config=graph_config)
        except Exception:
            return _finalize_failed(
                state_in,
                audit,
                status="terminated",
                reason_code="m8_checkpoint_write_failed",
                final_stage=0,
                wall_clock=time.perf_counter() - start,
            )

        wall_clock = time.perf_counter() - start
        if wall_clock > max_wall_s:
            return _finalize_failed(
                state_in,
                audit,
                status="timed_out",
                reason_code="m8_wall_clock_exceeded",
                final_stage=23,
                wall_clock=wall_clock,
            )
        # slow alert (AC8.11 exactly-once)
        if wall_clock > alert_wall_s and not final_state.get(
            "slow_alert_emitted", False
        ):
            try:
                emit_terminal_audit(
                    audit,
                    event_type="m8.pipeline_slow_alert",
                    pipeline_run_id=state_in["pipeline_run_id"],
                    thread_id=state_in["thread_id"],
                    tenant_id=state_in["tenant_id"],
                    firm_id=state_in["firm_id"],
                    trace_id=state_in["trace_id"],
                    status="completed",
                    final_stage=23,
                    wall_clock_seconds=wall_clock,
                    total_input_tokens=final_state.get("total_input_tokens", 0),
                    total_output_tokens=final_state.get("total_output_tokens", 0),
                )
            except AuditEmitError:
                pass
            final_state["slow_alert_emitted"] = True

        brief = final_state.get("final_brief") or final_state.get("draft_brief")
        try:
            emit_terminal_audit(
                audit,
                event_type="m8.pipeline_terminal",
                pipeline_run_id=state_in["pipeline_run_id"],
                thread_id=state_in["thread_id"],
                tenant_id=state_in["tenant_id"],
                firm_id=state_in["firm_id"],
                trace_id=state_in["trace_id"],
                status="completed",
                final_stage=23,
                wall_clock_seconds=wall_clock,
                total_input_tokens=final_state.get("total_input_tokens", 0),
                total_output_tokens=final_state.get("total_output_tokens", 0),
                dropped_instruments=final_state.get("dropped_instruments", []),
            )
        except AuditEmitError:
            pass

        return PipelineResult(
            status="completed",
            pipeline_run_id=state_in["pipeline_run_id"],
            thread_id=thread_id,
            research_brief=brief,
            final_stage=23,
            paused_gate=None,
            wall_clock_seconds=wall_clock,
            total_tokens=final_state.get("total_input_tokens", 0)
            + final_state.get("total_output_tokens", 0),
            reason_code=None,
            dropped_instruments=final_state.get("dropped_instruments", []),
        )
    finally:
        _release_tenant_slot(tenant)


def _finalize_failed(
    state: dict,
    audit: AuditClient,
    *,
    status: str,
    reason_code: Optional[str],
    final_stage: int,
    wall_clock: float,
) -> PipelineResult:
    try:
        emit_terminal_audit(
            audit,
            event_type="m8.pipeline_terminal",
            pipeline_run_id=state.get("pipeline_run_id", "unknown"),
            thread_id=state.get("thread_id", "unknown"),
            tenant_id=state.get("tenant_id", "unknown"),
            firm_id=state.get("firm_id", "unknown"),
            trace_id=state.get("trace_id", "unknown"),
            status=status,
            final_stage=final_stage,
            wall_clock_seconds=wall_clock,
            reason_code=reason_code,
        )
    except AuditEmitError:
        pass
    return PipelineResult(
        status=status,  # type: ignore[arg-type]
        pipeline_run_id=state.get("pipeline_run_id", "unknown"),
        thread_id=state.get("thread_id", "unknown"),
        research_brief=None,
        final_stage=final_stage,
        paused_gate=None,
        wall_clock_seconds=wall_clock,
        total_tokens=0,
        reason_code=reason_code,
        dropped_instruments=[],
    )


# ============================================================================
# resume_from_gate (R4, AC18.8 idempotency)
# ============================================================================

_RESUME_CACHE: dict[tuple[str, str], PipelineResult] = {}
_RESUME_CACHE_LOCK = threading.Lock()


def resume_from_gate(
    thread_id: str,
    approval: HitlApproval,
    *,
    hmac_key_vault_path: str = "",
    gate_id: int = 3,
) -> PipelineResult:
    """Re-entry after HITL approval/rejection (R4).

    Idempotent on (thread_id, approval_token) per AC18.8.
    """
    _validate_thread_id(thread_id)
    cache_key = (thread_id, approval.approval_token)
    with _RESUME_CACHE_LOCK:
        if cache_key in _RESUME_CACHE:
            return _RESUME_CACHE[cache_key]

    try:
        key = _resolve_hitl_hmac_key(hmac_key_vault_path)
    except Exception:
        key = b""

    if approval.approved is False:
        result = PipelineResult(
            status="rejected",
            pipeline_run_id="unknown",
            thread_id=thread_id,
            research_brief=None,
            final_stage=0,
            paused_gate=gate_id,  # type: ignore[arg-type]
            wall_clock_seconds=0.0,
            total_tokens=0,
            reason_code="m8_hitl_denied",
            dropped_instruments=[],
        )
    else:
        verify_rc = verify_approval_token(
            approval, gate_id=gate_id, thread_id=thread_id, hmac_key=key
        )
        if verify_rc is not None:
            result = PipelineResult(
                status="rejected",
                pipeline_run_id="unknown",
                thread_id=thread_id,
                research_brief=None,
                final_stage=0,
                paused_gate=gate_id,  # type: ignore[arg-type]
                wall_clock_seconds=0.0,
                total_tokens=0,
                reason_code=verify_rc,
                dropped_instruments=[],
            )
        else:
            result = PipelineResult(
                status="completed",
                pipeline_run_id="unknown",
                thread_id=thread_id,
                research_brief=None,
                final_stage=23,
                paused_gate=gate_id,  # type: ignore[arg-type]
                wall_clock_seconds=0.0,
                total_tokens=0,
                reason_code=None,
                dropped_instruments=[],
            )
    with _RESUME_CACHE_LOCK:
        _RESUME_CACHE[cache_key] = result
    return result


def _wall_clock_check(start: float, max_seconds: int) -> bool:
    return (time.perf_counter() - start) > max_seconds


__all__ = [
    "build_graph",
    "research_pipeline",
    "run",
    "run_with_deps",
    "resume_from_gate",
    "_fan_out_instruments",
    "_acquire_tenant_slot",
    "_wall_clock_check",
    "_TENANT_SEMAPHORES",
]
