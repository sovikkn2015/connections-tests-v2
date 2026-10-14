# Adapter-Layer Remediation Fixes Spec

> Workstream: 007-adapter-agent remediation lane
> Scope: B1, B3, B4 (BLOCKERS) + M5, M9, M10, M11, M12 + sidecar (MAJORS) + M14 roadmap (deferral)
> Date: 2026 Q2 remediation cycle
> Goal: lift adapter-layer LLMJ from 6.0 → ≥ 8.0 GO

## Summary of changes

### BLOCKER B1 — M7 canonicalize at M6 gateway layer
- Add `src/m6_mcp_gateway/canonicalize.py` exposing a `Canonicalizer` with
  `(vendor, tool_name) -> translator_function` dispatch.
- Stage 6 of `TrustAwareGateway.call` (currently "translate (no-op Phase 1)")
  replaces its pass-through with `Canonicalizer.translate(vendor, tool_name, raw)`.
- Unknown `(vendor, tool_name)` pairs pass through unchanged (AC: Smarsh search
  returns unstructured transcripts that have no canonical shape).
- Adapters stay vendor-pure (Rule 33).
- Integration test: `tests/integration/test_m6_m7_canonicalize.py` pushes an
  Orion holdings vendor payload through `TrustAwareGateway.call` and asserts the
  response's `result` is an M3 `Holding` model.

### BLOCKER B3 — 5 REST-adapter Helm subcharts
Five new subcharts under `deploy/helm/007-fsi/charts/`:
- `m11-salesforce-fsc-adapter/`
- `m11-schwab-adapter/`
- `m11-orion-adapter/`
- `m11-emoney-adapter/`
- `m11-smarsh-archive-adapter/`

Each contains 11 files:
`Chart.yaml`, `values.yaml`, `templates/_helpers.tpl`, `templates/deployment.yaml`,
`templates/service.yaml`, `templates/serviceaccount.yaml`,
`templates/networkpolicy.yaml` (ingress from M6 only; egress in allowlist mode
merges `egressAllowlist` + kube-dns + Vault), `templates/pdb.yaml`,
`templates/certificate.yaml` (cert-manager 24h), `templates/externalsecret.yaml`,
`templates/configmap.yaml`.

Umbrella `Chart.yaml` picks up 5 new `condition:`-guarded dependencies.
`values-cloud.yaml` gets 5 new blocks:
- `m11-<vendor>-adapter.enabled: false`
- `m11-<vendor>-adapter.egressAllowlist: [...]` (Vault + vendor host stubs)

`deploy/tests/test_helm_lint.sh` adds the 5 new subchart paths.
`deploy/tests/test_helm_template_egress.sh` keeps Phase B count assertion
tolerant (>=4) — the extras render only when enabled, so default install still
produces ~11 NetworkPolicies.

### BLOCKER B4 — Audit sidecar + M10 canonical shape
1. Shared sidecar template `deploy/helm/007-fsi/charts/_common/fluent-bit-sidecar.yaml`
   is a helm template helper (named template: `007.fluentBitSidecar`) that each
   adapter chart includes. Config map keyed by chart release name.
2. M10 `POST /audit` is extended to accept two shapes via shape-sniffer:
   - Existing `StageAuditPayload` (M8 pipeline events).
   - New adapter-canonical: `{module, kind, ts, tool?, firm_id?, tenant_id?, outcome?, duration_ms?, ...}`.
   Both translate into M3 `AuditEntry`; fan out to the 3-tier WORM pipeline.
3. All M11 subcharts (BLPAPI, gRPC, 5 REST) + M13 include the sidecar container.
4. Integration test: `tests/integration/test_m10_adapter_audit_shape.py` injects
   an adapter-canonical event and asserts the entry lands in all three tiers
   with `tenant_id` + `firm_id` preserved.

### MAJOR M5 — Canonical error envelope for REST
- Port `src/m11_rest_adapters/shared/mcp-sdk/src/server.ts` + `errors.ts`:
  - from: `{result, error: {code, message, vendorStatusCode, retryable}}`
  - to:   `{isError: boolean, content: [{type:"text", text: string}], errorCode: string, vendorStatusCode?: number, retryable: boolean}`
  - Success bodies drop `result` in favour of `{isError: false, content: <handler return>}`.
- Keep the 22-code error vocab.
- Update every vendor adapter test suite and the shared SDK tests.

### MAJOR M9 — 3 missing M7 translators
- `src/m7_schema_translators/bloomberg/` — `security_profile.py` (SecurityProfile) + `quote.py` (Quote).
- `src/m7_schema_translators/ice_data/` — `security_profile.py` + `quote.py`.
- `src/m7_schema_translators/smarsh/` — `interaction_summary.py` (InteractionSummary).
- Registered in `TRANSLATOR_REGISTRY` via package `__init__`.
- Reconciliation tests under `tests/schema-reconciliation/`:
  - `test_m7_roundtrip_bloomberg.py`, `test_m7_roundtrip_ice_data.py`,
    `test_m7_roundtrip_smarsh.py`.

### MAJOR M10 — REST Dockerfile fixes
Each of the 5 REST Dockerfiles:
- Adds `HEALTHCHECK --interval=30s --timeout=3s --retries=3 CMD [...] /healthcheck.sh` (wrapper that hits `GET /`).
- Switches `USER nonroot` to numeric `USER 1000`.
- Adds `LABEL org.opencontainers.image.title="007-fsi/m11-<vendor>-adapter"`.
- `deploy/tests/test_dockerfile_security.sh` DOCKERFILES array extended to
  include all 5.

### MAJOR M11 — SS&C Eze → ICE Data ADR
- New file `docs/architecture/ADR-02-gRPC-lighthouse-ICE-vs-Eze.md`.
- Amendment note at the top of `ARCH-07-definitive-tech-stack.md` referencing
  ADR-02.

### MAJOR M12 — M13 per-tenant salt
- Refactor `DropCopyEmitter.__init__` to accept `salt_provider: Callable[[str], bytes]`
  instead of `account_salt: bytes`.
- `StaticSaltProvider(salt_bytes)` helper for tests and single-tenant installs.
- `VaultSaltProvider(secrets_client, path_template)` helper for production
  (path template `secret/data/007/m13/account_hash_salt/{tenant_id}`).
- `create_app(account_salt=...)` in `m13_fix_bridge/app.py` changes to
  `create_app(salt_provider=...)` (preserving `account_salt` as a convenience
  shim for backwards compat in tests).
- Update `startup.py` to build `VaultSaltProvider` from env template.
- Update `drop_copy._emit_canonical` to call `salt_provider(tenant_id)`.

### DEFERRED M14 — SFTP + MCP-NATIVE
- `docs/roadmap.md` updated with Phase 3 entries:
  - `M11-SFTP (Schwab/Fidelity daily files)` — target Phase 3 BD onboarding.
  - `M11-MCP-NATIVE (FactSet passthrough)` — target Phase 3.

## Compliance review

- Rule 33 (no cross-module imports) preserved — M7 is called from M6 gateway,
  not from adapters.
- Rule 10 (polyglot M11) preserved — REST subcharts follow the BLPAPI/gRPC
  pattern.
- Rule 6 (3-tier WORM audit) — sidecar + M10 canonical shape extend coverage
  to M11/M13.
- Rule 5 (canonical error envelope) — TypeScript half aligned to Python/M13.
- Rule 16 (cost_basis never null) — unchanged; new translators either don't
  carry cost basis (Bloomberg/ICE security profile + Smarsh interaction) or
  route through `normalize_cost_basis_method`.
- Rule 20 (zero creds) — all new subcharts use Vault path patterns only.
- Rule 21 (24h mTLS rotation) — new certificate templates inherit
  `duration: 24h` default.

## Test strategy

- Python: `pytest tests/` must stay ≥ 2127 passed, grow to ~2230 with new
  translator + audit shape + canonicalize + sidecar shim tests.
- TypeScript: `cd src/m11_rest_adapters && npm test` — all 5 adapter suites
  + shared SDK green.
- Deploy gates: all 6 shell scripts PASS.
- 10/10 stable bundle runs.

