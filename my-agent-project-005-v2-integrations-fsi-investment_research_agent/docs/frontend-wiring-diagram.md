# 005-V2 Frontend Data Wiring — Before vs After

> Date: April 18, 2026
> Purpose: Document the migration from seed data to real backend APIs

---

```
═══════════════════════════════════════════════════════════════════════════════
  005-V2 FRONTEND DATA WIRING — BEFORE vs AFTER
═══════════════════════════════════════════════════════════════════════════════


  BEFORE (seed data mockery)
  ──────────────────────────

  User types "NVDA quote"
       │
       ├──────────────────────────────────────────────────────────────┐
       │                                                              │
       ▼                                                              ▼
  CHAT PANEL (left)                                    RESEARCH PANEL (right)
       │                                                              │
       │ sendMessage("NVDA quote")                     extractTickers("NVDA")
       │                                                              │
       ▼                                                              ▼
  agentApi.ts                                          loadTickerData("NVDA")
       │                                                              │
       │ routeMessage() → IR_MarketDataAction                         │ SYNCHRONOUS
       │                                                              │ reads from
       ▼                                                              ▼
  Salesforce Apex                                      seedData.ts ← HARDCODED
       │                                               ┌──────────────────────┐
       │ HTTP callout                                  │ COMPANY_PROFILES     │
       ▼                                               │ ANALYST_COVERAGE     │
  AWS Lambda                                           │ CONSENSUS_SUMMARIES  │
       │                                               │ CHART_DATA           │
       │ Alpha Vantage API                             │ SAMPLE_FILINGS       │
       ▼                                               │ VALUATION_SNAPSHOTS  │
  REAL live price                                      │ SENTIMENT_SNAPSHOTS  │
       │                                               │ HISTORICAL_FINANCIALS│
       ▼                                               └──────────────────────┘
  Streams into chat bubble                                        │
  (real data, text only)                                          ▼
                                                       Populates all 4 tabs
                                                       INSTANTLY with FAKE data
                                                       (never updates from backend)

  ❌ Two disconnected paths. Chat = real. Panel = fake.


═══════════════════════════════════════════════════════════════════════════════


  AFTER (real wiring)
  ───────────────────

  User types "NVDA quote"
       │
       ├──────────────────────────────────────────────────────────────┐
       │                                                              │
       ▼                                                              ▼
  CHAT PANEL (left)                                    RESEARCH PANEL (right)
       │                                                              │
       │ sendMessage("NVDA quote")                     extractTickers("NVDA")
       │                                                              │
       ▼                                                              ▼
  agentApi.ts                                          loadTickerData("NVDA")
       │                                                              │
       │ (unchanged — same                                            │ ASYNC
       │  Apex fallback flow)                                         │ shows spinner
       │                                                              ▼
       │                                               researchApi.ts ← NEW
       │                                                              │
       │                                               fetchAllResearchData()
       │                                                              │
       │                                          Promise.allSettled([
       │                                               │    │    │    │    │
       │                                               ▼    ▼    ▼    ▼    ▼
       │
       │                              ┌─────────┐ ┌────────┐ ┌──────┐ ┌────────┐ ┌───────┐
       │                              │COMPANY  │ │COVERAGE│ │VALUA-│ │SENTI-  │ │FILINGS│
       │                              │fetchCo..│ │fetchCo.│ │TION  │ │MENT    │ │fetchFi│
       │                              │Data()   │ │verage()│ │fetch.│ │fetch.. │ │lings()│
       │                              └────┬────┘ └───┬────┘ └──┬───┘ └───┬────┘ └──┬────┘
       │                                   │          │         │         │          │
       ▼                                   ▼          ▼         ▼         ▼          ▼
  ┌─────────────┐                    ┌───────────────────────────────────────────────────┐
  │ Salesforce  │                    │              PARALLEL API CALLS                   │
  │ Apex Action │                    │                                                   │
  │ (chat flow) │                    │  CRM data ──→ Salesforce Apex REST                │
  │             │                    │    • IR_CompanyLookupAction (company profile)      │
  │             │                    │    • IR_CoverageCheckAction (analyst coverage)     │
  │             │                    │                                                   │
  │             │                    │  Market data ──→ AWS Lambda DIRECT (JSON)          │
  │             │                    │    • /market-data/tools/call → get_quote           │
  │             │                    │    • /market-data/tools/call → get_analyst_consensus│
  │             │                    │                                                   │
  │             │                    │  Valuation ──→ AWS Lambda DIRECT (JSON)            │
  │             │                    │    • /financial-analysis/fair_value                 │
  │             │                    │    → DCF + Monte Carlo + Comps + Bedrock narrative │
  │             │                    │                                                   │
  │             │                    │  Sentiment ──→ AWS Lambda DIRECT (JSON)            │
  │             │                    │    • /sentiment-analysis/aggregate_sentiment       │
  │             │                    │    → Comprehend NLP + Bedrock synthesis            │
  │             │                    │                                                   │
  │             │                    │  Filings ──→ AWS Lambda DIRECT (JSON)              │
  │             │                    │    • /sec-edgar/tools/call → get_10k               │
  │             │                    │    • /sec-edgar/tools/call → get_10q               │
  └──────┬──────┘                    └──────────────────────┬────────────────────────────┘
         │                                                  │
         ▼                                                  ▼
  Streams into                                    Parsed into typed structs:
  chat bubble                                     CompanyData, CoverageData[],
  (text, real)                                    ConsensusSummary, ValuationData,
                                                  SentimentData, FilingData[]
                                                            │
                                                            ▼
                                                  Zustand store updated
                                                  dataSource = 'live'
                                                            │
                                                  ┌────────┼────────┐────────┐
                                                  ▼        ▼        ▼        ▼
                                              Company  Coverage  Analysis  Filings
                                                tab      tab       tab      tab
                                              (LIVE)   (LIVE)    (LIVE)   (LIVE)

  ✅ Both paths hit real APIs. Panel shows LIVE badge.


═══════════════════════════════════════════════════════════════════════════════


  KEY DESIGN DECISION: WHY AWS DIRECT (not through Apex)?
  ───────────────────────────────────────────────────────

  CHAT PATH (unchanged):
    Frontend → Apex → AWS Lambda → JSON → Apex formats to TEXT → chat bubble
                                          ^^^^^^^^^^^^^^^^^^^^^^^^
                                          Loses structure! Text only.

  RESEARCH PANEL PATH (new):
    Frontend → AWS Lambda DIRECT → JSON → Frontend parses to typed structs
                                          ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
                                          Keeps structure! Rich UI.

  CRM-only data (company, coverage) still goes through Apex because
  that data lives in Salesforce custom objects (IR_Company__c, IR_Coverage__c).


═══════════════════════════════════════════════════════════════════════════════


  FILE CHANGE MAP
  ───────────────

  src/
  ├── services/
  │   ├── agentApi.ts          ← UNCHANGED (chat flow)
  │   ├── researchApi.ts       ← NEW (research panel data fetching)
  │   └── responseParser.ts    ← MODIFIED (removed isSupported → isValidTicker)
  ├── store/
  │   └── agentStore.ts        ← MODIFIED (loadTickerData now async, calls researchApi)
  ├── components/
  │   ├── ChatPanel.tsx        ← MINOR (comments only)
  │   ├── CompanyCard.tsx      ← MODIFIED (added spinner + error states)
  │   ├── CoverageTable.tsx    ← UNCHANGED (reads from store)
  │   ├── FinancialChart.tsx   ← UNCHANGED (reads from store)
  │   └── ResearchPanel.tsx    ← UNCHANGED (reads from store)
  ├── data/
  │   └── seedData.ts          ← KEPT AS FALLBACK (not imported by default)
  └── types/
      └── index.ts             ← UNCHANGED

  .env                         ← ADDED VITE_AWS_API_KEY
  .env.example                 ← ADDED VITE_AWS_API_KEY


═══════════════════════════════════════════════════════════════════════════════


  FALLBACK STRATEGY
  ─────────────────

  seedData.ts is KEPT but NOT imported by the active code path.
  It remains available for:
    • Offline development / demo mode
    • Future graceful degradation if backend is unreachable
    • Reference data for testing parsers

  To re-enable seed fallback, import from seedData.ts in researchApi.ts
  and return seed data when fetchAllResearchData() catches errors.
```
