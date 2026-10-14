# Project 005 V3 — Agentforce + Strands + AWS + Agent Fabric

> **STATUS 2026-04-26:** V3-B live on current Anypoint Developer tier. V3-C (Agent Registry/Broker/Visualizer) scaffolded but on-hold pending subscription upgrade. See docs/v3-b-architecture.md.

> Date: April 23, 2026
> Audience: Architecture leads, engineering
> Scope: V3 adds MuleSoft Agent Fabric to the existing V2 multi-agent architecture. Replaces hardcoded wiring with governed discovery, policy-enforced routing, and unified observability.

---

## Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  PROJECT 005 V3 — AGENTFORCE + STRANDS + AWS + AGENT FABRIC                 │
│                                                                              │
│  What changes from V2: Agent Fabric replaces hardcoded wiring,               │
│  adds governed discovery, policy-enforced routing, and unified observability  │
└──────────────────────────────────────────────────────────────────────────────┘

                    ┌─────────────────────────────────┐
                    │  ANALYST                         │
                    │  Web Chat / Slack / Agent API    │
                    └───────────────┬─────────────────┘
                                    │
                                    ▼
┌══════════════════════════════════════════════════════════════════════════════┐
║  SALESFORCE ORG                                                             ║
║                                                                             ║
║  ┌────────────────────────────────────────────────────────────────────────┐ ║
║  │  AGENTFORCE (Agent 1 — IR Research Orchestrator)                       │ ║
║  │  Runtime: Atlas Reasoning Engine                                       │ ║
║  │  Trust: Einstein Trust Layer (native)                                  │ ║
║  │                                                                        │ ║
║  │  12 Topics → routes queries to actions                                 │ ║
║  │       │                                                                │ ║
║  │       ├── CRM Actions (Apex, SOQL) ──→ IR_Company__c, IR_Coverage__c  │ ║
║  │       │                                                                │ ║
║  │       └── External Actions ──→ ┌─────────────────────────────────┐    │ ║
║  │                                │  AGENT FABRIC (NEW IN V3)       │    │ ║
║  │                                │  Flex Gateway + Agent Registry   │    │ ║
║  │                                └────────────┬────────────────────┘    │ ║
║  └─────────────────────────────────────────────┼────────────────────────┘ ║
║                                                │                          ║
║  ┌──────────────────┐  ┌───────────────────────┼──────────────────────┐  ║
║  │ IR COMPLIANCE     │  │  CRM Objects          │                      │  ║
║  │ AGENT (Agent 2)   │  │  IR_Company__c        │                      │  ║
║  │ (Agentforce)      │  │  IR_Coverage__c       │                      │  ║
║  │                   │  │  IR_Research_Note__c   │                      │  ║
║  │ Registered in ────┼──│  IR_Audit_Log__c      │                      │  ║
║  │ Agent Registry    │  │  IR_Watchlist__c       │                      │  ║
║  └──────────────────┘  └───────────────────────┼──────────────────────┘  ║
╚════════════════════════════════════════════════╪══════════════════════════╝
                                                 │
                    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┼─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                    ALL EXTERNAL CALLS GO THROUGH │ FLEX GATEWAY (V3)
                    MCP protocol, governed,       │ rate-limited, audited
                    ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─┼─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─
                                                 │

╔════════════════════════════════════════════════╪══════════════════════════╗
║  MULESOFT AGENT FABRIC — CONTROL PLANE                                    ║
║                                                │                          ║
║  ┌─────────────────────────────────────────────┴──────────────────────┐  ║
║  │                                                                    │  ║
║  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐ │  ║
║  │  │ AGENT        │  │ AGENT        │  │ AGENT VISUALIZER         │ │  ║
║  │  │ REGISTRY     │  │ BROKER       │  │ (Observability)          │ │  ║
║  │  │              │  │              │  │                          │ │  ║
║  │  │ Registered:  │  │ Routes:      │  │ Real-time map:           │ │  ║
║  │  │ • IR Orch.   │  │              │  │ Agent1 → Flex GW →      │ │  ║
║  │  │ • IR Compl.  │  │ L1-L2 →      │  │   MCP Server → Data →   │ │  ║
║  │  │ • Financial  │  │   MCP direct │  │   Response               │ │  ║
║  │  │   Analysis   │  │              │  │                          │ │  ║
║  │  │ • Sentiment  │  │ L3-L4 →      │  │ Traces every call       │ │  ║
║  │  │   Analysis   │  │   Strands    │  │ across SF + AWS          │ │  ║
║  │  │ • SEC EDGAR  │  │   agents     │  │                          │ │  ║
║  │  │ • Market Data│  │              │  │ Replaces:                │ │  ║
║  │  │ • News Search│  │ Compliance → │  │ • Langfuse (partial)     │ │  ║
║  │  │              │  │   IR Compl.  │  │ • CloudWatch dashboard   │ │  ║
║  │  │ Discoverable │  │   Agent      │  │ • Custom correlation IDs │ │  ║
║  │  │ by any agent │  │              │  │                          │ │  ║
║  │  │ in the org   │  │ Policy-      │  │                          │ │  ║
║  │  │              │  │ enforced,    │  │                          │ │  ║
║  │  │              │  │ not prompt-  │  │                          │ │  ║
║  │  │              │  │ based        │  │                          │ │  ║
║  │  └──────────────┘  └──────────────┘  └──────────────────────────┘ │  ║
║  │                                                                    │  ║
║  │  ┌──────────────────────────────────────────────────────────────┐  │  ║
║  │  │ FLEX GATEWAY (MCP + A2A Protocol Enforcement)                │  │  ║
║  │  │                                                              │  │  ║
║  │  │ Policies:                                                    │  │  ║
║  │  │ • MNPI filter: block holdings amounts in outbound requests   │  │  ║
║  │  │ • Rate limit: 25 req/sec per tool, 50 burst                  │  │  ║
║  │  │ • Auth: API key + mTLS (replaces plain API key)              │  │  ║
║  │  │ • Audit: every call logged for FINRA (replaces custom code)  │  │  ║
║  │  │ • Circuit breaker: 3 failures → open → 120s recovery         │  │  ║
║  │  │ • Timeout: 30s for MCP tools, 120s for Strands agents        │  │  ║
║  │  └──────────────────────────────────────────────────────────────┘  │  ║
║  │         │              │              │              │              │  ║
║  └─────────┼──────────────┼──────────────┼──────────────┼──────────────┘  ║
╚════════════╪══════════════╪══════════════╪══════════════╪══════════════════╝
             │              │              │              │
             ▼              ▼              ▼              ▼
╔════════════════════════════════════════════════════════════════════════════╗
║  AWS (us-east-1)                                                          ║
║                                                                           ║
║  ┌──────────────────────────────────────────────────────────────────────┐ ║
║  │  MCP SERVERS (Lambda) — registered in Agent Registry                  │ ║
║  │                                                                       │ ║
║  │  ┌────────────┐  ┌────────────┐  ┌────────────┐                      │ ║
║  │  │ SEC EDGAR  │  │ Market     │  │ News       │                      │ ║
║  │  │ MCP Server │  │ Data MCP   │  │ Search MCP │                      │ ║
║  │  │            │  │            │  │            │                      │ ║
║  │  │ get_10k    │  │ get_quote  │  │ search_news│                      │ ║
║  │  │ get_10q    │  │ get_hist   │  │ get_hdl    │                      │ ║
║  │  │ get_8k     │  │ get_cons   │  │ get_sent   │                      │ ║
║  │  │ get_ins    │  │ get_opts   │  │            │                      │ ║
║  │  └────────────┘  └────────────┘  └────────────┘                      │ ║
║  │                                                                       │ ║
║  │  Data: SEC EDGAR API, Alpha Vantage/Finnhub, Tavily                   │ ║
║  └──────────────────────────────────────────────────────────────────────┘ ║
║                                                                           ║
║  ┌──────────────────────────────────────────────────────────────────────┐ ║
║  │  STRANDS AGENTS (Lambda) — registered in Agent Registry               │ ║
║  │                                                                       │ ║
║  │  ┌──────────────────────────┐  ┌──────────────────────────────────┐  │ ║
║  │  │ Financial Analysis Agent │  │ Sentiment Analysis Agent         │  │ ║
║  │  │ (Strands SDK + Bedrock)  │  │ (Strands SDK + Bedrock)          │  │ ║
║  │  │                          │  │                                  │  │ ║
║  │  │ @tool run_dcf            │  │ @tool analyze_transcript         │  │ ║
║  │  │ @tool run_comps          │  │ @tool score_news_sentiment       │  │ ║
║  │  │ @tool monte_carlo        │  │ @tool detect_tone_shifts         │  │ ║
║  │  │ @tool fair_value         │  │ @tool aggregate_sentiment        │  │ ║
║  │  │                          │  │                                  │  │ ║
║  │  │ Discovered via Registry  │  │ Discovered via Registry          │  │ ║
║  │  │ Governed via Flex GW     │  │ Governed via Flex GW             │  │ ║
║  │  └──────────────────────────┘  └──────────────────────────────────┘  │ ║
║  └──────────────────────────────────────────────────────────────────────┘ ║
║                                                                           ║
║  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────────┐   ║
║  │ SSE Proxy    │  │ Token Proxy  │  │ S3 + CloudFront              │   ║
║  │ /sse-proxy   │  │ /oauth/token │  │ React frontend (SLDS)        │   ║
║  └──────────────┘  └──────────────┘  └───────────────────────────────┘   ║
║                                                                           ║
║  Bedrock (Claude Sonnet 4.6) ← used by Strands agents                    ║
║  Langfuse ← retained for LLM-specific traces (complements Visualizer)    ║
╚═══════════════════════════════════════════════════════════════════════════╝
```

---

## What V3 Needs (Delta from V2)

| # | What | Effort | Notes |
|---|------|--------|-------|
| 1 | MuleSoft Anypoint Platform license | $$ | Required for Agent Fabric. Enterprise-negotiated. |
| 2 | Flex Gateway deployment | 2 days | Replaces API Gateway for MCP/A2A calls. Sits between SF and AWS. |
| 3 | Agent Registry setup | 1 day | Register all 7 components (2 agents, 2 Strands agents, 3 MCP servers) via YAML descriptors. |
| 4 | Agent Broker configuration | 2 days | Define routing policies: L1-L2 → MCP direct, L3-L4 → Strands agents, compliance → IR Compliance Agent. |
| 5 | Flex Gateway policies | 2 days | MNPI filter, rate limits, circuit breaker, FINRA audit logging, mTLS. Replaces custom Apex/Python code. |
| 6 | Apex action refactor | 3 days | Replace Named Credential + Custom Label wiring with Agent Fabric broker calls. Remove hardcoded Lambda URLs from Apex. |
| 7 | Agent Visualizer setup | 1 day | Connect to all registered agents/tools. Configure dashboards. |
| 8 | Strands agent registration | 1 day | Expose Strands agents as A2A-compatible endpoints. Register in Agent Registry. |
| 9 | Remove custom resilience code | 1 day | Delete circuit breaker Python, health check script, CloudWatch dashboard — Flex Gateway handles it. |
| 10 | Testing + validation | 3 days | Run 30-query eval suite through the new path. Verify Flex Gateway policies. |
| **Total** | | **~16 days** | |

---

## What V3 Removes from V2

- Hardcoded Lambda URLs in Apex Custom Labels
- Named Credential manual setup for AWS
- Custom API key auth handling
- Custom MNPI filtering in Apex (moves to Flex Gateway policy)
- Custom circuit breaker code
- Custom health check script
- Separate CloudWatch dashboard
- Manual correlation ID threading

## What V3 Keeps from V2

- Agentforce agents (orchestrator + compliance) — unchanged
- Strands agents on Lambda — unchanged, just registered in Agent Fabric
- MCP servers on Lambda — unchanged, just governed by Flex Gateway
- React frontend on S3/CloudFront — unchanged
- Langfuse — retained for LLM-specific traces (complements Agent Visualizer)
- Einstein Trust Layer — unchanged
- CRM objects and seed data — unchanged

---

## V2 → V3 Comparison

| Dimension | V2 (Current) | V3 (Agent Fabric) |
|-----------|-------------|-------------------|
| Agent discovery | Hardcoded in Apex | Agent Registry (YAML) |
| Routing | Apex actions with Named Credentials | Agent Broker (policy-enforced) |
| Governance | Plain API key, custom Apex code | Flex Gateway (MCP/A2A policies) |
| MNPI enforcement | Apex code (IR_MnpiGuard) | Flex Gateway policy + Apex (defense in depth) |
| Observability | Langfuse + CloudWatch (separate) | Agent Visualizer + Langfuse (unified) |
| Circuit breakers | Custom Python code | Flex Gateway policy |
| Audit logging | Custom Apex + Langfuse | Flex Gateway FINRA policy + Langfuse |
| Adding new agents | Manual Apex + Named Credential setup | Register in Agent Registry, auto-discoverable |
| Cross-platform debugging | Multi-console scavenger hunt | Agent Visualizer real-time map |

---

## Prerequisites

1. MuleSoft Anypoint Platform license with Agent Fabric capabilities
2. Flex Gateway deployed (can run on AWS ECS/EKS or as a sidecar)
3. Anypoint Code Builder for YAML-first agent network definition
4. Existing 005 V2 fully deployed and working (agents, MCP servers, frontend)

---

## Sources

- [MuleSoft Agent Fabric](https://www.mulesoft.com/ai/agent-fabric)
- [Agent Fabric Deep Dive](https://architect.salesforce.com/docs/architect/fundamentals/guide/mulesoft-agent-fabric-deep-dive)
- [Choosing Integration Patterns for Agentforce](https://www.salesforce.com/blog/how-to-choose-integration-pattern-for-agentforce/)
- Content was rephrased for compliance with licensing restrictions.


---

## What Is Flex Gateway?

Flex Gateway is MuleSoft's lightweight API gateway that runs anywhere — your cloud, your data center, your laptop. It sits between your agents and the services they call, enforcing policies on every interaction.

### API Gateway (current V2) vs Flex Gateway (V3)

| Capability | AWS API Gateway (V2) | Flex Gateway (V3) |
|-----------|---------------------|-------------------|
| Protocol support | HTTP/REST only | HTTP + MCP + A2A natively |
| Auth | API keys, IAM | API keys, mTLS, OAuth, per-agent identity |
| Rate limiting | Per-API-key | Per-agent, per-tool, per-user |
| MNPI filtering | Not possible at gateway | Block MNPI fields before they reach downstream |
| Circuit breakers | Not built-in | Policy-based, configurable per route |
| Audit logging | CloudWatch (infra-level) | Full agent context: who called what, why, what data flowed |
| Policy management | AWS Console | Anypoint Platform (same UI as Agent Fabric) |
| Agent awareness | None — treats all calls as HTTP | Understands agent identity, tool schemas, MCP protocol |

### Where It Runs

```
Option 1: Docker container on ECS/EKS (your AWS account)  ← recommended for 005 V3
Option 2: Standalone on an EC2 instance
Option 3: Kubernetes sidecar
Option 4: MuleSoft-hosted (CloudHub)
```

~50MB container. Deploys in minutes. Connects back to Anypoint Platform for policy management and observability.

### How It Changes the Data Flow

```
BEFORE (V2):
  Agentforce → Named Credential → AWS API Gateway (API key) → Lambda MCP server
  No MNPI filtering at gateway. No agent-aware audit. No circuit breakers.

AFTER (V3):
  Agentforce → Agent Fabric Broker → Flex Gateway → Lambda MCP server
                                        │
                                        ├── MNPI policy: blocks holdings amounts
                                        ├── Rate limit: 25 req/sec per tool
                                        ├── Auth: mTLS + API key
                                        ├── Audit: full agent context logged
                                        ├── Circuit breaker: 3 failures → open
                                        └── Timeout: 30s MCP, 120s Strands
```

The Lambda functions don't change. The MCP servers don't change. Flex Gateway sits in front of them and enforces policies. It turns "we trust the code to filter MNPI" into "the gateway blocks MNPI before it reaches the code."

### What Flex Gateway Replaces in V2

| V2 Custom Code | Flex Gateway Policy |
|----------------|-------------------|
| `IR_MnpiGuard` Apex class (~200 lines) | MNPI content filter policy (YAML) |
| API key auth via Named Credentials | mTLS + API key policy |
| Custom circuit breaker Python (~80 lines) | Circuit breaker policy (YAML) |
| CloudWatch dashboard (~60 lines JSON) | Agent Visualizer (built-in) |
| Custom correlation ID threading (~93 lines) | Built-in request tracing |
| Custom health check script (~100 lines) | Gateway health monitoring |

Total custom code replaced: ~533 lines → YAML policy configs.
