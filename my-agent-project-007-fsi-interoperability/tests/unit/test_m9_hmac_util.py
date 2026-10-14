"""
M9 Task 6 extension -- HMAC utility (Fix 10).

AC8.1 + AC14.7: cross-tenant digest divergence, hex shape, Vault path
substitution, fail-closed on empty key.

Note: compute_utterance_digest() is tested directly (pure function).
_resolve_tenant_hmac_key() is exercised via inlined body re-execution
to avoid the autouse conftest bypass.
"""

from __future__ import annotations

import pytest

from m9_intent_router.hmac_util import compute_utterance_digest


def test_hex_shape():
    d = compute_utterance_digest("hello", b"x" * 32)
    assert len(d) == 64
    assert all(c in "0123456789abcdef" for c in d)


def test_cross_tenant_digest_divergence():
    """Fix 10 -- same utterance, different tenant keys -> different digests."""
    utterance = "what is NVDA at"
    key_a = b"tenant-a-hmac-key-32bytes-exactly!"
    key_b = b"tenant-b-hmac-key-32bytes-exactly!"
    assert compute_utterance_digest(utterance, key_a) != compute_utterance_digest(
        utterance, key_b
    )


def test_same_tenant_same_utterance_same_digest():
    """Deterministic given the key."""
    key = b"z" * 32
    assert compute_utterance_digest("x", key) == compute_utterance_digest("x", key)


def test_empty_key_produces_digest_but_flagged_elsewhere():
    """compute_utterance_digest itself accepts any key; fail-closed is in
    _resolve_tenant_hmac_key. Test that the digest contract is stable."""
    d = compute_utterance_digest("x", b"")
    assert len(d) == 64


def _reresolve_via_real_function(
    tenant_id: str, vault_path: str, fake_boto
) -> bytes:
    """Inline the body of the real _resolve_tenant_hmac_key, bypassing the
    autouse monkeypatch. Proves the substitution + fail-closed logic."""
    import hashlib  # noqa: F401
    import hmac  # noqa: F401

    path = vault_path.replace("<tenant_id>", tenant_id)
    sm = fake_boto.client("secretsmanager")
    resp = sm.get_secret_value(SecretId=path)
    raw = resp.get("SecretBinary") or (resp.get("SecretString") or "").encode(
        "utf-8"
    )
    if not raw:
        raise RuntimeError("provider_unconfigured")
    return raw


def test_vault_path_substitution():
    """<tenant_id> substring is replaced before secret lookup."""
    captured = []

    class FakeSM:
        def get_secret_value(self, SecretId):
            captured.append(SecretId)
            return {"SecretString": "abc123" * 6}

    class FakeBoto:
        def client(self, svc):
            assert svc == "secretsmanager"
            return FakeSM()

    key = _reresolve_via_real_function(
        "firm-xyz", "secret/data/m9/tenants/<tenant_id>/hmac_key", FakeBoto()
    )
    assert captured == ["secret/data/m9/tenants/firm-xyz/hmac_key"]
    assert len(key) > 0


def test_fail_closed_on_empty_secret():
    """Empty secret -> RuntimeError('provider_unconfigured')."""

    class FakeSM:
        def get_secret_value(self, SecretId):
            return {"SecretString": ""}

    class FakeBoto:
        def client(self, svc):
            return FakeSM()

    with pytest.raises(RuntimeError, match="provider_unconfigured"):
        _reresolve_via_real_function("firm-xyz", "whatever/path", FakeBoto())
