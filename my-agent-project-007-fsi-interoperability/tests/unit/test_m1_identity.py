"""
M1 Agent Identity — Unit Tests.

Covers spec §3 tasks T9..T19 (R1..R6 acceptance criteria).

    PYTHONPATH=my-agent-project-007-fsi-interoperability/src \\
        python3 -m pytest my-agent-project-007-fsi-interoperability/tests/ -v
"""

from __future__ import annotations

import ast
import re
import time
from datetime import datetime, timezone
from pathlib import Path

import jwt as pyjwt
import pytest

from m5_config_loader import (
    Archetype,
    FirmConfig,
    RegistrationType,
)

import m1_identity
from m1_identity import (
    AidClaims,
    DEFAULT_CLOCK_SKEW_SECONDS,
    DEFAULT_TTL_SECONDS,
    ISSUER,
    IdentityService,
    InvalidAidError,
    LEI_PATTERN,
    MAX_CLOCK_SKEW_SECONDS,
    MAX_TTL_SECONDS,
    MIN_TTL_SECONDS,
    Role,
)
from m1_identity import claims as claims_mod
from m1_identity import service as service_mod


# =============================================================================
# Fixtures — explicit test-only key, never production-shaped
# =============================================================================

# 50 chars — clearly labelled test-only. No AKIA/sk-/Bearer/long-hex patterns.
_TEST_KEY = "test-key-only-for-unit-tests-do-not-deploy-000000"
_AUDIENCE = "007-mcp-gateway"


@pytest.fixture
def svc(monkeypatch) -> IdentityService:
    """Default IdentityService with HS256 + test-only key."""
    monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
    return IdentityService(audience=_AUDIENCE)


@pytest.fixture
def issue_kwargs() -> dict:
    return dict(
        sub="sarah.chen@acmewm.com",
        firm_id="CRD-123456",
        crd_number="CRD-123456",
        archetype=Archetype.tier4_independent_ria,
        role=Role.advisor,
        registration_type=RegistrationType.ria_only,
        authority_scope=["portfolio.read", "research.create"],
        authority_excludes=["order.submit_without_hitl"],
        # Valid LEI format: 18 alnum + 2 numeric check digits (ISO 17442)
        lei="549300ACMEWM1234RI99",
    )


@pytest.fixture
def firm_config() -> FirmConfig:
    return FirmConfig(
        name="Acme Wealth Management",
        lei="549300ACMEWM1234RI99",
        crd_number="CRD-123456",
        registration_type=RegistrationType.ria_only,
    )


# =============================================================================
# T2 / T9 — Issuance (R1)
# =============================================================================

class TestIssue:

    def test_issue_returns_three_segment_jwt_string(self, svc, issue_kwargs):
        # AC-R1-1
        token = svc.issue(**issue_kwargs)
        assert isinstance(token, str)
        assert token.count(".") == 2
        for seg in token.split("."):
            assert seg

    def test_decoded_token_contains_all_claims(self, svc, issue_kwargs):
        # AC-R1-2
        token = svc.issue(**issue_kwargs)
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        for key in (
            "iss", "sub", "aud", "exp", "iat", "nbf", "jti",
            "firm_id", "lei", "crd_number", "archetype", "role",
            "authority_scope", "authority_excludes", "registration_type",
        ):
            assert key in raw, f"missing claim: {key}"
        assert raw["sub"] == issue_kwargs["sub"]
        assert raw["firm_id"] == issue_kwargs["firm_id"]
        assert raw["crd_number"] == issue_kwargs["crd_number"]
        assert raw["archetype"] == issue_kwargs["archetype"].value
        assert raw["role"] == issue_kwargs["role"].value
        assert raw["registration_type"] == issue_kwargs["registration_type"].value
        assert raw["lei"] == issue_kwargs["lei"]
        assert raw["authority_scope"] == issue_kwargs["authority_scope"]
        assert raw["authority_excludes"] == issue_kwargs["authority_excludes"]

    def test_iss_locked_to_platform(self, svc, issue_kwargs):
        # AC-R1-3
        token = svc.issue(**issue_kwargs)
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        assert raw["iss"] == "007-fsi-platform"

    def test_aud_equals_configured_audience(self, svc, issue_kwargs):
        # AC-R1-4
        token = svc.issue(**issue_kwargs)
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        assert raw["aud"] == _AUDIENCE

    def test_jti_uniqueness_across_1000_tokens(self, svc, issue_kwargs):
        # AC-R1-5
        seen: set[str] = set()
        for _ in range(1000):
            token = svc.issue(**issue_kwargs)
            raw = pyjwt.decode(
                token,
                options={"verify_signature": False, "verify_aud": False},
            )
            seen.add(raw["jti"])
        assert len(seen) == 1000

    def test_exp_minus_iat_equals_ttl(self, svc, issue_kwargs):
        # AC-R1-6
        token = svc.issue(**issue_kwargs, ttl_seconds=600)
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        assert raw["exp"] - raw["iat"] == 600

    def test_default_ttl_is_900(self, svc, issue_kwargs):
        token = svc.issue(**issue_kwargs)
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        assert raw["exp"] - raw["iat"] == DEFAULT_TTL_SECONDS == 900

    def test_nbf_equals_iat(self, svc, issue_kwargs):
        # AC-R1-7
        token = svc.issue(**issue_kwargs)
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        assert raw["nbf"] == raw["iat"]

    def test_archetype_must_be_enum(self, svc, issue_kwargs):
        # AC-R1-8
        kwargs = {**issue_kwargs, "archetype": "tier4_independent_ria"}
        with pytest.raises(ValueError, match="archetype must be"):
            svc.issue(**kwargs)

    def test_role_must_be_enum(self, svc, issue_kwargs):
        # AC-R1-9
        kwargs = {**issue_kwargs, "role": "advisor"}
        with pytest.raises(ValueError, match="role must be"):
            svc.issue(**kwargs)

    def test_registration_type_must_be_enum(self, svc, issue_kwargs):
        # AC-R1-10
        kwargs = {**issue_kwargs, "registration_type": "ria_only"}
        with pytest.raises(ValueError, match="registration_type must be"):
            svc.issue(**kwargs)

    def test_empty_firm_id_raises(self, svc, issue_kwargs):
        # AC-R1-11
        with pytest.raises(ValueError, match="firm_id"):
            svc.issue(**{**issue_kwargs, "firm_id": ""})

    def test_empty_crd_raises(self, svc, issue_kwargs):
        # AC-R1-11
        with pytest.raises(ValueError, match="crd_number"):
            svc.issue(**{**issue_kwargs, "crd_number": ""})

    def test_empty_sub_raises(self, svc, issue_kwargs):
        with pytest.raises(ValueError, match="sub"):
            svc.issue(**{**issue_kwargs, "sub": ""})

    def test_malformed_lei_raises(self, svc, issue_kwargs):
        # AC-R1-12
        with pytest.raises(ValueError, match="LEI"):
            svc.issue(**{**issue_kwargs, "lei": "not-a-lei"})

    def test_null_lei_accepted(self, svc, issue_kwargs):
        # AC-R1-12, R1.3 — lei=None encoded as JSON null
        token = svc.issue(**{**issue_kwargs, "lei": None})
        raw = pyjwt.decode(
            token, options={"verify_signature": False, "verify_aud": False}
        )
        assert raw["lei"] is None
        assert "lei" in raw  # present, not omitted

    def test_ttl_below_min_raises(self, svc, issue_kwargs):
        # AC-R1-13
        with pytest.raises(ValueError, match=r"ttl_seconds"):
            svc.issue(**issue_kwargs, ttl_seconds=30)

    def test_ttl_above_max_raises(self, svc, issue_kwargs):
        # AC-R1-13
        with pytest.raises(ValueError, match=r"ttl_seconds"):
            svc.issue(**issue_kwargs, ttl_seconds=MAX_TTL_SECONDS + 1)

    def test_authority_scope_must_be_list_of_str(self, svc, issue_kwargs):
        with pytest.raises(ValueError, match="authority_scope"):
            svc.issue(**{**issue_kwargs, "authority_scope": "not-a-list"})
        with pytest.raises(ValueError, match="authority_scope"):
            svc.issue(**{**issue_kwargs, "authority_scope": [1, 2, 3]})

    def test_authority_excludes_must_be_list_of_str(self, svc, issue_kwargs):
        with pytest.raises(ValueError, match="authority_excludes"):
            svc.issue(**{**issue_kwargs, "authority_excludes": None})


# =============================================================================
# T6 / T10 — Verification (R2)
# =============================================================================

class TestVerify:

    def test_round_trip_returns_aid_claims(self, svc, issue_kwargs):
        # AC-R2-1
        token = svc.issue(**issue_kwargs)
        claims = svc.verify(token)
        assert isinstance(claims, AidClaims)
        assert claims.sub == issue_kwargs["sub"]
        assert claims.archetype == issue_kwargs["archetype"].value
        assert claims.role == issue_kwargs["role"]
        assert claims.lei == issue_kwargs["lei"]

    def test_wrong_key_raises_bad_signature(self, svc, issue_kwargs,
                                             monkeypatch):
        # AC-R2-2
        token = svc.issue(**issue_kwargs)
        monkeypatch.setenv(
            "AID_SIGNING_KEY",
            "test-key-only-for-unit-tests-do-not-deploy-DIFFERENT"
        )
        other = IdentityService(audience=_AUDIENCE)
        with pytest.raises(InvalidAidError, match="bad_signature") as exc:
            other.verify(token)
        assert exc.value.reason == "bad_signature"

    def test_expired_token_raises(self, svc, issue_kwargs):
        # AC-R2-3
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now - 1000, nbf=now - 1000,
                                 exp=now - 500)
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="expired") as exc:
            svc.verify(token)
        assert exc.value.reason == "expired"

    def test_wrong_issuer_raises(self, svc, issue_kwargs):
        # AC-R2-4
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now,
                                 exp=now + 300, iss="bad-issuer")
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="bad_issuer"):
            svc.verify(token)

    def test_wrong_audience_raises(self, svc, issue_kwargs):
        # AC-R2-5
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now,
                                 exp=now + 300, aud="some-other-audience")
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="bad_audience"):
            svc.verify(token)

    def test_alg_none_rejected(self, svc, issue_kwargs):
        # AC-R2-6
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now, exp=now + 300)
        token = pyjwt.encode(payload, key="", algorithm="none")
        with pytest.raises(InvalidAidError) as exc:
            svc.verify(token)
        assert exc.value.reason in {
            "bad_algorithm", "malformed", "bad_signature", "invalid_claims",
        }

    def test_tampered_payload_raises(self, svc, issue_kwargs):
        # AC-R2-7
        token = svc.issue(**issue_kwargs)
        header, payload, sig = token.split(".")
        tampered = f"{header}.{payload + 'X'}.{sig}"
        with pytest.raises(InvalidAidError) as exc:
            svc.verify(tampered)
        assert exc.value.reason in {
            "bad_signature", "malformed", "invalid_claims",
        }

    def test_revoked_token_raises(self, svc, issue_kwargs):
        # AC-R2-8
        token = svc.issue(**issue_kwargs)
        claims = svc.verify(token)
        svc.revoke(claims.jti)
        with pytest.raises(InvalidAidError, match="revoked") as exc:
            svc.verify(token)
        assert exc.value.reason == "revoked"

    def test_malformed_token_non_string(self, svc):
        # AC-R2-9
        with pytest.raises(InvalidAidError, match="malformed"):
            svc.verify("")

    def test_malformed_token_wrong_segments(self, svc):
        # AC-R2-9
        with pytest.raises(InvalidAidError):
            svc.verify("not-a-jwt")
        with pytest.raises(InvalidAidError):
            svc.verify("a.b")
        with pytest.raises(InvalidAidError):
            svc.verify("a.b.c.d")

    def test_missing_required_claim_raises(self, svc, issue_kwargs):
        # AC-R2-10
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now, exp=now + 300)
        del payload["firm_id"]
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="invalid_claims"):
            svc.verify(token)

    def test_missing_lei_claim_raises(self, svc, issue_kwargs):
        # N4 — lei key absent (vs lei=None)
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now, exp=now + 300)
        del payload["lei"]
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="invalid_claims"):
            svc.verify(token)

    def test_verify_never_returns_on_failure(self, svc):
        # AC-R2-11
        for bad in ["", "junk", "a.b.c"]:
            with pytest.raises(InvalidAidError):
                svc.verify(bad)

    def test_invalid_archetype_in_payload_raises(self, svc, issue_kwargs):
        # AC-R2-12 (F9)
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now, exp=now + 300)
        payload["archetype"] = "lol"
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="invalid_claims") as exc:
            svc.verify(token)
        assert exc.value.reason == "invalid_claims"

    def test_invalid_registration_type_in_payload_raises(self, svc,
                                                         issue_kwargs):
        # AC-R2-13 (F9)
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now, nbf=now, exp=now + 300)
        payload["registration_type"] = "foo"
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="invalid_claims"):
            svc.verify(token)


# =============================================================================
# T16 — Clock skew leeway (R2.3)
# =============================================================================

class TestClockSkewLeeway:

    def test_exp_within_leeway_succeeds(self, svc, issue_kwargs):
        # AC-R2-14
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now - 1000, nbf=now - 1000,
                                 exp=now - 20)
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        claims = svc.verify(token)
        assert isinstance(claims, AidClaims)

    def test_exp_beyond_leeway_raises(self, svc, issue_kwargs):
        # AC-R2-15
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now - 1000, nbf=now - 1000,
                                 exp=now - 40)
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="expired"):
            svc.verify(token)

    def test_nbf_within_leeway_succeeds(self, svc, issue_kwargs):
        # AC-R2-16
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now + 20, nbf=now + 20,
                                 exp=now + 1000)
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        claims = svc.verify(token)
        assert isinstance(claims, AidClaims)

    def test_nbf_beyond_leeway_raises(self, svc, issue_kwargs):
        # AC-R2-17
        now = int(datetime.now(timezone.utc).timestamp())
        payload = _build_payload(issue_kwargs, iat=now + 40, nbf=now + 40,
                                 exp=now + 1000)
        token = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError, match="not_yet_valid"):
            svc.verify(token)

    def test_leeway_out_of_range_raises(self, monkeypatch):
        # AC-R2-18
        monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
        with pytest.raises(ValueError, match="clock_skew_leeway_seconds"):
            IdentityService(audience=_AUDIENCE,
                            clock_skew_leeway_seconds=-1)
        with pytest.raises(ValueError, match="clock_skew_leeway_seconds"):
            IdentityService(audience=_AUDIENCE,
                            clock_skew_leeway_seconds=MAX_CLOCK_SKEW_SECONDS + 1)


# =============================================================================
# T7 / T11 — Revocation (R3)
# =============================================================================

class TestRevocation:

    def test_revoke_marks_jti(self, svc):
        # AC-R3-1
        jti = "abc-123"
        assert not svc.is_revoked(jti)
        svc.revoke(jti)
        assert svc.is_revoked(jti)

    def test_revoke_then_verify_raises(self, svc, issue_kwargs):
        # AC-R3-2
        token = svc.issue(**issue_kwargs)
        claims = svc.verify(token)
        svc.revoke(claims.jti)
        with pytest.raises(InvalidAidError, match="revoked"):
            svc.verify(token)

    def test_revoke_idempotent(self, svc):
        # AC-R3-3
        svc.revoke("abc")
        svc.revoke("abc")
        assert svc.is_revoked("abc")

    def test_revoke_empty_raises(self, svc):
        # AC-R3-4
        with pytest.raises(ValueError, match="non-empty"):
            svc.revoke("")

    def test_revoke_too_long_raises(self, svc):
        # AC-R3-4
        with pytest.raises(ValueError, match="length exceeds"):
            svc.revoke("x" * 257)

    def test_revoke_whitespace_raises(self, svc):
        # AC-R3-4
        with pytest.raises(ValueError, match="whitespace"):
            svc.revoke("abc def")
        with pytest.raises(ValueError, match="whitespace"):
            svc.revoke("abc\n")
        with pytest.raises(ValueError, match="whitespace"):
            svc.revoke("\tabc")

    def test_revoke_control_char_raises(self, svc):
        # AC-R3-4
        with pytest.raises(ValueError, match="whitespace"):
            svc.revoke("abc\x01")

    def test_revoke_non_string_raises(self, svc):
        with pytest.raises(ValueError, match="string"):
            svc.revoke(123)  # type: ignore[arg-type]

    def test_is_revoked_tolerates_non_string(self, svc):
        assert svc.is_revoked(None) is False  # type: ignore[arg-type]
        assert svc.is_revoked(123) is False  # type: ignore[arg-type]


# =============================================================================
# T3 / T12 — Security (R4)
# =============================================================================

class TestSecurity:

    def test_missing_env_raises_runtime_error(self, monkeypatch):
        # AC-R4-1, AC-R4-2 -- with both env vars absent, RS256 (default)
        # raises about AID_PRIVATE_KEY_PEM.
        monkeypatch.delenv("AID_SIGNING_KEY", raising=False)
        monkeypatch.delenv("AID_PRIVATE_KEY_PEM", raising=False)
        with pytest.raises(RuntimeError, match="AID_PRIVATE_KEY_PEM"):
            IdentityService(audience=_AUDIENCE)

    def test_short_key_raises_runtime_error(self, monkeypatch):
        # AC-R4-3
        monkeypatch.setenv("AID_SIGNING_KEY", "too-short")
        with pytest.raises(RuntimeError, match="32 bytes"):
            IdentityService(audience=_AUDIENCE)

    def test_repr_does_not_leak_key(self, svc):
        # AC-R4-4
        r = repr(svc)
        assert _TEST_KEY not in r
        assert ISSUER in r
        assert _AUDIENCE in r
        assert "alg" in r

    def test_str_does_not_leak_key(self, svc):
        # AC-R4-4
        assert _TEST_KEY not in str(svc)

    def test_default_ttl_constants(self):
        # AC-R4-9
        assert DEFAULT_TTL_SECONDS == 900
        assert MIN_TTL_SECONDS == 60
        assert MAX_TTL_SECONDS == 86_400

    def test_ttl_above_cap_at_construction_raises(self, monkeypatch):
        # AC-R4-10
        monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
        with pytest.raises(ValueError, match="hard cap"):
            IdentityService(audience=_AUDIENCE,
                            max_ttl_seconds=MAX_TTL_SECONDS + 1)

    def test_default_ttl_below_min_at_construction_raises(self, monkeypatch):
        # AC-R4-11
        monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
        with pytest.raises(ValueError, match="below minimum"):
            IdentityService(audience=_AUDIENCE,
                            default_ttl_seconds=MIN_TTL_SECONDS - 1)

    def test_unsupported_algorithm_raises(self, monkeypatch):
        monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
        # RS256 and HS256 are supported; ES256 is not.
        with pytest.raises(ValueError, match="Unsupported algorithm"):
            IdentityService(audience=_AUDIENCE, algorithm="ES256")

    def test_empty_audience_raises(self, monkeypatch):
        monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
        with pytest.raises(ValueError, match="audience"):
            IdentityService(audience="")


# =============================================================================
# T15 / T18 — Frozen vocabulary + message hygiene (R4.2)
# =============================================================================

class TestErrorVocabulary:

    FROZEN_VOCAB = frozenset({
        "malformed",
        "bad_signature",
        "bad_algorithm",
        "expired",
        "not_yet_valid",
        "bad_issuer",
        "bad_audience",
        "revoked",
        "invalid_claims",
    })

    def test_invalid_aid_error_has_reason_attribute(self):
        exc = InvalidAidError("bad_signature")
        assert exc.reason == "bad_signature"

    def test_str_equals_reason_no_pii(self):
        # AC-R4-8 (F7)
        for reason in self.FROZEN_VOCAB:
            exc = InvalidAidError(reason)
            assert str(exc) == reason, (
                f"{reason}: str(exc) must equal reason exactly to prevent "
                f"PII leakage via exception messages"
            )

    def test_all_negative_scenarios_raise_from_frozen_vocab(
        self, svc, issue_kwargs
    ):
        now = int(datetime.now(timezone.utc).timestamp())
        seen_reasons: set[str] = set()

        # malformed scenarios
        for token in ["", "not-a-jwt", "a.b.c"]:
            with pytest.raises(InvalidAidError) as exc:
                svc.verify(token)
            assert exc.value.reason in self.FROZEN_VOCAB
            seen_reasons.add(exc.value.reason)

        # wrong issuer
        payload = _build_payload(issue_kwargs, iat=now, nbf=now,
                                 exp=now + 300, iss="bad")
        tok = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError) as exc:
            svc.verify(tok)
        assert exc.value.reason == "bad_issuer"
        seen_reasons.add(exc.value.reason)

        # wrong audience
        payload = _build_payload(issue_kwargs, iat=now, nbf=now,
                                 exp=now + 300, aud="bad")
        tok = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError) as exc:
            svc.verify(tok)
        assert exc.value.reason == "bad_audience"
        seen_reasons.add(exc.value.reason)

        # expired
        payload = _build_payload(issue_kwargs, iat=now - 1000,
                                 nbf=now - 1000, exp=now - 500)
        tok = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError) as exc:
            svc.verify(tok)
        assert exc.value.reason == "expired"
        seen_reasons.add(exc.value.reason)

        # invalid_claims (bad archetype)
        payload = _build_payload(issue_kwargs, iat=now, nbf=now,
                                 exp=now + 300)
        payload["archetype"] = "lol"
        tok = pyjwt.encode(payload, _TEST_KEY, algorithm="HS256")
        with pytest.raises(InvalidAidError) as exc:
            svc.verify(tok)
        assert exc.value.reason == "invalid_claims"
        seen_reasons.add(exc.value.reason)

        # Every observed reason is from the frozen set.
        assert seen_reasons.issubset(self.FROZEN_VOCAB)

    def test_service_module_documents_pyjwt_mapping(self):
        # §2.10 — service file references each PyJWT exception.
        source = Path(service_mod.__file__).read_text()
        for name in (
            "InvalidSignatureError",
            "ExpiredSignatureError",
            "ImmatureSignatureError",
            "InvalidIssuerError",
            "InvalidAudienceError",
            "InvalidAlgorithmError",
            "MissingRequiredClaimError",
            "DecodeError",
            "InvalidTokenError",
        ):
            assert name in source, f"PyJWT {name} not handled in service.py"


# =============================================================================
# T5 / T13 — Integration with M5 (R5)
# =============================================================================

class TestM5Integration:

    def test_archetype_enum_matches_m5(self):
        # AC-R5-1
        from m5_config_loader import Archetype as M5Archetype
        assert Archetype is M5Archetype
        assert {a.value for a in Archetype} == {
            "tier1_investment_bank",
            "tier2_asset_manager",
            "tier3_broker_dealer",
            "tier4_independent_ria",
            "tier5_hedge_fund",
        }

    def test_registration_type_enum_matches_m5(self):
        # AC-R5-2
        from m5_config_loader import RegistrationType as M5RegType
        assert RegistrationType is M5RegType
        assert {r.value for r in RegistrationType} == {
            "ria_only", "bd_only", "dual_registered",
        }

    def test_issue_from_firm_config_derives_fields(self, svc, firm_config):
        # AC-R5-3
        token = svc.issue_from_firm_config(
            firm_config=firm_config,
            sub="sarah.chen",
            role=Role.advisor,
            archetype=Archetype.tier4_independent_ria,
            authority_scope=["portfolio.read"],
            authority_excludes=[],
        )
        claims = svc.verify(token)
        assert claims.firm_id == firm_config.crd_number
        assert claims.crd_number == firm_config.crd_number
        assert claims.lei == firm_config.lei
        assert claims.registration_type == firm_config.registration_type.value

    def test_issue_from_firm_config_with_null_lei(self, svc):
        firm = FirmConfig(
            name="Small RIA",
            lei=None,
            crd_number="CRD-999",
            registration_type=RegistrationType.ria_only,
        )
        token = svc.issue_from_firm_config(
            firm_config=firm,
            sub="sarah.chen",
            role=Role.advisor,
            archetype=Archetype.tier4_independent_ria,
            authority_scope=[],
            authority_excludes=[],
        )
        claims = svc.verify(token)
        assert claims.lei is None

    def test_issue_from_firm_config_rejects_non_firm_config(self, svc):
        with pytest.raises(ValueError, match="FirmConfig"):
            svc.issue_from_firm_config(
                firm_config={"crd_number": "CRD-1"},  # type: ignore[arg-type]
                sub="x", role=Role.advisor,
                archetype=Archetype.tier4_independent_ria,
                authority_scope=[], authority_excludes=[],
            )


# =============================================================================
# T14 — Module boundary (AC-R5-4) — AST scan
# =============================================================================

_FORBIDDEN_MODULE_PREFIXES = (
    "m2_", "m3_", "m4_", "m6_", "m7_", "m8_", "m9_", "m10_",
    "m11_", "m12_", "m13_",
)

_ALLOWED_PROJECT_PREFIX = "m5_config_loader"


def _is_forbidden(module: str) -> bool:
    if not module:
        return False
    if module.startswith(_ALLOWED_PROJECT_PREFIX):
        return False
    for prefix in _FORBIDDEN_MODULE_PREFIXES:
        if module.startswith(prefix):
            return True
    return False


def _scan_imports_for_file(path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(path.read_text())
    forbidden: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden(alias.name):
                    forbidden.append((node.lineno, alias.name))
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            if _is_forbidden(module):
                forbidden.append((node.lineno, module))
    return forbidden


class TestModuleBoundary:

    def test_no_cross_module_imports(self):
        # AC-R5-4
        src_dir = Path(m1_identity.__file__).parent
        violations: list[str] = []
        for py_file in sorted(src_dir.glob("*.py")):
            for lineno, module in _scan_imports_for_file(py_file):
                violations.append(f"{py_file.name}:{lineno}: {module}")
        assert not violations, (
            "Forbidden cross-module imports detected:\n  "
            + "\n  ".join(violations)
        )

    def test_allowed_imports_include_m5(self):
        source = Path(claims_mod.__file__).read_text()
        assert "from m5_config_loader" in source


# =============================================================================
# T17 — LEI regex drift (AC-R5-6)
# =============================================================================

class TestLEIDrift:

    def test_m1_lei_pattern_equals_m5(self):
        # AC-R5-6
        import m5_config_loader.loader as m5_loader
        m5_source = Path(m5_loader.__file__).read_text()
        # Find the exact regex literal in M5
        # Looking for: r"^[A-Z0-9]{18}[0-9]{2}$"
        expected_literal = r'r"^[A-Z0-9]{18}[0-9]{2}$"'
        assert expected_literal in m5_source, (
            "Could not locate M5 LEI regex literal — test setup broken "
            "or M5 changed its pattern"
        )
        # M1's LEI_PATTERN is the inner pattern string
        assert LEI_PATTERN == r"^[A-Z0-9]{18}[0-9]{2}$"


# =============================================================================
# T7 — Health (AC-R6-1) and T8 — public API (AC-R6-3)
# =============================================================================

class TestHealthAndPublicAPI:

    def test_health_fields(self, svc):
        # AC-R6-1
        h = svc.health()
        assert h["status"] == "ok"
        assert h["alg"] == "HS256"
        assert h["issuer"] == ISSUER
        assert h["audience"] == _AUDIENCE
        assert h["revoked_count"] == 0
        assert h["clock_skew_leeway_seconds"] == DEFAULT_CLOCK_SKEW_SECONDS

    def test_health_never_returns_key(self, svc):
        h = svc.health()
        assert _TEST_KEY not in str(h)
        assert "_key" not in h
        assert "key" not in h

    def test_health_counts_revocations(self, svc):
        svc.revoke("abc")
        svc.revoke("def")
        assert svc.health()["revoked_count"] == 2

    def test_public_api_matches_all(self):
        # AC-R6-3
        expected = {
            "AidClaims", "Role", "InvalidAidError", "ISSUER", "LEI_PATTERN",
            "IdentityService", "DEFAULT_TTL_SECONDS", "MAX_TTL_SECONDS",
            "MIN_TTL_SECONDS", "DEFAULT_CLOCK_SKEW_SECONDS",
            "MAX_CLOCK_SKEW_SECONDS", "SIGNING_ALGORITHM_DEFAULT",
        }
        assert set(m1_identity.__all__) == expected


# =============================================================================
# T19 — Performance sanity (AC-R6-2)
# =============================================================================

class TestPerformance:

    def test_issue_verify_round_trip_under_50ms(self, svc, issue_kwargs):
        start = time.perf_counter()
        token = svc.issue(**issue_kwargs)
        svc.verify(token)
        elapsed_ms = (time.perf_counter() - start) * 1000
        assert elapsed_ms < 50, (
            f"issue+verify round-trip took {elapsed_ms:.2f} ms (budget 50 ms)"
        )


# =============================================================================
# Security hygiene — source scan for credential patterns (AC-R4-6)
# =============================================================================

_CREDENTIAL_PATTERNS = [
    re.compile(r"AKIA[A-Z0-9]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"Bearer\s+[A-Za-z0-9\-_.]{8,}"),
    # Patterns below are split via string concatenation to prevent this file
    # from matching its own credential detectors.
    re.compile("-" * 5 + "BEGIN"),
    re.compile(r"ghp_[A-Za-z0-9]{36,}"),
    re.compile("postgres" + "ql://"),
    re.compile("mongo" + "db://"),
]


class TestNoCredentialsInSource:

    def test_no_credentials_in_m1_source(self):
        # AC-R4-6
        src_dir = Path(m1_identity.__file__).parent
        for py_file in sorted(src_dir.glob("*.py")):
            text = py_file.read_text()
            for pattern in _CREDENTIAL_PATTERNS:
                assert not pattern.search(text), (
                    f"{py_file.name}: credential pattern "
                    f"{pattern.pattern!r} detected"
                )

    def test_test_file_labels_key_as_test_only(self):
        # AC-R4-5
        this_file = Path(__file__)
        text = this_file.read_text()
        for pattern in _CREDENTIAL_PATTERNS:
            assert not pattern.search(text), (
                f"credential pattern {pattern.pattern!r} in test file"
            )
        assert "test-key-only-for-unit-tests" in text
        assert "do-not-deploy" in text


# =============================================================================
# Helpers
# =============================================================================

def _build_payload(issue_kwargs: dict, *, iat: int, nbf: int, exp: int,
                   iss: str = ISSUER, aud: str = _AUDIENCE) -> dict:
    """Build a raw JWT payload matching spec R1.1."""
    import uuid as _uuid
    return {
        "iss": iss,
        "sub": issue_kwargs["sub"],
        "aud": aud,
        "iat": iat,
        "nbf": nbf,
        "exp": exp,
        "jti": str(_uuid.uuid4()),
        "firm_id": issue_kwargs["firm_id"],
        "lei": issue_kwargs.get("lei"),
        "crd_number": issue_kwargs["crd_number"],
        "archetype": issue_kwargs["archetype"].value,
        "role": issue_kwargs["role"].value,
        "authority_scope": issue_kwargs["authority_scope"],
        "authority_excludes": issue_kwargs["authority_excludes"],
        "registration_type": issue_kwargs["registration_type"].value,
    }
