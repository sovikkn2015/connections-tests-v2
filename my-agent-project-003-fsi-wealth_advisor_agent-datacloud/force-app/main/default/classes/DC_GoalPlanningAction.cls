public with sharing class DC_GoalPlanningAction {

    public class GoalInput {
        @InvocableVariable(label='Client Name' description='Name of the client or household to get goals for' required=true)
        public String clientName;
    }

    public class GoalOutput {
        @InvocableVariable(label='Goals Summary' description='Financial goals with progress and gap analysis from Data Cloud')
        public String goalsSummary;
    }

    @InvocableMethod(
        label='Get Financial Goals (Data Cloud)'
        description='Returns financial goals with target amounts, current progress, and gap analysis from Data Cloud'
    )
    public static List<GoalOutput> getFinancialGoals(List<GoalInput> inputs) {
        List<GoalOutput> outputs = new List<GoalOutput>();

        for (GoalInput input : inputs) {
            GoalOutput output = new GoalOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|s)\\s*', ' ')
                .replaceAll('(?i)s$', '')
                .trim();
            if (String.isBlank(cleanName)) cleanName = rawName;

            try {
                // Find clients matching name (could be household or individual)
                ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                cq.sql = 'SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\'';
                ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                // Also search by household name
                ConnectApi.CdpQueryInput hq = new ConnectApi.CdpQueryInput();
                hq.sql = 'SELECT Id__c, Name__c FROM WA_Household_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 hr = ConnectApi.CdpQuery.queryAnsiSqlV2(hq);

                Set<String> clientIds = new Set<String>();
                String householdName = cleanName;

                if (hr.data != null && !hr.data.isEmpty()) {
                    String hhId = String.valueOf(hr.data[0].rowData[0]);
                    householdName = String.valueOf(hr.data[0].rowData[1]);
                    // Get all clients in this household
                    ConnectApi.CdpQueryInput hcq = new ConnectApi.CdpQueryInput();
                    hcq.sql = 'SELECT Id__c FROM WA_Client_c_Home__dlm WHERE Household_c__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                    ConnectApi.CdpQueryOutputV2 hcr = ConnectApi.CdpQuery.queryAnsiSqlV2(hcq);
                    if (hcr.data != null) {
                        for (ConnectApi.CdpQueryV2Row row : hcr.data) {
                            clientIds.add(String.valueOf(row.rowData[0]));
                        }
                    }
                }
                if (cr.data != null) {
                    for (ConnectApi.CdpQueryV2Row row : cr.data) {
                        clientIds.add(String.valueOf(row.rowData[0]));
                    }
                }

                if (clientIds.isEmpty()) {
                    output.goalsSummary = 'No client or household found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                // Build IN clause
                List<String> idList = new List<String>(clientIds);
                String inClause = '\'' + String.join(idList, '\',\'') + '\'';

                ConnectApi.CdpQueryInput gq = new ConnectApi.CdpQueryInput();
                gq.sql = 'SELECT Name__c, Target_Amount_c__c, Current_Amount_c__c, Target_Date_c__c, Client_c__c ' +
                    'FROM WA_Financial_Goal_c_Home__dlm WHERE Client_c__c IN (' + inClause + ')';
                ConnectApi.CdpQueryOutputV2 gr = ConnectApi.CdpQuery.queryAnsiSqlV2(gq);

                if (gr.data == null || gr.data.isEmpty()) {
                    output.goalsSummary = 'No financial goals found for "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                String summary = 'Financial Goals: ' + householdName;
                for (ConnectApi.CdpQueryV2Row row : gr.data) {
                    Decimal target = row.rowData[1] != null ? Decimal.valueOf(String.valueOf(row.rowData[1])) : 0;
                    Decimal current = row.rowData[2] != null ? Decimal.valueOf(String.valueOf(row.rowData[2])) : 0;
                    Decimal progress = target > 0 ? ((current / target) * 100).setScale(1) : 0;
                    Decimal gap = target - current;

                    summary += '\n\n  ' + row.rowData[0]
                        + '\n    Target: $' + formatCurrency(target)
                        + '\n    Current: $' + formatCurrency(current)
                        + '\n    Progress: ' + progress + '%'
                        + '\n    Gap: $' + formatCurrency(gap)
                        + '\n    Target Date: ' + (row.rowData[3] != null ? String.valueOf(row.rowData[3]) : 'Not set');
                }

                output.goalsSummary = summary;
            } catch (Exception e) {
                output.goalsSummary = 'Error querying Data Cloud: ' + e.getMessage();
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
