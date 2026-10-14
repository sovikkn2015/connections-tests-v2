# eMoney Translators — Changelog

All notable changes to eMoney translators are documented here.
Format: Keep a Changelog.

## [0.1.0] — 2026-04-26

### Added
- eMoney PlanSummary translator (T7): Plan SUMMARY → canonical PlanSummary.
- `extra="forbid"` on vendor model rejects raw plan body (M4 MNPI policy).
- `net_worth` DERIVED from totalAssets - totalLiabilities — declared REVERSE-lossy.
- plan_type mapping: Comprehensive→comprehensive, Retirement→retirement_only, etc.
- VENDOR_API_VERSION = "v2".
