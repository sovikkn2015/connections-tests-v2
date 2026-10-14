"""
M8 Pipeline Engine -- HITL gate primitives.

- HMAC-SHA-256 approval token derivation with Vault-resolved key (AC4.5)
- Role verification per gate (AC4.8)
- Timeout reaper helper (AC4.7)
- Key rotation via pod-restart re-fetch (AC4.12)

boto3 allowed here for AWS Secrets Manager resolution (AC13.3).
"""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Optional

from m8_pipeline_engine.models import HitlApproval, HitlGatePayload

try:
    import boto3
except Exception:  # pragma: no cover
    boto3 = None  # type: ignore[assignment]


_GATE_ROLES: dict[int, frozenset[str]] = {
    1: frozenset({"research_specialist", "supervising_advisor", "advisor"}),
    2: frozenset({"compliance_officer"}),
    3: frozenset({"supervising_advisor", "advisor"}),
}


def _verify_approver_role(gate_id: int, aid_claims: Any) -> bool:
    """Return True iff the approver's role matches the gate (AC4.8)."""
    if aid_claims is None:
        return False
    role_val: Any
    if hasattr(aid_claims, "role"):
        role_val = getattr(aid_claims, "role")
    elif isinstance(aid_claims, dict) and "role" in aid_claims:
        role_val = aid_claims["role"]
    else:
        return False
    role_str = (
        role_val.value if hasattr(role_val, "value") else str(role_val)
    )
    return role_str in _GATE_ROLES.get(gate_id, frozenset())


@lru_cache(maxsize=32)
def _resolve_hitl_hmac_key(vault_path: str) -> bytes:
    """Fetch HMAC key from AWS Secrets Manager (AC4.6, AC4.12).

    Cached for process lifetime -- pod restart re-fetches (rotation path).
    Test bypass: monkeypatch this function.
    """
    if not vault_path:
        raise RuntimeError("m8_hitl_key_unresolved")
    if boto3 is None:
        raise RuntimeError("m8_hitl_key_unresolved")
    try:
        client = boto3.client("secretsmanager")
        response = client.get_secret_value(SecretId=vault_path)
        raw = response.get("SecretBinary") or response.get("SecretString") or b""
        if isinstance(raw, str):
            raw = raw.encode("utf-8")
        if not raw:
            raise RuntimeError("m8_hitl_key_unresolved")
        return raw
    except Exception as exc:
        raise RuntimeError(f"m8_hitl_key_unresolved: {exc!r}")


def build_approval_token(
    key: bytes,
    *,
    gate_id: int,
    approver_aid_sub: str,
    approver_timestamp: datetime,
    thread_id: str,
) -> str:
    """HMAC-SHA-256 hex digest of ``f"{gate}|{sub}|{iso}|{thread}"`` (AC4.5)."""
    msg = (
        f"{gate_id}|{approver_aid_sub}|{approver_timestamp.isoformat()}|{thread_id}"
    ).encode("utf-8")
    return hmac.new(key, msg, hashlib.sha256).hexdigest()


def verify_approval_token(
    approval: HitlApproval,
    *,
    gate_id: int,
    thread_id: str,
    hmac_key: bytes,
    now: Optional[datetime] = None,
    ttl_seconds: int = 14400,
) -> Optional[str]:
    """Return None on valid approval; else a reason_code (AC4.10, AC4.11)."""
    if not hmac_key:
        return "m8_hitl_token_expired"
    if now is None:
        now = datetime.now(timezone.utc)
    ts = approval.approver_timestamp
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    skew = abs((now - ts).total_seconds())
    if skew > ttl_seconds:
        return "m8_hitl_token_expired"

    expected = build_approval_token(
        hmac_key,
        gate_id=gate_id,
        approver_aid_sub=approval.approver_aid_sub,
        approver_timestamp=approval.approver_timestamp,
        thread_id=thread_id,
    )
    if not hmac.compare_digest(expected, approval.approval_token):
        return "m8_hitl_denied"
    return None


def build_gate_payload(
    *,
    gate_id: int,
    pipeline_run_id: str,
    thread_id: str,
    summary: dict[str, Any],
    emitted_at: Optional[datetime] = None,
) -> HitlGatePayload:
    """Construct the HitlGatePayload persisted during interrupt() (AC4.2)."""
    stage_map: dict[int, int] = {1: 7, 2: 13, 3: 21}
    role_map: dict[int, str] = {
        1: "research_specialist_or_supervising_advisor",
        2: "compliance_officer",
        3: "supervising_advisor",
    }
    return HitlGatePayload(
        gate_id=gate_id,  # type: ignore[arg-type]
        pipeline_run_id=pipeline_run_id,
        thread_id=thread_id,
        stage_number=stage_map[gate_id],  # type: ignore[arg-type]
        approver_role_required=role_map[gate_id],
        summary=summary,
        emitted_at=emitted_at or datetime.now(timezone.utc),
    )


def reap_timed_out_threads(
    paused_threads: dict[str, datetime],
    *,
    now: Optional[datetime] = None,
    ttl_seconds: int = 14400,
) -> list[str]:
    """Return thread_ids whose HITL pause has exceeded ``ttl_seconds`` (AC4.7)."""
    if now is None:
        now = datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    result: list[str] = []
    for tid, paused_at in paused_threads.items():
        if paused_at.tzinfo is None:
            paused_at = paused_at.replace(tzinfo=timezone.utc)
        if (now - paused_at).total_seconds() > ttl_seconds:
            result.append(tid)
    return result


__all__ = [
    "build_gate_payload",
    "build_approval_token",
    "verify_approval_token",
    "reap_timed_out_threads",
    "_verify_approver_role",
    "_resolve_hitl_hmac_key",
]
