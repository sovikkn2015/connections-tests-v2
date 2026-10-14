"""M8 stage 12: Cross-source synthesis - REDUCE across instruments + sources.

AC5.4 (reducer), AC5.5 (all-failed case), AC5.8 (zero-fan-out bypass).
"""

from __future__ import annotations

from typing import Any

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_12_cross_source_synthesis(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    discovered = list(state.get("discovered_instruments", []) or [])
    per_instrument = state.get("per_instrument_results", {}) or {}

    # AC5.8 zero-fan-out bypass -- emit single_tool_bypass audit
    if len(discovered) == 0:
        output: dict[str, Any] = {"cross_source_synthesis": {}}
        audit_stage(
            state,
            audit=audit,
            stage_number=12,
            stage_name="stage_12_cross_source_synthesis",
            input_payload={"discovered_count": 0},
            output_payload={},
            latency_ms=elapsed_ms(start),
            event_type="m8.single_tool_bypass",
            reason_code=None,
        )
        return output

    # AC5.5 all-instruments-failed guard
    if not per_instrument and discovered:
        output = {"cross_source_synthesis": {}}
        audit_stage(
            state,
            audit=audit,
            stage_number=12,
            stage_name="stage_12_cross_source_synthesis",
            input_payload={"discovered_count": len(discovered)},
            output_payload={},
            latency_ms=elapsed_ms(start),
            reason_code="m8_map_reduce_all_failed",
        )
        return output

    reason_code = None
    tokens_in = tokens_out = 0
    synthesis: dict[str, Any] = {}
    # AC A16: reducer iterates in sorted() order for determinism
    try:
        summaries = {k: per_instrument[k] for k in sorted(per_instrument.keys())}
        prompt = f"Synthesize across these per-instrument results: {summaries}"
        gen = llm.generate(
            stage_name="stage_12_cross_source_synthesis",
            prompt=prompt,
            max_tokens=15000,
            temperature=0.3,
            response_format="text",
        )
        tokens_in, tokens_out = gen.input_tokens, gen.output_tokens
        synthesis = {"summary": gen.text, "instrument_count": len(summaries)}
    except LlmTimeoutError:
        reason_code = "m8_llm_timeout"
    except LlmMalformedOutputError:
        reason_code = "m8_llm_malformed_output"
    except LlmProviderError as exc:
        reason_code = "m8_llm_5xx" if exc.status_code >= 500 else "m8_llm_4xx"

    output = {"cross_source_synthesis": synthesis}
    audit_stage(
        state,
        audit=audit,
        stage_number=12,
        stage_name="stage_12_cross_source_synthesis",
        input_payload={"discovered_count": len(discovered)},
        output_payload={"summary_len": len(synthesis.get("summary", ""))},
        latency_ms=elapsed_ms(start),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_12_cross_source_synthesis"]
