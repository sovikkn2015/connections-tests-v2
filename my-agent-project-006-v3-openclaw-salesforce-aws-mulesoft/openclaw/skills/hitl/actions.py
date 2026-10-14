"""hitl.run — mint and verify approval tokens for the HITL gate.

Two public entry points:

  - `mint(ApprovalMintInput)` — called when the action_specialist shows the
    ActionPlan to the RM. Returns a token + exp for the UI.
  - `verify(ApprovalVerifyInput)` — called when the user clicks Approve on
    the frontend. Returns a signed approval object on success; raises
    HITLError on ANY failure mode (tamper, expiry, replay, plan-mismatch).

`run()` is a thin dispatcher (mint or verify) used by the skill registry.

Steering rule 22 — audit logs carry only the SHA-256 fingerprint, never the
raw token. `mint` returns the raw token to the UI; every internal log hashes
it first.

Replay protection: the TokenStore holds fingerprint -> exp. Verify consumes
the fingerprint atomically; a second verify with the same token raises
HITLError(kind="replay").
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field

from ..audit_logging.actions import Action as AuditAction
from ..audit_logging.actions import AuditInput
from ..audit_logging.actions import run as audit_run
from .._mcp_client import MCPClient, get_shared_mock_client
from ._tokens import (
    TokenStore,
    VerifiedClaims,
    compute_plan_hash,
    get_default_store,
    mint_token,
    verify_token,
)


class HITLError(Exception):
    """Approval-flow error surfaced to the caller. Do not catch-and-ignore.

    Attributes:
        kind: one of 'tamper' | 'expired' | 'plan_mismatch' | 'user_mismatch'
              | 'replay' | 'malformed' | 'signing_missing'.
    """

    def __init__(self, *, kind: str, reason: str) -> None:
        self.kind = kind
        self.reason = reason
        super().__init__(f"hitl_error kind={kind} reason={reason}")


class ApprovalMintInput(BaseModel):
    """Input for minting a fresh approval token.

    `action_plan` is the canonical plan the token will be bound to. Its
    SHA-256 becomes the `plan_hash` claim; verify requires the same dict
    to rehydrate the same hash.
    """

    action_plan: Dict[str, Any] = Field(..., description="Canonical ActionPlan")
    user_id: str = Field(..., min_length=1, description="RM's principal_id")
    ttl_seconds: int = Field(300, ge=30, le=3600)

    # For audit linkage
    principal_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    model_config = {"frozen": True}


class ApprovalMintOutput(BaseModel):
    """Returned to the UI only; never logged raw."""

    token: str = Field(..., min_length=1, description="Raw token for UI. DO NOT LOG.")
    plan_hash: str = Field(..., min_length=16)
    expires_at: datetime
    audit_row_id: Optional[str] = None

    model_config = {"frozen": True}


class ApprovalVerifyInput(BaseModel):
    """Input when the RM clicks Approve in the HITL UI."""

    token: str = Field(..., min_length=1)
    action_plan: Dict[str, Any] = Field(
        ..., description="SAME plan the token was minted for (rebinding check)"
    )
    expected_user_id: Optional[str] = Field(
        None,
        description="When set, token's user_id claim must match (defense in depth).",
    )

    # For audit linkage
    principal_id: str = Field(..., min_length=1)
    agent_id: str = Field(..., min_length=1)
    session_id: str = Field(..., min_length=1)
    correlation_id: str = Field(..., min_length=1)

    model_config = {"frozen": True}


class ApprovalVerifyOutput(BaseModel):
    """Signed approval object passed to the action_specialist on success."""

    approved: bool
    user_id: str
    plan_hash: str
    approved_at: datetime
    token_fingerprint: str = Field(
        ..., description="SHA-256 fingerprint; safe to log (steering rule 22)."
    )
    audit_row_id: str

    model_config = {"frozen": True}


async def mint(
    payload: ApprovalMintInput,
    *,
    mcp: Optional[MCPClient] = None,
) -> ApprovalMintOutput:
    """Mint a fresh token + write an audit row recording the mint attempt."""
    plan_hash = compute_plan_hash(payload.action_plan)
    try:
        token, exp = mint_token(
            plan_hash=plan_hash,
            user_id=payload.user_id,
            ttl_seconds=payload.ttl_seconds,
        )
    except RuntimeError as exc:
        raise HITLError(kind="signing_missing", reason=str(exc))

    client = mcp or get_shared_mock_client()
    audit = await audit_run(
        AuditInput(
            action=AuditAction.DUAL_AUTH_REQUESTED,
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            gate_trace=[
                {"gate": "hitl_mint", "outcome": "ok", "plan_hash": plan_hash[:16]}
            ],
            payload={"ttl_seconds": payload.ttl_seconds, "user_id": payload.user_id},
        ),
        mcp=client,
    )

    return ApprovalMintOutput(
        token=token,
        plan_hash=plan_hash,
        expires_at=datetime.fromtimestamp(exp, tz=timezone.utc),
        audit_row_id=audit.audit_row_id,
    )


async def verify(
    payload: ApprovalVerifyInput,
    *,
    mcp: Optional[MCPClient] = None,
    store: Optional[TokenStore] = None,
) -> ApprovalVerifyOutput:
    """Verify a token; consume it (single-use); write HITL_APPROVED audit.

    Raises:
        HITLError: on any failure. Callers treat this as a hard stop.
    """
    token_store = store or get_default_store()
    expected_hash = compute_plan_hash(payload.action_plan)

    try:
        claims: VerifiedClaims = verify_token(
            payload.token,
            expected_plan_hash=expected_hash,
            expected_user_id=payload.expected_user_id,
        )
    except ValueError as exc:
        # Map reason -> kind for structured consumers.
        reason = str(exc)
        kind = (
            "expired"
            if "expired" in reason
            else "tamper"
            if "signature" in reason
            else "plan_mismatch"
            if "plan_hash" in reason
            else "user_mismatch"
            if "user_id mismatch" in reason
            else "malformed"
        )
        # Write audit row recording the rejection (gate fired).
        client = mcp or get_shared_mock_client()
        await audit_run(
            AuditInput(
                action=AuditAction.HITL_REJECTED,
                principal_id=payload.principal_id,
                agent_id=payload.agent_id,
                session_id=payload.session_id,
                correlation_id=payload.correlation_id,
                approval_token=payload.token,
                gate_trace=[
                    {"gate": "hitl_verify", "outcome": "rejected", "kind": kind}
                ],
                payload={"reason": reason[:120]},
            ),
            mcp=client,
        )
        raise HITLError(kind=kind, reason=reason)

    # Replay check
    if await token_store.is_consumed(claims.fingerprint):
        client = mcp or get_shared_mock_client()
        await audit_run(
            AuditInput(
                action=AuditAction.HITL_REJECTED,
                principal_id=payload.principal_id,
                agent_id=payload.agent_id,
                session_id=payload.session_id,
                correlation_id=payload.correlation_id,
                approval_token=payload.token,
                gate_trace=[
                    {"gate": "hitl_verify", "outcome": "replay", "kind": "replay"}
                ],
            ),
            mcp=client,
        )
        raise HITLError(kind="replay", reason="token already consumed")

    await token_store.consume(claims.fingerprint, claims.exp)

    client = mcp or get_shared_mock_client()
    audit = await audit_run(
        AuditInput(
            action=AuditAction.HITL_APPROVED,
            principal_id=payload.principal_id,
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            correlation_id=payload.correlation_id,
            approver_id=claims.user_id,
            approval_token=payload.token,
            gate_trace=[
                {
                    "gate": "hitl_verify",
                    "outcome": "approved",
                    "plan_hash": claims.plan_hash[:16],
                }
            ],
        ),
        mcp=client,
    )

    return ApprovalVerifyOutput(
        approved=True,
        user_id=claims.user_id,
        plan_hash=claims.plan_hash,
        approved_at=datetime.now(timezone.utc),
        token_fingerprint=claims.fingerprint,
        audit_row_id=audit.audit_row_id,
    )


async def run(
    payload: Any, *, mcp: Optional[MCPClient] = None
) -> Any:
    """Dispatcher: routes to mint() or verify() based on input type.

    Exists so the skill registry can call `skill.run(input)` uniformly.
    """
    if isinstance(payload, ApprovalMintInput):
        return await mint(payload, mcp=mcp)
    if isinstance(payload, ApprovalVerifyInput):
        return await verify(payload, mcp=mcp)
    raise TypeError(
        "hitl.run expected ApprovalMintInput or ApprovalVerifyInput, "
        f"got {type(payload).__name__}"
    )
