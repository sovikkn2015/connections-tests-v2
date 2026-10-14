"""
M1 Agent Identity Service — Integration Tests.

Tests cover:
  1. Issue AID for Tier 4 RIA advisor (human)
  2. Issue AID for agent (research specialist) with authority_scope
  3. Issue AID for Tier 3 BD advisor with LEI
  4. Verify valid AID
  5. Verify revoked AID (should fail)
  6. Verify garbage token (should fail)
  7. Agent without authority_scope (should fail validation)
  8. AID hash is 64-char SHA-256
  9. Cache hit on second verify

No cross-module imports. Tests use M1 internals only.
"""

from __future__ import annotations

import re

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

from models import (
    ActorType,
    Archetype,
    Role,
    AIDClaims,
    IssueAIDRequest,
    VerifyAIDRequest,
    RevokeAIDRequest,
)
from aid_service import AIDService, AIDRegistry, KeyProvider


# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture(scope="module")
def rsa_keys() -> tuple[str, str]:
    """Generate RSA key pair for tests. Dev only — production uses KMS/Vault."""
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = (
        private_key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode("utf-8")
    )
    return private_pem, public_pem


@pytest.fixture
def service(rsa_keys: tuple[str, str]) -> AIDService:
    """Fresh AIDService per test with clean registry and cache."""
    private_pem, public_pem = rsa_keys
    key_provider = KeyProvider(private_pem, public_pem)
    registry = AIDRegistry()
    return AIDService(key_provider, registry, cache_ttl_seconds=60)


# ── Test 1: Issue AID for Tier 4 RIA advisor ────────────────────


def test_issue_tier4_ria_advisor(service: AIDService):
    """Tier 4 RIA advisor — human, fiduciary, no LEI required."""
    request = IssueAIDRequest(
        actor_type=ActorType.human,
        display_name="Sarah Chen",
        firm_id="acme_wealth_management",
        crd_number="123456",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        jurisdiction="US",
        authority_scope=["client.read", "portfolio.read", "research.read"],
        authority_excludes=["order.submit"],
        client_scope=["C-12345", "C-67890"],
        ttl_hours=8,
    )
    response = service.issue(request)

    assert response.aid_id is not None
    assert response.token is not None
    assert len(response.token) > 100  # JWT is substantial
    assert response.claims.actor_type == ActorType.human
    assert response.claims.archetype == Archetype.tier4_independent_ria
    assert response.claims.role == Role.advisor
    assert response.claims.crd_number == "123456"
    assert response.claims.lei is None  # LEI not required for RIA
    assert response.claims.firm_id == "acme_wealth_management"
    assert "client.read" in response.claims.authority_scope
    assert "order.submit" in response.claims.authority_excludes
    assert response.claims.client_scope == ["C-12345", "C-67890"]


# ── Test 2: Issue AID for agent (research specialist) ───────────


def test_issue_agent_research_specialist(service: AIDService):
    """Agent specialist — MUST have authority_scope (Rule 5)."""
    request = IssueAIDRequest(
        actor_type=ActorType.agent,
        display_name="Research Specialist Agent",
        firm_id="acme_wealth_management",
        archetype=Archetype.tier4_independent_ria,
        role=Role.agent_research,
        jurisdiction="US",
        authority_scope=[
            "research.read",
            "research.generate",
            "sec_edgar.read",
            "market_data.read",
        ],
        authority_excludes=["order.submit", "client.write", "portfolio.write"],
        ttl_hours=24,
    )
    response = service.issue(request)

    assert response.aid_id is not None
    assert response.claims.actor_type == ActorType.agent
    assert response.claims.role == Role.agent_research
    assert len(response.claims.authority_scope) == 4
    assert "research.generate" in response.claims.authority_scope
    assert "order.submit" in response.claims.authority_excludes


# ── Test 3: Issue AID for Tier 3 BD advisor with LEI ────────────


def test_issue_tier3_bd_advisor_with_lei(service: AIDService):
    """Tier 3 BD — has LEI, CRD, Reg BI applies."""
    request = IssueAIDRequest(
        actor_type=ActorType.human,
        display_name="James Rodriguez",
        firm_id="national_financial_partners",
        lei="5493001KJTIIGC8Y1R12",
        crd_number="789012",
        archetype=Archetype.tier3_broker_dealer,
        role=Role.advisor,
        jurisdiction="US",
        authority_scope=[
            "client.read",
            "portfolio.read",
            "order.draft",
            "order.submit",
        ],
        client_scope=["C-11111", "C-22222", "C-33333"],
        ttl_hours=8,
    )
    response = service.issue(request)

    assert response.claims.lei == "5493001KJTIIGC8Y1R12"
    assert response.claims.crd_number == "789012"
    assert response.claims.archetype == Archetype.tier3_broker_dealer
    assert "order.submit" in response.claims.authority_scope


# ── Test 4: Verify valid AID ────────────────────────────────────


def test_verify_valid_aid(service: AIDService):
    """Issue then verify — should return valid=True with claims."""
    issue_req = IssueAIDRequest(
        actor_type=ActorType.human,
        display_name="Sarah Chen",
        firm_id="acme_wealth_management",
        crd_number="123456",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        authority_scope=["client.read", "portfolio.read"],
    )
    issued = service.issue(issue_req)
    result = service.verify(issued.token)

    assert result.valid is True
    assert result.aid_id == issued.aid_id
    assert result.claims is not None
    assert result.claims.display_name == "Sarah Chen"
    assert result.claims.archetype == Archetype.tier4_independent_ria
    assert result.status.value == "active"
    assert result.cached is False  # First verify — not cached


# ── Test 5: Verify revoked AID (should fail) ────────────────────


def test_verify_revoked_aid_fails(service: AIDService):
    """Revoked AID must be rejected immediately (Rule 2: fail-closed)."""
    issue_req = IssueAIDRequest(
        actor_type=ActorType.human,
        display_name="Terminated Advisor",
        firm_id="acme_wealth_management",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        authority_scope=["client.read"],
    )
    issued = service.issue(issue_req)

    # Revoke
    revoke_req = RevokeAIDRequest(
        aid_id=issued.aid_id, reason="Employment terminated"
    )
    revoke_resp = service.revoke(revoke_req, revoked_by="compliance@acme.com")
    assert revoke_resp.status.value == "revoked"

    # Verify should fail
    result = service.verify(issued.token)
    assert result.valid is False
    assert result.reason == "Token revoked"
    assert result.status.value == "revoked"


# ── Test 6: Verify garbage token (should fail) ──────────────────


def test_verify_garbage_token_fails(service: AIDService):
    """Random string should fail gracefully, not throw."""
    result = service.verify("this.is.not.a.jwt")
    assert result.valid is False
    assert result.reason is not None
    assert "Invalid token" in result.reason


# ── Test 7: Agent without authority_scope (should fail) ─────────


def test_agent_without_authority_scope_fails():
    """Zero-scope agents are not permitted (Rule 5)."""
    with pytest.raises(ValueError, match="authority_scope"):
        AIDClaims(
            actor_type=ActorType.agent,
            display_name="Bad Agent",
            firm_id="test_firm",
            archetype=Archetype.tier4_independent_ria,
            role=Role.agent_research,
            authority_scope=[],  # Empty — should fail
        )


# ── Test 8: AID hash is 64-char SHA-256 ─────────────────────────


def test_aid_hash_is_sha256(service: AIDService):
    """hash_aid() returns 64-char lowercase hex (SHA-256) for M10 audit."""
    issue_req = IssueAIDRequest(
        actor_type=ActorType.human,
        display_name="Hash Test",
        firm_id="test_firm",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        authority_scope=["client.read"],
    )
    issued = service.issue(issue_req)
    hashed = AIDService.hash_aid(issued.aid_id)

    assert len(hashed) == 64
    assert re.match(r"^[a-f0-9]{64}$", hashed)
    # Same input produces same hash (deterministic)
    assert AIDService.hash_aid(issued.aid_id) == hashed
    # Different input produces different hash
    assert AIDService.hash_aid("different-id") != hashed


# ── Test 9: Cache hit on second verify ───────────────────────────


def test_verify_cache_hit(service: AIDService):
    """Second verify of same token should come from cache."""
    issue_req = IssueAIDRequest(
        actor_type=ActorType.human,
        display_name="Cache Test",
        firm_id="test_firm",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        authority_scope=["client.read"],
    )
    issued = service.issue(issue_req)

    # First verify — not cached
    result1 = service.verify(issued.token)
    assert result1.valid is True
    assert result1.cached is False

    # Second verify — should be cached
    result2 = service.verify(issued.token)
    assert result2.valid is True
    assert result2.cached is True
    assert result2.aid_id == result1.aid_id
    assert result2.claims.display_name == "Cache Test"


# ═══════════════════════════════════════════════════════════════════
# BLOCKER 10: FastAPI endpoint tests via TestClient
# ═══════════════════════════════════════════════════════════════════

from fastapi.testclient import TestClient
from app import create_app


@pytest.fixture(scope="module")
def fastapi_client(rsa_keys: tuple[str, str]) -> TestClient:
    """Create a TestClient for the M1 FastAPI app."""
    private_pem, public_pem = rsa_keys
    app = create_app(private_key=private_pem, public_key=public_pem)
    return TestClient(app)


# ── Test: POST /aid/issue returns 200 with valid AID ────────────


def test_fastapi_issue_returns_200(fastapi_client: TestClient):
    """POST /aid/issue returns 200 with a valid AID token."""
    resp = fastapi_client.post("/aid/issue", json={
        "actor_type": "human",
        "display_name": "FastAPI Test Advisor",
        "firm_id": "test_firm",
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "authority_scope": ["client.read", "portfolio.read"],
        "ttl_hours": 8,
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["aid_id"]
    assert body["token"]
    assert len(body["token"]) > 100
    assert body["claims"]["actor_type"] == "human"
    assert body["claims"]["archetype"] == "tier4_independent_ria"
    assert body["claims"]["role"] == "advisor"


# ── Test: POST /aid/verify returns valid=True for good token ─────


def test_fastapi_verify_valid_token(fastapi_client: TestClient):
    """POST /aid/verify returns valid=True for a freshly issued token."""
    # Issue first
    issue_resp = fastapi_client.post("/aid/issue", json={
        "actor_type": "human",
        "display_name": "Verify Test",
        "firm_id": "test_firm",
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "authority_scope": ["client.read"],
    })
    token = issue_resp.json()["token"]

    # Verify
    verify_resp = fastapi_client.post("/aid/verify", json={"token": token})

    assert verify_resp.status_code == 200
    body = verify_resp.json()
    assert body["valid"] is True
    assert body["aid_id"] is not None
    assert body["claims"]["display_name"] == "Verify Test"


# ── Test: POST /aid/verify returns valid=False for revoked token ─


def test_fastapi_verify_revoked_token(fastapi_client: TestClient):
    """POST /aid/verify returns valid=False after revocation."""
    # Issue
    issue_resp = fastapi_client.post("/aid/issue", json={
        "actor_type": "human",
        "display_name": "Revoke Target",
        "firm_id": "test_firm",
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "authority_scope": ["client.read"],
    })
    aid_id = issue_resp.json()["aid_id"]
    token = issue_resp.json()["token"]

    # Revoke
    revoke_resp = fastapi_client.post("/aid/revoke", json={
        "aid_id": aid_id,
        "reason": "Test revocation",
    })
    assert revoke_resp.status_code == 200

    # Verify — should be invalid
    verify_resp = fastapi_client.post("/aid/verify", json={"token": token})
    assert verify_resp.status_code == 200
    body = verify_resp.json()
    assert body["valid"] is False
    assert "revoked" in body.get("reason", "").lower()


# ── Test: POST /aid/revoke returns 200 ───────────────────────────


def test_fastapi_revoke_returns_200(fastapi_client: TestClient):
    """POST /aid/revoke returns 200 with revocation confirmation."""
    # Issue first
    issue_resp = fastapi_client.post("/aid/issue", json={
        "actor_type": "human",
        "display_name": "Revoke Test",
        "firm_id": "test_firm",
        "archetype": "tier4_independent_ria",
        "role": "advisor",
        "authority_scope": ["client.read"],
    })
    aid_id = issue_resp.json()["aid_id"]

    # Revoke
    resp = fastapi_client.post("/aid/revoke", json={
        "aid_id": aid_id,
        "reason": "Employment terminated",
    })

    assert resp.status_code == 200
    body = resp.json()
    assert body["aid_id"] == aid_id
    assert body["status"] == "revoked"
    assert body["revoked_at"] is not None


# ── Test: GET /health returns ok ─────────────────────────────────


def test_fastapi_health_returns_ok(fastapi_client: TestClient):
    """GET /health returns status ok."""
    resp = fastapi_client.get("/health")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "m1-identity"
