# M3 Canonical Schema Registry — 18 FSI Data Types

Status: DEFINED (all 18 types have field-level JSON Schema definitions, pending compliance SME validation)
Version: 0.1.0 (pre-SME review)
Types: 18
$id namespace: `https://007.fsi/schemas/canonical/{type}/v0.1.0`

These JSON Schema definitions map 17 vendor data models to one canonical representation.
Every M7 translator converts vendor data TO these types. Every M11 adapter returns these types.
OPA rules (M2/M4) evaluate against these types.

## Types

| # | Type | File | Status | SME Review Needed |
|---|------|------|--------|-------------------|
| 1 | Client | client.json | DEFINED | PII classification, vendor_mappings validation |
| 2 | Holding | holding.json | DEFINED | MarketValue accrued interest (PENDING SME) |
| 3 | Order | order.json | DEFINED | Order types per custodian |
| 4 | ResearchBrief | research-brief.json | DEFINED | Output format validation |
| 5 | ComplianceCheck | compliance-check.json | DEFINED | Check types per archetype |
| 6 | AuditEntry | audit-entry.json | DEFINED | Retention per jurisdiction, provenance chain |
| 7 | Household | household.json | DEFINED | CRITICAL — container model, 3 vendor mappings |
| 8 | TaxLot | tax-lot.json | DEFINED | CRITICAL — cost_basis_method normalization |
| 9 | Transaction | transaction.json | DEFINED | Transaction type mapping per custodian |
| 10 | Balance | balance.json | DEFINED | Balance components per custodian feed |
| 11 | Performance | performance.json | DEFINED | TWR methodology (modified_dietz vs daily_valuation) |
| 12 | SecurityProfile | security-profile.json | DEFINED | Bloomberg field mapping, restricted list integration |
| 13 | Quote | quote.json | DEFINED | Real-time vs delayed disclosure |
| 14 | PlanSummary | plan-summary.json | DEFINED | eMoney/MoneyGuidePro field mapping |
| 15 | Goal | goal.json | DEFINED | SF FSC FinancialGoal picklist mapping |
| 16 | InteractionSummary | interaction-summary.json | DEFINED | CRM write-back format, principal review |
| 17 | ComplianceAlert | compliance-alert.json | DEFINED | Alert severity, SLA deadlines, routing rules |
| 18 | PaymentInstruction | payment-instruction.json | DEFINED | ISO 20022 pain.001 mapping (Phase 5) |

## Conventions

All 18 schemas follow these patterns:
- `$id`: `https://007.fsi/schemas/canonical/{type}/v0.1.0`
- `canonical_id` (uuid): primary key for every type
- `source_system` + `source_id`: vendor provenance
- `vendor_mappings`: preserves vendor-specific semantics (where applicable)
- `reconciliation`: tracks cross-vendor agreement (where applicable)
- `trace_id`: links to M10 audit trail (where applicable)
- `x-pii: true`: marks fields for M4 MNPI filtering (Client type)

## Versioning

All types use semver. Breaking changes detected in CI.
Schema decision log: `schemas/canonical/DECISION-LOG.md`

## Key Design Decisions

### Household Container Model
The canonical Household is NOT a unified model. It is a container that holds references to vendor-specific groupings. See `household.json` for the full schema.

### Cost Basis (TaxLot)
`cost_basis_method` is REQUIRED. M7 translators MUST set it. OPA validates it is never null. See DECISION-LOG.

### MNPI Filtering (Client, PlanSummary)
PII fields on Client are marked `x-pii: true`. M4 strips them by role/archetype before LLM access.
PlanSummary raw data NEVER sent to LLM — summary-level only.

### Compliance (ComplianceCheck, ComplianceAlert)
All compliance decisions are deterministic OPA/Rego. NOT LLM-generated. `wsp_section` required on alerts (steering rule 19).

### Payments (PaymentInstruction)
ISO 20022 pain.001 mapping for Phase 5 Tier 1 bank integration. BSA/AML CTR/SAR/OFAC screening fields included.
