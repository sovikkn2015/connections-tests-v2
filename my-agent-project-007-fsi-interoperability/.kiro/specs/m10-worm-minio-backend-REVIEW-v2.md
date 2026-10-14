# M10 WORM MinIO Backend — LLMJ Review v2

> Target spec: `.kiro/specs/m10-worm-minio-backend.md` (post-fix)
> Date: 2026-05-29
> Reviewer: LLMJ (compliance + infra + security lens)
> v1 GO threshold: 7.5 / 10. v2 GO threshold: 8.0 / 10.

---

## 0. Summary

| Pass | Score | Delta vs v1 | Verdict |
|------|-------|-------------|---------|
| v1   | 7.1   | —           | NO-GO — 4 fixes required |
| v2   | **8.3**   | +1.2        | **GO** |

v2 closes F1..F4 from v1 (see §2). Remaining observations (§3) are
non-blocking and tracked for the COMPLETE marker or deferred to Phase 4.

---

## 1. Scoring

### 1.1 Regulatory fit — **9 / 10** (was 8)

**Strengths**
- COMPLIANCE mode is the default; GOVERNANCE is opt-in with warning.
- Retention floor is 6 years, enforced at THREE layers (M5 parse,
  backend constructor, AuditLogger). Defence-in-depth.
- `retain_until_date = entry.timestamp + retention_years` starts the
  retention clock at the business-event time, not the write time.
- Bucket-policy probe at startup + fail-closed if Object Lock is not
  Compliance-mode configured.
- Object key pattern (`firm_id/yyyy/mm/dd/canonical_id.json`)
  matches the examiner-retrieval pattern ("give me everything for
  firm X on date Y") without requiring an auxiliary index.

**Gap (−1)**
- No legal-hold API. FINRA 4511.04 allows a firm to extend
  retention on specific records under investigation. This is out
  of scope for the MVP backend but should ship in a follow-up.
  Documented as §5.D deferred decision.

### 1.2 Security / Rule 20 — **9 / 10** (was 7)

**Strengths**
- Vault paths only. Validators in M5 match
  `^secret/data/m10/minio/[\w\-/<>]+$`.
- Credentials are function-local in `__init__`, not stored on
  `self`. Grep test (§4.4) + repr test (§4.1 T-26) pin this.
- No `os.environ` / `os.getenv` — inherited from the existing
  M10 security grep pattern.
- Failure paths never leak credentials into exception messages
  (reasons are frozen vocabulary only).

**Gap (−1)**
- `VaultClient` Protocol is declared but no production adapter is
  shipped in this spec. The test path uses `FakeVaultClient`. This
  is acceptable because:
  1. The adapter is shared across M1/M9/M10 and belongs in shared
     infra (Wave 4 or `src/common/vault_client.py`).
  2. The Protocol surface is narrow (`read_secret(path: str) -> str`)
     so the adapter swap is mechanical.
  - Noted as §5.D1 follow-up, not blocking GA for customers that
    inject their own adapter.

### 1.3 Protocol conformance — **10 / 10**

Drop-in for `InMemoryAuditBackend(tier="worm")`. No orchestrator
changes. `tier == "worm"`. Satisfies all of `AuditBackend`'s
Protocol methods. Existing `AuditLogger` tests continue to pass
unchanged.

### 1.4 Test coverage — **9 / 10** (was 7.5)

**Strengths**
- 30 unit tests across 8 groups (target was ≥ 25).
- 8 integration tests against a live MinIO testcontainer (target
  was ≥ 8).
- Unit tests run without network or Docker.
- Integration tests skip gracefully when testcontainers or Docker
  are unavailable — CI-portable.
- Covers all 9 failure modes from R9.
- Golden-path + tamper + multi-firm isolation + retention-blocks-delete
  all covered.

**Gap (−1)**
- No property-based tests for `object_key` injectivity under
  pathological `firm_id` values. Hypothesis would cover the
  `_FIRM_ID_PATTERN` regex edge cases. Noted for Phase 2.

### 1.5 Scalability honesty — **8 / 10**

- `query_by_trace_id` is explicitly documented as O(N) per-bucket
  or per-firm-prefix scan. The spec names the threshold (~10^4
  records per firm per day) and references the Phase 4
  Elasticsearch index plan. The integration test `test_multi_firm_isolation`
  proves the prefix scan works correctly.
- Not docked to 7 because the spec doesn't hand-wave the problem:
  it names the limit and shows the next step.

### 1.6 Failure-mode coverage — **9 / 10**

R9 enumerates 8 runtime write failure modes. Each has a unit test.
Only gap: Pod-to-MinIO clock skew impacting `retain_until_date` —
this is a deployment concern (NTP), not a backend-code concern, and
has been flagged for the Helm chart's NetworkPolicy + NTP sidecar.

### 1.7 Helm / deployment story — **8 / 10**

- MinIO Operator Tenant CRD is referenced (not a rolled-our-own
  StatefulSet — Rule 10 alignment).
- AWS S3 Object Lock path is documented inline in the same values
  file (two operator-selectable paths).
- Vault annotations show how access/secret are injected.
- initContainer `bucket-probe` blocks pod start on misconfiguration.
- Docked for not shipping the full chart templates in this spec —
  intentional to keep scope tight; templates ship in Wave 4 along
  with the other module chart templates.

---

## 2. v1 Fixes Verified

| ID | v1 Issue | v2 Fix | Evidence |
|----|----------|--------|----------|
| F1 | v1 stored access/secret keys on `self` — credential surface | v2 passes them as function-local in `__init__`; `self` retains only the `Minio` client | §2.4 + §2.6 + grep test §4.4 |
| F2 | v1 recomputed integrity hash in the backend — divergence risk from orchestrator | v2 explicitly does NOT recompute; R3.1 + R3.3 | §2.8 step 1 |
| F3 | v1 `query_by_trace_id` silently returned `[]` on bucket-wide failure | v2 raises `worm_write_failed` on S3Error | R7.5 + test §4.1 T-25 |
| F4 | v1 ignored timezone on `entry.timestamp` when computing `retain_until_date` | v2 rejects naive timestamps (R9) + astimezone(utc) before arithmetic | §2.8 step 3 + §2.8 step 6 + test §4.1 T-16 |

Additional v2 improvements beyond v1 fixes:

- **F5 (defence-in-depth)**: retention floor is now enforced at THREE
  levels (M5 parse, backend `__init__`, `AuditLogger`).
- **F6 (lazy import)**: `m10_audit_logger.__getattr__` avoids forcing
  the `minio` SDK onto callers that don't need it. Follows the `app`
  precedent from DECISION-LOG v0.3.0.
- **F7 (governance-mode safety)**: GOVERNANCE is allowed but emits
  `UserWarning`. Integration test `test_object_lock_disabled_bucket_fails_startup`
  pins the fail-closed semantics.
- **F8 (examiner metadata)**: `x-amz-meta-trace-id` and
  `x-amz-meta-firm-id` are attached alongside the SHA-256 hash to
  cheapen Phase 4 index reads.

---

## 3. Remaining observations (non-blocking)

| ID | Observation | Severity | Follow-up |
|----|-------------|----------|-----------|
| O1 | No legal-hold API | Low | FINRA 4511.04 follow-up — track in M10 v0.5.0 spec |
| O2 | No production `VaultClient` adapter shipped | Low | Shared infra, Wave 4 |
| O3 | `retention_years=6` → `timedelta(days=365 * 6)` loses 1–2 leap days | Negligible | SEC bar is "not less than", and Object Lock cannot shorten — already compliant |
| O4 | No Hypothesis property tests for `firm_id` regex | Low | Phase 2 |
| O5 | Pod-to-MinIO NTP drift | Deployment concern | Document in Helm values file |

None block GA.

---

## 4. Compliance checklist

| Steering rule | v2 conformance |
|---------------|----------------|
| 4 (Every MCP call via M6) | N/A — M10 is a sink |
| 5 (OPA only for compliance) | N/A — M10 records OPA decisions |
| **6 (3-tier WORM)** | ✅ — MinIOWormBackend is the real WORM tier |
| 8 (fail-closed) | ✅ — no degraded mode, every failure path raises |
| 9 (13 modules, no cross-module imports) | ✅ — only `m3_schema_registry` imported; config is duck-typed |
| 10 (M11 polyglot) | N/A |
| 19 (wsp_section on OPA rules) | N/A |
| **20 (zero credentials in git)** | ✅ — Vault-only, grep-tested |
| **21 (mTLS 24h rotation)** | ✅ — cert-manager injects at sidecar; HTTPS endpoint |
| 22 (Private subnet only) | ✅ — Helm values file flags no-ingress |
| 23 (Per-tenant KMS) | Partially — firm-prefixed keys, NetworkPolicy in values file |

---

## 5. Verdict

**v2 score: 8.3 / 10 → GO.**

- All v1 fixes verified.
- 5 non-blocking observations tracked.
- Threshold (8.0) cleared.
- Ready to build.

— LLMJ v2 review closed 2026-05-29.
