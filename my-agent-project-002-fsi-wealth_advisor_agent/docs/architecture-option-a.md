# Wealth Advisor Agent — Architecture (Option A: CRM Objects)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        WEALTH ADVISOR AGENT                                 │
│                        Option A: CRM Objects                                │
│                                                                             │
│  ┌───────────────────────────────────────────────────────────────────────┐  │
│  │                         TOPIC SELECTOR                                │  │
│  │            "Route advisor request to the right topic"                 │  │
│  └────┬──────────┬──────────────┬──────────────┬────────┬──────────┬────┘  │
│       │          │              │              │        │          │        │
│       ▼          ▼              ▼              ▼        ▼          ▼        │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────┐ ┌────────────┐   │
│  │CLIENT  │ │PORTFO- │ │  GOAL    │ │MEETING │ │ESCAL-│ │OFF TOPIC / │   │
│  │LOOKUP  │ │LIO     │ │ PLANNING │ │ PREP   │ │ATION │ │AMBIGUOUS   │   │
│  └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └──┬───┘ └────────────┘   │
│      │          │           │            │         │                       │
│      ▼          ▼           ▼            ▼         ▼                       │
│  ┌────────┐ ┌────────┐ ┌──────────┐ ┌────────┐ ┌──────┐                  │
│  │get_    │ │get_    │ │get_      │ │get_    │ │@utils│                  │
│  │client_ │ │portfo- │ │financial_│ │meeting_│ │.esca-│                  │
│  │360     │ │lio_    │ │goals     │ │prep    │ │late  │                  │
│  │(Apex)  │ │summary │ │(Apex)    │ │(Apex)  │ │      │                  │
│  │        │ │(Apex)  │ │          │ │        │ │      │                  │
│  └───┬────┘ └───┬────┘ └────┬─────┘ └───┬────┘ └──────┘                  │
│      │          │           │            │                                │
│      └──────────┴───────────┴────────────┘                                │
│                      │                                                     │
│                      ▼  SOQL                                               │
│  ┌───────────────────────────────────────────────────────────────────────┐ │
│  │                    SALESFORCE CRM OBJECTS                              │ │
│  │                                                                       │ │
│  │  ┌──────────────────┐        ┌──────────────────┐                     │ │
│  │  │ WA_Household__c  │───────▶│  WA_Client__c    │                     │ │
│  │  │                  │  1:N   │                  │                     │ │
│  │  │ • Name           │        │ • Name           │                     │ │
│  │  │ • Total_AUM__c   │        │ • Email__c       │                     │ │
│  │  │ • Advisor__c     │        │ • Phone__c       │                     │ │
│  │  │ • Risk_Profile__c│        │ • Role__c        │                     │ │
│  │  └──────────────────┘        └────────┬─────────┘                     │ │
│  │                                       │ 1:N                           │ │
│  │                          ┌────────────┼────────────┐                  │ │
│  │                          ▼            ▼            ▼                  │ │
│  │  ┌──────────────────┐ ┌────────────────┐ ┌──────────────────┐        │ │
│  │  │WA_Financial_     │ │WA_Financial_   │ │  WA_Meeting__c   │        │ │
│  │  │Account__c        │ │Goal__c         │ │                  │        │ │
│  │  │                  │ │                │ │ • Subject__c     │        │ │
│  │  │ • Type__c        │ │ • Name         │ │ • Date_Time__c   │        │ │
│  │  │ • Balance__c     │ │ • Target__c    │ │ • Location__c    │        │ │
│  │  │ • Allocation__c  │ │ • Current__c   │ │ • Notes__c       │        │ │
│  │  │ • YTD_Return__c  │ │ • Target_Date__c│ │ • Action_Items__c│        │ │
│  │  └──────────────────┘ └────────────────┘ └──────────────────┘        │ │
│  │                                                                       │ │
│  └───────────────────────────────────────────────────────────────────────┘ │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                             │
│  SEED DATA (5 Households)                                                   │
│                                                                             │
│  ┌──────────────┬──────────┬───────────┬──────────────────────────────┐    │
│  │ Household    │ AUM      │ Risk      │ Members                      │    │
│  ├──────────────┼──────────┼───────────┼──────────────────────────────┤    │
│  │ Johnson      │ $2.8M    │ Moderate  │ Sarah (primary), Tom          │    │
│  │ Chen         │ $4.1M    │ Aggressive│ Wei (primary), Lin            │    │
│  │ Martinez     │ $1.2M    │ Conserv.  │ Carlos (primary), Maria       │    │
│  │ Patel        │ $6.5M    │ Moderate  │ Raj (primary), Priya          │    │
│  │ Williams     │ $890K    │ Growth    │ James (primary), Olivia       │    │
│  └──────────────┴──────────┴───────────┴──────────────────────────────┘    │
│                                                                             │
│  ═══════════════════════════════════════════════════════════════════════    │
│                                                                             │
│  TEST CASES                                                                 │
│                                                                             │
│  "Tell me about the Johnsons"         → client_lookup   → get_client_360   │
│  "How is Wei Chen's portfolio?"       → portfolio_review → get_portfolio..  │
│  "What are the Patels' goals?"        → goal_planning   → get_fin_goals    │
│  "Prep me for my meeting with Carlos" → meeting_prep    → get_meeting_prep │
│  "Transfer me to compliance"          → escalation      → escalate         │
│  "What's the stock price of Apple?"   → off_topic       → (redirect)       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```
