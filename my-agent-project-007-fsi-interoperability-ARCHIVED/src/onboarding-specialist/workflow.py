"""
Onboarding Specialist — Multi-session KYC workflow engine.

HITL mandatory at COMPLIANCE_REVIEW stage.
Sanctions screening deterministic (not LLM).
Multi-session: sessions persist across days.
30-day abandonment timeout.

No cross-module imports. M2/M4 checks via REST (not imported).
All compliance decisions deterministic — no LLM.

Backends:
  In-memory (default) for dev/test.
  DynamoDB for production (ONBOARD_STORE_BACKEND=dynamodb).
"""

import hashlib
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

try:
    from .models import (
        ComplianceReview,
        KYCResult,
        OnboardingRequest,
        OnboardingSession,
        OnboardingState,
        RiskProfile,
        SanctionsResult,
    )
except ImportError:
    import importlib.util
    import pathlib as _pathlib
    _models_path = _pathlib.Path(__file__).parent / "models.py"
    _spec = importlib.util.spec_from_file_location("onboarding_models_local", _models_path)
    _mod = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(_mod)
    ComplianceReview = _mod.ComplianceReview
    KYCResult = _mod.KYCResult
    OnboardingRequest = _mod.OnboardingRequest
    OnboardingSession = _mod.OnboardingSession
    OnboardingState = _mod.OnboardingState
    RiskProfile = _mod.RiskProfile
    SanctionsResult = _mod.SanctionsResult

logger = logging.getLogger("onboarding_specialist.workflow")

# 30-day abandonment timeout
ABANDONMENT_DAYS = 30

# Terminal states
TERMINAL_STATES = {OnboardingState.APPROVED, OnboardingState.REJECTED, OnboardingState.ABANDONED}

# Valid state transitions — strict enforcement
VALID_TRANSITIONS: dict[OnboardingState, list[OnboardingState]] = {
    OnboardingState.INITIATED: [OnboardingState.COLLECTING_INFO, OnboardingState.ABANDONED],
    OnboardingState.COLLECTING_INFO: [OnboardingState.KYC_PENDING, OnboardingState.ABANDONED],
    OnboardingState.KYC_PENDING: [OnboardingState.KYC_VERIFIED, OnboardingState.REJECTED, OnboardingState.ABANDONED],
    OnboardingState.KYC_VERIFIED: [OnboardingState.SANCTIONS_SCREENING, OnboardingState.ABANDONED],
    OnboardingState.SANCTIONS_SCREENING: [OnboardingState.SANCTIONS_CLEAR, OnboardingState.REJECTED, OnboardingState.ABANDONED],
    OnboardingState.SANCTIONS_CLEAR: [OnboardingState.RISK_PROFILING, OnboardingState.ABANDONED],
    OnboardingState.RISK_PROFILING: [OnboardingState.RISK_PROFILED, OnboardingState.ABANDONED],
    OnboardingState.RISK_PROFILED: [OnboardingState.ACCOUNT_OPENING, OnboardingState.ABANDONED],
    OnboardingState.ACCOUNT_OPENING: [OnboardingState.DOCUSIGN_PENDING, OnboardingState.ABANDONED],
    OnboardingState.DOCUSIGN_PENDING: [OnboardingState.DOCUSIGN_SIGNED, OnboardingState.ABANDONED],
    OnboardingState.DOCUSIGN_SIGNED: [OnboardingState.COMPLIANCE_REVIEW, OnboardingState.ABANDONED],
    OnboardingState.COMPLIANCE_REVIEW: [OnboardingState.APPROVED, OnboardingState.REJECTED, OnboardingState.ABANDONED],
    # Terminal states
    OnboardingState.APPROVED: [],
    OnboardingState.REJECTED: [],
    OnboardingState.ABANDONED: [],
}


# ── Session Store Backends ───────────────────────────────────────


class InMemorySessionStore:
    """In-memory session store. Default for dev/test."""

    def __init__(self) -> None:
        self._sessions: dict[str, OnboardingSession] = {}

    def put(self, session: OnboardingSession) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: str) -> Optional[OnboardingSession]:
        return self._sessions.get(session_id)


class DynamoDBSessionStore:
    """
    DynamoDB-backed session store for production.

    Activated when ONBOARD_STORE_BACKEND=dynamodb and ONBOARD_DYNAMODB_TABLE is set.
    Uses boto3 DynamoDB (put_item, get_item).
    Credentials from IAM role / env (Rule 20). No credentials in code.

    Falls back to in-memory on connection failure.
    """

    def __init__(self, table_name: str, dynamodb_client: Any = None) -> None:
        self._table_name = table_name
        if dynamodb_client is not None:
            self._client = dynamodb_client
        else:
            try:
                import boto3
            except ImportError:
                raise RuntimeError(
                    "boto3 is required for DynamoDB session store. "
                    "Install with: pip install boto3"
                )
            self._client = boto3.resource("dynamodb").Table(table_name)
        self._fallback: InMemorySessionStore | None = None
        logger.info("DynamoDBSessionStore initialized: table=%s", table_name)

    def _get_fallback(self) -> InMemorySessionStore:
        if self._fallback is None:
            self._fallback = InMemorySessionStore()
            logger.warning("DynamoDBSessionStore: activated in-memory fallback")
        return self._fallback

    def put(self, session: OnboardingSession) -> None:
        try:
            self._client.put_item(Item={
                "session_id": session.session_id,
                "session_json": session.model_dump_json(),
            })
        except Exception as exc:
            logger.error("DynamoDB put_item failed: %s. Using fallback.", exc)
            self._get_fallback().put(session)

    def get(self, session_id: str) -> Optional[OnboardingSession]:
        try:
            resp = self._client.get_item(Key={"session_id": session_id})
            item = resp.get("Item")
            if item is None:
                if self._fallback:
                    return self._fallback.get(session_id)
                return None
            return OnboardingSession.model_validate_json(item["session_json"])
        except Exception as exc:
            logger.error("DynamoDB get_item failed: %s. Using fallback.", exc)
            return self._get_fallback().get(session_id)


def create_session_store() -> InMemorySessionStore | DynamoDBSessionStore:
    """
    Factory: select session store backend based on env var.

    ONBOARD_STORE_BACKEND: "memory" (default) or "dynamodb"
    ONBOARD_DYNAMODB_TABLE: DynamoDB table name (required for dynamodb)
    """
    backend = os.environ.get("ONBOARD_STORE_BACKEND", "memory").lower()
    if backend == "dynamodb":
        table_name = os.environ.get("ONBOARD_DYNAMODB_TABLE")
        if not table_name:
            logger.warning(
                "ONBOARD_STORE_BACKEND=dynamodb but ONBOARD_DYNAMODB_TABLE not set. "
                "Falling back to in-memory session store."
            )
            return InMemorySessionStore()
        try:
            store = DynamoDBSessionStore(table_name=table_name)
            logger.info("Onboarding session store backend: dynamodb (table=%s)", table_name)
            return store
        except Exception as exc:
            logger.error(
                "Failed to initialize DynamoDB session store: %s. "
                "Falling back to in-memory.",
                exc,
            )
            return InMemorySessionStore()
    logger.info("Onboarding session store backend: memory")
    return InMemorySessionStore()



class OnboardingWorkflow:
    """
    Multi-session KYC workflow engine.

    In-memory store for dev/test. DynamoDB for production.
    Backend selected via ONBOARD_STORE_BACKEND env var (default: memory).
    No cross-module imports — M2/M4 compliance checks arrive as data.
    """

    def __init__(self, store: InMemorySessionStore | DynamoDBSessionStore | None = None) -> None:
        self._store = store or InMemorySessionStore()

    @property
    def _sessions(self) -> "dict[str, OnboardingSession]":
        """Backward-compatible access to underlying store dict (for tests)."""
        if isinstance(self._store, InMemorySessionStore):
            return self._store._sessions
        raise AttributeError("_sessions not available on non-memory backends")

    def _validate_transition(self, session: OnboardingSession, target: OnboardingState) -> None:
        """Validate state transition. Raises ValueError if invalid."""
        allowed = VALID_TRANSITIONS.get(session.state, [])
        if target not in allowed:
            raise ValueError(
                f"Invalid transition: {session.state.value} → {target.value}. "
                f"Allowed: {[s.value for s in allowed]}"
            )

    def _update_session(self, session: OnboardingSession, **kwargs) -> OnboardingSession:
        """Update session fields and persist."""
        now = datetime.now(timezone.utc).isoformat()
        updated = session.model_copy(update={**kwargs, "updated_at": now, "last_activity_at": now})
        self._store.put(updated)
        return updated

    # ── Start ────────────────────────────────────────────────────

    def start_onboarding(self, request: OnboardingRequest) -> OnboardingSession:
        """Start a new onboarding session in INITIATED state."""
        session = OnboardingSession(
            client_name=request.client_name,
            client_type=request.client_type,
            advisor_id=request.advisor_id,
            firm_id=request.firm_id,
            jurisdiction=request.jurisdiction,
            state=OnboardingState.INITIATED,
        )
        self._store.put(session)
        logger.info("Onboarding started: %s for %s", session.session_id, session.client_name)
        return session

    # ── Collect Info ─────────────────────────────────────────────

    def collect_client_info(self, session_id: str, client_info: dict) -> OnboardingSession:
        """
        Collect client information. INITIATED → COLLECTING_INFO → KYC_PENDING.
        """
        session = self._get_session_or_raise(session_id)
        self._validate_transition(session, OnboardingState.COLLECTING_INFO)

        session = self._update_session(
            session, state=OnboardingState.COLLECTING_INFO, client_info=client_info
        )

        # Auto-advance to KYC_PENDING
        self._validate_transition(session, OnboardingState.KYC_PENDING)
        session = self._update_session(session, state=OnboardingState.KYC_PENDING)
        logger.info("Session %s: client info collected, KYC pending", session_id)
        return session

    # ── KYC ──────────────────────────────────────────────────────

    def submit_kyc(self, session_id: str, kyc_result: KYCResult) -> OnboardingSession:
        """
        Submit KYC result. KYC_PENDING → KYC_VERIFIED or REJECTED.
        Deterministic — no LLM.
        """
        session = self._get_session_or_raise(session_id)

        if not kyc_result.verified:
            self._validate_transition(session, OnboardingState.REJECTED)
            session = self._update_session(
                session, state=OnboardingState.REJECTED, kyc_result=kyc_result
            )
            logger.info("Session %s: KYC FAILED → REJECTED: %s", session_id, kyc_result.reason)
            return session

        self._validate_transition(session, OnboardingState.KYC_VERIFIED)
        session = self._update_session(
            session, state=OnboardingState.KYC_VERIFIED, kyc_result=kyc_result
        )

        # Auto-advance to SANCTIONS_SCREENING
        self._validate_transition(session, OnboardingState.SANCTIONS_SCREENING)
        session = self._update_session(session, state=OnboardingState.SANCTIONS_SCREENING)
        logger.info("Session %s: KYC verified, sanctions screening", session_id)
        return session

    # ── Sanctions ────────────────────────────────────────────────

    def screen_sanctions(self, session_id: str, sanctions_result: SanctionsResult) -> OnboardingSession:
        """
        Screen sanctions. SANCTIONS_SCREENING → SANCTIONS_CLEAR or REJECTED.
        Deterministic — no LLM (Rule 14).
        """
        session = self._get_session_or_raise(session_id)

        if not sanctions_result.clear:
            self._validate_transition(session, OnboardingState.REJECTED)
            session = self._update_session(
                session, state=OnboardingState.REJECTED, sanctions_result=sanctions_result
            )
            logger.info("Session %s: sanctions HIT → REJECTED: %s", session_id, sanctions_result.hits)
            return session

        self._validate_transition(session, OnboardingState.SANCTIONS_CLEAR)
        session = self._update_session(
            session, state=OnboardingState.SANCTIONS_CLEAR, sanctions_result=sanctions_result
        )

        # Auto-advance to RISK_PROFILING
        self._validate_transition(session, OnboardingState.RISK_PROFILING)
        session = self._update_session(session, state=OnboardingState.RISK_PROFILING)
        logger.info("Session %s: sanctions clear, risk profiling", session_id)
        return session

    # ── Risk Profiling ───────────────────────────────────────────

    def profile_risk(self, session_id: str, risk_profile: RiskProfile) -> OnboardingSession:
        """
        Profile client risk. RISK_PROFILING → RISK_PROFILED → ACCOUNT_OPENING.
        Deterministic scoring.
        """
        session = self._get_session_or_raise(session_id)
        self._validate_transition(session, OnboardingState.RISK_PROFILED)

        session = self._update_session(
            session, state=OnboardingState.RISK_PROFILED, risk_profile=risk_profile
        )

        # Auto-advance to ACCOUNT_OPENING
        self._validate_transition(session, OnboardingState.ACCOUNT_OPENING)
        session = self._update_session(session, state=OnboardingState.ACCOUNT_OPENING)
        logger.info("Session %s: risk profiled (%s), account opening", session_id, risk_profile.risk_category)
        return session

    # ── Account Opening ──────────────────────────────────────────

    def open_account(self, session_id: str) -> OnboardingSession:
        """
        Open account. ACCOUNT_OPENING → DOCUSIGN_PENDING.
        """
        session = self._get_session_or_raise(session_id)
        self._validate_transition(session, OnboardingState.DOCUSIGN_PENDING)

        account_id = f"ACCT-{uuid.uuid4().hex[:8].upper()}"
        session = self._update_session(
            session, state=OnboardingState.DOCUSIGN_PENDING, account_id=account_id
        )
        logger.info("Session %s: account %s opened, DocuSign pending", session_id, account_id)
        return session

    # ── DocuSign ─────────────────────────────────────────────────

    def complete_docusign(self, session_id: str) -> OnboardingSession:
        """
        Complete DocuSign. DOCUSIGN_PENDING → DOCUSIGN_SIGNED → COMPLIANCE_REVIEW.
        """
        session = self._get_session_or_raise(session_id)
        self._validate_transition(session, OnboardingState.DOCUSIGN_SIGNED)

        session = self._update_session(session, state=OnboardingState.DOCUSIGN_SIGNED)

        # Auto-advance to COMPLIANCE_REVIEW (HITL mandatory here)
        self._validate_transition(session, OnboardingState.COMPLIANCE_REVIEW)
        session = self._update_session(session, state=OnboardingState.COMPLIANCE_REVIEW)
        logger.info("Session %s: DocuSign signed, awaiting HITL compliance review", session_id)
        return session

    # ── HITL Compliance Review ───────────────────────────────────

    @staticmethod
    def generate_approval_token(session_id: str, reviewer_id: str, timestamp: str) -> str:
        """Generate SHA-256 approval token: SHA-256(session_id + reviewer_id + timestamp)."""
        payload = f"{session_id}{reviewer_id}{timestamp}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def approve_onboarding(self, session_id: str, reviewer_id: str) -> OnboardingSession:
        """
        HITL approve onboarding. COMPLIANCE_REVIEW → APPROVED.
        Generates SHA-256 token.
        """
        session = self._get_session_or_raise(session_id)
        self._validate_transition(session, OnboardingState.APPROVED)

        now = datetime.now(timezone.utc).isoformat()
        token = self.generate_approval_token(session_id, reviewer_id, now)

        review = ComplianceReview(
            reviewer_id=reviewer_id,
            approved=True,
            approval_token=token,
            reviewed_at=now,
        )
        session = self._update_session(
            session, state=OnboardingState.APPROVED, compliance_review=review
        )
        logger.info("Session %s: APPROVED by %s", session_id, reviewer_id)
        return session

    def reject_onboarding(self, session_id: str, reviewer_id: str, reason: str) -> OnboardingSession:
        """
        HITL reject onboarding. COMPLIANCE_REVIEW → REJECTED.
        """
        session = self._get_session_or_raise(session_id)
        self._validate_transition(session, OnboardingState.REJECTED)

        now = datetime.now(timezone.utc).isoformat()
        review = ComplianceReview(
            reviewer_id=reviewer_id,
            approved=False,
            reason=reason,
            reviewed_at=now,
        )
        session = self._update_session(
            session, state=OnboardingState.REJECTED, compliance_review=review
        )
        logger.info("Session %s: REJECTED by %s: %s", session_id, reviewer_id, reason)
        return session

    # ── Abandonment ──────────────────────────────────────────────

    def check_abandonment(self, session_id: str) -> OnboardingSession:
        """
        Check 30-day abandonment timeout.
        If last activity > 30 days ago and not terminal, transitions to ABANDONED.
        """
        session = self._get_session_or_raise(session_id)

        if session.state in TERMINAL_STATES:
            return session

        last_activity = datetime.fromisoformat(session.last_activity_at)
        if last_activity.tzinfo is None:
            last_activity = last_activity.replace(tzinfo=timezone.utc)

        deadline = last_activity + timedelta(days=ABANDONMENT_DAYS)
        now = datetime.now(timezone.utc)

        if now > deadline:
            self._validate_transition(session, OnboardingState.ABANDONED)
            session = self._update_session(session, state=OnboardingState.ABANDONED)
            logger.warning("Session %s: ABANDONED after %d days", session_id, ABANDONMENT_DAYS)

        return session

    # ── Queries ──────────────────────────────────────────────────

    def get_session(self, session_id: str) -> Optional[OnboardingSession]:
        """Get session by ID. Returns None if not found."""
        return self._store.get(session_id)

    def resume_session(self, session_id: str) -> OnboardingSession:
        """
        Resume a session (multi-session support). Updates last_activity_at.
        Returns the session in its current state for continuation.
        """
        session = self._get_session_or_raise(session_id)

        if session.state in TERMINAL_STATES:
            raise ValueError(
                f"Cannot resume session {session_id}: state is {session.state.value} (terminal)"
            )

        now = datetime.now(timezone.utc).isoformat()
        session = session.model_copy(update={"last_activity_at": now, "updated_at": now})
        self._store.put(session)
        logger.info("Session %s: resumed at state %s", session_id, session.state.value)
        return session

    # ── Internal ─────────────────────────────────────────────────

    def _get_session_or_raise(self, session_id: str) -> OnboardingSession:
        """Get session or raise ValueError."""
        session = self._store.get(session_id)
        if session is None:
            raise ValueError(f"Session not found: {session_id}")
        return session
