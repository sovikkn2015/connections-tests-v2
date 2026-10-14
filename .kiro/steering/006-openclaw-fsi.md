---
inclusion: fileMatch
fileMatchPattern: "my-agent-project-006-v1-openclaw-salesforce-aws/**"
---

# Project 006 v1: OpenClaw + Salesforce + AWS — Steering

Note: This steering applies to the v1 (Phases 1–5, no MuleSoft) tree.
For the Phase 6 MuleSoft work, see `.kiro/steering/006-v2-mulesoft.md`.

## Design Documents (Source of Truth)
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/design-doc.md]]
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/006-tech-stack-assessment.md]]
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/006-query-matrix-expanded.md]]
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/006-data-sources-and-evaluation-strategy.md]]
- #[[file:my-agent-project-006-v1-openclaw-salesforce-aws/docs/006-frontend-assessment-openclaw.md]]

## Architecture Rules (Non-Negotiable)

### Agent Runtime
1. OpenClaw is the ONLY agent runtime. No Agentforce, no Strands, no custom agent loops.
2. OpenClaw runs on AWS Bedrock AgentCore. Serverless. Zero idle cost.
3. All agent communication goes through OpenClaw's Gateway API (WebSocket primary, REST fallback).
4. AutoResearchClaw is the pipeline framework. Fork and adapt — do NOT build a custom pipeline.

### LLM
5. Claude Sonnet 4.6 (Bedrock) for L3-L5 queries and pipeline stages.
6. Claude Haiku 4.6 (Bedrock) for L1-L2 queries.
7. NO Amazon Comprehend. NO FinBERT. The LLM handles all sentiment analysis.
8. NO GPT/OpenAI. Everything runs through Bedrock.

### MCP Servers
9. All MCP servers run on Lambda + API Gateway.
10. MCP protocol compliance required: GET / (info), POST /tools/list (catalog), POST /tools/call (invoke).
11. Three MCP servers: SEC EDGAR, Market Data (Alpha Vantage primary), News (Tavily primary).
12. Every MCP tool must have a JSON Schema definition in tools/list response.

### Salesforce
13. Salesforce is the data platform, NOT the agent platform.
14. CRM access happens server-side via OpenClaw's salesforce-api skill. Frontend does NOT call SF APIs directly for agent queries.
15. Custom objects: IR_Research_Note__c, IR_Coverage__c, IR_Watchlist__c, IR_Company__c, IR_Audit_Log__c.
16. FSC objects: FinServ__FinancialAccount__c, FinServ__FinancialHolding__c.
17. Every agent action must write to IR_Audit_Log__c (FINRA requirement).

### Frontend
18. React 19 + TypeScript + Vite 6 + Zustand 5 + Recharts + SLDS.
19. Frontend connects to OpenClaw via WebSocket (not Salesforce Agent API).
20. SF OAuth2 PKCE for user identity only. Agent communication via OpenClaw Bearer token.
21. All research panel components are backend-agnostic (render from Zustand state, not API-specific types).

### Security
22. Zero credentials in git. All secrets in AWS Secrets Manager.
23. Bedrock Guardrails for all LLM calls (PII masking, toxicity, denied topics, prompt injection).
24. SF Models API for CRM data reasoning (Einstein Trust Layer).
25. HITL required for ALL MuleSoft actions. No autonomous trade/wire/account execution.
26. MNPI fields NEVER sent to LLM prompts or stored in OpenClaw memory.

### Deployment
27. ONE environment. No dev/staging/production split.
28. Everything reproducible from git: sf org create + sf project deploy + sam deploy.
29. Seed data via Apex scripts. No manual data entry.
30. No click-ops. If it can't be scripted, it doesn't belong in the build.

## Build Order (from design doc)
Phase 1 (wk 1-2): OpenClaw on AgentCore + SF objects + seed data + Langfuse + Slack
Phase 2 (wk 2-3): 3 MCP servers on Lambda (SEC EDGAR, Market Data, News)
Phase 3 (wk 3-5): AutoResearchClaw fork, FSI adaptation, SF publish + audit
Phase 4 (wk 5-6): Financial modeling skills (DCF, comps, Monte Carlo, sentiment via LLM)
Phase 5 (wk 6-8): Production hardening, dual trust layer, multi-channel, eval suite, frontend
Phase 6 (wk 8-10): MuleSoft action execution with HITL

DO NOT skip phases. Each phase depends on the previous. If Phase 3 fails, Phases 1-2 still work.

## 005 Mistakes to Avoid
- DO NOT bypass the agent with direct API calls from the frontend (005 Gap 1)
- DO NOT use plain HTTP when the design says WebSocket/MCP/A2A (005 Gap 2, 8)
- DO NOT stub critical features and call them done (005 Gap 10 — research brief was a stub)
- DO NOT simulate streaming when real streaming is available (005 Gap 7)
- DO NOT skip MNPI enforcement — implement it from Phase 1 (005 Gap 17)
- DO NOT hardcode credentials anywhere (005 credential finding)
- DO NOT build custom pipelines when AutoResearchClaw already exists
- DO NOT add Comprehend/FinBERT — the LLM handles sentiment (006 tech stack assessment)
