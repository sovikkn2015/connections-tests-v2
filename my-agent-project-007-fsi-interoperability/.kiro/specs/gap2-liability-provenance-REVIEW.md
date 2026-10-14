# Gap 2 — Liability Provenance — LLMJ Review v1 (HARSH)

> Reviewer role: skeptical compliance-specialist LLMJ, tuned hostile.
> Scoring: 6 dimensions, must hit 7.5+/10 weighted for GO.
> Spec reviewed: `.kiro/specs/gap2-liability-provenance.md`

---

## SCORES

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 6.5   |
| Accuracy         | 20%    | 7.5   |
| Security         | 20%    | 6.0   |
| Testability      | 15%    | 7.5   |
| Design alignment | 10%    | 7.5   |
| Gaps             | 10%    | 5.5   |

**Weighted total: 6.775 / 10 — CONDITIONAL GO — REVISE.**

---

## REQUIRED FIXES (blocking)

### F1. R3.7 overall_warranty rule is logically ambiguous.

R3.7 says "if `chain_verified == False` — `unknown`" AND "if
`error_attribution is not None` — `max(max(rank), best_effort)`". What
if BOTH? What if a stage is already `unknown`? Rewrite as explicit
precedence ladder:

1. If `chain_verified == False` — `unknown` (wins).
2. Else if any stage classified `unknown` — `unknown`.
3. Else if `error_attribution is not None` — `max(max(stage rank),
   best_effort)`.
4. Else — `max(stage rank)`.

Document the precedence explicitly so future edits can't subtly break
fail-closed semantics.

### F2. R3.8 PII enforcement is aspirational, not mechanical.

Spec says reports MUST NOT contain PII but only relies on Pydantic
length caps. A 500-char `reason` can easily hold a name + account + SSN.
Pick one of:

(a) Validate `reason` against Gap 6 Layer A regex set (SSN, email,
    account, IBAN) and reject at construction time.
(b) Explicitly delegate sanitization to the caller (M6) and add a
    unit test that proves the model itself will surface values
    containing SSN/email patterns unchanged (documenting the contract).

Pick (a) or (b). "Aspirational" is not acceptable in a compliance spec.

### F3. No schema version on LiabilityReport.

Regulators will demand schema versioning on a 6-year WORM artifact. Add
`report_schema_version: str` with a class-level constant default
`"1.0.0"` (immutable via `field_validator` rejecting caller overrides).
Include it in `to_canonical_json()` and golden hex.

### F4. No concrete golden hex published.

R3.5 claims deterministic SHA-256. Tests should pin a SPECIFIC hex on a
SPECIFIC fixture. Publish it in-spec so reviewers can recompute
independently:

- `trace_id = "trace-fixed-001"`
- `generated_at = 2026-04-14T12:00:00+00:00`
- 2-stage chain: `(m1.verify, m1, <fixed-hash-1>)`,
  `(m6.dispatch, m6, <fixed-hash-2>)` with timestamps also fixed.
- `chain_verified = True`, `error = None`.
- Published SHA-256 hex of `to_canonical_json()`.

Without this, determinism is a claim, not a test.

### F5. Precedence when `chain_verified=False` + error is None.

Clarify: `is_clean()` is False, and `overall_warranty == unknown`
(R3.7 ladder rule 1). State explicitly so future simplification can't
break it. Add test T2.15b.

### F6. `WarrantyBoundary.TABLE` is coupled to M10's module regex.

M10's `_MODULE_PATTERN` accepts m1..m13 only. If M10 expands the
namespace (say m14, m15) but Gap 2's table doesn't, every stage for the
new module classifies `unknown` — a silent fail-closed, which is
*correct* but leaves regulators wondering why. Add a CI test:

```
assert set(WarrantyBoundary.TABLE.keys()) == {"m1","m2",...,"m13"}
```

And a comment in `warranty.py` that links to M10's `_MODULE_PATTERN`.
Explicit coupling is acceptable; silent drift is not.

### F7. `ErrorAttribution.reason` structural upgrade path.

Phase 1 `reason: str` is fine, but insurance underwriters want
structured codes. Document the Phase 2 extension in §0.1 (non-goals):
Phase 2 will add `reason_codes: tuple[str, ...]` forward-compatibly.
Also add `model_config = ConfigDict(frozen=True, extra="forbid")` so
unknown fields during Phase 2 transition fail loudly, not silently.

### F8. `to_canonical_json` serialization contract is underspecified.

R3.4 says "key-sorted, compact JSON". But what about tuples? Nested
Pydantic? Enums? Datetimes? Specify explicitly to prevent drift from
M10's `_canonical_json`:

- `datetime` → UTC ISO 8601 with `Z` suffix (not `+00:00`).
- `Enum` → `.value`.
- `UUID` → `str(uuid)`.
- `tuple` → JSON array (list).
- `sort_keys=True`, `separators=(",", ":")`.
- Pydantic models → `model_dump(mode="json")` then re-serialized with
  `sort_keys=True` to guarantee ordering (Pydantic v2 preserves
  declaration order by default; `sort_keys=True` canonicalizes).

---

## RECOMMENDED FIXES (non-blocking)

### R1. §2.5 wiring is words-only.

Add an ASCII handoff diagram: `builder.verify()` →
`LiabilityReport.build(...)` → `M10.write(entry_with_report_json)`.

### R2. `StageClassification.is_failing` semantics.

Add to R3.1: "exactly one `stage_classifications` entry has
`is_failing=True` iff `error_attribution is not None`, and that entry's
`stage.stage == error_attribution.stage`. All other entries have
`is_failing=False`."

### R3. Gap 1 integration mention.

One-line note in §0.1: "Phase 2 Gap 1 (Reg BI Doc Generator) consumes
this report via `to_canonical_json()` to attach provenance to Reg BI
documents."

### R4. Line budget math.

Spec target ~700 total. Spec says Gap 2 ≈ 560 lines. Tests ≈ 350. With
shared `src/compliance/__init__.py` (~20) and Gap 6 (~520) the combined
compliance module is ~1,400 lines. Reconcile: ARCH-06 target is ~700
for Gap 2 alone or combined? State explicitly that Gap 2 ≈ 560-600
lines Python + 350 test lines.

### R5. `model_dump()` vs JSON determinism.

T2.3 uses `to_dict()` — make sure it calls `model_dump(mode="json",
exclude_none=False)` explicitly. Pydantic v2 defaults are fine but
document them.

### R6. Missing negative: `attribute_from_chain(chain=[])` — ValueError.

Distinct from T2.13 (build() rejects empty chain). Add explicit test
for the helper itself.

### R7. Missing positive: all-best_effort chain, no error —
`overall_warranty == best_effort`, `is_clean() == False`
(best_effort is not "clean" by R3.6 — but wait, R3.6 says `is_clean()`
= `chain_verified and no_error and overall_warranty != unknown`.
Best_effort passes that! So is_clean() == True.).

This exposes an ambiguity: is best_effort "clean" enough to deliver?
For a research brief (M8, Sonnet), we know the output is best_effort;
that doesn't make it dirty. is_clean() semantics should be "trustworthy
provenance" not "fully warranted". Document this in R3.6:

"is_clean() returns True when provenance is intact and no error is
attributed. A best_effort overall_warranty is still 'clean' — the
output is deliverable, but callers SHOULD surface the warranty level
to end users."

Fix the wording explicitly.

---

## SUMMARY

- 8 blocking fixes (F1-F8).
- 7 recommended fixes (R1-R7).
- Rewrite R3.7 as precedence ladder.
- Add `report_schema_version` field.
- Publish concrete golden hex digest.
- Decide PII enforcement on `reason` (not aspirational).
- Clarify is_clean() semantics for best_effort.

The core architecture is sound — warranty table, 6-category taxonomy,
chain delegation to M10. But the spec needs tightening on determinism
contracts, schema versioning, and PII enforcement before build.

Re-review required after fixes. Target 7.5+/10.
