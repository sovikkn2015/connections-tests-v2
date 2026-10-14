# Self-LLMJ Review v2 — remediation-trust-fixes.md

> Reviewer: 007-trust-agent (LLMJ mode, own-work review).
> Review type: spec-level, post-v1-fixups, pre-build.
> Spec under review: `.kiro/specs/remediation-trust-fixes.md` (updated).
> Prior review: `.kiro/specs/remediation-trust-fixes-REVIEW.md` (v1, 7.4/10 CONDITIONAL GO).

---

## Overall score: 8.3 / 10 — GO

Scored by the 6-dimension rubric (completeness 25%, accuracy 20%,
security 20%, testability 15%, design alignment 10%, gaps 10%).

| Dim | Weight | Score | Weighted |
|-----|--------|-------|----------|
| Completeness | 25% | 8.5 | 2.125 |
| Accuracy | 20% | 8.5 | 1.70 |
| Security | 20% | 8.5 | 1.70 |
| Testability | 15% | 8.5 | 1.275 |
| Design alignment | 10% | 8.0 | 0.80 |
| Gaps | 10% | 7.0 | 0.70 |
| **Weighted total** | | | **8.30** |

Clears the 8.0 GO bar.

---

## v1 action items — verified resolved

| # | Action | Status | Evidence |
|---|--------|--------|----------|
| 1 | §3.5 M3 cross-module authorization callout | ✅ Added | §3.5 explicitly references REMEDIATION-PLAN authorization + scopes the change to one field |
| 2 | §4.3.2 strict-mode mitigation patterns + field_validator escape hatch | ✅ Added | §4.3.2 now lists 3-step vendor-wire-format pattern + "never silently reintroduce strict=False" |
| 3 | M7-FIX `grepSearch` across `deploy/` + `config/` + `docs/` | ✅ Added | Task 6 under §5.4 now covers all those paths |
| 4 | §6.3.3 Operator migration note | ✅ Added | Explicit "before this fix / after this fix" contract + PEM-only story |
| 5 | ADR-01 + AuditEmitter comment about shim removal release | ✅ Added | AC M11.2 now names v0.6.0 as the shim removal target |
| 6 | Phase-1 scenarios MUST stay green callout | ✅ Added | §9.1 explicitly calls out `test_phase1_trust_layer.py` 7 scenarios |
| 7 | `backends_by_tier` public-API comment | ✅ Added | Docstring added in §2.3 design block |
| 8 | Canonical canary test | ✅ Added | `test_canonical_shape_preserves_trace_id_and_tenant_id` in §7.4 task 4 |
| 9 | Positive AidClaims tenant_id test | ✅ Added | Expanded §3.6 task 6 to include `test_aidclaims_roundtrip_preserves_tenant_id` |
| 10 | Rewrite Rule 33 as "see Rule 10" (preserve numbering) | ✅ Fixed | AC S.4 now rewrites Rule 33 as SUPERSEDED, not deleted |
| 11 | Existing `test_m8_m6_shape_match.py` tests stay as-is | ✅ Clarified | Task 5 under §5.4 now says "existing 6 tests stay as-is" |
| 12 | Verify `.env.example` for M8 has no stale `/gateway/call` comment | ✅ Added | Task 7 under §5.4 explicitly requires verification |

All 12 v1 must-dos addressed.

---

## Remaining residual risks (acknowledged, not blocking)

### R1. `test_values_cloud_global.py` file-naming inconsistency

v1 minor m-1 suggested renaming to `test_helm_values_cloud_global.py`
for consistency with module-scoped test names. The current name
`test_values_cloud_global.py` is clear enough — the file-naming
convention in the repo is not strictly module-scoped (e.g.,
`test_env_example_shipped.py`). Leaving as-is. Not a defect.

### R2. The M3 `AuditEntry` change is explicitly steering-authorized but still a cross-module write

§3.5 calls this out. The build phase will:
- Make the `tenant_id` addition in a single strReplace on `src/m3_schema_registry/types.py`.
- Not touch any other M3 types.
- Not add any new M3 imports anywhere.
- Let `AuditEntry.model_rebuild()` pick up the change (already called in `types.py`).

### R3. Commit-count is still a loose estimate

§10 says ~8 commits. If a single model-strict flip cascades into
test edits, we may end up with 10-12 commits. That is fine — the
spec caps at "one logical change per commit", not "exactly N commits."

### R4. The ADR is short by design

`docs/ADR/ADR-01-pydantic-strict.md` will be < 100 lines. A longer ADR
would add breadth but not depth. The format chosen is "ADR short form"
(context → decision → consequence → migration) which is idiomatic.

---

## Per-fix audit (post-v1 state)

### B11 — Helm duplicate global

- Requirements clear. 6 ACs.
- Test plan concrete: `yaml.safe_load` → assert single `global` + 8 sub-keys.
- Deploy gates explicitly required to stay green.
- No residual gap.

### B12 — M10 fail-closed

- Requirements clear. 8 ACs including the 4-way matrix.
- Env var defaults documented (false = secure default).
- `backends_by_tier` public method addition is the right abstraction
  to avoid private-attr reads in health probes.
- 8 new tests cover the 2x2 matrix + startup + helper.
- No residual gap.

### M3 — tenant_id

- Requirements clear. 8 ACs.
- §3.5 explicitly authorizes the cross-module M3 write via the
  REMEDIATION-PLAN language.
- 3 new tests + positive roundtrip case.
- Every call site enumerated; default convention (tenant_id = firm_id)
  is documented.
- No residual gap.

### M4 — strict=True

- Requirements clear. 6 ACs.
- Mitigation patterns concrete (field_validator mode="before" escape
  hatch, never silent strict=False).
- ADR-01 deliverable named.
- "Fix fixture, not model" policy explicit.
- No residual gap.

### M7 — /tools/call

- Requirements clear. 6 ACs.
- M6 double-registration design idiomatic (shared impl, `_finalize`
  wrapper for header).
- M8 client bugfix explicitly called out (path was misaligned with
  today's M6 surface).
- `grepSearch` scope widened to deploy + config + docs.
- No residual gap.

### M8 — M1 startup fail-closed

- Requirements clear. 7 ACs.
- §6.3.3 operator-migration note is explicit about the regression from
  silent-503 → hard-fail-startup — which is the CORRECT fail-closed
  direction per Rule 8.
- PEM-only with dated Vault-pull follow-up is honest.
- 4 new tests cover every env combination.
- No residual gap.

### M11 — canonical audit shape

- Requirements clear. 7 ACs.
- Shim window bounded (v0.6.0).
- M10 dispatch logic clear (canonical shape wins when both markers
  present).
- Canary test locks trace_id + tenant_id survival.
- No residual gap.

### STEERING

- 5 ACs. Rule 33 preserved as SUPERSEDED.
- Dated Phase-2 milestones (Q3/Q4 2026 for OPA; Q1/Q2 2027 for KMS).
- No residual gap.

---

## Build-readiness checklist

- [x] Every fix has numbered ACs.
- [x] Every fix has a concrete test plan.
- [x] Every fix names the files it touches.
- [x] Regression budget defined (≥ 2127 passed, 0 regressions).
- [x] Stability gate defined (10/10 stable runs).
- [x] Deploy gates named (helm_lint, helm_template_egress, dockerfile_security).
- [x] Steering carve-out is part of the spec, not a separate afterthought.
- [x] Rule-compliance matrix snapshots before / after.
- [x] Commit strategy with one logical change per commit.
- [x] ADR-01 location defined (`docs/ADR/ADR-01-pydantic-strict.md`).
- [x] COMPLETE marker criteria defined.

---

## Verdict

**GO. Build phase may commence.**

Re-scored 8.3 / 10 post-v1 fixups. All 12 v1 must-dos resolved. No
new blockers surfaced in v2. Residual risks (R1-R4) are acknowledged
as design choices, not defects.

Next step: execute the build per the §10 commit strategy.
