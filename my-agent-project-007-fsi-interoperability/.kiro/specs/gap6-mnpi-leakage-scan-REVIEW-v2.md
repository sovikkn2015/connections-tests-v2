# Gap 6 — MNPI Leakage Scan — LLMJ Review v2

> Re-review of `.kiro/specs/gap6-mnpi-leakage-scan.md` (v2).
> Target: 7.5+/10 weighted for GO.

---

## FIX VERIFICATION (v1 — v2)

| v1 item | v2 addresses | Verified |
|---------|--------------|----------|
| F1 (FP/FN acknowledgments)  | §0.1 (email noise, account_number breadth, SSN-dashed limit, IBAN shape) | OK |
| F2 (STUB-warning docstring) | R4.2 literal + T6.9b | OK |
| F3 (aggressive-NER lock-in) | R3.2 + T6.7b | OK |
| F4 (error_message regex)    | R1.2 + R5.4 + T6.21b | OK |
| F5 (ReDoS)                  | R2.1 linear-time + T6.26 | OK |
| F6 (None strict unified)    | R2.3 TypeError on None; matches R5.6 | OK |
| F7 (empty-latency doc)      | R5.6, R5.8 | OK |
| F8 (error-path latency)     | R5.8 explicit | OK |
| R1 (match_codes rename)     | R1.2 + consistent throughout | OK |
| R2 (keyword list 25)        | R4.2 expanded, categorized | OK |
| R3 (scan_id)                | Deferred (non-blocking) | N/A |
| R4 (T6.22 expected)         | `{A:5, B:12, C:10}` published | OK |
| R5 (KEYWORDS stability)     | R4.2 documented | OK |
| R6 (Protocol compliance)    | T6.27 | OK |
| R7 (latency CI scope)       | §0.1 + R6.3 | OK |
| R8 (no-match fast path)     | T6.3 `"this is clean text"` | OK |

All 8 blocking fixes verified. 7 of 8 recommendations addressed.

---

## SCORES (v2)

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 8.5   |
| Testability      | 15%    | 9.0   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |

Calculation:
- 25*8.5 + 20*8.5 + 20*8.5 + 15*9.0 + 10*8.5 + 10*7.5
- = 212.5 + 170 + 170 + 135 + 85 + 75 = 847.5
- / 100 = 8.475

**Weighted total: 8.48 / 10 — GO.**

Margin above 7.5 threshold: +0.98.

---

## MINOR ITEMS FOR IMPLEMENTATION (non-blocking)

### M1. `ERROR_MESSAGE_RE` as public constant

Expose `ERROR_MESSAGE_RE = re.compile(...)` at scanner module level
so tests can import and reuse it. Prevents test-side duplication.

### M2. Scanner loop vs unrolled

Sketch uses a for-loop. An unrolled form (3 explicit try/except
blocks) is also acceptable. Unrolled reads cleaner; looped is more
compact. Test coverage is identical.

### M3. `match_codes` tuple serialization

Pydantic serializes tuples to JSON arrays. Test comparisons should
use tuples explicitly (not lists). Document in test header.

### M4. Stub input validation completeness

Add Layer C stub input-validation tests (None / non-str / oversized)
to T6.28 parametrization. T6.7c handles NER; T6.28 should cover
both.

### M5. `_default_clock` visibility

Private helper; not part of public API. Tests inject their own fake.

### M6. KEYWORDS source organization

Flatten to one `_KEYWORDS` tuple at module level. Category
documentation lives in a comment block. Runtime behavior is a single
linear scan.

### M7. `PATTERNS` dual exposure

Module-level `PATTERNS` (for `from ... import PATTERNS`) and
`LayerARegexScanner.PATTERNS` (class alias) bound to same tuple
object. Consistency guaranteed.

---

## VERDICT

**GO. 8.48 / 10.**

Gap 6 v2 resolves every blocking issue from v1. False-positive
acknowledgments make the fail-closed design auditable. ReDoS
protection is mechanical. Error-message discipline prevents input
leakage. Stub non-production docstring prevents accidental deployment.

7 minor implementation items noted; none blocking.

**Both Gap 2 (8.30) and Gap 6 (8.48) pass the 7.5 threshold. Proceed
to build.**
