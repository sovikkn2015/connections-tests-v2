# M10 Audit Logger — Spec (v2)

> Module: M10 Audit Logger
> Phase: 1 (Trust Layer — second module after M1)
> Agent: 007-trust-agent
> Status: v2 (post-review, addresses F1..F24)
> Source docs: ARCH-09 (M10 row), ARCH-07 (stack), 007-consolidated-design-and-plan.md (Part 3, Part 9 Gap 2), IMPL-06 (Blocker 1 minimal archiving)

---

## 0. CONTEXT AND SCOPE

M10 is the audit logger for the 007 trust layer. It writes EVERY audit event
to THREE tiers atomically:

1. **Langfuse** — operational LLM observability
2. **S3 Object Lock WORM** — regulatory archive (SEC 17a-4, 6-year retention)
3. **CRM** — business record

If ANY tier fails, the audit write fails. If the audit write fails, the
originating request fails (fail-closed). Failed writes are appended to a
dead letter queue (DLQ) for retry/investigation — the DLQ does NOT bypass
the audit requirement.

M10 is called by M1, M6, M8 (entries from all trust pipeline stages) and
calls nothing. It is a pure sink.

### 0.1 Phase 1 scope (library with pluggable backends)

Phase 1 ships M10 as an importable Python library. The three backends
(Langfuse, S3 WORM, CRM) are INJECTED as Protocol implementations. Dev and
unit tests use `InMemoryAuditBackend` — a deterministic, in-memory
implementation that makes the fail-closed semantics testable without AWS /
Langfuse / Salesforce dependencies.

- Phase 1: three injectable `AuditBackend` protocol instances. Default dev
  wiring = 3 x `InMemoryAuditBackend`. The trust pipeline integration test
  uses the in-memory backends.
- Phase 2: real Langfuse SDK, real `boto3` S3 client with Object Lock in
  Compliance mode, real Salesforce REST client. The `AuditLogger` public
  surface and `AuditBackend` protocol are stable across the migration —
  only wiring changes.

### 0.2 Non-goals

- M10 does NOT read or query audit entries at scale (production reads go
  directly to Langfuse / S3 / CRM). A `query_by_trace_id` helper exists for
  debugging only. Production backends may raise `NotImplementedError` for
  `query_by_trace_id` — see R7.
- M10 does NOT perform retry/backoff inside `write(...)`. A failed tier
  write immediately raises `AuditWriteError`. Retry is the DLQ consumer's
  job (Phase 2).
- M10 does NOT mutate input entries. Every sealed entry is IMMUTABLE once
  written. No update operations. No delete. No overwrite of existing
  WORM objects.
- M10 does NOT generate `canonical_id`, `trace_id`, `actor_id`,
  `timestamp`, or any actor/action data — callers supply these on the
  `AuditEntry`. M10 only computes the SHA-256 integrity hash, attaches it,
  and fans out to three tiers.
- M10 does NOT import any other `m*_` module except `m3_schema_registry`
  (for `AuditEntry`, `ProvenanceStage`) and optionally `m5_config_loader`
  (for a retention years default, lazy import).
- M10 does NOT call OPA. Compliance decisions happen in M2/M4. M10 records
  the outcome.
- M10 has no HTTP surface in Phase 1. FastAPI wrapping is deferred.
- M10 does NOT filter MNPI. M4 does that before the entry reaches M10.
- M10 does NOT enforce `entry.module in m1..m13` — M3 is responsible for
  that validation at the schema layer (see R1.2 / F4). M10 treats
  `entry.module` as an opaque caller-supplied string.
- M10 does NOT bound the DLQ in Phase 1. A Phase 2 implementation MUST
  bound it (disk overflow, TTL).
- M10 writes the three tiers sequentially (determinism). Phase 2 may
  parallelize with careful DLQ handling.

### 0.3 Transport-agnostic

Backends are Protocols with a single `write(entry)` method. How a Phase 2
backend talks to Langfuse / S3 / Salesforce is that backend's concern.

### 0.4 Upstream caller contract (REQUIRED reading for M6 spec)

When `AuditLogger.write(...)` raises `AuditWriteError`, the originating
caller (typically M6 gateway) MUST:

1. NOT retry synchronously. The DLQ already holds the failed entry.
2. Return a hard failure to the client (HTTP 500 from M6's perspective).
3. NOT serve cached data as fallback (fail-closed).
4. NOT silently swallow the error.

This is the M10->M6 contract. M10 does not enforce this (it cannot — M6
runs in a separate process); the spec documents the expectation.

### 0.5 M3 version pinning

M10 depends on `m3_schema_registry` and uses `AuditEntry` + `ProvenanceStage`
as public data types. M3 breaking changes (field removals, type changes)
will break M10. Phase 1 pins: M3 semantic major version MUST match. A test
asserts `AuditEntry` has the fields M10 relies on (input_hash, output_hash,
sha256_integrity, retention_years, provenance_chain, trace_id).

---

## 1. REQUIREMENTS

### R1. AuditEntry Write Orchestration (3-tier atomic)

The `AuditLogger.write(entry)` method writes an `AuditEntry` to all three
backends. If ANY tier write raises, `write` raises `AuditWriteError`.

#### R1.1 Write pipeline

1. Validate `entry` is an instance of `m3_schema_registry.AuditEntry`
   (strict `isinstance` check, NOT duck-typed).
2. Validate `entry.sha256_integrity` is the empty string `""` on input.
   If non-empty, raise `AuditWriteError("invalid_entry")` — an
   already-sealed entry must not be resubmitted; the caller must pass a
   fresh unsealed entry. (F11)
3. Enforce retention: if `entry.retention_years is None or < 6`, raise
   `AuditWriteError("retention_too_short")`.
4. Compute SHA-256 integrity hash over the canonical payload (see R2).
5. Attach the hash to a new `AuditEntry` copy via Pydantic
   `model_copy(update={"sha256_integrity": <hex>})`. Input entry is NOT
   mutated.
6. Invoke `langfuse.write(sealed_entry)`.
7. Invoke `worm.write(sealed_entry)`.
8. Invoke `crm.write(sealed_entry)`.
9. If steps 6/7/8 all succeed, return the sealed `AuditEntry`.
10. If ANY of steps 6/7/8 raises, convert to
    `AuditWriteError("{tier}_write_failed")` where `{tier}` is one of
    `langfuse`, `worm`, `crm`. Append the sealed entry + reason to the
    DLQ (R6), then re-raise. Other tiers are NOT rolled back.

#### R1.2 AuditEntry.module is not validated by M10 (F4)

M10 records `entry.module` verbatim. Module name validation (regex
`^m(1[0-3]|[1-9])$`) is M3's responsibility. The M3 schema may add a
validator; M10 does not duplicate it. This is documented here so the
boundary is explicit.

#### R1.3 Acceptance criteria (R1)

- **AC-R1-1:** `write(entry)` with all three backends healthy returns a
  sealed `AuditEntry` whose `sha256_integrity` is a 64-char lowercase hex.
- **AC-R1-2:** The returned entry is a different object than the input
  entry (`entry is not sealed`). The input entry's `sha256_integrity`
  is still `""` after the call (proves non-mutation).
- **AC-R1-3:** After a successful write, all three in-memory backends
  contain the sealed entry (len == 1 each).
- **AC-R1-4:** If Langfuse raises, `write` raises
  `AuditWriteError("langfuse_write_failed")`. DLQ has 1 record.
  WORM and CRM are NOT invoked (their `entries` remain empty).
- **AC-R1-5:** If WORM raises, `write` raises
  `AuditWriteError("worm_write_failed")`. DLQ has 1 record. Langfuse
  has 1 entry (already written). CRM is NOT invoked.
- **AC-R1-6:** If CRM raises, `write` raises
  `AuditWriteError("crm_write_failed")`. DLQ has 1 record. Langfuse
  and WORM both have 1 entry (not rolled back).
- **AC-R1-7:** Passing a non-`AuditEntry` (dict, different Pydantic
  model, string) raises `AuditWriteError("invalid_entry")`. None of
  the three backends is invoked. DLQ is empty.
- **AC-R1-8:** An entry with `retention_years=5` raises
  `AuditWriteError("retention_too_short")`. No backend invoked. DLQ
  is empty.
- **AC-R1-9:** An entry with `retention_years=None` raises
  `AuditWriteError("retention_too_short")`. (The M3 default is 6, but
  a caller may explicitly set None — fail-closed.)
- **AC-R1-10:** An entry with `retention_years=6` succeeds.
  `retention_years=7` succeeds. `retention_years=100` succeeds.
- **AC-R1-11 (F11):** An entry with a non-empty `sha256_integrity` on
  input raises `AuditWriteError("invalid_entry")` — backends not invoked.
- **AC-R1-12 (F14/F12):** After sealing, re-writing the same UNSEALED
  entry through a fresh AuditLogger instance produces an IDENTICAL
  `sha256_integrity`. This proves determinism. (Tests a fresh unsealed
  entry twice, NOT the same sealed entry twice — that would fail
  AC-R1-11.)
- **AC-R1-13 (F18):** The sealed entry preserves every input field
  unchanged EXCEPT `sha256_integrity`. A field-by-field diff confirms
  no silent drops / renames / reorderings.

### R2. SHA-256 Integrity Hash

#### R2.1 Canonicalisation

The hash is computed over a deterministic JSON serialization of a
subset of the entry's fields — the "hash payload." The hash payload
EXCLUDES `sha256_integrity` itself.

Precise steps:

```python
dumped = entry.model_dump(mode="json", exclude={"sha256_integrity"})
canonical = json.dumps(dumped, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
integrity = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
```

Pydantic v2's `mode="json"` emits:
- `UUID` -> str
- `datetime` -> ISO-8601 string
- `Enum` -> `.value`

M10 pins the `datetime` format by configuring AuditEntry consumers to
produce timezone-aware datetimes; Pydantic v2's default ISO-8601
serialization for a `datetime(..., tzinfo=timezone.utc)` is
`"2026-04-14T12:00:00+00:00"` (or `"Z"` depending on version). M10
does NOT override Pydantic's default — it trusts the deterministic
output and pins the result in a golden vector. (F8)

`_canonical_json` is ONLY used for:
1. Hashing the AuditEntry (via `model_dump(mode="json", exclude=...)` first).
2. Hashing a provenance stage payload (where `payload` is arbitrary
   caller-provided data — raw dict, Pydantic model, primitive).

For case 2, an internal `_json_default` fallback converts UUID / datetime
/ Enum if the caller passes raw instances (not dumped JSON). For case 1,
the pydantic pre-dump already emits strings, so `_json_default` is not
exercised — and a test asserts this. (F7)

#### R2.2 Verify helper

`AuditLogger.verify_integrity(entry) -> bool` recomputes the hash from
the same canonicalisation and compares to `entry.sha256_integrity`.
Returns `True` on match, `False` otherwise. Does NOT raise.

#### R2.3 Acceptance criteria (R2)

- **AC-R2-1:** The hash is 64 lowercase hex chars (`re.fullmatch(r"[0-9a-f]{64}", hex)`).
- **AC-R2-2:** The hash is deterministic: building the same fresh
  unsealed entry twice and sealing each yields identical hashes.
- **AC-R2-3:** Changing any field of a sealed entry (except
  `sha256_integrity`) causes `verify_integrity` to return `False`.
- **AC-R2-4:** `verify_integrity` on a correctly sealed entry returns
  `True`.
- **AC-R2-5 (F5/F9/F17):** A GOLDEN VECTOR test: given the `_fixed_entry()`
  fixture (pinned UUIDs, timestamp, fields), the sealed hash equals a
  specific hex string computed INDEPENDENTLY during implementation by
  hand-constructing the expected canonical JSON and hashing it. The
  test includes both the pinned hex AND the independently-computed
  expected canonical JSON as a comment for future reviewers.
- **AC-R2-6:** `verify_integrity` on an entry with empty-string
  `sha256_integrity` returns `False`.
- **AC-R2-7 (F6):** List ordering IS significant: two entries identical
  in all fields EXCEPT `provenance_chain` order (e.g., reversed) produce
  DIFFERENT hashes. Test this explicitly.

### R3. ProvenanceChainBuilder (Gap 2)

Implements the per-stage SHA-256 hash chain for liability attribution
(ARCH-06 Gap 2). Each stage's hash is SHA-256 of:

```
previous_hash + "|" + stage + "|" + module + "|" + payload_hash + "|" + timestamp_iso
```

where:
- `previous_hash` = previous stage's hash (empty string for stage 0)
- `payload_hash` = SHA-256(canonical_json(payload)) — same
  `_canonical_json` as R2
- `timestamp_iso` = `timestamp.isoformat()` (timezone-aware UTC required)

#### R3.1 API

```python
class ProvenanceChainBuilder:
    """Per-stage SHA-256 chain for liability attribution (Gap 2).

    NOT thread-safe. Callers serialize per-trace.
    """
    def __init__(self) -> None: ...
    def append(self, *, stage: str, module: str,
               payload: Any, timestamp: datetime) -> ProvenanceStage: ...
    def chain(self) -> list[ProvenanceStage]: ...
    def head_hash(self) -> str: ...
    def verify(self) -> bool: ...
```

#### R3.2 Acceptance criteria (R3)

- **AC-R3-1:** An empty builder has `chain() == []` and `head_hash() == ""`.
- **AC-R3-2 (golden vector):** Appending one stage with pinned inputs
  produces a `ProvenanceStage.hash` equal to a specific hex computed
  INDEPENDENTLY (test comment documents the expected component string).
- **AC-R3-3:** Appending a second stage links correctly: its hash
  incorporates the first stage's hash (verifiable by recomputing).
- **AC-R3-4:** `verify()` on a freshly-built 2-stage chain returns `True`.
- **AC-R3-5:** Tampering with any stage's `hash` field causes `verify()`
  to return `False`.
- **AC-R3-6:** Tampering with any stage's `stage` / `module` /
  `timestamp` causes `verify()` to return `False`.
- **AC-R3-7:** `stage` and `module` MUST be non-empty strings —
  `ValueError` otherwise.
- **AC-R3-8:** `module` MUST match `^m(1[0-3]|[1-9])$`. `"m14"`, `"foo"`,
  `"M1"`, `""` all raise `ValueError`.
- **AC-R3-9:** `timestamp` MUST be timezone-aware. A naive datetime
  raises `ValueError`.
- **AC-R3-10:** The builder is explicitly NOT thread-safe (class
  docstring). No lock inside.
- **AC-R3-11 (F24):** A usage example test demonstrates the intended
  idiom: build a 2-stage chain, attach to AuditEntry via
  `provenance_chain=builder.chain()`, write, verify sealed entry's hash
  covers the chain (flipping chain order changes the entry hash —
  already covered by AC-R2-7).

### R4. AuditBackend Protocol + InMemoryAuditBackend

#### R4.1 Protocol

```python
@runtime_checkable
class AuditBackend(Protocol):
    tier: str  # "langfuse" | "worm" | "crm"
    def write(self, entry: AuditEntry) -> None: ...
    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]: ...
```

Contract:
- `write` MUST raise any exception to signal failure; return value is ignored.
- `query_by_trace_id`: InMemoryAuditBackend implements it (returns
  entries matching trace_id exactly, case-sensitive). Phase 2 backends
  MAY raise `NotImplementedError` (S3 Object Lock cannot query by
  trace_id efficiently). `AuditLogger.query_by_trace_id` catches
  `NotImplementedError` from the WORM backend and returns an empty
  list — this keeps the debug method safe in production. (F2)

#### R4.2 InMemoryAuditBackend

```python
class InMemoryAuditBackend:
    tier: str
    entries: list[AuditEntry]

    def __init__(self, *, tier: str,
                 fail_on_nth: Optional[int] = None,
                 fail_message: str = "injected_failure") -> None: ...
    def write(self, entry: AuditEntry) -> None: ...
    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]: ...
    def reset(self) -> None: ...
```

- `tier` must be in `VALID_TIERS` — else `ValueError`.
- `fail_on_nth`: if set, the Nth call to `write` raises
  `RuntimeError(fail_message)`. Counter increments BEFORE the fail check.
  Entries are appended AFTER the fail check, so failing writes do NOT add.
- `query_by_trace_id`: returns all entries where `entry.trace_id == trace_id`,
  exact match, case-sensitive, preserving insertion order. (F1)
- `reset()`: clears `entries` and the counter.

#### R4.3 Acceptance criteria (R4)

- **AC-R4-1:** `InMemoryAuditBackend(tier=t).tier == t` for each of the
  three valid tiers.
- **AC-R4-2:** `InMemoryAuditBackend(tier="x")` raises `ValueError`.
- **AC-R4-3:** `write(entry)` appends to `entries`.
- **AC-R4-4:** With `fail_on_nth=1`, the first `write` raises
  `RuntimeError("injected_failure")`, `entries` remains empty.
- **AC-R4-5:** With `fail_on_nth=2`, first write succeeds; second
  raises and does NOT append.
- **AC-R4-6:** `reset()` clears `entries` and the counter.
- **AC-R4-7 (F1):** `query_by_trace_id("t1")` returns only entries with
  `trace_id=="t1"`, in insertion order. Non-matching trace returns `[]`.
- **AC-R4-8 (F1):** `query_by_trace_id` is case-sensitive: asking for
  `"T1"` when the entry has `"t1"` returns `[]`.

### R5. AuditWriteError (Frozen Vocabulary)

Vocabulary (R5.1):

```
invalid_entry
retention_too_short
langfuse_write_failed
worm_write_failed
crm_write_failed
invalid_backend_tier
```

Shape (R5.2):

```python
class AuditWriteError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason
```

`str(exc) == exc.reason` always. No PII, no entry contents, no stack
trace strings in the message — reason only.

#### R5.3 Acceptance criteria (R5)

- **AC-R5-1:** `VALID_REASONS` is a frozenset with exactly the 6 strings.
- **AC-R5-2:** Every `AuditWriteError` raised by M10 has
  `.reason in VALID_REASONS`. Each failure path has a test.
- **AC-R5-3:** `str(exc) == exc.reason` for every error path.
- **AC-R5-4:** A grep of `src/m10_audit_logger/**/*.py` for the literal
  string `AuditWriteError(` yields ONLY constructors with arguments that
  are elements of `VALID_REASONS`. A test enumerates grep matches and
  asserts each arg string is in `VALID_REASONS`.

### R6. Dead Letter Queue

#### R6.1 Protocol + default

```python
@runtime_checkable
class AuditDLQ(Protocol):
    def enqueue(self, entry: AuditEntry, reason: str) -> None: ...

class InMemoryAuditDLQ:
    records: list[tuple[AuditEntry, str]]
    def enqueue(self, entry: AuditEntry, reason: str) -> None: ...
    def reset(self) -> None: ...
```

If `AuditLogger` is constructed without a DLQ, it creates a fresh
`InMemoryAuditDLQ` internally — guarantees failed entries are never lost
when DLQ is healthy.

#### R6.2 DLQ-failure handling (F10)

If `dlq.enqueue(...)` itself raises, M10:

1. Appends the entry to an internal `self._lost_entries: list[tuple[AuditEntry, str]]`
   list (bounded only by memory in Phase 1). This is the last-ditch
   fallback, inspectable via `AuditLogger.lost_entries()`.
2. Does NOT change the `AuditWriteError.reason` — the caller still sees
   the original tier failure reason, not a DLQ reason.
3. Does NOT log entry contents (security rule R8.3). A Phase 2
   implementation may emit a warning counter via a metrics backend.

#### R6.3 Acceptance criteria (R6)

- **AC-R6-1:** After a Langfuse failure, DLQ contains exactly one record
  `(entry, "langfuse_write_failed")`.
- **AC-R6-2:** After a WORM failure, DLQ contains exactly one record
  `(entry, "worm_write_failed")`.
- **AC-R6-3:** After a CRM failure, DLQ contains exactly one record
  `(entry, "crm_write_failed")`.
- **AC-R6-4 (F15):** A successful 3-tier write leaves DLQ empty AND
  `lost_entries()` empty.
- **AC-R6-5:** A custom DLQ instance whose `enqueue` raises does NOT
  mask the original tier failure reason. The raised `AuditWriteError`
  has the original tier reason; `lost_entries()` contains the failed
  entry with the original reason.
- **AC-R6-6 (F5):** DLQ is shared by reference if passed to multiple
  AuditLogger instances. A note in the constructor docstring documents
  this explicitly.

### R7. Query Interface (debug only)

`AuditLogger.query_by_trace_id(trace_id) -> list[AuditEntry]` delegates
to the WORM backend's `query_by_trace_id`. If the WORM backend raises
`NotImplementedError` (Phase 2 S3 Object Lock), M10 returns `[]`.

Docstring explicitly warns: production reads should go to Langfuse /
S3 / CRM directly.

#### R7.1 Acceptance criteria (R7)

- **AC-R7-1:** After writing 3 entries with `trace_id="t1"` and 1 with
  `trace_id="t2"`, `query_by_trace_id("t1")` returns all 3.
- **AC-R7-2:** `query_by_trace_id("unknown")` returns `[]`.
- **AC-R7-3:** Method delegates to WORM only (Langfuse and CRM not read).
  Test verifies by using a wrapped WORM that tracks calls.
- **AC-R7-4:** If WORM's `query_by_trace_id` raises
  `NotImplementedError`, `AuditLogger.query_by_trace_id` returns `[]`
  (does not propagate).

### R8. Security

- **AC-R8-1:** No signing key, API key, token, password, or connection
  string appears in `src/m10_audit_logger/**` or
  `tests/unit/test_m10_audit_logger.py`. Regex sweep:
  `AKIA|sk-[A-Za-z0-9]{20,}|Bearer\s+\S+|password\s*=\s*['"]`. Zero
  matches.
- **AC-R8-2:** No top-level env var reads in M10 source. `os.environ`
  is not imported/referenced.
- **AC-R8-3:** The module does NOT log entry contents. No `logging`
  calls, no `print`, no `stderr` writes of entry fields. Future
  logging (Phase 2) MAY log `trace_id` + `canonical_id` + `action`
  only — NEVER the payload or PII fields.
- **AC-R8-4:** Every error path raises `AuditWriteError` or `ValueError`.
  No bare `except:`. The tier-write wrapper uses
  `except Exception as exc` (narrow to `Exception`, never `BaseException`)
  and immediately re-raises as `AuditWriteError`.
- **AC-R8-5:** `str(exc) == exc.reason` for every `AuditWriteError`
  raised by M10. No extra text.

### R9. Integration

- **AC-R9-1:** M10 imports `AuditEntry` and `ProvenanceStage` from
  `m3_schema_registry`.
- **AC-R9-2:** M10 does NOT import from `m1_*`, `m2_*`, `m4_*`, `m6_*`,
  `m7_*`, `m8_*`, `m9_*`, `m11_*`, `m12_*`, `m13_*`. Verified by AST scan.
- **AC-R9-3:** M10 MAY import from `m5_config_loader` only to read a
  retention-years default. If used, the import is LAZY (inside a helper
  function), never module-level, so test runs that don't exercise that
  path do not require M5 to be importable. Phase 1 decision: M10 does
  NOT actually need M5 (the default is hardcoded as `MIN_RETENTION_YEARS
  = 6`). The optional-M5 allowance is forward-compatibility only.
- **AC-R9-4:** M10's public API surface equals `__all__` in
  `m10_audit_logger/__init__.py`.
- **AC-R9-5 (F20):** A test asserts `AuditEntry` has all fields M10
  relies on: `canonical_id, trace_id, timestamp, actor_id, action,
  module, decision, input_hash, output_hash, latency_ms, firm_id,
  worm_record_id, sha256_integrity, retention_years, provenance_chain`.
  Breaking changes in M3 will trip this test loudly.

### R10. Operational

- **AC-R10-1 (F16):** Writing 1,000 entries against in-memory backends
  completes in < 10 seconds on local developer hardware (relaxed from
  5s for CI tolerance). Test is gated by `@pytest.mark.perf` or similar
  — recommended but not blocking.
- **AC-R10-2:** `AuditLogger.health()` returns:
  ```python
  {
      "status": "ok",
      "tiers": ["langfuse", "worm", "crm"],
      "dlq_depth": N,
      "lost_depth": M,
      "min_retention_years": 6,
  }
  ```
  No secrets. No entry contents. Exact key set asserted.

---

## 2. DESIGN

### 2.1 Directory layout

```
my-agent-project-007-fsi-interoperability/
  src/
    m10_audit_logger/
      __init__.py    # Public API re-exports
      backends.py    # AuditBackend, InMemoryAuditBackend,
                     # AuditDLQ, InMemoryAuditDLQ, VALID_TIERS
      logger.py      # AuditLogger, AuditWriteError, hash helpers,
                     # MIN_RETENTION_YEARS, VALID_REASONS
      provenance.py  # ProvenanceChainBuilder (Gap 2)
  tests/
    unit/
      test_m10_audit_logger.py
```

### 2.2 Public API

```python
from m10_audit_logger import (
    AuditLogger,
    AuditWriteError,
    AuditBackend,
    InMemoryAuditBackend,
    AuditDLQ,
    InMemoryAuditDLQ,
    ProvenanceChainBuilder,
    MIN_RETENTION_YEARS,   # 6
    VALID_TIERS,           # ("langfuse", "worm", "crm")
    VALID_REASONS,         # frozenset of 6 strings
)
```

`__all__` in `__init__.py` lists exactly these names.

### 2.3 `backends.py` shape

```python
from typing import Protocol, Optional, runtime_checkable
from m3_schema_registry import AuditEntry

VALID_TIERS: tuple[str, ...] = ("langfuse", "worm", "crm")

@runtime_checkable
class AuditBackend(Protocol):
    tier: str
    def write(self, entry: AuditEntry) -> None: ...
    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]: ...

@runtime_checkable
class AuditDLQ(Protocol):
    def enqueue(self, entry: AuditEntry, reason: str) -> None: ...

class InMemoryAuditBackend:
    tier: str
    entries: list[AuditEntry]
    _counter: int
    _fail_on_nth: Optional[int]
    _fail_message: str

    def __init__(self, *, tier, fail_on_nth=None,
                 fail_message="injected_failure"): ...
    def write(self, entry): ...
    def query_by_trace_id(self, trace_id): ...
    def reset(self): ...

class InMemoryAuditDLQ:
    records: list[tuple[AuditEntry, str]]
    def enqueue(self, entry, reason): ...
    def reset(self): ...
```

### 2.4 `logger.py` shape

```python
MIN_RETENTION_YEARS: int = 6

VALID_REASONS: frozenset[str] = frozenset({
    "invalid_entry",
    "retention_too_short",
    "langfuse_write_failed",
    "worm_write_failed",
    "crm_write_failed",
    "invalid_backend_tier",
})

class AuditWriteError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

def _json_default(v): ...        # used ONLY by provenance stage payload hash
def _canonical_json(obj) -> str: ...
def _compute_integrity_hash(entry: AuditEntry) -> str: ...

class AuditLogger:
    _langfuse: AuditBackend
    _worm: AuditBackend
    _crm: AuditBackend
    _dlq: AuditDLQ
    _min_retention_years: int
    _lost_entries: list[tuple[AuditEntry, str]]

    def __init__(self, *, langfuse, worm, crm,
                 dlq=None, min_retention_years=MIN_RETENTION_YEARS): ...

    def write(self, entry: AuditEntry) -> AuditEntry: ...
    def verify_integrity(self, entry: AuditEntry) -> bool: ...
    def query_by_trace_id(self, trace_id: str) -> list[AuditEntry]: ...
    def health(self) -> dict: ...
    def lost_entries(self) -> list[tuple[AuditEntry, str]]: ...
```

Constructor validation:
- For each slot, `getattr(backend, "tier", None) == <slot_name>` — else
  `AuditWriteError("invalid_backend_tier")`. This handles the missing-
  attribute case cleanly. (F3)
- `min_retention_years >= MIN_RETENTION_YEARS` — else `ValueError`.

### 2.5 `provenance.py` shape

```python
import hashlib
import re
from datetime import datetime, timezone
from typing import Any
from m3_schema_registry import ProvenanceStage

_MODULE_PATTERN = re.compile(r"^m(1[0-3]|[1-9])$")

def _stage_hash(*, previous_hash: str, stage: str, module: str,
                payload: Any, timestamp: datetime) -> str: ...

class ProvenanceChainBuilder:
    """NOT thread-safe. Callers serialize per-trace."""
    _stages: list[ProvenanceStage]

    def __init__(self) -> None: ...
    def append(self, *, stage, module, payload, timestamp) -> ProvenanceStage: ...
    def chain(self) -> list[ProvenanceStage]: ...
    def head_hash(self) -> str: ...
    def verify(self) -> bool: ...
```

### 2.6 Security constraints

| Constraint | Enforcement |
|-----------|------------|
| No credentials | No `os.environ` reads. No hardcoded secrets. Test fixtures use plain labels. |
| Immutability | `write` returns a new sealed entry via `model_copy(update=...)`. Input not mutated. |
| Fail-closed | Every tier failure raises. DLQ is side channel, never masks. |
| Frozen vocab | `VALID_REASONS` frozenset. Grep enforces. |
| No MNPI leakage | Error messages carry reason only. No logging of entry contents. |
| No cross-module imports | AST scan. Only `m3_schema_registry` allowed. |
| Hash integrity | SHA-256 over canonical JSON excluding `sha256_integrity`. Golden vector pinned. |
| Tampering | Pre-populated `sha256_integrity` on input REJECTED. |

### 2.7 Module boundary

Allowed in `src/m10_audit_logger/**`:
- stdlib: `__future__`, `datetime`, `enum`, `hashlib`, `json`, `re`,
  `typing`, `uuid`
- third-party: `pydantic`
- project: `m3_schema_registry` (required); `m5_config_loader`
  (optional, LAZY only — not used in Phase 1)

Forbidden: `m1_*`, `m2_*`, `m4_*`, `m6_*`, `m7_*`, `m8_*`, `m9_*`,
`m11_*`, `m12_*`, `m13_*`.

### 2.8 AST cross-module import test

Algorithm (adapted from M1 spec §2.7):

For each `.py` file under `src/m10_audit_logger/`:
1. Read source, call `ast.parse(source)`.
2. Walk with `ast.walk`.
3. For every `ast.Import`: inspect each `alias.name`.
4. For every `ast.ImportFrom`: inspect `node.module`.

Forbidden prefixes (exact):
```
m1_, m2_, m4_, m6_, m7_, m8_, m9_, m11_, m12_, m13_
```

Allowed project prefixes: `m3_schema_registry`, `m5_config_loader`.

Any forbidden match fails with
`{file_path}:{lineno}: forbidden import {module}`.

### 2.9 OPA/Rego interaction

M10 contains zero Rego. Steering rule 19 (`wsp_section` annotation on
OPA rules) does not apply. M10 STORES `wsp_section` on AuditEntry but
does not produce rules. A test (AC-R1-13) confirms `wsp_section` is
preserved verbatim through write.

### 2.10 Error reason vocabulary (frozen)

```
invalid_entry          # entry not AuditEntry OR has non-empty sha256_integrity on input
retention_too_short    # retention_years is None or < 6
langfuse_write_failed  # Langfuse backend raised
worm_write_failed      # WORM backend raised
crm_write_failed       # CRM backend raised
invalid_backend_tier   # constructor: backend.tier missing or wrong value
```

A test enumerates these and asserts `VALID_REASONS == {...}`.

### 2.11 PyJWT-equivalent exception mapping

M10 does not use PyJWT. The tier-write wrapper catches `Exception`
broadly (NOT `BaseException`) and re-raises as
`AuditWriteError("{tier}_write_failed")`. Narrow-except is explicit
because backends are pluggable (they may raise arbitrary types).

### 2.12 Hash payload canonicalisation (precise)

```python
from datetime import datetime
from enum import Enum
from uuid import UUID
import hashlib
import json
from typing import Any

def _json_default(v: Any) -> Any:
    """Fallback only for the provenance-payload path.

    AuditEntry hash uses model_dump(mode='json', ...), which pre-dumps
    UUIDs/datetimes/Enums to strings — so this fallback is not reached
    on that path (a test asserts so).
    """
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, datetime):
        return v.isoformat()
    if isinstance(v, Enum):
        return v.value
    raise TypeError(f"not serializable: {type(v).__name__}")

def _canonical_json(obj: Any) -> str:
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, default=_json_default,
    )

def _compute_integrity_hash(entry) -> str:
    dumped = entry.model_dump(mode="json", exclude={"sha256_integrity"})
    return hashlib.sha256(
        _canonical_json(dumped).encode("utf-8")
    ).hexdigest()
```

### 2.13 Stage hash canonicalisation (Gap 2)

```python
def _stage_hash(*, previous_hash, stage, module, payload, timestamp):
    payload_canon = _canonical_json(payload)
    payload_hash = hashlib.sha256(payload_canon.encode("utf-8")).hexdigest()
    components = "|".join([
        previous_hash or "",
        stage,
        module,
        payload_hash,
        timestamp.isoformat(),
    ])
    return hashlib.sha256(components.encode("utf-8")).hexdigest()
```

### 2.14 Golden vector production (F9)

Golden vectors are computed INDEPENDENTLY during implementation:

1. Write down the fixed input by hand.
2. Construct the expected canonical JSON by hand (sorted keys,
   `(",",":")` separators, specific ISO timestamp format).
3. Compute SHA-256 via a one-liner:
   `python3 -c "import hashlib; print(hashlib.sha256('<json>'.encode()).hexdigest())"`.
4. Paste the hex into the test AND paste the expected JSON in a
   comment for reviewer verification.

The test then ALSO calls the implementation and asserts equality with
the pinned hex. If the implementation's canonicalisation deviates, the
test fails loudly.

### 2.15 Usage example (F24) — reference idiom

```python
from datetime import datetime, timezone
from m3_schema_registry import AuditEntry
from m10_audit_logger import (
    AuditLogger, InMemoryAuditBackend, ProvenanceChainBuilder,
)

# Build provenance chain across pipeline stages
builder = ProvenanceChainBuilder()
builder.append(
    stage="m1.verify",
    module="m1",
    payload={"jti": "abc", "sub": "sarah"},
    timestamp=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
)
builder.append(
    stage="m2.authority",
    module="m2",
    payload={"decision": "allow", "rule": "advisor.read_own_clients"},
    timestamp=datetime(2026, 4, 14, 12, 0, 1, tzinfo=timezone.utc),
)

# Build audit entry with the chain
entry = AuditEntry(
    canonical_id="11111111-1111-1111-1111-111111111111",
    trace_id="trace-001",
    timestamp=datetime(2026, 4, 14, 12, 0, 2, tzinfo=timezone.utc),
    actor_id="actor-hash-abc",
    action="portfolio.read",
    module="m6",
    decision="allow",
    input_hash="0" * 64,
    output_hash="1" * 64,
    latency_ms=42,
    firm_id="CRD-123456",
    worm_record_id="worm/key/001",
    sha256_integrity="",              # M10 fills this in
    provenance_chain=builder.chain(), # attach Gap 2 chain
    retention_years=6,
)

logger = AuditLogger(
    langfuse=InMemoryAuditBackend(tier="langfuse"),
    worm=InMemoryAuditBackend(tier="worm"),
    crm=InMemoryAuditBackend(tier="crm"),
)
sealed = logger.write(entry)
assert logger.verify_integrity(sealed)
```

---

## 3. TASKS

Each task produces implementation + tests together. Fail-closed tests
use `pytest.raises`.

| # | Task | Files | Covers ACs |
|---|------|-------|------------|
| T1 | Package skeleton (empty modules, `__init__.py` stubs) | 4 files | — |
| T2 | `backends.py`: `AuditBackend` / `AuditDLQ` Protocols, `VALID_TIERS` | `backends.py` | R4.1 |
| T3 | `backends.py`: `InMemoryAuditBackend` (incl. fail_on_nth, query_by_trace_id) + `InMemoryAuditDLQ` | `backends.py` | R4.2, R4.3, R6.1 |
| T4 | `logger.py`: `MIN_RETENTION_YEARS`, `VALID_REASONS`, `AuditWriteError`, `_json_default`, `_canonical_json`, `_compute_integrity_hash` | `logger.py` | R2.1, R5 |
| T5 | `logger.py`: `AuditLogger.__init__` with tier validation via `getattr` | `logger.py` | constructor + F3 |
| T6 | `logger.py`: `AuditLogger.write` with 3-tier orchestration, DLQ, lost_entries | `logger.py` | R1, R6 |
| T7 | `logger.py`: `verify_integrity`, `query_by_trace_id` (with NotImplemented handling), `health`, `lost_entries` | `logger.py` | R2.2, R7, R10.2, R6.2 |
| T8 | `provenance.py`: `_stage_hash`, `ProvenanceChainBuilder` with module regex + validation | `provenance.py` | R3 |
| T9 | `__init__.py` with re-exports + `__all__` | `__init__.py` | AC-R9-4 |
| T10 | Test: happy-path 3-tier write, sealed entry shape, hex format | test file | AC-R1-1..3 |
| T11 | Test: Langfuse failure -> DLQ + reason + WORM/CRM not invoked | test file | AC-R1-4, AC-R6-1 |
| T12 | Test: WORM failure -> DLQ + reason + Langfuse written, CRM not invoked | test file | AC-R1-5, AC-R6-2 |
| T13 | Test: CRM failure -> DLQ + reason + Langfuse/WORM written | test file | AC-R1-6, AC-R6-3 |
| T14 | Test: invalid_entry (dict, model, pre-sealed), retention edge cases | test file | AC-R1-7..11 |
| T15 | Test: deterministic hash, golden vector for AuditEntry, exclusion of sha256_integrity | test file | AC-R2-1..5 |
| T16 | Test: `verify_integrity` true/false/tampered/empty | test file | AC-R2-3, R2-4, R2-6 |
| T17 | Test: provenance_chain order matters for hash | test file | AC-R2-7 |
| T18 | Test: ProvenanceChainBuilder — empty, single-stage golden, chain link, verify, tamper | test file | AC-R3-1..6 |
| T19 | Test: ProvenanceChainBuilder validation — empty strings, bad module, naive timestamp | test file | AC-R3-7..9 |
| T20 | Test: ProvenanceChainBuilder thread-safety comment present (docstring inspection) | test file | AC-R3-10 |
| T21 | Test: Usage idiom — chain + entry, sealed entry verifies | test file | AC-R3-11 |
| T22 | Test: InMemoryAuditBackend tier validation, fail_on_nth 1/2, reset, query | test file | AC-R4-1..8 |
| T23 | Test: frozen reason vocabulary + grep scan of source | test file | AC-R5-1..4 |
| T24 | Test: DLQ empty on success + DLQ-failure does not mask reason + lost_entries captured | test file | AC-R6-4..5 |
| T25 | Test: DLQ-shared-by-reference note | test file | AC-R6-6 |
| T26 | Test: `query_by_trace_id` happy path, unknown, WORM-only, NotImplementedError tolerated | test file | AC-R7-1..4 |
| T27 | Security tests: no credentials regex scan; no `os.environ`; no logging | test file | AC-R8-1..5 |
| T28 | AST import test: forbidden/allowed prefixes | test file | AC-R9-1..3 |
| T29 | `__all__` surface test + M3 compatibility test | test file | AC-R9-4, AC-R9-5 |
| T30 | Perf sanity test (1,000 writes < 10s) marked as perf | test file | AC-R10-1 |
| T31 | `health()` shape test | test file | AC-R10-2 |
| T32 | Write-twice determinism test (fresh unsealed entries) | test file | AC-R1-12 |
| T33 | Field preservation test (sealed entry vs input, all non-hash fields equal) | test file | AC-R1-13 |

Test count target: 45-55. Every AC maps to at least one test.

### 3.1 Test fixture policy

```python
from datetime import datetime, timezone
from uuid import UUID
from m3_schema_registry import AuditEntry

def _fixed_entry() -> AuditEntry:
    """Deterministic fixture for golden-vector tests. No credentials."""
    return AuditEntry(
        canonical_id=UUID("11111111-1111-1111-1111-111111111111"),
        trace_id="trace-fixed-001",
        timestamp=datetime(2026, 4, 14, 12, 0, 0, tzinfo=timezone.utc),
        actor_id="actor-hash-abc",
        action="test.action",
        module="m10",
        decision="allow",
        input_hash="0" * 64,
        output_hash="1" * 64,
        latency_ms=5,
        firm_id="CRD-123456",
        worm_record_id="worm/key/fixed",
        sha256_integrity="",  # will be sealed by AuditLogger.write
        retention_years=6,
    )
```

No credentials. No real API keys. No Bearer tokens. No AKIA/sk-/
password=... patterns.

### 3.2 Golden vectors — independent computation

The test file includes the expected canonical JSON in a comment block
above the pinned hex, so any reviewer can recompute locally:

```python
# Expected canonical JSON for _fixed_entry (independent computation):
# {"action":"test.action","actor_id":"actor-hash-abc","archetype":null,...}
# SHA-256 of the above (utf-8 bytes):
# <pinned-hex>
EXPECTED_ENTRY_HASH = "<pinned-hex>"
```

---

## 4. REVIEW FIX TRACEABILITY (v1 -> v2)

| Review Fix | Spec Section Addressing It |
|-----------|----------------------------|
| F1 — InMemoryAuditBackend.query_by_trace_id behavior | R4.2, AC-R4-7, AC-R4-8 |
| F2 — Phase 2 backend NotImplementedError contract | R4.1 contract, R7, AC-R7-4 |
| F3 — Missing-tier-attribute path | §2.4 constructor, uses `getattr(backend, "tier", None)` |
| F4 — AuditEntry.module validation boundary | R1.2 explicit non-enforcement; §0.2 non-goal |
| F5 — DLQ sharing note | AC-R6-6, constructor docstring |
| F6 — List order hash significance | AC-R2-7 |
| F7 — `_json_default` scope | §2.12 docstring, "test asserts so" comment |
| F8 — datetime ISO format pinned via golden vector | R2.1 final paragraph, AC-R2-5 |
| F9 — Independent golden vector computation | §2.14, §3.2 |
| F10 — DLQ-failure mechanism (lost_entries) | R6.2, AC-R6-5, `lost_entries()` method |
| F11 — Pre-populated sha256_integrity rejected | R1.1 step 2, AC-R1-11 |
| F12 — Write-twice idempotence semantics | AC-R1-12 (fresh entries, not sealed replay) |
| F13 — DLQ unbounded note | §0.2 non-goal |
| F14 — Write-twice test | T32 |
| F15 — DLQ-empty-on-success test | AC-R6-4, T24 |
| F16 — Perf test relaxed to 10s + marked perf | AC-R10-1, T30 |
| F17 — Separate golden vectors per hash flavor | T15 (entry), T18 (stage) |
| F18 — Field preservation test | AC-R1-13, T33 |
| F19 — M6 integration note | §0.4 upstream caller contract |
| F20 — M3 version pinning | §0.5, AC-R9-5 |
| F21 — Health check scope | §0.2 non-goal; AC-R10-2 is metadata-only |
| F22 — Sequential vs parallel phase note | §0.2 non-goal |
| F23 — Upstream caller contract | §0.4 |
| F24 — Usage example | §2.15 reference idiom, T21 |

---

## 5. DESIGN DOC TRACEABILITY

| Design doc requirement | Spec section |
|------------------------|--------------|
| ARCH-09 M10 row: 3-tier Langfuse + S3 WORM + CRM, SHA-256, 6-year, fail-closed | R1, R2, AC-R1-8..10 |
| ARCH-09: M10 called by M1, M6, M8; calls nothing | §0.2 non-goals |
| ARCH-07: Python + FastAPI + Langfuse | §0.1 (Phase 1 library; FastAPI deferred) |
| Consolidated Part 3: "M10: LOG EVERYTHING" | R1 |
| Consolidated Part 9 Gap 2: per-stage SHA-256 chain | R3 |
| IMPL-06 Blocker 1: minimal archiving on M10 for Phase 2 | R1 (3-tier) + R7 (query debug) |
| Steering rule 3 (SHA-256 integrity hash on every write) | R2 |
| Steering rule 4 (WORM S3 Object Lock, 6-year) | R1.1 step 3, AC-R1-8..10 |
| Steering rule 6 (three-tier audit, all required) | R1, AC-R1-4..6 |
| Steering rule 7 (fail-closed) | R1, AC-R1-4..6, §0.4 |
| Steering rule 8 (DLQ for retry, request still fails) | R6, AC-R6 |
| Steering rule 9 (zero credentials) | R8, AC-R8-1..2 |
| Steering rule 10 (no cross-module imports) | R9, §2.7, §2.8 |
| Steering rule 13 (per-stage SHA-256 provenance chain) | R3 |

---

*m10-audit-logger.md (v2) — M10 Audit Logger Spec*
*Project 007 FSI Interoperability Platform*
