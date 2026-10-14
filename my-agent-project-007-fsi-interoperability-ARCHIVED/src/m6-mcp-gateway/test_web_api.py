"""
M6 Web API Layer — Tests.

Tests cover:
  1. test_chat_send_returns_message — POST /api/v1/chat/send with valid token
  2. test_chat_send_requires_auth — POST /api/v1/chat/send without token → 401
  3. test_reviews_pending_requires_principal_role — GET /api/v1/reviews/pending
  4. test_audit_trail_requires_compliance_role — GET /api/v1/audit/trail
  5. test_admin_health_requires_admin_role — GET /api/v1/admin/health
  6. test_order_approve_writes_audit — POST /api/v1/orders/approve
  7. test_sse_stream_sends_events — GET /api/v1/chat/stream (mock SSE)

All downstream modules (M1, M2, M4, M9, M10) are mocked via
unittest.mock.patch — no cross-module imports.
"""

from __future__ import annotations

import importlib
import json
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch, MagicMock

import httpx
import pytest
import pytest_asyncio

# ── Package registration (same pattern as test_m6_gateway.py) ────

_pkg_dir = Path(__file__).parent
_pkg_name = "m6_mcp_gateway"
if _pkg_name not in sys.modules:
    _spec = importlib.util.spec_from_file_location(
        _pkg_name,
        _pkg_dir / "__init__.py",
        submodule_search_locations=[str(_pkg_dir)],
    )
    _mod = importlib.util.module_from_spec(_spec)
    sys.modules[_pkg_name] = _mod
    _spec.loader.exec_module(_mod)

for _submod_name in (
    "models", "leakage_scan", "resilience", "trust_pipeline",
    "mcp_proxy", "web_api", "app",
):
    _full_name = f"{_pkg_name}.{_submod_name}"
    if _full_name not in sys.modules:
        _sub_spec = importlib.util.spec_from_file_location(
            _full_name,
            _pkg_dir / f"{_submod_name}.py",
            submodule_search_locations=[str(_pkg_dir)],
        )
        _sub_mod = importlib.util.module_from_spec(_sub_spec)
        sys.modules[_full_name] = _sub_mod
        _sub_spec.loader.exec_module(_sub_mod)

from fastapi.testclient import TestClient
from m6_mcp_gateway.app import app


import m6_mcp_gateway.web_api as web_api_mod


# ── Mock response builders ───────────────────────────────────────

VALID_TOKEN = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.test.signature"


def _m1_valid(role: str = "advisor") -> dict:
    return {
        "valid": True,
        "aid_id": "aid-test-001",
        "claims": {
            "actor_type": "human",
            "display_name": "test.user",
            "firm_id": "test_firm",
            "archetype": "tier4_independent_ria",
            "role": role,
            "jurisdiction": "US",
            "authority_scope": ["*"],
            "authority_excludes": [],
            "client_scope": ["*"],
            "pod_id": None,
        },
    }


def _m1_invalid() -> dict:
    return {"valid": False, "reason": "Token expired"}


def _m2_allow() -> dict:
    return {"decision": "ALLOW", "reason": "Authorized"}


def _m2_deny() -> dict:
    return {"decision": "DENY", "reason": "Not authorized"}


def _m4_passthrough(payload: dict) -> dict:
    return {"filtered_payload": payload, "fields_removed": []}


def _m10_ok() -> dict:
    return {"canonical_id": "audit-001", "sha256_integrity": "a" * 64, "tier_results": []}


def _m9_classify() -> dict:
    return {
        "specialist": "client_service",
        "response": "Here is the portfolio summary for your client.",
        "intent": "portfolio_review",
        "confidence": 0.95,
    }


# ── Mock httpx transport ─────────────────────────────────────────


class WebAPIMockTransport(httpx.AsyncBaseTransport):
    """Mock transport for web API tests. Routes by URL pattern."""

    def __init__(self, role: str = "advisor", m1_valid: bool = True, m2_allow: bool = True):
        self._role = role
        self._m1_valid = m1_valid
        self._m2_allow = m2_allow
        self.audit_calls: list[dict] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        url = str(request.url)

        if "/aid/verify" in url:
            data = _m1_valid(self._role) if self._m1_valid else _m1_invalid()
            return httpx.Response(200, json=data)

        if "/policy/authority" in url:
            data = _m2_allow() if self._m2_allow else _m2_deny()
            return httpx.Response(200, json=data)

        if "/mnpi/filter" in url:
            body = json.loads(request.content) if request.content else {}
            payload = body.get("data_payload", {})
            return httpx.Response(200, json=_m4_passthrough(payload))

        if "/intent/classify" in url:
            return httpx.Response(200, json=_m9_classify())

        if "/audit/write" in url:
            body = json.loads(request.content) if request.content else {}
            self.audit_calls.append(body)
            return httpx.Response(201, json=_m10_ok())

        if "/audit/query" in url:
            return httpx.Response(200, json={"entries": [], "count": 0})

        if "/memory/conversation" in url:
            return httpx.Response(200, json={"messages": []})

        if "/order/" in url and "/approve" in url:
            return httpx.Response(200, json={"state": "APPROVED"})

        if "/order/" in url and "/reject" in url:
            return httpx.Response(200, json={"state": "CANCELLED"})

        if "/health" in url:
            return httpx.Response(200, json={"status": "ok"})

        return httpx.Response(404, json={"error": "not found"})


def _inject_mock_client(transport: WebAPIMockTransport):
    """Replace the web_api module's httpx client with a mock transport."""
    mock_client = httpx.AsyncClient(transport=transport)
    web_api_mod._http_client = mock_client
    return mock_client


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _reset_client():
    """Reset the shared httpx client before each test."""
    web_api_mod._http_client = None
    yield
    web_api_mod._http_client = None


@pytest.fixture
def client():
    """FastAPI test client with web_api routes only (no lifespan needed)."""
    from fastapi import FastAPI
    test_app = FastAPI()
    test_app.include_router(web_api_mod.web_api_router)
    return TestClient(test_app)


# ═════════════════════════════════════════════════════════════════
# TEST 1: chat_send returns ChatMessage
# ═════════════════════════════════════════════════════════════════


class TestChatSend:
    def test_chat_send_returns_message(self, client):
        """POST /api/v1/chat/send with valid token returns ChatMessage."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/chat/send",
            json={"content": "Show me the Henderson portfolio"},
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["role"] == "agent"
        assert data["specialist"] == "client_service"
        assert "content" in data
        assert len(data["content"]) > 0
        assert "timestamp" in data
        assert "provenanceTraceId" in data

    def test_chat_send_requires_auth(self, client):
        """POST /api/v1/chat/send without token returns 401."""
        resp = client.post(
            "/api/v1/chat/send",
            json={"content": "Hello"},
        )

        assert resp.status_code == 401
        data = resp.json()
        assert "error" in data

    def test_chat_send_invalid_token(self, client):
        """POST /api/v1/chat/send with invalid token returns 401."""
        transport = WebAPIMockTransport(m1_valid=False)
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/chat/send",
            json={"content": "Hello"},
            headers={"Authorization": "Bearer invalid-token"},
        )

        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════
# TEST 2: reviews/pending requires principal role
# ═════════════════════════════════════════════════════════════════


class TestReviewsPending:
    def test_reviews_pending_requires_principal_role(self, client):
        """GET /api/v1/reviews/pending with advisor role returns 403."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/reviews/pending",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 403

    def test_reviews_pending_allowed_for_principal(self, client):
        """GET /api/v1/reviews/pending with principal role succeeds."""
        transport = WebAPIMockTransport(role="principal")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/reviews/pending",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200

    def test_reviews_pending_allowed_for_admin(self, client):
        """GET /api/v1/reviews/pending with admin role succeeds."""
        transport = WebAPIMockTransport(role="admin")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/reviews/pending",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200

    def test_reviews_pending_requires_auth(self, client):
        """GET /api/v1/reviews/pending without token returns 401."""
        resp = client.get("/api/v1/reviews/pending")
        assert resp.status_code == 401


# ═════════════════════════════════════════════════════════════════
# TEST 3: audit/trail requires compliance_officer role
# ═════════════════════════════════════════════════════════════════


class TestAuditTrail:
    def test_audit_trail_requires_compliance_role(self, client):
        """GET /api/v1/audit/trail with advisor role returns 403."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/audit/trail",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 403

    def test_audit_trail_allowed_for_compliance_officer(self, client):
        """GET /api/v1/audit/trail with compliance_officer role succeeds."""
        transport = WebAPIMockTransport(role="compliance_officer")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/audit/trail",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200

    def test_audit_trail_allowed_for_admin(self, client):
        """GET /api/v1/audit/trail with admin role succeeds."""
        transport = WebAPIMockTransport(role="admin")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/audit/trail",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200


# ═════════════════════════════════════════════════════════════════
# TEST 4: admin/health requires admin role
# ═════════════════════════════════════════════════════════════════


class TestAdminHealth:
    def test_admin_health_requires_admin_role(self, client):
        """GET /api/v1/admin/health with advisor role returns 403."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/admin/health",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 403

    def test_admin_health_allowed_for_admin(self, client):
        """GET /api/v1/admin/health with admin role returns LayerHealth[]."""
        transport = WebAPIMockTransport(role="admin")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/admin/health",
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) >= 1
        for layer in data:
            assert "name" in layer
            assert "modules" in layer


# ═════════════════════════════════════════════════════════════════
# TEST 5: order/approve writes audit
# ═════════════════════════════════════════════════════════════════


class TestOrderApprove:
    def test_order_approve_writes_audit(self, client):
        """POST /api/v1/orders/approve writes audit entry to M10."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/orders/approve",
            json={"orderId": "ORD-12345"},
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "approvalToken" in data
        assert len(data["approvalToken"]) == 64  # SHA-256 hex

        # Verify audit was written
        assert len(transport.audit_calls) >= 1
        audit_entry = transport.audit_calls[-1]
        assert audit_entry["action"] == "order.approve"
        assert audit_entry["decision"] == "allow"

    def test_order_approve_requires_auth(self, client):
        """POST /api/v1/orders/approve without token returns 401."""
        resp = client.post(
            "/api/v1/orders/approve",
            json={"orderId": "ORD-12345"},
        )
        assert resp.status_code == 401

    def test_order_reject_writes_audit(self, client):
        """POST /api/v1/orders/reject writes audit entry."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/orders/reject",
            json={"orderId": "ORD-12345", "reason": "Client changed mind"},
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True

        assert len(transport.audit_calls) >= 1
        audit_entry = transport.audit_calls[-1]
        assert audit_entry["action"] == "order.reject"


# ═════════════════════════════════════════════════════════════════
# TEST 6: SSE stream sends events
# ═════════════════════════════════════════════════════════════════


class TestSSEStream:
    def test_sse_stream_sends_events(self, client):
        """GET /api/v1/chat/stream returns SSE events."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/chat/stream",
            params={
                "conversationId": "conv-001",
                "content": "Show portfolio",
                "token": VALID_TOKEN,
            },
        )

        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers.get("content-type", "")

        body = resp.text
        events = _parse_sse_events(body)

        event_types = [e["event"] for e in events]
        assert "detail" in event_types, f"Expected 'detail' event, got: {event_types}"
        assert "token" in event_types, f"Expected 'token' event, got: {event_types}"
        assert "done" in event_types, f"Expected 'done' event, got: {event_types}"

    def test_sse_stream_requires_auth(self, client):
        """GET /api/v1/chat/stream without token returns 401."""
        resp = client.get(
            "/api/v1/chat/stream",
            params={"conversationId": "conv-001", "content": "Hello"},
        )

        assert resp.status_code == 401

    def test_sse_stream_blocked_on_trust_failure(self, client):
        """GET /api/v1/chat/stream with invalid token sends blocked event."""
        transport = WebAPIMockTransport(m1_valid=False)
        _inject_mock_client(transport)

        resp = client.get(
            "/api/v1/chat/stream",
            params={
                "conversationId": "conv-001",
                "content": "Hello",
                "token": "bad-token",
            },
        )

        assert resp.status_code == 200
        body = resp.text
        events = _parse_sse_events(body)
        event_types = [e["event"] for e in events]
        assert "blocked" in event_types


# ── SSE parser helper ────────────────────────────────────────────


def _parse_sse_events(body: str) -> list[dict[str, str]]:
    """Parse SSE event stream into list of {event, data} dicts."""
    events = []
    current_event = "message"
    current_data = ""

    for line in body.split("\n"):
        if line.startswith("event: "):
            current_event = line[7:].strip()
        elif line.startswith("data: "):
            current_data = line[6:]
        elif line == "":
            if current_event or current_data:
                events.append({"event": current_event, "data": current_data})
                current_event = "message"
                current_data = ""

    return events


# ═════════════════════════════════════════════════════════════════
# TEST 7: M2 authority denial blocks request
# ═════════════════════════════════════════════════════════════════


class TestAuthorityDenial:
    def test_chat_send_denied_by_m2(self, client):
        """POST /api/v1/chat/send denied when M2 returns DENY."""
        transport = WebAPIMockTransport(role="advisor", m2_allow=False)
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/chat/send",
            json={"content": "Hello"},
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 403


# ═════════════════════════════════════════════════════════════════
# TEST 8: Reviews action generates approval token
# ═════════════════════════════════════════════════════════════════


class TestReviewsAction:
    def test_reviews_action_generates_approval_token(self, client):
        """POST /api/v1/reviews/action returns SHA-256 approval token."""
        transport = WebAPIMockTransport(role="principal")
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/reviews/action",
            json={
                "reviewId": "rev-001",
                "action": "approve",
                "reason": "Looks good",
            },
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert "approvalToken" in data
        assert len(data["approvalToken"]) == 64

    def test_reviews_action_requires_principal(self, client):
        """POST /api/v1/reviews/action with advisor role returns 403."""
        transport = WebAPIMockTransport(role="advisor")
        _inject_mock_client(transport)

        resp = client.post(
            "/api/v1/reviews/action",
            json={"reviewId": "rev-001", "action": "approve"},
            headers={"Authorization": f"Bearer {VALID_TOKEN}"},
        )

        assert resp.status_code == 403
