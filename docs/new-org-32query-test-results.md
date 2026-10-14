# Test Results (32-Query Full Run) — New Org Reproducibility Test

```
Org: orgfarm-035b70d101-dev-ed (fresh Agentforce Developer Edition)
Agent: WA_P1to5_Advisor v1
Test: WA_P1to5_Advisor_Full_Test (32 queries)
Method: sf agent test run --api-name WA_P1to5_Advisor_Full_Test (end-to-end through agent)
Date: 2026-04-03
Duration: 4m 13s
```

## Results Summary

| Metric | Score | Count |
|--------|-------|-------|
| Topic Pass | 96.88% | 31/32 |
| Action Pass | 87.50% | 28/32 |
| Outcome Pass | 100.00% | 32/32 |

## Full 32-Query Results — With Actual Agent Responses

| # | Query | Topic | Action | Outcome | Agent Response (truncated) |
|---|-------|:-----:|:------:|:-------:|---------------------------|
| 1 | Tell me about the Johnson household | ✅ | ✅ | ✅ | Johnson Family household has $2.8M AUM, moderate risk profile. Advisor: Alex Morgan. Members: Sarah Johnson (Primary), Tom Johnson (Spouse). Accounts: Johnson Family Trust $1.5M, Johnson IRA $450K, Johnson 401k $820K. |
| 2 | Tell me about the Chen family | ✅ | ✅ | ✅ | Chen Family household has $4.1M AUM, aggressive risk profile. Members: Wei Chen (Primary), Lin Chen (Spouse). Accounts: Chen Brokerage $2.2M, Chen Roth IRA $850K, Chen 529 Plan $1.05M. |
| 3 | Tell me about the Martinez household | ✅ | ✅ | ✅ | Martinez Family household has $1.2M AUM, conservative risk profile. Members: Carlos Martinez (Primary), Maria Martinez (Spouse). Accounts: Martinez IRA $680K, Martinez 401k $520K. |
| 4 | Tell me about the Patel family | ✅ | ✅ | ✅ | Patel Family household has $6.5M AUM, moderate risk profile. Members: Raj Patel (Primary), Priya Patel (Spouse). Accounts: Patel Brokerage $3.2M, Patel Trust $2.1M, Patel Roth IRA $1.2M. |
| 5 | Tell me about the Williams family | ✅ | ✅ | ✅ | Williams Family household has $890K AUM, growth risk profile. Members: James Williams (Primary), Olivia Williams (Spouse). Accounts: Williams 401k $520K, Williams IRA $370K. |
| 6 | How is Wei Chen's portfolio? | ✅ | ✅ | ✅ | Wei Chen's portfolio valued at $3.0M, aggressive risk. Chen Brokerage: $2.2M (80/15/5, YTD 12.3%). Chen Roth IRA: $850K (75/20/5, YTD 11.1%). |
| 7 | How is Raj Patel's portfolio performing? | ✅ | ✅ | ✅ | Raj Patel's portfolio valued at $5.3M, moderate risk. Patel Brokerage: $3.2M (65/25/10, YTD 9.7%). Patel Trust: $2.1M (55/35/10, YTD 6.9%). |
| 8 | Show me James Williams portfolio | ✅ | ✅ | ✅ | James Williams portfolio: $520K. Williams 401k: 70/20/10, YTD 10.2%. |
| 9 | What are the Johnsons' retirement goals? | ✅ | ✅ | ✅ | Johnson Family goals: Retirement $2.8M/$3M (93.3%), College Fund Emma $145K/$200K (72.5%). |
| 10 | What are the Patels' goals? | ✅ | ✅ | ✅ | Patel Family goals: Retirement $6.5M/$8M (81.2%), Philanthropy Fund $650K/$1M (65.0%). |
| 11 | What goals does Carlos Martinez have? | ✅ | ✅ | ✅ | Carlos Martinez goals: Retirement $1.2M/$1.5M (80%), Vacation Home $120K/$350K (34.3%). |
| 12 | Prep me for my meeting with Sarah Johnson | ✅ | ✅ | ✅ | Meeting brief: Sarah Johnson, Johnson Family, $2.8M, Moderate. Annual Portfolio Review, Conference Room A. Portfolio + goals included. |
| 13 | Prep me for my meeting with Carlos | ✅ | ✅ | ✅ | Meeting brief: Carlos Martinez, Martinez Family, $1.2M, Conservative. Retirement Planning Check-in, Conference Room B. |
| 14 | Prepare my meeting with Raj Patel | ✅ | ✅ | ✅ | Meeting brief: Raj Patel, Patel Family, $6.5M, Moderate. Estate Planning Discussion, Client Home. |
| 15 | Does Sarah Johnson need rebalancing? | ✅ | ✅ | ✅ | Sarah Johnson does not need rebalancing. All accounts within tolerance. Johnson IRA: drift at threshold (5%). |
| 16 | Check rebalancing for Wei Chen | ✅ | ✅ | ✅ | Wei Chen does not need rebalancing. Chen Brokerage matches target exactly. All within 5% threshold. |
| 17 | Does the Martinez account need rebalancing? | ✅ | ✅ | ✅ | Martinez account does not need rebalancing. All accounts within tolerance. |
| 18 | Show me recent transactions for Sarah Johnson | ✅ | ✅ | ✅ | Sarah Johnson transactions: Buy $25K VTI, Sell $15K BND, Buy $50K AAPL, Sell $30K MSFT, dividends, fees. Total Buys: $75K, Sells: $45K. |
| 19 | What are Wei Chen's latest transactions? | ✅ | ✅ | ✅ | Wei Chen transactions: Buy $100K NVDA, Buy $35K QQQ, Buy $75K TSLA, Sell $50K META, Sell $80K AMZN, dividends, fees. |
| 20 | Show me Raj Patel's transaction history | ✅ | ✅ | ✅ | Raj Patel transactions: Buy $200K VTI, Buy $50K BND, Sell $150K AAPL, Buy $100K MSFT, dividends, fees. Total Buys: $350K, Sells: $265K. |
| 21 | Is the Patel account compliant? | ✅ | ✅ | ✅ | Patel account is compliant. All accounts meet target allocations and risk profile requirements. |
| 22 | Run a compliance check on the Martinez household | ✅ | ✅ | ✅ | Martinez household compliant. Conservative risk (target 30/60/10). IRA: 40/50/10 ✓, 401k: 35/55/10 ✓. Status: PASS. |
| 23 | Check compliance for Wei Chen | ✅ | ✅ | ✅ | Wei Chen (Chen Family) compliant. Aggressive risk (target 80/15/5). All 3 accounts meet or exceed compliance standards. |
| 24 | Who referred the Williams family? | ✅ | ✅ | ✅ | Williams family referred through LinkedIn Campaign Q4 (Marketing), 2024-10-05, Status: New, Value: $1.2M. |
| 25 | Who referred the Johnsons? | ✅ | ✅ | ✅ | Johnsons referred by Dr. Robert Kim (Client), 2023-03-15, Status: Converted, Value: $2.8M. |
| 26 | What's the referral source for the Patels? | ✅ | ✅ | ✅ | Patels referred by Sarah Johnson (Client), 2021-06-10, Status: Converted, Value: $6.5M. |
| 27 | Transfer me to a specialist | ✅ | — | ✅ | You will be transferred to a specialist for further assistance. Is there anything specific you would like the specialist to help you with? |
| 28 | I need to speak to a human | ✅ | — | ✅ | I will connect you to a human advisor. Is there anything specific you would like them to assist you with? |
| 29 | What is the weather today? | ✅ | — | ✅ | I am here to assist with wealth advisory topics such as client portfolios, financial goals, market data, and related services. |
| 30 | What's the stock price of Apple? | ❌ topic | — | ✅ | The market data service is temporarily unavailable, so I cannot retrieve the current stock price of Apple right now. (Routed to market_data instead of off_topic) |
| 31 | Tell me about the Johnsons (plural) | ✅ | ✅ | ✅ | Johnson Family household $2.8M AUM, moderate risk. Sarah Johnson (Primary), Tom Johnson (Spouse). 3 accounts. Fuzzy match handled plural "Johnsons". |
| 32 | How is Carlos doing on his goals? (first name) | ✅ | ✅ | ✅ | Carlos goals: Retirement 80% ($1.2M/$1.5M, gap $300K, target 2038). Vacation Home 34.3% ($120K/$350K, gap $230K, target 2029). First-name fuzzy match worked. |

## Comparison: Original Org vs New Org

| Metric | Original Org (1124a2bced) | New Org (035b70d101) | Delta |
|--------|--------------------------|----------------------|-------|
| Topic Pass | 100% (32/32) | 96.88% (31/32) | -1 (Q30 market_data vs off_topic) |
| Action Pass | 87.50% | 87.50% | Same |
| Outcome Pass | 81.25% (26/32) | 100% (32/32) | +6 (DC streams now working) |
| Duration | 4m 12s | 4m 13s | Same |
| Transaction queries | ❌ (3 fails, no DC stream) | ✅ (3 pass) | Fixed |
| Referral queries | ❌ (3 fails, no DC stream) | ✅ (3 pass) | Fixed |

The new org scores better on Outcome (100% vs 81.25%) because Data Cloud streams for WA_Transaction__c and WA_Referral__c are now properly set up with DMO mappings. The original org had those streams pending.

Q30 ("stock price of Apple") routes to market_data instead of off_topic — this is actually correct behavior since the agent has a market_data topic. The original org's test expected off_topic, but the agent reasonably interprets "stock price" as a market data request.
