"""
M8 Pipeline Engine -- PipelineState TypedDict.

LangGraph StateGraph schema. v0.2.0 drops compliance_check field per Req-Fix 9
(never populated; stage 20 emits compliance_decision/rule/wsp directly).

Adds slow_alert_emitted bool (AC8.11 exactly-once gate).

See `.kiro/specs/m8-pipeline-engine.md` §LangGraph State Schema.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from m3_schema_registry import (
    Client,
    Holding,
    Household,
    InteractionSummary,
    ResearchBrief,
    ResearchSource,
)
from m9_intent_router.models import RoutingDecision  # annotation-only


class PipelineState(TypedDict, total=False):
    """LangGraph state for the 23-stage research pipeline.

    Every field is optional (total=False). Required-at-entry keys enforced by
    ``_validate_initial_state`` in graph.py: trace_id, thread_id,
    pipeline_run_id, tenant_id, firm_id, routing_decision, user_utterance,
    runtime, archetype.
    """

    # ---- IMMUTABLE INPUT (set by M12) ----
    trace_id: str
    thread_id: str
    pipeline_run_id: str
    tenant_id: str
    firm_id: str
    routing_decision: RoutingDecision
    user_utterance: str
    runtime: Literal["managed_agents", "strands"]
    archetype: Literal[
        "tier1_investment_bank",
        "tier2_asset_manager",
        "tier3_broker_dealer",
        "tier4_independent_ria",
        "tier5_hedge_fund",
    ]
    supervisor_aid_token: str

    # ---- STAGE 1 ----
    intake: dict[str, Any]
    instruments: list[str]

    # ---- STAGE 2 ----
    crm_context: dict[str, Any]
    primary_client: Optional[Client]
    primary_household: Optional[Household]
    prior_holdings: list[Holding]  # tax_lots[*].cost_basis_method REQUIRED (A12)
    prior_briefs: list[str]

    # ---- STAGES 3-6 ----
    market_data: dict[str, dict[str, Any]]
    news_items: dict[str, list[dict]]
    sec_filings: dict[str, dict[str, str]]
    transcript_summary: dict[str, str]

    # ---- GATE 1 (stage 7) ----
    gate_1_payload: dict[str, Any]
    gate_1_approved_by: Optional[str]
    gate_1_approved_at: Optional[datetime]

    # ---- STAGE 8 MAP-REDUCE ----
    discovered_instruments: list[str]
    dropped_instruments: list[str]
    per_instrument_results: dict[str, dict[str, Any]]
    per_instrument_errors: dict[str, str]

    # ---- STAGE 12 REDUCE ----
    cross_source_synthesis: dict[str, Any]

    # ---- GATE 2 (stage 13) ----
    gate_2_payload: dict[str, Any]
    gate_2_approved_by: Optional[str]
    gate_2_approved_at: Optional[datetime]

    # ---- STAGES 14-18 ----
    thesis: str
    catalysts: list[str]
    risks: list[str]
    rating: Literal["strong_buy", "buy", "hold", "sell", "strong_sell"]
    target_price: Optional[float]

    # ---- STAGE 19 ----
    draft_brief: Optional[ResearchBrief]
    data_sources: list[ResearchSource]
    interaction_summary: Optional[InteractionSummary]

    # ---- STAGE 20 (NO compliance_check -- dropped v0.2.0 Req-Fix 9) ----
    compliance_decision: Literal["ALLOW", "DENY", "ESCALATE"]
    compliance_escalation: bool   # A24: survives checkpoint round-trip
    compliance_rule_applied: Optional[str]
    compliance_wsp_section: Optional[str]

    # ---- GATE 3 (stage 21) ----
    gate_3_payload: dict[str, Any]
    gate_3_approved_by: Optional[str]
    gate_3_approved_at: Optional[datetime]
    anti_fabrication_failures: list[dict[str, Any]]

    # ---- TERMINAL ----
    final_brief: Optional[ResearchBrief]
    pipeline_status: Literal[
        "completed", "paused", "rejected", "timed_out", "terminated", "failed"
    ]
    terminal_reason_code: Optional[str]

    # ---- AUDIT BOOKKEEPING ----
    clock_stamps: dict[int, float]
    total_input_tokens: int
    total_output_tokens: int
    slow_alert_emitted: bool  # AC8.11 exactly-once gate (v0.2.0)


__all__ = ["PipelineState"]
