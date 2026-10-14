# Spec: M8 Pipeline Engine

> Module: M8 — Pipeline Engine
> Phase: 2 (Intelligence Layer — RIA lighthouse)
> Owner: Pipeline and Intent Specialist
> **Version: 0.2.0** — Addresses LLMJ-v1 review (7.63/10 CONDITIONAL GO, 2026-05-18). All 12 Required Fixes closed; Recommended Fixes R1-R5 integrated. Targets ≥ 8.0/10 GO on LLMJ-v1 re-review. Mirrors M7 v0.3.0 / M11 v0.2.0 / M9 v0.2.0 structural discipline.
> Dependencies (runtime): AWS Bedrock Claude Sonnet (research synthesis, via `boto3` Bedrock Runtime); PostgreSQL 16 (LangGraph `Checkpointer` backend, Phase 2 cloud via RDS and on-prem) OR DynamoDB (Phase 3 alternative); outbound mTLS to M6 Trust-Aware Gateway (every MCP tool call); outbound mTLS to M10 Audit Logger REST endpoint (every audit emission); HashiCorp Vault / AWS Secrets Manager (IRSA-resolved Bedrock credentials, checkpointer DSN, per-tenant KMS key handle, HITL HMAC key).
> Dependencies (code — ALIGNED WITH ARCH-09 MATRIX row M8 = `.  *  .  .  *  *  .  .  .  *  .  .  .`): `m3_schema_registry` (canonical types — `ResearchBrief`, `InteractionSummary`, `SecurityIdentifier`, `ResearchSource`, `Client`, `Holding`, `Household`, `TaxLot`), `m5_config_loader` (`Archetype`, `Runtime`, `SpecialistConfig`, and a new `PipelineConfig` sub-model — **SHARED-WITH-M5** amendment pending M5 v0.4.0), `m9_intent_router.models` (`RoutingDecision`, `SelectedTarget`, `IntentCategory` — **type-annotation-only import** for `PipelineState.routing_decision`; M8 NEVER calls M9's `route()`). ZERO imports from M1, M2, M4, M6, M7, M10, M11, M12, M13, `compliance.gap2`, `compliance.gap6`. M8's dependencies on M2 (authority pre-check) and M6 (tool dispatch) and M10 (audit) are all **runtime HTTP calls through injected Protocol clients** — never Python imports.
> Consumers (ALIGNED WITH ARCH-09 MATRIX column 8 — M12 marked `*`, all others `.`): **M12 Supervisor Runtime** (primary and only direct caller in Phase 2 — `research_pipeline.run(initial_state, thread_id)` per ARCH-08 Journey §5). M6 does NOT call M8 (ARCH-09 column 8 row M6 = `.`). M9 does NOT call M8 (ARCH-09 column 8 row M9 = `.`). M8 is a stateful-but-pure library wrapping a LangGraph `StateGraph` — M12 imports and invokes it.
> Design Sources: `docs/007-consolidated-design-and-plan.md` Part 7 + Part 11 (Phase 2 plan, Week 28-36 lighthouse); ARCH-04 v2 §M8 Pipeline Engine (LangGraph MIT, `langgraph + langchain-aws`, DynamoDB/PostgreSQL checkpointer pluggable — but see Known Blocker row 17 re: `langchain-aws` deviation); ARCH-07 §Agent Runtime Matrix (Research = LangGraph + Sonnet, `<20 min` full run, async) + §Model Selection Table (Research = Sonnet for deep reasoning / large context); ARCH-09 §M8 row + §DEPENDENCY MATRIX row 8 + column 8 (M8 → {M2, M5, M6, M10}; {M12} → M8); ARCH-08 §M8 networking (private subnet, mTLS to M6, PrivateLink to Bedrock, Gateway Endpoint to DynamoDB / RDS in-VPC to PostgreSQL) + §Journey step 5 (M12 → M8 → M6); ARCH-10 §Decision 2 "Research Specialist — KEEP BOTH VERSIONS" (M8 LangGraph v1 proven with 23 stages + 48 tests + HITL + checkpointing; Strands v2 is a separate module not built here); ARCH-03 §M8 ADAPT budget (~1,400 lines ported from 006); ARCH-06 v3 §Gap 2 Liability Framework (M8 per-stage provenance: stage number + model version + prompt template version + input/output hashes — Steering Rule 32, per-stage audit); `src/m6_mcp_gateway/gateway.py` (`TrustAwareGateway.call(request: GatewayRequest) -> GatewayResponse` — **dataclass-shaped; failures RAISED as `GatewayError`, not returned** — Required Fixes 1-4 acknowledge); `src/m3_schema_registry/types.py` (`Holding` has NO `cost_basis_method`; `TaxLot.cost_basis_method` does — Required Fix 5 acknowledges); `src/m9_intent_router/models.py` (`RoutingDecision` — annotation-only import). Steering rules 4, 5, 6, 7, 8, 13, 14, 15, 20, 32.
> Language: Python 3.12+ | Runtime Validation: Pydantic v2 (pinned `>=2.0,<3.0`) | Framework: `langgraph >= 0.4, < 2.0` (MIT — bumped from `<0.3` in v0.2.0 per Required Fix 8; covers V1.0 stable line) | LLM SDK: `boto3` ≥ 1.34 (Bedrock Runtime Sonnet; NO `langchain-aws`, NO `langchain`, NO `langchain-community`, NO `anthropic` SDK) | Checkpointer: `langgraph-checkpoint-postgres` (Phase 2) / `langgraph-checkpoint-dynamodb` (Phase 3, reserved) | Property tests: `hypothesis` ≥ 6.100 (dev only; CI `max_examples=20`, local `max_examples=50` per Recommended Fix 4)
> Estimated Lines: ~1,400 production src lines across `__init__.py` + `graph.py` (LangGraph `StateGraph` wiring) + `state.py` (`PipelineState` TypedDict) + `nodes/` (23 stage functions, one file each — ~50 lines avg) + `hitl.py` (gate primitives, token derivation) + `checkpointer.py` (Postgres/DynamoDB factory) + `llm_client.py` (`SonnetClient` via `boto3` + `FakeSonnetClient`) + `gateway_client.py` (`GatewayClient` Protocol + `M6GatewayClient` HTTP impl + `FakeGatewayClient`) + `audit_client.py` (new in v0.2.0 — `AuditClient` Protocol + `M10AuditClient` HTTP impl + `FakeAuditClient` — replaces the invented `GatewayClient.emit_audit` per Required Fix 4) + `audit_emit.py` (per-stage audit-line construction) + `errors.py` (`VALID_REASON_CODES`) + `models.py` (shared pydantic models) per ARCH-03 / ARCH-09 size budget; ~1,850 lines of spec (v0.2.0, +296 over v0.1.0 for fix traceability + expanded M6 response-handling + AuditClient protocol + SHARED-WITH amendments).

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.1.0 | 2026-05-18 | Initial draft. Targets ≥ 7.5/10 GO on LLMJ-v1. Establishes: (1) 23-stage LangGraph `StateGraph` with stages pinned to 006 pipeline.py — **renamed stage 12 to `stage_12_cross_source_synthesis` and stage 21 to `stage_21_anti_fabrication_check` (drift vs 006)**; (2) 3 HITL gates at stages 7, 13, 21 matching 006 `HITL_STAGES`; (3) Pluggable `Checkpointer` — PostgreSQL default; (4) Map-reduce via `Send` API at stage 8; (5) Bedrock Claude Sonnet via `boto3` Converse API; (6) All MCP tool calls through M6 via injected `GatewayClient` Protocol; (7) Per-stage audit write to M10 via `GatewayClient.emit_audit` **(REMOVED in v0.2.0 — Required Fix 4 showed M6 exports no such method)**; (8) Token budget table per stage; (9) Closed frozen `VALID_REASON_CODES` set (**20 codes in v0.1.0**); (10) Positive-allow-list module boundary; AST scan. |
| **0.2.0** | **2026-05-20** | **LLMJ-v1 fix pass (12 Required + 5 Recommended).** (1) **Req-Fix 1-2 — M6 `GatewayRequest`/`GatewayResponse` shape:** v0.1.0 incorrectly modeled both as Pydantic v2. Real M6 exports them as `@dataclass(frozen=True)`. v0.2.0 drops the Pydantic copy; M8 defines a `GatewayRequest` dataclass (field-for-field compatible with M6's) + a thin `VendorAdapter`-resolver seam so `vendor_adapter` is never `None` at construction. AC7.2 rewritten. Task 20 asserts via `dataclasses.fields()` introspection. **SHARED-WITH-M6:** M6 v0.3.0 should expose a "server-side adapter resolution" mode (`VendorAdapterRegistry.resolve(tool_name)`), making M8's client shim optional. (2) **Req-Fix 3 — failure paths RAISE `GatewayError`:** v0.1.0's `GatewayResponse.decision == "DENY"` / `reason == "vendor_unavailable"` branches were unreachable. v0.2.0 rewrites §M6 Gateway Call Pattern Response Handling to `try / except GatewayError as exc` with branch on `exc.reason` ∈ `VALID_GATEWAY_REASONS`. AC7.7, AC7.8, AC7.9 rewritten. (3) **Req-Fix 4 — audit fan-out decoupled from M6:** v0.1.0 invented `GatewayClient.emit_audit(...)` which does not exist on `TrustAwareGateway`. v0.2.0 introduces a separate `AuditClient` Protocol with `M10AuditClient` (talks to M10's FastAPI `/audit` route) + `FakeAuditClient`. **SHARED-WITH-M10:** M10 v0.3.0 exposes the REST endpoint (spec'd in M10 section R3.x). AC7.1 / AC18.2 / §Integration Point with M10 rewritten. AC15.1 `__all__` gains `AuditClient`, `M10AuditClient`, `FakeAuditClient` (now 24 names, up from 21). (4) **Req-Fix 5 — `Holding.cost_basis_method` moved to `TaxLot`:** v0.1.0 invariant walked a field that does not exist on `Holding` per `src/m3_schema_registry/types.py` line 719-721. v0.2.0 rewrites State Field Invariant "Cost basis preservation" to walk `holding.tax_lots[*].cost_basis_method`. A12 invariant, Task 11 test, Error Code Map row 20 trigger, State Schema comment, AC12.2 allow-list (drops `ComplianceCheck` — see Fix 9; adds `TaxLot`) all updated. (5) **Req-Fix 6 — 006 stage-name rename justification:** v0.1.0 claimed "provenance continuity" but silently renamed stage 12 (006: `_stage_12_sentiment_synthesis`) and stage 21 (006: `_stage_21_final_approval_gate`). v0.2.0 keeps the v0.2.0 names (they better describe the v0.2.0 behaviour — stage 12 IS a reduce across all sources, stage 21 IS the anti-fab + HITL hybrid), drops "verbatim preservation" framing, adds DECISION-LOG D13 documenting both renames. Phase 2 Scope bullet 1 updated. (6) **Req-Fix 7 — 10-vs-20 reason code reconciliation:** v0.1.0 said "10 codes" in three places, "20 codes" in three places. Global sweep: Changelog bullet 9 (above), Phase 2 Scope bullet 9, R11 header, D7 decision log → all say 20. (7) **Req-Fix 8 — LangGraph import path + version pin:** `langgraph.constants.Send` deprecated since V1.0 (verified on `langgraph==0.6.6`). Skeleton B.2 updated to `from langgraph.types import Send`. Version pin bumped to `>= 0.4, < 2.0` (covers V1.0 stable line). AC12.7 rewritten. (8) **Req-Fix 9 — `ComplianceCheck` drop:** v0.1.0's `PipelineState.compliance_check: Optional[ComplianceCheck]` was never populated; `ComplianceCheck` is not in v0.2.0's AC12.2 allow-list. Stage 20 emits `compliance_decision` + `compliance_rule_applied` + `compliance_wsp_section` + `compliance_escalation` which suffice. State schema slimmed. (9) **Req-Fix 10 — ARCH-04 v2 `langchain-aws` deviation:** v0.1.0 buried this in DECISION-LOG D12. v0.2.0 elevates to Known Blockers row 17 with an explicit "ARCH-04 v2 update requested" status. (10) **Req-Fix 11 — AC13.5 tightening:** `print(` allow-list now requires "digest-only audit line; raw payload never printed" + source-level assertion. (11) **Req-Fix 12 — HITL HMAC key rotation contract:** new AC4.12 documents pod-restart-triggered key re-fetch + quarterly rotation cadence. (12) **Recommended Fixes 1-5:** R1 → AC5.8 (zero-fan-out stage 8 case); R2 → A24 invariant (compliance_escalation survives checkpoint round-trip, Task 9); R3 → per-task reason-code coverage matrix (Tasks 14/16/17); R4 → Hypothesis CI budget `max_examples=20` (local 50); R5 → `interrupt()` → checkpointer write order regression test (Task 9 extension). Section §Review Fix Traceability populated with 12 rows. |

---

## Architecture Clarification: M8 is a Stateful-but-Pure LangGraph Library Consumed by M12

ARCH-04 v2 §M8 Pipeline Engine (LangGraph) pins the framework. ARCH-09 dependency matrix (lines 302-315) shows:

```
Row M8    (M8 calls...):    .  *  .  .  *  *  .  .  .  *  .  .  .
                            M1 M2 M3 M4 M5 M6 M7 M8 M9 M10 M11 M12 M13
Col M8    (...who calls M8): .  .  .  .  .  .  .  .  .  .   .   *   .
```

**This is the single source of truth.** M8 calls M2, M5, M6, M10 at runtime (not via Python imports — via `GatewayClient` + `AuditClient` HTTP/mTLS calls to those modules). M8 is called by M12 only. v0.2.0 is authored directly against this matrix — no subsequent realignment needed.

- **M8 is a LangGraph library** — a `StateGraph` definition plus a `research_pipeline: CompiledGraph` singleton plus a synchronous `run(initial_state, thread_id) -> PipelineResult` wrapper. The `StateGraph` is defined at module import time; the `Checkpointer` is attached at `compile()` time from `PipelineConfig`. Not an HTTP server. Not a FastAPI app. No `uvicorn`, no `fastapi` imports.
- **M8 is called by M12 Supervisor Runtime.** Per ARCH-08 §Journey step 5: `M12 → M8 Pipeline (private subnet A, mTLS)`. M12 constructs the initial `PipelineState` from the `RoutingDecision` it received from M9, then calls `research_pipeline.run(initial_state, thread_id=decision.trace_id)`. M8 is the library that owns the 23-stage graph; M12 is the runtime that owns the event loop.
- **M8 never calls M9.** ARCH-09 row M8 column M9 = `.`. M9's `RoutingDecision` is passed to M8 as part of the initial `PipelineState` — M8 reads `state.routing_decision`, never invokes `m9_intent_router.route()`. M8 imports from `m9_intent_router.models` for type annotations only. AST scan (R12 AC12.6) forbids any runtime reference.
- **M8 never calls MCP servers directly.** Every MCP tool call goes through M6's `TrustAwareGateway.call(GatewayRequest) -> GatewayResponse` — failure paths **RAISE `GatewayError`** per v0.2.0 Required Fix 3, not return DENY-shaped responses. M8 holds a `GatewayClient` Protocol reference (not an `m6_mcp_gateway` import — a Protocol-shaped adapter injected at `compile()` time). Steering Rule 4 + Rule 7 enforced by R7 + R12 + AST scan.
- **M8 never imports M11.** M11 REST adapters are M6's downstream vendor concern. M8 names tools by their M6-registered name (e.g., `sec_edgar.fetch_10k`, `bloomberg.market_data`, `salesforce.fetch_client`) and lets M6 dispatch.
- **M8 never imports M10.** M8 emits audit events by calling `AuditClient.emit(entry: StageAuditPayload) -> None` — a separate Protocol (added in v0.2.0 per Required Fix 4). `M10AuditClient` is the production impl talking to M10's FastAPI `/audit` endpoint directly (mTLS, private subnet). The earlier v0.1.0 design of piggy-backing audit on `GatewayClient.emit_audit()` is withdrawn — M6's `TrustAwareGateway` has no such method. M10 writes the 3-tier WORM (Langfuse + S3 Object Lock + CRM).
- **M8 does NOT make compliance decisions.** Stage 20 (compliance screening) calls M2/M4 via M6's `action="compliance.screen"` — M8 receives a `GatewayResponse.decision` value (`ALLOW` / `ESCALATE`) on the success path, or catches `GatewayError("authority_denied")` / `GatewayError("authority_escalated")` on the failure path, and branches accordingly. M8 never runs OPA. Never runs Rego. Never interprets policy rules. Steering Rule 5 + Rule 14.
- **M8 does NOT answer the user.** M8 produces a `ResearchBrief` (M3 canonical type) — M12 is responsible for marshaling the brief to the channel. Stage 23 is a terminal audit write; the `PipelineResult` returned to M12 carries the brief plus metadata.
- **M8 is runtime-agnostic.** Managed Agents (Cloud Tier 3/4) and Strands (hybrid Tier 2/5) both have their Supervisor call `research_pipeline.run()` identically. Runtime swap is a Helm values toggle per ARCH-07 §Agent Runtime Matrix.
- **M8 is deterministic-modulo-LLM.** Given the same `(initial_state, thread_id, Checkpointer, GatewayClient, AuditClient, LLMClient)`, M8 produces the same graph structure, the same sequence of M6 tool calls, the same HITL-gate emissions, and the same audit payload shapes. The sole non-deterministic element is the Bedrock Sonnet response itself (and `datetime.utcnow()` — captured in `PipelineState.clock_stamps[stage_n]`). Test suites use `FakeSonnetClient` + `FakeGatewayClient` + `FakeAuditClient` for byte-identical reproducibility.

M8 does NOT import from M1, M2, M4, M6, M7, M10, M11, M12, M13, `compliance.gap2`, `compliance.gap6`. M8 imports ONLY from `m3_schema_registry` (canonical types), `m5_config_loader` (`Archetype`, `Runtime`, `SpecialistConfig`, `PipelineConfig`), and `m9_intent_router.models` (type-annotation-only: `RoutingDecision`, `SelectedTarget`, `IntentCategory`).

---

## Phase 2 Scope

Per `docs/007-consolidated-design-and-plan.md` Part 11 and the Phase 2 plan in ARCH-09 (Week 14-36, 7-person team, 24-week window), M8 Phase 2 scope covers:

- **23-stage research pipeline** — every stage enumerated in §FSI Pipeline Stage Catalog. v0.1.0 claimed verbatim preservation from 006 `_all_stage_methods()`; v0.2.0 (per Required Fix 6) acknowledges two deliberate renames against 006: stage 12 (`_stage_12_sentiment_synthesis` → `stage_12_cross_source_synthesis`) and stage 21 (`_stage_21_final_approval_gate` → `stage_21_anti_fabrication_check`). Both renames are justified in DECISION-LOG D13 and reflect semantic drift between 006's single-source sentiment synthesis and 007's map-reduce cross-source synthesis; and between 006's HITL-only gate and 007's combined anti-fab-scan + HITL-gate at stage 21. Stage numbers (1-23) remain stable as the authoritative identifier; stage names are secondary.
- **3 HITL gates** at stages 7, 13, 21 — matches 006 `HITL_STAGES = {7, 13, 21}` (verified 006 v2 `pipeline.py` line 58). Approver roles pinned per §HITL Gate Specification.
- **LangGraph `StateGraph` with `PipelineState` TypedDict** — see §LangGraph State Schema.
- **Pluggable `Checkpointer`** — `langgraph-checkpoint-postgres` default for Phase 2 cloud (RDS) and on-prem (local PostgreSQL 16). `langgraph-checkpoint-dynamodb` reserved as a Protocol-satisfying stub for Phase 3. Fail-closed on checkpoint write failure (R3).
- **One LLM provider live** — `SonnetClient` wrapping `boto3` Bedrock Runtime `converse` API. Three additional providers (`AzureOpenAIClient`, `VertexClient`, `VllmClient`) are reserved as Protocol-satisfying stubs for Phase 3+.
- **One map-reduce fan-out** — stage 8 uses LangGraph `Send` API for per-instrument parallel research (up to 10 instruments); stage 12 aggregates (reduce). Zero-fan-out case (zero discovered instruments) is spec'd explicitly in AC5.8 (Recommended Fix 1).
- **One integration point** — M12 Supervisor Runtime (direct in-process call, no FastAPI; M12 imports and calls `research_pipeline.run()` synchronously, wrapping in `asyncio.to_thread` if needed).
- **One config-source amendment** — SHARED-WITH-M5: `PipelineConfig` sub-model added to M5 config schema. See §Known Blockers row 1.
- **Per-stage audit emission** — every stage emits one structured audit line via the `AuditClient` Protocol (new in v0.2.0 per Required Fix 4 — replaces the invented `GatewayClient.emit_audit` seam). Audit shape pinned in §Integration Point with M10 (ARCH-06 v3 Gap 2 row).
- **Closed frozen error vocabulary** — **20 `reason_code` values** (R11). v0.1.0 drafted 10 initially then expanded to 20; v0.2.0 sweeps every textual reference to make this consistent (Required Fix 7).
- **Anti-fabrication check** at stage 21 — every numeric claim in the draft `ResearchBrief` MUST trace back to a `ResearchSource` entry; missing provenance → `m8_anti_fabrication_failed` + HITL escalation. Ported directly from 006 `data_sources` ledger pattern.

### Explicitly OUT of scope (deferred to "M8-lighthouse-2" in Phase 3 or later)

- **Strands v2 research specialist** — ARCH-10 Decision 2 documents a parallel v2 rewrite as a Strands agent with 23 tools. M8 Phase 2 ships the LangGraph v1. The config toggle selecting v1 vs v2 lives in M5 (`SpecialistConfig.research_specialist_version: Literal["v1_langgraph", "v2_strands"]` — default `"v1_langgraph"` in Phase 2). v2 is a separate module not built by this spec.
- **DynamoDB checkpointer live** — Protocol-level stub only. Phase 3 wires `langgraph-checkpoint-dynamodb` with Gateway Endpoint networking per ARCH-08 §3.1.
- **Non-Bedrock LLM providers live** — Protocol-level stubs only. Phase 3 wires `AzureOpenAIClient`, `VertexClient`, `VllmClient`.
- **Time-travel debugging UI** — LangGraph provides the primitives (historical checkpoints keyed by `thread_id + checkpoint_ns`). The operator UI to replay from an arbitrary checkpoint is Phase 3 work.
- **Multi-tenant concurrency admission** — Steering Rule 11 caps 3 concurrent research pipelines per tenant. Phase 2 implements a tenant-scoped semaphore (R11 AC11.5). Queue overflow handling + dashboarding is Phase 3.
- **Pipeline stage reconfiguration via config** — Phase 2 hardcodes the 23-stage graph. Phase 3 may allow per-archetype stage subsets (e.g., single-tool market query pipeline skipping SEC filings).
- **Hierarchical RAG over 10-K filings** — RES-08 §Context Window Management proposes pre-indexing 10-Ks into pgvector. Phase 2 fetches 10-K chunks on-demand via M6 `sec_edgar.fetch_10k` with explicit `max_tokens` trimming at stage 5. Vector retrieval is Phase 3.
- **MetaClaw cross-run lesson capture** — 006 v2 `apply_lessons` / `record_lesson` is a learning layer. Phase 2 M8 does NOT implement lesson capture; all 23 stages are stateless-per-run. Phase 3+ reinstates.
- **Custom prompt-template hot-reload** — prompt templates are loaded at module import time from `src/m8_pipeline_engine/prompts/*.jinja` (Phase 2). Hot-reload from M5 is Phase 3.
- **Fine-grained budget enforcement beyond `maxTokens`** — Phase 2 caps `maxTokens` per stage via Bedrock Converse `inferenceConfig`. Input token counting + pre-flight trimming is Phase 3.
- **Cross-pipeline resumption** — if M8 crashes mid-stage, `thread_id` allows resumption on pod restart. Cross-pipeline trigger chains (pipeline A output → pipeline B input) are Phase 3.

---

## Known Blockers & Pending Items

Per ARCH-04 v2, ARCH-09, IMPL-06, and Steering Rule 15. Each maps to a DECISION-LOG entry in `src/m8_pipeline_engine/DECISION-LOG.md` (R17 AC17.4).

| # | Area | Question | Impact on M8 | Status |
|---|------|----------|--------------|--------|
| 1 | **M5 `PipelineConfig` sub-model (SHARED-WITH-M5)** | M8 needs a config object with fields `checkpointer_backend: Literal["postgres","dynamodb"]`, `checkpointer_dsn_vault_path: str`, `model_id: str`, `model_provider: Literal["bedrock","azure_openai","vertex","vllm"]`, `region: str` (default `"us-east-1"`), `hitl_timeout_seconds: int` (default 14400 = 4h), `max_concurrent_instruments: int` (default 10), `max_pipeline_wall_clock_seconds: int` (default 1200 = 20 min), `alert_pipeline_wall_clock_seconds: int` (default 900 = 15 min), `token_budgets: dict[str, int]`, `gateway_base_url: str`, `gateway_mtls_client_cert_path: str`, `hitl_hmac_key_vault_path: str`, `audit_base_url: str` (new in v0.2.0 per Required Fix 4 — M10 FastAPI endpoint), `audit_mtls_client_cert_path: str`. M5 v0.3.0 does NOT currently expose this sub-model. | Resolution: M5 adds `PipelineConfig` under `SpecialistConfig` (sibling of `IntentRouterConfig` added for M9). M8 v0.2.0 uses positive-allow-list import `from m5_config_loader import PipelineConfig` and fails AC12.4 AST-import scan until M5 v0.4.0 ships it. Integration-test gate: `tests/integration/test_m8_m5_config_shape.py` (xfail until M5 v0.4.0). | **SHARED-WITH-M5** — M5 to resolve in v0.4.0. Spec'd ETA tied to Phase 2 Week 30 per ARCH-09 build order. |
| 2 | **Bedrock Claude Sonnet model ID** | ARCH-07 pins "Bedrock Claude Sonnet" without a versioned model ID. v0.2.0 tentatively pins `"anthropic.claude-sonnet-4-5-20250929-v1:0"` (paralleling 006 v2's Sonnet 4.6 era; exact Bedrock model ID may differ). | All `SonnetClient.generate` calls carry this model ID. If deployed Bedrock region does not advertise it, the adapter raises `LlmProviderError` → stage fails with `m8_llm_5xx` → HITL escalation. No crash. Task 18 first-live-call probe records actual ID in DECISION-LOG. | **PENDING-VERIFICATION** — first-live-call probe at Task 18. DECISION-LOG records live ID on mismatch. |
| 3 | **Bedrock Converse JSON-mode for Sonnet synthesis** | Sonnet synthesis stages (9, 10, 12, 13, 14, 15, 16, 17, 18, 19) do NOT use `tool_use` — they emit freeform text with structured JSON output. Bedrock Converse supports JSON mode via `additionalModelRequestFields={"response_format": {"type": "json_object"}}` (subject to Bedrock release). | Risk: if Bedrock rejects JSON-mode on Sonnet, synthesis stages fall back to regex-extracted JSON (fragile). Task 7 ships a "first live call" fixture. Until verified, Task 18 is gated. | **PENDING-VERIFICATION** — first-live-call at Task 18. |
| 4 | **LangGraph `Checkpointer` Postgres schema segregation** | `langgraph-checkpoint-postgres` ships with a default schema (`checkpoints` + `checkpoint_writes` + `checkpoint_migrations` tables). RDS PostgreSQL lives in a shared `fsi007` DB alongside M1, M3. Schema collision risk with M10 Langfuse tables. | Resolution: M8 checkpointer schema lives in a dedicated PostgreSQL schema `m8_checkpoints` (not `public`). DSN is `postgresql://fsi007:<vault-resolved>@<rds-endpoint>/fsi007?options=-csearch_path%3Dm8_checkpoints`. Task 17 asserts schema segregation. DBA sign-off required before Phase 2 Week 30 bring-up. | **PENDING-WITH-DBA** — schema plan drafted; DBA to confirm during Phase 2 Week 28 infrastructure bring-up. |
| 5 | **M2/M4 OPA policy IDs used at Stage 20** | Stage 20 calls `action="compliance.screen"` with `target={"canonical_type": "ResearchBrief", "ticker": ..., "client_id": ...}` through M6. M2/M4 OPA policy IDs used at this stage are TBD. | M8 treats the returned `Decision` value (`ALLOW`/`DENY`/`ESCALATE`) as opaque. Policy-ID specificity is M2/M4's concern. M8 only forwards `rule_applied` + `wsp_section` into audit. | **SHARED-WITH-COMPLIANCE-LAYER** — M2/M4 owns the policy-ID list. M8 does not block on this. |
| 6 | **M6 `GatewayClient` wire shape — v0.2.0 corrected** | v0.1.0 misread `TrustAwareGateway` as a Protocol and invented a Pydantic wrapper for `GatewayRequest` / `GatewayResponse`. Real M6 (`src/m6_mcp_gateway/gateway.py` lines 118 + 221) exports both as `@dataclass(frozen=True)`. v0.2.0 corrects this: M8 defines its own `GatewayRequest` as a field-for-field compatible `@dataclass(frozen=True)` (not Pydantic), avoiding an `m6_mcp_gateway` import. Cross-module shape-match test (Task 20) asserts `dataclasses.fields()` equality. | **SHARED-WITH-M6-A:** `GatewayRequest.vendor_adapter` is REQUIRED and non-None per M6's `__post_init__`. M8 does not know which vendor-adapter instance handles which `tool_name` — that resolution lives in M6. Two resolutions available: **(a)** M6 v0.3.0 adds a server-side `VendorAdapterRegistry.resolve(tool_name) -> VendorAdapter` accessible via a new `GatewayClient.call_with_resolution(request_without_adapter)` helper — preferred; **(b)** M6 publishes a `VendorAdapterRegistry` instance that M8 receives at `compile()` time and calls `registry.resolve(tool_name)` to fill the field locally before calling `.call()`. v0.2.0 specs (b) as the Phase 2 path (AC7.3 `M6GatewayClient` wraps a registry ref) and flags (a) as the Phase 3 simplification. | **SHARED-WITH-M6** — M6 v0.3.0 to resolve. Phase 2 workaround viable with (b). |
| 7 | **23-stage final count authority** | ARCH-09 + ARCH-07 + Part 7 of 007-consolidated pin "23 stages". 006 v2 `pipeline.py` (verified 2026-05-17 at line 160-174) enumerates exactly 23 stages: `_stage_1_intake` through `_stage_23_delivery_notify`. v0.2.0 preserves this count; stage numbers match 006 one-to-one; two stage NAMES (12, 21) are renamed — see DECISION-LOG D13. | No change from 007 architecture. Stage catalog below is authoritative. Stage NUMBER is the stable identifier for audit and cross-module reference. | **RESOLVED** — 23 stages verified against 006 v2 source. |
| 8 | **HITL gates — timeout + escalation policy** | Steering Rule 8 requires fail-closed on timeout. 006 v2 `config.arc.yaml` documents a 4-hour default. ARCH-08 §Capacity doesn't publish an explicit timeout ceiling. v0.2.0 pins 4 hours (14,400 seconds) as `PipelineConfig.hitl_timeout_seconds`. | On timeout: pipeline marked `TIMED_OUT`, final audit event `reason_code="m8_hitl_timeout"`, `PipelineResult.status="timed_out"`. M12 re-surfaces to channel as escalation. | **RESOLVED** — 4h default, config-driven. |
| 9 | **HITL approval token algorithm** | 007 Steering (Trust Layer paragraph) pins `SHA-256(gate_id + approver_id + timestamp)`. 006 v2 MuleSoft rule set pins HMAC-SHA-256 with 5-min TTL. M8's HITL gate tokens serve a different purpose (research pipeline gate approval — not MuleSoft action execution). v0.2.0 uses **HMAC-SHA-256(vault-resolved key, f"{gate_id}\|{approver_aid_sub}\|{iso_timestamp}\|{thread_id}")** — tamper-proof against forgery. Key lives at `PipelineConfig.hitl_hmac_key_vault_path`. TTL: `PipelineConfig.hitl_timeout_seconds`. Rotation cadence per AC4.12. | R4 AC4.5 pins the algorithm. AC4.6 asserts key is fetched from Vault, not env. AC4.12 (new in v0.2.0) pins rotation. Task 8 exercises token verification across wall-clock boundaries (TTL expiry) and key-rotation boundaries. | **RESOLVED** — HMAC-SHA-256 with Vault-resolved key, quarterly rotation. |
| 10 | **Stage 8 map-reduce fan-out width** | LangGraph `Send` API supports arbitrary fan-out, but Bedrock Sonnet regional TPS cap under sustained multi-instrument fan-out can trigger 429s. v0.2.0 caps `max_concurrent_instruments=10` from `PipelineConfig`. Discovery at stage 4 that returns more than 10 instruments → sorted by mentioned-count and top 10 retained; dropped instruments listed in `PipelineState.dropped_instruments` for audit. Zero-instrument case per AC5.8 (new in v0.2.0). | Preserves Bedrock TPS budget. Phase 3 may allow tenant-scoped caps. | **RESOLVED** — cap at 10, configurable, documented. |
| 11 | **20-minute wall-clock ceiling (Steering Rule 11 implication)** | ARCH-07 §SLA Targets pins M8 full run `<20 min` (alert at `>20 min for 5 min`). Steering Rule 11 requires async dispatch. v0.2.0 treats 20 min as a HARD ceiling (`max_pipeline_wall_clock_seconds=1200`); 15 min as an alert threshold (`alert_pipeline_wall_clock_seconds=900`). At hard ceiling, current stage is aborted, pipeline marked `TIMED_OUT`, final audit emits `reason_code="m8_wall_clock_exceeded"`. | Wall-clock is measured outside HITL gate time — HITL gate wall time does not count toward the ceiling (otherwise every HITL pipeline would always timeout). Task 13 exercises the ceiling with `FakeSonnetClient(delay_ms=...)`. | **RESOLVED** — hard ceiling excludes HITL wait time; configurable. |
| 12 | **Anti-fabrication check mechanism** | 006 v2 pipeline enforced "every number in the final brief MUST trace back to `self.data_sources`". M8 v0.2.0 ports this as Stage 21 `_stage_21_anti_fabrication_check`: walks `PipelineState.draft_brief`, extracts every numeric token via regex, asserts each is present in some `ResearchSource.raw_excerpt` within `PipelineState.data_sources`. | Failure → `reason_code="m8_anti_fabrication_failed"` → HITL gate 3 escalation (advisor manually reviews). Anti-fabrication is a guardrail, not a hard fail. | **RESOLVED** — ported from 006 pattern. |
| 13 | **Checkpointer schema migrations** | `langgraph-checkpoint-postgres` ships schema migrations. Deployment pipeline runs them at pod startup. Risk: mid-deploy pipelines holding open checkpoints during migration. | Resolution: migrations run from a dedicated migration Job (not the M8 pod startup). M8 pods start with readiness probe checking `checkpointer.ready()`. Task 17 asserts migration runbook shipped. | **PENDING-WITH-DEVOPS** — migration runbook deferred to Phase 2 Week 30 DevOps sprint. |
| 14 | **Per-stage prompt template versioning** | ARCH-06 v3 Gap 2 row "M8 Pipeline" requires `prompt_template_version` in audit. v0.2.0 pins each prompt to a hash-of-content plus a semantic version: `{stage_name}_prompt_v{major}.{minor}.{patch}_{sha256[:8]}`. Prompt files live at `src/m8_pipeline_engine/prompts/{stage_name}.jinja` with a companion `{stage_name}.version` file. | Every audit row carries `prompt_template_version`. Changing a prompt = version bump. Task 10 asserts every LLM-bearing stage has a matching prompt file + version file. | **RESOLVED** — version-file pattern. |
| 15 | **SHA algorithm migration seam (FIPS / post-quantum)** | Current hash is `hashlib.sha256(...)`. Future FIPS mode or post-quantum forcing may require SHA-3 / BLAKE3. | `audit_emit.compute_io_digest()` is a single function — migration is a one-file change + SCHEMA_VERSION MAJOR bump. | **RESOLVED** — single-seam refactor. |
| 16 | **Concurrent pipeline cap (Steering Rule 11 — 3 per tenant)** | Steering Rule 11 requires 3 concurrent per tenant. M8 enforces via a module-level `dict[str, threading.Semaphore]` keyed by `tenant_id` (from `PipelineState.tenant_id`). Semaphore(3). Queue beyond limit — v0.2.0 BLOCKS with `threading.Semaphore.acquire(timeout=60)` and on timeout emits `reason_code="m8_tenant_concurrency_exceeded"`. | Phase 3 may replace with a proper queue (Redis-backed). Phase 2 block-with-timeout is simple and Steering-Rule-11 compliant. | **RESOLVED** — `threading.Semaphore(3)` per tenant, 60s wait timeout. |
| 17 | **ARCH-04 v2 `langchain-aws` deviation (Req-Fix 10)** | ARCH-04 v2 §M8 "Key Libraries" lists `langgraph + langchain-aws`. v0.2.0 uses `boto3` Bedrock Runtime `converse` directly — NOT `langchain-aws`. Rationale: `langchain-aws` pulls the `langchain` umbrella which couples M8 to LangChain's abstraction shape, violating Steering Rule 15 (provider abstraction must be M8's own `LLMClient` Protocol, not LangChain's `BaseChatModel`). | v0.1.0 buried this in DECISION-LOG D12. v0.2.0 elevates to this Known Blockers row with explicit ARCH-04 v2 update request. Dependency on architecture team to revise ARCH-04 v2 "Key Libraries" to read `langgraph + boto3 (Bedrock Runtime)`. Until revised, M8 is technically non-compliant with ARCH-04 v2 as written, but compliant with its intent (Sonnet on Bedrock). | **PENDING-ARCH-04-UPDATE** — architecture team to revise ARCH-04 v2 §M8 "Key Libraries". M8 ships as spec'd. |
| 18 | **M10 `/audit` FastAPI route (SHARED-WITH-M10, Req-Fix 4)** | v0.2.0 introduces a separate `AuditClient` Protocol — `M10AuditClient` talks to M10's FastAPI `POST /audit` endpoint over mTLS. M10 v0.2.0 does not yet expose this route. | Resolution: M10 v0.3.0 adds `POST /audit` accepting JSON-serialized `StageAuditPayload` + `PipelineTerminalAuditPayload` shapes; returns `202 Accepted` on queued-for-3-tier-write, `5xx` on unavailability. `M10AuditClient` retries once on 5xx, then raises `AuditEmitError` → M8 emits `m8_audit_write_failed` + terminates. Integration gate: `tests/integration/test_m8_m10_audit_contract.py` (xfail until M10 v0.3.0). | **SHARED-WITH-M10** — M10 v0.3.0 to expose `/audit`. |

---

## Steering Rules M8 Must Honor

| Rule # | Rule | Addressed In |
|--------|------|--------------|
| **4** | Every MCP call MUST pass through M6 Trust-Aware Gateway. | R7 (`GatewayClient` Protocol — all tool calls routed through M6), R12 (no M11 import), §Architecture Clarification bullet 4, §M6 Gateway Call Pattern, Task 6 AST scan asserts no direct vendor SDK. |
| **5** | M2/M4 policy evaluation is OPA/Rego ONLY. Compliance checks are NEVER done by LLM. | R4 AC4.9 (Stage 20 calls `action="compliance.screen"` via M6; M8 receives Decision value and branches), §FSI Pipeline Stage Catalog Stage 20 row explicit "NO LLM — OPA via M6". |
| **6** | M10 audit writes to THREE tiers: Langfuse + S3 Object Lock WORM + CRM. All three required. | R8 (per-stage audit via `AuditClient.emit` — M10 fans out to 3 tiers internally; M8 is unaware of the 3-tier split, responsibility delegated), §Integration Point with M10. |
| **7** | MNPI fields NEVER sent to LLM prompts or agent memory unfiltered. | R7 AC7.5 (every M6 call response goes through M4 filtering before M8 sees it — M8 receives already-filtered data; redaction is M6's concern), R7 AC7.6 (M8 never logs raw LLM prompt input bodies — only `input_sha256` digests), §M6 Gateway Call Pattern. |
| **8** | Fail-closed on ANY compliance check failure. | R4 AC4.3 (HITL timeout → `TIMED_OUT`), R3 AC3.5 (checkpoint write failure → `TERMINATED`), R4 AC4.4 (HITL rejection → `REJECTED`), R7 AC7.8 (M6 raises `GatewayError("authority_denied")` → stage fails hard, `reason_code="m8_compliance_denied"`), R11 (closed reason-code set). |
| **13** | Bedrock Claude Sonnet for research. Bedrock Claude Haiku for routing/conversation/execution. | R6 (`SonnetClient` — all LLM-bearing M8 stages use Sonnet), §Token Budget Table (model column = Sonnet for all LLM stages), §Known Blockers row 2 (model ID verification), Task 7. |
| **14** | NO LLM for compliance (M2/M4 is deterministic OPA). | R4 AC4.9 (Stage 20 via M6 → M2/M4 OPA; no Sonnet call), §FSI Pipeline Stage Catalog Stage 20. |
| **15** | LLM provider is abstracted. Swappable via config. | R6 (`LLMClient` Protocol + `SonnetClient` + `FakeSonnetClient` + three reserved stubs), §LLM Provider Abstraction. |
| **20** | Zero credentials in git. All secrets via HashiCorp Vault or AWS Secrets Manager. | R14 (IRSA / Vault resolution via `boto3` default credential chain for Bedrock AND Vault-path resolution for HITL HMAC key AND Vault-path resolution for Checkpointer DSN; AST scan), AC14.1-14.8. |
| **32** | SECURITY PER MODULE: no credentials, Pydantic-validated inputs, MNPI filtered, audit logged, cost_basis never null. | R7 (no direct vendor calls; MNPI filter is M6's job), R8 (audit per stage with I/O digests — ARCH-06 v3 Gap 2 row), R12 (module boundary), R13 (forbidden imports), R14 (zero credentials). `cost_basis_method` is M7's concern (M7 populates it on each `TaxLot` before M8 sees a `Holding`); M8 validates at state-update time per A12. |

---

## Requirements

### R1. Public Entry Point — `research_pipeline.run(initial_state, thread_id) -> PipelineResult`

M8 exposes one public entry point. It is a pure function apart from: (a) M6 tool calls via `GatewayClient.call(...)`, (b) M10 audit writes via `AuditClient.emit(...)` (new in v0.2.0 per Required Fix 4 — was `GatewayClient.emit_audit` in v0.1.0), (c) LangGraph `Checkpointer` writes to PostgreSQL, (d) Bedrock `converse` calls via `SonnetClient`, (e) `time.perf_counter()` / `datetime.utcnow()` captured in `PipelineState.clock_stamps`. No module-level mutable state, no global registry mutation.

**Acceptance Criteria:**
- **AC1.1:** `m8_pipeline_engine.research_pipeline.run(initial_state: PipelineState, thread_id: str) -> PipelineResult` is importable from the package root.
- **AC1.2:** `PipelineState` is a `TypedDict` (LangGraph `StateGraph` requirement) with `total=False` — every field is optional except `routing_decision`, `trace_id`, `tenant_id`, `thread_id`, `firm_id`, `pipeline_run_id`. Full field list in §LangGraph State Schema.
- **AC1.3:** `thread_id` MUST match regex `^[a-z0-9][a-z0-9\-]{7,63}$` (lowercase alphanumeric + hyphen, 8-64 chars). Invalid `thread_id` → `ValueError("invalid_thread_id")` raised synchronously before any checkpoint write or LLM call. This is a developer-error contract, not a runtime compliance branch.
- **AC1.4:** `run()` is synchronous. M12 may wrap in `asyncio.to_thread` if it needs an async interface. LangGraph's underlying event loop runs on the calling thread.
- **AC1.5:** `run()` is idempotent with respect to its inputs for the pure-function slice. Tenant semaphore acquisition (R16) is the sole side effect beyond the injected deps.
- **AC1.6:** `run()` does NOT mutate `initial_state`. LangGraph copy-on-write semantics enforced; Task 11 asserts `initial_state == initial_state_before_call` deep-equal post-`run()`.
- **AC1.7:** If `thread_id` matches an existing checkpoint, `run()` resumes from the last completed stage (LangGraph native behavior). Task 9 asserts.
- **AC1.8:** `run()` returns `PipelineResult(status: Literal["completed", "paused", "rejected", "timed_out", "terminated", "failed"], pipeline_run_id: str, thread_id: str, research_brief: Optional[ResearchBrief], final_stage: int, paused_gate: Optional[int], wall_clock_seconds: float, total_tokens: int, reason_code: Optional[str], dropped_instruments: list[str])`. Pydantic v2 model, `ConfigDict(frozen=True, extra="forbid")`.
- **AC1.9:** `run()` does NOT raise exceptions for compliance or operational failures — it returns `PipelineResult(status="failed", reason_code=...)`. The only exception class `run()` may raise is `ValueError` for developer-error inputs (AC1.3, AC1.10). Task 15 asserts.
- **AC1.10:** `initial_state.routing_decision.selected_target.kind == "pipeline"` — any other kind raises `ValueError("not_a_pipeline_intent")`. Task 15 asserts.
- **AC1.11:** `initial_state.routing_decision.selected_target.name` MUST match regex `^m8\.research_(pipeline_[1-3]|single_tool)$`. Unknown name → `ValueError("unknown_pipeline_name")`. Matches M9 AC18.3 PROPOSED names.
- **AC1.12:** `run()` wall-clock ceiling: `PipelineConfig.max_pipeline_wall_clock_seconds` (default 1200 = 20 min). Wall clock EXCLUDES HITL gate wait time. Breach → final audit row emits `reason_code="m8_wall_clock_exceeded"`, `PipelineResult.status="timed_out"`.

### R2. 23-Stage Pipeline (Pinned Stage List + State Transitions)

The pipeline is a LangGraph `StateGraph` with exactly 23 stage nodes plus START and END sentinels. Stage numbers 1-23 map one-to-one to 006 v2 `pipeline.py::_all_stage_methods()` (verified 2026-05-17, lines 160-174). Two stage NAMES (12, 21) are deliberately renamed vs 006 — see DECISION-LOG D13 and Phase 2 Scope bullet 1.

**Acceptance Criteria:**
- **AC2.1:** `src/m8_pipeline_engine/graph.py::build_graph()` returns a `langgraph.StateGraph[PipelineState]` with exactly 23 stage nodes registered. Node names match the stage catalog (lowercase snake_case: `stage_1_intake`, `stage_2_crm_context`, …, `stage_23_delivery_notify`).
- **AC2.2:** `STAGE_NAMES: tuple[str, ...]` is a module-level frozen tuple at `src/m8_pipeline_engine/__init__.py` with exactly 23 entries in execution order. `assert len(STAGE_NAMES) == 23`. Task 3 asserts.
- **AC2.3:** Sequential edges (STAGE_N → STAGE_N+1) exist for N in {1..6, 8..12, 14..20, 22..23}. Conditional edges exist at stages 7, 13, 21 (HITL gates — see R4). Map-reduce edges exist at stages 8 (fan-out) and 12 (fan-in).
- **AC2.4:** Every stage node signature is `def stage_N_name(state: PipelineState) -> dict[str, Any]` where the returned dict is a **partial state update** (LangGraph merge semantics). Stage functions MUST NOT mutate `state`.
- **AC2.5:** Every stage function is a pure function of `state`, the injected `GatewayClient` (for M6 calls), the injected `AuditClient` (for audit emission, new in v0.2.0) and the injected `LLMClient` (for Sonnet calls). No `time.sleep`, no `random.*`, no filesystem reads, no environment reads past module import time.
- **AC2.6:** Stage functions live at `src/m8_pipeline_engine/nodes/stage_N_name.py` — one file per stage. Task 2 AST scan enforces this directory shape.
- **AC2.7:** `STAGE_NAMES` is exported in `__all__` (R15). External modules (including M12) MUST use `STAGE_NAMES[N-1]` rather than hardcoding stage names — stage NUMBER is the stable cross-module identifier per §Stage Name Immutability Contract.
- **AC2.8:** `PIPELINE_NAMES: frozenset[str] = frozenset({"m8.research_pipeline_1", "m8.research_pipeline_2", "m8.research_pipeline_3", "m8.research_single_tool"})` — exported at module root for M9 cross-module version-match test (M9 Task 19). Any change to this set = MINOR bump; removal/rename = MAJOR bump.
- **AC2.9:** Every stage number 1..23 is represented exactly once in the graph. Task 3 meta-test: `assert set(range(1, 24)) == set(int(n.split("_")[1]) for n in STAGE_NAMES)`.

### R3. Checkpointer — PostgreSQL Default, DynamoDB Reserved, Fail-Closed on Write Failure

Pipeline state MUST survive pod restarts. LangGraph native `Checkpointer` to PostgreSQL (Phase 2) or DynamoDB (Phase 3) is used. Checkpoint write failure is a terminal condition — M8 does NOT retry silently; it emits `reason_code="m8_checkpoint_write_failed"` and returns `status="terminated"`.

**Acceptance Criteria:**
- **AC3.1:** `src/m8_pipeline_engine/checkpointer.py::build_checkpointer(config: PipelineConfig) -> langgraph.checkpoint.base.BaseCheckpointSaver` constructs the backend from `config.checkpointer_backend`. `"postgres"` → `PostgresSaver` from `langgraph-checkpoint-postgres`; `"dynamodb"` → `DynamoDbSaver` (reserved stub).
- **AC3.2:** The checkpointer DSN is resolved from Vault at process startup via `config.checkpointer_dsn_vault_path`. Cached; not re-fetched per call. If Vault returns empty bytes → `RuntimeError("m8_checkpointer_dsn_unresolved")` → pod readiness probe fails.
- **AC3.3:** PostgreSQL checkpoint schema is segregated: connection uses `search_path=m8_checkpoints`. AC17 integration test asserts schema isolation from M10 Langfuse tables.
- **AC3.4:** The compiled graph is built at module import time: `research_pipeline = build_graph().compile(checkpointer=_CHECKPOINTER)`. The `_CHECKPOINTER` is constructed once per process.
- **AC3.5:** On checkpoint write failure (exception from `checkpointer.put(...)`), the running pipeline: (a) emits a final audit row via `AuditClient.emit` with `reason_code="m8_checkpoint_write_failed"`, (b) returns `PipelineResult(status="terminated", reason_code="m8_checkpoint_write_failed", …)`. No silent retry. No partial state left in memory. Task 9 asserts via `FailingCheckpointer(fail_at_stage=N)`.
- **AC3.6:** The checkpointer is injectable for tests via `research_pipeline_with_checkpointer(ckpt: BaseCheckpointSaver) -> CompiledGraph`. Tests use `InMemorySaver` from `langgraph.checkpoint.memory`.
- **AC3.7:** Resumption: `run(initial_state, thread_id)` with a previously-seen `thread_id` resumes from the last persisted checkpoint. The `initial_state` argument is IGNORED on resumption (LangGraph behavior). Task 9 asserts state is that of the resumed thread.
- **AC3.8:** Checkpointer construction failures at module import time are fatal — the M8 import raises `RuntimeError("m8_checkpointer_unavailable")`. Pod readiness probe fails; Kubernetes restarts until config fixed.
- **AC3.9:** Reserved `DynamoDbSaver` stub: `__init__` raises `NotImplementedError("Phase 3")`. Signature satisfies LangGraph `BaseCheckpointSaver` Protocol.
- **AC3.10:** `state.compliance_escalation` (bool) survives checkpoint round-trip (Recommended Fix 2). A resumed pipeline at Gate 3 that was flagged escalation at Stage 20 MUST still see `state.compliance_escalation == True`. Task 9 asserts via `InMemorySaver` + serialized round-trip.

### R4. Three HITL Gates — Stages 7, 13, 21 — Tamper-Proof Approval Tokens — Fail-Closed on Timeout/Rejection

Stages 7, 13, 21 are HITL gates (verified against 006 v2 `pipeline.py` line 58 `HITL_STAGES = {7, 13, 21}`). At each gate, the graph pauses via LangGraph `interrupt()`, persists state via the Checkpointer, emits a notification audit event via `AuditClient`, and waits for resumption with a valid approval token. Each gate has a pinned approver role, timeout, and escalation policy.

**Acceptance Criteria:**
- **AC4.1:** `HITL_GATES: frozenset[int] = frozenset({7, 13, 21})` is exported in `__all__`. Meta-test asserts `HITL_GATES == {7, 13, 21}`.
- **AC4.2:** Each HITL gate node: (a) builds a `HitlGatePayload` (Pydantic v2 frozen model) with gate-specific fields, (b) emits an audit event via `AuditClient.emit` with `reason_code=None` (successful gate arrival, not a failure), (c) calls LangGraph `interrupt(payload)` to pause graph execution. LangGraph persists `PipelineState` to the checkpointer automatically. **Order invariant (Recommended Fix 5):** audit emission completes BEFORE the `interrupt()` call; `interrupt()` BEFORE the checkpointer `put()` fires (LangGraph internal). Task 9 asserts ordering via a spy `CheckpointerWithAuditSpy`.
- **AC4.3:** `resume_from_gate(thread_id: str, approval: HitlApproval) -> PipelineResult` is the public re-entry point. Accepts the same `thread_id` and an `HitlApproval(approver_aid_sub: str, approved: bool, approval_token: str, approver_timestamp: datetime, notes: Optional[str])` Pydantic model. Token verification is HMAC-SHA-256 (AC4.5).
- **AC4.4:** On `approval.approved=False`: pipeline emits final audit with `reason_code="m8_hitl_denied"`, returns `PipelineResult(status="rejected", paused_gate=N, reason_code="m8_hitl_denied")`. No further stages execute. No graph checkpoint is overwritten — the rejected state is preserved for compliance review.
- **AC4.5:** Approval token shape: `HMAC-SHA-256(vault_key, f"{gate_id}|{approver_aid_sub}|{approver_timestamp.isoformat()}|{thread_id}")`. Hex-encoded 64 chars. Verification is constant-time (`hmac.compare_digest`).
- **AC4.6:** The HITL HMAC key is fetched from Vault at process startup via `config.hitl_hmac_key_vault_path`. Cached. If absent at startup → `RuntimeError("m8_hitl_key_unresolved")` → pod readiness probe fails. Token verification with an empty key never succeeds.
- **AC4.7:** Approval timeout: if no `resume_from_gate(...)` call arrives within `config.hitl_timeout_seconds` wall-clock of the `interrupt()` emission, a background reaper (or the next `run()`/`resume_from_gate()` call on a re-fetched state) emits `reason_code="m8_hitl_timeout"`, returns `PipelineResult(status="timed_out", paused_gate=N, reason_code="m8_hitl_timeout")`. Timeout reaper: `m8_pipeline_engine.hitl::reap_timed_out_threads(now: datetime) -> list[str]` is a pure function M12 invokes on a cron schedule (M12's responsibility, not M8's runtime).
- **AC4.8:** Approver role is enforced per-gate: Gate 1 (stage 7) = `research_specialist` OR `supervising_advisor`; Gate 2 (stage 13) = `compliance_officer`; Gate 3 (stage 21) = `supervising_advisor`. Enforcement lives in `_verify_approver_role(gate_id, approver_aid_claims) -> bool`. Missing role → `reason_code="m8_hitl_role_mismatch"`. See §HITL Gate Specification.
- **AC4.9:** Compliance pre-check at Stage 20 is NOT an HITL gate — it is a deterministic call to M6's `compliance.screen` action, which in turn consults M2/M4 OPA policy. M8 branches on the success-path `GatewayResponse.decision` ∈ `{ALLOW, ESCALATE}` and the failure-path `GatewayError.reason` ∈ `{authority_denied, authority_escalated}`. `authority_denied` → fail hard with `reason_code="m8_compliance_denied"`. `authority_escalated` (or `ESCALATE` returned on success) → flow continues to HITL Gate 3 (stage 21) for human review with `state.compliance_escalation=True`. `ALLOW` → proceed to stage 21.
- **AC4.10:** Token replay protection: token binding includes `thread_id` AND `approver_timestamp`. A previously-used token on a new `thread_id` MUST NOT verify (different HMAC input). A previously-used token on the SAME `thread_id` is allowed only if the gate has not yet been resumed (LangGraph's idempotency on `interrupt()` resume — replay within a single gate is safe by design).
- **AC4.11:** Token timestamp skew: if `abs(now - approver_timestamp) > config.hitl_timeout_seconds`, token is rejected with `reason_code="m8_hitl_token_expired"`. Task 8 asserts via clock injection.
- **AC4.12:** **HITL HMAC key rotation (new in v0.2.0, Required Fix 12).** The HMAC key cached at process startup MUST be re-fetched on pod restart (no in-flight rotation; pods are cattle). Kubernetes rolling deploys cycle ~all M8 pods quarterly as part of the 24-hour mTLS rotation × 90-day aggregate cycle. Operator-initiated rotation: (a) write new key to Vault at the configured path, (b) trigger rolling `kubectl rollout restart deploy/m8` — each new pod fetches the new key at startup. In-flight pipelines at a HITL gate MUST NOT be disrupted during rotation: the OLD key remains valid until the pod holding the cached old key terminates, and resumption on a new pod with a new key will fail token verification with `m8_hitl_token_expired` — approver then re-submits with a freshly-signed token using the NEW key. This is by design (no key continuity across pod boundaries). Rotation cadence: quarterly (90 days), aligned with certificate rotation cycle. Test: Task 8 `test_hitl_key_rotation` pods A and B with different cached keys, asserts token signed under A's key fails verification on B.

### R5. Map-Reduce Synthesis via LangGraph `Send` API

Stage 8 uses LangGraph's `Send` API to fan out per-instrument research (one `Send` per instrument discovered in Stage 4, capped at `max_concurrent_instruments=10`). Stages 9-11 run per-instrument in parallel. Stage 12 aggregates.

**Acceptance Criteria:**
- **AC5.1:** Stage 8 node returns `list[Send]` — one `Send("stage_9_dcf_valuation", {"instrument": inst, ...per-instrument-state})` per instrument from `state.discovered_instruments`. LangGraph fans out automatically.
- **AC5.2:** Per-instrument sub-state (stages 9-11) is keyed by `instrument_id`. `state.per_instrument_results: dict[str, PerInstrumentResult]` with `instrument_id` keys collects outputs.
- **AC5.3:** Fan-out cap: `len(sends) <= config.max_concurrent_instruments` (default 10). Instruments beyond cap are sorted by `mentioned_count` descending and top-N retained. Dropped instruments listed in `state.dropped_instruments: list[str]` for audit — NOT an error.
- **AC5.4:** Stage 12 (reduce / cross-source synthesis) reads `state.per_instrument_results` after fan-in (LangGraph guarantees all `Send` branches complete before the reducer runs). Combines per-instrument summaries into `state.cross_source_synthesis`.
- **AC5.5:** Per-instrument stage failure does NOT fail the whole pipeline. The failed instrument is recorded in `state.per_instrument_errors: dict[str, str]` (instrument → reason_code) and the pipeline continues. At reduce stage, if `len(state.per_instrument_results) == 0` (ALL failed), stage 12 emits `reason_code="m8_map_reduce_all_failed"` and pipeline fails.
- **AC5.6:** Reducer combines `dict` shapes with `operator.or_` merge — LangGraph native. Task 5 asserts merge semantics via property tests.
- **AC5.7:** Map-reduce width is checked at stage 8: if the LLM-generated instrument discovery returns `> config.max_concurrent_instruments * 3` instruments, emit `reason_code="m8_map_reduce_too_wide"`, cap at `max_concurrent_instruments`, continue. This is an observability signal, not an error.
- **AC5.8:** **Zero-fan-out case (new in v0.2.0, Recommended Fix 1).** If `state.discovered_instruments == []` at stage 8 entry, stage 8 returns `[]` (empty `Send` list) — LangGraph skips fan-out and proceeds directly to stage 12. Stage 12 sees `per_instrument_results == {}` and, by AC5.5, would emit `m8_map_reduce_all_failed`. v0.2.0 adds a pre-condition: stage 12 checks `len(state.discovered_instruments) == 0` FIRST (before checking `per_instrument_results`) and in that case emits audit `event_type="m8.single_tool_bypass"` with `reason_code=None` and returns an empty `cross_source_synthesis` payload — pipeline continues to stage 13. This covers `m8.research_single_tool` pipelines (e.g., "What's NVDA's Q3 EPS?") where no instrument fan-out is needed. Task 16 `test_zero_fan_out_single_tool` asserts.

### R6. LLM — Bedrock Claude Sonnet via `boto3` Converse API

All LLM-bearing stages use Bedrock Claude Sonnet (Steering Rule 13). Model access via `boto3` Bedrock Runtime `converse` API. `temperature=0.3` for synthesis stages (enough stochasticity for creative synthesis, not enough for hallucination); `maxTokens` per-stage from `PipelineConfig.token_budgets`.

**Acceptance Criteria:**
- **AC6.1:** `LLMClient` is a `typing.Protocol` in `src/m8_pipeline_engine/llm_client.py` declaring: `generate(self, *, stage_name: str, prompt: str, max_tokens: int, temperature: float, response_format: Literal["text", "json"]) -> LlmGeneration`. `@runtime_checkable`.
- **AC6.2:** `LlmGeneration` is a Pydantic v2 model with `ConfigDict(frozen=True, extra="forbid")`, fields: `text: str`, `input_tokens: int`, `output_tokens: int`, `latency_ms: int`, `model: str`, `provider: Literal["bedrock","azure_openai","vertex","vllm","fake"]`, `stop_reason: str`.
- **AC6.3:** `SonnetClient(model_id: str, region: str, timeout_ms: int = 60000, max_retries: int = 2)` — constructor stores config; no Bedrock call until `.generate(...)`. No credentials passed — `boto3.client("bedrock-runtime")` resolves via default credential chain.
- **AC6.4:** `SonnetClient.generate` issues a Bedrock Runtime `converse` API call with `system=[{"text": <loaded-from-prompt-file>}]`, `messages=[{"role":"user","content":[{"text":prompt}]}]`, `inferenceConfig={"temperature": temperature, "maxTokens": max_tokens}`. For `response_format="json"`, add `additionalModelRequestFields={"response_format":{"type":"json_object"}}`.
- **AC6.5:** Bedrock timeout → `LlmTimeoutError`. Bedrock 5xx → `LlmProviderError(status_code)`. Bedrock 4xx → `LlmProviderError(status_code)`. Bedrock returns a response that does not parse as expected JSON (when `response_format="json"`) → `LlmMalformedOutputError`. These four error classes are the only exceptions `generate` raises.
- **AC6.6:** Retries: `max_retries=2` for 5xx and timeout classes ONLY (never 4xx). Exponential backoff 500 ms × 2^n with ±25% jitter.
- **AC6.7:** `generate` NEVER logs the raw `prompt`. It logs only `{trace_id, stage_name, input_sha256, model, provider, latency_ms, status, input_tokens, output_tokens}`. Task 15 asserts no substring match of a canary string in captured stdout.
- **AC6.8:** Model ID default: `"anthropic.claude-sonnet-4-5-20250929-v1:0"` (PENDING-VERIFICATION per §Known Blockers row 2). Override via `PipelineConfig.model_id`. Different LLM-bearing stages MAY use different model IDs in Phase 3; Phase 2 uses one Sonnet ID for all.
- **AC6.9:** `generate` is synchronous. Async wrapping is M12's responsibility.
- **AC6.10:** `FakeSonnetClient(responses: dict[str, LlmGeneration | Exception], delay_ms: int = 0)` satisfies `LLMClient`. Keyed by `input_sha256` (computed from `stage_name + prompt`). Values may be `LlmGeneration` → returned verbatim; `LlmTimeoutError` / `LlmProviderError` / `LlmMalformedOutputError` → raised verbatim. `delay_ms` introduces a `time.sleep` for wall-clock testing (Task 13).
- **AC6.11:** Reserved stubs `AzureOpenAIClient`, `VertexClient`, `VllmClient` exist in `llm_client.py` — each `__init__` raises `NotImplementedError("Phase 3")` and signature satisfies the Protocol.
- **AC6.12:** `select_llm_client(config: PipelineConfig) -> LLMClient` is the sole construction point. Dispatch: `"bedrock"` → `SonnetClient`; `"azure_openai"` → `AzureOpenAIClient`; `"vertex"` → `VertexClient`; `"vllm"` → `VllmClient`. Unknown → `ValueError("provider_unconfigured")`.

### R7. All Tool Calls Through M6 Gateway via `GatewayClient` Protocol

Steering Rule 4 + Rule 7. M8 NEVER calls MCP servers directly, NEVER imports `m6_mcp_gateway`, NEVER imports any `m11_*` vendor adapter. All tool calls (SEC EDGAR, Bloomberg, News API, Salesforce, Orion, eMoney, Schwab) go through the injected `GatewayClient` Protocol. **v0.2.0 corrects v0.1.0's three shape-drift bugs (Required Fixes 1-3):** real M6 `GatewayRequest`/`GatewayResponse` are `@dataclass(frozen=True)`, not Pydantic; `vendor_adapter` is REQUIRED non-None; failure reasons are RAISED as `GatewayError`, not returned as `GatewayResponse` fields.

**Acceptance Criteria:**
- **AC7.1:** `GatewayClient` is a `typing.Protocol` in `src/m8_pipeline_engine/gateway_client.py` with ONE method: `call(self, request: GatewayRequest) -> GatewayResponse`. `@runtime_checkable`. (v0.1.0's `emit_audit` method is REMOVED per Required Fix 4 — audit now goes through the separate `AuditClient` Protocol; see §Integration Point with M10 and R8.)
- **AC7.2:** `GatewayRequest` and `GatewayResponse` in `src/m8_pipeline_engine/gateway_client.py` are `@dataclass(frozen=True)` — matching M6's shape verbatim (`src/m6_mcp_gateway/gateway.py` lines 118 + 221). Field lists are field-for-field compatible. v0.1.0's Pydantic v2 wrapper is dropped (Required Fix 1). Cross-module shape-match test (Task 20) uses `dataclasses.fields()` introspection to assert field name + type equality against M6's exported types — NOT `model_fields` (which dataclasses do not have). Example field list for `GatewayRequest`: `token: str`, `action: str`, `tool_name: str`, `mcp_server: str`, `payload: Any`, `trace_id: str`, `firm_id: str`, `target: Mapping[str, Any]`, `context: Mapping[str, Any]`, `session_id: Optional[str]`, `vendor_adapter: Any` (VendorAdapter-shaped — REQUIRED non-None). Example field list for `GatewayResponse`: `decision: Literal["ALLOW", "DENY", "ESCALATE"]`, `result: Any`, `liability_report: Optional[Any]` (M8 does not interpret; M6 populates), `trace_id: str`, `latency_ms: int`, `provenance_head: str`, `rule_applied: Optional[str]`, `wsp_section: Optional[str]`, `reason: Optional[str]`. On the success path (ALLOW), `decision == "ALLOW"` and `result is not None`. The ESCALATE decision may also appear on the success path (no `GatewayError` raised); M8 treats it as an advisory — see AC7.8.
- **AC7.3:** `M6GatewayClient(base_url: str, mtls_cert_path: str, vendor_adapter_registry: VendorAdapterResolver, timeout_ms: int)` is the production implementation (v0.2.0 updated — was missing `vendor_adapter_registry` in v0.1.0). Uses `urllib.request` (stdlib — not `requests`, not `httpx`) with a custom `HTTPSHandler` for mTLS. Endpoint: `POST {base_url}/gateway/call`. Content-Type `application/json`. Before calling `.call()`, M8's `_invoke_tool` helper resolves a `VendorAdapter` instance via `vendor_adapter_registry.resolve(tool_name)` and populates `GatewayRequest.vendor_adapter` — Required Fix 2. `VendorAdapterResolver` is a `typing.Protocol` with `resolve(tool_name: str) -> Any` (returning a VendorAdapter-shaped object with callable `.call` + str `.name`). The in-process Phase 2 implementation is a `LocalVendorAdapterResolver` that mirrors M6's registry contents; in a future M6 v0.3.0 "server-side adapter resolution" mode (§Known Blockers row 6 option (a)), the resolver would become a no-op stub returning a sentinel that M6 interprets. SHARED-WITH-M6.
- **AC7.4:** `FakeGatewayClient(call_responses: dict[str, GatewayResponse | Exception], recorded_calls: list[GatewayRequest])` satisfies `GatewayClient`. `call_responses` keyed by `tool_name`. An `Exception` value — specifically `GatewayError(reason)` — is RAISED on invocation to exercise failure paths; a `GatewayResponse` value is returned. `recorded_calls` appends every request for test assertion. Used by Tasks 1, 11, 14, 15, 16, 17, 20.
- **AC7.5:** MNPI filtering is M6's concern. M8 receives `GatewayResponse.result` already MNPI-filtered (M4 post-response hook runs inside M6's `call()`). M8 never post-filters. Task 11 property test asserts `stage_response_body` contains no MNPI-shaped fields (SSN regex, bank routing regex) — if it ever does, the failure is M6's, not M8's; M8 still refuses to forward such content to Sonnet and emits `reason_code="m8_mnpi_leaked_through_gateway"` as defensive depth (corresponds to catching `GatewayError("mnpi_leakage_scan")` per AC7.9).
- **AC7.6:** M8 never logs raw tool payloads. Only `input_sha256` and `output_sha256` digests land in stdout/audit. Task 15 canary scan asserts.
- **AC7.7:** On `GatewayResponse.decision == "ALLOW"` (success path, ALLOW branch): stage uses `resp.result` as its output, captures `resp.rule_applied` + `resp.wsp_section` in audit, continues. `result is None` → stage continues with empty result (treated as "tool returned nothing found", not error).
- **AC7.8:** On `GatewayResponse.decision == "ESCALATE"` (rare success-path branch — M6 may return ESCALATE with `result` populated when policy dictates advisory continuation): stage continues, `state.compliance_escalation=True` is set, which forces HITL Gate 3 to open (even if anti-fabrication passes). Audit captures `gateway_decision="ESCALATE"`, `rule_applied`, `wsp_section`. (Note: M6 also raises `GatewayError("authority_escalated")` on the failure path; see AC7.9. Both paths end up setting `compliance_escalation=True`.)
- **AC7.9:** **M6 failure paths RAISE `GatewayError(reason)` — NEVER returned as `GatewayResponse` fields (Required Fix 3).** M8's `_invoke_tool` wraps `gateway.call(...)` in `try / except GatewayError as exc` and branches on `exc.reason` ∈ `VALID_GATEWAY_REASONS` (M6's frozen set — see `src/m6_mcp_gateway/gateway.py` line 58):
  - `exc.reason == "invalid_identity"` → **unexpected — M12 should have verified identity upstream**. Stage fails with `reason_code="m8_stage_failed"`. Pipeline terminates. Ops alert.
  - `exc.reason == "authority_denied"` → stage fails hard with `reason_code="m8_compliance_denied"`. Pipeline terminates with `status="failed"`. No stage-level retry.
  - `exc.reason == "authority_escalated"` → stage continues but `state.compliance_escalation=True` is set (forces HITL Gate 3). No `reason_code`. Pipeline continues. (Parallels the ESCALATE-on-success path in AC7.8.)
  - `exc.reason == "vendor_unavailable"` → stage retries up to `max_retries=2` with 500 ms exponential backoff. Beyond retries → stage fails with `reason_code="m8_stage_failed"`, pipeline terminates.
  - `exc.reason == "vendor_error"` → stage fails with `reason_code="m8_stage_failed"`, pipeline terminates. No retry (distinguishes from `vendor_unavailable` — vendor_error is a semantic vendor failure, not a transport issue).
  - `exc.reason == "rate_limited"` → stage waits 2 s then retries once. Beyond → `m8_stage_failed`.
  - `exc.reason == "circuit_open"` → stage fails with `reason_code="m8_stage_failed"`. No retry (circuit is upstream; M8 respects it). Pipeline terminates.
  - `exc.reason == "mnpi_leakage_scan"` → DEFENSIVE path. M8 emits `reason_code="m8_mnpi_leaked_through_gateway"` (this is an M6/M4 upstream bug, but M8 fails closed). Pipeline terminates.
  - `exc.reason == "mnpi_filter_error"` → M6-internal MNPI-filter plumbing failure. M8 emits `reason_code="m8_mnpi_leaked_through_gateway"` (shares the defensive bucket — M8 does not know whether filter failure means filter bypassed or filter crashed; fail closed). Pipeline terminates.
  - `exc.reason == "audit_failed"` → M6-internal audit-write failure. Semantically distinct from M8's own audit failure (AC8.5). M8 treats this as terminal: emit `reason_code="m8_audit_write_failed"` via its own `AuditClient`, return `status="terminated"`. (If M8's `AuditClient` itself subsequently fails to emit, M8's audit-failure path kicks in per AC8.5 — double fault is still terminal.)
  - `exc.reason == "invalid_request"` → developer-error class (M8 constructed a malformed `GatewayRequest`). M8 emits `reason_code="m8_stage_failed"` and re-raises in dev builds (`AssertionError` wrapping the `GatewayError`); in prod builds emits `m8_stage_failed` only. Task 15 asserts via `FakeGatewayClient` raising `GatewayError("invalid_request")`.
  Each branch emits the stage audit payload BEFORE marking the stage failed so the audit trail captures the failure reason. Task 15 `test_gateway_error_branches` exercises every `VALID_GATEWAY_REASONS` value via `FakeGatewayClient` exception injection.
- **AC7.10:** M6 tool name vocabulary used by M8 stages: `sec_edgar.fetch_10k`, `sec_edgar.fetch_10q`, `sec_edgar.fetch_8k`, `bloomberg.market_data`, `bloomberg.fundamentals`, `bloomberg.earnings_transcript`, `bloomberg.peer_comps`, `news_api.scan`, `salesforce.fetch_client`, `salesforce.fetch_household`, `salesforce.writeback_research_brief`, `orion.fetch_holdings`, `orion.fetch_transactions`, `emoney.fetch_plan_summary`, `schwab.fetch_positions`, `compliance.screen`. Task 19 asserts subset-of-M6's registered tools (xfail until M6 Phase 2 manifest lands).
- **AC7.11:** `GatewayClient` + `AuditClient` + `LLMClient` are injected at `CompiledGraph` compile time — NOT at `run()` call time. Tests use `FakeGatewayClient` + `FakeAuditClient` + `FakeSonnetClient`; production uses `M6GatewayClient` + `M10AuditClient` + `SonnetClient`. `build_graph(gateway: GatewayClient, audit: AuditClient, llm: LLMClient) -> StateGraph[PipelineState]`.

### R8. Per-Stage Audit Emission — ARCH-06 v3 Gap 2 Row — via `AuditClient` Protocol (v0.2.0)

Every stage emits exactly one audit line. **v0.2.0 change (Required Fix 4):** audit goes through a separate `AuditClient` Protocol (`M10AuditClient` → M10's FastAPI `/audit` endpoint), NOT through `GatewayClient.emit_audit` (which does not exist on M6's `TrustAwareGateway`). ARCH-06 v3 §Gap 2 "M8 Pipeline" row pins the fields: stage number, model version, prompt template version, input_sha256, output_sha256. v0.2.0 adds pipeline_run_id, thread_id, tenant_id, latency_ms, tokens_used, reason_code for operational observability.

**Acceptance Criteria:**
- **AC8.1:** Audit payload schema is a Pydantic v2 model `StageAuditPayload` with `ConfigDict(frozen=True, extra="forbid")`. Required fields: `source: Literal["m8"] = "m8"`, `pipeline_run_id: str`, `thread_id: str`, `tenant_id: str`, `firm_id: str`, `stage_number: int` (1..23), `stage_name: str`, `trace_id: str`, `timestamp: str` (ISO-8601 UTC with `Z` suffix), `model_version: Optional[str]` (None for non-LLM stages), `prompt_template_version: Optional[str]` (None for non-LLM stages), `input_sha256: str` (64-char hex lowercase), `output_sha256: str` (64-char hex lowercase), `latency_ms: int` (>= 0), `input_tokens: int` (>= 0; 0 for non-LLM stages), `output_tokens: int` (>= 0; 0 for non-LLM stages), `reason_code: Optional[str]` (None on success, else member of `VALID_REASON_CODES`), `tool_name: Optional[str]` (for M6-call stages), `gateway_decision: Optional[Literal["ALLOW","DENY","ESCALATE"]]` (for M6-call stages — v0.2.0 allows `"DENY"` as an audit-only label when M8 translates `GatewayError("authority_denied")` into an audit row; M8 never receives `decision="DENY"` on the success return), `rule_applied: Optional[str]`, `wsp_section: Optional[str]`.
- **AC8.2:** Exactly one audit call per stage invocation (including failure paths). Hook: `_emit_stage_audit(audit_client, state, stage_number, ...) -> None` called in a `try/finally` block around the stage body.
- **AC8.3:** `input_sha256` is `hashlib.sha256(canonical_json(stage_input).encode()).hexdigest()` where `stage_input` is the pre-stage subset of `PipelineState` relevant to the stage. `output_sha256` is computed over the stage's returned partial-state update.
- **AC8.4:** `canonical_json()` uses `json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)` for deterministic byte-level hashing across processes.
- **AC8.5:** Audit emission failures (`AuditClient.emit` raises `AuditEmitError`) trigger RETRY once with 200 ms backoff, then `reason_code="m8_audit_write_failed"`, pipeline terminates with `status="terminated"`. Fail-closed per Steering Rule 8. Task 10 asserts via `FailingFakeAuditClient`.
- **AC8.6:** Audit payload MUST NOT contain raw client/security identifiers that would be MNPI-adjacent in plaintext. Only their `*_sha256` digests (computed with tenant-scoped HMAC key where appropriate — deferred to Phase 3). Phase 2: ticker + client_id are deemed non-MNPI by M4 convention and may appear in audit. Task 15 asserts no 9-digit bank-routing / 10-digit phone patterns leak into audit JSON.
- **AC8.7:** Audit emission is best-effort for latency but correct-before-fast — the audit emit completes BEFORE the stage returns (so a downstream replay sees a causally-consistent audit chain). Audit write counts toward stage `latency_ms`.
- **AC8.8:** Terminal pipeline audit row (emitted at end of `run()` regardless of status) carries `stage_number=23` if stage 23 completed; else the last-executed stage number; plus fields `pipeline_status`, `final_brief_sha256` (if `ResearchBrief` produced), `total_wall_clock_seconds`, `total_tokens`. This is a distinct payload model `PipelineTerminalAuditPayload` with `event_type="m8.pipeline_terminal"`.
- **AC8.9:** Audit schema JSON Schema file at `src/m8_pipeline_engine/schemas/m8_stage_audit.schema.json` round-trips: `StageAuditPayload(**example).model_dump() == example`. Meta-test validates against JSON Schema draft 2020-12.
- **AC8.10:** `AuditClient` is a `typing.Protocol` in `src/m8_pipeline_engine/audit_client.py` with ONE method: `emit(self, entry: dict) -> None`. `@runtime_checkable`. `M10AuditClient(base_url: str, mtls_cert_path: str, timeout_ms: int)` POSTs the entry to `{base_url}/audit`. 5xx → retry once; second 5xx → `AuditEmitError`. `FakeAuditClient(entries: list[dict], fail_at: int = -1)` satisfies the Protocol — used by all tests. `AuditEmitError` is the single exception class; all other audit-write errors wrap as `AuditEmitError`.
- **AC8.11:** `m8.pipeline_slow_alert` is emitted exactly once when wall-clock first crosses `alert_pipeline_wall_clock_seconds` (Recommended Fix 11 — adopted from LLMJ v1 recommended list). State flag `state.slow_alert_emitted: bool` gates. Task 13 asserts single-emission even across multiple stages past the threshold.

### R9. Resumption — `thread_id` Allows Checkpoint-Based Recovery

If a pipeline is interrupted mid-stage (pod restart, HITL pause, explicit cancellation), the same `thread_id` on a subsequent `run()` call resumes from the last completed stage via LangGraph native checkpointer semantics.

**Acceptance Criteria:**
- **AC9.1:** `research_pipeline.run(initial_state, thread_id="thread-abc")` after a previous interrupted `run()` with `thread_id="thread-abc"` resumes at the next pending stage. The `initial_state` argument is ignored on resumption (LangGraph behavior). Task 9 asserts.
- **AC9.2:** Resumption MUST emit an audit row at each stage the same way a fresh run does — with `reason_code=None` and the same digests. Task 10 asserts.
- **AC9.3:** Pod restart: if the M8 pod crashes at stage 11, the new pod picks up any pending pipeline on M12-driven re-invocation with the same `thread_id`. No special orchestration in M8 — pure LangGraph behavior.
- **AC9.4:** Resumption after HITL gate rejection (`approval.approved=False`) is NOT permitted on the same `thread_id` — the gate state is terminal. A new `thread_id` is required. Task 8 asserts.
- **AC9.5:** Resumption after timeout: the reaper emits `reason_code="m8_hitl_timeout"` and marks the thread `TIMED_OUT`. A new `thread_id` is required to retry.
- **AC9.6:** Resumption after wall-clock exceeded: same as timeout — terminal, new `thread_id` required.
- **AC9.7:** Resumption after `m8_compliance_denied`: terminal, new `thread_id` required. Stage 20 DENY is a compliance decision — re-running is a compliance violation unless underlying inputs have changed.
- **AC9.8:** **Resumption preserves `state.compliance_escalation` (new in v0.2.0, Recommended Fix 2).** If Stage 20 sets `compliance_escalation=True` and the pipeline is checkpointed (Gate 3 entry), on resumption the flag survives the round-trip. Task 9 `test_compliance_escalation_survives_checkpoint` asserts using `InMemorySaver`.
- **AC9.9:** **`interrupt()` → checkpointer write order regression guard (new in v0.2.0, Recommended Fix 5).** LangGraph's internal ordering (audit emit before `interrupt()` before checkpointer `put()`) is relied upon by M8's HITL contract. Task 9 `test_hitl_interrupt_checkpoint_order` uses a `CheckpointerWithAuditSpy` that records an ordered list of `(audit_emit, interrupt_called, checkpoint_put)` events and asserts the monotone order. If a future LangGraph version bump reorders these, this test fails CI and M8 is refactored accordingly.

### R10. Determinism & Idempotency

Same `(initial_state, thread_id, GatewayClient, AuditClient, LLMClient, Checkpointer)` → same `PipelineResult`, excluding `clock_stamps`, `latency_ms`, and LLM-originated non-deterministic text. Tests use `FakeSonnetClient` + `FakeGatewayClient` + `FakeAuditClient` + `InMemorySaver` for byte-identical reproducibility.

**Acceptance Criteria:**
- **AC10.1:** Two `run()` calls with identical fakes and a fresh `thread_id` produce `PipelineResult`s whose `model_dump(exclude={"wall_clock_seconds"})` are equal when all Sonnet + Gateway responses are pre-seeded.
- **AC10.2:** `run()` does not consume randomness from `random.*` or `secrets.*` or `uuid.uuid4()` EXCEPT at three well-defined points: (a) `pipeline_run_id` generation at `run()` entry (uses `uuid.uuid4()`), (b) HMAC nonce for HITL token replay defense (Phase 3; Phase 2 skipped), (c) Bedrock request IDs inside `boto3`. Task 2 AST scan forbids `random`, `secrets` imports in stage files. `uuid.uuid4()` allowed ONLY in `src/m8_pipeline_engine/__init__.py::_generate_pipeline_run_id`.
- **AC10.3:** Stage functions are pure functions of `(state, gateway, audit, llm)`. Task 11 Hypothesis property test asserts `stage_N(state, gateway, audit, llm) == stage_N(state, gateway, audit, llm)` byte-identical over ≥20 (CI) / ≥50 (local) generated states per Recommended Fix 4.
- **AC10.4:** Idempotency: `run()` does not mutate `initial_state`. Deep-copy-before / equality-after for both args. Task 11 asserts.
- **AC10.5:** Stage ordering determinism: given fan-out at stage 8, reducer at stage 12 sees per-instrument results keyed by `instrument_id` — dict iteration at stage 12 MUST use `sorted()` for deterministic ordering. Task 11 asserts.
- **AC10.6:** `clock_stamps` and `latency_ms` are the only non-deterministic fields explicitly EXCLUDED from determinism comparisons.
- **AC10.7:** `pipeline_run_id` is deterministic given seeding: for tests, inject a `_run_id_factory` via `research_pipeline.run(_run_id_factory=lambda: "test-run-0001")`.

### R11. Error Vocabulary — Closed Frozen Set (20 Codes)

All `reason_code` values are drawn from a closed frozen set of **20 codes** (Required Fix 7 reconciles with v0.1.0's internal inconsistency). Attempting to emit an unknown code is a developer error caught at audit-serialization time via Pydantic validator.

**Acceptance Criteria:**
- **AC11.1:** `VALID_REASON_CODES: frozenset[str] = frozenset({"m8_stage_failed", "m8_checkpoint_write_failed", "m8_audit_write_failed", "m8_hitl_timeout", "m8_hitl_denied", "m8_hitl_role_mismatch", "m8_hitl_token_expired", "m8_llm_5xx", "m8_llm_4xx", "m8_llm_timeout", "m8_llm_malformed_output", "m8_compliance_denied", "m8_mnpi_leaked_through_gateway", "m8_map_reduce_too_wide", "m8_map_reduce_all_failed", "m8_token_budget_exceeded", "m8_wall_clock_exceeded", "m8_tenant_concurrency_exceeded", "m8_anti_fabrication_failed", "m8_invalid_state"})` — **20 codes in v0.2.0** (unchanged from v0.1.0 AC11.1; v0.2.0 sweeps the Changelog + Phase 2 Scope + R11 header to also say 20, resolving the three-places-said-10 inconsistency that LLMJ v1 flagged as Required Fix 7). Meta-test asserts `len(VALID_REASON_CODES) == 20`.
- **AC11.2:** `StageAuditPayload.reason_code: Optional[str]` with Pydantic `@field_validator` asserting `v is None or v in VALID_REASON_CODES`.
- **AC11.3:** Meta-test (Task 15) exercises every `reason_code`. Unreachable codes fail the test.
- **AC11.4:** Adding a code = MINOR bump; removing/renaming = MAJOR bump. DECISION-LOG records every change.
- **AC11.5:** `reason_code` strings are lowercase snake_case prefixed with `"m8_"`, matching regex `^m8_[a-z][a-z0-9_]+[a-z0-9]$`. Lint asserted.
- **AC11.6:** Error vocabulary MUST NOT leak MNPI-category specificity. `m8_mnpi_leaked_through_gateway` is the only MNPI-related code — no `ssn_detected`, no specific MNPI categories in reason codes.

### R12. Module Boundary Enforcement (AST Scan) — ARCH-09 ALIGNED

M8 imports ONLY from `m3_schema_registry`, `m5_config_loader`, and `m9_intent_router.models` per ARCH-09 matrix row M8 (M8 → M3 via types, M5 via config). **Type-annotation-only** import of M9 models; no runtime reference. Positive allow-list, not negative blacklist.

**Acceptance Criteria:**
- **AC12.1:** `tests/security/test_module_boundary.py` walks every `.py` file under `src/m8_pipeline_engine/` with `ast.parse`, collects every `Import` / `ImportFrom` node, and rejects any whose module matches `^(m1_|m2_|m4_|m6_|m7_|m10_|m11_|m12_|m13_|compliance\.)`.
- **AC12.2:** Positive allow-list for intra-project imports: `m3_schema_registry.{ResearchBrief, InteractionSummary, SecurityIdentifier, ResearchSource, Client, Holding, Household, TaxLot, CostBasisMethod, Valuation, Beneficiary}` (v0.2.0 adds `TaxLot` + `CostBasisMethod` for cost-basis invariant per Required Fix 5; **drops `ComplianceCheck`** per Required Fix 9 — never populated in state); `m5_config_loader.{Archetype, Runtime, SpecialistConfig, PipelineConfig}`; `m9_intent_router.models.{RoutingDecision, SelectedTarget, IntentCategory}`. Any other intra-project dotted module name fails the scan.
- **AC12.3:** From M3, M8 imports ONLY canonical types for use in `PipelineState` annotations and `PipelineResult.research_brief` construction. M8 NEVER calls M3 factory helpers or mutators; M3 is imported as pure-data types only.
- **AC12.4:** From M5, M8 imports `Archetype`, `Runtime`, `SpecialistConfig`, `PipelineConfig` (pending M5 v0.4.0 per §Known Blockers row 1). Loader via `m5_config_loader.load_pipeline_config(...)`.
- **AC12.5:** From `m9_intent_router.models`, M8 imports `RoutingDecision`, `SelectedTarget`, `IntentCategory` ONLY for type annotations (`PipelineState.routing_decision: RoutingDecision`). Task 2 asserts no runtime method invocation on these types beyond `.selected_target.kind`, `.selected_target.name`, `.intent.value` (read-only attribute access). No call to `m9_intent_router.route()`.
- **AC12.6:** Forbidden string-level references: `test_no_forbidden_module_strings.py` scans for literals `"m1_"`, `"m2_"`, `"m4_"`, `"m6_"`, `"m7_"`, `"m10_"`, `"m11_"`, `"m12_"`, `"m13_"` in source — rejected unless inside documentation strings or PIPELINE_NAMES frozenset. `EXEMPT_FILES = {"src/m8_pipeline_engine/__init__.py"}` (which legitimately references `m8.research_pipeline_*` names).
- **AC12.7:** `pyproject.toml` `[project.dependencies]` contains only: `pydantic>=2.0,<3.0`, `boto3>=1.34`, `langgraph>=0.4,<2.0` (v0.2.0 bump per Required Fix 8 — was `>=0.2.0,<0.3` which pinned M8 two majors behind the current LangGraph V1.0 stable), `langgraph-checkpoint-postgres>=2.0.0,<3.0`, `psycopg[binary]>=3.1`, `m3-schema-registry>=0.1.0,<1.0`, `m5-config-loader>=0.4.0,<1.0`, `m9-intent-router>=0.2.0,<1.0`. Task 17 asserts.
- **AC12.8:** `from m6_mcp_gateway ...` or `from m11_* ...` or `from m12_* ...` or `from m10_* ...` anywhere in M8 source is a test failure. Task 2 asserts.
- **AC12.9:** M8 does NOT import any `compliance.*` module (Gap 2 liability provenance runs inside M6/M10, not inside M8).

### R13. Forbidden Imports (AST Scan)

M8 is stdlib + pinned-third-party only. Forbidden imports would introduce logging side-channel MNPI leaks, network leaks, or pipeline-framework coupling bypassing LangGraph.

**Acceptance Criteria:**
- **AC13.1:** `tests/security/test_forbidden_imports.py` AST-scans every source file and rejects imports of: `logging`, `requests`, `httpx`, `aiohttp`, `urllib3`, `langchain`, `langchain_aws`, `langchain_community`, `anthropic`, `openai`, `warnings`, `tempfile`, `socket`, `subprocess`, `grpc`, `google.cloud`, `azure.*`, `celery`, `prefect`, `airflow`, `crewai`.
- **AC13.2:** Allow-list stdlib: `ast`, `base64`, `copy`, `datetime`, `enum`, `functools`, `hashlib`, `hmac`, `json`, `re`, `time`, `types`, `typing`, `collections`, `threading`, `uuid`, `urllib.request`, `urllib.parse`, `urllib.error`, `ssl`, `contextlib`, `dataclasses`, `operator`. Third-party: `pydantic`, `boto3`, `botocore`, `langgraph`, `langgraph.checkpoint.postgres`, `langgraph.checkpoint.memory`, `langgraph.types` (v0.2.0 — for `Send` import per Required Fix 8), `psycopg`. Intra-project: `m3_schema_registry.*`, `m5_config_loader.*`, `m9_intent_router.models.*`.
- **AC13.3:** `boto3` allowed ONLY in `src/m8_pipeline_engine/llm_client.py` AND `src/m8_pipeline_engine/hitl.py` (for Vault HMAC key resolution via Secrets Manager client) AND `src/m8_pipeline_engine/checkpointer.py` (for Vault DSN resolution). Any other M8 file importing `boto3` fails the scan.
- **AC13.4:** `hmac` and `hashlib` allowed globally. `urllib.request` allowed ONLY in `src/m8_pipeline_engine/gateway_client.py` (for the `M6GatewayClient` HTTPS/mTLS calls) AND `src/m8_pipeline_engine/audit_client.py` (for `M10AuditClient` HTTPS/mTLS calls — new in v0.2.0).
- **AC13.5:** **`print` allow-list tightened (v0.2.0, Required Fix 11).** `print(` appears in at most two places: (a) `audit_emit.py` as a fallback path — MUST emit digest-only audit lines (input_sha256 + output_sha256 + stage_number + reason_code only — NO raw payload, NO prompt body, NO tool result body), (b) the module's `__main__` guard if any (diagnostic banner only). Source-level assertion test: `test_print_discipline` scans every `print(` site and asserts (via AST analysis of the call arguments) that no variable named `prompt`, `payload`, `result`, `tool_result`, `raw`, or `text` is passed as an argument to `print(...)`. Forbidden patterns yield immediate test failure.
- **AC13.6:** `time.perf_counter()` / `time.monotonic()` allowed for `latency_ms` measurement only. Forbidden: `time.sleep` in production code paths (allowed in `FakeSonnetClient` since it is a test utility + retry backoff in `SonnetClient.generate`).
- **AC13.7:** `threading` allowed ONLY for `threading.Semaphore(3)` per-tenant concurrency cap (R16). `asyncio` is NOT imported by M8.
- **AC13.8:** `langchain` (the umbrella package) is explicitly forbidden — v0.2.0 uses `langgraph` only. This preserves the Steering-Rule-15 provider abstraction (LangChain's abstraction leaks implementation choices across providers). `langchain-aws` is NOT an approved dependency despite ARCH-04 v2 "Key Libraries" listing — see Known Blockers row 17.

### R14. Zero Credentials in Code

No API keys, tokens, passwords, model endpoint secrets, checkpointer DSNs, or connection strings in source code, config files, or environment-variable defaults. Ever.

**Acceptance Criteria:**
- **AC14.1:** `tests/security/test_no_hardcoded_creds.py` regex-scans every source file and `pyproject.toml` for literal assignments matching credential shapes: `(?i)(api_key|apikey|secret|password|token|access_key|dsn)\s*=\s*['"][^'"<>]+['"]`. Zero hits.
- **AC14.2:** Bedrock credentials resolve via `boto3` default chain: IRSA → instance metadata → env → Vault. M8 code passes NO credentials to `boto3.client("bedrock-runtime")`.
- **AC14.3:** Checkpointer DSN fetched from Vault at process startup via `PipelineConfig.checkpointer_dsn_vault_path`. Cached. Never logged.
- **AC14.4:** HITL HMAC key fetched from Vault at process startup via `PipelineConfig.hitl_hmac_key_vault_path`. Cached. Never logged. Task 17 asserts memory-only residence (no filesystem write). Rotation per AC4.12.
- **AC14.5:** AWS region read from `PipelineConfig.region`. Default literal `"us-east-1"` exists in M5 `PipelineConfig`, not in M8.
- **AC14.6:** **Ships `.env.example`** at `src/m8_pipeline_engine/.env.example`. Contents: `AWS_REGION=us-east-1`, `M8_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0`, `M8_CHECKPOINTER_BACKEND=postgres`, `M8_CHECKPOINTER_DSN_VAULT_PATH=secret/data/m8/checkpointer_dsn`, `M8_HITL_HMAC_KEY_VAULT_PATH=secret/data/m8/hitl_hmac_key`, `M8_GATEWAY_BASE_URL=https://m6-gateway.internal:8443`, `M8_GATEWAY_MTLS_CERT_PATH=/etc/m8/mtls/client.pem`, `M8_AUDIT_BASE_URL=https://m10-audit.internal:8443` (new in v0.2.0 per Req-Fix 4), `M8_AUDIT_MTLS_CERT_PATH=/etc/m8/mtls/audit-client.pem`, `M8_HITL_TIMEOUT_SECONDS=14400`, `M8_MAX_WALL_CLOCK_SECONDS=1200`. Zero credential-shaped names. Task 17 asserts shipping.
- **AC14.7:** Runtime configuration logs `PipelineConfig.model_dump(exclude={"checkpointer_dsn_vault_path", "hitl_hmac_key_vault_path"})` — defensive exclude.
- **AC14.8:** Checkpoint state table contents MAY contain MNPI-filtered payloads (post-M4-filter). Checkpoint rows MUST NOT contain cleartext advisor AID tokens, HITL HMAC keys, or Bedrock credentials. Task 17 asserts via post-run row-scan against a canary fixture.

### R15. Public API Surface — `__all__`

The package's public API is small and frozen. Internal helpers are leading-underscore-prefixed and MUST NOT be imported from outside the package.

**Acceptance Criteria:**
- **AC15.1:** `src/m8_pipeline_engine/__init__.py` declares `__all__ = ["research_pipeline", "run", "resume_from_gate", "PipelineState", "PipelineResult", "PipelineConfig", "STAGE_NAMES", "HITL_GATES", "PIPELINE_NAMES", "VALID_REASON_CODES", "SCHEMA_VERSION", "LLMClient", "SonnetClient", "FakeSonnetClient", "GatewayClient", "M6GatewayClient", "FakeGatewayClient", "GatewayRequest", "GatewayResponse", "AuditClient", "M10AuditClient", "FakeAuditClient", "HitlApproval", "HitlGatePayload", "AuditEmitError"]`. **Exactly 24 names in v0.2.0** (up from 21 — added `AuditClient`, `M10AuditClient`, `FakeAuditClient`, `AuditEmitError` per Required Fix 4; no removals).
- **AC15.2:** Importing a leading-underscore name from outside the package is a test failure.
- **AC15.3:** `SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"` in v0.2.0 (unchanged).
- **AC15.4:** Every `__all__` name has a Sphinx-style docstring.
- **AC15.5:** Reserved providers (`AzureOpenAIClient`, `VertexClient`, `VllmClient`) and `DynamoDbSaver` are NOT in `__all__`.
- **AC15.6:** Adding or removing a name from `__all__` is a MAJOR bump. Modifying a signature is also a MAJOR bump.

### R16. Latency Budget — Wall-Clock Ceiling and Alert Threshold

ARCH-07 pins M8 `<20 min` full run (alert at `>20 min for 5 min`). Part 7 of 007-consolidated states p50 `<15 min`. v0.2.0 treats 20 min as hard ceiling, 15 min as alert.

**Acceptance Criteria:**
- **AC16.1:** `PipelineConfig.max_pipeline_wall_clock_seconds = 1200` (20 min) is the HARD ceiling. Breach → abort current stage, final audit with `reason_code="m8_wall_clock_exceeded"`, `PipelineResult.status="timed_out"`. HITL wait time is EXCLUDED from this measurement.
- **AC16.2:** `PipelineConfig.alert_pipeline_wall_clock_seconds = 900` (15 min) is the alert threshold. When exceeded (but still under the ceiling), a SECOND audit row is emitted with `reason_code=None` and `event_type="m8.pipeline_slow_alert"`. Not a failure, just an operational signal. Exactly-once emission per AC8.11.
- **AC16.3:** Per-tenant concurrency: `threading.Semaphore(3)` per `tenant_id`. Blocking acquisition with `timeout=60`. On timeout, emit `reason_code="m8_tenant_concurrency_exceeded"`, return `PipelineResult(status="failed", reason_code="m8_tenant_concurrency_exceeded")`. Steering Rule 11.
- **AC16.4:** Per-stage token budget: `PipelineConfig.token_budgets[stage_name]`. See §Token Budget Table for defaults. LLM call with `max_tokens=budget`. If `LlmGeneration.output_tokens == budget` AND `LlmGeneration.stop_reason == "max_tokens"`, emit `reason_code="m8_token_budget_exceeded"` as a soft warning in the audit row (not a failure — the truncated output is still used).
- **AC16.5:** Benchmark captures wall-clock p50, p95, p99 over a suite of 20 deterministic test pipelines (all `FakeSonnetClient` + `FakeGatewayClient` + `FakeAuditClient`, seeded). Emits `tests/benchmarks/m8_latency.json`. CI fails if adapter-layer p99 regresses > 20%.
- **AC16.6:** Measurement: `time.perf_counter()` (monotonic). Stage-level `latency_ms >= 0`.

### R17. Integration Point with M12 Supervisor Runtime

M12 is M8's only direct caller in Phase 2 (ARCH-09 matrix column 8, M12 marked `*`). M12 constructs the initial `PipelineState` from the `RoutingDecision` it received from M9, then calls `research_pipeline.run(initial_state, thread_id)`. See §Integration Point with M12.

**Acceptance Criteria:**
- **AC17.1:** M12 Supervisor calls M8 directly via `m8_pipeline_engine.research_pipeline.run(initial_state, thread_id)`. Not through M6. Not through a FastAPI route. In-process.
- **AC17.2:** M12 populates `initial_state.routing_decision` from the `RoutingDecision` returned by `m9_intent_router.route(...)`. M8 reads `state.routing_decision.selected_target.name` at stage 1 to branch between pipeline variants (v0.2.0 all variants execute the same 23-stage graph except `m8.research_single_tool` which hits the zero-fan-out AC5.8 path at stage 8; Phase 3 may differentiate further).
- **AC17.3:** M12 handles the async dispatch wrapper per Steering Rule 11. M12 wraps `run()` in `asyncio.to_thread` and polls for completion. M8 itself is synchronous.
- **AC17.4:** M8 publishes a DECISION-LOG entry for any change to: `PipelineState` shape, `PipelineResult` shape, `PIPELINE_NAMES`, `HITL_GATES`, `STAGE_NAMES`, `VALID_REASON_CODES`, `SCHEMA_VERSION`, public `__all__`. Rename policy: renaming a `stage_N_name` is a MAJOR bump; old name MAY be aliased for one minor-version deprecation window; audit consumers MUST query on `stage_number` (stable) rather than `stage_name`.
- **AC17.5:** M12 spec (when v0.1.0 ships) cites this section by name.
- **AC17.6:** Integration contract test: `tests/integration/test_m12_m8_supervisor_call.py` constructs a fake `RoutingDecision` (from `m9_intent_router.models`), builds a `PipelineState`, calls `research_pipeline.run()` with `FakeGatewayClient` + `FakeAuditClient` + `FakeSonnetClient` + `InMemorySaver`, asserts round-trip shape. Does NOT import M12 (Phase 2 depth-first).

### R18. Integration Point with M10 Audit Logger — via `AuditClient` Protocol (v0.2.0)

M8 NEVER imports M10. **v0.2.0 change (Required Fix 4):** M8 writes audit events directly to M10's FastAPI `/audit` endpoint via the `M10AuditClient` Protocol impl — NOT via `GatewayClient.emit_audit(...)` (which does not exist on M6). M10 internally fans out to the 3-tier WORM (Langfuse + S3 Object Lock + CRM per Steering Rule 6). M8 is unaware of the 3-tier split.

**Acceptance Criteria:**
- **AC18.1:** M8 has zero import-time or runtime reference to M10 Python packages. Task 2 AST scan confirms. M8 talks to M10 via `M10AuditClient` Protocol implementation which HTTP-POSTs to the M10 FastAPI endpoint — a runtime network call, not a Python import. SHARED-WITH-M10 — see Known Blockers row 18.
- **AC18.2:** Per-stage `StageAuditPayload` is serialized to JSON via `canonical_json()` (AC8.4) and passed to `AuditClient.emit({"source": "m8", "event_type": "m8.stage_completed", "payload": payload_dict})`.
- **AC18.3:** Terminal `PipelineTerminalAuditPayload` is emitted with `event_type="m8.pipeline_terminal"` at the end of `run()` regardless of `PipelineResult.status`.
- **AC18.4:** HITL gate entry emits `event_type="m8.hitl_gate_entered"`; HITL gate approval emits `event_type="m8.hitl_gate_approved"`; HITL gate rejection emits `event_type="m8.hitl_gate_rejected"`; HITL timeout emits `event_type="m8.hitl_gate_timed_out"`. Four sub-event types.
- **AC18.5:** M8 does NOT write to Langfuse directly, does NOT write to S3 Object Lock directly, does NOT write to CRM directly. All three are M10's concern, reached through M10's FastAPI `/audit` route.
- **AC18.6:** M8 audit payloads are ARCH-06 v3 §Gap 2 "M8 Pipeline" row-compliant: every payload carries `stage_number`, `model_version`, `prompt_template_version`, `input_sha256`, `output_sha256`. AC8.1.
- **AC18.7:** Audit write failures (`AuditClient.emit` raises `AuditEmitError` after 1 retry) are terminal per AC8.5. M8 does NOT fall back to Langfuse-direct, S3-direct, or CRM-direct — the Protocol boundary is enforced.
- **AC18.8:** `resume_from_gate(thread_id, approval)` is idempotent at the audit level — a second call with the same `(thread_id, approval.approval_token)` returns the cached `PipelineResult` from the first call (stored in state via LangGraph checkpointer behavior for consumed `interrupt()` tokens) and does NOT emit a second `m8.hitl_gate_approved` audit row (Recommended Fix 12 from LLMJ v1 recommended list). Task 8 asserts.

---

## FSI Pipeline Stage Catalog — 23 Stages (Pinned)

Stage numbers (1-23) map one-to-one to 006 v2 `pipeline.py::_all_stage_methods()` (verified 2026-05-17, lines 160-174). Stage names match 006 for 21 of 23 stages; two names (stages 12, 21) are deliberately renamed in 007 — see DECISION-LOG D13. Categories: `research`, `synthesis`, `compliance`, `hitl`, `terminal`.

| # | `STAGE_NAMES[i-1]` | 006 Name | Phase | Category | LLM | HITL | Tool(s) via M6 | Description |
|---|--------------------|----------|-------|----------|-----|------|----------------|-------------|
| 1 | `stage_1_intake` | `_stage_1_intake` | A: Intake | research | Sonnet | no | — | Parse utterance + `routing_decision.entities`. Extract `event_type`, `timeframe`, `focus_areas`. |
| 2 | `stage_2_crm_context` | `_stage_2_crm_context` | A | research | None | no | `salesforce.fetch_client`, `.fetch_household` | Fetch client + household + prior research. M4 filters MNPI. |
| 3 | `stage_3_market_data` | `_stage_3_market_data` | B: Data | research | None | no | `bloomberg.market_data` | Quotes, fundamentals per ticker. |
| 4 | `stage_4_news_sentiment` | `_stage_4_news_sentiment` | B | research | Sonnet | no | `news_api.scan` | Sonnet summarizes news headlines to sentiment. Budget 10K. |
| 5 | `stage_5_sec_filings` | `_stage_5_sec_filings` | B | research | None | no | `sec_edgar.fetch_10k/10q/8k` | Latest filings, budget-trimmed server-side. |
| 6 | `stage_6_transcript_analysis` | `_stage_6_transcript_analysis` | B | synthesis | Sonnet | no | `bloomberg.earnings_transcript` | Sonnet condenses transcript. Budget 8K. |
| 7 | `stage_7_data_quality_gate` | `_stage_7_data_quality_gate` | **HITL 1** | hitl | None | **yes** | — | **HITL GATE 1** — data review. Approver: `research_specialist` OR `supervising_advisor`. |
| 8 | `stage_8_financial_modeling` | `_stage_8_financial_modeling` | C: Analysis | synthesis | Sonnet | no | — | Fan-out (`Send`) per instrument. Zero-fan-out case per AC5.8. Budget 8K/instrument. |
| 9 | `stage_9_dcf_valuation` | `_stage_9_dcf_valuation` | C (mapped) | synthesis | Sonnet | no | — | Per-instrument DCF. Budget 6K. |
| 10 | `stage_10_comps_analysis` | `_stage_10_comps_analysis` | C (mapped) | synthesis | Sonnet | no | `bloomberg.peer_comps` | Per-instrument comps. Budget 6K. |
| 11 | `stage_11_monte_carlo` | `_stage_11_monte_carlo` | C (mapped) | synthesis | None | no | — | Deterministic Monte Carlo. Ported from 006 `monte_carlo.py`. |
| 12 | `stage_12_cross_source_synthesis` **[RENAMED vs 006]** | `_stage_12_sentiment_synthesis` | C: Reduce | synthesis | Sonnet | no | — | **REDUCE** across per-instrument results + all sources. 007 rename reflects map-reduce scope (D13). Budget 15K. |
| 13 | `stage_13_analysis_review_gate` | `_stage_13_analysis_review_gate` | **HITL 2** | hitl | None | **yes** | — | **HITL GATE 2** — analysis review. Approver: `compliance_officer`. |
| 14 | `stage_14_thesis_generation` | `_stage_14_thesis_generation` | D: Recommendation | synthesis | Sonnet | no | — | Thesis narrative. Budget 8K. |
| 15 | `stage_15_catalyst_identification` | `_stage_15_catalyst_identification` | D | synthesis | Sonnet | no | — | Catalyst list. Budget 4K. |
| 16 | `stage_16_risk_assessment` | `_stage_16_risk_assessment` | D | synthesis | Sonnet | no | — | Risk list. Budget 4K. |
| 17 | `stage_17_rating_determination` | `_stage_17_rating_determination` | D | synthesis | Sonnet | no | — | `rating ∈ {strong_buy,buy,hold,sell,strong_sell}`. Budget 2K. |
| 18 | `stage_18_target_price_calc` | `_stage_18_target_price_calc` | D | synthesis | None | no | — | Deterministic weighted avg → `target_price`. |
| 19 | `stage_19_brief_assembly` | `_stage_19_brief_assembly` | E: Output | terminal | Sonnet | no | — | Assemble draft `ResearchBrief`. Budget 12K. |
| 20 | `stage_20_compliance_check` | `_stage_20_compliance_check` | E | compliance | **OPA** | no | `compliance.screen` (→ M2/M4 via M6) | **NO LLM**. OPA decision; DENY via `GatewayError("authority_denied")`, ESCALATE → Gate 3. |
| 21 | `stage_21_anti_fabrication_check` **[RENAMED vs 006]** | `_stage_21_final_approval_gate` | **HITL 3** | hitl | None | **yes** | — | **HITL GATE 3** — anti-fab check FIRST, then supervisor approval. 007 rename reflects hybrid (D13). Approver: `supervising_advisor`. |
| 22 | `stage_22_crm_writeback` | `_stage_22_crm_writeback` | E | terminal | None | no | `salesforce.writeback_research_brief` | Write final brief to CRM (M4 re-screens). |
| 23 | `stage_23_delivery_notify` | `_stage_23_delivery_notify` | E | terminal | None | no | — | Emit terminal audit. Return `PipelineResult(status="completed", ...)`. |

### Category Summary

- **research**: 1, 2, 3, 4, 5. **synthesis**: 6, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 19. **compliance**: 20. **hitl**: 7, 13, 21. **terminal**: 22, 23.

### LLM-Bearing Stages

Stages 1, 4, 6, 8, 9, 10, 12, 14, 15, 16, 17, 19 — **12 stages** call Sonnet. Stages 2, 3, 5, 11, 18, 20, 22, 23 — 8 non-LLM. Stages 7, 13, 21 — 3 HITL gates (stage 21 also runs anti-fab pre-gate).

### Stage Name Immutability Contract

`STAGE_NAMES` frozen at module import. Renaming a stage = MAJOR bump (AC17.4). Audit consumers MUST query on `stage_number` (integer 1..23) — the stable identifier. The v0.1.0 → v0.2.0 transition did NOT rename any stage; the two 007 names that differ from 006 have been in 007 since v0.1.0 and remain in v0.2.0 with rename rationale in D13 (Required Fix 6 closure).

---

## HITL Gate Specification — 3 Gates

Each gate: trigger + approver role + timeout + escalation + token derivation. All fail-closed per Steering Rule 8.

### Gate 1 — Stage 7 — Data-Gathering Review

| Field | Value |
|-------|-------|
| **Trigger** | Stages 1-6 complete. Unconditional. |
| **Approver Role** | `research_specialist` OR `supervising_advisor`. |
| **Payload** | `HitlGatePayload(gate_id=1, pipeline_run_id, thread_id, stage_number=7, summary: {instruments, source_count, total_data_points, missing_sources, token_budget_consumed_so_far})`. |
| **Timeout** | `config.hitl_timeout_seconds` (default 14,400s). |
| **Token** | `HMAC-SHA-256(vault_hmac_key, f"1\|{approver_aid_sub}\|{iso_timestamp}\|{thread_id}")`. |
| **Approve** | Resume stage 8. Audit `m8.hitl_gate_approved`, `reason_code=None`. |
| **Reject** | Terminate; `reason_code="m8_hitl_denied"`, `paused_gate=1`. New `thread_id` required to retry. |
| **Timeout** | Terminate; `reason_code="m8_hitl_timeout"`. |
| **Role Mismatch** | `reason_code="m8_hitl_role_mismatch"`. |

### Gate 2 — Stage 13 — Analysis Review

| Field | Value |
|-------|-------|
| **Trigger** | Stages 8-12 complete. Also triggered when `state.compliance_escalation=True`. |
| **Approver Role** | `compliance_officer`. |
| **Payload** | `HitlGatePayload(gate_id=2, ..., summary: {per_instrument_count, dropped_instruments, thesis_draft_sha256, risks_draft_sha256, cross_source_synthesis_sha256, estimated_reg_bi_risk})`. |
| **Timeout** | 4h. |
| **Token** | `HMAC-SHA-256(vault_hmac_key, f"2\|{approver_aid_sub}\|{iso_timestamp}\|{thread_id}")`. |
| **Terminal paths** | Approve → stage 14; Reject → `m8_hitl_denied`; Timeout → `m8_hitl_timeout`; Role Mismatch → `m8_hitl_role_mismatch`. |

### Gate 3 — Stage 21 — Final Approval (Anti-Fabrication + Supervisor Review)

| Field | Value |
|-------|-------|
| **Trigger** | Stages 14-20 complete. Stage 21 runs anti-fab FIRST (numeric-token audit against `state.data_sources`), populates `state.anti_fabrication_failures`, THEN pauses for human approval. Rename vs 006 reflects combined responsibility (D13). |
| **Approver Role** | `supervising_advisor`. |
| **Payload** | `HitlGatePayload(gate_id=3, ..., summary: {final_brief_sha256, rating, target_price, anti_fabrication_passed, anti_fabrication_failures, compliance_escalation, source_count, total_wall_clock_seconds})`. |
| **Timeout** | 4h. |
| **Token** | `HMAC-SHA-256(vault_hmac_key, f"3\|{approver_aid_sub}\|{iso_timestamp}\|{thread_id}")`. |
| **Terminal paths** | Approve → stage 22 (CRM writeback); Reject → `m8_hitl_denied`; Timeout → `m8_hitl_timeout`; Role Mismatch → `m8_hitl_role_mismatch`. |

### Gate Invariants

- `HITL_GATES == {7, 13, 21}`. Adding a gate = MAJOR bump.
- Every gate has terminal timeout + rejection paths (Steering Rule 8).
- Role-stratification: Gate 1 ⊆ Gate 3 approvers; Gate 2 exclusively compliance.
- HITL wait time NOT counted toward `max_pipeline_wall_clock_seconds`.
- **Key-rotation invariant (v0.2.0)**: quarterly HMAC rotation per AC4.12; cross-pod-boundary verification fails with `m8_hitl_token_expired`.

---

## Token Budget Table — Per-Stage `maxTokens` for Sonnet

Hard-capped via `inferenceConfig.maxTokens` in every `SonnetClient.generate()` call. Defaults sourced from `PipelineConfig.token_budgets`.

| Stage | Stage Name | Max Output Tokens | Rationale |
|-------|------------|-------------------|-----------|
| 1 | `stage_1_intake` | 2,000 | Parse + classify — short structured output. |
| 4 | `stage_4_news_sentiment` | 10,000 | Summarize 50-200 news items. |
| 6 | `stage_6_transcript_analysis` | 8,000 | Condense multi-thousand-line transcript. |
| 8 | `stage_8_financial_modeling` | 8,000/instrument | Parallel fan-out — budget × cap (10). |
| 9 | `stage_9_dcf_valuation` | 6,000/instrument | Structured DCF output. |
| 10 | `stage_10_comps_analysis` | 6,000/instrument | Structured comps + multiples. |
| 12 | `stage_12_cross_source_synthesis` | 15,000 | **LARGEST** — reduce across instruments + sources. |
| 14 | `stage_14_thesis_generation` | 8,000 | Thesis narrative. |
| 15 | `stage_15_catalyst_identification` | 4,000 | Structured catalyst list. |
| 16 | `stage_16_risk_assessment` | 4,000 | Structured risk list. |
| 17 | `stage_17_rating_determination` | 2,000 | Rating value + justification. |
| 19 | `stage_19_brief_assembly` | 12,000 | Final brief markdown + structured fields. |

**Aggregate budget per pipeline run** (single instrument): ~85K output. With 10-instrument fan-out: ~285K upper bound. At Sonnet $15/1M × 285K ≤ $4.27 output + $3/1M × 500K input ≤ $1.50 input. Total ≤ $5.80 per run.

### Budget Overrun Handling

`stop_reason == "max_tokens"` AND `output_tokens == max_tokens` → emit `reason_code="m8_token_budget_exceeded"` in audit. SOFT warning; truncated output is still used. No runtime budget enforcement beyond `maxTokens` in Phase 2.

---

## LangGraph State Schema — `PipelineState` TypedDict

`PipelineState` is a `typing.TypedDict` with `total=False`.

```python
# src/m8_pipeline_engine/state.py

from __future__ import annotations
from datetime import datetime
from typing import Any, Literal, Optional, TypedDict

from m3_schema_registry import (
    Client, Holding, Household, ResearchBrief, ResearchSource,
    SecurityIdentifier, InteractionSummary, TaxLot,
)
# NOTE: v0.1.0 imported ComplianceCheck here; dropped in v0.2.0 per Required Fix 9 —
# never populated; stage 20 emits compliance_decision/rule/wsp directly into state.
from m9_intent_router.models import RoutingDecision  # annotation-only


class PipelineState(TypedDict, total=False):
    # ---- IMMUTABLE INPUT (set by M12) ----
    trace_id: str
    thread_id: str
    pipeline_run_id: str
    tenant_id: str
    firm_id: str
    routing_decision: RoutingDecision
    user_utterance: str
    runtime: Literal["managed_agents", "strands"]
    archetype: Literal[
        "tier1_investment_bank", "tier2_asset_manager",
        "tier3_broker_dealer", "tier4_independent_ria",
        "tier5_hedge_fund",
    ]
    supervisor_aid_token: str

    # ---- STAGE 1 ----
    intake: dict[str, Any]
    instruments: list[str]

    # ---- STAGE 2 ----
    crm_context: dict[str, Any]
    primary_client: Optional[Client]
    primary_household: Optional[Household]
    prior_holdings: list[Holding]            # each Holding.tax_lots[*].cost_basis_method REQUIRED per A12 (v0.2.0 Req-Fix 5)
    prior_briefs: list[str]

    # ---- STAGES 3-6 ----
    market_data: dict[str, dict[str, Any]]
    news_items: dict[str, list[dict]]
    sec_filings: dict[str, dict[str, str]]
    transcript_summary: dict[str, str]

    # ---- GATE 1 ----
    gate_1_payload: dict[str, Any]
    gate_1_approved_by: Optional[str]
    gate_1_approved_at: Optional[datetime]

    # ---- STAGE 8 MAP-REDUCE ----
    discovered_instruments: list[str]
    dropped_instruments: list[str]
    per_instrument_results: dict[str, dict[str, Any]]
    per_instrument_errors: dict[str, str]

    # ---- STAGE 12 REDUCE ----
    cross_source_synthesis: dict[str, Any]

    # ---- GATE 2 ----
    gate_2_payload: dict[str, Any]
    gate_2_approved_by: Optional[str]
    gate_2_approved_at: Optional[datetime]

    # ---- STAGES 14-18 ----
    thesis: str
    catalysts: list[str]
    risks: list[str]
    rating: Literal["strong_buy","buy","hold","sell","strong_sell"]
    target_price: Optional[float]

    # ---- STAGE 19 ----
    draft_brief: Optional[ResearchBrief]
    data_sources: list[ResearchSource]
    interaction_summary: Optional[InteractionSummary]

    # ---- STAGE 20 ----
    compliance_decision: Literal["ALLOW","DENY","ESCALATE"]
    compliance_escalation: bool              # survives checkpoint per AC3.10 / A24 (Rec-Fix 2)
    # v0.1.0 had: compliance_check: Optional[ComplianceCheck]  -- DROPPED v0.2.0 (Req-Fix 9)
    compliance_rule_applied: Optional[str]
    compliance_wsp_section: Optional[str]

    # ---- GATE 3 ----
    gate_3_payload: dict[str, Any]
    gate_3_approved_by: Optional[str]
    gate_3_approved_at: Optional[datetime]
    anti_fabrication_failures: list[dict[str, Any]]

    # ---- TERMINAL ----
    final_brief: Optional[ResearchBrief]
    pipeline_status: Literal[
        "completed", "paused", "rejected", "timed_out",
        "terminated", "failed",
    ]
    terminal_reason_code: Optional[str]

    # ---- AUDIT BOOKKEEPING ----
    clock_stamps: dict[int, float]
    total_input_tokens: int
    total_output_tokens: int
    slow_alert_emitted: bool                 # AC8.11 exactly-once gate (v0.2.0)
```

### State Field Invariants

- **AC1.2**: Required keys at `run()` entry: `{trace_id, thread_id, pipeline_run_id, tenant_id, firm_id, routing_decision, user_utterance, runtime, archetype}`. Missing any → `ValueError("incomplete_initial_state")`.
- **Mutation immutability**: LangGraph copy-on-write; stage functions return partial dicts. MUST NOT `state["foo"] = bar` in-place. Task 11 asserts.
- **MNPI residency**: `prior_holdings`, `market_data`, `news_items`, `sec_filings`, `crm_context` ONLY enter state post-M4-filter. Task 11 property asserts.
- **Cost basis preservation (v0.2.0 rewritten per Required Fix 5)**: every `Holding` in `prior_holdings` has `tax_lots: list[TaxLot]`. For every Holding, every `tl` in `holding.tax_lots` MUST satisfy `tl.cost_basis_method is not None`. `Holding` has NO `cost_basis_method` field — verified `src/m3_schema_registry/types.py` line 719-721 docstring. M3's `@field_validator cost_basis_method_never_null` raises at `TaxLot` construction; M8 defensively walks `for h in state.get("prior_holdings", []): for tl in h.tax_lots: assert tl.cost_basis_method is not None` in `_validate_state_invariants`. Failure → `reason_code="m8_invalid_state"`. Task 11 `test_cost_basis_preserved` asserts.
- **Schema version**: MINOR bump to add; MAJOR to remove/rename.
- **Compliance escalation persistence (v0.2.0 A24 Rec-Fix 2)**: `state.compliance_escalation` survives checkpoint round-trip. Task 9 asserts.

---

## Checkpointer Contract

LangGraph's `BaseCheckpointSaver` Protocol. Phase 2 uses `PostgresSaver`. Phase 3 reserves `DynamoDbSaver`.

### `PostgresSaver` (Phase 2 default)

- Import: `from langgraph.checkpoint.postgres import PostgresSaver`
- Construction: `PostgresSaver.from_conn_string(dsn)` — DSN Vault-resolved at startup.
- Schema: `m8_checkpoints` (segregated per Known Blockers row 4).
- Migration: dedicated K8s Job pre-deploy. Readiness probe gates on `checkpointer.ready()`.
- Concurrency: 3 connections per pod (matches tenant semaphore).

### `DynamoDbSaver` (Phase 3 reserved)

- Phase 2 stub: `__init__` raises `NotImplementedError("Phase 3")`.

### `InMemorySaver` (Tests)

Used by Tasks 1, 3, 4, 5, 6, 8, 9, 10, 11.

### Fail-Closed Contract

- Checkpoint write failure → audit `reason_code="m8_checkpoint_write_failed"`, `status="terminated"`. No silent retry.
- Read failure on resumption → same path.
- Schema mismatch / JSON-decode failure → same path.
- `state.compliance_escalation` survives round-trip (A24 Rec-Fix 2).

---

## M6 Gateway Call Pattern (REWRITTEN in v0.2.0 per Required Fixes 1-3)

M8 issues every tool call through `GatewayClient.call(request: GatewayRequest) -> GatewayResponse`. Request construction + response handling is centralized in `_invoke_tool(gateway, ...)` helper to ensure every stage uses the same pattern.

**Critical v0.2.0 corrections vs v0.1.0:**
- `GatewayRequest` and `GatewayResponse` are `@dataclass(frozen=True)` (M6's real shape), NOT Pydantic v2 models.
- `GatewayRequest.vendor_adapter` is REQUIRED non-None. v0.1.0's `vendor_adapter=None` construction raises `ValueError` at `__post_init__`. v0.2.0 introduces a `VendorAdapterResolver` seam — `_invoke_tool` resolves the adapter via `resolver.resolve(tool_name)` before constructing the request.
- Failure paths are RAISED as `GatewayError(reason)`, NOT returned as `GatewayResponse` fields. v0.1.0's `response.decision == "DENY"` / `response.reason == "vendor_unavailable"` branches were unreachable.

### `_invoke_tool` Helper Signature (v0.2.0)

```python
# src/m8_pipeline_engine/gateway_client.py (excerpt)
from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class VendorAdapterResolver(Protocol):
    """Protocol mirroring M6's VendorAdapterRegistry surface.

    M8 never imports M6's registry; the production impl
    `LocalVendorAdapterResolver` wraps a registry snapshot fetched
    from M6's FastAPI /adapters route at compile time.
    """

    def resolve(self, tool_name: str) -> Any:  # Returns VendorAdapter-shaped object
        ...


@dataclass(frozen=True)
class GatewayRequest:
    """Dataclass-shaped copy of M6's GatewayRequest.

    Field-for-field match with src/m6_mcp_gateway/gateway.py line 118.
    NOT a Pydantic model (v0.1.0 drift corrected in v0.2.0 Req-Fix 1).
    """
    token: str
    action: str
    tool_name: str
    mcp_server: str
    payload: Any
    trace_id: str
    firm_id: str
    target: Mapping[str, Any]
    context: Mapping[str, Any]
    session_id: Optional[str]
    vendor_adapter: Any  # VendorAdapter-shaped; REQUIRED non-None


@dataclass(frozen=True)
class GatewayResponse:
    """Dataclass-shaped copy of M6's GatewayResponse.

    Only appears on the ALLOW / ESCALATE success paths of
    TrustAwareGateway.call(). Failure paths raise GatewayError.
    """
    decision: str  # Literal["ALLOW", "DENY", "ESCALATE"]; DENY never returned, only raised
    result: Any
    liability_report: Optional[Any]
    trace_id: str
    latency_ms: int
    provenance_head: str
    rule_applied: Optional[str]
    wsp_section: Optional[str]
    reason: Optional[str]


class GatewayError(Exception):
    """M6's raised-failure type. Import-shape compatible; M8 defines
    its own copy to avoid m6_mcp_gateway import. M8 catches by
    duck-typing on .reason attribute.
    """
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


def _invoke_tool(
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    *,
    trace_id: str,
    firm_id: str,
    tenant_id: str,
    aid_token: str,              # from state.supervisor_aid_token
    tool_name: str,              # e.g., "sec_edgar.fetch_10k"
    mcp_server: str,             # e.g., "sec_edgar" or "bloomberg"
    action: str,                 # e.g., "research.read", "compliance.screen"
    payload: dict,
    target: dict,
    context: dict,
    max_retries: int = 2,
) -> GatewayResponse:
    """Construct request, resolve adapter, call gateway, branch on outcome.

    Raises nothing — always returns GatewayResponse. Failure branches
    are captured into the stage's reason_code by the caller.
    """
    vendor_adapter = resolver.resolve(tool_name)  # v0.2.0 — was None in v0.1.0
    request = GatewayRequest(
        token=aid_token,
        action=action,
        tool_name=tool_name,
        mcp_server=mcp_server,
        payload=payload,
        trace_id=trace_id,
        firm_id=firm_id,
        target=target,
        context=context,
        session_id=None,
        vendor_adapter=vendor_adapter,
    )
    return gateway.call(request)  # May raise GatewayError; caller catches.
```

### Request Field Conventions

- `action`: dotted path. M8 uses `"research.read"` for read-only vendor calls, `"research.writeback"` for CRM writes (stage 22), `"compliance.screen"` for stage 20. Every action string is pre-registered with M2/M4 OPA policy (M2 owns the action vocabulary).
- `tool_name`: dotted path `{server}.{operation}`. Must match M6's registered tool manifest. See AC7.10 for the Phase 2 list.
- `mcp_server`: `{server}` prefix of `tool_name`. E.g., `tool_name="sec_edgar.fetch_10k"` → `mcp_server="sec_edgar"`.
- `target`: identifies the compliance subject. For data reads: `{"canonical_type": "Client", "client_id": "..."}` or `{"canonical_type": "SecurityProfile", "ticker": "NVDA"}`. M2 evaluates policy against `target`.
- `context`: routing hints. M8 passes `{"pipeline_run_id", "stage_number", "stage_name"}` so M6 / M10 can correlate. Never PII.
- `payload`: vendor-specific request body. For `sec_edgar.fetch_10k`: `{"ticker": "NVDA", "max_chunks": 20}`. M8 never embeds raw client PII in payload.
- `vendor_adapter`: resolved via `VendorAdapterResolver.resolve(tool_name)` — v0.2.0. Never None.

### Response Handling (REWRITTEN v0.2.0 per Required Fix 3)

M8 wraps every `gateway.call(...)` in `try / except GatewayError as exc`. Only the ALLOW path (and the rare success-path ESCALATE) return a `GatewayResponse`.

```python
# Excerpt — every stage's M6 call follows this pattern

from m8_pipeline_engine.gateway_client import GatewayError, _invoke_tool

def _call_with_branching(gateway, resolver, ...) -> tuple[Optional[GatewayResponse], Optional[str]]:
    """Returns (response, reason_code). Exactly one is non-None."""
    try:
        response = _invoke_tool(gateway, resolver, ...)
    except GatewayError as exc:
        # M6's frozen reason vocabulary — see src/m6_mcp_gateway/gateway.py line 58
        if exc.reason == "authority_denied":
            return None, "m8_compliance_denied"
        if exc.reason == "authority_escalated":
            # Not a reason_code; sets state.compliance_escalation=True upstream
            return None, "__ESCALATION__"
        if exc.reason == "vendor_unavailable":
            # Retry once with 500ms backoff; second failure falls to m8_stage_failed
            return None, "m8_stage_failed"
        if exc.reason == "vendor_error":
            return None, "m8_stage_failed"
        if exc.reason == "rate_limited":
            # Wait 2s + retry once; second failure falls to m8_stage_failed
            return None, "m8_stage_failed"
        if exc.reason == "circuit_open":
            return None, "m8_stage_failed"
        if exc.reason == "mnpi_leakage_scan":
            return None, "m8_mnpi_leaked_through_gateway"
        if exc.reason == "mnpi_filter_error":
            return None, "m8_mnpi_leaked_through_gateway"  # defensive
        if exc.reason == "audit_failed":
            # M6's audit chain failed; M8's own audit may still succeed
            return None, "m8_audit_write_failed"
        if exc.reason == "invalid_request":
            # Developer error — M8 constructed a malformed request
            return None, "m8_stage_failed"
        if exc.reason == "invalid_identity":
            # Unexpected — M12 should have verified upstream
            return None, "m8_stage_failed"
        # Any unmapped reason → generic stage_failed (defensive)
        return None, "m8_stage_failed"

    # Success path: ALLOW or ESCALATE (returned, not raised)
    if response.decision == "ALLOW":
        return response, None
    if response.decision == "ESCALATE":
        # rare — M6 may return ESCALATE with a populated result
        return response, "__ESCALATION__"
    # DENY is never returned (M6 raises GatewayError('authority_denied')); defensive
    return None, "m8_compliance_denied"
```

The success path continues with `response.result` as the stage output. The `__ESCALATION__` sentinel signals the caller to set `state.compliance_escalation=True` without setting a failure `reason_code`.

### Audit Linkage

Every `_invoke_tool` call is followed by a `StageAuditPayload` emission via the injected `AuditClient` (v0.2.0 — was `GatewayClient.emit_audit` in v0.1.0, withdrawn) with fields `tool_name`, `gateway_decision` (`"ALLOW"` on success, `"DENY"` on caught `authority_denied`, `"ESCALATE"` on either escalation path), `rule_applied`, `wsp_section`. Task 10 asserts. Task 15 `test_gateway_error_branches` exhaustively exercises every `VALID_GATEWAY_REASONS` string via `FakeGatewayClient` raising pre-seeded `GatewayError` instances.

---

## Integration Point with M12 (Supervisor Runtime) — Request/Response Shapes

M12 is M8's only direct caller in Phase 2 (ARCH-09 column 8 `*`). In-process Python call — no FastAPI route, no MCP, no REST.

### Call Site (Python, M12-side)

```python
# M12 Supervisor — src/m12_supervisor/dispatch.py (illustrative, lives in M12 spec)
import uuid
from m5_config_loader import Archetype, Runtime, load_pipeline_config
from m8_pipeline_engine import (
    research_pipeline, PipelineState, PipelineResult,
)
from m9_intent_router import RoutingDecision

_CFG = load_pipeline_config()       # startup
_GATEWAY = M6GatewayClient(...)     # injected elsewhere
_AUDIT = M10AuditClient(...)        # v0.2.0 — new separate client per Req-Fix 4
_LLM = select_llm_client(_CFG)

def dispatch_research_pipeline(
    user_utterance: str,
    routing_decision: RoutingDecision,
    aid_claims,  # verified upstream
    trace_id: str,
) -> PipelineResult:
    initial_state: PipelineState = {
        "trace_id": trace_id,
        "thread_id": f"thread-{uuid.uuid4().hex}",
        "pipeline_run_id": f"run-{uuid.uuid4().hex}",
        "tenant_id": aid_claims.firm_id,
        "firm_id": aid_claims.firm_id,
        "routing_decision": routing_decision,
        "user_utterance": user_utterance,
        "runtime": Runtime(aid_claims.runtime).value,
        "archetype": Archetype(aid_claims.archetype).value,
        "supervisor_aid_token": aid_claims.raw_token,
    }
    return research_pipeline.run(initial_state, thread_id=initial_state["thread_id"])
```

### Request Shape (M12 → M8)

- **Positional**: `initial_state: PipelineState` (TypedDict — serializable to JSON).
- **Keyword**: `thread_id: str` (matches regex `^[a-z0-9][a-z0-9\-]{7,63}$` per AC1.3).
- **Pre-conditions**: `initial_state.routing_decision.selected_target.kind == "pipeline"` (AC1.10); `initial_state.routing_decision.selected_target.name` in `PIPELINE_NAMES` (AC1.11).

### Response Shape (M8 → M12) — Happy Path

```json
{
  "status": "completed",
  "pipeline_run_id": "run-7f3c9a1e",
  "thread_id": "thread-8a3d0022",
  "research_brief": {
    "brief_id": "uuid-...",
    "security_identifier": {"ticker": "NVDA"},
    "analyst_id": "agent-42",
    "rating": "buy",
    "target_price": 1280.0,
    "summary": "...",
    "thesis": "...",
    "catalysts": ["Q1 earnings", "GTC conference"],
    "risks": ["China export restrictions"],
    "sources": [{"type": "sec_filing", "identifier": "NVDA 10-K 2026"}],
    "pipeline_run_id": "run-7f3c9a1e",
    "hitl_gates_passed": ["gate_1", "gate_2", "gate_3"],
    "anti_fabrication_score": 0.98,
    "created_at": "2026-05-20T14:37:22Z",
    "trace_id": "supv-2026-05-20-7f3c9a1e"
  },
  "final_stage": 23,
  "paused_gate": null,
  "wall_clock_seconds": 847.3,
  "total_tokens": 42850,
  "reason_code": null,
  "dropped_instruments": []
}
```

### HITL Pause Response Shape (M8 → M12)

```json
{
  "status": "paused",
  "pipeline_run_id": "run-7f3c9a1e",
  "thread_id": "thread-8a3d0022",
  "research_brief": null,
  "final_stage": 7,
  "paused_gate": 1,
  "wall_clock_seconds": 142.7,
  "total_tokens": 8240,
  "reason_code": null,
  "dropped_instruments": []
}
```

M12 receives this, notifies the approver (via channel), and waits for `HitlApproval`. On resumption, M12 calls `research_pipeline.resume_from_gate(thread_id, approval) -> PipelineResult`.

### Async Dispatch Discipline (Steering Rule 11)

M12 dispatches `research_pipeline.run()` asynchronously via `asyncio.to_thread`. Max 3 concurrent per tenant is enforced by M8's `threading.Semaphore(3)` (R16 AC16.3). Beyond 3, M12 queues — M8 blocks up to 60s then fails with `m8_tenant_concurrency_exceeded`.

---

## Integration Point with M10 (Audit Logger) — via `AuditClient` Protocol (v0.2.0)

M8 NEVER imports M10. **v0.2.0 (Required Fix 4):** M8 writes audit events directly to M10's FastAPI `POST /audit` endpoint via the `M10AuditClient` Protocol impl. v0.1.0's design — piggy-backing on `GatewayClient.emit_audit(...)` — is withdrawn because M6's `TrustAwareGateway` has no such method. M10 internally fans out to the 3-tier WORM (Langfuse + S3 Object Lock + CRM per Steering Rule 6).

**SHARED-WITH-M10** (Known Blocker row 18): M10 v0.3.0 must ship the `POST /audit` endpoint. Until M10 v0.3.0, M8's integration test `test_m8_m10_audit_contract.py` is marked `xfail`.

### `AuditClient` Protocol (v0.2.0 — new)

```python
# src/m8_pipeline_engine/audit_client.py
from typing import Protocol, runtime_checkable


@runtime_checkable
class AuditClient(Protocol):
    """Thin HTTP client talking to M10's /audit endpoint.

    M8 defines this Protocol locally; M10AuditClient is the production
    impl; FakeAuditClient is the test impl. M8 never imports m10_*.
    """

    def emit(self, entry: dict) -> None:
        """POST to {base_url}/audit. Returns on 2xx.

        Retry once on 5xx; second 5xx raises AuditEmitError.
        Raises AuditEmitError on any non-2xx after retry.
        """
        ...


class AuditEmitError(Exception):
    """Unified failure type for AuditClient.emit. Wraps any underlying
    urllib / network / parse failure.
    """


class M10AuditClient:
    """Production impl. mTLS to M10's FastAPI private-subnet endpoint."""

    def __init__(
        self, *, base_url: str, mtls_cert_path: str, timeout_ms: int = 10000,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._cert = mtls_cert_path
        self._timeout = timeout_ms / 1000.0

    def emit(self, entry: dict) -> None:
        # urllib.request with mTLS HTTPSHandler; retry once on 5xx
        ...


class FakeAuditClient:
    """Test impl. Records every emit into a public list for assertions."""

    def __init__(self, fail_at: int = -1) -> None:
        self.entries: list[dict] = []
        self._fail_at = fail_at
        self._call_count = 0

    def emit(self, entry: dict) -> None:
        self._call_count += 1
        if self._call_count == self._fail_at:
            raise AuditEmitError("fake_failure")
        self.entries.append(entry)
```

### Audit Event Catalog

| Event Type | Emitted At | Payload Model | Reason Code |
|-----------|-----------|---------------|-------------|
| `m8.stage_started` | Entry to each stage 1..23 | `StageAuditPayload` with `output_sha256=""` (empty placeholder) | None |
| `m8.stage_completed` | Exit from each stage on success | `StageAuditPayload` | None |
| `m8.stage_failed` | Stage raises / returns failure | `StageAuditPayload` | One of `VALID_REASON_CODES` |
| `m8.hitl_gate_entered` | Entry to stages 7, 13, 21 | `StageAuditPayload` + `{gate_id, approver_role_required}` | None |
| `m8.hitl_gate_approved` | `resume_from_gate` with `approved=True` | `StageAuditPayload` + `{gate_id, approver_aid_sub, approver_timestamp}` | None |
| `m8.hitl_gate_rejected` | `resume_from_gate` with `approved=False` | Same + `{rejection_notes}` | `m8_hitl_denied` |
| `m8.hitl_gate_timed_out` | Reaper emits | Same | `m8_hitl_timeout` |
| `m8.pipeline_slow_alert` | Wall-clock > `alert_pipeline_wall_clock_seconds` (exactly once per AC8.11) | `PipelineTerminalAuditPayload` | None |
| `m8.single_tool_bypass` | Stage 12 on zero-fan-out (AC5.8) | `StageAuditPayload` | None |
| `m8.pipeline_terminal` | End of `run()` regardless of status | `PipelineTerminalAuditPayload` | Matches `PipelineResult.reason_code` |

### Audit Payload Example (`m8.stage_completed` after stage 12 cross-source synthesis)

```json
{
  "source": "m8",
  "event_type": "m8.stage_completed",
  "pipeline_run_id": "run-7f3c9a1e",
  "thread_id": "thread-8a3d0022",
  "tenant_id": "firm-abc-12345",
  "firm_id": "firm-abc-12345",
  "stage_number": 12,
  "stage_name": "stage_12_cross_source_synthesis",
  "trace_id": "supv-2026-05-20-7f3c9a1e",
  "timestamp": "2026-05-20T14:21:47.312Z",
  "model_version": "anthropic.claude-sonnet-4-5-20250929-v1:0",
  "prompt_template_version": "stage_12_cross_source_synthesis_prompt_v1.0.0_a7f3c9a1",
  "input_sha256": "c1b4...ef9a",
  "output_sha256": "dd02...12c7",
  "latency_ms": 8425,
  "input_tokens": 28500,
  "output_tokens": 14892,
  "reason_code": null,
  "tool_name": null,
  "gateway_decision": null,
  "rule_applied": null,
  "wsp_section": null
}
```

### M10 Fan-Out (informational, not M8's concern)

M10 receives this payload and fans out to:
1. **Langfuse**: observability trace keyed by `trace_id` + `pipeline_run_id`. Hot-accessible, 30-day retention.
2. **S3 Object Lock WORM**: immutable audit log, 6-year retention (SEC 17a-4 / FINRA 4511).
3. **CRM (Salesforce IR_Audit_Log__c or equivalent)**: summary row for compliance retrieval.

M8 does NOT see any of this. M8 just emits one JSON object per event via `AuditClient.emit`.

---

## Integration Point with M2/M4 (Policy Engine) — via M6, NOT Direct

M8 NEVER imports M2 or M4. Compliance pre-check at Stage 20 is a `GatewayClient.call(request)` with `action="compliance.screen"`. M6 routes the request through M2 (authority) and M4 (MNPI filter), both of which consult OPA/Rego. M8 receives the `GatewayResponse.decision` value (`ALLOW`/`ESCALATE`) on success or catches `GatewayError("authority_denied"|"authority_escalated")` on failure, per the v0.2.0 REWRITTEN response-handling pattern above.

### Stage 20 Call Pattern (v0.2.0 updated)

```python
# src/m8_pipeline_engine/nodes/stage_20_compliance_check.py (illustrative)

def stage_20_compliance_check(
    state: PipelineState,
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,
    audit: AuditClient,
    llm: LLMClient,  # unused — Steering Rule 14
) -> dict[str, Any]:
    draft = state["draft_brief"]
    response, reason_code = _call_with_branching(
        gateway, resolver,
        trace_id=state["trace_id"],
        firm_id=state["firm_id"],
        tenant_id=state["tenant_id"],
        aid_token=state.get("supervisor_aid_token", ""),
        tool_name="compliance.screen",
        mcp_server="m2_m4_compliance",
        action="compliance.screen",
        payload={
            "canonical_type": "ResearchBrief",
            "brief_sha256": compute_io_digest(draft.model_dump()),
            "tickers": list(state["instruments"]),
            "client_id": state["primary_client"].canonical_id if state.get("primary_client") else None,
            "archetype": state["archetype"],
        },
        target={"canonical_type": "ResearchBrief", "draft_sha256": compute_io_digest(draft.model_dump())},
        context={
            "pipeline_run_id": state["pipeline_run_id"],
            "stage_number": 20,
            "stage_name": "stage_20_compliance_check",
        },
    )
    if reason_code == "m8_compliance_denied":
        # Fail hard — caller captures in audit + terminates
        return {"compliance_decision": "DENY", "__reason_code__": reason_code}
    if reason_code == "__ESCALATION__":
        # Force Gate 3
        return {
            "compliance_decision": "ESCALATE",
            "compliance_escalation": True,
            "compliance_rule_applied": response.rule_applied if response else None,
            "compliance_wsp_section": response.wsp_section if response else None,
        }
    # ALLOW path
    return {
        "compliance_decision": "ALLOW",
        "compliance_escalation": False,
        "compliance_rule_applied": response.rule_applied,
        "compliance_wsp_section": response.wsp_section,
    }
```

### Invariants

- M8 never runs OPA. Never evaluates Rego. Never interprets a policy rule.
- M8 never re-implements any M4 MNPI filter. M4 post-filters every `GatewayResponse.result`; M8 accepts the filtered payload.
- Stage 20's LLM column = OPA (not Sonnet). Zero Sonnet calls in this stage.
- Steering Rule 14 (NO LLM for compliance) asserted.
- Stage 20 both-path decisions (ALLOW/ESCALATE success, DENY/ESCALATE failure) captured in audit with `gateway_decision` field.

---

## Error Code Map

Drives Task 15 exhaustive `VALID_REASON_CODES` meta-test. Every code in the frozenset (R11 AC11.1 — **20 codes in v0.2.0**) has exactly one row.

| # | `reason_code` | Triggered By | Detection Point | `PipelineResult.status` | Downstream Outcome |
|---|---------------|--------------|-----------------|-------------------------|--------------------|
| 1 | `m8_stage_failed` | Generic stage-level exception not mapped to a more specific code; also `GatewayError.reason` ∈ `{vendor_unavailable, vendor_error, rate_limited, circuit_open, invalid_request, invalid_identity}` after retry exhaustion | Any stage body | `failed` | Pipeline terminates; M10 counts per-stage failure rate |
| 2 | `m8_checkpoint_write_failed` | `checkpointer.put()` raises | `graph.py::_checkpoint_hook` | `terminated` | Pipeline terminates; ops alerted on sustained rate |
| 3 | `m8_audit_write_failed` | `AuditClient.emit()` raises `AuditEmitError` after one retry (v0.2.0 — was `GatewayClient.emit_audit` in v0.1.0) OR caught `GatewayError("audit_failed")` from M6's own audit chain | `audit_emit.py::_emit_with_retry` + `_invoke_tool` exception handler | `terminated` | Pipeline terminates; Steering Rule 6 (audit required) |
| 4 | `m8_hitl_timeout` | Reaper fires `config.hitl_timeout_seconds` after gate entry | `hitl.py::reap_timed_out_threads` | `timed_out` | M12 surfaces escalation to human operations |
| 5 | `m8_hitl_denied` | `resume_from_gate(approval.approved=False)` | `hitl.py::_apply_rejection` | `rejected` | Compliance review trail preserved; new `thread_id` required to retry |
| 6 | `m8_hitl_role_mismatch` | Approver's `aid.role` not in gate's allow-list | `hitl.py::_verify_approver_role` | `failed` | Investigative — possible credential theft, audit escalated |
| 7 | `m8_hitl_token_expired` | `abs(now - approver_timestamp) > config.hitl_timeout_seconds` OR HMAC key rotation mismatch (AC4.12) | `hitl.py::_verify_token` | `failed` | Replay defense / post-rotation; approver retries with fresh token |
| 8 | `m8_llm_5xx` | `SonnetClient.generate` raises `LlmProviderError(status_code ∈ 500..599)` after retries | `nodes/stage_N.py::_llm_call_wrapper` | `failed` | Pipeline terminates; ops alerted on sustained Bedrock 5xx |
| 9 | `m8_llm_4xx` | `LlmProviderError(status_code ∈ 400..499)` — config defect, never transient | Same | `failed` | Operator alert; no retry |
| 10 | `m8_llm_timeout` | `LlmTimeoutError` from Bedrock (`timeout_ms` exceeded) | Same | `failed` | Ops alert on regional Bedrock latency regression |
| 11 | `m8_llm_malformed_output` | `LlmMalformedOutputError` — Sonnet emits non-JSON where JSON required, or invalid enum value | Same | `failed` | Operator alert; prompt template review |
| 12 | `m8_compliance_denied` | `GatewayError("authority_denied")` raised at stage 20 OR at any mid-pipeline M6 call (v0.2.0 REWRITTEN from "GatewayResponse.decision == DENY") | `_invoke_tool` `except GatewayError` | `failed` | Compliance review; M2/M4 rule + wsp_section captured for investigation |
| 13 | `m8_mnpi_leaked_through_gateway` | `GatewayError("mnpi_leakage_scan")` OR `GatewayError("mnpi_filter_error")` raised (v0.2.0 REWRITTEN from "GatewayResponse.reason == mnpi_leakage_scan") | `_invoke_tool` `except GatewayError` | `failed` | Severe — Steering Rule 7 invariant violated in upstream; escalation to compliance team |
| 14 | `m8_map_reduce_too_wide` | Stage 8 discovers > `max_concurrent_instruments * 3` instruments | `nodes/stage_8_financial_modeling.py` | — (soft warning, pipeline continues with capped set) | Observability signal; does NOT fail pipeline |
| 15 | `m8_map_reduce_all_failed` | Stage 12 reducer finds `len(per_instrument_results) == 0` AND `len(discovered_instruments) > 0` (AC5.8 zero-fan-out case is NOT this — emits `m8.single_tool_bypass` instead) | `nodes/stage_12_cross_source_synthesis.py` | `failed` | All per-instrument branches errored; pipeline terminates |
| 16 | `m8_token_budget_exceeded` | `LlmGeneration.stop_reason == "max_tokens"` with truncated output | `nodes/stage_N.py::_check_budget` | — (soft warning) | Observability signal; budgets tuned in DECISION-LOG |
| 17 | `m8_wall_clock_exceeded` | Total wall-clock (excluding HITL) > `max_pipeline_wall_clock_seconds` | `graph.py::_wall_clock_check` | `timed_out` | Pipeline terminates; ops alert |
| 18 | `m8_tenant_concurrency_exceeded` | `threading.Semaphore(3).acquire(timeout=60)` times out | `graph.py::_acquire_tenant_slot` | `failed` | M12 backpressure; caller queues |
| 19 | `m8_anti_fabrication_failed` | Stage 21 finds numeric tokens in `draft_brief` not traceable to `data_sources` | `nodes/stage_21_anti_fabrication_check.py` | — (forwards to HITL Gate 3 with flag) | Human reviewer decides; NOT a hard fail |
| 20 | `m8_invalid_state` | Stage detects violated state invariant — specifically **any `tl.cost_basis_method is None` for `tl` in `holding.tax_lots` across `state.prior_holdings`** (v0.2.0 corrected per Required Fix 5 — v0.1.0 incorrectly referenced `Holding.cost_basis_method` which does not exist on `Holding` per `src/m3_schema_registry/types.py` line 719-721) | Any stage body via `_validate_state_invariants` | `failed` | Upstream bug; trace captured, pipeline terminates |

**Count verification**: `assert len(VALID_REASON_CODES) == 20` — Task 15 meta-test. If this ever fails, either R11 AC11.1 or this table must be updated in lockstep.

---

## Tasks — 20 Atomic Implementation Tasks

Tasks are ordered by dependency. Each task cites the Acceptance Criteria it satisfies. Tasks 1-3 are foundational; tasks 4-19 implement the 23 stages plus HITL; task 20 is the end-to-end integration contract test. Per-task reason-code coverage matrix for Tasks 14/16/17 added in v0.2.0 per Recommended Fix 3.

| # | Task | Deliverable Files | Satisfies AC | Depends On | xfail? |
|---|------|-------------------|--------------|------------|--------|
| 1 | **Bootstrap: LLMClient + GatewayClient + AuditClient Protocols + Fakes (v0.2.0 adds AuditClient)** | `src/m8_pipeline_engine/llm_client.py` (LLMClient Protocol, SonnetClient stub, FakeSonnetClient, reserved provider stubs, select_llm_client); `src/m8_pipeline_engine/gateway_client.py` (GatewayClient Protocol, M6GatewayClient stub, FakeGatewayClient, VendorAdapterResolver Protocol, LocalVendorAdapterResolver, GatewayRequest/Response @dataclass per Req-Fix 1, GatewayError per Req-Fix 3); `src/m8_pipeline_engine/audit_client.py` (AuditClient Protocol, M10AuditClient stub, FakeAuditClient, AuditEmitError per Req-Fix 4); `tests/unit/test_llm_client.py`; `tests/unit/test_gateway_client.py`; `tests/unit/test_audit_client.py` | AC6.1-6.12, AC7.1-7.11, AC8.10 | — | no |
| 2 | **Boundary enforcement** | `tests/security/test_module_boundary.py`; `tests/security/test_forbidden_imports.py`; `tests/security/test_no_forbidden_module_strings.py`; `tests/security/test_no_hardcoded_creds.py`; `tests/security/test_print_discipline.py` (v0.2.0 per Req-Fix 11) | AC12.1-12.9, AC13.1-13.8, AC14.1-14.8 | Task 1 | no |
| 3 | **Pipeline models + constants** | `src/m8_pipeline_engine/models.py` (HitlApproval, HitlGatePayload, PipelineResult, StageAuditPayload, PipelineTerminalAuditPayload, LlmGeneration); `src/m8_pipeline_engine/errors.py` (VALID_REASON_CODES frozenset, exception classes); `src/m8_pipeline_engine/__init__.py` (STAGE_NAMES, HITL_GATES, PIPELINE_NAMES, SCHEMA_VERSION, 24-entry __all__ per Req-Fix 4); `tests/unit/test_models.py`; `tests/unit/test_constants.py::test_stage_name_immutability` | AC1.8, AC2.2, AC2.7, AC2.8, AC2.9, AC4.1, AC11.1-11.6, AC15.1-15.6 | Task 1 | no |
| 4 | **State schema + invariants** | `src/m8_pipeline_engine/state.py` (PipelineState TypedDict — v0.2.0 drops `compliance_check`, adds `slow_alert_emitted`); `tests/unit/test_state_schema.py` (required-keys check, MNPI residency property, cost_basis walks `tax_lots[*].cost_basis_method` per Req-Fix 5) | AC1.2, AC10.4 (partial) | Task 3 | no |
| 5 | **LangGraph graph assembly (skeleton)** | `src/m8_pipeline_engine/graph.py::build_graph` (23 nodes registered, sequential edges, conditional edges at gates, `Send` API at stage 8 via `from langgraph.types import Send` per Req-Fix 8, reducer at stage 12); `tests/unit/test_graph_assembly.py` (node count, edge topology, Send import path) | AC2.1-2.6, AC5.1, AC5.4, AC5.8 | Tasks 3, 4 | no |
| 6 | **Checkpointer factory** | `src/m8_pipeline_engine/checkpointer.py` (PostgresSaver wrapper, DynamoDbSaver stub, InMemorySaver helper); `tests/unit/test_checkpointer.py` (factory dispatch, DSN resolution, schema segregation) | AC3.1-3.9 | Task 1 | no |
| 7 | **SonnetClient live call (Bedrock Converse)** | `src/m8_pipeline_engine/llm_client.py::SonnetClient` (full implementation with Converse API, retry/backoff, JSON-mode); `tests/unit/test_sonnet_client.py` (botocore Stubber — no live Bedrock) | AC6.1-6.12 | Task 1 | no |
| 8 | **HITL primitives + token algorithm + key rotation** | `src/m8_pipeline_engine/hitl.py` (build_gate_payload, verify_approval_token, reap_timed_out_threads, _verify_approver_role, _resolve_hitl_hmac_key); `tests/unit/test_hitl.py` (token derivation, TTL expiry, role mismatch, replay defense, **key rotation across pod boundaries** per AC4.12 Req-Fix 12, **idempotent `resume_from_gate`** per AC18.8) | AC4.1-4.12, AC18.8 | Task 3 | no |
| 9 | **Checkpoint resumption + fail-closed + state-field persistence + order regression** | `src/m8_pipeline_engine/graph.py::_checkpoint_hook`; `tests/unit/test_checkpoint_resumption.py` (InMemorySaver resume, FailingCheckpointer fail-closed, schema mismatch detection, **`test_compliance_escalation_survives_checkpoint`** per AC9.8/A24 Recommended Fix 2, **`test_hitl_interrupt_checkpoint_order`** per AC9.9 Recommended Fix 5) | AC3.5, AC3.10, AC9.1-9.9 | Tasks 5, 6 | no |
| 10 | **Per-stage audit emission via AuditClient (v0.2.0)** | `src/m8_pipeline_engine/audit_emit.py` (emit_stage_audit, compute_io_digest, PipelineTerminalAuditPayload helpers, exactly-once slow-alert gate per AC8.11); `src/m8_pipeline_engine/schemas/m8_stage_audit.schema.json`; `tests/unit/test_audit_emit.py` (schema round-trip, canary regex scan, failure retry path against `FailingFakeAuditClient` per Req-Fix 4) | AC8.1-8.11, AC18.1-18.8 | Task 3, Task 1 (AuditClient) | no |
| 11 | **Property tests — determinism + state immutability + CI budget** | `tests/property/strategies.py` (`@composite` for PipelineState + supporting types); `tests/property/test_determinism.py`; `tests/property/test_state_immutability.py`; `tests/property/test_cost_basis_preserved.py` (walks `tax_lots[*].cost_basis_method` per Req-Fix 5). Hypothesis pinned `max_examples=20` (CI, env `CI=1`) / `max_examples=50` (local) per Recommended Fix 4. | AC1.6, AC10.1-10.7 | Tasks 4, 5 | no |
| 12 | **Concurrency smoke test + tenant semaphore** | `src/m8_pipeline_engine/graph.py::_acquire_tenant_slot`; `tests/benchmarks/test_m8_concurrency.py` (10 threads × 5 thread_ids, tenant semaphore behavior) | AC1.5, AC16.3 | Task 5 | no |
| 13 | **Wall-clock ceiling + alert threshold + exactly-once alert** | `src/m8_pipeline_engine/graph.py::_wall_clock_check`; `tests/unit/test_wall_clock.py` (FakeSonnetClient with `delay_ms`, ceiling breach, alert emission exactly-once across multiple post-threshold stages per AC8.11) | AC16.1-16.6, AC8.11 | Task 5 | no |
| 14 | **Research/data gathering stages (1-6) — reason-code coverage matrix** | `src/m8_pipeline_engine/nodes/stage_{1..6}_*.py`; `src/m8_pipeline_engine/prompts/stage_{1,4,6}_*.jinja` + `.version` files; `tests/unit/test_stages_1_6.py` (per-stage happy-path + each reason_code path). **Reason-code coverage matrix (v0.2.0, Recommended Fix 3):** Task 14 exercises codes `m8_stage_failed` (stages 2, 3, 5 on `GatewayError("vendor_unavailable")` retry exhaustion), `m8_llm_5xx` (stages 1, 4, 6), `m8_llm_4xx` (stages 1, 4, 6), `m8_llm_timeout` (stages 1, 4, 6), `m8_llm_malformed_output` (stage 1 JSON parse failure), `m8_token_budget_exceeded` (stage 4 soft warning), `m8_mnpi_leaked_through_gateway` (stage 2 `GatewayError("mnpi_leakage_scan")`). | AC2.4-2.5 (stages 1-6) | Tasks 5, 7, 10 | no |
| 15 | **Exhaustive reason_code meta-test** | `tests/unit/test_reason_codes.py` — exercises every 20 of the VALID_REASON_CODES via FakeSonnetClient Exception injection + FakeGatewayClient Exception injection (covers every `VALID_GATEWAY_REASONS` member per AC7.9) + `FailingCheckpointer` + `FailingFakeAuditClient` + `AntiFabFailureFixture`; canary-utterance stdout scan (AC6.7, AC14.1) | AC6.7, AC11.3, AC7.9 | Tasks 1, 7, 8, 10 | no |
| 16 | **Analysis + synthesis stages (8-12) + map-reduce + zero-fan-out — reason-code coverage matrix** | `src/m8_pipeline_engine/nodes/stage_{8..12}_*.py`; `src/m8_pipeline_engine/prompts/stage_{8,9,10,12}_*.jinja` + `.version` files; `tests/unit/test_stages_8_12.py` (fan-out cap, reducer, per-instrument error tolerance, `m8_map_reduce_all_failed`, **`test_zero_fan_out_single_tool`** per AC5.8 Recommended Fix 1). **Reason-code coverage matrix (Recommended Fix 3):** exercises `m8_map_reduce_too_wide` (stage 8), `m8_map_reduce_all_failed` (stage 12), `m8_llm_5xx` + `m8_llm_timeout` + `m8_token_budget_exceeded` (stages 9, 10, 12), `m8_stage_failed` (stage 10 peer-comps `GatewayError`). | AC5.1-5.8, AC2.4-2.5 (stages 8-12) | Tasks 5, 7, 10 | no |
| 17 | **Recommendation + output stages (14-23) + compliance + anti-fabrication — reason-code coverage matrix** | `src/m8_pipeline_engine/nodes/stage_{14..23}_*.py`; `src/m8_pipeline_engine/prompts/stage_{14,15,16,17,19}_*.jinja` + `.version` files; `tests/unit/test_stages_14_23.py`; `tests/unit/test_anti_fabrication.py` (numeric-token provenance, escalation path). **Reason-code coverage matrix (Recommended Fix 3):** exercises `m8_compliance_denied` (stage 20 `GatewayError("authority_denied")` per AC7.9 v0.2.0), compliance escalation via `GatewayError("authority_escalated")` AND via success-path `decision="ESCALATE"`, `m8_anti_fabrication_failed` (stage 21), `m8_invalid_state` (stages 14-23 on `holding.tax_lots[*].cost_basis_method is None` per Req-Fix 5). | AC2.4-2.5 (stages 14-23), AC7.7-7.9 | Tasks 5, 7, 10 | no |
| 18 | **Bedrock first-live-call + model-ID verification** | `tests/integration/test_bedrock_first_call.py` (live Bedrock — gated behind `M8_LIVE=1`); DECISION-LOG update on mismatch | §Known Blockers row 2, row 3 | Task 7 | gated |
| 19 | **Config shape integration + .env.example shipping + M10 audit contract** | `tests/integration/test_m8_m5_config_shape.py` (SHARED-WITH-M5); `tests/integration/test_env_example_shipped.py`; `tests/integration/test_m8_m10_audit_contract.py` (v0.2.0 — SHARED-WITH-M10 xfail until M10 v0.3.0 ships `/audit`) | AC14.6, §Known Blockers rows 1 + 18 | Task 1 | xfail (until M5 v0.4.0 + M10 v0.3.0) |
| 20 | **M12 supervisor-call integration + cross-module version match + M6 shape match** | `tests/integration/test_m12_m8_supervisor_call.py` — round-trip matches §Integration Point with M12 examples using FakeGatewayClient + FakeAuditClient + FakeSonnetClient + InMemorySaver; `tests/integration/test_cross_module_pipeline_names.py` — asserts `PIPELINE_NAMES` subset of M9's `{t.name for t in m9_intent_router.taxonomy.TAXONOMY_DISPATCH.values() if t.kind == "pipeline"}`; **`tests/integration/test_m6_shape_match.py`** — asserts M8's `GatewayRequest` / `GatewayResponse` dataclasses have identical `dataclasses.fields()` to M6's exported types (Req-Fix 1 verification; xfail if M6 export-surface changes) | AC17.1-17.6, AC18.1-18.6, AC7.2 | Tasks 14, 16, 17 | cross-module-xfail (until M9 v0.2.0 + M6 v0.2.0 stable) |

### Task Dependencies (DAG)

```
T1 ──┬──► T2
     ├──► T3 ──► T4 ──► T5 ──► T9, T11, T12, T13
     ├──► T6 ──┐
     ├──► T7 ──┼──► T14 (stages 1-6)
     └──► T8   │    └──► T16 (stages 8-12)
               │    └──► T17 (stages 14-23)
               ▼          │
               T10       T15 (exhaustive reason codes)
                          │
                          ▼
                         T20 (supervisor integration + shape match)
T7 ──► T18 (gated live)
T1 ──► T19 (xfail pending M5 v0.4.0 + M10 v0.3.0)
```

Critical path: T1 → T3 → T4 → T5 → T14 → T16 → T17 → T20. Target: Phase 2 Weeks 30-36 per ARCH-09 build order.

---

## Hypothesis Strategy Approach

Hypothesis property-test strategies compose via `@composite` to produce `(PipelineState, FakeSonnetClient, FakeGatewayClient, FakeAuditClient)` tuples that exercise stage functions under realistic-shaped inputs. v0.2.0 uses firm-level `Archetype.tier4_independent_ria` throughout, populates a minimal valid `RoutingDecision`, and seeds fakes on `input_sha256` digests.

**CI budget (Recommended Fix 4):** `max_examples=20` in CI (env `CI=1` detection), `max_examples=50` in local dev. Deadline 5000 ms. Documented in DECISION-LOG D14.

### `pipeline_state_variants()` Composite Strategy

```python
# tests/property/strategies.py
import os
from hypothesis import strategies as st
from hypothesis.strategies import composite

from m9_intent_router.models import (
    RoutingDecision, SelectedTarget, IntentCategory,
)
from m3_schema_registry import Holding, TaxLot, CostBasisMethod
from m8_pipeline_engine.state import PipelineState

CI_MAX = 20   # Recommended Fix 4 — CI budget
LOCAL_MAX = 50  # Recommended Fix 4 — local budget
MAX_EXAMPLES = CI_MAX if os.environ.get("CI") == "1" else LOCAL_MAX


@composite
def tax_lot_with_method(draw) -> TaxLot:
    """cost_basis_method NEVER null per M3 validator + v0.2.0 Req-Fix 5."""
    return TaxLot(
        lot_id=draw(st.uuids()),
        holding_ref="HOLD-" + draw(st.from_regex(r"[a-f0-9]{8}", fullmatch=True)),
        quantity=draw(st.floats(min_value=1.0, max_value=10000.0)),
        cost_basis_method=draw(st.sampled_from(list(CostBasisMethod))),
        cost_basis_amount=draw(st.floats(min_value=100.0, max_value=1_000_000.0)),
        source_custodian="schwab",
    )


@composite
def holding_with_tax_lots(draw) -> Holding:
    """v0.2.0 — Holding has tax_lots: list[TaxLot] with cost_basis_method per lot.
    Holding itself has NO cost_basis_method field (Req-Fix 5).
    """
    lots = draw(st.lists(tax_lot_with_method(), min_size=1, max_size=3))
    return Holding(
        canonical_id=draw(st.uuids()),
        account_ref="ACCT-" + draw(st.from_regex(r"[a-f0-9]{8}", fullmatch=True)),
        quantity=sum(lot.quantity for lot in lots),
        market_value=draw(st.floats(min_value=1000.0, max_value=10_000_000.0)),
        as_of_date=draw(st.dates()),
        source_system="schwab",
        source_id=draw(st.from_regex(r"SCH-[0-9]{10}", fullmatch=True)),
        tax_lots=lots,
    )
```

### Usage in Task 11 Determinism Test

```python
from hypothesis import given, settings
from m8_pipeline_engine import research_pipeline
from m8_pipeline_engine.gateway_client import FakeGatewayClient
from m8_pipeline_engine.audit_client import FakeAuditClient
from m8_pipeline_engine.llm_client import FakeSonnetClient
from langgraph.checkpoint.memory import InMemorySaver
from tests.property.strategies import pipeline_state_variants, MAX_EXAMPLES

@given(state=pipeline_state_variants())
@settings(max_examples=MAX_EXAMPLES, deadline=5000)
def test_pipeline_determinism(state):
    gateway = _seeded_fake_gateway_factory(state)
    audit = FakeAuditClient()
    llm = _seeded_fake_sonnet_factory(state)
    ckpt1 = InMemorySaver()
    ckpt2 = InMemorySaver()
    r1 = research_pipeline.run_with_deps(state, state["thread_id"], gateway, audit, llm, ckpt1)
    r2 = research_pipeline.run_with_deps(state, state["thread_id"] + "-dup", gateway, audit, llm, ckpt2)
    assert r1.model_dump(exclude={"wall_clock_seconds","thread_id","pipeline_run_id"}) == \
           r2.model_dump(exclude={"wall_clock_seconds","thread_id","pipeline_run_id"})
```

**CI budget (Recommended Fix 4)**: property suites run at 20 × 5s ≈ 100s per suite × 3 suites ≈ 300s in CI; 50 × 5s ≈ 750s worst-case locally. Documented in DECISION-LOG D14.

### Determinism Invariant Matrix

| Invariant | Strategy Check | Property Test |
|-----------|----------------|---------------|
| Two identical calls → identical decisions (excl. `wall_clock_seconds`) | Same `(state, fakes)` | `test_determinism.py::test_pipeline_determinism` |
| `run()` does not mutate `initial_state` (AC1.6) | `copy.deepcopy` before; `==` after | `test_state_immutability.py::test_input_not_mutated` |
| Reducer ordering deterministic (AC10.5) | seed `FakeSonnetClient` with multi-instrument results | `test_determinism.py::test_reducer_ordering` |
| Cost basis never null (AC7.5, Rule 32, Req-Fix 5) | strategy uses `holding_with_tax_lots` → each `tax_lots[*].cost_basis_method` drawn from `CostBasisMethod` | `test_cost_basis_preserved.py::test_all_tax_lots_have_method` |
| `compliance_escalation` survives checkpoint (A24, Rec-Fix 2) | `InMemorySaver` round-trip | `test_checkpoint_resumption.py::test_compliance_escalation_survives_checkpoint` |

---

## Review Fix Traceability

LLMJ-v1 review (2026-05-18) raised 12 Required Fixes + 14 Recommended Fixes. v0.2.0 addresses all 12 Required + Recommended 1-5 (plus selected minor). Every Required Fix has a row below with its resolution trace.

| # | Required Fix (LLMJ-v1) | Severity | Addressed In Spec Section / AC / Task | Status |
|---|------------------------|----------|---------------------------------------|--------|
| 1 | **M6 `GatewayRequest`/`GatewayResponse` Pydantic-vs-dataclass shape drift.** v0.1.0 modeled both as Pydantic v2; real M6 exports both as `@dataclass(frozen=True)` (`src/m6_mcp_gateway/gateway.py` lines 118 + 221). | CRITICAL — Accuracy | AC7.2 rewritten (dataclass, field list verbatim from M6); §M6 Gateway Call Pattern rewritten; `dataclasses.fields()` equality test in Task 20 `test_m6_shape_match.py`; Appendix B.4 new skeleton; Changelog v0.2.0 bullet (1); Appendix C D12 cross-referenced. | **CLOSED** |
| 2 | **`GatewayRequest.vendor_adapter` required non-None.** v0.1.0's `_invoke_tool` constructed `vendor_adapter=None`, which raises `ValueError` at M6's `__post_init__` (line 196-204). Every M8→M6 call in v0.1.0 would fail at request construction. | CRITICAL — Accuracy | AC7.3 adds `VendorAdapterResolver` Protocol + `LocalVendorAdapterResolver` production impl; §M6 Gateway Call Pattern `_invoke_tool` signature accepts `resolver` and calls `resolver.resolve(tool_name)` before constructing the request. SHARED-WITH-M6 (Known Blocker row 6) documents M6 v0.3.0 "server-side adapter resolution" as the preferred long-term path. Task 1 deliverable list updated. | **CLOSED — workaround; SHARED-WITH-M6 for long-term fix** |
| 3 | **M6 failure paths RAISE `GatewayError(reason)`, not return `GatewayResponse` with `decision=='DENY'` or `reason=='vendor_unavailable'`.** v0.1.0's response-handling branches were unreachable. | CRITICAL — Accuracy | AC7.7-7.9 rewritten to use `try / except GatewayError as exc; if exc.reason == ...` pattern branching across all 11 members of M6's `VALID_GATEWAY_REASONS`. §M6 Gateway Call Pattern Response Handling rewritten with `_call_with_branching` helper. Error Code Map rows 12, 13 updated. Task 15 `test_gateway_error_branches` exercises every `VALID_GATEWAY_REASONS` value. | **CLOSED** |
| 4 | **M6 has no `emit_audit()` method.** v0.1.0 invented `GatewayClient.emit_audit(...)`; M6's `TrustAwareGateway` public surface is `call(...)` + `health()` only. | CRITICAL — Accuracy | New `AuditClient` Protocol in `src/m8_pipeline_engine/audit_client.py` (AC8.10) with `M10AuditClient` (mTLS to M10 FastAPI `POST /audit`) + `FakeAuditClient` + `AuditEmitError`. AC7.1 reduced to single-method `call()` Protocol. AC18.1-18.8 rewritten for direct M10 integration. `__all__` grows to 24 names (AC15.1). SHARED-WITH-M10 — Known Blocker row 18 documents M10 v0.3.0 `/audit` endpoint requirement; Task 19 xfail gate. Appendix B.5 new skeleton. | **CLOSED — workaround; SHARED-WITH-M10 for endpoint** |
| 5 | **`Holding.cost_basis_method` does not exist.** Field lives on `TaxLot`. v0.1.0's State Field Invariant + A12 + Error Code Map row 20 + Task 11 all referenced a non-existent attribute. Verified against `src/m3_schema_registry/types.py` line 719-721 docstring + line 698 `TaxLot.cost_basis_method`. | MAJOR — Accuracy | State Field Invariant "Cost basis preservation" rewritten to walk `holding.tax_lots[*].cost_basis_method`. A12 invariant rewritten. Error Code Map row 20 trigger rewritten. Task 11 `test_cost_basis_preserved` rewritten. AC12.2 allow-list adds `TaxLot`, `CostBasisMethod`. Hypothesis strategy composes `holding_with_tax_lots` + `tax_lot_with_method`. | **CLOSED** |
| 6 | **006 stage-name drift vs "provenance continuity" claim.** v0.1.0 banner + DECISION-LOG D2 claimed verbatim preservation; stage 12 (006 `_stage_12_sentiment_synthesis`) and stage 21 (006 `_stage_21_final_approval_gate`) were silently renamed. | MAJOR — Accuracy | Keep the 007 names (better describe v0.2.0 behavior — stage 12 IS a reduce across all sources, stage 21 IS anti-fab + HITL hybrid). Drop "verbatim preservation" framing. Phase 2 Scope bullet 1 rewritten. FSI Pipeline Stage Catalog gains "006 Name" column with `[RENAMED vs 006]` markers. §Stage Name Immutability Contract discusses v0.1.0 → v0.2.0 no-rename policy. DECISION-LOG D13 added with full rationale. | **CLOSED** |
| 7 | **10-vs-20 reason code internal inconsistency.** Three locations said "10 codes", three said "20", one admitted the delta. | MAJOR — Doc Consistency | Global sweep: Changelog v0.1.0 bullet 9 now says "**20 codes in v0.1.0**"; Phase 2 Scope bullet 9 says "**20 `reason_code` values**"; R11 header says "Closed Frozen Set (**20 Codes**)"; DECISION-LOG D7 rewritten to "20 reason codes in v0.1.0 (vs. original target 10) — reconciled in v0.2.0". AC11.1, Error Code Map, Task 15 unchanged (already 20). | **CLOSED** |
| 8 | **LangGraph `Send` import deprecated + version pin stale.** `langgraph.constants.Send` deprecated since V1.0; spec pinned `langgraph >= 0.2.0, < 0.3` (two majors behind V1.0). | MAJOR — Accuracy | Appendix B.2 skeleton updated: `from langgraph.types import Send`. AC12.7 rewritten: `langgraph >= 0.4, < 2.0`. AC13.2 third-party allow-list adds `langgraph.types`. Banner `Language` row updated. Task 5 `test_graph_assembly.py` asserts the import path. | **CLOSED** |
| 9 | **`ComplianceCheck` imported but not populated.** v0.1.0 AC12.2 allow-listed `ComplianceCheck` and `PipelineState.compliance_check: Optional[ComplianceCheck]`, but no stage populated it. | MINOR — Accuracy | Drop `ComplianceCheck` from AC12.2 allow-list. Drop `compliance_check` field from `PipelineState` (§State Schema comment marks the drop). Stage 20 emits `compliance_decision` + `compliance_rule_applied` + `compliance_wsp_section` + `compliance_escalation` which suffice. | **CLOSED — simpler path chosen** |
| 10 | **ARCH-04 v2 `langchain-aws` deviation buried in DECISION-LOG.** v0.1.0 D12 silently documented the deviation; should be a surfaced Known Blocker with an ARCH-04 v2 update request. | MINOR — Design Alignment | Known Blockers row 17 added (ARCH-04 v2 `langchain-aws` deviation — Req-Fix 10) with "PENDING-ARCH-04-UPDATE" status and rationale (LangChain umbrella would violate Steering Rule 15 provider abstraction). AC13.8 references the row. Changelog v0.2.0 bullet (9) notes the elevation. | **CLOSED — elevated visibility; architecture update still pending** |
| 11 | **AC13.5 `print` discipline too lax.** Allowed `print(` in two files without asserting content. | MINOR — Security | AC13.5 tightened: "digest-only audit line; raw payload never printed" + source-level `test_print_discipline` AST scan forbids variables named `prompt`, `payload`, `result`, `tool_result`, `raw`, `text` as args to `print(...)`. Task 2 adds `test_print_discipline.py` deliverable. | **CLOSED** |
| 12 | **HITL HMAC key rotation contract missing.** v0.1.0 pinned the key fetch at startup but said nothing about rotation / pod-restart re-fetch. | MINOR — Security | New AC4.12 documents pod-restart-triggered re-fetch, quarterly rotation cadence (90 days, aligned with 24hr mTLS × 90-day aggregate), in-flight pipeline behavior (post-rotation tokens sign under new key; cross-pod-boundary verification failures emit `m8_hitl_token_expired`). Task 8 `test_hitl_key_rotation` asserts pod A/B key divergence. Gate Invariants "Key-rotation invariant (v0.2.0)" added. DECISION-LOG D15 added. | **CLOSED** |

**Recommended Fixes integrated in v0.2.0:**

- **R1 (Completeness)**: AC5.8 — stage 8 zero-discovered-instruments path; stage 12 `m8.single_tool_bypass` audit event; Task 16 `test_zero_fan_out_single_tool`.
- **R2 (Completeness)**: A24 invariant + AC3.10 + AC9.8 — `state.compliance_escalation` survives checkpoint round-trip; Task 9 `test_compliance_escalation_survives_checkpoint`.
- **R3 (Completeness)**: Per-task reason-code coverage matrix on Tasks 14, 16, 17 — every reason code assigned to the stage group most likely to emit it, with explicit test coverage.
- **R4 (Testability)**: Hypothesis `max_examples=20` CI / `max_examples=50` local — env-gated on `CI=1`; documented in DECISION-LOG D14.
- **R5 (Testability)**: AC9.9 — `interrupt()` → checkpointer write-order regression guard with `CheckpointerWithAuditSpy`.
- **R11 (Gaps)**: AC8.11 — `m8.pipeline_slow_alert` exactly-once emission gated by `state.slow_alert_emitted`.
- **R12 (Gaps)**: AC18.8 — `resume_from_gate` idempotency on same `(thread_id, approval_token)`.

Not integrated in v0.2.0 (deferred to v0.3.0 review cycle): R6 (M12 cross-module count match — M12 spec not drafted), R7 (M4 client_id MNPI classification — SHARED-WITH-M4), R8 (tenant-scoped checkpointer key — Phase 3), R9 (audit-outage circuit breaker readiness probe), R10 (dropped_instruments propagation into ResearchBrief.sources), R13 (ARCH-05 v2 non-interaction statement), R14 (Steering Rules 9/10/17/19 in trace table — N/A in M8 scope).

---

## Steering-Rule Traceability

Maps every Steering Rule that M8 must honor to the concrete spec section / AC / task that addresses it. Auditable trace from `.kiro/steering/007-fsi-interoperability.md` → this spec.

| Steering Rule | Rule Text (abbreviated) | Addressed In | Test |
|---------------|-------------------------|--------------|------|
| Rule 4 | Every MCP call through M6 | R7 AC7.1-7.11; §M6 Gateway Call Pattern; §Architecture Clarification bullet 4 | Task 2 AST scan; Task 14/16/17 per-stage tests; Task 20 M6 shape match |
| Rule 5 | M2/M4 OPA-only; no LLM compliance | R4 AC4.9; §Integration Point with M2/M4; §FSI Pipeline Stage Catalog Stage 20 row | Task 17 stage 20 test |
| Rule 6 | M10 3-tier WORM required | R8 AC8.1-8.11; §Integration Point with M10 (via AuditClient) | Task 10, Task 19 (xfail M10 v0.3.0) |
| Rule 7 | MNPI never to LLM unfiltered | R7 AC7.5, AC7.6; §State Field Invariants "MNPI residency" | Task 11 property test; Task 15 canary |
| Rule 8 | Fail-closed on compliance check failure | R3 AC3.5; R4 AC4.3-4.12; R7 AC7.7-7.9; R11 | Task 8, Task 9, Task 15 |
| Rule 11 | Async dispatch; max 3 concurrent per tenant | R16 AC16.3; §Integration Point with M12 §Async Dispatch | Task 12 |
| Rule 13 | Sonnet for research, Haiku for routing | R6 (all LLM calls Sonnet); §Token Budget Table (model column) | Task 7 |
| Rule 14 | NO LLM for compliance | R4 AC4.9; §FSI Pipeline Stage Catalog Stage 20 | Task 17 stage 20 |
| Rule 15 | LLM provider swappable | R6 AC6.1, AC6.11, AC6.12 | Task 1, Task 7 |
| Rule 20 | Zero credentials in code | R14 AC14.1-14.8 | Task 2 credential scan |
| Rule 32 | Pydantic validation; MNPI filtered; audit logged; cost_basis never null (v0.2.0 walks `TaxLot` per Req-Fix 5) | R4 (Pydantic models), R7-R8-R14, §State Field Invariants "Cost basis preservation" | Task 2, Task 10, Task 11 `test_cost_basis_preserved`, Task 15 |

---

## Appendix A — Pipeline Invariants

Authoritative invariant list. Every invariant is enforced by at least one test. Adding or removing an invariant is a MINOR or MAJOR spec bump respectively. v0.2.0 adds A24 per Recommended Fix 2.

| # | Invariant | Enforcement Mechanism | Test |
|---|-----------|----------------------|------|
| A1 | `len(STAGE_NAMES) == 23` | Frozen module-level tuple | Task 3 `test_stage_name_immutability::test_stage_count` |
| A2 | `HITL_GATES == {7, 13, 21}` | Frozen module-level frozenset | Task 3 `test_constants::test_hitl_gates` |
| A3 | Every stage number in 1..23 represented exactly once | Meta-test over `STAGE_NAMES` | Task 3 `test_stage_name_immutability::test_bijective_numbering` |
| A4 | `PIPELINE_NAMES` ⊆ `m9_intent_router.taxonomy` pipeline-kind names | Cross-module version match | Task 20 `test_cross_module_pipeline_names` (xfail until M9 v0.2.0 stable) |
| A5 | Positive import allow-list: `m3_schema_registry`, `m5_config_loader`, `m9_intent_router.models` only | AST scan | Task 2 `test_module_boundary` |
| A6 | No `langchain*` / `anthropic` / `requests` / `logging` imports | AST scan | Task 2 `test_forbidden_imports` |
| A7 | `boto3` imports confined to `llm_client.py`, `hitl.py`, `checkpointer.py` | AST scan | Task 2 `test_forbidden_imports::test_boto3_scope` |
| A8 | Every LLM-bearing stage has a prompt file + `.version` file | Filesystem check | Task 10 `test_prompt_template_versioning` |
| A9 | Every stage emits exactly one audit row on entry + exit via `AuditClient` | Audit hook decorator | Task 10 `test_audit_per_stage` |
| A10 | `PipelineState` unchanged after `run()` returns | Deep-equality check | Task 11 `test_state_immutability::test_input_not_mutated` |
| A11 | No MNPI-shaped fields (SSN, 9-digit routing) in `PipelineState` after any stage | Regex scan over serialized state | Task 11 `test_mnpi_residency_property` |
| A12 | **Every `Holding` in state has `holding.tax_lots[*].cost_basis_method is not None` (v0.2.0 rewritten per Required Fix 5 — `Holding` has NO `cost_basis_method` field; `TaxLot.cost_basis_method` does)** | Pydantic validator on `TaxLot` + state invariant walk | Task 11 `test_cost_basis_preserved::test_all_tax_lots_have_method` |
| A13 | `VALID_REASON_CODES` is closed set of 20 codes; every emitted code is a member | Pydantic `@field_validator` | Task 15 `test_reason_codes::test_all_exercised` |
| A14 | HITL token verification is constant-time (`hmac.compare_digest`) | Source-level audit | Task 8 `test_hitl::test_constant_time_verification` |
| A15 | HITL wait time EXCLUDED from wall-clock budget | Timer integration | Task 13 `test_wall_clock::test_hitl_excluded` |
| A16 | Reducer at stage 12 iterates `per_instrument_results` in `sorted()` order | Source-level + property test | Task 11 `test_determinism::test_reducer_ordering` |
| A17 | Fan-out cap enforced: `len(sends) <= max_concurrent_instruments` | Stage 8 check | Task 16 `test_stages_8_12::test_fan_out_cap` |
| A18 | Checkpoint write failure terminates pipeline (no silent retry) | `_checkpoint_hook` fail-closed | Task 9 `test_checkpoint_resumption::test_fail_closed` |
| A19 | Stage 20 NEVER calls Sonnet — only M6 compliance.screen | Source-level audit + stage test | Task 17 `test_stages_14_23::test_stage_20_no_llm` |
| A20 | `print(` appears only in `audit_emit.py` fallback (AC13.5 v0.2.0 tightened) — no raw payload args | AST scan | Task 2 `test_print_discipline` |
| A21 | Zero credentials in source or config | Regex scan | Task 2 `test_no_hardcoded_creds` |
| A22 | Anti-fabrication scoring on passing brief; else HITL Gate 3 flags | Stage 21 logic | Task 17 `test_anti_fabrication::test_scoring` |
| A23 | Every HITL gate has timeout + rejection + role-mismatch paths | §HITL Gate Specification | Task 8 `test_hitl::test_all_terminal_paths` |
| **A24** | **`state.compliance_escalation: bool` survives checkpoint round-trip (v0.2.0, Recommended Fix 2)** | `InMemorySaver` round-trip | Task 9 `test_compliance_escalation_survives_checkpoint` |

---

## Appendix B — Skeleton Files

Layout of `src/m8_pipeline_engine/`. Every file has a stub that satisfies its module-level `__all__` and AST-boundary invariants. v0.2.0 adds `audit_client.py` per Required Fix 4.

```
src/m8_pipeline_engine/
├── __init__.py                                     # 85 lines — public API surface (24 names v0.2.0)
├── .env.example                                    # 14 lines — non-credential env keys (v0.2.0 adds M8_AUDIT_*)
├── DECISION-LOG.md                                 # Appendix C seed (v0.2.0 adds D13 + D14)
├── state.py                                        # 115 lines — PipelineState TypedDict (compliance_check dropped)
├── models.py                                       # 130 lines — pipeline models
├── errors.py                                       # 50 lines — VALID_REASON_CODES + exception classes
├── graph.py                                        # 200 lines — StateGraph assembly (langgraph.types.Send)
├── hitl.py                                         # 150 lines — gate primitives + reaper + key rotation
├── checkpointer.py                                 # 80 lines  — factory + stubs
├── llm_client.py                                   # 150 lines — LLMClient Protocol + providers
├── gateway_client.py                               # 160 lines — GatewayClient Protocol + @dataclass shapes + VendorAdapterResolver
├── audit_client.py                                 # 90 lines — AuditClient Protocol + M10AuditClient + FakeAuditClient (NEW v0.2.0)
├── audit_emit.py                                   # 100 lines — per-stage audit emission via AuditClient
├── nodes/
│   ├── __init__.py                                 # 20 lines
│   ├── stage_1_intake.py                           # 50 lines
│   ├── stage_2_crm_context.py                      # 40 lines
│   ├── stage_3_market_data.py                      # 40 lines
│   ├── stage_4_news_sentiment.py                   # 60 lines
│   ├── stage_5_sec_filings.py                      # 60 lines
│   ├── stage_6_transcript_analysis.py              # 50 lines
│   ├── stage_7_data_quality_gate.py                # 30 lines (HITL)
│   ├── stage_8_financial_modeling.py               # 75 lines (fan-out + zero-fan-out AC5.8)
│   ├── stage_9_dcf_valuation.py                    # 50 lines
│   ├── stage_10_comps_analysis.py                  # 50 lines
│   ├── stage_11_monte_carlo.py                     # 60 lines (no LLM)
│   ├── stage_12_cross_source_synthesis.py          # 75 lines (reducer + single-tool bypass)
│   ├── stage_13_analysis_review_gate.py            # 30 lines (HITL)
│   ├── stage_14_thesis_generation.py               # 50 lines
│   ├── stage_15_catalyst_identification.py         # 40 lines
│   ├── stage_16_risk_assessment.py                 # 40 lines
│   ├── stage_17_rating_determination.py            # 40 lines
│   ├── stage_18_target_price_calc.py               # 50 lines
│   ├── stage_19_brief_assembly.py                  # 60 lines
│   ├── stage_20_compliance_check.py                # 55 lines (OPA via M6; try/except GatewayError)
│   ├── stage_21_anti_fabrication_check.py          # 70 lines (HITL + scan)
│   ├── stage_22_crm_writeback.py                   # 50 lines
│   └── stage_23_delivery_notify.py                 # 30 lines
├── prompts/
│   ├── stage_1_intake.jinja + .version
│   ├── stage_4_news_sentiment.jinja + .version
│   ├── stage_6_transcript_analysis.jinja + .version
│   ├── stage_8_financial_modeling.jinja + .version
│   ├── stage_9_dcf_valuation.jinja + .version
│   ├── stage_10_comps_analysis.jinja + .version
│   ├── stage_12_cross_source_synthesis.jinja + .version
│   ├── stage_14_thesis_generation.jinja + .version
│   ├── stage_15_catalyst_identification.jinja + .version
│   ├── stage_16_risk_assessment.jinja + .version
│   ├── stage_17_rating_determination.jinja + .version
│   └── stage_19_brief_assembly.jinja + .version
└── schemas/
    ├── m8_stage_audit.schema.json                  # AC8.9
    └── m8_pipeline_terminal_audit.schema.json      # AC8.8
```

Test layout:

```
tests/
├── unit/ (17 files — adds test_audit_client.py per v0.2.0)
├── property/ (strategies.py + 3 property tests — adds test_cost_basis_preserved.py per Req-Fix 5)
├── security/ (5 AST scans — adds test_print_discipline.py per Req-Fix 11)
├── benchmarks/ (concurrency)
└── integration/
    ├── test_m8_m5_config_shape.py                  # xfail until M5 v0.4.0
    ├── test_env_example_shipped.py
    ├── test_bedrock_first_call.py                  # gated M8_LIVE=1
    ├── test_m12_m8_supervisor_call.py
    ├── test_cross_module_pipeline_names.py         # xfail until M9 v0.2.0 stable
    ├── test_m8_m10_audit_contract.py               # NEW v0.2.0 — xfail until M10 v0.3.0
    └── test_m6_shape_match.py                      # NEW v0.2.0 — dataclasses.fields() equality (Req-Fix 1)
```

**Line count roll-up**: ~1,460 production + ~1,200 test lines ≈ **2,660 lines total**. Matches ARCH-03 `~1,400` ADAPT budget for production code (within +5% for v0.2.0 AuditClient addition).

### B.1 — `src/m8_pipeline_engine/__init__.py` Skeleton (v0.2.0)

```python
"""M8 Pipeline Engine — LangGraph 23-stage research pipeline with 3 HITL gates."""

from typing import Literal

from m5_config_loader import PipelineConfig       # re-export (SHARED-WITH-M5)
from m8_pipeline_engine.audit_client import (
    AuditClient, AuditEmitError, FakeAuditClient, M10AuditClient,
)
from m8_pipeline_engine.errors import VALID_REASON_CODES
from m8_pipeline_engine.gateway_client import (
    FakeGatewayClient, GatewayClient, GatewayRequest, GatewayResponse,
    M6GatewayClient,
)
from m8_pipeline_engine.graph import research_pipeline, resume_from_gate, run
from m8_pipeline_engine.hitl import HitlApproval, HitlGatePayload
from m8_pipeline_engine.llm_client import (
    FakeSonnetClient, LLMClient, SonnetClient,
)
from m8_pipeline_engine.models import PipelineResult
from m8_pipeline_engine.state import PipelineState

SCHEMA_VERSION: Literal["1.0.0"] = "1.0.0"

STAGE_NAMES: tuple[str, ...] = (
    "stage_1_intake", "stage_2_crm_context", "stage_3_market_data",
    "stage_4_news_sentiment", "stage_5_sec_filings", "stage_6_transcript_analysis",
    "stage_7_data_quality_gate",
    "stage_8_financial_modeling", "stage_9_dcf_valuation",
    "stage_10_comps_analysis", "stage_11_monte_carlo",
    "stage_12_cross_source_synthesis",     # renamed from 006 _stage_12_sentiment_synthesis (D13)
    "stage_13_analysis_review_gate",
    "stage_14_thesis_generation", "stage_15_catalyst_identification",
    "stage_16_risk_assessment", "stage_17_rating_determination",
    "stage_18_target_price_calc", "stage_19_brief_assembly",
    "stage_20_compliance_check",
    "stage_21_anti_fabrication_check",     # renamed from 006 _stage_21_final_approval_gate (D13)
    "stage_22_crm_writeback", "stage_23_delivery_notify",
)
assert len(STAGE_NAMES) == 23, "STAGE_NAMES must have exactly 23 entries (R2)"

HITL_GATES: frozenset[int] = frozenset({7, 13, 21})

PIPELINE_NAMES: frozenset[str] = frozenset({
    "m8.research_pipeline_1",
    "m8.research_pipeline_2",
    "m8.research_pipeline_3",
    "m8.research_single_tool",
})

__all__ = [
    "research_pipeline", "run", "resume_from_gate",
    "PipelineState", "PipelineResult", "PipelineConfig",
    "STAGE_NAMES", "HITL_GATES", "PIPELINE_NAMES",
    "VALID_REASON_CODES", "SCHEMA_VERSION",
    "LLMClient", "SonnetClient", "FakeSonnetClient",
    "GatewayClient", "M6GatewayClient", "FakeGatewayClient",
    "GatewayRequest", "GatewayResponse",
    "AuditClient", "M10AuditClient", "FakeAuditClient",    # NEW v0.2.0
    "AuditEmitError",                                       # NEW v0.2.0
    "HitlApproval", "HitlGatePayload",
]
assert len(__all__) == 24, "__all__ must have exactly 24 names (AC15.1 v0.2.0)"
```

### B.2 — `src/m8_pipeline_engine/graph.py` Skeleton (v0.2.0 — Send import path fixed)

```python
"""LangGraph StateGraph assembly. Compiled at module import time."""
from __future__ import annotations

import threading
import uuid
from collections import defaultdict

from langgraph.graph import END, START, StateGraph
from langgraph.types import Send          # v0.2.0 — was `from langgraph.constants import Send` (deprecated since V1.0)

from m8_pipeline_engine.state import PipelineState
from m8_pipeline_engine.gateway_client import GatewayClient, VendorAdapterResolver
from m8_pipeline_engine.audit_client import AuditClient             # NEW v0.2.0
from m8_pipeline_engine.llm_client import LLMClient
from m8_pipeline_engine.checkpointer import build_checkpointer
from m8_pipeline_engine.nodes import (
    stage_1_intake, stage_2_crm_context, stage_3_market_data,
    stage_4_news_sentiment, stage_5_sec_filings, stage_6_transcript_analysis,
    stage_7_data_quality_gate, stage_8_financial_modeling,
    stage_9_dcf_valuation, stage_10_comps_analysis, stage_11_monte_carlo,
    stage_12_cross_source_synthesis, stage_13_analysis_review_gate,
    stage_14_thesis_generation, stage_15_catalyst_identification,
    stage_16_risk_assessment, stage_17_rating_determination,
    stage_18_target_price_calc, stage_19_brief_assembly,
    stage_20_compliance_check, stage_21_anti_fabrication_check,
    stage_22_crm_writeback, stage_23_delivery_notify,
)

_TENANT_SEMAPHORES: dict[str, threading.Semaphore] = defaultdict(
    lambda: threading.Semaphore(3)
)


def build_graph(
    gateway: GatewayClient,
    resolver: VendorAdapterResolver,       # NEW v0.2.0 — Req-Fix 2
    audit: AuditClient,                     # NEW v0.2.0 — Req-Fix 4
    llm: LLMClient,
) -> StateGraph:
    g: StateGraph[PipelineState] = StateGraph(PipelineState)
    # ... 23 add_node calls
    # ... sequential edges for non-HITL, non-map-reduce stages
    # ... conditional edges at gates 7, 13, 21
    # ... Send fan-out at stage 8 (zero-fan-out per AC5.8); reducer at stage 12
    g.add_edge(START, "stage_1_intake")
    g.add_edge("stage_23_delivery_notify", END)
    return g


def _fan_out_instruments(state: PipelineState) -> list[Send]:
    """AC5.1 + AC5.8 — zero-instrument case returns [] (no Send)."""
    cap = state.get("config_max_concurrent_instruments", 10)
    instruments = state.get("discovered_instruments", [])[:cap]
    return [
        Send("stage_9_dcf_valuation", {"instrument_id": inst, **state})
        for inst in instruments
    ]


def run(
    initial_state: PipelineState,
    thread_id: str,
    *,
    _run_id_factory=lambda: f"run-{uuid.uuid4().hex}",
) -> "PipelineResult":
    """Synchronous entry. See R1."""
    # validate thread_id (AC1.3)
    # acquire tenant semaphore (AC16.3)
    # start wall-clock timer (AC16.1)
    # invoke research_pipeline with config={"configurable": {"thread_id": thread_id}}
    # on return, build PipelineResult
    ...


def resume_from_gate(thread_id: str, approval: "HitlApproval") -> "PipelineResult":
    """Re-entry after HITL approval/rejection. See R4.
    Idempotent on (thread_id, approval.approval_token) per AC18.8.
    """
    ...
```

### B.3 — `src/m8_pipeline_engine/.env.example` (R14 AC14.6, v0.2.0 adds M8_AUDIT_*)

```
# M8 Pipeline Engine — environment keys (NO SECRETS — all resolved via Vault)
AWS_REGION=us-east-1
M8_MODEL_ID=anthropic.claude-sonnet-4-5-20250929-v1:0
M8_MODEL_PROVIDER=bedrock
M8_CHECKPOINTER_BACKEND=postgres
M8_CHECKPOINTER_DSN_VAULT_PATH=secret/data/m8/checkpointer_dsn
M8_HITL_HMAC_KEY_VAULT_PATH=secret/data/m8/hitl_hmac_key
M8_GATEWAY_BASE_URL=https://m6-gateway.internal:8443
M8_GATEWAY_MTLS_CERT_PATH=/etc/m8/mtls/client.pem
M8_AUDIT_BASE_URL=https://m10-audit.internal:8443
M8_AUDIT_MTLS_CERT_PATH=/etc/m8/mtls/audit-client.pem
M8_HITL_TIMEOUT_SECONDS=14400
M8_MAX_WALL_CLOCK_SECONDS=1200
M8_ALERT_WALL_CLOCK_SECONDS=900
M8_MAX_CONCURRENT_INSTRUMENTS=10
```

### B.4 — `src/m8_pipeline_engine/gateway_client.py` Skeleton (NEW v0.2.0 — dataclass shapes)

```python
"""GatewayClient Protocol + dataclass-shaped requests/responses matching M6."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Optional, Protocol, runtime_checkable


@runtime_checkable
class GatewayClient(Protocol):
    """Protocol matching M6 TrustAwareGateway.call surface.

    v0.1.0 also declared emit_audit here — withdrawn in v0.2.0 per
    Required Fix 4. Audit now goes through the separate AuditClient.
    """

    def call(self, request: "GatewayRequest") -> "GatewayResponse":
        """Raises GatewayError(reason) on any failure path."""
        ...


@runtime_checkable
class VendorAdapterResolver(Protocol):
    """Protocol resolving a VendorAdapter by tool_name.

    Used by _invoke_tool to populate GatewayRequest.vendor_adapter
    (required non-None per M6 __post_init__ — Req-Fix 2).
    """

    def resolve(self, tool_name: str) -> Any:  # VendorAdapter-shaped
        ...


@dataclass(frozen=True)
class GatewayRequest:
    """Dataclass-shaped copy of M6's GatewayRequest (Req-Fix 1).
    Field-for-field equivalent to src/m6_mcp_gateway/gateway.py line 118.
    """
    token: str
    action: str
    tool_name: str
    mcp_server: str
    payload: Any
    trace_id: str
    firm_id: str
    target: Mapping[str, Any]
    context: Mapping[str, Any]
    session_id: Optional[str]
    vendor_adapter: Any  # REQUIRED non-None — Req-Fix 2


@dataclass(frozen=True)
class GatewayResponse:
    """Dataclass-shaped copy of M6's GatewayResponse (Req-Fix 1).
    Only returned on ALLOW / ESCALATE success paths; failure paths raise.
    """
    decision: str  # "ALLOW" | "DENY" | "ESCALATE" — DENY never returned, only raised
    result: Any
    liability_report: Optional[Any]
    trace_id: str
    latency_ms: int
    provenance_head: str
    rule_applied: Optional[str]
    wsp_section: Optional[str]
    reason: Optional[str]


class GatewayError(Exception):
    """Duck-typed copy of M6's GatewayError (Req-Fix 3).
    M8 imports nothing from m6_mcp_gateway — this is a local copy
    with a .reason attribute matching M6's contract.
    """
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class LocalVendorAdapterResolver:
    """Production VendorAdapterResolver.
    Wraps a snapshot of M6's registry fetched at compile time.
    SHARED-WITH-M6: M6 v0.3.0 server-side resolution removes this shim.
    """
    def __init__(self, registry_snapshot: dict[str, Any]) -> None:
        self._reg = registry_snapshot

    def resolve(self, tool_name: str) -> Any:
        try:
            return self._reg[tool_name]
        except KeyError:
            raise GatewayError("invalid_request")


class M6GatewayClient:
    """Production GatewayClient. HTTPS/mTLS to M6 FastAPI."""
    def __init__(
        self, *, base_url: str, mtls_cert_path: str,
        vendor_adapter_registry: VendorAdapterResolver,
        timeout_ms: int = 30000,
    ) -> None:
        ...

    def call(self, request: GatewayRequest) -> GatewayResponse:
        ...


class FakeGatewayClient:
    """Test GatewayClient. Seeded responses; records every call."""
    def __init__(
        self,
        call_responses: dict[str, GatewayResponse | Exception],
    ) -> None:
        self.call_responses = call_responses
        self.recorded_calls: list[GatewayRequest] = []

    def call(self, request: GatewayRequest) -> GatewayResponse:
        self.recorded_calls.append(request)
        resp = self.call_responses[request.tool_name]
        if isinstance(resp, Exception):
            raise resp  # GatewayError(reason) typically
        return resp
```

### B.5 — `src/m8_pipeline_engine/audit_client.py` Skeleton (NEW v0.2.0 — Req-Fix 4)

```python
"""AuditClient Protocol + M10AuditClient + FakeAuditClient.

Introduced in v0.2.0 to replace the invented GatewayClient.emit_audit
method (which M6's TrustAwareGateway does not expose). Talks directly
to M10's FastAPI /audit endpoint over mTLS.
"""
from __future__ import annotations

import ssl
import urllib.error
import urllib.request
from typing import Protocol, runtime_checkable


class AuditEmitError(Exception):
    """Unified audit-emit failure type."""


@runtime_checkable
class AuditClient(Protocol):
    def emit(self, entry: dict) -> None:
        """POST entry to M10's /audit. Raises AuditEmitError on failure."""
        ...


class M10AuditClient:
    """Production AuditClient. mTLS to M10 FastAPI."""
    def __init__(
        self, *, base_url: str, mtls_cert_path: str,
        timeout_ms: int = 10000,
    ) -> None:
        self._url = f"{base_url.rstrip('/')}/audit"
        self._cert = mtls_cert_path
        self._timeout = timeout_ms / 1000.0

    def emit(self, entry: dict) -> None:
        # Build SSL context with client cert
        ctx = ssl.create_default_context()
        ctx.load_cert_chain(self._cert)
        # urllib request; retry once on 5xx
        ...


class FakeAuditClient:
    """Test AuditClient. Records every emit."""
    def __init__(self, fail_at: int = -1) -> None:
        self.entries: list[dict] = []
        self._fail_at = fail_at
        self._count = 0

    def emit(self, entry: dict) -> None:
        self._count += 1
        if self._count == self._fail_at:
            raise AuditEmitError("fake_failure")
        self.entries.append(entry)
```

---

## Appendix C — DECISION-LOG Seed

Seed entries for `src/m8_pipeline_engine/DECISION-LOG.md`. v0.2.0 adds D13 + D14.

```markdown
# M8 Pipeline Engine — Decision Log

## 2026-05-18 — v0.1.0 Initial Draft

### D1. LangGraph chosen over custom pipeline engine
Source: ARCH-04 v2 §M8 Pipeline Engine (LangGraph). Rationale: native
checkpointing + HITL + time-travel + `Send` fan-out. Custom pipeline.py
in 006 lacks checkpointing. See §Architecture Clarification.

### D2. 23 stages ported from 006 pipeline.py (stage numbers stable; 2 names renamed — see D13)
Source: 006 v2 `pipeline.py::_all_stage_methods()` line 160-174. Verified
2026-05-17. v0.2.0 correction (Req-Fix 6): of 23 stages, 21 names match
006 verbatim; stages 12 and 21 are renamed for semantic fit — see D13.

### D3. 3 HITL gates at stages 7, 13, 21
Source: 006 v2 `pipeline.py` line 58 `HITL_STAGES = {7, 13, 21}`. Approver
role assignment (research → compliance → supervising) mirrors 006.

### D4. PostgreSQL checkpointer default, DynamoDB reserved
Source: ARCH-04 v2 §M8. Schema segregation via `search_path=m8_checkpoints`
to avoid M10 Langfuse collision.

### D5. Sonnet model ID tentative
Pinned: `"anthropic.claude-sonnet-4-5-20250929-v1:0"`. PENDING-VERIFICATION.
Task 18 first-live-call probe records actual Bedrock-advertised ID.

### D6. HITL token HMAC-SHA-256 with Vault-resolved key
Rationale: Steering pins `SHA-256(gate_id + approver_id + timestamp)`
abstractly; HMAC variant adds tamper defense against forgery. TTL =
hitl_timeout_seconds. Rotation per D15 (below, added v0.2.0 AC4.12).

### D7. 20 reason codes in v0.1.0 (vs. original target 10) — reconciled in v0.2.0
Initial intent was 10; drafting forced 20 to cover all observed failure
modes. v0.1.0 left three textual references saying "10" while six said
"20" — LLMJ v1 flagged as Required Fix 7. v0.2.0 global sweep makes all
references say 20. Closed set pinned at AC11.1.

### D8. Map-reduce cap at 10 instruments
Rationale: preserves Bedrock regional TPS budget under sustained fan-out.
Phase 3 may tenant-scope.

### D9. Wall-clock ceiling EXCLUDES HITL wait
Rationale: HITL gate could wait 4h; compute budget is 20 min. Measuring
them separately preserves both SLAs.

### D10. Anti-fabrication check at stage 21 (guardrail, not hard fail)
Rationale: 006 pattern. Human reviewer at Gate 3 decides; M8 only
surfaces violations for review. Stage renamed in 007 to reflect
combined responsibility — see D13.

### D11. 006 v2 MetaClaw lesson capture deferred to Phase 3
Rationale: stateless-per-run simplifies Phase 2 lighthouse. Phase 3
re-introduces after baseline data accumulated.

### D12. No `langchain-aws` despite ARCH-04 v2 "Key Libraries"
Rationale: `boto3` Bedrock Runtime `converse` API is sufficient;
`langchain-aws` pulls `langchain` umbrella which breaks Steering Rule 15
provider abstraction. M8 goes direct to `boto3`. v0.2.0 elevates this
from a decision-log entry to Known Blockers row 17 per Required Fix 10,
with an explicit ARCH-04 v2 update request tracked against the
architecture team.

## 2026-05-20 — v0.2.0 LLMJ v1 Fix Pass

### D13. Stage 12 and Stage 21 renames vs 006 — justification (Required Fix 6)
LLMJ v1 flagged that v0.1.0's "provenance continuity" / "verbatim
preservation" framing was partially false: two of 23 stages were
silently renamed vs 006 v2 `pipeline.py::_all_stage_methods()`.

- **Stage 12 rename**: 006 name `_stage_12_sentiment_synthesis` →
  007 name `stage_12_cross_source_synthesis`. Rationale: 006's stage
  synthesized sentiment from a single news/earnings source in a
  single-instrument pipeline. 007's stage is the REDUCE step of the
  map-reduce fan-out introduced at stage 8 — it combines per-instrument
  results (stages 9-11 across up to 10 instruments) PLUS all sources
  (market + news + filings + transcript). "Cross-source synthesis"
  accurately describes the reducer; "sentiment synthesis" does not.

- **Stage 21 rename**: 006 name `_stage_21_final_approval_gate` →
  007 name `stage_21_anti_fabrication_check`. Rationale: 006's stage
  was purely a HITL gate (final advisor approval). 007's stage runs
  the anti-fabrication check (numeric-token provenance audit against
  `state.data_sources`) FIRST, populates `state.anti_fabrication_failures`,
  THEN enters the HITL gate with the failure summary surfaced. The
  stage is a hybrid — anti-fab scan + HITL gate — and the 007 name
  reflects the scan-first discipline.

v0.2.0 keeps the 007 names (they better describe v0.2.0 behavior) and
drops the "verbatim preservation" claim. Audit consumers MUST query on
stage_number (integer 1..23) which is stable across both generations.

### D14. Hypothesis CI budget (Recommended Fix 4)
Property tests run with `max_examples=20` under env `CI=1`, `max_examples=50`
locally. CI wall-clock: ≈100s per suite × 3 suites ≈ 300s. Local: up to
≈750s. Detection at strategies.py module-level via `os.environ.get("CI")`.
Documented to prevent CI-hanging regressions when Hypothesis is tuned up.

### D15. HITL HMAC key rotation contract (Required Fix 12)
Quarterly rotation (90 days), aligned with 24hr mTLS certificate rotation
× 90-day aggregate cycle. Pod-restart-triggered re-fetch — no in-flight
rotation. In-flight pipelines at HITL gates across a rotation boundary
emit `m8_hitl_token_expired` on resumption; approver re-submits with
freshly-signed token using new key. See AC4.12.
```

---

## Appendix D — Cross-Reference Placeholder

Filled in during review cycles. Maps M8 spec sections to spec sections in peer modules (M6, M9, M10, M12) where contract shape matters.

| M8 Section | Peer Module | Peer Section | Notes |
|-----------|-------------|--------------|-------|
| §M6 Gateway Call Pattern | M6 spec v0.2.0 | R1.1 `GatewayRequest` `@dataclass` | M8's `GatewayRequest` is a local dataclass copy — Task 20 asserts `dataclasses.fields()` equality (v0.2.0 Req-Fix 1 corrected v0.1.0 Pydantic drift) |
| §M6 Gateway Call Pattern (failure paths) | M6 spec v0.2.0 | R2 `GatewayError` + `VALID_GATEWAY_REASONS` | M8 catches `GatewayError` and branches on `exc.reason` across all 11 members (v0.2.0 Req-Fix 3) |
| §Architecture Clarification (M9 as input) | M9 spec v0.2.0 | R18 AC18.1-18.7 | M9 declares M8 reads `state.routing_decision`; M8 imports `m9_intent_router.models` type-only |
| §Integration Point with M12 | M12 spec (not yet drafted) | TBD | M12 calls `research_pipeline.run()` in-process |
| §Integration Point with M10 (via AuditClient, v0.2.0) | M10 spec v0.3.0 (pending) | `POST /audit` FastAPI route | M8 `M10AuditClient` POSTs `StageAuditPayload` / `PipelineTerminalAuditPayload` to M10 over mTLS. SHARED-WITH-M10 Known Blockers row 18. |
| §Integration Point with M2/M4 | M2/M4 spec (existing) | M2 `action` vocabulary | M8 uses `action="compliance.screen"` + others registered with M2 |
| §Token Budget Table | M5 spec v0.4.0 (pending) | `PipelineConfig.token_budgets` | M5 owns the dict; M8 reads at compile |
| §Checkpointer Contract | `langgraph-checkpoint-postgres` docs | `PostgresSaver.from_conn_string` | External dependency |
| §FSI Pipeline Stage Catalog | 006 v2 `pipeline.py` lines 160-174 | `_all_stage_methods()` | Provenance for ADAPT — 21 of 23 stage names verbatim; stages 12 + 21 renamed per D13 |

---

## Document Metadata

| Field | Value |
|-------|-------|
| Spec Version | **0.2.0** |
| Date | 2026-05-20 |
| Author | Pipeline and Intent Specialist |
| Review Status | LLMJ-v1 v0.1.0 review completed 2026-05-18 (7.63/10 CONDITIONAL GO); v0.2.0 addresses all 12 Required + Recommended 1-5 + selected minor. Awaiting LLMJ-v1 re-review. |
| Target Review Score | ≥ 8.0/10 GO on LLMJ-v1 re-review (calibration set: M7 v0.3.0, M11 v0.2.0, M9 v0.2.0 — all achieved 8.0+ on their fix passes) |
| Mirror Discipline | M7 v0.3.0 / M11 v0.2.0 / M9 v0.2.0 fix-pass discipline |
| Prior Version | v0.1.0 (1,554 lines, 2026-05-18) |
| Required Fixes Addressed | 12 / 12 (see §Review Fix Traceability) |
| Recommended Fixes Integrated | R1, R2, R3, R4, R5, R11, R12 (7 of 14; others deferred) |
| Sections Implemented | Banner; Changelog (v0.1.0 + v0.2.0 entries); Architecture Clarification; Phase 2 Scope; Known Blockers (18 rows — 2 added in v0.2.0); Steering Rules (11 rules); Requirements R1-R18 with full AC coverage (v0.2.0 adds AC3.10, AC4.12, AC5.8, AC7.11, AC8.10, AC8.11, AC9.8, AC9.9, AC18.7, AC18.8); FSI Pipeline Stage Catalog (23 stages, "006 Name" column for rename audit); HITL Gate Specification (3 gates + key rotation invariant); Token Budget Table; LangGraph State Schema (compliance_check dropped per Req-Fix 9); Checkpointer Contract; M6 Gateway Call Pattern (REWRITTEN per Req-Fix 1-3); Integration Point with M12; Integration Point with M10 (via new AuditClient per Req-Fix 4); Integration Point with M2/M4; Error Code Map (20 rows; row 20 trigger corrected per Req-Fix 5); Tasks (20 atomic; Tasks 14/16/17 reason-code coverage matrix per Rec-Fix 3); Hypothesis Strategy Approach (CI budget per Rec-Fix 4); Review Fix Traceability (**12 rows — one per Required Fix**); Steering-Rule Traceability (11 rules); Appendix A (24 invariants — A24 added per Rec-Fix 2); Appendix B (skeleton files + `__init__.py` with 24 `__all__` names + `graph.py` with `langgraph.types.Send` + `.env.example` with M8_AUDIT_* + `gateway_client.py` dataclass shapes + `audit_client.py` NEW); Appendix C (DECISION-LOG seed with 15 entries — D13 + D14 + D15 added in v0.2.0); Appendix D (cross-reference with M6/M10 v0.2.0 updates) |
| Final Line Count | See `wc -l` at commit — target band: 1,800-1,950 lines (v0.1.0 1,554 + ~300 for fix traceability + expanded response handling + AuditClient protocol + SHARED-WITH amendments) |
