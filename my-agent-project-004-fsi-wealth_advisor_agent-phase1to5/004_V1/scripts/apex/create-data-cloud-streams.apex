// Create Data Cloud CRM data streams programmatically via REST API
// Run: sf apex run --file scripts/apex/create-data-cloud-streams.apex
//
// This script creates CRM Connector data streams for all 7 WA_* objects
// in Data Cloud. It uses the /services/data/v66.0/ssot/data-streams REST API.
//
// Prerequisites:
//   - Data Cloud must be provisioned and live in your org
//   - The CRM objects must already be deployed (sf project deploy start --source-dir force-app/main/default/objects)
//   - Seed data should be loaded (sf apex run --file scripts/apex/seed-data.apex)
//
// After running this script:
//   - Wait 5-10 minutes for the initial data sync
//   - Run scripts/apex/verify-data.apex to confirm data is queryable
//   - If DLM object names differ, update the SQL in the DC_* Apex classes
//
// API Reference:
//   https://developer.salesforce.com/blogs/2026/01/streamline-data-360-onboarding-with-api-driven-automation

// Define all 7 data streams to create
// Format: { objectName, streamName, category }
// Categories: Profile (for people), Engagement (for events with timestamps), Other (for everything else)
List<Map<String, String>> streams = new List<Map<String, String>>{
    new Map<String, String>{ 'object' => 'WA_Household__c',          'name' => 'WA_Household_c_Home',          'category' => 'Other' },
    new Map<String, String>{ 'object' => 'WA_Client__c',             'name' => 'WA_Client_c_Home',             'category' => 'Profile' },
    new Map<String, String>{ 'object' => 'WA_Financial_Account__c',  'name' => 'WA_Financial_Account_c_Home',  'category' => 'Other' },
    new Map<String, String>{ 'object' => 'WA_Financial_Goal__c',     'name' => 'WA_Financial_Goal_c_Home',     'category' => 'Other' },
    new Map<String, String>{ 'object' => 'WA_Meeting__c',            'name' => 'WA_Meeting_c_Home',            'category' => 'Engagement' },
    new Map<String, String>{ 'object' => 'WA_Transaction__c',        'name' => 'WA_Transaction_c_Home',        'category' => 'Other' },
    new Map<String, String>{ 'object' => 'WA_Referral__c',           'name' => 'WA_Referral_c_Home',           'category' => 'Other' }
};

String baseUrl = URL.getOrgDomainUrl().toExternalForm();
String endpoint = baseUrl + '/services/data/v66.0/ssot/data-streams';
String sessionId = UserInfo.getSessionId();

// The CRM connector name — this is the default for the home org.
// If your org uses a different connector name, update this value.
// You can find it by checking existing data streams in Data Cloud.
String connectorName = 'SalesforceDotCom_Home';

Integer created = 0;
Integer skipped = 0;
Integer failed = 0;

for (Map<String, String> stream : streams) {
    String objectName = stream.get('object');
    String streamName = stream.get('name');
    String category = stream.get('category');

    try {
        // Build the payload
        // Required fields: name, connectorInfo (connectorDetails.name, connectorDetails.sourceObject, connectorType),
        //                   dataAccessMode, dataLakeObjectInfo (category, dataspaceInfo)
        String payload = '{' +
            '"name": "' + streamName + '",' +
            '"connectorInfo": {' +
                '"connectorDetails": {' +
                    '"name": "' + connectorName + '",' +
                    '"sourceObject": "' + objectName + '"' +
                '},' +
                '"connectorType": "SalesforceDotCom"' +
            '},' +
            '"dataAccessMode": "INGEST",' +
            '"dataLakeObjectInfo": {' +
                '"category": "' + category + '",' +
                '"dataspaceInfo": [{"name": "default"}]' +
            '}' +
        '}';

        HttpRequest req = new HttpRequest();
        req.setEndpoint(endpoint);
        req.setMethod('POST');
        req.setHeader('Authorization', 'Bearer ' + sessionId);
        req.setHeader('Content-Type', 'application/json');
        req.setBody(payload);
        req.setTimeout(60000);

        Http http = new Http();
        HttpResponse res = http.send(req);

        if (res.getStatusCode() == 201) {
            created++;
            System.debug('✅ Created: ' + objectName + ' → ' + streamName + ' (category: ' + category + ')');
        } else if (res.getStatusCode() == 409 || res.getBody().contains('already exists')) {
            skipped++;
            System.debug('⏭️ Skipped (already exists): ' + objectName);
        } else {
            failed++;
            System.debug('❌ Failed: ' + objectName + ' → HTTP ' + res.getStatusCode() + ' | ' + res.getBody());
        }
    } catch (Exception e) {
        failed++;
        System.debug('❌ Error creating stream for ' + objectName + ': ' + e.getMessage());
    }
}

System.debug('============================================================');
System.debug('Data Cloud Stream Creation Summary:');
System.debug('  Created: ' + created);
System.debug('  Skipped (already exist): ' + skipped);
System.debug('  Failed: ' + failed);
System.debug('');
System.debug('Next steps:');
System.debug('  1. Wait 5-10 minutes for initial data sync');
System.debug('  2. Run: sf apex run --file scripts/apex/verify-data.apex');
System.debug('  3. If DLM names differ, update SQL in DC_* Apex classes');
System.debug('============================================================');
