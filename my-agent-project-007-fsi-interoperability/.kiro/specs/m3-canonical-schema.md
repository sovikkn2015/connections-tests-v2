# Spec: M3 Canonical Schema Registry

> Module: M3 — Canonical Schema Registry
> Phase: 0 (prerequisite — no dependencies)
> Owner: Schema Specialist
> Version: 0.1.0 (pre-SME review)
> Dependencies: None (pure data library, calls nothing)
> Consumers: M7 (imports types), M2/M4 (evaluates against types), M6 (routes typed data), M11 (returns typed data)
> Design Sources: 007-consolidated-design-and-plan.md Part 10, ARCH-09 (module detail + dependency matrix), ARCH-07 (tech stack), IMPL-06 Blocker 3, DECISION-LOG.md (30+ field-level decisions)
> Language: Python 3.12+ | Runtime Validation: Pydantic v2 | Schema Format: JSON Schema Draft 2020-12
> Estimated Lines: ~1,700 total (~1,200 JSON Schema + ~500 Python)

---

## Architecture Clarification: Library vs Service

ARCH-07 lists "FastAPI + JSON Schema" for M3. The ARCH-09 dependency matrix shows M3 calls nothing and is called by M7 via Python import. These are not contradictory:

- **M3 core is a LIBRARY** — Pydantic v2 models + JSON Schema files. M7 imports M3 types directly. This is the primary usage pattern.
- **FastAPI is for the optional Schema Registry API endpoint** — a thin HTTP wrapper that serves schema definitions (GET /schemas/{type}, GET /schemas/{type}/v{version}) for non-Python consumers, CI validation, and schema discovery. This is a convenience layer, not the core.

M3 does NOT import from any other module. Other modules import M3's types. This is the designed pattern per the dependency matrix — M3 is a shared data library, not a service with business logic.

---

## Known Blockers (Pending SME Decisions)

Per DECISION-LOG, these decisions are PENDING and may affect implementation:

| Field | Question | Impact | Status |
|-------|----------|--------|--------|
| Holding.market_value | Does MarketValue include accrued interest? Differs by custodian feed. | M7 translator logic, Holding schema | PENDING SME |
| SecurityIdentifier | Canonical ID: CUSIP? FIGI? ISIN? All three? Cross-reference service needed. | SecurityProfile, Holding, Quote cross-referencing | PENDING SME |
| Performance.methodology | Modified Dietz vs daily valuation — which is default? | GIPS compliance, Performance schema | PENDING SME (needs validation) |

Implementation proceeds with current field definitions. SME decisions may trigger MINOR or MAJOR version bumps per semver rules.

---

## PII vs MNPI Distinction

This spec distinguishes two regulatory categories:

- **PII (Personally Identifiable Information)**: Data that identifies a natural person — email, phone, date_of_birth, ssn_last_four, tax_id, physical address. Marked with `"x-pii": true` in JSON Schema and `json_schema_extra={"x-pii": True}` in Pydantic. M4 strips PII fields by role/archetype before LLM access.
- **MNPI (Material Non-Public Information)**: Security-level information that could affect trading decisions — `mnpi_flag` on SecurityProfile, `is_restricted` on SecurityProfile, raw plan data on PlanSummary. MNPI is handled by M4 OPA rules at the field and entity level, not by schema annotations alone.

Both are filtered by M4. PII uses the `x-pii` annotation mechanism. MNPI uses OPA policy rules that evaluate context (who is asking, what security, what archetype).

---

## Requirements

### R1: 18 Canonical FSI Data Types
The schema registry MUST define exactly 18 Pydantic v2 models representing canonical FSI data types. These types map 17 vendor data models into a single canonical representation. Each type has a corresponding JSON Schema file in `schemas/canonical/`.

**Acceptance Criteria:**
- AC1.1: Registry contains exactly 18 types: Client, Household, Holding, TaxLot, Order, Transaction, Balance, Performance, SecurityProfile, Quote, PlanSummary, Goal, InteractionSummary, ComplianceAlert, ResearchBrief, ComplianceCheck, AuditEntry, PaymentInstruction.
- AC1.2: A `CANONICAL_TYPES` dict maps type name (str) to Pydantic model class. `len(CANONICAL_TYPES) == 18`.
- AC1.3: All types are importable from `m3_schema_registry`.
- AC1.4: Every type has a corresponding `.json` file in `schemas/canonical/` with matching field definitions.

### R2: JSON Schema Draft 2020-12 (Primary Artifact)
Every canonical type MUST have a JSON Schema file as a primary artifact (not a derived export). These are the contract that M7 translators, M2/M4 OPA rules, and external consumers validate against.

**Acceptance Criteria:**
- AC2.1: Every `.json` file includes `"$schema": "https://json-schema.org/draft/2020-12/schema"`.
- AC2.2: Every `.json` file includes `"$id": "https://007.fsi/schemas/canonical/{type-slug}/v0.1.0"` where type-slug is kebab-case.
- AC2.3: Every property in every schema has a `"description"` field documenting what it includes, excludes, and its FSI semantic meaning.
- AC2.4: PII fields include `"x-pii": true` in their JSON Schema property definition.
- AC2.5: `scripts/validate-schemas.py` validates all 18 schemas pass Draft 2020-12 dialect, $id format, and description presence. Exit code 0 in CI.

### R3: Standard Fields on Every Type
Every canonical type MUST include standard provenance and identity fields.

**Acceptance Criteria:**
- AC3.1: Every type has `canonical_id` (UUID format) as its primary key (field name varies: `canonical_id`, `lot_id`, `check_id`, `order_id`, etc. — but always UUID).
- AC3.2: Every type that receives vendor data has `source_system` (string) and `source_id` (string) for vendor provenance.
- AC3.3: Types with audit needs have `trace_id` (string) linking to M10 audit trail.
- AC3.4: Types with multiple vendor sources have `vendor_mappings` (object) preserving vendor-specific semantics.
- AC3.5: Types with multiple vendor sources have `reconciliation` (object) with `sources_agree` (bool), `discrepancies` (list[str]), `last_reconciled` (datetime).

### R4: Household is a CONTAINER Model
The Household type MUST preserve vendor-specific groupings (SF FSC = relationship, Orion = portfolio_management, Schwab = custodial). It does NOT unify them.

**Acceptance Criteria:**
- AC4.1: Household has `vendor_mappings` as an object with optional keys: `salesforce_fsc`, `orion`, `schwab`. Each contains vendor-specific IDs and grouping type. Vendor mappings do NOT contain member lists.
- AC4.2: Household has `members` at the top level — a list of objects with `client_ref`, `role`, and `source` (which vendor defined this membership).
- AC4.3: Household has a `reconciliation` object with `sources_agree` (bool), `discrepancies` (list[str]), and `last_reconciled` (datetime). NOT a simple `discrepancy_flag`/`discrepancy_notes`.
- AC4.4: When vendor sources disagree on membership, discrepancies are added to `reconciliation.discrepancies` for SME review.

### R5: Cost Basis Method is REQUIRED on TaxLot
TaxLot MUST have a `cost_basis_method` field that is REQUIRED (not Optional, never null). Holdings contain `tax_lots: list[TaxLot]` — cost_basis_method is on TaxLot, NOT on Holding.

**Acceptance Criteria:**
- AC5.1: `TaxLot.cost_basis_method` is type `CostBasisMethod` (enum), not Optional. Constructing a TaxLot without it raises ValidationError.
- AC5.2: `CostBasisMethod` enum has exactly 5 values: `specific_lot`, `average_cost`, `fifo`, `lifo`, `hifo`.
- AC5.3: `TaxLot.source_cost_basis_method` (string, optional) preserves the custodian's native method name for reconciliation.
- AC5.4: `Holding` does NOT have `cost_basis_method`. Holdings have `tax_lots: list[TaxLot]` which contain cost basis.
- AC5.5: Pydantic validator on TaxLot rejects `cost_basis_method=None` with explicit error message about regulatory risk.

### R6: PII Fields Annotated with x-pii
Fields containing PII MUST be marked with `"x-pii": true` in JSON Schema and `json_schema_extra={"x-pii": True}` in Pydantic models. This is the mechanism M4 uses to identify fields for filtering. NOT description string matching.

**Acceptance Criteria:**
- AC6.1: Client PII fields marked with `x-pii`: `email`, `phone`, `date_of_birth`, `ssn_last_four`, `tax_id`.
- AC6.2: PaymentInstruction beneficiary fields (account_number, routing_number, iban) are PII-sensitive and handled by M4 policy (beneficiary is a sub-object).
- AC6.3: A `PII_FIELDS` dict maps `(type_name, field_name)` pairs for all fields with `x-pii: true`. Replaces the old `MNPI_FIELDS` concept.
- AC6.4: `model_json_schema()` output for Client includes `"x-pii": true` on the 5 PII fields.
- AC6.5: SecurityProfile has `is_restricted` (bool) and `mnpi_flag` (bool) — these are MNPI indicators, not PII annotations. They are handled by M4 OPA rules, not x-pii markers.

### R7: Enums for Controlled Vocabularies
All controlled vocabularies MUST be defined as Python `str, enum.Enum` subclasses. Free-form strings are not acceptable for fields with finite valid values.

**Acceptance Criteria:**
- AC7.1: All 22 enums defined (see Enum Registry below). Each enum's value count matches the specification.
- AC7.2: Enum values use snake_case strings (e.g., `"specific_lot"`, not `"SpecificLot"`).
- AC7.3: AccountType enum has exactly 16 values per DECISION-LOG BLOCKER-8 resolution: `taxable`, `traditional_ira`, `roth_ira`, `401k`, `403b`, `457`, `sep_ira`, `simple_ira`, `trust_revocable`, `trust_irrevocable`, `custodial_utma`, `custodial_ugma`, `erisa_pension`, `erisa_profit_sharing`, `529`, `hsa`.

### R8: Schema Versioning
All schemas use strict semver starting at `0.1.0`. Version appears in `$id` URI and in the `SCHEMA_VERSION` constant.

**Acceptance Criteria:**
- AC8.1: `SCHEMA_VERSION = "0.1.0"` (not `1.0.0` — pre-SME review).
- AC8.2: All `$id` URIs use `v0.1.0`.
- AC8.3: Breaking changes (field removed/renamed, type changed, required field added) = MAJOR bump.
- AC8.4: Additive changes (new optional field, new enum value) = MINOR bump.
- AC8.5: Documentation-only changes = PATCH bump.

### R9: No External Dependencies Beyond Pydantic
M3 has zero dependencies on other modules. It imports only stdlib + pydantic.

**Acceptance Criteria:**
- AC9.1: No imports from any other module (`m1_*`, `m2_*`, `m5_*`, `m6_*`, etc.).
- AC9.2: Only imports: `__future__`, `datetime`, `decimal`, `enum`, `typing`, `uuid`, `pydantic`.
- AC9.3: `requirements.txt` contains only `pydantic>=2.0,<3.0`.

### R10: JSON Schema Export
Each type MUST be exportable as JSON Schema for runtime consumers.

**Acceptance Criteria:**
- AC10.1: Every model's `model_json_schema()` returns valid JSON Schema.
- AC10.2: An `export_all_schemas()` function returns a dict of all 18 JSON schemas keyed by type name.
- AC10.3: Exported schemas match the hand-written `.json` files in `schemas/canonical/` (field names, types, required arrays).

### R11: DECISION-LOG Maintenance
All schema decisions MUST be documented in `schemas/canonical/DECISION-LOG.md` per Rule 14.

**Acceptance Criteria:**
- AC11.1: Every new field addition, enum change, or semantic decision has a DECISION-LOG entry.
- AC11.2: Each entry includes: Date, Type, Field, Decision, Rationale, Decided By.
- AC11.3: Pending SME decisions are marked as `PENDING SME` with clear description of what's blocked.

---

## Enum Registry (22 Enums)

| # | Enum | Values | Used By |
|---|------|--------|---------|
| 1 | `AccountType` | 16: taxable, traditional_ira, roth_ira, 401k, 403b, 457, sep_ira, simple_ira, trust_revocable, trust_irrevocable, custodial_utma, custodial_ugma, erisa_pension, erisa_profit_sharing, 529, hsa | Balance, Order, Holding, Transaction |
| 2 | `SourceSystem` | 21: salesforce_fsc, orion, schwab, schwab_sftp, fidelity, fidelity_sftp, pershing, envestnet, bloomberg, factset, alpha_vantage, iex, sec_edgar, emoney, moneyguidepro, rightcapital, wealthbox, redtail, swift_gateway, agent_generated, manual | All types (source_system field) |
| 3 | `CostBasisMethod` | 5: specific_lot, average_cost, fifo, lifo, hifo | TaxLot |
| 4 | `OrderStatus` | 12: draft, compliance_check, pending_approval, approved, submitted, confirmed, pending_settlement, settled, rejected, cancelled, settlement_failed, escalated | Order |
| 5 | `TransactionType` | 19: buy, sell, sell_short, buy_to_cover, dividend, interest, fee, management_fee, transfer_in, transfer_out, distribution, contribution, wire_in, wire_out, journal, reinvestment, return_of_capital, corporate_action, margin_interest | Transaction |
| 6 | `ComplianceCheckType` | 12: restricted_list, concentration_limit, trading_window, suitability, chinese_wall, pod_isolation, mnpi_filter, erisa_prohibited_transaction, rmd_check, bsa_aml_ctr, bsa_aml_sar, sanctions_screen | ComplianceCheck |
| 7 | `ComplianceDecision` | 5: ALLOW, DENY, WARN, REQUIRE_APPROVAL, ESCALATE | ComplianceCheck |
| 8 | `AlertType` | 15: restricted_list_violation, concentration_breach, suitability_drift, mnpi_leakage_detected, chinese_wall_breach, bsa_aml_ctr, bsa_aml_sar, sanctions_match, erisa_prohibited_transaction, trading_window_violation, rmd_missed, wash_sale_detected, principal_review_overdue, cross_border_violation, pod_isolation_breach | ComplianceAlert |
| 9 | `AlertSeverity` | 5: critical, high, medium, low, informational | ComplianceAlert |
| 10 | `AlertStatus` | 5: open, acknowledged, investigating, resolved, escalated, false_positive | ComplianceAlert |
| 11 | `PaymentType` | 7: wire_domestic, wire_international, ach_transfer, check_request, journal_transfer, standing_instruction, distribution | PaymentInstruction |
| 12 | `PaymentStatus` | 10: draft, compliance_check, pending_approval, approved, submitted, processing, completed, rejected, cancelled, failed | PaymentInstruction |
| 13 | `AssetClass` | 12: equity, fixed_income, etf, mutual_fund, option, future, commodity, crypto, alternative, money_market, preferred_stock, reit | SecurityProfile |
| 14 | `GoalType` | 11: retirement, education, home_purchase, emergency_fund, wealth_transfer, charitable_giving, debt_payoff, major_purchase, income_replacement, legacy, custom | Goal |
| 15 | `GoalStatus` | 5: on_track, at_risk, behind, achieved, abandoned | Goal |
| 16 | `PerformanceMethodology` | 3: modified_dietz, daily_valuation, irr_only | Performance |
| 17 | `PerformancePeriod` | 9: mtd, qtd, ytd, 1y, 3y, 5y, 10y, itd, custom | Performance |

Note: Some types use constrained strings rather than enums where the value set is open-ended (e.g., `client_type` validated to `{individual, entity, trust}` via field_validator, `jurisdiction` as string). These are documented per-type below.

---

## Shared Sub-Models

These sub-models are used across multiple canonical types.

### SecurityIdentifier
Cross-reference object holding multiple identifiers for the same security. PENDING SME decision on canonical ID preference.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| ticker | string | optional | — | — | Exchange ticker symbol |
| cusip | string | optional | 9-char alphanumeric | — | CUSIP identifier |
| isin | string | optional | 2-letter country + 10 alphanum | — | ISIN identifier |
| figi | string | optional | 12-char alphanumeric | — | FIGI identifier |
| sedol | string | optional | 7-char alphanumeric | — | SEDOL identifier |
| bloomberg_id | string | optional | — | — | Bloomberg ticker format (e.g., "NVDA US Equity") |

### Reconciliation
Tracks cross-vendor agreement for types with multiple vendor sources. Used by Household, Client, Goal, PlanSummary.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| sources_agree | bool | required | — | — | True if all vendor sources agree on data |
| discrepancies | list[str] | required | default=[] | — | List of disagreements between sources — flagged for SME review |
| last_reconciled | datetime | required | ISO 8601 | — | When reconciliation last ran |

### HitlApproval
Human-in-the-loop approval record. Used by Order, PaymentInstruction.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| approver_id | string | required | — | — | ID of the human approver |
| approved_at | datetime | required | ISO 8601 | — | Timestamp of approval |
| approval_token | string | required | SHA-256 hex | — | SHA-256(entity_id + approver_id + timestamp) — tamper-proof |

### PII Marker
Utility class for Pydantic `json_schema_extra`. Usage: `Field(json_schema_extra={"x-pii": True})`.

---

## Field-Level Type Definitions (All 18 Types)

### Type 1: Client
Canonical FSI client profile. PII fields marked with `x-pii: true` for M4 MNPI filtering.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for canonical client record |
| display_name | string | required | min=1, max=255 | — | Human-readable display name |
| client_type | string | required | enum: individual, entity, trust | — | Legal classification. Validated by field_validator. |
| first_name | string | optional | max=100 | — | Given name (individual only). Excludes entity names. |
| last_name | string | optional | max=100 | — | Family name (individual only). Excludes entity names. |
| email | string | optional | — | **PII** (x-pii) | Client email address. M4 strips for non-authorized roles. |
| phone | string | optional | — | **PII** (x-pii) | Client phone number. M4 strips for non-authorized roles. |
| date_of_birth | date | optional | ISO 8601 date | **PII** (x-pii) | Date of birth. M4 strips for non-authorized roles. |
| ssn_last_four | string | optional | pattern: `^[0-9]{4}$` | **PII** (x-pii) | Last four SSN digits only. Full SSN never stored. |
| tax_id | string | optional | — | **PII** (x-pii) | EIN for entities/trusts. PII — M4 strips. |
| risk_tolerance | string | optional | — | — | Suitability result: conservative, moderately_conservative, moderate, moderately_aggressive, aggressive |
| investment_objectives | list[str] | optional | default=[] | — | Objectives: growth, income, capital_preservation, speculation, balanced |
| time_horizon | string | optional | — | — | short_term (<3y), medium_term (3-10y), long_term (>10y) |
| annual_income_range | string | optional | — | — | Self-reported income bracket |
| net_worth_range | string | optional | — | — | Self-reported total net worth bracket |
| liquid_net_worth_range | string | optional | — | — | Excludes primary residence |
| tax_bracket | string | optional | — | — | Client tax bracket |
| advisor_ref | UUID | optional | — | — | Canonical Advisor ID |
| firm_id | UUID | required | — | — | Canonical Firm ID |
| household_ref | UUID | optional | — | — | Canonical Household ID |
| archetype | string | optional | — | — | Client segmentation: mass_affluent, hnw, uhnw |
| jurisdiction | string | required | — | — | Primary regulatory jurisdiction (US, US-CA, UK, EU, SG, HK) |
| accounts | list[UUID] | optional | default=[] | — | Canonical Account IDs linked to this client |
| kyc_status | string | optional | — | — | KYC verification status: pending, verified, expired, failed |
| kyc_verified_date | date | optional | — | — | Date KYC was last verified |
| pii_classification | string | optional | default="confidential" | — | Data classification: public, internal, confidential, restricted |
| vendor_mappings | ClientVendorMappings | optional | — | — | Preserves vendor-specific client identifiers (SF FSC, Orion, Schwab, Fidelity) |
| reconciliation | Reconciliation | optional | — | — | Cross-vendor agreement tracking |
| source_system | string | required | — | — | Source system that provided this client record |
| source_id | string | required | — | — | Vendor-specific client ID |
| created_at | datetime | required | ISO 8601 | — | Record creation timestamp |
| updated_at | datetime | required | ISO 8601 | — | Record last update timestamp |

Client vendor mapping sub-models: `ClientVendorSalesforceFSC` (account_id, contact_id, person_account), `ClientVendorOrion` (client_id, representative_id), `ClientVendorSchwab` (account_holder_id), `ClientVendorFidelity` (customer_id).

### Type 2: Household
CONTAINER model — holds vendor-specific groupings, NOT a unified model. SF FSC uses "relationship" grouping, Orion uses "portfolio_management", Schwab uses "custodial". All three semantics preserved via vendor_mappings.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for canonical household |
| display_name | string | required | — | — | Human-readable household display name |
| primary_source | string | required | enum: salesforce_fsc, orion, schwab, fidelity, pershing, manual | — | Primary source system for this household |
| members | list[HouseholdMember] | required | — | — | Household members with roles and source attribution. Members are at Household level, NOT inside vendor_mappings. |
| accounts | list[HouseholdAccount] | optional | default=[] | — | Accounts linked to this household |
| vendor_mappings | HouseholdVendorMappings | optional | — | — | Preserves vendor-specific grouping semantics. Contains IDs and grouping types ONLY — no member lists. |
| reconciliation | Reconciliation | optional | — | — | Cross-vendor agreement tracking: sources_agree, discrepancies list, last_reconciled |

HouseholdMember: `client_ref` (string, required), `role` (string, required — enum: primary, spouse, dependent, trustee, beneficiary, authorized_signer, power_of_attorney), `source` (string, required — which vendor defined this membership).

HouseholdAccount: `account_ref` (string, required), `source` (string, required).

HouseholdVendorMappings sub-models:
- `HouseholdVendorSFSC`: household_id (string), grouping_type (const: "relationship")
- `HouseholdVendorOrion`: household_id (string), grouping_type (const: "portfolio_management")
- `HouseholdVendorSchwab`: master_account (string), grouping_type (const: "custodial")

### Type 3: TaxLot
Individual tax lot within a holding. `cost_basis_method` is REQUIRED — wrong cost basis = wrong tax reporting = regulatory violation. Custodian defaults vary: Schwab = specific_lot, Fidelity = average_cost (mutual funds) / specific_lot (equities).

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| lot_id | UUID | required | format: uuid | — | Primary key for this tax lot |
| holding_ref | string | required | — | — | Canonical Holding ID this lot belongs to |
| security_ref | string | optional | — | — | Canonical security identifier |
| acquisition_date | date | required | ISO 8601 | — | Date the lot was acquired |
| acquisition_price | float | optional | — | — | Price per unit at acquisition |
| quantity | float | required | — | — | Number of shares/units in this lot |
| cost_basis_method | CostBasisMethod | **required** | enum, NEVER null | — | REQUIRED. Pydantic validator rejects None. Regulatory risk if missing. |
| cost_basis_amount | float | required | — | — | Total cost basis for this lot |
| holding_period | string | optional | enum: short_term, long_term, unknown | — | Tax holding period classification |
| unrealized_gain_loss | float | optional | nullable | — | Unrealized gain/loss for this lot |
| wash_sale_disallowed | float | optional | nullable | — | Disallowed loss amount if wash sale applies |
| source_custodian | string | required | — | — | Which custodian provided this data |
| source_cost_basis_method | string | optional | — | — | Custodian's native method name (for reconciliation with canonical method) |

### Type 4: Holding
Canonical position/holding. Maps from Orion Position, SF FSC FinancialHolding, custodian positions. Does NOT have cost_basis_method — that's on TaxLot. Holdings contain `tax_lots: list[TaxLot]`.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for canonical holding record |
| account_ref | string | required | — | — | Canonical Account ID |
| client_ref | string | optional | — | — | Canonical Client ID |
| security_identifier | SecurityIdentifier | optional | — | — | Cross-reference: multiple identifiers for the same security |
| security_name | string | optional | — | — | Security display name |
| security_type | string | optional | — | — | Classification: equity, fixed_income, mutual_fund, etf, option, cash, alternative, other |
| quantity | float | required | — | — | Number of shares/units held |
| market_value | float | required | — | — | Current market value. Excludes accrued interest by default (Schwab convention). PENDING SME on accrued interest. |
| market_value_includes_accrued | bool | optional | default=false | — | Explicit flag — M7 translator sets based on custodian feed |
| cost_basis | float | optional | — | — | Total cost basis for this holding position |
| unrealized_gain_loss | float | optional | — | — | Unrealized gain/loss amount |
| unrealized_gain_loss_pct | float | optional | — | — | Unrealized gain/loss as percentage |
| weight_in_account | float | optional | — | — | Percentage of account this holding represents |
| currency | string | optional | default="USD" | — | ISO 4217 currency code |
| as_of_date | date | required | ISO 8601 | — | Date this position data is valid for |
| account_type | AccountType | optional | 16-value enum | — | Account type for ERISA/tax rules. Per BLOCKER-8 resolution. |
| source_system | string | required | — | — | Source system that provided this holding data |
| source_id | string | required | — | — | Vendor-specific holding/position ID |
| tax_lots | list[TaxLot] | optional | default=[] | — | Individual tax lots for this holding. Cost basis method lives here. |

### Type 5: Order
Canonical trade order. Used by Execution Specialist state machine. 12-state lifecycle. HITL mandatory before submission.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| order_id | UUID | required | format: uuid | — | Primary key for canonical order |
| client_ref | string | required | — | — | Canonical Client ID |
| account_ref | string | required | — | — | Canonical Account ID |
| security_identifier | SecurityIdentifier | optional | — | — | Security being traded |
| side | string | required | — | — | Trade side: buy, sell, sell_short, buy_to_cover |
| order_type | string | optional | — | — | Order type: market, limit, stop, stop_limit |
| quantity | float | required | — | — | Number of shares/units to trade |
| limit_price | float | optional | — | — | Limit price for limit/stop_limit orders |
| stop_price | float | optional | — | — | Stop price for stop/stop_limit orders |
| time_in_force | string | optional | default="day" | — | Time in force: day, gtc, ioc, fok |
| status | OrderStatus | required | 12-value enum | — | Order lifecycle status per Execution Specialist state machine |
| compliance_checks | list[ComplianceCheck] | optional | default=[] | — | Compliance check results for this order |
| hitl_approval | HitlApproval | optional | — | — | HITL approval record if approved |
| submitted_at | datetime | optional | — | — | When order was submitted to execution venue |
| confirmed_at | datetime | optional | — | — | When order execution was confirmed |
| settled_at | datetime | optional | — | — | When order settlement completed |
| settlement_date_expected | date | optional | — | — | Expected settlement date (T+1 from trade date) |
| execution_venue | string | optional | — | — | Custodian API, FIX broker, OMS |
| fill_price | float | optional | — | — | Actual execution price |
| fill_quantity | float | optional | — | — | Actual filled quantity |
| commission | float | optional | — | — | Commission charged |
| account_type | AccountType | optional | 16-value enum | — | Account type for ERISA/tax rules |
| tax_impact | TaxImpact | optional | — | — | Estimated tax impact shown at HITL gate |
| trace_id | string | optional | — | — | Links to M10 audit trail |
| created_at | datetime | required | — | — | Order creation timestamp |

TaxImpact sub-model: `estimated_gain_loss` (float), `holding_period` (string), `tax_rate_estimate` (float, optional), `wash_sale_risk` (bool, default=false).

### Type 6: Transaction
Canonical transaction record. 19 transaction types normalized by M7 translator. Trade history, dividends, fees, transfers.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| transaction_id | UUID | required | format: uuid | — | Primary key for canonical transaction |
| account_ref | UUID | required | — | — | Canonical Account ID |
| client_ref | UUID | optional | — | — | Canonical Client ID |
| order_ref | UUID | optional | — | — | Canonical Order ID if trade originated from 007 |
| transaction_type | TransactionType | required | 19-value enum | — | Transaction classification normalized by M7 translator |
| security_identifier | SecurityIdentifier | optional | — | — | Null for cash transactions (fees, wires) |
| security_name | string | optional | — | — | Security display name |
| quantity | float | optional | — | — | Number of shares/units. Null for cash transactions. |
| price | float | optional | — | — | Price per unit at execution |
| amount | float | required | — | — | Total transaction amount |
| commission | float | optional | — | — | Commission charged |
| fees | float | optional | — | — | SEC fees, exchange fees, etc. |
| net_amount | float | optional | — | — | Amount after commissions and fees |
| trade_date | date | required | ISO 8601 | — | Date the trade was executed |
| settlement_date | date | optional | — | — | Settlement date (T+1 for equities since May 2024) |
| settlement_status | string | optional | enum: pending, settled, failed | — | Settlement lifecycle status |
| currency | string | optional | default="USD", pattern: `^[A-Z]{3}$` | — | ISO 4217 currency code |
| description | string | optional | — | — | Custodian-provided transaction description |
| tax_lot_ref | string | optional | — | — | Tax lot ID if this transaction created/closed a lot |
| cost_basis_impact | CostBasisImpact | optional | — | — | Tax impact: realized_gain_loss, holding_period, wash_sale_disallowed |
| account_type | AccountType | optional | 16-value enum | — | Account type for ERISA/tax rules |
| source_system | string | required | — | — | Source system that provided this transaction |
| source_id | string | required | — | — | Custodian transaction ID |
| source_transaction_type | string | optional | — | — | Custodian's native transaction type code (for reconciliation) |
| trace_id | string | optional | — | — | Links to M10 audit trail |
| created_at | datetime | required | — | — | Transaction record creation timestamp |

CostBasisImpact sub-model: `realized_gain_loss` (float, optional), `holding_period` (string, optional), `wash_sale_disallowed` (float, optional).

### Type 7: Balance
Canonical account balance. Maps from custodian balance feeds (Schwab, Fidelity, Pershing). `is_real_time` distinguishes API vs daily file.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| balance_id | UUID | required | format: uuid | — | Primary key for canonical balance snapshot |
| account_ref | UUID | required | — | — | Canonical Account ID |
| client_ref | UUID | optional | — | — | Canonical Client ID |
| total_value | float | required | — | — | Total account value (long_market_value + cash_balance - short_market_value) |
| cash_balance | float | optional | — | — | Available cash (settled) |
| cash_unsettled | float | optional | — | — | Cash from unsettled trades |
| money_market_balance | float | optional | — | — | Sweep/money market balance |
| long_market_value | float | optional | — | — | Market value of long positions |
| short_market_value | float | optional | — | — | Market value of short positions (absolute value) |
| margin_balance | float | optional | — | — | Margin debit balance |
| margin_equity | float | optional | — | — | Equity in margin account |
| buying_power | float | optional | — | — | Available buying power |
| accrued_interest | float | optional | — | — | Accrued interest on fixed income holdings |
| pending_activity | float | optional | — | — | Pending deposits/withdrawals |
| account_type | AccountType | optional | 16-value enum | — | Account type for ERISA/tax rules (ARCH-06 Gap 5) |
| currency | string | optional | default="USD", pattern: `^[A-Z]{3}$` | — | ISO 4217 currency code |
| as_of_date | date | required | ISO 8601 | — | Date this balance snapshot is valid for |
| as_of_time | datetime | optional | — | — | Intraday timestamp if real-time balance |
| is_real_time | bool | optional | default=false | — | True if from real-time API, false if from daily file. Compliance must know data freshness. |
| source_system | string | required | — | — | Source system that provided this balance data |
| source_id | string | required | — | — | Vendor-specific balance record ID |
| source_balance_components | dict | optional | — | — | Custodian's native balance breakdown (for reconciliation) |

### Type 8: Performance
Canonical portfolio performance metrics. TWR methodology must be explicit for GIPS compliance. Risk metrics required for suitability analysis.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| performance_id | UUID | required | format: uuid | — | Primary key for this performance record |
| account_ref | UUID | required | — | — | Canonical Account ID |
| client_ref | UUID | optional | — | — | Canonical Client ID |
| household_ref | UUID | optional | — | — | Canonical Household ID for household-level performance |
| period | PerformancePeriod | required | 9-value enum | — | Performance measurement period |
| twr_return | float | required | — | — | Time-weighted return as decimal (e.g., 0.085 = 8.5%) |
| irr_return | float | optional | — | — | Internal rate of return as decimal |
| gross_return | float | optional | — | — | Return before fees |
| net_return | float | optional | — | — | Return after fees |
| benchmark_return | float | optional | — | — | Benchmark return for same period |
| benchmark_name | string | optional | — | — | Benchmark index name |
| benchmark_ticker | string | optional | — | — | Benchmark ticker |
| alpha | float | optional | — | — | Excess return over benchmark |
| sharpe_ratio | float | optional | — | — | Risk-adjusted return metric. Required for suitability analysis. |
| standard_deviation | float | optional | — | — | Portfolio volatility |
| max_drawdown | float | optional | — | — | Maximum peak-to-trough decline |
| start_date | date | required | — | — | Period start date |
| end_date | date | required | — | — | Period end date |
| start_value | float | optional | — | — | Portfolio value at period start |
| end_value | float | optional | — | — | Portfolio value at period end |
| net_flows | float | optional | — | — | Net cash flows during period |
| income_earned | float | optional | — | — | Dividends + interest earned during period |
| realized_gains | float | optional | — | — | Realized capital gains during period |
| fees_paid | float | optional | — | — | Total fees paid during period |
| methodology | PerformanceMethodology | required | 3-value enum | — | TWR calculation methodology. PENDING SME validation. |
| is_gips_compliant | bool | optional | default=false | — | True if follows GIPS standards |
| source_system | string | required | — | — | Source system that provided this performance data |
| source_id | string | required | — | — | Vendor-specific performance record ID |
| as_of_date | date | required | — | — | Date this performance data is valid for |

### Type 9: SecurityProfile
Canonical security/instrument reference data. `is_restricted` and `mnpi_flag` are critical for M2 restricted list checks and M4 MNPI filtering.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for this security profile |
| ticker | string | required | — | — | Exchange ticker symbol |
| security_name | string | required | — | — | Full legal or display name |
| asset_class | AssetClass | required | 12-value enum | — | Broad asset classification |
| cusip | string | optional | pattern: `^[A-Z0-9]{9}$` | — | CUSIP identifier |
| isin | string | optional | pattern: `^[A-Z]{2}[A-Z0-9]{10}$` | — | ISIN identifier |
| figi | string | optional | pattern: `^[A-Z0-9]{12}$` | — | FIGI identifier |
| sedol | string | optional | pattern: `^[A-Z0-9]{7}$` | — | SEDOL identifier |
| bloomberg_id | string | optional | — | — | Bloomberg ticker format |
| exchange | string | optional | — | — | Primary exchange MIC code |
| sector | string | optional | — | — | GICS sector |
| industry | string | optional | — | — | GICS industry |
| market_cap | float | optional | ge=0 | — | Market capitalization |
| pe_ratio | float | optional | — | — | Price-to-earnings ratio |
| eps | float | optional | — | — | Earnings per share |
| dividend_yield | float | optional | ge=0 | — | Annual yield as decimal |
| beta | float | optional | — | — | Beta relative to market |
| fifty_two_week_high | float | optional | — | — | 52-week high price |
| fifty_two_week_low | float | optional | — | — | 52-week low price |
| avg_volume_30d | int | optional | ge=0 | — | 30-day average trading volume |
| shares_outstanding | int | optional | ge=0 | — | Total shares outstanding |
| description | string | optional | — | — | Business description |
| country | string | optional | pattern: `^[A-Z]{2}$` | — | ISO-3166-1 alpha-2 domicile |
| currency | string | required | pattern: `^[A-Z]{3}$` | — | ISO 4217 currency code |
| is_restricted | bool | optional | default=false | **MNPI indicator** | True if on firm restricted list. M2 OPA checks this. |
| restricted_since | date | optional | — | — | Date added to restricted list |
| mnpi_flag | bool | optional | default=false | **MNPI indicator** | True if MNPI exists for this security. M4 filters before LLM. |
| last_updated | datetime | required | — | — | When this profile was last updated |
| source_system | string | required | — | — | Source system that provided this security data |
| source_id | string | required | — | — | Vendor-specific security ID |

### Type 10: Quote
Canonical price quote. `is_delayed` is REQUIRED for compliance disclosure — Alpha Vantage = delayed, Bloomberg = real-time.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for this quote |
| security_ref | UUID | required | — | — | Canonical SecurityProfile ID |
| ticker | string | required | — | — | Ticker for quick reference |
| price | float | required | — | — | Last traded or latest quoted price |
| bid | float | optional | — | — | Current bid price |
| ask | float | optional | — | — | Current ask price |
| bid_size | int | optional | — | — | Bid size in lots |
| ask_size | int | optional | — | — | Ask size in lots |
| volume | int | optional | ge=0 | — | Session trading volume |
| open | float | optional | — | — | Session open price |
| high | float | optional | — | — | Session high price |
| low | float | optional | — | — | Session low price |
| previous_close | float | optional | — | — | Previous session close price |
| change | float | optional | — | — | Absolute change from previous close |
| change_pct | float | optional | — | — | Percentage change |
| vwap | float | optional | — | — | Volume-weighted average price |
| as_of_timestamp | datetime | required | — | — | Timestamp of this quote |
| is_delayed | bool | **required** | — | — | True if delayed. Compliance must disclose to clients. REQUIRED. |
| delay_minutes | int | optional | ge=0 | — | Minutes delayed (null if real-time) |
| market_status | string | optional | — | — | Market status: pre_market, open, post_market, closed |
| currency | string | required | pattern: `^[A-Z]{3}$` | — | ISO 4217 currency code |
| source_system | string | required | — | — | Source system |
| source_id | string | required | — | — | Vendor-specific quote ID |

### Type 11: PlanSummary
Canonical financial plan summary. Raw plan data NEVER sent to LLM — M4 filters to summary-level only. Full plan data stays in planning system.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for this plan summary |
| client_ref | UUID | required | — | — | Canonical Client ID |
| household_ref | UUID | optional | — | — | Canonical Household ID |
| plan_name | string | required | — | — | Plan display name |
| plan_type | string | optional | — | — | Plan type: comprehensive, retirement_only, education_only, estate, tax, insurance |
| probability_of_success | float | required | ge=0, le=100 | — | Overall plan success probability (0-100) |
| as_of_date | date | required | — | — | Date this plan summary is valid for |
| total_assets | float | optional | ge=0 | — | Total assets in plan |
| total_liabilities | float | optional | ge=0 | — | Total liabilities in plan |
| net_worth | float | optional | — | — | Net worth (assets - liabilities) |
| retirement_goal_amount | float | optional | ge=0 | — | Retirement goal target amount |
| retirement_target_date | date | optional | — | — | Retirement target date |
| retirement_income_gap | float | optional | — | — | Annual income shortfall in retirement (negative = surplus) |
| monte_carlo_success_pct | float | optional | ge=0, le=100 | — | Monte Carlo success percentage |
| monte_carlo_iterations | int | optional | — | — | Number of Monte Carlo iterations |
| annual_savings_rate | float | optional | ge=0 | — | As decimal (0.15 = 15%) |
| annual_spending | float | optional | ge=0 | — | Annual spending amount |
| social_security_estimate | float | optional | ge=0 | — | Estimated annual SS benefit |
| pension_income | float | optional | ge=0 | — | Annual pension income |
| goals | list[UUID] | optional | default=[] | — | Canonical Goal IDs linked to this plan |
| assumptions | PlanAssumptions | optional | — | — | Plan assumptions (inflation_rate, return_assumption, life_expectancy, retirement_age, tax_rate_assumption) |
| recommendations | list[PlanRecommendation] | optional | — | — | Plan recommendations (summary level only — raw data never to LLM) |
| vendor_mappings | PlanVendorMappings | optional | — | — | Preserves vendor-specific plan identifiers (eMoney, MoneyGuidePro, RightCapital) |
| source_system | string | required | — | — | Source system: emoney, moneyguidepro, rightcapital, manual |
| source_id | string | required | — | — | Vendor-specific plan ID |
| created_at | datetime | required | — | — | Plan creation timestamp |
| updated_at | datetime | required | — | — | Plan last update timestamp |

PlanAssumptions sub-model: `inflation_rate` (float), `return_assumption` (float), `life_expectancy` (int, ge=0), `retirement_age` (int, optional), `tax_rate_assumption` (float, optional).
PlanRecommendation sub-model: `category` (string), `description` (string), `priority` (string: high, medium, low).
PlanVendorMappings: `PlanVendorEMoney` (plan_id, scenario_id), `PlanVendorMoneyGuidePro` (plan_id, scenario_name), `PlanVendorRightCapital` (plan_id).

### Type 12: Goal
Canonical financial goal. Maps from SF FSC FinancialGoal, eMoney, MoneyGuidePro. Goal type picklists differ across vendors — M7 normalizes to canonical enum.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for this goal |
| client_ref | UUID | required | — | — | Canonical Client ID |
| household_ref | UUID | optional | — | — | Canonical Household ID if goal is household-level |
| plan_ref | UUID | optional | — | — | Canonical PlanSummary ID this goal belongs to |
| goal_type | GoalType | required | 11-value enum | — | Goal classification |
| goal_name | string | required | — | — | Display name (e.g., "Retire at 65") |
| target_amount | float | required | ge=0 | — | Target dollar amount for the goal |
| current_amount | float | optional | ge=0 | — | Current funded amount toward the goal |
| funding_pct | float | optional | ge=0, le=100 | — | Percentage funded |
| target_date | date | required | — | — | Target completion date |
| priority | string | required | — | — | Goal priority: critical, high, medium, low |
| status | GoalStatus | required | 5-value enum | — | Current goal status: on_track, at_risk, behind, achieved, abandoned |
| monthly_contribution | float | optional | ge=0 | — | Monthly savings allocated to this goal |
| linked_accounts | list[UUID] | optional | default=[] | — | Canonical Account IDs funding this goal |
| assumptions | GoalAssumptions | optional | — | — | Goal planning assumptions (inflation_rate, return_rate, tax_rate) |
| vendor_mappings | GoalVendorMappings | optional | — | — | Preserves vendor-specific goal semantics (SF FSC, eMoney, MoneyGuidePro) |
| as_of_date | date | required | — | — | Date this goal data is valid for |
| source_system | string | required | — | — | Source system |
| source_id | string | required | — | — | Vendor-specific goal ID |
| created_at | datetime | required | — | — | Goal creation timestamp |
| updated_at | datetime | required | — | — | Goal last update timestamp |

GoalAssumptions sub-model: `inflation_rate` (float), `return_rate` (float), `tax_rate` (float, optional).
GoalVendorMappings: `GoalVendorSFSC` (financial_goal_id, goal_type_picklist), `GoalVendorEMoney` (goal_id, goal_category), `GoalVendorMoneyGuidePro` (goal_id, goal_type).

### Type 13: InteractionSummary
Canonical meeting/interaction summary. Client Service Specialist output. Write-back to CRM. Principal review required for BD (FINRA 2210).

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for this interaction summary |
| client_ref | UUID | required | — | — | Canonical Client ID |
| household_ref | UUID | optional | — | — | Canonical Household ID |
| advisor_ref | UUID | required | — | — | Canonical Advisor ID (from M1 AID) |
| interaction_type | string | required | — | — | Type: meeting, phone_call, email, chat, video_call, in_person |
| interaction_date | date | required | alias="date" | — | Date of the interaction |
| start_time | datetime | optional | — | — | Interaction start time |
| end_time | datetime | optional | — | — | Interaction end time |
| duration_minutes | int | optional | ge=0 | — | Duration in minutes |
| summary | string | required | — | — | Agent-generated summary (MNPI-filtered before storage) |
| topics_discussed | list[str] | optional | default=[] | — | Topics discussed |
| action_items | list[ActionItem] | optional | default=[] | — | Action items from the interaction |
| attendees | list[Attendee] | optional | default=[] | — | People who attended |
| sentiment | string | optional | — | — | Client sentiment: positive, neutral, concerned, negative |
| next_meeting_date | date | optional | — | — | Scheduled next meeting date |
| crm_write_back | CrmWriteBack | optional | — | — | Status of write-back to CRM systems (SF FSC, Wealthbox, Redtail) |
| compliance_review | ComplianceReview | optional | — | — | Principal review status if BD (FINRA 2210) |
| channel | string | optional | — | — | Channel: slack, teams, whatsapp, web, email, phone, in_person |
| trace_id | string | required | — | — | Links to M10 audit trail |
| source_system | string | required | — | — | Source system |
| source_id | string | optional | — | — | Vendor-specific interaction ID |
| created_at | datetime | required | — | — | Record creation timestamp |
| updated_at | datetime | required | — | — | Record last update timestamp |

ActionItem sub-model: `description` (string), `assigned_to` (string), `due_date` (date, optional), `status` (string: pending, in_progress, completed, cancelled).
Attendee sub-model: `name` (string), `role` (string: client, spouse, advisor, associate, specialist, attorney, cpa, other), `canonical_ref` (UUID, optional).
CrmWriteBack: `CrmWriteBackEntry` per vendor (record_id, written_at, status: pending/written/failed). Vendors: salesforce_fsc, wealthbox, redtail.
ComplianceReview: `required` (bool), `review_id` (string, optional), `status` (string: not_required, pending, approved, rejected).

### Type 14: ComplianceCheck
Result of a deterministic OPA compliance check. NOT LLM-generated. Used by Order and PaymentInstruction.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| check_id | UUID | required | format: uuid | — | Primary key for this compliance check result |
| check_type | ComplianceCheckType | required | 12-value enum | — | Type of compliance check performed |
| decision | ComplianceDecision | required | 5-value enum | — | Compliance decision: ALLOW, DENY, WARN, REQUIRE_APPROVAL, ESCALATE |
| reason | string | required | — | — | Human-readable reason for the decision |
| rule_applied | string | required | — | — | OPA rule path (e.g., authority/restricted_list.rego:check_restricted_list) |
| policy_bundle_version | string | optional | — | — | OPA bundle version for audit trail |
| wsp_section | string | optional | — | — | WSP section this rule maps to (ARCH-06 Gap 3, steering rule 19) |
| input_context | ComplianceCheckInputContext | optional | — | — | What was checked (security_id, client_id, action, archetype, account_type) |
| details | dict | optional | — | — | Additional context (e.g., concentration percentage) |
| evaluated_at | datetime | required | — | — | When the check was evaluated |
| trace_id | string | required | — | — | Links to M10 audit trail |

### Type 15: ComplianceAlert
Proactive compliance alert generated by OPA rules (M2/M4). NOT LLM-generated. `wsp_section` is REQUIRED per steering rule 19.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| alert_id | UUID | required | format: uuid | — | Primary key for this compliance alert |
| alert_type | AlertType | required | 15-value enum | — | Classification of the compliance alert |
| severity | AlertSeverity | required | 5-value enum | — | Alert severity. Critical = immediate action required. BSA/AML CTR/SAR always critical. |
| status | AlertStatus | required | 6-value enum | — | Current alert lifecycle status |
| title | string | optional | — | — | Human-readable alert title |
| description | string | optional | — | — | Detailed description of what triggered the alert |
| triggered_by_rule | string | required | — | — | OPA rule path that triggered this alert |
| policy_bundle_version | string | optional | — | — | OPA bundle version for reproducibility |
| wsp_section | string | **required** | — | — | Written Supervisory Procedures section reference. REQUIRED per steering rule 19. |
| client_ref | UUID | optional | — | — | Canonical Client ID if client-specific |
| account_ref | UUID | optional | — | — | Canonical Account ID if account-specific |
| security_ref | string | optional | — | — | Security identifier if security-specific |
| advisor_ref | UUID | optional | — | — | Advisor whose action triggered the alert |
| firm_id | string | required | — | — | Firm context for multi-tenant routing |
| archetype | string | optional | — | — | Firm archetype (tier3_bd, tier4_ria, etc.) |
| jurisdiction | string | optional | — | — | Regulatory jurisdiction (US, UK, EU, SG, HK) |
| assigned_to | string | optional | — | — | Compliance officer or principal assigned to review |
| escalation_chain | list[EscalationEntry] | optional | default=[] | — | Escalation history |
| resolution | AlertResolution | optional | — | — | Resolution details if resolved |
| sla_deadline | datetime | optional | — | — | Deadline for acknowledgment/resolution. BSA/AML SAR = 30 days. Principal review = 4 hours. |
| related_alerts | list[UUID] | optional | default=[] | — | Related alert IDs for pattern detection |
| evidence | AlertEvidence | optional | — | — | Supporting evidence (input_hash, threshold_value, actual_value, details) |
| trace_id | string | required | — | — | Links to M10 audit trail |
| created_at | datetime | required | — | — | Alert creation timestamp |
| updated_at | datetime | required | — | — | Alert last update timestamp |

EscalationEntry sub-model: `escalated_to` (string), `escalated_at` (datetime), `reason` (string).
AlertResolution sub-model: `resolved_by` (string), `resolved_at` (datetime), `resolution_type` (string: action_taken, false_positive, risk_accepted, referred_to_regulator), `resolution_notes` (string).
AlertEvidence sub-model: `input_hash` (string, SHA-256), `threshold_value` (float, optional), `actual_value` (float, optional), `details` (string, optional).

### Type 16: AuditEntry
Immutable audit trail entry. Written to M10 3-tier storage (Langfuse + S3 Object Lock WORM + CRM). 6-year retention minimum (SEC 17a-4).

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| canonical_id | UUID | required | format: uuid | — | Primary key for this audit entry |
| trace_id | string | required | — | — | Distributed trace ID linking all entries for one request across all modules |
| timestamp | datetime | required | — | — | When this audit entry was created |
| actor_id | string | required | — | — | AID hash of the actor (agent, advisor, system) |
| action | string | required | — | — | What was done (e.g., portfolio_rebalance_proposed) |
| module | string | required | — | — | Module that generated this entry: m1-m13 |
| target_type | string | optional | — | — | Entity type acted upon |
| target_id | string | optional | — | — | Canonical ID of the entity acted upon |
| decision | string | required | — | — | Decision outcome: allow, deny, warn, escalate, error |
| reason | string | optional | — | — | Reason for the decision |
| input_hash | string | required | pattern: `^[a-f0-9]{64}$` | — | SHA-256 of input payload for reproducibility |
| output_hash | string | required | pattern: `^[a-f0-9]{64}$` | — | SHA-256 of output payload for reproducibility |
| policy_bundle_version | string | optional | — | — | OPA bundle version used |
| rule_applied | string | optional | — | — | Rego rule path evaluated |
| wsp_section | string | optional | — | — | WSP section reference (steering rule 19) |
| data_sources_used | list[str] | optional | default=[] | — | Data sources consulted |
| latency_ms | int | required | ge=0 | — | Operation latency in milliseconds |
| archetype | string | optional | — | — | Client archetype classification |
| role | string | optional | — | — | Actor role (advisor, compliance_officer, agent) |
| firm_id | string | required | — | — | Firm context for multi-tenant |
| jurisdiction | string | optional | — | — | Regulatory jurisdiction |
| provenance_chain | list[ProvenanceStage] | optional | — | — | Liability provenance chain (ARCH-06 Gap 2). Per-stage SHA-256 hash. |
| worm_record_id | string | required | — | — | S3 Object Lock key for WORM copy |
| sha256_integrity | string | required | pattern: `^[a-f0-9]{64}$` | — | SHA-256 of entire entry for tamper detection |
| langfuse_trace_url | string | optional | — | — | Langfuse trace URL for LLM observability |
| crm_record_id | string | optional | — | — | SF Record ID if written to CRM |
| retention_years | int | optional | default=6 | — | Minimum retention period. 6 years default (SEC 17a-4). Jurisdiction may require more. |

ProvenanceStage sub-model: `stage` (string), `module` (string), `hash` (string, SHA-256), `timestamp` (datetime).

### Type 17: ResearchBrief
Structured output from Research Specialist (LangGraph pipeline). Source-attributed. Anti-fabrication scored.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| brief_id | UUID | required | format: uuid | — | Primary key for this research brief |
| security_identifier | SecurityIdentifier | optional | — | — | Security being researched |
| analyst_id | string | required | — | — | Analyst or agent ID that produced this brief |
| rating | string | required | — | — | Rating: strong_buy, buy, hold, sell, strong_sell |
| target_price | float | optional | — | — | Analyst target price |
| current_price | float | optional | — | — | Current market price at time of brief |
| summary | string | required | — | — | Executive summary (2-3 paragraphs) |
| thesis | string | required | — | — | Investment thesis |
| catalysts | list[str] | optional | default=[] | — | Potential catalysts |
| risks | list[str] | optional | default=[] | — | Key risks |
| valuation | Valuation | optional | — | — | Valuation analysis (DCF, comps, Monte Carlo) |
| sources | list[ResearchSource] | required | — | — | Sources used in the research. Source attribution required. |
| pipeline_run_id | string | required | — | — | LangGraph pipeline execution ID |
| hitl_gates_passed | list[str] | optional | default=[] | — | HITL gates passed during pipeline |
| anti_fabrication_score | float | required | ge=0, le=1 | — | Anti-fabrication confidence score (0-1) |
| created_at | datetime | required | — | — | Brief creation timestamp |
| trace_id | string | required | — | — | Links to M10 audit trail |

Valuation sub-model: `dcf_fair_value` (float, optional), `comps_implied_value` (float, optional), `monte_carlo_p5` (float, optional), `monte_carlo_median` (float, optional), `monte_carlo_p95` (float, optional).
ResearchSource sub-model: `source_type` (string: sec_filing, market_data, news, earnings_transcript, analyst_consensus, crm_data), `description` (string), `url` (string, optional), `source_date` (date, optional).

### Type 18: PaymentInstruction
Canonical payment/wire instruction. Maps to ISO 20022 pain.001 (Phase 5). HITL mandatory. BSA/AML fields required for regulatory compliance.

| Field | Type | Req/Opt | Constraints | PII/MNPI | Description |
|-------|------|---------|-------------|----------|-------------|
| instruction_id | UUID | required | format: uuid | — | Primary key for this payment instruction |
| client_ref | UUID | required | — | — | Canonical Client ID |
| account_ref | UUID | required | — | — | Source account canonical ID |
| payment_type | PaymentType | required | 7-value enum | — | Payment classification |
| amount | float | required | ge=0 | — | Payment amount |
| currency | string | required | pattern: `^[A-Z]{3}$` | — | ISO 4217 currency code |
| beneficiary | Beneficiary | required | — | — | Beneficiary details (see sub-model) |
| purpose | string | optional | — | — | Payment purpose/memo |
| reference | string | optional | — | — | Client or firm reference number |
| value_date | date | optional | — | — | Requested value/settlement date |
| status | PaymentStatus | required | 10-value enum | — | Payment lifecycle status. HITL mandatory before submission. |
| compliance_checks | list[ComplianceCheck] | optional | default=[] | — | BSA/AML, sanctions, OFAC screening results |
| bsa_aml | BsaAml | optional | — | — | BSA/AML specific fields (CTR, SAR, sanctions, OFAC) |
| hitl_approval | HitlApproval | optional | — | — | HITL approval record |
| iso20022_mapping | Iso20022Mapping | optional | — | — | ISO 20022 pain.001 message mapping (Phase 5) |
| trace_id | string | required | — | — | Links to M10 audit trail |
| source_system | string | required | — | — | Source system: schwab, fidelity, pershing, swift_gateway, manual |
| source_id | string | optional | — | — | Vendor-specific payment ID |
| created_at | datetime | required | — | — | Payment creation timestamp |
| updated_at | datetime | required | — | — | Payment last update timestamp |

Beneficiary sub-model: `name` (string), `account_number` (string — masked in logs), `routing_number` (string, optional — ABA domestic), `swift_bic` (string, optional — pattern: SWIFT/BIC), `iban` (string, optional), `bank_name` (string, optional), `bank_address` (string, optional), `intermediary_bank` (string, optional).

BsaAml sub-model (regulatory requirement, not optional feature):
- `ctr_required` (bool) — True if amount >= $10,000 (CTR threshold)
- `ctr_filed` (bool, optional) — True if CTR has been filed
- `sar_flagged` (bool) — True if structuring or suspicious pattern detected
- `sanctions_screened` (bool) — True if sanctions screening completed
- `sanctions_result` (string, optional) — clear, potential_match, confirmed_match
- `ofac_screened` (bool) — True if OFAC screening completed
- `ofac_result` (string, optional) — clear, potential_match, confirmed_match

Iso20022Mapping sub-model (Phase 5): `message_id` (string — pain.001 MsgId), `payment_info_id` (string — pain.001 PmtInfId), `end_to_end_id` (string — pain.001 EndToEndId), `charge_bearer` (string — DEBT, CRED, SHAR, SLEV).

---


## Design

### Directory Structure

```
src/m3-schema-registry/              # Hyphenated directory name (project convention)
  m3_schema_registry/                # Python package (underscored for importable package name)
    __init__.py                      # Exports: CANONICAL_TYPES, PII_FIELDS, SCHEMA_VERSION, export_all_schemas
    types.py                         # All 18 Pydantic models + 22 enums + sub-models (~1,000 lines)
  pyproject.toml                     # Package metadata, pydantic dependency
  requirements.txt                   # pydantic>=2.0,<3.0

schemas/canonical/                   # JSON Schema files (PRIMARY artifacts, not derived)
  client.json
  household.json
  tax-lot.json
  holding.json
  order.json
  transaction.json
  balance.json
  performance.json
  security-profile.json
  quote.json
  plan-summary.json
  goal.json
  interaction-summary.json
  compliance-check.json
  compliance-alert.json
  audit-entry.json
  research-brief.json
  payment-instruction.json
  DECISION-LOG.md                    # All schema decisions (Rule 14)
  README.md                          # Schema registry documentation

scripts/
  validate-schemas.py                # CI script: validates Draft 2020-12, $id format, descriptions

tests/unit/
  test_m3_schema_registry.py         # Unit tests for Pydantic models, enums, exports

tests/schema-reconciliation/
  test_schema_json_match.py          # Validates Pydantic model_json_schema() matches .json files
```

### Directory Naming Convention

The project uses **hyphenated** directory names (`m3-schema-registry`) for filesystem paths. The Python package inside uses **underscored** names (`m3_schema_registry`) because Python imports require valid identifiers. This is standard Python packaging convention.

- Filesystem path: `src/m3-schema-registry/m3_schema_registry/`
- Python import: `from m3_schema_registry import Client, Household, TaxLot`
- Or: `from m3_schema_registry.types import Client`

### API Surface

```python
# Constants
SCHEMA_VERSION: str = "0.1.0"                          # Pre-SME review, not 1.0.0
CANONICAL_TYPES: dict[str, type[BaseModel]]            # 18 entries, keyed by type name
PII_FIELDS: dict[tuple[str, str], str]                 # (type_name, field_name) -> description

# Functions
def export_all_schemas() -> dict[str, dict]:           # type_name -> JSON Schema dict
def get_schema(type_name: str) -> dict:                # Single type JSON Schema

# Enums (17 primary)
AccountType, SourceSystem, CostBasisMethod, OrderStatus, TransactionType,
ComplianceCheckType, ComplianceDecision, AlertType, AlertSeverity, AlertStatus,
PaymentType, PaymentStatus, AssetClass, GoalType, GoalStatus,
PerformanceMethodology, PerformancePeriod

# Shared Sub-Models
SecurityIdentifier, Reconciliation, PII, HitlApproval

# Models (18)
Client, Household, TaxLot, Holding, Order, Transaction, Balance, Performance,
SecurityProfile, Quote, PlanSummary, Goal, InteractionSummary, ComplianceCheck,
ComplianceAlert, AuditEntry, ResearchBrief, PaymentInstruction

# Vendor Mapping Sub-Models
ClientVendorMappings, ClientVendorSalesforceFSC, ClientVendorOrion, ClientVendorSchwab, ClientVendorFidelity
HouseholdVendorMappings, HouseholdVendorSFSC, HouseholdVendorOrion, HouseholdVendorSchwab
PlanVendorMappings, PlanVendorEMoney, PlanVendorMoneyGuidePro, PlanVendorRightCapital
GoalVendorMappings, GoalVendorSFSC, GoalVendorEMoney, GoalVendorMoneyGuidePro
CrmWriteBack, CrmWriteBackEntry

# Type-Specific Sub-Models
HouseholdMember, HouseholdAccount, TaxImpact, CostBasisImpact,
ComplianceCheckInputContext, EscalationEntry, AlertResolution, AlertEvidence,
ProvenanceStage, PlanAssumptions, PlanRecommendation, GoalAssumptions,
ActionItem, Attendee, ComplianceReview, Beneficiary, BsaAml, Iso20022Mapping,
ResearchSource, Valuation
```

### PII Annotation Mechanism

PII fields use Pydantic's `json_schema_extra` to inject `"x-pii": true` into the JSON Schema output:

```python
class PII:
    MARKER: dict[str, bool] = {"x-pii": True}

# Usage on Client model:
email: Optional[str] = Field(
    default=None,
    json_schema_extra=PII.MARKER,
    description="Client email. PII — M4 strips for non-authorized roles."
)
```

This produces JSON Schema output:
```json
{
  "email": {
    "type": ["string", "null"],
    "description": "Client email. PII — M4 strips for non-authorized roles.",
    "x-pii": true
  }
}
```

M4 OPA rules check for `"x-pii": true` in the schema to identify fields to strip. This is NOT description string matching.

### Security Constraints

- No credentials in any file.
- PII fields are annotated but never filtered here (M4's job).
- MNPI indicators (`is_restricted`, `mnpi_flag`) are boolean flags — M4 OPA rules evaluate them.
- No network calls. No file I/O beyond import.
- `PII_FIELDS` dict is a convenience lookup — the authoritative source is `json_schema_extra` on each field.

### Module Boundary

- M3 imports NOTHING from other modules. Zero cross-module imports.
- Other modules import M3's types via Python import. This is the designed pattern per ARCH-09 dependency matrix.
- M3 is a shared data library. It is NOT an exception to the "no cross-module imports" rule — the rule says modules don't import FROM other modules' internals. M3 is explicitly designed to be imported BY M7, and its types are the canonical contract.

### Optional Schema Registry API (FastAPI)

ARCH-07 lists FastAPI for M3. This refers to an optional HTTP endpoint for schema discovery:

```
GET  /schemas/                          -> list of 18 type names
GET  /schemas/{type}                    -> JSON Schema for type
GET  /schemas/{type}/v{version}         -> Versioned JSON Schema
GET  /schemas/{type}/pydantic           -> Pydantic model_json_schema() output
```

This is a convenience layer for non-Python consumers and CI tooling. The core M3 library does not require FastAPI. FastAPI is an optional dependency for the registry API only. Implementation of this API is a separate task from the core library.

---

## Tasks

### Task 1: Create JSON Schema files for all 18 types
Write 18 `.json` files in `schemas/canonical/` as primary artifacts. Each file must include `$schema`, `$id`, `title`, `description`, `type`, `required` array, and `properties` with field-level descriptions. PII fields include `"x-pii": true`.

**Files:** `schemas/canonical/{type}.json` × 18
**Tests:** `scripts/validate-schemas.py` validates all 18 schemas
**Acceptance Criteria:** AC2.1, AC2.2, AC2.3, AC2.4, AC2.5

### Task 2: Create shared enums (17 primary enums)
Write all 17 primary enums in `m3_schema_registry/types.py`. Each enum is `str, enum.Enum` with snake_case values. AccountType has 16 values per BLOCKER-8 resolution.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify enum value counts and specific values
**Acceptance Criteria:** AC7.1, AC7.2, AC7.3, AC5.2

### Task 3: Create shared sub-models (SecurityIdentifier, Reconciliation, PII, HitlApproval)
Write shared sub-models used across multiple types. `PII.MARKER` provides the `json_schema_extra` dict.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify Reconciliation fields, PII.MARKER dict, HitlApproval construction
**Acceptance Criteria:** AC3.5, AC6.3

### Task 4: Create Client model with PII annotations and vendor mappings
Write Client + ClientVendorMappings + vendor sub-models. 5 PII fields use `json_schema_extra=PII.MARKER`. Includes `canonical_id`, `source_system`, `source_id`, `vendor_mappings`, `reconciliation`.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify PII fields in `model_json_schema()` output, vendor_mappings structure, required fields
**Acceptance Criteria:** AC3.1, AC3.2, AC3.4, AC6.1, AC6.4

### Task 5: Create Household container model
Write Household + HouseholdMember + HouseholdAccount + HouseholdVendorMappings + 3 vendor sub-models. Members at Household level (NOT inside vendor_mappings). Reconciliation object (NOT discrepancy_flag).

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify members at top level, vendor_mappings has no member lists, reconciliation has sources_agree/discrepancies/last_reconciled
**Acceptance Criteria:** AC4.1, AC4.2, AC4.3, AC4.4

### Task 6: Create TaxLot model with REQUIRED cost_basis_method
Write TaxLot + CostBasisMethod enum. `cost_basis_method` is REQUIRED (not Optional). Pydantic validator rejects None with regulatory risk message. Includes `source_cost_basis_method` for reconciliation.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify ValidationError on missing cost_basis_method, ValidationError on None, 5 enum values, source_cost_basis_method present
**Acceptance Criteria:** AC5.1, AC5.2, AC5.3, AC5.5

### Task 7: Create Holding model (NO cost_basis_method, HAS tax_lots)
Write Holding model. Does NOT have `cost_basis_method` field. Has `tax_lots: list[TaxLot]`. Includes `account_type`, `as_of_date`, `currency`, standard fields.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify Holding has no `cost_basis_method` attribute, has `tax_lots` field, `account_type` uses AccountType enum
**Acceptance Criteria:** AC5.4

### Task 8: Create Order model with 12-state lifecycle
Write Order + OrderStatus enum + TaxImpact sub-model. 12 OrderStatus values matching Execution Specialist state machine. Includes `compliance_checks`, `hitl_approval`, settlement fields.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify 12 OrderStatus values, required fields, compliance_checks list type
**Acceptance Criteria:** AC3.1, AC3.3

### Task 9: Create Transaction, Balance, Performance models
Write Transaction (19 TransactionType values, CostBasisImpact, settlement_status), Balance (is_real_time, account_type), Performance (PerformanceMethodology, PerformancePeriod, risk metrics).

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify 19 TransactionType values, Balance.is_real_time default, Performance.methodology required
**Acceptance Criteria:** AC3.1, AC3.2, AC7.1

### Task 10: Create SecurityProfile, Quote models
Write SecurityProfile (is_restricted, mnpi_flag, AssetClass enum), Quote (is_delayed REQUIRED). SecurityProfile MNPI indicators are boolean flags, not x-pii annotations.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify is_restricted/mnpi_flag defaults, is_delayed required on Quote, AssetClass 12 values
**Acceptance Criteria:** AC6.5, AC7.1

### Task 11: Create PlanSummary, Goal models with vendor mappings
Write PlanSummary (PlanVendorMappings, PlanAssumptions, PlanRecommendation), Goal (GoalType, GoalStatus, GoalVendorMappings, GoalAssumptions). Both have vendor_mappings for container pattern.

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify GoalType 11 values, GoalStatus 5 values, vendor_mappings structure
**Acceptance Criteria:** AC3.4, AC7.1

### Task 12: Create InteractionSummary, ComplianceCheck, ComplianceAlert models
Write InteractionSummary (CrmWriteBack, ComplianceReview, ActionItem, Attendee), ComplianceCheck (ComplianceCheckType, ComplianceDecision), ComplianceAlert (AlertType, AlertSeverity, AlertStatus, wsp_section REQUIRED, evidence).

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify wsp_section required on ComplianceAlert, 15 AlertType values, 12 ComplianceCheckType values, 5 ComplianceDecision values
**Acceptance Criteria:** AC3.3, AC7.1

### Task 13: Create AuditEntry, ResearchBrief, PaymentInstruction models
Write AuditEntry (ProvenanceStage, retention_years, SHA-256 patterns), ResearchBrief (Valuation, ResearchSource, anti_fabrication_score), PaymentInstruction (Beneficiary, BsaAml, Iso20022Mapping, PaymentType, PaymentStatus).

**Files:** `src/m3-schema-registry/m3_schema_registry/types.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify SHA-256 patterns on AuditEntry, BsaAml fields on PaymentInstruction (ctr_required, sar_flagged, sanctions_screened, ofac_screened), PaymentType 7 values, PaymentStatus 10 values
**Acceptance Criteria:** AC3.1, AC3.3, AC7.1

### Task 14: Create registry exports (__init__.py, CANONICAL_TYPES, PII_FIELDS, export_all_schemas)
Wire up `__init__.py` with all public exports. `CANONICAL_TYPES` dict with 18 entries. `PII_FIELDS` dict mapping (type_name, field_name) for all x-pii fields. `export_all_schemas()` function. `SCHEMA_VERSION = "0.1.0"`.

**Files:** `src/m3-schema-registry/m3_schema_registry/__init__.py`
**Tests:** `tests/unit/test_m3_schema_registry.py` — verify len(CANONICAL_TYPES)==18, all types importable, PII_FIELDS contains Client PII fields, export_all_schemas returns 18 schemas, SCHEMA_VERSION=="0.1.0"
**Acceptance Criteria:** AC1.1, AC1.2, AC1.3, AC6.3, AC8.1, AC9.1, AC9.2, AC10.1, AC10.2

### Task 15: Create package files (pyproject.toml, requirements.txt)
Write `pyproject.toml` with package metadata and `requirements.txt` with `pydantic>=2.0,<3.0`.

**Files:** `src/m3-schema-registry/pyproject.toml`, `src/m3-schema-registry/requirements.txt`
**Tests:** Verify `requirements.txt` contains only pydantic
**Acceptance Criteria:** AC9.3

### Task 16: Create schema validation script
Write `scripts/validate-schemas.py` that validates all 18 JSON Schema files: JSON parse, Draft 2020-12 `$schema`, `$id` format (`https://007.fsi/schemas/canonical/{type}/v{semver}`), `description` on every property, `x-pii` on Client PII fields. Exit code 0/1 for CI.

**Files:** `scripts/validate-schemas.py`
**Tests:** Run script against `schemas/canonical/` — exit code 0
**Acceptance Criteria:** AC2.5

### Task 17: Create schema-to-model reconciliation tests
Write tests that verify Pydantic `model_json_schema()` output matches the hand-written `.json` files in `schemas/canonical/` — field names, types, required arrays must align.

**Files:** `tests/schema-reconciliation/test_schema_json_match.py`
**Tests:** All 18 types pass reconciliation
**Acceptance Criteria:** AC1.4, AC10.3

### Task 18: Create DECISION-LOG.md and README.md
Write `schemas/canonical/DECISION-LOG.md` with all existing decisions from archived log. Write `schemas/canonical/README.md` documenting all 18 types, conventions, versioning, and key design decisions.

**Files:** `schemas/canonical/DECISION-LOG.md`, `schemas/canonical/README.md`
**Tests:** Files exist and contain required sections
**Acceptance Criteria:** AC11.1, AC11.2, AC11.3

### Task 19: Module isolation verification
Write a test that scans `m3_schema_registry/` source files and verifies zero imports from any other module (m1_*, m2_*, m4_*, m5_*, m6_*, etc.). Only stdlib + pydantic imports allowed.

**Files:** `tests/unit/test_m3_schema_registry.py` (additional test case)
**Tests:** Import scan passes
**Acceptance Criteria:** AC9.1, AC9.2

---

## Review Fix Traceability

This section maps each LLMJ review fix to the spec sections that address it.

### Required Fixes (10)

| # | Fix | Addressed In |
|---|-----|-------------|
| 1 | Field-level definitions for all 18 types | Field-Level Type Definitions section — every field listed with name, type, req/opt, constraints, PII/MNPI |
| 2 | JSON Schema file specifications | R2 (AC2.1-AC2.5), Task 1, Task 16, Design → Directory Structure |
| 3 | Fix x-pii annotation mechanism | R6 (AC6.1-AC6.5), Design → PII Annotation Mechanism, PII.MARKER pattern |
| 4 | Remove cost_basis_method from Holding | R5 (AC5.4), Type 4 Holding (no cost_basis_method, has tax_lots), Task 7 |
| 5 | Fix Household AC2.2 — vendor mappings no member lists | R4 (AC4.1, AC4.2), Type 2 Household (members at top level), Task 5 |
| 6 | Fix Household AC2.3 — reconciliation object | R4 (AC4.3), Type 2 Household (Reconciliation sub-model), Task 5 |
| 7 | Add all missing enums | Enum Registry (17 primary enums with value counts), R7 (AC7.1-AC7.3), Tasks 2-13 |
| 8 | Add standard field requirements | R3 (AC3.1-AC3.5), every type definition includes canonical_id, source_system, source_id |
| 9 | Resolve FastAPI question | Architecture Clarification section — M3 is a LIBRARY, FastAPI is optional registry API |
| 10 | Fix directory naming | Design → Directory Structure, Design → Directory Naming Convention |

### Recommended Fixes (5)

| # | Fix | Addressed In |
|---|-----|-------------|
| 11 | Start SCHEMA_VERSION at 0.1.0 | R8 (AC8.1, AC8.2) — SCHEMA_VERSION = "0.1.0" |
| 12 | Add acceptance criteria for JSON Schema validation | R2 (AC2.1-AC2.5) — Draft 2020-12, $id format, description on every field |
| 13 | Reference pending SME decisions | Known Blockers section — 3 pending SME decisions listed |
| 14 | Add task for DECISION-LOG maintenance | R11 (AC11.1-AC11.3), Task 18 |
| 15 | Distinguish PII from MNPI | PII vs MNPI Distinction section, R6 uses "PII" not "MNPI" for x-pii fields, AC6.5 distinguishes MNPI indicators |

---

*Spec: M3 Canonical Schema Registry — Project 007 FSI Interoperability Platform*
*Rewritten to address all 10 required fixes and 5 recommended fixes from LLMJ review (4.8/10 → target 8.0+/10)*