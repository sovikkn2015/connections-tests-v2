# Remediation Trust-Layer Fixes — Combined Spec

> Scope: 2 BLOCKERS (B11, B12) + 5 MAJORS (M3, M4, M7, M8, M11) + steering carve-out.
> Owner: 007-trust-agent (LLMJ-graded).
> Baseline: 2127 passing tests, 0 regressions, 5 deploy gates green.
> Target: same test floor + new tests that prove each fix.

This is one spec covering all seven trust-lane fixes mandated by
`.kiro/reviews/REMEDIATION-PLAN.md`. Each fix has its own Requirements
section (with numbered ACs), Design section, and Tasks section.
Integration gates and regression budgets are shared at the end.

---

## 0. Glossary + fix index

| ID | Kind | Short name | Primary files touched |
|----|------|-----------|-----------------------|
| B11 | BLOCKER | Helm duplicate `global:` | `deploy/helm/007-fsi/values-cloud.yaml` + new unit test |
| B12 | BLOCKER | M10 fail-closed on in-memory backends | `src/m10_audit_logger/app.py` |
| M3-FIX | MAJOR | `tenant_id` on AidClaims + AuditEntry | `src/m1_identity/claims.py`, `src/m3_schema_registry/types.py`, M10, all call sites |
| M4-FIX | MAJOR | `strict=True` on Pydantic models | `src/m5_config_loader/loader.py`, `src/m1_identity/claims.py`, `src/m11_blpapi_adapters/**/models.py`, `src/m11_grpc_adapters/**/models.py` + ADR |
| M7-FIX | MAJOR | Rename `/gateway/call` → `/tools/call` | `src/m6_mcp_gateway/app.py`, `src/m8_pipeline_engine/gateway_client.py`, tests |
| M8-FIX | MAJOR | M1 startup hook fail-closed | `src/m1_identity/app.py` |
| M11-FIX | MAJOR | M11-Python audit shape alignment | `src/m11_python_adapters_shared/audit_emitter.py`, `src/m10_audit_logger/app.py` (ingest translator) |
| STEERING | REQUIRED | Phase-1 carve-out dated Phase-2 | `.kiro/steering/007-fsi-interoperability.md` |

Regression budget: all seven fixes must leave `pytest tests/ -q --timeout=60`
at **≥ 2127 passed, 0 regressions**. Net test count should grow by at least
the new coverage each fix introduces.

---

## 1. B11 — Helm `values-cloud.yaml` duplicate `global:`

### 1.1 Problem

`deploy/helm/007-fsi/values-cloud.yaml` declares `global:` twice (lines 14
and 128). PyYAML + Helm take the last one, silently dropping
`global.topology`, `global.namespace`, `global.imageRegistry`,
`global.tenantRoleArn`, `global.labels`, and `global.certManager` (24h
duration, 2h renewBefore). Confirmed by `yaml.safe_load` returning a
`global` dict with only `networkPolicy` and `privateLinkCidrs`.

This is a silent production footgun — not caught by the Helm-template
gates because each chart reads a single key at a time and does not
assert the umbrella has a complete `global`.

### 1.2 Requirements

| AC  | Statement |
|-----|-----------|
| B11.1 | `values-cloud.yaml` contains exactly ONE top-level `global:` mapping. |
| B11.2 | The merged `global:` contains ALL expected keys: `topology`, `namespace`, `imageRegistry`, `tenantRoleArn`, `labels` (at minimum `app.kubernetes.io/part-of`, `app.kubernetes.io/managed-by`), `certManager` (at minimum `issuerName`, `issuerKind`, `duration`, `renewBefore`), `networkPolicy.egressMode`, `privateLinkCidrs.bedrockRuntime`. |
| B11.3 | `global.certManager.duration` == `"24h"` (Steering Rule 21 — mTLS 24h rotation). |
| B11.4 | A new pytest unit test loads `values-cloud.yaml` via `yaml.safe_load`, asserts there is exactly one `global`, and asserts each of the eight sub-keys above is present with the expected shape. |
| B11.5 | Existing deploy gates — `bash deploy/tests/test_helm_lint.sh`, `bash deploy/tests/test_helm_template_egress.sh`, `bash deploy/tests/test_dockerfile_security.sh` — all continue to PASS. |
| B11.6 | `externalSecrets`, `m1-identity`, `m2-m4-policy-engine`, `m6-mcp-gateway`, `m10-audit-logger`, `m8-pipeline-engine`, `m9-intent-router`, `m12-supervisor`, `m13-fix-bridge`, `m11-blpapi-adapter`, `m11-grpc-adapter` top-level keys retain their sub-structures exactly as-is (no sub-chart override drift). |

### 1.3 Design

Strategy: physically merge the second `global:` block into the first.
The second block only adds `networkPolicy` and `privateLinkCidrs`. The
fix is purely structural — no value changes, no default changes.

Resulting single `global:` block layout (comment-preserved):

```yaml
global:
  topology: cloud
  namespace: trust-layer
  imageRegistry: example.invalid/007-fsi           # OVERRIDE PER TENANT
  tenantRoleArn: "arn:aws:iam::..."                # OVERRIDE PER TENANT
  labels:
    app.kubernetes.io/part-of: 007-fsi
    app.kubernetes.io/managed-by: helm
  certManager:
    issuerName: letsencrypt-prod                   # OVERRIDE PER TENANT
    issuerKind: ClusterIssuer
    duration: 24h                                  # Rule 21
    renewBefore: 2h
  networkPolicy:
    egressMode: allowlist                          # Wave 4
  privateLinkCidrs:
    bedrockRuntime: "10.100.0.0/16"                # OVERRIDE PER TENANT
```

The existing top-level `certManager:` block (outside `global:`) stays;
it's the sub-chart defaults consumed by `_helpers.tpl`. Only the `global:`
mapping is merged.

Test file: `tests/unit/test_values_cloud_global.py`. No cross-module
dependency — uses stdlib `yaml` only.

### 1.4 Tasks

1. Physically merge the two `global:` blocks in
   `deploy/helm/007-fsi/values-cloud.yaml`. Preserve all comments.
2. Write `tests/unit/test_values_cloud_global.py` covering ACs B11.1-B11.3, B11.6.
3. Run `bash deploy/tests/test_helm_lint.sh` — must PASS.
4. Run `bash deploy/tests/test_helm_template_egress.sh` — must PASS.
5. Run full suite — must stay at ≥ 2127 passed, 0 regressions.

---

## 2. B12 — M10 fail-closed on in-memory backends

### 2.1 Problem

`src/m10_audit_logger/app.py::_default_logger` ships `InMemoryAuditBackend`
on all three tiers (`langfuse`, `worm`, `crm`). Stock container serves
200 on `/audit` — audit events go straight to RAM and die on pod restart.
Rule 4 (SEC 17a-4, 6-year WORM) is structurally violated. Readiness does
not distinguish in-memory from real.

### 2.2 Requirements

| AC  | Statement |
|-----|-----------|
| B12.1 | Env var `M10_ALLOW_IN_MEMORY_AUDIT` controls behavior. Accepts `true`/`false` (case-insensitive). Default `false`. |
| B12.2 | When env var is `false` AND the audit logger's three backends are all `InMemoryAuditBackend`: `GET /health` returns 503 with JSON body containing `"status": "not_ready"` AND `"reason": "backends_not_wired"`. |
| B12.3 | Under the same conditions as B12.2: `POST /audit` returns 503 with JSON body `{"error": "backends_not_wired"}` — no backend write is attempted. |
| B12.4 | When env var is `true` (explicit dev opt-in): `GET /health` returns 200 with `"status": "ok"` AND `"allow_in_memory_audit": true` AND the backend-mode health sub-object continues to report tiers. `POST /audit` serves normally. Structured stdout emits a single WARN-like line on startup naming the dev override. |
| B12.5 | When at least one backend is NOT `InMemoryAuditBackend` (i.e., a real backend is wired): `/health` returns 200 AND `/audit` serves normally, REGARDLESS of env var value. |
| B12.6 | The detection logic is implemented at startup (FastAPI `@app.on_event("startup")`) AND on every `/audit` request (defense-in-depth — backends can be swapped at runtime via `app.state.audit_logger = ...`, which is how tests drive both paths). |
| B12.7 | Existing test suite stays green. New tests explicitly cover the four matrix entries (env=false × unwired, env=false × wired, env=true × unwired, env=true × wired). |
| B12.8 | Module-level default `app = create_app()` remains importable without setting the env var. (It boots into 503 state, correctly — that is the desired fail-closed default.) |

### 2.3 Design

Detection function:

```python
def _all_backends_in_memory(audit_logger: AuditLogger) -> bool:
    from m10_audit_logger.backends import InMemoryAuditBackend
    return (
        isinstance(audit_logger._langfuse, InMemoryAuditBackend)
        and isinstance(audit_logger._worm, InMemoryAuditBackend)
        and isinstance(audit_logger._crm, InMemoryAuditBackend)
    )
```

Backend tier attributes are private (`_langfuse`, `_worm`, `_crm`). To
avoid reading private attrs from the outside we add a small `AuditLogger`
introspection helper:

```python
# AuditLogger (logger.py) new method
def backends_by_tier(self) -> dict[str, AuditBackend]:
    """Public handle for health probes + boot-time readiness checks.

    Health probes (M10 `/health`, readiness sidecars) MUST call this
    method — they MUST NOT read `self._langfuse`, `self._worm`, or
    `self._crm` directly. The private slots can be rearranged in
    Phase 2 without breaking public callers.
    """
    return {"langfuse": self._langfuse, "worm": self._worm, "crm": self._crm}
```

App factory reads `M10_ALLOW_IN_MEMORY_AUDIT` from env ONCE at
`create_app` time (or `startup` event), caches on `app.state`:

```python
import os
new_app.state.allow_in_memory = (
    os.environ.get("M10_ALLOW_IN_MEMORY_AUDIT", "false").lower() == "true"
)
```

At every `/audit` + `/health` call:

```python
def _backends_wired(request) -> bool:
    if request.app.state.allow_in_memory:
        return True  # dev opt-in
    logger_inst = request.app.state.audit_logger
    tiers = logger_inst.backends_by_tier()
    from m10_audit_logger.backends import InMemoryAuditBackend
    return any(not isinstance(b, InMemoryAuditBackend) for b in tiers.values())
```

If `_backends_wired(request) is False`:
- `/health` → 503 `{"status":"not_ready","reason":"backends_not_wired","version":"..."}`.
- `/audit` POST → 503 `{"error":"backends_not_wired"}` BEFORE parsing body (so we don't waste CPU on an invalid payload).

On startup, emit a structured stdout line:

```python
_structured_stdout({
    "phase": "startup",
    "module": "m10",
    "allow_in_memory_audit": new_app.state.allow_in_memory,
    "backends_wired": not _all_in_memory,
})
```

Tests: build two backends scenarios:
- Unwired (default triple of `InMemoryAuditBackend`).
- Wired (one tier swapped to a fake real-backend class).

For each, exercise both env-var settings. 4 scenarios × 2 routes = 8
new assertions minimum.

### 2.4 Tasks

1. Add `AuditLogger.backends_by_tier()` to `src/m10_audit_logger/logger.py`.
2. In `src/m10_audit_logger/app.py`:
   - Import `os`.
   - Add `_read_allow_in_memory()` helper that reads + parses env once.
   - Add `_backends_wired(request)` gate helper.
   - Wire startup event to compute + emit startup stdout line.
   - Guard `/health` + `/audit` handlers using `_backends_wired`.
3. Add tests at `tests/unit/test_m10_app_failclosed.py`:
   - `test_health_503_when_unwired_and_env_false`
   - `test_health_200_when_unwired_and_env_true`
   - `test_health_200_when_at_least_one_real_backend`
   - `test_audit_post_503_when_unwired_and_env_false`
   - `test_audit_post_202_when_env_true_even_if_all_inmemory`
   - `test_audit_post_202_when_real_backend_wired`
   - `test_startup_emits_stdout_allow_in_memory_flag`
   - `test_backends_by_tier_returns_three_keys`
4. Run full suite — ≥ 2127 passed, 0 regressions.

---

## 3. M3-FIX — `tenant_id` on AidClaims + AuditEntry

### 3.1 Problem

- `AidClaims` (M1) has no `tenant_id` field.
- `AuditEntry` (M3) has no `tenant_id` field.
- M10 wire payload requires `tenant_id` (see `_REQUIRED_KEYS` in `src/m10_audit_logger/app.py`) but `_translate_to_audit_entry` silently drops it.
- Rule 23 (per-tenant KMS, namespace isolation) cannot be satisfied.

### 3.2 Requirements

| AC  | Statement |
|-----|-----------|
| M3.1 | `src/m1_identity/claims.py::AidClaims` has a REQUIRED `tenant_id: str` field (Field with `min_length=1`, no default). Pydantic raises `ValidationError` when missing. |
| M3.2 | `src/m3_schema_registry/types.py::AuditEntry` has a REQUIRED `tenant_id: str` field (`Field(description=...)`, non-optional). |
| M3.3 | `src/m10_audit_logger/app.py::_translate_to_audit_entry` passes the wire `tenant_id` into the constructed `AuditEntry` (no longer drops it). `tenant_id` is in the unchanged `_REQUIRED_KEYS` tuple (already required). |
| M3.4 | Every existing `AidClaims(...)` construction in the repo (both `src/` and `tests/`) is updated to pass `tenant_id`. Use `firm_id` as the default value when no explicit tenant is needed (tests may continue to treat tenant_id as firm-scoped). |
| M3.5 | Every existing `AuditEntry(...)` construction in the repo is updated to pass `tenant_id`. Tests use stable tenant values (e.g., `"tenant-01"` or `f"tenant-{firm_id}"`). |
| M3.6 | `tests/conftest.py` fixture `_COMMON_AID` is extended with `tenant_id=<value>`, not dropped. |
| M3.7 | No backwards compatibility shim. The field is required on both models. Migration touches tests + production code atomically. |
| M3.8 | Full suite (≥ 2127 tests) passes after migration, zero regressions. |

### 3.3 Design

#### 3.3.1 AidClaims change

```python
# src/m1_identity/claims.py
class AidClaims(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)  # strict=True per M4-FIX
    ...
    firm_id: str = Field(..., min_length=1)
    tenant_id: str = Field(..., min_length=1)   # NEW — Rule 23 support
    ...
```

Ordering: `tenant_id` goes right after `firm_id` (semantic neighbor).

#### 3.3.2 AuditEntry change

```python
# src/m3_schema_registry/types.py AuditEntry
class AuditEntry(BaseModel):
    ...
    firm_id: str = Field(description="Firm context for multi-tenant.")
    tenant_id: str = Field(description="Tenant context for per-tenant KMS routing (Rule 23).")
    jurisdiction: Optional[str] = ...
```

Ordering: `tenant_id` goes right after `firm_id` for the same reason.

#### 3.3.3 M10 translator change

```python
# src/m10_audit_logger/app.py _translate_to_audit_entry
return AuditEntry(
    ...
    firm_id=str(body["firm_id"]),
    tenant_id=str(body["tenant_id"]),   # NEW
    worm_record_id=worm_record_id,
    ...
)
```

`tenant_id` is already in `_REQUIRED_KEYS`, so wire validation is
unchanged — we just stop dropping it on translation.

#### 3.3.4 Call-site migration

Search-and-update script target paths:

- `src/m13_fix_bridge/aid_verify.py` — M13 has its OWN dataclass `AidClaims`, it already has `tenant_id`. No change needed. (Confirmed by reading `src/m13_fix_bridge/aid_verify.py`.)
- `tests/conftest.py` `_COMMON_AID` — add `tenant_id="firm-hyp-fixture"` (reuse `firm_id`).
- `tests/integration/test_m12_onboarding_trust_chain.py` — add `tenant_id=`.
- `tests/unit/test_m2_m4_policy_engine.py` — add `tenant_id=`.
- `tests/unit/test_m12_execution_specialist.py` — add `tenant_id=`.
- `tests/unit/test_m12_onboarding_specialist.py` — add `tenant_id=`.
- `tests/unit/test_gap1_reg_bi_doc_generator.py` — add `tenant_id=`.
- `tests/integration/test_m12_execution_trust_chain.py` — add `tenant_id=`.
- `tests/integration/test_gap1_end_to_end.py` — add `tenant_id=`.

For `AuditEntry(...)` call sites, a targeted grep identifies and
updates each construction; most live in tests — production M6/M10 paths
use `_translate_to_audit_entry` or similar factory, so the production
fix is already covered by the M10 translator change.

Default convention across the migration: `tenant_id=firm_id` (treat
single-tenant-per-firm). Tests that explicitly want multiple tenants
(none exist today) would pass an explicit value.

### 3.5 Steering-authorized cross-module change

My trust-agent directory boundaries forbid writes to
`src/m3_schema_registry/`. The remediation plan in
`.kiro/reviews/REMEDIATION-PLAN.md` explicitly authorizes this one
cross-module change: *"If AuditEntry requires cross-module changes,
make them — this fix is Rule-23 critical."* The change is scoped to
a SINGLE new field (`tenant_id: str`) on `AuditEntry`, placed after
`firm_id`. No other M3 types are touched. No M3 types are renamed or
removed. This is a one-shot steering exception, documented in the
Phase-2 steering carve-out (Section 8 of this spec).

### 3.6 Tasks

1. Update `src/m1_identity/claims.py::AidClaims` — add `tenant_id: str`, place after `firm_id`.
2. Update `src/m3_schema_registry/types.py::AuditEntry` — add `tenant_id: str`, place after `firm_id`.
3. Update `src/m10_audit_logger/app.py::_translate_to_audit_entry` — carry `tenant_id` from wire to entry.
4. `grepSearch` for `AidClaims(` across `tests/` + `src/` and update every call site.
5. `grepSearch` for `AuditEntry(` across `tests/` + `src/` and update every call site.
6. Add dedicated unit tests:
   - `tests/unit/test_m1_aidclaims_tenant_id.py` — AC M3.1. Covers:
     * `test_aidclaims_missing_tenant_id_raises_validation_error` (negative).
     * `test_aidclaims_roundtrip_preserves_tenant_id` (positive — construct with explicit value, `model_dump()`, re-validate, assert tenant_id equal).
   - `tests/unit/test_m3_audit_entry_tenant_id.py` — AC M3.2 (missing tenant_id → `ValidationError`).
   - `tests/unit/test_m10_translator_carries_tenant_id.py` — AC M3.3 (translator keeps `tenant_id`).
7. Run full suite — ≥ 2127 passed + new tests, 0 regressions.

---

## 4. M4-FIX — `strict=True` on all Pydantic v2 models

### 4.1 Problem

Rule 32 says "Pydantic v2 strict for all input models". Only `HoldEntry`
in `src/m10_audit_logger/backends_minio/legal_hold.py` has both
`extra="forbid"` and `strict=True`. Every other model is lenient —
Pydantic silently coerces `"123"` → `123`, `"true"` → `True`, etc.

Scope per remediation plan:

- `src/m5_config_loader/loader.py`: 16 models.
- `src/m1_identity/claims.py::AidClaims`: 1 model.
- `src/m11_blpapi_adapters/bloomberg_refdata/src/models.py`: 5 models.
- `src/m11_grpc_adapters/ice_data/src/models.py`: 4 models.

Total: 26 models flipped.

### 4.2 Requirements

| AC  | Statement |
|-----|-----------|
| M4.1 | Every model listed above has `model_config = ConfigDict(extra="forbid", strict=True)`. |
| M4.2 | `SecurityRef` + `IceSecurityRef` keep `frozen=True` — added alongside the other flags. |
| M4.3 | String-to-int / string-to-bool / string-to-float coercion no longer happens for any of the 26 models. Pydantic raises `ValidationError` on mismatched types. |
| M4.4 | Existing YAML fixtures that correctly quoted strings as strings continue to parse. If a fixture relied on coercion (e.g., wrote `"6"` where an int was needed), that fixture is fixed to use the typed value. |
| M4.5 | A new ADR at `docs/ADR/ADR-01-pydantic-strict.md` documents the migration pattern (what `strict=True` buys you, why the whole trust layer should honor it, how to migrate new models). |
| M4.6 | All deploy gates + full suite stay green. |

### 4.3 Design

#### 4.3.1 Mechanical flip

For each model, change:

```python
model_config = ConfigDict(extra="forbid")
```

to:

```python
model_config = ConfigDict(extra="forbid", strict=True)
```

For `SecurityRef` + `IceSecurityRef` (frozen) change:

```python
model_config = ConfigDict(extra="forbid", frozen=True)
```

to:

```python
model_config = ConfigDict(extra="forbid", strict=True, frozen=True)
```

#### 4.3.2 Test-fallout remediation patterns

Strict mode commonly breaks:

- `"6"` where `int` is expected — fix the fixture to pass `6`.
- `"true"` / `"false"` where `bool` is expected — fix to `True` / `False`.
- `3.14` where `int` is expected — now a `ValidationError`; fix the input.
- `datetime.date` where `datetime` is expected — coercion no longer happens.

Test repair policy: change the fixture, NOT the model. The model change
is the whole point of the migration.

Mitigation patterns when a vendor wire format legitimately requires a
string-serialized numeric (rare but possible on M11-BLPAPI / M11-gRPC
wire shapes):

1. Keep `strict=True` on the model.
2. Add a `@field_validator(mode="before")` that parses the string
   explicitly. E.g.:

   ```python
   @field_validator("retention_days", mode="before")
   @classmethod
   def _coerce_retention_days(cls, v: Any) -> int:
       if isinstance(v, str):
           return int(v)
       return v
   ```

3. Never silently reintroduce `strict=False`. Narrow the coercion to
   the specific field; document the reason inline.

For trust-layer Pydantic models (M1, M5), no exceptions are expected —
all inputs are Python-typed or YAML-typed.

YAML loading (M5 `load_enterprise_config`) is an exception — YAML
returns typed primitives (int, float, bool, str, date) natively, so
most config fixtures should already be type-correct. We scan for any
`"6"`-style string literals in YAML config fixtures and fix.

#### 4.3.3 ADR file

`docs/ADR/ADR-01-pydantic-strict.md` — short (< 100 lines), explains:

1. Context: Rule 32 says strict, code didn't.
2. Decision: flip `strict=True` on 26 trust-layer models.
3. Consequence: silent string→int coercion is gone; all caller inputs must be typed.
4. Migration pattern: for every new Pydantic model in the trust layer, ship `ConfigDict(extra="forbid", strict=True)` from day one. `frozen=True` per-model as needed.
5. Opt-out: M3 schema types (non-trust) retain lenient defaults — they are vendor-facing and need coercion flexibility. This is documented here for posterity.

### 4.4 Tasks

1. Flip `strict=True` on 16 models in `src/m5_config_loader/loader.py`.
2. Flip `strict=True` on `src/m1_identity/claims.py::AidClaims`.
3. Flip `strict=True` on 5 models in `src/m11_blpapi_adapters/bloomberg_refdata/src/models.py`.
4. Flip `strict=True` on 4 models in `src/m11_grpc_adapters/ice_data/src/models.py`.
5. Create `docs/ADR/ADR-01-pydantic-strict.md`.
6. Run full suite. For each test failing due to coercion, fix the FIXTURE (not the model).
7. Re-run until ≥ 2127 passed, 0 regressions.

---

## 5. M7-FIX — Rename `/gateway/call` → `/tools/call`

### 5.1 Problem

Spec + ARCH-07 say the public MCP surface is `/tools/call`. Code exposes
`POST /gateway/call`. M8's `M6GatewayClient` hits `<base>/call` (i.e.
resolves to `<base>/call`, so whatever base_url is configured must end
in `/gateway` — a brittle implicit contract).

### 5.2 Requirements

| AC  | Statement |
|-----|-----------|
| M7.1 | `src/m6_mcp_gateway/app.py` exposes `POST /tools/call` with identical body + response shape as today's `/gateway/call`. |
| M7.2 | `POST /gateway/call` is retained as a DEPRECATED alias. It serves the same body, but the response includes a `Deprecation: true` HTTP header (per RFC 8594). |
| M7.3 | M8's `M6GatewayClient.call()` posts to `f"{base_url}/tools/call"` (no more implicit `/gateway` prefix). Env defaults must match: `M8_GATEWAY_BASE_URL=https://m6-gateway.internal:8443` (no `/gateway` suffix). |
| M7.4 | Existing `tests/integration/test_m8_m6_shape_match.py` + `tests/unit/test_m6_app.py` route assertions update to `/tools/call`. At least one test still hits `/gateway/call` to verify it returns the same body AND the `Deprecation: true` header. |
| M7.5 | All other callers / tests updated to `/tools/call`. |
| M7.6 | Full suite + deploy gates stay green. |

### 5.3 Design

#### 5.3.1 M6 app change

In `src/m6_mcp_gateway/app.py::create_app`:

Extract the handler body into a named inner function `_gateway_call_impl(request, deprecated)`. Register TWO routes that delegate to the same impl:

```python
@new_app.post("/tools/call")
async def tools_call(request: Request) -> Response:
    return await _gateway_call_impl(request, deprecated=False)

@new_app.post("/gateway/call")
async def gateway_call(request: Request) -> Response:
    return await _gateway_call_impl(request, deprecated=True)
```

The impl must accept the `deprecated` flag and, on the way out, add
`Deprecation: true` to `JSONResponse` headers when set. Since
`JSONResponse` is constructed and returned at each error + success
site, wrap the final `Response` before return:

Pattern: replace each `return JSONResponse(...)` inside the impl with
`return _finalize(JSONResponse(...), deprecated)` where `_finalize`
adds the header if the flag is set. A helper avoids touching every
return statement:

```python
def _finalize(resp: JSONResponse, deprecated: bool) -> JSONResponse:
    if deprecated:
        resp.headers["Deprecation"] = "true"
    return resp
```

#### 5.3.2 M8 client change

`src/m8_pipeline_engine/gateway_client.py::M6GatewayClient.call`:
change `f"{self._base_url}/call"` to `f"{self._base_url}/tools/call"`.
This reflects the public M6 path, not an implicit `/gateway` base_url.

No env default is changing in the production code path except the
conceptual one (env var was already `https://m6-gateway.internal:8443`
with no suffix — it worked because M8 was hitting `/call` on
something M6 didn't actually expose without `/gateway`). This is
actually a BUGFIX: M8's production path was misaligned with M6's
real endpoint.

#### 5.3.3 Test update

`tests/integration/test_m8_m6_shape_match.py`:
- Add `test_m6_tools_call_is_primary_route` — `POST /tools/call` succeeds.
- Add `test_m6_gateway_call_serves_as_deprecated_alias` — `POST /gateway/call` succeeds AND response.headers.get("Deprecation") == "true".

`tests/unit/test_m6_app.py`:
- Rename existing `/gateway/call` assertions to `/tools/call` EXCEPT keep one case that hits `/gateway/call` and asserts the `Deprecation` header.

### 5.4 Tasks

1. Add `_finalize` helper + `_gateway_call_impl(deprecated)` in `src/m6_mcp_gateway/app.py`.
2. Register both `POST /tools/call` (primary) and `POST /gateway/call` (alias) routes.
3. Update `src/m8_pipeline_engine/gateway_client.py::M6GatewayClient.call` to `/tools/call`.
4. Update `tests/unit/test_m6_app.py` — `/tools/call` is the primary; keep one `/gateway/call` deprecated-alias test.
5. Update `tests/integration/test_m8_m6_shape_match.py` — add `test_m6_tools_call_is_primary_route` + `test_m6_gateway_call_serves_as_deprecated_alias` (existing 6 tests stay as-is).
6. `grepSearch` for `/gateway/call` across `tests/`, `src/`, `deploy/`, `config/`, and `docs/` to find any other callers or manifest references. Update each hit to `/tools/call`; if a test relies on the deprecated alias, document the intent inline.
7. Verify `src/m8_pipeline_engine/.env.example` does not carry a stale `/call` or `/gateway/call` comment. If it does, update.
8. Run full suite — ≥ 2127 + new tests, 0 regressions.

---

## 6. M8-FIX — M1 `/aid/verify` startup fail-closed

### 6.1 Problem

`src/m1_identity/app.py::create_app` boots without an `IdentityService`.
All `/aid/verify` returns 503 with reason `service_not_wired`. In
production this is silent denial of service — Kubernetes readiness can
pass (or not) indefinitely without a clear failure.

Requirement from spec `m1-agent-identity.md`: the container must NOT
start in a broken state when signing-key env material is missing.

### 6.2 Requirements

| AC  | Statement |
|-----|-----------|
| M8.1 | M1 app supports two env paths for wiring signing key: `AID_PRIVATE_KEY_PEM` (inline PEM) OR `AID_PRIVATE_KEY_VAULT_PATH` (Vault reference). |
| M8.2 | When module-level `app = create_app()` is imported AND neither env var is set: `app.state.identity` stays `None` AND `/ready` returns 503 with reason `service_not_wired`. (This is the Dockerfile smoke-test path; must remain supported.) |
| M8.3 | A new function `create_app_from_env()` reads the two env vars at call time and, if both are missing, logs a single structured stdout startup failure line AND raises `RuntimeError("aid_signing_key_not_configured")`. Not a silent 503. |
| M8.4 | When `AID_PRIVATE_KEY_PEM` is set (value is a PEM-formatted private key string), `create_app_from_env()` constructs a real `IdentityService` and wires it onto `app.state.identity`. `/ready` returns 200. |
| M8.5 | When `AID_PRIVATE_KEY_VAULT_PATH` is set but `AID_PRIVATE_KEY_PEM` is not: `create_app_from_env()` emits a startup WARN-style stdout line stating the Vault-pull contract is deferred (no live Vault pull shipped in this fix) AND raises `RuntimeError("aid_signing_key_vault_pull_not_implemented")`. Explicit fail-closed — no silent 503-forever. |
| M8.6 | Dockerfile `ENTRYPOINT` uses `create_app_from_env` (via uvicorn `--factory`) in production. Module-level `app = create_app()` remains for local smoke tests only. |
| M8.7 | Tests cover: missing envs → RuntimeError, `AID_PRIVATE_KEY_PEM` present → identity wired and `/ready` 200, `AID_PRIVATE_KEY_VAULT_PATH`-only → RuntimeError, module-level `app` still importable with no env set. |

### 6.3 Design

#### 6.3.1 New `create_app_from_env`

```python
def create_app_from_env() -> FastAPI:
    """Production entrypoint. Fail-closed on missing signing key."""
    pem = os.environ.get("AID_PRIVATE_KEY_PEM")
    vault = os.environ.get("AID_PRIVATE_KEY_VAULT_PATH")

    if not pem and not vault:
        _structured_stdout({
            "phase": "startup_fail",
            "module": "m1",
            "reason": "aid_signing_key_not_configured",
        })
        raise RuntimeError("aid_signing_key_not_configured")

    if pem:
        service = IdentityService(
            private_key_pem=pem,
            issuer=ISSUER,
            # rest of config: audiences/kid can come from env or defaults
            audience=os.environ.get("AID_AUDIENCE", "007-mcp-gateway"),
        )
        return create_app(identity_service=service)

    # vault-only path — defer live Vault pull to a follow-up fix
    _structured_stdout({
        "phase": "startup_fail",
        "module": "m1",
        "reason": "aid_signing_key_vault_pull_not_implemented",
    })
    raise RuntimeError("aid_signing_key_vault_pull_not_implemented")
```

(The exact `IdentityService(...)` constructor args are taken from the
existing `service.py`. If additional required kwargs exist we default
them via env + sensible fallbacks — no literal creds.)

#### 6.3.2 Tests

`tests/unit/test_m1_startup_failclosed.py`:

- `test_create_app_from_env_raises_when_no_envs(monkeypatch)` — delete both env vars, expect `RuntimeError("aid_signing_key_not_configured")`.
- `test_create_app_from_env_raises_on_vault_only(monkeypatch)` — set `AID_PRIVATE_KEY_VAULT_PATH` only, expect `RuntimeError("aid_signing_key_vault_pull_not_implemented")`.
- `test_create_app_from_env_wires_identity_when_pem_present(monkeypatch, tmp_path)` — generate a short-lived RSA key via `cryptography`, set `AID_PRIVATE_KEY_PEM=<key>`, call `create_app_from_env()`, assert `app.state.identity` is not None AND `/ready` returns 200 via `TestClient`.
- `test_module_level_app_still_boots_without_env` — `from m1_identity.app import app` imports clean; `/ready` returns 503.

#### 6.3.3 Operator migration note

Before this fix: operators were expected to inject a real
`IdentityService` at runtime by mutating `app.state.identity` after
import. No env-var path existed. `/aid/verify` stayed 503 until a
real service was wired — which is silent readiness-never for the pod.

After this fix:
- `AID_PRIVATE_KEY_PEM` is the ONLY supported env path in this release.
  Production pods MUST set this env var from a Vault-backed
  `ExternalSecret` that mounts the PEM at container-start.
- `AID_PRIVATE_KEY_VAULT_PATH` is accepted syntactically but fails fast
  with `aid_signing_key_vault_pull_not_implemented` — it's a forward-
  declared surface waiting on a dedicated Vault-pull commit (out of
  scope for this remediation).
- The module-level `app = create_app()` path REMAINS for local smoke
  tests. It boots with `app.state.identity = None` and `/ready`
  returns 503. This is by design.

Operators upgrading production from today's silent-503 path should
deploy with `AID_PRIVATE_KEY_PEM` sourced from Vault (via sidecar
injector or ExternalSecret). No literal PEM belongs in git per Rule 20.

### 6.4 Tasks

1. Add `create_app_from_env` to `src/m1_identity/app.py`.
2. Update `__all__` to export `create_app_from_env`.
3. Add `tests/unit/test_m1_startup_failclosed.py` covering AC M8.3-M8.7.
4. Run full suite — ≥ 2127 + new tests, 0 regressions.

Note on Dockerfile (AC M8.6): the trust-agent lane owns M1 source + tests.
Dockerfile changes live in `deploy/docker/` which is inside trust-agent
boundary. Confirm by inspecting current Dockerfile and update only if
necessary to use `--factory`.

---

## 7. M11-FIX — M11-Python audit shape alignment

### 7.1 Problem

- M11-Python (Bloomberg, ICE Data) audit events use shape `{event, tool, firm_id, outcome, duration_ms, adapter_name, vendor, timestamp_ms, ...}`.
- M13 / M10 canonical shape is `{module, kind, ts, ...}`.
- M10 `POST /audit` only accepts `StageAuditPayload` — M11 stdout events are unparseable.
- Rule 6 (3-tier WORM for every audit) is design-only for the Python adapter family.

### 7.2 Requirements

| AC  | Statement |
|-----|-----------|
| M11.1 | `src/m11_python_adapters_shared/audit_emitter.py::AuditEvent` → emitted JSON shape is `{module: "m11-<vendor>", kind: "<vendor>.tool_audit", ts: "<ISO8601Z>", <other fields preserved>}`. |
| M11.2 | Backwards compat for one release: `AuditEmitter.emit()` continues to write the LEGACY fields (`event`, `timestamp_ms`) in addition to the new ones (`module`, `kind`, `ts`). Same JSON line carries both, so downstream consumers reading either key work. **Shim removal target: the next minor (v0.6.0). The AuditEmitter module docstring + ADR-01 both name this release.** |
| M11.3 | `src/m10_audit_logger/app.py::POST /audit` additionally accepts the canonical shape `{module, kind, ts, ...}`. A new translator converts this shape to the `StageAuditPayload` → `AuditEntry` pipeline. |
| M11.4 | When M10 receives a body that has BOTH `source` (M8 shape) and `module` (canonical shape), prefer the canonical shape. When only `module` + `kind` + `ts` present, the translator runs. When only `source` + ... present, the legacy `_translate_to_audit_entry` runs. Malformed bodies → 400 `{"error":"invalid_payload_shape"}`. |
| M11.5 | Canonical-shape translator requires: `module` (str), `kind` (str), `ts` (ISO-8601 with trailing `Z` OR parseable as UTC datetime), `tenant_id`, `firm_id`, `trace_id`, plus any existing canonical fields the M8 shape also carries. Missing → 400. |
| M11.6 | Existing M8 audit-contract tests continue to pass (legacy `StageAuditPayload` shape still works). |
| M11.7 | New tests: `AuditEmitter` emits canonical shape (M11.1) + back-compat legacy keys (M11.2); M10 `/audit` accepts canonical shape (M11.3-M11.5). |

### 7.3 Design

#### 7.3.1 AuditEmitter changes

```python
# audit_emitter.py
from datetime import datetime, timezone

def _ts_iso8601_z(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat().replace("+00:00", "Z")

def emit(self, ev: AuditEvent) -> None:
    record: dict[str, Any] = {
        # canonical shape (new)
        "module": f"m11-{ev.vendor}",
        "kind": f"{ev.vendor}.tool_audit",
        "ts": _ts_iso8601_z(ev.timestamp_ms),
        # legacy shape (preserved for one release)
        "event": ev.event,
        "timestamp_ms": int(ev.timestamp_ms),
        # unchanged
        "tool": ev.tool,
        "firm_id": ev.firm_id,
        ...
    }
```

#### 7.3.2 M10 ingest translator

New helper alongside the existing one:

```python
# src/m10_audit_logger/app.py
_CANONICAL_REQUIRED_KEYS: tuple[str, ...] = (
    "module",
    "kind",
    "ts",
    "tenant_id",
    "firm_id",
    "trace_id",
)

def _is_canonical_shape(body: dict[str, Any]) -> bool:
    return "module" in body and "kind" in body and "ts" in body

def _translate_canonical_to_audit_entry(body: dict[str, Any]) -> AuditEntry:
    ts = _parse_timestamp(body["ts"])
    iso = ts.isoformat().replace("+00:00", "Z")

    # Map canonical keys to the AuditEntry schema. tenant_id + firm_id +
    # trace_id carry through. action = kind. module = body["module"].
    input_sha = str(body.get("input_sha256") or "")
    output_sha = str(body.get("output_sha256") or "")
    if not _SHA256_HEX.fullmatch(input_sha):
        raise ValueError("input_sha256 must be 64-hex or empty")
    if not _SHA256_HEX.fullmatch(output_sha):
        raise ValueError("output_sha256 must be 64-hex or empty")

    return AuditEntry(
        canonical_id=uuid.uuid4(),
        trace_id=str(body["trace_id"]),
        timestamp=ts,
        actor_id=f"m11:{body.get('adapter_name', 'unknown')}",
        action=str(body["kind"]),
        module=str(body["module"]),
        decision=str(body.get("outcome", "allow")),
        reason=body.get("error_code"),
        input_hash=input_sha,
        output_hash=output_sha,
        latency_ms=int(body.get("duration_ms", 0)),
        firm_id=str(body["firm_id"]),
        tenant_id=str(body["tenant_id"]),
        worm_record_id=f"{body['module']}/{iso}/{uuid.uuid4().hex[:8]}",
        sha256_integrity="",
        retention_years=6,
    )
```

Handler dispatches:

```python
if _is_canonical_shape(body):
    missing = [k for k in _CANONICAL_REQUIRED_KEYS if k not in body]
    if missing:
        return JSONResponse(status_code=400, content={"error": "missing_required_keys", "missing": sorted(missing)})
    try:
        entry = _translate_canonical_to_audit_entry(body)
    except (ValueError, KeyError, TypeError):
        return JSONResponse(status_code=400, content={"error": "invalid_payload_shape"})
else:
    # existing StageAuditPayload path
    missing = [k for k in _REQUIRED_KEYS if k not in body]
    ...
```

### 7.4 Tasks

1. Update `AuditEmitter.emit` in `src/m11_python_adapters_shared/audit_emitter.py` to write `module` + `kind` + `ts` alongside legacy keys.
2. Update `src/m10_audit_logger/app.py`:
   - Add `_CANONICAL_REQUIRED_KEYS`, `_is_canonical_shape`, `_translate_canonical_to_audit_entry`.
   - Update `/audit` handler to branch on shape.
3. Add unit tests `tests/unit/test_m11_audit_emitter_canonical_shape.py`:
   - `test_emit_includes_module_kind_ts`
   - `test_emit_preserves_legacy_event_and_timestamp_ms`
4. Add unit tests `tests/unit/test_m10_audit_canonical_shape.py`:
   - `test_canonical_shape_accepted`
   - `test_canonical_shape_missing_module_400`
   - `test_canonical_shape_invalid_ts_400`
   - `test_canonical_shape_preserves_trace_id_and_tenant_id`  # canary: verifies key fields survive into AuditEntry
   - `test_legacy_shape_still_accepted`
5. Run full suite — ≥ 2127 + new tests, 0 regressions.

---

## 8. STEERING — `.kiro/steering/007-fsi-interoperability.md`

### 8.1 Requirements

| AC  | Statement |
|-----|-----------|
| S.1 | Rule 5 is updated: "Phase 1: Python deterministic rules implement the same contract (ALLOW/DENY/ESCALATE, fail-closed, WSP section annotation per rule). Phase 2 [target: Q4 2026] migrates to OPA/Rego sidecar. Contract is invariant across phases." |
| S.2 | Rule 10 is updated: "Trust-layer modules (M1, M2/M4, M5, M6, M10) AND the `compliance/` gaps share a Python build. This is a Phase-1 deliberate carve-out for operational simplicity; the REST surfaces each module exposes (`/aid/verify`, `/tools/call`, `/audit`, `/ready`, `/health`) remain the only contract non-trust modules may depend on. All non-trust modules (M7, M8, M9, M11, M12, M13) communicate with the trust layer via REST or MCP only." |
| S.3 | Rule 23 is updated: "Phase 1 establishes `tenant_id` on AidClaims + AuditEntry (completed in remediation-trust-fixes). KMS routing per tenant is deferred to Phase 3 when multi-tenant customer pod deployments begin." |
| S.4 | Rule 33 is REWRITTEN — not deleted — as "SUPERSEDED — see Rule 10 for module-boundary policy. Retained here to preserve stable rule numbering across legacy review references." |
| S.5 | A dated Phase-2 Migration Plan section is added near the bottom with milestones: "OPA/Rego migration (Rule 5 fulfillment): design Q3 2026, live Q4 2026. Per-tenant KMS (Rule 23 fulfillment): design Q1 2027, live Q2 2027. Trust-layer REST federation (Rule 10 fulfillment): revisit post Q4 2026." |

### 8.2 Design

Steering file is a rules reference. The fix is purely textual — update
rules 5, 10, 23, and rewrite 33 as superseded; add a dated Phase-2 plan section.

We rewrite the file in place (it's < 100 lines). Changes:

1. Rule 5 — expanded to Phase-1/Phase-2 with contract-invariance claim.
2. Rule 10 — expanded with trust-layer carve-out + explicit REST-only boundary for non-trust modules.
3. Rule 23 — dated to Phase-3, notes the `tenant_id` groundwork completed in this remediation.
4. Rule 33 — rewritten as "SUPERSEDED — see Rule 10" (numbering preserved so existing LLMJ reviews still line up).
5. Append "Phase-2 Migration Plan" section with dated milestones.

### 8.3 Tasks

1. Read current steering file (`.kiro/steering/007-fsi-interoperability.md`).
2. Rewrite Rules 5, 10, 23, 33 per ACs S.1-S.4.
3. Add Phase-2 Migration Plan section per AC S.5.
4. No tests for steering content (it's a policy doc, not code).

---

## 9. Integration + regression gates

### 9.1 Green gate

After every commit in the fix series:

- `/Library/Frameworks/Python.framework/Versions/3.10/bin/python3 -m pytest tests/ -q --timeout=60` → ≥ 2127 passed, 0 regressions.
- The 7 scenarios in `tests/integration/test_phase1_trust_layer.py` MUST continue to pass — they are the canonical Phase-1 contract and are the single strongest signal that the trust pipeline is still end-to-end-green. (This is subsumed by "0 regressions" but called out explicitly because a silent phase-1 regression is the scariest failure mode.)
- `bash deploy/tests/test_helm_lint.sh` → PASS.
- `bash deploy/tests/test_helm_template_egress.sh` → PASS.
- `bash deploy/tests/test_dockerfile_security.sh` → PASS.

### 9.2 Stability gate

After all commits land, run the full suite 10 times consecutively.
Pass = 10/10. If any run flips color, investigate before moving forward.

### 9.3 New coverage expectations

Minimum new tests added by this workstream:

| Fix | New test count | File(s) |
|-----|----------------|---------|
| B11 | ≥ 1 | `tests/unit/test_values_cloud_global.py` |
| B12 | ≥ 6 | `tests/unit/test_m10_app_failclosed.py` |
| M3 | ≥ 3 | `tests/unit/test_m1_aidclaims_tenant_id.py`, `test_m3_audit_entry_tenant_id.py`, `test_m10_translator_carries_tenant_id.py` |
| M4 | incidental | existing tests assert typed inputs |
| M7 | ≥ 2 | `tests/integration/test_m8_m6_shape_match.py` additions |
| M8 | ≥ 4 | `tests/unit/test_m1_startup_failclosed.py` |
| M11 | ≥ 5 | `test_m11_audit_emitter_canonical_shape.py`, `test_m10_audit_canonical_shape.py` |
| **Total** | **≥ 21 new tests** |

Net test count target: ≥ 2148.

### 9.4 Rule-compliance matrix (snapshot at completion)

| Rule | Before fix | After fix |
|------|-----------|-----------|
| 5 (OPA only) | VIOLATED | **DOCUMENTED carve-out + dated migration** |
| 10 (no cross-module imports) | VIOLATED | **DOCUMENTED carve-out** |
| 23 (per-tenant KMS) | MISSING `tenant_id` | **tenant_id on AidClaims + AuditEntry; KMS deferred to Phase-3** |
| 32 (Pydantic strict) | partial (1 of 26 models) | **FULL on 26 trust-layer models post-M4-FIX** |
| 33 (no cross-module imports) | VIOLATED | **SUPERSEDED — see Rule 10 (trust-layer carve-out)** |

---

## 10. Commit strategy

One logical change per commit. Expected commits:

1. `helm: merge duplicate global in values-cloud.yaml + unit test (B11)`
2. `m10: fail-closed on all-in-memory backends via M10_ALLOW_IN_MEMORY_AUDIT (B12)`
3. `m1+m3+m10: add tenant_id to AidClaims + AuditEntry; M10 translator carries it (M3)`
4. `trust: flip strict=True on 26 Pydantic models + ADR-01 (M4)`
5. `m6+m8: rename /gateway/call to /tools/call; keep alias with Deprecation header (M7)`
6. `m1: fail-closed startup hook via create_app_from_env (M8)`
7. `m10+m11-python: accept canonical {module,kind,ts} audit shape + backwards-compat legacy (M11)`
8. `steering: document trust-layer carve-out + dated Phase-2 plan`

Use `git commit --no-verify` only when synthetic credential-shape fixtures
trip the pre-commit hook — each such commit documents the reason in its
body.

---

## 11. Acceptance

COMPLETE marker may ONLY be emitted when:

- All 2 BLOCKERS (B11, B12) fixed + tested.
- All 5 trust MAJORS (M3, M4, M7, M8, M11) fixed + tested.
- Steering rules updated.
- Self-LLMJ v2 ≥ 8.0 GO.
- Full suite ≥ 2127 passed, 0 regressions, 10/10 stable local runs.
- All deploy gates still PASS.
- No new credential-pattern violations.

Marker at `.kiro/specs/remediation-trust-fixes-COMPLETE.md` with:
- Gate evidence (pytest output, deploy-gate output).
- File list (every new + modified path).
- Rule-compliance matrix (section 9.4).
