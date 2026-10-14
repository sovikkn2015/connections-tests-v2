# Remediation Trust-Fixes — Progress Report (NOT COMPLETE)

> Owner: 007-trust-agent
> Status: **PARTIAL** — B11 + B12 landed as git commits on `feat/007-phase4-m11-wave4`.
> M3 / M4 / M7 / M8 / M11 / steering-update NOT committed due to environment instability.
> Date: this session

---

## What landed (committed)

| Fix | Commit | Status |
|-----|--------|--------|
| B11 -- Helm `values-cloud.yaml` duplicate `global:` merge | `9e5e235a` | ✅ COMMITTED |
| B12 -- M10 fail-closed on all-InMemory backends | `a621c41b` | ✅ COMMITTED |

Both commits on `feat/007-phase4-m11-wave4`. 12 new tests for B11
(`tests/unit/test_values_cloud_global.py`) + 16 new tests for B12
(`tests/unit/test_m10_app_failclosed.py`). Deploy gates green:
`test_helm_lint.sh` PASS, `test_helm_template_egress.sh` PASS,
`test_dockerfile_security.sh` PASS.

## What did NOT land

| Fix | Work state | Blocker |
|-----|-----------|---------|
| M3 -- `tenant_id` on AidClaims + AuditEntry | Applied TWICE; reverted each time | Workspace branch kept switching between `feat/007-phase4-m11-wave4` and `feat/006-v3-live-demo` between tool calls; uncommitted edits were silently lost |
| M4 -- `strict=True` on 26 Pydantic models + ADR-01 | Spec written; no code committed | Same env issue; blocked on M3 landing |
| M7 -- rename `/gateway/call` -> `/tools/call` | Spec written; no code committed | Same env issue |
| M8 -- M1 startup hook fail-closed (`create_app_from_env`) | Spec written; no code committed | Same env issue |
| M11 -- audit shape alignment `{module, kind, ts}` | Spec written; no code committed | Same env issue |
| Steering carve-out (Rules 5/10/23/33 + dated Phase-2 plan) | Spec written; steering file not edited | Same env issue |

## What IS saved on disk (spec artefacts)

| Artefact | Purpose |
|----------|---------|
| `.kiro/specs/remediation-trust-fixes.md` | Combined spec for all 7 fixes (~900 lines) |
| `.kiro/specs/remediation-trust-fixes-REVIEW.md` | Self-LLMJ v1 (7.4/10 CONDITIONAL GO) |
| `.kiro/specs/remediation-trust-fixes-REVIEW-v2.md` | Self-LLMJ v2 (8.3/10 GO) |
| `.kiro/specs/remediation-trust-fixes-PROGRESS.md` | This file |

## Regression gate state (last stable snapshot)

- `pytest tests/ -q --timeout=60` (excluding WIP from concurrent agents):
  **1995 passed, 0 failed, 0 regressions from my changes**.
- Phase-1 trust-layer integration (`test_phase1_trust_layer.py` 7 scenarios):
  all PASSING.
- Deploy gates: all PASS.

Known pre-existing test failures (from OTHER concurrent sub-agent work,
NOT my regressions):

- `test_source_system_21_values` — adapter-agent added 2 vendor slugs, test hardcoded 21.
- `test_m8_stages_3_6_data_gathering.py` — pipeline-agent tests ahead of stage impl.
- `test_m8_hitl_interrupt.py` — pipeline-agent WIP import error.
- `test_m6_m7_canonicalize.py` — adapter-agent M7 wiring hits MNPI edge case.
- `schema-reconciliation/test_m7_roundtrip_*` — adapter-agent WIP.

## Environment instability observed

Two distinct silent-revert incidents, both confirmed via `readFile` +
`grepSearch` + `git status`:

1. After committing B11, attempts to modify
   `src/m10_audit_logger/app.py` and `src/m10_audit_logger/logger.py`
   for B12 were silently reverted. Reapplied via `strReplace` and
   committed successfully.

2. After committing B12, all M3-FIX edits were silently reverted.
   Root cause: the workspace was checked out to a different git
   branch (`feat/006-v3-live-demo`) between my tool calls. Recovered
   once by `git stash --include-untracked` + `git checkout
   feat/007-phase4-m11-wave4`. Second revert happened the same way
   after reapplying — the branch switched back again after my next
   set of edits.

This is the "silent-revert defensive posture" the task reminder warned
about, realised in practice. The defensive `readFile` / `grepSearch`
checks worked (they detected the reverts), but re-applying edits in
this environment became unstable enough that finishing M3 -- M11 in
this session was not feasible.

## Spec acceptance (for M3 through M11 + steering)

Self-LLMJ v2 score: **8.3 / 10 -- GO**. All 12 v1 must-dos addressed:

1. ✅ §3.5 M3 cross-module authorization callout
2. ✅ §4.3.2 strict-mode mitigation patterns
3. ✅ M7-FIX grep-expanded across deploy + config + docs
4. ✅ §6.3.3 Operator migration note for M8-FIX
5. ✅ ADR-01 named + M11 shim removal release (v0.6.0)
6. ✅ Phase-1 scenarios must stay green (explicit)
7. ✅ `backends_by_tier` public-API comment
8. ✅ Canonical canary test for audit shape
9. ✅ Positive AidClaims tenant_id test
10. ✅ Rule 33 rewritten as SUPERSEDED (preserving numbering)
11. ✅ Existing `test_m8_m6_shape_match.py` tests stay as-is
12. ✅ `.env.example` M8 verification task

## Recommended continuation

Execute the spec in a fresh stable session pinned to
`feat/007-phase4-m11-wave4`. Between every tool call run
`git rev-parse --abbrev-ref HEAD` to confirm the branch has not switched.
Commit order per §10 of the spec.

## Rule-compliance matrix (current state)

| Rule | Before | After my session | Target post-full-remediation |
|------|--------|------------------|------------------------------|
| 5 (OPA only) | VIOLATED | VIOLATED (steering update pending) | DOCUMENTED carve-out + dated Phase-2 |
| 10 (no cross-module imports) | VIOLATED | VIOLATED | DOCUMENTED carve-out |
| 23 (per-tenant KMS) | MISSING tenant_id | MISSING tenant_id (M3-FIX reverted) | tenant_id on AidClaims + AuditEntry |
| 32 (Pydantic strict) | partial (1/26) | partial (1/26) | FULL 26/26 |
| 33 (no cross-module imports) | VIOLATED | VIOLATED | SUPERSEDED by Rule 10 |
| B11 (Helm global) | VIOLATED | **FIXED** | FIXED |
| B12 (M10 fail-closed) | VIOLATED | **FIXED** | FIXED |

## Honest verdict

B11 + B12 are done -- the two production footguns are eliminated, tested,
and deploy-gate-green. The remaining 5 MAJORS have a complete, self-reviewed
GO spec ready for a fresh session to execute.

COMPLETE marker cannot be emitted. This PROGRESS marker stands in its
place.
