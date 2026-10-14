# Cost Analysis: Projects 001–006

> Date: April 21, 2026
> Audience: C-Level / Executive Steering Committee
> Scope: Build cost, run cost, and licensing for all six agent projects
> Exclusion: Project 007 is out of scope for this analysis

---

## Executive Summary

This document provides a three-scenario cost breakdown (Conservative, Baseline, Aggressive) for the progressive series of FSI agent projects built on Salesforce, AWS, and OpenClaw. Each project layers new capabilities on the previous one — from a Hello World proof-of-concept (001) to a full multi-platform AI research system with trade execution (006).

The total investment across all six projects ranges from **$113K (Conservative)** to **$524K (Aggressive)** over a 12-month period, covering build labor, platform licensing, cloud infrastructure, and third-party data services. The single largest cost driver across all scenarios is **engineering labor** (55–65% of total in Baseline), followed by **Salesforce licensing** (22%).

---

## Assumptions

### General Assumptions
1. **Team composition:** 1 senior full-stack engineer (Salesforce + AWS), 1 part-time architect/reviewer. No dedicated QA, PM, or DevOps — this is a build-and-prove team, not a product org.
2. **Fully loaded engineer cost:** $150/hr (includes benefits, overhead). This is the blended rate used across all scenarios.
3. **Salesforce org:** Developer Edition (free) for 001–004. For 005–006 production scenarios, Enterprise or FSC licensing is assumed.
4. **AWS region:** us-east-1 (cheapest for Bedrock + Lambda).
5. **No dev/staging/prod split** — single environment per project, reproducible from git.
6. **Projects are sequential** — each builds on the previous. Labor estimates reflect incremental effort, not greenfield.
7. **LLM pricing** is on-demand (no provisioned throughput commitments). Bedrock pricing as of April 2026.
8. **Salesforce pricing** uses list rates. Enterprise negotiation typically yields 20–35% discount — not reflected here.
9. **Usage volume** for run costs assumes a small team (5–15 analysts/advisors) in pilot mode, not enterprise-wide rollout.
10. **MuleSoft** (006 Phase 6 only) is estimated at typical enterprise-negotiated rates since no public price list exists.

### LLM Token Pricing (Bedrock, On-Demand, April 2026)

| Model | Input / 1M tokens | Output / 1M tokens |
|-------|-------------------|---------------------|
| Claude Sonnet 4.6 | $3.00 | $15.00 |
| Claude Haiku 4.5 | $1.00 | $5.00 |

### Salesforce Licensing Reference (List Price)

| Product | Price |
|---------|-------|
| Sales Cloud Enterprise | $165/user/month |
| Financial Services Cloud Enterprise | $300/user/month |
| Agentforce Conversations | $2/conversation (legacy) |
| Agentforce Flex Credits | $500/100K credits (~$0.10/action) |
| Data Cloud Credits | $500/100K credits |
| Einstein Trust Layer | Included with Agentforce |

### AWS Infrastructure Reference

| Service | Price |
|---------|-------|
| Lambda | $0.20/1M requests + $0.0000166667/GB-sec |
| API Gateway (REST) | $3.50/1M requests |
| S3 + CloudFront | ~$5–10/month for static frontend |
| Bedrock Guardrails | Included with Bedrock usage |
| Secrets Manager | $0.40/secret/month |
| Fargate (Langfuse hosting) | ~$0.04/vCPU-hr + $0.004/GB-hr |

---

## Project-by-Project Breakdown

### Project 001: Hello World Agentforce

**What it is:** Bare SFDX scaffold. 1 agent, 4 topics, 1 Apex action. Validates toolchain and publish flow.

**Complexity:** Minimal. No AWS, no integrations, no custom objects beyond demo.

| Cost Category | Conservative | Baseline | Aggressive |
|---------------|-------------|----------|------------|
| **Build Labor** | 16 hrs × $150 = $2,400 | 24 hrs × $150 = $3,600 | 40 hrs × $150 = $6,000 |
| **Salesforce License** | $0 (Dev Edition) | $0 (Dev Edition) | $0 (Dev Edition) |
| **Agentforce Usage** | $0 (testing only) | $0 | $0 |
| **AWS** | $0 | $0 | $0 |
| **Monthly Run Cost** | $0 | $0 | $0 |
| **Year 1 Total** | **$2,400** | **$3,600** | **$6,000** |

**Key takeaway:** Near-zero cost. This is a learning exercise and toolchain validation.

---

### Project 002: Wealth Advisor Agent (CRM-Backed)

**What it is:** 6 topics, 4 Apex actions, 5 custom objects (Household, Client, Account, Goal, Meeting). SOQL-based data grounding. Real CRM data model for wealth management.

**Complexity:** Low-medium. Pure Salesforce, no external integrations.

| Cost Category | Conservative | Baseline | Aggressive |
|---------------|-------------|----------|------------|
| **Build Labor** | 40 hrs × $150 = $6,000 | 60 hrs × $150 = $9,000 | 80 hrs × $150 = $12,000 |
| **Salesforce License** | $0 (Dev Edition) | $0 (Dev Edition) | $300/user × 5 users × 12 mo = $18,000 (FSC) |
| **Agentforce Usage** | $0 (testing) | $50/mo × 12 = $600 | $200/mo × 12 = $2,400 |
| **Data API / Third Party** | $0 | $0 | $0 |
| **Monthly Run Cost** | $0 | ~$50 | ~$200 |
| **Year 1 Total** | **$6,000** | **$9,600** | **$32,400** |

**Notes:**
- Conservative assumes Dev Edition for prototyping only.
- Aggressive assumes FSC licensing for 5 pilot advisors in a real org — this is where Salesforce licensing dominates.

---

### Project 003: Wealth Advisor Agent (Data Cloud-Backed)

**What it is:** Same agent spec as 002, but swaps SOQL for `ConnectApi.CdpQuery` against Data Cloud DLMs. Demonstrates CRM vs Data Cloud grounding tradeoff.

**Complexity:** Medium. Adds Data Cloud provisioning, CRM Connector sync, DLM mapping.

| Cost Category | Conservative | Baseline | Aggressive |
|---------------|-------------|----------|------------|
| **Build Labor (incremental from 002)** | 24 hrs × $150 = $3,600 | 40 hrs × $150 = $6,000 | 60 hrs × $150 = $9,000 |
| **Salesforce License** | $0 (Dev Edition) | $0 (Dev Edition) | $300/user × 5 × 12 = $18,000 (FSC) |
| **Data Cloud Credits** | $0 (included in Dev Ed) | $500/100K × 2 packs = $1,000 | $500/100K × 6 packs = $3,000 |
| **Agentforce Usage** | $0 | $50/mo × 12 = $600 | $200/mo × 12 = $2,400 |
| **Monthly Run Cost** | $0 | ~$130 | ~$450 |
| **Year 1 Total** | **$3,600** | **$7,600** | **$32,400** |

**Notes:**
- Data Cloud credits are consumption-based. Small pilot with 5 households and 7 DLM tables consumes minimal credits.
- Aggressive scenario assumes ongoing Data Cloud usage with real client data volumes.

---

### Project 004: Wealth Advisor — Production Hardening (Phase 1–5)

**What it is:** Production-grade wealth advisor. 10 topics, 8 Apex actions, 8 custom objects (adds Transactions, Referrals, Audit Log). MCP connectors, Experience Cloud multi-channel deployment, RBAC, RAG, audit logging, performance testing.

**Complexity:** Medium-high. First project with MCP integration, multi-channel, and compliance features.

| Cost Category | Conservative | Baseline | Aggressive |
|---------------|-------------|----------|------------|
| **Build Labor (incremental from 003)** | 80 hrs × $150 = $12,000 | 120 hrs × $150 = $18,000 | 160 hrs × $150 = $24,000 |
| **Salesforce License** | $0 (Dev Edition) | $300/user × 5 × 12 = $18,000 | $300/user × 10 × 12 = $36,000 |
| **Data Cloud Credits** | $0 | $1,000 | $3,000 |
| **Agentforce Usage** | $0 | $100/mo × 12 = $1,200 | $400/mo × 12 = $4,800 |
| **Experience Cloud** | $0 | $0 (included w/ license) | $0 (included) |
| **Third-Party Data APIs** | $0 | $50/mo × 12 = $600 | $130/mo × 12 = $1,560 |
| **Monthly Run Cost** | $0 | ~$150 | ~$550 |
| **Year 1 Total** | **$12,000** | **$38,800** | **$69,360** |

**Notes:**
- MCP connectors (market data, news) require API subscriptions: Alpha Vantage ($50/mo), NewsAPI (free tier).
- Experience Cloud chat widget is included with Sales/Service Cloud licenses.
- RBAC, audit logging, and RAG are Salesforce-native features — no additional licensing.

---

### Project 005 (v1 + v2): Investment Research Agent — Cross-Platform Multi-Agent

**What it is:** Major architectural leap. Salesforce Agentforce orchestrator + AWS Lambda MCP servers + Strands agents + Langfuse governance. v2 adds compliance agent, MNPI enforcement, bidirectional AWS↔SF, SSE streaming, React frontend.

**Components:** 2 Agentforce agents, 16 topics, 24 Apex classes, 5 CRM objects, 7 Lambda functions, 3 MCP servers (11 tools), 2 Strands agents (8 tools), React frontend on S3/CloudFront, Langfuse observability.

| Cost Category | Conservative | Baseline | Aggressive |
|---------------|-------------|----------|------------|
| **Build Labor (v1 + v2)** | 240 hrs × $150 = $36,000 | 360 hrs × $150 = $54,000 | 480 hrs × $150 = $72,000 |
| **Salesforce License** | $0 (Dev Edition) | $300/user × 5 × 12 = $18,000 | $300/user × 15 × 12 = $54,000 |
| **Agentforce Usage** | $0 | $200/mo × 12 = $2,400 | $500/mo × 12 = $6,000 |
| **AWS — Bedrock LLM** | | | |
| — Sonnet 4.6 (analysis, pipeline) | $50/mo × 12 = $600 | $200/mo × 12 = $2,400 | $800/mo × 12 = $9,600 |
| — Haiku (routing, simple queries) | $10/mo × 12 = $120 | $50/mo × 12 = $600 | $200/mo × 12 = $2,400 |
| **AWS — Lambda + API Gateway** | $10/mo × 12 = $120 | $25/mo × 12 = $300 | $60/mo × 12 = $720 |
| **AWS — S3 + CloudFront** | $5/mo × 12 = $60 | $10/mo × 12 = $120 | $20/mo × 12 = $240 |
| **Langfuse (cloud)** | $0 (free tier) | $29/mo × 12 = $348 | $59/mo × 12 = $708 |
| **Third-Party Data APIs** | | | |
| — Alpha Vantage (Standard) | $50/mo × 12 = $600 | $50/mo × 12 = $600 | $50/mo × 12 = $600 |
| — Tavily (Pro) | $50/mo × 12 = $600 | $50/mo × 12 = $600 | $50/mo × 12 = $600 |
| — SEC EDGAR | $0 (free, public) | $0 | $0 |
| **Monthly Run Cost** | ~$175 | ~$615 | ~$1,690 |
| **Year 1 Total** | **$38,100** | **$79,368** | **$146,868** |

**Notes:**
- Bedrock LLM cost is the most variable line item. Conservative assumes light testing (~50 research briefs/month). Aggressive assumes 15 analysts running 10+ queries/day.
- Strands agents on Lambda use Bedrock — their LLM cost is included in the Bedrock line.
- Amazon Comprehend (used by Sentiment Agent in 005) adds ~$10–50/month depending on volume — included in Lambda line.
- The React frontend is static (S3 + CloudFront) — negligible cost.

---

### Project 006: OpenClaw + Salesforce + AWS (Full Runtime Replatform)

**What it is:** Complete runtime swap. OpenClaw on Bedrock AgentCore replaces Agentforce as agent runtime. AutoResearchClaw 23-stage pipeline with 3 HITL gates. 3 MCP servers, financial modeling skills (DCF, comps, Monte Carlo), multi-channel (Slack, WhatsApp, Telegram, Discord, Web), dual trust layer (Bedrock Guardrails + Einstein Trust Layer via SF Models API), MuleSoft action execution (Phase 6).

**Build timeline:** 10 weeks across 6 phases.

| Cost Category | Conservative | Baseline | Aggressive |
|---------------|-------------|----------|------------|
| **Build Labor (10 weeks)** | 320 hrs × $150 = $48,000 | 480 hrs × $150 = $72,000 | 640 hrs × $150 = $96,000 |
| **Salesforce License** | $0 (Dev/Scratch) | $300/user × 5 × 12 = $18,000 | $300/user × 15 × 12 = $54,000 |
| **Agentforce Usage** | $0 (not used) | $0 (not used) | $0 (not used) |
| **AWS — Bedrock LLM** | | | |
| — Sonnet 4.6 (L3-L5, pipeline) | $100/mo × 12 = $1,200 | $400/mo × 12 = $4,800 | $1,500/mo × 12 = $18,000 |
| — Haiku 4.5 (L1-L2, routing) | $20/mo × 12 = $240 | $80/mo × 12 = $960 | $300/mo × 12 = $3,600 |
| **AWS — AgentCore (serverless)** | $10/mo × 12 = $120 | $30/mo × 12 = $360 | $100/mo × 12 = $1,200 |
| **AWS — Lambda + API Gateway** | $10/mo × 12 = $120 | $25/mo × 12 = $300 | $60/mo × 12 = $720 |
| **AWS — S3 + CloudFront** | $5/mo × 12 = $60 | $10/mo × 12 = $120 | $20/mo × 12 = $240 |
| **Langfuse (self-hosted, Fargate)** | $30/mo × 12 = $360 | $50/mo × 12 = $600 | $100/mo × 12 = $1,200 |
| **Third-Party Data APIs** | | | |
| — Alpha Vantage (Standard) | $50/mo × 12 = $600 | $50/mo × 12 = $600 | $50/mo × 12 = $600 |
| — Polygon.io (Starter) | $0 | $29/mo × 12 = $348 | $29/mo × 12 = $348 |
| — EODHD (All-World) | $0 | $80/mo × 12 = $960 | $80/mo × 12 = $960 |
| — Tavily (Pro) | $50/mo × 12 = $600 | $50/mo × 12 = $600 | $50/mo × 12 = $600 |
| — SEC EDGAR | $0 | $0 | $0 |
| **MuleSoft (Phase 6)** | $0 (not built) | $2,000/mo × 6 = $12,000 | $5,000/mo × 12 = $60,000 |
| **Monthly Run Cost** | ~$275 | ~$805 | ~$2,290 |
| **Year 1 Total** | **$51,300** | **$111,648** | **$237,468** |

**Notes:**
- OpenClaw is MIT open-source — zero licensing cost. AgentCore is serverless pay-per-use.
- 006 does NOT use Agentforce — Salesforce is data-only. No Agentforce conversation charges.
- MuleSoft is the wildcard. Conservative skips Phase 6 entirely. Baseline assumes 6 months of MuleSoft at a negotiated rate. Aggressive assumes full-year MuleSoft with trade execution, wires, KYC.
- MuleSoft pricing is enterprise-negotiated and opaque. The $2K–$5K/month range reflects typical small-deployment vCore costs based on industry benchmarks.
- Bedrock LLM cost is higher than 005 because the 23-stage pipeline is token-intensive. A single deep research brief can consume 100K–500K tokens.
- Self-hosted Langfuse on Fargate (1 vCPU, 2GB) runs ~$30/month. Production with more capacity runs $50–100/month.

---

## Consolidated Summary: All Projects

### Year 1 Total Cost by Scenario

| Project | Conservative | Baseline | Aggressive |
|---------|-------------|----------|------------|
| 001 — Hello World | $2,400 | $3,600 | $6,000 |
| 002 — Wealth Advisor (CRM) | $6,000 | $9,600 | $32,400 |
| 003 — Wealth Advisor (Data Cloud) | $3,600 | $7,600 | $32,400 |
| 004 — Wealth Advisor (Production) | $12,000 | $38,800 | $69,360 |
| 005 — Investment Research (Multi-Agent) | $38,100 | $79,368 | $146,868 |
| 006 — OpenClaw Replatform | $51,300 | $111,648 | $237,468 |
| **TOTAL** | **$113,400** | **$250,616** | **$524,496** |

### Year 1 Cost by Category (Baseline Scenario)

| Category | Amount | % of Total |
|----------|--------|------------|
| Engineering Labor | $162,600 | 65% |
| Salesforce Licensing (FSC) | $54,000 | 22% |
| MuleSoft (006 Phase 6, 6 months) | $12,000 | 5% |
| AWS Bedrock LLM (Sonnet + Haiku) | $8,760 | 3% |
| Agentforce Consumption | $4,200 | 2% |
| Third-Party Data APIs | $3,708 | 1% |
| Data Cloud Credits | $2,000 | 1% |
| AWS Infrastructure (Lambda, API GW, S3, AgentCore) | $1,200 | <1% |
| Langfuse (cloud + self-hosted) | $948 | <1% |
| **Total** | **$250,616** | **100%** |

---

## Scenario Definitions

### Conservative — "Prove the Concept"
- Dev Edition / scratch orgs only (zero Salesforce licensing)
- 1 engineer, part-time on each project
- No MuleSoft integration
- Light LLM usage (testing and demos only)
- No production deployment — everything stays in prototype
- **Who this is for:** Innovation lab validating feasibility before requesting budget

### Baseline — "Pilot with Real Users"
- FSC licensing for 5 pilot users (005 + 006)
- 1 full-time engineer + part-time architect
- MuleSoft for 6 months (Phase 6 of 006)
- Moderate LLM usage (5–10 analysts, daily queries)
- Single production environment, reproducible from git
- **Who this is for:** Business unit running a controlled pilot with real advisors/analysts

### Aggressive — "Production at Scale"
- FSC licensing for 15 users across 005 + 006
- 1.5 FTE engineers (surge capacity for 006's 10-week build)
- Full-year MuleSoft with trade execution
- Heavy LLM usage (15+ analysts, 10+ queries/day, full pipeline runs)
- Multi-channel deployment (Slack, WhatsApp, Web)
- **Who this is for:** Firm committed to production deployment with real trade execution

---

## Cost Drivers and Sensitivities

### 1. Engineering Labor (Largest Cost — 65% of Baseline)
Labor is the dominant cost because these are custom-built systems, not off-the-shelf products. The progressive build approach mitigates this — each project reuses code from the previous one (005 reuses 002/003/004's CRM patterns, 006 reuses 005's MCP servers). A second full-time engineer accelerates delivery but increases cost proportionally.

### 2. Salesforce Licensing (22% of Baseline)
FSC at $300/user/month is the single biggest recurring line item once you move past prototyping. For 15 users over 12 months, that's $54,000 — before any Agentforce or Data Cloud consumption. Negotiation levers: multi-year commitment, bundling with existing Salesforce contracts, or using Sales Cloud Enterprise ($165/user) instead of FSC where FinServ__* objects aren't required.

### 3. Bedrock LLM Tokens (Largest Variable Cost)
A single 23-stage research brief in 006 can consume 200K–500K tokens (input + output). At Sonnet 4.6 rates ($3/$15 per 1M tokens), that's $1–$5 per brief. At 20 briefs/day, that's $20–$100/day or $600–$3,000/month. The tiered model strategy (Haiku for L1-L2, Sonnet for L3-L5) reduces this by routing ~80% of daily query volume to the cheaper model.

### 4. MuleSoft (006 Phase 6 Only — 5% of Baseline)
MuleSoft pricing is enterprise-negotiated and can range from $1,500/month for a minimal deployment to $10,000+/month for production with multiple vCores and high-throughput APIs. If trade execution isn't required, skip Phase 6 entirely and save $12K–$60K/year.

### 5. Third-Party Data APIs (Fixed, Small — 1% of Baseline)
Alpha Vantage ($50/mo), Tavily ($50/mo), Polygon ($29/mo), EODHD ($80/mo) are fixed subscription costs totaling $130–$210/month. These are table stakes for any financial data application and don't scale with usage.

---

## What You Get for the Money

| Investment Level | What's Delivered | Business Value |
|-----------------|-----------------|----------------|
| **$113K (Conservative)** | 6 working prototypes, validated architecture, zero licensing cost | Proof of feasibility. Board-ready demo. Architecture decision (005 vs 006) informed by real builds. |
| **$251K (Baseline)** | Production pilot with 5 real users, compliance-ready, auditable, multi-channel | 5 analysts/advisors producing research 3–5x faster. FINRA-ready audit trail. Real ROI data for scale decision. |
| **$524K (Aggressive)** | Full production system, 15 users, trade execution, multi-channel, dual trust layer | Operational system replacing manual research workflow. Measurable headcount efficiency. Competitive advantage in wealth transfer capture. |

---

## 005 vs 006: Cost Comparison

A key decision point is whether to invest in 005 (Agentforce + Strands + AWS) or 006 (OpenClaw + Salesforce + AWS). Both deliver similar research capabilities, but with different cost profiles.

| Dimension | 005 | 006 |
|-----------|-----|-----|
| Agentforce licensing | Yes — $2/conversation or Flex Credits | No — OpenClaw is MIT, free |
| Agent runtime cost | Salesforce (included in license) + AWS Lambda | AWS AgentCore (serverless, pay-per-use) |
| LLM cost | Bedrock (Strands agents only) | Bedrock (all queries — higher token volume) |
| Salesforce role | Agent platform + data platform | Data platform only |
| MuleSoft | Not included | Phase 6 ($12K–$60K/year) |
| Channels | 3 (Web, Slack, Agent API) | 12+ (Slack, WhatsApp, Telegram, Discord, Web, API) |
| Vendor lock-in | Agentforce (Salesforce proprietary) | OpenClaw (MIT open-source) |
| Build complexity | Higher (~16,590 lines, Apex + Python + 2 runtimes) | Lower (~7,870 lines, single runtime) |

**Bottom line:** 006 has lower Salesforce consumption costs (no Agentforce charges) but higher AWS costs (all reasoning runs on Bedrock). For high-volume usage (15+ analysts), 006 is cheaper because Bedrock token costs scale more favorably than Agentforce per-conversation pricing. For low-volume usage (< 5 analysts), 005 may be cheaper because Agentforce conversations are infrequent.

---

## Recommendation

Start with **Baseline** (~$251K). It delivers a production-ready pilot with real users and real compliance controls, while keeping MuleSoft exposure limited to 6 months. The pilot generates the ROI data needed to justify (or kill) the Aggressive scenario.

The Conservative scenario ($113K) is appropriate only if the goal is pure R&D with no near-term production intent. The Aggressive scenario ($524K) should only be pursued after the Baseline pilot proves analyst adoption and measurable time savings.

---

## Sources

- AWS Bedrock pricing: [pecollective.com](https://pecollective.com/tools/aws-bedrock-pricing/), [wring.co](https://wring.co/blog/aws-bedrock-pricing-guide)
- Salesforce Agentforce pricing: [magicfuse.co](https://magicfuse.co/blog/agentforce-cost/), [redresscompliance.com](https://redresscompliance.com/salesforce-agentforce-pricing-evolution-2026.html)
- Salesforce FSC licensing: [redresscompliance.com](https://redresscompliance.com/salesforce-financial-services-cloud-licensing.html)
- Salesforce Data Cloud pricing: [redresscompliance.com](https://www.redresscompliance.com/salesforce-data-cloud-pricing.html)
- AWS Lambda/API Gateway pricing: [wring.co](https://wring.co/blog/aws-lambda-pricing-guide)
- Langfuse pricing: [langfuse.com](https://langfuse.com/pricing), [langfuse.com/pricing-self-host](https://langfuse.com/pricing-self-host)
- MuleSoft licensing: [atonementlicensing.com](https://atonementlicensing.com/blog/mulesoft-licensing/)
- Content was rephrased for compliance with licensing restrictions.
