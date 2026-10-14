# M5 Enterprise Config Loader — DECISION LOG

Chronological record of schema-shape decisions for `m5_config_loader`.
Each entry captures the trigger, resolution, and downstream impact so future
maintainers can audit the SemVer path without re-reading every spec.

---

## D1 — v0.1.0 initial schema

Phase 0 scaffold per `docs/007-consolidated-design-and-plan.md` Part 6.
Shipped: `FirmConfig`, `Archetype` (5 tiers), `JurisdictionConfig` (5 regions),
`DeploymentConfig`, `VendorConfig`, `ChannelConfig`, `ComplianceConfig`,
`SpecialistConfig`, `MemoryConfig`, `EnterpriseConfig`,
`load_enterprise_config`, `validate_no_secrets` credential scanner.
`CONFIG_VERSION = "0.1.0"`.

---

## D2 — v0.3.0 · `IntentRouterConfig` sub-model (SHARED-WITH-M5, M9 Known Blockers row 2)

**Trigger.** M9 v0.2.0 spec §Known Blockers row 2 declares that M9 consumes
an `IntentRouterConfig` sub-model attached under `SpecialistConfig`. M9's
AST positive-allow-list import `from m5_config_loader import
IntentRouterConfig` fails until M5 ships it. Integration gate
`tests/integration/test_m9_m5_config_shape.py` was xfail-strict-false
until this entry shipped.

**Resolution.** Added `IntentRouterConfig` as a frozen Pydantic v2 model
with `ConfigDict(frozen=True, extra="forbid")`. Fields mirror M9 spec
AC5.1-AC5.4 / AC4.5:

| Field | Type | Default | Source |
|-------|------|---------|--------|
| `model_id` | `str` | `"anthropic.claude-3-5-haiku-20241022-v1:0"` | M9 Known Blockers row 3 |
| `provider` | `Literal["bedrock","azure_openai","vertex","vllm"]` | `"bedrock"` | M9 AC4.5 |
| `region` | `str` | `"us-east-1"` | M9 Known Blockers row 2 |
| `confidence_high` | `float` (0-1) | `0.95` | M9 AC5.1 |
| `confidence_med` | `float` (0-1) | `0.80` | M9 AC5.2 |
| `timeout_ms` | `int` (1-30000) | `1500` | M9 AC1.8 |
| `fallback_enabled` | `bool` | `True` | M9 R7 |
| `tenant_hmac_key_vault_path` | `str` | required | M9 Fix 10 |

Validators:
- `_no_literal_secret` on `tenant_hmac_key_vault_path` — rejects any
  value that matches `_SECRET_PATTERNS` (Steering Rule 20).
- `_validate_threshold_ordering` — M9 AC5.4 invariant
  (`confidence_high > confidence_med > 0.0`).

Wired under `SpecialistConfig.intent_router: Optional[IntentRouterConfig]`
(`default=None`). Phase 1 RIAs may leave it None. Public API gains
`load_intent_router_config(path)` convenience helper that goes through
`load_enterprise_config(path).specialists.intent_router`.

**Downstream impact.**
- `CONFIG_VERSION` bumped `"0.1.0"` → `"0.3.0"` (MINOR: additive).
- Sample configs re-versioned.
- M9 integration xfail lifted; test passes on v0.3.0.
- `FakeIntentRouterConfig` in `tests/conftest.py` remains for M9 internal
  tests — duck-typed, field subset of the real model.

---

## D3 — v0.4.0 · `PipelineConfig` sub-model (SHARED-WITH-M5, M8 Known Blockers row 1)

**Trigger.** M8 v0.2.0 spec §Known Blockers row 1 declares that M8 consumes
a `PipelineConfig` sub-model attached under `SpecialistConfig`. Integration
gate `tests/integration/test_m8_m5_config_shape.py` was xfail-strict-false
until this entry shipped.

**Resolution.** Added `PipelineConfig` as a frozen Pydantic v2 model with
`ConfigDict(frozen=True, extra="forbid")`. Fifteen fields per M8 spec:

| Field | Type | Default | Source |
|-------|------|---------|--------|
| `model_id` | `str` | `"anthropic.claude-sonnet-4-5-20250929-v1:0"` | M8 Known Blockers row 2 |
| `model_provider` | `Literal["bedrock","azure_openai","vertex","vllm"]` | `"bedrock"` | M8 R6 |
| `region` | `str` | `"us-east-1"` | M8 Known Blockers row 1 |
| `checkpointer_backend` | `Literal["postgres","dynamodb"]` | `"postgres"` | M8 R3 |
| `checkpointer_dsn_vault_path` | `str` | required | M8 Known Blockers row 4 |
| `hitl_timeout_seconds` | `int` | `14400` (4h) | M8 AC4.3 |
| `hitl_hmac_key_vault_path` | `str` | required | M8 AC4.12 |
| `max_concurrent_instruments` | `int` (1-100) | `10` | M8 Known Blockers row 10 |
| `max_pipeline_wall_clock_seconds` | `int` | `1200` (20 min) | M8 AC16.1 |
| `alert_pipeline_wall_clock_seconds` | `int` | `900` (15 min) | M8 AC16.2 |
| `token_budgets` | `dict[str, int]` | M8 Token Budget Table (12 stages) | M8 AC16.4 |
| `gateway_base_url` | `str` | required | M8 §M6 Gateway |
| `gateway_mtls_client_cert_path` | `str` | required | M8 §M6 Gateway |
| `audit_base_url` | `str` | required | M8 v0.2.0 Required Fix 4 |
| `audit_mtls_client_cert_path` | `str` | required | M8 v0.2.0 Required Fix 4 |

Validators:
- `_no_literal_secret` across all four vault/cert path fields — rejects
  any value matching `_SECRET_PATTERNS` (Steering Rule 20).
- `_positive_token_budgets` — every per-stage budget must be a positive
  `int` (rejects `bool`, `str`, `float`, `<=0`).
- `_validate_wall_clock_ordering` —
  `alert_pipeline_wall_clock_seconds <= max_pipeline_wall_clock_seconds`
  (M8 AC16.1 / AC16.2 consistency).

Default `token_budgets` carries the twelve per-stage Sonnet `maxTokens`
values from M8 v0.2.0 §Token Budget Table:
`stage_1_intake=2000`, `stage_4_news_sentiment=10000`,
`stage_6_transcript_analysis=8000`, `stage_8_financial_modeling=8000`,
`stage_9_dcf_valuation=6000`, `stage_10_comps_analysis=6000`,
`stage_12_cross_source_synthesis=15000`,
`stage_14_thesis_generation=8000`,
`stage_15_catalyst_identification=4000`, `stage_16_risk_assessment=4000`,
`stage_17_rating_determination=2000`, `stage_19_brief_assembly=12000`.

Wired under `SpecialistConfig.pipeline: Optional[PipelineConfig]`
(`default=None`). Phase 1 RIAs without M8 deployed leave it None. Public
API gains `load_pipeline_config(path)` convenience helper that goes
through `load_enterprise_config(path).specialists.pipeline`.

**Downstream impact.**
- `CONFIG_VERSION` bumped `"0.3.0"` → `"0.4.0"` (MINOR: additive).
- Sample configs re-versioned to `"0.4.0"` (no new sub-config content
  required because the fields are Optional; Phase 1 firms stay on the
  minimum schema).
- M8 integration xfail lifted; test passes on v0.4.0.
- `FakePipelineConfig` in `tests/fixtures/m8_fixtures.py` remains for M8
  internal tests; integration gate now asserts
  `set(FakePipelineConfig.model_fields) <= set(PipelineConfig.model_fields)`
  to catch drift in future minor bumps.

---

## Invariants (enforced by the test suite)

- **Zero credentials.** No field accepts an embedded credential value.
  `_no_literal_secret` validators on every Vault/cert-path field + the
  module-level `validate_no_secrets()` scanner on loaded YAML.
- **Frozen sub-configs.** Both v0.3.0+ / v0.4.0+ sub-models use
  `ConfigDict(frozen=True)`. Mid-run tuning is not supported; configs are
  loaded once and treated as immutable.
- **Fail-closed defaults.** `IntentRouterConfig` high=0.95, med=0.80,
  fallback_enabled=True. `PipelineConfig` max_pipeline_wall_clock=1200s,
  hitl_timeout=14400s.
- **Backward-compatible minor bumps.** Each additive field is Optional
  (top-level) or has a spec-derived default.

---

## Reserved slots (not yet shipped)

- **v0.5.0** — reserved for M11 per-adapter config (BLPAPI, gRPC, FIX).
  No M11 spec has yet declared a SHARED-WITH-M5 requirement.
- **v1.0.0** — bump when first BD deployment hardens the schema (Phase 3).
