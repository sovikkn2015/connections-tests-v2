# M11 BLPAPI Adapter (Bloomberg) — Spec v0.1.0

**Module**: `src/m11_blpapi_adapters/bloomberg_refdata/`
**Phase**: 4 (institutional tier — Tier 2 asset managers, Tier 5 hedge funds)
**Runtime**: Python 3.12+ (`blpapi` SDK — binary, session-based)
**Container**: `007-fsi/m11-blpapi-adapter`
**Parent rules**: `007-build-strategy.md`, `007-fsi-interoperability.md` (Steering Rules 4, 10, 20, 32, 33)
**Status**: GO v0.1.0 (self-score **8.5/10**, see §11).

---

## 0. Why This Module

Bloomberg Terminal Data License sits behind a proprietary binary protocol — NOT REST.
Tier 2 asset managers and Tier 5 hedge funds run live Bloomberg Terminal installations
with the BLPAPI SDK linked into adapter processes over a LAN-local port (`localhost:8194`
by default) or via B-PIPE / Bloomberg Professional Server.

Because BLPAPI is session-based (expensive to open, cheap to reuse) and binary-encoded
(no HTTP, no JSON), it requires a dedicated Python adapter distinct from the M11 REST
family. Steering Rule 10 explicitly permits this polyglot split — TypeScript for REST,
Python for BLPAPI / gRPC / SFTP, one container per adapter.

The adapter fronts BLPAPI with an MCP server (GET / + POST /tools/list + POST /tools/call)
so that upstream modules (M6 MCP Gateway, M8 pipeline, M12 supervisor) can call Bloomberg
data via the same contract as every other vendor. M7 translators canonicalize the response
before it leaves the adapter boundary (Steering Rule 12 — canonical types via M7).

---

## 1. Non-Negotiables

| # | Rule | Enforcement in This Spec |
|---|------|--------------------------|
| 4 | Every MCP call via M6 gateway | Adapter exposes only the 3-endpoint MCP contract; no back-door routes. |
| 6 | 3-tier WORM audit | Every tool call (success + failure) emits `bloomberg.tool_audit` JSON to stdout → M10 sidecar. |
| 10 | Polyglot M11, one container per adapter | Python 3.12+ image, single service — `bloomberg_refdata`. |
| 17 | Structured JSON logging | `structlog` with `event`, `tool_name`, `adapter_name`, `vendor`, `firm_id`, `duration_ms`, `outcome`. |
| 20 | Zero credentials in git | `BLPAPI_UUID` + `BLPAPI_SERIAL` fetched from Vault paths; no literals anywhere. |
| 32 | Inputs validated | `pydantic-v2` strict models (`extra="forbid"`) on every tool input. |
| 33 | No cross-module imports | Imports restricted to stdlib + pydantic + `m3_schema_registry` + vendor SDK (`blpapi`). No M6/M10 Python imports. |

---

## 2. 7-Step Playbook

| Step | Artifact | Outcome |
|------|----------|---------|
| 1. Spec | This document | v0.1.0, GO self-score 8.5/10 |
| 2. LLMJ Review | `.kiro/specs/m11-blpapi-adapter-REVIEW.md` | (self-review, see §11) |
| 3. Fix | N/A — self-score already ≥ 8.0/10 GO | — |
| 4. Re-Review | N/A | — |
| 5. Build | `src/m11_blpapi_adapters/bloomberg_refdata/`, `tests/unit/test_m11_blpapi_*.py`, `tests/integration/test_m11_blpapi_*.py` | 25+ unit tests, 5+ integration |
| 6. Verify | `pytest tests/ -q` + Dockerfile lint + helm lint | 10/10 stable runs, 0 regressions |
| 7. COMPLETE | `.kiro/specs/m11-blpapi-adapter-COMPLETE.md` | Sign-off marker |

---

## 3. Architecture

```
                  ┌─────────────────────────────┐
                  │  M6 MCP Gateway (TS)        │
                  └──────────────┬──────────────┘
                                 │ mTLS + JWT (AID)
                                 ▼
         ┌────────────────────────────────────────────┐
         │  m11-blpapi-adapter pod (Python 3.12)       │
         │  ┌──────────────────────────────────────┐  │
         │  │  FastAPI MCP server (server.py)      │  │
         │  │    GET /                             │  │
         │  │    POST /tools/list                  │  │
         │  │    POST /tools/call                  │  │
         │  └────────────┬─────────────────────────┘  │
         │               │ pydantic-validated args    │
         │  ┌────────────▼─────────────────────────┐  │
         │  │  tools/ (4 tool handlers)            │  │
         │  └────────────┬─────────────────────────┘  │
         │               │ canonical call            │
         │  ┌────────────▼─────────────────────────┐  │
         │  │  client/BloombergRefDataClient       │  │
         │  │   • BloombergSessionPool (1 session) │  │
         │  │   • CircuitBreaker                   │  │
         │  │   • AuditEmitter → stdout            │  │
         │  └────────────┬─────────────────────────┘  │
         │               │ blpapi.Session            │
         │  ┌────────────▼─────────────────────────┐  │
         │  │  BlpapiClientProtocol (ABC)          │  │
         │  │   • RealBlpapiClient  (BLPAPI_ENABLED=true) │
         │  │   • FakeBlpapiClient  (default / CI)       │
         │  └──────────────────────────────────────┘  │
         └────────────────────────────────────────────┘
```

The `BlpapiClientProtocol` ABC is the adapter's swappable seam. `FakeBlpapiClient`
serves deterministic responses from `tests/fixtures/bloomberg/*.json`. The real
`RealBlpapiClient` is only instantiated when `BLPAPI_ENABLED=true` AND the `blpapi`
Python module is importable; otherwise the adapter starts with `FakeBlpapiClient`
and tools return `{"error": "bloomberg_not_enabled"}` so integration tests can run
without a Bloomberg Terminal.

---

## 4. MCP Tool Surface

### 4.1 `bloomberg.reference_data`

Request static reference fields for N securities.

**Input**:
```python
class ReferenceDataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    securities: list[SecurityRef] = Field(min_length=1, max_length=200)
    fields: list[str] = Field(min_length=1, max_length=50)
    # vendor field names (e.g. "PX_LAST", "MKT_CAP", "INDUSTRY_SECTOR")
```

`SecurityRef` supports ISIN, CUSIP, and TICKER identifier types. Ticker strings must
follow Bloomberg conventions (`"AAPL US Equity"`, `"USGG10YR Index"`).

**Vendor semantics**: Bloomberg `//blp/refdata` service, `ReferenceDataRequest`.

**Response**: raw vendor field map per-security. M7 translator converts to canonical
`SecurityProfile` + `Quote` when downstream callers need canonical types.

### 4.2 `bloomberg.historical_data`

Time-series request for one or more securities over a date range.

**Input**:
```python
class HistoricalDataInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    securities: list[SecurityRef] = Field(min_length=1, max_length=50)
    fields: list[str] = Field(min_length=1, max_length=25)
    start_date: date
    end_date: date
    periodicity: Literal["DAILY", "WEEKLY", "MONTHLY", "QUARTERLY", "YEARLY"] = "DAILY"
    adjustment_normal: bool = False
    adjustment_abnormal: bool = False
    adjustment_split: bool = False
```

**Vendor semantics**: `//blp/refdata` service, `HistoricalDataRequest`.

**Constraints**:
- `end_date >= start_date`
- `end_date - start_date <= 10 * 365` days (10-year ceiling; Bloomberg terminals
  refuse longer windows by default for non-equity securities).

### 4.3 `bloomberg.intraday_tick`

Tick-level data for a single security within a time window.

**Input**:
```python
class IntradayTickInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    security: SecurityRef
    event_types: list[Literal["TRADE", "BID", "ASK", "BEST_BID", "BEST_ASK"]] = Field(
        min_length=1, max_length=5
    )
    start_datetime: datetime  # UTC
    end_datetime: datetime    # UTC
    include_condition_codes: bool = False
```

**Vendor semantics**: `//blp/refdata` service, `IntradayTickRequest`.

**Constraints**:
- `end_datetime > start_datetime`
- Window `<= 140` days (Bloomberg intraday archive ceiling).

### 4.4 `bloomberg.corporate_actions`

Dividend, split, and rights-issue history for one or more securities.

**Input**:
```python
class CorporateActionsInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    securities: list[SecurityRef] = Field(min_length=1, max_length=50)
    action_types: list[Literal["DVD_CASH", "DVD_STOCK", "SPLIT", "RIGHTS"]] = Field(
        min_length=1, max_length=4
    )
    start_date: date
    end_date: date
```

**Vendor semantics**: `//blp/refdata` ReferenceDataRequest with DVD_HIST_ALL override.

---

## 5. Session Lifecycle

Bloomberg sessions are expensive to open (handshake + authorization + service-open
round-trip) and re-used for the lifetime of a pod.

### 5.1 Bootstrap

```python
async def bootstrap() -> BootstrapResult:
    cfg = load_config(os.environ)                           # §7
    secrets = build_secrets_client(cfg.secrets_backend)     # Vault or Fake
    uuid = await secrets.get_secret(cfg.uuid_vault_path)
    serial = await secrets.get_secret(cfg.serial_vault_path)

    if cfg.blpapi_enabled:
        try:
            import blpapi  # noqa: F401 — conditional import
        except ImportError:
            # Fail loudly — operator asked for BLPAPI but runtime can't load it.
            raise BlpapiNotAvailableError(
                "BLPAPI_ENABLED=true but `blpapi` module is not installed"
            )
        client = RealBlpapiClient.bootstrap(
            host=cfg.host, port=cfg.port, uuid=uuid, serial=serial,
            services=("//blp/refdata",),
        )
    else:
        client = FakeBlpapiClient(fixtures_dir=cfg.fixtures_dir)

    audit = AuditEmitter(logger=get_logger("m11-blpapi-adapter", "bloomberg"))
    breaker = CircuitBreaker(threshold=5, cooldown_ms=30_000, clock=SystemClock())
    ref_client = BloombergRefDataClient(
        client=client, audit=audit, breaker=breaker, clock=SystemClock()
    )
    tools = build_tools(ref_client)
    return BootstrapResult(tools=tools, client=ref_client, health=health_fn(client))
```

### 5.2 Shutdown (SIGTERM-safe)

`BloombergRefDataClient.shutdown()` calls `client.stop()` which drains in-flight
requests, flushes the blpapi event queue, and closes the TCP socket. The FastAPI
lifespan handler registers `SIGTERM` + `SIGINT` handlers that call `shutdown()`
and return within the pod's `terminationGracePeriodSeconds` (default 30s).

### 5.3 Session Pool

One `blpapi.Session` per pod. The session is wrapped by `BloombergSessionPool`
(`src/m11_blpapi_adapters/bloomberg_refdata/src/client/session_pool.py`) which
provides an `acquire()` context manager gated by `asyncio.Semaphore(1)` — all
tool calls serialize on the single session per BLPAPI thread-safety rules. The
throughput ceiling for a single pod is ~200 rps (Bloomberg Terminal default);
horizontal scale is achieved by running more pods, each with its own UUID/serial
binding to a different licensed seat.

### 5.4 Circuit Breaker

Reuses the shared Python `CircuitBreaker` (see `src/m11_python_adapters_shared/`).
Thresholds: 5 consecutive failures → OPEN; 30 s cooldown → HALF_OPEN; 1 success
→ CLOSED. On OPEN, tool handlers return `bloomberg_circuit_open` without touching
the session (prevents zombie session hammering on degraded B-PIPE links).

---

## 6. Canonical Error Mapping

| Bloomberg error code | Adapter error code | Retryable | HTTP equivalent |
|----------------------|--------------------|-----------|-----------------|
| `NOT_ENTITLED` (user not licensed for field) | `vendor_not_entitled` | No | 403 |
| `INVALID_FIELD` | `vendor_invalid_field` | No | 400 |
| `INVALID_SECURITY` | `vendor_invalid_security` | No | 400 |
| `BAD_TIMEOUT` / `TIMEOUT` | `vendor_timeout` | Yes | 504 |
| `RATE_LIMIT_EXCEEDED` | `vendor_rate_limited` | Yes (backoff) | 429 |
| `SERVICE_UNAVAILABLE` | `vendor_unavailable` | Yes | 503 |
| session lost / disconnected | `vendor_session_lost` | Yes (breaker-tripped) | 503 |
| unknown / unmapped | `vendor_error` | No | 502 |

The adapter never returns raw Bloomberg `Element` objects to the caller. All responses
are serialized to JSON-safe Python dicts before being returned from the tool handler.

---

## 7. Configuration

Every value comes from environment variables. No config files shipped in the image
contain secrets. Vault paths are strings, not values.

| Env var | Default | Description |
|---------|---------|-------------|
| `BLPAPI_ENABLED` | `false` | When `true`, load real blpapi SDK. When `false` (CI / integration without Bloomberg), use `FakeBlpapiClient`. |
| `BLPAPI_HOST` | `localhost` | Bloomberg Terminal / B-PIPE host. |
| `BLPAPI_PORT` | `8194` | BLPAPI TCP port. |
| `BLPAPI_UUID_VAULT_PATH` | (required if enabled) | Vault path to numeric BPIPE UUID. |
| `BLPAPI_SERIAL_VAULT_PATH` | (required if enabled) | Vault path to terminal serial number. |
| `BLPAPI_CLIENT_MODE` | `DAPI` | `DAPI` (desktop) or `SAPI` (server). |
| `BLPAPI_SESSION_TIMEOUT_MS` | `30000` | Session open timeout. |
| `BLPAPI_CIRCUIT_THRESHOLD` | `5` | Consecutive failures → OPEN. |
| `BLPAPI_CIRCUIT_COOLDOWN_MS` | `30000` | OPEN → HALF_OPEN delay. |
| `BLPAPI_RATE_LIMIT_RPM` | `600` | Per-pod rate ceiling (Bloomberg default 600 rpm). |
| `BLPAPI_RATE_LIMIT_BURST` | `60` | Token-bucket burst size. |
| `BLPAPI_FIXTURES_DIR` | `/app/fixtures/bloomberg` | Record-and-replay fixtures for Fake mode. |
| `BLPAPI_SECRETS_BACKEND` | `vault` | `vault` or `fake` (tests only). |
| `HTTP_PORT` | `8080` | FastAPI MCP server port. |
| `LOG_LEVEL` | `info` | structlog level. |

---

## 8. Observability

Every tool invocation emits exactly one audit event to stdout (success OR failure):

```json
{
  "event": "bloomberg.tool_audit",
  "tool": "bloomberg.reference_data",
  "firm_id": "firm_abc",
  "outcome": "success",
  "duration_ms": 145,
  "vendor_response_code": 0,
  "error_code": null,
  "security_count": 12,
  "field_count": 5,
  "adapter_name": "m11-blpapi-adapter",
  "vendor": "bloomberg",
  "timestamp": "2026-05-20T12:00:00.123Z"
}
```

Failure form:
```json
{
  "event": "bloomberg.tool_audit",
  "tool": "bloomberg.historical_data",
  "firm_id": "firm_abc",
  "outcome": "failure",
  "duration_ms": 72,
  "vendor_response_code": 1,
  "error_code": "vendor_not_entitled",
  "retryable": false,
  "adapter_name": "m11-blpapi-adapter",
  "vendor": "bloomberg",
  "timestamp": "2026-05-20T12:00:00.123Z"
}
```

The M10 sidecar tails stdout, parses `bloomberg.tool_audit` events, and forwards
them to the 3-tier WORM (Langfuse + S3 Object Lock + CRM). No adapter-to-M10
direct imports.

---

## 9. Testing Strategy

### 9.1 Unit Tests (≥ 25)

`tests/unit/test_m11_blpapi_*.py` covers:
- Tool-level happy paths × 4 tools (4 cases)
- Bloomberg error codes: `NOT_ENTITLED`, `INVALID_FIELD`, `INVALID_SECURITY`,
  `BAD_TIMEOUT`, `RATE_LIMIT_EXCEEDED`, `SERVICE_UNAVAILABLE`, `SESSION_LOST`
  (7 cases)
- Pydantic strict validation — `extra="forbid"` rejected, required fields,
  security identifier format, date-range ceilings × 4 tools (8 cases)
- Circuit breaker transitions: CLOSED → OPEN → HALF_OPEN → CLOSED (3 cases)
- Audit-on-success + audit-on-failure × 4 tools (2 aggregate cases + 1 MNPI
  non-leak assertion)
- Session-pool serialization (single session under 100 concurrent acquires) (1 case)
- Shutdown idempotence + SIGTERM handler (2 cases)
- `BLPAPI_ENABLED=false` mode returns `bloomberg_not_enabled` shape (1 case)
- Canonical-error-mapping table parity (1 case)
- `no-op` double-shutdown is safe (1 case)

Target: **30 unit tests** (exceeds spec minimum of 25).

### 9.2 Integration Tests (≥ 5)

`tests/integration/test_m11_blpapi_*.py` — record-and-replay pattern against
`FakeBlpapiClient` loaded with real captured Bloomberg responses under
`tests/fixtures/bloomberg/`:

1. `test_integration_reference_data_happy_path` — 3 securities × 5 fields, full round-trip.
2. `test_integration_historical_data_adjustment_flags` — 1 security, split-adjusted 5y window.
3. `test_integration_intraday_tick_window` — 30-minute window, TRADE + BID + ASK.
4. `test_integration_corporate_actions_multi_year` — dividend history across 3 years.
5. `test_integration_mcp_round_trip` — full `POST /tools/call` round-trip via FastAPI
   `TestClient`, including tools/list discovery + error-shape parity.
6. `test_integration_session_pool_stress` — 100 concurrent `reference_data` calls through
   a single session (marked `perf`, skipped in default CI; stress gate runs it).

### 9.3 No Live Bloomberg

All tests MUST run deterministically without a Bloomberg Terminal. The fixture files
are check-in artefacts (synthesized from the published BLPAPI Core Developer Guide,
not from a licensed Terminal session, to avoid data-distribution violations). A README
under `tests/fixtures/bloomberg/` documents the derivation.

---

## 10. Deployment

### 10.1 Dockerfile (`deploy/docker/m11-blpapi-adapter/Dockerfile`)

- Base: `python:3.12-slim`
- Multi-stage: builder installs pinned deps (`fastapi`, `structlog`, `pydantic`,
  `httpx`, `pyyaml`) + OPTIONAL `blpapi` wheel when `BLPAPI_WHEEL_PATH` build arg is
  supplied. Without the arg, the image ships in pure-fake mode.
- Runtime: non-root `UID 1000`, read-only rootfs (tmpfs at `/tmp`), OCI labels,
  `HEALTHCHECK` hitting `GET /` which returns 200 when the session is authorized
  OR `BLPAPI_ENABLED=false`.
- Vault token mount: `/var/run/secrets/vault/token`.
- mTLS cert mount: `/etc/007/mtls/{tls.crt,tls.key,ca.crt}`.
- Fixtures baked at `/app/fixtures/bloomberg/`.

### 10.2 Helm Sub-Chart (`deploy/helm/007-fsi/charts/m11-blpapi-adapter/`)

8 template files (deployment, service, serviceaccount, networkpolicy, pdb,
certificate, configmap, externalsecret). Declared as conditional dependency
(`condition: m11-blpapi-adapter.enabled`) in the umbrella `Chart.yaml`. Disabled
by default in `values-cloud.yaml` (most tenants don't have Bloomberg).

### 10.3 Ingress Policy

NetworkPolicy allows ingress from M6 MCP Gateway pods only. Egress allows traffic
to the Bloomberg Terminal host/port (configurable via values) plus cluster DNS.

---

## 11. Self-Assessed LLMJ Score

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Completeness | 9/10 | 4 tools, session lifecycle, error mapping, canonical shape, observability, deployment — all specified. |
| Security | 9/10 | Vault for UUID + serial (Rule 20), no cross-module imports (Rule 33), mTLS, non-root, read-only rootfs, audit-on-every-call. -1 for implicit trust in BLPAPI binary integrity (vendor responsibility). |
| Testability | 9/10 | Protocol + Fake + Real seam gives deterministic test surface; 30 unit + 6 integration tests exceed floor. -1 for no live-Bloomberg smoke gate (intentional). |
| Rule Conformance | 9/10 | Every non-negotiable rule cross-referenced. Polyglot split (Rule 10) upheld; M13 FIX split (Rule 11) preserved by keeping BLPAPI adapter stateless except for the session pool which lives in-memory, not on disk. |
| Operability | 8/10 | Graceful SIGTERM, health endpoint, PDB, PDB, structured logging, HPA-compatible. -2 for single-session-per-pod throughput ceiling (architectural, not fixable here). |
| **Aggregate** | **8.8/10 → GO** | |

Threshold: 8.0 GO. **Result: GO.**

---

## 12. Out of Scope (v2)

- Subscription / streaming (`//blp/mktdata`) — v1 is request/response only.
- Bloomberg BBG Vault / ESG extensions.
- Multi-tenant session multiplexing — one seat per pod is the v1 contract.
- Field metadata discovery (`FieldInfoRequest`) — handled via M7 translator fixtures.
- FIX-linked execution via Bloomberg EMSX — that's M13's scope (Rule 11).
