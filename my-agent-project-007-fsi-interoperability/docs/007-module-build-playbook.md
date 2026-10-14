# Project 007: Module Build Playbook

> How M3 was built. How every module after it must be built.
> This is the proven process. Do not deviate.

---

## The Process (7 Steps)

### Step 1: Write the Spec

Create a Kiro spec at `.kiro/specs/{module}-spec.md` with three sections:

**Requirements** — What the module does. Each requirement has numbered acceptance criteria (AC).
Every AC must be deterministic and testable — no ambiguity. Reference the design docs
(007-consolidated-design-and-plan.md, ARCH-09, ARCH-07, IMPL-06) for field-level detail.

**Design** — Directory structure, API surface, security constraints, module boundary.
List every file that will be created. Define the public interface (functions, classes, constants).

**Tasks** — Numbered, ordered, atomic. Each task produces implementation + tests together.
Each task references specific ACs it covers. A task is not done until its tests pass.

What made M3's spec work: field-level definitions for every type, every enum value listed
explicitly, every sub-model defined. The spec was 1,100 lines — comprehensive enough that
the builder agent never had to guess.

### Step 2: LLMJ Review (First Pass)

Send the spec to the specialist sub-agent for the module with instructions to review as
an LLMJ (LLM Judge). Score on 6 dimensions:

1. COMPLETENESS (25%) — Does it cover everything the design docs require?
2. ACCURACY (20%) — Do the details match the source of truth?
3. SECURITY (20%) — PII/MNPI handled? Credentials? Input validation?
4. TESTABILITY (15%) — Can every AC be tested deterministically?
5. DESIGN ALIGNMENT (10%) — Does it match ARCH-07, ARCH-09?
6. GAPS (10%) — What's missing?

The reviewer must be harsh. The reviewer must list every issue found.
The reviewer writes the review to `.kiro/specs/{module}-REVIEW.md`.

M3 first review: 4.8/10 CONDITIONAL GO. Found 10 critical issues including zero field-level
definitions, wrong MNPI mechanism, cost_basis_method on wrong type, Household errors,
15+ missing enums.

### Step 3: Fix the Spec

Send the spec + review back to the specialist agent with instructions to rewrite the spec
addressing every required fix. The agent rewrites the spec from scratch — not patches,
a full rewrite.

M3: Schema agent rewrote from 90 lines to 1,100 lines. All 10 required fixes + 5
recommended fixes addressed. Review fix traceability table added mapping each fix
to the spec section that addresses it.

### Step 4: LLMJ Review (Second Pass)

Same specialist agent re-reviews the corrected spec. Same 6 dimensions. Must score 7.5+/10
for GO verdict. If CONDITIONAL GO, repeat Steps 3-4. If NO GO, escalate.

M3 second review: 8.35/10 GO. All 10 fixes verified. 7 minor items noted for implementation
(none blocking).

### Step 5: Build

Send the GO spec to the specialist agent with instructions to build everything.
The agent builds autonomously — no human approval per file.

Build rules given to the agent:
- Follow the spec exactly. Every field, every enum, every sub-model.
- Tests WITH implementation — not after.
- Fix minor items from the LLMJ review during implementation.
- No credentials in any file.
- No cross-module imports.
- Only allowed imports (stdlib + framework).

M3: Schema agent built all 19 tasks. types.py (1,182 lines), __init__.py (195 lines),
18 JSON Schema files, validation script, DECISION-LOG, unit tests (57), reconciliation
tests (90).

### Step 6: Verify Tests Pass

Run all tests. Not the agent's word — actual test execution.

```bash
PYTHONPATH=my-agent-project-007-fsi-interoperability/src \
  python3 -m pytest my-agent-project-007-fsi-interoperability/tests/ -v --tb=short
```

Plus any module-specific validation:
```bash
python3 my-agent-project-007-fsi-interoperability/scripts/validate-schemas.py
```

M3: 147 tests passed (57 unit + 90 reconciliation). Schema validation script exit 0.

### Step 7: Mark Module Complete

The module is done when:
- [ ] All tests pass (verified by running them, not by agent claim)
- [ ] LLMJ review scored 7.5+/10 GO
- [ ] Zero cross-module imports (verified by test or AST scan)
- [ ] No hardcoded credentials (verified by hook)
- [ ] Security checklist passed (PII annotated, inputs validated, MNPI handled)
- [ ] Spec acceptance criteria all covered by tests

Only then move to the next module.

---

## The Agents Involved

| Role | Agent | What It Does |
|------|-------|-------------|
| Planner | Main agent (me) | Writes initial spec, orchestrates the process |
| Reviewer | Specialist sub-agent | LLMJ review — harsh, specific, scored |
| Fixer | Same specialist | Rewrites spec to address review findings |
| Builder | Same specialist | Builds code + tests from the GO spec |
| Verifier | Main agent (me) | Runs tests, confirms they pass |

The specialist agent changes per module:
- M3, M7: `007-schema-agent`
- M1, M2/M4, M10, M5: `007-trust-agent`
- M6: `007-gateway-agent`
- M8, M9: `007-pipeline-agent`
- M11: `007-adapter-agent`
- Compliance gaps: `007-compliance-agent`

---

## What This Process Prevents

| Failure Mode | How It's Prevented |
|-------------|-------------------|
| Spec too vague → wrong implementation | LLMJ review catches vagueness (M3: 4.8/10 first pass) |
| Code doesn't match design | Spec references design docs, LLMJ verifies alignment |
| Security afterthought | LLMJ scores security as 20% of review, hooks enforce on every write |
| Tests written after code (or not at all) | Tasks require tests WITH implementation, verified by running |
| Breadth-first scaffolding | One module complete before next starts, hooks enforce build order |
| Agent praises its own work | Separate reviewer agent, tuned to be skeptical |
| Context drift across modules | Fresh agent invocation per module, steering file provides persistent context |
| Mocks that don't match reality | Integration tests at phase boundaries use real module interfaces |

---

## Build Order (Remaining)

```
✅ Phase 0: M3 (Schema) — DONE (147 tests, 8.35/10 GO)
⬜ Phase 0: M5 (Enterprise Config)
   → Integration test: M3 + M5 together

⬜ Phase 1: M1 (Agent Identity)
⬜ Phase 1: M10 (Audit Logger)
⬜ Phase 1: M2/M4 (Policy Engine)
⬜ Phase 1: M6 (MCP Gateway)
⬜ Phase 1: Gap 2 (Liability Provenance)
⬜ Phase 1: Gap 6 (MNPI Leakage Scan)
   → Integration test: Full trust pipeline (M1 → M2 → M4 → M6 → M10)

⬜ Phase 2: M7 (Schema Translators)
⬜ Phase 2: M11-REST (MCP Adapters)
⬜ Phase 2: M9 (Intent Router)
⬜ Phase 2: M8 (Pipeline Engine)
   → Integration test: Full query flow
```

---

## M3 Build Evidence

| Artifact | Location | Lines |
|----------|----------|-------|
| Spec (v2, GO) | `.kiro/specs/m3-canonical-schema.md` | ~1,100 |
| LLMJ Review v1 (4.8/10) | `.kiro/specs/m3-canonical-schema-REVIEW.md` | ~400 |
| LLMJ Review v2 (8.35/10 GO) | `.kiro/specs/m3-canonical-schema-REVIEW-v2.md` | ~300 |
| Source: types.py | `src/m3_schema_registry/types.py` | 1,182 |
| Source: __init__.py | `src/m3_schema_registry/__init__.py` | 195 |
| JSON Schemas | `schemas/canonical/*.json` × 18 | ~1,200 |
| Unit tests | `tests/unit/test_m3_schema_registry.py` | 643 |
| Reconciliation tests | `tests/schema-reconciliation/test_schema_json_match.py` | 93 |
| Schema validator | `scripts/validate-schemas.py` | 100 |
| Decision log | `schemas/canonical/DECISION-LOG.md` | ~60 |
| **Total** | | **~5,273** |

Test results: 147 passed, 0 failed, 0.52s.

---

*007-module-build-playbook.md — Project 007 FSI Interoperability Platform*
*This is the process. Follow it for every module.*
