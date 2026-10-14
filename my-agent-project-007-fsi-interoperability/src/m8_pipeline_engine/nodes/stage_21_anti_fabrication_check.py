"""M8 stage 21: Anti-fabrication check + HITL Gate 3.

1. Walks draft_brief text, extracts numeric tokens.
2. For each numeric token not present in any ResearchSource.description,
   appends to anti_fabrication_failures.
3. Emits HITL gate payload (via build_gate_payload). Actual interrupt()
   call happens in graph.py conditional edge.
"""

from __future__ import annotations

import re
from typing import Any

from m8_pipeline_engine.nodes._common import audit_stage, elapsed_ms, timed


_NUMERIC_RE = re.compile(r"[-+]?\b\d{1,3}(?:[,\.]\d+)*\b")


def stage_21_anti_fabrication_check(
    state: dict,
    *,
    gateway=None,
    resolver=None,
    audit=None,
    llm=None,
    config=None,
) -> dict:
    start = timed()
    draft = state.get("draft_brief")
    sources = state.get("data_sources", []) or []

    # Combine source corpus for numeric-token match
    corpus_parts: list[str] = []
    for src in sources:
        desc = getattr(src, "description", None) or (
            src.get("description", "") if isinstance(src, dict) else ""
        )
        corpus_parts.append(desc)
    corpus = " ".join(corpus_parts)

    draft_text = ""
    if draft is not None:
        # Pull common text fields
        for attr in ("summary", "thesis"):
            v = getattr(draft, attr, None)
            if v:
                draft_text += " " + str(v)
        # catalysts / risks are lists
        for attr in ("catalysts", "risks"):
            vs = getattr(draft, attr, None) or []
            draft_text += " " + " ".join(str(x) for x in vs)

    draft_numbers = set(_NUMERIC_RE.findall(draft_text))
    corpus_numbers = set(_NUMERIC_RE.findall(corpus))
    missing = sorted(draft_numbers - corpus_numbers)
    failures: list[dict[str, Any]] = [
        {"token": tok, "reason": "not_in_sources"} for tok in missing
    ]

    output: dict[str, Any] = {"anti_fabrication_failures": failures}
    reason_code = "m8_anti_fabrication_failed" if failures else None
    audit_stage(
        state,
        audit=audit,
        stage_number=21,
        stage_name="stage_21_anti_fabrication_check",
        input_payload={"draft_numbers": len(draft_numbers)},
        output_payload={"failure_count": len(failures)},
        latency_ms=elapsed_ms(start),
        reason_code=reason_code,
    )
    return output


__all__ = ["stage_21_anti_fabrication_check"]
