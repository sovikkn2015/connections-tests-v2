# FSI Wealth Advisor Agent — Phase 1-5

> **Version Note:** This project has two versions:
> - `004_V1/` — Frozen snapshot of the original implementation
> - `004_V2/` — Current version with all gaps addressed (see `docs/gap-analysis-v1-to-v2.md`)

An Agentforce agent for wealth advisors with 10 topics, 8 Apex actions, Data Cloud integration, MCP connectors, multi-channel deployment, and production-readiness features (audit logging, RBAC, RAG, performance testing).

Builds on [project-003](../my-agent-project-003-fsi-wealth_advisor_agent-datacloud/) (Data Cloud edition) with 4 new topics, 3 new custom objects, MCP integration, and compliance tooling.

## Quick Start

### Prerequisites
- Salesforce CLI (`sf`) installed
- Agentforce-enabled org with Data Cloud provisioned
- Authenticated: `sf org login web --alias my-org`

### Deploy

```bash
# 1. Deploy custom objects and Apex classes
sf project deploy start --source-dir force-app

# 2. Grant field-level security (run once after first deploy)
sf apex run --file scripts/apex/grant-fls.apex

# 3. Seed demo data (5 households, 10 clients, 13 accounts, 10 goals,
#    5 meetings, 52 transactions, 5 referrals)
sf apex run --file scripts/apex/seed-data.apex

# 4. Grant Apex class access to Einstein Agent User
sf apex run --file scripts/apex/grant-permissions.apex

# 5. Deploy the agent script
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles

# 6. Deploy test definitions
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions

# 7. Deploy CORS + CSP for Experience Cloud chat widget
#    (First update the URL in both files to match your org's site domain)
sf project deploy start --source-dir force-app/main/default/corsWhitelistOrigins
sf project deploy start --source-dir force-app/main/default/cspTrustedSites
```

### Create Data Cloud Streams (UI — one time)

1. `sf org open` → App Launcher → "Data Cloud"
2. Data Streams → New → Salesforce CRM
3. Select these 7 objects:
   - WA_Household__c
   - WA_Client__c
   - WA_Financial_Account__c
   - WA_Financial_Goal__c
   - WA_Meeting__c
   - WA_Transaction__c *(new)*
   - WA_Referral__c *(new)*
4. Deploy each stream, wait 5-10 minutes for sync

### Verify Data Cloud Sync

```bash
sf apex run --file scripts/apex/verify-data.apex
```

### Activate Agent (UI)

1. Setup → Agents → "WA P1to5 Advisor"
2. Assign EinsteinServiceAgent user → Save → Commit Version → Activate

### Test

```bash
sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --verbose
```

### How to Use the Agent

**Option 1: Agent Builder Preview (quickest — for demos and testing)**
1. `sf org open` → Setup → Agents → WA P1to5 Advisor
2. Click "Preview" (top right)
3. Type any query from the test list below

**Option 2: Wealth Advisor Portal (for end users)**
1. Create Experience Cloud site: Setup → Digital Experiences → All Sites → New → Help Center
2. Configure AI Experiences: Workspaces → AI Experiences → set Default AI Agent to "WA P1to5 Advisor"
3. Customize branding in Experience Builder (remove default template branding, add wealth advisor colors)
4. Publish the site
5. Visit: `https://<your-domain>.develop.my.site.com/<url-prefix>/s/`
6. See [docs/phase4-deployment-channels.md](docs/phase4-deployment-channels.md) for detailed step-by-step guide

**Option 4: Wealth Advisor Workbench (Visualforce — recommended for demos)**

A self-contained Visualforce page with a chat-like Q&A interface. No external dependencies.

1. Deploy the VF page and controller (included in `force-app/main/default/pages/` and `classes/WA_WorkbenchController.cls`)
2. Open: `https://<your-org>.develop.my.salesforce.com/apex/WA_Workbench`
3. Features:
   - 8 categorized sample query sections (Client Lookup, Portfolio, Goals, Meeting Prep, Rebalancing, Transactions, Compliance, Referrals)
   - Calls Apex actions directly via JavaScript Remoting — no Agent API needed
   - Dark blue header, two-panel layout (chat + help cards)
   - Works for any authenticated Salesforce user

**Option 5: React Frontend (local development)**

A React app for local development and demos. Connects to the Salesforce org via OAuth2 PKCE.

```bash
cd frontend
npm install
cp .env.example .env
# Edit .env with your Connected App values
npm run dev
# Opens http://localhost:5173
```

Features: 8 categorized sample queries, SLDS styling, Zustand store, streaming responses.

**Option 3: CLI testing**
```bash
sf agent test run --api-name WA_P1to5_Advisor_Full_Test --wait 15
```

## Test Queries (10 Topics)

### Client Lookup
- "Tell me about the Johnson household"
- "Who is Wei Chen?"
- "Look up the Patel family"
- "Tell me about James Williams"

### Portfolio Review
- "How is Sarah Johnson's portfolio performing?"
- "Show me Wei Chen's allocation"
- "What are the returns for Raj Patel?"

### Goal Planning
- "What are the Johnsons' retirement goals?"
- "How is Carlos Martinez tracking on his goals?"
- "Show me the Patels' financial goals"

### Meeting Prep
- "Prep me for my meeting with Sarah Johnson"
- "What should I know before meeting Carlos Martinez?"
- "Give me a brief for the Patel meeting"

### Rebalancing Alerts *(new)*
- "Does Sarah Johnson need rebalancing?"
- "Check rebalancing for Wei Chen"
- "Is the Martinez portfolio drifting?"

### Transaction History *(new)*
- "Show me recent transactions for Wei Chen"
- "What trades has Raj Patel made recently?"
- "Transaction history for Sarah Johnson"

### Compliance Check *(new)*
- "Is the Patel account compliant?"
- "Run a compliance check on the Martinez household"
- "Check suitability for Wei Chen"

### Referral Tracking *(new)*
- "Who referred the Williams family?"
- "What's the referral source for the Johnsons?"
- "Show me referral info for the Patels"

### Escalation
- "Transfer me to a specialist"
- "I need to speak to a human"

### Off Topic
- "What's the weather today?"
- "What's the stock price of Apple?"


## Demo Data

| Household | AUM | Risk Profile | Members | Accounts | Goals | Txns | Referral Source |
|-----------|-----|-------------|---------|----------|-------|------|-----------------|
| Johnson | $2.8M | Moderate | Sarah, Tom | 3 (IRA, 401k, Trust) | 2 | 10 | Dr. Robert Kim (Client) |
| Chen | $4.1M | Aggressive | Wei, Lin | 3 (Brokerage, Roth, 529) | 2 | 11 | TechVentures Gala (Event) |
| Martinez | $1.2M | Conservative | Carlos, Maria | 2 (IRA, 401k) | 2 | 8 | First National Bank (Partner) |
| Patel | $6.5M | Moderate | Raj, Priya | 3 (Brokerage, Trust, Roth) | 2 | 12 | Sarah Johnson (Client) |
| Williams | $890K | Growth | James, Olivia | 2 (401k, IRA) | 2 | 11 | LinkedIn Campaign (Marketing) |

**Totals:** 5 households, 10 clients, 13 accounts, 10 goals, 5 meetings, 52 transactions, 5 referrals.

## Architecture

```
User → Agent (WA_P1to5_Advisor) → Topic Selector (10 topics)
                                        │
    ┌───────┬───────┬───────┬───────┬───────┬───────┬───────┬───────┐
    ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼       │
 client  portfo  goal   meeting rebal  txn    compl  refer  escal/
 lookup  review  plan   prep    ance   hist   iance  ral    off-topic
    │       │       │       │       │       │       │       │
    ▼       ▼       ▼       ▼       ▼       ▼       ▼       ▼
 DC_*Action classes (8 Apex) → ConnectApi.CdpQuery → Data Cloud DLMs (7)
                                                          ▲
                                                    CRM Connector
                                                          │
                                                    CRM Objects (8)
                                                    + WA_Audit_Log__c
```

Full architecture diagram: [docs/architecture-phase1to5.md](docs/architecture-phase1to5.md)

## What's New vs project-003

| Feature | project-003 | project-004 (this) |
|---------|------------|-------------------|
| Topics | 6 | 10 (+rebalancing, transactions, compliance, referrals) |
| Apex Actions | 4 | 8 + DC_AuditLogAction |
| Custom Objects | 5 | 8 (+WA_Transaction__c, WA_Referral__c, WA_Audit_Log__c) |
| DLM Tables | 5 | 7 (+Transaction, Referral) |
| Seed Data | 33 records | 90+ records (+52 txns, +5 referrals) |
| MCP | None | Market data, news, agent-to-agent |
| Channels | Agent Builder only | Web chat, Slack, mobile |
| Compliance | None | Audit logging, RBAC, Knowledge RAG |
| Error Handling | Basic | Multi-fallback fuzzy matching |
| VF Workbench | — | 1 page + 1 controller (WA_Workbench, WA_WorkbenchController) |
| React Frontend | — | 1 app (10 components, SLDS-styled) — local dev only |

## Project Structure

```
force-app/main/default/
  aiAuthoringBundles/WA_P1to5_Advisor/   # Agent script (10 topics)
  aiEvaluationDefinitions/                # Test specs (10 cases)
  classes/                                # 9 Apex classes:
    DC_ClientLookupAction.cls             #   Phase 1 (hardened)
    DC_PortfolioReviewAction.cls          #   Phase 1 (hardened)
    DC_GoalPlanningAction.cls             #   Phase 1 (hardened)
    DC_MeetingPrepAction.cls              #   Phase 1 (hardened)
    DC_RebalancingAction.cls              #   Phase 2 (new)
    DC_TransactionHistoryAction.cls       #   Phase 2 (new)
    DC_ComplianceCheckAction.cls          #   Phase 2 (new)
    DC_ReferralTrackingAction.cls         #   Phase 2 (new)
    DC_AuditLogAction.cls                 #   Phase 5 (compliance)
  corsWhitelistOrigins/                   # Phase 4 (CORS for chat widget)
    WA_Portal_Site.corsWhitelistOrigin    #   Update URL for your org
  cspTrustedSites/                        # Phase 4 (CSP for portal)
    WA_Portal_Site.cspTrustedSite         #   Update URL for your org
  objects/                                # 8 custom objects:
    WA_Household__c/                      #   Original
    WA_Client__c/                         #   Original
    WA_Financial_Account__c/              #   Original (+Target_Allocation__c)
    WA_Financial_Goal__c/                 #   Original
    WA_Meeting__c/                        #   Original
    WA_Transaction__c/                    #   New (Phase 2)
    WA_Referral__c/                       #   New (Phase 2)
    WA_Audit_Log__c/                      #   New (Phase 5)
scripts/apex/
  seed-data.apex                          # Seeds all demo data
  grant-fls.apex                          # Grants FLS to System Administrator
  grant-permissions.apex                  # Grants agent user Apex class access
  verify-data.apex                        # Verifies Data Cloud sync (7 DLM tables)
mcp-config/
  mcp-market-data.json                    # Alpha Vantage MCP config (Phase 3)
  mcp-news-feed.json                      # NewsAPI MCP config (Phase 3)
docs/
  architecture-phase1to5.md               # Full architecture + data model diagrams
  phase3-mcp-integration.md               # MCP setup guide
  phase4-deployment-channels.md           # Web chat, Slack, mobile setup
  phase5-knowledge-rag.md                 # Knowledge articles + RAG setup
  phase5-rbac.md                          # Role-based access control guide
  phase5-performance-testing.md           # Load testing + SLA guide
```

## Phase Implementation Guides

| Phase | Doc | Summary |
|-------|-----|---------|
| 1 | (code) | Fuzzy matching, error handling, test expansion |
| 2 | (code) | 4 new topics + actions + objects + seed data |
| 3 | [phase3-mcp-integration.md](docs/phase3-mcp-integration.md) | Market data, news, agent-to-agent MCP |
| 4 | [phase4-deployment-channels.md](docs/phase4-deployment-channels.md) | Web chat, Slack, mobile deployment |
| 5A | [phase5-knowledge-rag.md](docs/phase5-knowledge-rag.md) | Knowledge articles + RAG grounding |
| 5B | (code) | WA_Audit_Log__c + DC_AuditLogAction |
| 5C | [phase5-rbac.md](docs/phase5-rbac.md) | OWD, sharing rules, permission sets |
| 5D | [phase5-performance-testing.md](docs/phase5-performance-testing.md) | k6 load tests, SLA tiers |

## Important Notes

- DLM object names (e.g., `WA_Household_c_Home__dlm`) may differ by org — run `verify-data.apex` after creating data streams
- All Apex classes use `with sharing` for RBAC enforcement
- The `cleanClientName()` method strips common suffixes to improve fuzzy matching
- Rebalancing uses a 5% drift threshold; compliance uses 15% drift + 80% concentration thresholds
- WA_Audit_Log__c is a CRM-only object (not synced to Data Cloud) for compliance logging
