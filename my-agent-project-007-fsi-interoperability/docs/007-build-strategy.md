# Project 007: Build Strategy — Lessons from How the Best Ship Code with AI

> Date: April 23, 2026
> Purpose: Prevent the mistakes from the first build. Define how we build 007 from scratch.
> Sources: OpenAI Harness Engineering, Anthropic Harness Design, Kiro Spec-Driven Development,
>          Veracode 2026 GenAI Security Report, OWASP, Augment Code, INNOQ, HuggingFace Agentic Trends

---

## What Went Wrong Last Time

The first 007 build produced 454 tests and zero working integration. The code looked right but was built with shortcuts:

1. **Breadth-first, not depth-first.** All 13 modules were scaffolded simultaneously. None were complete.
2. **Mocks everywhere.** Modules were tested against mocks, not real interfaces. The mocks didn't match reality.
3. **No contract verification.** Code was written, tests were written, but nobody verified the code matched the design doc.
4. **No integration gates.** Modules were built in isolation with no phase-boundary integration tests.
5. **Security was afterthought.** Credentials patterns, MNPI handling, and input validation were "we'll add later."
6. **Context drift.** As the build progressed, the AI lost track of architecture rules and started taking shortcuts.

---

## What the Industry Learned in 2025-2026

### OpenAI: "Harness Engineering" (April 2026)

OpenAI built a million-line product with zero manually-written code using Codex. Key lessons
([source](https://openai.com/index/harness-engineering/)):

- **Give the agent a map, not a manual.** A short AGENTS.md (~100 lines) points to deeper docs.
  Don't dump everything into context. Progressive disclosure: start small, teach where to look.
- **Enforce invariants, not implementations.** Strict architectural layers with validated dependency
  directions. Custom linters enforce boundaries mechanically. The agent has freedom within boundaries.
- **Repository is the single source of truth.** If it's not in the repo, it doesn't exist for the agent.
  Slack discussions, design decisions, architectural patterns — all must be versioned in-repo.
- **Documentation gardening.** A recurring agent scans for stale docs and opens fix-up PRs.
  Knowledge base must stay current or the agent builds against outdated assumptions.
- **"Golden principles" over manual cleanup.** Encode taste as mechanical rules. Run background
  agents that scan for deviations and open targeted refactoring PRs. Technical debt is garbage
  collected continuously, not in painful bursts.
- **Boring tech wins.** Technologies that are composable, API-stable, and well-represented in
  training data are easier for agents to model. Sometimes reimplementing a subset is cheaper
  than working around opaque upstream behavior.

### Anthropic: "Harness Design for Long-Running Apps" (March 2026)

Anthropic's internal team built complex full-stack apps with multi-hour autonomous coding sessions.
Key lessons ([source](https://www.anthropic.com/engineering/harness-design-long-running-apps)):

- **Three-agent architecture: Planner → Generator → Evaluator.** The planner expands a brief
  prompt into a full spec. The generator builds one feature at a time. The evaluator QAs the
  running application (not just the code) using Playwright/browser automation.
- **Sprint contracts.** Before each sprint, generator and evaluator negotiate what "done" looks
  like. Testable criteria are agreed upon before code is written. This bridges the gap between
  high-level spec and testable implementation.
- **Separate generation from evaluation.** Agents are poor at self-evaluation — they praise their
  own work even when it's mediocre. A separate evaluator tuned to be skeptical catches real bugs.
- **Context resets over compaction.** Clearing the context window entirely and starting fresh with
  a structured handoff artifact beats summarizing in place. Clean slate prevents context anxiety.
- **Spec stays high-level on purpose.** The planner focuses on product context and high-level
  technical design, NOT granular implementation details. Errors in a detailed spec cascade into
  the implementation. Let the agent figure out the path within constraints.

### Kiro: Spec-Driven Development

Kiro's native spec workflow ([source](https://kiro.dev/docs/specs/)):

- **Requirements → Design → Tasks.** Each spec has three phases. Requirements define WHAT with
  acceptance criteria. Design defines HOW with technical approach. Tasks are numbered, ordered,
  implementable units.
- **Human reviews each phase.** The agent proposes, the human approves or edits, then the agent
  proceeds. No autonomous phase transitions.
- **Tasks are atomic.** Each task produces a testable, reviewable change. The agent works through
  tasks one at a time.
- **Steering files provide persistent context.** Architecture rules, coding standards, and project
  conventions are always loaded. The agent never starts from zero.

### Security: The 45% Problem

Veracode's 2026 study found 45% of AI-generated code contains exploitable vulnerabilities
([source](https://www.alexcloudstar.com/blog/ai-generated-code-security-risks-2026/)). The top
patterns in AI-generated code:

- Hardcoded credentials (API keys, passwords in source)
- Improper input validation
- Over-permissive IAM/authorization
- SQL injection via string concatenation
- Path traversal vulnerabilities

Mitigation (from [Bishop Fox](https://bishopfox.com/resources/security-guardrails-ai-code-checklist),
[Gyanblog](https://www.gyanblog.com/security/software-security-ai-era-ways-write-secure-code/)):

- **Treat ALL AI-generated code as untrusted.** Review every line.
- **Never embed secrets in code.** All secrets via environment variables or secret managers.
- **Parameterized queries everywhere.** No string concatenation for SQL/API calls.
- **Input validation at every boundary.** Parse, don't guess (Pydantic, JSON Schema).
- **SAST/DAST in CI/CD.** Automated security scanning on every commit.
- **Pre-commit hooks** that block credentials, MNPI patterns, and known vulnerability patterns.

### Spec-Driven Architecture Contracts (INNOQ, Feb 2026)

When agents build, architecture must speak
([source](https://www.innoq.com/en/blog/2026/02/spec-driven-architecture-contracts-fuer-agenten/)):

- **Domain contracts:** Define bounded contexts, entity ownership, allowed cross-domain calls.
- **Architecture contracts:** Layer dependencies, allowed imports, module boundaries.
- **Ops contracts:** Health checks, logging format, metrics, deployment topology.
- **Security contracts:** Auth requirements, data classification, encryption at rest/transit.

These contracts are versioned, machine-readable, and enforced in CI. The agent reads them
before writing code. Violations are caught mechanically, not by human review.

---

## The 007 Build Strategy

Based on the above research, here is the strategy for rebuilding 007.

### Principle 1: Spec-First, Code-Second

Every module gets a Kiro spec before any code is written:

1. **Requirements** — What the module does, inputs, outputs, acceptance criteria.
   References the design doc (007-consolidated-design-and-plan.md, ARCH-09).
2. **Design** — API surface, data models, error handling, security constraints.
   Includes the module's architecture contract (boundaries, dependencies, auth).
3. **Tasks** — Numbered, ordered, atomic implementation units. Each task produces
   a testable change. Tests are written BEFORE or WITH the implementation (TDD).

The spec is the contract. Code that doesn't match the spec is wrong.

### Principle 2: Depth-First, One Module at a Time

Build order follows the dependency matrix exactly:

```
Phase 0: M3 (Schema) → M5 (Config)
Phase 1: M1 (Identity) → M10 (Audit) → M2/M4 (Policy) → M6 (Gateway)
         + Gap 2 (Liability Provenance) + Gap 6 (MNPI Leakage Scan)
Phase 2: M7 (Translators) → M11-REST (Adapters) → M9 (Intent) → M8 (Pipeline)
```

Each module is COMPLETE (implementation + tests + passing + reviewed) before the next begins.
No scaffolding the next module while the current one has failing tests.

### Principle 3: Integration Gates at Phase Boundaries

- After Phase 0: Integration test M3 + M5 together (config loads, schema validates).
- After Phase 1: Integration test the full trust pipeline (M1 → M2 → M4 → M6 → M10).
  A request flows through all trust modules end-to-end. MNPI is filtered. Audit is written.
  Deny path works. Allow path works. Escalate path works.
- After Phase 2: Integration test a full query flow (intent → gateway → adapter → translator
  → MNPI filter → audit → response).

No phase transition without passing integration tests.

### Principle 4: Separate Generator from Evaluator

After each module is built, a separate review pass checks:

1. Does the code match the spec? (Contract verification)
2. Does the code match the design doc? (Architecture alignment)
3. Are there hardcoded credentials? (Security)
4. Are MNPI fields handled correctly? (Compliance)
5. Are module boundaries respected? (No cross-module imports)
6. Do tests cover the acceptance criteria? (Coverage)

The hooks we already have (007-architecture-alignment, 007-post-write-review,
007-opa-compliance-review) serve as the mechanical evaluator. They fire on every write.

### Principle 5: Security is Not Optional

For every module, before it's considered complete:

- [ ] No hardcoded credentials (enforced by hook + grep in CI)
- [ ] All inputs validated at boundary (Pydantic models for Python, Zod for TypeScript)
- [ ] MNPI fields never sent to LLM unfiltered (enforced by M4 OPA rules)
- [ ] All client data access logged to M10 (enforced by hook)
- [ ] cost_basis_method never null on holdings (enforced by Pydantic + hook)
- [ ] No cross-module imports (enforced by hook + linter)
- [ ] Secrets loaded from environment variables only

### Principle 6: Steering File is the Map

The existing `.kiro/steering/007-fsi-interoperability.md` is the persistent context.
It contains architecture rules, build order, and module boundaries. It loads automatically
for every file in the 007 folder. The agent never starts from zero.

Keep it under 100 lines (it currently is). Point to deeper docs, don't dump everything in.

### Principle 7: Context Resets Between Modules

Each module should be built in a focused session. When moving to the next module:

- Start a fresh conversation
- The steering file provides persistent context
- The spec for the new module provides the contract
- The previous module's API surface (not implementation) provides the interface

This prevents context drift where the agent starts confusing Module A's patterns with
Module B's requirements.

### Principle 8: Tests Are the Acceptance Criteria

For each task in a spec:

1. Write the test first (or simultaneously with the implementation)
2. The test must reference a specific acceptance criterion from the spec
3. The test must pass before the task is marked complete
4. Integration tests at phase boundaries verify cross-module behavior

No "tests pass against mocks that don't match reality." Integration tests use real
module interfaces, not mocked ones.

---

## The Build Sequence

```
STEP 1: Create Kiro spec for M3 (Canonical Schema)
        → Requirements, Design, Tasks
        → Human reviews and approves
        → Agent implements tasks one at a time
        → All tests pass
        → Module complete

STEP 2: Create Kiro spec for M5 (Enterprise Config)
        → Same process
        → Integration test: M3 + M5 together

STEP 3: Create Kiro spec for M1 (Agent Identity)
        → Same process

STEP 4: Create Kiro spec for M10 (Audit Logger)
        → Same process

STEP 5: Create Kiro spec for M2/M4 (Policy Engine)
        → Same process

STEP 6: Create Kiro spec for M6 (MCP Gateway)
        → Same process
        → Integration test: Full trust pipeline (M1 → M2 → M4 → M6 → M10)

STEP 7: Compliance gaps (Gap 2, Gap 6)
        → Built as sub-modules of M6/M10
        → Integration test: Trust pipeline with compliance

... continue for Phase 2 modules ...
```

---

## What This Strategy Prevents

| Previous Failure | How This Strategy Prevents It |
|-----------------|------------------------------|
| Breadth-first scaffolding | Depth-first, one module at a time |
| Mocks that don't match reality | Integration tests at phase boundaries |
| Code doesn't match design | Spec-first with contract verification |
| Security afterthought | Security checklist per module, hooks enforce |
| Context drift | Context resets between modules, steering file |
| No integration testing | Phase boundary gates with real interfaces |
| "We'll add tests later" | TDD — tests written with implementation |

---

## Sources

- OpenAI Harness Engineering: [openai.com/index/harness-engineering](https://openai.com/index/harness-engineering/)
- Anthropic Harness Design: [anthropic.com/engineering/harness-design-long-running-apps](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- Kiro Specs: [kiro.dev/docs/specs](https://kiro.dev/docs/specs/)
- Veracode 2026 GenAI Security: [alexcloudstar.com](https://www.alexcloudstar.com/blog/ai-generated-code-security-risks-2026/)
- INNOQ Spec-Driven Architecture: [innoq.com](https://www.innoq.com/en/blog/2026/02/spec-driven-architecture-contracts-fuer-agenten/)
- Agentic Coding Trends 2026: [huggingface.co](https://huggingface.co/blog/Svngoku/agentic-coding-trends-2026)
- Bishop Fox Security Guardrails: [bishopfox.com](https://bishopfox.com/resources/security-guardrails-ai-code-checklist)
- Content was rephrased for compliance with licensing restrictions.

---

*007-build-strategy.md — Project 007 FSI Interoperability Platform*
