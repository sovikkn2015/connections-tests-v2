"""Dual authorization for high-notional MuleSoft actions.

Required for (v2 steering rule 5):
- Wire transfers > $100,000
- Trade orders (notional) > $500,000
- Account closures (always)

Rules (steering rules 6, 7):
- Second approver MUST be distinct from first approver
- Second approver MUST hold the Senior_Compliance_Approver permission set in SF

If no eligible second approver is available within the SLA window, the action
stays in IR_Pending_Approval__c with status = AWAITING_SECOND. The caller
(actions.py) handles the queue-vs-proceed decision.

No hardcoded signing key. HITL_SIGNING_KEY env var is populated from AWS
Secrets Manager on Lambda startup (or by the test harness). Missing key = fail
closed (per v2 steering rule 18).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
import time
from dataclasses import dataclass


WIRE_THRESHOLD_USD = 100_000.00
TRADE_NOTIONAL_THRESHOLD_USD = 500_000.00

_HITL_SIGNING_KEY_ENV = "HITL_SIGNING_KEY"


class SecondApproverIneligible(Exception):
    """Raised if candidate second approver is same as first approver (rule 6)."""


class SigningKeyMissing(RuntimeError):
    """Raised when HITL_SIGNING_KEY env var is not set. Fail closed, no default."""


@dataclass(frozen=True)
class DualAuthToken:
    """Signed, plan-bound combined approval from two distinct senior approvers."""

    first_approver_id: str
    second_approver_id: str
    approved_at: int
    expires_at: int
    plan_hash: str
    combined_signature: str


# ---------------------------------------------------------------------------
# Threshold logic
# ---------------------------------------------------------------------------


def threshold_requires_dual_auth(*, action_type: str, notional: float) -> bool:
    """Return True if the action notional triggers the dual-auth requirement.

    action_type values: wire, trade, rebalance, account_close
    """
    if action_type == "wire":
        return notional > WIRE_THRESHOLD_USD
    if action_type in {"trade", "rebalance"}:
        return notional > TRADE_NOTIONAL_THRESHOLD_USD
    if action_type == "account_close":
        return True
    return False


# ---------------------------------------------------------------------------
# Injectable approver lookup + channel prompt
# ---------------------------------------------------------------------------


def _default_find_eligible_second_approver(first_approver_id: str) -> str | None:
    """Default stub. Production queries SF User with Senior_Compliance_Approver perm set."""
    raise NotImplementedError(
        "Second-approver lookup not wired. Set dual_auth.find_eligible = <callable>."
    )


def _default_prompt_second_approver(
    approver_id: str, plan_summary: str, plan_hash: str, timeout_seconds: int,
) -> dict:
    """Default stub. Production sends Slack/Teams/email ping to the senior approver."""
    raise NotImplementedError(
        "Second-approver channel not wired. Set dual_auth.prompt_second_approver = <callable>."
    )


find_eligible = _default_find_eligible_second_approver
prompt_second_approver = _default_prompt_second_approver


# ---------------------------------------------------------------------------
# Signing
# ---------------------------------------------------------------------------


def _get_signing_key() -> bytes:
    key = os.environ.get(_HITL_SIGNING_KEY_ENV)
    if not key:
        raise SigningKeyMissing(
            f"Environment variable {_HITL_SIGNING_KEY_ENV} is not set. "
            "Dual-auth token signing cannot proceed without a key from Secrets Manager."
        )
    return key.encode()


def _sign_combined(
    first: str, second: str, plan_hash: str, approved_at: int, expires_at: int,
) -> str:
    msg = f"{first}|{second}|{plan_hash}|{approved_at}|{expires_at}".encode()
    mac = hmac.new(_get_signing_key(), msg, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac).decode().rstrip("=")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def request_second_approval(
    *,
    first_approver_id: str,
    plan_hash: str,
    plan_summary: str = "",
    timeout_seconds: int = 3600,
) -> DualAuthToken | None:
    """Route to an eligible Senior_Compliance_Approver.

    Returns DualAuthToken on approval, None if:
    - No eligible second approver available, OR
    - Second approver does not respond within timeout_seconds.

    Raises:
        SecondApproverIneligible if lookup returned the same user as first approver.
        SigningKeyMissing if HITL_SIGNING_KEY env var unset.
    """
    candidate = find_eligible(first_approver_id)
    if candidate is None:
        return None

    if candidate == first_approver_id:
        raise SecondApproverIneligible(
            f"Second approver {candidate} is the same as first approver - rule 6 violation"
        )

    response = prompt_second_approver(candidate, plan_summary, plan_hash, timeout_seconds)
    decision = response.get("decision")

    if decision != "APPROVED":
        return None

    now = int(time.time())
    expires = now + timeout_seconds
    return DualAuthToken(
        first_approver_id=first_approver_id,
        second_approver_id=candidate,
        approved_at=now,
        expires_at=expires,
        plan_hash=plan_hash,
        combined_signature=_sign_combined(first_approver_id, candidate, plan_hash, now, expires),
    )


def verify_dual_auth_token(token: DualAuthToken, plan_hash: str) -> bool:
    """Verify: distinct approvers, matches plan_hash, not expired, signature valid."""
    if token.first_approver_id == token.second_approver_id:
        return False
    if token.plan_hash != plan_hash:
        return False
    if int(time.time()) > token.expires_at:
        return False
    expected = _sign_combined(
        token.first_approver_id, token.second_approver_id, token.plan_hash,
        token.approved_at, token.expires_at,
    )
    return hmac.compare_digest(token.combined_signature, expected)
