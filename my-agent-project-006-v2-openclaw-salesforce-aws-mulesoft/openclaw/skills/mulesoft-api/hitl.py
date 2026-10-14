"""HITL (Human-In-The-Loop) approval gate for MuleSoft actions.

Every MuleSoft write action pauses here for explicit human approval. The frontend
HitlPanel, Slack, or Teams channel presents the action plan and returns one of
[approve, reject, edit, abstain].

Approval tokens are:
- Signed with HMAC-SHA256 using a secret held in AWS Secrets Manager.
- Bound to a specific plan_hash - token is invalidated if ActionPlan changes.
- Time-bound with a 5-min TTL so captured tokens cannot be replayed later.

v2 steering rule 2: every MuleSoft write requires a valid ApprovalToken.
v2 steering rule 18: secrets only in AWS Secrets Manager, zero credentials in git.
v2 steering rule 22: tokens NEVER logged in raw form - hash only.

Signing key:
- Production/sandbox: read from AWS Secrets Manager at runtime (env var HITL_SIGNING_KEY
  populated by Lambda startup or by test harness)
- No hardcoded fallback key. Calls fail loudly if the key is missing rather than
  silently using a known default (which would be a credential leak per rule 5).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass
from typing import Literal


ApprovalDecision = Literal["APPROVED", "REJECTED", "EDITED", "EXPIRED", "READ_ONLY"]

# 5 min TTL - short enough to block replay, long enough for a human to click a button.
DEFAULT_APPROVAL_TTL_SECONDS = 300

# The HMAC signing key lives in Secrets Manager; wired at runtime via env var.
_HITL_SIGNING_KEY_ENV = "HITL_SIGNING_KEY"


class ApprovalRejected(Exception):
    """Raised when user explicitly rejects the action plan."""


class ApprovalTimeout(Exception):
    """Raised when user does not respond within TTL."""


class SigningKeyMissing(RuntimeError):
    """Raised when HITL_SIGNING_KEY env var is not set. Fail closed, never use a default."""


@dataclass(frozen=True)
class ApprovalToken:
    """Signed, plan-bound approval for a single MuleSoft write.

    signature = HMAC_SHA256(signing_key, f"{approver_id}|{approved_at}|{expires_at}|{plan_hash}")
    """

    approver_id: str
    approved_at: int
    expires_at: int
    plan_hash: str
    signature: str

    @classmethod
    def read_only(cls) -> "ApprovalToken":
        """Sentinel token for read-only tool calls (get_order_status, get_settlement_status)."""
        return cls(
            approver_id="read-only",
            approved_at=0,
            expires_at=0,
            plan_hash="read-only",
            signature="read-only",
        )

    @property
    def is_read_only(self) -> bool:
        return self.approver_id == "read-only" and self.signature == "read-only"


# ---------------------------------------------------------------------------
# Injectable channel bridge (test harness swaps this for a deterministic stub)
# ---------------------------------------------------------------------------


def _default_channel_prompt(plan_summary: str, plan_hash: str, timeout_seconds: int) -> dict:
    """Default stub. Production wires this to OpenClaw Gateway WebSocket (stream='hitl').

    Must return a dict with keys:
        decision:    APPROVED | REJECTED | EXPIRED | EDITED
        approver_id: str (SF User Id)
        edited_plan: optional dict if decision == EDITED
    """
    raise NotImplementedError(
        "HITL channel not wired. Set hitl.channel_prompt = <callable>."
    )


channel_prompt = _default_channel_prompt


# ---------------------------------------------------------------------------
# Signing / verification
# ---------------------------------------------------------------------------


def _get_signing_key() -> bytes:
    """Load HMAC key from env (populated from Secrets Manager on Lambda startup).

    Raises SigningKeyMissing if not set. NO hardcoded fallback - that would be a
    credential in git per v2 steering rule 5.
    """
    key = os.environ.get(_HITL_SIGNING_KEY_ENV)
    if not key:
        raise SigningKeyMissing(
            f"Environment variable {_HITL_SIGNING_KEY_ENV} is not set. "
            "HITL token signing cannot proceed without a key from Secrets Manager."
        )
    return key.encode()


def _sign(approver_id: str, approved_at: int, expires_at: int, plan_hash: str) -> str:
    msg = f"{approver_id}|{approved_at}|{expires_at}|{plan_hash}".encode()
    mac = hmac.new(_get_signing_key(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


def _build_token(approver_id: str, plan_hash: str, ttl_seconds: int) -> ApprovalToken:
    now = int(time.time())
    expires = now + ttl_seconds
    return ApprovalToken(
        approver_id=approver_id,
        approved_at=now,
        expires_at=expires,
        plan_hash=plan_hash,
        signature=_sign(approver_id, now, expires, plan_hash),
    )


def verify_token(token: ApprovalToken, plan_hash: str) -> bool:
    """Verify HMAC signature AND plan_hash match AND not expired.

    Returns False for any mismatch. Does NOT raise - caller decides.
    """
    if token.is_read_only:
        # Read-only sentinel is NOT valid for writes.
        return False

    if token.plan_hash != plan_hash:
        return False

    if int(time.time()) > token.expires_at:
        return False

    expected_sig = _sign(token.approver_id, token.approved_at, token.expires_at, token.plan_hash)
    return hmac.compare_digest(token.signature, expected_sig)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def request_approval(
    plan_summary: str,
    plan_hash: str,
    timeout_seconds: int = DEFAULT_APPROVAL_TTL_SECONDS,
) -> ApprovalToken:
    """Prompt the user via their current channel and block until decision or timeout.

    Returns ApprovalToken on APPROVED.

    Raises:
        ApprovalRejected on REJECTED
        ApprovalTimeout on EXPIRED
        SigningKeyMissing if signing key env var unset
        RuntimeError on EDITED (upstream should rebuild the plan and re-request)
    """
    response = channel_prompt(plan_summary, plan_hash, timeout_seconds)
    decision = response.get("decision")
    approver_id = response.get("approver_id", "unknown")

    if decision == "APPROVED":
        return _build_token(
            approver_id=approver_id, plan_hash=plan_hash, ttl_seconds=timeout_seconds,
        )

    if decision == "REJECTED":
        raise ApprovalRejected(response.get("reason", "Rejected by user"))

    if decision == "EDITED":
        raise RuntimeError("Plan edited - upstream should rebuild and re-request approval")

    if decision == "EXPIRED":
        raise ApprovalTimeout(f"No response within {timeout_seconds}s")

    raise RuntimeError(f"Unknown HITL decision: {decision}")
