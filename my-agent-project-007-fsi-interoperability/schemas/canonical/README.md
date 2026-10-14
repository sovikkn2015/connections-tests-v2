# Canonical Schema Registry

18 canonical FSI data types for Project 007 FSI Interoperability Platform.

## Version

`0.1.0` (pre-SME review)

## Types

| # | Type | File | Key Concerns |
|---|------|------|-------------|
| 1 | Client | client.json | PII fields (x-pii), vendor_mappings, KYC status |
| 2 | Household | household.json | CONTAINER model, 3 vendor mappings, members at top level |
| 3 | TaxLot | tax-lot.json | cost_basis_method REQUIRED, never null |
| 4 | Holding | holding.json | NO cost_basis_method (on TaxLot), tax_lots list |
| 5 | Order | order.json | 12-state lifecycle, HITL mandatory |
| 6 | Transaction | transaction.json | 19 transaction types, settlement status |
| 7 | Balance | balance.json | 16 account types, is_real_time flag |
| 8 | Performance | performance.json | TWR methodology, risk metrics |
| 9 | SecurityProfile | security-profile.json | is_restricted, mnpi_flag |
| 10 | Quote | quote.json | is_delayed REQUIRED |
| 11 | PlanSummary | plan-summary.json | Raw data NEVER to LLM |
| 12 | Goal | goal.json | Status enum, vendor goal type mapping |
| 13 | InteractionSummary | interaction-summary.json | CRM write-back, principal review |
| 14 | ComplianceCheck | compliance-check.json | OPA result, wsp_section optional |
| 15 | ComplianceAlert | compliance-alert.json | wsp_section REQUIRED, SLA deadlines |
| 16 | AuditEntry | audit-entry.json | Provenance chain, 6-year retention |
| 17 | ResearchBrief | research-brief.json | Source attribution, anti-fabrication |
| 18 | PaymentInstruction | payment-instruction.json | ISO 20022, BSA/AML fields |

## Conventions

- `$schema`: Draft 2020-12
- `$id`: `https://007.fsi/schemas/canonical/{type-slug}/v{semver}`
- Every field has a `description`
- PII fields marked with `"x-pii": true`
- Semver: MAJOR=breaking, MINOR=additive, PATCH=docs only

## Decisions

See [DECISION-LOG.md](DECISION-LOG.md) for all schema decisions.
