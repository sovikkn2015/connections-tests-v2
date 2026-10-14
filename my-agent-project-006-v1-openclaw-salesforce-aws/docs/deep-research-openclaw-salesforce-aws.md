# Deep Research: OpenClaw + Salesforce + AWS Integration

> Research date: April 6, 2026
> Sources: [OpenClaw GitHub](https://github.com/openclaw/openclaw), [AWS OpenClaw Lightsail](https://aws.amazon.com/blogs/aws/introducing-openclaw-on-amazon-lightsail-to-run-your-autonomous-private-ai-agents/), [OpenClaw Salesforce Skills](https://playbooks.com/skills/openclaw/skills/salesforce-api), [OpenClaw MCP Integration](https://www.dench.com/blog/openclaw-mcp-tools), [AWS Bedrock AgentCore](https://aws.amazon.com/blogs/aws/introducing-amazon-bedrock-agentcore-securely-deploy-and-operate-ai-agents-at-any-scale/), [awsopenclaw.com](https://www.awsopenclaw.com/)
> Content was rephrased for compliance with licensing restrictions.

---

## 1. What Is OpenClaw?

OpenClaw is an open-source, self-hosted AI agent framework (MIT license, ~247K GitHub stars as of early 2026). It turns an LLM into a persistent, always-on autonomous agent that communicates through messaging platforms (Slack, WhatsApp, Telegram, Discord, iMessage, web chat) and takes real actions — file I/O, shell commands, API calls, browser automation, email, calendar management, and multi-step workflow orchestration.

Key characteristics:
- Self-hosted: runs on your own infrastructure (laptop, VPS, Raspberry Pi, EC2, or Bedrock AgentCore)
- Model-agnostic: works with Anthropic Claude, OpenAI, Ollama (local), Amazon Bedrock, and dozens of other providers
- Extensible via "Skills": modular capabilities the agent can invoke (think plugins/tools)
- MCP-native: supports Model Context Protocol for standardized tool integration
- Multi-channel: single agent instance accessible from 12+ messaging platforms simultaneously
- Persistent memory: maintains conversation context and learned preferences across sessions

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        OPENCLAW RUNTIME                         │
│                                                                 │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐ │
│  │  GATEWAY     │  │  AGENT CORE  │  │  SKILL REGISTRY      │ │
│  │              │  │              │  │                       │ │
│  │  Routes msgs │  │  LLM reason- │  │  Built-in skills     │ │
│  │  from all    │  │  ing loop    │  │  Custom skills       │ │
│  │  channels    │  │              │  │  MCP tool adapters    │ │
│  │              │  │  Decides     │  │  ClawHub marketplace  │ │
│  │  Slack       │  │  which skill │  │                       │ │
│  │  WhatsApp    │  │  to invoke   │  │  salesforce-api       │ │
│  │  Telegram    │  │              │  │  aws-bedrock          │ │
│  │  Discord     │  │  Maintains   │  │  yahoo-finance        │ │
│  │  Web Chat    │  │  memory      │  │  sec-edgar            │ │
│  │  iMessage    │  │              │  │  browser-automation   │ │
│  │  Agent API   │  │              │  │  ...                  │ │
│  └──────────────┘  └──────────────┘  └──────────────────────┘ │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  MCP CLIENT                                               │  │
│  │  Connects to any MCP-compatible server for tool access    │  │
│  └──────────────────────────────────────────────────────────┘  │
│                                                                 │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  LLM PROVIDER                                             │  │
│  │  Bedrock (Claude) │ OpenAI │ Ollama │ Any OpenAI-compat   │  │
│  └──────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. OpenClaw ↔ Salesforce Integration

### Verdict: Yes, fully possible. Multiple proven paths exist.

### Integration Methods

| Method | Maturity | How It Works |
|--------|----------|-------------|
| `salesforce-api` skill (official) | Production-ready | Managed OAuth via Maton gateway. SOQL queries, sObject CRUD, batch ops. Proxies to SF REST API. |
| `salesforce` skill (community) | Production-ready | Direct SF REST API with OAuth 2.0. SOQL/SOSL, schema inspection, CRUD, bulk ops, Apex execution, metadata deploy, raw REST. |
| `salesforce-dx` skill | Stable | Uses `sf` CLI. Pipeline analysis, deal discovery, org management. |
| MCP via Composio | Stable | Composio provides a Salesforce MCP server. OpenClaw connects natively. Auth handled automatically. |
| Custom HTTP skill | DIY | OpenClaw calls SF REST API directly with Connected App OAuth. |

### What OpenClaw Can Do with Salesforce

- Run SOQL and SOSL queries against any object
- Inspect object schemas (describe calls)
- Create, read, update, delete records on any sObject
- Bulk import/export operations
- Execute anonymous Apex
- Deploy metadata via Metadata API
- Make raw REST API calls to any SF endpoint
- Subscribe to Platform Events (via webhook/streaming skill)
- Trigger Flows and Process Builder via REST

### Salesforce Connected App Setup

```
Salesforce Org
  └─ Setup → App Manager → New Connected App
      ├─ Enable OAuth Settings
      ├─ Callback URL: (your gateway or maton.ai callback)
      ├─ Selected OAuth Scopes:
      │   ├─ api (Access and manage your data)
      │   ├─ refresh_token (Perform requests at any time)
      │   └─ custom_permissions (if needed)
      └─ Consumer Key + Secret → OpenClaw env vars
```

### Limitations

- No native Agentforce integration — OpenClaw is a separate agent framework
- No Atlas Reasoning Engine access — OpenClaw uses its own LLM reasoning loop
- Data Cloud (CdpQuery) not directly accessible — needs Apex REST wrapper or Connect API
- Einstein Trust Layer does not apply — must implement PII masking, toxicity detection, audit trail yourself
- Platform Events require streaming/webhook skill or polling

---

## 3. OpenClaw ↔ AWS Integration

### Verdict: Yes, deeply integrated. AWS treats OpenClaw as a first-class citizen.

AWS launched an official OpenClaw blueprint on Amazon Lightsail (early 2026), making it a one-click deployment. The community built enterprise-grade deployment on Bedrock AgentCore.

### Deployment Options on AWS

| Option | Infrastructure | Cost Model | Best For |
|--------|---------------|-----------|----------|
| Lightsail Blueprint | Pre-configured VM | Fixed monthly ($5-40/mo) | Quick start, personal use |
| EC2 (manual) | Self-managed EC2 | On-demand/reserved | Full control |
| Bedrock AgentCore Runtime | Serverless containers | Pay-per-use (zero idle) | Enterprise, auto-scaling |
| ECS/Fargate | Container orchestration | Per-task pricing | Team deployments |

### Bedrock AgentCore Deployment

```
┌─────────────────────────────────────────────────────────────────┐
│  AWS — BEDROCK AGENTCORE RUNTIME                                 │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  OPENCLAW AGENT                                          │    │
│  │  LLM: Claude Sonnet 4 (Bedrock)                         │    │
│  │  Skills: salesforce-api, yahoo-finance, sec-edgar, etc.  │    │
│  │  MCP: connected to Lambda MCP servers                    │    │
│  │  Channels: Slack, Web Chat, WhatsApp, Telegram, API      │    │
│  │  Auto-scaling: 0 → ∞ | Zero idle cost                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  Bedrock LLM │ Lambda (MCP) │ S3 │ Redshift │ Kinesis │ etc.   │
└─────────────────────────────────────────────────────────────────┘
```

OpenClaw natively speaks MCP — the same MCP servers from Project 005 (SEC EDGAR, Market Data, News Search on Lambda) work without modification.

---

## 4. Three-Way Integration: OpenClaw + Salesforce + AWS

### Verdict: Yes, architecturally sound. Three viable patterns.

### Pattern A: OpenClaw as the Orchestrator (Replaces Agentforce)

OpenClaw runs on AWS (AgentCore), uses Bedrock for LLM, connects to Salesforce via REST API skills, and uses AWS services for compute-heavy tasks. Agentforce is not used.

```
Analyst (Slack / WhatsApp / Telegram / Web)
  │
  ▼
AWS — OpenClaw on AgentCore
  ├── salesforce-api skill ──→ Salesforce CRM (SOQL, CRUD)
  ├── financial-analysis skill ──→ numpy/pandas/scipy (local)
  ├── MCP: SEC EDGAR, Market Data, News (Lambda)
  ├── Comprehend, Transcribe, Textract (AWS AI)
  └── Redshift, S3, Kinesis (AWS Data)
```

Pros: single runtime, full Python, multi-channel, no SF AI pricing, open source
Cons: no Einstein Trust Layer, no Atlas Reasoning, no native CRM depth, compliance risk for FSI

### Pattern B: OpenClaw as Sidecar (Alongside Agentforce)

Agentforce remains the CRM-facing agent. OpenClaw runs on AWS as a specialist for compute-heavy tasks. Agentforce delegates via Apex HTTP Callout.

```
Analyst (Web Chat / Slack / Agent API)
  │
  ▼
Salesforce — Agentforce Orchestrator
  ├── CRM topics (native Apex actions)
  └── Compute topics ──HTTP──→ AWS — OpenClaw on AgentCore
                                  ├── financial-analysis skill
                                  ├── sentiment-analysis skill
                                  └── document-processing skill
```

Pros: best of both worlds, Einstein Trust Layer for CRM, Agentforce UI/guardrails
Cons: two runtimes, OpenClaw adds complexity vs. Strands (Project 005 pattern)

### Pattern C: OpenClaw as User-Facing Gateway

OpenClaw handles all user channels (12+). Routes to Agentforce (CRM) or Strands (compute) based on intent.

```
Analyst (any of 12+ channels)
  │
  ▼
AWS — OpenClaw Gateway (AgentCore)
  ├── "Look up NVIDIA coverage" ──→ Agentforce (SF Agent API)
  ├── "Run DCF on NVIDIA"       ──→ Strands Agent (Bedrock)
  ├── "Summarize 10-K"          ──→ OpenClaw skill (Textract+LLM)
  └── "What's NVIDIA trading?"  ──→ MCP Market Data (Lambda)
```

Pros: maximum channel coverage, each backend does what it's best at
Cons: most complex (three runtimes), routing logic needs careful design

---

## 5. Comparison: OpenClaw vs. Strands vs. Agentforce

| Dimension | OpenClaw | Strands Agents | Agentforce |
|-----------|----------|---------------|------------|
| License | MIT (open source) | Apache 2.0 (open source) | Salesforce proprietary |
| Language | TypeScript/Node.js | Python | Apex |
| LLM Support | Any (Bedrock, OpenAI, Ollama, etc.) | Bedrock-native | SF-managed (GPT-4o default) |
| Deployment | Self-hosted (EC2, AgentCore, local) | Lambda, AgentCore, local | Salesforce org only |
| Channels | 12+ (Slack, WhatsApp, Telegram, Discord, iMessage, web, etc.) | None (API only) | Web Chat, Slack, Mobile, Messaging, Voice, API |
| Tool System | Skills + MCP | @tool decorator + MCP | Actions (Flow, Apex, API) |
| CRM Access | Via REST API skill | Via HTTP calls | Native (SOQL, CdpQuery, DML) |
| Trust/Security | DIY | DIY | Einstein Trust Layer |
| Reasoning | LLM-driven (simple loop) | LLM-driven (agent loop) | Atlas Reasoning Engine (grounding, retry) |
| Memory | Built-in persistent | Custom (DynamoDB, etc.) | Session context |
| Marketplace | ClawHub (~thousands of skills) | None | AppExchange |
| GitHub Stars | ~247K | ~15K | N/A |
| Ideal For | Multi-channel gateway, rapid prototyping | Compute-heavy Python backends | CRM-native, enterprise compliance |

---

## 6. Recommendation

### Where OpenClaw Uniquely Adds Value

1. **Channel coverage**: WhatsApp, Telegram, iMessage, Discord — channels Agentforce doesn't natively support
2. **Skill marketplace**: Thousands of pre-built skills on ClawHub for rapid prototyping
3. **Self-hosted control**: Full data sovereignty, no Salesforce AI consumption pricing
4. **Rapid iteration**: Skills are TypeScript functions, faster to build than Apex actions
5. **Personal agent pattern**: Each analyst gets their own OpenClaw instance with personalized memory

### Where OpenClaw Falls Short for FSI

1. **No Einstein Trust Layer**: Must build PII masking, toxicity detection, audit trail from scratch
2. **No native CRM depth**: REST API works but no CdpQuery, no Data Cloud vector search, no native Platform Events
3. **Enterprise governance**: No built-in RBAC, no SF permission sets, no sharing rules
4. **Compliance risk**: Regulated FSI firms may not approve self-hosted open-source agent handling client data without significant security hardening
5. **No AI Evaluation framework**: No equivalent to SF AI Evaluation Definitions

### Decision Matrix

| If you need... | Use... |
|---------------|--------|
| Maximum channel coverage (WhatsApp, Telegram, iMessage) | OpenClaw as gateway (Pattern C) |
| Rapid prototyping with pre-built skills | OpenClaw as orchestrator (Pattern A) |
| Enterprise compliance with Einstein Trust Layer | Agentforce + Strands (Project 005 pattern) |
| Simplest architecture with fewest moving parts | Agentforce + Strands (Project 005 pattern) |
| Self-hosted, zero Salesforce AI costs | OpenClaw as orchestrator (Pattern A) |
| Personal analyst agents with persistent memory | OpenClaw (any pattern) |

---

## 7. Conclusion

**Is it possible to integrate OpenClaw, Salesforce, and AWS? Yes, definitively.**

The integration paths are well-established:
- OpenClaw → Salesforce: official `salesforce-api` skill (managed OAuth, SOQL, CRUD, bulk ops) or MCP via Composio
- OpenClaw → AWS: first-class citizen — Lightsail blueprint, AgentCore deployment, native Bedrock LLM, IAM access to all services
- Three-way: OpenClaw on AWS (AgentCore) + Salesforce skill for CRM + AWS services for compute/data

The question isn't whether it's possible — it's whether it's the right choice vs. the Agentforce + Strands pattern from Project 005. For FSI with strict compliance requirements, Agentforce + Strands is safer. For maximum channel reach and rapid prototyping, OpenClaw adds real value as a gateway layer.

### Next Steps (if proceeding)

1. Decide on pattern (A, B, or C)
2. Create design doc with sprint breakdown
3. Prototype OpenClaw on Lightsail with `salesforce-api` skill connected to a scratch org
4. Test MCP server reuse from Project 005
5. Evaluate security hardening requirements for FSI compliance

---

## 8. AutoResearchClaw — Evaluation for Project 006

> Source: [github.com/aiming-lab/AutoResearchClaw](https://github.com/aiming-lab/AutoResearchClaw)
> Content was rephrased for compliance with licensing restrictions.

### What It Is

AutoResearchClaw is an open-source (MIT), fully autonomous 23-stage research pipeline built on top of OpenClaw. You give it a research topic — it produces a conference-ready academic paper with real literature (OpenAlex, Semantic Scholar, arXiv), sandboxed experiments, statistical analysis, multi-agent peer review, and LaTeX output (NeurIPS/ICML/ICLR templates).

It's not a chatbot that summarizes articles. It's a structured pipeline that decomposes problems, searches real databases, generates and runs experiments, self-heals on failure, pivots when hypotheses don't hold, and produces verified citations.

### Why It Matters for 006

AutoResearchClaw is the most advanced demonstration of what an OpenClaw-based agent can do when connected to real tools and data sources. It validates several architectural assumptions in our 006 research:

1. **OpenClaw can orchestrate complex multi-stage workflows** — 23 stages across 8 phases, with gate stages, rollback, PIVOT/REFINE decision loops, and artifact versioning. This is more sophisticated than anything Agentforce or Strands does out of the box.

2. **OpenClaw's skill system is production-grade** — 19 built-in skills, custom skill loading via SKILL.md with YAML frontmatter, trigger keywords, and applicable stages.

3. **MCP integration works end-to-end** — Uses MCP adapters for external agent communication (CLI, WebSocket, MCP). Confirms OpenClaw's MCP client is battle-tested.

4. **Multi-agent patterns are viable** — CodeAgent, BenchmarkAgent, FigureAgent are sub-agent systems within the pipeline. Multi-agent debate for hypothesis generation and peer review.

5. **Human-in-the-loop is solved** — 6 intervention modes (full-auto, gate-only, checkpoint, step-by-step, co-pilot, custom), per-stage policies, SmartPause (confidence-driven dynamic pausing), cost guardrails, escalation policies.

6. **Self-learning across runs** — MetaClaw integration captures lessons from failures, converts them to reusable skills, injects into future runs. +18.3% robustness improvement in controlled experiments.

### Architecture Relevance

```
AutoResearchClaw Pipeline Architecture
(relevant patterns for 006)

┌─────────────────────────────────────────────────────────────────┐
│  23-STAGE PIPELINE                                               │
│                                                                  │
│  Phase A: Scoping ──→ Phase B: Literature ──→ Phase C: Synthesis │
│       │                    │                       │             │
│       ▼                    ▼                       ▼             │
│  Phase D: Design ──→ Phase E: Execution ──→ Phase F: Analysis   │
│       │                    │                       │             │
│       │              (self-healing)          (PIVOT/REFINE)      │
│       ▼                    ▼                       ▼             │
│  Phase G: Writing ──→ Phase H: Finalization                      │
│       │                    │                                     │
│  (multi-agent              (4-layer citation                     │
│   peer review)              verification)                        │
│                                                                  │
│  CROSS-CUTTING:                                                  │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │ Gate     │ │ HITL     │ │ MetaClaw │ │ Anti-Fabrication  │   │
│  │ Stages   │ │ Co-Pilot │ │ Learning │ │ Sentinel          │   │
│  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### How It Could Fit Into 006

| Use Case | How AutoResearchClaw Helps |
|----------|--------------------------|
| Automated research briefs | `researchclaw run --topic "NVIDIA earnings analysis Q2 2026"` — structured research with real citations, not just an LLM summary |
| Literature review automation | Stages 3-6 use OpenAlex, Semantic Scholar, arXiv APIs with deduplication and relevance scoring |
| Experiment validation | Sandboxed execution with self-healing — could run financial models (DCF, Monte Carlo) in a controlled environment |
| Quality assurance | 4-layer citation verification, anti-fabrication sentinel, claim verification — addresses hallucinated data in financial research |
| Analyst workflow | Co-Pilot mode lets analysts guide research at key decision points while the pipeline handles grunt work |
| Cross-run learning | MetaClaw means the system gets better at financial research over time |

### What Would Need to Change for FSI

AutoResearchClaw is built for academic research. Adapting for FSI investment research requires:

1. **Custom skills for financial data** — Replace academic literature skills with SEC EDGAR, market data, news MCP servers
2. **Financial experiment templates** — Replace ML experiment sandbox with financial modeling sandbox (DCF, comps, Monte Carlo, backtesting)
3. **Compliance integration** — Add compliance screening as a gate stage (restricted list, MNPI, trading windows) via Salesforce skill
4. **Output format** — Replace LaTeX/NeurIPS template with investment research brief format (rating, target price, thesis, risks, catalysts)
5. **Data sources** — Swap OpenAlex/Semantic Scholar for financial data APIs, Redshift historical data, Data Cloud CRM data
6. **Audit trail** — Route pipeline actions through audit logging skill that writes to Salesforce

### Evaluation Summary

| Dimension | Assessment |
|-----------|-----------|
| Technical feasibility | High — OpenClaw-native, MCP-compatible, skill-extensible |
| Relevance to 006 | High — validates OpenClaw orchestration pattern, provides proven multi-stage pipeline framework |
| Effort to adapt for FSI | Medium — needs custom financial skills, compliance gates, output format changes. Core pipeline (staging, HITL, self-healing, learning) reusable as-is. |
| Risk | Low-medium — MIT license, active development (v0.4.0, April 2026), large community. Risk is in FSI customization, not the framework. |
| Recommendation | Worth prototyping. Fork, replace academic skills with financial skills, connect Salesforce via skill, deploy on AWS AgentCore. Test with "Generate research brief on NVIDIA" and evaluate output quality. |

### Updated Next Steps for 006

1. Decide on architecture pattern (A, B, or C from Section 4)
2. Evaluate AutoResearchClaw as the pipeline framework:
   - Fork the repo
   - Replace academic literature skills with financial data skills (SEC EDGAR, market data, news MCP servers)
   - Add Salesforce skill for CRM data and compliance checks
   - Adapt output format from academic paper to investment research brief
   - Test on AWS Lightsail with Bedrock (Claude) as LLM
3. Create design doc with sprint breakdown
4. Prototype end-to-end: analyst says "Research NVIDIA" in Slack → OpenClaw + AutoResearchClaw pipeline → structured research brief
