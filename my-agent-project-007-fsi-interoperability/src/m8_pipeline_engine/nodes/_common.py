"""Shared stage helpers (not exported)."""

from __future__ import annotations

import time
from typing import Any, Optional

from m8_pipeline_engine.audit_emit import emit_stage_audit


def audit_stage(
    state: dict,
    *,
    audit: Any,
    stage_number: int,
    stage_name: str,
    input_payload: Any,
    output_payload: Any,
    latency_ms: int,
    event_type: str = "m8.stage_completed",
    reason_code: Optional[str] = None,
    model_version: Optional[str] = None,
    prompt_template_version: Optional[str] = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    tool_name: Optional[str] = None,
    gateway_decision: Optional[str] = None,
    rule_applied: Optional[str] = None,
    wsp_section: Optional[str] = None,
) -> None:
    emit_stage_audit(
        audit,
        event_type=event_type,
        pipeline_run_id=state.get("pipeline_run_id", "unknown"),
        thread_id=state.get("thread_id", "unknown"),
        tenant_id=state.get("tenant_id", "unknown"),
        firm_id=state.get("firm_id", "unknown"),
        stage_number=stage_number,
        stage_name=stage_name,
        trace_id=state.get("trace_id", "unknown"),
        input_payload=input_payload,
        output_payload=output_payload,
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reason_code=reason_code,
        model_version=model_version,
        prompt_template_version=prompt_template_version,
        tool_name=tool_name,
        gateway_decision=gateway_decision,
        rule_applied=rule_applied,
        wsp_section=wsp_section,
    )


def timed() -> float:
    return time.perf_counter()


def elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


__all__ = ["audit_stage", "timed", "elapsed_ms"]
