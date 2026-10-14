# Schwab Translators — Changelog

All notable changes to Schwab translators are documented here.
Format: Keep a Changelog.

## [0.1.0] — 2026-04-26

### Added
- Schwab Holding translator (T8): Position → canonical Holding with embedded TaxLots.
- Schwab TaxLot translator (T9): lot → canonical TaxLot. cost_basis_method fail-closed.
- Schwab Household translator (T11): MasterAccount → canonical Household (custodial grouping).
- VENDOR_API_VERSION = "v1" (URL path versioning, v0.2.0 fix).
- `$`-prefix stripping on money fields via `@field_validator(mode="before")`.
- 8-digit accountNumber pattern validation.
- market_value_includes_accrued = False DERIVED (Schwab convention).
- unrealized_gain_loss_pct DERIVED (vendor decimal × 100).
- `IRA` vendor label → `traditional_ira` + `schwab_ira_label_ambiguous` note.
- Schwab UK SpecificLot → `ambiguous_mapping` (PENDING SME IMPL-06 follow-up).
