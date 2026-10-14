# M11-REST Adapters — LLMJ Review (First Pass)

**Spec Version:** 0.1.0 (1,628 lines)
**Reviewer:** adapter-agent acting as independent LLMJ
**Date:** 2026-04-25
**Playbook Step:** 2 of 7

---

## Weighted Score: 7.27 / 10 — **CONDITIONAL GO** (fix and re-review)

| # | Dimension | Weight | Score | Weighted |
|---|-----------|--------|-------|----------|
| 1 | Completeness | 25% | 8.2 | 2.05 |
| 2 | Accuracy | 20% | 5.8 | 1.16 |
| 3 | Security | 20% | 8.4 | 1.68 |
| 4 | Testability | 15% | 7.5 | 1.125 |
| 5 | Design Alignment | 10% | 7.7 | 0.77 |
| 6 | Gaps | 10% | 5.0 | 0.50 |
| — | **TOTAL** | **100%** | — | **7.285 ≈ 7.27** |

Scoring bands: 8.0+ = GO, 7.5-7.9 = MARGINAL GO, 6.5-7.4 = CONDITIONAL GO, <6.5 = NO GO.

The spec lands in CONDITIONAL GO territory. The architecture, security, and test discipline are strong. But **two facts are wrong against the source of truth**: (a) RES-08 does not actually publish the rate-limit numbers M11 claims it does, and (b) the eMoney allow-list and SFDC raw-payload shape do not line up with what M7's Pydantic `extra="forbid"` models actually accept — the very contract M11 is supposed to preserve. Combined with a thin set of production-realism gaps (concurrency, token-rotation failure modes, observability hand-off), this needs a v0.2.0 rewrite.

This is the normal discipline bar. M7 hit 7.36/10 on its first pass. M3 hit 4.8/10. Being at 7.27 on pass 1 means the structure is right and the content needs tightening.

---

## 1. Completeness — 8.2/10

### Evidence

- 18 numbered requirements (R1-R18). 133 ACs across them (Appendix B AC Count table, lines 1184-1189). All 8 mandatory steering rules (10, 20-26) mapped to specific requirements in the §Steering Rules table (lines 64-75).
- 4 adapters × 14 tools enumerated in §Phase 2 Lighthouse Scope (lines 29-38) AND cross-referenced in Appendix A Tool × Adapter Matrix (lines 1148-1166).
- OAuth flow specified per vendor: SFDC JWT Bearer (Appendix C.1), Orion client-credentials (C.2), eMoney client-credentials + scope-narrowing (C.3), Schwab refresh-token rotation (C.4). Each has a step-by-step HTTP trace with request/response shapes and log events.
- 6 worked scenarios in Appendix D: happy path, Zod reject, eMoney raw-plan reject, circuit-open, vendor 429, retry exhaustion. Every error path is walked end-to-end with exact response bodies.
- Error vocabulary is closed: 21 errorCode values frozen in AC16.3 with matching HTTP status + retryable table in Error Code Map (lines 1039-1060).
- Test inventory per adapter declared in AC18.1 (8 test files) + shared-SDK tests in AC18.2 (10 test files) + cross-module integration in Tasks 18-20.
- DECISION-LOG seed has 20 entries in Appendix E covering rate-limit citations, SF field-name PENDING, eMoney DENY list, Schwab RT rotation, and all mTLS choices.
- Per-vendor tool input field tables (lines 670-815): every tool has required/optional flags, Zod constraints, cross-field refinements (Orion 90-day max range), and vendor-endpoint URL.

### Strengths

- Audit-bypass contract from M7 side is honored (R12 AC12.6, Integration Point with M7). M11 explicitly does NOT import M7 — matches M7 v0.3.0 spec Integration Point with M11 verbatim.
- Error-to-M6 mapping table is explicit (lines 552-556): vendor_circuit_open / adapter_timeout / mtls_degraded → unavailable, everything else → error. This is the kind of seam detail that caused M6's own first review grief.
- VENDOR_API_VERSION cross-module check (AC10.1) is correct — I verified all four M7 constants: salesforce_fsc/client.py = v59.0, orion/holding.py = v2.0, emoney/plan_summary.py = v2, schwab/holding.py = v1. M11's declared values match exactly.
- Phase 2 OUT-of-scope list is explicit: no Fidelity/Pershing/Wealthbox/Redtail/Envestnet/ComplySci/EDGAR/AV/News; no BLPAPI/gRPC/SFTP/MCP-NATIVE; no webhooks; no Apex custom endpoints. Nothing left to a reviewer's imagination.

### Weaknesses (HARSH)

- **No SEC EDGAR adapter** and no acknowledgement of Phase 1 scope. ARCH-09 (line 88) lists SEC EDGAR as Phase 1 with a 10 req/s rate limit. M11-REST v0.1.0 punts this to OUT-of-scope under "Phase 3/4 per ARCH-09" — but ARCH-09 puts EDGAR in Phase 1, not 3/4. Either the spec is wrong about scope OR EDGAR belongs in Phase 1 and needs to be built earlier.
- **Alpha Vantage + News API missed.** ARCH-09 puts both in Phase 2 ("Bloomberg fallback for market data" + "news scan for research pipeline"). M11-REST v0.1.0 excludes them with a one-line dismissal. If M8 Research Pipeline (also Phase 2) needs news + market data, excluding them here means M8 has no vendor data path.
- **R11 Dockerfile AC11.5 image-size cap of 150 MiB is asserted but not justified.** @modelcontextprotocol/sdk pulls a non-trivial dependency closure; @aws-sdk/client-secrets-manager alone is ~25 MiB. Show the math.
- **No cold-start latency budget.** R17 sets a 120s startupProbe window but that's for OAuth bootstrap + version check. There's no target for steady-state request latency (TTFB) or p95 tail. M6 needs this to wire circuit-breaker reset timing coherently.
- **No documented behavior when X-Firm-ID header mismatches token's firm claim.** M6 spec (line 617) requires request.firm_id match claims.firm_id. Adapter only enforces presence. Header-vs-token match is M6's job, but M11 accepting requests with a valid cert means it trusts M6 to have checked — say so.
- **Phase 3 hooks absent.** Spec says "Orion Basic-auth fallback stubbed for Phase 3" (Task 9) but doesn't show the stub shape or how Phase 3 enablement works (Helm values flip? different secret path? rate-limit config change?). If Phase 3 is supposed to enable without re-architecture, declare the shape now.

### What would make it a 10

Add SEC EDGAR to Phase 2 scope (Phase 1 per ARCH-09, shares TypeScript SDK). Confirm Alpha Vantage + News API placement with M8 spec owner. Measure and cite the Dockerfile image-size closure. Add latency targets (p50/p95) not just startup budget. Make Phase 3 Basic-auth enablement a concrete toggle now.

---

## 2. Accuracy — 5.8/10

This is where the spec takes its first real hits. Four distinct accuracy problems, two severe.

### Evidence

Cross-verified claims against: `src/m6_mcp_gateway/adapters.py` (M6's VendorAdapter Protocol), `src/m7_schema_translators/**/{client,household,goal,plan_summary,holding,taxlot,transaction}.py` and `models.py` (M7's VENDOR_API_VERSION constants and Pydantic models), `docs/research/RES-08-financial-infrastructure-deep-research.md` (vendor facts), `docs/architecture/ARCH-09-complete-module-map.md` (M11 row and sub-types), `.kiro/specs/m7-schema-translators.md` (audit-bypass contract).

### Strengths

- **M7 VENDOR_API_VERSION match: correct.** Verified all four:
  - SFDC `v59.0` — matches M7 client.py / household.py / goal.py line 52/42/41.
  - Orion `v2.0` — matches M7 holding.py / household.py / taxlot.py / transaction.py line 40/42/32/40.
  - eMoney `v2` — matches M7 plan_summary.py line 49.
  - Schwab `v1` — matches M7 holding.py / household.py / taxlot.py line 40/42/30. Schwab CHANGELOG confirms the v0.2.0 fix.
- **M6 VendorAdapter Protocol: M11's assumed shape matches actual.** M11 spec lines 519-527 declare a @runtime_checkable Protocol with `name: str` and `def call(self, *, tool_name: str, payload: Any) -> Any`. Byte-identical to M6 adapters.py lines 52-69.
- **M6 VendorAdapterError kinds: frozen to 2 values.** M11's mapping table (lines 552-556) says M6 has only unavailable and error. Verified against M6 adapters.py line 21: VALID_VENDOR_KINDS = frozenset({"unavailable", "error"}). Correct.
- **Schwab URL path /trader/v1/... :** plausible. T-SC2 hedges on the tax-lot endpoint ("if Schwab exposes directly" OR "derived from positions"), which is honest given Schwab docs ambiguity.

### Weaknesses (HARSH)

#### Problem 1 (SEVERE): Rate-limit citations are fabricated.

AC5.2 (lines 180-184) cites RES-08 §2.1 for Schwab 120 req/min, §3.1 for Orion 60 req/min, §5 for eMoney 30 req/s, §6.1 for SFDC 100K/24h. I cross-checked:

- RES-08 §2.1 Schwab (lines 128-177) — vendor approval, cost basis, master account grouping. ZERO rate-limit number.
- RES-08 §3.1 Orion (lines 284-338) — mentions "paginated, rate-limited" and pagination best practices. ZERO specific number.
- RES-08 §5 — this is PAYMENT AND SETTLEMENT INFRASTRUCTURE (SWIFT, DTCC, Fedwire). No eMoney content at §5 at all. eMoney appears only in summary tables without rate data. The §5 citation is wrong section entirely.
- RES-08 §6.1 SFDC (lines 602-662) — protocols and Household mismatch. ZERO rate-limit number. The 100K/24h figure is a real Salesforce governor-limit fact but not in RES-08.

Appendix E DECISION-LOG rows 1-4 repeat the same false citations. Four citations in a row all claim numbers RES-08 does not contain.

**Why this matters:** AC15.2 says "Every vendor rate-limit value has a DECISION-LOG entry citing the RES-08 section or vendor-documentation URL." Implementation will follow the citations, a reviewer will check them, the chain breaks. Cite the real vendor documentation URLs (Salesforce governor-limits page, Schwab developer-portal rate-limit page, Orion developer-portal quota page, eMoney API reference) or mark as PENDING-VERIFICATION.

#### Problem 2 (SEVERE): eMoney allow-list does not match M7's Pydantic model.

AC8.5 declares the EMoneyPlanSummaryOutput strict allow-list: planId, clientId, householdId, planType, createdDate, lastModified, totalAssets, totalLiabilities, netWorth, monthlyIncome, monthlyExpenses, retirementAge, retirementAssets, retirementIncomeNeed, successProbability, goals[].

But `src/m7_schema_translators/emoney/models.py` EMoneyPlanSummary (lines 86-147) is `extra="forbid"` and expects: planId, scenarioId, clientId, householdId, planName, planType, probabilityOfSuccess, asOfDate, totalAssets, totalLiabilities, retirementGoal (object), monteCarlo (object), annualSavingsRate, annualSpending, socialSecurityEstimate, pensionIncome, goalIds (list of IDs, not objects), assumptions, recommendations, createdAt, updatedAt.

Overlap: only ~5 fields (planId, clientId, householdId, planType, totalAssets, totalLiabilities). Every other M11-allow-listed field (netWorth, monthlyIncome, monthlyExpenses, retirementAge, retirementAssets, retirementIncomeNeed, successProbability, createdDate, lastModified, goals) is NOT in M7's model and would be rejected by `extra="forbid"`. Conversely, M11 does not permit scenarioId, planName, probabilityOfSuccess, asOfDate, retirementGoal, monteCarlo, annualSavingsRate, annualSpending, socialSecurityEstimate, pensionIncome, goalIds, assumptions, recommendations, createdAt, updatedAt — all of which M7 needs.

Implementing AC8.5 as written means every eMoney call fails at M7 Stage 6. This breaks the RIA lighthouse meeting-prep journey — the workflow Phase 2 is designed to validate. Field lists must be reconciled before implementation.

#### Problem 3 (MEDIUM): Raw SFDC payload vs M7 model field-case mismatch.

M11 returns "VERBATIM vendor JSON" (§Integration Point with M7 lines 505-515). Real SFDC uses PascalCase (Id, FirstName, FinServ__HouseholdId__c). But M7's SalesforceFSCAccountContact model (`src/m7_schema_translators/salesforce_fsc/models.py` lines 19-166) uses snake_case (firm_id, household_id, first_name, email, kyc_status) with no Pydantic aliases (no populate_by_name, no Field(alias=...)) and `extra="forbid"`.

`to_canonical_client` (salesforce_fsc/client.py line 134) calls `SalesforceFSCAccountContact(**vendor_payload)`. Raw SFDC `{"Id": "001...", "FinServ__HouseholdId__c": "..."}` triggers `extra_forbidden` on every key.

Either (a) M7 is expected to rewrite with aliases, (b) M6 Stage 6 transforms before calling M7, or (c) M11 pre-normalizes (contradicts R12). M11 spec says (c) is forbidden and (a/b) is someone else's problem — correct in scope, but the integration is fragile enough to belong in §Known Blockers as SHARED-with-M7. Right now the spec treats it as solved. It isn't.

#### Problem 4 (MINOR): Orion URL path /api/v2.0/portfolio/accounts/... is un-cited.

RES-08 §3.1 describes Orion's domain structure but publishes no URL paths. Archived 007 code used `api.orionadvisor.com/api/v1`, not v2.0. Live Orion developer portal uses mixed path prefixes. Mark PENDING-VERIFICATION like SFDC field names.

### What would make it a 10

Fix rate-limit citations. Reconcile eMoney field list with M7 (rewrite AC8.5 to match M7 field set or mark PENDING until sandbox-response shape captured). Add SFDC PascalCase vs M7 snake_case contract mismatch to §Known Blockers. Verify Orion URL paths or mark PENDING.

---

## 3. Security — 8.4/10

Strongest dimension. The spec treats security as load-bearing, not decorative.

### Evidence

- **Zero credentials in git (Rule 20):** AC4.1 AST scan, AC4.9 Dockerfile lint, AC4.10 .env.example values are REPLACE_ME only, AC4.11 regex scan for AWS-access-key / JWT / PEM / slack / stripe credential shapes. Multi-layer defense.
- **mTLS (Rule 21):** TLS 1.3 only with three AEAD ciphers (AC9.3). 24h rotation with renewBefore 8h (AC9.2). Reload via fs.watchFile; failure yields GET / = 503. CN check against MTLS_TRUSTED_SUBJECT_CN.
- **Egress allow-list (Rule 22):** Per-adapter FQDN allow-list with Cilium FQDNSelector or CIDR fallback. M11 called out as "the ONE module with public-internet egress" — acknowledged risk, explicit perimeter.
- **Per-tenant isolation (Rule 23):** Namespace {firm}-m11-{vendor}. ServiceAccount per-adapter. NetworkPolicy per-adapter. Per-firm rate-limiter and circuit-breaker keys.
- **PII in logs:** pino.redact with wildcard paths (**.password, **.secret, **.token) + specific paths (req.body.arguments.ssn, req.body.arguments.taxId, etc.). AC7.7 test greps captured log stream for synthetic PII and asserts no match.
- **Forbidden Node APIs (AC14.4):** eval, Function(), vm.*, child_process.*, dgram.*, cluster.*, worker_threads.*, process.binding, process.dlopen — AST scanned. JSON.parse banned (AC14.8); fastify handles parsing with size limit.
- **Distroless nonroot runtime (AC11.1):** pinned SHA256 digests, USER nonroot, no shell.
- **eMoney scope-creep enforcement (Appendix C.3 step 4):** if vendor grants wider scope than requested, process.exit(3) at startup. Fail-closed on security regression — exactly the discipline Rule 8 demands.
- **eMoney raw-plan rejection (R8 AC8.5-8.6):** Zod .strict() output schema with DENY-list of raw-plan fields (scenariosDetail, rawPlanBody, advisorNotes, etc.). HTTP 502 with emoney_raw_plan_forbidden. Log captures field NAMES only (Appendix D.3 line 1467).

### Weaknesses (HARSH)

- **Schwab refresh-token rotation is the weakest credential path.** Adapter writes a NEW refresh token back to Secrets on every access-token refresh (~every 29 min). At 100 firms × 3 replicas that's ~10 writes/min sustained. Vault default lease paths have rate limits. AC4.7 says "write failure → GET / reports oauth:'degraded' but does not crash" — the adapter keeps running with a still-valid RT, but Schwab rotated server-side. NEXT refresh (~30 min later) fails. Latent 30-min outage. No CRITICAL alert path.
- **Per-adapter ServiceAccount RBAC for Schwab needs explicit narrow scope.** AC9.7 says "read Secrets m11-{vendor}-mtls-certs only. No write access anywhere." But Schwab REQUIRES write access to its RT secret. Spec acknowledges as "narrow exception" (Appendix C.4) but doesn't include the K8s RBAC YAML — a Role granting `["get","update"]` on `m11-schwab-refresh-token` ONLY. Missing manifest = easy to over-grant at build time.
- **No SSRF mitigation for vendor-returned URLs.** tokenUrl and loginUrl come from Secrets (trusted) but instance_url comes from SFDC response (Appendix C.1 step 4). A compromised SFDC response returning `instance_url: http://169.254.169.254/latest/meta-data/` (EC2 metadata) or `http://localhost:5000/internal` would be used blindly as base URL. Validate against egress allow-list before next call.
- **mTLS cert reload failure is fail-open in practice.** AC9.2: reload failure → GET / = 503. Requests in flight when reload fails proceed with OLD cert until kubelet kills pod on next probe cycle (30s liveness × 5 failures = up to 2.5 min undetected cert-drift).
- **OAuth token cache has no LRU eviction.** AC4.6: in-memory only, pod-restart refetch. AC5.4 bounds rate-limiter at 1024 LRU; AC6.2 same for circuit breaker. But auth.ts `Map<firm_id, CachedToken>` is unbounded. 10 000 firms → 10 000-entry map forever. Combined with --max-old-space-size=512, this is an OOM vector.
- **No npm audit / SCA policy.** AC12.2 allow-list but no CVE-response policy. undici has had parser CVEs; fastify has shipped RCE patches. Require Snyk/Dependabot blocking merges on high/critical + dependency-refresh SLA.

### What would make it a 10

Add Schwab-specific K8s Role + RoleBinding YAML. Add SSRF validation (reuse egress allow-list). Bound auth.ts firm-token map with 1024-entry LRU. State dependency-CVE policy with CI enforcement. Add audit side-channel for rt_rotation_write_failed that escalates within 5 minutes.

---

## 4. Testability — 7.5/10

### Evidence

- Vitest pinned (AC18.3). Coverage thresholds 85% line, 75% branch — CI fails below.
- msw (Mock Service Worker) pinned for vendor HTTP mocking (AC18.4). Fixtures under tests/fixtures/vendor_{name}/*.json.
- Every AC has a SPEC-TRACEABILITY.md row per adapter (AC18.5) — mirrors M7 discipline.
- Cross-module test: test_m11_m7_version_match.py reads M7's Python VENDOR_API_VERSION via importlib and the adapter's package to assert equality (Task 19). No mocks.
- FakeClock and FakeSecretsClient specified in shared SDK (src/clock.ts, src/secrets.ts). Dependency injection enables deterministic circuit-breaker and rate-limit tests without wall-clock sleep.
- Task 23 "dress rehearsal" runs all 4 adapters in docker-compose against a mock M6 and asserts the RIA meeting-prep journey end-to-end — circuit exercise, rate-limit exercise, mTLS-reload exercise, eMoney raw-plan rejection. Concrete criteria, not vibes.

### Strengths

- Cross-language test (Python targeting both codebases) resolves the polyglot integration-test problem.
- PII-free fixture enforcement (AC14.7) — .example/.invalid/.test domains, 555- SSN prefix. Prevents tests leaking PII.
- Rate-limit test (AC5.8) is deterministic via FakeClock.advance() — no sleeps, no flakiness.
- Circuit breaker states independently testable via DI (AC6.9).

### Weaknesses (HARSH)

- **test_m11_error_contract.ts (Task 18) is under-specified.** AC16.4 says "forces each error class (429, 5xx-exhausted, OAuth expiry, Zod-fail, circuit-open, raw-plan-rejection)." How does the test force OAuth expiry deterministically? Probably FakeClock.advance(expiresAt+1), but spec doesn't say. How does it force circuit-open? 5 consecutive 500s via msw? Any real-clock step makes the test non-deterministic. Specify the mechanism per error class.
- **No test for vendor 429 with malformed Retry-After header.** AC5.7 says "parsed as integer seconds OR HTTP-date; both handled." What if header is "garbage"? -1? HTTP-date 30 days out (cap at `max(Retry-After, 30)` — or 30-day pause)? Spec doesn't enumerate, no test specified.
- **eMoney raw-plan test depends on a fixture containing scenariosDetail.** AC14.7 forbids PII in fixtures. Real eMoney raw-plan body IS MNPI-class data. Spec says sandbox "may return them" — fine, but the test fixture must be handcrafted without real PII. One-line note needed.
- **No mutation test / no negative-Zod-fuzz test.** Zod tests (Task 6) assert malformed input rejects. No coverage for the harder case: input Zod accepts but should be rejected (boundary values, Unicode edge cases, very long strings within .max(32000)). M7 has Hypothesis-style property tests (M7 Appendix B.6). M11 should too.
- **Cross-adapter load test missing.** Task 23 exercises happy path + a handful of error classes at single-request level. No concurrent-request test — what happens when 50 requests for firm_id=acme land simultaneously and bucket has 10 tokens? Task 23 says "200 concurrent SFDC calls with burst=10" but that's only 1 of 4 adapters.
- **No chaos test.** Secrets backend down mid-request? DNS fail for vendor FQDN? Spec handles the error paths in code (AC6.4 retries on DNS failure) but no integration test exercises them.

### What would make it a 10

Specify how every error class in error-contract test is forced (clock advance, msw response sequence, fake-secret failure). Add Retry-After edge-case tests. Add Hypothesis/fast-check property-based Zod fuzz mirroring M7 §Hypothesis Strategy Approach. Add concurrent-request saturation tests for each adapter. Add at least one chaos scenario (secrets backend 500 for 30s) in Task 23.

---

## 5. Design Alignment — 7.7/10

### Evidence

- **ARCH-09 M11-REST row (line 73):** TypeScript + MCP SDK. M11-REST v0.1.0 pins Node 20+, TypeScript 5.4+, @modelcontextprotocol/sdk ≥ 0.5, Zod 3.23+. Match.
- **ARCH-07 M11-REST row:** TypeScript + MCP SDK. Match.
- **Steering Rule 10 (M11 polyglot, each adapter = own container):** R3 AC3.4-3.6 pin per-adapter Dockerfile + Deployment + NetworkPolicy + ServiceAccount. No shared Pod. Correct.
- **Steering Rules 24-25 (docker-compose for dev, Helm for prod, 3 topologies):** R11 AC11.6 + §Deployment Notes. Topology values explicitly listed (cloud/hybrid/on-prem).
- **ARCH-09 dependency matrix `M11 → M7: *`:** M11 spec reverses — adapters return raw, M6 calls M7. Matches M7 v0.3.0 §Integration Point with M11 lighthouse-1 verbatim.
- **M3 SourceSystem enum:** M11 uses salesforce_fsc / orion / emoney / schwab — matches M7 exactly.

### Strengths

- Explicit statement of what M11 does NOT do (§What M11 Does NOT Do, lines 515-521) is a good alignment guardrail: no canonicalization, no ReconciliationNote, no Pydantic, no M4 MNPI filtering.
- R1 AC1.6 merges server-info + health-check into GET / — follows the upstream MCP SDK pattern and K8s probes rather than inventing a parallel /health endpoint.

### Weaknesses

- **M12 Agent Runtime is not mentioned.** Steering Rule 1 puts Claude Managed Agents as the default Cloud runtime. M11 is runtime-agnostic (correct), but the spec should say so explicitly.
- **Observability hand-off to M10 is not designed.** Steering Rule 6 mandates 3-tier audit. R16 AC16.2 says M6 captures M11 error body into AuditEntry — M6 obligation. M11's pino logs are local only. If M10 wants adapter-level metrics (p95 latency per tool, circuit-open counts per firm), how? Prometheus scrape? OTel exporter? ARCH-07 lists Prometheus + Grafana + OTel + Jaeger — M11 adopts pino and mentions nothing else. Declare at least one.
- **Helm chart (Task 21) is a skeleton.** Templates exist but chart structure not nailed (umbrella vs per-adapter subchart — M11 says umbrella with 4 subcharts; ARCH-09 says "Helm umbrella chart" at module level; not in conflict but cross-adapter values-rendering unspecified).
- **ARCH-09 Schwab row says "Positions, balances, trade submission" (Phase 2).** M11 spec scopes Schwab to read-only. Deliberate sane descope but not logged as a deviation from ARCH-09. DECISION-LOG should log it.
- **SEC EDGAR (Phase 1 per ARCH-09) is missing.** Already raised.

### What would make it a 10

State "M11 is runtime-agnostic — Managed Agents or Strands sees adapters as MCP HTTP services." Specify observability-export seam. Resolve EDGAR. Log Schwab descope.

---

## 6. Gaps — 5.0/10

### Evidence

§Appendix F "Review Fix Traceability" placeholder to be populated after this review. §Known Blockers table (lines 48-62) has 12 open questions marked PENDING/SHARED/RESOLVED.

### Strengths

Known blockers are genuinely known, not whitewashed: Schwab vendor-approval, eMoney API access tier, SFDC field PENDING-VERIFICATION, Schwab sandbox-vs-prod token divergence, CIDR churn, mTLS issuer variance, 429 header parsing, SFDC daily budget, Schwab tax-lot field granularity, eMoney raw-plan boundary.

### Weaknesses (HARSH)

Ten items absent that should be present:

1. **Concurrency model.** Adapter is single-process (AC14.4). Max concurrent in-flight vendor calls per pod? If 200 requests for 200 firm_ids land simultaneously and OAuth refresh for 200 is due in the same minute — thundering herd. undici default `connections: 10` per Agent; spec doesn't pin it.

2. **Token-rotation failure modes, Schwab.** Covered in Security. Latent 30-min outage if RT write fails + Schwab rotates server-side. No alerting path.

3. **Vendor-response schema drift.** Change process absent. Appendix E row 6 says new eMoney fields default to BLOCKED — good — but the response SLA to allow-list legitimately new fields is undefined.

4. **Observability hand-off to M10.** No correlated OTel span across M6 → M11 → vendor. X-Trace-Id propagated (good) but no spans, no dashboards. Operator visibility during RIA lighthouse = guesswork.

5. **Pod-scheduling constraints.** Single replica? Anti-affinity for HA? AC3.5 calls HPA "optional" but no CPU/memory requests. AC11.8 sets --max-old-space-size=512 but no K8s resource requests — pod starved to 128 MiB pressure-OOMs.

6. **Graceful-shutdown under in-flight OAuth refresh.** AC17.3: SIGTERM → stop-accepting → drain ≤30s. What if Schwab RT rotation is in-flight when SIGTERM fires? Pod might exit before writing new RT. Require: complete in-flight RT rotations first, THEN drain.

7. **Phase 3 hooks.** ORION_AUTH_MODE=basic — re-bootstrap? Hot-switch? Restart required? Different secret path? Undocumented.

8. **SFTP sub-type overlap.** ARCH-09 puts Schwab SFTP in Phase 2 (separate Python container). M11 REST-Schwab and SFTP-Schwab both deliver tax-lot data. Conflict resolution undocumented. Probably M7's job but a one-line cross-reference needed.

9. **No vendor-side retry / idempotency for writebacks.** sfdc.update_client and sfdc.create_interaction_summary are writebacks. Retry on 5xx can cause double-writes + client retry. Use SFDC `If-Match` + ETag? Client-generated idempotency key? Spec silent.

10. **No data-residency / geo-routing.** EU-based firm with SFDC org at `my.salesforce.com.eu` — does the adapter route there? M5 config presumably handles but M11 spec doesn't acknowledge multi-region endpoints.

### What would make it a 10

Address all 10 in a v0.2.0 §Gaps Resolution table. Extend §Known Blockers.

---

## Required Fixes (numbered)

These MUST be fixed before re-review. Expectation: full spec rewrite like M3/M7 v1→v2, not surgical patches.

1. **Fix fabricated RES-08 citations for rate limits (AC5.2, AC15.2, Appendix E rows 1-4).** Cite real vendor documentation URL (Salesforce governor-limits page, Schwab developer-portal rate-limit page, Orion developer-portal quota page, eMoney API reference) OR mark as PENDING-VERIFICATION and remove the RES-08 citation. Current citations (§2.1, §3.1, §5, §6.1) do not contain the numbers they claim.

2. **Reconcile eMoney allow-list (AC8.5) with M7 EMoneyPlanSummary Pydantic model.** Current 16-field allow-list overlaps M7's field set on only ~5 fields. As-implemented, every eMoney call fails at M7 Stage 6. Options: (a) rewrite AC8.5 to match M7's field set; (b) engage M7 spec owner to align both sides; (c) mark AC8.5 as PENDING and defer enforcement until sandbox-response shape is captured. Do not implement as written.

3. **Add SFDC PascalCase vs M7 snake_case mismatch to §Known Blockers.** M11 forwards raw SFDC JSON, M7's SalesforceFSCAccountContact expects snake_case with extra="forbid" and no aliases. Not M11's fix, but M11 spec claims the integration works; it doesn't. Add as SHARED-with-M7.

4. **Declare Orion URL paths as PENDING-VERIFICATION.** /api/v2.0/portfolio/accounts/{id}/positions is not RES-08-sourced and differs from the archived 007 code (/api/v1). Mark like SFDC field names.

5. **Add SEC EDGAR adapter to Phase 2 scope OR provide explicit ARCH-09 cross-reference** explaining the Phase 1 → deferred decision. ARCH-09 puts EDGAR in Phase 1.

6. **Declare the observability hand-off to M10.** Either add OpenTelemetry SDK integration (stdout transporter or OTLP exporter) OR state that M11 emits only pino logs and M6 reads them via sidecar + Langfuse. Current spec has zero /metrics endpoint, zero OTel, zero Prometheus mention.

7. **Specify concurrency limits and K8s resource requests/limits.** Pin undici Agent.connections per adapter. Declare resources.requests.{cpu,memory} and resources.limits.{cpu,memory}. Declare single-replica or multi-replica stance with anti-affinity.

8. **Add a concrete Schwab RT-rotation-failure alerting path.** AC4.7 says "degraded, not crash." Add: escalate to operator within 5 minutes via M10 audit side-channel + Prometheus alert rule.

9. **Specify how test_m11_error_contract.ts forces each error class deterministically.** FakeClock.advance for OAuth expiry, msw response sequence for 5xx retry exhaustion, fake-secrets failure for OAuth-write path.

10. **Add Hypothesis-style (fast-check) property-based Zod fuzz tests for every tool input schema.** Follow M7 §Hypothesis Strategy Approach. Reject rate ≥ 99% for out-of-domain; accept rate ≥ 99% for generated in-domain.

11. **Narrow Schwab ServiceAccount's Secret-write RBAC.** Add concrete Role + RoleBinding YAML granting ["get","update"] on `secretName == "m11-schwab-refresh-token"` ONLY. Do not grant secrets/*. Include in §mTLS Configuration Template.

12. **Add SSRF validation for vendor-returned URLs.** instance_url (SFDC), any tokenUrl or redirect URL from vendor response — validate against the adapter's egress allow-list before issuing next call.

13. **Resolve the Phase 3 Orion Basic-auth toggle concretely.** Is ORION_AUTH_MODE a values.yaml toggle requiring redeploy, a runtime env-var requiring restart, or hot-reloadable? Same secret path or different (m11/orion/basic_credentials)?

14. **Declare idempotency semantics for the two SFDC writebacks** (sfdc.update_client, sfdc.create_interaction_summary). Retry on 5xx can cause double-writes. SFDC If-Match + record ETag? Client-generated idempotency key?

15. **Bound the auth.ts per-firm token cache with LRU.** Match R5 AC5.4 and R6 AC6.2's 1024-entry LRU cap. Unbounded Map<firm_id, CachedToken> is an OOM vector.

16. **Add a vendor-schema-drift change process.** When eMoney (or any vendor) adds a new field, what's the workflow to add to the allow-list? Who approves (Compliance SME per AC15.5)? What's the SLA?

17. **Document the Schwab trade-submission descope** from ARCH-09 Phase 2 read-write to M11-REST Phase 2 read-only. DECISION-LOG entry (Appendix E) citing rationale (RIA lighthouse is read-only per IMPL-06 Blocker 1).

---

## Recommended Fixes

R1. **Measure and cite the Docker image-size closure.** node_modules + dist/ + distroless base = total. AC11.5 asserts 150 MiB; show math.
R2. **Add latency targets** (p50/p95/p99 TTFB per tool). M6 uses them to tune its own breaker-reset clock.
R3. **Add a chaos test** in Task 23 (secrets backend 500 for 30s; DNS fail for 10s; vendor TLS handshake hangs).
R4. **Add Retry-After header edge-case tests**: negative values, HTTP-date 30 days in future, invalid values — clamp at max(value, 30) and cap at 300s.
R5. **Add a per-firm-token LRU eviction test** (1025-entry load, assert firm #1 evicted).
R6. **Add "which adapter wins on cost_basis conflict" one-liner** (M7 owns reconciliation between REST and SFTP Schwab tax lots).
R7. **Strengthen Dockerfile lint to require pinned SHA256 digests** via custom CI check (hadolint doesn't enforce by default).
R8. **Add Prometheus-compatible metric emission**, even via pino → log-based metrics (Grafana Loki). Don't leave M10 dashboard-blind.
R9. **Provide values-schema JSON** for the Helm umbrella chart so `helm lint` catches missing values before deploy.
R10. **Cross-verify M7 translator coverage against M11 tools.** Include cross-verification result in §Integration Point with M7.

---

## Verdict

**7.27/10 — CONDITIONAL GO. Fix the 17 required items; do NOT skip to build.**

The spec has the right shape. It addresses all 8 mandatory steering rules (10, 20-26), enumerates 18 requirements and 133 ACs, covers every Phase 2 vendor with OAuth flows and worked examples, and honors the M7 audit-bypass contract on the critical dimension (no import, no canonicalization, no direct translator call). Security is strong — AST scans, fixture scans, redact rules, distroless-nonroot, mTLS 1.3-only, per-tenant namespace + NetworkPolicy, eMoney scope-creep fail-closed. Testability has the right primitives (FakeClock, FakeSecretsClient, msw, SPEC-TRACEABILITY discipline).

The spec falls short on accuracy — and the two severe accuracy problems are exactly the kind a reviewer should not let through. Fabricated RES-08 citations (four in a row, with the §5 one especially bad because RES-08 §5 is PAYMENT AND SETTLEMENT with no eMoney content at all) mean every rate-limit DECISION-LOG entry fails fact-check. More damaging, the eMoney SUMMARY-only allow-list does not match M7's Pydantic model — the two were written independently and never reconciled. Implementing AC8.5 as written means the RIA meeting-prep journey's planning-data integration fails Stage 6 translation on every call. This would surface in integration, but the point of a spec is to catch it before integration.

The gaps column is where the spec reveals its youth: no concurrency pinning, no pod resource limits, no observability hand-off, no SSRF mitigation, no Schwab RT-failure alerting path, no idempotency semantics for the two writebacks, no Phase 3 Basic-auth enablement detail. These aren't deal-breakers — most show up in production and get patched — but the M3/M7 discipline bar says catch them at spec time.

The path to 8.0+ is clear: a full v0.2.0 rewrite addressing the 17 required fixes. Not surgical patches — a rewrite. Follow M7's pattern (v0.1 → v0.2 fixed 17 items in 2 weeks, v0.3 fixed 4 NI items → GO at 8.29). The architecture is sound; the content needs tightening. Re-review after rewrite targeting 8.0+.

Do the work. The spec is close.

---

*m11-rest-adapters-REVIEW.md — Project 007 FSI Interoperability Platform*
*LLMJ v1 Review — adapter-agent acting as independent judge*
*2026-04-25*
