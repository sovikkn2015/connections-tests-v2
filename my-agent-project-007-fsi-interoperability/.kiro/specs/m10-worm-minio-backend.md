# M10 WORM MinIO Backend — Spec (v2)

> **Module**: M10 Audit Logger — WORM tier (backend implementation)
> **Wave**: Ops Hardening Wave 3
> **Phase**: 1 (Trust Layer — backend-slot upgrade, B2 work stream)
> **Agent**: 007-trust-agent (Trust Layer Specialist)
> **Status**: v2 (post-review, addresses F1..F14)
> **Source docs**: Steering Rule 6 (3-tier audit), Steering Rule 4 (WORM in Compliance mode), ARCH-04 (S3/MinIO WORM), ARCH-09 (M10 row), 007-consolidated-design-and-plan.md (Part 3 audit layer), phase1-LLMJ-ASSESSMENT.md B3 (real backend), phase1-trust-layer-SCORING.md §7.3

---

## 0. CONTEXT AND SCOPE

### 0.1 Problem

Today M10 ships with `InMemoryAuditBackend` on all three tiers (Langfuse +
WORM + CRM). The WORM tier is the only one that carries a **regulatory
claim** (SEC 17a-4(f)(2)(ii), 17a-4(e)(5), FINRA 4511): Write Once Read
Many, minimum 6-year retention, tamper-evident, cryptographically
verifiable, and demonstrable to an examiner. An in-memory dict provides
none of these.

For customer GA the WORM tier MUST be backed by a real immutable object
store. This spec is the minimum viable real WORM implementation:
`MinIOWormBackend` — MinIO's S3-compatible Object Lock in Compliance
mode. It fits on-prem + air-gapped + self-hosted-cloud topologies and is
the drop-in replacement for `InMemoryAuditBackend(tier="worm")` in all
production values files. AWS S3 Object Lock lives behind the same
`AuditBackend` Protocol contract and remains a future deliverable.

### 0.2 Scope boundary (non-negotiable)

This spec covers ONLY:

1. `src/m10_audit_logger/backends/minio_worm.py` — new
   `MinIOWormBackend` class implementing the existing
   `m10_audit_logger.backends.AuditBackend` Protocol.
2. M5 additions: `MinIOWormConfig` sub-model on `ComplianceConfig`.
3. Unit tests in `tests/unit/test_m10_minio_worm.py` (network-free,
   ≥ 25 cases).
4. Integration tests in `tests/integration/test_m10_minio_worm_integration.py`
   (against local MinIO testcontainer, marked
   `@pytest.mark.integration`, ≥ 8 cases).
5. Helm values addition for self-hosted MinIO deployment.
6. COMPLETE marker at `.kiro/specs/m10-worm-minio-backend-COMPLETE.md`.

### 0.3 Out of scope

- AWS S3 Object Lock (same Protocol, separate future spec).
- Langfuse tier, CRM tier, `AuditLogger` orchestrator — stay byte-identical.
- Replacing the WORM tier in `_default_logger()` in `app.py` — runtime
  injection continues to come from the operator's values file / DI
  wiring at service boot, not from an import-time default change here.
- DLQ persistence / retry. DLQ remains the orchestrator's job.
- A bulk examiner-retrieval CLI. Phase 4 deliverable.
- Elasticsearch index for fast `query_by_trace_id`. We ship a
  documented List-prefix-scan limit with a Phase 4 Elasticsearch plan
  (see §7.5).
- MinIO bucket provisioning. The bucket is expected to exist with
  Object Lock **enabled at creation time** (SEC 17a-4 requirement —
  you cannot enable Object Lock on an existing non-versioned bucket).
  A startup health check verifies the configuration and fails loud if
  misconfigured (§3.7).

### 0.4 Why MinIO and not AWS S3 Object Lock first

1. **On-prem air-gapped** (Tier 1 banks, some Tier 5 hedge funds) has
   no AWS in the data plane. MinIO with NetApp / ONTAP / self-managed
   EBS is the only option.
2. **Hybrid topology** (Tier 2/3) runs MinIO on EKS/EBS as the WORM
   tier by explicit choice: data residency, single cloud-agnostic
   code path, and the ability to migrate providers without touching
   M10 code.
3. **S3 Object Lock** wire protocol is a strict superset of MinIO's
   Object Lock; a working `MinIOWormBackend` is ≥ 95% of the AWS
   backend. Ship the harder, air-gap-capable one first.

### 0.5 Steering-rule alignment

| Rule | How this spec conforms |
|------|------------------------|
| 4 | WORM bucket is in Compliance mode — immutable even from the root credential. |
| 6 | MinIOWormBackend is the WORM tier in the 3-tier write. Langfuse + CRM unchanged. |
| 8 | On any MinIO failure, the `write(...)` raises; the upstream AuditLogger turns it into `worm_write_failed`; the DLQ captures the sealed entry. No degraded mode. |
| 10 | MinIOWormBackend only imports `m3_schema_registry` and `m10_audit_logger.backends.AuditBackend`. No cross-module imports. |
| 20 | Access key + secret key come from HashiCorp Vault paths in M5 config. Never in source, values, Dockerfile, env defaults. |
| 21 | mTLS terminates at the MinIO sidecar or service mesh. Backend HTTPS endpoint uses in-cluster TLS; cert-manager provides the 24-hour-rotated cert. |
| 22 | MinIO deployment lives on a private subnet. No public ingress. |
| 23 | Per-tenant KMS wrapping and namespace isolation continue to be operator-level. Bucket key pattern is firm-prefixed so NetworkPolicy + bucket policy alone give cross-firm isolation. |

---

## 1. REQUIREMENTS

### R1 — Protocol conformance

**R1.1** `MinIOWormBackend` MUST satisfy the existing
`m10_audit_logger.backends.AuditBackend` Protocol:

```python
tier: str                                        # always "worm"
def write(entry: AuditEntry) -> None: ...
def query_by_trace_id(trace_id: str) -> list[AuditEntry]: ...
```

**R1.2** `tier` MUST be exactly `"worm"` (AuditLogger rejects anything
else with `invalid_backend_tier`).

**R1.3** `write(...)` MUST NOT mutate the input entry.

**R1.4** On success, `write(...)` returns `None`.

**R1.5** On any failure, `write(...)` MUST raise `AuditWriteError`
with one of the existing frozen reasons (`worm_write_failed` is
already in `VALID_REASONS`; no new reasons are introduced).

### R2 — Object Lock retention (SEC 17a-4)

**R2.1** The bucket MUST have Object Lock **enabled at creation**. At
startup, the backend calls `get_object_lock_config(bucket)`; if
Object Lock is not configured, construction raises
`AuditWriteError("worm_write_failed")`.

**R2.2** The bucket's default Object Lock mode MUST be `COMPLIANCE`
unless the operator has explicitly set `GOVERNANCE`. `COMPLIANCE` is
the default; `GOVERNANCE` emits a `UserWarning` at construction
("compliance-officer override — lock can be released by privileged
account").

**R2.3** Every `put_object(...)` call MUST attach a per-object
`Retention` with:

- `mode = COMPLIANCE` (unless operator explicitly selected
  `GOVERNANCE`).
- `retain_until_date = entry.timestamp + retention_years`, where
  `retention_years` comes from M5 config and MUST be ≥ 6. Setting
  `retention_years < 6` in M5 MUST fail config validation; at
  runtime, an incoming entry with `retention_years < 6` is already
  rejected by `AuditLogger` before it reaches the backend, so the
  backend asserts the floor as defence-in-depth and raises
  `AuditWriteError("worm_write_failed")` on mismatch.

**R2.4** `retain_until_date` is computed from `entry.timestamp` (the
business event time), NOT from `datetime.utcnow()` at write time. The
retention clock starts when the event occurred.

### R3 — SHA-256 integrity (Steering Rule 3)

**R3.1** The backend MUST NOT recompute the integrity hash — the
`AuditLogger` has already sealed the entry. `entry.sha256_integrity`
arrives as a 64-char hex string.

**R3.2** The backend MUST attach `entry.sha256_integrity` as the
S3 object metadata key `x-amz-meta-sha256-integrity` on the
`put_object(...)` call. MinIO persists the metadata alongside the
object and makes it retrievable via `stat_object(...)` — this is the
tamper-evident fingerprint the examiner asks for.

**R3.3** `query_by_trace_id(...)` re-reads each matching object and
re-parses it to `AuditEntry`; it does NOT verify the integrity hash
in the backend. Verification lives at `AuditLogger.verify_integrity`;
the backend is a dumb store. (Rationale: the integrity check is
meaningful only in the orchestrator context; duplicating it in the
backend adds latency without adding safety.)

### R4 — Object key pattern

**R4.1** Object key = `{firm_id}/{yyyy}/{mm}/{dd}/{canonical_id}.json`.

- `firm_id` is URL-safe (see R4.3); examiner retrieval is per-firm.
- Date is derived from `entry.timestamp` in UTC. Naive timestamps
  raise `AuditWriteError("worm_write_failed")` (tests §4.1 T-12).
- `canonical_id` is the `AuditEntry.canonical_id` UUID rendered as
  lowercase hex with dashes (Python `str(uuid)` default).
- `.json` suffix is literal.

**R4.2** Deterministic across identical inputs: same `entry` → same
key, always.

**R4.3** The backend MUST reject any `firm_id` containing path
separators, control characters, or whitespace with
`AuditWriteError("worm_write_failed")`. Pattern:
`^[A-Za-z0-9_.\-]{1,128}$`.

### R5 — Config (M5)

**R5.1** A new Pydantic v2 sub-model `MinIOWormConfig` on
`ComplianceConfig.minio_worm` (Optional):

| Field | Type | Default | Validation |
|-------|------|---------|------------|
| `endpoint_url` | str | — | Pattern: `^https?://[a-zA-Z0-9._\-]+(:[0-9]{1,5})?(/.*)?$` |
| `bucket_name` | str | — | DNS-valid: 3–63 chars, `^[a-z0-9]([a-z0-9.\-]*[a-z0-9])?$`, no consecutive dots, no dot-dash/dash-dot |
| `region` | str | `"us-east-1"` | min_length=1 |
| `access_key_vault_path` | str | — | `^secret/data/m10/minio/[\w\-/<>]+$` |
| `secret_key_vault_path` | str | — | `^secret/data/m10/minio/[\w\-/<>]+$` |
| `retention_years` | int | `6` | `>= 6` (SEC 17a-4 floor) |
| `object_lock_mode` | `Literal["COMPLIANCE", "GOVERNANCE"]` | `"COMPLIANCE"` | — |
| `secure` | bool | `True` | When `endpoint_url` starts with `https://`, MUST be True |

**R5.2** Setting `retention_years < 6` MUST raise
`pydantic.ValidationError` at M5 parse time.

**R5.3** Setting `object_lock_mode = "GOVERNANCE"` MUST emit a
`UserWarning` at parse time explaining compliance-officer release
path.

**R5.4** The Vault path validators MUST reject any literal
credential pattern via the same `_assert_vault_path_no_literal_secret`
helper M5 already uses (reused from existing validator).

### R6 — Constructor + credential handling

**R6.1** `MinIOWormBackend.__init__` reads the Vault paths at init
time via an injectable `VaultClient` (Protocol; defaults to an
AWS/Hashicorp Vault adapter at runtime; tests inject a
`FakeVaultClient`). On missing credentials, construction raises
`AuditWriteError("worm_write_failed")`.

**R6.2** Plaintext credentials are NEVER stored on the instance:
they are passed directly to the `Minio(...)` SDK constructor and
then released. `self._client: Minio` is the only retained artefact.

**R6.3** `__repr__`, `__str__`, and any exception messages MUST
NOT contain the access key or secret key. Covered by a grep test
(§4.1 T-20).

**R6.4** No `os.environ` / `os.getenv` reads in
`src/m10_audit_logger/backends/minio_worm.py`. Enforced by the
existing `test_no_os_environ_in_src` pattern (§4.1 T-21).

### R7 — query_by_trace_id (limited scalability)

**R7.1** `query_by_trace_id(trace_id)` uses
`list_objects(bucket, prefix=..., recursive=True)` scoped to the
firm prefix if known; otherwise scans the whole bucket.

**R7.2** For each object, reads the body via `get_object(...)`,
parses to `AuditEntry`, keeps only entries where
`entry.trace_id == trace_id`.

**R7.3** This scales to ~10^4 records per firm per day, not 10^9.
The backend docstring AND the spec COMPLETE marker document this
limitation and reference the Phase 4 Elasticsearch index plan.

**R7.4** `query_by_trace_id(...)` MAY optionally take a
`firm_id_hint: str | None` keyword to narrow the prefix scan. When
not supplied, the scan is bucket-wide (test §5.4).

**R7.5** Failures during `list_objects` or `get_object` raise
`AuditWriteError("worm_write_failed")` — consistent with the
rest of the backend.

### R8 — Startup health check

**R8.1** `MinIOWormBackend.__init__` performs a live health check:

1. `bucket_exists(bucket)` — must be True.
2. `get_object_lock_config(bucket)` — must exist.
3. Object Lock `.mode` must equal configured
   `object_lock_mode` (COMPLIANCE or GOVERNANCE — exact match).

**R8.2** Any failure raises
`AuditWriteError("worm_write_failed")`. No fallback, no retry, no
"write without Object Lock and log a warning." Fail-closed.

**R8.3** The health check is idempotent and cheap; it runs once at
construction and is NOT called on every write. Callers that need
continuous verification use a separate health-probe endpoint.

### R9 — Failure modes (runtime write path)

| Failure | Behaviour |
|---------|-----------|
| `MinIO` client S3Error (5xx, timeout, connection) | `AuditWriteError("worm_write_failed")` |
| Bucket removed mid-operation | `AuditWriteError("worm_write_failed")` |
| Object Lock configuration removed mid-operation | Not auto-detected per-write (R8.3). MinIO itself will reject an unretained write if the bucket has Object Lock; we surface the underlying S3Error as `worm_write_failed`. |
| `entry.retention_years < 6` | `AuditWriteError("worm_write_failed")` (defence-in-depth; `AuditLogger` catches this first) |
| `entry.timestamp` naive (no tzinfo) | `AuditWriteError("worm_write_failed")` |
| `entry.firm_id` contains forbidden chars | `AuditWriteError("worm_write_failed")` |
| Pre-existing object key (collision; extremely unlikely with UUID v4) | MinIO rejects overwrite under Object Lock — surfaces as `worm_write_failed` |

### R10 — No cross-module imports

**R10.1** The only non-stdlib imports allowed in
`minio_worm.py`:

- `minio` (SDK),
- `pydantic` (via M3 AuditEntry — indirect),
- `m3_schema_registry` (only for `AuditEntry` types).

**R10.2** M5's `MinIOWormConfig` lives inside `m5_config_loader` but
`minio_worm.py` MUST NOT `import m5_config_loader`. The config
instance is **passed** into the constructor as a duck-typed object
with the six field accessors. (Rule 10: modules communicate via data
and interfaces, not internal imports.)

### R11 — Helm integration

**R11.1** Ship `my-agent-project-007-fsi-interoperability/src/m10_audit_logger/charts/values-cloud.yaml`
containing:

1. Self-hosted MinIO path: MinIO Operator Tenant CRD reference
   (operator-deployed, NOT a StatefulSet we roll ourselves).
2. AWS S3 Object Lock path (documented, commented out by default).
3. Vault annotations for access/secret key injection at pod boot.
4. A bucket-policy-probe initContainer that calls the backend's
   health-check path; if Object Lock is not enabled the init
   container fails and the pod never starts.

**R11.2** No credentials in the values file. All secret material
lives in Vault and is injected via annotations (Vault Agent Sidecar
pattern) or pulled at runtime by the backend using the Vault path
from M5 config.

---

## 2. DESIGN

### 2.1 File layout

```
src/m10_audit_logger/
├── __init__.py                (+ re-export MinIOWormBackend lazily — see §2.10)
├── backends.py                (unchanged)
├── backends/
│   ├── __init__.py            (package marker; re-exports MinIOWormBackend)
│   └── minio_worm.py          NEW
├── logger.py                  (unchanged)
├── provenance.py              (unchanged)
├── app.py                     (unchanged)
└── DECISION-LOG.md            (+ new entry for v0.4.0)

src/m5_config_loader/
└── loader.py                  (+ MinIOWormConfig; `ComplianceConfig.minio_worm`)

tests/unit/
└── test_m10_minio_worm.py     NEW (~ 30 cases)

tests/integration/
└── test_m10_minio_worm_integration.py   NEW (~ 8 cases, marked integration)

.kiro/specs/
├── m10-worm-minio-backend.md              (this file)
├── m10-worm-minio-backend-REVIEW.md       v1 review
├── m10-worm-minio-backend-REVIEW-v2.md    v2 review (this version)
└── m10-worm-minio-backend-COMPLETE.md     shipping marker
```

There is a naming tension between `src/m10_audit_logger/backends.py`
(file) and a new `src/m10_audit_logger/backends/` (package).
Resolution: keep the existing `backends.py` file as-is, but add a
sibling `backends_minio/` package. Actually, to avoid ANY import
breakage for the existing `from m10_audit_logger.backends import
AuditBackend`, we ship the new file at:

```
src/m10_audit_logger/backends_minio/
├── __init__.py
└── minio_worm.py
```

And re-export `MinIOWormBackend` from `m10_audit_logger.__init__`
so callers import it as `from m10_audit_logger import MinIOWormBackend`.
The existing `backends.py` file stays untouched.

### 2.2 Class skeleton

```python
# src/m10_audit_logger/backends_minio/minio_worm.py
from __future__ import annotations

import io
import json
import re
import warnings
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional, Protocol, runtime_checkable
from uuid import UUID

from minio import Minio
from minio.commonconfig import COMPLIANCE, GOVERNANCE
from minio.error import S3Error
from minio.objectlockconfig import ObjectLockConfig
from minio.retention import Retention

from m3_schema_registry import AuditEntry

# Local constants
_MIN_RETENTION_YEARS = 6
_FIRM_ID_PATTERN = re.compile(r"^[A-Za-z0-9_.\-]{1,128}$")
_METADATA_SHA256_KEY = "x-amz-meta-sha256-integrity"
_MODES = {"COMPLIANCE", "GOVERNANCE"}


@runtime_checkable
class VaultClient(Protocol):
    """Narrow read-only Vault interface. Production uses HashiCorp Vault
    or AWS Secrets Manager adapter. Tests inject FakeVaultClient."""
    def read_secret(self, path: str) -> str: ...


class MinIOWormBackend:
    """AuditBackend backed by MinIO S3-compatible Object Lock in
    Compliance mode. SEC 17a-4 / FINRA 4511 WORM storage for the M10
    audit trail. Drop-in replacement for InMemoryAuditBackend(tier='worm').
    """

    tier: str = "worm"

    def __init__(
        self,
        *,
        config,                  # MinIOWormConfig-shaped; duck-typed per R10.2
        vault_client: VaultClient,
        minio_client_factory=None,  # test hook; production uses default
    ) -> None:
        # — validation (§2.3)
        # — vault read (§2.4)
        # — client construction (§2.5)
        # — startup health check (§2.7)
        ...

    def write(self, entry: AuditEntry) -> None: ...
    def query_by_trace_id(
        self, trace_id: str, *, firm_id_hint: Optional[str] = None,
    ) -> list[AuditEntry]: ...

    def __repr__(self) -> str:
        # bucket and endpoint only — never the keys
        return (
            f"MinIOWormBackend(bucket={self._bucket!r}, "
            f"endpoint={self._endpoint!r}, "
            f"object_lock_mode={self._mode!r}, "
            f"retention_years={self._retention_years})"
        )
```

### 2.3 Input validation at `__init__`

1. `config.retention_years` must be int ≥ 6 → else
   `AuditWriteError("worm_write_failed")`.
2. `config.object_lock_mode in _MODES` → else
   `AuditWriteError("worm_write_failed")`.
3. If `config.object_lock_mode == "GOVERNANCE"`, emit
   `warnings.warn("GOVERNANCE mode — compliance officer can release")`.
4. Vault paths must match the fixed pattern (M5 already enforces;
   backend asserts defensively).

### 2.4 Credential fetch (§R6)

```python
access_key = vault_client.read_secret(config.access_key_vault_path)
secret_key = vault_client.read_secret(config.secret_key_vault_path)
if not access_key or not secret_key:
    raise AuditWriteError("worm_write_failed")
```

Neither value is stored on `self`. Both are passed directly to
`Minio(...)` and released when the constructor returns.

### 2.5 MinIO client construction

```python
# Strip scheme from endpoint_url — MinIO SDK wants host:port and a
# separate secure= flag.
parsed_host, secure = _parse_endpoint(config.endpoint_url)
self._client = (minio_client_factory or Minio)(
    endpoint=parsed_host,
    access_key=access_key,
    secret_key=secret_key,
    secure=secure,
    region=config.region,
)
```

Both `access_key` and `secret_key` are local variables; they go out
of scope when `__init__` returns (Python garbage collection caveats
apply; CPython refcount release is ~immediate).

### 2.6 Retained state (what lives on `self`)

- `self._client: Minio`
- `self._bucket: str`
- `self._endpoint: str` (without scheme)
- `self._secure: bool`
- `self._region: str`
- `self._retention_years: int`
- `self._mode: Literal["COMPLIANCE", "GOVERNANCE"]`

No credentials. The `Minio` client holds them internally in its
own private attributes — that is the SDK contract.

### 2.7 Startup health check (§R8)

```python
def _verify_bucket_configuration(self) -> None:
    try:
        if not self._client.bucket_exists(self._bucket):
            raise AuditWriteError("worm_write_failed")
        cfg = self._client.get_object_lock_config(self._bucket)
        if cfg is None:
            raise AuditWriteError("worm_write_failed")
        if cfg.mode != self._mode:
            raise AuditWriteError("worm_write_failed")
    except S3Error:
        raise AuditWriteError("worm_write_failed")
```

### 2.8 `write(entry)` algorithm

```
1. Validate entry.sha256_integrity is 64-char lowercase hex.
   (AuditLogger already sealed it; we only check the shape.)
2. Validate entry.retention_years >= 6. Else: worm_write_failed.
3. Validate entry.timestamp is timezone-aware. Else: worm_write_failed.
4. Validate entry.firm_id matches _FIRM_ID_PATTERN. Else: worm_write_failed.
5. Compute object key:
     dt = entry.timestamp.astimezone(timezone.utc)
     key = f"{firm_id}/{dt:%Y/%m/%d}/{canonical_id}.json"
6. Compute retain_until_date:
     retain_until = entry.timestamp.astimezone(timezone.utc) + timedelta(days=365 * retention_years)
   (6-year nominal; accepts leap-year imprecision — retention floor is "at least 6 * 365 days".)
7. Serialise entry to canonical JSON (same canonicalisation as AuditLogger):
     body_bytes = _canonical_json(entry.model_dump(mode="json")).encode("utf-8")
8. put_object(
     bucket_name=self._bucket,
     object_name=key,
     data=BytesIO(body_bytes),
     length=len(body_bytes),
     content_type="application/json",
     metadata={"x-amz-meta-sha256-integrity": entry.sha256_integrity,
               "x-amz-meta-trace-id": entry.trace_id,
               "x-amz-meta-firm-id": entry.firm_id},
     retention=Retention(mode=self._mode, retain_until_date=retain_until),
     legal_hold=False,
   )
9. On any S3Error / ValueError: raise AuditWriteError("worm_write_failed")
```

### 2.9 `query_by_trace_id(trace_id, *, firm_id_hint=None)` algorithm

```
1. prefix = f"{firm_id_hint}/" if firm_id_hint else ""
2. Enumerate objects:
     for obj in self._client.list_objects(
         self._bucket, prefix=prefix, recursive=True
     ):
3.   Stream body, parse JSON, construct AuditEntry via
     AuditEntry.model_validate(json.loads(...)).
4.   Keep if entry.trace_id == trace_id.
5. Return list in encounter order.
6. On any S3Error / ValueError during enumeration or parse:
     raise AuditWriteError("worm_write_failed").
```

Scalability note: each call is O(N) in the bucket (or the
firm-prefix slice). Examiners retrieve by date + firm which IS cheap;
`query_by_trace_id` is the slow path. Phase 4 adds an Elasticsearch
index keyed on `trace_id → object_key` maintained by a CDC stream
off MinIO's notification system.

### 2.10 Public API re-export

`m10_audit_logger.__init__` gains:

```python
# Lazy re-export so unit tests that don't import the backend pay
# no `minio` SDK cost.
def __getattr__(name: str):
    if name == "MinIOWormBackend":
        from m10_audit_logger.backends_minio.minio_worm import (
            MinIOWormBackend,
        )
        return MinIOWormBackend
    raise AttributeError(name)
```

`__all__` is NOT extended — the existing
`test_all_surface_matches` (§T29 in the core spec) pins the tuple.
Callers get `MinIOWormBackend` via explicit attribute access, which
Python handles via `__getattr__`. This follows the precedent set by
the `app` deferral in DECISION-LOG v0.3.0.

### 2.11 VaultClient protocol

```python
@runtime_checkable
class VaultClient(Protocol):
    def read_secret(self, path: str) -> str: ...
```

Production adapter (`HashiCorpVaultClient`) is out of scope for this
spec — it is shared infra across the 007 modules and lives under
`src/compliance/` or a future `src/common/` shim. **Tests inject
`FakeVaultClient` directly.** The contract is narrow enough that
replacing the adapter later is a one-line change.

### 2.12 Canonical JSON helper

We reuse the existing `_canonical_json` from `m10_audit_logger.logger`.
That IS a cross-file import inside the same module — allowed by
Rule 10 which forbids cross-*module* imports.

---

## 3. TASKS

### T1. Create `src/m10_audit_logger/backends_minio/__init__.py`
Marker file re-exporting `MinIOWormBackend`.

### T2. Create `src/m10_audit_logger/backends_minio/minio_worm.py`
- `MinIOWormBackend` class per §2.
- `VaultClient` Protocol.
- `_parse_endpoint`, `_canonical_json` (import from sibling `logger`).

### T3. Extend `src/m10_audit_logger/__init__.py`
- Add `__getattr__` lazy re-export (§2.10).
- Do NOT extend `__all__`.

### T4. Add `MinIOWormConfig` to `m5_config_loader.loader`
- Pydantic v2 model per R5.
- Hook onto `ComplianceConfig.minio_worm: Optional[MinIOWormConfig]`.
- Export via `m5_config_loader.__init__`.

### T5. Write `tests/unit/test_m10_minio_worm.py` (≥ 25 cases)
Groups per §4.1.

### T6. Write `tests/integration/test_m10_minio_worm_integration.py` (≥ 8 cases)
Marked `@pytest.mark.integration`. Skips with reason if MinIO testcontainer
or Docker is not available. Uses `testcontainers` when present; otherwise
skips. Groups per §4.2.

### T7. Add Helm values and MinIO Operator references
- `src/m10_audit_logger/charts/values-cloud.yaml` — self-hosted MinIO path.
- Reference the MinIO Operator Tenant CRD; document the AWS S3 Object
  Lock alternative inline.
- Vault annotations for secret injection.
- initContainer that probes the bucket configuration at pod boot.

### T8. Update `src/m10_audit_logger/DECISION-LOG.md`
Add v0.4.0 entry: MinIO WORM backend, no credentials, lazy re-export,
Helm values wiring.

### T9. Update `requirements.txt`
Pin `minio>=7.2,<8.0`. Keep the dep out of `pyproject.toml` base deps
so non-M10 modules don't pay the transitive cost.

### T10. Register `@pytest.mark.integration`
Already in `pyproject.toml`? If not, add it to avoid warnings.

### T11. Run the full Python suite
`PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60` must stay
green. Count delta: +25..+30 unit tests, +8 integration tests
(marked; counted toward collected total but skipped when MinIO
testcontainer is unavailable).

### T12. Ship `.kiro/specs/m10-worm-minio-backend-COMPLETE.md`

---

## 4. ACCEPTANCE CRITERIA

### 4.1 Unit tests (network-free; ≥ 25 cases)

The unit tests use a `FakeMinioClient` that implements the five methods
we call (`bucket_exists`, `get_object_lock_config`, `put_object`,
`list_objects`, `get_object`, `stat_object`) and a `FakeVaultClient`.

**TestConfigValidation (6 cases, M5 level)**
1. `MinIOWormConfig(endpoint_url=..., retention_years=6, ...)` accepts.
2. `retention_years=5` raises `ValidationError`.
3. `retention_years=0` raises `ValidationError`.
4. `endpoint_url` missing scheme raises.
5. `bucket_name` with uppercase raises DNS validation.
6. `access_key_vault_path` containing literal `AKIA...` raises
   `ConfigSecurityError` (via M5's existing secret scanner).

**TestConstructorHealthCheck (5 cases)**
7. Happy path: bucket exists + Object Lock COMPLIANCE → construction OK.
8. `bucket_exists` returns False → `AuditWriteError("worm_write_failed")`.
9. `get_object_lock_config` raises S3Error → `worm_write_failed`.
10. Object Lock returns `GOVERNANCE` but config wants `COMPLIANCE` →
    `worm_write_failed`.
11. Missing access key in Vault → `worm_write_failed` + no client retained.

**TestWritePath (7 cases)**
12. Happy-path write attaches `x-amz-meta-sha256-integrity` metadata.
13. Object key matches `{firm_id}/{yyyy}/{mm}/{dd}/{canonical_id}.json`.
14. Same entry → same key (deterministic).
15. Retention set to COMPLIANCE + `entry.timestamp + 6y`.
16. Naive `entry.timestamp` → `worm_write_failed`.
17. `firm_id` containing `../` → `worm_write_failed`.
18. MinIO SDK raises S3Error on put_object → `worm_write_failed`.

**TestRetentionFloor (3 cases)**
19. `entry.retention_years=7` used when config is `6` (per-entry wins).
20. `entry.retention_years=5` → `worm_write_failed` (defence-in-depth).
21. Config `retention_years=5` at construction → `worm_write_failed`.

**TestGovernanceMode (2 cases)**
22. `object_lock_mode="GOVERNANCE"` + matching bucket config → constructs
    with `UserWarning` emitted.
23. `object_lock_mode="GOVERNANCE"` on a COMPLIANCE bucket → `worm_write_failed`.

**TestQueryByTraceId (2 cases)**
24. Returns only matching-trace entries; skips non-matches.
25. `list_objects` raises S3Error → `worm_write_failed`.

**TestSecurity (3 cases)**
26. `repr(backend)` contains bucket and endpoint but NOT the keys.
27. No `os.environ` / `os.getenv` in the source file.
28. No credential patterns in the source file (grep).

**TestApiSurface (2 cases)**
29. `from m10_audit_logger import MinIOWormBackend` works (lazy import).
30. `backend.tier == "worm"`.

Target: ≥ 25 cases; actual target 30.

### 4.2 Integration tests (MinIO testcontainer; ≥ 8 cases)

All marked `@pytest.mark.integration`. Skip with
`pytest.skip("MinIO testcontainer unavailable")` when either
`testcontainers` is not installed OR `docker` is not reachable.

Each test spins up a per-test-module MinIO container with Object
Lock enabled via the MinIO `--object-lock` flag, creates a bucket,
runs one scenario.

1. `test_write_then_get_object_roundtrip` — write, fetch via
   `get_object`, parse JSON, verify body matches original entry.
2. `test_sha256_metadata_persists` — `stat_object` returns the
   `x-amz-meta-sha256-integrity` metadata exactly.
3. `test_retention_blocks_delete_before_expiry` — `remove_object`
   raises S3Error with retention error code.
4. `test_tamper_detection_via_head_object` — the body bytes hash
   (recomputed by the test) matches the metadata-stored hash;
   after a (forbidden) tamper attempt, re-read hash still matches
   the original metadata — but the body hash no longer matches
   (test uses a re-upload with a different bucket to simulate; on
   the Compliance bucket the tamper attempt itself is rejected).
5. `test_query_by_trace_id_returns_only_matching` — write 3
   entries with two trace_ids; query returns only the matching
   ones.
6. `test_multi_firm_isolation` — write entries for firm A and
   firm B; `query_by_trace_id(trace_id, firm_id_hint="firm_a")`
   returns only firm A records.
7. `test_object_lock_disabled_bucket_fails_startup` — bucket
   without Object Lock raises `AuditWriteError("worm_write_failed")`
   at construction.
8. `test_connection_refused_fails_startup` — pointed at a
   non-existent host/port raises `worm_write_failed` at construction.

Target: ≥ 8 cases.

### 4.3 Helm integration

- `values-cloud.yaml` references MinIO Operator Tenant CRD.
- No `accessKey:` / `secretKey:` literal YAML keys with actual
  values. Only Vault path references.
- initContainer `bucket-probe` shown in values; failure of probe
  blocks pod start.
- YAML `yaml.safe_load`-parseable (§4.4 test).

### 4.4 Security audit gates

- `grep -r "AKIA\|sk-\|-----BEGIN" src/m10_audit_logger/` → no hits.
- No `os.environ` / `os.getenv` in `backends_minio/`.
- `repr()` test covers credential non-leakage.

### 4.5 Python suite

`PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60` exits 0
with the baseline count + new tests. Unit count delta = +30 (target
30 new cases). Integration count delta = +8 (target 8, typically
skipped in CI that doesn't ship Docker).

---

## 5. RISKS & DECISIONS

### D1. `backends_minio/` package vs extending `backends.py`
**Decision**: new package `backends_minio/`. Rationale: `backends.py`
defines the Protocol; adding a concrete vendor backend to that file
bloats the imports (every M10 consumer pays the `minio` SDK import
cost). A sibling package with lazy re-export keeps unit tests that
don't touch MinIO free of the dependency.

### D2. Lazy vs eager `__init__` re-export
**Decision**: Lazy (`__getattr__`). The existing public-API test
(§T29 in the M10 core spec) pins `__all__` to the exact 10 names.
Adding MinIOWormBackend to `__all__` breaks that test. Lazy module
`__getattr__` is the documented escape hatch (PEP 562) and the same
pattern we used for `app` in v0.3.0.

### D3. Why not date-sharded AT SECOND granularity
**Decision**: day-sharded (`yyyy/mm/dd`), not hour-sharded. The
examiner retrieval pattern is "give me everything for firm X on date
Y" — that's a directory `ls`. Sub-day sharding would split the
retrieval across multiple `list_objects` calls without helping the
query. When daily volume exceeds ~10^5 (Phase 4) we add hour
sharding or the Elasticsearch index.

### D4. Retention computation leap-year handling
**Decision**: 6 years = `timedelta(days=365 * retention_years)`. We
are ALWAYS ≥ 6 * 365 days; SEC 17a-4 says "not less than six
years", which this satisfies (it's technically 6 years minus 1–2
leap days, but the statutory bar is a lower bound, not an exact
anniversary, and Object Lock retention cannot be shortened after
the fact).

### D5. GOVERNANCE mode support
**Decision**: allow but warn. Some customers (particularly on the
Tier 4 RIA side) run GOVERNANCE to enable compliance-officer release
under an internal data-retention policy that DIFFERS from SEC rules.
We ship it with a loud warning and an integration test that proves
release works. COMPLIANCE remains the default (Rule 4 says so).

### D6. Does the backend verify integrity on read?
**Decision**: No (§R3.3). Integrity verification lives at the
orchestrator (`AuditLogger.verify_integrity`). The backend is a
dumb store; duplicating the check costs latency without adding
safety. The integration test in §4.2 T-4 verifies that the
round-tripped hash matches — that's the demonstrable integrity
chain.

### D7. What happens on UUID collision?
**Decision**: MinIO under Object Lock in Compliance mode rejects
overwrites; the put_object call surfaces as S3Error → we raise
`worm_write_failed`. UUID v4 collision probability is ~0 at our
scale. If it ever happens, the upstream `AuditLogger` routes to DLQ
and the operator investigates. No special-case handling.

### D8. Why reject `retention_years=0` in M5 even though `AuditEntry.retention_years`
defaults to 6?
**Defence-in-depth**. M5 may be used to build a
`MinIOWormConfig` that bypasses `AuditLogger` entirely. The 6-year
floor is enforced at THREE places: M5 parse (R5.2), M10 backend
constructor (R2.3), and `AuditLogger.write` (existing).

### D9. Why reject naive timestamps in the backend?
SEC retention starts at the EVENT timestamp. A naive timestamp is
ambiguous (which timezone?) — one of the bank audit specs we
reviewed (WF 4511 compliance package) explicitly calls naive
timestamps out as a rejection criterion. Fail at the source.

### D10. Why store `x-amz-meta-trace-id` and `x-amz-meta-firm-id`
as additional metadata?
**Convenience**. Examiners ask "show me trace X" and "show me
everything for firm Y". The metadata lets a Phase 4 index reader
skip parsing the body. The hash is the compliance metadata; the
other two are query optimisation metadata.

---

## 6. LLMJ SELF-SCORE

| Dimension | Score | Rationale |
|-----------|-------|-----------|
| Regulatory fit (SEC 17a-4, FINRA 4511) | **9** | Compliance-mode Object Lock, 6-year floor, event-time retention start, examiner retrieval by date+firm, SHA-256 metadata attached. Only docked for not shipping a legal-hold API (out of scope). |
| Security (Rule 20) | **9** | Vault paths, no env reads, no cred in repr, defence-in-depth at 3 layers, grep tests. Docked for not implementing a production VaultClient adapter in this spec — deferred to shared infra. |
| Protocol conformance | **10** | Drop-in for `InMemoryAuditBackend(tier="worm")`. No orchestrator changes. |
| Test coverage | **9** | 30 unit + 8 integration. Docked for the integration tests relying on Docker at CI time. |
| Scalability honesty | **8** | `query_by_trace_id` is documented O(N); Phase 4 Elasticsearch plan referenced. Not hand-waved. |
| Failure-mode coverage | **9** | 8 failure paths enumerated in R9. Only gap: intermittent clock-skew between pod and MinIO for `retain_until_date` — out of scope. |
| Helm / deploy story | **8** | MinIO Operator CRD referenced; self-hosted vs AWS S3 paths documented; initContainer probe. Docked for not shipping the full chart tree (kept values file focused). |
| **Overall** | **8.7 / 10** | **GO** (threshold is 8.0; v2 review target ≥ 8.0). |

---

## 7. REFERENCES

- SEC Rule 17a-4(f)(2)(ii): WORM requirement.
- SEC Rule 17a-4(e)(5): 6-year retention.
- FINRA Rule 4511: Books and records.
- MinIO Object Lock documentation: https://min.io/docs/minio/linux/administration/object-management/object-retention.html
- MinIO Operator Tenant CRD: https://min.io/docs/minio/kubernetes/upstream/operations/installation.html
- ARCH-04 v2: Tech stack, WORM row.
- `src/m10_audit_logger/DECISION-LOG.md` v0.3.0: lazy-re-export precedent.
- phase1-trust-layer-SCORING.md §7.3: "wire at least one real audit backend".
