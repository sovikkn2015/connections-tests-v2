# LLMJ-v2 Review — M8 Pipeline Engine Spec v0.2.0

> Reviewer: Independent LLM Judge (LLMJ-v2)
> Target: `my-agent-project-007-fsi-interoperability/.kiro/specs/m8-pipeline-engine.md` v0.2.0 (2,014 lines)
> Prior: v0.1.0 scored **7.63 / 10 — CONDITIONAL GO** (LLMJ-v1, 2026-05-18). v0.2.0 is a fix pass targeting ≥ 8.0 GO.
> Date: 2026-05-20
> Calibration set: M7 v0.3.0 (8.45), M11 v0.2.0 (8.30), M9 v0.2.0 (8.25), M1 v0.2.0 (8.50), M10 v0.2.0 (8.35), M2/M4 v0.2.0 (8.40), M6 v0.2.0 (8.20)
> GO threshold: ≥ 8.0 / 10. CONDITIONAL GO < 8.0.

---

## Weighted Score Table

| # | Dimension | Weight | Raw | Weighted | Δ vs v1 | Notes |
|---|-----------|-------:|----:|---------:|--------:|-------|
| 1 | Completeness | 25% | 9.0 | 2.25 | +0.13 | AC5.8 zero-fan-out, AC8.11 exactly-once slow alert, AC9.8 escalation-persists-across-checkpoint, AC9.9 interrupt ordering, AC18.8 resume idempotency, new AuditClient module. 24 invariants. 20 tasks with reason-code coverage matrix. |
| 2 | Accuracy | 20% | 8.5 | 1.70 | +0.50 | All five v1 cross-module shape-drift bugs resolved against real M6 + M3 source. Every residual reference to the old shapes is in review-traceability / changelog context, correctly labeled historical. |
| 3 | Security | 20% | 8.5 | 1.70 | +0.10 | AC13.5 print discipline now AST-inspects call arguments for `prompt`/`payload`/`result`/`raw`/`text`. AC4.12 HMAC rotation contract with quarterly cadence + pod-boundary failure mode documented. Vault + mTLS preserved. |
| 4 | Testability | 15% | 8.5 | 1.28 | +0.07 | Per-task reason-code coverage matrix on Tasks 14/16/17. Hypothesis CI budget fixed at 20 / local 50. `CheckpointerWithAuditSpy` for interrupt ordering. A12 now walks a field that actually exists. |
| 5 | Design Alignment | 10% | 8.0 | 0.80 | +0.05 | `langchain-aws` deviation surfaced to Known Blockers row 17 with explicit ARCH-04 v2 update request. SHARED-WITH-M5 (PipelineConfig) + SHARED-WITH-M6 (vendor adapter resolution) + SHARED-WITH-M10 (/audit endpoint) all filed as blockers. |
| 6 | Gaps | 10% | 8.0 | 0.80 | +0.05 | R11 + R12 from v1 recommended list integrated (slow-alert exactly-once, resume idempotency). Outstanding: audit-outage circuit breaker (R9), `dropped_instruments` into brief (R10), tenant-scoped checkpointer key (R8) — all explicitly deferred. |
| | **TOTAL** | 100% | | **8.53** | **+0.90** | **GO** — clears the 8.0 threshold cleanly. Matches M7 v0.3.0 / M11 v0.2.0 / M9 v0.2.0 fix-pass trajectory. |

---

## Verdict: **8.53 / 10 — GO**

v0.2.0 is a textbook fix pass. Every one of the 12 Required Fixes is closed against the actual source-of-truth code in `src/m6_mcp_gateway/gateway.py`, `src/m3_schema_registry/types.py`, `src/m9_intent_router/taxonomy.py`, and 006 `pipeline.py`. Every Required Fix has a traceable landing location in the spec — R-section ACs, invariant table, task list, error code map, Known Blockers, and DECISION-LOG — with cross-references that survive spot-check. Seven of fourteen Recommended Fixes (R1-R5, R11, R12) are integrated cleanly; the other seven are explicitly deferred with rationale.

The spec is now ready to implement. Task 1 (bootstrap `GatewayClient` + `AuditClient` + `LLMClient` Protocols) will no longer fail at the first M6 call, because the `_invoke_tool` helper now resolves a real `VendorAdapter` via `VendorAdapterResolver.resolve(tool_name)` and the response-handling path catches `GatewayError` and branches on `exc.reason` across all 11 members of M6's `VALID_GATEWAY_REASONS`.

---

## Fix Verification Table — One Row Per LLMJ-v1 Required Fix

Verified via direct inspection of v0.2.0 spec + ground-truth source.

| # | v1 Required Fix | v0.2.0 Landing | Status | Ground-Truth Check |
|---|-----------------|----------------|--------|--------------------|
| 1 | M6 `GatewayRequest`/`GatewayResponse` Pydantic-vs-`@dataclass(frozen=True)` drift | AC7.2 rewritten with dataclass + verbatim field list; Appendix B.4 skeleton; Task 20 `test_m6_shape_match.py` asserts via `dataclasses.fields()`; Changelog v0.2.0 bullet (1); Review Fix Traceability row 1. | **RESOLVED** | `src/m6_mcp_gateway/gateway.py` line 118 `@dataclass(frozen=True)` + line 221 confirmed. Field list in AC7.2 matches M6 line 118-133 verbatim: `token, action, tool_name, mcp_server, payload, trace_id, firm_id, target, context, session_id, vendor_adapter`. |
| 2 | `vendor_adapter=None` at `_invoke_tool` would raise `ValueError` at M6 `__post_init__` | AC7.3 introduces `VendorAdapterResolver` Protocol with `resolve(tool_name: str) -> Any`; `_invoke_tool` helper calls `resolver.resolve(tool_name)` BEFORE constructing `GatewayRequest`; `LocalVendorAdapterResolver` production impl in B.4; SHARED-WITH-M6 Known Blocker row 6 documents M6 v0.3.0 "server-side adapter resolution" preferred long-term path; Task 1 deliverable updated. | **RESOLVED — workaround; SHARED-WITH-M6** | `src/m6_mcp_gateway/gateway.py` line 196-204 `__post_init__` confirms `vendor_adapter is None → raise ValueError`. `_invoke_tool` now passes resolved non-None adapter. |
| 3 | M6 failure paths `raise GatewayError(reason)` not return DENY-shaped response | AC7.9 rewritten with `try / except GatewayError as exc` and branch per each of 11 `VALID_GATEWAY_REASONS` members; §M6 Gateway Call Pattern Response Handling rewritten with `_call_with_branching` helper; Error Code Map rows 12 and 13 explicitly note "v0.2.0 REWRITTEN from GatewayResponse.decision == DENY"; Task 15 `test_gateway_error_branches` exercises every reason via `FakeGatewayClient` exception injection. | **RESOLVED** | `src/m6_mcp_gateway/gateway.py` line 66-77 confirms 11-member `VALID_GATEWAY_REASONS` frozenset. AC7.9 enumerates all 11. |
| 4 | M6 has no `emit_audit()` method | New `AuditClient` Protocol with single `emit(entry: dict) -> None` at AC8.10; `M10AuditClient` production impl + `FakeAuditClient` + `AuditEmitError` in Appendix B.5; AC7.1 reduced `GatewayClient` Protocol to single `call()` method; R18 rewritten to route audit via `AuditClient` to M10 FastAPI `/audit`; `__all__` grows to 24 names (AC15.1); SHARED-WITH-M10 Known Blocker row 18; Task 19 xfail until M10 v0.3.0. | **RESOLVED — workaround; SHARED-WITH-M10** | `TrustAwareGateway` public surface is `call()` + `health()` only (verified at M6 gateway.py). No `emit_audit`. AuditClient Protocol sidesteps correctly. |
| 5 | `Holding.cost_basis_method` does not exist | State Field Invariant "Cost basis preservation" rewritten to walk `holding.tax_lots[*].cost_basis_method`; A12 rewritten; Error Code Map row 20 trigger rewritten; AC12.2 allow-list adds `TaxLot` + `CostBasisMethod` (and drops `ComplianceCheck`); Hypothesis strategies `holding_with_tax_lots` + `tax_lot_with_method`; Task 11 `test_cost_basis_preserved::test_all_tax_lots_have_method`. | **RESOLVED** | `src/m3_schema_registry/types.py` line 719-721 `Holding` docstring: "Does NOT have cost_basis_method — that is on TaxLot" confirmed. `TaxLot.cost_basis_method` at line 698 with `@field_validator cost_basis_method_never_null` confirmed. A12 walks the real field. |
| 6 | 006 stage-name drift vs "verbatim preservation" claim | Phase 2 Scope bullet 1 rewritten to acknowledge two deliberate renames; FSI Pipeline Stage Catalog gains "006 Name" column with `[RENAMED vs 006]` markers for stages 12 and 21; §Stage Name Immutability Contract discusses v0.1.0 → v0.2.0 no-rename policy; DECISION-LOG D13 added with full rationale per stage (stage 12 reduce scope; stage 21 anti-fab + HITL hybrid). | **RESOLVED** | 006 `pipeline.py` line 112-128 confirmed — 006 has `_stage_12_sentiment_synthesis` and `_stage_21_final_approval_gate`. Stage NUMBERS 1-23 are bijective preserved; stage NAMES diverge only at 12 and 21 as D13 states. |
| 7 | 10-vs-20 reason code global inconsistency | Global sweep verified: Changelog v0.1.0 bullet 9 now "20 codes in v0.1.0"; Phase 2 Scope bullet 9 "20 `reason_code` values"; R11 header "Closed Frozen Set (**20 Codes**)"; DECISION-LOG D7 rewritten to "20 reason codes in v0.1.0 (vs. original target 10) — reconciled in v0.2.0". AC11.1 + Error Code Map + Task 15 unchanged (already 20 in v0.1.0). | **RESOLVED** | No active contract references "10 codes". All six v1 locations now say 20. Remaining "10 codes" reference is in Review Fix Traceability row 7 describing the v1 bug, correctly historical. |
| 8 | `langgraph.constants.Send` deprecated; version pin two majors stale | Appendix B.2 skeleton `from langgraph.types import Send`; AC12.7 pin `langgraph>=0.4,<2.0` (was `>=0.2.0,<0.3`); AC13.2 third-party allow-list adds `langgraph.types`; Banner Language row updated; Task 5 `test_graph_assembly.py` asserts the import path. | **RESOLVED** | Spec line 1591 shows `from langgraph.types import Send` with comment "v0.2.0 — was `from langgraph.constants import Send` (deprecated since V1.0)". Only residual reference to the old path is this historical annotation. |
| 9 | `ComplianceCheck` allow-listed but never populated | `ComplianceCheck` dropped from AC12.2 allow-list; `compliance_check` field dropped from `PipelineState` with explicit comment in state.py skeleton marking the drop; stage 20 emits `compliance_decision` + `compliance_rule_applied` + `compliance_wsp_section` + `compliance_escalation` which suffice. | **RESOLVED — simpler path chosen** | AC12.2 verified: allow-list reads `...TaxLot, CostBasisMethod, Valuation, Beneficiary` — `ComplianceCheck` absent. State schema snippet has explicit comment "v0.1.0 had: compliance_check: Optional[ComplianceCheck] -- DROPPED v0.2.0 (Req-Fix 9)". |
| 10 | `langchain-aws` deviation buried in DECISION-LOG | Known Blockers row 17 added (ARCH-04 v2 `langchain-aws` deviation — Req-Fix 10) with "PENDING-ARCH-04-UPDATE" status and rationale (LangChain umbrella would violate Steering Rule 15 provider abstraction). AC13.8 references the row. Changelog v0.2.0 bullet (9) notes the elevation. | **RESOLVED — elevated visibility; ARCH-04 v2 update still pending** | Known Blockers row 17 verified present. Banner also explicitly cites row 17. AC13.8 cross-references correctly. |
| 11 | AC13.5 `print` discipline too lax | AC13.5 rewritten to require "digest-only audit line; raw payload never printed" + source-level AST scan. `test_print_discipline` scans every `print(` call and asserts no variable named `prompt`, `payload`, `result`, `tool_result`, `raw`, or `text` is passed as an argument. Task 2 adds the deliverable. A20 invariant updated. | **RESOLVED** | AC13.5 verified to AST-inspect call arguments by variable name. Enforceable; not an easy bypass. |
| 12 | HITL HMAC key rotation contract missing | AC4.12 new: quarterly 90-day rotation aligned with 24hr mTLS rotation cycle; pod-restart-triggered re-fetch (no in-flight rotation; pods are cattle); in-flight HITL gates across rotation boundary emit `m8_hitl_token_expired`; Task 8 `test_hitl_key_rotation` exercises cross-pod key divergence; Gate Invariants "Key-rotation invariant (v0.2.0)" added; DECISION-LOG D15 added. | **RESOLVED** | AC4.12 + D15 + A14 all coherent. Reason code `m8_hitl_token_expired` already in VALID_REASON_CODES — no set expansion needed. |

**12 / 12 CLOSED.** Zero PARTIAL. Zero REGRESSED.

---

## Recommended Fix Integration Check

v0.1.0 review called out 14 Recommended Fixes. v0.2.0 integrates 7 of them (R1-R5, R11, R12). The other seven are explicitly deferred to v0.3.0 with written rationale in §Review Fix Traceability:

| R# | Title | v0.2.0 Status | Landing |
|----|-------|---------------|---------|
| R1 | Stage 8 zero-fan-out path | **INTEGRATED** | AC5.8 + `m8.single_tool_bypass` audit event + Task 16 `test_zero_fan_out_single_tool` |
| R2 | `compliance_escalation` survives checkpoint | **INTEGRATED** | A24 invariant + AC3.10 + AC9.8 + Task 9 test |
| R3 | Per-task reason-code coverage matrix | **INTEGRATED** | Tasks 14, 16, 17 each carry an explicit reason-code matrix in the Tasks table |
| R4 | Hypothesis CI / local budget pinning | **INTEGRATED** | `max_examples=20` CI / `50` local, env-gated on `CI=1`; DECISION-LOG D14 |
| R5 | `interrupt()` → checkpointer write order regression guard | **INTEGRATED** | AC9.9 + `CheckpointerWithAuditSpy` helper + Task 9 extension |
| R6 | Cross-module test to M12 spec | DEFERRED | M12 spec not yet drafted |
| R7 | `client_id` MNPI classification cite | DEFERRED | SHARED-WITH-M4; AC8.6 holds current stance |
| R8 | `(tenant_id, thread_id)` compound checkpointer key | DEFERRED | Phase 3 — per-tenant isolation upgrade |
| R9 | Audit-outage circuit-breaker readiness probe | DEFERRED | No Phase 2 Kubernetes-level readiness gate |
| R10 | `dropped_instruments` into `ResearchBrief.sources` | DEFERRED | Phase 3 — observability / brief-shape amendment |
| R11 | `m8.pipeline_slow_alert` exactly-once emission | **INTEGRATED** | AC8.11 + `state.slow_alert_emitted` gate + Task 13 |
| R12 | `resume_from_gate` idempotency | **INTEGRATED** | AC18.8 |
| R13 | ARCH-05 v2 non-interaction statement | DEFERRED | N/A in M8 scope per author rationale |
| R14 | Rules 9/10/17/19 in Steering trace | DEFERRED | Rationale: N/A in M8 scope |

All 7 deferrals carry a named reason. None are silent drops.

---

## Dimension-by-Dimension Analysis

### 1. Completeness — 9.0 / 10 (Δ +0.5)

**Evidence**
- 23 stages pinned with 006-name column + `[RENAMED vs 006]` markers on stages 12 and 21.
- 3 HITL gates, every gate fully specified (trigger, approver, token, timeout, rejection, role mismatch, key rotation behavior).
- 20 reason codes, one Error Code Map row each, every code reachable through a documented task (Tasks 14/16/17 reason-code coverage matrix).
- 24 pipeline invariants (was 23 in v0.1.0); A24 added for `compliance_escalation` checkpoint persistence.
- 18 Known Blockers (was 16); row 17 (`langchain-aws` deviation) + row 18 (M10 `/audit` endpoint) added.
- 20 atomic tasks, each citing the AC it satisfies.
- Appendix B expanded: B.4 new `gateway_client.py` skeleton with dataclass shapes + `VendorAdapterResolver`; B.5 new `audit_client.py` skeleton.
- DECISION-LOG gains D13 (renames justification), D14 (Hypothesis CI budget), D15 (HMAC rotation cadence).

**Strengths**
- Zero-fan-out path (AC5.8) closes the `m8.research_single_tool` case that would have emitted a spurious `m8_map_reduce_all_failed`.
- `m8.pipeline_slow_alert` exactly-once (AC8.11) prevents alert storms as a pipeline crosses the 15-min threshold mid-stage-chain.
- Resume idempotency (AC18.8) closes the "double audit on redelivered approval" class of bug.

**Weaknesses**
- M12 integration test (Task 20) is xfail-pending-on-M12-spec. Correct choice given M12 isn't drafted yet, but carries forward.
- Phase 3 deferrals for `dropped_instruments` propagation into `ResearchBrief.sources` means RIA advisors do not yet see coverage gaps in the brief; M8 captures the data in audit but not in the deliverable.

**Score delta**: +0.5. v0.1.0 was already 8.5 here; the additional AC coverage (5.8, 8.10, 8.11, 9.8, 9.9, 18.8) plus the new audit module push this to 9.0.

### 2. Accuracy — 8.5 / 10 (Δ +2.5)

**Evidence**
- AC7.2 field list for `GatewayRequest` matches `src/m6_mcp_gateway/gateway.py` line 118-133 verbatim: `token, action, tool_name, mcp_server, payload, trace_id, firm_id, target, context, session_id, vendor_adapter`.
- AC7.9 enumerates all 11 members of M6's `VALID_GATEWAY_REASONS` frozenset (verified at `gateway.py` line 66-77): `invalid_identity, authority_denied, authority_escalated, mnpi_filter_error, circuit_open, rate_limited, vendor_unavailable, vendor_error, mnpi_leakage_scan, audit_failed, invalid_request`. Every one has a branch.
- State Field Invariant "Cost basis preservation" walks `holding.tax_lots[*].cost_basis_method` — real field, confirmed on `TaxLot` line 698 with `@field_validator cost_basis_method_never_null`. `Holding` docstring line 719-721 says "Does NOT have cost_basis_method" verbatim.
- Phase 2 Scope bullet 1 no longer claims "verbatim preservation"; it acknowledges the two deliberate renames with cross-reference to D13.
- `langgraph.types.Send` import path is correct (deprecated `langgraph.constants.Send` appears only in the annotation comment on the replacement line).
- 006 stage NUMBERS 1-23 all match `_all_stage_methods()` (verified `pipeline.py` line 112-128). Stage NAMES 12 and 21 differ; D13 justifies.
- M9 `TAXONOMY_DISPATCH` pipeline-kind targets include `m8.research_pipeline_1`, `m8.research_pipeline_2`, `m8.research_pipeline_3`, `m8.research_single_tool` (verified `src/m9_intent_router/taxonomy.py` line 64-74) — A4 invariant's `PIPELINE_NAMES ⊆ M9's pipeline-kind names` is feasible and Task 20 `test_cross_module_pipeline_names` is the enforcement.

**Strengths**
- The spec now treats M6 as an external API with a frozen wire contract, rather than as a Python import. This is architecturally cleaner and is the path Steering Rule 13 (strict module boundaries) actually requires.
- `VendorAdapterResolver` Protocol is a careful mirror of M6's internal registry without reaching into M6's private surface. Phase 2 workaround (`LocalVendorAdapterResolver`) has a clean upgrade path to M6 v0.3.0 server-side resolution.

**Weaknesses / Residual Risk**
- The `LocalVendorAdapterResolver` requires M8 to hold a registry snapshot whose contents M6 has not yet formally published. SHARED-WITH-M6 is filed but Phase 2 M8 integration testing will need a M6 v0.2.1 manifest route or an agreed JSON contract. No blocker for spec GO; will surface during Task 19.
- `LiabilityReport` in `GatewayResponse` is typed `Optional[Any]` in M8's dataclass copy; M6's real type is `LiabilityReport` from `compliance.gap2_liability_provenance`. The `dataclasses.fields()` shape-match in Task 20 will assert field NAMES + positions match but not type annotations. Technically correct per Req-Fix 1 (M8 must not import compliance.*); pragmatically acceptable. Document in DECISION-LOG if not already.

**Score delta**: +2.5. v0.1.0's 6.0 was dominated by five cross-module inventions. All five are now verified against source. 8.5 (not 9.0) because the shape-match remains a runtime-asserted test, not a type-system guarantee.

### 3. Security — 8.5 / 10 (Δ +0.5)

**Evidence**
- AC13.5 now AST-scans every `print(` call and asserts no variable named `prompt`, `payload`, `result`, `tool_result`, `raw`, or `text` is among the arguments. Test runs under Task 2. Not bypassable via trivial rename-of-local.
- AC4.12 adds an explicit HMAC key rotation contract: quarterly (90-day) rotation, aligned with 24hr mTLS cert rotation × 90-day aggregate; pod-restart-triggered re-fetch (pods are cattle); in-flight HITL gates across rotation boundary emit `m8_hitl_token_expired`.
- DECISION-LOG D15 captures the rotation policy with rationale.
- Vault resolution preserved: AC14.3 (checkpointer DSN), AC14.4 (HITL HMAC key), AC14.5 (region); zero credentials in code at AC14.1 regex scan.
- mTLS paths preserved: `M6GatewayClient`, `M10AuditClient`, checkpointer DSN all Vault-resolved.
- R11 header + AC11.6 still hold the "no MNPI-category specificity" line; `m8_mnpi_leaked_through_gateway` remains the single MNPI reason code.

**Strengths**
- The rotation contract makes an explicit trade-off: no in-flight rotation preserves correctness (a running HITL gate keeps the cached key) at the cost of some approver-side reissue friction after rotation boundaries. The trade-off is argued, not hidden.
- AC13.5 AST scan is a real improvement over v0.1.0's "allow-list of two files" — it now has semantic content, not just location filtering.

**Weaknesses**
- Rotation frequency (90 days) is lax compared to a 24-hour mTLS rotation. Defensible for a gate-timeout artifact (HITL TTL is 4h; tokens expire well before key rotation) but Phase 3 should consider a shorter cadence when Vault Agent sidecar is standard. Not a blocker.
- `state.supervisor_aid_token` rides in the `PipelineState` and is therefore checkpointed. AC14.8 forbids cleartext AID token persistence in checkpoint rows, but the state TypedDict still types the field as `str`. Minor: a `SecretStr` wrapper or pre-checkpoint redaction would make the invariant self-enforcing rather than test-enforced. Defer to v0.3.0.

**Score delta**: +0.5. v0.1.0 was already 8.0. Rotation contract + AST-based print discipline pushes to 8.5.

### 4. Testability — 8.5 / 10 (Δ +0.5)

**Evidence**
- Tasks 14/16/17 each include an explicit reason-code coverage matrix in the deliverables description. This catches the v1 weakness that "every code is reachable" was asserted abstractly but not per-task.
- Task 15 `test_gateway_error_branches` exercises every `VALID_GATEWAY_REASONS` value (11 of them) via `FakeGatewayClient` raising pre-seeded `GatewayError` instances. Closes Req-Fix 3 testability.
- Hypothesis `max_examples=20 (CI) / 50 (local)` is pinned at `tests/property/strategies.py` module-level with env-gated selection. No more unbounded CI wall-time.
- Task 9 `test_hitl_interrupt_checkpoint_order` uses a `CheckpointerWithAuditSpy` that records `(audit_emit, interrupt_called, checkpoint_put)` order — regression guard against LangGraph internal reordering across version bumps.
- Task 9 `test_compliance_escalation_survives_checkpoint` exercises A24 with `InMemorySaver` round-trip.
- Task 11 `test_cost_basis_preserved::test_all_tax_lots_have_method` walks a field that actually exists; Hypothesis `holding_with_tax_lots` + `tax_lot_with_method` strategies compose correctly with M3's Pydantic validators.
- Task 20 `test_m6_shape_match.py` new: asserts M8's dataclass field lists equal M6's via `dataclasses.fields()` introspection.

**Strengths**
- The `FakeSonnetClient` / `FakeGatewayClient` / `FakeAuditClient` triple gives stages a clean deterministic-replay substrate. `AuditClient` split out cleanly — tests can assert audit-row shape without synthesizing a gateway call graph.
- AC9.9's `CheckpointerWithAuditSpy` is a subtle but important regression guard; LangGraph has changed internal ordering before (observed in V0.x → V1.0).

**Weaknesses**
- Task 18 Bedrock live-call remains gated behind `M8_LIVE=1` env var with no CI scheduled run. Model-ID drift could slip past CI for days. Minor: doc in DECISION-LOG when the first live run will happen. Not a spec defect.
- Task 19 M10 `/audit` contract is xfail-pending-M10 v0.3.0. Correct posture; will need re-activation when M10 v0.3.0 ships.

**Score delta**: +0.5. v0.1.0 was 8.0 (one invariant unimplementable against real M3 shape). With A12 now walking the real field + per-task reason-code coverage + interrupt-ordering regression, testability climbs to 8.5.

### 5. Design Alignment — 8.0 / 10 (Δ +0.5)

**Evidence**
- `langchain-aws` ARCH-04 v2 deviation is now Known Blockers row 17 with "PENDING-ARCH-04-UPDATE" and rationale (Steering Rule 15 provider abstraction). Surfaced, not silent.
- SHARED-WITH-M5 (PipelineConfig), SHARED-WITH-M6 (vendor adapter resolution — row 6), SHARED-WITH-M10 (/audit endpoint — row 18) all filed as blockers with explicit version targets.
- ARCH-09 matrix row M8 = `. * . . * * . . . * . . .` cited three times (banner Dependencies row, §Architecture Clarification, §Phase 2 Scope).
- Steering-Rule Traceability table covers Rules 4, 5, 6, 7, 8, 11, 13, 14, 15, 20, 32 with explicit AC + Task mappings.
- ARCH-06 v3 Gap 2 row for M8 Pipeline is honored: AC8.1 carries stage_number, model_version, prompt_template_version, input_sha256, output_sha256.

**Strengths**
- The three SHARED-WITH blockers make cross-module dependencies visible to the program plan. Phase 2 Week 28 bring-up knows exactly what M5, M6, M10 owe.

**Weaknesses**
- Steering Rule 11 (async dispatch, max 3 concurrent) is enforced by `threading.Semaphore(3)` with 60s block-then-fail. Steering Rule 11 actually says "Queued beyond limit". The block-then-fail is a pragmatic Phase 2 approximation of queuing; Phase 3 Redis-backed queue is deferred (Known Blockers row 16). Defensible; noted in the Phase 2 Scope deferral list.
- `langchain-aws` deviation still awaits an actual ARCH-04 v2 update. Row 17 documents the request, but the architecture document itself hasn't changed yet. Not a spec defect — this is exactly what Known Blockers are for.

**Score delta**: +0.5. v0.1.0 was 7.5 with the `langchain-aws` deviation buried. Surfacing it and filing the other two SHARED-WITH blockers pushes to 8.0.

### 6. Gaps — 8.0 / 10 (Δ +0.5)

**Evidence**
- AC8.11 (`m8.pipeline_slow_alert` exactly-once): `state.slow_alert_emitted` gate + Task 13 assertion.
- AC18.8 (`resume_from_gate` idempotency): second call with same `(thread_id, approval_token)` returns cached result; no second `m8.hitl_gate_approved` audit row.
- AC5.8 zero-fan-out case: stage 12 checks `len(discovered_instruments) == 0` FIRST before checking `per_instrument_results`, emits `m8.single_tool_bypass` and proceeds.
- AC9.8 escalation-persists-across-checkpoint: A24 + `FakeCheckpointer` round-trip.

**Strengths**
- The four gaps closed (R11, R12, R1, R2) cover the most user-visible misbehaviors: alert storms, double-audit on redelivery, false `m8_map_reduce_all_failed` on single-tool queries, and escalation-lost-on-resumption.

**Weaknesses (deferred)**
- Audit-outage circuit-breaker readiness probe (R9): no pod-level load-shedding if M10 `/audit` sustained-failure > 10% / 30s. Phase 3.
- `dropped_instruments` propagation into `ResearchBrief.sources` or a new `dropped_coverage` field (R10): advisors see audit-level coverage gaps but not brief-level. Phase 3.
- Tenant-scoped checkpointer key compound `(tenant_id, thread_id)` (R8): Phase 2 uses `thread_id` alone; Phase 3 isolation upgrade.

**Score delta**: +0.5. The biggest operationally-visible gaps from v1 recommended list are now closed.

---

## New Issues Introduced by v0.2.0

I scanned the v0.2.0 delta against v0.1.0 for regression-class issues. The findings are small.

### N1 [MINOR — Design] — `VendorAdapterResolver` Protocol coupling to M6's internal registry

The `LocalVendorAdapterResolver` (Appendix B.4) wraps a `registry_snapshot: dict[str, Any]` fetched from M6 at compile time. This is a workaround for v1's Required Fix 2 and is explicitly flagged as SHARED-WITH-M6 (Known Blocker row 6). Two sub-concerns:

1. **Phase 2 bring-up requires a M6 `/adapters` route or equivalent**: the spec says "fetched from M6's FastAPI /adapters route at compile time" (near AC7.3), but M6 v0.2.0 does not expose `/adapters` — the M6 spec's public surface is `call()` + `health()` only. Task 19 `test_m8_m5_config_shape.py` is xfail pending M5 v0.4.0, but the corresponding M6 /adapters contract is only tracked in row 6 as "SHARED-WITH-M6 — M6 v0.3.0 to resolve. Phase 2 workaround viable with (b)." Workaround (b) requires M6 to publish the registry INSTANCE that M8 receives at compile time, which is a runtime object exchange — a different contract from a JSON-over-HTTP /adapters route.

   **Recommendation (not blocking)**: add a Phase 2 Week 28 coordination artifact — either a M6 v0.2.1 spec amendment exposing a bootstrap `/adapters` JSON route, OR a documented Python-object hand-off at M12 supervisor construction time. v0.3.0 of M8 should pick one and pin it.

2. **`resolve` contract on unknown `tool_name`**: `LocalVendorAdapterResolver.resolve` raises `GatewayError("invalid_request")` on KeyError. The semantics align with M6's `invalid_request` reason, but this is an M8-constructed `GatewayError`, not an M6 one — the `_invoke_tool` caller's branch on `exc.reason == "invalid_request"` then fires with `reason_code="m8_stage_failed"`, which is pragmatically correct but semantically blends two distinct failure modes (registry miss vs M6 request rejection). A dedicated reason code or pre-call validation would separate them. Not a spec defect — an operational-readability preference.

### N2 [MINOR — Accuracy] — `GatewayResponse.liability_report` typed `Optional[Any]` in M8's dataclass copy

M6's real `GatewayResponse` types `liability_report: Optional[LiabilityReport]` (from `compliance.gap2_liability_provenance`). M8's dataclass copy types it `Optional[Any]` to avoid the `compliance.*` import that R12 AC12.2 + AC12.9 forbid. This is defensible — M8 does not interpret liability reports, it passes them through in audit — and the `dataclasses.fields()` shape-match in Task 20 asserts field NAMES and field POSITIONS match, not the exact runtime types.

**Recommendation (not blocking)**: explicit DECISION-LOG entry (D16?) documenting that type-annotation equality is intentionally relaxed for `liability_report` and `vendor_adapter` (both `Any` in M8's copy, concrete in M6's). The spec implies this is fine; making it explicit survives M6 future-refactor.

### N3 [MINOR — Testability] — AuditClient mTLS cert handling under rotation

`M10AuditClient(base_url, mtls_cert_path, timeout_ms)` loads the client cert at construction time. Under Steering Rule 21 (cert-manager, 24hr rotation), the long-lived `M10AuditClient` instance holds a stale cert after rotation. The existing `M6GatewayClient` has the same concern but is out of scope for this review. AC14.8 doesn't cover runtime cert refresh.

**Recommendation (not blocking)**: pod-local approach is to rely on Kubernetes rolling restart (same as HMAC key rotation per AC4.12). Document in DECISION-LOG that mTLS client cert refresh is pod-restart-triggered, no in-flight refresh. Probably already implied by AC4.12's "pods are cattle" framing but worth making explicit.

### N4 [TRIVIAL — Doc] — Changelog high-level summary says "R1-R5 integrated"; actually seven are integrated

The changelog for v0.2.0 says "Recommended Fixes R1-R5 integrated" in the prose summary but later correctly enumerates R1-R5 + R11 + R12 in §Review Fix Traceability. Seven, not five, are integrated. Minor copy nit; does not affect behavior.

**None of N1-N4 blocks GO.** They are v0.3.0 polish.

---

## Residual-Reference Audit (accuracy regression check)

I scanned v0.2.0 for residual mentions of the v1 incorrect shapes. Every residual reference is in explicitly historical context (Changelog, Review Fix Traceability row, annotation comment on the replacement code line). Zero active contracts use the old shapes.

| Pattern | Total residual references | Acceptable contexts | Active-contract references |
|---------|--------------------------:|---------------------|---------------------------:|
| `GatewayClient.emit_audit` | 7 | Changelog v0.1.0 bullet (7), Changelog v0.2.0 bullet (3), R1 preamble, R8 header, R18 header, §Audit Linkage annotation, Review Fix Traceability row 4 — all marked as v0.1.0 historical and v0.2.0 withdrawn | **0** |
| `Holding.cost_basis_method` | 3 | Banner "Required Fix 5 acknowledges", Review Fix Traceability row 5, Error Code Map row 20 "v0.2.0 corrected per Required Fix 5 — v0.1.0 incorrectly referenced" — all historical | **0** |
| `langgraph.constants.Send` | 3 | Changelog v0.2.0 bullet (7), Review Fix Traceability row 8, Appendix B.2 annotation comment on the replacement `from langgraph.types import Send` line — all historical | **0** |
| "10 codes" / "10 Codes" | 2 | Changelog v0.2.0 bullet (6) describing the fix, Review Fix Traceability row 7 describing the v1 bug — both historical | **0** |
| `Pydantic v2 models matching M6` | 0 | (the v1-bug phrasing is gone entirely) | **0** |

**Zero accuracy regressions.** Every residual reference is labeled historical and in a context where removing it would obscure the fix trace.

---

## Final Verdict

**8.53 / 10 — GO**

v0.2.0 is a clean fix pass on a v0.1.0 that was already structurally strong. All 12 Required Fixes are closed against real source-of-truth code. Seven of fourteen Recommended Fixes are integrated; the remaining seven are explicitly deferred with rationale. Zero accuracy regressions; every residual reference to a v1 incorrect shape is in historical context.

The spec is implementation-ready. Task 1 (bootstrap the three Protocol clients) will succeed against real M6 dataclass shapes. Task 15 (exhaustive reason-code meta-test) covers all 11 M6 `VALID_GATEWAY_REASONS` members plus all 20 M8 `VALID_REASON_CODES` members. Task 20 (M6 shape match via `dataclasses.fields()`) will pass against the committed M6 code. Task 11 (cost-basis-preserved property test) walks a field that actually exists.

Three items to carry forward into implementation — none blocking:
- **N1**: Phase 2 needs a documented M6 `/adapters` bootstrap route OR a Python-object hand-off at M12 supervisor construction. Work with M6 owner in Phase 2 Week 28.
- **N2**: A DECISION-LOG entry making the `Any`-vs-concrete type relaxation explicit for `liability_report` and `vendor_adapter` would survive M6 refactors gracefully.
- **N3**: Pod-restart-triggered mTLS cert refresh (same model as HMAC key rotation per AC4.12) should be stated explicitly, not only implied.

The spec matches the M7 v0.3.0 / M11 v0.2.0 / M9 v0.2.0 / M10 v0.2.0 / M1 v0.2.0 / M6 v0.2.0 / M2/M4 v0.2.0 fix-pass trajectory — every module that went from ~7.3-7.6 CONDITIONAL GO on v1 review has landed in the 8.2-8.5 GO band on v2 review. M8 at 8.53 sits at the top of that band.

**Recommend: proceed to Build step of the 7-step playbook.**

---

## Review Metadata

| Field | Value |
|-------|-------|
| Review Version | LLMJ-v2 |
| Reviewed Spec Version | 0.2.0 |
| Reviewed Spec Lines | 2,014 (+460 over v0.1.0's 1,554) |
| Reviewer | Independent LLM Judge |
| Calibration set | M7 v0.3.0 (8.45), M11 v0.2.0 (8.30), M9 v0.2.0 (8.25), M1 v0.2.0 (8.50), M10 v0.2.0 (8.35), M2/M4 v0.2.0 (8.40), M6 v0.2.0 (8.20) |
| v1 Score | 7.63 / 10 (CONDITIONAL GO) |
| v2 Score | **8.53 / 10 (GO)** |
| Δ | **+0.90** |
| Required Fixes Closed | 12 / 12 |
| Recommended Fixes Closed | 7 / 14 (R1-R5, R11, R12) |
| New Issues (non-blocking) | 4 (N1-N4) |
| Accuracy Regressions | 0 |
| Ground-Truth Files Re-Consulted | `src/m6_mcp_gateway/gateway.py` (lines 58-310 — dataclass shapes, VALID_GATEWAY_REASONS, GatewayError); `src/m3_schema_registry/types.py` (lines 690-740 — TaxLot.cost_basis_method, Holding docstring); `src/m9_intent_router/taxonomy.py` (lines 63-78 — TAXONOMY_DISPATCH pipeline targets); `src/m9_intent_router/models.py` (lines 1-50 — RoutingDecision shape); `my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/openclaw/skills/fsi-research/pipeline.py` (lines 50-128 — HITL_STAGES + _all_stage_methods()) |
