# LLMJ-v1 Review — M8 Pipeline Engine Spec v0.1.0

> Reviewer: Independent LLM Judge (LLMJ-v1)
> Target: `my-agent-project-007-fsi-interoperability/.kiro/specs/m8-pipeline-engine.md` v0.1.0 (1,554 lines)
> Date: 2026-05-18
> Calibration set: M7 v1 (7.36), M11 v1 (7.27), M9 v1 (7.42)
> GO threshold: ≥ 8.0/10. CONDITIONAL GO < 8.0.

---

## Weighted Score Table

| # | Dimension | Weight | Raw | Weighted | Notes |
|---|-----------|-------:|----:|---------:|-------|
| 1 | Completeness | 25% | 8.5 | 2.13 | 23 stages, 3 HITL gates, 20 reason codes, 20 tasks, 23 invariants, 16 Known Blockers, Appendix B skeleton, `.env.example`, DECISION-LOG seed. |
| 2 | Accuracy | 20% | 6.0 | 1.20 | Three cross-module shape-drift bugs + `Holding.cost_basis_method` misattribution + stage-name drift vs "provenance continuity" claim + internal 10/20 reason-code inconsistency. |
| 3 | Security | 20% | 8.0 | 1.60 | Zero-creds, MNPI residency property, Vault paths, canary scans, AST boundary scan, no OPA inside M8. Solid. |
| 4 | Testability | 15% | 8.0 | 1.20 | Every AC pins a test; deterministic fakes; Hypothesis strategies illustrated. Minor: one invariant (A12) unimplementable against real M3 shape. |
| 5 | Design Alignment | 10% | 7.5 | 0.75 | ARCH-09 matrix cited correctly, Steering Rules traced. Deviation from ARCH-04 v2 "Key Libraries" buried in DECISION-LOG. |
| 6 | Gaps | 10% | 7.5 | 0.75 | HITL, map-reduce, anti-fabrication covered. Missing: escalation-flag persistence, audit back-pressure, stage-8 empty fan-out. |
| | **TOTAL** | 100% | | **7.63** | **CONDITIONAL GO** — above 7.5 bar, below 8.0 GO bar. |

---

## Verdict: **7.63 / 10 — CONDITIONAL GO**

Strong spec structurally (mirrors M7 v0.3.0 / M11 v0.2.0 / M9 v0.2.0 discipline), strong security posture, thorough testability. Pulled down by three accuracy misses against real source-of-truth code (M6 gateway shape, M3 `Holding.cost_basis_method`, 006 stage names) and one doc-consistency defect (10 vs 20 reason codes repeated in three places). All fixable in a v0.2.0 without restructuring. Mirrors the M9 v1 (7.42) pattern — same class of miss (invented cross-module shape); one fix pass gets this to 8.0+.

### Verified WRONG

1. **M6 `GatewayRequest` / `GatewayResponse` shape is NOT Pydantic.** `src/m6_mcp_gateway/gateway.py` lines 118 and 221 define both as `@dataclass(frozen=True)`, not `pydantic.BaseModel`. The spec (R7 AC7.2) says "Pydantic v2 models matching M6's wire shape." Two different validation surfaces, two different `.model_dump()` methods, different error types on construction. Task 20's cross-module "asserts Pydantic field equality against M6's exported types" will fail trivially — M6's types have no `model_fields`.

2. **M6 `GatewayRequest.vendor_adapter` is REQUIRED and non-None.** `src/m6_mcp_gateway/gateway.py` `__post_init__` (line 196-204): `if self.vendor_adapter is None: raise ValueError("vendor_adapter must not be None")` and further requires callable `.call` and str `.name`. The spec's `_invoke_tool` helper (spec line 707) constructs `GatewayRequest(..., vendor_adapter=None, ...)`. **This will raise `ValueError` at request construction time — every single M6 call fails.**

3. **M6 DENY/ESCALATE/vendor_unavailable/rate_limited/mnpi_leakage_scan are RAISED, not RETURNED.** `TrustAwareGateway.call()` returns `GatewayResponse` **only** on the ALLOW path (`gateway.py` line 577 success return). Failure paths (`_handle_failure`, line 605+) unconditionally `raise GatewayError(reason)`. The M8 spec's Response Handling section (spec lines 724-736) reads:
   - "`GatewayResponse.decision == 'DENY'` → stage fails hard"
   - "`GatewayResponse.decision == 'ESCALATE'` → stage continues"
   - "`GatewayResponse.reason == 'vendor_unavailable'` → stage retries"
   - "`GatewayResponse.reason == 'rate_limited'` → stage waits 2s"
   - "`GatewayResponse.reason == 'mnpi_leakage_scan'` → emit `m8_mnpi_leaked_through_gateway`"

   **None of these branches will ever execute.** The gateway never returns a DENY response; it raises `GatewayError("authority_denied")`. Correct contract: `try: resp = gateway.call(req); except GatewayError as exc: if exc.reason == "authority_denied": ...`. This is the exact class of bug M9 v1 had with the invented `VendorAdapter` shape (7.42/10 penalty).

4. **M6 has no `emit_audit()` method.** M6's `TrustAwareGateway` public surface is `call(request) -> GatewayResponse` plus `health()`. Audit fan-out happens *inside* `call()` via the injected `AuditLogger.write(entry)`. The spec's `GatewayClient.emit_audit(entry: dict) -> None` (R7 AC7.1, R18 AC18.2) invents a method that M6 does not export. Known Blocker 6 flags "pending-confirm-with-M6" but doesn't treat it as a hard blocker — it is one.

5. **M3 `Holding` has NO `cost_basis_method` field.** `src/m3_schema_registry/types.py` line 719-721 verbatim: `"""Canonical position/holding. Does NOT have cost_basis_method — that is on TaxLot."""` The field lives on `TaxLot.cost_basis_method: CostBasisMethod` (line 698) with a `@field_validator` that rejects `None`. The M8 spec's State Field Invariant "Cost basis preservation" (spec line 632) and Error Code Map row 20 (spec line 979) both say `Holding.cost_basis_method`. **The invariant as-written cannot be implemented — the attribute does not exist on `Holding`.** Either rewrite to walk each Holding's `tax_lots: list[TaxLot]` and assert every lot's `cost_basis_method` is non-None, or drop the invariant (M3 already validates it at `TaxLot` construction). Steering Rule 32 clause "cost_basis never null" is honored by M3/M7, not by M8.

6. **006 stage-name drift vs "provenance continuity" claim.** Spec banner + Phase 2 Scope + D2 DECISION-LOG claim "Names preserved from 006 `pipeline.py` `_all_stage_methods()`." Verified drift:
   - 006 stage 12: `_stage_12_sentiment_synthesis` → spec `stage_12_cross_source_synthesis` **(renamed)**
   - 006 stage 21: `_stage_21_final_approval_gate` → spec `stage_21_anti_fabrication_check` **(renamed)**

   Two renames out of 23 is ~9% drift. Either rename stages back verbatim, or drop the "provenance continuity" framing and justify each rename (stage 12 is now a reduce step because of map-reduce; stage 21 is now anti-fab + gate hybrid). Current framing misleadingly claims verbatim preservation.

7. **Internal inconsistency: 10 vs 20 reason codes.**
   - Changelog (spec line 20), 9th bullet: "Closed frozen `VALID_REASON_CODES` set (**10 codes**)"
   - Phase 2 Scope bullet (spec line 64): "Closed frozen error vocabulary — **10** `reason_code` values (R11)"
   - R11 header (spec line 281): "**Closed Frozen Set (10 Codes)**"
   - R11 AC11.1 (spec line 286): "**20 codes in v0.1.0**"
   - R11 AC11.1 meta-test: "`assert len(VALID_REASON_CODES) == 20`"
   - Error Code Map (spec line 955): "**20 codes in v0.1.0**"
   - Appendix C D7: "Initial intent was 10; drafting forced 20"

   Three places say 10, three places say 20, one admits the delta. Global sweep, pick one.

8. **`langgraph.constants.Send` is deprecated.** Verified at runtime (`langgraph==0.6.6`): `LangGraphDeprecatedSinceV10: Importing Send from langgraph.constants is deprecated. Please use 'from langgraph.types import Send' instead. Deprecated in LangGraph V1.0 to be removed in V2.0.` Spec Appendix B.2 `graph.py` skeleton uses the deprecated path. Bigger: spec banner pins `langgraph >= 0.2.0, < 0.3` (AC12.7 also) — real-world current is 0.6.x / 1.0.x. A `<0.3` pin freezes M8 on a pre-1.0 library two majors old. Move to `>=0.4,<2.0` and update the import.

9. **PostgresSaver package naming.** `langgraph-checkpoint-postgres` is the PyPI package name; import path is `from langgraph.checkpoint.postgres import PostgresSaver`. Plausible. The local env doesn't have it installed; cannot runtime-confirm the class name or the `.from_conn_string(dsn)` constructor. Add a PENDING-VERIFICATION row or pin to a specific version already verified against.

10. **Bedrock Sonnet model ID.** Spec acknowledges PENDING-VERIFICATION (Known Blocker 2) and has Task 18 live-probe. Sufficient; don't inflate.

### Strengths
- ARCH-09 matrix quotation is character-perfect — better than M9 v1 managed.
- 006 v2 line 58 HITL_STAGES and line 160-174 enumeration are quoted with correct line numbers.
- All M3 type names exist (minus the `cost_basis_method` misplacement).
- Bedrock model ID is flagged PENDING with a live probe task; doesn't hide uncertainty.

### Weaknesses (HARSH)
- Three cross-module shape-drift bugs against real M6 + M3 source code (items 1, 2, 3, 4, 5 above). **The M6 inventions are the most serious — every production M8 call would fail at `GatewayRequest(vendor_adapter=None)`.**
- Doc consistency: 10/20 codes repeated in three places each. Basic editing miss.
- LangGraph import path deprecated; version pin two majors stale.
- "Provenance continuity" claim partially false.

### What would make it a 10
- Drop the invented Pydantic wrapper; use the real M6 dataclasses directly OR define a Protocol that M8 imports without reaching for Pydantic shape copies.
- Change `_invoke_tool`: (a) inject a working `vendor_adapter` (or mark it a blocker that needs M6 clarification), (b) wrap the call in `try/except GatewayError` and branch on `exc.reason`.
- Rewrite State Field Invariant to walk `Holding.tax_lots[*].cost_basis_method` rather than `Holding.cost_basis_method`.
- Either align stage 12/21 names to 006 verbatim or drop "provenance continuity."
- Global sweep: 10 → 20.
- `Send` import from `langgraph.types`; bump pin.

---

## Required Fixes (MUST fix before GO)

Numbered, severity-ordered.

1. **[CRITICAL — Accuracy]** Fix M6 `GatewayRequest` / `GatewayResponse` shape drift. Either (a) drop the Pydantic wrapper and use real M6 `@dataclass(frozen=True)` types (AC7.2 rewrite), or (b) keep the Pydantic wrapper but assert field-equality via `dataclasses.fields()` introspection, not `model_fields`. Update Task 20 accordingly.

2. **[CRITICAL — Accuracy]** Fix `_invoke_tool` helper (spec lines 695-713): `vendor_adapter=None` unconditionally raises `ValueError` at M6's `GatewayRequest.__post_init__`. Either inject a real `vendor_adapter` at the M8 layer (and document the map of tool_name → VendorAdapter that M6 would normally resolve) OR escalate to Known Blocker 6 as HARD block until M6 exposes "server-side adapter resolution" mode. Current code cannot invoke M6 at all.

3. **[CRITICAL — Accuracy]** Rewrite DENY/ESCALATE/vendor_unavailable/rate_limited/mnpi_leakage_scan response handling (§M6 Gateway Call Pattern Response Handling, spec lines 724-736). These are `raise GatewayError(reason)` from M6, not `GatewayResponse` fields. Correct pattern:
   ```python
   try:
       resp = gateway.call(req)  # only reached on ALLOW
   except GatewayError as exc:
       if exc.reason == "authority_denied":   reason_code = "m8_compliance_denied"
       elif exc.reason == "authority_escalated": state.compliance_escalation=True; continue
       elif exc.reason == "vendor_unavailable":  retry_with_backoff
       elif exc.reason == "rate_limited":         wait_and_retry
       elif exc.reason == "mnpi_leakage_scan":   reason_code = "m8_mnpi_leaked_through_gateway"
       elif exc.reason == "audit_failed":         terminate
       else:                                       reason_code = "m8_stage_failed"
   ```
   Update AC7.7, AC7.8, and Response Handling section.

4. **[CRITICAL — Accuracy]** Resolve `GatewayClient.emit_audit(entry) -> None` method invention (AC7.1, AC18.2). M6 has no such method. Either (a) M6 grows one (elevate Known Blocker 6 to HARD block on M6 v0.3.0), (b) M8 writes audit via a separately injected `AuditClient` talking to M10's FastAPI (Protocol-shaped; does not violate AC18.1), or (c) M8 writes audit through a `/audit` route on M6's FastAPI. Pick one; update DECISION-LOG.

5. **[MAJOR — Accuracy]** Fix M3 `Holding.cost_basis_method` misattribution. `Holding` has no such field; `TaxLot.cost_basis_method` does. Rewrite State Field Invariant "Cost basis preservation" (spec line 632) and Error Code Map row 20 (spec line 979) to walk `holding.tax_lots[*].cost_basis_method`. Update A12 invariant and Task 11 `test_cost_basis_preserved`.

6. **[MAJOR — Accuracy]** Reconcile "provenance continuity" with stage-12 and stage-21 renames. Either:
   - Rename spec stages back to `stage_12_sentiment_synthesis` and `stage_21_final_approval_gate` (matches 006 verbatim), OR
   - Drop the "verbatim preservation" framing and document the renames as deliberate (stage 12 is a reduce step because of map-reduce; stage 21 is anti-fab + gate).

7. **[MAJOR — Doc Consistency]** Global sweep: replace every "10 codes" with "20 codes". Locations: Changelog line 20 bullet 9, Phase 2 Scope line 64, R11 header line 281. AC11.1 and Error Code Map already say 20.

8. **[MAJOR — Accuracy]** LangGraph `Send` import: change `from langgraph.constants import Send` to `from langgraph.types import Send` (Appendix B.2 skeleton). Update version pin from `langgraph >= 0.2.0, < 0.3` to `>= 0.4, < 2.0` (or current stable major). Update AC12.7.

9. **[MINOR — Accuracy]** `ComplianceCheck` in AC12.2 positive allow-list is unused. Either drop from M3 import allow-list AND from `PipelineState.compliance_check` field (which nothing populates), OR have stage 20 construct a `ComplianceCheck` from the `GatewayResponse`.

10. **[MINOR — Design Alignment]** Elevate DECISION-LOG D12 (drop `langchain-aws`) to a Known Blockers row with ARCH-04 v2 update request. Spec should not silently deviate from an architecture document.

11. **[MINOR — Security]** Tighten AC13.5: "print emits digest-only audit line; raw payload never printed" + source-level assertion.

12. **[MINOR — Security]** Add HITL HMAC key rotation contract (pod restart triggers re-fetch; document rotation cadence).

---

## Recommended Fixes (nice-to-haves)

Numbered.

1. **[Completeness]** Add AC5.8: stage 8 with zero discovered instruments skips fan-out and reducer; pipeline proceeds to stage 13 with `per_instrument_results={}` — NOT `m8_map_reduce_all_failed`. Matters for `m8.research_single_tool` pipelines.
2. **[Completeness]** Add A24 invariant: `state.compliance_escalation` survives checkpoint round-trip. Test in Task 9.
3. **[Completeness]** Per-task reason-code coverage matrix on Tasks 14/16/17.
4. **[Testability]** Pin Hypothesis `max_examples=20` for CI, `max_examples=50` for local dev. Document CI budget.
5. **[Testability]** Explicit integration test for `interrupt()` → checkpointer write order (regression guard for LangGraph version bumps).
6. **[Testability]** Second version-match test: `STAGE_NAMES` count == M12's expected count (mark pending until M12 spec drafted).
7. **[Security]** Cite M4 on "client_id deemed non-MNPI" in AC8.6 or redact `client_id` to `client_id_sha256`.
8. **[Security]** Add `(tenant_id, thread_id)` compound checkpointer key to AC3.6 so resumption is tenant-scoped.
9. **[Gaps]** Audit-outage circuit breaker: readiness probe fails if M6 audit emit has sustained failure rate > 10% over 30s, causing Kubernetes to shed load at pod level.
10. **[Gaps]** Propagate `state.dropped_instruments` into `ResearchBrief.sources` or `ResearchBrief.dropped_coverage` field so advisors see coverage gaps.
11. **[Gaps]** `m8.pipeline_slow_alert` exactly-once emission AC.
12. **[Gaps]** `resume_from_gate` idempotency AC: second call with same `(thread_id, approval.approval_token)` returns cached result.
13. **[Design Alignment]** ARCH-05 v2 non-interaction statement ("M8 does not read/write agent memory").
14. **[Design Alignment]** Add Steering Rules 9, 10, 17, 19 to the Steering-Rule Traceability table (even if "N/A in Phase 2 M8 scope").

---

## Final Verdict

**7.63 / 10 — CONDITIONAL GO**

This is a structurally mature spec. It mirrors M7 v0.3.0 / M11 v0.2.0 / M9 v0.2.0 discipline: explicit Known Blockers with DECISION-LOG mapping, 20 atomic tasks with xfail gates, 23 invariants each bound to a test, a complete Error Code Map, a full integration contract with M12, and a defensible Phase 2 scope with honest out-of-scope calls.

Pulled down by four distinct accuracy issues that mirror the failure mode of M9 v1 and M11 v1:

1. **Three cross-module shape-drift bugs against real 007 code** (M6 dataclass-vs-Pydantic; M6 requires non-null `vendor_adapter`; M6 raises `GatewayError` rather than returning DENY-shaped responses; M6 has no `emit_audit` method). Any one of these makes M8 unable to call M6 on day one of implementation. All three together indicate the spec author wrote against a model of M6's shape that doesn't match M6's committed code — exactly the M9 v1 `VendorAdapter` invention pattern (7.42).
2. **M3 `Holding.cost_basis_method` misattribution** (field lives on `TaxLot`; `Holding` docstring says so explicitly). AC7.5 / Error Code Map row 20 / A12 invariant all reference a non-existent attribute.
3. **006 stage-name drift vs "provenance continuity" claim** — two of 23 stage names are silently renamed despite the banner and DECISION-LOG D2 claiming verbatim preservation.
4. **Internal 10-vs-20 reason-code inconsistency** in three places.

Plus a minor: `langgraph.constants.Send` deprecated since V1.0; version pin is two majors stale.

None of these require a spec rewrite. Required Fixes 1-8 will move this to 8.0+ GO. Items 5-7 and 9-12 clean up the remaining rough edges. The spec reaches the 7.5 minimum for review passage but should NOT be greenlit to implementation until Required Fixes 1-8 are closed — otherwise Task 1 (bootstrap `GatewayClient`) fails at first call and blocks the entire dependency chain.

**Recommend: v0.2.0 authored with Required Fixes 1-8 + Recommended Fixes 1-5, then re-review.** Target post-fix score: 8.2-8.5/10 GO (matching M7 v0.3.0 / M11 v0.2.0 trajectory).

---

## Review Metadata

| Field | Value |
|-------|-------|
| Review Version | LLMJ-v1 |
| Reviewed Spec Version | 0.1.0 |
| Reviewer | Independent LLM Judge |
| Calibration set | M7 v1 (7.36), M11 v1 (7.27), M9 v1 (7.42) |
| Final Score | 7.63 / 10 |
| Verdict | CONDITIONAL GO |
| Required Fixes | 12 |
| Recommended Fixes | 14 |
| Ground-Truth Files Consulted | `ARCH-04-v2-tech-stack-decisions.md`, `ARCH-06-v3-compliance-gap-designs.md`, `ARCH-07-definitive-tech-stack.md`, `ARCH-08-packaging-networking-well-architected.md`, `ARCH-09-complete-module-map.md`, `ARCH-10-agentic-core-redesign.md`, `007-consolidated-design-and-plan.md`, `src/m3_schema_registry/types.py`, `src/m6_mcp_gateway/gateway.py`, `src/m9_intent_router/taxonomy.py`, `src/m9_intent_router/models.py`, `my-agent-project-006-v2-.../openclaw/skills/fsi-research/pipeline.py` (lines 50-174) |
