# Gap 1 — Reg BI Doc Generator — LLMJ Review v1 (of spec v3)

> Reviewer: LLMJ (compliance-agent expertise — Phase-3 BD review)
> Target: `.kiro/specs/gap1-reg-bi-doc-generator.md` (v3)
> Prior history: v1 → v2 of spec scored 7.7 → 8.7 GO. This review is the
>   v1 LLMJ pass over the Phase-3 **v3** expansion that adds OPA matrix,
>   M4 MNPI preflight, canonical disclosure types, renderer, principal
>   review queue, and Smarsh hook.
> Rubric: 0.0–10.0, GO ≥ 8.0.

---

## Summary scores (v3 draft)

| Dimension                              | v2  | v3 draft |
|----------------------------------------|-----|----------|
| Requirements clarity                   | 8.6 | 7.8      |
| Determinism / no-LLM contract          | 8.8 | 8.4      |
| Fail-closed semantics                  | 8.4 | 7.8      |
| Module boundary enforcement            | 9.0 | 8.6      |
| PII / security                         | 8.6 | 8.2      |
| Test traceability                      | 8.8 | 7.6      |
| Canonical JSON / hash contract         | 8.8 | 8.2      |
| Applicability gate precedence          | 9.0 | 9.0      |
| OPA matrix design (NEW)                | —   | 7.6      |
| MNPI preflight (NEW)                   | —   | 7.8      |
| Renderer contract (NEW)                | —   | 7.4      |
| Principal review queue (NEW)           | —   | 7.6      |
| Smarsh hook (NEW)                      | —   | 8.0      |
| **Overall**                            | 8.7 | **7.9**  |

Below 8.0 on first pass of the expansion — findings itemized, fixes
tractable in one rewrite.

---

## Findings (fix before v2 review)

### F1 — `renderer` ordering in flow vs `rendered_content_sha256`

**Severity: high.** R7.3 step 8 renders the HTML BEFORE building the
document (step 9), but the document field `rendered_content_sha256`
is a regular field. For step 8 to populate it, we either need a two-
phase build or the renderer must take the UN-finalized data.

**Recommendation.** Two options:
(a) Drop `rendered_content_sha256` from `RegBiDocument`; store it on
    `RenderedDocument` only; generator returns a pair
    `(RegBiDocument, RenderedDocument | None)` OR exposes renderer
    as a follow-up method.
(b) Build doc WITHOUT the field, render, then build a second immutable
    doc `with_rendered_hash(...)` that copies + sets the field.

Pick (b) — keeps `generate(...)` single-return and keeps the hash
bound to the document for downstream consumers (Smarsh, audit).
Clarify in R7.3 + §2.2.

### F2 — `SmarshArchiveClient.archive` accepts both doc AND rendered

**Severity: medium.** Smarsh expects a communications record, which
for a Reg BI doc means the rendered body + metadata. If rendering
failed or renderer wasn't wired, calling archive with a None rendered
is an interface violation. Either make `rendered` optional (and lax in
the stub) or **require renderer** when `smarsh_client` is wired.

**Recommendation.** Require renderer wiring when smarsh is wired;
raise `ValueError("smarsh_requires_renderer")` at `__init__` if
smarsh is provided without renderer. Document in R7.1b.

### F3 — `AuditClient` typing for SKIP path

**Severity: medium.** R8.1 `write(record: RegBiDocument |
GenerationSkipped)` — that is fine at the type level, but `R7.3 step
2b` conflates audit failure semantics for skip vs doc paths. SKIP
audit failure should NOT raise (skip is a log-only event), or the
generator is brittle to a transient audit sink issue on a skip that
had no downstream consequence.

**Recommendation.** SKIP-path audit failure swallows silently (log
internally via a hook) since there is no document to protect; doc-
path audit failure raises (17a-4 violation risk). Clarify in R7.3
step 2b and R8.3.

Alternative: both raise. Pick one; the stronger fail-closed posture
(both raise) is consistent with the project's overall stance. If we
pick "both raise", tests T1.25 need a skip-path twin.

**Decision for v2:** both raise. Fail-closed beats clever silence.

### F4 — OPA matrix — Rego shape mismatch

**Severity: medium.** `rule_applied` regex is
`^reg_bi/matrix/[a-z0-9_]+\.v[1-9]\d*$`. Other 007 rules use path
shape `package/module/rule_name.vN` (e.g. `authority/advisor/
restricted_list.v1`). Our matrix uses `reg_bi/matrix/...` — acceptable
prefix but the lift-to-Rego will map `reg_bi.matrix.<rule_name>`.

**Recommendation.** Name the rules
`reg_bi.matrix.base.v1`,
`reg_bi.matrix.tier3_broker_dealer.v1`,
etc. Keep the slash shape in Python (`reg_bi/matrix/...`) since that is
consistent with Gap 2 / M4 Phase-1 rule_applied; add an assertion that
`rule_applied.replace("/", ".")` is the Rego package path. T1.36a.

### F5 — `narrative_model_used` vs `narrative_model` coupling

**Severity: low.** R4.7 stores `narrative_model` on the doc. If the
hosting service swaps in a real Haiku client, the stub
`BulletConcatNarrativeClient` is used in-process but
`narrative_model_used` reads "haiku" from config. That's a lie —
field records intent, not actuality.

**Recommendation.** Rename field to `narrative_model_configured` and
accept the "intent, not actuality" semantic in the description; OR
also record `narrative_client_class_name: str`. Pick the former —
cheaper and the hosting service is the only place where reality
differs from config. Update R6.1 + R4.7 wording. Add test T1.51b
asserting field records CONFIG value regardless of wired client.

### F6 — `RegexMnpiFilter` duplicates `_scrub_pii`

**Severity: low.** The Phase-3 default MNPI filter is a regex filter
that uses the same four patterns as `_scrub_pii`. Having two copies
means pattern drift is silent. Either:
(a) Import the patterns from `document.py::_PII_PATTERNS`.
(b) Re-declare and add a cross-check test.

**Recommendation.** (a). Narrow the boundary by importing.
`mnpi_preflight.py` can import from `document.py`. Document in R4b.2.

### F7 — `is_retail` placement

**Severity: low.** `is_retail` is on both `ResolvedRequirements` AND
the final `RegBiDocument`. Is this redundant?

**Recommendation.** Keep on both. `ResolvedRequirements` is the
in-flight computation; `RegBiDocument` surfaces it for FINRA examiner
retrieval (a retail flag on the archived document is auditor-
expected). Add a note in R6.1 + R3.7.

### F8 — Golden-hex T1.19 bootstrap procedure

**Severity: low.** T1.19 says "golden hex" but not how to bootstrap.
The test needs a fixture that produces the same document twice, with
a pinned document_id and pinned generated_at.

**Recommendation.** Spec should say:
- Injected `document_id_factory = lambda: UUID('11111111-1111-4111-
  8111-111111111111')`.
- `generated_at = datetime(2026,1,1, tzinfo=UTC)`.
- Use `BulletConcatNarrativeClient` (deterministic).
- On first run, assert-and-capture; second run asserts equality with
  captured value. Gap 2 T2.17 is the template.

Add as explicit procedural note in T1.19.

### F9 — Principal-queue before OR after audit

**Severity: medium.** R7.3 steps 11 and 14 put enqueue pre_use BEFORE
step 13 (audit) and post_use AFTER audit. Pre-audit enqueue means a
principal could review a doc that never made it to WORM — if audit
fails at step 13, queue has stale entry.

**Recommendation.** Either:
(a) Both enqueue AFTER audit (rename "pre_use" → "pre_use in lifecycle
    vs principal decision", which is the FINRA 2210 semantic: pre_use
    means before COMMUNICATION USE, not before audit).
(b) Keep pre_use before audit but add a compensating: if audit fails,
    principal queue gets an invalidation event.

Pick (a). FINRA 2210 "pre_use" = "before the communication is used
with the public" — it does NOT mean before the audit log is written.
Reword R7.3 + R9.1 accordingly.

### F10 — Test count: unit ≥30 claimed, actual enumeration

**Severity: low.** Counting T1.1..T1.53 with sub-IDs (T1.18b,
T1.29b, T1.30b, T1.31a, T1.36a, T1.42b, T1.46b..d, T1.51b, T1.51,
T1.52, T1.53), there are ~50 test funcs. Good — exceeds 30. Keep.
Document total count in §3.1 header for the builder agent.

### F11 — Integration I5 semantics

**Severity: low.** I5 says "audit write failure → generator
propagates; Smarsh still ran pre-audit (we verify M10 is the LAST
write)". With F9 fix applied, ordering is:
1. Render
2. Smarsh archive
3. Audit write  ← raises
4. Principal queue (post_use)

So if audit fails, principal queue never gets the entry — good. But
Smarsh has the record with a doc that "never happened" per WORM.
That is an actual Phase-3 risk, not a spec bug; Smarsh expects
compensating deletion or the doc is kept and re-audited on retry.

**Recommendation.** Document in §5 Risks. Add I5 to verify Smarsh
was called and audit raised — it's a legit verification; the
compensation design is Phase-3 Smarsh-adapter concern.

### F12 — `OpaRequirementsResolver` thread-safety

**Severity: trivial.** Resolver holds `REQUIRED_SECTIONS_MATRIX` at
module load; immutable tuple of frozen models → thread-safe. Document
explicitly.

### F13 — Missing test for `SmarshArchiveFailed` string

**Severity: trivial.** T1.45 says "raises `SmarshArchiveFailed(
'smarsh_archive_failed')`" — add assertion that `str(exc) ==
"smarsh_archive_failed"` mirrors the AuditWriteFailed pattern (R8.3).

### F14 — `product_type` string-typed vs enum

**Severity: low.** R1.2 lists `product_type: str | None` with a set
of allowed values but no validator. Two routes:
(a) Accept any string (matrix has default fallthrough).
(b) Add field_validator limiting to the enumerated set.

**Recommendation.** (b) — use a `Literal[...]` union type or a
`ProductType` enum. Keeps the OPA matrix closed. Phase-4 can
expand. Spec clarification in R1.2.

### F15 — `CanonicalDisclosures` model is implied, not declared

**Severity: low.** R6.1 references `canonical_disclosures:
CanonicalDisclosures` but R3b lists the 7 individual types without
binding them into a single model. Add:
```
class CanonicalDisclosures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    conflict_inventory: ConflictInventoryDisclosure
    best_interest_rationale: BestInterestRationale
    fees_and_compensation: FeesAndCompensation
    product_scope: ProductScope
    monitoring_frequency: MonitoringFrequency
    discipline_history_link: DisciplineHistoryLink
    limitations: Limitations
```

Document in R3b.

---

## Decision

**SCORE: 7.9 — NO-GO. Fixes required before build.**

Findings F1, F2, F3, F4, F9 are structural; F5..F15 are polish. A
single rewrite pass addresses all of them. The v3 core architecture
(OPA matrix + MNPI preflight + renderer + queue + Smarsh) is sound —
only the interfaces and sequencing need tightening.

Re-review after rewrite.
