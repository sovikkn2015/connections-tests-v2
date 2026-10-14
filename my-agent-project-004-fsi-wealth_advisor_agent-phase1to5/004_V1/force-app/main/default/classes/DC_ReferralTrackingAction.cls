public with sharing class DC_ReferralTrackingAction {

    public class ReferralInput {
        @InvocableVariable(label='Client Name' description='Name of the client or household to look up referrals for' required=true)
        public String clientName;
    }

    public class ReferralOutput {
        @InvocableVariable(label='Referral Info' description='Referral source, status, and value from Data Cloud')
        public String referralInfo;
    }

    @InvocableMethod(
        label='Get Referral Info (Data Cloud)'
        description='Returns referral tracking information for a client or household from Data Cloud'
    )
    public static List<ReferralOutput> getReferralInfo(List<ReferralInput> inputs) {
        List<ReferralOutput> outputs = new List<ReferralOutput>();

        for (ReferralInput input : inputs) {
            ReferralOutput output = new ReferralOutput();
            try {
                String cleanName = cleanClientName(input.clientName);

                // Search household first
                ConnectApi.CdpQueryInput hq = new ConnectApi.CdpQueryInput();
                hq.sql = 'SELECT Id__c, Name__c FROM WA_Household_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 hr = ConnectApi.CdpQuery.queryAnsiSqlV2(hq);

                String hhId = null;
                String hhName = cleanName;

                if (hr.data != null && !hr.data.isEmpty()) {
                    hhId = safeStr(hr.data[0].rowData[0]);
                    hhName = safeStr(hr.data[0].rowData[1]);
                } else {
                    // Try finding via client name
                    ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                    cq.sql = 'SELECT Household_c__c, Name__c FROM WA_Client_c_Home__dlm ' +
                        'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                    ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                    if (cr.data == null || cr.data.isEmpty()) {
                        // Fallback: try name parts
                        if (cleanName.contains(' ')) {
                            for (String part : cleanName.split('\\s+')) {
                                if (part.length() < 2) continue;
                                cq.sql = 'SELECT Household_c__c, Name__c FROM WA_Client_c_Home__dlm ' +
                                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(part) + '%\' LIMIT 1';
                                cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);
                                if (cr.data != null && !cr.data.isEmpty()) break;
                            }
                        }
                    }

                    if (cr.data != null && !cr.data.isEmpty()) {
                        hhId = safeStr(cr.data[0].rowData[0]);
                        // Get household name
                        ConnectApi.CdpQueryInput hq2 = new ConnectApi.CdpQueryInput();
                        hq2.sql = 'SELECT Name__c FROM WA_Household_c_Home__dlm WHERE Id__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                        ConnectApi.CdpQueryOutputV2 hr2 = ConnectApi.CdpQuery.queryAnsiSqlV2(hq2);
                        if (hr2.data != null && !hr2.data.isEmpty()) {
                            hhName = safeStr(hr2.data[0].rowData[0]);
                        }
                    }
                }

                if (hhId == null) {
                    output.referralInfo = 'No client or household found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                // Get all clients in household
                ConnectApi.CdpQueryInput ccq = new ConnectApi.CdpQueryInput();
                ccq.sql = 'SELECT Id__c FROM WA_Client_c_Home__dlm WHERE Household_c__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                ConnectApi.CdpQueryOutputV2 ccr = ConnectApi.CdpQuery.queryAnsiSqlV2(ccq);

                if (ccr.data == null || ccr.data.isEmpty()) {
                    output.referralInfo = 'No clients found in household for "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                List<String> clientIds = new List<String>();
                for (ConnectApi.CdpQueryV2Row row : ccr.data) {
                    clientIds.add(safeStr(row.rowData[0]));
                }
                String inClause = '\'' + String.join(clientIds, '\',\'') + '\'';

                // Query referrals
                ConnectApi.CdpQueryInput rq = new ConnectApi.CdpQueryInput();
                rq.sql = 'SELECT Name__c, Source_c__c, Source_Type_c__c, Date_c__c, Status_c__c, Value_c__c, Client_c__c ' +
                    'FROM WA_Referral_c_Home__dlm WHERE Client_c__c IN (' + inClause + ')';
                ConnectApi.CdpQueryOutputV2 rr = ConnectApi.CdpQuery.queryAnsiSqlV2(rq);

                if (rr.data == null || rr.data.isEmpty()) {
                    output.referralInfo = 'No referrals found for the ' + hhName + '.';
                    outputs.add(output);
                    continue;
                }

                String info = 'Referral Tracking: ' + hhName;
                Decimal totalValue = 0;

                for (ConnectApi.CdpQueryV2Row row : rr.data) {
                    Decimal value = row.rowData[5] != null ? Decimal.valueOf(String.valueOf(row.rowData[5])) : 0;
                    totalValue += value;

                    info += '\n\n  ' + safeStr(row.rowData[0])
                        + '\n    Source: ' + safeStr(row.rowData[1])
                        + '\n    Type: ' + safeStr(row.rowData[2])
                        + '\n    Date: ' + safeStr(row.rowData[3])
                        + '\n    Status: ' + safeStr(row.rowData[4])
                        + '\n    Estimated Value: $' + formatCurrency(value);
                }

                info += '\n\n=== SUMMARY ==='
                    + '\nTotal Referrals: ' + rr.data.size()
                    + '\nTotal Estimated Value: $' + formatCurrency(totalValue);

                output.referralInfo = info;
            } catch (Exception e) {
                output.referralInfo = 'I was unable to retrieve referral information. Please try again or check the client name.';
            }

            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                DC_AuditLogAction.logInteraction(
                    'WA_P1to5_Advisor',
                    'referral_tracking',
                    'get_referrals',
                    inputs[i].clientName,
                    outputs[i].referralInfo,
                    inputs[i].clientName
                );
            } catch (Exception auditEx) {
                // Don't fail the action if audit logging fails
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        return outputs;
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
