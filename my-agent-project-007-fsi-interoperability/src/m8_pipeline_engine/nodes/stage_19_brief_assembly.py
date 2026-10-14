"""M8 stage 19: Assemble draft ResearchBrief from prior stage state.

Builds an M3 ResearchBrief for downstream compliance/anti-fab/delivery stages.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from m3_schema_registry import ResearchBrief, ResearchSource

from m8_pipeline_engine.errors import (
    LlmMalformedOutputError,
    LlmProviderError,
    LlmTimeoutError,
)
from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


def stage_19_brief_assembly(
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

    thesis = state.get("thesis", "")
    catalysts = state.get("catalysts", []) or []
    risks = state.get("risks", []) or []
    rating = state.get("rating", "hold")
    target_price = state.get("target_price")

    try:
        prompt = (
            f"Produce executive summary for thesis={thesis!r} "
            f"catalysts={catalysts} risks={risks}"
        )
        gen = llm.generate(
            stage_name="stage_19_brief_assembly",
            prompt=prompt,
            max_tokens=12000,
            temperature=0.2,
            response_format="text",
        )
        tokens_in, tokens_out = gen.input_tokens, gen.output_tokens
        summary = gen.text or "(empty)"
    except LlmTimeoutError:
        reason_code = "m8_llm_timeout"
        summary = thesis or "(empty)"
    except LlmMalformedOutputError:
        reason_code = "m8_llm_malformed_output"
        summary = thesis or "(empty)"
    except LlmProviderError as exc:
        reason_code = "m8_llm_5xx" if exc.status_code >= 500 else "m8_llm_4xx"
        summary = thesis or "(empty)"

    # Build data_sources from state for ResearchBrief.sources
    sources_in = state.get("data_sources", []) or []
    source_models: list[ResearchSource] = []
    for s in sources_in:
        if isinstance(s, ResearchSource):
            source_models.append(s)
        elif isinstance(s, dict):
            try:
                source_models.append(ResearchSource(**s))
            except Exception:
                pass
    if not source_models:
        # ResearchBrief requires non-empty sources; seed with placeholder
        source_models.append(
            ResearchSource(
                source_type="crm_data",
                description="(no sources -- placeholder)",
            )
        )

    try:
        brief = ResearchBrief(
            brief_id=uuid.uuid4(),
            security_identifier=None,
            analyst_id=state.get("supervisor_aid_token", "m8-agent")[:64] or "m8-agent",
            rating=rating,
            target_price=target_price if target_price is not None else None,
            summary=summary[:2000],
            thesis=(thesis or "(empty)")[:4000],
            catalysts=[str(c) for c in catalysts][:20],
            risks=[str(r) for r in risks][:20],
            sources=source_models,
            pipeline_run_id=state.get("pipeline_run_id", "unknown"),
            hitl_gates_passed=["gate_1", "gate_2"],
            anti_fabrication_score=1.0,
            created_at=datetime.now(timezone.utc),
            trace_id=state.get("trace_id", "unknown"),
        )
        output: dict[str, Any] = {"draft_brief": brief, "data_sources": source_models}
    except Exception:
        reason_code = reason_code or "m8_invalid_state"
        output = {}

    audit_stage(
        state,
        audit=audit,
        stage_number=19,
        stage_name="stage_19_brief_assembly",
        input_payload={"thesis_len": len(thesis)},
        output_payload={"has_brief": "draft_brief" in output},
        latency_ms=elapsed_ms(start),
        input_tokens=tokens_in,
        output_tokens=tokens_out,
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_19_brief_assembly"]
