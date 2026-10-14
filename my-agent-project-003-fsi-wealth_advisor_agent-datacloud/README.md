# FSI Wealth Advisor Agent - Data Cloud Edition (Option B)

Same wealth advisor agent as Option A, but queries data from Salesforce Data Cloud via `ConnectApi.CdpQuery` instead of SOQL on CRM objects.

## Architecture

```
Option A: Agent → Apex → SOQL → CRM Custom Objects (WA_Household__c)
Option B: Agent → Apex → ConnectApi.CdpQuery → Data Cloud DLMs (*__dlm)
```

## Prerequisites
- Data Cloud provisioned and live
- Salesforce CLI (`sf`) installed
- Authenticated: `sf org login web --alias my-org`

## Setup

### Step 1: Deploy custom objects, Apex classes, and seed data (programmatic)
```bash
# Deploy objects and classes
sf project deploy start --source-dir force-app

# Grant field-level security
sf apex run --file scripts/apex/grant-fls.apex

# Seed CRM data (this data will sync to Data Cloud via CRM Connector)
sf apex run --file scripts/apex/seed-data.apex
```

### Step 2: Create CRM Data Streams (UI - one time)
1. `sf org open`
2. Go to App Launcher → "Data Cloud"
3. Click "Data Streams" → "New"
4. Select "Salesforce CRM" as source
5. Select these 5 objects:
   - WA_Household__c
   - WA_Client__c
   - WA_Financial_Account__c
   - WA_Financial_Goal__c
   - WA_Meeting__c
6. Deploy each data stream
7. Wait 5-10 minutes for initial sync

### Step 3: Verify data synced (programmatic)
```bash
sf apex run --file scripts/apex/verify-data.apex
```
Note: DLM object names may vary. Check Data Cloud > Data Model for exact names and update Apex classes if needed.

### Step 4: Grant permissions (programmatic)
```bash
sf apex run --file scripts/apex/grant-permissions.apex
```

### Step 5: Deploy agent (programmatic)
```bash
sf project deploy start --source-dir force-app/main/default/aiAuthoringBundles
sf project deploy start --source-dir force-app/main/default/aiEvaluationDefinitions
```

### Step 6: Activate agent (UI)
1. `sf org open`
2. Find "WA DC Advisor" in Agents
3. Assign user → Save → Commit → Activate

### Step 7: Test (programmatic)
```bash
sf agent test run --api-name WA_DC_Advisor_Test --wait 10 --verbose
```

## Test Queries
- "Tell me about the Johnson household"
- "How is Wei Chen's portfolio?"
- "What are the Patels' goals?"
- "Prep me for my meeting with Carlos"
- "Transfer me to compliance"
- "What's the stock price of Apple?"

## Important Notes
- The Apex classes use `ConnectApi.CdpQuery.queryAnsiSqlV2()` to query Data Cloud
- DLM object names (e.g., `WA_Household__dlm`) may differ based on how Data Cloud names them during stream creation
- After creating data streams, run `verify-data.apex` to confirm the exact object/field names
- Update the Apex classes if the DLM names differ from what's coded

## Project Structure
```
force-app/main/default/
  aiAuthoringBundles/WA_DC_Advisor/   # Agent script
  aiEvaluationDefinitions/             # Test spec
  classes/                             # 4 DC_* Apex actions using CdpQuery
  objects/                             # 5 custom objects (same as Option A)
scripts/apex/
  seed-data.apex                       # Seeds 5 households into CRM objects
  grant-fls.apex                       # Grants FLS to System Administrator
  grant-permissions.apex               # Grants agent user Apex class access
  ingest-data.apex                     # Verifies CRM source data exists
  verify-data.apex                     # Verifies Data Cloud has the data
```
