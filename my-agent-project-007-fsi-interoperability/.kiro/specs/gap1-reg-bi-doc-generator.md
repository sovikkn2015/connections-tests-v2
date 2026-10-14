# Gap 1 — Reg BI Doc Generator — Spec (v3, Phase-3 BD)

> Sub-module: Gap 1 Reg BI Doc Generator
> Parent module: M10 (Audit Logger)
> Phase: 2–3 (Phase-3 BD onboarding closure)
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 §1 (Gap 1), ARCH-09, 007-consolidated §Part 9,
>   IMPL-06.
> Related: M5 `RegBiConfig` + `PrincipalReviewConfig`, M3 `Client / Order /
>   ResearchBrief`, M1 `AidClaims`, M10 `AuditLogger` (Phase 3), M4
>   `MnpiPolicy` (preflight gate before any LLM call), M2 authority rules
>   (OPA matrix for required sections).
> Status: **v3 (post-LLMJ-v1)** — addresses F1..F15 from the v1 review
>   of v3. Supersets v2 (8.7 GO) with the Phase-3 deliverables:
>   canonical disclosure types, OPA-style required-sections matrix,
>   M4 MNPI preflight on LLM path, deterministic PDF/HTML renderer with
>   content hash, principal review queue emission (pre_use vs post_use),
>   Smarsh archive hook (interface only), M10 audit emission from every
>   generation path. Changes tracked in §6, §7 (review-fix traceability).

---

## 0. CONTEXT AND SCOPE

### 0.1 What Gap 1 is

Gap 1 is the **deterministic Reg BI Recommendation Disclosure** assembler
(SEC 17 CFR §240.15l-1). It produces one immutable document per
recommendation event, rendered to both canonical JSON and HTML, hashed,
queued for principal review (FINRA 2210) when required, handed to the
Smarsh archive hook, and written to the M10 audit tier.

### 0.2 Classification vs narrative — the OPA/LLM split

Reg BI has two categories. Gap 1 treats them differently:

| Category        | Source                                             | Engine                   |
|-----------------|----------------------------------------------------|--------------------------|
| Classification  | applicability, required-sections matrix, bullets   | **Deterministic Python** |
| Narrative       | "basis for recommendation" prose                   | LLM (Haiku by default)   |

Steering rule 5 and rule 14 are honoured: **no LLM makes a compliance
decision.** The LLM only stitches the already-populated bullets into
English prose. A failed / PII-leaking / MNPI-leaking LLM call degrades
to empty narrative + forced `advisor_review_required=True`. The bullets
stand on their own as a complete Reg BI record.

### 0.3 Required-sections matrix (NEW v3)

For every APPLICABLE input the generator derives a required-sections
matrix keyed by `(archetype, account_type, product_type)`. The matrix
is implemented as a **deterministic OPA-style rule table in Python**
(`obligations.py::REQUIRED_SECTIONS_MATRIX`) ready for Phase-2 lift to
Rego. Every entry carries:

- `rule_applied` — `reg_bi/matrix/{archetype}.v{N}` path
- `wsp_section` — firm WSP reference (steering rule 19)
- required canonical disclosure types (subset of the 7 in §0.4)
- the 4 Reg BI obligations that must be populated

Default: all four obligations are ALWAYS required; archetype- /
account-type- / product-type-specific rules only ADD canonical
disclosure types on top (see R3).

### 0.4 Canonical disclosure types (NEW v3)

Seven first-class disclosure types, each a frozen Pydantic model, each
emitted into the document as a typed field (not a free-text bullet):

1. **`conflict_inventory`** — typed list of `ConflictEntry` (from M5).
2. **`best_interest_rationale`** — typed record: objectives-alignment,
   risk-alignment, time-horizon-alignment, summary (1-paragraph prose
   slot, LLM-optional).
3. **`fees_and_compensation`** — typed list of fee items (source, type,
   amount, basis).
4. **`product_scope`** — enum summarising which product universes the
   firm offers (proprietary, affiliated, third-party, captive).
5. **`monitoring_frequency`** — scheduled review cadence for the
   recommendation (`"none" | "quarterly" | "semi_annual" | "annual" |
   "event_driven"`).
6. **`discipline_history_link`** — stable URL to Form CRS / IAPD /
   BrokerCheck disciplinary history page. String, URL-shaped.
7. **`limitations`** — free-list of declared limitations (license,
   product scope, account-minimum, geographic, etc.).

All seven are always present in the document; empty-but-present is
valid for `limitations` and `discipline_history_link` (= `""`).

### 0.5 M4 MNPI preflight (NEW v3, steering rule 7)

Before any LLM call, every bullet and every structured field fed to the
narrative client passes through the injected M4 MNPI filter interface
(Protocol `MnpiFilter`). Fail-closed:

- Any filter error, exception, or scrub-changed return → narrative
  ABORTED, empty string substituted, `advisor_review_required=True`,
  `llm_narrative_failed=True`, audit tag
  `"mnpi_preflight_failed"` recorded on the section.
- The filter is invoked **once per section**, on the tuple of bullets
  handed to `stitch()`. Test T1.41 / T1.42 lock this.

### 0.6 Principal review queue (NEW v3, steering rule 17)

When `PrincipalReviewConfig.mode == pre_use`, the document is emitted
to the principal review queue BEFORE being returned to the caller;
when `post_use`, AFTER. In both modes, the queue entry is emitted
unconditionally when the advisor/principal review gate evaluates True
and the firm is `bd_only` or `dual_registered` (RIA-only firms do not
hit FINRA 2210 and do not queue).

Queue entry shape (R9): immutable `PrincipalReviewQueueEntry` with
doc ref, firm_id, retail/institutional classification (deterministic
via `OpaRequirementsResolver` → steering rule 17), SLA hours, timeout
action. **SAR / anti-tipping-off**: the queue ONLY receives compliance-
officer-routable records; advisor bodies never see the
`advisor_review_required` flag on their own records (steering rule 5).

Queue emission is via an injected Protocol `PrincipalReviewQueue`; the
actual queue bus (SQS / Kafka) is a separate module.

### 0.7 Smarsh archive hook (NEW v3, steering rule 18, interface only)

Before BD deploy, every Reg BI communication must be archived to
Smarsh. Gap 1 exposes a Protocol `SmarshArchiveClient` with a single
`archive(document, rendered_html, rendered_hash)` method. The actual
Smarsh adapter is `src/m11_rest_adapters/smarsh_archive/` (separate
task — Phase 3). Gap 1 ships the interface + an `InMemorySmarshClient`
stub.

Fail-closed: Smarsh archive failure raises `SmarshArchiveFailed` (same
pattern as `AuditWriteFailed`). Tests T1.43..T1.45 lock this.

### 0.8 Deterministic PDF/HTML renderer (NEW v3)

Phase-3 ships a minimal **deterministic HTML renderer** —
`DocumentRenderer.render_html(document) -> RenderedDocument`:

- Input: frozen `RegBiDocument`.
- Output: `RenderedDocument(content_type, body, content_sha256)`.
- `content_type`: `"text/html"` (Phase 3) or `"application/pdf"`
  (Phase 4 stub only; raises `RendererNotImplemented` in Phase 3).
- `content_sha256`: SHA-256 hex of the rendered body bytes.
- Deterministic: identical document → byte-identical body → identical
  hash. Golden-hex test T1.46 locks.
- No Jinja, no templating libraries — pure Python string-escape +
  section iteration. (Jinja integration deferred to Phase 4; this
  renderer is the wire-format Smarsh archives and principal review
  queue consume.)

PDF is stubbed only: `render_pdf` raises `RendererNotImplemented`.

### 0.9 M10 audit emission (steering rule 6)

Every generation path emits to M10 audit tier, both the APPLICABLE
path (success or propagated error) and the SKIP_* paths (for coverage
logs). Done via the injected `AuditClient` Protocol. Verified by
T1.25 + T1.26 + T1.31a.

### 0.10 Non-goals

- NO Jinja templates in Phase 3 (deferred to Phase 4).
- NO actual Smarsh connector — interface only. Connector is a separate
  M11-REST module.
- NO actual OPA/Rego bundle for Gap 1 — the matrix is deterministic
  Python. (Phase 4 may lift selected rules to Rego.)
- NO DLQ for audit failures — caller retries.
- NO dedupe of documents — caller responsibility.
- NO actual LLM SDK dependency — Bedrock client injected by the hosting
  service via `NarrativeClient` Protocol (same decoupling as M8/M9).

### 0.11 Directory layout

```
src/compliance/gap1_reg_bi_doc_generator/
  __init__.py                 # public API
  _types.py                   # enums + error vocabulary
  applicability.py            # applicability gate (R2)
  disclosures.py              # 7 canonical disclosure types (R3b)
  obligations.py              # 4 obligation populators + matrix (R3)
  narrative.py                # NarrativeClient Protocol + stubs (R4)
  mnpi_preflight.py           # MnpiFilter Protocol + stubs (R4b)
  document.py                 # GenerationInput, RegBiDocument,
                              #   canonical JSON + hash (R6)
  renderer.py                 # DocumentRenderer + RenderedDocument (R5b)
  principal_queue.py          # PrincipalReviewQueue Protocol + entry (R9)
  smarsh_hook.py              # SmarshArchiveClient Protocol + stub (R10)
  audit_client.py             # AuditClient Protocol + stub (R8)
  generator.py                # RegBiDocGenerator orchestrator (R7)
```

### 0.12 Allowed imports (per-file; AST-scan T1.22)

- stdlib: `__future__`, `datetime`, `enum`, `hashlib`, `html`, `json`,
  `re`, `typing`, `uuid`
- `pydantic`
- `m3_schema_registry` (`Client`, `Order`, `ResearchBrief`, `AccountType`)
- `m5_config_loader` (`RegBiConfig`, `ConflictEntry`,
  `RegistrationType`, `Archetype`, `PrincipalReviewConfig`,
  `PrincipalReviewMode`, `TimeoutAction`)
- `m1_identity` (`AidClaims`, `Role`)

FORBIDDEN: `m2_m4_policy_engine` (we bind via Protocol — avoids the
cross-module import ban of steering rule 9), `m6_mcp_gateway`, `m7_*`,
`m8_*`, `m9_*`, `m10_audit_logger`, `m11_*`, `m12_*`. No LLM SDKs
(`anthropic`, `openai`, `boto3`, `httpx`, `requests`). No filesystem
I/O. No network I/O.

Cross-cutting note: M4 `MnpiPolicy` from `m2_m4_policy_engine` is NOT
imported; the hosting service wires it in via the `MnpiFilter`
Protocol. This keeps Gap 1 self-contained and AST-scannable.

### 0.13 Threading

Pure data + frozen Pydantic + injected stateless stubs → thread-safe.
All collections returned to callers are `tuple[...]`.

### 0.14 Line budget (Phase 2–3)

| File                    | Target  | Notes                        |
|-------------------------|---------|------------------------------|
| `_types.py`             | ~90     | enums + errors               |
| `applicability.py`      | ~90     | precedence ladder            |
| `disclosures.py`        | ~160    | 7 canonical disclosure types |
| `obligations.py`        | ~340    | 4 populators + matrix        |
| `narrative.py`          | ~110    | Protocol + 2 stubs           |
| `mnpi_preflight.py`     | ~110    | Protocol + 2 stubs           |
| `document.py`           | ~220    | doc + canonical JSON + PII   |
| `renderer.py`           | ~190    | HTML + hash + PDF stub       |
| `principal_queue.py`    | ~140    | Protocol + entry + resolver  |
| `smarsh_hook.py`        | ~80     | Protocol + stub              |
| `audit_client.py`       | ~70     | Protocol + stub              |
| `generator.py`          | ~280    | orchestrator                 |
| `__init__.py`           | ~80     | public API re-exports        |
| **Python total**        | ~1,960  |                              |
| Unit tests              | ~900    | ≥30 test funcs               |
| Integration tests       | ~250    | ≥5 test funcs                |

Target ARCH-06 ~1,100 LoC overshoots intentionally — the Phase-3
additions (renderer, principal queue, Smarsh hook, disclosures,
MNPI preflight) add ~860 LoC; the v2 core stays ~800. Tests grow
accordingly.

---

## 1. REQUIREMENTS

### R1. Trigger events and inputs

**R1.1** `TriggerEventType` enum — exactly 3 members:

| value                     | canonical source                                |
|---------------------------|-------------------------------------------------|
| `recommendation.draft`    | Client Service Specialist recommendation event  |
| `research.rating_issued`  | ResearchBrief with non-null rating              |
| `order.drafted_retail`    | Order status=DRAFT, retail client               |

Unknown trigger string passed to any helper → `UnsupportedTriggerError`.

**R1.2** `GenerationInput` frozen Pydantic (`ConfigDict(frozen=True,
extra="forbid")`):

- `trigger: TriggerEventType`
- `trace_id: str` (1..200)
- `generated_at: datetime` (tz-aware UTC; naive → ValueError;
  stored as `.astimezone(timezone.utc)`)
- `client: Client`
- `advisor: AidClaims`
- `research_brief: ResearchBrief | None`
- `order: Order | None`
- `reason_trace: tuple[str, ...]` (≤50 items; each ≤500 chars
  POST-scrub)
- `config: RegBiConfig`
- `principal_review_config: PrincipalReviewConfig | None = None`
  (when None and registration_type ∈ {bd_only, dual_registered},
  principal review queue is NOT emitted; warning allowed via R9.4)
- `product_type: ProductType | None = None` — `ProductType` is a
  `str, Enum` with members {mutual_fund, etf, equity, option,
  annuity, private}; used by the required-sections matrix (R3).
  Validator rejects unknown strings.

`firm_registration_type` NOT included — sourced from
`advisor.registration_type`.

**R1.3** At least one of `research_brief` / `order` MUST be non-None.
Neither → `ValueError("at least one of research_brief / order required")`.

### R2. Applicability gate

**R2.1** `ApplicabilityResult` enum — exactly 4 members:
- `APPLICABLE`
- `SKIP_RIA`
- `SKIP_INSTITUTIONAL`
- `SKIP_AUTO_DISABLED`

**R2.2** `evaluate_applicability(inp) -> ApplicabilityResult` is
deterministic. No I/O. No clock. No randomness.

**R2.3 Precedence ladder** — first match wins:
1. `inp.config.auto_generate == False` → `SKIP_AUTO_DISABLED`
2. `inp.advisor.registration_type == RegistrationType.ria_only`
   → `SKIP_RIA`
3. `inp.client.client_type in {"entity", "trust"}` → `SKIP_INSTITUTIONAL`
4. else → `APPLICABLE`

### R3. OPA-style required-sections matrix (NEW v3)

**R3.0** Intent: the required-sections matrix is the OPA/Rego rule set
for Gap 1. Each row has `rule_applied`, `wsp_section`, and a
deterministic predicate on `(archetype, account_type, product_type)`.

Phase 3 runs the matrix in Python; Phase 4 lifts to Rego.

**R3.1 Matrix schema** — tuple of frozen `RequiredSectionsRule`:
- `rule_applied: str` matching
  `^reg_bi/matrix/[a-z0-9_]+\.v[1-9]\d*$`
- `wsp_section: str` (e.g. `"WSP-REGBI-2.1"`)
- `applies_when: RequiredSectionsPredicate` — frozen Pydantic with
  optional `archetype`, optional `account_type`, optional
  `product_type` (all `None` = wildcard)
- `adds_disclosures: frozenset[str]` — subset of the 7 canonical
  disclosure-type names
- `severity: Literal["ADD", "BLOCK"] = "ADD"` — Phase 3 is ADD-only;
  BLOCK is reserved for Phase 4 archetype-incompatible combos

**R3.2 Base matrix (always emitted regardless of archetype):**

| rule_applied                               | wsp_section     | adds_disclosures                                                                                             |
|--------------------------------------------|-----------------|--------------------------------------------------------------------------------------------------------------|
| `reg_bi/matrix/base.v1`                    | `WSP-REGBI-1.1` | `conflict_inventory`, `best_interest_rationale`, `fees_and_compensation`, `product_scope`, `discipline_history_link`, `limitations` |

**R3.3 Archetype overlays:**

| rule_applied                               | applies_when                      | wsp_section     | adds                   |
|--------------------------------------------|-----------------------------------|-----------------|------------------------|
| `reg_bi/matrix/tier3_broker_dealer.v1`     | archetype=tier3_broker_dealer     | `WSP-REGBI-3.1` | `monitoring_frequency` |
| `reg_bi/matrix/tier4_independent_ria.v1`   | archetype=tier4_independent_ria   | `WSP-REGBI-4.1` | (none — see R3.4)      |

**R3.4** `tier4_independent_ria` with `registration_type=ria_only`
short-circuits at R2.3 step 2 and never reaches the matrix. If
archetype=tier4 but registration_type=dual_registered, the base matrix
applies without the `monitoring_frequency` add. (Edge case tested in
T1.35.)

**R3.5 Account-type overlays** (per Gap 5 contract, pre-integration):

| rule_applied                           | applies_when                  | wsp_section     | adds                       |
|----------------------------------------|-------------------------------|-----------------|----------------------------|
| `reg_bi/matrix/account_ira.v1`         | account_type ∈ {traditional_ira, roth_ira, sep_ira, simple_ira} | `WSP-REGBI-5.1` | `monitoring_frequency`     |
| `reg_bi/matrix/account_401k.v1`        | account_type ∈ {k401, b403}   | `WSP-REGBI-5.2` | `monitoring_frequency`     |

(Full ERISA matrix is Gap 5. Gap 1 handles these four because Reg BI
applies to rollovers from qualified plans per SEC Reg BI Release
34-86031 §III.A.2.)

**R3.6 Product-type overlays:**

| rule_applied                        | applies_when           | wsp_section     | adds          |
|-------------------------------------|------------------------|-----------------|---------------|
| `reg_bi/matrix/product_mf.v1`       | product_type=mutual_fund | `WSP-REGBI-6.1` | (none — base covers) |
| `reg_bi/matrix/product_annuity.v1`  | product_type=annuity   | `WSP-REGBI-6.2` | `monitoring_frequency`, `limitations` |
| `reg_bi/matrix/product_private.v1`  | product_type=private   | `WSP-REGBI-6.3` | `limitations` |

**R3.7** `OpaRequirementsResolver.resolve(inp) -> ResolvedRequirements`
returns the deterministic union of matched rules:

- `matched_rules: tuple[str, ...]` — sorted list of `rule_applied`.
- `matched_wsp_sections: tuple[str, ...]` — sorted list of
  `wsp_section`.
- `required_disclosures: frozenset[str]` — union of `adds_disclosures`.
- `required_obligations: frozenset[ObligationCode]` — always all four
  (DISCLOSURE, CARE, COI, COMPLIANCE); reserved for Phase 4.
- `is_retail: bool` — `True` iff `client.client_type == "individual"`
  (steering rule 17 — principal-review classification is OPA's job).
- `severity: Literal["ADD", "BLOCK"] = "ADD"` — Phase 3 always ADD.

**R3.8** Every rule in the matrix MUST have `wsp_section` filled
(non-empty); build-time assertion at module import. T1.36 locks.

**R3.9** (F4) Every `rule_applied` slash-form maps to a valid Rego
dotted-path: `rule_applied.replace("/", ".")` is the future Rego
package + rule name. Lift-to-Rego contract; tested by T1.36a.

### R3a. Four-obligation populators (v2 requirements preserved)

Each populator returns a `RegBiSection` (frozen Pydantic):
- `obligation_code: ObligationCode` ∈ {DISCLOSURE, CARE, COI, COMPLIANCE}
- `bullets: tuple[str, ...]` (each 1..500 chars post-scrub)
- `narrative: str` (≤2000 chars; may be empty)
- `populated_by: str` matching `POPULATED_BY_RE`
- `force_review: bool`

Populator rules R3a.1..R3a.4 are identical to v2 R3.1..R3.4
(DISCLOSURE ≥3 bullets, CARE ≥4, COI ≥1, COMPLIANCE ≥2). `populated_by`
emits `v1` in Phase 3; versioning is per-obligation (v2 F4).

Min-bullet floor breach → `InsufficientBulletsError` (hard raise).
Max-bullet overflow → silent trim (newest dropped).

**R3a.5 No `client.display_name` in bullets/narrative** (v2 F3).
Populators use `"the client"` / `"the household"`.

**R3a.6 No LLM in populators** (steering rule 14; AST-scan T1.22).

### R3b. Seven canonical disclosure types

See §0.4. Each is a frozen Pydantic model living in `disclosures.py`:

- `ConflictInventoryDisclosure(entries: tuple[ConflictEntry, ...])`
- `BestInterestRationale(objectives_alignment: str, risk_alignment:
  str, time_horizon_alignment: str, summary: str = "")`
- `FeesAndCompensation(items: tuple[FeeItem, ...])` where
  `FeeItem(source: str, fee_type: str, amount: float | None,
  basis: str, description: str)`
- `ProductScope(scope: Literal["proprietary", "affiliated",
  "third_party", "captive", "mixed"])`
- `MonitoringFrequency(cadence: Literal["none", "quarterly",
  "semi_annual", "annual", "event_driven"])`
- `DisciplineHistoryLink(url: str)` — URL-shaped; empty allowed but
  typed.
- `Limitations(entries: tuple[str, ...])` — ≤20 strings, each ≤200
  chars.

All seven models are `frozen=True, extra="forbid"`.

**R3b.1 `CanonicalDisclosures` container** (F15):

```python
class CanonicalDisclosures(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    conflict_inventory: ConflictInventoryDisclosure
    best_interest_rationale: BestInterestRationale
    fees_and_compensation: FeesAndCompensation
    product_scope: ProductScope
    monitoring_frequency: MonitoringFrequency
    discipline_history_link: DisciplineHistoryLink
    limitations: Limitations
```

This is the single nested field on `RegBiDocument`.

`populate_disclosures(inp, resolved) -> CanonicalDisclosures` builds
the full set. Populators are deterministic. Sources:
- `conflict_inventory` ← `config.conflict_inventory`.
- `best_interest_rationale` ← deterministic join of risk tolerance +
  objectives + time horizon from Client; `summary` left empty for
  narrative stitching.
- `fees_and_compensation` ← commission from order if present; future
  hook for TaxLot-level fees.
- `product_scope` ← deterministic default `"mixed"` unless firm
  specifies (hook for Phase-4 enterprise config).
- `monitoring_frequency` ← `"annual"` default; `"event_driven"` for
  annuity/private.
- `discipline_history_link` ← URL built from `AidClaims.firm_id` + a
  stable template (`https://adviserinfo.sec.gov/firm/summary/{firm_id}`);
  validated URL-shaped.
- `limitations` ← base `["Recommendation scope limited to in-scope
  products and firm-licensed jurisdictions."]` plus product overlays.

### R4. Narrative layer (LLM, OPTIONAL)

**R4.1** `NarrativeClient` Protocol:
```python
@runtime_checkable
class NarrativeClient(Protocol):
    def stitch(
        self,
        *,
        obligation: ObligationCode,
        bullets: tuple[str, ...],
        reason_trace: tuple[str, ...],
    ) -> str: ...
```

**R4.2** `StubNarrativeClient`: always returns `""`. Phase-2/3 default
when `RegBiConfig.narrative_model == "none"`.

**R4.3** `BulletConcatNarrativeClient`: deterministic, no LLM.
`"; ".join(bullets)[:2000]`.

**R4.4** `FakeLLMNarrativeClient` (NEW v3, tests only): deterministic
canned responses keyed by `(obligation, bullets_hash)`; used by
integration tests to avoid wiring a real Bedrock SDK.

**R4.5 LLM failure handling.** If injected client's `stitch()` raises
(any exception type):
- Generator catches.
- Replaces narrative with `""` for that section.
- Sets `document.llm_narrative_failed = True`.
- Sets `document.advisor_review_required = True` (forced).
- NEVER re-raises.

**R4.6 Narrative PII scrub.** After `stitch()` returns, apply
`_scrub_pii`. If scrub CHANGED the string (PII was found):
- Replace narrative with `""`.
- Set `advisor_review_required = True`.
- Set `llm_narrative_failed = True`.

**R4.7 narrative_model sourced from config** (steering rule 15).
`inp.config.narrative_model` (default `"haiku"`) is recorded in
`document.narrative_model_configured` for audit. The field records
**configured intent**, not the wired client class; a hosting service
that wires a real Haiku Bedrock client on top of `"haiku"` config is
consistent with the field. T1.51b locks this semantic.

Real client resolution lives in the hosting service; Gap 1's stub
default is:
- `config.narrative_model == "none"` → `StubNarrativeClient`
- else (including `"haiku"`, `"sonnet"`) → `BulletConcatNarrativeClient`
  (until a real client is injected).

This keeps Gap 1 self-contained while honouring the M5 config.

### R4b. M4 MNPI preflight (NEW v3, steering rule 7)

**R4b.1** `MnpiFilter` Protocol:
```python
@runtime_checkable
class MnpiFilter(Protocol):
    def preflight(
        self,
        *,
        bullets: tuple[str, ...],
        claims: AidClaims,
    ) -> MnpiPreflightResult: ...
```

`MnpiPreflightResult` frozen Pydantic:
- `passed: bool`
- `reason: str` (≤200 chars; NO PII)
- `filtered_bullets: tuple[str, ...] = ()` (empty unless passed)

**R4b.2** Two stub implementations:
- `StubMnpiFilter(pass_all=True)` — for unit tests that don't exercise
  the gate.
- `RegexMnpiFilter` — applies the 4 module-local PII patterns. **To
  avoid drift, `mnpi_preflight.py` imports `_PII_PATTERNS` from
  `document.py`** (F6); having a single source of truth is tested by
  T1.41a.  Scrub-changed ⇒ FAIL. No LLM. Used as Phase-3 default when
  no `m2_m4_policy_engine.MnpiPolicy` is wired in.

**R4b.3 Preflight invocation.** Before EVERY call to
`NarrativeClient.stitch`:

1. Call `mnpi_filter.preflight(bullets=sec.bullets,
   claims=inp.advisor)`.
2. If `passed=False` OR filter raises → ABORT narrative for that
   section. Record section-level flag `mnpi_preflight_failed=True`.
   Set `advisor_review_required=True`. Do NOT call `stitch()`. This is
   the fail-closed gate (steering rule 8).
3. If `passed=True` → pass `filtered_bullets` (if non-empty) or
   `bullets` to stitch.

**R4b.4** `mnpi_preflight_failed` bool recorded per-section and
aggregated on the document as `any_mnpi_preflight_failed`.

### R5. Security + PII

**R5.1** No credentials in source. No network I/O. No filesystem I/O.
CI check via AST-scan T1.22 + grep test T1.47.

**R5.2 `_scrub_pii`** — same four patterns as Gap 2 + Gap 6:
- SSN dashed: `\b\d{3}-\d{2}-\d{4}\b`
- Account 12+ digits: `\b\d{12,}\b`
- Email: `\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b`
- IBAN: `\b[A-Z]{2}\d{2}[A-Z0-9]{11,30}\b`

Each match replaced with `REDACTION_TOKEN = "[REDACTED]"`.
Deterministic. Idempotent.

Applied at 4 checkpoints:
1. `reason_trace` field validator (GenerationInput).
2. Each bullet at populator finalize.
3. Each narrative post-stitch.
4. HTML renderer escape + scrub on every cell.

**R5.3 No Client PII leak.** `Client.email`, `date_of_birth`,
`ssn_last_four`, `tax_id` NEVER read by populators or renderer. T1.18
locks.

**R5.4** `extra="forbid"` on every Pydantic model. T1.27 locks.

### R5b. Deterministic HTML renderer

**R5b.1** `DocumentRenderer.render_html(document) -> RenderedDocument`:

- Pure-Python string assembly. `html.escape(..., quote=True)` on every
  variable.
- Section ordering fixed: header → applicability trace → 4 obligations
  (DISCLOSURE, CARE, COI, COMPLIANCE) → 7 canonical disclosures →
  signatures block.
- UTF-8 encoded. `content_sha256 = sha256(body.encode("utf-8"))
  .hexdigest()`.
- Deterministic: 2 calls on same document → byte-identical body.

**R5b.2** `RenderedDocument` frozen Pydantic:
- `content_type: Literal["text/html", "application/pdf"]`
- `body: bytes` (max 2 MiB)
- `content_sha256: str` (64 hex chars)
- `rendered_at: datetime` tz-aware — injected factory default is
  `inp.generated_at` to keep determinism.

**R5b.3** `render_pdf(document)` raises
`RendererNotImplemented("pdf_deferred_phase4")` until the PDF path is
wired. Reserved for Phase 4.

### R6. RegBiDocument (v2 fields preserved + v3 additions)

**R6.1** Frozen Pydantic (`frozen=True, extra="forbid"`):

v2 fields (all retained):
- `document_schema_version: Literal["1.1.0"]` — **bumped from 1.0.0**
- `document_id: UUID`
- `trace_id: str` (1..200)
- `generated_at: datetime` (tz-aware UTC)
- `trigger: TriggerEventType`
- `client_ref: UUID` (from `Client.canonical_id`)
- `advisor_sub: str` (from `AidClaims.sub`, 1..128)
- `firm_id: str` (from `AidClaims.firm_id`, 1..128)
- `registration_type: RegistrationType`
- `disclosure: RegBiSection`
- `care: RegBiSection`
- `coi: RegBiSection`
- `compliance: RegBiSection`
- `advisor_review_required: bool`
- `llm_narrative_failed: bool = False`
- `reason_trace_redacted: tuple[str, ...]`
- `research_brief_ref: UUID | None = None`
- `order_ref: UUID | None = None`
- `liability_report_sha256: str | None = None`

v3 additions:
- `canonical_disclosures: CanonicalDisclosures` — the 7-type record.
- `matched_rules: tuple[str, ...]` — sorted rule_applied list.
- `matched_wsp_sections: tuple[str, ...]` — sorted wsp list.
- `required_disclosures: tuple[str, ...]` — sorted list of required
  disclosure-type names.
- `is_retail: bool` — from OpaRequirementsResolver. (F7) Duplicated
  onto the document so FINRA-examiner retrieval does not require
  re-running the resolver; the resolver output is the source of truth
  and the document field just surfaces it.
- `narrative_model_configured: str` — echoes `config.narrative_model`.
  Records CONFIGURED intent (F5), not the wired client class.
- `any_mnpi_preflight_failed: bool = False`
- `rendered_content_sha256: str | None = None` — filled if renderer
  emitted a rendition before doc finalization; `None` otherwise.

**R6.2 Canonical JSON** — identical contract to Gap 2:
- `model.model_dump(mode="json", exclude_none=False)`.
- `json.dumps(data, sort_keys=True, separators=(",", ":"),
  default=_json_default)`.

**R6.3** `sha256_digest()` — SHA-256 hex of canonical JSON.

**R6.4 Deterministic.** Same inputs (plus injected deterministic
factory) → byte-identical JSON.

**R6.5 Golden hex.** T1.19 locks bootstrap digest.

### R7. RegBiDocGenerator

**R7.1** Class signature:
```python
class RegBiDocGenerator:
    def __init__(
        self,
        *,
        narrative_client: NarrativeClient | None = None,
        audit_client: AuditClient | None = None,
        mnpi_filter: MnpiFilter | None = None,
        principal_queue: PrincipalReviewQueue | None = None,
        smarsh_client: SmarshArchiveClient | None = None,
        renderer: DocumentRenderer | None = None,
        requirements_resolver: OpaRequirementsResolver | None = None,
        document_id_factory: Callable[[], UUID] = uuid4,
    ) -> None: ...

    def generate(
        self, inp: GenerationInput
    ) -> RegBiDocument | GenerationSkipped: ...
```

**R7.1a** `__init__` preconditions (F2 applied):
- If `smarsh_client is not None` and `renderer is None` → raise
  `ValueError("smarsh_requires_renderer")`. Rationale: Smarsh archive
  wire-format is the rendered body + hash; without a renderer, the
  archive is incomplete.

**R7.1b** All dependencies default to safe in-memory / deterministic
stubs (or `None`) so the class is constructible without args in tests.

**R7.2** `GenerationSkipped` frozen Pydantic:
- `reason: ApplicabilityResult` (one of SKIP_*)
- `trace_id: str`
- `trigger: TriggerEventType`
- Rejects `APPLICABLE` as a reason with ValidationError.

SKIP path STILL calls `audit_client.write(skipped)` if wired — we
record the skip (coverage per R7.3 step 2a).

**R7.3 Flow** (F1 + F9 applied — render first, then doc, then
rendered-hash-bound doc; principal queue AFTER audit in both modes).

1. Evaluate applicability (R2).
2. If SKIP_*:
   2a. Build `GenerationSkipped`.
   2b. If `audit_client` wired → write the skip record. Audit failure
       on SKIP path ALSO raises `AuditWriteFailed` (fail-closed,
       consistent with doc path — F3).
   2c. Return `GenerationSkipped`.
3. Resolve required sections via `OpaRequirementsResolver`.
4. Build 4 obligations (populators; may raise
   `InsufficientBulletsError` — propagate).
5. Build 7 canonical disclosures (populators; deterministic).
6. For each obligation section:
   6a. Call `mnpi_filter.preflight(bullets, claims)`. On fail / raise:
       narrative = `""`, section flag `mnpi_preflight_failed=True`,
       SKIP stitch.
   6b. Else call `narrative_client.stitch(...)`. On exception:
       `llm_narrative_failed=True`, narrative = `""`.
   6c. PII-scrub narrative. If changed: narrative = `""`, flags set.
7. Mint UUID via `document_id_factory()`.
8. Build **provisional** `RegBiDocument` (no
   `rendered_content_sha256` yet).
9. Compute `advisor_review_required` (R7.5) on the provisional doc.
10. If `renderer` wired: `rendered = renderer.render_html(doc)` →
    rebuild `doc = doc.with_rendered_hash(rendered.content_sha256)`
    (immutable copy-with-update). Else `rendered = None`.
11. If `smarsh_client` wired AND `registration_type in {bd_only,
    dual_registered}`: `smarsh_client.archive(document=doc,
    rendered=rendered)`. Failure raises `SmarshArchiveFailed`.
    `smarsh_client` wired without `renderer` → raise
    `ValueError("smarsh_requires_renderer")` at `__init__` (F2).
12. `audit_client.write(doc)`. Failure raises `AuditWriteFailed`.
13. If `principal_queue` wired AND `registration_type != ria_only`
    AND `advisor_review_required == True` AND
    `principal_review_config` non-None → `principal_queue.enqueue(
    entry)`. Mode (pre_use / post_use) is recorded on the entry and
    is semantic for the consumer (F9 — it refers to "pre-use of the
    communication with the public", NOT to audit ordering). Queue
    enqueue is ALWAYS after audit in the wall-clock lifecycle.
14. Return the final `RegBiDocument`.

**R7.4** Audit / Smarsh / MNPI-preflight-exception during config
resolution are the three raise paths. Everything else degrades.

**R7.5 advisor_review_required.** Gate precedence (OR'd):
```
require_advisor_review (firm FLOOR — True always wins)
 OR client.risk_tolerance is None
 OR llm_narrative_failed
 OR any_mnpi_preflight_failed
 OR any section.force_review
 OR any reason_trace entry startswith "REVIEW:"
```

### R8. AuditClient Protocol (v2, expanded v3)

**R8.1** Protocol:
```python
@runtime_checkable
class AuditClient(Protocol):
    def write(
        self,
        record: RegBiDocument | GenerationSkipped,
    ) -> None: ...
```

Fire-and-forget; caller owns dedupe.

**R8.2** `InMemoryAuditClient` stub — appends each write to a list.
Separate `records_docs` and `records_skips` properties for ease of
inspection.

**R8.3** `AuditWriteFailed(RuntimeError)`:
- `reason: str` ∈ `{"audit_write_failed"}`.
- `str(exc) == exc.reason`. No PII, no stack string.

### R9. PrincipalReviewQueue (NEW v3, steering rule 17)

**R9.1** `PrincipalReviewQueueEntry` frozen Pydantic:
- `entry_id: UUID`
- `trace_id: str`
- `document_id: UUID`
- `firm_id: str`
- `registration_type: RegistrationType`
- `is_retail: bool` — OPA classifier output
- `mode: PrincipalReviewMode`
- `sla_hours: int`
- `timeout_action: TimeoutAction`
- `rendered_content_sha256: str | None` — optional wire-format hash
- `submitted_at: datetime` (tz-aware UTC)

**R9.2** `PrincipalReviewQueue` Protocol:
```python
@runtime_checkable
class PrincipalReviewQueue(Protocol):
    def enqueue(self, entry: PrincipalReviewQueueEntry) -> None: ...
```

**R9.3** `InMemoryPrincipalReviewQueue` stub — appends to a list.

**R9.4** Firm/mode gating (enqueue preconditions):
- `registration_type in {bd_only, dual_registered}`.
- `principal_review_config` non-None.
- `advisor_review_required == True`.

Otherwise, no enqueue (silent no-op). This keeps RIA-only paths clear
of FINRA 2210 queue entries.

**R9.4a** (F9) The queue enqueue ALWAYS happens AFTER M10 audit write
in the wall-clock lifecycle. The `mode` field on the entry
(`pre_use` / `post_use`) is a FINRA 2210 SEMANTIC — it indicates
whether the principal must review BEFORE COMMUNICATING the recommendation
to the public (`pre_use`) or AFTER (`post_use`). It does NOT control
when Gap 1 calls enqueue; Gap 1 always calls enqueue once, after
audit, carrying the mode for the consumer. T1.47 + T1.48 lock this.

**R9.5 Anti-tipping-off** (steering rule 5 via cross-ref). The queue
entry does NOT include advisor identity-visible fields beyond what is
already in `AidClaims`; it never carries SAR pattern data. SAR routing
is Gap 4's concern. T1.44 verifies the entry shape is bounded.

### R10. SmarshArchiveClient (NEW v3, steering rule 18, interface only)

**R10.1** `SmarshArchiveClient` Protocol:
```python
@runtime_checkable
class SmarshArchiveClient(Protocol):
    def archive(
        self,
        *,
        document: RegBiDocument,
        rendered: RenderedDocument,
    ) -> None: ...
```

**R10.2** `InMemorySmarshClient` stub — appends to a list. Thread-local
avoided; fresh instance per test.

**R10.3** `SmarshArchiveFailed(RuntimeError)`:
- `reason: str` ∈ `{"smarsh_archive_failed"}`.

**R10.4** Gating: generator invokes archive only when
`registration_type in {bd_only, dual_registered}`. RIA-only firms
skip.

### R11. Public API

`gap1_reg_bi_doc_generator/__init__.py` re-exports (at minimum):
```
TriggerEventType, ApplicabilityResult, ObligationCode,
GenerationInput, GenerationSkipped, RegBiSection, RegBiDocument,
RegBiDocGenerator, POPULATED_BY_RE, DOCUMENT_SCHEMA_VERSION,
NarrativeClient, StubNarrativeClient, BulletConcatNarrativeClient,
FakeLLMNarrativeClient,
AuditClient, InMemoryAuditClient, AuditWriteFailed,
MnpiFilter, StubMnpiFilter, RegexMnpiFilter, MnpiPreflightResult,
OpaRequirementsResolver, ResolvedRequirements,
REQUIRED_SECTIONS_MATRIX,
RequiredSectionsRule, RequiredSectionsPredicate,
DocumentRenderer, RenderedDocument, RendererNotImplemented,
PrincipalReviewQueue, InMemoryPrincipalReviewQueue,
PrincipalReviewQueueEntry,
SmarshArchiveClient, InMemorySmarshClient, SmarshArchiveFailed,
ConflictInventoryDisclosure, BestInterestRationale, FeeItem,
FeesAndCompensation, ProductScope, MonitoringFrequency,
DisciplineHistoryLink, Limitations, CanonicalDisclosures,
UnsupportedTriggerError, InsufficientBulletsError,
REDACTION_TOKEN,
```

`src/compliance/__init__.py` re-exports Gap 1 symbols alongside
Gap 2 + Gap 6.

### R12. Module boundary

- IMPORTS: stdlib + pydantic + {`m3_schema_registry`,
  `m5_config_loader`, `m1_identity`}.
- AST-scan T1.22 enforces.

---

## 2. DESIGN

### 2.1 File layout (matches §0.11)

```
src/compliance/gap1_reg_bi_doc_generator/
  __init__.py
  _types.py
  applicability.py
  disclosures.py
  obligations.py
  narrative.py
  mnpi_preflight.py
  document.py
  renderer.py
  principal_queue.py
  smarsh_hook.py
  audit_client.py
  generator.py
tests/unit/
  test_gap1_reg_bi_doc_generator.py
tests/integration/
  test_gap1_end_to_end.py
```

### 2.2 Control-flow sketch (happy path, BD dual-registered)

```
GenerationInput
    │
    ▼
evaluate_applicability → APPLICABLE
    │
    ▼
OpaRequirementsResolver.resolve →
    matched_rules, wsp_sections, required_disclosures, is_retail
    │
    ▼
POPULATORS (4 deterministic) ── may raise InsufficientBulletsError
    │
    ▼
DISCLOSURE_POPULATORS (7 deterministic)
    │
    ▼
for each section:
    MnpiFilter.preflight ── FAIL → narrative="", flags set
    NarrativeClient.stitch ── raise / PII → narrative="", flags set
    │
    ▼
render_html → RenderedDocument (content_sha256 captured)
    │
    ▼
RegBiDocument built
    │
    ▼
advisor_review_required gate applied
    │
    ▼
[principal_queue.enqueue if pre_use + gated]
    │
    ▼
smarsh_client.archive (bd / dual only)
    │
    ▼
audit_client.write(document)
    │
    ▼
[principal_queue.enqueue if post_use + gated]
    │
    ▼
return RegBiDocument
```

### 2.3 Canonical-JSON invariant

The 7 `CanonicalDisclosures` types are nested Pydantic models. They
serialize via `model_dump(mode="json", exclude_none=False)` into
deterministic dicts; `_json_default` handles `Enum` / `datetime` /
`UUID` / `tuple` the same way Gap 2 does.

### 2.4 Security

- `extra="forbid"` on every model.
- 4 PII scrub checkpoints.
- Max-length on every string field.
- HTML renderer uses `html.escape(..., quote=True)` — XSS defence.
- No credentials in source.

### 2.5 Module boundary

stdlib + pydantic + m3/m5/m1 only. AST-enforced.

---

## 3. TASKS

### 3.1 Unit tests (≥30)

#### Base enums / inputs / applicability (v2)

T1.1 — `TriggerEventType` enum: 3 members, values match R1.1.
T1.2 — `ObligationCode` enum: 4 members.
T1.3 — `ApplicabilityResult` enum: 4 members.
T1.4 — `GenerationInput` frozen + extra=forbid; parametrized failures.
T1.5 — `reason_trace` PII scrub at validator; SSN/email masked.
T1.6 — `evaluate_applicability` precedence ladder parametrized (5 cases).
T1.7 — `evaluate_applicability` bd_only + individual → APPLICABLE.

#### Populators (v2)

T1.8 — DISCLOSURE happy path; ≥3 bullets; commission formatted.
T1.9 — CARE happy path; 5 `"alt:"` entries → ≤3 alternatives.
T1.10 — CARE risk_tolerance=None + objectives=[] → force_review=True.
T1.11 — COI 3 entries + commission + dual_registered → ≥5 bullets.
T1.12 — COI empty inventory + bd_only → exactly 1 fallback bullet.
T1.13 — COMPLIANCE anti_fabrication_score 0.8765 → "0.877".
T1.14 — COMPLIANCE require_advisor_review=True → review bullet present.
T1.15 — `StubNarrativeClient.stitch` returns `""`.
T1.16 — `BulletConcatNarrativeClient` 2000-byte cut.
T1.17 — `POPULATED_BY_RE` matches v1/v2, rejects v0/missing.
T1.18 — No PII leak into canonical JSON (SSN, email, tax_id).
T1.18b — `client.display_name` not in any bullet/narrative/HTML.

#### Document + hashing (v2)

T1.19 — **Golden-hex bootstrap procedure** (F8): pinned fixture with
       - `document_id_factory = lambda: UUID("11111111-1111-4111-8111-
         111111111111")`,
       - `generated_at = datetime(2026,1,1, tzinfo=UTC)`,
       - `BulletConcatNarrativeClient`,
       - all stubs wired in a deterministic config. First run asserts
       the computed digest against a constant captured once (Gap 2
       T2.17 template). Golden hex bound to v3 schema (`1.1.0`); any
       field/layout bump breaks this test intentionally.
T1.20 — 3 TriggerEventType values → valid documents.
T1.21 — 4 ApplicabilityResult outcomes parametrized.
T1.22 — AST import-scan: stdlib + pydantic + m1/m3/m5 only.
T1.23 — NarrativeClient raises → `llm_narrative_failed=True`,
        `advisor_review_required=True`, no exception.
T1.24 — NarrativeClient returns email → scrub → narrative="", flags.
T1.25 — AuditClient.write raises → `AuditWriteFailed` with
        `reason="audit_write_failed"`.
T1.26 — AuditClient=None → no sink call; document returned.
T1.27 — `extra="forbid"` on all models (one assert per model).
T1.28 — require_advisor_review=False + all clean → review=False.
T1.29 — require_advisor_review=False + risk_tolerance=None → True.
T1.29b — reason_trace startswith "REVIEW:" → review=True.
T1.30 — schema_version parametrized (accept "1.1.0"; reject "2.0.0"/"").
T1.30b — InsufficientBulletsError propagates (no catch).
T1.31 — `_scrub_pii` idempotence parametrized.
T1.31a — SKIP path calls `audit_client.write(skipped)` (coverage).
T1.32 — Public API exports match R11 (frozen list compare).
T1.33 — `GenerationSkipped(reason=APPLICABLE)` → ValidationError.

#### OPA matrix (NEW v3)

T1.34 — `REQUIRED_SECTIONS_MATRIX` imports cleanly; every rule has
         non-empty `wsp_section` + `rule_applied` matching regex.
T1.35 — `OpaRequirementsResolver.resolve` parametrized over archetype
         × account_type × product_type → expected disclosures + rules.
T1.36 — Build-time assertion: every matrix rule has wsp_section
         (AST parse of `REQUIRED_SECTIONS_MATRIX`).
T1.37 — `is_retail` True for client_type=individual, False for
         entity/trust (but those short-circuit at SKIP, so test is
         on the resolver directly).
T1.38 — `matched_rules` sorted, deduped, stable.

#### Canonical disclosure types (NEW v3)

T1.39 — Each of 7 disclosure types rejects unknown kwargs.
T1.40 — `populate_disclosures` round-trips via canonical JSON.

#### MNPI preflight (NEW v3)

T1.41 — `RegexMnpiFilter.preflight` FAILs on SSN-bearing bullet;
         narrative ABORTED; `any_mnpi_preflight_failed=True`;
         advisor_review_required=True.
T1.42 — `MnpiFilter.preflight` raising → same fail-closed behaviour.
T1.42b — Preflight invoked BEFORE `NarrativeClient.stitch` — spy
         ordering assertion.

#### Smarsh hook (NEW v3)

T1.43 — bd_only firm → Smarsh archive called with document + rendered.
T1.44 — ria_only firm → Smarsh archive NOT called (gated).
T1.45 — Smarsh client raises → `SmarshArchiveFailed("smarsh_archive_failed")`.

#### Renderer (NEW v3)

T1.46 — Golden-hex of `render_html(document).content_sha256`.
T1.46b — `render_html` deterministic across 2 calls.
T1.46c — `render_pdf` raises `RendererNotImplemented`.
T1.46d — HTML body has NO unescaped bullet text (XSS-safe sentinel).

#### Principal review queue (NEW v3)

T1.47 — `pre_use` mode + BD firm + review_required → queue enqueued
         BEFORE audit write (spy ordering).
T1.48 — `post_use` mode + BD firm → queue enqueued AFTER audit write.
T1.49 — ria_only firm → queue NOT enqueued.
T1.50 — review_required=False → queue NOT enqueued.

#### narrative_model sourcing (NEW v3)

T1.51 — `config.narrative_model="haiku"` → `narrative_model_used="haiku"`.
T1.52 — `config.narrative_model="none"` → StubNarrativeClient path,
         narrative strings all empty.

#### No credentials (NEW v3)

T1.53 — grep-scan of src/compliance/gap1_reg_bi_doc_generator for
         `AKIA|aws_secret|sk-|password=` returns no matches.

### 3.2 Integration tests (≥5)

#### test_gap1_end_to_end.py

I1 — End-to-end BD dual-registered APPLICABLE path: input →
      RegBiDocument → InMemoryAuditClient has 1 doc →
      InMemorySmarshClient has 1 archive → InMemoryPrincipalReviewQueue
      has 1 entry → rendered body is valid HTML.

I2 — End-to-end RIA-only path: SKIP_RIA → InMemoryAuditClient has
      1 skip record → no Smarsh → no principal queue.

I3 — End-to-end FakeLLM + MNPI preflight FAIL: narrative aborted on
      one section → document still produced with flags → audit writes.

I4 — End-to-end FakeLLM success: narratives populated; renderer
      content_sha256 stable across repeat runs (mini-golden).

I5 — End-to-end audit write failure: AuditClient raises →
      generator propagates `AuditWriteFailed`; Smarsh still ran pre-
      audit (we verify M10 is the LAST write). Pre-audit state
      committed is acceptable per R7.4.

---

## 4. TRACEABILITY

| AC     | Task(s)                                             |
|--------|-----------------------------------------------------|
| R1.1   | T1.1, T1.20                                         |
| R1.2   | T1.4, T1.27                                         |
| R1.3   | T1.4                                                |
| R2.1   | T1.3, T1.21                                         |
| R2.2   | T1.6, T1.7                                          |
| R2.3   | T1.6                                                |
| R3.0–8 | T1.34–T1.38                                         |
| R3a.1  | T1.8                                                |
| R3a.2  | T1.9, T1.10                                         |
| R3a.3  | T1.11, T1.12                                        |
| R3a.4  | T1.13, T1.14                                        |
| R3a.5  | T1.18b                                              |
| R3a.6  | T1.22                                               |
| R3b    | T1.39, T1.40                                        |
| R4.1–3 | T1.15, T1.16                                        |
| R4.4   | T1.51 (via FakeLLM in I3/I4)                        |
| R4.5   | T1.23                                               |
| R4.6   | T1.24                                               |
| R4.7   | T1.51, T1.52                                        |
| R4b.1–4| T1.41, T1.42, T1.42b, I3                            |
| R5.1   | T1.22, T1.53                                        |
| R5.2   | T1.5, T1.31                                         |
| R5.3   | T1.18                                               |
| R5.4   | T1.27                                               |
| R5b.1–3| T1.46, T1.46b, T1.46c, T1.46d                       |
| R6.1–5 | T1.19, T1.27, T1.30                                 |
| R7.1–5 | T1.20, T1.21, T1.23, T1.25, T1.26, T1.30b, T1.28,
           T1.29, T1.29b, T1.47, T1.48                         |
| R8.1–3 | T1.25, T1.26, T1.31a                                |
| R9.1–5 | T1.47, T1.48, T1.49, T1.50                          |
| R10.1–4| T1.43, T1.44, T1.45                                 |
| R11    | T1.32                                               |
| R12    | T1.22                                               |
| Integ. | I1, I2, I3, I4, I5                                  |

---

## 5. RISKS AND MITIGATIONS

- **Scope creep** — v3 adds ~860 LoC of new components. Mitigation:
  each component is a small, injected Protocol with a stub default.
  Integration tests exercise the wiring; unit tests cover the edges.
- **OPA matrix drift** — Phase-4 port to Rego could drift. Mitigation:
  every matrix rule is keyed by `rule_applied` matching the Rego
  path shape; T1.34 locks.
- **LLM PII leak** — M4 preflight + post-stitch scrub double guards.
  T1.41, T1.24 lock.
- **Schema-version bump** — v2 used 1.0.0; v3 bumps to 1.1.0.
  Golden-hex T1.19 re-pinned at v3 build.

---

## 6. CHANGES FROM v2 (GO 8.7)

| v2 area                                      | v3 delta                                                   |
|----------------------------------------------|------------------------------------------------------------|
| `RegBiDocument` fields                       | +8 new fields; schema_version bumped 1.0.0 → 1.1.0         |
| Populators                                   | Preserved; added 7 canonical disclosure types              |
| Compliance-decision engine                   | Added `OpaRequirementsResolver` + matrix                   |
| LLM preflight                                | Added `MnpiFilter` Protocol + `RegexMnpiFilter` default    |
| Renderer                                     | Added `DocumentRenderer.render_html` + content_sha256      |
| Principal review                             | Added queue entry + protocol + pre/post_use wiring         |
| Smarsh                                       | Added hook Protocol + stub; gated to BD/dual               |
| Audit                                        | SKIP paths now emit audit records                          |
| `narrative_model`                            | Sourced from `RegBiConfig` (not hard-coded)                |
| Tests                                        | +24 unit, +5 integration                                   |
