# Monthly Service Costs: Projects 001–006

> Date: April 21, 2026
> Audience: C-Level / Executive Steering Committee
> Scope: Monthly recurring service and infrastructure costs only — no engineering labor
> Exclusion: Project 007 is out of scope

---

## Conservative — "Prove the Concept"

Dev Edition orgs, free tiers, testing only. No production users.

| Service | 001–003 | 004 | 005 | 006 |
|---------|---------|-----|-----|-----|
| SF License | $0 | $0 | $0 | $0 |
| Agentforce | $0 | $0 | $0 | $0 |
| Data Cloud | $0 | $0 | $0 | $0 |
| Bedrock Sonnet 4.6 | $0 | $0 | $50 | $100 |
| Bedrock Haiku 4.5 | $0 | $0 | $10 | $20 |
| AgentCore | $0 | $0 | $0 | $10 |
| Lambda + API Gateway | $0 | $0 | $10 | $10 |
| S3 + CloudFront | $0 | $0 | $5 | $5 |
| Langfuse | $0 | $0 | $0 | $30 |
| Alpha Vantage | $0 | $0 | $50 | $50 |
| Polygon.io | $0 | $0 | $0 | $0 |
| EODHD | $0 | $0 | $0 | $0 |
| Tavily | $0 | $0 | $50 | $50 |
| MuleSoft | $0 | $0 | $0 | $0 |
| **Total** | **$0** | **$0** | **$175** | **$275** |

---

## Baseline — "Pilot with 5 Users"

FSC licensing for 5 pilot users. Moderate LLM usage. MuleSoft for 006 Phase 6.

| Service | 001–003 | 004 | 005 | 006 |
|---------|---------|-----|-----|-----|
| SF License (FSC ×5) | $0 | $1,500 | $1,500 | $1,500 |
| Agentforce | $50 | $100 | $200 | $0 |
| Data Cloud | $83 | $83 | $0 | $0 |
| Bedrock Sonnet 4.6 | $0 | $0 | $200 | $400 |
| Bedrock Haiku 4.5 | $0 | $0 | $50 | $80 |
| AgentCore | $0 | $0 | $0 | $30 |
| Lambda + API Gateway | $0 | $0 | $25 | $25 |
| S3 + CloudFront | $0 | $0 | $10 | $10 |
| Langfuse | $0 | $0 | $29 | $50 |
| Alpha Vantage | $0 | $50 | $50 | $50 |
| Polygon.io | $0 | $0 | $0 | $29 |
| EODHD | $0 | $0 | $0 | $80 |
| Tavily | $0 | $0 | $50 | $50 |
| MuleSoft | $0 | $0 | $0 | $2,000 |
| **Total** | **$133** | **$1,733** | **$2,114** | **$4,304** |

---

## Aggressive — "Production with 15 Users"

FSC licensing for 15 users. Heavy LLM usage (15+ analysts, 10+ queries/day). Full-year MuleSoft with trade execution.

| Service | 001–003 | 004 | 005 | 006 |
|---------|---------|-----|-----|-----|
| SF License (FSC ×15) | $0 | $3,000 | $4,500 | $4,500 |
| Agentforce | $200 | $400 | $500 | $0 |
| Data Cloud | $250 | $250 | $0 | $0 |
| Bedrock Sonnet 4.6 | $0 | $0 | $800 | $1,500 |
| Bedrock Haiku 4.5 | $0 | $0 | $200 | $300 |
| AgentCore | $0 | $0 | $0 | $100 |
| Lambda + API Gateway | $0 | $0 | $60 | $60 |
| S3 + CloudFront | $0 | $0 | $20 | $20 |
| Langfuse | $0 | $0 | $59 | $100 |
| Alpha Vantage | $0 | $50 | $50 | $50 |
| Polygon.io | $0 | $0 | $0 | $29 |
| EODHD | $0 | $0 | $0 | $80 |
| Tavily | $0 | $0 | $50 | $50 |
| MuleSoft | $0 | $0 | $0 | $5,000 |
| **Total** | **$450** | **$3,700** | **$6,239** | **$11,789** |

---

## Monthly Totals — All Projects Combined

| Scenario | 001–003 | 004 | 005 | 006 | Combined |
|----------|---------|-----|-----|-----|----------|
| Conservative | $0 | $0 | $175 | $275 | **$450** |
| Baseline | $133 | $1,733 | $2,114 | $4,304 | **$8,284** |
| Aggressive | $450 | $3,700 | $6,239 | $11,789 | **$22,178** |

---

## Annualized Service Costs (No Labor)

| Scenario | Monthly | Annual |
|----------|---------|--------|
| Conservative | $450 | **$5,400** |
| Baseline | $8,284 | **$99,408** |
| Aggressive | $22,178 | **$266,136** |

---

## Cost Distribution (Baseline)

| Category | Monthly | % of Total |
|----------|---------|------------|
| Salesforce FSC Licensing | $4,500 | 54% |
| MuleSoft (006 only) | $2,000 | 24% |
| Bedrock LLM (Sonnet + Haiku) | $730 | 9% |
| Agentforce Consumption | $350 | 4% |
| Third-Party Data APIs | $309 | 4% |
| Data Cloud Credits | $166 | 2% |
| AWS Infrastructure (Lambda, API GW, S3, AgentCore) | $100 | 1% |
| Langfuse | $79 | 1% |
| **Total** | **$8,284** | **100%** |

---

## Key Observations

1. **Salesforce licensing is 54% of the Baseline monthly bill.** It's the single biggest lever. Negotiating a 25% discount on FSC saves $1,125/month ($13,500/year). Using Sales Cloud Enterprise ($165/user) instead of FSC where FinServ__* objects aren't needed cuts the line in half.

2. **MuleSoft is 24% of Baseline — and entirely optional.** Skip 006 Phase 6 (trade execution) and the combined monthly drops from $8,284 to $6,284. MuleSoft only matters if you need the agent to execute trades, wires, and KYC — not just research.

3. **Bedrock LLM is 9% of Baseline but the most volatile line.** A single 23-stage research brief in 006 costs $1–$5 in tokens. At 20 briefs/day, Bedrock alone hits $600–$3,000/month. The tiered model strategy (Haiku for 80% of queries, Sonnet for complex analysis) keeps this manageable.

4. **006 eliminates Agentforce charges.** OpenClaw is MIT open-source, AgentCore is serverless pay-per-use. The tradeoff: higher Bedrock token spend since all reasoning runs on AWS instead of Salesforce.

5. **AWS infrastructure (Lambda, API Gateway, S3, CloudFront) is negligible.** Under $100/month combined across all projects. Serverless pricing at pilot scale is essentially free.

6. **Conservative scenario is nearly free.** $450/month total — just data API subscriptions and light Bedrock usage. Everything else runs on Dev Edition free tiers.

---

## Sources

- AWS Bedrock pricing: [pecollective.com](https://pecollective.com/tools/aws-bedrock-pricing/)
- Salesforce FSC licensing: [redresscompliance.com](https://redresscompliance.com/salesforce-financial-services-cloud-licensing.html)
- Salesforce Agentforce pricing: [redresscompliance.com](https://redresscompliance.com/salesforce-agentforce-pricing-evolution-2026.html)
- MuleSoft licensing: [atonementlicensing.com](https://atonementlicensing.com/blog/mulesoft-licensing/)
- Content was rephrased for compliance with licensing restrictions.
