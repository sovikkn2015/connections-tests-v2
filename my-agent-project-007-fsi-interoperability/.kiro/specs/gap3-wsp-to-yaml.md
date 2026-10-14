# Gap 3 — WSP-to-YAML Compliance Mapping — Spec (v2, post-review)

> Sub-module: Gap 3 WSP-to-YAML Mapping
> Parent module: M2 (Authority Policy)
> Phase: 3 (BD onboarding prerequisite per ARCH-06 §3.8)
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 (Gap 3), ARCH-09 (compliance sub-modules),
>   007-consolidated-design-and-plan.md (Part 9, Gap 3),
>   IMPL-06 (blocker matrix), steering rule 19.
> Related: M2 `AuthorityPolicy.rule_table()` (already built —
>   `src/m2_m4_policy_engine/authority.py`).
> Status: v2 — addresses F1..F8, R1..R7 from v1 review.

---

## 0. CONTEXT AND SCOPE

FINRA Rule 3110 requires every broker-dealer to maintain Written
Supervisory Procedures (WSPs). A FINRA examiner will ask: "Show me
the WSP for this AI agent, and prove that each procedure is enforced
by a specific technical control." Gap 3 is the **machine-readable
bridge** that answers that question.

Gap 3 is a **build-time tooling/registry sub-module**. It does not
evaluate any runtime policy. It does three things:

1. **Ingest** a human-readable WSP document into a structured,
   validated Pydantic model (one `WspSection` per procedure).
2. **Map** each `WspSection` to one or more OPA bundle + Rego rule
   identifiers (forward direction) and map every OPA rule back to a
   WSP section (reverse direction).
3. **Report** coverage gaps — WSP sections with no Rego anchor, and
   Rego rules with no `wsp_section` annotation.

The output is a versioned YAML manifest (`wsp-to-rego-mapping.yaml`)
that M5 config loads as a pointer and CI/CD consumes as a validator.
No runtime traffic touches Gap 3. It is a reporter + artifact builder.

Gap 3 lives in `src/compliance/gap3_wsp_to_yaml/`. Python 3.12+,
Pydantic v2, PyYAML only. NO LLM calls. Pure deterministic analyzer.

### 0.1 Non-goals

- Does NOT evaluate OPA rules at runtime (M2 owns that).
- Does NOT write to WORM or emit audit entries (M10 owns audit).
- Does NOT modify any Rego source file (only reads the inventory
  surface `AuthorityPolicy.rule_table()` + an optional `.rego` scan).
- Does NOT parse prose WSP text into requirements (ingest is
  structured YAML/JSON only — prose stays opaque `body` text).
- Does NOT decide allow/deny for any request.
- Does NOT use an LLM for classification or parsing.
- Does NOT mutate inputs. All pure-ish functions (filesystem I/O is
  surfaced behind a `FileReader` Protocol for tests).

**Phase 4 forward-compat:**
- `WspSection` ships `schema_version: Literal["1.0.0"]`. Phase 4
  adds `approval_history: tuple[ApprovalEntry, ...]` under a bumped
  schema. `extra="forbid"` makes the bump explicit.
- CI/CD hook (`validate_bundle_annotations`) will move to
  `opa-bundles/` build pipeline in Phase 4; Phase 3 ships it as a
  library function + CLI subcommand.

### 0.2 Directory layout

```
src/compliance/gap3_wsp_to_yaml/
  __init__.py               # public API re-exports
  models.py                 # Pydantic v2: WspSection, RuleAnchor, ...
  ingest.py                 # WSP document ingest (YAML/JSON reader)
  registry.py               # Build + query bidirectional cross-ref
  yaml_generator.py         # Emit wsp-to-rego-mapping.yaml
  coverage.py               # Coverage report (forward + reverse gaps)
  rego_scanner.py           # Lightweight .rego wsp_section extractor
  cli.py                    # `python -m compliance.gap3_wsp_to_yaml`
```

### 0.3 Allowed imports

- stdlib: `__future__`, `argparse`, `dataclasses`, `enum`, `hashlib`,
  `json`, `pathlib`, `re`, `sys`, `typing`, `datetime`, `io`,
  `types`.
- `pydantic` (v2 only).
- `yaml` (PyYAML — already in pyproject).
- `m2_m4_policy_engine.AuthorityPolicy` (READ-ONLY: `rule_table()`
  and `list_rules()` — no evaluation path touched).

FORBIDDEN: any other `m*_` module, `openai`, `anthropic`,
`langchain`, `boto3`, `langfuse`, `requests`, `httpx`, any LLM SDK.

### 0.4 Threading

Pure functions + frozen Pydantic models → thread-safe. The CLI
returns exit codes; no mutable global state.

### 0.5 Line budget

ARCH-06 target: ~1,000 lines (Python + Rego annotations + JSON
schemas). Gap 3 Python source only:

- `models.py`: ~220
- `ingest.py`: ~110
- `registry.py`: ~180
- `yaml_generator.py`: ~95
- `coverage.py`: ~130
- `rego_scanner.py`: ~80
- `cli.py`: ~130
- `__init__.py`: ~55
- Tests (gap3): ~700

Python source ≈ 1,000. Within ARCH-06 Gap 3 budget.

---

## 1. REQUIREMENTS

### R1. WSP ingest model (`WspSection`)

**R1.1** Frozen Pydantic v2 model
(`ConfigDict(frozen=True, extra="forbid")`) with the following
fields:

| Field              | Type                       | Notes                                   |
|--------------------|----------------------------|-----------------------------------------|
| `schema_version`   | `Literal["1.0.0"]`         | Class-pinned. Bump is explicit.         |
| `wsp_id`           | `str` (min 1, max 40)      | Document ID, e.g. `"WSP-ACME-2026"`.    |
| `section_id`       | `str` pattern `WSP_SECTION_RE` | e.g. `"WSP-TRD-3.1"`.               |
| `title`            | `str` (min 1, max 200)     | Human section title.                    |
| `body`             | `str` (min 1, max 10_000)  | Prose procedure text.                   |
| `supervisory_role` | `SupervisoryRole` enum     | 7 canonical roles.                      |
| `frequency`        | `SupervisoryFrequency` enum| 7 cadences.                             |
| `escalation_path`  | `tuple[str, ...]` (min 1)  | Ordered role chain.                     |
| `last_reviewed`    | `date \| None`             | `None` means never reviewed.            |

**R1.2** `WSP_SECTION_RE` is `re.compile(r"^WSP-[A-Z]+-\d+(\.\d+)?$")`
and MUST equal `m2_m4_policy_engine.WSP_SECTION_RE` (spec R1 cross-
couples to the runtime engine's regex by value-equality — not
import, to keep boundary tight). Coupling test T3.3 asserts equality.

**R1.3** `SupervisoryRole` enum (string values):
`chief_compliance_officer`, `compliance_officer`, `principal`,
`registered_rep`, `operations`, `cco_designee`, `audit_committee`.

**R1.4** `SupervisoryFrequency` enum (string values):
`real_time`, `intraday`, `daily`, `weekly`, `monthly`, `quarterly`,
`ad_hoc`.

**R1.5** `escalation_path` is a non-empty, length-capped (10),
tuple of strings. Each entry is validated against `SupervisoryRole`
values (string comparison; the stored type stays `str` so historical
role names survive an enum add).

**R1.6** `last_reviewed` is an optional `datetime.date`. String
inputs follow ISO 8601 (`YYYY-MM-DD`) via Pydantic's built-in
coercion; invalid strings raise `ValidationError`.

### R2. Rule anchor + mapping models

**R2.1** `RuleAnchor` frozen Pydantic — the machine-readable
address of a policy rule:
- `rule_applied: str` — must match `RULE_APPLIED_RE` imported from
  M2 (`m2_m4_policy_engine.RULE_APPLIED_RE`). Exposing the coupling
  guarantees renames cascade.
- `opa_bundle: str` (min 1, max 100) — e.g. `"authority"`.
- `rego_file: str` pattern `^[a-z_/]+\.rego$` — e.g.
  `"authority/restricted_list.rego"`.
- `rego_rule: str` (min 1, max 80) — e.g. `"check_restricted_list"`.

**R2.2** `WspMapping` frozen Pydantic bundling one `WspSection` +
ordered tuple of `RuleAnchor`:
- `wsp_section: WspSection`
- `rules: tuple[RuleAnchor, ...]` — may be empty (that is the
  coverage-gap case).

**R2.3** Two reverse-index helpers on `MappingRegistry`:
- `by_wsp(section_id) -> tuple[RuleAnchor, ...]` — forward lookup.
- `by_rule(rule_applied) -> tuple[str, ...]` — returns every
  `section_id` that anchors this rule. Empty tuple = orphan rule.

**R2.4** `MappingRegistry.from_m2(authority: AuthorityPolicy,
sections: Sequence[WspSection])` — convenience constructor that
builds a registry by joining M2's `rule_table()` output to the
ingested sections on `wsp_section`. A single rule may anchor
multiple WSP sections and vice versa (many-to-many).

### R3. YAML generator

**R3.1** `generate_manifest(registry, *, generated_at,
last_updated_by) -> str` emits YAML with:

```yaml
schema_version: "1.0.0"
generated_at: "2026-04-14T12:00:00Z"
last_updated_by: "compliance_sme@firm.com"
wsp_document_id: "WSP-ACME-2026"
mappings:
  - wsp_section: "WSP-TRD-3.1"
    wsp_title: "Restricted List Management"
    supervisory_role: "compliance_officer"
    frequency: "real_time"
    escalation_path: ["compliance_officer", "chief_compliance_officer"]
    rules:
      - rule_applied: "authority/advisor/restricted_list.v1"
        opa_bundle: "authority"
        rego_file: "authority/restricted_list.rego"
        rego_rule: "check_restricted_list"
```

**R3.2** Output is **deterministic**: sections sorted by
`section_id` ASCII ascending; `rules` sorted by `rule_applied`
ASCII ascending. `yaml.safe_dump` with `sort_keys=True,
default_flow_style=False, allow_unicode=True, width=100`.

**R3.3** Generator MUST reject:
- empty `registry` (no sections ingested) → `ValueError`.
- naive `generated_at` → `ValueError("generated_at must be tz-aware")`.
- `last_updated_by` matching any PII regex (R5.1) → `ValueError`
  (keeps reviewer identity as work email, rejects embedded SSNs/
  account numbers in identity strings).

**R3.4** `sha256_digest(manifest_str) -> str` returns hex SHA-256
of the emitted YAML UTF-8 bytes. Same inputs → byte-identical YAML
→ identical digest (determinism contract).

### R4. Coverage reporter

**R4.1** `build_coverage_report(registry) -> CoverageReport`
returns a frozen Pydantic model:

| Field                      | Type                     | Meaning                                  |
|----------------------------|--------------------------|------------------------------------------|
| `schema_version`           | `Literal["1.0.0"]`       |                                          |
| `total_wsp_sections`       | `int`                    |                                          |
| `total_rules`              | `int`                    | from M2 `rule_table()` if registry built via `from_m2`. |
| `mapped_sections`          | `int`                    | sections with >=1 anchor.                |
| `unmapped_sections`        | `tuple[str, ...]`        | `section_id` list, sorted.               |
| `orphan_rules`             | `tuple[str, ...]`        | `rule_applied` list with no WSP, sorted. |
| `coverage_pct`             | `float` (0-100, 3dp)     | `mapped / total_wsp_sections * 100`.     |
| `orphan_pct`               | `float` (0-100, 3dp)     | `orphans / total_rules * 100`.           |
| `exit_code`                | `int`                    | 0 = OK, 1 = gaps found, 2 = CI-blocking. |

**R4.2** `exit_code` mapping (fail-closed for CI):
- 0: `unmapped_sections` empty AND `orphan_rules` empty.
- 1: any unmapped section or orphan rule.
- 2: registry built with `strict=True` and any orphan rule exists
  (steering rule 19 violation — CI blocks the bundle build).

**R4.3** `coverage_pct` rounded **half-even** to 3 decimal places
via `round(x, 3)` (Python's banker's rounding). Same input → same
float.

**R4.4** If `total_wsp_sections == 0`, `coverage_pct` = `0.000`
and `exit_code` = `2` (empty registry is a CI-blocking misconfig,
not a success).

### R5. Security

**R5.1** PII regex set applied to free-text WSP fields
(`body`, `title`, `last_updated_by`). Same regex set as Gap 2
(SSN, 12+ digits, email, IBAN). Match → `ValueError` at model
construction.

> Exception: `body` MAY contain email-like strings that reference
> role mailboxes (e.g., `cco@firm.com`). Per R5.1, these ARE
> rejected in Phase 3. The WSP author is expected to use role names
> (`compliance_officer`) in procedure body, not email addresses. CI
> failures surface the violating section.

**R5.2** `last_updated_by` max length 120.

**R5.3** `FileReader` Protocol gates filesystem access. Production
uses `LocalFileReader` (pathlib). Tests use `InMemoryFileReader`.
No hard-coded paths. All paths validated with `pathlib.Path` and
confined to `--wsp-dir` / `--opa-dir` command-line arguments.

**R5.4** CLI never echoes file contents on error. Exit code + one-
line error reason only (frozen vocabulary). No traceback by
default; `--debug` prints the exception class name only, no chain.

**R5.5** No credentials, no network I/O, no WORM write, no audit
emission. Gap 3 is a build-time tool.

### R6. CLI (`python -m compliance.gap3_wsp_to_yaml`)

**R6.1** Single subcommand `scan-and-report` (Phase 3 default):
```
python -m compliance.gap3_wsp_to_yaml scan-and-report \
    --wsp-file path/to/wsp.yaml \
    --output path/to/mapping.yaml \
    [--strict] [--debug]
```

**R6.2** Behavior:
1. Read `--wsp-file` via `LocalFileReader`.
2. Parse YAML into `list[WspSection]`. First validation error →
   exit 3 (`wsp_ingest_failed`).
3. Build registry via `MappingRegistry.from_m2(AuthorityPolicy(),
   sections)`. Errors → exit 4 (`registry_build_failed`).
4. Build `CoverageReport`. Print one-line summary to stdout.
5. If `--output` provided, write manifest YAML.
6. Exit with `report.exit_code` (0/1/2 per R4.2).

**R6.3** Error reasons (frozen vocabulary; nothing else ever
printed):
```
wsp_ingest_failed
registry_build_failed
manifest_write_failed
argument_parse_failed
```

**R6.4** No network I/O, no subprocess calls.

### R7. Determinism + test hooks

**R7.1** All public functions pure or behind a `FileReader`
Protocol.

**R7.2** Byte-identical manifest YAML across two invocations with
identical inputs (T3.12 asserts via `sha256_digest`).

**R7.3** `from_m2` builds the same registry structure for the same
`(AuthorityPolicy, sections)` tuple — property test exercises order
stability (T3.24).

**R7.4** No `datetime.now()`, no `uuid.uuid4()` inside the library.
Clock + id generation are caller-supplied (CLI gets them from
`datetime.now(timezone.utc)` / fixed `last_updated_by`).

---

## 2. DESIGN

### 2.1 File layout (repeats §0.2 with line estimates)

```
src/compliance/gap3_wsp_to_yaml/
  __init__.py             # ~55
  models.py               # ~220
  ingest.py               # ~110
  registry.py             # ~180
  yaml_generator.py       # ~95
  coverage.py             # ~130
  rego_scanner.py         # ~80
  cli.py                  # ~130
tests/unit/
  test_gap3_wsp_to_yaml.py   # ~700
tests/integration/
  test_gap3_m2_registry_roundtrip.py  # ~90
```

### 2.2 Public surface

```python
# compliance.gap3_wsp_to_yaml
from compliance.gap3_wsp_to_yaml import (
    # Enums
    SupervisoryRole, SupervisoryFrequency,
    # Models
    WspSection, RuleAnchor, WspMapping, CoverageReport,
    # Registry
    MappingRegistry,
    # Ingest
    FileReader, LocalFileReader, InMemoryFileReader,
    ingest_wsp_yaml,
    # Generator + coverage
    generate_manifest, sha256_digest, build_coverage_report,
    # Rego scanner
    scan_rego_file, scan_rego_directory,
    # Constants
    WSP_SECTION_RE, SECTION_SCHEMA_VERSION,
)
```

### 2.3 `MappingRegistry.from_m2` algorithm

```
rule_rows = authority.rule_table()  # list[dict]
sections_by_id = {s.section_id: s for s in sections}

# Forward: per section, collect rules whose wsp_section matches.
forward: dict[str, list[RuleAnchor]] = {s.section_id: [] for s in sections}
# Reverse: per rule_applied, collect section_ids that match.
reverse: dict[str, list[str]] = {}

for row in rule_rows:
    wsp = row["wsp_section"]
    rule_applied = row["rule_applied"]
    reverse.setdefault(rule_applied, [])
    if wsp in forward:
        anchor = RuleAnchor(
            rule_applied=rule_applied,
            opa_bundle=_bundle_from(rule_applied),
            rego_file=_rego_file_from(rule_applied),
            rego_rule=_rego_rule_from(rule_applied),
        )
        forward[wsp].append(anchor)
        reverse[rule_applied].append(wsp)
    # else: rule has a wsp_section that is NOT in ingested doc ->
    #       orphan candidate surfaced by coverage report.

# Sort for determinism.
mappings = tuple(
    WspMapping(
        wsp_section=sections_by_id[sid],
        rules=tuple(sorted(anchors, key=lambda a: a.rule_applied)),
    )
    for sid, anchors in sorted(forward.items())
)
```

### 2.4 `scan_rego_file` (minimal)

Reads a `.rego` file. Extracts every `# METADATA` block's `custom:
wsp_section: "<VALUE>"` line via regex. Returns
`tuple[RegoRuleAnchor, ...]`. Used by CI to catch Rego rules with
no `wsp_section` annotation.

Regex (single-line, conservative):
```
_WSP_IN_REGO = re.compile(
    r"^\s*wsp_section\s*:\s*\"(WSP-[A-Z]+-\d+(?:\.\d+)?)\"\s*$",
    re.MULTILINE,
)
```

Files without annotations → returned anchors include
`wsp_section=None` for the module-level `package` line; coverage
reporter flags them as orphans.

### 2.5 Wiring diagram

```
WSP author ─► wsp.yaml                                    (HUMAN EDITS)
                │
                ▼
         ingest_wsp_yaml
                │
                ▼        ┌────────────────────────┐
           list[WspSection]◄─── FileReader (Protocol)
                │
                ▼
     MappingRegistry.from_m2(AuthorityPolicy(), sections)
                │
                ├────────► generate_manifest → wsp-to-rego-mapping.yaml
                │                              (deterministic YAML)
                │
                ├────────► build_coverage_report → CoverageReport
                │                              (exit code 0/1/2)
                │
                └────────► scan_rego_directory (CI hook)
                                               │
                                               ▼
                                        orphan rule list
```

### 2.6 Security

- No credentials, no secrets, no network I/O.
- All filesystem access behind `FileReader` Protocol.
- PII regex on every ingested free-text field (R5.1).
- Length caps on every string field.
- `extra="forbid"` on every model.
- No logging of file contents. One-line exit reasons.
- No exception chaining in CLI user output; `--debug` prints class
  name only.

### 2.7 Module boundary

- IMPORTS: `m2_m4_policy_engine.AuthorityPolicy`,
  `m2_m4_policy_engine.RULE_APPLIED_RE`,
  `m2_m4_policy_engine.WSP_SECTION_RE` (READ-ONLY).
- DOES NOT IMPORT: any other `m*_` module, Gap 2/4/6, LLM SDKs.
- DOES NOT MUTATE: `AuthorityPolicy` state; only calls
  `rule_table()` / `list_rules()`.

---

## 3. TASKS

T3.1  — `SupervisoryRole`, `SupervisoryFrequency` enums; value
         snapshots T3.1a/T3.1b.

T3.2  — `WspSection` frozen Pydantic; every field validated per
         R1.1; `model_dump(mode="json")` round-trip.

T3.3  — Coupling assertion (R1.2): `WSP_SECTION_RE.pattern ==
         m2_m4_policy_engine.WSP_SECTION_RE.pattern`.

T3.4  — `escalation_path` validation: empty → ValueError; >10 →
         ValueError; unknown role → ValueError; duplicate allowed
         (principal→principal means dual-role).

T3.5  — PII regex on `title`, `body`, `last_updated_by` (R5.1)
         parametrized: SSN / email / 12-digit acct / IBAN / clean.

T3.6  — `RuleAnchor` frozen; rule_applied coupled to M2 regex;
         bad path → ValidationError.

T3.7  — `WspMapping` frozen; empty `rules` allowed (that is the
         coverage-gap case).

T3.8  — `ingest_wsp_yaml(reader, path)` happy path: reads 3-section
         fixture → 3 `WspSection` objects, preserved order.

T3.9  — `ingest_wsp_yaml` error paths: missing file (exit 3), non-
         YAML bytes, YAML-not-a-list, section missing required
         field, duplicate `section_id` → ValueError.

T3.10 — `MappingRegistry.from_m2(AuthorityPolicy(), sections)`
         happy path: 11 M2 rules → registry covers matching
         sections, unmatched rules surface in `orphan_rules`.

T3.11 — `MappingRegistry.by_wsp(section_id)` and `.by_rule(
         rule_applied)` round-trip.

T3.12 — Golden manifest YAML: fixture (3 sections + M2 rules) →
         byte-identical YAML across 2 runs; `sha256_digest` matches
         pinned `GOLDEN_MANIFEST_DIGEST` constant.

T3.13 — `generate_manifest` empty registry → ValueError.

T3.14 — `generate_manifest` naive `generated_at` → ValueError.

T3.15 — `generate_manifest` PII in `last_updated_by` → ValueError.

T3.16 — `build_coverage_report` happy path: 3 sections, all
         mapped, 0 orphans → exit_code=0, coverage_pct=100.000.

T3.17 — `build_coverage_report` with unmapped section →
         exit_code=1, `unmapped_sections` sorted ASCII ascending.

T3.18 — `build_coverage_report` with orphan rule →
         exit_code=1, `orphan_rules` sorted ASCII ascending.

T3.19 — `build_coverage_report` with `strict=True` + orphan →
         exit_code=2.

T3.20 — `build_coverage_report` with empty registry →
         exit_code=2, coverage_pct=0.000.

T3.21 — `scan_rego_file` extracts `wsp_section` metadata; file
         without annotation returns empty tuple.

T3.22 — `scan_rego_directory` aggregates across multiple files;
         deterministic ordering by path.

T3.23 — CLI `scan-and-report` happy path (tmp_path, in-mem stdout
         capture) → exit 0 with summary line.

T3.24 — CLI `scan-and-report` with unmapped section → exit 1;
         stdout one line, stderr empty.

T3.25 — CLI `scan-and-report --strict` with orphan → exit 2.

T3.26 — CLI invalid argument → exit 5 (`argument_parse_failed`).

T3.27 — AST import scan: Gap 3 source imports only stdlib +
         pydantic + yaml + m2_m4_policy_engine.

T3.28 — `extra="forbid"` on every model — one param-test per
         model (WspSection, RuleAnchor, WspMapping, CoverageReport).

T3.29 — `schema_version="2.0.0"` on `WspSection` →
         ValidationError.

T3.30 — Determinism property: given fixed sections + M2, two
         independent registry builds produce equal `__repr__`
         outputs.

T3.31 — Integration: `AuthorityPolicy.rule_table()` sample matches
         generated manifest `rules` entries for the 11 M2 rules
         (cross-module round-trip).

T3.32 — Integration: M10 audit emission — Gap 3 does NOT call M10
         (negative assertion: `sys.modules` check that
         `m10_audit_logger` is absent after `import compliance
         .gap3_wsp_to_yaml`).

T3.33 — Integration: coverage report passes through
         `m2_m4_policy_engine` round-trip without module-boundary
         violation (AST scan on Gap 3 package).

---

## 4. TRACEABILITY

| AC    | Task(s)                                      |
|-------|----------------------------------------------|
| R1.1  | T3.2, T3.28                                  |
| R1.2  | T3.3                                         |
| R1.3  | T3.1                                         |
| R1.4  | T3.1                                         |
| R1.5  | T3.4                                         |
| R1.6  | T3.2                                         |
| R2.1  | T3.6                                         |
| R2.2  | T3.7                                         |
| R2.3  | T3.11                                        |
| R2.4  | T3.10                                        |
| R3.1  | T3.12                                        |
| R3.2  | T3.12                                        |
| R3.3  | T3.13, T3.14, T3.15                          |
| R3.4  | T3.12                                        |
| R4.1  | T3.16, T3.17, T3.18                          |
| R4.2  | T3.16, T3.17, T3.18, T3.19, T3.20            |
| R4.3  | T3.16                                        |
| R4.4  | T3.20                                        |
| R5.1  | T3.5, T3.15                                  |
| R5.2  | T3.5                                         |
| R5.3  | T3.8, T3.9                                   |
| R5.4  | T3.24, T3.26                                 |
| R5.5  | T3.32                                        |
| R6.1  | T3.23                                        |
| R6.2  | T3.23, T3.24, T3.25                          |
| R6.3  | T3.23, T3.24, T3.25, T3.26                   |
| R6.4  | T3.27                                        |
| R7.1  | T3.27                                        |
| R7.2  | T3.12                                        |
| R7.3  | T3.30                                        |
| R7.4  | T3.30                                        |

---

## 5. REVIEW FIX TRACEABILITY (v1 — v2)

| Review item | v2 section                                  |
|-------------|---------------------------------------------|
| F1 (regex coupling) | R1.2 + T3.3                         |
| F2 (PII enforcement) | R5.1 + T3.5                        |
| F3 (schema version) | R1.1 `Literal["1.0.0"]` + T3.29      |
| F4 (golden manifest) | R3.4 + T3.12                       |
| F5 (empty-registry CI semantics) | R4.4 + T3.20              |
| F6 (CLI frozen exit codes) | R6.3 + T3.26                    |
| F7 (filesystem Protocol) | R5.3 + T3.8/T3.9                  |
| F8 (determinism contract) | R7.2 + T3.12/T3.30               |
| R1 (wiring diagram) | §2.5                                 |
| R2 (line budget) | §0.5                                    |
| R3 (module boundary AST) | §2.7 + T3.27/T3.32               |
| R4 (forward-compat Phase 4) | §0.1                          |
| R5 (coverage percentage rounding) | R4.3                    |
| R6 (rego scanner precision) | §2.4                          |
| R7 (many-to-many mapping) | §2.3                            |
