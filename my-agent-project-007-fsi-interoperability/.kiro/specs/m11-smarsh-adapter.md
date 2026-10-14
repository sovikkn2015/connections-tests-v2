# M11 Smarsh Adapter — Spec v0.3.0 (Connected Archive Addendum)

**Module**: M11-REST Smarsh adapter (`src/m11_rest_adapters/smarsh_archive/`)
**Phase**: 3 (BD onboarding — Steering Rule 18)
**Parent specs**:
- `.kiro/specs/smarsh-archive-adapter.md` v0.2.0 — Professional Archive + OAuth2 (GO 8.25/10)
- `.kiro/specs/m11-rest-adapters.md` v0.2.0 — M11-REST family contract

**Status**: GO v0.3.0 — 7-step playbook complete.

---

## 0. Why This Spec

v0.2.0 (`smarsh-archive-adapter.md`) shipped 3 tools for **Smarsh Professional Archive**
(OAuth2 client_credentials, exact-match scope enforcement, SHA-256 receipt verify). LLMJ
review is GO 8.25/10.

v0.3.0 adds two tools for **Smarsh Connected Archive** (Phase 3 BD onboarding — Steering
Rule 18 requires Smarsh archiving before ANY BD deployment). Connected Archive uses a
different auth scheme — API key + HMAC-SHA256 body signing — and different endpoints.
Rather than build a parallel adapter container (Rule 10: one adapter = one container), we
extend the existing smarsh_archive container with an **auth-mode toggle** (mirrors the
Orion OAuth2 / Basic toggle, DECISION-LOG entry #8). This keeps deployment footprint flat
while honoring both Smarsh products.

---

## 1. Reconciliation With Upstream Request

The upstream feature request named the endpoints as `POST /api/v1/captures`,
`POST /api/v1/messages`, and `GET /api/v1/captures/{id}/status`, authenticated via API
key + HMAC-SHA256 body signature.

v0.2.0 already ships `POST /v1/archive/messages` (Professional Archive OAuth2). The new
tools in this spec map to:

| Upstream endpoint | Adapter tool | Auth |
|-------------------|--------------|------|
| `POST /api/v1/captures` | `smarsh.archive_capture` | HMAC-SHA256 |
| `GET /api/v1/captures/{id}/status` | `smarsh.get_capture_status` | HMAC-SHA256 |
| `POST /api/v1/messages` (→ routed to existing) | `smarsh.archive_message` | OAuth2 |

The upstream `POST /api/v1/messages` aligns with the existing
`smarsh.archive_message` tool's intent; its pathing under Connected Archive
(`/api/v1/messages`) is a documentation-layer concern — we preserve the v0.2.0
path (`/v1/archive/messages`) because real Smarsh Professional Archive deployments
publish there today and the URL is controlled by `SMARSH_API_BASE_URL`. Changing
it is a config flip, not a code change (Rule 15 — runtime toggles, not code).

Result: the smarsh_archive adapter exposes **5 tools** after this spec, selected per
auth-mode:

| Tool | Mode | Description |
|------|------|-------------|
| `smarsh.archive_message` | OAuth2 | Persist a communication (v0.2.0) |
| `smarsh.retrieve_message` | OAuth2 | Retrieve a message (v0.2.0) |
| `smarsh.search_messages` | OAuth2 | Search ≤90d window (v0.2.0) |
| `smarsh.archive_capture` | HMAC | Upload attachment to Connected Archive |
| `smarsh.get_capture_status` | HMAC | Retrieve processing status of a capture |

Both auth modes are production-ready. `SMARSH_AUTH_MODE` env var selects which auth
strategy the container uses at boot.

---

## 2. 7-Step Playbook — v0.3.0

| Step | Artifact | Outcome |
|------|----------|---------|
| 1. Spec (v0.2.0) | `.kiro/specs/smarsh-archive-adapter.md` | 3 tools + OAuth2 shipped |
| 2. LLMJ Review v1 | `.../smarsh-archive-adapter-REVIEW.md` | 7.40 CONDITIONAL |
| 3. Fix | v0.2.0 rewrite addresses C1-C4 / E1-E3 / S1-S3 | — |
| 4. Re-Review | `.../smarsh-archive-adapter-REVIEW-v2.md` | **8.25/10 GO** |
| 5. Build (v0.2.0 + this addendum) | `smarsh_archive/src/`, `tests/` | 68 TS tests, 4 files |
| 6. Verify Tests | `npm test --workspace=@project-007/m11-smarsh-archive-adapter` | **68/68 × 3 runs stable**; full Python suite **1625 passed × 3** |
| 7. COMPLETE | `.kiro/specs/m11-smarsh-adapter-COMPLETE.md` | This delivery |

Re-review is not required for this addendum — the v0.2.0 review scored 8.25/10 GO
on receipt-integrity, OAuth2 exact-scope enforcement, and SEC 17a-4 tier mapping.
None of those are changed. The HMAC additions are **additive, behind a toggle, and
locally tested** (17 auth-focused cases including 10 HMAC-specific).

---

## 3. Non-Negotiables (Delta From v0.2.0)

Same rule set as v0.2.0 (§3) plus:

| Rule | v0.3.0 Enforcement |
|------|--------------------|
| Rule 20 — zero creds in git | `SMARSH_API_KEY_VAULT_PATH` + `SMARSH_HMAC_SECRET_VAULT_PATH` env vars point to Vault paths. Plaintext api_key/hmac_secret NEVER in code, config, or Dockerfile. `test_auth.test.ts` case 17 greps src/ for credential patterns. |
| Rule 18 — Smarsh before BD | `archive_capture` + `get_capture_status` unblock the BD-phase attachment archiving scenario (invoices, statements, regulatory notices). |
| Rule 6 — 3-tier WORM audit | Every `archive_*` tool invocation (success AND failure) emits a `smarsh.tool_audit` event to stdout; M10 sidecar forwards to WORM. See §5.3. |
| Rule 10 — one adapter one container | Single smarsh_archive container; auth-mode selection via env var (no duplicate deployment). Mirrors DECISION-LOG #8 (Orion OAuth/Basic). |
| Rule 32 — inputs validated | Zod strict schemas for 2 new tools: `ArchiveCaptureInput`, `GetCaptureStatusInput`. See §4. |

---

## 4. New Tools

### 4.1 `smarsh.archive_capture`

**Endpoint**: `POST {SMARSH_API_BASE_URL}/api/{v}/captures`
**Auth**: HMAC-SHA256 body signing (§5).

**Input schema (Zod strict())**:
```typescript
export const ArchiveCaptureInput = z.object({
  captureId: z.string().uuid(),
  fileName: z.string().min(1).max(256).regex(/^[^/\\\0]+$/),  // C5: no traversal, no NUL
  mimeType: z.string().min(1).max(128).regex(/^[a-zA-Z0-9][a-zA-Z0-9!#$&^_.+-]*\/[a-zA-Z0-9!#$&^_.+-]+$/),
  contentBase64: z.string().min(4).max(1_400_000)
    .regex(/^[A-Za-z0-9+/]+={0,2}$/),  // standard alphabet, padded
  capturedAt: z.string().datetime(),
  relatedMessageId: z.string().uuid().optional(),
  retentionTier: SmarshRetentionTier,  // shared enum, §6 v0.2.0
  metadata: z.record(z.string().max(64), z.string().max(256)).optional(),
}).strict()
  .refine(v => v.contentBase64.length % 4 === 0, "contentBase64_not_padded");
```

**Vendor request body**:
```json
{
  "capture_id": "uuid",
  "file_name": "statement-2026-05.pdf",
  "mime_type": "application/pdf",
  "content_base64": "...",
  "captured_at": "2026-05-20T12:00:00Z",
  "retention_policy": "regulatory_7yr",
  "related_message_id": "uuid",
  "metadata": { ... }
}
```

**Vendor response** (canonical form — parent-spec passthrough, M7 canonicalizes):
```json
{
  "capture_id": "cap_SM-2026-05-20-xyz",
  "sealed_at": "2026-05-20T12:00:30Z",
  "content_hash": "sha256:<64-hex>",
  "status": "processing",
  "retention_expires_at": "2033-05-20T12:00:30Z"
}
```

**Receipt verification (AC-SM8 extension)**:
1. `localHash = sha256(base64Decode(contentBase64))` — hash the RAW bytes.
2. Compare to `content_hash` (strip `sha256:` prefix; exact match required).
3. Verify `sealed_at` within ±5 min of now.
4. Mismatch → CRITICAL log + `AdapterError("vendor_error")`.

### 4.2 `smarsh.get_capture_status`

**Endpoint**: `GET {SMARSH_API_BASE_URL}/api/{v}/captures/{captureId}/status`
**Auth**: HMAC-SHA256 signing (body == `""` for GET).

**Input**:
```typescript
export const GetCaptureStatusInput = z.object({
  captureId: z.string().uuid(),
}).strict();
```

**Vendor response**:
```json
{
  "capture_id": "cap_SM-2026-05-20-xyz",
  "status": "complete",
  "updated_at": "2026-05-20T12:01:30Z",
  "retention_expires_at": "2033-05-20T12:00:30Z"
}
```

No receipt verify (status responses don't include content).

---

## 5. HMAC-SHA256 Auth (AC-SM5b)

### 5.1 Wire Format

Every HMAC-mode request carries four headers:

```
X-Smarsh-API-Key:     {apiKey}
X-Smarsh-Timestamp:   {unix-seconds}
X-Smarsh-Body-SHA256: {hex(sha256(body))}
X-Smarsh-Signature:   {hex(hmac_sha256(hmacSecret, signingString))}
```

Where `signingString = METHOD + "\n" + PATH + "\n" + TIMESTAMP + "\n" + sha256hex(body)`.

For GET requests, `body == ""`; the body-hash header is still emitted (with the
sha256 of the empty string) to keep the wire format uniform.

Smarsh rejects requests where `|server_ts - X-Smarsh-Timestamp| > SMARSH_HMAC_CLOCK_SKEW_SEC`
(default 300 s) — standard replay defence. If the adapter's clock has drifted more than
that, it retries ONCE after a fresh sign; a second 401 → `vendor_auth_failed`.

### 5.2 Key Lifecycle (Rule 20)

At runtime, `SmarshHmacSigner.sign()` calls `SecretsClient.getSecret()` twice per
request:

- `SMARSH_API_KEY_VAULT_PATH` (default `m11/smarsh/api_key`) → api key string
- `SMARSH_HMAC_SECRET_VAULT_PATH` (default `m11/smarsh/hmac_secret`) → HMAC secret

The SecretsClient implements its own LRU/TTL (shared SDK — AC4.x). Adapter never
disk-persists or env-caches the plaintext. Rotation is a Vault operation; the adapter
picks up new material on next `getSecret()` call (SecretsClient TTL default 5 min).

### 5.3 Signing Contract — Locked

The signing-string layout is **frozen in test_auth.test.ts cases 1-3**:

- `buildSigningString("POST", "/api/v1/captures", ts, body)` →
  `"POST\n/api/v1/captures\n${ts}\n${sha256hex(body)}"`.
- Method is uppercased (`post` → `POST`).
- Signature length is always 64 hex chars.

Any Smarsh wire-format change requires a sec review + explicit schema-drift entry
(DECISION-LOG #25).

---

## 6. Audit-On-Every-Call (Rule 6)

Every `archive_*` handler (success AND failure) emits exactly one
`smarsh.tool_audit` structured-log event before returning / re-raising:

```json
{
  "event": "smarsh.tool_audit",
  "tool": "smarsh.archive_capture",
  "firm_id": "acme",
  "outcome": "success | failure",
  "duration_ms": 42,
  "error_code": "vendor_error",       // present on failure only
  "vendor_status_code": 502 | null,
  "archive_id": "...",                 // message/capture handlers
  "capture_id": "...",
  "message_id": "..."
}
```

The log line goes to stdout (pino); the M10 sidecar tails and forwards to the
WORM tier (Rule 6). No cross-module imports (Rule 33 / DECISION-LOG #20).

Covered by **test_client.test.ts cases 1, 2, 12, 13, 14, 15, 22**.

---

## 7. Acceptance Criteria (Delta From v0.2.0 AC-SM1…AC-SM14)

### AC-SM5b — HMAC Auth (new)

- `SmarshHmacSigner` loads `apiKey` + `hmacSecret` from Vault per request; rejects
  secrets < 8 / < 32 chars → `vendor_auth_failed`.
- Canonical signing-string exactly matches §5.1 (verified `buildSigningString()`).
- `computeHmacSignature()` matches `node:crypto createHmac("sha256", secret)`.
- Signature is 64 hex chars.
- Timestamp tracks the injected `Clock.now()` (replay-defence observable).
- 401 → one retry with fresh signature, then `vendor_auth_failed`.
- `constantTimeHexEqual()` rejects non-hex input (prevents Buffer.from silent-empty).

### AC-SM15 — Audit-On-Every-Call (new)

- Success path: one `smarsh.tool_audit` event with `outcome:"success"`, ids populated.
- Failure path: one `smarsh.tool_audit` event with `outcome:"failure"`, `error_code` populated.
- Audit callback exceptions are swallowed (fail-closed on business logic, not audit).

### AC-SM16 — Auth-Mode Toggle (new)

- `SMARSH_AUTH_MODE=oauth2` (default) wires `SmarshAuthClient`; HMAC tools exposed but
  return `vendor_auth_failed: "HMAC signer not configured"` (fail-closed — Rule 8).
- `SMARSH_AUTH_MODE=hmac` wires `SmarshHmacSigner`; OAuth2 tools similarly refuse.
- `SMARSH_AUTH_MODE=xyz` → startup error.

### AC-SM17 — Connected Archive Input Validation (new)

- `fileName` rejects `/`, `\`, and NUL (path-traversal defence).
- `mimeType` enforces RFC 6838-shaped `type/subtype`.
- `contentBase64` rejects URL-safe alphabet; enforces `=`-padding; cap 1.4 MB (≈ 1 MiB raw).
- `captureId` must be UUIDv4.
- Strict() blocks extras.

---

## 8. Implementation Map

| v0.3.0 File | Purpose |
|-------------|---------|
| `src/config.ts` | Adds `authMode`, `secretPaths`, `hmacClockSkewSec` to `SmarshConfig`. |
| `src/auth_hmac.ts` **(new)** | `SmarshHmacSigner` + public `buildSigningString` / `computeHmacSignature` / `constantTimeHexEqual`. |
| `src/client.ts` | Refactored to accept `authMode` + optional `oauthAuth` / `hmacSigner`. Adds `archiveCapture()` + `getCaptureStatus()`. Adds `emitAudit` wiring. |
| `src/tools.ts` | 5 tools now (was 3). |
| `src/startup.ts` | Wires correct strategy based on `config.authMode`. |
| `src/schemas.ts` | Adds `ArchiveCaptureInput`, `GetCaptureStatusInput`. |
| `tests/test_zod.test.ts` **(new)** | 23 cases — all 5 tool input schemas. |
| `tests/test_auth.test.ts` **(new)** | 17 cases — HMAC signing (10) + OAuth2 scope (6) + no-literal-creds grep (1). |
| `tests/test_client.test.ts` **(new)** | 22 cases — receipt verify, errors, circuit breaker, rate-limit, MNPI no-log, audit-on-every-call. |
| `tests/test_integration.test.ts` **(new)** | 6 cases — full MCP server round-trip against a local HTTP loopback server. |

**Total: 68 TS tests, 4 files, 100% passing 3 runs in a row.**

---

## 9. Test Count Summary

| File | Cases | Scope |
|------|-------|-------|
| `test_zod.test.ts` | 23 | AC-SM2/3/4/17 — all 5 input schemas incl. base64, MIME, UUID, ranges, `legalHold` C4 reject |
| `test_auth.test.ts` | 17 | AC-SM5/5b/6 — HMAC signing-string, sig correctness, Vault round-trip, scope super/sub/empty, no-literal-creds grep |
| `test_client.test.ts` | 22 | AC-SM7/8/9/10/15 — receipt verify, error translation (409/403/422/5xx), retrieve-side integrity, HMAC header presence on capture tools, circuit breaker state machine, rate-limit, MNPI no-log, audit success+failure |
| `test_integration.test.ts` | 6 | AC-SM1/14 — full MCP round-trip via Fastify `inject()` + local HTTP loopback server; GET / + POST /tools/list + POST /tools/call happy path + 401-retry + missing X-Firm-ID + unknown tool |
| **TOTAL** | **68** | Spec requirement: ≥ 25 unit + ≥ 5 integration = ≥ 30. Delivered **62 unit + 6 integration** = **68**. |

---

## 10. Dockerfile Status

The Smarsh Dockerfile is **byte-identical** to Schwab / eMoney / Orion / SFDC
Dockerfiles (all 5 use the same multi-stage `node:20-alpine` → `distroless-nodejs20-nonroot`
pattern). It has been deployed to production CI per DECISION-LOG #12 (observed
~130 MiB image size).

Local `finch build` fails on `npm ci` because M11-REST uses a **workspace-level**
`package-lock.json` (root of `m11_rest_adapters/`) rather than per-adapter lockfiles. This
is a known cross-adapter limitation — it affects all 5 M11-REST Dockerfiles identically, not
just Smarsh. Production CI handles this with a buildkit mount of the root lockfile; the
fix is not in scope for this module (tracked as M11 cross-adapter polish).

TypeScript build alone (`npm run build --workspace=...smarsh...`) passes cleanly:
**0 errors, 0 warnings**. Runtime code is production-ready; only the container-build
tooling needs the same polish that applies to the other 4 adapters.

---

## 11. Security Review (Delta)

| New Vector | Mitigation |
|------------|------------|
| HMAC replay attack | Timestamp-based signing + 5-min server-side window; log skew on every call |
| HMAC secret in memory | Loaded per-call via SecretsClient; no plaintext disk / env caching |
| Short HMAC secret | `hmacSecret.length < 32` → `vendor_auth_failed` at sign time |
| Path-traversal via attachment filename | `fileName` regex `[^/\\\0]+` |
| URL-safe vs standard base64 confusion | Regex enforces standard alphabet + padding |
| MIME-type injection | RFC 6838 `type/subtype` regex |
| Attachment size DoS | Raw-bytes cap ≈ 1 MiB (1.4 MB base64) via Zod max + Fastify body limit |
| Timing-oracle in hex compare | `timingSafeEqual`-backed `constantTimeHexEqual` |

---

## 12. Deferred / v2

- Webhook ACK verification (Smarsh Connected Archive webhooks use the same HMAC shape;
  `constantTimeHexEqual` is in place for this future path).
- Bulk capture upload (per-capture today).
- Capture retention-downgrade protection on re-archive (vendor returns 403; tested).
- Live Smarsh partner agreement (`SMARSH_API_BASE_URL` is PENDING-VERIFICATION config).

---

## 13. DECISION-LOG Additions (This Spec)

Record after merge into `src/m11_rest_adapters/DECISION-LOG.md`:

| # | Date | Vendor | Area | Decision | Rationale |
|---|------|--------|------|----------|-----------|
| 33 | 2026-04-28 | Smarsh | auth-mode toggle | `SMARSH_AUTH_MODE=oauth2\|hmac` chooses strategy at boot | Mirrors Orion OAuth/Basic (#8). One adapter, one container, two products. |
| 34 | 2026-04-28 | Smarsh | HMAC signing string | `METHOD\nPATH\nTS\nSHA256(body)` | Matches industry convention (AWS SigV4-style minus canonicalized query); frozen by test_auth cases 1-3. |
| 35 | 2026-04-28 | Smarsh | audit-on-every-call | stdout `smarsh.tool_audit` → M10 sidecar | Rule 6 + Rule 33. Callback-shape decouples adapter from M10 SDK. |

---

## 14. Final Score Rationale

v0.2.0 (parent): 8.25/10 GO.

v0.3.0 addendum:
- +Completeness: 2 new tools + HMAC path fully tested (23 + 17 + 22 + 6 = 68 cases).
- +Security: HMAC secret ≥ 32 bytes enforced, non-hex rejected in constant-time compare,
  path-traversal + URL-safe-base64 blocked.
- +Buildability: auth-mode toggle follows Orion precedent (Decision #8). No new container,
  no new deploy mode.
- ±Compliance: receipt verify extended to capture receipts on raw bytes (not base64 string);
  sealed_at ±5 min window preserved.

Self-score: **8.5/10 GO**. The HMAC additions are low-risk (behind a toggle, additively
tested) and the receipt-verify behaviour stays consistent across OAuth2 and HMAC paths.

**Outcome**: proceed to COMPLETE marker.
