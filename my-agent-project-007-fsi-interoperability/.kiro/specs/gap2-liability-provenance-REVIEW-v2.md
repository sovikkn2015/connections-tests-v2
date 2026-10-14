# Gap 2 — Liability Provenance — LLMJ Review v2

> Re-review of `.kiro/specs/gap2-liability-provenance.md` (v2).
> Target: 7.5+/10 weighted for GO.

---

## FIX VERIFICATION (v1 — v2)

| v1 item | v2 addresses | Verified |
|---------|--------------|----------|
| F1 (R3.7 precedence ladder) | R3.7 4-rule ladder, first-match-wins | OK |
| F2 (PII enforcement mechanical) | R2.4 regex set, ValueError, T2.10 parametrized | OK |
| F3 (schema version) | R3.1 `report_schema_version="1.0.0"`, T2.22 | OK |
| F4 (golden hex) | R3.5 fixture + GOLDEN_HEX_DIGEST + T2.17 | OK |
| F5 (verify=False + no error) | R3.6 + R3.7 rule 1, T2.18 | OK |
| F6 (table coupling) | R1.8 + T2.7 | OK |
| F7 (reason_codes Phase 2) | §0.1 + R2.2 `extra="forbid"` | OK |
| F8 (canonical JSON contract) | R3.4 explicit `_json_default` | OK |
| R1 (wiring diagram) | §2.3 ASCII | OK |
| R2 (is_failing invariant) | R3.1 + T2.23 | OK |
| R3 (Gap 1 integration) | §0.1 | OK |
| R4 (line budget) | §0.5 | OK |
| R5 (model_dump mode) | R3.4 `mode="json"` | OK |
| R6 (empty-chain attribute) | T2.11 four cases | OK |
| R7 (best_effort clean) | R3.6 explicit, T2.21 | OK |

All 8 blocking fixes verified. All 7 recommendations addressed.

---

## SCORES (v2)

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 8.0   |
| Testability      | 15%    | 8.5   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |

Calculation:
- 25*8.5 + 20*8.5 + 20*8.0 + 15*8.5 + 10*8.5 + 10*7.5
- = 212.5 + 170 + 160 + 127.5 + 85 + 75 = 830
- / 100 = 8.30

**Weighted total: 8.30 / 10 — GO.**

Margin above 7.5 threshold: +0.80.

---

## MINOR ITEMS FOR IMPLEMENTATION (non-blocking)

### M1. GOLDEN_HEX_DIGEST bootstrap flow

T2.17 pins the digest after first run:
1. First pass: test computes digest, initially asserted against a
   placeholder that will fail.
2. Agent records the printed value in `GOLDEN_HEX_DIGEST = "..."`
   at top of test file.
3. Second pass: test asserts pinned value.

Comment this flow in the test file. Future canonical-JSON changes
break T2.17 — intentional drift detection.

### M2. `_json_default` parity with M10's `_canonical_json`

Both must produce identical output for overlapping types (datetime,
Enum, UUID). Add cross-reference comment pointing to M10. Phase-
boundary integration tests catch drift.

### M3. `report_schema_version` enforcement

Recommended: `Literal["1.0.0"]` type annotation rather than manual
`field_validator`. Pydantic rejects other values automatically.

### M4. Forbidden-imports test T2.25

Mirror M10's test approach (see
`tests/unit/test_m10_audit_logger.py`). Consistency across tests.

### M5. Test file growth

~400 lines is within budget. If tests grow >500, consider splitting
into `test_warranty.py` + `test_attribution.py`. Not required for
Phase 1.

---

## VERDICT

**GO. 8.30 / 10.**

All blocking issues resolved. Minor items are implementation guidance,
not blockers. Spec is ready for build.
