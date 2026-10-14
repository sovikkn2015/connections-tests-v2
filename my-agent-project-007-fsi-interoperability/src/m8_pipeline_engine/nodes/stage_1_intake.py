"""M8 stage 1: Parse utterance + routing_decision.entities.

LLM-bearing (Sonnet, 2K tokens). Extracts event_type / timeframe /
focus_areas. MNPI filtering happens at M12 upstream; M8 receives an
already-filtered utterance.
"""

from __future__ import annotations

from typing import Any

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


_PROMPT = (
    "Extract entities from this user query as JSON with keys event_type, "
    "timeframe, focus_areas. Query: {utterance}"
)


def stage_1_intake(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    utterance = state.get("user_utterance", "")
    reason_code = None
    intake: dict[str, Any] = {}
    tokens_in = tokens_out = 0

    prompt = _PROMPT.format(utterance=utterance)
    try:
        gen = llm.generate(
            stage_name="stage_1_intake",
            prompt=prompt,
            max_tokens=2000,
            temperature=0.1,
            response_format="json",
        )
        tokens_in, tokens_out = gen.input_tokens, gen.output_tokens
        try:
            import json
            intake = json.loads(gen.text) if gen.text else {}
            if not isinstance(intake, dict):
                intake = {"raw": gen.text}
        except Exception:
            intake = {"raw": gen.text}
    except LlmTimeoutError:
        reason_code = "m8_llm_timeout"
    except LlmMalformedOutputError:
        reason_code = "m8_llm_malformed_output"
    except LlmProviderError as exc:
        reason_code = "m8_llm_5xx" if exc.status_code >= 500 else "m8_llm_4xx"

    routing = state.get("routing_decision")
    entities: dict[str, str] = {}
    if routing is not None:
        entities = getattr(routing, "entities", {}) or {}
    instruments = [v for k, v in entities.items() if k in ("ticker", "security_id")]

    output: dict[str, Any] = {"intake": intake, "instruments": instruments}
    audit_stage(
        state,
        audit=audit,
        stage_number=1,
        stage_name="stage_1_intake",
        input_payload={"utterance_len": len(utterance)},
        output_payload=output,
        latency_ms=elapsed_ms(start),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_1_intake"]
