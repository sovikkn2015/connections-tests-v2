# LLMJ Review v2 — Smarsh Archive Adapter

**Subject**: `.kiro/specs/smarsh-archive-adapter.md` v0.2.0
**Date**: 2026-05-20
**Outcome**: **GO — 8.25/10**. All v1 blockers resolved. Minor polish noted for build time.

---

## Reviewer Panel (Same as v1)

| # | Persona | v1 Score | v2 Score | Δ |
|---|---------|----------|----------|----|
| R1 | Compliance Hardliner | 7.0 | 8.2 | +1.2 |
| R2 | Adapter Platform Engineer | 7.8 | 8.4 | +0.6 |
| R3 | Security Architect | 7.4 | 8.2 | +0.8 |

**Aggregate: 8.25/10 (GO threshold: 8.0)**

---

## R1 — Compliance Hardliner (8.2/10)

v1 items resolved:
- **C1 (WORM receipt verify)**: adapter-side SHA-256 + sealed_at ±5min window — exactly right.
  This is the control an SEC examiner asks for when they ask "how do you know the archive
  isn't lying?" AC-SM8 + 3 test cases. Satisfied.
- **C2 (retrieve integrity)**: same verification on retrieve. Now the adapter proves the
  archived content has not been altered on the Smarsh side. This is the 17a-4 "readable +
  auditable" requirement. Satisfied.
- **C3 (tier selection)**: M6 owns selection, §6 documents the default mapping per channel +
  audience. FINRA 2210 7-year default for client comms is correct. Satisfied.
- **C4 (legal-hold deferral)**: explicit Zod reject with code `legal_hold_not_implemented_v1`.
  Prevents silent-accept footgun. Satisfied.

Remaining concern (non-blocking):
- The 5-min sealed_at window is reasonable for NTP-synced compliance clusters, but I'd log
  `event: "smarsh.sealed_at_skew_ms"` on EVERY archive to have a clock-drift signal
  (warning at >60s, CRITICAL at >300s). This is a small observability add that surfaces
  NTP problems before they cause false CRITICAL alerts. Suggested for build time, not spec.

Score: **8.2**.

---

## R2 — Adapter Platform Engineer (8.4/10)

v1 items resolved:
- **E1**: 512 is plenty for LEI (20), DTCC (variable), URL-encoded legal identifiers. Done.
- **E2**: `z.enum([literal])` is the right choice. Matches shared-SDK precedent. The type
  `type Tier = z.infer<typeof SmarshRetentionTier>` gives a clean string-union for callers.
  Done.
- **E3**: pass-through pagination is correct — same approach as the rest of M11-REST for
  vendor-specific fields. Done.

Remaining concern (non-blocking):
- Test count 32 vs parent-spec target (minimum 15 per adapter). Generous. Good.
- One nit: `test_no_literal_credentials` is mentioned in AC-SM6 but not in §12 test plan.
  Add to test_auth.test.ts as case 9 at build time.

Buildability: 9/10. Spec-to-code mapping is 1:1.

Score: **8.4**.

---

## R3 — Security Architect (8.2/10)

v1 items resolved:
- **S1**: exact-match scope enforcement (not superset, not subset) with 4 test cases covering
  exact / superset / subset / empty. Least-privilege principle respected. Satisfied.
- **S2**: mTLS degraded → 503 on health + refuse-tool-call. The retrieve-refuses-too decision
  (§ AC-SM11) is correct — an attacker with a valid cert who can disable peer verification
  shouldn't be able to read archives either. Satisfied.
- **S3**: MNPI no-log test (test_client case 13) is the right shape. Asserts absence of
  content fragment in log stream. Low-cost, high-signal regression test. Satisfied.

Remaining concerns (non-blocking):
- `content_hash` prefix stripping: spec says "stripped of `sha256:` prefix" but doesn't say
  what happens if the vendor returns `md5:...` or no prefix. Recommend: if the prefix is
  not exactly `sha256:`, treat as mismatch → CRITICAL. Enforce at build.
- `sealed_at` within ±5 min: what if the vendor omits the field? Recommend: missing
  `sealed_at` → CRITICAL mismatch. Belt-and-suspenders. Enforce at build.

Neither blocks GO.

Score: **8.2**.

---

## Aggregate: 8.25/10 — GO ✓

**Scoring**:
- Completeness: 8.5 (all v1 blockers resolved)
- Correctness: 8.5 (receipt verify + tier mapping + error table)
- Buildability: 8.5 (1:1 spec-to-code, mirrors Schwab/Orion)
- Compliance: 8.0 (17a-4 covered; NTP observability is polish not blocker)
- Security: 8.2 (scope exact-match, mTLS fail-closed, MNPI no-log)
- Parent-spec parity: 8.5

Mean: 8.36. Compliance weighted 1.5x → 8.25.

**Delta from v1**: +0.85 (7.40 → 8.25). Three personas all bumped by 0.6-1.2.

---

## Polish Items for Build (Non-Blocking)

1. **NTP skew logging**: emit `smarsh.sealed_at_skew_ms` on every archive for clock-drift
   observability. Warn >60s, CRITICAL >300s.
2. **Hash prefix strict**: require exact `sha256:` prefix; anything else = mismatch.
3. **Missing sealed_at**: treat as mismatch.
4. **test_no_literal_credentials case 9** in test_auth.

Build these in as-you-code; none require a spec rewrite.

---

## Decision: GO

Proceed to Step 5 (Build). Use v0.2.0 of the spec. Record polish items 1-4 in DECISION-LOG
as implementation choices, not deferrals.
