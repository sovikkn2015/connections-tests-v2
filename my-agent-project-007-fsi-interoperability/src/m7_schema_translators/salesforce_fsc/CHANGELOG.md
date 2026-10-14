# Salesforce FSC Translators — Changelog

All notable changes to SF FSC translators are documented here.
Format: Keep a Changelog.

## [0.1.0] — 2026-04-26

### Added
- SF FSC Client translator (T1): Account+Contact → canonical Client.
- SF FSC Household translator (T2): FinServ__Household__c → canonical Household (container).
- SF FSC Goal translator (T3): FinServ__FinancialGoal__c → canonical Goal.
- ENUM_MAPPINGS / REVERSE_ENUM_MAPPINGS (MappingProxyType) for client_type, kyc_status, role, goal_type, status.
- LOSSY_FIELDS / REVERSE_LOSSY_FIELDS declared on every translator.
- Person Account vs Business Account / Trust branching via `@model_validator`.
- `archetype` pass-through with NO validation (M3 has no validator).
- funding_pct (Goal) DERIVED — declared REVERSE-lossy.

### Known-Pending
- SF FSC field names (FinServ__AccountIds__c, FinServ__HouseholdId__c, …) are PENDING-VERIFICATION vs live SF FSC v59.0 org via SOQL. DECISION-LOG owner assigned.
