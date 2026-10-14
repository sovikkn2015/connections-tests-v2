# M2/M4 Policy Engine — LLMJ Review v2 (post-fix)

> Reviewer: 007-trust-agent (LLMJ pass 2)
> Spec under review: `.kiro/specs/m2-m4-policy-engine.md` (v2)
> Stance: HARSH. Re-review after v1 produced 6.88 CONDITIONAL GO.
> Threshold: >= 7.5/10 overall AND all REQUIRED fixes landed.

---

## v1 -> v2 fix verification

| Fix | Status | Evidence in v2 |
|-----|--------|----------------|
| F1 (REQUIRED) R2.2 ordering semantics | LANDED | §2.2 pseudocode + worked example, AC-R2-8 |
| F2 (REQUIRED) ALLOW+ESCALATE | LANDED | AC-R2-8 explicit assertion |
| F3 (REQUIRED) dual_registered intentional | LANDED | R4.10 F3 note |
| F4 (REQUIRED) Missing target/context unified | LANDED | R1.5 + `_require()` + AC-R1-9/10 |
| F5 (REQUIRED) Phase 1 predicate literal | LANDED | R5.2 `_IS_COMPLIANCE_OFFICER` lambda |
| F6 (REC) client.list in read_other | LANDED | R4.4 + AC-R4-4-4 |
| F7 (REQUIRED) Role.system/agent | LANDED | R4.11 + AC-R4-11-* |
| F8 (REQUIRED) Literal PolicyInput examples | LANDED | R1.3 three concrete literals |
| F9 (REC) Meta rules distinguished | LANDED | R4.1 lists 3 meta rule IDs |
| F10 (REQUIRED) Beneficiary allow-listed | LANDED | R9 |
| F11 (REQUIRED) Decision mapping | LANDED | R1.1 table + AC-R1-12 + R11 exports |
| F12 (REC) authority_scope Phase 2 note | LANDED | R4.2 bottom note |
| F13 (REC) Beneficiary drift at __init__ | LANDED | §0.7 + R5.4 + AC-R5-18 |
| F14 (REQUIRED) concentration_pct type | LANDED | R4.7 + AC-R4-7-5..7 |
| F15 (REQUIRED) reason LITERAL | LANDED | §0.3 + R7 + AC-R2-5 + AC-R7-2 |
| F16 (REC) Phase 2 post-validation | LANDED | §0.2 + R7 |
| F17 (REC) strict mode | LANDED | R5.1 + AC-R5-13 |
| F18 (REQUIRED) module vs E2E | LANDED | §0.6 |
| F19 (REQUIRED) Identity vs value | LANDED | AC-R5-10 |
| F20 (REQUIRED) Structural equality | LANDED | AC-R6-1 |
| F21 (REC) Test subclass injection | LANDED | T13 |
| F22 (REC) Golden-vector rule_table | LANDED | AC-R10-5 |
| F23 (REC) Smoke test executable | LANDED | T25 |
| F24 (REQUIRED) rule_kind | LANDED | R10 + AC-R10-6 |
| F25 (REC) FastAPI Phase 2 only | LANDED | §0.1 |
| F26 (REC) Drift concrete cases | LANDED | §0.7 |
| F27 (REQUIRED) authority_excludes rule | LANDED | R4.2 + T4 |
| F28 (REQUIRED) Principal Phase 2 extensions | LANDED | R4.10 F28 note |
| F29 (REC) payment.draft Phase 2 | LANDED | §0.2 + R1.4 |
| F30 (REC) Gap 6 boundary | LANDED | §0.2 |

All 17 REQUIRED fixes: LANDED.
All 13 RECOMMENDED fixes: LANDED.

---

## 1. Completeness — 8.5/10

v1: 6.5. v2: 8.5.

Strong:
- 11-entry rule inventory matches AC-R2-1.
- authority_excludes rule at position 1.
- Role.system/agent explicitly handled (R4.11 + AC-R4-11-*).
- Concrete PolicyInput literals in R1.3.
- `_require()` unifies missing target/context.
- Every rule carries archetypes, actions, rule_kind, decision_kinds,
  wsp_section.

Minor:
- **M1 (minor)** R4.11 "system identity must use compliance_officer"
  should be mirrored to the M6 spec. Cross-spec note, not blocking.
- **M2 (minor)** `unknown_action` meta rule applied BEFORE the loop —
  spec is clear in §2.4 but clarify in list_rules() docstring that
  ordering is for audit; engine uses them differently.

Score: 8.5/10.

---

## 2. Accuracy — 8.5/10

v1: 7.0. v2: 8.5.

Strong:
- Decision to ComplianceDecision mapping pinned + exported as constant.
- concentration_pct strict float check (bool/int/str/out-of-range all
  fail closed).
- Beneficiary drift at construction.
- Engine pseudocode is copy-pasteable.

Minor:
- **M3 (minor)** R2.2 pseudocode compares `inp.identity.archetype`
  (str in AidClaims) against `{a.value for a in rule.archetypes}`
  (set of str). Add a code comment that archetype is stored as string
  in AidClaims (not Archetype enum instance).
- **M4 (minor)** T26 should add explicit assertion that
  AidClaims.authority_excludes is a list[str] field.

Score: 8.5/10.

---

## 3. Security — 8.5/10

v1: 7.0. v2: 8.5.

Strong:
- evaluation_error reason is LITERAL string with AC pinning
  no-substring-leak (AC-R7-2 + AC-R2-5).
- PII-in-reason audit with concrete fixture values (AC-R8-4).
- strict=True opt-in closes unknown-type filter leak.
- §0.6 documents module-vs-E2E boundary.
- No env reads, no network, no log, no time.

Minor:
- **M5 (minor)** AC-R8-4 fixture values should be pinned as test
  constants so every iteration is explicit. Handle in T22.

Score: 8.5/10.

---

## 4. Testability — 8.5/10

v1: 7.0. v2: 8.5.

Strong:
- 26 tasks mapped to ACs.
- Golden-vector test for rule_table (AC-R10-5).
- Executable smoke-test contract (T25).
- Test subclass injection documented (T13).
- Drift tests concrete (T26 + §0.7).

Minor:
- **M6 (minor)** AC-R7-2 should iterate over
  `decision.details.values()` in addition to `decision.reason` — pin
  in T13 body.

Score: 8.5/10.

---

## 5. Design Alignment — 9.0/10

v1: 7.5. v2: 9.0.

Strong:
- §0.1 clarifies FastAPI row is Phase 2.
- R12 Phase 2 migration path concrete.
- Upstream contract (§0.6) is M6's exact handoff.
- rule_applied format matches OPA package path.
- §0.7 drift tests match M1/M3/M5 public surfaces.

No blockers. Score: 9.0/10.

---

## 6. Gaps — 8.5/10

v1: 6.5. v2: 8.5.

Strong:
- 14-item non-goals section.
- payment.draft Phase 1 behavior explicit.
- Gap 6 boundary documented.
- Phase 2 extensions for principal.review_required named.
- authority_scope Phase 2 rule path reserved.
- Role.system/agent Phase 1 behavior nailed down.

Minor:
- **M7 (minor)** Add non-goal: "No `opa eval` subprocess calls in
  Phase 1 tests." Not blocking.

Score: 8.5/10.

---

## Summary of remaining items (all MINOR, none blocking)

- M1: Cross-spec note to M6 about system-identity constraint
- M2: Docstring clarity on list_rules vs engine loop for unknown_action
- M3: Archetype-as-string comment in engine pseudocode
- M4: T26 assertion on AidClaims.authority_excludes field type
- M5: Pin fixture PII constants for AC-R8-4
- M6: Iterate details.values() in T13 substring check
- M7: Non-goal "no opa eval in Phase 1 tests"

Address during build.

---

## Overall

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Completeness | 8.5 | 25% | 2.125 |
| Accuracy | 8.5 | 20% | 1.700 |
| Security | 8.5 | 20% | 1.700 |
| Testability | 8.5 | 15% | 1.275 |
| Design Alignment | 9.0 | 10% | 0.900 |
| Gaps | 8.5 | 10% | 0.850 |
| **TOTAL** | | | **8.55 / 10** |

### Verdict: GO

- All 17 REQUIRED fixes from v1 LANDED.
- All 13 RECOMMENDED fixes LANDED.
- 7 MINOR polish items for build.
- Score 8.55 >> 7.5 threshold.

Build autonomously. The spec is the contract.

---

*m2-m4-policy-engine-REVIEW-v2.md — LLMJ pass 2*
