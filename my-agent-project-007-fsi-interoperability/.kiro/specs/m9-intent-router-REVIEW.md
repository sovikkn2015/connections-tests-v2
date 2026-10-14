# M9 Intent Router — LLMJ Review (First Pass)

**Spec Version:** 0.1.0 (1,765 lines)
**Reviewer:** pipeline-and-intent-agent acting as independent LLMJ
**Date:** 2026-05-15
**Playbook Step:** 2 of 7

---

## Weighted Score: 7.42 / 10 — **CONDITIONAL GO** (fix and re-review)

| # | Dimension | Weight | Score | Weighted |
|---|-----------|--------|-------|----------|
| 1 | Completeness | 25% | 8.4 | 2.10 |
| 2 | Accuracy | 20% | 5.5 | 1.10 |
| 3 | Security | 20% | 8.6 | 1.72 |
| 4 | Testability | 15% | 8.0 | 1.20 |
| 5 | Design Alignment | 10% | 6.5 | 0.65 |
| 6 | Gaps | 10% | 6.5 | 0.65 |
| — | **TOTAL** | **100%** | — | **7.42** |

Scoring bands: 8.0+ = GO, 7.5–7.9 = MARGINAL GO, 6.5–7.4 = CONDITIONAL GO, <6.5 = NO GO.

The spec lands in CONDITIONAL GO territory. Structural discipline is very strong (18 atomic tasks, AC-indexed tests, Hypothesis strategy, MNPI fail-closed, positive allow-list for imports, closed frozen reason-code vocabulary, explicit §Known Blockers with SHARED-WITH-M5 gating). Security discipline mirrors M6/M7/M11 at their best.

But **four facts do not match source of truth**: (a) the ARCH-09 dependency matrix for M9 — M9 calls M1 and M5, not M3 and M5, and M9 is called by M12, not M6; (b) the claimed ARCH-07 latency target (p50<200/p95<500/p99<1000) is stricter than ARCH-07 actually publishes (only `<500ms` is stated for the Supervisor Haiku row); (c) the M6 VendorAdapter Protocol shown in §Integration Point with M6 has a `handler=` kwarg and `timeout_ms=` that do NOT exist on the real Protocol in `src/m6_mcp_gateway/adapters.py`; (d) `RouterContext.archetype: Archetype` imports the M5 FIRM archetype enum but the worked example uses `"mass_affluent"` which is a CLIENT-level archetype string from M3, not an M5 enum value.

Three of those are the M7-v1 class of miss: the spec treats the integration seam as solved when it demonstrably does not fit. This is the same pattern M7 v1 hit 7.36 on and M11 v1 hit 7.27 on. Fix them and the spec clears 8.0+.

---

## 1. Completeness — 8.4/10

### Evidence

- **18 numbered requirements (R1–R18), ~131 ACs** across them. Every requirement has explicit AC enumeration and maps to at least one task in §Tasks.
- **18 atomic tasks** (Task 1 through Task 18). Each task cites AC ranges. Task 2 enforces Steering Rule 29 depth-first by writing negative tests BEFORE any implementation.
- **§Known Blockers table** with 8 rows: 3 PENDING-VERIFICATION, 1 SHARED-WITH-M5, 4 RESOLVED. Every blocker has Impact + Status column.
- **§Phase 2 Scope** plus explicit OUT-of-scope list deferring unsupported-intent rejection templates, multi-turn clarification, non-Bedrock providers, intent-weighted load shaping, channel-specific hints, multilingual taxonomy, conversation memory, cost attribution to Phase 3+. Nothing silent.
- **§FSI Intent Taxonomy** — 11-row dispatch table with enum name, string value, kind, target name, example utterance, and specialist mapping per row.
- **§Confidence Threshold Table** — 12-row table enumerating boundary behavior for every scenario (exact boundary, ±ε, NaN, custom thresholds, invariant violation). Drives Task 13 parameterized tests directly.
- **§Error Code Map** — 12-row table with triggered-by, detection point, HTTP-equivalent, `fallback_used`, downstream outcome. Matches the 12-value `VALID_REASON_CODES` frozenset exactly. No drift.
- **§MNPI-Shape Patterns** — 4-category regex table with validator, example hit, example miss, false-positive acknowledgement + fixed-order Precedence subsection.
- **§Entity Extraction Regex Library** — 6-slot regex table with Phase 2 ticker whitelist (50 entries), SF 18-char checksum, household/account prefix conventions, ISO date-range + relative whitelist.
- **§Hypothesis Strategy Approach** — full `@composite` `utterance_variants()` worked example with 11 intent skeletons, 50-entry ticker whitelist, 5 pre-computed valid SF 18-char IDs, safe household/account/date lists. M7 v1 did NOT have this; M9 v0.1.0 ships it upfront.
- **Appendix A Routing Matrix Invariants** — 18 import-time / runtime / integration-test invariants with failure-mode assertion messages. Appendix B.1–B.6 skeletons. Appendix C DECISION-LOG seed with 8 entries. Appendix D cross-reference placeholder.

### Strengths

- **Task 2 "negative tests FIRST"** — before any implementation, four security/boundary tests are written (`test_module_boundary.py`, `test_forbidden_imports.py`, `test_no_hardcoded_creds.py`, `test_no_m8_string_ref.py`). M3 v2 / M7 v2 / M11 v2 discipline baked in from v0.1.0.
- **Closed frozen error vocabulary** — `VALID_REASON_CODES` is a 12-value frozenset, every code is documented in §Error Code Map, AC11.3 meta-test asserts every code is reachable. AC11.6 forbids MNPI-category leakage into codes.
- **Architecture Clarification block** explicitly states M9 is a pure in-process library, never a service, and M6 orchestrates. Heads off "is this a service?" review friction.
- **§Phase 2 Scope lists out-of-scope items by name** — "multi-turn clarification loop", "cost attribution per intent", "multilingual taxonomy". Decoupled from Phase 3 work.

### Weaknesses (HARSH)

- **Task 19 is referenced but does not exist.** Appendix A invariant A7 and A17 both say "Task 19 cross-module version-match test". §Tasks has Tasks 1–18 only. Broken reference that will confuse implementers. Either add Task 19 (cross-module constant match against M6's tool registry + M8's `PIPELINE_NAMES`) or re-point A7/A17 to an existing task.
- **No Review Fix Traceability rows** (explicitly placeholdered empty in v0.1.0). Fine for first-pass, but v0.2.0 work will be substantial.
- **M5 `IntentRouterConfig` SHARED-WITH-M5 has no concrete ETA.** §Known Blockers row 2 says "M5 v0.3.0" but M5 does not currently expose this model. Without ETA + M5 owner sign-off, AC12.4 AST-import scan fails on day one.
- **`unsupported` Phase 2 handling is a stub.** No metric/telemetry commitment on top-5 unsupported utterances. Phase 3 will need this data; commit to capturing SHA counts now.
- **No coverage for `context.runtime` and `context.archetype` being actually USED downstream.** AC1.2 requires them in `RouterContext`. But `route()` never reads them in any AC — and the taxonomy dispatch is runtime/archetype-agnostic. Either document M9 is deliberately runtime-agnostic OR use them for at least one routing decision. As written, the fields are ceremonial.
- **No versioning story for `TAXONOMY_DISPATCH` target-name RENAMES.** AC18.4 handles ADD. No policy for RENAME or REMOVE. Audit consumers query on `selected_target.name`.
- **AC14.6 `provider_secret` defensive exclude** defends against a phantom field — `IntentRouterConfig` has no `provider_secret` attribute declared anywhere.

### What would make it a 10

Close the Task 19 broken reference. Commit to a Phase-3 unsupported-intent telemetry hook now (SHA-only). Pin M5 `IntentRouterConfig` to a specific M5 spec version. Resolve whether `runtime`/`archetype` are used or ceremonial. Declare breaking-rename policy for pipeline names.

---

## 2. Accuracy — 5.5/10

This is the weakest dimension. Four distinct accuracy problems, two severe. Weights drag the weighted score below 7.5.

### Evidence

Cross-verified against: `src/m6_mcp_gateway/adapters.py` (real `VendorAdapter` Protocol); `src/m3_schema_registry/types.py` (entity types M9 claims to import); `src/m5_config_loader/__init__.py` and `.../loader.py` (real `Archetype` / `Runtime` enums); `docs/architecture/ARCH-07-definitive-tech-stack.md` (Supervisor latency row); `docs/architecture/ARCH-09-complete-module-map.md` (dependency matrix, M9 row); `docs/architecture/ARCH-05-v2-multi-agent-and-memory-architecture.md` §Supervisor Model.

### Strengths

- **12-value `VALID_REASON_CODES` matches §Error Code Map exactly.** No drift across AC11.1, §Error Code Map, Appendix B.6 `errors.py` skeleton. 12 codes; every code has a row; every row has a triggering condition.
- **Bedrock Claude 3.5 Haiku model ID `anthropic.claude-3-5-haiku-20241022-v1:0`** is the real AWS Bedrock canonical model ID for Claude 3.5 Haiku (October 2024 snapshot). NOT invented. Spec acknowledges PENDING-VERIFICATION for region probe (Task 16) — honest framing.
- **Bedrock Converse API `toolConfig` envelope shape in §LLM Contract JSON Schema Example** matches the real Bedrock Converse API: `toolConfig.tools[].toolSpec.inputSchema.json` + `toolChoice: {tool: {name: ...}}` + `inferenceConfig: {temperature, maxTokens}`. Tool response shape `output.message.content[].toolUse.{toolUseId, name, input}` + `stopReason: "tool_use"` + `usage` is correct.
- **SF 18-char checksum description** is directionally correct (split 15 chars into 3 groups of 5, each group's per-char uppercase bitmap forms a 5-bit number 0–31, mapped to base-32 alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZ012345`). AC6.3 could be tighter but is not wrong.
- **ABA checksum weights `[3,7,1,3,7,1,3,7,1]` over 9 digits with `sum(weight * digit) % 10 == 0`** is the correct ABA algorithm. Spec writes out all nine weights explicitly. `021000021` (Chase NY) check: 0·3 + 2·7 + 1·1 + 0·3 + 0·7 + 0·1 + 0·3 + 2·7 + 1·1 = 14 + 1 + 14 + 1 = 30, 30 % 10 == 0 ✓.
- **12 reason codes in `VALID_REASON_CODES` match R11 AC11.1 text exactly.** No drift.

### Weaknesses (HARSH)

#### Problem 1 (SEVERE): The ARCH-09 dependency matrix for M9 is misread.

Spec banner line 11: "ARCH-09 §Module M9 row + dependency matrix (M9 depends on M3, M5; called by M6)."

Actual ARCH-09 dependency matrix (lines 302–315):

```
          M1  M2  M3  M4  M5  M6  M7  M8  M9  M10 M11 M12 M13
  M6       *   *   .   *   .   .   .   .   .   *   *   .   *
  M9       *   .   .   .   *   .   .   .   .   .   .   .   .
  M12      .   .   .   .   .   *   .   *   *   .   .   .   .
```

Reading row M9: `* . . . * . . . . . . . .` — **M9 calls M1 and M5. Not M3.**

Reading column 9 (who calls M9): M6 column is `.`, M12 column is `*`. **M9 is called by M12, not M6.**

That is the opposite of every integration point the spec builds. Consequences:

- **R1 AC1.2** declares `RouterContext.archetype: Archetype` + `runtime: Runtime` (both from M5) but does NOT model an `identity: AID` field from M1 — despite ARCH-09 saying M9 calls M1. The steering file (project 007) restated in the system prompt says literally: "M9 calls M1 for identity verification, M5 for config." M9 spec pretends this dependency does not exist.
- **R12 AC12.2 positive allow-list** permits `m3_schema_registry.*` and `m5_config_loader.*` only. Importing M1 would fail the AST scan the spec just wrote. Either the allow-list is wrong and M1 must be added, OR ARCH-09 + steering file are wrong and a DECISION-LOG entry must override them with SME sign-off.
- **R17 (Integration Point with M6)** is structured around M6 calling M9 as a `VendorAdapter`. ARCH-09 matrix says M6 does not call M9. ARCH-05 v2 §Supervisor Routing Logic pseudocode (lines 275–310) shows `intent_router.classify(user_message, aid)` called directly by the Supervisor (M12), not by M6.
- **R18 (Integration Point with M8)** says "M8 calls M9 via M6". ARCH-09 row M8 is `. * . . * * . . . * . . .` — M8 calls M2, M5, M6, M10. Not M9. The M8 → M6 → M9 chain is a spec-level invention, not an ARCH-09 claim.

This is the M7 v1 "Integration Point with M6 wires to a shape M6 doesn't define" bug, one module over. Fix: re-read ARCH-09, decide whether M9 is called by M6 (new architectural claim requiring ARCH-09 update + DECISION-LOG + committee sign-off) or by M12 (align spec to ARCH-09 and rewrite R17/R18), and either way, pin M9's outbound call to M1 per the matrix.

#### Problem 2 (SEVERE): ARCH-07 latency granularity is fabricated.

Spec banner line 11: "ARCH-07 Supervisor Model latency target (p50 < 200 ms, p95 < 500 ms, p99 < 1000 ms)."

R16 AC16.4: "Production targets (live Bedrock): p50 < 200 ms, p95 < 500 ms, p99 < 1000 ms. SLO targets, not CI gates."

Actual ARCH-07 content (grep for Haiku / supervisor):
- Line 57: `| Supervisor | Haiku | Fast routing, less than 500ms |`
- ARCH-05 v2 line 310 (the other citation): `Typical routing decision: <500ms`

There is no p50 / p95 / p99 published anywhere in ARCH-07. The spec invented numeric granularity to make the latency claim look precise. The p50<200 / p95<500 / p99<1000 is a reasonable SLO shape, but it is NOT what ARCH-07 says, and citing ARCH-07 for it is a citation fabrication in the M11-v1 mold (RES-08 rate-limit citations that did not exist).

Fix: mark p50/p95/p99 as an M9-originated target with rationale in DECISION-LOG and cite ARCH-07 ONLY for "< 500 ms supervisor routing" (actual source-of-truth text). Alternatively, bump ARCH-07 to publish the percentile breakdown with architect sign-off.

#### Problem 3 (SEVERE): M6 `VendorAdapter` Protocol signature does not match real M6.

Spec §Integration Point with M6 / Registration block:

```python
M6_REGISTRY.register(
    VendorAdapter(
        name="m9",
        tool_name="m9.route",
        handler=_m9_vendor_adapter_call,
        timeout_ms=3000,
    )
)
```

Actual `src/m6_mcp_gateway/adapters.py` lines 50–69:

```python
@runtime_checkable
class VendorAdapter(Protocol):
    name: str
    def call(self, *, tool_name: str, payload: Any) -> Any: ...
```

The real Protocol has TWO members: `name: str` attribute and `call(*, tool_name, payload)` method. There is no `tool_name=` constructor kwarg, no `handler=` kwarg, no `timeout_ms=` kwarg. `VendorAdapter` is a **Protocol** — you implement it with a class that has a `name` attribute and a `call` method. You do not "construct" a `VendorAdapter(...)` with kwargs.

Additionally there is no `M6_REGISTRY.register(...)` public API in the M6 source — `adapters.py` exposes `VendorAdapter`, `VendorAdapterError`, `VALID_VENDOR_KINDS`, `StubVendorAdapter` in `__all__`, nothing registry-shaped.

AC17.6 then writes an integration test using this invented shape. The test as specified does not compile against real M6. This is structurally identical to M7 v1's `req.target.source_system` assumption that M6 did not define.

Fix: rewrite §Integration Point with M6 to (a) define an M9 adapter CLASS with `name="m9"` attribute and `call(*, tool_name, payload)` method, (b) drop `tool_name=` from construction (arrives as a method argument), (c) drop `timeout_ms=` (M6 imposes timeout per R17.7), (d) replace `M6_REGISTRY.register(...)` with whatever the real M6 Phase 2 wiring surface is (or mark SHARED-WITH-M6 PENDING).

#### Problem 4 (MEDIUM): `Archetype` vs archetype semantic mismatch.

`src/m5_config_loader/loader.py` line 78:

```python
class Archetype(str, Enum):
    tier1_investment_bank = "tier1_investment_bank"
    tier2_asset_manager = "tier2_asset_manager"
    tier3_broker_dealer = "tier3_broker_dealer"
    tier4_independent_ria = "tier4_independent_ria"
    tier5_hedge_fund = "tier5_hedge_fund"
```

`src/m3_schema_registry/types.py` line 647:

```python
archetype: Optional[str] = Field(default=None,
    description="Client segmentation: mass_affluent, hnw, uhnw.")
```

M5's `Archetype` is FIRM-level (tier1..tier5). M3's `Client.archetype` is CLIENT-level segmentation (mass_affluent, hnw, uhnw).

M9 spec:
- AC1.2: `RouterContext.archetype: Archetype` (imported from M5 per line 9).
- §Integration Point with M6 / Request example: `"archetype": "mass_affluent"`.
- Hypothesis strategy: `archetype="mass_affluent"`.

Both examples use `"mass_affluent"` — which is a CLIENT segmentation string from M3, NOT a valid value for the M5 `Archetype` enum. Pydantic `extra="forbid"` + `archetype: Archetype` will reject `"mass_affluent"` at validation time.

Either: (a) `RouterContext.archetype` is FIRM archetype (examples must use `"tier4_independent_ria"`), or (b) it is CLIENT archetype (M3 ships the enum, not M5; type annotation is wrong). The Phase 2 RIA lighthouse narrative suggests (a), but the examples say (b). Pick one.

#### Problem 5 (MINOR): `m8.research_pipeline_1/2/3/single_tool` pipeline names are invented.

None of `m8.research_pipeline_1`, `m8.research_pipeline_2`, `m8.research_pipeline_3`, `m8.research_single_tool`, or `m6.composed_goal_tracking` appear anywhere in ARCH-07, ARCH-09, ARCH-05 v2, the consolidated design, or any M8/M6 spec or source. M9 is inventing M8's pipeline naming convention.

Spec §Integration Point with M8 acknowledges this ("M8 spec owns the authoritative list. Rename / add flow...") but then AC2.6 and Taxonomy Invariants A7 HARD-CODE a regex that asserts the invented names. Tasks 16 and 19 (19 doesn't exist) assume the names are canonical.

Same pattern as M11 v1 asserting Orion URL paths as if sourced when they weren't. Mark PENDING-CONFIRM-WITH-M8-SPEC-OWNER. Current status `RESOLVED — SemVer discipline` (§Known Blockers row 5) papers over the unresolved cross-module contract.

### What would make it a 10

Fix Problem 1 (align with ARCH-09 matrix — M9 calls M1+M5, is called by M12, not M6). Fix Problem 2 (attribute p50/p95/p99 to M9's DECISION-LOG, cite ARCH-07 only for <500ms). Fix Problem 3 (real M6 `VendorAdapter` Protocol shape, no `handler=`/`tool_name=`/`timeout_ms=` kwargs). Fix Problem 4 (decide firm vs client archetype, rewrite examples consistently). Downgrade Problem 5 to PENDING-CONFIRM-WITH-M8.

---

## 3. Security — 8.6/10

Strongest dimension. The spec treats MNPI as a first-class hazard and instruments it with multiple layers.

### Evidence

- **MNPI pre-scan runs BEFORE the LLM call (R8 AC8.4).** No Bedrock exposure surface for MNPI-shape utterances. ~1 ms overhead, saves 150–400 ms on bad paths anyway (DECISION-LOG 4).
- **SHA-256 of raw utterance is the ONLY utterance identifier in audit (AC8.1, AC9.4).** Raw utterance never propagates. Canary test in Task 15 and Task 10 asserts no substring match.
- **MNPI category never leaks to audit (AC8.6, AC11.6, Invariant A16).** `reason_code="mnpi_shape_suspected"` is the only MNPI-related code. No `ssn_suspected`. Meta-test scans `VALID_REASON_CODES` for `ssn/routing/bank/account_number` substrings.
- **Zero credentials in code (R14).** boto3 default credential chain (IRSA → instance metadata → env → Vault). AC14.1 regex scan over every source + `pyproject.toml`. AC14.4 `.env.example` contains region / provider / timeout placeholders only.
- **Audit via `print()` only, NOT `logging` (AC9.7, AC13.1, AC13.5).** `logging` forbidden in R13 because formatters/handlers/filters could inadvertently leak raw utterance. `print(` usage asserted to exist in exactly ONE place. Matches M7 / M11 discipline.
- **Forbidden imports AST scan (AC13.1).** `logging`, `requests`, `httpx`, `urllib`, `urllib3`, `langchain`, `langgraph`, `anthropic`, `openai`, `warnings`, `tempfile`, `socket`, `subprocess`, `aiohttp`, `grpc`, `google.cloud`, `azure.*`. Covers usual side channels plus competitive-framework coupling hazards.
- **Positive allow-list module boundary (R12 AC12.2).** `m3_schema_registry.{types, enums}` + `m5_config_loader.{Archetype, Runtime, SpecialistConfig, IntentRouterConfig}`. Better than M7 v1's textual guidance.
- **4xx = no retry (AC7.6, AC3.5).** 4xx is a developer/config defect. Spec explicitly refuses to retry. Correct fail-fast posture.
- **Fail-closed on LLM exhaustion (AC7.4).** If Haiku timeouts AND deterministic fallback returns None, escalate to human. No degraded-mode answer.
- **`boto3` restricted to one file (AC13.3).** Only `llm_client.py` may import boto3. Any other file importing fails the scan. Tight blast radius.

### Weaknesses (HARSH)

- **MNPI false-positive on 9-digit ZIP-plus-four is acknowledged but not instrumented.** §Known Blockers row 7 says "If rate exceeds 2% of utterances in first week, taxonomy/regex tuning is a Phase 3 task" — but there is no AC asserting the `reason_code="mnpi_shape_suspected"` counter is emitted to M10 in a shape Phase 3 can slice. Phase 3 has to re-derive the rate from grep on 12M+ audit lines. Add a concrete telemetry hook now.
- **`FakeLlmClient.classify_latency_ms` does NOT simulate Bedrock 5xx / 4xx / malformed output paths.** Appendix B.1 shows the fake only ever returns a `LlmClassification`. How does Task 15 meta-test construct `llm_error_5xx` / `llm_error_4xx` / `llm_malformed_output` scenarios deterministically? Spec says "one test per reason_code" but doesn't show the mechanism.
- **MNPI regex for `bank_account` is `\b\d{10,17}\b`.** Excludes 9-digit (reserving for routing), but does NOT exclude 13-digit (collides with credit card Luhn-validated numbers — potentially more sensitive than a bank account). No Luhn check. Not a blocker for Phase 2 fail-closed posture, but should be acknowledged.
- **`hashlib.sha256(utterance.encode("utf-8"))` is plain SHA-256 without a tenant-salt.** Two advisors at different tenants typing the exact same utterance produce the same sha. Rainbow-table attack against short/predictable utterances ("What is AAPL price") becomes feasible. Recommend HMAC-SHA-256 with a tenant-scoped key pulled from Vault, or prepend `tenant_id` + nonce before hashing. AC8.1 as written is weaker than it looks.
- **No `.env.example` specified — AC14.4 "if present" hedges.** Either commit to shipping an `.env.example` template or commit to NOT shipping one. "If present" is the M11 v1 class of hedge.
- **AST scan AC12.1 matches `^m8_` module names but not literal `m8.` dotted references inside strings.** AC12.6 / `test_no_m8_string_ref.py` covers string literals — good — but it scans for `"m8_"` and `"m8."` only. The taxonomy DISPATCH hardcodes `"m8.research_pipeline_1"` which literally contains `"m8."`. AC12.6's rule "rejected unless inside documentation strings" has to exempt taxonomy.py. Spec doesn't call out the exemption.
- **No ratelimiter or circuit-breaker INSIDE M9.** AC17.7 delegates to M6. If M6 is down or the dispatcher has a bug, M9 will issue Bedrock calls at unlimited QPS. Add a pure-sentinel local cap (e.g., `threading.Semaphore(max=16)` around `classify`) as defense-in-depth.
- **`warnings` module forbidden (AC13.1) but Pydantic v2 emits `UserWarning` on some misuse paths.** Low risk but possible `RuntimeError` at import time if Pydantic upgrades emit a new warning.

### What would make it a 10

HMAC the utterance hash with a tenant-scoped key. Commit to shipping (or not shipping) `.env.example`. Instrument the MNPI-false-positive rate counter to M10 in a Phase-3-queryable shape. Tighten `FakeLlmClient` to support exception injection per `utterance_sha256`. Add a local Semaphore defense-in-depth.

---

## 4. Testability — 8.0/10

### Evidence

- **Pytest + Hypothesis pinned.** `hypothesis>=6.100`, `pytest>=8.0`, `jsonschema>=4.21` in `[project.optional-dependencies] dev`.
- **Every AC maps to a task citing the AC range.** Full trace.
- **Hypothesis `@composite` worked example shipped in the spec** with 11 intent skeletons, 50-ticker whitelist, 5 pre-computed valid SF 18-char IDs, safe household/account/date lists. `@settings(max_examples=100, deadline=500)`. M7 v1 did not have this.
- **Table-driven confidence threshold test (Task 13)** consumes §Confidence Threshold Table (12 rows) directly.
- **Latency benchmark Task 12** uses `FakeLlmClient(classify_latency_ms=50)`, 500 calls, p50/p95/p99, emits `tests/benchmarks/m9_latency.json`. CI fails if p99 regresses >20%.
- **Determinism property test (Task 11)** asserts `route(u,c).model_dump(exclude={"llm_latency_ms"}) == route(u,c).model_dump(exclude={"llm_latency_ms"})` over ≥100 generated utterances.
- **MNPI negative-path tests (Task 6 + Task 14)** — one positive + near-miss per category. `021000021` Chase NY ABA passes; `123456789` fails ABA.
- **PII-free audit scan (Task 10)** — canary utterance with embedded email/SSN/phone; assert substring NOT in `audit_payload()` string form.
- **Three integration-contract tests** (Task 16). The M8 one explicitly does NOT import M8.

### Strengths

- **Hypothesis strategy PII-safety is explicit.** §Hypothesis Strategy Approach lists why `from_type(RouterContext)` is NOT used — default `st.text()` would generate SSN-shape Unicode → false-positive MNPI hits. Ticker whitelist + pre-computed SF IDs + relative-date whitelist is exactly M7 v2 discipline.
- **Replicability notes** call out that the MNPI property test uses a restricted digit alphabet. Rare in first-pass specs.
- **Task 18 "strategy coverage" test** asserts every intent skeleton is generated ≥20 times out of 500 draws. Prevents silent skew in Hypothesis sampling.
- **Idempotency / no-mutation tests (AC10.5, AC1.6)** — deep-copy before / equality after. Not just "same output" but "inputs unmodified".

### Weaknesses (HARSH)

- **`FakeLlmClient` exception-injection path is undefined.** Task 15 meta-test needs to trigger every one of 12 reason codes. For `llm_timeout`, `llm_error_5xx`, `llm_error_4xx`, `llm_malformed_output`, `taxonomy_mismatch`, `regex_fallback_miss`, the fake must raise the right exception per `utterance_sha256`. Appendix B.1 shows the fake only returning a `LlmClassification`. Extend the fake to accept `responses: dict[str, LlmClassification | Exception]`.
- **No concurrency / thread-safety test.** R1 AC1.5 says "thread-safe. No module-level mutable state". But no `test_route_is_thread_safe` running N threads issuing simultaneous `route()` calls. AST scan isn't enough — Python modules can have mutable global state that only surfaces under load.
- **AC1.8 "returns within `timeout_ms * 2` wall clock in all paths"** — how is this asserted deterministically? A real `LlmTimeoutError` requires the boto3 client to actually time out. Spec doesn't pin the test mechanism.
- **No test for confidence=`float("inf")` or `float("-inf")`.** AC5.7 covers `NaN`. Pydantic `Field(ge=0.0, le=1.0)` should reject them, but worth a row.
- **§Confidence Threshold Table row "Invariant violation"** says "Loader fails at startup" but no test asserts this. Add `test_config_invariant_rejected`.
- **Hypothesis `@settings(max_examples=100, deadline=500)` budget is tight.** 100 × 500 ms = 50 s worst case per property test. 3 property files = 150 s. The "<60 s CI" claim is tight. Either tighten `deadline=200` OR acknowledge the 150 s budget honestly.
- **No test for `IntentRouterConfig.fallback_enabled=False` + `LlmProviderError(4xx)`.** AC7.6 says 4xx always escalates regardless of fallback setting. Table-driven test doesn't enumerate this row.
- **No meta-test for `m9_audit_payload.schema.json`** against JSON Schema 2020-12 meta-schema. AC9.8 validates audit payloads against the schema; also assert the schema itself validates against the 2020-12 meta-schema.

### What would make it a 10

Pin the `FakeLlmClient` exception injection mechanism. Add a concurrency smoke test. Add the confidence-infinity row. Pin deadline / CI budget honestly. Add `fallback_enabled=False + 4xx` table row. Meta-validate the audit schema.

---

## 5. Design Alignment — 6.5/10

Weak. The Design Alignment dimension takes hits from the Accuracy problems above — specifically the dependency matrix misread and the invented VendorAdapter kwargs.

### Evidence

- **ARCH-07 M9 row:** `| M9 Intent Router | Python | LLM function calling |`. Spec banner matches.
- **ARCH-09 M9 row:** `| M9 | Intent Router | BUILD | Python | LLM function calling | ~300 | Natural language to structured FSI intent. Confidence thresholds. |`. Spec estimated-lines matches.
- **ARCH-09 ASCII diagram:** `M9 Intent Router (Haiku, LLM function calling, <500ms)`. Spec aligns on "<500 ms" at the high level (but fabricates the percentile breakdown).
- **ARCH-09 Phase 2 build order:** Phase 2 = M7 + M11-REST + M9 + M8 + M12. M9 spec places itself in Phase 2. Consistent.
- **Steering Rule 7** (M6 gateway mandatory): R17 + R18 + §Architecture Clarification thread the needle so M9 never calls a tool itself.
- **Steering Rule 13** (Haiku for routing): R3 (`BedrockHaikuClient`). Correct model.
- **Steering Rule 14** (NO LLM for compliance): R2 AC2.3 routes `compliance.question` to `escalate` kind; NEVER to an LLM-generated answer. Appendix A A4 import-time assertion. Correct.
- **Steering Rule 15** (LLM provider abstracted): R4 `LLMProvider` Protocol + 1 real + 1 fake + 3 stubs. Correct.
- **Steering Rule 20** (zero credentials): R14 + Task 2. Correct.
- **Steering Rule 32** (per-module security): R8 + R9 + R12 + R13 + R14. Correct.

### Strengths

- **ARCH-04 v2 "LangGraph excluded" for M9** — correctly excludes LangGraph from M9 and leaves it to M8. AC13.1 forbids `langgraph` import.
- **M6's `VendorAdapterError.kind` frozen vocabulary (`unavailable`, `error`) is preserved** via R17's pass-through shape. M9 never raises `VendorAdapterError` directly.
- **Runtime-agnosticism** — spec says both Managed Agents and Strands call M9 through M6 identically. Correct per Steering Rule 3.
- **Pure library, not a service** — Architecture Clarification block heads off "FastAPI or library?" review friction.

### Weaknesses

- **Problem 1 from §Accuracy repeats here.** ARCH-09 dependency matrix says M9 calls M1+M5 and is called by M12. Spec says M9 calls M3+M5 and is called by M6. Either ARCH-09 is wrong (architect sign-off to override) or spec is wrong (R12, R17, R18, §Integration Points, Task 2 allow-list all need update). #1 design-alignment defect.
- **Problem 3 from §Accuracy repeats here.** `VendorAdapter(name=..., tool_name=..., handler=..., timeout_ms=...)` constructor signature in §Integration Point with M6 does not match real Protocol. An integration test written against the spec will not compile against real M6.
- **ARCH-05 v2 §Supervisor Routing Logic pseudocode** shows `intent_router.classify(user_message, aid)` called DIRECTLY by the Supervisor with `aid` (AgentIdentityDocument from M1) as argument. M9 spec's `RouterContext` has NO `identity` or `aid` field. If the supervisor is supposed to pass M1's AID to M9 for identity-verification (per steering), the context shape is missing the field.
- **M12 is never mentioned in §Dependencies.** ARCH-09 says M12 calls M9. Spec treats M12 as nonexistent. Add M12 to §Consumers or argue why ARCH-09's `M12 → M9` row is wrong.
- **`client.household_summary` routes to a `pipeline` kind** (`m8.research_pipeline_3`) even though the intent prefix is `client.*`. Invariant A7's regex and AC2.6 are satisfied, but the architectural storyline that `client.*` routes to the Client Service Specialist while `SelectedTarget.kind == "pipeline"` routes to the Research Pipeline is confusing. Pick one.
- **Steering Rule 8 (fail-closed) is NOT in the §Steering Rules M9 Must Honor table** even though §Taxonomy Invariants cites "Steering Rule 8 invariant" and multiple ACs depend on it. Add.

### What would make it a 10

Align with ARCH-09 dependency matrix or DECISION-LOG an intentional override. Fix the VendorAdapter shape. Add `identity: AID` (or `aid`) to RouterContext per ARCH-05 v2. Add M12 to §Consumers. Resolve the `client.household_summary → pipeline` naming conflict. Add Steering Rule 8 to the steering-rules table.

---

## 6. Gaps — 6.5/10

### Evidence

- §Known Blockers table with 8 rows (3 PENDING-VERIFICATION, 1 SHARED-WITH-M5, 4 RESOLVED).
- §Review Fix Traceability placeholder (to populate at v0.2.0).
- Appendix D Cross-Reference Placeholder binds M9 to M6, M8, M10, M5, M3, ARCH-04 v2, ARCH-05 v2, ARCH-07, ARCH-09, IMPL-06, steering file.

### Strengths

- **Known Blockers are genuine** — `IntentRouterConfig` M5 shape unresolved, Bedrock region model-ID verification, Bedrock Converse API tool_use shape validation, Haiku latency variance, taxonomy versioning, fallback coverage gap, MNPI regex false-positive rate, tool_use determinism.
- **Cross-reference maintenance rules** name the triggering events for each downstream update. Operationally actionable.

### Weaknesses (HARSH)

Nine items absent that should be present:

1. **ARCH-09 dependency matrix mismatch itself is not logged as a blocker.** The #1 structural issue is not in the blockers table. Should be a row as `SHARED-WITH-ARCH-09` until architect decides.
2. **Identity (M1 AID) integration is not mentioned.** Steering file says "M9 calls M1 for identity verification". Spec treats this as nonexistent.
3. **M12 consumer is not mentioned.** ARCH-09 `M12 → M9: *`. Spec banner lists only M6 and M8.
4. **Schema-drift policy for taxonomy RENAME.** AC18.4 handles ADD; no policy for RENAME or REMOVE of a pipeline/tool target name. Audit consumers query on `selected_target.name`.
5. **Multi-tenant utterance SHA collision.** Two tenants hashing same utterance → same sha → attacker can correlate across tenants.
6. **No concurrency limit inside M9.** AC17.7 delegates to M6. If M6 has a bug, M9 issues unlimited QPS.
7. **`FakeLlmClient` exception injection mechanism.** Required to exercise 6 of 12 reason codes but not designed.
8. **Task 19 referenced but not defined.** A7 and A17 invariants cite it.
9. **No vendor-lock-in risk on `hashlib.sha256` algorithm choice.** FIPS mode or post-quantum migration would force SHA-3 / BLAKE3. No abstraction seam.

### What would make it a 10

Add all 9 to §Known Blockers or a §Gaps Resolution table. Log the ARCH-09 matrix mismatch explicitly.

---

## Required Fixes (numbered)

Must be fixed before re-review. Expectation: full spec rewrite targeting v0.2.0 with §Review Fix Traceability populated, like M7 v0.1.0 → v0.3.0 and M11 v0.1.0 → v0.2.0.

1. **Reconcile with ARCH-09 dependency matrix (row M9 + column 9).** Matrix says M9 calls M1 and M5, and M9 is called by M12 (not M6). Spec says M9 calls M3 and M5, and M9 is called by M6. Either (a) rewrite R12 positive allow-list to add `m1_agent_identity`, rewrite R17 as "Integration Point with M12", update §Consumers, update §Architecture Clarification; or (b) override ARCH-09 with an architect-signed DECISION-LOG entry plus an ARCH-09 erratum. Do not ship v0.2.0 with the contradiction unresolved.

2. **Stop citing ARCH-07 for the p50<200 / p95<500 / p99<1000 latency targets.** ARCH-07 publishes `<500 ms` for Supervisor Haiku. The percentile granularity is an M9-originated SLO. Move to DECISION-LOG with rationale, cite ARCH-07 only for `<500 ms`.

3. **Fix the M6 `VendorAdapter` Protocol shape in §Integration Point with M6.** Real Protocol: `name: str` + `call(*, tool_name, payload) -> Any`. No `handler=`, `tool_name=`, `timeout_ms=` kwargs on construction. No `M6_REGISTRY.register(...)` public API. Rewrite the registration block with a class that implements the real Protocol, or mark the registration shape SHARED-WITH-M6 PENDING.

4. **Resolve `RouterContext.archetype` type confusion.** AC1.2 imports `Archetype` from M5 (firm-level: `tier1_investment_bank`..`tier5_hedge_fund`). Examples use `"mass_affluent"` (client-level per M3 `Client.archetype`). Pick firm or client, update type + all examples + all Hypothesis strategy inputs consistently.

5. **Fill in Task 19.** Invariants A7 and A17 cite "Task 19 cross-module version-match test" but §Tasks has Tasks 1–18 only. Either add Task 19 (assert `TAXONOMY_DISPATCH` tool-kind names are a subset of M6's registered tool set AND pipeline-kind names are a subset of M8's exported `PIPELINE_NAMES`) or re-point A7/A17 to an existing task.

6. **Downgrade `m8.research_pipeline_1/2/3/single_tool` and `m6.composed_goal_tracking` to PENDING-CONFIRM-WITH-M8/M6.** Names are invented; no design doc publishes them. Current §Known-Blockers status `RESOLVED` is misleading.

7. **Declare M12 as a consumer (or explicitly rebut ARCH-09's `M12 → M9` row).** ARCH-09 matrix says M12 calls M9. Spec §Consumers names only M6 and M8.

8. **Add `identity: AgentIdentityDocument` (or equivalent M1 field) to `RouterContext`.** ARCH-05 v2 §Supervisor Routing Logic passes `aid` to `intent_router.classify(user_message, aid)`. Steering rule says M9 calls M1 for identity verification. `RouterContext` has no identity field.

9. **Specify `FakeLlmClient` exception-injection mechanism.** 6 of 12 `VALID_REASON_CODES` cannot be exercised in Task 15 without a fake that can raise the right exception per `utterance_sha256`. Either extend `FakeLlmClient.responses` to accept `Exception` values or ship a second `ExceptionInjectingFakeLlmClient`.

10. **HMAC the utterance SHA with a tenant-scoped key.** Current `hashlib.sha256(utterance.encode("utf-8"))` (AC8.1) enables cross-tenant utterance correlation via rainbow table on short/predictable utterances. Prepend `tenant_id` + Vault-resolved nonce OR switch to `hmac.new(tenant_key, utterance, sha256)`.

11. **Resolve the `client.household_summary → m8.research_pipeline_3` naming conflict.** Either rename the intent to `research.household_summary` or route to a `tool`/`specialist` kind (matches `client.*` prefix).

12. **Add Steering Rule 8 (fail-closed) to §Steering Rules M9 Must Honor.** Rule is cited in §Taxonomy Invariants and multiple ACs but missing from the steering table.

13. **Specify how `route()` `timeout_ms * 2` wall-clock guarantee (AC1.8) is tested deterministically.** Either add a `SlowFakeLlmClient(block_ms=N)` that blocks past `timeout_ms` or inject `LlmTimeoutError` from the fake.

14. **Disambiguate `test_no_m8_string_ref.py` (AC12.6) vs taxonomy.py.** The taxonomy file literally contains `"m8.research_pipeline_1"` — the very string AC12.6 says is rejected. Add taxonomy.py to the exemption list explicitly.

---

## Recommended Fixes (nice-to-have, numbered)

These are desirable but not blockers for the 8.0+ threshold.

1. **Instrument `reason_code="mnpi_shape_suspected"` counter with tenant dimension** so Phase 3 can slice false-positive rate per tenant without regrepping audit lines.
2. **Add a `SlowFakeLlmClient` or parametric `block_ms` to `FakeLlmClient`** so timeout path can be tested without monkey-patching.
3. **Add concurrency smoke test** (e.g., 50 threads × 20 `route()` calls) to Task 12 benchmark.
4. **Add `float('inf')` / `float('-inf')` rows to §Confidence Threshold Table and Task 13.**
5. **Tighten Hypothesis `deadline=200` or publish honest total CI budget** (3 property files × 100 examples × 500 ms ≈ 150 s).
6. **Add a `fallback_enabled=False + 4xx` row to the confidence/error test table.**
7. **Commit to shipping an `.env.example` with placeholder values, or explicitly do not ship one.** `if present` in AC14.4 is hedging.
8. **Add defense-in-depth `threading.Semaphore(max=16)` inside M9** in case M6 rate-limiter has a gap.
9. **Add a meta-test that validates `schemas/m9_audit_payload.schema.json` itself against JSON Schema 2020-12 meta-schema.**
10. **Tighten the `bank_account` MNPI regex to exclude Luhn-valid 13-/16-/19-digit sequences** OR explicitly accept fail-closed over-match as desirable.
11. **Pin the SF 18-char checksum algorithm more precisely in AC6.3** (base-32 alphabet `ABCDEFGHIJKLMNOPQRSTUVWXYZ012345`, three 5-bit groups, each bit = uppercase flag).
12. **Add a rename-policy DECISION-LOG entry** for how audit-consumer queries survive a `selected_target.name` rename (alias table? deprecation window? major bump only?).

---

## Final Verdict

**7.42 / 10 — CONDITIONAL GO.**

The spec is structurally in the top quartile of first-pass specs in this project. 18 atomic tasks, AC-indexed tests, Hypothesis strategy worked upfront, closed frozen reason-code vocabulary, positive-allow-list boundary scan, MNPI fail-closed pre-LLM, SHA-256 audit with no raw utterance, boto3-only-in-one-file discipline, zero `logging` module, explicit §Known Blockers. That is what a Phase 2 intelligence-layer module should look like at v0.1.0.

But it is blocked on four accuracy misses that are categorically the same as M7 v1 and M11 v1: **the spec treats integration seams as solved when they are not.** M9 claims an ARCH-09 dependency relationship that ARCH-09 does not state, cites ARCH-07 for latency granularity that ARCH-07 does not publish, invokes an M6 `VendorAdapter` Protocol shape that M6 does not define, and mixes the M5 firm-Archetype enum with the M3 client-archetype string. Each miss alone is fixable in a surgical patch; together they describe a spec that treated the source-of-truth files as confirmatory rather than authoritative.

M7 v1 → v2 and M11 v1 → v2 have the playbook. Rewrite §Integration Point with M6 against the real Protocol. Add a §Review Fix Traceability table populated by the 14 Required Fixes. Log the ARCH-09 discrepancy in §Known Blockers and get architect sign-off (or realign). Resolve the firm-vs-client archetype confusion.

Target for v0.2.0: 8.2+ and GO. The structural work is much smaller than the M3 v1 → v2 rewrite or the M11 v1 → v2 rewrite — this is a patch, not a redesign. But the patch must be honest about which claims were assertions rather than verifications, and must move each PENDING from RESOLVED back to PENDING until the cross-module owner signs.
