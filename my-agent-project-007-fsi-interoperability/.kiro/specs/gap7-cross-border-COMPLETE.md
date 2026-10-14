# Gap 7 — Cross-Border Regulatory Enforcement — COMPLETE

**Sub-module**: Gap 7 Cross-Border Jurisdiction Enforcement
**Parent module**: M2 (Authority Policy Engine) + egress hook in M6
**Phase**: 3-5 (GDPR basics Phase 3, full MiFID II/DORA Phase 5)
**Playbook**: 7 steps complete

## Scorecard

| Step | Status | Result |
|------|--------|--------|
| 1. Spec | done | v2, §R1..R8, 7 sections |
| 2. LLMJ Review v1 | done | 7.4/10 CONDITIONAL GO |
| 3. Fix | done | v2 addresses F1..F8, R1..R8 |
| 4. LLMJ Review v2 | done | 8.4/10 GO |
| 5. Build | done | ~960 Python LOC src + ~430 Rego LOC |
| 6. Verify Tests | done | 83 unit + 3 integration = 86 tests |
| 7. Complete | done | This marker |

## Scope Delivered

### 5×5 Jurisdiction matrix (all 25 cells explicit)

```
primary \ residency   us      eu      uk      sg      hk
us                    ALLOW   SCC     SCC     SCC     SCC
eu                    SCC     ALLOW   SCC     DENY    DENY
uk                    SCC     SCC     ALLOW   SCC     SCC
sg                    SCC     SCC     SCC     ALLOW   SCC
hk                    SCC     DENY    SCC     SCC     ALLOW
```

EU → {SG, HK} and HK → EU are DENY because no mutual adequacy
decision exists. Import-time assertion locks cardinality to 25 and
rejects any drift.

### Six regulatory evaluators

1. **Jurisdiction matrix** (fail-closed on undefined pairs).
2. **GDPR Art. 6(1) lawful basis** — 11-row truth table across all 6
   bases (consent, contract, legal_obligation, vital_interests,
   public_task, legitimate_interests).
3. **MiFID II Art. 25(2)/(3)** — retail / professional /
   eligible_counterparty classification + product-governance gate.
4. **MAS Notice 626 §9** (Singapore) — retail marketing of
   restricted products (crypto, leveraged FX) is DENY.
5. **HKMA / SFC §5.1A** (Hong Kong) — complex products to
   non-professionals without KYC is DENY.
6. **Cross-border MNPI filter** — EU PII fields must not cross EU
   border without SCC; HK SFC MNPI fields must not cross HK border.
   Runs BEFORE any LLM/vendor call.

### Egress gate (single public composer)

`EgressGate.evaluate(req: EgressRequest) -> EgressDecision` applies
all six gates in order, short-circuiting on first DENY, emitting M10
audit on every decision including ALLOW.

### OPA/Rego bundles under `opa-bundles/jurisdiction/`

All 13 rules carry `wsp_section` annotations in the allowed
vocabulary (Reg BI §15l-1, GDPR Art. 6(1)(a..f), GDPR Art. 17(3)(b),
GDPR Art. 46, MiFID II Art. 25(2)/(3)/27, MAS Notice 626 §9, SFC
§5.1A, SFC Part XIVA, FCA Consumer Duty PRIN 2A, 17 CFR §240.17a-4(e)(5)).

## Non-Negotiables Verified

- **No LLM SDK** — AST scan confirms zero imports of anthropic,
  openai, bedrock, boto3, langchain, transformers, spacy.
- **Fail-closed** —
  - Undefined matrix pair → DENY rule_id `gap7.matrix.undefined_pair`.
  - EU subject without lawful_basis → DENY.
  - Audit sink raise → `AuditWriteFailed("audit_write_failed")`.
- **All 25 jurisdiction pairs populated** (import-time cardinality
  assert + parametrised unit test).
- **11 GDPR truth-table rows** all covered by unit tests.
- **wsp_section everywhere** — every Rego rule has one, validated by
  `rego_loader.load_manifest`.
- **Module boundary** — only `m5_config_loader` imported across the
  module boundary; no M2/M6/M10 / cross-gap imports.
- **No credential literals** — regex scan of all source files.
- **Audit on every decision** — ALLOW and DENY both emit.
- **Rationale sanitised** — charset regex rejects PII; max 240 chars.
- **MNPI cross-border filter runs BEFORE LLM/vendor egress**
  (steering rule 7).

## Test Results (10/10 stable)

- Unit: 83 tests in `tests/unit/test_gap7_cross_border.py` including
  parametrised matrix (25 pairs) + GDPR 11 rows + MiFID II + MAS +
  HKMA + cross-border MNPI.
- Integration: 3 M2 policy-engine round-trip tests in
  `tests/integration/test_gap5_gap7_m2_round_trip.py`.
- Full project suite: 1707 passed, 4 skipped, 5 xfailed, 1 xpassed.
- 10 consecutive runs of
  `PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60` exit 0.

## Files Delivered

Source (Python 3.10+):
- `src/compliance/gap7_cross_border/__init__.py`
- `src/compliance/gap7_cross_border/_types.py`
- `src/compliance/gap7_cross_border/matrix.py`
- `src/compliance/gap7_cross_border/gdpr.py`
- `src/compliance/gap7_cross_border/mifid2.py`
- `src/compliance/gap7_cross_border/mas_hkma.py`
- `src/compliance/gap7_cross_border/mnpi_cross_border.py`
- `src/compliance/gap7_cross_border/egress_gate.py`
- `src/compliance/gap7_cross_border/audit_client.py`
- `src/compliance/gap7_cross_border/rego_loader.py`
- `src/compliance/gap7_cross_border/DECISION-LOG.md`

OPA/Rego bundles:
- `opa-bundles/jurisdiction/us/reg_bi.rego`
- `opa-bundles/jurisdiction/eu/gdpr_lawful_basis.rego`
- `opa-bundles/jurisdiction/eu/mifid2_suitability.rego`
- `opa-bundles/jurisdiction/uk/fca_consumer_duty.rego`
- `opa-bundles/jurisdiction/sg/mas_notice_626.rego`
- `opa-bundles/jurisdiction/hk/hkma_sfc_marketing.rego`
- `opa-bundles/jurisdiction/conflict_resolution.rego`
- `opa-bundles/jurisdiction/manifest.json`

Specs + tests:
- `.kiro/specs/gap7-cross-border.md`
- `tests/unit/test_gap7_cross_border.py`
- `tests/integration/test_gap5_gap7_m2_round_trip.py` (shared)

## Deployment Gating

Phase 3 ships GDPR lawful-basis + MiFID II retail gate + MAS/HKMA
marketing rules + cross-border MNPI + 5x5 matrix.

Phase 4-5 deferred (spec §7):
- Full DORA ICT third-party register + incident-reporting timeline.
- FCA Consumer Duty outcomes tracker.
- GDPR DSAR workflow engine.
- Data residency region router (M6 layer).
- AI Act high-risk classification.

These are documented out-of-scope items; the current matrix
baseline is conservative enough to remain correct while those
tracks mature.

## Phase 3 Next

Gap 4 BSA/AML is the remaining Phase 3 compliance gap. After that,
Phase 5 onboarding of on-prem topology + Tier 1/5 support.
