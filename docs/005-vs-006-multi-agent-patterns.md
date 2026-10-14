# 005 vs 006: Multi-Agent Patterns

> Date: April 8, 2026
> Scope: How agents communicate in each architecture

---

## Key Finding

Neither 005 nor 006 uses A2A (Agent-to-Agent protocol). Both are hub-and-spoke with tool invocation over HTTP or in-process calls — not agent discovery, capability negotiation, or bidirectional task management.

- 005 is multi-agent at the infrastructure level — separate Lambda functions, separate runtimes, HTTP between them
- 006 is multi-agent at the pipeline level — same process, same LLM, different personas orchestrated by AutoResearchClaw

---

## 005: Multi-Agent — Two Runtimes, Three Agents, HTTP Boundaries

```
  User (Web Chat / Slack / Agent API)
         │
         ▼
┌─────────────────────────────────────────────────────────────┐
│  SALESFORCE ORG                                              │
│                                                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │  AGENTFORCE (Agent 1 — Orchestrator)                   │  │
│  │  Runtime: Atlas Reasoning Engine                       │  │
│  │  Language: Apex                                        │  │
│  │  Trust: Einstein Trust Layer (native)                  │  │
│  │                                                        │  │
│  │  Intent Router → Topics → Apex Actions                 │  │
│  │       │              │              │                   │  │
│  │       ▼              ▼              ▼                   │  │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────────────────┐  │  │
│  │  │CRM      │  │MCP       │  │Strands Callout       │  │  │
│  │  │Actions  │  │Callout   │  │Actions               │  │  │
│  │  │(Apex)   │  │Actions   │  │(Apex → HTTP → AWS)   │  │  │
│  │  │         │  │(Apex)    │  │                       │  │  │
│  │  │SOQL     │  │          │  │IR_FinancialAnalysis   │  │  │
│  │  │CRUD     │  │Named     │  │IR_SentimentAnalysis   │  │  │
│  │  │FLS      │  │Credential│  │                       │  │  │
│  │  └────┬────┘  └────┬─────┘  └───────────┬───────────┘  │  │
│  │       │             │                    │              │  │
│  └───────┼─────────────┼────────────────────┼──────────────┘  │
│          │             │                    │                  │
│          ▼             │                    │                  │
│  ┌──────────────┐      │                    │                  │
│  │ CRM Data     │      │                    │                  │
│  │ IR_Company   │      │                    │                  │
│  │ IR_Coverage  │      │                    │                  │
│  │ IR_Audit_Log │      │                    │                  │
│  │ Holdings     │      │                    │                  │
│  └──────────────┘      │                    │                  │
└────────────────────────┼────────────────────┼──────────────────┘
                         │                    │
            ─ ─ ─ ─ ─ ─ ┼ ─ ─ ─ ─ ─ ─ ─ ─ ─┼─ ─ ─ ─ ─ ─ ─
            HTTP / Named │ Credential         │ HTTP / API Key
            ─ ─ ─ ─ ─ ─ ┼ ─ ─ ─ ─ ─ ─ ─ ─ ─┼─ ─ ─ ─ ─ ─ ─
                         │                    │
                         ▼                    ▼
┌─────────────────────────────────────────────────────────────┐
│  AWS                                                         │
│                                                              │
│  ┌──────────────────────┐    ┌────────────────────────────┐ │
│  │ MCP Servers (Lambda)  │    │ Strands Agents (Lambda)    │ │
│  │                       │    │                            │ │
│  │ ┌──────────────────┐ │    │ ┌────────────────────────┐ │ │
│  │ │ SEC EDGAR        │ │    │ │ Agent 2: Financial     │ │ │
│  │ │ get_10k, get_10q │ │    │ │ Analysis Agent         │ │ │
│  │ └──────────────────┘ │    │ │                        │ │ │
│  │ ┌──────────────────┐ │    │ │ Runtime: Strands SDK   │ │ │
│  │ │ Market Data      │ │    │ │ LLM: Bedrock Claude    │ │ │
│  │ │ get_quote, hist. │ │    │ │ Tools: @tool decorator │ │ │
│  │ └──────────────────┘ │    │ │                        │ │ │
│  │ ┌──────────────────┐ │    │ │ run_dcf()              │ │ │
│  │ │ News Search      │ │    │ │ run_comps()            │ │ │
│  │ │ search, headlines│ │    │ │ monte_carlo()          │ │ │
│  │ └──────────────────┘ │    │ └────────────────────────┘ │ │
│  └──────────────────────┘    │ ┌────────────────────────┐ │ │
│                               │ │ Agent 3: Sentiment     │ │ │
│                               │ │ Analysis Agent         │ │ │
│                               │ │                        │ │ │
│                               │ │ Runtime: Strands SDK   │ │ │
│                               │ │ LLM: Bedrock Claude    │ │ │
│                               │ │                        │ │ │
│                               │ │ analyze_news()         │ │ │
│                               │ │ score_sentiment()      │ │ │
│                               │ └────────────────────────┘ │ │
│                               └────────────────────────────┘ │
│                                                              │
│  Bedrock (Claude) ← used by Strands agents                   │
└─────────────────────────────────────────────────────────────┘

  Agent boundaries:
  ┌─────────┐     HTTP      ┌─────────┐     HTTP      ┌─────────┐
  │Agent 1  │ ──────────▶  │Agent 2  │               │Agent 3  │
  │Agentforce│ ──────────────────────────────────────▶ │Sentiment│
  │(Apex)   │              │Financial│               │(Python) │
  └─────────┘              │(Python) │               └─────────┘
  Salesforce                └─────────┘
                            AWS Lambda                 AWS Lambda
```

### How Agentforce Calls Strands Agents (Plain HTTP, Not A2A)

```apex
// IR_FinancialAnalysisAction.cls — callAgent method
HttpRequest req = new HttpRequest();
req.setEndpoint(AWS_BASE_URL + '/financial-analysis/' + toolName);
req.setMethod('POST');
req.setHeader('Content-Type', 'application/json');
req.setHeader('x-api-key', AWS_API_KEY);
Map<String, Object> bodyMap = new Map<String, Object>{ 'ticker' => ticker };
req.setBody(JSON.serialize(bodyMap));
HttpResponse resp = http.send(req);
```

This is a synchronous HTTP POST. The Strands agent receives a ticker, runs a computation, returns JSON. No agent discovery, no capability negotiation, no task lifecycle. Agentforce treats Strands agents the same way it treats MCP servers — as tool endpoints.

---

## 006: Single Runtime — One Agent, Multi-Agent Pipeline Inside

```
  User (Slack / WhatsApp / Telegram / Discord / Web / iMessage / API)
         │
         ▼
┌─────────────────────────────────────────────────────────────────────┐
│  AWS — OPENCLAW ON BEDROCK AGENTCORE                                 │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │  OPENCLAW (Single Agent Runtime)                                │ │
│  │  LLM: Claude Sonnet 4.6 (Bedrock)                              │ │
│  │  Memory: persistent per-user                                    │ │
│  │  Channels: 12+ (all via Gateway WebSocket)                      │ │
│  │                                                                  │ │
│  │  Intent Router                                                   │ │
│  │       │                                                          │ │
│  │       ├── Simple query (L1-L2) → Skills directly                │ │
│  │       │                                                          │ │
│  │       └── Complex query (L3-L5) → AutoResearchClaw Pipeline     │ │
│  │                                          │                       │ │
│  │  ┌──────────────────────────────────────────────────────────┐   │ │
│  │  │  AUTORESEARCHCLAW PIPELINE (23 stages, in-process)       │   │ │
│  │  │                                                          │   │ │
│  │  │  Phase A: Scoping                                        │   │ │
│  │  │    ┌──────────────┐                                      │   │ │
│  │  │    │ Planner      │  (LLM persona — decomposes query)    │   │ │
│  │  │    └──────┬───────┘                                      │   │ │
│  │  │           │                                              │   │ │
│  │  │  Phase B: Data Collection                                │   │ │
│  │  │    ┌──────┴───────┐                                      │   │ │
│  │  │    │ Data Agents  │  (parallel — call MCP + SF skill)    │   │ │
│  │  │    └──────┬───────┘                                      │   │ │
│  │  │           │                                              │   │ │
│  │  │  Phase C: Synthesis                                      │   │ │
│  │  │    ┌──────┴───────────────────────────────────────┐      │   │ │
│  │  │    │ MULTI-AGENT DEBATE (in-process, same LLM)    │      │   │ │
│  │  │    │                                               │      │   │ │
│  │  │    │  ┌──────────┐ ┌──────────┐ ┌──────────────┐ │      │   │ │
│  │  │    │  │Bull Case │ │Bear Case │ │Base Case     │ │      │   │ │
│  │  │    │  │Agent     │ │Agent     │ │Agent         │ │      │   │ │
│  │  │    │  │(persona) │ │(persona) │ │(persona)     │ │      │   │ │
│  │  │    │  └────┬─────┘ └────┬─────┘ └──────┬───────┘ │      │   │ │
│  │  │    │       └────────────┼───────────────┘         │      │   │ │
│  │  │    │                    ▼                          │      │   │ │
│  │  │    │              Thesis Merge                     │      │   │ │
│  │  │    └──────────────────┬────────────────────────────┘      │   │ │
│  │  │           │           │                                   │   │ │
│  │  │      ★ HITL GATE ★   │  (analyst approves/refines)       │   │ │
│  │  │           │           │                                   │   │ │
│  │  │  Phase D-E: Analysis + Execution                          │   │ │
│  │  │    ┌──────┴───────┐                                      │   │ │
│  │  │    │ CodeAgent    │  (generates + runs DCF, comps,       │   │ │
│  │  │    │ (in-process) │   Monte Carlo in Python sandbox)     │   │ │
│  │  │    └──────┬───────┘                                      │   │ │
│  │  │           │                                              │   │ │
│  │  │    ┌──────┴───────┐                                      │   │ │
│  │  │    │ Self-Healing │  (retries on failure, adjusts params)│   │ │
│  │  │    └──────┬───────┘                                      │   │ │
│  │  │           │                                              │   │ │
│  │  │      ★ HITL GATE ★   (analyst reviews assumptions)       │   │ │
│  │  │           │                                              │   │ │
│  │  │  Phase F-G: Writing + Review                              │   │ │
│  │  │    ┌──────┴───────────────────────────────────────┐      │   │ │
│  │  │    │ PEER REVIEW (multi-agent, in-process)        │      │   │ │
│  │  │    │                                               │      │   │ │
│  │  │    │  ┌────────────┐  ┌────────────────────────┐  │      │   │ │
│  │  │    │  │Reviewer    │  │Anti-Fabrication         │  │      │   │ │
│  │  │    │  │Agent       │  │Sentinel                 │  │      │   │ │
│  │  │    │  │(checks     │  │(verifies every claim    │  │      │   │ │
│  │  │    │  │ logic)     │  │ against tool results)   │  │      │   │ │
│  │  │    │  └────────────┘  └────────────────────────┘  │      │   │ │
│  │  │    └──────────────────┬────────────────────────────┘      │   │ │
│  │  │           │           │                                   │   │ │
│  │  │  Phase H: Finalization                                    │   │ │
│  │  │      ★ HITL GATE ★   (analyst final approval)             │   │ │
│  │  │           │                                              │   │ │
│  │  │    ┌──────┴───────┐  ┌──────────┐  ┌──────────────┐     │   │ │
│  │  │    │ Publish to   │  │ Audit to │  │ MetaClaw     │     │   │ │
│  │  │    │ SF CRM       │  │ SF + LF  │  │ (learning)   │     │   │ │
│  │  │    └──────────────┘  └──────────┘  └──────────────┘     │   │ │
│  │  └──────────────────────────────────────────────────────────┘   │ │
│  │                                                                  │ │
│  │  Skills (all in-process, no HTTP between them):                  │ │
│  │  ┌──────────┐┌──────────┐┌──────────┐┌──────────┐┌──────────┐ │ │
│  │  │SF CRM    ││Financial ││Compliance││Audit     ││MuleSoft  │ │ │
│  │  │Skill     ││Analysis  ││Screening ││Logging   ││API Skill │ │ │
│  │  │(REST API)││(sandbox) ││(SF query)││(SF+LF)   ││(HITL req)│ │ │
│  │  └──────────┘└──────────┘└──────────┘└──────────┘└──────────┘ │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────┐                                         │
│  │ MCP Servers (Lambda)    │  ← only external calls (HTTP)          │
│  │ SEC EDGAR │ Market Data │                                         │
│  │ News Search             │                                         │
│  └────────────────────────┘                                         │
│                                                                      │
│  Bedrock (Claude) ← used by OpenClaw directly                       │
│  Bedrock Guardrails ← applied to all LLM calls                      │
│                                                                      │
│         │  Salesforce REST API (OAuth 2.0)                           │
│         ▼                                                            │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │  SALESFORCE ORG (data layer only — not the agent platform)    │  │
│  │  CRM: Accounts, Holdings, Coverage, Research Notes, Audit Log │  │
│  │  Trust Layer: via SF Models API (CRM reasoning only)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘

  Agent boundaries:
  ┌─────────────────────────────────────────────────────────────┐
  │ OpenClaw (single process)                                    │
  │                                                              │
  │  Planner ──▶ Data Agents ──▶ Bull/Bear/Base Debate          │
  │     ──▶ CodeAgent ──▶ Reviewer ──▶ Anti-Fab Sentinel        │
  │                                                              │
  │  All "agents" are LLM personas within the same runtime.     │
  │  No HTTP between them. No separate deployments.              │
  │  Pipeline orchestrates sequencing, gates, and self-healing.  │
  └─────────────────────────────────────────────────────────────┘
```

---

## The Fundamental Difference

| Dimension | 005 | 006 |
|-----------|-----|-----|
| Agent boundaries | Infrastructure (separate Lambdas, HTTP) | Prompt (same process, LLM personas) |
| Communication | HTTP POST with JSON, API key auth | In-process function calls, shared memory |
| Failure mode | Agents fail independently (HTTP timeout) | Shared fate (if OpenClaw dies, all die) |
| Latency between agents | Network round-trip (~100-500ms per call) | Zero (same process) |
| Protocol | Plain REST (not A2A, not MCP between agents) | Pipeline stage sequencing (not A2A) |
| Agent discovery | None — endpoints hardcoded in Apex | None — personas defined in pipeline config |
| Negotiation | None — request/response only | None — pipeline dictates sequence |

Neither is A2A. Both are hub-and-spoke with the orchestrator calling specialists. The difference is whether the spokes are separate infrastructure (005) or separate prompts within the same infrastructure (006).

### What A2A Would Look Like (Neither Project Does This)

```
  ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
  │ Agent A      │ ◄─────▶ │ Agent B      │ ◄─────▶ │ Agent C      │
  │              │  A2A    │              │  A2A    │              │
  │ /.well-known │         │ /.well-known │         │ /.well-known │
  │ /agent.json  │         │ /agent.json  │         │ /agent.json  │
  │              │         │              │         │              │
  │ Discovers B  │         │ Discovers A,C│         │ Discovers B  │
  │ Negotiates   │         │ Negotiates   │         │ Negotiates   │
  │ Delegates    │         │ Delegates    │         │ Delegates    │
  └─────────────┘         └─────────────┘         └─────────────┘

  - Each agent publishes capabilities via /.well-known/agent.json
  - Agents discover each other dynamically
  - Task lifecycle: submitted → working → completed
  - Bidirectional — any agent can delegate to any other
  - No central orchestrator required
```
