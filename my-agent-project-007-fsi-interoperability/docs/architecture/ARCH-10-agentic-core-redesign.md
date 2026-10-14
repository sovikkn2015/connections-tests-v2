# ARCH-10: Agentic Core Redesign — Strands SDK + Bedrock AgentCore

> Date: April 18, 2026
> Category: ARCHITECTURE (product design)
> Status: DESIGN PHASE — No code until approved
> Predecessor: REV-11 (The Empty Room), ARCH-07 (tech stack), ARCH-09 (module map)
> Purpose: Design the actual AI agent core that makes 007 work
> Research: Strands Agents SDK 1.0, Bedrock AgentCore (GA Oct 2025), AgentCore Gateway, AgentCore Memory

---

## THE PROBLEM

91K lines of trust layer, compliance, adapters, and UI. Zero LLM calls. Zero agent reasoning. REV-11 documented this as "The Empty Room." This document designs the tenants.

---

## RESEARCH FINDINGS

### Strands Agents SDK (Open Source, Apache 2.0)

Sources: [GitHub](https://github.com/strands-agents/sdk-python), [PyPI](https://pypi.org/project/strands-agents/), [AWS blog](https://aws.amazon.com/jp/blogs/opensource/introducing-strands-agents-1-0-production-ready-multi-agent-orchestration-made-simple/)

Core concept (rephrased): Give the agent a prompt, a model, and tools. The LLM decides what to do. No routing code. No state machines for tool selection. The model drives the loop.

Key capabilities:
- Model-agnostic: Bedrock, Anthropic, OpenAI, Ollama, Gemini, self-hosted
- Native MCP support: MCPClient wraps any MCP server as a tool
- Streaming: agent.stream() yields tokens
- Tool decorator: @tool with docstring that LLM reads to understand purpose
- Multi-agent: agents-as-tools pattern (supervisor calls specialists as tools)
- The agent loop: model receives message, decides to call tool, tool executes, result fed back, model decides next action or responds

Supervisor pattern (from [Sanjay Chaudhari](https://sanjaychaudhari.com/blog/strands-agents-bedrock-agentcore), rephrased): Specialist agents are defined as @tool functions. The supervisor's LLM decides which specialist to call based on the user's request. No if/else routing — the model reasons about it.

### Bedrock AgentCore (GA October 2025)

Sources: [AWS docs](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/what-is-bedrock-agentcore.html), [AWS blog](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/)

Three services relevant to 007:

1. AgentCore Gateway — centralized MCP tool server. Routes agent tool calls to MCP servers. Handles auth, tool discovery, naming collisions. 007's 20 M11 adapters are MCP servers — Gateway fronts them all behind one endpoint. ([Source](https://aws.amazon.com/blogs/machine-learning/transform-your-mcp-architecture-unite-mcp-servers-through-agentcore-gateway/))

2. AgentCore Memory — managed short-term + long-term memory. Replaces 007's custom L1-L4 memory. ([Source](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/memory.html))

3. AgentCore Runtime — deploys MCP servers as managed containers in microVMs. Session isolation. Stateful MCP support. ([Source](https://aws.amazon.com/blogs/machine-learning/introducing-stateful-mcp-client-capabilities-on-amazon-bedrock-agentcore-runtime/))

### How They Fit Together

Strands SDK = build agents (define tools, run LLM loop)
AgentCore = run agents in production (scale, memory, gateway, security)

---

## REDESIGN

### Principle: The LLM Drives the Loop

Current 007: Python if/else routes requests. Mock responses.
Redesign: LLM decides which tools to call, calls them through M6, synthesizes response.

### Architecture

```
User Message → M6 Web API → Trust Pipeline (M1→M2→M4)
    |
    v
SUPERVISOR AGENT (Strands, Haiku)
  tools: [research_specialist, client_service_specialist,
          compliance_check, execution_specialist, onboarding_specialist]
    |
    v (LLM decides which specialist)
CLIENT SERVICE SPECIALIST (Strands, Haiku)
  tools: [get_client_profile, get_holdings, get_financial_plan,
          get_recent_interactions, check_compliance]
    |
    v (LLM decides which tools, calls them via M6)
  get_client_profile("Henderson") → M6 → M11 Salesforce → MNPI-filtered
  get_holdings("Henderson") → M6 → M11 Orion → MNPI-filtered
  get_financial_plan("Henderson") → M6 → M11 eMoney → MNPI-filtered
    |
    v (LLM synthesizes from all three)
Meeting prep brief → Leakage scan → M10 audit → SSE stream to UI
```

Every tool call goes through M6 trust pipeline. MNPI filtered before LLM sees data. Audit on every action. The 91K lines of trust infrastructure become guardrails around the agent core.

### Specialist Definitions

| Specialist | Agent | Model | Tools (via M6) |
|-----------|-------|-------|----------------|
| Supervisor | Strands Agent | Haiku | 5 specialist tools |
| Research | Strands Agent wrapping LangGraph | Sonnet | SEC EDGAR, Bloomberg, News |
| Client Service | Strands Agent | Haiku | Salesforce, Orion, eMoney, Memory |
| Compliance | NOT an agent — OPA/Rego | None | Deterministic. Called as @tool. |
| Execution | Strands Agent + state machine | Haiku | Schwab, Fidelity, Eze |
| Onboarding | Strands Agent + workflow | Haiku | KYC tools, DocuSign |

### AgentCore Integration

| Service | 007 Usage | Replaces |
|---------|-----------|----------|
| AgentCore Gateway | Front 20 M11 adapters behind single MCP endpoint | M6 manual routing |
| AgentCore Memory | L1-L4 memory | Custom Redis/DynamoDB/pgvector |
| AgentCore Runtime | Deploy M11 adapters as managed MCP servers | Docker in EKS |

### What Changes vs What Stays

| Component | Change? | Detail |
|-----------|---------|--------|
| M1 Identity | NO | JWT RS256, same |
| M2/M4 OPA | NO | Deterministic Rego, same |
| M3 Schema | NO | 18 types, same |
| M5 Config | NO | Enterprise YAML, same |
| M6 Gateway | EXTEND | Add Strands agent host to web API |
| M7 Translators | NO | Vendor to canonical, same |
| M8 Pipeline | FIX | Add real Sonnet LLM nodes to LangGraph |
| M9 Intent Router | REPLACE | Supervisor agent handles routing via LLM |
| M10 Audit | NO | 3-tier WORM, same |
| M11 Adapters | NO | 20 MCP servers, same |
| M12 Web Console | NO | React UI, same |
| M13 FIX Bridge | NO | QuickFIX, same |
| Supervisor | REPLACE | Strands Agent with specialists-as-tools |
| Specialists | REPLACE | Strands Agents with real LLM + tools |

### New Code Structure

```
src/m12-agent-runtime/
  agents/
    supervisor.py           # Strands Agent: routes to specialists
    client_service.py       # Strands Agent: meeting prep, portfolio
    research.py             # Strands Agent: wraps M8 LangGraph
    execution.py            # Strands Agent: wraps state machine
    onboarding.py           # Strands Agent: wraps workflow
  tools/
    m6_tools.py             # @tool wrappers for M6 MCP calls
    compliance_tools.py     # @tool wrapper for M2 OPA
    memory_tools.py         # @tool wrapper for memory retrieval
  config.py                 # Model provider config
  agent_factory.py          # Creates agents per archetype
```

### Dependencies

```
strands-agents>=1.0
strands-agents-tools>=1.0
boto3  # Bedrock model provider
```

---

## IMPLEMENTATION PLAN

| Phase | What | Duration | Needs |
|-------|------|----------|-------|
| 1 | Strands SDK + supervisor + client_service with 3 tools via M6. Real Bedrock LLM calls. | 1-2 weeks | AWS creds with Bedrock access |
| 2 | Remaining specialists (research, execution, onboarding) | 1-2 weeks | Phase 1 |
| 3 | SSE streaming from agent.stream() through web API to frontend | 1 week | Phase 1 |
| 4 | AgentCore Gateway fronting M11 adapters | 1 week | AgentCore access |
| 5 | AgentCore Memory for L1-L4 | 1 week | AgentCore access |
| 6 | Accuracy testing: 200+ eval queries | 2 weeks | Phase 2 |

### To Start Phase 1

1. AWS account with Bedrock model access (Claude Haiku + Sonnet)
2. `pip install strands-agents strands-agents-tools`
3. That's it. Works locally against Bedrock.

---

## DECISIONS (Approved April 18, 2026)

### Decision 1: M9 Intent Router — KEEP BOTH VERSIONS

Keep existing M9 regex intent router as v1 (fast path, <1ms, >95% confidence).
Build new Strands supervisor agent as v2 (LLM reasoning, ~500ms).
Both versions coexist. Config toggle selects which runs.
v1 handles obvious requests. v2 handles ambiguous ones. Can A/B test.

### Decision 2: Research Specialist — KEEP BOTH VERSIONS

Keep existing M8 LangGraph pipeline as v1 (23 stages, checkpointing, HITL, 48 tests).
Build new Strands agent with 23 tools as v2 (Option B — rewrite as agent).
Both versions coexist. Config toggle selects which runs.
v1 is proven and tested. v2 is the target architecture.

### Decision 3: AgentCore Gateway — OPTION B (Behind M6)

Keep existing M6 trust gateway as the outermost layer.
AgentCore Gateway sits BEHIND M6, handling tool discovery and adapter routing.
M6 enforces trust (M1→M2→M4→M10) on every call. Gateway handles MCP routing after trust clears.
Reason: Trust layer must be outermost. If Gateway is in front, OPA/MNPI/audit can be bypassed.

Both versions coexist: v1 = M6 routes directly to adapters. v2 = M6 routes through AgentCore Gateway.

### Decision 4: Token Budget — KEEP AS IS + ADD CACHING

Haiku for routing/conversation: ~$0.002 per meeting prep.
Sonnet for research: ~$0.05 per deep research query.
Acceptable. No optimization needed now.
Add caching layer: cache common queries (same client, same day) to reduce redundant LLM calls.
Cache key: hash(client_id + query_type + date). TTL: 1 hour. Storage: Redis L1.

---

*ARCH-10 — Project 007 FSI Interoperability Platform*
*Agentic Core Redesign — Decisions approved. Ready to build.*
