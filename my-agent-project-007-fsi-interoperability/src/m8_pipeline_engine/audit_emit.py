"""
M8 Pipeline Engine -- Per-stage audit emission helpers.

R8: every stage emits exactly one audit row. Audit goes through AuditClient
(v0.2.0, Required Fix 4).

``print(`` is only allowed here per AC13.5 as a digest-only fallback when
AuditClient itself raises AuditEmitError -- raw payloads NEVER printed.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from m8_pipeline_engine.audit_client import AuditClient, AuditEmitError
from m8_pipeline_engine.models import (
    PipelineTerminalAuditPayload,
    StageAuditPayload,
)


def canonical_json(value: Any) -> str:
    """Stable JSON serialization for digest calculation."""

    def _default(obj: Any) -> Any:
        if hasattr(obj, "model_dump"):
            return obj.model_dump(mode="json")
        if isinstance(obj, datetime):
            return obj.isoformat()
        return repr(obj)

    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), default=_default
    )


def compute_io_digest(value: Any) -> str:
    """SHA-256 hex digest of canonical_json(value). Empty -> '' (R8 Gap 2)."""
    if value is None:
        return ""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def emit_stage_audit(
    audit: AuditClient,
    *,
    event_type: str,
    pipeline_run_id: str,
    thread_id: str,
    tenant_id: str,
    firm_id: str,
    stage_number: int,
    stage_name: str,
    trace_id: str,
    input_payload: Any,
    output_payload: Any,
    latency_ms: int,
    input_tokens: int = 0,
    output_tokens: int = 0,
    reason_code: Optional[str] = None,
    model_version: Optional[str] = None,
    prompt_template_version: Optional[str] = None,
    tool_name: Optional[str] = None,
    gateway_decision: Optional[str] = None,
    rule_applied: Optional[str] = None,
    wsp_section: Optional[str] = None,
    timestamp: Optional[datetime] = None,
) -> StageAuditPayload:
    """Build + emit a StageAuditPayload via AuditClient."""
    payload = StageAuditPayload(
        event_type=event_type,
        pipeline_run_id=pipeline_run_id,
        thread_id=thread_id,
        tenant_id=tenant_id,
        firm_id=firm_id,
        stage_number=stage_number,
        stage_name=stage_name,
        trace_id=trace_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        model_version=model_version,
        prompt_template_version=prompt_template_version,
        input_sha256=compute_io_digest(input_payload),
        output_sha256=compute_io_digest(output_payload),
        latency_ms=latency_ms,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        reason_code=reason_code,
        tool_name=tool_name,
        gateway_decision=gateway_decision,
        rule_applied=rule_applied,
        wsp_section=wsp_section,
    )
    try:
        audit.emit(payload.model_dump(mode="json"))
    except AuditEmitError:
        # Digest-only fallback per AC13.5. Raw payload NEVER printed.
        _fallback = {
            "source": "m8",
            "event_type": event_type,
            "stage_number": stage_number,
            "input_sha256": payload.input_sha256,
            "output_sha256": payload.output_sha256,
            "reason_code": reason_code,
        }
        print(json.dumps(_fallback, sort_keys=True))
    return payload


def emit_terminal_audit(
    audit: AuditClient,
    *,
    event_type: str,
    pipeline_run_id: str,
    thread_id: str,
    tenant_id: str,
    firm_id: str,
    trace_id: str,
    status: str,
    final_stage: int,
    wall_clock_seconds: float,
    total_input_tokens: int = 0,
    total_output_tokens: int = 0,
    reason_code: Optional[str] = None,
    dropped_instruments: Optional[list[str]] = None,
    timestamp: Optional[datetime] = None,
) -> PipelineTerminalAuditPayload:
    """Build + emit a PipelineTerminalAuditPayload (AC8.8)."""
    payload = PipelineTerminalAuditPayload(
        event_type=event_type,
        pipeline_run_id=pipeline_run_id,
        thread_id=thread_id,
        tenant_id=tenant_id,
        firm_id=firm_id,
        trace_id=trace_id,
        timestamp=timestamp or datetime.now(timezone.utc),
        status=status,  # type: ignore[arg-type]
        final_stage=final_stage,
        wall_clock_seconds=wall_clock_seconds,
        total_input_tokens=total_input_tokens,
        total_output_tokens=total_output_tokens,
        reason_code=reason_code,
        dropped_instruments=list(dropped_instruments or []),
    )
    try:
        audit.emit(payload.model_dump(mode="json"))
    except AuditEmitError:
        _fallback = {
            "source": "m8",
            "event_type": event_type,
            "status": status,
            "reason_code": reason_code,
        }
        print(json.dumps(_fallback, sort_keys=True))
    return payload


__all__ = [
    "emit_stage_audit",
    "emit_terminal_audit",
    "compute_io_digest",
    "canonical_json",
    "PipelineTerminalAuditPayload",
]
