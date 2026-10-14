# Gap 3 — WSP-to-YAML Mapping — LLMJ Review v1

> Review of `.kiro/specs/gap3-wsp-to-yaml.md` (v1).
> Target: 7.5+/10 weighted for GO.

---

## FINDINGS

### BLOCKING (F)

**F1 (CRITICAL) — WSP_SECTION_RE decoupling risk.**
v1 R1.2 requires `WSP_SECTION_RE` to "equal" the M2 regex. But
`re.Pattern` objects are not `==` comparable by pattern string in
a way that survives module reloads. Make the coupling test
explicit: `_.pattern == m2_m4_policy_engine.WSP_SECTION_RE.pattern`.
Spec should state "pattern-string equality", not "regex equality".

**F2 — PII enforcement on `body` is too strict.**
v1 R5.1 rejects email-looking strings in `body`. A WSP procedure
body commonly says: "Escalate to cco@firm.com". Current rule
makes the spec unusable. Need either (a) an allow-list for role
mailbox addresses, or (b) a note that the WSP author must use
role names, not email. Spec currently has no note.

**F3 — `schema_version` enforcement mechanism unspecified.**
v1 says `schema_version: Literal["1.0.0"]` but does not describe
test coverage for version mismatch. Add an explicit "version
mutation" task.

**F4 — Missing golden-manifest digest.**
v1 R3.4 describes `sha256_digest` but no golden-value test. Gap 2
has `GOLDEN_HEX_DIGEST`; Gap 3 should match that rigor.

**F5 — Empty-registry semantics unspecified for coverage.**
What exit code for `CoverageReport` when registry has 0 sections?
v1 is silent. Must specify: 0 sections is a CI-blocking misconfig
(exit 2), not a happy path.

**F6 — CLI exit code vocabulary not frozen.**
v1 R6.2 mixes exit codes with free-form error reasons. Need a
frozen vocabulary (like Gap 6 ScanDecision), enumerated in the
spec so tests can assert on it without drift.

**F7 — Filesystem access has no isolation seam.**
v1 has `ingest_wsp_yaml(path)` reading the filesystem directly.
No Protocol-based reader means tests must use `tmp_path`, which
is slow and couples tests to filesystem layout. Add `FileReader`
Protocol.

**F8 — Determinism contract missing.**
v1 does not require byte-identical output across runs. Without
that, CI diff-checks become flaky. Lock determinism via sorted
sections, sorted rules, and the golden digest test.

### RECOMMENDATIONS (R)

**R1 — Wiring diagram.** Add ASCII diagram showing data flow:
WSP author → wsp.yaml → ingest → registry → manifest YAML +
coverage report. Gap 2 has this; Gap 3 should too.

**R2 — Line budget breakdown.** v1 says "~1,000 lines" aggregate.
Break down per file so the implementer has a target.

**R3 — Module boundary via AST.** v1 says "imports only M2";
tests should assert this via `ast` module scanning. Gap 2 does
this in T2.25.

**R4 — Phase 4 forward-compat.** v1 is silent on Phase 4
migration. Gap 2 has a `§0.1 forward-compat` section; Gap 3
should match.

**R5 — Coverage percentage rounding.**
`coverage_pct` as `float` → floating-point drift. Either round to
3 dp via `round(x, 3)` (banker's) or use `Decimal`. Spec should
pick one.

**R6 — Rego scanner precision.**
v1 R2's `scan_rego_file` regex is not defined. Define it in §2.4
with actual pattern. Needed so implementer doesn't guess.

**R7 — Many-to-many mapping.**
v1 does not state whether a single Rego rule can anchor multiple
WSP sections. Need explicit "many-to-many" semantics so the
reverse-index type is `tuple[str, ...]` not `str`.

---

## SCORES (v1)

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 6.5   |
| Accuracy         | 20%    | 7.0   |
| Security         | 20%    | 6.0   |
| Testability      | 15%    | 6.5   |
| Design alignment | 10%    | 7.0   |
| Gaps             | 10%    | 5.5   |

Calculation:
- 25*6.5 + 20*7.0 + 20*6.0 + 15*6.5 + 10*7.0 + 10*5.5
- = 162.5 + 140 + 120 + 97.5 + 70 + 55 = 645
- / 100 = 6.45

**Weighted total: 6.45 / 10 — CONDITIONAL GO.**

All 8 blocking items + 7 recommendations must be addressed in v2
before GO.

---

## VERDICT

**CONDITIONAL GO — 6.45 / 10.** Fix F1..F8 and R1..R7, then
re-review.
