"""AID (Agent Identity Document) verification for M13.

M1 issues JWTs in production; M13 verifies them offline. Three modes:

* ``StaticAidVerifier`` — tests. Map of ``{token_str: claims_dict}``.
* ``HmacAidVerifier``   — HS256 shared-secret mode. Vault-delivered.
* (``RsaAidVerifier`` — RS256 public-key mode. Not fleshed out in the
  v1 build because ``pyjwt[crypto]`` is a heavier dep; the shape is
  registered so production can swap in a real RSA verifier without
  spec rework.)

No M1 import (Rule 33). No ``m11_python_adapters_shared`` import (D9).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Mapping, Protocol


class AidVerifyError(Exception):
    """Any failure during AID verification."""


@dataclass(frozen=True)
class AidClaims:
    """Parsed AID JWT claims required by M13 (see Spec §R13.2)."""

    sub: str
    aid: str
    role: str
    tenant_id: str
    firm_id: str
    iat: int
    exp: int


class AidVerifier(Protocol):
    def verify(self, token: str) -> AidClaims: ...


# ---------------------------------------------------------------------------
# Static (test) verifier
# ---------------------------------------------------------------------------


class StaticAidVerifier:
    """Test-only verifier.

    Constructed with a mapping of ``{raw_token_string: claims_dict}``.
    Tokens must match exactly (no cryptography). Unknown tokens raise
    ``AidVerifyError``.
    """

    def __init__(self, token_map: Mapping[str, Mapping[str, object]]) -> None:
        self._map: dict[str, AidClaims] = {}
        for tok, claims in token_map.items():
            self._map[tok] = _claims_from_mapping(claims)

    @classmethod
    def empty(cls) -> "StaticAidVerifier":
        return cls({})

    def verify(self, token: str) -> AidClaims:
        if not isinstance(token, str) or not token:
            raise AidVerifyError("empty token")
        claims = self._map.get(token)
        if claims is None:
            raise AidVerifyError("unknown token")
        _check_exp(claims.exp)
        return claims


# ---------------------------------------------------------------------------
# HMAC HS256 verifier (tests + dev). No pyjwt dep — manual implementation.
# ---------------------------------------------------------------------------


def _b64u_decode(s: str) -> bytes:
    pad = "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s + pad)


def _b64u_encode(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode("ascii")


class HmacAidVerifier:
    """HS256 JWT verifier. Accepts ``alg=HS256`` only.

    Tests may also use this alongside a helper to build tokens without
    needing ``pyjwt`` at import time.
    """

    _ALLOWED_ALG = "HS256"

    def __init__(self, secret: bytes) -> None:
        if not isinstance(secret, (bytes, bytearray)) or len(secret) < 16:
            raise ValueError("secret must be bytes >= 16 bytes")
        self._secret = bytes(secret)

    @staticmethod
    def make_token(secret: bytes, claims: Mapping[str, object]) -> str:
        """Build an HS256 token for tests. Not exposed in production."""
        header = {"alg": "HS256", "typ": "JWT"}
        header_b64 = _b64u_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        payload_b64 = _b64u_encode(json.dumps(claims, separators=(",", ":")).encode("utf-8"))
        signing_input = (header_b64 + "." + payload_b64).encode("ascii")
        sig = hmac.new(secret, signing_input, hashlib.sha256).digest()
        return header_b64 + "." + payload_b64 + "." + _b64u_encode(sig)

    def verify(self, token: str) -> AidClaims:
        if not isinstance(token, str) or token.count(".") != 2:
            raise AidVerifyError("malformed token")
        header_b64, payload_b64, sig_b64 = token.split(".")
        try:
            header = json.loads(_b64u_decode(header_b64))
        except Exception as exc:
            raise AidVerifyError("bad header") from exc
        if header.get("alg") != self._ALLOWED_ALG:
            raise AidVerifyError("unsupported alg")
        signing_input = (header_b64 + "." + payload_b64).encode("ascii")
        expected_sig = hmac.new(self._secret, signing_input, hashlib.sha256).digest()
        try:
            given_sig = _b64u_decode(sig_b64)
        except Exception as exc:
            raise AidVerifyError("bad signature encoding") from exc
        if not hmac.compare_digest(expected_sig, given_sig):
            raise AidVerifyError("bad signature")
        try:
            payload = json.loads(_b64u_decode(payload_b64))
        except Exception as exc:
            raise AidVerifyError("bad payload") from exc
        claims = _claims_from_mapping(payload)
        _check_exp(claims.exp)
        return claims


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _claims_from_mapping(raw: Mapping[str, object]) -> AidClaims:
    required = ("sub", "aid", "role", "tenant_id", "firm_id", "iat", "exp")
    for k in required:
        if k not in raw:
            raise AidVerifyError(f"missing claim: {k}")
    try:
        return AidClaims(
            sub=str(raw["sub"]),
            aid=str(raw["aid"]),
            role=str(raw["role"]),
            tenant_id=str(raw["tenant_id"]),
            firm_id=str(raw["firm_id"]),
            iat=int(raw["iat"]),  # type: ignore[arg-type]
            exp=int(raw["exp"]),  # type: ignore[arg-type]
        )
    except (TypeError, ValueError) as exc:
        raise AidVerifyError("invalid claim types") from exc


def _check_exp(exp: int, *, now: int | None = None) -> None:
    cur = int(time.time()) if now is None else int(now)
    if exp <= cur:
        raise AidVerifyError("expired")


__all__ = [
    "AidClaims",
    "AidVerifier",
    "AidVerifyError",
    "HmacAidVerifier",
    "StaticAidVerifier",
]
