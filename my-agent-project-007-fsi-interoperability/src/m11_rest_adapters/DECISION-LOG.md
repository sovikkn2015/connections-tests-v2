# M11-REST DECISION-LOG

Seeded per spec Appendix E. Every entry: Date | Vendor | Tool/Area | Decision | Rationale | Decided By.

## 2026-05-05 Phase 2 Lighthouse Build

| # | Date | Vendor | Tool / Area | Decision | Rationale | Decided By |
|---|------|--------|-------------|----------|-----------|------------|
| 1 | 2026-05-05 | SFDC | rate_limit | 100K/24h → `RPM=4166`, `BURST=200` | Salesforce Platform API Limits Cheatsheet (Enterprise, per connected app). | Spec v0.2.0 |
| 2 | 2026-05-05 | Orion | rate_limit | **PENDING-VERIFICATION** — 60 RPM / burst 10 | Orion developer portal is login-gated. Verification: Task 11 probe + Orion support-email. | Spec v0.2.0 |
| 3 | 2026-05-05 | eMoney | rate_limit | **PENDING-VERIFICATION** — 30 req/s (1800 RPM) / burst 30 | eMoney ref is behind Fidelity partner portal. Verification: post-partnership API ref review. | Spec v0.2.0 |
| 4 | 2026-05-05 | Schwab | rate_limit | **PENDING-VERIFICATION** — 120 RPM / burst 20 sandbox | Schwab Developer Portal rate-limit page is NDA-gated. | Spec v0.2.0 |
| 5 | 2026-05-05 | SFDC | **SHARED-WITH-M7** — PascalCase vs snake_case | M11 does NOT pre-normalize; M7 owns the fix. Integration-test gate at `tests/integration/test_m7_sfdc_shape.py` (xfail). | M7 `extra="forbid"` + no aliases; SFDC returns PascalCase. M11 passthrough contract precludes adapter-side fix. | Adapter Specialist + M7 Owner |
| 6 | 2026-05-05 | eMoney | raw-plan allow-list aligned to M7 | 7 required + 14 optional (NEW-2 patch). Any other key → `emoney_raw_plan_forbidden`. | M7 `EMoneyPlanSummary` has `extra="forbid"`; symmetry prevents drift. Set-equality enforced by `test_m7_emoney_allowlist.py`. | Spec v0.2.0 |
| 7 | 2026-05-05 | Schwab | RT-rotation failure alerting | `auth.schwab.rt_rotation_failed` at pino `fatal` `severity:"CRITICAL"` → M10 → PagerDuty ≤ 5 min. | Closes 30-min latent outage window (AC4.13). | Spec v0.2.0 |
| 8 | 2026-05-05 | Orion | OAuth vs Basic toggle | Phase 2 = OAuth. Phase 3 = Basic via `ORION_AUTH_MODE=basic` + pod redeploy. Separate Secret path. | Not hot-reloadable. Both branches test-covered. | Spec v0.2.0 |
| 9 | 2026-05-05 | All | sandbox vs production | Phase 2 = sandboxes (Schwab + eMoney). | Operational gates (approval, partnership), not code gates. | Spec |
| 10 | 2026-05-05 | All | mTLS rotation | 24 h | Steering Rule 21. | Steering |
| 11 | 2026-05-05 | All | circuit threshold | 5 consecutive OR > 50% over 60 s (≥ 10 calls) | Industry norm; short enough to protect. | Spec |
| 12 | 2026-05-05 | All | image size cap | 150 MiB cap, observed ~130 | distroless ~80 + node_modules ~40 + dist ~10. CI asserts. | Spec v0.2.0 |
| 13 | 2026-05-05 | All | latency targets | p50 < 200 ms, p95 < 1000 ms, p99 < 3000 ms | Adapter-side only. Task 23 enforces at 200-call sample. | Spec v0.2.0 |
| 14 | 2026-05-05 | All | concurrency | `undici.Agent({connections: 10})` per pod | Balances vendor-TCP + single-replica blast radius. Override via `ADAPTER_UNDICI_CONNECTIONS` (1-64). | Spec v0.2.0 |
| 15 | 2026-05-05 | All | K8s resources | `requests: {cpu:100m, memory:256Mi}` / `limits: {cpu:500m, memory:512Mi}`. 1 replica Phase 2. | Matches Node `--max-old-space-size=512`. Singleton avoids distributed state. | Spec v0.2.0 |
| 16 | 2026-05-05 | All | M7 non-import | M11 MUST NOT depend on `@project-007/m7-schema-translators`. | Audit-bypass prevention. | M7 spec v0.3.0 |
| 17 | 2026-05-05 | SFDC | writable allow-list | Only Status, ClientArchetype, RiskToleranceUpdatedDate, Description. | PII via service-account bypasses SFDC native PII audit. | Spec + Compliance |
| 18 | 2026-05-05 | SFDC | writeback idempotency | `If-Match` ETag. 412 → `vendor_conflict`. M6 re-fetches once. | SFDC's only concurrency primitive. | Spec v0.2.0 |
| 19 | 2026-05-05 | All | per-firm rate-limit key | `X-Firm-ID` required | Multi-tenant isolation (Steering 23). LRU 1024. | Spec |
| 20 | 2026-05-05 | All | no M11→M10 direct writes | Sidecar forwards CRITICAL to M10 aggregator. | Steering 33 — no cross-module imports. | M10 spec |
| 21 | 2026-05-05 | Orion | URL paths | **PENDING-VERIFICATION** — `/api/v2.0/...`. Startup probe → 404 = `orion.path_unverified` + degraded. | Archived 007 used `/api/v1`. Live portal requires login. | Spec v0.2.0 |
| 22 | 2026-05-05 | SEC EDGAR | phase assignment | **DEFERRED** to M8 Research Pipeline | Not the RIA meeting-prep journey. | Spec v0.2.0 |
| 23 | 2026-05-05 | Alpha Vantage + News API | phase assignment | **DEFERRED** — M8 spec prerequisite | — | Spec v0.2.0 |
| 24 | 2026-05-05 | Schwab | **trade submission descope** | Phase 2 READ-ONLY. No `schwab.submit_trade`. | IMPL-06 Blocker 1 (Principal Review + FINRA 2210 + order state machine). Phase 3. | Spec v0.2.0 + IMPL-06 |
| 25 | 2026-05-05 | All | schema-drift process | Field NAME → SME review 48h → allow-list + MINOR bump OR stay BLOCKED. Playbook: `docs/vendor-schema-drift-playbook.md`. | Prevents MNPI leakage via accidental allow-listing. | Spec v0.2.0 |
| 26 | 2026-05-05 | eMoney | scope enforcement | Reject wider granted scope. | Scope creep = security regression. `auth.ts::acquire` step 3. | Spec |
| 27 | 2026-05-05 | All | no body JSON.parse | Fastify body parser + 1 MiB limit. | Prototype-pollution + large-payload DoS defense. | Spec |
| 28 | 2026-05-05 | All | TLS 1.3 only | No fallback. | Node 20 native; all vendors support. | Spec |
| 29 | 2026-05-05 | All | per-firm circuit key | `{firm_id}:{vendor}` LRU 1024. | Isolates faulty-firm blast radius. | Spec |
| 30 | 2026-05-05 | SFDC | SSRF on `instance_url` | Validate against egress + reject private IPs. `vendor_ssrf_blocked`. | EC2-metadata (`169.254.169.254`) exfiltration defense. | Spec v0.2.0 |
| 31 | 2026-05-05 | All | auth.ts LRU bound | Token cache LRU 1024. | Prevents OOM at 10 000-firm scale. Eviction test in SFDC `test_auth.test.ts`. | Spec v0.2.0 |
| 32 | 2026-05-05 | All | observability hand-off | pino stdout → log-shipper sidecar → Langfuse + Datadog/Loki + M10 (CRITICAL). | Sidecar default Phase 2; OTEL OTLP-stdout on Phase 3 roadmap. | Spec v0.2.0 |
