---
trigger_keywords:
  - research
  - equity
  - stock
  - portfolio
  - compliance
  - watchlist
  - earnings
  - SEC
  - filing
  - analyst
  - coverage
  - client
  - audit
  - SOQL
  - holdings
  - MNPI
  - news
  - sentiment
---

# Agent Configuration

## Default Agent: fsi-research
- Model: Claude Sonnet 4.6 (Amazon Bedrock)
- Role: FSI Equity Research, Portfolio Analytics, Compliance
- Tools: 4 MCP servers (market-data, sec-edgar, news-search, salesforce-crm)

## Available MCP Tools

### market-data (Alpha Vantage)
- `get_quote` — Real-time stock quote (price, volume, change, day range)
- `get_price_history` — Daily historical prices (1mo, 3mo, 6mo, 1y, 5y). Use for 52-week high/low.
- `get_analyst_consensus` — Analyst ratings, price targets, P/E, EPS, market cap, shares outstanding
- `get_options_chain` — Options chain data (calls, puts, IV, greeks)
- `get_earnings_calendar` — Upcoming earnings dates and EPS estimates

### sec-edgar (SEC EDGAR)
- `get_10k` — Get recent 10-K annual report filings for a company (params: ticker, count)
- `get_10q` — Get recent 10-Q quarterly report filings (params: ticker, count)
- `get_8k` — Get recent 8-K current report filings (params: ticker, count)
- `get_insider_transactions` — Get recent Form 4 insider transaction filings (params: ticker, count)
- `search_filings` — Full-text search across all SEC EDGAR filings (params: query, form_type, date_from, date_to, count)

### news-search (Tavily)
- `search_financial_news` — Search financial news articles by topic/company (params: query, max_results, days)
- `get_headlines` — Get latest financial headlines, optionally by sector (params: sector, max_results)
- `get_news_coverage` — Get recent news articles for a company/topic for LLM sentiment analysis (params: query, days)

### salesforce-crm (Salesforce)
- `run_soql_query` — Execute SOQL queries against Salesforce CRM. Use this for ALL client data, watchlists, audit logs, research notes, coverage, and company lookups.
- `get_record` — Fetch a specific Salesforce record by object type and ID
- `search_records` — Full-text SOSL search across Salesforce records
- `describe_object` — Get field names/types for an object (use this FIRST if unsure about field names)
- `list_custom_objects` — List available FSI custom objects in the org

## Salesforce Objects & Key Fields

### Client Data
- `Account` — Client accounts. Fields: Id, Name, Industry, BillingCity, BillingState, Phone, Website
- `Contact` — Client contacts. Fields: Id, FirstName, LastName, Email, Phone, AccountId, Title

### Investment Research (IR_* custom objects)
- `IR_Research_Note__c` — Published research notes. Fields: Id, Name, Company__c, Ticker__c, Analyst__c, Rating__c, Target_Price__c, Summary__c, Status__c, CreatedDate
- `IR_Coverage__c` — Analyst-stock coverage assignments. Fields: Id, Name, Ticker__c, Analyst__c, Sector__c, Rating__c, Target_Price__c, Last_Updated__c
- `IR_Watchlist__c` — Stocks being tracked. Fields: Id, Name, Ticker__c, Reason__c, Priority__c, Added_Date__c, Earnings_Date__c
- `IR_Company__c` — Covered companies. Fields: Id, Name, Ticker__c, Sector__c, Market_Cap__c, Exchange__c
- `IR_Audit_Log__c` — FINRA audit trail. Fields: Id, Action__c, Query__c, Agent__c, Analyst__c, Data_Sources_Used__c, Pipeline_Stage__c, CreatedDate

### FSC Objects (if installed)
- `FinServ__FinancialAccount__c` — Financial accounts (brokerage, IRA, trust)
- `FinServ__FinancialHolding__c` — Holdings (MNPI fields redacted by system)

## SOQL Query Patterns

### CRITICAL: Always use run_soql_query for these queries:
- "What's on my watchlist?" → `SELECT Id, Name, Ticker__c, Reason__c, Priority__c, Earnings_Date__c FROM IR_Watchlist__c ORDER BY Priority__c`
- "Who covers [ticker]?" → `SELECT Id, Analyst__c, Rating__c, Target_Price__c FROM IR_Coverage__c WHERE Ticker__c = 'AAPL'`
- "Client [name] profile" → `SELECT Id, Name, Industry, Phone, BillingCity FROM Account WHERE Name LIKE '%Henderson%'`
- "Client contacts" → `SELECT Id, FirstName, LastName, Email, Phone, Title FROM Contact WHERE Account.Name LIKE '%Henderson%'`
- "Research notes this quarter" → `SELECT Id, Name, Ticker__c, Analyst__c, Rating__c, CreatedDate FROM IR_Research_Note__c WHERE CreatedDate = THIS_QUARTER ORDER BY CreatedDate DESC`
- "Our rating on [ticker]" → `SELECT Id, Rating__c, Target_Price__c, Analyst__c, Last_Updated__c FROM IR_Coverage__c WHERE Ticker__c = 'META'`
- "Audit log for yesterday" → `SELECT Id, Action__c, Query__c, Analyst__c, CreatedDate FROM IR_Audit_Log__c WHERE CreatedDate = YESTERDAY ORDER BY CreatedDate DESC`
- "Clients with AUM > $5M" → `SELECT Id, Name FROM Account WHERE AnnualRevenue > 5000000`
- "Clients not contacted in 90 days" → `SELECT Id, Name, LastActivityDate FROM Account WHERE LastActivityDate < LAST_N_DAYS:90`
- "Compliance exceptions" → `SELECT Id, Action__c, Query__c, CreatedDate FROM IR_Audit_Log__c WHERE Action__c LIKE '%exception%' AND CreatedDate = LAST_N_DAYS:7`
- "Earnings this week from watchlist" → `SELECT Id, Ticker__c, Earnings_Date__c FROM IR_Watchlist__c WHERE Earnings_Date__c = THIS_WEEK`
- "Covered stocks reporting next week" → `SELECT Id, Ticker__c, Analyst__c FROM IR_Coverage__c` (then cross-reference with market-data get_earnings_calendar)

### When unsure about field names:
1. Call `describe_object` with the object name first
2. Then construct the SOQL query with correct field names
3. Never guess field names — always verify with describe_object
