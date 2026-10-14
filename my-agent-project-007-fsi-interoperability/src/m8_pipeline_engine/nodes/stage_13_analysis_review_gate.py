"""M8 stage 13: HITL Gate 2 -- analysis review."""

from __future__ import annotations

from datetime import datetime, timezone

from m8_pipeline_engine.hitl import build_gate_payload
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_13_analysis_review_gate(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    summary = {
        "per_instrument_count": len(state.get("per_instrument_results", {}) or {}),
        "dropped_instruments": state.get("dropped_instruments", []),
        "compliance_escalation": bool(state.get("compliance_escalation", False)),
    }
    payload = build_gate_payload(
        gate_id=2,
        pipeline_run_id=state.get("pipeline_run_id", ""),
        thread_id=state.get("thread_id", ""),
        summary=summary,
        emitted_at=datetime.now(timezone.utc),
    )
    output = {"gate_2_payload": payload.model_dump(mode="json")}
    audit_stage(
        state,
        audit=audit,
        stage_number=13,
        stage_name="stage_13_analysis_review_gate",
        input_payload=summary,
        output_payload=output,
        latency_ms=elapsed_ms(start),
        event_type="m8.hitl_gate_entered",
    )
    return output


__all__ = ["stage_13_analysis_review_gate"]
