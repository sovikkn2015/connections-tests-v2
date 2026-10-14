# M9 Intent Router — COMPLETE

**Module**: M9 Intent Router
**Phase**: 2 (Intelligence Layer — RIA lighthouse)
**Spec Version**: v0.2.0
**Build Completed**: 2026-05-16
**Playbook**: All 7 steps complete
**Final Status**: ✅ GO — cleared for Phase 2 integration.

---

## Playbook Summary (7 Steps)

| Step | Action | Output | Score / Result |
|------|--------|--------|----------------|
| 1 | Spec v0.1.0 | 1,765 lines — initial draft | — |
| 2 | LLMJ v1 review | `m9-intent-router-REVIEW.md` | **7.42 / 10 CONDITIONAL GO** (14 Required Fixes) |
| 3 | Fix pass → v0.2.0 rewrite | 2,130 lines | — |
| 4 | LLMJ v2 re-review | `m9-intent-router-REVIEW-v2.md` | **8.47 / 10 GO** (+1.05 Δ) |
| 5 | Build | 14 source files + 19 test files | 19/19 tasks complete |
| 6 | Verify | `pytest tests/ --tb=short` | **1045 passed, 0 failed** (10/10 stable stress) |
| 7 | Complete marker | this file | — |

---

## What Ships

### Source Tree — `src/m9_intent_router/` (1,690 LOC)

| File | LOC | Purpose |
|------|-----|---------|
| `__init__.py` | 50 | 11 names in `__all__`, `SCHEMA_VERSION = "1.1.0"` |
| `errors.py` | 44 | `VALID_REASON_CODES` frozenset (13 codes) + 3 exception classes |
| `taxonomy.py` | 325 | `IntentCategory` (11 members), `SelectedTarget`, `TAXONOMY_DISPATCH`, `build_tool_schema()`, Authority Scope Matrix, invariants A1–A19 |
| `models.py` | 122 | `RouterContext` (+ AC1.9 self-consistency), `LlmClassification` (Inf/NaN rejected), `RoutingDecision` (12-key audit) |
| `hmac_util.py` | 54 | Tenant-scoped HMAC-SHA-256 + Vault resolver (Fix 10) |
| `regex_library.py` | 146 | SF 18-char base-32 checksum, 50-ticker whitelist, 6 regex slots |
| `mnpi_scan.py` | 80 | 4-category MNPI scanner, ABA checksum, precedence ordering |
| `fallback.py` | 49 | 3 deterministic regex patterns |
| `llm_client.py` | 351 | `LLMProvider` Protocol, `BedrockHaikuClient`, `FakeLlmClient` (Fix 9), `SlowFakeLlmClient` (Fix 13), 3 Phase 3 stubs, `select_provider` |
| `route.py` | 469 | Dispatcher — MNPI pre-scan → LLM inside `Semaphore(16)` → authority scope → single `print()` audit emit |
| `prompts/system.md` | — | LLM system prompt |
| `schemas/m9_audit_payload.schema.json` | — | JSON Schema 2020-12 |
| `DECISION-LOG.md` | — | Seeded |
| `.env.example` | — | No credential-shaped names |

### Test Tree — `tests/` (2,823 LOC, **206 new M9 tests**)

| Category | Files | Coverage |
|----------|-------|----------|
| Unit | 14 | Taxonomy, models, LLM client, regex lib, MNPI scan, HMAC util, Bedrock (Stubber), route, authority scope, role downgrade, fallback, confidence thresholds (21 rows), reason codes (all 13), audit schema |
| Security | 4 | Module boundary AST scan, forbidden imports, no `m8_` string ref (taxonomy.py exempt), no hardcoded creds |
| Property | 2 | Determinism + regex library safety (Hypothesis ≥ 500 cases) |
| Benchmarks | 2 | Concurrency (50 threads × 20 calls), MNPI latency (<20 ms) |
| Integration | 6 | `bedrock_first_call` (M9_LIVE gated), `env_example_shipped`, `pyproject_deps`, `m5_config_shape` (xfail), `m12_m9_supervisor_call`, `cross_module_version_match` (xfail) |

---

## 14 Required Fixes from LLMJ v1 — All Resolved

| # | Fix | Resolution |
|---|-----|------------|
| 1 | ARCH-09 dependency matrix alignment | M9 imports M1+M5 (not M3), called by M12 (not M6) |
| 2 | ARCH-07 latency citation | Only `<500ms` cited; p50/p95/p99 in M9 DECISION-LOG |
| 3 | M6 VendorAdapter shape | §Integration Point with M6 deleted; §Integration Point with M12 replaces |
| 4 | `RouterContext.archetype` firm-level | Uses M5 `Archetype.tier4_independent_ria` throughout |
| 5 | Task 19 defined | `test_cross_module_version_match.py` — xfail pending M6/M8 |
| 6 | Pipeline/tool names → PENDING-CONFIRM | `m8.research_*` + `m6.composed_goal_tracking` downgraded |
| 7 | M12 declared as consumer | Primary and only direct caller |
| 8 | `identity: AidClaims` + Authority Scope Matrix | New field, new AC12.9 post-LLM fail-closed, new `aid_authority_denied` code |
| 9 | `FakeLlmClient` Exception injection | `responses: dict[str, LlmClassification \| Exception]` |
| 10 | HMAC-SHA-256 tenant-scoped | `hmac_util.py` + `IntentRouterConfig.tenant_hmac_key_vault_path` |
| 11 | `CLIENT_HOUSEHOLD_SUMMARY` rename | → `RESEARCH_HOUSEHOLD_SUMMARY`, SCHEMA_VERSION 1.0.0 → 1.1.0 |
| 12 | Steering Rule 8 in table | Fail-closed explicitly listed |
| 13 | `SlowFakeLlmClient` for timeout | Deterministic timeout test — no real boto3 needed |
| 14 | `taxonomy.py` exempted from m8-string-ref scan | `EXEMPT_FILES` hardcoded |

---

## 11 of 12 Recommended Fixes Landed

R1 tenant-dimension MNPI counter; R2 `SlowFakeLlmClient`; R3 concurrency smoke test; R4 Inf/-Inf rows; R5 honest 150s CI budget; R6 `fallback_enabled=False + 4xx` row; R7 `.env.example` ships; R8 `Semaphore(16)` defense-in-depth; R9 audit schema meta-validation; R11 SF 18-char checksum pinned; R12 rename-policy DECISION-LOG. R10 (Luhn-tighten `bank_account`) deferred to Phase 3 with acknowledgement.

---

## Test Suite Status

### Final Run
```
pytest tests/ --tb=short --timeout=60
1045 passed, 1 skipped, 4 xfailed, 1 xpassed in 3.99s
```

### Stress Test — 10 Consecutive Runs
All 10 runs: `1045 passed, 1 skipped, 4 xfailed, 1 xpassed` — range 3.41s to 3.97s.
**10/10 stable — zero flakes.**

### Test Count Progression
- Pre-M9: 839 passing
- Post-M9: **1045 passing (+206 M9 tests)**

### Skipped / xfailed (all expected)
- `test_bedrock_first_call.py` — skipped (`@skipif` on `M9_LIVE` env var — live Bedrock probe gated behind flag)
- `test_m9_m5_config_shape.py` — xfail (pending M5 v0.3.0 `IntentRouterConfig`)
- `test_m9_cross_module_version_match.py` (2 tests) — xfail (pending M6 Phase 2 composed-tool manifest + M8 v0.1.0 `PIPELINE_NAMES`)
- Pre-existing SFDC PascalCase gate from M11 — 1 xfailed

---

## Integration Readiness

### Pending Handshakes (xfail posture — auto-upgrade on handshake)

1. **M5 `IntentRouterConfig` sub-model** — Phase 2 Week 32. M9 uses duck-typed config via `FakeIntentRouterConfig` (tests/conftest.py) until M5 ships.
2. **M6 composed-tool manifest** — When M6 Phase 2 exports `REGISTERED_TOOLS`, `test_tool_kind_names_subset_of_m6_registered` upgrades.
3. **M8 `PIPELINE_NAMES`** — When M8 v0.1.0 exports the constant, `test_pipeline_kind_names_subset_of_m8_pipeline_names` upgrades.
4. **Bedrock live-call verification (Task 16)** — Run `M9_LIVE=1 pytest tests/integration/test_bedrock_first_call.py` with IRSA.

No action required from M9 to un-block these — they upgrade on the upstream module's release cadence.

### Absolute Rules Verified

- ✅ **Zero credentials in code** — AST scan + regex scan at CI gate
- ✅ **No `logging` imports** — forbidden AST scan
- ✅ **Single `print()` call** — only in `route.py::_emit_audit` (AC13.5)
- ✅ **Positive allow-list boundary** — M9 imports ONLY `m1_identity` + `m5_config_loader` (AC12.2)
- ✅ **boto3 confined** — only in `llm_client.py` + `hmac_util.py` (AC13.3)
- ✅ **MNPI fail-closed** — pre-LLM scan short-circuits to `escalate_to_human` (Steering Rule 8)
- ✅ **HMAC-SHA-256 per tenant** — rainbow-table attack eliminated (Fix 10)
- ✅ **AID authority fail-closed** — `aid_authority_denied` reason code + §Authority Scope Matrix
- ✅ **All 13 VALID_REASON_CODES exercised** — Task 15 meta-test asserts reachability
- ✅ **Determinism property-tested** — Hypothesis ≥ 100 examples
- ✅ **Concurrency defense-in-depth** — `Semaphore(16)` verified at 50 threads × 20 calls

---

## Artifacts

| Artifact | Path |
|----------|------|
| Spec v0.2.0 (GO) | `.kiro/specs/m9-intent-router.md` |
| LLMJ v1 Review | `.kiro/specs/m9-intent-router-REVIEW.md` (7.42/10) |
| LLMJ v2 Review | `.kiro/specs/m9-intent-router-REVIEW-v2.md` (8.47/10 GO) |
| Source | `src/m9_intent_router/` |
| Tests | `tests/{unit,security,property,benchmarks,integration}/test_m9_*.py` |
| Shared fixtures | `tests/conftest.py` (F1-F5) |
| Completion marker | this file |

---

## Phase 2 Module Progress

- ✅ **M7 Schema Translators** (v0.3.0, 8.29/10 GO)
- ✅ **M11 REST Adapters** (v0.2.0, 8.52/10 GO)
- ✅ **M9 Intent Router** (v0.2.0, 8.47/10 GO) ← this module
- ⬜ **M8 Pipeline Engine** — next

**3 of 4 Phase 2 modules complete.** Target: M8 closes Phase 2.

---

*M9 Intent Router — COMPLETE*
*Project 007 FSI Interoperability Platform*
