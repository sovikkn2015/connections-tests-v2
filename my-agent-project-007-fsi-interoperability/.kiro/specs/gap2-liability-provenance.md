# Gap 2 — Liability Provenance — Spec (v2, post-review)

> Sub-module: Gap 2 Liability Provenance
> Parent modules: M6 (MCP Gateway) + M10 (Audit Logger)
> Phase: 1
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 (Gap 2), ARCH-09 (compliance sub-modules),
>   007-consolidated-design-and-plan.md (Part 9, Gap 2), IMPL-06.
> Related: M10 `ProvenanceChainBuilder` (already built)
> Status: v2 — addresses F1..F8, R1..R7 from v1 review.

---

## 0. CONTEXT AND SCOPE

M10's `ProvenanceChainBuilder` already builds the per-stage SHA-256
linked chain. Gap 2 adds the three pieces that sit on top of that chain
and turn it into a **liability artifact** usable in regulatory dispute
resolution:

1. **WarrantyBoundary** — deterministic module-to-warranty mapping.
2. **ErrorAttribution** — attribute pipeline failures to a stage +
   module + 6-category taxonomy.
3. **LiabilityReport** — full chain + warranty per stage + attribution
   + summary + schema version + content hash.

Gap 2 lives in `src/compliance/gap2_liability_provenance/`. Phase 1 is
Python-only. NO LLM. Pure deterministic analyzer.

### 0.1 Non-goals

- Does NOT build the hash chain (M10 owns it).
- Does NOT write to WORM (M10).
- Does NOT decide allow/deny (M2/M4).
- Does NOT produce E&O insurance PDF (Phase 2; Gap 2 produces JSON).
- Does NOT re-verify chain (caller passes `chain_verified` bool from
  `builder.verify()`).
- Does NOT mutate inputs. All pure functions.

**Phase 2 forward-compat:**
- `ErrorAttribution.reason_codes: tuple[str, ...]` — structured codes
  for insurance underwriters. Phase 1 has `reason: str` only. Model
  uses `extra="forbid"` so Phase 2 upgrade is explicit.
- Gap 1 (Reg BI Doc Generator) will consume `LiabilityReport` via
  `to_canonical_json()`.

### 0.2 Directory layout

```
src/compliance/
  __init__.py                           # re-exports gap2 + gap6
  gap2_liability_provenance/
    __init__.py
    warranty.py
    attribution.py
```

### 0.3 Allowed imports

- stdlib: `__future__`, `dataclasses`, `enum`, `hashlib`, `json`,
  `re`, `typing`, `datetime`, `types`
- `pydantic`
- `m3_schema_registry` (for `ProvenanceStage`)

FORBIDDEN: any other `m*_` module, `openai`, `anthropic`, `langchain`,
`boto3`, `langfuse`, `requests`, `httpx`, any LLM SDK.

### 0.4 Threading

Pure functions + frozen models → thread-safe.

### 0.5 Line budget

ARCH-06 target: ~700 for Gap 2.
- `warranty.py`: ~180
- `attribution.py`: ~320
- `gap2 __init__.py`: ~40
- `src/compliance/__init__.py`: ~20 (shared with Gap 6)
- Tests: ~400

Python source ≈ 540. Tests ≈ 400. On target (shared init brings
combined Gap 2 + Gap 6 into ARCH-06 aggregate budget).

---

## 1. REQUIREMENTS

### R1. WarrantyBoundary

**R1.1** `classify(module: str) -> WarrantyClassification` returns:
- `module: str` (echoed)
- `category: WarrantyCategory` (`warranted` | `best_effort` | `unknown`)
- `reason: WarrantyReason`

**R1.2** Deterministic. No I/O. No clock. No random.

**R1.3** Warranty table (Phase 1):

| Module | Category    | Reason                  |
|--------|-------------|-------------------------|
| `m1`   | warranted   | deterministic_code_007  |
| `m2`   | warranted   | deterministic_opa_007   |
| `m3`   | warranted   | deterministic_code_007  |
| `m4`   | warranted   | deterministic_opa_007   |
| `m5`   | warranted   | deterministic_code_007  |
| `m6`   | warranted   | deterministic_code_007  |
| `m7`   | warranted   | deterministic_code_007  |
| `m8`   | best_effort | llm_007                 |
| `m9`   | best_effort | llm_007                 |
| `m10`  | warranted   | deterministic_code_007  |
| `m11`  | best_effort | external_vendor         |
| `m12`  | best_effort | llm_007                 |
| `m13`  | warranted   | deterministic_code_007  |
| other  | unknown     | unknown_module          |

**R1.4** Case-sensitive. Only lowercase `m1..m13` recognized. `"M1"`,
`"  m1"`, `"m1 "`, `"m1.verify"` → `unknown`.

**R1.5** `ProvenanceStage.stage` NOT used for classification; only
`.module` is consulted.

**R1.6** `WarrantyCategory.ordered_rank()`:
- `warranted` = 0, `best_effort` = 1, `unknown` = 2

**R1.7** `classify_all()` returns immutable mapping (MappingProxyType).
Mutation raises TypeError.

**R1.8** Coupling test: `set(WarrantyBoundary.TABLE.keys())` MUST
equal `{"m1", ..., "m13"}`. Links to M10's `_MODULE_PATTERN`.

### R2. ErrorAttribution

**R2.1** `ErrorCategory` enum — exactly 6 members:

| code                       | meaning                                  |
|----------------------------|------------------------------------------|
| `source_data_error`        | Vendor returned wrong/stale/corrupt data |
| `schema_translation_error` | M7 failed to map vendor — canonical      |
| `policy_evaluation_error`  | M2/M4 OPA rule bug or missing rule       |
| `llm_synthesis_error`      | LLM hallucinated / produced wrong output |
| `human_approval_error`     | HITL approved something it shouldn't     |
| `compliance_rule_error`    | OPA rule applied with wrong logic        |

**R2.2** `ErrorAttribution` frozen Pydantic model
(`ConfigDict(frozen=True, extra="forbid")`):
- `category: ErrorCategory`
- `stage: str` (min_length=1, max_length=200)
- `module: str` (min_length=1, max_length=20)
- `reason: str` (max_length=500) — see R2.4
- `occurred_at: datetime` (tz-aware UTC; naive → ValueError)

`extra="forbid"` means Phase 2 adding `reason_codes` is an explicit
model upgrade, not silent.

**R2.3** `model_dump(mode="json")` produces JSON-safe dict: enums as
strings, datetimes as UTC `Z`-suffixed.

**R2.4 PII enforcement on `reason`.** Validated at construction
against regex set:
- SSN: `\b\d{3}-\d{2}-\d{4}\b`
- Account (12+ digits): `\b\d{12,}\b`
- Email: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`
- IBAN: `\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b`

Match → `ValueError("reason contains potential PII pattern: <code>")`.
Patterns duplicated locally (Gap 2 does not import Gap 6; decoupled).

**R2.5** `attribute_from_chain(...)`:

```
attribute_from_chain(
    *, chain: Sequence[ProvenanceStage],
    failing_stage_name: str,
    category: ErrorCategory,
    reason: str,
    occurred_at: datetime,
) -> ErrorAttribution
```

- Empty chain → `ValueError("chain is empty")`.
- Stage not found → `ValueError("stage {name!r} not in chain")`.
- Duplicate → `ValueError("stage {name!r} appears more than once")`.

### R3. LiabilityReport

**R3.1** Frozen Pydantic (`frozen=True, extra="forbid"`):
- `report_schema_version: str` — class constant `"1.0.0"`,
  field_validator rejects any other value.
- `trace_id: str` (min_length=1, max_length=200)
- `generated_at: datetime` (tz-aware UTC)
- `chain: tuple[ProvenanceStage, ...]` (non-empty)
- `chain_verified: bool`
- `stage_classifications: tuple[StageClassification, ...]` (one per
  chain stage, same order)
- `overall_warranty: WarrantyCategory`
- `error_attribution: ErrorAttribution | None`
- `summary: LiabilitySummary`

`StageClassification` (frozen, `extra="forbid"`):
- `stage: ProvenanceStage`
- `classification: WarrantyClassification`
- `is_failing: bool`

Invariant: exactly one entry has `is_failing=True` iff
`error_attribution is not None`, matching stage name.

`LiabilitySummary` (frozen, `extra="forbid"`):
- `stage_count: int`
- `warranted_count: int`
- `best_effort_count: int`
- `unknown_count: int`
- `failing_stage: str | None`
- `failing_module: str | None`
- `failing_category: ErrorCategory | None`

**R3.2** `LiabilityReport.build(...)`:

```
build(
    *,
    trace_id: str,
    chain: list[ProvenanceStage],
    chain_verified: bool,
    generated_at: datetime,
    error: ErrorAttribution | None = None,
    boundary: WarrantyBoundary | None = None,
) -> LiabilityReport
```

Validation:
- `trace_id` empty → `ValueError`.
- `chain` empty → `ValueError`.
- `generated_at` naive → `ValueError`.
- `error.stage` absent / duplicate in chain → `ValueError`.
- Classify via `boundary or WarrantyBoundary()`.
- Compute `overall_warranty` per R3.7.
- Build `stage_classifications` honouring invariant.
- Build `summary` counters.

**R3.3** Determinism: same inputs → byte-identical
`to_canonical_json()`.

**R3.4 Canonical JSON contract.**
- Pydantic models: `model.model_dump(mode="json",
  exclude_none=False)`.
- `json.dumps(data, sort_keys=True, separators=(",", ":"),
  default=_json_default)`.
- `_json_default`:
  - `datetime` → UTC ISO 8601 `Z`-suffixed (not `+00:00`).
  - `Enum` → `.value`.
  - `UUID` → `str(uuid)`.
  - `tuple` → `list(tuple)`.
  - else → `TypeError`.

**R3.5 Golden hex digest.** Pinned fixture (fixed strings + fixed
timestamps) → `GOLDEN_HEX_DIGEST` constant in the test file. T2.17
asserts:
1. Byte-identical canonical JSON across two builds.
2. `sha256_digest() == GOLDEN_HEX_DIGEST`.
3. Independent recomputation via `hashlib.sha256(
   to_canonical_json().encode()).hexdigest()` matches constant.

Fixture:
```
report_schema_version = "1.0.0"
trace_id              = "trace-fixed-001"
generated_at          = 2026-04-14T12:00:00+00:00
chain = [
    ProvenanceStage(stage="m1.verify", module="m1",
        hash="0"*64, timestamp=2026-04-14T11:59:00+00:00),
    ProvenanceStage(stage="m6.dispatch", module="m6",
        hash="1"*64, timestamp=2026-04-14T11:59:30+00:00),
]
chain_verified = True
error          = None
```

The implementation agent records `GOLDEN_HEX_DIGEST` after first
correct run. Any future change to canonical JSON format will break
T2.17 — intentional.

**R3.6 `is_clean()` semantics.**

Returns True iff:
- `chain_verified == True`
- `error_attribution is None`
- `overall_warranty != unknown`

`best_effort` IS considered clean. It means "deliverable with
warranty surfaced to end user" — not "blocked". Callers SHOULD display
the warranty level to users for best_effort outputs.

**R3.7 overall_warranty precedence ladder.** First match wins:

1. `chain_verified == False` → `unknown`.
2. Any stage classified `unknown` → `unknown`.
3. `error_attribution is not None` → `max(max(stage rank),
   best_effort)`.
4. Else → `max(stage rank)`.

Rule 1 and 2 both yield `unknown`; rule 1 takes precedence because
broken chain integrity is stronger than unknown-module signal.

**R3.8** Report MUST NOT contain raw PII/MNPI:
- `reason` validated via R2.4 (mechanical).
- `trace_id`, `stage`, `module` length-capped.
- Payload hashes are SHA-256 (one-way).

### R4. Public API

`gap2_liability_provenance/__init__.py` re-exports:
```
WarrantyCategory, WarrantyReason, WarrantyClassification, WarrantyBoundary,
ErrorCategory, ErrorAttribution,
LiabilityReport, LiabilitySummary, StageClassification,
```

`src/compliance/__init__.py` re-exports gap2 + gap6.

### R5. Determinism + tests

**R5.1** All public functions pure.
**R5.2** Byte-identical canonical JSON (T2.17).
**R5.3** Warranty table snapshot (T2.4).
**R5.4** Every `ErrorCategory` member exercised (T2.20).
**R5.5** Edge cases: empty chain, empty trace_id, naive datetime,
unknown stage attribution, unknown module → unknown, verify=False →
unknown, all-warranted happy, all-best_effort happy (clean), warranted
+ error (best_effort, not clean), verify=False + no error (unknown,
not clean).

---

## 2. DESIGN

### 2.1 File layout

```
src/compliance/
  __init__.py                            # ~20
  gap2_liability_provenance/
    __init__.py                          # ~40
    warranty.py                          # ~180
    attribution.py                       # ~320
tests/unit/
  test_gap2_liability_provenance.py      # ~400
```

### 2.2 Canonical JSON helper (local in `attribution.py`)

```python
def _json_default(obj):
    if isinstance(obj, datetime):
        if obj.tzinfo is None:
            raise TypeError("naive datetime not serializable")
        return obj.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, UUID):
        return str(obj)
    if isinstance(obj, tuple):
        return list(obj)
    raise TypeError(f"not JSON serializable: {type(obj).__name__}")


def _canonical_json(data) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"),
                      default=_json_default)
```

### 2.3 Handoff diagram

```
ProvenanceChainBuilder (M10)
    │  .chain(), .verify() -> bool
    ▼
LiabilityReport.build(                   (Gap 2)
    trace_id=..., chain=builder.chain(),
    chain_verified=builder.verify(),
    generated_at=utc_now, error=optional,
)
    │  .to_canonical_json()
    │  .sha256_digest()
    ▼
M6 -> M10.write(AuditEntry(
    action="liability.report_generated",
    input_hash=report.sha256_digest(),
    provenance_chain=list(report.chain),
))
```

### 2.4 Frozen-model pattern

`ConfigDict(frozen=True, extra="forbid")` on every model. Mutation
raises `ValidationError`.

### 2.5 Security

- No credentials, no secrets.
- No network I/O, no filesystem I/O.
- PII regex on `reason` (R2.4) — mechanical.
- Length caps on every string field.
- `extra="forbid"` on every model.
- No logging.

### 2.6 Module boundary

- IMPORTS: `m3_schema_registry.ProvenanceStage` only.
- DOES NOT IMPORT: any other `m*_` module, Gap 6, LLM SDKs.

---

## 3. TASKS

T2.1 — `WarrantyCategory` enum + `ordered_rank()`.

T2.2 — `WarrantyReason` enum — 5 codes match R1.3.

T2.3 — `WarrantyClassification` frozen Pydantic; `model_dump(
mode="json")` keys JSON-safe.

T2.4 — `classify(...)` for all 13 modules — snapshot matches R1.3.

T2.5 — `classify(...)` for unknown inputs (`"M1"`, `"m14"`, `""`,
`"m1 "`, `"m1.verify"`) → `unknown` / `unknown_module`.

T2.6 — `classify_all()` immutable; mutation raises TypeError.

T2.7 — Coupling assertion (R1.8): TABLE keys == {m1..m13}.

T2.8 — `ErrorCategory` has exactly 6 members.

T2.9 — `ErrorAttribution` tz-aware validator; naive datetime raises.

T2.10 — PII validation on `reason` (R2.4). Parametrized:
- SSN → ValueError
- Email → ValueError
- Account (12+ digits) → ValueError
- IBAN → ValueError
- Clean reason → success

T2.11 — `attribute_from_chain(...)`: happy / empty chain / not-found /
duplicate. Four cases.

T2.12 — `StageClassification` frozen; mutation raises.

T2.13 — `LiabilitySummary` counters for mixed chain
`(m1, m8, m14-unknown)` → warranted=1, best_effort=1, unknown=1.

T2.14 — `build(...)` happy path: all warranted, no error,
`chain_verified=True` → `is_clean()`, `overall_warranty=warranted`.

T2.15 — `build(...)` empty trace_id / empty chain / naive datetime →
`ValueError`. Parametrized.

T2.16 — `build(...)` attribution.stage not in chain → `ValueError`.

T2.17 — Golden hex (R3.5): fixture → byte-identical canonical JSON;
`sha256_digest() == GOLDEN_HEX_DIGEST`; independent recompute matches.

T2.18 — `chain_verified=False` + no error → `is_clean() == False`,
`overall_warranty == unknown`.

T2.19 — Warranted chain + error at m1 → `is_clean() == False`,
`overall_warranty == best_effort`.

T2.20 — Every `ErrorCategory` member exercised (parametrized over 6).

T2.21 — All-best_effort chain, no error → `overall_warranty ==
best_effort`, `is_clean() == True` (R3.6).

T2.22 — `report_schema_version="2.0.0"` → ValidationError (mutation-
proof).

T2.23 — `stage_classifications` invariant (R3.1): exactly one
`is_failing=True` iff error is not None.

T2.24 — Public API exported from `compliance.gap2_liability_provenance`
(R4).

T2.25 — AST import scan: Gap 2 source imports stdlib + pydantic +
`m3_schema_registry` only.

T2.26 — `extra="forbid"` on every model. Passing unknown kwarg raises
ValidationError. One test per model (ErrorAttribution, LiabilityReport,
StageClassification, LiabilitySummary, WarrantyClassification).

---

## 4. TRACEABILITY

| AC     | Task(s)                                |
|--------|----------------------------------------|
| R1.1   | T2.1, T2.2, T2.3, T2.4                 |
| R1.2   | T2.4                                   |
| R1.3   | T2.4                                   |
| R1.4   | T2.5                                   |
| R1.5   | T2.4                                   |
| R1.6   | T2.1                                   |
| R1.7   | T2.6                                   |
| R1.8   | T2.7                                   |
| R2.1   | T2.8                                   |
| R2.2   | T2.9, T2.26                            |
| R2.3   | T2.3                                   |
| R2.4   | T2.10                                  |
| R2.5   | T2.11                                  |
| R3.1   | T2.12, T2.13, T2.14, T2.23             |
| R3.2   | T2.14, T2.15, T2.16, T2.22             |
| R3.3   | T2.17                                  |
| R3.4   | T2.17                                  |
| R3.5   | T2.17                                  |
| R3.6   | T2.14, T2.18, T2.19, T2.21             |
| R3.7   | T2.14, T2.18, T2.19, T2.21             |
| R3.8   | T2.10                                  |
| R4     | T2.24                                  |
| R5.1   | T2.17                                  |
| R5.2   | T2.17                                  |
| R5.3   | T2.4                                   |
| R5.4   | T2.20                                  |
| R5.5   | T2.5, T2.15, T2.16, T2.18, T2.19, T2.21|

---

## 5. REVIEW FIX TRACEABILITY (v1 — v2)

| Review item | v2 section                              |
|-------------|-----------------------------------------|
| F1 (R3.7 precedence)     | R3.7 explicit ladder       |
| F2 (PII enforcement)     | R2.4 mechanical regex      |
| F3 (schema version)      | R3.1, T2.22                |
| F4 (golden hex)          | R3.5, T2.17                |
| F5 (verify=False clarity)| R3.6, R3.7 rule 1, T2.18   |
| F6 (table coupling)      | R1.8, T2.7                 |
| F7 (reason_codes Phase 2)| §0.1, `extra="forbid"` R2.2|
| F8 (canonical JSON)      | R3.4                       |
| R1 (wiring diagram)      | §2.3                       |
| R2 (is_failing invariant)| R3.1, T2.23                |
| R3 (Gap 1 integration)   | §0.1                       |
| R4 (line budget)         | §0.5                       |
| R5 (model_dump mode)     | R3.4 `mode="json"`         |
| R6 (empty-chain attr)    | T2.11                      |
| R7 (best_effort clean)   | R3.6, T2.21                |
