# Spec: M5 Enterprise Config Loader

> Module: M5 — Enterprise Config Loader
> Phase: 0 (prerequisite — pure data, calls nothing)
> Owner: Trust Layer Specialist
> Version: 0.2.0 (post-LLMJ review v1 — all 8 fixes applied)
> Dependencies: None (M5 defines its own enums)
> Consumers: M2 (authority policy), M4 (MNPI policy), M8 (pipeline engine), M9 (intent router)
> Design Sources: 007-consolidated-design-and-plan.md Part 6 + Part 11, ARCH-09, ARCH-07, IMPL-06, ARCH-06-v3
> Language: Python 3.12+ | Validation: Pydantic v2 | Config Format: YAML
> Estimated Lines: ~250 Python + ~80 YAML per config template

---

## Review Fix Traceability

| Fix | Issue | Spec Section Updated |
|-----|-------|---------------------|
| FIX-1 | Runtime enum underscore convention | Design > Enum Convention Note |
| FIX-2 | Missing SuitabilityStandard enum | Enum Registry (now 8 enums) |
| FIX-3 | Missing PrincipalReviewMode + TimeoutAction enums | Enum Registry (now 8 enums) |
| FIX-4 | LEI validation regex missing | AC4.3 — regex specified |
| FIX-5 | AC8.6 warning not testable | AC8.6 — warnings.warn() specified |
| FIX-6 | validate_no_secrets patterns incomplete | Security Constraints — expanded |
| FIX-7 | No config version field | R15 added, EnterpriseConfig table updated |
| FIX-8 | ChannelConfig too loose | AC7.3 — VALID_CHANNELS frozenset |
| REC-1 | Config hash for provenance | R16 added |
| REC-2 | OPA bundle prefix helper | R17 added |

---

## Architecture Clarification: Library, Not Service

Per ARCH-09 dependency matrix, M5 calls nothing and is called by M2, M4, M8, M9 (4 consumers). M5 is a pure data library — it loads YAML config files, validates them with Pydantic v2, and exposes typed config objects. There is no REST API, no FastAPI, no HTTP server. Consumers import `load_enterprise_config()` and get a validated `EnterpriseConfig` object.

M5 defines its own enums for archetype, jurisdiction, registration type, topology, runtime, suitability standard, principal review mode, and timeout action. M3 does not export Archetype or Jurisdiction enums — M3 uses constrained strings for these fields. M5 is the canonical source for these controlled vocabularies.

---

## Requirements

### R1: Load and Validate Per-Firm YAML Config
**Acceptance Criteria:**
- AC1.1: `load_enterprise_config(path: Path) -> EnterpriseConfig` loads and validates a YAML file.
- AC1.2: Missing required fields raise `ValidationError` listing every missing field.
- AC1.3: Invalid enum values raise `ValidationError` with the invalid value and valid options.
- AC1.4: Config files with extra/unknown fields raise `ValidationError` (strict mode).
- AC1.5: File not found raises `FileNotFoundError` with the attempted path.
- AC1.6: Invalid YAML syntax raises `ConfigLoadError` with context.

### R2: 5 Enterprise Archetypes
**Acceptance Criteria:**
- AC2.1: `Archetype` enum has exactly 5 values: `tier1_investment_bank`, `tier2_asset_manager`, `tier3_broker_dealer`, `tier4_independent_ria`, `tier5_hedge_fund`.
- AC2.2: Archetype is required on `EnterpriseConfig`. Missing raises `ValidationError`.
- AC2.3: Each archetype maps to a distinct compliance profile.

### R3: 5 Jurisdictions
**Acceptance Criteria:**
- AC3.1: `Jurisdiction` enum has exactly 5 values: `us`, `eu`, `uk`, `sg`, `hk`.
- AC3.2: Jurisdiction is required on `JurisdictionConfig`. Missing raises `ValidationError`.
- AC3.3: `data_residency` is also a `Jurisdiction` enum value.

### R4: Firm Identity
**Acceptance Criteria:**
- AC4.1: `FirmConfig` has: `name` (str, required, min_length=1), `lei` (str | None, optional), `crd_number` (str, required, min_length=1), `registration_type` (RegistrationType enum, required).
- AC4.2: `crd_number` validated as non-empty via `min_length=1`.
- AC4.3: `lei` when provided validated with regex `^[A-Z0-9]{18}[0-9]{2}$` (ISO 17442). Invalid raises `ValidationError`.

### R5: Vendor Configuration
**Acceptance Criteria:**
- AC5.1: `VendorConfig` has: `crm` (str, required), `portfolio` (str, required), `planning` (str | None, optional), `custodians` (list[str], required, min_length=1), `market_data` (str | None, optional), `compliance_archive` (str | None, optional).
- AC5.2: Vendor names are free-form strings (not enums).
- AC5.3: `custodians` empty list raises `ValidationError`.

### R6: Deployment Configuration
**Acceptance Criteria:**
- AC6.1: `DeploymentConfig` has: `topology` (Topology enum), `region` (str), `runtime` (Runtime enum). All required.

### R7: Channel Configuration
**Acceptance Criteria:**
- AC7.1: `ChannelConfig` has: `enabled` (list[str], min_length=1), `primary` (str). All required.
- AC7.2: `primary` must be in `enabled`. Validator raises `ValidationError` if not.
- AC7.3: `VALID_CHANNELS = frozenset({"slack", "teams", "web", "whatsapp", "email", "sms"})`. All entries validated. Unknown raises `ValidationError`.

### R8: Compliance Configuration
**Acceptance Criteria:**
- AC8.1: `ComplianceConfig` has: `suitability_standard` (SuitabilityStandard enum), `reg_bi_enabled` (bool), `smarsh_enabled` (bool), `principal_review_enabled` (bool), `worm_retention_years` (int, ge=6), `mnpi_filtering` (str), `hitl_timeout_hours` (int, ge=1, le=168, default=24).
- AC8.2: `worm_retention_years` < 6 raises `ValidationError`.
- AC8.3: `principal_review_config` optional: `mode` (PrincipalReviewMode), `sla_hours` (int, ge=1, default=4), `timeout_action` (TimeoutAction, default=block).
- AC8.4: `bsa_aml_config` optional: `enabled` (bool), `ctr_threshold` (float, default=10000.0), `sar_structuring_threshold` (float, default=8000.0).
- AC8.5: `reg_bi_config` optional: `template` (str, default="default"), `conflict_inventory` (list[ConflictEntry], default=[]), `auto_generate` (bool, default=True), `require_advisor_review` (bool, default=True), `narrative_model` (str, default="haiku").
- AC8.6: BD archetype without principal_review_enabled: `model_validator(mode="after")` on `EnterpriseConfig` calls `warnings.warn("...", UserWarning)`. Testable via `pytest.warns(UserWarning)`.
- AC8.7: `principal_review_enabled=True` without `principal_review_config` raises `ValidationError`.

### R9: Specialist Agent Configuration
**Acceptance Criteria:**
- AC9.1: `SpecialistConfig` has: `enabled` (list[str]), `supervisor_model` (str, default="haiku"), `research_model` (str, default="sonnet"), `client_service_model` (str, default="haiku"), `execution_model` (str | None), `onboarding_model` (str | None).
- AC9.2: `VALID_SPECIALISTS = frozenset({"client_service", "research", "execution", "onboarding"})`. Unknown raises `ValidationError`.
- AC9.3: `compliance` in enabled list raises `ValidationError` (always implicit, OPA not LLM).

### R10: Memory Configuration
**Acceptance Criteria:**
- AC10.1: `MemoryConfig` has: `l1_ttl_hours` (int, ge=1, default=8), `l2_retention_days` (int, ge=1, default=7), `l3_retention_years` (int, ge=1, default=2), `l4_enabled` (bool, default=True), `l5_enabled` (bool, default=True).
- AC10.2: Integer values < 1 raise `ValidationError`.

### R11: MNPI Field Rules
**Acceptance Criteria:**
- AC11.1: `mnpi_filtering` string identifies the MNPI rule set.
- AC11.2: Actual rules in OPA/Rego bundles, not M5.

### R12: HITL Timeout
**Acceptance Criteria:**
- AC12.1: `hitl_timeout_hours` (int, ge=1, le=168, default=24).
- AC12.2: Outside 1-168 raises `ValidationError`.

### R13: No Credentials
**Acceptance Criteria:**
- AC13.1: No credential-like defaults in models.
- AC13.2: YAML files contain zero secrets.
- AC13.3: `validate_no_secrets(data: dict)` raises `ConfigSecurityError` on detection.

### R14: Strict Models
**Acceptance Criteria:**
- AC14.1: All models use `ConfigDict(extra="forbid")`.
- AC14.2: Unknown fields raise `ValidationError`.

### R15: Config Versioning
**Acceptance Criteria:**
- AC15.1: `config_version` (str, required) on `EnterpriseConfig`. Semver: `^\d+\.\d+\.\d+$`.
- AC15.2: `CONFIG_VERSION = "0.1.0"` constant exported.
- AC15.3: Mismatch raises `ValidationError`.

### R16: Config Hash for Provenance
**Acceptance Criteria:**
- AC16.1: `config_hash` field on `EnterpriseConfig` (SHA-256 hex digest of raw YAML bytes).
- AC16.2: Hash computed before parsing — hashes raw file, not parsed object.
- AC16.3: `config_hash` not in YAML file — computed and injected by loader.

### R17: OPA Bundle Prefix Helper
**Acceptance Criteria:**
- AC17.1: `EnterpriseConfig.get_opa_bundle_prefix() -> str` returns prefix. E.g., `tier3_broker_dealer` -> `"opa-bundles/tier3/"`.
- AC17.2: All 5 archetypes have defined mappings.

---

## Enum Registry (8 Enums)

| # | Enum | Values | Used By |
|---|------|--------|---------|
| 1 | `Archetype` | 5: `tier1_investment_bank`, `tier2_asset_manager`, `tier3_broker_dealer`, `tier4_independent_ria`, `tier5_hedge_fund` | EnterpriseConfig |
| 2 | `Jurisdiction` | 5: `us`, `eu`, `uk`, `sg`, `hk` | JurisdictionConfig |
| 3 | `RegistrationType` | 3: `ria_only`, `bd_only`, `dual_registered` | FirmConfig |
| 4 | `Topology` | 3: `cloud`, `hybrid`, `onprem` | DeploymentConfig |
| 5 | `Runtime` | 2: `managed_agents`, `strands_sdk` | DeploymentConfig |
| 6 | `SuitabilityStandard` | 2: `fiduciary`, `reg_bi` | ComplianceConfig |
| 7 | `PrincipalReviewMode` | 2: `pre_use`, `post_use` | PrincipalReviewConfig |
| 8 | `TimeoutAction` | 2: `block`, `escalate` | PrincipalReviewConfig |

---

## Design

### Directory Structure

```
my-agent-project-007-fsi-interoperability/
  src/m5_config_loader/
    __init__.py
    loader.py
  config/
    enterprise-config-tier3-bd.yaml
    enterprise-config-tier4-ria.yaml
  tests/unit/
    test_m5_config_loader.py
  tests/integration/
    test_phase0_m3_m5.py
```

### Module Boundary
- Imports: `__future__`, `hashlib`, `pathlib`, `re`, `typing`, `warnings`, `enum`, `pydantic`, `yaml`
- NO imports from M1-M13
- Consumers import from `m5_config_loader`

### Enum Convention (FIX-1)
All enum values use snake_case underscores. ARCHIVED configs used hyphens — corrected.

### Security Constraints
1. Zero credentials in config files or code
2. `validate_no_secrets()` patterns: `AKIA[A-Z0-9]{16}`, `sk-`, `Bearer `, `password`, `secret`, `api_key`, `-----BEGIN`, `ghp_`, `xoxb-`, `xoxp-`, `postgresql://`, `mongodb://`, `redis://`, `mysql://`, `token=`, `apikey=`
3. All models: `extra="forbid"`
4. LEI regex: `^[A-Z0-9]{18}[0-9]{2}$`

---

## Tasks

### Task 1: Enums, Constants, Exceptions (AC2.1, AC3.1, AC6.1, AC15.2)
Write `loader.py` with 8 enums, constants, exceptions. Write tests for enum values/counts.

### Task 2: Sub-Models (AC4.1-AC4.3, AC5.1-AC5.3, AC6.1, AC7.1-AC7.3, AC8.3-AC8.5, AC9.1-AC9.3, AC10.1-AC10.2)
Add all sub-models with validators. Write tests for each.

### Task 3: ComplianceConfig (AC8.1-AC8.2, AC8.7, AC12.1-AC12.2)
Add ComplianceConfig with cross-field validators. Write tests.

### Task 4: EnterpriseConfig (AC1.4, AC2.2, AC8.6, AC14.1-AC14.2, AC15.1, AC15.3, AC16.1, AC17.1-AC17.2)
Add top-level model with version check, hash field, OPA helper, BD warning. Write tests.

### Task 5: Loader + Security (AC1.1-AC1.6, AC13.3, AC16.2)
Add load function, secret scanner, __init__.py. Write tests.

### Task 6: Sample Configs (AC1.1, AC13.2)
Write YAML configs. Write load-and-validate tests.

### Task 7: Integration Test (AC2.3, AC3.3)
Write Phase 0 M3+M5 integration test.
