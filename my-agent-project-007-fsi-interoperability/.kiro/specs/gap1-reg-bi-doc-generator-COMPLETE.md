# Gap 1 — Reg BI Doc Generator — COMPLETE

> Sub-module: Gap 1 Reg BI Doc Generator
> Parent module: M10 (Audit Logger)
> Phase: 2-3 (Phase-3 BD onboarding closure)
> Status: **COMPLETE — v3 shipped**

---

## Playbook Status

| Step | Name | Status | Notes |
|------|------|--------|-------|
| 1 | Spec v1 | ✅ | `.kiro/specs/gap1-reg-bi-doc-generator.md` |
| 2 | LLMJ Review v1 | ✅ | F1..F15 findings against v3 spec |
| 3 | Spec v3 (rewrite) | ✅ | Addresses F1..F15 inline |
| 4 | LLMJ Review v2 | ✅ | **≥8.0 GO** — `.kiro/specs/gap1-reg-bi-doc-generator-REVIEW-v2.md` |
| 5 | Build | ✅ | 8 source files + 2 test files (this doc) |
| 6 | Verify | ✅ | 91 new tests pass, 1848 total, 10 consecutive stable runs |
| 7 | Complete | ✅ | This marker |

---

## Scores

- **v2 LLMJ score**: ≥8.0/10 GO (captured at review time; see REVIEW-v2.md).
- **v3 coverage vs spec**: every R1..R12 acceptance criterion mapped
  to at least one unit or integration test (see §Traceability).

---

## LOC Totals

### Python source — `src/compliance/gap1_reg_bi_doc_generator/`

| File | Lines | Purpose |
|------|-------|---------|
| `__init__.py` | 177 | Public API re-exports (R11) |
| `_types.py` | 58 | Enums + error vocabulary |
| `applicability.py` | 39 | Precedence ladder (R2) |
| `audit_client.py` | 107 | AuditClient Protocol + in-memory stub (R8) |
| `disclosures.py` | 349 | 7 canonical disclosure types (R3b) |
| `document.py` | 377 | GenerationInput + RegBiDocument + PII scrub (R1, R5, R6) |
| `generator.py` | 495 | RegBiDocGenerator orchestrator (R7) |
| `mnpi_preflight.py` | 123 | MnpiFilter Protocol + Regex default (R4b) |
| `narrative.py` | 128 | NarrativeClient Protocol + stubs + FakeLLM (R4) |
| `obligations.py` | 646 | 4-obligation populators + OPA matrix (R3, R3a) |
| `principal_queue.py` | 85 | PrincipalReviewQueue Protocol + entry (R9) |
| `renderer.py` | 330 | DocumentRenderer + RenderedDocument (R5b) |
| `smarsh_hook.py` | 79 | SmarshArchiveClient Protocol + stub (R10) |
| **Total Python src** | **2,993** | ≈ spec target ~1,960 Python + headers/docstrings |

### Tests

| File | Lines | Tests | Purpose |
|------|-------|-------|---------|
| `tests/unit/test_gap1_reg_bi_doc_generator.py` | 1,485 | 86 | T1.1..T1.53 unit coverage |
| `tests/integration/test_gap1_end_to_end.py` | 365 | 5 | I1..I5 integration coverage |
| **Total tests** | **1,850** | **91** | |

### Grand total: **4,843 LoC**

---

## Verification

### Baseline + Gap 1 v3 suite

Command:
```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
```

Result:
```
1848 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in ~10s
```

- Baseline before Gap 1 v3: **1757 passed**.
- After Gap 1 v3: **1848 passed** (+91).
- Zero regressions.

### 10 consecutive stable runs

| Run | Passed | Wall-clock |
|-----|--------|------------|
| 1 | 1848 | 9.24s |
| 2 | 1848 | 9.98s |
| 3 | 1848 | 10.48s |
| 4 | 1848 | 10.55s |
| 5 | 1848 | 9.89s |
| 6 | 1848 | 9.64s |
| 7 | 1848 | 9.54s |
| 8 | 1848 | 9.54s |
| 9 | 1848 | 9.79s |
| 10 | 1848 | 10.56s |

All 10 runs produced identical `1848 passed, 12 skipped, 5 xfailed, 1 xpassed`. No flakiness.

---

## Acceptance Criteria Checklist (spec §2.8 + §6)

### Module boundary (steering rules 9 + 14 + spec R12)

- [x] `src/compliance/gap1_reg_bi_doc_generator/` imports only stdlib +
      pydantic + `{m1_identity, m3_schema_registry, m5_config_loader}`.
      Enforced by AST-scan T1.22.
- [x] No imports of `m2_m4_policy_engine`, `m6_mcp_gateway`, `m7_*`,
      `m8_*`, `m9_*`, `m10_audit_logger`, `m11_*`, `m12_*`.
- [x] No LLM SDKs (`anthropic`, `openai`, `boto3`, `httpx`, `requests`).
- [x] No filesystem or network I/O in the module.

### Determinism + fail-closed

- [x] Every compliance check implemented as deterministic Python
      (populators + OPA matrix). NO LLM for compliance (steering rule 14).
- [x] M4 MNPI preflight invoked BEFORE every `NarrativeClient.stitch`
      call. T1.41, T1.42, T1.42b.
- [x] Fail-closed on every compliance path: MNPI failure → narrative
      aborted + `advisor_review_required=True` + audit recorded.
- [x] Audit write failure raises `AuditWriteFailed` — the one raise
      path (R7.4). T1.25.
- [x] SKIP_* path also emits audit + raises on audit failure
      (F3 fail-closed parity). T1.31a + T1.31b.
- [x] Smarsh archive failure raises `SmarshArchiveFailed` (R10.3).
      T1.45.
- [x] `InsufficientBulletsError` propagates; no degradation.

### OPA matrix (R3, steering rule 19)

- [x] Every rule in `REQUIRED_SECTIONS_MATRIX` has a non-empty
      `wsp_section` annotation. Build-time assert in `obligations.py`
      + test T1.36.
- [x] `rule_applied` path maps 1:1 to a Rego dotted path
      (T1.36a — `replace("/", ".")` yields `^[a-z0-9_.]+\.v[1-9]\d*$`).
- [x] Base + archetype + account-type + product-type overlays all
      present; IRA and 401(k)/403(b) account overlays shipped.

### Canonical disclosures (R3b)

- [x] All 7 canonical disclosure types frozen Pydantic +
      `extra="forbid"`. T1.39.
- [x] `CanonicalDisclosures` container present on every
      `RegBiDocument`.
- [x] `populate_disclosures` deterministic, round-trips via
      `model_dump` ↔ `model_validate`. T1.40.

### Document (R6)

- [x] `document_schema_version` bumped 1.0.0 → **1.1.0**. T1.19b, T1.30.
- [x] 8 new v3 fields present: `canonical_disclosures`,
      `matched_rules`, `matched_wsp_sections`, `required_disclosures`,
      `is_retail`, `narrative_model_configured`,
      `any_mnpi_preflight_failed`, `rendered_content_sha256`.
- [x] `with_rendered_hash()` immutable copy-with-update (R7.3 step 10).
- [x] `extra="forbid"` on every Pydantic model. T1.27.
- [x] Canonical JSON deterministic + SHA-256 digest. Golden-hex T1.19.

### Renderer (R5b)

- [x] `render_html` pure Python + `html.escape(quote=True)` — XSS-safe.
      T1.46d.
- [x] Deterministic across two calls on same document. T1.46b.
- [x] `content_sha256` = SHA-256 hex of UTF-8 body bytes. T1.46.
- [x] `render_pdf` raises `RendererNotImplemented("pdf_deferred_phase4")`.
      T1.46c.
- [x] Body size cap 2 MiB.

### Principal review queue (R9, steering rule 17)

- [x] Protocol + `InMemoryPrincipalReviewQueue` stub + immutable
      `PrincipalReviewQueueEntry`.
- [x] FINRA 2210 `pre_use` / `post_use` semantics:
      - `pre_use`: queue enqueued BEFORE audit write. T1.47.
      - `post_use`: queue enqueued AFTER audit write. T1.48.
- [x] Gated to `registration_type in {bd_only, dual_registered}` AND
      `advisor_review_required=True` AND `principal_review_config`
      non-None. T1.49, T1.50.

### Smarsh archive (R10, steering rule 18)

- [x] Protocol + `InMemorySmarshClient` stub + `SmarshArchiveFailed`.
- [x] Gated to BD/dual-registered firms only. T1.43, T1.44.
- [x] `__init__` precondition: `smarsh_client` without `renderer`
      raises `ValueError("smarsh_requires_renderer")`. T1.45a.

### Narrative + MNPI (R4, R4b, steering rules 7 + 14)

- [x] `NarrativeClient` Protocol + `StubNarrativeClient` +
      `BulletConcatNarrativeClient` + `FakeLLMNarrativeClient`.
- [x] `narrative_model_configured` sourced from `RegBiConfig.narrative_model`,
      not hard-coded. T1.51, T1.52.
- [x] LLM failure (raise / PII / non-string) → narrative `""` +
      `llm_narrative_failed=True` + `advisor_review_required=True`.
      T1.23, T1.24.
- [x] `MnpiFilter` Protocol + `StubMnpiFilter` + `RegexMnpiFilter`.
- [x] `RegexMnpiFilter` imports `_PII_PATTERNS` FROM `document.py` —
      single source of truth (R4b.2 / F6). T1.41a.
- [x] Preflight runs BEFORE stitch for every section. T1.42b.

### Security

- [x] `_scrub_pii` applied at 4 checkpoints (reason_trace validator,
      bullet finalize, narrative post-stitch, renderer cells).
- [x] Client PII (`email`, `date_of_birth`, `ssn_last_four`, `tax_id`)
      never read by populators or renderer. T1.18, T1.18b.
- [x] No `client.display_name` emitted in bullets or narrative. T1.18b.
- [x] No credentials anywhere in source (grep scan T1.53).

### Audit (R8)

- [x] `AuditClient.write` accepts `RegBiDocument | GenerationSkipped`.
- [x] `InMemoryAuditClient` exposes `records_docs` and `records_skips`.
- [x] SKIP paths write audit (coverage). T1.31a.
- [x] `AuditWriteFailed(reason="audit_write_failed")`. T1.25.

### Public API (R11)

- [x] All 49 symbols listed in R11 re-exported from
      `gap1_reg_bi_doc_generator/__init__.py`. T1.32.
- [x] Top-level `compliance/__init__.py` re-exports alongside Gap 2 +
      Gap 6.

---

## Traceability — Unit + Integration Coverage

| Spec AC | Tests |
|---------|-------|
| R1.1 (triggers) | T1.1, T1.20 |
| R1.2 (GenerationInput shape) | T1.4, T1.27 |
| R1.3 (research_brief \| order required) | T1.4 |
| R2.1 (ApplicabilityResult enum) | T1.3, T1.21 |
| R2.2–2.3 (precedence ladder) | T1.6, T1.7 |
| R3.0–R3.8 (OPA matrix) | T1.34–T1.38 |
| R3.9 (F4 Rego-path shape) | T1.36a |
| R3a.1 (DISCLOSURE populator) | T1.8 |
| R3a.2 (CARE populator) | T1.9, T1.10 |
| R3a.3 (COI populator) | T1.11, T1.12 |
| R3a.4 (COMPLIANCE populator) | T1.13, T1.14 |
| R3a.5 (no display_name) | T1.18b |
| R3a.6 (no LLM in populators) | T1.22 |
| R3b (canonical disclosures) | T1.39, T1.40 |
| R4.1–R4.3 (narrative stubs) | T1.15, T1.16 |
| R4.4 (FakeLLM) | I3, I4 |
| R4.5 (LLM failure degrades) | T1.23 |
| R4.6 (PII scrub post-stitch) | T1.24 |
| R4.7 (narrative_model from config) | T1.51, T1.52 |
| R4b.1–R4b.4 (MNPI preflight) | T1.41, T1.41a, T1.42, T1.42b, I3 |
| R5.1 (no creds / I/O) | T1.22, T1.53 |
| R5.2 (scrub patterns) | T1.5, T1.31 |
| R5.3 (no Client PII) | T1.18 |
| R5.4 (extra=forbid) | T1.27 |
| R5b (renderer) | T1.46, T1.46b, T1.46c, T1.46d |
| R6 (RegBiDocument) | T1.19, T1.19b, T1.27, T1.30 |
| R7 (generator flow) | T1.20, T1.21, T1.23, T1.25, T1.26, T1.28, T1.29, T1.29b, T1.30b, T1.47, T1.48, I1, I2 |
| R7.1a (smarsh precondition) | T1.45a |
| R8 (audit) | T1.25, T1.26, T1.31a, T1.31b |
| R9 (principal queue) | T1.47, T1.48, T1.49, T1.50 |
| R10 (smarsh) | T1.43, T1.44, T1.45, T1.45a |
| R11 (public API) | T1.32 |
| R12 (module boundary) | T1.22 |
| Integration | I1, I2, I3, I4, I5 |

Coverage: every R1..R12 AC mapped to at least one test. OK.

---

## Steering-rule Compliance

- ✅ Rule 4 — All compliance decisions are deterministic Python +
  (future) Rego (matrix shape ready). LLM is cosmetic.
- ✅ Rule 5 — No SAR data in Gap 1 (cross-ref; Gap 4 is the SAR owner).
- ✅ Rule 6 — M10 audit emission wired via Protocol; every generate path
  (including SKIP_*) writes audit.
- ✅ Rule 7 — M4 MNPI preflight runs BEFORE every LLM call. Fail-closed.
- ✅ Rule 8 — Fail-closed: audit / Smarsh failures raise; MNPI /
  narrative failures degrade + force advisor review.
- ✅ Rule 9 — Module boundary respected (AST-scan T1.22).
- ✅ Rule 14 — No LLM for compliance decisions.
- ✅ Rule 15 — `narrative_model` swappable via M5 config.
- ✅ Rule 17 — Principal review queue (FINRA 2210) implemented with
  pre_use / post_use semantics.
- ✅ Rule 18 — Smarsh archive hook interface shipped; gated to BD/dual.
- ✅ Rule 19 — Every OPA matrix rule has a `wsp_section` annotation
  (build-time assert + T1.36).

---

## Files Delivered

### Source (`src/compliance/gap1_reg_bi_doc_generator/`)

- `__init__.py` (modified — extended re-exports)
- `_types.py` (preserved from v2)
- `applicability.py` (preserved from v2)
- `audit_client.py` (modified — accepts GenerationSkipped too)
- `disclosures.py` (new — 7 canonical disclosure types)
- `document.py` (modified — schema 1.1.0 + 8 new fields + ProductType + with_rendered_hash)
- `generator.py` (rewritten — R7.3 flow: resolver → populators → disclosures → mnpi → narrative → renderer → queue/smarsh/audit)
- `mnpi_preflight.py` (new — M4 MNPI Protocol + RegexMnpiFilter)
- `narrative.py` (modified — added FakeLLMNarrativeClient)
- `obligations.py` (rewritten — preserved populators + added OPA matrix + resolver)
- `principal_queue.py` (new — FINRA 2210 queue Protocol)
- `renderer.py` (new — deterministic HTML renderer)
- `smarsh_hook.py` (new — Smarsh archive Protocol)

### Tests

- `tests/unit/test_gap1_reg_bi_doc_generator.py` (new — 86 unit tests)
- `tests/integration/test_gap1_end_to_end.py` (new — 5 integration tests)

### Updated top-level

- `src/compliance/__init__.py` (extended re-exports for Gap 1 v3)

### This marker

- `.kiro/specs/gap1-reg-bi-doc-generator-COMPLETE.md`
