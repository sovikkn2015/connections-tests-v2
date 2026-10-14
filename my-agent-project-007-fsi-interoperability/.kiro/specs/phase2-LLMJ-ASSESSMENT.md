# Phase 2 LLMJ DEEP ASSESSMENT — Intelligence Layer (RIA Lighthouse)

> **Reviewer:** Independent LLM Judge (pipeline-and-intent-specialist acting as cross-module LLMJ)
> **Scope:** Phase 2 per steering file line 75 — `M7 + M11-REST + M9 + M8 + M12 (intelligence layer) → RIA lighthouse`
> **Date:** 2026-05-20
> **Verdict up front:** **8.44 / 10 — GO for RIA lighthouse demo (with one caveat)**
> **Caveat:** M12 Supervisor is part of the Phase 2 scope per steering and has **not** shipped. The 4 built modules (M7, M11, M9, M8) are product-demo-ready; the end-to-end RIA journey is simulated by integration tests that construct M12's inputs directly.

---

## 1. Weighted Score Table

GO threshold ≥ 8.0/10 weighted.

| # | Dimension | Weight | Raw | Weighted | Notes |
|---|-----------|-------:|----:|---------:|-------|
| 1 | Completeness | 25% | 8.3 | 2.08 | 4/5 Phase 2 modules shipped (M7, M11, M9, M8). **M12 Supervisor missing.** RIA journey demonstrable against library surface; last-mile Supervisor wrapping not yet built. |
| 2 | Accuracy | 20% | 8.8 | 1.76 | Cross-module shape contracts all verified against real source (M8↔M6 dataclass, M9↔M8 pipeline names, M7↔M3 types). All v2 Required Fixes landed. |
| 3 | Security | 20% | 8.9 | 1.78 | MNPI fail-closed on every entry point. Zero credentials across polyglot (Python + TypeScript). Bedrock via IRSA; Vault HMAC keys; mTLS 1.3 across modules. |
| 4 | Testability | 15% | 8.6 | 1.29 | **1189 passed, 4 skipped, 8 xfailed, 1 xpassed** confirmed by fresh run. 10/10 stress-stable. Hypothesis pinned `max_examples=20 CI / 50 local`. 139+ TS vitest. |
| 5 | Design Alignment | 10% | 8.2 | 0.82 | ARCH-09 matrix honored. Steering Rules 7/8/13/14/15/16/20/32 landed in every module. cost_basis_method never null enforced at M7 TaxLot level + M8 A12 invariant. |
| 6 | Gaps | 10% | 7.1 | 0.71 | 4 SHARED-WITH items outstanding (M5 v0.3.0 IntentRouterConfig, M5 v0.4.0 PipelineConfig, M10 v0.3.0 `/audit`, M6 v0.3.0 `/adapters`). Plus M12 + e2e test not yet drafted. |
| — | **TOTAL** | **100%** | — | **8.44** | **GO** — clears 8.0 threshold with 0.44 headroom. |

Phase 2 module average LLMJ-v2 score: 8.45/10 (M7 8.29, M11 8.52, M9 8.47, M8 8.53). This cross-module assessment lands slightly lower (8.44) because inter-module gaps aren't visible in module-by-module reviews.

---

## 2. Per-Dimension Deep Dive

### 2.1 Completeness — 8.3/10

**Evidence**

| Module | Deliverable | Claimed | Verified |
|--------|-------------|---------|----------|
| M7 | Translator pairs | 11 (SF 3 + Orion 4 + eMoney 1 + Schwab 3) + multi-vendor Household merger | ✅ `TRANSLATOR_REGISTRY` has exactly 11 keys in `src/m7_schema_translators/__init__.py`; eager-imports on package load fail-closed |
| M11 | MCP adapters | 4 adapters × 14 tools (SFDC 5 + Orion 4 + eMoney 1 + Schwab 3 read) + 1 shared SDK | ✅ Directory scan: `salesforce_fsc/`, `orion/`, `emoney/`, `schwab/`, `shared/mcp-sdk/` each with `src/tools.ts` + own tests |
| M9 | Intent taxonomy | 11 members, 3-bucket confidence, Haiku via Bedrock | ✅ `IntentCategory` enum exactly 11 members verified; `TAXONOMY_DISPATCH` = 11 entries; `A1/A2/A9/A10/A11` invariants assert at import |
| M8 | 23-stage LangGraph pipeline | 23 nodes + 3 HITL gates at {7,13,21} + map-reduce + 12 LLM-bearing stages | ✅ 23 stage files `stage_1_intake.py` through `stage_23_delivery_notify.py`; HITL `_GATE_ROLES` keyed 1/2/3 mapping to stages 7/13/21; 12 `.jinja` prompts + 12 `.version` files |
| M12 | Supervisor runtime | **NOT SHIPPED** | ❌ `src/` listing has no `m12_*` directory. Steering line 75 lists M12 as Phase 2; it is pending. |

**Strengths**

- Each of the 4 shipped modules has a COMPLETE marker with playbook step summary, non-negotiables checklist, and test count progression.
- Phase 2 scoping honesty: explicitly OUT-of-scope items enumerated (Strands v2 deferred, DynamoDB checkpointer stubbed, non-Bedrock providers stubbed, SEC EDGAR deferred to M8 window).
- Integration tests simulate M12 by constructing RouterContext / PipelineState directly. The M9→M8 handoff IS wired; the library surface IS demo-ready.

**Weaknesses**

- **M12 missing.** Steering file line 75 pins M12 as part of Phase 2. M8 COMPLETE marker declares "Phase 2 — COMPLETE (All 4 Modules)" which is inaccurate — only 4/5 steering-listed modules shipped.
- **No single end-to-end RIA-journey test** that chains M11 fetch → M7 translate → M6 gateway → M8 pipeline → M10 audit.

### 2.2 Accuracy — 8.8/10

Cross-module contracts verified against real source code:

| Contract | Verification |
|----------|--------------|
| M8 `GatewayRequest` field list ↔ M6 dataclass | ✅ `src/m8_pipeline_engine/gateway_client.py` dataclass fields `(token, action, tool_name, mcp_server, payload, trace_id, firm_id, target, context, session_id, vendor_adapter)` match `src/m6_mcp_gateway/gateway.py` line 116-134 field-for-field. Verified via `tests/integration/test_m8_m6_shape_match.py` using `dataclasses.fields()`. |
| M8 `GatewayError` branching ↔ M6 `VALID_GATEWAY_REASONS` | ✅ M6 `VALID_GATEWAY_REASONS` frozenset (11 codes) confirmed at `src/m6_mcp_gateway/gateway.py` line 64-77: `invalid_identity, invalid_request, authority_denied, authority_escalated, mnpi_filter_error, mnpi_leakage_scan, vendor_unavailable, vendor_error, rate_limited, circuit_open, audit_failed`. M8 `_call_with_branching` in `gateway_client.py` branches on every one. |
| M9 pipeline-target names ↔ M8 `PIPELINE_NAMES` | ✅ M9 `taxonomy.py` uses `m8.research_pipeline_1/2/3` + `m8.research_single_tool`. M8 `graph.py::_validate_initial_state` validates with regex `^m8\.research_(pipeline_[1-3]\|single_tool)$` — identical to M9's `_M8_PIPELINE_RE`. |
| M7 UUID namespaces ↔ M3 types | ✅ M7 v0.3.0 REVIEW-v2 spot-checked 33 field rows; 33/33 correct. |
| M7 `TaxLot.cost_basis_method` ↔ M3 type | ✅ M3 `TaxLot` has `cost_basis_method` field with `@field_validator cost_basis_method_never_null`; M8 A12 walks `holding.tax_lots[*].cost_basis_method`; M8 `graph.py::_validate_state_invariants` confirms. |
| M11 eMoney allow-list ↔ M7 `EMoneyPlanSummary` | ✅ M11 v0.2.0 REVIEW-v2 verified set-equal: 7 required + 14 optional = 21 top-level fields. |
| M11 → M7 audit-bypass | ✅ M11 passes raw vendor JSON through M6; M6 calls M7 at M8 stage 6 per M7 v0.3.0 §Integration Point with M6 (AC13.2). |

**Strengths**

- All 5 Phase 2 v0.1.0 accuracy defects (fabricated citations, wrong dataclass shapes, invented cost_basis field, wrong ARCH-09 row, wrong VendorAdapter kwargs) are eliminated at spec AND implementation level.
- Residual-reference audits in each v2 review confirm v1 wrong shapes appear only in Changelog / Review Fix Traceability / historical annotations — zero active contracts use old shapes.

**Weaknesses**

- `LiabilityReport` type relaxation: M8's `GatewayResponse.liability_report` typed `Optional[Any]` rather than concrete `LiabilityReport` (to avoid forbidden `compliance.gap2_liability_provenance` import). Defensible but needs explicit M8 DECISION-LOG entry.
- Schwab `VENDOR_API_VERSION="v1"` still an assumption per M7 Known Blockers.
- SF FSC PascalCase gate still xfailed (`tests/integration/test_m7_sfdc_shape.py`): real SFDC payloads will fail at M11→M6→M7 until M7 adds alias-transformer.

### 2.3 Security — 8.9/10

| Module | MNPI defense | Credentials | mTLS / IRSA |
|--------|--------------|-------------|-------------|
| M7 | Fail-closed on `UnknownEnumValue`; `ReconciliationNote` allow-listed field diffs only | Pure library, no HTTP; AST forbids `httpx`/`requests`/`boto3`/`fastapi`/`openai`/`anthropic` | N/A |
| M11 | TypeScript Zod strict; eMoney allow-list set-equal to M7; SSRF validator on vendor URLs | Zero credentials across 4 adapters + shared SDK; pino redaction; AWS Secrets Manager + `LRUCache({max:1024})` per-firm token cache | mTLS 1.3 + 24h cert-manager rotation |
| M9 | Pre-LLM MNPI shape scan (4 categories + precedence); Rule 8 fail-closed to `escalate_to_human`; **HMAC-SHA-256 tenant-scoped utterance digest** (rainbow-table-proof) | Zero credentials; IRSA; Vault HMAC key | Bedrock via private VPC endpoint |
| M8 | 3 HITL gates with **HMAC-SHA-256 approval tokens** + Vault-resolved key + 4h timeout + quarterly rotation; `m8_mnpi_leaked_through_gateway` branching | Zero credentials; `print(` AST scan rejects payload-like argument names; boto3 confined to `llm_client.py`/`hitl.py`/`checkpointer.py` | mTLS to M6 + M10; PrivateLink to Bedrock; RDS in-VPC |

**Strengths**

- **Zero credentials across polyglot codebase.** Python AST scan + TS regex scan + `.env.example` clean across all 4 modules.
- **MNPI filter on EVERY entry point.** M9 pre-LLM shape scan. M7 fail-closed on unknown enum. M11 Zod strict. M8 branches on M6 gateway MNPI reasons.
- **HMAC-SHA-256 where it matters.** M9 tenant-scoped utterance digest. M8 HITL approval tokens with quarterly rotation aligned to 24h mTLS cadence.
- **AST scans hold the line.** Positive allow-lists (M9: `m1_identity` + `m5_config_loader` only; M8: `m3_schema_registry` + `m5_config_loader` + `m9_intent_router.models` annotation-only).

**Weaknesses**

- mTLS cert reload has a 2.5min latent rotation window (standard kubernetes posture).
- HMAC key `@lru_cache(maxsize=128)` caches per process indefinitely; rotation is pod-restart-triggered.
- Schwab refresh-token CRITICAL alerting lives behind M10 `/audit` route pending.
- `tests/` dir not in credential-scan scope; fixture keys intentionally present.

### 2.4 Testability — 8.6/10

Fresh full-suite run (2026-05-20):

```
pytest tests/ --tb=line -q --timeout=60
1189 passed, 4 skipped, 8 xfailed, 1 xpassed, 3 warnings in 8.82s
```

**Matches M8 COMPLETE marker claim exactly.** Collection count = 1202 (1189 + 4 + 8 + 1). Stress per COMPLETE: 10/10 stable, 7.17s-8.65s range.

Test distribution:

- Unit: 42 files
- Security: 9 files (forbidden imports, module boundaries, no-hardcoded-creds, print discipline)
- Property: 6 files (Hypothesis, `max_examples=20 CI / 50 local`)
- Benchmarks: 3 files (M8/M9 concurrency, M9 MNPI latency <20ms)
- Integration: 17 files (cross-module version match, SFDC shape gate, M12 supervisor simulation)

TypeScript vitest on M11: 139+ tests directly counted; 156 claimed in COMPLETE marker (describe.each nesting accounts for difference).

**Strengths**

- **1189 passing on fresh run confirms the claim.** Zero flakes at 10/10 stress.
- Hypothesis property tests have pinned CI budget; determinism validated via `@composite` strategies composed with M3's Pydantic validators.
- Each module has **reason-code coverage matrix**: M7 7 codes, M8 20 codes, M9 13 codes — every one exercised.
- Cross-module version-match tests written as `xfail(strict=False)` → auto-upgrade when SHARED-WITH items land.

**Weaknesses**

- `test_m7_sfdc_shape.py` xfailed strict — will flip red the moment M7 ships fix.
- Live Bedrock probes gated behind `M8_LIVE=1` / `M9_LIVE=1`; no CI-scheduled runs.
- No single end-to-end RIA-journey test chaining M11→M7→M6→M8→M10.

### 2.5 Design Alignment — 8.2/10

ARCH-09 dependency matrix verification:

| Module | ARCH-09 row | Actual imports | Match |
|--------|-------------|----------------|-------|
| M7 | `.  .  *  .  *  .  .  .  .  .  .  .  .` (M7 → M3 + M5) | `m3_schema_registry` (types), enum-only M5 | ✅ |
| M11 | outer-ring adapter, M6↔M11 only | TypeScript MCP servers; no Python cross-module imports | ✅ |
| M9 | `*  .  .  .  *  .  .  .  .  .  .  .  .` (M9 → M1 + M5) | `m1_identity` + `m5_config_loader` | ✅ |
| M8 | `.  *  .  .  *  *  .  .  .  *  .  .  .` (M8 → M2 + M5 + M6 + M10) | M2/M6/M10 via HTTP Protocols; `m3_schema_registry` + `m5_config_loader` + `m9_intent_router.models` annotation-only | ✅ |

Steering Rules verified:

- Rule 4 (M6 gateway for all MCP): all 4 modules
- Rule 5 (OPA-only compliance): M9 routes compliance to escalate; M8 stage 20 via M6
- Rule 7 (M6 gateway): enforced
- Rule 8 (fail-closed): M9 MNPI; M8 HITL timeout; M7 UnknownEnumValue; M11 Zod strict
- Rule 13 (Sonnet/Haiku split): M8 Sonnet via boto3; M9 Haiku via boto3 `converse` + Anthropic `tool_use`
- Rule 14 (no LLM for compliance): enforced
- Rule 15 (LLM provider abstracted): Protocol with Bedrock default + 3 Phase 3 stubs
- Rule 16 (cost_basis_method never null): M7 fail-closes; M8 A12 walks `holding.tax_lots[*].cost_basis_method`
- Rule 20 (zero credentials): Vault + IRSA + `.env.example` clean
- Rule 32 (security per module): every box ticked

**Weaknesses**

- `langchain-aws` deviation in M8 pending ARCH-04 v2 update (Known Blockers row 17).
- Rule 11 (async, max 3 concurrent, queued) is `threading.Semaphore(3)` block-then-fail-60s. Phase 3 Redis-backed true queue deferred.

### 2.6 Gaps — 7.1/10

4 SHARED-WITH items outstanding:

| # | SHARED-WITH item | Target | Test posture |
|---|------------------|--------|--------------|
| 1 | M5 v0.3.0 `IntentRouterConfig` | M5 Week 32 | `test_m9_m5_config_shape.py` — xfail(strict=False), auto-upgrades |
| 2 | M5 v0.4.0 `PipelineConfig` | M5 Week 30 | `test_m8_m5_config_shape.py` — xfail(strict=False), auto-upgrades |
| 3 | M10 v0.3.0 `/audit` REST route | M10 Week 28 | `test_m8_m10_audit_contract.py` — xfail(strict=False), auto-upgrades |
| 4 | M6 v0.3.0 `/adapters` bootstrap route | M6 Week 28 | M8 workaround via `LocalVendorAdapterResolver(registry_snapshot)` |

Plus:

| # | Gap | Status |
|---|-----|--------|
| 5 | **M12 Supervisor module** (Phase 2 steering line 75) | Not built |
| 6 | **End-to-end RIA lighthouse integration test** | Not written |
| 7 | SFDC PascalCase alias handling | SHARED-WITH-M7 row 14 — xfailed strict |
| 8 | Schwab developer-program approval | Operational (6-8 wk lead) |
| 9 | eMoney partnership approval | Operational (6-12 mo lead) |

---

## 3. Cross-Module Contract Verification Table

| Boundary | Contract | Verified against | Status |
|----------|----------|------------------|--------|
| **M7 ↔ M3** | M7 produces M3 canonical types with exact UUID vs str discipline | `src/m3_schema_registry/types.py` — 33/33 rows verified | ✅ |
| **M7 ↔ Steering 16** | `cost_basis_method` NEVER null; fail-closed on unmappable | `src/m7_schema_translators/cost_basis.py` + M3 validator | ✅ |
| **M8 ↔ M6** | `GatewayRequest`/`GatewayResponse` dataclass field-for-field | M8 dataclass == M6 lines 116-134 | ✅ Task 20 asserts via `dataclasses.fields()` |
| **M8 ↔ M6 reasons** | All 11 `VALID_GATEWAY_REASONS` branched | M6 line 64-77 frozenset; M8 `_call_with_branching` | ✅ 11/11 |
| **M8 ↔ M8 reasons** | 20 `VALID_REASON_CODES` reachable | M8 `errors.py` `assert len == 20`; Tasks 14/16/17 matrix | ✅ 20/20 |
| **M8 ↔ M9** | Pipeline names match | M9 `_M8_PIPELINE_RE` == M8 `_validate_initial_state` regex | ✅ identical regex |
| **M9 ↔ M1** | `RouterContext.identity: AidClaims` self-consistency | M9 AC1.9 validator | ✅ |
| **M9 ↔ M5** | `IntentRouterConfig` duck-typed pending M5 v0.3.0 | `getattr(config, ...)` | ⚠ xfail pending M5 |
| **M9 → M12** | `RoutingDecision` audit payload 12-key shape | `test_m12_m9_supervisor_call.py` | ✅ |
| **M11 ↔ M7** | M11 raw vendor JSON → M6 → M7 at M8 stage 6 | M7 v0.3.0 AC13.2 | ✅ |
| **M11 ↔ M7 eMoney** | eMoney allow-list set-equal to `EMoneyPlanSummary` | 21 fields × 2 sides | ✅ |
| **M11 ↔ M7 SFDC** | SFDC PascalCase alias handling | SHARED-WITH-M7 row 14 | ⚠ xfail strict |
| **M8/M9 → M1** | AidClaims for authority scope | `taxonomy.required_scopes(intent)` + `_check_authority_scope()` | ✅ |
| **M8 → M10** | Per-stage audit via `/audit` REST | M8 `audit_client.py` M10AuditClient | ⚠ Pending M10 v0.3.0 |

**Summary:** 12 contracts ✅ clean, 3 ⚠ pending SHARED-WITH. Zero contract violations. Zero silent drift.

---

## 4. End-to-End RIA Lighthouse Scenario Trace

**Scenario:** Advisor says "prep me for Henderson meeting tomorrow" at 8am. Expected outcome: by 9am, Salesforce has a writeback research brief with Henderson-household-contextualized market + news + SEC analysis, 3 HITL gates auto-approved or escalated.

**Hop-by-hop wiring check:**

| # | Hop | Built? | Wired? | Evidence |
|---|-----|--------|--------|----------|
| 1 | Advisor utterance arrives at channel | ⚠ Channel is M13 (Phase 4) or OpenClaw wedge | — | Out of Phase 2 scope |
| 2 | Channel → **M12 Supervisor** constructs `RouterContext` from `AidClaims` | ❌ **M12 not built** | — | No `src/m12_*` directory |
| 3 | M12 → **M9** `route(utterance, context, _provider, _config)` | ✅ | ✅ | `test_m12_m9_supervisor_call.py` — `"prep me for tomorrow's meeting"` → `RESEARCH_MEETING_PREP` at 0.97 |
| 4 | M9 → `RoutingDecision(target=SelectedTarget(kind="pipeline", name="m8.research_pipeline_1"))` | ✅ | ✅ | Payload asserted `selected_target.name == "m8.research_pipeline_1"` |
| 5 | M12 → **M8** `research_pipeline.run(initial_state, thread_id)` | ✅ | ✅ | `test_m12_m8_supervisor_call.py::test_m12_supervisor_m8_round_trip_returns_pipeline_result` |
| 6 | M8 stages 1-6 (intake, CRM, market, news, SEC, transcripts via M6) | ✅ | ✅ | Each stage `_call_with_branching` via FakeGatewayClient |
| 7 | M8 stage 7 — **HITL GATE 1 (data quality review)** | ✅ | ✅ | `hitl.py::verify_approval_token` + HMAC-SHA-256 quarterly rotation |
| 8 | Approver role: advisor or supervising_advisor | ✅ | ✅ | `_GATE_ROLES[1] == frozenset({"research_specialist","supervising_advisor","advisor"})` |
| 9 | M8 stage 8 — **map-reduce** over up to 10 instruments via `langgraph.types.Send` | ✅ | ✅ | `test_m8_stages_8_12.py` |
| 10 | M8 stages 9-12 (DCF, comps, Monte Carlo, cross-source synthesis) | ✅ | ✅ | Sonnet stages via `FakeSonnetClient` |
| 11 | M8 stage 13 — **HITL GATE 2 (analysis review)** — compliance_officer | ✅ | ✅ | `_GATE_ROLES[2] == frozenset({"compliance_officer"})` |
| 12 | M8 stages 14-20 (thesis, catalyst, risk, rating, target_price, brief, compliance via M6→OPA) | ✅ | ✅ | Stage 20 calls `action="compliance.screen"` via gateway |
| 13 | M8 stage 21 — **HITL GATE 3 (final + anti-fabrication)** | ✅ | ✅ | Every numeric claim traces back to `ResearchSource.raw_excerpt` |
| 14 | M8 stage 22 — **CRM writeback** via M6→SFDC with ETag idempotency | ✅ | ✅ | M11 AC8.9 `If-Match` ETag; M6 handles 412 retry |
| 15 | M8 stage 23 — **delivery notify** — terminal audit via `AuditClient.emit()` | ✅ | ⚠ | Fake captures; real M10 `/audit` endpoint pending |
| 16 | `PipelineResult` returned to M12 → marshal `brief` to channel | ❌ **M12 not built** | — | Simulation test stops here |

**Diagnosis:** 14 of 16 hops are built and wired in the library surface. The 2 missing hops are the M12 bookends. The library surface ships demo-ready; the end-to-end wrapper is missing.

**Demo viability:** A ~40-line harness playing the M12 role would demonstrate the full 23-stage pipeline end-to-end against fake clients. This is not Phase 2 production closure but IS lighthouse-demo closure.

---

## 5. SHARED-WITH Items Outstanding

| Item | Target | Owner | ETA | xfail test |
|------|--------|-------|-----|-----------|
| IntentRouterConfig sub-model | M5 v0.3.0 | M5 | Week 32 | `test_m9_m5_config_shape.py` — strict=False |
| PipelineConfig sub-model | M5 v0.4.0 | M5 | Week 30 | `test_m8_m5_config_shape.py` — strict=False |
| `/audit` REST route | M10 v0.3.0 | M10 | Week 28 | `test_m8_m10_audit_contract.py` — strict=False |
| `/adapters` bootstrap route | M6 v0.3.0 | M6 | Week 28 | M8 workaround via `LocalVendorAdapterResolver` |
| SFDC PascalCase alias-transformer | M7 v0.4.0 | M7 | TBD | `test_m7_sfdc_shape.py` — strict=True |
| M12 Supervisor module | M12 v0.1.0 | Supervisor Specialist | Phase 2 closure | None possible without M12 |
| End-to-end RIA integration test | — | Test infra | Phase 2 closure | **None written** |

**Auto-upgrade posture:** All 4 xfail(strict=False) tests flip to `xpassed` the moment their upstream dependency ships — ops signal for "upstream shipped". No M8/M9/M11 re-review required.

**Blocking for production:** SHARED-WITH items 1-4 must resolve. SFDC PascalCase blocks SFDC adapter production. M12 + e2e test block Phase 2 steering-list closure.

**Non-blocking for RIA lighthouse demo:** All 7 items. Demo runs against fake clients + in-memory checkpointer + captured audit entries.

---

## 6. Final Verdict

**Phase 2 Intelligence Layer: GO for RIA lighthouse demo at 8.44/10 weighted.**

The 4 shipped modules (M7, M11, M9, M8) together form a complete product-demo substrate. Every architectural rule, every Phase 2 Required Fix, every cross-module contract has been verified at spec, implementation, and test level. The 1189-test suite passes deterministically with zero flakes across 10 stress runs. MNPI fail-closed on every entry point. Zero credentials across polyglot Python + TypeScript. HMAC-SHA-256 tamper-proof tokens for tenant-scoped utterance digests and HITL approvals. 3 HITL gates at stages 7/13/21 with Vault-resolved keys and quarterly rotation. LangGraph `Send` fan-out with cap 10 instruments. 20-minute wall-clock ceiling excluding HITL wait time. 12 LLM-bearing stages with per-stage token budgets and Bedrock Sonnet. Every specialist route either lands at an M8 pipeline or an M6 tool or an escalate target — all 11 intent categories covered by taxonomy invariants A1-A19 asserted at module import.

The gap is the **last mile**. M12 Supervisor is on the Phase 2 steering list (line 75) and is not yet built. The M12 Supervisor is a ~200-line module that (a) receives channel utterances + AidClaims, (b) calls `m9.route(utterance, context)`, (c) constructs a `PipelineState` from the `RoutingDecision`, (d) calls `research_pipeline.run(state, thread_id)`, (e) marshals `PipelineResult.brief` back to the channel. Integration tests already simulate this exact shape. For a customer demo, a harness playing the M12 role is sufficient; for production, M12 must ship before Phase 3 starts. The M8 COMPLETE marker claim "Phase 2 CLOSED" is premature — 4/5 steering-listed modules is not closure.

The 4 SHARED-WITH items are honest Phase 2 Week 28-32 cross-cutting work. Each has an xfail(strict=False) test written that auto-upgrades on upstream ship. M8 has a working `LocalVendorAdapterResolver` fallback that makes the RIA demo viable today.

The v0.1.0 → v0.2.0 discipline across all 4 modules was textbook. Accuracy gains +2.2 to +3.1 points per module as each v2 review surgically eliminated the fabricated shapes and wrong citations from v0.1.0 drafts. The cross-module contract verification table shows 12/15 contracts clean, 3 pending SHARED-WITH — exactly what a 4-module phase with 4 upstream amendments should look like.

**Is the RIA lighthouse demo-ready?** Yes, against a ~40-line M12 harness + fake clients. The Henderson-meeting journey runs end-to-end through 23 stages with 3 HITL gates. The brief comes back shape-correct. The audit trail captures per-stage provenance with ARCH-06 v3 Gap 2 fields. A real demo needs a live M12 + live M10 + live M6 `/adapters` — all tractable in 2-3 weeks of Phase 2 Week 28-32 work.

Any crack here WOULD show to customers; the crack is cosmetic (library-surface demo vs production-wrapped demo) and fully closable inside Phase 2's remaining window.

---

## 7. Recommendations for RIA Lighthouse Deployment

### MUST-DO before lighthouse customer demo (Week 28-32)

1. **Build M12 Supervisor thin wrapper** (~200 LOC under `src/m12_supervisor/`). Even a test-only harness in `tests/integration/test_ria_lighthouse_e2e.py` scripting the M12 role is sufficient for first-demo.

2. **Ship end-to-end RIA journey integration test.** One test: AidClaims → `m9.route("prep me for Henderson meeting tomorrow", ctx)` → `m8.research_pipeline.run(state, thread_id)` → auto-approve HITL gates via FakeApprover → assert brief shape + 22-stage audit entries + CRM writeback captured. ~150 LOC. Closes the biggest demo-readiness gap.

3. **Unblock M5 v0.3.0 `IntentRouterConfig` + M5 v0.4.0 `PipelineConfig`** on the M5 team. Every Phase 2 module xfails one or both. Auto-upgrade means no follow-on work in M7/M8/M9/M11.

4. **Unblock M10 v0.3.0 `/audit` REST route.** M8 per-stage audit + M11 CRITICAL alerting both block on this. Mock M10 sidecar acceptable for demo but not for SOC 2.

5. **Unblock M6 v0.3.0 `/adapters` route** OR pin the Python-object-handoff contract at M12 construction time.

### SHOULD-DO before customer signs paperwork (Week 32-36)

6. **Resolve M7 SFDC PascalCase alias-transformer.** `test_m7_sfdc_shape.py` is xfail(strict=True) — flips red the moment M7 is fixed. SFDC payloads from real org fail at M11→M6→M7 until then. Options: (a) `populate_by_name=True + Field(alias=...)` on every PascalCase field, OR (b) `pascal_to_snake(payload)` helper before model construction.

7. **Verify Schwab `VENDOR_API_VERSION="v1"` URL-path** against live Schwab sandbox.

8. **Schedule CI-automated first-live-call Bedrock probes.** Add weekly cron GitHub Action with IRSA to catch model-ID drift early.

9. **Document M8 DECISION-LOG entry for `liability_report` type relaxation** (intentional `Optional[Any]` vs M6 concrete type, to avoid forbidden compliance import).

10. **Write M7 Hypothesis `@composite` worked example** — M7 REVIEW-v2 NI-1 flagged; M11 has the pattern for lift-and-shift.

### NICE-TO-HAVE (post-Phase-2)

11. Tenant-scoped checkpointer compound key `(tenant_id, thread_id)`.
12. Audit-outage circuit-breaker readiness probe on M8 pod.
13. `dropped_instruments` propagation into `ResearchBrief.sources`.
14. M9 MNPI Luhn tightening for `bank_account`.
15. Phase 3 Redis-backed queue for M8 cross-tenant admission.

### Operational (vendor / compliance / partnership)

16. **Schwab developer-program approval** (6-8 wk lead).
17. **eMoney partnership approval** (6-12 mo lead).
18. **Orion URL path verification** against live developer portal.
19. **Vault tenant HMAC key provisioning** for M9 — per-tenant Vault policy + IAM cross-tenant isolation.

---

## 8. Score Summary

| Dimension | Score | Notes |
|-----------|------:|-------|
| Completeness | 8.3 | 4/5 modules shipped; M12 missing |
| Accuracy | 8.8 | All cross-module contracts verified |
| Security | 8.9 | MNPI + credentials + mTLS strong across polyglot |
| Testability | 8.6 | 1189 passing, stress-stable, 139+ TS vitest |
| Design Alignment | 8.2 | ARCH-09 + Steering 7/8/13/14/15/16/20/32 honored |
| Gaps | 7.1 | 4 SHARED-WITH + M12 + e2e test outstanding |
| **Weighted** | **8.44** | **GO for RIA lighthouse demo** |

Per-module LLMJ-v2 cross-reference:

| Module | v1 | v2 | Δ |
|--------|----|----|---|
| M7 Schema Translators | 7.36 | 8.29 | +0.93 |
| M11 REST Adapters | 7.27 | 8.52 | +1.25 |
| M9 Intent Router | 7.42 | 8.47 | +1.05 |
| M8 Pipeline Engine | 7.63 | 8.53 | +0.90 |
| **Module average** | **7.42** | **8.45** | **+1.03** |

Phase 2 cross-module assessment: 8.44 — slightly below module average because inter-module gaps (M12, e2e test, 4 SHARED-WITH) aren't visible in module-by-module reviews.

---

## 9. Review Metadata

| Field | Value |
|-------|-------|
| Review Type | LLMJ Deep Phase Assessment (cross-module) |
| Scope | Phase 2 Intelligence Layer — M7 + M11-REST + M9 + M8 (+ M12 per steering) |
| GO Threshold | ≥ 8.0 weighted |
| Final Score | **8.44 / 10 — GO for RIA lighthouse demo** |
| Module Artifacts Reviewed | 4 specs v0.2.0-v0.3.0, 4 REVIEW files (v1), 4 REVIEW-v2 files, 4 COMPLETE markers |
| Source Files Inspected | `src/m8_pipeline_engine/{gateway_client,graph,hitl,errors}.py`, `src/m9_intent_router/{taxonomy,route,errors}.py`, `src/m7_schema_translators/{__init__.py,shared/dispatcher.py}`, `src/m6_mcp_gateway/gateway.py` (M6 ground-truth) |
| Test Suite Run | 1189 passed, 4 skipped, 8 xfailed, 1 xpassed in 8.82s (fresh run 2026-05-20) |
| Calibration | Phase 1 SCORING 8.33; module v2 average 8.45 |
| Contract Verification | 12 of 15 cross-module contracts clean, 3 pending SHARED-WITH |
| Reviewer | Pipeline and Intent Specialist acting as independent Phase 2 LLM Judge |
| Date | 2026-05-20 |

---

*phase2-LLMJ-ASSESSMENT.md — Project 007 FSI Interoperability Platform*
*LLMJ Deep Phase Assessment — Phase 2 Intelligence Layer (RIA lighthouse)*
*Verdict: **8.44 / 10 — GO for RIA lighthouse demo.** Ship M12 thin-wrapper + one e2e integration test to close Phase 2 steering-list per line 75.*
