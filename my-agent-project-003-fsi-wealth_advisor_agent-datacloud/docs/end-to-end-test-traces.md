# WA DC Advisor - End-to-End Test Traces

All queries tested against Data Cloud DMOs via `ConnectApi.CdpQuery.queryAnsiSqlV2()`.

```
═══════════════════════════════════════════════════════════════════════════════
QUERY 1: "Tell me about the Johnsons"
═══════════════════════════════════════════════════════════════════════════════

REQUEST:  "Tell me about the Johnsons"
TOPIC:    Topic Selector → client_lookup
ACTION:   get_client_360 (DC_ClientLookupAction.cls)
TOOL:     ConnectApi.CdpQuery.queryAnsiSqlV2()
SQL:      SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c, Advisor_c__c, Id__c
          FROM WA_Household_c_Home__dlm
          WHERE Name__c LIKE '%Johnson%'
DATA:     WA_Household_c_Home__dlm → 1 row
          WA_Client_c_Home__dlm → 2 rows
          WA_Financial_Account_c_Home__dlm → 3 rows

RESPONSE: Johnson Family household has total AUM of $2.8 million, moderate risk
          profile. Advisor: Alex Morgan.
          Members:
            Sarah Johnson (Primary) | sarah.johnson@email.com
            Tom Johnson (Spouse) | tom.johnson@email.com
          Accounts:
            Johnson Family Trust (Trust): $1.5M
            Johnson IRA (IRA): $450K
            Johnson 401k (401k): $820K

RESULT:   Topic ✅ | Action ✅ | Outcome ✅


═══════════════════════════════════════════════════════════════════════════════
QUERY 2: "How is Wei Chen's portfolio?"
═══════════════════════════════════════════════════════════════════════════════

REQUEST:  "How is Wei Chen's portfolio?"
TOPIC:    Topic Selector → portfolio_review
ACTION:   get_portfolio_summary (DC_PortfolioReviewAction.cls)
TOOL:     ConnectApi.CdpQuery.queryAnsiSqlV2()
SQL:      SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm
          WHERE Name__c LIKE '%Wei Chen%'
          → then: SELECT Name__c, Risk_Profile_c__c FROM WA_Household_c_Home__dlm
          → then: SELECT Name__c, Type_c__c, Balance_c__c, Allocation_c__c,
                  YTD_Return_c__c FROM WA_Financial_Account_c_Home__dlm
DATA:     WA_Client_c_Home__dlm → 1 row (Wei Chen)
          WA_Household_c_Home__dlm → 1 row (Chen Family)
          WA_Financial_Account_c_Home__dlm → 2 rows

RESPONSE: Wei Chen's portfolio summary:
          Household: Chen Family
          Risk Profile: Aggressive
          Accounts:
            Chen Roth IRA - Balance: $850K, Allocation: 75% Equity / 20% Fixed
              / 5% Cash, YTD Return: 11.1%
            Chen Brokerage - Balance: $2.2M, Allocation: 80% Equity / 15% Fixed
              / 5% Cash, YTD Return: 12.3%
          Total portfolio value: $3.0M

RESULT:   Topic ✅ | Action ✅ | Outcome ✅


═══════════════════════════════════════════════════════════════════════════════
QUERY 3: "What are the Patels' goals?"
═══════════════════════════════════════════════════════════════════════════════

REQUEST:  "What are the Patels' goals?"
TOPIC:    Topic Selector → goal_planning
ACTION:   get_financial_goals (DC_GoalPlanningAction.cls)
TOOL:     ConnectApi.CdpQuery.queryAnsiSqlV2()
SQL:      SELECT Id__c, Name__c FROM WA_Household_c_Home__dlm
          WHERE Name__c LIKE '%Patel%'
          → then: SELECT Id__c FROM WA_Client_c_Home__dlm
                  WHERE Household_c__c = '<patel_hh_id>'
          → then: SELECT Name__c, Target_Amount_c__c, Current_Amount_c__c,
                  Target_Date_c__c FROM WA_Financial_Goal_c_Home__dlm
                  WHERE Client_c__c IN ('<id1>','<id2>')
DATA:     WA_Household_c_Home__dlm → 1 row (Patel Family)
          WA_Client_c_Home__dlm → 2 rows (Raj, Priya)
          WA_Financial_Goal_c_Home__dlm → 2 rows

RESPONSE: The Patels have two main financial goals:
          Philanthropy Fund
            Target: $1.0M | Current: $650K | Progress: 65% | Gap: $350K
            Target Date: December 31, 2030
          Retirement
            Target: $8.0M | Current: $6.5M | Progress: 81.2% | Gap: $1.5M
            Target Date: January 1, 2033

RESULT:   Topic ✅ | Action ✅ | Outcome ✅


═══════════════════════════════════════════════════════════════════════════════
QUERY 4: "Prep me for my meeting with Carlos"
═══════════════════════════════════════════════════════════════════════════════

REQUEST:  "Prep me for my meeting with Carlos"
TOPIC:    Topic Selector → meeting_prep
ACTION:   get_meeting_prep (DC_MeetingPrepAction.cls)
TOOL:     ConnectApi.CdpQuery.queryAnsiSqlV2()
SQL:      SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm
          WHERE Name__c LIKE '%Carlo%'
          → then: SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c
                  FROM WA_Household_c_Home__dlm
          → then: SELECT Name__c, Date_Time_c__c, Location_c__c, Notes_c__c,
                  Action_Items_c__c FROM WA_Meeting_c_Home__dlm
          → then: SELECT Name__c, Type_c__c, Balance_c__c, YTD_Return_c__c
                  FROM WA_Financial_Account_c_Home__dlm
          → then: SELECT Name__c, Target_Amount_c__c, Current_Amount_c__c
                  FROM WA_Financial_Goal_c_Home__dlm
DATA:     WA_Client_c_Home__dlm → 1 row (Carlos Martinez)
          WA_Household_c_Home__dlm → 1 row (Martinez Family)
          WA_Meeting_c_Home__dlm → 1 row
          WA_Financial_Account_c_Home__dlm → 1 row
          WA_Financial_Goal_c_Home__dlm → 2 rows

RESPONSE: Meeting Prep for Carlos Martinez:
          Client: Carlos Martinez (Martinez Family)
          Total AUM: $1.2M | Risk Profile: Conservative
          Upcoming Meeting:
            Subject: Retirement Planning Check-in
            Date: April 2, 2026
            Location: Office - Conference Room B
            Notes: Carlos wants to discuss moving retirement date earlier
            Action Items: Run updated retirement projections; review vacation
              home savings plan
          Portfolio Snapshot:
            Martinez IRA: $680K (YTD: 4.1%)
          Goals Status:
            Retirement: 80% ($1.2M / $1.5M)
            Vacation Home: 34% ($120K / $350K)
          Suggested Talking Points:
            1. Review portfolio performance and rebalancing needs
            2. Discuss progress toward financial goals
            3. Address life changes or updated priorities
            4. Review and confirm risk tolerance

RESULT:   Topic ✅ | Action ✅ | Outcome ✅


═══════════════════════════════════════════════════════════════════════════════
QUERY 5: "Transfer me to compliance"
═══════════════════════════════════════════════════════════════════════════════

REQUEST:  "Transfer me to compliance"
TOPIC:    Topic Selector → escalation
ACTION:   (escalation - no Apex action)
TOOL:     @utils.escalate
DATA:     N/A

RESPONSE: You are being transferred to compliance. Is there anything specific
          you would like them to address?

RESULT:   Topic ✅ | Outcome ✅


═══════════════════════════════════════════════════════════════════════════════
QUERY 6: "What's the stock price of Apple?"
═══════════════════════════════════════════════════════════════════════════════

REQUEST:  "What's the stock price of Apple?"
TOPIC:    Topic Selector → off_topic
ACTION:   (none - redirect only)
TOOL:     N/A
DATA:     N/A

RESPONSE: I am here to assist with wealth advisory topics such as client
          lookups, portfolio reviews, goal planning, and meeting preparation.
          How can I help you with your wealth management needs today?

RESULT:   Topic ✅ | Outcome ✅


═══════════════════════════════════════════════════════════════════════════════
SUMMARY
═══════════════════════════════════════════════════════════════════════════════

Test Results:  6/6 PASSING
Topic:         100% (6/6)
Action:         67% (4/6 - escalation and off_topic have no trackable actions)
Outcome:       100% (6/6)
Data Source:   Salesforce Data Cloud (ConnectApi.CdpQuery → *__dlm DMOs)
Duration:      1m 14s
```
