# Project 007 v3: Build Strategy — Specialist Skills & Architecture Adherence

> Date: April 12, 2026
> Problem: 007 is a large, complex build (~20,000 lines across 12+ modules, 7 compliance gaps, 5 archetypes). Every module must adhere to the v2/v3 architecture. No shortcuts. No fixing afterwards.
> Solution: Specialist build agents with domain-specific skills, architecture enforcement via steering files and hooks, and a layered quality gate system.
> Research: Claude Code subagents, Kiro steering/hooks/custom agents, OpenClaw SKILL.md pattern, agent skills framework (Anthropic), harness engineering patterns.

---

## The Core Insight

007 cannot be built by one agent doing everything. It needs specialist agents, each with deep knowledge of their domain, constrained to their module boundaries, and enforced by architecture hooks that prevent drift.

Three systems enable this:

1. Kiro Steering Files (.kiro/steering/) -- always-on architecture rules loaded into every agent session
2. Kiro Hooks (.kiro/hooks/) -- pre/post tool-use checks that BLOCK non-compliant code before it is written
3. Kiro Custom Agents / Subagents -- specialist agents with domain-specific prompts, tool access, and context files

The 006 project already uses this pattern (006-openclaw-fsi.md steering + 5 hooks). 007 needs a much more comprehensive version.

---

## The Build Architecture

```
ARCHITECT (human) -- specs, reviews, approves
    |
ORCHESTRATOR (Kiro main agent) -- delegates to specialists
    |
    +-- TRUST AGENT (M1, M2/M4, M10)
    +-- SCHEMA AGENT (M3, M7)
    +-- GATEWAY AGENT (M6)
    +-- PIPELINE AGENT (M8, M9)
    +-- ADAPTER AGENT (M11)
    +-- COMPLIANCE AGENT (Gaps 1-7)
```

Each specialist has its own steering file, context files, module boundary, and cannot write outside its domain.

---

## 6 Specialist Build Agents

### Agent 1: Trust Layer Specialist (M1, M2/M4, M10)

Builds: Identity service (Keycloak + AID), OPA policy engine (authority + MNPI bundles), audit logger (three-tier WORM), provenance chain.

Context files loaded every session:
- 007-v2-tech-stack-decisions.md (M1, M2/M4, M10 sections)
- 007-v3-compliance-gap-designs.md (Gap 2: Liability, Gap 6: MNPI Scan)
- 007-v2-multi-agent-and-memory-architecture.md (guardrails composition)

Rules enforced:
- All policy evaluation via OPA/Rego only
- Fail-closed on all trust decisions
- Every audit write includes SHA-256 integrity hash
- WORM uses S3 Object Lock Compliance mode
- AID travels with every request
- MNPI filter log produced for every data access
- Cannot write files outside M1, M2, M4, M10
- Cannot use LLM for compliance decisions

### Agent 2: Schema Specialist (M3, M7)

Builds: Canonical schema registry (JSON Schema), schema translators (per vendor).

Context files:
- 007-v2-tech-stack-decisions.md (M3, M7 sections)
- 007-v3-compliance-gap-designs.md (Gap 5: ERISA account types)
- 007-fsi-enterprise-archetypes-technology-analysis.md (vendor systems)

Rules enforced:
- All types in JSON Schema Draft 2020-12
- Every field has description documenting inclusions/exclusions
- Semantic versioning with breaking change detection in CI
- Every translator has automated reconciliation tests
- Account type field required on Client, Holding, Order
- Cannot write files outside M3, M7
- Cannot define types without field-level documentation

### Agent 3: Gateway Specialist (M6)

Builds: Trust-aware MCP gateway (FastAPI middleware).

Context files:
- 007-v2-tech-stack-decisions.md (M6 section)
- 007-v2-multi-agent-and-memory-architecture.md (guardrails composition)
- 007-module-architecture-and-interconnectivity.md (M6 dependencies)

Rules enforced:
- Every MCP call passes through M6
- Pre-call: verify AID, check authority, filter MNPI
- Post-call: filter response, scan for leakage, audit
- Circuit breaker per MCP server
- Rate limiting per user per tool
- Generic error messages to clients, full errors to logs
- Cannot write files outside M6
- Cannot allow any MCP call to bypass trust checks

### Agent 4: Pipeline and Intent Specialist (M8, M9)

Builds: LangGraph pipeline (23-stage), FSI intent router.

Context files:
- 007-v2-tech-stack-decisions.md (M8, M9 sections)
- 007-v2-multi-agent-and-memory-architecture.md (multi-agent, context management)
- 007-v3-compliance-gap-designs.md (Gap 1: Reg BI triggers)

Rules enforced:
- Pipeline defined as LangGraph graph only
- Checkpointing to DynamoDB/PostgreSQL
- 3 HITL gates with tamper-proof approval tokens
- Token budgets enforced per stage
- Intent router uses LLM function calling with FSI taxonomy
- Confidence thresholds: >95% direct, 80-95% plan, <80% clarify
- All tool calls through M6 gateway only
- Cannot write files outside M8, M9
- Cannot call MCP servers directly

### Agent 5: Adapter Specialist (M11)

Builds: MCP server adapters for each vendor system.

Context files:
- 007-v2-tech-stack-decisions.md (M11 section)
- 007-fsi-enterprise-archetypes-technology-analysis.md (vendor APIs)

Rules enforced:
- Every adapter implements GET / + POST /tools/list + POST /tools/call
- Every tool has JSON Schema definition
- Authentication via environment variables only
- Per-vendor rate limiting
- Canonical error format
- Each adapter independently deployable
- Cannot write files outside M11
- Cannot hardcode credentials

### Agent 6: Compliance Gap Specialist (Gaps 1-7)

Builds: Reg BI generator, liability framework, WSP mapping, BSA/AML, ERISA, MNPI scan, cross-border.

Context files:
- 007-v3-compliance-gap-designs.md (ALL 7 gaps -- primary reference)
- 007-v2-multi-agent-and-memory-architecture.md (guardrails, specialists)
- REVIEW-v3-final-committee-assessment.md (remaining gaps)

Rules enforced:
- All compliance checks via OPA/Rego
- Reg BI triggers on recommendation events from specialists
- BSA/AML SAR alerts to compliance officer ONLY (anti-tipping-off)
- ERISA rules layer on top of archetype rules
- MNPI scan: Layer A <10ms, Layer B <100ms, Layer C <2s
- Cross-border: jurisdiction overlays on OPA bundles
- WSP annotations (wsp_section) in every Rego rule
- All compliance data in WORM
- Cannot use LLM for compliance decisions
- Cannot route SAR alerts to advisors

---

## Steering and Hooks Structure

### Steering Files

```
.kiro/steering/
  007-architecture.md          -- primary, always loaded for 007 files
  007-trust-layer.md           -- loaded for M1, M2, M4, M10 files
  007-schema.md                -- loaded for M3, M7 files
  007-gateway.md               -- loaded for M6 files
  007-pipeline.md              -- loaded for M8, M9 files
  007-adapters.md              -- loaded for M11 files
  007-compliance-gaps.md       -- loaded for compliance gap files
```

### Hooks

```
.kiro/hooks/
  007-architecture-alignment.kiro.hook   -- pre-write: check arch rules
  007-module-boundary.kiro.hook          -- pre-write: check file is in correct module
  007-quality-gate.kiro.hook             -- post-write: lint, types, docs
  007-no-credentials.kiro.hook           -- pre-write: block hardcoded secrets
  007-compliance-rules.kiro.hook         -- post-write: verify OPA rules have wsp_section
  007-integration-verify.kiro.hook       -- post-task: verify cross-module integration
```

---

## 4 Quality Gates

```
GATE 1: STEERING CHECK (automatic, pre-write)
  Does this code follow the architecture rules?
  Enforced by: Kiro hooks (pre-tool-use)

GATE 2: SPECIALIST REVIEW (automatic, post-write)
  Does this code meet domain standards?
  Enforced by: Kiro hooks (post-tool-use) + getDiagnostics

GATE 3: INTEGRATION TEST (automatic, post-task)
  Does this code work with existing modules?
  Enforced by: CI/CD pipeline (pytest + eval suite)

GATE 4: ARCHITECTURE REVIEW (human, per-phase)
  Does the completed phase match the v2/v3 design?
  Enforced by: human review at phase gates
```

---

## Build Sequence

```
PHASE 0 (Weeks 0-4): Setup
  Create all steering files and hooks
  Set up CI/CD with architecture gates
  Create module directory structure

PHASE 1 (Weeks 4-16): Foundation
  Trust Agent builds first (M1, M2/M4, M10)
  Schema Agent builds in parallel (M3)
  Gateway Agent builds after trust layer (M6)
  Compliance Agent adds provenance chain (Gap 2) and MNPI scan Layer A (Gap 6)

PHASE 2 (Weeks 12-28): MVP
  All 6 agents work in parallel within their boundaries
  Schema Agent: translators for SF, Orion, eMoney, Schwab
  Adapter Agent: MCP servers for above vendors
  Pipeline Agent: LangGraph pipeline + intent router
  Compliance Agent: Reg BI, WSP mapping, account types, MNPI Layers B+C
  Lighthouse deployment in draft mode

PHASE 3+ (Weeks 24+): Hardening
  Compliance Agent: BSA/AML, cross-border
  Adapter Agent: more vendor adapters
  All agents: production hardening
```

---

## Why This Works

1. No shortcuts. Hooks enforce architecture at write-time, not review-time. A specialist cannot write non-compliant code -- the hook blocks it.

2. Domain depth. Each specialist has deep context about its modules. It does not need to understand the whole system.

3. Boundary enforcement. Each specialist can only write in its module directory. Trust Agent cannot modify Pipeline. Adapter Agent cannot modify Gateway.

4. Incremental verification. Every file checked at write-time (Gate 1-2), every task at completion (Gate 3), every phase by human (Gate 4).

5. Architecture as code. The v2/v3 design documents ARE the context files loaded into every specialist session. The architecture IS the prompt. The code must match the design because the design is what the agent reads.

---

## OpenClaw Skill Mapping (for the runtime product)

The build agents produce code that becomes OpenClaw skills in the deployed product:

| Build Agent | Produces | Becomes OpenClaw Skill |
|-------------|----------|----------------------|
| Trust Agent | M1, M2/M4, M10 code | fsi-trust-layer skill |
| Schema Agent | M3, M7 code | fsi-schema skill |
| Gateway Agent | M6 code | fsi-gateway skill |
| Pipeline Agent | M8, M9 code | fsi-research skill (from 006, upgraded) |
| Adapter Agent | M11 code | One skill per vendor (fsi-orion, fsi-schwab, etc.) |
| Compliance Agent | Gap 1-7 code | fsi-compliance skill |

Each skill follows the OpenClaw SKILL.md pattern: YAML frontmatter (name, trigger keywords, requirements) + markdown instructions + bundled code/scripts.

The build agents are the builders. The OpenClaw skills are the product.


---

## Appendix: ASCII Visual Summary

```
THE BUILD ARCHITECTURE

                         YOU (Architect)
                          |
                          | specs, reviews, approves
                          |
                    ORCHESTRATOR (Kiro main agent)
                          |
                          | delegates to specialists
                          |
        +---------+-------+-------+---------+---------+
        |         |       |       |         |         |
        v         v       v       v         v         v
  +----------++-------++------++--------++--------++----------+
  |  TRUST   ||SCHEMA ||GATE- ||PIPELINE||ADAPTER ||COMPLIANCE|
  |  AGENT   ||AGENT  ||WAY   ||AGENT   ||AGENT   ||AGENT     |
  |          ||       ||AGENT ||        ||        ||          |
  | M1 Ident || M3 Reg|| M6 GW|| M8 Lang|| M11 MCP|| Gaps 1-7 |
  | M2 OPA   || M7 Xlt||      || M9 Intn|| servers|| Reg BI   |
  | M4 MNPI  ||       ||      ||        ||        || BSA/AML  |
  | M10 Audit||       ||      ||        ||        || ERISA    |
  +----------++-------++------++--------++--------++----------+


4 QUALITY GATES

  GATE 1          GATE 2            GATE 3           GATE 4
  STEERING        SPECIALIST        INTEGRATION      ARCHITECTURE
  CHECK           REVIEW            TEST             REVIEW
  (pre-write)     (post-write)      (post-task)      (per-phase)
  automatic       automatic         CI/CD            human
  |               |                 |                |
  v               v                 v                v
  WRITE           VERIFY            INTEGRATE        SHIP


BUILD SEQUENCE

  PHASE 0 (Wk 0-4): SETUP
    Create steering + hooks + CI/CD + directory structure

  PHASE 1 (Wk 4-16): FOUNDATION
    Wk 4-6   TRUST ---- M1 Identity
    Wk 4-7   SCHEMA --- M3 Canonical Schema
    Wk 6-10  TRUST ---- M2/M4 OPA Policy Engine
    Wk 6-8   TRUST ---- M10 Audit Logger (WORM)
    Wk 8-12  GATEWAY -- M6 Trust-Aware MCP Gateway
    Wk 8-12  COMPLIANCE Gap 2 Provenance Chain
    Wk 10-12 COMPLIANCE Gap 6 MNPI Scan Layer A
    Wk 12-14 ALL ------ "Trust Gate" demo

  PHASE 2 (Wk 12-28): MVP (all 6 agents parallel)
    Wk 12-16 SCHEMA --- M7 Translators (4 vendors)
    Wk 12-16 ADAPTER -- M11 Adapters (4 vendors)
    Wk 12-16 PIPELINE - M9 Intent Router
    Wk 14-20 PIPELINE - M8 LangGraph Pipeline
    Wk 14-20 COMPLIANCE Gap 1 Reg BI + Gap 3 WSP
    Wk 16-20 COMPLIANCE Gap 5 Account-Type + Gap 6 Layers B+C
    Wk 16-24 PIPELINE - Multi-agent (Strands + 2 specialists)
    Wk 22-28 ALL ------ Lighthouse (draft mode)

  PHASE 3+ (Wk 24+): HARDENING
    COMPLIANCE Gap 4 BSA/AML + Gap 7 Cross-Border
    ADAPTER -- more vendors
    ALL ------ SOC 2, production, 20-50 customers


BUILD AGENTS -> PRODUCT SKILLS

  +------------+------------------+--------------------+
  | Build Agent| Produces         | Becomes Skill      |
  +------------+------------------+--------------------+
  | Trust      | M1, M2/M4, M10   | fsi-trust-layer    |
  | Schema     | M3, M7           | fsi-schema          |
  | Gateway    | M6               | fsi-gateway         |
  | Pipeline   | M8, M9           | fsi-research        |
  | Adapter    | M11 (per vendor) | fsi-orion, fsi-schwab|
  | Compliance | Gaps 1-7         | fsi-compliance      |
  +------------+------------------+--------------------+


WHY THIS WORKS

  1. NO SHORTCUTS -- hooks enforce at WRITE-TIME, not review-time
  2. DOMAIN DEPTH -- each specialist knows its modules deeply
  3. BOUNDARY ENFORCEMENT -- agents cannot write outside their directory
  4. INCREMENTAL VERIFICATION -- every file, task, and phase is checked
  5. ARCHITECTURE AS CODE -- design docs ARE the context files
```
