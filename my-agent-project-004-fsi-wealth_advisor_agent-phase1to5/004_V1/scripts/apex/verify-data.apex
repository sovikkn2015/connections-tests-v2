// Verify data is queryable in Data Cloud — Phase 1-5
// Run: sf apex run --file scripts/apex/verify-data.apex
// Run this AFTER the data streams have synced (wait ~5-10 minutes after setup)

List<String> queries = new List<String>{
    'SELECT COUNT() FROM WA_Household_c_Home__dlm',
    'SELECT COUNT() FROM WA_Client_c_Home__dlm',
    'SELECT COUNT() FROM WA_Financial_Account_c_Home__dlm',
    'SELECT COUNT() FROM WA_Financial_Goal_c_Home__dlm',
    'SELECT COUNT() FROM WA_Meeting_c_Home__dlm',
    'SELECT COUNT() FROM WA_Transaction_c_Home__dlm',
    'SELECT COUNT() FROM WA_Referral_c_Home__dlm'
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

// Sample queries to verify field names
List<String> sampleQueries = new List<String>{
    'SELECT * FROM WA_Household_c_Home__dlm LIMIT 1',
    'SELECT * FROM WA_Transaction_c_Home__dlm LIMIT 1',
    'SELECT * FROM WA_Referral_c_Home__dlm LIMIT 1'
};

for (String sql : sampleQueries) {
    try {
        ConnectApi.CdpQueryInput queryInput = new ConnectApi.CdpQueryInput();
        queryInput.sql = sql;
        ConnectApi.CdpQueryOutputV2 response = ConnectApi.CdpQuery.queryAnsiSqlV2(queryInput);
        System.debug('Sample: ' + sql);
        System.debug('  Data: ' + response.data);
        System.debug('  Metadata: ' + response.metadata);
    } catch (Exception e) {
        System.debug(sql + ' → ERROR: ' + e.getMessage());
        System.debug('TIP: Check Data Cloud > Data Model for the exact DLM object names.');
    }
}
