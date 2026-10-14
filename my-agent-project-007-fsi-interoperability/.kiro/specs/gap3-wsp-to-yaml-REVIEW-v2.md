# Gap 3 — WSP-to-YAML Mapping — LLMJ Review v2

> Re-review of `.kiro/specs/gap3-wsp-to-yaml.md` (v2).
> Target: 7.5+/10 weighted for GO.

---

## FIX VERIFICATION (v1 → v2)

| v1 item | v2 addresses | Verified |
|---------|--------------|----------|
| F1 (regex coupling by pattern string) | R1.2 + T3.3  | OK |
| F2 (PII + role-mailbox note)          | R5.1 (prose note under the field) | OK |
| F3 (schema version enforcement)       | R1.1 `Literal["1.0.0"]` + T3.29 | OK |
| F4 (golden manifest digest)           | R3.4 + T3.12 + GOLDEN_MANIFEST_DIGEST constant | OK |
| F5 (empty-registry CI semantics)      | R4.4 + T3.20 | OK |
| F6 (CLI exit-code frozen vocab)       | R6.3 + T3.23..T3.26 | OK |
| F7 (filesystem Protocol)              | R5.3 + T3.8, T3.9, T3.23 | OK |
| F8 (determinism contract)             | R7.2 + T3.12 + T3.30 | OK |
| R1 (wiring diagram)                   | §2.5 ASCII | OK |
| R2 (line budget breakdown)            | §0.5 | OK |
| R3 (AST boundary scan)                | §2.7 + T3.27 | OK |
| R4 (Phase 4 forward-compat)           | §0.1 | OK |
| R5 (coverage percent rounding)        | R4.3 `round(x, 3)` banker's | OK |
| R6 (rego scanner regex)               | §2.4 regex block | OK |
| R7 (many-to-many mapping)             | §2.3 + R2.3 + T3.11 | OK |

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

Margin above 7.5: +0.80.

---

## MINOR ITEMS FOR IMPLEMENTATION (non-blocking)

### M1. Bootstrap `GOLDEN_MANIFEST_DIGEST`

Follow Gap 2's pattern: first pass computes the digest and the
implementer pins the value. Future changes to YAML format or
field ordering break T3.12 deliberately.

### M2. `scan_rego_directory` path stability

`Path.iterdir()` is platform-ordered on some filesystems. Wrap
with `sorted(paths)` before returning.

### M3. `CoverageReport.exit_code` — keep as int

Python CLIs want an int, not an enum. int is fine; no upgrade.

### M4. CLI `--debug` flag

Prints exception class name only (not message). Keeps the
frozen-vocabulary invariant (R6.3) intact while giving developers
signal.

### M5. Test split

If `test_gap3_wsp_to_yaml.py` grows > 800 lines, split into
`test_gap3_models.py` + `test_gap3_registry.py`. Not required
for Phase 3.

---

## VERDICT

**GO. 8.30 / 10.** Ready for build.
