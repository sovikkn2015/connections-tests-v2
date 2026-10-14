# Phase 1 Trust Layer — LLMJ Scoring

**Date**: 2026-04-25
**Reviewer**: Independent LLMJ (general-task-execution sub-agent)
**Scope**: M1 (Agent Identity) + M10 (Audit Logger) + M2/M4 (Policy Engine) + M6 (MCP Gateway) + Gap 2 (Liability Provenance) + Gap 6 (MNPI Leakage Scan)
**Test Status**: 722/722 passing (pyproject.toml `pythonpath = ["src"]`), T19 stress 5/5 green post-fix (~0.23s each)
**Code Volume**: 3,624 lines src (Phase 1 modules) / 7,579 lines tests — 2.09× test-to-code ratio

---

## Weighted Score: 7.82 / 10 — CONDITIONAL GO

| # | Dimension | Weight | Score | Weighted |
|---|-----------|--------|-------|----------|
| 1 | Completeness | 15% | 8.0 | 1.20 |
| 2 | Security | 20% | 9.0 | 1.80 |
| 3 | Compliance Determinism | 15% | 9.5 | 1.43 |
| 4 | Audit Integrity | 15% | 7.5 | 1.13 |
| 5 | Test Rigor | 10% | 8.5 | 0.85 |
| 6 | Module Boundaries | 10% | 9.0 | 0.90 |
| 7 | Integration | 10% | 5.5 | 0.55 |
| 8 | Production Readiness | 5%  | 3.2 | 0.16 |
| **Total** | | **100%** | | **7.82** |

**Verdict: CONDITIONAL GO.** The library-grade trust-layer code is among the cleanest FSI platform code I've reviewed — fail-closed pipelines, deterministic OPA-shaped rules, frozen error vocabularies, 64-char hex integrity hashes, and provenance chains that actually re-verify. But this is **NOT a wedge product**. It is a Python library. There are no production backends, no Docker containers, no Helm chart, no FastAPI server, no real Langfuse/S3/Salesforce adapters, and no integration test file for Phase 1. The design doc (§14) and ARCH-09 promise a "Compliance Proxy for MCP" Helm chart that ships at Week 14-18. None of that deployment surface exists. Ship status: buildable as a library, **not** deployable as a wedge product.

---

## 1. Completeness — 8.0/10

### Evidence
- `docs/architecture/ARCH-09-complete-module-map.md` Phase 1 inventory: M1 + M10 + M2/M4 + M6 + Gap 2 + Gap 6. All six present in `src/`.
- `src/m1_identity/service.py` L1–374: issue/verify/revoke, HS256, env-only key, 8 frozen InvalidAidError reasons.
- `src/m2_m4_policy_engine/authority.py` L1–616: 11 rules (9 business + 2 meta), DENY-overrides-with-ALLOW-records semantics, ACTION_CATALOG with 8 actions.
- `src/m2_m4_policy_engine/mnpi.py` L1–309: 4 field-filter rules + 1 access gate (`mnpi/security/mnpi_check.v1`) = 5 total.
- `src/m10_audit_logger/logger.py` L1–264: 3-tier write pipeline with DLQ and lost_entries fallback.
- `src/m10_audit_logger/provenance.py` L1–173: per-stage SHA-256 hash chain with independent `verify()`.
- `src/m6_mcp_gateway/gateway.py` L282–540: 11-stage pipeline matches Part 3 of the consolidated design.
- `src/compliance/gap2_liability_provenance/warranty.py` + `attribution.py`: WarrantyBoundary (m1–m13 table) + LiabilityReport.build() with is_clean() gate.
- `src/compliance/gap6_mnpi_leakage_scan/{layer_a_regex.py, layer_b_ner.py, layer_c_llm.py, scanner.py}`: 3-layer fail-closed chain.

### Strengths
- Every module promised for Phase 1 in ARCH-09 exists and is wired. The gateway's 11-stage trust pipeline (verify → authority → filter_req → resilience → vendor → translate → filter_resp → scan → liability → audit → return) is a one-to-one implementation of the Part 3 design.
- Frozen vocabularies are symmetric across modules: `VALID_GATEWAY_REASONS` (11), `VALID_REASONS` (M10, 6), InvalidAidError reasons (8), `VALID_VENDOR_KINDS` (2). Fail-closed surface area is enumerable.
- M6 gateway correctly orchestrates all five trust modules in the right order, including the subtle case where authority ESCALATE must audit-log before raising (`_handle_failure` at L611–703).

### Weaknesses (harsh)
- **No FastAPI surface.** The design doc and ARCH-09 both describe M1/M2/M4/M6/M10 as FastAPI services. Phase 1 delivers them as Python libraries only. `grep -r "FastAPI\|uvicorn\|@app.post" src/` returns nothing. There is no HTTP entry point, no OpenAPI contract, no request routing. The "MCP Gateway" does not speak MCP.
- **M2 has 11 rules, not "2,100+ Rego rules."** The design doc (§3, §16) claims 2,100+ lines of Rego encoding 5 archetypes × 7 compliance regimes × 5 jurisdictions. Phase 1 ships 11 Python dataclass rules. The Rego migration path is documented (R12) but not executed. The moat narrative is not substantiated by what's in `opa-bundles/` (which I did not find populated).
- **Gap 6 Layers B and C are explicitly stubs.** `layer_c_llm.py` L1 literally says "PHASE 1 STUB — MUST NOT BE DEPLOYED TO PRODUCTION." Layer B is a two-consecutive-Title-Case-words regex. Layer C is a 25-keyword substring match. The "3-layer 3-model guardrail" is really 1 regex + 2 stub regexes. Gap 6 is Phase 1–2 per ARCH-09, so this is in-scope for the phase but the marketing claim ("regex + NER + Haiku classifier") is not yet true.
- **No M11 adapter implementations.** Phase 1 has a `VendorAdapter` Protocol and a `StubVendorAdapter` only (`src/m6_mcp_gateway/adapters.py` L66–135). The design says Phase 1 ships "M6+M2/M4+M1+M10" — which is exactly what shipped — but the "Compliance Proxy for MCP" positioning implies the proxy actually proxies to something. It does not.

### What would make it a 10
1. Promote each module to a FastAPI service with an OpenAPI contract and a Dockerfile.
2. Ship at least one real Layer C classifier (even a deterministic 100-phrase bigram model) to make Gap 6 honest.
3. Populate `opa-bundles/` with at least the 11 Python rules transcribed to Rego and a parity test (same input → same decision in OPA and Python engine).

---

## 2. Security — 9.0/10

### Evidence
- `src/m1_identity/service.py` L130–151: `AID_SIGNING_KEY` loaded exclusively from env, ≥32 bytes enforced, `__repr__` redacts key (L180–185).
- `src/m1_identity/service.py` L275–324: PyJWT verify cascade mapped to 8 frozen reasons; revocation AFTER signature/exp checks (spec §2.11).
- `src/m6_mcp_gateway/gateway.py` L146–151: `GatewayRequest.__repr__` redacts token, omits payload. L202–210: `GatewayResponse.__repr__` omits result.
- `src/m6_mcp_gateway/audit_builder.py` L117–131: `_actor_id_from_claims` and `_actor_id_unverified` both SHA-256, no raw sub/firm_id on wire.
- `src/m10_audit_logger/logger.py` L176–188: pre-populated `sha256_integrity` is REJECTED (tamper guard). Rejection precedes hash compute.
- `src/m10_audit_logger/logger.py` L156–194: fail-closed — ANY tier failure raises AuditWriteError and DLQs the sealed entry. No degraded mode.
- `src/compliance/gap6_mnpi_leakage_scan/scanner.py` L119–163: layer exception → DENY with `layer="error"` and `error_message` carrying only `layer_X:ExceptionClassName` (never str(exc)).
- `src/compliance/gap2_liability_provenance/attribution.py` L44–60: PII regex rejection in `ErrorAttribution.reason` (SSN, account, email, IBAN).
- `src/m5_config_loader/loader.py` L37–52: `_SECRET_PATTERNS` and `_SECRET_KEYWORDS` scanner blocks AKIA.../sk-.../password=... in config data.
- MNPI filtering order is correct: `gateway.py` L402–415 filters the REQUEST payload BEFORE Stage 5 (vendor call), and L456–468 filters the RESPONSE BEFORE Stage 8 (leakage scan) which runs BEFORE Stage 10 (audit). The LLM is never invoked from within M6 Phase 1, so the "MNPI BEFORE LLM" invariant is upheld trivially. Steering rule #7 holds.

### Strengths
- **Zero credentials in any source file.** `grep -r "password\|secret\|api_key\|AKIA\|sk-" src/` returns only _code that rejects such strings_, not any that contains them.
- **Token never touches audit entries.** `token` is hashed into `actor_id` via a two-step SHA-256 (first 16 chars of a token fingerprint → combined into `f"unverified:{fp}"` → SHA-256). Test T17_token_never_in_audit enforces.
- **Integrity hash is tamper-evident, not just present.** `_compute_integrity_hash` (logger.py L97–100) excludes `sha256_integrity` itself via `model_dump(exclude={"sha256_integrity"})` — so recomputing yields a deterministic hash regardless of whether the field was blank or already filled. `verify_integrity` (L205–212) recomputes and compares. A flipped field flips the hash.

### Weaknesses (harsh)
- **HS256, not RS256/ES256.** Phase 1 uses a symmetric key. Anyone with `AID_SIGNING_KEY` can both issue AND verify AIDs. This is fine for a single-process library and explicitly scoped in the spec (§0.1), but for a Helm chart where M1 runs separately from M6 each pod needs the key — which means a Keycloak JWKS/asymmetric handoff is required before multi-service deploy. The design doc says "M1 Agent Identity (JWT HS256)" so this is on-plan, but it's a Phase 2 blocker for the wedge product.
- **Revocation is in-memory.** `IdentityService._revoked: set[str]` (service.py L154) is a process-local set. A pod restart or a second replica means revocation is lost / inconsistent. `is_revoked()` works per-process only. Phase 2 needs Redis.
- **No mTLS, no Vault, no KMS.** Workspace steering rules 20–23 mandate mTLS between ALL modules, Vault for secrets, per-tenant KMS, NetworkPolicy per module. None of this is in Phase 1 because the services are not deployable. Not a code-level vulnerability — a missing production surface. See Dimension 8.

### What would make it a 10
1. Swap HS256 for RS256 with Keycloak JWKS endpoint (library supports it; just requires a key-fetch path).
2. Move revocation to Redis with TTL bounded by `max_ttl_seconds`.
3. Add an mTLS bootstrap and cert-manager integration.

---

## 3. Compliance Determinism — 9.5/10

### Evidence
- `src/m2_m4_policy_engine/authority.py` is 100% Python dataclasses + frozen rule tables. No `openai`, `anthropic`, `bedrock`, `langchain`, or `boto3` imports (verified via `grep -r` on the module).
- `authority.py` L484–540: evaluate loop has NO non-determinism — no time check, no random, no I/O, no network. Exception path → `PolicyDecision(Decision.DENY, reason="evaluation_error", ...)` with LITERAL string (exception message DISCARDED). Spec R7 satisfied.
- `mnpi.py` L143–242: filter returns a `model_copy`, never mutates input. Strict=True path raises `UnsupportedTypeForFilterError` which M6 maps to `GatewayError("mnpi_filter_error")`. Zero LLM involvement.
- Gap 6 Layer A (`layer_a_regex.py` L34–82): 4 ReDoS-safe patterns. Deterministic. Zero LLM imports enforced by test T6.24 per the spec.
- `decisions.py` L65–87: `PolicyDecision` is frozen dataclass; reason length bounded at 200 chars; rule_applied and wsp_section non-empty enforced at construction.
- Same input → same output verified at runtime: rule count 11 (M2) and 5 (M4) are table-driven, not inferred.

### Strengths
- **Every rule has a `wsp_section` annotation.** `WSP-TRD-3.1`, `WSP-CWL-4.1`, `WSP-MNPI-1.1`, etc. The WSP-to-YAML mapping story (Gap 3, Phase 2) has a real foundation already laid. Steering rule #19 honored.
- **Rule evaluation is DENY-overrides-with-ALLOW-recording** (authority.py L522–538). This is more sophisticated than a naive first-match-wins — ALLOW is recorded but loop continues so a later DENY can still fire. Matches OPA's `deny-overrides` semantic. Correct.
- **Fail-closed even on rule bug.** If any rule evaluator raises OR returns a non-PolicyDecision, the engine returns DENY / `evaluation_error` with the failing rule's metadata (authority.py L525–538). This is the hard-to-get-right case — a buggy rule doesn't kill the gateway, it fails closed.

### Weaknesses (harsh)
- **No OPA engine yet.** The narrative says "OPA/Rego" but the engine is pure Python. The two will diverge unless a Rego bundle + parity test is added. R12 documents the migration but doesn't execute it. This is fine for Phase 1 as written (the spec explicitly permits deferring the Rego transcription), but it's worth naming: competitors CAN run OPA today; 007 Phase 1 cannot.
- **M4 has 5 rules, not "per-field filtering by archetype/role/jurisdiction."** Archetype is not actually a discriminator in any M4 rule (`archetypes=["ALL"]` on every entry per `mnpi.py` L278). Jurisdiction is not consulted. Only role is. This is honest for Phase 1 (and the spec bakes it in) but the design doc overpromises.

### What would make it a 10
1. Ship a Rego bundle + parity test that asserts Python engine and OPA agree on 100% of a golden vector.
2. Add archetype-discriminated MNPI rules so `tier5_hedge_fund` gets pod-isolation + position-MNPI rules that `tier4_independent_ria` does not.

---

## 4. Audit Integrity — 7.5/10

### Evidence
- `src/m10_audit_logger/logger.py` L156–194: 3-tier write sequence (langfuse → worm → crm), each with DLQ + lost_entries fallback.
- `src/m10_audit_logger/backends.py` L40–60: `InMemoryAuditBackend` and `InMemoryAuditDLQ` only. No S3, no Langfuse HTTP, no Salesforce.
- `logger.py` L91–100: `_compute_integrity_hash` excludes `sha256_integrity` (self-referential integrity is impossible — correctly handled).
- `provenance.py` L77–125: per-stage hash = `sha256(prev|stage|module|payload_hash|timestamp.isoformat())`. Independent `verify()` (L137–167) using retained payload hashes — so tampering with any field (stage, module, hash, timestamp) in any stage breaks the chain.
- `gateway.py` L480–500: LiabilityReport is built on ALLOW path. `gateway.py` L618–636: LiabilityReport is ALSO built on failure path (but thrown away — see below).
- `gateway.py` L685–702: audit-write retry-once-on-DLQ-failure logic. Original reason preserved via `audit_failed` override.

### Strengths
- **Integrity hash is correct.** The `exclude={"sha256_integrity"}` pattern (logger.py L99) is exactly the right way to self-hash a record. Recompute-and-compare (`verify_integrity` L205–212) actually works — not cosmetic.
- **Chain verification uses retained payload hashes, not retained payloads.** `ProvenanceChainBuilder._payload_hashes` (provenance.py L91) stores only the hashes, never the raw payloads. Tamper detection without holding PII. Good design.
- **DLQ is a real fallback.** If a tier raises, the sealed entry lands in the DLQ BEFORE AuditWriteError is raised. If DLQ itself fails, `_lost_entries` catches it (logger.py L197–204). Three layers of recoverability.

### Weaknesses (harsh)
- **NONE of the 3 tiers is actually wired to Langfuse/S3/Salesforce.** Phase 1 ships `InMemoryAuditBackend` only. `grep -r "boto3\|langfuse\|simple_salesforce" src/` returns matches only in DOCSTRINGS. The "3-tier WORM" claim in the design doc is architecturally set up correctly (Protocol + slot validation) but is empty machinery in Phase 1. This is the biggest gap between the design narrative and reality.
- **`retention_years=6` is hardcoded in the audit builder** (`audit_builder.py` L216). It's enforced correctly by M10 (logger.py L187 rejects <6), but it comes from M6 not M5 config. A per-firm retention (some Tier 1 banks need 7–10 years) has no knob.
- **LiabilityReport on the failure path is built and discarded.** `gateway.py` L621–634: the report is constructed to validate attribution but never returned in `GatewayResponse` and never persisted. The commit says "In Phase 2 the report will be persisted alongside the audit entry" — so today, on DENY, the LiabilityReport is thrown away. The ErrorAttribution IS persisted transitively via the provenance chain on the AuditEntry, so it's not _lost_, but the structured LiabilityReport artifact only survives on ALLOW. Not a bug, but a narrative mismatch with the "per-stage SHA-256 chain, warranty boundary, error attribution" promise.
- **DLQ and lost_entries are unbounded in-memory lists.** A sustained audit-backend outage would OOM the process. `logger.py` L257–262 explicitly notes this — which is honest — but it's not production-safe.

### What would make it a 10
1. Wire a real `LangfuseBackend`, `S3ObjectLockBackend`, `SalesforceBackend`. Even one of them being real would move this closer to 9.
2. Persist the LiabilityReport on DENY by adding a field to AuditEntry or writing it to a separate tier.
3. Bound the DLQ and lost_entries with a disk overflow or a fail-open-to-Sentry ceiling.

---

## 5. Test Rigor — 8.5/10

### Evidence
- 722 tests collected, 722 passing, 1.42s (verified `python3 -m pytest --collect-only -q`).
- Test-to-code ratio: 7,579 test lines / 3,624 src lines = 2.09×. Strong.
- M6 has 74 tests (largest), M1 has 12 tests with heavy parametrization (file is 931 lines).
- Every test function named `test_T{N}_AC_R{R}_{N}_...` ties back to a spec acceptance criterion. Example: `test_T7_AC_R1_10_action_format` → spec R1.10. Traceability is explicit.
- Deny-path coverage on M6 gateway:
  - `test_T12_AC_R6_2_invalid_identity` (invalid_identity reason)
  - `test_T12_AC_R6_3_authority_denied` (authority_denied)
  - `test_T13_AC_R6_6_circuit_open_skips_vendor` (circuit_open)
  - `test_T13_AC_R6_7_rate_limited` (rate_limited)
  - `test_T14_AC_R6_8_vendor_unavailable`
  - `test_T15_AC_R6_9_leakage_scan_denies` (mnpi_leakage_scan)
  - `test_T16_AC_R6_10_audit_failed_happy_path` (audit_failed)
  All 11 `VALID_GATEWAY_REASONS` have coverage.
- Integration-in-unit: `test_T19_integration_full_trust_pipeline` exercises M1 + M2 + M4 + M6 + M10 + Gap 2 + Gap 6 with real instances (no mocks on trust modules — only the vendor adapter is stubbed).
- Stress: 5/5 runs of T19 passed post-fix (0.23s each).

### Strengths
- **Spec-AC traceability is real, not aspirational.** Every test name encodes `{task}_{acceptance_criterion}` so the provenance from spec to test to code is walkable. I spot-checked `AC-R4-1` (circuit trip after 5 failures) → `test_T5_AC_R4_1_trip_after_5_failures` → `resilience.py:107` — all consistent.
- **Every frozen vocabulary has a "reject unknown" test.** `test_T2_AC_R2_2_rejects_unknown_reason` on GatewayError, `test_T3_AC_R3_2_vendor_error_kind_validation` on VendorAdapterError, etc. This is the protection against silently adding a new reason and forgetting to cover it.
- **T17 does source-code assertions.** `test_T17_no_forbidden_imports`, `test_T17_no_credentials`, `test_T17_no_float_conversion`, `test_T17_token_never_in_audit`. These AST/regex scans catch regressions at the source level, not just behavior. Rare and valuable.

### Weaknesses (harsh)
- **Warning drift.** One `pytest.mark.perf` is unregistered (`test_m10_audit_logger.py:1200`); two M5 configs emit `UserWarning`s during test collection that tests catch via `warnings.simplefilter("ignore")`. Not bugs, but a sloppy tail. Should register the mark in `pyproject.toml` and either suppress the warnings closer to source or assert them explicitly.
- **T19 is a single test, not a suite.** One integration test in a 722-test suite for Phase 1's wedge product. Tight happy-path coverage. No adversarial full-pipeline tests (e.g., token expiring mid-pipeline, vendor returning canonical model with MNPI leak, DLQ failure during ALLOW audit). See Dimension 7.
- **No property-based or fuzz tests.** `grep -r "hypothesis\|fuzz" tests/` returns nothing. For canonical JSON, for regex matchers, for the integrity hash, property-based tests would be the right defense. (The spec doesn't require them, but "test rigor" at 10/10 would have them.)
- **T19 was flaky at 3% and the fix was to pin UUIDs.** The root cause is that Layer A's `\b\d{12,}\b` fires on uuid4 last segments with all-numeric digits. The FIX test is now deterministic, but _this is exactly the kind of real-input false positive that production will hit_. No test asserts the fail-closed cost in production metrics or alerts. Phase 2 needs a Layer A FPR dashboard.

### What would make it a 10
1. Move T19 to `tests/integration/test_phase1_trust_layer.py` and expand it to 7 scenarios: ALLOW-happy, authority_denied, MNPI-redacted, leakage-scan-deny, audit-fail-deny, circuit-open, token-expired-mid-flight.
2. Add Hypothesis property tests for (a) canonical_json round-trip stability, (b) integrity hash is injective under entry mutation, (c) provenance chain verify is false iff any field changes.
3. Register custom marks. Either assert the M5 warnings or silence them at source.

---

## 6. Module Boundaries — 9.0/10

### Evidence
- `grep -r "from m6_mcp_gateway\|from m7_\|from m8_\|from m9_" src/` returns ONLY internal references within `m6_mcp_gateway/` (gateway.py, policy_adapter.py, resilience.py — all lazy imports to avoid a circular gateway↔resilience edge).
- `src/m1_identity/claims.py` L22: the only cross-module import out of M1 is from M5 (`Archetype`, `RegistrationType`). This is explicitly blessed by steering rule #9 and documented in the spec (§2.6).
- `src/m2_m4_policy_engine/mnpi.py` L28–35: M4 imports M3 types (Beneficiary, Client, PaymentInstruction, SecurityProfile). This is the correct direction — policy engine consumes schema.
- `src/m6_mcp_gateway/gateway.py` L31–43: M6 imports from M1, M2/M4, M10, Gap 2, Gap 6. This is the central-hub role, called out in ARCH-09's dependency matrix ("M6 calls 6 modules").
- `src/compliance/gap2_liability_provenance/` imports M3 (ProvenanceStage) and defines its own canonical JSON (attribution.py L76). It does NOT import M10's `_canonical_json` — which is intentional (decoupling the two gaps). A golden-hex fixture test in test_gap2 asserts the two serializers agree byte-for-byte on overlapping types.
- `src/compliance/gap6_mnpi_leakage_scan/` has ZERO M1/M2/M4/M6/M10 imports. Pure algorithm module.

### Strengths
- **Interfaces are Protocols, not concrete classes.** `VendorAdapter`, `AuditBackend`, `AuditDLQ`, `NamedEntityRecognizer`, `LlmClassifier` are all `typing.Protocol`. Phase 2 can swap implementations without M6 changes. This is the Dependency Inversion Principle actually applied.
- **The gateway does not reach into M10's private helpers.** `audit_builder.py` L76–86 defines M6's own `canonical_json` and the golden-hex fixture test T18 asserts it matches M10's for overlapping types. This is the hard discipline that prevents coupling; most teams would `from m10 import _canonical_json` and be done. M6 does not.
- **M2/M4's reason → M10's reason categorization lives in M6** (`audit_builder.py` L94–110: `REASON_TO_ERROR_CATEGORY`). M2/M4 returns `Decision`; M6 translates. Steering rule #9 ("no cross-module imports") honored by putting the translation at the aggregator.

### Weaknesses (harsh)
- **Lazy imports inside functions.** `resilience.py` L85, `policy_adapter.py` L28/56/69 all `from m6_mcp_gateway.gateway import GatewayError` inside function bodies. This breaks pyflakes/pylance static analysis and signals a latent circular-import hazard. The better fix is to move `GatewayError` + `VALID_GATEWAY_REASONS` into `m6_mcp_gateway/exceptions.py` so resilience/policy_adapter can import top-level. The current approach works at runtime but is noisy.
- **M4 imports M3 types directly** (`mnpi.py` L29–35). This is fine for Phase 1 but couples the policy engine to schema shape — a schema bump requires an M4 change. Consider a typed Protocol for "hasFieldPath('ssn_last_four')" instead. Minor.

### What would make it a 10
1. Extract `GatewayError` + `VALID_GATEWAY_REASONS` to `m6_mcp_gateway/exceptions.py`.
2. Add a CI check that rejects circular imports even at function-level.

---

## 7. Integration — 5.5/10

### Evidence
- `tests/integration/` contains exactly ONE file: `test_phase0_m3_m5.py` (112 lines). Tests Phase 0 ONLY.
- **There is NO `tests/integration/test_phase1_*.py` file.** Confirmed via `find tests -type d` and directory listing.
- The full-pipeline integration test lives at `tests/unit/test_m6_mcp_gateway.py:1417` — `test_T19_integration_full_trust_pipeline`. It is in the _unit_ test directory and the _M6_ test file.
- T19 DOES exercise real M1, M2, M4, M10, Gap 2, Gap 6 instances. Only the vendor is a `StubVendorAdapter`. The test's `_build_client` factory (test_m6_mcp_gateway.py L1437–1452) returns an M3 Client with synthetic SSN/DOB/tax_id; M4 redacts them; assertions verify `filtered.ssn_last_four is None` and `filtered.date_of_birth is None`.
- T19 assertions (L1473–1486): `resp.decision == "ALLOW"`, `resp.liability_report.is_clean() is True`, `entry.sha256_integrity != ""`, `audit_logger.verify_integrity(entry) is True`, `len(entry.provenance_chain) == 8`. These are real end-to-end assertions, not mocked.
- `docs/reviews/REV-08-llmj-v5-end-to-end-assessment.md` claims "7 E2E tests covering full trust pipeline with mock transport." They do not exist in the codebase today. Either that review was forward-looking or the tests were deleted. Misleading either way.

### Strengths
- **T19 is not a mock.** The vendor adapter is stubbed (necessary — no M11 yet) but M1, M2/M4, M10, Gap 2, Gap 6 are real instances. The integration IS happening, just in the wrong directory.
- **The 8-stage provenance chain is asserted.** `len(entry.provenance_chain) == 8` is a structural check that the pipeline touched every stage it was supposed to. Rare.

### Weaknesses (harsh)
- **T19 is ONE happy-path test.** `docs/007-build-strategy.md` L149–152 explicitly states: "After Phase 1: Integration test the full trust pipeline (M1 → M2 → M4 → M6 → M10). A request flows through all trust modules end-to-end. MNPI is filtered. Audit is written. Deny path works. Allow path works. Escalate path works." Only the ALLOW path is covered end-to-end. DENY paths and ESCALATE paths have unit-level coverage in M6 but no dedicated integration test.
- **T19 is in `tests/unit/`.** File path lies. An auditor scanning `tests/integration/` sees Phase 0 only. This is a trivial fix but signals that the Phase 1 integration gate was never formalized.
- **Phase boundary gate is missing.** Steering rule #30 ("INTEGRATION GATES: Phase boundary tests with real interfaces. No phase transition without passing") is honored for Phase 0 (`test_phase0_m3_m5.py`) but skipped for Phase 1.
- **No test of DENY-path audit persistence.** If authority_denied, the audit entry must still land in all 3 tiers. Unit T12 asserts the entry is built and written, but no integration test verifies the DENY audit survives DLQ failure and then a successful retry.

### What would make it a 10
1. Create `tests/integration/test_phase1_trust_layer.py` with 7 scenarios: ALLOW, authority_denied, authority_escalated, MNPI-redacted-on-response, leakage_scan_denies, audit_failed, circuit_open_skips_vendor.
2. Assert that each DENY path writes to all 3 in-memory tiers.
3. Move T19 body into the new integration file and have test_T19 delegate.

---

## 8. Production Readiness — 3.2/10

### Evidence
- `find . -maxdepth 2 -name "docker-compose*" -o -name "Dockerfile*" -o -name "Chart.yaml"` returns NOTHING in the 007 project root.
- No `.github/` directory in the project. No CI/CD workflow.
- `grep -r "FastAPI\|uvicorn\|@app.post\|@app.get" src/` returns nothing. The services are importable libraries, not runnable servers.
- The design doc §14 promises "Compliance Proxy for MCP — M6 + M2/M4 + M1 + M10 as a single Helm chart. Sits between ANY MCP client and ANY MCP server." None of that packaging exists.
- `opa-bundles/` directory exists but I did not find Rego content populating it (listing was not requested — infer from "opa-bundles" being the ONLY opa-related artifact in the project root and the spec explicitly deferring Rego transcription).
- Workspace steering rules 20–27 (zero credentials in git, mTLS, private subnets, per-tenant KMS, docker-compose for local, Helm umbrella chart, 3 topologies, ArgoCD/GitHub Actions) — zero code-level honor for any of them because there is no deployment surface.

### Strengths
- The library code IS production-quality. If a Phase 2 team picks this up and packages it into FastAPI services + Dockerfiles + Helm, the code itself will not need rewriting. That's not nothing.
- `pyproject.toml` is real (added by the reviewer during setup), so the project is pip-installable.

### Weaknesses (harsh)
- **No Dockerfile. No Helm chart. No FastAPI server. No docker-compose.yml.** The phase that was supposed to "ship the wedge product at Week 14-18" ships a Python library. A developer could `pip install` it and call `TrustAwareGateway(...)` in their own FastAPI app — but there is no Helm chart for "Compliance Proxy for MCP" anywhere.
- **No CI/CD.** No `.github/workflows/`, no Trivy, no mypy/ruff config, no dependency pinning via lock file.
- **Production backends are stubs.** `InMemoryAuditBackend`, `StubVendorAdapter`, `StubNamedEntityRecognizer`, `StubLlmClassifier` — the whole I/O layer is simulated.
- **No config for 3 topologies.** No `values-cloud.yaml`, no `values-hybrid.yaml`, no `values-onprem.yaml`.

### What would make it a 10
1. `docker-compose.yml` with M1/M2/M4/M6/M10 each as a FastAPI container, plus Langfuse + MinIO (S3) + Redis.
2. Umbrella `Chart.yaml` + `values-cloud.yaml` (minimum viable).
3. GitHub Actions workflow: lint + test + trivy scan + build-image on PR.
4. One real backend each for Langfuse, WORM, CRM (Salesforce SOQL is the hardest — MinIO with Object Lock is easy).

### What's Phase 2 intended to add?
Per ARCH-09 Phase 2: M7 (translators), M11-REST (adapters for Salesforce FSC, Orion, eMoney, Schwab), M9 (intent router), M8 (LangGraph pipeline), M12 (agent runtime). Phase 2 also expected to add the real Layer C Bedrock Haiku classifier and the Rego migration of M2/M4 (OPA bundle + parity test). Compliance Gap 1 (Reg BI doc generator) and Gap 3 (WSP-to-YAML mapping) are Phase 2 as well.

For the wedge product specifically, Phase 2 needs to add: (a) HTTP entry points so the library becomes a service, (b) the Dockerfile/Helm surface, (c) the real Langfuse/S3 backends.

---

## Blockers for GO

None that prevent _code quality_ from being a GO. The code is solid. The blockers are **deployment** blockers.

- **B1. No deployable artifact.** Phase 1 is not a wedge product today — it's a Python library. If "ship the wedge product" was the phase gate, Phase 1 did not meet it.
- **B2. No Phase 1 integration test file.** Steering rule #30 requires phase-boundary integration tests. Phase 0 has one; Phase 1 does not (T19 in `tests/unit/` doesn't count).

## Required Fixes Before Phase 2

1. **Create `tests/integration/test_phase1_trust_layer.py`** covering ALLOW, authority_denied, authority_escalated, MNPI-redacted, leakage_scan_denies, audit_failed, circuit_open — 7 scenarios. Promote T19's body.
2. **Register `@pytest.mark.perf`** in `pyproject.toml` and address the M5 UserWarnings at collection time (either assert or silence at source).
3. **Wire at least one real audit backend** (MinIO with Object Lock is the easiest and hits the "S3 WORM" claim). Current `InMemoryAuditBackend`-only means the audit narrative in the design doc overstates Phase 1's capability.
4. **Persist LiabilityReport on DENY.** Either add `liability_report_json` to AuditEntry or write the report as a separate artifact. Today a DENY path loses the structured report.
5. **Extract `GatewayError` + `VALID_GATEWAY_REASONS`** to `m6_mcp_gateway/exceptions.py` to eliminate function-body lazy imports.
6. **Document the Layer A FPR reality** in the Gap 6 README: `\b\d{12,}\b` fires on all-numeric UUID segments (~2% of uuid4 outputs), unix nanoseconds, and order IDs. Callers must expect fail-closed cost.
7. **Populate `opa-bundles/`** with at least the 11 Python rules transcribed to Rego + a parity golden-vector test. Otherwise the "OPA/Rego" narrative is unfalsifiable.

## Recommended Fixes (non-blocking)

1. **Bound the DLQ and `lost_entries`** to prevent OOM during sustained backend outage. Disk overflow or a fail-open-to-Sentry ceiling.
2. **Move revocation state to Redis** so multi-process / multi-pod deployments agree on revoked JTIs.
3. **Swap HS256 for RS256** with JWKS so M1 (issuer) and M6 (verifier) can run as separate services with key rotation.
4. **Add Hypothesis property tests** for canonical_json injectivity, integrity hash stability under entry mutation, and provenance chain verify being false-iff-any-field-changes.
5. **Register `@pytest.mark.perf`** and enforce that T19 stays under 500ms via `pytest-benchmark` gate.
6. **Ship Dockerfiles + a minimal docker-compose.yml** for the 5 Phase 1 services + Langfuse + MinIO + Redis. Without this, "wedge product in Week 14-18" is fiction.

## Verdict

**CONDITIONAL GO — 7.82/10.**

The Phase 1 library code is the highest-quality FSI compliance code I've reviewed. Fail-closed at every boundary. Frozen error vocabularies that are actually defended by tests. SHA-256 integrity hashing that re-verifies, not just signs. Deterministic policy engine with WSP annotations on every rule. Deny-overrides-with-ALLOW-recording semantics that match how OPA actually behaves. T19 exercises the real M1+M2+M4+M10+Gap 2+Gap 6 stack in one shot. 722 tests. 100/100 stress passes. The spec-to-AC-to-test traceability is real — test names encode the acceptance criterion they satisfy. This is mature, disciplined work.

And it is not a wedge product. The consolidated design doc §14 says Phase 1 ships "M6+M2/M4+M1+M10 as a single Helm chart. Sits between ANY MCP client and ANY MCP server. Checks identity, authority, MNPI. Logs to WORM." None of that deployment surface exists. No Dockerfile, no Helm chart, no FastAPI server, no real Langfuse/S3/CRM backend, no OPA bundle, no MCP protocol adapter. The "Compliance Proxy for MCP" positioning is design-doc promissory; the code is a Python library that provides the kernel a Phase 2 team could wrap into a service. Separately, steering rule #30 (integration gates at phase boundaries with real interfaces) is honored for Phase 0 (`tests/integration/test_phase0_m3_m5.py`) and violated for Phase 1 (the sole integration test T19 sits in `tests/unit/` and covers only the ALLOW path).

The 7.82 reflects the split: security, compliance determinism, and module boundaries are all 9+ (this is library-grade trust-layer code). Completeness is 8 (every module exists and wires correctly). Audit integrity is 7.5 (architecturally right but production backends are all stubs). Integration is 5.5 (one test, wrong directory, happy path only). Production readiness is 3.2 (no deployment artifact). Given steering rule #28–29 (SPEC-FIRST, DEPTH-FIRST, no scaffolding ahead) the stubbed backends and missing Helm chart are defensible for a "Phase 1 library" interpretation — but the design doc's "ship the wedge product at Week 14-18" is NOT what this Phase 1 delivered. Proceed to Phase 2 after addressing B1 (one real backend per tier, even if minimal) and B2 (promote T19 to a proper 7-scenario integration test). The code is ready; the product is not.

---

*`.kiro/specs/phase1-trust-layer-SCORING.md` — independent LLMJ review*
*Weighted score: 7.82 / 10 — CONDITIONAL GO*
