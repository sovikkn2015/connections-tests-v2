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
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?)\\s*', ' ')
                .replaceAll('(?i)s$', '')
                .trim();
            if (String.isBlank(cleanName)) cleanName = rawName;

            try {
                ConnectApi.CdpQueryInput q = new ConnectApi.CdpQueryInput();
                q.sql = 'SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c, Advisor_c__c, Id__c ' +
                    'FROM WA_Household_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 r = ConnectApi.CdpQuery.queryAnsiSqlV2(q);

                if (r.data != null && !r.data.isEmpty()) {
                    List<Object> row = r.data[0].rowData;
                    String hhName = String.valueOf(row[0]);
                    String aum = formatCurrency(row[1]);
                    String risk = String.valueOf(row[2]);
                    String advisor = String.valueOf(row[3]);
                    String hhId = String.valueOf(row[4]);

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
                            summary += '\n  - ' + clientRow.rowData[0] + ' (' + clientRow.rowData[1] + ') | ' + clientRow.rowData[2];
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
                            summary += '\n  - ' + acctRow.rowData[0] + ' (' + acctRow.rowData[1] + '): $' + formatCurrency(acctRow.rowData[2]);
                        }
                    }

                    output.clientSummary = summary;
                } else {
                    output.clientSummary = 'No client or household found matching "' + input.clientName + '".';
                }
            } catch (Exception e) {
                output.clientSummary = 'Error querying Data Cloud: ' + e.getMessage();
            }

            outputs.add(output);
        }
        return outputs;
    }

    private static String formatCurrency(Object value) {
        if (value == null) return '0';
        Decimal d = Decimal.valueOf(String.valueOf(value));
        if (d >= 1000000) return String.valueOf((d / 1000000).setScale(1)) + 'M';
        if (d >= 1000) return String.valueOf((d / 1000).setScale(0)) + 'K';
        return String.valueOf(d.setScale(2));
    }
}
