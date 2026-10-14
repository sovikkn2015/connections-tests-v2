"""M8 stage 23: Terminal -- emit completion marker.

Returns pipeline_status = 'completed'. The graph.py run() wrapper emits the
m8.pipeline_terminal audit event.
"""

from __future__ import annotations

from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_23_delivery_notify(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    output = {"pipeline_status": "completed"}
    audit_stage(
        state,
        audit=audit,
        stage_number=23,
        stage_name="stage_23_delivery_notify",
        input_payload=None,
        output_payload=output,
        latency_ms=elapsed_ms(start),
    )
    return output


__all__ = ["stage_23_delivery_notify"]
