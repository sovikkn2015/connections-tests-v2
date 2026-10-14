# M1 Agent Identity — Spec (v2)

> Module: M1 Agent Identity
> Phase: 1 (Trust Layer)
> Agent: 007-trust-agent
> Status: v2 (post-review, addresses F1–F12 + R1–R5)
> Source docs: ARCH-09 (M1 row), ARCH-07 (stack), 007-consolidated-design-and-plan.md (Part 3 — Trust Layer), IMPL-06

---

## 0. CONTEXT AND SCOPE

M1 is the first module of the trust layer (THE MOAT). Every MCP call in 007 begins
with "WHO is asking?" — answered by verifying an Agent Identity Document (AID)
issued by M1.

Five downstream modules consume M1:
- M2 (Authority Policy) — reads AID claims to evaluate ALLOW/DENY/ESCALATE
- M4 (MNPI Policy) — reads archetype/role to filter fields
- M6 (MCP Gateway) — verifies AID on every incoming request
- M9 (Intent Router) — attaches actor identity to intent classification
- M10 (Audit Logger) — records actor_id (AID hash) on every audit entry

M1 calls nothing. It is a pure trust primitive: issue, verify, revoke.

### 0.1 Phase 1 scope (library, HS256, in-memory revocation)

Addresses F12. Phase 1 ships M1 as an importable Python library (class
`IdentityService`). No standalone FastAPI service in Phase 1 — M6 imports
`IdentityService` directly and wires it into FastAPI middleware. A standalone
REST facade is deferred until a consumer outside the trust layer (e.g., an
external HITL UI in Phase 3+) needs it.

- Phase 1: HMAC-SHA256 (HS256), in-memory revocation set, library only.
- Phase 2: RS256 (asymmetric), Keycloak as issuer, revocation backed by
  Redis or PostgreSQL. The `IdentityService` class signature and `AidClaims`
  shape are stable across migration — algorithm is a constructor param;
  revocation set is a protocol swap.

### 0.2 Non-goals

- M1 does NOT issue refresh tokens.
- M1 does NOT perform mTLS cert issuance (cert-manager does).
- M1 does NOT call Keycloak in Phase 1.
- M1 does NOT store user passwords (Keycloak will, Phase 2).
- M1 does NOT authenticate humans — it trusts the caller and issues an AID.
- M1 does NOT validate `authority_scope` / `authority_excludes` against any
  action catalog — M2 owns that. M1 carries them through unchanged. (R3)
- M1 does NOT detect replays. The `jti` is a unique identifier that consumers
  (M6) can use to implement single-use by calling `revoke(jti)` after use. (F3)

### 0.3 Transport-agnostic

M1 returns JWTs as bare strings. How they reach M6 (Authorization header,
payload field, etc.) is M6's concern. M1 has no HTTP surface in Phase 1.

---

## 1. REQUIREMENTS

### R1. AID Issuance

The service issues Agent Identity Documents (AIDs) as signed JWTs containing
FSI-specific claims. An AID binds an actor to a firm, an archetype, and an
authority envelope.

#### R1.1 Required JWT claims (RFC 7519 + FSI extensions)

| Claim | Type | Source | Required | Purpose |
|-------|------|--------|----------|---------|
| `iss` | string | Fixed: `007-fsi-platform` | yes | Issuer lock. |
| `sub` | string | Caller-supplied actor id | yes | Subject — the actor. |
| `aud` | string | Configured audience (e.g., `007-mcp-gateway`) | yes | Audience lock. |
| `exp` | int | Computed from TTL | yes | Expiration. |
| `iat` | int | Server clock at issue | yes | Issued-at. |
| `nbf` | int | == `iat` | yes | Not-before. |
| `jti` | string (UUID4) | Generated per token | yes | JWT ID — enables consumer-driven single-use/revocation tracking. (F3) |
| `firm_id` | string | From FirmConfig | yes | Multi-tenant scope. Non-empty. |
| `lei` | string or null | From FirmConfig.lei | yes (may be null) | LEI (ISO 17442). 20 chars if non-null. |
| `crd_number` | string | From FirmConfig.crd_number | yes | CRD number. Non-empty. |
| `archetype` | string | M5 `Archetype` enum value | yes | tier1..tier5. |
| `role` | string | M1 `Role` enum value | yes | Operational role. |
| `authority_scope` | list[string] | Caller-supplied | yes | Actions permitted. Not validated by M1. |
| `authority_excludes` | list[string] | Caller-supplied | yes | Actions forbidden. Not validated by M1. |
| `registration_type` | string | M5 `RegistrationType` enum value | yes | `ria_only`, `bd_only`, `dual_registered`. |

#### R1.2 Acceptance criteria (R1)

- **AC-R1-1:** `issue(...)` returns a JWT string (3 base64url segments separated by `.`).
- **AC-R1-2:** Decoded token contains ALL claims from R1.1 with values matching inputs.
- **AC-R1-3:** `iss == "007-fsi-platform"` always. Caller cannot override.
- **AC-R1-4:** `aud` equals the service's configured audience. Caller cannot override.
- **AC-R1-5:** `jti` is a valid UUID4. 1,000 tokens → 1,000 unique jtis.
- **AC-R1-6:** `exp - iat == ttl_seconds` (default 900 = 15 min).
- **AC-R1-7:** `nbf == iat`.
- **AC-R1-8:** `archetype` input validated against M5 `Archetype` enum — invalid raises `ValueError`.
- **AC-R1-9:** `role` input validated against M1 `Role` enum — invalid raises `ValueError`.
- **AC-R1-10:** `registration_type` input validated against M5 `RegistrationType` enum — invalid raises `ValueError`.
- **AC-R1-11:** Empty `firm_id` or empty `crd_number` raises `ValueError`.
- **AC-R1-12:** Malformed LEI (not matching `^[A-Z0-9]{18}[0-9]{2}$`) raises `ValueError`. `lei=None` is accepted.
- **AC-R1-13:** `ttl_seconds` outside `[60, 86400]` raises `ValueError`. Default: 900.

#### R1.3 Null-value encoding (F1)

- `lei=None` → JSON `null` in the payload → decoded as `None` in `AidClaims`.
- The `lei` claim is ALWAYS present in the payload (possibly with value `null`),
  never omitted.

#### R1.4 Example payload (R1 recommended)

Decoded payload for a Tier 4 RIA advisor:

```json
{
  "iss": "007-fsi-platform",
  "sub": "sarah.chen@acmewm.com",
  "aud": "007-mcp-gateway",
  "iat": 1713000000,
  "nbf": 1713000000,
  "exp": 1713000900,
  "jti": "9c4f0c2e-6b1e-4d9a-8a2b-7a3c6f5e0f11",
  "firm_id": "CRD-123456",
  "lei": "549300ACMEWM1234RIA0",
  "crd_number": "CRD-123456",
  "archetype": "tier4_independent_ria",
  "role": "advisor",
  "authority_scope": ["portfolio.read", "research.create", "meeting.prep"],
  "authority_excludes": ["order.submit_without_hitl", "wire.initiate"],
  "registration_type": "ria_only"
}
```

### R2. AID Verification

#### R2.1 Verification pipeline

`verify(token: str) -> AidClaims` executes the following checks. Any failure
raises `InvalidAidError`. Never returns a claim dict on failure.

1. Token structure: three dot-separated base64url segments.
2. Signature: HMAC-SHA256 over header.payload using the signing key.
3. Algorithm lock: header `alg == "HS256"`. Rejects `"none"`, `"RS256"`, etc.
4. Expiration: `exp > now - leeway`. Beyond → `expired`.
5. Not-before: `nbf <= now + leeway`. Beyond → `not_yet_valid`.
6. Issuer: `iss == "007-fsi-platform"`. Otherwise → `bad_issuer`.
7. Audience: `aud == configured_audience`. Otherwise → `bad_audience`.
8. Revocation: `jti NOT IN revocation_set` (only after signature + exp + iss + aud pass).
9. Claim parse: remaining payload parsed into `AidClaims` Pydantic model
   (archetype / registration_type enum-membership validated here). Failure →
   `invalid_claims`.

Revocation is checked AFTER signature/issuer/audience to prevent a revocation
oracle for spoofed tokens.

#### R2.2 Acceptance criteria (R2)

- **AC-R2-1:** Valid, fresh token returns an `AidClaims` instance with all claims.
- **AC-R2-2:** Token signed with the wrong key → `InvalidAidError("bad_signature")`.
- **AC-R2-3:** Token with `exp` past (beyond leeway) → `InvalidAidError("expired")`.
- **AC-R2-4:** Token with `iss != "007-fsi-platform"` → `InvalidAidError("bad_issuer")`.
- **AC-R2-5:** Token with `aud` not matching configured audience → `InvalidAidError("bad_audience")`.
- **AC-R2-6:** Token with `alg: "none"` → `InvalidAidError("bad_algorithm")`.
- **AC-R2-7:** Tampered payload (any bit flip) → `InvalidAidError("bad_signature")`.
- **AC-R2-8:** Revoked token (jti in revocation set) → `InvalidAidError("revoked")`.
- **AC-R2-9:** Malformed token → `InvalidAidError("malformed")`.
- **AC-R2-10:** Token missing a required claim → `InvalidAidError("invalid_claims")`.
- **AC-R2-11:** `verify` NEVER returns a success-like value on failure. Every error
  path raises.
- **AC-R2-12 (F9):** Token with `archetype: "lol"` → `InvalidAidError("invalid_claims")`.
- **AC-R2-13 (F9):** Token with `registration_type: "foo"` → `InvalidAidError("invalid_claims")`.

#### R2.3 Clock skew leeway (F5)

- Default leeway: 30 seconds.
- Configurable: `clock_skew_leeway_seconds: int = 30`, range `[0, 300]`.
- **AC-R2-14:** Token with `exp` 20s past (within default 30s leeway) → verify SUCCEEDS.
- **AC-R2-15:** Token with `exp` 40s past → `InvalidAidError("expired")`.
- **AC-R2-16:** Token with `nbf` 20s in future (within leeway) → verify SUCCEEDS.
- **AC-R2-17:** Token with `nbf` 40s in future → `InvalidAidError("not_yet_valid")`.
- **AC-R2-18:** `clock_skew_leeway_seconds` outside `[0, 300]` at construction → `ValueError`.

### R3. Revocation

#### R3.1 Behavior

- `revoke(jti: str) -> None` adds `jti` to an in-memory revocation set.
- `is_revoked(jti: str) -> bool` returns `True` if `jti` is in the set.
- Revocation is idempotent.
- A revoked, otherwise-valid token's `verify` raises `InvalidAidError("revoked")`.

#### R3.2 Acceptance criteria (R3)

- **AC-R3-1:** After `revoke(jti)`, `is_revoked(jti) == True`.
- **AC-R3-2:** After `revoke(jti)`, `verify(token_with_that_jti)` raises `InvalidAidError("revoked")`.
- **AC-R3-3:** `revoke(jti)` called twice does not raise.
- **AC-R3-4 (F8):** `revoke(jti)` validates jti input:
  - empty string → `ValueError`
  - length > 256 → `ValueError`
  - whitespace or control characters → `ValueError`

#### R3.3 Revocation store failure semantics (F2)

- Phase 1 (in-memory): cannot fail — `set` operations do not raise.
- Phase 2+ (external store): store unreachable → `InvalidAidError("revoked")`
  (fail-closed). No "assume not revoked" fallback.

#### R3.4 Thread safety (R4 recommended)

Python GIL makes `set.add` / `set.__contains__` atomic within a single process.
No lock required in Phase 1. Phase 2 Redis/PG provides its own atomicity.

### R4. Security

#### R4.1 Signing key management

- **AC-R4-1:** Signing key read ONLY from `os.environ["AID_SIGNING_KEY"]` at construction.
  No default, no CLI flag, no config file.
- **AC-R4-2:** Missing `AID_SIGNING_KEY` → `RuntimeError` at construction.
- **AC-R4-3:** `AID_SIGNING_KEY` shorter than 32 bytes → `RuntimeError`.
- **AC-R4-4:** Key stored only as instance attribute (`self._key`). NEVER logged
  or serialised in `repr`. No `__str__` defined.
- **AC-R4-5:** Test fixtures use a key literal containing `test-key-only-for-unit-tests`
  and `do-not-deploy` — at least 32 bytes.
- **AC-R4-6:** No signing key, API key, token, password, or connection string
  appears anywhere in `src/m1_identity/**` or `tests/unit/test_m1_identity.py`.

#### R4.2 Fail-closed invariant

- **AC-R4-7:** Every error path in `verify` raises `InvalidAidError`. No bare
  `except:`. No `except Exception:` fall-through. Only explicit exceptions
  listed in §2.10.
- **AC-R4-8 (F7):** `InvalidAidError` constructed ONLY with a `reason` string
  from the frozen vocabulary. Decoded payload contents MUST NOT be passed to
  the exception. Test asserts `str(exc) == exc.reason` for every negative
  scenario — no extra text, no PII leakage.

Frozen vocabulary:
```
malformed, bad_signature, bad_algorithm, expired, not_yet_valid,
bad_issuer, bad_audience, revoked, invalid_claims
```

#### R4.3 Token lifetime controls

- **AC-R4-9:** Default TTL = 900 seconds (15 min).
- **AC-R4-10:** Hard cap TTL = 86,400 seconds (24 hr). Above → `ValueError`.
- **AC-R4-11:** TTL < 60 seconds → `ValueError`.

### R5. Integration

- **AC-R5-1:** `archetype` claim uses `m5_config_loader.Archetype` values (5 members).
- **AC-R5-2:** `registration_type` claim uses `m5_config_loader.RegistrationType` values (3 members).
- **AC-R5-3:** `issue_from_firm_config(*, firm_config, sub, role, archetype, authority_scope, authority_excludes, ttl_seconds=None)` accepts `m5_config_loader.FirmConfig` and derives:
  - `firm_id = firm_config.crd_number`
  - `lei = firm_config.lei`
  - `crd_number = firm_config.crd_number`
  - `registration_type = firm_config.registration_type`
  Convenience wrapper; canonical path is `issue(...)`. Tests exercise BOTH.
- **AC-R5-4:** M1 does NOT import from M2, M3, M4, M6, M7, M8, M9, M10, M11, M12, M13.
  Verified by AST scan (§2.7).
- **AC-R5-5:** AID claims provide sub + firm_id + archetype + role so M10 can
  construct `AuditEntry`. M1 does not import M3.
- **AC-R5-6 (F4):** LEI regex is inlined in M1 with a source-of-truth comment
  pointing to `m5_config_loader`. A drift test asserts the M1 regex pattern
  string equals the M5 regex pattern string at runtime.

### R6. Operational

- **AC-R6-1 (F6):** `IdentityService.health()` returns:
  ```python
  {
      "status": "ok",
      "alg": "HS256",
      "issuer": "007-fsi-platform",
      "audience": "<configured>",
      "revoked_count": N,
      "clock_skew_leeway_seconds": 30
  }
  ```
  Audience and issuer are non-sensitive config. Signing key MUST NOT appear.
- **AC-R6-2:** Token round-trip (issue + verify) completes in < 50 ms on
  local developer hardware.
- **AC-R6-3:** Public API surface equals `__all__` in `m1_identity/__init__.py`.

---

## 2. DESIGN

### 2.1 Directory layout

```
my-agent-project-007-fsi-interoperability/
  src/
    m1_identity/
      __init__.py          # Public API re-exports
      claims.py            # AidClaims, Role, InvalidAidError, ISSUER, LEI_PATTERN
      service.py           # IdentityService + constants
  tests/
    unit/
      test_m1_identity.py  # All R1-R6 acceptance criteria
```

### 2.2 Public API

```python
from m1_identity.claims import (
    AidClaims, Role, InvalidAidError, ISSUER, LEI_PATTERN,
)
from m1_identity.service import (
    IdentityService,
    DEFAULT_TTL_SECONDS,         # 900
    MAX_TTL_SECONDS,             # 86400
    MIN_TTL_SECONDS,             # 60
    DEFAULT_CLOCK_SKEW_SECONDS,  # 30
    MAX_CLOCK_SKEW_SECONDS,      # 300
    SIGNING_ALGORITHM_DEFAULT,   # "HS256"
)
```

`__all__` lists exactly these names.

### 2.3 `claims.py` shape

```python
ISSUER: str = "007-fsi-platform"

# Source of truth: m5_config_loader.FirmConfig.validate_lei
# Duplicated here to avoid importing a private validator.
# Drift test asserts this pattern == the M5 pattern at runtime.
LEI_PATTERN: str = r"^[A-Z0-9]{18}[0-9]{2}$"

class Role(str, Enum):
    advisor = "advisor"
    compliance_officer = "compliance_officer"
    system = "system"
    agent = "agent"

class InvalidAidError(Exception):
    """Fail-closed AID verification error. .reason from frozen vocabulary."""
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

class AidClaims(BaseModel):
    model_config = ConfigDict(extra="forbid")
    iss: str
    sub: str = Field(..., min_length=1)
    aud: str = Field(..., min_length=1)
    exp: int
    iat: int
    nbf: int
    jti: str = Field(..., min_length=1)

    firm_id: str = Field(..., min_length=1)
    lei: Optional[str] = None
    crd_number: str = Field(..., min_length=1)
    archetype: str          # enum-validated below
    role: Role
    authority_scope: list[str] = Field(default_factory=list)
    authority_excludes: list[str] = Field(default_factory=list)
    registration_type: str  # enum-validated below

    # Validators:
    # - iss == ISSUER
    # - lei matches LEI_PATTERN if not None
    # - archetype in m5_config_loader.Archetype values
    # - registration_type in m5_config_loader.RegistrationType values
```

The archetype / registration_type validators import from `m5_config_loader`
(allowed). (F9)

### 2.4 `service.py` shape

```python
DEFAULT_TTL_SECONDS: int = 900
MIN_TTL_SECONDS: int = 60
MAX_TTL_SECONDS: int = 86_400
DEFAULT_CLOCK_SKEW_SECONDS: int = 30
MAX_CLOCK_SKEW_SECONDS: int = 300
SIGNING_ALGORITHM_DEFAULT: str = "HS256"

_SIGNING_KEY_ENV: str = "AID_SIGNING_KEY"
_MIN_KEY_BYTES: int = 32
_MAX_JTI_LEN: int = 256

class IdentityService:
    def __init__(
        self, *,
        audience: str,
        algorithm: str = SIGNING_ALGORITHM_DEFAULT,
        default_ttl_seconds: int = DEFAULT_TTL_SECONDS,
        max_ttl_seconds: int = MAX_TTL_SECONDS,
        clock_skew_leeway_seconds: int = DEFAULT_CLOCK_SKEW_SECONDS,
    ) -> None: ...

    def __repr__(self) -> str: ...   # Never leaks key

    def issue(self, *, sub, firm_id, crd_number, archetype, role,
              registration_type, authority_scope, authority_excludes,
              lei=None, ttl_seconds=None) -> str: ...

    def issue_from_firm_config(self, *, firm_config, sub, role, archetype,
                                authority_scope, authority_excludes,
                                ttl_seconds=None) -> str: ...

    def verify(self, token: str) -> AidClaims: ...
    def revoke(self, jti: str) -> None: ...
    def is_revoked(self, jti: str) -> bool: ...
    def health(self) -> dict: ...
```

### 2.5 Security constraints

| Constraint | Enforcement |
|-----------|------------|
| No credentials in code | Signing key from env only. |
| Algorithm lock | PyJWT `algorithms=["HS256"]`. |
| Issuer lock | `issuer="007-fsi-platform"` to `jwt.decode`. |
| Audience lock | `audience=<configured>` to `jwt.decode`. |
| Fail-closed | Every error raises `InvalidAidError`. |
| Key length | ≥ 32 bytes at construction. |
| Key leakage | `__repr__` excludes key. No `__str__`. |
| Test key | `"test-key-only-for-unit-tests-do-not-deploy-000000"` (50 chars). |
| Enum validation at verify | archetype + registration_type validated against M5 enums (F9). |
| Error hygiene | `str(exc) == exc.reason` (F7). |

### 2.6 Module boundary

Allowed in `src/m1_identity/**`:
- stdlib: `__future__`, `datetime`, `enum`, `hashlib`, `os`, `re`, `typing`, `uuid`
- third-party: `jwt` (PyJWT), `pydantic`
- project: `m5_config_loader` only

Forbidden: `m2_*`, `m3_*`, `m4_*`, `m6_*`, `m7_*`, `m8_*`, `m9_*`, `m10_*`, `m11_*`, `m12_*`, `m13_*`.

### 2.7 AST cross-module import test (F10)

For each `.py` file under `src/m1_identity/`:
1. Read source, call `ast.parse(source)`.
2. Walk tree with `ast.walk`.
3. For every `ast.Import`: inspect each `alias.name`; check against forbidden prefixes.
4. For every `ast.ImportFrom`: inspect `node.module`; check against forbidden prefixes.

Forbidden prefixes (exact list):
```
m2_, m3_, m4_, m6_, m7_, m8_, m9_, m10_, m11_, m12_, m13_
```

Allowed project prefix: `m5_config_loader`.

Any forbidden match fails the test with `{file_path}:{lineno}: forbidden import {module}`.

### 2.8 OPA/Rego interaction

M1 contains zero Rego. Steering rule 19 (`wsp_section` annotation on every OPA
rule) applies to modules producing Rego. M1 produces none, so no annotation is
required. M2/M4 Rego rules consuming AID claims will carry their own
annotations.

### 2.9 Error reason vocabulary (frozen)

```
malformed         # Token structure invalid
bad_signature     # Signature check failed
bad_algorithm     # Header alg not allowed
expired           # exp < now - leeway
not_yet_valid     # nbf > now + leeway
bad_issuer        # iss != "007-fsi-platform"
bad_audience      # aud != configured audience
revoked           # jti in revocation set
invalid_claims    # Pydantic validation failed (incl. enum-membership)
```

A test enumerates these strings and asserts the frozen set.

### 2.10 PyJWT exception mapping (F11)

| PyJWT Exception | `reason` |
|-----------------|----------|
| `InvalidSignatureError` | `bad_signature` |
| `ExpiredSignatureError` | `expired` |
| `ImmatureSignatureError` | `not_yet_valid` |
| `InvalidIssuerError` | `bad_issuer` |
| `InvalidAudienceError` | `bad_audience` |
| `InvalidAlgorithmError` | `bad_algorithm` |
| `MissingRequiredClaimError` | `invalid_claims` |
| `DecodeError` | `malformed` |
| `InvalidTokenError` (catch-all within PyJWT hierarchy) | `invalid_claims` |
| `pydantic.ValidationError` (post-decode) | `invalid_claims` |

Order of `except` clauses matters — PyJWT uses class hierarchy. Subclasses must
come before their base. `InvalidTokenError` is the base and MUST be the last
PyJWT clause.

### 2.11 Revocation check ordering

Verify pipeline checks revocation AFTER signature/exp/iss/aud but BEFORE Pydantic
claim parse:
- Unsigned or forged jti cannot probe the revocation set (no oracle).
- Revocation rejection is cheaper than claim parse.

### 2.12 Observability note (R5 recommended)

M1 methods are synchronous and return. Callers (M6) measure latencies and count
outcomes via their own metrics layer. M1 emits no metrics in Phase 1.

---

## 3. TASKS

Each task produces implementation + tests together.

| # | Task | Files | Covers ACs |
|---|------|-------|------------|
| T1 | Package skeleton | 3 files | — |
| T2 | `claims.py`: ISSUER, LEI_PATTERN, Role, InvalidAidError, AidClaims (with enum-membership validators) | `claims.py` | R1.1, AC-R1-3, AC-R1-12, AC-R2-12, AC-R2-13, AC-R4-8 shape, AC-R5-6 |
| T3 | `IdentityService.__init__` + env loading + `__repr__` + clock skew param | `service.py` | AC-R4-1..R4-4, AC-R4-9..R4-11, AC-R2-18 |
| T4 | `issue(...)` with TTL enforcement and all claims | `service.py` | AC-R1-1..R1-13 |
| T5 | `issue_from_firm_config(...)` | `service.py` | AC-R5-1..R5-3 |
| T6 | `verify(token)` with explicit PyJWT exception mapping + leeway + revocation order | `service.py` | AC-R2-1..R2-17, AC-R4-7, AC-R4-8 |
| T7 | `revoke`, `is_revoked`, `health` with jti validation | `service.py` | AC-R3-1..R3-4, AC-R6-1 |
| T8 | `__init__.py` with re-exports + `__all__` | `__init__.py` | AC-R6-3 |
| T9 | Issuance tests (happy path, all claims, 1,000 jti uniqueness, TTL bounds, null LEI) | `test_m1_identity.py` | R1 ACs |
| T10 | Verification tests (happy + 13 negative) | `test_m1_identity.py` | R2 ACs |
| T11 | Revocation tests (4 ACs incl. jti validation edge cases) | `test_m1_identity.py` | R3 ACs |
| T12 | Security tests (env, key length, repr, no prod keys, frozen vocab) | `test_m1_identity.py` | R4 ACs |
| T13 | `issue_from_firm_config` test with real `FirmConfig` | `test_m1_identity.py` | R5 ACs |
| T14 | AST test — no forbidden imports (§2.7) | `test_m1_identity.py` | AC-R5-4 |
| T15 | Frozen error reason vocabulary + PyJWT mapping table test | `test_m1_identity.py` | AC-R4-8, §2.10 |
| T16 | Clock skew leeway tests (within / beyond on exp and nbf) | `test_m1_identity.py` | AC-R2-14..R2-17 |
| T17 | LEI regex drift test: M1 LEI_PATTERN == M5 regex | `test_m1_identity.py` | AC-R5-6 |
| T18 | InvalidAidError message hygiene: `str(exc) == exc.reason` | `test_m1_identity.py` | AC-R4-8 |
| T19 | Perf sanity (issue + verify < 50 ms) | `test_m1_identity.py` | AC-R6-2 |

Test count target: ~50. Every AC maps to at least one test.

### 3.1 Test fixture policy

```python
_TEST_KEY = "test-key-only-for-unit-tests-do-not-deploy-000000"  # 50 chars

@pytest.fixture
def svc(monkeypatch):
    monkeypatch.setenv("AID_SIGNING_KEY", _TEST_KEY)
    return IdentityService(audience="007-mcp-gateway")
```

Literal contains `test-key-only-for-unit-tests` and `do-not-deploy`. No
production-shaped key anywhere (no AKIA, no long hex, no `sk-`, no `Bearer `).

---

## 4. REVIEW FIX TRACEABILITY

| Review Fix | Spec Section Addressing It |
|-----------|----------------------------|
| F1 — null-LEI encoding | R1.3, AC-R1-12 |
| F2 — revocation store failure semantics | R3.3 |
| F3 — remove "replay detection" language | §0.2 non-goals, R1.1 jti description |
| F4 — LEI regex duplication | AC-R5-6, §2.3 LEI_PATTERN comment, T17 |
| F5 — clock skew leeway | R2.3, AC-R2-14..R2-18, §2.4 constructor, T16 |
| F6 — health non-sensitive declaration | AC-R6-1 |
| F7 — InvalidAidError message hygiene | AC-R4-8, T18 |
| F8 — jti input bounds in revoke | AC-R3-4 |
| F9 — enum-membership at verify | AC-R2-12, AC-R2-13, §2.3 validators |
| F10 — AST test algorithm | §2.7 |
| F11 — PyJWT exception mapping table | §2.10, T15 |
| F12 — library-vs-service scope | §0.1 |
| R1 — example payload | R1.4 |
| R2 — non-goals | §0.2 |
| R3 — authority_scope advisory | §0.2 non-goals |
| R4 — thread safety note | R3.4 |
| R5 — observability deferred | §2.12 |

---

## 5. DESIGN DOC TRACEABILITY

| Design doc requirement | Spec section |
|------------------------|--------------|
| ARCH-09 M1 row: issues/verifies/revokes AIDs, JWT with FSI claims | R1, R2, R3 |
| ARCH-09: Called by M2, M4, M6, M9, M10 (5 consumers) | §0 |
| ARCH-07: Python + FastAPI + Keycloak | §0.1 (Phase 1 = library; FastAPI deferred; Keycloak = Phase 2) |
| Consolidated design Part 3: "M1: WHO is asking?" | §0 |
| Steering rule 9: no cross-module imports | AC-R5-4, §2.6, §2.7 |
| Steering rule 20: zero credentials in git | R4.1 |
| Steering rule 5: OPA/Rego for compliance (not LLM) | §2.8 |
| Steering rule 19: `wsp_section` on OPA rules | §2.8 (M1 has no OPA) |
| IMPL-06: Phase 1 trust layer foundation | §0 |

---

*m1-agent-identity.md (v2) — M1 Agent Identity Spec*
*Project 007 FSI Interoperability Platform*
