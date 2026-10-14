# M7 Schema Translators — LLMJ Review (First Pass)

**Spec Version:** 0.1.0 (1,379 lines)
**Reviewer:** schema-agent (M7 specialist, acting as independent LLM Judge)
**Date:** 2026-04-25
**Playbook Step:** 2 (LLMJ First Pass)

## Weighted Score: 7.36 / 10 — CONDITIONAL GO

| # | Dimension | Weight | Score | Weighted |
|---|-----------|--------|-------|----------|
| 1 | Completeness | 25% | 8.0 | 2.00 |
| 2 | Accuracy | 20% | 6.0 | 1.20 |
| 3 | Security | 20% | 8.5 | 1.70 |
| 4 | Testability | 15% | 7.5 | 1.125 |
| 5 | Design Alignment | 10% | 6.5 | 0.65 |
| 6 | Gaps | 10% | 6.9 | 0.69 |
| **Total** | | 100% | | **7.365** |

Rounded: **7.36 / 10 → CONDITIONAL GO**. The spec is dramatically better than M3's first pass (4.8) — it is closer to M3's second pass bar (8.35). Scope is honestly defined, cost basis is addressed, the boundary story is tight. But the T1–T11 field tables reference M3 field names that don't match M3's actual `types.py`, the M6 integration point is wired to a dict shape (`req.target.source_system`) that M6 does not define, and several testability/operational gaps remain. Fix the accuracy and M6-integration bugs and it should clear 7.5+ on the re-review.

---

## 1. Completeness — 8.0/10

### Evidence
- Scope explicitly stated: 4 vendors × 8 canonical types = 11 translator pairs (Lighthouse Scope table, L34–41; R2 AC2.5–AC2.7).
- 15 requirements (R1–R15) with ~95 ACs — covers contract, coverage, models, fail-closed, cost basis, enum discipline, Household container, versioning, reconciliation note, determinism, round-trip, module boundary, public API, security, decision log.
- Explicit "OUT of scope" section (L44) deferring Order/Balance/Performance/SecurityProfile/Quote/InteractionSummary/ComplianceCheck/ComplianceAlert/AuditEntry/ResearchBrief/PaymentInstruction + Fidelity/Pershing/Bloomberg/etc. to "M7-lighthouse-2". No silent gaps.
- Cost Basis Normalization Matrix (L283–316) — both `COST_BASIS_VENDOR_MAP` (13 rows) and `COST_BASIS_DEFAULTS` (7 rows) + 4 fail-closed cases.
- Vendor Enum Mapping Matrix (L318–385) — every canonical enum field touched by Phase 2 translators, with vendor string → canonical value per vendor.
- Known Blockers & Pending SME Decisions table (L48–57) — 4 rows, honest about what's unresolved.
- 20 tasks (Task 1 – Task 20) each citing specific ACs.

### Strengths
- The scope boundary is declared cleanly. Unlike M3's first pass which tried to silently cover everything, M7 says "11 pairs, these 8 types, these 4 vendors" and pins it with `len(TRANSLATOR_REGISTRY) == 11`.
- Cost basis is treated as a first-class section, not a footnote — both vendor map and default map are tabled with rationale.
- The DECISION-LOG hook (R15 + Task 20) preserves M3's discipline.

### Weaknesses (HARSH)
1. **Steering Rule 10 coverage is hand-waved.** Rule 10 requires `account_type` on Balance, Holding, Transaction, etc. for OPA per-type compliance rules. M7 Phase 2 does NOT translate Balance (out of scope), so the compliance loop that R10 exists to serve is HALF-wired. This is a scope decision, not a defect, but the spec does not name it as a gap — it should explicitly say "OPA per-type rules for Balance are blocked on M7-lighthouse-2" in the Known Blockers table.
2. **No spec for the M7 `__init__.py` symbol ordering / registry construction order.** AC13.1 gives an `__all__` list but does not say whether the registry is built at import-time (which means a vendor module import failure takes down the whole package) or lazily. For a fail-closed library this matters — call it out.
3. **R8 VENDOR_API_VERSION window is under-specified.** AC8.6 says "Optional `MIN_VENDOR_API_VERSION` / `MAX_VENDOR_API_VERSION`" — but says nothing about what the compatibility semantics are for SF FSC (e.g., `v59.0` vs `v60.0`). Is semver comparison used? Lexicographic? The spec is silent. Either commit to "no compatibility window in Phase 2 — bumping the vendor API bumps translator MAJOR" or define it. As written, AC8.6 is not implementable.
4. **No explicit coverage for null/missing PII fields.** The spec says "PII passthrough only" (R14.5) but does not cover "what happens when the vendor omits the PII field entirely" — does the translator preserve None, default to empty string, or error? This is not specified and tests can't pin it.
5. **No story for vendor IDs that contain URL-hostile characters.** The spec does `uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")` but SF FSC IDs are 18-char alphanumeric so that's safe. However Orion `clientId`, Schwab `accountNumber`, eMoney `planId` — the spec does not specify the character set constraint. A vendor ID containing `:` would collide namespace keys. Add a canonicalization rule or document the assumption.
6. **R7 Household multi-vendor has no deterministic merge-order rule.** `to_canonical_household_multi(payloads: dict[str, dict])` — when both SF FSC and Orion claim the same `client_ref` with different `role`, who wins on the canonical `members[]`? AC7.5 says "member-list diff" produces a discrepancy string, but does the canonical `members` list include ONE record or TWO? Silent.
7. **No `fields_unchanged` in ReconciliationNote.** R9.1 tracks `fields_dropped` and `fields_derived`. For audit you also want "fields_pass_through_unchanged" (the happy-path majority). Not strictly required but its absence makes note interpretation asymmetric.
8. **Missing R on Decimal vs float.** M6's §R12 AC-R12-5 treats `Decimal` as first-class via canonical_json. M3's types use `float` everywhere for money (`market_value: float`, `cost_basis: float`). M7 inherits this defect — but the spec should at least acknowledge "M3 uses `float` which risks IEEE-754 cent drift; canonical model decision is inherited and not challenged here." Silent inheritance of a known defect is a completeness miss.
9. **No migration / contract-freeze note for M8 consumer.** The spec lists M8 as a consumer (line 10) but only elaborates M6 integration. What does M8 do with a ReconciliationNote? Is M8 even allowed to call `translate_to_canonical` directly or does it go through M6? Silent.
10. **R15 `DECISION-LOG` location fork.** R15 says `src/m7_translators/DECISION-LOG.md`, but the project convention (M3) put DECISION-LOG at `schemas/canonical/DECISION-LOG.md`. Steering says M7 decisions go in its own log — OK, but "M3 DECISION-LOG has pending items that affect M7 (Holding.accrued_interest)" — does M7's DECISION-LOG cross-reference them? The spec mentions them in Known Blockers but doesn't bind that table to the DECISION-LOG file.

### What would make it a 10
- Name the M7-lighthouse-2 items that M7 Phase 2 forces other modules to defer (OPA per-Balance rules, Order flow, Performance TWR).
- Add explicit "null-PII" and "vendor-ID-hostile-character" handling rules under R14 or a new R16.
- Add a Household merge-order invariant to R7 (e.g., "SF FSC role wins when ambiguous; discrepancy always flagged").

---


## 2. Accuracy — 6.0/10

This is the weakest dimension. Several T1–T11 field mappings reference M3 field names or type shapes that don't match `src/m3_schema_registry/types.py`. A translator cannot be correct against an imagined canonical model.

### Evidence
- Verified M3 `types.py` at `src/m3_schema_registry/types.py` (1,183 lines).
- Verified `CANONICAL_TYPES` keys in `__init__.py` — 18 entries, string names match M7 registry tuples (`"Client"`, `"Household"`, `"TaxLot"`, `"Holding"`, `"Transaction"`, `"PlanSummary"`, `"Goal"`). Good.
- Verified M5 `__init__.py` — `Archetype`, `Jurisdiction`, `RegistrationType` all exported. M7's claim in R12.4 is correct.
- Verified `CostBasisMethod` enum — values `specific_lot`, `average_cost`, `fifo`, `lifo`, `hifo` — match M7 spec L112 exactly. Good.

### Strengths
- `CANONICAL_TYPES` string keys match the keys M7 uses in TRANSLATOR_REGISTRY.
- `CostBasisMethod` enum values match M7's mapping tables.
- M5 exports exactly the three enums M7 claims to import.
- Vendor API versions cited (SF FSC `v59.0`, Orion `v2.0`, eMoney `v2`, Schwab `MarketDataAPI 1.0`) are plausible public-facing version strings; none look invented.

### Weaknesses (HARSH)

1. **T1 Client table invents `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS` namespaces.** M3 `Client.firm_id: UUID` (REQUIRED) and `Client.accounts: list[UUID]`. M7 T1 uses `uuid5(FIRM_NS, value)` and `uuid5(ACCOUNT_NS, ...)` but AC10.5 enumerates only 7 namespaces (`CLIENT_NS, HOUSEHOLD_NS, HOLDING_NS, TAXLOT_NS, TRANSACTION_NS, GOAL_NS, PLAN_NS`). Translator code would raise `NameError`. At least 3 namespaces missing.

2. **T1 `display_name` has no empty-string guard.** M3 requires `display_name: str` with `min_length=1, max_length=255`. Empty `Account.Name` → Pydantic ValidationError, not `TranslationError`. Wrap with `MissingRequiredField`.

3. **T4/T8 (Orion & Schwab → Holding) type mismatch: `UUID` vs `str` on `*_ref` fields.** M3 `Holding.account_ref: str` (REQUIRED), `Holding.client_ref: Optional[str]`. M7 T4/T8 assign via `uuid5(...)` which returns `UUID`. Pydantic v2 MAY coerce (non-strict default) or MAY NOT. Pattern repeats across T4, T5, T7, T8, T9, T10, T11 — 6+ distinct places. Resolve: either explicit `str(UUID(...))` cast or change M3 to `UUID` uniformly.

4. **T5 collapses `source_id` and `transaction_id` into one mapping cell.** M3 defines them as TWO SEPARATE fields: `transaction_id: UUID` (primary key) and `source_id: str` (custodian ID). M7 T5 says `Transaction.transactionId | source_id / transaction_id | uuid5(TRANSACTION_NS, ...)`. Assigning a UUID to `source_id: str` is wrong.

5. **T5 does not map `Transaction.trace_id`.** Optional in M3, so not a hard defect, but clarify: does M7 pass `trace_id` through from vendor payload, or does M6 attach it? Silent.

6. **T5 reverse direction for `order_ref` is unspecified.** Forward sets `order_ref=null` (Orion doesn't track 007 orders). Reverse — what if canonical `order_ref` is set? Dropped? Preserved in `customAttributes`? Silent.

7. **T2 (SF FSC → Household) claims `FinServ__Household__c.FinServ__AccountIds__c → accounts[]`.** SF FSC does NOT have a stock scalar-with-IDs field — account linkage is via junction `FinServ__FinancialAccount__c` with a Household lookup. **Not confirmed against SF FSC v59.0.** If wrong, T2 must be rewritten.

8. **T3 (SF FSC → Goal) references `FinServ__FinancialGoal__c.FinServ__HouseholdId__c`.** SF FSC v59.0 typically exposes `FinServ__Household__c` as a lookup, not an ID picklist. Verify against vendor docs.

9. **T1 claims `archetype` "validates `{mass_affluent, hnw, uhnw}`".** M3 `Client.archetype: Optional[str]` has NO Pydantic validator. Either add the validator to M3 (outside M7's directory boundary) or remove the validation claim.

10. **`AccountType` three-way mismatch.** Steering Rule 10 lists `individual`, `joint_tos`, `joint_tic`, `pension`, `profit_sharing`, `457b`. M3 actually defines: `TAXABLE, TRADITIONAL_IRA, ROTH_IRA, K401, B403, B457 (value "457"), SEP_IRA, SIMPLE_IRA, TRUST_REVOCABLE, TRUST_IRREVOCABLE, CUSTODIAL_UTMA, CUSTODIAL_UGMA, ERISA_PENSION, ERISA_PROFIT_SHARING, PLAN_529, HSA`. M7 tables collapse `INDIVIDUAL`/`JOINT_TOS` into `taxable` — which is CORRECT against M3 but contradicts steering. Spec must explicitly call out that steering Rule 10 uses an outdated draft and M3 is source of truth.

11. **M3 `AccountType.B457` value is `"457"`, not `"457b"`.** M7 maps no 457 vendor string in any T-table. If Orion or Schwab returns a 457 account, `UnknownEnumValue` fires. Add row or document as Phase 2 gap.

12. **T9 `TaxLot.holding_ref` type mismatch.** M3 `TaxLot.holding_ref: str` (REQUIRED). M7 `uuid5(HOLDING_NS, ...)` returns UUID. Same issue as #3.

13. **T7 `probability_of_success` no validation guard.** M3 `probability_of_success: float = Field(ge=0, le=100)` (REQUIRED). Out-of-range eMoney value → Pydantic ValidationError, not `TranslationError`. Wrap with `MissingRequiredField`/`TypeCoercionError`.

14. **T9 and Task 12 contradict on `source_cost_basis_method` for vendor-silent case.** T9 says "direct vendor string". Task 12 says "null when vendor was silent". Pick one — M3 allows null (`Optional[str]`) so null-when-silent is correct; update T9.

15. **T6 (Orion → Household) and T10 (Orion → TaxLot) are three sentences each, "analogous to".** Not specifiable — reviewer cannot verify Orion field names, engineer cannot build without inventing them. Fill explicit field tables.

16. **Orion vendor API version `v2.0`.** Orion Connect REST has historically versioned as `v1`/`v1.1`. `v2.0` may be current private/beta endpoint. Pin to Orion developer-portal URL in DECISION-LOG.

### What would make it a 10
- Make every T-table Derivation cell a valid Python expression against real M3 Pydantic types. Resolve all `UUID` vs `str` mismatches.
- Enumerate every UUID namespace used in T1–T11 in AC10.5 (add at minimum `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS`).
- Fill T6 and T10 with explicit field tables.
- Add "Verified against M3 types.py as of {date}" checklist per translator pair.

---

## 3. Security — 8.5/10

### Evidence
- R14 Security Invariants (L227–244) with 7 ACs — credentials grep, no PII in exceptions, no `logging` import, forbidden imports grep, PII passthrough only, reconciliation-note scan, JSON-serializable details.
- R10 Idempotency (L161–170) forbids `uuid4`, `datetime.now`, `time.time`, `random.*`.
- R12 Module Boundary (L198–209) — forbidden module prefixes and vendor SDKs (`simple_salesforce`, `orion_sdk`, `schwab_sdk`, `emoney_sdk`), M5 imports limited to enums.
- R9.5/R9.6 `ReconciliationNote` PII-free scan with `RECONCILIATION_NOTE_SAFE_FIELDS` allow-list.
- Task 2 writes negative tests FIRST (L1089–1102).

### Strengths
- Negative-tests-first discipline pinned to AC-IDs.
- Forbidden import list covers vendor SDKs — prevents hidden credential paths.
- PII passthrough is correct: M4 filters AFTER translation. Verified against M6 spec §0.5 stages 7 and 8 — both fire after Stage 6 `m6.translate`.
- `RECONCILIATION_NOTE_SAFE_FIELDS` allow-list is deny-by-default — the right pattern.

### Weaknesses (HARSH)
1. **`warnings` module not forbidden.** `warnings.warn()` leaks to stderr. Add to forbidden list or accept with PII-free contract.
2. **AC14.2 `valid_values` in exceptions could in theory contain PII.** Unlikely for enum values like `PersonAccount` / `SpecificLot`, but add test: `valid_values` is always a subset of a static, documented enum literal set — not vendor-runtime strings.
3. **`TranslationError.details` "JSON-serializable, PII-free" is weaker than the PII-free claim alone.** `{"email_length": 25}` is JSON-serializable and implicitly PII-leaky. Task 19 scans `str(note)` but not exception `details`. Extend.
4. **No credentials / PII scan on fixtures.** Task 2/19 grep `src/` but not `tests/schema-reconciliation/fixtures/`. Synthetic fixtures drift. Add pre-commit fixture scan.
5. **AC14.4 forbidden list not exhaustive.** Forbids `pathlib.Path.open` but not `io.open`, `os.open`, `tempfile.*`. Commit to stdlib allow-list or widen.
6. **`CostBasisUnmappable.details["vendor_value"]="Other"` technically violates "no raw vendor field values".** Cost basis values are enum-constrained and PII-impossible IN THEORY, but defense-in-depth says sanitize or add an explicit invariant test.
7. **AC12.4 is textual guidance, not AST-enforced.** M5 exports many enums beyond the 3 allow-listed (`Topology`, `Runtime`, `SuitabilityStandard`, `PrincipalReviewMode`, `TimeoutAction`, etc.). Accidental import of any — or `EnterpriseConfig`/`load_enterprise_config` — must fail the test. Make AC12.4 a positive AST-level allow-list.
8. **PII with whitespace-only values not specified.** `Contact.Email = "   "` — passes through? Trimmed? Error? Silent.

### What would make it a 10
- Turn AC12.4 into positive AST-enforced allow-list.
- Extend PII-free scan to cover exception `details` and fixture files.
- Add `warnings` and `tempfile` to forbidden imports.
- Document/test the cost-basis-values-are-PII-impossible invariant.

---

## 4. Testability — 7.5/10

### Evidence
- R11 Round-Trip (L177–185) — ≥3 fixtures per pair, "double-trip" equality, `LOSSY_FIELDS` documented.
- R10 Idempotency (L161–170) — Hypothesis property tests ≥100 cases per translator.
- Every task cites AC IDs (L1079–1328).
- Task 16 enum-mapping meta-test discovers translators via registry.
- Task 18 idempotency property tests.
- Task 19 PII-free scan.

### Strengths
- Tests AC-indexed — M3-second-pass discipline.
- Round-trip "double-trip" formula `to_canonical(x) == to_canonical(from_canonical(to_canonical(x)))` mathematically sound.
- Fixtures mandated synthetic-only (AC11.2).

### Weaknesses (HARSH)
1. **Hypothesis on Pydantic v2 `extra="forbid"` vendor models rejects most random dicts.** Spec does not specify HOW payloads are generated — `from_type(VendorModel)` or hand-written `@composite`? 11 pairs × 3 shapes = 33 hand-written strategies if hand-written. Call out the work in Task 18.
2. **AC1.3 "byte-identical on BOTH elements" requires stable list ordering in `ReconciliationNote.fields_dropped` / `fields_derived`.** Not asserted — if built from set iteration, order drifts. Pin sorting.
3. **AC11.3 "Divergence raises `RoundTripDivergence`"** — clarify whether equality compares canonical only, or note+canonical.
4. **AC11.5 enforces `cost_basis_method != None` via M3 validator.** Good. But `source_cost_basis_method` — the distinction between vendor-silent-defaulted and vendor-explicit — is not asserted. Add.
5. **AC6.5 meta-test partially circular.** "Every vendor string in ENUM_MAPPINGS produces a valid canonical enum" — the vendor string IS the key. Real test: every vendor value came from a pinned vendor-docs artifact. Out of Phase 2 scope but noting.
6. **Discrepancy-string format not pinned in AC7.5.** Test breaks on minor refactor. Pin format explicitly.
7. **No fixture for L314 row 3 "Schwab UK `SpecificLot` ambiguous — PENDING SME".** Add `@pytest.mark.xfail(reason="pending SME")` skeleton so we cannot forget.
8. **AC10.4 `≥100 cases per translator × 11 = 1,100 cases`.** No CI time bound. Naïve Hypothesis on complex Pydantic model can take minutes per test. Add `@settings(max_examples=100, deadline=500)` or "test_m7_idempotency <2min total".
9. **No concurrency smoke test.** AC1.7 says sync functions, M6 wraps in `asyncio.to_thread`. Accidental mutation of `ENUM_MAPPINGS` — multi-thread stress would catch it. Add.
10. **Double-trip undefined for multi-vendor Household.** `to_canonical_household_multi({"salesforce_fsc": p1, "orion": p2})` → single canonical. `from_canonical_household(canonical, vendor="salesforce_fsc")` → SF only. Subsequent `to_canonical_household_multi({"salesforce_fsc": that_sf})` loses Orion. AC11.3 applies only to single-vendor. Say it.
11. **AC8.5 "top entry of CHANGELOG matches SCHEMA_VERSION"** fragile. Mandate Keep-A-Changelog format or regex on anchored `## [{SCHEMA_VERSION}] — {date}`.

### What would make it a 10
- Spec Hypothesis strategy approach with one example.
- Pin discrepancy-string format.
- Add concurrency smoke test.
- Add CI time bounds.
- Mark AC11.3 as single-vendor only; multi-vendor has AC7.7.

---

## 5. Design Alignment — 6.5/10

Second-weakest. M7's Integration Point (L1002–1022) binds to M6 request shape (`req.target.source_system`, `req.target.canonical_type`) that M6 does NOT define.

### Evidence
- ARCH-09 table: M7 is ADAPT, Python, Pydantic v2, 400-800 lines each. M7 spec claims ~3,000 lines total (11 × ~270 avg = 2,970). Matches.
- ARCH-09 dependency matrix: `M7 → M3` only. M7 spec §Module Boundary matches and extends to M5(enums).
- Build order: Phase 2 = M7 + M11-REST + M9 + M8 + M12. M7 spec in Phase 2. Consistent.
- Part 10 of consolidated design + Phase 2 plan: "Salesforce, Orion, eMoney, Schwab". M7 spec matches exactly.
- IMPL-06 Blocker 3 cost basis. M7 R5 ACs match.
- M6 spec §R11: `Translators: pass-through → M7 vendor→canonical call`. High-level consistent.

### Strengths
- Phase 2 scope (4 vendors × 8 types) matches Part 10 and ARCH-09.
- Dependency matrix honored: M7 → M3 + M5(enums). No creep.
- Cost basis aligned with IMPL-06 Blocker 3.

### Weaknesses (HARSH)

1. **CRITICAL: M6's `GatewayRequest.target` is `Mapping[str, Any]` (M6 spec §R1.1) with default `{}`.** M7 spec (L1008–1011) accesses `req.target.source_system` and `req.target.canonical_type` as attributes. Correct access is `req.target["source_system"]`. But more critically, **M6 does NOT guarantee those keys exist in `target`.** M6's `target` is opaque (passed to `PolicyInput.target`). **M7 is inventing a dict schema M6 has not ratified.** Fix: spec M6 to guarantee those keys (M6 spec amendment), or change M7 dispatcher to accept explicit parameters, not reach into `target`.

2. **M6 spec line 148 Stage 6 payload is hardcoded Phase 1: `{"pass_through": true}`.** M7 Phase 2 sketch changes this to `{"reconciliation_note": ..., "pass_through": False}`. M7 is spec'ing M6's Phase 2 payload on M6's behalf. Escalate to M6 owner.

3. **M11 listed as consumer (L10) — bypasses M6 trust pipeline.** ARCH-09 shows `M11 → M7 = *`, so structurally OK. But if M11 calls M7 before returning to M6, `ReconciliationNote` never hits M10 audit. **Audit trail is lost on M11→M7 path.** Either remove M11 from consumers, or document the dual-caller audit contract.

4. **M8 listed as consumer (L10) but ARCH-09 dependency matrix shows `M8 → M7` is NOT marked.** M8 calls M2, M5, M6, M10 — not M7. **Invented consumer relationship.** Fix ARCH-09 or remove M8 from consumer list.

5. **Directory naming drift.** M3 = `src/m3_schema_registry/`, M5 = `src/m5_config_loader/`, M6 = `src/m6_mcp_gateway/`. Pattern: `m{N}_{name}_{suffix}`. M7 puts source at `src/m7_translators/` — drops "schema". L824 acknowledges but doesn't justify. Violates convention.

6. **Package name vs import name inconsistency.** `pyproject.toml` `name = "m7-schema-translators"` → import `m7_schema_translators`. Spec uses `from m7_translators import`. Two names. Pick one.

7. **Schwab API version `"MarketDataAPI 1.0"` nonstandard.** Schwab uses `/v1` URL versioning. Pin to the actual URL path version.

8. **Line estimate not load-balanced.** eMoney (1 pair) ≈ 200-400 lines. Orion (4 pairs) ≈ 1,600-3,200. Schwab (3 pairs + `$`-strip) ≈ 1,400-2,400. "~3,000 total" is plausible but per-translator column needs revision.

9. **No explicit ARCH-07 pydantic pin alignment.** Spec says "Pydantic v2" but doesn't cite exact pin. M3's actual requirement must be matched to avoid integration drift.

10. **Schwab SFTP daily-file reconciliation out of Phase 2.** Part 10 mentions daily-file reconciliation; only Schwab REST is in M7 Phase 2. Call out in Known Blockers.

### What would make it a 10
- Fix M6 integration contract: spec M6 `target` keys or change M7 dispatcher signature.
- Reconcile M8 and M11 consumers against ARCH-09.
- Fix package/import/directory naming consistency.
- Pin Schwab version to URL path.

---

## 6. Gaps — 6.9/10

### Evidence
- Known Blockers table (L48–57) covers 4 pending items.
- R15 DECISION-LOG maintenance.
- Task 2 + Task 19 front-load negative tests.

### Strengths
- Honest about PENDING SME items.
- Fail-closed cost basis cases enumerated.
- Idempotency guarantees enable WORM replay.

### Weaknesses (HARSH)

1. **No observability story.** If `translate_to_canonical` raises `UnknownEnumValue(vendor_value="RARE")`, how does production know WHICH translator, HOW OFTEN, UNDER WHAT LOAD? M6 logs reason_code + field_path but cannot log the enum value without M7 surfacing it via `details`. Spec does not mandate M6 propagate `details` to M10. **Cross-module observability contract missing.**

2. **No concurrency guarantees around `ENUM_MAPPINGS` / `TRANSLATOR_REGISTRY`.** `dict[...]` not `MappingProxyType` / frozen. Accidental `ENUM_MAPPINGS["client_type"]["NewValue"] = "..."` at runtime breaks idempotency silently. 3-line fix.

3. **No translator-version-mismatch detection.** If M6 Phase-2 expects v0.2.0 but v0.1.0 installed, does M6 discover? AC13.5 exposes `SCHEMA_VERSION` but no healthcheck/compat API. Add `m7_translators.compatible_with(min_version: str) -> bool`.

4. **`len(TRANSLATOR_REGISTRY) == 11` hardcoded in AC2.5.** Phase 3 Fidelity breaks. Change to `>= 11` with "every entry has a task" invariant.

5. **No round-trip test for `ReconciliationNote` itself.** R11 compares canonical only. Note ordering stability not asserted cross-pass.

6. **`from_canonical` under-specified for most pairs.** Forward tables detailed; reverse is assumed inverse. Lossy fields, vendor fields derived from combined canonical fields, canonical-has-more-fields — reverse rules not written. Every T-table needs reverse-lossy section.

7. **Partial-data handling.** Orion Position with NO `taxLots[]` → `tax_lots=[]` (M3 default)? `MissingRequiredField`? Spec silent.

8. **Numeric-validator edges.** Schwab `costBasis` `@field_validator(mode="before")` strips `$` and commas. `"12345"` (no prefix)? Passes? Silent.

9. **SF FSC Person Account vs Business Account divergence.** SF FSC has two RecordTypes: `PersonAccount` (Account+Contact merged) and `Business Account` (separate Contact). Business Account has NO Contact — first/last/email MUST be null. Translator must branch on `client_type == "entity"`. Task 3 doesn't cover this.

10. **No deprecation story for SCHEMA_VERSION bumps.** Is 0.1.0 supported in parallel with 0.2.0? Hard cutoff? Needed for simultaneous M6/M11/M8 consumption. Silent.

11. **`TranslationError.details: dict` not TypedDict per subclass.** Tests can't assert structurally. Tighten with TypedDict or frozen dataclass per subclass.

12. **Single-vendor vs multi-vendor Household reconciliation behavior.** Single-vendor `to_canonical_household_*` → `reconciliation=None`. Multi-vendor populates. Semantically OK but downstream confused. Document explicitly.

13. **Vendor-ID hostile-character handling.** `uuid5(CLIENT_NS, f"salesforce_fsc:{Account.Id}")` — SF FSC IDs are 18-char alphanumeric (safe). Orion/Schwab/eMoney ID character sets not declared. A vendor ID with `:` would collide namespace keys. Add constraint (e.g., `[a-zA-Z0-9._-]+` or URL-encode).

### What would make it a 10
- Observability section: `details → M6 → M10` contract.
- `MappingProxyType` for registry + enum mappings.
- `compatible_with(min_version)` API.
- Person Account vs Business Account branching in Task 3.
- Vendor-ID character-set constraint in R10.
- TypedDict per `TranslationError` subclass.

---

## Required Fixes (must address for GO verdict)

**Accuracy blockers:**

1. Fix `UUID` vs `str` mismatch across T4, T5, T7, T8, T9, T10, T11. Either `str(UUID(...))` or change M3 uniformly.
2. Fix T5 collapsing `source_id` and `transaction_id`. Two separate fields, two separate derivations.
3. Enumerate missing UUID namespaces in AC10.5 — at minimum `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS`.
4. Fill T6 (Orion → Household) and T10 (Orion → TaxLot) with explicit field tables.
5. Verify SF FSC field names `FinServ__AccountIds__c`, `FinServ__HouseholdId__c`, `FinServ__ClientArchetype__c` against SF FSC v59.0 docs. Rewrite if absent.
6. Remove T1 validation claim `{mass_affluent, hnw, uhnw}` unless M3 adds validator.
7. Document `AccountType` mismatch between steering Rule 10 and M3's actual enum (M3 is source of truth).
8. Reconcile T9/Task 12 contradiction on `source_cost_basis_method` for vendor-silent case — null, not "direct vendor string".

**Design-alignment blockers:**

9. Fix M6 Integration Point sketch. Either change M7 dispatcher signature (explicit params, no `req.target.*`), or escalate to M6 spec for `target` keys amendment.
10. Reconcile M8 and M11 consumers against ARCH-09 dependency matrix.
11. Fix package name / import name / directory name inconsistency.

**Completeness / testability blockers:**

12. Make AC12.4 a positive AST-enforced allow-list.
13. Specify Hypothesis strategy approach in Task 18 (with one example).
14. Pin exact discrepancy-string format in AC7.5.
15. Document single-vendor vs multi-vendor Household reconciliation behavior.
16. Extend PII-free scan (Task 19) to cover `TranslationError.details` AND fixtures.
17. Add reverse-lossy section to every T-table.

## Recommended Fixes (nice-to-have)

- `types.MappingProxyType` for `ENUM_MAPPINGS` and `TRANSLATOR_REGISTRY`.
- `m7_translators.compatible_with(min_version: str) -> bool`.
- Change `len(TRANSLATOR_REGISTRY) == 11` to `>= 11`.
- SF FSC Person Account vs Business Account branching in Task 3.
- Concurrency smoke test for dispatcher.
- Add `warnings` and `tempfile` to forbidden imports.
- Document observability handoff contract.
- TypedDict per `TranslationError` subclass.
- Pin Schwab API version to URL path.
- Align pydantic version pin with M3's actual requirement.
- Add `@pytest.mark.xfail(reason="pending SME")` skeleton for Schwab UK case.
- CI time bounds on Hypothesis tasks.

## Verdict

**Weighted score 7.36 / 10 → CONDITIONAL GO.**

This spec is substantially more disciplined than M3's first pass (4.8). Scope is honestly defined (11 translator pairs, pinned). Cost basis is treated as a first-class section with both vendor map and defaults. Module boundaries are AST-scannable. Household container pattern preserved with `grouping_type` CONSTS. Fail-closed is default. Every task cites AC IDs. Task 2's negative-tests-first alone raises the floor.

The accuracy dimension drags the score down. T1–T11 field tables do not match M3's actual `types.py` in 10+ places: `UUID` vs `str` on `*_ref` fields in 6+ translators, `source_id`/`transaction_id` collapsed in T5, 3+ UUID namespaces used but undeclared in AC10.5, T6 and T10 stubbed as "analogous to" with no tables, several SF FSC field names unverified, a non-existent M3 validator claimed in T1. These are spec-hygiene defects from not running the tables against M3's real Pydantic models. A round of "read M3, update tables" closes most of them.

The design-alignment issue is narrower but sharper: M7 reaches into `req.target.source_system` when M6 §R1 defines `target` as opaque `Mapping[str, Any]`. This is the single most important fix — a cross-module contract claim M6 has not ratified. Either M6 amends `target` to pin the keys, or M7's dispatcher accepts explicit parameters. Additionally, M8 and M11 as consumers contradict ARCH-09's dependency matrix (M8) and bypass audit trail (M11).

Security, Testability, and Completeness all score above 7.5 individually. Address the 17 Required Fixes, re-verify against `src/m3_schema_registry/types.py` line-by-line, escalate the `target` dict schema question to M6, then re-review. Target 7.5+ on re-review for a GO verdict.

Proceed to **Fix** (playbook step 3), then re-review.
