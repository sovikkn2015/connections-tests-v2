"""Task 8 -- HITL primitives: token derivation, role, rotation, idempotent resume."""

from datetime import datetime, timedelta, timezone

import pytest

from m8_pipeline_engine.hitl import (
    build_approval_token,
    build_gate_payload,
    reap_timed_out_threads,
    verify_approval_token,
    _verify_approver_role,
)
from m8_pipeline_engine.models import HitlApproval
from m8_pipeline_engine.graph import _RESUME_CACHE, resume_from_gate


_KEY = b"fixture-key-not-secret-32-bytes!!"


def _approval(gate_id, thread_id, sub="user-1", key=_KEY, now=None):
    if now is None:
        now = datetime.now(timezone.utc)
    token = build_approval_token(
        key, gate_id=gate_id, approver_aid_sub=sub, approver_timestamp=now, thread_id=thread_id
    )
    return HitlApproval(
        approver_aid_sub=sub,
        approved=True,
        approval_token=token,
        approver_timestamp=now,
    )


def test_build_gate_payload_stage_mapping():
    p = build_gate_payload(gate_id=1, pipeline_run_id="run", thread_id="thread-x", summary={})
    assert p.stage_number == 7
    p = build_gate_payload(gate_id=2, pipeline_run_id="run", thread_id="thread-x", summary={})
    assert p.stage_number == 13
    p = build_gate_payload(gate_id=3, pipeline_run_id="run", thread_id="thread-x", summary={})
    assert p.stage_number == 21


def test_verify_approval_token_valid():
    a = _approval(1, "thread-xyz123")
    rc = verify_approval_token(a, gate_id=1, thread_id="thread-xyz123", hmac_key=_KEY)
    assert rc is None


def test_verify_approval_token_expired():
    old = datetime.now(timezone.utc) - timedelta(seconds=20000)
    a = _approval(1, "thread-xyz123", now=old)
    rc = verify_approval_token(a, gate_id=1, thread_id="thread-xyz123", hmac_key=_KEY, ttl_seconds=100)
    assert rc == "m8_hitl_token_expired"


def test_verify_approval_token_bad_key():
    a = _approval(1, "thread-xyz123")
    rc = verify_approval_token(a, gate_id=1, thread_id="thread-xyz123", hmac_key=b"other-key-------")
    assert rc == "m8_hitl_denied"


def test_verify_approval_token_empty_key_fails():
    a = _approval(1, "thread-xyz123")
    rc = verify_approval_token(a, gate_id=1, thread_id="thread-xyz123", hmac_key=b"")
    assert rc == "m8_hitl_token_expired"


def test_verify_approver_role_gate_1_accepts_research_specialist():
    class C:
        role = "research_specialist"
    assert _verify_approver_role(1, C()) is True


def test_verify_approver_role_gate_2_only_compliance():
    class C:
        role = "advisor"
    assert _verify_approver_role(2, C()) is False


def test_reap_timed_out_threads():
    old = datetime.now(timezone.utc) - timedelta(seconds=20000)
    fresh = datetime.now(timezone.utc)
    result = reap_timed_out_threads(
        {"old-thread": old, "fresh-thread": fresh}, ttl_seconds=100
    )
    assert result == ["old-thread"]


def test_key_rotation_cross_pod_boundary():
    """AC4.12 -- token signed under pod A's key fails on pod B's key."""
    key_a = b"pod-A-key------------------------"
    key_b = b"pod-B-key------------------------"
    # Build an approval timestamp close to now so TTL never trips
    now = datetime.now(timezone.utc)
    token = build_approval_token(
        key_a, gate_id=1, approver_aid_sub="u", approver_timestamp=now, thread_id="t-r12345678"
    )
    a = HitlApproval(
        approver_aid_sub="u",
        approved=True,
        approval_token=token,
        approver_timestamp=now,
    )
    rc = verify_approval_token(a, gate_id=1, thread_id="t-r12345678", hmac_key=key_b)
    assert rc == "m8_hitl_denied"


def test_resume_idempotency_cache():
    """AC18.8 -- same (thread_id, approval_token) returns cached result."""
    _RESUME_CACHE.clear()
    now = datetime.now(timezone.utc)
    token = "b" * 64  # any 64-hex token
    approval = HitlApproval(
        approver_aid_sub="u",
        approved=False,
        approval_token=token,
        approver_timestamp=now,
    )
    r1 = resume_from_gate("thread-idemp-12345", approval)
    r2 = resume_from_gate("thread-idemp-12345", approval)
    assert r1 is r2
