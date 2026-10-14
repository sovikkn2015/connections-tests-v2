# Gap 5 — ERISA Account-Type — Decision Log

## D1. Python is the execution engine; Rego mirrors the truth tables

ARCH-06 §5.3 ships production rules in Rego. Gap 5 Phase 2–3 executes
the same truth tables in pure Python for three reasons:

1. **Deterministic** — rules 5 and 14 require no LLM. Python is
   deterministic. OPA is also deterministic, but the binary is not
   available in every deployment topology (CI, unit-test, on-prem
   Tier 1). Python runs everywhere.
2. **Testable** — the Python engine can be unit-tested against the
   128-cell decision matrix without a running OPA sidecar.
3. **Parity-guarded** — unit tests load the manifest and walk the
   rules, ensuring every Rego file carries the wsp_section the Python
   engine emits. Rego drift is a test failure.

## D2. `rationale` is machine-facing, not user-facing

R2.4 constrains `rationale` to the charset
`[A-Za-z0-9 _\-\.\(\)/§]`. This keeps:
- no free-form PII,
- no advisor name,
- no client display_name,
- no SSN / account / phone.

User-visible narrative lives in Gap 1 (Reg BI doc generator). Gap 5
sits upstream of Gap 1 and only tells Gap 1 "use the fiduciary
template" or "use the enhanced-PTE template".

## D3. ALLOW decisions are audited

Every `evaluate()` call emits. Compliance officers and FINRA examiners
need the complete decision trail; SEC 17a-4(e)(5) retention applies
to decisions, not just denials.

## D4. Outcome does not merge silently

The engine never returns `REQUIRE_ENHANCED_DOC` plus `BLOCK` as a
compound outcome. `BLOCK` dominates; PTE attribution is still added
to `rule_ids` so the audit trail shows *why the block still had a
rollover context*, but there is exactly one `outcome` field.

## D5. Taxonomy drift caught at import time

`taxonomy.py` has import-time `assert` statements on RETIREMENT_SET
cardinality and ERISA_GOVERNED_SET subset-ness. A typo that widens
or narrows these sets fails pytest collection immediately.
