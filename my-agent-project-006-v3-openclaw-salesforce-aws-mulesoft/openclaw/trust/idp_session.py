"""AgentCore session token mint/verify.

HMAC-SHA256 signed tokens carrying principal_id + persona + TTL. Minted by
the channel adapter when a WebSocket opens; verified on every incoming hop.

Keys come from AGENTCORE_SESSION_SIGNING_KEY (env). Missing key = hard fail
(we never run with an insecure default).

Distinct from the HITL approval token (separate signing key): that token is
minted inside the skill on Approve click; this one bounds the whole session.
"""

from __future__ import annotations

import base64
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from hashlib import sha256
from typing import Optional


class SessionTokenInvalid(Exception):
    """Raised when a session token fails any verification step.

    Covers tampering, expired TTL, unknown signing key, malformed encoding.
    Callers must fail-closed: terminate the WebSocket, require re-auth.
    """


@dataclass(frozen=True)
class SessionClaims:
    """Parsed claims from a verified session token."""

    principal_id: str
    persona: str
    session_id: str
    issued_at: int
    expires_at: int
    channel: str = "web"


def _b64url_encode(data: bytes) -> str:
    """URL-safe base64 without padding (JWT-style)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    """URL-safe base64 decode with padding added back."""
    padding = 4 - (len(data) % 4)
    if padding != 4:
        data = data + ("=" * padding)
    return base64.urlsafe_b64decode(data.encode("ascii"))


class SessionTokenMinter:
    """Mint + verify session tokens. Stateless per instance.

    Token format (JWT-ish, not JWT): body_b64url.signature_b64url
    Body is UTF-8 JSON of the claims. Signature is HMAC-SHA256 of the body
    bytes with the shared secret from env.
    """

    def __init__(
        self,
        *,
        signing_key: Optional[str] = None,
        default_ttl_s: int = 3600,
    ) -> None:
        """
        Args:
            signing_key: override for tests. Production reads from env.
            default_ttl_s: default token lifetime; channel adapter can override.

        Raises:
            RuntimeError: if the signing key is missing.
        """
        key = signing_key or os.getenv("AGENTCORE_SESSION_SIGNING_KEY")
        if not key:
            raise RuntimeError(
                "AGENTCORE_SESSION_SIGNING_KEY not set. "
                "Session token mint/verify requires a 64-hex-char signing key. "
                "See .env.example."
            )
        self._key = key.encode("utf-8")
        self._default_ttl = default_ttl_s

    def mint(
        self,
        *,
        principal_id: str,
        persona: str,
        channel: str = "web",
        ttl_s: Optional[int] = None,
    ) -> str:
        """Mint a fresh session token bound to (principal, persona)."""
        if persona not in {"fsi_research", "fsi_advisor", "fsi_client_liaison"}:
            raise ValueError(f"unknown persona: {persona!r}")
        now = int(time.time())
        ttl = ttl_s if ttl_s is not None else self._default_ttl
        body = {
            "principal_id": principal_id,
            "persona": persona,
            "session_id": secrets.token_hex(16),
            "channel": channel,
            "iat": now,
            "exp": now + ttl,
        }
        body_bytes = json.dumps(body, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
        body_b64 = _b64url_encode(body_bytes)
        sig = hmac.new(self._key, body_b64.encode("ascii"), sha256).digest()
        sig_b64 = _b64url_encode(sig)
        return f"{body_b64}.{sig_b64}"

    def verify(self, token: str) -> SessionClaims:
        """Verify a token; return its claims on success.

        Raises:
            SessionTokenInvalid: on any failure (tamper, expiry, shape).
        """
        if not token or token.count(".") != 1:
            raise SessionTokenInvalid("malformed token shape")
        body_b64, sig_b64 = token.split(".", 1)

        try:
            sig = _b64url_decode(sig_b64)
        except Exception as exc:  # noqa: BLE001
            raise SessionTokenInvalid(f"signature decode error: {exc}") from exc

        expected = hmac.new(self._key, body_b64.encode("ascii"), sha256).digest()
        if not hmac.compare_digest(expected, sig):
            raise SessionTokenInvalid("signature mismatch")

        try:
            body_bytes = _b64url_decode(body_b64)
            body = json.loads(body_bytes.decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            raise SessionTokenInvalid(f"body decode error: {exc}") from exc

        now = int(time.time())
        try:
            exp = int(body["exp"])
            iat = int(body["iat"])
        except (KeyError, TypeError, ValueError) as exc:
            raise SessionTokenInvalid(f"missing/invalid iat/exp: {exc}") from exc

        if now >= exp:
            raise SessionTokenInvalid("token expired")
        if now < iat - 5:
            raise SessionTokenInvalid("token used before issued_at")

        try:
            return SessionClaims(
                principal_id=body["principal_id"],
                persona=body["persona"],
                session_id=body["session_id"],
                issued_at=iat,
                expires_at=exp,
                channel=body.get("channel", "web"),
            )
        except KeyError as exc:
            raise SessionTokenInvalid(f"missing claim: {exc}") from exc
