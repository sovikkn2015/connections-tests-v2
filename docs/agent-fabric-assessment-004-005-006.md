# Salesforce Agent Fabric Assessment: Projects 004, 005, 006

> Date: April 23, 2026
> Audience: Architecture leads, C-level
> Source: [MuleSoft Agent Fabric](https://www.mulesoft.com/ai/agent-fabric), [Salesforce Agent Fabric Control Plane](https://www.salesforce.com/news/stories/agent-fabric-control-plane-announcement/), [Deep Dive](https://architect.salesforce.com/docs/architect/fundamentals/guide/mulesoft-agent-fabric-deep-dive)
> Content was rephrased for compliance with licensing restrictions.

---

## What Agent Fabric Is

A unified control plane for managing multi-agent systems. Four pillars:

1. **Discover (Agent Registry)** — centralized catalog of all AI agents, MCP servers, and tools across the org. Eliminates redundancy, enables reuse.
2. **Orchestrate (Agent Broker)** — intelligent routing that dynamically matches tasks to the best-fit agent or tool. Powered by an LLM of your choice.
3. **Govern (Flex Gateway)** — enforces security and compliance policies on every agent-to-agent and agent-to-tool interaction via MCP and A2A protocols.
4. **Observe (Agent Visualizer)** — real-time interactive map of agent interactions. Traces decisions, monitors health, enables continuous optimization.

Agent Fabric uses a YAML-first approach — you define agent networks through a metadata descriptor that decouples definition from execution. Created in Anypoint Code Builder.

---

## Project 004: Wealth Advisor (Production) — Low Scope

**Current state:** 1 Agentforce agent, 10 topics, 8 Apex actions, MCP connectors (market data, news), Experience Cloud deployment.

**Where Agent Fabric fits:**

| Capability | Current 004 | With Agent Fabric |
|-----------|------------|-------------------|
| Agent discovery | Not needed (single agent) | Register agent + MCP connectors in Registry for org-wide reuse |
| Routing | Agentforce topic selector (built-in) | No change needed — single agent doesn't need a broker |
| Governance | Custom CORS/API key handling in Apex | Flex Gateway could enforce policies on MCP calls |
| Observability | Salesforce debug logs + Data Cloud | Agent Visualizer would show MCP call flows |

**Practical value: Small.** 004 is a single agent. Agent Fabric solves multi-agent coordination. You don't have agent sprawl with one agent. The only real benefit is registering the MCP connectors so other agents in the org can discover and reuse them.

**Recommendation:** Skip for 004 unless the firm is deploying multiple agents that need to share 004's MCP connectors.

---

## Project 005: Investment Research (Multi-Agent) — Medium Scope

**Current state:** 3 agents (Agentforce orchestrator + 2 Strands agents on Lambda), 3 MCP servers, Langfuse observability. Agents communicate via plain HTTP — no discovery, no governance, no cross-platform observability.

**Where Agent Fabric fits:**

| Capability | Current 005 | With Agent Fabric |
|-----------|------------|-------------------|
| Agent discovery | Hardcoded in Apex (Named Credentials, Custom Labels) | Register all 5 components (2 Agentforce agents, 2 Strands agents, 3 MCP servers) in Agent Registry |
| Routing | Agentforce orchestrator with Apex actions calling specific Lambda URLs | Agent Broker dynamically routes "run DCF analysis" to Financial Analysis agent, "check compliance" to Compliance Agent — no hardcoded endpoints |
| Governance | Plain API key auth on Apex-to-Lambda calls | Flex Gateway enforces rate limits, audit logging, MNPI policies at gateway level instead of Apex code |
| Observability | Langfuse (LLM traces) + CloudWatch (Lambda) — separate systems | Agent Visualizer shows real-time flow: Agentforce → Strands Financial Agent → MCP Market Data → back to Agentforce |

**Key benefits for 005:**
- Replaces hardcoded wiring between Agentforce and Strands agents with discoverable, governed connections
- Solves the cross-platform debugging problem (Salesforce + AWS) with unified observability
- MNPI enforcement moves from Apex code to gateway policy — harder to bypass

**Practical value: Medium.** 005 already works with hardcoded wiring. Agent Fabric would make it more maintainable and observable, but it's not blocking anything. Worth considering if the firm plans to add more agents to the 005 architecture.

**Recommendation:** Consider for 005 if keeping the Agentforce path. The biggest win is replacing the hardcoded Apex-to-Lambda wiring with governed, discoverable connections.

---

## Project 006: OpenClaw Replatform — High Scope (Natural Fit)

**Current state:** OpenClaw agent on AgentCore + 5 MCP servers (sec-edgar, market-data, news-search, salesforce-crm, research-pipeline) + 23-stage pipeline + Salesforce CRM + MuleSoft (Phase 6). Biggest operational challenge is the space between these systems.

**Where Agent Fabric fits:**

| Capability | Current 006 | With Agent Fabric |
|-----------|------------|-------------------|
| Agent discovery | Scattered across openclaw.json, SAM templates, Salesforce metadata | Agent Registry: single catalog of all 5 MCP servers, OpenClaw agent, pipeline, MuleSoft actions |
| Routing | LLM-driven intent classification (prompt instruction) | Agent Broker: policy-enforced routing — "any query mentioning 'deep dive' MUST go through pipeline" as a policy, not a prompt |
| Governance | Plain API Gateway with API key. MNPI filtering in Python code. | Flex Gateway: MNPI policies at gateway level, per-user rate limiting, FINRA audit logging at gateway, circuit breakers as policies |
| Observability | Langfuse (LLM) + CloudWatch (infra) + IR_Audit_Log__c (compliance) — 3 separate systems | Agent Visualizer: real-time interaction map across all 4 platforms |
| MuleSoft (Phase 6) | Documentation only — not built | Native fit: trade execution skills registered as governed actions with HITL policies at Flex Gateway |

### Detailed 006 Benefits

**1. Agent Registry — register everything**

The 5 MCP servers, the OpenClaw agent, the pipeline, the MuleSoft actions. One catalog instead of scattered configs. Any new agent in the org can discover and reuse the SEC EDGAR MCP server or the financial analysis pipeline without knowing the Lambda URL.

**2. Agent Broker — replace the intent router**

Currently, OpenClaw's LLM decides whether to call MCP tools directly (L1-L2) or invoke the pipeline (L3+). Agent Fabric's broker handles this routing with governance policies — enforced rules, not prompt instructions that can be bypassed.

**3. Flex Gateway — govern MCP calls**

This is the biggest win. Every MCP call from OpenClaw to Lambda currently goes through a plain API Gateway with an API key. Flex Gateway could:
- Enforce MNPI policies at the gateway level (block requests containing holdings amounts before they reach the MCP server)
- Rate limit per-user, per-tool (not just per-API-key)
- Log every agent-to-tool interaction for FINRA audit — at the gateway, not in application code
- Apply circuit breaker patterns as gateway policies instead of custom Python code

**4. Agent Visualizer — solve the observability problem**

The entire resilience strategy doc (correlation IDs, two-tier observability, runbooks) exists because there's no unified view across 4 platforms. Agent Visualizer would show: `User → OpenClaw → Claude Sonnet → market-data MCP → Finnhub → response` in real time. That's the trace panel built in the frontend, but at the platform level with governance.

**5. MuleSoft Phase 6 — native fit**

Agent Fabric IS MuleSoft. The Phase 6 trade execution skills (submit_order, initiate_wire, run_kyc) would be registered as governed actions with HITL policies enforced at the Flex Gateway level — not in prompt instructions.

### Architecture: Before and After

```
BEFORE (current 006):
  OpenClaw → plain HTTP → API Gateway → Lambda MCP servers
  OpenClaw → plain HTTP → Salesforce REST API
  OpenClaw → prompt instruction → "route to pipeline"
  No governance layer. No discovery. No cross-platform observability.

AFTER (with Agent Fabric):
  OpenClaw → Flex Gateway (MCP protocol, governed) → MCP servers
  OpenClaw → Flex Gateway (A2A protocol, governed) → other agents
  Agent Broker → routes L3+ queries to pipeline (policy-enforced)
  Agent Registry → all tools/agents discoverable
  Agent Visualizer → real-time interaction map
  Flex Gateway → MNPI filtering, rate limiting, audit logging at gateway
```

### What Agent Fabric Replaces in the Resilience Strategy

The `docs/006-operational-resilience-strategy.md` defines 5 layers of operational resilience. Agent Fabric would replace ~60% of it:

| Resilience Layer | Custom Code (current) | Agent Fabric Equivalent |
|-----------------|----------------------|------------------------|
| Correlation ID | ~93 lines across 6 files | Built into Agent Visualizer tracing |
| Circuit Breakers | ~150 lines (new circuit_breaker.py) | Flex Gateway circuit breaker policy |
| Health Checks | ~100 lines (health-check.py) | Agent Visualizer health monitoring |
| CloudWatch Dashboard | ~60 lines (dashboard JSON) | Agent Visualizer real-time map |
| Langfuse Trace Enrichment | ~70 lines in pipeline.py | Agent Visualizer + Flex Gateway logs |
| Runbooks | Documentation only | Still needed (Agent Fabric doesn't write runbooks) |

**Practical value: High.** Agent Fabric is the natural evolution for 006 — especially for Phase 6 (MuleSoft) and for solving the operational complexity that the resilience strategy addresses with custom code.

---

## The Tradeoff

Agent Fabric adds MuleSoft to the stack. 006 already has 4 platforms (Salesforce + AWS + OpenClaw + MuleSoft-planned). Agent Fabric doesn't add a new platform — it's MuleSoft, which is already in the 006 design for Phase 6.

However:
- **Cost:** MuleSoft Anypoint Platform licensing is enterprise-negotiated. Agent Fabric capabilities may require additional licensing beyond base Anypoint.
- **Complexity:** Another layer to configure and maintain. YAML-first is clean but adds a learning curve.
- **Timing:** Agent Fabric is evolving rapidly (automated discovery announced recently). Some features may be beta or limited.

---

## Recommendation

| Project | Agent Fabric? | When | Why |
|---------|--------------|------|-----|
| 004 | Skip | — | Single agent, no sprawl to manage |
| 005 | Consider | If scaling beyond 3 agents | Replaces hardcoded Apex-to-Lambda wiring with governed connections |
| 006 | Yes | Phase 5-6 (production hardening + MuleSoft) | Natural fit: solves operational complexity, enables Phase 6, replaces ~60% of custom resilience code |

For 006 specifically: implement Agent Fabric when you start Phase 6 (MuleSoft trade execution). At that point you're already adding MuleSoft to the stack — Agent Fabric comes with it and solves the governance, observability, and routing problems that the current architecture handles with custom code.

---

## Sources

- [MuleSoft Agent Fabric](https://www.mulesoft.com/ai/agent-fabric)
- [Salesforce Agent Fabric Control Plane Announcement](https://www.salesforce.com/news/stories/agent-fabric-control-plane-announcement/)
- [Agent Fabric Deep Dive — Salesforce Architect](https://architect.salesforce.com/docs/architect/fundamentals/guide/mulesoft-agent-fabric-deep-dive)
- [Choosing Integration Patterns for Agentforce](https://www.salesforce.com/blog/how-to-choose-integration-pattern-for-agentforce/)
- [MCP Support Across Salesforce](https://developer.salesforce.com/blogs/2025/06/introducing-mcp-support-across-salesforce)
- Content was rephrased for compliance with licensing restrictions.
