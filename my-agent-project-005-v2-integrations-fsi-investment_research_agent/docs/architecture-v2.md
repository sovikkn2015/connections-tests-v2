# Project 005 V2 — Implemented Architecture

## Architecture Diagram (ASCII)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ LANGFUSE (us.cloud.langfuse.com)                                            │
│ 30+ traces │ Spans │ Generations │ Prompt Registry │ Cross-platform audit   │
│ ← SF pushes via @future │ AWS pushes via Python SDK →                       │
└──────────────────────────────┬──────────────────────────────────────────────┘
                               │
┌══════════════════════════════╪══════════════════════════════════════════════┐
║ SALESFORCE (Agentforce)                                                    ║
║                              │                                             ║
║  ┌───────────────────────────┴───────────────────────────────────────────┐ ║
║  │ IR RESEARCH ORCHESTRATOR (Agentforce, Atlas Reasoning Engine)         │ ║
║  │ 12 Topics → routes queries to actions                                 │ ║
║  │                                                                       │ ║
║  │ CRM Topics (SOQL)     Cross-Platform (A2A/MCP)    Orchestration       │ ║
║  │ ┌──────────────┐      ┌──────────────────────┐   ┌────────────────┐  │ ║
║  │ │company_lookup│      │financial_analysis ────┼─→│research_brief  │  │ ║
║  │ │coverage_check│      │  (Strands Agent A2A)  │   │ (calls all 7   │  │ ║
║  │ │earnings_cal  │      │sentiment_analysis ────┼─→│  actions, saves │  │ ║
║  │ │watchlist     │      │  (Strands Agent A2A)  │   │  IR_Research_  │  │ ║
║  │ └──────┬───────┘      │sec_filings ───────────┼─→│  Note__c)      │  │ ║
║  │        │              │  (SEC EDGAR MCP)      │   └────────────────┘  │ ║
║  │        │              │market_data ───────────┼─→ MCP                 │ ║
║  │        │              │news_search ───────────┼─→ MCP                 │ ║
║  │        │              └──────────┬────────────┘                       │ ║
║  │        ▼                         │ Custom Labels (URL + API Key)      │ ║
║  │   CRM SOQL                       │ HTTP + x-api-key header            │ ║
║  └──────────────────────────────────┼───────────────────────────────────┘ ║
║                                     │                                     ║
║  ┌──────────────────┐  ┌────────────┴─────┐  ┌────────────────────────┐  ║
║  │IR_COMPLIANCE     │  │IR_McpServer      │  │ CRM Objects            │  ║
║  │AGENT             │  │Endpoint          │  │ IR_Company__c          │  ║
║  │(separate agent)  │  │(@RestResource    │  │ IR_Coverage__c         │  ║
║  │                  │  │ /ir-mcp/*)       │  │ IR_Watchlist__c        │  ║
║  │Topics:           │  │                  │  │ IR_Research_Note__c    │  ║
║  │ restricted_list  │  │Exposes CRM to    │  │ IR_Audit_Log__c       │  ║
║  │ trading_window   │  │AWS agents:       │  │                        │  ║
║  │ mnpi_check       │  │ get_analyst_cov  │  │ IR_MnpiGuard enforces  │  ║
║  │ full_screening   │  │ get_company_info │  │ PUBLIC / INTERNAL /    │  ║
║  │                  │  │ get_holdings     │  │ CONFIDENTIAL /         │  ║
║  │Uses:             │  │ get_meetings     │  │ RESTRICTED             │  ║
║  │IR_Compliance     │  │                  │  │                        │  ║
║  │ScreeningAction   │  │MNPI-filtered:    │  │ CONFIDENTIAL never     │  ║
║  │IR_MnpiCheckAction│  │holdings blocked  │  │ crosses to AWS         │  ║
║  │IR_MnpiGuard      │  │for external call │  │ RESTRICTED = compliance│  ║
║  └──────────────────┘  └──────────────────┘  └────────────────────────┘  ║
║                                                                           ║
║  IR_AgentApiProxy (@RestResource /ir-agent/chat/)                         ║
║  IR_DataCloudAction (CdpQuery → SOQL fallback)                            ║
║  IR_ExperienceCloudHelper (channel setup docs)                            ║
╚═══════════════════════════════╤═══════════════════════════════════════════╝
                                │
                                │ HTTPS + x-api-key
                                │ ↓ A2A: natural language → agent reasons
                                │ ↓ MCP: /tools/list, /tools/call
                                │ ↑ Bidirectional: AWS → SF via OAuth2
                                │
╔═══════════════════════════════╪═══════════════════════════════════════════╗
║ AWS (us-east-1)                                                          ║
║                               │                                          ║
║  ┌────────────────────────────┴────────────────────────────────────────┐ ║
║  │ API GATEWAY — 7 Lambda functions                                    │ ║
║  └──┬──────────┬──────────┬──────────┬──────────┬──────────┬──────────┘ ║
║     ▼          ▼          ▼          ▼          ▼          ▼            ║
║  ┌────────┐┌────────┐┌────────┐                                        ║
║  │SEC     ││Market  ││News   │  MCP SERVERS (MCP Protocol)             ║
║  │EDGAR   ││Data    ││Search │  GET /         → server info             ║
║  │        ││        ││       │  POST /tools/list → tool catalog         ║
║  │get_10k ││get_quot││search │  POST /tools/call → invoke by name       ║
║  │get_10q ││get_hist││get_hdl│                                          ║
║  │get_8k  ││get_cons││get_snt│  Data: SEC EDGAR API, Alpha Vantage,    ║
║  │get_ins ││get_opts││       │  Tavily (all real external APIs)         ║
║  └────────┘└────────┘└────────┘                                        ║
║                                                                         ║
║  ┌──────────────────────────────┐ ┌──────────────────────────────────┐  ║
║  │ FINANCIAL ANALYSIS AGENT     │ │ SENTIMENT ANALYSIS AGENT         │  ║
║  │ (Strands SDK + Bedrock)      │ │ (Strands SDK + Bedrock +         │  ║
║  │                              │ │  Amazon Comprehend)              │  ║
║  │ @tool run_dcf                │ │ @tool analyze_transcript         │  ║
║  │ @tool run_comps              │ │   → Comprehend DetectSentiment   │  ║
║  │ @tool monte_carlo            │ │   → Comprehend DetectEntities    │  ║
║  │ @tool fair_value             │ │   → Comprehend DetectKeyPhrases  │  ║
║  │                              │ │ @tool score_news_sentiment       │  ║
║  │ POST /agent ← A2A endpoint  │ │ @tool detect_tone_shifts         │  ║
║  │   Agent reasons, picks tools │ │ @tool aggregate_sentiment        │  ║
║  │                              │ │                                  │  ║
║  │ salesforce_client.py ────────┼─┼──→ OAuth2 → SF /ir-mcp          │  ║
║  │   for CRM context enrichment │ │    (bidirectional)               │  ║
║  └──────────────────────────────┘ └──────────────────────────────────┘  ║
║                                                                         ║
║  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────────────┐ ║
║  │ SSE Proxy    │  │ Token Proxy  │  │ S3 + CloudFront              │ ║
║  │ /sse-proxy   │  │ /oauth/token │  │ React frontend (SLDS)        │ ║
║  └──────────────┘  └──────────────┘  └───────────────────────────────┘ ║
╚═════════════════════════════════════════════════════════════════════════╝
```


## Protocol Map

| Protocol | Direction | Implementation |
|----------|-----------|----------------|
| MCP | SF → AWS Lambda MCP Servers | Apex HTTP callout, MCP tools/list + tools/call |
| A2A | SF → AWS Strands Agents | Apex HTTP to /agent endpoint, agent reasons autonomously |
| Bidirectional | AWS → SF | salesforce_client.py OAuth2 → /ir-mcp REST endpoint |
| SSE | Frontend → AWS → Strands | SSE proxy Lambda, text/event-stream |
| OAuth2 PKCE | Frontend → SF | Token proxy Lambda, Connected App |
| Langfuse | Both → Langfuse Cloud | Apex @future + Python SDK |

## Data Flow: "Deep dive on NVIDIA"

```
1. Analyst → Orchestrator (Agentforce, 12 topics)
2. → CRM: company_lookup (IR_Company__c SOQL)
3. → CRM: coverage_check (IR_Coverage__c SOQL)
4. → MCP: SEC EDGAR get_10k (real SEC filings via Lambda)
5. → MCP: Market Data get_quote (real Alpha Vantage via Lambda)
6. → A2A: Financial Analysis Agent (Strands @tool: DCF + comps + Monte Carlo + Bedrock narrative)
7. → A2A: Sentiment Analysis Agent (Strands @tool: Comprehend NLP + Bedrock synthesis)
8. → Compliance Agent (separate Agentforce agent: restricted list + trading window + MNPI)
9. → Orchestrator assembles IR_Research_Note__c
10. → Returns brief to analyst
11. → Langfuse: full trace with spans across both platforms
12. → IR_Audit_Log__c: compliance record in CRM
```

## Component Inventory

| Component | Count | Platform |
|-----------|-------|----------|
| Agentforce Agents | 2 (Orchestrator + Compliance) | Salesforce |
| Agent Topics | 16 (12 orchestrator + 4 compliance) | Salesforce |
| Apex Classes | 24 | Salesforce |
| CRM Objects | 5 | Salesforce |
| Custom Labels | 2 (AWS URL + API Key) | Salesforce |
| Lambda Functions | 7 | AWS |
| MCP Servers | 3 (11 tools total) | AWS |
| Strands Agents | 2 (8 @tool functions) | AWS |
| AI Services | Bedrock Claude + Comprehend | AWS |
| Frontend | React + SLDS on S3/CloudFront | AWS |
| Governance | Langfuse Cloud (30+ traces) | Cross-platform |

## Gap Closure Status (V2)

| # | Gap | Status |
|---|-----|--------|
| 1 | Agent API | ✅ CLOSED — IR_AgentApiProxy |
| 2 | A2A Protocol | ✅ CLOSED — Strands /agent endpoints, live SF→AWS |
| 3 | Strands SDK | ✅ CLOSED — @tool decorators, Agent + BedrockModel |
| 5 | Compliance Agent | ✅ CLOSED — Separate IR_Compliance_Agent |
| 6 | Data Cloud | ✅ CLOSED — CdpQuery → SOQL fallback |
| 7 | SSE Streaming | ✅ CLOSED — SSE proxy Lambda |
| 8 | MCP Protocol | ✅ CLOSED — McpServer class, tools/list + tools/call |
| 9 | SF as MCP Server | ✅ CLOSED — IR_McpServerEndpoint |
| 10 | Research Brief | ✅ CLOSED — 7-action orchestration → IR_Research_Note__c |
| 11 | Comprehend | ✅ CLOSED — DetectSentiment/Entities/KeyPhrases |
| 12 | Channels | ✅ CLOSED — IR_ExperienceCloudHelper |
| 17 | MNPI Enforcement | ✅ CLOSED — IR_MnpiGuard, 4 classification levels |
| 18 | Bidirectional | ✅ CLOSED — salesforce_client.py OAuth2 → /ir-mcp |
