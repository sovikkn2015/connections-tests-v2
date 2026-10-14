# Gap 6 — MNPI Leakage Scan — LLMJ Review v1 (HARSH)

> Reviewer role: skeptical compliance-specialist LLMJ, tuned hostile.
> Scoring: 6 dimensions, must hit 7.5+/10 weighted for GO.
> Spec reviewed: `.kiro/specs/gap6-mnpi-leakage-scan.md`

---

## SCORES

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 6.0   |
| Accuracy         | 20%    | 7.0   |
| Security         | 20%    | 6.0   |
| Testability      | 15%    | 8.0   |
| Design alignment | 10%    | 8.0   |
| Gaps             | 10%    | 5.0   |

**Weighted total: 6.625 / 10 — CONDITIONAL GO — REVISE.**

---

## REQUIRED FIXES (blocking)

### F1. Regex false-positive / false-negative acknowledgments missing.

- Email regex fires on benign mentions ("info@example.com"). Fine at
  this layer (fail-closed), but document the trade-off.
- `account_number` fires on any 12+ digits (timestamps, tracking
  numbers, prices in cents).
- SSN regex does NOT catch undashed 9-digit SSNs (`123456789`).
  Either add a second pattern `ssn_nodash = \b\d{9}\b` (high FP) OR
  document Phase 1 limits; Phase 2 NER catches undashed forms.
- IBAN regex is shape-only; no mod-97-10 checksum. Document.

Publish these explicitly in R2.1 so Phase 1 isn't considered
bulletproof.

### F2. Phase 1 stub must be flagged as non-production.

R4.2 keyword list is fine in the spec. But the SOURCE file MUST carry
a docstring warning: "STUB — PHASE 1 ONLY. MUST NOT be deployed to
production. Replace with Bedrock Haiku classifier (Phase 2) before any
customer deployment."

Also: the source file MUST NOT include real-world MNPI examples in
comments ("e.g., 'Apple will beat by 10¢'"). Spec should state this
explicitly.

Add a deployment gate: Phase 2 replaces the stub before any customer
deployment.

### F3. Layer B stub false-positives on common non-PII phrases.

"Federal Reserve", "New York", "Black Scholes", "Wall Street" all
match the capitalized-pair pattern. This is acceptable (fail-closed),
but must be documented explicitly:

"StubNamedEntityRecognizer is intentionally aggressive. Common non-PII
capitalized phrases (Federal Reserve, New York, etc.) WILL be blocked
by the stub. Phase 2 NER (spaCy) replaces it and allows benign
entities."

Add a test T6.7b asserting "Federal Reserve" IS blocked — locks in
the aggressive behavior so future "smart fix" PRs can't regress
fail-closed.

### F4. R5.4 error_message leak risk.

`error_message = f"{layer_code}:{type(exc).__name__}"`. Exception class
names are bounded by Python naming rules but Phase 2 libraries
(spaCy, boto3) can raise exceptions whose class names are generic
("InvalidRequestError") but whose repr or str contains input-derived
fragments. Defense: ONLY `type(exc).__name__`, never `str(exc)`,
never `repr(exc)`. And enforce:

"`error_message` MUST match regex `^layer_[abc]:[A-Za-z_][A-Za-z0-9_]*$`
— no whitespace, no parentheses, no content derived from input."

Add T6.21b asserting this regex on a fixture where the inner exception
carries an exotic message.

### F5. ReDoS protection missing.

Regex catastrophic backtracking is a real attack vector. Email regex
has nested quantifiers (`[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+`) — linear,
safe. But confirm:

"Each Layer A pattern MUST be verified as linear-time (no nested
quantifiers on overlapping character classes, no backreferences).
T6.26: scan(`'a' * 100_000`) completes in <100ms. Scan(`'-' * 100_000`)
completes in <100ms."

### F6. Layer A vs scanner None-handling inconsistency.

R2.3: `LayerARegexScanner.scan(None) → (ALLOW, ())`.
R5.6: `MnpiLeakageScanner.scan(None) → TypeError`.

This asymmetry is a footgun. Pick one contract:

**Recommendation**: Make BOTH strict. Layer A raises `TypeError` on
None too. The "defensive None" behavior invites callers to pass
unchecked data — exactly what fail-closed tries to prevent.

Revise R2.3: `scan(None)` raises `TypeError`.

### F7. Empty `latency_ms_per_layer` for empty-string input is
ambiguous to monitoring.

For a caller monitoring per-layer latency in metrics, an empty dict
looks like a skipped scan. Document:

"`latency_ms_per_layer` is empty iff the scanner took the empty-string
fast path (no layers ran). Metrics callers MUST treat empty dict as
'scan skipped'. A non-empty dict always contains `A` at minimum (or
the exact subset of layers that executed)."

### F8. R5.8 clarify Layer A error-path latency.

"When a layer raises, its own latency is NOT recorded (measurement
aborted). Prior layers' latencies ARE recorded."

This makes the invariant testable: T6.18 asserts timings is empty when
Layer A raises; T6.19 asserts `{"A": <int>}` when Layer B raises;
T6.20 asserts `{"A", "B"}` keys when Layer C raises.

---

## RECOMMENDED FIXES (non-blocking)

### R1. `matches` field name invites misuse.

The name "matches" suggests raw matched text. Rename to `match_codes`
or `flags` — matches the R2.4 contract that NO raw text is emitted.

### R2. Keyword list too small.

9 keywords is a sparse stub. Phase 1 should have 20-30 covering
earnings, M&A, insider, and timing terms. Not blocking (it's a stub)
but a useful stub is better.

### R3. Add `scan_id` to `ScanResult`.

For M6 — M10 audit correlation, a short UUID or SHA-256 prefix. Phase 1
can leave it optional; Phase 2 populates.

### R4. Publish expected timings in T6.22.

Spec says "Injectable clock test". Publish the expected dict:
`{"A": 5, "B": 12, "C": 10}` given clock sequence `[0, 5M, 8M, 20M, 25M,
35M]`. Removes ambiguity.

### R5. `StubLlmClassifier.KEYWORDS` visibility.

Expose for Phase 1 testability. Document that Phase 2 classifiers have
no such attribute — callers who depend on `.KEYWORDS` break. Protocol
is the ONLY stable contract.

### R6. Protocol compliance test.

Add a test that a custom class implementing `.scan(text) ->
(ScanDecision, tuple[str, ...])` works with `MnpiLeakageScanner(ner=
CustomNer())`. Prevents accidental Protocol narrowing.

### R7. Latency assertion absence explanation.

"Budgets <10ms / <100ms / <2s are DOCUMENTED, not ASSERTED. CI latency
gates are a Phase 2 concern (machine variance). Phase 1 asserts
correctness only."

### R8. Add T6.3b to assert all-pattern no-match fast path.

`LayerARegexScanner.scan("hello world")` — ALLOW `()`. Document:
scanner still iterates all patterns but returns ALLOW when none match.
This behavior (iterate all) is desirable: unioned match codes on hits.

---

## SUMMARY

- 8 blocking fixes (F1-F8).
- 8 recommended fixes (R1-R8).

Key issues:
- False-positive / false-negative acknowledgments missing (F1, F3).
- Stub must be flagged non-production (F2).
- error_message leak defense (F4).
- ReDoS protection (F5).
- None-handling inconsistency (F6).
- Empty-scan latency ambiguity (F7).
- Error-path latency recording (F8).
- `matches` naming (R1).
- Keyword list coverage (R2).

Core design (3-layer, fail-closed, injectable Protocols) is sound.
But compliance scanners live and die by edge cases, and this spec
papers over several.

Re-review required after fixes. Target 7.5+/10.
