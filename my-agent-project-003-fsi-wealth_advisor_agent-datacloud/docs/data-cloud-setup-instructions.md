# Data Cloud Setup Instructions (One-Time UI Steps)

## Before You Start
Run these commands first to deploy objects and seed data:
```bash
cd my-agent-project-003-fsi-wealth_advisor_agent-datacloud
sf project deploy start --source-dir force-app/main/default/objects
sf apex run --file scripts/apex/grant-fls.apex
sf apex run --file scripts/apex/seed-data.apex
```

## Step 1: Open Data Cloud Setup
```bash
sf org open --path "/lightning/setup/CDPSetupHome/home"
```

## Step 2: Navigate to Data Streams
1. Open the App Launcher (waffle icon, top left)
2. Search for "Data Streams" and click it
3. You should see a "Data Streams" list view (may show "Recently Viewed" with 0 items)
4. Click "New" (blue button, top right)

## Step 3: Create Data Streams
1. Click the "New" button (blue, top right)
2. In the "New Data Stream" dialog:
   - Salesforce Org: select "121" (your home org)
   - Click "View Objects" (not View Bundles)
   - In the Search box, type "WA_" to filter
   - Check the boxes for all 5 objects:
     - WA_Client__c
     - WA_Financial_Account__c
     - WA_Financial_Goal__c
     - WA_Household__c
     - WA_Meeting__c
   - Click "Next"
3. On the next screen, for each object in the left sidebar, click on it and configure:

| Object | Object Category | Event Time Field | Primary Key |
|--------|----------------|-----------------|-------------|
| WA_Client__c | Profile | (leave blank) | Record ID |
| WA_Financial_Account__c | Other | (leave blank) | Record ID |
| WA_Financial_Goal__c | Other | (leave blank) | Record ID |
| WA_Household__c | Other | (leave blank) | Record ID |
| WA_Meeting__c | Engagement | Date_Time__c | Record ID |

   - Click each object name in the left sidebar
   - Set the "Object Category" dropdown (required for all objects)
   - For WA_Meeting__c: also set "Event Time Field" to Date_Time__c (required for Engagement category)
   - Leave "Primary Key" as "Record ID" for all
   - Make sure all fields are selected (check "Custom Fields" tab too)
4. Click "Next" / "Deploy" / "Save"

## Step 4: Map Data Lake Objects to Data Model Objects
1. Go to Data Cloud app → "Data Lake Objects" tab (top nav)
2. You should see 5 WA objects with record counts
3. For each object, do the following:
   a. Click the object name (e.g., "WA_Household__c_Home")
   b. On the right side, under "Data Mapping", click "Start"
   c. In the "Select Objects" dialog, click "Custom Data Model" tab
   d. Click "New" to create a new custom DMO
   e. Einstein auto-maps all fields — verify all fields show as "Is Mapped"
   f. Click "Save" (blue button, top right)
   g. Go back to Data Lake Objects list and repeat for the next object

Do this for all 5:
- WA_Household__c_Home
- WA_Client__c_Home
- WA_Financial_Account__c_Home
- WA_Financial_Goal__c_Home
- WA_Meeting__c_Home

## Step 5: Wait for Data Model sync
- After mapping, wait 5-10 minutes for the DMOs to become queryable
- You can check status in Data Cloud > Data Model > switch to "Mapped" view

## Step 6: Verify data synced (programmatic)
```bash
sf apex run --file scripts/apex/verify-data.apex
```
This will query each Data Cloud DLM object and show record counts.

**Important:** The DLM object names may differ from what's coded in the Apex classes.
Common patterns:
- `WA_Household__dlm` (simple)
- `WA_Household_WA_Household__dlm` (prefixed with connector name)
- Check Data Cloud > Data Model for exact names

If names differ, update the SQL strings in the 4 DC_* Apex classes.

## Step 6: Deploy Apex Classes and Agent
```bash
sf project deploy start --source-dir force-app/main/default/classes
sf apex run --file scripts/apex/grant-permissions.apex
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions
```

## Step 7: Activate Agent
1. `sf org open`
2. Go to Agentforce Studio > Agents
3. Find "WA DC Advisor"
4. Assign EinsteinServiceAgent user
5. Save > Commit Version > Activate

## Step 8: Test
```bash
sf agent test run --api-name WA_DC_Advisor_Test --wait 10 --verbose
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "DataModelEntity not found" | DLM object name is wrong. Check Data Cloud > Data Model for exact names |
| verify-data.apex shows 0 records | Data stream hasn't synced yet. Wait 5-10 minutes |
| Agent doesn't call actions | Run grant-permissions.apex to give agent user Apex class access |
| "No client found" | Check fuzzy matching in Apex - the DLM field names may differ |
