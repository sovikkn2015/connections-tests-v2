# Data Cloud Setup Instructions — Phase 1-5 (One-Time UI Steps)

## Before You Start

Deploy objects, classes, seed data, and permissions first:
```bash
cd my-agent-project-004-fsi-wealth_advisor_agent-phase1to5
sf project deploy start --source-dir force-app/main/default/objects --wait 20
sf project deploy start --source-dir force-app/main/default/classes --wait 20
sf project deploy start --source-dir force-app/main/default/permissionsets --wait 20
sf apex run --file scripts/apex/grant-fls.apex
sf apex run --file scripts/apex/seed-data.apex
sf apex run --file scripts/apex/grant-permissions.apex
```

## Step 1: Open Data Cloud

```bash
sf org open
```
Then: App Launcher (waffle icon) → search "Data Cloud" → click it.

## Step 2: Create CRM Data Stream

1. Click "Data Streams" in the left nav
2. Click "New" (blue button, top right)
3. Select "Salesforce CRM" as the source
4. Click "View Objects"
5. Search "WA_" to filter
6. Check these 7 objects:
   - WA_Household__c
   - WA_Client__c
   - WA_Financial_Account__c
   - WA_Financial_Goal__c
   - WA_Meeting__c
   - WA_Transaction__c
   - WA_Referral__c
7. **DO NOT** select WA_Audit_Log__c — it's CRM-only (compliance logging via DML, not queried via Data Cloud)
8. Click "Next"

## Step 3: Configure Each Object

Click each object in the left sidebar and set the category:

| Object | Category | Event Time Field | Primary Key | Notes |
|--------|----------|-----------------|-------------|-------|
| WA_Household__c | **Other** | (leave blank) | Record ID | |
| WA_Client__c | **Profile** | (leave blank) | Record ID | |
| WA_Financial_Account__c | **Other** | (leave blank) | Record ID | |
| WA_Financial_Goal__c | **Other** | (leave blank) | Record ID | |
| WA_Meeting__c | **Engagement** | Date_Time__c | Record ID | Engagement requires an event time field |
| WA_Transaction__c | **Engagement** | Date__c | Record ID | Engagement requires an event time field |
| WA_Referral__c | **Other** | (leave blank) | Record ID | |

For each object:
- Select the category from the dropdown
- For Engagement objects (Meeting, Transaction): also set the "Event Time Field"
- Leave "Primary Key" as "Record ID"
- Make sure all custom fields are selected (check the "Custom Fields" tab)
- Leave "Batch Ingestion" fields unchecked (for streaming ingestion)

Click "Next" → "Deploy" → "Save"

## Step 4: Wait for Initial Sync

Data Cloud takes 5-10 minutes for the initial sync. You can check progress:
- Data Cloud → Data Streams → click your stream → check "Last Refreshed" timestamps

## Step 5: Verify Data Synced

```bash
sf apex run --file scripts/apex/verify-data.apex
```

This queries each DLM table and shows record counts. Expected:

| DLM Object | Expected Records |
|------------|-----------------|
| WA_Household_c_Home__dlm | 5 |
| WA_Client_c_Home__dlm | 10 |
| WA_Financial_Account_c_Home__dlm | 13 |
| WA_Financial_Goal_c_Home__dlm | 10 |
| WA_Meeting_c_Home__dlm | 5 |
| WA_Transaction_c_Home__dlm | 52 |
| WA_Referral_c_Home__dlm | 5 |

**Important:** DLM object names may vary by org. If verify-data.apex fails, check Data Cloud → Data Model for the exact names and update the Apex classes accordingly.

## Step 6: Deploy Agent and Activate

```bash
# Deploy agent script
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles --wait 20
```

Then activate via UI:
1. `sf org open`
2. Setup → Agents (or Agentforce Studio)
3. Find "WA P1to5 Advisor"
4. Assign EinsteinServiceAgent user
5. Click "New Version" → Commit → Activate

## Step 7: Deploy Test Definitions and Run Tests

```bash
# Deploy test definitions (only after agent is activated)
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions --wait 20

# Run tests
sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --verbose
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "We hit a snag" — select category | Each object needs a category. See the table in Step 3 |
| "DataModelEntity not found" | DLM name is wrong. Check Data Cloud → Data Model for exact names |
| verify-data.apex shows 0 records | Stream hasn't synced yet. Wait 5-10 minutes and retry |
| Agent doesn't call actions | Run `grant-permissions.apex` to give agent user Apex class access |
| "No client found" in agent | DLM field names may differ. Check Data Cloud → Data Model |
| WA_Audit_Log__c errors | Don't add it to Data Cloud. It's CRM-only, written via DML |
| Transaction/Referral show 0 in DC | These are new streams — may take longer to sync initially |
