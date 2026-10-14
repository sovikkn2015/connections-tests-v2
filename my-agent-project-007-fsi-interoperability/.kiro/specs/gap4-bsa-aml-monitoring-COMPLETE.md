# Gap 4 — BSA/AML Ongoing Monitoring — COMPLETE

Parent modules: M2 (Authority Policy) + M10 (Audit Logger)
Phase: 3 (BD onboarding, post-Execution-Specialist per ARCH-06 §P2)
Agent: 007-compliance-agent
Review: `.kiro/specs/gap4-bsa-aml-monitoring-REVIEW-v2.md` — **8.40 / 10 GO**

---

## Summary

Gap 4 implements deterministic post-trade BSA/AML monitoring:

- **CTR threshold detection** — single cash txn >= $10,000 (31 CFR §1010.311).
- **CTR 24h aggregate** — same-client cash sums > $10,000 in 24h (strict `>`).
- **SAR structuring detection** — 3+ mid-band ($7,000..$9,999.99) cash
  txns in a 7-day rolling window (31 CFR §1023.320).
- **Anti-tipping-off compliance** — every alert `route_to="compliance_officer"`;
  `do_not_notify` always contains `advisor` + `client`
  (31 U.S.C. §5318(g)(2)).
- **Fail-closed M10 audit emission** — every alert becomes an
  `AuditEntry` with uniform `action="bsa_aml.alert_emitted"` and
  `target_type="cash_transaction"` so log observers cannot infer
  that a SAR is imminent.
- **BsaAmlConfig.enabled=False short-circuits** — no store writes,
  no alerts, no audit emission, no Redis connections. Verified by
  T4.24, T4.25, T4.41.
- **Rego oracle parity** — `opa-bundles/bsa-aml/ctr.rego` +
  `sar_structuring.rego` with `wsp_section` annotations ready for
  Phase-4 OPA runtime migration.

All classification is deterministic Python + OPA/Rego. Zero LLM calls.
Decimal arithmetic avoids float drift at the $10K boundary.

---

## LOC

| Artifact | Path | Lines |
|----------|------|-------|
| Spec (GO, v2) | `.kiro/specs/gap4-bsa-aml-monitoring.md` | 860 |
| Spec review v1 | `.kiro/specs/gap4-bsa-aml-monitoring-REVIEW.md` | 131 |
| Spec review v2 (GO) | `.kiro/specs/gap4-bsa-aml-monitoring-REVIEW-v2.md` | 93 |
| `__init__.py` | `src/compliance/gap4_bsa_aml_monitoring/__init__.py` | 95 |
| `models.py` | `src/compliance/gap4_bsa_aml_monitoring/models.py` | 330 |
| `window_store.py` | `src/compliance/gap4_bsa_aml_monitoring/window_store.py` | 171 |
| `monitors.py` | `src/compliance/gap4_bsa_aml_monitoring/monitors.py` | 324 |
| `rules.py` | `src/compliance/gap4_bsa_aml_monitoring/rules.py` | 180 |
| `audit_emitter.py` | `src/compliance/gap4_bsa_aml_monitoring/audit_emitter.py` | 172 |
| `config.py` | `src/compliance/gap4_bsa_aml_monitoring/config.py` | 126 |
| **Python source total** | | **1,398** |
| `ctr.rego` | `opa-bundles/bsa-aml/ctr.rego` | 92 |
| `sar_structuring.rego` | `opa-bundles/bsa-aml/sar_structuring.rego` | 80 |
| `bundle.yaml` | `opa-bundles/bsa-aml/bundle.yaml` | 29 |
| `README.md` | `opa-bundles/bsa-aml/README.md` | 38 |
| **Rego / manifest total** | | **239** |
| Unit tests | `tests/unit/test_gap4_bsa_aml_monitoring.py` | 1,117 |
| Integration tests | `tests/integration/test_gap4_m2_policy_engine_roundtrip.py` | 229 |
| **Test total** | | **1,346** |

ARCH-06 budget target: ~1,100 lines (Python 600 + Rego 400 + fixtures 100).
Actual source: 1,398 Python + 239 Rego/YAML = 1,637. The overage is
driven by:
- Decimal arithmetic throughout (spec F1 fix) — wider models.py than planned.
- Anti-tipping-off invariant validators on BsaAmlAlert.
- `peek()` non-mutating path added to prevent double-counting in M2
  pre-trade gating.

---

## Test counts

| Suite | File | Tests |
|-------|------|-------|
| Unit | `tests/unit/test_gap4_bsa_aml_monitoring.py` | 70 |
| Integration | `tests/integration/test_gap4_m2_policy_engine_roundtrip.py` | 4 |
| **Gap 4 total** | | **74** |

Full project suite after Gap 3 + Gap 4: **1,707 passed, 0 failed**.

Command:
```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
# 1707 passed, 4 skipped, 5 xfailed, 1 xpassed, 101 warnings in 10.09s
```

---

## Acceptance Criteria checklist (per spec §4 traceability)

- [x] **R1.1** `CashTransactionCategory` 4-value enum — T4.1.
- [x] **R1.2** `CashTransaction` frozen Pydantic; naive datetime
      rejected; negative amount rejected — T4.2.
- [x] **R1.3** `Decimal` thresholds (`CTR_THRESHOLD_USD = Decimal("10000.00")`,
      `SAR_STRUCTURING_LOWER = Decimal("7000.00")`) — T4.16..T4.19.
- [x] **R1.4** `CashTransaction.from_m3` adapter: wire_in, wire_out,
      cash_deposit contribution, cash_withdrawal distribution,
      rejects non-cash types — T4.3, T4.4.
- [x] **R2.1** `AlertSeverity`, `AlertType` enums — T4.1.
- [x] **R2.3** `BsaAmlAlert` frozen; invariants enforced — T4.5.
- [x] **R2.4** Frozen `ALERT_REASONS` vocabulary — T4.7.
- [x] **R2.5** `matched_transactions` uniqueness + `matched_amount_usd > 0`
      invariants — T4.8.
- [x] **R3.1** `CtrMonitor.evaluate` single-txn (>= threshold) +
      24h aggregate (> threshold, strict) — T4.16, T4.17, T4.18, T4.19.
- [x] **R3.2** `SarStructuringMonitor.evaluate` 3+ mid-band txns in
      7-day rolling window — T4.20, T4.21, T4.22, T4.23.
- [x] **R3.3** Monitor order (CTR then SAR) deterministic — T4.20
      (CTR + SAR both fire independently when applicable).
- [x] **R4.1** `WindowStore` Protocol — T4.9.
- [x] **R4.2** `InMemoryWindowStore.record` bisect-sorted; `within`
      respects category filter; `purge_before` returns count — T4.10,
      T4.12, T4.13.
- [x] **R4.3** `threading.Lock()` thread safety — T4.14 (100 writes
      across 10 threads, zero data races).
- [x] **R4.4** `RedisWindowStore` stub raises `NotImplementedError` —
      T4.15.
- [x] **R4.5** Window boundary semantics (start-exclusive, end-inclusive)
      — T4.11.
- [x] **R5.1** `CtrPolicyRule` and `SarStructuringPolicyRule` satisfy
      M2 `PolicyRule` Protocol — T4.26.
- [x] **R5.2** `CtrPolicyRule.evaluate` happy path + missing context
      fail-closed DENY — T4.27, T4.28.
- [x] **R5.3** `SarStructuringPolicyRule.evaluate` happy path —
      T4.30.
- [x] **R5.4** Both adapters satisfy `isinstance(_, PolicyRule)` —
      T4.26.
- [x] **R6.1** `config.enabled=False` → no alerts, no store write,
      no audit emission — T4.24, T4.29, T4.30 (disabled variants).
- [x] **R6.2** `config=None` → same invariants — T4.25.
- [x] **R6.3** Config immutable per engine instance — T4.24 verifies.
- [x] **R7.1-R7.5** `AuditEmitter` populates every required
      `AuditEntry` field; anti-tipping-off invariants; determinism —
      T4.31, T4.32, T4.40.
- [x] **R7.4** `AlertEmitFailed("audit_write_failed")` on M10 failure
      (fail-closed, never silent drop) — T4.33.
- [x] **R8.1** `ctr.rego` has `# METADATA` + `wsp_section: "WSP-BSA-8.2"` —
      T4.34.
- [x] **R8.2** `sar_structuring.rego` has `wsp_section: "WSP-BSA-8.1"` —
      T4.34.
- [x] **R8.3** `bundle.yaml` manifest enumerates both rules + Python
      oracle refs — T4.34.
- [x] **R8.4** Gap 3 `scan_rego_file` verifies annotations — T4.34.
- [x] **R9.1** PII regex on `reason_detail` — T4.6 (SSN, email,
      12-digit acct, IBAN all rejected).
- [x] **R9.2** No credentials (grep clean).
- [x] **R9.3** `route_to: Literal["compliance_officer"]` — T4.5.
- [x] **R9.4** `reason_detail` max 500, PII-filtered — T4.6.
- [x] **R9.5** Thread-safety lock presence — T4.14_has_lock.

## Verification gates

- [x] **Every OPA rule has wsp_section annotation** — shell grep:
      `grep -q "wsp_section:"` on both `.rego` files returns 0.
      T4.34 parses via Gap 3 `scan_rego_file` — both files carry
      the correct WSP anchor.
- [x] **No LLM dependencies** — `grep -rEn
      "openai|anthropic|langchain|bedrock|claude"` on Gap 4 sources
      → 0 matches.
- [x] **M5 BsaAmlConfig.enabled=False fully disables Gap 4** —
      T4.24 (engine with emitter, 100 txns of $50K → 0 alerts,
      store.size()==0, 3-tier audit entries==0);
      T4.25 (config=None same guarantee);
      T4.41 (real M5 BsaAmlConfig with 50 txns of $50K,
      all three audit backends empty).
- [x] **No credentials** — grep clean across `src/compliance/
      gap4_bsa_aml_monitoring/`, `opa-bundles/bsa-aml/`, and the
      specs.
- [x] **M10 audit emission from every Gap 4 alert path** —
      T4.31 populates entry; T4.32 uniform action string;
      T4.33 fail-closed on write error; T4.40 end-to-end to 3
      real in-memory backends with integrity hash verification.

## Files delivered

```
.kiro/specs/
  gap4-bsa-aml-monitoring.md
  gap4-bsa-aml-monitoring-REVIEW.md
  gap4-bsa-aml-monitoring-REVIEW-v2.md
  gap4-bsa-aml-monitoring-COMPLETE.md        (this file)

src/compliance/gap4_bsa_aml_monitoring/
  __init__.py
  models.py
  window_store.py
  monitors.py
  rules.py
  audit_emitter.py
  config.py

opa-bundles/bsa-aml/
  ctr.rego
  sar_structuring.rego
  bundle.yaml
  README.md

tests/unit/test_gap4_bsa_aml_monitoring.py
tests/integration/test_gap4_m2_policy_engine_roundtrip.py
```

---

## V2 score recap

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 8.5   |
| Testability      | 15%    | 8.5   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |

**Weighted total: 8.40 / 10 — GO.**

---

**Status: COMPLETE. Ready for Phase 4 (OPA-as-runtime, RedisWindowStore
wiring, real OFAC list integration).**
