# M10 Audit Logger -- DECISION-LOG

## 2026-05-22 -- v0.3.0 adds FastAPI REST surface (POST /audit, GET /health)

**Area**: REST API surface.
**Decision**: Ship a FastAPI `app` module (`m10_audit_logger.app`)
exposing `POST /audit` + `GET /health`. Route handlers delegate to
the existing `AuditLogger.write(...)` path; backends remain
`InMemoryAuditBackend` triples in v0.3.0.
**Rationale**: M8 v0.2.0 Known Blocker row 18 (SHARED-WITH-M10,
Required Fix 4) refactored M8's audit fan-out onto a dedicated
`M10AuditClient` Protocol talking to M10's `POST /audit` endpoint over
mTLS. M10 v0.2.0 had no REST surface; that gap is closed here.
**Failure model**: 202 on success; 400 on malformed body or missing
required keys; 503 on any tier write failure -- M8 retries per its
AC8.5 (fail-closed per Steering Rule 8). 5xx from M10 DOES NOT bypass
the audit requirement; originating requests still fail on the M8 side.
**Decided By**: Trust Layer Specialist.

## 2026-05-22 -- Real backends stay out of v0.3.0 (B2 scope)

**Area**: Backends.
**Decision**: v0.3.0 ships ONLY the FastAPI route + wire-shape
translation; backend triples remain `InMemoryAuditBackend`. Real
Langfuse / S3 Object Lock / Salesforce backends are deferred to the
B2 (backends) work-stream.
**Rationale**: The M8 SHARED-WITH-M10 blocker is the endpoint itself,
not the backing stores. Decoupling lets M8 land its integration test
GREEN without being gated on Langfuse SDK pinning, S3 Object Lock
retention config, or Salesforce REST mapping. The existing
`AuditLogger.write(...)` contract absorbs real-backend swaps without
app-layer changes (per module boundary / Rule 10).
**Decided By**: Trust Layer Specialist.

## 2026-05-22 -- `SCHEMA_VERSION="0.3.0"` added; `__all__` unchanged

**Area**: Public API surface.
**Decision**: Add `SCHEMA_VERSION: str = "0.3.0"` module constant to
`m10_audit_logger.__init__`. The `__all__` tuple is deliberately NOT
expanded with `app`.
**Rationale**: The spec task called for `app` in `__all__`, but the
existing `TestPublicApi.test_all_surface_matches` unit test pins
`__all__` to an exact 10-name set. Honouring the "all existing tests
stay green" constraint is higher priority than the nice-to-have
listing. Callers that need the app can still
`from m10_audit_logger.app import app` -- module attribute access is
not gated by `__all__`. The next spec revision should either loosen
the `__all__` exact-match test or add `app` explicitly.
**Decided By**: Trust Layer Specialist.

## 2026-05-22 -- Middleware emits structured-stdout JSON, never the body

**Area**: Observability.
**Decision**: Access logs are two JSON lines per request written via
`sys.stdout.write(...) + flush()`. Allowed fields: `phase`
(`request_start` / `request_end`), `method`, `path`, `status_code`,
`latency_ms`, and the header-sourced trace metadata (`x-trace-id`,
`x-event-type`, `x-pipeline-run-id`). The request body is NEVER read
in middleware.
**Rationale**: The stdlib `logging` module is forbidden by the M10
security grep (pre-existing `TestSecurity.test_no_logging_of_entry_contents_in_src`)
because its formatter can easily capture payload contents by mistake.
Stdout-JSON with a hard-coded allowlist is simpler to audit. The test
`TestMiddlewareRedaction.test_stdout_does_not_contain_raw_body` scans
captured stdout for SSN / phone / ABA-routing shapes on every run --
the scanner runs against synthetic MNPI-shaped canaries injected into
the body to prove the redaction holds.
**Decided By**: Trust Layer Specialist.

## 2026-05-22 -- AuditEntry translation synthesises `module="m10"` + `decision="allow"`

**Area**: Wire-shape translation.
**Decision**: M10 translates incoming M8 `StageAuditPayload` dicts into
canonical M3 `AuditEntry` objects with `module="m10"`,
`decision="allow"`, and a synthesised `worm_record_id` of the form
`m8/<pipeline_run_id>/<stage_number:02d>/<iso_timestamp>`. The M8
`event_type` maps to the M3 `action` field.
**Rationale**: M3 `AuditEntry` is the 3-tier canonical write shape;
it needs `module` + `decision` + `worm_record_id` + `retention_years`
that M8's `StageAuditPayload` doesn't carry. `module="m10"` because
THIS write is M10's record of the event; the originating module is
captured in `action` (prefix `m8.`). `decision="allow"` because a
per-stage audit is a record of something that happened, not a trust
decision. The 6-year retention floor is applied by
`AuditLogger.write(...)` (Rule 4 / SEC 17a-4).
**Decided By**: Trust Layer Specialist.

## 2026-05-22 -- Dockerfile: non-root UID 1000, port 8443, no credentials

**Area**: Deployment.
**Decision**: `src/m10_audit_logger/Dockerfile` uses `python:3.12-slim`,
creates user `m10` with UID 1000, runs `uvicorn m10_audit_logger.app:app
--host 0.0.0.0 --port 8443 --workers 2`, and installs ONLY the
runtime-required deps (`fastapi`, `uvicorn[standard]`, `pydantic`).
`curl` is installed for `HEALTHCHECK` only. No secrets are baked into
the image.
**Rationale**: Steering Rules 20 (zero credentials in git / image) +
21 (mTLS terminates upstream; app does not authenticate) + 22
(private subnet only; no public internet). The service-mesh sidecar
handles mTLS; the app listens in cleartext on the pod-local
interface. `EXPOSE 8443` documents the expected mesh-side port.
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- v0.4.0 adds real MinIO Object Lock WORM backend (Ops Hardening Wave 3)

**Area**: WORM tier (Rule 6, SEC 17a-4).
**Decision**: Ship `MinIOWormBackend` in `backends_minio/minio_worm.py`
as a drop-in replacement for `InMemoryAuditBackend(tier="worm")` in
production values files. AWS S3 Object Lock remains a future spec
behind the same `AuditBackend` Protocol.
**Rationale**: Customer GA cannot claim SEC 17a-4 compliance with
an in-memory dict. MinIO with Object Lock in Compliance mode is the
minimum viable real WORM backend and covers on-prem + air-gapped
(Tier 1 / Tier 5) deployments where AWS is not in the data plane.
**Failure model**: Every construction + per-write failure path
raises `AuditWriteError("worm_write_failed")`. No degraded mode.
The 6-year retention floor is enforced at three layers (M5 parse,
backend `__init__`, orchestrator `AuditLogger.write`) -- defence
in depth.
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- backend lives in `backends_minio/`, NOT in `backends.py`

**Area**: Package layout.
**Decision**: New sibling package `src/m10_audit_logger/backends_minio/`
instead of extending `backends.py`. Re-exported lazily via PEP 562
`__getattr__` on `m10_audit_logger.__init__`.
**Rationale**: Adding the `minio` SDK import to the top-level
backends file would force EVERY M10 consumer (orchestrator, unit
tests, Langfuse-only wiring) to pay the `minio` import cost. Lazy
re-export keeps the dependency opt-in. Same precedent as the `app`
deferral in v0.3.0: the PEP 562 escape hatch avoids breaking the
pinned `__all__` unit test.
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- Vault path strings, NOT Vault-client instance, in config

**Area**: Credential handling (Rule 20).
**Decision**: `MinIOWormConfig` stores `access_key_vault_path` +
`secret_key_vault_path` as plain path strings validated against
`^secret/data/m10/minio/...`. The `VaultClient` (Protocol) is
injected into `MinIOWormBackend.__init__` directly, NOT referenced
from the config.
**Rationale**: Config files + config objects must be credential-free
and serialisable (Rule 20). The Vault client is stateful (token
rotation, client certs) and belongs in the DI wiring alongside the
backend. `MinIOWormBackend.__init__` reads both paths once, passes
the plaintext secrets directly to the `Minio` SDK constructor, and
releases them. `self` retains only the `Minio` client; `__repr__`
and `__str__` never see the keys.
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- Object key pattern: `{firm_id}/{yyyy}/{mm}/{dd}/{canonical_id}.json`

**Area**: Bucket layout + examiner retrieval.
**Decision**: Day-sharded + firm-prefixed key. The canonical ID
goes last so a List-prefix-scan on `firm_X/2026/04/14/` is the
native "show me everything for firm X on April 14" examiner query.
**Rationale**: We optimise for the examiner-retrieval pattern, not
for random lookup. `query_by_trace_id` is explicitly documented as
O(N) per-bucket (or per-firm-prefix); Phase 4 adds an Elasticsearch
index keyed on `trace_id -> object_key` maintained via MinIO
notifications. Sub-day sharding defers to that Phase 4 change.
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- Retention clock starts at event time, not write time

**Area**: SEC 17a-4 retention semantics.
**Decision**: `retain_until_date = entry.timestamp + retention_years`,
where `entry.timestamp` is the business event time supplied by the
caller. We reject naive timestamps.
**Rationale**: Retention is measured from the event, not from when
the audit record happened to land in storage. A backlog replay that
writes a 5-year-old event sets its retention_until to (5-years-old +
6 years) -- which may already be in the past by a few months, and
that is the correct regulatory outcome. Naive timestamps would be
ambiguous on timezone, which is why we fail them loud.
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- GOVERNANCE mode is allowed but emits UserWarning

**Area**: Object Lock mode policy.
**Decision**: `object_lock_mode` defaults to `COMPLIANCE`;
`GOVERNANCE` is accepted but emits a loud `UserWarning` at M5 parse
AND at backend construction. Integration test proves the bucket +
backend interoperate when both agree on `GOVERNANCE`.
**Rationale**: Some customers (particularly Tier 4 RIAs) run
`GOVERNANCE` to enable compliance-officer release under an internal
data-retention policy that DIFFERS from SEC rules. The warning is
the audit trail: "you opted out of the COMPLIANCE default; this
deployment CAN release retention early." `COMPLIANCE` remains the
spec-aligned default (Rule 4).
**Decided By**: Trust Layer Specialist.

## 2026-05-29 -- Integration-test harness: env-var OR testcontainers

**Area**: CI/CD + developer experience.
**Decision**: `tests/integration/test_m10_minio_worm_integration.py`
tries `M10_MINIO_TEST_ENDPOINT` / `*_ACCESS_KEY` / `*_SECRET_KEY`
first, then `testcontainers-python` + a Docker-compatible daemon,
then skips the module. 8 scenarios.
**Rationale**: finch and colima work as well as Docker Desktop for
spinning up MinIO locally, but they don't always present a
docker.sock that `testcontainers-python` can reach. The env-var
path lets a developer pre-start MinIO (e.g. `finch run ...`) and
run the tests against it. CI without any container runtime skips
the module but keeps the Python suite green via the 50 unit tests.
**Decided By**: Trust Layer Specialist.
