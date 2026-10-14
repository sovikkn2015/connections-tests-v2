# M11-REST Adapters — LLMJ Review v2 (Second Pass)

**Spec Version:** 0.2.0 (1,560 lines)
**Reviewer:** adapter-agent (second pass, same harshness bar as v1)
**Date:** 2026-04-25
**v1 Score:** 7.27 / 10 CONDITIONAL GO
**Target:** ≥ 7.5 for GO (8.0+ preferred)
**Playbook Step:** 4 of 7

---

## Weighted Score: 8.52 / 10 — **GO** (proceed to Step 5 Build)

| # | Dimension | Weight | v1 | v2 | Δ | Weighted |
|---|-----------|--------|----|----|---|----------|
| 1 | Completeness | 25% | 8.2 | 8.7 | +0.5 | 2.175 |
| 2 | Accuracy | 20% | 5.8 | 8.0 | +2.2 | 1.60 |
| 3 | Security | 20% | 8.4 | 9.1 | +0.7 | 1.82 |
| 4 | Testability | 15% | 7.5 | 8.3 | +0.8 | 1.245 |
| 5 | Design Alignment | 10% | 7.7 | 8.5 | +0.8 | 0.85 |
| 6 | Gaps | 10% | 5.0 | 8.3 | +3.3 | 0.83 |
| — | **TOTAL** | **100%** | 7.27 | — | **+1.25** | **8.52** |

Bands: 8.0+ = GO, 7.5-7.9 = MARGINAL GO, 6.5-7.4 = CONDITIONAL GO, < 6.5 = NO GO.

**Verdict: GO.** The rewrite lands the two severe accuracy problems from v1 (fabricated RES-08 citations + eMoney allow-list mismatch with M7), closes the observability and idempotency gaps, and adds real fast-check property tests. Of the 17 required fixes, 17 landed — though 3 of them have Appendix F traceability references that do NOT resolve to the section headers claimed (the same NI-1 regression that bit M7 v0.2.0). Those are annotated below as NI-1 through NI-3 and can be patched post-build; they do not justify another CONDITIONAL-GO lap.

---

## Fix Verification Table — Required Fixes (17)

| # | v1 Required Fix | Landed? | Evidence | Quality |
|---|-----------------|---------|----------|---------|
| 1 | Kill fabricated RES-08 rate-limit citations (AC5.2, AC15.2, Appendix E rows 1-4) | ✅ YES | AC5.2 now cites Salesforce Platform API Limits Cheatsheet URL for SFDC; Orion/eMoney/Schwab all explicitly `PENDING-VERIFICATION` with named verification gates (portal login, Fidelity partnership, NDA). Appendix E rows 1-4 rewritten. No `RES-08 §2.1/§3.1/§5/§6.1` fabrications survive — spot-checked all four. | A |
| 2 | Reconcile eMoney allow-list with M7 `EMoneyPlanSummary` | ✅ YES (with label typo) | AC8.5 rewritten: **Required (7)** = planId, clientId, planName, probabilityOfSuccess, asOfDate, createdAt, updatedAt. **Optional** = scenarioId, householdId, planType, totalAssets, totalLiabilities, retirementGoal, monteCarlo, annualSavingsRate, annualSpending, socialSecurityEstimate, pensionIncome, goalIds, assumptions, recommendations. Verified field-for-field against `src/m7_schema_translators/emoney/models.py` (read 2026-05-05): set-equal to M7's 21 top-level fields. `goalIds` correctly specified as `array of string — IDs only, NOT objects` (matches M7 `list[str]`). **Minor:** AC8.5 says "Optional (15)" but lists 14 items — off-by-one label, content is correct. | B+ |
| 3 | Document SFDC PascalCase vs M7 snake_case mismatch as SHARED-WITH-M7 | ✅ YES | §Known Blockers row 4 + dedicated §Integration Point with M7 subsection + Appendix E row 5 + `tests/integration/test_m7_sfdc_shape.py` gate. Reproduction explicit (`SalesforceFSCAccountContact(**vendor_payload)` → `extra_forbidden`). Resolution options (a/b/c) clearly owned by M7. | A |
| 4 | Mark Orion URL paths as PENDING-VERIFICATION | ✅ YES | AC2.11 + §Known Blockers row 6 + Appendix E row 21 + Task 11 startup probe. Paths explicitly annotated in Appendix A. | A |
| 5 | Add SEC EDGAR to Phase 2 scope OR provide ARCH-09 cross-reference | ✅ YES | §Explicitly OUT of Scope bullet + Appendix E row 22. Reasoning: EDGAR is Phase 1 per ARCH-09 but it feeds M8 Research Pipeline, not the RIA meeting-prep journey. Deferred to M8 build window. Defensible — EDGAR is not a custodian/CRM/planning/portfolio vendor and the RIA lighthouse does not need 10-Ks. | A |
| 6 | Declare observability hand-off to M10 | ✅ YES | AC7.9 + §Observability Hand-Off to M10 (Option A default sidecar, Option B opt-in OTEL) + Events Escalated table + Appendix E row 32. Concrete: pino stdout → fluent-bit/vector sidecar → Langfuse + Datadog/Loki + M10. | A |
| 7 | Specify concurrency + K8s resource requests/limits | ✅ YES | AC3.9 (`undici.Agent({connections: 10})`, env override `ADAPTER_UNDICI_CONNECTIONS` 1-64) + AC3.10 (requests 100m/256Mi, limits 500m/512Mi, Phase 2 singleton, Phase 3 HPA). Deployment YAML snippet in §mTLS + Deployment Template. | A |
| 8 | Add concrete Schwab RT-rotation-failure alerting path | ✅ YES | AC4.13: pino `fatal` `{event:"auth.schwab.rt_rotation_failed", severity:"CRITICAL"}` → M10 sidecar → PagerDuty/OpsGenie within 5 min, SLO ack ≤ 15 min. Appendix C.4 Step 4 includes full code sketch. §Events M10 Escalates table locks the escalation. | A |
| 9 | Specify how `test_m11_error_contract.ts` forces each error class deterministically | ✅ YES | AC16.4 adds a 12-row mechanism table: FakeClock for OAuth expiry, msw `.use` sequence for 5xx/circuit/timeout, rawPlanBody fixture for eMoney, FakeSecretsClient `instance_url` for SSRF, cert-file rewrite for mtls_degraded, missing header for missing_firm_id. Every mechanism is deterministic — no wall-clock sleeps. | A |
| 10 | Add property-based Zod fuzz tests (fast-check) | ✅ YES | AC18.6 + dedicated §fast-check Strategy Approach section with a worked 50-line example for `sfdc.fetch_client` (in-domain + out-of-domain generators, 1000 runs, ≥99% accept/reject thresholds) + per-tool matrix table covering all 14 tools + Tasks 6/10/13/16 call it out per adapter. Mirrors M7's Hypothesis Strategy. | A |
| 11 | Narrow Schwab ServiceAccount's Secret-write RBAC | ✅ YES | §RBAC Template Schwab variant: concrete Role + RoleBinding YAML, `resourceNames: ["m11-schwab-refresh-token"]`, `verbs: ["get","update"]`, no wildcards. Default SFDC/Orion/eMoney Role granted `["get"]` only. | A |
| 12 | Add SSRF validation for vendor-returned URLs | ✅ YES | AC14.10 + `src/ssrf.ts` in shared SDK (Task 2) + Appendix C.1 Step 5 (SFDC OAuth flow) + Appendix D.7 worked scenario + Appendix E row 30 + `vendor_ssrf_blocked` errorCode added to R16 AC16.3. Covers https-only + FQDN allow-list match + DNS resolve + RFC1918/link-local/loopback/ULA reject. | A |
| 13 | Resolve Phase 3 Orion Basic-auth toggle concretely | ✅ YES | AC4.12 + Appendix C.2 Phase 3 subsection + Appendix E row 8. Helm values toggle `ORION_AUTH_MODE=basic` → pod redeploy (NOT hot-reloadable). Separate Secret path `m11/orion/basic_credentials → {username, password}`. Both branches test-covered per Task 9. | A |
| 14 | Declare idempotency semantics for SFDC writebacks | ✅ YES | AC8.9 + T-SF4/T-SF5 in §Design + Appendix D.8 worked scenario + Appendix E row 18. Uses SFDC `If-Match` ETag (captured as `_etag` sibling in `fetch_client` response). 412 → adapter 409 `vendor_conflict`, non-retryable. M6 re-fetches + retries once. | A |
| 15 | Bound auth.ts token cache with LRU | ✅ YES | AC4.14 (`LRUCache<string, CachedToken>({max: 1024, ttl: null, updateAgeOnGet: true})`) + AC3.7 (LRUCache re-export from shared SDK) + AC12.2 (`lru-cache` added to package allow-list) + Appendix E row 31 + Task 5 1025-entry eviction test. Matches R5/R6 LRU cap of 1024. | A |
| 16 | Add vendor-schema-drift change process | ✅ YES | AC15.6 (6-step process) + Appendix E row 25 + Task 22 creates `src/m11_rest_adapters/docs/vendor-schema-drift-playbook.md`. 48h SME review SLA. Compliance classifies safe-summary vs MNPI-like before allow-list. | A |
| 17 | Document Schwab trade-submission descope | ✅ YES | §Phase 2 Lighthouse Scope (Schwab row READ-ONLY) + §Explicitly OUT of Scope first bullet + AC2.4 explicit `No schwab.submit_trade` + §Design Schwab Tools "NOT included Phase 2" paragraph + Appendix A footer row + Appendix E row 24. Cites IMPL-06 Blocker 1. | A |

**Score: 17/17 landed.** 3 of 17 have traceability-table references that don't resolve cleanly (see NI-1/NI-2/NI-3 below) — content exists in spec; Appendix F just points to the wrong header or wrong row number.

## Fix Verification Table — Recommended Fixes (10)

| # | v1 Recommended Fix | Landed? | Evidence |
|---|--------------------|---------|----------|
| R1 | Docker image-size math | ✅ | AC11.5: 80 + 40 + 10 ≈ 130 MiB with 20 MiB buffer. Called out dominant dep (`@aws-sdk/client-secrets-manager` ~20 MiB). |
| R2 | Latency targets | ✅ | AC1.5: p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms. Task 23 enforces 200-call sample. |
| R3 | Chaos tests | ✅ | Task 23 adds three scenarios: secrets 500 for 30s, DNS fail 10s, vendor TLS hang 15s. |
| R4 | Retry-After edge cases | ✅ | AC5.7: 5 cases (integer, HTTP-date, negative→0, > 300s cap, malformed→default, absent→30, zero→1 minimum). Test matrix in Task 7. |
| R5 | Per-firm token LRU eviction test | ✅ | AC4.14 + Task 5 explicit 1025-entry load + assert firm #1 evicted. |
| R6 | cost_basis conflict one-liner | ⚠ **Partial (NI-3)** | Stated in Appendix F row R6 only — claimed location "§Integration Point with M7" does NOT actually contain the REST-vs-SFTP tax-lot reconciliation sentence. §What M11 Does NOT Do says "no `cost_basis_method` assignment" but that's a scope-exclusion, not a reconciliation-ownership statement. |
| R7 | Dockerfile SHA256-pin CI check | ✅ | AC11.1 + Task 21 CI check per Appendix F. |
| R8 | Prometheus-compatible metric emission | ✅ | §Observability Hand-Off to M10 Option A (Loki/Datadog log-based metrics) + Option B (OTEL OTLP-stdout → Prometheus via OTel Collector). Acceptable indirection. |
| R9 | Helm values-schema JSON | ✅ | Task 21 adds `charts/m11-rest-adapters/values.schema.json`. |
| R10 | Cross-verify M7 translator coverage vs M11 tools | ✅ | Appendix A totals footnote: 11 read-tool pairs (matching M7 TRANSLATOR_REGISTRY), 2 writeback-only. |

**Score: 9/10 cleanly landed, 1/10 partial (R6 dangling).**

---

## Dangling-Reference Regressions (NI-1 / NI-2 / NI-3)

These are the M7-v0.2.0-style Traceability-Table hazards: Appendix F points at section headers or row numbers that don't contain what's claimed. Content still exists elsewhere — these are markdown hygiene problems, not fix failures. Calling them out so they don't bite the post-build traceability audit.

### NI-1 (dangling ref): Fix #2 cites "§Known Blockers row 12" — wrong row

Appendix F row for Fix #2 (eMoney allow-list reconciliation) lists:
> `**AC8.5**, **§Known Blockers row 12**, **Appendix E row 6**, **Task 13**, **Task 20**`

Counted from the header `## Known Blockers & Pending Items`:

1. Schwab developer-program approval
2. eMoney API access tier
3. SF FSC field names not verified
4. SFDC PascalCase vs M7 snake_case (v0.2.0 new)
5. Orion MarketValue accrued interest
6. Orion URL paths (v0.2.0 new)
7. Schwab sandbox → production OAuth divergence
8. Orion OAuth vs Basic
9. NetworkPolicy egress CIDR churn
10. mTLS cert-manager issuer
11. Rate-limit headers (429 parsing)
12. **Salesforce daily API call budget**  ← what Fix #2 points to (WRONG)
13. Schwab tax-lot field granularity
14. **eMoney "raw plan" vs "summary" boundary**  ← what Fix #2 SHOULD point to

Row 12 is the SFDC daily budget row, not eMoney. Implementation will grep "eMoney" in row 12 and not find it. **Fix:** change `row 12` → `row 14` in the Appendix F cell for Fix #2.

### NI-2 (dangling ref): Fix #17 cites "§Design Schwab Tools — explicit NOT included"

Content EXISTS (§Design Schwab Tools has a paragraph starting `**NOT included Phase 2 (Phase 3 spec):**`, and Appendix A's last table row uses `—` in the # column), but the Appendix F reference phrasing is inconsistent — §Design has no subheader literally called "Schwab Tools — explicit NOT included." The actual header is `### Schwab Tools (Read-Only — Phase 3 descope per Appendix E row 24)`. A reviewer grepping "explicit NOT included" as a header won't find it. Low-impact — the content is on the page, just differently labeled.

### NI-3 (dangling ref): Recommended Fix R6 content lives ONLY in Appendix F itself

Appendix F row R6 claims the cost_basis one-liner lands in "§Integration Point with M7" — but I read that entire section (§Integration Point with M7, lines 813-917) and it does NOT contain the sentence "M7 owns reconciliation between REST and SFTP Schwab tax lots." The only cost_basis reference in §Integration Point with M7 is bullet "No canonicalization (no `cost_basis_method` assignment...)" which is a scope exclusion, not a reconciliation-ownership statement. **Fix:** add one sentence to §Integration Point with M7's "What M11 Does NOT Do" bullet list: "M11 returns raw tax-lot data for Schwab from both REST and (Phase 2) SFTP sub-types. Reconciliation between the two feeds is M7's job, not M11's."

---

## 1. Completeness — 8.7 / 10 (↑ 0.5 from v1)

### Delta vs v1

- **SEC EDGAR resolved** as DEFERRED to M8 Research Pipeline (Appendix E row 22). Defensible: RIA meeting-prep journey does not read 10-Ks. v1 flagged this as a Phase-1-vs-Phase-3 scope ambiguity; v0.2.0 picks a position with cited rationale.
- **Alpha Vantage + News API** resolved as gated by M8 spec (Appendix E row 23). Correct.
- **Dockerfile image-size math** added: distroless 80 MiB + node_modules 40 MiB + dist/ 10 MiB ≈ 130 MiB with 20 MiB buffer (AC11.5). Answers v1 R1.
- **Latency targets**: p50 < 200 / p95 < 1000 / p99 < 3000 ms per tool (AC1.5). Enforced at Task 23 200-sample dress rehearsal.
- **Phase 3 Orion Basic-auth toggle** is now concrete (AC4.12 + Appendix C.2 Phase 3): Helm-values redeploy, separate Secret path.
- Phase-2 scope still 4 adapters × 14 tools. **147 ACs total** (up from 133). 23 tasks.
- **Cold-start / steady-state latency** now split: startup 120s (AC17.2), runtime latency per AC1.5.

### Strengths

- Phase-2 in-scope vs out-of-scope remains explicit. Six scope-out bullets (SFTP, BLPAPI, gRPC, MCP-NATIVE, Wealthbox/Redtail/Envestnet, webhooks).
- Every piece of new content ties to a numbered requirement, an AC, and a specific Appendix E row — the traceability surface is consistent.

### Weaknesses (HARSH)

- **X-Firm-ID vs token firm-claim mismatch** still not explicitly addressed. v1 called this out; v0.2.0 still trusts M6 to have checked, without stating so in §Integration Point with M6. Low-impact but still open.
- **Phase 3 hooks beyond Orion Basic-auth** still sketchy. Task 9 covers Orion; what about Phase 3 Schwab writebacks? v0.2.0 descopes Phase 2 correctly but does not sketch the Phase 3 spec shape (values toggle? new adapter package? new Helm subchart?). Appendix E row 24 only hints.
- **No data-residency / multi-region endpoints** (EU SFDC `*.my.salesforce.com.eu`). v1 flagged this; v0.2.0 egress allow-list includes `*.my.salesforce.com` and `*.salesforce.com` which covers EU hostnames implicitly, but the regional routing rule is not declared.

---

## 2. Accuracy — 8.0 / 10 (↑ 2.2 from v1 — biggest delta)

This is the dimension that killed v1. v0.2.0 lands the two severe problems.

### Fix Evidence

- **Rate-limit citations (v1 problem 1):** AC5.2 rewritten. SFDC cites Salesforce Platform API Limits Cheatsheet URL. Orion/eMoney/Schwab all marked PENDING-VERIFICATION with explicit verification gates (developer-portal login, Fidelity partner portal, Schwab NDA). Appendix E rows 1-4 rewritten. The §5 citation that was egregiously wrong (RES-08 §5 is Payment & Settlement, no eMoney content) is completely gone. **Fabrication eliminated.**
- **eMoney allow-list (v1 problem 2):** I cross-checked AC8.5 field-by-field against `src/m7_schema_translators/emoney/models.py` (read fresh 2026-05-05). M7's `EMoneyPlanSummary` has 21 top-level fields; AC8.5 Required (7) + Optional (14) = 21 matches exactly. Every field maps 1:1. `goalIds` correctly called out as "array of string — IDs only, NOT objects" (M7: `list[str]`). `recommendations` correctly declared as array of `.strict()` `{category, description, priority}` matching M7's `EMoneyRecommendation` frozen model. The v1 failure mode ("every eMoney call fails at M7 Stage 6") no longer applies. `test_m7_emoney_allowlist.py` prevents future drift via set-equality assertion against `EMoneyPlanSummary.model_fields.keys()`.
- **SFDC PascalCase vs M7 snake_case (v1 problem 3):** documented as SHARED-WITH-M7 in §Known Blockers row 4, §Integration Point with M7 dedicated subsection, Appendix E row 5, integration-test gate `test_m7_sfdc_shape.py`. M11 correctly refuses to pre-normalize (preserves R12). Resolution options are M7's call.
- **Orion URL paths (v1 problem 4):** AC2.11 marks PENDING-VERIFICATION with startup-probe gate at Task 11.

### Weaknesses (HARSH)

- **AC8.5 label off-by-one:** "Optional (15)" lists only 14 items. Content correct, count label wrong. Minor — will catch in implementation review. Doesn't block GO.
- **AC18.2 "Shared SDK tests: 11 files" includes `.py` files in a TypeScript package.** AC18.2 enumerates `test_ssrf.ts`, `test_m11_error_contract.ts`, `test_m11_m7_version_match.py`, `test_m7_sfdc_shape.py`, `test_m7_emoney_allowlist.py`. vitest (AC18.3) runs TypeScript tests only. The Python tests run under pytest from the M7 side. The spec does not declare which package ships the Python tests or how CI invokes them. Mixing runtimes in a single test inventory without runner clarity is a new hygiene gap.
  - **Recommendation:** In AC18.2 split into `8 TypeScript shared-SDK tests (vitest)` + `3 cross-module Python tests (pytest, live in repo-root tests/integration/)`. The cross-module tests already exist there per §Cross-Module Invariants Tested — AC18.2 just needs to stop lumping them with shared-SDK TS tests.
- **Appendix C.3 eMoney scope literal `scope="plan_summary:read"`** is not cited. Scope strings are vendor-specific; eMoney may or may not accept that literal value (its API reference is PENDING-VERIFICATION). Low risk because the scope-mismatch test enforces fail-closed at startup (Appendix C.3 step 3 `process.exit(3)`), but the string should be marked illustrative/PENDING or pulled from config.
- **Appendix E row 30 "SSRF validation on `instance_url`":** well documented, but AC14.10 does not enumerate whether the egress allow-list validation happens BEFORE or AFTER DNS resolution. Order matters for TOCTOU correctness. Clarify the order (FQDN match → resolve → classify) at build time.
- **NI-1, NI-2, NI-3** (Traceability Table dangling refs) belong here methodologically. Accuracy docks 0.3 for those three.

---

## 3. Security — 9.1 / 10 (↑ 0.7 from v1 — strongest dimension)

### Fix Evidence

- **SSRF validation (v1 weakness 3):** AC14.10 + `src/ssrf.ts` + Appendix D.7 worked example. Covers https-only, FQDN match, DNS resolve, RFC1918/link-local/loopback/ULA reject. Applied at SFDC OAuth Step 5 (instance_url validation) and any vendor-returned URL.
- **Schwab ServiceAccount narrow RBAC (v1 weakness 2):** §RBAC Template Schwab variant with concrete Role (`resourceNames: ["m11-schwab-refresh-token"]`, `verbs: ["get","update"]` only) + RoleBinding. Default adapters read-only.
- **auth.ts LRU bound (v1 weakness 5):** AC4.14 `LRUCache({max: 1024})`, matches AC5.4/AC6.2. 1025-entry eviction test.
- **Schwab RT-rotation-failure alerting (v1 weakness 1):** AC4.13 + Appendix C.4 step 4 + §Events M10 Escalates table. Pino `fatal severity:"CRITICAL"` → M10 sidecar → PagerDuty within 5 min.
- **SIGTERM during RT rotation (v1 weakness 4 related):** AC17.3 adds "wait ≤ 10s for RT rotation to finish before drain." Closes the 30-min latent outage window.

### Strengths

- Zero-credentials multi-layer defense intact (AC4.1 AST scan + AC4.11 regex + AC14.1).
- Egress allow-list per-adapter still called out as M11 = only public-internet-touching module.
- eMoney scope-creep fail-closed (Appendix C.3 step 3 `process.exit(3)`) preserved.
- TLS 1.3 + 3 AEAD ciphers + 24h rotation all preserved.
- 22 frozen errorCode vocabulary (v1 had 21; `vendor_ssrf_blocked` added).

### Weaknesses (HARSH)

- **mTLS cert reload fail-open window (v1 weakness 4):** unchanged. AC9.2 still says "reload failure → 503" but doesn't address in-flight requests continuing on OLD cert until kubelet kills the pod (up to 2.5 min undetected cert-drift). Minor — kubelet probes at 30s × 5 failures is the standard envelope.
- **No SCA / npm audit policy:** v1 R8 partially addressed via §Observability Hand-Off (alerting on adapter logs) but the dependency-CVE intake policy is still silent. AC12.2 names an allow-list; AC11.7 names hadolint. Neither specifies Snyk/Dependabot with high-CVE blocking merges or a dependency-refresh SLA.
- **SSRF `validateVendorURL` DNS check is TOCTOU-vulnerable** in a pedantic sense — resolved IP at validation time may differ from IP at connect time. Mitigation (pin-to-IP on validated call) not specified. Low likelihood in practice; add as a Known Blocker.
- **Observability sidecar image not pinned** in v0.2.0 (comes from a Helm dependency). For supply-chain hygiene, pin digest in values-*.yaml.

Docks ~0.3 from the ideal 9.4 because of the unchanged mTLS reload window + still-missing dependency-CVE policy.

---

## 4. Testability — 8.3 / 10 (↑ 0.8 from v1)

### Fix Evidence

- **Property-based fuzz (v1 weakness 4):** AC18.6 + §fast-check Strategy Approach + Worked Example for `sfdc.fetch_client` + Per-Tool matrix for all 14 tools (including 2 writebacks). Target: ≥99% accept in-domain, ≥99% reject out-of-domain, 1000 runs. Mirrors M7 Hypothesis.
- **Error-contract mechanism table (v1 weakness 1):** AC16.4 adds a 12-row table forcing every error class deterministically (FakeClock, msw sequences, fixture-based, synthetic cert-file rewrites). No wall-clock sleeps.
- **Retry-After edge cases (v1 weakness 2):** AC5.7 covers 5 cases — integer, HTTP-date, negative→0, > 300s cap, malformed→default, zero→1 min. Test matrix in Task 7.
- **Concurrent-load test (v1 weakness 5):** Task 23 adds 50 simultaneous SFDC calls with burst=10 → first 10 pass, 40 × 429. AC5.9.
- **Chaos scenarios (v1 R3):** Task 23 now has 3 explicit scenarios (secrets 500 for 30s, DNS fail 10s, vendor TLS hang 15s).

### Strengths

- FakeClock + FakeSecretsClient DI discipline unchanged — still the right pattern.
- PII-free fixture enforcement (AC14.7) still enforced.
- Coverage 85% line / 75% branch still CI-enforced.

### Weaknesses (HARSH)

- **AC18.2 polyglot test inventory.** (See Accuracy §2 for detail.) Shared-SDK is TypeScript but AC18.2 lumps 3 `.py` cross-module tests with 8 TS shared-SDK tests. The `.py` tests have no vitest invocation path. Not a showstopper — they'll run under pytest at repo root — but AC18.2 as written implies they do. Needs a one-line split.
- **Mutation testing still absent.** v1 asked for boundary-value coverage beyond Zod-accepts-it; v0.2.0 answers with fast-check (good), but no Stryker-style mutation test. Fine for Phase 2 — parks this as a recommended improvement.
- **Concurrent-load test covers only SFDC.** AC5.9 specifies "50 simultaneous requests, burst=10." v1 asked for concurrency test per adapter. v0.2.0 Task 23 has SFDC test explicitly; other three adapters have rate-limit tests (AC5.8) but not explicit concurrency. Minor.
- **No integration test for Schwab RT rotation failure path** (AC4.13 CRITICAL alert). Task 15 tests `setSecret` throw + log event shape, but doesn't assert the M10-sidecar forwarding path. That's M10's seam though, not M11's — borderline acceptable.

---

## 5. Design Alignment — 8.5 / 10 (↑ 0.8 from v1)

### Fix Evidence

- **M12 Agent Runtime agnosticism** now stated: "M11 is runtime-agnostic — Managed Agents (Cloud Tier 3/4) and Strands (hybrid/on-prem Tier 1/2/5) both see adapters as plain MCP HTTP services behind M6. No code path differs by runtime." §Architecture Clarification.
- **Observability hand-off to M10** (v1 weakness): §Observability Hand-Off to M10 section declares Option A (sidecar) + Option B (OTEL) with explicit Phase 2 commitment to Option A.
- **Helm chart structure** (v1 weakness): §Deployment Notes states umbrella + 4 subcharts with shared templates. Task 21 enumerates the files. values.schema.json added for helm lint.
- **ARCH-09 Schwab trade submission descope** now logged (Appendix E row 24).
- **SEC EDGAR** positioned vs ARCH-09 Phase 1 with M8 ownership rationale (Appendix E row 22).

### Strengths

- ARCH-09 M11-REST row match (TypeScript + MCP SDK + @modelcontextprotocol/sdk ≥ 0.5 + Zod 3.23+) unchanged and correct.
- M7 v0.3.0 §Integration Point with M11 audit-bypass contract preserved verbatim.
- M6 VendorAdapter Protocol match unchanged (R3 shape).
- Steering Rules 10 / 20-26 all cleanly addressed.

### Weaknesses

- **M11-SFTP overlap still only one-liner.** Known Blockers row 13 ("Schwab tax-lot field granularity — RESOLVED — passthrough") hints but does not explicitly say M7 picks which Schwab feed wins on cost_basis conflict. See NI-3 — R6 recommended-fix content never made it into §Integration Point with M7.
- **No cross-reference to M13 FIX Bridge.** Steering Rule 11 separates M11 from M13; v0.2.0 doesn't even mention M13 exists. Not strictly required (Phase 4), but a one-liner keeps the alignment clean.

---

## 6. Gaps — 8.3 / 10 (↑ 3.3 from v1 — second-biggest delta)

v1 scored 5.0 because 10 items were missing. v0.2.0 addresses 9 of 10 cleanly.

### Fix Evidence

| v1 Gap | v0.2.0 Status |
|--------|---------------|
| 1. Concurrency model | AC3.9 `undici.Agent({connections: 10})` + AC5.9 concurrent load test |
| 2. Schwab RT-rotation failure alerting | AC4.13 CRITICAL → PagerDuty within 5 min |
| 3. Vendor schema drift | AC15.6 + playbook at Task 22 |
| 4. Observability hand-off | §Observability Hand-Off to M10 + Events Escalated table |
| 5. Pod-scheduling constraints | AC3.10 resources + Phase-2-singleton + Phase-3-HPA |
| 6. Graceful shutdown under in-flight RT rotation | AC17.3 wait ≤ 10s for completion before drain |
| 7. Phase 3 Orion Basic-auth toggle | AC4.12 + Appendix C.2 Phase 3 concrete |
| 8. SFTP sub-type overlap | ⚠ Partial — Known Blockers row 13 hints; NI-3 R6 orphan content |
| 9. Writeback idempotency | AC8.9 + Appendix D.8 worked example (ETag If-Match) |
| 10. Data-residency / geo-routing | ❌ Still silent. Egress allow-list covers `*.my.salesforce.com` (catches EU) but no explicit multi-region config section |

### Strengths

- The gap resolution table reads like an engineer's list, not a PM checklist. Every item has a named AC or section.
- Known Blockers table grew from 12 to 14 rows with 2 new v0.2.0 rows (SFDC PascalCase, Orion URL paths). SHARED-WITH-M7 items are explicitly M7's problem to resolve.

### Weaknesses

- Gap 10 (geo-routing) unresolved. Not a showstopper for the RIA lighthouse (single-US-firm Phase 2 targeting), but will bite at first EU tenant onboarding.
- Gap 8 (SFTP overlap one-liner) still partial — see NI-3.

---

## New Issues Introduced in v0.2.0 (regressions)

Beyond NI-1/NI-2/NI-3 documented above, these are net-new issues the rewrite created:

### NEW-1 (Medium): AC18.2 polyglot test inventory confusion

AC18.2 lumps 3 Python pytest files (`test_m11_m7_version_match.py`, `test_m7_sfdc_shape.py`, `test_m7_emoney_allowlist.py`) with 8 TypeScript vitest files under "Shared SDK tests: 11 files." AC18.3 says `vitest --run` with 85% line / 75% branch coverage — Python files can't run under vitest and can't contribute to TypeScript branch coverage. CI will either skip them or fail. Split AC18.2 into two sub-ACs. Low effort, high clarity.

### NEW-2 (Minor): AC8.5 label count off-by-one

"Optional (15)" lists 14 fields. Content is correct (matches M7 field-by-field), count label is wrong. Cosmetic; won't break anything.

### NEW-3 (Minor): `SIDECAR_ENABLED` and `OTEL_EXPORTER_OTLP_ENABLED` in `.env.example`

AC4.10 lists these as new in v0.2.0 `.env.example`. But these are orchestrator-level toggles (Helm values), not application runtime env vars the adapter reads. If the adapter never reads them, they shouldn't be in `.env.example`. If the adapter does read them (to adjust log-format or OTel SDK initialization), specify which code path consumes them. Currently ambiguous.

### NEW-4 (Minor): Appendix C.3 eMoney scope literal not cited

`scope="plan_summary:read"` appears as a literal in Appendix C.3 step 1. eMoney's actual scope grammar is PENDING-VERIFICATION (row 3). Either mark the literal as illustrative or pull from config.

### NEW-5 (Low): `SIDECAR_ENABLED=true` default may conflict with Option B OTEL

If both sidecar and OTEL are enabled, logs get double-forwarded. §Observability Hand-Off to M10 commits to Option A for Phase 2 — fine, but state that Option B is mutually exclusive with Option A at runtime to prevent misconfiguration.

---

## Cross-Reference Sanity Checks (Appendix F spot-check)

Spot-checked every Appendix F Traceability Table claim against real spec content:

| Fix # | Appendix F References | Resolve? |
|-------|----------------------|----------|
| 1 | AC5.2, AC15.2, Appendix E rows 1-4 | ✅ all present and content-correct |
| 2 | AC8.5, §Known Blockers **row 12**, Appendix E row 6, Task 13, Task 20 | ⚠ **NI-1: row 12 is wrong** — eMoney row is row 14 |
| 3 | §Known Blockers row 4, §Integration Point with M7 subsection, Appendix E row 5, Task 20 | ✅ |
| 4 | AC2.11, §Known Blockers row 6, Appendix E row 21, Task 11 | ✅ |
| 5 | §Explicitly OUT of Scope, Appendix E row 22 | ✅ |
| 6 | AC7.9, §Observability Hand-Off to M10, Appendix E row 32 | ✅ |
| 7 | AC3.9, AC3.10, §Deployment Notes, Deployment snippet, Appendix E rows 14-15 | ✅ |
| 8 | AC4.13, §Events M10 Escalates, Appendix C.4, Appendix E row 7 | ✅ |
| 9 | AC16.4 mechanism table, Task 18 | ✅ |
| 10 | AC18.6, §fast-check Strategy Approach, Tasks 6/10/13/16 | ✅ |
| 11 | §RBAC Template, AC9.7 exception, Task 15 | ✅ |
| 12 | AC14.10, Appendix C.1 step 5, Appendix D.7, Task 2, Task 5, Appendix E row 30 | ✅ |
| 13 | AC4.12, Appendix C.2 Phase 3 section, Appendix E row 8, Task 9 | ✅ |
| 14 | AC8.9, T-SF4/T-SF5, Appendix D.8, Appendix E row 18 | ✅ (T-SF4/T-SF5 are paragraphs in §Design, not tables — minor naming stretch) |
| 15 | AC4.14, AC3.7, AC12.2, Appendix E row 31, Task 2, Task 5 | ✅ |
| 16 | AC15.6, Appendix E row 25, Task 22 | ✅ |
| 17 | §Phase 2 Lighthouse Scope, §Explicitly OUT of Scope, AC2.4, §Design Schwab Tools "explicit NOT included", Appendix A footer row, Appendix E row 24 | ⚠ **NI-2: "Schwab Tools — explicit NOT included" is paraphrased** — actual header is "Schwab Tools (Read-Only — Phase 3 descope per Appendix E row 24)" |

**15/17 clean, 2/17 with dangling references (NI-1, NI-2). Plus NI-3 for Recommended Fix R6** which references §Integration Point with M7 content that doesn't exist.

This is better than M7 v0.2.0 (which had 5 NI-style dangling refs), but hygiene should be tightened before Appendix F goes into the build-time traceability audit.

---

## Verdict

**8.52 / 10 — GO. Proceed to Step 5 Build.**

### What landed

All 17 required fixes + 9 of 10 recommended fixes. The two severe accuracy problems from v1 are gone: rate-limit citations are either real vendor-doc URLs or explicit PENDING-VERIFICATION with named gates, and the eMoney allow-list is set-equal to M7's `EMoneyPlanSummary` (verified field-by-field against `src/m7_schema_translators/emoney/models.py`). Security gained SSRF validation, narrow Schwab RBAC, LRU-bounded token cache, and CRITICAL alerting for RT-rotation failures — all concrete, all testable. Observability gap closed with a two-option Phase 2 commitment (Option A sidecar default; Option B OTEL opt-in). fast-check property tests cover all 14 tools with the same discipline M7 v0.3.0 uses for Hypothesis.

### What's left

Three dangling traceability references (NI-1, NI-2, NI-3) — the M7-v0.2.0-style hygiene regression that bit the M7 second pass. Appendix F points at section headers that either have the wrong row number (Fix #2 → row 12 should be row 14), a paraphrased header name (Fix #17 → "explicit NOT included" doesn't exist as a header), or content that never got written (R6 → cost_basis reconciliation one-liner never made it into §Integration Point with M7). None blocks the build — the content they claim exists either already exists elsewhere or is a 1-2 sentence patch. They're markdown hygiene, not accuracy failures.

Plus five low-severity new issues:
- NEW-1: AC18.2 polyglot test inventory mixes .ts + .py without declaring pytest runner (medium)
- NEW-2: AC8.5 "Optional (15)" label vs 14 listed items (minor)
- NEW-3: SIDECAR_ENABLED / OTEL_EXPORTER in .env.example with unclear consumer (minor)
- NEW-4: eMoney scope literal "plan_summary:read" uncited (minor)
- NEW-5: Option A / Option B mutual-exclusion not stated (low)

### Recommended patches before Step 5 Build (post-GO, inline with implementation)

1. Fix NI-1: change "§Known Blockers row 12" → "§Known Blockers row 14" in Appendix F row for Fix #2.
2. Fix NI-2: change Appendix F row for Fix #17 header reference to the actual heading text.
3. Fix NI-3: add the R6 cost_basis-reconciliation one-liner to §Integration Point with M7 "What M11 Does NOT Do" bullet list.
4. Fix NEW-1: split AC18.2 into "8 TypeScript vitest shared-SDK tests" + "3 Python pytest cross-module tests, repo-root `tests/integration/`, invoked via separate CI step."
5. Fix NEW-2: change "Optional (15)" to "Optional (14)" in AC8.5.

All five are 1-line edits. No re-review needed for these. The spec is GO-quality.

### Score delta versus v1 (visual)

```
Completeness     ████████░░ 8.2 → ████████▓░ 8.7 (+0.5)
Accuracy         █████▓░░░░ 5.8 → ████████░░ 8.0 (+2.2) ★
Security         ████████▓░ 8.4 → █████████░ 9.1 (+0.7)
Testability      ███████▓░░ 7.5 → ████████▓░ 8.3 (+0.8)
Design Align     ███████▓░░ 7.7 → ████████▓░ 8.5 (+0.8)
Gaps             █████░░░░░ 5.0 → ████████▓░ 8.3 (+3.3) ★
─────────────────────────────────────────────────────────
WEIGHTED         7.27/10 ⚠ → 8.52/10 ✅ (+1.25)
```

The rewrite did what M3 v1→v2 did and what M7 v1→v2 did: full rewrite, not patches, with ~1.25-point weighted swing. Same discipline.

Ship it. Build M11-REST.

---

*m11-rest-adapters-REVIEW-v2.md — Project 007 FSI Interoperability Platform*
*LLMJ v2 Review — adapter-agent acting as independent second-pass judge*
*2026-04-25*
