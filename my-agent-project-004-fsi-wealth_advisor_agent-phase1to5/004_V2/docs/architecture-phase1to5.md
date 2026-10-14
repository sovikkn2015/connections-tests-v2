# FSI Wealth Advisor Agent — Phase 1-5 Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    WA P1to5 ADVISOR — FULL ARCHITECTURE                         │
│                                                                                 │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                           TOPIC SELECTOR (10 topics)                      │  │
│  └──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘  │
│     │      │      │      │      │      │      │      │      │      │           │
│     ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼           │
│  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌────┐┌────┐ │
│  │CLIENT││PORT- ││GOAL  ││MEET- ││REBAL-││TRANS-││COMPL-││REFER-││ESC-││OFF │ │
│  │LOOK- ││FOLIO ││PLAN- ││ING   ││ANCING││ACTION││IANCE ││RAL   ││ALA-││TOP-│ │
│  │UP    ││REVIEW││NING  ││PREP  ││ALERTS││HIST. ││CHECK ││TRACK ││TION││IC  │ │
│  └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└────┘└────┘ │
│     │       │       │       │       │       │       │       │                  │
│     ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼                  │
│  DC_Client DC_Port DC_Goal DC_Meet DC_Reb DC_Txn DC_Comp DC_Ref               │
│  Lookup    folio   Plan    ing     alanc  Hist   liance  erral                 │
│  Action    Review  Action  Prep    ing    Action Check   Track                 │
│  (Apex)    Action  (Apex)  Action  Action (Apex) Action  Action               │
│            (Apex)          (Apex)  (Apex)        (Apex)  (Apex)               │
│     │       │       │       │       │       │       │       │                  │
│     └───────┴───────┴───────┴───────┴───────┴───────┴───────┘                  │
│                              │                                                  │
│                              ▼  ConnectApi.CdpQuery.queryAnsiSqlV2()            │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    DATA CLOUD (7 DLM Objects)                             │  │
│  │                                                                           │  │
│  │  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐          │  │
│  │  │WA_Household  │────▶│ WA_Client    │────▶│WA_Financial_     │          │  │
│  │  │__dlm         │ 1:N │ __dlm        │ 1:N │Account__dlm      │          │  │
│  │  └──────────────┘     └──────┬───────┘     └──────────────────┘          │  │
│  │                              │ 1:N                                        │  │
│  │                    ┌─────────┼─────────┬─────────┐                        │  │
│  │                    ▼         ▼         ▼         ▼                        │  │
│  │  ┌──────────────┐┌──────────┐┌────────────┐┌──────────────┐              │  │
│  │  │WA_Financial_ ││WA_Meet-  ││WA_Trans-   ││WA_Referral   │              │  │
│  │  │Goal__dlm     ││ing__dlm  ││action__dlm ││__dlm         │              │  │
│  │  └──────────────┘└──────────┘└────────────┘└──────────────┘              │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                              ▲                                                  │
│                              │  CRM Connector (auto-sync)                       │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                    SALESFORCE CRM (8 Custom Objects)                       │  │
│  │  WA_Household__c, WA_Client__c, WA_Financial_Account__c,                 │  │
│  │  WA_Financial_Goal__c, WA_Meeting__c, WA_Transaction__c,                 │  │
│  │  WA_Referral__c, WA_Audit_Log__c                                         │  │
│  └───────────────────────────────────────────────────────────────────────────┘  │
│                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════    │
│                                                                                 │
│  COMPLIANCE LOGGING                    MCP CONNECTORS (Phase 3)                 │
│  ┌──────────────────────┐              ┌──────────────────────────────────┐     │
│  │ WA_Audit_Log__c      │              │ Market Data (Alpha Vantage)      │     │
│  │                      │              │   get_stock_quote                │     │
│  │ Agent_Name__c        │              │   get_market_index               │     │
│  │ User__c              │              │   get_historical_prices          │     │
│  │ Topic__c             │              │   get_sector_performance         │     │
│  │ Action__c            │              ├──────────────────────────────────┤     │
│  │ Query__c             │              │ Financial News (NewsAPI)         │     │
│  │ Response_Summary__c  │              │   search_news                    │     │
│  │ Client_Accessed__c   │              │   get_market_headlines           │     │
│  │ Timestamp__c         │              │   get_company_news               │     │
│  │ Session_Id__c        │              ├──────────────────────────────────┤     │
│  └──────────────────────┘              │ Compliance Agent (Internal)      │     │
│                                        │   check_compliance (agent→agent) │     │
│  DEPLOYMENT CHANNELS (Phase 4)         └──────────────────────────────────┘     │
│  ┌──────────────────────────────────────────────────────────────────────┐       │
│  │  Web Chat (Experience Cloud)  │  Slack  │  Mobile (SF Mobile App)   │       │
│  └──────────────────────────────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────────────────────────────┘
```


## Data Model

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                           DATA MODEL (8 Objects)                                │
│                                                                                 │
│  ┌─────────────────────┐                                                        │
│  │  WA_Household__c    │                                                        │
│  │  ─────────────────  │                                                        │
│  │  Name (auto)        │                                                        │
│  │  Total_AUM__c       │                                                        │
│  │  Risk_Profile__c    │                                                        │
│  │  Advisor__c         │                                                        │
│  └────────┬────────────┘                                                        │
│           │ 1:N (Household__c)                                                  │
│           ▼                                                                     │
│  ┌─────────────────────┐                                                        │
│  │  WA_Client__c       │                                                        │
│  │  ─────────────────  │                                                        │
│  │  Name (auto)        │                                                        │
│  │  Household__c (FK)  │                                                        │
│  │  Email__c           │                                                        │
│  │  Phone__c           │                                                        │
│  │  Role__c            │                                                        │
│  └──┬──────┬──────┬──────┬──────┘                                               │
│     │      │      │      │  1:N (Client__c)                                     │
│     ▼      ▼      ▼      ▼                                                      │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │WA_Financial_ │ │WA_Financial_ │ │WA_Meeting__c │ │WA_Referral   │           │
│  │Account__c    │ │Goal__c       │ │              │ │__c           │           │
│  │──────────────│ │──────────────│ │──────────────│ │──────────────│           │
│  │Client__c(FK) │ │Client__c(FK) │ │Client__c(FK) │ │Client__c(FK) │           │
│  │Type__c       │ │Target_Amt__c │ │Date_Time__c  │ │Source__c     │           │
│  │Balance__c    │ │Current_Amt__c│ │Location__c   │ │Source_Type__c│           │
│  │Allocation__c │ │Target_Date__c│ │Notes__c      │ │Date__c       │           │
│  │YTD_Return__c │ └──────────────┘ │Action_Items  │ │Status__c     │           │
│  │Target_Alloc  │                  │__c           │ │Value__c      │           │
│  │ation__c      │                  └──────────────┘ └──────────────┘           │
│  └──────┬───────┘                                                               │
│         │ 1:N (Account__c)                                                      │
│         ▼                                                                       │
│  ┌──────────────┐                  ┌──────────────────────┐                     │
│  │WA_Transac-   │                  │ WA_Audit_Log__c      │                     │
│  │tion__c       │                  │ (Compliance Logging)  │                     │
│  │──────────────│                  │──────────────────────│                     │
│  │Client__c(FK) │                  │ Agent_Name__c        │                     │
│  │Account__c(FK)│                  │ User__c              │                     │
│  │Type__c       │                  │ Topic__c             │                     │
│  │Amount__c     │                  │ Action__c            │                     │
│  │Date__c       │                  │ Query__c             │                     │
│  │Symbol__c     │                  │ Response_Summary__c  │                     │
│  │Description__c│                  │ Client_Accessed__c   │                     │
│  └──────────────┘                  │ Timestamp__c         │                     │
│                                    │ Session_Id__c        │                     │
│                                    └──────────────────────┘                     │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Topic → Action → Apex Class Mapping

| # | Topic | Agent Action | Apex Class | Data Source |
|---|-------|-------------|------------|-------------|
| 1 | `client_lookup` | `get_client_360` | `DC_ClientLookupAction` | Data Cloud (CdpQuery) |
| 2 | `portfolio_review` | `get_portfolio_summary` | `DC_PortfolioReviewAction` | Data Cloud (CdpQuery) |
| 3 | `goal_planning` | `get_financial_goals` | `DC_GoalPlanningAction` | Data Cloud (CdpQuery) |
| 4 | `meeting_prep` | `get_meeting_prep` | `DC_MeetingPrepAction` | Data Cloud (CdpQuery) |
| 5 | `rebalancing_alerts` | `check_rebalancing` | `DC_RebalancingAction` | Data Cloud (CdpQuery) |
| 6 | `transaction_history` | `get_transactions` | `DC_TransactionHistoryAction` | Data Cloud (CdpQuery) |
| 7 | `compliance_check` | `run_compliance` | `DC_ComplianceCheckAction` | Data Cloud (CdpQuery) |
| 8 | `referral_tracking` | `get_referrals` | `DC_ReferralTrackingAction` | Data Cloud (CdpQuery) |
| 9 | `escalation` | `@utils.escalate` | (built-in) | N/A |
| 10 | `off_topic` | (none — redirect) | (none) | N/A |

## Apex Action Patterns

All 8 Apex actions follow the same pattern:

```
1. Input:  @InvocableVariable clientName (String)
2. Clean:  cleanClientName() — strips suffixes (household, family, the, etc.)
3. Search: CdpQuery LIKE '%name%' on WA_Client_c_Home__dlm or WA_Household_c_Home__dlm
4. Fallback: Split name into parts, try each part
5. Fallback: Search client → get household ID → search household
6. Query:  CdpQuery for related data (accounts, goals, meetings, etc.)
7. Format: Build human-readable summary string
8. Error:  try/catch → user-friendly error message
9. Output: @InvocableVariable summary (String)
```

Shared utility methods in every class:
- `cleanClientName(String)` — regex-based name normalization
- `safeStr(Object)` — null-safe string conversion
- `formatCurrency(Object)` — human-readable currency ($1.2M, $450K)

## Data Cloud DLM Object Names

| CRM Object | DLM Object (Data Cloud) |
|------------|------------------------|
| `WA_Household__c` | `WA_Household_c_Home__dlm` |
| `WA_Client__c` | `WA_Client_c_Home__dlm` |
| `WA_Financial_Account__c` | `WA_Financial_Account_c_Home__dlm` |
| `WA_Financial_Goal__c` | `WA_Financial_Goal_c_Home__dlm` |
| `WA_Meeting__c` | `WA_Meeting_c_Home__dlm` |
| `WA_Transaction__c` | `WA_Transaction_c_Home__dlm` |
| `WA_Referral__c` | `WA_Referral_c_Home__dlm` |

> Note: DLM names may vary by org. Run `scripts/apex/verify-data.apex` after creating data streams.

## Test Results Summary

| Test # | Query | Expected Topic | Expected Action |
|--------|-------|---------------|-----------------|
| 1 | "Tell me about the Johnsons" | client_lookup | get_client_360 |
| 2 | "How is Wei Chen's portfolio?" | portfolio_review | get_portfolio_summary |
| 3 | "What are the Patels' goals?" | goal_planning | get_financial_goals |
| 4 | "Prep me for my meeting with Carlos" | meeting_prep | get_meeting_prep |
| 5 | "Does Sarah Johnson need rebalancing?" | rebalancing_alerts | check_rebalancing |
| 6 | "Show me recent transactions for Wei Chen" | transaction_history | get_transactions |
| 7 | "Is the Patel account compliant?" | compliance_check | run_compliance |
| 8 | "Who referred the Williams family?" | referral_tracking | get_referrals |
| 9 | "Transfer me to a specialist" | escalation | (escalate) |
| 10 | "What is the weather today?" | off_topic | (redirect) |

Run tests: `sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --verbose`

## Demo Data Summary

| Household | AUM | Risk Profile | Members | Accounts | Goals | Transactions | Referral |
|-----------|-----|-------------|---------|----------|-------|-------------|----------|
| Johnson | $2.8M | Moderate | Sarah, Tom | 3 (IRA, 401k, Trust) | 2 | 10 | Client (Dr. Kim) |
| Chen | $4.1M | Aggressive | Wei, Lin | 3 (Brokerage, Roth, 529) | 2 | 11 | Event (Gala) |
| Martinez | $1.2M | Conservative | Carlos, Maria | 2 (IRA, 401k) | 2 | 8 | Partner (Bank) |
| Patel | $6.5M | Moderate | Raj, Priya | 3 (Brokerage, Trust, Roth) | 2 | 12 | Client (Sarah J.) |
| Williams | $890K | Growth | James, Olivia | 2 (401k, IRA) | 2 | 11 | Marketing (LinkedIn) |

Totals: 5 households, 10 clients, 13 accounts, 10 goals, 5 meetings, 52 transactions, 5 referrals.


## Phase-by-Phase Implementation Summary

### Phase 1: Hardening
- Improved fuzzy matching: regex-based name cleaning strips suffixes (household, family, the, etc.)
- Multi-level fallback: full name → name parts → client-to-household reverse lookup
- Error handling: all CdpQuery calls wrapped in try/catch with user-friendly messages
- Null-safe field access via `safeStr()` helper
- Expanded test coverage: 10 test cases covering all topics

### Phase 2: New Topics + Actions
- 4 new topics added to the agent: rebalancing_alerts, transaction_history, compliance_check, referral_tracking
- 4 new Apex actions: DC_RebalancingAction, DC_TransactionHistoryAction, DC_ComplianceCheckAction, DC_ReferralTrackingAction
- 2 new custom objects: WA_Transaction__c (7 fields), WA_Referral__c (6 fields)
- New field on WA_Financial_Account__c: Target_Allocation__c (for rebalancing drift calculation)
- 52 seed transactions across all 10 clients, 5 referrals (one per household)
- Rebalancing uses configurable target allocations by risk profile with 5% drift threshold
- Compliance checks: suitability rules, concentration risk (>80%), drift from target (>15%)

### Phase 3: MCP Integration
- MCP connector configs for Alpha Vantage (market data) and NewsAPI (financial news)
- Agent-to-agent orchestration: Wealth Advisor → Compliance Agent via MCP
- Market data tools: get_stock_quote, get_market_index, get_historical_prices, get_sector_performance
- News tools: search_news, get_market_headlines, get_company_news
- Apex fallback action (DC_MarketDataAction) for orgs without MCP connector support
- Cross-reference flow: portfolio holdings → news search per holding

### Phase 4: Deployment Channels
- Web Chat: Experience Cloud site with Embedded Service Messaging widget
- Slack: Salesforce for Slack integration with channel-specific topic routing
- Mobile: Salesforce Mobile App with Agentforce tab and floating chat button
- All channels connect to the same agent and Data Cloud backend
- Security: Slack visibility controls, mobile session auth, web chat site authentication

### Phase 5: Production Readiness
- **5A Knowledge + RAG:** Salesforce Knowledge base with 5 FSI articles (margin policy, rebalancing guidelines, onboarding, risk framework, fee schedule). Einstein Knowledge Grounding for RAG.
- **5B Audit Trail:** WA_Audit_Log__c custom object with 9 fields. DC_AuditLogAction Apex class (invocable + static helper). Logs every agent interaction for SEC/FINRA compliance.
- **5C RBAC:** OWD set to Private, child objects Controlled by Parent. Permission sets: WA_Advisor, WA_Compliance_Officer, WA_Admin. CRM pre-filter before CdpQuery for Data Cloud sharing enforcement.
- **5D Performance Testing:** k6 load test scripts, Apex-level perf tests, CdpQuery latency benchmarks. SLA tiers: Internal (P95 < 8s), Client-facing (P95 < 5s), Compliance (100% audit completeness).

## MCP Connector Configuration

| Connector | API | Config File | Tools |
|-----------|-----|-------------|-------|
| Market Data | Alpha Vantage | `mcp-config/mcp-market-data.json` | 4 tools (quote, index, historical, sector) |
| Financial News | NewsAPI | `mcp-config/mcp-news-feed.json` | 3 tools (search, headlines, company) |
| Compliance Agent | Internal (Agentforce) | (Setup UI) | 1 tool (check_compliance) |

## Comparison: project-003 vs project-004

| Feature | project-003 (Data Cloud) | project-004 (Phase 1-5) |
|---------|-------------------------|------------------------|
| Topics | 6 (4 data + escalation + off-topic) | 10 (8 data + escalation + off-topic) |
| Apex Actions | 4 (DC_Client, DC_Portfolio, DC_Goal, DC_Meeting) | 8 (+DC_Rebalancing, DC_Transaction, DC_Compliance, DC_Referral) + DC_AuditLog |
| Custom Objects | 5 | 8 (+WA_Transaction, WA_Referral, WA_Audit_Log) |
| DLM Tables | 5 | 7 (+WA_Transaction, WA_Referral) |
| Seed Data | 5 HH, 10 clients, 13 accts, 10 goals, 5 meetings | Same + 52 transactions, 5 referrals |
| Test Cases | 16 | 10 (core) + Phase 5 extended |
| MCP | None | Market data, news, agent-to-agent |
| Channels | Agent Builder only | Web chat, Slack, mobile |
| Compliance | None | Audit logging, RBAC, Knowledge RAG |
| Error Handling | Basic try/catch | Enhanced: multi-fallback, user-friendly messages |
| Fuzzy Matching | Basic LIKE | Regex cleaning + name-part fallback + reverse lookup |


---

## Final Architecture (What Was Built)

```
┌─────────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                         │
│  FSI WEALTH ADVISOR AGENT — WHAT WAS BUILT                                              │
│  Project: my-agent-project-004-fsi-wealth_advisor_agent-phase1to5                       │
│  Org: orgfarm-1124a2bced-dev-ed | Git: sovikkn2015/connections-tests                    │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                              USERS                                                │  │
│  │                                                                                   │  │
│  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐                    │  │
│  │  │  Wealth Advisor  │  │  Compliance     │  │  Admin          │                    │  │
│  │  │  (WA_Advisor     │  │  (WA_Compliance │  │  (WA_Admin      │                    │  │
│  │  │   perm set)      │  │   _Officer)     │  │   perm set)     │                    │  │
│  │  │  Read clients    │  │  ViewAll + Read │  │  Full CRUD      │                    │  │
│  │  └────────┬─────────┘  └────────┬────────┘  └────────┬────────┘                    │  │
│  │           └─────────────────────┴─────────────────────┘                            │  │
│  │                                 │                                                  │  │
│  └─────────────────────────────────┼──────────────────────────────────────────────────┘  │
│                                    ▼                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                    WA_P1to5_Advisor (Agentforce Agent v1 Active)                   │  │
│  │                    12 Topics | Atlas Reasoning Engine                               │  │
│  │                                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                         TOPIC SELECTOR                                      │  │  │
│  │  └┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────┬────────────────────┘  │  │
│  │   │    │    │    │    │    │    │    │    │    │    │    │                         │  │
│  │   ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼                         │  │
│  │  CLT  PRT  GOL  MTG  RBL  TXN  CMP  REF  MKT  NWS  ESC  OFF                     │  │
│  │  LKP  REV  PLN  PRP  ART  HST  CHK  TRK  DAT  FED  ALT  TPC                     │  │
│  │   │    │    │    │    │    │    │    │    │    │    │    │                         │  │
│  └───┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼────┼─────────────────────┘  │
│      │    │    │    │    │    │    │    │    │    │    │    │                           │
│      ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼    ▼                           │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │                         APEX ACTIONS (11 classes)                                  │  │
│  │                                                                                   │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PHASE 1 — Hardened (CdpQuery → Data Cloud)                                 │  │  │
│  │  │  DC_ClientLookupAction    │ DC_PortfolioReviewAction                         │  │  │
│  │  │  DC_GoalPlanningAction    │ DC_MeetingPrepAction                             │  │  │
│  │  │  Features: fuzzy match, name-part fallback, try/catch, safeStr, audit log    │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PHASE 2 — New Topics (CdpQuery → Data Cloud)                               │  │  │
│  │  │  DC_RebalancingAction     │ DC_TransactionHistoryAction                      │  │  │
│  │  │  DC_ComplianceCheckAction │ DC_ReferralTrackingAction                        │  │  │
│  │  │  Features: drift analysis, suitability checks, summary totals, audit log     │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PHASE 3 — MCP Fallback (Http callout → External APIs)                      │  │  │
│  │  │  DC_MarketDataAction (→ Alpha Vantage)                                       │  │  │
│  │  │  DC_NewsSearchAction (→ NewsAPI)                                              │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │  PHASE 5 — Compliance                                                       │  │  │
│  │  │  DC_AuditLogAction (→ WA_Audit_Log__c)                                       │  │  │
│  │  │  Wired into all 8 data actions via logInteraction()                          │  │  │
│  │  └─────────────────────────────────────────────────────────────────────────────┘  │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│      │                              │                              │                     │
│      │ CdpQuery (8 actions)         │ Http callout (2 actions)     │ DML (audit)         │
│      ▼                              ▼                              ▼                     │
│  ┌──────────────────────┐  ┌──────────────────────┐  ┌──────────────────────────────┐  │
│  │  DATA CLOUD           │  │  EXTERNAL APIs       │  │  CRM OBJECTS                 │  │
│  │  (7 DLM tables)       │  │                      │  │                              │  │
│  │                       │  │  Alpha Vantage    ⏳  │  │  WA_Audit_Log__c          ✅ │  │
│  │  Household__dlm    ✅ │  │  (Remote Site ✅)     │  │  (9 fields, compliance)      │  │
│  │  Client__dlm       ✅ │  │  (API key needed)    │  │                              │  │
│  │  Fin_Account__dlm  ✅ │  │                      │  │  Knowledge__kav           ✅ │  │
│  │  Fin_Goal__dlm     ✅ │  │  NewsAPI         ⏳  │  │  (5 articles published)      │  │
│  │  Meeting__dlm      ✅ │  │  (Remote Site ✅)     │  │                              │  │
│  │  Transaction__dlm  ⏳ │  │  (API key needed)    │  └──────────────────────────────┘  │
│  │  Referral__dlm     ⏳ │  └──────────────────────┘                                    │
│  │  (streams created,    │                                                               │
│  │   syncing...)         │                                                               │
│  └───────────┬───────────┘                                                               │
│              │ CRM Connector (auto-sync)                                                 │
│              ▼                                                                           │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  SALESFORCE CRM (8 custom objects + seed data)                                    │  │
│  │                                                                                   │  │
│  │  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐                   │  │
│  │  │WA_Household  │────▶│ WA_Client    │────▶│WA_Fin_Account    │                   │  │
│  │  │  5 records   │ 1:N │  10 records  │ 1:N │  13 records      │                   │  │
│  │  └──────────────┘     └──────┬───────┘     └────────┬─────────┘                   │  │
│  │                              │ 1:N                  │ 1:N                         │  │
│  │                    ┌─────────┼─────────┬────────────┘                             │  │
│  │                    ▼         ▼         ▼         ▼                                │  │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                             │  │
│  │  │Fin_Goal  │ │Meeting   │ │Transact  │ │Referral  │                             │  │
│  │  │10 records│ │5 records │ │52 records│ │5 records │                             │  │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘                             │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  TESTING & QUALITY                                                                │  │
│  │                                                                                   │  │
│  │  Test Definitions:              Evaluation:                 Reproducibility:       │  │
│  │  ├─ Basic (10 cases)            ├─ LLM-as-Judge rubrics     ├─ setup.sh (13 steps)│  │
│  │  ├─ Full (32 cases)             ├─ 32 golden answers        ├─ 8 Apex scripts     │  │
│  │  └─ Phase5 (12 cases)           └─ Judge prompt template    └─ All in git         │  │
│  │                                                                                   │  │
│  │  Results: Topic 100% | Action 80% | Outcome 80%                                   │  │
│  │  (2 fails = DC streams still syncing for Transaction + Referral)                  │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  SECURITY                                                                         │  │
│  │                                                                                   │  │
│  │  Permission Sets (3):           FLS: 44 fields granted                            │  │
│  │  ├─ WA_Advisor (read)           Agent User: 11 classes granted                    │  │
│  │  ├─ WA_Compliance (viewAll)     Remote Sites: alphavantage.co + newsapi.org       │  │
│  │  └─ WA_Admin (full CRUD)        Audit: every action logged to WA_Audit_Log__c     │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
│  ┌───────────────────────────────────────────────────────────────────────────────────┐  │
│  │  DOCUMENTATION (12 files in docs/)                                                │  │
│  │                                                                                   │  │
│  │  README.md                  architecture-phase1to5.md    deployment-status.md      │  │
│  │  end-to-end-test-traces.md  llm-as-judge-evaluation.md   code-review-report.md    │  │
│  │  phase3-mcp-integration.md  phase4-deployment-channels.md                         │  │
│  │  phase5-knowledge-rag.md    phase5-rbac.md               phase5-performance.md    │  │
│  └───────────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                         │
└─────────────────────────────────────────────────────────────────────────────────────────┘
```


---

## UI/UX Deployment Plan — Wealth Advisor Workbench

### Design Decision: Salesforce-Native vs External Hosting

Project 004 is Salesforce-only (no AWS). After evaluating 4 options for hosting the UI, the decision is to use Salesforce-native deployment exclusively:

| Option | Approach | Verdict | Rationale |
|--------|----------|---------|-----------|
| Experience Cloud + Embedded Chat | Help Center site with Agentforce chat widget | ✅ Primary | Fully Salesforce-native, no external infra, built-in auth, agent just works |
| Lightning App Page + Custom LWC | Full-screen LWC in Lightning Experience | ❌ Rejected | Requires LWC rewrite, can't use Agent API streaming easily |
| Visualforce + Static Resource | React app zipped as Static Resource | ❌ Rejected | 5MB limit, cross-domain issues, fragile caching |
| Experience Cloud + Custom LWC Pages | LWR site with custom LWC page components | ❌ Rejected | High effort LWC rewrite, overkill for chat-based agent |

### Why Experience Cloud Chat Widget Is the Right UX

Unlike project 005 (Investment Research) where analysts need charts, peer comparison tables, and financial analysis panels, project 004's value is in conversational AI. The advisor asks questions and gets structured text responses from Data Cloud:

- Client 360 views → text summary with AUM, risk profile, household members
- Portfolio reviews → text with allocation percentages and YTD returns
- Goal tracking → text with progress bars described as percentages
- Meeting prep → text brief with talking points
- Compliance checks → text with pass/fail indicators
- Rebalancing alerts → text with drift analysis

A chat interface IS the workbench for this use case. The Experience Cloud Help Center template provides a professional, branded portal with the Agentforce chat widget built in.

### What's Already Deployed

| Component | Status | URL/Location |
|-----------|--------|-------------|
| Experience Cloud site "Wealth Advisor Portal" | ✅ Live | `https://orgfarm-035b70d101-dev-ed.develop.my.site.com/WAP1to5Advisor/s/` |
| CORS Whitelist | ✅ Deployed | `force-app/main/default/corsWhitelistOrigins/` |
| CSP Trusted Site | ✅ Deployed | `force-app/main/default/cspTrustedSites/` |
| Embedded Service Deployment sites | ✅ Live | ESW_WA_Chat and ESW_WA_Advisor_Chat |
| Agent (WA P1to5 Advisor) | ✅ Active | 12 topics, 8 Apex actions |

### What Needs Verification

1. AI Experiences configuration — is the agent connected to the portal site?
2. Chat widget visibility — does the floating chat button appear on the portal?
3. Branding — is the Capricorn Coffee default branding replaced with Wealth Advisor branding?
4. End-to-end test — can a user chat with the agent through the portal?

### Branding Specification

| Property | Value | Notes |
|----------|-------|-------|
| Site Name | Wealth Advisor | Header text |
| Tagline | Your AI-Powered Financial Assistant | Below site name |
| Primary Color | `#1B5E20` | Dark green — wealth management standard |
| Header Background | `#1B5E20` | Dark green |
| Header Text | `#FFFFFF` | White |
| Footer Text | © 2026 Wealth Advisor Portal — Powered by Agentforce | |

### Sample Query Categories for Portal

The portal should guide users with categorized sample queries. These map to the 10 agent topics:

| Category | Sample Queries | Agent Topic |
|----------|---------------|-------------|
| 👤 Client Lookup | "Tell me about the Johnsons", "Who is Wei Chen?" | client_lookup |
| 📊 Portfolio | "How is Wei Chen's portfolio?", "Johnson allocation" | portfolio_review |
| 🎯 Goals | "What are the Patels' goals?", "Retirement progress" | goal_planning |
| 📋 Meeting Prep | "Prep me for my meeting with Carlos" | meeting_prep |
| ⚖️ Rebalancing | "Does Sarah Johnson need rebalancing?" | rebalancing_alerts |
| 💳 Transactions | "Recent transactions for Wei Chen" | transaction_history |
| ✅ Compliance | "Is the Patel account compliant?" | compliance_check |
| 🤝 Referrals | "Who referred the Williams family?" | referral_tracking |

### React Frontend (Development/Demo Tool)

A React frontend also exists at `frontend/` for local development and demos. It connects to the same Salesforce org via OAuth2 PKCE and calls the same Apex actions. This is NOT the production deployment — it's a development tool.

```bash
cd frontend && npm install && cp .env.example .env && npm run dev
```

### Verification Checklist

- [ ] Portal URL returns 200: `https://orgfarm-035b70d101-dev-ed.develop.my.site.com/WAP1to5Advisor/s/`
- [ ] Chat widget visible (floating button, bottom right)
- [ ] Agent responds to "Tell me about the Johnsons" with Data Cloud data
- [ ] Agent responds to "How is Wei Chen's portfolio?" with allocation data
- [ ] Branding shows "Wealth Advisor" (not Capricorn Coffee)
