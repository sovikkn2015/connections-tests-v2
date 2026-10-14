# Reproducibility Deployment Log

Target Org: `<your-org>.develop.my.salesforce.com`
Username: `<your-username>@agentforce.com`
Org ID: `<your-org-id>`
Date: 2026-04-03

---

## Project 1: my-agent-project (Hello World Agent)

### What Worked (CLI deploy)
- ✅ `HelloAction.cls` — deployed via `sf project deploy start --source-dir force-app/main/default/classes --wait 20`
- ✅ `Hello_World_Agent.agent` + `.bundle-meta.xml` — deployed via `sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20`
- ✅ Apex test: `HelloAction.getGreeting("Sam")` → "Hello Sam! Welcome! I'm your Hello World agent. How can I help you today?"

### What Failed / Required Fixing
- ❌ `GenAiPlannerBundle` — internal Salesforce error. Not portable cross-org.
- ❌ `Bot` + `BotVersion` — "Required fields are missing: [PlannerId]"
- ❌ `AiEvaluationDefinition` — "BotVersion not found"

### Root Cause
`bots/` and `genAiPlannerBundles/` are org-specific. Not deployable cross-org via metadata API.

### Reproducible Deploy Order
```bash
cd my-agent-project
sf project deploy start --source-dir force-app/main/default/classes --wait 20
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20
# MANUAL: Setup → Agents → Hello World Agent → New Version → Commit → Activate
# THEN: sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20
```

---

## Project 2: my-agent-project-002-fsi-wealth_advisor_agent (WA CRM)

### What Worked (CLI deploy) — ALL FIRST TRY ✅
- ✅ 5 custom objects + 21 fields (26 components)
- ✅ 4 Apex classes (ClientLookupAction, PortfolioReviewAction, GoalPlanningAction, MeetingPrepAction)
- ✅ FLS granted for 21 fields
- ✅ Seed data: 5 households, 10 clients, 13 accounts, 10 goals, 5 meetings
- ✅ Agent bundle (WA_Advisor_v2)

### What Failed / Required Fixing
- Nothing. All CLI deploys succeeded first try.

### Test Verification — All 4 Actions Passed ✅
```
1. ClientLookupAction("Johnson") → Johnson Family | $2.8M | Moderate | 2 members, 3 accounts ✅
2. PortfolioReviewAction("Wei Chen") → Chen Family | Aggressive | $3.0M | 11.97% YTD ✅
3. GoalPlanningAction("Patel") → 2 goals: Philanthropy 65%, Retirement 81.2% ✅
4. MeetingPrepAction("Carlos") → Martinez Family | $1.2M | Meeting April 6 | 2 goals ✅
```

### Reproducible Deploy Order
```bash
cd my-agent-project-002-fsi-wealth_advisor_agent
sf project deploy start --source-dir force-app/main/default/objects --wait 20
sf project deploy start --source-dir force-app/main/default/classes --wait 20
sf apex run --file scripts/apex/grant-fls.apex
sf apex run --file scripts/apex/seed-data.apex
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles/WA_Advisor_v2 --wait 20
# MANUAL: Setup → Agents → WA Advisor v2 → Assign user → New Version → Commit → Activate
# THEN: sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20
```

---

## Project 3: my-agent-project-003-fsi-wealth_advisor_agent-datacloud (WA Data Cloud)

### What Worked (CLI deploy) — ALL FIRST TRY ✅
- ✅ Custom objects already deployed from Project 2 (shared)
- ✅ 4 DC_* Apex classes (DC_ClientLookupAction, DC_PortfolioReviewAction, DC_GoalPlanningAction, DC_MeetingPrepAction)
- ✅ Apex class access granted to Einstein Agent User (4 classes)
- ✅ Agent bundle (WA_DC_Advisor)

### What Failed / Required Fixing
- Nothing failed in CLI deploy.
- ⚠️ DC_* actions cannot be tested via Apex anonymous because they use `ConnectApi.CdpQuery` which requires Data Cloud streams to be created and synced (UI step).

### Data Cloud Dependency (Manual Steps)
1. Create CRM Data Streams for 5 objects (WA_Household__c, WA_Client__c, WA_Financial_Account__c, WA_Financial_Goal__c, WA_Meeting__c)
2. Wait 5-10 minutes for initial sync
3. Run `sf apex run --file scripts/apex/verify-data.apex` to confirm DLM table names
4. Update Apex classes if DLM names differ from coded values

### Reproducible Deploy Order
```bash
cd my-agent-project-003-fsi-wealth_advisor_agent-datacloud
# Objects already deployed from Project 2
sf project deploy start --source-dir force-app/main/default/classes --wait 20
sf apex run --file scripts/apex/grant-permissions.apex
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20
# MANUAL: Create Data Cloud CRM data streams (5 objects) via UI
# MANUAL: Wait for sync, run verify-data.apex
# MANUAL: Setup → Agents → WA DC Advisor → Assign user → New Version → Commit → Activate
# THEN: sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20
```

---

## Project 4: my-agent-project-004-fsi-wealth_advisor_agent-phase1to5 (WA Phase 1-5)

### What Worked (CLI deploy) — ALL FIRST TRY ✅
- ✅ 8 custom objects + 44 fields (3 new: WA_Transaction__c, WA_Referral__c, WA_Audit_Log__c + 1 new field Target_Allocation__c on WA_Financial_Account__c)
- ✅ 11 Apex classes (5 new: DC_AuditLogAction, DC_ComplianceCheckAction, DC_RebalancingAction, DC_ReferralTrackingAction, DC_TransactionHistoryAction, DC_MarketDataAction, DC_NewsSearchAction + 4 updated from Project 3)
- ✅ FLS granted for 44 fields (23 new)
- ✅ Seed data: 5 households, 10 clients, 13 accounts, 10 goals, 5 meetings, 52 transactions, 5 referrals (90+ records)
- ✅ Apex class access granted to Einstein Agent User (7 new classes)
- ✅ 3 permission sets (WA_Advisor, WA_Compliance_Officer, WA_Admin)
- ✅ Agent bundle (WA_P1to5_Advisor)

### What Failed / Required Fixing
- Nothing failed in CLI deploy.
- ⚠️ DC_* actions require Data Cloud streams (same as Project 3, but 7 objects instead of 5)
- ⚠️ DC_MarketDataAction and DC_NewsSearchAction require API keys (optional)

### Data Verification ✅
- 52 transactions confirmed in org
- 5 referrals confirmed in org
- Project 2 SOQL-based actions still work after re-seed

### Pending (Manual Steps)
1. Create Data Cloud CRM data streams for 7 objects (NOT WA_Audit_Log__c — it's CRM-only)
   - See `docs/data-cloud-setup-instructions.md` for category mapping and step-by-step
2. Activate agents via UI (Setup → Agents)
3. Deploy test definitions after agent activation
4. Optional: Set up API keys for market data + news
5. Optional: Deploy remote site settings for external APIs
6. Optional: Seed Knowledge articles + publish

### Reproducible Deploy Order
```bash
cd my-agent-project-004-fsi-wealth_advisor_agent-phase1to5
sf project deploy start --source-dir force-app/main/default/objects --wait 20
sf project deploy start --source-dir force-app/main/default/classes --wait 20
sf project deploy start --source-dir force-app/main/default/permissionsets --wait 20
sf apex run --file scripts/apex/grant-fls.apex
sf apex run --file scripts/apex/seed-data.apex
sf apex run --file scripts/apex/grant-permissions.apex
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20
# Phase 4: Deploy CORS + CSP for Experience Cloud chat widget
# (First update URLs in corsWhitelistOrigins/ and cspTrustedSites/ to match your org's site domain)
sf project deploy start --source-dir force-app/main/default/corsWhitelistOrigins --wait 20
sf project deploy start --source-dir force-app/main/default/cspTrustedSites --wait 20
# MANUAL: Create Data Cloud CRM data streams (7 objects) via UI
# MANUAL: Wait for sync, run verify-data.apex
# MANUAL: Setup → Agents → WA P1to5 Advisor → Assign user → New Version → Commit → Activate
# THEN: sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20
# MANUAL: Create Experience Cloud site (Help Center template) → customize branding → configure AI Experiences → publish
# See docs/phase4-deployment-channels.md for detailed steps
```

---

## Summary

### Deployment Scorecard

| Project | CLI Deploys | Failures | Apex Tests | Status |
|---------|------------|----------|------------|--------|
| 1 (Hello World) | 2/5 | 3 (bot/planner/test) | 1/1 ✅ | Partial — needs UI agent creation |
| 2 (WA CRM) | 5/5 | 0 | 4/4 ✅ | Complete — needs UI agent activation |
| 3 (WA Data Cloud) | 3/3 | 0 | N/A (needs DC streams) | Complete — needs Data Cloud setup |
| 4 (WA Phase 1-5) | 8/8 | 0 | N/A (needs DC streams) | Complete — needs Data Cloud + Experience Cloud setup |

### Key Findings

1. **Fully portable via CLI:** CustomObject, CustomField, ApexClass, PermissionSet, AiAuthoringBundle, CorsWhitelistOrigin, CspTrustedSite, RemoteSiteSetting, Apex scripts
2. **NOT portable via CLI:** GenAiPlannerBundle, Bot/BotVersion, AiEvaluationDefinition (depends on bot)
3. **Requires UI:** Agent activation (assign user → commit → activate), Data Cloud stream creation
4. **First deploy to fresh org:** ~7 minutes (SOAP API warmup). Subsequent deploys: 1-7 seconds.
5. **Deploy order matters:** Objects → Classes → FLS → Seed Data → Permissions → Agent Bundle → (UI activation) → Test Definitions
6. **Cross-project compatibility:** Projects 2-4 share the same custom objects. Deploying Project 4 objects updates Project 2's objects (adds fields, changes metadata). Project 2 SOQL actions continue to work after Project 4 deployment.
