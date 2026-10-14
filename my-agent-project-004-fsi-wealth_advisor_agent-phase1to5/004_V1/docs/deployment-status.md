# Deployment Status — WA P1to5 Advisor

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                DEPLOYED TO ORG: orgfarm-1124a2bced-dev-ed                        │
│                USER: sovikn.0627f403e6bb@agentforce.com                          │
│                API: v66.0 | STATUS: ✅ Live                                      │
│                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│  AGENT: WA_P1to5_Advisor ✅                                                      │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                         TOPIC SELECTOR (10 topics)                        │  │
│  └──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘  │
│     │      │      │      │      │      │      │      │      │      │           │
│     ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼           │
│  ┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌──────┐┌────┐┌────┐ │
│  │CLIENT││PORT- ││GOAL  ││MEET- ││REBAL-││TRANS-││COMPL-││REFER-││ESC-││OFF │ │
│  │LOOK- ││FOLIO ││PLAN- ││ING   ││ANCING││ACTION││IANCE ││RAL   ││ALA-││TOP-│ │
│  │UP    ││REVIEW││NING  ││PREP  ││ALERTS││HIST. ││CHECK ││TRACK ││TION││IC  │ │
│  │  ✅  ││  ✅  ││  ✅  ││  ✅  ││  ✅  ││  ✅  ││  ✅  ││  ✅  ││ ✅ ││ ✅ │ │
│  └──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└──┬───┘└────┘└────┘ │
│     │       │       │       │       │       │       │       │                  │
│     ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    APEX CLASSES (9 deployed) ✅                          │   │
│  │                                                                         │   │
│  │  HARDENED (Phase 1):              NEW (Phase 2):                        │   │
│  │  ├─ DC_ClientLookupAction    ✅   ├─ DC_RebalancingAction          ✅  │   │
│  │  ├─ DC_PortfolioReviewAction ✅   ├─ DC_TransactionHistoryAction   ✅  │   │
│  │  ├─ DC_GoalPlanningAction    ✅   ├─ DC_ComplianceCheckAction      ✅  │   │
│  │  └─ DC_MeetingPrepAction     ✅   └─ DC_ReferralTrackingAction     ✅  │   │
│  │                                                                         │   │
│  │  COMPLIANCE (Phase 5):                                                  │   │
│  │  └─ DC_AuditLogAction        ✅                                        │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼  ConnectApi.CdpQuery.queryAnsiSqlV2()            │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │                    CUSTOM OBJECTS (8 deployed) ✅                        │   │
│  │                                                                         │   │
│  │  EXISTING (updated):                NEW (created):                      │   │
│  │  ├─ WA_Household__c          ✅     ├─ WA_Transaction__c          ✅   │   │
│  │  ├─ WA_Client__c             ✅     │   (7 fields: Client, Account,    │   │
│  │  ├─ WA_Financial_Account__c  ✅     │    Type, Amount, Date,           │   │
│  │  │   (+Target_Allocation__c) ✅     │    Symbol, Description)          │   │
│  │  ├─ WA_Financial_Goal__c     ✅     ├─ WA_Referral__c             ✅   │   │
│  │  └─ WA_Meeting__c            ✅     │   (6 fields: Client, Source,     │   │
│  │                                     │    Source_Type, Date,             │   │
│  │                                     │    Status, Value)                 │   │
│  │                                     └─ WA_Audit_Log__c            ✅   │   │
│  │                                        (9 fields: Agent_Name, User,    │   │
│  │                                         Topic, Action, Query,          │   │
│  │                                         Response_Summary,              │   │
│  │                                         Client_Accessed,               │   │
│  │                                         Timestamp, Session_Id)         │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│  SCRIPTS EXECUTED ✅                                                             │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  grant-fls.apex          → 23 new field permissions granted       ✅   │   │
│  │  seed-data.apex          → 5 HH, 10 clients, 13 accts, 10 goals, ✅   │   │
│  │                            5 meetings, 52 txns, 5 referrals            │   │
│  │  grant-permissions.apex  → 5 new Apex class grants to Agent User  ✅   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  SEED DATA ✅                                                                    │
│  ┌──────────────┬──────────┬───────────┬─────┬──────┬──────┬──────┬─────────┐  │
│  │ Household    │ AUM      │ Risk      │ Mbr │ Acct │ Goal │ Txns │ Referral│  │
│  ├──────────────┼──────────┼───────────┼─────┼──────┼──────┼──────┼─────────┤  │
│  │ Johnson      │ $2.8M    │ Moderate  │  2  │  3   │  2   │  10  │ Client  │  │
│  │ Chen         │ $4.1M    │ Aggressive│  2  │  3   │  2   │  11  │ Event   │  │
│  │ Martinez     │ $1.2M    │ Conserv.  │  2  │  2   │  2   │   8  │ Partner │  │
│  │ Patel        │ $6.5M    │ Moderate  │  2  │  3   │  2   │  12  │ Client  │  │
│  │ Williams     │ $890K    │ Growth    │  2  │  2   │  2   │  11  │ Mktg    │  │
│  ├──────────────┼──────────┼───────────┼─────┼──────┼──────┼──────┼─────────┤  │
│  │ TOTAL        │ $15.49M  │           │ 10  │  13  │  10  │  52  │    5    │  │
│  └──────────────┴──────────┴───────────┴─────┴──────┴──────┴──────┴─────────┘  │
│                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│  PENDING (requires UI)                                                          │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  ⏳ Activate agent: Setup → Agents → WA P1to5 Advisor                  │   │
│  │     → Assign user → Save → Commit Version → Activate                   │   │
│  │  ⏳ Deploy test definitions (after agent has a BotVersion)              │   │
│  │  ⏳ Create Data Cloud streams for WA_Transaction__c + WA_Referral__c   │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```


---

## Roadmap vs Implementation Status

Legend: ✅ Deployed to org | 📄 Doc/config created (needs UI steps) | ⏳ Blocked on UI step | ❌ Not started

| Phase | Feature | Status | What Was Built | What's Pending |
|-------|---------|--------|----------------|----------------|
| **1** | Fuzzy matching improvements | ✅ Done | `cleanClientName()` with expanded regex + name-part fallback + reverse household lookup in all 8 DC_* classes | — |
| **1** | Multi-turn conversations | 📄 Doc only | Documented in test traces | Live testing after agent activation |
| **1** | Error handling | ✅ Done | All CdpQuery calls wrapped in try/catch, `safeStr()` null-safe helper, user-friendly messages (no stack traces) | — |
| **1** | Expand test coverage to 30+ | ✅ Done | 54 test cases across 3 test definitions (10 + 32 + 12) | Deploy test XMLs after agent has a BotVersion (UI step) |
| **1** | Org cleanup (delete orphaned agents) | ⏳ Pending | — | Manual UI: delete v2, v3, v4, v5 agents from Setup |
| **2** | Rebalancing Alerts | ✅ Deployed | `DC_RebalancingAction.cls` + agent topic `rebalancing_alerts` + target allocations per risk profile + 5% drift threshold | — |
| **2** | Transaction History | ✅ Deployed | `DC_TransactionHistoryAction.cls` + `WA_Transaction__c` object (7 fields) + 52 seed transactions + agent topic `transaction_history` | Create Data Cloud stream for WA_Transaction__c |
| **2** | Compliance Check | ✅ Deployed | `DC_ComplianceCheckAction.cls` + agent topic `compliance_check` + suitability/concentration/drift checks | — |
| **2** | Referral Tracking | ✅ Deployed | `DC_ReferralTrackingAction.cls` + `WA_Referral__c` object (6 fields) + 5 seed referrals + agent topic `referral_tracking` | Create Data Cloud stream for WA_Referral__c |
| **3** | External Market Data (MCP) | 📄 Doc only | `docs/phase3-mcp-integration.md` + `mcp-config/mcp-market-data.json` + sample Apex fallback class + agent topic definition | Register MCP connector in org, get Alpha Vantage API key |
| **3** | News Feed (MCP) | 📄 Doc only | `docs/phase3-mcp-integration.md` + `mcp-config/mcp-news-feed.json` + agent topic definition | Register MCP connector in org, get NewsAPI key |
| **3** | Agent-to-Agent (MCP) | 📄 Doc only | Architecture diagram + Compliance Agent script + MCP config in docs | Build and deploy WA_Compliance_Agent, register MCP bridge |
| **4** | Web Chat (Experience Cloud) | ✅ Partial | Experience Cloud site created ("Wealth Advisor Portal"), CORS + CSP deployed, internal user login enabled, step-by-step branding guide | Customize branding in Experience Builder (UI), configure AI Experiences (UI), publish site |
| **4** | Slack Integration | 📄 Doc only | `docs/phase4-deployment-channels.md` — Slack app config, channel routing, example interactions | Install Salesforce for Slack, enable Agentforce for Slack (UI) |
| **4** | Mobile (SF Mobile App) | 📄 Doc only | `docs/phase4-deployment-channels.md` — mobile nav config, push notifications guide | Enable Agentforce in mobile settings (UI) |
| **5A** | Knowledge Articles + RAG | 📄 Doc only | `docs/phase5-knowledge-rag.md` — 5 FSI articles (margin policy, rebalancing guidelines, onboarding, risk framework, fee schedule) + RAG config + `knowledge_base` topic definition | Enable Salesforce Knowledge, import articles, configure Einstein Knowledge Grounding (UI) |
| **5B** | Audit Trail + Compliance Logging | ✅ Deployed | `WA_Audit_Log__c` object (9 fields) + `DC_AuditLogAction.cls` (invocable + static helper) — deployed to org | Wire audit logging into each DC_* action call |
| **5C** | Role-Based Access (RBAC) | 📄 Doc only | `docs/phase5-rbac.md` — OWD config, 3 permission sets (Advisor/Compliance/Admin), CRM pre-filter pattern for Data Cloud sharing | Set OWD to Private, create permission sets, assign to users (UI) |
| **5D** | Performance Testing | 📄 Doc only | `docs/phase5-performance-testing.md` — k6 load test script, Apex perf test scripts, SLA tiers, monitoring dashboards | Run actual load tests against live agent |
| **5** | LLM-as-Judge Evaluation | 📄 Doc only | `docs/llm-as-judge-evaluation.md` — 6 rubrics, 32 golden answers, judge prompt template, batch eval script, improved bot_response_rating strings | Run evaluation against live agent responses |
| **—** | Agent Activation | ⏳ Pending | Agent script deployed to org | Assign user → Save → Commit Version → Activate (UI) |
| **—** | Test Definitions Deploy | ⏳ Pending | 3 XML files ready locally | Deploy after agent has a BotVersion |
| **6** | Prompt Templates | ❌ Not started | — | Future: `my-agent-project-005-*` |
| **6** | Calculated Insights (Data Cloud) | ❌ Not started | — | Future |
| **6** | Proactive Alerts | ❌ Not started | — | Future |
| **6** | Multi-Language Support | ❌ Not started | — | Future |


---

## Architecture: What's Deployed

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                    LIVE IN ORG: orgfarm-1124a2bced-dev-ed                        │
│                                                                                 │
│  AGENT: WA_P1to5_Advisor (Version 1 — Active)                                   │
│  ┌───────────────────────────────────────────────────────────────────────────┐  │
│  │                         TOPIC SELECTOR (10 topics)                        │  │
│  └──┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬────────┘  │
│     ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼           │
│  client  portfo  goal   meet   rebal  txn    compl  refer  escal  off           │
│  lookup  review  plan   prep   ance   hist   iance  ral    ation  topic         │
│    ✅      ✅     ✅     ✅     ✅     ✅     ✅     ✅     ✅     ✅            │
│     │       │       │       │       │       │       │       │                   │
│     ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼                   │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  APEX CLASSES (11 deployed)                                             │   │
│  │                                                                         │   │
│  │  Phase 1 (hardened):          Phase 2 (new):         Phase 3 (MCP):     │   │
│  │  DC_ClientLookupAction   ✅   DC_RebalancingAction ✅  DC_MarketData  ✅│   │
│  │  DC_PortfolioReviewAction✅   DC_TransactionHistory✅  DC_NewsSearch  ✅│   │
│  │  DC_GoalPlanningAction   ✅   DC_ComplianceCheck   ✅                   │   │
│  │  DC_MeetingPrepAction    ✅   DC_ReferralTracking  ✅  Phase 5:         │   │
│  │                                                        DC_AuditLog    ✅│   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                              │                                                  │
│                              ▼                                                  │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  CUSTOM OBJECTS (8)                                                     │   │
│  │                                                                         │   │
│  │  WA_Household__c ✅    WA_Transaction__c ✅ (NEW)                       │   │
│  │  WA_Client__c    ✅    WA_Referral__c    ✅ (NEW)                       │   │
│  │  WA_Financial_Account__c ✅ (+Target_Allocation__c)                     │   │
│  │  WA_Financial_Goal__c ✅   WA_Audit_Log__c ✅ (NEW, 9 fields)          │   │
│  │  WA_Meeting__c   ✅                                                     │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  SECURITY & PERMISSIONS                                                 │   │
│  │                                                                         │   │
│  │  Permission Sets:                  Remote Site Settings:                 │   │
│  │  WA_Advisor              ✅        Alpha_Vantage (alphavantage.co)  ✅  │   │
│  │  WA_Compliance_Officer   ✅        News_API (newsapi.org)           ✅  │   │
│  │  WA_Admin                ✅                                             │   │
│  │                                    FLS: 44 fields granted           ✅  │   │
│  │  Agent User Class Access:          Agent User: 11 classes granted   ✅  │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
│  ┌─────────────────────────────────────────────────────────────────────────┐   │
│  │  TEST DEFINITIONS (3)              SEED DATA                            │   │
│  │                                                                         │   │
│  │  WA_P1to5_Advisor_Test      ✅     5 households         ✅             │   │
│  │  WA_P1to5_Advisor_Full_Test ✅     10 clients           ✅             │   │
│  │  WA_Advisor_Phase5_Test     ✅     13 accounts          ✅             │   │
│  │                                    10 goals             ✅             │   │
│  │  54 test cases total               5 meetings           ✅             │   │
│  │  Topic: 100% | Outcome: 80%       52 transactions      ✅             │   │
│  │                                    5 referrals          ✅             │   │
│  │                                    5 knowledge articles ✅ (drafts)    │   │
│  └─────────────────────────────────────────────────────────────────────────┘   │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

---

## Roadmap Status: Deployed vs Pending

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│                                                                                 │
│  PHASE 1: HARDENING                                                             │
│  ┌──────────────────────────────────┬──────────────────────────────────────┐    │
│  │ ✅ DEPLOYED                      │ ⏳ PENDING                           │    │
│  │                                  │                                      │    │
│  │ Fuzzy matching (regex +          │ Delete orphaned agents               │    │
│  │   name-part fallback)            │   v2, v3, v4, v5 (UI)               │    │
│  │ Error handling (try/catch,       │                                      │    │
│  │   safeStr, user-friendly msgs)   │                                      │    │
│  │ 54 test cases (3 test defs)      │                                      │    │
│  └──────────────────────────────────┴──────────────────────────────────────┘    │
│                                                                                 │
│  PHASE 2: NEW TOPICS                                                            │
│  ┌──────────────────────────────────┬──────────────────────────────────────┐    │
│  │ ✅ DEPLOYED                      │ ⏳ PENDING                           │    │
│  │                                  │                                      │    │
│  │ DC_RebalancingAction       ✅    │ Data Cloud stream:                   │    │
│  │ DC_TransactionHistoryAction✅    │   WA_Transaction__c (UI)             │    │
│  │ DC_ComplianceCheckAction   ✅    │   WA_Referral__c (UI)                │    │
│  │ DC_ReferralTrackingAction  ✅    │                                      │    │
│  │ WA_Transaction__c object   ✅    │ (Txn + Referral topics fail          │    │
│  │ WA_Referral__c object      ✅    │  until streams are created)          │    │
│  │ 52 transactions seeded     ✅    │                                      │    │
│  │ 5 referrals seeded         ✅    │                                      │    │
│  └──────────────────────────────────┴──────────────────────────────────────┘    │
│                                                                                 │
│  PHASE 3: MCP INTEGRATION                                                       │
│  ┌──────────────────────────────────┬──────────────────────────────────────┐    │
│  │ ✅ DEPLOYED                      │ ⏳ PENDING                           │    │
│  │                                  │                                      │    │
│  │ DC_MarketDataAction        ✅    │ Set API keys in Named Creds (UI)     │    │
│  │ DC_NewsSearchAction        ✅    │   Alpha Vantage: get key             │    │
│  │ Remote Site: alphavantage  ✅    │   NewsAPI: get key                   │    │
│  │ Remote Site: newsapi       ✅    │ Add market_data + market_news        │    │
│  │ MCP config JSONs           ✅    │   topics to agent script             │    │
│  │ Implementation guide       ✅    │ Agent-to-Agent orchestration         │    │
│  └──────────────────────────────────┴──────────────────────────────────────┘    │
│                                                                                 │
│  PHASE 4: DEPLOYMENT CHANNELS                                                   │
│  ┌──────────────────────────────────┬──────────────────────────────────────┐    │
│  │ ✅ DEPLOYED                      │ ⏳ PENDING                           │    │
│  │                                  │                                      │    │
│  │ Step-by-step guides        ✅    │ Customize branding in Exp Builder    │    │
│  │   (web chat, Slack, mobile)      │   (remove Capricorn Coffee)     (UI) │    │
│  │ Experience Cloud site       ✅   │ Configure AI Experiences        (UI) │    │
│  │   "Wealth Advisor Portal"        │   (set Default AI Agent)             │    │
│  │ CORS whitelist              ✅   │ Publish site                    (UI) │    │
│  │ CSP Trusted Site            ✅   │ Install Salesforce for Slack    (UI) │    │
│  │ Internal user login         ✅   │ Enable Agentforce in mobile     (UI) │    │
│  │ Network name + description  ✅   │                                      │    │
│  └──────────────────────────────────┴──────────────────────────────────────┘    │
│                                                                                 │
│  PHASE 5: PRODUCTION READINESS                                                  │
│  ┌──────────────────────────────────┬──────────────────────────────────────┐    │
│  │ ✅ DEPLOYED                      │ ⏳ PENDING                           │    │
│  │                                  │                                      │    │
│  │ 5A Knowledge:                    │ 5A: Publish 5 draft articles (UI)    │    │
│  │   5 articles created (drafts)✅  │     Configure Einstein Knowledge     │    │
│  │                                  │     Grounding on agent (UI)          │    │
│  │ 5B Audit Trail:                  │                                      │    │
│  │   WA_Audit_Log__c object    ✅   │ 5B: Wire audit calls into each      │    │
│  │   DC_AuditLogAction         ✅   │     DC_* action (code change)        │    │
│  │                                  │                                      │    │
│  │ 5C RBAC:                         │ 5C: Set OWD to Private (UI)          │    │
│  │   WA_Advisor perm set       ✅   │     Create sharing rules (UI)        │    │
│  │   WA_Compliance_Officer     ✅   │     Assign perm sets to users (UI)   │    │
│  │   WA_Admin perm set         ✅   │                                      │    │
│  │                                  │ 5D: Run perf tests against           │    │
│  │ 5D Performance:                  │     live agent                        │    │
│  │   k6 scripts + guides      ✅   │                                      │    │
│  │                                  │ LLM-as-Judge: Run eval against       │    │
│  │ LLM-as-Judge:                    │   live agent responses               │    │
│  │   32 golden answers         ✅   │                                      │    │
│  │   Judge prompt template     ✅   │                                      │    │
│  └──────────────────────────────────┴──────────────────────────────────────┘    │
│                                                                                 │
│  PHASE 6: ADVANCED AI                                                           │
│  ┌──────────────────────────────────┬──────────────────────────────────────┐    │
│  │ ✅ DEPLOYED                      │ ❌ NOT STARTED                       │    │
│  │                                  │                                      │    │
│  │ (nothing)                        │ Prompt Templates                     │    │
│  │                                  │ Calculated Insights (Data Cloud)     │    │
│  │                                  │ Proactive Alerts (Platform Events)   │    │
│  │                                  │ Multi-Language Support               │    │
│  └──────────────────────────────────┴──────────────────────────────────────┘    │
│                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════     │
│  TOTALS                                                                         │
│                                                                                 │
│  Apex Classes:     11 deployed    │  Objects:     8 deployed                    │
│  Permission Sets:   3 deployed    │  Seed Data:  90+ records                    │
│  Remote Sites:      2 deployed    │  Test Cases: 54 across 3 defs              │
│  Knowledge:         5 drafts      │  Test Pass:  Topic 100%, Outcome 80%       │
│  Agent:             Active v1     │  Docs:       12 markdown files             │
│                                                                                 │
│  Phase 1: 90% done  │  Phase 4: Guides only (100% UI)                          │
│  Phase 2: 85% done  │  Phase 5: 70% done                                       │
│  Phase 3: 60% done  │  Phase 6: 0% (future)                                    │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```


---

## Pending Items

| # | Pending Item | Phase | Why It's Pending | Impact | How to Fix |
|---|-------------|-------|-----------------|--------|------------|
| 1 | Data Cloud stream: WA_Transaction__c | 2 | UI-only — Data Cloud streams can't be created via CLI/metadata | Transaction History topic fails (3 test cases) | Data Cloud → Data Streams → New → select WA_Transaction__c |
| 2 | Data Cloud stream: WA_Referral__c | 2 | UI-only — same as above | Referral Tracking topic fails (3 test cases) | Data Cloud → Data Streams → New → select WA_Referral__c |
| 3 | Delete orphaned agents (v2-v5) | 1 | UI-only — agent deletion not available via CLI | Org clutter, no functional impact | Setup → Agents → delete old versions |
| 4 | API key: Alpha Vantage | 3 | Need to register at alphavantage.co and set key in Named Credential | DC_MarketDataAction will fail on callout | Setup → Named Credentials → Alpha_Vantage → set apikey |
| 5 | API key: NewsAPI | 3 | Need to register at newsapi.org and set key in Named Credential | DC_NewsSearchAction will fail on callout | Setup → Named Credentials → News_API → set apiKey |
| 6 | Add market_data + market_news topics to agent | 3 | Agent needs new version with 2 additional topics wired to the new Apex classes | Market/news queries not routed | Update .agent file, deploy, commit new version |
| 7 | Publish 5 Knowledge articles | 5A | Articles created as drafts, publishing failed (KbManagement API ID issue) | Knowledge search won't find them | Knowledge tab → select each article → Publish |
| 8 | Configure Einstein Knowledge Grounding | 5A | UI-only — grounding source config on agent | Agent won't search Knowledge for policy questions | Setup → Agents → WA P1to5 → Grounding Sources → add Knowledge |
| 9 | Wire audit logging into DC_* actions | 5B | Code change — each action needs to call DC_AuditLogAction after returning results | No compliance trail of agent interactions | Add `DC_AuditLogAction.logInteraction(...)` call to each class |
| 10 | Set OWD to Private | 5C | Intentionally skipped — would break agent tests in dev org | No record-level security | Do when going to production (Setup → Sharing Settings) |
| 11 | Create sharing rules | 5C | Depends on OWD being Private first | Advisors can see all clients | Setup → Sharing Settings → New Rule |
| 12 | Assign permission sets to users | 5C | No advisor/compliance users exist yet in dev org | Permission sets deployed but unassigned | Setup → Permission Sets → assign to users |
| 13 | Experience Cloud branding + AI Experiences | 4 | Site created, CORS deployed. Branding customization and AI agent connection require Experience Builder UI | Chat widget not yet connected to agent | Follow guide in `docs/phase4-deployment-channels.md` Steps 2-4 |
| 14 | Slack integration | 4 | 100% UI — requires Slack workspace admin | No Slack channel | Follow guide in `docs/phase4-deployment-channels.md` |
| 15 | Mobile app config | 4 | 100% UI — Setup toggle | No mobile access | Follow guide in `docs/phase4-deployment-channels.md` |
| 16 | Run performance tests | 5D | Needs live agent + k6 installed | No baseline metrics | Run scripts from `docs/phase5-performance-testing.md` |
| 17 | Run LLM-as-Judge evaluation | 5 | Needs LLM API key (OpenAI/Anthropic) + live responses | No quality scores | Run eval script from `docs/llm-as-judge-evaluation.md` |
| 18 | Phase 6: Prompt Templates | 6 | Not started | — | Future project |
| 19 | Phase 6: Calculated Insights | 6 | Not started | — | Future project |
| 20 | Phase 6: Proactive Alerts | 6 | Not started | — | Future project |
| 21 | Phase 6: Multi-Language | 6 | Not started | — | Future project |

Items 1-2 are the blockers for 100% test pass rate. Everything else is production-readiness or future work.

---

## Test Results (32-Query Full Run) — With Actual Agent Responses

| # | Query | Topic | Action | Data Returned | Outcome | Agent Response |
|---|-------|-------|--------|---------------|:-------:|----------------|
| 1 | Tell me about the Johnson household | client_lookup ✅ | get_client_360 ✅ | Johnson Family, $2.8M AUM, Moderate risk | ✅ | Johnson Family household has $2.8M AUM, moderate risk profile. Advisor: Alex Morgan. Members: Sarah Johnson (Primary), Tom Johnson (Spouse). Accounts: Johnson Family Trust $1.5M, Johnson IRA $450K, Johnson 401k $820K. |
| 2 | Tell me about the Chen family | client_lookup ✅ | get_client_360 ✅ | Chen Family, $4.1M AUM, Aggressive risk | ✅ | Chen Family household has $4.1M AUM, aggressive risk profile. Members: Wei Chen (Primary), Lin Chen (Spouse). Accounts: Chen Brokerage $2.2M, Chen Roth IRA $850K, Chen 529 Plan $1.05M. |
| 3 | Tell me about the Martinez household | client_lookup ✅ | get_client_360 ✅ | Martinez Family, $1.2M AUM, Conservative | ✅ | Martinez Family household has $1.2M AUM, conservative risk profile. Members: Carlos Martinez (Primary), Maria Martinez (Spouse). Accounts: Martinez IRA $680K, Martinez 401k $520K. |
| 4 | Tell me about the Patel family | client_lookup ✅ | get_client_360 ✅ | Patel Family, $6.5M AUM, Moderate risk | ✅ | Patel Family household has $6.5M AUM, moderate risk profile. Members: Raj Patel (Primary), Priya Patel (Spouse). Accounts: Patel Brokerage $3.2M, Patel Trust $2.1M, Patel Roth IRA $1.2M. |
| 5 | Tell me about the Williams family | client_lookup ✅ | get_client_360 ✅ | Williams Family, $890K AUM, Growth risk | ✅ | Williams Family household has $890K AUM, growth risk profile. Members: James Williams (Primary), Olivia Williams (Spouse). Accounts: Williams 401k $520K, Williams IRA $370K. |
| 6 | How is Wei Chen's portfolio? | portfolio_review ✅ | get_portfolio_summary ✅ | Chen Brokerage $2.2M, Chen Roth IRA $850K | ✅ | Wei Chen's portfolio is valued at $3.0M with aggressive risk profile. Chen Brokerage: $2.2M, 80% Equity/15% Fixed/5% Cash, YTD 12.3%. Chen Roth IRA: $850K, 75% Equity/20% Fixed/5% Cash, YTD 11.1%. |
| 7 | How is Raj Patel's portfolio performing? | portfolio_review ✅ | get_portfolio_summary ✅ | Patel Brokerage $3.2M, Patel Trust $2.1M | ✅ | Raj Patel's portfolio is valued at $5.3M with moderate risk profile. Patel Brokerage: $3.2M, 65/25/10, YTD 9.7%. Patel Trust: $2.1M, 55/35/10, YTD 6.9%. |
| 8 | Show me James Williams portfolio | portfolio_review ✅ | get_portfolio_summary ✅ | Williams 401k $520K | ✅ | James Williams portfolio: $520K. Williams 401k: 70% Equity/20% Fixed/10% Cash, YTD 10.2%. |
| 9 | What are the Johnsons' retirement goals? | goal_planning ✅ | get_financial_goals ✅ | Retirement $2.8M/$3M, College Fund $145K/$200K | ✅ | Johnson Family goals: Retirement — target $3M, current $2.8M, 93.3% progress, gap $200K, target 2035. College Fund Emma — target $200K, current $145K, 72.5% progress, gap $55K, target 2030. |
| 10 | What are the Patels' goals? | goal_planning ✅ | get_financial_goals ✅ | Retirement $6.5M/$8M, Philanthropy $650K/$1M | ✅ | Patel Family goals: Retirement — target $8M, current $6.5M, 81.2% progress, gap $1.5M, target 2033. Philanthropy Fund — target $1M, current $650K, 65.0% progress, gap $350K, target 2030. |
| 11 | What goals does Carlos Martinez have? | goal_planning ✅ | get_financial_goals ✅ | Retirement $1.2M/$1.5M, Vacation Home $120K/$350K | ✅ | Carlos Martinez goals: Retirement — target $1.5M, current $1.2M, 80% progress, gap $300K, target 2038. Vacation Home — target $350K, current $120K, 34.3% progress, gap $230K, target 2029. |
| 12 | Prep me for my meeting with Sarah Johnson | meeting_prep ✅ | get_meeting_prep ✅ | Annual Portfolio Review, Conf Room A | ✅ | Meeting brief: Sarah Johnson, Johnson Family, $2.8M AUM, Moderate. Meeting: Annual Portfolio Review, Conference Room A. Portfolio: Johnson IRA $450K (7.2%), Johnson Family Trust $1.53M (5.8%). Goals: Retirement 93%, College Fund 73%. Talking points provided. |
| 13 | Prep me for my meeting with Carlos | meeting_prep ✅ | get_meeting_prep ✅ | Retirement Planning Check-in, Conf Room B | ✅ | Meeting brief: Carlos Martinez, Martinez Family, $1.2M AUM, Conservative. Meeting: Retirement Planning Check-in, 2026-04-03, Conference Room B. Notes: Carlos wants to move retirement earlier. Portfolio: Martinez IRA $680K (4.1%). Goals: Vacation Home 34%, Retirement 80%. |
| 14 | Prepare my meeting with Raj Patel | meeting_prep ✅ | get_meeting_prep ✅ | Estate Planning Discussion, Client Home | ✅ | Meeting brief: Raj Patel, Patel Family, $6.5M AUM, Moderate. Meeting: Estate Planning Discussion, Client Home. Notes: philanthropy fund + estate plan. Portfolio: Patel Brokerage $3.2M (9.7%), Patel Trust $2.1M (6.9%). Goals: Retirement 81%, Philanthropy 65%. |
| 15 | Does Sarah Johnson need rebalancing? | rebalancing_alerts ✅ | check_rebalancing ✅ | Moderate target 55/35/10, IRA 60/30/10, Trust 50/40/10 | ✅ | Sarah Johnson does not need rebalancing. All accounts within tolerance. Johnson IRA: drift at threshold (5%), Johnson Family Trust: drift at threshold (5%). No action needed. |
| 16 | Check rebalancing for Wei Chen | rebalancing_alerts ✅ | check_rebalancing ✅ | Aggressive target 80/15/5, Brokerage 80/15/5, Roth 75/20/5 | ✅ | Wei Chen does not need rebalancing. Chen Brokerage matches target exactly. Chen Roth IRA drifts within tolerance. All accounts within >5% threshold. |
| 17 | Does the Martinez account need rebalancing? | rebalancing_alerts ✅ | check_rebalancing ✅ | Conservative target 30/60/10, IRA 40/50/10 | ✅ | Martinez account does not need rebalancing. All accounts within tolerance, no asset class drifting more than 5% from target. |
| 18 | Show me recent transactions for Sarah Johnson | transaction_history ✅ | get_transactions ✅ | (no data — DLM missing) | ❌ | "I was unable to retrieve Sarah Johnson's transaction history. Please verify the client name or try again." — DLM table WA_Transaction_c_Home__dlm not found. |
| 19 | What are Wei Chen's latest transactions? | transaction_history ✅ | get_transactions ✅ | (no data — DLM missing) | ❌ | "I was unable to retrieve Wei Chen's transaction history. Please verify the client name or try again." — DLM table missing. |
| 20 | Show me Raj Patel's transaction history | transaction_history ✅ | get_transactions ✅ | (no data — DLM missing) | ❌ | "I was unable to retrieve Raj Patel's transaction history. Please verify the client name or try again." — DLM table missing. |
| 21 | Is the Patel account compliant? | compliance_check ✅ | run_compliance ✅ | 3 accounts all pass suitability + concentration + drift | ✅ | Patel account is compliant. All accounts meet target allocations: Patel Roth IRA 60/30/10 ✓, Patel Brokerage 65/25/10 ✓, Patel Trust 55/35/10 ✓. Status: PASS. |
| 22 | Run a compliance check on the Martinez household | compliance_check ✅ | run_compliance ✅ | 2 accounts, Conservative 30/60/10 target | ✅ | Martinez household compliant. Conservative risk (target 30/60/10). IRA: 40/50/10 ✓, 401k: 35/55/10 ✓. All accounts compliant. |
| 23 | Check compliance for Wei Chen | compliance_check ✅ | run_compliance ✅ | 3 accounts, Aggressive 80/15/5 target | ✅ | Wei Chen (Chen Family) compliant. Aggressive risk (target 80/15/5). Brokerage: 80/15/5 ✓, Roth IRA: 75/20/5 ✓, 529 Plan: 65/30/5 ✓. Status: PASS. |
| 24 | Who referred the Williams family? | referral_tracking ✅ | get_referrals ✅ | (no data — DLM missing) | ❌ | "I was unable to retrieve referral information for the Williams family." — DLM table WA_Referral_c_Home__dlm not found. |
| 25 | Who referred the Johnsons? | referral_tracking ✅ | get_referrals ✅ | (no data — DLM missing) | ❌ | "I was unable to retrieve referral information for the Johnsons." — DLM table missing. |
| 26 | What's the referral source for the Patels? | referral_tracking ✅ | get_referrals ✅ | (no data — DLM missing) | ❌ | "I was unable to retrieve referral information for the Patels." — DLM table missing. |
| 27 | Transfer me to a specialist | escalation ✅ | @utils.escalate | N/A | ✅ | "I will transfer you to a specialist for further assistance. Is there anything specific you would like the specialist to help you with?" |
| 28 | I need to speak to a human | escalation ✅ | @utils.escalate | N/A | ✅ | "I will connect you with a human advisor. Is there anything specific you would like them to assist you with?" |
| 29 | What is the weather today? | off_topic ✅ | (none — redirect) | N/A | ✅ | "I am here to assist with wealth advisory topics such as client portfolios, financial goals, meetings, and related services. How can I help you with your wealth management needs today?" |
| 30 | What's the stock price of Apple? | off_topic ✅ | (none — redirect) | N/A | ✅ | "I am unable to provide stock prices. How can I assist you with wealth management, portfolio reviews, goal planning, or other advisory services?" |
| 31 | Tell me about the Johnsons (plural) | client_lookup ✅ | get_client_360 ✅ | Johnson Family (fuzzy match: "Johnsons" → "Johnson") | ✅ | Same as #1 — Johnson Family $2.8M, Moderate, Sarah+Tom, 3 accounts. Fuzzy matching stripped trailing 's'. |
| 32 | How is Carlos doing on his goals? (first name) | goal_planning ✅ | get_financial_goals ✅ | Carlos Martinez (fuzzy match: "Carlos" → "Carlo") | ✅ | Carlos has two goals: Vacation Home — $120K/$350K, 34.3% progress, gap $230K, target June 2029. Retirement — $1.2M/$1.5M, 80% progress, gap $300K, target January 2038. |

Topic: 100% (32/32) | Action: 87.5% | Outcome: 81.25% | Duration: 4m 12s

6 failures = Transaction History (3) + Referral Tracking (3) — pending Data Cloud streams for WA_Transaction__c and WA_Referral__c.


---

## Project-004 Full Architecture

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                                                                                     │
│  PROJECT-004: FSI WEALTH ADVISOR AGENT — PHASE 1-5                                  │
│  Org: orgfarm-1124a2bced-dev-ed | Agent: WA_P1to5_Advisor v1 (Active)               │
│  Git: github.com/sovikkn2015/connections-tests                                      │
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                                                                               │  │
│  │   DEPLOYMENT CHANNELS (Phase 4 — pending UI)                                  │  │
│  │   ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                        │  │
│  │   │  Web Chat     │  │    Slack     │  │   Mobile     │                        │  │
│  │   │  (Exp Cloud)  │  │  (SF4Slack)  │  │  (SF App)    │                        │  │
│  │   │   ⏳ pending  │  │  ⏳ pending  │  │  ⏳ pending  │                        │  │
│  │   └──────┬───────┘  └──────┬───────┘  └──────┬───────┘                        │  │
│  │          └──────────────────┴──────────────────┘                               │  │
│  │                             │                                                  │  │
│  │                             ▼                                                  │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│                                                                                     │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                    WA_P1to5_Advisor (Agentforce Agent)                         │  │
│  │                                                                               │  │
│  │  ┌─────────────────────────────────────────────────────────────────────────┐  │  │
│  │  │                      TOPIC SELECTOR (10 topics)                         │  │  │
│  │  └──┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬─────┬──────────────┘  │  │
│  │     │     │     │     │     │     │     │     │     │     │                   │  │
│  │     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼     ▼                   │  │
│  │  ┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐┌─────┐    │  │
│  │  │CLNT ││PORT ││GOAL ││MEET ││REBL ││TXN  ││CMPL ││REFR ││ESCL ││OFF  │    │  │
│  │  │LOOK ││REVW ││PLAN ││PREP ││ALRT ││HIST ││CHCK ││TRCK ││TION ││TOPC │    │  │
│  │  │ ✅  ││ ✅  ││ ✅  ││ ✅  ││ ✅  ││ ✅  ││ ✅  ││ ✅  ││ ✅  ││ ✅  │    │  │
│  │  └──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└──┬──┘└─────┘└─────┘    │  │
│  │     │      │      │      │      │      │      │      │                       │  │
│  └─────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼───────────────────────┘  │
│        │      │      │      │      │      │      │                                  │
│        ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼                           │
│  ┌───────────────────────────────────────────────────────────────────────────────┐  │
│  │                    APEX CLASSES (11 deployed to org)                           │  │
│  │                                                                               │  │
│  │  Phase 1 (Hardened)         Phase 2 (New)            Phase 3 (MCP Fallback)   │  │
│  │  ┌────────────────────┐    ┌────────────────────┐   ┌────────────────────┐    │  │
│  │  │DC_ClientLookup   ✅│    │DC_Rebalancing    ✅│   │DC_MarketData     ✅│    │  │
│  │  │DC_PortfolioReview✅│    │DC_TransactionHist✅│   │DC_NewsSearch     ✅│    │  │
│  │  │DC_GoalPlanning   ✅│    │DC_ComplianceCheck✅│   └────────────────────┘    │  │
│  │  │DC_MeetingPrep    ✅│    │DC_ReferralTrack  ✅│   Phase 5 (Compliance)      │  │
│  │  └────────────────────┘    └────────────────────┘   ┌────────────────────┐    │  │
│  │                                                      │DC_AuditLog       ✅│    │  │
│  │  All classes: with sharing, cleanClientName(),        └────────────────────┘    │  │
│  │  safeStr(), formatCurrency(), try/catch                                        │  │
│  └───────────────────────────────────────────────────────────────────────────────┘  │
│        │                                    │                    │                   │
│        │ CdpQuery                           │ Http callout       │ DML insert        │
│        ▼                                    ▼                    ▼                   │
│  ┌──────────────────────────┐  ┌──────────────────────┐  ┌──────────────────────┐  │
│  │  DATA CLOUD (7 DLMs)     │  │  EXTERNAL APIs       │  │  CRM OBJECTS         │  │
│  │                          │  │                      │  │                      │  │
│  │  WA_Household__dlm    ✅ │  │  Alpha Vantage   ⏳  │  │  WA_Audit_Log__c  ✅ │  │
│  │  WA_Client__dlm       ✅ │  │  (market data)       │  │  (compliance log)    │  │
│  │  WA_Fin_Account__dlm  ✅ │  │  Remote Site ✅      │  │                      │  │
│  │  WA_Fin_Goal__dlm     ✅ │  │  Named Cred  ⏳ key  │  │  Knowledge__kav   ⚠️ │  │
│  │  WA_Meeting__dlm      ✅ │  │                      │  │  (5 drafts, need     │  │
│  │  WA_Transaction__dlm  ⏳ │  │  NewsAPI         ⏳  │  │   publishing)        │  │
│  │  WA_Referral__dlm     ⏳ │  │  (financial news)    │  │                      │  │
│  │                          │  │  Remote Site ✅      │  └──────────────────────┘  │
│  │  ⏳ = needs DC stream    │  │  Named Cred  ⏳ key  │                             │
│  └──────────────────────────┘  └──────────────────────┘                             │
│        ▲                                                                            │
│        │ CRM Connector (auto-sync)                                                  │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  SALESFORCE CRM OBJECTS (8 deployed)                                         │   │
│  │                                                                              │   │
│  │  ┌──────────────┐     ┌──────────────┐     ┌──────────────────┐              │   │
│  │  │WA_Household  │────▶│ WA_Client    │────▶│WA_Fin_Account    │              │   │
│  │  │__c        ✅ │ 1:N │ __c       ✅ │ 1:N │__c            ✅ │              │   │
│  │  └──────────────┘     └──────┬───────┘     └────────┬─────────┘              │   │
│  │                              │ 1:N                  │ 1:N                    │   │
│  │                    ┌─────────┼─────────┬────────────┘                        │   │
│  │                    ▼         ▼         ▼         ▼                           │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │   │
│  │  │WA_Fin_   │ │WA_Meet   │ │WA_Trans  │ │WA_Refer  │                        │   │
│  │  │Goal__c ✅│ │ing__c ✅ │ │action  ✅│ │ral__c ✅ │                        │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘                        │   │
│  │                                                                              │   │
│  │  SEED DATA: 5 HH | 10 clients | 13 accts | 10 goals | 5 meetings            │   │
│  │             52 transactions | 5 referrals                                    │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  SECURITY & TESTING                                                          │   │
│  │                                                                              │   │
│  │  Permission Sets (3):          Tests (54 cases):        FLS & Grants:        │   │
│  │  ┌──────────────────┐          ┌──────────────────┐     ┌────────────────┐   │   │
│  │  │WA_Advisor      ✅│          │Basic (10)      ✅│     │44 fields    ✅ │   │   │
│  │  │WA_Compliance   ✅│          │Full (32)       ✅│     │11 classes   ✅ │   │   │
│  │  │WA_Admin        ✅│          │Phase5 (12)     ✅│     │Agent User   ✅ │   │   │
│  │  └──────────────────┘          └──────────────────┘     └────────────────┘   │   │
│  │                                                                              │   │
│  │  Results: Topic 100% | Action 87.5% | Outcome 81.25%                         │   │
│  │  (6 fails = Transaction + Referral — pending DC streams)                     │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
│  ┌──────────────────────────────────────────────────────────────────────────────┐   │
│  │  DOCUMENTATION (12 files)                                                    │   │
│  │                                                                              │   │
│  │  README.md                    architecture-phase1to5.md                       │   │
│  │  deployment-status.md         end-to-end-test-traces.md                      │   │
│  │  llm-as-judge-evaluation.md   code-review-report.md                          │   │
│  │  phase3-mcp-integration.md    phase4-deployment-channels.md                  │   │
│  │  phase5-knowledge-rag.md      phase5-rbac.md                                 │   │
│  │  phase5-performance-testing.md                                               │   │
│  └──────────────────────────────────────────────────────────────────────────────┘   │
│                                                                                     │
└─────────────────────────────────────────────────────────────────────────────────────┘
```


---

## Multi-Turn Conversation Tests

The `sf agent test run` CLI only supports single-turn queries (one utterance per test case). Multi-turn conversations must be tested in the Agent Builder Preview chat UI, where the Atlas reasoning engine maintains session context across turns.

### Flow 1: Client Deep-Dive (Johnson)

| Turn | Query | Expected Topic | Tests |
|------|-------|---------------|-------|
| 1 | "Tell me about the Johnsons" | client_lookup | Initial lookup |
| 2 | "How is Sarah's portfolio doing?" | portfolio_review | Resolves "Sarah" from context → Sarah Johnson |
| 3 | "Does she need rebalancing?" | rebalancing_alerts | Resolves "she" → Sarah Johnson |
| 4 | "Prep me for my meeting with her" | meeting_prep | Resolves "her" → Sarah Johnson |

### Flow 2: Cross-Topic Comparison (Patel → Chen)

| Turn | Query | Expected Topic | Tests |
|------|-------|---------------|-------|
| 1 | "Who are the Patels?" | client_lookup | Initial lookup |
| 2 | "Are they compliant?" | compliance_check | Resolves "they" → Patel household |
| 3 | "What about their goals?" | goal_planning | Resolves "their" → Patel household |
| 4 | "Now check the Chen family" | client_lookup | Topic switch to new client |

### Flow 3: Advisor Workflow (Martinez)

| Turn | Query | Expected Topic | Tests |
|------|-------|---------------|-------|
| 1 | "I have a meeting with Carlos Martinez tomorrow" | meeting_prep | Meeting prep with context |
| 2 | "What are his goals?" | goal_planning | Resolves "his" → Carlos Martinez |
| 3 | "Does he need rebalancing?" | rebalancing_alerts | Resolves "he" → Carlos Martinez |
| 4 | "Transfer me to compliance" | escalation | Escalation from mid-conversation |

### Flow 4: Ambiguous → Resolution (Patel)

| Turn | Query | Expected Topic | Tests |
|------|-------|---------------|-------|
| 1 | "Tell me about Raj" | client_lookup | First-name-only fuzzy match |
| 2 | "How is his portfolio?" | portfolio_review | Resolves "his" → Raj Patel |
| 3 | "Compare that to the Williams family" | client_lookup | Topic switch, new client |

### How to Test

1. Open the org: `sf org open`
2. Go to Setup → Agents → WA P1to5 Advisor
3. Click "Preview" (top right)
4. Type each turn sequentially in the chat
5. Verify the agent resolves pronouns ("she", "his", "they") from prior context


---

## Live Data Test Results (Tavily API — March 31, 2026)

Run: `sf apex run --file scripts/apex/test-live-data.apex`

| # | Test | Action Class | Query | Result | Live Response |
|---|------|-------------|-------|:------:|---------------|
| 1 | Market Data | DC_MarketDataAction | S&P 500 today | ✅ | S&P 500 at 6,343.73, up 0.36% (March 31, 2026) |
| 2 | Market Data | DC_MarketDataAction | Apple AAPL stock price | ✅ | AAPL at $246.63, down $2.17 (0.87%) |
| 3 | News Search | DC_NewsSearchAction | Tesla | ✅ | Tesla Q1 2026 challenges, profitability concerns, competition |
| 4 | News Search | DC_NewsSearchAction | Federal Reserve interest rates | ✅ | Fed held rates at 3.50%-3.75%, uncertainty about future cuts |

4/4 passed. Powered by Tavily Search API (api.tavily.com). API key masked in git as `YOUR_TAVILY_API_KEY`.


---

# Reproducibility Deployment — New Org (orgfarm-035b70d101-dev-ed)

```
┌─────────────────────────────────────────────────────────────────────────────────┐
│          REPRODUCED ON ORG: orgfarm-035b70d101-dev-ed                            │
│          DATE: 2026-04-03                                                        │
│          API: v66.0 | STATUS: ✅ Live                                            │
│                                                                                 │
│  Method: Full CLI deployment from git to a fresh Agentforce Developer Edition    │
│  Source: github.com/sovikkn2015/connections-tests                                │
│                                                                                 │
│  ═══════════════════════════════════════════════════════════════════════════════  │
│                                                                                 │
│  WHAT WAS DEPLOYED (programmatic — no UI)                                        │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  Custom Objects:     8 (5 existing + 3 new)                        ✅  │     │
│  │  Apex Classes:      11 (4 hardened + 4 new + 2 MCP + 1 audit)      ✅  │     │
│  │  Permission Sets:    3 (Advisor, Compliance, Admin)                 ✅  │     │
│  │  Remote Sites:       3 (Alpha Vantage, NewsAPI, Tavily)             ✅  │     │
│  │  Agent Bundle:       WA_P1to5_Advisor                               ✅  │     │
│  │  Test Definitions:   3 (10 + 32 + 12 = 54 cases)                   ✅  │     │
│  │  FLS:               44 fields granted                               ✅  │     │
│  │  Agent User Access: 11 Apex classes granted                         ✅  │     │
│  │  Perm Set Assign:    3 sets → current user                          ✅  │     │
│  │  Seed Data:         90+ records (5 HH, 10 clients, 13 accts,       ✅  │     │
│  │                      10 goals, 5 meetings, 52 txns, 5 referrals)        │     │
│  │  Data Cloud:         7 DLO streams + 7 DMO mappings                ✅  │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
│  WHAT REQUIRED UI                                                                │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  Data Cloud streams:  Created via UI (category selection required)      │     │
│  │  DMO mappings:        Created via Connect REST API (setup-dmo-mappings) │     │
│  │  Agent activation:    Auto-created when agent bundle deployed           │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
│  WHAT'S STILL PENDING                                                            │
│  ┌─────────────────────────────────────────────────────────────────────────┐     │
│  │  Knowledge articles:  Knowledge not enabled in org (UI: Setup toggle)   │     │
│  │  Einstein Grounding:  UI only (Setup → Agents → Grounding Sources)      │     │
│  │  OWD Private:         Skipped (would break agent in dev org)            │     │
│  │  External Creds:      AuthQueryParameter type not supported in org      │     │
│  │  API keys:            Alpha Vantage / NewsAPI / Tavily (optional)       │     │
│  │  Phase 4 channels:    Web Chat, Slack, Mobile (100% UI)                 │     │
│  └─────────────────────────────────────────────────────────────────────────┘     │
│                                                                                 │
└─────────────────────────────────────────────────────────────────────────────────┘
```

## Test Results (32-Query Full Run) — New Org

Run: `sf agent test run --api-name WA_P1to5_Advisor_Full_Test --wait 15`
Duration: 4m 13s

| # | Query | Topic | Action | Outcome | Agent Response (key data) |
|---|-------|:-----:|:------:|:-------:|--------------------------|
| 1 | Tell me about the Johnson household | ✅ | ✅ | ✅ | Johnson Family $2.8M, Moderate, Sarah+Tom, 3 accounts |
| 2 | Tell me about the Chen family | ✅ | ✅ | ✅ | Chen Family $4.1M, Aggressive, Wei+Lin, 3 accounts |
| 3 | Tell me about the Martinez household | ✅ | ✅ | ✅ | Martinez Family $1.2M, Conservative, Carlos+Maria, 2 accounts |
| 4 | Tell me about the Patel family | ✅ | ✅ | ✅ | Patel Family $6.5M, Moderate, Raj+Priya, 3 accounts |
| 5 | Tell me about the Williams family | ✅ | ✅ | ✅ | Williams Family $890K, Growth, James+Olivia, 2 accounts |
| 6 | How is Wei Chen's portfolio? | ✅ | ✅ | ✅ | $3.0M, Brokerage $2.2M (12.3%), Roth $850K (11.1%) |
| 7 | How is Raj Patel's portfolio performing? | ✅ | ✅ | ✅ | $5.3M, Brokerage $3.2M (9.7%), Trust $2.1M (6.9%) |
| 8 | Show me James Williams portfolio | ✅ | ✅ | ✅ | $520K, 401k 70/20/10, YTD 10.2% |
| 9 | What are the Johnsons' retirement goals? | ✅ | ✅ | ✅ | Retirement 93.3%, College Fund 72.5% |
| 10 | What are the Patels' goals? | ✅ | ✅ | ✅ | Retirement 81.2%, Philanthropy 65.0% |
| 11 | What goals does Carlos Martinez have? | ✅ | ✅ | ✅ | Retirement 80%, Vacation Home 34.3% |
| 12 | Prep me for my meeting with Sarah Johnson | ✅ | ✅ | ✅ | Annual Portfolio Review, Conf Room A, goals+portfolio |
| 13 | Prep me for my meeting with Carlos | ✅ | ✅ | ✅ | Retirement Planning Check-in, Conf Room B |
| 14 | Prepare my meeting with Raj Patel | ✅ | ✅ | ✅ | Estate Planning Discussion, Client Home |
| 15 | Does Sarah Johnson need rebalancing? | ✅ | ✅ | ✅ | No rebalancing needed, within tolerance |
| 16 | Check rebalancing for Wei Chen | ✅ | ✅ | ✅ | No rebalancing needed, matches target |
| 17 | Does the Martinez account need rebalancing? | ✅ | ✅ | ✅ | No rebalancing needed |
| 18 | Show me recent transactions for Sarah Johnson | ✅ | ✅ | ✅ | Buy VTI $25K, Sell BND $15K, Buy AAPL $50K... |
| 19 | What are Wei Chen's latest transactions? | ✅ | ✅ | ✅ | Buy NVDA $100K, Buy QQQ $35K, Buy TSLA $75K... |
| 20 | Show me Raj Patel's transaction history | ✅ | ✅ | ✅ | Buy VTI $200K, Sell AAPL $150K, Buy MSFT $100K... |
| 21 | Is the Patel account compliant? | ✅ | ✅ | ✅ | All accounts compliant, PASS |
| 22 | Run a compliance check on the Martinez household | ✅ | ✅ | ✅ | Conservative 30/60/10, all PASS |
| 23 | Check compliance for Wei Chen | ✅ | ✅ | ✅ | Aggressive 80/15/5, all 3 accounts compliant |
| 24 | Who referred the Williams family? | ✅ | ✅ | ✅ | LinkedIn Campaign Q4, Marketing, $1.2M |
| 25 | Who referred the Johnsons? | ✅ | ✅ | ✅ | Dr. Robert Kim, Client, Converted, $2.8M |
| 26 | What's the referral source for the Patels? | ✅ | ✅ | ✅ | Sarah Johnson, Client, Converted, $6.5M |
| 27 | Transfer me to a specialist | ✅ | — | ✅ | Transferred to specialist |
| 28 | I need to speak to a human | ✅ | — | ✅ | Connected to human advisor |
| 29 | What is the weather today? | ✅ | — | ✅ | Redirected to wealth advisory topics |
| 30 | What's the stock price of Apple? | ❌ | — | ✅ | Routed to market_data (not off_topic) |
| 31 | Tell me about the Johnsons (plural) | ✅ | ✅ | ✅ | Fuzzy match: "Johnsons" → Johnson Family |
| 32 | How is Carlos doing on his goals? (first name) | ✅ | ✅ | ✅ | First-name match: Carlos → Martinez goals |

**Topic: 96.88% (31/32) | Action: 87.50% (28/32) | Outcome: 100% (32/32)**

## Comparison: Original Org vs New Org

| Metric | Original Org (1124a2bced) | New Org (035b70d101) | Delta |
|--------|--------------------------|----------------------|-------|
| Topic Pass | 100% (32/32) | 96.88% (31/32) | -1 (Q30 market_data vs off_topic) |
| Action Pass | 87.50% (28/32) | 87.50% (28/32) | Same |
| Outcome Pass | 81.25% (26/32) | **100% (32/32)** | **+6** |
| Duration | 4m 12s | 4m 13s | Same |
| Transaction queries (Q18-20) | ❌ 3 fails (no DC stream) | ✅ 3 pass | **Fixed** |
| Referral queries (Q24-26) | ❌ 3 fails (no DC stream) | ✅ 3 pass | **Fixed** |
| Knowledge articles | 5 drafts | Not enabled | Blocked (UI) |
| Remote site settings | 2 deployed | 3 deployed (+Tavily) | +1 |
| Permission set assignments | Not assigned | 3 assigned | **New** |

Key improvement: Outcome went from 81.25% → 100% because Data Cloud streams for Transaction and Referral objects are now properly set up with DMO mappings via the Connect REST API (`setup-dmo-mappings.py`).

## Reproducible Setup Commands (for a fresh org)

```bash
cd my-agent-project-004-fsi-wealth_advisor_agent-phase1to5

# 1. Deploy metadata
sf project deploy start --source-dir force-app/main/default/objects --wait 20
sf project deploy start --source-dir force-app/main/default/classes --wait 20
sf project deploy start --source-dir force-app/main/default/permissionsets --wait 20
sf project deploy start --source-dir force-app/main/default/remoteSiteSettings --wait 20

# 2. Grant access + seed data
sf apex run --file scripts/apex/grant-fls.apex
sf apex run --file scripts/apex/seed-data.apex
sf apex run --file scripts/apex/grant-permissions.apex
sf apex run --file scripts/apex/assign-permission-sets.apex

# 3. Deploy agent + tests
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20

# 4. Data Cloud setup (after creating streams in UI)
python3 scripts/setup-dmo-mappings.py [org-alias]

# 5. Verify + test
sf apex run --file scripts/apex/verify-data.apex
sf agent test run --api-name WA_P1to5_Advisor_Full_Test --wait 15
```
