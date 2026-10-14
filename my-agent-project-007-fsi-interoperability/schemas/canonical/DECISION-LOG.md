# Canonical Schema Decision Log

All schema decisions documented per Rule 14. Each entry: Date, Type, Field, Decision, Rationale, Decided By.

---

| Date | Type | Field | Decision | Rationale | Decided By |
|------|------|-------|----------|-----------|------------|
| 2026-04-17 | TaxLot | cost_basis_method | REQUIRED enum, never null | Wrong cost basis = wrong tax reporting = regulatory violation. Custodian defaults vary (Schwab=specific_lot, Fidelity=average_cost for MF). M7 translators MUST set this. | Architect + Compliance SME |
| 2026-04-17 | Holding | cost_basis_method | REMOVED from Holding | cost_basis_method belongs on TaxLot, not Holding. Holdings contain tax_lots list. | Architect |
| 2026-04-17 | Household | model_type | CONTAINER model, not unified | SF FSC=relationship, Orion=portfolio_management, Schwab=custodial. Three different concepts. Container preserves all three via vendor_mappings. | Architect + Compliance SME |
| 2026-04-17 | Household | members | Top-level field, NOT inside vendor_mappings | Members with role and source attribution at Household level. Vendor mappings contain IDs and grouping types only. | Architect |
| 2026-04-17 | Household | reconciliation | Object with sources_agree, discrepancies, last_reconciled | NOT a simple discrepancy_flag/notes. Structured for SME review workflow. | Architect |
| 2026-04-17 | AccountType | values | 16 ERISA + tax-advantaged types | Per BLOCKER-8 resolution. OPA needs account_type for per-type compliance rules. | Architect + Compliance SME |
| 2026-04-17 | Client | PII fields | 5 fields marked x-pii: email, phone, date_of_birth, ssn_last_four, tax_id | M4 uses x-pii annotation to identify fields for stripping. Not description string matching. | Architect |
| 2026-04-17 | Beneficiary | PII fields | 3 fields marked x-pii: account_number, routing_number, iban | LLMJ v2 review identified gap — M4 needs x-pii on nested sub-model PII fields too. | LLMJ Review |
| 2026-04-17 | ComplianceAlert | wsp_section | REQUIRED field | Per steering rule 19. Every OPA rule must include wsp_section for WSP-to-YAML mapping. | Architect |
| 2026-04-17 | ComplianceCheck | wsp_section | OPTIONAL field | Not all compliance checks originate from WSP-mapped rules. Deliberate difference from ComplianceAlert. | Architect |
| 2026-04-17 | Quote | is_delayed | REQUIRED bool | Compliance must disclose delayed vs real-time quotes to clients. Alpha Vantage=delayed, Bloomberg=real-time. | Architect + Compliance SME |
| 2026-04-17 | SecurityProfile | is_restricted, mnpi_flag | MNPI indicators (bool), NOT x-pii | These are entity-level flags for M2/M4 OPA rules, not PII annotations. Different filtering mechanism. | Architect |
| 2026-04-17 | All | SCHEMA_VERSION | 0.1.0 (pre-SME review) | Not 1.0.0. Pre-SME review version. Will bump per semver rules after SME validation. | Architect |
| 2026-04-17 | SourceSystem | enum purpose | Validation in M7 translators | SourceSystem enum exists for M7 translator validation during vendor data translation. source_system fields on types are string (not enum) for flexibility with new vendors. | Architect |
| 2026-04-17 | All | financial amounts | float type | Pydantic v2 handles float display/comparison fine. These are not accounting-precision arithmetic. If reconciliation tests show precision drift, migrate to Decimal. | Architect |
| 2026-04-17 | AlertStatus | value count | 6 values (not 5) | open, acknowledged, investigating, resolved, escalated, false_positive. LLMJ v2 review caught count error. | LLMJ Review |

## PENDING SME Decisions

| Type | Field | Question | Impact | Status |
|------|-------|----------|--------|--------|
| Holding | market_value | Does MarketValue include accrued interest? Differs by custodian feed. | M7 translator logic | PENDING SME |
| SecurityIdentifier | canonical_id | Canonical ID preference: CUSIP? FIGI? ISIN? All three? | Cross-referencing | PENDING SME |
| Performance | methodology | Modified Dietz vs daily valuation — which is default? | GIPS compliance | PENDING SME |
