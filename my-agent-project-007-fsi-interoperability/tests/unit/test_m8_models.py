"""Task 3 -- Pydantic v2 models: frozen + extra=forbid + validators."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from m8_pipeline_engine.models import (
    HitlApproval,
    HitlGatePayload,
    LlmGeneration,
    PipelineResult,
    PipelineTerminalAuditPayload,
    StageAuditPayload,
)


def _ts():
    return datetime.now(timezone.utc)


def test_pipeline_result_frozen():
    r = PipelineResult(
        status="completed",
        pipeline_run_id="run-1",
        thread_id="thread-1",
        final_stage=23,
        wall_clock_seconds=1.0,
        total_tokens=100,
    )
    with pytest.raises(ValidationError):
        r.status = "failed"  # type: ignore[misc]


def test_pipeline_result_reason_code_validated():
    with pytest.raises(ValidationError):
        PipelineResult(
            status="failed",
            pipeline_run_id="run-1",
            thread_id="thread-1",
            final_stage=0,
            wall_clock_seconds=0.0,
            total_tokens=0,
            reason_code="not_in_vocab",
        )


def test_pipeline_result_valid_reason_code_accepted():
    r = PipelineResult(
        status="failed",
        pipeline_run_id="run-1",
        thread_id="thread-1",
        final_stage=0,
        wall_clock_seconds=0.0,
        total_tokens=0,
        reason_code="m8_stage_failed",
    )
    assert r.reason_code == "m8_stage_failed"


def test_hitl_approval_token_pattern():
    HitlApproval(
        approver_aid_sub="user-1",
        approved=True,
        approval_token="a" * 64,
        approver_timestamp=_ts(),
    )
    with pytest.raises(ValidationError):
        HitlApproval(
            approver_aid_sub="user-1",
            approved=True,
            approval_token="short",
            approver_timestamp=_ts(),
        )


def test_hitl_gate_payload_gate_id_restricted():
    HitlGatePayload(
        gate_id=1,
        pipeline_run_id="run",
        thread_id="thread-x",
        stage_number=7,
        approver_role_required="research_specialist",
        summary={},
        emitted_at=_ts(),
    )
    with pytest.raises(ValidationError):
        HitlGatePayload(
            gate_id=4,  # type: ignore[arg-type]
            pipeline_run_id="run",
            thread_id="thread-x",
            stage_number=7,
            approver_role_required="r",
            summary={},
            emitted_at=_ts(),
        )


def test_stage_audit_payload_reason_code_validated():
    with pytest.raises(ValidationError):
        StageAuditPayload(
            event_type="m8.stage_completed",
            pipeline_run_id="run",
            thread_id="thread-x",
            tenant_id="t",
            firm_id="f",
            stage_number=1,
            stage_name="stage_1_intake",
            trace_id="tid",
            timestamp=_ts(),
            input_sha256="",
            output_sha256="",
            latency_ms=0,
            reason_code="nope",
        )


def test_llm_generation_extra_forbidden():
    with pytest.raises(ValidationError):
        LlmGeneration(
            text="t",
            input_tokens=1,
            output_tokens=1,
            latency_ms=1,
            model="m",
            provider="fake",
            stop_reason="end_turn",
            extra_field="bad",  # type: ignore[call-arg]
        )


def test_terminal_audit_reason_code_validated():
    PipelineTerminalAuditPayload(
        event_type="m8.pipeline_terminal",
        pipeline_run_id="run",
        thread_id="thread-x",
        tenant_id="t",
        firm_id="f",
        trace_id="tid",
        timestamp=_ts(),
        status="completed",
        final_stage=23,
        wall_clock_seconds=1.0,
    )
