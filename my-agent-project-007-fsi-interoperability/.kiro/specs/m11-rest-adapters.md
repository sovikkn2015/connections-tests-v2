# Spec: M11 REST Adapters

> Module: M11-REST — MCP Adapters (REST sub-type only)
> Phase: 2 (Intelligence Layer — RIA lighthouse)
> Owner: Adapter Specialist (`007-adapter-agent`)
> **Version: 0.2.0 (post-LLMJ-v1 fix)** — full rewrite of v0.1.0 (7.27/10 CONDITIONAL GO) addressing all 17 required fixes + 10 recommended fixes. Target re-review ≥ 8.0/10 GO.
> Dependencies (runtime): HashiCorp Vault / AWS Secrets Manager (secrets); cert-manager (mTLS); outbound vendor HTTPS endpoints
> Dependencies (code): `@project-007/mcp-sdk` (local TypeScript package). ZERO imports from M1-M10, M12, M13, compliance.gap*, m7_schema_translators. Adapters do NOT import M7.
> Consumers: M6 Trust-Aware Gateway (Stage 5 `m6.vendor_call` via `VendorAdapter` protocol). M6 is the ONLY caller in Phase 2.
> Design Sources: 007-consolidated-design-and-plan.md Part 10 + Phase 2 plan, ARCH-09 Module M11 row + §M11 Adapter Sub-Types + dependency matrix, ARCH-07 tech stack (§M11-REST row), IMPL-06 Blocker 1 (principal review / execution deferred to Phase 3) + Blocker 2 (M11 polyglot), RES-08 §2 (custodians) + §3 (portfolio mgmt) + §6 (CRM), Steering rules 10 / 20-26 / 28-34, M7 spec v0.3.0 §Integration Point with M11 (dual-caller audit contract), M7 `src/m7_schema_translators/emoney/models.py` `EMoneyPlanSummary` + `salesforce_fsc/models.py` `SalesforceFSCAccountContact` (verified line-by-line 2026-05-05), M6 spec §R3 (`VendorAdapter` protocol).
> Language: TypeScript 5.4+ | Runtime: Node.js 20+ (LTS) | Validation: Zod 3.23+ | HTTP: `undici` (native fetch) + retry | MCP: `@modelcontextprotocol/sdk` ≥ 0.5 | Property-based tests: `fast-check` ≥ 3.0
> Estimated Lines: ~2,400 total across 4 adapters + shared SDK (~500 avg per adapter + shared ~450 + tests ~900)

---

## Changelog v0.1.0 → v0.2.0

v1 LLMJ reviewer scored v0.1.0 at **7.27/10 CONDITIONAL GO** (Accuracy 5.8, Gaps 5.0, Completeness 8.2, Security 8.4, Testability 7.5, Design Alignment 7.7). 17 required fixes + 10 recommended fixes. v0.2.0 is a full rewrite — every fix landed in the traceability table at Appendix F.

| Area | v0.1.0 | v0.2.0 |
|------|--------|--------|
| Accuracy — rate-limit citations | 4 citations (RES-08 §2.1/§3.1/§5/§6.1) that RES-08 does NOT contain. §5 wrong section entirely (Payment & Settlement). | Citations replaced with real vendor-doc URLs (Salesforce Platform Limits Cheatsheet) or explicit `PENDING-VERIFICATION` markers for numbers behind developer-portal logins. See AC5.2, Appendix E rows 1-4. |
| Accuracy — eMoney allow-list (AC8.5) | 16 fields that overlapped M7's `EMoneyPlanSummary` on only ~5. Every tool call would have failed Pydantic at M7 Stage 6. | Rewritten to M7's exact field set (verified 2026-05-05). M7 is source of truth. See AC8.5, §Known Blockers, Appendix E row 6. |
| Accuracy — SFDC PascalCase vs M7 snake_case | Silent. Spec claimed passthrough works; it doesn't. | Added to §Known Blockers as `SHARED-WITH-M7` with reproduction + integration-test gate. See §Known Blockers row 4 + Appendix E row 5. |
| Accuracy — Orion URL paths | Asserted `/api/v2.0/portfolio/accounts/...` as if sourced. | Marked `PENDING-VERIFICATION` like SFDC field names. See AC2.11, Appendix E row 21. |
| Completeness — SEC EDGAR | Dismissed as Phase 3/4 (wrong — ARCH-09 Phase 1). | DECISION-LOG entry: EDGAR is Phase 1 per ARCH-09 but is M8 Research Pipeline's data source, NOT M11-REST Phase 2 lighthouse (RIA meeting-prep). Deferred to M8 build window. Appendix E row 22. |
| Completeness — Alpha Vantage + News API | One-line dismissal. | DECISION-LOG entry + M8 cross-reference: gated by M8 spec. Appendix E row 23. |
| Completeness — Docker image-size math (R1/AC11.5) | 150 MiB cap asserted, no math. | Breakdown: distroless-nodejs20 ~80 MiB + `node_modules` ~40 MiB + `dist/` ~10 MiB ≈ **130 MiB** with 20 MiB buffer. See AC11.5. |
| Completeness — Latency targets | Absent (only startup budget). | p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms adapter-side. See AC1.5. |
| Completeness — Phase 3 Orion Basic-auth toggle | Described as "stubbed"; shape undocumented. | Concrete: `ORION_AUTH_MODE=basic` is a Helm values.yaml value requiring pod redeploy; separate Secret path `m11/orion/basic_credentials` → `{username, password}`; auth flow branches at `src/auth.ts` startup; same rate-limit + circuit-breaker config. R4 AC4.12, Appendix C.2 Phase 3. |
| Security — Schwab RT-rotation-failure alerting | "degraded, not crash" — latent 30-min outage. | AC4.13: `{event:"auth.schwab.rt_rotation_failed", severity:"CRITICAL"}` → M10 audit sidecar → PagerDuty/OpsGenie within 5 minutes. |
| Security — Schwab ServiceAccount RBAC | "narrow exception" mentioned, no YAML. | Concrete Role + RoleBinding YAML in §RBAC Template — `["get","update"]` on `m11-schwab-refresh-token` Secret ONLY. |
| Security — SSRF on vendor-returned URLs | Silent. | AC14.10: validate `instance_url` against egress FQDN allow-list; reject RFC 1918 / link-local / loopback. `vendor_ssrf_blocked` errorCode. |
| Security — auth.ts token cache bound | Unbounded Map → OOM. | LRU 1024 entries (`lru-cache` added to allow-list AC12.2). AC4.14. |
| Security — Observability hand-off to M10 | Silent. | pino JSON logs → Datadog/Langfuse sidecar (Helm toggle) → M10 aggregator. Optional OTEL OTLP-stdout exporter. §Observability Hand-Off to M10 + AC7.9. |
| Security — Concurrency + K8s resources | Silent. | `undici.Agent({connections:10})`. `resources.requests.{cpu:100m,memory:256Mi}` / `limits.{cpu:500m,memory:512Mi}`. 1 replica Phase 2; HPA Phase 3. AC3.9 + AC3.10. |
| Testability — error-contract test mechanisms | Under-specified. | Per-class mechanism table in AC16.4. |
| Testability — property-based Zod fuzz | Absent. | AC18.6 + §fast-check Strategy Approach with worked example (`sfdc.fetch_client`). |
| Testability — Retry-After edge cases | Silent. | AC5.7 expanded: negative → 0; HTTP-date > 300s → cap 300; malformed → 30. Test matrix in Task 7. |
| Gaps — SFDC writeback idempotency | Silent. | AC8.9 + T-SF4/T-SF5: `If-Match` ETag captured from prior fetch; 412 → `vendor_conflict` → M6 re-fetches + retries. |
| Gaps — Schwab trade submission descope | Silent. | DECISION-LOG entry: Phase 2 read-only per IMPL-06 Blocker 1. Appendix E row 24. |
| Gaps — Vendor schema-drift change process | Silent. | AC15.6: field NAME captured in log → SME review 48h → allow-list + MINOR bump → deploy. |
| Recommended — chaos test | Absent. | Task 23 extended with 3 chaos scenarios. |

---

## Architecture Clarification: M11 is Polyglot, This Spec is REST-Only

Steering Rule 10: "M11 is POLYGLOT: TypeScript for REST, Python for BLPAPI/gRPC/SFTP. Each adapter is its own container." ARCH-09 §M11 Adapter Sub-Types enumerates five sub-types: M11-REST (TypeScript), M11-BLPAPI (Python), M11-gRPC (Python), M11-SFTP (Python), M11-MCP-NATIVE (passthrough via M6).

This spec covers ONLY **M11-REST** for the Phase 2 lighthouse.

- **M11-REST is a collection of independent adapters** — four of them in Phase 2. Each adapter is its own npm package, Docker image, Kubernetes Deployment, NetworkPolicy, cert-manager Certificate. Adapters share ONLY the `@project-007/mcp-sdk` local package (MCP types + server harness). No business logic, no cross-adapter state.
- **Adapters return RAW vendor payloads.** Canonical translation is M7's job (called by M6 at Stage 6, NOT by M11). Matches M7 spec v0.3.0 §Integration Point with M11 verbatim.
- **M11 does NOT import M7.** AC12.6 enforces this via AST + package-manifest scan.
- **M6 is the only caller.** M11 adapters expose an MCP HTTP interface; M6 speaks MCP via the `VendorAdapter` Protocol. No other Phase 2 module talks to adapters directly.
- **M11 is runtime-agnostic.** Managed Agents (Cloud Tier 3/4) and Strands (hybrid/on-prem Tier 1/2/5) both see adapters as plain MCP HTTP services behind M6. No code path differs by runtime.

---

## Phase 2 Lighthouse Scope

Per 007-consolidated-design-and-plan.md Part 10 and Phase 2 plan in ARCH-09, M11-REST Phase 2 covers **4 vendors × 14 tools**:

| Adapter | Source System (M3 `SourceSystem`) | Tools (14 total) | Rationale |
|---------|-----------------------------------|------------------|-----------|
| **Salesforce FSC** | `salesforce_fsc` | `sfdc.fetch_client`, `sfdc.fetch_household`, `sfdc.fetch_goal`, `sfdc.update_client`, `sfdc.create_interaction_summary` (5) | CRM — client master, Household, goal picklists. Writebacks use `If-Match` ETag idempotency (AC8.9). |
| **Orion** | `orion` | `orion.fetch_holdings`, `orion.fetch_transactions`, `orion.fetch_household`, `orion.fetch_taxlots` (4) | Portfolio accounting — positions, trade history, custodial Household, embedded lots. |
| **eMoney** | `emoney` | `emoney.fetch_plan_summary` (1) | Financial planning — plan-level SUMMARY only. Raw plan body NEVER crosses adapter boundary (strict Zod allow-list matching M7's `EMoneyPlanSummary`). |
| **Schwab (Trader API REST)** | `schwab` | `schwab.fetch_positions`, `schwab.fetch_taxlots`, `schwab.fetch_master_account` (3) | Custodian — positions, tax lots, master-account grouping. **READ-ONLY** (trade submission descoped to Phase 3 per IMPL-06 Blocker 1; Appendix E row 24). |

### Explicitly OUT of Scope (Phase 2 M11-REST)

- **Schwab trade submission** — descoped to Phase 3 per IMPL-06 Blocker 1 (Principal Review + FINRA 2210 + execution order state machine). Appendix E row 24.
- **SEC EDGAR** — ARCH-09 Phase 1 (10 req/s, free API); deferred to M8 Research Pipeline build window (M8 owns EDGAR as a 10-K/10-Q/8-K data source, not M11-REST for meeting-prep). Appendix E row 22.
- **Alpha Vantage + News API** — ARCH-09 Phase 2 but gated by M8 Research Pipeline spec (not yet written). Appendix E row 23.
- **Other REST adapters** — Fidelity, Pershing, Wealthbox, Redtail, Envestnet, ComplySci. Deferred to Phase 3/4.
- **M11-BLPAPI, M11-gRPC, M11-SFTP, M11-MCP-NATIVE** — separate specs, separate containers, Phase 2 SFTP / Phase 4 others.
- **Vendor writebacks beyond SFDC interaction summary** — Orion/eMoney/Schwab are read-only in Phase 2.
- **Webhook/streaming subscriptions** — poll-only in Phase 2.
- **SFDC Apex custom endpoints** — standard REST + SOQL only.

---

## Known Blockers & Pending Items

Per RES-08, IMPL-06, and Steering Rules 20-26, M11 inherits these open questions. Each maps to a DECISION-LOG entry in `src/m11_rest_adapters/DECISION-LOG.md` (see R15).

| Area | Question | Impact on M11-REST | Status |
|------|----------|--------------------|--------|
| Schwab developer-program approval | RES-08 §2.1 — Schwab Advisor Services vendor approval takes 6-8 weeks, security assessment required | Cannot hit production Schwab Trader API until approved. Phase 2 lighthouse uses **Schwab sandbox** (api-sandbox.schwab.com). Production cutover is a deployment gate. | PENDING-VENDOR-APPROVAL (operational) |
| eMoney API access tier | RES-08 §6 — eMoney has restricted API access for non-Fidelity firms; 6-12 month approval timeline | Phase 2 lighthouse uses **eMoney sandbox**. Production requires Fidelity partnership agreement. | PENDING-VENDOR-APPROVAL |
| SF FSC field names not verified against live org | M7 v0.3.0 DECISION-LOG flags `FinServ__AccountIds__c`, `FinServ__HouseholdId__c`, `FinServ__ClientArchetype__c` as PENDING-VERIFICATION | SFDC adapter SOQL queries assume generic FSC v59.0 extension names. If live org uses different custom fields, SOQL returns empty columns. M11 forwards whatever SFDC returns; M7 translator fails at Pydantic `extra="forbid"` if shape is wrong. | SHARED-WITH-M7 — M11 inherits, does not resolve. |
| **SFDC PascalCase vs M7 snake_case field names (v0.2.0 new)** | M7's `SalesforceFSCAccountContact` (verified 2026-05-05 at `src/m7_schema_translators/salesforce_fsc/models.py`) uses snake_case (`account_id`, `first_name`, `household_id`, `kyc_status`) with `extra="forbid"` and **NO Pydantic aliases**. Real SFDC REST returns PascalCase (`Id`, `FirstName`, `FinServ__HouseholdId__c`). `SalesforceFSCAccountContact(**vendor_payload)` → `extra_forbidden` on every key. | Reproduction: M6 Stage 6 calls `to_canonical_client("salesforce_fsc", Client, sfdc_json)` → Pydantic error on first key. Resolution options: **(a)** M7 adds `populate_by_name=True` + `Field(alias="Id")` etc. to `SalesforceFSCAccountContact`; **(b)** M7 adds an alias-transformer helper called before `model_validate`; **(c)** M6 inserts a PascalCase→snake_case transformer at Stage 5.5 (violates "M11 returns raw" contract — rejected). **(a) or (b)** — M7's call. M11 does NOT pre-normalize per R12 AC12.1. Integration-test gate: `tests/integration/test_m7_sfdc_shape.py` calls M7 with an actual SFDC-shaped fixture; must pass before the SFDC adapter goes to pre-prod. | SHARED-WITH-M7 — **M7 to resolve in v0.3.1 or v0.4.0**. M11 v0.2.0 documents gap; does not close it. Appendix E row 5. |
| Orion MarketValue accrued interest | RES-08 §3.1 — "MarketValue field — does it include accrued interest? Must document per custodian feed." | Adapter does not interpret — forwards raw numeric. M7 owns `market_value_includes_accrued` flag. | SHARED-WITH-M7 |
| **Orion URL paths (v0.2.0 new)** | `/api/v2.0/portfolio/accounts/{id}/positions` et al. are not RES-08-sourced. Archived 007 code used `/api/v1`. Live Orion developer portal uses mixed path prefixes and requires login. | Adapter URL paths marked `PENDING-VERIFICATION` (mirror SFDC field-name handling). Verification gate: first-live-call probe at Task 11 captures and confirms path. Fail-loud at startup if path returns 404. | PENDING-VERIFICATION — developer-portal confirmation required. Appendix E row 21. |
| Schwab sandbox → production OAuth divergence | Sandbox may issue non-expiring tokens; production mandates 30-minute access + 7-day refresh rotation | Adapter code is production-shaped from day one. Sandbox is a strict subset. | Addressed in R4 (token rotation) + Task 14. |
| Orion OAuth vs Basic auth | Orion exposes both OAuth and HTTP Basic per RES-08 §3.1 | Phase 2 = OAuth. Phase 3 = Basic fallback via `ORION_AUTH_MODE=basic` Helm toggle (pod redeploy). Appendix C.2 Phase 3 section. | RESOLVED — OAuth Phase 2. |
| NetworkPolicy egress CIDR churn | Vendor public-IP ranges change quarterly | Phase 2 uses Cilium `FQDNSelector` (if Cilium) or wide CIDR with named-list ConfigMap. | RESOLVED — FQDN-selector. |
| mTLS cert-manager issuer in hybrid/on-prem | Cloud = AWS Private CA; hybrid/on-prem = customer internal CA | Issuer is a Helm value; manifests are topology-agnostic. | RESOLVED — Helm values toggle. |
| Rate-limit headers (429 parsing) | SFDC/Schwab return `Retry-After`; Orion/eMoney do not | Token bucket first; 429 extends pause. Malformed/missing header → default 30 s, cap 300 s (AC5.7). | RESOLVED — v0.2.0 AC5.7. |
| Salesforce daily API call budget | SFDC governor limits per **org**; noisy neighbor risk | Adapter-side token bucket enforces **per-firm-per-vendor** quota from M5 config. | RESOLVED — AC5.4. |
| Schwab tax-lot field granularity | Sandbox vs prod field-name divergence possible | Adapter returns RAW Schwab JSON; M7 `schwab/taxlot.py` owns normalization. | RESOLVED — passthrough. |
| eMoney "raw plan" vs "summary" boundary | What constitutes safe `plan_summary` vs raw plan body? | Zod output schema **aligned to M7's `EMoneyPlanSummary`** (v0.2.0 fix). Non-matching fields → HTTP 502 `emoney_raw_plan_forbidden`. | RESOLVED — AC8.5. |

Implementation proceeds with documented rules. Pending items are operational (vendor approval) or inherited from M7 (shape questions) — none block the M11-REST spec itself.

---

## Steering Rules M11-REST Must Honor

| Rule # | Rule | Addressed In |
|--------|------|--------------|
| **10** | M11 is POLYGLOT: TypeScript for REST, Python for BLPAPI/gRPC/SFTP. Each adapter is its own container. | R1 (TypeScript), R3 (per-adapter Docker image), R11 (directory structure), entire spec scope |
| **20** | Zero credentials in git. All secrets via HashiCorp Vault or AWS Secrets Manager. | R4 (SecretsClient), AC4.1 (AST scan), Task 2, §Security Constraints |
| **21** | mTLS between ALL modules (cert-manager, 24hr rotation). | R9 (mTLS), AC9.1-9.5, §mTLS Configuration template, Task 6 |
| **22** | Private subnets only for data plane. PrivateLink for Bedrock. No public internet for MNPI. | R9 (egress control), §NetworkPolicy Template, §Deployment Notes. M11 is the ONE module with public-internet egress (allow-listed per-adapter). |
| **23** | Per-tenant KMS key. Namespace isolation. NetworkPolicy per module. | R9 AC9.6-9.7, §NetworkPolicy Template |
| **24** | docker-compose.yml for local dev. Helm umbrella chart for production. | R11 AC11.6, §Deployment Notes |
| **25** | 3 topologies: cloud, hybrid, on-prem — toggled via Helm values. | §Deployment Notes — M11 manifests are topology-agnostic. |
| **26** | GitOps via ArgoCD. CI/CD via GitHub Actions. | Out-of-spec tooling. Adapter images are ArgoCD-managed. Noted in §Deployment Notes. |

---

## Requirements

### R1. MCP Protocol Contract — GET / + POST /tools/list + POST /tools/call

Every M11-REST adapter is an HTTP server that implements **exactly three endpoints**. No additional routes. This is the universal MCP contract inherited from `@modelcontextprotocol/sdk` — any deviation breaks M6's `VendorAdapter` protocol.

**Acceptance Criteria:**

- **AC1.1:** `GET /` returns `{type: "mcp-server", version, vendor, schemaVersion, vendorApiVersion, tools: string[]}`. `vendor` matches `SourceSystem`. `vendorApiVersion` matches M7's constant (SFDC `"v59.0"`, Orion `"v2.0"`, eMoney `"v2"`, Schwab `"v1"`).
- **AC1.2:** `POST /tools/list` returns `{tools: ToolDescriptor[]}` with `{name, description, inputSchema: JSONSchema7}`. Tools alphabetically sorted. `inputSchema` via `zod-to-json-schema` (`target: "jsonSchema2020-12"`, pinned `>=3.22,<4.0`). No `any`.
- **AC1.3:** `POST /tools/call` accepts `{name, arguments}`. Success `{result, error:null}`; failure `{result:null, error:{code, message, vendorStatusCode, retryable}}`.
- **AC1.4:** No fourth endpoint. Test fires `GET /health`, `GET /metrics`, `POST /anything` → HTTP 404.
- **AC1.5 (v0.2.0):** 60 s timeout (`ADAPTER_HTTP_TIMEOUT_MS` default 60000). **Steady-state latency targets** (adapter-side only, excluding vendor): **p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms**. Task 23 enforces at 200-call sample.
- **AC1.6:** `GET /` DOUBLE DUTY — MCP handshake + K8s health. 200 when OAuth OK + circuit CLOSED + mTLS OK. 503 otherwise with `{status:"degraded", reason, checks:{oauth, circuit, mtls}}`.
- **AC1.7:** Every response: `Content-Type: application/json; charset=utf-8`, `X-Adapter-Version: {version}`, `X-Trace-Id` echoed/generated.
- **AC1.8:** Non-JSON → 415. Body > 1 MiB → 413.

### R2. Tool Registry and Coverage (4 Adapters, 14 Tools)

**Acceptance Criteria:**

- **AC2.1:** SFDC 5 tools: `sfdc.{fetch_client, fetch_household, fetch_goal, update_client, create_interaction_summary}`.
- **AC2.2:** Orion 4 tools: `orion.{fetch_holdings, fetch_transactions, fetch_household, fetch_taxlots}`.
- **AC2.3:** eMoney 1 tool: `emoney.fetch_plan_summary`.
- **AC2.4:** Schwab 3 tools: `schwab.{fetch_positions, fetch_taxlots, fetch_master_account}`. **No `schwab.submit_trade`** (Phase 3 per IMPL-06 Blocker 1).
- **AC2.5:** Names match `^(sfdc|orion|emoney|schwab)\.(fetch|create|update)_[a-z_]+$`.
- **AC2.6:** Each tool description 20-500 chars. Read tools say "returns raw vendor JSON — use M7 translator to canonicalize".
- **AC2.7:** Registry `Readonly<Record<...>>`, `Object.freeze`.
- **AC2.8:** Keys alphabetically sorted.
- **AC2.9:** Unknown name → 404 `tool_not_found`.
- **AC2.10:** Zod-invalid → 400 `invalid_arguments` (path only, no values).
- **AC2.11 (v0.2.0):** Orion endpoint paths **PENDING-VERIFICATION**. Task 11 startup probe; 404 → `orion.path_unverified` log + adapter degraded.

### R3. Per-Adapter Independence

**Acceptance Criteria:**

- **AC3.1:** Directory layout per §Directory Structure. Four vendor dirs + `shared/mcp-sdk/`.
- **AC3.2:** Unique package names per adapter. Version `0.1.0` initially.
- **AC3.3:** Zero cross-adapter dependency.
- **AC3.4:** Own `Dockerfile`, independent image tags.
- **AC3.5:** Own Deployment + ServiceAccount + NetworkPolicy + Service.
- **AC3.6:** No intra-M11 IPC.
- **AC3.7:** `@project-007/mcp-sdk` contains ONLY shared scaffolding + **v0.2.0 `LRUCache` re-export + `ssrf.ts`**.
- **AC3.8:** Explicit named-export list.
- **AC3.9 (v0.2.0 concurrency):** Exactly ONE `undici.Agent({connections: 10, pipelining: 0, keepAliveTimeout: 30_000, keepAliveMaxTimeout: 60_000})`. Override via `ADAPTER_UNDICI_CONNECTIONS` (1-64).
- **AC3.10 (v0.2.0 K8s resources):** `requests: {cpu: 100m, memory: 256Mi}`, `limits: {cpu: 500m, memory: 512Mi}`. Phase 2 = **1 replica per adapter per firm**. HPA Phase 3 via `hpa.enabled` (default false).

### R4. Credentials via SecretsClient — Zero Hardcoding

**Acceptance Criteria:**

- **AC4.1:** AST scan rejects credential-shaped variable assignments.
- **AC4.2:** `SecretsClient` interface with `getSecret`, `getJSONSecret`, `setSecret`, `refreshRequired`. `VaultSecretsClient` + `AWSSecretsClient`. `SECRETS_BACKEND ∈ {vault, aws}` (unset → fail).
- **AC4.3:** Secret paths `m11/{vendor}/{credential_type}`, per-adapter const.
- **AC4.4:** Startup fails (exit 2) + `secrets_bootstrap_failed` on missing path or parse failure.
- **AC4.5:** Tokens never logged. Test asserts no substring match.
- **AC4.6:** In-memory only. Pod restart → refetch.
- **AC4.7:** Proactive refresh when `expiresAt - now() < 60_000 ms`. Schwab RT write failure → `GET /` reports `oauth:"degraded"`, no crash.
- **AC4.8:** mTLS certs mounted from `/etc/m11/mtls/`. `fs.watchFile` reload. Reload failure → 503.
- **AC4.9:** Zero credentials in Dockerfile. Hadolint CI.
- **AC4.10:** `.env.example` all REPLACE_ME. v0.2.0 adds `ADAPTER_UNDICI_CONNECTIONS`, `ORION_AUTH_MODE`, `SIDECAR_ENABLED`, `OTEL_EXPORTER_OTLP_ENABLED`.
- **AC4.11:** Regex scan `(?i)(AKIA|eyJ|-----BEGIN|xox[pb]-|sk_live_)` over `.env.example`.
- **AC4.12 (v0.2.0 Orion Phase 3 toggle):** `ORION_AUTH_MODE ∈ {oauth, basic}` resolved at **startup only** (not hot-reloadable). Helm values change + pod redeploy. `basic` uses `m11/orion/basic_credentials` → `{username, password}`. `auth.ts` branches at bootstrap. Both branches test-covered.
- **AC4.13 (v0.2.0 Schwab alerting):** RT write failure → pino `fatal` `{event:"auth.schwab.rt_rotation_failed", severity:"CRITICAL", firm_id, retry_count, reason}`. M10 sidecar → PagerDuty/OpsGenie within 5 min. SLO: ack ≤ 15 min.
- **AC4.14 (v0.2.0 LRU):** `tokenCache: LRUCache<string, CachedToken>({max: 1024, ttl: null, updateAgeOnGet: true})`. 1025-entry eviction test.

### R5. Per-Adapter Rate Limiting — Token Bucket (Fail-Closed)

**Acceptance Criteria:**

- **AC5.1:** `TokenBucket(rpm, burst, clock).tryAcquire()` → `{ok:true}|{ok:false, retryAfterMs}`. `Clock` DI.
- **AC5.2 (v0.2.0 — citations corrected):**
  - **SFDC 100K/24h**: Salesforce Platform API Limits Cheatsheet — `https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/`. `RPM=4166, BURST=200`. `DailyBucket` resets midnight UTC.
  - **Orion 60 RPM (default)**: **PENDING-VERIFICATION** — developer portal login-gated. `RPM=60, BURST=10`. Override via Helm.
  - **eMoney 30 req/s (default)**: **PENDING-VERIFICATION** — Fidelity partner portal. `RPM=1800, BURST=30`. Override via Helm.
  - **Schwab 120 RPM (sandbox default)**: **PENDING-VERIFICATION** — Developer Portal NDA-gated. `RPM=120, BURST=20`. Override via Helm.
- **AC5.3:** Empty bucket → 429 `rate_limit_exceeded` + `Retry-After` header.
- **AC5.4:** Per-firm key `{firm_id}:{vendor}` from required `X-Firm-ID`. `LRUCache<string, TokenBucket>({max: 1024})`.
- **AC5.5:** Vendor 429 pauses local bucket `max(parsedRetryAfter, 30)` s. Counts as circuit failure.
- **AC5.6:** Pino `rate_limit_hit`, `rate_limit_vendor_429`. No PII.
- **AC5.7 (v0.2.0 edge cases):** Integer OR HTTP-date. Negative → 0 then default 30. HTTP-date > 300 s future → cap 300 s (log `retry_after_capped`). Malformed → default 30 s (log `retry_after_malformed`, length only). Absent → 30 s. Zero → 1 s minimum.
- **AC5.8:** `FakeClock` test: exhaust → 429 → advance → succeed.
- **AC5.9 (v0.2.0):** Task 23 concurrent-load: 50 simultaneous requests, `burst=10` → first 10 pass, 40 get 429.

### R6. Circuit Breaker + Retry

**Acceptance Criteria:**

- **AC6.1:** Three-state breaker. OPEN on ≥5 consecutive failures OR >50% over rolling 60s with ≥10 calls. Reset 30_000 ms.
- **AC6.2:** Per `{firm_id}:{vendor}` key. `LRUCache({max: 1024})`.
- **AC6.3:** OPEN → 503 `vendor_circuit_open`, retryable.
- **AC6.4:** Retry up to 3, exponential from 100 ms, doubling, jitter ±25%. Retries 5xx + timeout + socket + DNS. Never 4xx (except 429 per R5) or OAuth.
- **AC6.5:** Exhaustion → 502 `vendor_error`.
- **AC6.6:** Failed retry increments; success resets in CLOSED.
- **AC6.7:** Pino `circuit_breaker_{opened,half_open,closed}`.
- **AC6.8:** Full vendor-status → adapter-status table in §Design Error Code Map.
- **AC6.9:** DI-testable.
- **AC6.10:** M6 has gateway-level breaker (defense-in-depth).

### R7. Structured JSON Logging — Zero PII / Zero Vendor Payloads

**Acceptance Criteria:**

- **AC7.1:** `getLogger` from shared SDK.
- **AC7.2:** Redact `req.body.arguments.{ssn,taxId,email,dateOfBirth}`, `req.headers.{authorization,x-vendor-token}`, `err.response.data`, wildcards `**.{password,secret,token}`. Replacement `"[REDACTED]"`.
- **AC7.3:** No `console.*` (AST).
- **AC7.4:** One `mcp.tool_call.start` + one `mcp.tool_call.end` per request. `end` has `status_code, duration_ms, vendor_status_code, retry_count, circuit_state`. NO `result`, NO `arguments`.
- **AC7.5:** Log line ≤ 8 KiB.
- **AC7.6:** `trace_id` per request; propagated to vendor.
- **AC7.7:** PII + token literal capture test.
- **AC7.8:** Default `info`; `debug` Helm-gated.
- **AC7.9 (v0.2.0):** Pino stdout → sidecar (Option A default) OR OTEL OTLP-stdout (Option B opt-in).

### R8. Zod Runtime Validation — Input + eMoney Strict Output

**Acceptance Criteria:**

- **AC8.1:** Every tool has `inputSchema`. No `z.any()`. No top-level `z.unknown()`.
- **AC8.2:** Zod → JSON Schema 2020-12.
- **AC8.3:** Invalid → 400 BEFORE vendor call, OAuth refresh, or rate-limit consumption.
- **AC8.4:** Error message contains path only — no values.
- **AC8.5 (v0.2.0 — M7-aligned allow-list):** `EMoneyPlanSummaryOutput` is `.strict()` with exactly the top-level keys of M7 `src/m7_schema_translators/emoney/models.py` `EMoneyPlanSummary` (verified 2026-05-05):

  **Required (7):** `planId`, `clientId`, `planName` (min 1), `probabilityOfSuccess` (0-100), `asOfDate` (date), `createdAt` (datetime), `updatedAt` (datetime).

  **Optional (14):** `scenarioId`, `householdId`, `planType` (enum Comprehensive/Retirement/Education/Estate/Tax/Insurance), `totalAssets` (≥0), `totalLiabilities` (≥0), `retirementGoal` (`.strict()` `{amount?≥0, targetDate?, incomeGap?}`), `monteCarlo` (`.strict()` `{successPct?:0-100, iterations?}`), `annualSavingsRate` (≥0), `annualSpending` (≥0), `socialSecurityEstimate` (≥0), `pensionIncome` (≥0), `goalIds` (array of string — **IDs only, NOT objects**), `assumptions` (`.strict()`), `recommendations` (array of `.strict()` `{category, description, priority}`).

  **Forbidden (reject):** `scenariosDetail`, `cashflowProjection`, `assumptionsDetail`, `rawPlanBody`, `advisorNotes`, `clientBalanceSheet`, `insuranceDetails`, `taxProjections`, `estateDetails`, `monteCarloFullPath`, any other top-level key.

  Rationale: M7 is source of truth. `EMoneyPlanSummary` has `extra="forbid"` — exact set-equality is the only reconciled state. Enforced by `test_m7_emoney_allowlist.py`.

- **AC8.6:** Forbidden field → 502 `emoney_raw_plan_forbidden`, `vendorStatusCode:200`, non-retryable. Pino `emoney.raw_plan_rejected` with NAMES only.
- **AC8.7:** SFDC/Orion/Schwab apply Zod to INPUT only; output is passthrough.
- **AC8.8:** Malformed vendor JSON → 502 `vendor_invalid_json`, retryable.
- **AC8.9 (v0.2.0 SFDC writeback idempotency):** `update_client` + `create_interaction_summary` require `ifMatch: string` (SFDC ETag from prior fetch response `_etag`). Adapter forwards as `If-Match: {etag}`. SFDC 412 → adapter 409 `vendor_conflict`, non-retryable. M6 re-fetches + retries once. Second 409 → bubble to caller. Not client-generated keys — SFDC doesn't support them.

### R9. mTLS + NetworkPolicy + Health Checks

**Acceptance Criteria:**

- **AC9.1:** Client cert to M6 + validate M6's. cert-manager `Certificate` per-adapter. Issuer Helm-configurable.
- **AC9.2:** Rotation 24 h (`duration: 24h, renewBefore: 8h`). `fs.watchFile` reload. Failure → 503.
- **AC9.3:** TLS 1.3 only, 3 AEAD ciphers, `requestCert: true, rejectUnauthorized: true`. Subject-CN check.
- **AC9.4:** Ingress only `app=m6-mcp-gateway` in `{firm}-m6`.
- **AC9.5:** Egress allow-list per adapter (FQDN or CIDR) + cluster DNS + OIDC. All other DENIED.
- **AC9.6:** Namespace `{firm}-m11-{vendor}`.
- **AC9.7:** ServiceAccount per adapter. Read mTLS Secret only **except Schwab** (narrow `["get","update"]` on `m11-schwab-refresh-token` per §RBAC Template).
- **AC9.8:** `GET /` checks oauth/circuit/mtls → HTTP 200 if all ok, else 503 with `checks` object.
- **AC9.9:** Probes target `/`. Startup 120 s.

### R10. Schema Version Compatibility

**Acceptance Criteria:**

- **AC10.1:** Adapter `VENDOR_API_VERSION` matches M7 exactly. `test_m11_m7_version_match.py`.
- **AC10.2:** SFDC: `GET /services/data/`; `v59.0` present → pass.
- **AC10.3:** Schwab: `GET /trader/v1/userPreference`; 404 on `/v1/*` → exit 3.
- **AC10.4:** Orion + eMoney: no version endpoint. Log `vendor_version_check_skipped`.
- **AC10.5:** First call success logs `vendor_first_call_succeeded`.
- **AC10.6:** Don't log full version-endpoint response.

### R11. Dockerfile

**Acceptance Criteria:**

- **AC11.1:** Two stages with pinned SHA256 digests (Helm values).
- **AC11.2:** Builder: `npm ci --omit=optional && npm run build && npm prune --production`.
- **AC11.3:** Runtime: `USER nonroot`, `ENTRYPOINT ["/nodejs/bin/node", "/app/dist/index.js"]`, port 8080.
- **AC11.4:** No shell; K8s probes for health.
- **AC11.5 (v0.2.0 — measured):** ≤ 150 MiB. Breakdown: distroless base ~80 MiB + `node_modules` (dominant `@aws-sdk/client-secrets-manager` ~20 MiB) ~40 MiB + `dist/` ~10 MiB ≈ **130 MiB** with 20 MiB buffer. CI asserts.
- **AC11.6:** `docker-compose.yml` with `vault:dev` for `make dev`.
- **AC11.7:** `hadolint --failure-threshold error`.
- **AC11.8:** `NODE_ENV=production`, `NODE_OPTIONS="--enable-source-maps --max-old-space-size=512"`.
- **AC11.9:** `.dockerignore` excludes tests/docs/env/git/coverage/vscode/dist.

### R12. Module Boundary Isolation

**Acceptance Criteria:**

- **AC12.1:** AST rejects imports from `m{1..13}_*`, `compliance/`, `@project-007/m{3,6,7}-*`.
- **AC12.2 (v0.2.0 — `lru-cache` added):** Allow-list: `@project-007/mcp-sdk`, `@modelcontextprotocol/sdk`, `zod`, `zod-to-json-schema`, `undici`, `pino`, `fastify`, `fastify-plugin`, `uuid`, `@fastify/helmet`, `@fastify/rate-limit` (optional), `node-vault`, `@aws-sdk/client-secrets-manager`, **`lru-cache`**. Dev-only: `vitest`, `msw`, `fast-check`, `tsx`.
- **AC12.3:** No adapter-to-adapter imports.
- **AC12.4:** No `fs.*` for app data (only `fs.watchFile` on `/etc/m11/mtls/*`).
- **AC12.5:** Adapter random uses `crypto.randomUUID()` only.
- **AC12.6:** `test_no_m7_import.ts` AST-greps — zero occurrences.

### R13. Public API Surface

**Acceptance Criteria:**

- **AC13.1:** `src/index.ts` exports exactly `startServer`, `TOOLS`, `VENDOR_API_VERSION`.
- **AC13.2:** `AdapterConfig` all fields required (enforces DI).
- **AC13.3:** Second `startServer` call throws `AdapterAlreadyRunning`.
- **AC13.4:** `client.ts` not exported.
- **AC13.5:** M6 does NOT `import` adapter code.

### R14. Security Invariants

**Acceptance Criteria:**

- **AC14.1:** (R4.) Zero hardcoded creds.
- **AC14.2:** Error messages contain only `{errorCode, message, vendor, toolName, vendorStatusCode, retryable}`.
- **AC14.3:** No filesystem writes outside `stdout`/`stderr`/`/tmp`.
- **AC14.4:** Forbidden: `eval`, `Function(`, `vm.*`, `child_process.*`, `dgram.*`, `cluster.*`, `worker_threads.*`, `process.binding`, `process.dlopen`.
- **AC14.5:** PII-shaped arg keys → warn `pii_shaped_argument` (passed through; M4 filters upstream).
- **AC14.6:** Zod input rejects PII-shaped keys except opaque-ID cases (SFDC clientId regex).
- **AC14.7:** Fixture scan: `.example`/`.invalid`/`.test` emails, `555-` SSN prefix.
- **AC14.8:** No `JSON.parse` on incoming body.
- **AC14.9:** TLS all sockets. No `rejectUnauthorized: false`.
- **AC14.10 (v0.2.0 SSRF):** `validateVendorURL(url, allowlist)`:
  - `https:` only (reject http/file/ftp/gopher/data).
  - Host must match allow-list (strict subdomain match).
  - DNS resolve; reject if IP in RFC1918 (`10/8, 172.16/12, 192.168/16`), link-local (`169.254/16`), loopback (`127/8, ::1`), ULA (`fc00::/7`).
  - Reject → startup exit 3 with `auth.sfdc.ssrf_blocked` OR mid-request 502 `vendor_ssrf_blocked`.
  Applied to SFDC `instance_url` and any vendor-returned URL. Test `tests/security/test_ssrf.ts`.

### R15. DECISION-LOG Maintenance

**Acceptance Criteria:**

- **AC15.1:** Entries: Date, Vendor, Tool/Area, Decision, Rationale, Decided By.
- **AC15.2 (v0.2.0):** Rate-limit values cite real vendor URL OR `PENDING-VERIFICATION` with named gate. No fabricated RES-08 §N.N citations.
- **AC15.3:** Every tool description has DECISION-LOG entry.
- **AC15.4:** SFDC field-name PENDING mirrored.
- **AC15.5:** eMoney raw-plan DENY list documented with source.
- **AC15.6 (v0.2.0 schema-drift):** (1) Fail closed; (2) NAME logged in `{vendor}.raw_field_observed`; (3) SME review 48 h SLA; (4) if safe, allow-list + MINOR bump + deploy; (5) if MNPI, stay BLOCKED; (6) playbook at `docs/vendor-schema-drift-playbook.md` (Task 22).

### R16. Observability Contract

**Acceptance Criteria:**

- **AC16.1:** Error body shape locked per AC1.3.
- **AC16.2:** M6 captures adapter error verbatim into `AuditEntry.payload["adapter_error"]`.
- **AC16.3 (v0.2.0):** 22-code frozen set including new `vendor_ssrf_blocked`.
- **AC16.4 (v0.2.0 per-class mechanisms):** `test_m11_error_contract.ts`:

| Error Class | errorCode | Mechanism |
|-------------|-----------|-----------|
| OAuth expiry | `vendor_auth_failed` | `FakeClock.advance(expiresAt - now + 1)`; msw 401 on refresh. |
| 5xx retry exhaustion | `vendor_error` | `msw.use(http.get('*', () => HttpResponse.json({}, {status: 503})))` across all 3 attempts. |
| Circuit OPEN | `vendor_circuit_open` | 5 consecutive msw 500 → breaker tripped → 6th returns 503. |
| Zod fail | `invalid_arguments` | Payload missing required field. |
| eMoney raw-plan | `emoney_raw_plan_forbidden` | msw returns 200 with `rawPlanBody` → strict output reject. |
| Vendor 429 | `vendor_rate_limit` | msw 429 + `Retry-After: 45`. |
| Vendor timeout | `vendor_timeout` | msw `delay(65_000)` > 60 s. |
| Malformed JSON | `vendor_invalid_json` | msw returns `'{"broken":'`. |
| Local rate-limit | `rate_limit_exceeded` | `FakeClock` exhaust + 11 calls with burst=10. |
| SSRF block | `vendor_ssrf_blocked` | FakeSecrets returns `instance_url:"http://169.254.169.254/"`. |
| mTLS reload fail | `mtls_degraded` | Rewrite cert to invalid PEM mid-run. |
| Missing firm_id | `missing_firm_id` | Request without `X-Firm-ID`. |

### R17. Startup Sequence & Fail-Fast

**Acceptance Criteria:**

- **AC17.1:** Ordered serial: env → SecretsClient → mTLS certs → OAuth bootstrap → **SSRF-validate** (v0.2.0) → version check → breakers/limits/Agent → fastify routes → TLS bind → `startup.ready`.
- **AC17.2:** 120 s budget.
- **AC17.3:** SIGTERM graceful: drain ≤ 30 s. **v0.2.0 — if Schwab RT rotation in-flight, wait ≤ 10 s for completion BEFORE drain.**
- **AC17.4:** Unhandled rejection → `fatal_error` (redact), exit 1.

### R18. Test Coverage & CI Gates

**Acceptance Criteria:**

- **AC18.1:** Per-adapter: `integration`, `client`, `auth`, `rate_limit`, `circuit`, `logging`, `zod`, `startup`, **`property` (v0.2.0)**.
- **AC18.2:** Shared SDK + cross-module test suite:
  - TypeScript shared-SDK tests (vitest): 8 files — `test_no_hardcoded_creds.ts`, `test_no_token_in_logs.ts`, `test_module_boundary.ts`, `test_package_allow_list.ts`, `test_env_example.ts`, `test_no_console.ts`, `test_forbidden_apis.ts`, `test_no_m7_import.ts`, plus core SDK tests (`test_mcp_server.ts`, `test_error_codes.ts`, `test_logger_redact.ts`, `test_ssrf.ts`, `test_m11_error_contract.ts`).
  - Python cross-module tests (pytest, repo-root `tests/integration/`): `test_m11_m7_version_match.py`, `test_m7_sfdc_shape.py`, `test_m7_emoney_allowlist.py`.
- **AC18.3:** `vitest --run`. Coverage 85% line / 75% branch.
- **AC18.4:** msw fixtures PII-free.
- **AC18.5:** `SPEC-TRACEABILITY.md` per adapter.
- **AC18.6 (v0.2.0 fast-check):** In-domain generator ≥99% accept over 1000 runs; out-of-domain ≥99% reject. Worked example for `sfdc.fetch_client` in §fast-check Strategy Approach.

---

## Design

### Directory Structure

```
src/m11_rest_adapters/
├── shared/
│   └── mcp-sdk/                        # @project-007/mcp-sdk workspace
│       ├── package.json
│       ├── src/
│       │   ├── index.ts                # barrel
│       │   ├── types.ts                # MCP envelope + AdapterConfig
│       │   ├── server.ts               # McpServer (fastify harness)
│       │   ├── logger.ts               # pino + redact
│       │   ├── clock.ts                # Clock + SystemClock + FakeClock
│       │   ├── secrets.ts              # SecretsClient + Vault + AWS
│       │   ├── errors.ts               # VALID_ADAPTER_ERROR_CODES (22) + constructors
│       │   ├── ssrf.ts                 # v0.2.0 — validateVendorURL
│       │   └── lru.ts                  # v0.2.0 — lru-cache re-export
│       └── tests/                      # 11 shared tests
├── salesforce_fsc/
│   ├── package.json, tsconfig.json, Dockerfile, .dockerignore, .env.example
│   ├── SPEC-TRACEABILITY.md
│   ├── src/ { index.ts, tools.ts, schemas.ts, client.ts, auth.ts,
│   │         circuit.ts, rate_limit.ts, config.ts, startup.ts }
│   └── tests/ { integration, client, auth, rate_limit, circuit,
│                logging, zod, property (v0.2.0), startup }.test.ts
├── orion/                              # mirror layout
├── emoney/                             # mirror + strict output Zod
├── schwab/                             # mirror + RT rotation + narrow RBAC
├── DECISION-LOG.md
└── docs/
    └── vendor-schema-drift-playbook.md # v0.2.0 AC15.6
```

### Salesforce FSC Tools

**T-SF1: `sfdc.fetch_client`** — `{clientId: /^[a-zA-Z0-9]{15,18}$/}` → SOQL on `Account` via `GET /services/data/v59.0/query/`. Response `ETag` header captured as top-level `_etag` sibling for writebacks (AC8.9).

**T-SF2: `sfdc.fetch_household`** — `{householdId: /^[a-zA-Z0-9]{15,18}$/}` → SOQL on `FinServ__Household__c` with nested `FinServ__HouseholdMember__r`.

**T-SF3: `sfdc.fetch_goal`** — `{goalId: /^[a-zA-Z0-9]{15,18}$/}` → SOQL on `FinServ__FinancialGoal__c`.

**T-SF4: `sfdc.update_client` (v0.2.0 ETag + writable allow-list)** — `{clientId, ifMatch: string (1-256), fields: .strict({FinServ__Status__c?, FinServ__ClientArchetype__c? ≤128, FinServ__RiskToleranceUpdatedDate__c? ISO-date, Description? ≤4000})}`. PII fields NOT writable. `PATCH /services/data/v59.0/sobjects/Account/{id}` with `If-Match: {ifMatch}`. 412 → adapter 409 `vendor_conflict`.

**T-SF5: `sfdc.create_interaction_summary` (v0.2.0 ETag)** — `{clientId, ifMatch, summaryText (1-32000), interactionDate (ISO date), interactionType? enum}`. `POST /services/data/v59.0/sobjects/FinServ__Interaction__c` with `If-Match: {ifMatch}` (prevents child against stale parent).

### Orion Tools (All endpoints PENDING-VERIFICATION per AC2.11)

**T-OR1: `orion.fetch_holdings`** — `{accountId: int>0, asOfDate?: ISO date ≤ today}` → `GET /api/v2.0/portfolio/accounts/{accountId}/positions`.

**T-OR2: `orion.fetch_transactions`** — `{accountId, startDate, endDate}` with `endDate - startDate ≤ 90 days` via `.refine()` → `GET /api/v2.0/portfolio/accounts/{accountId}/transactions`.

**T-OR3: `orion.fetch_household`** — `{householdId: int>0}` → `GET /api/v2.0/portfolio/households/{householdId}`.

**T-OR4: `orion.fetch_taxlots`** — `{accountId, asOfDate?}` → `GET /api/v2.0/portfolio/accounts/{accountId}/taxlots`.

### eMoney Tool

**T-EM1: `emoney.fetch_plan_summary`** — `{planId: UUID, includeGoals?: boolean}` → `GET /api/v2/plans/{planId}/summary?includeGoals=true`. **Output:** `EMoneyPlanSummaryOutput` `.strict()` per AC8.5 (M7-aligned).

### Schwab Tools (Read-Only — Phase 3 descope per Appendix E row 24)

**T-SC1: `schwab.fetch_positions`** — `{accountNumber: /^\d{8}$/, fields?: array}` → `GET /trader/v1/accounts/{accountNumber}?fields=positions`.

**T-SC2: `schwab.fetch_taxlots`** — `{accountNumber: /^\d{8}$/, symbol?: /^[A-Z0-9.\-]+$/.max(20)}` → `GET /trader/v1/accounts/{accountNumber}/taxlots` (if exposed) or derived from positions fields.

**T-SC3: `schwab.fetch_master_account`** — `{masterAccountId: /^[A-Z0-9\-]{1,32}$/, includeLinkedAccounts?: boolean}` → `GET /trader/v1/masterAccounts/{masterAccountId}`.

**NOT included Phase 2 (Phase 3 spec):** `schwab.submit_trade`, `schwab.cancel_order`, `schwab.replace_order`. Requires Principal Review + FINRA 2210 + execution order state machine per IMPL-06 Blocker 1. Appendix E row 24.

### NetworkPolicy Template

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: m11-{{ .Values.m11.vendor }}
  namespace: {{ .Values.firm.namespace }}-m11-{{ .Values.m11.vendor }}
spec:
  podSelector: { matchLabels: { app: m11-{{ .Values.m11.vendor }} } }
  policyTypes: [Ingress, Egress]
  ingress:
    - from:
        - namespaceSelector: { matchLabels: { firm: {{ .Values.firm.namespace }} } }
          podSelector: { matchLabels: { app: m6-mcp-gateway } }
      ports: [{ protocol: TCP, port: 8080 }]
  egress:
    - to:
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: kube-system } }
          podSelector: { matchLabels: { k8s-app: kube-dns } }
      ports: [{ protocol: UDP, port: 53 }, { protocol: TCP, port: 53 }]
{{- range .Values.m11.egressFQDNs }}
    - toFQDNs: [{ matchName: {{ . | quote }} }]
      ports: [{ protocol: TCP, port: 443 }]
{{- end }}
    - to:
        - namespaceSelector: { matchLabels: { kubernetes.io/metadata.name: {{ .Values.m11.secretsNamespace }} } }
      ports: [{ protocol: TCP, port: 443 }]
```

Per-adapter FQDN lists:
- SFDC: `login.salesforce.com`, `test.salesforce.com`, `*.my.salesforce.com`, `*.salesforce.com`
- Orion: `api.orionadvisor.com`, `stagingapi.orionadvisor.com`
- eMoney: `api.emoneyadvisor.com`, `api-sandbox.emoneyadvisor.com`
- Schwab: `api.schwabapi.com`, `api-sandbox.schwabapi.com`, `sws-gateway.schwab.com`

### mTLS + Deployment Template (v0.2.0 — resources + undici concurrency)

cert-manager `Certificate`:

```yaml
apiVersion: cert-manager.io/v1
kind: Certificate
metadata:
  name: m11-{{ .Values.m11.vendor }}-mtls
  namespace: {{ .Values.firm.namespace }}-m11-{{ .Values.m11.vendor }}
spec:
  secretName: m11-{{ .Values.m11.vendor }}-mtls-certs
  duration: 24h
  renewBefore: 8h
  subject: { organizations: [{{ .Values.firm.name }}] }
  commonName: m11-{{ .Values.m11.vendor }}.{{ .Values.firm.namespace }}.svc.cluster.local
  usages: [server auth, client auth]
  issuerRef: { name: {{ .Values.m11.certIssuer }}, kind: ClusterIssuer }
```

Deployment container snippet:

```yaml
containers:
  - name: adapter
    resources:                                             # v0.2.0 AC3.10
      requests: { cpu: 100m, memory: 256Mi }
      limits:   { cpu: 500m, memory: 512Mi }
    volumeMounts: [{ name: mtls-certs, mountPath: /etc/m11/mtls, readOnly: true }]
    env:
      - { name: MTLS_CLIENT_CERT_PATH, value: /etc/m11/mtls/tls.crt }
      - { name: MTLS_CLIENT_KEY_PATH,  value: /etc/m11/mtls/tls.key }
      - { name: MTLS_CA_CERT_PATH,     value: /etc/m11/mtls/ca.crt }
      - { name: MTLS_TRUSTED_SUBJECT_CN, value: "m6-mcp-gateway.{{ .Values.firm.namespace }}.svc.cluster.local" }
      - { name: ADAPTER_UNDICI_CONNECTIONS, value: "10" }   # v0.2.0 AC3.9
      - { name: SIDECAR_ENABLED, value: "true" }
```

### RBAC Template (v0.2.0 — Schwab narrow write addresses review Security weakness 2)

Default (SFDC / Orion / eMoney — read-only):

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: m11-{{ .Values.m11.vendor }}-secret-read
  namespace: {{ .Values.firm.namespace }}-m11-{{ .Values.m11.vendor }}
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["m11-{{ .Values.m11.vendor }}-mtls-certs"]
    verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: m11-{{ .Values.m11.vendor }}-secret-read
  namespace: {{ .Values.firm.namespace }}-m11-{{ .Values.m11.vendor }}
subjects:
  - { kind: ServiceAccount, name: m11-{{ .Values.m11.vendor }}, namespace: {{ .Values.firm.namespace }}-m11-{{ .Values.m11.vendor }} }
roleRef: { kind: Role, name: m11-{{ .Values.m11.vendor }}-secret-read, apiGroup: rbac.authorization.k8s.io }
```

Schwab ADDITIONAL narrow write:

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: m11-schwab-refresh-token-rotate
  namespace: {{ .Values.firm.namespace }}-m11-schwab
rules:
  - apiGroups: [""]
    resources: ["secrets"]
    resourceNames: ["m11-schwab-refresh-token"]         # ONLY this secret
    verbs: ["get", "update"]                             # no create, delete, patch, list, watch
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: m11-schwab-refresh-token-rotate
  namespace: {{ .Values.firm.namespace }}-m11-schwab
subjects:
  - { kind: ServiceAccount, name: m11-schwab, namespace: {{ .Values.firm.namespace }}-m11-schwab }
roleRef: { kind: Role, name: m11-schwab-refresh-token-rotate, apiGroup: rbac.authorization.k8s.io }
```

`resourceNames` restricts verbs to the single named Secret. No wildcards, no cluster-scope.

### Dockerfile Template

```dockerfile
# syntax=docker/dockerfile:1.7
FROM node:20-alpine@sha256:PINNED AS builder
WORKDIR /app
COPY package.json package-lock.json tsconfig.json ./
COPY src ./src
RUN npm ci --omit=optional && npm run build && npm prune --production

FROM gcr.io/distroless/nodejs20-debian12:nonroot@sha256:PINNED AS runtime
WORKDIR /app
COPY --from=builder --chown=nonroot:nonroot /app/dist ./dist
COPY --from=builder --chown=nonroot:nonroot /app/node_modules ./node_modules
COPY --from=builder --chown=nonroot:nonroot /app/package.json ./package.json
USER nonroot
EXPOSE 8080
ENV NODE_ENV=production \
    NODE_OPTIONS="--enable-source-maps --max-old-space-size=512"
ENTRYPOINT ["/nodejs/bin/node", "/app/dist/index.js"]
```

### Error Code Map (22 codes v0.2.0)

| errorCode | HTTP | retryable | Source |
|-----------|------|-----------|--------|
| `tool_not_found` | 404 | false | AC2.9 |
| `invalid_arguments` | 400 | false | AC2.10, AC8.3 |
| `missing_firm_id` | 400 | false | AC5.4 |
| `unsupported_media_type` | 415 | false | AC1.8 |
| `payload_too_large` | 413 | false | AC1.8 |
| `adapter_timeout` | 504 | true | AC1.5 |
| `rate_limit_exceeded` | 429 | true | AC5.3 |
| `vendor_rate_limit` | 429 | true | AC6.8 |
| `vendor_bad_request` | 400 | false | AC6.8 |
| `vendor_auth_failed` | 401 | false | AC6.8 |
| `vendor_forbidden` | 403 | false | AC6.8 |
| `vendor_not_found` | 404 | false | AC6.8 |
| `vendor_conflict` | 409 | false | AC6.8, **AC8.9 v0.2.0 (SFDC 412→409)** |
| `vendor_unprocessable` | 422 | false | AC6.8 |
| `vendor_error` | 502 | true | AC6.5 |
| `vendor_timeout` | 504 | true | AC6.8 |
| `vendor_circuit_open` | 503 | true | AC6.3 |
| `vendor_invalid_json` | 502 | true | AC8.8 |
| `emoney_raw_plan_forbidden` | 502 | false | AC8.6 |
| `startup_version_mismatch` | — (exit) | — | AC10.2 |
| `mtls_degraded` | 503 | true | AC9.2 |
| **`vendor_ssrf_blocked`** (v0.2.0) | 502 / startup exit | false | AC14.10 |

### Deployment Notes

- **Topology:** `values-cloud.yaml` uses AWS Private CA + `AWSSecretsClient`; `values-hybrid.yaml` uses firm CA + `VaultSecretsClient`; `values-onprem.yaml` same with no cloud egress.
- **Per-tenant KMS (Rule 23):** No PV Phase 2. SFTP Phase 2 Python container is separate.
- **Replication (v0.2.0):** Phase 2 = 1 replica per adapter per firm (singleton simplifies in-pod token cache + circuit breaker). Phase 3 HPA via `hpa.enabled` Helm value (default false Phase 2).
- **Concurrency (v0.2.0):** Shared `undici.Agent({connections: 10})` per pod. 1 replica × 10 connections × 120 Schwab RPM ≈ 20 req/min utilization under sustained load. 200 concurrent M6 requests → ~190 queue → adapter-timeout fallback at 60 s.
- **GitOps:** ArgoCD values override for image tag.
- **Helm umbrella:** `charts/m11-rest-adapters/` with 4 sub-charts + shared templates (NetworkPolicy, Certificate, Deployment, Service, ServiceAccount, Role, RoleBinding — default + Schwab variant).

---

## Observability Hand-Off to M10

M11 adapters emit pino JSON to stdout. M10 Audit Logger needs adapter-level metrics (p95 latency per tool, circuit-open counts per firm, rate-limit-hit counts per firm, SSRF-block events, Schwab RT-rotation failures). The seam between pino-stdout and M10 is declared here (fix for review weakness 4 under §Security and gap #4).

### Option A (default): Sidecar Log Shipper → M10

- A log-shipper sidecar (`fluent-bit` or `vector`) runs in the same Pod as each M11 adapter.
- Sidecar reads `stdout` via the K8s container-log stream, parses pino JSON, forwards to:
  - **Langfuse** for Agent-runtime observability (Steering Rule 6 tier 1).
  - **Datadog Logs** (cloud topology) OR **Loki** (hybrid/on-prem) for operator dashboards.
  - **M10 Audit Writer** for `severity:"CRITICAL"` pino events (AC4.13 Schwab RT rotation + `event:"emoney.raw_plan_rejected"` + `event:"auth.sfdc.ssrf_blocked"`) via the M10 aggregator's HTTP/JSON intake.
- Sidecar enabled via Helm `sidecar.enabled` (default `true` Phase 2).
- Sidecar does NOT emit traces — logs are the protocol.
- Metric derivation (p50/p95/p99) is a Loki/Datadog log-based-metric definition, not an adapter concern.

### Option B (opt-in): OpenTelemetry OTLP-stdout exporter

- Adapters include `@opentelemetry/sdk-node` + OTLP-stdout exporter (added to AC12.2 allow-list in v0.2.x if adopted).
- Spans emitted per tool call with `traceId` matching `X-Trace-Id`.
- Sidecar (Datadog OTel receiver / Jaeger agent) scrapes and forwards.
- Opt-in via Helm `otel.enabled` (default `false` Phase 2 — adds ~5 MiB to image).

**v0.2.0 commits to Option A for Phase 2 lighthouse.** Option B is on the Phase 3 roadmap. No adapter code changes required to flip; only Helm values.

### Events M10 Escalates

| Event | Severity | Escalation |
|-------|----------|------------|
| `auth.schwab.rt_rotation_failed` | CRITICAL | PagerDuty/OpsGenie within 5 min (AC4.13) |
| `auth.sfdc.ssrf_blocked` | CRITICAL | PagerDuty within 5 min — potential compromise signal |
| `emoney.raw_plan_rejected` | WARN | Ticket to compliance queue within 1 business day (schema drift investigation) |
| `circuit_breaker_opened` | INFO | Dashboard only; operator pages only if OPEN > 10 min |
| `rate_limit_hit` (local, not vendor-429) | INFO | Dashboard only |
| `startup.ready` | INFO | Dashboard only |

---

## fast-check Strategy Approach (Property-Based Zod Fuzz)

Mirrors M7 v0.3.0 §Hypothesis Strategy Approach. `fast-check` is the TypeScript equivalent of Python's Hypothesis. Used in AC18.6 property tests.

### Worked Example — `sfdc.fetch_client`

Input Zod schema:
```ts
const FetchClientInput = z.object({
  clientId: z.string().regex(/^[a-zA-Z0-9]{15,18}$/)
});
```

Property test covers both acceptance (in-domain generator) and rejection (out-of-domain):

```ts
import * as fc from "fast-check";
import { describe, it, expect } from "vitest";
import { FetchClientInput } from "../src/schemas";

describe("sfdc.fetch_client property-based", () => {

  // In-domain: strings of 15-18 chars, base62 alphabet
  const inDomainClientId = fc
    .tuple(
      fc.integer({min: 15, max: 18}),
      fc.constantFrom("a","b","c","...","Z","0","1","...","9")
    )
    .map(([len, _]) => {
      const chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789";
      return Array.from({length: len}, () =>
        chars[Math.floor(Math.random() * chars.length)]).join("");
    });

  it("accepts in-domain clientId ≥ 99% of the time", () => {
    let accepted = 0;
    const runs = 1000;
    fc.assert(
      fc.property(inDomainClientId, (id) => {
        const res = FetchClientInput.safeParse({ clientId: id });
        if (res.success) accepted++;
        return true;  // we measure rate, not single-case truth
      }),
      { numRuns: runs, seed: 42 }
    );
    expect(accepted / runs).toBeGreaterThanOrEqual(0.99);
  });

  it("rejects out-of-domain clientId ≥ 99% of the time", () => {
    // Generator includes: wrong length, forbidden chars (-, space, unicode), empty string
    const outDomain = fc.oneof(
      fc.string({minLength: 0, maxLength: 14}),
      fc.string({minLength: 19, maxLength: 100}),
      fc.constant(""),
      fc.constantFrom("dash-has-dash", "spa ce here", "emoji😀here", "héllo-with-ñ"),
    );
    let rejected = 0;
    const runs = 1000;
    fc.assert(
      fc.property(outDomain, (id) => {
        const res = FetchClientInput.safeParse({ clientId: id });
        if (!res.success) rejected++;
        return true;
      }),
      { numRuns: runs, seed: 43 }
    );
    expect(rejected / runs).toBeGreaterThanOrEqual(0.99);
  });

  it("rejects missing required fields", () => {
    fc.assert(
      fc.property(fc.record({}), (payload) => {
        const res = FetchClientInput.safeParse(payload);
        return !res.success;
      }),
      { numRuns: 100 }
    );
  });
});
```

### Per-Tool Property Test Matrix

Each tool in §Design has a corresponding `property.test.ts` section with analogous in-domain and out-of-domain generators:

| Tool | In-domain generator | Out-of-domain generator |
|------|---------------------|-------------------------|
| `sfdc.fetch_client` | base62 15-18 chars | len ≠ 15-18, Unicode, dashes |
| `sfdc.fetch_household` | base62 18 chars | len ≠ 18 |
| `sfdc.fetch_goal` | base62 18 chars | len ≠ 18 |
| `sfdc.update_client` | valid `{clientId, fields?: {...}, ifMatch: string≥1}` with only writable field names | missing `ifMatch`, non-writable fields, empty fields |
| `sfdc.create_interaction_summary` | valid `{clientId, summaryText: string max 32000, interactionDate: ISO date, ifMatch}` | summaryText > 32000, malformed date |
| `orion.fetch_holdings` | `{accountId: int > 0, asOfDate: ISO date ≤ today}` | negative accountId, future asOfDate |
| `orion.fetch_transactions` | `{accountId, startDate, endDate}` with `endDate - startDate ≤ 90 days` | range > 90 days |
| `orion.fetch_household` | `{householdId: int > 0}` | negative |
| `orion.fetch_taxlots` | `{accountId, asOfDate}` | negative |
| `emoney.fetch_plan_summary` | `{planId: UUID}` | non-UUID string |
| `schwab.fetch_positions` | `{accountNumber: 8-digit}` | other length |
| `schwab.fetch_taxlots` | `{accountNumber: 8-digit, symbol?: A-Z0-9.-, max 20}` | bad accountNumber or symbol |
| `schwab.fetch_master_account` | `{masterAccountId: uppercase alnum/dash 1-32}` | lowercase, too long |

Task 23 dress rehearsal asserts the full matrix runs green in < 60 s wall-clock.

---

## Integration Point with M6

M6 Trust-Aware Gateway is the sole caller of M11 adapters in Phase 2. The integration follows M6 spec §R3 `VendorAdapter` Protocol — adapters are registered in M6's `AdapterRegistry` at startup and invoked at M6 pipeline Stage 5 (`m6.vendor_call`).

### Control Flow (Phase 2 Lighthouse)

```
   Caller  ──MCP/HTTP──>  M6 Gateway  ──M6 Stage 1-4 (trust layer)─> (checks pass)
                                ▼
                          M6 Stage 5: m6.vendor_call
                                │
                                │  HTTPS + mTLS (24h rotating cert)
                                ▼
                       M11-REST adapter  ──HTTPS──>  Vendor API
                          (Docker container)              │
                                │  <──────RAW JSON────────┘
                                │
                          Fastify response:
                          {result: <raw vendor JSON>, error: null}
                                ▼
                          M6 Stage 6: m6.translate  ──>  M7 (Python library)
                                                         returns (canonical, note)
                                ▼
                          M6 Stage 7-9: MNPI filter, audit, return
```

### The M6 Side of the Contract

M6 sees M11 through the `VendorAdapter` Protocol declared in `src/m6_mcp_gateway/adapters.py`:

```python
@runtime_checkable
class VendorAdapter(Protocol):
    name: str
    def call(self, *, tool_name: str, payload: Any) -> Any: ...
```

M6's concrete `MCPHttpAdapter` (Phase 2 M6 amendment — NOT part of M11 spec) wraps an HTTP client that:

1. Speaks mTLS to `https://m11-{vendor}.{firm}-m11-{vendor}.svc.cluster.local:8080/tools/call`.
2. Sends body `{name: tool_name, arguments: payload}` + headers `X-Trace-Id`, `X-Firm-ID`.
3. On HTTP 2xx: returns `response.result` to the rest of M6's pipeline.
4. On HTTP non-2xx: raises `VendorAdapterError(kind="unavailable"|"error")`. `error.code` is captured into AuditEntry per AC16.2.

### Headers M6 Sends and M11 Requires

| Header | Required? | Purpose |
|--------|-----------|---------|
| `Content-Type: application/json` | YES (AC1.8) | Reject non-JSON with 415 |
| `X-Firm-ID` | YES (AC5.4) | Per-firm rate-limiter + circuit-breaker key |
| `X-Trace-Id` | Optional (AC1.7) | Echoed in response + log events; generated if absent |
| `Authorization` (mTLS cert) | YES (AC9.3) | Client cert check against `MTLS_TRUSTED_SUBJECT_CN` |

M11 rejects requests missing `X-Firm-ID` with HTTP 400 `errorCode="missing_firm_id"`.

### What M6 Does NOT Get From M11

- Canonical types — M6 invokes M7 at Stage 6.
- MNPI filtering — M4 at Stage 7, AFTER M7.
- Audit entries — M6 writes at Stage 9 via M10. M11 emits operational pino logs only.
- Retry across adapters — M6 does NOT retry a failed adapter against a different adapter.
- Tool-selection logic — M6 resolves tool names via its own registry, populated from `POST /tools/list` at cold start.

### Where M11 Diverges From M6's `VendorAdapterError` Shape

| Adapter `errorCode` | M6 `VendorAdapterError.kind` | M6 HTTP status to caller |
|---------------------|------------------------------|--------------------------|
| `vendor_circuit_open`, `adapter_timeout`, `mtls_degraded`, `vendor_ssrf_blocked` | `unavailable` | 503 |
| Everything else | `error` | as-is (or 502 for `vendor_error`) |

This mapping is M6's responsibility, documented here for M11 integrators.

---

## Integration Point with M7

M7 Schema Translators are a pure Python library that M6 calls at Stage 6 with the raw vendor dict M11 just returned. M11 does NOT import M7. Matches M7 spec v0.3.0 §Integration Point with M11 verbatim.

### Phase 2 Rule (lighthouse-1): M11 Returns Raw, M6 Calls M7

```
M11 adapter code paths do NOT import `m7_schema_translators`.
M11 adapter package.json does NOT depend on @project-007/m7-schema-translators.
M11 adapter tests do NOT import m7_schema_translators.
```

Enforced by AC12.6 (shared test `test_no_m7_import.ts`) + AC12.1 AST scan. Violating the rule breaks M10's audit chain because every translate call MUST produce an `AuditEntry` via M6's Stage 9, and a direct M11→M7 call would bypass that stage.

### What M11 Guarantees to M7 (Via M6)

1. `vendor_payload` is a Python dict (M6 deserialized M11's JSON response body's `result` field).
2. `vendor_payload` is the VERBATIM vendor JSON — M11 did not normalize field names, did not convert types, did not strip or add fields (eMoney strict-output rejection is the ONLY exception; when rejected, M7 never sees the payload).
3. `source_system` in M6's dispatch call matches M11's `vendor` header: SFDC tools → `"salesforce_fsc"`, Orion → `"orion"`, eMoney → `"emoney"`, Schwab → `"schwab"`.
4. `VENDOR_API_VERSION` cross-check — AC10.1.

### What M11 Does NOT Do

- No canonicalization (no `UUID` wrapping, no `cost_basis_method` assignment, no enum mapping).
- M11 returns raw tax-lot data for Schwab from both REST (Phase 2) and future SFTP sub-types. Reconciliation between those two feeds is M7's job, not M11's.
- No `ReconciliationNote` emission.
- No canonical-shape validation (M7 Pydantic `extra="forbid"` is defense-in-depth).
- No M4 MNPI filtering (M4 runs at Stage 7 AFTER M7).

### SFDC PascalCase vs M7 snake_case (v0.2.0 open gap)

**Confirmed gap** (verified against M7 `src/m7_schema_translators/salesforce_fsc/models.py` 2026-05-05). M7's `SalesforceFSCAccountContact` uses snake_case fields (`account_id`, `first_name`, `household_id`, `kyc_status`, `first_name`, etc.) with `extra="forbid"` and NO `populate_by_name`, NO `Field(alias=...)`. Real SFDC REST returns PascalCase keys (`Id`, `FirstName`, `FinServ__HouseholdId__c`, `FinServ__KYCStatus__c`). The adapter's "VERBATIM vendor JSON" passthrough hands M7 a payload M7 cannot ingest.

**M11's position:**
- M11 does NOT pre-normalize (contradicts R12 AC12.1).
- M11 documents the gap in §Known Blockers row 4 and Appendix E row 5.
- M7 owns the fix — either alias-map on `SalesforceFSCAccountContact` OR an alias-transformer layer in `client.py::to_canonical_client`.
- Integration-test gate: `tests/integration/test_m7_sfdc_shape.py` fires an actual SFDC-shaped fixture through M7 and must pass before the SFDC adapter reaches pre-prod. Until this gate passes, the SFDC adapter is flagged Integration-Blocker in §Known Blockers.

### Cross-Module Invariants Tested

- `tests/integration/test_m11_m7_version_match.py` — AC10.1.
- `tests/integration/test_m11_no_m7_import.ts` — AC12.6.
- `tests/integration/test_m6_error_propagation.py` — M6 captures M11 error body verbatim (AC16.2; lives in M6's Phase 2 amendment spec).
- **`tests/integration/test_m7_sfdc_shape.py` (v0.2.0)** — the SHARED-WITH-M7 PascalCase gap gate. Must pass before pre-prod deployment of SFDC adapter.
- **`tests/integration/test_m7_emoney_allowlist.py` (v0.2.0)** — asserts the eMoney Zod output allow-list (AC8.5) matches `EMoneyPlanSummary.model_fields.keys()` set equality. If M7 or M11 drifts, this test fails.

---

## Tasks

Tasks are numbered, ordered, atomic, depth-first per-adapter. Each task references the ACs it covers. Tests are written WITH implementation.

### Phase A — Shared SDK (Tasks 1-3)

**Task 1: Scaffold `@project-007/mcp-sdk` workspace package**

Create `src/m11_rest_adapters/shared/mcp-sdk/` with `package.json`, `tsconfig.json`, barrel `src/index.ts`. Declare npm workspace in repo root. Pin TypeScript 5.4, Node 20 (engines), Zod 3.23, fastify 4.x, pino 9.x, undici 6.x, `lru-cache` ^11, `fast-check` ^3 (devDep). Covers AC3.7, AC3.8, AC12.2.

**Task 2: Implement shared MCP server harness + types + errors + clock + logger + SSRF + LRU**

Build `src/types.ts` (MCP envelope + `AdapterConfig`), `src/server.ts` (`McpServer` class wrapping fastify with 3 routes), `src/logger.ts` (`getLogger` with pino + redact rules), `src/clock.ts` (`Clock` + `SystemClock` + `FakeClock`), `src/errors.ts` (`VALID_ADAPTER_ERROR_CODES` frozen set + error constructors + HTTP status mapper), `src/secrets.ts` (`SecretsClient` interface + stubs for Vault/AWS), **`src/ssrf.ts` (`validateVendorURL`, v0.2.0)**, **`src/lru.ts` (re-export `lru-cache`, v0.2.0)**. Covers R1 (AC1.1-1.8), R7 (AC7.1-7.2, AC7.5-7.6), R13 (AC13.2), R16 (AC16.3), R14 (AC14.10). Tests: `test_mcp_server.ts`, `test_error_codes.ts`, `test_logger_redact.ts`, `test_ssrf.ts`.

**Task 3: Write shared-SDK security + boundary tests (11 tests)**

Write all shared tests under `tests/`: `test_no_hardcoded_creds.ts`, `test_no_token_in_logs.ts`, `test_module_boundary.ts`, `test_package_allow_list.ts`, `test_env_example.ts`, `test_no_console.ts`, `test_forbidden_apis.ts`, `test_no_m7_import.ts`, `test_ssrf.ts`, placeholder for `test_m11_error_contract.ts` (filled in Task 18). Covers R4, R12, R14.

### Phase B — Salesforce FSC Adapter (Tasks 4-8)

**Task 4: Scaffold SFDC adapter package + Dockerfile**

Create `src/m11_rest_adapters/salesforce_fsc/` with `package.json` (`@project-007/m11-salesforce-fsc-adapter@0.1.0`), `tsconfig.json`, `Dockerfile` (multi-stage distroless), `.dockerignore`, `.env.example`. Covers R3, R11. Tests: `tests/startup.test.ts` env validation; Dockerfile lint in CI; image-size assertion per AC11.5.

**Task 5: SFDC OAuth JWT Bearer auth + LRU token cache + SSRF validation**

Build `src/auth.ts`: JWT assertion via `crypto.createSign("RSA-SHA256")`, POST to `/services/oauth2/token`, **cache in `LRUCache<string, CachedToken>({max: 1024})` (v0.2.0 AC4.14)**, proactive refresh, redaction. **Validate `instance_url` via `validateVendorURL` before first use (v0.2.0 AC14.10).** Covers R4, R14. Tests: `tests/auth.test.ts` with `FakeSecretsClient` + msw; LRU 1025-entry eviction test; SSRF test (FakeSecretsClient returns `instance_url: "http://169.254.169.254/"` → startup rejects).

**Task 6: SFDC client.ts + 5 tool implementations + Zod schemas + property tests**

Build `src/client.ts` (undici + circuit + retry + rate limit), `src/tools.ts` (frozen registry), `src/schemas.ts` (Zod input + output ETag capture per AC8.9). Covers R2, R8, AC8.9. Tests: `tests/client.test.ts` (one per tool with msw), `tests/zod.test.ts` (malformed rejected pre-vendor), **`tests/property.test.ts` fast-check for each of 5 tools (v0.2.0 AC18.6)**.

**Task 7: SFDC circuit + rate limiter + Retry-After edge cases + logging**

Build `src/circuit.ts`, `src/rate_limit.ts` (`TokenBucket` + `DailyBucket` for SFDC 100K/24h). **Retry-After parsing handles 5 edge cases per AC5.7: integer, HTTP-date, negative, HTTP-date > 300s (cap), malformed, absent. Test matrix in `tests/rate_limit.test.ts`.** Wire into `client.ts`. Emit pino events. Covers R5, R6, R7.

**Task 8: SFDC startup sequence + version check + integration tests + traceability**

Build `src/index.ts` + `src/startup.ts` implementing R17 sequence with SFDC `GET /services/data/` version check (AC10.2). Tests: `tests/integration.test.ts`. Write `SPEC-TRACEABILITY.md`. Covers R10, R17, R18.

### Phase C — Orion Adapter (Tasks 9-11)

**Task 9: Scaffold Orion adapter + OAuth client-credentials + Basic-auth stub**

Scaffold per Task 4 pattern. Build `src/auth.ts` for Orion client-credentials flow. **Phase 3 Basic-auth branch (v0.2.0 AC4.12): `auth.ts` reads `ORION_AUTH_MODE` at startup; `basic` branch loads `m11/orion/basic_credentials` → `{username, password}` and sets `Authorization: Basic` on every request. Both branches share `BaseAuthStrategy` interface. Basic branch test-covered (not mocked out).** Covers R3, R4 (AC4.12), R11.

**Task 10: Orion client + 4 tools + Zod schemas + property tests + circuit/rate/logging**

Build `client.ts`, 4 tools per §Design T-OR1-T-OR4, Zod schemas, property tests (AC18.6). Rate limit 60 RPM / burst 10. Covers R2 (AC2.2), R5, R6, R7, R8, R18.

**Task 11: Orion startup + path-verification probe + version-skip log + integration tests + traceability**

Orion has no version endpoint — log `vendor_version_check_skipped` per AC10.4 + first-call-success per AC10.5. **v0.2.0 PENDING-VERIFICATION path probe: at startup, issue a known-safe `GET` against the configured base path; 404 → log `orion.path_unverified` and mark adapter degraded.** Integration tests + SPEC-TRACEABILITY. Covers R10, R17, R18, AC2.11.

### Phase D — eMoney Adapter (Tasks 12-14)

**Task 12: Scaffold eMoney + OAuth client-credentials + scope enforcement**

Scaffold per pattern. Build `src/auth.ts` with MANDATORY scope check per Appendix C.3: reject token response granting wider scope than requested. Covers R3, R4, R11.

**Task 13: eMoney client + 1 tool + input Zod + STRICT output Zod aligned to M7**

Build `client.ts`, `tools.ts` (single tool `emoney.fetch_plan_summary`), `schemas.ts` with `EMoneyPlanSummaryInput` (UUID) AND `EMoneyPlanSummaryOutput` (**strict, allow-list matching M7's `EMoneyPlanSummary` v0.2.0 AC8.5**). On vendor response, invoke `EMoneyPlanSummaryOutput.safeParse`; on failure emit HTTP 502 `emoney_raw_plan_forbidden` per AC8.6. Covers R2 (AC2.3), R8 (AC8.5-8.6). Tests: `tests/zod.test.ts` with fixtures containing `rawPlanBody`, `scenariosDetail` → reject. **`tests/integration/test_m7_emoney_allowlist.py` asserts set-equality with `EMoneyPlanSummary.model_fields.keys()`** — prevents future drift.

**Task 14: eMoney circuit + rate limit + logging + integration + traceability**

Rate 1800 RPM / burst 30 (default per AC5.2 PENDING-VERIFICATION). Emit `emoney.raw_plan_rejected` with field NAMES only per AC8.6. Covers R5, R6, R7, R17, AC15.6 schema-drift log path.

### Phase E — Schwab Adapter (Tasks 15-17)

**Task 15: Scaffold Schwab adapter + OAuth refresh-token + Secrets writeback + narrow RBAC + CRITICAL alert**

Scaffold per pattern. Build `src/auth.ts` with refresh-token rotation per Appendix C.4 — adapter writes NEW RT back to Secrets via `SecretsClient.setSecret`. **v0.2.0 — on RT write failure emit `{event:"auth.schwab.rt_rotation_failed", severity:"CRITICAL"}` at pino `fatal` for M10 sidecar escalation (AC4.13). Adapter does NOT crash (access token still valid). §RBAC Template narrow Role + RoleBinding (`["get","update"]` on `m11-schwab-refresh-token` only).** Covers R3, R4 (AC4.7, AC4.13), R9 (AC9.7 exception), R11. Tests: `tests/auth.test.ts` forces `setSecret` to throw; assert log event shape + severity; assert RBAC manifest passes `kubeconform`.

**Task 16: Schwab client + 3 tools + Zod schemas + property tests + circuit/rate/logging**

Build `client.ts`, 3 read tools per §Design T-SC1-T-SC3, Zod, property tests. Rate 120 RPM / burst 20 (PENDING-VERIFICATION). **Explicitly NO `schwab.submit_trade` tool (v0.2.0 Phase 2 descope per IMPL-06 Blocker 1 — Appendix E row 24).** Covers R2 (AC2.4), R5, R6, R7, R8, R18.

**Task 17: Schwab startup + version check + integration tests + SIGTERM handling**

Schwab version check: `GET /trader/v1/userPreference` per AC10.3. Integration tests include RT rotation path (msw returns new RT; adapter writes to FakeSecretsClient). **SIGTERM during in-flight RT rotation: wait ≤ 10 s for completion before drain (AC17.3 v0.2.0).** Covers R10, R17, R18.

### Phase F — Cross-Adapter Integration (Tasks 18-21)

**Task 18: Cross-adapter error-contract test (`test_m11_error_contract.ts` v0.2.0 mechanism table)**

In `tests/integration/` write parameterized test iterating all 4 adapters, forcing each error class **via the exact mechanisms in AC16.4 table** (FakeClock for OAuth expiry, msw sequence for 5xx exhaustion, 5-response msw for circuit-open, missing-field payload for Zod, rawPlanBody fixture for eMoney, msw delay for timeout, broken JSON for invalid_json, FakeClock-bucket-exhaustion for rate_limit_exceeded, FakeSecretsClient `instance_url:"http://169.254.169.254/"` for SSRF, cert-file-rewrite for mtls_degraded, missing X-Firm-ID for missing_firm_id). Covers R16 (AC16.4).

**Task 19: Cross-module version-match test (`test_m11_m7_version_match.py`)**

Python pytest reads M7's per-translator `VENDOR_API_VERSION` via `importlib` and the adapter's exported const; asserts equality (4 assertions). Covers R10 (AC10.1).

**Task 20: Cross-module no-M7-import + SFDC shape + eMoney allow-list tests**

AST-scan all 4 adapter packages + shared SDK for any reference to `m7_schema_translators` — zero occurrences (AC12.6). **v0.2.0 `test_m7_sfdc_shape.py` asserts M7 can ingest a PascalCase SFDC fixture (currently FAILS — documents the SHARED-WITH-M7 gap and gates pre-prod).** **v0.2.0 `test_m7_emoney_allowlist.py` asserts M11 Zod allow-list is set-equal to M7 `EMoneyPlanSummary` fields.** Covers R12 (AC12.6), §Known Blockers row 4, AC8.5.

**Task 21: Helm chart skeleton + NetworkPolicy + Certificate + RBAC templates + resource limits**

Add `charts/m11-rest-adapters/` with sub-charts for 4 adapters. Shared templates: `networkpolicy.yaml`, `certificate.yaml`, `deployment.yaml` (**v0.2.0 resources.requests/limits + ADAPTER_UNDICI_CONNECTIONS env**), `service.yaml`, `serviceaccount.yaml`, **`role.yaml` + `rolebinding.yaml`** (default + Schwab narrow-write variant). Values matrix: `values-cloud.yaml`, `values-hybrid.yaml`, `values-onprem.yaml`. Tested via `helm template` + `kubeconform` in CI. Covers R9, §RBAC Template, §Deployment Notes, AC3.9, AC3.10.

### Phase G — Documentation + Final Gates (Tasks 22-23)

**Task 22: DECISION-LOG population + SPEC-TRACEABILITY rollup + schema-drift playbook**

Populate `src/m11_rest_adapters/DECISION-LOG.md` with entries per AC15.1-15.6 (rate-limit sources with real URLs or PENDING markers, SFDC field-name PENDING mirror, eMoney raw-plan DENY list source, Schwab trade-submission descope per Appendix E row 24, SEC EDGAR M8-cross-reference per row 22, vendor-schema-drift playbook entry per AC15.6). **v0.2.0 — create `src/m11_rest_adapters/docs/vendor-schema-drift-playbook.md` with the 48h-SLA workflow from AC15.6.** Per-adapter `SPEC-TRACEABILITY.md` verified against all 18 requirements. Covers R15, R18 (AC18.5).

**Task 23: End-to-end lighthouse dress rehearsal + chaos scenarios + latency targets**

Run all 4 adapters in docker-compose against a mock M6 exercising the RIA meeting-prep journey: SFDC fetch_client (captures ETag) + fetch_household → Orion fetch_holdings + fetch_taxlots → eMoney fetch_plan_summary → SFDC create_interaction_summary (with ETag). Assert:

- All adapter responses conform to AC1.3 shape.
- Zero credentials in captured log stream (re-run AC7.7).
- eMoney raw-plan rejection path exercised at least once (fixture with `rawPlanBody`).
- Circuit breaker exercised under simulated vendor outage (msw 503 × 6 → OPEN).
- Rate limiter exercised — 50 concurrent SFDC calls with `burst=10` → first 10 pass, rest 429.
- mTLS cert reload exercised — rewrite cert file mid-run, assert `GET /` stays 200.
- **Latency targets met (v0.2.0 AC1.5): p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms per tool call (adapter-side, excluding vendor latency).** 200 calls per tool.
- **Chaos scenarios (v0.2.0 recommended fix R3):**
  - **Secrets backend 500 for 30 s** (FakeSecretsClient `getSecret` throws 500) → adapters emit `secrets_bootstrap_failed` on fresh startups; running adapters continue with cached tokens; degrade gracefully.
  - **DNS failure for 10 s** (msw intercepts with `ERR_DNS`) → retry wrapper retries 3× with backoff; circuit breaker eventually opens; recovery clean.
  - **Vendor TLS-handshake hang 15 s** (msw `delay(15_000)` on TLS) → undici timeout fires; adapter returns `vendor_timeout`; no pod crash.
- **fast-check property matrix green in < 60 s wall-clock** per §fast-check Strategy Approach.

---

## Appendix A — Tool × Adapter Matrix (Summary)

| # | Tool | Adapter | Vendor Endpoint (primary) | M7 Translator Target | Phase 2 AC Coverage |
|---|------|---------|---------------------------|----------------------|---------------------|
| 1 | `sfdc.fetch_client` | salesforce_fsc | SOQL on `Account` via `GET /services/data/v59.0/query/` | `(salesforce_fsc, Client)` | R2 AC2.1, §T-SF1, Task 6 |
| 2 | `sfdc.fetch_household` | salesforce_fsc | SOQL on `FinServ__Household__c` | `(salesforce_fsc, Household)` | §T-SF2, Task 6 |
| 3 | `sfdc.fetch_goal` | salesforce_fsc | SOQL on `FinServ__FinancialGoal__c` | `(salesforce_fsc, Goal)` | §T-SF3, Task 6 |
| 4 | `sfdc.update_client` | salesforce_fsc | `PATCH /services/data/v59.0/sobjects/Account/{id}` + `If-Match` (v0.2.0) | none (writeback) | §T-SF4, Task 6, AC8.9 |
| 5 | `sfdc.create_interaction_summary` | salesforce_fsc | `POST /services/data/v59.0/sobjects/FinServ__Interaction__c` + `If-Match` (v0.2.0) | none (writeback) | §T-SF5, Task 6, AC8.9 |
| 6 | `orion.fetch_holdings` | orion | `GET /api/v2.0/portfolio/accounts/{id}/positions` **PENDING-VERIFICATION** | `(orion, Holding)` | R2 AC2.2, AC2.11, §T-OR1, Task 10 |
| 7 | `orion.fetch_transactions` | orion | `GET /api/v2.0/portfolio/accounts/{id}/transactions` **PENDING-VERIFICATION** | `(orion, Transaction)` | §T-OR2, Task 10 |
| 8 | `orion.fetch_household` | orion | `GET /api/v2.0/portfolio/households/{id}` **PENDING-VERIFICATION** | `(orion, Household)` | §T-OR3, Task 10 |
| 9 | `orion.fetch_taxlots` | orion | `GET /api/v2.0/portfolio/accounts/{id}/taxlots` **PENDING-VERIFICATION** | `(orion, TaxLot)` | §T-OR4, Task 10 |
| 10 | `emoney.fetch_plan_summary` | emoney | `GET /api/v2/plans/{id}/summary` | `(emoney, PlanSummary)` | R2 AC2.3, R8 AC8.5-8.6, §T-EM1, Task 13 |
| 11 | `schwab.fetch_positions` | schwab | `GET /trader/v1/accounts/{num}?fields=positions` | `(schwab, Holding)` | R2 AC2.4, §T-SC1, Task 16 |
| 12 | `schwab.fetch_taxlots` | schwab | `GET /trader/v1/accounts/{num}/taxlots` | `(schwab, TaxLot)` | §T-SC2, Task 16 |
| 13 | `schwab.fetch_master_account` | schwab | `GET /trader/v1/masterAccounts/{id}` | `(schwab, Household)` | §T-SC3, Task 16 |
| — | `schwab.submit_trade` (Phase 3 — NOT in v0.2.0) | — | — | — | **Descoped** per Appendix E row 24 |

**Totals:** 4 adapters, 13 read tools + 2 writeback tools = **14 tools**. Every read tool has a matching M7 translator pair registered in M7's `TRANSLATOR_REGISTRY` (11 pairs; writebacks are M11-only).

---

## Appendix B — Spec Coverage Verification Checklist

| Spec Area | Count | Verified By |
|-----------|-------|-------------|
| Numbered requirements | **18** (R1-R18) | §Requirements TOC |
| Total acceptance criteria | **147** (v0.2.0 — up from 133 in v0.1.0; new ACs: 2.11, 3.9, 3.10, 4.12, 4.13, 4.14, 5.9, 8.9, 14.10, 15.6, 18.6, plus expansions) | Count below |
| Tasks | **23** (Tasks 1-23) | §Tasks |
| Adapters | **4** | §Phase 2 Lighthouse Scope |
| Tools | **14** | Appendix A |
| Mandatory steering rules addressed | **8** (10, 20-26) | §Steering Rules M11-REST Must Honor |
| mTLS rotation window | 24 h | R9 AC9.2 |
| Image size cap (measured) | 150 MiB (observed ~130 MiB) | R11 AC11.5 |
| Rate-limit sources | vendor-doc URLs OR PENDING-VERIFICATION (v0.2.0 — no fabricated citations) | R5 AC5.2 |
| eMoney raw-plan rejection | SUMMARY-only, allow-list matches M7 Pydantic | R8 AC8.5-8.6 |
| Dual-caller audit-bypass contract | M11 does NOT import M7 | R12 AC12.6, §Integration Point with M7 |
| Closed errorCode vocabulary | 22 codes (v0.2.0 adds `vendor_ssrf_blocked`) | R16 AC16.3 |

### AC Count Per Requirement

| Req | # ACs v0.1.0 | # ACs v0.2.0 | Req | # ACs v0.1.0 | # ACs v0.2.0 | Req | # ACs v0.1.0 | # ACs v0.2.0 |
|-----|---|---|-----|---|---|-----|---|---|
| R1  | 8 | 8 | R7  | 8 | 9 | R13 | 5 | 5 |
| R2  | 10 | 11 | R8  | 8 | 9 | R14 | 9 | 10 |
| R3  | 8 | 10 | R9  | 9 | 9 | R15 | 5 | 6 |
| R4  | 11 | 14 | R10 | 6 | 6 | R16 | 4 | 4 |
| R5  | 8 | 9 | R11 | 9 | 9 | R17 | 4 | 4 |
| R6  | 10 | 10 | R12 | 6 | 6 | R18 | 5 | 6 |

Total = **147 ACs** across 18 requirements (v0.2.0), up from 133 in v0.1.0.

---

## Appendix C — Worked OAuth Flow Sequences

### C.1 Salesforce FSC — JWT Bearer + SSRF Validation (v0.2.0)

```
1. Startup: adapter → SecretsClient.getJSONSecret("m11/salesforce_fsc/oauth_credentials")
   returns {clientId, username, privateKeyPEM, loginUrl}

2. Build JWT assertion (RS256) via crypto.createSign.
   header  = {"alg":"RS256","typ":"JWT"}
   payload = {"iss":clientId,"sub":username,"aud":loginUrl,"exp":now+300}

3. POST {loginUrl}/services/oauth2/token
     grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer&assertion={assertion}

4. Response: {access_token, scope, instance_url, token_type:"Bearer"}

5. SSRF validation (v0.2.0 AC14.10):
   validateVendorURL(response.instance_url, egressAllowlist) or throw.
   - https: only; host matches allow-list; DNS resolve; reject RFC1918/link-local/loopback/ULA.
   Reject → exit with auth.sfdc.ssrf_blocked OR mid-request 502 vendor_ssrf_blocked.

6. Cache in LRUCache({max:1024}): CachedToken{accessToken, expiresAt=now+7200s, instanceUrl}.

7. Tool call uses instance_url as base (NOT loginUrl).
   Capture response ETag → expose as _etag sibling (AC8.9 writeback idempotency).

8. On 401: invalidate, retry steps 2-5, second 401 → HTTP 401 to M6.
```

Log events (token redacted): `auth.sfdc.jwt_assertion_built`, `auth.sfdc.ssrf_check_passed`, `auth.sfdc.token_acquired`, `auth.sfdc.refresh_proactive`, `auth.sfdc.token_invalidated`.

### C.2 Orion — OAuth (Phase 2) + Basic Auth (Phase 3 v0.2.0)

**Phase 2 default (ORION_AUTH_MODE=oauth):**

```
1. SecretsClient.getJSONSecret("m11/orion/oauth_credentials") → {clientId, clientSecret, tokenUrl}
2. POST {tokenUrl} with Basic auth + grant_type=client_credentials
3. Response: {access_token, expires_in:3600}. Cache in LRU 1024.
4. Tool calls: Authorization: Bearer {access_token}
5. On 401: invalidate, re-run step 2, retry ONCE.
```

**Phase 3 flip (v0.2.0 AC4.12 — concrete toggle):**

```
Helm values-{topology}.yaml:
  m11:
    orion:
      authMode: basic    # flips ORION_AUTH_MODE=basic; REQUIRES POD REDEPLOY (not hot-reload)

Secret path change:
  m11/orion/oauth_credentials  →  m11/orion/basic_credentials  →  {username, password}

Startup:
  if ORION_AUTH_MODE == "basic":
    creds = SecretsClient.getJSONSecret("m11/orion/basic_credentials")
    auth = BasicAuthStrategy(creds.username, creds.password)
    # No token exchange; no expiresAt; no refresh.

Tool calls:
  Authorization: Basic base64(username:password)

Password rotation: update Secret → redeploy pod.
```

`GET /` reports `{"auth_mode": "oauth"|"basic"}`. Rate-limit + circuit-breaker identical.

### C.3 eMoney — OAuth + Strict Scope Enforcement

```
1. SecretsClient.getJSONSecret("m11/emoney/oauth_credentials")
   → {clientId, clientSecret, tokenUrl, scope="plan_summary:read"}
2. POST {tokenUrl} with client-credentials + scope
3. Response.scope MUST equal requested:
   if (response.scope !== requestedScope) {
     logger.fatal({event:"auth.emoney.scope_violation", requested, granted});
     process.exit(3);
   }
4. Tool call: GET /api/v2/plans/{planId}/summary?includeGoals=true with Bearer.
5. Response parse:
   EMoneyPlanSummaryOutput.safeParse(body);
   if (!result.success) {
     logger.warn({event:"emoney.raw_plan_rejected",
                 field_names: result.error.issues
                   .filter(i => i.code === "unrecognized_keys")
                   .flatMap(i => i.keys)});
     return HTTP 502 errorCode="emoney_raw_plan_forbidden";
   }
```

### C.4 Schwab — RT Rotation + CRITICAL Alert (v0.2.0)

```
Out-of-band (once per firm): advisor consent → initial RT stored in m11/schwab/refresh_token.

Startup:
1. rt_current = SecretsClient.getSecret("m11/schwab/refresh_token")
   creds = SecretsClient.getJSONSecret("m11/schwab/oauth_credentials")

2. POST https://api.schwabapi.com/v1/oauth/token
     Basic auth; grant_type=refresh_token&refresh_token={rt_current}

3. Response (RT ROTATES):
   {access_token (30min), refresh_token (NEW 7-day), expires_in:1800, scope:"api"}

4. Persist NEW RT (v0.2.0 CRITICAL alert on failure):
   try {
     await secretsClient.setSecret("m11/schwab/refresh_token", response.refresh_token);
     logger.info({event:"auth.schwab.rt_rotated", firm_id});
   } catch (err) {
     logger.fatal({
       event: "auth.schwab.rt_rotation_failed",
       severity: "CRITICAL",                              # v0.2.0 AC4.13
       firm_id, adapter:"schwab",
       retry_count: err.retryCount || 0,
       reason: err.code || "unknown"
     });
     # M10 sidecar → PagerDuty/OpsGenie within 5 min.
     # Adapter does NOT crash — access token still valid ~30 min.
     healthState.oauth = "degraded";   # GET / returns 503 next probe.
   }

5. Cache access_token (LRU 1024) with expiresAt = now + 1800s.

Failure modes:
  - 400 invalid_grant → RT expired/revoked → exit 3, log auth.schwab.rt_invalid_grant.
    Operator re-runs out-of-band consent.
  - 401 on tool call → invalidate access_token, rerun steps 2-4, retry ONCE.
  - SIGTERM during step 4: wait ≤ 10s for setSecret to finish before drain (AC17.3 v0.2.0).
```

RBAC: Schwab ServiceAccount has `["get","update"]` on `m11-schwab-refresh-token` ONLY.

---

## Appendix D — Worked Tool Call Scenarios

### D.1 Successful Call — `orion.fetch_holdings`

```
Request:
   POST https://m11-orion.acme-m11-orion.svc.cluster.local:8080/tools/call
   Content-Type: application/json
   X-Firm-ID: acme
   X-Trace-Id: 9f2e4c1b-8a3d-4f16-b9c7-1e2d3f4a5b6c
   (mTLS client cert CN=m6-mcp-gateway.acme-m6.svc.cluster.local)
   body: {"name":"orion.fetch_holdings", "arguments":{"accountId":12345, "asOfDate":"2026-04-28"}}

Adapter pipeline:
  1. Fastify parse body (< 1 MiB).
  2. X-Firm-ID → firm_id="acme".
  3. Rate limiter tryAcquire("acme:orion") → {ok:true}.
  4. Circuit state("acme:orion") → CLOSED.
  5. Tool lookup → found.
  6. Zod parse → valid.
  7. Auth: cached token (48m remaining).
  8. Log mcp.tool_call.start.
  9. undici.fetch via shared Agent (connections:10) →
     GET https://api.orionadvisor.com/api/v2.0/portfolio/accounts/12345/positions?asOfDate=2026-04-28
 10. Vendor HTTP 200, 23 KiB, 7 positions.
 11. JSON.parse → positions array.
 12. Log mcp.tool_call.end {status_code:200, duration_ms:182, retry_count:0, circuit_state:"CLOSED"}.
 13. Circuit.recordSuccess → consecutive_failures = 0.

Response (182 ms < p95 target 1000 ms):
   HTTP 200
   body: {"result":{"positions":[...],"asOfDate":"2026-04-28"}, "error":null}
```

M6 Stage 6 calls `m7_schema_translators.translate_to_canonical("orion", "Holding", position_dict)`.

### D.2 Zod Input Rejection — `sfdc.fetch_client`

```
Request: body: {"name":"sfdc.fetch_client", "arguments":{"clientId":"not-a-valid-id"}}

Pipeline:
  1-5. Normal up to tool lookup.
  6. Zod fails regex /^[a-zA-Z0-9]{15,18}$/.
  7. Log mcp.tool_call.invalid_args with error_path:"arguments.clientId".
  8. HTTP 400 — NO vendor call, NO rate-limit consumed.

Response:
   HTTP 400
   body: {"result":null,
          "error":{"code":"invalid_arguments",
                   "message":"arguments.clientId: expected string matching /^[a-zA-Z0-9]{15,18}$/",
                   "vendorStatusCode":null, "retryable":false}}
```

Path-only error per AC8.4 — user-supplied value NEVER echoed.

### D.3 eMoney Raw-Plan Rejection (v0.2.0 — M7-aligned allow-list)

```
Request: body: {"name":"emoney.fetch_plan_summary",
                "arguments":{"planId":"550e8400-e29b-41d4-a716-446655440000"}}

Pipeline:
  1-7. Normal up to vendor call.
  8. GET /api/v2/plans/550e8400.../summary?includeGoals=true
  9. Vendor HTTP 200, body:
     {"planId":"550e8400-...", "clientId":"...", "planName":"Retirement v3",
      "probabilityOfSuccess":78.5, "asOfDate":"2026-04-28",
      "createdAt":"2025-01-15T00:00:00Z", "updatedAt":"2026-04-01T00:00:00Z",
      "totalAssets":1250000, "totalLiabilities":180000,
      "goalIds":["g-1","g-2"],
      "scenariosDetail":{...},       <-- FORBIDDEN
      "rawPlanBody":"<huge tree>"    <-- FORBIDDEN
     }
 10. EMoneyPlanSummaryOutput.safeParse(body) → success:false,
     issues:[{path:[], code:"unrecognized_keys", keys:["scenariosDetail","rawPlanBody"]}]
 11. Log emoney.raw_plan_rejected with field_names only (NEVER values).
 12. HTTP 502.

Response:
   HTTP 502
   body: {"result":null,
          "error":{"code":"emoney_raw_plan_forbidden",
                   "message":"eMoney response contained non-summary fields; adapter configured SUMMARY-only",
                   "vendorStatusCode":200, "retryable":false}}
```

Raw plan body NEVER reaches M6, M7, M4, or the LLM. M10 sidecar forwards WARN to Compliance queue per AC15.6.

### D.4 Circuit Breaker Open — `schwab.fetch_positions`

```
Pipeline:
  1-5. Parse, rate-limit OK, tool lookup.
  6. Circuit.state("acme:schwab") → OPEN (reset_at = now+20000ms).
  7. Log mcp.tool_call.circuit_open_rejected with reset_at.
  8. HTTP 503 — NO vendor call.

Response:
   HTTP 503
   body: {"result":null,
          "error":{"code":"vendor_circuit_open",
                   "message":"circuit breaker open for schwab; retry after 2026-04-28T13:45:12Z",
                   "vendorStatusCode":null, "retryable":true}}
```

M6 maps to `VendorAdapterError(kind="unavailable")`.

### D.5 Vendor 429 + Retry-After Edge Cases (v0.2.0)

```
Pipeline:
  1-8. Normal vendor call issued.
  9. Vendor HTTP 429, Retry-After: 45.
 10. Parse per AC5.7: integer 45 → use 45 s.
 11. Pause "acme:orion" bucket for max(45, 30) = 45 s.
 12. Circuit.recordFailure.
 13. Log rate_limit_vendor_429.
 14. HTTP 429 + Retry-After: 45.
```

**Edge cases (AC5.7):**
- `Retry-After: -5` → 0, default 30 s.
- `Retry-After: Thu, 28 May 2026 00:00:00 GMT` (30d future) → cap **300 s**.
- `Retry-After: garbage` → default 30 s, log raw_value_length only.
- Absent → 30 s.
- `Retry-After: 0` → minimum 1 s.

### D.6 Retry Exhaustion — `sfdc.fetch_client`

```
Pipeline:
  9. Vendor 503 (attempt 1). Backoff ~85 ms.
 10. Vendor 503 (attempt 2). Backoff ~215 ms.
 11. Vendor 503 (attempt 3). Backoff ~390 ms.
 12. VendorCallError(vendor_5xx_exhausted).
 13. consecutive_failures += 3; threshold 5 → may trip OPEN.
 14. Log mcp.tool_call.end {status_code:502, vendor_status_code:503, retry_count:3}.

Response:
   HTTP 502
   body: {"result":null,
          "error":{"code":"vendor_error",
                   "message":"salesforce_fsc returned 503 after 3 retries",
                   "vendorStatusCode":503, "retryable":true}}
```

### D.7 SSRF Block (v0.2.0)

```
Startup step 4 OAuth response:
  {"access_token":"...", "instance_url":"http://169.254.169.254/latest/meta-data/", ...}

Step 5 SSRF validation:
  - Protocol "http:" → FAIL (https only).
  - Would-also-fail: IP ∈ 169.254/16 link-local.

Action:
  Log auth.sfdc.ssrf_blocked {firm_id, url_host:"169.254.169.254", resolved_ip_class:"link_local"}.
  process.exit(3).

M10 sidecar: CRITICAL → PagerDuty within 5 min.
Operator investigation: possible SFDC credential compromise OR misconfigured redirect.
```

### D.8 SFDC Writeback Idempotency (v0.2.0)

```
M6 issues sfdc.fetch_client first → adapter returns _etag sibling:
   {"result":{"Id":"001A...", "Name":"Jane Doe", ..., "_etag":"\"W/\\\"3-abc123\\\"\""},
    "error":null}

M6 invokes sfdc.update_client with ETag:
   body: {"name":"sfdc.update_client",
          "arguments":{"clientId":"001A...",
                       "ifMatch":"\"W/\\\"3-abc123\\\"\"",
                       "fields":{"FinServ__Status__c":"Inactive"}}}

Adapter:
  9. PATCH /services/data/v59.0/sobjects/Account/001A...
       If-Match: "W/\"3-abc123\""
       body: {"FinServ__Status__c":"Inactive"}
 10. SFDC HTTP 412 Precondition Failed.
 11. Adapter HTTP 409 vendor_conflict.

Response:
   HTTP 409
   body: {"result":null,
          "error":{"code":"vendor_conflict",
                   "message":"sfdc ETag mismatch — re-fetch and retry",
                   "vendorStatusCode":412, "retryable":false}}

M6 behavior (per M6 Phase 2 amendment):
  - On 409: re-invoke sfdc.fetch_client → extract new _etag.
  - Retry sfdc.update_client ONCE with new ifMatch.
  - Second 409 → bubble to caller; human intervention required.
```

Non-retryable at adapter boundary prevents naive retry loops; no double-writes.

---

## Appendix E — DECISION-LOG Seed Entries (Phase 2 Initial Population)

Populate `src/m11_rest_adapters/DECISION-LOG.md` at build time. Task 22 finalizes; Appendix E is the seed set. **v0.2.0 rewrite fixes citations per review Required Fix #1 + adds new entries per required fixes #5, #13, #16, #17.**

| # | Date | Vendor | Tool / Area | Decision | Rationale | Decided By |
|---|------|--------|-------------|----------|-----------|------------|
| 1 | 2026-05-05 | SFDC | rate_limit | 100K/24h → RPM=4166, burst=200 | **Source:** Salesforce Platform API Limits Cheatsheet — "API Call Maximum (24-hour period)" for Enterprise Edition = 100K per connected app, documented at `https://developer.salesforce.com/docs/atlas.en-us.salesforce_app_limits_cheatsheet.meta/salesforce_app_limits_cheatsheet/`. Adapter-side budget is defensive (SFDC enforces org-wide). | Adapter Spec v0.2.0 |
| 2 | 2026-05-05 | Orion | rate_limit | 60 RPM, burst=10 (default) | **PENDING-VERIFICATION** — Orion developer portal (`developer.orionadvisor.com`) is login-gated. RES-08 §3.1 notes "paginated, rate-limited" without publishing a number. Value is a conservative default from 006 archived usage patterns. Verification gate: Task 11 first-call probe + Orion support-email confirmation before pre-prod. Override via Helm `m11.orion.rateLimitRpm`. | Adapter Spec v0.2.0 (PENDING-VERIFICATION) |
| 3 | 2026-05-05 | eMoney | rate_limit | 30 req/s (1800 RPM), burst=30 (default) | **PENDING-VERIFICATION** — eMoney API reference is behind the Fidelity partner portal. Value is a conservative default from sandbox-era documentation screenshots captured by 006 predecessor. Verification gate: post-partnership API reference review. Override via Helm `m11.emoney.rateLimitRpm`. | Adapter Spec v0.2.0 (PENDING-VERIFICATION) |
| 4 | 2026-05-05 | Schwab | rate_limit | 120 RPM, burst=20 (sandbox default) | **PENDING-VERIFICATION** — Schwab Developer Portal (`developer.schwab.com`) rate-limit page is gated by vendor-approval NDA. RES-08 §2.1 describes approval process but publishes no number. Value is a sandbox-observed default; production may differ post-approval. Override via Helm `m11.schwab.rateLimitRpm`. | Adapter Spec v0.2.0 (PENDING-VERIFICATION) |
| 5 | 2026-05-05 | SFDC | **SHARED-WITH-M7 — PascalCase vs snake_case** (v0.2.0 NEW) | Document M7-side gap; M11 does NOT pre-normalize | Verified against `src/m7_schema_translators/salesforce_fsc/models.py` 2026-05-05: `SalesforceFSCAccountContact` uses snake_case with `extra="forbid"` and no aliases; SFDC returns PascalCase. Gap is M7's to resolve (add `populate_by_name=True` + `Field(alias=...)` OR alias-transformer helper). M11 passthrough contract (R12) precludes M11-side transformation. Integration test `tests/integration/test_m7_sfdc_shape.py` gates pre-prod deployment. | Adapter Spec v0.2.0 + M7 spec owner (SHARED-WITH-M7 — M7 to close in v0.3.1+) |
| 6 | 2026-05-05 | eMoney | raw-plan allow-list (v0.2.0 — aligned to M7) | AC8.5 allow-list set-equal to `EMoneyPlanSummary.model_fields` in `src/m7_schema_translators/emoney/models.py` | Required: planId, clientId, planName, probabilityOfSuccess, asOfDate, createdAt, updatedAt. Optional: scenarioId, householdId, planType, totalAssets, totalLiabilities, retirementGoal, monteCarlo, annualSavingsRate, annualSpending, socialSecurityEstimate, pensionIncome, goalIds, assumptions, recommendations. Forbidden (reject with `emoney_raw_plan_forbidden`): scenariosDetail, cashflowProjection, assumptionsDetail, rawPlanBody, advisorNotes, clientBalanceSheet, insuranceDetails, taxProjections, estateDetails, monteCarloFullPath, and any other top-level key. `extra="forbid"` on M7 side enforces symmetry. | Adapter Spec v0.2.0 + Compliance SME (pending review) |
| 7 | 2026-05-05 | Schwab | refresh-token rotation | Schwab rotates RT on every use; adapter writes NEW RT back to Secrets. Rotation failure = **CRITICAL alert via M10 sidecar → PagerDuty within 5 min** (v0.2.0 AC4.13). | Schwab Trader API OAuth 2.0 RFC 6749 §6. RT theft has one-call window. Rotation failure is silent outage (~30 min later next refresh fails) — closes with explicit alert path. | Adapter Spec v0.2.0 |
| 8 | 2026-05-05 | Orion | OAuth vs Basic (v0.2.0 concrete Phase 3 toggle) | Phase 2 = OAuth. Phase 3 = Basic via `ORION_AUTH_MODE=basic` **Helm values toggle requiring pod redeploy**. Separate Secret path `m11/orion/basic_credentials`. | Not hot-reloadable — Secret path change + Deployment env change both require pod restart. Concrete auth-branch code landed in v0.2.0 Task 9 (Basic branch test-covered). | Adapter Spec v0.2.0 |
| 9 | 2026-05-05 | All | sandbox vs production | Phase 2 lighthouse uses sandboxes (Schwab + eMoney) | Schwab developer-program approval (6-8 wk) and eMoney partnership (6-12 mo) are operational gates, not code gates. Code is production-shaped. | Adapter Spec |
| 10 | 2026-05-05 | All | mTLS rotation window | 24 hours | Steering Rule 21. Balances rotation frequency with cert-manager / K8s load. | Steering Rule 21 |
| 11 | 2026-05-05 | All | circuit threshold | 5 consecutive failures OR > 50% rate over rolling 60s with ≥ 10 calls | Industry norm. Short enough to protect, long enough to absorb transients. | Adapter Spec |
| 12 | 2026-05-05 | All | image size cap (measured — v0.2.0) | 150 MiB cap; observed ~130 MiB | Distroless base ~80 MiB + `node_modules` ~40 MiB + `dist/` ~10 MiB. 20 MiB buffer. | Adapter Spec v0.2.0 |
| 13 | 2026-05-05 | All | latency targets (v0.2.0 NEW) | p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms per tool call (adapter-side only) | Task 23 enforces at 200-call sample. Feeds M6's circuit-breaker reset-timer calibration. | Adapter Spec v0.2.0 |
| 14 | 2026-05-05 | All | concurrency (v0.2.0 NEW) | `undici.Agent({connections: 10})` shared across the process | Balances vendor-TCP efficiency with single-replica pod blast radius. Override via `ADAPTER_UNDICI_CONNECTIONS` (1-64). | Adapter Spec v0.2.0 |
| 15 | 2026-05-05 | All | K8s resources (v0.2.0 NEW) | `requests: {cpu: 100m, memory: 256Mi}` / `limits: {cpu: 500m, memory: 512Mi}`. 1 replica Phase 2; HPA Phase 3. | Baseline matches Node `--max-old-space-size=512`. Single-replica Phase 2 avoids distributed-state in token cache + circuit breaker. | Adapter Spec v0.2.0 |
| 16 | 2026-05-05 | All | M7 non-import rule | M11 package.json MUST NOT depend on `@project-007/m7-schema-translators` | M7 v0.3.0 §Integration Point with M11 audit-bypass prevention. Preserves M10 audit chain. | M7 spec v0.3.0 |
| 17 | 2026-05-05 | SFDC | update_client writable allow-list | Only `FinServ__Status__c`, `FinServ__ClientArchetype__c`, `FinServ__RiskToleranceUpdatedDate__c`, `Description` writable via adapter | PII fields (name, email, phone, SSN, DOB, tax ID) via service-account would bypass SFDC native PII-change audit. Stay in SFDC UI. | Adapter Spec + Compliance SME |
| 18 | 2026-05-05 | SFDC | writeback idempotency (v0.2.0 NEW) | `If-Match` header with record ETag (captured from prior fetch). 412 → `vendor_conflict`. | SFDC REST does not support client-generated idempotency keys. ETag is SFDC's canonical concurrency primitive. M6 re-fetches + retries once on 409. | Adapter Spec v0.2.0 |
| 19 | 2026-05-05 | All | per-firm rate-limit key | `X-Firm-ID` header required | Multi-tenant isolation per Steering Rule 23. LRU 1024 per AC5.4. | Adapter Spec |
| 20 | 2026-05-05 | All | no M11→M10 direct writes | M10 audit is M6's job at Stage 9 | M11 emits operational pino logs only. Sidecar forwards CRITICAL events to M10 aggregator; M10 is not called directly (Steering Rule 33 — no cross-module imports). | Steering Rule 33 / M10 Spec |
| 21 | 2026-05-05 | Orion | URL paths (v0.2.0 NEW) | `/api/v2.0/portfolio/accounts/...` marked **PENDING-VERIFICATION** | Archived 007 code used `/api/v1`. Live Orion portal requires login. Verification gate: first-call probe at Task 11 startup (`orion.path_unverified` log event on 404). | Adapter Spec v0.2.0 (PENDING-VERIFICATION) |
| 22 | 2026-05-05 | SEC EDGAR | phase assignment (v0.2.0 NEW) | **DEFERRED from M11-REST Phase 2 lighthouse** — owned by M8 Research Pipeline as data source (not the RIA meeting-prep journey) | ARCH-09 lists EDGAR as Phase 1 (free API, 10 req/s, no vendor approval). But the Phase 2 M11-REST lighthouse scope is the RIA meeting-prep journey (4 vendors: SFDC + Orion + eMoney + Schwab). EDGAR 10-K/10-Q/8-K ingestion is an M8 Research Pipeline concern. EDGAR adapter is built in the M8 build window (Phase 2 later-wave) once the M8 spec exists. Not a regression — a scope-alignment decision. | Adapter Spec v0.2.0 + Project 007 Design |
| 23 | 2026-05-05 | Alpha Vantage + News API | phase assignment (v0.2.0 NEW) | **DEFERRED** — gated by M8 Research Pipeline spec (not yet written) | ARCH-09 Phase 2 both. M11-REST cannot build against M8's consumption contract without the M8 spec. Defer until M8 spec exists. | Adapter Spec v0.2.0 |
| 24 | 2026-05-05 | Schwab | **trade submission descope** (v0.2.0 NEW) | **M11-REST Phase 2 is READ-ONLY** — no `schwab.submit_trade` tool | ARCH-09 Phase 2 Schwab row says "Positions, balances, trade submission". IMPL-06 Blocker 1 defers execution to Phase 3 (Principal Review + FINRA 2210 + execution order state machine + HITL approval token + 24h auto-cancel). Trade submission needs all of these; Phase 2 has none. Deliberate descope for the RIA lighthouse. Phase 3 adds `schwab.submit_trade`, `schwab.cancel_order`, `schwab.replace_order` as a new adapter spec. | Adapter Spec v0.2.0 + IMPL-06 Blocker 1 |
| 25 | 2026-05-05 | All | schema-drift process (v0.2.0 NEW) | Field NAME logged → Compliance SME review 48h → if safe-summary, allow-list + MINOR bump + deploy | Enforces fail-closed on unknown fields (eMoney). Prevents MNPI leakage via accidental allow-listing. Playbook at `src/m11_rest_adapters/docs/vendor-schema-drift-playbook.md`. | Adapter Spec v0.2.0 |
| 26 | 2026-05-05 | eMoney | scope enforcement | Reject any token granting scope > requested | "scope creep" = security regression. Fail startup if eMoney grants wider scope. | Adapter Spec |
| 27 | 2026-05-05 | All | no body `JSON.parse` | Fastify body parser with size limit | Defense against prototype pollution + large-payload DoS. Centralized + AST-banned. | Adapter Spec |
| 28 | 2026-05-05 | All | TLS 1.3 only | No TLS 1.2 fallback | Node 20 supports 1.3 natively; vendors all support it. | Adapter Spec |
| 29 | 2026-05-05 | All | per-firm circuit-breaker key | `{firm_id}:{vendor}` LRU 1024 | Isolates faulty-firm blast radius. | Adapter Spec |
| 30 | 2026-05-05 | SFDC | **SSRF validation on `instance_url`** (v0.2.0 NEW) | Validate vendor-returned URLs against egress allow-list + reject RFC1918 / link-local / loopback | SFDC OAuth response contains `instance_url` consumed as base URL for subsequent calls. A compromised SFDC response could point adapter at EC2 metadata (`169.254.169.254`) or cluster-internal endpoints. `vendor_ssrf_blocked` errorCode on reject. | Adapter Spec v0.2.0 |
| 31 | 2026-05-05 | All | **auth.ts LRU bound** (v0.2.0 NEW) | Token cache LRU 1024 entries | Prevents OOM at scale (10 000 firms × unbounded Map). `lru-cache` added to AC12.2 allow-list. | Adapter Spec v0.2.0 |
| 32 | 2026-05-05 | All | **observability hand-off** (v0.2.0 NEW) | pino stdout JSON → log-shipper sidecar (`fluent-bit` or `vector`) → Langfuse + Datadog/Loki + M10 for CRITICAL events | Sidecar default Phase 2; OTEL OTLP-stdout exporter on Phase 3 roadmap. Events M10 escalates table documented in §Observability Hand-Off to M10. | Adapter Spec v0.2.0 |

Expected final DECISION-LOG has 40-60 entries after Task 22 population.

---

## Appendix F — Review Fix Traceability Table

Maps each of the 17 Required Fixes + 10 Recommended Fixes from `m11-rest-adapters-REVIEW.md` (LLMJ v1 scoring 7.27/10) to the spec section where v0.2.0 lands the fix. Mirrors M7 v0.2.0 discipline.

### Required Fixes (17)

| # | v1 Required Fix | v0.2.0 Spec Section(s) | Landing |
|---|-----------------|------------------------|---------|
| 1 | Fix fabricated RES-08 citations (AC5.2, AC15.2, Appendix E rows 1-4) | **AC5.2**, **AC15.2**, **Appendix E rows 1-4** | SFDC cites Salesforce Platform API Limits Cheatsheet URL. Orion/eMoney/Schwab marked PENDING-VERIFICATION with named verification gates. RES-08 citations used ONLY for facts RES-08 actually contains (approval timelines, protocol descriptions). |
| 2 | Reconcile eMoney allow-list (AC8.5) with M7 `EMoneyPlanSummary` Pydantic model | **AC8.5**, **§Known Blockers row 14**, **Appendix E row 6**, **Task 13**, **Task 20 `test_m7_emoney_allowlist.py`** | AC8.5 rewritten to the exact field set of M7's `EMoneyPlanSummary` (verified 2026-05-05). Required fields (7) + optional fields (15) + explicit forbidden list (10+). Integration test asserts set-equality — catches future drift. |
| 3 | Add SFDC PascalCase vs M7 snake_case mismatch to §Known Blockers as SHARED-WITH-M7 | **§Known Blockers row 4**, **§Integration Point with M7 "SFDC PascalCase..." subsection**, **Appendix E row 5**, **Task 20 `test_m7_sfdc_shape.py`** | Gap documented with reproduction, options for M7 fix (aliases vs alias-transformer), integration-test gate. |
| 4 | Declare Orion URL paths as PENDING-VERIFICATION | **AC2.11**, **§Known Blockers row 6**, **Appendix E row 21**, **Task 11** | Paths marked PENDING-VERIFICATION. Startup probe at Task 11; 404 → `orion.path_unverified` + degraded. |
| 5 | Add SEC EDGAR to Phase 2 scope OR provide explicit ARCH-09 cross-reference | **§Explicitly OUT of Scope**, **Appendix E row 22** | DECISION-LOG row 22: EDGAR is Phase 1 per ARCH-09 but owned by M8 Research Pipeline as a data source (not RIA meeting-prep). Deferred to M8 build window with cross-reference. |
| 6 | Declare the observability hand-off to M10 | **AC7.9**, **§Observability Hand-Off to M10**, **Appendix E row 32** | Option A (default): pino stdout → log-shipper sidecar → Langfuse + Datadog/Loki + M10. Option B (opt-in): OTEL OTLP-stdout. v0.2.0 commits to Option A Phase 2. Events M10 escalates table. |
| 7 | Specify concurrency limits and K8s resource requests/limits | **AC3.9**, **AC3.10**, **§Deployment Notes**, **mTLS Configuration Template Deployment snippet**, **Appendix E rows 14-15** | `undici.Agent({connections: 10})`. `resources.requests.{cpu: 100m, memory: 256Mi}` / `limits.{cpu: 500m, memory: 512Mi}`. 1 replica Phase 2; HPA Phase 3. |
| 8 | Add concrete Schwab RT-rotation-failure alerting path | **AC4.13**, **§Observability Hand-Off to M10 events table**, **Appendix C.4**, **Appendix E row 7** | Pino `fatal` event `auth.schwab.rt_rotation_failed` `severity:"CRITICAL"` → M10 sidecar → PagerDuty/OpsGenie within 5 min SLO. Adapter does NOT crash. |
| 9 | Specify how `test_m11_error_contract.ts` forces each error class deterministically | **AC16.4 mechanism table**, **Task 18** | 12-row table per error class with exact mechanism (FakeClock, msw `.use(...)` sequence, 5-response msw for circuit, missing-field payload for Zod, rawPlanBody fixture for eMoney, FakeSecretsClient instance_url for SSRF, cert-file rewrite for mtls_degraded). |
| 10 | Add Hypothesis-style (fast-check) property-based Zod fuzz | **AC18.6**, **§fast-check Strategy Approach**, **Task 6, 10, 13, 16** (each builds `property.test.ts`) | Worked example for `sfdc.fetch_client` (in-domain + out-of-domain generators, 1000 runs, ≥99% accept / reject rates). Per-tool matrix table for all 14 tools. |
| 11 | Narrow Schwab ServiceAccount's Secret-write RBAC | **§RBAC Template**, **AC9.7 exception**, **Task 15** | Concrete Role + RoleBinding YAML granting `["get","update"]` on `m11-schwab-refresh-token` ONLY. `resourceNames` restricts to single Secret. No wildcards, no cluster-scope. |
| 12 | Add SSRF validation for vendor-returned URLs | **AC14.10**, **Appendix C.1 step 5**, **Appendix D.7**, **Task 2** (`src/ssrf.ts`), **Task 5**, **Appendix E row 30** | `validateVendorURL()` in shared SDK: https-only + FQDN allow-list match + DNS-resolve + RFC1918/link-local/loopback reject. Enforced in SFDC auth startup. `vendor_ssrf_blocked` errorCode. |
| 13 | Resolve Phase 3 Orion Basic-auth toggle concretely | **AC4.12**, **Appendix C.2 Phase 3 section**, **Appendix E row 8**, **Task 9** | `ORION_AUTH_MODE=basic` Helm values toggle requiring pod redeploy (NOT hot-reload). Separate Secret path `m11/orion/basic_credentials`. `auth.ts` branches at startup. Both branches test-covered in Task 9. |
| 14 | Declare idempotency semantics for SFDC writebacks | **AC8.9**, **T-SF4 / T-SF5 tables**, **Appendix D.8**, **Appendix E row 18** | `If-Match` header with record ETag captured from prior `sfdc.fetch_client` response (exposed as `_etag` top-level sibling). 412 → HTTP 409 `vendor_conflict`. M6 re-fetches + retries once. |
| 15 | Bound the auth.ts per-firm token cache with LRU | **AC4.14**, **AC3.7** (LRUCache re-export), **AC12.2** (`lru-cache` added), **Appendix E row 31**, **Task 2**, **Task 5** | `LRUCache<string, CachedToken>({max: 1024})` — matches AC5.4 / AC6.2 caps. `lru-cache` added to allow-list. 1025-entry eviction test in Task 5. |
| 16 | Add vendor-schema-drift change process | **AC15.6**, **Appendix E row 25**, **Task 22** (`vendor-schema-drift-playbook.md`) | 6-step process: fail-closed → log field NAME → SME review 48h → classify (safe / MNPI-like) → allow-list + MINOR bump + deploy OR stay BLOCKED. Playbook document in Task 22. |
| 17 | Document Schwab trade-submission descope | **§Phase 2 Lighthouse Scope**, **§Explicitly OUT of Scope**, **AC2.4**, **§Design Schwab Tools (Read-Only — Phase 3 descope per Appendix E row 24)**, **Appendix A footer row**, **Appendix E row 24** | DECISION-LOG row 24 cites IMPL-06 Blocker 1 (Principal Review + FINRA 2210 + execution order state machine). Phase 3 adds `schwab.submit_trade`, `schwab.cancel_order`, `schwab.replace_order` as a new adapter spec. |

### Recommended Fixes (10)

| # | v1 Recommended Fix | v0.2.0 Spec Section |
|---|--------------------|---------------------|
| R1 | Measure and cite Docker image-size closure | **AC11.5** — 80+40+10≈130 MiB breakdown. |
| R2 | Add latency targets (p50/p95/p99 TTFB per tool) | **AC1.5** — p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms. Task 23 enforces. |
| R3 | Add chaos test in Task 23 | **Task 23** — secrets backend 500 for 30s; DNS failure for 10s; vendor TLS-handshake hang 15s. |
| R4 | Add Retry-After header edge-case tests | **AC5.7** — 5 cases (integer, HTTP-date, negative, HTTP-date > 300s cap, malformed, zero). Test matrix in Task 7. |
| R5 | Add per-firm-token LRU eviction test | **AC4.14** — 1025-entry load, assert firm #1 evicted. Task 5. |
| R6 | Add "which adapter wins on cost_basis conflict" one-liner | **§Integration Point with M7** (M7 owns reconciliation between REST and SFTP Schwab tax lots). M11 passthrough; no reconciliation logic. |
| R7 | Strengthen Dockerfile lint to require pinned SHA256 digests | **AC11.1** + Task 21 CI — Helm values pin digests; CI custom check asserts image reference matches `@sha256:` format. |
| R8 | Add Prometheus-compatible metric emission | **§Observability Hand-Off to M10** — pino → sidecar → Loki/Datadog log-based metrics (p50/p95 derived at aggregator). OTEL OTLP-stdout opt-in for direct Prometheus via OTel Collector. |
| R9 | Provide values-schema JSON for Helm umbrella chart | **Task 21** — `charts/m11-rest-adapters/values.schema.json` authored alongside `values-*.yaml`. `helm lint` catches missing values. |
| R10 | Cross-verify M7 translator coverage against M11 tools | **Appendix A footnote** — every read tool has a matching M7 translator pair (`test_m11_m7_version_match.py` Task 19); writebacks are M11-only (no M7 pair). 11 read-tool pairs, 2 writeback-only. |

---

## Appendix G — Glossary (Cross-Module Terms)

| Term | Meaning (M11-REST context) |
|------|----------------------------|
| Adapter | A single M11-REST Docker container for one vendor (SFDC, Orion, eMoney, Schwab in Phase 2). |
| Tool | A named MCP operation exposed by an adapter — e.g. `orion.fetch_holdings`. Has a Zod input schema; invokes vendor HTTP endpoints; returns raw vendor JSON. |
| Firm | A 007 tenant; identified by `X-Firm-ID` header. One firm may use all four adapters with its own credentials. |
| Vendor API version | The version of the external vendor's API the adapter speaks (SFDC `v59.0`, Orion `v2.0`, eMoney `v2`, Schwab `v1`). MUST match M7's per-translator constant. |
| Schema version | The adapter's own semver. Bumps on input Zod OR output shape OR auth flow change. Independent of vendor API version. |
| Circuit breaker | Per-firm-per-vendor state machine that stops vendor calls after repeated failures. LRU 1024 entries. |
| Rate-limit bucket | Per-firm-per-vendor token bucket. LRU 1024 entries. |
| Token cache | Per-firm LRU 1024 (v0.2.0 AC4.14) of active OAuth access tokens. Never persisted. |
| mTLS | Mutual TLS — both client (M6) and server (M11 adapter) present certificates. cert-manager rotates 24-hourly. |
| Raw vendor payload | HTTP response body from vendor, parsed as JSON, untouched. Adapter's primary output. |
| Canonical | An M3 Pydantic model produced by M7 translators. M11 never produces canonical types. |
| ETag | SFDC opaque record-version string captured from `GET` response header; used in `If-Match` on writebacks (v0.2.0 AC8.9) for optimistic concurrency. |
| SSRF | Server-Side Request Forgery — risk that a compromised vendor response points the adapter at internal/metadata endpoints. v0.2.0 AC14.10 validates. |
| CRITICAL event | A pino `fatal`-level event (`auth.schwab.rt_rotation_failed`, `auth.sfdc.ssrf_blocked`) escalated within 5 min by the M10 sidecar. |
| Sidecar | Log-shipper Pod (`fluent-bit` or `vector`) running alongside each M11 adapter; forwards pino stdout to Langfuse + Datadog/Loki + M10 per §Observability Hand-Off. |

---

## Appendix H — Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1.0 | 2026-04-28 | Initial draft for LLMJ-v1 review. 18 requirements, 133 ACs, 23 tasks, 4 adapters, 14 tools. 1,628 lines. |
| 0.2.0 | 2026-05-05 | **Post-LLMJ-v1 fix.** Full rewrite addressing all 17 required fixes + 10 recommended fixes from `m11-rest-adapters-REVIEW.md` (7.27/10 CONDITIONAL GO). 18 requirements, **147 ACs** (+14), 23 tasks (unchanged; content expanded per v0.2.0 additions), 4 adapters, 14 tools. New sections: §Observability Hand-Off to M10, §fast-check Strategy Approach, §RBAC Template. Appendix E DECISION-LOG: 32 seed entries (+12). Appendix F: full Review Fix Traceability Table. Target re-review ≥ 8.0/10 GO. |

---

*m11-rest-adapters.md v0.2.0 — Project 007 FSI Interoperability Platform*
*Phase 2 Intelligence Layer — RIA Lighthouse*
*Owner: Adapter Specialist (`007-adapter-agent`)*
*Next step: LLMJ v2 re-review per 7-step playbook (target ≥ 8.0/10 GO)*
