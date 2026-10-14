# ARCH-09: Complete Module Map — All 13 Modules


> Date: April 14, 2026
> Category: ARCHITECTURE (product design)
> Predecessor: ARCH-03 (module architecture), ARCH-07 (tech stack), RES-08 (infrastructure research), IMPL-06 (blocker resolution)
> Purpose: Visual reference for all 13 modules, their sub-types, compliance sub-modules, and full call flow
> Updates: Incorporates M11 polyglot (IMPL-06 Blocker 2), M13 FIX Bridge, M3 18 types (Blocker 3), Claude Managed Agents runtime

---

## THE 13 MODULES — ARCHITECTURE DIAGRAM

```
                         USER
                          |
                   M12 OpenClaw (12+ channels: Slack, Teams, WhatsApp, Web)
                   + Claude Managed Agents (cloud) / Strands SDK (hybrid/on-prem)
                          |
                   M9 Intent Router (Haiku, LLM function calling, <500ms)
                          |
            +-------------+-------------+
            |             |             |
      Research      Client Service  Execution     5 Specialist Agents
      (LangGraph    (Strands/MA     (Strands/MA   + Compliance (OPA, NO LLM)
       Sonnet)       Haiku)          + StateMach)  + Onboarding (Haiku)
            |             |             |
            +-------------+-------------+
                          |
                   M6 MCP Gateway (Trust-Aware — THE CORE OF 007)
                     |       |       |       |
               M1 Identity  M2/M4 OPA  M10 Audit  M5 Config
                          |
                   M11 MCP Adapters (17+ systems, polyglot)
                   M13 FIX Bridge (stateful TCP sessions)
                          |
            +-------------+-------------+
            |             |             |
      Salesforce    Orion         Schwab        + Bloomberg, FactSet,
      FSC                                        Fidelity, Pershing,
                                                 Eze, SWIFT...
```

---

## MODULE DETAIL TABLE

| # | Module | Type | Language | Framework | Lines | What It Does |
|---|--------|------|----------|-----------|-------|-------------|
| M1 | Agent Identity | BUILD | Python | FastAPI + Keycloak | ~300 | Issues, verifies, revokes Agent Identity Documents (JWT with FSI claims) |
| M2 | Authority Policy | BUILD | Rego + Python | OPA + FastAPI | ~500 | Evaluates (identity, action, target, context) to ALLOW/DENY/ESCALATE |
| M3 | Canonical Schema | BUILD | YAML + Python | JSON Schema + Pydantic | ~1,700 | 18 FSI data types mapping 17 vendor models. Versioned (semver). |
| M4 | MNPI Policy | BUILD | Rego + Python | OPA + FastAPI | ~400 | Per-field data filtering by archetype, role, and jurisdiction |
| M5 | Enterprise Config | ADAPT | Python | Pydantic v2 | ~200 | Per-firm YAML config: archetype, vendors, compliance, jurisdiction |
| M6 | MCP Gateway | BUILD | Python | FastAPI middleware | ~600-1,200 | Central trust hub. Every MCP call passes through. Wires M1+M2+M4+M10. |
| M7 | Schema Translators | ADAPT | Python | Pydantic v2 | ~400-800 each | Vendor data to/from canonical types. One per vendor. |
| M8 | Pipeline Engine | ADAPT | Python | LangGraph | ~1,400 | 23-stage research pipeline. Checkpointed. 3 HITL gates. Map-reduce. |
| M9 | Intent Router | BUILD | Python | LLM function calling | ~300 | Natural language to structured FSI intent. Confidence thresholds. |
| M10 | Audit Logger | ADAPT | Python | FastAPI + Langfuse | ~200 | 3-tier: Langfuse + S3 Object Lock WORM + CRM. SHA-256. 6-year. |
| M11 | MCP Adapters | ADAPT | Polyglot | See sub-types below | varies | 17+ vendor wrappers across 5 protocol types |
| M12 | Agent Runtime | PLUG IN | Python | Managed Agents / Strands | 0 | Channel gateway + agent orchestration (plug into, not build) |
| M13 | FIX Bridge | BUILD | Python | QuickFIX + MCP | ~1,500-2,500 | Stateful FIX 4.2 TCP sessions. Specialist contractor. Phase 4. |


---

## M11 ADAPTER SUB-TYPES (polyglot)

All adapters implement the same MCP interface regardless of language: GET / (server info), POST /tools/list (available tools), POST /tools/call (execute tool). Each adapter is its own Docker container. M6 gateway talks MCP to all of them.

### M11-REST (TypeScript, MCP SDK)

| Adapter | Auth | Lines | Phase | Notes |
|---------|------|-------|-------|-------|
| Salesforce FSC | OAuth 2.0 | 400-600 | 2 | SOQL queries, Household mismatch |
| Orion | OAuth / Basic | 400-600 | 2 | Hierarchical data model, webhooks available |
| eMoney | OAuth 2.0 | 400-600 | 2 | Fidelity-owned, poorly documented |
| Schwab (REST) | OAuth 2.0 | 500-700 | 2 | Positions, balances, trade submission |
| Fidelity | OAuth 2.0 | 400-600 | 3 | 6-12 month vendor approval |
| Pershing | OAuth 2.0 | 400-600 | 3 | Integration Hub, BD custodian |
| Wealthbox | API key | 300-400 | 3 | CRM for small RIAs |
| Redtail | API key | 300-400 | 3 | CRM for small RIAs |
| Envestnet | OAuth 2.0 | 400-600 | 4 | Competitor risk (110K advisors) |
| ComplySci | API key | 300-400 | 4 | Personal trading compliance |
| SEC EDGAR | None (free) | 300-400 | 1 | 10 req/s rate limit, from 006 |
| Alpha Vantage | API key | 200-300 | 2 | Bloomberg fallback for market data |
| News API | API key | 200-300 | 2 | News scan for research pipeline |

### M11-BLPAPI (Python, blpapi SDK)

| Adapter | Auth | Lines | Phase | Notes |
|---------|------|-------|-------|-------|
| Bloomberg B-PIPE | License + cert | 600-800 | 4 | Binary protocol, subscription model, 10K+ fields, PrivateLink on AWS, $24K+/yr |

### M11-gRPC (Python, grpcio)

| Adapter | Auth | Lines | Phase | Notes |
|---------|------|-------|-------|-------|
| SS&C Eze (xAPI) | OAuth 2.0 | 400-600 | 4 | Proto file definitions, hedge fund OMS/EMS |

### M11-SFTP (Python, paramiko)

| Adapter | Auth | Lines | Phase | Notes |
|---------|------|-------|-------|-------|
| Schwab daily files | SFTP credentials | 300-400 | 2 | CSV/fixed-width, cost basis source of truth |
| Fidelity daily files | SFTP credentials | 300-400 | 3 | Batch reconciliation |

### M11-MCP-NATIVE (passthrough via M6)

| Adapter | Auth | Lines | Phase | Notes |
|---------|------|-------|-------|-------|
| FactSet | OAuth 2.0 | ~0 (passthrough) | 4 | FactSet's own production MCP server. Routes through M6 for trust/MNPI. Validates 007 thesis. |


---

## M13: FIX BRIDGE — DETAILED

Separate module from M11 due to fundamental architectural differences: stateful TCP (not stateless HTTP), persistent sessions (not request/response), sequence number tracking, and specialist contractor requirement.

```
FIX BRIDGE ARCHITECTURE:

  ┌──────────────────────────────────────────────────────────────────┐
  |  M13 FIX Bridge                                                  |
  |                                                                  |
  |  ┌────────────────────────────────────────────────────────────┐ |
  |  | QuickFIX Engine (Python or Java)                           | |
  |  |                                                            | |
  |  | Session Layer:                                             | |
  |  |   Logon, heartbeat, sequence numbers, gap-fill recovery    | |
  |  |   Persistent TCP connection to broker/exchange             | |
  |  |                                                            | |
  |  | Application Layer:                                         | |
  |  |   NewOrderSingle (D)     - submit order                   | |
  |  |   ExecutionReport (8)    - fill/reject/ack                 | |
  |  |   OrderCancelRequest (F) - cancel order                    | |
  |  |   Allocation (J)         - post-trade allocation           | |
  |  └────────────────────────────────────────────────────────────┘ |
  |                                                                  |
  |  MCP Wrapper:                                                    |
  |    Exposes FIX operations as MCP tools                           |
  |    M6 gateway calls M13 like any other adapter                   |
  |    Trust/MNPI/audit still enforced                               |
  |                                                                  |
  |  State Persistence:                                              |
  |    Cloud: DynamoDB (session state) + S3 (message store)          |
  |    Hybrid: Local PostgreSQL + PersistentVolume                   |
  |    Kubernetes: StatefulSet (not Deployment)                      |
  |    Pod restart: reads last sequence from store, gap-fill works   |
  |                                                                  |
  |  1,500-2,500 lines. FIX specialist contractor. Phase 4.          |
  |  14 weeks minimum. Budget $168-280K.                             |
  └──────────────────────────────────────────────────────────────────┘
```

---

## COMPLIANCE SUB-MODULES (~7,000 lines total)

These are sub-modules integrated into M2/M4/M6/M10, not standalone services.

| Gap | Sub-module of | Lines | Phase | What It Does |
|-----|--------------|-------|-------|-------------|
| 1. Reg BI Doc Generator | M10 | ~1,100 | 2 | Auto-generates structured Reg BI documentation for every recommendation |
| 2. Liability Provenance | M6 + M10 | ~700 | 1 | Per-stage SHA-256 hash chain, warranty boundary, error attribution |
| 3. WSP-to-YAML Mapping | M2 | ~1,000 | 2 | Bidirectional cross-reference: human WSP to OPA/Rego rules |
| 4. BSA/AML Monitoring | M2 | ~1,100 | 3 | CTR ($10K+), SAR patterns, sanctions, anti-tipping-off |
| 5. ERISA Account-Type | M2 | ~950 | 2-3 | 16 account types, per-type OPA rules, tax impact calculator |
| 6. MNPI Leakage Scan | M6 | ~550 | 1-2 | 3-layer output guardrail: regex (<10ms) + NER (<100ms) + Haiku (<2s) |
| 7. Cross-Border | M2 | ~1,600 | 3-5 | 5 jurisdiction overlays (US/EU/UK/SG/HK), GDPR, MiFID II, DORA |


---

## THE 5 SPECIALIST AGENTS

```
SUPERVISOR (Claude Managed Agents / Strands SDK)
  Model: Haiku (<500ms routing decisions)
  Pattern: Constrained plan-and-execute
  Routes to correct specialist based on M9 intent classification
       |
       +-- RESEARCH SPECIALIST
       |     Framework: LangGraph (stateful graph with checkpointing)
       |     Model: Sonnet (deep reasoning, large context)
       |     Pipeline: 23 stages, 3 HITL gates, map-reduce synthesis
       |     Tools: SEC EDGAR, Bloomberg/FactSet, news APIs (via M6)
       |     Output: Structured ResearchBrief with source attribution
       |     Timeout: 20 min max. Async (supervisor polls for completion).
       |
       +-- CLIENT SERVICE SPECIALIST
       |     Framework: Strands / Managed Agents
       |     Model: Haiku (<3s conversational response)
       |     Memory: Full 6-layer access (L1-L5), MNPI-filtered
       |     Tools: CRM, Portfolio, Planning systems (via M6)
       |     Output: Meeting prep, portfolio review, client summaries
       |     Cross-channel: WhatsApp session continues on Slack
       |
       +-- COMPLIANCE SPECIALIST
       |     Framework: OPA/Rego (NOT an LLM agent)
       |     Model: NONE — deterministic rule evaluation
       |     Interface: MCP tool called by other specialists
       |     Checks: Restricted list, concentration, suitability,
       |             Chinese wall, pod isolation, MNPI filtering
       |     Accuracy: 99.9% (limited only by rule currency)
       |     Why no LLM: "How do you ensure compliance checks are
       |     correct?" "Deterministic rule evaluation, not probabilistic."
       |
       +-- EXECUTION SPECIALIST
       |     Framework: Strands / Managed Agents + finite state machine
       |     Model: Haiku (order preparation)
       |     State machine: DRAFT -> COMPLIANCE_CHECK -> PENDING_APPROVAL
       |       -> APPROVED -> SUBMITTED -> CONFIRMED -> PENDING_SETTLEMENT
       |       -> SETTLED (or SETTLEMENT_FAILED -> ESCALATED)
       |     HITL: MANDATORY before any order submission. No autonomous trades.
       |     Approval token: SHA-256(gate_id + approver_id + timestamp)
       |     Timeout: 24 hours without approval = auto-cancel
       |
       +-- ONBOARDING SPECIALIST
             Framework: Workflow engine (Python state machine)
             Model: Haiku (conversational form filling, doc extraction)
             Steps: Collect info -> KYC -> sanctions -> risk profile
               -> account opening -> DocuSign -> compliance review (HITL)
             Multi-session: client may complete over days
             BSA/AML: KYC feeds initial CDD record for ongoing monitoring
```

---

## 6-LAYER MEMORY ARCHITECTURE

```
  L6: COMPLIANCE MEMORY    S3 Object Lock (WORM)     6+ years    Immutable audit trail
  L5: PROCEDURAL MEMORY    File-based JSON (S3)      Permanent   Advisor workflow preferences
  L4: SEMANTIC MEMORY      pgvector / Pinecone       Permanent   Learned facts about clients
  L3: EPISODIC MEMORY      DynamoDB + vector          2 years     Past interactions + outcomes
  L2: SHORT-TERM MEMORY    DynamoDB                   7 days      Recent interactions (summarized)
  L1: WORKING MEMORY       Redis                      8hr TTL     Current conversation (cross-channel)
```

All memory MNPI-filtered on retrieval via M4 OPA rules. Memory entries tagged with archetype/role. Tier 3 advisor sees own clients only. Tier 5 HF PM sees own pod only. Tier 1 bank: Chinese wall enforced across memory boundaries.


---

## FULL CALL FLOW — ONE REQUEST THROUGH ALL MODULES

"Prep me for my meeting with Henderson tomorrow"

```
  M12 <-- Sarah types on Slack (OpenClaw receives)
   |
   +-> M1: Verify AID (sarah.chen, advisor, tier3, acme_wm)
   |
   +-> M9: Classify intent -> client.prep_meeting(client="Henderson")
   |       (Haiku via Managed Agents, <500ms)
   |
   +-> M2: Authority check -> Is Henderson Sarah's client? -> ALLOW
   |
   +-> CLIENT SERVICE SPECIALIST (via Managed Agents)
   |    |
   |    +-> M6 -> M11-REST (Salesforce) -> M7 -> canonical Client
   |    |   +-> M4: strip SSN, DOB (tier3 MNPI rules)
   |    |   +-> M10: log data access to WORM (SHA-256)
   |    |
   |    +-> M6 -> M11-REST (Orion) -> M7 -> canonical Holding[]
   |    |   +-> M4: keep full holdings (tier3 retail advisor)
   |    |   +-> M10: log
   |    |
   |    +-> M6 -> M11-REST (eMoney) -> M7 -> canonical PlanSummary
   |    |   +-> M4: summary only, no raw plan to LLM
   |    |   +-> M10: log
   |    |
   |    +-> LLM (Haiku): synthesize meeting prep brief
   |    |   Input: Client + Holdings + PlanSummary (all MNPI-filtered)
   |    |
   |    +-> GAP 6: MNPI Leakage Scan
   |    |   Layer A: regex (<10ms) -> PASS
   |    |   (Layers B+C only if A flags)
   |    |
   |    +-> Principal Review (if BD, FINRA 2210)
   |        RIA: deliver directly
   |        BD: queue for principal approval first
   |
   +-> M10: Log complete journey
   |   Provenance chain: M1 -> M9 -> M2 -> M6 -> M11 -> M7 -> M4 -> LLM -> M10
   |   Per-stage SHA-256 hash. Trace ID links everything.
   |
   +-> M12: Deliver brief to Sarah on Slack

  RESULT: Complete meeting prep brief in <60 seconds.
  All 13 modules touched. Full audit trail. MNPI filtered. Compliant.
```

---

## DEPENDENCY MATRIX

Who calls whom (row calls column):

```
          M1  M2  M3  M4  M5  M6  M7  M8  M9  M10 M11 M12 M13
  M1       .   .   .   .   .   .   .   .   .   .   .   .   .
  M2       *   .   .   .   *   .   .   .   .   .   .   .   .
  M3       .   .   .   .   .   .   .   .   .   .   .   .   .
  M4       *   .   .   .   *   .   .   .   .   .   .   .   .
  M5       .   .   .   .   .   .   .   .   .   .   .   .   .
  M6       *   *   .   *   .   .   .   .   .   *   *   .   *
  M7       .   .   *   .   .   .   .   .   .   .   .   .   .
  M8       .   *   .   .   *   *   .   .   .   *   .   .   .
  M9       *   .   .   .   *   .   .   .   .   .   .   .   .
  M10      *   .   .   .   .   .   .   .   .   .   .   .   .
  M11      .   .   .   .   .   .   *   .   .   .   .   .   .
  M12      .   .   .   .   .   *   .   *   *   .   .   .   .
  M13      .   .   .   .   .   .   .   .   .   .   .   .   .
```

Key observations:
- M1 (Identity) called by 5 modules — foundational
- M5 (Config) called by 4 modules — enterprise DNA
- M6 (MCP Gateway) calls 6 modules — central hub (including M13)
- M3 and M5 call nothing — pure data
- M12 only calls M6, M8, M9 — clean interface
- M13 is called only by M6 — isolated stateful bridge

---

## BUILD ORDER

```
Phase 0: M3 (Schema, 18 types) + M5 (Config)
         Pure data, no deps. Compliance SME co-design.

Phase 1: M1 (Identity) + M10 (Audit) + M2/M4 (Policy)
         Trust layer. THE MOAT. + M6 (Gateway).
         WEDGE PRODUCT ships here (Week 14-18).

Phase 2: M7 (Translators) + M11-REST (Adapters) + M9 (Intent) + M8 (Pipeline)
         Intelligence layer. RIA lighthouse (Week 28-36).

Phase 3: Smarsh + Execution Specialist + Onboarding Specialist
         Production hardening. BD onboarding.

Phase 4: M11-BLPAPI (Bloomberg) + M11-gRPC (Eze) + M13 (FIX Bridge)
         Tier 2/5 expansion. Hybrid topology.

Phase 5: DEFERRED (Tier 1 + Global)
```

---

*ARCH-09 — Project 007 FSI Interoperability Platform*
*Complete Module Map — All 13 Modules*


---

## SUMMARY TABLES

### All 13 Modules

| # | Module | Type | Language | Framework | Lines | Phase | What It Does |
|---|--------|------|----------|-----------|-------|-------|-------------|
| M1 | Agent Identity | BUILD | Python | FastAPI + Keycloak | ~300 | 1 | Issues, verifies, revokes AIDs (JWT with FSI claims: LEI, CRD, archetype, role) |
| M2 | Authority Policy | BUILD | Rego + Python | OPA + FastAPI | ~500 | 1 | 2,100+ Rego rules. ALLOW/DENY/ESCALATE. Deterministic, not LLM. 99.9% accurate. |
| M3 | Canonical Schema | BUILD | YAML + Python | JSON Schema + Pydantic | ~1,700 | 0-1 | 18 FSI data types mapping 17 vendor models. Household container model. Versioned. |
| M4 | MNPI Policy | BUILD | Rego + Python | OPA + FastAPI | ~400 | 1 | Per-field data filtering by archetype, role, jurisdiction. Chinese walls. Pod isolation. |
| M5 | Enterprise Config | ADAPT | Python | Pydantic v2 | ~200 | 0-1 | Per-firm YAML: archetype, vendors, compliance regime, jurisdiction, channels, MNPI rules |
| M6 | MCP Gateway | BUILD | Python | FastAPI middleware | ~600-1,200 | 1 | THE CORE. Every MCP call passes through. Wires M1->M2->M4->M10. Circuit breakers. |
| M7 | Schema Translators | ADAPT | Python | Pydantic v2 | ~400-800 ea | 2 | Vendor to canonical. One per vendor. Cost basis normalization. Household mapping. |
| M8 | Pipeline Engine | ADAPT | Python | LangGraph | ~1,400 | 2 | 23-stage research pipeline. Checkpointed. 3 HITL gates. Map-reduce. Token budgets. |
| M9 | Intent Router | BUILD | Python | LLM function calling | ~300 | 2 | NL to structured FSI intent. >95% direct, 80-95% LLM plan, <80% clarify. |
| M10 | Audit Logger | ADAPT | Python | FastAPI + Langfuse | ~200 | 1 | 3-tier: Langfuse + S3 Object Lock WORM + CRM. SHA-256. 6-year. Fail-closed. |
| M11 | MCP Adapters | ADAPT | Polyglot | See sub-types | varies | 1-4 | 17+ vendor wrappers. 5 protocol types. Each = own Docker container. |
| M12 | Agent Runtime | PLUG IN | Python | Managed Agents / Strands | 0 | 2 | OpenClaw channels + supervisor + 5 specialists. Runtime is config toggle. |
| M13 | FIX Bridge | BUILD | Python | QuickFIX + MCP | ~1,500-2,500 | 4 | Stateful FIX 4.2 TCP. Sequence tracking. StatefulSet. Specialist contractor. |

### M11 Adapter Sub-Types

| Sub-Type | Language | Framework | Adapters | Lines Each | Phase |
|----------|----------|-----------|----------|-----------|-------|
| M11-REST | TypeScript | MCP SDK | SF FSC, Orion, eMoney, Schwab, Fidelity, Pershing, Wealthbox, Redtail, Envestnet, ComplySci, EDGAR, Alpha Vantage, News | 200-700 | 1-4 |
| M11-BLPAPI | Python | blpapi SDK + MCP | Bloomberg B-PIPE | 600-800 | 4 |
| M11-gRPC | Python | grpcio + MCP | SS&C Eze (xAPI) | 400-600 | 4 |
| M11-SFTP | Python | paramiko | Schwab daily files, Fidelity daily files | 300-400 | 2-3 |
| M11-MCP-NATIVE | Passthrough | Via M6 gateway | FactSet (own MCP server) | ~0 | 4 |

### Compliance Sub-Modules (~7,000 lines total)

| Gap | Parent Module | Lines | Phase | What |
|-----|-------------|-------|-------|------|
| 1. Reg BI Doc Generator | M10 | ~1,100 | 2 | Auto-generates Reg BI docs for every recommendation |
| 2. Liability Provenance | M6 + M10 | ~700 | 1 | Per-stage SHA-256 chain, warranty boundary, error attribution |
| 3. WSP-to-YAML Mapping | M2 | ~1,000 | 2 | Bidirectional: human WSP to OPA/Rego rules |
| 4. BSA/AML Monitoring | M2 | ~1,100 | 3 | CTR ($10K+), SAR patterns, sanctions, anti-tipping-off |
| 5. ERISA Account-Type | M2 | ~950 | 2-3 | 16 account types, per-type OPA rules, tax impact |
| 6. MNPI Leakage Scan | M6 | ~550 | 1-2 | 3-layer: regex (<10ms), NER (<100ms), Haiku (<2s) |
| 7. Cross-Border | M2 | ~1,600 | 3-5 | US/EU/UK/SG/HK overlays, GDPR, MiFID II, DORA |

### Specialist Agents

| Specialist | Framework | LLM | Latency | Key Feature |
|-----------|-----------|-----|---------|-------------|
| Supervisor | Managed Agents / Strands | Haiku | <500ms | Constrained plan-and-execute routing |
| Research | LangGraph | Sonnet | <20 min | 23-stage pipeline, 3 HITL gates, map-reduce |
| Client Service | Managed Agents / Strands | Haiku | <3s | Cross-channel memory (L1-L5), meeting prep |
| Compliance | OPA/Rego | NONE | <10ms | Deterministic. Called as tool. Not an LLM agent. |
| Execution | Managed Agents / Strands + State Machine | Haiku | varies | HITL mandatory. Zero autonomous trades. T+1 tracking. |
| Onboarding | Workflow Engine | Haiku | multi-day | KYC, sanctions, risk, account open, DocuSign |