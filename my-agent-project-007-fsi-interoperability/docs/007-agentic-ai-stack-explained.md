# 007 Agentic AI Stack — Explained

> For anyone who wants to understand how the AI agent system actually works.

---

## What "Agentic AI" Means in 007

An AI agent is software that can: (1) understand what you want, (2) decide which tools to use, (3) use those tools, (4) combine the results, and (5) give you an answer. It's not a chatbot — it takes actions across multiple systems.

When an advisor says "Prep me for Henderson tomorrow," the agent figures out this means "pull client profile + holdings + financial plan + compliance checks," decides which systems to query, calls those systems through the trust layer, combines the data into a meeting brief, and delivers it back.

---

## The Agentic Stack — 5 Layers

```
LAYER 1: LLM (The Brain)
  Claude Sonnet (Bedrock) — deep reasoning, research ($$)
  Claude Haiku (Bedrock) — fast routing, conversation ($)
  NOT used for compliance (OPA/Rego only)
  Abstracted: swap for Azure OpenAI, GCP Vertex, or self-hosted vLLM

LAYER 2: AGENT ORCHESTRATION (The Coordinator)
  Supervisor (Haiku, <500ms routing)
  Constrained plan-and-execute pattern
  Runtime: Managed Agents (cloud Phase 2) / Strands SDK (hybrid) / FastAPI (current)

LAYER 3: SPECIALISTS (The Workers) — 5 agents
  Research:       LangGraph + Sonnet, 23 stages, 3 HITL gates, 20 min max
  Client Service: Strands + Haiku, <3s, cross-channel memory
  Compliance:     OPA/Rego ONLY, NO LLM, deterministic, <10ms
  Execution:      State machine + Haiku, mandatory HITL, zero autonomous trades
  Onboarding:     Workflow engine + Haiku, multi-session, KYC/sanctions/DocuSign

LAYER 4: TOOLS (What agents use)
  20 MCP adapters across 5 protocols (REST, BLPAPI, gRPC, SFTP, MCP-native)
  Every tool call goes through M6 trust gateway — agents never call vendors directly

LAYER 5: MEMORY (What agents remember)
  L1 Working (Redis, 8hr) → L2 Short-term (DynamoDB, 7d) → L3 Episodic (2yr)
  → L4 Semantic (pgvector, permanent) → L5 Procedural (S3, permanent)
  → L6 Compliance (S3 WORM, 6+ years, immutable)
  All MNPI-filtered on retrieval via M4
```

---

## Key Frameworks

| Framework | What | Where | Why |
|-----------|------|-------|-----|
| LangGraph | Stateful graph engine | Research (M8) | 23-stage pipeline, checkpointing, HITL, map-reduce |
| Managed Agents | Bedrock agent orchestration | Supervisor (cloud) | Designed, Phase 2 wiring |
| Strands SDK | Open-source agent framework | Supervisor (hybrid) | Self-hosted alternative |
| OPA/Rego | Policy-as-code | Compliance (M2/M4) | Deterministic, auditable, 2,100+ rules |
| MCP | Model Context Protocol | All 20 adapters | Standard agent-to-tool protocol |
| FastAPI | Python async web framework | All backend modules | REST APIs between modules |

---

## Request Flow

```
"Prep me for Henderson tomorrow"
    |
    v
M9 Intent Router (Haiku, <500ms)
  → client.prep_meeting, confidence 0.97, route: client_service
    |
    v
Supervisor → CLIENT SERVICE SPECIALIST
    |
    v
Specialist needs 3 tools: Salesforce + Orion + eMoney
    |
    v
Each tool call through M6 TRUST GATEWAY:
  M1 verify → M2 authority (OPA) → M4 MNPI filter → route → M10 audit
    |
    v
Specialist gets MNPI-filtered data from all 3 systems
    |
    v
Haiku synthesizes meeting prep (LLM never sees SSN — already stripped)
    |
    v
Gap 6 Leakage Scan (regex + NER + classifier)
    |
    v
If BD: Principal Review Queue (FINRA 2210)
If RIA: deliver directly
    |
    v
M10 logs complete journey (SHA-256 provenance chain, 3-tier WORM)
    |
    v
Advisor gets meeting prep — 60 seconds, 5 systems, all compliant
```

---

*Project 007 FSI Interoperability Platform*
