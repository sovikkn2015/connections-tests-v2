"""
Onboarding Specialist — Tests (~20 tests).

Uses importlib pattern for module loading (prefix: onboarding_).
Covers: full happy path, KYC failure→REJECTED, sanctions hit→REJECTED,
compliance rejection, multi-session resume, 30-day abandonment,
invalid transitions, SHA-256 hashes.

No cross-module imports. No credentials. No LLM.
"""

from __future__ import annotations

import hashlib
import importlib
import re
import sys
import types
from datetime import datetime, timedelta, timezone

import pytest

# ── importlib pattern ────────────────────────────────────────────

def _load_module(name: str, file_name: str) -> types.ModuleType:
    """Load a module from the onboarding-specialist package using importlib."""
    import importlib.util
    import pathlib
    base = pathlib.Path(__file__).parent
    spec = importlib.util.spec_from_file_location(name, base / file_name)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

onboarding_models = _load_module("onboarding_models", "models.py")

# Rebuild Pydantic models after importlib loading (forward refs from __future__ annotations)
for _cls_name in dir(onboarding_models):
    _cls = getattr(onboarding_models, _cls_name)
    if isinstance(_cls, type) and hasattr(_cls, "model_rebuild") and hasattr(_cls, "__pydantic_generic_metadata__"):
        _cls.model_rebuild()

onboarding_wf = _load_module("onboarding_workflow", "workflow.py")

OnboardingState = onboarding_models.OnboardingState
OnboardingRequest = onboarding_models.OnboardingRequest
OnboardingSession = onboarding_models.OnboardingSession
KYCResult = onboarding_models.KYCResult
SanctionsResult = onboarding_models.SanctionsResult
RiskProfile = onboarding_models.RiskProfile
ComplianceReview = onboarding_models.ComplianceReview
OnboardingWorkflow = onboarding_wf.OnboardingWorkflow
ABANDONMENT_DAYS = onboarding_wf.ABANDONMENT_DAYS



# ── Fixtures ─────────────────────────────────────────────────────


@pytest.fixture
def wf() -> OnboardingWorkflow:
    """Fresh workflow per test."""
    return OnboardingWorkflow()


@pytest.fixture
def sample_request() -> OnboardingRequest:
    """Standard onboarding request."""
    return OnboardingRequest(
        client_name="Jane Smith",
        client_type="individual",
        advisor_id="advisor-001",
        firm_id="acme_wealth",
        jurisdiction="US",
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _passing_kyc() -> KYCResult:
    return KYCResult(verified=True, verified_at=_now_iso(), document_hash="a" * 64)


def _passing_sanctions() -> SanctionsResult:
    return SanctionsResult(clear=True, screened_at=_now_iso())


def _passing_risk() -> RiskProfile:
    return RiskProfile(risk_score=25, risk_category="low", factors=["stable_income"], profiled_at=_now_iso())


def _advance_to_compliance_review(wf, request):
    """Helper: advance session through full workflow to COMPLIANCE_REVIEW."""
    session = wf.start_onboarding(request)
    session = wf.collect_client_info(session.session_id, {"occupation": "engineer", "income": "100k+"})
    session = wf.submit_kyc(session.session_id, _passing_kyc())
    session = wf.screen_sanctions(session.session_id, _passing_sanctions())
    session = wf.profile_risk(session.session_id, _passing_risk())
    session = wf.open_account(session.session_id)
    session = wf.complete_docusign(session.session_id)
    return session


# ── Test 1: Start onboarding in INITIATED state ─────────────────


def test_onboarding_start_initiated(wf, sample_request):
    """New session starts in INITIATED state."""
    session = wf.start_onboarding(sample_request)
    assert session.state == OnboardingState.INITIATED
    assert session.client_name == "Jane Smith"
    assert session.advisor_id == "advisor-001"
    assert session.session_id is not None


# ── Test 2: Full happy path INITIATED → APPROVED ────────────────


def test_onboarding_full_happy_path(wf, sample_request):
    """Full workflow: INITIATED → ... → COMPLIANCE_REVIEW → APPROVED."""
    session = _advance_to_compliance_review(wf, sample_request)
    assert session.state == OnboardingState.COMPLIANCE_REVIEW

    session = wf.approve_onboarding(session.session_id, "compliance-officer-001")
    assert session.state == OnboardingState.APPROVED
    assert session.compliance_review is not None
    assert session.compliance_review.approved is True
    assert session.compliance_review.approval_token is not None


# ── Test 3: KYC failure → REJECTED ──────────────────────────────


def test_onboarding_kyc_failure_rejected(wf, sample_request):
    """KYC failure transitions to REJECTED."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "unknown"})
    assert session.state == OnboardingState.KYC_PENDING

    failed_kyc = KYCResult(verified=False, reason="Document mismatch", verified_at=_now_iso())
    session = wf.submit_kyc(session.session_id, failed_kyc)
    assert session.state == OnboardingState.REJECTED
    assert session.kyc_result.reason == "Document mismatch"


# ── Test 4: Sanctions hit → REJECTED ────────────────────────────


def test_onboarding_sanctions_hit_rejected(wf, sample_request):
    """Sanctions hit transitions to REJECTED."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "engineer"})
    session = wf.submit_kyc(session.session_id, _passing_kyc())
    assert session.state == OnboardingState.SANCTIONS_SCREENING

    hit_sanctions = SanctionsResult(clear=False, hits=["OFAC_SDN_MATCH"], screened_at=_now_iso())
    session = wf.screen_sanctions(session.session_id, hit_sanctions)
    assert session.state == OnboardingState.REJECTED
    assert "OFAC_SDN_MATCH" in session.sanctions_result.hits


# ── Test 5: Compliance rejection ─────────────────────────────────


def test_onboarding_compliance_rejection(wf, sample_request):
    """HITL compliance rejection transitions to REJECTED."""
    session = _advance_to_compliance_review(wf, sample_request)
    session = wf.reject_onboarding(session.session_id, "compliance-officer-001", "Incomplete documentation")
    assert session.state == OnboardingState.REJECTED
    assert session.compliance_review.approved is False
    assert session.compliance_review.reason == "Incomplete documentation"


# ── Test 6: Multi-session resume ─────────────────────────────────


def test_onboarding_multi_session_resume(wf, sample_request):
    """Session can be resumed across days (multi-session)."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "engineer"})
    assert session.state == OnboardingState.KYC_PENDING

    # Simulate resuming next day
    resumed = wf.resume_session(session.session_id)
    assert resumed.session_id == session.session_id
    assert resumed.state == OnboardingState.KYC_PENDING
    # last_activity_at should be updated
    assert resumed.last_activity_at >= session.last_activity_at


# ── Test 7: Cannot resume terminal session ───────────────────────


def test_onboarding_cannot_resume_terminal(wf, sample_request):
    """Cannot resume APPROVED session."""
    session = _advance_to_compliance_review(wf, sample_request)
    session = wf.approve_onboarding(session.session_id, "compliance-officer-001")
    assert session.state == OnboardingState.APPROVED

    with pytest.raises(ValueError, match="terminal"):
        wf.resume_session(session.session_id)



# ── Test 8: 30-day abandonment ───────────────────────────────────


def test_onboarding_30_day_abandonment(wf, sample_request):
    """Session inactive for >30 days transitions to ABANDONED."""
    session = wf.start_onboarding(sample_request)

    past = datetime.now(timezone.utc) - timedelta(days=31)
    session_updated = session.model_copy(update={"last_activity_at": past.isoformat()})
    wf._sessions[session.session_id] = session_updated

    session = wf.check_abandonment(session.session_id)
    assert session.state == OnboardingState.ABANDONED


# ── Test 9: No abandonment before 30 days ────────────────────────


def test_onboarding_no_abandonment_before_30_days(wf, sample_request):
    """Session active within 30 days stays in current state."""
    session = wf.start_onboarding(sample_request)
    session = wf.check_abandonment(session.session_id)
    assert session.state == OnboardingState.INITIATED


# ── Test 10: Abandonment skips terminal states ───────────────────


def test_onboarding_abandonment_skips_terminal(wf, sample_request):
    """Abandonment check on APPROVED session is a no-op."""
    session = _advance_to_compliance_review(wf, sample_request)
    session = wf.approve_onboarding(session.session_id, "co-001")

    past = datetime.now(timezone.utc) - timedelta(days=60)
    session_updated = session.model_copy(update={"last_activity_at": past.isoformat()})
    wf._sessions[session.session_id] = session_updated

    session = wf.check_abandonment(session.session_id)
    assert session.state == OnboardingState.APPROVED


# ── Test 11: Invalid transition INITIATED → APPROVED ─────────────


def test_onboarding_invalid_transition_initiated_to_approved(wf, sample_request):
    """Cannot jump from INITIATED to APPROVED."""
    session = wf.start_onboarding(sample_request)
    with pytest.raises(ValueError, match="Invalid transition"):
        wf.approve_onboarding(session.session_id, "co-001")


# ── Test 12: Invalid transition from REJECTED ────────────────────


def test_onboarding_invalid_transition_from_rejected(wf, sample_request):
    """REJECTED is terminal — no transitions out."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "unknown"})
    failed_kyc = KYCResult(verified=False, reason="Fraud", verified_at=_now_iso())
    session = wf.submit_kyc(session.session_id, failed_kyc)
    assert session.state == OnboardingState.REJECTED

    with pytest.raises(ValueError, match="Invalid transition"):
        wf.collect_client_info(session.session_id, {"occupation": "engineer"})


# ── Test 13: SHA-256 approval token format ───────────────────────


def test_onboarding_sha256_approval_token(wf, sample_request):
    """Approval token is valid 64-char SHA-256 hex."""
    session = _advance_to_compliance_review(wf, sample_request)
    session = wf.approve_onboarding(session.session_id, "co-001")

    token = session.compliance_review.approval_token
    assert len(token) == 64
    assert re.match(r"^[a-f0-9]{64}$", token)


# ── Test 14: SHA-256 token matches manual computation ────────────


def test_onboarding_sha256_token_matches_manual():
    """Token matches manual SHA-256 computation."""
    sid = "test-session"
    rid = "test-reviewer"
    ts = "2024-01-01T00:00:00Z"

    expected = hashlib.sha256(f"{sid}{rid}{ts}".encode("utf-8")).hexdigest()
    actual = OnboardingWorkflow.generate_approval_token(sid, rid, ts)
    assert actual == expected


# ── Test 15: Get session by ID ───────────────────────────────────


def test_onboarding_get_session(wf, sample_request):
    """Get session by ID returns the session."""
    session = wf.start_onboarding(sample_request)
    fetched = wf.get_session(session.session_id)
    assert fetched is not None
    assert fetched.session_id == session.session_id


# ── Test 16: Get session not found ───────────────────────────────


def test_onboarding_get_session_not_found(wf):
    """Get non-existent session returns None."""
    assert wf.get_session("nonexistent-id") is None


# ── Test 17: Session not found raises ValueError ─────────────────


def test_onboarding_session_not_found_raises(wf):
    """Operations on non-existent session raise ValueError."""
    with pytest.raises(ValueError, match="Session not found"):
        wf.collect_client_info("nonexistent", {"data": "test"})


# ── Test 18: Account ID generated on open_account ────────────────


def test_onboarding_account_id_generated(wf, sample_request):
    """open_account generates an account ID."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "engineer"})
    session = wf.submit_kyc(session.session_id, _passing_kyc())
    session = wf.screen_sanctions(session.session_id, _passing_sanctions())
    session = wf.profile_risk(session.session_id, _passing_risk())
    session = wf.open_account(session.session_id)

    assert session.account_id is not None
    assert session.account_id.startswith("ACCT-")


# ── Test 19: ABANDONED is terminal ───────────────────────────────


def test_onboarding_abandoned_is_terminal(wf, sample_request):
    """ABANDONED is terminal — no transitions out."""
    session = wf.start_onboarding(sample_request)

    past = datetime.now(timezone.utc) - timedelta(days=31)
    session_updated = session.model_copy(update={"last_activity_at": past.isoformat()})
    wf._sessions[session.session_id] = session_updated

    session = wf.check_abandonment(session.session_id)
    assert session.state == OnboardingState.ABANDONED

    with pytest.raises(ValueError, match="terminal"):
        wf.resume_session(session.session_id)


# ── Test 20: Sanctions lists checked ─────────────────────────────


def test_onboarding_sanctions_lists_checked(wf, sample_request):
    """Sanctions result includes standard lists."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "engineer"})
    session = wf.submit_kyc(session.session_id, _passing_kyc())

    sanctions = _passing_sanctions()
    session = wf.screen_sanctions(session.session_id, sanctions)
    assert "OFAC_SDN" in session.sanctions_result.lists_checked
    assert "UN_SANCTIONS" in session.sanctions_result.lists_checked


# ── Test 21: Risk profile stored ─────────────────────────────────


def test_onboarding_risk_profile_stored(wf, sample_request):
    """Risk profile is stored on session."""
    session = wf.start_onboarding(sample_request)
    session = wf.collect_client_info(session.session_id, {"occupation": "engineer"})
    session = wf.submit_kyc(session.session_id, _passing_kyc())
    session = wf.screen_sanctions(session.session_id, _passing_sanctions())
    session = wf.profile_risk(session.session_id, _passing_risk())

    assert session.risk_profile is not None
    assert session.risk_profile.risk_category == "low"
    assert session.risk_profile.risk_score == 25


# ═══════════════════════════════════════════════════════════════════
# FastAPI endpoint tests
# ═══════════════════════════════════════════════════════════════════

onboarding_app = _load_module("onboarding_app", "app.py")
create_app = onboarding_app.create_app

from fastapi.testclient import TestClient


@pytest.fixture
def client() -> TestClient:
    """FastAPI test client."""
    app = create_app()
    return TestClient(app)


def test_onboarding_health_endpoint(client):
    """GET /health returns ok."""
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["module"] == "onboarding-specialist"


def test_onboarding_start_endpoint(client):
    """POST /onboarding/start returns session in INITIATED."""
    resp = client.post("/onboarding/start", json={
        "client_name": "Jane Smith",
        "advisor_id": "advisor-001",
        "firm_id": "acme_wealth",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "INITIATED"
    assert body["client_name"] == "Jane Smith"


def test_onboarding_get_session_endpoint(client):
    """GET /onboarding/{id} returns the session."""
    start_resp = client.post("/onboarding/start", json={
        "client_name": "Test Client",
        "advisor_id": "advisor-001",
        "firm_id": "acme_wealth",
    })
    session_id = start_resp.json()["session_id"]

    resp = client.get(f"/onboarding/{session_id}")
    assert resp.status_code == 200
    assert resp.json()["session_id"] == session_id


def test_onboarding_get_session_not_found_endpoint(client):
    """GET /onboarding/{id} returns 404 for non-existent session."""
    resp = client.get("/onboarding/nonexistent-id")
    assert resp.status_code == 404
