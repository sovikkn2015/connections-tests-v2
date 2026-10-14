# M7 Schema Translators - Decision Log

All M7 decisions per Rule 14.

## Structural Decisions

| Date | Vendor | Type | Field | Decision |
|------|--------|------|-------|----------|
| 2026-04-26 | all | TaxLot | source_cost_basis_method vendor-silent | Store None; provenance in ReconciliationNote.cost_basis_source.method_origin=="vendor_default" |
| 2026-04-26 | all | namespaces | 10 + ORDER_NS reserved | Declared in shared/namespaces.py |
| 2026-04-26 | salesforce_fsc | Client | archetype | Pass-through; no M7 validator |
| 2026-04-26 | salesforce_fsc | all | FinServ custom fields | PENDING-VERIFICATION vs live SF v59.0 SOQL |
| 2026-04-26 | all | AccountType | M3 is SOT; Steering Rule 10 outdated |
| 2026-04-26 | orion/schwab | Holding/TaxLot | 457 vendor string | Not mapped Phase 2 - UnknownEnumValue |
| 2026-04-26 | schwab | all | VENDOR_API_VERSION=v1 | URL path versioning, v0.2.0 fix |
| 2026-04-26 | schwab | TaxLot | UK SpecificLot | ambiguous_mapping, PENDING SME IMPL-06 |
| 2026-04-26 | schwab | Holding/TaxLot | dollar-prefixed numerics | Vendor model strips at mode=before |
| 2026-04-26 | orion | Transaction | transaction_id vs source_id | TWO separate fields, v0.2.0 fix |
| 2026-04-26 | salesforce_fsc | Client | Person vs Business | Business/Trust -> no PII |
| 2026-04-26 | all | Household | Single vs multi reconciliation | Single=None, multi=populated |
| 2026-04-26 | all | Household | Role mismatch | Preserve BOTH records, emit discrepancy |
| 2026-04-26 | all | errors | NI-2 PII leak guard | Allow-list _SAFE_DETAIL_KEYS |
| 2026-04-26 | all | reconciliation | NI-4 | schwab_ira_label_ambiguous typo fix |

## Lossy Rationales

| Vendor | Type | Dir | Fields |
|--------|------|-----|--------|
| salesforce_fsc | Client | fwd | sf_metadata, created_by_sf, last_activity_date_sf |
| salesforce_fsc | Client | rev | CreatedBy, LastActivityDate, InternalMetadata |
| salesforce_fsc | Goal | rev | funding_pct DERIVED |
| emoney | PlanSummary | fwd | fullPlanBody, scenariosDetail, cashflowProjection (MNPI) |
| emoney | PlanSummary | rev | net_worth DERIVED |
| schwab | Holding | rev | market_value_includes_accrued DERIVED |
| orion/schwab | Household | fwd | portfolioIds, benchmark, titleCode |

## Cost Basis Defaults

| Vendor | Group | Class | Default |
|--------|-------|-------|---------|
| schwab | taxable | equity | specific_lot |
| schwab | taxable | mutual_fund | average_cost |
| schwab | taxable | etf | specific_lot |
| schwab | retirement | * | fifo |
| orion | taxable | equity | specific_lot |
| orion | taxable | mutual_fund | average_cost |
| orion | retirement | * | fifo |

## M3 Cross-Refs

- Holding.accrued_interest PENDING SME -> Schwab market_value_includes_accrued=False
- SecurityIdentifier.canonical_id PENDING SME -> M7 uses ticker string
- Performance.methodology PENDING SME -> Phase 2 out of scope
