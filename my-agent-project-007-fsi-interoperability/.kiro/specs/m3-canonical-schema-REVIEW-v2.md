# LLMJ Re-Review (v2): M3 Canonical Schema Registry Spec

> Reviewer: Schema Specialist (LLMJ)
> Date: 2026-04-17
> Spec Under Review: `.kiro/specs/m3-canonical-schema.md` (rewritten)
> Previous Review: `.kiro/specs/m3-canonical-schema-REVIEW.md` — Score: 4.8/10, CONDITIONAL GO
> Source-of-Truth Documents:
>   - `007-consolidated-design-and-plan.md` (Part 10)
>   - `ARCH-09-complete-module-map.md` (M3 row + dependency matrix)
>   - `IMPL-06-blocker-resolution-plan.md` (Blocker 3)
>   - `DECISION-LOG.md` (archived, 30+ decisions)
>   - Archived `schemas/canonical/household.json`, `tax-lot.json`
>   - Archived `src/m3-schema-registry/types.py` (1,037 lines, 78 classes)
> Verdict: **GO**

---

## PREVIOUS REVIEW: 10 REQUIRED FIXES — VERIFICATION

Before scoring, I verify each of the 10 required fixes from the 4.8/10 review was actually addressed.

| # | Required Fix | Status | Evidence |
|---|-------------|--------|----------|
| 1 | Add field-level definitions for all 18 types | **FIXED** | "Field-Level Type Definitions" section covers all 18 types with field name, type, req/opt, constraints, PII/MNPI, and description columns. ~600 lines of field tables. Every field documented. |
| 2 | Add JSON Schema file specifications | **FIXED** | R2 (AC2.1-AC2.5) specifies `$schema`, `$id`, field-level `description`, `x-pii` markers. Directory structure lists all 18 `.json` files. Task 1 creates them. Task 16 creates `validate-schemas.py`. |
| 3 | Fix `x-pii` annotation mechanism | **FIXED** | R6 specifies `json_schema_extra={"x-pii": True}` via `PII.MARKER` class. Lists all 5 Client PII fields (AC6.1). Includes code example showing Pydantic to JSON Schema output. AC6.5 correctly distinguishes MNPI indicators from PII. |
| 4 | Remove `cost_basis_method` from Holding | **FIXED** | R5 AC5.4: "Holding does NOT have cost_basis_method." Type 4 Holding table has no `cost_basis_method` field. Has `tax_lots: list[TaxLot]`. Task 7 explicitly tests this. |
| 5 | Fix Household vendor mappings (no member lists) | **FIXED** | R4 AC4.1: "Vendor mappings do NOT contain member lists." AC4.2: "members at the top level." Type 2 Household table shows members at Household level. HouseholdVendorMappings sub-models contain only IDs and grouping types. |
| 6 | Fix Household reconciliation object | **FIXED** | R4 AC4.3: "reconciliation object with sources_agree (bool), discrepancies (list[str]), and last_reconciled (datetime). NOT a simple discrepancy_flag/discrepancy_notes." Shared Reconciliation sub-model defined. |
| 7 | Add all missing enums | **FIXED** | Enum Registry lists 17 primary enums with value counts and specific values. All 15+ enums from the previous review's missing list are present: SourceSystem (21), TransactionType (19), ComplianceCheckType (12), ComplianceDecision (5), AlertType (15), AlertSeverity (5), AlertStatus (6), PaymentType (7), PaymentStatus (10), AssetClass (12), GoalType (11), GoalStatus (5), PerformanceMethodology (3), PerformancePeriod (9). |
| 8 | Add standard field requirements | **FIXED** | R3 (AC3.1-AC3.5) specifies `canonical_id` (UUID), `source_system`, `source_id`, `trace_id`, `vendor_mappings`, `reconciliation`. Every type definition includes these fields where applicable. |
| 9 | Resolve FastAPI question | **FIXED** | "Architecture Clarification" section at top of spec: M3 core is a library, FastAPI is optional registry API. Dependency matrix cited. No ambiguity. |
| 10 | Fix directory naming | **FIXED** | "Directory Naming Convention" section: filesystem = `m3-schema-registry` (hyphen), Python package = `m3_schema_registry` (underscore). Standard Python packaging convention documented. |

**All 10 required fixes addressed.** Additionally, all 5 recommended fixes were addressed:
- Fix 11: `SCHEMA_VERSION = "0.1.0"` (AC8.1)
- Fix 12: JSON Schema validation criteria (AC2.1-AC2.5)
- Fix 13: Pending SME decisions listed in "Known Blockers" section
- Fix 14: DECISION-LOG maintenance task (R11, Task 18)
- Fix 15: PII vs MNPI distinction section at top of spec

---

## DIMENSION 1: COMPLETENESS — Score: 9/10 (was 4/10)

### What Improved

This is the most dramatic improvement. The spec went from a 20-line skeleton to a 1,099-line contract with:

- **All 18 types fully specified** with field-level tables (name, type, req/opt, constraints, PII/MNPI, description). This is the single biggest fix — an implementer can now build every model from the spec alone without reverse-engineering design docs.
- **17 enums with explicit values** — AccountType (16), SourceSystem (21), CostBasisMethod (5), OrderStatus (12), TransactionType (19), ComplianceCheckType (12), ComplianceDecision (5), AlertType (15), AlertSeverity (5/6), PaymentType (7), PaymentStatus (10), AssetClass (12), GoalType (11), GoalStatus (5), PerformanceMethodology (3), PerformancePeriod (9).
- **20+ sub-models defined** — SecurityIdentifier, Reconciliation, HitlApproval, PII, all vendor mapping sub-models (Client x4, Household x3, Plan x3, Goal x3), CrmWriteBack, ComplianceReview, ActionItem, Attendee, TaxImpact, CostBasisImpact, PlanAssumptions, PlanRecommendation, GoalAssumptions, Beneficiary, BsaAml, Iso20022Mapping, EscalationEntry, AlertResolution, AlertEvidence, ProvenanceStage, Valuation, ResearchSource, ComplianceCheckInputContext.
- **JSON Schema files specified** as primary artifacts with directory listing, validation script, and reconciliation tests.
- **Standard fields documented** per type (canonical_id, source_system, source_id, trace_id, vendor_mappings, reconciliation).
- **19 tasks** with clear file targets, test references, and AC traceability.
- **Review Fix Traceability** section maps every fix to spec sections — excellent practice.

### What Still Needs Work

**Minor issue: Enum count inconsistency.** The Enum Registry header says "22 Enums" but the table lists 17. AC7.1 says "All 22 enums defined." The API Surface section says "Enums (17 primary)." The traceability section says "17 primary enums." The number 22 appears to be a stale count that includes constrained string validators (e.g., `client_type`, `settlement_status`, `holding_period`) which are not formal enums. The spec should pick one number and be consistent. The actual enum count in the table is 17. This is cosmetic but could confuse an implementer checking AC7.1.

**Minor issue: AlertStatus value count.** The Enum Registry row says "5" values but lists 6 (open, acknowledged, investigating, resolved, escalated, false_positive). The ComplianceAlert field definition says "6-value enum." The archived implementation also has 6. The Enum Registry row label should say "6" not "5."

**Minor issue: `Decimal` vs `float`.** AC9.2 lists `decimal` as an allowed import, but all financial amount fields use `float`. The previous review flagged this as G19. The spec doesn't explicitly address the decision to use `float` over `Decimal` for financial amounts. In practice, Pydantic v2 handles `float` fine for this use case (amounts are display/comparison, not accounting-precision arithmetic), and the archived implementation uses `float`. But a one-line rationale would prevent future questions.

**Deduction: -1** for the enum count inconsistency (22 vs 17 — an implementer checking AC7.1 would be confused) and the AlertStatus count error.

---

## DIMENSION 2: ACCURACY — Score: 8/10 (was 6/10)

### What Improved

- **Household container model is now correct.** Members at top level with source attribution. Vendor mappings contain IDs and grouping types only. Reconciliation uses the proper object pattern. Matches archived `household.json` exactly.
- **TaxLot cost_basis_method correctly placed.** On TaxLot only, not Holding. `source_cost_basis_method` included for reconciliation. Matches archived `tax-lot.json` exactly.
- **PII annotation mechanism is correct.** `json_schema_extra={"x-pii": True}` via `PII.MARKER`. Code example shows the Pydantic to JSON Schema output. All 5 Client PII fields listed. Matches archived `types.py`.
- **AccountType enum values match DECISION-LOG BLOCKER-8 resolution.** 16 values explicitly listed in AC7.3. Correct convention (taxable, traditional_ira, etc.).
- **PII vs MNPI correctly distinguished.** Separate section at top of spec. `x-pii` for PII fields. `is_restricted`/`mnpi_flag` as MNPI indicators handled by M4 OPA rules (AC6.5).
- **Field names match archived implementation.** Spot-checked Client, TaxLot, Holding, Household, Order, ComplianceCheck against archived `types.py` — field names, types, and constraints align.

### What Still Needs Work

**Minor issue: `source_system` type inconsistency across types.** Client defines `source_system: string` (free-form). The spec also defines a `SourceSystem` enum with 21 values. But no type definition uses `SourceSystem` as the field type — they all use `string`. The enum exists in the registry but isn't referenced by any field. This is actually correct for flexibility (new vendors shouldn't require enum changes), but the spec should note why `SourceSystem` is an enum that isn't used as a field type. Is it for validation in M7 translators? For documentation? The purpose is unclear.

**Minor issue: Some field types differ between spec and archived code.** The spec defines `Holding.account_ref` as `string`, but `Transaction.account_ref` is `UUID`. This inconsistency (UUID vs string for the same semantic concept) exists in the archived code too, so the spec is accurately reflecting reality — but it's a design smell that should be noted for future cleanup.

**Minor issue: `ComplianceCheck.wsp_section` is optional in the spec** (and in the archived code), but steering rule 19 says "every OPA rule must include wsp_section annotation." The ComplianceAlert type correctly makes `wsp_section` required. ComplianceCheck having it optional is defensible (not all checks originate from WSP-mapped rules), but the spec should note this deliberate difference.

**Deduction: -2** for the SourceSystem enum purpose ambiguity and the ref-type inconsistency (UUID vs string for cross-references). Neither is blocking, but both will generate questions during implementation.

---

## DIMENSION 3: SECURITY — Score: 8/10 (was 5/10)

### What Improved

- **PII fields comprehensively listed.** Client: email, phone, date_of_birth, ssn_last_four, tax_id (AC6.1). All 5 marked with `x-pii: true`. Previous review noted only 3 were identified.
- **PaymentInstruction BSA/AML fields fully specified.** BsaAml sub-model includes: `ctr_required`, `ctr_filed`, `sar_flagged`, `sanctions_screened`, `sanctions_result`, `ofac_screened`, `ofac_result`. Previous review flagged these as missing (G9). Now complete.
- **SecurityProfile MNPI fields specified.** `is_restricted` and `mnpi_flag` with correct defaults (false) and clear descriptions. AC6.5 explicitly distinguishes these from PII annotations.
- **Data classification present.** Client has `pii_classification` field (public, internal, confidential, restricted). Previous review flagged this as missing.
- **Beneficiary fields identified as PII-sensitive.** AC6.2 notes beneficiary account_number, routing_number, iban are handled by M4 policy.
- **PII.MARKER mechanism is correct and testable.** AC6.4 verifies `model_json_schema()` output includes `x-pii: true`.

### What Still Needs Work

**Minor issue: Beneficiary PII fields not marked with `x-pii`.** AC6.2 says beneficiary fields are "PII-sensitive and handled by M4 policy" but doesn't use `x-pii` markers on them. The Beneficiary sub-model field table doesn't show any PII/MNPI annotations. If M4 uses `x-pii` to identify fields to strip (which is the stated mechanism), then `account_number`, `routing_number`, and `iban` on Beneficiary should also have `x-pii: true`. The spec says M4 handles them "by policy" which implies a different mechanism than the annotation-based approach used for Client PII. This is a gap — either mark them with `x-pii` or explicitly document why they use a different filtering mechanism.

**Minor issue: No mention of field-level encryption.** The spec correctly marks PII for filtering but doesn't address whether PII fields should be encrypted at rest (beyond the general WORM/S3 Object Lock for audit). This is arguably M10/infrastructure concern, not M3, but a note would be helpful.

**Deduction: -2** for the Beneficiary PII annotation gap. This is a real filtering gap — if M4 scans for `x-pii: true` and Beneficiary fields don't have it, they won't be stripped.

---

## DIMENSION 4: TESTABILITY — Score: 8/10 (was 6/10)

### What Improved

- **Acceptance criteria are specific and deterministic.** AC5.1: "Constructing a TaxLot without [cost_basis_method] raises ValidationError." AC5.5: "Pydantic validator on TaxLot rejects cost_basis_method=None with explicit error message." AC7.3: Lists all 16 AccountType values. AC2.2: Specifies exact `$id` format. These are all directly testable.
- **JSON Schema validation specified.** AC2.5: `scripts/validate-schemas.py` validates Draft 2020-12, $id format, description presence. Exit code 0 in CI.
- **Schema-to-model reconciliation tests specified.** Task 17: `tests/schema-reconciliation/test_schema_json_match.py` verifies Pydantic `model_json_schema()` matches hand-written `.json` files.
- **Module isolation test specified.** Task 19: Scans source files for zero cross-module imports.
- **PII annotation testable.** AC6.4: `model_json_schema()` output for Client includes `x-pii: true` on 5 PII fields.
- **19 tasks with explicit AC references.** Every task maps to specific acceptance criteria.

### What Still Needs Work

**Minor issue: No negative test cases for enums.** The spec tests that enums have the right values (AC7.1) but doesn't specify testing that invalid enum values are rejected. Pydantic v2 handles this by default, but an explicit AC like "Constructing a Transaction with transaction_type='invalid' raises ValidationError" would strengthen the test suite.

**Minor issue: No round-trip serialization test specified.** The spec tests JSON Schema export (AC10.1-AC10.3) and schema-to-model matching (Task 17), but doesn't specify a test that constructs a model instance, serializes to JSON, deserializes back, and verifies equality. This is important for M7 translator integration.

**Deduction: -2** for missing round-trip serialization tests and negative enum validation tests. These are standard Pydantic testing patterns that should be specified.

---

## DIMENSION 5: DESIGN ALIGNMENT — Score: 9/10 (was 4/10)

### What Improved

- **FastAPI question resolved.** Architecture Clarification section clearly states: M3 core is a library, FastAPI is optional registry API. Dependency matrix cited. No ambiguity.
- **Directory structure matches project convention.** `src/m3-schema-registry/m3_schema_registry/` with explanation of hyphen vs underscore convention.
- **File structure is complete.** `types.py`, `__init__.py`, `pyproject.toml`, `requirements.txt`, 18 JSON Schema files, DECISION-LOG.md, README.md, validate-schemas.py, unit tests, reconciliation tests.
- **Module boundary correctly stated.** "M3 imports NOTHING from other modules. Other modules import M3's types." No longer calls it an "exception" to the rule.
- **SCHEMA_VERSION = "0.1.0"** — correct pre-1.0 semver.
- **Line estimate alignment.** Spec estimates ~1,700 total (~1,200 JSON Schema + ~500 Python). ARCH-09 says ~1,700. Match.
- **Tech stack alignment.** Python 3.12+, Pydantic v2, JSON Schema Draft 2020-12. Matches ARCH-07 and ARCH-09.

### What Still Needs Work

**Minor issue: `scripts/validate-schemas.py` is outside the M3 directory boundaries.** The spec places it in `scripts/` at project root. The Schema Specialist's directory boundaries are `src/m3-schema-registry/`, `src/m7-schema-translators/`, `schemas/canonical/`, `schemas/translators/`. Strictly, `scripts/` is outside the boundary. This is a pragmatic choice (CI scripts belong at project root), but the spec should acknowledge the boundary exception or place the script inside `src/m3-schema-registry/scripts/`.

**Deduction: -1** for the scripts directory boundary question. Minor but worth noting.

---

## DIMENSION 6: GAPS — Score: 8/10 (was 3/10)

### Critical Gaps from v1 Review — All Resolved

| v1 Gap | Status |
|--------|--------|
| G1: No field-level definitions | **RESOLVED** — all 18 types fully specified |
| G2: No JSON Schema files | **RESOLVED** — R2, Task 1, Task 16 |
| G3: x-pii mechanism wrong | **RESOLVED** — R6, PII.MARKER pattern |
| G4: reconciliation object missing | **RESOLVED** — R3 AC3.5, shared Reconciliation sub-model |
| G5: vendor_mappings only on Household | **RESOLVED** — Client, PlanSummary, Goal all have vendor_mappings |
| G6: Standard fields missing | **RESOLVED** — R3 AC3.1-AC3.5 |
| G7: 15+ enums missing | **RESOLVED** — 17 enums in registry |
| G8: AccountType values ambiguous | **RESOLVED** — AC7.3 lists all 16 values |
| G9: BSA/AML fields missing | **RESOLVED** — BsaAml sub-model on PaymentInstruction |
| G10: cost_basis_method on Holding | **RESOLVED** — removed, on TaxLot only |

### Remaining Gaps (Non-Critical)

| # | Gap | Severity | Impact |
|---|-----|----------|--------|
| G1 | Enum count inconsistency (22 in AC7.1 vs 17 in table) | Low | Implementer confusion on acceptance criteria |
| G2 | AlertStatus says "5" but lists 6 values | Low | Wrong value count in enum registry |
| G3 | Beneficiary PII fields not marked with x-pii | Medium | M4 may not strip beneficiary account numbers |
| G4 | SourceSystem enum defined but never used as field type | Low | Purpose unclear — documentation or validation? |
| G5 | `float` vs `Decimal` for financial amounts not justified | Low | Won't block implementation but will generate questions |
| G6 | No round-trip serialization test specified | Low | M7 integration testing gap |
| G7 | `scripts/` directory outside Schema Specialist boundary | Low | Pragmatic but technically out of scope |
| G8 | Cross-reference type inconsistency (UUID vs string for `*_ref` fields) | Low | Design smell, not blocking |

**Deduction: -2** for G3 (Beneficiary PII gap is a real security concern) and the accumulated minor gaps.

---

## SCORECARD

| Dimension | v1 Score | v2 Score | Weight | Weighted |
|-----------|----------|----------|--------|----------|
| 1. COMPLETENESS | 4/10 | **9/10** | 25% | 2.25 |
| 2. ACCURACY | 6/10 | **8/10** | 20% | 1.60 |
| 3. SECURITY | 5/10 | **8/10** | 20% | 1.60 |
| 4. TESTABILITY | 6/10 | **8/10** | 15% | 1.20 |
| 5. DESIGN ALIGNMENT | 4/10 | **9/10** | 10% | 0.90 |
| 6. GAPS | 3/10 | **8/10** | 10% | 0.80 |
| **TOTAL** | **4.80** | | | **8.35/10** |

---

## VERDICT: GO

The spec went from a skeleton (4.8/10) to a comprehensive, implementable contract (8.35/10). Every one of the 10 required fixes was addressed. Every one of the 5 recommended fixes was addressed. The spec now contains:

- 1,099 lines (up from ~150)
- All 18 types with field-level definitions
- 17 enums with explicit values
- 20+ sub-models
- 18 JSON Schema files specified as primary artifacts
- PII annotation mechanism correctly specified
- Household container model correctly specified
- TaxLot cost_basis_method correctly placed and constrained
- BSA/AML fields on PaymentInstruction
- FastAPI question resolved
- Directory naming resolved
- 19 implementation tasks with AC traceability
- Review fix traceability section

This is a spec an implementer can build from without reverse-engineering design docs.

### Items to Watch During Implementation

1. **Fix the enum count inconsistency.** Change AC7.1 from "22 enums" to "17 enums" (or whatever the correct count is after deciding whether constrained string validators count). Fix AlertStatus from "5" to "6" in the Enum Registry.

2. **Decide on Beneficiary PII marking.** Either add `x-pii: true` to Beneficiary.account_number, Beneficiary.routing_number, and Beneficiary.iban, or document why M4 uses a different mechanism for nested sub-model PII. This is a real security gap if M4 relies solely on `x-pii` scanning.

3. **Add round-trip serialization tests** during implementation. Construct, serialize, deserialize, assert equality for all 18 types. M7 translators depend on this.

4. **Clarify SourceSystem enum purpose.** If it's for M7 translator validation, say so. If it's documentation-only, note that. Currently it's an orphan enum.

5. **Watch the `float` precision** on financial amounts during M7 translator testing. If reconciliation tests show precision drift (e.g., $10,000.005 vs $10,000.01), consider migrating to `Decimal` for amount fields. The spec allows `decimal` in imports (AC9.2) so the door is open.

6. **`scripts/validate-schemas.py` placement.** During implementation, confirm this is acceptable at project root or move to `src/m3-schema-registry/scripts/`.

7. **Cross-reference type consistency.** During implementation, decide whether `*_ref` fields should all be UUID or all be string. Currently mixed. Not blocking but worth standardizing.

None of these items are blockers. All are addressable during implementation without spec revision.

---

*LLMJ Re-Review (v2) — M3 Canonical Schema Registry Spec*
*Project 007 FSI Interoperability Platform*
*Previous: 4.8/10 CONDITIONAL GO | Current: 8.35/10 GO*
