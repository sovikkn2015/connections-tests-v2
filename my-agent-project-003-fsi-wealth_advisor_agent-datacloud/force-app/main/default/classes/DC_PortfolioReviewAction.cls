public with sharing class DC_PortfolioReviewAction {

    public class ReviewInput {
        @InvocableVariable(label='Client Name' description='Name of the client to review portfolio for' required=true)
        public String clientName;
    }

    public class ReviewOutput {
        @InvocableVariable(label='Portfolio Summary' description='Portfolio allocation, performance, and alerts from Data Cloud')
        public String portfolioSummary;
    }

    @InvocableMethod(
        label='Get Portfolio Summary (Data Cloud)'
        description='Returns portfolio allocation breakdown, YTD returns from Data Cloud'
    )
    public static List<ReviewOutput> getPortfolioSummary(List<ReviewInput> inputs) {
        List<ReviewOutput> outputs = new List<ReviewOutput>();

        for (ReviewInput input : inputs) {
            ReviewOutput output = new ReviewOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|s)\\s*', ' ')
                .replaceAll('(?i)s$', '')
                .trim();
            if (String.isBlank(cleanName)) cleanName = rawName;

            try {
                // Find client
                ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                cq.sql = 'SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                if (cr.data == null || cr.data.isEmpty()) {
                    output.portfolioSummary = 'No client found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                String clientId = String.valueOf(cr.data[0].rowData[0]);
                String clientName2 = String.valueOf(cr.data[0].rowData[1]);
                String hhId = String.valueOf(cr.data[0].rowData[2]);

                // Get household info
                ConnectApi.CdpQueryInput hq = new ConnectApi.CdpQueryInput();
                hq.sql = 'SELECT Name__c, Risk_Profile_c__c FROM WA_Household_c_Home__dlm WHERE Id__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                ConnectApi.CdpQueryOutputV2 hr = ConnectApi.CdpQuery.queryAnsiSqlV2(hq);

                String hhName = hr.data != null && !hr.data.isEmpty() ? String.valueOf(hr.data[0].rowData[0]) : 'Unknown';
                String risk = hr.data != null && !hr.data.isEmpty() ? String.valueOf(hr.data[0].rowData[1]) : 'Unknown';

                // Get accounts
                ConnectApi.CdpQueryInput aq = new ConnectApi.CdpQueryInput();
                aq.sql = 'SELECT Name__c, Type_c__c, Balance_c__c, Allocation_c__c, YTD_Return_c__c FROM WA_Financial_Account_c_Home__dlm ' +
                    'WHERE Client_c__c = \'' + String.escapeSingleQuotes(clientId) + '\'';
                ConnectApi.CdpQueryOutputV2 ar = ConnectApi.CdpQuery.queryAnsiSqlV2(aq);

                String summary = 'Portfolio Review: ' + clientName2
                    + '\nHousehold: ' + hhName
                    + '\nRisk Profile: ' + risk;

                Decimal totalBal = 0;
                if (ar.data != null && !ar.data.isEmpty()) {
                    summary += '\n\nAccounts:';
                    for (ConnectApi.CdpQueryV2Row row : ar.data) {
                        Decimal bal = row.rowData[2] != null ? Decimal.valueOf(String.valueOf(row.rowData[2])) : 0;
                        totalBal += bal;
                        summary += '\n  - ' + row.rowData[0] + ' (' + row.rowData[1] + ')'
                            + '\n    Balance: $' + formatCurrency(bal)
                            + '\n    Allocation: ' + row.rowData[3]
                            + '\n    YTD Return: ' + (row.rowData[4] != null ? row.rowData[4] + '%' : 'N/A');
                    }
                }
                summary += '\n\nTotal Portfolio Value: $' + formatCurrency(totalBal);

                output.portfolioSummary = summary;
            } catch (Exception e) {
                output.portfolioSummary = 'Error querying Data Cloud: ' + e.getMessage();
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
