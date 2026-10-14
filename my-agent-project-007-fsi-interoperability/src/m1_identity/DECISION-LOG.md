# M1 Agent Identity — DECISION LOG

Chronological record of signing / verification / key-handling decisions for
`m1_identity`. Each entry captures the trigger, resolution, and downstream
impact so future maintainers can audit the SemVer path without re-reading
every spec.

---

## D-RS256 — RS256 becomes default; HS256 deprecated; JWKS endpoint exposed

**Area**: Token signing algorithm, key material handling, public-key
distribution.

**Decision**:
- `IdentityService._algorithm` defaults to `"RS256"` via
  `SIGNING_ALGORITHM_DEFAULT`. `"HS256"` is still accepted but emits
  `DeprecationWarning` at construction time (`stacklevel=2`) with a
  pointer to this log entry.
- RS256 private key is read from `os.environ["AID_PRIVATE_KEY_PEM"]`
  only — no CLI flag, no config file, no default. Unencrypted PKCS#8
  or PKCS#1 PEM is accepted; anything encrypted raises `RuntimeError`
  at `__init__` (bubbled up from `serialization.load_pem_private_key`
  with `password=None`).
- Minimum RSA key size is 2048 bits (`_MIN_RSA_KEY_BITS`). Shorter
  keys raise `RuntimeError` at `__init__`. Non-RSA keys (EC, Ed25519,
  DSA) also raise `RuntimeError`.
- Key id (`kid`) is computed as the RFC 7638 JWK Thumbprint (SHA-256
  over the canonical `{"e":...,"kty":"RSA","n":...}` encoding) and is
  emitted as both a JWT header (`kid`) and in the JWKS response.
- `IdentityService.get_jwks()` returns `{"keys": [<jwk>]}` in RFC 7517
  shape with `kty="RSA"`, `use="sig"`, `alg="RS256"`, `kid=<thumbprint>`,
  `n` and `e` base64url-encoded unsigned integers (RFC 7518 §2). For
  `HS256` instances it returns `{"keys": []}` — nothing public to
  publish.

**Rationale** (why):
- Steering Rule 21 mandates asymmetric signing for multi-service
  deployment. HS256 requires every verifier (M6 Trust-Aware Gateway,
  M10 audit logger, M12 supervisor) to hold the same HMAC secret —
  that many copies of a shared secret is a credential-sprawl problem
  incompatible with Rule 20 (zero credentials in git) and Rule 23
  (per-tenant namespace isolation).
- With RS256, M1 holds the only copy of the private key; everyone
  else pulls `GET /.well-known/jwks.json` and verifies with the
  public key alone. Key rotation is a private-key swap on M1 with
  JWKS re-publication; verifiers need no redeploy.
- RFC 7638 thumbprint is deterministic from the key itself, so
  `kid` does not require a side-channel identifier registry.

**Backward compat**:
- `algorithm="HS256"` still works end-to-end. All 77 pre-existing M1
  unit tests were updated to pass `algorithm="HS256"` explicitly and
  to suppress the DeprecationWarning where HS256 use is intentional
  (see `tests/unit/test_m1_identity.py` `svc` fixture).
- The public `__all__` surface is unchanged; `get_jwks` and the
  RS256 constants were additive.

**Algorithm confusion defense**:
- `jwt.decode(..., algorithms=[self._algorithm])` pins the accepted
  algorithm to the constructor argument. An HS256-signed token
  presented to an RS256-configured service raises
  `InvalidAidError(reason="bad_algorithm")` — PyJWT's
  `InvalidAlgorithmError` is the only code path that reaches that
  branch. This is covered by
  `tests/unit/test_m1_rs256_signing.py::test_hs256_token_rejected_when_rs256_configured`.

**Secrecy of private key material**:
- `IdentityService.__repr__` / `__str__` emit only `issuer`,
  `audience`, `alg`, `kid`, and `revoked_count`. They never touch
  `self._rsa_private`, `self._hmac_key`, or the raw PEM bytes from
  the environment. Covered by
  `tests/unit/test_m1_rs256_signing.py::test_private_key_never_in_repr_or_str`.

**Downstream impact**:
- M6 Trust-Aware Gateway verifies AIDs by pulling M1's JWKS over
  mTLS and caching the public key by `kid`.
- M10 audit logger records the `kid` alongside every AID-bearing
  event so a future key rotation is traceable per token.
- M12 supervisor re-verifies AIDs on the specialist-dispatch boundary
  using the same JWKS.

**Decided By**: Trust Layer Specialist.

---
