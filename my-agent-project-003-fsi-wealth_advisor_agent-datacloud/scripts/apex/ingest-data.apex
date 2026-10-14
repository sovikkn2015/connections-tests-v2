// Ingest data into Data Cloud via Ingestion API
// Run: sf apex run --file scripts/apex/ingest-data.apex
//
// IMPORTANT: This script uses the CRM data that already exists in the org
// (from Option A's seed-data.apex). The CRM Connector data stream will
// automatically sync the WA_* custom objects into Data Cloud.
//
// If you used the Ingestion API approach instead of CRM Connector,
// you would need to POST JSON data to the Ingestion API endpoint.
// That requires a Connected App + OAuth token exchange which is
// beyond what can be done in anonymous Apex.
//
// For CRM Connector approach: No action needed here.
// The data streams will sync automatically once created in the UI.
//
// To verify the data synced, run: sf apex run --file scripts/apex/verify-data.apex

// Verify the source CRM data exists
Integer households = [SELECT COUNT() FROM WA_Household__c];
Integer clients = [SELECT COUNT() FROM WA_Client__c];
Integer accounts = [SELECT COUNT() FROM WA_Financial_Account__c];
Integer goals = [SELECT COUNT() FROM WA_Financial_Goal__c];
Integer meetings = [SELECT COUNT() FROM WA_Meeting__c];

System.debug('=== CRM Source Data (will sync to Data Cloud) ===');
System.debug('Households: ' + households);
System.debug('Clients: ' + clients);
System.debug('Financial Accounts: ' + accounts);
System.debug('Financial Goals: ' + goals);
System.debug('Meetings: ' + meetings);

if (households == 0) {
    System.debug('WARNING: No CRM data found. Run the Option A seed-data.apex first:');
    System.debug('  sf apex run --file ../my-agent-project-002-fsi-wealth_advisor_agent/scripts/apex/seed-data.apex');
}
