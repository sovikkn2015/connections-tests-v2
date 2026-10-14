"""Task 10 -- audit_emit helpers: schema round-trip, digest scan, failure retry."""

import json
from datetime import datetime, timezone

import pytest

from m8_pipeline_engine.audit_client import AuditEmitError, FakeAuditClient
from m8_pipeline_engine.audit_emit import (
    canonical_json,
    compute_io_digest,
    emit_stage_audit,
    emit_terminal_audit,
)


def test_canonical_json_sorted_keys():
    a = canonical_json({"b": 2, "a": 1})
    assert a == '{"a":1,"b":2}'


def test_compute_io_digest_stable():
    d1 = compute_io_digest({"b": 2, "a": 1})
    d2 = compute_io_digest({"a": 1, "b": 2})
    assert d1 == d2
    assert len(d1) == 64


def test_compute_io_digest_none_is_empty():
    assert compute_io_digest(None) == ""


def test_emit_stage_audit_records_into_fake():
    c = FakeAuditClient()
    emit_stage_audit(
        c,
        event_type="m8.stage_completed",
        pipeline_run_id="run",
        thread_id="thread-x",
        tenant_id="t",
        firm_id="f",
        stage_number=1,
        stage_name="stage_1_intake",
        trace_id="tid",
        input_payload={"k": 1},
        output_payload={"k": 2},
        latency_ms=5,
    )
    assert len(c.entries) == 1
    assert c.entries[0]["stage_number"] == 1
    # digest is 64 hex
    assert len(c.entries[0]["input_sha256"]) == 64


def test_emit_stage_audit_failure_prints_digest_only(capsys):
    """AC13.5 -- digest-only fallback when AuditClient raises."""
    c = FakeAuditClient(fail_at=1)
    emit_stage_audit(
        c,
        event_type="m8.stage_completed",
        pipeline_run_id="run",
        thread_id="thread-x",
        tenant_id="t",
        firm_id="f",
        stage_number=1,
        stage_name="stage_1_intake",
        trace_id="tid",
        input_payload={"secret_payload": "x"},
        output_payload=None,
        latency_ms=1,
    )
    out = capsys.readouterr().out
    # Canary: raw payload must NOT appear in fallback print
    assert "secret_payload" not in out
    # Digest MUST appear
    parsed = json.loads(out.strip())
    assert "input_sha256" in parsed


def test_emit_terminal_audit_shape():
    c = FakeAuditClient()
    emit_terminal_audit(
        c,
        event_type="m8.pipeline_terminal",
        pipeline_run_id="run",
        thread_id="thread-x",
        tenant_id="t",
        firm_id="f",
        trace_id="tid",
        status="completed",
        final_stage=23,
        wall_clock_seconds=1.0,
    )
    assert c.entries[0]["status"] == "completed"
