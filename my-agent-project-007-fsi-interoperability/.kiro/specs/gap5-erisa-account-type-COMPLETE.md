# Gap 5 — ERISA Account-Type Gating — COMPLETE

**Sub-module**: Gap 5 ERISA Account-Type Gating
**Parent module**: M2 (Authority Policy Engine)
**Phase**: 2-3 (BD onboarding)
**Playbook**: 7 steps complete

## Scorecard

| Step | Status | Result |
|------|--------|--------|
| 1. Spec | done | v2, §R1..R8, 7 sections |
| 2. LLMJ Review v1 | done | 7.6/10 CONDITIONAL GO |
| 3. Fix | done | v2 addresses F1..F6, R1..R6 |
| 4. LLMJ Review v2 | done | 8.3/10 GO |
| 5. Build | done | 659 Python LOC src + 286 Rego LOC |
| 6. Verify Tests | done | 41 unit + 3 integration = 44 tests |
| 7. Complete | done | This marker |

## Scope Delivered

16-type canonical AccountType taxonomy + two deterministic gates
composed into a single fail-closed engine:

- **Fiduciary gate** — ERISA §404(a)(1)(B) — blocks Reg BI doc path
  on retirement accounts when firm suitability_standard=fiduciary.
- **PTE 2020-02 gate** — ERISA PTE 2020-02(b) — forces enhanced
  documentation on rollover recommendations into retirement accounts.

5 Rego rule files under `opa-bundles/account-type/` + manifest.json,
each carrying a `wsp_section` annotation in the allowed vocabulary:

- ERISA Policy §404(a)(1)(B)
- ERISA Policy §406
- ERISA Policy §PTE 2020-02(b)
- ERISA Policy §PTE 2020-02(e)
- ERISA Policy §IRC 4975

Python engine + Rego parity: `rego_loader.load_manifest` is a
build-time validator (rejects missing / unknown wsp_section), so any
drift between Python truth tables and Rego annotations fails the unit
test `test_every_rego_rule_has_wsp_section`.

## Non-Negotiables Verified

- **No LLM SDK** — AST scan across `gap5_erisa_account_type/` confirms
  zero imports of anthropic, openai, bedrock, boto3, langchain,
  transformers, spacy.
- **Fail-closed** — audit-sink raise → `AuditWriteFailed`;
  `str(exc) == "audit_write_failed"`.
- **Deterministic** — 128-cell decision matrix (16 account types × 2
  suitability standards × 2 doc paths × 2 rollover flags) asserted
  deterministic in test `test_all_128_cells_deterministic`.
- **wsp_section everywhere** — every Rego rule carries one, validated
  by `rego_loader`.
- **Module boundary** — only `m5_config_loader` imported across the
  module boundary; no M2/M10 / cross-gap imports.
- **Audit on every decision** — ALLOW, BLOCK, REQUIRE_ENHANCED_DOC all
  emit to the injected M10 client.
- **Rationale sanitised** — charset regex rejects PII; max 200 chars.

## Test Results (10/10 stable)

- Unit: 41 tests across
  `tests/unit/test_gap5_erisa_account_type.py`
- Integration: 3 M2 policy-engine round-trip tests in
  `tests/integration/test_gap5_gap7_m2_round_trip.py`
- Full project suite: 1707 passed, 4 skipped, 5 xfailed, 1 xpassed
- 10 consecutive runs of `PYTHONPATH=src python3 -m pytest tests/
  -q --timeout=60` all exit 0

## Files Delivered

Source (Python 3.10+):
- `src/compliance/gap5_erisa_account_type/__init__.py`
- `src/compliance/gap5_erisa_account_type/_types.py`
- `src/compliance/gap5_erisa_account_type/taxonomy.py`
- `src/compliance/gap5_erisa_account_type/gates.py`
- `src/compliance/gap5_erisa_account_type/engine.py`
- `src/compliance/gap5_erisa_account_type/audit_client.py`
- `src/compliance/gap5_erisa_account_type/rego_loader.py`
- `src/compliance/gap5_erisa_account_type/DECISION-LOG.md`

OPA/Rego bundles:
- `opa-bundles/account-type/fiduciary_gate.rego`
- `opa-bundles/account-type/pte_2020_02.rego`
- `opa-bundles/account-type/erisa.rego`
- `opa-bundles/account-type/ira.rego`
- `opa-bundles/account-type/manifest.json`

Specs + tests:
- `.kiro/specs/gap5-erisa-account-type.md`
- `tests/unit/test_gap5_erisa_account_type.py`
- `tests/integration/test_gap5_gap7_m2_round_trip.py` (shared)

## Deployment Gating

Pre-prod requires 2 operational items (Phase 4 SME):
- Party-in-interest list data source (`data.party_in_interest_list`)
  for ERISA §406 rule to fire.
- Plan investment menu integration for 401(k)/403(b) menu checks
  (ARCH-06 §5.3 `check_plan_investment_menu` — deferred).

Phase 2-3 delivers the fiduciary gate + PTE 2020-02 rollover gate;
deferred work is catalogued in `.kiro/specs/gap5-erisa-account-type.md §7`.

## Phase 3 Next

Gap 4 (BSA/AML) and Gap 7 (Cross-Border) ship alongside Gap 5 in
Phase 3. Gap 5 dependencies (M5 Jurisdiction config) are Phase 0 /
Phase 1 complete.
