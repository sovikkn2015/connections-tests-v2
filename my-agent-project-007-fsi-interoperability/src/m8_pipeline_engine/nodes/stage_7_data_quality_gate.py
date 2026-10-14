"""M8 stage 7: HITL Gate 1 -- data quality review.

Pre-populates gate_1_payload. The interrupt() call happens at graph edge level.
"""

from __future__ import annotations

from datetime import datetime, timezone

from m8_pipeline_engine.hitl import build_gate_payload
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_7_data_quality_gate(
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
        "instruments": state.get("instruments", []),
        "source_count": len(state.get("data_sources", []) or []),
        "news_count": sum(
            len(v) for v in (state.get("news_items", {}) or {}).values()
        ),
    }
    payload = build_gate_payload(
        gate_id=1,
        pipeline_run_id=state.get("pipeline_run_id", ""),
        thread_id=state.get("thread_id", ""),
        summary=summary,
        emitted_at=datetime.now(timezone.utc),
    )
    output = {"gate_1_payload": payload.model_dump(mode="json")}
    audit_stage(
        state,
        audit=audit,
        stage_number=7,
        stage_name="stage_7_data_quality_gate",
        input_payload=summary,
        output_payload=output,
        latency_ms=elapsed_ms(start),
        event_type="m8.hitl_gate_entered",
    )
    return output


__all__ = ["stage_7_data_quality_gate"]
