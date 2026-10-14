# 006 V3 — Mock vs Real: What's Live Data, What's Seed Data, What's Drama

> **Date:** 2026-05-02
> **Method:** Line-by-line code review of every MCP server, every skill, every data pipeline script, every CDK stack, every seed script, and every `MOCK_MODE` branch.
> **Rule:** If the code has a `MOCK_MODE` env var, I traced which mode is set in the deployed Lambda. If a data source has a seed script, I traced whether there's a live pipeline that refreshes it.

---

## The Verdict Up Front

The platform has **three layers of data reality**:

1. **Live APIs** — real vendor calls on every turn (Finnhub, Tavily, Bedrock, Salesforce REST). No caching beyond 15s. No stale data.
2. **Seeded-once corpora** — real SEC filings downloaded once, chunked, and indexed into Bedrock KB. Real text, but not auto-refreshing.
3. **Static reference data** — JSON files committed to the repo (restricted list, OFAC SDN stub, mock household data). Updated manually.

There is **no CDC pipeline** (Salesforce → Aurora sync), **no scheduled filing refresh**, and **no live OFAC feed**. The data pipelines exist as code but are run manually, not on a schedule.

---

## Layer 1: Live APIs — Real Data on Every Call

These hit real vendor endpoints on every invocation. No mock drama.

### market-data MCP → Finnhub (LIVE)

| What | Evidence |
|------|----------|
| **Code:** `aws/mcp-servers/market-data/app.py` | `_finnhub("/quote", {"symbol": symbol})` calls `https://finnhub.io/api/v1/quote` with real `FINNHUB_API_KEY` |
| **Fallback:** Alpha Vantage | `_alpha_vantage_quote()` fires when Finnhub fails |
| **Cache:** 15 seconds in-memory per warm Lambda | `_QUOTE_CACHE` with `_CACHE_TTL_S = 15.0` |
| **Mock branch:** `MARKET_DATA_MODE=mock` returns deterministic shapes | `_mock_quote()` returns `base = 100.0 + (sum(ord(c) for c in symbol) % 500)` |
| **Deployed mode:** `live` (default) | Env var defaults to `"live"` — mock requires explicit `MARKET_DATA_MODE=mock` |
| **Verified live:** NVDA $211.27 in a real turn | `REVIEWER_FIXES_APPLIED.md` |

**Verdict: REAL.** Every `get_quote` call hits Finnhub. The 15s cache is per-Lambda-container, not persistent. Historical bars and technicals also hit Finnhub live, with mock fallback only on Finnhub failure.

### news-search MCP → Tavily + Finnhub fallback (LIVE)

| What | Evidence |
|------|----------|
| **Code:** `aws/mcp-servers/news-search/app.py` | `_tavily_search()` POSTs to `https://api.tavily.com/search` with real `TAVILY_API_KEY` |
| **Fallback:** Finnhub company-news | `_finnhub_search()` fires when Tavily rate-limits |
| **Sentiment:** Bedrock Claude Sonnet | `_bedrock_sentiment()` calls `bedrock-runtime.converse()` with Sonnet model |
| **Mock branch:** `NEWS_SEARCH_MODE=mock` | Returns 3 canned articles with `"source": "MockWire"` |
| **Deployed mode:** `live` (default) | |

**Verdict: REAL.** News search hits Tavily (or Finnhub fallback) on every call. Sentiment scoring uses real Bedrock Sonnet, not Amazon Comprehend. Mock mode requires explicit opt-in.

### salesforce-crm MCP → Salesforce REST API (LIVE with OBO)

| What | Evidence |
|------|----------|
| **Code:** `aws/mcp-servers/salesforce-crm/app.py` | `_sf_call()` makes real `httpx` requests to `{instance_url}/services/data/v60.0/...` |
| **Auth:** Per-user OBO via sf-auth-proxy | `_obo_token()` calls sf-auth-proxy Lambda → JWT Bearer grant → scoped access token |
| **MNPI redaction:** Applied on every outbound record | `redact_record()` / `redact_records()` from `_mnpi_redact.py` |
| **Mock branch:** `SALESFORCE_CRM_MODE=mock` | Returns canned `_mock_records()` — hardcoded Patel/Chen household data |
| **Deployed mode:** `live` (default) | |
| **Verified live:** Real SF IDs returned (`a08gK00000Phu29QAB`) | `llmj-v6-final-assessment.md` |

**Verdict: REAL when OBO is configured.** SOQL queries, object reads, creates, and updates all go through real Salesforce REST. The mock branch returns hardcoded household data (Patel, Chen) — this is the fallback when OBO isn't configured, not the production path.

### sec-edgar MCP → EDGAR + Bedrock KB (MIXED)

| What | Evidence |
|------|----------|
| **Filing lookup:** `_finnhub` is NOT used — direct EDGAR REST | `_cik_for()` calls `https://data.sec.gov/submissions/CIK{cik}.json` |
| **KB retrieval:** Real Bedrock KB | `bedrock_agent.retrieve()` with `knowledgeBaseId` from env |
| **Source chunks:** S3 lookup | `_s3_get_chunk()` reads from the chunks bucket |
| **Source tables:** NOT LIVE | `"Live mode placeholder — filings-corpus table extraction not yet deployed"` — returns empty stub |
| **Mock branch:** `SEC_EDGAR_MODE=mock` | Returns `_fixtures.py` canned data: `MOCK_SOURCE_CHUNKS`, `MOCK_SOURCE_TABLES`, `MOCK_10K_FILING_TEXT` |
| **Deployed mode:** `live` (default) | |

**Verdict: PARTIALLY REAL.** Filing lookups hit real EDGAR. KB retrieval hits real Bedrock KB with 784 real chunks. But source table drill-down returns empty stubs in live mode because the filings-corpus table extraction pipeline isn't deployed. Source chunk drill-down works via S3 (real chunks uploaded by `seed-kb-chunks.py`).

### Bedrock (Sonnet / Haiku / Titan / Guardrails) — LIVE

| What | Evidence |
|------|----------|
| **Reasoning:** Sonnet 4.5 via `BedrockConverseClient.converse()` | Real `bedrock-runtime` calls |
| **FAQ/Draft:** Haiku 4.5 | `resolve_model_id(ModelTier.HAIKU)` |
| **Embeddings:** Titan v2 | KB ingestion pipeline |
| **Guardrails:** `guardrailConfig` attached when env vars set | `GuardrailInterventionError` on `stopReason == "guardrail_intervened"` |
| **Verified live:** 16.2s research turn, 8.5s advisor draft | |

**Verdict: REAL.** Every LLM call is a real Bedrock API call. No stub LLM. No cached responses.

### Langfuse — LIVE

| What | Evidence |
|------|----------|
| **Traces:** Real Langfuse US cloud | `_ScrubbingLangfuseWrapper` wraps every span |
| **Scrubbing:** MNPI + PII + token scrubbing before flush | Three-pass recursive |

**Verdict: REAL.** Traces accumulate in real Langfuse. Scrubbing is mechanical.

---

## Layer 2: Seeded-Once Corpora — Real Data, No Auto-Refresh

These contain real data that was downloaded/created once and indexed. They don't refresh automatically.

### Bedrock Knowledge Base — 784 Real SEC Filing Chunks

| What | Evidence |
|------|----------|
| **Source:** 10 real SEC filings (NVDA, MSFT, AAPL, TSLA, META, GOOGL, AMZN, AMD, JPM, GS) | `scripts/download-sample-filings.sh` downloads from `sec.gov` |
| **Chunking:** `scripts/seed-kb-chunks.py` | HTML → BeautifulSoup → text → 1500-char windows with 200-char overlap |
| **Upload:** S3 → Bedrock KB data source → Titan v2 embeddings | Real embeddings, real FAISS index |
| **Refresh:** MANUAL | No scheduled re-download. No EventBridge trigger. No CDC. |
| **Pipeline code exists:** `aws/data-pipelines/filings-corpus/lambdas/` | `chunker.py`, `embedder.py`, `ingest_handler.py`, `textract_handler.py`, `xbrl_parser.py` — all written but not deployed as scheduled Lambdas |

**Verdict: REAL DATA, STATIC PIPELINE.** The 784 chunks are from real SEC filings (real XBRL-in-HTML from sec.gov). But they were downloaded once and indexed once. There's no scheduled pipeline that pulls new filings. The pipeline Lambda code exists (`filings-corpus/lambdas/`) but isn't wired to an EventBridge schedule or S3 trigger.

### Aurora pgvector — Schema + RLS, No Live Data Flow

| What | Evidence |
|------|----------|
| **CDK stack:** `aurora_stack.py` | Creates Aurora Serverless v2 cluster with `001_init.sql` schema + `002_rls_policies.sql` |
| **RLS:** Row-level security on `principal_id` | Applied at deploy time |
| **CDC pipeline:** `research-corpus/lambdas/cdc_handler.py` | Code exists but NOT deployed as a scheduled Lambda |
| **Data flow:** None live | No Salesforce Platform Event → EventBridge → Aurora path |

**Verdict: INFRASTRUCTURE DEPLOYED, NO LIVE DATA FLOW.** The Aurora cluster is up with schema and RLS. But there's no CDC pipeline feeding it. The `cdc_handler.py` exists as code but isn't triggered.

### Salesforce SObjects — Seeded + Live Writes

| What | Evidence |
|------|----------|
| **Seed script:** `scripts/seed-demo-rows.sh` | Creates 1 `Client_Inquiry__c`, 2 `Research_Brief__c`, 1 `IR_Audit_Log__c` via `sf data create record` |
| **Live writes:** Agent turns write real rows | `publish_brief` → `Research_Brief__c`, `audit_logging` → `IR_Audit_Log__c`, `rm_handoff` → `Client_Inquiry__c` |
| **Household data:** NOT seeded by the agent | The 4 demo households (Patel, Chen, Vance, Al-Rashid) need to be created via `seed-demo-data.apex` |

**Verdict: MIXED.** The initial rows are seeded by a script. But every agent turn writes real rows to real Salesforce via real REST API. The data grows with usage. The household/position data for the demo needs to be seeded separately.

---

## Layer 3: Static Reference Data — JSON Files in the Repo

These are committed JSON files that don't update automatically.

### Restricted List — `compliance_screening/restricted_list.json`

| What | Evidence |
|------|----------|
| **Content:** 20 fictional tickers (ACME, BIGCO, CYBRX, etc.) | None are real tickers |
| **Version:** `"2026-03-10"` | |
| **Description:** `"Production feed is a house-policy service; this file is demo-mode seed data."` | |
| **Refresh:** MANUAL | No API call to a compliance service. No scheduled update. |

**Verdict: STATIC SEED DATA.** The restricted list is 20 fictional tickers in a JSON file. In production this would be a live feed from a house-policy service. The code supports `reload_restricted_list()` but nothing calls it on a schedule.

### OFAC SDN List — `mulesoft_api/ofac_sdn_stub.json`

| What | Evidence |
|------|----------|
| **Content:** 5 entries (Kim Jong Un, sanctioned entities) | |
| **Description:** `"US Treasury OFAC SDN list — V3 demo-mode seed (real feed is a daily download)."` | |
| **Override:** `OFAC_SDN_PATH` env var + `reload_ofac()` function | Supports hot-reload from a different path |
| **Refresh:** MANUAL | No scheduled download from Treasury. |

**Verdict: STATIC SEED DATA.** 5 entries in a JSON file. Production would be a daily download from Treasury's SDN list. The code supports hot-reload via env var but nothing triggers it.

### Frontend Topology — `shared/data/topology.json`

| What | Evidence |
|------|----------|
| **Content:** Node/edge graph of the 14-agent topology | Generated by `scripts/export_topology.py` from the Python topology |
| **Refresh:** MANUAL | Run `python scripts/export_topology.py` after topology changes |

**Verdict: STATIC BUT DERIVED.** Generated from the real Python topology. Not auto-synced — must be regenerated manually.

### Client 360 Allocation Bar — Hardcoded in `AdvisorWorkbenchV6.tsx`

| What | Evidence |
|------|----------|
| **Content:** `62% equity, 22% fixed, 9% alts, 4% RE, 3% other` | Hardcoded `style={{ width: '62%' }}` etc. |
| **Holdings:** Shows "—" for Total AUM and Cash sleeve | |

**Verdict: HARDCODED UI PLACEHOLDER.** Not connected to any data source. The `handle_read_household_positions` MCP tool exists and returns real data (or mock data), but the V6 `ClientContextPanel` doesn't call it.

### Queue Data — Live via WebSocket, Empty at Start

| What | Evidence |
|------|----------|
| **Store:** `shared/store/queues.ts` — Zustand store, starts empty | `EMPTY: { inbox: [], briefs: [], alerts: [], pending: [] }` |
| **Population:** `queue_update` WebSocket events from agent turns | `onQueueUpdate` in `useStreamingTurn` |
| **Persistence:** None | Queues reset on page refresh |

**Verdict: LIVE BUT EPHEMERAL.** Queue items arrive via real WebSocket events from real agent turns. But they don't persist — page refresh clears them. No pre-seeded queue data.

---

## Layer 4: Mock Branches — What Happens When Vendors Are Down

Every MCP server has a `MOCK_MODE` env var. Here's what each mock branch does:

| MCP Server | Mock Env Var | Mock Behavior | Default Mode |
|------------|-------------|---------------|--------------|
| market-data | `MARKET_DATA_MODE=mock` | Deterministic price from `sum(ord(c))` hash | `live` |
| news-search | `NEWS_SEARCH_MODE=mock` | 3 canned articles from "MockWire" | `live` |
| salesforce-crm | `SALESFORCE_CRM_MODE=mock` | Hardcoded Patel/Chen household records | `live` |
| sec-edgar | `SEC_EDGAR_MODE=mock` | `_fixtures.py` canned chunks/tables | `live` |
| sf-auth-proxy | `SF_AUTH_PROXY_MODE=mock` | Returns `MOCK-ACCESS-{principal}` token | `live` |
| mulesoft-actions | (via `mulesoft_api` skill) | `MULESOFT_MODE=mock` returns deterministic order/wire IDs | `sandbox` (default — routes to CloudHub) |

**All components now default to live.** As of 2026-05-02, `MULESOFT_MODE` defaults to `sandbox` (was `mock`). The skill layer (`mulesoft_api/actions.py`) and the MCP server Lambda (`mulesoft-actions/app.py`) both route to the deployed CloudHub apps by default. Tests explicitly set `MULESOFT_MODE=mock` via `conftest.py` so they remain isolated. To revert to mock for local dev, set `MULESOFT_MODE=mock` explicitly.

### The MCP Client Mock — `_mcp_client.py`

The skill layer's `get_shared_mock_client()` is **live-first, mock-fallback**:

```python
if api_url:  # MCP_API_URL is set → production
    _SHARED = MCPClient(mock=False, server_urls=server_urls)
    return _SHARED
# Fallback to mock
_SHARED = MCPClient(mock=True)
```

When `MCP_API_URL` is set (which it is in the deployed Lambda environment), skills call real MCP servers over HTTPS. The mock router is only used in unit tests or when `MCP_API_URL` is unset.

---

## Data Pipelines — What Exists vs What Runs

### Pipelines That Exist as Code

| Pipeline | Code Location | What It Does | Deployed? | Scheduled? |
|----------|--------------|--------------|-----------|------------|
| Filings corpus ingestion | `aws/data-pipelines/filings-corpus/lambdas/` | Download → Textract → chunk → embed → KB | CDK stack exists (`filings_pipeline_stack.py`) | **NO** — no EventBridge rule, no S3 trigger |
| Research corpus CDC | `aws/data-pipelines/research-corpus/lambdas/cdc_handler.py` | SF Platform Event → Aurora pgvector | CDK stack exists (`research_pipeline_stack.py`) | **NO** — no EventBridge rule |
| Risk alerts monitor | `aws/data-pipelines/risk-alerts/lambdas/monitor.py` | Price monitor → SQS → compliance sweep | CDK stack exists (`risk_alerts_stack.py`) | **NO** — no CloudWatch Events rule |
| KB chunk seeder | `scripts/seed-kb-chunks.py` | HTML → chunks → S3 → KB ingestion | Script only | **MANUAL** — run once |
| Filing downloader | `scripts/download-sample-filings.sh` | curl from sec.gov | Script only | **MANUAL** — run once |
| Demo data seeder | `scripts/seed-demo-rows.sh` | sf CLI → Salesforce records | Script only | **MANUAL** — run once |

### Pipelines That Actually Run

| Pipeline | Trigger | Evidence |
|----------|---------|----------|
| Bedrock KB ingestion | Manual via `seed-kb-chunks.py` → S3 upload → KB data source sync | 784 chunks indexed, Titan v2 embeddings |
| Agent turn → Salesforce write | Every agent turn | `Research_Brief__c`, `IR_Audit_Log__c`, `Client_Inquiry__c` rows |
| Agent turn → Langfuse trace | Every agent turn | Traces accumulate with MNPI/PII/token scrubbing |

**Verdict: No automated data pipelines run on a schedule.** The CDK stacks for filings, research-corpus, and risk-alerts exist but don't have EventBridge rules or S3 triggers wired. All data ingestion is manual (run a script once). The only "pipeline" that runs continuously is the agent itself — every turn writes to Salesforce and Langfuse.

---

## Summary: The Honest Data Map

```
┌─────────────────────────────────────────────────────────────────────┐
│                        LIVE ON EVERY CALL                           │
│                                                                     │
│  Finnhub quotes ──→ market-data MCP ──→ real price (15s cache)     │
│  Tavily news    ──→ news-search MCP ──→ real articles              │
│  Bedrock Sonnet ──→ coordinator     ──→ real LLM reasoning         │
│  Bedrock Haiku  ──→ coordinator     ──→ real LLM draft             │
│  Bedrock KB     ──→ sec-edgar MCP   ──→ real retrieval (784 chunks)│
│  Salesforce REST──→ salesforce-crm  ──→ real SOQL/DML via OBO      │
│  Langfuse       ──→ coordinator     ──→ real traces                │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     SEEDED ONCE, NOT REFRESHING                     │
│                                                                     │
│  10 SEC filings (real HTML from sec.gov) → 784 KB chunks           │
│  4 demo households (Patel, Chen, Vance, Al-Rashid) in Salesforce   │
│  Aurora pgvector schema + RLS (no data flowing in)                 │
│  Demo Research_Brief__c + Client_Inquiry__c + IR_Audit_Log__c rows │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     STATIC JSON IN THE REPO                         │
│                                                                     │
│  restricted_list.json — 20 fictional tickers, manual update        │
│  ofac_sdn_stub.json — 5 entries, manual update                    │
│  topology.json — generated from Python, manual regenerate          │
│  Client 360 allocation bar — hardcoded percentages in TSX          │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     MOCK (only when explicitly opted in)            │
│                                                                     │
│  MuleSoft — MULESOFT_MODE defaults to sandbox (CloudHub live)        │
│  Set MULESOFT_MODE=mock explicitly for local dev/tests              │
│  All other MCPs default to live; mock requires explicit env var    │
│  MCP client — mock only when MCP_API_URL is unset (tests)         │
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                     PIPELINE CODE EXISTS, NOT SCHEDULED              │
│                                                                     │
│  filings-corpus: chunker + embedder + textract + xbrl_parser       │
│  research-corpus: cdc_handler + chunker + embedder + sharing_rules │
│  risk-alerts: monitor + sweep_dispatcher                           │
│  All have CDK stacks. None have EventBridge triggers.              │
└─────────────────────────────────────────────────────────────────────┘
```

---

## What's Mock Drama vs What's Real — Final Call

| Claim | Real or Drama? | Evidence |
|-------|---------------|----------|
| "Real Finnhub quotes" | **REAL** | `_finnhub("/quote")` with API key, 15s cache, verified $211.27 |
| "Real Tavily news search" | **REAL** | `_tavily_search()` with API key, Finnhub fallback |
| "Real Bedrock reasoning" | **REAL** | `bedrock-runtime.converse()` with Sonnet/Haiku, 16.2s verified |
| "Real Salesforce OBO" | **REAL** | JWT Bearer grant via sf-auth-proxy, real SF IDs returned |
| "784 real SEC filing chunks" | **REAL DATA, STATIC** | Downloaded from sec.gov, chunked, indexed — but not auto-refreshing |
| "OFAC SDN screening" | **REAL CODE, STATIC DATA** | `_screen_ofac()` runs on every wire — but against 5 stub entries |
| "Restricted list compliance" | **REAL CODE, STATIC DATA** | `compliance_screening` runs deterministically — but against 20 fictional tickers |
| "MuleSoft trade execution" | **LIVE (sandbox)** | `MULESOFT_MODE` defaults to `sandbox`. Routes to CloudHub Alpaca paper + Dwolla sandbox. Set `mock` explicitly to revert. |
| "Client 360 holdings" | **HARDCODED** | Allocation bar is `style={{ width: '62%' }}` in TSX |
| "Demand signals from client inquiries" | **LIVE BUT EMPTY** | Queue store starts empty, populates from real WebSocket events |
| "CDC pipeline keeps Aurora in sync" | **CODE EXISTS, NOT RUNNING** | `cdc_handler.py` written, CDK stack exists, no trigger |
| "Automated filing refresh" | **CODE EXISTS, NOT RUNNING** | Pipeline Lambdas written, no schedule |
| "Risk alert monitoring" | **CODE EXISTS, NOT RUNNING** | `monitor.py` + `sweep_dispatcher.py` written, no trigger |

---

*Assessment closed 2026-05-02. Every `MOCK_MODE` branch traced. Every data source verified.*
