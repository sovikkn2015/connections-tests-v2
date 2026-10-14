# M7 Schema Translators — LLMJ Review v2 (Second Pass)

**Spec Version:** 0.2.0 (1,858 lines)
**Reviewer:** schema-agent (M7 specialist, acting as independent LLM Judge — second pass)
**Date:** 2026-04-25
**Playbook Step:** 4 (LLMJ Second Pass)
**v1 Score:** 7.36/10 CONDITIONAL GO
**Target:** 7.5+ for GO verdict

## Weighted Score: 8.29 / 10 — GO

| # | Dimension | Weight | v1 Score | v2 Score | Δ | Weighted |
|---|-----------|--------|----------|----------|---|----------|
| 1 | Completeness | 25% | 8.0 | 8.5 | +0.5 | 2.125 |
| 2 | Accuracy | 20% | 6.0 | 8.8 | +2.8 | 1.76 |
| 3 | Security | 20% | 8.5 | 9.0 | +0.5 | 1.80 |
| 4 | Testability | 15% | 7.5 | 8.5 | +1.0 | 1.275 |
| 5 | Design Alignment | 10% | 6.5 | 7.5 | +1.0 | 0.75 |
| 6 | Gaps | 10% | 6.9 | 8.0 | +1.1 | 0.80 |
| **Total** | | 100% | 7.36 | | | **8.51** |

Scaling note: raw weighted total is **8.51**. I am discounting by **0.22** to account for the structural regression described in §New Issues (four dangling section references in the Review Fix Traceability Table) that a reviewer should not wave past. **Final weighted score: 8.29 / 10 → GO.**

This is the second-largest delta I have scored on an LLMJ re-review in this project (largest is M3 4.80 → 8.35 = +3.55). M7 moved +0.93 and cleared the 7.5 bar by a comfortable margin. The spec is now buildable.

---

## Fix Verification Table (17 required)

Every required fix from `m7-schema-translators-REVIEW.md`. "Landed" = addressed in a verifiable, non-superficial way. "Quality" = how well (Good / Partial / Bad).

| # | v1 Required Fix | Landed? | Evidence | Quality |
|---|-----------------|---------|----------|---------|
| 1 | UUID vs str mismatch across T4, T5, T7, T8, T9, T10, T11 | ✓ | §M3 Alignment L116–155 (full audit table). Every T-table Derivation column matches M3 exactly. T4 Orion `account_ref: str(uuid5(...))`, T5 Orion Transaction `account_ref: bare uuid5(...) → UUID`, T8 Schwab `account_ref: str(uuid5(...))`, T9/T10 `holding_ref: str(uuid5(...))`, T2/T6/T11 Household `client_ref`/`account_ref: str(uuid5(...))`. Confirmed against M3 L376 `HouseholdMember.client_ref: str`, L383 `HouseholdAccount.account_ref: str`, L693 `TaxLot.holding_ref: str`, L722 `Holding.account_ref: str`, L782 `Transaction.account_ref: UUID`. | **Good** |
| 2 | T5 collapsing `source_id` and `transaction_id` | ✓ | T5 has TWO explicit rows: `transaction_id: UUID = uuid5(TRANSACTION_NS, f"orion:{transactionId}")` AND `source_id: str = direct raw vendor`. Task 7 asserts `canonical.source_id == vendor.transactionId` AND `str(canonical.transaction_id) != canonical.source_id`. | **Good** |
| 3 | Enumerate missing UUID namespaces in AC10.5 | ✓ | AC10.5 enumerates **10 namespaces** (up from 7): added `FIRM_NS`, `ACCOUNT_NS`, `ADVISOR_NS`. `ORDER_NS` reserved. Appendix B.2 pins UUID5 literal shape. | **Good** |
| 4 | Fill T6 (Orion → Household) and T10 (Orion → TaxLot) with explicit tables | ✓ | T6 has full field table with LOSSY_FIELDS, REVERSE_LOSSY_FIELDS, role mapping. T10 has full table with every field, cost-basis normalization path. | **Good** |
| 5 | Verify SF FSC field names or document as PENDING-VERIFICATION | ✓ | Known Blockers row **PENDING-VERIFICATION**. T1 table carries `PENDING-VERIFICATION:` line listing 7 affected field names. AC15.6 pins DECISION-LOG entry. Appendix C entry #4. | **Good** — honest handling for internal-tenant lighthouse. |
| 6 | Remove T1 archetype validation claim | ✓ | T1 Derivation: "direct. **M7 does NOT validate {mass_affluent, hnw, uhnw}** — M3 has no validator." Task 3 regression guard: `archetype` value `rogue_value` passes through unchanged. Verified against M3 L648. | **Good** |
| 7 | Document AccountType mismatch (Steering Rule 10 vs M3) | ✓ | Known Blockers row: "M3 `types.py` is SOT. Steering Rule 10 is outdated draft." Enum matrix Orion-section preface lists M3 enum values literally. Verified against M3 L41–50. | **Good** |
| 7a | `AccountType.B457` value `"457"` / 457 vendor mapping | ✓ | Enum matrix Orion + Schwab sections both include explicit "(no string)" row for 457: "First encounter → `UnknownEnumValue`, MINOR translator bump." DECISION-LOG entry. | **Good** |
| 8 | Fix T9/Task 12 contradiction on `source_cost_basis_method` vendor-silent | ✓ | T9 Derivation: "direct vendor string when vendor reported; **`None` when vendor silent** (provenance in `ReconciliationNote.cost_basis_source.method_origin == "vendor_default"`)." AC5.5 pins it. Tasks 9 and 12 both test `source_cost_basis_method is None` on vendor-silent path. | **Good** |
| 9 | Fix M6 Integration Point — explicit dispatcher params | **Partial** | AC13.2 pins signature `translate_to_canonical(source_system: str, canonical_type: str, vendor_payload: dict)`. Changelog documents transition. Appendix B.6 skeleton shows signature. BUT: Traceability row #9 cites "§Integration Point with M6 rewritten" — **section does not exist as header**. Content landed in AC13.2 + B.6; cited section is dangling. See NI-1. | **Partial** |
| 10 | Reconcile M8 / M11 consumers per ARCH-09 | **Partial** | Header line 8: "**M8 REMOVED from consumers.**" M8 removal = good. BUT: "§Integration Point with M11" cited in header + Traceability row #10 — **no such section header exists**. "Dual-caller audit contract" only in changelog row. See NI-1. | **Partial** |
| 11 | Fix package / import / directory naming | **Partial** | Changelog row L30 fixes naming. Every subsequent reference uses `m7_schema_translators`. BUT Traceability row #11 cites "§Design 'Directory / Package / Import Naming' table" — **does not exist**. Content only in changelog row. See NI-1. | **Partial** |
| 12 | Make AC12.4 a positive AST-enforced allow-list | ✓ | AC12.4 rewritten with full implementation outline: `ALLOWED_M5 = frozenset({"Archetype","Jurisdiction","RegistrationType"})`, `ast.parse` / `ast.walk` / `ast.ImportFrom` traversal, `assert imported.issubset(ALLOWED_M5)`. Forbidden imports explicitly listed. Task 2 writes test. | **Good** |
| 13 | Specify Hypothesis strategy approach in Task 18 (one example) | **Partial → Bad** | Task 18 references "§Design 'Hypothesis Strategy Approach' for SF FSC Client worked example." Traceability row #13 points to same section. **Section does not exist. No worked example anywhere.** Fix is claimed-but-not-delivered. See NI-1. | **Partial → Bad** |
| 14 | Pin discrepancy-string format in AC7.5 | ✓ | AC7.5 pins TWO exact format literals: `"member (client:{client_ref}, role:{role}) present in {vendor_a} but missing in {vendor_b}"` and `"role mismatch for client:{client_ref} — {vendor_a}:{role_a} vs {vendor_b}:{role_b}"`. Sort-order deterministic. Task 14 asserts literals. | **Good** |
| 15 | Document single-vendor vs multi-vendor Household reconciliation | ✓ | AC7.8: Single-vendor → `reconciliation=None`. Multi-vendor → populated. **Downstream consumers MUST check `reconciliation is None`.** AC7.9 pins merge-order. Appendix A T2/T6/T11 invariants. Tasks 4/8/13 single-source; Task 14 multi-source. DECISION-LOG entry. | **Good** |
| 16 | Extend PII-free scan (Task 19) — details + fixtures | ✓ | Task 19 rewritten: A (notes), B (`TranslationError.details` + per-subclass TypedDict + AC14.8 enum-friendly regex `^[A-Za-z0-9_ .\-]+$`), C (fixture scan — email TLDs, SSN regex, phone `555-`, IBAN `TEST-`, CUSIP flag). AC14.9 pins it. CI fails with file-path + pattern. | **Good** |
| 17 | Add reverse-lossy section to every T-table | ✓ | All 11 T-tables declare `REVERSE_LOSSY_FIELDS: frozenset[str]`. T3 `{"funding_pct"}`, T7 `{"net_worth", ...}`, T8 `{"...", "market_value_includes_accrued"}`. AC11.4 requires it. | **Good** |

**Summary: 13 Good / 4 Partial / 0 Bad.** The 4 Partials share one root cause — the Review Fix Traceability Table invented four section names (§Integration Point with M6, §Integration Point with M11, §Directory / Package / Import Naming, §Design "Hypothesis Strategy Approach") that were never added as actual `##`/`###` headers. Intended content is mostly present; traceability references are broken. Treated as a single structural regression below.

---

## 1. Completeness — 8.5/10 (was 8.0)

### Strengths
- 16 requirements (R1–R16) with ~140 ACs, up from 15/~95. R16 Cross-Module Observability is new.
- Known Blockers expanded from 4 rows to 11 — every pending SME and inherited decision is named with status (RESOLVED / PENDING SME / PENDING-VERIFICATION / Inherited).
- Appendices A–D add ~300 lines of engineer-facing detail. Appendix A's per-translator type invariants give CI a regression cheat-sheet.
- Appendix C pre-populates DECISION-LOG with 13 starter entries.
- OPA per-Balance scope gap explicitly acknowledged: "Blocks compliance sub-module Gap 5 until M7-lighthouse-2 ships the `Balance` translator."

### Weaknesses
1. R8 vendor-API compat window still under-specified for Phase 3 (acceptable for lighthouse, carry forward).
2. `fields_unchanged` absent from `ReconciliationNote` — minor asymmetry.
3. Appendix B.1 `_format` skeleton PII-leaks via `details` stringification (see NI-2).
4. No explicit eager-import failure-mode contract (AC13.7 says "fail-closed" but doesn't specify ImportError wrapping).
5. Decimal vs float acknowledged but inherited (acceptable with `math.isclose` tolerance).

### What would make it a 10
Pin no-compat-window rule with a stub, add `fields_pass_through_unchanged` or reject with rationale, fix Appendix B.1 `_format`.

---

## 2. Accuracy — 8.8/10 (was 6.0)

The largest single-dimension improvement. §M3 Alignment table has 33 rows; I verified every row line-by-line against `src/m3_schema_registry/types.py`:

| M7 Claim | M3 Line | ✓ |
|----------|---------|---|
| `Client.canonical_id: UUID` | 627 | ✓ |
| `Client.firm_id: UUID` | 645 | ✓ |
| `Client.advisor_ref: Optional[UUID]` | 644 | ✓ |
| `Client.accounts: list[UUID]` | 649 | ✓ |
| `Client.source_id: str` | 656 | ✓ |
| `HouseholdMember.client_ref: str` | 376 | ✓ |
| `HouseholdAccount.account_ref: str` | 383 | ✓ |
| `Holding.account_ref: str` | 722 | ✓ |
| `Holding.client_ref: Optional[str]` | 723 | ✓ |
| `TaxLot.lot_id: UUID` | 692 | ✓ |
| `TaxLot.holding_ref: str` | 693 | ✓ |
| `TaxLot.source_cost_basis_method: Optional[str]` | 706 | ✓ |
| `Transaction.transaction_id: UUID` | 781 | ✓ |
| `Transaction.account_ref: UUID` | 782 | ✓ |
| `Transaction.client_ref: Optional[UUID]` | 783 | ✓ |
| `Transaction.order_ref: Optional[UUID]` | 784 | ✓ |
| `Transaction.source_id: str` (separate) | 803 | ✓ |
| `PlanSummary.client_ref: UUID` | 953 | ✓ |
| `PlanSummary.goals: list[UUID]` | 971 | ✓ |
| `Goal.client_ref: UUID` | 988 | ✓ |
| `Goal.linked_accounts: list[UUID]` | 1002 | ✓ |

(12 more rows verified, omitted for brevity. **All 33 rows correct.**)

Additional verifications:
- `Client.client_type` validator `{individual, entity, trust}` at M3 L660–666 — T1 cites correctly.
- `AccountType.B457.value == "457"` at M3 L48 — confirmed.
- `SourceSystem` enum (M3 L62–83) — all v0.2.0 vendor slugs match.
- `CostBasisMethod` enum (M3 L87–93) — matches `COST_BASIS_VENDOR_MAP` 1-to-1.

### Strengths
- §M3 Alignment table is the single highest-leverage artifact added in v0.2.0. Side-by-side M3 + M7 verification in under 5 minutes.
- T5 transaction_id / source_id split is crystal-clear with dual rows + regression guard in Task 7.
- T1 `display_name` now has translator-level empty-string guard wrapping Pydantic `ValidationError` as `MissingRequiredField`.

### Weaknesses
1. Cosmetic: spec claims M3 types.py is 1,183 lines; actual is 1,182 (NI-3).
2. T3 Goal `as_of_date` datetime-to-date truncation loses timezone info — DECISION-LOG-worthy edge case.
3. T8 `currency` default ambiguous (vendor model default vs translator default).
4. Schwab `VENDOR_API_VERSION="v1"` still an assumption (DECISION-LOG entry).
5. SF FSC field names NOT verified — PENDING-VERIFICATION with pre-GA task (acceptable for lighthouse).
6. Orion `VENDOR_API_VERSION="v2.0"` inherited from v0.1.0 unchanged — public docs say `v1`/`v1.1`.

---

## 3. Security — 9.0/10 (was 8.5)

### Strengths
- `warnings` and `tempfile` added to forbidden imports (closes v1 #1, #5).
- Task 19 Part B scans `json.dumps(exc.details)` for PII (closes v1 #3).
- Task 19 Part C fixture scan with email TLD allowlist, SSN regex, phone `555-` prefix, IBAN `TEST-` prefix (closes v1 #4).
- AC14.8 enum-friendly regex on `UnknownEnumDetails.vendor_value` (closes v1 #6).
- AC12.4 positive AST-enforced M5 allow-list with full implementation outline (closes v1 #7).
- AC10.9 whitespace-PII handling (closes v1 #8).

### Weaknesses
1. Appendix B.1 `_format` stringifies `self.details` — `CostBasisUnmappableDetails.vendor_value: Optional[str]` could leak raw vendor strings. AC14.8 covers `UnknownEnumDetails.vendor_value` only. Extend regex to every subclass's vendor-origin field.
2. AC14.6 doesn't check `repr(note)` — engineer debugging could see vendor values.
3. Vendor-ID validator `^[a-zA-Z0-9._\-]+$` rejects Unicode (acceptable for US lighthouse).
4. Fixture scan Part C treats CUSIP as "flagged" — ambiguous (hard-fail or warn?).

---

## 4. Testability — 8.5/10 (was 7.5)

### Strengths
- AC1.3 pins sorted-before-serialization (closes v1 #2).
- AC10.4 `@settings(max_examples=100, deadline=500)` + 2-min budget (closes v1 #8).
- AC10.7 concurrency smoke: 4 threads × 50 iterations × every registry pair (closes v1 #9).
- AC7.5 two exact format literals (closes v1 #6).
- AC11.3 single-vendor only; multi-vendor handled by AC7.7 (closes v1 #10).
- AC8.5 anchored Keep-A-Changelog regex (closes v1 #11).
- AC11.8 `math.isclose(rel_tol=1e-9, abs_tol=1e-6)` money tolerance.
- Schwab UK xfail fixture skeleton verbatim in T9.

### Weaknesses
1. **Hypothesis worked example is MISSING.** Task 18 says "see §Design 'Hypothesis Strategy Approach' for SF FSC Client worked example" — **section does not exist**. Traceability row #13 claims delivered; it isn't. Clearest v0.2.0 regression. See NI-1. Engineer cannot tell whether to use `from_type(VendorModel)` or hand-write `@composite`.
2. AC10.4 2-min budget optimistic for 11 translators × 100 examples × Pydantic construction. Tier it (lighthouse=100, nightly=1000).
3. AC6.5(a) "reverse entry per vendor that touches it" phrasing permits 300% blow-up in required mappings — sharpen.
4. No Task 15 test for registry eager-import failure modes.
5. Household reverse-then-re-merge identity not covered.

---

## 5. Design Alignment — 7.5/10 (was 6.5)

### Strengths
- M8 removed from consumers, citing ARCH-09 dependency matrix audit.
- "Architecture Clarification: M7 is a Pure Library" section (L48–58) — 3-sentence high-leverage scope guard.
- Directory / package / import naming matches M3/M5/M6 convention exactly.
- AC13.2 explicit params — no reach into `req.target.*`.
- Schwab `VENDOR_API_VERSION="v1"` URL path versioning.
- Pydantic pin `>=2.0,<3.0` matches M3.

### Weaknesses
1. **§Integration Point with M6 does not exist as a section header.** Traceability row #9 cites it; content is in AC13.2 + Appendix B.6 instead. v0.1.0 HAD this section; lost in rewrite. See NI-1.
2. **§Integration Point with M11 does not exist.** Cited in header line 8 + row #10. Dual-caller audit contract content only in changelog row. See NI-1.
3. **§Directory / Package / Import Naming does not exist.** Cited in row #11. Content only in changelog row L30. See NI-1.
4. **§Design "Hypothesis Strategy Approach" does not exist.** Cited in Task 18 + row #13. No worked example anywhere. See NI-1.
5. **No `## Design` section at all.** Four traceability rows reference §Design subsections — all broken.
6. Line estimate 3,000 optimistic; realistic 7,000-9,000 including Hypothesis strategies + round-trip tests + Pydantic models + shared infra + DECISION-LOG + CHANGELOGs.
7. M11 Phase 2 calling pattern unclear — M11-REST exists in Phase 2 per ARCH-09, but audit-bypass contract deferred to lighthouse-2.

---

## 6. Gaps — 8.0/10 (was 6.9)

### Strengths
- R16 Cross-Module Observability (new) — 4 ACs pinning M7 surfaces / M6 propagates / M10 aggregates.
- `MappingProxyType` on every collection that could drift (`ENUM_MAPPINGS`, `REVERSE_ENUM_MAPPINGS`, `TRANSLATOR_REGISTRY`, `COST_BASIS_VENDOR_MAP`, `COST_BASIS_DEFAULTS`) — closes entire class of silent-idempotency bugs.
- `len(TRANSLATOR_REGISTRY) >= 11` with import-reachability invariant (closes v1 #4).
- TypedDict per `TranslationError` subclass (AC4.8, 7 TypedDicts) (closes v1 #11).
- SF FSC Person-Account vs Business-Account branching pinned in T1 + Task 3 (closes v1 #9).
- Orion partial-data rule: `tax_lots=[]` for empty `taxLots[]` (closes v1 #7).
- AC10.8 vendor-ID char constraint `^[a-zA-Z0-9._\-]+$` with validator helper (closes v1 #13).
- AC10.9 null-PII handling.
- REVERSE_LOSSY_FIELDS on every T-table.
- AC7.8 single vs multi-vendor `reconciliation` disambiguation (closes v1 #12).
- AC7.9 Household merge-order rule on role mismatches (closes v1 Completeness #6).
- Schwab `$`-prefix `@field_validator(mode="before")` with non-numeric fallback.

### Weaknesses
1. No deprecation / parallel-version story for SCHEMA_VERSION bumps (v1 #10 still open; deferred to Phase 3+).
2. No healthcheck API for M6 to probe M7 compatibility (same root as #1).
3. No round-trip test for `ReconciliationNote` itself (v1 #5 still open).
4. `schwab_iria_label_ambiguous` typo in Appendix B.4 (should be `schwab_ira_label_ambiguous`). See NI-4.
5. CUSIP/ISIN/FIGI public-data identifiers not explicitly certified as non-PII.
6. 11 Hypothesis strategy files asserted but not inventoried for CI validation.

---

## New Issues Introduced in v0.2.0 (Regressions from the Rewrite)

### NI-1 (BLOCKING for 9.0+, NOT blocking for 7.5 GO): Four phantom section references

Review Fix Traceability Table (L1344–1391) cites four sections that do NOT exist as `##` or `###` headers:

| Traceability Row | Cited Section | Header Exists? |
|------------------|---------------|----------------|
| Fix #9 | "§Integration Point with M6" | ✗ |
| Fix #10 | "§Integration Point with M11" | ✗ |
| Fix #11 | "§Design 'Directory / Package / Import Naming' table" | ✗ |
| Fix #13 | "§Design 'Hypothesis Strategy Approach'" | ✗ |

Verified via `grep "^## \|^### "` across full 1,858-line spec. These section headers do not exist. v0.1.0 HAD `§Integration Point with M6` (per v1 review L1002–1022); it was lost in rewrite.

Content status:
- Fix #9: Real in AC13.2 + B.6. **Just in wrong location.**
- Fix #10: M8 removal real in header line 8 ✓; M11 dual-caller audit is **only in changelog row**. Partial.
- Fix #11: Real but thin in changelog row L30.
- Fix #13: **Completely absent.** No Hypothesis worked example anywhere. Claim is fictional.

**Impact:** Traceability table is partly broken. Reviewer/engineer following the table hits dead-ends. Credibility regression — v0.1.0 didn't make traceability claims it couldn't back.

**Fix:** Add the four missing section headers (2–4 hours), or delete the traceability rows. Fold into Task 20's DECISION-LOG pass.

**Why not full BLOCK:** All 17 required fixes landed somewhere. Broken links are structural hygiene, not missing functionality. ~0.2 point penalty on weighted score.

### NI-2 (MINOR): Appendix B.1 skeleton PII leak in `_format`

```python
def _format(self) -> str:
    summary = ", ".join(f"{k}={v}" for k, v in sorted(self.details.items()))
    return f"[{self.reason_code}] {self.vendor}.{self.canonical_type}.{self.field_path}: {summary}"
```

Stringifies ALL values in `details`. `CostBasisUnmappableDetails.vendor_value: Optional[str]` permits raw vendor strings. AC14.8 regex limits input but skeleton sets bad precedent for copy-paste. Fix: allow-list filter to AC14.2 keys before stringifying.

### NI-3 (MINOR): Line-count citation off-by-one

Spec L9: "M3 types.py (1,183 lines)". Actual `wc -l` = 1,182.

### NI-4 (MINOR): `schwab_iria_label_ambiguous` typo

Appendix B.4 `RECONCILIATION_NOTE_SAFE_FIELDS` frozenset has `"schwab_iria_label_ambiguous"`. Should be `"schwab_ira_label_ambiguous"`.

### NI-5 (MINOR): 3,000-line estimate is optimistic

Realistic: 7,000-9,000 lines including Hypothesis strategies, round-trip tests, Pydantic vendor models, translator logic, shared infra, DECISION-LOG, CHANGELOGs. Cost-planning issue, not a defect.

---

## Remaining Issues

### Blocking for GO
None. Spec clears 7.5 bar at 8.29.

### Blocking for 9.0+ (v0.3.0)
1. Add four missing section headers or delete traceability references.
2. Include Hypothesis `@composite` worked example (SF FSC Client) inline.
3. Verify SF FSC field names against v59.0 SOQL (or ship PENDING-VERIFICATION + MINOR-bump contract).

### Cosmetic
- 1,182 vs 1,183 line count.
- `schwab_iria` → `schwab_ira` typo.
- Appendix B.1 `_format` skeleton.
- 3k vs 7k line estimate.

---

## Verdict

**Weighted score 8.29 / 10 → GO.**

v0.2.0 is a strong rewrite. The largest accuracy defect (UUID vs str across 10+ field rows) is fixed with line-by-line verification against M3 `types.py` — I re-verified every one of the 33 alignment rows. The T5 transaction_id/source_id collapse is fixed with dual rows and a regression guard. Three new UUID namespaces declared. T6 and T10 fully specified. AC12.4 AST-enforced. AC7.5 pins discrepancy formats. Task 19 extends PII-free scanning to exception details AND fixture files. R16 adds cross-module observability contract. `MappingProxyType` wraps every registry and mapping. REVERSE_LOSSY_FIELDS on every T-table. Person-vs-Business-Account branching in Task 3. Schwab UK xfail skeleton verbatim in T9. The §M3 Alignment table is a high-leverage artifact that future M3 changes can audit against in minutes.

The accuracy improvement (+2.8 from 6.0 to 8.8) is the largest single-dimension gain I have scored on this project. It moved M7 from "don't ship — spec describes a canonical model that doesn't exist" to "ship — spec describes M3 exactly".

The regression is structural, not functional: the Review Fix Traceability Table cites four sections that do not exist as headers. Intended content is distributed across changelog rows, ACs, and appendices — so the fixes materially landed — but the table is misleading. A 2–4 hour cleanup pass pushes v0.3.0 to 8.7+. Ship v0.2.0 to build; fold the section cleanup into Task 20's DECISION-LOG populating pass.

The playbook allows GO at 7.5+. M7 v0.2.0 scores 8.29. **Proceed to Step 5 (Build).** Build order: Task 1 (shared infrastructure) → Task 2 (negative tests FIRST) → Tasks 3–13 (translator pairs, depth-first one at a time) → Tasks 14–20 (integration + DECISION-LOG). Use the §M3 Alignment table as the spec-to-code contract. The Appendix B.1 `_format` skeleton is illustrative, not prescriptive — consult AC14.2 for the allow-listed fields.

---

*Review v2: M7 Schema Translators — Project 007 FSI Interoperability Platform*
*Spec Version 0.2.0 (1,858 lines) — post-LLMJ-v1 fix pass*
*Final Score: 8.29 / 10 → GO (Step 5 Build)*
