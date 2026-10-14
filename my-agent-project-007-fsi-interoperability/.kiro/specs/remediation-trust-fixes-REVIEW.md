# Self-LLMJ Review v1 — remediation-trust-fixes.md

> Reviewer: 007-trust-agent (LLMJ mode, own-work review).
> Review type: spec-level, pre-build.
> Spec under review: `.kiro/specs/remediation-trust-fixes.md`.
> Target outcome: identify gaps before writing code.

---

## Overall score: 7.4 / 10 — CONDITIONAL GO

Scored by the 6-dimension rubric (completeness 25%, accuracy 20%,
security 20%, testability 15%, design alignment 10%, gaps 10%).

| Dim | Weight | Score | Weighted |
|-----|--------|-------|----------|
| Completeness | 25% | 7.5 | 1.875 |
| Accuracy | 20% | 7.5 | 1.50 |
| Security | 20% | 8.0 | 1.60 |
| Testability | 15% | 8.0 | 1.20 |
| Design alignment | 10% | 7.0 | 0.70 |
| Gaps | 10% | 5.0 | 0.50 |
| **Weighted total** | | | **7.375 → 7.4** |

Not high enough for GO. Several concrete gaps are fixable before build.

---

## Critical issues (MUST fix before v2)

### 1. M3-FIX is underspecified for the `AuditEntry` cross-module change

The remediation plan explicitly states: "If `AuditEntry` requires
cross-module changes, make them — this fix is Rule-23 critical." The
spec does acknowledge the M3 change (section 3.3.2) and lists it in the
task index, BUT:

- **My directory boundaries forbid writing to `src/m3_schema_registry/`.** The trust-layer spec lists `src/m3-schema-registry/` (note hyphens) as out-of-scope. However, the remediation plan explicitly authorizes this cross-module change with the language "this fix is Rule-23 critical." This is a steering-exception case parallel to the trust-layer cross-module-import carve-out being documented in Steering §8.

**Action**: add a §3.5 to the spec explicitly calling out the M3 change as a steering-authorized exception. Reference the remediation-plan sentence. Name the protective guardrails: `AuditEntry` changes are confined to the new `tenant_id` field + the `Field(description=...)` entry, no other fields added or removed.

### 2. M4-FIX test-fallout strategy is too optimistic

Section 4.3.2 says "Test repair policy: change the fixture, NOT the
model." That's right in principle, but the current suite has 2127
tests. Flipping 26 models to `strict=True` will cascade into many more
failures than the 10-ish I'm implying.

**Action**: add a mitigation section listing the known coercion patterns
the suite uses (string-to-int, int-to-float, etc.) and a fallback clause:
if a single fixture-fix does not close the failure, we check whether
the model actually NEEDS the coercion semantics (e.g., `Port` accepting
both int and string). For trust-layer models we do NOT make exceptions —
strict is strict. For M11-BLPAPI / M11-gRPC, if a vendor wire format
requires string-serialized numerics, we add an explicit `field_validator`
to the model (not a coercion). Document the pattern in ADR-01.

### 3. M7-FIX does NOT specify what happens to existing `/gateway/call` Helm / deployment manifests

The `app.py` change is clear. But values-cloud.yaml, the ingress
template, and any NetworkPolicy allowlist that references `/gateway/call`
(probably none, but check) must be verified.

**Action**: add a Task under M7-FIX to `grepSearch` for `/gateway/call`
under `deploy/` and `config/`. If any hits, update to `/tools/call` AND
ensure back-compat routing (both paths served by the same Service).

### 4. M8-FIX Vault pull path is vague

AC M8.5 says "fails-closed on Vault-path-only". In practice this means
the operator CANNOT start M1 via Vault yet — only inline PEM works.
That's a regression from today's "stays 503 until someone injects".
It's also the CORRECT fail-closed behavior per Rule 8. But it needs
explicit acknowledgement that operators shipping via Vault today must
now ship inline PEM (or have a follow-up story to pull from Vault).

**Action**: add an §6.3.3 "Operator migration note" explicitly stating:
- Today: operators were expected to inject a real IdentityService at runtime. No env-var path existed.
- After this fix: `AID_PRIVATE_KEY_PEM` is the only supported env path; `AID_PRIVATE_KEY_VAULT_PATH` fails fast with a clear reason.
- Follow-up: a dedicated Vault-pull commit (out of scope here) will implement the Vault resolution.

### 5. M11-FIX shape back-compat window is not bounded

AC M11.2 says "backwards compat for one release" but does not name the
release or the removal path.

**Action**: add a comment to `AuditEmitter.emit` + a line in the ADR-01
that says "Release v0.6.0 removes the legacy `event` + `timestamp_ms`
fields. Operators upgrading from ≤ 0.5.x must update their log
consumers first."

### 6. Integration gate does NOT require the phase-1 scenario suite

The phase-1 integration test `tests/integration/test_phase1_trust_layer.py`
has 7 scenarios. My spec does not explicitly require those 7 to pass
post-fix — it only requires "0 regressions on the full suite."

**Action**: add a bullet to §9.1 saying "The 7 scenarios in
`test_phase1_trust_layer.py` MUST continue to pass — they are the
canonical Phase-1 contract." This is covered by "0 regressions" but
calling it out raises the floor.

---

## Medium issues (SHOULD address)

### M-A. B12 startup check uses private attr `_langfuse`

My design touches `AuditLogger._langfuse` via `backends_by_tier()`. I
already add a public method `backends_by_tier()` (good). Be explicit
that callers MUST go through the method, not the private attr. This
ties the health probe to the public API.

**Action**: add a comment to `AuditLogger.backends_by_tier()` explicitly
stating "Health probes MUST use this, not the private `_langfuse` /
`_worm` / `_crm` attrs."

### M-B. M11-FIX canonical translator needs `target_type` / `target_id` treatment

`AuditEntry` has optional `target_type` + `target_id`. The canonical
translator I wrote sets neither. That's fine per schema (both optional),
but a canary test would help — what fields survive from the canonical
shape into the entry?

**Action**: add a test `test_canonical_audit_entry_preserves_trace_id_and_tenant_id` to `test_m10_audit_canonical_shape.py`.

### M-C. AidClaims `tenant_id` test coverage thin

I add one test for AC M3.1 (missing → ValidationError). I should also
add a positive test (explicit value + `model_dump()` roundtrip) to
lock the shape.

**Action**: expand `test_m1_aidclaims_tenant_id.py` to include a
positive construction test.

### M-D. Steering rule numbering

Section §8 says "collapse Rule 33 into Rule 10." But other rules
reference 33 by number (Rule 33 is mentioned in the review trust-layer
file as well). Collapsing shifts the rule ordering.

**Action**: instead of deleting Rule 33, rewrite it as "Rule 33: see Rule 10
for module-boundary policy (superseded)." That preserves numbering for
references.

### M-E. M7-FIX does not say what `test_m8_m6_shape_match.py` assertions need to keep

The existing test asserts the `/gateway/reasons` route shape + M6↔M8
dataclass field parity. None of that cares about `/gateway/call` per
se — so my fix there is just to add 2 new tests, not modify existing.

**Action**: clarify in §5.3.3 that the existing 6 tests stay as-is;
only `test_m6_tools_call_is_primary_route` + `test_m6_gateway_call_serves_as_deprecated_alias` are new.

### M-F. No explicit mention of UPDATE to `src/m8_pipeline_engine/.env.example` in M7-FIX

If we are renaming the path, the documented default URL for M8 may
need a comment update.

**Action**: verify `.env.example` comments don't reference `/call` or
`/gateway/call`; update if they do.

---

## Minor issues

### m-1. Test file naming consistency

Some new test files use underscores-with-module-prefix (e.g.,
`test_m10_app_failclosed.py`), others don't (`test_values_cloud_global.py`).
The latter is fine since it's not module-scoped, but for consistency
consider `test_helm_values_cloud_global.py`.

### m-2. Docker layer caching

B11 merges YAML comments. Helm tooling treats Values as a dictionary —
comments are lost on template render. This is fine, but we should not
be surprised if a linter strips comments. Not a defect.

### m-3. ADR-01 location

`docs/ADR/ADR-01-pydantic-strict.md` — the `docs/ADR/` directory does
not exist. Need to create it. (fsWrite handles this.)

### m-4. Rule-compliance matrix missing Rule 32

Section §9.4 matrix has Rule 5, 10, 23, 32, 33. Rule 32 entry says "full on 26 trust-layer models." That's the right claim but the claim is about Pydantic strict — which is what M4-FIX delivers. Tighten: "full on 26 trust-layer models post-M4-FIX."

---

## What the spec DOES get right

- **Explicit requirements per fix** with numbered ACs, testable.
- **Design separated from Tasks** — consistent with Kiro spec pattern.
- **Commit strategy** with one logical change per commit.
- **Integration gates** with pytest + deploy gates tied together.
- **New coverage expectations** quantified with minimum counts.
- **Rule-compliance matrix** makes the before/after explicit.
- **Steering carve-out explicitly called out** — prevents repeating the same review finding next cycle.
- **M11 back-compat window** identifies the shim period clearly even if it needs a bounded end-date.

---

## Must-dos before v2

1. Add §3.5 — explicit M3 cross-module authorization callout.
2. Expand §4.3.2 with strict-mode mitigation patterns + field_validator escape hatch.
3. Add `grepSearch` task for `/gateway/call` under `deploy/` + `config/` in M7-FIX.
4. Add §6.3.3 "Operator migration note" in M8-FIX.
5. Add ADR-01 + AuditEmitter comment about M11 shim removal release (e.g., v0.6.0).
6. Add explicit callout that `test_phase1_trust_layer.py` 7 scenarios MUST stay green.
7. Add `backends_by_tier` public-API comment.
8. Add canonical-audit-entry canary test.
9. Expand `test_m1_aidclaims_tenant_id.py` with positive case.
10. Rewrite Rule 33 as "see Rule 10" instead of deleting.
11. Clarify existing `test_m8_m6_shape_match.py` tests stay as-is.
12. Verify `.env.example` for M8 has no stale `/gateway/call` comment.

All fixable in spec edits before build.

---

## Proposed v2 path

Address all 12 action items above. Re-score. Target ≥ 8.0 GO.
