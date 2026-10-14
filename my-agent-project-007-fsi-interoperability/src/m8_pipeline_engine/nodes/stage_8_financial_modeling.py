"""M8 stage 8: Financial modeling - map-reduce fan-out via LangGraph Send API.

AC5.1 + AC5.3 + AC5.7 + AC5.8 (zero-fan-out single-tool bypass).
"""

from __future__ import annotations

from typing import Any

from langgraph.types import Send

from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_8_financial_modeling(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    """Returns a partial state update. The conditional edge registered in
    graph.py separately dispatches ``Send`` objects via ``_fan_out_instruments``.
    """
    start = timed()
    instruments = list(state.get("instruments", []) or [])
    # Discovered instruments may have been set by an earlier stage
    discovered = list(state.get("discovered_instruments", []) or instruments)
    cap = 10
    if config is not None:
        cap = getattr(config, "max_concurrent_instruments", 10)

    reason_code = None
    dropped: list[str] = list(state.get("dropped_instruments", []) or [])

    # AC5.7 -- too-wide warning
    if len(discovered) > cap * 3:
        reason_code = "m8_map_reduce_too_wide"

    # Cap
    if len(discovered) > cap:
        dropped.extend(discovered[cap:])
        discovered = discovered[:cap]

    output: dict[str, Any] = {
        "discovered_instruments": discovered,
        "dropped_instruments": dropped,
    }
    audit_stage(
        state,
        audit=audit,
        stage_number=8,
        stage_name="stage_8_financial_modeling",
        input_payload={"instrument_count": len(instruments)},
        output_payload={
            "discovered_count": len(discovered),
            "dropped_count": len(dropped),
        },
        latency_ms=elapsed_ms(start),
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_8_financial_modeling"]
