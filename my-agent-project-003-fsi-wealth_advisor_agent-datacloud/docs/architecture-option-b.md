# WA DC Advisor - Option B Architecture (Data Cloud)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    WA DC ADVISOR - DATA CLOUD EDITION                        │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         TOPIC SELECTOR                                │  │
│  └────┬──────────┬──────────────┬──────────────┬────────┬──────────┬────┘  │
│       │          │              │              │        │          │        │
│       ▼          ▼              ▼              ▼        ▼          ▼        │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────────┐   │
│  │CLIENT  │ │PORTFO- │ │  GOAL    │ │MEETING │ │ESCAL-│ │OFF TOPIC   │   │
│  │LOOKUP  │ │LIO     │ │ PLANNING │ │ PREP   │ │ATION │ │            │   │
│  └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └──────┘ └────────────┘   │
│      │          │           │            │                                │
│      ▼          ▼           ▼            ▼                                │
│  DC_Client   DC_Portfo   DC_Goal     DC_Meeting                           │
│  Lookup      lioReview   Planning    Prep                                 │
│  Action      Action      Action      Action                               │
│  (Apex)      (Apex)      (Apex)      (Apex)                               │
│      │          │           │            │                                │
│      └──────────┴───────────┴────────────┘                                │
│                      │                                                     │
│                      ▼  ConnectApi.CdpQuery.queryAnsiSqlV2()               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    DATA CLOUD (Data 360)                               │ │
│  │                                                                       │ │
│  │  ┌──────────────────┐        ┌──────────────────┐                     │ │
│  │  │ WA_Household     │───────▶│  WA_Client       │                     │ │
│  │  │ __dlm            │  1:N   │  __dlm           │                     │ │
│  │  │                  │        │                  │                     │ │
│  │  │ name__c          │        │ name__c          │                     │ │
│  │  │ total_aum__c     │        │ email__c         │                     │ │
│  │  │ risk_profile__c  │        │ role__c          │                     │ │
│  │  │ advisor__c       │        │ household_id__c  │                     │ │
│  │  └──────────────────┘        └────────┬─────────┘                     │ │
│  │                                       │ 1:N                           │ │
│  │                          ┌────────────┼────────────┐                  │ │
│  │                          ▼            ▼            ▼                  │ │
│  │  ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐        │ │
│  │  │WA_Financial_     │ │WA_Financial_   │ │  WA_Meeting      │        │ │
│  │  │Account__dlm      │ │Goal__dlm       │ │  __dlm           │        │ │
│  │  │                  │ │                │ │                  │        │ │
│  │  │ balance__c       │ │ target_amt__c  │ │ subject__c       │        │ │
│  │  │ allocation__c    │ │ current_amt__c │ │ meeting_dt__c    │        │ │
│  │  │ ytd_return__c    │ │ target_date__c │ │ notes__c         │        │ │
│  │  └──────────────────┘ └────────────────┘ └──────────────────┘        │ │
│  │                                                                       │ │
│  │  Data synced from CRM via Salesforce CRM Connector Data Streams       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                      ▲                                                     │
│                      │  CRM Connector (auto-sync)                          │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    SALESFORCE CRM OBJECTS                              │ │
│  │  WA_Household__c, WA_Client__c, WA_Financial_Account__c,             │ │
│  │  WA_Financial_Goal__c, WA_Meeting__c                                  │ │
│  │  (seeded with 5 households, 10 clients, 13 accounts, 10 goals,       │ │
│  │   5 meetings)                                                         │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                             │
│  OPTION A vs OPTION B                                                       │
│                                                                             │
│  Option A: Agent → Apex → SOQL → WA_Household__c (CRM)                     │
│  Option B: Agent → Apex → CdpQuery → WA_Household__dlm (Data Cloud)        │
│                                                                             │
│  Same agent script, same topics, same test queries.                         │
│  Only the Apex data layer changes.                                          │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
