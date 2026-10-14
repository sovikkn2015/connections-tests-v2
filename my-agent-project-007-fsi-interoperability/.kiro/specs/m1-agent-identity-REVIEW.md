# M1 Agent Identity — LLMJ Review v1

> Reviewer: 007-trust-agent (self-LLMJ, tuned for skepticism)
> Target: `.kiro/specs/m1-agent-identity.md` (v1)
> Verdict: **6.55/10 — CONDITIONAL GO** (requires v2 fixes)
> Stance: Harsh. Production trust code for a regulated platform.

---

## SCORES (weighted)

| Dimension | Weight | Score | Weighted |
|-----------|--------|-------|----------|
| 1. Completeness | 25% | 6.5/10 | 1.625 |
| 2. Accuracy | 20% | 7.0/10 | 1.400 |
| 3. Security | 20% | 6.5/10 | 1.300 |
| 4. Testability | 15% | 7.5/10 | 1.125 |
| 5. Design Alignment | 10% | 6.0/10 | 0.600 |
| 6. Gaps | 10% | 5.0/10 | 0.500 |
| **TOTAL** | **100%** | | **6.55/10** |

Threshold for GO: 7.5/10. Below the bar.

---

## REQUIRED FIXES (blocking)

### F1. AidClaims model — null-LEI wire encoding is IMPLICIT

Spec R1.1 says `lei` is "20 chars if present" but doesn't state what hits the wire
when there's no LEI. Is it JSON null? Is the claim omitted?

**Fix:** Add R1.3 "Null-value encoding":
- `lei=None` → JSON `null` in payload → decoded as `None` in `AidClaims`.
- The `lei` claim is ALWAYS present in the payload (possibly with value `null`),
  never omitted — simplifies consumer parsing (M2/M4).

### F2. Revocation store failure semantics — fail-closed not stated for Phase 2+

Phase 1 is in-memory so can't fail. But the spec must state the contract for
Phase 2 (Redis/PG).

**Fix:** Add R3.3 "Revocation store failure semantics":
- Phase 1 (in-memory): cannot fail.
- Phase 2+: store failure → `InvalidAidError("revoked")` (fail-closed).
  No "assume not revoked" fallback.

### F3. "Replay detection" language in R1.1 is misleading — M1 does NOT detect replays

Spec R1.1 says jti is "used for replay detection and revocation" but R3 only
defines revocation. Replay detection is M6's job.

**Fix:** Update R1.1 language:
- jti is "a unique identifier enabling M6 or other consumers to implement
  single-use/replay protection by calling `revoke(jti)` after use. M1 itself
  does not enforce replay — it is a primitive."

### F4. LEI regex duplication with M5 is not called out

M5's `loader.py` already defines the exact regex. Spec says M1 contains the regex
inline. This is duplication.

**Fix:** §2.3 — explicitly state: "The LEI regex is duplicated inline with an
inline comment 'source of truth: m5_config_loader.FirmConfig.validate_lei'.
Duplication is deliberate to avoid importing a private validator; a drift test
asserts both regexes match." Add AC: "Test asserts M1 LEI regex pattern string
equals M5 LEI regex pattern string."

### F5. Zero clock skew leeway will cause production flaps

AC-R2-3 implicitly uses 0-second leeway. In distributed systems this causes
transient verification failures during NTP sync.

**Fix:** Default leeway = 30 seconds. Add construction param
`clock_skew_leeway_seconds: int = 30` (range 0..300). Add ACs:
- Token with `exp` 20s past but within 30s leeway → verify SUCCEEDS.
- Token with `exp` 40s past (beyond leeway) → raises `expired`.
- Token with `nbf` 20s in future, within leeway → verify SUCCEEDS.
- Token with `nbf` 40s in future → raises `not_yet_valid`.

### F6. Health endpoint — declare audience as non-sensitive

**Fix:** Add note to AC-R6-1: "Audience and issuer are non-sensitive configuration
values. Signing key is sensitive and MUST NOT appear in `health()` output or logs."

### F7. InvalidAidError message must not leak decoded payload contents

Spec says "no stack traces or PII leaked" but doesn't spell out the mechanism.

**Fix:** Strengthen AC-R4-8: "`InvalidAidError` is constructed ONLY with a
`reason` string from the frozen vocabulary. Decoded payload contents (sub,
firm_id, etc.) MUST NOT be passed to the exception. Test asserts that for each
negative scenario, `str(exc)` equals `reason` exactly (no extra text)."

### F8. No bounds on jti in revoke — potential memory DoS

AC-R3-4 covers empty string only. Missing: huge strings, control characters.

**Fix:** Revoke validates jti: non-empty, length ≤ 256, no whitespace or control
chars. Add AC:
- `revoke("")` raises `ValueError`.
- `revoke("x" * 257)` raises `ValueError`.
- `revoke("abc\n")` raises `ValueError`.
- `revoke("abc def")` raises `ValueError`.

### F9. Archetype / registration_type NOT enum-validated at verify time

Critical. Spec §2.3 shows `AidClaims.archetype: str`. Decoded from a forged/malformed
token, a garbage archetype value would pass Pydantic. M2/M4 depend on the claim
being one of the 5 enum values.

**Fix:** `AidClaims.archetype` field validator:
```python
@field_validator("archetype")
@classmethod
def _validate_archetype(cls, v: str) -> str:
    valid = {a.value for a in Archetype}
    if v not in valid:
        raise ValueError(f"archetype must be one of {sorted(valid)}")
    return v
```
Same for `registration_type`. Same for `role` (already an enum via Pydantic).
Add ACs:
- Token with `archetype="lol"` → `InvalidAidError("invalid_claims")` on verify.
- Token with `registration_type="foo"` → `InvalidAidError("invalid_claims")`.

### F10. AST test algorithm for "no cross-module imports" is hand-wavy

Spec says "AST scan" but not what exactly.

**Fix:** §2.7 adds:
"The test iterates every `.py` file under `src/m1_identity/`, calls `ast.parse`,
walks the tree, and for every `ast.Import` / `ast.ImportFrom` node checks the
module prefix. Forbidden prefixes: `m2_`, `m3_`, `m4_`, `m6_`, `m7_`, `m8_`,
`m9_`, `m10_`, `m11_`, `m12_`, `m13_`. Allowed prefix: `m5_config_loader`.
Any forbidden match fails the test with module path and node location."

### F11. Error-mapping table (PyJWT → InvalidAidError.reason) is missing from spec

This is where security bugs live. The spec should make the mapping explicit so
a reviewer can check it line-by-line.

**Fix:** Add §2.10 "PyJWT exception mapping":

| PyJWT Exception | `InvalidAidError.reason` |
|-----------------|---------------------------|
| `InvalidSignatureError` | `bad_signature` |
| `ExpiredSignatureError` | `expired` |
| `ImmatureSignatureError` | `not_yet_valid` |
| `InvalidIssuerError` | `bad_issuer` |
| `InvalidAudienceError` | `bad_audience` |
| `InvalidAlgorithmError` | `bad_algorithm` |
| `MissingRequiredClaimError` | `invalid_claims` |
| `DecodeError` | `malformed` |
| `InvalidTokenError` (catch-all) | `invalid_claims` |
| `pydantic.ValidationError` | `invalid_claims` |

Add AC: "Verify handles each listed PyJWT exception explicitly. No bare `except:`
or `except Exception:` — only the listed classes. Catch-all path is
`InvalidTokenError` which maps to `invalid_claims`."

### F12. Scope note — M1 is a library, not a service, in Phase 1

ARCH-07 says "FastAPI + Keycloak" for M1. Spec builds a class, not a FastAPI app.
The scope difference must be declared explicitly so reviewers don't think it's
missing.

**Fix:** Add to §0 Context:
"Phase 1 scope: M1 ships as an importable Python library (class `IdentityService`).
No FastAPI app in Phase 1 — M6 (MCP Gateway) imports `IdentityService` directly
and wires it into its FastAPI middleware. A standalone FastAPI facade for M1 is
out of scope until there is a consumer outside the trust layer (e.g., an external
HITL UI in Phase 3+). Keycloak integration is deferred to Phase 2 when algorithm
migrates from HS256 to RS256."

---

## RECOMMENDED FIXES (non-blocking, should still land)

### R1. Add example AidClaims payload

Shows exactly what a decoded token looks like. Helps reviewers eyeball shape.

### R2. Non-goals section

State explicitly: M1 does not issue refresh tokens, does not do cert issuance
(cert-manager), does not talk to Keycloak (Phase 2), does not store user passwords,
does not do authentication of humans (that's Keycloak).

### R3. authority_scope / authority_excludes are advisory strings

State M1 does NOT validate these against a catalog — M2 owns that. M1 just carries
them through unchanged.

### R4. Note on thread safety

Python GIL makes `set.add` atomic — no lock required in Phase 1. Phase 2 Redis/PG
provides its own atomicity.

### R5. Observability hooks

Future modules (M6) will want metrics on issue/verify counts and latencies. The
spec can note this as deferred (M1 returns; the caller measures) without adding
complexity now.

---

## DIMENSION-BY-DIMENSION DETAIL

### Completeness — 6.5/10
Missing: replay semantics (F3), clock leeway (F5), revocation failure semantics
(F2), null-LEI wire (F1), PyJWT error mapping (F11), library-vs-service scope (F12).

### Accuracy — 7.0/10
Claims align with ARCH-09. PyJWT API usage correct. FirmConfig fields correct.
Issue: duplication of LEI regex not called out (F4).

### Security — 6.5/10
Good: env-only key, 32-byte min, fail-closed, algorithm lock, issuer/audience lock.
Bad: archetype/registration_type decoded as bare strings (F9), no bounds on jti
in revoke (F8), InvalidAidError message hygiene not spelled out (F7), 0-second
clock skew unsafe (F5).

### Testability — 7.5/10
Strong: deterministic ACs, `pytest.raises(match=)`, 1,000-token uniqueness,
perf target. Weak: AST algorithm under-specified (F10).

### Design Alignment — 6.0/10
Aligns with ARCH-09 row, steering rules 9 and 20. Misalignment: ARCH-07 implies
FastAPI service but Phase 1 is a library — needs explicit scope note (F12).

### Gaps — 5.0/10
Missing: HS256→RS256 migration detail, key rotation, observability hooks (R5),
behavior when M5 adds new archetype values.

---

## VERDICT

**6.55/10 — CONDITIONAL GO.**

Structure is sound. 12 required fixes (F1–F12) must land before build. F9, F5,
F3, F1, F11 are the most critical — they touch the trust contract directly.

Rewrite the spec addressing all F1–F12 required fixes plus R1–R5 recommended
fixes. Target v2: 8.0+/10.

---

*m1-agent-identity-REVIEW.md (v1) — First-pass LLMJ review*
