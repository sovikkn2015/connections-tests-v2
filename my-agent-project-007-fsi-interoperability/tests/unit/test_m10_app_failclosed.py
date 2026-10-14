"""B12 -- M10 fail-closed on unwired (all-in-memory) audit backends.

Covers the four-cell matrix:

    flag=False × unwired (all InMemory)  -> 503 backends_not_wired on /audit + /health
    flag=False × wired (>=1 real)        -> 202 / 200
    flag=True  × unwired                 -> 202 / 200 (dev opt-in)
    flag=True  × wired                   -> 202 / 200

+ startup stdout diagnostic line + backends_by_tier invariant.

M10 default ships with InMemoryAuditBackend on all three tiers. Without
this gate, a stock container silently accepts audits that die on pod
restart (Rule 4 SEC 17a-4 violation). The fail-closed default is
intentional: operators must explicitly pass
``allow_in_memory_audit=True`` to ``create_app(...)`` for dev / CI
(which the Dockerfile bootstrap does from ``M10_ALLOW_IN_MEMORY_AUDIT``
env, NOT the M10 source code -- see
``deploy/docker/m10-audit-logger/app/main.py``).

M10 source code contains NO env reads (security invariant --
see ``test_no_os_environ_in_src`` in ``test_m10_audit_logger.py``).
"""

from __future__ import annotations

import io
import uuid
from datetime import datetime, timezone
from typing import Any
from unittest import mock

import pytest
from fastapi.testclient import TestClient

from m10_audit_logger.app import (
    _all_backends_in_memory,
    create_app,
)
from m10_audit_logger.backends import (
    InMemoryAuditBackend,
    InMemoryAuditDLQ,
)
from m10_audit_logger.logger import AuditLogger


# ---------------------------------------------------------------------------
# Fixtures + fakes
# ---------------------------------------------------------------------------


class _RealisticBackend:
    """Stand-in for a real backend (e.g. Langfuse client, MinIO S3, CRM).

    Not an ``InMemoryAuditBackend``, so the fail-closed gate treats it
    as "wired." Implements the backend Protocol surface -- only what
    the logger calls.
    """

    def __init__(self, tier: str) -> None:
        self.tier = tier
        self.records: list = []

    def write(self, entry: Any) -> None:
        self.records.append(entry)

    def query_by_trace_id(self, trace_id: str) -> list:
        return []

    def health(self) -> dict:
        return {"tier": self.tier, "status": "ok"}


def _unwired_logger() -> AuditLogger:
    """Three tiers, all InMemoryAuditBackend. Matches _default_logger."""
    return AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=InMemoryAuditBackend(tier="worm"),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )


def _half_wired_logger() -> AuditLogger:
    """WORM is a realistic backend; others in-memory. Gate should allow."""
    return AuditLogger(
        langfuse=InMemoryAuditBackend(tier="langfuse"),
        worm=_RealisticBackend(tier="worm"),
        crm=InMemoryAuditBackend(tier="crm"),
        dlq=InMemoryAuditDLQ(),
    )


def _valid_wire_body() -> dict:
    """M8 StageAuditPayload wire shape -- includes tenant_id (M3-FIX)."""
    return {
        "source": "m8",
        "event_type": "stage_start",
        "pipeline_run_id": "run-0001",
        "thread_id": "thread-001",
        "tenant_id": "tenant-01",
        "firm_id": "firm-01",
        "stage_number": 1,
        "stage_name": "bootstrap",
        "trace_id": "trace-aaaa",
        "timestamp": datetime.now(timezone.utc).isoformat().replace(
            "+00:00", "Z"
        ),
        "input_sha256": "a" * 64,
        "output_sha256": "b" * 64,
        "latency_ms": 3,
        "reason_code": None,
    }


# ---------------------------------------------------------------------------
# backends_by_tier + _all_backends_in_memory
# ---------------------------------------------------------------------------


def test_backends_by_tier_returns_three_tier_keys() -> None:
    logger = _unwired_logger()
    tiers = logger.backends_by_tier()
    assert set(tiers.keys()) == {"langfuse", "worm", "crm"}


def test_all_backends_in_memory_true_when_unwired() -> None:
    logger = _unwired_logger()
    assert _all_backends_in_memory(logger) is True


def test_all_backends_in_memory_false_when_half_wired() -> None:
    logger = _half_wired_logger()
    assert _all_backends_in_memory(logger) is False


# ---------------------------------------------------------------------------
# /health -- 2x2 matrix
# ---------------------------------------------------------------------------


def test_health_503_when_unwired_and_flag_false() -> None:
    app = create_app(audit_logger=_unwired_logger(), allow_in_memory_audit=False)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "not_ready"
    assert body["reason"] == "backends_not_wired"
    assert body["allow_in_memory_audit"] is False


def test_health_200_when_unwired_and_flag_true() -> None:
    app = create_app(audit_logger=_unwired_logger(), allow_in_memory_audit=True)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["allow_in_memory_audit"] is True


def test_health_200_when_at_least_one_real_backend() -> None:
    """Real backend wired -> gate allows regardless of flag."""
    app = create_app(audit_logger=_half_wired_logger(), allow_in_memory_audit=False)
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


# ---------------------------------------------------------------------------
# /audit POST -- 2x2 matrix
# ---------------------------------------------------------------------------


def test_audit_post_503_when_unwired_and_flag_false() -> None:
    app = create_app(audit_logger=_unwired_logger(), allow_in_memory_audit=False)
    with TestClient(app) as client:
        resp = client.post("/audit", json=_valid_wire_body())
    assert resp.status_code == 503
    assert resp.json() == {"error": "backends_not_wired"}


def test_audit_post_202_when_flag_true_even_if_all_in_memory() -> None:
    app = create_app(audit_logger=_unwired_logger(), allow_in_memory_audit=True)
    with TestClient(app) as client:
        resp = client.post("/audit", json=_valid_wire_body())
    assert resp.status_code == 202
    body = resp.json()
    assert body["status"] == "queued"
    uuid.UUID(body["audit_id"])  # valid uuid


def test_audit_post_202_when_real_backend_wired() -> None:
    app = create_app(audit_logger=_half_wired_logger(), allow_in_memory_audit=False)
    with TestClient(app) as client:
        resp = client.post("/audit", json=_valid_wire_body())
    assert resp.status_code == 202
    assert resp.json()["status"] == "queued"


# ---------------------------------------------------------------------------
# create_app default (no flag) is fail-closed
# ---------------------------------------------------------------------------


def test_create_app_default_is_fail_closed() -> None:
    """The absolute default (no kwargs) is fail-closed on in-memory backends."""
    app = create_app()  # no audit_logger, no flag -> unwired default + flag=False
    with TestClient(app) as client:
        resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "backends_not_wired"


# ---------------------------------------------------------------------------
# Startup diagnostic line
# ---------------------------------------------------------------------------


def test_startup_emits_stdout_posture_unwired() -> None:
    captured = io.StringIO()
    with mock.patch("m10_audit_logger.app.sys.stdout", new=captured):
        create_app(audit_logger=_unwired_logger(), allow_in_memory_audit=False)
    output = captured.getvalue()
    assert "\"phase\":\"startup\"" in output
    assert "\"module\":\"m10\"" in output
    assert "\"all_backends_in_memory\":true" in output
    assert "\"allow_in_memory_audit\":false" in output
    assert "\"backends_wired\":false" in output


def test_startup_emits_backends_wired_true_when_real() -> None:
    captured = io.StringIO()
    with mock.patch("m10_audit_logger.app.sys.stdout", new=captured):
        create_app(audit_logger=_half_wired_logger(), allow_in_memory_audit=False)
    output = captured.getvalue()
    assert "\"all_backends_in_memory\":false" in output
    assert "\"backends_wired\":true" in output


def test_startup_emits_backends_wired_true_when_flag_true() -> None:
    captured = io.StringIO()
    with mock.patch("m10_audit_logger.app.sys.stdout", new=captured):
        create_app(audit_logger=_unwired_logger(), allow_in_memory_audit=True)
    output = captured.getvalue()
    assert "\"all_backends_in_memory\":true" in output
    assert "\"allow_in_memory_audit\":true" in output
    assert "\"backends_wired\":true" in output


# ---------------------------------------------------------------------------
# Module-level app still boots (for Dockerfile smoke test)
# ---------------------------------------------------------------------------


def test_module_level_app_importable() -> None:
    """``from m10_audit_logger.app import app`` must not raise."""
    from m10_audit_logger import app as app_mod
    assert app_mod.app is not None
    # Default posture: unwired + flag=False -> 503. That IS the point.
    with TestClient(app_mod.app) as client:
        resp = client.get("/health")
    assert resp.status_code == 503
    assert resp.json()["reason"] == "backends_not_wired"
