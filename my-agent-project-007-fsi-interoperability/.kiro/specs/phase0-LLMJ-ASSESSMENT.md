# Phase 0 LLMJ Deep Assessment — Foundation Layer (M3 + M5)

> Role: Independent LLM Judge
> Scope: Phase 0 per steering file line 73 — `M3 (18 types) + M5 (config templates)`
> Date: 2026-04-27
> Source of truth: `docs/architecture/ARCH-09-complete-module-map.md`, `ARCH-04-v2`, `ARCH-07`, `IMPL-06-blocker-resolution-plan.md`, `schemas/canonical/DECISION-LOG.md`, module specs (`m3-canonical-schema-REVIEW-v2.md` GO 8.35, `m5-enterprise-config-REVIEW-v2.md` GO 8.18)
> Verdict: **GO — 8.62 / 10**

---

## Executive Summary

Phase 0 is the most complete foundation layer in the project. Every module built on top of Phase 0 (M1 identity, M6 gateway, M7 translators, M8 pipeline, M9 router, M10 audit, compliance gaps) is already importing from M3 and/or M5 successfully — the foundation is not just written, it's load-bearing and working.

- **Tests:** 220 passing (57 M3 unit + 64 M5 unit + 9 Phase-0 integration + 90 schema-reconciliation). Clean run, 1.01s, 0 failures, 2 expected UserWarnings for BD-without-Smarsh / FINRA.
- **Schemas:** all 18 JSON Schema files validate (Draft 2020-12 + `$id` format + field-level description + Client PII x-pii markers).
- **Pydantic ↔ JSON parity:** 18/18 types — field-names, required-arrays, `$schema`, `$id` all match.
- **DECISION-LOG:** 16 decisions recorded, 3 pending-SME items explicitly flagged (Holding accrued interest, SecurityIdentifier canonical ID, Performance methodology default).
- **Downstream consumers:** M1, M2/M4, M6, M7, M8, M9, M10, compliance gaps all import from M3/M5 cleanly. No cross-module imports detected (AST scan enforced in `test_no_cross_module_imports`).

Where it frays is around two SHARED-WITH-M5 amendments that are not technically Phase 0 scope but will block Phase 2 integration tests:
1. `IntentRouterConfig` (M9 Known Blocker row 2) — NOT shipped in `m5_config_loader/loader.py`.
2. `PipelineConfig` (M8 Known Blocker row 1) — NOT shipped in `m5_config_loader/loader.py`.

These are M5 v0.3.0 / v0.4.0 work. They don't block Phase 1 (trust layer).

---

## Scorecard (Weighted)

| # | Dimension | Weight | Score | Weighted |
|---|-----------|--------|-------|----------|
| 1 | Completeness | 25% | 9.0 | 2.250 |
| 2 | Accuracy | 20% | 8.5 | 1.700 |
| 3 | Security | 20% | 8.5 | 1.700 |
| 4 | Testability | 15% | 9.0 | 1.350 |
| 5 | Design Alignment | 10% | 9.0 | 0.900 |
| 6 | Gaps | 10% | 7.2 | 0.720 |
| | **TOTAL** | **100%** | | **8.62** |

GO threshold (≥ 8.0) met.

---

## Dimension 1 — Completeness (25%) — Score 9.0/10

### Evidence

**M3 — 18 canonical types, every one present and importable:**

| # | Type | Pydantic class | JSON file | Key assertions |
|---|------|---------------|-----------|----------------|
| 1 | Client | `Client` | `client.json` | 5 PII fields x-pii; client_type validator |
| 2 | Household | `Household` | `household.json` | Container model; members top-level |
| 3 | Holding | `Holding` | `holding.json` | cost_basis_method NOT present (correct) |
| 4 | TaxLot | `TaxLot` | `tax-lot.json` | cost_basis_method REQUIRED; validator rejects None |
| 5 | Order | `Order` | `order.json` | 12 OrderStatus states |
| 6 | Transaction | `Transaction` | `transaction.json` | 19 TransactionType values |
| 7 | Balance | `Balance` | `balance.json` | is_real_time + account_type |
| 8 | Performance | `Performance` | `performance.json` | TWR + 3 methodologies |
| 9 | SecurityProfile | `SecurityProfile` | `security-profile.json` | is_restricted + mnpi_flag |
| 10 | Quote | `Quote` | `quote.json` | is_delayed REQUIRED |
| 11 | PlanSummary | `PlanSummary` | `plan-summary.json` | Summary-level only |
| 12 | Goal | `Goal` | `goal.json` | 11 GoalType, 5 GoalStatus |
| 13 | InteractionSummary | `InteractionSummary` | `interaction-summary.json` | CRM write-back + principal review |
| 14 | ComplianceCheck | `ComplianceCheck` | `compliance-check.json` | wsp_section optional |
| 15 | ComplianceAlert | `ComplianceAlert` | `compliance-alert.json` | wsp_section REQUIRED (rule 19) |
| 16 | AuditEntry | `AuditEntry` | `audit-entry.json` | 3-tier WORM + provenance_chain |
| 17 | ResearchBrief | `ResearchBrief` | `research-brief.json` | Anti-fabrication score; sources required |
| 18 | PaymentInstruction | `PaymentInstruction` | `payment-instruction.json` | BSA/AML + HITL + ISO 20022 |

**M3 — 17 enums** (matches AC7.1 after v2 review correction): AccountType (16), SourceSystem (21), CostBasisMethod (5), OrderStatus (12), TransactionType (19), ComplianceCheckType (12), ComplianceDecision (5), AlertType (15), AlertSeverity (5), AlertStatus (6), PaymentType (7), PaymentStatus (10), AssetClass (12), GoalType (11), GoalStatus (5), PerformanceMethodology (3), PerformancePeriod (9). Unit tests assert each count.

**M3 — 20+ sub-models:** SecurityIdentifier, Reconciliation, HitlApproval, PII, 4 client vendor mappings, 3 household vendor mappings, 3 plan vendor mappings, 3 goal vendor mappings, CrmWriteBack, ComplianceReview, ActionItem, Attendee, Beneficiary (3 x-pii fields), BsaAml, Iso20022Mapping, TaxImpact, CostBasisImpact, PlanAssumptions, PlanRecommendation, GoalAssumptions, EscalationEntry, AlertResolution, AlertEvidence, ProvenanceStage, Valuation, **`ResearchSource`** (confirms ARCH-06 v3 Gap 2 requirement — liability provenance source ledger present).

**M5 — EnterpriseConfig shipped with 10 sub-models and 8 enums:**

| Element | Count | Match to ARCH-04 v2 / ARCH-07 |
|--------|-------|-------------------------------|
| Top-level fields | 11 (config_version, firm, archetype, jurisdiction, deployment, vendors, channels, compliance, specialists, memory, config_hash) | ✓ |
| Archetype enum | 5 tiers | ✓ consolidated design Part 6 |
| Jurisdiction enum | 5 (us, eu, uk, sg, hk) | ✓ ARCH-06 Gap 7 |
| RegistrationType | 3 | ✓ |
| Topology | 3 (cloud, hybrid, onprem) | ✓ steering rules 24-26 |
| Runtime | 2 (managed_agents, strands_sdk) | ✓ rule 1, snake_case per v1 fix |
| SuitabilityStandard | 2 | ✓ |
| PrincipalReviewMode | 2 (pre_use, post_use) | ✓ FINRA 2210 |
| TimeoutAction | 2 | ✓ |
| Sample YAML configs | 2 (tier3-bd, tier4-ria) | ✓ both load and validate |
| Security | 10 regex + 5 keyword patterns | ✓ |
| OPA helper | `get_opa_bundle_prefix()` → tierN/ | ✓ |
| Hash | deterministic SHA-256 `config_hash` | ✓ |

### Strengths

- Every required type is present. No skeletons. No placeholders.
- Pydantic ↔ JSON parity enforced via 90 parametrized tests (18 types × 5 checks).
- `PII_FIELDS` registry auto-builds by scanning `model_json_schema()` — forgetting `x-pii` silently fails the registry, creating an incentive to annotate correctly.
- `CANONICAL_TYPES` dict is the single import-time registry every downstream module uses. M7 translators use it via `from m3_schema_registry import CANONICAL_TYPES, SourceSystem`.
- `scripts/validate-schemas.py` checks every property in every JSON file has a `description`. Passes.
- DECISION-LOG has 16 explicit entries with Date/Type/Field/Decision/Rationale/Decided By.

### Weaknesses

- `ResearchBrief.sources: list[ResearchSource]` is REQUIRED (correct) but `ResearchSource` itself only requires `source_type` and `description`. Numeric-token → source-ledger mapping (ARCH-06 v3 Gap 2 strict form) is expressed via `url` + `source_date`, not a strongly-typed mapping. Fine for Phase 0, tighten when provenance wires up.
- M5 `MemoryConfig` accepts `memory: {}` and fills defaults (good ergonomics) but the integration test passes `memory={}` without asserting defaults populate. Small gap.

### What would make it a 10
- Ship `IntentRouterConfig` and `PipelineConfig` SHARED-WITH-M5 amendments.
- Add round-trip serialization test on `EnterpriseConfig`.
- Strongly type `ResearchSource` numeric-token field for Gap 2.

---

## Dimension 2 — Accuracy (20%) — Score 8.5/10

### Evidence

**Field-level accuracy vs vendor reality:**

| Concern | Expected | Found | Verdict |
|---------|----------|-------|---------|
| `cost_basis_method` on TaxLot | REQUIRED, never null, 5-value enum | `CostBasisMethod` enum + `@field_validator(mode="before")` raises "regulatory violation" on None | ✅ |
| `cost_basis_method` on Holding | MUST NOT exist | `"cost_basis_method" not in Holding.model_fields` enforced | ✅ |
| Household vendor mappings | SF FSC=relationship, Orion=portfolio_management, Schwab=custodial | All 3 sub-models with correct `grouping_type` defaults | ✅ |
| Household members | Top-level, NOT in vendor_mappings | `members: list[HouseholdMember]` at top level; no `member` substring in any vendor mapping (test enforced) | ✅ |
| Reconciliation | `sources_agree`, `discrepancies[]`, `last_reconciled` | Shared sub-model with exactly those 3 fields | ✅ |
| 16 AccountType values | BLOCKER-8 resolution list | Exact 16-value match | ✅ |
| Client PII | 5 fields (email, phone, DOB, ssn_last_four, tax_id) | All 5 `json_schema_extra=PII.MARKER` → `x-pii: true` | ✅ |
| Beneficiary PII | account_number, routing_number, iban | All 3 marked PII (v2 review fix applied) | ✅ |
| SecurityProfile MNPI | is_restricted, mnpi_flag | Present, explicitly NOT x-pii (tested) | ✅ |
| Quote `is_delayed` | REQUIRED | No default; ValidationError if omitted (tested) | ✅ |
| ComplianceAlert `wsp_section` | REQUIRED (rule 19) | No default; ValidationError if omitted (tested) | ✅ |
| ComplianceCheck `wsp_section` | Optional | Optional, defaults None (tested) | ✅ |

**M5 accuracy vs architecture:**

| Architecture ref | Required | Found | Verdict |
|------------------|----------|-------|---------|
| ARCH-04 v2 Runtime | snake_case `managed_agents` | `Runtime.managed_agents.value == "managed_agents"` | ✅ |
| ARCH-06 Gap 1 Reg BI | conflict_inventory, auto_generate, require_advisor_review, narrative_model | All 4 on `RegBiConfig` | ✅ |
| ARCH-06 Gap 5 ERISA | account_type on relevant types | Balance, Holding, Transaction, Order have `account_type: Optional[AccountType]` | ✅ |
| ARCH-06 Gap 7 Cross-border | 5 jurisdictions | us/eu/uk/sg/hk | ✅ |
| Steering rule 19 | wsp_section on OPA rule outputs | ComplianceAlert.wsp_section REQUIRED | ✅ |
| Firm LEI | ISO 17442 (18 alphanum + 2 check) | `^[A-Z0-9]{18}[0-9]{2}$` | ✅ |
| WORM retention | ≥ 6 years (SEC 17a-4) | `Field(..., ge=6)` | ✅ |
| HITL timeout | Bounded | `Field(24, ge=1, le=168)` | ✅ |

**SourceSystem purpose clarified** via DECISION-LOG: "Validation in M7 translators. source_system fields on types are string (not enum) for flexibility with new vendors." M7 imports `SourceSystem` from M3 — consistent.

### Strengths

- Custodian defaults called out in TaxLot docstring exactly as rule 7 requires (Schwab=specific_lot, Fidelity=average_cost MF / specific_lot equities).
- Hardest case (Household with 3-vendor semantic disagreement) handled correctly — container model, not flattened, per rule 6.
- Settlement date documented as T+1 since May 2024 — current with reality.
- ISO 4217 currency + ISO-3166-1 alpha-2 + ISO 20022 pain.001 cited where appropriate.

### Weaknesses

- Cross-reference type inconsistency: `Holding.account_ref: str` vs `Transaction.account_ref: UUID`. Both are "canonical Account ID." Flagged in v2 review G8; still present. Design smell, not blocker.
- `float` for financial amounts. DECISION-LOG allows migrating to Decimal if reconciliation shows drift, but no quantitative threshold specified.
- `firm_id` type asymmetry: Client has `UUID`, ComplianceAlert/AuditEntry have `str`. Same semantic concept, different types.
- `SpecialistConfig.VALID_SPECIALISTS` narrow (4 values). ARCH-05 v2 describes supervisor + 5 specialists. Compliance correctly excluded per rule 5. Looks right but worth a doc note.

### What would make it a 10
- Standardize `*_ref` fields to UUID everywhere (or consistently to string).
- Standardize `firm_id` type.
- Document Decimal migration trigger threshold in DECISION-LOG.

---

## Dimension 3 — Security (20%) — Score 8.5/10

### Evidence

**PII handling (steering rule 7):**

- 5 Client PII fields annotated `json_schema_extra=PII.MARKER` → `x-pii: true` in schema output. Auto-scanned into `PII_FIELDS` at import. M4 `mnpi.py` imports `Beneficiary, Client` and uses the annotation for filtering.
- Beneficiary nested PII (account_number, routing_number, iban) marked — v2 review gap closed.
- SecurityProfile `is_restricted` and `mnpi_flag` explicitly NOT x-pii (MNPI indicators, not PII) — tested.

**Cost-basis enforcement (steering rule 16):**

- `TaxLot.cost_basis_method: CostBasisMethod = Field(description=...)` — no default, required.
- `@field_validator("cost_basis_method", mode="before")` raises `ValueError("cost_basis_method is REQUIRED and cannot be None. Wrong cost basis method = wrong tax reporting = regulatory violation.")`.
- `test_cost_basis_method_none_rejected` asserts the regex "regulatory violation" in the raised error.
- Holding deliberately omits `cost_basis_method` — `test_holding_has_no_cost_basis_method` enforces.
- M7 translators (`cost_basis.py`, `schwab/taxlot.py`, `orion/taxlot.py`) import `CostBasisMethod` and use `normalize_cost_basis_method`. Enforcement is live, not just tested in isolation.

**No credentials (steering rule 20):**

- `validate_no_secrets()` runs BEFORE Pydantic parses YAML. Detects `AKIA`, `Bearer `, `sk-`, `ghp_`, `xox[bp]-`, `-----BEGIN`, `postgresql://`, `mongodb://`, `redis://`, `mysql://`, and key=value pairs containing `password|secret|api_key|apikey|token=`.
- 9 positive-detection tests + 1 clean-pass test.
- Both sample YAMLs tested against `validate_no_secrets` — pass because neither includes any credential.
- Only identifier-like value in samples is firm LEI, which is a public ISO 17442 identifier.

### Strengths

- Secret scanner recursive — a secret at `root.nested.items[2].deep.value` is caught with exact path.
- PEM detection robust — test itself splits the marker to dodge Amazon CodeDefender false positives; runtime matcher still works.
- `extra="forbid"` on every Pydantic model catches YAML typos at load time.
- `model_validator(mode="after")` on `EnterpriseConfig` emits `UserWarning` (testable via `pytest.warns`) for BD archetype without FINRA 2210 principal review OR without Smarsh. Matches rules 17-18.
- `config_hash` (SHA-256 of file bytes) supports tamper-detection when M10 ingests the loaded config.

### Weaknesses

- No field-level encryption metadata. PII fields marked for filtering but no `x-encrypt-at-rest` or `x-kms-key-class` annotation. Rules 20-23 imply per-tenant KMS. Whether that's M3 or M10/infrastructure is a design call; the spec-v2 review flagged it as a gap and it remains unaddressed.
- `pyproject.toml filterwarnings` silences pydantic DeprecationWarning and jose DeprecationWarning — fine for ergonomics but masks real deprecation signals.
- Secret regex `token=` keyword requires `=` in the value, so `token: "abc123"` in plain YAML could slip past. Coverage of SaaS prefixes (ghp_, sk-, xox…) compensates.
- No runtime enforcement of `SourceSystem` enum on canonical type fields. `source_system: str` is free-form. Intentional per DECISION-LOG for vendor flexibility; worth a note.

### What would make it a 10
- Add `x-encrypt-at-rest: true` annotation to Client + Beneficiary PII fields. Documents intent even without runtime.
- Add `allowed_source_systems` M5 config field that M3 can enforce via validator override.
- Add test scanning every type's JSON Schema and asserting every PII-classified field has `x-pii: true`.

---

## Dimension 4 — Testability (15%) — Score 9.0/10

### Evidence

**Test counts (actual, from `pytest --collect-only`):**

| Suite | File | Count |
|-------|------|-------|
| M3 unit | `tests/unit/test_m3_schema_registry.py` | **57** |
| M5 unit | `tests/unit/test_m5_config_loader.py` | **64** |
| Phase 0 integration | `tests/integration/test_phase0_m3_m5.py` | **9** |
| Schema reconciliation | `tests/schema-reconciliation/test_schema_json_match.py` | **90** (18 types × 5 checks) |
| **Phase 0 total** | | **220** |

Full run: **220 passed**, 2 expected UserWarnings, 1.01s. `scripts/validate-schemas.py` → `All 18 schemas validated successfully.`

**What the tests actually assert:**

- `test_cost_basis_method_none_rejected` uses `pytest.raises(ValidationError, match="regulatory violation")` — exact compliance message enforced, not just error class.
- `test_vendor_mappings_no_member_lists` walks `HouseholdVendorMappings.model_fields` asserting `"member" not in field_name.lower()`. Regression-proof.
- `test_no_cross_module_imports` uses `ast.parse` + `ast.walk` to scan every Python file in `src/m3_schema_registry/` for imports starting with `m1_`…`m13_`. CI enforced.
- `test_only_allowed_imports` allow-lists `{__future__, datetime, decimal, enum, typing, uuid, pydantic, m3_schema_registry}` and fails otherwise.
- `test_all_types_serializable` runs `model_json_schema()` + `json.dumps` + `json.loads` for every type.
- `test_field_names_match` and `test_required_fields_match` parametrized across all 18 types — adding a Pydantic field without updating JSON (or vice versa) blows up immediately.
- `test_schema_has_valid_id` asserts `https://007.fsi/schemas/canonical/{slug}/v0.1.0`.
- `test_config_hash_deterministic` asserts `sha256(file_bytes)` stable across loads.
- `test_ria_no_warnings` uses `warnings.simplefilter("error")` to assert RIA archetype produces zero UserWarnings.

### Strengths

- All tests deterministic. No sleep, no network, no flake.
- `pytest.warns` for non-blocking BD guardrails — testable without crash-on-sight.
- Round-trip serialization tested at type level (`test_tax_lot_round_trip`, `test_household_round_trip`, `test_client_round_trip`) — closes M7 integration seam.
- Module-boundary AST scan saves a week of pain the first time someone writes `from m6_mcp_gateway import ...` to "just get the types."
- `test_all_5_archetypes_have_opa_prefix` iterates every Archetype, asserts `get_opa_bundle_prefix()` returns valid `opa-bundles/tierN/`. Means new archetype additions won't silently break OPA routing.

### Weaknesses

- No Hypothesis property tests on M3/M5. Project already uses Hypothesis for M8/M9. M3 types would benefit from construct-dump-reparse property tests.
- No explicit enum-rejection negative tests. Pydantic guarantees the behavior; explicit tests are cheap insurance.
- No test asserting tier3-bd.yaml BSA/AML thresholds match Pydantic defaults. If either drifts, nothing fails.

### What would make it a 10
- 3-5 Hypothesis property tests (round-trip, random-field-mutation rejection, Decimal-ish float precision).
- Enum-rejection negatives for TransactionType, OrderStatus, AlertType, AccountType.
- Cross-config template-drift test: tier3 principal_review_enabled == True; tier4 == False.

---

## Dimension 5 — Design Alignment (10%) — Score 9.0/10

### Cross-Module Dependency Verification

| Consumer | ARCH-09 says needs | M3/M5 expose | Status |
|----------|-----|-----|-----|
| M1 Identity | M5 (Archetype, RegistrationType, FirmConfig) | All imported in `m1_identity/claims.py` + `service.py` | ✅ |
| M2/M4 Policy | M3 (Client, Beneficiary, Holding); M5 (Archetype, RegistrationType) | M3 types in `mnpi.py`; M5 enums in `authority.py` | ✅ |
| M6 Gateway | M3 (AuditEntry, ProvenanceStage) | Imported in `audit_builder.py` | ✅ |
| M7 Translators | M3 (18 types, CostBasisMethod, SourceSystem, CANONICAL_TYPES, vendor sub-models) | Imported in every translator + `__init__.py` | ✅ |
| M8 Pipeline | M3 (Client, Holding, ResearchBrief, ResearchSource) | Imported in `state.py` + `nodes/stage_19_brief_assembly.py` | ✅ |
| M9 Router | M5 (Archetype, Runtime); M1 (AidClaims). NOT M3 per ARCH-09 | Imported in `models.py`. No M3 import. | ✅ |
| M10 Audit | M3 (AuditEntry, ProvenanceStage) | Imported in `logger.py`, `backends.py`, `provenance.py` | ✅ |
| M11 REST Adapters | (indirect via M7) | TypeScript adapters call M7 Python | ✅ |
| Compliance Gap 2 | M3 (ProvenanceStage) | Imported in `attribution.py` | ✅ |
| Compliance Gap 6 | (ResearchSource, AuditEntry) | Imported | ✅ |

**Match to ARCH-04 v2 / ARCH-07 stack:**

- Pydantic v2, JSON Schema Draft 2020-12, Python (pyproject `>=3.10`; ARCH-07 says 3.12+ — see Gaps). PyYAML. ✅
- `Runtime` enum snake_case matches Helm values keys. ✅
- `Topology` enum matches `values-cloud.yaml / values-hybrid.yaml / values-onprem.yaml`. ✅
- `get_opa_bundle_prefix()` aligns with `opa-bundles/tier{N}/` filesystem layout. ✅

**Match to IMPL-06 Blocker 3 (cost basis normalization):**

- TaxLot.cost_basis_method REQUIRED + enum-constrained + validator-enforced on None. ✅
- M7 translators consume `CostBasisMethod` via `normalize_cost_basis_method`. ✅
- DECISION-LOG row 1 cites "Compliance SME" as decider. ✅

### Strengths

- Zero surprise imports. AST tests enforce the module graph.
- Directory naming respects Python packaging (`src/m3_schema_registry/` underscore).
- `SCHEMA_VERSION = "0.1.0"` honest — pre-SME review. Will bump MAJOR on breaking change per rules 4-5.
- `CONFIG_VERSION = "0.1.0"` cross-checked at load time. Catches wrong-version YAML before Pydantic partial-validates.

### Weaknesses

- pyproject `requires-python = ">=3.10"` but steering rule 15 + both specs say 3.12+. Doesn't block Phase 0 (tests pass on 3.10.9) but contradicts spec.
- `scripts/validate-schemas.py` outside Schema Specialist boundary (project-root `scripts/`). v2 review G7; pragmatic but still a boundary note.

### What would make it a 10
- Bump pyproject to `>=3.12` before Phase 1.
- Move validate-schemas.py into `src/m3_schema_registry/scripts/` OR add steering addendum.

---

## Dimension 6 — Gaps (10%) — Score 7.2/10

### Critical (blocking Phase 2 integration)

| # | Gap | Blocks | Owner | Target |
|---|-----|--------|-------|--------|
| G1 | `IntentRouterConfig` NOT shipped in M5 | M9 integration tests needing config-loaded model_id, confidence_high, confidence_med, timeout_ms, fallback_enabled, tenant_hmac_key_vault_path | M5 (SHARED-WITH-M5) | v0.3.0 |
| G2 | `PipelineConfig` NOT shipped in M5 | M8 integration tests needing pipeline config | M5 (SHARED-WITH-M5) | v0.4.0 |
| G3 | pyproject `>=3.10` vs spec `3.12+` | Phase 1+ consistency | Platform | v0.2.0 |

### Minor (non-blocking)

| # | Gap | Impact |
|---|-----|--------|
| G4 | Cross-ref type inconsistency (UUID vs str) | Design smell; M8 pipeline state must handle both |
| G5 | `firm_id` type varies across types | Same family as G4 |
| G6 | `float` financial amounts without quantitative migration trigger | Possible precision drift in M7 reconciliation |
| G7 | 3 pending-SME decisions in DECISION-LOG unresolved (Holding accrued interest, SecurityIdentifier canonical ID, Performance methodology default) | M7 translator accuracy; M8 pipeline ambiguity |
| G8 | `scripts/validate-schemas.py` outside Schema Specialist boundary | Cosmetic |
| G9 | No `x-encrypt-at-rest` annotation on PII fields | Documentation gap |
| G10 | No Hypothesis property tests on M3/M5 | Testability thoroughness |

### Cross-Module Dependency Table (consolidated)

| Consumer | M3 needs | M5 needs | Status |
|----------|----------|----------|--------|
| M1 Identity | — | Archetype, RegistrationType, FirmConfig | ✅ SHIPPED |
| M2/M4 Policy | Client, Beneficiary, PII_FIELDS, Holding, TaxLot | Archetype, RegistrationType | ✅ SHIPPED |
| M6 Gateway | AuditEntry, ProvenanceStage | — | ✅ SHIPPED |
| M7 Translators | 18 types, CostBasisMethod, SourceSystem, CANONICAL_TYPES, vendor sub-models | — | ✅ SHIPPED |
| M8 Pipeline | Client, Holding, ResearchBrief, ResearchSource, state types | `PipelineConfig` | ⚠️ **M5 MISSING** |
| M9 Router | — (no M3 per ARCH-09) | Archetype, Runtime, SpecialistConfig, `IntentRouterConfig` | ⚠️ **M5 MISSING `IntentRouterConfig`** |
| M10 Audit | AuditEntry, ProvenanceStage | — | ✅ SHIPPED |
| M11 REST Adapters | (indirect via M7) | (indirect via M5 firm) | ✅ SHIPPED |
| M12 Supervisor (Phase 2) | Intent via M9; maybe Client | SpecialistConfig, Archetype | ✅ SHIPPED |
| M13 FIX Bridge (Phase 4) | Order, Transaction | DeploymentConfig | ✅ SHIPPED |
| Compliance Gap 2 | ProvenanceStage | — | ✅ SHIPPED |
| Compliance Gap 6 | ResearchSource, AuditEntry | — | ✅ SHIPPED |

**10 of 12 consumers GREEN. 2 YELLOW (M8 PipelineConfig, M9 IntentRouterConfig) — both Phase 2, both SHARED-WITH-M5 amendments designed in the M8/M9 specs but not yet coded in M5.**

### What would make it a 10
- Close G1 and G2: ship `IntentRouterConfig` + `PipelineConfig` in M5 v0.3.0 / v0.4.0 before Phase 2 gate.
- Close G3: bump pyproject to 3.12.

---

## Known Blockers (Outstanding)

| # | Blocker | Source | Blocks | Target | Status |
|---|---------|--------|--------|--------|--------|
| B1 | `IntentRouterConfig` sub-model: model_id, provider, confidence_high (0.95), confidence_med (0.80), timeout_ms (1500), fallback_enabled (True), tenant_hmac_key_vault_path, region, utterance_hmac_algorithm, cost_budget_usd_per_day | m9-intent-router.md §Known Blockers row 2 | M9 integration; Phase 2 gate | M5 v0.3.0 | **NOT STARTED** |
| B2 | `PipelineConfig` sub-model (M8 stage configs, HITL gates, LangGraph checkpointer settings) | m8-pipeline-engine.md | M8 integration; Phase 2 gate | M5 v0.4.0 | **NOT STARTED** |
| B3 | 3 pending-SME schema decisions | DECISION-LOG §Pending SME | M7 translator accuracy; M8 research pipeline | M3 v0.2.0 | **PENDING SME** |
| B4 | Python version mismatch (pyproject 3.10 vs spec 3.12) | This assessment | Consistency | M3/M5 pyproject v0.2.0 | **OPEN** |

---

## Recommendations for v0.3.0+

**Must-do for Phase 2 gate (blocking):**

1. Ship M5 `IntentRouterConfig` + wire into `EnterpriseConfig`. Add to both sample YAMLs. Bump `CONFIG_VERSION` to `0.3.0`. Update `test_m5_config_loader.py`.
2. Ship M5 `PipelineConfig` + wire. Same pattern. Bump to `0.4.0`.
3. Bump `pyproject.toml` `requires-python` to `>=3.12`.

**Should-do before Phase 1 trust-layer gate (non-blocking but valuable):**

4. Resolve the 3 PENDING-SME entries. Each one will bite a downstream module.
5. Standardize `*_ref` fields to UUID across all 18 types (or document the asymmetry for v1.0.0 cleanup).
6. Standardize `firm_id` type across Client, ComplianceAlert, AuditEntry.
7. Add `x-encrypt-at-rest: true` annotation to Client + Beneficiary PII fields.
8. Add Hypothesis property tests for round-trip serialization on all 18 types.
9. Add enum-rejection negative tests for TransactionType, OrderStatus, AlertType, AccountType.
10. Resolve `scripts/validate-schemas.py` boundary — move or add steering addendum.

**Nice-to-do for v0.5.0+ (after Phase 2):**

11. Define Decimal migration trigger: "if M7 reconciliation tests observe >$0.01 drift on any amount field, migrate that type's `float` → `Decimal`."
12. Add `allowed_source_systems` configurable field in M5 that M3 enforces via validator override.
13. Consider lifting `ResearchSource` to a first-class canonical type — simplifies ARCH-06 v3 Gap 2 liability provenance.

---

## Final Verdict

**GO — 8.62 / 10.** Phase 0 is a solid foundation. Ship it.

Why this foundation is worth trusting:

- 220 tests green in a second. No flakes.
- 18/18 JSON schemas valid. Pydantic ↔ JSON parity enforced by 90 parametrized tests.
- Module boundary enforced by AST scanning, not just docs.
- `cost_basis_method` mandate implemented AND validated AND consumed by M7. Three layers close the loop.
- PII annotation (`x-pii: true`) live, auto-scanned, consumed by M4. Not aspirational.
- Household container model correctly preserves three conflicting vendor semantics.
- 10 of 12 downstream consumers already importing from M3/M5 successfully.
- 16 documented decisions in DECISION-LOG with owners and rationale.
- Zero credentials in config + runtime scanner.

What keeps it off 9.0:

- 2 SHARED-WITH-M5 config amendments (`IntentRouterConfig`, `PipelineConfig`) designed in the M8/M9 specs but not yet coded in M5. They will block Phase 2 integration.
- pyproject Python lags the spec (3.10 vs 3.12).
- Minor ref-type and firm_id asymmetries.
- 3 pending-SME decisions affecting M7 accuracy.

None of these stop the foundation from serving Phase 1 (M1 + M10 + M2/M4 + M6 — the trust layer). The trust layer does not consume `IntentRouterConfig` or `PipelineConfig`. Phase 1 can start today against this foundation.

Phase 0 earns a GO. Proceed to Phase 1 integration gate with M1 + M10 + M2/M4 + M6 assessment.

---

*LLMJ Phase 0 Deep Assessment — Project 007 FSI Interoperability Platform*
*220 tests passing | 18 types validated | 8.62 / 10 GO*
