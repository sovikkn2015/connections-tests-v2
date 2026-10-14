"""
Memory Service — Tests (~18 tests).

Uses importlib pattern for module loading (prefix: memory_).
Covers: write/read per layer, TTL expiry L1 (8hr), TTL expiry L2 (7 day),
MNPI filtering on read, conversation context, advisor preferences,
semantic search stub.

No cross-module imports. No credentials. No LLM.
"""

from __future__ import annotations

import importlib
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

# ── importlib pattern ────────────────────────────────────────────


def _load_module(name: str, file_name: str) -> types.ModuleType:
    """Load a module from the memory-service package."""
    import importlib.util
    import pathlib
    base = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, base / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


memory_models = _load_module("memory_models", "models.py")

for _cls_name in dir(memory_models):
    _cls = getattr(memory_models, _cls_name)
    if isinstance(_cls, type) and hasattr(_cls, "model_rebuild") and hasattr(_cls, "__pydantic_generic_metadata__"):
        _cls.model_rebuild()

memory_store_mod = _load_module("memory_store_service", "memory_store.py")

MemoryLayer = memory_models.MemoryLayer
MemoryEntry = memory_models.MemoryEntry
MemoryQuery = memory_models.MemoryQuery
MemoryService = memory_store_mod.MemoryService


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def svc() -> MemoryService:
    """Fresh memory service per test."""
    return MemoryService()


def _entry(
    layer: MemoryLayer = MemoryLayer.L1,
    client_id: str = "cli-001",
    content: str = "test content",
    advisor_id: str | None = None,
    mnpi_tags: list[str] | None = None,
    archetype: str | None = None,
    role: str | None = None,
    channel: str | None = None,
) -> MemoryEntry:
    return MemoryEntry(
        layer=layer,
        client_id=client_id,
        content=content,
        advisor_id=advisor_id,
        mnpi_tags=mnpi_tags or [],
        archetype=archetype,
        role=role,
        channel=channel,
    )


# ── Test 1: Write and read L1 ───────────────────────────────────


def test_memory_write_read_l1(svc):
    """Write to L1 and read back."""
    entry = _entry(MemoryLayer.L1, content="L1 working memory")
    written = svc.write(MemoryLayer.L1, entry)
    assert written.layer == MemoryLayer.L1
    assert written.expires_at is not None  # L1 has 8hr TTL

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L1])
    results = svc.read(query)
    assert len(results) == 1
    assert results[0].content == "L1 working memory"


# ── Test 2: Write and read L2 ───────────────────────────────────


def test_memory_write_read_l2(svc):
    """Write to L2 and read back."""
    entry = _entry(MemoryLayer.L2, content="L2 short-term")
    written = svc.write(MemoryLayer.L2, entry)
    assert written.layer == MemoryLayer.L2
    assert written.expires_at is not None  # L2 has 7d TTL

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L2])
    results = svc.read(query)
    assert len(results) == 1


# ── Test 3: Write and read L3 ───────────────────────────────────


def test_memory_write_read_l3(svc):
    """Write to L3 episodic memory — no auto-expiry."""
    entry = _entry(MemoryLayer.L3, content="L3 episodic")
    written = svc.write(MemoryLayer.L3, entry)
    assert written.expires_at is None  # L3 has no auto-expiry

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L3])
    results = svc.read(query)
    assert len(results) == 1


# ── Test 4: Write and read L4 ───────────────────────────────────


def test_memory_write_read_l4(svc):
    """Write to L4 semantic memory — permanent."""
    entry = _entry(MemoryLayer.L4, content="L4 semantic fact")
    written = svc.write(MemoryLayer.L4, entry)
    assert written.expires_at is None

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L4])
    results = svc.read(query)
    assert len(results) == 1


# ── Test 5: Write and read L5 ───────────────────────────────────


def test_memory_write_read_l5(svc):
    """Write to L5 procedural memory — advisor preferences."""
    entry = _entry(MemoryLayer.L5, content="Prefers morning meetings", advisor_id="adv-001")
    written = svc.write(MemoryLayer.L5, entry)
    assert written.expires_at is None

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L5])
    results = svc.read(query)
    assert len(results) == 1


# ── Test 6: L6 write redirects to M10 ───────────────────────────


def test_memory_l6_redirects_to_m10(svc):
    """L6 compliance memory redirects to M10 — not stored locally."""
    entry = _entry(MemoryLayer.L6, content="Compliance record")
    written = svc.write(MemoryLayer.L6, entry)
    assert written.layer == MemoryLayer.L6

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L6])
    results = svc.read(query)
    assert len(results) == 0  # Not stored in local memory


# ── Test 7: L1 TTL expiry (8hr) ─────────────────────────────────


def test_memory_l1_ttl_expiry(svc):
    """L1 entries expire after 8 hours."""
    entry = _entry(MemoryLayer.L1, content="Will expire")
    written = svc.write(MemoryLayer.L1, entry)

    # Manually set expires_at to past
    past = (datetime.now(timezone.utc) - timedelta(hours=9)).isoformat()
    svc._stores[MemoryLayer.L1][0] = written.model_copy(update={"expires_at": past})

    removed = svc.expire_entries()
    assert removed == 1

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L1])
    results = svc.read(query)
    assert len(results) == 0


# ── Test 8: L2 TTL expiry (7 day) ───────────────────────────────


def test_memory_l2_ttl_expiry(svc):
    """L2 entries expire after 7 days."""
    entry = _entry(MemoryLayer.L2, content="Will expire")
    written = svc.write(MemoryLayer.L2, entry)

    past = (datetime.now(timezone.utc) - timedelta(days=8)).isoformat()
    svc._stores[MemoryLayer.L2][0] = written.model_copy(update={"expires_at": past})

    removed = svc.expire_entries()
    assert removed == 1

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L2])
    results = svc.read(query)
    assert len(results) == 0


# ── Test 9: Non-expired entries survive ──────────────────────────


def test_memory_non_expired_survive(svc):
    """Non-expired entries are not removed."""
    entry = _entry(MemoryLayer.L1, content="Still fresh")
    svc.write(MemoryLayer.L1, entry)

    removed = svc.expire_entries()
    assert removed == 0

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L1])
    results = svc.read(query)
    assert len(results) == 1


# ── Test 10: MNPI filtering on read — blocked ───────────────────


def test_memory_mnpi_filtering_blocked(svc):
    """MNPI-tagged entries are blocked when caller lacks archetype."""
    entry = _entry(
        MemoryLayer.L1,
        content="Sensitive holdings data",
        mnpi_tags=["holdings_amount"],
        archetype="tier3_advisor",
    )
    svc.write(MemoryLayer.L1, entry)

    # Query without matching archetype — should be filtered out
    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L1])
    results = svc.read(query)
    assert len(results) == 0


# ── Test 11: MNPI filtering on read — allowed ───────────────────


def test_memory_mnpi_filtering_allowed(svc):
    """MNPI-tagged entries are visible when caller has matching archetype."""
    entry = _entry(
        MemoryLayer.L1,
        content="Sensitive holdings data",
        mnpi_tags=["holdings_amount"],
        archetype="tier3_advisor",
    )
    svc.write(MemoryLayer.L1, entry)

    # Query with matching archetype — should be visible
    query = MemoryQuery(
        client_id="cli-001",
        layers=[MemoryLayer.L1],
        archetype_filter="tier3_advisor",
    )
    results = svc.read(query)
    assert len(results) == 1
    assert results[0].content == "Sensitive holdings data"


# ── Test 12: MNPI role filtering ─────────────────────────────────


def test_memory_mnpi_role_filtering(svc):
    """MNPI entries with role restriction are filtered by role."""
    entry = _entry(
        MemoryLayer.L2,
        content="Trade intention data",
        mnpi_tags=["trade_intention"],
        role="portfolio_manager",
    )
    svc.write(MemoryLayer.L2, entry)

    # Wrong role — blocked
    query = MemoryQuery(
        client_id="cli-001",
        layers=[MemoryLayer.L2],
        role_filter="analyst",
    )
    assert len(svc.read(query)) == 0

    # Correct role — allowed
    query = MemoryQuery(
        client_id="cli-001",
        layers=[MemoryLayer.L2],
        role_filter="portfolio_manager",
    )
    assert len(svc.read(query)) == 1


# ── Test 13: Conversation context (L1) ──────────────────────────


def test_memory_conversation_context(svc):
    """get_conversation_context returns L1 entries for client."""
    svc.write(MemoryLayer.L1, _entry(content="msg 1", channel="slack"))
    svc.write(MemoryLayer.L1, _entry(content="msg 2", channel="slack"))
    svc.write(MemoryLayer.L1, _entry(content="msg 3", channel="teams"))

    results = svc.get_conversation_context("cli-001")
    assert len(results) == 3

    # Filter by channel
    results = svc.get_conversation_context("cli-001", channel="slack")
    assert len(results) == 2


# ── Test 14: Advisor preferences (L5) ───────────────────────────


def test_memory_advisor_preferences(svc):
    """get_advisor_preferences returns L5 procedural memory."""
    entry = _entry(MemoryLayer.L5, content="Prefers charts over tables", advisor_id="adv-001")
    svc.write(MemoryLayer.L5, entry)

    prefs = svc.get_advisor_preferences("adv-001")
    assert len(prefs) > 0
    assert "Prefers charts over tables" in prefs.values()


# ── Test 15: Advisor preferences empty ───────────────────────────


def test_memory_advisor_preferences_empty(svc):
    """get_advisor_preferences returns empty dict for unknown advisor."""
    prefs = svc.get_advisor_preferences("unknown-advisor")
    assert prefs == {}


# ── Test 16: Semantic search stub returns empty ──────────────────


def test_memory_semantic_search_stub(svc):
    """search_semantic returns empty list in dev mode."""
    results = svc.search_semantic("cli-001", "retirement planning")
    assert results == []


# ── Test 17: Multi-layer read ────────────────────────────────────


def test_memory_multi_layer_read(svc):
    """Read across multiple layers."""
    svc.write(MemoryLayer.L1, _entry(MemoryLayer.L1, content="L1 entry"))
    svc.write(MemoryLayer.L2, _entry(MemoryLayer.L2, content="L2 entry"))
    svc.write(MemoryLayer.L3, _entry(MemoryLayer.L3, content="L3 entry"))

    query = MemoryQuery(
        client_id="cli-001",
        layers=[MemoryLayer.L1, MemoryLayer.L2, MemoryLayer.L3],
    )
    results = svc.read(query)
    assert len(results) == 3


# ── Test 18: Client isolation ────────────────────────────────────


def test_memory_client_isolation(svc):
    """Entries for different clients are isolated."""
    svc.write(MemoryLayer.L1, _entry(client_id="cli-001", content="Client 1 data"))
    svc.write(MemoryLayer.L1, _entry(client_id="cli-002", content="Client 2 data"))

    query = MemoryQuery(client_id="cli-001", layers=[MemoryLayer.L1])
    results = svc.read(query)
    assert len(results) == 1
    assert results[0].content == "Client 1 data"


# ═══════════════════════════════════════════════════════════════════
# FastAPI endpoint tests
# ═══════════════════════════════════════════════════════════════════

memory_app_mod = _load_module("memory_app", "app.py")
create_app = memory_app_mod.create_app

from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


def test_memory_health_endpoint(client):
    """GET /health returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "memory-service"


def test_memory_write_endpoint(client):
    """POST /memory/write stores an entry."""
    resp = client.post("/memory/write", json={
        "layer": "L1",
        "entry": {
            "layer": "L1",
            "client_id": "cli-001",
            "content": "Test write via API",
        },
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["layer"] == "L1"
    assert body["content"] == "Test write via API"


def test_memory_conversation_endpoint(client):
    """GET /memory/conversation/{client_id} returns entries."""
    # Write first
    client.post("/memory/write", json={
        "layer": "L1",
        "entry": {
            "layer": "L1",
            "client_id": "cli-001",
            "content": "Conversation message",
        },
    })
    resp = client.get("/memory/conversation/cli-001")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) >= 1
