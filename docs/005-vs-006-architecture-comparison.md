# 005 vs 006: Architecture Comparison — Code, Trade-offs, and Deciding Factors

> Date: April 8, 2026
> Scope: Project 005 (Agentforce + Strands + AWS) vs Project 006 (OpenClaw + Salesforce + AWS)

---

## Why 006 Has Less Code Than 005

006 is more comprehensive in scope (12+ channels, 23-stage research pipeline, dual trust layer, MuleSoft integration, 150-query eval suite) but has ~7,870 lines of code vs 005 V2's ~16,590. The reason is architectural — not missing features.

### Line Count Breakdown

| Layer | 005 V2 | 006 | Delta | Why |
|-------|--------|-----|-------|-----|
| Apex classes | 3,971 | 0 | -3,971 | 006 uses OpenClaw skills instead of Apex actions |
| Apex scripts | 371 | 461 | +90 | 006 has more seed data (25 clients vs 10) |
| Python (Lambda/agents) | 4,570 | 3,032 | -1,538 | 006 drops Strands agents — financial analysis runs in OpenClaw sandbox |
| TypeScript/React | 3,255 | 2,802 | -453 | Similar frontends, 006 slightly leaner |
| XML (SF metadata) | 876 | 997 | +121 | 006 has more custom objects and permission sets |
| YAML (SAM/config) | 392 | 578 | +186 | 006 adds OpenClaw config, AutoResearchClaw config, guardrails |
| Shell scripts | 284 | 0 | -284 | 006 hasn't built deploy scripts yet |
| JSON (agent bundles) | 2,562 | 169 | -2,393 | 006 doesn't use Agentforce — no aiAuthoringBundles metadata |
| SKILL.md (config-as-code) | 0 | 746 | +746 | OpenClaw skills are markdown config, not compiled code |
| CSS | 154 | 215 | +61 | Minor styling differences |

### Totals

| Metric | 005 V2 | 006 |
|--------|--------|-----|
| Code lines | ~16,590 | ~7,870 |
| Doc lines | ~4,300 | ~5,360 |
| Total lines | ~20,680 | ~13,720 |

### Where the Code Went

The ~8,700 line difference comes from three architectural shifts:

1. Zero Apex classes (-3,971 lines). In 005, Salesforce is the agent platform. Every agent action needs an Apex class — CRM queries, MCP callouts, Bedrock callouts, seed data runners, FLS grants, permission scripts. That's 12 Apex classes. In 006, OpenClaw is the agent platform. CRM interaction happens through OpenClaw's pre-built salesforce-api skill (configured, not coded). The agent logic that was in Apex is now in SKILL.md files — YAML frontmatter and markdown instructions.

2. No Strands agents (-1,538 lines). 005 V2 has MCP servers AND Strands agents (financial analysis, sentiment analysis) as separate Lambda functions with their own orchestration boilerplate. 006 has the MCP servers but financial analysis runs as Python skills inside OpenClaw's sandbox. Same math, less plumbing.

3. No Agentforce metadata (-2,393 lines). 005 needs aiAuthoringBundles, aiEvaluationDefinitions, and agent topic JSON configs for Agentforce. 006 doesn't use Agentforce at all — the agent is configured in openclaw.json and SKILL.md files.

The complexity shifted from code you write to platforms you configure. Less code, but also less enforcement — the security audit found that MNPI filtering and HITL gates that were enforceable in Apex code are now prompt-based instructions in SKILL.md files.

---

## Architecture Comparison

### 005: Agentforce + Strands + AWS

```
User → Salesforce (Web Chat / Slack / Agent API)
         │
         ▼
  Agentforce (Atlas Reasoning Engine)
         │
         ├── Apex Actions (CRM queries, MCP callouts)
         ├── Strands Agents on Lambda (financial analysis, sentiment)
         ├── MCP Servers on Lambda (SEC EDGAR, Market Data, News)
         └── Einstein Trust Layer (PII, toxicity, audit)
         │
         ▼
  Salesforce CRM (data) + AWS (compute)
```

### 006: OpenClaw + Salesforce + AWS

```
User → OpenClaw Gateway (Slack / WhatsApp / Telegram / Discord / Web / API)
         │
         ▼
  OpenClaw on Bedrock AgentCore (LLM reasoning + orchestration)
         │
         ├── salesforce-api skill (CRM queries via REST)
         ├── Financial analysis skills (Python sandbox)
         ├── AutoResearchClaw pipeline (23-stage)
         ├── MCP Servers on Lambda (SEC EDGAR, Market Data, News)
         ├── Bedrock Guardrails (PII, toxicity, prompt injection)
         └── MuleSoft skill (trade execution, wires, KYC)
         │
         ▼
  Salesforce CRM (data + audit) + AWS (compute + LLM)
```

---

## Pros and Cons

### 005: Agentforce + Strands

Pros:
- Einstein Trust Layer covers all CRM interactions out of the box — PII masking, toxicity detection, audit trail, zero custom security code for the Salesforce layer
- Atlas Reasoning Engine handles grounding, retry logic, and hallucination reduction natively
- Native CRM depth — SOQL, CdpQuery, Data Cloud vector search, Platform Events all work without REST API overhead
- Salesforce permission model enforced — sharing rules, field-level security, permission sets apply to agent actions automatically
- HITL and compliance enforcement in Apex code — not prompt-based, actually compiled and enforced at runtime
- Simpler identity model — Salesforce handles user auth, agent identity, and permission scoping in one system
- Fewer moving parts — two platforms (Salesforce + AWS) instead of four
- Enterprise support — Salesforce support covers the agent layer, not just the CRM

Cons:
- Limited channels — Web Chat, Slack, Messaging, Voice, API. No WhatsApp, Telegram, Discord, iMessage
- No structured research pipeline — Agentforce has topics and actions, not a 23-stage pipeline with gates, self-healing, and cross-run learning
- Vendor lock-in — Apex actions, agent topics, and aiAuthoringBundles are Salesforce-proprietary. Moving to another platform means rewriting everything
- Salesforce AI consumption pricing — Einstein AI credits can be significant at scale
- Apex limitations — no numpy, pandas, scipy. Financial modeling requires a separate compute layer (Strands on Lambda), adding complexity
- Two agent runtimes — Agentforce for orchestration + Strands for compute. Two systems to maintain, debug, and monitor
- Slower iteration — Apex deploys require metadata push, agent version commit, and activation. OpenClaw skills are file edits
- No persistent memory — Agentforce has session context but no cross-session memory. Each conversation starts fresh

### 006: OpenClaw + Salesforce + AWS

Pros:
- 12+ channels — Slack, WhatsApp, Telegram, Discord, iMessage, web chat, mobile, API. Meets users wherever they are
- AutoResearchClaw pipeline — 23-stage structured research with HITL co-pilot, anti-fabrication, self-healing, multi-agent debate, citation verification, and cross-run learning. Nothing comparable exists in Agentforce
- No vendor lock-in — OpenClaw is MIT-licensed. Skills, MCP servers, and Salesforce integration are portable
- Single agent runtime — OpenClaw handles orchestration, channels, memory, and skill execution. No second runtime needed
- Persistent per-user memory — conversations and learned preferences carry across sessions
- Full Python in sandbox — numpy, pandas, scipy, yfinance available for financial modeling without a separate compute layer
- Faster iteration — skills are markdown + Python files, no metadata deploy or agent activation required
- Serverless on AgentCore — zero idle cost, auto-scaling, pay-per-use
- Skill marketplace — thousands of pre-built skills on ClawHub for rapid capability expansion
- Dual trust layer — Bedrock Guardrails (LLM calls) + Einstein Trust Layer via SF Models API (CRM reasoning)

Cons:
- No native Einstein Trust Layer on the agent runtime — Bedrock Guardrails fill the gap, but it's two systems instead of one integrated layer
- No native CRM depth — REST API works but loses CdpQuery, Data Cloud vector search, native Platform Events
- MNPI enforcement is prompt-based — SKILL.md instructions tell the LLM not to leak MNPI, but there's no compiled code enforcing it (security audit Finding #7)
- HITL enforcement is prompt-based — MuleSoft trade/wire actions rely on LLM following SKILL.md instructions to pause for approval (security audit Finding #13)
- No Salesforce permission model on agent actions — OpenClaw doesn't inherit sharing rules, FLS, or permission sets. Must enforce at the Salesforce REST API layer
- Four platforms — OpenClaw, Salesforce, AWS, MuleSoft. More integration surface, more things that break, more expertise needed
- Broader team skill requirements — TypeScript (OpenClaw), Python (skills, MCP), Apex (Salesforce), AWS infra. 005 needs Apex + Python + TypeScript
- Gateway token in browser — the security audit found the OpenClaw bearer token is bundled into frontend JavaScript (Finding #2)
- Memory poisoning risk — persistent memory without encryption or integrity checks (security audit Finding #12)
- AutoResearchClaw is originally academic — FSI adaptation introduces risk if the upstream project diverges
- Enterprise governance gap — no built-in RBAC, no equivalent to Salesforce's permission set architecture at the agent layer

---

## When to Choose Which

| If you need... | Choose |
|---------------|--------|
| Maximum channel reach (WhatsApp, Telegram, Discord) | 006 |
| Structured multi-stage research pipeline | 006 |
| No vendor lock-in | 006 |
| Persistent cross-session memory | 006 |
| Full Python financial modeling in-agent | 006 |
| Native CRM compliance and trust layer | 005 |
| Code-enforced HITL and MNPI controls | 005 |
| Salesforce permission model on agent actions | 005 |
| Fewer platforms to manage | 005 |
| Enterprise support on the agent layer | 005 |
| Fastest time to production for CRM-centric use cases | 005 |
| Regulatory audit with minimal custom security code | 005 |

---

## The Core Trade-off

005 trades flexibility for safety. Salesforce's walled garden means fewer channels and vendor lock-in, but also means Einstein Trust Layer, permission sets, and Apex-enforced compliance come for free.

006 trades safety for flexibility. OpenClaw's open architecture means 12+ channels, a proven research pipeline, and no lock-in, but also means you're responsible for building the security controls that Salesforce gives you out of the box.

For a regulated FSI enterprise, the question is: does the value of 12+ channels and a 23-stage research pipeline justify the cost of rebuilding the compliance enforcement that Salesforce provides natively? If your analysts live in Slack and WhatsApp and need structured research automation, yes. If they primarily work in Salesforce and need CRM-native agents with minimal security overhead, no.
