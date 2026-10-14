# Agentforce FSI Wealth Advisor — Roadmap

## Current State

Three working agents deployed and tested:

| Agent | Project | Data Layer | Topics | Actions | Tests |
|-------|---------|------------|--------|---------|-------|
| Hello World | my-agent-project | N/A (demo) | 4 (Greeting, Escalation, Off-Topic, Ambiguous) | 1 Apex (HelloAction) | 2 cases, Topic 100%, Outcome 100% |
| WA Advisor v6 | my-agent-project-002 | SOQL → CRM Objects | 6 (Client Lookup, Portfolio Review, Goal Planning, Meeting Prep, Escalation, Off-Topic) | 4 Apex | 6 cases, Topic 100%, Action 67%, Outcome 100% |
| WA DC Advisor | my-agent-project-003 | CdpQuery → Data Cloud DLMs | 6 (same as v6) | 4 Apex (DC_*) | 16 cases, Topic 100%, Action 87.5%, Outcome 87.5% |

Demo data: 5 households ($890K–$6.5M AUM), 10 clients, 13 accounts, 10 goals, 5 meetings.
Architecture pattern: identical agent scripts, pluggable data layer (SOQL vs ConnectApi.CdpQuery).
All code on git: sovikkn2015/connections-tests.

---

```
PHASE 1: HARDENING (Current → 1 week)
──────────────────────────────────────

□ Fuzzy matching improvements
  "James Williams", "Carlos Martinez", "Johnsons" fail on some queries.
  → Improve regex stripping + add SOSL search fallback for CRM version.
  → Validate DLM LIKE queries handle edge cases in Data Cloud version.

□ Multi-turn conversation support
  Test and document the two-turn flow where agent asks for
  clarification then calls the action on the second turn.

□ Error handling
  Wrap all CdpQuery calls with proper try/catch.
  Return user-friendly messages instead of stack traces.
  Handle null DLM fields gracefully.

□ Expand test coverage → 30+ queries
  Partial names, misspellings, empty results, special characters.
  Add full-household coverage for all 5 families across all 4 topics.
  (WA_DC_Advisor_Full_Test already has 16 — extend to 30+.)

□ Org cleanup
  Delete orphaned agents: v2, v3, v4, v5, Wealth_Advisor_Agent,
  FSI_Wealth_Advisor. Keep only WA Advisor v6 + WA DC Advisor.


PHASE 2: NEW TOPICS + ACTIONS (1–2 weeks)
──────────────────────────────────────

□ Rebalancing Alerts — new topic + action
  "Does Sarah Johnson need rebalancing?"
  → Compare current allocation vs target allocation per account
  → Flag accounts that drifted >5% from target
  → Build for both CRM (SOQL) and Data Cloud (CdpQuery) versions

□ Transaction History — new topic + action
  "Show me recent transactions for Wei Chen"
  → New WA_Transaction__c object (buy/sell/dividend/fee)
  → Seed 50+ transactions across clients
  → New Data Cloud data stream for WA_Transaction__c

□ Compliance Check — new topic + action
  "Is the Patel account compliant?"
  → Check suitability rules (risk profile vs actual allocation)
  → Flag violations (e.g., aggressive allocation for conservative client)
  → Return pass/fail with specific violations

□ Referral Tracking — new topic + action
  "Who referred the Williams family?"
  → New WA_Referral__c object (source, date, status, value)
  → Track referral pipeline and conversion


PHASE 3: MCP INTEGRATION (2–3 weeks)
──────────────────────────────────────

□ External Market Data via MCP
  "What's the S&P 500 doing today?"
  → MCP connector to a market data API (Alpha Vantage / Yahoo Finance)
  → Agent answers market questions alongside client data
  → Contextual: "How does Wei Chen's portfolio compare to the S&P?"

□ News Feed via MCP
  "Any news about Apple stock?"
  → MCP connector to a financial news API
  → Cross-reference with portfolio holdings

□ Agent-to-Agent via MCP
  → Wealth Advisor agent calls a Compliance agent
  → Multi-agent orchestration demo
  → Compliance agent validates suitability before advisor acts


PHASE 4: DEPLOYMENT CHANNELS (3–4 weeks)
──────────────────────────────────────

□ Web Chat (Enhanced Messaging)
  → Deploy agent to a public-facing web chat widget
  → Experience Cloud site with embedded messaging
  → Client-facing portal for self-service queries

□ Slack Integration
  → Deploy agent to a Slack channel
  → Advisors query client data from Slack
  → "Hey @WealthAdvisor, prep me for my 2pm with Raj Patel"

□ Mobile (Salesforce Mobile App)
  → Agent accessible from the Salesforce mobile app
  → On-the-go meeting prep and client lookups


PHASE 5: PRODUCTION READINESS (4–6 weeks)
──────────────────────────────────────

□ Identity Resolution (Data Cloud)
  → Unified client profiles across multiple data sources
  → Merge duplicate client records from different systems
  → Single golden record per client

□ Knowledge Articles + RAG
  → New topic for policy/procedure questions
  → "What's our firm's policy on margin accounts?"
  → Knowledge base with FSI-specific articles grounded via RAG

□ Audit Trail + Compliance Logging
  → Log every agent interaction to a custom object
  → Track what data was accessed, by whom, when
  → Required for SEC/FINRA compliance in production

□ Role-Based Access
  → Different advisors see only their clients
  → Agent respects sharing rules and FLS
  → Test with multiple advisor profiles

□ Performance Testing
  → Load test with 100+ concurrent users
  → Measure response times, action latency, CdpQuery throughput
  → Establish SLAs for agent response time


PHASE 6: ADVANCED AI (6–8 weeks)
──────────────────────────────────────

□ Prompt Templates
  → Reusable templates for common advisor tasks
  → "Generate a quarterly review email for the Johnsons"
  → Grounded in CRM data via merge fields

□ Calculated Insights (Data Cloud)
  → Pre-computed metrics: AUM growth rate, client engagement score
  → "Which clients are at risk of leaving?"
  → Churn prediction based on interaction frequency + portfolio performance

□ Proactive Alerts
  → Agent initiates conversations based on triggers
  → "Raj Patel's portfolio dropped 10% this week"
  → Platform Events → Agent notification → Advisor outreach

□ Multi-Language Support
  → Spanish, French, Mandarin
  → Serve global wealth management teams
  → Locale-aware currency and date formatting
```

---

## Architecture Reference

```
Option A (CRM):        Agent → Apex → SOQL → WA_*__c (CRM Objects)
Option B (Data Cloud): Agent → Apex → CdpQuery → WA_*__dlm (Data Cloud DMOs)

Both share: same agent script, same topics, same test queries.
Only the Apex data layer changes.
```

## Key Technical Decisions

- Agent script pattern: `set @variables.result = @outputs.xxx` with conditional `if @variables.result:` in instructions
- Fuzzy matching: strip suffixes (household, family, the, s) + LIKE queries
- Einstein Agent User requires explicit Apex class access + object/field permissions (granted via scripts)
- Data Cloud DLM object names vary by org — verify with `verify-data.apex` after stream creation
