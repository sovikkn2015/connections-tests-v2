// Verify data is queryable in Data Cloud
// Run: sf apex run --file scripts/apex/verify-data.apex
// Run this AFTER the data streams have synced (wait ~5-10 minutes after setup)

// NOTE: The DLM object names below may need adjustment based on how Data Cloud
// names them during data stream creation. Check Data Cloud > Data Model for exact names.
// Common patterns:
//   CRM objects: WA_Household__c → WA_Household__dlm or WA_Household_WA_Household__dlm
//   Ingestion API: Uses the object name from the schema you defined

List<String> queries = new List<String>{
    'SELECT COUNT() FROM WA_Household__dlm',
    'SELECT COUNT() FROM WA_Client__dlm',
    'SELECT COUNT() FROM WA_Financial_Account__dlm',
    'SELECT COUNT() FROM WA_Financial_Goal__dlm',
    'SELECT COUNT() FROM WA_Meeting__dlm'
};

for (String sql : queries) {
    try {
        ConnectApi.CdpQueryInput queryInput = new ConnectApi.CdpQueryInput();
        queryInput.sql = sql;
        ConnectApi.CdpQueryOutputV2 response = ConnectApi.CdpQuery.queryAnsiSqlV2(queryInput);
        System.debug(sql + ' → ' + response.data);
    } catch (Exception e) {
        System.debug(sql + ' → ERROR: ' + e.getMessage());
    }
}

// Also try a sample query to verify field names
try {
    ConnectApi.CdpQueryInput queryInput = new ConnectApi.CdpQueryInput();
    queryInput.sql = 'SELECT * FROM WA_Household__dlm LIMIT 1';
    ConnectApi.CdpQueryOutputV2 response = ConnectApi.CdpQuery.queryAnsiSqlV2(queryInput);
    System.debug('Sample household: ' + response.data);
    System.debug('Metadata: ' + response.metadata);
} catch (Exception e) {
    System.debug('Sample query error: ' + e.getMessage());
    System.debug('TIP: Check Data Cloud > Data Model for the exact DLM object names.');
    System.debug('You may need to update the SQL in the Apex classes to match.');
}
