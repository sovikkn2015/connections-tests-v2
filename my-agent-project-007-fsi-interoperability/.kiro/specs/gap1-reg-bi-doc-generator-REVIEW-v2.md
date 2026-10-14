# Gap 1 — Reg BI Doc Generator — LLMJ Review v2

> Reviewer: LLMJ
> Target: `.kiro/specs/gap1-reg-bi-doc-generator.md` (v2)
> Rubric: see v1 review. GO threshold: 8.0.

---

## Summary scores

| Dimension                         | v1  | v2  |
|-----------------------------------|-----|-----|
| Requirements clarity              | 7.6 | 8.6 |
| Determinism / no-LLM contract     | 8.2 | 8.8 |
| Fail-closed semantics             | 6.8 | 8.4 |
| Module boundary enforcement       | 8.8 | 9.0 |
| PII / security                    | 7.8 | 8.6 |
| Test traceability                 | 7.9 | 8.8 |
| Canonical JSON / hash contract    | 8.4 | 8.8 |
| Applicability gate precedence     | 8.0 | 9.0 |
| Overall                           | 7.7 | **8.7** |

---

## Verification of v1 findings

- **F1 (min-bullet enforcement)** — FIXED. R3.7 adds
  `InsufficientBulletsError`; T1.30b locks it. R9 exports. ✓
- **F2 (trust client_type)** — FIXED. R2.3 step 3 covers both entity
  and trust; T1.6 parametrizes all three. ✓
- **F3 (no display_name in bullets)** — FIXED. R3.8 + T1.18b. ✓
- **F4 (independent populator versioning)** — FIXED. R3.5 clarifies
  per-obligation `vN`. ✓
- **F5 (audit client dedupe)** — FIXED. R8.1 explicit. ✓
- **F6 (UTC normalize)** — FIXED. R1.2 `.astimezone(timezone.utc)`. ✓
- **F7 (cap POST-scrub)** — FIXED. R1.2 + R5.2. ✓
- **F8 (positive schema-version)** — FIXED. T1.30 parametrized. ✓
- **R1..R8 recommendations** — all traced in §5. ✓

---

## Residual findings (minor)

### r1 — `dataclasses` is imported but no dataclasses used

**Severity: trivial.** `0.6` lists `dataclasses` in allowed imports,
but the v2 design uses Pydantic models exclusively. Drop from the
allow-list to tighten the boundary; OR keep if the generator class is
in fact a `@dataclass`. Low-impact; builder agent can decide.

### r2 — `InsufficientBulletsError` not tested for all 4 obligations

**Severity: low.** T1.30b covers CARE. Consider parametrizing across
all 4 obligations so a future regression in DISCLOSURE/COI/COMPLIANCE
min-bullet logic is caught.

**Recommendation:** OK as-is; T1.11/T1.12/T1.13/T1.14 adequately
cover happy paths. T1.30b's CARE failure case is the only practical
min-breach since COMPLIANCE has 2 always-on bullets and COI has a
fallback. DISCLOSURE bulletpath always hits 3. No change needed.

### r3 — AST-scan test also needs to check narrative.py + audit_client.py

**Severity: low.** T1.22 says "Gap 1 source" generically. State
explicitly that the scan iterates every `.py` under
`src/compliance/gap1_reg_bi_doc_generator/`.

**Recommendation:** Note as build-agent TODO; spec is clear enough.

### r4 — `research_brief_ref` derivation is implicit

**Severity: low.** R6.1 says `research_brief_ref: UUID | None`. Spec
does not state how it's populated — presumably `inp.research_brief.brief_id`
when present. Make explicit.

**Recommendation:** Build-agent can derive; no spec change needed.

### r5 — `advisor_review_required` gate ordering — clarity

**Severity: low.** R7.5 uses "if True: force True; else: signal
escalation". The semantic is "require_advisor_review is a FLOOR:
True always wins; False lets signals elevate". That's fine, but the
prose could be clearer.

**Recommendation:** Documented in the sketch; buildable. Non-blocking.

---

## Decision

**SCORE: 8.7 — GO.**

All F-findings fixed. Remaining residuals are stylistic / buildable.
Spec is ready for implementation. Proceed to Step 5 (build).
