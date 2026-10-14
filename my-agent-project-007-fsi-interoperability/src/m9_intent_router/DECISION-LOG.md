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

## 2026-05-14 — Audit emitted via stdout JSON, not logging

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
**Decision**: `UNSUPPORTED` -> `escalate_to_human` with `reason_code="unsupported_intent_stub"`. Phase 3 adds rejection templates.
**Decided By**: Product + Intent Router Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 1)

**Area**: Module dependency graph
**Decision**: Realign with ARCH-09 dependency matrix. M9 calls M1+M5 (was M3+M5 in v0.1.0 banner). M9 called by M12 (was M6).
**Rationale**: ARCH-09 is the source of truth.
**Decided By**: Pipeline and Intent Specialist after LLMJ-v1 review.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 2)

**Area**: Latency SLO attribution
**Decision**: ARCH-07 cited ONLY for `<500 ms` Supervisor Haiku target. p50<200 / p95<500 / p99<1000 percentile breakdown is an M9-originated SLO.
**Decided By**: Pipeline and Intent Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 4)

**Area**: Archetype semantics
**Decision**: `RouterContext.archetype` is firm-level `Archetype` from M5 (`tier1_investment_bank`..`tier5_hedge_fund`). NOT M3 client-level segmentation.
**Decided By**: Pipeline and Intent Specialist + Supervisor Model owner.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 10)

**Area**: Security / audit hash
**Decision**: `utterance_sha256` switches from plain SHA-256 to HMAC-SHA-256 with tenant-scoped Vault-resolved key.
**Rationale**: Plain SHA-256 enabled cross-tenant rainbow-table correlation on short/predictable utterances.
**Decided By**: Security review + Intent Router Specialist.

## 2026-05-16 — v0.2.0 LLMJ-v1 fix pass (Fix 11)

**Area**: Taxonomy rename
**Decision**: `CLIENT_HOUSEHOLD_SUMMARY` -> `RESEARCH_HOUSEHOLD_SUMMARY`. String value `client.household_summary` -> `research.household_summary`. SCHEMA_VERSION 1.0.0 -> 1.1.0.
**Rationale**: Intent dispatched `kind="pipeline"` -- prefix must align with kind (AC2.9).
**Decided By**: Pipeline and Intent Specialist.

## 2026-05-16 — v0.2.0 Fix 17.4 rename policy

**Area**: Audit contract
**Decision**: Renaming `selected_target.name` is a MAJOR bump. One-minor-version alias window MAY be provided. Audit consumers MUST query on `utterance_sha256` + `intent.value`, NOT on `selected_target.name` alone.
**Decided By**: Pipeline and Intent Specialist + Audit Specialist.
