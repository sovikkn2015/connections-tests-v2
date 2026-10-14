# Orion Translators — Changelog

All notable changes to Orion translators are documented here.
Format: Keep a Changelog.

## [0.1.0] — 2026-04-26

### Added
- Orion Holding translator (T4): Position → canonical Holding with embedded TaxLots.
- Orion Transaction translator (T5): Transaction → canonical Transaction. `transaction_id` (UUID) and `source_id` (str) are TWO separate fields (v0.2.0 fix).
- Orion TaxLot translator (T10): tax lot → canonical TaxLot. `cost_basis_method` never null. `holding_ref` is `str`.
- Orion Household translator (T6): portfolio_management grouping container.
- ENUM_MAPPINGS for account_type, transaction_type, settlement_status, holding_period, role.
- M3 is SOT for AccountType — 457 deliberately NOT mapped in Phase 2 (first encounter → UnknownEnumValue, MINOR bump).
- `TRUST` vendor string → `trust_revocable` default with `orion_trust_label_ambiguous` reconciliation note.
- `order_ref` preserved via `OrionTransaction.customAttributes["order_ref"]` on reverse.
