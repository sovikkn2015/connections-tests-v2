"""HMAC-SHA256 approval tokens for the HITL gate.

Token format (base64url-encoded envelope):

    payload = {
        "v": 1,
        "plan_hash": <sha256 of canonical ActionPlan JSON>,
        "user_id":   <principal_id of approver>,
        "iat":       <issued-at epoch seconds>,
        "exp":       <expiry epoch seconds>  # iat + 300 by default
    }
    token = base64url(payload) + "." + hex(hmac_sha256(key, payload_bytes))

Verification rules (fail-closed):
  - Signature must validate under the current HITL_SIGNING_KEY.
  - `exp` must be in the future.
  - `plan_hash` must equal the expected hash the caller provides (rebinding).
  - Token must NOT have been used before (`TokenStore.consume()`).

The TokenStore is an in-memory single-use registry. Production should swap
in a Redis-backed implementation via `replace_default_store()`; the interface
is async-safe and idempotent.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time as _time
from dataclasses import dataclass
from typing import Dict, Optional, Tuple


class TokenStore:
    """Async-safe in-memory store of consumed token fingerprints.

    Keys are HMAC-derived fingerprints (32 hex chars). Storing the raw token
    would violate steering rule 22.
    """

    def __init__(self) -> None:
        self._seen: Dict[str, float] = {}

    async def is_consumed(self, fingerprint: str) -> bool:
        now = _time.time()
        to_drop = [k for k, exp in self._seen.items() if exp < now]
        for k in to_drop:
            del self._seen[k]
        return fingerprint in self._seen

    async def consume(self, fingerprint: str, exp: float) -> None:
        self._seen[fingerprint] = exp

    async def reset(self) -> None:
        self._seen.clear()


_DEFAULT_STORE: Optional[TokenStore] = None


def get_default_store() -> TokenStore:
    """Return the module-level TokenStore, creating one lazily."""
    global _DEFAULT_STORE
    if _DEFAULT_STORE is None:
        _DEFAULT_STORE = TokenStore()
    return _DEFAULT_STORE


def replace_default_store(store: TokenStore) -> None:
    """Swap the default store (tests + Redis-backed prod)."""
    global _DEFAULT_STORE
    _DEFAULT_STORE = store


def _signing_key() -> bytes:
    key = os.getenv("HITL_SIGNING_KEY")
    if not key or len(key) < 32:
        raise RuntimeError(
            "HITL_SIGNING_KEY env var missing or too short (need >=32 chars); "
            "seed via AWS Secrets Manager /006-v3/hitl/signing-key"
        )
    return key.encode("utf-8")


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64dec(s: str) -> bytes:
    pad = 4 - (len(s) % 4)
    if pad < 4:
        s += "=" * pad
    return base64.urlsafe_b64decode(s.encode("ascii"))


def _fingerprint(mac_hex: str) -> str:
    """Derive a non-reversible fingerprint (steering rule 22: never raw)."""
    return hmac.new(_signing_key(), mac_hex.encode(), hashlib.sha256).hexdigest()[:32]


@dataclass
class VerifiedClaims:
    """Claims payload extracted from a verified token."""

    plan_hash: str
    user_id: str
    iat: float
    exp: float
    fingerprint: str


def mint_token(
    *, plan_hash: str, user_id: str, ttl_seconds: int = 300
) -> Tuple[str, float]:
    """Return (token, exp_epoch). TTL default is 5 minutes (steering rule 2)."""
    if not plan_hash:
        raise ValueError("plan_hash required")
    if not user_id:
        raise ValueError("user_id required")
    if ttl_seconds <= 0 or ttl_seconds > 3600:
        raise ValueError("ttl_seconds must be 1..3600")

    iat = _time.time()
    exp = iat + ttl_seconds
    payload = {
        "v": 1,
        "plan_hash": plan_hash,
        "user_id": user_id,
        "iat": iat,
        "exp": exp,
    }
    payload_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
    mac = hmac.new(_signing_key(), payload_bytes, hashlib.sha256).hexdigest()
    token = f"{_b64(payload_bytes)}.{mac}"
    return token, exp


def verify_token(
    token: str,
    *,
    expected_plan_hash: Optional[str] = None,
    expected_user_id: Optional[str] = None,
) -> VerifiedClaims:
    """Parse + verify a token. Raises ValueError with a reason on failure."""
    if not token or "." not in token:
        raise ValueError("token malformed")

    payload_b64, mac_hex = token.rsplit(".", 1)
    try:
        payload_bytes = _b64dec(payload_b64)
    except Exception as exc:
        raise ValueError(f"token payload not base64url: {exc}")

    expected_mac = hmac.new(_signing_key(), payload_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected_mac, mac_hex):
        raise ValueError("signature mismatch")

    try:
        claims = json.loads(payload_bytes)
    except ValueError as exc:
        raise ValueError(f"claims not json: {exc}")

    if claims.get("v") != 1:
        raise ValueError("unsupported token version")
    plan_hash = claims.get("plan_hash")
    user_id = claims.get("user_id")
    iat = float(claims.get("iat", 0))
    exp = float(claims.get("exp", 0))

    if not plan_hash or not user_id:
        raise ValueError("claims missing plan_hash/user_id")

    now = _time.time()
    if exp < now:
        raise ValueError("token expired")

    if expected_plan_hash is not None and expected_plan_hash != plan_hash:
        raise ValueError("plan_hash mismatch — token was minted for a different plan")

    if expected_user_id is not None and expected_user_id != user_id:
        raise ValueError("user_id mismatch")

    return VerifiedClaims(
        plan_hash=plan_hash,
        user_id=user_id,
        iat=iat,
        exp=exp,
        fingerprint=_fingerprint(mac_hex),
    )


def compute_plan_hash(plan: Dict) -> str:
    """Canonical SHA-256 of an ActionPlan dict — used both by caller + token."""
    payload = json.dumps(plan, separators=(",", ":"), sort_keys=True, default=str)
    return hashlib.sha256(payload.encode()).hexdigest()
