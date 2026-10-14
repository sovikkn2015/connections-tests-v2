# M2/M4 Policy Engine — LLMJ Review v1

> Reviewer: 007-trust-agent (LLMJ pass 1)
> Spec under review: `.kiro/specs/m2-m4-policy-engine.md` (v1)
> Stance: HARSH. This is the MOAT. Every ambiguity becomes a production
> incident. Compliance is deterministic; the spec must be, too.
> Threshold: >= 7.5/10 overall AND all REQUIRED fixes landed.

---

## 1. Completeness — 6.5/10

Covers most of the contract. Several gaps when examined closely.

Strong points:
- 9 rules (8 authority + meta) fully specified with rule IDs + WSPs.
- 5 MNPI rules listed with exact field paths.
- Evaluation order explicit (R4.1).
- Phase 1 / Phase 2 delineation clear.
- Non-mutation semantics for MNPI filter clear.

**F1 (REQUIRED) — R2.2 ordering semantics are contradictory.**
Step 5 says DENY/ESCALATE is terminal and stops the loop. Step 6 says
ALLOW records and continues. Step 7 says "return the FIRST ALLOW."
But if a later rule (e.g., principal.review_required) returns
ESCALATE, the earlier ALLOW is never reached because the engine
already stopped at ESCALATE. The "FIRST ALLOW" wording is fine, but
the spec should explicitly state: the recorded ALLOW is returned ONLY
IF no later rule returns DENY or ESCALATE. Add a concrete example
showing advisor.read_own_clients=ALLOW then
advisor.concentration_limit=ESCALATE giving a final ESCALATE.

**F2 (REQUIRED) — T12 test expectation contradicts R2.2.**
T12 says "ESCALATE (concentration) returned even when earlier rules
ALLOW." This is correct but R2.2 as written is ambiguous. Pin it:
ALLOW is recorded but DENY/ESCALATE from a later rule OVERRIDES.

**F3 (REQUIRED) — principal.review_required dual_registered path
unclear.**
Dual-registered firms correctly trigger this rule for BD-side
activity. The spec treats that as implicit. Add an explicit note so a
reviewer doesn't read it as a bug.

**F4 (REQUIRED) — Missing-context handling is inconsistent across
rules.**
R1.5 says M2 returns DENY on missing context. R4.2 says "Missing
target[advisor_id]" produces the same. That key is on target, not
context. Rename R1.5 to "Missing target or context keys" and make it
a single policy across both dicts.

**F5 (REQUIRED) — Role Phase 1 set does NOT include senior_advisor
yet R5.3 still says "role >= senior_advisor (Phase 1:
compliance_officer only)."**
Pin: the Phase 1 code constant is literally
is_compliance_officer = lambda role: role == Role.compliance_officer.
The ">=" language is documentation-only.

**F6 (REC) — No coverage for client.list in
read_other_advisor_clients.**
R1.4 lists client.list. advisor.read_own_clients lists
{client.read, client.list, portfolio.view}.
read_other_advisor_clients lists only {client.read, portfolio.view}.
Cross-advisor listing should also be denied. Add client.list.

**F7 (REQUIRED) — No spec for Role.system / Role.agent.**
M1 Role has advisor, compliance_officer, system, agent. The rules
only handle advisor + compliance_officer paths. What does an
agent/system role get? Silent default-deny? Decide and write it.

**F8 (REQUIRED) — PolicyInput examples are prose, not literal.**
R1.3 lists target keys per action as English. Provide concrete
Python literal examples for at least client.read, order.submit,
comm.send_retail.

**F9 (REC) — Missing rule_applied for meta default-deny vs
unknown_action.**
R1.4 uses authority/meta/unknown_action.v1, R2.2 uses
authority/meta/default_deny.v1. Two different meta rules. List them
both in rule_table.

**F10 (REQUIRED) — AST scan allow-list is incomplete.**
R9 allows m3_schema_registry.{Client, SecurityProfile, ...} but
section 2.7 says mnpi.py also uses Beneficiary. Add Beneficiary to
R9's allow-list.

Score: 6.5/10.

---

## 2. Accuracy — 7.0/10

Generally aligned with source docs. A few mismatches.

Strong points:
- wsp_section strings match the task description exactly.
- Rule IDs chosen for Phase 2 OPA compatibility.
- Role hierarchy note acknowledges Phase 1 reality.

**F11 (REQUIRED) — Decision.ESCALATE vs M3 ComplianceDecision.**
M3's ComplianceDecision has 5 members (ALLOW, DENY, WARN,
REQUIRE_APPROVAL, ESCALATE). M2/M4 has 3. The mapping from
Decision to ComplianceDecision that M6 will use is unspecified. Pin
it: Decision.ALLOW -> ComplianceDecision.ALLOW, Decision.DENY ->
ComplianceDecision.DENY, Decision.ESCALATE ->
ComplianceDecision.REQUIRE_APPROVAL. Enforce in a unit test.

**F12 (REC) — authority_scope / authority_excludes are referenced but
never consumed.**
M1 carries these. Phase 1 doesn't touch them. Declare explicitly as
a Phase 2 rule with a placeholder rule_applied.

**F13 (REC) — Beneficiary drift check at construction.**
Move the drift check from the test into MnpiPolicy.__init__ so a
missing attribute surfaces at construction, not at first call.

**F14 (REQUIRED) — concentration_pct type handling unclear.**
R4.6 says float > 0.10. But what about int(1)? Pin: MUST be a float
in [0.0, 1.0]. Non-float or out-of-range is treated as missing.

Score: 7.0/10.

---

## 3. Security — 7.0/10

Good practices enumerated; some gaps.

Strong points:
- R8 credential grep.
- R6 AST scan for forbidden imports.
- R5.1 input non-mutation via model_copy.

**F15 (REQUIRED) — R7.4 says reason does not contain exception
message but no mechanism.**
Pin: on exception, the engine constructs reason='evaluation_error'
(a LITERAL string). The exception message is DISCARDED. Add a test
that a rule raising RuntimeError("client@example.com") produces
reason == "evaluation_error" (no email substring).

**F16 (REQUIRED) — No guard against a rule returning a DENY with PII
leaked into reason / details.**
Phase 1 has no user rules, so this is hypothetical. Explicitly defer
to Phase 2 in section 0.2 and R7, OR implement a post-validation
check on every rule-returned decision.

**F17 (REC) — MnpiPolicy.filter returns input unchanged for
unsupported types — silent security risk.**
If the builder forgets to add a canonical type, filter returns it
unfiltered. Proposed: filter(claims, instance, strict=True) raises
on unknown type. Default strict=False for composability. M6's wrapper
passes strict=True.

**F18 (REQUIRED) — R8.3 non-mutation is module guarantee, not E2E.**
After filter, the original client still has SSN. Phase 1 cannot
prevent this at the module boundary. State: "Non-mutation is a module
guarantee. Callers MUST drop the original reference after filter().
M6 enforces via a single-use pattern." Document in §0.6.

Score: 7.0/10.

---

## 4. Testability — 7.0/10

Most ACs are testable. Several are vague.

Strong points:
- Every rule has ALLOW and DENY/ESCALATE paths.
- AC-R6-1 100-call determinism.
- AC-R8-3 non-mutation test.

**F19 (REQUIRED) — AC-R5-10 identity vs value semantics ambiguous.**
Pydantic model_copy does a shallow copy at the top level. Nested
fields are references. "Identity of original fields" could mean is
comparison or ==. Pin:
- Flat: original.ssn_last_four == "1234" after filter (value check).
- Nested: original.beneficiary.account_number == "ACCT-9" after filter.

**F20 (REQUIRED) — AC-R6-1 dict identity unclear.**
100-call determinism uses structural equality via ==. What about
dict identity? Not required. State explicitly.

**F21 (REC) — T13 exception-handling test needs a mechanism.**
Pin: Tests subclass AuthorityPolicy with _build_rules returning a
custom tuple including a _BoomRule that raises.

**F22 (REC) — No golden-vector test for rule_table() output.**
Add an AC pinning the EXACT list of 9 dicts for authority and 5 for
mnpi.

**F23 (REC) — Smoke test must be an executable contract.**
T24 should assert decision.decision == ALLOW, rule_applied, wsp_section,
and filtered field values explicitly.

Score: 7.0/10.

---

## 5. Design Alignment — 7.5/10

Reasonably aligned with ARCH docs.

Strong points:
- Rule-path format matches OPA package convention.
- Phase 1/2 migration story coherent.

**F24 (REQUIRED) — MnpiPolicy mixes filter and access rule types.**
list_rules and rule_table must distinguish them. Add
rule_kind: Literal["filter", "access"] to each rule_table entry.

**F25 (REC) — ARCH-07 "FastAPI + OPA" applies to Phase 2.**
Add a line in 0.1: "The FastAPI + OPA row in ARCH-07 describes the
Phase 2 deployment, not Phase 1."

**F26 (REC) — 0.7 drift test needs concrete failure cases.**
Pin: "If M1 Role removes compliance_officer, the drift test fails. If
M3 Client removes ssn_last_four, the drift test fails. If M5
RegistrationType removes bd_only, the drift test fails."

Score: 7.5/10.

---

## 6. Gaps — 6.5/10

Non-goals list is thorough but some edge cases still uncovered.

**F27 (REQUIRED) — AidClaims.authority_excludes is ignored.**
If an AID has authority_excludes=["order.submit"], the engine should
auto-DENY order.submit regardless of other rules. Phase 1 MUST
include this check as a dedicated rule
(authority/meta/excludes_check.v1, WSP-META-0.2) at the very start of
the evaluation order. Alternatively, explicitly mark as Phase 2 with
a documented non-goal — but the CVE-like risk of ignoring a
negative-authority assertion is too high to defer.

**F28 (REQUIRED) — principal.review_required is too minimal.**
IMPL-06 Blocker 4 says the rule classifies based on "recipient type,
content type, channel, archetype, registration type." Phase 1 uses
only recipient_type. Acknowledge the other factors as Phase 2 and
name the future extensions.

**F29 (REC) — No coverage for payment.draft.**
Add: "Phase 1 does not implement payment.draft authority. Caller
gets DENY / no_rule_matched. Phase 2 adds a BSA/AML gate." Document
in non-goals.

**F30 (REC) — Gap 6 boundary not stated.**
Spec should say: "M4 filters INPUTS (pre-LLM). Gap 6 (MNPI Leakage
Scan, M6 sub-module) scans OUTPUTS (post-LLM). M2/M4 does NOT
implement Gap 6."

Score: 6.5/10.

---

## Summary of findings

### REQUIRED fixes (must land in v2)

| # | Section | Fix |
|---|---------|-----|
| F1 | R2.2 | Clarify deny-overrides with explicit example |
| F2 | R2.2/T12 | Pin "ALLOW recorded, DENY/ESCALATE overrides" |
| F3 | R4.9 | Clarify dual_registered intentionally triggers FINRA 2210 |
| F4 | R1.5 | Unify missing-target/context policy |
| F5 | R5.3 | Pin Phase 1 predicate as role == Role.compliance_officer |
| F7 | R4.*/R5.* | Spec Role.system / Role.agent handling |
| F8 | R1.3 | Concrete PolicyInput literal examples per action |
| F10 | R9 | Add Beneficiary to allow-list |
| F11 | R1.1 | Map Decision to M3 ComplianceDecision |
| F14 | R4.6 | Pin concentration_pct as float in [0.0, 1.0] |
| F15 | R7 | Pin reason == "evaluation_error" literal |
| F18 | §0.6 | Document non-mutation is module guarantee, not E2E |
| F19 | AC-R5-10 | Pin identity vs value semantics |
| F20 | AC-R6-1 | Pin structural (not identity) equality |
| F24 | R10 | rule_table entries include rule_kind |
| F27 | R9 | Add authority.meta.excludes_check.v1 rule |
| F28 | R4.9 | Note Phase 2 content/channel classifier |

### RECOMMENDED fixes (address during build)

| # | Section | Fix |
|---|---------|-----|
| F6 | R1.4 / R4.3 | Add client.list to read_other_advisor_clients.actions |
| F9 | R1.4/R2.2 | Clarify unknown_action.v1 vs default_deny.v1 |
| F12 | R9 | Explain authority_scope Phase 1 non-use |
| F13 | T19 | Move Beneficiary drift check into __init__ |
| F16 | R7 | Post-validate rule-returned reason for PII (Phase 2) |
| F17 | R5.1 | filter(..., strict=True) opt-in |
| F21 | T13 | Pin subclass-override pattern for tests |
| F22 | AC-R10-* | Golden-vector test for rule_table output |
| F23 | T24 | Smoke test as executable contract |
| F25 | §0.1 | Clarify FastAPI row applies to Phase 2 |
| F26 | §0.7 | Concrete drift-test failures |
| F29 | §0.2 | payment.draft unimplemented in Phase 1 |
| F30 | §0.2 | Gap 6 boundary (pre-LLM vs post-LLM) |

---

## Overall

| Dimension | Score | Weight | Weighted |
|-----------|-------|--------|----------|
| Completeness | 6.5 | 25% | 1.625 |
| Accuracy | 7.0 | 20% | 1.400 |
| Security | 7.0 | 20% | 1.400 |
| Testability | 7.0 | 15% | 1.050 |
| Design Alignment | 7.5 | 10% | 0.750 |
| Gaps | 6.5 | 10% | 0.650 |
| **TOTAL** | | | **6.875 / 10** |

### Verdict: CONDITIONAL GO — 17 REQUIRED fixes blocking

Score 6.88 < 7.5 threshold.

Spec is structurally sound but the compliance surface has ambiguities
that will cause production incidents. Required fixes center on:
- Deny-overrides semantics precision.
- Missing role / action / archetype branch coverage.
- authority_excludes handling.
- Decision to ComplianceDecision mapping.
- Security guarantee language.
- Testable post-conditions.

Rewrite as v2 addressing all 17 REQUIRED fixes. 13 RECOMMENDED items
should be addressed during build but are not blocking.

---

*m2-m4-policy-engine-REVIEW.md — LLMJ pass 1*
