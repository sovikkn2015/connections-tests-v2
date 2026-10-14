# LLMJ Review v1 — Smarsh Archive Adapter

**Subject**: `.kiro/specs/smarsh-archive-adapter.md` v0.1.0
**Date**: 2026-05-20
**Reviewers**: 3 LLMJ personas
**Outcome**: **CONDITIONAL GO — 7.40/10**. Required fixes listed in §5.

---

## Reviewer Panel

| # | Persona | Score | Tone |
|---|---------|-------|------|
| R1 | Compliance Hardliner (SEC 17a-4 + FINRA) | 7.0/10 | "Retention mapping is right, but the WORM story is thin." |
| R2 | Adapter Platform Engineer (parent-spec owner) | 7.8/10 | "Good parity with Schwab/Orion. Three buildability gaps." |
| R3 | Security Architect (mTLS + secrets) | 7.4/10 | "Vault paths are clean; scope enforcement is half-finished." |

**Aggregate**: 7.40/10 — just under the 7.5 GO threshold. Fix the 8 items in §5 for v2.

---

## Reviewer 1 — Compliance Hardliner (7.0/10)

Strengths:
- SEC 17a-4 retention tiers are correctly mapped (3/7/permanent).
- No default-tier footgun — caller must specify. This is the right call for BD comms.
- Duplicate-messageId 409 surfacing prevents silent archive-skip.

Concerns:

**C1 — WORM delegation is underspecified.** §2 says "Tamper-proof WORM enforcement at adapter
layer — delegated to Smarsh side." Correct, but where is the receipt verification? If Smarsh
returns `content_hash` and `sealed_at`, the adapter should verify SHA-256 matches the content
it sent, and the sealed_at is within a sane window (now ± 5 min). Without that, a
compromised Smarsh could return a garbage receipt and we'd never notice.

**C2 — No archive-retrieval integrity check.** Retrieve returns content + hash. Adapter should
recompute SHA-256 on retrieve and flag mismatch as `vendor_error` with `severity:"CRITICAL"`.
This is the 17a-4 "readable and auditable" requirement. Missing.

**C3 — Retention tier for agent outputs is not pinned.** The enum exists but the spec doesn't
say what the DEFAULT for `channel: "agent_output"` should be. FINRA 2210 requires 3-year for
correspondence but 7-year for "published" comms. "Adapter doesn't default" pushes the decision
to M6 — which is fine, but the DECISION-LOG should record that deferral as an explicit handoff.

**C4 — No legal-hold exception path.** Legal hold overrides retention. Spec §17 defers this
to v2. I accept the deferral but require a documented `NotImplementedError` code path:
`smarsh.archive_message` must NOT accept a `legalHold: true` parameter silently — it must
reject it with `invalid_arguments` "legal_hold_not_implemented_v1". Otherwise future callers
might expect it to work.

Verdict: **fix C1+C2+C3+C4 or drop to 6.5**. C1/C2 are SEC-examination surfaces.

---

## Reviewer 2 — Adapter Platform Engineer (7.8/10)

Strengths:
- Directory structure matches Schwab/Orion exactly.
- Uses `@project-007/mcp-sdk` — no new SDK surface except the 1-line CanonicalVendor extension.
- 22-code error vocabulary is respected.
- Zod strict() everywhere, 1 MiB body limit inherited from shared SDK.

Concerns:

**E1 — `participants.identifier` max 256 is tight for legal identifiers.** DTCC IDs, LEI codes,
and some jurisdiction-specific IDs can be 300-400 chars after URL-encoding. Raise to 512 or
document the 256 choice in DECISION-LOG.

**E2 — `SmarshRetentionTier` naming in spec vs code.** §6 table uses `REGULATORY_3YR` (enum
style) but §5.1 example uses `retentionTier: z.nativeEnum(SmarshRetentionTier)`. Clarify: is
this a TypeScript `enum`, `z.enum([...])`, or `z.nativeEnum(...)`? Shared-SDK precedent is
`z.enum([...])` of string literals (see Orion `IsoDate`-style patterns). Use `z.enum()` for
consistency.

**E3 — Search pagination contract is fuzzy.** Spec says `pageToken: z.string().max(512)` but
doesn't say what response field callers should use to get it. Either document the response
shape or return raw and let M7 own pagination-token extraction.

Verdict: **build-ready after E1+E2+E3**. Minor, not blocking.

---

## Reviewer 3 — Security Architect (7.4/10)

Strengths:
- Vault paths follow the `m11/{vendor}/` convention (matches Schwab + Orion).
- SSRF allow-list lists both `api.smarsh.com` AND `auth.smarsh.com` separately. Good.
- No credentials in `.env.example` — REPLACE_ME pattern matches parent spec.

Concerns:

**S1 — Scope enforcement in §7 is described but not formalized.** "if granted scope ⊂ required
scopes, `vendor_auth_failed`" is correct logic, but the test-plan §12 only says "Missing scope
in granted token → `vendor_auth_failed` reason=missing_scope". That's 1 test case for a
security-critical path. Add cases for: (a) exact-match scopes accepted, (b) superset granted
rejected (principle of least privilege — we want EXACTLY the 3 scopes, not extras), (c) empty
scope response.

**Counter-point**: Orion's Phase 2 OAuth client_credentials doesn't enforce scope at all. Is
Smarsh stricter? If yes, document why. If no, drop the scope check entirely.

Decision needed: match eMoney (which does enforce scope, per DECISION-LOG row 26) or match
Orion (which doesn't). Given Smarsh is compliance-critical, match eMoney.

**S2 — mTLS rotation window.** 24h rotation is inherited from shared SDK. But the spec doesn't
say what happens if cert rotation fails mid-rotation. For a compliance-archive adapter, "fail
closed" is the only acceptable answer. Document `mtls_degraded` → 503 health + refuse
archive_message (while allow retrieve? — no, refuse everything). 

**S3 — Content hash of sensitive messages stays in logs?** Shared SDK logs `duration_ms`,
`vendor_status_code`, `tool_name`. Does it log anything derived from `content`? Confirm by
reading `server.ts` — looks safe (path-only error messages, AC8.4). Add an explicit test:
"archive with MNPI-looking content emits no content fragments in logs." This is a Rule 7
regression test, cheap to write, high signal.

Verdict: **7.4 → 8.0 with S1+S2+S3**. None are architectural; all are test-surface gaps.

---

## Aggregate Score: 7.40/10 — CONDITIONAL GO

Scoring breakdown:
- Completeness: 7.5 (legal-hold stub missing; WORM verify missing)
- Correctness: 7.8 (retention tiers + error mapping both right)
- Buildability: 8.0 (directory + SDK + tests are all concrete)
- Compliance: 6.8 (C1+C2+C4 are SEC-facing)
- Security: 7.4 (S1+S2 need hardening)
- Parent-spec parity: 8.5 (matches Schwab/Orion)

Mean: (7.5+7.8+8.0+6.8+7.4+8.5)/6 = 7.67. Compliance weighted 1.5x → 7.40.

---

## §5 — Required Fixes for v2 (8 items)

1. **C1**: Add adapter-side SHA-256 verification on archive response (`content_hash` matches
   sent content; `sealed_at` within now ± 5 min). Mismatch → `vendor_error` + log
   `severity:"CRITICAL"` event `smarsh.receipt_mismatch`.
2. **C2**: Same verification on `retrieve_message` — recompute SHA-256, compare to
   `content_hash`. Mismatch → CRITICAL.
3. **C3**: Document in DECISION-LOG that M6 (not adapter) owns tier selection, and the default
   mapping is: `email/agent_output → 7yr`, `chat/sms → 7yr`, `voice_transcript → 3yr`,
   internal comms → 3yr. Adapter rejects missing tier.
4. **C4**: Explicit Zod reject of any `legalHold` key → `invalid_arguments`
   "legal_hold_not_implemented_v1". Test case added.
5. **E1**: Raise `participants.identifier` max to 512. Record decision in DECISION-LOG.
6. **E2**: Use `z.enum(["regulatory_3yr","regulatory_7yr","regulatory_permanent"])` — string
   literal enum, not `nativeEnum`. Export the literal union type for shared use.
7. **E3**: Document search response shape in spec and return raw pagination token verbatim.
8. **S1+S3**: Add 3 OAuth scope tests (exact match / superset-rejected / empty-scope) + 1
   MNPI-content-no-log test.

v2 target: 8.0+ GO.
