# M1 Agent Identity — LLMJ Review v2

> Reviewer: 007-trust-agent (self-LLMJ)
> Target: `.kiro/specs/m1-agent-identity.md` (v2, post F1–F12 + R1–R5 fixes)
> Verdict: **8.25/10 — GO**
> Stance: Skeptical verification that v1 required fixes all landed.

---

## SCORES (weighted)

| Dimension | Weight | v1 | v2 | Weighted (v2) |
|-----------|--------|----|----|---|
| 1. Completeness | 25% | 6.5 | 8.5 | 2.125 |
| 2. Accuracy | 20% | 7.0 | 8.5 | 1.700 |
| 3. Security | 20% | 6.5 | 8.5 | 1.700 |
| 4. Testability | 15% | 7.5 | 8.5 | 1.275 |
| 5. Design Alignment | 10% | 6.0 | 8.0 | 0.800 |
| 6. Gaps | 10% | 5.0 | 6.5 | 0.650 |
| **TOTAL** | **100%** | **6.55** | | **8.25/10** |

Threshold: 7.5/10. **GO.**

---

## V1 REQUIRED FIX VERIFICATION

| # | Fix | Landed? | Evidence in v2 |
|---|-----|---------|----------------|
| F1 | Null-LEI wire encoding | ✅ | R1.3, AC-R1-12 |
| F2 | Revocation store failure semantics | ✅ | R3.3 |
| F3 | Remove "replay detection" language | ✅ | §0.2, R1.1 jti col "consumer-driven" |
| F4 | LEI regex duplication called out | ✅ | AC-R5-6, §2.3 comment, T17 |
| F5 | Clock skew leeway | ✅ | R2.3, AC-R2-14..R2-18 |
| F6 | Health non-sensitive declaration | ✅ | AC-R6-1 |
| F7 | InvalidAidError message hygiene | ✅ | AC-R4-8 `str(exc) == exc.reason`, T18 |
| F8 | jti bounds in revoke | ✅ | AC-R3-4 |
| F9 | Enum membership at verify | ✅ | AC-R2-12, AC-R2-13, §2.3 |
| F10 | AST algorithm spelled out | ✅ | §2.7 step-by-step |
| F11 | PyJWT exception mapping | ✅ | §2.10 table, ordering note |
| F12 | Library-vs-service scope | ✅ | §0.1 |

**12/12 required fixes landed.**

## V1 RECOMMENDED FIX VERIFICATION

| # | Fix | Landed? | Evidence |
|---|-----|---------|----------|
| R1 | Example payload | ✅ | R1.4 JSON block |
| R2 | Non-goals | ✅ | §0.2 |
| R3 | authority_scope advisory | ✅ | §0.2, R1.1 notes |
| R4 | Thread safety note | ✅ | R3.4 |
| R5 | Observability deferred | ✅ | §2.12 |

**5/5 recommended fixes landed.**

---

## NEW ISSUES (implementation-time, non-blocking)

### N1. `ConfigDict(extra="forbid")` locks claim set

Adding a future claim (e.g., `jurisdiction`) is a breaking change for verifiers
built against the current model. Current posture is the right security default.
Document "adding a claim requires coordinated release across M1 + all 5
consumers."

### N2. PyJWT `leeway` applies to both exp and nbf

The spec is consistent (AC-R2-14/15 exp, AC-R2-16/17 nbf). PyJWT's single
leeway value correctly covers both. **No action.**

### N3. `options={"require": [...]}` should list ALL R1.1 claims

Because R1.3 says `lei` is always present (possibly null), PyJWT's `require`
list should include `lei`. The spec's R2.1 step 9 defers to Pydantic parsing,
but PyJWT catching it first gives a cleaner error. Build-time recommendation:

```python
options={"require": ["iss","sub","aud","exp","iat","nbf","jti",
                     "firm_id","lei","crd_number","archetype","role",
                     "authority_scope","authority_excludes","registration_type"]}
```

### N4. Add test: "`lei` claim missing entirely" (vs `lei=None`)

Separate from null-LEI. A token where the `lei` key is absent from payload
should raise. Implied by R1.3 + AC-R2-10; recommend explicit test.

### N5. `health()` could include `default_ttl_seconds`, `max_ttl_seconds`

Nice for diagnostics. Not required. **Not blocking.**

### N6. Frozen vocabulary test should use `frozenset` comparison

Order-agnostic. **Implementation note.**

---

## DIMENSION DETAIL (V2)

### Completeness — 8.5/10
All 12 F-fixes landed. Example payload clarifies shape. Non-goals are explicit.
Transport-agnostic note in §0.3. Deducted 1.5 for minor N3/N4.

### Accuracy — 8.5/10
Claim table consistent with M5 FirmConfig. PyJWT exception names match the
real `jwt.exceptions` module. LEI regex matches M5 verbatim. FirmConfig fields
(`crd_number`, `lei`, `registration_type`) spot-checked.

### Security — 8.5/10
Env-only key, 32-byte min, key redaction, fail-closed on every path, algorithm
lock, issuer/audience lock, enum-membership at verify (F9 critical), message
hygiene, jti bounds, clock skew leeway. Deducted 1.5 for typing strictness
(archetype as str in model, validator-enforced — acceptable).

### Testability — 8.5/10
Every AC maps to a test. 19 tasks, ~50 tests. AST algorithm executable.
Performance target quantified. 1,000-token jti uniqueness is concrete.
Deducted 1.5 — hypothesis/property-based testing not in scope, acceptable.

### Design Alignment — 8.0/10
§0.1 reconciles ARCH-07 "FastAPI + Keycloak" expectation with Phase 1 library
scope. §2.6/2.7 enforce rule 9. §2.8 notes rule 19 inapplicability. §0 lists
the 5 consumers per ARCH-09.

### Gaps — 6.5/10
Still missing:
- Key rotation (ops concern, not M1 code — acceptable)
- M5 enum extension behavior (runtime re-read — acceptable)
- Metrics (§2.12 defers to callers — acceptable)

---

## VERDICT

**8.25/10 — GO.**

All 12 required fixes landed. All 5 recommended fixes landed. No new blockers.

Apply N1–N6 as implementation notes during build:
- N1: Document breaking-change posture for claim additions.
- N3: Full `require` list in PyJWT `options`.
- N4: Explicit test for "lei claim absent entirely".
- N5: Optional `health()` extras.
- N6: `frozenset` comparison for vocabulary test.

Proceed to Step 5 (build).

---

*m1-agent-identity-REVIEW-v2.md — Second-pass LLMJ review*
