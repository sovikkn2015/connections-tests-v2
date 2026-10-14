"""M8 stage 14: Thesis narrative (Sonnet, 8K tokens)."""

from __future__ import annotations

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_14_thesis_generation(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    reason_code = None
    tokens_in = tokens_out = 0
    thesis = ""
    try:
        gen = llm.generate(
            stage_name="stage_14_thesis_generation",
            prompt=f"Thesis for {state.get('instruments', [])}",
            max_tokens=8000,
            temperature=0.3,
            response_format="text",
        )
        tokens_in, tokens_out = gen.input_tokens, gen.output_tokens
        thesis = gen.text or ""
    except LlmTimeoutError:
        reason_code = "m8_llm_timeout"
    except LlmMalformedOutputError:
        reason_code = "m8_llm_malformed_output"
    except LlmProviderError as exc:
        reason_code = "m8_llm_5xx" if exc.status_code >= 500 else "m8_llm_4xx"
    output = {"thesis": thesis or "(no thesis)"}
    audit_stage(
        state,
        audit=audit,
        stage_number=14,
        stage_name="stage_14_thesis_generation",
        input_payload=None,
        output_payload={"thesis_len": len(thesis)},
        latency_ms=elapsed_ms(start),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_14_thesis_generation"]
