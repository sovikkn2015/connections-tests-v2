# M10 Audit Logger — LLMJ Review (v1)

> Reviewer: 007-trust-agent (LLMJ pass 1)
> Spec under review: `.kiro/specs/m10-audit-logger.md` (v1)
> Stance: HARSH. Every weakness surfaced. Missing details matter.
> Verdict format: score per dimension, overall, required vs recommended fixes.

---

## Scoring rubric

| Dimension | Weight |
|-----------|--------|
| 1. Completeness | 25% |
| 2. Accuracy | 20% |
| 3. Security | 20% |
| 4. Testability | 15% |
| 5. Design Alignment | 10% |
| 6. Gaps | 10% |

Threshold for GO: >= 7.5/10 overall AND no open REQUIRED fixes.

---

## 1. Completeness — 6.5/10

### What's good
- AuditLogger surface covers write, verify_integrity, query_by_trace_id, health.
- AuditBackend + InMemoryAuditBackend + AuditDLQ + InMemoryAuditDLQ all specified.
- ProvenanceChainBuilder has a full API and module regex.
- Frozen reason vocabulary enumerated.
- Golden vector discipline called out.
- Traceability table to design docs + steering rules.

### What's missing or thin

**F1 (REQUIRED) — InMemoryAuditBackend.query_by_trace_id behavior unspecified.**
R4.2 class signature lists `query_by_trace_id` only in R4.1's Protocol and R7.1
AC. There is no explicit requirement that `InMemoryAuditBackend` implements it,
what it filters on, or case-sensitivity. R7.1 AC-R7-3 asserts WORM-only
delegation but the method's filter semantics on the in-memory backend are
assumed, not stated.

**F2 (REQUIRED) — `AuditBackend` Protocol method `query_by_trace_id` phase-2
contract unclear.** Real Phase 2 S3 Object Lock CANNOT implement
query_by_trace_id efficiently. The spec needs to allow a Phase 2 backend to
raise `NotImplementedError` OR clearly state that this is debug-only and
M10's `AuditLogger.query_by_trace_id` is a no-op against production
backends. Current text is ambiguous.

**F3 (REQUIRED) — No definition of "tier" attribute discovery.**
Constructor validation says "backend.tier must match its slot." What if the
backend has no `tier` attribute (duck-typing failure)? The spec must say:
`getattr(backend, "tier", None) != expected_tier -> AuditWriteError("invalid_backend_tier")`.
Otherwise an `AttributeError` leaks.

**F4 (REQUIRED) — `AuditEntry.module` is a free-form string, NOT validated
against m1..m13.** The spec puts the regex on `ProvenanceStage.module` only.
The consolidated design says audit entries record which module generated them.
A caller could write `entry.module = "m99"` and the entry would be accepted.
Decide: either (a) enforce the same regex in AuditLogger.write, or (b) state
explicitly that M10 trusts the caller and a separate M3 validator handles it.
Ambiguity = security gap.

**F5 (RECOMMENDED) — No spec for what happens if DLQ is the SAME object
across multiple AuditLogger instances.** Common test footgun. State: DLQ is
shared by reference; callers are responsible for isolation. Add a note.

**F6 (RECOMMENDED) — No spec for list-field ordering stability in the
canonicalised hash.** `provenance_chain` is a list. If a caller builds the
list in one order, and a different caller builds it in another, the hash
differs. The spec needs to say: list order IS semantically significant for
hash purposes (that's correct, but make it explicit).

---

## 2. Accuracy — 7.0/10

### What's good
- Matches ARCH-09 M10 row (3-tier, SHA-256, 6-year, fail-closed).
- AuditEntry field list aligns with M3 (spot-checked canonical_id, trace_id,
  sha256_integrity, retention_years, provenance_chain).
- ProvenanceStage matches M3 (stage, module, hash, timestamp).
- Hash canonicalisation uses Pydantic v2 `model_dump(mode="json", exclude=...)`.

### What's wrong or imprecise

**F7 (REQUIRED) — `_json_default` is dead code as written.**
Spec says "Pydantic v2 JSON mode already normalizes UUID/datetime/enum to
strings, so `_json_default` is defensive only." If `model_dump(mode="json")`
emits strings, then `json.dumps(..., default=_json_default)` on a dict of
primitives never hits `_json_default`. Either:
  - Remove `_json_default` entirely (rely on Pydantic's JSON mode), OR
  - Document that `_json_default` is reachable ONLY from the provenance
    stage payload hash (where caller-provided arbitrary `payload` DOES flow
    through `_canonical_json`).

The spec should clarify which call sites use `_canonical_json` with raw
user payloads vs dumped pydantic output.

**F8 (REQUIRED) — datetime ISO format not pinned.**
`datetime.isoformat()` output depends on tzinfo. A `datetime(..., tzinfo=utc)`
serializes as `2026-04-14T12:00:00+00:00`. Pydantic v2 JSON mode may
serialize differently depending on version/config. A mismatch between the
pydantic path (AuditEntry hash) and the raw path (stage payload hash) would
produce DIFFERENT ISO strings for the same wall-clock time. Pin one: spec
must require explicit `.isoformat()` everywhere AND verify pydantic default
matches, OR override pydantic's serializer for timestamps.

**F9 (RECOMMENDED) — Golden vector production method not reproducible.**
Spec says "Hash vectors are computed during implementation by running the
canonicalisation once and pasting the hex." Circular — the test pins
whatever the implementation produced, so it can't detect the implementation
being wrong on day 1. Improve: provide an independent Python one-liner that
computes the vector from a hand-constructed JSON string. The test compares
against that independently-computed hex.

---

## 3. Security — 7.5/10

### What's good
- Frozen reason vocabulary.
- No credentials policy with concrete regex.
- Error message hygiene (`str(exc) == exc.reason`).
- No entry contents in error messages or logs.
- Fail-closed on all tier failures.

### What's thin or missing

**F10 (REQUIRED) — DLQ enqueue failure path is vague.**
R6.2 AC-R6-5 says "DLQ enqueue failure is logged but does NOT mask the
original tier failure reason." But: (a) no logging infrastructure is
specified (what logger? what level?), (b) the spec forbids logging entry
contents — but if DLQ fails AND we don't log, the failed entry is lost
entirely. Decide:
  - M10 keeps an in-memory fallback list ("lost_entries") that survives
    DLQ enqueue failure, OR
  - M10 accepts the entry is lost if DLQ fails (document the risk), OR
  - M10 raises a secondary warning exception.

Current spec is silent on the actual mechanism. Pick one.

**F11 (REQUIRED) — No defense against untrusted `entry.sha256_integrity` on input.**
An input `AuditEntry` can carry a non-empty `sha256_integrity` already
(Pydantic accepts any str). The spec says M10 computes and attaches its own.
But does M10 REJECT a pre-populated hash, or silently overwrite? Decide:
  - REJECT: `AuditWriteError("invalid_entry")` if input.sha256_integrity is
    non-empty (caller must pass empty string).
  - OVERWRITE: silently recompute and replace.

Current test fixture passes `sha256_integrity=""`, which implies expected
behavior is "empty string required," but the requirement is not stated.
Document.

**F12 (RECOMMENDED) — No tampering detection at write time.**
If the caller modifies a sealed entry and tries to `write` it again (rarely
intended, but possible), M10 will just overwrite. Fine — M10 is idempotent
— but state it. Tests should cover: `logger.write(sealed_entry)` returns a
sealed entry with IDENTICAL hash (deterministic) and the DLQ + backend
semantics are same as first write.

**F13 (RECOMMENDED) — No rate limiting or size limit on DLQ.**
An attacker could fill DLQ in memory. State: DLQ is unbounded in Phase 1;
production implementation MUST bound it. Add to non-goals.

---

## 4. Testability — 7.5/10

### What's good
- 27 tasks, each tied to ACs.
- 40-55 tests target.
- Golden vectors for hash AND provenance chain.
- Fixture is explicit with fixed UUIDs and timestamps.
- AST scan + credential regex sweep.

### What's missing

**F14 (REQUIRED) — No explicit test for "write twice is idempotent-like."**
See F12. Add a task: write the same entry twice, verify hash is
identical, verify two entries in each backend.

**F15 (REQUIRED) — No test that DLQ does NOT fire on success.**
AC-R6-4 is listed but the task list (T21) only partially covers it. Make
explicit: after a happy-path write, assert `dlq.records == []`.

**F16 (RECOMMENDED) — Perf test is wall-clock based (flaky on CI).**
AC-R10-1 "1,000 writes < 5s" can fail on slow CI. Either:
  - Make it 10s tolerance, OR
  - Mark the test as `@pytest.mark.slow` and exclude from default run, OR
  - Just measure per-write microseconds and assert shape (not threshold).

**F17 (RECOMMENDED) — Golden vector test not isolated.**
One golden vector test for AuditEntry hash, one for ProvenanceStage hash.
Keep them separate and label clearly so a canonicalisation change shows
exactly where it broke.

---

## 5. Design Alignment — 8.0/10

### What's good
- Maps to ARCH-09 M10 row, ARCH-07 stack.
- Consolidated design Part 3 and Part 9 Gap 2 both referenced.
- Steering rules 3, 4, 6, 7, 8, 9, 10, 13 addressed.
- Library-vs-service scoping matches M1 precedent.

### What's off

**F18 (REQUIRED) — Steering rule 19 (wsp_section) handling is incomplete.**
Spec §2.9 says "M10 STORES wsp_section on AuditEntry but does not produce
rules." Fine — but the test should verify that M10 does NOT drop or alter
`wsp_section` on the entry. Add a test that the sealed entry preserves
every non-hash field exactly as input.

**F19 (RECOMMENDED) — No mention of how M10 interacts with M6's trust pipeline.**
The consolidated design Part 3 shows M10 as the final stage of every trust
pipeline call. The spec should note that M6 is expected to call
`AuditLogger.write` synchronously on every gateway request — and that the
fail-closed semantics mean a failed audit write blocks the gateway
response. Add to §0 or §9 traceability.

**F20 (RECOMMENDED) — M3 version pinning unaddressed.**
If M3's AuditEntry adds a field in v0.2, does M10 break? State: M10 depends
on `m3_schema_registry >= 0.1.0 < 0.2.0` or equivalent. Version story is
missing.

---

## 6. Gaps — 6.5/10

### What's covered
- Gap 2 (Liability Provenance) explicit.
- Frozen vocabulary.
- 3-tier fail-closed.

### What's not

**F21 (RECOMMENDED) — No health check for backends.**
`AuditLogger.health()` reports tier names but doesn't ping backends. For
Phase 1 that's fine. State: health is a metadata-only check; real backend
health is Phase 2.

**F22 (RECOMMENDED) — No "fan-out" parallelism consideration.**
Three sequential writes = higher latency. Phase 1 is sequential (correct
for determinism). State: Phase 2 may parallelize (with careful DLQ handling).

**F23 (REQUIRED) — No guidance on what the caller does after `AuditWriteError`.**
The spec says "originating caller MUST treat this as a hard failure and
propagate." But then what? Gateway returns 500 to client? Document the
expected upstream behavior — even if M10 doesn't enforce it, the spec is
the contract for M6's integration.

**F24 (RECOMMENDED) — No provenance-chain-on-entry handling.**
AuditEntry has `provenance_chain: list[ProvenanceStage]`. If the caller
builds a chain with `ProvenanceChainBuilder` and attaches it to an
AuditEntry, the entry hash covers the chain (good). But there's no
example / reference showing the intended idiom. Add a usage example.

---

## Summary of fixes

### REQUIRED (must fix before GO)
1. **F1** — InMemoryAuditBackend.query_by_trace_id behavior stated
2. **F2** — AuditBackend.query_by_trace_id contract for Phase 2 S3
3. **F3** — Missing-tier-attribute path specified
4. **F4** — AuditEntry.module validation decision (enforce or explicitly trust caller)
5. **F7** — `_json_default` scope clarified (pydantic path vs raw payload path)
6. **F8** — datetime ISO format pinned across both paths
7. **F10** — DLQ enqueue failure mechanism chosen (lost_entries? log? re-raise?)
8. **F11** — Pre-populated `sha256_integrity` on input: reject or overwrite
9. **F14** — Test task for "write twice idempotent-like"
10. **F15** — Test task for "DLQ empty on success" explicit
11. **F18** — Test that sealed entry preserves all non-hash fields
12. **F23** — Document upstream caller contract after AuditWriteError

### RECOMMENDED (fix if quick)
- F5 — DLQ sharing note
- F6 — List order hash significance
- F9 — Independent golden vector computation
- F12 — "Write twice" tampering semantics
- F13 — DLQ unbounded note (Phase 1)
- F16 — Perf test robustness
- F17 — Separate golden vectors per hash flavor
- F19 — M6 integration note
- F20 — M3 version pinning
- F21 — Health check scope
- F22 — Sequential vs parallel phase note
- F24 — Usage example with ProvenanceChainBuilder

---

## Overall

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Completeness | 6.5 | 25% | 1.625 |
| Accuracy | 7.0 | 20% | 1.400 |
| Security | 7.5 | 20% | 1.500 |
| Testability | 7.5 | 15% | 1.125 |
| Design Alignment | 8.0 | 10% | 0.800 |
| Gaps | 6.5 | 10% | 0.650 |
| **TOTAL** | | | **7.10 / 10** |

### Verdict: CONDITIONAL GO

Close to the 7.5 threshold but NOT there. 12 required fixes must be
addressed in v2. Most are small clarifications. A full rewrite (not
patches) should land all 12 required + most of the 12 recommended.

Expected v2 score: 8.2-8.5/10 once required fixes land.

---

*m10-audit-logger-REVIEW.md — LLMJ pass 1*
