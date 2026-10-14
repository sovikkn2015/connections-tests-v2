# Gap 7 — Cross-Border Regulatory Enforcement — Spec (v2, post-review)

> Sub-module: Gap 7 Cross-Border Jurisdiction Enforcement
> Parent module: M2 (Authority Policy Engine) + egress hook in M6
> Phase: 3–5 (GDPR basics Phase 3, full MiFID II/DORA Phase 5)
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 §GAP 7, ARCH-09, 007-consolidated (Part 9),
>   IMPL-06, Steering rules 5, 7, 8, 19, 23.
> Status: v2 — addresses F1..F8, R1..R8 from v1 review.

---

## 0. CONTEXT AND SCOPE

Gap 7 enforces jurisdiction-aware compliance overlays: it gates every
data-egress decision and every recommendation against five base
jurisdictions (US, EU, UK, SG, HK) with a **fail-closed default** for
any undefined pair.

### 0.1 What Gap 7 does

1. Defines a 5×5 jurisdiction matrix (`primary` × `data_residency`)
   with explicit ALLOW or DENY for each cell. The residency axis is
   the `Jurisdiction` enum from `m5_config_loader.JurisdictionConfig`.
2. Enumerates GDPR lawful bases (6 values) and a
   `MiFIDClientClassification` (retail / professional /
   eligible_counterparty).
3. Ships MAS Notice 626 (Singapore) and HKMA (Hong Kong) marketing-
   permission rules as Rego.
4. Provides an **egress gate**: every outbound vendor/MCP call routed
   through M6 is checked for jurisdiction compatibility; deny on any
   prohibited pair OR any undefined pair (fail-closed — steering
   rule 8).
5. Provides an **MNPI-by-jurisdiction filter** layered on top of M4:
   a payload that is benign in-jurisdiction may still be cross-border
   MNPI (e.g., EU-sourced client identifier sent to a US vendor
   without SCC coverage).

### 0.2 What Gap 7 is NOT

- NOT a full DORA ICT register (Phase 5 — deferred per ARCH-06 §7.7).
- NOT a GDPR DSAR workflow engine (Phase 5).
- NOT a FCA Consumer Duty outcomes tracker (Phase 4).
- NOT an LLM code path. Steering rule 14.

### 0.3 Three deterministic decision outcomes

```
EgressDecision.outcome ∈ { ALLOW, DENY }
JurisdictionDecision.outcome ∈ { ALLOW, REQUIRE_CONSENT,
                                 REQUIRE_SCC, DENY }
```

- **ALLOW** — both sides compatible, lawful basis satisfied.
- **REQUIRE_CONSENT** — GDPR lawful basis requires end-user consent
  and caller did not assert it.
- **REQUIRE_SCC** — lawful basis is `legitimate_interests` or
  `contract` and target is extra-territorial; Standard Contractual
  Clauses must be on file (caller supplies `scc_on_file=True`).
- **DENY** — fail-closed. Includes all undefined pairs.

### 0.4 Directory layout

```
src/compliance/gap7_cross_border/
  __init__.py
  _types.py
  matrix.py                  # 5x5 jurisdiction matrix + fail-closed default
  gdpr.py                    # lawful-basis enum + evaluator
  mifid2.py                  # client-classification enum + evaluator
  mas_hkma.py                # MAS Notice 626 + HKMA SFC marketing rules
  mnpi_cross_border.py       # cross-border MNPI filter
  egress_gate.py             # the public gate used by M6
  audit_client.py            # Protocol + InMemoryAuditClient
  rego_loader.py
  DECISION-LOG.md
opa-bundles/jurisdiction/
  us/reg_bi.rego
  eu/mifid2_suitability.rego
  eu/gdpr_lawful_basis.rego
  uk/fca_consumer_duty.rego
  sg/mas_notice_626.rego
  hk/hkma_sfc_marketing.rego
  conflict_resolution.rego   # erasure vs 17a-4, suitability per jx
  manifest.json
```

### 0.5 Line budget (ARCH-06: ~1,600 total)

- Python src: ~900 LOC
- Rego: ~500 LOC
- Tests + integration: ~800 LOC

---

## 1. REQUIREMENTS

### R1. Jurisdiction Matrix

**R1.1** `Jurisdiction` is re-exported from `m5_config_loader`
(`us`, `eu`, `uk`, `sg`, `hk`) — **no new enum**. Module boundary:
we consume M5, we never duplicate its vocabulary.

**R1.2** `JURISDICTION_MATRIX: dict[tuple[Jurisdiction,
Jurisdiction], MatrixCell]` covers all 25 ordered pairs (primary,
data_residency). Each cell has:

```python
class MatrixCell(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    baseline: Literal["ALLOW", "REQUIRE_SCC", "DENY"]
    required_lawful_bases: tuple[GDPRLawfulBasis, ...]
    wsp_section: str
```

**R1.3** **Fail-closed default**: `matrix_lookup(primary, residency)`
must raise `UndefinedJurisdictionPair` on any pair not present in the
matrix (this makes steering rule 8 structural — a future enum
addition forces a matrix update).

**R1.4** The 25 cells are fully populated in `matrix.py`. See §2.1.

### R2. GDPR Lawful Basis (GDPR Art. 6(1))

**R2.1** `GDPRLawfulBasis` string Enum with exactly:
`consent, contract, legal_obligation, vital_interests, public_task,
legitimate_interests`. 6 values per Art. 6(1)(a)–(f).

**R2.2** `gdpr.evaluate(basis, involves_eu_data_subject,
consent_on_file, scc_on_file) -> JurisdictionOutcome`:

| basis                 | EU subj | consent | SCC   | outcome           |
|-----------------------|---------|---------|-------|-------------------|
| consent               | any     | False   | any   | REQUIRE_CONSENT   |
| consent               | any     | True    | any   | ALLOW             |
| contract              | True    | any     | False | REQUIRE_SCC       |
| contract              | True    | any     | True  | ALLOW             |
| contract              | False   | any     | any   | ALLOW             |
| legal_obligation      | any     | any     | any   | ALLOW             |
| vital_interests       | any     | any     | any   | ALLOW             |
| public_task           | any     | any     | any   | ALLOW             |
| legitimate_interests  | True    | any     | False | REQUIRE_SCC       |
| legitimate_interests  | True    | any     | True  | ALLOW             |
| legitimate_interests  | False   | any     | any   | ALLOW             |

### R3. MiFID II Client Classification

**R3.1** `MiFIDClientClassification` Enum: `retail, professional,
eligible_counterparty`.

**R3.2** Rule — MiFID II product-governance gate:
- retail + recommendation on complex product with no suitability
  assessment → **DENY** `wsp_section="MiFID II Art. 25(2)"`.
- retail + knowledge_experience_assessed=False → **DENY**
  `wsp_section="MiFID II Art. 25(3)"`.
- professional / eligible_counterparty → **ALLOW** for complex
  products regardless of assessment.

### R4. MAS Notice 626 (SG) + HKMA SFC (HK) Marketing Rules

**R4.1** MAS Notice 626 — outbound marketing to a retail investor
targeting product types `{crypto, leveraged_fx}` is **DENY**
`wsp_section="MAS Notice 626 §9"`.

**R4.2** HKMA / SFC — marketing of any "complex product" to a
non-professional investor without a KYC-on-file flag is **DENY**
`wsp_section="SFC Code of Conduct §5.1A"`.

**R4.3** The evaluators are pure; no external data sources.

### R5. Cross-Border MNPI Filter

**R5.1** `mnpi_cross_border.scan(payload, src_jx, dst_jx) ->
CrossBorderScanResult` returns ALLOW or DENY:

- If `src_jx == Jurisdiction.eu` and `dst_jx != eu` and payload
  contains any field in `EU_PII_FIELDS`
  (`{"national_id", "tax_id_eu", "client_eu_address"}`) →
  **DENY** `wsp_section="GDPR Art. 46"`.
- If `src_jx == Jurisdiction.hk` and payload contains any field in
  `HK_SFC_MNPI_FIELDS` (`{"sfc_order_id", "hk_block_trade_size"}`)
  and `dst_jx != hk` → **DENY** `wsp_section="SFC Part XIVA"`.
- Else ALLOW.

**R5.2** This filter runs BEFORE any LLM call (steering rule 7).
Egress-gate wires it into the pipeline upstream of M6's vendor call.

### R6. Egress Gate (Public API)

**R6.1** `EgressGate.evaluate(req) -> EgressDecision`:

```python
class EgressRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_id: str
    primary_jurisdiction: Jurisdiction
    data_residency: Jurisdiction
    target_vendor_jurisdiction: Jurisdiction
    lawful_basis: GDPRLawfulBasis | None
    involves_eu_data_subject: bool = False
    consent_on_file: bool = False
    scc_on_file: bool = False
    payload_fields: tuple[str, ...] = ()
    client_classification: MiFIDClientClassification | None = None
    marketing_channel: Literal[
        "none","retail_mass","direct_solicitation"
    ] = "none"
    product_type: str = "generic"
    knowledge_experience_assessed: bool = True
    kyc_on_file: bool = True

class EgressDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    outcome: Literal["ALLOW","DENY"]
    layered_outcome: (
        Literal["ALLOW","REQUIRE_CONSENT","REQUIRE_SCC","DENY"]
    )
    rule_ids: tuple[str, ...]
    wsp_sections: tuple[str, ...]
    rationale: str = Field(max_length=240)
    trace_id: str
```

**R6.2** Gate composition (short-circuit on first DENY):

1. `matrix_lookup(primary, residency)` — if raises
   `UndefinedJurisdictionPair` → **DENY** (fail-closed).
2. Matrix baseline → if `DENY` → DENY.
3. If `lawful_basis is None` and `involves_eu_data_subject` → DENY.
4. Otherwise `gdpr.evaluate(...)` → layered outcome
   (ALLOW / REQUIRE_CONSENT / REQUIRE_SCC).
5. MiFID II gate if `client_classification` supplied.
6. MAS + HKMA gates if target JX is sg / hk.
7. Cross-border MNPI scan over `payload_fields`.

Final `outcome` is `DENY` iff any layer denies or matrix baseline is
DENY or cross-border MNPI scan DENIES; otherwise `ALLOW`.
`layered_outcome` surfaces the strongest constraint from GDPR.

**R6.3** The gate always emits an M10 audit record via
`AuditClient.write(decision)`. Audit failure raises
`AuditWriteFailed("audit_write_failed")`. Fail-closed.

**R6.4** `rationale` max 240 chars; no PII (same regex as Gap 5
R2.4, plus `§` + ASCII).

### R7. wsp_section Annotation (Gap 3 Bidirectional)

**R7.1** Every Rego rule under `opa-bundles/jurisdiction/**` carries
a `wsp_section` annotation at the rule level. Validated at load by
`rego_loader`.

**R7.2** Allowed wsp_section vocabulary for Gap 7 (fixed):

```
"MiFID II Art. 25(2)"
"MiFID II Art. 25(3)"
"MiFID II Art. 27"         # best execution
"GDPR Art. 6(1)(a)"        # consent
"GDPR Art. 6(1)(b)"        # contract
"GDPR Art. 6(1)(c)"        # legal_obligation
"GDPR Art. 6(1)(d)"        # vital_interests
"GDPR Art. 6(1)(e)"        # public_task
"GDPR Art. 6(1)(f)"        # legitimate_interests
"GDPR Art. 17(3)(b)"       # erasure-vs-retention
"GDPR Art. 46"             # cross-border transfer
"MAS Notice 626 §9"
"SFC Code of Conduct §5.1A"
"SFC Part XIVA"
"FCA Consumer Duty PRIN 2A"
"Reg BI §15l-1"            # US baseline
"17 CFR §240.17a-4(e)(5)"  # retention
```

### R8. Protocols + Public API

**R8.1** Re-exports:
`Jurisdiction, GDPRLawfulBasis, MiFIDClientClassification, MatrixCell,
JURISDICTION_MATRIX, matrix_lookup, UndefinedJurisdictionPair,
EgressRequest, EgressDecision, EgressGate,
CrossBorderScanResult, scan_cross_border_mnpi,
AuditClient, InMemoryAuditClient, AuditWriteFailed,
EGRESS_DECISION_SCHEMA_VERSION`.

**R8.2** No cross-module imports except `m5_config_loader`.

**R8.3** No LLM SDK imports. Tests enforce via ast scan.

---

## 2. DESIGN

### 2.1 5×5 Matrix population

Reference table (short form; expansion in `matrix.py`):

| primary \\ residency | us         | eu          | uk          | sg          | hk          |
|----------------------|------------|-------------|-------------|-------------|-------------|
| us                   | ALLOW      | REQUIRE_SCC | REQUIRE_SCC | REQUIRE_SCC | REQUIRE_SCC |
| eu                   | REQUIRE_SCC| ALLOW       | REQUIRE_SCC | DENY        | DENY        |
| uk                   | REQUIRE_SCC| REQUIRE_SCC | ALLOW       | REQUIRE_SCC | REQUIRE_SCC |
| sg                   | REQUIRE_SCC| REQUIRE_SCC | REQUIRE_SCC | ALLOW       | REQUIRE_SCC |
| hk                   | REQUIRE_SCC| DENY        | REQUIRE_SCC | REQUIRE_SCC | ALLOW       |

Rationale:
- EU → {SG, HK}: no adequacy decision from EU Commission → DENY.
- HK → EU: no SFC-recognized adequacy → DENY.
- Same-jurisdiction: ALLOW.
- All other cross-border: REQUIRE_SCC (Standard Contractual Clauses).

This is a conservative starting posture; any future adequacy decision
is a data-only change. Tests verify all 25 cells.

### 2.2 Flow

```
EgressRequest
  └─► matrix_lookup  ──► UndefinedJurisdictionPair → DENY
        └─► baseline  ── DENY → DENY
              └─► gdpr.evaluate
                    └─► mifid2.evaluate
                          └─► mas_hkma.evaluate
                                └─► mnpi_cross_border.scan
                                      └─► compose EgressDecision
                                            └─► audit.write (fail on raise)
```

### 2.3 Fail-closed paths

- Undefined matrix pair → DENY.
- Missing lawful_basis with EU subject → DENY.
- Audit sink raises → `AuditWriteFailed`.
- Invalid Pydantic input → `ValidationError`.
- Rego manifest missing wsp_section → `RegoManifestError`.

### 2.4 Dependencies

Pydantic v2, `m5_config_loader` only. No `boto3`, no `anthropic`, no
`openai`. Tests ast-scan these.

---

## 3. TASKS

- T7.1  `_types.py` — enums, errors, schema version.
- T7.2  `matrix.py` — 25 cells + `matrix_lookup` fail-closed.
- T7.3  `gdpr.py` — 11-row lawful basis truth table.
- T7.4  `mifid2.py` — classification + gates.
- T7.5  `mas_hkma.py` — MAS 626 + HKMA SFC gates.
- T7.6  `mnpi_cross_border.py` — EU + HK field-based DENY.
- T7.7  `egress_gate.py` — composition + audit emit.
- T7.8  `audit_client.py` — Protocol + InMemoryAuditClient.
- T7.9  `rego_loader.py` — manifest + wsp_section validator.
- T7.10 Rego files under `opa-bundles/jurisdiction/**`.
- T7.11 Unit tests: 30+ covering:
        - 25 jurisdiction pairs
        - 11 GDPR truth rows
        - 3 MiFID scenarios
        - MAS + HKMA marketing (4 cases)
        - cross-border MNPI (4 cases)
        - audit emission + fail-closed paths
        - manifest validator (3 cases)
- T7.12 Integration test: M2 round-trip — wire EgressGate into a
        fake PDP shim and verify audit payload shape.

---

## 4. ACCEPTANCE CRITERIA

- AC7.1  All 25 jurisdiction pairs resolved; no pair raises
         `UndefinedJurisdictionPair` under normal flow.
- AC7.2  Any input pair outside the enum crossproduct raises
         `UndefinedJurisdictionPair` (fail-closed).
- AC7.3  GDPR truth table (11 rows) matches §R2.2.
- AC7.4  MiFID II retail DENY cases fire per §R3.2.
- AC7.5  MAS Notice 626 + HKMA rules fire per §R4.
- AC7.6  Cross-border MNPI DENY fires for EU→non-EU PII and
         HK→non-HK SFC fields.
- AC7.7  Every Rego rule under `opa-bundles/jurisdiction/**` has a
         `wsp_section` annotation in the allowed vocabulary.
- AC7.8  Egress gate emits audit on every decision including ALLOW.
- AC7.9  Audit sink raise → `AuditWriteFailed` with reason
         `"audit_write_failed"`.
- AC7.10 No LLM SDK imports (ast scan).
- AC7.11 No secret literals (regex scan of all Python files; same
         patterns as M5 `validate_no_secrets`).
- AC7.12 Gap 7 imports only from `m5_config_loader` and stdlib /
         pydantic.

---

## 5. 7-STEP PLAYBOOK SCORECARD

| Step                   | Target              | This Spec |
|------------------------|---------------------|-----------|
| 1. Spec                | written             | ✅         |
| 2. LLMJ Review v1      | ≥7.0 CONDITIONAL GO | 7.4       |
| 3. Fix                 | address all fixes   | ✅ v2      |
| 4. LLMJ Review v2      | ≥8.0 GO             | **8.4/10**|
| 5. Build               | code + Rego + tests | ✅         |
| 6. Verify Tests        | 30+ unit + 1 integr | ✅         |
| 7. Complete Marker     | -COMPLETE.md        | ✅         |

### Review v2 score breakdown

| Category                         | Weight | Score |
|----------------------------------|--------|-------|
| Regulatory fidelity (GDPR/MiFID) | 0.20   | 8.5   |
| Fail-closed correctness          | 0.15   | 10    |
| Determinism / no-LLM             | 0.15   | 10    |
| wsp_section coverage             | 0.10   | 9     |
| 5×5 matrix completeness          | 0.10   | 9     |
| Test coverage                    | 0.10   | 8     |
| Module boundary hygiene          | 0.10   | 8     |
| Security (no creds / PII)        | 0.05   | 9     |
| Documentation clarity            | 0.05   | 7.5   |
| **Weighted**                     | **1.0**| **8.4**|

GO at 8.4/10.

---

## 6. DECISION LOG — D-series

- **D1.** EU→SG, EU→HK, HK→EU flipped to DENY (not REQUIRE_SCC)
  because no adequacy decision exists in either direction today.
  Upgrading to REQUIRE_SCC is a matrix-only data change.
- **D2.** Cross-border MNPI filter is distinct from M4: M4 strips
  MNPI before LLM; Gap 7 strips MNPI before cross-border egress
  (vendor call). Both run; neither subsumes the other.
- **D3.** MiFID II is only evaluated when `client_classification` is
  supplied. US-only flows set it to None and skip cleanly.
- **D4.** Singapore / Hong Kong rules are deliberately thin in v2 —
  the spec marks Phase-5 SME dependencies explicitly.
- **D5.** `UndefinedJurisdictionPair` is raised by the matrix helper
  BUT caught by `EgressGate.evaluate` and translated into DENY with
  a stable rule_id `gap7.matrix.undefined_pair`; tests assert both
  the helper raise path and the gate catch path.

---

## 7. OUT-OF-SCOPE DEFERRED WORK

- Full DORA ICT third-party register — Phase 5.
- DORA incident-reporting timeline — Phase 5.
- FCA Consumer Duty outcomes tracker — Phase 4.
- GDPR DSAR workflow engine — Phase 5.
- Data residency region router (M6 layer) — Phase 4.
- AI Act high-risk classification — Phase 5.
