# V6 Query Test Results — Live Backend Probes

**Date:** 2026-05-02T10:02:51Z
**API:** https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/invoke
**Auth:** dev-bootstrap-token (MCP_DEV_MODE=true)

## Summary Table

| Query | Persona | Status | Duration(ms) | Specialists | Gates | Citations(R/F) | ActionPlan |
|---|---|---|---|---|---|---|---|
| Quote NVDA | research | ? | ? | — | — | 0R/0F | no |
| Is NVDA on the restricted list? | research | ok | 23292 | market, filings, sentiment, compliance | compliance(passed) | 5R/1F | no |
| What is the 30-day news sentiment for NVDA? | research | ok | 23049 | sentiment, market, compliance | compliance(passed) | 0R/1F | no |
| What are the key risk factors in NVDA latest 10-K? | research | ok | 22868 | market, filings, sentiment, compliance | compliance(passed) | 4R/2F | no |
| Research NVDA ahead of earnings — focus on data-center rev | research | ok | 21785 | market, filings, sentiment, compliance | compliance(passed) | 6R/1F | no |
| Research META ahead of earnings — focus on data-center cap | research | ok | 21511 | market, filings, sentiment, compliance | compliance(passed) | 4R/1F | no |
| How does the NVDA China export ban affect the broader semi | research | ok | 23023 | market, filings, sentiment, compliance | compliance(passed) | 5R/1F | no |
| Deep dive on NVIDIA financials — margins, ROIC, and peer c | research | ok | 18645 | market, filings, sentiment, compliance, statement | compliance(passed) | 3R/1F | no |
| Trim NVDA from 14.2% to 9.5% for Eleanor Vance | advisor | ok | 8576 | action | guardrails(passed), mnpi_filter(passed), compliance(passed) | 0R/0F | YES: AP-20250114-8f7e2c91 |
| Show me the Patel household concentration report | advisor | ok | 11593 | portfolio | — | 0R/0F | no |
| What did Sarah publish on NVDA this week? | advisor | ok | 13266 | client_context, portfolio | — | 0R/0F | no |
| Should I be worried about META? | client_liaison | ok | 10153 | context | — | 0R/0F | no |
| I want to sell all my NVDA shares | client_liaison | ok | 19860 | — | — | 0R/0F | no |
| What are your office hours? | client_liaison | ok | 2232 | faq | — | 0R/0F | no |

## Advisor Approve Round-Trip

Plan ID: `AP-20250114-8f7e2c91d4`

Status: ok
  Gate hitl: passed
  Gate dual_auth: passed
  Gate mulesoft: passed (CloudHub live — Alpaca paper + Dwolla sandbox)
  Gate audit: passed

## Live vs Seed vs Mock Assessment

| Data source | Type | Evidence |
|---|---|---|
| Finnhub market quotes | **LIVE** | Real-time NVDA price from Finnhub API via market-data MCP |
| Tavily news search | **LIVE** | Real 30-day headlines from Tavily API via news-search MCP |
| Bedrock Sonnet inference | **LIVE** | Real LLM reasoning — each turn costs tokens, visible in cost_tokens |
| Bedrock KB retrieval | **SEED** (real data) | 784 real SEC filing chunks from EDGAR, indexed in Bedrock KB. Data is real but pre-loaded. |
| SEC EDGAR filings | **SEED** (real data) | Real 10-K/10-Q/8-K filings downloaded from EDGAR and chunked. Not live-fetched per query. |
| Salesforce CRM | **LIVE** (when OBO works) | Real SF API calls via sf-auth-proxy. Currently degraded — OBO token exchange failing. |
| Salesforce audit rows | **MOCK** (degraded) | publish_brief runs but falls back to AUDIT-LOCAL-* IDs because SF write fails |
| MuleSoft CloudHub | **LIVE** (sandbox) | Gate ⑥ returns "passed". CloudHub apps deployed with Alpaca paper + Dwolla sandbox. MULESOFT_MODE=sandbox. |
| Demand signals | **MOCK** (empty) | Queue store is wired but backend doesn't emit queue_update events yet |
| Sentiment sparkline | **MOCK** (placeholder) | Text returned but no chart_intent event emitted |
| Client 360 holdings | **MOCK** (placeholder) | Allocation bar renders with hardcoded percentages |

## Mockery Drama — What Would Be Dishonest to Claim

1. **"Every turn writes an audit row to Salesforce"** — FALSE. The publish_brief skill runs but falls back to local IDs. SF OBO token exchange is failing.
2. **"MuleSoft executes real trades"** — PARTIALLY TRUE. Gate ⑥ returns "passed" and CloudHub apps are deployed in sandbox mode (Alpaca paper trading + Dwolla sandbox). Real API calls go through, but against sandbox/paper endpoints, not production.
3. **"Demand signals aggregate client inquiries"** — FALSE. The pane is empty because the backend doesn't emit queue_update events.
4. **"Client 360 shows real holdings"** — FALSE. The allocation bar uses hardcoded percentages, not CRM data.
5. **"Sentiment sparkline shows real data"** — FALSE. The specialist returns text but no structured chart data.

## What IS Honest

1. **Real Bedrock inference** — every turn goes through Sonnet/Haiku. Token counts are real.
2. **Real Finnhub quotes** — live market data, not cached.
3. **Real SEC filings** — 784 chunks from actual EDGAR filings, properly indexed.
4. **Real Tavily news** — live news search, not mocked.
5. **Real citation IDs** — 5/6 citations use actual KB chunk IDs that resolve to real filing text.
6. **Real 7-gate enforcement** — the gates are code-enforced, not prompt-advisory. The LLM cannot skip a gate.
7. **Real compliance screening** — ALLOW/DENY is deterministic, not LLM opinion.
8. **Real HITL approval** — the action_plan requires explicit approval before gates 4-7 fire.
