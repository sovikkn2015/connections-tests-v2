"""
Smarsh Archiver — Tests (~12 tests).

Uses importlib pattern for module loading (prefix: smarsh_).
Covers: archive communication, verify, SHA-256 hash, content types,
missing record, health endpoint.

No cross-module imports. No credentials. No LLM.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import sys
import types

import pytest

# ── importlib pattern ────────────────────────────────────────────


def _load_module(name: str, file_name: str) -> types.ModuleType:
    """Load a module from the smarsh-archiver package using importlib."""
    import importlib.util
    import pathlib
    base = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, base / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


smarsh_models = _load_module("smarsh_models", "models.py")

for _cls_name in dir(smarsh_models):
    _cls = getattr(smarsh_models, _cls_name)
    if isinstance(_cls, type) and hasattr(_cls, "model_rebuild") and hasattr(_cls, "__pydantic_generic_metadata__"):
        try:
            _cls.model_rebuild()
        except Exception:
            pass

smarsh_archiver_mod = _load_module("smarsh_archiver_service", "archiver.py")

# Rebuild models again after archiver module loaded (it may have its own refs)
for _cls_name in dir(smarsh_models):
    _cls = getattr(smarsh_models, _cls_name)
    if isinstance(_cls, type) and hasattr(_cls, "model_rebuild") and hasattr(_cls, "__pydantic_generic_metadata__"):
        try:
            _cls.model_rebuild()
        except Exception:
            pass

# Also rebuild models referenced inside the archiver module
for _attr in ["ArchiveRecord", "ArchiveResult", "SmarshConfig"]:
    _cls = getattr(smarsh_archiver_mod, _attr, None)
    if _cls and hasattr(_cls, "model_rebuild"):
        try:
            _cls.model_rebuild()
        except Exception:
            pass

ContentType = smarsh_models.ContentType
SmarshConfig = smarsh_models.SmarshConfig
ArchiveRecord = smarsh_models.ArchiveRecord
ArchiveResult = smarsh_models.ArchiveResult
SmarshArchiver = smarsh_archiver_mod.SmarshArchiver


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def archiver() -> SmarshArchiver:
    """Fresh archiver with in-memory store per test."""
    config = SmarshConfig(firm_id="test-firm-001")
    return SmarshArchiver(config=config)


# ── Test 1: Archive agent_response ───────────────────────────────


@pytest.mark.asyncio
async def test_smarsh_archive_agent_response(archiver):
    """Archive an agent_response communication."""
    result = await archiver.archive_communication(
        content="Based on your portfolio, I recommend...",
        content_type="agent_response",
        metadata={"advisor_id": "adv-001", "client_id": "cli-001"},
    )
    assert result.success is True
    assert result.receipt_id is not None
    assert result.receipt_id.startswith("SMARSH-")
    assert result.record_id is not None


# ── Test 2: Archive meeting_summary ──────────────────────────────


@pytest.mark.asyncio
async def test_smarsh_archive_meeting_summary(archiver):
    """Archive a meeting_summary communication."""
    result = await archiver.archive_communication(
        content="Meeting with Henderson: discussed retirement planning.",
        content_type="meeting_summary",
    )
    assert result.success is True
    assert result.receipt_id is not None


# ── Test 3: Archive research_brief ───────────────────────────────


@pytest.mark.asyncio
async def test_smarsh_archive_research_brief(archiver):
    """Archive a research_brief communication."""
    result = await archiver.archive_communication(
        content="SEC filing analysis for ACME Corp Q4 2024.",
        content_type="research_brief",
    )
    assert result.success is True


# ── Test 4: Archive trade_confirmation ───────────────────────────


@pytest.mark.asyncio
async def test_smarsh_archive_trade_confirmation(archiver):
    """Archive a trade_confirmation communication."""
    result = await archiver.archive_communication(
        content="Trade confirmed: BUY 100 AAPL @ $185.50",
        content_type="trade_confirmation",
    )
    assert result.success is True


# ── Test 5: SHA-256 hash computed correctly ──────────────────────


@pytest.mark.asyncio
async def test_smarsh_sha256_hash_correct(archiver):
    """SHA-256 hash of content matches manual computation."""
    content = "Test content for hashing"
    expected_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    result = await archiver.archive_communication(
        content=content, content_type="agent_response",
    )
    assert result.success is True

    record = await archiver.get_archive_status(result.record_id)
    assert record is not None
    assert record.content_hash == expected_hash
    assert len(record.content_hash) == 64
    assert re.match(r"^[a-f0-9]{64}$", record.content_hash)


# ── Test 6: SHA-256 static method ────────────────────────────────


def test_smarsh_compute_content_hash_static():
    """Static compute_content_hash returns valid SHA-256."""
    content = "Hello, Smarsh!"
    h = SmarshArchiver.compute_content_hash(content)
    expected = hashlib.sha256(content.encode("utf-8")).hexdigest()
    assert h == expected
    assert len(h) == 64


# ── Test 7: Verify archive by receipt ID ─────────────────────────


@pytest.mark.asyncio
async def test_smarsh_verify_archive(archiver):
    """Verify archive returns True for existing receipt."""
    result = await archiver.archive_communication(
        content="Archivable content", content_type="agent_response",
    )
    assert result.success is True

    verified = await archiver.verify_archive(result.receipt_id)
    assert verified is True


# ── Test 8: Verify archive returns False for unknown receipt ─────


@pytest.mark.asyncio
async def test_smarsh_verify_archive_unknown(archiver):
    """Verify archive returns False for non-existent receipt."""
    verified = await archiver.verify_archive("SMARSH-NONEXISTENT")
    assert verified is False


# ── Test 9: Get archive status ───────────────────────────────────


@pytest.mark.asyncio
async def test_smarsh_get_archive_status(archiver):
    """Get archive status returns the record."""
    result = await archiver.archive_communication(
        content="Status check content", content_type="meeting_summary",
    )
    record = await archiver.get_archive_status(result.record_id)
    assert record is not None
    assert record.record_id == result.record_id
    assert record.content_type == ContentType.meeting_summary
    assert record.retention_years == 6
    assert record.firm_id == "test-firm-001"


# ── Test 10: Get archive status missing record ──────────────────


@pytest.mark.asyncio
async def test_smarsh_get_archive_status_missing(archiver):
    """Get archive status returns None for non-existent record."""
    record = await archiver.get_archive_status("nonexistent-id")
    assert record is None


# ── Test 11: Invalid content type rejected ───────────────────────


@pytest.mark.asyncio
async def test_smarsh_invalid_content_type(archiver):
    """Invalid content type returns failure."""
    result = await archiver.archive_communication(
        content="Some content", content_type="invalid_type",
    )
    assert result.success is False
    assert "Invalid content_type" in result.error


# ── Test 12: Metadata preserved on record ────────────────────────


@pytest.mark.asyncio
async def test_smarsh_metadata_preserved(archiver):
    """Metadata is preserved on the archive record."""
    meta = {"advisor_id": "adv-001", "channel": "slack"}
    result = await archiver.archive_communication(
        content="Content with metadata",
        content_type="agent_response",
        metadata=meta,
    )
    record = await archiver.get_archive_status(result.record_id)
    assert record.metadata == meta


# ═══════════════════════════════════════════════════════════════════
# FastAPI endpoint tests
# ═══════════════════════════════════════════════════════════════════

smarsh_app_mod = _load_module("smarsh_app", "app.py")
create_app = smarsh_app_mod.create_app

from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


def test_smarsh_health_endpoint(client):
    """GET /health returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "smarsh-archiver"


def test_smarsh_archive_endpoint(client):
    """POST /archive returns success."""
    resp = client.post("/archive", json={
        "content": "Test communication for archiving",
        "content_type": "agent_response",
        "metadata": {"test": True},
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert body["receipt_id"] is not None


def test_smarsh_archive_get_not_found(client):
    """GET /archive/{id} returns 404 for missing record."""
    resp = client.get("/archive/nonexistent-id")
    assert resp.status_code == 404
