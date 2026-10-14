# Agentforce + FSI Agent Projects

A progressive series of Salesforce Agentforce and FSI (Financial Services Industry) agent builds. Each numbered folder is an iteration that layers new capabilities, runtimes, or architectural patterns on top of the previous one.

## Projects

### `my-agent-project-001`
Hello World Agentforce starter. Bare SFDX scaffold, used to validate the toolchain and publish flow.

### `my-agent-project-002-fsi-wealth_advisor_agent`
Wealth advisor agent, **Option A (CRM-backed)**. 6 topics and 4 Apex actions over custom objects (`WA_Household__c`, `WA_Client__c`, `WA_Financial_Account__c`, `WA_Financial_Goal__c`, `WA_Meeting__c`). Client lookup, portfolio review, goal planning, meeting prep via SOQL.

### `my-agent-project-003-fsi-wealth_advisor_agent-datacloud`
Same wealth advisor agent, **Option B (Data Cloud-backed)**. Swaps SOQL for `ConnectApi.CdpQuery` against Data Cloud DLMs. Demonstrates the CRM vs Data Cloud grounding tradeoff on an identical agent spec.

### `my-agent-project-004-fsi-wealth_advisor_agent-phase1to5`
Production hardening of 003. Adds 4 topics, 3 new objects (transactions, referrals), MCP connectors, multi-channel deploy (Experience Cloud chat widget with CORS/CSP), audit logging, RBAC, RAG, and performance testing.

### `my-agent-project-005-v1-integrations-fsi-investment_research_agent`
Pivot to **Investment Research**. Cross-platform multi-agent system: Salesforce Agentforce orchestrator + AWS MCP servers + Strands agents + Langfuse governance. v1 is the initial cut — single research agent, chat panel wired to live AWS Lambdas, research panel rendering from static seed data.

### `my-agent-project-005-v2-integrations-fsi-investment_research_agent`
Same cross-platform foundation as v1, materially extended. v2 adds:
- **Separate IR Compliance Agent** (agent-to-agent) with `restricted_list`, `trading_window`, `mnpi_check`, `full_screening` topics.
- **MNPI enforcement layer** — `IR_MnpiGuard`, `IR_MnpiCheckAction`, PUBLIC/INTERNAL/CONFIDENTIAL/RESTRICTED classification; CONFIDENTIAL never crosses to AWS.
- **Bidirectional AWS→SF** via `IR_McpServerEndpoint` (`@RestResource /ir-mcp/*`) exposing CRM tools to Strands agents, with MNPI filtering on outbound holdings.
- **Shared `mcp_protocol.py`** across all three MCP Lambdas (SEC EDGAR, Market Data, News) for consistent `/tools/list` + `/tools/call` handling.
- **`IR_ResearchBriefAction`** orchestrator that chains 7 actions and persists to `IR_Research_Note__c`.
- **`IR_AgentApiProxy`**, **`IR_DataCloudAction`** (CdpQuery with SOQL fallback), **`IR_ExperienceCloudHelper`**, plus a reworked frontend (`researchApi.ts`, refreshed chat/company/header components) and an SSE proxy for streaming.

### `my-agent-project-006-v1-openclaw-salesforce-aws`
Full runtime replatform. **OpenClaw on AWS Bedrock AgentCore** replaces Agentforce as the agent runtime. AutoResearchClaw 23-stage research pipeline with 3 HITL gates, 3 MCP Lambdas (SEC EDGAR, Market Data, News), financial skills (DCF, comps, Monte Carlo, stress test), multi-channel delivery (Slack, Web, WhatsApp). Claude Sonnet 4.6 + Haiku 4.6 on Bedrock.

### `my-agent-project-007-fsi-interoperability`
The platform play. A 13-module FSI interoperability layer (M1-M13) with a trust-aware MCP gateway, deterministic OPA/Rego compliance (never LLM), canonical schema registry (18 FSI types), and 20 MCP adapters across 5 protocols. OpenClaw becomes channel-only; Managed Agents/Strands run the agents. Supports cloud, hybrid, and on-prem topologies via Helm values toggle.

## Progression

```
single agent (001)
  → data grounding options: CRM vs Data Cloud (002 → 003)
  → production features: MCP, multi-channel, audit, RBAC, RAG (004)
  → multi-agent + AWS integration (005)
  → full runtime swap to OpenClaw/Bedrock (006)
  → enterprise interoperability platform (007)
```

## Visual Progression

```
┌──────────────────────────────────────────────────────────────────┐
│  001 · my-agent-project-001                                      │
│  Hello World Agentforce                                          │
│                                                                  │
│     User ──▶ Agent ──▶ "hi"                                      │
│                                                                  │
│  Bare SFDX scaffold. Validates toolchain + publish flow.         │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  add domain + CRM grounding
┌──────────────────────────────────────────────────────────────────┐
│  002 · fsi-wealth_advisor_agent  (Option A — CRM)                │
│                                                                  │
│     User ──▶ Agent ──▶ Apex Action ──▶ SOQL ──▶ WA_*__c          │
│                                                                  │
│  6 topics · 4 actions · 5 custom objects                         │
│  (Household, Client, Account, Goal, Meeting)                     │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  swap grounding source
┌──────────────────────────────────────────────────────────────────┐
│  003 · fsi-wealth_advisor_agent-datacloud  (Option B — DC)       │
│                                                                  │
│     User ──▶ Agent ──▶ Apex ──▶ ConnectApi.CdpQuery ──▶ *__dlm   │
│                                                                  │
│  Same agent spec · CRM vs Data Cloud tradeoff study              │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  productionize
┌──────────────────────────────────────────────────────────────────┐
│  004 · fsi-wealth_advisor_agent-phase1to5                        │
│                                                                  │
│     User ──▶ Agent ──┬──▶ Apex ──▶ Data Cloud                    │
│     (Web/Mobile/     ├──▶ MCP connectors                         │
│      Exp. Cloud)     ├──▶ RAG                                    │
│                      └──▶ Audit log · RBAC                       │
│                                                                  │
│  +4 topics · +Transactions/Referrals · CORS/CSP · perf tests     │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  pivot to Investment Research · go multi-agent
┌──────────────────────────────────────────────────────────────────┐
│  005-v1 · integrations-fsi-investment_research_agent             │
│                                                                  │
│     Analyst ──▶ Agentforce Orchestrator ──┬──▶ SOQL              │
│                         │                  ├──▶ MCP Lambda ×3    │
│                         │                  │   (SEC, Mkt, News)  │
│                         └─────▶ Strands Agent ×2 (A2A)           │
│                                  (Financial, Sentiment)          │
│                         ──▶ Langfuse traces                      │
│                                                                  │
│  Chat: live Lambdas · Research panel: static seed                │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  harden · add compliance + MNPI
┌──────────────────────────────────────────────────────────────────┐
│  005-v2 · integrations-fsi-investment_research_agent             │
│                                                                  │
│     Analyst ──▶ IR Research Agent ◀──A2A──▶ IR Compliance Agent  │
│                    │                         (restricted list,   │
│                    │                          trading window,    │
│                    │                          MNPI check)        │
│                    ├──▶ MCP Lambda ×3 (shared mcp_protocol.py)   │
│                    ├──▶ Strands ×2 ──▶ IR_McpServerEndpoint      │
│                    │                    (AWS → SF, MNPI-filtered)│
│                    ├──▶ IR_ResearchBriefAction ──▶ Research_Note │
│                    └──▶ IR_MnpiGuard (PUB/INT/CONF/RESTRICTED)   │
│                                                                  │
│  Bidirectional · MNPI layer · frontend rework · SSE streaming    │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  full runtime replatform
┌──────────────────────────────────────────────────────────────────┐
│  006 · openclaw-salesforce-aws                                   │
│                                                                  │
│     Slack/Web/WhatsApp ──▶ OpenClaw Gateway (WebSocket)          │
│                                 │                                │
│                                 ▼  on AWS Bedrock AgentCore      │
│                         AutoResearchClaw Pipeline                │
│                         23 stages · 3 HITL gates                 │
│                         Sonnet 4.6 · Haiku 4.6                   │
│                                 │                                │
│                 ┌───────────────┼───────────────┐                │
│                 ▼               ▼               ▼                │
│            MCP Lambdas     Skills           Salesforce           │
│            (SEC, Mkt,      (DCF, comps,     (CRM data +          │
│             News)           Monte Carlo,     IR_Audit_Log__c)    │
│                             stress test)                         │
│                                                                  │
│  No Agentforce runtime · no Comprehend/FinBERT · Bedrock only    │
└──────────────────────────────────────────────────────────────────┘
                               │
                               ▼  platform / interoperability play
┌──────────────────────────────────────────────────────────────────┐
│  007 · fsi-interoperability                                      │
│                                                                  │
│   12+ Channels ──▶ OpenClaw (channel gateway ONLY)               │
│                         │                                        │
│                         ▼                                        │
│                 Supervisor + 5 Specialists                       │
│                 (Managed Agents / Strands)                       │
│                         │                                        │
│     ┌───────────────────┼───────────────────────┐                │
│     ▼                   ▼                       ▼                │
│   M1 Identity      M6 Trust-Aware        M3 Schema Registry      │
│   M2/M4 OPA ──────▶ MCP Gateway ◀────── (18 canonical types)     │
│   M10 Audit         (EVERY call)         M7 Translators          │
│   (Langfuse +             │                      │               │
│    WORM S3 +              ▼                      ▼               │
│    CRM)          M11 Adapters ×20        M13 FIX Bridge          │
│                  (REST · BLPAPI ·        (stateful,              │
│                   gRPC · SFTP)            StatefulSet+PV)        │
│                                                                  │
│  OPA/Rego only (never LLM) · MNPI filtered before prompt         │
│  Topologies: cloud / hybrid / on-prem (Helm values toggle)       │
└──────────────────────────────────────────────────────────────────┘
```

## Supporting Material

- `agent_structure_studies/` — Deep dives on Agentforce architecture (Atlas reasoning, Einstein Trust Layer, Data 360 grounding, deployment channels, memory/actions).
- `docs/` — Cross-cutting architecture comparisons (005 vs 006), Agentforce layer explanations, Kiro-to-Salesforce connection guide, roadmap.
- `.kiro/` — Steering rules per project (006 and 007 have strict non-negotiable architecture rules).
