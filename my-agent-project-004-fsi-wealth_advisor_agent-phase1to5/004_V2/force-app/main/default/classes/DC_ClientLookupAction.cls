public with sharing class DC_ClientLookupAction {

    public class LookupInput {
        @InvocableVariable(label='Client Name' description='Name of the client or household to look up' required=true)
        public String clientName;
    }

    public class LookupOutput {
        @InvocableVariable(label='Client Summary' description='360-degree client and household summary from Data Cloud')
        public String clientSummary;
    }

    @InvocableMethod(
        label='Get Client 360 (Data Cloud)'
        description='Returns a 360-degree view of a client from Data Cloud including household members, accounts, and AUM'
    )
    public static List<LookupOutput> getClient360(List<LookupInput> inputs) {
        List<LookupOutput> outputs = new List<LookupOutput>();

        for (LookupInput input : inputs) {
            LookupOutput output = new LookupOutput();
            try {
                String cleanName = cleanClientName(input.clientName);

                // Try household search first
                ConnectApi.CdpQueryInput q = new ConnectApi.CdpQueryInput();
                q.sql = 'SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c, Advisor_c__c, Id__c ' +
                    'FROM WA_Household_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 r = ConnectApi.CdpQuery.queryAnsiSqlV2(q);

                // Fallback: try splitting name and searching parts
                if ((r.data == null || r.data.isEmpty()) && cleanName.contains(' ')) {
                    List<String> parts = cleanName.split('\\s+');
                    for (String part : parts) {
                        if (part.length() < 2) continue;
                        q.sql = 'SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c, Advisor_c__c, Id__c ' +
                            'FROM WA_Household_c_Home__dlm ' +
                            'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(part) + '%\' LIMIT 1';
                        r = ConnectApi.CdpQuery.queryAnsiSqlV2(q);
                        if (r.data != null && !r.data.isEmpty()) break;
                    }
                }

                // Fallback: search by client name then get household
                if (r.data == null || r.data.isEmpty()) {
                    String hhId = findHouseholdByClientName(cleanName);
                    if (hhId != null) {
                        q.sql = 'SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c, Advisor_c__c, Id__c ' +
                            'FROM WA_Household_c_Home__dlm WHERE Id__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                        r = ConnectApi.CdpQuery.queryAnsiSqlV2(q);
                    }
                }

                if (r.data == null || r.data.isEmpty()) {
                    output.clientSummary = 'No client or household found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                List<Object> row = r.data[0].rowData;
                String hhName = safeStr(row[0]);
                String aum = formatCurrency(row[1]);
                String risk = safeStr(row[2]);
                String advisor = safeStr(row[3]);
                String hhId = safeStr(row[4]);

                String summary = 'Household: ' + hhName
                    + '\nTotal AUM: $' + aum
                    + '\nRisk Profile: ' + risk
                    + '\nAdvisor: ' + advisor;

                // Get clients
                ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                cq.sql = 'SELECT Name__c, Role_c__c, Email_c__c FROM WA_Client_c_Home__dlm ' +
                    'WHERE Household_c__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                if (cr.data != null && !cr.data.isEmpty()) {
                    summary += '\n\nMembers:';
                    for (ConnectApi.CdpQueryV2Row clientRow : cr.data) {
                        summary += '\n  - ' + safeStr(clientRow.rowData[0]) + ' (' + safeStr(clientRow.rowData[1]) + ') | ' + safeStr(clientRow.rowData[2]);
                    }
                }

                // Get accounts
                ConnectApi.CdpQueryInput aq = new ConnectApi.CdpQueryInput();
                aq.sql = 'SELECT Name__c, Type_c__c, Balance_c__c FROM WA_Financial_Account_c_Home__dlm ' +
                    'WHERE Client_c__c IN (SELECT Id__c FROM WA_Client_c_Home__dlm WHERE Household_c__c = \'' + String.escapeSingleQuotes(hhId) + '\')';
                ConnectApi.CdpQueryOutputV2 ar = ConnectApi.CdpQuery.queryAnsiSqlV2(aq);

                if (ar.data != null && !ar.data.isEmpty()) {
                    summary += '\n\nAccounts:';
                    for (ConnectApi.CdpQueryV2Row acctRow : ar.data) {
                        summary += '\n  - ' + safeStr(acctRow.rowData[0]) + ' (' + safeStr(acctRow.rowData[1]) + '): $' + formatCurrency(acctRow.rowData[2]);
                    }
                }

                output.clientSummary = summary;
            } catch (Exception e) {
                output.clientSummary = 'I was unable to look up that client. Please try again with a different name or check the spelling.';
            }

            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                DC_AuditLogAction.logInteraction(
                    'WA_P1to5_Advisor',
                    'client_lookup',
                    'get_client_360',
                    inputs[i].clientName,
                    outputs[i].clientSummary,
                    inputs[i].clientName
                );
            } catch (Exception auditEx) {
                // Don't fail the action if audit logging fails
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        return outputs;
    }

    private static String findHouseholdByClientName(String name) {
        try {
            ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
            cq.sql = 'SELECT Household_c__c FROM WA_Client_c_Home__dlm WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(name) + '%\' LIMIT 1';
            ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);
            if (cr.data != null && !cr.data.isEmpty()) {
                return safeStr(cr.data[0].rowData[0]);
            }
            // Try parts of name
            if (name.contains(' ')) {
                for (String part : name.split('\\s+')) {
                    if (part.length() < 2) continue;
                    cq.sql = 'SELECT Household_c__c FROM WA_Client_c_Home__dlm WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(part) + '%\' LIMIT 1';
                    cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);
                    if (cr.data != null && !cr.data.isEmpty()) {
                        return safeStr(cr.data[0].rowData[0]);
                    }
                }
            }
        } catch (Exception e) {
            // Swallow — caller handles null
        }
        return null;
    }

    private static String cleanClientName(String raw) {
        String rawName = raw != null ? raw.trim() : '';
        String cleanName = rawName
            .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|rebalancing|transactions?|compliance|referral|history|check|alert|recent|meeting|prep)\\s*', ' ')
            .replaceAll('(?i)s$', '')
            .trim();
        if (String.isBlank(cleanName)) cleanName = rawName;
        return cleanName;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }

    private static String formatCurrency(Object value) {
        if (value == null) return '0';
        try {
            Decimal d = Decimal.valueOf(String.valueOf(value));
            if (d >= 1000000) return String.valueOf((d / 1000000).setScale(1)) + 'M';
            if (d >= 1000) return String.valueOf((d / 1000).setScale(0)) + 'K';
            return String.valueOf(d.setScale(2));
        } catch (Exception e) {
            return '0';
        }
    }
}
