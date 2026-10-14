"""M8 stage 17: Rating determination (Sonnet, 2K tokens)."""

from __future__ import annotations

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


_ALLOWED = {"strong_buy", "buy", "hold", "sell", "strong_sell"}


def stage_17_rating_determination(
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
    rating = "hold"

    try:
        gen = llm.generate(
            stage_name="stage_17_rating_determination",
            prompt="Emit one of strong_buy/buy/hold/sell/strong_sell",
            max_tokens=2000,
            temperature=0.1,
            response_format="text",
        )
        tokens_in, tokens_out = gen.input_tokens, gen.output_tokens
        cand = (gen.text or "").strip().lower()
        if cand in _ALLOWED:
            rating = cand
    except LlmTimeoutError:
        reason_code = "m8_llm_timeout"
    except LlmMalformedOutputError:
        reason_code = "m8_llm_malformed_output"
    except LlmProviderError as exc:
        reason_code = "m8_llm_5xx" if exc.status_code >= 500 else "m8_llm_4xx"

    output = {"rating": rating}
    audit_stage(
        state,
        audit=audit,
        stage_number=17,
        stage_name="stage_17_rating_determination",
        input_payload=None,
        output_payload=output,
        latency_ms=elapsed_ms(start),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_17_rating_determination"]
