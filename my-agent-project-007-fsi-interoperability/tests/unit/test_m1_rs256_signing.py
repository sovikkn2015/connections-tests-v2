"""
M1 Agent Identity — RS256 Signing Tests.

Covers Phase 1.5 (Steering Rule 21) asymmetric-signing migration.
See `src/m1_identity/DECISION-LOG.md` entry D-RS256.

    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest \\
        my-agent-project-007-fsi-interoperability/tests/unit/test_m1_rs256_signing.py -v

Test-only RSA / EC keys are generated at setup time with `cryptography`.
No PEM bytes are hard-coded; generated material is ephemeral per-test and
never leaves the process.
"""

from __future__ import annotations

import base64
import warnings

import jwt as pyjwt
import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from m5_config_loader import Archetype, RegistrationType

from m1_identity import (
    AidClaims,
    IdentityService,
    InvalidAidError,
    Role,
)


# =============================================================================
# Helpers — test-only, ephemeral, never production-shaped
# =============================================================================

_AUDIENCE = "007-mcp-gateway"


def _rsa_pem(key_size: int = 2048) -> str:
    """Generate a fresh RSA private key and return it as PKCS#8 unencrypted PEM."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=key_size)
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _ec_pem() -> str:
    """Generate a fresh EC (SECP256R1) private key as PKCS#8 unencrypted PEM."""
    key = ec.generate_private_key(ec.SECP256R1())
    return key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")


def _issue_kwargs() -> dict:
    return dict(
        sub="sarah.chen@acmewm.com",
        firm_id="CRD-123456",
        crd_number="CRD-123456",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        registration_type=RegistrationType.ria_only,
        authority_scope=["portfolio.read", "research.create"],
        authority_excludes=["order.submit_without_hitl"],
        lei="549300ACMEWM1234RI99",
    )


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def rs256_svc(monkeypatch) -> IdentityService:
    """RS256-configured IdentityService with a fresh 2048-bit key."""
    monkeypatch.setenv("AID_PRIVATE_KEY_PEM", _rsa_pem(2048))
    return IdentityService(audience=_AUDIENCE, algorithm="RS256")


# =============================================================================
# Tests
# =============================================================================

class TestRs256Signing:

    def test_issue_and_verify_rs256_roundtrip(self, rs256_svc):
        """Happy path: RS256-issued token verifies back to a valid AidClaims."""
        token = rs256_svc.issue(**_issue_kwargs())
        assert isinstance(token, str)
        assert token.count(".") == 2

        # Header carries kid so remote verifiers can pick the right JWK.
        header = pyjwt.get_unverified_header(token)
        assert header["alg"] == "RS256"
        assert header["kid"]  # non-empty thumbprint

        claims = rs256_svc.verify(token)
        assert isinstance(claims, AidClaims)
        assert claims.sub == "sarah.chen@acmewm.com"
        assert claims.crd_number == "CRD-123456"
        assert claims.lei == "549300ACMEWM1234RI99"

    def test_hs256_token_rejected_when_rs256_configured(
        self, rs256_svc, monkeypatch
    ):
        """Algorithm-confusion defense: HS256 token presented to RS256 service
        raises InvalidAidError(reason="bad_algorithm")."""
        # Mint a separate HS256 service on its own key. HS256 construction
        # emits DeprecationWarning (expected and intentional here).
        monkeypatch.setenv(
            "AID_SIGNING_KEY",
            "test-key-only-for-unit-tests-do-not-deploy-000000",
        )
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", DeprecationWarning)
            hs_svc = IdentityService(audience=_AUDIENCE, algorithm="HS256")

        hs_token = hs_svc.issue(**_issue_kwargs())

        # The RS256-configured service must refuse an HS256 token.
        with pytest.raises(InvalidAidError) as excinfo:
            rs256_svc.verify(hs_token)
        assert excinfo.value.reason == "bad_algorithm"

    def test_jwks_format_rfc7517(self, rs256_svc):
        """get_jwks() returns RFC 7517 shape with RSA JWK params."""
        jwks = rs256_svc.get_jwks()
        assert set(jwks.keys()) == {"keys"}
        assert len(jwks["keys"]) == 1

        jwk = jwks["keys"][0]
        assert jwk["kty"] == "RSA"
        assert jwk["use"] == "sig"
        assert jwk["alg"] == "RS256"
        assert jwk["kid"]
        assert isinstance(jwk["n"], str) and jwk["n"]
        assert isinstance(jwk["e"], str) and jwk["e"]

        # n/e must be base64url-encoded (no '+', '/', or '=' padding).
        for component in (jwk["n"], jwk["e"]):
            assert "+" not in component
            assert "/" not in component
            assert "=" not in component
            # Round-trip decode must succeed (pad back before decoding).
            pad = "=" * (-len(component) % 4)
            base64.urlsafe_b64decode(component + pad)

        # The kid must match the header on a freshly-issued token.
        token = rs256_svc.issue(**_issue_kwargs())
        assert pyjwt.get_unverified_header(token)["kid"] == jwk["kid"]

    def test_private_key_never_in_repr_or_str(self, rs256_svc, monkeypatch):
        """Neither repr() nor str() may leak PEM bytes, HMAC secrets, or any
        portion of the raw key material."""
        pem_material = monkeypatch.setenv  # just to assert fixture wiring
        del pem_material

        repr_out = repr(rs256_svc)
        str_out = str(rs256_svc)

        for banned in (
            "BEGIN PRIVATE KEY",
            "BEGIN RSA PRIVATE KEY",
            "END PRIVATE KEY",
            "END RSA PRIVATE KEY",
            "-----",
            "MIIE",   # common PKCS#8 PEM body prefix
            "MIIC",   # common PKCS#1 PEM body prefix
        ):
            assert banned not in repr_out, f"repr leaked {banned!r}"
            assert banned not in str_out, f"str leaked {banned!r}"

        # Sanity: repr still carries non-secret observability fields.
        assert "IdentityService" in repr_out
        assert "RS256" in repr_out

    def test_short_rsa_key_rejected_at_init(self, monkeypatch):
        """A 1024-bit RSA key is below the 2048-bit floor and must raise."""
        monkeypatch.setenv("AID_PRIVATE_KEY_PEM", _rsa_pem(1024))
        with pytest.raises(RuntimeError, match="below minimum"):
            IdentityService(audience=_AUDIENCE, algorithm="RS256")

    def test_non_rsa_key_rejected_at_init(self, monkeypatch):
        """An EC private key must be refused — only RSA keys are supported."""
        monkeypatch.setenv("AID_PRIVATE_KEY_PEM", _ec_pem())
        with pytest.raises(RuntimeError, match="must be an RSA private key"):
            IdentityService(audience=_AUDIENCE, algorithm="RS256")

    def test_rs256_default_when_no_algorithm_specified(self, monkeypatch):
        """Constructor with no `algorithm=` argument defaults to RS256
        and emits NO DeprecationWarning."""
        monkeypatch.setenv("AID_PRIVATE_KEY_PEM", _rsa_pem(2048))

        with warnings.catch_warnings(record=True) as captured:
            warnings.simplefilter("always")
            svc = IdentityService(audience=_AUDIENCE)

        deprecation_hits = [
            w for w in captured if issubclass(w.category, DeprecationWarning)
        ]
        assert deprecation_hits == [], (
            "RS256 default path must not emit DeprecationWarning; "
            f"got {[str(w.message) for w in deprecation_hits]}"
        )

        # And the default is in fact RS256.
        token = svc.issue(**_issue_kwargs())
        assert pyjwt.get_unverified_header(token)["alg"] == "RS256"
