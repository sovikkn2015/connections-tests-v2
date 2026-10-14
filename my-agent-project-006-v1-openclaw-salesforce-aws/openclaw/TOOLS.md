# Tool Usage Guide

## When to use each tool

| Query Type | Tool | Example |
|-----------|------|---------|
| Stock price/quote | market-data → get_quote | "What's NVDA trading at?" |
| Price history / 52-week range | market-data → get_price_history | "TSLA 52-week high/low" |
| Analyst ratings / P/E / market cap | market-data → get_analyst_consensus | "Consensus on AAPL" |
| Options data | market-data → get_options_chain | "NVDA options chain" |
| Earnings dates | market-data → get_earnings_calendar | "When does JPM report?" |
| 10-K annual reports | sec-edgar → get_10k | "NVDA latest 10-K" |
| 10-Q quarterly reports | sec-edgar → get_10q | "AAPL latest 10-Q" |
| 8-K current reports | sec-edgar → get_8k | "Tesla 8-K filings this week" |
| Insider transactions (Form 4) | sec-edgar → get_insider_transactions | "MSFT insider transactions" |
| Filing full-text search | sec-edgar → search_filings | "AI disclosure rules in 10-Ks" |
| Financial news search | news-search → search_financial_news | "Tesla news today" |
| Latest headlines | news-search → get_headlines | "Latest tech headlines" |
| News coverage for sentiment | news-search → get_news_coverage | "NVDA news coverage this week" |
| Client data / profiles | salesforce-crm → run_soql_query | "Client Henderson's profile" |
| Watchlist | salesforce-crm → run_soql_query | "What's on my watchlist?" |
| Audit logs | salesforce-crm → run_soql_query | "Audit log for yesterday" |
| Holdings | salesforce-crm → run_soql_query | "Client Patel's top holdings" |
| Research notes | salesforce-crm → run_soql_query | "Notes published this quarter" |
| Coverage / ratings | salesforce-crm → run_soql_query | "Our rating on META" |
| Compliance exceptions | salesforce-crm → run_soql_query | "Compliance exceptions last 7 days" |
| Object field discovery | salesforce-crm → describe_object | "What fields does IR_Watchlist__c have?" |

## SOQL Examples for Common Queries

### Watchlist & Coverage
- Watchlist: `SELECT Id, Name, Ticker__c, Reason__c, Priority__c, Earnings_Date__c FROM IR_Watchlist__c ORDER BY Priority__c`
- Who covers a stock: `SELECT Id, Analyst__c, Rating__c, Target_Price__c, Last_Updated__c FROM IR_Coverage__c WHERE Ticker__c = 'AAPL'`
- Our rating on a stock: `SELECT Id, Rating__c, Target_Price__c, Analyst__c FROM IR_Coverage__c WHERE Ticker__c = 'META'`
- Covered stocks: `SELECT Id, Ticker__c, Analyst__c, Sector__c FROM IR_Coverage__c`

### Client Data
- Client profile: `SELECT Id, Name, Industry, Phone, BillingCity, BillingState FROM Account WHERE Name LIKE '%Henderson%'`
- Client contacts: `SELECT Id, FirstName, LastName, Email, Phone, Title FROM Contact WHERE Account.Name LIKE '%Henderson%'`
- Clients with high AUM: `SELECT Id, Name, AnnualRevenue FROM Account WHERE AnnualRevenue > 5000000`
- Clients not contacted recently: `SELECT Id, Name, LastActivityDate FROM Account WHERE LastActivityDate < LAST_N_DAYS:90`

### Research & Audit
- Research notes this quarter: `SELECT Id, Name, Ticker__c, Analyst__c, Rating__c, CreatedDate FROM IR_Research_Note__c WHERE CreatedDate = THIS_QUARTER ORDER BY CreatedDate DESC`
- Audit log yesterday: `SELECT Id, Action__c, Query__c, Analyst__c, CreatedDate FROM IR_Audit_Log__c WHERE CreatedDate = YESTERDAY ORDER BY CreatedDate DESC`
- Compliance exceptions: `SELECT Id, Action__c, Query__c, CreatedDate FROM IR_Audit_Log__c WHERE Action__c LIKE '%exception%' AND CreatedDate = LAST_N_DAYS:7`

### Holdings (MNPI fields auto-redacted)
- Client holdings: `SELECT Id, Name, FinServ__FinancialAccount__c FROM FinServ__FinancialHolding__c`

## Important Notes
- If unsure about field names, call `describe_object` FIRST with the object name
- NEVER guess field names — always verify
- NEVER say "I don't have that data" without querying Salesforce first
