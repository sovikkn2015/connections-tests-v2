# End-to-End Test Results — Project 005

Date: 2026-04-07
Org: Developer Edition
Langfuse: 22 traces (13 Salesforce + 9 AWS)
Pass Rate: 20/20 (100%)

## Test Results

| # | Tool | Action | Query | Agent Name | Agent Location | Data Source | Data Location | Response | Status |
|---|------|--------|-------|------------|----------------|-------------|---------------|----------|--------|
| 1 | company_lookup | get_company_info | NVDA | IR Research Orchestrator | Salesforce | IR_Company__c, IR_Coverage__c | Salesforce CRM | NVIDIA Corp, Technology, NASDAQ, $2.80T, $135.50, Earnings 2026-05-28, Coverage: Priya Sharma Hold, Sarah Kim Buy | PASS |
| 2 | company_lookup | get_company_info | AAPL | IR Research Orchestrator | Salesforce | IR_Company__c, IR_Coverage__c | Salesforce CRM | Apple Inc, Technology, NASDAQ, $3.20T, $198.75, Earnings 2026-04-30 | PASS |
| 3 | company_lookup | get_company_info | JPM | IR Research Orchestrator | Salesforce | IR_Company__c, IR_Coverage__c | Salesforce CRM | JPMorgan Chase, Financials, NYSE, $680B, $245.30, Earnings 2026-04-14 | PASS |
| 4 | coverage_check | get_coverage_info | NVDA | IR Research Orchestrator | Salesforce | IR_Coverage__c | Salesforce CRM | 2 records: Priya Sharma Hold $145, Sarah Kim Buy $180 | PASS |
| 5 | coverage_check | get_coverage_info | Sarah Kim | IR Research Orchestrator | Salesforce | IR_Coverage__c | Salesforce CRM | 4 records: AAPL Strong Buy $210, AMZN Buy $225, MSFT Buy $460, NVDA Buy $180 | PASS |
| 6 | coverage_check | get_coverage_info | Healthcare | IR Research Orchestrator | Salesforce | IR_Coverage__c, IR_Company__c | Salesforce CRM | 4 records: JNJ Buy $175, JNJ Hold $165, UNH Strong Buy $640 | PASS |
| 7 | earnings_calendar | get_earnings_calendar | NVDA | IR Research Orchestrator | Salesforce | IR_Company__c | Salesforce CRM | 2026-05-28 NVIDIA (NVDA) — 51 days | PASS |
| 8 | earnings_calendar | get_earnings_calendar | this month | IR Research Orchestrator | Salesforce | IR_Company__c | Salesforce CRM | JPM 4/14, JNJ 4/15, UNH 4/15, NEE 4/22, CAT 4/28, AMZN 4/29, MSFT 4/29, AAPL 4/30 | PASS |
| 9 | watchlist | get_watchlist | all | IR Research Orchestrator | Salesforce | IR_Watchlist__c, IR_Company__c | Salesforce CRM | 8 entries across High/Medium/Low priorities | PASS |
| 10 | watchlist | get_watchlist | high | IR Research Orchestrator | Salesforce | IR_Watchlist__c, IR_Company__c | Salesforce CRM | 3 entries: UNH, JPM, NVDA | PASS |
| 11 | compliance_screening | check_compliance | NVDA | Compliance Screening Agent | Salesforce | IR_Company__c | Salesforce CRM | PASS — not restricted, quiet period check, no MNPI | PASS |
| 12 | compliance_screening | check_compliance | JPM | Compliance Screening Agent | Salesforce | IR_Company__c | Salesforce CRM | FLAGGED — earnings 7 days away (quiet period) | PASS |
| 13 | compliance_screening | check_compliance | AAPL | Compliance Screening Agent | Salesforce | IR_Company__c | Salesforce CRM | PASS — not restricted, earnings 23 days (outside quiet period) | PASS |
| 14 | sec_filings | get_10k | NVDA 10-K | SEC EDGAR MCP Server | AWS Lambda | SEC EDGAR API | SEC.gov (external) | 3 filings, latest 2026-02-25 | PASS |
| 15 | sec_filings | get_10q | AAPL 10-Q | SEC EDGAR MCP Server | AWS Lambda | SEC EDGAR API | SEC.gov (external) | 3 filings, latest 2026-01-30 | PASS |
| 16 | financial_analysis | run_dcf | NVDA DCF | Financial Analysis Agent | AWS Lambda + Bedrock | Hardcoded financials | AWS Lambda (in-memory) | Fair value: $869.88, Upside: 542.4% | PASS |
| 17 | financial_analysis | run_comps | AAPL Comps | Financial Analysis Agent | AWS Lambda + Bedrock | Hardcoded financials | AWS Lambda (in-memory) | P/E: -16.9% discount vs peers | PASS |
| 18 | financial_analysis | monte_carlo | JPM Monte Carlo | Financial Analysis Agent | AWS Lambda | Hardcoded financials | AWS Lambda (in-memory) | Median: $259.03, Range: $179.96-$368.15 | PASS |
| 19 | sentiment_analysis | analyze_transcript | NVDA transcript | Sentiment Analysis Agent | AWS Lambda + Bedrock | Sample transcript | AWS Lambda + Bedrock Claude Sonnet 4 | Bullish, High confidence, Enthusiastic but cautious tone | PASS |
| 20 | sentiment_analysis | score_news_sentiment | AAPL news | Sentiment Analysis Agent | AWS Lambda + Bedrock | News API fallback | AWS Lambda + Bedrock Claude Sonnet 4 | Neutral, Score: 0.1 | PASS |

## Agents

| Agent | Location | Topics | LLM |
|-------|----------|--------|-----|
| IR Research Orchestrator | Salesforce (Agentforce) | company_lookup, coverage_check, earnings_calendar, watchlist, sec_filings, market_data | Atlas Reasoning Engine |
| Compliance Screening Agent | Salesforce (Apex) | compliance_screening | None (rule-based) |
| Financial Analysis Agent | AWS Lambda + Bedrock | financial_analysis (DCF, comps, Monte Carlo, fair value) | Claude Sonnet 4 |
| Sentiment Analysis Agent | AWS Lambda + Bedrock | sentiment_analysis (transcript, news, tone, aggregate) | Claude Sonnet 4 |
| SEC EDGAR MCP Server | AWS Lambda | sec_filings (10-K, 10-Q, 8-K, insider) | None (API proxy) |

## Data Sources

| Source | Location | Objects/APIs | Used By |
|--------|----------|-------------|---------|
| Salesforce CRM | Salesforce org | IR_Company__c, IR_Coverage__c, IR_Watchlist__c, IR_Research_Note__c, IR_Audit_Log__c | Queries 1-13 |
| SEC EDGAR | SEC.gov (external) | Full-text search + Company submissions API | Queries 14-15 |
| Hardcoded financials | AWS Lambda (in-memory) | Revenue, FCF margin, P/E, EV/EBITDA, P/S, volatility for 10 tickers | Queries 16-18 |
| Bedrock Claude Sonnet 4 | AWS Bedrock (us-east-1) | LLM inference for narrative generation and sentiment analysis | Queries 16 (fair_value), 19-20 |
| News API | Tavily (external) | Financial news search (fallback to hardcoded summary) | Query 20 |

## Governance

All 20 queries traced in Langfuse:
- 13 Salesforce traces (IR_LangfuseTracer.cls via Named Credential)
- 7 AWS traces (langfuse_wrapper.py via REST API)
- Bedrock LLM calls logged as GENERATION events with model ID, prompt, response, token usage
- 5 prompts managed in Langfuse prompt registry (fetched at runtime with hardcoded fallback)
