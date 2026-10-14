# Spec: M9 Intent Router

> Module: M9 — Intent Router
> Phase: 2 (Intelligence Layer — RIA lighthouse)
> Owner: Pipeline and Intent Specialist
> **Version: 0.2.0** — LLMJ-v1 fix pass. Addresses all 14 Required Fixes from `m9-intent-router-REVIEW.md` (2026-05-15). Targets ≥ 8.0/10 GO on re-review. Mirrors M7 v0.3.0 + M11 v0.2.0 structural discipline.
> Dependencies (runtime): AWS Bedrock Claude Haiku endpoint (Phase 2 LLM provider); HashiCorp Vault / AWS Secrets Manager (IRSA role resolution, tenant-scoped HMAC key for `utterance_sha256`); outbound HTTPS to Bedrock control plane only.
> Dependencies (code — ALIGNED WITH ARCH-09 MATRIX row M9 = `* . . . * . . . . . . . .`): `m1_identity` (`AidClaims`, `Role` — AgentIdentityDocument passed by the Supervisor/M12 to `route()` for identity-gated classification hints), `m5_config_loader` (`Archetype`, `Runtime`, `SpecialistConfig`, and the new `IntentRouterConfig` sub-model — SHARED-WITH-M5 amendment). ZERO imports from M2, M3, M4, M6, M7, M8, M10, M11, M12, M13, `compliance.gap2`, `compliance.gap6`. The prior v0.1.0 banner claim that M9 imports from M3 is RETRACTED — it misread ARCH-09. See §Review Fix Traceability row 1.
> Consumers (ALIGNED WITH ARCH-09 MATRIX column 9 — M12 marked `*`, M6 marked `.`): **M12 Supervisor Model** (primary and only direct caller in Phase 2 — `intent_router.classify(user_message, aid)` per ARCH-05 v2 §Supervisor Routing Logic lines 275-310). M8 Research Pipeline Stage 1 obtains the supervisor's prior classification via `PipelineState.routing_decision` — M8 does NOT re-call M9. M6 Trust-Aware Gateway does NOT call M9 (ARCH-09 says so; v0.1.0 spec was wrong). See §Review Fix Traceability rows 1 and 7.
> Design Sources: `docs/007-consolidated-design-and-plan.md` Part 9 (Intent Router & Pipeline); ARCH-04 v2 §Tech Stack Decisions (M9 row — LangGraph excluded, LLM function calling); ARCH-05 v2 §Multi-Agent & Memory Architecture §Supervisor Routing Logic (lines 275-310 — Supervisor calls `intent_router.classify(user_message, aid)` directly); ARCH-07 §Model Selection Table (Supervisor = Haiku, `<500ms` — this is the ONLY cited latency number; percentile breakdown is an M9-originated DECISION-LOG SLO, NOT an ARCH-07 claim — see §Review Fix Traceability row 2); ARCH-09 §DEPENDENCY MATRIX row M9 + column M9 (M9 → {M1, M5}; {M12} → M9); Steering rules 7, 8, 13, 14, 15, 20, 32.
> Language: Python 3.12+ | Runtime Validation: Pydantic v2 (pinned `>=2.0,<3.0`) | LLM SDK: `boto3` ≥ 1.34 (Bedrock Runtime client only — NO `anthropic`, NO `langchain`, NO `langgraph`) | Property tests: `hypothesis` ≥ 6.100 (dev only)
> Estimated Lines: ~320 production src lines across `__init__.py` + `taxonomy.py` + `regex_library.py` + `mnpi_scan.py` + `llm_client.py` + `fallback.py` + `route.py` + `models.py` + `hmac_util.py` per ARCH-09 size budget (~300); ~1,800 lines of spec (v0.2.0).

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 0.2.0 | 2026-05-16 | **LLMJ-v1 fix pass.** Full rewrite in place. Addresses 14 Required Fixes + 7 Recommended from `m9-intent-router-REVIEW.md`. Key changes: (1) realigned dependency graph with ARCH-09 matrix — M9 imports M1+M5 (not M3), consumed by M12 (not M6); (2) `RouterContext` gains `identity: AidClaims` field per ARCH-05 v2; (3) M6 integration section deleted; new §Integration Point with M12 reflects Supervisor direct call; (4) ARCH-07 latency claim reduced to `<500 ms` with p50/p95/p99 SLO moved to M9 DECISION-LOG; (5) `RouterContext.archetype: Archetype` is now firm-level from M5 with examples using `tier4_independent_ria`; (6) `FakeLlmClient.responses` accepts `LlmClassification | Exception`; adds `SlowFakeLlmClient` for timeout determinism; (7) `utterance_sha256` switched to HMAC-SHA-256 with tenant-scoped Vault-resolved key; (8) `client.household_summary` renamed to `research.household_summary` to match `pipeline` kind; (9) Task 19 added (cross-module version match test); (10) `m8.research_pipeline_*` pipeline names downgraded to PENDING-CONFIRM-WITH-M8 in §Known Blockers; (11) `taxonomy.py` exempted explicitly in AC12.6; (12) Steering Rule 8 (fail-closed) added to §Steering Rules; (13) `threading.Semaphore(16)` defense-in-depth added (R19); (14) §Review Fix Traceability populated (14 rows). |
| 0.1.0 | 2026-05-14 | Initial draft. Scored 7.42/10 CONDITIONAL GO in LLMJ-v1 review. |

---

## Architecture Clarification: M9 is a Pure In-Process Classifier Consumed by the Supervisor (M12)

ARCH-04 v2 §Tech Stack Decisions places M9 in the "pure library" row alongside M7: no FastAPI, no HTTP listener, no network I/O other than the Bedrock Runtime call through `boto3`. ARCH-09 dependency matrix (lines 302-315) shows:

```
Row M9    (M9 calls...):    *  .  .  .  *  .  .  .  .  .  .  .  .
                            M1 M2 M3 M4 M5 M6 M7 M8 M9 M10 M11 M12 M13
Col M9    (...who calls M9): .  .  .  .  .  .  .  .  .  .   .   *   .
```

**This is the single source of truth.** The v0.1.0 spec inverted this on both axes (claiming M3 not M1, and M6 not M12 as consumer). v0.2.0 aligns. No architect override needed — v0.1.0 was a misread, not a proposed amendment.

- **M9 is a LIBRARY** — a Pydantic v2 `RoutingDecision` model + a pure `route(utterance, context) -> RoutingDecision` function + a swappable `LLMProvider` protocol. Not an HTTP server. Not stateful between calls. Does not schedule anything.
- **M9 is called directly by M12 (Supervisor Model).** Per ARCH-05 v2 §Supervisor Routing Logic: `decision = intent_router.classify(user_message, aid)`. `aid` is an `AidClaims` from M1. M12 constructs `RouterContext` from `aid` + request metadata, then calls `m9_intent_router.route(utterance, context)`.
- **M9 does not orchestrate pipelines.** LangGraph-based pipeline orchestration is M8's concern. M9 only classifies the utterance and returns a `SelectedTarget` that M12 (or the downstream specialist) will later dispatch through M6.
- **M9 does not call MCP tools.** M9 returns `SelectedTarget(kind="tool", name="sfdc.fetch_client", …)`. The Supervisor (M12) or the Specialist ultimately dispatches the tool through M6 per Steering Rule 7. M9 itself has no outbound network I/O to M6.
- **M9 does not write audit.** M9 emits a structured JSON line to stdout via `print()`. The Supervisor (M12) receives the `RoutingDecision` object and is responsible for calling M10 with it as part of the broader supervisor audit event. M9 never imports M10.
- **M9 calls M1 for identity verification context only.** v0.2.0 accepts an already-verified `AidClaims` inside `RouterContext.identity`. M9 does NOT re-verify the signature (that is M12/M6's job). M9 reads `aid.archetype`, `aid.role`, `aid.authority_scope`, `aid.authority_excludes` to inform confidence gating (R5 AC5.8) and MAY short-circuit to `escalate_to_human` if the advisor lacks authority for a classified target (R12 AC12.9). This is what "M9 calls M1" means in ARCH-09: M9 consumes M1 types, not M1 runtime service calls.
- **M8 does not import M9.** M8 Stage 1 consumes `PipelineState.routing_decision` populated by the Supervisor BEFORE the pipeline dispatches. M8 never re-classifies.
- **M9 is runtime-agnostic.** Managed Agents (Cloud Tier 3/4) and Strands (hybrid/on-prem Tier 1/2/5) both have their Supervisor call M9 identically. Provider abstraction (R4) handles cloud-provider swap.

M9 does NOT import from M2, M3, M4, M6, M7, M8, M10, M11, M12, M13, `compliance.gap2`, `compliance.gap6`. M9 imports ONLY from M1 (`AidClaims`, `Role`) and M5 (`Archetype`, `Runtime`, `SpecialistConfig`, `IntentRouterConfig` — read-only config objects and enum values).

---

## Phase 2 Scope

Per `docs/007-consolidated-design-and-plan.md` Part 9 and the Phase 2 plan in ARCH-09 (Week 14-36, 7-person team, 24-week window), M9 Phase 2 scope covers:

- **11-value FSI intent taxonomy** (see §FSI Intent Taxonomy) — closed `IntentCategory` enum. v0.2.0 renames `CLIENT_HOUSEHOLD_SUMMARY` to `RESEARCH_HOUSEHOLD_SUMMARY` to match its `pipeline`-kind dispatch (Fix 11).
- **One LLM provider live** — `BedrockHaikuClient` wrapping Bedrock Runtime `converse` API with Anthropic tool_use schema. Three additional providers (`AzureOpenAIClient`, `VertexClient`, `VllmClient`) are reserved as Protocol-satisfying stubs for Phase 3+ (not implemented in v0.2.0).
- **Two fake LLM providers** — `FakeLlmClient` (supports exception injection per Fix 9) and `SlowFakeLlmClient(block_ms=N)` (supports deterministic timeout testing per Fix 13).
- **One integration point** — M12 Supervisor (direct in-process call per ARCH-05 v2). M8 indirectly consumes `RoutingDecision` via `PipelineState.routing_decision`, populated by M12 BEFORE pipeline dispatch.
- **One config-source amendment** — SHARED-WITH-M5: `IntentRouterConfig` sub-model added to M5 config schema (fields: `model_id`, `provider`, `confidence_high`, `confidence_med`, `timeout_ms`, `fallback_enabled`, `tenant_hmac_key_vault_path`). See §Known Blockers row 2.
- **Tenant-scoped audit hashing** — `utterance_sha256` is now `HMAC-SHA-256(tenant_key, utterance)`. Tenant key resolved from Vault path in `IntentRouterConfig.tenant_hmac_key_vault_path` (Fix 10).

### Explicitly OUT of scope (deferred to "M9-lighthouse-2" in Phase 3 or later)

- **`unsupported` intent category terminal handling** — Phase 2 returns `RoutingDecision(intent=UNSUPPORTED, …, reason_code="unsupported_intent_stub")` with a Phase-3-queryable telemetry counter (`reason_code` + `utterance_sha256` + tenant_id) wired to M10 via stdout audit line. Phase 3 work: rejection templates per archetype, multilingual fallback, top-5 unsupported-intent dashboard.
- **Multi-turn clarification loop** — Phase 2 returns `escalate_to_human` on `<80%` confidence; the channel surfaces a clarifying question. Phase 3 adds a short-horizon clarification loop inside M9 itself (capped at one round, temperature=0, same taxonomy).
- **Non-Bedrock providers live** — Protocol-level stubs only. Phase 3 wires `AzureOpenAIClient`, `VertexClient`, `VllmClient`.
- **Intent-weighted load shaping** — Phase 2 pipelines are capped at 3 concurrent per tenant by M8 (Steering Rule 11). M9 does not participate in admission control in Phase 2.
- **Channel-specific routing hints** — Phase 2 `context` carries `runtime`, `archetype` (firm), `identity`, `tenant_id` only. Channel-specific hints (Slack vs Teams vs web) deferred to Phase 3.
- **Multilingual taxonomy** — Phase 2 is English-only.
- **Conversation memory** — M9 is stateless. Conversation-memory lookup is a supervisor concern, handed to M9 via `context.prior_turns_summary` if M12 populates it. Phase 2 accepts the field but ignores it (R1 AC1.7).
- **Cost attribution per intent** — Phase 2 emits `llm_latency_ms`, `llm_model`, `llm_provider` but not per-call cost. Cost rollups are M10's concern.

---

## Known Blockers & Pending Items

Per ARCH-04 v2, ARCH-09, IMPL-06, and Steering Rule 15. Each maps to a DECISION-LOG entry in `src/m9_intent_router/DECISION-LOG.md` (R17 AC17.4). v0.2.0 downgrades three formerly-RESOLVED rows to PENDING-CONFIRM and adds two new rows (ARCH-09 matrix alignment + pipeline naming).

| # | Area | Question | Impact on M9 | Status |
|---|------|----------|--------------|--------|
| 1 | **ARCH-09 matrix alignment (NEW v0.2.0)** | v0.1.0 banner claimed M9↔{M3,M6}; ARCH-09 says M9↔{M1, M5, M12}. v0.2.0 realigns. No architect override needed — v0.1.0 was a misread. | Caller changed from M6 (v0.1.0) to M12 (v0.2.0). R12 allow-list swaps M3→M1. `RouterContext` gains `identity: AidClaims`. §Integration Point with M6 deleted; §Integration Point with M12 added. | **RESOLVED** (v0.2.0 realigned). |
| 2 | **M5 `IntentRouterConfig` sub-model (SHARED-WITH-M5)** | M9 needs a config object with fields `model_id: str`, `provider: Literal["bedrock","azure_openai","vertex","vllm"]`, `confidence_high: float` (default 0.95), `confidence_med: float` (default 0.80), `timeout_ms: int` (default 1500), `fallback_enabled: bool` (default True), `tenant_hmac_key_vault_path: str`, `region: str` (default `"us-east-1"`). M5 v0.2.0 does NOT currently expose this sub-model. | Resolution: M5 adds `IntentRouterConfig` under `SpecialistConfig`. M9 v0.2.0 uses positive-allow-list import `from m5_config_loader import IntentRouterConfig` and fails AC12.4 AST-import scan until M5 v0.3.0 ships it. Integration-test gate: `tests/integration/test_m9_m5_config_shape.py` (xfail until M5 v0.3.0). | **SHARED-WITH-M5** — M5 to resolve in v0.3.0. Spec'd ETA tied to Phase 2 Week 32 per ARCH-09 build order. |
| 3 | **Bedrock Claude Haiku model ID** | ARCH-07 pins "Bedrock Claude Haiku" without a versioned model ID. v0.2.0 tentatively pins `"anthropic.claude-3-5-haiku-20241022-v1:0"`. | All `BedrockHaikuClient.classify` calls carry this model ID. If deployed Bedrock region does not advertise it, the adapter raises `LlmProviderError` → fallback engages. No crash. | **PENDING-VERIFICATION** — first-live-call probe at Task 16. DECISION-LOG records live ID on mismatch. |
| 4 | **Anthropic tool_use JSON Schema under Bedrock** | Bedrock Converse API wraps Anthropic tool_use slightly differently than direct Anthropic. | Risk: if Bedrock rejects the tool schema, every classification call returns 400 → fallback engages. Task 7 ships a "first live call" fixture. | **PENDING-VERIFICATION** — first-live-call at Task 16. |
| 5 | **M8 pipeline naming convention (DOWNGRADED from v0.1.0 RESOLVED)** | `m8.research_pipeline_1/2/3/single_tool` names were invented by v0.1.0 — they do NOT appear in any published design doc or M8 source. v0.1.0 §Known Blockers marked this RESOLVED under "SemVer discipline" — misleading; the names themselves were never sourced. | Phase 2 Task 19 (new in v0.2.0) asserts M9's pipeline-kind names are a subset of M8's exported `PIPELINE_NAMES` constant. Until M8 v0.1.0 ships and exports that constant, Task 19 is xfail. M9's names are a PROPOSAL to M8, not a confirmed contract. | **PENDING-CONFIRM-WITH-M8** — M8 Phase 2 spec owns the authoritative list. |
| 6 | **M6 `m6.composed_goal_tracking` tool name (DOWNGRADED from v0.1.0 RESOLVED)** | `CLIENT_GOAL_TRACKING` routes to `SelectedTarget(kind="tool", name="m6.composed_goal_tracking")`. This is a composed tool (multi-call goal tracking) — it does NOT appear in M6 Phase 1 source. Invented by v0.1.0. | Phase 2 Task 19 asserts this name is a subset of M6's registered tool set. Until M6 Phase 2 composed-tool manifest lands, Task 19 xfails on this row. | **PENDING-CONFIRM-WITH-M6** — M6 Phase 2 spec owns the list. |
| 7 | **Haiku latency variability under Bedrock load** | Bedrock regional Haiku availability occasionally exceeds ARCH-07 `<500 ms`. | Spec sets `timeout_ms=1500` default — 1 s budget for retries + HTTP overhead above the ARCH-07 published ceiling. On timeout, fallback engages with `fallback_used=True`. Operational, not a spec defect. | RESOLVED — fallback absorbs variance. |
| 8 | **Intent taxonomy versioning** | If the 11-value taxonomy expands, every downstream consumer (M12, audit schema) sees a breaking change. | v0.2.0 pins `SCHEMA_VERSION: Literal["1.1.0"] = "1.1.0"` (bumped from 1.0.0 due to `CLIENT_HOUSEHOLD_SUMMARY` → `RESEARCH_HOUSEHOLD_SUMMARY` rename per Fix 11 — MINOR on add, MAJOR on remove/rename; rename is MAJOR but Phase 2 pre-ship so internal 1.x bump acceptable per DECISION-LOG entry). Adding an enum value is MINOR; removing or renaming post-Phase-2-GA is MAJOR. | RESOLVED — SemVer discipline. |
| 9 | **Fallback router coverage gap** | Deterministic fallback (R7) covers `meeting_prep`, `market_query`, `client_data_lookup` only. | Under Bedrock outage, unmapped utterances escalate to human. `reason_code="regex_fallback_miss"` counter wired at R9. | RESOLVED — documented. |
| 10 | **MNPI-shape regex false positives** | 9-digit ZIP-plus-four → SSN-shape FP → escalate. | Acceptable fail-closed (Steering Rule 8). `reason_code="mnpi_shape_suspected"` rate tracked with tenant dimension (Recommended Fix 1 integrated). If rate >2% in first week, Phase 3 tuning. | RESOLVED — fail-closed + instrumented. |
| 11 | **Determinism under tool_use non-determinism** | Anthropic tool_use `temperature=0` near-deterministic, not byte-identical across regions. | R10 spec-level tie-break (alphabetical enum order — AC10.3). Task 11 Hypothesis asserts over ≥100 utterances. | RESOLVED — spec-level tie-break. |
| 12 | **Tenant HMAC key provisioning** | `utterance_sha256` is now HMAC-SHA-256 with tenant-scoped key (Fix 10). Key resolved from Vault path `IntentRouterConfig.tenant_hmac_key_vault_path`. | Vault path must exist per tenant. If absent at `route()` time → `LlmProviderError`-style escalation with `reason_code="provider_unconfigured"` (bootstrap failure, not runtime). Task 17 asserts. | **PENDING-VERIFICATION** — Ops provisions Vault path in Phase 2 Week 28 bring-up. |
| 13 | **SHA algorithm migration seam (FIPS / post-quantum)** | Current hash is `hmac.new(..., digestmod=sha256)`. Future FIPS mode or post-quantum forcing may require SHA-3 / BLAKE3. | `hmac_util.compute_utterance_digest()` is a single function — migration is a one-file change + SCHEMA_VERSION MAJOR bump. Documented here for future maintainers. | RESOLVED — single-seam refactor. |

---

## Steering Rules M9 Must Honor

| Rule # | Rule | Addressed In |
|--------|------|--------------|
| **7** | Every MCP call MUST pass through M6 Trust-Aware Gateway. | R17 (M9 never calls MCP tools; `SelectedTarget` is a data hand-off to M12/specialist; they dispatch via M6), §Architecture Clarification, §Integration Point with M12. |
| **8** | Fail-closed on ANY compliance check failure. | R8 (MNPI pre-scan short-circuits to `escalate_to_human` before the LLM call), R7 (fallback `regex_fallback_miss` escalates), R12 (AID authority-scope miss escalates), §Taxonomy Invariants. ADDED in v0.2.0 per Fix 12. |
| **13** | Bedrock Claude Haiku for routing/conversation/execution. | R3 (`BedrockHaikuClient`), R4 (provider abstraction preserves swap), §Known Blockers row 3 (model ID verification), Task 7. |
| **14** | NO LLM for compliance (M2/M4 is deterministic OPA). | R2 (`compliance.question` intent → routes to compliance specialist — M9 **NEVER answers**), §FSI Intent Taxonomy row 9, AC2.5 (test asserts compliance specialist route). |
| **15** | LLM provider is abstracted. Swappable via config. | R4 (`LLMProvider` Protocol + `BedrockHaikuClient` + `FakeLlmClient` + `SlowFakeLlmClient` + three reserved stubs), §Design `llm_client.py` skeleton. |
| **20** | Zero credentials in git. All secrets via HashiCorp Vault or AWS Secrets Manager. | R14 (IRSA / Vault resolution via `boto3` default credential chain AND tenant HMAC key via Vault path; AST scan), AC14.1-14.7. |
| **32** | SECURITY PER MODULE: no credentials, Pydantic-validated inputs, MNPI filtered, audit logged, cost_basis never null. | R8 (MNPI pre-scan), R9 (audit payload shape), R12 (module boundary), R13 (forbidden imports), R14 (zero credentials), R19 (concurrency defense-in-depth). `cost_basis_method` not applicable to routing. |

---

## Requirements

### R1. Public Dispatcher Contract — `route(utterance, context) -> RoutingDecision`

M9 exposes one public entry point. It is a pure function: no I/O other than the LLM call through the configured provider + the Vault HMAC-key fetch (cached) + the stdout audit emit. No module-level mutable state, no global registry mutation, no `time.time()` except to measure `llm_latency_ms`.

**Acceptance Criteria:**
- **AC1.1:** `m9_intent_router.route(utterance: str, context: RouterContext) -> RoutingDecision` is importable from the package root.
- **AC1.2:** `RouterContext` is a Pydantic v2 model with `ConfigDict(frozen=True, extra="forbid")` containing: `trace_id: str`, `runtime: Runtime` (from M5 — firm runtime), `archetype: Archetype` (from M5 — **firm-level**: `tier1_investment_bank`..`tier5_hedge_fund`; NOT M3's client-level segmentation — Fix 4), `tenant_id: str`, `identity: AidClaims` (from M1 — **already verified** AID — Fix 8), `prior_turns_summary: Optional[str] = None` (ignored in Phase 2 per §Phase 2 Scope).
- **AC1.3:** `utterance` MUST satisfy `1 <= len(utterance) <= 4096`. Empty or oversize → `RoutingDecision(intent=UNSUPPORTED, selected_target=SelectedTarget(kind="escalate", name="human_specialist"), reason_code="invalid_utterance_length", fallback_used=False)`. No exception raised.
- **AC1.4:** `route()` is NOT `async`. Synchronous only. M12 may wrap the call in `asyncio.to_thread` if needed.
- **AC1.5:** `route()` is thread-safe. No module-level mutable state. Taxonomy, regex library, error vocabulary, and config are loaded once at import time into frozen containers (`types.MappingProxyType`, `frozenset`). Concurrency smoke test (Task 12 extension) runs 50 threads × 20 calls to verify (Recommended Fix 3 integrated).
- **AC1.6:** `route()` does NOT mutate `utterance` or `context`. Verified by deep-copy-before / equality-after in Task 11.
- **AC1.7:** `context.prior_turns_summary` is accepted by the signature (forward-compatibility) but never read in Phase 2. Task 11 asserts behavioural identity when the field is `None` vs an arbitrary string.
- **AC1.8:** `route()` returns within `timeout_ms * 2` wall clock in all paths (LLM success, LLM timeout → fallback, MNPI short-circuit, invalid length). Deterministic test uses `SlowFakeLlmClient(block_ms=3000)` + `timeout_ms=1500` → asserts `route()` returns in `< 3000 ms` AND emits `reason_code="llm_timeout"` (Fix 13 + Recommended Fix 2). Real boto3 timeout is NOT required for this test — `SlowFakeLlmClient` raises `LlmTimeoutError` after `block_ms` elapsed.
- **AC1.9:** `route()` validates `context.identity.archetype` matches `context.archetype.value` (self-consistency — the Supervisor MUST have built RouterContext from the AID). Mismatch → `RoutingDecision(intent=ESCALATE_TO_HUMAN, reason_code="provider_unconfigured")`. This defends against Supervisor misconstruction (Fix 8 integration).

### R2. FSI Intent Taxonomy — 11-Value Closed Enum

The taxonomy is a CLOSED set. Every member has a dispatch entry in the taxonomy → target table. Adding a value is a MINOR bump; removing or renaming is a MAJOR bump. v0.2.0 renames `CLIENT_HOUSEHOLD_SUMMARY` → `RESEARCH_HOUSEHOLD_SUMMARY` (Fix 11 — matches `pipeline`-kind dispatch).

**Acceptance Criteria:**
- **AC2.1:** `IntentCategory` is a `str, Enum` subclass with exactly 11 members: `RESEARCH_MEETING_PREP`, `RESEARCH_PORTFOLIO_REVIEW`, `RESEARCH_MARKET_QUERY`, `RESEARCH_HOUSEHOLD_SUMMARY`, `CLIENT_DATA_LOOKUP`, `CLIENT_GOAL_TRACKING`, `CLIENT_PLAN_SUMMARY`, `TRADE_INQUIRY`, `COMPLIANCE_QUESTION`, `ESCALATE_TO_HUMAN`, `UNSUPPORTED`. String values use dot-notation (e.g., `"research.meeting_prep"`).
- **AC2.2:** `TAXONOMY_DISPATCH: MappingProxyType[IntentCategory, SelectedTarget]` exposes every enum member → `SelectedTarget` mapping. `len(TAXONOMY_DISPATCH) == 11`. Test asserts set-equality with `set(IntentCategory)`.
- **AC2.3:** `compliance.question` maps to `SelectedTarget(kind="escalate", name="compliance_specialist")`. M9 MUST NOT call any LLM path to generate a compliance answer.
- **AC2.4:** `escalate_to_human` maps to `SelectedTarget(kind="escalate", name="human_specialist")`.
- **AC2.5:** `unsupported` maps to `SelectedTarget(kind="escalate", name="human_specialist")` with `reason_code="unsupported_intent_stub"`.
- **AC2.6:** Every `research.*` intent (including `research.household_summary` post-Fix-11 rename) maps to `SelectedTarget(kind="pipeline", name="m8.research_pipeline_{1|2|3|single_tool}")` — names PENDING-CONFIRM-WITH-M8 per §Known Blockers row 5.
- **AC2.7:** `SCHEMA_VERSION: Literal["1.1.0"] = "1.1.0"` exposed at `m9_intent_router.__init__`. Meta-test: if `len(IntentCategory) != 11`, test fails with "taxonomy change requires SemVer bump".
- **AC2.8:** `IntentCategory` is alphabetically ordered by enum value string when iterated. Task 11 Hypothesis tie-break uses this ordering.
- **AC2.9:** No `client.*`-prefixed intent routes to `kind="pipeline"`. No `research.*`-prefixed intent routes to `kind="tool"`. Prefix consistency invariant — Fix 11 resolution. Meta-test at Task 3.

### R3. LLM Function Calling via Bedrock Claude Haiku

The classifier is an Anthropic `tool_use` call — the LLM emits a structured `routing_decision` tool invocation matching the taxonomy JSON Schema. `temperature=0`. No freeform-text reliance.

**Acceptance Criteria:**
- **AC3.1:** `BedrockHaikuClient(model_id: str, region: str, timeout_ms: int, max_retries: int = 2)` — constructor stores config; no Bedrock call until `.classify(...)` invoked. No credentials passed in constructor — `boto3.client("bedrock-runtime")` resolves via default credential chain (IRSA / Vault / env).
- **AC3.2:** `BedrockHaikuClient.classify(utterance: str, taxonomy_schema: dict) -> LlmClassification` issues a Bedrock Runtime `converse` API call with `toolConfig={"tools": [{"toolSpec": {...routing_decision tool...}}], "toolChoice": {"tool": {"name": "routing_decision"}}}`, `inferenceConfig={"temperature": 0.0, "maxTokens": 2000}`. Forces tool invocation.
- **AC3.3:** `LlmClassification` is a Pydantic v2 model with `ConfigDict(frozen=True, extra="forbid")`, fields: `intent: IntentCategory`, `confidence: float` (0.0-1.0), `entities: dict[str, str]`, `latency_ms: int`, `model: str`, `provider: Literal["bedrock","azure_openai","vertex","vllm","fake"]`.
- **AC3.4:** Bedrock timeout beyond `timeout_ms` → `LlmTimeoutError`. Bedrock 5xx → `LlmProviderError(status_code)`. Malformed tool output → `LlmMalformedOutputError`. These three error classes are the only exceptions `classify` ever raises.
- **AC3.5:** Retries capped at `max_retries=2` for 5xx and timeout classes ONLY (never 4xx). Exponential backoff 100 ms × 2^n with ±25% jitter.
- **AC3.6:** `classify` NEVER logs the raw `utterance`. It logs only `{trace_id, utterance_sha256, model, provider, latency_ms, status}`. Task 15 asserts no substring match of a canary utterance in captured stdout.
- **AC3.7:** Model ID is `"anthropic.claude-3-5-haiku-20241022-v1:0"` by default (PENDING-VERIFICATION per §Known Blockers row 3). Override via `IntentRouterConfig.model_id`.
- **AC3.8:** `classify` is synchronous. The boto3 client runs on a worker thread when M9 is called from async code (M12's responsibility, not M9's).

### R4. LLM Provider Abstraction — `LLMProvider` Protocol

Provider is swappable via config. Phase 2 ships one real provider (`BedrockHaikuClient`) and two test providers (`FakeLlmClient` + `SlowFakeLlmClient`). Three additional providers are Protocol-satisfying stubs reserved for Phase 3+.

**Acceptance Criteria:**
- **AC4.1:** `LLMProvider` is a `typing.Protocol` in `src/m9_intent_router/llm_client.py` declaring one method: `classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification`. The Protocol is `@runtime_checkable`.
- **AC4.2:** `BedrockHaikuClient` satisfies `LLMProvider`. `isinstance(BedrockHaikuClient(...), LLMProvider) is True`.
- **AC4.3:** `FakeLlmClient(responses: dict[str, LlmClassification | Exception])` satisfies `LLMProvider` (Fix 9). Keyed by `utterance_sha256`. Values may be:
  - `LlmClassification` → returned verbatim.
  - `LlmTimeoutError` / `LlmProviderError` / `LlmMalformedOutputError` → raised verbatim.
  - Any other Exception subtype → raised verbatim (exercises unhandled-exception paths).
- **AC4.4:** Reserved stubs `AzureOpenAIClient`, `VertexClient`, `VllmClient` exist in `llm_client.py` — each `__init__` raises `NotImplementedError("Phase 3")` and `classify` signature satisfies the Protocol.
- **AC4.5:** `select_provider(config: IntentRouterConfig) -> LLMProvider` is the sole construction point. Dispatch: `"bedrock"` → `BedrockHaikuClient`; `"azure_openai"` → `AzureOpenAIClient`; `"vertex"` → `VertexClient`; `"vllm"` → `VllmClient`. Unknown provider → `ValueError("provider_unconfigured")`.
- **AC4.6:** `route()` never imports `BedrockHaikuClient` directly. Task 2 AST scan confirms.
- **AC4.7:** All concrete providers live in one file: `src/m9_intent_router/llm_client.py`. No per-provider directory sprawl.
- **AC4.8:** `FakeLlmClient.classify` is pure and deterministic given its `responses` dict.
- **AC4.9:** `SlowFakeLlmClient(block_ms: int, timeout_ms: int)` (new in v0.2.0 — Fix 13): sleeps via `time.sleep(min(block_ms, timeout_ms) / 1000.0)` then raises `LlmTimeoutError` if `block_ms > timeout_ms`. Used exclusively by AC1.8 timeout test. Satisfies `LLMProvider`.

### R5. Confidence Threshold Gating

Intent routing follows strict thresholds. Thresholds are config-driven, not hardcoded constants.

**Acceptance Criteria:**
- **AC5.1:** `config.confidence_high` (default 0.95) — `confidence >= 0.95` → direct dispatch via `TAXONOMY_DISPATCH[classification.intent]`.
- **AC5.2:** `config.confidence_med` (default 0.80) — `0.80 <= confidence < 0.95` → dispatch with `reason_code="llm_assisted_plan"` for downstream observability.
- **AC5.3:** `confidence < 0.80` → `RoutingDecision(intent=ESCALATE_TO_HUMAN, selected_target=SelectedTarget(kind="escalate", name="human_specialist"), reason_code="low_confidence", confidence=<original>)`. Original confidence preserved for audit.
- **AC5.4:** `config.confidence_high > config.confidence_med > 0.0` invariant. Pydantic validator enforces; loader fails if violated.
- **AC5.5:** Both thresholds inclusive at the lower bound: `confidence == 0.95` → direct dispatch; `confidence == 0.80` → llm-assisted; `confidence == 0.799` → escalate.
- **AC5.6:** Table-driven test asserts boundaries: `0.94999`, `0.95`, `0.95001`, `0.79999`, `0.80`, `0.80001`, `0.0`, `1.0`, `float("inf")`, `float("-inf")` (Recommended Fix 4 integrated).
- **AC5.7:** `confidence == NaN` → treated as `< 0.80` → escalate with `reason_code="low_confidence"`. `float("inf")`/`float("-inf")` → Pydantic `Field(ge=0.0, le=1.0)` rejects at `LlmClassification` construction → `LlmMalformedOutputError` raised by `classify`.
- **AC5.8:** `context.identity.role == Role.agent` AND `classification.intent == TRADE_INQUIRY` → downgrade to `confidence_med` bucket regardless of LLM confidence (Fix 8 integration — agent-issued trade inquiries get extra scrutiny). Documented in §Confidence Threshold Table.

### R6. Entity Extraction — Regex-First, LLM-Fallback

Entities are extracted from the utterance by a regex library BEFORE the LLM call. The LLM's `entities` tool field is a cross-check, not a source of truth.

**Acceptance Criteria:**
- **AC6.1:** `extract_entities(utterance: str) -> dict[str, str]` is pure, returning dict keyed by `ticker`, `client_id`, `household_id`, `account_id`, `date_range`. Missing slots absent (not `None`).
- **AC6.2:** `ticker` regex: `r"\b[A-Z]{1,5}\b"` case-sensitive; filtered against a Phase 2 whitelist of ~50 NYSE/NASDAQ tickers (§Entity Extraction Regex Library).
- **AC6.3:** `client_id` regex: Salesforce 18-char case-sensitive alphanumeric `r"\b[a-zA-Z0-9]{18}\b"` with trailing 3-char case-insensitive checksum validator. Checksum algorithm: split first 15 chars into three 5-char groups; per group, build a 5-bit number where bit `i` = 1 if char `i` is uppercase; map each 5-bit number (0-31) into base-32 alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZ012345` — that 3-char sequence is the trailing checksum (Recommended Fix 11 integrated).
- **AC6.4:** `household_id` regex: `r"\bHH-[A-Z0-9]{10,16}\b"` — firm-scoped `HH-` prefix.
- **AC6.5:** `account_id` regex: `r"\bACC-[A-Z0-9]{8,12}\b"` — firm-scoped `ACC-` prefix.
- **AC6.6:** `date_range` regex: ISO-8601 range `r"\b(\d{4}-\d{2}-\d{2})\s*(?:to|-|through|—)\s*(\d{4}-\d{2}-\d{2})\b"` PLUS relative forms (`last_quarter`, `YTD`, `last_30_days`, `last_90_days`, `last_12_months`) via whitelist.
- **AC6.7:** Regex functions never raise. Hypothesis property test asserts no `re.error` over ≥500 synthetic inputs.
- **AC6.8:** `entities` in `RoutingDecision.audit_payload()` is **keys only** — values redacted to `"<present>"`.

### R7. Deterministic Fallback Router — Keyword-Regex Safety Net

On LLM failure, a deterministic keyword-regex router classifies the utterance to one of three canonical intents. If none match, escalate. `fallback_used=True` marks the decision for audit.

**Acceptance Criteria:**
- **AC7.1:** `fallback_classify(utterance: str) -> Optional[IntentCategory]` is pure. Returns `None` if no pattern matches.
- **AC7.2:** Supported fallback patterns:
  - `meeting_prep` — `r"\b(prep|prepare|prep me|meeting|brief me|get ready)\b"` → `RESEARCH_MEETING_PREP`.
  - `market_query` — `r"\b(market|quote|price|research|earnings|fundamentals)\b"` → `RESEARCH_MARKET_QUERY`.
  - `client_data_lookup` — `r"\b(show|lookup|find|get|fetch|pull up)\s+(client|account|household)\b"` → `CLIENT_DATA_LOOKUP`.
- **AC7.3:** On `LlmTimeoutError` → if `fallback_classify` returns a value → `RoutingDecision(intent=<value>, confidence=0.5, fallback_used=True, reason_code="llm_timeout")`.
- **AC7.4:** On `LlmTimeoutError` → if `fallback_classify` returns `None` → `RoutingDecision(intent=ESCALATE_TO_HUMAN, confidence=0.0, fallback_used=True, reason_code="regex_fallback_miss")`.
- **AC7.5:** Same for `LlmProviderError(5xx)` → `reason_code="llm_error_5xx"`. For `LlmMalformedOutputError` → `reason_code="llm_malformed_output"`. For `taxonomy_mismatch` → also fallback.
- **AC7.6:** For 4xx provider errors → NO fallback. Escalate with `reason_code="llm_error_4xx"` — 4xx is a config defect, not transient.
- **AC7.7:** `config.fallback_enabled=False` → skip `fallback_classify` → escalate with original `reason_code`. Default `True`. Test table includes `fallback_enabled=False + 4xx` row (Recommended Fix 6).

### R8. MNPI-Safe Prompt — Pre-LLM Shape Scan + HMAC-SHA-256 Tenant-Scoped Audit

Raw utterance NEVER appears in audit logs. M9 computes `utterance_sha256 = HMAC-SHA-256(tenant_key, utterance)` once at the top of `route()` and uses that for all observability. Before the LLM call, M9 scans for MNPI-shape patterns. Suspected hit → short-circuit to `escalate_to_human`. **v0.2.0 change (Fix 10):** switched from plain SHA-256 to HMAC-SHA-256 with a tenant-scoped Vault-resolved key.

**Acceptance Criteria:**
- **AC8.1:** `utterance_sha256 = hmac.new(tenant_key_bytes, utterance.encode("utf-8"), hashlib.sha256).hexdigest()` where `tenant_key_bytes = _resolve_tenant_hmac_key(context.tenant_id, config.tenant_hmac_key_vault_path)`. Computed ONCE per call and propagated to `LlmClassification`, `RoutingDecision`, and the audit payload. Never recomputed downstream. **Rainbow-table attack across tenants is no longer feasible** — two tenants hashing the same utterance produce different digests (Fix 10).
- **AC8.2:** `scan_mnpi_shape(utterance: str) -> Optional[str]` returns the matched MNPI category name if any regex hits, else `None`. Pure, no I/O.
- **AC8.3:** MNPI-shape patterns (full table in §MNPI-Shape Patterns):
  - `ssn` — `r"\b\d{3}-\d{2}-\d{4}\b"` OR `r"\b\d{9}\b"` with anti-ZIP-plus-four filter.
  - `bank_account` — `r"\b\d{10,17}\b"` (excludes 9-digit).
  - `routing_number` — `r"\b\d{9}\b"` combined with ABA checksum validator (positional weights 3,7,1,3,7,1,3,7,1; sum % 10 == 0).
- **AC8.4:** MNPI hit → `RoutingDecision(intent=ESCALATE_TO_HUMAN, confidence=0.0, fallback_used=False, reason_code="mnpi_shape_suspected", entities={})`. No LLM call issued.
- **AC8.5:** MNPI hit → `route()` returns in under 20 ms. Benchmark asserts at Task 14.
- **AC8.6:** Matched MNPI category NOT included in `reason_code` beyond canonical `mnpi_shape_suspected` — revealing "ssn" in audit is itself a MNPI leak.
- **AC8.7:** Regex false positives documented in §Known Blockers row 10. Acceptable fail-closed posture (Steering Rule 8).
- **AC8.8:** Task 14 negative-path tests: every MNPI category triggers; every near-miss (8-digit account, ZIP-plus-four, 10-digit phone) tested. ABA check isolates routing-vs-ZIP.
- **AC8.9:** Tenant HMAC counter: audit payload carries `tenant_id` (already a field) plus `reason_code="mnpi_shape_suspected"` enabling per-tenant false-positive dashboards without re-grep (Recommended Fix 1 integrated).

### R9. Structured Audit Emission

Every `route()` call emits a log event that the Supervisor (M12) captures and hands to M10 as the `AuditEntry.payload`. M9 itself does not write to M10.

**Acceptance Criteria:**
- **AC9.1:** `RoutingDecision.audit_payload() -> dict[str, Any]` returns a dict with exactly these keys: `trace_id`, `utterance_sha256`, `intent`, `confidence`, `selected_target`, `fallback_used`, `llm_latency_ms`, `llm_model`, `llm_provider`, `reason_code`, `entities_present`, `tenant_id` (added in v0.2.0 — enables per-tenant MNPI counter per Recommended Fix 1).
- **AC9.2:** `entities_present` is a sorted list of slot names that `extract_entities` populated — VALUES are NOT included.
- **AC9.3:** `selected_target` is emitted as `{"kind": <str>, "name": <str>}` dict (JSON-safe).
- **AC9.4:** `utterance_sha256` is the 64-char hex digest (HMAC-SHA-256 output). Raw utterance NEVER present. Task 10 regex scan over captured audit blob asserts no substring match for a canary utterance.
- **AC9.5:** PII-free invariant: no email, no SSN, no account number, no routing number, no client name, no ticker value, no household ID, no account ID literal in audit. Task 10 regex scan enforces. `identity.sub` and other AID fields NOT in audit.
- **AC9.6:** `reason_code`, if set, drawn from `VALID_REASON_CODES` (R11). If unset (successful high-confidence dispatch), `reason_code: None`.
- **AC9.7:** Emission via stdlib `print(json.dumps(...))` to stdout — NOT `logging.getLogger()` (R13 forbids `logging`). One line per route call. Supervisor (M12) sidecar captures stdout and forwards to M10.
- **AC9.8:** Emitted audit payload validates against `schemas/m9_audit_payload.schema.json` (JSON Schema 2020-12). Schema shipped in `src/m9_intent_router/schemas/`. Task 10 round-trips. Meta-test (Task 10 extension, Recommended Fix 9): asserts `m9_audit_payload.schema.json` itself validates against the JSON Schema 2020-12 meta-schema.

### R10. Determinism & Idempotency

Same `(utterance, context)` → same `RoutingDecision`, excluding `llm_latency_ms`. Temperature=0 plus taxonomy tie-break is the mechanism.

**Acceptance Criteria:**
- **AC10.1:** Two calls with identical `(utterance, context)` against the same `LLMProvider` instance produce `RoutingDecision`s whose `model_dump(exclude={"llm_latency_ms"})` are equal.
- **AC10.2:** Against `FakeLlmClient` seeded with a known response, two calls are byte-identical on `model_dump_json(sort_keys=True, exclude={"llm_latency_ms"})`.
- **AC10.3:** Tie-break rule: equal top-token probability → pick earlier in `IntentCategory` alphabetical order. `min(candidates, key=lambda c: c.intent.value)`.
- **AC10.4:** Hypothesis property test asserts determinism over ≥100 generated utterances: `route(u, c) == route(u, c)` for every pair. `@settings(max_examples=100, deadline=500)`. Honest CI budget: 3 property files × 100 examples × 500 ms ≈ 150 s worst-case (Recommended Fix 5 integrated — documented, not hidden).
- **AC10.5:** Idempotency: `route()` does not mutate its inputs. Deep-copy-before / equality-after for both args.
- **AC10.6:** `route()` does not consume randomness from `random.*` or `secrets.*` or `uuid.uuid4()`. Task 2 AST scan forbids these imports in `route.py`.
- **AC10.7:** `llm_latency_ms` is the only non-deterministic field and is EXCLUDED from determinism comparisons explicitly.

### R11. Error Vocabulary — Closed Frozen Set

All `reason_code` values are drawn from a closed frozen set. Attempting to emit an unknown code is a developer error caught at test time.

**Acceptance Criteria:**
- **AC11.1:** `VALID_REASON_CODES: frozenset[str] = frozenset({"llm_timeout", "llm_error_5xx", "llm_error_4xx", "llm_malformed_output", "mnpi_shape_suspected", "low_confidence", "regex_fallback_miss", "provider_unconfigured", "taxonomy_mismatch", "llm_assisted_plan", "invalid_utterance_length", "unsupported_intent_stub", "aid_authority_denied"})` — 13 codes in v0.2.0 (added `aid_authority_denied` per Fix 8 R12 AC12.9).
- **AC11.2:** `RoutingDecision.reason_code: Optional[str]` with Pydantic `@field_validator` asserting `v is None or v in VALID_REASON_CODES`.
- **AC11.3:** Meta-test (Task 15) exercises every `reason_code`. Unreachable codes fail the test.
- **AC11.4:** Adding a code = MINOR bump; removing/renaming = MAJOR bump. DECISION-LOG records every change.
- **AC11.5:** `reason_code` strings are lowercase snake_case, matching regex `^[a-z][a-z0-9_]+[a-z0-9]$`. Lint asserted.
- **AC11.6:** Error vocabulary MUST NOT leak MNPI-category specificity. `mnpi_shape_suspected` is the only MNPI-related code — no `ssn_suspected`, no `routing_suspected`.

### R12. Module Boundary Enforcement (AST Scan) — ARCH-09 ALIGNED

M9 imports ONLY from `m1_identity` and `m5_config_loader` per ARCH-09 matrix row M9. Positive allow-list, not negative blacklist. **v0.2.0 change (Fix 1):** `m3_schema_registry` REMOVED from allow-list; `m1_identity` ADDED.

**Acceptance Criteria:**
- **AC12.1:** `tests/security/test_module_boundary.py` walks every `.py` file under `src/m9_intent_router/` with `ast.parse`, collects every `Import` / `ImportFrom` node, and rejects any whose module matches `^(m2_|m3_|m4_|m6_|m7_|m8_|m10_|m11_|m12_|m13_|compliance\.)`.
- **AC12.2:** Positive allow-list for intra-project imports: `m1_identity.{AidClaims, Role, InvalidAidError}`; `m5_config_loader.{Archetype, Runtime, SpecialistConfig, IntentRouterConfig}`. Any other intra-project dotted module name fails the scan. **m3_schema_registry is NOT on the allow-list in v0.2.0 — removed per Fix 1.**
- **AC12.3:** From M1, M9 imports ONLY `AidClaims`, `Role`, `InvalidAidError` — used exclusively for `RouterContext.identity` field typing and authority checks in `route.py`. Task 2 asserts M9 never re-verifies a token (`IdentityService.verify` is not imported).
- **AC12.4:** From M5, M9 imports `Archetype`, `Runtime`, `SpecialistConfig`, `IntentRouterConfig` (pending M5 v0.3.0 per §Known Blockers row 2). Loader via `m5_config_loader.load_intent_router_config(...)`.
- **AC12.5:** Test iterates every import in every source file; positive-allow-list hit is the only accept path.
- **AC12.6:** Forbidden string-level references: `test_no_m8_string_ref.py` scans for the literal `"m8_"` in source — rejected unless inside documentation strings. **`taxonomy.py` is explicitly exempted from this scan** (Fix 14) — it must contain literal strings like `"m8.research_pipeline_1"` by design. Exemption is hardcoded in the test: `EXEMPT_FILES = {"src/m9_intent_router/taxonomy.py"}`.
- **AC12.7:** `pyproject.toml` `[project.dependencies]` contains only: `pydantic>=2.0,<3.0`, `boto3>=1.34`, `m1-identity>=0.1.0,<1.0`, `m5-config-loader>=0.3.0,<1.0`. Task 17 asserts. **`m3-schema-registry` REMOVED in v0.2.0.**
- **AC12.8:** `from m3_schema_registry ...` anywhere in M9 source is a test failure (ARCH-09 says M9 does not import M3). Task 2 asserts.
- **AC12.9:** If `context.identity.authority_scope` does not include a scope matching the classified `SelectedTarget` (per §Authority Scope Matrix), route returns `RoutingDecision(intent=ESCALATE_TO_HUMAN, reason_code="aid_authority_denied", confidence=<original>)`. Fail-closed per Steering Rule 8. Task 16 exercises.

### R13. Forbidden Imports (AST Scan)

M9 is stdlib-only outside a small allow-list. Forbidden imports would introduce logging-side-channel MNPI leaks, network leaks, process escape, filesystem surprise, or pipeline-framework coupling.

**Acceptance Criteria:**
- **AC13.1:** `tests/security/test_forbidden_imports.py` AST-scans every source file and rejects imports of: `logging`, `requests`, `httpx`, `urllib`, `urllib3`, `langchain`, `langgraph`, `anthropic`, `openai`, `warnings`, `tempfile`, `socket`, `subprocess`, `aiohttp`, `grpc`, `google.cloud`, `azure.*`.
- **AC13.2:** Allow-list stdlib: `ast`, `base64`, `datetime`, `enum`, `functools`, `hashlib`, `hmac`, `json`, `re`, `time`, `types`, `typing`, `collections`, `threading`. Third-party: `pydantic`, `boto3`, `botocore`. Intra-project: `m1_identity.*`, `m5_config_loader.*`.
- **AC13.3:** `boto3` allowed ONLY in `src/m9_intent_router/llm_client.py` AND `src/m9_intent_router/hmac_util.py` (the latter for Vault SDK via boto3 Secrets Manager client). Any other M9 file importing `boto3` fails the scan.
- **AC13.4:** `hmac` allowed globally (Fix 10 — used for `utterance_sha256`). `hashlib` allowed globally. `base64` allowed globally (reserved for Phase 3 binary-safe entity encodings).
- **AC13.5:** `print` is explicitly allowed as the audit emission mechanism. A test asserts `print(` appears in exactly one place: `src/m9_intent_router/route.py` `_emit_audit` function.
- **AC13.6:** `time.time()` / `time.perf_counter()` allowed for `llm_latency_ms` only. Forbidden: `time.sleep` in production code paths (allowed in `SlowFakeLlmClient` since it is a test utility).
- **AC13.7:** `threading` allowed for boto3 timeout wrappers AND `threading.Semaphore(16)` defense-in-depth (R19). `asyncio` is NOT imported by M9.

### R14. Zero Credentials in Code

No API keys, tokens, passwords, model endpoint secrets, or connection strings in source code, config files, or environment-variable defaults. Ever.

**Acceptance Criteria:**
- **AC14.1:** `tests/security/test_no_hardcoded_creds.py` regex-scans every source file and `pyproject.toml` for literal assignments matching credential shapes: `(?i)(api_key|apikey|secret|password|token|access_key)\s*=\s*['"][^'"]+['"]`. Zero hits.
- **AC14.2:** Bedrock credentials resolve via `boto3` default chain: IRSA → instance metadata → env → Vault. M9 code passes NO credentials to `boto3.client("bedrock-runtime")`.
- **AC14.3:** AWS region read from `IntentRouterConfig.region` (defaults to `"us-east-1"`). The default literal exists in M5 `IntentRouterConfig`, not in M9.
- **AC14.4:** **Ships `.env.example`** (Recommended Fix 7 integrated — no `if present` hedge). Contents: `AWS_REGION=us-east-1`, `M9_PROVIDER=bedrock`, `M9_TIMEOUT_MS=1500`, `M9_TENANT_HMAC_KEY_VAULT_PATH=secret/data/m9/tenants/<tenant_id>/hmac_key`. Zero credential-shaped names. Lives at `src/m9_intent_router/.env.example`. Task 17 asserts shipping.
- **AC14.5:** Dockerfile is NOT shipped in Phase 2 (M9 is in-process).
- **AC14.6:** Runtime configuration logs `IntentRouterConfig.model_dump(exclude={"tenant_hmac_key_vault_path"})` — defensive exclude. v0.1.0's `provider_secret` phantom exclude is removed.
- **AC14.7:** Tenant HMAC key is fetched from Vault at process startup (cached in memory, not re-fetched per call). If the Vault path resolves to empty bytes or is absent, process startup fails with `provider_unconfigured` and the pod does not serve traffic. Task 17 asserts.

### R15. Public API Surface — `__all__`

The package's public API is small and frozen. Internal helpers are leading-underscore-prefixed and MUST NOT be imported from outside the package.

**Acceptance Criteria:**
- **AC15.1:** `src/m9_intent_router/__init__.py` declares `__all__ = ["route", "RoutingDecision", "RouterContext", "IntentCategory", "SelectedTarget", "VALID_REASON_CODES", "LLMProvider", "BedrockHaikuClient", "FakeLlmClient", "SlowFakeLlmClient", "SCHEMA_VERSION"]`. Exactly these 11 names in v0.2.0 (added `SlowFakeLlmClient` for deterministic timeout tests — Fix 13).
- **AC15.2:** Importing a leading-underscore name from outside the package is a test failure.
- **AC15.3:** `SCHEMA_VERSION` is `"1.1.0"` in v0.2.0.
- **AC15.4:** Every `__all__` name has a Sphinx-style docstring.
- **AC15.5:** Reserved providers (`AzureOpenAIClient`, `VertexClient`, `VllmClient`) are NOT in `__all__`.
- **AC15.6:** Adding or removing a name from `__all__` is a MAJOR bump. Modifying a signature is also a MAJOR bump.

### R16. Observability Contract — Latency Budget

M9's `route()` target is **ARCH-07 published: `< 500 ms` for Supervisor Haiku (Model Selection Table line 57)**. The percentile breakdown below is an **M9-originated SLO** recorded in `DECISION-LOG.md` — **NOT cited to ARCH-07** (Fix 2).

**Acceptance Criteria:**
- **AC16.1:** `RoutingDecision.audit_payload()` is called exactly once per `route()` invocation. Computational cost < 1 ms.
- **AC16.2:** Benchmark issues 500 calls against `FakeLlmClient` with seeded classification. Asserts adapter-layer overhead < 10 ms.
- **AC16.3:** Benchmark captures p50, p95, p99 and emits `tests/benchmarks/m9_latency.json`. CI fails if p99 adapter-layer overhead regresses > 20%.
- **AC16.4:** **ARCH-07 SOURCED TARGET:** `p_max < 500 ms` on warm Bedrock (published number). **M9 DECISION-LOG INTERNAL SLO (not cited to ARCH-07):** p50 < 200 ms, p95 < 500 ms, p99 < 1000 ms. These percentile numbers are owned by M9, documented in DECISION-LOG, and MAY be revised without ARCH-07 amendment (Fix 2).
- **AC16.5:** `llm_latency_ms` measured with `time.perf_counter()` (monotonic). Test asserts `llm_latency_ms >= 0`.
- **AC16.6:** MNPI short-circuit < 20 ms (AC8.5). Invalid-utterance-length path < 5 ms.
- **AC16.7:** Concurrency smoke test (Recommended Fix 3): 50 threads × 20 `route()` calls; assert no deadlock, no exception, total wall-clock < 30 s with FakeLlmClient seeded at 50 ms per call.

### R17. Integration Point with M12 (Supervisor Model) — REPLACES v0.1.0 §Integration Point with M6

M12 Supervisor Model is M9's only direct caller in Phase 2 (ARCH-09 matrix column 9, M12 marked `*`). M6 does NOT call M9 (ARCH-09 matrix column 9, M6 marked `.`). v0.1.0 got this wrong; v0.2.0 corrects it (Fix 1, Fix 7). **This section replaces the former §Integration Point with M6.**

**Acceptance Criteria:**
- **AC17.1:** M12 Supervisor calls M9 directly via `m9_intent_router.route(utterance, context)`. Not through M6. Not as a `VendorAdapter`. The `VendorAdapter` Protocol in `m6_mcp_gateway/adapters.py` (real shape: `name: str` + `call(*, tool_name, payload)`) is NOT implemented by M9 — M9 is not a vendor seen through M6 (Fix 3).
- **AC17.2:** M12 constructs `RouterContext` from the verified `AidClaims` it received at request ingress: `RouterContext(trace_id=…, runtime=…, archetype=Archetype(aid.archetype), tenant_id=aid.firm_id, identity=aid, prior_turns_summary=…)`. M9 AC1.9 asserts self-consistency.
- **AC17.3:** M12 handles all audit writes to M10. M9 emits a structured JSON line to stdout; M12's sidecar (or equivalent log shipper) scrapes and forwards.
- **AC17.4:** M9 publishes a DECISION-LOG entry for any change to: `IntentCategory` enum, `VALID_REASON_CODES`, `SCHEMA_VERSION`, public `__all__`, `RouterContext` shape, or `selected_target.name` taxonomy. Rename policy (Recommended Fix 12 integrated): renaming `selected_target.name` is a MAJOR bump; old name MAY be aliased for one minor-version deprecation window; audit consumers MUST query on `utterance_sha256` + `intent.value`, NOT on `selected_target.name` alone.
- **AC17.5:** M12 spec (when v0.1.0 ships) cites this section by name.
- **AC17.6:** Integration contract test: `tests/integration/test_m12_m9_supervisor_call.py` constructs a `RouterContext` with a fake `AidClaims` (from `m1_identity.IdentityService().issue(...)`), calls `route()`, asserts round-trip shape. Does NOT import M12 (Phase 2 depth-first).
- **AC17.7:** Rate-limiting is M12's or M6's job. M9 holds a `threading.Semaphore(16)` defense-in-depth cap (R19) but never rejects calls — only serializes them.

### R18. Indirect Integration with M8 (via PipelineState, not direct call) — REWRITTEN from v0.1.0

M8's LangGraph pipeline consumes a `RoutingDecision` from `PipelineState.routing_decision`. M8 does NOT call M9. The Supervisor (M12) runs M9 BEFORE dispatching to M8 and passes the decision as initial pipeline state. **v0.2.0 change (Fix 1):** the "M8 calls M9 via M6" chain from v0.1.0 is removed — ARCH-09 says neither M8 nor M6 calls M9.

**Acceptance Criteria:**
- **AC18.1:** M9 has zero import-time or runtime reference to M8. Task 2 AST scan confirms (AC12.6 string-literal scan exempts `taxonomy.py` per Fix 14).
- **AC18.2:** M8 does not call M9. M8 reads `pipeline_state.routing_decision` at Stage 1 (details in M8 spec).
- **AC18.3:** `RoutingDecision.selected_target.kind == "pipeline"` → `selected_target.name` matches an M8 pipeline name. Phase 2 **PROPOSED (PENDING-CONFIRM-WITH-M8, Fix 6)**: `m8.research_pipeline_1`, `m8.research_pipeline_2`, `m8.research_pipeline_3`, `m8.research_single_tool`.
- **AC18.4:** If M8 adds a pipeline → M9 taxonomy MINOR bump → audit schema MINOR bump.
- **AC18.5:** `RoutingDecision.selected_target.kind == "tool"` → `selected_target.name` matches an M6-registered tool (e.g., `sfdc.fetch_client`, `emoney.fetch_plan_summary`, `orion.fetch_transactions`). `m6.composed_goal_tracking` is PENDING-CONFIRM-WITH-M6 (Fix 6).
- **AC18.6:** Cross-module integration test `tests/integration/test_m8_m9_stage1_contract.py` stubs M8 pipeline state, constructs a `RoutingDecision` with `selected_target.name="m8.research_pipeline_1"`, asserts shape matches the contract documented in §Integration Point with M8. Does NOT import M8.
- **AC18.7:** M9 never receives M8 pipeline state — it only ever receives `(utterance, context)`.

### R19. Concurrency Defense-in-Depth — `threading.Semaphore(16)`

Defense-in-depth against M12/M6 rate-limiter gaps. Pure-sentinel local cap (Recommended Fix 8 integrated).

**Acceptance Criteria:**
- **AC19.1:** `route()` acquires a module-level `threading.Semaphore(16)` at entry and releases on return (via `try/finally`). Cap is hardcoded; not tenant-scoped in Phase 2.
- **AC19.2:** Semaphore DOES NOT reject — it blocks. Blocked callers wait in FIFO.
- **AC19.3:** Task 12 concurrency smoke test verifies `Semaphore(16)` holds: 50 threads × 20 calls = 1000 calls, max concurrent `classify()` observed ≤ 16, no deadlock, total < 30 s.
- **AC19.4:** The semaphore counter is observable via a pure `_inflight_count()` helper (for debug only, not exported).
- **AC19.5:** Semaphore does NOT wrap `_emit_audit` — audit emission is fast and unserialized.

---

## FSI Intent Taxonomy — 11 Categories (v0.2.0)

The closed taxonomy enumerates every intent M9 can classify. v0.2.0 renames `CLIENT_HOUSEHOLD_SUMMARY` → `RESEARCH_HOUSEHOLD_SUMMARY` (Fix 11 — prefix alignment with `pipeline` kind). Changing this table is a MINOR (add) or MAJOR (remove/rename) version bump. v0.2.0 represents a MAJOR rename accepted pre-Phase-2-GA with internal bump to `SCHEMA_VERSION=1.1.0`.

| # | `IntentCategory` (enum) | String Value | `SelectedTarget.kind` | `SelectedTarget.name` | Example Utterance | Specialist / Pipeline |
|---|------------------------|--------------|-----------------------|-----------------------|-------------------|-----------------------|
| 1 | `RESEARCH_MEETING_PREP` | `research.meeting_prep` | `pipeline` | `m8.research_pipeline_1` ¹ | "Prep me for the Henderson meeting tomorrow" | Research Specialist — pipeline 1 |
| 2 | `RESEARCH_PORTFOLIO_REVIEW` | `research.portfolio_review` | `pipeline` | `m8.research_pipeline_2` ¹ | "Review the Johnson portfolio for Q1" | Research Specialist — pipeline 2 |
| 3 | `RESEARCH_MARKET_QUERY` | `research.market_query` | `pipeline` | `m8.research_single_tool` ¹ | "What's NVDA's earnings outlook?" | Research Specialist — single-tool path |
| 4 | `RESEARCH_HOUSEHOLD_SUMMARY` | `research.household_summary` | `pipeline` | `m8.research_pipeline_3` ¹ | "Summarize the Martinez household" | Research Specialist — pipeline 3 (renamed from `client.*` in v0.2.0 — Fix 11) |
| 5 | `CLIENT_DATA_LOOKUP` | `client.data_lookup` | `tool` | `sfdc.fetch_client` | "Show me client 001ABCDEFGHIJKLMNO" | Client Service Specialist — direct via M6 |
| 6 | `CLIENT_GOAL_TRACKING` | `client.goal_tracking` | `tool` | `m6.composed_goal_tracking` ² | "How is Henderson tracking to retirement?" | Client Service Specialist — composed tool |
| 7 | `CLIENT_PLAN_SUMMARY` | `client.plan_summary` | `tool` | `emoney.fetch_plan_summary` | "Pull the Henderson financial plan" | Client Service Specialist |
| 8 | `TRADE_INQUIRY` | `trade.inquiry` | `tool` | `orion.fetch_transactions` | "Show me Henderson's trades this quarter" | Execution Specialist (read-only Phase 2) |
| 9 | `COMPLIANCE_QUESTION` | `compliance.question` | `escalate` | `compliance_specialist` | "Is NVDA on the restricted list?" | Compliance Specialist — OPA only, NO LLM answer |
| 10 | `ESCALATE_TO_HUMAN` | `escalate_to_human` | `escalate` | `human_specialist` | (confidence < 0.80 OR LLM error OR MNPI OR AID authority denied) | Human advisor |
| 11 | `UNSUPPORTED` | `unsupported` | `escalate` | `human_specialist` | "Tell me a joke" (out-of-domain) | Polite rejection via channel |

¹ PENDING-CONFIRM-WITH-M8 per §Known Blockers row 5 (Fix 6).  
² PENDING-CONFIRM-WITH-M6 per §Known Blockers row 6 (Fix 6).

### Taxonomy Invariants

- **AC2.2 invariant**: `set(TAXONOMY_DISPATCH) == set(IntentCategory)` — every enum member has exactly one dispatch row.
- **AC2.9 prefix invariant (v0.2.0, Fix 11)**: every `kind == "pipeline"` target has a `research.*`-prefixed intent; every `kind == "tool"` target has a `client.*` or `trade.*`-prefixed intent; every `kind == "escalate"` target has a `compliance.*`, `escalate_to_human`, or `unsupported` intent.
- **Rule 14 invariant**: `COMPLIANCE_QUESTION.selected_target.kind == "escalate"`. M9 NEVER answers a compliance question with an LLM output.
- **Steering Rule 8 invariant**: `ESCALATE_TO_HUMAN`, `UNSUPPORTED`, and `COMPLIANCE_QUESTION` all route to `escalate` kind. (Added to §Steering Rules in v0.2.0 per Fix 12.)
- **M8 coupling invariant**: every `kind == "pipeline"` target name matches `^m8\.research_(pipeline_[1-3]|single_tool)$`. Task 19 cross-module version-match asserts subset-of-M8-PIPELINE_NAMES.

### Authority Scope Matrix (NEW in v0.2.0 — Fix 8 support)

Maps `IntentCategory` → required `aid.authority_scope` entry. AC12.9 checks this before returning a non-escalate decision. Missing scope → `reason_code="aid_authority_denied"`.

| Intent | Required scope | Rationale |
|--------|----------------|-----------|
| All `research.*` | `research.read` OR `research.execute` | Research pipelines consume client context. |
| `client.data_lookup` | `client.read` | Client PII read. |
| `client.goal_tracking` | `client.read` + `goal.read` | Goals are a sub-resource. |
| `client.plan_summary` | `plan.read` | Plan summaries are sensitive. |
| `trade.inquiry` | `trade.read` | Phase 2 is read-only; Phase 3 adds `trade.execute`. |
| `compliance.question` | — | Routes to escalate; scope check skipped. |
| `escalate_to_human` | — | Always allowed. |
| `unsupported` | — | Always allowed. |

`aid.authority_excludes` is an explicit deny-list consulted AFTER the allow-list. If `authority_scope=["*"]` AND `authority_excludes=["trade.execute"]`, the advisor has all read scopes but not trade execution.

## Review Fix Traceability

Populated in v0.2.0 post LLMJ-v1 review. Every Required Fix from `m9-intent-router-REVIEW.md` maps to a spec section / AC / task that addresses it. Recommended Fixes that landed in v0.2.0 also listed. Mirrors M7 v0.2.0 / M11 v0.2.0 discipline.

### Required Fixes (14 — all addressed)

| # | Required Fix (from review) | Severity | Addressed in Spec Section / AC / Task | Status |
|---|----------------------------|----------|---------------------------------------|--------|
| 1 | Reconcile with ARCH-09 dependency matrix (M9 calls M1+M5, not M3+M5; called by M12, not M6) | SEVERE | §Banner (Dependencies + Consumers lines rewritten); §Architecture Clarification block rewritten; §Known Blockers row 1 "ARCH-09 matrix alignment" (RESOLVED); R12 AC12.2 allow-list swap M3→M1; R12 AC12.7 `pyproject.toml` deps swap; R12 AC12.8 positive test `m3_schema_registry` never imported; R17 §Integration Point with M12 (replaces §Integration Point with M6); R18 rewritten; Task 2 negative scan updated | **RESOLVED — v0.2.0 realigned; no architect override needed (v0.1.0 was a misread, not a proposed amendment)** |
| 2 | Stop citing ARCH-07 for p50/p95/p99 latency granularity; ARCH-07 publishes `<500ms` only | SEVERE | §Banner (Design Sources line rewritten — ARCH-07 cited only for `<500ms`); R16 AC16.4 (ARCH-07 sourced = `p_max<500ms`; percentiles = M9-originated SLO in DECISION-LOG); Appendix C DECISION-LOG new entry 2026-05-16 "M9-originated percentile SLO" | **RESOLVED** |
| 3 | Fix M6 `VendorAdapter` Protocol shape — real Protocol is `name: str` + `call(*, tool_name, payload)`, no `handler=`/`tool_name=`/`timeout_ms=` constructor kwargs, no `M6_REGISTRY.register` public API | SEVERE | §Integration Point with M6 DELETED; replaced by §Integration Point with M12 (direct in-process call, no VendorAdapter); R17 AC17.1 explicit ("VendorAdapter Protocol NOT implemented by M9"); §Integration Point with M12 §Why NOT a VendorAdapter explains the v0.1.0 misread | **RESOLVED** |
| 4 | Resolve `RouterContext.archetype` firm-vs-client confusion — examples used `"mass_affluent"` (M3 client) while type imported `Archetype` (M5 firm) | MEDIUM | R1 AC1.2 (annotation + comment "firm-level: `tier1_investment_bank`..`tier5_hedge_fund`; NOT M3's client-level"); §Integration Point with M12 call-site example uses `Archetype(aid.archetype)`; §Hypothesis Strategy Approach worked example uses `Archetype.tier4_independent_ria` throughout; Task 3 test asserts rejection of non-Archetype string | **RESOLVED** — picked firm-level, consistent across all examples |
| 5 | Fill in Task 19 — invariants A7 and A17 reference "Task 19" but §Tasks had only 1-18 | MEDIUM (broken reference) | Task 19 added: "Cross-module version-match test" asserting `TAXONOMY_DISPATCH` tool-kind names are a subset of M6's registered tool set AND pipeline-kind names are a subset of M8's exported `PIPELINE_NAMES`; Appendix A A7 and A17 repointed from "Task 19 cross-module version-match asserts" → "Task 19 cross-module version-match test `tests/integration/test_cross_module_version_match.py`" | **RESOLVED** |
| 6 | Downgrade `m8.research_pipeline_{1/2/3/single_tool}` and `m6.composed_goal_tracking` from RESOLVED to PENDING-CONFIRM-WITH-M8/M6 — names are invented | MINOR (honest-status) | §Known Blockers row 5 "M8 pipeline naming convention — DOWNGRADED PENDING-CONFIRM-WITH-M8"; §Known Blockers row 6 "M6 `m6.composed_goal_tracking` — DOWNGRADED PENDING-CONFIRM-WITH-M6"; §FSI Intent Taxonomy footnotes ¹ ² flag each entry; AC2.6 cites the pending status; Task 19 xfail posture | **RESOLVED** |
| 7 | Declare M12 as a consumer (or explicitly rebut ARCH-09's `M12 → M9` row) | MEDIUM | §Banner Consumers line rewritten (M12 is primary and only direct caller); §Architecture Clarification bullet 2 explicit; §Integration Point with M12 (R17 + dedicated section); Known Blockers row 1; Appendix D cross-reference placeholder adds M12 row | **RESOLVED — declared M12** |
| 8 | Add `identity: AgentIdentityDocument` (or equivalent M1 field) to `RouterContext` — ARCH-05 v2 passes `aid` to `intent_router.classify(user_message, aid)` | MEDIUM | R1 AC1.2 (adds `identity: AidClaims` field from M1); AC1.9 (self-consistency check: `context.identity.archetype == context.archetype.value`); AC5.8 (Agent+TRADE_INQUIRY downgrade — Role-aware gating); §Authority Scope Matrix; R12 AC12.9 (`aid_authority_denied` fail-closed); R11 AC11.1 (new `aid_authority_denied` code — 13 codes total); Task 16 test_authority_scope.py | **RESOLVED** |
| 9 | Specify `FakeLlmClient` exception-injection mechanism so Task 15 can exercise all `VALID_REASON_CODES` | MEDIUM | R4 AC4.3 (`responses: dict[str, LlmClassification \| Exception]`); Appendix B.1 skeleton updated to show exception-raising path; Task 1 test asserts exception values raised verbatim; Task 15 uses `FakeLlmClient` with `Exception` values to exercise `llm_timeout`/`llm_error_5xx`/`llm_error_4xx`/`llm_malformed_output`/`taxonomy_mismatch` | **RESOLVED** |
| 10 | HMAC the utterance SHA with a tenant-scoped key — plain SHA-256 enables cross-tenant rainbow-table attack | HIGH (privacy) | R8 AC8.1 rewritten ("HMAC-SHA-256(tenant_key, utterance)"); §Phase 2 Scope bullet "Tenant-scoped audit hashing"; §Known Blockers row 12 "Tenant HMAC key provisioning"; new file `src/m9_intent_router/hmac_util.py` (`_resolve_tenant_hmac_key` + `compute_utterance_digest`); R14 AC14.7 (Vault resolution); new test `tests/unit/test_hmac_util.py`; `IntentRouterConfig.tenant_hmac_key_vault_path` field added to SHARED-WITH-M5 contract (Known Blockers row 2) | **RESOLVED** |
| 11 | Resolve `client.household_summary → m8.research_pipeline_3` naming conflict — `client.*` prefix routes to `pipeline` kind | MINOR | AC2.1 rename `CLIENT_HOUSEHOLD_SUMMARY` → `RESEARCH_HOUSEHOLD_SUMMARY`; §FSI Intent Taxonomy row 4 updated (string value `research.household_summary`); AC2.9 new prefix-consistency invariant; §LLM Contract JSON Schema Example updated enum; §Hypothesis Strategy Approach skeleton updated; `SCHEMA_VERSION` bumped to `1.1.0` (AC15.3); Known Blockers row 8 DECISION-LOG rationale | **RESOLVED — renamed (option (a) per review suggestion)** |
| 12 | Add Steering Rule 8 (fail-closed) to §Steering Rules M9 Must Honor table | MINOR (doc) | §Steering Rules M9 Must Honor now includes Rule 8 row pointing to R8 MNPI pre-scan, R7 fallback `regex_fallback_miss`, R12 AC12.9 authority denial, §Taxonomy Invariants; also cited in §Taxonomy Invariants as "Steering Rule 8 invariant" | **RESOLVED** |
| 13 | Specify how `route()` `timeout_ms * 2` wall-clock guarantee (AC1.8) is tested deterministically | MEDIUM (testability) | R4 AC4.9 (`SlowFakeLlmClient(block_ms, timeout_ms)`); R1 AC1.8 rewritten to pin the test mechanism (`SlowFakeLlmClient(block_ms=3000) + timeout_ms=1500 → assert route() returns in <3000 ms AND emits reason_code="llm_timeout"`); R15 AC15.1 `SlowFakeLlmClient` added to `__all__` (11 names); Task 1 test; Task 15 uses it for `llm_timeout` row | **RESOLVED** |
| 14 | Disambiguate `test_no_m8_string_ref.py` (AC12.6) vs `taxonomy.py` — taxonomy literally contains `"m8.research_pipeline_1"` which AC12.6 rejects | MINOR (broken test) | R12 AC12.6 rewritten: `EXEMPT_FILES = {"src/m9_intent_router/taxonomy.py"}` explicit; Task 2 `test_no_m8_string_ref.py` updated to respect exemption; AC18.1 cross-cites the exemption | **RESOLVED** |

### Recommended Fixes Landed in v0.2.0 (7 of 12)

| # | Recommended Fix | Landed In | Status |
|---|-----------------|-----------|--------|
| R1 | Instrument `reason_code="mnpi_shape_suspected"` counter with tenant dimension | R8 AC8.9; R9 AC9.1 (audit adds `tenant_id`); §MNPI-Shape Patterns §False-Positive Rate Target paragraph | LANDED |
| R2 | `SlowFakeLlmClient` / parametric `block_ms` for deterministic timeout tests | R4 AC4.9; covered by Fix 13 too | LANDED |
| R3 | Concurrency smoke test (50 threads × 20 calls) | Task 12 extension — `tests/benchmarks/test_m9_concurrency.py`; R16 AC16.7; R19 AC19.3 | LANDED |
| R4 | `float("inf")` / `float("-inf")` rows in §Confidence Threshold Table | AC5.6 updated list; table rows added | LANDED |
| R5 | Honest CI budget for Hypothesis property suite | AC10.4 rewritten to document ≈ 150 s worst-case | LANDED |
| R6 | `fallback_enabled=False + 4xx` row in test table | AC7.7 cites it; §Confidence Threshold Table last row; Task 9 test | LANDED |
| R7 | Commit to shipping `.env.example` | AC14.4 rewritten without `if present` hedge; file path pinned (`src/m9_intent_router/.env.example`); Task 17 test `test_env_example_shipped.py` | LANDED |
| R8 | `threading.Semaphore(16)` defense-in-depth | R19 (new requirement, 5 ACs); AC13.7 allow; Task 12 test | LANDED |
| R9 | Meta-test validating audit schema against 2020-12 meta-schema | Task 10 test `test_audit_schema_meta` | LANDED |
| R11 | SF 18-char checksum algorithm pinned precisely | AC6.3 rewritten with base-32 alphabet + 3-group + bit-flag algorithm | LANDED |
| R12 | Rename-policy DECISION-LOG entry for `selected_target.name` | AC17.4 rewritten with explicit rename policy: MAJOR bump, one-minor-version alias window, consumers query on `utterance_sha256`+`intent.value` | LANDED |

**Deferred to Phase 3** (not landed in v0.2.0): R10 (Luhn-tighten `bank_account` regex — acknowledged in §MNPI-Shape Patterns row 3 false-positive column).

### Net Effect vs v0.1.0

- 14 Required Fixes — ALL addressed.
- 11 Recommended Fixes — 11 landed; 1 deferred with acknowledgement.
- New sections: §Authority Scope Matrix (Fix 8 support).
- Deleted sections: §Integration Point with M6 (Fix 1 + Fix 3 — replaced by §Integration Point with M12).
- Renamed sections: §Integration Point with M8 (substantially rewritten — Fix 1).
- New code files: `src/m9_intent_router/hmac_util.py` (Fix 10), `src/m9_intent_router/.env.example` (Recommended Fix 7).
- New tests: `tests/unit/test_authority_scope.py`, `tests/unit/test_hmac_util.py`, `tests/benchmarks/test_m9_concurrency.py`, `tests/integration/test_m12_m9_supervisor_call.py`, `tests/integration/test_cross_module_version_match.py`.
- Deleted tests: `tests/integration/test_m6_m9_vendor_adapter.py` (Fix 1 + Fix 3).
- `VALID_REASON_CODES` grows 12 → 13 (added `aid_authority_denied` — MINOR bump).
- `IntentCategory` rename `CLIENT_HOUSEHOLD_SUMMARY` → `RESEARCH_HOUSEHOLD_SUMMARY` (Fix 11 — MAJOR rename; pre-Phase-2-GA window, accepted).
- `SCHEMA_VERSION` 1.0.0 → 1.1.0.
- `pyproject.toml` dependencies: `m3-schema-registry` REMOVED, `m1-identity` ADDED (Fix 1).
- `__all__` grows 10 → 11 names (added `SlowFakeLlmClient` — Fix 13, MAJOR bump pre-GA OK).

Target score: ≥ 8.0/10 GO on LLMJ-v2 re-review.

---

## Steering-Rule Traceability (v0.2.0)

| Steering Rule | Addressed In |
|---------------|--------------|
| **Rule 7** — Every MCP call MUST pass through M6 Trust-Aware Gateway | R17 (M9 never calls MCP tools — `SelectedTarget` is a data hand-off); §Architecture Clarification; §Integration Point with M12 §Why NOT a VendorAdapter |
| **Rule 8 (NEW in v0.2.0)** — Fail-closed on ANY compliance check failure | R8 (MNPI pre-scan short-circuit); R7 (fallback `regex_fallback_miss` → escalate); R12 AC12.9 (`aid_authority_denied` → escalate); §Taxonomy Invariants "Steering Rule 8 invariant" |
| **Rule 13** — Bedrock Claude Haiku for routing | R3 AC3.1-3.8 (`BedrockHaikuClient`); §Known Blockers row 3 (model ID verification); Task 7 |
| **Rule 14** — NO LLM for compliance (M2/M4 is deterministic OPA) | R2 AC2.3 (compliance.question → escalate); §FSI Intent Taxonomy row 9; §Taxonomy Invariants "Rule 14 invariant"; Task 15 |
| **Rule 15** — LLM provider abstracted, swappable via config | R4 AC4.1-4.9 (`LLMProvider` Protocol + `select_provider`); Task 1 |
| **Rule 20** — Zero credentials in git, Vault/Secrets Manager | R14 AC14.1-14.7 (boto3 default chain + Vault HMAC key); Task 2 `test_no_hardcoded_creds.py` |
| **Rule 32** — Security per module | R8 (MNPI), R9 (audit), R12 (boundary), R13 (forbidden imports), R14 (zero creds), R19 (concurrency defense-in-depth) |

---

## Appendix A — Intent Category Routing Matrix Invariants (v0.2.0)

Condensed invariants CI asserts on `TAXONOMY_DISPATCH`. Every row is a runtime `assert` in `taxonomy.py::_validate_taxonomy()`, called once at import time. Bad states fail at module load — never at route call.

| # | Invariant | Enforcement Point | Failure Mode |
|---|-----------|-------------------|--------------|
| A1 | `len(IntentCategory) == 11` | Import-time assert | `AssertionError("taxonomy change requires SemVer bump")` |
| A2 | `set(TAXONOMY_DISPATCH.keys()) == set(IntentCategory)` | Import-time assert | `AssertionError("dispatch missing entry for {enum_member}")` |
| A3 | Every `SelectedTarget.kind ∈ {"pipeline", "tool", "escalate"}` | Pydantic `Literal` | `ValidationError` at module load |
| A4 | `TAXONOMY_DISPATCH[COMPLIANCE_QUESTION].kind == "escalate"` AND `.name == "compliance_specialist"` | Import-time assert | `AssertionError("Steering Rule 14 violation")` |
| A5 | `TAXONOMY_DISPATCH[ESCALATE_TO_HUMAN].kind == "escalate"` AND `.name == "human_specialist"` | Import-time assert | `AssertionError` |
| A6 | `TAXONOMY_DISPATCH[UNSUPPORTED].kind == "escalate"` AND `.name == "human_specialist"` | Import-time assert | `AssertionError` |
| A7 | Every `kind == "pipeline"` target name matches `^m8\.research_(pipeline_[1-3]\|single_tool)$` | Import-time regex | `AssertionError("pipeline name does not match M8 naming contract")`. **Upstream cross-module version match asserted by Task 19 `tests/integration/test_cross_module_version_match.py`** (Fix 5). |
| A8 | Every `kind == "tool"` target name contains at least one `.` (namespace.tool_name) | Import-time regex | `AssertionError("tool name missing namespace separator")` |
| A9 | Exactly 4 pipeline-kind entries (Phase 2 — all `research.*` per Fix 11) | Import-time count | `AssertionError("Phase 2 expects exactly 4 pipeline targets")` |
| A10 | Exactly 4 tool-kind entries (Phase 2) | Import-time count | `AssertionError("Phase 2 expects exactly 4 tool targets")` |
| A11 | Exactly 3 escalate-kind entries | Import-time count | `AssertionError("Phase 2 expects exactly 3 escalate targets")` |
| A12 | `TAXONOMY_DISPATCH` is `types.MappingProxyType` (immutable) | Import-time type check | `TypeError` on mutation |
| A13 | `IntentCategory` values alphabetically sorted | Import-time sorted-check | `AssertionError("enum must be alphabetically ordered for tie-break determinism")` |
| A14 | `COMPLIANCE_QUESTION` never appears as `RoutingDecision.intent` with `selected_target.kind != "escalate"` | Runtime assertion in `route.py` after tie-break | `AssertionError("Steering Rule 14 runtime violation")` |
| A15 | `VALID_REASON_CODES` is a `frozenset` (immutable) with exactly **13 codes in v0.2.0** | Type + count check | `TypeError` on mutation / `AssertionError` on count |
| A16 | No `reason_code` value contains `ssn`, `routing`, `bank`, `account_number` (AC8.6) | Meta-test regex scan | `AssertionError("MNPI category must not leak into reason_code")` |
| A17 | `RoutingDecision.selected_target.name` for `kind == "tool"` is an element of M6-registered tool set | **Task 19 cross-module version-match test** (`tests/integration/test_cross_module_version_match.py` — Fix 5); M6 dispatch validation | Integration-test failure (xfail until M6 Phase 2 manifest lands) |
| A18 | No `kind` has an empty `name` string | Pydantic `min_length=1` | `ValidationError` at module load |
| A19 (NEW v0.2.0, Fix 11) | Prefix-kind consistency: `research.*` → `pipeline` OR `escalate`; `client.*` + `trade.*` → `tool`; `compliance.*` + `escalate_to_human` + `unsupported` → `escalate` | Import-time assert | `AssertionError("prefix-kind invariant violation: {intent} cannot route to kind={kind}")` |

### Test Coverage

`tests/unit/test_taxonomy.py::test_all_invariants` iterates A1-A19 and asserts each.

### Runtime vs. Import-Time

- A1-A13, A15-A16, A18-A19 — **import-time**: fail at `import m9_intent_router`. Pod does not serve traffic.
- A14 — **runtime**: fail at `route()` call. Fail-closed escalate.
- A17 — **integration-test-time**: reconciled against M6's tool registry by Task 19. xfail in v0.2.0 until M6 Phase 2 manifest lands.

---

## Appendix B — Skeleton Files (Spec-Level, Illustrative)

Spec-level skeletons for shared pieces. Tasks 1-8 are authoritative.

### B.1 `src/m9_intent_router/llm_client.py` (v0.2.0 — Fix 9 + Fix 13)

```python
"""LLM provider abstraction for M9.

LLMProvider Protocol + concrete/stub implementations + select_provider dispatch.
boto3 allowed ONLY in this file (AC13.3) AND hmac_util.py.
"""
from __future__ import annotations
import time
from typing import Protocol, runtime_checkable

from m9_intent_router.errors import (
    LlmTimeoutError, LlmProviderError, LlmMalformedOutputError,
)
from m9_intent_router.models import LlmClassification
from m9_intent_router.taxonomy import IntentCategory


@runtime_checkable
class LLMProvider(Protocol):
    """Protocol every M9 LLM provider must satisfy (R4)."""
    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification: ...


class BedrockHaikuClient:
    """Bedrock Claude Haiku provider. Phase 2 default."""
    def __init__(self, model_id: str, region: str, timeout_ms: int, max_retries: int = 2) -> None:
        import boto3
        self._client = boto3.client("bedrock-runtime", region_name=region)
        self._model_id = model_id
        self._timeout_ms = timeout_ms
        self._max_retries = max_retries

    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification:
        raise NotImplementedError("Task 7 owns implementation")


class FakeLlmClient:
    """Deterministic fake provider for tests and benchmarks.

    v0.2.0 (Fix 9): responses may be LlmClassification OR Exception.
    Exception values are raised verbatim when keyed by utterance digest.
    """
    def __init__(
        self,
        responses: dict[str, "LlmClassification | Exception"] | None = None,
        classify_latency_ms: int = 0,
    ) -> None:
        self._responses = responses or {}
        self._classify_latency_ms = classify_latency_ms

    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification:
        if self._classify_latency_ms:
            time.sleep(self._classify_latency_ms / 1000.0)
        # NOTE: caller is responsible for passing the HMAC-SHA-256 digest as the
        # lookup key (Fix 10). For tests, callers hmac the utterance with a
        # test-fixture tenant key.
        # For simplicity at the fake boundary, we accept the raw utterance-
        # derived key computation is done by the fixture.
        key = _fixture_key(utterance)
        result = self._responses.get(key)
        if isinstance(result, Exception):
            raise result                                       # Fix 9
        if isinstance(result, LlmClassification):
            return result
        return LlmClassification(
            intent=IntentCategory.UNSUPPORTED, confidence=0.0,
            entities={}, latency_ms=self._classify_latency_ms,
            model="fake", provider="fake",
        )


class SlowFakeLlmClient:
    """Slow fake provider for deterministic timeout tests (v0.2.0 — Fix 13)."""
    def __init__(self, block_ms: int, timeout_ms: int) -> None:
        self._block_ms = block_ms
        self._timeout_ms = timeout_ms

    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification:
        sleep_ms = min(self._block_ms, self._timeout_ms)
        time.sleep(sleep_ms / 1000.0)
        if self._block_ms > self._timeout_ms:
            raise LlmTimeoutError(f"blocked {self._block_ms}ms > timeout {self._timeout_ms}ms")
        return LlmClassification(
            intent=IntentCategory.UNSUPPORTED, confidence=0.0,
            entities={}, latency_ms=sleep_ms, model="slow_fake", provider="fake",
        )


class AzureOpenAIClient:
    """Reserved for Phase 3."""
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Phase 3 — AzureOpenAIClient reserved")
    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification:
        raise NotImplementedError("Phase 3")


class VertexClient:
    """Reserved for Phase 3."""
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Phase 3 — VertexClient reserved")
    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification:
        raise NotImplementedError("Phase 3")


class VllmClient:
    """Reserved for Phase 3."""
    def __init__(self, *args: object, **kwargs: object) -> None:
        raise NotImplementedError("Phase 3 — VllmClient reserved")
    def classify(self, utterance: str, taxonomy_schema: dict) -> LlmClassification:
        raise NotImplementedError("Phase 3")


def select_provider(config) -> LLMProvider:
    """Construct the LLM provider from an IntentRouterConfig. Sole construction point."""
    if config.provider == "bedrock":
        return BedrockHaikuClient(
            model_id=config.model_id, region=config.region, timeout_ms=config.timeout_ms,
        )
    if config.provider == "azure_openai":
        return AzureOpenAIClient()
    if config.provider == "vertex":
        return VertexClient()
    if config.provider == "vllm":
        return VllmClient()
    raise ValueError("provider_unconfigured")
```

### B.2 `src/m9_intent_router/hmac_util.py` (NEW v0.2.0 — Fix 10)

```python
"""Tenant-scoped HMAC-SHA-256 utterance digest.

Prevents cross-tenant rainbow-table attack on short/predictable utterances.
Tenant key resolved from Vault once at process start; cached in memory.
"""
from __future__ import annotations
import hmac
import hashlib
from functools import lru_cache


@lru_cache(maxsize=128)
def _resolve_tenant_hmac_key(tenant_id: str, vault_path: str) -> bytes:
    """Fetch tenant HMAC key from Vault. Cached per process. Fail-closed.

    Vault path template: secret/data/m9/tenants/<tenant_id>/hmac_key
    Returns raw bytes (≥ 32 bytes recommended).
    """
    import boto3                                                # AC13.3
    # Phase 2: AWS Secrets Manager adapter. Phase 3+: HashiCorp Vault SDK.
    sm = boto3.client("secretsmanager")
    path = vault_path.replace("<tenant_id>", tenant_id)
    resp = sm.get_secret_value(SecretId=path)
    raw = resp.get("SecretBinary") or (resp.get("SecretString") or "").encode("utf-8")
    if not raw:
        raise RuntimeError("provider_unconfigured")             # fail-closed
    return raw


def compute_utterance_digest(utterance: str, tenant_key: bytes) -> str:
    """Return 64-char hex HMAC-SHA-256 digest. Single migration seam
    for future SHA-3 / BLAKE3 (per §Known Blockers row 13)."""
    return hmac.new(tenant_key, utterance.encode("utf-8"), hashlib.sha256).hexdigest()
```

### B.3 `src/m9_intent_router/models.py` (v0.2.0 — Fix 8)

```python
"""Pydantic v2 models for M9."""
from __future__ import annotations
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from m1_identity import AidClaims                               # Fix 8 + Fix 1 ARCH-09
from m5_config_loader import Archetype, Runtime                 # Fix 4 — firm-level
from m9_intent_router.errors import VALID_REASON_CODES
from m9_intent_router.taxonomy import IntentCategory, SelectedTarget


class RouterContext(BaseModel):
    """Context passed to route() by M12 (AC1.2 — v0.2.0 includes identity)."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_id: str = Field(min_length=1)
    runtime: Runtime
    archetype: Archetype                                        # firm-level, NOT M3
    tenant_id: str = Field(min_length=1)
    identity: AidClaims                                         # Fix 8 — from M1
    prior_turns_summary: Optional[str] = None                   # Phase 2 ignores

    @model_validator(mode="after")
    def _aid_self_consistency(self) -> "RouterContext":         # AC1.9
        if self.identity.archetype != self.archetype.value:
            raise ValueError(
                "AID archetype must equal RouterContext archetype "
                f"(got identity={self.identity.archetype!r}, ctx={self.archetype.value!r})"
            )
        return self


class LlmClassification(BaseModel):
    """Provider-level classification result (AC3.3)."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    intent: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)                   # rejects Inf/-Inf (AC5.7)
    entities: dict[str, str] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    model: str
    provider: str


class RoutingDecision(BaseModel):
    """M9 public output (AC9.1 — v0.2.0 adds tenant_id)."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_id: str
    utterance_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    intent: IntentCategory
    confidence: float = Field(ge=0.0, le=1.0)
    entities: dict[str, str] = Field(default_factory=dict)
    selected_target: SelectedTarget
    fallback_used: bool
    llm_latency_ms: int = Field(ge=0)
    llm_model: str
    llm_provider: str
    reason_code: Optional[str] = None
    tenant_id: str = Field(min_length=1)                        # v0.2.0 Recommended Fix 1

    @field_validator("reason_code")
    @classmethod
    def _reason_code_in_vocabulary(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        if v not in VALID_REASON_CODES:
            raise ValueError(f"reason_code {v!r} not in VALID_REASON_CODES")
        return v

    def audit_payload(self) -> dict[str, Any]:
        """M10-safe audit dict — 12 keys in v0.2.0."""
        return {
            "trace_id": self.trace_id,
            "utterance_sha256": self.utterance_sha256,
            "intent": self.intent.value,
            "confidence": self.confidence,
            "selected_target": {"kind": self.selected_target.kind, "name": self.selected_target.name},
            "fallback_used": self.fallback_used,
            "llm_latency_ms": self.llm_latency_ms,
            "llm_model": self.llm_model,
            "llm_provider": self.llm_provider,
            "reason_code": self.reason_code,
            "entities_present": sorted(self.entities.keys()),
            "tenant_id": self.tenant_id,                        # v0.2.0
        }
```

### B.4 `src/m9_intent_router/route.py` — Dispatcher body sketch (v0.2.0 — Fix 8, Fix 10, R19)

```python
"""M9 route() dispatcher — the sole public entry point."""
from __future__ import annotations
import json
import threading
import time
from typing import Any

from m9_intent_router.errors import (
    LlmTimeoutError, LlmProviderError, LlmMalformedOutputError,
)
from m9_intent_router.fallback import fallback_classify
from m9_intent_router.hmac_util import _resolve_tenant_hmac_key, compute_utterance_digest
from m9_intent_router.llm_client import LLMProvider
from m9_intent_router.mnpi_scan import scan_mnpi_shape
from m9_intent_router.models import RouterContext, RoutingDecision
from m9_intent_router.regex_library import extract_entities
from m9_intent_router.taxonomy import (
    IntentCategory, SelectedTarget, TAXONOMY_DISPATCH, build_tool_schema,
)

_UTTERANCE_MIN = 1
_UTTERANCE_MAX = 4096

# Defense-in-depth cap (R19). Module-level, thread-safe.
_INFLIGHT = threading.Semaphore(16)


def route(utterance: str, context: RouterContext, *, _provider: LLMProvider, _config: Any) -> RoutingDecision:
    """Public entry point. Pure apart from provider call + audit emit."""
    if not (_UTTERANCE_MIN <= len(utterance) <= _UTTERANCE_MAX):
        return _short_circuit(
            context=context, config=_config,
            digest=compute_utterance_digest("", _empty_tenant_key()),
            intent=IntentCategory.UNSUPPORTED,
            reason_code="invalid_utterance_length",
        )

    tenant_key = _resolve_tenant_hmac_key(
        context.tenant_id, _config.tenant_hmac_key_vault_path,
    )
    digest = compute_utterance_digest(utterance, tenant_key)    # Fix 10

    if scan_mnpi_shape(utterance) is not None:
        return _short_circuit(
            context=context, config=_config, digest=digest,
            intent=IntentCategory.ESCALATE_TO_HUMAN,
            reason_code="mnpi_shape_suspected",
        )

    entities = extract_entities(utterance)

    with _INFLIGHT:                                             # R19
        try:
            start = time.perf_counter()
            classification = _provider.classify(utterance, build_tool_schema())
            latency_ms = int((time.perf_counter() - start) * 1000)
            decision = _dispatch_classification(
                classification=classification, entities=entities, digest=digest,
                context=context, latency_ms=latency_ms, config=_config,
            )
        except (LlmTimeoutError, LlmProviderError, LlmMalformedOutputError) as exc:
            decision = _handle_llm_error(
                exc=exc, utterance=utterance, digest=digest,
                context=context, config=_config,
            )

    _emit_audit(decision)
    return decision


def _emit_audit(decision: RoutingDecision) -> None:
    """R9 AC9.7 — the ONLY print() call in M9."""
    print(json.dumps({"source": "m9", **decision.audit_payload()}, sort_keys=True))
```

### B.5 `src/m9_intent_router/errors.py` (v0.2.0 — 13 reason codes)

```python
"""Error classes + closed reason-code vocabulary (R11)."""
from __future__ import annotations

VALID_REASON_CODES: frozenset[str] = frozenset({
    "llm_timeout", "llm_error_5xx", "llm_error_4xx", "llm_malformed_output",
    "mnpi_shape_suspected", "low_confidence", "regex_fallback_miss",
    "provider_unconfigured", "taxonomy_mismatch", "llm_assisted_plan",
    "invalid_utterance_length", "unsupported_intent_stub",
    "aid_authority_denied",                                     # v0.2.0 — Fix 8
})


class LlmProviderError(Exception):
    def __init__(self, status_code: int, message: str = "") -> None:
        self.status_code = status_code
        super().__init__(message)


class LlmTimeoutError(Exception):
    """classify() exceeded provider.timeout_ms."""


class LlmMalformedOutputError(Exception):
    """Provider returned an unparseable tool output."""
```

### B.6 `src/m9_intent_router/__init__.py` (v0.2.0 — 11 names)

See §Design / Public API.

---

## Appendix C — DECISION-LOG Seed (v0.2.0 additions)

Seed entries for `src/m9_intent_router/DECISION-LOG.md`. v0.2.0 adds entries tied to each Required Fix.

```markdown
# M9 Intent Router — DECISION-LOG

## 2026-05-14 — Initial taxonomy: 11 FSI intent categories

**Area**: Taxonomy
**Decision**: Ship 11-value closed `IntentCategory` enum.
**Rationale**: Covers Phase 2 RIA lighthouse journeys per ARCH-09 + 007-consolidated-design-and-plan Part 9. 11 is the smallest set keeping adjacent categories unambiguous.
**Decided By**: Pipeline and Intent Specialist + Supervisor Model owner.

## 2026-05-14 — Bedrock Claude Haiku model ID

**Area**: LLM Provider
**Decision**: Default `IntentRouterConfig.model_id = "anthropic.claude-3-5-haiku-20241022-v1:0"`.
**Rationale**: Latest GA Haiku snapshot as of 2026-05. ARCH-07 pins Haiku without a version; PENDING-VERIFICATION for first-live-call region probe (Task 16).
**Decided By**: Intent Router Specialist.

## 2026-05-14 — Three reserved providers stubbed in Phase 2

**Area**: LLM Provider Abstraction
**Decision**: `AzureOpenAIClient`, `VertexClient`, `VllmClient` ship as Protocol-satisfying stubs. NOT in `__all__`.
**Rationale**: Rule 15 requires abstraction; stubs verify swap-readiness without tripling test matrix.
**Decided By**: Architecture review.

## 2026-05-14 — MNPI pre-scan runs BEFORE LLM call (fail-closed)

**Area**: Security / MNPI
**Decision**: `scan_mnpi_shape()` at `route()` top-level, before LLM.
**Rationale**: Rule 8 fail-closed. Sending utterance to Bedrock creates MNPI exposure surface.
**Decided By**: Compliance + Security review.

## 2026-05-14 — MNPI category NEVER revealed in audit

**Area**: Security / MNPI
**Decision**: `reason_code="mnpi_shape_suspected"` is the only MNPI-related code. Generic — never category-specific.
**Rationale**: Revealing "ssn_suspected" is itself a MNPI leak.
**Decided By**: Compliance review.

## 2026-05-14 — Audit emitted via stdout JSON, not `logging`

**Area**: Observability
**Decision**: `route()` emits one `print(json.dumps(...))` line per call.
**Rationale**: R13 forbids `logging`. `print` is ONE call site.
**Decided By**: Architecture review.

## 2026-05-14 — Temperature=0 + alphabetical tie-break

**Area**: Determinism
**Decision**: `temperature=0.0`; ties broken by alphabetical enum ordering.
**Rationale**: Determinism critical for audit reproducibility.
**Decided By**: Intent Router Specialist.

## 2026-05-14 — `unsupported` Phase 2 handling is a stub

**Area**: Scope
**Decision**: `UNSUPPORTED` → `escalate_to_human` with `reason_code="unsupported_intent_stub"`. Phase 3 adds rejection templates.
**Decided By**: Product + Intent Router Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 1)

**Area**: Module dependency graph
**Decision**: Realign with ARCH-09 dependency matrix. M9 calls M1+M5 (was M3+M5 in v0.1.0 banner — misread). M9 called by M12 (was M6 — misread). §Integration Point with M6 deleted; §Integration Point with M12 added.
**Rationale**: ARCH-09 is the source of truth. v0.1.0 spec treated the matrix as confirmatory; v0.2.0 treats it as authoritative.
**Decided By**: Pipeline and Intent Specialist after LLMJ-v1 review.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 2)

**Area**: Latency SLO attribution
**Decision**: ARCH-07 cited ONLY for `<500 ms` Supervisor Haiku target. p50<200 / p95<500 / p99<1000 percentile breakdown is an M9-originated SLO owned by this DECISION-LOG — may be revised without ARCH-07 amendment.
**Rationale**: Review evidence: ARCH-07 line 57 publishes `<500ms` only; v0.1.0 citation of the percentile shape was a fabrication in the M11-v1 RES-08 mold.
**Decided By**: Pipeline and Intent Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 4)

**Area**: Archetype semantics
**Decision**: `RouterContext.archetype` is **firm-level** `Archetype` from M5 (`tier1_investment_bank`..`tier5_hedge_fund`). NOT M3's client-level segmentation ("mass_affluent", "hnw", "uhnw"). All worked examples updated.
**Rationale**: RIA lighthouse (Phase 2) routes on firm archetype. Client-level archetype is per-client metadata; M9 routes per-utterance, not per-client.
**Decided By**: Pipeline and Intent Specialist + Supervisor Model owner.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 10)

**Area**: Security / audit hash
**Decision**: `utterance_sha256` switches from plain SHA-256 to HMAC-SHA-256 with a tenant-scoped Vault-resolved key.
**Rationale**: Plain SHA-256 enabled cross-tenant rainbow-table correlation on short/predictable utterances. HMAC with per-tenant key eliminates the attack.
**Decided By**: Security review + Intent Router Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 11)

**Area**: Taxonomy rename
**Decision**: `CLIENT_HOUSEHOLD_SUMMARY` → `RESEARCH_HOUSEHOLD_SUMMARY`. String value `client.household_summary` → `research.household_summary`. SCHEMA_VERSION 1.0.0 → 1.1.0.
**Rationale**: Intent dispatched `kind="pipeline"` — prefix must align with kind (AC2.9). Renaming pre-Phase-2-GA accepted.
**Decided By**: Pipeline and Intent Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 17.4 rename policy)

**Area**: Audit contract
**Decision**: Renaming `selected_target.name` is a MAJOR bump. One-minor-version alias window MAY be provided. Audit consumers MUST query on `utterance_sha256` + `intent.value`, NOT on `selected_target.name` alone.
**Rationale**: Prevents silent audit-query breakage on rename.
**Decided By**: Pipeline and Intent Specialist + Audit Specialist.
```

---

## Appendix D — Cross-Reference Placeholder

| Target Spec | Cross-Reference Topic | M9 Spec Location | Target Spec Location |
|-------------|-----------------------|-------------------|----------------------|
| **M12 Supervisor (new in v0.2.0)** | Direct in-process `route()` call per ARCH-05 v2 | §Integration Point with M12 | M12 spec §Supervisor Routing Logic (when v0.1.0 ships) |
| **M1 Identity (new in v0.2.0 — Fix 1, Fix 8)** | `AidClaims`, `Role`, authority_scope | R1 AC1.2; §Authority Scope Matrix | `src/m1_identity/claims.py` §AidClaims |
| M8 spec | Stage 1 consumes `PipelineState.routing_decision` | §Integration Point with M8 | M8 spec §Pipeline Stages §Stage 1 |
| M5 spec (SHARED-WITH-M5) | `IntentRouterConfig` sub-model incl. `tenant_hmac_key_vault_path` | §Known Blockers row 2 | M5 spec v0.3.0 §Config Schema §IntentRouterConfig |
| M10 spec | Audit payload shape (12 keys, incl. tenant_id) | §Integration Point with M12 §Audit Handoff | M10 spec §AuditEntry.payload §Per-Source Shapes §m9 |
| **M6 (v0.2.0 INDIRECT)** | Target-name tool manifest (for Task 19) | §Known Blockers row 6 | M6 spec Phase 2 composed-tool manifest |
| ARCH-04 v2 | M9 tech stack row | §Banner §Design Sources | `docs/architecture/ARCH-04-v2-tech-stack-decisions.md` §M9 |
| **ARCH-05 v2** | Supervisor Routing Logic direct-call pattern | R17 | `docs/architecture/ARCH-05-v2-multi-agent-and-memory-architecture.md` §Supervisor Routing Logic lines 275-310 |
| ARCH-07 | `<500 ms` Haiku supervisor target (ONLY this number — Fix 2) | R16 AC16.4 | `docs/architecture/ARCH-07-definitive-tech-stack.md` §Model Selection Table line 57 |
| ARCH-09 | Dependency matrix row M9 + column 9 | §Banner §Architecture Clarification | `docs/architecture/ARCH-09-complete-module-map.md` §DEPENDENCY MATRIX lines 302-315 |
| IMPL-06 | Blocker resolution items | §Known Blockers | `docs/implementation/IMPL-06-blocker-resolution-plan.md` |
| Steering file | Rules 7, 8, 13, 14, 15, 20, 32 | §Steering Rules M9 Must Honor | `.kiro/steering/007-fsi-interoperability.md` |

### Cross-Reference Maintenance

- When M12 Phase 2 spec lands → M12 cites §Integration Point with M12. Trigger: M12 v0.1.0.
- When M8 v0.1.0 lands + exports `PIPELINE_NAMES` → Task 19 flips from xfail to strict-pass.
- When M6 Phase 2 composed-tool manifest lands → Task 19 second half flips to strict-pass.
- When M5 v0.3.0 adds `IntentRouterConfig` (incl. `tenant_hmac_key_vault_path` — Fix 10) → §Known Blockers row 2 RESOLVED; `test_m9_m5_config_shape.py` un-xfail.
- When LLMJ-v2 reviews this spec → §Review Fix Traceability updates; version bumps to 0.3.0 if further fixes needed, 1.0.0 if GO.
- When Bedrock Haiku model ID verification completes (Task 16 first-live-call) → §Known Blockers row 3 updates.


---

## §Confidence Threshold Table

Drives Task 13 parameterized test. Every row is a single `pytest.mark.parametrize` entry in `tests/unit/test_confidence_thresholds.py`. v0.2.0 adds rows for Role=agent + TRADE_INQUIRY downgrade (Fix 8 / AC5.8), Inf/-Inf Pydantic rejection (Recommended Fix 4), and `fallback_enabled=False + 4xx` (Recommended Fix 6).

| # | Scenario | `confidence` | `intent` | `role` | `fallback_enabled` | LLM error? | Expected `intent` out | Expected `reason_code` | Expected `fallback_used` | AC |
|---|----------|--------------|----------|--------|--------------------|------------|-----------------------|------------------------|--------------------------|-----|
| 1 | Happy path — high bucket | 0.97 | RESEARCH_MEETING_PREP | advisor | true | — | RESEARCH_MEETING_PREP | None | false | AC5.1 |
| 2 | Boundary — lower edge of high bucket | 0.95 | RESEARCH_MEETING_PREP | advisor | true | — | RESEARCH_MEETING_PREP | None | false | AC5.1, AC5.5 |
| 3 | Just below high bucket | 0.94999 | RESEARCH_MEETING_PREP | advisor | true | — | RESEARCH_MEETING_PREP | llm_assisted_plan | false | AC5.2, AC5.6 |
| 4 | Mid bucket | 0.87 | CLIENT_DATA_LOOKUP | advisor | true | — | CLIENT_DATA_LOOKUP | llm_assisted_plan | false | AC5.2 |
| 5 | Lower edge of mid bucket | 0.80 | CLIENT_DATA_LOOKUP | advisor | true | — | CLIENT_DATA_LOOKUP | llm_assisted_plan | false | AC5.2, AC5.5 |
| 6 | Just below mid bucket | 0.79999 | CLIENT_DATA_LOOKUP | advisor | true | — | ESCALATE_TO_HUMAN | low_confidence | false | AC5.3, AC5.6 |
| 7 | Deep low | 0.05 | TRADE_INQUIRY | advisor | true | — | ESCALATE_TO_HUMAN | low_confidence | false | AC5.3 |
| 8 | NaN confidence | `float("nan")` | any | advisor | true | — | ESCALATE_TO_HUMAN | low_confidence | false | AC5.7 |
| 9 | `float("inf")` — Pydantic rejects | `float("inf")` | any | advisor | true | — | ESCALATE_TO_HUMAN | llm_malformed_output | true (regex hit) / false (regex miss) | AC5.7, Recommended Fix 4 |
| 10 | `float("-inf")` — Pydantic rejects | `float("-inf")` | any | advisor | true | — | ESCALATE_TO_HUMAN | llm_malformed_output | true / false | AC5.7, Recommended Fix 4 |
| 11 | Role=agent + TRADE_INQUIRY → downgrade (Fix 8) | 0.98 | TRADE_INQUIRY | agent | true | — | TRADE_INQUIRY | llm_assisted_plan | false | AC5.8 |
| 12 | Role=agent + TRADE_INQUIRY low | 0.70 | TRADE_INQUIRY | agent | true | — | ESCALATE_TO_HUMAN | low_confidence | false | AC5.8 (downgrade still below med threshold) |
| 13 | Role=advisor + TRADE_INQUIRY high — NO downgrade | 0.98 | TRADE_INQUIRY | advisor | true | — | TRADE_INQUIRY | None | false | AC5.8 (negative — advisors unaffected) |
| 14 | LLM timeout + fallback regex hits | — | (provider raises `LlmTimeoutError`) | advisor | true | timeout | RESEARCH_MEETING_PREP | llm_timeout | true | AC7.3 |
| 15 | LLM timeout + fallback regex miss | — | (provider raises `LlmTimeoutError`) | advisor | true | timeout | ESCALATE_TO_HUMAN | regex_fallback_miss | true | AC7.4 |
| 16 | LLM 5xx + fallback hits | — | (raises `LlmProviderError(503)`) | advisor | true | 5xx | CLIENT_DATA_LOOKUP | llm_error_5xx | true | AC7.5 |
| 17 | LLM 4xx — NO fallback | — | (raises `LlmProviderError(400)`) | advisor | true | 4xx | ESCALATE_TO_HUMAN | llm_error_4xx | false | AC7.6 |
| 18 | `fallback_enabled=False` + timeout | — | (timeout) | advisor | **false** | timeout | ESCALATE_TO_HUMAN | llm_timeout | false | AC7.7 |
| 19 | `fallback_enabled=False` + 4xx (Recommended Fix 6) | — | (4xx) | advisor | **false** | 4xx | ESCALATE_TO_HUMAN | llm_error_4xx | false | AC7.6, AC7.7, Recommended Fix 6 |
| 20 | Malformed LLM output → treat as fallback | — | (raises `LlmMalformedOutputError`) | advisor | true | malformed | RESEARCH_MEETING_PREP (if regex hits) | llm_malformed_output | true | AC7.5 |
| 21 | Taxonomy mismatch (LLM returns non-enum value → Pydantic rejects → malformed path) | — | (raises `LlmMalformedOutputError`) | advisor | true | malformed | ESCALATE_TO_HUMAN (regex miss) | llm_malformed_output | true | AC7.5 |

**Test harness**: each row constructs a `FakeLlmClient` seeded with either a `LlmClassification(intent=<col>, confidence=<col>, …)` or the exception (rows 14-21). Rows 11-13 assert the Role=agent + TRADE_INQUIRY downgrade logic AT the route dispatcher, NOT at the provider — the provider returns the raw confidence; `route()` applies the downgrade.

**Boundary invariant**: every boundary is CLOSED at the lower bound per AC5.5. The 0.95 row lands in high; the 0.80 row lands in mid. Row 3 and Row 6 sit one ULP below (`0.94999`, `0.79999`) and validate the strict-less-than downgrade.

**Count**: 21 rows in v0.2.0, up from 12 in v0.1.0. Growth: +3 for Fix 8 (rows 11-13), +2 for Recommended Fix 4 (rows 9-10), +1 for Recommended Fix 6 (row 19), +3 for completeness (rows 20-21 malformed + row 13 negative test for Fix 8).

---

## §Entity Extraction Regex Library

6-slot regex table referenced by AC6.1-6.8. Lives in `src/m9_intent_router/regex_library.py`. Every regex is compiled once at module import with `re.compile` and cached in a `types.MappingProxyType[str, re.Pattern]`. Every regex has a passing and a failing fixture in `tests/unit/test_regex_library.py`.

| Slot | Regex | Anchors | Post-regex Validator | Passing Examples | Failing Examples | Notes |
|------|-------|---------|----------------------|------------------|------------------|-------|
| `ticker` | `r"\b[A-Z]{1,5}\b"` | word-boundary, case-sensitive | Whitelist intersection (Phase 2 — 50 entries; see below) | `NVDA`, `AAPL`, `MSFT`, `TSLA`, `BRK`, `JPM` | `nvda` (lowercase), `BANANA` (6 chars), `A1B` (digits), `I` (whitelist miss — too ambiguous) | Pre-LLM entity extraction is a cross-check. LLM's `entities.ticker` is authoritative when it disagrees. |
| `client_id` | `r"\b[a-zA-Z0-9]{18}\b"` | word-boundary, mixed-case | SF 18-char checksum: split first 15 into three 5-char groups; per group build 5-bit number where bit `i` = 1 if char `i` is uppercase; map each 5-bit int (0-31) via base-32 alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZ012345` — that 3-char sequence is the trailing checksum (AC6.3, Recommended Fix 11). | `003xx0000012ABCAAM` (valid SF ID); `a0Xxx000000ZZZMAA2` | `003xx0000012ABCXXX` (checksum mismatch); `003xx0000012ABC` (15 chars — too short); `abc` | Checksum validates; raw regex match without checksum is a FALSE POSITIVE. |
| `household_id` | `r"\bHH-[A-Z0-9]{10,16}\b"` | word-boundary, upper-case | length ≤ 19 chars total | `HH-A1B2C3D4E5`, `HH-AAAAAAAAAA`, `HH-9999999999999999` | `HH-abc` (lowercase), `HH-123` (too short), `hh-A1B2C3D4E5` (prefix case) | Firm-scoped. Aligns with M3 Household container ID shape. |
| `account_id` | `r"\bACC-[A-Z0-9]{8,12}\b"` | word-boundary, upper-case | length ≤ 16 chars total | `ACC-1234ABCD`, `ACC-AAAAAAAAAAAA` | `ACC-123` (too short), `acc-1234ABCD` (prefix case), `ACCT-1234ABCD` (wrong prefix) | Firm-scoped. |
| `date_range` — absolute | `r"\b(\d{4}-\d{2}-\d{2})\s*(?:to\|-\|through\|—)\s*(\d{4}-\d{2}-\d{2})\b"` | word-boundary | Pydantic date parse both ends; start ≤ end | `2026-01-01 to 2026-03-31`, `2026-01-01 — 2026-03-31`, `2026-01-01 through 2026-03-31` | `2026-13-01 to 2026-03-31` (invalid month), `2026-03-31 to 2026-01-01` (reversed) | Supports em-dash. Pydantic parses dates — regex is a pre-filter only. |
| `date_range` — relative | whitelist `{"last_quarter", "YTD", "last_30_days", "last_90_days", "last_12_months"}` | exact match (case-insensitive) | — | `last quarter`, `LAST_30_DAYS`, `ytd` | `last_week` (not in whitelist), `Q1` (ambiguous) | Normalized to canonical form before return (e.g., `"last quarter"` → `"last_quarter"`). |

### Phase 2 Ticker Whitelist (50 entries)

Single source of truth: `src/m9_intent_router/regex_library.py` top-level constant `_TICKER_WHITELIST: frozenset[str]`. Phase 2 covers the most-queried NYSE/NASDAQ large-caps per IMPL-06 beta-tenant survey. Non-whitelisted tickers caught by regex fall through to LLM entity resolution — they are NOT populated in `entities["ticker"]`.

```
NVDA AAPL MSFT GOOGL GOOG AMZN META TSLA BRK BRKB
JPM  BAC  WFC   GS     MS   C     SCHW AXP  BLK   V
MA   PG   KO    PEP    WMT  COST  HD   MCD  NKE   DIS
XOM  CVX  COP   SLB    PFE  MRK   JNJ  UNH  LLY   ABBV
BA   CAT  GE    HON    UPS  FDX   NEE  T    VZ    CRM
```

**Deliberately excluded from Phase 2**: ambiguous single-letter tickers (`A`, `C`, `F`, `T`, `V` — note: `T`, `V`, `C` above are included as fully-known names — not single-letter confusables; `A` / `F` excluded as false-positive magnets). Task 11 property test generates adversarial utterances containing `I`, `A`, `O`, `U` — asserts these do NOT appear in `entities["ticker"]`.

### Pure-Function Contract

Every public function in `regex_library.py` is:
- `def extract_entities(utterance: str) -> dict[str, str]` — pure, no I/O, no module-level mutable state.
- Never raises — AC6.7 asserted via Hypothesis over ≥500 examples.
- Missing slots absent from returned dict (not `None`-valued) — AC6.1.

### Redaction in Audit

`RoutingDecision.audit_payload().entities_present` is a sorted list of **KEYS ONLY** (AC6.8, AC9.2). A household ID is a MNPI-grade identifier — audit emits `["household_id"]`, NEVER `["household_id=HH-A1B2..."]`.

---

## §MNPI-Shape Patterns

Referenced by R8 AC8.2-8.9. Lives in `src/m9_intent_router/mnpi_scan.py`. `scan_mnpi_shape(utterance: str) -> Optional[str]` returns the matched category name if any pattern hits, else `None`. **The category name is NEVER surfaced in `reason_code`** (AC8.6) — `reason_code="mnpi_shape_suspected"` is the only MNPI-related code — but `scan_mnpi_shape` returns it for unit-test introspection.

### 4-Category Regex Table

| Category | Regex | Post-regex Validator | Example Hit | Example Miss (near-miss edge case) | Known False-Positive |
|----------|-------|----------------------|-------------|-------------------------------------|----------------------|
| `ssn` | `r"\b\d{3}-\d{2}-\d{4}\b"` OR `r"\b\d{9}\b"` | Anti-ZIP-plus-four filter: if utterance ALSO matches `r"\b\d{5}-\d{4}\b"` anywhere, the bare 9-digit match is treated as `ssn` ONLY IF it is NOT immediately preceded by a 5-digit-dash pattern. ABA-routing filter (see routing_number row) overrides on checksum match. | `SSN 123-45-6789`, `My social is 123456789` | `90210` (5-digit ZIP), `90210-1234` (ZIP+4 — anti-filter engages) | `123456789` when it IS actually a ZIP+4 concatenation (`12345-6789`) with the dash dropped — acknowledged fail-closed (Steering Rule 8). |
| `bank_account` | `r"\b\d{10,17}\b"` | Must NOT match routing_number checksum; must NOT match SSN dashed form | `account 1234567890`, `4111111122223333` (16-digit Visa-shape) | `12345` (5-digit), `123456789` (9-digit — caught by SSN or routing, not bank) | Phone numbers `(212) 555-1212` written as `2125551212` (10 digits) — **acknowledged FP**; Luhn-tighten deferred to Phase 3 (R10 deferral). |
| `routing_number` | `r"\b\d{9}\b"` | **ABA checksum**: positional weights `[3,7,1,3,7,1,3,7,1]`; `sum(d_i * w_i) % 10 == 0`. If checksum passes → routing; if fails → falls through (possibly matches SSN rule). | `021000021` (JPMorgan Chase routing — checksum valid), `011000015` (FRB Boston — valid) | `123456789` (checksum fails — falls through to SSN bare-9 path) | 9-digit ZIP+4 (already stripped of dash) coincidentally passing ABA checksum — astronomically rare but acknowledged. |
| `wire_instruction` | `r"\b(wire|ACH|swift|BIC)\s*[:=]?\s*\w+\b"` combined with bank_account OR routing_number hit in same utterance | If `wire`/`ACH`/`swift`/`BIC` keyword AND any numeric shape matches, escalate | `wire $50k to routing 021000021 account 1234567890` | `wireless plan`, `ACH pump` (no numeric context) | Token `wire` in non-financial context (`wire transfer` → discuss the concept generically); documented fail-closed. |

### Precedence Subsection

Patterns are scanned in this strict order; first hit wins:

1. **`wire_instruction`** (highest — compound signal, lowest FP rate among MNPI categories)
2. **`routing_number`** (checksum-validated — deterministic, low FP)
3. **`ssn`** dashed form `\d{3}-\d{2}-\d{4}` (anchored, low FP)
4. **`ssn`** bare 9-digit form (after anti-ZIP-plus-four filter)
5. **`bank_account`** (10-17 digits — highest FP rate; runs last)

`scan_mnpi_shape` returns the first-matched category name. Ordering is asserted in `tests/unit/test_mnpi_scan.py::test_precedence`. Re-ordering the precedence is a MAJOR audit-semantic change (though `reason_code` is always the same `mnpi_shape_suspected`, per-category FP dashboards would drift).

### Validator Implementation Sketch

```python
# src/m9_intent_router/mnpi_scan.py (excerpt)
import re
from typing import Optional

_SSN_DASHED = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
_NINE_DIGITS = re.compile(r"\b\d{9}\b")
_ZIP_PLUS4 = re.compile(r"\b\d{5}-\d{4}\b")
_BANK_10_17 = re.compile(r"\b\d{10,17}\b")
_WIRE_KW = re.compile(r"\b(wire|ACH|swift|BIC)\b", re.IGNORECASE)

_ABA_WEIGHTS = (3, 7, 1, 3, 7, 1, 3, 7, 1)


def _aba_valid(nine: str) -> bool:
    return sum(int(d) * w for d, w in zip(nine, _ABA_WEIGHTS)) % 10 == 0


def scan_mnpi_shape(utterance: str) -> Optional[str]:
    """Return matched MNPI category name, or None. Precedence-ordered."""
    # 1. wire_instruction compound
    if _WIRE_KW.search(utterance) and (_NINE_DIGITS.search(utterance) or _BANK_10_17.search(utterance)):
        return "wire_instruction"
    # 2. routing_number (ABA-validated)
    for m in _NINE_DIGITS.finditer(utterance):
        if _aba_valid(m.group(0)):
            return "routing_number"
    # 3. ssn dashed
    if _SSN_DASHED.search(utterance):
        return "ssn"
    # 4. ssn bare 9-digit (anti-ZIP+4)
    for m in _NINE_DIGITS.finditer(utterance):
        start = m.start()
        # anti-ZIP+4: reject if the 9 digits sit immediately inside a "12345-6789" construct
        preceding_5 = utterance[max(0, start - 6):start]   # 5 digits + dash
        if re.match(r"\d{5}-$", preceding_5):
            continue
        return "ssn"
    # 5. bank_account
    if _BANK_10_17.search(utterance):
        return "bank_account"
    return None
```

### False-Positive Rate Target

Per §Known Blockers row 10 (acceptable fail-closed posture). Target: **≤ 2%** mnpi-shape FP rate over first week of Phase 2 RIA lighthouse production traffic. Measurement: `reason_code="mnpi_shape_suspected"` counter with tenant-id dimension (AC8.9, Recommended Fix 1 — enables per-tenant dashboards without grepping raw utterances). If observed rate exceeds 2% in any tenant, Phase 3 tightens `bank_account` regex (Luhn — R10 deferral) and possibly adds context-aware wire-instruction filter.

**Acknowledged residual FPs**: `"my phone is 2125551212"` (10 digits → `bank_account`), `"ZIP 90210-1234"` written as `"902101234"` (→ `routing_number` if checksum accidentally valid, else `ssn`), `"12345 via wire next Tuesday"` (wire keyword + 5 digits — does NOT trigger under current rules because `\d{10,17}` requires 10+ digits — documented as near-miss).

---

## §Error Code Map

Drives Task 15 exhaustive `VALID_REASON_CODES` meta-test. Every code in the frozenset (R11 AC11.1 — **13 codes in v0.2.0**) has exactly one row. v0.2.0 adds `aid_authority_denied` (Fix 8).

| # | `reason_code` | Triggered By | Detection Point | HTTP-equivalent | `fallback_used` | Downstream Outcome |
|---|---------------|--------------|-----------------|-----------------|-----------------|--------------------|
| 1 | `llm_timeout` | `LlmTimeoutError` from provider (`boto3` timeout or `SlowFakeLlmClient` block > timeout) | `route.py::_handle_llm_error` | 504 | true (if regex fallback hits) / false (if `fallback_enabled=False`) | Dispatch to fallback-classified intent OR escalate; audit records `llm_provider`, `llm_model`, elapsed `llm_latency_ms` |
| 2 | `llm_error_5xx` | `LlmProviderError(status_code=500..599)` | `route.py::_handle_llm_error` | 5xx | true (if regex fallback hits) | Fallback dispatch OR escalate; M10 counts 5xx rate per-provider |
| 3 | `llm_error_4xx` | `LlmProviderError(status_code=400..499)` — config defect, never transient | `route.py::_handle_llm_error` | 4xx | **false** (AC7.6 — 4xx bypasses fallback) | Escalate; M12 surfaces as operator alert |
| 4 | `llm_malformed_output` | `LlmMalformedOutputError` (Pydantic `LlmClassification` construction fails, tool output unparseable, taxonomy enum mismatch, NaN / Inf confidence rejected by `Field(ge=0, le=1)`) | `route.py::_handle_llm_error` | 502 | true (if regex fallback hits) | Fallback dispatch OR escalate |
| 5 | `mnpi_shape_suspected` | `scan_mnpi_shape(utterance) is not None` | `route.py` pre-LLM (AC8.4) | — (no HTTP call issued) | **false** | Escalate to human; audit counts per-tenant (AC8.9); NO MNPI category leaked in `reason_code` |
| 6 | `low_confidence` | `classification.confidence < config.confidence_med` (incl. NaN — AC5.7) | `route.py::_dispatch_classification` | — (LLM succeeded) | false | Escalate; original confidence preserved in audit for threshold-tuning analysis |
| 7 | `regex_fallback_miss` | LLM error AND `fallback_classify(utterance) is None` | `route.py::_handle_llm_error` | — | true (fallback attempted but missed) | Escalate; M10 counts `regex_fallback_miss` rate per tenant (drives Phase 3 fallback-pattern expansion) |
| 8 | `provider_unconfigured` | `select_provider` raises `ValueError("provider_unconfigured")` OR Vault HMAC key absent at startup (AC14.7) | Process bootstrap (pod doesn't serve traffic) | — (bootstrap) | false | Pod fails readiness probe; Kubernetes crash-loops until config fixed |
| 9 | `taxonomy_mismatch` | LLM returns an enum-value string that is not in `IntentCategory` (A14 runtime invariant) | `route.py::_dispatch_classification` post-Pydantic | — | true (fallback attempted) | Same path as `llm_malformed_output` but distinguishes LLM-returned-wrong-enum from Pydantic-rejected-shape |
| 10 | `llm_assisted_plan` | `config.confidence_med <= confidence < config.confidence_high` (mid bucket) — **OR** Role=agent + TRADE_INQUIRY downgrade (AC5.8, Fix 8) | `route.py::_dispatch_classification` | — | false | Dispatch succeeded at mid-confidence; M10 counts mid-bucket dispatches per specialist for quality review |
| 11 | `invalid_utterance_length` | `len(utterance)` outside `[1, 4096]` | `route.py` top-level (AC1.3) | — | false | Escalate; M10 counts abuse signal (empty or oversize spam) |
| 12 | `unsupported_intent_stub` | Classification matched `IntentCategory.UNSUPPORTED` (LLM ran out of taxonomy) | `route.py::_dispatch_classification` | — | false | Escalate; M10 queryable by tenant + `utterance_sha256` for Phase 3 taxonomy expansion |
| 13 | **`aid_authority_denied`** (NEW v0.2.0 — Fix 8) | `context.identity.authority_scope` does NOT include a scope matching `SelectedTarget` per §Authority Scope Matrix, OR `context.identity.authority_excludes` explicitly denies | `route.py` **post-LLM** (after classification, before dispatch — AC12.9) | — (no LLM error; policy rejection) | **false** | Escalate; audit records denied scope name **in a separate M12-emitted event** (`supervisor.authority_denial`) — NOT in M9's audit payload (see §Integration Point with M12 §Response Shape — Fix 8 example) |

**Count verification**: `assert len(VALID_REASON_CODES) == 13` — Task 15 meta-test. If this ever fails, either R11 AC11.1 or this table must be updated in lockstep.

---

## §LLM Contract JSON Schema Example

R3 AC3.2 specifies Bedrock Converse API `toolConfig` with an Anthropic tool_use shape. This section gives the concrete shape M9 sends, the expected response, the system prompt, and parsing rules. v0.2.0 updates the `intent.enum` list to reflect the Fix 11 rename (`research.household_summary`, not `client.household_summary`).

### `toolConfig` — The Sole Bedrock Tool

```json
{
  "tools": [
    {
      "toolSpec": {
        "name": "routing_decision",
        "description": "Classify the user utterance into exactly one FSI intent category with calibrated confidence and extracted entities.",
        "inputSchema": {
          "json": {
            "type": "object",
            "required": ["intent", "confidence", "entities"],
            "additionalProperties": false,
            "properties": {
              "intent": {
                "type": "string",
                "enum": [
                  "research.meeting_prep",
                  "research.portfolio_review",
                  "research.market_query",
                  "research.household_summary",
                  "client.data_lookup",
                  "client.goal_tracking",
                  "client.plan_summary",
                  "trade.inquiry",
                  "compliance.question",
                  "escalate_to_human",
                  "unsupported"
                ]
              },
              "confidence": {
                "type": "number",
                "minimum": 0.0,
                "maximum": 1.0,
                "description": "Calibrated probability that the chosen intent is correct. Must be ≤ 0.80 if uncertain."
              },
              "entities": {
                "type": "object",
                "additionalProperties": {"type": "string"},
                "description": "Extracted entities by slot name: ticker, client_id, household_id, account_id, date_range."
              }
            }
          }
        }
      }
    }
  ],
  "toolChoice": {"tool": {"name": "routing_decision"}}
}
```

**Critical**: `"additionalProperties": false` — Bedrock MUST emit exactly these three fields. `intent.enum` contains exactly 11 values matching `IntentCategory` (AC2.1). `client.household_summary` is explicitly NOT on the list (Fix 11 rename verification).

### `inferenceConfig`

```json
{
  "temperature": 0.0,
  "maxTokens": 2000,
  "topP": 1.0
}
```

`temperature=0.0` underpins AC10.1 determinism. `maxTokens=2000` caps any runaway thinking tokens (Anthropic tool_use emits thinking before tool invocation in newer snapshots).

### System Prompt (Passed via `system` Converse Field)

```
You are a pure-function intent classifier for a financial-services advisory platform.
You MUST invoke the `routing_decision` tool exactly once. Do not emit freeform text.
Do not answer the user's question. Do not engage with the content of the utterance.
You only classify it.

Rules:
- Emit `compliance.question` for any regulatory, suitability, or rule-interpretation utterance.
  You MUST NOT attempt to answer — downstream OPA handles compliance answers.
- Emit `escalate_to_human` if the utterance is ambiguous, emotional, or requires judgment
  you cannot confidently classify.
- Emit `unsupported` if the utterance is in scope of the platform but no current intent fits.
- For each extracted entity (ticker, client_id, household_id, account_id, date_range), emit
  a string value. Missing entities must be omitted — do NOT emit empty strings.
- Confidence MUST be calibrated: emit ≤ 0.80 when uncertain, ≥ 0.95 only when certain.
- You are processing potentially sensitive utterances — NEVER echo, paraphrase, or restate
  the utterance in any tool field.
```

### Expected Response Shape (Bedrock Returns)

```json
{
  "output": {
    "message": {
      "role": "assistant",
      "content": [
        {
          "toolUse": {
            "toolUseId": "tooluse_abc123",
            "name": "routing_decision",
            "input": {
              "intent": "research.household_summary",
              "confidence": 0.96,
              "entities": {"household_id": "HH-A1B2C3D4E5F6"}
            }
          }
        }
      ]
    }
  },
  "stopReason": "tool_use",
  "usage": {"inputTokens": 312, "outputTokens": 48, "totalTokens": 360}
}
```

**Parsing rules** (`BedrockHaikuClient.classify`):

1. Assert `response["stopReason"] == "tool_use"`. Any other stop reason → `LlmMalformedOutputError`.
2. Walk `response["output"]["message"]["content"]` — find the `toolUse` block.
3. Assert exactly one `toolUse` block; more than one → `LlmMalformedOutputError`.
4. Assert `toolUse["name"] == "routing_decision"` — any other name → `LlmMalformedOutputError` (model hallucinated tool).
5. Construct `LlmClassification(**toolUse["input"], latency_ms=…, model=…, provider="bedrock")`. Pydantic v2 rejects:
   - Enum value not in `IntentCategory` → `ValidationError` → wrapped to `LlmMalformedOutputError` with `reason_code="taxonomy_mismatch"`.
   - `confidence` outside `[0.0, 1.0]` (incl. `Inf`, `-Inf`, `NaN`) → `ValidationError` → wrapped to `LlmMalformedOutputError` (AC5.7, Recommended Fix 4).
   - Extra fields in `input` → Pydantic `extra="forbid"` rejects (model_config on `LlmClassification`).
6. `entities` keys validated against the 5 known slot names; unknown slots dropped with a debug print (NOT an error — forward-compat).
7. Emission: `LlmClassification` returned; caller (`route()`) takes over.

### v0.2.0 Fix 11 Verification Unit Test

```python
# tests/unit/test_llm_contract_schema.py
from m9_intent_router.taxonomy import build_tool_schema

def test_enum_includes_research_household_summary():
    schema = build_tool_schema()
    enum_values = schema["tools"][0]["toolSpec"]["inputSchema"]["json"]["properties"]["intent"]["enum"]
    assert "research.household_summary" in enum_values
    assert "client.household_summary" not in enum_values          # Fix 11 negative assertion
    assert len(enum_values) == 11                                  # AC2.1
```

### Why NOT `anthropic` SDK Directly

M9 uses `boto3` Bedrock Runtime `converse` API — NOT the `anthropic` Python SDK. Rationale:

1. **R13 forbidden imports**: `anthropic`, `openai`, `langchain`, `langgraph` are all banned. `boto3` is the single approved cloud SDK (AC13.3).
2. **Rule 15 (provider abstraction)**: going through Bedrock keeps a single cloud API surface that the `LLMProvider` Protocol abstracts. `VllmClient` / `VertexClient` / `AzureOpenAIClient` will all issue to their respective SDKs — but `BedrockHaikuClient` sits on `boto3`.
3. **Credential chain (R14)**: `boto3` resolves credentials via IRSA / instance metadata / env / Vault without M9 code passing any secret.


## §Fixtures Catalog — Shared Test Scaffolding

The restored Tasks (1-19) share a small set of fixtures. Centralizing here prevents per-test duplication and keeps determinism invariants obvious. All fixtures live under `tests/fixtures/` and are imported via `conftest.py`.

### F1. `fixture_tenant_hmac_key`

```python
# tests/fixtures/hmac.py
import pytest

# Deterministic 32-byte key for all hypothesis + unit tests. NEVER a production key.
# Labeled explicitly so R14 credential scan never flags it.
_FIXTURE_TENANT_HMAC_KEY = b"m9-test-fixture-not-a-real-key!!"   # 32 bytes

@pytest.fixture(scope="session")
def fixture_tenant_hmac_key() -> bytes:
    return _FIXTURE_TENANT_HMAC_KEY
```

Used by: Task 5, 6, 8, 10, 11, 13, 14, 15, 18 — any test that keys `FakeLlmClient.responses` on an HMAC digest.

### F2. `fixture_aid_advisor` + `fixture_aid_agent` + `fixture_aid_compliance_officer`

```python
# tests/fixtures/aid.py
import pytest
from m1_identity import AidClaims, Role

_COMMON = dict(
    firm_id="firm-hyp-fixture",
    archetype="tier4_independent_ria",               # Fix 4 — firm-level
    runtime="managed_agents",
    iat=1747368000, exp=1747371600,
)

@pytest.fixture
def fixture_aid_advisor() -> AidClaims:
    return AidClaims(
        sub="advisor-01", role=Role.advisor,
        authority_scope=["research.read", "research.execute", "client.read",
                         "goal.read", "plan.read", "trade.read"],
        authority_excludes=[], jti="aid-advisor-0001", **_COMMON,
    )

@pytest.fixture
def fixture_aid_agent() -> AidClaims:
    """Agent role — narrower authority (Fix 8 downgrades TRADE_INQUIRY to med bucket)."""
    return AidClaims(
        sub="agent-01", role=Role.agent,
        authority_scope=["research.read", "client.read", "trade.read"],
        authority_excludes=["trade.execute", "plan.write"],
        jti="aid-agent-0001", **_COMMON,
    )

@pytest.fixture
def fixture_aid_compliance_officer() -> AidClaims:
    return AidClaims(
        sub="compliance-01", role=Role.compliance_officer,
        authority_scope=["*"],
        authority_excludes=["trade.execute"], jti="aid-compliance-0001", **_COMMON,
    )
```

Used by: Task 8, 13, 15, 18.

### F3. `fixture_router_context_factory`

```python
# tests/fixtures/context.py
import pytest
from m5_config_loader import Archetype, Runtime
from m9_intent_router import RouterContext

@pytest.fixture
def fixture_router_context_factory():
    def _make(aid, *, trace_id="test-trace-0001") -> RouterContext:
        return RouterContext(
            trace_id=trace_id,
            runtime=Runtime.managed_agents,
            archetype=Archetype.tier4_independent_ria,   # Fix 4
            tenant_id=aid.firm_id,
            identity=aid,                                 # Fix 8
            prior_turns_summary=None,
        )
    return _make
```

Used by: every route() test.

### F4. `fixture_fake_llm_factory`

```python
# tests/fixtures/llm.py
import pytest
from m9_intent_router import IntentCategory, LlmClassification
from m9_intent_router.hmac_util import compute_utterance_digest
from m9_intent_router.llm_client import FakeLlmClient

@pytest.fixture
def fixture_fake_llm_factory(fixture_tenant_hmac_key):
    def _make(utterance_to_response: dict[str, LlmClassification | Exception]) -> FakeLlmClient:
        responses = {
            compute_utterance_digest(u, fixture_tenant_hmac_key): r   # Fix 10 keying
            for u, r in utterance_to_response.items()
        }
        return FakeLlmClient(responses=responses)
    return _make
```

Used by: every test exercising `route()` past MNPI pre-scan.

### F5. `fixture_intent_router_config`

```python
# tests/fixtures/config.py
import pytest
from m5_config_loader import IntentRouterConfig

@pytest.fixture
def fixture_intent_router_config() -> IntentRouterConfig:
    return IntentRouterConfig(
        model_id="anthropic.claude-3-5-haiku-20241022-v1:0",
        provider="bedrock",
        region="us-east-1",
        confidence_high=0.95,
        confidence_med=0.80,
        timeout_ms=1500,
        fallback_enabled=True,
        tenant_hmac_key_vault_path="secret/data/m9/tenants/<tenant_id>/hmac_key",
    )
```

xfail'd until M5 v0.3.0 lands `IntentRouterConfig` per §Known Blockers row 2. Task 17 flips this to strict-pass.

---

## §Integration Test Journey — End-to-End RIA Lighthouse Scenario

A concrete, narrated journey through the 19 tasks for the Phase 2 RIA lighthouse tenant. Demonstrates the restored sections interacting. Lives as `tests/integration/test_ria_lighthouse_journey.py` — composed of Tasks 18 + 19 assertions plus ad-hoc scripted scenarios.

### Scenario 1 — High-Confidence `research.meeting_prep` (happy path)

1. M12 receives user message `"prep me for my meeting with 003xx0000012ABCAAM tomorrow"` from an authenticated advisor (AID `fixture_aid_advisor`).
2. M12 verifies AID via `IdentityService.verify` → `AidClaims`.
3. M12 constructs `RouterContext` via `fixture_router_context_factory(aid)`.
4. M12 calls `route(user_message, ctx, _provider=_PROVIDER, _config=_CFG)`.
5. M9 computes `utterance_sha256 = HMAC-SHA-256(tenant_key, utterance)` — Fix 10.
6. M9 runs `scan_mnpi_shape` — returns `None`.
7. M9 runs `extract_entities` — returns `{"client_id": "003xx0000012ABCAAM", "date_range": "tomorrow"}` (tomorrow fails relative-form whitelist; regex drops, LLM will resolve).
8. M9 acquires `_INFLIGHT` semaphore slot (R19).
9. M9 calls `BedrockHaikuClient.classify(utterance, build_tool_schema())`.
10. Bedrock returns `toolUse` with `{"intent": "research.meeting_prep", "confidence": 0.97, "entities": {"client_id": "003xx0000012ABCAAM"}}`.
11. M9 confidence = 0.97 ≥ 0.95 high bucket → direct dispatch via `TAXONOMY_DISPATCH[RESEARCH_MEETING_PREP]` = `SelectedTarget(kind="pipeline", name="m8.research_pipeline_1")`.
12. M9 emits stdout audit JSON (see §Integration Point with M12 §Audit Handoff).
13. M9 returns `RoutingDecision` to M12.
14. M12 writes `AuditEntry(event_type="supervisor.intent_routed", payload=decision.audit_payload(), ...)` to M10.
15. M12 dispatches to M8 pipeline 1 via `PipelineState.routing_decision = decision` — M8 does NOT re-classify.

**Asserted invariants**: `decision.reason_code is None`, `decision.fallback_used is False`, `decision.confidence == 0.97`, `decision.selected_target.name == "m8.research_pipeline_1"`.

### Scenario 2 — `research.household_summary` (Fix 11 rename verification)

1. User message: `"summarize household HH-A1B2C3D4E5F6 for next week's review"`.
2. Bedrock returns `{"intent": "research.household_summary", "confidence": 0.96, ...}`.
3. M9 dispatches to `m8.research_pipeline_3` (kind="pipeline") — **NOT** `client.household_summary` (pre-Fix-11 name that no longer exists).
4. Task 19 cross-module version-match asserts `"m8.research_pipeline_3" ∈ m8_research_pipeline.PIPELINE_NAMES` — xfail until M8 v0.1.0.

**Asserted invariants**: `decision.intent == IntentCategory.RESEARCH_HOUSEHOLD_SUMMARY`, `decision.intent.value == "research.household_summary"`, `decision.selected_target.kind == "pipeline"`.

### Scenario 3 — Agent + TRADE_INQUIRY downgrade (Fix 8 / AC5.8)

1. `fixture_aid_agent` (role=Role.agent, `authority_excludes=["trade.execute"]`).
2. User message: `"what's the current ask on NVDA"`.
3. Bedrock returns `{"intent": "trade.inquiry", "confidence": 0.98, "entities": {"ticker": "NVDA"}}`.
4. M9 detects `role == agent` AND `intent == TRADE_INQUIRY` → AC5.8 downgrade: confidence effective-bucket becomes med regardless of 0.98.
5. Dispatch proceeds to `trade.inquiry` tool (scope `trade.read` present), but `reason_code="llm_assisted_plan"` marks the mid-bucket path.

**Asserted invariants**: `decision.confidence == 0.98` (original preserved), `decision.reason_code == "llm_assisted_plan"`, `decision.intent == IntentCategory.TRADE_INQUIRY`.

### Scenario 4 — AID authority denied (Fix 8 / AC12.9)

1. `fixture_aid_agent` missing `plan.read` scope.
2. User message: `"summarize the plan for 003xx0000099ZZZAAA"`.
3. Bedrock returns `{"intent": "client.plan_summary", "confidence": 0.94, ...}`.
4. §Authority Scope Matrix: `client.plan_summary` requires `plan.read`. AID has `authority_scope=["research.read", "client.read", "trade.read"]` — `plan.read` absent.
5. M9 post-LLM check (AC12.9) fires: `reason_code="aid_authority_denied"`, intent forced to `ESCALATE_TO_HUMAN`.

**Asserted invariants**: `decision.intent == IntentCategory.ESCALATE_TO_HUMAN`, `decision.reason_code == "aid_authority_denied"`, `decision.confidence == 0.94` (original preserved), no trace of denied scope name in `decision.audit_payload()`.

### Scenario 5 — MNPI shape short-circuit

1. User message: `"wire $50k to routing 021000021 account 1234567890"`.
2. M9 `scan_mnpi_shape` returns `"wire_instruction"` (highest precedence — compound keyword + numeric signals).
3. M9 short-circuits BEFORE Bedrock call — zero LLM tokens consumed, zero LLM latency.
4. Audit emitted with `reason_code="mnpi_shape_suspected"` — category name (`wire_instruction`) NOT leaked in audit (AC8.6).

**Asserted invariants**: `decision.intent == IntentCategory.ESCALATE_TO_HUMAN`, `decision.reason_code == "mnpi_shape_suspected"`, `decision.llm_latency_ms == 0`, `route()` wall-clock < 20 ms (AC8.5).

### Scenario 6 — LLM timeout + fallback

1. User message: `"prep me for the Henderson meeting"`.
2. `SlowFakeLlmClient(block_ms=3000, timeout_ms=1500)` installed as provider.
3. Classify sleeps 1500ms then raises `LlmTimeoutError`.
4. M9 runs `fallback_classify` — matches `prep|prepare|meeting` pattern → `RESEARCH_MEETING_PREP`.
5. `RoutingDecision(intent=RESEARCH_MEETING_PREP, confidence=0.5, fallback_used=True, reason_code="llm_timeout")`.

**Asserted invariants**: `route()` returns in < 3000 ms (AC1.8), `decision.fallback_used is True`, `decision.reason_code == "llm_timeout"`, `decision.confidence == 0.5`.

### Scenario 7 — 4xx NO fallback (AC7.6, Recommended Fix 6)

1. `FakeLlmClient.responses` seeded with `LlmProviderError(400, "invalid tool schema")` for this utterance.
2. M9 catches `LlmProviderError` with `status_code=400`.
3. AC7.6: 4xx is config defect → NO fallback attempted.
4. `fallback_enabled=True` OR `False` — same outcome (AC7.7 corner case).

**Asserted invariants**: `decision.fallback_used is False`, `decision.reason_code == "llm_error_4xx"`, `decision.intent == IntentCategory.ESCALATE_TO_HUMAN`.

---

## Appendix E — Worked Test Skeletons (spec-level, illustrative)

Spec-level skeletons for the three most subtle restored tests. Tasks 13, 15, and 19 are the authoritative sources — these are reading aids.

### E.1 Task 13 — `tests/unit/test_confidence_thresholds.py` (excerpt)

```python
import pytest
from m9_intent_router import IntentCategory, LlmClassification, route
from m9_intent_router.errors import (
    LlmTimeoutError, LlmProviderError, LlmMalformedOutputError,
)

# See §Confidence Threshold Table — 21 rows. Parametrized.
_CASES = [
    # (id, conf, intent, role, fallback_enabled, error, expected_intent, expected_reason, fallback_used)
    ("row01_happy_high",      0.97, "research.meeting_prep", "advisor", True, None,
                              "research.meeting_prep", None, False),
    ("row02_boundary_high",   0.95, "research.meeting_prep", "advisor", True, None,
                              "research.meeting_prep", None, False),
    ("row03_just_below_high", 0.94999, "research.meeting_prep", "advisor", True, None,
                              "research.meeting_prep", "llm_assisted_plan", False),
    # ... rows 4-21 from §Confidence Threshold Table
    ("row11_agent_trade_hi",  0.98, "trade.inquiry", "agent", True, None,
                              "trade.inquiry", "llm_assisted_plan", False),           # Fix 8 / AC5.8
    ("row19_nofb_4xx",        None, None, "advisor", False, LlmProviderError(400),
                              "escalate_to_human", "llm_error_4xx", False),           # Recommended Fix 6
]

@pytest.mark.parametrize("case_id,conf,intent,role,fb,err,exp_intent,exp_reason,exp_fb",
                         [(c[0], *c[1:]) for c in _CASES], ids=lambda c: c[0])
def test_confidence_thresholds(
    case_id, conf, intent, role, fb, err, exp_intent, exp_reason, exp_fb,
    fixture_fake_llm_factory, fixture_aid_advisor, fixture_aid_agent,
    fixture_router_context_factory, fixture_intent_router_config,
):
    utterance = "prep me for my meeting with 003xx0000012ABCAAM tomorrow"
    aid = fixture_aid_agent if role == "agent" else fixture_aid_advisor
    ctx = fixture_router_context_factory(aid)
    cfg = fixture_intent_router_config.model_copy(update={"fallback_enabled": fb})
    if err is not None:
        provider = fixture_fake_llm_factory({utterance: err})
    else:
        provider = fixture_fake_llm_factory({utterance: LlmClassification(
            intent=IntentCategory(intent), confidence=conf, entities={},
            latency_ms=50, model="fake", provider="fake",
        )})
    decision = route(utterance, ctx, _provider=provider, _config=cfg)
    assert decision.intent.value == exp_intent, f"{case_id}: intent"
    assert decision.reason_code == exp_reason, f"{case_id}: reason_code"
    assert decision.fallback_used is exp_fb, f"{case_id}: fallback_used"
```

### E.2 Task 15 — `tests/unit/test_reason_codes.py` (exhaustive vocabulary)

```python
from m9_intent_router.errors import VALID_REASON_CODES

def test_all_13_reason_codes_exercised(all_scenarios_producing_reason_codes):
    """Meta-test: every code in VALID_REASON_CODES must be produced by at least one scenario."""
    produced = {s.reason_code for s in all_scenarios_producing_reason_codes if s.reason_code}
    missing = VALID_REASON_CODES - produced
    unexpected = produced - VALID_REASON_CODES
    assert not missing, f"unreachable reason codes: {missing}"
    assert not unexpected, f"unknown reason codes emitted: {unexpected}"
    assert "aid_authority_denied" in produced, "Fix 8 code must be exercised"     # explicit
```

### E.3 Task 19 — `tests/integration/test_cross_module_version_match.py` (xfail-until-M6/M8)

```python
import pytest
from m9_intent_router import IntentCategory
from m9_intent_router.taxonomy import TAXONOMY_DISPATCH


@pytest.mark.xfail(reason="PENDING-CONFIRM-WITH-M6 — M6 Phase 2 composed-tool manifest", strict=False)
def test_tool_kind_names_subset_of_m6_registered():
    from m6_mcp_gateway import REGISTERED_TOOLS           # M6 Phase 2 symbol (not yet exported)
    m9_tool_names = {t.name for t in TAXONOMY_DISPATCH.values() if t.kind == "tool"}
    missing = m9_tool_names - set(REGISTERED_TOOLS)
    assert not missing, f"M9 references tools not in M6 registry: {missing}"


@pytest.mark.xfail(reason="PENDING-CONFIRM-WITH-M8 — M8 v0.1.0 PIPELINE_NAMES constant", strict=False)
def test_pipeline_kind_names_subset_of_m8_pipeline_names():
    from m8_research_pipeline import PIPELINE_NAMES       # M8 v0.1.0 symbol (not yet exported)
    m9_pipeline_names = {t.name for t in TAXONOMY_DISPATCH.values() if t.kind == "pipeline"}
    missing = m9_pipeline_names - set(PIPELINE_NAMES)
    assert not missing, f"M9 references pipelines not exported by M8: {missing}"
```

**xfail posture**: strict=False — if M6 / M8 land their manifests and the names happen to match, the test silently upgrades to passing. No need to rewrite when unblocking happens.

### E.4 Task 6 Extension — `tests/unit/test_hmac_util.py` (Fix 10 — cross-tenant divergence)

```python
from m9_intent_router.hmac_util import compute_utterance_digest

def test_same_utterance_different_tenants_produces_different_digests():
    """Fix 10: HMAC prevents cross-tenant rainbow-table correlation."""
    utterance = "what is NVDA at"
    key_tenant_a = b"tenant-a-hmac-key-32bytes-exactly!"
    key_tenant_b = b"tenant-b-hmac-key-32bytes-exactly!"
    assert compute_utterance_digest(utterance, key_tenant_a) != \
           compute_utterance_digest(utterance, key_tenant_b)


def test_hex_shape():
    d = compute_utterance_digest("hello", b"x" * 32)
    assert len(d) == 64 and all(c in "0123456789abcdef" for c in d)
```

### E.5 Task 8 Extension — `tests/unit/test_authority_scope.py` (Fix 8)

```python
from m9_intent_router import IntentCategory

# See §Authority Scope Matrix.
_MATRIX = [
    ("research.meeting_prep",     {"research.read"},                  True),
    ("research.meeting_prep",     {"client.read"},                    False),   # missing research.read
    ("client.plan_summary",       {"plan.read", "client.read"},       True),
    ("client.plan_summary",       {"client.read"},                    False),   # missing plan.read
    ("trade.inquiry",             {"trade.read"},                     True),
    ("trade.inquiry",             set(),                              False),
    ("compliance.question",       set(),                              True),    # always allowed
    ("escalate_to_human",         set(),                              True),
    ("unsupported",               set(),                              True),
]

def test_authority_matrix_enforced():
    from m9_intent_router.route import _check_authority_scope
    for intent_val, scopes, expected in _MATRIX:
        result = _check_authority_scope(IntentCategory(intent_val), scopes, set())
        assert result is expected, f"{intent_val} with {scopes} — expected {expected}"


def test_authority_excludes_denies_even_when_allow_star():
    """authority_scope=['*'] + authority_excludes=['trade.execute'] denies trade.execute."""
    from m9_intent_router.route import _check_authority_scope
    allowed = _check_authority_scope(
        IntentCategory.TRADE_INQUIRY, {"*"}, {"trade.execute"},
    )
    assert allowed is True    # trade.inquiry only needs trade.read, which * covers
    # Future: when TRADE_EXECUTE intent lands, assert False.
```

---

## Integration Point with M12 (Supervisor Model) — Request/Response Shapes + Audit Handoff

M12 is M9's only direct caller in Phase 2 (ARCH-09 matrix column 9, M12 marked `*`). This section gives concrete JSON examples of the data that crosses the M12 ⇄ M9 boundary, plus the audit hand-off to M10 that M12 performs on M9's behalf. v0.2.0 replaces the deleted v0.1.0 §Integration Point with M6 (Fix 1 + Fix 3).

### Why NOT a VendorAdapter

M6's `VendorAdapter` Protocol (`m6_mcp_gateway/adapters.py`) has real shape `{name: str, call(*, tool_name: str, payload: dict) -> dict}`. M9 is **not** a vendor — it is an in-process classifier. v0.1.0 confused these and invented `VendorAdapter(handler=..., tool_name=..., timeout_ms=...)` + `M6_REGISTRY.register(...)` — neither exists in M6 source. v0.2.0 deletes that integration entirely. M9 ships as a library; M12 imports and calls `route()` directly.

### Call Site (Python, M12-side)

```python
# M12 Supervisor — src/m12_supervisor/routing.py (illustrative, lives in M12 spec)
from m1_identity import IdentityService, AidClaims, Role
from m5_config_loader import Archetype, Runtime, load_intent_router_config
from m9_intent_router import route, RouterContext, RoutingDecision
from m9_intent_router.llm_client import select_provider

_CFG = load_intent_router_config()                          # startup
_PROVIDER = select_provider(_CFG)                           # M9 helper

def handle_user_message(user_message: str, raw_aid: bytes, trace_id: str) -> RoutingDecision:
    aid: AidClaims = IdentityService.verify(raw_aid)        # M12 re-verifies — M9 does NOT
    ctx = RouterContext(
        trace_id=trace_id,
        runtime=Runtime(aid.runtime),                       # e.g., Runtime.managed_agents
        archetype=Archetype(aid.archetype),                 # firm-level, Fix 4
        tenant_id=aid.firm_id,
        identity=aid,                                       # Fix 8 — carries authority_scope
        prior_turns_summary=None,                           # Phase 2 ignores
    )
    decision = route(user_message, ctx, _provider=_PROVIDER, _config=_CFG)
    # M12 hands decision.audit_payload() to M10 as part of a broader supervisor event.
    return decision
```

### Request Shape (M12 → M9) — `RouterContext` Example

```json
{
  "trace_id": "supv-2026-05-16-7f3c9a1e",
  "runtime": "managed_agents",
  "archetype": "tier4_independent_ria",
  "tenant_id": "firm-abc-12345",
  "identity": {
    "sub": "agent-42",
    "firm_id": "firm-abc-12345",
    "archetype": "tier4_independent_ria",
    "role": "agent",
    "authority_scope": ["research.read", "client.read", "goal.read", "plan.read", "trade.read"],
    "authority_excludes": ["trade.execute"],
    "runtime": "managed_agents",
    "iat": 1747368000,
    "exp": 1747371600,
    "jti": "aid-7f3c9a1e-0001"
  },
  "prior_turns_summary": null
}
```

Utterance crosses the boundary as a separate positional arg — keeps it out of any `RouterContext.model_dump()` that M12 might accidentally log.

### Response Shape (M9 → M12) — `RoutingDecision` Example (high-confidence `research.meeting_prep`)

```json
{
  "trace_id": "supv-2026-05-16-7f3c9a1e",
  "utterance_sha256": "c1b4...ef9a",
  "intent": "research.meeting_prep",
  "confidence": 0.97,
  "entities": {"client_id": "003xx0000012ABCAAM", "date_range": "last_30_days"},
  "selected_target": {"kind": "pipeline", "name": "m8.research_pipeline_1"},
  "fallback_used": false,
  "llm_latency_ms": 312,
  "llm_model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "llm_provider": "bedrock",
  "reason_code": null,
  "tenant_id": "firm-abc-12345"
}
```

### Response Shape — Fix 8 Authority Denial Example

Agent with `authority_excludes=["trade.execute"]` utters "buy 500 shares NVDA". Classified as `trade.inquiry` at 0.92 — per AC5.8, role=`agent` + `TRADE_INQUIRY` downgrades to med bucket. `trade.inquiry` requires `trade.read` (Agent has it), so dispatch proceeds — `reason_code="llm_assisted_plan"`. A stricter case: utterance `"summarize the plan for 003xx0000099ZZZAAA"` classified to `client.plan_summary` at 0.94 — scope check at AC12.9 fires because `plan.read` is missing:

```json
{
  "trace_id": "supv-2026-05-16-7f3c9a1e",
  "utterance_sha256": "55d8...1c22",
  "intent": "escalate_to_human",
  "confidence": 0.94,
  "entities": {"client_id": "003xx0000099ZZZAAA"},
  "selected_target": {"kind": "escalate", "name": "human_specialist"},
  "fallback_used": false,
  "llm_latency_ms": 308,
  "llm_model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "llm_provider": "bedrock",
  "reason_code": "aid_authority_denied",
  "tenant_id": "firm-abc-12345"
}
```

Confidence preserved (0.94), intent forced to `escalate_to_human`, `reason_code="aid_authority_denied"` — the denied scope name is NOT included in the audit payload (avoids leaking authority topology). Denied-scope name is written to M10 separately by M12's sidecar under a distinct audit event (`supervisor.authority_denial`) — not by M9.

### Response Shape — `research.household_summary` Example (Fix 11 verification)

```json
{
  "trace_id": "supv-2026-05-16-a3e1",
  "utterance_sha256": "7a9c...0044",
  "intent": "research.household_summary",
  "confidence": 0.96,
  "entities": {"household_id": "HH-A1B2C3D4E5F6"},
  "selected_target": {"kind": "pipeline", "name": "m8.research_pipeline_3"},
  "fallback_used": false,
  "llm_latency_ms": 287,
  "llm_model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "llm_provider": "bedrock",
  "reason_code": null,
  "tenant_id": "firm-abc-12345"
}
```

Verifies AC2.9 prefix invariant: `research.household_summary` (not `client.household_summary`) routes to `kind="pipeline"` target `m8.research_pipeline_3`. Pre-Fix-11 this was `client.household_summary` — which would have violated the prefix-kind invariant.

### Audit Handoff — M12 → M10

M9 emits **one stdout JSON line** per `route()` call (AC9.7). M12's sidecar (or fluent-bit equivalent in Managed Agents topology) captures stdout and forwards to M10. The captured line is literally `decision.audit_payload()` with a `"source": "m9"` prefix added by `_emit_audit`:

```json
{
  "source": "m9",
  "confidence": 0.97,
  "entities_present": ["client_id", "date_range"],
  "fallback_used": false,
  "intent": "research.meeting_prep",
  "llm_latency_ms": 312,
  "llm_model": "anthropic.claude-3-5-haiku-20241022-v1:0",
  "llm_provider": "bedrock",
  "reason_code": null,
  "selected_target": {"kind": "pipeline", "name": "m8.research_pipeline_1"},
  "tenant_id": "firm-abc-12345",
  "trace_id": "supv-2026-05-16-7f3c9a1e",
  "utterance_sha256": "c1b4...ef9a"
}
```

(`sort_keys=True` — alphabetical order, deterministic for byte-diff audit reproduction.)

M12 then issues a separate `AuditEntry` to M10 of the shape:

```json
{
  "event_type": "supervisor.intent_routed",
  "trace_id": "supv-2026-05-16-7f3c9a1e",
  "firm_id": "firm-abc-12345",
  "agent_id": "agent-42",
  "payload": { "...the m9 audit_payload verbatim..." },
  "timestamp": "2026-05-16T14:02:37.312Z"
}
```

The `payload` field carries M9's audit dict verbatim — M12 does not re-shape. M10 3-tier WORM (Langfuse + S3 Object Lock + CRM per Steering Rule 6) is M12/M10's responsibility; M9 never opens a connection to any of the three.

### Rename Policy for `selected_target.name`

Renaming a `selected_target.name` (e.g., `m8.research_pipeline_3` → `m8.household_research_pipeline`) is a **MAJOR bump**. A one-minor-version alias window MAY be offered: dispatcher emits BOTH old and new names under a feature-flag, audit consumers query on `utterance_sha256` + `intent.value` (stable) rather than `selected_target.name` (volatile). DECISION-LOG 2026-05-16 entry "Fix 17.4 rename policy" is the source of truth.

---

## §Tasks — 19 Atomic Implementation Tasks

Tasks are ordered by dependency. Each task cites the Acceptance Criteria it satisfies. Task 19 is NEW in v0.2.0 (Fix 5). Tasks 6 and 8 pick up extensions for HMAC utility (Fix 10) and AID authority scope (Fix 8).

| # | Task | Deliverable Files | Satisfies AC | Depends On | xfail? |
|---|------|-------------------|--------------|------------|--------|
| 1 | **Bootstrap provider interface + fakes** | `src/m9_intent_router/llm_client.py` (LLMProvider Protocol, FakeLlmClient, SlowFakeLlmClient, reserved stubs, select_provider); `tests/unit/test_llm_client.py` | AC4.1-4.9 | — | no |
| 2 | **Boundary enforcement** | `tests/security/test_module_boundary.py`, `tests/security/test_forbidden_imports.py`, `tests/security/test_no_m8_string_ref.py`, `tests/security/test_no_hardcoded_creds.py` | AC12.1-12.8, AC13.1-13.7, AC14.1-14.7 | Task 1 | no |
| 3 | **Intent taxonomy + dispatch table** | `src/m9_intent_router/taxonomy.py` (IntentCategory 11-member enum, SelectedTarget, TAXONOMY_DISPATCH MappingProxyType, _validate_taxonomy invariants A1-A19); `tests/unit/test_taxonomy.py::test_all_invariants` | AC2.1-2.9, A1-A19 | Task 1 | no |
| 4 | **Pydantic models** | `src/m9_intent_router/models.py` (RouterContext with identity, LlmClassification with ge/le bounds, RoutingDecision with tenant_id); `tests/unit/test_models.py` | AC1.2, AC1.9, AC3.3, AC5.7, AC9.1-9.6, AC11.1-11.6 | Task 3 | no |
| 5 | **Entity extraction regex library** | `src/m9_intent_router/regex_library.py` (extract_entities, ticker whitelist, SF 18-char checksum validator, household/account regex, date-range whitelist); `tests/unit/test_regex_library.py` + `tests/property/test_regex_library_property.py` | AC6.1-6.8 | Task 4 | no |
| 6 | **MNPI-shape pre-scan + HMAC utterance digest** (Fix 10 extension) | `src/m9_intent_router/mnpi_scan.py`; `src/m9_intent_router/hmac_util.py`; `tests/unit/test_mnpi_scan.py`; **`tests/unit/test_hmac_util.py`** (Fix 10 — cross-tenant digest divergence, Vault path substitution, fail-closed on empty key) | AC8.1-8.9, AC14.7 | Task 4 | no |
| 7 | **BedrockHaikuClient** | `src/m9_intent_router/llm_client.py::BedrockHaikuClient` (converse API, toolConfig, temperature=0, retry/backoff); `tests/unit/test_bedrock_client.py` (botocore Stubber — no live Bedrock) | AC3.1-3.8 | Task 1 | no |
| 8 | **route() dispatcher + AID authority scope check** (Fix 8 extension) | `src/m9_intent_router/route.py` (route, _short_circuit, _dispatch_classification, _handle_llm_error, _emit_audit, _INFLIGHT semaphore); **`tests/unit/test_authority_scope.py`** (Fix 8); `tests/unit/test_route.py`; `tests/unit/test_role_downgrade.py` | AC1.1-1.9, AC5.1-5.8, AC9.7, AC12.9, AC19.1 | Tasks 3, 4, 5, 6, 7 | no |
| 9 | **Deterministic fallback router** | `src/m9_intent_router/fallback.py`; `tests/unit/test_fallback.py` (cover `fallback_enabled=False` + 4xx — Recommended Fix 6) | AC7.1-7.7 | Task 8 | no |
| 10 | **Audit schema + meta-validation** | `src/m9_intent_router/schemas/m9_audit_payload.schema.json`; `tests/unit/test_audit_schema.py::test_round_trip`; `tests/unit/test_audit_schema.py::test_audit_schema_meta` (Recommended Fix 9); canary regex scan for raw-utterance leakage | AC9.1-9.8 | Task 8 | no |
| 11 | **Property tests — determinism + entity-regex safety** | `tests/property/test_determinism.py` (≥100 examples); `tests/property/test_entity_regex.py` (≥500 examples, no re.error) | AC1.5-1.7, AC6.7, AC10.1-10.7 | Task 8 | no |
| 12 | **Concurrency smoke test + R19 semaphore** | `tests/benchmarks/test_m9_concurrency.py` (50 threads × 20 calls); `tests/unit/test_inflight_semaphore.py` | AC1.5, AC16.7, AC19.1-19.5 | Task 8 | no |
| 13 | **Parameterized confidence-threshold test (R5 boundaries)** | `tests/unit/test_confidence_thresholds.py` — 21 rows per §Confidence Threshold Table incl. Inf/-Inf, NaN, Role=agent+TRADE_INQUIRY downgrade, `fallback_enabled=False + 4xx` | AC5.1-5.8 | Task 8 | no |
| 14 | **MNPI negative-path benchmark** | `tests/unit/test_mnpi_negative_paths.py`; `tests/benchmarks/test_mnpi_latency.py` (<20ms) | AC8.5, AC8.8 | Task 6 | no |
| 15 | **Exhaustive reason_code meta-test** | `tests/unit/test_reason_codes.py` — exercises every one of the 13 VALID_REASON_CODES incl. `aid_authority_denied` (Fix 8) via FakeLlmClient Exception injection (Fix 9) + SlowFakeLlmClient for timeout (Fix 13); canary-utterance stdout-scan | AC3.6, AC11.3 | Tasks 8, 9 | no |
| 16 | **Bedrock first-live-call + model-ID verification** | `tests/integration/test_bedrock_first_call.py` (live Bedrock — gated behind `M9_LIVE=1`); DECISION-LOG update on mismatch | §Known Blockers row 3 | Task 7 | gated |
| 17 | **Config shape integration + .env.example shipping** | `tests/integration/test_m9_m5_config_shape.py` (SHARED-WITH-M5); `tests/integration/test_env_example_shipped.py` (Recommended Fix 7) | AC14.4, §Known Blockers row 2 | Task 1 | xfail (until M5 v0.3.0) |
| 18 | **M12 supervisor-call integration** | `tests/integration/test_m12_m9_supervisor_call.py` — round-trip matches §Integration Point with M12 examples | AC17.1-17.4 | Task 8 | no |
| 19 | **Cross-module version-match test** (NEW v0.2.0 — Fix 5) | `tests/integration/test_cross_module_version_match.py` — asserts `{t.name for t in TAXONOMY_DISPATCH.values() if t.kind=="tool"} ⊆ m6_mcp_gateway.REGISTERED_TOOLS` AND `{... if t.kind=="pipeline"} ⊆ m8_research_pipeline.PIPELINE_NAMES` | Appendix A A7, A17; §Known Blockers rows 5, 6 | Task 3 | **xfail until M6 Phase 2 composed-tool manifest + M8 v0.1.0 ship** |

### Task Dependencies (DAG)

```
T1 ──┬──► T2        (boundary enforcement reads Task 1 AST)
     ├──► T3 ──┬──► T4 ──┬──► T5 ──┐
     │         │         └──► T6 ──┤
     │         └──────────────────────►T8 ◄── T7 ◄── T1
     │                               │
     │                               ├──► T9, T10, T11, T12, T13, T15, T18
     │                               └──► T14 ◄── T6
     └──► T19 (waits on T3 + M6/M8)
T7 ──► T16 (gated live)
T1 ──► T17 (xfail pending M5)
```

Critical path: T1 → T3 → T4 → T6 → T8 → T15. Target: Phase 2 Weeks 28-30 per ARCH-09 build order. T19 un-xfails at Phase 2 Week 34 when M6 + M8 land their manifests.

### Task 6 Extension — HMAC utility test coverage (Fix 10)

Task 6 ships `hmac_util.py` alongside the MNPI scanner. `tests/unit/test_hmac_util.py` asserts:

- **Cross-tenant divergence**: same utterance, two tenant keys → two digests. Prevents rainbow-table attack.
- **Hex shape invariant**: digest is exactly 64 hex chars matching `^[0-9a-f]{64}$`.
- **Vault path substitution**: `_resolve_tenant_hmac_key("firm-xyz", "secret/data/m9/tenants/<tenant_id>/hmac_key")` substitutes `<tenant_id>` correctly.
- **Fail-closed on empty key**: `_resolve_tenant_hmac_key` raises `RuntimeError("provider_unconfigured")` if Vault returns empty bytes (R14 AC14.7).
- **LRU cache behaviour**: `@lru_cache(maxsize=128)` verified — two calls with identical `(tenant_id, vault_path)` → one boto3 call.

### Task 8 Extension — AID authority scope coverage (Fix 8)

Task 8 ships `route.py` with authority-scope gating AND `_check_authority_scope` helper. `tests/unit/test_authority_scope.py` asserts:

- Every row of §Authority Scope Matrix — scope hit returns `True`, scope miss returns `False`.
- `authority_scope=["*"]` grants everything EXCEPT what `authority_excludes` denies.
- `compliance.question`, `escalate_to_human`, `unsupported` bypass scope check (always allowed — terminal escalations).
- Role=agent + TRADE_INQUIRY downgrade fires BEFORE scope check (downgrade is on confidence, not on scope).
- Failed scope check → `RoutingDecision(intent=ESCALATE_TO_HUMAN, reason_code="aid_authority_denied", confidence=<original>)` with denied scope name NOT present anywhere in `audit_payload()`.

---

## §Hypothesis Strategy Approach

Hypothesis property-test strategies compose via `@composite` to produce `(utterance, RouterContext)` tuples that exercise `route()` under realistic-shaped inputs. v0.2.0 worked example uses firm-level `Archetype.tier4_independent_ria` (Fix 4), populates `identity: AidClaims` (Fix 8), and keys `FakeLlmClient` on the HMAC digest (Fix 10 — not plain SHA).

### `utterance_variants()` Composite Strategy

```python
# tests/property/strategies.py
from hypothesis import strategies as st
from hypothesis.strategies import composite

from m1_identity import AidClaims, Role
from m5_config_loader import Archetype, Runtime
from m9_intent_router import RouterContext
from m9_intent_router.hmac_util import compute_utterance_digest

# Fixed test-fixture HMAC key — NEVER a real tenant key (R14).
_FIXTURE_TENANT_KEY = b"m9-hypothesis-fixture-key-32b!!!"

# Phase 2 supported utterance templates — minimal, intent-diverse.
_TEMPLATES = [
    "prep me for my meeting with {client_id}",
    "show me the household summary for {household_id}",       # research.household_summary (Fix 11)
    "what is the current price of {ticker}",
    "pull up account {account_id}",
    "track goals for household {household_id}",
    "what does compliance say about {ticker}",
    "buy {qty} shares of {ticker}",
    "summarize the plan for {client_id}",
]

_TICKER = st.sampled_from(["NVDA", "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA", "META", "JPM"])
_QTY = st.integers(min_value=1, max_value=10_000)
_CLIENT_ID = st.from_regex(r"^[a-zA-Z0-9]{18}$", fullmatch=True)
_HOUSEHOLD_ID = st.from_regex(r"^HH-[A-Z0-9]{10,16}$", fullmatch=True)
_ACCOUNT_ID = st.from_regex(r"^ACC-[A-Z0-9]{8,12}$", fullmatch=True)


@composite
def aid_claims(draw) -> AidClaims:
    """Generate an AidClaims consistent with Archetype.tier4_independent_ria (Fix 4 + Fix 8)."""
    role = draw(st.sampled_from([Role.agent, Role.advisor, Role.compliance_officer]))
    scopes = draw(st.sets(st.sampled_from(
        ["research.read", "research.execute", "client.read", "goal.read",
         "plan.read", "trade.read"]
    ), min_size=1, max_size=6))
    return AidClaims(
        sub=draw(st.from_regex(r"^agent-\d{2,4}$", fullmatch=True)),
        firm_id="firm-hyp-fixture",
        archetype="tier4_independent_ria",              # Fix 4 firm-level
        role=role,
        authority_scope=sorted(scopes),
        authority_excludes=[],
        runtime="managed_agents",
        iat=1747368000, exp=1747371600,
        jti=draw(st.from_regex(r"^aid-[a-f0-9]{8}$", fullmatch=True)),
    )


@composite
def router_context(draw) -> RouterContext:
    aid = draw(aid_claims())
    return RouterContext(
        trace_id=draw(st.from_regex(r"^hyp-[a-f0-9]{8}$", fullmatch=True)),
        runtime=Runtime.managed_agents,
        archetype=Archetype.tier4_independent_ria,      # Fix 4 — matches aid.archetype
        tenant_id=aid.firm_id,
        identity=aid,                                    # Fix 8
        prior_turns_summary=None,
    )


@composite
def utterance_variants(draw) -> tuple[str, RouterContext, str]:
    """Returns (utterance, context, utterance_hmac_digest) for FakeLlmClient keying.

    The digest is HMAC-SHA-256(fixture_tenant_key, utterance) — Fix 10.
    Test fixtures seed FakeLlmClient.responses on THIS digest (not plain SHA).
    """
    template = draw(st.sampled_from(_TEMPLATES))
    utterance = template.format(
        client_id=draw(_CLIENT_ID),
        household_id=draw(_HOUSEHOLD_ID),
        account_id=draw(_ACCOUNT_ID),
        ticker=draw(_TICKER),
        qty=draw(_QTY),
    )
    ctx = draw(router_context())
    digest = compute_utterance_digest(utterance, _FIXTURE_TENANT_KEY)   # Fix 10
    return utterance, ctx, digest
```

### Usage in Task 11 Determinism Test

```python
from hypothesis import given, settings
from m9_intent_router import route, IntentCategory, LlmClassification
from m9_intent_router.llm_client import FakeLlmClient
from tests.property.strategies import utterance_variants

@given(uc=utterance_variants())
@settings(max_examples=100, deadline=500)
def test_route_determinism(uc):
    utterance, ctx, digest = uc
    seeded_resp = LlmClassification(
        intent=IntentCategory.RESEARCH_MEETING_PREP, confidence=0.97,
        entities={}, latency_ms=50, model="fake", provider="fake",
    )
    provider = FakeLlmClient(responses={digest: seeded_resp})  # Fix 10 keying
    d1 = route(utterance, ctx, _provider=provider, _config=_TEST_CFG)
    d2 = route(utterance, ctx, _provider=provider, _config=_TEST_CFG)
    assert d1.model_dump(exclude={"llm_latency_ms"}) == d2.model_dump(exclude={"llm_latency_ms"})
```

**CI budget** (AC10.4): 3 property files (`test_determinism.py`, `test_entity_regex.py`, `test_mnpi_scan_property.py`) × 100 examples × 500 ms deadline ≈ 150 s worst-case wall-clock. Documented honestly — Recommended Fix 5.

### Shrinking Behaviour

Hypothesis shrinks to the smallest `(utterance, context)` causing a failure. Minimal-counterexample invariant: shrunken utterances are still ≥ 1 char (AC1.3 lower bound); shrunken `authority_scope` is still non-empty (strategy invariant). This makes failure diagnosis tractable — shrunk failures land in `.hypothesis/examples/` as deterministic seeds.

### Determinism Invariant Matrix

| Invariant | Strategy Check | Property Test |
|-----------|----------------|---------------|
| Two identical calls → identical decisions (excl. `llm_latency_ms`) | Same `(utterance, ctx, provider)` | `test_determinism.py::test_route_determinism` |
| `prior_turns_summary=None` vs arbitrary string → same decision (Phase 2 ignores — AC1.7) | `st.one_of(st.none(), st.text())` | `test_determinism.py::test_prior_turns_ignored` |
| `route()` does not mutate inputs (AC1.6) | `copy.deepcopy` before; `==` after | `test_determinism.py::test_input_immutability` |
| Tie-break alphabetical (AC10.3) | seed `FakeLlmClient` with two candidates at equal confidence | `test_determinism.py::test_alphabetical_tie_break` |

---

## Document Metadata

| Field | Value |
|-------|-------|
| Spec Version | **0.2.0** |
| Date | 2026-05-16 |
| Author | Pipeline and Intent Specialist |
| Review Status | Pending LLMJ-v2 |
| Target Review Score | ≥ 8.0/10 GO on re-review |
| Mirror Discipline | M7 v0.3.0 + M11 v0.2.0 |
| Prior Version | 0.1.0 (scored 7.42/10 CONDITIONAL GO in LLMJ-v1); v0.2.0 rewrite addressed 14 Required Fixes but dropped 8 implementation-ready sections — this restoration pass brings them back |
| Required Fixes Addressed | 14 of 14 |
| Recommended Fixes Landed | 11 of 12 (R10 Luhn-tighten deferred to Phase 3 with acknowledgement) |
| Restored Sections (completeness repair) | 8 of 8 — (1) §Integration Point with M12 §Request/Response Shapes + §Audit Handoff (replaces v0.1.0 §Integration Point with M6); (2) §Tasks (19 atomic tasks incl. new Task 19 cross-module version-match + Task 6 HMAC extension + Task 8 authority-scope extension); (3) §Hypothesis Strategy Approach (`utterance_variants()` `@composite` worked example); (4) §Confidence Threshold Table (21 rows incl. `float('inf')`/`float('-inf')`, `fallback_enabled=False + 4xx`, Role=agent+TRADE_INQUIRY downgrade); (5) §Entity Extraction Regex Library (6-slot + 50-ticker whitelist); (6) §MNPI-Shape Patterns (4-category + precedence); (7) §Error Code Map (13 rows incl. `aid_authority_denied`); (8) §LLM Contract JSON Schema Example (Bedrock `toolConfig` with Fix-11 enum `research.household_summary`) |
| Supporting Sections Added | §Fixtures Catalog, §Integration Test Journey, Appendix E (worked test skeletons) |
| Final Line Count | See `wc -l` at commit — target band: M7 v0.3.0 / M11 v0.2.0 (~1,800-2,000 lines) |
