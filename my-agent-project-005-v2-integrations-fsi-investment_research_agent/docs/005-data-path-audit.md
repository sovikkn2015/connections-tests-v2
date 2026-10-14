# 005 V2 — Data Path Audit: What's Real vs Seed Data

> Date: April 18, 2026
> Purpose: Transparent accounting of every data path in the 005 V2 system

---

## Summary

The 005 V2 system has two independent data paths that serve different parts of the UI. The **chat panel** (left) returns real, live-computed data from AWS Lambda and Salesforce. The **research panel** (right) displays hardcoded seed data from a static TypeScript file. These two paths are not connected — the research panel never updates from backend responses.

---

## UI Data Path Map

```
┌─────────────────────────────────────────────────────────────────────┐
│  BROWSER                                                            │
│                                                                     │
│  ┌──────────────────────┐    ┌──────────────────────────────────┐  │
│  │  CHAT PANEL (left)   │    │  RESEARCH PANEL (right)          │  │
│  │                      │    │                                  │  │
│  │  Data source:        │    │  Data source:                    │  │
│  │  REAL backend APIs   │    │  seedData.ts (HARDCODED)         │  │
│  │                      │    │                                  │  │
│  │  Path:               │    │  Path:                           │  │
│  │  User query          │    │  extractTickers() detects        │  │
│  │  → SF Apex action    │    │  ticker in query text            │  │
│  │  → AWS Lambda        │    │  → loadTickerData(ticker)        │  │
│  │  → Real API calls    │    │  → Reads from seedData.ts        │  │
│  │  → Streamed response │    │  → Populates all tabs instantly  │  │
│  │                      │    │                                  │  │
│  │  ✅ LIVE DATA        │    │  ❌ STATIC SEED DATA             │  │
│  └──────────────────────┘    └──────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Component-by-Component Breakdown

### Chat Panel (Left) — REAL

| Step | Component | What Happens | Real? |
|------|-----------|-------------|-------|
| 1 | Frontend `agentApi.ts` | Routes query by keyword to an Apex action | Yes |
| 2 | SF Apex (e.g. `IR_MarketDataAction`) | Makes HTTP callout to AWS Lambda MCP server | Yes |
| 3 | AWS Lambda `ir-market-data-mcp-prod` | Calls Alpha Vantage API for live quote | Yes — real API |
| 4 | AWS Lambda `ir-sec-edgar-mcp-prod` | Calls SEC EDGAR API for filings | Yes — real API |
| 5 | AWS Lambda `ir-news-search-mcp-prod` | Calls Tavily API for news | Yes — real API |
| 6 | AWS Lambda `ir-financial-analysis-prod` | Fetches live price from MCP, runs DCF/comps/Monte Carlo math, calls Bedrock Claude for narrative | Yes — live price + real LLM |
| 7 | AWS Lambda `ir-sentiment-analysis-prod` | Calls Bedrock Claude + Amazon Comprehend for sentiment | Yes — real LLM + NLP |
| 8 | Response streamed back to chat | Text appears in chat panel | Yes |

### Research Panel (Right) — SEED DATA

| Tab | Data Source | File | Real? |
|-----|-----------|------|-------|
| Company (price, P/E, market cap, 52-week range) | `COMPANY_PROFILES` in seedData.ts | Hardcoded for 11 tickers | ❌ No |
| Coverage (analyst ratings, target prices) | `ANALYST_COVERAGE` in seedData.ts | Hardcoded | ❌ No |
| Analysis (DCF fair value, Monte Carlo, comps) | `VALUATION_SNAPSHOTS` in seedData.ts | Hardcoded | ❌ No |
| Analysis (revenue chart, EPS, margins) | `CHART_DATA` in seedData.ts | Hardcoded | ❌ No |
| Filings (10-K, 10-Q, 8-K summaries) | `SAMPLE_FILINGS` in seedData.ts | Hardcoded | ❌ No |
| Sentiment badge | `SENTIMENT_SNAPSHOTS` in seedData.ts | Hardcoded | ❌ No |

### Why the Research Panel Shows Instantly

When a user types "NVDA quote", the frontend:
1. Calls `extractTickers("NVDA QUOTE")` → finds "NVDA"
2. Calls `loadTickerData("NVDA")` → reads all 8 sections from seedData.ts
3. Populates the research panel immediately (no API call)
4. Simultaneously sends the query to the backend (real API call)
5. Backend response streams into the chat panel (takes 2-10 seconds)

The research panel appears instant because it's reading a local TypeScript file, not waiting for an API response.

---

## Backend Components: Real vs Hardcoded

### MCP Servers (Lambda) — ALL REAL

| Server | Lambda | External API | Verdict |
|--------|--------|-------------|---------|
| Market Data | `ir-market-data-mcp-prod` | Alpha Vantage (real-time quotes, history, consensus) | ✅ Real API |
| SEC EDGAR | `ir-sec-edgar-mcp-prod` | SEC EDGAR (filings, insider transactions) | ✅ Real API |
| News Search | `ir-news-search-mcp-prod` | Tavily (financial news search) | ✅ Real API |

### Strands Agents (Lambda) — MIXED

| Agent | Lambda | What's Real | What's Hardcoded |
|-------|--------|------------|-----------------|
| Financial Analysis | `ir-financial-analysis-prod` | Live price from MCP, DCF/comps/Monte Carlo math, Bedrock Claude narrative | Revenue TTM, FCF margin, volatility fall back to cached values if MCP unavailable (labeled `data_source: cached`) |
| Sentiment Analysis | `ir-sentiment-analysis-prod` | Bedrock Claude LLM, Amazon Comprehend NLP, news from Tavily MCP | Sample earnings transcripts for NVDA/AAPL/MSFT are hardcoded (other tickers get generic transcript) |

### Salesforce Apex Actions — REAL CRM (SEEDED)

| Action | What It Does | Data Source |
|--------|-------------|-------------|
| `IR_CompanyLookupAction` | SOQL query on IR_Company__c | Real SOQL, seeded data (10 companies) |
| `IR_CoverageCheckAction` | SOQL query on IR_Coverage__c | Real SOQL, seeded data (20 records) |
| `IR_WatchlistAction` | SOQL query on IR_Watchlist__c | Real SOQL, seeded data (8 entries) |
| `IR_EarningsCalendarAction` | SOQL query on IR_Company__c | Real SOQL, seeded data |
| `IR_ComplianceScreeningAction` | SOQL + restricted list check | Real SOQL, restricted list has fake tickers |
| `IR_MarketDataAction` | HTTP callout to Lambda MCP | Real — calls live Alpha Vantage |
| `IR_SecFilingsAction` | HTTP callout to Lambda MCP | Real — calls live SEC EDGAR |
| `IR_NewsSearchAction` | HTTP callout to Lambda MCP | Real — calls live Tavily |
| `IR_FinancialAnalysisAction` | HTTP callout to Lambda Strands agent | Real — live DCF + Bedrock LLM |
| `IR_SentimentAnalysisAction` | HTTP callout to Lambda Strands agent | Real — Bedrock + Comprehend |
| `IR_ResearchBriefAction` | Orchestrates all above | Mixed — depends on sub-actions |

### Observability — REAL

| Component | What It Does | Real? |
|-----------|-------------|-------|
| Langfuse (Apex `IR_LangfuseTracer`) | Creates traces for every Apex action via Named Credential | ✅ Real HTTP callouts |
| Langfuse (Lambda `langfuse_wrapper.py`) | Creates traces for every Lambda invocation | ✅ Real HTTP callouts |
| Langfuse URL | https://us.cloud.langfuse.com | ✅ 50+ real traces visible |

---

## What Needs to Change

### Priority 1: Research Panel Should Show Live Data

The research panel should parse structured data from the backend response instead of loading from seedData.ts. This requires:
- Backend responses to include structured JSON (not just narrative text)
- Frontend to parse JSON blocks from chat responses
- Research panel to update progressively as data arrives
- Seed data to remain as fallback only (with "seed data" label)

### Priority 2: Financial Analysis Should Fetch All Inputs Live

Currently `_fetch_live_data()` gets live price and P/E from the MCP, but falls back to cached values for revenue, FCF margin, and volatility. These should also come from the MCP's `get_analyst_consensus` endpoint (which returns revenue per share, profit margin, etc.).

### Priority 3: Sentiment Should Fetch Real Transcripts

The sentiment analysis Lambda uses hardcoded `SAMPLE_TRANSCRIPTS` for 3 tickers. It should fetch real earnings call coverage from the news MCP or SEC EDGAR instead.

---

## Supported Tickers

The frontend research panel supports 11 tickers:
`AAPL`, `MSFT`, `NVDA`, `AMZN`, `GOOGL`, `JPM`, `V`, `JNJ`, `XOM`, `TSLA`, `CRM`

Any other ticker will show data in the chat panel (from real APIs) but NOT in the research panel.

---

## How to Verify What's Real

1. **Chat panel**: Type "NVDA quote" — the price in the chat response comes from Alpha Vantage (live). Compare it to the price shown in the research panel ($135.40 from seed data). They will differ.

2. **Langfuse traces**: Visit https://us.cloud.langfuse.com — real traces show tool inputs/outputs with actual API data.

3. **Lambda logs**: Check CloudWatch logs for `ir-financial-analysis-prod` — you'll see `Live data for NVDA: price=XXX` when MCP is working, or `using cache` when it falls back.

4. **data_source field**: The financial analysis Lambda now includes `"data_source": "live"` or `"data_source": "cached (2026-04-08)"` in every response.
