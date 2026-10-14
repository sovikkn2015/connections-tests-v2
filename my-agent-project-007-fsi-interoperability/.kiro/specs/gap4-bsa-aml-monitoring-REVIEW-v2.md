# Gap 4 — BSA/AML Monitoring — LLMJ Review v2

> Re-review of `.kiro/specs/gap4-bsa-aml-monitoring.md` (v2).
> Target: 7.5+/10 weighted for GO.

---

## FIX VERIFICATION (v1 → v2)

| v1 item | v2 addresses | Verified |
|---------|--------------|----------|
| F1 (Decimal thresholds) | R1.3 + `CTR_THRESHOLD_USD = Decimal("10000.00")` | OK |
| F2 (anti-tipping-off invariants) | R7.3 explicit + T4.32 | OK |
| F3 (route_to Literal) | R2.3 `Literal["compliance_officer"]` + T4.5 | OK |
| F4 (reason vocabulary frozen) | R2.4 + T4.7 | OK |
| F5 (matched_transactions uniqueness) | R2.5 + T4.8 | OK |
| F6 (enabled=False no-op enumeration) | R6.1, R6.2 + T4.24, T4.25 | OK |
| F7 (window boundary semantics) | R4.5 half-open + T4.11 | OK |
| F8 (Rego wsp_section annotations) | R8.1 + §2.4 rego sketch + T4.34 | OK |
| F9 (audit write failure → AlertEmitFailed) | R7.4 + T4.33 | OK |
| R1 (wiring diagram) | §2.1 ASCII | OK |
| R2 (line budget breakdown) | §0.5 | OK |
| R3 (Phase 4 forward-compat) | §0.1 + R4.4 `RedisWindowStore` stub | OK |
| R4 (thread safety) | R4.3 `threading.Lock()` + T4.14 | OK |
| R5 (M2 PolicyRule Protocol) | R5.4 + T4.26 `isinstance` check | OK |
| R6 (AST boundary scan) | §2.5 + T4.36 | OK |
| R7 (archetype gate via M5) | T4.41 | OK |
| R8 (7-day SAR boundary precision) | R3.2 + T4.23 | OK |

All 9 blocking fixes verified. All 8 recommendations addressed.

---

## SCORES (v2)

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 8.5   |
| Testability      | 15%    | 8.5   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |

Calculation:
- 25*8.5 + 20*8.5 + 20*8.5 + 15*8.5 + 10*8.5 + 10*7.5
- = 212.5 + 170 + 170 + 127.5 + 85 + 75 = 840
- / 100 = 8.40

**Weighted total: 8.40 / 10 — GO.**

Margin above 7.5: +0.90. Security score now matches other
dimensions — F2/F3/F9 fixes closed the anti-tipping-off gap.

---

## MINOR ITEMS FOR IMPLEMENTATION (non-blocking)

### M1. Decimal default_factory

`CashTransaction.amount_usd` should use
`Field(..., gt=Decimal("0"))` with explicit Decimal bound.
Pydantic v2 handles Decimal comparisons natively.

### M2. `bisect.insort` stability

For equal `occurred_at` timestamps in `InMemoryWindowStore`,
insort should be stable (order of insertion). Document this in
the code comment.

### M3. AuditEntry `canonical_id` — let caller override for tests

Spec already calls this out (R7.5). Implement as
`canonical_id: UUID | None = None` parameter; default to
`uuid4()` if None. Simplifies golden-value tests.

### M4. Rego rule oracle-parity test

A Phase-4-ready extra test would feed the Python monitor and a
real OPA sidecar with the same `CashTransaction` and compare
outputs. Not required for Phase 3 (no OPA sidecar in CI yet).

### M5. Gap 3 <-> Gap 4 integration

Gap 3's `scan_rego_file` should validate Gap 4's `.rego` files
as part of the coverage sweep. Not required in either Gap's
test file, but worth documenting as a CI-pipeline item.

---

## VERDICT

**GO. 8.40 / 10.** Ready for build.
