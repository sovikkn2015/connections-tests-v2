# LLMJ Review: M3 Canonical Schema Registry Spec

> Reviewer: Schema Specialist (LLMJ)
> Date: 2026-04-16
> Spec Under Review: `.kiro/specs/m3-canonical-schema.md`
> Source-of-Truth Documents:
>   - `007-consolidated-design-and-plan.md` (Part 10)
>   - `ARCH-09-complete-module-map.md` (M3 row + Compliance Sub-Modules)
>   - `ARCH-07-definitive-tech-stack.md` (Stack Per Module for M3)
>   - `IMPL-06-blocker-resolution-plan.md` (Blocker 3)
>   - `DECISION-LOG.md` (archived, 30+ decisions)
>   - `007-build-strategy.md` (spec-first principles)
> Verdict: **CONDITIONAL GO** — fixable issues, but must be fixed before code starts

---

## DIMENSION 1: COMPLETENESS — Score: 4/10

This is the spec's weakest dimension. The gap between what the design docs require and what the spec defines is severe.

### 1A. The 18 Types Are Listed But Not Specified

The spec lists all 18 type names in AC1.1. That's correct. But the spec contains **zero field-level definitions** for any of the 18 types. The entire "Design" section is 20 lines — a file structure and an API surface listing function signatures.

Compare to what the design docs require:
- IMPL-06 Blocker 3 specifies the Household schema field-by-field (canonical_id, display_name, primary_source, members with roles, vendor_mappings with 3 vendor objects, reconciliation with sources_agree/discrepancies/last_reconciled).
- IMPL-06 specifies TaxLot fields (cost_basis_method, source_custodian, source_cost_basis_method).
- The DECISION-LOG has 30+ field-level decisions across all 18 types.
- The archived implementation has 1,037 lines of Pydantic models with 78 classes.

The spec says "Write 6 Pydantic models with schema_version, required fields, MNPI annotations" in Task 2 but never says **what those fields are**. This is a blank check to the implementer.

**Impact**: An implementer working from this spec alone would have to reverse-engineer field definitions from the design docs, the DECISION-LOG, and the archived code. The spec fails its primary purpose: being the contract between design and implementation.

### 1B. Line Estimate Mismatch

ARCH-09 estimates M3 at **~1,700 lines** (YAML + Python). IMPL-06 revised estimates: ~1,200 lines YAML + ~500 lines Python validation = ~1,700 total.

The spec proposes **2 files**: `__init__.py` + `models.py`. The archived implementation that actually built all 18 types is 1,037 lines in `types.py` alone, plus `__init__.py`, plus `pyproject.toml`, plus `requirements.txt`. And that's just the Python side — the 18 JSON Schema files in `schemas/canonical/` are another ~1,200+ lines.

The spec doesn't mention JSON Schema files at all. R6 says "exportable as JSON Schema" via `model_json_schema()`, but the design docs (ARCH-07, ARCH-09) explicitly list "JSON Schema" as M3's framework. The spec treats JSON Schema as a derived artifact. The design docs treat it as a primary artifact.

### 1C. Missing Enums and Sub-Models

The spec defines 7 enums (AC5.1-AC5.7). The archived implementation has **15+ enums** and **20+ sub-models**:

Missing enums from spec:
- `SourceSystem` enum (21 values — every vendor in the platform)
- `TransactionType` enum (19 values — per DECISION-LOG)
- `ComplianceCheckType` enum (12 values)
- `ComplianceDecision` enum (5 values: ALLOW/DENY/WARN/REQUIRE_APPROVAL/ESCALATE)
- `AlertType` enum (15 values — per DECISION-LOG)
- `AlertSeverity` enum (5 values)
- `AlertStatus` enum (5 values)
- `PaymentType` enum (7 values)
- `PaymentStatus` enum (10 values)
- `AssetClass` enum (12 values)
- `GoalType` enum (11 values)
- `GoalStatus` enum (5 values — per DECISION-LOG)
- `PerformanceMethodology` enum (3 values — per DECISION-LOG)
- `PerformancePeriod` enum (9 values)

Missing sub-models:
- `SecurityIdentifier` (ticker, cusip, isin, figi, sedol, bloomberg_id)
- `Reconciliation` (sources_agree, discrepancies, last_reconciled)
- `HitlApproval` (approver_id, approved_at, approval_token)
- `ProvenanceStage` (stage, module, hash, timestamp)
- `Beneficiary`, `BsaAml`, `Iso20022Mapping` (PaymentInstruction sub-models)
- `CostBasisImpact` (Transaction sub-model)
- `PlanAssumptions`, `PlanRecommendation` (PlanSummary sub-models)
- `GoalAssumptions` (Goal sub-model)
- `ActionItem`, `Attendee`, `CrmWriteBack`, `ComplianceReview` (InteractionSummary)
- All vendor mapping sub-models (Client, Household, PlanSummary, Goal)

### 1D. Missing Standard Fields

The design docs (Rule 18, IMPL-06) require standard fields on every type:
- `canonical_id` (uuid) — mentioned nowhere in the spec
- `source_system` + `source_id` — mentioned nowhere
- `vendor_mappings` — only mentioned for Household
- `reconciliation` — only mentioned for Household (as `discrepancy_flag`)
- `trace_id` — mentioned nowhere
- `x-pii: true` markers — spec mentions "MNPI" in descriptions but not the `x-pii` JSON Schema extension or `json_schema_extra` Pydantic pattern

### 1E. Missing JSON Schema Files

Rule 1 requires JSON Schema Draft 2020-12 with `$schema` and `$id` for every type. The spec mentions JSON Schema only as an export (`model_json_schema()`). It does not specify:
- 18 individual `.json` files in `schemas/canonical/`
- The `$id` format: `https://007.fsi/schemas/canonical/{type}/v{semver}`
- Field-level `description` on every property (Rule 3)
- `x-pii: true` annotations in JSON Schema (Rule 11)
- The `reconciliation` object pattern (Rule 13)
- The `vendor_mappings` pattern (Rule 12)

---

## DIMENSION 2: ACCURACY — Score: 6/10

What the spec does define is mostly correct, but with notable errors.

### 2A. Household Container Model — Partially Correct

R2 correctly identifies Household as a CONTAINER model with vendor-specific groupings. AC2.1-AC2.4 are reasonable. However:

**Error**: AC2.3 defines `discrepancy_flag` (bool) and `discrepancy_notes` (optional str). The design docs (IMPL-06) and the archived schema use a `reconciliation` object with `sources_agree` (bool), `discrepancies` (list of strings), and `last_reconciled` (datetime). The spec's simplified version loses the `last_reconciled` timestamp and collapses the discrepancy list into a single string. This is a semantic mismatch with the source of truth.

**Error**: AC2.2 says "Each vendor mapping has: vendor name, vendor household ID, grouping type, member list." The design docs show vendor mappings do NOT contain member lists — members are at the Household level with source attribution. Vendor mappings contain vendor-specific IDs and grouping type only. Putting member lists inside vendor mappings would duplicate data and create reconciliation nightmares.

### 2B. Cost Basis Method — Correct But Incomplete

R3 correctly makes `cost_basis_method` REQUIRED on TaxLot. AC3.3 correctly lists the 5 enum values.

**Issue**: R3 also puts `cost_basis_method` on Holding. The archived implementation does NOT have `cost_basis_method` on Holding — it's on TaxLot only. Holdings have `tax_lots: list[TaxLot]` which contain the cost basis method. The design docs (IMPL-06 Blocker 3) only specify `cost_basis_method` on TaxLot, not Holding. The spec adds it to Holding without design doc justification.

**Missing**: The spec doesn't mention `source_cost_basis_method` (the custodian's native method name for reconciliation), which IMPL-06 explicitly requires.

### 2C. MNPI Annotation — Wrong Mechanism

R4/AC4.1-AC4.3 check for "MNPI" in Field descriptions. The actual mechanism per Rule 11 and the archived implementation is `"x-pii": true` in JSON Schema (implemented via `json_schema_extra=PII.MARKER` in Pydantic). Checking for "MNPI" in description strings is fragile and doesn't match the design.

**Also**: The spec calls it "MNPI" throughout. The design docs distinguish between PII (personally identifiable information: email, phone, DOB, SSN, tax_id) and MNPI (material non-public information: security-level, like `mnpi_flag` on SecurityProfile). The spec conflates these two concepts. M4 filters both, but they're different regulatory categories.

### 2D. Account Type Enum — Wrong Values

AC5.2 says "AccountType enum exists with 16 values (ERISA + non-ERISA)" but doesn't list them. Rule 10 in the system prompt lists: `individual`, `joint_tos`, `joint_tic`, `ira_traditional`, `ira_roth`, etc. But the DECISION-LOG (BLOCKER-8 resolution) explicitly chose DIFFERENT values: `taxable`, `traditional_ira`, `roth_ira`, `401k`, `403b`, `457`, `sep_ira`, `simple_ira`, `trust_revocable`, `trust_irrevocable`, `custodial_utma`, `custodial_ugma`, `erisa_pension`, `erisa_profit_sharing`, `529`, `hsa`.

The spec doesn't specify which convention to use, leaving this ambiguous. The DECISION-LOG already resolved this conflict — the spec should reference that decision.

### 2E. OrderStatus — Correct Count, Unverified Values

AC5.4 says "OrderStatus enum with full lifecycle (12 states per design doc)" but doesn't list the 12 states. The design doc (ARCH-09, Execution Specialist) specifies: DRAFT → COMPLIANCE_CHECK → PENDING_APPROVAL → APPROVED → SUBMITTED → CONFIRMED → PENDING_SETTLEMENT → SETTLED (+ SETTLEMENT_FAILED → ESCALATED + REJECTED + CANCELLED). That's 12. The spec should list them explicitly.

### 2F. Missing Enums from Spec

AC5.5 defines `RiskProfile` (5 levels) — not in the design docs. Where does this come from?
AC5.6 defines `Archetype` (5 tiers) — this is an M5 Enterprise Config concept, not an M3 schema type. The archived implementation uses string fields for archetype, not an enum in M3.
AC5.7 defines `Jurisdiction` (5: us, eu, uk, sg, hk) — reasonable but the design docs show jurisdiction as a string field, not a constrained enum in M3.

---

## DIMENSION 3: SECURITY — Score: 5/10

### 3A. PII/MNPI Marking Is Underspecified

The spec identifies 3 MNPI fields (AC4.1-AC4.3): Client.ssn, Client.date_of_birth, PaymentInstruction.recipient_account. The DECISION-LOG and Rule 11 identify at minimum: email, phone, date_of_birth, ssn_last_four, tax_id, and physical address on Client. The spec misses email, phone, and tax_id.

The `MNPI_FIELDS` dict (AC4.4) is a good idea but the spec doesn't define what fields go in it. The archived implementation uses `json_schema_extra={"x-pii": True}` on 5 Client fields. The spec's approach of checking description strings is not the same mechanism.

### 3B. PaymentInstruction Security Fields Missing

The spec mentions `PaymentInstruction.recipient_account` as MNPI but doesn't specify the BSA/AML fields that IMPL-06 and the DECISION-LOG require:
- `ctr_required` (bool, amount >= $10K)
- `sar_flagged` (bool, structuring patterns)
- `sanctions_screened` (bool)
- `ofac_screened` (bool)

These are regulatory requirements, not optional features.

### 3C. SecurityProfile MNPI Fields Missing

The DECISION-LOG specifies `is_restricted` and `mnpi_flag` on SecurityProfile. These are critical for M2 restricted list checks and M4 MNPI filtering. The spec doesn't mention them.

### 3D. No Mention of Data Classification

The archived Client model has `pii_classification: str` (public, internal, confidential, restricted). The spec doesn't address data classification at all.

---

## DIMENSION 4: TESTABILITY — Score: 6/10

### 4A. Acceptance Criteria Are Mostly Testable

AC1.1 (18 types), AC1.4 (CANONICAL_TYPES dict length), AC3.3 (enum values), AC3.4 (ValidationError on missing cost_basis_method), AC6.1 (valid JSON Schema export), AC7.1-AC7.2 (import restrictions) — these are all deterministic and testable.

### 4B. Missing Test Scenarios

The spec has no acceptance criteria for:
- Round-trip JSON serialization/deserialization for all 18 types
- `x-pii` markers appearing in exported JSON Schema
- `vendor_mappings` structure validation per type
- `reconciliation` object validation
- `canonical_id` is UUID format on every type
- `source_system` + `source_id` present on every type that requires them
- Field-level `description` present on every field (Rule 3)
- `$id` format validation on exported schemas
- `$schema` Draft 2020-12 on exported schemas
- Enum value completeness (e.g., TransactionType has exactly 19 values)

### 4C. No Reconciliation Test Criteria

Rule 9 requires reconciliation tests in `tests/schema-reconciliation/`. The spec puts all tests in `tests/unit/test_m3_schema_registry.py`. No reconciliation tests are specified. (Note: reconciliation tests are primarily an M7 concern, but M3 should have schema-level validation tests.)

### 4D. Ambiguous Criteria

AC2.2: "Each vendor mapping has: vendor name, vendor household ID, grouping type, member list" — as noted above, "member list" is wrong. This would produce a failing test against the correct implementation.

AC4.1: "Client.ssn has Field description containing 'MNPI'" — the field is `ssn_last_four`, not `ssn`. And the mechanism should be `x-pii` in json_schema_extra, not string matching on description.

---

## DIMENSION 5: DESIGN ALIGNMENT — Score: 4/10

### 5A. Tech Stack Mismatch

ARCH-07 Stack Per Module for M3: "Python | FastAPI + JSON Schema"
ARCH-09 Module Detail: "YAML + Python | JSON Schema + Pydantic | ~1,700 lines"

The spec says: "Python 3.12+ | Pydantic v2" — no mention of FastAPI, no mention of JSON Schema as a primary artifact, no mention of YAML.

**Critical**: ARCH-07 lists FastAPI as part of M3's stack. This implies M3 has an API surface (e.g., schema registry endpoint). The spec defines M3 as a pure Python library with no API. This is a fundamental architectural question: is M3 a library or a service?

The dependency matrix in ARCH-09 shows M3 calls nothing and is called by M7 (via Python import). This supports the library model. But ARCH-07's FastAPI reference suggests a service model. The spec should explicitly address and resolve this contradiction.

### 5B. File Structure Doesn't Match Design

The spec proposes:
```
src/m3_schema_registry/
  __init__.py
  models.py
```

The design docs and archived implementation require:
```
src/m3-schema-registry/          # Note: hyphen, not underscore
  __init__.py
  types.py                       # (or models.py — naming is a decision)
  pyproject.toml
  requirements.txt

schemas/canonical/
  client.json
  household.json
  tax-lot.json
  ... (18 JSON Schema files)
  DECISION-LOG.md
  README.md
```

The spec omits the entire `schemas/canonical/` directory. It omits `pyproject.toml` and `requirements.txt`. It uses underscores (`m3_schema_registry`) where the project uses hyphens (`m3-schema-registry`).

### 5C. Module Boundary Statement Is Wrong

The spec says: "M3 is the one exception to the 'no cross-module imports' rule — it's a shared data library, not a service."

Rule 16 says: "No cross-module imports. M3 and M7 do NOT import from M1, M2, M4, M5, M6, M8, M9, M10, M11, M12, or M13."

The ARCH-09 dependency matrix shows M7 calls M3 (M7 imports M3 types). This is correct — M3 is imported BY other modules, but M3 itself imports nothing. The spec's statement is misleading. M3 doesn't violate the rule; other modules importing M3's types is the designed pattern. The spec should state this clearly without calling it an "exception."

### 5D. Missing API Surface Elements

The spec's API surface lists `SCHEMA_VERSION: str = "1.0.0"`. But the schemas use `v0.1.0` in their `$id` URIs. Starting at 1.0.0 implies production-ready. Starting at 0.1.0 (per the archived schemas) correctly signals pre-1.0 development. This is a semver semantic issue.

---

## DIMENSION 6: GAPS — Score: 3/10

### Critical Gaps (Must Fix Before Code)

| # | Gap | Impact | Source |
|---|-----|--------|--------|
| G1 | No field-level definitions for any of the 18 types | Implementer has no contract. Will produce wrong fields. | IMPL-06, DECISION-LOG |
| G2 | No JSON Schema files specified | Missing ~1,200 lines of primary artifacts. Rule 1 violated. | ARCH-07, ARCH-09, Rule 1 |
| G3 | `x-pii` annotation mechanism not specified | M4 integration will fail. Security gap. | Rule 11, DECISION-LOG |
| G4 | `reconciliation` object pattern not specified | Types with multi-vendor sources will lack agreement tracking. | Rule 13, IMPL-06 |
| G5 | `vendor_mappings` pattern not specified beyond Household | Client, PlanSummary, Goal all need vendor_mappings. | Rule 12, DECISION-LOG |
| G6 | Standard fields (canonical_id, source_system, source_id, trace_id) not specified | Every type needs these. Spec doesn't mention them. | Rule 18, IMPL-06 |
| G7 | 15+ enums and 20+ sub-models missing | Spec defines 7 enums. Implementation needs 22+. | DECISION-LOG, archived code |
| G8 | AccountType enum values not specified (two conflicting conventions exist) | BLOCKER-8 resolution in DECISION-LOG chose specific values. Spec is silent. | DECISION-LOG |
| G9 | BSA/AML fields on PaymentInstruction not specified | Regulatory requirement. | IMPL-06, DECISION-LOG |
| G10 | `cost_basis_method` incorrectly placed on Holding (should be TaxLot only) | Design doc only puts it on TaxLot. Holdings contain tax_lots. | IMPL-06 Blocker 3 |

### Significant Gaps (Should Fix)

| # | Gap | Impact | Source |
|---|-----|--------|--------|
| G11 | ARCH-07 lists FastAPI for M3 — spec doesn't address this | Architectural ambiguity: library vs service? | ARCH-07 |
| G12 | Directory naming: spec uses `m3_schema_registry` (underscore), project uses `m3-schema-registry` (hyphen) | Import path mismatch | Archived project structure |
| G13 | `SCHEMA_VERSION = "1.0.0"` vs `v0.1.0` in schema $id URIs | Semver inconsistency | Archived schemas, Rule 4 |
| G14 | Spec says "Client.ssn" — field is actually `ssn_last_four` | Wrong field name in acceptance criteria | DECISION-LOG, archived code |
| G15 | No mention of DECISION-LOG maintenance (Rule 14) | Schema decisions won't be documented | Rule 14 |
| G16 | No mention of `schemas/canonical/README.md` | Missing documentation artifact | Archived project |
| G17 | Household AC2.2 says vendor mappings contain "member list" — they don't | Would produce wrong implementation | IMPL-06 |
| G18 | PII vs MNPI conflation | Different regulatory categories treated as one | Design docs |

### Minor Gaps

| # | Gap | Impact |
|---|-----|--------|
| G19 | No mention of `Decimal` type for financial amounts | Float precision issues in production |
| G20 | No mention of currency fields (ISO 4217) as standard pattern | Missing on types that need it |
| G21 | No mention of `as_of_date` pattern for point-in-time data | Missing temporal semantics |
| G22 | Spec doesn't reference the DECISION-LOG's pending SME decisions (market_value accrued interest, security_identifier canonical ID) | Could block implementation |

---

## SCORECARD

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| 1. COMPLETENESS | 4/10 | 25% | 1.00 |
| 2. ACCURACY | 6/10 | 20% | 1.20 |
| 3. SECURITY | 5/10 | 20% | 1.00 |
| 4. TESTABILITY | 6/10 | 15% | 0.90 |
| 5. DESIGN ALIGNMENT | 4/10 | 10% | 0.40 |
| 6. GAPS | 3/10 | 10% | 0.30 |
| **TOTAL** | | | **4.80/10** |

---

## VERDICT: CONDITIONAL GO

The spec correctly identifies the high-level requirements (18 types, Household container, cost_basis_method required, MNPI annotation, enums, JSON Schema export, module isolation). The intent is right. The structure (Requirements → Design → Tasks) follows the build strategy.

But the spec is a **skeleton**, not a contract. It defines WHAT M3 should do at a 10,000-foot level but provides almost zero field-level detail. An implementer working from this spec alone would produce a fundamentally different (and wrong) implementation than what the design docs require.

### Required Fixes Before Code Starts (10 items)

1. **Add field-level definitions** for all 18 types, either inline or by explicit reference to the DECISION-LOG and IMPL-06 Blocker 3 schema definitions. At minimum, list required fields, their types, and constraints for each of the 18 models.

2. **Add JSON Schema file specifications** in `schemas/canonical/`. Each of the 18 types needs a `.json` file with `$schema`, `$id`, field-level `description`, and `x-pii` markers. These are primary artifacts, not derived.

3. **Fix the `x-pii` annotation mechanism**. Replace "MNPI in description" with `"x-pii": true` in JSON Schema / `json_schema_extra={"x-pii": True}` in Pydantic. List all PII fields explicitly.

4. **Remove `cost_basis_method` from Holding**. It belongs on TaxLot only. Holdings contain `tax_lots: list[TaxLot]`.

5. **Fix Household AC2.2** — vendor mappings do NOT contain member lists. Members are at the Household level with source attribution.

6. **Fix Household AC2.3** — replace `discrepancy_flag`/`discrepancy_notes` with the `reconciliation` object pattern (sources_agree, discrepancies list, last_reconciled datetime).

7. **Add all missing enums** (at least list names and value counts). 15+ enums are missing.

8. **Add standard field requirements** — every type needs `canonical_id` (UUID), `source_system`, `source_id`. Types with audit needs get `trace_id`. Types with multi-vendor sources get `reconciliation` and `vendor_mappings`.

9. **Resolve the FastAPI question** — is M3 a library or a service? ARCH-07 says FastAPI. The dependency matrix says library. Pick one and document why.

10. **Fix directory naming** — `m3-schema-registry` (hyphen) to match project convention, with note about Python import path (`m3_schema_registry` for imports).

### Recommended Fixes (Not Blocking, 5 items)

11. Start `SCHEMA_VERSION` at `0.1.0`, not `1.0.0`.
12. Add acceptance criteria for JSON Schema validation (Draft 2020-12, $id format, description on every field).
13. Reference the DECISION-LOG's pending SME decisions as known blockers.
14. Add a task for DECISION-LOG maintenance.
15. Distinguish PII from MNPI in the spec language.

---

*LLMJ Review — M3 Canonical Schema Registry Spec*
*Project 007 FSI Interoperability Platform*
