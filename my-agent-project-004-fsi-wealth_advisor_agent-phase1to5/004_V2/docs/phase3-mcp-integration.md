# Phase 3: MCP Integration — Implementation Guide

## Overview

Phase 3 extends the WA_P1to5_Advisor agent with external data sources via the Model Context Protocol (MCP). This enables the agent to answer market data questions, surface financial news, and orchestrate with other agents (e.g., Compliance) — all without leaving the Agentforce conversation.

**Prerequisites:**
- WA_P1to5_Advisor agent deployed and active (from Phases 1–2)
- Data Cloud with WA_*_c_Home__dlm tables populated
- API keys for external services (Alpha Vantage, NewsAPI)
- Salesforce CLI authenticated to your org

---

## 3A. External Market Data via MCP

### What This Enables
Advisors can ask real-time market questions alongside client data:
- "What's the S&P 500 doing today?"
- "How does Wei Chen's portfolio compare to the market?"
- "Show me Apple's stock price over the last 3 months"

### Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                     WA_P1to5_Advisor Agent                       │
│                                                                  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────────┐│
│  │ client   │  │portfolio │  │ market   │  │ Other existing   ││
│  │ _lookup  │  │ _review  │  │ _data    │  │ topics...        ││
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └──────────────────┘│
│       │              │             │                             │
│       ▼              ▼             ▼                             │
│  DC_Client      DC_Portfolio   MCP Connector                    │
│  LookupAction   ReviewAction   (market-data)                    │
│       │              │             │                             │
│       ▼              ▼             ▼                             │
│  Data Cloud      Data Cloud    Alpha Vantage                    │
│  (DLM tables)    (DLM tables)  REST API                         │
└──────────────────────────────────────────────────────────────────┘
```

### Step 1: Get an Alpha Vantage API Key

1. Go to [https://www.alphavantage.co/support/#api-key](https://www.alphavantage.co/support/#api-key)
2. Register for a free API key (5 requests/minute, 500/day)
3. For production, upgrade to a premium key ($49.99/month for 75 req/min)
4. Store the key securely — you'll reference it in the MCP config

### Step 2: MCP Server Configuration

The MCP server config lives at `mcp-config/mcp-market-data.json` (already created in this project). Key settings:

```json
{
  "mcpServers": {
    "market-data": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-market-data"],
      "env": {
        "ALPHA_VANTAGE_API_KEY": "${ALPHA_VANTAGE_API_KEY}",
        "MARKET_DATA_BASE_URL": "https://www.alphavantage.co/query",
        "RATE_LIMIT_PER_MINUTE": "5",
        "CACHE_TTL_SECONDS": "300"
      },
      "capabilities": {
        "tools": [
          {
            "name": "get_stock_quote",
            "description": "Get real-time stock quote for a given ticker symbol",
            "inputSchema": {
              "type": "object",
              "properties": {
                "symbol": { "type": "string", "description": "Ticker (e.g., AAPL, MSFT, SPY)" }
              },
              "required": ["symbol"]
            }
          },
          {
            "name": "get_market_index",
            "description": "Get current value and daily change for a market index",
            "inputSchema": {
              "type": "object",
              "properties": {
                "index": { "type": "string", "enum": ["SPX", "DJI", "IXIC", "RUT"] }
              },
              "required": ["index"]
            }
          },
          {
            "name": "get_historical_prices",
            "description": "Get historical daily prices for a ticker over a date range",
            "inputSchema": {
              "type": "object",
              "properties": {
                "symbol": { "type": "string" },
                "period": { "type": "string", "enum": ["1W", "1M", "3M", "6M", "1Y", "5Y"] }
              },
              "required": ["symbol", "period"]
            }
          },
          {
            "name": "get_sector_performance",
            "description": "Get performance breakdown by market sector",
            "inputSchema": {
              "type": "object",
              "properties": {
                "period": { "type": "string", "enum": ["realtime", "1D", "5D", "1M", "3M", "YTD", "1Y"] }
              },
              "required": ["period"]
            }
          }
        ]
      }
    }
  }
}
```

### Step 3: Register MCP Connector in Agentforce

As of API v66.0, MCP connectors in Agentforce are configured via Setup UI:

1. **Navigate to Setup → MCP Connectors** (or search "MCP" in Quick Find)
2. Click **New MCP Connector**
3. Fill in:
   - **Label:** Market Data (Alpha Vantage)
   - **API Name:** Market_Data_Alpha_Vantage
   - **Server URL:** Point to your hosted MCP server endpoint
   - **Authentication:** API Key → paste your Alpha Vantage key
   - **Timeout:** 10 seconds
4. Click **Save & Test Connection**
5. Under **Available Tools**, verify all 4 tools appear:
   - `get_stock_quote`
   - `get_market_index`
   - `get_historical_prices`
   - `get_sector_performance`

> **Note:** If your org doesn't yet have the MCP Connectors UI (it's rolling out in stages), you can alternatively expose market data via a custom Apex action that calls the Alpha Vantage REST API using `Http` / `HttpRequest`. The agent topic definition below works with either approach.

### Step 4: Alternative — Apex-Based Market Data Action

If MCP connectors aren't available in your org, create an Apex class that calls Alpha Vantage directly:

```apex
public with sharing class DC_MarketDataAction {

    public class MarketInput {
        @InvocableVariable(label='Query' description='Market data query' required=true)
        public String query;
    }

    public class MarketOutput {
        @InvocableVariable(label='Market Summary' description='Market data response')
        public String marketSummary;
    }

    @InvocableMethod(label='Get Market Data' description='Fetch real-time market data from Alpha Vantage')
    public static List<MarketOutput> getMarketData(List<MarketInput> inputs) {
        List<MarketOutput> outputs = new List<MarketOutput>();
        for (MarketInput input : inputs) {
            MarketOutput output = new MarketOutput();
            try {
                // Parse query to determine symbol/index
                String symbol = extractSymbol(input.query);
                HttpRequest req = new HttpRequest();
                req.setEndpoint('callout:Alpha_Vantage/query?function=GLOBAL_QUOTE&symbol='
                    + EncodingUtil.urlEncode(symbol, 'UTF-8'));
                req.setMethod('GET');
                req.setTimeout(10000);
                Http http = new Http();
                HttpResponse res = http.send(req);
                if (res.getStatusCode() == 200) {
                    Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(res.getBody());
                    Map<String, Object> quote = (Map<String, Object>) body.get('Global Quote');
                    if (quote != null) {
                        output.marketSummary = symbol + ': $' + quote.get('05. price')
                            + ' | Change: ' + quote.get('09. change') + ' (' + quote.get('10. change percent') + ')'
                            + ' | Volume: ' + quote.get('06. volume');
                    } else {
                        output.marketSummary = 'No data found for symbol: ' + symbol;
                    }
                } else {
                    output.marketSummary = 'API error: HTTP ' + res.getStatusCode();
                }
            } catch (Exception e) {
                output.marketSummary = 'Error fetching market data: ' + e.getMessage();
            }
            outputs.add(output);
        }
        return outputs;
    }

    private static String extractSymbol(String query) {
        // Map common names to ticker symbols
        Map<String, String> symbolMap = new Map<String, String>{
            'S&P 500' => 'SPY', 'S&P' => 'SPY', 'SP500' => 'SPY',
            'DOW' => 'DIA', 'NASDAQ' => 'QQQ', 'RUSSELL' => 'IWM',
            'APPLE' => 'AAPL', 'MICROSOFT' => 'MSFT', 'GOOGLE' => 'GOOGL',
            'AMAZON' => 'AMZN', 'TESLA' => 'TSLA', 'META' => 'META'
        };
        String upper = query.toUpperCase().trim();
        for (String key : symbolMap.keySet()) {
            if (upper.contains(key)) return symbolMap.get(key);
        }
        // If no match, assume the query itself is a ticker
        return upper.replaceAll('[^A-Z]', '');
    }
}
```

**Setup for the Apex approach:**
1. Create a Named Credential called `Alpha_Vantage`:
   - URL: `https://www.alphavantage.co`
   - Auth: Named Principal → API Key (pass as query param `apikey`)
2. Add `https://www.alphavantage.co` to Remote Site Settings
3. Deploy the class and grant access to the Einstein Agent User

### Step 5: Agent Topic Definition — market_data

Add this topic to the `.agent` file for WA_P1to5_Advisor:

```yaml
topic market_data:
    label: "Market Data"
    description: "Get real-time market data, stock quotes, index performance, and sector analysis"

    actions:
        get_market_data:
            description: "Fetch real-time market data including stock quotes, index values, and sector performance. Supports ticker symbols and common names like 'S&P 500', 'Apple', 'Dow'."
            inputs:
                query: string
                    description: "The market data query — a ticker symbol (AAPL), index name (S&P 500), or natural language question"
            outputs:
                marketSummary: string
                    description: "Market data summary with price, change, and volume"
            target: "apex://DC_MarketDataAction"

    reasoning:
        instructions:->
            if @variables.result:
                | Here is the market data:
                  {!@variables.result}
            else:
                | Use get_market_data to fetch the requested market information. Extract the ticker symbol or index name from the user message.
                  For portfolio comparison questions, first call get_portfolio_summary from the portfolio_review topic, then call get_market_data for the benchmark.
        actions:
            get_market_data: @actions.get_market_data
                with query=...
                set @variables.result = @outputs.marketSummary
```

### Test Queries for market_data Topic

| Query | Expected Behavior |
|-------|-------------------|
| "What's the S&P 500 doing today?" | Calls get_market_data with SPY, returns index price + change |
| "Show me Apple's stock price" | Calls get_market_data with AAPL |
| "How does Wei Chen's portfolio compare to the market?" | Calls portfolio_review first, then market_data for SPY benchmark |
| "What's happening in the tech sector?" | Calls get_sector_performance for tech sector |

---

## 3B. News Feed via MCP

### What This Enables
Advisors can get financial news relevant to their clients' holdings:
- "Any news about Apple stock?"
- "What's in the news for the tech sector?"
- Cross-reference news with portfolio holdings

### MCP Server Configuration

Save to `mcp-config/mcp-news-feed.json`:

```json
{
  "mcpServers": {
    "financial-news": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-server-news"],
      "env": {
        "NEWS_API_KEY": "${NEWS_API_KEY}",
        "NEWS_API_BASE_URL": "https://newsapi.org/v2",
        "DEFAULT_CATEGORY": "business",
        "MAX_ARTICLES": "5",
        "CACHE_TTL_SECONDS": "600"
      },
      "description": "MCP server for financial news via NewsAPI",
      "capabilities": {
        "tools": [
          {
            "name": "search_news",
            "description": "Search for financial news articles by keyword, company, or topic",
            "inputSchema": {
              "type": "object",
              "properties": {
                "query": {
                  "type": "string",
                  "description": "Search query (company name, ticker, topic)"
                },
                "category": {
                  "type": "string",
                  "description": "News category filter",
                  "enum": ["business", "technology", "general"]
                },
                "maxResults": {
                  "type": "integer",
                  "description": "Maximum number of articles to return",
                  "default": 5
                }
              },
              "required": ["query"]
            }
          },
          {
            "name": "get_market_headlines",
            "description": "Get top financial market headlines",
            "inputSchema": {
              "type": "object",
              "properties": {
                "country": {
                  "type": "string",
                  "description": "Country code for headlines",
                  "default": "us"
                },
                "maxResults": {
                  "type": "integer",
                  "default": 5
                }
              }
            }
          },
          {
            "name": "get_company_news",
            "description": "Get news specific to a company by ticker symbol",
            "inputSchema": {
              "type": "object",
              "properties": {
                "symbol": {
                  "type": "string",
                  "description": "Stock ticker symbol (e.g., AAPL, MSFT)"
                },
                "days": {
                  "type": "integer",
                  "description": "Number of days to look back",
                  "default": 7
                }
              },
              "required": ["symbol"]
            }
          }
        ]
      }
    }
  }
}
```

### Register News MCP Connector in Agentforce

1. **Setup → MCP Connectors → New**
2. Fill in:
   - **Label:** Financial News (NewsAPI)
   - **API Name:** Financial_News_NewsAPI
   - **Server URL:** Your hosted MCP news server endpoint
   - **Authentication:** API Key
   - **Timeout:** 10 seconds
3. **Save & Test Connection**

### Agent Topic Definition — market_news

```yaml
topic market_news:
    label: "Market News"
    description: "Get financial news, market headlines, and company-specific news. Can cross-reference with client portfolio holdings."

    actions:
        search_financial_news:
            description: "Search for financial news by company, ticker, or topic. Returns headlines, summaries, and sources."
            inputs:
                query: string
                    description: "Search query — company name, ticker symbol, or topic"
            outputs:
                newsSummary: string
                    description: "News articles summary with headlines and key points"
            target: "apex://DC_NewsSearchAction"

    reasoning:
        instructions:->
            if @variables.result:
                | Here are the latest news articles:
                  {!@variables.result}
            else:
                | Use search_financial_news to find relevant news. Extract the company name, ticker, or topic from the user message.
                  If the user asks about news related to a client's portfolio, first look up their holdings via portfolio_review, then search news for each major holding.
        actions:
            search_financial_news: @actions.search_financial_news
                with query=...
                set @variables.result = @outputs.newsSummary
```

### Cross-Reference Flow: News + Portfolio

When an advisor asks "Any news affecting Wei Chen's portfolio?", the agent should:

1. Route to `portfolio_review` → call `DC_PortfolioReviewAction` → get holdings list
2. Route to `market_news` → call `search_financial_news` for each major holding
3. Synthesize: "Wei Chen holds AAPL (35%), MSFT (25%), VTI (40%). Here's relevant news..."

This multi-step flow works because the agent's planner can chain topic transitions within a single conversation turn.

### Test Queries for market_news Topic

| Query | Expected Behavior |
|-------|-------------------|
| "Any news about Apple stock?" | Searches news for AAPL |
| "What are today's market headlines?" | Returns top financial headlines |
| "Any news affecting the Patel portfolio?" | Looks up Patel holdings, then searches news for each |

---

## 3C. Agent-to-Agent Orchestration via MCP

### What This Enables
The Wealth Advisor agent can delegate compliance checks to a separate Compliance agent, creating a multi-agent workflow:
- Advisor asks: "Is the Patel account compliant?"
- Wealth Advisor agent → calls Compliance agent via MCP
- Compliance agent checks suitability rules → returns pass/fail
- Wealth Advisor agent presents results to the advisor

### Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        ADVISOR CONVERSATION                             │
│                                                                         │
│  Advisor: "Is the Patel account compliant?"                             │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              WA_P1to5_Advisor (Primary Agent)                     │  │
│  │                                                                   │  │
│  │  1. Topic Selector → compliance_check                             │  │
│  │  2. Calls DC_ComplianceCheckAction (Apex)                         │  │
│  │     └─ Queries Data Cloud for client risk profile + allocation    │  │
│  │  3. Calls Compliance Agent via MCP                                │  │
│  │     └─ Passes: risk_profile, current_allocation, account_type     │  │
│  └──────────────┬────────────────────────────────────────────────────┘  │
│                 │                                                        │
│                 │  MCP Call (agent-to-agent)                              │
│                 ▼                                                        │
│  ┌───────────────────────────────────────────────────────────────────┐  │
│  │              WA_Compliance_Agent (Secondary Agent)                 │  │
│  │                                                                   │  │
│  │  1. Receives: risk_profile, allocation, account_type              │  │
│  │  2. Checks suitability rules:                                     │  │
│  │     - Conservative client → max 30% equities                      │  │
│  │     - Moderate client → max 60% equities                          │  │
│  │     - Aggressive client → max 90% equities                        │  │
│  │  3. Returns: PASS/FAIL + violations list                          │  │
│  └──────────────┬────────────────────────────────────────────────────┘  │
│                 │                                                        │
│                 ▼                                                        │
│  Agent: "The Patel account (Moderate risk) is COMPLIANT.                │
│          Current equity allocation: 55% (limit: 60%). No violations."   │
└─────────────────────────────────────────────────────────────────────────┘
```

### Step 1: Create the Compliance Agent

The Compliance agent is a separate Agentforce agent with a single topic:

```yaml
# WA_Compliance_Agent.agent
system:
    instructions: "You are a compliance validation tool. You check client accounts against suitability rules and return PASS or FAIL with specific violations."
    messages:
        welcome: "Compliance Agent ready."
        error: "Compliance check failed."

config:
    developer_name: "WA_Compliance_Agent"
    agent_label: "WA Compliance Agent"
    description: "Validates client account compliance against suitability rules"

topic compliance_validation:
    label: "Compliance Validation"
    description: "Validate account suitability based on risk profile and allocation"

    actions:
        validate_compliance:
            description: "Check if a client's portfolio allocation matches their risk profile"
            inputs:
                clientName: string
                    description: "Client or household name"
            outputs:
                complianceResult: string
                    description: "PASS/FAIL with violation details"
            target: "apex://DC_ComplianceValidationAction"

    reasoning:
        instructions:->
            | Use validate_compliance to check the client's account. Return the result exactly as provided by the action.
        actions:
            validate_compliance: @actions.validate_compliance
                with clientName=...
```

### Step 2: MCP Configuration for Agent-to-Agent

```json
{
  "mcpServers": {
    "compliance-agent": {
      "command": "sf",
      "args": ["agent", "invoke", "--agent-name", "WA_Compliance_Agent"],
      "env": {
        "SF_ORG_ALIAS": "${SF_ORG_ALIAS}",
        "TIMEOUT_SECONDS": "30"
      },
      "description": "MCP bridge to the WA Compliance Agent for suitability checks",
      "capabilities": {
        "tools": [
          {
            "name": "check_compliance",
            "description": "Invoke the Compliance Agent to validate account suitability",
            "inputSchema": {
              "type": "object",
              "properties": {
                "clientName": {
                  "type": "string",
                  "description": "Client or household name to check"
                },
                "checkType": {
                  "type": "string",
                  "description": "Type of compliance check",
                  "enum": ["suitability", "concentration", "regulatory", "full"]
                }
              },
              "required": ["clientName"]
            }
          }
        ]
      }
    }
  }
}
```

### Step 3: Register in Agentforce

1. **Setup → MCP Connectors → New**
2. Fill in:
   - **Label:** Compliance Agent (Internal)
   - **API Name:** Compliance_Agent_Internal
   - **Type:** Internal Agent
   - **Target Agent:** WA_Compliance_Agent
   - **Timeout:** 30 seconds
3. **Save**

### Step 4: Add Compliance Topic to Primary Agent

Add to the WA_P1to5_Advisor `.agent` file's topic_selector:

```yaml
# Add to topic_selector reasoning actions:
go_to_compliance_check: @utils.transition to @topic.compliance_check
    description: "User wants to check compliance or suitability"
```

### Suitability Rules Reference

| Risk Profile | Max Equities | Max Alternatives | Min Fixed Income |
|-------------|-------------|-----------------|-----------------|
| Conservative | 30% | 5% | 50% |
| Moderate | 60% | 15% | 25% |
| Aggressive | 90% | 30% | 5% |
| Very Aggressive | 100% | 40% | 0% |

### Multi-Agent Flow Sequence

```
1. Advisor: "Is the Patel account compliant?"
2. WA_P1to5_Advisor:
   a. Topic Selector → compliance_check
   b. Calls DC_ComplianceCheckAction (local Apex)
      - Queries Data Cloud for Patel household
      - Gets risk_profile = "Moderate", current equities = 55%
   c. Calls Compliance Agent via MCP
      - Passes: clientName="Patel", checkType="suitability"
   d. Compliance Agent returns: "PASS — Moderate risk, 55% equities (limit 60%)"
3. WA_P1to5_Advisor presents result to advisor
```

---

## Summary: New Topics Added in Phase 3

| Topic | Source | Tools/Actions |
|-------|--------|---------------|
| `market_data` | MCP → Alpha Vantage (or Apex fallback) | get_stock_quote, get_market_index, get_historical_prices, get_sector_performance |
| `market_news` | MCP → NewsAPI (or Apex fallback) | search_news, get_market_headlines, get_company_news |
| `compliance_check` | MCP → WA_Compliance_Agent | check_compliance (delegates to secondary agent) |

## Updated Topic Selector

After Phase 3, the WA_P1to5_Advisor topic selector should include:

```yaml
start_agent topic_selector:
    label: "Topic Selector"
    description: "Route to the right topic"

    reasoning:
        instructions:|
            Select the tool that best matches the user's message.
        actions:
            go_to_client_lookup: @utils.transition to @topic.client_lookup
                description: "User wants to look up a client or household"
            go_to_portfolio_review: @utils.transition to @topic.portfolio_review
                description: "User wants to review a portfolio or check performance"
            go_to_goal_planning: @utils.transition to @topic.goal_planning
                description: "User wants to check financial goals or progress"
            go_to_meeting_prep: @utils.transition to @topic.meeting_prep
                description: "User wants to prepare for a client meeting"
            go_to_market_data: @utils.transition to @topic.market_data
                description: "User wants market data, stock quotes, or index performance"
            go_to_market_news: @utils.transition to @topic.market_news
                description: "User wants financial news or headlines"
            go_to_compliance_check: @utils.transition to @topic.compliance_check
                description: "User wants to check compliance or suitability"
            go_to_escalation: @utils.transition to @topic.escalation
                description: "User wants to speak to a human"
            go_to_off_topic: @utils.transition to @topic.off_topic
                description: "User request is off-topic"
```
