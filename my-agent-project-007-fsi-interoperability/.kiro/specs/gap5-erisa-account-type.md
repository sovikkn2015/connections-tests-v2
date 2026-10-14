# Gap 5 — ERISA Account-Type Gating — Spec (v2, post-review)

> Sub-module: Gap 5 ERISA Account-Type Gating
> Parent module: M2 (Authority Policy Engine)
> Phase: 2–3 (BD onboarding)
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 §GAP 5, ARCH-09, 007-consolidated (Part 9),
>   IMPL-06, Steering rules 5, 8, 14, 19.
> Status: v2 — addresses F1..F6, R1..R6 from v1 review.

---

## 0. CONTEXT AND SCOPE

Gap 5 enforces retirement-account-aware compliance gating so that a
recommendation suitable for a taxable account cannot silently satisfy
an ERISA-governed account. It sits inside the M2 Authority Policy
Engine as a deterministic Python wrapper around OPA/Rego rules.

### 0.1 What Gap 5 does

1. Classifies every request by canonical `AccountType` taxonomy (16
   types — spec R1).
2. Runs two deterministic gates:
   - **Fiduciary gate** — if account is in retirement set AND firm
     `SuitabilityStandard == fiduciary`, the Reg BI code path is
     blocked; fiduciary best-interest documentation is forced.
   - **DOL PTE 2020-02 rollover gate** — any recommendation flagged
     `is_rollover=True` into a retirement account triggers an
     enhanced-documentation requirement.
3. Emits a decision record to M10 (via injected `AuditClient`
   Protocol) for every ALLOW, BLOCK, or REQUIRE_ENHANCED decision.

### 0.2 What Gap 5 is NOT

- NOT a tax calculator (ARCH-06 §5.4 — Phase 4 scope).
- NOT an RMD scheduler (ARCH-06 §5.3 `check_rmd_status` — Phase 3+).
- NOT a trust impartiality checker (Phase 4 SME-gated).
- NOT an LLM code path. Ever. Steering rule 14.

### 0.3 Three deterministic decision outcomes

```
AccountTypeDecision ∈ { ALLOW, BLOCK, REQUIRE_ENHANCED_DOC }
```

- **ALLOW** — standard path; no ERISA or PTE constraint triggered.
- **BLOCK** — Reg BI path attempted on a fiduciary-gated retirement
  account. Fail-closed.
- **REQUIRE_ENHANCED_DOC** — fiduciary-gated OR PTE 2020-02 rollover.
  Downstream (Gap 1 Reg BI doc generator, M12 Execution Specialist)
  must produce fiduciary best-interest documentation before HITL
  clears.

### 0.4 Directory layout

```
src/compliance/gap5_erisa_account_type/
  __init__.py
  _types.py               # AccountType enum + AccountTypeDecision + errors
  taxonomy.py             # retirement_set + classification helpers
  gates.py                # fiduciary_gate + pte_rollover_gate (pure)
  engine.py               # AccountTypeEngine orchestrator + audit emit
  audit_client.py         # Protocol + InMemoryAuditClient
  rego_loader.py          # Optional: load opa-bundles/account-type metadata
  DECISION-LOG.md
opa-bundles/account-type/
  erisa.rego              # ERISA §406 + §404 rules, wsp_section annotations
  ira.rego                # IRA-specific rules (PTE 2020-02, RMD shell)
  fiduciary_gate.rego     # Reg BI vs Fiduciary branching
  pte_2020_02.rego        # DOL PTE 2020-02 rollover rule
  manifest.json           # Bundle manifest + wsp_section index
```

### 0.5 Line budget (ARCH-06: ~950 total)

- Python src: ~650 LOC
- Rego: ~300 LOC
- Tests: ~600 LOC

---

## 1. REQUIREMENTS

### R1. Account Type Taxonomy

**R1.1** `AccountType` string Enum with exactly these 16 values
(matches ARCH-06 §5.2):

```
taxable_brokerage, traditional_ira, roth_ira, sep_ira, simple_ira,
k401, k403b, k457, erisa_pension, erisa_profit_sharing,
trust_revocable, trust_irrevocable, custodial_utma, custodial_ugma,
account_529, hsa
```

Enum names are `snake_case`. Non-identifier values (`401k`, `403b`,
`457`, `529`) are stored as `k401`, `k403b`, `k457`, `account_529`
to stay valid Python identifiers; the canonical string value is the
regulatory name (`401k`, `403b`, etc.).

**R1.2** Canonical `RETIREMENT_SET: frozenset[AccountType]` includes
exactly: `traditional_ira, roth_ira, sep_ira, simple_ira, k401,
k403b, k457, erisa_pension, erisa_profit_sharing`. 9 members. No
others. Trusts and custodials are NOT retirement for Gap 5 purposes
(they have their own regimes).

**R1.3** Canonical `ERISA_GOVERNED_SET: frozenset[AccountType]`
includes exactly: `k401, k403b, k457, erisa_pension,
erisa_profit_sharing`. IRAs are NOT ERISA-governed (they are
IRC-governed with fiduciary overlay).

**R1.4** Canonical `TAX_DEFERRED_SET` — documentation-only helper,
used by Gap 1 / M12. Not a gating input.

### R2. `AccountTypeDecision` Record

**R2.1** `AccountTypeDecision` is a frozen Pydantic v2 model
(`ConfigDict(frozen=True, extra="forbid")`) with fields:

```
outcome: Outcome                    # ALLOW | BLOCK | REQUIRE_ENHANCED_DOC
account_type: AccountType
rule_ids: tuple[str, ...]           # which gate(s) triggered
wsp_sections: tuple[str, ...]       # every matching rule's wsp_section
rationale: str                      # <=200 chars, no PII
suitability_standard: SuitabilityStandard  # snapshot from ComplianceConfig
is_rollover: bool                   # echo of input
trace_id: str                       # caller-supplied, UUID-like
```

**R2.2** `Outcome` string Enum: `ALLOW`, `BLOCK`, `REQUIRE_ENHANCED_DOC`.

**R2.3** `rule_ids` elements are OPA-style paths:
- `authority.account_type.fiduciary_gate.reg_bi_blocked_on_retirement`
- `authority.account_type.pte_2020_02.rollover_requires_enhanced_doc`

**R2.4** `rationale` MUST NOT contain client display_name, SSN, account
number, or any free-text user input. It may contain `account_type.value`
and a short rule-name string.

**R2.5** `wsp_sections` is non-empty iff `outcome != ALLOW`. Every rule
fired contributes exactly one `wsp_section` token (R6.1).

### R3. Fiduciary Gate (Rule 1)

**R3.1** Inputs (from `AccountTypeRequest`):
- `account_type: AccountType`
- `suitability_standard: SuitabilityStandard`
- `proposed_doc_path: Literal["reg_bi", "fiduciary"]`

**R3.2** Truth table:

| account_type ∈ RETIREMENT_SET | suitability_standard | proposed_doc_path | outcome                 |
|-------------------------------|----------------------|-------------------|-------------------------|
| False                         | any                  | any               | pass-through (not fired)|
| True                          | reg_bi               | reg_bi            | pass-through            |
| True                          | reg_bi               | fiduciary         | pass-through            |
| True                          | fiduciary            | reg_bi            | **BLOCK**               |
| True                          | fiduciary            | fiduciary         | pass-through            |

**R3.3** Rule id: `authority.account_type.fiduciary_gate.reg_bi_blocked_on_retirement`
**R3.4** wsp_section: `"ERISA Policy §404(a)(1)(B)"` (prudent-expert).

### R4. DOL PTE 2020-02 Rollover Gate (Rule 2)

**R4.1** Inputs:
- `account_type: AccountType`
- `is_rollover: bool`

**R4.2** Truth table:

| is_rollover | account_type ∈ RETIREMENT_SET | outcome                |
|-------------|-------------------------------|------------------------|
| False       | any                           | pass-through           |
| True        | False                         | pass-through           |
| True        | True                          | **REQUIRE_ENHANCED_DOC**|

**R4.3** Rule id: `authority.account_type.pte_2020_02.rollover_requires_enhanced_doc`
**R4.4** wsp_section: `"ERISA Policy §PTE 2020-02(b)"`.

### R5. Engine — Decision Composition

**R5.1** `AccountTypeEngine.evaluate(request) -> AccountTypeDecision`.

**R5.2** Rule precedence (first fired wins the worst outcome; outcomes
do NOT merge silently):
1. Fiduciary gate. If it fires → `BLOCK`. Short-circuit. PTE check
   also appended to `rule_ids` ONLY if it would independently fire
   (so the audit record captures full attribution).
2. Else, PTE 2020-02 gate. If it fires → `REQUIRE_ENHANCED_DOC`.
3. Else → `ALLOW` (rule_ids empty, wsp_sections empty).

**R5.3** A BLOCK decision NEVER degrades to ALLOW. Fail-closed —
steering rule 8.

**R5.4** Engine is stateless; all state is derived from the request
and an injected `AuditClient`.

### R6. wsp_section Annotation Requirements (Gap 3 Bidirectional)

**R6.1** Every Rego rule file under `opa-bundles/account-type/` MUST
carry a `wsp_section` custom annotation at the rule level. Build-time
validator in `rego_loader.py` rejects any bundle that omits it.

**R6.2** Allowed `wsp_section` vocabulary for Gap 5 (fixed set; Gap 3
cross-checks this list):

```
"ERISA Policy §404(a)(1)(B)"    # prudent-expert
"ERISA Policy §406"             # prohibited transactions
"ERISA Policy §PTE 2020-02(b)"  # rollover best-interest
"ERISA Policy §PTE 2020-02(e)"  # documentation
"ERISA Policy §IRC 4975"        # IRA prohibited transactions
```

Unknown tokens cause `rego_loader` to raise `RegoManifestError`.

### R7. Audit Emission to M10

**R7.1** Every `evaluate()` call emits ONE audit record via
`AuditClient.write(decision: AccountTypeDecision)`. Even ALLOW.

**R7.2** Audit failure raises `AuditWriteFailed("audit_write_failed")`.
No silent degradation (rule 4 of the module spec).

**R7.3** `AuditClient` is a `typing.Protocol`, `@runtime_checkable`.
The real M10 client is wired at service startup; Gap 5 source carries
only the Protocol + `InMemoryAuditClient` reference impl.

**R7.4** The audit payload is a dict with the serialized
`AccountTypeDecision` plus a top-level `"gap"` field equal to the
string `"gap5"` and a `"schema_version"` field equal to
`ACCOUNT_TYPE_DECISION_SCHEMA_VERSION` (= `"1.0.0"`).

### R8. Protocols + Public API

**R8.1** Public API re-exports:
`AccountType, Outcome, AccountTypeRequest, AccountTypeDecision,
AccountTypeEngine, AuditClient, InMemoryAuditClient, AuditWriteFailed,
RETIREMENT_SET, ERISA_GOVERNED_SET, ACCOUNT_TYPE_DECISION_SCHEMA_VERSION`.

**R8.2** No import of `m2_m4_policy_engine` or any sibling gap module
from Gap 5 source (steering rule 9).

**R8.3** Gap 5 may import from `m5_config_loader` for
`SuitabilityStandard` and `ComplianceConfig` — these are shared data
contracts, not logic.

---

## 2. DESIGN

### 2.1 Request Contract

```python
class AccountTypeRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    trace_id: str = Field(min_length=8, max_length=64,
                          pattern=r"^[A-Za-z0-9\-]+$")
    account_type: AccountType
    suitability_standard: SuitabilityStandard
    proposed_doc_path: Literal["reg_bi", "fiduciary"]
    is_rollover: bool = False
    requested_by: str = Field(min_length=1, max_length=64,
                              pattern=r"^[A-Za-z0-9_\-]+$")
```

`requested_by` is the AID `sub` (advisor/agent id); stays out of
rationale per R2.4.

### 2.2 Engine skeleton

```python
class AccountTypeEngine:
    def __init__(self, audit_client: AuditClient) -> None: ...

    def evaluate(
        self, request: AccountTypeRequest
    ) -> AccountTypeDecision:
        # 1. Fiduciary gate
        fid = _fiduciary_gate(request)
        # 2. PTE 2020-02 gate
        pte = _pte_2020_02_gate(request)
        # 3. Compose outcome (R5.2)
        decision = _compose(request, fid, pte)
        # 4. Emit audit; raise on sink failure
        self._audit.write(decision)
        return decision
```

### 2.3 Rego bundles

Python is the decision engine of record; the Rego files are the
canonical policy source that a future real-OPA integration will
evaluate. They ship identical truth tables. `rego_loader` checks that
every rule has a `wsp_section` annotation in the allowed vocabulary
(R6.2). Unit tests assert Python + Rego agree on the matrix.

### 2.4 Failure modes

| Case                                     | Behavior                                   |
|------------------------------------------|--------------------------------------------|
| Invalid `AccountType` at input           | Pydantic `ValidationError`                 |
| Invalid `suitability_standard`           | Pydantic `ValidationError`                 |
| Audit sink raises                        | `AuditWriteFailed("audit_write_failed")`   |
| Rego bundle missing wsp_section          | `RegoManifestError` at load                |
| Unknown wsp_section token                | `RegoManifestError` at load                |

---

## 3. TASKS

- T5.1  `_types.py` — AccountType, Outcome, errors, schema version.
- T5.2  `taxonomy.py` — RETIREMENT_SET, ERISA_GOVERNED_SET,
        TAX_DEFERRED_SET, helpers.
- T5.3  `gates.py` — `_fiduciary_gate`, `_pte_2020_02_gate` (pure).
- T5.4  `engine.py` — composition + audit emission.
- T5.5  `audit_client.py` — Protocol + InMemoryAuditClient.
- T5.6  `rego_loader.py` — manifest loader + wsp_section validator.
- T5.7  Rego: `erisa.rego`, `ira.rego`, `fiduciary_gate.rego`,
        `pte_2020_02.rego`, `manifest.json`.
- T5.8  Unit tests: 25+ covering the account-type matrix,
        fiduciary-vs-reg_bi branching, PTE 2020-02, audit emission,
        Rego manifest validation, precedence, schema version.
- T5.9  Integration test: M2 round-trip — wire
        `AccountTypeEngine` into a fake `PolicyDecisionPoint` shim
        exposing `evaluate()` and verify payload shape reaches the
        audit sink.

---

## 4. ACCEPTANCE CRITERIA

- AC5.1  Every Rego rule carries a `wsp_section` annotation.
- AC5.2  `rego_loader.load_manifest()` rejects any missing or unknown
         `wsp_section`.
- AC5.3  Fiduciary gate truth table (R3.2) passes all 5 rows.
- AC5.4  PTE 2020-02 gate truth table (R4.2) passes all 3 rows.
- AC5.5  Every 16 AccountType values × both suitability_standards ×
         both doc_paths × rollover ∈ {False,True} (=128 cells) yield
         a deterministic outcome; unit test asserts the 128-cell
         matrix.
- AC5.6  BLOCK outcome emits audit record with `outcome="BLOCK"`,
         non-empty `rule_ids`, non-empty `wsp_sections`.
- AC5.7  ALLOW outcome emits audit record with `outcome="ALLOW"`,
         empty `rule_ids`, empty `wsp_sections`.
- AC5.8  Audit write failure raises `AuditWriteFailed`;
         `str(exc) == "audit_write_failed"`.
- AC5.9  No LLM SDK import (ast scan: `anthropic`, `openai`,
         `bedrock`, `boto3`, `langchain`, `transformers`).
- AC5.10 `rationale` length ≤ 200 and matches
         `^[A-Za-z0-9_\- .§()§/]+$` (no free-form PII).
- AC5.11 Gap 5 imports only from `m5_config_loader` and stdlib.

---

## 5. 7-STEP PLAYBOOK SCORECARD

| Step                    | Target                 | This Spec |
|-------------------------|------------------------|-----------|
| 1. Spec                 | written                | ✅         |
| 2. LLMJ Review v1       | ≥7.0 CONDITIONAL GO    | 7.6       |
| 3. Fix                  | address all fixes      | ✅ v2      |
| 4. LLMJ Review v2       | ≥8.0 GO                | **8.3/10**|
| 5. Build                | code + Rego + tests    | ✅         |
| 6. Verify Tests         | 25+ unit, 1+ integr.,  | ✅         |
|                         | full suite green       |           |
| 7. Complete Marker      | .kiro/specs/*-COMPLETE | ✅         |

### Review v2 score breakdown

| Category                         | Weight | Score |
|----------------------------------|--------|-------|
| Regulatory fidelity (ERISA/PTE)  | 0.20   | 8.5   |
| Determinism / no-LLM             | 0.15   | 10    |
| Fail-closed correctness          | 0.15   | 9     |
| wsp_section coverage (Gap 3 tie) | 0.10   | 9     |
| Audit emission completeness      | 0.10   | 8     |
| Test coverage (matrix + audit)   | 0.10   | 8     |
| Module boundary hygiene          | 0.10   | 8     |
| Security (no creds / PII)        | 0.05   | 9     |
| Documentation clarity            | 0.05   | 7.5   |
| **Weighted**                     | **1.0**| **8.3**|

GO at 8.3/10.

---

## 6. DECISION LOG — D-series

- **D1.** Python is the execution engine of record; Rego is policy
  source-of-truth mirrored 1:1 (same truth tables). Dual-source is
  tolerable because Gap 5 ships 2 rules; unit tests assert parity.
- **D2.** Custodial and trust accounts are intentionally OUT of the
  Phase 2–3 retirement set. Their rules land in Phase 4 (SME-gated).
- **D3.** The engine emits audit on every outcome including ALLOW,
  because compliance officers need a full decision trail per SEC
  17a-4(e)(5).
- **D4.** `requested_by` never appears in `rationale` — AID identity
  stays in the audit envelope, not the user-visible reason.

---

## 7. OUT-OF-SCOPE DEFERRED WORK

- RMD monitoring (`check_rmd_status`) — Phase 3 calendar sub-system.
- Party-in-interest list integration — Phase 4 data source.
- Trust impartiality (income vs remainder) — Phase 4 SME.
- Tax impact calculator — Phase 4 (ARCH-06 §5.4).
- 529/HSA state-specific overlays — Phase 5.
