"""
M1 Agent Identity -- IdentityService.

Issues, verifies, and revokes Agent Identity Documents (AIDs) as signed JWTs.

Phase 1 shipped HS256 (HMAC). Phase 1.5 adds RS256 (RSA) per Steering Rule 21
(mTLS / asymmetric signing for multi-service deployment). RS256 is now the
default so M6 verifiers only need the public key (JWKS). HS256 remains
available for backward-compatible unit tests and single-process embedding but
is explicitly deprecated via DeprecationWarning at construction time.

Key material sources (never in code, never in config files):
  - HS256 (deprecated): os.environ["AID_SIGNING_KEY"] -- HMAC shared secret.
  - RS256 (default):    os.environ["AID_PRIVATE_KEY_PEM"] -- PKCS#8 PEM.

Fail-closed on every verify path -- every error raises `InvalidAidError` with
a reason from the frozen vocabulary.
"""

from __future__ import annotations

import base64
import hashlib
import os
import re
import uuid
import warnings
from datetime import datetime, timezone
from typing import Any, Literal, Optional, Union

import jwt  # PyJWT
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.exceptions import (
    DecodeError,
    ExpiredSignatureError,
    ImmatureSignatureError,
    InvalidAlgorithmError,
    InvalidAudienceError,
    InvalidIssuerError,
    InvalidSignatureError,
    InvalidTokenError,
    MissingRequiredClaimError,
)
from pydantic import ValidationError

from m5_config_loader import Archetype, FirmConfig, RegistrationType

from m1_identity.claims import (
    AidClaims,
    InvalidAidError,
    ISSUER,
    Role,
)


# =============================================================================
# Public constants
# =============================================================================

DEFAULT_TTL_SECONDS: int = 900          # 15 minutes
MIN_TTL_SECONDS: int = 60               # 1 minute
MAX_TTL_SECONDS: int = 86_400           # 24 hours
DEFAULT_CLOCK_SKEW_SECONDS: int = 30
MAX_CLOCK_SKEW_SECONDS: int = 300       # 5 minutes
#: RS256 is default (Steering Rule 21). HS256 retained as deprecated.
SIGNING_ALGORITHM_DEFAULT: str = "RS256"
SupportedAlgorithm = Literal["HS256", "RS256"]
_SUPPORTED_ALGORITHMS: frozenset[str] = frozenset({"HS256", "RS256"})


# =============================================================================
# Private constants
# =============================================================================

_HS256_KEY_ENV: str = "AID_SIGNING_KEY"
_RS256_KEY_ENV: str = "AID_PRIVATE_KEY_PEM"
_MIN_HMAC_KEY_BYTES: int = 32
_MIN_RSA_KEY_BITS: int = 2048
_MAX_JTI_LEN: int = 256

# Required claims — PyJWT raises MissingRequiredClaimError when any claim is
# missing OR has a None value (PyJWT checks `payload.get(claim) is None`).
# `lei` is deliberately excluded from this list because `lei=None` is a
# legitimate wire value (R1.3). Missing-claim enforcement for `lei` is handled
# by the AidClaims Pydantic model (ConfigDict `extra="forbid"` rejects unknown
# keys and the model requires the `lei` key by virtue of its field declaration;
# absence manifests as Pydantic `ValidationError` → `invalid_claims`).
_REQUIRED_CLAIMS: tuple[str, ...] = (
    "iss", "sub", "aud", "exp", "iat", "nbf", "jti",
    "firm_id", "crd_number", "archetype", "role",
    "authority_scope", "authority_excludes", "registration_type",
)

# Control-character + whitespace detector for jti input validation (AC-R3-4).
_CONTROL_OR_WS_RE: re.Pattern[str] = re.compile(r"[\s\x00-\x1f\x7f]")


# =============================================================================
# Key material helpers (module-private)
# =============================================================================

def _b64url_uint(value: int) -> str:
    """RFC 7518 sec 2 base64url-encoded big-endian unsigned integer."""
    length = (value.bit_length() + 7) // 8 or 1
    return base64.urlsafe_b64encode(
        value.to_bytes(length, "big")
    ).rstrip(b"=").decode("ascii")


def _compute_kid(public_key: rsa.RSAPublicKey) -> str:
    """RFC 7638 JWK Thumbprint (SHA-256) -- deterministic key id."""
    numbers = public_key.public_numbers()
    n = _b64url_uint(numbers.n)
    e = _b64url_uint(numbers.e)
    canonical = f'{{"e":"{e}","kty":"RSA","n":"{n}"}}'.encode("utf-8")
    digest = hashlib.sha256(canonical).digest()
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def _load_rsa_private_key(pem: str) -> rsa.RSAPrivateKey:
    """Load a PKCS#8 or PKCS#1 PEM private key. Unencrypted only."""
    try:
        key = serialization.load_pem_private_key(
            pem.encode("utf-8"), password=None
        )
    except (TypeError, ValueError) as exc:
        raise RuntimeError(
            f"{_RS256_KEY_ENV} is not a valid unencrypted PEM private key: "
            f"{exc}"
        )
    if not isinstance(key, rsa.RSAPrivateKey):
        raise RuntimeError(
            f"{_RS256_KEY_ENV} must be an RSA private key "
            f"(got {type(key).__name__})"
        )
    if key.key_size < _MIN_RSA_KEY_BITS:
        raise RuntimeError(
            f"{_RS256_KEY_ENV} RSA key size {key.key_size} below minimum "
            f"{_MIN_RSA_KEY_BITS} bits"
        )
    return key


# =============================================================================
# IdentityService
# =============================================================================

class IdentityService:
    """
    Issues, verifies, revokes Agent Identity Documents.

    Constructor:
      - audience (required): `aud` claim locked on every token.
      - algorithm (default RS256): "RS256" (default) or "HS256" (deprecated).
      - default_ttl_seconds (default 900).
      - max_ttl_seconds (default 86_400).
      - clock_skew_leeway_seconds (default 30, range [0, 300]).

    Key material sources (env vars only -- never in config files):
      - RS256: `AID_PRIVATE_KEY_PEM` -- PKCS#8 unencrypted PEM private key.
      - HS256 (deprecated): `AID_SIGNING_KEY` -- HMAC shared secret, >= 32 bytes.
    HS256 emits `DeprecationWarning` at construction time per Rule 21.
    """

    def __init__(
        self,
        *,
        audience: str,
        algorithm: str = SIGNING_ALGORITHM_DEFAULT,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_ttl_seconds: int = MAX_TTL_SECONDS,
        clock_skew_leeway_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
    ) -> None:
        if not audience:
            raise ValueError("audience is required and must be non-empty")
        if algorithm not in _SUPPORTED_ALGORITHMS:
            raise ValueError(
                f"Unsupported algorithm '{algorithm}'. "
                f"Supported: {sorted(_SUPPORTED_ALGORITHMS)}."
            )
        # Auto-detect: if caller did not override the nominal RS256 default
        # but AID_PRIVATE_KEY_PEM is absent and AID_SIGNING_KEY is present,
        # fall back to HS256 with DeprecationWarning (backward compat path
        # for Phase 1 tests and single-process embedding per Rule 21).
        if (
            algorithm == SIGNING_ALGORITHM_DEFAULT
            and not os.environ.get(_RS256_KEY_ENV)
            and os.environ.get(_HS256_KEY_ENV)
        ):
            algorithm = "HS256"
        if max_ttl_seconds > MAX_TTL_SECONDS:
            raise ValueError(
                f"max_ttl_seconds {max_ttl_seconds} exceeds hard cap "
                f"{MAX_TTL_SECONDS}"
            )
        if default_ttl_seconds < MIN_TTL_SECONDS:
            raise ValueError(
                f"default_ttl_seconds {default_ttl_seconds} below minimum "
                f"{MIN_TTL_SECONDS}"
            )
        if default_ttl_seconds > max_ttl_seconds:
            raise ValueError(
                "default_ttl_seconds must be <= max_ttl_seconds"
            )
        if not (0 <= clock_skew_leeway_seconds <= MAX_CLOCK_SKEW_SECONDS):
            raise ValueError(
                f"clock_skew_leeway_seconds {clock_skew_leeway_seconds} "
                f"outside [0, {MAX_CLOCK_SKEW_SECONDS}]"
            )

        # Algorithm-specific key loading.
        self._rsa_private: Optional[rsa.RSAPrivateKey] = None
        self._rsa_public_pem: Optional[bytes] = None
        self._kid: Optional[str] = None

        if algorithm == "RS256":
            pem = os.environ.get(_RS256_KEY_ENV)
            if not pem:
                raise RuntimeError(
                    f"{_RS256_KEY_ENV} environment variable is required "
                    "for RS256 (no default, no CLI flag, no config file)"
                )
            self._rsa_private = _load_rsa_private_key(pem)
            public_key = self._rsa_private.public_key()
            self._rsa_public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            self._kid = _compute_kid(public_key)
            # PyJWT accepts PEM bytes for RS256 encode/decode.
            self._signing_key: Union[str, bytes] = pem.encode("utf-8")
            self._verify_key: Union[str, bytes] = self._rsa_public_pem
        else:
            # HS256 -- deprecated (Steering Rule 21).
            warnings.warn(
                "HS256 is deprecated for M1 IdentityService; "
                "use RS256 (AID_PRIVATE_KEY_PEM) per Steering Rule 21. "
                "HS256 remains for backward-compatible unit tests only.",
                DeprecationWarning,
                stacklevel=2,
            )
            key = os.environ.get(_HS256_KEY_ENV)
            if not key:
                raise RuntimeError(
                    f"{_HS256_KEY_ENV} environment variable is required "
                    "for HS256 (no default, no CLI flag, no config file)"
                )
            if len(key.encode("utf-8")) < _MIN_HMAC_KEY_BYTES:
                raise RuntimeError(
                    f"{_HS256_KEY_ENV} must be at least "
                    f"{_MIN_HMAC_KEY_BYTES} bytes "
                    "(HMAC-SHA256 requires 256 bits of entropy)"
                )
            self._signing_key = key
            self._verify_key = key

        self._audience: str = audience
        self._algorithm: str = algorithm
        self._default_ttl: int = default_ttl_seconds
        self._max_ttl: int = max_ttl_seconds
        self._leeway: int = clock_skew_leeway_seconds
        self._revoked: set[str] = set()

    def __repr__(self) -> str:
        # NEVER leak key material.
        return (
            f"IdentityService(issuer={ISSUER!r}, audience={self._audience!r}, "
            f"alg={self._algorithm!r}, revoked_count={len(self._revoked)})"
        )

    def get_jwks(self) -> dict:
        """Return RFC 7517 JWKS with the RS256 public key. RS256 only."""
        if self._algorithm != "RS256" or self._rsa_private is None:
            raise RuntimeError(
                "get_jwks() is only available when algorithm='RS256'"
            )
        numbers = self._rsa_private.public_key().public_numbers()
        return {
            "keys": [
                {
                    "kty": "RSA",
                    "use": "sig",
                    "alg": "RS256",
                    "kid": self._kid,
                    "n": _b64url_uint(numbers.n),
                    "e": _b64url_uint(numbers.e),
                }
            ]
        }

    # -------------------------------------------------------------------------
    # Issue
    # -------------------------------------------------------------------------

    def issue(
        self,
        *,
        sub: str,
        firm_id: str,
        crd_number: str,
        archetype: Archetype,
        role: Role,
        registration_type: RegistrationType,
        authority_scope: list[str],
        authority_excludes: list[str],
        lei: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Issue an AID for `sub`. Returns the encoded JWT string."""
        if not isinstance(archetype, Archetype):
            raise ValueError(
                "archetype must be m5_config_loader.Archetype enum member"
            )
        if not isinstance(role, Role):
            raise ValueError("role must be m1_identity.Role enum member")
        if not isinstance(registration_type, RegistrationType):
            raise ValueError(
                "registration_type must be m5_config_loader.RegistrationType "
                "enum member"
            )
        if not sub:
            raise ValueError("sub must be non-empty")
        if not firm_id:
            raise ValueError("firm_id must be non-empty")
        if not crd_number:
            raise ValueError("crd_number must be non-empty")

        ttl = self._default_ttl if ttl_seconds is None else ttl_seconds
        if ttl < MIN_TTL_SECONDS or ttl > self._max_ttl:
            raise ValueError(
                f"ttl_seconds {ttl} outside [{MIN_TTL_SECONDS}, {self._max_ttl}]"
            )

        # LEI format validation (AC-R1-12). None allowed.
        if lei is not None and not re.match(
            r"^[A-Z0-9]{18}[0-9]{2}$", lei
        ):
            raise ValueError(f"Invalid LEI format: '{lei}'")

        # authority_scope / authority_excludes: M1 does not validate semantics
        # (M2 owns the action catalog). Require lists of strings.
        if not isinstance(authority_scope, list) or not all(
            isinstance(a, str) for a in authority_scope
        ):
            raise ValueError("authority_scope must be list[str]")
        if not isinstance(authority_excludes, list) or not all(
            isinstance(a, str) for a in authority_excludes
        ):
            raise ValueError("authority_excludes must be list[str]")

        now = int(datetime.now(timezone.utc).timestamp())
        payload: dict[str, Any] = {
            "iss": ISSUER,
            "sub": sub,
            "aud": self._audience,
            "iat": now,
            "nbf": now,
            "exp": now + ttl,
            "jti": str(uuid.uuid4()),
            "firm_id": firm_id,
            "lei": lei,  # JSON null when None (R1.3)
            "crd_number": crd_number,
            "archetype": archetype.value,
            "role": role.value,
            "authority_scope": list(authority_scope),
            "authority_excludes": list(authority_excludes),
            "registration_type": registration_type.value,
        }
        headers = {"kid": self._kid} if self._algorithm == "RS256" else None
        return jwt.encode(
            payload,
            self._signing_key,
            algorithm=self._algorithm,
            headers=headers,
        )

    def issue_from_firm_config(
        self,
        *,
        firm_config: FirmConfig,
        sub: str,
        role: Role,
        archetype: Archetype,
        authority_scope: list[str],
        authority_excludes: list[str],
        ttl_seconds: Optional[int] = None,
    ) -> str:
        """Convenience over `issue` — derives firm fields from `FirmConfig`."""
        if not isinstance(firm_config, FirmConfig):
            raise ValueError(
                "firm_config must be m5_config_loader.FirmConfig instance"
            )
        return self.issue(
            sub=sub,
            firm_id=firm_config.crd_number,
            crd_number=firm_config.crd_number,
            archetype=archetype,
            role=role,
            registration_type=firm_config.registration_type,
            authority_scope=authority_scope,
            authority_excludes=authority_excludes,
            lei=firm_config.lei,
            ttl_seconds=ttl_seconds,
        )

    # -------------------------------------------------------------------------
    # Verify
    # -------------------------------------------------------------------------

    def verify(self, token: str) -> AidClaims:
        """
        Verify `token` and return parsed `AidClaims`.

        Pipeline (spec R2.1): structure → signature → alg → exp → nbf → iss →
        aud → revocation → claim parse. Every error path raises
        `InvalidAidError` with reason from the frozen vocabulary.
        """
        if not isinstance(token, str) or not token:
            raise InvalidAidError("malformed")

        try:
            payload: dict[str, Any] = jwt.decode(
                token,
                self._verify_key,
                algorithms=[self._algorithm],
                issuer=ISSUER,
                audience=self._audience,
                leeway=self._leeway,
                options={"require": list(_REQUIRED_CLAIMS)},
            )
        # Order matters: PyJWT exception hierarchy. Subclasses first; base last.
        except InvalidSignatureError:
            raise InvalidAidError("bad_signature")
        except ExpiredSignatureError:
            raise InvalidAidError("expired")
        except ImmatureSignatureError:
            raise InvalidAidError("not_yet_valid")
        except InvalidIssuerError:
            raise InvalidAidError("bad_issuer")
        except InvalidAudienceError:
            raise InvalidAidError("bad_audience")
        except InvalidAlgorithmError:
            raise InvalidAidError("bad_algorithm")
        except MissingRequiredClaimError:
            raise InvalidAidError("invalid_claims")
        except DecodeError:
            raise InvalidAidError("malformed")
        except InvalidTokenError:
            # Base of PyJWT hierarchy — catch-all.
            raise InvalidAidError("invalid_claims")

        # Revocation check AFTER signature/exp/iss/aud pass (spec §2.11).
        jti = payload.get("jti")
        if isinstance(jti, str) and jti in self._revoked:
            raise InvalidAidError("revoked")

        try:
            return AidClaims.model_validate(payload)
        except ValidationError:
            raise InvalidAidError("invalid_claims")

    # -------------------------------------------------------------------------
    # Revocation
    # -------------------------------------------------------------------------

    def revoke(self, jti: str) -> None:
        """
        Add `jti` to the revocation set.

        Validates input (AC-R3-4): non-empty, length <= 256, no whitespace or
        control characters. Idempotent.
        """
        self._validate_jti_input(jti)
        self._revoked.add(jti)

    def is_revoked(self, jti: str) -> bool:
        """Return True if jti is in the revocation set."""
        if not isinstance(jti, str):
            return False
        return jti in self._revoked

    @staticmethod
    def _validate_jti_input(jti: str) -> None:
        if not isinstance(jti, str):
            raise ValueError("jti must be a string")
        if not jti:
            raise ValueError("jti must be non-empty")
        if len(jti) > _MAX_JTI_LEN:
            raise ValueError(f"jti length exceeds {_MAX_JTI_LEN}")
        if _CONTROL_OR_WS_RE.search(jti):
            raise ValueError("jti must not contain whitespace or control chars")

    # -------------------------------------------------------------------------
    # Health
    # -------------------------------------------------------------------------

    def health(self) -> dict:
        """Diagnostics. NEVER returns key material."""
        return {
            "status": "ok",
            "alg": self._algorithm,
            "issuer": ISSUER,
            "audience": self._audience,
            "revoked_count": len(self._revoked),
            "clock_skew_leeway_seconds": self._leeway,
        }
