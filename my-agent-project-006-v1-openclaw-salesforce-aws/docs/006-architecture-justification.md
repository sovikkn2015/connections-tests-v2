# Project 006: Architecture Justification — Why an FSI Enterprise Would Build This

> Date: April 8, 2026
> Source: Project 006 design documents, tech stack assessment, deep research, evaluation strategy

---

## The Core Problem 006 Solves

Equity research analysts spend ~70% of their time on data gathering and formatting. Wealth advisors spend ~45 minutes prepping for each client meeting. Compliance teams manually review every trade. These are high-value professionals doing low-value repetitive work across disconnected systems — CRM, market data terminals, regulatory filing databases, news feeds, trading systems.

No single vendor platform covers all of this. Salesforce owns the client relationship but can't run financial models or pull SEC filings natively. AWS has the compute and data infrastructure but has no CRM or user-facing channels. Agentforce has a trust layer but only supports a handful of channels and can't orchestrate a 23-stage research pipeline.

---

## The Deciding Factors

What pushes an FSI enterprise toward this architecture:

1. **Channel reach is non-negotiable.** Advisors in the field use WhatsApp. Analysts live in Slack and Discord. Agentforce supports ~5 channels. OpenClaw supports 12+. If your users aren't at a desk with Salesforce open, you need the agent to meet them where they are.

2. **The research pipeline already exists.** AutoResearchClaw is a battle-tested 23-stage pipeline with HITL co-pilot, self-healing, anti-fabrication, multi-agent debate, and cross-run learning. Building this from scratch on Agentforce or Strands would take months. Forking and adapting it for FSI takes weeks.

3. **FINRA 2026 demands auditability of AI agents.** The architecture provides three audit layers (Langfuse traces, IR_Audit_Log__c in Salesforce, Einstein Trust Layer logs) and HITL gates at every critical decision point. Every action is logged with full provenance. This isn't optional — it's regulatory.

4. **Vendor lock-in avoidance.** OpenClaw is MIT-licensed. Skills, MCP servers, and the Salesforce integration are all portable. If the enterprise decides to swap the agent runtime in 2 years, the MCP servers, financial models, and CRM objects all survive. Compare that to building everything in Apex on Agentforce — you're locked in.

5. **The firm already owns Salesforce and AWS.** OpenClaw is the only new piece, and it's free. The architecture leverages existing investments rather than requiring new platform purchases.

---

## The Value Proposition

- **Analyst productivity:** 70% of time reclaimed from data gathering. A "deep dive on NVIDIA" that took a day now takes minutes with analyst oversight at 3 HITL gates.
- **Compliance automation:** Self-auditing agent with MNPI screening, restricted list checks, and trading window enforcement baked into every query path.
- **Cross-run learning:** MetaClaw means the system improves over time. Each research brief makes the next one better.
- **Incremental delivery:** 6 phases over 10 weeks, each independently valuable. If Phase 3 fails, Phases 1-2 still work as a CRM-connected agent with market data.

---

## Pros

- Maximum channel coverage (12+ vs 5-6 on Agentforce)
- Proven 23-stage research pipeline with anti-fabrication and citation verification
- No vendor lock-in (MIT license, portable skills and MCP servers)
- Zero custom security code — Bedrock Guardrails + SF Models API handle it via config
- Dual trust layer (Bedrock Guardrails for LLM calls, Einstein Trust Layer for CRM reasoning)
- Serverless, zero idle cost deployment on AgentCore
- Single reproducible environment (`git clone → sf org create → sf project deploy → sam deploy → done`)
- Three-layer evaluation strategy purpose-built for finance (numerical precision, temporal correctness, compliance hard gates)

---

## Cons

- **Complexity:** Four platforms (OpenClaw, Salesforce, AWS, MuleSoft) means more integration surface area, more things that can break, more expertise needed on the team.
- **No native Einstein Trust Layer coverage for the agent runtime itself** — Bedrock Guardrails fill the gap, but it's two systems instead of one.
- **No native CRM depth from the agent** — REST API works but you lose CdpQuery, Data Cloud vector search, and native Platform Event subscriptions.
- **Enterprise governance gap** — OpenClaw has no built-in RBAC, no SF permission sets, no sharing rules. You have to enforce these at the Salesforce layer.
- **Compliance risk for regulated firms** — Self-hosted open-source agent handling client data requires significant security hardening and internal approval processes.
- **Team skill requirements** — You need people who know TypeScript (OpenClaw), Python (MCP servers, financial models), Apex (Salesforce), and AWS infrastructure. That's a broader skill set than a pure Salesforce or pure AWS approach.
- **AutoResearchClaw is originally academic** — The FSI adaptation (replacing literature skills with financial data skills, adding compliance gates, changing output format) is medium effort and introduces risk if the upstream project diverges.

---

## When This Architecture Makes Sense

An FSI enterprise would choose 006 when they need multi-channel reach beyond what Agentforce offers, want to avoid vendor lock-in, already have significant AWS and Salesforce investments, need a structured research pipeline (not just a chatbot), and have the engineering team to manage a multi-platform system.

If the firm only needs CRM-native agents accessible through Salesforce UI and Slack, the simpler Agentforce + Strands pattern from Project 005 is the safer bet. 006 is for firms that have outgrown that model.
