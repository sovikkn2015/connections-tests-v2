# Project 007 v2: Findings Summary

> Date: April 12, 2026
> Score: 5.1 -> 7.5/10. Verdict: GO FOR PHASE 0.

---

## The Score Journey

| Area | v1 | v2 | Delta |
|------|-----|-----|-------|
| Architecture and Tech Stack | 6.8 | 8.4 | +1.6 |
| Compliance and Regulatory | 5.0 | 6.6 | +1.6 |
| Commercial Viability | 5.3 | 6.7 | +1.4 |
| Agentic AI Design Patterns | 4.0 | 8.3 | +4.3 |
| Implementation Feasibility | 4.2 | 7.1 | +2.9 |
| OVERALL | 5.1 | 7.5 | +2.4 |

---

## The 10 Required Actions

| # | Action | Status |
|---|--------|--------|
| 1 | Hire compliance SME | FULLY ADDRESSED |
| 2 | Start vendor API applications | FULLY ADDRESSED |
| 3 | Tech stack decision document | FULLY ADDRESSED |
| 4 | Multi-agent architecture | FULLY ADDRESSED |
| 5 | Memory architecture | FULLY ADDRESSED |
| 6 | WORM-compliant audit storage | FULLY ADDRESSED |
| 7 | Canonical schema design | PARTIAL |
| 8 | Evaluation framework | FULLY ADDRESSED |
| 9 | Pricing and GTM strategy | FULLY ADDRESSED |
| 10 | Cross-border regulatory support | PARTIAL |

8 fully addressed. 2 partial. 0 not addressed.

---

## Key Finding 1: Multi-Agent Was the Biggest Win (+4.3)

v1: Single agent with tools. v2: Supervisor + 5 specialists.

- Supervisor: Strands SDK, Haiku, less than 500ms routing
- Research: LangGraph, Sonnet, 23-stage, 20min max
- Client Service: Strands, Haiku, less than 3s, memory-enabled
- Compliance: OPA/Rego, NO LLM, deterministic
- Execution: Strands + state machine, mandatory HITL
- Onboarding: Workflow engine, multi-session

Compliance is NOT an LLM agent. It is OPA. This is the architecturally correct answer for regulators.

---

## Key Finding 2: Tech Stack Is Now Explicit

Every module has language, framework, alternatives considered, and cloud-agnostic path.

| Module | Language | Framework | Key Decision |
|--------|----------|-----------|-------------|
| M1 Identity | Python | FastAPI + Keycloak | Custom AID on Keycloak |
| M2/M4 Policy | Rego + Python | OPA + FastAPI | Merged into one OPA |
| M3 Schema | Python | JSON Schema | Semver, break detection |
| M5 Config | Python | Pydantic | Hot reload, Vault |
| M6 Gateway | Python | FastAPI middleware | App-level, not Envoy |
| M7 Translators | Python | Pydantic | Hand-written + codegen |
| M8 Pipeline | Python | LangGraph | Replaces 006 custom |
| M9 Intent | Python | LLM function calling | Confidence thresholds |
| M10 Audit | Python | FastAPI | 3-tier WORM |
| M11 Adapters | TypeScript | MCP SDK | Per-vendor containers |
| M12 Runtime | Python | Strands SDK | Multi-agent on AgentCore |

3 topologies: Cloud ($800-$8K/mo), Hybrid (trust on-prem), On-Premise (self-hosted LLM).

LLM abstracted: Bedrock, Azure OpenAI, GCP Vertex AI, self-hosted, LiteLLM.

---

## Key Finding 3: Memory Went From Zero to 6 Layers

| Layer | Store | Retention | Purpose |
|-------|-------|-----------|---------|
| L6 Compliance | S3 Object Lock WORM | 6+ years | Regulatory audit |
| L5 Procedural | File JSON | Permanent | Advisor preferences |
| L4 Semantic | pgvector/Pinecone | Permanent | Client facts |
| L3 Episodic | DynamoDB + vector | 2 years | Past interactions |
| L2 Short-Term | DynamoDB/PostgreSQL | 7 days | Recent interactions |
| L1 Working | Redis | 8hr session | Current conversation |

All layers MNPI-tagged. Retrieval passes through OPA. Cross-channel persistence.

---

## Key Finding 4: Audit Is Now WORM-Compliant

- Tier 1 Operational (Langfuse): 90 days. NOT regulatory record.
- Tier 2 Compliance (S3 Object Lock): Immutable. 6 years. SHA-256. THIS is the record of truth.
- Tier 3 Business (Salesforce CRM): Advisor-accessible. Not regulatory record.

Fail-closed: if audit write fails, entire request fails.

---

## Key Finding 5: Eval Went From 150 to 1,230+ Tests

| Dimension | Count |
|-----------|-------|
| Functional (5 archetypes) | 750 |
| Adversarial compliance | 200 |
| Schema reconciliation | 100/translator |
| Multi-agent routing | 200 |
| End-to-end journeys | 30 |
| Performance | 50 |
| TOTAL | 1,230+ |

---

## Key Finding 6: Implementation Plan Is Now Honest

| Phase | What | Weeks | Cost |
|-------|------|-------|------|
| 0 | Prerequisites | 0-4 | $40-70K |
| 1 | Foundation | 4-16 | $180-280K |
| 2 | Tier 3/4 MVP | 12-28 | $350-520K |
| 3 | Production hardening | 24-36 | $480-720K |
| 4 | Tier 2/5 expansion | 36-52 | $600-900K |
| 5 | Tier 1 + global | 52-78 | $900K-1.4M |
| TOTAL | 18 months | 78 weeks | $2.6-3.9M |

Team: 3 to 12. Break-even: Month 10-14. 15-risk register. 13-vendor tracker.

---

## Key Finding 7: Compliance Is Still the Weakest (6.6/10)

Strong: WORM audit, MNPI enforcement, HITL gates, deterministic OPA, fail-closed.

Still missing: Reg BI documentation generator, liability framework, WSP-to-YAML mapping, BSA/AML monitoring, ERISA awareness, MNPI leakage scan design, cross-border architecture.

---

## Key Finding 8: Competitive Window Is 18-24 Months

Envestnet ($1B R&D, Tier 3/4), Salesforce Agentforce (CRM-native), BlackRock Aladdin (Tier 2/5) are all building AI. 007's moat is cross-archetype compliance across all 5 tiers. Window closes when incumbents add cross-system interoperability.

---

## 5 Things Still Needed Before Code

1. Reg BI documentation generator — structured output, not logging. BD deployment blocker.
2. MNPI leakage scan — output guardrail detecting LLM inference of filtered data.
3. Canonical schema fields — Client + Holding with field-level semantics. Validate against real APIs.
4. Liability framework — matrix, warranty boundary, E&O insurance. GC blocker.
5. Technical spikes — LangGraph checkpointing, OPA at scale, Redis cross-channel, LLM abstraction. 1 week each.

---

## The Verdict

v1: CONDITIONAL GO (5.1/10). "Vision exceptional. Specification not."

v2: GO FOR PHASE 0 (7.5/10). "Architecture is now buildable. Start immediately."

What changed: single to multi-agent (+4.3), no memory to 6-layer (+5.5), no tech stack to fully specified (+4.5), no WORM to three-tier (+3.5), 150 to 1,230+ tests (+5.0), optimistic to honest timeline (+4.0).

What didn't change enough: compliance depth (6.6, should be highest), cross-border (US-centric), liability (absent).

"Build the signals first. The trains are now designed. Time to lay track."
