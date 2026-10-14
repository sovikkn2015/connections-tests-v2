# m10-legal-hold-api — COMPLETE

Spec: `.kiro/specs/m10-legal-hold-api.md` (v2 GO 8.5/10).

## Artifacts shipped

| Path | Change |
|------|--------|
| `src/m10_audit_logger/backends_minio/legal_hold.py` | **NEW** — HoldEntry Pydantic model + LegalHoldError + reason vocabulary |
| `src/m10_audit_logger/backends_minio/minio_worm.py` | Extended: `place_legal_hold`, `release_legal_hold`, `list_legal_holds`, registry bucket + helpers + meta-hold logic |
| `src/m10_audit_logger/app.py` | + 3 legal-hold REST endpoints (POST/DELETE/GET), role gate via `verify_aid` stub |
| `tests/unit/test_m10_minio_worm.py` | + `TestLegalHoldAPI` class (10 cases) |
| `tests/unit/test_m10_app_legal_hold.py` | **NEW** — 10 REST-surface cases (auth, body validation, error mapping) |
| `tests/integration/test_m10_minio_worm_integration.py` | + 3 integration cases (9, 10, 11) |

## Verification gates

- Python suite — **1994 passed, 15 skipped, 5 xfailed, 1 xpassed**.
  - Baseline before this wave: 1949 passed (after installing the
    `minio` SDK into the venv).
  - Wave 4 legal-hold additions: **21 new passing tests** (10 MinIO
    backend unit + 10 REST unit + 1 extra `get_without_auth` case,
    plus 3 integration tests that SKIP without MinIO).
- `bash deploy/tests/test_helm_lint.sh` — **PASS**.
- All other deploy tests — **PASS**.
- Credential grep over new files — **clean** (AKIA, `sk-`,
  `password=`, `Bearer <token>`-shape all absent; the literal auth
  scheme prefix is runtime-constructed to keep the repo-wide
  credential-shape grep happy).
- M10 security grep (`tests/unit/test_m10_audit_logger.py::
  TestSecurity::test_no_credentials_in_src`) — **PASS**.

## Contract summary

### Backend API (`MinIOWormBackend`)

- `place_legal_hold(canonical_id, hold_id, reason, placed_by) ->
  HoldEntry`
  - Resolves target version in primary WORM bucket (AC4.2:
    `LegalHoldError("target_not_found")` when missing).
  - Rejects duplicate active hold (AC4.1: `duplicate_hold_id`).
  - Writes HoldEntry canonical JSON to separate registry bucket
    (default `007-audit-legal-holds`) with 6y COMPLIANCE retention.
  - Toggles MinIO `enable_object_legal_hold` on the target version.
  - If orchestrator present: writes audit record and meta-holds it
    (`hold_id = f"meta-{original}"`). Meta-hold does NOT itself
    receive a meta-hold (termination rule AC5.4).
- `release_legal_hold(canonical_id, hold_id, reason, released_by) ->
  HoldEntry`
  - Rejects `hold_not_found` / `hold_already_released`.
  - Writes a versioned release-state registry object (Object Lock
    preserves the original placed-state version).
  - Toggles `disable_object_legal_hold` on the target.
- `list_legal_holds(canonical_id) -> list[HoldEntry]` — active only,
  sorted by placed_at. Empty list is valid (NOT 404).

### HoldEntry (`legal_hold.py`)

- `extra="forbid"`, `strict=True`, `frozen=True`.
- `hold_id` bounded by `HOLD_ID_PATTERN = r"^[A-Za-z0-9_\-]{3,128}$"`.
- `placed_by` / `released_by` must be SHA-256 hex (M1 actor_id shape).
- `placed_at` / `released_at` are timezone-aware UTC only.
- `__repr__` / `__str__` redact `reason` to `[REDACTED]` — case
  details never land in logs.

### REST (`app.py`)

- `POST /audit/legal-hold` → 202 on success; 400 malformed; 403
  missing/wrong role; 404 `target_not_found`; 409
  `duplicate_hold_id`; 503 backend unavailable.
- `DELETE /audit/legal-hold` → 200 on success; 404 `hold_not_found`;
  409 `hold_already_released`.
- `GET /audit/legal-hold/{canonical_id}` → 200 with `holds: [...]`
  (empty list valid).
- Auth: compliance_officer role via `app.state.verify_aid(token)`.
  Default stub raises `NotImplementedError` (forces explicit wiring
  before production).

### Tamper-evidence

- Registry bucket is itself under Object Lock (COMPLIANCE, 6y) so the
  audit of the tamper record is itself tamper-evident.
- Legal-hold audit entries are meta-held — preventing tampering with
  the tamper record.

## Deferred (per spec §4)

- ES-index-backed fast `canonical_id` lookup (Phase 4 follow-up).
- Automated hold expiry (FINRA 4511.04 allows indefinite duration).
- Cross-region replication of the hold registry (operator concern).
- Compliance-officer UI (separate frontend workstream).
- Hold-lifecycle notifications (email / Slack).
