# Gap 3 — WSP-to-YAML Compliance Mapping — COMPLETE

Parent module: M2 (Authority Policy)
Phase: 3 (BD onboarding prerequisite per ARCH-06 §3.8)
Agent: 007-compliance-agent
Review: `.kiro/specs/gap3-wsp-to-yaml-REVIEW-v2.md` — **8.30 / 10 GO**

---

## Summary

Gap 3 is the build-time bridge between a firm's Written Supervisory
Procedures (WSP) document and the OPA/Rego policy bundles that
implement them. Pure deterministic analyzer. NO LLM. NO runtime
traffic. Reads `AuthorityPolicy.rule_table()` from M2 (already built)
and joins it to an ingested WSP YAML document to produce a bidirectional
cross-reference manifest + a CI-blocking coverage report.

---

## LOC

| Artifact | Path | Lines |
|----------|------|-------|
| Spec (GO, v2) | `.kiro/specs/gap3-wsp-to-yaml.md` | 641 |
| Spec review v1 | `.kiro/specs/gap3-wsp-to-yaml-REVIEW.md` | 115 |
| Spec review v2 (GO) | `.kiro/specs/gap3-wsp-to-yaml-REVIEW-v2.md` | 87 |
| `__init__.py` | `src/compliance/gap3_wsp_to_yaml/__init__.py` | 90 |
| `__main__.py` | `src/compliance/gap3_wsp_to_yaml/__main__.py` | 10 |
| `models.py` | `src/compliance/gap3_wsp_to_yaml/models.py` | 236 |
| `ingest.py` | `src/compliance/gap3_wsp_to_yaml/ingest.py` | 190 |
| `registry.py` | `src/compliance/gap3_wsp_to_yaml/registry.py` | 247 |
| `yaml_generator.py` | `src/compliance/gap3_wsp_to_yaml/yaml_generator.py` | 127 |
| `coverage.py` | `src/compliance/gap3_wsp_to_yaml/coverage.py` | 85 |
| `rego_scanner.py` | `src/compliance/gap3_wsp_to_yaml/rego_scanner.py` | 93 |
| `cli.py` | `src/compliance/gap3_wsp_to_yaml/cli.py` | 177 |
| **Python source total** | | **1,255** |
| Unit tests | `tests/unit/test_gap3_wsp_to_yaml.py` | 1,044 |
| Integration tests | `tests/integration/test_gap3_m2_registry_roundtrip.py` | 154 |
| **Test total** | | **1,198** |

ARCH-06 budget target: ~1,000 lines. Actual Python source: 1,255 lines.
The overage is driven by explicit PII validators + Rego-file scanner +
frozen-vocabulary CLI plumbing, all required by the v2 spec fixes.

---

## Test counts

| Suite | File | Tests |
|-------|------|-------|
| Unit | `tests/unit/test_gap3_wsp_to_yaml.py` | 69 |
| Integration | `tests/integration/test_gap3_m2_registry_roundtrip.py` | 3 |
| **Gap 3 total** | | **72** |

Full project suite after Gap 3 + Gap 4: **1,707 passed, 0 failed**.

Command:
```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
# 1707 passed, 4 skipped, 5 xfailed, 1 xpassed, 101 warnings in 10.09s
```

---

## Acceptance Criteria checklist (per spec §4 traceability)

- [x] **R1.1** `WspSection` frozen Pydantic v2 model — T3.2, T3.28.
- [x] **R1.2** `WSP_SECTION_RE.pattern == m2.WSP_SECTION_RE.pattern` — T3.3.
- [x] **R1.3** `SupervisoryRole` 7-value enum — T3.1a.
- [x] **R1.4** `SupervisoryFrequency` 7-value enum — T3.1b.
- [x] **R1.5** `escalation_path` validation (min 1, max 10, valid
      roles, duplicates allowed) — T3.4.
- [x] **R1.6** `last_reviewed` ISO 8601 coercion — T3.2.
- [x] **R2.1** `RuleAnchor` regex-coupled to M2 `RULE_APPLIED_RE` — T3.6.
- [x] **R2.2** `WspMapping` supports empty `rules` (coverage gap) — T3.7.
- [x] **R2.3** `MappingRegistry.by_wsp()` / `.by_rule()` bidirectional — T3.11.
- [x] **R2.4** `MappingRegistry.from_m2` happy path — T3.10.
- [x] **R3.1** YAML manifest shape — T3.12 (golden).
- [x] **R3.2** Deterministic output (sorted sections, sorted rules) — T3.12.
- [x] **R3.3** Empty registry / naive datetime / PII in
      `last_updated_by` rejected — T3.13, T3.14, T3.15.
- [x] **R3.4** `sha256_digest` pinned golden value:
      `76aac9a36ea81d032f82d23310c583e0f4140e7517292128332a109769f9be9b`
      — T3.12.
- [x] **R4.1** `CoverageReport` frozen model — T3.16, T3.17, T3.18.
- [x] **R4.2** Exit code ladder (0 / 1 / 2) — T3.16, T3.17, T3.18, T3.19, T3.20.
- [x] **R4.3** `round(x, 3)` banker's rounding — T3_rounding_banker_matches_round.
- [x] **R4.4** Empty registry → exit 2 (CI-blocking) — T3.20.
- [x] **R5.1** PII regex on `title` / `body` / `last_updated_by` — T3.5, T3.15.
- [x] **R5.2** `last_updated_by` length cap (120) — T3.5 (implicit).
- [x] **R5.3** `FileReader` Protocol (no hard-coded paths) — T3.8, T3.9.
- [x] **R5.4** CLI one-line error reasons (no tracebacks by default) — T3.24, T3.26.
- [x] **R5.5** No credentials, no network, no WORM, no audit — T3.32.
- [x] **R6.1** CLI subcommand `scan-and-report` — T3.23.
- [x] **R6.2** CLI behavior (ingest → registry → report → optional
      output) — T3.23, T3.24, T3.25, T3.26.
- [x] **R6.3** Frozen exit-reason vocabulary — T3.23, T3.24, T3.25, T3.26.
- [x] **R6.4** No network I/O, no subprocess — T3.27 (AST scan).
- [x] **R7.1** Pure functions + FileReader Protocol — T3.27.
- [x] **R7.2** Byte-identical manifest output — T3.12.
- [x] **R7.3** `from_m2` registry structure stable — T3_30_mapping_order_stable.
- [x] **R7.4** No `datetime.now()` inside the library — T3.30.

## Verification gates

- [x] **Every Rego rule has wsp_section annotation** (checked via
      `scan_rego_file` in T3.21/T3.22; Gap 3 itself has no Rego, but
      its scanner is the CI hook for other gaps).
- [x] **No LLM dependencies** — `grep` for
      `openai|anthropic|langchain|bedrock|claude` on
      `src/compliance/gap3_wsp_to_yaml/` → 0 matches.
- [x] **Module boundary respected** — Gap 3 imports only M2 +
      pydantic + yaml + stdlib; verified by T3.27 AST scan.
- [x] **No credentials** — `grep` for AKIA/sk-/Bearer/ghp_/
      password=/api_key= on Gap 3 sources → 0 matches.
- [x] **Does NOT import M10 audit logger** — T3.32 AST scan.

## Files delivered

```
.kiro/specs/
  gap3-wsp-to-yaml.md
  gap3-wsp-to-yaml-REVIEW.md
  gap3-wsp-to-yaml-REVIEW-v2.md
  gap3-wsp-to-yaml-COMPLETE.md       (this file)

src/compliance/gap3_wsp_to_yaml/
  __init__.py
  __main__.py
  models.py
  ingest.py
  registry.py
  yaml_generator.py
  coverage.py
  rego_scanner.py
  cli.py

tests/unit/test_gap3_wsp_to_yaml.py
tests/integration/test_gap3_m2_registry_roundtrip.py
```

---

## V2 score recap

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 8.0   |
| Testability      | 15%    | 8.5   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |

**Weighted total: 8.30 / 10 — GO.**

---

**Status: COMPLETE. Ready for Phase 4 (runtime OPA migration).**
