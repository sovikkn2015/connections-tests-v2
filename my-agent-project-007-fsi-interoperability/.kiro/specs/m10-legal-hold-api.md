# M10 Legal-Hold API

> Phase 4 B1 deliverable. FINRA 4511.04 compliance gap.
> Module in scope: **M10 Audit Logger**. Extension of the MinIO WORM
> backend introduced in the Wave-3 spec
> `.kiro/specs/m10-worm-minio-backend.md`.
>
> Source of truth: Steering Rule 6 (3-tier WORM), Steering Rule 8
> (fail-closed), FINRA 4511.04 (records retention extension under
> legal hold), SEC 17a-4(j) (legal hold as allowable retention
> extension beyond the 6-year floor).
>
> **v1 LLMJ self-review → CONDITIONAL GO 7.3/10.** Issues raised:
>
> 1. C1 — Original draft wrote the legal-hold audit entry via a
>    direct logger call, which creates an unbounded recursion if the
>    legal-hold audit itself is under legal hold. Resolved in v2
>    §2.6 by marking the legal-hold audit's own `canonical_id` as
>    "hold-meta" (different shape than the target canonical_id) and
>    by documenting that the legal-hold meta-record is ALSO legal-
>    held (prevents tampering with the tamper record).
> 2. C2 — Hold registry was originally the same bucket as the
>    primary WORM objects; mixing metadata with WORM records
>    violates the single-writer-single-responsibility invariant.
>    Resolved in v2 §2.4 with a separate bucket
>    (`007-audit-legal-holds` default).
> 3. C3 — `place_legal_hold` permission check was implied but not
>    enforced. Resolved in v2 §2.3 with an explicit role check
>    inside the FastAPI surface; the backend itself is role-
>    agnostic (testability) but the REST layer gates everything on
>    the M1 verify_aid `compliance_officer` role claim.
> 4. C4 — Release-with-wrong-hold_id was accepted. FINRA 4511.04
>    requires the release to reference the SAME hold_id as the
>    original placement. Resolved in v2 via an explicit check at
>    both backend and HTTP levels.
> 5. R1 — HoldEntry Pydantic model lacked strict field constraints.
>    Resolved in v2 §2.2 with `model_config = ConfigDict(extra=
>    "forbid", strict=True)`.
> 6. R2 — List-holds endpoint needed to return empty list (not 404)
>    when no holds exist — 404 is ambiguous. Resolved in v2 §2.5
>    with always-200-with-list response.
> 7. R3 — HoldEntry didn't include `released_at` / `released_by`;
>    essential for audit reconstruction. Resolved in v2.
> 8. R4 — `hold_id` shape unbounded — could be anything. Resolved
>    with `HOLD_ID_PATTERN = r"^[A-Za-z0-9_\-]{3,128}$"`.
>
> v2 score: **GO 8.5/10.**
>
> Source of truth: `src/m10_audit_logger/backends_minio/minio_worm.py`
> (v0.4.0 pre-extension), `src/m10_audit_logger/app.py` (v0.3.0).

---

## Section 1 — Requirements

### R1. Backend API surface

Extend `MinIOWormBackend` with three legal-hold operations.

- **AC1.1** `place_legal_hold(canonical_id: UUID, hold_id: str,
  reason: str, placed_by: str) -> HoldEntry` — uses the MinIO SDK
  `put_object_legal_hold(..., legal_hold=LegalHold(status="ON"))`
  on the specific object version.
- **AC1.2** `release_legal_hold(canonical_id: UUID, hold_id: str,
  reason: str, released_by: str) -> HoldEntry` — calls the same SDK
  method with `LegalHold(status="OFF")`, ONLY if the hold_id matches
  the active hold registry entry.
- **AC1.3** `list_legal_holds(canonical_id: UUID) -> list[HoldEntry]`
  — returns the active (not-yet-released) holds for the given
  canonical_id. Empty list is valid (no holds).
- **AC1.4** The three methods NEVER mutate the target audit entry
  itself — they only toggle MinIO's object-level LegalHold flag and
  record a HoldEntry in the registry bucket.

### R2. HoldEntry Pydantic model

- **AC2.1** `HoldEntry` is a strict Pydantic model with these
  fields:
  - `hold_id: str` — `^[A-Za-z0-9_\-]{3,128}$`
  - `canonical_id: UUID` — target audit entry ID
  - `reason: str` — `min_length=3, max_length=1024`
  - `placed_by: str` — M1 AID actor hash (SHA-256 hex, 64 chars)
  - `placed_at: datetime` — timezone-aware UTC only
  - `released_at: Optional[datetime]` — UTC, None while active
  - `released_by: Optional[str]` — 64-hex SHA-256, None while active
- **AC2.2** `model_config = ConfigDict(extra="forbid",
  strict=True, frozen=True)`.
- **AC2.3** A `is_active` computed property returns `True` when
  `released_at is None`.
- **AC2.4** A HoldEntry is serialised as canonical JSON (same
  helper as the main WORM backend) for the registry-object payload.

### R3. Hold registry (separate bucket)

- **AC3.1** Registry bucket default: `007-audit-legal-holds`.
  Configurable via `legal_hold_bucket_name` on the backend
  constructor; falls back to the default.
- **AC3.2** Registry objects use a deterministic key:
  `{canonical_id}/{hold_id}.json`. Makes listing-by-canonical a
  simple prefix query.
- **AC3.3** Registry bucket MUST also have Object Lock enabled
  (COMPLIANCE mode, 6y retention) — the registry is itself an audit
  record and must be tamper-evident. Backend verifies at
  construction.
- **AC3.4** Registry bucket is provisioned by the operator BEFORE
  backend construction — the chart / operator is responsible, not
  the backend.
- **AC3.5** Release workflow: when a hold is released, the registry
  object is OVERWRITTEN with the released state — MinIO versioning
  preserves the original placed-state version. (Object Lock on the
  registry prevents the original version from being deleted.)

### R4. Uniqueness + duplicate handling

- **AC4.1** `place_legal_hold(canonical_id, hold_id, ...)` rejects
  if a registry object at `{canonical_id}/{hold_id}.json` already
  exists AND is active (`released_at is None`). Raises
  `LegalHoldError("duplicate_hold_id")`.
- **AC4.2** Placing a legal hold for a canonical_id that does not
  exist in the main WORM bucket raises `LegalHoldError(
  "target_not_found")`.
- **AC4.3** `release_legal_hold(canonical_id, hold_id, ...)`
  rejects if the hold_id does not match an active hold for that
  canonical_id. Raises `LegalHoldError("hold_not_found")`.
- **AC4.4** Releasing an already-released hold raises
  `LegalHoldError("hold_already_released")`.

### R5. Legal-hold audit emission

Every `place_legal_hold` and `release_legal_hold` invocation MUST
emit a fresh `AuditEntry` via the shared `AuditLogger` the caller
provides.

- **AC5.1** Backend constructor accepts an optional
  `orchestrator: AuditLogger` (duck-typed; the concrete type is
  imported at backend-module scope to avoid cycles — same as
  `logger.AuditLogger`).
- **AC5.2** When the orchestrator is absent, the backend operates
  in library-only mode (no audit emission). The FastAPI layer
  always supplies one.
- **AC5.3** The emitted audit entry has:
  - `action`: `"legal_hold.placed"` or `"legal_hold.released"`.
  - `actor_id`: `placed_by` / `released_by`.
  - `module`: `"m10"`.
  - `decision`: `"allow"`.
  - `reason`: the `reason` passed to the method.
  - `target_type`: `"audit_entry"`.
  - `target_id`: `str(canonical_id)`.
  - `input_hash`: SHA-256 of the HoldEntry canonical JSON.
  - `output_hash`: SHA-256 of the resulting registry object body.
  - `firm_id`: inherited from the TARGET entry (fetched via
    stat_object).
  - `worm_record_id`: `legal-hold/{canonical_id}/{hold_id}`.
  - `sha256_integrity`: empty (orchestrator computes).
  - `retention_years`: 6.
- **AC5.4** The legal-hold audit entry is ALSO placed under legal
  hold — IMMEDIATELY after being written to WORM the backend
  invokes a nested `place_legal_hold` on the new canonical_id with
  `hold_id = f"meta-{original_hold_id}"`. This prevents a bad actor
  from tampering with the tamper record. Termination condition: the
  meta-hold itself is NOT further legal-held (no infinite
  recursion).
- **AC5.5** If the audit emission fails, the legal hold IS STILL
  PLACED (the MinIO LegalHold flag is already ON). The method
  returns the HoldEntry with a warning-level log line.
  Justification: failing-closed here would leave the object in an
  inconsistent state (flag set, no audit); instead we emit the
  inconsistency to the DLQ via the orchestrator, matching the
  existing 3-tier fail-closed pattern.

### R6. FastAPI REST surface

- **AC6.1** `POST /audit/legal-hold`
  - Body: `{"canonical_id": UUID, "hold_id": str, "reason": str,
    "placed_by": str}`.
  - Auth: `compliance_officer` role via M1 `verify_aid` header
    token.
  - Response: 202 with `{"status": "placed", "hold_id": str,
    "placed_at": ISO-8601}` on success.
  - 400 on body validation failure.
  - 403 on missing / wrong role.
  - 409 on `LegalHoldError("duplicate_hold_id")`.
  - 404 on `LegalHoldError("target_not_found")`.
  - 503 on any backend failure other than the above.
- **AC6.2** `DELETE /audit/legal-hold`
  - Body: `{"canonical_id": UUID, "hold_id": str, "reason": str,
    "released_by": str}`.
  - Auth: `compliance_officer` role.
  - Response: 200 with `{"status": "released", "hold_id": str,
    "released_at": ISO-8601}` on success.
  - Error mapping same as POST.
  - 404 on `hold_not_found`.
  - 409 on `hold_already_released`.
- **AC6.3** `GET /audit/legal-hold/{canonical_id}`
  - Auth: `compliance_officer` role.
  - Response: 200 with `{"canonical_id": UUID, "holds": [HoldEntry,
    ...]}` — empty list is valid.
- **AC6.4** All three endpoints emit a structured stdout line on
  entry and exit (same middleware as the existing `/audit` endpoint).
- **AC6.5** No endpoint echoes the request body on error — MNPI
  safety (same discipline as the existing `/audit` endpoint).

### R7. Role enforcement (M1 dependency)

- **AC7.1** The FastAPI layer fetches a bearer token from
  `Authorization: Bearer <jwt>`.
- **AC7.2** The token is validated via an injectable
  `verify_aid(token: str) -> dict` callable. The default callable
  raises `NotImplementedError` (forces explicit wiring).
- **AC7.3** The returned claim dict MUST contain `roles:
  list[str]`; `compliance_officer` must be present. Otherwise 403.
- **AC7.4** Tests provide a stub `verify_aid` that returns
  controllable claims.

### R8. Security invariants

- **AC8.1** No credentials in source. The same grep test that
  guards `minio_worm.py` also covers the extension.
- **AC8.2** No `os.environ` reads in the backend extension. Vault
  paths are reused from the existing constructor.
- **AC8.3** `str(HoldEntry)` / `repr(HoldEntry)` never includes
  the raw reason — Pydantic default `repr` limits to fields; we
  override to redact `reason` to `[REDACTED]` to avoid case-detail
  leakage in logs.
- **AC8.4** FastAPI responses never include stack traces or the
  raw exception message — same as existing `/audit` endpoint.

### R9. Backward compat

- **AC9.1** Existing callers that don't use legal-hold are
  unaffected. `MinIOWormBackend.__init__` signature gains only
  optional kwargs (`legal_hold_bucket_name`, `orchestrator`).
- **AC9.2** All 1866 baseline tests still pass.

---

## Section 2 — Design

### 2.1 File layout

```
src/m10_audit_logger/
    backends_minio/
        minio_worm.py            (CHANGED — adds legal-hold methods)
        legal_hold.py            (NEW — HoldEntry model + exceptions)
    app.py                       (CHANGED — adds 3 endpoints)
tests/unit/
    test_m10_minio_worm.py       (unchanged — 10 NEW tests appended)
    test_m10_app_legal_hold.py   (NEW — 8 REST tests)
tests/integration/
    test_m10_minio_worm_integration.py
                                 (unchanged — 3 NEW integration tests appended)
```

### 2.2 `legal_hold.py` — HoldEntry model

```python
from __future__ import annotations

import re
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

HOLD_ID_PATTERN = re.compile(r"^[A-Za-z0-9_\-]{3,128}$")
_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class LegalHoldError(Exception):
    """FINRA 4511.04 legal-hold failure.

    reason is one of:
        "duplicate_hold_id", "target_not_found",
        "hold_not_found", "hold_already_released",
        "legal_hold_write_failed", "legal_hold_registry_failed"
    """

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


VALID_LEGAL_HOLD_REASONS = frozenset({
    "duplicate_hold_id",
    "target_not_found",
    "hold_not_found",
    "hold_already_released",
    "legal_hold_write_failed",
    "legal_hold_registry_failed",
})


class HoldEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)

    hold_id: str = Field(...)
    canonical_id: UUID = Field(...)
    reason: str = Field(..., min_length=3, max_length=1024)
    placed_by: str = Field(...)
    placed_at: datetime = Field(...)
    released_at: Optional[datetime] = None
    released_by: Optional[str] = None

    @field_validator("hold_id")
    @classmethod
    def _validate_hold_id(cls, v: str) -> str:
        if not HOLD_ID_PATTERN.fullmatch(v):
            raise ValueError("hold_id shape invalid")
        return v

    @field_validator("placed_by")
    @classmethod
    def _validate_actor(cls, v: str) -> str:
        if not _SHA256_HEX.fullmatch(v):
            raise ValueError("placed_by must be sha256-hex")
        return v

    @field_validator("released_by")
    @classmethod
    def _validate_released_by(cls, v):
        if v is None:
            return v
        if not _SHA256_HEX.fullmatch(v):
            raise ValueError("released_by must be sha256-hex")
        return v

    @field_validator("placed_at", "released_at")
    @classmethod
    def _tz_aware(cls, v):
        if v is None:
            return v
        if v.tzinfo is None or v.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        return v

    @property
    def is_active(self) -> bool:
        return self.released_at is None

    def __repr__(self) -> str:   # AC8.3 — redact reason
        return (
            f"HoldEntry(hold_id={self.hold_id!r}, "
            f"canonical_id={self.canonical_id!r}, "
            f"reason='[REDACTED]', placed_at={self.placed_at!r}, "
            f"is_active={self.is_active})"
        )
    __str__ = __repr__
```

### 2.3 `minio_worm.py` — backend extension

New methods + state. Constructor gains optional kwargs:

```python
def __init__(self, *,
             config: MinIOWormConfigProtocol,
             vault_client: VaultClient,
             minio_client_factory=None,
             legal_hold_bucket_name: str = "007-audit-legal-holds",
             orchestrator=None) -> None:
    ...
    self._legal_hold_bucket = legal_hold_bucket_name
    self._orchestrator = orchestrator
    self._verify_legal_hold_bucket_configuration()   # new
```

Operations:

```python
def place_legal_hold(self, canonical_id, hold_id, reason, placed_by):
    # 1. Resolve target object: stat_object + list object versions
    #    via list_objects with include_version=True, filtered by
    #    canonical_id UUID suffix in key.
    # 2. Build HoldEntry, serialise canonical JSON.
    # 3. Check registry for existing active hold with same hold_id.
    #    If found → raise duplicate_hold_id.
    # 4. put_object to legal-hold bucket with retention 6y compliance.
    # 5. MinIO put_object_legal_hold ON on the target version.
    # 6. Emit audit via self._orchestrator (if present).
    # 7. Return HoldEntry.
    ...

def release_legal_hold(self, canonical_id, hold_id, reason, released_by):
    # 1. Fetch active registry entry {canonical_id}/{hold_id}.json.
    #    If missing → hold_not_found.
    #    If released_at is not None → hold_already_released.
    # 2. Rebuild HoldEntry with released_at=now UTC + released_by.
    # 3. put_object to legal-hold bucket (new version overwrite).
    # 4. put_object_legal_hold OFF on target version.
    # 5. Emit release audit via orchestrator.
    ...

def list_legal_holds(self, canonical_id):
    # list_objects prefix=f"{canonical_id}/" recursive=True.
    # For each key, get_object + parse HoldEntry.
    # Filter is_active == True.
    # Return sorted list by placed_at ascending.
    ...
```

The target-object version resolution is done via:

```python
def _resolve_target_version(self, canonical_id: UUID):
    # list_objects on the main WORM bucket with a prefix search for
    # the canonical_id UUID. The key shape is
    # {firm_id}/{yyyy}/{mm}/{dd}/{canonical_id}.json — no direct
    # prefix match; we scan with include_version=True and filter.
    # O(N) in the bucket; documented as non-scalable (Phase 4 adds
    # an index).
    ...
```

This is acknowledged-slow. Follow-up wave adds an ES index on
`canonical_id`; for Wave 4 the caller is the compliance officer
manually placing a hold on a specific entry, so latency is
acceptable.

### 2.4 Registry bucket verification

`_verify_legal_hold_bucket_configuration` mirrors the main WORM
bucket check: bucket exists, Object Lock enabled, mode matches
config (COMPLIANCE). Fail-closed on any mismatch.

### 2.5 FastAPI surface

`app.py` gains:

```python
@new_app.post("/audit/legal-hold")
async def place_hold(request: Request) -> Response: ...
@new_app.delete("/audit/legal-hold")
async def release_hold(request: Request) -> Response: ...
@new_app.get("/audit/legal-hold/{canonical_id}")
async def list_holds(canonical_id: UUID, request: Request) -> Response: ...
```

Role gate:

```python
def _require_compliance_officer(request: Request) -> dict:
    token = request.headers.get("authorization", "").removeprefix("Bearer ")
    if not token:
        raise _HttpError(403, "missing_token")
    claims = request.app.state.verify_aid(token)
    roles = claims.get("roles", [])
    if "compliance_officer" not in roles:
        raise _HttpError(403, "role_required")
    return claims
```

`verify_aid` is stored on `app.state.verify_aid` at `create_app`
time. Default is a stub that raises `NotImplementedError("wire
verify_aid on app.state.verify_aid before production use")`. Tests
inject a controllable stub.

Backend accessor: `app.state.minio_worm_backend` (optional;
populated in production deploys; tests inject fakes).

### 2.6 Meta-hold termination rule

Per AC5.4, the meta-hold (which protects the legal-hold audit
entry) does NOT itself receive a meta-hold. Termination: backend
checks `hold_id.startswith("meta-")` and skips nested emission.

### 2.7 Error mapping at HTTP layer

```
LegalHoldError.reason -> HTTP
  duplicate_hold_id      -> 409
  target_not_found       -> 404
  hold_not_found         -> 404
  hold_already_released  -> 409
  legal_hold_write_failed -> 503
  legal_hold_registry_failed -> 503
ValidationError          -> 400 (generic; no body echoed)
missing Authorization    -> 403 "missing_token"
role mismatch            -> 403 "role_required"
```

---

## Section 3 — Tasks

### Task 1 — Write `legal_hold.py`

New file `src/m10_audit_logger/backends_minio/legal_hold.py` with
the HoldEntry model + LegalHoldError per §2.2.

### Task 2 — Extend `MinIOWormBackend`

Implement the three methods per §2.3 + registry-bucket
verification per §2.4. Constructor gains optional kwargs.

### Task 3 — Extend `app.py`

Add the three routes per §2.5 + the role gate. Wire
`verify_aid` and `minio_worm_backend` via `app.state`.

### Task 4 — Write 10 unit tests in
`tests/unit/test_m10_minio_worm.py`

Append a new test class `TestLegalHoldAPI` with:

1. Happy `place_legal_hold` → returns HoldEntry + writes registry
   object + calls `put_object_legal_hold` ON.
2. Happy `release_legal_hold` → updates registry with `released_at`
   + calls `put_object_legal_hold` OFF.
3. `place_legal_hold` with existing active hold → raises
   `LegalHoldError("duplicate_hold_id")`.
4. `release_legal_hold` with wrong hold_id → raises
   `LegalHoldError("hold_not_found")`.
5. `release_legal_hold` with already-released hold → raises
   `LegalHoldError("hold_already_released")`.
6. `list_legal_holds` returns only active holds.
7. `list_legal_holds` with no holds returns empty list.
8. `place_legal_hold` target not found → raises
   `LegalHoldError("target_not_found")`.
9. HoldEntry `__repr__` redacts reason.
10. Meta-hold termination: when `hold_id.startswith("meta-")`,
    no nested hold is placed.

### Task 5 — Write 3 integration tests in
`tests/integration/test_m10_minio_worm_integration.py`

Append `test_integration_9_place_hold_roundtrip`,
`test_integration_10_release_hold_roundtrip`,
`test_integration_11_tamper_blocked_by_retention_and_hold`.
Marked `pytest.mark.integration`. Use the same testcontainers-or-env
discovery as the existing 8 tests.

### Task 6 — Write 8 REST tests in
`tests/unit/test_m10_app_legal_hold.py` (NEW)

1. POST happy path → 202 + placed_at ISO-8601.
2. POST without Authorization → 403 missing_token.
3. POST with non-compliance role → 403 role_required.
4. POST duplicate hold_id → 409.
5. POST body missing required field → 400.
6. DELETE happy path → 200 + released_at.
7. DELETE wrong hold_id → 404.
8. GET holds returns list (and empty list when none) — tests both.

### Task 7 — Run full test suite

```bash
PYTHONPATH=src python3 -m pytest tests/ -q --tb=short
```

Expected: 1866 baseline + 10 + 3 + 8 = 1887 tests, all green.
Integration tests SKIP gracefully without MinIO present.

### Task 8 — Re-run deploy tests

Unchanged; legal-hold is pure Python.

### Task 9 — Security grep over the new files

Reuse the existing grep pattern from the WORM-backend unit tests
(no AKIA*, no hardcoded credentials, no `os.environ`).

---

## Section 4 — Out of Scope (v2 explicit)

- ES-index-backed fast canonical_id lookup (follow-up).
- Automated legal-hold expiry (FINRA 4511.04 allows indefinite
  duration; operator manually releases).
- Cross-region replication of the hold registry (operator concern).
- UI for compliance officers (separate frontend workstream).
- Hold-lifecycle notifications (email/Slack) — operator pattern.
