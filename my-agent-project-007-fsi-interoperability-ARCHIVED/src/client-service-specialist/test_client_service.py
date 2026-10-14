"""
Client Service Specialist — Tests (~15 tests).

Uses importlib pattern for module loading (prefix: clientsvc_).
Covers: meeting prep, portfolio review, client summary, MNPI filtered flag,
sources tracked, channel preserved.

No cross-module imports. No credentials. No LLM.
"""

from __future__ import annotations

import importlib
import sys
import types

import pytest

# ── importlib pattern ────────────────────────────────────────────


def _load_module(name: str, file_name: str) -> types.ModuleType:
    """Load a module from the client-service-specialist package."""
    import importlib.util
    import pathlib
    base = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, base / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


clientsvc_models = _load_module("clientsvc_models", "models.py")

for _cls_name in dir(clientsvc_models):
    _cls = getattr(clientsvc_models, _cls_name)
    if isinstance(_cls, type) and hasattr(_cls, "model_rebuild") and hasattr(_cls, "__pydantic_generic_metadata__"):
        _cls.model_rebuild()

clientsvc_service = _load_module("clientsvc_service", "service.py")

ClientServiceRequest = clientsvc_models.ClientServiceRequest
ClientServiceResponse = clientsvc_models.ClientServiceResponse
MeetingPrepBrief = clientsvc_models.MeetingPrepBrief
RequestType = clientsvc_models.RequestType
ClientServiceEngine = clientsvc_service.ClientServiceEngine


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def engine() -> ClientServiceEngine:
    """Fresh engine with in-memory stubs per test."""
    return ClientServiceEngine()


def _make_request(
    request_type: str = "meeting_prep",
    client_id: str = "cli-001",
    channel: str = "slack",
    advisor_id: str = "adv-001",
    query: str | None = None,
) -> ClientServiceRequest:
    return ClientServiceRequest(
        client_id=client_id,
        request_type=RequestType(request_type),
        channel=channel,
        advisor_id=advisor_id,
        query=query,
    )


# ── Test 1: Meeting prep returns content ─────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_meeting_prep_content(engine):
    """Meeting prep returns content with client name."""
    req = _make_request("meeting_prep")
    resp = await engine.handle_request(req)
    assert "Meeting Prep" in resp.content
    assert "Henderson" in resp.content


# ── Test 2: Meeting prep brief structure ─────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_meeting_prep_brief(engine):
    """prepare_meeting returns a MeetingPrepBrief with highlights."""
    brief = await engine.prepare_meeting("cli-001")
    assert type(brief).__name__ == "MeetingPrepBrief"
    assert brief.client_name == "Jane Henderson"
    assert len(brief.portfolio_highlights) > 0
    assert len(brief.action_items) > 0


# ── Test 3: Meeting prep portfolio highlights ────────────────────


@pytest.mark.asyncio
async def test_clientsvc_meeting_prep_highlights(engine):
    """Meeting prep includes portfolio value in highlights."""
    brief = await engine.prepare_meeting("cli-001")
    combined = " ".join(brief.portfolio_highlights)
    assert "$85,800.00" in combined


# ── Test 4: Meeting prep action items ────────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_meeting_prep_action_items(engine):
    """Meeting prep includes risk tolerance in action items."""
    brief = await engine.prepare_meeting("cli-001")
    combined = " ".join(brief.action_items)
    assert "moderate" in combined.lower()


# ── Test 5: Portfolio review returns summary ─────────────────────


@pytest.mark.asyncio
async def test_clientsvc_portfolio_review(engine):
    """Portfolio review returns summary with total value."""
    req = _make_request("portfolio_review")
    resp = await engine.handle_request(req)
    assert "Portfolio Review" in resp.content
    assert "$85,800.00" in resp.content


# ── Test 6: Portfolio review includes positions ──────────────────


@pytest.mark.asyncio
async def test_clientsvc_portfolio_review_positions(engine):
    """Portfolio review includes position count."""
    summary = await engine.review_portfolio("cli-001")
    assert "Positions: 3" in summary


# ── Test 7: Client summary returns profile ───────────────────────


@pytest.mark.asyncio
async def test_clientsvc_client_summary(engine):
    """Client summary returns profile with name and type."""
    req = _make_request("client_summary")
    resp = await engine.handle_request(req)
    assert "Client Summary" in resp.content
    assert "Henderson" in resp.content


# ── Test 8: Client summary no PII ────────────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_client_summary_no_pii(engine):
    """Client summary does not contain PII (SSN, DOB)."""
    summary = await engine.summarize_client("cli-001")
    assert "ssn" not in summary.lower()
    assert "dob" not in summary.lower()
    assert "date_of_birth" not in summary.lower()


# ── Test 9: MNPI filtered flag always True ───────────────────────


@pytest.mark.asyncio
async def test_clientsvc_mnpi_filtered_flag(engine):
    """All responses have mnpi_filtered=True."""
    for rt in ["meeting_prep", "portfolio_review", "client_summary", "general"]:
        req = _make_request(rt, query="test query")
        resp = await engine.handle_request(req)
        assert resp.mnpi_filtered is True, f"mnpi_filtered should be True for {rt}"


# ── Test 10: Sources tracked for meeting prep ────────────────────


@pytest.mark.asyncio
async def test_clientsvc_sources_tracked_meeting_prep(engine):
    """Meeting prep tracks data sources used."""
    req = _make_request("meeting_prep")
    resp = await engine.handle_request(req)
    assert len(resp.sources_used) > 0
    assert "salesforce_fsc" in resp.sources_used


# ── Test 11: Sources tracked for portfolio review ────────────────


@pytest.mark.asyncio
async def test_clientsvc_sources_tracked_portfolio(engine):
    """Portfolio review tracks data sources."""
    req = _make_request("portfolio_review")
    resp = await engine.handle_request(req)
    assert "orion" in resp.sources_used


# ── Test 12: Channel preserved in response ───────────────────────


@pytest.mark.asyncio
async def test_clientsvc_channel_preserved(engine):
    """Channel from request is preserved in response."""
    for channel in ["slack", "teams", "whatsapp", "web"]:
        req = _make_request("client_summary", channel=channel)
        resp = await engine.handle_request(req)
        assert resp.channel == channel


# ── Test 13: General request with query ──────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_general_request(engine):
    """General request includes the query text."""
    req = _make_request("general", query="What is the client's risk profile?")
    resp = await engine.handle_request(req)
    assert "risk profile" in resp.content.lower()


# ── Test 14: Trace ID preserved ──────────────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_trace_id_preserved(engine):
    """Trace ID from request is preserved in response."""
    req = _make_request("meeting_prep")
    resp = await engine.handle_request(req)
    assert resp.trace_id == req.trace_id


# ── Test 15: Response has response_id ────────────────────────────


@pytest.mark.asyncio
async def test_clientsvc_response_has_id(engine):
    """Every response has a unique response_id."""
    req = _make_request("client_summary")
    resp = await engine.handle_request(req)
    assert resp.response_id is not None
    assert len(resp.response_id) > 0


# ═══════════════════════════════════════════════════════════════════
# FastAPI endpoint tests
# ═══════════════════════════════════════════════════════════════════

clientsvc_app_mod = _load_module("clientsvc_app", "app.py")
create_app = clientsvc_app_mod.create_app

from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


def test_clientsvc_health_endpoint(client):
    """GET /health returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "client-service-specialist"


def test_clientsvc_service_request_endpoint(client):
    """POST /service/request returns response."""
    resp = client.post("/service/request", json={
        "client_id": "cli-001",
        "request_type": "meeting_prep",
        "advisor_id": "adv-001",
        "channel": "slack",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["mnpi_filtered"] is True
    assert "content" in body
