"""M8 stage 18: Deterministic weighted-average target price. NO LLM."""

from __future__ import annotations

from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_18_target_price_calc(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    per = state.get("per_instrument_results", {}) or {}
    prices: list[float] = []
    for v in per.values():
        if isinstance(v, dict) and isinstance(v.get("dcf_target"), (int, float)):
            prices.append(float(v["dcf_target"]))
    target = sum(prices) / len(prices) if prices else None
    output = {"target_price": target}
    audit_stage(
        state,
        audit=audit,
        stage_number=18,
        stage_name="stage_18_target_price_calc",
        input_payload={"price_count": len(prices)},
        output_payload=output,
        latency_ms=elapsed_ms(start),
    )
    return output


__all__ = ["stage_18_target_price_calc"]
