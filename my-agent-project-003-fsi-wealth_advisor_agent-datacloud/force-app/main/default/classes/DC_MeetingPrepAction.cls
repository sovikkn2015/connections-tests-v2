public with sharing class DC_MeetingPrepAction {

    public class PrepInput {
        @InvocableVariable(label='Client Name' description='Name of the client to prepare meeting brief for' required=true)
        public String clientName;
    }

    public class PrepOutput {
        @InvocableVariable(label='Meeting Brief' description='Meeting preparation brief from Data Cloud')
        public String meetingBrief;
    }

    @InvocableMethod(
        label='Get Meeting Prep (Data Cloud)'
        description='Returns a meeting preparation brief from Data Cloud including client summary, portfolio, and talking points'
    )
    public static List<PrepOutput> getMeetingPrep(List<PrepInput> inputs) {
        List<PrepOutput> outputs = new List<PrepOutput>();

        for (PrepInput input : inputs) {
            PrepOutput output = new PrepOutput();
            String rawName = input.clientName != null ? input.clientName.trim() : '';
            String cleanName = rawName
                .replaceAll('(?i)\\s*(household|family|the|account|client|portfolio|goals?|meeting|prep|s)\\s*', ' ')
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
                    output.meetingBrief = 'No client found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                String clientId = String.valueOf(cr.data[0].rowData[0]);
                String clientName2 = String.valueOf(cr.data[0].rowData[1]);
                String hhId = String.valueOf(cr.data[0].rowData[2]);

                // Get household
                ConnectApi.CdpQueryInput hq = new ConnectApi.CdpQueryInput();
                hq.sql = 'SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c FROM WA_Household_c_Home__dlm WHERE Id__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                ConnectApi.CdpQueryOutputV2 hr = ConnectApi.CdpQuery.queryAnsiSqlV2(hq);

                String brief = '=== MEETING PREP BRIEF (Data Cloud) ==='
                    + '\nClient: ' + clientName2;
                if (hr.data != null && !hr.data.isEmpty()) {
                    brief += '\nHousehold: ' + hr.data[0].rowData[0]
                        + '\nTotal AUM: $' + formatCurrency(hr.data[0].rowData[1])
                        + '\nRisk Profile: ' + hr.data[0].rowData[2];
                }

                // Get meeting
                ConnectApi.CdpQueryInput mq = new ConnectApi.CdpQueryInput();
                mq.sql = 'SELECT Name__c, Date_Time_c__c, Location_c__c, Notes_c__c, Action_Items_c__c ' +
                    'FROM WA_Meeting_c_Home__dlm WHERE Client_c__c = \'' + String.escapeSingleQuotes(clientId) + '\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 mr = ConnectApi.CdpQuery.queryAnsiSqlV2(mq);

                if (mr.data != null && !mr.data.isEmpty()) {
                    brief += '\n\n--- Upcoming Meeting ---'
                        + '\nSubject: ' + mr.data[0].rowData[0]
                        + '\nDate: ' + mr.data[0].rowData[1]
                        + '\nLocation: ' + mr.data[0].rowData[2]
                        + '\nNotes: ' + mr.data[0].rowData[3]
                        + '\nAction Items: ' + mr.data[0].rowData[4];
                }

                // Get accounts
                ConnectApi.CdpQueryInput aq = new ConnectApi.CdpQueryInput();
                aq.sql = 'SELECT Name__c, Type_c__c, Balance_c__c, YTD_Return_c__c FROM WA_Financial_Account_c_Home__dlm ' +
                    'WHERE Client_c__c = \'' + String.escapeSingleQuotes(clientId) + '\'';
                ConnectApi.CdpQueryOutputV2 ar = ConnectApi.CdpQuery.queryAnsiSqlV2(aq);

                if (ar.data != null && !ar.data.isEmpty()) {
                    brief += '\n\n--- Portfolio Snapshot ---';
                    for (ConnectApi.CdpQueryV2Row row : ar.data) {
                        brief += '\n  ' + row.rowData[0] + ' (' + row.rowData[1] + '): $' + formatCurrency(row.rowData[2])
                            + ' | YTD: ' + (row.rowData[3] != null ? row.rowData[3] + '%' : 'N/A');
                    }
                }

                // Get goals
                ConnectApi.CdpQueryInput gq = new ConnectApi.CdpQueryInput();
                gq.sql = 'SELECT Name__c, Target_Amount_c__c, Current_Amount_c__c FROM WA_Financial_Goal_c_Home__dlm ' +
                    'WHERE Client_c__c = \'' + String.escapeSingleQuotes(clientId) + '\'';
                ConnectApi.CdpQueryOutputV2 gr = ConnectApi.CdpQuery.queryAnsiSqlV2(gq);

                if (gr.data != null && !gr.data.isEmpty()) {
                    brief += '\n\n--- Goals Status ---';
                    for (ConnectApi.CdpQueryV2Row row : gr.data) {
                        Decimal target = row.rowData[1] != null ? Decimal.valueOf(String.valueOf(row.rowData[1])) : 0;
                        Decimal current = row.rowData[2] != null ? Decimal.valueOf(String.valueOf(row.rowData[2])) : 0;
                        Decimal pct = target > 0 ? ((current / target) * 100).setScale(0) : 0;
                        brief += '\n  ' + row.rowData[0] + ': ' + pct + '% ($' + formatCurrency(current) + ' / $' + formatCurrency(target) + ')';
                    }
                }

                brief += '\n\n--- Suggested Talking Points ---'
                    + '\n  1. Review portfolio performance and rebalancing needs'
                    + '\n  2. Discuss progress toward financial goals'
                    + '\n  3. Address life changes or updated priorities'
                    + '\n  4. Review and confirm risk tolerance';

                output.meetingBrief = brief;
            } catch (Exception e) {
                output.meetingBrief = 'Error querying Data Cloud: ' + e.getMessage();
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
