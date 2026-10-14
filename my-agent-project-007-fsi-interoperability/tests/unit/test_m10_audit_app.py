"""
M10 Audit Logger -- FastAPI app unit tests.

Covers v0.3.0 POST /audit + GET /health surface landed for the
SHARED-WITH-M10 blocker (row 18) in M8 v0.2.0's spec.

Contract under test:
* 202 + {"status":"queued","audit_id":...} on success.
* 400 on malformed body / missing required keys / bad payload shape.
* 503 on AuditWriteError from any of the 3 backend tiers.
* GET /health returns 200 with backend metadata.
* Middleware never emits raw payload body; a stdout canary scan rejects
  MNPI-shaped tokens (SSN / bank-routing / phone) on the access log.

Run:

    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest my-agent-project-007-fsi-interoperability/tests/unit/test_m10_audit_app.py -v
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from m10_audit_logger import InMemoryAuditBackend, InMemoryAuditDLQ
from m10_audit_logger.app import app as module_level_app
from m10_audit_logger.app import create_app
from m10_audit_logger.logger import AuditLogger


# =============================================================================
# Fixtures
# =============================================================================


def _well_formed_body(**overrides) -> dict:
    """An M8 StageAuditPayload-shaped dict with every required key set."""
    body = {
        "source": "m8",
        "event_type": "m8.stage_completed",
        "pipeline_run_id": "run-7f3c9a1e",
        "thread_id": "thread-8a3d0022",
        "tenant_id": "firm-abc-12345",
        "firm_id": "firm-abc-12345",
        "stage_number": 12,
        "stage_name": "stage_12_cross_source_synthesis",
        "trace_id": "supv-2026-05-20-7f3c9a1e",
        "timestamp": "2026-05-20T14:21:47.312Z",
        "input_sha256": "c" * 64,
        "output_sha256": "d" * 64,
        "latency_ms": 8425,
        "reason_code": None,
    }
    body.update(overrides)
    return body


def _healthy_triple():
    return (
        InMemoryAuditBackend(tier="langfuse"),
        InMemoryAuditBackend(tier="worm"),
        InMemoryAuditBackend(tier="crm"),
    )


@pytest.fixture
def healthy_app():
    """A fresh app wired to a healthy 3-tier triple. Exposes backends."""
    lf, worm, crm = _healthy_triple()
    dlq = InMemoryAuditDLQ()
    logger = AuditLogger(langfuse=lf, worm=worm, crm=crm, dlq=dlq)
    app = create_app(logger, allow_in_memory_audit=True)
    app.state.lf = lf
    app.state.worm = worm
    app.state.crm = crm
    app.state.dlq = dlq
    return app


@pytest.fixture
def client(healthy_app):
    return TestClient(healthy_app)


# =============================================================================
# Happy path -- POST /audit 202
# =============================================================================


class TestPostAuditHappyPath:

    def test_valid_body_returns_202_queued(self, client):
        resp = client.post("/audit", json=_well_formed_body())
        assert resp.status_code == 202
        payload = resp.json()
        assert payload["status"] == "queued"
        assert re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12}",
            payload["audit_id"],
        )

    def test_valid_body_fans_out_to_three_tiers(self, client, healthy_app):
        client.post("/audit", json=_well_formed_body())
        assert len(healthy_app.state.lf.entries) == 1
        assert len(healthy_app.state.worm.entries) == 1
        assert len(healthy_app.state.crm.entries) == 1

    def test_sealed_entry_has_integrity_hash(self, client, healthy_app):
        client.post("/audit", json=_well_formed_body())
        sealed = healthy_app.state.worm.entries[0]
        assert re.fullmatch(r"[0-9a-f]{64}", sealed.sha256_integrity)

    def test_retention_defaults_to_six_years(self, client, healthy_app):
        client.post("/audit", json=_well_formed_body())
        sealed = healthy_app.state.worm.entries[0]
        assert sealed.retention_years == 6

    def test_action_carries_event_type(self, client, healthy_app):
        client.post(
            "/audit",
            json=_well_formed_body(event_type="m8.stage_failed"),
        )
        sealed = healthy_app.state.worm.entries[0]
        assert sealed.action == "m8.stage_failed"

    def test_iso_timestamp_without_z_suffix_accepted(
        self, client, healthy_app
    ):
        client.post(
            "/audit",
            json=_well_formed_body(timestamp="2026-05-20T14:21:47.312+00:00"),
        )
        sealed = healthy_app.state.worm.entries[0]
        assert sealed.timestamp == datetime(
            2026, 5, 20, 14, 21, 47, 312000, tzinfo=timezone.utc
        )


# =============================================================================
# 400 paths -- malformed body
# =============================================================================


class TestPostAuditBadRequest:

    def test_not_json_returns_400(self, client):
        resp = client.post(
            "/audit",
            content=b"not valid json{{",
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_json"

    def test_body_is_list_returns_400(self, client):
        resp = client.post("/audit", json=[1, 2, 3])
        assert resp.status_code == 400
        assert resp.json()["error"] == "body_must_be_object"

    def test_missing_single_required_key_returns_400(self, client):
        body = _well_formed_body()
        del body["trace_id"]
        resp = client.post("/audit", json=body)
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["error"] == "missing_required_keys"
        assert payload["missing"] == ["trace_id"]

    def test_missing_multiple_required_keys_returns_400(self, client):
        body = _well_formed_body()
        del body["firm_id"]
        del body["stage_number"]
        resp = client.post("/audit", json=body)
        assert resp.status_code == 400
        assert resp.json()["missing"] == ["firm_id", "stage_number"]

    def test_invalid_timestamp_returns_400(self, client):
        resp = client.post(
            "/audit",
            json=_well_formed_body(timestamp="not-a-date"),
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_payload_shape"

    def test_invalid_sha256_returns_400(self, client):
        resp = client.post(
            "/audit",
            json=_well_formed_body(input_sha256="too-short"),
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "invalid_payload_shape"

    def test_400_body_does_not_echo_original_payload(self, client):
        """MNPI-safety: 400 response must not mirror caller-supplied
        body fragments (could carry PII)."""
        resp = client.post(
            "/audit",
            json=_well_formed_body(
                trace_id="supv-123-with-ssn-123-45-6789",
                input_sha256="too-short",
            ),
        )
        assert resp.status_code == 400
        text = resp.text
        assert "123-45-6789" not in text
        assert "supv-123-with-ssn" not in text

    def test_400_does_not_write_to_any_tier(self, client, healthy_app):
        body = _well_formed_body()
        del body["firm_id"]
        client.post("/audit", json=body)
        assert healthy_app.state.lf.entries == []
        assert healthy_app.state.worm.entries == []
        assert healthy_app.state.crm.entries == []


# =============================================================================
# 503 -- backend failure
# =============================================================================


class TestPostAuditBackendFailure:

    def test_langfuse_failure_returns_503(self):
        logger = AuditLogger(
            langfuse=InMemoryAuditBackend(
                tier="langfuse", fail_on_nth=1
            ),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm"),
        )
        client = TestClient(create_app(logger, allow_in_memory_audit=True))
        resp = client.post("/audit", json=_well_formed_body())
        assert resp.status_code == 503
        payload = resp.json()
        assert payload["error"] == "backend_unavailable"
        assert payload["reason"] == "langfuse_write_failed"

    def test_worm_failure_returns_503(self):
        logger = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=InMemoryAuditBackend(tier="worm", fail_on_nth=1),
            crm=InMemoryAuditBackend(tier="crm"),
        )
        client = TestClient(create_app(logger, allow_in_memory_audit=True))
        resp = client.post("/audit", json=_well_formed_body())
        assert resp.status_code == 503
        assert resp.json()["reason"] == "worm_write_failed"

    def test_crm_failure_returns_503(self):
        logger = AuditLogger(
            langfuse=InMemoryAuditBackend(tier="langfuse"),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm", fail_on_nth=1),
        )
        client = TestClient(create_app(logger, allow_in_memory_audit=True))
        resp = client.post("/audit", json=_well_formed_body())
        assert resp.status_code == 503
        assert resp.json()["reason"] == "crm_write_failed"


# =============================================================================
# GET /health
# =============================================================================


class TestHealth:

    def test_health_returns_200_with_backend_metadata(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        payload = resp.json()
        assert payload["status"] == "ok"
        assert payload["version"] == "0.3.0"
        backends = payload["backends"]
        assert backends["status"] == "ok"
        assert backends["tiers"] == ["langfuse", "worm", "crm"]
        assert backends["min_retention_years"] == 6

    def test_health_reflects_dlq_depth_after_failure(self):
        logger = AuditLogger(
            langfuse=InMemoryAuditBackend(
                tier="langfuse", fail_on_nth=1
            ),
            worm=InMemoryAuditBackend(tier="worm"),
            crm=InMemoryAuditBackend(tier="crm"),
            dlq=InMemoryAuditDLQ(),
        )
        client = TestClient(create_app(logger, allow_in_memory_audit=True))
        client.post("/audit", json=_well_formed_body())
        h = client.get("/health").json()
        assert h["backends"]["dlq_depth"] == 1


# =============================================================================
# Middleware redaction (canary scan on captured stdout)
# =============================================================================


_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_BANK_ROUTING = re.compile(r"\b\d{9}\b")           # ABA routing numbers
_PHONE = re.compile(r"\b\d{3}-\d{3}-\d{4}\b")


class TestMiddlewareRedaction:

    def test_stdout_does_not_contain_raw_body(
        self, capfd, client, healthy_app
    ):
        body = _well_formed_body(
            # Inject MNPI-shaped canaries into the body; middleware
            # must NEVER echo these to stdout.
            pipeline_run_id="run-ssn-123-45-6789",
            thread_id="thread-phone-555-123-4567",
            tenant_id="firm-routing-021000021",
        )
        resp = client.post("/audit", json=body)
        assert resp.status_code == 202

        captured = capfd.readouterr().out
        # Structural sanity: middleware emitted at least entry+exit lines.
        assert "request_start" in captured
        assert "request_end" in captured
        # Redaction check: no MNPI-shaped tokens in the access log.
        assert not _SSN.search(captured), "SSN leaked to stdout"
        assert not _PHONE.search(captured), "phone leaked to stdout"
        assert not _BANK_ROUTING.search(captured), (
            "bank routing leaked to stdout"
        )
        # And the redacted body values themselves must not appear.
        assert "123-45-6789" not in captured
        assert "555-123-4567" not in captured
        assert "021000021" not in captured

    def test_stdout_surfaces_only_allowed_fields(
        self, capfd, client
    ):
        client.post(
            "/audit",
            json=_well_formed_body(),
            headers={
                "x-trace-id": "trace-visible",
                "x-event-type": "m8.stage_completed",
                "x-pipeline-run-id": "run-visible",
            },
        )
        captured = capfd.readouterr().out
        # Header-derived fields are the ONLY trace metadata allowed.
        assert "trace-visible" in captured
        assert "run-visible" in captured
        assert "m8.stage_completed" in captured
        # Body values must never surface -- pick a body-only string.
        assert "supv-2026-05-20-7f3c9a1e" not in captured


# =============================================================================
# Module-level default app -- imported directly by the M8 integration test
# =============================================================================


class TestModuleLevelApp:

    def test_module_level_app_exposes_audit_route(self):
        routes = [r.path for r in module_level_app.routes]
        assert "/audit" in routes
        assert "/health" in routes

    def test_module_level_app_health_is_reachable(self):
        """B12: module-level default app is fail-closed (in-memory x 3).

        Pre-B12 this returned 200. Post-B12 the stock container fails
        closed by default; operators must inject a real backend or
        opt into in-memory via the deploy-level bootstrap (which sets
        ``allow_in_memory_audit=True`` from the env var
        ``M10_ALLOW_IN_MEMORY_AUDIT``).
        """
        resp = TestClient(module_level_app).get("/health")
        assert resp.status_code == 503
        assert resp.json()["reason"] == "backends_not_wired"
