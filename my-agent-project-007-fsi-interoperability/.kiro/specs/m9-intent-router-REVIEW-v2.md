# M9 Intent Router — LLMJ Review v2 (Re-Review)

**Spec Version:** 0.2.0 (2,130 lines)
**Reviewer:** pipeline-and-intent-agent acting as independent LLMJ
**Date:** 2026-05-16
**Playbook Step:** 4 of 7
**Prior Score:** 7.42/10 CONDITIONAL GO (v0.1.0, 2026-05-15)

---

## Weighted Score: 8.47 / 10 — **GO**

| # | Dimension | Weight | v1 Score | v2 Score | Weighted | Δ |
|---|-----------|--------|----------|----------|----------|---|
| 1 | Completeness | 25% | 8.4 | 9.1 | 2.28 | +0.7 |
| 2 | Accuracy | 20% | 5.5 | 8.6 | 1.72 | +3.1 |
| 3 | Security | 20% | 8.6 | 9.1 | 1.82 | +0.5 |
| 4 | Testability | 15% | 8.0 | 8.7 | 1.31 | +0.7 |
| 5 | Design Alignment | 10% | 6.5 | 9.0 | 0.90 | +2.5 |
| 6 | Gaps | 10% | 6.5 | 8.4 | 0.84 | +1.9 |
| — | **TOTAL** | **100%** | 7.42 | — | **8.47** | **+1.05** |

Scoring bands: 8.0+ = GO, 7.5–7.9 = MARGINAL GO, 6.5–7.4 = CONDITIONAL GO, <6.5 = NO GO.

The spec clears the 8.0 GO threshold with meaningful headroom. The v0.2.0 rewrite is a surgical, honest fix pass in the mold of M7 v0.3.0 and M11 v0.2.0. All 14 Required Fixes are RESOLVED with verifiable spec-inspection evidence. 11 of 12 Recommended Fixes landed (R10 Luhn-tighten deferred to Phase 3 with explicit acknowledgement). Accuracy jumps +3.1 points because all four severe v1 accuracy defects are now resolved against source-of-truth files. Design Alignment jumps +2.5 because the dependency graph now matches ARCH-09 matrix row M9 + column 9 exactly.

Two minor cosmetic issues in Appendix B skeletons (`_fixture_key` and `_empty_tenant_key` called but not defined) and one duplication (Steering Rule 8 traceability doubled) are non-blocking polish items. None delay build.

---

## Fix Verification Table

One row per v1 Required Fix. Evidence cited from direct v0.2.0 spec inspection.

| # | v1 Required Fix | v0.2.0 Evidence | Status |
|---|-----------------|-----------------|--------|
| 1 | ARCH-09 matrix alignment (M9 ↔ M1+M5, called by M12) | Banner lines 7-8 rewritten (Deps M1+M5, Consumers M12-only); §Architecture Clarification quotes matrix row M9 = `* . . . * . . . . . . . .` char-for-char (verified against ARCH-09 line 312); §Known Blockers row 1 RESOLVED; R12 AC12.2 allow-list now `m1_identity` + `m5_config_loader`; AC12.7 removes `m3-schema-registry` from pyproject; AC12.8 negative test for `m3_schema_registry` imports; §Integration Point with M6 DELETED; §Integration Point with M12 ADDED | **RESOLVED** |
| 2 | ARCH-07 only for `<500ms`; percentiles M9-DECISION-LOG-owned | Banner line 12 (Design Sources) explicit: "ARCH-07 §Model Selection Table (Supervisor = Haiku, `<500ms` — this is the ONLY cited latency number"); R16 AC16.4 splits ARCH-07 SOURCED (`p_max<500ms`) vs M9 DECISION-LOG INTERNAL SLO (p50/p95/p99); Appendix C DECISION-LOG 2026-05-16 entry records rationale. Verified against ARCH-07 line 57: `\| Supervisor \| Haiku \| Fast routing, less than 500ms \|` — no percentile breakdown anywhere | **RESOLVED** |
| 3 | M6 VendorAdapter shape corrected / §Integration Point with M6 deleted | §Integration Point with M6 DELETED (grep confirms no header); §Integration Point with M12 replaces with direct-call pattern; R17 AC17.1 explicit: "The `VendorAdapter` Protocol in `m6_mcp_gateway/adapters.py` (real shape: `name: str` + `call(*, tool_name, payload)`) is NOT implemented by M9"; §Why NOT a VendorAdapter subsection (line ~1755) shows real Protocol shape and acknowledges v0.1.0 invention; no `handler=`/`tool_name=`/`timeout_ms=` kwargs anywhere; no `M6_REGISTRY.register(...)` anywhere | **RESOLVED** |
| 4 | RouterContext.archetype firm-level (tier4_independent_ria) | R1 AC1.2 comment: "firm-level: `tier1_investment_bank`..`tier5_hedge_fund`; NOT M3's client-level"; §Integration Point with M12 request example uses `"archetype": "tier4_independent_ria"`; §Hypothesis Strategy composite uses `Archetype.tier4_independent_ria` throughout; F2 fixture `_COMMON` uses `archetype="tier4_independent_ria"`; Appendix C DECISION-LOG Fix 4 entry explicit. All `mass_affluent` residuals are in Review-Fix-Traceability row 4 or DECISION-LOG rejection context — no live examples | **RESOLVED** |
| 5 | Task 19 exists (cross-module version match) | §Tasks table row 19 "Cross-module version-match test (NEW v0.2.0 — Fix 5)"; deliverable `tests/integration/test_cross_module_version_match.py`; Appendix A A7 + A17 repointed to Task 19; Appendix E.3 ships worked test skeleton with both `test_tool_kind_names_subset_of_m6_registered` + `test_pipeline_kind_names_subset_of_m8_pipeline_names` under `@pytest.mark.xfail(strict=False)` | **RESOLVED** |
| 6 | m8.research_pipeline_* and m6.composed_goal_tracking → PENDING-CONFIRM | §Known Blockers row 5 "DOWNGRADED from v0.1.0 RESOLVED" — status PENDING-CONFIRM-WITH-M8; row 6 PENDING-CONFIRM-WITH-M6; FSI Intent Taxonomy footnotes ¹ ² flag each entry; AC2.6 cites pending status; Task 19 xfails on both subsets | **RESOLVED** |
| 7 | M12 declared as consumer | Banner line 8: "**M12 Supervisor Model** (primary and only direct caller in Phase 2)"; §Architecture Clarification bullet 2 with ARCH-05 v2 line 275-310 citation; §Integration Point with M12 top-level section; Appendix D cross-reference table adds M12 row labeled "(new in v0.2.0)"; M6 explicitly described as NOT a consumer | **RESOLVED** |
| 8 | identity: AidClaims in RouterContext + Authority Scope Matrix + aid_authority_denied | R1 AC1.2 adds `identity: AidClaims`; AC1.9 self-consistency validator; §Authority Scope Matrix (NEW subsection, 8 rows + exclude precedence); R11 AC11.1 VALID_REASON_CODES grows 12→13 adding `aid_authority_denied`; R12 AC12.9 post-LLM fail-closed check; §Error Code Map row 13; AC5.8 Role=agent + TRADE_INQUIRY downgrade; B.3 models.py imports `AidClaims` from m1_identity + `@model_validator(mode="after")`; Appendix E.5 `test_authority_scope.py`; fixture F2 ships 3 AID variants. Cross-verified against m1-agent-identity.md line 81: archetype is string claim — AC1.9 string-vs-string comparison is correct | **RESOLVED** |
| 9 | FakeLlmClient.responses accepts Exception values | R4 AC4.3: "`FakeLlmClient(responses: dict[str, LlmClassification \| Exception])`"; Exception values raised verbatim; Appendix B.1 shows `if isinstance(result, Exception): raise result`; Task 15 exercises every reason code via Exception injection | **RESOLVED** |
| 10 | HMAC-SHA-256 with tenant-scoped key | R8 AC8.1 rewritten with `hmac.new(tenant_key_bytes, ..., sha256).hexdigest()`; new file `hmac_util.py` spec'd in Appendix B.2 with `_resolve_tenant_hmac_key` + `compute_utterance_digest` + `@lru_cache(maxsize=128)`; `IntentRouterConfig.tenant_hmac_key_vault_path` new field (SHARED-WITH-M5 row 2); R14 AC14.7 fail-closed Vault resolution; R13 AC13.4 hmac allowed globally; Task 6 extension ships `test_hmac_util.py` with cross-tenant divergence (Appendix E.4); DECISION-LOG Fix 10 entry | **RESOLVED** |
| 11 | CLIENT_HOUSEHOLD_SUMMARY → RESEARCH_HOUSEHOLD_SUMMARY rename | R2 AC2.1 lists 11 enum values with `RESEARCH_HOUSEHOLD_SUMMARY` at position 4 (string value `research.household_summary`); §FSI Intent Taxonomy table row 4; AC2.9 new prefix invariant; Appendix A A19 (NEW) import-time prefix-kind consistency; §LLM Contract JSON Schema Example `intent.enum` contains `research.household_summary` (not `client.household_summary`) with explicit negative unit test; SCHEMA_VERSION 1.0.0→1.1.0 (AC15.3); all residual `client.household_summary` in rename discussion / negative assertions only | **RESOLVED** |
| 12 | Steering Rule 8 in §Steering Rules table | §Steering Rules M9 Must Honor now has Rule 8 row: "Fail-closed on ANY compliance check failure" addressing R8 + R7 + R12 AC12.9 + §Taxonomy Invariants. §Steering-Rule Traceability (v0.2.0) table also includes Rule 8. §Taxonomy Invariants "Steering Rule 8 invariant" retained | **RESOLVED** |
| 13 | SlowFakeLlmClient for deterministic timeout testing | R4 AC4.9: `SlowFakeLlmClient(block_ms, timeout_ms)` sleeps min then raises `LlmTimeoutError` if block_ms>timeout_ms; R1 AC1.8 pins mechanism: `SlowFakeLlmClient(block_ms=3000) + timeout_ms=1500` → route() returns <3000ms AND reason_code="llm_timeout"; R15 AC15.1 adds to __all__ (11 names); Appendix B.1 shows the class; Task 15 uses it | **RESOLVED** |
| 14 | taxonomy.py exempted from test_no_m8_string_ref.py | R12 AC12.6 rewritten: "`taxonomy.py` is explicitly exempted from this scan (Fix 14) — it must contain literal strings like `'m8.research_pipeline_1'` by design. Exemption is hardcoded in the test: `EXEMPT_FILES = {'src/m9_intent_router/taxonomy.py'}`"; AC18.1 cross-cites the exemption | **RESOLVED** |

**All 14 Required Fixes: RESOLVED.** Zero PARTIAL. Zero REGRESSED.

---

## 1. Completeness — 9.1/10 (Δ +0.7)

### Evidence

- **19 numbered requirements (R1–R19), ~145 ACs.** Up from 18 R's in v0.1.0. R19 (Concurrency Defense-in-Depth) new per Recommended Fix 8.
- **19 atomic tasks.** Task 19 (cross-module version-match) closes v0.1.0 broken reference. Tasks 6 and 8 absorb HMAC and authority-scope extensions cleanly.
- **§Review Fix Traceability populated** with 14 Required + 11 Recommended Fixes, each mapping to spec section / AC / task.
- **8 restored sections, all implementation-ready**: §Integration Point with M12 (replaces deleted §Integration Point with M6); §Tasks (19 atomic); §Hypothesis Strategy Approach (`utterance_variants()` `@composite`); §Confidence Threshold Table (21 rows — up from 12); §Entity Extraction Regex Library (6 slots + 50-ticker whitelist); §MNPI-Shape Patterns (4 categories + precedence); §Error Code Map (13 rows — up from 12); §LLM Contract JSON Schema Example (Bedrock toolConfig + Fix 11 enum).
- **§Integration Test Journey** new section with 7 scripted end-to-end scenarios.
- **§Fixtures Catalog** new section F1–F5 centralizes tenant HMAC key, 3 AID variants, router context factory, fake LLM factory, `IntentRouterConfig`.
- **Appendix E** Worked Test Skeletons — 5 subsections (E.1 Task 13 confidence thresholds; E.2 Task 15 reason-code meta; E.3 Task 19 cross-module version-match; E.4 Task 6 HMAC; E.5 Task 8 authority scope).
- **Appendix A grew** 18 → 19 invariants — A19 (prefix-kind consistency, Fix 11) added at import-time; A17 now points to Task 19 integration-test.

### Strengths

- **Task 19 xfail posture is honest.** `strict=False` — silent upgrade when M6/M8 ship manifests. Matches M11 v2 discipline.
- **§Integration Test Journey Scenario 4 (authority denial)** stress-tests Fix 8 end-to-end: role=agent, missing `plan.read`, classified to `client.plan_summary` at 0.94 → `aid_authority_denied` with confidence preserved and denied-scope-name NOT in audit. Exercises AC5.8 + AC12.9 + §Authority Scope Matrix simultaneously.
- **Fixtures F2 ships 3 AID variants** with explicit `authority_excludes=["trade.execute"]` on agent — directly unlocks Scenarios 3 and 4 without drift.
- **§Phase 2 Scope OUT-of-scope list** explicitly defers multi-turn clarification, non-Bedrock providers, intent-weighted load shaping, channel-specific hints, multilingual taxonomy, conversation memory, cost attribution. No silent scope creep.
- **Known Blockers table grew 8 → 13 rows** — added ARCH-09 matrix alignment (NEW row 1), Tenant HMAC key provisioning (NEW row 12), SHA migration seam (NEW row 13). Honestly downgraded rows 5 and 6 from RESOLVED to PENDING-CONFIRM.

### Weaknesses (HARSH)

- **Appendix B.1 `FakeLlmClient` skeleton calls `_fixture_key(utterance)`** (line ~603), undefined anywhere. Fixture F4 uses correct `compute_utterance_digest(u, fixture_tenant_hmac_key)`. The B.1 comment acknowledges the mismatch but the sketch still contains the undefined call. NON-BLOCKING but implementers will need to reconcile. **Recommendation:** inline the hmac call in B.1 or delete `_fixture_key` and reference Fixture F4.
- **Appendix B.4 `route.py` sketch calls `_empty_tenant_key()`** (line ~834), undefined. Invalid-utterance-length short-circuit computes `digest=compute_utterance_digest("", _empty_tenant_key())`. **Recommendation:** skip digest computation entirely on invalid length (it's meaningless anyway) OR define the helper explicitly.
- **Known Blockers rows 5 and 6 target resolution is "Phase 2 Week 34" implicitly** but no column enumerates trigger event in a SHARED-WITH-OWNER format. Add an "ETA / Trigger" column or reference cross-reference-maintenance entries.
- **No forward-compat note for `prior_turns_summary` Phase 3 semantics.** AC1.7 says accepted-but-ignored in Phase 2. OUT-of-scope defers multi-turn. Implementers don't know whether Phase 3 will read the field or migrate.
- **Appendix D cross-reference table has M12 row** labeled "(new in v0.2.0)" but no M12 spec file path. Cross-reference-maintenance subsection doesn't list M12's expected citation line.

### What would make it a 10

Fix `_fixture_key` / `_empty_tenant_key` undefined-helper references. Add "ETA / Trigger" column to Known Blockers SHARED/PENDING rows. Pin Phase 3 `prior_turns_summary` semantics forward.

---

## 2. Accuracy — 8.6/10 (Δ +3.1)

The big jump. All four severe v1 accuracy defects are fixed with verifiable evidence.

### Evidence

Cross-verified against: ARCH-09 lines 302-315 (dependency matrix); ARCH-07 line 57 (Supervisor Haiku `<500ms`); m1-agent-identity.md lines 63-100 (AidClaims shape); m9-intent-router.md itself (residual-reference greps).

### Strengths

- **ARCH-09 matrix alignment exact.** Banner quotes row M9 = `* . . . * . . . . . . . .`, matches ARCH-09 line 312 character-for-character. Column 9 verified against row M12 line 306 — position 9 is `*`, every other row's position 9 is `.`. Spec's "M12 is primary and only direct caller" is correct.
- **ARCH-07 latency citation honest.** R16 AC16.4 explicit split: ARCH-07 SOURCED = `p_max<500ms`; M9 DECISION-LOG INTERNAL SLO = p50<200/p95<500/p99<1000. ARCH-07 line 57 publishes only `less than 500ms`, nothing else.
- **No `VendorAdapter(handler=..., tool_name=..., timeout_ms=...)`** anywhere. Grep confirms. Deleted §Integration Point with M6 left no residue. §Why NOT a VendorAdapter subsection states the real M6 Protocol shape explicitly.
- **`AidClaims.archetype == RouterContext.archetype.value` self-consistency is type-correct.** m1-agent-identity.md line 81 declares `archetype` as `string` (M5 Archetype enum value). AC1.9 compares string to string via `context.identity.archetype != context.archetype.value` — `Archetype(str, Enum).value` returns a string. Types line up.
- **`m8.research_pipeline_*` and `m6.composed_goal_tracking` are honestly PENDING.** §Known Blockers rows 5 and 6 explicitly "DOWNGRADED from v0.1.0 RESOLVED". FSI Intent Taxonomy footnotes flag each row. Task 19 xfails on both subsets.

### Weaknesses (HARSH)

- **Banner line 12 (Design Sources) is parenthetical-dense.** The ARCH-07 disclaimer is correct but the single-line banner is becoming hard to scan. Minor readability.
- **R19 `threading.Semaphore(16)` cap hardcoded** with no DECISION-LOG entry justifying "why 16". AC19.1 just says "Cap is hardcoded; not tenant-scoped in Phase 2". Add a DECISION-LOG entry with queue-depth × p99-latency math.
- **`m8.research_single_tool` as `kind="pipeline"`** is semantically odd (reads tool-shaped, not pipeline-shaped). Appendix A invariant A9 treats it as a pipeline. Probably a correct modeling decision (M8's single-tool mode IS a length-1 pipeline) but worth one sentence of clarification.
- **`IntentRouterConfig.tenant_hmac_key_vault_path`** uses literal `<tenant_id>` string substitution via `path.replace("<tenant_id>", tenant_id)` (Appendix B.2). Works for Phase 2 but footgun: tenant_id containing literal `<tenant_id>` would double-substitute. Should use a proper format specifier.

### What would make it a 10

DECISION-LOG entry justifying Semaphore(16). One-sentence clarification of `m8.research_single_tool`. Pin `<tenant_id>` placeholder-substitution format.

---

## 3. Security — 9.1/10 (Δ +0.5)

Already strong in v1; v0.2.0 adds HMAC (Fix 10), concurrency defense-in-depth (Fix 19), authority-scope fail-closed (Fix 8).

### Evidence

- **HMAC-SHA-256 with tenant-scoped Vault-resolved key** (Fix 10). R8 AC8.1 + `hmac_util.py` + `_resolve_tenant_hmac_key` + `IntentRouterConfig.tenant_hmac_key_vault_path`. Cross-tenant rainbow-table attack eliminated.
- **AID authority-scope fail-closed** (Fix 8). R12 AC12.9 post-LLM check against §Authority Scope Matrix. New `aid_authority_denied` reason code. Denied-scope name NOT in audit payload (explicit in §Integration Point with M12 §Response Shape + §Error Code Map row 13).
- **`threading.Semaphore(16)` defense-in-depth** (R19). Blocks, does not reject. Prevents M6/M12 rate-limiter gap letting M9 issue unlimited QPS.
- **MNPI pre-scan still runs before LLM call** (R8 AC8.4). HMAC digest computed once at top of `route()` BEFORE MNPI scan. No MNPI-shape utterance ever reaches Bedrock.
- **MNPI category leakage canary (A16)** retained. Tenant-id dimension added to counter (Recommended Fix 1 landed — AC8.9 + AC9.1 adds `tenant_id` to audit payload).
- **Zero credentials in code (R14).** `.env.example` shipped without `if present` hedge (AC14.4 — Recommended Fix 7). Vault path for tenant HMAC key is template, no secret material. boto3 default credential chain unchanged.
- **Forbidden imports** intact. `hmac` allowed globally (R13 AC13.4). `threading.Semaphore` allowed (AC13.7).
- **Positive allow-list module boundary** (R12 AC12.2) now `m1_identity` + `m5_config_loader` only. `m3_schema_registry` removed.
- **Audit schema meta-validation** (Recommended Fix 9) via Task 10 extension.

### Weaknesses (HARSH)

- **`_resolve_tenant_hmac_key` fetches via `boto3.client("secretsmanager")`** (Appendix B.2 line ~678). Tenant A's M9 pod should not resolve Tenant B's HMAC key. Cross-tenant isolation depends on per-tenant IAM scoping — an Ops/Vault concern — but Known Blockers row 12 doesn't name this requirement. Add.
- **`@lru_cache(maxsize=128)` caches HMAC key indefinitely per process.** Key rotation requires pod restart. Not a defect but worth a Known Blockers row for rotation cadence + TTL.
- **HMAC key caching means compromised process has persistent access** to every tenant's key it has seen. Standard threat model for in-memory caching. Phase 3 item (Vault dynamic secrets + short TTL) worth naming.
- **Test fixture key `b"m9-hypothesis-fixture-key-32b!!!"`** in §Hypothesis Strategy Approach is labeled non-production. AC14.1 regex scans `src/` only, not `tests/` — spec should state tests/ is explicitly OUT of credential-scan scope.
- **Bedrock `maxTokens=2000`** unchanged from v0.1.0. Adequate for tool invocation but no budget guard against long thinking preamble. Minor.

### What would make it a 10

Add Known Blockers rows for HMAC cross-tenant IAM isolation, key rotation cadence + TTL. Acknowledge tests/ is out of credential-scan scope in AC14.1.

---

## 4. Testability — 8.7/10 (Δ +0.7)

Fix 9 (Exception injection) + Fix 13 (SlowFakeLlmClient) + Recommended Fixes 3, 4, 5, 6, 9 landed.

### Evidence

- **`FakeLlmClient.responses: dict[str, LlmClassification | Exception]`** (Fix 9). Exception values raised verbatim. Unlocks deterministic exercise of every VALID_REASON_CODES entry.
- **`SlowFakeLlmClient(block_ms, timeout_ms)`** (Fix 13). AC1.8 test mechanism pinned without real boto3 timeout.
- **§Confidence Threshold Table 12 → 21 rows.** Inf/-Inf Pydantic rejection (9, 10 — Recommended Fix 4); Role=agent + TRADE_INQUIRY downgrade (11, 12, 13 — Fix 8 / AC5.8); `fallback_enabled=False + 4xx` (19 — Recommended Fix 6); malformed-output branches (20, 21).
- **Task 12 concurrency smoke test** (Recommended Fix 3). 50 threads × 20 calls. AC19.3.
- **Honest Hypothesis CI budget** (Recommended Fix 5). AC10.4: "3 property files × 100 examples × 500 ms ≈ 150 s worst-case" — documented, not hidden.
- **Audit schema meta-validation** (Recommended Fix 9). Task 10 extension `test_audit_schema_meta.py`.
- **19 atomic tasks.** Task 19 closes A7/A17 broken reference.
- **Fixtures F1–F5** centralize test scaffolding.

### Strengths

- **§Confidence Threshold Table** is now the most complete testability artifact in the spec. 21 rows = 21 `parametrize` entries = exhaustive boundary + error-matrix coverage. Row 13 (advisor + TRADE_INQUIRY high — NO downgrade) is the key negative test for Fix 8 — catches regression where someone implements the downgrade unconditionally.
- **Appendix E.1–E.5 worked test skeletons** for the five most subtle tests.
- **Task 19 xfail=strict=False** correctly handles the PENDING-CONFIRM cross-module contracts.

### Weaknesses (HARSH)

- **`FakeLlmClient` skeleton keying ambiguity.** B.1 sketch calls `_fixture_key(utterance)`; Fixture F4 correctly uses `compute_utterance_digest(u, fixture_tenant_hmac_key)`. If a test accidentally keys on plain SHA, the response silently misses and the fake returns default `UNSUPPORTED`. **Recommendation:** delete `_fixture_key(...)` from B.1 and inline the HMAC computation.
- **Task 12 concurrency test** asserts "max concurrent classify() observed ≤ 16" but observation mechanism isn't pinned. AC19.4 mentions `_inflight_count()` helper but AC19.3 should name it explicitly.
- **Appendix E.2 `test_all_13_reason_codes_exercised` takes a fixture** `all_scenarios_producing_reason_codes` which isn't defined anywhere in the spec. Implementers will wire it in `conftest.py`.
- **No property test for AID authority-scope edge cases.** Fix 8 adds extensive AID-driven logic but no property invariant asserts "every AC5.8 downgrade ⇒ role=agent AND intent=TRADE_INQUIRY" or "every `aid_authority_denied` ⇒ required_scopes ⊄ authority_scope". Add to Task 11.
- **`SlowFakeLlmClient` sleep `min(block_ms, timeout_ms)`** may under-sleep on flaky CI. AC1.8 asserts `< 3000 ms` — safe 50% margin over `block_ms=3000`. Minor.

### What would make it a 10

Reconcile `_fixture_key` → `compute_utterance_digest` in B.1. Pin concurrency-observation mechanism in AC19.3. Define `all_scenarios_producing_reason_codes` in Appendix E.2 or conftest. Add AID-driven property invariants to Task 11.

---

## 5. Design Alignment — 9.0/10 (Δ +2.5)

The huge jump. Every v1 alignment defect resolved against ARCH-09 + ARCH-07 + ARCH-05 v2 + steering.

### Evidence

- **ARCH-09 dependency matrix alignment exact** — row M9 and column 9 verified character-by-character.
- **ARCH-05 v2 §Supervisor Routing Logic integration** (Fix 8) via `context.identity: AidClaims`. AC1.9 self-consistency enforces supervisor built context from verified AID.
- **ARCH-07 `<500ms` Haiku cited exactly where it appears** (line 57). Percentile breakdown now M9 DECISION-LOG property.
- **Steering Rule 7** (M6 gateway): R17 + R18 + §Architecture Clarification. M9 never calls MCP tools.
- **Steering Rule 8** (fail-closed): in §Steering Rules table (Fix 12).
- **Steering Rule 13** (Haiku for routing): R3 `BedrockHaikuClient`.
- **Steering Rule 14** (NO LLM for compliance): R2 AC2.3 + Appendix A A4 + §Taxonomy Invariants "Rule 14 invariant".
- **Steering Rule 15** (LLM provider abstracted): R4 Protocol + 1 real + 2 fakes + 3 stubs.
- **Steering Rule 20** (zero credentials): R14 + Vault HMAC key.
- **Steering Rule 32** (per-module security): R8 + R9 + R12 + R13 + R14 + R19.

### Strengths

- **§Architecture Clarification** states "This is the single source of truth" for ARCH-09 matrix. v0.1.0 misread acknowledged explicitly ("v0.1.0 was a misread, not a proposed amendment"). Honest.
- **M8 indirect-integration story clean.** R18 rewritten: "M8's LangGraph pipeline consumes a `RoutingDecision` from `PipelineState.routing_decision`. M8 does NOT call M9." Matches ARCH-09 row M8 column 9 = `.`.
- **§Integration Point with M12 §Why NOT a VendorAdapter** subsection is a strong learning artifact closing the door on v0.1.0's pattern.
- **Appendix D cross-reference table** has M12 row added. ARCH-07 row pinpoints line 57. ARCH-09 row pinpoints lines 302-315.

### Weaknesses (HARSH)

- **`m8.research_single_tool` as `kind="pipeline"`** is semantically odd (see Accuracy weakness). M8 Phase 2 spec should clarify; Known Blockers row 5 could note.
- **R17 title "REPLACES v0.1.0 §Integration Point with M6"** is correct for v0.2.0 framing but stale-prone. Minor future-hygiene.
- **Steering Rule 8 in §Steering Rules table AND §Steering-Rule Traceability** — mild duplication; prune one or mark canonical vs summary.
- **Appendix D cross-reference maintenance** lists triggers for M12/M8/M6/M5 but not ARCH-09 itself. If ARCH-09 changes, M9's matrix citations need updating. Add trigger.

### What would make it a 10

Clarify `m8.research_single_tool` semantics. Prune duplicated Steering Rule 8 traceability. Add ARCH-09 change-trigger to cross-reference maintenance.

---

## 6. Gaps — 8.4/10 (Δ +1.9)

### Evidence

- **§Known Blockers** 8 → 13 rows. New: (1) ARCH-09 matrix alignment (RESOLVED v0.2.0), (12) Tenant HMAC key provisioning (PENDING Week 28), (13) SHA migration seam (RESOLVED single-file refactor).
- **§Review Fix Traceability** populated with 14 + 11 rows. No placeholder.
- **Appendix D cross-reference maintenance** names triggers for M12, M8, M6, M5, Bedrock model-ID verification, LLMJ-v2.
- **9 of 9 v1-flagged gaps addressed.** ARCH-09 mismatch Known Blocker (row 1); identity (Fix 8); M12 consumer (Fix 7); FakeLlmClient Exception injection (Fix 9); Task 19 defined (Fix 5); HMAC tenant-scoping (Fix 10); local concurrency cap (Fix 19).

### Strengths

- **§Known Blockers downgrades honest.** Rows 5 (M8 naming) and 6 (M6 composed_goal_tracking) moved from v0.1.0 RESOLVED to v0.2.0 PENDING-CONFIRM. No "RESOLVED — SemVer discipline" paper-over.
- **Rename policy for `selected_target.name` landed** (Recommended Fix 12). AC17.4: MAJOR bump, one-minor-version alias window, audit consumers query on `utterance_sha256` + `intent.value`. DECISION-LOG entry.
- **R10 Luhn deferral explicitly acknowledged** — Review Fix Traceability + §MNPI-Shape Patterns row 3 false-positive column paired.

### Weaknesses (HARSH)

- **Known Blockers row 12** doesn't name cross-tenant IAM-isolation requirement. Ops needs per-tenant Vault policy, not just path.
- **No Known Blocker row for skeleton reconciliation** (`_fixture_key` / `_empty_tenant_key` drift) — low-severity hygiene item.
- **No Known Blocker row for `Semaphore(16)` magic number rationale.**
- **HMAC key rotation policy missing.** No row. `@lru_cache` caches indefinitely.
- **`prior_turns_summary` Phase 3 transition plan unpinned.**

### What would make it a 10

Add 4 Known Blocker rows: (a) HMAC cross-tenant IAM isolation; (b) HMAC key rotation cadence + TTL; (c) Semaphore(16) rationale; (d) prior_turns_summary Phase 3 transition plan.

---

## New Issues Introduced by v0.2.0

No blocking new issues. Four non-blocking observations:

1. **Appendix B.1 `_fixture_key(utterance)`** called but not defined. Fixture F4 uses correct `compute_utterance_digest(utterance, tenant_key)`. B.1 should align. NON-BLOCKING — authoritative path is F4.
2. **Appendix B.4 `_empty_tenant_key()`** called in invalid-utterance-length short-circuit but not defined. NON-BLOCKING — skeleton only.
3. **Duplicate Steering Rule 8 traceability** in §Steering Rules M9 Must Honor + §Steering-Rule Traceability (v0.2.0). Mild redundancy. NON-BLOCKING — content consistent.
4. **`m8.research_single_tool` as `kind="pipeline"`** target name is semantically unusual. Accepted as length-1 pipeline per AC2.6 regex but naming reads tool-shaped. NON-BLOCKING — invariants fire at import.

**No accuracy regressions from v0.1.0.** Residual references to `m6_mcp_gateway` appear only in (a) AC17.1 Protocol-NOT-implemented assertion, (b) §Why NOT a VendorAdapter, (c) Appendix E.3 Task 19 xfail test, (d) Review Fix Traceability descriptions. All appropriate contexts. Residual `mass_affluent` references appear only in Review Fix Traceability row 4 (describing the fix) and DECISION-LOG Fix 4 (explicitly rejecting it). No live examples. Residual `client.household_summary` / `CLIENT_HOUSEHOLD_SUMMARY` references appear only in rename discussion (Changelog, Known Blockers row 8, Review Fix Traceability row 11, DECISION-LOG Fix 11, §LLM Contract JSON Schema Example negative assertion). No live occurrences.

---

## Required Fixes for v0.3.0

None. All 14 v1 Required Fixes are RESOLVED.

## Recommended Polish Items for v0.2.1 (optional — not blocking build)

1. Reconcile Appendix B.1 `FakeLlmClient` sketch with Fixture F4 — replace `_fixture_key(utterance)` with `compute_utterance_digest(utterance, self._tenant_key)` and add `tenant_key: bytes` to `FakeLlmClient.__init__`.
2. Define or remove `_empty_tenant_key()` in Appendix B.4 — prefer removing digest computation on invalid-length path.
3. Add 4 Known Blocker rows: HMAC cross-tenant IAM isolation; HMAC key rotation cadence + TTL; `Semaphore(16)` rationale; `prior_turns_summary` Phase 3 transition plan.
4. Pin concurrency-observation mechanism in AC19.3.
5. Add AID-driven property invariant to Task 11: "every AC5.8 downgrade ⇒ role=agent AND intent=TRADE_INQUIRY"; "every `aid_authority_denied` ⇒ required_scopes ⊄ authority_scope".
6. One-sentence clarification of `m8.research_single_tool` as length-1 pipeline.
7. Prune duplicated Steering Rule 8 traceability — keep one canonical table.

---

## Final Verdict

**8.47 / 10 — GO.**

The v0.2.0 rewrite lands where M7 v0.3.0 and M11 v0.2.0 landed: surgical, honest, traceable. Every one of the 14 v1 Required Fixes is RESOLVED with verifiable spec-inspection evidence. Accuracy jumps +3.1 points because all four severe v1 accuracy defects (ARCH-09 matrix misread, ARCH-07 citation fabrication, fake M6 VendorAdapter shape, archetype firm-vs-client mixup) are fixed at the spec level against source-of-truth documents — not papered over with DECISION-LOG overrides. Design Alignment jumps +2.5 because the dependency graph now matches ARCH-09 matrix row M9 + column 9 exactly.

The §Review Fix Traceability table with 14 + 11 rows, the restored §Integration Point with M12 replacing the deleted §Integration Point with M6, the §Authority Scope Matrix supporting Fix 8, the §MNPI-Shape Patterns with precedence and validator, the §Confidence Threshold Table grown from 12 → 21 rows, the 19-task §Tasks with Task 19 closing the broken reference, the §Integration Test Journey with 7 narrated scenarios, and the Appendix E worked test skeletons constitute one of the most complete spec rewrites in this project.

Two cosmetic skeleton defects (`_fixture_key` / `_empty_tenant_key` undefined) and one minor duplication (Steering Rule 8 table doubled) are the only non-trivial residue. None block build. All four v1 SEVERE accuracy defects are closed with evidence traceable to ARCH-09 lines 302-315, ARCH-07 line 57, `m6_mcp_gateway/adapters.py`, and `m1-agent-identity.md` line 81 respectively.

M9 v0.2.0 is cleared for build. Proceed to Playbook Step 5 (Build) with the 7-item recommended-polish list in mind for v0.2.1 maintenance. The Task 19 xfail posture will auto-upgrade when M6 Phase 2 composed-tool manifest and M8 v0.1.0 `PIPELINE_NAMES` land — no re-review required.

---

## Score Summary

| Dimension | v1 | v2 | Δ |
|-----------|----|----|---|
| Completeness (25%) | 8.4 | 9.1 | +0.7 |
| Accuracy (20%) | 5.5 | 8.6 | +3.1 |
| Security (20%) | 8.6 | 9.1 | +0.5 |
| Testability (15%) | 8.0 | 8.7 | +0.7 |
| Design Alignment (10%) | 6.5 | 9.0 | +2.5 |
| Gaps (10%) | 6.5 | 8.4 | +1.9 |
| **Weighted Total** | **7.42** | **8.47** | **+1.05** |

**Verdict: GO.** Proceed to build.
