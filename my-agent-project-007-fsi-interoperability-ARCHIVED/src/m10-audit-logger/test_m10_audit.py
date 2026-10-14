"""
M10 Audit Logger — Integration Tests

Covers:
  1. Write audit entry successfully (all 3 tiers)
  2. Fail-closed when WORM tier fails
  3. SHA-256 integrity hash is correct
  4. Provenance chain is preserved
  5. DLQ receives failed entries
  6. Query by trace_id returns the entry
  7. FastAPI endpoint integration
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio

# Ensure package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from m10_audit_logger.audit_service import AuditService, AuditWriteError
from m10_audit_logger.models import (
    AuditDecision,
    AuditEntry,
    AuditModule,
    ProvenanceStage,
    TierWriteResult,
    WriteAuditRequest,
)
from m10_audit_logger.writers import CrmWriter, LangfuseWriter, WormWriter


# ── Fixtures ─────────────────────────────────────────────────────


def _make_request(**overrides: Any) -> WriteAuditRequest:
    """Build a valid WriteAuditRequest with sensible defaults."""
    defaults = {
        "trace_id": "trace-test-001",
        "actor_id": "sha256:actor123",
        "action": "client_record_accessed",
        "module": AuditModule.m6,
        "decision": AuditDecision.allow,
        "input_hash": "a" * 64,
        "output_hash": "b" * 64,
        "firm_id": "acme_wm",
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "jurisdiction": "US",
        "data_sources_used": ["salesforce_fsc"],
        "latency_ms": 42,
    }
    defaults.update(overrides)
    return WriteAuditRequest(**defaults)


@pytest.fixture
def service() -> AuditService:
    """AuditService with in-memory writers (no external deps)."""
    return AuditService(
        langfuse_writer=LangfuseWriter(),
        worm_writer=WormWriter(),
        crm_writer=CrmWriter(),
    )


# ── Test 1: Successful 3-tier write ─────────────────────────────


@pytest.mark.asyncio
async def test_write_audit_all_tiers_succeed(service: AuditService) -> None:
    """All 3 tiers write successfully. Response includes all tier results."""
    request = _make_request()
    response = await service.write_audit(request)

    assert response.canonical_id  # UUID generated
    assert response.sha256_integrity  # SHA-256 computed
    assert len(response.sha256_integrity) == 64  # valid hex
    assert response.worm_record_id.startswith("s3://007-worm-audit/")
    assert len(response.tier_results) == 3

    # All tiers succeeded
    for result in response.tier_results:
        assert result.success is True
        assert result.record_id is not None
        assert result.error is None

    # Tier names present
    tier_names = {r.tier for r in response.tier_results}
    assert tier_names == {"worm", "langfuse", "crm"}


# ── Test 2: Fail-closed when WORM tier fails ────────────────────


@pytest.mark.asyncio
async def test_fail_closed_worm_failure() -> None:
    """If WORM tier fails, entire request fails (fail-closed, Rule 2)."""

    class FailingWormWriter(WormWriter):
        async def write(self, entry: AuditEntry) -> TierWriteResult:
            return TierWriteResult(
                tier="worm", success=False, error="S3 connection refused",
            )

    service = AuditService(
        langfuse_writer=LangfuseWriter(),
        worm_writer=FailingWormWriter(),
        crm_writer=CrmWriter(),
    )

    request = _make_request()
    with pytest.raises(AuditWriteError) as exc_info:
        await service.write_audit(request)

    assert "worm" in str(exc_info.value).lower()
    assert "fail-closed" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_fail_closed_langfuse_failure() -> None:
    """If Langfuse tier fails, entire request fails (fail-closed)."""

    class FailingLangfuseWriter(LangfuseWriter):
        async def write(self, entry: AuditEntry) -> TierWriteResult:
            return TierWriteResult(
                tier="langfuse", success=False, error="Langfuse unreachable",
            )

    service = AuditService(
        langfuse_writer=FailingLangfuseWriter(),
        worm_writer=WormWriter(),
        crm_writer=CrmWriter(),
    )

    request = _make_request()
    with pytest.raises(AuditWriteError) as exc_info:
        await service.write_audit(request)

    assert "langfuse" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fail_closed_crm_failure() -> None:
    """If CRM tier fails, entire request fails (fail-closed)."""

    class FailingCrmWriter(CrmWriter):
        async def write(self, entry: AuditEntry) -> TierWriteResult:
            return TierWriteResult(
                tier="crm", success=False, error="Salesforce 503",
            )

    service = AuditService(
        langfuse_writer=LangfuseWriter(),
        worm_writer=WormWriter(),
        crm_writer=FailingCrmWriter(),
    )

    request = _make_request()
    with pytest.raises(AuditWriteError):
        await service.write_audit(request)


# ── Test 3: SHA-256 integrity hash is correct ────────────────────


@pytest.mark.asyncio
async def test_sha256_integrity_hash_correct(service: AuditService) -> None:
    """SHA-256 integrity hash matches recomputation (Rule 3)."""
    request = _make_request()
    response = await service.write_audit(request)

    # Retrieve the entry and recompute hash
    entries = await service.query_by_trace_id("trace-test-001")
    assert len(entries) == 1
    entry = entries[0]

    # Recompute the hash from canonical fields (BLOCKER 7: includes provenance_chain)
    canonical = {
        "canonical_id": entry.canonical_id,
        "trace_id": entry.trace_id,
        "timestamp": entry.timestamp.isoformat(),
        "actor_id": entry.actor_id,
        "action": entry.action,
        "module": entry.module.value,
        "decision": entry.decision.value,
        "input_hash": entry.input_hash,
        "output_hash": entry.output_hash,
        "firm_id": entry.firm_id,
        "provenance_chain": None,
    }
    payload = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    assert entry.sha256_integrity == expected_hash
    assert response.sha256_integrity == expected_hash


def test_sha256_integrity_deterministic() -> None:
    """Same input always produces same SHA-256 hash."""
    entry1 = AuditEntry(
        trace_id="t1",
        actor_id="a1",
        action="test",
        module=AuditModule.m6,
        decision=AuditDecision.allow,
        input_hash="c" * 64,
        output_hash="d" * 64,
        firm_id="firm1",
    )
    entry2 = AuditEntry(
        canonical_id=entry1.canonical_id,
        trace_id="t1",
        actor_id="a1",
        action="test",
        module=AuditModule.m6,
        decision=AuditDecision.allow,
        input_hash="c" * 64,
        output_hash="d" * 64,
        firm_id="firm1",
        timestamp=entry1.timestamp,
    )
    assert entry1.sha256_integrity == entry2.sha256_integrity


# ── Test 4: Provenance chain is preserved ────────────────────────


@pytest.mark.asyncio
async def test_provenance_chain_preserved(service: AuditService) -> None:
    """Provenance chain (ARCH-06 Gap 2) is stored and retrievable."""
    chain = [
        ProvenanceStage(
            stage="identity_verification",
            module="M1",
            hash="e" * 64,
        ),
        ProvenanceStage(
            stage="authority_check",
            module="M2",
            hash="f" * 64,
        ),
        ProvenanceStage(
            stage="mnpi_filter",
            module="M4",
            hash="0" * 64,
        ),
    ]

    request = _make_request(
        trace_id="trace-provenance-001",
        provenance_chain=chain,
    )
    await service.write_audit(request)

    entries = await service.query_by_trace_id("trace-provenance-001")
    assert len(entries) == 1
    entry = entries[0]

    assert entry.provenance_chain is not None
    assert len(entry.provenance_chain) == 3
    assert entry.provenance_chain[0].stage == "identity_verification"
    assert entry.provenance_chain[0].module == "M1"
    assert entry.provenance_chain[0].hash == "e" * 64
    assert entry.provenance_chain[1].stage == "authority_check"
    assert entry.provenance_chain[2].stage == "mnpi_filter"


# ── Test 5: DLQ receives failed entries ──────────────────────────


@pytest.mark.asyncio
async def test_dlq_receives_failed_entries() -> None:
    """Failed writes go to DLQ (Rule 8). Request still fails."""

    class FailingWormWriter(WormWriter):
        async def write(self, entry: AuditEntry) -> TierWriteResult:
            return TierWriteResult(
                tier="worm", success=False, error="disk full",
            )

    service = AuditService(
        langfuse_writer=LangfuseWriter(),
        worm_writer=FailingWormWriter(),
        crm_writer=CrmWriter(),
    )

    request = _make_request(trace_id="trace-dlq-001")

    # Request fails
    with pytest.raises(AuditWriteError):
        await service.write_audit(request)

    # DLQ has the entry
    assert len(service.dead_letter_queue) == 1
    dlq_entry = service.dead_letter_queue[0]
    assert dlq_entry["entry"]["trace_id"] == "trace-dlq-001"
    assert "worm" in dlq_entry["failed_tiers"]


@pytest.mark.asyncio
async def test_dlq_multiple_failures_accumulate() -> None:
    """Multiple failures accumulate in DLQ."""

    class FailingCrmWriter(CrmWriter):
        async def write(self, entry: AuditEntry) -> TierWriteResult:
            return TierWriteResult(
                tier="crm", success=False, error="timeout",
            )

    service = AuditService(
        langfuse_writer=LangfuseWriter(),
        worm_writer=WormWriter(),
        crm_writer=FailingCrmWriter(),
    )

    for i in range(3):
        with pytest.raises(AuditWriteError):
            await service.write_audit(_make_request(trace_id=f"trace-dlq-{i}"))

    assert len(service.dead_letter_queue) == 3


# ── Test 6: Query by trace_id ───────────────────────────────────


@pytest.mark.asyncio
async def test_query_by_trace_id(service: AuditService) -> None:
    """Query returns entries matching trace_id."""
    # Write 2 entries with same trace_id, 1 with different
    await service.write_audit(_make_request(trace_id="trace-query-001"))
    await service.write_audit(
        _make_request(trace_id="trace-query-001", action="portfolio_read"),
    )
    await service.write_audit(_make_request(trace_id="trace-query-002"))

    results = await service.query_by_trace_id("trace-query-001")
    assert len(results) == 2
    assert all(e.trace_id == "trace-query-001" for e in results)

    results2 = await service.query_by_trace_id("trace-query-002")
    assert len(results2) == 1

    # Non-existent trace_id returns empty
    results3 = await service.query_by_trace_id("trace-nonexistent")
    assert len(results3) == 0


# ── Test 7: FastAPI endpoint integration ─────────────────────────


@pytest.mark.asyncio
async def test_fastapi_write_endpoint() -> None:
    """POST /audit/write returns 201 with all tier results."""
    from httpx import ASGITransport, AsyncClient

    from m10_audit_logger.app import app, configure

    configure(
        AuditService(
            langfuse_writer=LangfuseWriter(),
            worm_writer=WormWriter(),
            crm_writer=CrmWriter(),
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/audit/write",
            json={
                "trace_id": "trace-api-001",
                "actor_id": "sha256:api_actor",
                "action": "client_record_accessed",
                "module": "m6",
                "decision": "allow",
                "input_hash": "a" * 64,
                "output_hash": "b" * 64,
                "firm_id": "acme_wm",
            },
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["canonical_id"]
    assert len(body["sha256_integrity"]) == 64
    assert body["worm_record_id"].startswith("s3://")
    assert len(body["tier_results"]) == 3


@pytest.mark.asyncio
async def test_fastapi_query_endpoint() -> None:
    """GET /audit/query returns entries by trace_id."""
    from httpx import ASGITransport, AsyncClient

    from m10_audit_logger.app import app, configure

    svc = AuditService(
        langfuse_writer=LangfuseWriter(),
        worm_writer=WormWriter(),
        crm_writer=CrmWriter(),
    )
    configure(svc)

    # Write an entry first
    await svc.write_audit(_make_request(trace_id="trace-api-query"))

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/audit/query", params={"trace_id": "trace-api-query"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["count"] == 1
    assert body["entries"][0]["trace_id"] == "trace-api-query"


@pytest.mark.asyncio
async def test_fastapi_health_endpoint() -> None:
    """GET /health returns tier health status."""
    from httpx import ASGITransport, AsyncClient

    from m10_audit_logger.app import app, configure

    configure(
        AuditService(
            langfuse_writer=LangfuseWriter(),
            worm_writer=WormWriter(),
            crm_writer=CrmWriter(),
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["tiers"]["langfuse"] is True
    assert body["tiers"]["worm"] is True
    assert body["tiers"]["crm"] is True


@pytest.mark.asyncio
async def test_fastapi_write_fail_closed_returns_503() -> None:
    """POST /audit/write returns 503 when a tier fails."""
    from httpx import ASGITransport, AsyncClient

    from m10_audit_logger.app import app, configure

    class FailingWormWriter(WormWriter):
        async def write(self, entry: AuditEntry) -> TierWriteResult:
            return TierWriteResult(
                tier="worm", success=False, error="S3 down",
            )

    configure(
        AuditService(
            langfuse_writer=LangfuseWriter(),
            worm_writer=FailingWormWriter(),
            crm_writer=CrmWriter(),
        ),
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/audit/write",
            json={
                "trace_id": "trace-fail",
                "actor_id": "sha256:x",
                "action": "test",
                "module": "m6",
                "decision": "allow",
                "input_hash": "a" * 64,
                "output_hash": "b" * 64,
                "firm_id": "test_firm",
            },
        )

    assert resp.status_code == 503
    body = resp.json()
    assert body["detail"]["error"] == "audit_write_failed"


# ── Test: WORM record key format ─────────────────────────────────


@pytest.mark.asyncio
async def test_worm_record_key_format(service: AuditService) -> None:
    """WORM record ID follows S3 key pattern from ARCH-06."""
    request = _make_request(firm_id="acme_wm")
    response = await service.write_audit(request)

    # s3://007-worm-audit/{firm_id}/audit/{year}/{month}/{canonical_id}.json
    assert response.worm_record_id.startswith("s3://007-worm-audit/acme_wm/audit/")
    assert response.worm_record_id.endswith(".json")


# ── Test: Retention years default ─────────────────────────────────


def test_retention_years_default() -> None:
    """Default retention is 6 years per SEC 17a-4."""
    entry = AuditEntry(
        trace_id="t1",
        actor_id="a1",
        action="test",
        module=AuditModule.m10,
        decision=AuditDecision.allow,
        input_hash="a" * 64,
        output_hash="b" * 64,
        firm_id="firm1",
    )
    assert entry.retention_years == 6
