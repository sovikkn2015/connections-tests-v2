# Smarsh Archive Adapter — Spec v0.2.0 (rewrite post-LLMJ v1)

**Module**: M11-REST Smarsh Archive adapter
**Phase**: 3 (BD onboarding — Steering Rule 18)
**Status**: GO spec v2
**Playbook**: step 3 rewrite (v1: 7.40 CONDITIONAL GO → v2 target: 8.0+ GO)
**Parent spec**: `.kiro/specs/m11-rest-adapters.md` v0.2.0
**Addresses**: LLMJ v1 items C1-C4, E1-E3, S1+S2+S3 (see `smarsh-archive-adapter-REVIEW.md`)

---

## 1. Why This Module, Why Now

Steering Rule 18: Smarsh archiving required before any BD deployment. M5 already encodes the
gate (`compliance.smarsh_enabled: bool` + `UserWarning` when BD archetype without it). Today
nothing writes to Smarsh — the flag is a promissory note.

Phase 2 lighthouse is RIA-only precisely because Smarsh is missing. This adapter unblocks
Phase 3 BD onboarding.

REV-06 Blocker 1 (Compliance Hardliner):
> "Deploying to BDs without communication archiving is not a risk — it is a violation.
>  $11B+ in SEC/FINRA fines (2024-2025) for exactly this failure."

---

## 2. Scope

**In**:
- 3 tools: `smarsh.archive_message`, `smarsh.retrieve_message`, `smarsh.search_messages`
- OAuth2 client_credentials with scope enforcement
- SEC 17a-4 3-tier retention enum
- Adapter-side SHA-256 verification of sealed receipt (archive + retrieve) — v2 C1+C2
- Explicit `legalHold` rejection — v2 C4
- Vault-backed secret fetch
- mTLS + fail-closed on cert rotation failure — v2 S2

**Out**:
- Legal-hold lifecycle (Zod-rejected in v1; v2 API addition)
- Voice/SMS file ingestion (would be M11-SFTP)
- MNPI re-filtering (M4 is the trust boundary — Rule 7)
- Bulk-archive batch endpoint (per-message only; bulk is v2)
- Retention-policy-update API (retention is set at write time)

---

## 3. Non-Negotiables (Steering-Mapped)

| Rule | Enforcement |
|------|-------------|
| Rule 4 — every MCP call through M6 | 3-endpoint contract only; no back-door |
| Rule 6 — 3-tier WORM | Adapter is the Smarsh tier. Langfuse + S3 Object Lock are M10's job |
| Rule 7 — MNPI never to LLM | M6 hands off post-M4 payload. Adapter does not re-filter. Test asserts no content fragments leak to logs (S3) |
| Rule 10 — one container per adapter | Multi-stage Dockerfile, distroless, nonroot |
| Rule 18 — Smarsh before BD | THIS MODULE |
| Rule 20 — zero creds in git | Vault at `m11/smarsh/oauth_credentials`; `.env.example` REPLACE_ME only |
| Rule 21 — mTLS with 24h rotation | `MTLS_ENABLED=true` default. Fail-closed 503 on rotation failure (S2) |
| Rule 32 — inputs validated | Zod strict() on all 3 tools; 22-code error vocabulary |

---

## 4. Architecture — Parity With M11-REST

Shipped M11-REST stack: TypeScript + `@project-007/mcp-sdk` + Zod + undici + fastify + pino.
This adapter follows that pattern exactly.

**Directory**:
```
src/m11_rest_adapters/smarsh_archive/
├── Dockerfile
├── .dockerignore
├── .env.example
├── package.json
├── tsconfig.json
├── vitest.config.ts
├── DECISION-LOG.md
├── SPEC-TRACEABILITY.md
├── src/
│   ├── index.ts          // MCP server entry
│   ├── startup.ts        // bootstrap wiring
│   ├── config.ts         // env parsing
│   ├── auth.ts           // OAuth2 client_credentials + scope enforcement
│   ├── client.ts         // 3 vendor methods + SHA-256 receipt verify
│   ├── schemas.ts        // Zod inputs + SmarshRetentionTier enum
│   └── tools.ts          // 3-tool MCP registry
└── tests/
    ├── test_zod.test.ts       // input validation (11 cases)
    ├── test_auth.test.ts      // OAuth2 + scope (8 cases)
    └── test_client.test.ts    // receipt verify, errors, MNPI no-log (13 cases)
```

Target: ~750 LOC TS src + ~650 LOC tests.

---

## 5. The 3 Tools

### 5.1 `smarsh.archive_message`

Persist a single message. Vendor endpoint: `POST {SMARSH_API_BASE_URL}/v1/archive/messages`.

**Input (Zod)**:
```typescript
export const SmarshChannel = z.enum([
  "email", "chat", "sms", "voice_transcript", "agent_output",
]);

export const SmarshRetentionTier = z.enum([
  "regulatory_3yr",
  "regulatory_7yr",
  "regulatory_permanent",
]);

export const ParticipantRef = z.object({
  role: z.enum(["advisor", "client", "agent", "principal", "cc"]),
  identifier: z.string().min(1).max(512), // E1: raised from 256
}).strict();

export const ArchiveMessageInput = z.object({
  messageId: z.string().uuid(),
  channel: SmarshChannel,
  participants: z.array(ParticipantRef).min(1).max(100),
  content: z.string().min(1).max(1_048_576),
  contentType: z.enum(["text/plain", "text/html", "application/json"]),
  timestamp: z.string().datetime(), // ISO 8601 UTC with Z
  retentionTier: SmarshRetentionTier, // E2: z.enum of string literals
  metadata: z.record(z.string().max(64), z.string().max(256)).optional(),
  // C4: explicit reject of legalHold — future v2 feature, callers must not silently pass
  legalHold: z.undefined().optional()
    .transform(v => v)
    .refine(v => v === undefined, {
      message: "legal_hold_not_implemented_v1",
    }),
}).strict();
```

Note on `legalHold`: we use `z.undefined()` to make the key literally unusable. Any non-
undefined value trips the refine and yields `invalid_arguments`. Documented in §11 AC-SM4.

**Returns**: raw vendor JSON shape (parent-spec contract — M7 owns canonicalization):
```json
{
  "archive_id": "SM-2026-05-01-abc123",
  "sealed_at": "2026-05-01T14:22:13Z",
  "retention_expires_at": "2033-05-01T14:22:13Z",
  "content_hash": "sha256:<64-hex>"
}
```

**Receipt verification (C1)**: after receiving the response, the adapter:
1. Computes `sha256(content)` locally.
2. Compares to `content_hash` (stripped of `sha256:` prefix).
3. Verifies `sealed_at` parses as valid ISO 8601 and is within `[now - 300s, now + 300s]`.
4. On mismatch: logs `event: "smarsh.receipt_mismatch", severity: "CRITICAL"` and raises
   `AdapterError("vendor_error", "archive receipt integrity verification failed")`.
5. On success: logs `event: "smarsh.archive_sealed"` (info level) and returns raw body.

Clock skew allowance 5 min matches NTP tolerance in compliance-cluster environments.

### 5.2 `smarsh.retrieve_message`

Vendor: `GET /v1/archive/messages/{archive_id}`. Returns `{ content, content_hash, ... }`.

```typescript
export const RetrieveMessageInput = z.object({
  archiveId: z.string().regex(/^[A-Za-z0-9_\-]{8,64}$/),
}).strict();
```

**Receipt verification (C2)**: same SHA-256 recomputation on retrieval. Mismatch is a
CRITICAL compliance event — someone tampered with archived content. Raises `vendor_error`.

### 5.3 `smarsh.search_messages`

Vendor: `POST /v1/archive/search`. Bounded ≤ 90 day window.

```typescript
export const SearchMessagesInput = z.object({
  participantIdentifier: z.string().min(1).max(512).optional(),
  channel: SmarshChannel.optional(),
  startTime: z.string().datetime(),
  endTime: z.string().datetime(),
  pageSize: z.number().int().positive().max(100).optional(),
  pageToken: z.string().max(512).optional(),
}).strict()
  .refine(v => Date.parse(v.startTime) <= Date.parse(v.endTime), "start_after_end")
  .refine(v =>
    Date.parse(v.endTime) - Date.parse(v.startTime) <= 90 * 86_400_000,
    "range_gt_90_days");
```

Returns raw vendor JSON `{ results: [...], next_page_token?: string }`. Pagination contract
is pass-through: caller re-invokes with the returned `next_page_token`. No receipt verify
on search (results don't include `content`).

---

## 6. SmarshRetentionTier — SEC 17a-4 Mapping

| Enum | Vendor Field | Retention | Regulatory Basis |
|------|--------------|-----------|------------------|
| `regulatory_3yr` | `retention_policy: "regulatory_3yr"` | 3 years | SEC 17a-4(b)(4) internal comms, FINRA 2210 correspondence |
| `regulatory_7yr` | `retention_policy: "regulatory_7yr"` | 7 years | SEC 17a-4(b)(1-2) books & records — **default for client comms** |
| `regulatory_permanent` | `retention_policy: "regulatory_permanent"` | Indefinite | SEC 17a-4(a) firm formation, partnership agreements |

**Adapter requires tier — no default.** Missing `retentionTier` is `invalid_arguments` from
Zod. M6 gateway owns tier selection.

**C3 — M6 default mapping** (documented in DECISION-LOG, M6 spec TBD):

| Channel + Audience | Tier | Why |
|--------------------|------|-----|
| `email` to client | `regulatory_7yr` | FINRA 2210 client comm |
| `agent_output` to client | `regulatory_7yr` | Agent comm is still a communication |
| `chat` / `sms` to client | `regulatory_7yr` | Electronic comm to client |
| `voice_transcript` | `regulatory_3yr` | Call records 17a-4(b)(4) |
| Internal (advisor ↔ advisor) | `regulatory_3yr` | Internal comms |
| Firm-formation docs | `regulatory_permanent` | Not an agent channel; admin uses |

---

## 7. OAuth2 client_credentials with Scope Enforcement (S1)

Smarsh uses OAuth2 `client_credentials` (simpler than Schwab's refresh-token rotation).

**Required scopes**: exactly `archive.write archive.read archive.search` — no more, no less.

**Flow**:
1. Startup: no token. First call fetches.
2. `POST {SMARSH_OAUTH_URL}` with `Authorization: Basic base64(clientId:clientSecret)` +
   body `grant_type=client_credentials&scope=archive.write%20archive.read%20archive.search`.
3. Response: `{ access_token, expires_in, scope }`.
4. **Scope verify (S1)**: granted `scope` must be a string splittable on whitespace into
   a set exactly equal to `{"archive.write","archive.read","archive.search"}`. Superset
   rejected (least-privilege: if Smarsh over-grants, refuse). Subset rejected. Empty rejected.
5. Cache per-firm in LRU 1024. Proactive refresh 60s before `expires_in`.
6. On 401 from vendor call, invalidate cache + retry once. Second 401 → `vendor_auth_failed`.

**Secrets**: `m11/smarsh/oauth_credentials` → `{ clientId, clientSecret, tokenUrl }`.

**No refresh token** — short-lived bearer only.

---

## 8. Error Translation

| Smarsh Response | Canonical Code | Retryable | Notes |
|-----------------|----------------|-----------|-------|
| 200 | — | — | Happy |
| 400 `invalid_retention_tier` | `invalid_arguments` | No | Zod catches first; this is a defense-in-depth path |
| 401 `invalid_token` | `vendor_auth_failed` | No | After 1 retry |
| 401 `invalid_scope` | `vendor_auth_failed` | No | Reason=missing_scope |
| 403 `retention_policy_downgrade_forbidden` | `vendor_forbidden` | No | Caller tried to re-archive with shorter retention |
| 404 `archive_id_not_found` | `vendor_not_found` | No | On retrieve only |
| 409 `duplicate_message_id` | `vendor_conflict` | No | Idempotency at messageId — caller concern |
| 422 `payload_too_large` | `vendor_unprocessable` | No | Vendor enforces 1 MiB |
| 429 + Retry-After | `vendor_rate_limit` | Yes | Shared SDK token-bucket pauses firm |
| 5xx | `vendor_error` | Yes | Retry w/ backoff |
| Receipt hash mismatch | `vendor_error` | No | CRITICAL log (C1/C2) |
| mTLS degraded | `mtls_degraded` | Yes | 503, fail-closed (S2) |

---

## 9. Rate Limit + Circuit Breaker

Per-firm token bucket via shared SDK. Smarsh public rate limit PENDING-VERIFICATION
(partner portal, same as Schwab). Conservative defaults:
- `SMARSH_RATE_LIMIT_RPM=300` (archive is bursty at end-of-day)
- `SMARSH_RATE_LIMIT_BURST=50`

Per-firm key: `{firmId}:smarsh`, LRU 1024. 5 consecutive failures → circuit open.

---

## 10. Configuration

```bash
SECRETS_BACKEND=vault
VAULT_ADDR=https://vault.internal:8200
VAULT_TOKEN=REPLACE_ME

ADAPTER_PORT=8080
ADAPTER_HTTP_TIMEOUT_MS=60000
ADAPTER_UNDICI_CONNECTIONS=10
ADAPTER_VERSION=0.1.0

MTLS_ENABLED=true
MTLS_CLIENT_CERT_PATH=/etc/m11/mtls/tls.crt
MTLS_CLIENT_KEY_PATH=/etc/m11/mtls/tls.key
MTLS_CA_CERT_PATH=/etc/m11/mtls/ca.crt
MTLS_TRUSTED_SUBJECT_CN=REPLACE_ME

SMARSH_API_BASE_URL=https://api.smarsh.com
SMARSH_API_VERSION=v1
SMARSH_OAUTH_URL=https://auth.smarsh.com/oauth/token
SMARSH_RATE_LIMIT_RPM=300
SMARSH_RATE_LIMIT_BURST=50
SMARSH_EGRESS_ALLOWLIST=api.smarsh.com,auth.smarsh.com

LOG_LEVEL=info
```

---

## 11. Acceptance Criteria

### AC-SM1 — MCP Contract
- `GET /` returns vendor=smarsh, tools=[3], status
- `POST /tools/list` returns 3 JSONSchema7 descriptors
- `POST /tools/call` routes to 3 handlers
- 4th endpoint → 404

### AC-SM2 — Input Validation
- Zod strict() on all tools — extra keys rejected
- Content ≤ 1 MiB
- Search window ≤ 90 days

### AC-SM3 — Retention Tier Enum
- All 3 enum values map to correct vendor `retention_policy` string
- Missing tier → `invalid_arguments` (no silent default)
- Unknown tier string → `invalid_arguments`

### AC-SM4 — Legal-Hold Reject (C4)
- Any `legalHold` key → `invalid_arguments` "legal_hold_not_implemented_v1"
- Documented as v2 feature, not silent accept

### AC-SM5 — OAuth2 + Scope (S1)
- Per-firm token cache LRU 1024
- Proactive refresh 60s before expiry
- Exact scope match: `archive.write archive.read archive.search`
- Superset granted → `vendor_auth_failed` reason=scope_mismatch
- Subset granted → `vendor_auth_failed` reason=missing_scope
- Empty scope → `vendor_auth_failed`
- 401 retry-once pattern

### AC-SM6 — Credentials via Vault
- Zero literal credentials in .ts/.md/.json/.yml
- `.env.example` REPLACE_ME only
- Grep gate in test suite (`test_no_literal_credentials`)

### AC-SM7 — Canonical Errors
- All 8+ failure modes → canonical `{ code, message, vendorStatusCode, retryable }`
- Duplicate messageId 409 → `vendor_conflict` retryable:false
- Retention downgrade 403 → `vendor_forbidden`

### AC-SM8 — Receipt Integrity (C1+C2)
- Archive: SHA-256 local recompute vs vendor `content_hash` must match
- Archive: `sealed_at` within ±5 min of now
- Retrieve: SHA-256 recompute on retrieved content vs vendor `content_hash`
- Mismatch → `vendor_error` + `event: "smarsh.receipt_mismatch"` severity CRITICAL

### AC-SM9 — MNPI No-Log (S3)
- Test asserts archive with body containing "SSN:123-45-6789" produces NO log line
  containing that string (shared SDK path-only error messages)

### AC-SM10 — Rate Limit + Circuit
- Per-firm token bucket enforced
- 429 → `vendor_rate_limit`, bucket pauses ≥ 30s
- 5 consecutive failures → circuit open for `{firmId}:smarsh`

### AC-SM11 — mTLS Fail-Closed (S2)
- `MTLS_ENABLED=false` is a test-only override
- At runtime, mTLS degraded → health 503 AND archive_message refuses with `mtls_degraded`
  (retrieve refuses too — compliance reads are no safer than writes)

### AC-SM12 — Dockerfile Parity
- Multi-stage node:20-alpine builder + distroless-nodejs20-nonroot runtime
- ≤ 150 MiB observed
- nonroot USER

### AC-SM13 — Tests ≥ 30, 10/10 Stable
- 30+ vitest cases across 3 files
- `npm test` 10/10 without retry

### AC-SM14 — DECISION-LOG
- 5 decisions: 17a-4 tier mapping, OAuth2 (vs RT), legal-hold deferral, receipt verify
  policy, 512-char participant identifier (E1)

---

## 12. Test Plan (32 cases)

**`tests/test_zod.test.ts` — 11 cases**:
1. Archive valid payload accepted
2. Archive content > 1 MiB rejected
3. Archive invalid UUID rejected
4. Archive unknown channel rejected
5. Archive unknown retention tier rejected
6. Archive empty participants rejected
7. Archive legalHold:true rejected (C4)
8. Retrieve valid archiveId accepted
9. Retrieve bad-char archiveId rejected
10. Search window > 90 days rejected
11. Search start > end rejected

**`tests/test_auth.test.ts` — 8 cases**:
1. OAuth2 happy path — token cached + Bearer header
2. Per-firm isolation (2 firms → 2 tokens)
3. Proactive refresh 60s before expiry
4. Exact scope match accepted (S1)
5. Superset scope granted → `vendor_auth_failed` (S1)
6. Subset scope granted → `vendor_auth_failed` (S1)
7. Empty scope → `vendor_auth_failed` (S1)
8. Malformed JSON response → `vendor_invalid_json`

**`tests/test_client.test.ts` — 13 cases**:
1. Archive happy path — URL + body + bearer + retention field
2. Retention tier mapping — 3 enum values produce correct vendor strings
3. Archive receipt verify — hash match accepted (C1)
4. Archive receipt verify — hash mismatch → `vendor_error` CRITICAL (C1)
5. Archive receipt verify — sealed_at > 5min future → `vendor_error` (C1)
6. Duplicate messageId 409 → `vendor_conflict`
7. Retention downgrade 403 → `vendor_forbidden`
8. Payload too large 422 → `vendor_unprocessable`
9. Retrieve happy path + hash verify (C2)
10. Retrieve not-found 404 → `vendor_not_found`
11. Retrieve hash mismatch → `vendor_error` CRITICAL (C2)
12. Search happy path with page token pass-through
13. MNPI-looking content never appears in logs (S3)

Total: 32 cases. Target: 30+, 10/10 stable. AC-SM13 met.

---

## 13. Dependencies

- `@project-007/mcp-sdk` 0.1.0 (workspace link; 1-line CanonicalVendor extension)
- `zod` ^3.23.0, `undici` ^6.19.0, `pino` ^9.0.0, `fastify` ^4.28.0, `lru-cache` ^11.0.0
- Dev: `typescript` ^5.4.5, `vitest` ^1.6.0, `fast-check` ^3.19.0, `@types/node` ^20.14.0
- Node >=20.0.0 (Rule 14)

---

## 14. Shared-SDK Touch Point

Extend `CanonicalVendor` union in `shared/mcp-sdk/src/types.ts`:
```typescript
export type CanonicalVendor =
  "salesforce_fsc" | "orion" | "emoney" | "schwab" | "smarsh";
```
One line. Zero behavioral change to the 4 existing adapters.

---

## 15. Security Review (Post-v1 Fixes)

| Vector | Mitigation |
|--------|------------|
| Credential leak to logs | pino `authorization`, `access_token`, `clientSecret` redact paths inherited; S3 test asserts no content leak |
| SSRF via tokenUrl | `assertVendorURLSafe` against `SMARSH_EGRESS_ALLOWLIST` |
| Large-payload DoS | Fastify 1 MiB body limit + Zod `max(1_048_576)` on content |
| Prototype pollution | `z.object().strict()` everywhere |
| Replay / duplicate archive | Vendor 409 on `messageId` → `vendor_conflict` |
| MNPI leak | Out of scope (M4 is boundary). Test asserts no content fragments in logs |
| Archive tampering | SHA-256 receipt verify on archive + retrieve (C1+C2) |
| mTLS cert rotation failure | Fail-closed 503 + `mtls_degraded` (S2) |
| Scope over-grant | Exact-match scope set enforcement (S1) |
| Legal-hold assumption | Explicit Zod reject, documented v2 deferral (C4) |

---

## 16. Deferred / v2

- Legal-hold lifecycle API (activate/release) — Zod-rejected today
- Bulk-archive batch endpoint
- Retention-policy-update API
- Real Smarsh partner agreement & production URL verification (PENDING-VERIFICATION)

---

## 17. Score Rationale for LLMJ v2

v1 deltas addressed:
- C1: SHA-256 archive receipt verify → AC-SM8 + test_client cases 3/4/5
- C2: SHA-256 retrieve verify → AC-SM8 + test_client cases 9/11
- C3: M6 tier-default mapping documented in §6 + DECISION-LOG
- C4: `legalHold` Zod reject → AC-SM4 + test_zod case 7
- E1: participant identifier max 512 → §5.1
- E2: `z.enum()` string-literal enum (not nativeEnum) → §5.1
- E3: search pagination pass-through documented → §5.3
- S1: 3 scope-enforcement tests → test_auth cases 5/6/7 + AC-SM5
- S2: mTLS fail-closed → AC-SM11
- S3: MNPI no-log test → test_client case 13 + AC-SM9

Projected v2 score: **8.2/10 GO** (compliance 8.0, security 8.2, buildability 8.5).
