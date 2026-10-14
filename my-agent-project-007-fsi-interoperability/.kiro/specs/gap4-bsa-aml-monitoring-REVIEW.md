# Gap 4 — BSA/AML Monitoring — LLMJ Review v1

> Review of `.kiro/specs/gap4-bsa-aml-monitoring.md` (v1).
> Target: 7.5+/10 weighted for GO.

---

## FINDINGS

### BLOCKING (F)

**F1 (CRITICAL) — Float vs Decimal for $10,000 threshold.**
v1 uses `float` for `amount_usd`. 10000.0 is representable but
aggregate sums drift. Comparisons like `>= 10000.0` after summing
three 3333.34 transactions fail in edge cases. Must use
`decimal.Decimal` with string-conversion from M3 Transaction's
float `amount`.

**F2 (CRITICAL) — Anti-tipping-off invariants under-specified.**
31 U.S.C. §5318(g)(2) is a felony. v1 says "alerts route to
compliance officer" but does not define (a) what the
`AuditEntry.action` string is (must be uniform across CTR/SAR
alert types so log observers cannot reverse-engineer the
presence of a SAR), (b) that `target_type` must NOT say
"sar_filing", (c) that the advisor- and client-facing audit
trail partition excludes Gap 4 entries. Need explicit Python-
testable invariants.

**F3 — `route_to` as free-form string is dangerous.**
v1 has `route_to: str`. A rename bug or a misconfiguration could
route a SAR to `"advisor"`. Type-system enforcement required:
`route_to: Literal["compliance_officer"]`.

**F4 — Reason code vocabulary not frozen.**
v1 has `reason_code: str`. Same drift risk as M10's VALID_REASONS.
Lock to a `frozenset` enumerated in the spec, validated at
construction.

**F5 — `matched_transactions` duplicate protection.**
If the same txn is matched twice (bug in de-dup), alert amount
is double-counted. v1 doesn't specify a uniqueness invariant.

**F6 — `BsaAmlConfig.enabled=False` behavior is vague.**
v1 says "short-circuits" but does not enumerate: no store writes,
no audit emission, no background work. Tests must verify ZERO
side effects. Spec must enumerate.

**F7 — Window boundary semantics unspecified.**
v1 has `within(start, end)` without stating whether the bounds
are inclusive. FinCEN's 24-hour aggregate rule is interpreted
as a rolling wall-clock window. Need a precise inclusive/
exclusive rule with a parametrized test around the boundary
microsecond.

**F8 — Rego rules without wsp_section annotations.**
Steering rule 19 requires every Rego rule to have a
`wsp_section` annotation. v1 mentions Rego files but does not
show the `# METADATA` block format. Gap 3's CI hook will fail
on missing annotations. Must show the exact format.

**F9 — Audit emission failure path.**
v1 does not specify what happens when `AuditLogger.write`
raises. Silent drop is a compliance violation. Must fail-closed:
re-raise as `AlertEmitFailed` with frozen reason.

### RECOMMENDATIONS (R)

**R1 — Wiring diagram.** ASCII flow: M7 → M3 Transaction →
CashTransaction → BsaAmlEngine → alerts → AuditEmitter → M10.
Gap 2 has this.

**R2 — Line budget breakdown.** v1 says "~1,100 lines" aggregate.
Break down per file + Rego.

**R3 — Phase 4 forward-compat.** v1 silent on Phase 4
`RedisWindowStore`. Ship a stub now so imports don't break when
the real backend lands.

**R4 — Thread safety.** `InMemoryWindowStore` will be called
from a request-scoped thread pool (M6 hits post-trade hook
concurrently). Needs a `threading.Lock()`.

**R5 — M2 `PolicyRule` Protocol compliance.**
v1 describes adapters but doesn't assert `isinstance(_,
PolicyRule)`. Needed so M2's engine can pick them up without
special-casing.

**R6 — Module boundary via AST.**
Gap 4 imports are more numerous than Gap 2. An AST scan is the
only reliable way to guarantee no new imports sneak in.

**R7 — Archetype gate via M5.**
v1 assumes caller wires `BsaAmlConfig`. Integration test
should build it via the M5 loader with a real tier4 (RIA)
EnterpriseConfig and verify disable path.

**R8 — SAR structuring 7-day boundary.**
v1 says "7 days" without specifying seconds/microseconds. Same
as F7 for CTR — the SAR window also needs a precise rule and
boundary test.

---

## SCORES (v1)

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 6.5   |
| Accuracy         | 20%    | 6.5   |
| Security         | 20%    | 5.5   |
| Testability      | 15%    | 6.0   |
| Design alignment | 10%    | 7.0   |
| Gaps             | 10%    | 5.0   |

Calculation:
- 25*6.5 + 20*6.5 + 20*5.5 + 15*6.0 + 10*7.0 + 10*5.0
- = 162.5 + 130 + 110 + 90 + 70 + 50 = 612.5
- / 100 = 6.125

**Weighted total: 6.13 / 10 — CONDITIONAL GO.**

All 9 blocking items + 8 recommendations must be addressed in
v2 before GO. Security score is especially low due to the
anti-tipping-off gap and float-threshold risk.

---

## VERDICT

**CONDITIONAL GO — 6.13 / 10.** Fix F1..F9 and R1..R8, then
re-review.
