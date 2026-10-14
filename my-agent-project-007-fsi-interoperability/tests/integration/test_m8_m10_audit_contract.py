"""Task 19 -- SHARED-WITH-M10 /audit contract integration.

Known Blocker row 18: M10 v0.3.0 ships FastAPI ``POST /audit``.
With v0.3.0 landed, the xfail marker is removed and this suite
exercises the wire contract end-to-end against M10's TestClient-wrapped
app plus M8's ``M10AuditClient`` Protocol + ``FakeAuditClient`` impl.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from m10_audit_logger import InMemoryAuditBackend, InMemoryAuditDLQ
from m10_audit_logger.app import app as module_level_app
from m10_audit_logger.app import create_app
from m10_audit_logger.logger import AuditLogger


# =============================================================================
# Fixtures -- an M10 app wired to an observable in-memory triple
# =============================================================================


@pytest.fixture
def m10_triple():
    lf = InMemoryAuditBackend(tier="langfuse")
    worm = InMemoryAuditBackend(tier="worm")
    crm = InMemoryAuditBackend(tier="crm")
    return lf, worm, crm


@pytest.fixture
def m10_app(m10_triple):
    lf, worm, crm = m10_triple
    audit_logger = AuditLogger(
        langfuse=lf,
        worm=worm,
        crm=crm,
        dlq=InMemoryAuditDLQ(),
    )
    # B12: tests deliberately use InMemoryAuditBackend triples; opt in
    # via the dev flag so the fail-closed gate does not 503 us.
    new_app = create_app(audit_logger, allow_in_memory_audit=True)
    new_app.state.lf = lf
    new_app.state.worm = worm
    new_app.state.crm = crm
    return new_app


@pytest.fixture
def m10_client(m10_app):
    return TestClient(m10_app)


# =============================================================================
# M10 side -- the /audit route is exposed on the module-level app
# =============================================================================


def test_m10_exposes_audit_fastapi_route() -> None:
    """M10 v0.3.0 exposes POST /audit on its FastAPI app.

    Was xfail until v0.3.0 landed the FastAPI surface (SHARED-WITH-M10,
    Known Blocker row 18).
    """
    routes = [r.path for r in module_level_app.routes]
    assert "/audit" in routes


# =============================================================================
# M8 side -- Protocol shape + FakeAuditClient invariants
# =============================================================================


def test_m8_audit_client_protocol_roundtrips_stage_audit_payload() -> None:
    """FakeAuditClient accepts a StageAuditPayload dump without raising."""
    from m8_pipeline_engine.audit_client import AuditClient, FakeAuditClient
    from m8_pipeline_engine.models import StageAuditPayload

    fake: AuditClient = FakeAuditClient()
    payload = StageAuditPayload(
        event_type="m8.stage_completed",
        pipeline_run_id="run-1",
        thread_id="thread-abcdef12",
        tenant_id="t1",
        firm_id="f1",
        stage_number=1,
        stage_name="stage_1_intake",
        trace_id="trace-1",
        timestamp=datetime.now(timezone.utc),
        input_sha256="a" * 64,
        output_sha256="b" * 64,
        latency_ms=10,
    )
    fake.emit(payload.model_dump(mode="json"))
    assert len(fake.entries) == 1


def test_m8_audit_emit_error_raised_on_configured_failure() -> None:
    from m8_pipeline_engine.audit_client import AuditEmitError, FakeAuditClient

    fake = FakeAuditClient(fail_at=1)
    with pytest.raises(AuditEmitError):
        fake.emit({"event_type": "test"})


# =============================================================================
# End-to-end -- M8 payload shape round-trips cleanly through M10's /audit
# =============================================================================


def _m8_payload_dict() -> dict:
    """Build a StageAuditPayload via M8's model, dump to JSON-mode dict.

    This is the exact byte shape M8's ``M10AuditClient.emit`` would POST.
    """
    from m8_pipeline_engine.models import StageAuditPayload

    payload = StageAuditPayload(
        event_type="m8.stage_completed",
        pipeline_run_id="run-integration-7f3c9a1e",
        thread_id="thread-integration-8a3d0022",
        tenant_id="firm-integration-12345",
        firm_id="firm-integration-12345",
        stage_number=12,
        stage_name="stage_12_cross_source_synthesis",
        trace_id="supv-integration-7f3c9a1e",
        timestamp=datetime(
            2026, 5, 20, 14, 21, 47, 312000, tzinfo=timezone.utc
        ),
        input_sha256="c" * 64,
        output_sha256="d" * 64,
        latency_ms=8425,
    )
    return payload.model_dump(mode="json")


class TestEndToEndWireShape:

    def test_m8_wire_shape_accepted_by_m10(self, m10_client):
        """M8's dumped StageAuditPayload dict -> M10 POST /audit -> 202."""
        resp = m10_client.post("/audit", json=_m8_payload_dict())
        assert resp.status_code == 202
        body = resp.json()
        assert body["status"] == "queued"
        assert len(body["audit_id"]) == 36  # UUID v4 string

    def test_m8_wire_shape_fans_out_to_three_m10_tiers(
        self, m10_client, m10_app
    ):
        m10_client.post("/audit", json=_m8_payload_dict())
        assert len(m10_app.state.lf.entries) == 1
        assert len(m10_app.state.worm.entries) == 1
        assert len(m10_app.state.crm.entries) == 1

    def test_m8_event_type_preserved_in_m10_entry_action(
        self, m10_client, m10_app
    ):
        m10_client.post("/audit", json=_m8_payload_dict())
        sealed = m10_app.state.worm.entries[0]
        assert sealed.action == "m8.stage_completed"

    def test_m8_trace_id_preserved_in_m10_entry(self, m10_client, m10_app):
        m10_client.post("/audit", json=_m8_payload_dict())
        sealed = m10_app.state.worm.entries[0]
        assert sealed.trace_id == "supv-integration-7f3c9a1e"

    def test_m10_applies_six_year_retention_floor(
        self, m10_client, m10_app
    ):
        """SEC 17a-4 / Rule 4 -- every entry written via /audit must
        carry >=6 years retention regardless of caller intent."""
        m10_client.post("/audit", json=_m8_payload_dict())
        sealed = m10_app.state.worm.entries[0]
        assert sealed.retention_years is not None
        assert sealed.retention_years >= 6

    def test_m10_computes_integrity_hash_on_every_entry(
        self, m10_client, m10_app
    ):
        """SHA-256 integrity hash on every audit write (Rule 3)."""
        import re

        m10_client.post("/audit", json=_m8_payload_dict())
        sealed = m10_app.state.worm.entries[0]
        assert re.fullmatch(r"[0-9a-f]{64}", sealed.sha256_integrity)


# =============================================================================
# M10AuditClient contract -- the serialised body shape survives a
# urllib.request.Request.data round-trip (what M10AuditClient actually sends).
# =============================================================================


class TestM10AuditClientBodyShape:

    def test_body_is_json_serialisable_utf8(self):
        """M8's M10AuditClient does ``json.dumps(entry).encode("utf-8")``
        and POSTs that. Verify the StageAuditPayload dump survives
        that exact pipeline."""
        body = _m8_payload_dict()
        encoded = json.dumps(body).encode("utf-8")
        decoded = json.loads(encoded.decode("utf-8"))
        assert decoded == body

    def test_m10_accepts_m8_m10auditclient_encoded_body(self, m10_client):
        """Same bytes that M8's M10AuditClient produces -> M10 accepts."""
        body = _m8_payload_dict()
        encoded = json.dumps(body).encode("utf-8")
        resp = m10_client.post(
            "/audit",
            content=encoded,
            headers={"content-type": "application/json"},
        )
        assert resp.status_code == 202
