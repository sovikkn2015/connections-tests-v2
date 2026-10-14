# Trust Layer Audit: REAL vs MOCK — Brutally Honest Assessment

**Auditor**: M6 Gateway Specialist  
**Scope**: M1 (Identity), M2/M4 (Policy), M6 (Gateway), M10 (Audit), Integration Tests  
**Date**: Audit performed against current codebase

---

## 1. M1 IDENTITY (`src/m1-identity/`)

### Does `aid_service.py` actually call Keycloak?
**MOCK ONLY.** Keycloak is referenced in `docker-compose.yml` as a dependency and in the Dockerfile env var `KEYCLOAK_URL`, but **no code in `aid_service.py` or `app.py` ever calls Keycloak**. The `KEYCLOAK_URL` env var is set but never read by any Python code. M1 is a fully self-contained JWT issuer/verifier with no Keycloak integration.

### Does JWT verification use real RS256 crypto?
**REAL.** The `PyJWT` library (`jwt.encode` / `jwt.decode`) is used with `algorithm="RS256"`. The `entrypoint.py` generates a real RSA-2048 key pair using `cryptography.hazmat` when env vars are empty (dev mode). In production, real PEM keys would be injected via `M1_PRIVATE_KEY_PEM` / `M1_PUBLIC_KEY_PEM`. The crypto is genuine — not faked.

### Are AID tokens actually signed and verified?
**REAL.** `AIDService.issue()` calls `jwt.encode(payload, private_key, algorithm="RS256")` — real signing. `AIDService.verify()` calls `jwt.decode(token, public_key, algorithms=["RS256"], issuer=JWT_ISSUER)` — real verification with signature check, expiry check, and issuer validation.

### What happens when you call `/verify`?
**REAL CRYPTO.** The FastAPI endpoint in `app.py` calls `service.verify(request.token)` which performs real JWT RS256 decode, checks expiry, validates issuer, checks revocation in the registry, and extracts FSI claims. The LRU cache is in-memory (not Redis), but the crypto path is real.

### AID Registry (storage)?
**MOCK ONLY.** `AIDRegistry` is a Python `dict` in memory. Comment says "Production: PostgreSQL" but no PostgreSQL code exists. No database driver, no ORM, no SQL. Pure in-memory dict.

### Verify Cache?
**MOCK ONLY (dev-grade).** `VerifyCache` is an in-memory `OrderedDict` with thread-safe LRU. Comment says "Production: Redis" but no Redis code exists in M1. Functional for single-instance dev, not production-ready.

| Component | Classification |
|-----------|---------------|
| JWT RS256 signing | **REAL** |
| JWT RS256 verification | **REAL** |
| RSA key generation (dev) | **REAL** |
| Keycloak integration | **MOCK ONLY** (env var exists, zero code) |
| AID Registry (storage) | **MOCK ONLY** (in-memory dict) |
| Verify Cache | **MOCK ONLY** (in-memory, not Redis) |

---

## 2. M6 GATEWAY (`src/m6-mcp-gateway/`)

### Does `trust_pipeline.py` actually make HTTP calls to M1, M2, M4, M10?
**REAL (code path exists, will execute over HTTP).** Every module call (`_verify_identity`, `_check_authority`, `_filter_mnpi`, `_translate_response`, `_write_audit_log`) uses `httpx.AsyncClient` to make real HTTP POST requests to configurable URLs. No local function calls, no in-memory stubs. The URLs default to Docker service names (`http://m1-identity:8000`, etc.).

**CRITICAL GAP:** The `GatewayConfig` uses Pydantic `BaseModel` with hardcoded defaults — NOT `BaseSettings`. The docker-compose sets env vars like `M1_URL`, `M2_URL`, etc., but `GatewayConfig` never reads them. The config defaults to `http://m1-identity:8000` (port 8000) while docker-compose exposes M1 on port 8001. **This means docker-compose wiring is broken without manual config override.** The env vars are set but ignored.

### Does `mcp_proxy.py` actually forward MCP calls?
**REAL.** `MCPProxy.forward_mcp_call()` makes real `httpx.AsyncClient.post()` calls to `{server_url}/tools/call` with the MCP protocol payload. Full resilience pipeline (rate limit → circuit breaker → bulkhead → retry → timeout) wraps the call. This is genuine async HTTP forwarding.

### Does `resilience.py` have a real circuit breaker?
**REAL (with dual-mode state storage).**
- `CircuitBreaker` implements proper state machine: closed → open → half_open → closed.
- State transitions use `asyncio.Lock` for thread safety.
- `InMemoryCircuitBreakerStateStore` for dev (default).
- `RedisCircuitBreakerStateStore` for production — real Redis `HSET`/`HGETALL` with automatic fallback to in-memory if Redis is unavailable.
- `MCPProxy.__init__` selects Redis-backed or in-memory based on whether a Redis client is provided.

### Does `app.py` wire the trust pipeline into request handling?
**REAL.** The `/mcp/call` endpoint executes the full flow: pre-call pipeline → MCP forward → post-call pipeline. Fail-closed on any failure. Generic errors to client (Rule 9). The lifespan handler initializes `TrustPipeline`, attempts Redis connection, and creates `MCPProxy`.

### Rate Limiter?
**WIRED BUT DEV-MODE.** `RateLimiter` (in-memory sliding window) works correctly for single instance. `RedisRateLimiter` (sorted set sliding window) exists and uses real Redis commands (`ZRANGEBYSCORE`, `ZADD`, `ZREMRANGEBYSCORE`). Falls back to in-memory if Redis unavailable.

### Bulkhead Isolation?
**REAL.** `BulkheadRegistry` uses `asyncio.Semaphore` per server category. Functional and correct, though in-memory only (no cross-instance coordination).

| Component | Classification |
|-----------|---------------|
| HTTP calls to M1/M2/M4/M7/M10 | **REAL** (httpx async) |
| MCP forwarding to downstream | **REAL** (httpx async) |
| Circuit breaker state machine | **REAL** |
| Circuit breaker Redis state | **WIRED BUT DEV-MODE** (falls back to in-memory) |
| Rate limiter (in-memory) | **REAL** (single instance) |
| Rate limiter (Redis) | **WIRED BUT DEV-MODE** (falls back to in-memory) |
| Bulkhead isolation | **REAL** (asyncio.Semaphore) |
| Retry with backoff | **REAL** (tenacity) |
| Leakage scan Layer A (regex) | **REAL** (10+ MNPI patterns) |
| Leakage scan Layers B/C | **STUB** (returns pass, not_implemented) |
| Provenance chain SHA-256 | **REAL** (hashlib.sha256) |
| OpenTelemetry spans | **REAL** (tracer spans on every stage) |
| GatewayConfig env var loading | **BROKEN** (doesn't read docker-compose env vars) |

---

## 3. M2/M4 POLICY ENGINE (`src/m2-m4-policy-engine/`)

### Does `policy_client.py` actually call OPA server via HTTP?
**REAL (code path exists).** `_query_opa()` uses `httpx.AsyncClient` to POST to `{OPA_URL}/v1/data/{path}`. OPA_URL defaults to `http://localhost:8181` and is read from `os.environ.get("OPA_URL")`. In docker-compose, `OPA_URL=http://opa:8181` is set and **this env var IS actually read** (unlike M6's config).

### Does it use the local evaluator or OPA?
**CONFIGURABLE.** `app.py` checks `USE_LOCAL_EVALUATOR` env var at call time. Docker-compose sets `USE_LOCAL_EVALUATOR=false`, meaning **docker-compose mode uses real OPA HTTP calls**. Tests and standalone dev use the local evaluator.

### Is the local evaluator a real reimplementation?
**REAL (faithful mirror).** `evaluate_authority_local()` implements the same 5-rule logic as `opa-bundles/authority/main.rego`: excludes check → scope check → client scope → pod isolation → escalation → allow. `evaluate_mnpi_filter_local()` mirrors `opa-bundles/mnpi/main.rego`: client scope denial → pod isolation → PII stripping → tier-specific filtering. The logic is substantively equivalent, not a trivial stub.

### Does it enforce deny-by-default when OPA is unreachable?
**REAL.** `_query_opa()` returns `None` on `ConnectError`, `TimeoutException`, or any other exception. Both `evaluate_authority()` and `evaluate_mnpi_filter()` check for `None` and return DENY/strip-all responses. This is genuine fail-closed behavior.

### Are the OPA Rego policies real?
**REAL.** `opa-bundles/authority/main.rego` (160+ lines) and `opa-bundles/mnpi/main.rego` (200+ lines) contain substantive Rego rules with proper `wsp_section` annotations, helper functions, and test files. These are loaded by the OPA container via `--bundle /bundles` volume mount.

| Component | Classification |
|-----------|---------------|
| OPA HTTP calls | **REAL** (httpx, env-configurable) |
| Local evaluator (authority) | **REAL** (faithful Rego mirror) |
| Local evaluator (MNPI) | **REAL** (faithful Rego mirror) |
| Fail-closed on OPA unreachable | **REAL** |
| OPA Rego policies | **REAL** (substantive rules with tests) |
| USE_LOCAL_EVALUATOR toggle | **REAL** (env var checked at call time) |

---

## 4. M10 AUDIT LOGGER (`src/m10-audit-logger/`)

### Does `writers.py` actually call S3 with Object Lock?
**WIRED BUT DEV-MODE.** `WormWriter` has two paths:
- **Production path**: `self._s3.put_object(Bucket=..., ObjectLockMode="COMPLIANCE", ObjectLockRetainUntilDate=..., ChecksumAlgorithm="SHA256")` — real boto3 S3 call with Object Lock Compliance mode and 6-year retention. Includes leap-year-safe date calculation.
- **Dev path**: `self._store[key] = json.loads(body)` — in-memory dict.
- **Which runs?** `s3_client` is injected via constructor. `app.py` creates `WormWriter()` with no arguments → `s3_client=None` → **in-memory only by default**. Docker-compose sets `MINIO_ENDPOINT` env var but **no code reads it to create a boto3 client**. The production path exists but is never activated without manual `configure()` call.

### Does it actually call Langfuse SDK?
**WIRED BUT DEV-MODE.** `LangfuseWriter` has two paths:
- **Production path**: `self._client.trace(id=..., name=..., metadata=...)` — real Langfuse SDK call.
- **Dev path**: in-memory dict.
- **Which runs?** `app.py` creates `LangfuseWriter()` with no arguments → `client=None` → **in-memory only by default**. Docker-compose runs Langfuse container but no code creates a Langfuse client to inject.

### Does it actually call Salesforce CRM API?
**WIRED BUT DEV-MODE.** `CrmWriter` has two paths:
- **Production path**: `self._client.post("/services/data/v62.0/sobjects/IR_Audit_Log__c", json=payload)` — real Salesforce REST API call.
- **Dev path**: in-memory dict with fake CRM IDs.
- **Which runs?** `app.py` creates `CrmWriter()` with no arguments → `client=None` → **in-memory only by default**.

### Is the SHA-256 hash computation real?
**REAL.** `AuditEntry` model computes `sha256_integrity` over the entry's canonical fields. The hash is computed using real `hashlib.sha256`.

### Dead Letter Queue?
**MOCK ONLY.** `collections.deque` in memory. Comment says "Production: SQS/RabbitMQ" but no SQS code exists.

| Component | Classification |
|-----------|---------------|
| S3 Object Lock WORM write | **WIRED BUT DEV-MODE** (code exists, never activated) |
| Langfuse SDK write | **WIRED BUT DEV-MODE** (code exists, never activated) |
| Salesforce CRM write | **WIRED BUT DEV-MODE** (code exists, never activated) |
| SHA-256 integrity hash | **REAL** |
| 3-tier fail-closed logic | **REAL** (AuditWriteError raised on any tier failure) |
| Dead Letter Queue | **MOCK ONLY** (in-memory deque) |
| Audit entry indexing | **MOCK ONLY** (in-memory dict) |

---

## 5. INTEGRATION TESTS (`tests/integration/test_trust_pipeline_e2e.py`)

### Does this test start real services?
**NO. Everything is mocked.** The test uses `httpx.ASGITransport(app=app)` to run the FastAPI app in-process, and injects a `TrustPipelineMockTransport` that intercepts all outbound HTTP calls. No real M1, M2, M4, M7, M10, or MCP servers are started.

### What exactly is being tested?
**The wiring logic and fail-closed behavior.** Specifically:
1. Happy path: request flows through all pipeline stages in correct order
2. M1 deny → 403 with generic error
3. M2 deny → 403 with generic error
4. M4 MNPI filtering strips fields from request/response
5. Leakage scan blocks MNPI keywords and SSN patterns
6. Audit log receives correct provenance chain with SHA-256 hashes
7. Generic errors never leak internal details (Rule 9)

**What is NOT tested:**
- Real HTTP calls between containers
- Real JWT RS256 verification (mock returns `{"valid": true}`)
- Real OPA policy evaluation
- Real S3/Langfuse/CRM writes
- Real Redis rate limiting or circuit breaker state
- Real MCP server responses

### Unit tests (`test_m6_gateway.py`)?
**Same pattern.** All module dependencies mocked via `MockTransport`. Tests verify:
- Leakage scan regex patterns (REAL — actual regex execution)
- Circuit breaker state machine (REAL — actual state transitions)
- Rate limiter sliding window (REAL — actual time-based logic)
- Provenance chain SHA-256 (REAL — actual hash computation)
- Trust pipeline orchestration (MOCKED — httpx transport intercepts)

| Test Aspect | Classification |
|-------------|---------------|
| Pipeline orchestration flow | **TESTED (mocked deps)** |
| Fail-closed behavior | **TESTED (mocked deps)** |
| Leakage scan regex | **TESTED (real execution)** |
| Circuit breaker logic | **TESTED (real execution)** |
| Rate limiter logic | **TESTED (real execution)** |
| SHA-256 provenance | **TESTED (real execution)** |
| Inter-service HTTP calls | **NOT TESTED** |
| Real JWT verification | **NOT TESTED** |
| Real OPA evaluation | **NOT TESTED** |
| Real S3/Langfuse/CRM | **NOT TESTED** |

---

## 6. OVERALL WIRING: `docker-compose up`

### Will M6 actually call M1 over HTTP?
**PARTIALLY.** M6's `TrustPipeline` makes real `httpx` calls to the configured URLs. However, `GatewayConfig` uses `BaseModel` (not `BaseSettings`) and **does not read the `M1_URL`, `M2_URL`, etc. env vars** set in docker-compose. The defaults point to `http://m1-identity:8000` (port 8000) while docker-compose exposes M1 on port 8001. **Port mismatch will cause connection failures unless the config is manually overridden.**

### Will M6 actually call OPA over HTTP?
**INDIRECTLY YES.** M6 calls M2/M4 over HTTP. M2/M4's `policy_client.py` reads `OPA_URL` from env vars (correctly wired in docker-compose as `http://opa:8181`). With `USE_LOCAL_EVALUATOR=false`, M2/M4 will make real HTTP calls to the OPA container, which loads real Rego bundles.

### Will M10 actually write to MinIO (S3-compatible)?
**NO.** Docker-compose runs MinIO and sets `MINIO_ENDPOINT` env var, but `app.py` creates `WormWriter()` with no S3 client. No code reads `MINIO_ENDPOINT` to create a boto3 client. All three audit tiers write to in-memory stores.

### Is everything running in-memory?
**Mostly yes, with exceptions:**
- M1 JWT crypto is REAL (RSA-2048 keys generated at startup)
- M2/M4 → OPA HTTP calls are REAL (when `USE_LOCAL_EVALUATOR=false`)
- M6 → M1/M2/M4/M10 HTTP calls are REAL (but port mismatch in defaults)
- Redis connection is attempted (falls back to in-memory on failure)
- M10 audit writes are IN-MEMORY (no S3, no Langfuse SDK, no CRM client)

---

## Summary Matrix

| Module | Component | Status | Notes |
|--------|-----------|--------|-------|
| **M1** | JWT RS256 crypto | ✅ REAL | PyJWT + cryptography, real RSA-2048 |
| **M1** | Keycloak integration | ❌ MOCK ONLY | Env var exists, zero code |
| **M1** | AID registry | ❌ MOCK ONLY | In-memory dict, no PostgreSQL |
| **M2/M4** | OPA HTTP calls | ✅ REAL | httpx, env-configurable |
| **M2/M4** | Local evaluator | ✅ REAL | Faithful Rego mirror |
| **M2/M4** | Rego policies | ✅ REAL | Substantive rules with tests |
| **M2/M4** | Fail-closed | ✅ REAL | DENY on OPA unreachable |
| **M6** | Trust pipeline HTTP calls | ✅ REAL | httpx async to all modules |
| **M6** | MCP forwarding | ✅ REAL | httpx async |
| **M6** | Circuit breaker | ✅ REAL | State machine + Redis option |
| **M6** | Rate limiter | ✅ REAL | Sliding window + Redis option |
| **M6** | Leakage scan Layer A | ✅ REAL | 10+ regex patterns |
| **M6** | Leakage scan Layers B/C | ⚠️ STUB | Returns pass, not_implemented |
| **M6** | Config env var loading | ❌ BROKEN | Doesn't read docker-compose env vars |
| **M10** | S3 WORM write | ⚠️ WIRED BUT DEV-MODE | Code exists, never activated |
| **M10** | Langfuse write | ⚠️ WIRED BUT DEV-MODE | Code exists, never activated |
| **M10** | CRM write | ⚠️ WIRED BUT DEV-MODE | Code exists, never activated |
| **M10** | SHA-256 integrity | ✅ REAL | hashlib.sha256 |
| **M10** | DLQ | ❌ MOCK ONLY | In-memory deque |
| **Tests** | E2E integration | ⚠️ MOCKED | All deps mocked via transport |
| **Docker** | M6 → M1 wiring | ❌ BROKEN | Port mismatch in defaults |
| **Docker** | M2/M4 → OPA wiring | ✅ REAL | Correct env var reading |
| **Docker** | M10 → MinIO wiring | ❌ BROKEN | No boto3 client creation |

---

## Critical Findings

### 1. GatewayConfig Port Mismatch (BLOCKING)
`GatewayConfig` defaults to port 8000 for all modules, but docker-compose runs M1 on 8001, M2/M4 on 8002, M10 on 8010. The env vars (`M1_URL`, `M2_URL`, etc.) are set in docker-compose but **never read** because `GatewayConfig` is a plain `BaseModel`, not `BaseSettings`. Fix: either switch to `pydantic-settings.BaseSettings` with `env_prefix`, or read env vars in the lifespan handler.

### 2. M10 Backends Never Activated (BLOCKING for 3-tier audit)
All three M10 writers default to in-memory. Docker-compose runs MinIO and Langfuse but no code creates boto3/Langfuse clients from the env vars. The production code paths exist and look correct, but the dependency injection bridge is missing.

### 3. No True E2E Test Exists
Every test mocks all inter-service calls. There is no test that starts multiple containers and verifies real HTTP communication between M6 → M1 → M2/M4 → M10. The tests verify orchestration logic (valuable) but not integration (also needed).

### 4. Keycloak is a Phantom Dependency
Docker-compose starts Keycloak, M1 depends on it, but zero lines of Python code interact with Keycloak. It's infrastructure cost with no application value currently.
