# Spec: M7 Schema Translators

> Module: M7 — Schema Translators
> Phase: 2 (Intelligence Layer — RIA lighthouse)
> Owner: Schema Specialist
> Version: **0.3.0 (post-LLMJ-v2 NI-fix)** — surgical patch over v0.2.0 (8.29/10 GO) addressing the four dangling section references (NI-1) and the two cosmetic items (NI-3, NI-4) flagged by the v2 review. No requirement or AC content changed — headers added, line-count corrected, typo fixed.
> Dependencies: M3 (canonical types) + M5 (archetype enums, read-only). No others.
> Consumers: M6 Trust-Aware Gateway (Stage 6 `m6.translate`), M11 REST Adapters (Phase 2 wiring — audit-bypass contract, see §Integration Point with M11). **M8 REMOVED from consumers per ARCH-09 dependency matrix audit (see Review Fix Traceability row #10).**
> Design Sources: 007-consolidated-design-and-plan.md Part 10 + Phase 2 plan, ARCH-09 Module M7 row + dependency matrix, ARCH-07 tech stack, IMPL-06 Blocker 3 (cost basis), Steering rules 9/16/19/32, M3 `src/m3_schema_registry/types.py` (1,182 lines — verified line-by-line 2026-04-26), M6 spec §R1.1 (`GatewayRequest` shape).
> Language: Python 3.12+ | Runtime Validation: Pydantic v2 (pinned `>=2.0,<3.0` per M3 `src/m3_schema_registry/pyproject.toml`) | NO vendor SDKs (data-shape translators only)
> Estimated Lines: ~3,000 total across 11 translator pairs (4 vendors × variable types, ~270 avg + shared infra ~400)

---

## Changelog from v0.1.0 → v0.2.0

| Area | v0.1.0 | v0.2.0 |
|------|--------|--------|
| Accuracy (UUID vs str) | T-tables used `uuid5(...)` everywhere | Each T-table derivation now matches M3 `types.py` exactly: `str(uuid5(...))` where M3 expects `str`, bare `uuid5(...)` where M3 expects `UUID`. Audit table in §M3 Alignment. |
| T5 Transaction | `source_id` and `transaction_id` collapsed into one derivation | TWO separate derivations: `transaction_id: UUID` (primary key), `source_id: str` (raw vendor ID). |
| T6 / T10 Orion | "Analogous to T2/T9" stubs | Explicit field tables, one row per vendor field. |
| UUID namespaces (AC10.5) | 7 namespaces (`CLIENT_NS` … `PLAN_NS`) | 10 namespaces — added `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS`. |
| T1 archetype validation | Claimed validator `{mass_affluent, hnw, uhnw}` on `Client.archetype` | Claim removed. M3 `Client.archetype: Optional[str]` has no validator. Noted in Known Blockers. |
| AccountType vs steering Rule 10 | Silent mismatch | Explicit callout: M3 `types.py` is SOT. Rule 10 is outdated draft. `B457.value == "457"` (not "457b"). |
| T9/Task 12 cost basis | Contradiction on vendor-silent `source_cost_basis_method` | Pinned: vendor silent → `source_cost_basis_method=None`, provenance lives in `ReconciliationNote.cost_basis_source.method_origin == "vendor_default"`. |
| M6 integration | Reached into `req.target.source_system` / `req.target.canonical_type` | Dispatcher uses explicit parameters `translate_to_canonical(source_system, canonical_type, vendor_payload)`. M6 Phase 2 wiring extracts from request-level fields (M6 amendment deferred to M6 spec Phase 2). |
| M8 consumer | Listed as consumer | Removed. ARCH-09 dependency matrix shows M8 calls M2/M5/M6/M10 only. |
| M11 consumer | Listed without audit discussion | Explicit dual-caller audit contract documented in §Integration Point with M11. |
| Directory/package/import naming | `src/m7_translators/` + pkg `m7-schema-translators` + import `m7_translators` | Now follows M3/M5/M6 convention exactly: directory `src/m7_schema_translators/`, package `m7-schema-translators`, import `m7_schema_translators`. |
| Schwab `VENDOR_API_VERSION` | `"MarketDataAPI 1.0"` | `"v1"` (Schwab URL path versioning). |
| SF FSC field-name verification | Claimed without footnote | Documented as PENDING-VERIFICATION in Known Blockers — SF FSC v59.0 SOQL verification is a Phase 2 Task before GA. For lighthouse, field shapes assumed per generic FSC extension convention. |
| R16 Cross-Module Observability | absent | New requirement: M7 `TranslationError.details` contract, M6 propagation to M10. |
| AC12.4 | Textual M5 allow-list | Positive AST-enforced allow-list. Spec includes test outline. |
| Hypothesis strategy (Task 18) | "generates ≥100 synthetic payloads" | `@composite` strategies with one concrete worked example (SF FSC Client). |
| AC7.5 discrepancy format | "diff strings like ..." | Two exact string formats, format-literal pinned. |
| R7 single vs multi Household | Silent | Explicit rule: single-vendor `to_canonical_household_*` → `reconciliation=None`; multi-vendor → populated. Downstream consumers use `reconciliation is None` to distinguish. |
| PII-free scan (Task 19) | `str(note)` only | Extended to (a) `TranslationError.details`, (b) every fixture JSON under `tests/schema-reconciliation/fixtures/**`, with email/SSN/phone/IBAN regex guards. |
| Reverse-lossy | Only forward `LOSSY_FIELDS` documented | Every T-table now also declares `REVERSE_LOSSY_FIELDS` — canonical fields that don't round-trip back to the vendor shape. |
| `TRANSLATOR_REGISTRY` length | `== 11` | `>= 11` with invariant: every entry has a task/implementation file (AC2.5). |
| Mutability | Plain dicts | `MappingProxyType` wrap on `ENUM_MAPPINGS`, `REVERSE_ENUM_MAPPINGS`, `COST_BASIS_VENDOR_MAP`, `COST_BASIS_DEFAULTS`, `TRANSLATOR_REGISTRY`. |
| R14 forbidden imports | `open(`, `socket`, `urllib`, `httpx`, `requests`, `subprocess` | Added `warnings`, `tempfile`, `io.open`, `os.open`. |
| Concurrency test | absent | Task 18 adds 4-thread smoke test asserting byte-identical results on shared registry access. |
| `TranslationError.details` | `dict` | TypedDict per subclass (`UnknownEnumDetails`, `MissingRequiredDetails`, `CostBasisUnmappableDetails`, …). |
| Schwab UK cost basis | PENDING SME without skeleton | `@pytest.mark.xfail(reason="Schwab UK cost-basis PENDING SME — IMPL-06 follow-up")` in fixture skeleton. |

---

## Changelog from v0.2.0 → v0.3.0

v2 LLMJ review scored v0.2.0 at **8.29/10 GO** and flagged four non-blocking cosmetic items (NI-1 through NI-4). v0.3.0 is a surgical patch — no requirement, AC, or task content changed. Structural hygiene only.

| # | v2 NI | Problem | v0.3.0 Fix |
|---|-------|---------|------------|
| 1 | NI-1 | Review Fix Traceability Table (Fix #9) cited `§Integration Point with M6` — section did not exist as a header. Intended content lived in AC13.2 + Appendix B.6. | New dedicated `## Integration Point with M6` section added between §Field-Level Vendor → Canonical Mapping and §Tasks. Points to AC13.2 (dispatcher signature) and Appendix B.6 (skeleton). Explicitly documents: M6 calls M7's dispatcher with **explicit `source_system` + `canonical_type` params** (no reach into `req.target.*`). |
| 2 | NI-1 | Review Fix Traceability Table (Fix #10) cited `§Integration Point with M11` — section did not exist. Dual-caller audit contract only mentioned in the changelog row. | New dedicated `## Integration Point with M11` section added. Documents the dual-caller audit contract: Phase 2 uses M6-as-caller exclusively; M11-as-caller path is deferred to lighthouse-2 with explicit audit-bypass prevention rules. |
| 3 | NI-1 | Review Fix Traceability Table (Fix #11) cited `§Design "Directory / Package / Import Naming" table` — neither the `## Design` section nor the `###` subsection existed. | New `## Design` section added with `### Directory / Package / Import Naming` subsection. Pins: directory `src/m7_schema_translators/`, package `m7-schema-translators`, import `m7_schema_translators`. Follows M3/M5/M6 convention exactly. |
| 4 | NI-1 | Task 18 + Traceability Fix #13 cited `§Design "Hypothesis Strategy Approach"` — section did not exist AND no worked example existed anywhere in the spec. Biggest structural gap in v0.2.0. | New `### Hypothesis Strategy Approach` subsection under `## Design`. Provides a concrete, end-to-end SF FSC Client `@composite` strategy (`st.text`/`st.sampled_from`/`st.emails`/`st.dates`/`st.decimals`) with PII-safe alphabets and domain allow-lists. Pattern explicitly replicable across all 11 Phase 2 translator pairs. |
| 5 | NI-3 | Spec line 9 cited M3 `types.py` as "1,183 lines"; actual `wc -l` is 1,182. | Line-count corrected to `1,182` in version banner §Design Sources. |
| 6 | NI-4 | Appendix B.4 `RECONCILIATION_NOTE_SAFE_FIELDS` contained `"schwab_iria_label_ambiguous"` (typo — should be `"schwab_ira_label_ambiguous"`). v2 review noted build code already had the correct spelling. | Typo fixed in B.4 skeleton to match the build. |
| 7 | housekeeping | Version banner still read `Version 0.2.0 (post-LLMJ-v1 fix)`. | Banner updated to `Version 0.3.0 (post-LLMJ-v2 NI-fix)` with rationale line noting the 8.29/10 GO verdict from v2 review. |

NI-2 (Appendix B.1 `_format` skeleton allows stringification of all `details` values) and NI-5 (3,000-line estimate optimistic) are **NOT fixed in v0.3.0** — both are acceptable risks per v2 review: NI-2 is skeleton-only (illustrative, not prescriptive — AC14.2 + AC14.8 are authoritative at build time), NI-5 is a cost-planning concern, not a spec defect. v0.2.0 recommendations for 9.0+ (full SF FSC SOQL verification) remain deferred to lighthouse execution.

---

## Architecture Clarification: M7 is a Pure Library

ARCH-07 lists "Pydantic v2" for M7. The ARCH-09 dependency matrix shows M7 calls only M3 (column 3 marked, all others `.`). M7 is called BY M6 (row M6 → M7 marked `*`) and BY M11 (row M11 → M7 marked `*`). These are not contradictory:

- **M7 is a LIBRARY** — a bag of Pydantic v2 vendor models + pure functions `to_canonical_*` / `from_canonical_*`. No FastAPI. No HTTP. No network. No file I/O. No credentials. No logging.
- **M7 does not reach out to vendors.** M11 adapters own the vendor HTTP/SFTP/SDK call. M11 hands a Python dict (the raw vendor payload) to M7. M7 returns an M3 canonical Pydantic model. That is the entire contract.
- **M6 orchestrates.** M6 decides when to call `translate_to_canonical(source_system, canonical_type, vendor_payload)`. M7 never decides what to call, never logs to M10, never filters MNPI (M4 does that after M7 returns).

M7 does NOT import from M1, M2, M4, M6, M8, M9, M10, M11, M12, M13, compliance.gap2, compliance.gap6. M7 imports ONLY from M3 (canonical types + enums) and M5 (`Archetype`, `Jurisdiction`, `RegistrationType` — read-only enum values, never config objects or loaders).

---

## Phase 2 Lighthouse Scope

Per 007-consolidated-design-and-plan.md Part 10 and the Phase 2 plan in ARCH-09 (Week 14-36, 7-person team, 24-week window), M7 Phase 2 lighthouse covers **4 vendors × 8 canonical types = 11 translator pairs** — enough to power the RIA meeting-prep user journey end-to-end:

| Vendor | Source System (M3 `SourceSystem` enum) | Canonical Types Covered | Rationale |
|--------|----------------------------------------|-------------------------|-----------|
| **Salesforce FSC** | `salesforce_fsc` | Client, Household, Goal | CRM — client master, relationship grouping (`relationship` type), goal picklists |
| **Orion** | `orion` | Holding, Transaction, TaxLot, Household | Portfolio accounting — positions, trade history, embedded lots. Household grouping `portfolio_management`. |
| **eMoney** | `emoney` | PlanSummary | Financial planning — plan-level summary only. Raw plan data NEVER crosses translator boundary. |
| **Schwab** | `schwab` | Holding, TaxLot, Household | Custodian — positions, tax lots, custodial Household grouping. Default cost basis = `specific_lot` US. |

**Total: 4 vendors, 8 canonical types, 11 translator pairs** — 3 (SF FSC) + 4 (Orion) + 1 (eMoney) + 3 (Schwab).

### Explicitly OUT of scope (deferred to "M7-lighthouse-2" in Phase 3)

Remaining canonical types — Order, Balance, Performance, SecurityProfile, Quote, InteractionSummary, ComplianceCheck, ComplianceAlert, AuditEntry, ResearchBrief, PaymentInstruction — and the remaining vendors — Fidelity, Pershing, Envestnet, Bloomberg, FactSet, Alpha Vantage, IEX, SEC EDGAR, MoneyGuidePro, RightCapital, Wealthbox, Redtail, SWIFT, Schwab SFTP, Fidelity SFTP — are deferred. This spec does NOT block on their absence.

---

## Known Blockers & Pending SME Decisions

Per M3 DECISION-LOG and the architecture docs, M7 inherits these open questions. Each maps to a DECISION-LOG entry in `src/m7_schema_translators/DECISION-LOG.md` (see R15).

| Area | Question | Impact on M7 | Status |
|------|----------|--------------|--------|
| Holding.market_value accrued interest | Does MarketValue include accrued interest? Differs per custodian. | Orion/Schwab Holding translators must set `market_value_includes_accrued` flag based on vendor convention. Orion=explicit, Schwab=implicit false. | PENDING SME — M3 DECISION-LOG |
| Household sources_agree | What counts as a "discrepancy"? Member missing from one vendor? Role mismatch? | Household translator `from_canonical` + reconciliation helper logic. Pinned in AC7.5 (format-literal). | RESOLVED in v0.2.0 (AC7.5) |
| eMoney raw plan fields | Which eMoney fields are "raw plan" (never to LLM) vs "summary" (safe for summary brief)? | PlanSummary translator allow-list. M4 owns MNPI filtering AFTER translation; M7 only transports documented summary fields. `extra="forbid"` on `EMoneyPlanSummary` excludes raw body at vendor-model ingestion. | M4 owns filter; M7 rejects raw body at Pydantic validation. |
| Schwab cost basis default | If Schwab response omits `cost_basis_method` for a US account, what method do we assign? | Cost basis normalization rule (R5). Answer per Steering Rule 16 + IMPL-06: `specific_lot` for Schwab US taxable equity. | RESOLVED (steering rule) |
| Schwab UK `specific_lot` → UK default FIFO | Schwab UK account reports `"SpecificLot"` but UK jurisdiction defaults to FIFO. | Raise `CostBasisUnmappable(reason_code="ambiguous_mapping", details={"jurisdiction":"UK"})`. Fixture carries `@pytest.mark.xfail(reason="Schwab UK PENDING SME — IMPL-06 follow-up")` until SME rules. | PENDING SME |
| SF FSC field names | `FinServ__AccountIds__c`, `FinServ__HouseholdId__c`, `FinServ__ClientArchetype__c` not yet verified against live SF FSC v59.0 org via SOQL. | T1/T2/T3 derivations assume generic FSC extension shape. Incorrect names break translators at runtime via `extra="forbid"`. | **PENDING-VERIFICATION.** Lighthouse documents assumed shape; DECISION-LOG records "real-world SOQL verification" as a pre-GA Task. Phase 2 acceptable because RIA lighthouse is internal-tenant and field-name fix is a MINOR translator bump. |
| AccountType mismatch (Steering Rule 10 vs M3) | Steering Rule 10 lists `individual`, `joint_tos`, `joint_tic`, `pension`, `profit_sharing`, `457b` (outdated draft). M3 `AccountType` uses `TAXABLE`, `TRADITIONAL_IRA`, …, `B457 (value "457")`. | M3 `types.py` is source of truth. Steering Rule 10 is an outdated draft. M7 T-tables use M3 values. If Orion/Schwab returns an account type not mapped, `UnknownEnumValue` fires. | RESOLVED — M3 is SOT. Documented here and in DECISION-LOG. |
| 457 vendor string | M3 `AccountType.B457` value is `"457"` (not "457b"). Orion/Schwab lighthouse does not currently return a 457 string in any fixture. | No 457 vendor-string mapping in Phase 2 ENUM_MAPPINGS. First encounter triggers `UnknownEnumValue` and forces a MINOR translator bump with the new mapping row. | Phase 2 gap — documented. Not blocking lighthouse. |
| OPA per-Balance account_type rules | Steering Rule 10 requires `account_type` on Balance; M7 Phase 2 does NOT translate Balance (out of scope). | Blocks compliance sub-module Gap 5 (ERISA Account-Type) for Balance-level rules until M7-lighthouse-2 ships the `Balance` translator. | Scope gap — documented. |
| M3 `float` vs `Decimal` for money | `Holding.market_value: float`, `cost_basis: float` — IEEE-754 cent drift risk. | Inherited decision — M3 DECISION-LOG rationale: "Pydantic v2 handles float display/comparison fine. Migrate to Decimal if reconciliation tests show precision drift." M7 does not challenge. Round-trip tests assert delta ≤ 1e-6 on money fields. | Inherited. Not challenged. |
| Vendor-ID character set | `uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")` — SF FSC IDs are 18-char alphanumeric (safe). Orion/Schwab/eMoney ID character sets not formally declared. | Vendor IDs containing `:` would collide the namespace key format. | Constraint added in R10 (AC10.8): vendor IDs must match `[a-zA-Z0-9._\-]+`. Non-conformant payload → `TypeCoercionError(reason_code="vendor_id_invalid_chars")`. |

Implementation proceeds with documented rules. Pending items trigger MINOR translator version bumps, not blockers.

---

## Steering Rules M7 Must Honor

| Rule # | Rule | Addressed in |
|--------|------|--------------|
| **9** | 13 modules, strict boundaries, no cross-module imports | R12 + Module Boundary section + Task 2 (AST import-scan test) |
| **16** | Cost basis normalization is REQUIRED in M7; `cost_basis_method` never null | R5 + Cost Basis Normalization section + Tasks 9, 12 |
| **19** | Every OPA rule must include `wsp_section` — NOT M7's concern (M2/M4 own OPA). M7 MUST NOT strip `wsp_section` when translating ComplianceAlert (deferred to lighthouse-2). | Noted in §Out of Scope; ComplianceAlert deferred. |
| **32** | SECURITY PER MODULE: no credentials, Pydantic-validated inputs, MNPI filtered by M4, audit logged by M10, cost_basis never null | R5, R10, R12, R14, R16 + Security Constraints section |

---

## M3 Alignment — UUID vs str Audit (Source of Truth: `src/m3_schema_registry/types.py`)

The single most important accuracy fix in v0.2.0. Every `*_ref` / `*_id` field in every T-table is now aligned to M3's actual Pydantic annotation. Audit performed line-by-line against `src/m3_schema_registry/types.py` 2026-04-26.

| Canonical Type | Field | M3 Type | M7 Derivation (v0.2.0) |
|----------------|-------|---------|------------------------|
| `Client` | `canonical_id` | `UUID` | `uuid5(CLIENT_NS, f"{vendor}:{id}")` |
| `Client` | `firm_id` | `UUID` (REQUIRED) | `uuid5(FIRM_NS, value)` |
| `Client` | `advisor_ref` | `Optional[UUID]` | `uuid5(ADVISOR_NS, f"{vendor}:{id}")` |
| `Client` | `household_ref` | `Optional[UUID]` | `uuid5(HOUSEHOLD_NS, f"{vendor}:{id}")` |
| `Client` | `accounts` | `list[UUID]` | `[uuid5(ACCOUNT_NS, f"{vendor}:{id}") for id in …]` |
| `Client` | `source_id` | `str` | raw vendor ID, direct |
| `Client` | `source_system` | `str` | `"salesforce_fsc"` const |
| `Household` | `canonical_id` | `UUID` | `uuid5(HOUSEHOLD_NS, …)` |
| `Household` | `members[].client_ref` | `str` (NOT UUID — M3 `HouseholdMember.client_ref: str`) | **`str(uuid5(CLIENT_NS, f"{vendor}:{id}"))`** |
| `Household` | `accounts[].account_ref` | `str` (NOT UUID — M3 `HouseholdAccount.account_ref: str`) | **`str(uuid5(ACCOUNT_NS, f"{vendor}:{id}"))`** |
| `Holding` | `canonical_id` | `UUID` | `uuid5(HOLDING_NS, …)` |
| `Holding` | `account_ref` | `str` | **`str(uuid5(ACCOUNT_NS, f"{vendor}:{id}"))`** |
| `Holding` | `client_ref` | `Optional[str]` | **`str(uuid5(CLIENT_NS, …))`** when present |
| `Holding` | `source_id` | `str` | raw vendor ID |
| `TaxLot` | `lot_id` | `UUID` | `uuid5(TAXLOT_NS, …)` |
| `TaxLot` | `holding_ref` | `str` | **`str(uuid5(HOLDING_NS, f"{vendor}:{parent_position_id}"))`** |
| `TaxLot` | `security_ref` | `Optional[str]` | direct ticker/symbol string |
| `TaxLot` | `source_cost_basis_method` | `Optional[str]` | direct vendor string, or **`None`** when vendor silent |
| `Transaction` | `transaction_id` | `UUID` | `uuid5(TRANSACTION_NS, f"{vendor}:{id}")` |
| `Transaction` | `account_ref` | `UUID` | `uuid5(ACCOUNT_NS, f"{vendor}:{id}")` |
| `Transaction` | `client_ref` | `Optional[UUID]` | `uuid5(CLIENT_NS, f"{vendor}:{id}")` |
| `Transaction` | `order_ref` | `Optional[UUID]` | `uuid5(ORDER_NS, …)` or `None` |
| `Transaction` | `source_id` | `str` (SEPARATE from `transaction_id`!) | raw vendor transaction ID |
| `Transaction` | `source_transaction_type` | `Optional[str]` | direct vendor string |
| `PlanSummary` | `canonical_id` | `UUID` | `uuid5(PLAN_NS, …)` |
| `PlanSummary` | `client_ref` | `UUID` (REQUIRED) | `uuid5(CLIENT_NS, f"emoney:{id}")` |
| `PlanSummary` | `household_ref` | `Optional[UUID]` | `uuid5(HOUSEHOLD_NS, f"emoney:{id}")` |
| `PlanSummary` | `goals` | `list[UUID]` | `[uuid5(GOAL_NS, …) for id in …]` |
| `Goal` | `canonical_id` | `UUID` | `uuid5(GOAL_NS, …)` |
| `Goal` | `client_ref` | `UUID` | `uuid5(CLIENT_NS, …)` |
| `Goal` | `household_ref` | `Optional[UUID]` | `uuid5(HOUSEHOLD_NS, …)` |
| `Goal` | `plan_ref` | `Optional[UUID]` | `uuid5(PLAN_NS, …)` |
| `Goal` | `linked_accounts` | `list[UUID]` | `[uuid5(ACCOUNT_NS, …) for id in …]` |

Rule of thumb: `Transaction.*_ref` fields are **UUID**; `Holding.*_ref`, `TaxLot.holding_ref`, `Household.members[].client_ref`, `Household.accounts[].account_ref` are **str** — M7 wraps with `str()` to produce the canonical-URN form.

---

## Requirements

### R1. Translator Function Contract — Bidirectional, Pure, Idempotent
Every M7 translator MUST implement exactly two pure functions per (vendor, canonical type) pair. Both are pure (no I/O, no global state), both idempotent (byte-identical output for identical input).

**Acceptance Criteria:**
- **AC1.1:** Each translator module exposes `to_canonical_{type}(vendor_payload: dict) -> tuple[{CanonicalType}, ReconciliationNote]`.
- **AC1.2:** Each translator module exposes `from_canonical_{type}(canonical: {CanonicalType}) -> tuple[{VendorType}, ReconciliationNote]`.
- **AC1.3:** Two calls with identical input produce `(canonical, note)` pairs whose `model_dump_json(sort_keys=True)` are byte-identical on BOTH elements. `ReconciliationNote.fields_dropped` and `fields_derived` are sorted alphabetically before serialization.
- **AC1.4:** Two calls with identical canonical produce `(vendor_model, note)` pairs whose `model_dump_json(sort_keys=True)` are byte-identical.
- **AC1.5:** No translator performs network I/O, file I/O, env reads, `time.time()`, or random generation.
- **AC1.6:** No translator mutates its inputs (test via deep-copy before + equality after).
- **AC1.7:** Translator functions are NOT `async`. Synchronous only. M6 wraps calls in `asyncio.to_thread` if needed.
- **AC1.8:** Translator functions are thread-safe. No module-level mutable state. `ENUM_MAPPINGS`, `REVERSE_ENUM_MAPPINGS`, `TRANSLATOR_REGISTRY`, `COST_BASIS_VENDOR_MAP`, `COST_BASIS_DEFAULTS` are all `types.MappingProxyType` wrappers.

### R2. Lighthouse Vendor & Type Coverage (4 Vendors, 8 Canonical Types, ≥11 Translator Pairs)

**Acceptance Criteria:**
- **AC2.1:** Salesforce FSC translators exist for: Client, Household, Goal. (3 pairs)
- **AC2.2:** Orion translators exist for: Holding, Transaction, Household, TaxLot. (4 pairs)
- **AC2.3:** eMoney translator exists for: PlanSummary. (1 pair)
- **AC2.4:** Schwab translators exist for: Holding, TaxLot, Household. (3 pairs)
- **AC2.5:** `TRANSLATOR_REGISTRY: MappingProxyType[tuple[str, str], TranslatorPair]` exposed from `m7_schema_translators`. `len(TRANSLATOR_REGISTRY) >= 11`. Invariant: every entry has a matching implementation file — `for pair in TRANSLATOR_REGISTRY.values(): importlib.import_module(pair.module_path)` succeeds.
- **AC2.6:** Every registry entry references a valid `SourceSystem` enum value and a valid canonical type name from `CANONICAL_TYPES`.
- **AC2.7:** Exact 11 Phase 2 pairs: `(salesforce_fsc, Client)`, `(salesforce_fsc, Household)`, `(salesforce_fsc, Goal)`, `(orion, Holding)`, `(orion, Transaction)`, `(orion, Household)`, `(orion, TaxLot)`, `(emoney, PlanSummary)`, `(schwab, Holding)`, `(schwab, TaxLot)`, `(schwab, Household)`.

### R3. Pydantic v2 Vendor Models

**Acceptance Criteria:**
- **AC3.1:** Every vendor model sets `model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)`.
- **AC3.2:** Every field has a non-empty `description`.
- **AC3.3:** Vendor models live under `src/m7_schema_translators/{vendor}/models.py`.
- **AC3.4:** `to_canonical_*` first step is ALWAYS `vendor_model = {VendorModel}(**vendor_payload)`.
- **AC3.5:** Vendor models use only Pydantic v2 APIs (`@field_validator`, `ConfigDict`, `.model_dump()`).
- **AC3.6:** Field-level pydantic constraints applied where vendor docs specify them (e.g., Schwab `accountNumber` 8-digit → `pattern=r"^\d{8}$"`).
- **AC3.7:** `ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType[str, Enum]]` — nested MappingProxyType prevents mutation. `REVERSE_ENUM_MAPPINGS` same.

### R4. Fail-Closed on Unmappable Data

**Acceptance Criteria:**
- **AC4.1:** `TranslationError` base in `m7_schema_translators.errors` with `reason_code: str`, `vendor: str`, `canonical_type: str`, `field_path: str`, `details: TypedDict` (per AC4.8).
- **AC4.2:** Subclasses: `UnknownEnumValue`, `MissingRequiredField`, `TypeCoercionError`, `CostBasisUnmappable`, `VendorSchemaVersionMismatch`, `RoundTripDivergence`, `UnregisteredTranslator`.
- **AC4.3:** `reason_code` drawn from closed `VALID_REASON_CODES: frozenset[str]`: `{"unknown_enum_value", "missing_required_field", "type_coercion_failed", "vendor_id_invalid_chars", "cost_basis_unmappable", "unsupported_vendor_value", "ambiguous_mapping", "vendor_schema_version_mismatch", "round_trip_divergence", "unregistered_translator", "vendor_payload_validation_failed"}`.
- **AC4.4:** Translators NEVER catch `TranslationError` internally. Errors propagate to the caller.
- **AC4.5:** Translators NEVER return `None` from `to_canonical_*`. Exception: `from_canonical_household(canonical, vendor)` MAY return `(None, note)` when `vendor_mappings.{vendor}` is absent (AC7.6).
- **AC4.6:** Unknown enum values → raise `UnknownEnumValue`. Never default.
- **AC4.7:** `TranslationError.__str__` format: `"[{reason_code}] {vendor}.{canonical_type}.{field_path}: {details_summary}"`. No raw values. No PII.
- **AC4.8:** Per-subclass `TypedDict` for `details` (full definitions in Appendix B.1):
  - `UnknownEnumDetails`: `{vendor_value: str, valid_values: list[str]}`
  - `MissingRequiredDetails`: `{field_name: str}`
  - `TypeCoercionDetails`: `{expected_type: str, got_type: str}`
  - `CostBasisUnmappableDetails`: `{vendor_value: Optional[str], account_type_group: Optional[str], security_class: Optional[str], jurisdiction: Optional[str]}`
  - `VendorSchemaVersionMismatchDetails`: `{observed_version: str, min_supported: str, max_supported: str}`
  - `RoundTripDivergenceDetails`: `{field_path: str, forward_hash: str, roundtrip_hash: str}`
  - `UnregisteredTranslatorDetails`: `{valid_source_systems: list[str], valid_canonical_types: list[str]}`

### R5. Cost Basis Normalization (Steering Rule 16)
`cost_basis_method` on every canonical TaxLot. Never null.

**Acceptance Criteria:**
- **AC5.1:** `m7_schema_translators.cost_basis.normalize_cost_basis_method(vendor_string: Optional[str], vendor: str, account_type: Optional[str], security_class: Optional[str], jurisdiction: Optional[str]) -> CostBasisMethod` — deterministic, fail-closed.
- **AC5.2:** `COST_BASIS_VENDOR_MAP: MappingProxyType[tuple[str, str], CostBasisMethod]` — see §Cost Basis Normalization Matrix.
- **AC5.3:** `COST_BASIS_DEFAULTS: MappingProxyType[tuple[str, str, str], CostBasisMethod]` — Schwab US taxable equity → `specific_lot`, Fidelity mutual fund → `average_cost`, Fidelity equity → `specific_lot`.
- **AC5.4:** Every canonical TaxLot has `cost_basis_method` populated (M3 validator is defense-in-depth).
- **AC5.5:** Every TaxLot carries `source_cost_basis_method`. **Vendor-silent case: `source_cost_basis_method = None`.** Provenance lives in `ReconciliationNote.cost_basis_source.method_origin == "vendor_default"`. v0.2.0 fix to T9/Task 12 contradiction.
- **AC5.6:** Unknown inputs → `CostBasisUnmappable`. Never returns `specific_lot` as fallback.
- **AC5.7:** `CostBasisSource` sub-model on `ReconciliationNote.cost_basis_source` for every TaxLot: `{vendor_field, vendor_value: Optional[str], canonical_value, method_origin: Literal["vendor_reported","vendor_default","derived"], confidence: Literal["high","medium","low"]}`.
- **AC5.8:** `tests/unit/test_m7_cost_basis.py` covers: every VENDOR_MAP entry, every DEFAULTS entry, unknown raises, missing + unmapped raises, Schwab UK xfail.

### R6. Enum Mapping Discipline

**Acceptance Criteria:**
- **AC6.1:** Each translator declares `ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType[str, Enum]]`.
- **AC6.2:** Each translator declares `REVERSE_ENUM_MAPPINGS: MappingProxyType[str, MappingProxyType[Enum, str]]`.
- **AC6.3:** Unknown vendor value → `UnknownEnumValue(details={"vendor_value": v, "valid_values": sorted(mapping.keys())})`.
- **AC6.4:** All mappings in §Vendor Enum Mapping Matrix.
- **AC6.5:** Meta-test asserts (a) every canonical enum member has ≥1 reverse entry per vendor; (b) every vendor string maps to a valid canonical enum; (c) no vendor string maps to two different canonical enums within same field; (d) MappingProxyType wrap present (mutation raises TypeError).

### R7. Vendor Mappings Preserved (Household Container — M3 Rule 6)

**Acceptance Criteria:**
- **AC7.1:** SF FSC → `HouseholdVendorSFSC(household_id, grouping_type="relationship")`. Orion → `HouseholdVendorOrion(household_id, grouping_type="portfolio_management")`. Schwab → `HouseholdVendorSchwab(master_account, grouping_type="custodial")`. grouping_type CONSTs, test-asserted.
- **AC7.2:** `to_canonical_household_multi(payloads: Mapping[str, dict], last_reconciled: datetime) -> tuple[Household, ReconciliationNote]`. Caller provides `last_reconciled` — M7 never calls `datetime.utcnow()`.
- **AC7.3:** `members` at canonical top level, NOT inside `vendor_mappings`. `client_ref` is **`str`** per M3 — M7 produces `str(uuid5(CLIENT_NS, f"{vendor}:{id}"))`.
- **AC7.4:** `reconciliation` populated for multi-vendor only.
- **AC7.5:** Helper `_compare_household_members` uses EXACT format literals (test asserts):
  - Missing member: `"member (client:{client_ref}, role:{role}) present in {vendor_a} but missing in {vendor_b}"`
  - Role mismatch: `"role mismatch for client:{client_ref} — {vendor_a}:{role_a} vs {vendor_b}:{role_b}"`
  - Lists sorted alphabetically. `vendor_a` < `vendor_b` lexicographic — deterministic.
- **AC7.6:** `from_canonical_household(canonical, vendor) -> tuple[Optional[VendorHouseholdModel], ReconciliationNote]`. Returns `(None, note)` if `canonical.vendor_mappings.{vendor}` is `None`.
- **AC7.7:** Round-trip tests cover 6 scenarios: `{sfsc_only, orion_only, schwab_only, sfsc+orion, sfsc+schwab, all_three}`.
- **AC7.8 (single vs multi rule):** Single-vendor `to_canonical_household_*` → `reconciliation=None`. Multi-vendor → populated. **Downstream consumers MUST check `reconciliation is None` to distinguish single-source from multi-source data.**
- **AC7.9 (merge order):** When multiple vendors claim same `client_ref` with different `role`, BOTH records in `members[]` with source attribution AND role-mismatch discrepancy emitted. M7 does not pick a winner.

### R8. Schema Versioning

**Acceptance Criteria:**
- **AC8.1:** Each translator declares `SCHEMA_VERSION: str = "0.1.0"` initially.
- **AC8.2:** `VENDOR_API_VERSION`: SF FSC `"v59.0"`, Orion `"v2.0"`, eMoney `"v2"`, Schwab **`"v1"`** (URL path versioning — v0.2.0 fix).
- **AC8.3:** `TRANSLATOR_REGISTRY` entries carry `(schema_version, vendor_api_version)` via `TranslatorPair` dataclass.
- **AC8.4:** `CHANGELOG.md` per vendor, Keep-A-Changelog format: `## [0.1.0] — 2026-04-26` top anchor.
- **AC8.5:** `tests/schema-reconciliation/test_translator_versioning.py` asserts SCHEMA_VERSION regex `^\d+\.\d+\.\d+$` AND CHANGELOG top-line regex `^## \[{SCHEMA_VERSION}\] — \d{4}-\d{2}-\d{2}$`.
- **AC8.6:** Phase 2: no compat window. Vendor API bump = MAJOR translator bump. Optional `MIN_VENDOR_API_VERSION`/`MAX_VENDOR_API_VERSION` via `packaging.version.Version`. Reserved for Phase 3+.

### R9. Reconciliation Audit Trail

**Acceptance Criteria:**
- **AC9.1:** `ReconciliationNote` fields: `trace_id: Optional[str]`, `vendor: str`, `canonical_type: str`, `direction: Literal["to_canonical","from_canonical"]`, `fields_dropped: list[str]` (sorted), `fields_derived: list[str]` (sorted), `cost_basis_source: Optional[CostBasisSource]`, `vendor_schema_version: str`, `translator_schema_version: str`, `notes: list[str]` (allow-list only).
- **AC9.2:** Every `to_canonical_*` returns `(canonical_instance, ReconciliationNote)`.
- **AC9.3:** Every `from_canonical_*` returns `(vendor_instance, ReconciliationNote)`.
- **AC9.4:** `fields_dropped` = vendor fields with a value but not mapped (subset of `LOSSY_FIELDS`). `fields_derived` = canonical fields from defaults or computed rules.
- **AC9.5:** `ReconciliationNote` contains ZERO PII and ZERO MNPI.
- **AC9.6:** `RECONCILIATION_NOTE_SAFE_FIELDS: frozenset[str]` allow-list restricts `notes` content.
- **AC9.7:** Serializes deterministically (alphabetical keys + sorted lists).

### R10. Idempotency & Determinism

**Acceptance Criteria:**
- **AC10.1:** No `uuid.uuid4()` in any translator (AST grep).
- **AC10.2:** No `datetime.utcnow()`, `datetime.now()`, `time.time()` (AST grep).
- **AC10.3:** No `random.*` (AST grep).
- **AC10.4:** Hypothesis property tests ≥100 cases per translator. `@settings(max_examples=100, deadline=500)`; total ≤ 2 min.
- **AC10.5:** UUID namespaces in `m7_schema_translators.shared.namespaces` — **10 namespaces** (up from 7 in v0.1.0): `CLIENT_NS`, `HOUSEHOLD_NS`, `HOLDING_NS`, `TAXLOT_NS`, `TRANSACTION_NS`, `GOAL_NS`, `PLAN_NS`, **`FIRM_NS`** (new), **`ACCOUNT_NS`** (new), **`ADVISOR_NS`** (new). `ORDER_NS` reserved for future; Phase 2 uses `None` for `Transaction.order_ref`.
- **AC10.6:** `model_dump_json(sort_keys=True)` on two calls with equal input produces equal bytes.
- **AC10.7 (concurrency smoke):** Task 18 spawns 4 threads, each invokes `translate_to_canonical` for every registry pair in a 50-iteration loop, asserts byte-identical results AND no mutation of `ENUM_MAPPINGS`/`TRANSLATOR_REGISTRY`.
- **AC10.8 (vendor-ID chars):** Vendor IDs must match `^[a-zA-Z0-9._\-]+$`. Non-conformant → `TypeCoercionError(reason_code="vendor_id_invalid_chars")`.
- **AC10.9 (null-PII):** `None` preserved as `None`. Whitespace-only `"   "` collapsed to `None` via `str_strip_whitespace=True` + vendor model validator.

### R11. Round-Trip Reconciliation Tests

**Acceptance Criteria:**
- **AC11.1:** `tests/schema-reconciliation/test_m7_roundtrip_{vendor}_{type}.py` exists for all 11 pairs.
- **AC11.2:** ≥3 fixtures per test: minimal, fully-populated, edge-case. Synthetic only.
- **AC11.3:** "Double-trip" equality for SINGLE-VENDOR translators: `to_canonical(input) == to_canonical(from_canonical(to_canonical(input)))`. Multi-vendor Household uses AC7.7.
- **AC11.4:** `LOSSY_FIELDS: frozenset[str]` per translator (forward drops). `REVERSE_LOSSY_FIELDS: frozenset[str]` per translator (reverse drops). Every entry documented in `CHANGELOG.md`.
- **AC11.5:** Every TaxLot `cost_basis_method is not None`. Every fixture. `source_cost_basis_method` is vendor string when reported; `None` when silent.
- **AC11.6:** Every enum field resolves to a valid enum member.
- **AC11.7:** `ReconciliationNote.fields_dropped` is subset of `LOSSY_FIELDS` (forward) or `REVERSE_LOSSY_FIELDS` (reverse).
- **AC11.8:** Money-precision tolerance: `math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-6)` on money fields.

### R12. Module Boundary Isolation (Steering Rule 9)

**Acceptance Criteria:**
- **AC12.1:** `tests/unit/test_m7_module_boundary.py` walks every `.py` in `src/m7_schema_translators/` and asserts no forbidden prefix imports (`m1_`, `m2_`, `m4_`, `m6_`-`m13_`, `compliance.gap2`, `compliance.gap6`).
- **AC12.2:** Forbidden runtime deps (AST scan): `httpx`, `requests`, `boto3`, `fastapi`, `redis`, `langchain`, `langgraph`, `openai`, `anthropic`, `simple_salesforce`, `orion_sdk`, `schwab_sdk`, `emoney_sdk`.
- **AC12.3:** `requirements.txt` contains ONLY `pydantic>=2.0,<3.0` (exact match to M3 `src/m3_schema_registry/pyproject.toml`), `m3-schema-registry`, `m5-config-loader`.
- **AC12.4 (positive AST-enforced M5 allow-list):** Test parses `ast` of every `.py` under `src/m7_schema_translators/`, collects `ImportFrom` nodes with `node.module == "m5_config_loader"` (or `m5_config_loader.*`), asserts `set(alias.name for alias in node.names).issubset({"Archetype", "Jurisdiction", "RegistrationType"})`. Implementation:
  ```python
  import ast, pathlib
  ALLOWED_M5 = frozenset({"Archetype", "Jurisdiction", "RegistrationType"})
  for py_file in pathlib.Path("src/m7_schema_translators").rglob("*.py"):
      tree = ast.parse(py_file.read_text())
      for node in ast.walk(tree):
          if isinstance(node, ast.ImportFrom) and node.module and (
              node.module == "m5_config_loader"
              or node.module.startswith("m5_config_loader.")
          ):
              imported = {alias.name for alias in node.names}
              assert imported.issubset(ALLOWED_M5), (
                  f"{py_file}: disallowed M5 imports {imported - ALLOWED_M5}"
              )
  ```
  Forbidden M5 imports: `EnterpriseConfig`, `load_enterprise_config`, `FirmConfig`, `Topology`, `Runtime`, `SuitabilityStandard`, `PrincipalReviewMode`, `TimeoutAction`, `CONFIG_VERSION`, etc.
- **AC12.5:** Test-only deps (`hypothesis`, `pytest`) under `[project.optional-dependencies] dev`, not runtime.

### R13. Public API Surface

**Acceptance Criteria:**
- **AC13.1:** `__all__` in `m7_schema_translators/__init__.py` contains exactly: `TRANSLATOR_REGISTRY`, `translate_to_canonical`, `translate_from_canonical`, `TranslationError`, `UnknownEnumValue`, `MissingRequiredField`, `TypeCoercionError`, `CostBasisUnmappable`, `VendorSchemaVersionMismatch`, `RoundTripDivergence`, `UnregisteredTranslator`, `ReconciliationNote`, `CostBasisSource`, `TranslatorPair`, `SCHEMA_VERSION`, `VALID_REASON_CODES`.
- **AC13.2:** `translate_to_canonical(source_system: str, canonical_type: str, vendor_payload: dict) -> tuple[BaseModel, ReconciliationNote]`. **Explicit parameters — no reach into `req.target.*` (v0.2.0 fix).** Unregistered pair → `UnregisteredTranslator`.
- **AC13.3:** `translate_from_canonical(source_system: str, canonical_type: str, canonical: BaseModel) -> tuple[BaseModel, ReconciliationNote]` — symmetric.
- **AC13.4:** Vendor sub-packages NOT in `__all__`, NOT imported at top level. Consumers use the dispatcher.
- **AC13.5:** `SCHEMA_VERSION = "0.1.0"` at M7 package level (distinct from per-translator).
- **AC13.6:** `translate_to_canonical` validates `source_system` against `SourceSystem` enum and `canonical_type` against `CANONICAL_TYPES` before dispatch. Invalid → `UnregisteredTranslator` with `valid_source_systems` / `valid_canonical_types` in details.
- **AC13.7:** Registry construction is EAGER at package import (fail-closed — partial registry worse than no M7).

### R14. Security Invariants (Steering Rule 32)

**Acceptance Criteria:**
- **AC14.1:** Zero credentials (AST + literal scan: no `api_key`, `secret`, `password`, `token`, `bearer`, `oauth` string-literal assignments).
- **AC14.2:** `TranslationError` messages contain only `reason_code`, `vendor`, `canonical_type`, `field_path`, `valid_values`. Test scans `str(exc)` AND `exc.details` JSON for PII.
- **AC14.3:** `logging` NOT imported under `src/m7_schema_translators/`.
- **AC14.4:** Forbidden imports (v0.2.0 expanded): `os.environ`, `sys.path`, `pathlib.Path.open`, `open(`, `io.open`, `os.open`, `tempfile`, `socket`, `urllib`, `httpx`, `requests`, `subprocess`, **`warnings`** (leaks to stderr).
- **AC14.5:** PII-marked fields (per M3 `PII_FIELDS`) carried through unchanged.
- **AC14.6:** Security test iterates `TRANSLATOR_REGISTRY`, runs each against PII fixture, asserts no PII in `ReconciliationNote` string AND no PII in `TranslationError.details` JSON serialization.
- **AC14.7:** `TranslationError.details` values are strings, ints, or Optional thereof (per TypedDicts). No nested vendor payloads. No canonical models.
- **AC14.8 (enum-value sanitization invariant):** `UnknownEnumDetails.vendor_value` and `CostBasisUnmappableDetails.vendor_value` always match `^[A-Za-z0-9_ .\-]+$` (enum-friendly, PII-impossible).
- **AC14.9 (fixture PII scan):** Task 19 scans all `tests/schema-reconciliation/fixtures/**/*.json` for PII-shaped tokens. Fails CI on:
  - Email TLDs other than `.example`, `.invalid`, `.test`, `.localhost`
  - SSN-shaped `\b\d{3}-\d{2}-\d{4}\b`
  - Phone-shaped without `555-` prefix
  - IBAN-shaped without `TEST` prefix
  - CUSIP-shaped flagged for SME review

### R15. DECISION-LOG Maintenance

**Acceptance Criteria:**
- **AC15.1:** Entries include Date, Vendor, Canonical Type, Field, Decision, Rationale, Decided By.
- **AC15.2:** Every non-1:1 enum mapping documented.
- **AC15.3:** Every `LOSSY_FIELDS` / `REVERSE_LOSSY_FIELDS` entry documented with rationale.
- **AC15.4:** Every `COST_BASIS_DEFAULTS` entry documented per `(vendor, account_type_group, security_class)` tuple.
- **AC15.5:** DECISION-LOG cross-references M3 DECISION-LOG pending items (Holding.accrued_interest, SecurityIdentifier.canonical_id, Performance.methodology).
- **AC15.6:** DECISION-LOG includes entry for SF FSC field-name PENDING-VERIFICATION with owner assignment.

### R16. Cross-Module Observability Contract (NEW in v0.2.0)

**Rationale:** v0.1.0 Gap dimension flagged that M6 cannot log `UnknownEnumValue(vendor_value="RARE")` details without M7 surfacing them via `details`. R16 pins the details-shape contract + M6's propagation obligation to M10.

**Acceptance Criteria:**
- **AC16.1 (M7 side):** Every `TranslationError.details` contains ONLY the allow-listed keys per AC4.8. No raw vendor payload, no canonical model dump, no PII.
- **AC16.2 (M6 propagation):** M6 Phase 2 spec amendment MUST propagate `TranslationError.details` as-is into M10 `AuditEntry.payload["translation_error_details"]` so M10 can aggregate failure rates per `(vendor, canonical_type, field_path, reason_code, vendor_value)`. M6 does NOT transform or filter `details`.
- **AC16.3 (M10 aggregation):** OUT OF SCOPE for M7. M10 owns failure-rate dashboards.
- **AC16.4 (test):** `tests/unit/test_m7_observability_contract.py` — for every `TranslationError` subclass, instantiate a canonical example, assert `details` is JSON-serializable, matches per-subclass TypedDict (AC4.8), passes PII-free scan (AC14.6).

---

## Cost Basis Normalization Matrix

Per Steering Rule 16, `cost_basis_method` on canonical TaxLot is NEVER null. This matrix is the authoritative source of vendor → canonical mappings and defaults.

### Vendor String → Canonical Enum (`COST_BASIS_VENDOR_MAP`)

| Vendor | Vendor Native String | Canonical `CostBasisMethod` | Notes |
|--------|---------------------|-----------------------------|-------|
| schwab | `"SpecificLot"` | `specific_lot` | Schwab default for US taxable equity |
| schwab | `"SL"` | `specific_lot` | Schwab short form (daily file) |
| schwab | `"AverageCost"` | `average_cost` | Schwab for mutual funds |
| schwab | `"AC"` | `average_cost` | Schwab short form |
| schwab | `"FIFO"` | `fifo` | — |
| schwab | `"LIFO"` | `lifo` | — |
| schwab | `"HIFO"` | `hifo` | Highest-in-first-out (tax-loss harvesting) |
| schwab | `"MinTax"` | `hifo` | Schwab's tax-optimized label maps to HIFO |
| orion | `"SPECIFIC_LOT"` | `specific_lot` | Orion uses snake_case uppercase |
| orion | `"AVG_COST"` | `average_cost` | Orion abbreviation |
| orion | `"FIFO"` | `fifo` | — |
| orion | `"LIFO"` | `lifo` | — |
| orion | `"HIFO"` | `hifo` | — |

### Vendor Default Table (`COST_BASIS_DEFAULTS`)

Applied when vendor payload omits the cost basis method. Keyed by `(vendor, account_type_group, security_class)`. `account_type_group` grouped as `{"taxable", "retirement", "trust", "custodial"}`.

| Vendor | Account Type Group | Security Class | Default `CostBasisMethod` | Rationale |
|--------|-------------------|----------------|---------------------------|-----------|
| schwab | taxable | equity | `specific_lot` | Schwab US default post-2011 |
| schwab | taxable | mutual_fund | `average_cost` | IRS covered securities rule |
| schwab | taxable | etf | `specific_lot` | — |
| schwab | retirement | * | `fifo` | No tax impact on retirement; vendor sorts FIFO |
| orion | taxable | equity | `specific_lot` | Orion follows custodian |
| orion | taxable | mutual_fund | `average_cost` | — |
| orion | retirement | * | `fifo` | — |

### Fail-Closed Cases (raise `CostBasisUnmappable`)

| Condition | Example | Required Exception |
|-----------|---------|--------------------|
| Vendor reports unknown string | Schwab returns `"Other"` | `CostBasisUnmappable(reason_code="unsupported_vendor_value", details={"vendor_value":"Other", ...})` |
| No vendor string + unmapped default | Schwab + account_type_group=`trust` + security_class=`alternative` | `CostBasisUnmappable(reason_code="cost_basis_unmappable", details={"vendor_value": None, "account_type_group":"trust", "security_class":"alternative", ...})` |
| Vendor string + cross-jurisdictional ambiguity | Schwab UK account reports `"SpecificLot"` but UK uses FIFO by default | `CostBasisUnmappable(reason_code="ambiguous_mapping", details={"jurisdiction":"UK", "vendor_value":"SpecificLot", ...})` — PENDING SME, fixture `@pytest.mark.xfail(reason="Schwab UK PENDING SME — IMPL-06 follow-up")` |
| Missing security class and unknown account type | `account_type=None, security_class=None` | `CostBasisUnmappable(reason_code="cost_basis_unmappable", details={"vendor_value": None, "account_type_group": None, "security_class": None, "jurisdiction": None})` |

---

## Vendor Enum Mapping Matrix

Every canonical enum field any Phase 2 translator populates. Authoritative source for `ENUM_MAPPINGS` per translator.

### Salesforce FSC → canonical

| Canonical Field | Canonical Enum | Vendor String | Canonical Value | Primary for Reverse? |
|----------------|----------------|---------------|-----------------|----------------------|
| Client.client_type | (constrained str w/ validator: individual,entity,trust) | `"PersonAccount"` | `individual` | yes |
| Client.client_type | (constrained str) | `"Business Account"` | `entity` | yes |
| Client.client_type | (constrained str) | `"Trust"` | `trust` | yes |
| Client.kyc_status | (constrained str) | `"Verified"` | `verified` | yes |
| Client.kyc_status | (constrained str) | `"Pending"` | `pending` | yes |
| Client.kyc_status | (constrained str) | `"Expired"` | `expired` | yes |
| Client.kyc_status | (constrained str) | `"Failed"` | `failed` | yes |
| Goal.goal_type | `GoalType` | `"Retirement"` | `retirement` | yes |
| Goal.goal_type | `GoalType` | `"Education"` | `education` | yes |
| Goal.goal_type | `GoalType` | `"Home Purchase"` | `home_purchase` | yes |
| Goal.goal_type | `GoalType` | `"Emergency Fund"` | `emergency_fund` | yes |
| Goal.goal_type | `GoalType` | `"Wealth Transfer"` | `wealth_transfer` | yes |
| Goal.goal_type | `GoalType` | `"Charitable Giving"` | `charitable_giving` | yes |
| Goal.goal_type | `GoalType` | `"Debt Payoff"` | `debt_payoff` | yes |
| Goal.goal_type | `GoalType` | `"Major Purchase"` | `major_purchase` | yes |
| Goal.goal_type | `GoalType` | `"Income Replacement"` | `income_replacement` | yes |
| Goal.goal_type | `GoalType` | `"Legacy"` | `legacy` | yes |
| Goal.goal_type | `GoalType` | `"Custom"` | `custom` | yes |
| Goal.status | `GoalStatus` | `"On Track"` | `on_track` | yes |
| Goal.status | `GoalStatus` | `"At Risk"` | `at_risk` | yes |
| Goal.status | `GoalStatus` | `"Behind"` | `behind` | yes |
| Goal.status | `GoalStatus` | `"Achieved"` | `achieved` | yes |
| Goal.status | `GoalStatus` | `"Abandoned"` | `abandoned` | yes |
| Household.member.role | (constrained str) | `"Primary"` | `primary` | yes |
| Household.member.role | (constrained str) | `"Spouse"` | `spouse` | yes |
| Household.member.role | (constrained str) | `"Dependent"` | `dependent` | yes |
| Household.member.role | (constrained str) | `"Trustee"` | `trustee` | yes |
| Household.member.role | (constrained str) | `"Beneficiary"` | `beneficiary` | yes |

### Orion → canonical

M3 `AccountType` SOT: `TAXABLE`, `TRADITIONAL_IRA`, `ROTH_IRA`, `K401`(value `"401k"`), `B403`(value `"403b"`), `B457`(value `"457"`), `SEP_IRA`, `SIMPLE_IRA`, `TRUST_REVOCABLE`, `TRUST_IRREVOCABLE`, `CUSTODIAL_UTMA`, `CUSTODIAL_UGMA`, `ERISA_PENSION`, `ERISA_PROFIT_SHARING`, `PLAN_529`, `HSA`. Steering Rule 10 uses outdated draft names — M3 is SOT (see Known Blockers).

| Canonical Field | Canonical Enum | Vendor String | Canonical Value | Notes |
|----------------|----------------|---------------|-----------------|-------|
| Holding.account_type | `AccountType` | `"TAXABLE"` | `taxable` | Orion uppercase |
| Holding.account_type | `AccountType` | `"TRADITIONAL_IRA"` | `traditional_ira` | — |
| Holding.account_type | `AccountType` | `"ROTH_IRA"` | `roth_ira` | — |
| Holding.account_type | `AccountType` | `"401K"` | `401k` | — |
| Holding.account_type | `AccountType` | `"403B"` | `403b` | — |
| Holding.account_type | `AccountType` | `"SEP_IRA"` | `sep_ira` | — |
| Holding.account_type | `AccountType` | `"SIMPLE_IRA"` | `simple_ira` | — |
| Holding.account_type | `AccountType` | `"TRUST"` | `trust_revocable` | Orion single TRUST → default `trust_revocable`. Discrepancy flagged in reconciliation note. |
| Holding.account_type | `AccountType` | `"UTMA"` | `custodial_utma` | — |
| Holding.account_type | `AccountType` | `"UGMA"` | `custodial_ugma` | — |
| Holding.account_type | `AccountType` | (no string) | — | **No Orion `"457"` / `"457B"` vendor string mapped in Phase 2 Lighthouse fixtures. First encounter → `UnknownEnumValue`, triggers MINOR translator bump with the new row.** |
| Transaction.transaction_type | `TransactionType` | `"BUY"` | `buy` | — |
| Transaction.transaction_type | `TransactionType` | `"SELL"` | `sell` | — |
| Transaction.transaction_type | `TransactionType` | `"SELL_SHORT"` | `sell_short` | — |
| Transaction.transaction_type | `TransactionType` | `"BUY_TO_COVER"` | `buy_to_cover` | — |
| Transaction.transaction_type | `TransactionType` | `"DIV"` | `dividend` | Orion abbreviation |
| Transaction.transaction_type | `TransactionType` | `"INT"` | `interest` | — |
| Transaction.transaction_type | `TransactionType` | `"FEE"` | `fee` | — |
| Transaction.transaction_type | `TransactionType` | `"MGMT_FEE"` | `management_fee` | — |
| Transaction.transaction_type | `TransactionType` | `"TRANSFER_IN"` | `transfer_in` | — |
| Transaction.transaction_type | `TransactionType` | `"TRANSFER_OUT"` | `transfer_out` | — |
| Transaction.transaction_type | `TransactionType` | `"DISTRIBUTION"` | `distribution` | — |
| Transaction.transaction_type | `TransactionType` | `"CONTRIBUTION"` | `contribution` | — |
| Transaction.transaction_type | `TransactionType` | `"WIRE_IN"` | `wire_in` | — |
| Transaction.transaction_type | `TransactionType` | `"WIRE_OUT"` | `wire_out` | — |
| Transaction.transaction_type | `TransactionType` | `"JOURNAL"` | `journal` | — |
| Transaction.transaction_type | `TransactionType` | `"REINVEST"` | `reinvestment` | — |
| Transaction.transaction_type | `TransactionType` | `"ROC"` | `return_of_capital` | — |
| Transaction.transaction_type | `TransactionType` | `"CORP_ACTION"` | `corporate_action` | — |
| Transaction.transaction_type | `TransactionType` | `"MARGIN_INT"` | `margin_interest` | — |
| Transaction.settlement_status | (constrained str) | `"PENDING"` | `pending` | — |
| Transaction.settlement_status | (constrained str) | `"SETTLED"` | `settled` | — |
| Transaction.settlement_status | (constrained str) | `"FAILED"` | `failed` | — |

### Schwab → canonical

| Canonical Field | Canonical Enum | Vendor String | Canonical Value | Notes |
|----------------|----------------|---------------|-----------------|-------|
| Holding.account_type | `AccountType` | `"INDIVIDUAL"` | `taxable` | Schwab individual brokerage → canonical taxable |
| Holding.account_type | `AccountType` | `"JOINT_TOS"` | `taxable` | Joint tenants maps to taxable |
| Holding.account_type | `AccountType` | `"IRA"` | `traditional_ira` | Schwab single IRA label → default traditional_ira. Flag in reconciliation. |
| Holding.account_type | `AccountType` | `"ROTH_IRA"` | `roth_ira` | — |
| Holding.account_type | `AccountType` | `"SEP"` | `sep_ira` | — |
| Holding.account_type | `AccountType` | `"SIMPLE"` | `simple_ira` | — |
| Holding.account_type | `AccountType` | `"401K"` | `401k` | — |
| Holding.account_type | `AccountType` | `"TRUST"` | `trust_revocable` | Same ambiguity as Orion |
| Holding.account_type | `AccountType` | `"UTMA"` | `custodial_utma` | — |
| Holding.account_type | `AccountType` | `"UGMA"` | `custodial_ugma` | — |
| Holding.account_type | `AccountType` | (no string) | — | **No Schwab `"457"` vendor string mapped in Phase 2 Lighthouse fixtures. First encounter → `UnknownEnumValue`, MINOR translator bump.** |
| TaxLot.holding_period | (constrained str) | `"ST"` | `short_term` | Schwab short form |
| TaxLot.holding_period | (constrained str) | `"LT"` | `long_term` | — |
| TaxLot.holding_period | (constrained str) | `"UNKNOWN"` | `unknown` | — |

### eMoney → canonical

| Canonical Field | Canonical Enum | Vendor String | Canonical Value | Notes |
|----------------|----------------|---------------|-----------------|-------|
| PlanSummary.plan_type | (constrained str) | `"Comprehensive"` | `comprehensive` | eMoney title case |
| PlanSummary.plan_type | (constrained str) | `"Retirement"` | `retirement_only` | — |
| PlanSummary.plan_type | (constrained str) | `"Education"` | `education_only` | — |
| PlanSummary.plan_type | (constrained str) | `"Estate"` | `estate` | — |
| PlanSummary.plan_type | (constrained str) | `"Tax"` | `tax` | — |
| PlanSummary.plan_type | (constrained str) | `"Insurance"` | `insurance` | — |

---

## Field-Level Vendor → Canonical Mapping (11 Translator Pairs)

For each translator, the full field mapping. `Derivation` = how the canonical value is computed **against the M3 type annotation** (see §M3 Alignment). `Lossy?` = whether the field is in `LOSSY_FIELDS` (excluded from forward round-trip equality). `Rev-Lossy?` = whether the field is in `REVERSE_LOSSY_FIELDS` (reverse direction cannot reconstruct it).

### T1: Salesforce FSC → Client

**Vendor Model:** `SalesforceFSCAccountContact` (Account + Contact joined by `PrimaryContactId`). SF FSC Account + Contact SObject v59.0.
**Canonical Type:** `m3.Client`
**UUID Namespace:** `CLIENT_NS` — `Client.canonical_id` (M3: `UUID`) = `uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")`
**LOSSY_FIELDS:** `{"salesforce_fsc_metadata", "created_by_salesforce", "last_activity_date_salesforce"}`
**REVERSE_LOSSY_FIELDS:** `{"Account.FinServ__CreatedBy.Name", "Account.LastActivityDate", "Account.FinServ__InternalMetadata__c"}` — reverse cannot reconstruct SF internal metadata that was never on the canonical Client.
**PENDING-VERIFICATION:** `FinServ__AccountIds__c`, `FinServ__HouseholdId__c`, `FinServ__ClientArchetype__c`, `FinServ__KYCStatus__c`, `FinServ__KYCLastCompleted__c`, `FinServ__LastSSNDigits__c`, `FinServ__TaxID__c` — assumed per generic FSC extension convention. Real-org SOQL verification is a pre-GA Task.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `Account.Id` | `source_id` | `str` | direct | no |
| — (const) | `source_system` | `str` | `"salesforce_fsc"` | no |
| `Account.Id` | `canonical_id` | `UUID` | `uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")` | no |
| `Account.Name` | `display_name` | `str` (min_length=1) | direct; empty/whitespace-only → `MissingRequiredField(reason_code="missing_required_field", field_path="Account.Name")` | no |
| `Account.RecordType.Name` | `client_type` | `str` (M3 validator: `{individual, entity, trust}`) | ENUM_MAPPINGS: PersonAccount→individual, Business Account→entity, Trust→trust | no |
| `Contact.FirstName` | `first_name` | `Optional[str]` | direct (individual only; `None` for entity/trust) | no |
| `Contact.LastName` | `last_name` | `Optional[str]` | direct (individual only) | no |
| `Contact.Email` | `email` | `Optional[str]` (PII) | direct — carry through unchanged. `None` preserved as `None` (AC10.9). | no |
| `Contact.Phone` | `phone` | `Optional[str]` (PII) | direct (PII) | no |
| `Contact.Birthdate` | `date_of_birth` | `Optional[date]` (PII) | direct ISO 8601 date | no |
| `Account.FinServ__KYCStatus__c` | `kyc_status` | `Optional[str]` | ENUM_MAPPINGS | no |
| `Account.FinServ__KYCLastCompleted__c` | `kyc_verified_date` | `Optional[date]` | direct date | no |
| `Account.FinServ__LastSSNDigits__c` | `ssn_last_four` | `Optional[str]` (PII) | direct 4-digit string | no |
| `Account.FinServ__TaxID__c` | `tax_id` | `Optional[str]` (PII) | direct (entity/trust only) | no |
| `Account.FinServ__RiskTolerance__c` | `risk_tolerance` | `Optional[str]` | direct constrained string | no |
| `Account.FinServ__InvestmentObjectives__c` | `investment_objectives` | `list[str]` | SF multi-picklist `;`-separated → `[s.strip() for s in value.split(";") if s.strip()]` | no |
| `Account.FinServ__TimeHorizon__c` | `time_horizon` | `Optional[str]` | direct | no |
| `Account.FinServ__AnnualIncome__c` | `annual_income_range` | `Optional[str]` | direct bucket string | no |
| `Account.FinServ__NetWorth__c` | `net_worth_range` | `Optional[str]` | direct | no |
| `Account.FinServ__LiquidNetWorth__c` | `liquid_net_worth_range` | `Optional[str]` | direct | no |
| `Account.FinServ__TaxBracket__c` | `tax_bracket` | `Optional[str]` | direct | no |
| `Account.OwnerId` | `advisor_ref` | `Optional[UUID]` | `uuid5(ADVISOR_NS, f"salesforce_fsc:{OwnerId}")` | no |
| `Account.FinServ__FirmId__c` | `firm_id` | `UUID` (REQUIRED) | `uuid5(FIRM_NS, value)` — missing vendor value → `MissingRequiredField(field_path="Account.FinServ__FirmId__c")` | no |
| `Account.FinServ__HouseholdId__c` | `household_ref` | `Optional[UUID]` | `uuid5(HOUSEHOLD_NS, f"salesforce_fsc:{value}")` | no |
| `Account.FinServ__ClientArchetype__c` | `archetype` | `Optional[str]` (NO M3 validator) | direct. **M7 does NOT validate {mass_affluent, hnw, uhnw}** — M3 has no validator for this field. An unknown value passes through as `str`. Documented in DECISION-LOG. | no |
| `Account.FinServ__Jurisdiction__c` | `jurisdiction` | `str` (REQUIRED) | direct ISO-3166 or subdivision | no |
| `Account.FinServ__AccountIds__c` | `accounts` | `list[UUID]` | `[uuid5(ACCOUNT_NS, f"salesforce_fsc:{aid.strip()}") for aid in value.split(";") if aid.strip()]` | no |
| `Account.FinServ__PIIClassification__c` | `pii_classification` | `Optional[str]` | direct | no |
| `Account.CreatedDate` | `created_at` | `datetime` | direct ISO datetime | no |
| `Account.LastModifiedDate` | `updated_at` | `datetime` | direct ISO datetime | no |
| `Account.Id` + `Contact.Id` + `Account.FinServ__PersonAccount__c` | `vendor_mappings.salesforce_fsc` | `Optional[ClientVendorSalesforceFSC]` | `ClientVendorSalesforceFSC(account_id=Account.Id, contact_id=Contact.Id, person_account=bool(Account.FinServ__PersonAccount__c))` | no |
| `Account.FinServ__CreatedBy.Name` | — (dropped) | — | internal metadata | YES |
| `Account.LastActivityDate` | — (dropped) | — | not mapped | YES |
| `Account.FinServ__InternalMetadata__c` | — (dropped) | — | internal extension field | YES |

**Reverse (from_canonical_client):** Canonical `Client` → `SalesforceFSCAccountContact`. Reverse-lossy: fields in `REVERSE_LOSSY_FIELDS` (SF-internal metadata) cannot be reconstructed; round-trip tests exclude them. `accounts: list[UUID]` reverse — canonical UUIDs → `"salesforce_fsc:{aid}"` form is NOT invertible to the raw SF Account Id; reverse stores the UUID-string in `FinServ__AccountIds__c` and a round-trip fixture carries `LOSSY_FIELDS` assertion.

**Person-Account vs Business-Account branching:** Business Account has NO Contact — `first_name`, `last_name`, `email`, `phone`, `date_of_birth` MUST be `None` when `client_type == "entity"`. Vendor model enforces this via `@model_validator(mode="after")`. Test `test_m7_roundtrip_salesforce_fsc_client.py` includes one Business Account fixture to exercise the branch.

---

### T2: Salesforce FSC → Household

**Vendor Model:** `SalesforceFSCHousehold` (FinServ__Household__c + FinServ__HouseholdMember__c list)
**Canonical Type:** `m3.Household`
**UUID Namespace:** `HOUSEHOLD_NS`
**LOSSY_FIELDS:** `{"sf_internal_fields", "sf_household_record_type_metadata"}`
**REVERSE_LOSSY_FIELDS:** `{"FinServ__Household__c.{internal_metadata,record_type_info}"}` — same as above.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `FinServ__Household__c.Id` | `source_id` (on container, via helper) | — | direct | no |
| `FinServ__Household__c.Id` | `canonical_id` | `UUID` | `uuid5(HOUSEHOLD_NS, f"salesforce_fsc:{Id}")` | no |
| `FinServ__Household__c.Name` | `display_name` | `str` | direct | no |
| — (const) | `primary_source` | `str` | `"salesforce_fsc"` | no |
| `FinServ__HouseholdMember__c[]` | `members[]` | `list[HouseholdMember]` | each → `HouseholdMember(client_ref=str(uuid5(CLIENT_NS, f"salesforce_fsc:{m.AccountId}")), role=ENUM_MAPPINGS["role"][m.Role__c], source="salesforce_fsc")`. **`client_ref` is `str` per M3 `HouseholdMember.client_ref: str` — NOT `UUID`.** | no |
| `FinServ__Household__c.FinServ__AccountIds__c` (PENDING-VERIFICATION) | `accounts[]` | `list[HouseholdAccount]` | `[HouseholdAccount(account_ref=str(uuid5(ACCOUNT_NS, f"salesforce_fsc:{aid.strip()}")), source="salesforce_fsc") for aid in split(";")]`. **`account_ref` is `str` per M3.** | no |
| `FinServ__Household__c.Id` | `vendor_mappings.salesforce_fsc` | `Optional[HouseholdVendorSFSC]` | `HouseholdVendorSFSC(household_id=Id, grouping_type="relationship")` — grouping_type CONST, asserted by test | no |
| — (caller) | `reconciliation` | `Optional[Reconciliation]` | Single-vendor: `None` (per AC7.8). Multi-vendor entry point sets it. | no |

**Multi-vendor entry point:** `to_canonical_household_multi(payloads: Mapping[str, dict], last_reconciled: datetime)` — accepts any subset of `{salesforce_fsc, orion, schwab}`. Merges member lists preserving source attribution. `_compare_household_members` populates reconciliation per AC7.5 format literal.

**Reverse:** `from_canonical_household(canonical, vendor="salesforce_fsc")` produces `SalesforceFSCHousehold` ONLY if `canonical.vendor_mappings.salesforce_fsc is not None`. Otherwise `(None, note)` per AC7.6.

---

### T3: Salesforce FSC → Goal

**Vendor Model:** `SalesforceFSCFinancialGoal` (FinServ__FinancialGoal__c)
**Canonical Type:** `m3.Goal`
**UUID Namespace:** `GOAL_NS`
**LOSSY_FIELDS:** `{"sf_goal_created_by", "sf_goal_last_modified_by", "sf_custom_picklist_raw"}`
**REVERSE_LOSSY_FIELDS:** `{"funding_pct"}` — canonical `funding_pct` is DERIVED from `target_amount` / `current_amount`; reverse can only write the two primitives, not the derivation result.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `FinServ__FinancialGoal__c.Id` | `source_id` (helper) / `canonical_id` | `str` / `UUID` | `uuid5(GOAL_NS, f"salesforce_fsc:{Id}")`; `source_id = Id` | no |
| `FinServ__FinancialGoal__c.FinServ__PrimaryClient__c` | `client_ref` | `UUID` (REQUIRED) | `uuid5(CLIENT_NS, f"salesforce_fsc:{value}")` | no |
| `FinServ__FinancialGoal__c.FinServ__Household__c` | `household_ref` | `Optional[UUID]` | `uuid5(HOUSEHOLD_NS, f"salesforce_fsc:{value}")` when present | no |
| — | `plan_ref` | `Optional[UUID]` | `None` (SF FSC goals not linked to plans) | no |
| `FinServ__FinancialGoal__c.FinServ__GoalType__c` | `goal_type` | `GoalType` (enum) | ENUM_MAPPINGS | no |
| `FinServ__FinancialGoal__c.Name` | `goal_name` | `str` | direct | no |
| `FinServ__FinancialGoal__c.FinServ__TargetAmount__c` | `target_amount` | `float` (ge=0) | direct | no |
| `FinServ__FinancialGoal__c.FinServ__CurrentAmount__c` | `current_amount` | `Optional[float]` (ge=0) | direct | no |
| (computed) | `funding_pct` | `Optional[float]` (ge=0, le=100) | `current_amount / target_amount * 100` if both present and target_amount>0, else `None`. In `fields_derived`. **Reverse-lossy.** | no on forward; YES on reverse |
| `FinServ__FinancialGoal__c.FinServ__TargetDate__c` | `target_date` | `date` | direct date | no |
| `FinServ__FinancialGoal__c.FinServ__Priority__c` | `priority` | `str` | direct constrained string | no |
| `FinServ__FinancialGoal__c.FinServ__Status__c` | `status` | `GoalStatus` | ENUM_MAPPINGS | no |
| `FinServ__FinancialGoal__c.FinServ__MonthlyContribution__c` | `monthly_contribution` | `Optional[float]` (ge=0) | direct | no |
| `FinServ__FinancialGoal__c.FinServ__LinkedAccounts__c` | `linked_accounts[]` | `list[UUID]` | `[uuid5(ACCOUNT_NS, f"salesforce_fsc:{aid.strip()}") for aid in split(";")]` | no |
| `FinServ__FinancialGoal__c.FinServ__{Inflation,Return,Tax}Rate__c` | `assumptions` | `Optional[GoalAssumptions]` | `GoalAssumptions(inflation_rate=…, return_rate=…, tax_rate=…)` | no |
| `FinServ__FinancialGoal__c.Id` + `GoalType__c` | `vendor_mappings.salesforce_fsc` | `Optional[GoalVendorSFSC]` | `GoalVendorSFSC(financial_goal_id=Id, goal_type_picklist=vendor_goal_type_raw)` | no |
| `FinServ__FinancialGoal__c.LastModifiedDate` | `as_of_date` | `date` | truncate datetime → date | no |
| `FinServ__FinancialGoal__c.CreatedDate` | `created_at` | `datetime` | direct | no |
| `FinServ__FinancialGoal__c.LastModifiedDate` | `updated_at` | `datetime` | direct | no |

---

### T4: Orion → Holding

**Vendor Model:** `OrionPosition` (Orion Connect REST API v2.0 Position)
**Canonical Type:** `m3.Holding`
**UUID Namespace:** `HOLDING_NS` — `Holding.canonical_id` is `UUID`
**LOSSY_FIELDS:** `{"orion_internal_position_id", "orion_benchmark_id", "orion_custom_attributes"}`
**REVERSE_LOSSY_FIELDS:** `{"Position.internalPositionId", "Position.benchmarkId", "Position.customAttributes"}` — vendor-internal fields that canonical does not carry.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `Position.positionId` | `source_id` | `str` | direct | no |
| — (const) | `source_system` | `str` | `"orion"` | no |
| `Position.positionId` | `canonical_id` | `UUID` | `uuid5(HOLDING_NS, f"orion:{positionId}")` | no |
| `Position.accountId` | `account_ref` | **`str`** (M3: `Holding.account_ref: str`) | **`str(uuid5(ACCOUNT_NS, f"orion:{accountId}"))`** | no |
| `Position.clientId` | `client_ref` | **`Optional[str]`** (M3) | **`str(uuid5(CLIENT_NS, f"orion:{clientId}"))`** when present, else `None` | no |
| `Position.ticker` + `cusip` + `isin` + `figi` | `security_identifier` | `Optional[SecurityIdentifier]` | `SecurityIdentifier(ticker=…, cusip=…, isin=…, figi=…)` | no |
| `Position.securityName` | `security_name` | `Optional[str]` | direct | no |
| `Position.securityType` | `security_type` | `Optional[str]` | direct | no |
| `Position.quantity` | `quantity` | `float` | direct | no |
| `Position.marketValue` | `market_value` | `float` | direct | no |
| `Position.includesAccruedInterest` | `market_value_includes_accrued` | `Optional[bool]` | direct bool (Orion explicit) | no |
| `Position.costBasis` | `cost_basis` | `Optional[float]` | direct | no |
| `Position.unrealizedGainLoss` | `unrealized_gain_loss` | `Optional[float]` | direct | no |
| `Position.unrealizedGainLossPct` | `unrealized_gain_loss_pct` | `Optional[float]` | direct | no |
| `Position.weightInAccount` | `weight_in_account` | `Optional[float]` | direct | no |
| `Position.currency` | `currency` | `Optional[str]` (default USD) | direct ISO 4217 | no |
| `Position.asOfDate` | `as_of_date` | `date` (REQUIRED) | direct ISO 8601 date | no |
| `Position.accountType` | `account_type` | `Optional[AccountType]` | ENUM_MAPPINGS | no |
| `Position.positionId` | `source_id` | `str` | raw vendor ID | no |
| `Position.taxLots[]` | `tax_lots[]` | `list[TaxLot]` | each → `to_canonical_taxlot_orion(lot, parent_position_id=positionId)`; empty list when vendor returns no lots (M3 default) | no |
| `Position.internalPositionId` | — (dropped) | — | internal | YES |
| `Position.benchmarkId` | — (dropped) | — | out of scope | YES |
| `Position.customAttributes` | — (dropped) | — | firm-specific extension | YES |

**Partial-data rule:** Orion Position with NO `taxLots[]` → canonical `tax_lots=[]` (M3 `list[TaxLot] = Field(default_factory=list)`). Documented explicitly per review gap item.

---

### T5: Orion → Transaction

**Vendor Model:** `OrionTransaction` (Orion Connect REST API v2.0 Transaction)
**Canonical Type:** `m3.Transaction`
**UUID Namespaces:** `TRANSACTION_NS`, `ACCOUNT_NS`, `CLIENT_NS`, `ORDER_NS` (all **UUID** — Transaction is the one place where M3 uses UUID for refs, not str)
**LOSSY_FIELDS:** `{"orion_lot_allocation_detail", "orion_internal_memo", "orion_reversal_flag"}`
**REVERSE_LOSSY_FIELDS:** `{"Transaction.lotAllocationDetail", "Transaction.internalMemo", "Transaction.reversalFlag"}` — vendor-internal fields canonical does not carry.

**CRITICAL FIX (v0.2.0):** `transaction_id` and `source_id` are TWO SEPARATE fields in M3. Never collapse.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `Transaction.transactionId` | `transaction_id` | **`UUID`** (REQUIRED, primary key) | **`uuid5(TRANSACTION_NS, f"orion:{transactionId}")`** — bare UUID, not str | no |
| `Transaction.transactionId` | `source_id` | **`str`** (vendor-native ID, separate field) | **direct (raw vendor string)** | no |
| — (const) | `source_system` | `str` | `"orion"` | no |
| `Transaction.accountId` | `account_ref` | **`UUID`** (M3: `Transaction.account_ref: UUID`) | **`uuid5(ACCOUNT_NS, f"orion:{accountId}")`** — bare UUID | no |
| `Transaction.clientId` | `client_ref` | **`Optional[UUID]`** | **`uuid5(CLIENT_NS, f"orion:{clientId}")`** when present, else `None` | no |
| — | `order_ref` | `Optional[UUID]` | `None` (Orion doesn't track 007 orders). Documented in CHANGELOG. | no |
| `Transaction.type` | `transaction_type` | `TransactionType` (enum) | ENUM_MAPPINGS (Orion abbrevs) | no |
| `Transaction.ticker` + identifiers | `security_identifier` | `Optional[SecurityIdentifier]` | `SecurityIdentifier(...)` (`None` for cash transactions) | no |
| `Transaction.securityName` | `security_name` | `Optional[str]` | direct | no |
| `Transaction.quantity` | `quantity` | `Optional[float]` | direct (`None` for cash) | no |
| `Transaction.price` | `price` | `Optional[float]` | direct | no |
| `Transaction.amount` | `amount` | `float` (REQUIRED) | direct | no |
| `Transaction.commission` | `commission` | `Optional[float]` | direct | no |
| `Transaction.fees` | `fees` | `Optional[float]` | direct | no |
| `Transaction.netAmount` | `net_amount` | `Optional[float]` | direct | no |
| `Transaction.tradeDate` | `trade_date` | `date` (REQUIRED) | direct | no |
| `Transaction.settlementDate` | `settlement_date` | `Optional[date]` | direct | no |
| `Transaction.settlementStatus` | `settlement_status` | `Optional[str]` | ENUM_MAPPINGS | no |
| `Transaction.currency` | `currency` | `Optional[str]` | direct | no |
| `Transaction.description` | `description` | `Optional[str]` | direct | no |
| `Transaction.taxLotId` | `tax_lot_ref` | `Optional[str]` | direct string (M3: `str`) | no |
| `Transaction.{realizedGainLoss,holdingPeriod,washSaleDisallowed}` | `cost_basis_impact` | `Optional[CostBasisImpact]` | `CostBasisImpact(realized_gain_loss=…, holding_period=…, wash_sale_disallowed=…)` | no |
| `Transaction.accountType` | `account_type` | `Optional[AccountType]` | ENUM_MAPPINGS | no |
| `Transaction.type` (vendor native) | `source_transaction_type` | `Optional[str]` | direct (audit reconciliation) | no |
| `Transaction.createdAt` | `created_at` | `datetime` | direct | no |
| — (caller-set) | `trace_id` | `Optional[str]` | Not set by M7. M6 attaches `trace_id` to canonical models outside the translator. Documented in DECISION-LOG. | no |

**Reverse `order_ref` handling:** When canonical `order_ref` is set (Transaction originated from a 007 Order), `from_canonical_transaction_orion` stores the order_ref UUID-string in `Transaction.customAttributes["order_ref"]` (a vendor extension field) AND marks it in `ReconciliationNote.notes` with the safe token `"canonical_order_ref_preserved_in_custom_attributes"`. Round-trip test asserts canonical `order_ref` survives forward → reverse → forward.

---

### T6: Orion → Household (EXPLICIT TABLE — was "analogous to T2" in v0.1.0)

**Vendor Model:** `OrionHousehold` (Orion calls this "portfolio management" grouping — `Household` object in Orion REST v2.0)
**Canonical Type:** `m3.Household`
**UUID Namespace:** `HOUSEHOLD_NS`
**LOSSY_FIELDS:** `{"orion_portfolio_ids", "orion_benchmark_assignment", "orion_composite_membership"}`
**REVERSE_LOSSY_FIELDS:** `{"OrionHousehold.portfolioIds", "OrionHousehold.benchmarkAssignment", "OrionHousehold.compositeMembership"}` — Orion-internal grouping metadata canonical does not carry.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `OrionHousehold.householdId` | `source_id` (helper) | `str` | direct | no |
| `OrionHousehold.householdId` | `canonical_id` | `UUID` | `uuid5(HOUSEHOLD_NS, f"orion:{householdId}")` | no |
| `OrionHousehold.householdName` | `display_name` | `str` (REQUIRED) | direct | no |
| — (const) | `primary_source` | `str` | `"orion"` | no |
| `OrionHousehold.members[].clientId` + `.role` | `members[]` | `list[HouseholdMember]` | each → `HouseholdMember(client_ref=str(uuid5(CLIENT_NS, f"orion:{m.clientId}")), role=ENUM_MAPPINGS["role"][m.role], source="orion")`. **`client_ref` is `str` per M3.** | no |
| `OrionHousehold.linkedAccounts[]` (each is `{"accountId": ...}`) | `accounts[]` | `list[HouseholdAccount]` | `[HouseholdAccount(account_ref=str(uuid5(ACCOUNT_NS, f"orion:{a.accountId}")), source="orion") for a in linkedAccounts]`. **`account_ref` is `str` per M3.** | no |
| `OrionHousehold.householdId` | `vendor_mappings.orion` | `Optional[HouseholdVendorOrion]` | `HouseholdVendorOrion(household_id=householdId, grouping_type="portfolio_management")` — grouping_type CONST, test-asserted | no |
| — (single-vendor) | `reconciliation` | `Optional[Reconciliation]` | `None` per AC7.8 | no |
| `OrionHousehold.portfolioIds` | — (dropped) | — | Orion-internal grouping metadata, not represented canonically | YES |
| `OrionHousehold.benchmarkAssignment` | — (dropped) | — | out of scope | YES |
| `OrionHousehold.compositeMembership` | — (dropped) | — | out of scope | YES |

**Role mapping:** `"primary"` → `primary`, `"spouse"` → `spouse`, `"dependent"` → `dependent`, `"trustee"` → `trustee`, `"beneficiary"` → `beneficiary` (Orion uses lowercase — SF FSC uses title case; ENUM_MAPPINGS handles both).

---

### T7: eMoney → PlanSummary

**Vendor Model:** `EMoneyPlanSummary` (eMoney API v2 Plan — SUMMARY fields only, no full plan body)
**Canonical Type:** `m3.PlanSummary`
**UUID Namespace:** `PLAN_NS`
**LOSSY_FIELDS:** `{"emoney_full_plan_body", "emoney_scenarios_detail", "emoney_cashflow_projection_yearly", "emoney_asset_allocation_history"}` — vendor fields the vendor model REJECTS at ingestion.
**REVERSE_LOSSY_FIELDS:** `{"net_worth", "EMoney.scenariosDetail", "EMoney.cashflowProjection"}` — canonical `net_worth` is derived from `total_assets - total_liabilities`; eMoney does not accept it as input.

DECISION-LOG rationale: "eMoney full plan body is intentionally NOT mapped; raw plan data never crosses M7 boundary per M4 MNPI policy. The vendor model does not even DEFINE these fields — they are excluded at ingestion in M11 AND rejected by `EMoneyPlanSummary` via `extra='forbid'`."

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `Plan.planId` | `source_id` / `canonical_id` | `str` / `UUID` | `canonical_id = uuid5(PLAN_NS, f"emoney:{planId}")`; `source_id = planId` | no |
| — (const) | `source_system` | `str` | `"emoney"` | no |
| `Plan.clientId` | `client_ref` | `UUID` (REQUIRED) | `uuid5(CLIENT_NS, f"emoney:{clientId}")`; missing → `MissingRequiredField` | no |
| `Plan.householdId` | `household_ref` | `Optional[UUID]` | `uuid5(HOUSEHOLD_NS, f"emoney:{value}")` when present | no |
| `Plan.planName` | `plan_name` | `str` | direct | no |
| `Plan.planType` | `plan_type` | `Optional[str]` | ENUM_MAPPINGS | no |
| `Plan.probabilityOfSuccess` | `probability_of_success` | `float` (ge=0, le=100, REQUIRED) | direct float 0-100; out-of-range vendor value → `TypeCoercionError(reason_code="type_coercion_failed", field_path="Plan.probabilityOfSuccess", details={"expected_type": "float in [0,100]", "got_type": "float out of range"})` | no |
| `Plan.asOfDate` | `as_of_date` | `date` | direct date | no |
| `Plan.totalAssets` | `total_assets` | `Optional[float]` (ge=0) | direct | no |
| `Plan.totalLiabilities` | `total_liabilities` | `Optional[float]` (ge=0) | direct | no |
| (computed) | `net_worth` | `Optional[float]` | `total_assets - total_liabilities` if both present, else `None`. In `fields_derived`. **Reverse-lossy.** | no forward; YES reverse |
| `Plan.retirementGoal.amount` | `retirement_goal_amount` | `Optional[float]` (ge=0) | direct | no |
| `Plan.retirementGoal.targetDate` | `retirement_target_date` | `Optional[date]` | direct date | no |
| `Plan.retirementGoal.incomeGap` | `retirement_income_gap` | `Optional[float]` | direct (negative = surplus) | no |
| `Plan.monteCarlo.successPct` | `monte_carlo_success_pct` | `Optional[float]` (ge=0, le=100) | direct | no |
| `Plan.monteCarlo.iterations` | `monte_carlo_iterations` | `Optional[int]` | direct | no |
| `Plan.annualSavingsRate` | `annual_savings_rate` | `Optional[float]` (ge=0) | direct decimal | no |
| `Plan.annualSpending` | `annual_spending` | `Optional[float]` (ge=0) | direct | no |
| `Plan.socialSecurityEstimate` | `social_security_estimate` | `Optional[float]` (ge=0) | direct | no |
| `Plan.pensionIncome` | `pension_income` | `Optional[float]` (ge=0) | direct | no |
| `Plan.goalIds[]` | `goals` | `list[UUID]` | `[uuid5(GOAL_NS, f"emoney:{gid}") for gid in goalIds]` | no |
| `Plan.assumptions.{inflation,returnAssumption,lifeExpectancy,retirementAge,taxRate}` | `assumptions` | `Optional[PlanAssumptions]` | `PlanAssumptions(...)` | no |
| `Plan.recommendations[]` | `recommendations[]` | `list[PlanRecommendation]` | each → `PlanRecommendation(category, description, priority)` — SUMMARY ONLY | no |
| `Plan.planId` + `scenarioId` | `vendor_mappings.emoney` | `Optional[PlanVendorMappings]` → `emoney` | `PlanVendorEMoney(plan_id=planId, scenario_id=scenarioId)` | no |
| `Plan.createdAt` | `created_at` | `datetime` | direct | no |
| `Plan.updatedAt` | `updated_at` | `datetime` | direct | no |

---

### T8: Schwab → Holding

**Vendor Model:** `SchwabPosition` (Schwab Trader API v1 Position)
**Canonical Type:** `m3.Holding`
**UUID Namespace:** `HOLDING_NS`
**VENDOR_API_VERSION:** `"v1"` (Schwab URL path versioning — v0.2.0 fix)
**LOSSY_FIELDS:** `{"schwab_internal_position_metadata", "schwab_asset_subclass", "schwab_symbol_type_code"}`
**REVERSE_LOSSY_FIELDS:** `{"position.internalMetadata", "position.assetSubclass", "position.symbolTypeCode", "market_value_includes_accrued"}` — canonical `market_value_includes_accrued=False` is DERIVED (Schwab convention); Schwab has no explicit field to reverse-write to.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `position.id` | `source_id` / `canonical_id` | `str` / `UUID` | `canonical_id = uuid5(HOLDING_NS, f"schwab:{id}")`; `source_id = id` | no |
| — (const) | `source_system` | `str` | `"schwab"` | no |
| `position.accountNumber` | `account_ref` | **`str`** (M3) | **`str(uuid5(ACCOUNT_NS, f"schwab:{accountNumber}"))`** | no |
| `position.accountHolderId` | `client_ref` | **`Optional[str]`** | **`str(uuid5(CLIENT_NS, f"schwab:{accountHolderId}"))`** when present | no |
| `position.symbol` + `cusip` + `isin` | `security_identifier` | `Optional[SecurityIdentifier]` | `SecurityIdentifier(ticker=symbol, cusip=..., isin=...)` | no |
| `position.description` | `security_name` | `Optional[str]` | direct | no |
| `position.assetClass` | `security_type` | `Optional[str]` | direct (Schwab `EQUITY`, `FIXED_INCOME` — lowercased) | no |
| `position.quantity` | `quantity` | `float` | direct | no |
| `position.marketValue` | `market_value` | `float` | direct. Schwab `marketValue` EXCLUDES accrued interest by default. | no |
| — (const) | `market_value_includes_accrued` | `Optional[bool]` | `False` — DERIVED (Schwab convention); noted in `fields_derived`. **Reverse-lossy.** | no forward; YES reverse |
| `position.costBasis` | `cost_basis` | `Optional[float]` | direct. Schwab may return string with `"$"` prefix — vendor model `@field_validator("costBasis", mode="before")` strips `"$"` and `","`. Non-numeric after strip → `TypeCoercionError(field_path="position.costBasis")`. | no |
| `position.unrealizedGainLoss` | `unrealized_gain_loss` | `Optional[float]` | direct | no |
| `position.unrealizedGainLossPct` | `unrealized_gain_loss_pct` | `Optional[float]` | Schwab returns decimal; multiply by 100 per Schwab docs — DERIVED, in `fields_derived` | no |
| — (not returned) | `weight_in_account` | `Optional[float]` | `None` | no |
| `position.currency` | `currency` | `Optional[str]` | direct, default USD | no |
| `position.asOfDate` | `as_of_date` | `date` | direct date | no |
| `position.accountType` | `account_type` | `Optional[AccountType]` | ENUM_MAPPINGS | no |
| `position.taxLots[]` | `tax_lots[]` | `list[TaxLot]` | each → `to_canonical_taxlot_schwab(lot, parent_position_id=position.id)` | no |

**Schwab `$` prefix handling:** Vendor model `@field_validator("costBasis", "marketValue", "unrealizedGainLoss", mode="before")` strips `"$"` and `","` (`value.replace("$", "").replace(",", "").strip()`). Documented in DECISION-LOG.

---

### T9: Schwab → TaxLot

**Vendor Model:** `SchwabTaxLot` (nested in SchwabPosition)
**Canonical Type:** `m3.TaxLot`
**UUID Namespaces:** `TAXLOT_NS` (`TaxLot.lot_id: UUID`), derived `HOLDING_NS` for `holding_ref` (str)
**LOSSY_FIELDS:** `{"schwab_lot_internal_id", "schwab_lot_source_trade_ref"}`
**REVERSE_LOSSY_FIELDS:** `{"TaxLot.internalLotId", "TaxLot.sourceTradeRef"}` — Schwab-internal fields canonical does not carry.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `TaxLot.lotId` | `lot_id` | `UUID` (REQUIRED) | `uuid5(TAXLOT_NS, f"schwab:{lotId}")` | no |
| (parent position id) | `holding_ref` | **`str`** (M3) | **`str(uuid5(HOLDING_NS, f"schwab:{parent_position_id}"))`** — passed from caller (`to_canonical_taxlot_schwab(lot, parent_position_id=...)`) | no |
| `TaxLot.symbol` | `security_ref` | `Optional[str]` | direct ticker string (SecurityProfile lookup deferred) | no |
| `TaxLot.acquisitionDate` | `acquisition_date` | `date` (REQUIRED) | direct date | no |
| `TaxLot.acquisitionPrice` | `acquisition_price` | `Optional[float]` | direct; vendor-model `$`-strip validator handles string inputs | no |
| `TaxLot.quantity` | `quantity` | `float` (REQUIRED) | direct | no |
| `TaxLot.costBasisMethod` | `cost_basis_method` | `CostBasisMethod` (REQUIRED, never null per M3 validator) | **CRITICAL (Steering Rule 16)** — `normalize_cost_basis_method(vendor_string=lot.costBasisMethod, vendor="schwab", account_type=parent.accountType, security_class=parent.assetClass, jurisdiction=parent.jurisdiction)`. Vendor silent → `COST_BASIS_DEFAULTS`. **NEVER NULL.** Emits `ReconciliationNote.cost_basis_source`. | no |
| `TaxLot.costBasisAmount` | `cost_basis_amount` | `float` | direct float (`$`-strip) | no |
| `TaxLot.holdingPeriod` | `holding_period` | `Optional[str]` | ENUM_MAPPINGS (ST/LT/UNKNOWN) | no |
| `TaxLot.unrealizedGainLoss` | `unrealized_gain_loss` | `Optional[float]` | direct | no |
| `TaxLot.washSaleDisallowed` | `wash_sale_disallowed` | `Optional[float]` | direct | no |
| — (const) | `source_custodian` | `str` | `"schwab"` | no |
| `TaxLot.costBasisMethod` (vendor raw) | `source_cost_basis_method` | `Optional[str]` | **direct vendor string when vendor reported; `None` when vendor silent (provenance lives in `ReconciliationNote.cost_basis_source.method_origin == "vendor_default"`).** v0.2.0 fix to the T9/Task 12 contradiction. | no |

**Schwab UK xfail fixture skeleton:**
```python
@pytest.mark.xfail(reason="Schwab UK cost-basis PENDING SME — IMPL-06 follow-up")
def test_schwab_uk_specific_lot_ambiguous():
    lot = {"costBasisMethod": "SpecificLot", ...}
    parent = {"accountType": "INDIVIDUAL", "assetClass": "EQUITY", "jurisdiction": "UK"}
    with pytest.raises(CostBasisUnmappable) as exc:
        to_canonical_taxlot_schwab(lot, parent_position_id="P1", parent=parent)
    assert exc.value.reason_code == "ambiguous_mapping"
    assert exc.value.details["jurisdiction"] == "UK"
```

---

### T10: Orion → TaxLot (EXPLICIT TABLE — was "analogous to T9" in v0.1.0)

**Vendor Model:** `OrionTaxLot` (nested in OrionPosition — `Position.taxLots[]` array)
**Canonical Type:** `m3.TaxLot`
**UUID Namespaces:** `TAXLOT_NS` for `lot_id: UUID`; derived `HOLDING_NS` for `holding_ref: str`
**LOSSY_FIELDS:** `{"orion_lot_internal_id", "orion_lot_allocation_detail", "orion_lot_transfer_history"}`
**REVERSE_LOSSY_FIELDS:** `{"OrionTaxLot.internalLotId", "OrionTaxLot.allocationDetail", "OrionTaxLot.transferHistory"}` — Orion-internal lot metadata canonical does not carry.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `OrionTaxLot.lotId` | `lot_id` | `UUID` (REQUIRED) | `uuid5(TAXLOT_NS, f"orion:{lotId}")` | no |
| (parent position id) | `holding_ref` | **`str`** (M3) | **`str(uuid5(HOLDING_NS, f"orion:{parent_position_id}"))`** | no |
| `OrionTaxLot.symbol` | `security_ref` | `Optional[str]` | direct ticker | no |
| `OrionTaxLot.acquisitionDate` | `acquisition_date` | `date` (REQUIRED) | direct date | no |
| `OrionTaxLot.acquisitionPrice` | `acquisition_price` | `Optional[float]` | direct | no |
| `OrionTaxLot.quantity` | `quantity` | `float` (REQUIRED) | direct | no |
| `OrionTaxLot.costBasisMethod` | `cost_basis_method` | `CostBasisMethod` (REQUIRED) | **CRITICAL (Steering Rule 16)** — `normalize_cost_basis_method(vendor_string=lot.costBasisMethod, vendor="orion", account_type=parent.accountType, security_class=parent.securityType, jurisdiction=None)`. Uses `COST_BASIS_VENDOR_MAP[("orion", "SPECIFIC_LOT")]` etc. Vendor silent → `COST_BASIS_DEFAULTS[("orion", "taxable", "equity")]`. **NEVER NULL.** Emits `ReconciliationNote.cost_basis_source`. | no |
| `OrionTaxLot.costBasisAmount` | `cost_basis_amount` | `float` | direct | no |
| `OrionTaxLot.holdingPeriod` | `holding_period` | `Optional[str]` | ENUM_MAPPINGS (Orion returns `"SHORT_TERM"` / `"LONG_TERM"` / `"UNKNOWN"`) | no |
| `OrionTaxLot.unrealizedGainLoss` | `unrealized_gain_loss` | `Optional[float]` | direct | no |
| `OrionTaxLot.washSaleDisallowed` | `wash_sale_disallowed` | `Optional[float]` | direct | no |
| — (const) | `source_custodian` | `str` | `"orion"` | no |
| `OrionTaxLot.costBasisMethod` (vendor raw) | `source_cost_basis_method` | `Optional[str]` | direct vendor string when reported; `None` when vendor silent (per v0.2.0 fix) | no |
| `OrionTaxLot.internalLotId` | — (dropped) | — | Orion internal | YES |
| `OrionTaxLot.allocationDetail` | — (dropped) | — | out of scope | YES |
| `OrionTaxLot.transferHistory` | — (dropped) | — | out of scope | YES |

---

### T11: Schwab → Household

**Vendor Model:** `SchwabMasterAccount` (custodial master account grouping)
**Canonical Type:** `m3.Household`
**UUID Namespace:** `HOUSEHOLD_NS`
**LOSSY_FIELDS:** `{"schwab_master_account_metadata", "schwab_master_account_title_code"}`
**REVERSE_LOSSY_FIELDS:** `{"MasterAccount.metadata", "MasterAccount.titleCode"}` — Schwab-internal fields canonical does not carry.

| Vendor Field | Canonical Field | M3 Type | Derivation | Lossy? |
|-------------|-----------------|---------|------------|--------|
| `MasterAccount.masterAccountNumber` | `source_id` (helper) / `canonical_id` | `str` / `UUID` | `canonical_id = uuid5(HOUSEHOLD_NS, f"schwab:{masterAccountNumber}")` | no |
| `MasterAccount.name` | `display_name` | `str` | direct | no |
| — (const) | `primary_source` | `str` | `"schwab"` | no |
| `MasterAccount.linkedAccountHolders[]` | `members[]` | `list[HouseholdMember]` | each → `HouseholdMember(client_ref=str(uuid5(CLIENT_NS, f"schwab:{h.accountHolderId}")), role=ENUM_MAPPINGS["role"][h.role], source="schwab")`. **`client_ref` is `str`.** Schwab role: `"PRIMARY"`/`"SPOUSE"`/etc. | no |
| `MasterAccount.linkedAccounts[]` | `accounts[]` | `list[HouseholdAccount]` | `[HouseholdAccount(account_ref=str(uuid5(ACCOUNT_NS, f"schwab:{a.accountNumber}")), source="schwab") for a in linkedAccounts]`. **`account_ref` is `str`.** | no |
| `MasterAccount.masterAccountNumber` | `vendor_mappings.schwab` | `Optional[HouseholdVendorSchwab]` | `HouseholdVendorSchwab(master_account=masterAccountNumber, grouping_type="custodial")` — grouping_type CONST, test-asserted | no |

---

### T12: Registry Entry Summary

The 11 `TRANSLATOR_REGISTRY` entries:

| # | (source_system, canonical_type) | Module Path | Schema Version | Vendor API Version |
|---|---------------------------------|-------------|----------------|--------------------|
| 1 | `(salesforce_fsc, Client)` | `m7_schema_translators.salesforce_fsc.client` | `0.1.0` | `v59.0` |
| 2 | `(salesforce_fsc, Household)` | `m7_schema_translators.salesforce_fsc.household` | `0.1.0` | `v59.0` |
| 3 | `(salesforce_fsc, Goal)` | `m7_schema_translators.salesforce_fsc.goal` | `0.1.0` | `v59.0` |
| 4 | `(orion, Holding)` | `m7_schema_translators.orion.holding` | `0.1.0` | `v2.0` |
| 5 | `(orion, Transaction)` | `m7_schema_translators.orion.transaction` | `0.1.0` | `v2.0` |
| 6 | `(orion, Household)` | `m7_schema_translators.orion.household` | `0.1.0` | `v2.0` |
| 7 | `(orion, TaxLot)` | `m7_schema_translators.orion.taxlot` | `0.1.0` | `v2.0` |
| 8 | `(emoney, PlanSummary)` | `m7_schema_translators.emoney.plan_summary` | `0.1.0` | `v2` |
| 9 | `(schwab, Holding)` | `m7_schema_translators.schwab.holding` | `0.1.0` | **`v1`** |
| 10 | `(schwab, TaxLot)` | `m7_schema_translators.schwab.taxlot` | `0.1.0` | **`v1`** |
| 11 | `(schwab, Household)` | `m7_schema_translators.schwab.household` | `0.1.0` | **`v1`** |

`len(TRANSLATOR_REGISTRY) >= 11`. Lighthouse breakdown: SF FSC 3 + Orion 4 + eMoney 1 + Schwab 3.

---

## Integration Point with M6

M6 Trust-Aware Gateway is M7's primary caller in Phase 2 (see §Consumers in the banner and ARCH-09 row `M6 → M7: *`). This section pins the integration contract so that no reviewer, engineer, or downstream spec has to reconstruct it from scattered ACs. Added in v0.3.0 to close NI-1 Fix #9 from the v2 review (previously the Traceability Table cited this section but it did not exist as a header).

### Contract Summary

M6 MUST call M7 through the single public dispatcher entry point. M6 MUST pass the routing keys as explicit function parameters. M6 MUST NOT reach into request-object attributes inside M7.

- Authoritative signature (AC13.2): `translate_to_canonical(source_system: str, canonical_type: str, vendor_payload: dict) -> tuple[BaseModel, ReconciliationNote]`
- Reverse direction (AC13.3): `translate_from_canonical(source_system: str, canonical_type: str, canonical: BaseModel) -> tuple[BaseModel, ReconciliationNote]`
- Skeleton reference (Appendix B.6): `src/m7_schema_translators/__init__.py` shows the eager-registry dispatcher body.

### What M6 Does

In Stage 6 (`m6.translate`) of the M6 pipeline, M6 extracts `source_system` and `canonical_type` from the request-level `GatewayRequest` fields (M6 spec §R1.1 — `GatewayRequest.source_system: str`, `GatewayRequest.canonical_type: str`). M6 then calls:

```python
from m7_schema_translators import translate_to_canonical, TranslationError

try:
    canonical, note = translate_to_canonical(
        source_system=req.source_system,        # e.g. "orion"
        canonical_type=req.canonical_type,      # e.g. "Holding"
        vendor_payload=req.vendor_payload,      # dict from M11
    )
except TranslationError as exc:
    # Propagate details as-is into M10 audit entry (AC16.2).
    audit.payload["translation_error_details"] = exc.details
    raise
```

### What M6 MUST NOT Do (Regression Guards)

- M6 MUST NOT pass `req` (or any request object) as a positional argument — M7's signature is keyword-friendly and takes only primitives + dict.
- M6 MUST NOT access `req.target.source_system` or `req.target.canonical_type` — `req.target` is NOT part of the public contract. v0.1.0 erroneously documented a `req.target.*` pattern; v0.2.0 removed it. v0.3.0 reaffirms: routing keys are **request-level**, extracted by M6 BEFORE the M7 call.
- M6 MUST NOT catch `TranslationError` silently — it must propagate `exc.details` into `AuditEntry.payload["translation_error_details"]` per AC16.2 so M10 can aggregate failure rates per `(vendor, canonical_type, field_path, reason_code, vendor_value)`.
- M6 MUST NOT mutate, filter, or transform `exc.details` — M7 already guarantees the payload is PII-free and TypedDict-shaped (AC4.8 + AC14.6 + AC14.8).

### Where This Is Enforced in the Spec

- AC13.2 — explicit-parameter signature; `UnregisteredTranslator` on bad routing keys
- AC13.6 — dispatcher validates `source_system` against `SourceSystem` enum AND `canonical_type` against `CANONICAL_TYPES` BEFORE registry lookup
- AC13.7 — registry is eager at package import (fail-closed; partial registry worse than no M7)
- AC16.1 / AC16.2 — M7-side details-shape contract + M6 propagation obligation
- Appendix B.6 — reference skeleton of `translate_to_canonical` body

### Amendment Path

Any change to the dispatcher signature requires a MAJOR bump to `m7_schema_translators.SCHEMA_VERSION` (AC13.5) AND a coordinated amendment to the M6 Phase 2 spec. Such a change is OUT OF SCOPE for M7-lighthouse-1; any M6 change is scoped to the M6 spec, not this document.

---

## Integration Point with M11

M11 REST Adapters are the second caller documented in ARCH-09 (row `M11 → M7: *`). M7 Phase 2 explicitly restricts this integration to a single-caller model to preserve the M10 audit chain. Added in v0.3.0 to close NI-1 Fix #10 from the v2 review (previously the dual-caller audit contract only appeared in the changelog row — no header, no dedicated section).

### Phase 2 Rule (lighthouse-1): M6-as-Caller ONLY

In Phase 2, M11 adapters MUST NOT call `translate_to_canonical` / `translate_from_canonical` directly. The control flow is fixed:

```
M11 adapter (vendor HTTP/SFTP/SDK)
     → returns raw vendor dict to M6 gateway
     → M6 runs Stage 6 (`m6.translate`) which calls M7 dispatcher
     → M6 writes M10 AuditEntry including TranslationError.details if any
```

This keeps the audit chain intact. Every translate call produces exactly one `AuditEntry` via M6. No bypass path exists in Phase 2.

### Why the Restriction

Allowing M11 to call M7 directly creates an audit-bypass risk: an M11 adapter could translate a payload, write to a downstream queue, and never produce an `AuditEntry`. M10 would have no record of the translate operation. For the RIA lighthouse, this is unacceptable — M10 is the source of truth for M7 failure-rate aggregation (AC16.2, AC16.3) and for Langfuse + S3 Object Lock WORM + CRM tier-three audit (Steering Rule 6).

### Phase 2 Enforcement

- M11 Phase 2 adapters return raw vendor payload dicts to M6. M11 does NOT import `m7_schema_translators.translate_to_canonical` in Phase 2 code paths.
- M11 Phase 2 integration tests assert M6 is the sole caller in the control-flow graph (test responsibility lives in M11 spec, not M7).
- M7 Phase 2 security test `tests/unit/test_m7_module_boundary.py` (AC12.1) ensures M7 does NOT import from M11 or anything downstream — enforcement on M7's side only. Upstream enforcement (M11 does not call M7 directly) is an M11-spec test.

### M11-as-Caller Path (DEFERRED to lighthouse-2)

When batch-ingest adapters are added in M7-lighthouse-2 (Phase 3+), M11 MAY call M7 directly for bulk-translate operations. Before that path opens, the following audit-bypass prevention rules MUST be added to a future amendment of this spec:

1. Explicit caller-identity parameter. `translate_to_canonical(source_system, canonical_type, vendor_payload, *, caller_role: Literal["m6", "m11_batch"])`. Default would stay `"m6"` for backward compatibility.
2. Per-caller audit sink contract. When `caller_role="m11_batch"`, M11 MUST provide an `audit_sink: Callable[[AuditEntry], None]` so every translate call still produces an `AuditEntry`. M7 MAY invoke the sink, or M11 MAY be required to wrap the call — the decision lives in the lighthouse-2 amendment.
3. Bypass-denial test. A test must verify that an M11 direct call WITHOUT a registered audit sink raises `UnregisteredTranslator(reason_code="audit_sink_missing")` or equivalent.
4. ARCH-09 dependency matrix update. The `M11 → M7` cell would be upgraded from `*` (potential caller) to `*, with audit contract` annotation.

None of these are in scope for Phase 2. The lighthouse-2 amendment is the only place these rules get added — M7-lighthouse-1 (this spec) explicitly forbids the direct-call path.

### Where This Is Enforced in the Spec

- §Consumers banner line — "M11 REST Adapters (Phase 2 wiring — audit-bypass contract, see §Integration Point with M11)"
- AC12.1 / AC12.2 — M7-side forbidden-import + forbidden-runtime-dep AST scans (M7 does not reach M11)
- AC16.1 / AC16.2 — M7 details-shape + M6 propagation obligation — the contract that keeps the M6 audit chain intact
- §Known Blockers row "OPA per-Balance account_type rules" — indirect reference: Balance translator (a candidate lighthouse-2 type) would exercise the M11-batch path first

---

## Design

This section captures cross-cutting design decisions that span multiple requirements and tasks. Added in v0.3.0 to give Review Fix Traceability rows #11 and #13 a concrete target section (closing NI-1 from the v2 review — previously `## Design` did not exist as a header and both rows pointed to dangling subsections).

### Directory / Package / Import Naming

Pinned in v0.2.0 (changelog row L30). Now given a dedicated heading so the Review Fix Traceability Table (Fix #11) points to a real section.

| Concern | Value | Rationale |
|---------|-------|-----------|
| Source directory | `src/m7_schema_translators/` | Underscore form — matches M3 (`src/m3_schema_registry/`), M5 (`src/m5_config_loader/`), M6 (`src/m6_mcp_gateway/`). |
| Distribution package name (pyproject, PyPI-style) | `m7-schema-translators` | Hyphenated — PyPI/setuptools convention; matches `m3-schema-registry`, `m5-config-loader`, `m6-mcp-gateway`. |
| Python import path | `m7_schema_translators` | Underscore form — Python identifiers cannot contain hyphens; setuptools maps the hyphenated dist name to the underscored module automatically. |

Consistency check (what consumers write):

```python
# Distribution (requirements.txt / pyproject.toml [project.dependencies])
m7-schema-translators>=0.1.0,<1.0

# Import (everywhere in Python code)
from m7_schema_translators import (
    TRANSLATOR_REGISTRY,
    translate_to_canonical,
    translate_from_canonical,
    TranslationError,
)
```

Regression guards:
- AC12.3 — `requirements.txt` contains `m3-schema-registry`, `m5-config-loader`, and pydantic only. Hyphenated.
- AC12.4 — AST scan walks `src/m7_schema_translators/` (underscored) — any import path using a different capitalisation or form fails the scan.
- Task 20 — `pyproject.toml` declares `name = "m7-schema-translators"` exactly.

Violation cases (v0.1.0 regressions the naming pins now prevent):
- `src/m7_translators/` (missing `_schema_`) — would diverge from M3/M5/M6
- Package name `m7_schema_translators` in `pyproject.toml` (underscored) — non-standard for PyPI
- `from m7-schema-translators import ...` (hyphenated) — Python SyntaxError
- `src/M7SchemaTranslators/` (CamelCase) — diverges from Python convention and M3/M5/M6

### Hypothesis Strategy Approach

Task 18 cites this section for the SF FSC Client worked example. v0.2.0 referenced it without providing the example; v0.3.0 fills the gap (the single biggest structural regression the v2 review flagged at NI-1 Fix #13). The pattern here is replicable across all 11 Phase 2 translator pairs with only vendor-specific substitutions.

#### Design Decision: `@composite` over `from_type`

Hypothesis's `from_type(VendorModel)` auto-generates strategies from Pydantic field types. It is NOT used in M7 because:

1. Fixture PII scan (AC14.9) demands synthetic-only identifiers — the default strategies generate unconstrained strings that can match real email/SSN/phone/IBAN patterns.
2. Vendor-ID character constraint (AC10.8) requires `^[a-zA-Z0-9._\-]+$` — `from_type(str)` emits Unicode.
3. Enum-field constraints are fixed value sets (e.g., SF FSC `RecordType.Name ∈ {PersonAccount, Business Account, Trust}`). `from_type` cannot infer these from a non-Enum Pydantic field.
4. Determinism for property tests (AC10.4, AC1.3) needs bounded alphabets so `@settings(max_examples=100, deadline=500)` holds under the 2-minute budget.

Every Phase 2 translator therefore ships ONE `@composite` strategy in `tests/schema-reconciliation/strategies/{vendor}_{type}.py`. 11 files total — one per registry pair.

#### Worked Example: SF FSC Client `@composite` Strategy

Complete strategy for `tests/schema-reconciliation/strategies/salesforce_fsc_client.py`:

```python
# tests/schema-reconciliation/strategies/salesforce_fsc_client.py
from __future__ import annotations
from datetime import date
import hypothesis.strategies as st

# --- PII-safe alphabets and enumerations ---------------------------------

# SF FSC IDs: 15- or 18-char alphanumeric. M7 fixtures use the 18-char form.
SF_ID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# Vendor-ID character class matches AC10.8 `^[a-zA-Z0-9._\-]+$`. We keep it to
# alphanumerics only for SF FSC — dots/hyphens/underscores are legal in M7 but
# not emitted by the SF platform for Account.Id.
VENDOR_ID_ALPHABET = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

# PII-safe email domains (AC14.9 fixture scan allow-list).
PII_SAFE_EMAIL_DOMAINS = ["example.invalid", "example.test", "example.localhost"]

# Phone numbers: MUST carry `555-` prefix per AC14.9.
def _phone() -> st.SearchStrategy[str]:
    return st.builds(
        lambda suffix: f"+1-555-555-{suffix:04d}",
        st.integers(min_value=0, max_value=9999),
    )

# SF RecordType picklist — a fixed 3-value enum for Phase 2.
SF_RECORD_TYPE_NAMES = ["PersonAccount", "Business Account", "Trust"]

# SF KYCStatus picklist — fixed 4-value enum.
SF_KYC_STATUSES = ["Verified", "Pending", "Expired", "Failed"]

# Archetype — NO M3 validator (per Task 3 regression guard). Strategy still
# emits canonical values PLUS one "rogue_value" branch so the property test
# exercises the no-validator behaviour.
SF_ARCHETYPES = ["mass_affluent", "hnw", "uhnw", "rogue_value"]

# Jurisdiction — ISO 3166-1 alpha-2 subset used in lighthouse fixtures.
SF_JURISDICTIONS = ["US", "US-CA", "US-NY", "US-TX", "CA", "UK"]


# --- @composite strategy --------------------------------------------------

@st.composite
def sf_fsc_client_payload(draw) -> dict:
    """
    Generates a SF FSC Account+Contact payload shaped for to_canonical_client.

    All emitted values satisfy:
      * AC10.8 vendor-ID char constraint: ^[a-zA-Z0-9._\\-]+$
      * AC14.9 fixture PII scan (email/SSN/phone synthetic-only)
      * AC3.1 vendor model extra="forbid" (no stray keys)

    Every field is bounded to keep @settings(max_examples=100, deadline=500)
    under the 2-minute CI budget per AC10.4.
    """
    # Core IDs — 18-char SF IDs, PII-safe chars only.
    account_id = draw(
        st.text(alphabet=SF_ID_ALPHABET, min_size=18, max_size=18)
    )
    contact_id = draw(
        st.text(alphabet=SF_ID_ALPHABET, min_size=18, max_size=18)
    )
    owner_id = draw(
        st.text(alphabet=SF_ID_ALPHABET, min_size=18, max_size=18)
    )
    firm_id_raw = draw(
        st.text(alphabet=VENDOR_ID_ALPHABET, min_size=3, max_size=20)
    )
    household_id = draw(
        st.one_of(
            st.none(),
            st.text(alphabet=SF_ID_ALPHABET, min_size=18, max_size=18),
        )
    )

    # RecordType from the fixed 3-value enum (AC6.1 / ENUM_MAPPINGS).
    record_type_name = draw(st.sampled_from(SF_RECORD_TYPE_NAMES))
    is_person_account = (record_type_name == "PersonAccount")

    # Name — always populated (AC4.2 MissingRequiredField guard covered in
    # negative tests, not here).
    account_name = draw(
        st.text(
            alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz",
            min_size=1, max_size=40,
        ).filter(lambda s: s.strip() != "")
    )

    # Contact fields — present ONLY for PersonAccount (T1 branching rule).
    if is_person_account:
        first_name = draw(
            st.text(
                alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz",
                min_size=1, max_size=30,
            ).filter(lambda s: s.strip() != "")
        )
        last_name = draw(
            st.text(
                alphabet="ABCDEFGHIJKLMNOPQRSTUVWXYZ abcdefghijklmnopqrstuvwxyz",
                min_size=1, max_size=30,
            ).filter(lambda s: s.strip() != "")
        )
        email = draw(
            st.emails(domains=st.sampled_from(PII_SAFE_EMAIL_DOMAINS))
        )
        phone = draw(_phone())
        # DOB — synthetic-safe, anchored in 1940-2005 range.
        birthdate = draw(
            st.dates(min_value=date(1940, 1, 1), max_value=date(2005, 12, 31))
        )
    else:
        # Business Account / Trust — per T1 branching rule, individual-PII
        # fields MUST be None.
        first_name = None
        last_name = None
        email = None
        phone = None
        birthdate = None

    # KYC fields — always safe to emit.
    kyc_status = draw(st.sampled_from(SF_KYC_STATUSES))
    kyc_date = draw(
        st.dates(min_value=date(2020, 1, 1), max_value=date(2026, 12, 31))
    )

    # SSN last four — only for PersonAccount. 4 digits, string.
    ssn_last_four = (
        draw(st.text(alphabet="0123456789", min_size=4, max_size=4))
        if is_person_account else None
    )

    # Tax ID — entity/trust only. Synthetic 9-digit form.
    tax_id = (
        None if is_person_account
        else draw(st.text(alphabet="0123456789", min_size=9, max_size=9))
    )

    # Archetype — may be a known value or "rogue_value" (Task 3 guard).
    archetype = draw(st.sampled_from(SF_ARCHETYPES))
    jurisdiction = draw(st.sampled_from(SF_JURISDICTIONS))

    # AccountIds — semicolon-separated list (T1 derivation); 0..5 members.
    account_id_count = draw(st.integers(min_value=0, max_value=5))
    account_ids_list = [
        draw(st.text(alphabet=SF_ID_ALPHABET, min_size=18, max_size=18))
        for _ in range(account_id_count)
    ]
    account_ids_picklist = ";".join(account_ids_list)

    # Investment objectives — semicolon-separated bucket picklist.
    objectives_list = draw(
        st.lists(
            st.sampled_from([
                "GrowthOfCapital", "IncomeGeneration", "WealthPreservation",
                "Speculation", "TaxEfficiency",
            ]),
            min_size=0, max_size=3, unique=True,
        )
    )

    # Money ranges — string buckets (NOT raw dollar amounts).
    annual_income_range = draw(
        st.sampled_from(["<100k", "100k-250k", "250k-500k", "500k-1M", "1M+"])
    )
    net_worth_range = draw(
        st.sampled_from(["<1M", "1M-5M", "5M-25M", "25M-100M", "100M+"])
    )
    liquid_net_worth_range = draw(
        st.sampled_from(["<500k", "500k-1M", "1M-5M", "5M+"])
    )

    return {
        "Account": {
            "Id": account_id,
            "Name": account_name,
            "RecordType": {"Name": record_type_name},
            "OwnerId": owner_id,
            "FinServ__PersonAccount__c": is_person_account,
            "FinServ__FirmId__c": firm_id_raw,
            "FinServ__HouseholdId__c": household_id,
            "FinServ__KYCStatus__c": kyc_status,
            "FinServ__KYCLastCompleted__c": kyc_date.isoformat(),
            "FinServ__LastSSNDigits__c": ssn_last_four,
            "FinServ__TaxID__c": tax_id,
            "FinServ__ClientArchetype__c": archetype,
            "FinServ__Jurisdiction__c": jurisdiction,
            "FinServ__AccountIds__c": account_ids_picklist,
            "FinServ__InvestmentObjectives__c": ";".join(objectives_list),
            "FinServ__AnnualIncome__c": annual_income_range,
            "FinServ__NetWorth__c": net_worth_range,
            "FinServ__LiquidNetWorth__c": liquid_net_worth_range,
            "CreatedDate": "2024-01-01T00:00:00Z",
            "LastModifiedDate": "2026-04-01T00:00:00Z",
        },
        "Contact": {
            "Id": contact_id,
            "FirstName": first_name,
            "LastName": last_name,
            "Email": email,
            "Phone": phone,
            "Birthdate": birthdate.isoformat() if birthdate else None,
        },
    }
```

Companion property test (abbreviated — full body in Task 18):

```python
# tests/schema-reconciliation/test_m7_idempotency.py (sketch)
from hypothesis import given, settings
from .strategies.salesforce_fsc_client import sf_fsc_client_payload
from m7_schema_translators.salesforce_fsc.client import (
    to_canonical_client, from_canonical_client,
)

@given(sf_fsc_client_payload())
@settings(max_examples=100, deadline=500)
def test_sf_fsc_client_roundtrip_idempotent(payload):
    canonical_1, note_1 = to_canonical_client(payload)
    canonical_2, note_2 = to_canonical_client(payload)
    # AC1.3 byte-identical
    assert canonical_1.model_dump_json() == canonical_2.model_dump_json()
    assert note_1.model_dump_json() == note_2.model_dump_json()
    # AC1.4 reverse byte-identical
    reverse_1, _ = from_canonical_client(canonical_1)
    reverse_2, _ = from_canonical_client(canonical_1)
    assert reverse_1.model_dump_json() == reverse_2.model_dump_json()
```

#### Replication Pattern for the Other 10 Translators

The SF FSC Client strategy is the template. Each of the 10 other translator strategies follows this exact structure with only these substitutions:

| Slot in Template | Per-Translator Substitution |
|------------------|----------------------------|
| `SF_ID_ALPHABET` width (`min_size=18, max_size=18`) | Orion: `min_size=10, max_size=20` alnum. Schwab: `min_size=8, max_size=8` (accountNumber 8-digit per AC3.6). eMoney: `min_size=6, max_size=24` alnum. |
| `VENDOR_ID_ALPHABET` | Same `^[a-zA-Z0-9._\-]+$` for all vendors (AC10.8). |
| Enum fixed-value lists (`SF_RECORD_TYPE_NAMES`, `SF_KYC_STATUSES`, `SF_ARCHETYPES`) | Replace with per-vendor enums from §Vendor Enum Mapping Matrix. One `sampled_from` per enum field. |
| PII fields (`email`, `phone`, `birthdate`, `ssn_last_four`, `tax_id`) | Keep the PII-safe generators (`st.emails(domains=...)`, `_phone()`, `st.dates(...)`, 4-digit / 9-digit synthetic strings). Apply only to translators whose canonical type carries those PII fields (per M3 `PII_FIELDS`). |
| Money fields | Always string buckets (`st.sampled_from([...])`) OR `st.decimals(min_value=0, max_value=10_000_000, places=2)` when the canonical type is `float`. Never raw unbounded numerics. |
| Branching rules (`is_person_account` in SF FSC) | Preserved for vendors with similar split (Schwab `INDIVIDUAL` vs `TRUST`). No-op for eMoney/Orion. |
| Cost-basis-specific strategies (Orion TaxLot, Schwab TaxLot) | Add `st.sampled_from(["SpecificLot", "AverageCost", "FIFO", "LIFO", "HIFO", None])` for the `costBasisMethod` field — `None` branch exercises the vendor-silent → default path (AC5.5). |
| Account-type enums (Holding, TaxLot, Transaction translators) | `st.sampled_from([...])` from M3 `AccountType.value` list per §Enum Matrix, plus the "(no string)" 457 gap per Known Blockers row. |

Total: 11 strategy files, each ≤ ~200 lines, each bounded to keep `@settings(max_examples=100, deadline=500)` under the 2-minute total-test budget (AC10.4). Strategies import from `m7_schema_translators` only via module-path (never cross-module), so AC12.1 boundary scan still holds for strategy files.

Concurrency guard (AC10.7): the 4-thread smoke test in Task 18 reuses these `@composite` strategies to generate 50 payloads per thread, verifying byte-identical output across threads — no separate strategy needed.

---

## Tasks

Ordered, atomic tasks. Each task produces implementation + tests. Each task cites specific ACs. Target: build one complete translator pair at a time (depth-first per Steering Rule 29).

### Task 1: Infrastructure — errors + cost_basis + shared + dispatcher
Create the shared infrastructure that all translators depend on.

**Files:**
- `src/m7_schema_translators/errors.py` — `TranslationError` base + 7 subclasses + `VALID_REASON_CODES` + per-subclass TypedDicts (AC4.8)
- `src/m7_schema_translators/cost_basis.py` — `normalize_cost_basis_method` + `COST_BASIS_VENDOR_MAP` + `COST_BASIS_DEFAULTS` (all MappingProxyType-wrapped per AC5.2/AC5.3)
- `src/m7_schema_translators/shared/namespaces.py` — 10 UUID5 namespace constants (+ `ORDER_NS` reserved)
- `src/m7_schema_translators/shared/reconciliation_note.py` — `ReconciliationNote`, `CostBasisSource`, `RECONCILIATION_NOTE_SAFE_FIELDS`
- `src/m7_schema_translators/shared/dispatcher.py` — `TranslatorPair` frozen dataclass
- `src/m7_schema_translators/shared/vendor_id_validator.py` — `_validate_vendor_id_chars` (AC10.8)
- `src/m7_schema_translators/__init__.py` — skeleton with empty registry, public API shape, `SCHEMA_VERSION`

**Tests:**
- `tests/unit/test_m7_errors.py` — subclass inheritance, `VALID_REASON_CODES` is frozenset, every subclass has a valid reason_code, per-subclass TypedDict shape validated (AC4.8)
- `tests/unit/test_m7_cost_basis.py` — every VENDOR_MAP entry, every DEFAULTS entry, unknown → raises, missing → raises, MappingProxyType mutation raises TypeError, Schwab UK xfail
- `tests/unit/test_m7_public_api.py` — `__all__` contents, `SCHEMA_VERSION == "0.1.0"`
- `tests/unit/test_m7_observability_contract.py` — AC16.4 — per-subclass details JSON-serializable + PII-free

**Acceptance Criteria:** AC4.1, AC4.2, AC4.3, AC4.7, AC4.8, AC5.1, AC5.2, AC5.3, AC5.6, AC5.8, AC9.1, AC9.5, AC9.6, AC9.7, AC10.5, AC10.8, AC13.1, AC13.5, AC14.1, AC14.7, AC16.1, AC16.4

### Task 2: Module boundary + security invariants tests (BEFORE translator code)
Write the negative tests first — they enforce the "what M7 must NOT do" rules from Day 1.

**Files:**
- `tests/unit/test_m7_module_boundary.py` — AST import-scan test walking `src/m7_schema_translators/` — positive M5 allow-list per AC12.4 worked example
- `tests/unit/test_m7_security_invariants.py` — credential grep, PII-in-exception scan, forbidden import grep (expanded list: +warnings, +tempfile, +io.open, +os.open)

**Tests:**
- Forbidden module prefixes: m1_, m2_, m4_, m6_, m8-m13, compliance.gap2, compliance.gap6
- Forbidden runtime deps grep (vendor SDKs, httpx, etc.)
- No `logging`, `warnings`, `tempfile`, `os.environ`, `open(`, `io.open`, `os.open`, `socket`, `urllib`, `httpx`, `requests`, `subprocess` in source
- No `uuid.uuid4()`, `datetime.utcnow()`, `datetime.now()`, `time.time()`, `random.*` in source
- Permitted M5 imports (positive AST allow-list): `Archetype`, `Jurisdiction`, `RegistrationType` ONLY. Test asserts any other `m5_config_loader.*` import fails.

**Acceptance Criteria:** AC10.1, AC10.2, AC10.3, AC10.7 (concurrency threaded into Task 18), AC10.8, AC12.1, AC12.2, AC12.3, AC12.4, AC14.1, AC14.3, AC14.4

### Task 3: Salesforce FSC — vendor models + Client translator
First real translator. Establishes the pattern for all subsequent translators.

**Files:**
- `src/m7_schema_translators/salesforce_fsc/__init__.py`
- `src/m7_schema_translators/salesforce_fsc/models.py` — `SalesforceFSCAccountContact` (Account+Contact) with all v59.0 fields + `@model_validator(mode="after")` for Person-Account vs Business-Account branching (review recommended fix)
- `src/m7_schema_translators/salesforce_fsc/client.py` — `to_canonical_client`, `from_canonical_client`, `ENUM_MAPPINGS` (MappingProxyType), `REVERSE_ENUM_MAPPINGS`, `LOSSY_FIELDS`, `REVERSE_LOSSY_FIELDS`, `SCHEMA_VERSION="0.1.0"`, `VENDOR_API_VERSION="v59.0"`
- `src/m7_schema_translators/salesforce_fsc/CHANGELOG.md` — initial Keep-A-Changelog entry: `## [0.1.0] — 2026-04-26`
- `tests/schema-reconciliation/fixtures/salesforce_fsc/client/{minimal,fully_populated,edge_case,business_account}.json` — synthetic-only per AC14.9
- `tests/schema-reconciliation/test_m7_roundtrip_salesforce_fsc_client.py`

**Tests:**
- Vendor model rejects `extra="forbid"` violations
- Every field has a description
- `to_canonical_client` produces Client with deterministic `canonical_id = uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")`
- `firm_id` is UUID (bare) per M3 — test `isinstance(canonical.firm_id, UUID)`
- `accounts` is `list[UUID]` per M3 — test each element `isinstance(..., UUID)`
- Every PII field (email, phone, dob, ssn_last_four, tax_id) carried through unchanged
- Every enum mapping per SF FSC table (R6)
- Round-trip double-trip equality on 4 fixtures (incl. business_account)
- Business Account fixture: `first_name`, `last_name`, `email`, `phone`, `date_of_birth` all `None`
- Unknown client_type raises `UnknownEnumValue` with `details.valid_values` sorted alphabetically
- Missing `Account.Id` raises `MissingRequiredField`
- Missing `firm_id` raises `MissingRequiredField(field_path="Account.FinServ__FirmId__c")`
- Vendor ID containing `:` raises `TypeCoercionError(reason_code="vendor_id_invalid_chars")` (AC10.8)
- **v0.2.0 regression guard:** `archetype` value `"rogue_value"` passes through unchanged (no validator claim — review fix #6)

**Acceptance Criteria:** AC1.1, AC1.2, AC1.3, AC1.4, AC1.5, AC1.6, AC1.7, AC1.8, AC3.1, AC3.2, AC3.3, AC3.4, AC3.5, AC3.7, AC4.4, AC4.5, AC4.6, AC6.1, AC6.2, AC6.3, AC6.4, AC8.1, AC8.2, AC9.2, AC9.3, AC9.4, AC10.6, AC10.8, AC10.9, AC11.1, AC11.2, AC11.3, AC11.4, AC11.6, AC14.2, AC14.5, AC14.6

### Task 4: Salesforce FSC — Household translator
CONTAINER model. grouping_type="relationship" CONST. Members at canonical top level.

**Files:**
- Add to `src/m7_schema_translators/salesforce_fsc/models.py`: `SalesforceFSCHousehold`, `SalesforceFSCHouseholdMember`
- `src/m7_schema_translators/salesforce_fsc/household.py` — `to_canonical_household`, `from_canonical_household(..., vendor="salesforce_fsc")`
- Fixtures + round-trip test

**Tests:**
- Vendor mappings `HouseholdVendorSFSC(household_id, grouping_type="relationship")` — grouping_type asserted CONST
- Members at canonical top level, NOT inside `vendor_mappings`
- `members[].client_ref` is **`str`** per M3 (test `isinstance(m.client_ref, str)`) — v0.2.0 fix
- `accounts[].account_ref` is **`str`** per M3
- Each member has `source="salesforce_fsc"` attribution
- Single-vendor → `reconciliation is None` (AC7.8 invariant)
- `reconciliation.last_reconciled` — caller must provide (multi-vendor only); M7 does NOT call `datetime.utcnow()` (grep test)
- `from_canonical_household(canonical, vendor="salesforce_fsc")` returns `(None, note)` if no SF mapping present

**Acceptance Criteria:** AC7.1, AC7.3, AC7.4, AC7.6, AC7.8

### Task 5: Salesforce FSC — Goal translator
Goal picklist mapping via ENUM_MAPPINGS.

**Files:**
- Add to `src/m7_schema_translators/salesforce_fsc/models.py`: `SalesforceFSCFinancialGoal`
- `src/m7_schema_translators/salesforce_fsc/goal.py`
- Fixtures + round-trip test

**Tests:**
- All 11 `GoalType` values round-trip
- All 5 `GoalStatus` values round-trip
- `funding_pct` is in `REVERSE_LOSSY_FIELDS` (derived from target + current — v0.2.0 reverse-lossy tracking)
- `vendor_mappings.salesforce_fsc = GoalVendorSFSC(...)` populated
- `client_ref` / `household_ref` / `plan_ref` / `linked_accounts` all UUID-typed per M3
- Round-trip tolerance: money-field equality via `math.isclose` per AC11.8

**Acceptance Criteria:** AC6.1, AC6.4, AC11.4, AC11.7, AC11.8

### Task 6: Orion — vendor models + Holding translator
First of the 4-translator Orion batch.

**Files:**
- `src/m7_schema_translators/orion/__init__.py`
- `src/m7_schema_translators/orion/models.py` — `OrionPosition`, `OrionTransaction`, `OrionHousehold`, `OrionTaxLot`
- `src/m7_schema_translators/orion/holding.py`
- Fixtures + round-trip test

**Tests:**
- `market_value_includes_accrued` directly mapped from vendor `includesAccruedInterest` (Orion explicit)
- All Orion account_type enum values map correctly
- `account_ref` is **`str`** per M3 (test `isinstance(canonical.account_ref, str)`) — v0.2.0 fix, NOT UUID
- `client_ref` is **`Optional[str]`** per M3 — v0.2.0 fix
- `LOSSY_FIELDS` / `REVERSE_LOSSY_FIELDS` both populated
- Tax lots embedded in Position are translated via Orion TaxLot translator (Task 9)
- Partial-data: Orion Position with empty `taxLots[]` → canonical `tax_lots=[]` (no error)

**Acceptance Criteria:** AC2.2, AC11.4

### Task 7: Orion — Transaction translator
19 transaction types from Orion abbreviations. **Critical v0.2.0 fix: `transaction_id` vs `source_id` two separate fields.**

**Files:**
- `src/m7_schema_translators/orion/transaction.py`
- Fixtures + round-trip test

**Tests:**
- `transaction_id` is **`UUID`** (bare) per M3 (test `isinstance(canonical.transaction_id, UUID)`)
- `source_id` is **`str`** per M3 (test `isinstance(canonical.source_id, str)`; `canonical.source_id == vendor.transactionId`)
- `source_id != str(canonical.transaction_id)` — assert they are DIFFERENT values (source_id is raw vendor, transaction_id is uuid5-derived)
- `account_ref` is **`UUID`** per M3 (Transaction uses UUID — distinct from Holding)
- `client_ref` is **`Optional[UUID]`** per M3
- `order_ref` is `None` (Orion doesn't track 007 orders)
- All 19 `TransactionType` enum values map correctly from Orion abbreviations
- `settlement_status` mapping (PENDING/SETTLED/FAILED)
- `cost_basis_impact` sub-model populated from realizedGainLoss + holdingPeriod + washSaleDisallowed
- `source_transaction_type` preserves Orion native string for audit
- `trace_id` passed through from vendor payload if present, else `None`; M7 does NOT set it internally
- Reverse: canonical `order_ref` set → stored in `Transaction.customAttributes["order_ref"]` with safe-token note

**Acceptance Criteria:** AC6.1, AC6.3, AC11.3

### Task 8: Orion — Household translator (T6 spec — fully-detailed table)
grouping_type="portfolio_management" CONST.

**Files:**
- `src/m7_schema_translators/orion/household.py`
- Fixtures + round-trip test

**Tests:**
- `HouseholdVendorOrion(..., grouping_type="portfolio_management")` CONST
- Members carry `source="orion"`
- `members[].client_ref` is `str` per M3
- `accounts[].account_ref` is `str` per M3
- Orion's single TRUST label → canonical `trust_revocable` with discrepancy note referencing safe token `"orion_trust_label_ambiguous"`
- Single-vendor `reconciliation is None` (AC7.8)

**Acceptance Criteria:** AC7.1, AC7.8

### Task 9: Orion — TaxLot translator (+ cost basis normalization critical path)
Cost basis normalization is REQUIRED. This is the first translator to fully exercise `normalize_cost_basis_method`.

**Files:**
- `src/m7_schema_translators/orion/taxlot.py`
- Fixtures: include one with vendor-silent cost basis (exercises defaults), one with unknown string (exercises fail-closed), one with every valid enum value
- Round-trip test + focused cost-basis test

**Tests:**
- Vendor reports `SPECIFIC_LOT` → canonical `specific_lot`. `CostBasisSource.method_origin == "vendor_reported"`, confidence="high", `source_cost_basis_method == "SPECIFIC_LOT"`.
- Vendor silent, Orion + taxable equity → defaults to `specific_lot`. `method_origin == "vendor_default"`. **`source_cost_basis_method == None`** (v0.2.0 fix to T9/Task 12 contradiction).
- Vendor reports `"UNKNOWN_STRING"` → `CostBasisUnmappable(reason_code="unsupported_vendor_value")`.
- Every TaxLot has `cost_basis_method != None` (M3 Pydantic validator enforces).
- `lot_id` is **`UUID`** per M3
- `holding_ref` is **`str`** per M3 — `str(uuid5(HOLDING_NS, f"orion:{parent_position_id}"))`
- `ReconciliationNote.cost_basis_source` populated on every TaxLot.

**Acceptance Criteria:** AC5.1, AC5.4, AC5.5, AC5.6, AC5.7, AC5.8, AC11.5

### Task 10: eMoney — PlanSummary translator
Only eMoney translator. Raw plan body intentionally NOT mapped.

**Files:**
- `src/m7_schema_translators/emoney/__init__.py`
- `src/m7_schema_translators/emoney/models.py` — `EMoneyPlanSummary` (summary fields only; vendor model does NOT accept `fullPlanBody` — `extra="forbid"` excludes it)
- `src/m7_schema_translators/emoney/plan_summary.py`
- `src/m7_schema_translators/emoney/CHANGELOG.md` — documents the intentional omission of raw plan body
- Fixtures + round-trip test

**Tests:**
- Vendor model raises on any payload containing `fullPlanBody`, `cashflowProjection`, `assetAllocationHistory` (extra=forbid)
- `LOSSY_FIELDS` documented in CHANGELOG
- `net_worth` derived from `total_assets - total_liabilities` (in `fields_derived`, also in `REVERSE_LOSSY_FIELDS`)
- `probability_of_success` out of [0,100] → `TypeCoercionError`
- `vendor_mappings.emoney = PlanVendorEMoney(plan_id, scenario_id)` populated
- `client_ref` / `household_ref` / `goals[]` all UUID per M3

**Acceptance Criteria:** AC3.1, AC11.4, AC11.7

### Task 11: Schwab — vendor models + Holding translator + $ prefix handling
Schwab-specific quirks (dollar-prefixed strings, implicit `includes_accrued=false`). **v0.2.0: `VENDOR_API_VERSION = "v1"`.**

**Files:**
- `src/m7_schema_translators/schwab/__init__.py`
- `src/m7_schema_translators/schwab/models.py` — `SchwabPosition`, `SchwabTaxLot`, `SchwabMasterAccount`. Vendor model `@field_validator` strips `"$"` prefix and commas from numeric fields.
- `src/m7_schema_translators/schwab/holding.py`
- Fixtures (include one with $-prefixed costBasis, one with decimal unrealizedGainLossPct to test the *100 derivation)

**Tests:**
- `$1,234.56` in vendor payload → canonical float `1234.56`
- `unrealizedGainLossPct` returned as `0.085` → canonical `8.5` (multiply by 100); `fields_derived` includes `unrealized_gain_loss_pct`
- `market_value_includes_accrued` set to `False` (Schwab convention); `fields_derived` includes it; also in `REVERSE_LOSSY_FIELDS`
- `VENDOR_API_VERSION == "v1"` (not `"MarketDataAPI 1.0"`) — v0.2.0 fix
- `account_ref` is **`str`** per M3 (v0.2.0 fix)
- `client_ref` is **`Optional[str]`** per M3
- All Schwab account_type enum values map correctly

**Acceptance Criteria:** AC3.6, AC8.2, AC9.4, AC11.3

### Task 12: Schwab — TaxLot translator (cost basis critical path for US default)
`COST_BASIS_DEFAULTS[("schwab", "taxable", "equity")] == specific_lot` per Steering Rule 16.

**Files:**
- `src/m7_schema_translators/schwab/taxlot.py`
- Fixtures: include Schwab silent-on-cost-basis case for US taxable equity → must default to `specific_lot`; include UK xfail skeleton
- Round-trip test + focused cost-basis test

**Tests:**
- Schwab vendor silent + US taxable equity → `specific_lot`, `method_origin="vendor_default"`, `source_cost_basis_method=None` (v0.2.0 fix)
- Schwab `"SpecificLot"` → `specific_lot`, `method_origin="vendor_reported"`, `source_cost_basis_method="SpecificLot"`
- Schwab `"MinTax"` → `hifo`
- Schwab unknown string → `CostBasisUnmappable`
- Schwab UK `"SpecificLot"` → `CostBasisUnmappable(reason_code="ambiguous_mapping")` — `@pytest.mark.xfail(reason="Schwab UK PENDING SME — IMPL-06 follow-up")`
- Every TaxLot `cost_basis_method != None`
- `lot_id` is `UUID`, `holding_ref` is `str` per M3
- `source_cost_basis_method` preserves vendor raw string when reported; `None` when silent

**Acceptance Criteria:** AC5.1, AC5.2, AC5.3, AC5.4, AC5.5, AC5.6, AC5.7, AC11.5

### Task 13: Schwab — Household translator
grouping_type="custodial" CONST.

**Files:**
- `src/m7_schema_translators/schwab/household.py`
- Fixtures + round-trip test

**Tests:**
- `HouseholdVendorSchwab(master_account=..., grouping_type="custodial")` CONST
- Members from `linkedAccountHolders[]` carry `source="schwab"`
- `members[].client_ref` is `str`, `accounts[].account_ref` is `str` per M3
- `accounts[]` from `linkedAccounts[]`

**Acceptance Criteria:** AC7.1, AC7.8

### Task 14: Multi-vendor Household translator (`to_canonical_household_multi`)
6-scenario matrix for cross-vendor reconciliation.

**Files:**
- `src/m7_schema_translators/shared/household_merge.py` — `to_canonical_household_multi`, `_compare_household_members`
- `tests/schema-reconciliation/test_m7_multi_vendor_household.py`

**Tests:**
- All 6 scenarios: `{sfsc_only, orion_only, schwab_only, sfsc+orion, sfsc+schwab, all_three}`
- Single-source scenarios assert `reconciliation is None` (AC7.8)
- Multi-source scenarios assert `reconciliation is not None`
- Member-list diff: member present in one vendor but missing in another → EXACT format literal: `"member (client:{client_ref}, role:{role}) present in {vendor_a} but missing in {vendor_b}"` (AC7.5)
- Role mismatch: same client_ref with different role across vendors → EXACT format literal: `"role mismatch for client:{client_ref} — {vendor_a}:{role_a} vs {vendor_b}:{role_b}"` (AC7.5)
- Merge-order: both vendors claim same client_ref with different roles → BOTH records in `members[]` with source attribution + discrepancy emitted (AC7.9)
- `sources_agree=True` when all member sets equal
- `sources_agree=False` + non-empty `discrepancies` when not; `discrepancies` sorted alphabetically
- `last_reconciled` provided by caller; function does NOT call `datetime.utcnow()`
- Discrepancy strings sorted deterministically (alphabetical across ALL discrepancy lines)

**Acceptance Criteria:** AC7.2, AC7.5, AC7.7, AC7.8, AC7.9

### Task 15: Dispatcher wiring + TRANSLATOR_REGISTRY
Wire all 11 translator pairs into the registry. Populate the public API.

**Files:**
- Expand `src/m7_schema_translators/__init__.py` with ≥11-entry `TRANSLATOR_REGISTRY` wrapped in `MappingProxyType`
- Implement `translate_to_canonical` + `translate_from_canonical` dispatchers (explicit params per v0.2.0 fix)

**Tests:**
- `len(TRANSLATOR_REGISTRY) >= 11`
- Import-reachability invariant: `for pair in TRANSLATOR_REGISTRY.values(): importlib.import_module(pair.module_path)` succeeds for every entry (AC2.5)
- Every entry uses a valid `SourceSystem` enum value and a valid `CANONICAL_TYPES` name
- `translate_to_canonical("bogus", "Client", {})` raises `UnregisteredTranslator`
- `translate_to_canonical("salesforce_fsc", "NotAType", {})` raises `UnregisteredTranslator` with `valid_canonical_types` in details (UnregisteredTranslatorDetails TypedDict)
- Every registry entry carries `(schema_version, vendor_api_version)` pair
- `TRANSLATOR_REGISTRY` is MappingProxyType — mutation attempt raises TypeError
- Registry is eagerly constructed at package import (AC13.7) — test by reimporting and asserting keys unchanged

**Acceptance Criteria:** AC1.8, AC2.5, AC2.6, AC2.7, AC8.3, AC13.2, AC13.3, AC13.4, AC13.6, AC13.7

### Task 16: Enum mapping meta-test
Cross-cutting test over all 11 translators.

**Files:**
- `tests/unit/test_m7_enum_mappings.py`

**Tests:**
- For every translator with `ENUM_MAPPINGS`:
  - Every canonical enum member mapped to a vendor value has ≥1 reverse-mapping entry per vendor that touches it
  - Every vendor string → valid canonical enum (instance check)
  - No vendor string maps to two different canonical enums within the same field
  - `ENUM_MAPPINGS` is MappingProxyType — mutation raises TypeError (AC6.5(d))
  - `REVERSE_ENUM_MAPPINGS` same wrap
- Test iterates `TRANSLATOR_REGISTRY` to discover translators — no hard-coded list

**Acceptance Criteria:** AC3.7, AC6.5

### Task 17: Versioning test + CHANGELOGs
Enforce translator version discipline.

**Files:**
- `tests/schema-reconciliation/test_translator_versioning.py`
- CHANGELOG.md already populated per-vendor during Tasks 3-13 (Keep-A-Changelog format)

**Tests:**
- Every translator module has `SCHEMA_VERSION` and `VENDOR_API_VERSION` string constants
- Every version matches regex `^\d+\.\d+\.\d+$`
- Every CHANGELOG.md top entry matches anchored regex `^## \[{SCHEMA_VERSION}\] — \d{4}-\d{2}-\d{2}$` (AC8.5)
- Schwab `VENDOR_API_VERSION == "v1"` (not `"MarketDataAPI 1.0"`) — v0.2.0 regression guard
- `MIN_VENDOR_API_VERSION`/`MAX_VENDOR_API_VERSION`, if present (Phase 3+), trigger `VendorSchemaVersionMismatch` for out-of-window payloads via `packaging.version.Version` comparison

**Acceptance Criteria:** AC8.2, AC8.4, AC8.5, AC8.6

### Task 18: Idempotency property tests + concurrency smoke
Hypothesis-driven determinism + 4-thread concurrency invariant.

**Files:**
- `tests/schema-reconciliation/test_m7_idempotency.py`
- `tests/schema-reconciliation/strategies/{vendor}_{type}.py` — one `@composite` strategy per Phase 2 translator (11 strategies total) — see §Design "Hypothesis Strategy Approach" for SF FSC Client worked example

**Tests:**
- For every translator pair: hypothesis generates ≥100 synthetic vendor-model-valid payloads via `@composite` strategies (AC10.4)
- `model_dump_json(sort_keys=True)` byte-identical for repeated `to_canonical` calls (AC1.3, AC10.6)
- Same for `from_canonical` (AC1.4)
- Test also asserts no mutation of input dict/model (deep-copy-before, assert-after) (AC1.6)
- `@settings(max_examples=100, deadline=500)` per translator; total test-file wall-clock ≤2 min
- `ReconciliationNote.fields_dropped` and `fields_derived` are sorted (AC1.3 pin)
- **Concurrency smoke test (AC10.7):** spawn 4 `threading.Thread` workers, each calls `translate_to_canonical` for every registry pair in a 50-iteration loop; assert all threads produce byte-identical results AND `TRANSLATOR_REGISTRY`/`ENUM_MAPPINGS` unchanged post-run (MappingProxyType prevents mutation by construction)

**Acceptance Criteria:** AC1.3, AC1.4, AC1.6, AC1.8, AC10.4, AC10.6, AC10.7

### Task 19: Reconciliation note PII-free scan (EXTENDED per v0.2.0 fix #16)
Guarantee no PII leaks into audit notes, exception details, or fixture files.

**Files:**
- `tests/schema-reconciliation/test_m7_reconciliation_note_pii_free.py`
- `tests/schema-reconciliation/test_m7_fixture_pii_scan.py` — new in v0.2.0

**Tests (part A — reconciliation notes):**
- Iterate `TRANSLATOR_REGISTRY`. For each translator, build a fixture containing realistic-but-synthetic PII (email `"test@example.invalid"`, ssn_last_four `"1234"`, phone `"+1-555-5551212"`, market_value=1234567.89, account_number="00000001").
- Call translator. Inspect emitted `ReconciliationNote`.
- Assert `str(note)` does NOT contain any of the PII literal values.
- Assert every token in `note.notes` is either in `RECONCILIATION_NOTE_SAFE_FIELDS` OR matches a documented canonical/vendor field name.
- Assert `note.fields_dropped` is a subset of translator's `LOSSY_FIELDS` (forward) or `REVERSE_LOSSY_FIELDS` (reverse).

**Tests (part B — exception details, new in v0.2.0):**
- Iterate `TRANSLATOR_REGISTRY`. For each translator, trigger EACH `TranslationError` subclass by feeding a payload designed to fail (unknown enum, missing required, type coercion, cost basis unmappable).
- Inspect `str(exc)` AND `json.dumps(exc.details)`.
- Assert neither contains any PII literal from the fixture.
- Assert `exc.details` matches the per-subclass TypedDict exactly (AC4.8).
- Assert `UnknownEnumDetails.vendor_value` matches regex `^[A-Za-z0-9_ .\-]+$` (AC14.8 — enum-friendly).

**Tests (part C — fixture PII scan, new in v0.2.0):**
- Scan all `tests/schema-reconciliation/fixtures/**/*.json`. For each file:
  - Email regex: fail if any match ends in `.com`/`.org`/`.net`/`.edu`/`.gov`/`.io`/`.co` (require `.example`/`.invalid`/`.test`/`.localhost` only)
  - SSN regex (`\b\d{3}-\d{2}-\d{4}\b`): fail on any match
  - Phone regex: fail on any match except `555-` prefix (synthetic convention)
  - IBAN regex: fail on any match except `TEST`-prefix
- CI fails with file path + matched pattern on any hit (AC14.9).

**Acceptance Criteria:** AC9.5, AC9.6, AC11.7, AC14.2, AC14.6, AC14.8, AC14.9, AC16.4

### Task 20: DECISION-LOG + package metadata
Document every decision. Ship the package.

**Files:**
- `src/m7_schema_translators/DECISION-LOG.md` — every enum mapping that isn't 1:1, every LOSSY_FIELDS / REVERSE_LOSSY_FIELDS rationale, every COST_BASIS_DEFAULTS rule, SF FSC field-name verification task, cross-references to M3 DECISION-LOG pending items
- `src/m7_schema_translators/pyproject.toml` — package name `m7-schema-translators`
- `src/m7_schema_translators/requirements.txt` — `pydantic>=2.0,<3.0` (exact match to M3), `m3-schema-registry`, `m5-config-loader`

**Tests:**
- DECISION-LOG.md exists and contains Date/Vendor/Canonical Type/Field/Decision/Rationale/Decided By entries for every documented decision
- DECISION-LOG includes entries for: UUID vs str audit decisions (v0.2.0), Person-vs-Business Account branching, Schwab $-prefix handling, Schwab UK PENDING SME, SF FSC field-name PENDING-VERIFICATION, `archetype` no-validator decision, M3 AccountType as SOT (Steering Rule 10 outdated)
- `requirements.txt` grep: contains only pydantic + m3-schema-registry + m5-config-loader. Nothing else.

**Acceptance Criteria:** AC12.3, AC12.5, AC15.1, AC15.2, AC15.3, AC15.4, AC15.5, AC15.6

---

## Review Fix Traceability Table

Every required fix from the LLMJ v1 review (`m7-schema-translators-REVIEW.md`) mapped to the spec section / R / AC / Task where v0.2.0 addresses it. 17 required fixes + key recommended fixes.

### Required Fixes (17)

| # | Review Fix | Addressed In |
|---|-----------|--------------|
| 1 | Fix `UUID` vs `str` mismatch across T4, T5, T7, T8, T9, T10, T11 | §M3 Alignment (full audit table) + every T-table Derivation column now cites M3 type and explicit `str(uuid5(…))` vs bare `uuid5(…)`. T5 uses UUID (Transaction.*_ref are UUID in M3), T4/T8 use `str(uuid5(...))` (Holding.*_ref are str), T9/T10 use `str(uuid5(...))` for holding_ref (TaxLot.holding_ref is str), T2/T6/T11 use `str(uuid5(...))` for Household members/accounts (str in M3). |
| 2 | Fix T5 collapsing `source_id` and `transaction_id` | T5 rewritten with TWO explicit rows: `transaction_id: UUID = uuid5(...)` primary key AND `source_id: str = direct raw vendor`. Task 7 tests assert `source_id != str(transaction_id)`. |
| 3 | Enumerate missing UUID namespaces in AC10.5 | AC10.5 — **10 namespaces** (up from 7): added `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS`; `ORDER_NS` reserved but `None` in Phase 2. |
| 4 | Fill T6 (Orion → Household) and T10 (Orion → TaxLot) with explicit field tables | T6 fully detailed (OrionHousehold → Household with every field, LOSSY_FIELDS, REVERSE_LOSSY_FIELDS, role mapping). T10 fully detailed (OrionTaxLot nested in Position, cost-basis normalization path, every field). |
| 5 | Verify SF FSC field names or document as PENDING-VERIFICATION | Known Blockers row "SF FSC field names" — status **PENDING-VERIFICATION** with real-org SOQL verification as pre-GA Task. T1 / T2 / T3 tables flag specific fields. DECISION-LOG entry pinned via AC15.6. |
| 6 | Remove T1 archetype validation claim | T1 Derivation cell for `archetype` now reads: "direct. **M7 does NOT validate {mass_affluent, hnw, uhnw}** — M3 has no validator. Unknown value passes through as str." Task 3 regression guard tests unknown value passes through. |
| 7 | Document AccountType mismatch (steering Rule 10 vs M3) | Known Blockers "AccountType mismatch" row: "M3 `types.py` is SOT. Steering Rule 10 is outdated draft. M7 T-tables use M3 values." Enum matrix preface cites M3 SOT explicitly. |
| 7a | `AccountType.B457` value `"457"` not `"457b"` — 457 vendor mapping | Enum matrix Orion and Schwab sections include explicit "(no string)" row for 457: "No Orion/Schwab `457` vendor string mapped in Phase 2 Lighthouse fixtures. First encounter → `UnknownEnumValue`, MINOR translator bump." Documented in Known Blockers. |
| 8 | Fix T9/Task 12 contradiction on `source_cost_basis_method` vendor-silent case | T9 Derivation for `source_cost_basis_method`: "**direct vendor string when vendor reported; `None` when vendor silent (provenance lives in `ReconciliationNote.cost_basis_source.method_origin == "vendor_default"`).** v0.2.0 fix." AC5.5 pins the rule. Task 12 tests `source_cost_basis_method is None` on vendor-silent. Task 9 same. |
| 9 | Fix M6 Integration Point — explicit dispatcher params, no `req.target.*` | §Integration Point with M6 rewritten with explicit `source_system` / `canonical_type` parameters. AC13.2 pins the dispatcher signature. M6 Phase 2 wiring extracts from request-level fields via M6 spec amendment (deferred to M6). |
| 10 | Reconcile M8 / M11 consumers per ARCH-09 | Header line 8 (Consumers): **M8 REMOVED.** Documented "M8 REMOVED from consumers per ARCH-09 dependency matrix audit". §Integration Point with M11 (NEW) documents dual-caller audit contract: default path M6-as-caller (Phase 2); M11-as-caller path deferred to lighthouse-2 with audit-bypass prevention rules. |
| 11 | Fix package / import / directory naming | §Design "Directory / Package / Import Naming" table: directory = `src/m7_schema_translators/`, package = `m7-schema-translators`, import = `m7_schema_translators`. Matches M3/M5/M6 pattern exactly. Changelog row documents the transition. |
| 12 | Make AC12.4 a positive AST-enforced allow-list | AC12.4 completely rewritten with implementation outline (ast.parse, ast.ImportFrom, `ALLOWED_M5 = frozenset({"Archetype","Jurisdiction","RegistrationType"})`, `assert imported.issubset(ALLOWED_M5)`). Task 2 writes this test. |
| 13 | Specify Hypothesis strategy approach in Task 18 (one example) | §Design "Hypothesis Strategy Approach" — complete SF FSC Client `@composite` strategy shown with PII-safe alphabets/domains/phone prefixes. Pattern replicated across 11 strategies (one per translator). |
| 14 | Pin discrepancy-string format in AC7.5 | AC7.5 pins TWO exact format literals: `"member (client:{client_ref}, role:{role}) present in {vendor_a} but missing in {vendor_b}"` and `"role mismatch for client:{client_ref} — {vendor_a}:{role_a} vs {vendor_b}:{role_b}"`. Task 14 tests these literals. |
| 15 | Document single-vendor vs multi-vendor Household reconciliation | R7 AC7.8 — **Explicit rule:** single-vendor → `reconciliation=None`; multi-vendor → populated. Downstream consumers MUST check `reconciliation is None` to distinguish. Task 4/8/13 tests single-source path; Task 14 tests multi-source path. |
| 16 | Extend PII-free scan (Task 19) — details + fixtures | Task 19 rewritten with parts A (note), B (`TranslationError.details` + per-subclass TypedDict assert + enum-friendly regex AC14.8), C (fixture file scan — email/SSN/phone/IBAN regex with synthetic-only allowlist). AC14.9 pins it. |
| 17 | Add reverse-lossy section to every T-table | Every T1-T11 table now declares `REVERSE_LOSSY_FIELDS: frozenset[str]` with the vendor/canonical fields that don't round-trip back. AC11.4 requires it. Task 5 tests `funding_pct` in REVERSE_LOSSY_FIELDS; Task 10 `net_worth`; Task 11 `market_value_includes_accrued`. |

### Recommended Fixes Folded In (key items)

| Review Recommendation | Addressed In |
|-----------------------|--------------|
| `types.MappingProxyType` on `ENUM_MAPPINGS` and `TRANSLATOR_REGISTRY` | AC1.8, AC3.7, AC5.2, AC5.3, AC6.5(d), AC13.2. Test asserts mutation raises TypeError. |
| `len(TRANSLATOR_REGISTRY) >= 11` with per-entry task invariant | AC2.5 — `>= 11`, import-reachability invariant via `module_path` field on `TranslatorPair`. |
| Add `warnings`, `tempfile`, `io.open`, `os.open` to R14 forbidden imports | AC14.4 — forbidden list expanded explicitly. |
| Concurrency smoke test | AC10.7 + Task 18 — 4-thread smoke test asserting byte-identical results. |
| Observability handoff contract (M7 details → M6 → M10) | R16 — **new requirement** — + AC16.1/AC16.2/AC16.3/AC16.4. |
| TypedDict per `TranslationError` subclass | AC4.8 — 7 TypedDicts, one per subclass. Task 19 part B tests. |
| Pin Schwab API version to URL path `v1` | AC8.2 Schwab = `"v1"`. T8/T9/T11 tables updated. Task 11 regression guard. |
| Pin pydantic version consistent with M3 | AC12.3 + Dependencies section — `pydantic>=2.0,<3.0` exact match to `src/m3_schema_registry/pyproject.toml`. |
| `@pytest.mark.xfail(reason="Schwab UK PENDING SME")` skeleton | §T9 Schwab UK xfail fixture skeleton shown verbatim. Task 12 includes fixture. |
| SF FSC Person vs Business Account branching | T1 template includes `@model_validator(mode="after")` branching rule. Task 3 fixtures include `business_account.json`. |
| CI time bounds on Hypothesis | AC10.4 — `@settings(max_examples=100, deadline=500)`, total ≤ 2 min. |
| Partial-data Orion Position with empty taxLots[] | T4 "Partial-data rule" note + Task 6 test. |
| Vendor-ID hostile-character handling | AC10.8 + R14 `vendor_id_validator.py` helper. Task 3 test triggers `vendor_id_invalid_chars`. |
| `MIN_VENDOR_API_VERSION` / `MAX_VENDOR_API_VERSION` semantics | AC8.6 — "Phase 2: no window; vendor API bump = MAJOR translator bump. Reserved for Phase 3 use; semver via `packaging.version.Version`." |
| Null-PII handling (empty-string, whitespace, None) | AC10.9 — `str_strip_whitespace=True` + vendor model validator collapses `"   "` to `None`. Task 3 test. |
| Registry eager vs lazy construction | AC13.7 — **eager** (fail-closed). Documented rationale. |
| `fields_dropped`/`fields_derived` ordering | AC1.3 pin — sorted alphabetically before serialization. Task 18 regression guard. |
| Decimal vs float inherited decision | AC11.8 — `math.isclose` tolerance on money-field equality. |

---

## Steering-Rule Traceability

| Steering Rule | Addressed In |
|--------------|--------------|
| Steering Rule 9 (no cross-module imports) | R12 + §Module Boundary + Task 2 (AST allow-list) + Task 15 (registry construction) |
| Steering Rule 16 (cost_basis never null) | R5 + §Cost Basis Normalization Matrix + Task 9 + Task 12 + TaxLot translator tests |
| Steering Rule 19 (wsp_section on OPA rules) | Noted out-of-scope — ComplianceAlert deferred to M7-lighthouse-2 |
| Steering Rule 32 (security per module) | R10, R12, R14, R16 + §Security Constraints + Task 2 + Task 19 |
| Steering Rule 34 (no mocks at boundaries) | R11 round-trip tests use real `M3` canonical types + real Pydantic vendor models. Fixtures are synthetic data, not mocks. Task 19 Part C scans fixtures for PII-shaped tokens. |
| 7-step playbook — Spec-first | This document (v0.2.0 post-LLMJ-v1 fix pass) |
| TDD per-module | Tasks pair implementation + tests (Tasks 3-13 all produce both). Task 2 writes negative tests FIRST. |
| Integration gate | Task 15 (dispatcher + registry) + Task 14 (multi-vendor Household) are M7-internal integration. Cross-module integration with M6 is scoped in M6 Phase 2 migration (referenced in §Integration Point with M6), not this spec. Cross-module integration with M11 is scoped in §Integration Point with M11 (dual-caller audit contract). |

---

## Appendix A — Per-Translator M3 Type-Check Invariant Table

For reviewer convenience, a condensed per-translator assertion table that CI can generate automatically from the T-tables. Each row is an `isinstance(…)` or `is None` invariant asserted in the round-trip test.

### T1 SF FSC → Client — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.firm_id` | `isinstance(_, UUID)` |
| `canonical.advisor_ref` | `isinstance(_, UUID) or _ is None` |
| `canonical.household_ref` | `isinstance(_, UUID) or _ is None` |
| `canonical.accounts` | `isinstance(_, list) and all(isinstance(e, UUID) for e in _)` |
| `canonical.source_id` | `isinstance(_, str) and len(_) > 0` |
| `canonical.source_system` | `_ == "salesforce_fsc"` |
| `canonical.archetype` | `_ is None or isinstance(_, str)` (no validator) |

### T2 SF FSC → Household — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.primary_source` | `_ == "salesforce_fsc"` |
| `canonical.members` | `isinstance(_, list)` |
| `canonical.members[0].client_ref` | **`isinstance(_, str)`** (NOT UUID — M3) |
| `canonical.members[0].source` | `_ == "salesforce_fsc"` |
| `canonical.accounts` | `isinstance(_, list)` |
| `canonical.accounts[0].account_ref` | **`isinstance(_, str)`** (NOT UUID — M3) |
| `canonical.vendor_mappings.salesforce_fsc.grouping_type` | `_ == "relationship"` (CONST) |
| `canonical.reconciliation` | `_ is None` (single-vendor) |

### T3 SF FSC → Goal — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.client_ref` | `isinstance(_, UUID)` (REQUIRED) |
| `canonical.household_ref` | `isinstance(_, UUID) or _ is None` |
| `canonical.plan_ref` | `_ is None` (SF FSC does not link plans) |
| `canonical.linked_accounts` | `all(isinstance(e, UUID) for e in _)` |
| `canonical.goal_type` | `isinstance(_, GoalType)` |
| `canonical.status` | `isinstance(_, GoalStatus)` |
| `canonical.funding_pct` (reverse) | in `REVERSE_LOSSY_FIELDS` |

### T4 Orion → Holding — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.account_ref` | **`isinstance(_, str)`** (NOT UUID — M3 `Holding.account_ref: str`) |
| `canonical.client_ref` | **`isinstance(_, str) or _ is None`** (M3 `Optional[str]`) |
| `canonical.source_id` | `isinstance(_, str)` (raw Orion `positionId`) |
| `canonical.source_system` | `_ == "orion"` |
| `canonical.market_value_includes_accrued` | `isinstance(_, bool)` (Orion explicit) |
| `canonical.tax_lots` | `isinstance(_, list)` (empty ok) |

### T5 Orion → Transaction — type invariants (CRITICAL v0.2.0 FIX)

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.transaction_id` | **`isinstance(_, UUID)`** (primary key, UUID-derived) |
| `canonical.source_id` | **`isinstance(_, str) and _ == vendor.transactionId`** (raw vendor, SEPARATE from `transaction_id`) |
| `canonical.transaction_id` ≠ `canonical.source_id` | **`str(canonical.transaction_id) != canonical.source_id`** (different values — regression guard) |
| `canonical.account_ref` | **`isinstance(_, UUID)`** (NOT str — Transaction uses UUID in M3) |
| `canonical.client_ref` | **`isinstance(_, UUID) or _ is None`** |
| `canonical.order_ref` | `_ is None` (Orion doesn't track 007 orders in Phase 2) |
| `canonical.transaction_type` | `isinstance(_, TransactionType)` |
| `canonical.source_transaction_type` | `isinstance(_, str) or _ is None` (vendor raw preserved for audit) |
| `canonical.trace_id` | `_ is None` (M7 does not set it; M6 attaches externally) |

### T6 Orion → Household — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.primary_source` | `_ == "orion"` |
| `canonical.members[0].client_ref` | `isinstance(_, str)` (M3) |
| `canonical.members[0].source` | `_ == "orion"` |
| `canonical.accounts[0].account_ref` | `isinstance(_, str)` (M3) |
| `canonical.vendor_mappings.orion.grouping_type` | `_ == "portfolio_management"` (CONST) |
| `canonical.reconciliation` | `_ is None` (single-vendor) |

### T7 eMoney → PlanSummary — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.client_ref` | `isinstance(_, UUID)` (REQUIRED) |
| `canonical.household_ref` | `isinstance(_, UUID) or _ is None` |
| `canonical.goals` | `all(isinstance(e, UUID) for e in _)` |
| `canonical.probability_of_success` | `0.0 <= _ <= 100.0` |
| `canonical.net_worth` (reverse) | in `REVERSE_LOSSY_FIELDS` (derived) |
| `canonical.vendor_mappings.emoney` | `isinstance(_, PlanVendorEMoney)` |
| Vendor model rejects `fullPlanBody` | raises `ValidationError` via `extra="forbid"` |

### T8 Schwab → Holding — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.account_ref` | **`isinstance(_, str)`** (M3) |
| `canonical.client_ref` | **`isinstance(_, str) or _ is None`** (M3) |
| `canonical.market_value_includes_accrued` | `_ is False` (Schwab convention — DERIVED) |
| Vendor `$`-prefix → canonical float | `position.costBasis="$1,234.56"` → `canonical.cost_basis == 1234.56` |
| `canonical.unrealized_gain_loss_pct` | vendor `0.085` → canonical `8.5` (×100 derivation) |

### T9 Schwab → TaxLot — type invariants (CRITICAL v0.2.0 FIX)

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.lot_id` | `isinstance(_, UUID)` (REQUIRED) |
| `canonical.holding_ref` | **`isinstance(_, str)`** (M3) — `str(uuid5(HOLDING_NS, f"schwab:{parent.id}"))` |
| `canonical.cost_basis_method` | `isinstance(_, CostBasisMethod)` (NEVER None — Steering Rule 16) |
| `canonical.source_cost_basis_method` | `isinstance(_, str) or _ is None` (**`None` when vendor silent — v0.2.0 fix**) |
| `canonical.source_custodian` | `_ == "schwab"` |
| Note's `cost_basis_source.method_origin` | `_ in {"vendor_reported", "vendor_default", "derived"}` |

### T10 Orion → TaxLot — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.lot_id` | `isinstance(_, UUID)` |
| `canonical.holding_ref` | **`isinstance(_, str)`** (M3) — `str(uuid5(HOLDING_NS, f"orion:{parent.positionId}"))` |
| `canonical.cost_basis_method` | `isinstance(_, CostBasisMethod)` (NEVER None) |
| `canonical.source_cost_basis_method` | `isinstance(_, str) or _ is None` |
| `canonical.source_custodian` | `_ == "orion"` |

### T11 Schwab → Household — type invariants

| Canonical Field | Invariant |
|----------------|-----------|
| `canonical.canonical_id` | `isinstance(_, UUID)` |
| `canonical.primary_source` | `_ == "schwab"` |
| `canonical.members[0].client_ref` | `isinstance(_, str)` (M3) |
| `canonical.accounts[0].account_ref` | `isinstance(_, str)` (M3) |
| `canonical.vendor_mappings.schwab.grouping_type` | `_ == "custodial"` (CONST) |
| `canonical.reconciliation` | `_ is None` (single-vendor) |

---

## Appendix B — Shared Infrastructure Stubs

Implementation stubs for the shared pieces cited across tasks. Spec-level, not code-delivery — shows the shape consumers rely on.

### B.1 `errors.py` skeleton

```python
# src/m7_schema_translators/errors.py
from __future__ import annotations
from typing import Optional, TypedDict

VALID_REASON_CODES: frozenset[str] = frozenset({
    "unknown_enum_value", "missing_required_field", "type_coercion_failed",
    "vendor_id_invalid_chars", "cost_basis_unmappable", "unsupported_vendor_value",
    "ambiguous_mapping", "vendor_schema_version_mismatch", "round_trip_divergence",
    "unregistered_translator", "vendor_payload_validation_failed",
})

class UnknownEnumDetails(TypedDict):
    vendor_value: str
    valid_values: list[str]

class MissingRequiredDetails(TypedDict):
    field_name: str

class TypeCoercionDetails(TypedDict):
    expected_type: str
    got_type: str

class CostBasisUnmappableDetails(TypedDict):
    vendor_value: Optional[str]
    account_type_group: Optional[str]
    security_class: Optional[str]
    jurisdiction: Optional[str]

class VendorSchemaVersionMismatchDetails(TypedDict):
    observed_version: str
    min_supported: str
    max_supported: str

class RoundTripDivergenceDetails(TypedDict):
    field_path: str
    forward_hash: str
    roundtrip_hash: str

class UnregisteredTranslatorDetails(TypedDict):
    valid_source_systems: list[str]
    valid_canonical_types: list[str]

class TranslationError(Exception):
    def __init__(self, *, reason_code, vendor, canonical_type, field_path, details):
        assert reason_code in VALID_REASON_CODES
        self.reason_code = reason_code
        self.vendor = vendor
        self.canonical_type = canonical_type
        self.field_path = field_path
        self.details = details
        super().__init__(self._format())
    def _format(self) -> str:
        summary = ", ".join(f"{k}={v}" for k, v in sorted(self.details.items()))
        return f"[{self.reason_code}] {self.vendor}.{self.canonical_type}.{self.field_path}: {summary}"

class UnknownEnumValue(TranslationError): ...
class MissingRequiredField(TranslationError): ...
class TypeCoercionError(TranslationError): ...
class CostBasisUnmappable(TranslationError): ...
class VendorSchemaVersionMismatch(TranslationError): ...
class RoundTripDivergence(TranslationError): ...
class UnregisteredTranslator(TranslationError): ...
```

### B.2 `shared/namespaces.py` skeleton

```python
# src/m7_schema_translators/shared/namespaces.py — all UUID namespaces, checked in
from uuid import UUID

CLIENT_NS       = UUID("b1f4e5a0-0000-5000-8000-000000000001")
HOUSEHOLD_NS    = UUID("b1f4e5a0-0000-5000-8000-000000000002")
HOLDING_NS      = UUID("b1f4e5a0-0000-5000-8000-000000000003")
TAXLOT_NS       = UUID("b1f4e5a0-0000-5000-8000-000000000004")
TRANSACTION_NS  = UUID("b1f4e5a0-0000-5000-8000-000000000005")
GOAL_NS         = UUID("b1f4e5a0-0000-5000-8000-000000000006")
PLAN_NS         = UUID("b1f4e5a0-0000-5000-8000-000000000007")
FIRM_NS         = UUID("b1f4e5a0-0000-5000-8000-000000000008")  # v0.2.0 addition
ACCOUNT_NS      = UUID("b1f4e5a0-0000-5000-8000-000000000009")  # v0.2.0 addition
ADVISOR_NS      = UUID("b1f4e5a0-0000-5000-8000-00000000000a")  # v0.2.0 addition
ORDER_NS        = UUID("b1f4e5a0-0000-5000-8000-00000000000b")  # reserved, Phase 2 uses None
```

Actual UUID literal values will be generated once at Phase 2 infrastructure setup (Task 1) and committed — any change to a namespace value is a MAJOR version bump for EVERY translator that uses it (IDs would no longer round-trip).

### B.3 `shared/vendor_id_validator.py` skeleton (AC10.8)

```python
# src/m7_schema_translators/shared/vendor_id_validator.py
import re
from m7_schema_translators.errors import TypeCoercionError

_VENDOR_ID_PATTERN = re.compile(r"^[a-zA-Z0-9._\-]+$")

def validate_vendor_id_chars(vendor_id: str, *, vendor: str, canonical_type: str, field_path: str) -> None:
    if not isinstance(vendor_id, str) or not _VENDOR_ID_PATTERN.match(vendor_id):
        raise TypeCoercionError(
            reason_code="vendor_id_invalid_chars",
            vendor=vendor, canonical_type=canonical_type, field_path=field_path,
            details={
                "expected_type": "vendor_id matching ^[a-zA-Z0-9._\\-]+$",
                "got_type": "contains_disallowed_characters",
            },
        )
```

### B.4 `shared/reconciliation_note.py` skeleton

```python
# src/m7_schema_translators/shared/reconciliation_note.py
from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field

RECONCILIATION_NOTE_SAFE_FIELDS: frozenset[str] = frozenset({
    "vendor_reported", "vendor_default", "derived",
    "orion_trust_label_ambiguous", "schwab_ira_label_ambiguous",
    "canonical_order_ref_preserved_in_custom_attributes",
    "schwab_dollar_prefix_stripped", "schwab_unrealized_pct_x100",
    "single_vendor_no_reconciliation",
})

class CostBasisSource(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    vendor_field: str
    vendor_value: Optional[str]
    canonical_value: str
    method_origin: Literal["vendor_reported", "vendor_default", "derived"]
    confidence: Literal["high", "medium", "low"]

class ReconciliationNote(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    trace_id: Optional[str] = None
    vendor: str
    canonical_type: str
    direction: Literal["to_canonical", "from_canonical"]
    fields_dropped: list[str] = Field(default_factory=list)
    fields_derived: list[str] = Field(default_factory=list)
    cost_basis_source: Optional[CostBasisSource] = None
    vendor_schema_version: str
    translator_schema_version: str
    notes: list[str] = Field(default_factory=list)
```

### B.5 `shared/dispatcher.py` skeleton

```python
# src/m7_schema_translators/shared/dispatcher.py
from dataclasses import dataclass
from typing import Callable
from pydantic import BaseModel
from m7_schema_translators.shared.reconciliation_note import ReconciliationNote

@dataclass(frozen=True)
class TranslatorPair:
    to_canonical: Callable[[dict], tuple[BaseModel, ReconciliationNote]]
    from_canonical: Callable[[BaseModel], tuple[BaseModel, ReconciliationNote]]
    schema_version: str
    vendor_api_version: str
    module_path: str  # for AC2.5 import-reachability invariant
```

### B.6 `__init__.py` eager-registry construction skeleton (AC13.7)

```python
# src/m7_schema_translators/__init__.py
from types import MappingProxyType
from m3_schema_registry import SourceSystem, CANONICAL_TYPES
# EAGER imports — vendor-module import failure takes down the whole package (fail-closed)
from m7_schema_translators.salesforce_fsc.client import (
    to_canonical_client as _sf_client_fwd,
    from_canonical_client as _sf_client_rev,
    SCHEMA_VERSION as _sf_client_v,
    VENDOR_API_VERSION as _sf_client_api,
)
# ... (similar imports for every translator)
from m7_schema_translators.shared.dispatcher import TranslatorPair
from m7_schema_translators.errors import (
    TranslationError, UnregisteredTranslator, VALID_REASON_CODES,
    UnknownEnumValue, MissingRequiredField, TypeCoercionError,
    CostBasisUnmappable, VendorSchemaVersionMismatch, RoundTripDivergence,
)
from m7_schema_translators.shared.reconciliation_note import ReconciliationNote, CostBasisSource

SCHEMA_VERSION: str = "0.1.0"

_REGISTRY_RAW: dict[tuple[str, str], TranslatorPair] = {
    ("salesforce_fsc", "Client"): TranslatorPair(
        to_canonical=_sf_client_fwd, from_canonical=_sf_client_rev,
        schema_version=_sf_client_v, vendor_api_version=_sf_client_api,
        module_path="m7_schema_translators.salesforce_fsc.client",
    ),
    # ... 10 more entries
}
TRANSLATOR_REGISTRY: MappingProxyType[tuple[str, str], TranslatorPair] = MappingProxyType(_REGISTRY_RAW)

def translate_to_canonical(source_system: str, canonical_type: str, vendor_payload: dict):
    if source_system not in {s.value for s in SourceSystem} or canonical_type not in CANONICAL_TYPES:
        raise UnregisteredTranslator(
            reason_code="unregistered_translator",
            vendor=source_system, canonical_type=canonical_type, field_path="",
            details={
                "valid_source_systems": sorted(s.value for s in SourceSystem),
                "valid_canonical_types": sorted(CANONICAL_TYPES.keys()),
            },
        )
    key = (source_system, canonical_type)
    if key not in TRANSLATOR_REGISTRY:
        raise UnregisteredTranslator(
            reason_code="unregistered_translator",
            vendor=source_system, canonical_type=canonical_type, field_path="",
            details={
                "valid_source_systems": sorted({k[0] for k in TRANSLATOR_REGISTRY}),
                "valid_canonical_types": sorted({k[1] for k in TRANSLATOR_REGISTRY}),
            },
        )
    return TRANSLATOR_REGISTRY[key].to_canonical(vendor_payload)

__all__ = [
    "TRANSLATOR_REGISTRY", "translate_to_canonical", "translate_from_canonical",
    "TranslationError", "UnknownEnumValue", "MissingRequiredField", "TypeCoercionError",
    "CostBasisUnmappable", "VendorSchemaVersionMismatch", "RoundTripDivergence",
    "UnregisteredTranslator", "ReconciliationNote", "CostBasisSource", "TranslatorPair",
    "SCHEMA_VERSION", "VALID_REASON_CODES",
]
```

---

## Appendix C — Sample DECISION-LOG Entries (v0.2.0 starter set)

Starter entries for `src/m7_schema_translators/DECISION-LOG.md` that Task 20 must populate. Format matches M3 convention (Date, Vendor, Canonical Type, Field, Decision, Rationale, Decided By).

| Date | Vendor | Canonical Type | Field | Decision | Rationale | Decided By |
|------|--------|----------------|-------|----------|-----------|------------|
| 2026-04-26 | all | TaxLot | `source_cost_basis_method` on vendor-silent case | Store `None`, not vendor-silent marker string | M3 allows `Optional[str]`. Provenance lives in `ReconciliationNote.cost_basis_source.method_origin == "vendor_default"`. v0.2.0 fix to T9/Task 12 contradiction. | Architect (v0.2.0 spec rewrite) |
| 2026-04-26 | all | (namespace) | `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS` | Added as 3 new UUID5 namespaces | v0.1.0 T1 table used these namespaces but did not declare them in AC10.5. v0.2.0 enumerates all 10 (+ `ORDER_NS` reserved). | Architect (v0.2.0 spec rewrite) |
| 2026-04-26 | salesforce_fsc | Client | `archetype` validator | No M7-side validation; pass vendor string through as `str` | M3 `Client.archetype: Optional[str]` has NO Pydantic validator. Adding a validator is an M3 change — M3 is in Phase 0 and locked. Document as pass-through. | Architect (v0.2.0 spec rewrite) |
| 2026-04-26 | salesforce_fsc | Client, Household, Goal | `FinServ__AccountIds__c`, `FinServ__HouseholdId__c`, `FinServ__ClientArchetype__c`, `FinServ__KYCStatus__c`, `FinServ__KYCLastCompleted__c`, `FinServ__LastSSNDigits__c`, `FinServ__TaxID__c` | Assumed per generic FSC extension convention | Not yet verified against live SF FSC v59.0 org via SOQL. PENDING-VERIFICATION pre-GA. MINOR translator bump when verified. | Architect (v0.2.0 spec rewrite) + PENDING verification owner |
| 2026-04-26 | all | (AccountType) | M3 is SOT (not Steering Rule 10) | Steering Rule 10 uses an outdated draft listing `individual`/`joint_tos`/`pension` etc. M3 actually uses `TAXABLE`/`TRADITIONAL_IRA`/`ERISA_PENSION` etc. | M7 T-tables align to M3 `types.py` (verified 2026-04-26). Documented in Known Blockers. | Architect |
| 2026-04-26 | orion, schwab | Holding, TaxLot | `account_type = "457"` vendor string | No Phase 2 Lighthouse vendor-string mapping for 457 accounts | M3 `AccountType.B457` value is `"457"` (not "457b"). Orion/Schwab lighthouse fixtures do not include 457 accounts. First encounter → `UnknownEnumValue` + MINOR translator bump with new mapping row. | Architect |
| 2026-04-26 | schwab | all | `VENDOR_API_VERSION` | `"v1"` (not `"MarketDataAPI 1.0"`) | Schwab uses URL path versioning (`/v1/positions`, `/v1/taxlots`). v0.1.0 used a marketing label; v0.2.0 pins to URL path version. | Architect (v0.2.0 spec rewrite) |
| 2026-04-26 | schwab | TaxLot | Schwab UK `"SpecificLot"` | Raise `CostBasisUnmappable(reason_code="ambiguous_mapping")` | UK default is FIFO; Schwab reporting SpecificLot in a UK account is ambiguous. PENDING SME — IMPL-06 follow-up. Fixture marked `@pytest.mark.xfail`. | Architect + Compliance SME (PENDING) |
| 2026-04-26 | schwab | Holding, TaxLot | `$`-prefixed numeric strings | Vendor model `@field_validator(..., mode="before")` strips `"$"` and `","` before type coercion | Schwab occasionally returns `"$1,234.56"` instead of a float. Handled at vendor-model boundary so translator functions see clean floats. | Architect |
| 2026-04-26 | orion | Transaction | `transaction_id` vs `source_id` | TWO separate fields: `transaction_id: UUID = uuid5(TRANSACTION_NS, ...)` AND `source_id: str = direct raw vendor` | M3 defines these as distinct columns. v0.1.0 collapsed them — accuracy defect. v0.2.0 fix. | Architect (v0.2.0 spec rewrite) |
| 2026-04-26 | salesforce_fsc | Client | Person Account vs Business Account | Vendor model `@model_validator(mode="after")` enforces: `client_type == "entity"` implies all individual-PII fields (first_name, last_name, email, phone, dob) are `None` | SF FSC has two RecordTypes with different Contact shapes. Review recommendation. Task 3 fixtures include `business_account.json`. | Architect (review fix) |
| 2026-04-26 | all | Household | Single-vendor vs multi-vendor `reconciliation` | Single-vendor → `reconciliation=None`. Multi-vendor → populated. Downstream consumers MUST check `reconciliation is None` to distinguish. | Downstream consumer disambiguation. v0.2.0 required fix. | Architect (v0.2.0 spec rewrite) |
| 2026-04-26 | all | Household | Member merge-order on role mismatch | Preserve BOTH records in `members[]` with respective `source` attribution; emit role-mismatch discrepancy; M7 does NOT pick a winner | Review gap item — merge-order rule was silent in v0.1.0. Resolution deferred to SME. | Architect (v0.2.0 spec rewrite) |

Task 20 must add entries for every per-translator non-1:1 enum mapping, every `LOSSY_FIELDS` / `REVERSE_LOSSY_FIELDS` entry, every `COST_BASIS_DEFAULTS` row, and cross-references to M3 DECISION-LOG pending items (Holding.accrued_interest, SecurityIdentifier.canonical_id, Performance.methodology).

---

## Appendix D — Cross-Reference to Review Document

Reviewer convenience: direct map from review section / weakness to v0.2.0 section where the fix lives.

| Review v1 Section | Review Fix # | v0.2.0 Location |
|-------------------|-------------|-----------------|
| §2 Weakness #1 (T1 namespaces) | Fix #3 | AC10.5 — 10 namespaces enumerated |
| §2 Weakness #2 (T1 display_name empty guard) | recommended | T1 row: "empty → `MissingRequiredField`" |
| §2 Weakness #3 (UUID vs str across T4-T11) | Fix #1 | §M3 Alignment + every T-table + Appendix A |
| §2 Weakness #4 (T5 collapsed fields) | Fix #2 | T5 rewritten — two distinct rows |
| §2 Weakness #5 (T5 trace_id) | clarified | T5 `trace_id` row — M6 attaches externally |
| §2 Weakness #6 (T5 reverse order_ref) | clarified | T5 Reverse note — `customAttributes["order_ref"]` |
| §2 Weakness #7 (SF FSC field names T2) | Fix #5 | Known Blockers PENDING-VERIFICATION + DECISION-LOG |
| §2 Weakness #8 (T3 SF FSC HouseholdId) | Fix #5 | Same |
| §2 Weakness #9 (T1 archetype validator) | Fix #6 | T1 `archetype` row + DECISION-LOG + Task 3 guard |
| §2 Weakness #10 (AccountType three-way) | Fix #7 | Known Blockers + §Enum Matrix preface |
| §2 Weakness #11 (`AccountType.B457`) | Fix #7a | Enum matrix "(no string)" rows |
| §2 Weakness #12 (T9 holding_ref) | Fix #1 | T9 — `str(uuid5(...))` |
| §2 Weakness #13 (T7 probability_of_success) | clarified | T7 row — `TypeCoercionError` on out-of-range |
| §2 Weakness #14 (T9/Task 12 contradiction) | Fix #8 | T9 + AC5.5 + Task 9/12 tests |
| §2 Weakness #15 (T6/T10 stubs) | Fix #4 | T6 + T10 fully-detailed tables |
| §2 Weakness #16 (Orion API version) | recommended | DECISION-LOG cross-reference pending |
| §3 Weakness #1 (`warnings` forbidden) | recommended | AC14.4 expanded |
| §3 Weakness #3 (details PII) | Fix #16 Part B | AC14.6, AC14.9, Task 19 Part B |
| §3 Weakness #4 (fixture scan) | Fix #16 Part C | AC14.9 + Task 19 Part C |
| §3 Weakness #5 (forbidden list) | recommended | AC14.4 — tempfile, io.open, os.open added |
| §3 Weakness #6 (enum vendor_value PII) | recommended | AC14.8 — enum-friendly regex |
| §3 Weakness #7 (AC12.4 positive allow-list) | Fix #12 | AC12.4 rewritten + ast outline |
| §3 Weakness #8 (whitespace PII) | recommended | AC10.9 |
| §4 Weakness #1 (Hypothesis strategy) | Fix #13 | §Design "Hypothesis Strategy" + worked example |
| §4 Weakness #2 (byte-identical list ordering) | recommended | AC1.3 sorted lists pin |
| §4 Weakness #4 (source_cost_basis_method) | clarified | AC11.5 |
| §4 Weakness #6 (discrepancy format) | Fix #14 | AC7.5 format literals pinned |
| §4 Weakness #7 (Schwab UK xfail) | recommended | §T9 xfail skeleton + Task 12 fixture |
| §4 Weakness #8 (Hypothesis CI time) | recommended | AC10.4 `@settings` |
| §4 Weakness #9 (concurrency) | recommended | AC10.7 + Task 18 |
| §4 Weakness #10 (multi-vendor double-trip) | clarified | AC11.3 + AC7.7 |
| §4 Weakness #11 (CHANGELOG fragility) | recommended | AC8.5 Keep-A-Changelog anchored regex |
| §5 Weakness #1 (M6 target attribute access) | Fix #9 | AC13.2 + §Integration Point with M6 rewrite |
| §5 Weakness #2 (M6 Stage 6 payload) | deferred | §Integration Point with M6 defers to M6 spec |
| §5 Weakness #3 (M11 audit bypass) | Fix #10 | §Integration Point with M11 dual-caller contract |
| §5 Weakness #4 (M8 invented consumer) | Fix #10 | Header line 8 — M8 REMOVED |
| §5 Weakness #5 (directory naming) | Fix #11 | §Directory / Package / Import Naming |
| §5 Weakness #6 (package vs import) | Fix #11 | Same |
| §5 Weakness #7 (Schwab version) | recommended | AC8.2 `"v1"` |
| §5 Weakness #9 (pydantic pin) | recommended | AC12.3 + Dependencies |
| §6 Weakness #1 (observability) | recommended, major | R16 new requirement |
| §6 Weakness #2 (MappingProxyType) | recommended | AC1.8, AC3.7, AC5.2/5.3, AC6.5(d), AC13.2 |
| §6 Weakness #3 (version-mismatch) | deferred | AC8.6 notes future compat API |
| §6 Weakness #4 (hardcoded 11) | recommended | AC2.5 `>= 11` |
| §6 Weakness #6 (reverse direction) | Fix #17 | Every T-table `REVERSE_LOSSY_FIELDS` |
| §6 Weakness #7 (partial-data Orion) | recommended | T4 "Partial-data rule" note |
| §6 Weakness #9 (Person vs Business Account) | recommended | T1 `@model_validator` + Task 3 fixture |
| §6 Weakness #11 (TypedDict per subclass) | recommended | AC4.8 |
| §6 Weakness #12 (single-vs-multi Household) | Fix #15 | AC7.8 |
| §6 Weakness #13 (vendor-ID chars) | recommended | AC10.8 + B.3 skeleton |

---

*Spec: M7 Schema Translators — Project 007 FSI Interoperability Platform*
*Phase 2 Lighthouse Scope: 4 vendors × 8 canonical types = 11 translator pairs*
*Version 0.2.0 — post-LLMJ-v1 fix pass (target: 7.5+ on re-review)*
