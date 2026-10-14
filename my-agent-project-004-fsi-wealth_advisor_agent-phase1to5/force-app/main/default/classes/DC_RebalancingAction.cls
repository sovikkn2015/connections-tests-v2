public with sharing class DC_RebalancingAction {

    public class RebalanceInput {
        @InvocableVariable(label='Client Name' description='Name of the client to check rebalancing needs for' required=true)
        public String clientName;
    }

    public class RebalanceOutput {
        @InvocableVariable(label='Rebalancing Analysis' description='Drift analysis comparing current vs target allocation')
        public String rebalancingAnalysis;
    }

    // Target allocations by risk profile: Equity / Fixed / Cash
    private static final Map<String, Map<String, Decimal>> TARGET_ALLOCATIONS = new Map<String, Map<String, Decimal>>{
        'Conservative' => new Map<String, Decimal>{'Equity' => 30, 'Fixed' => 60, 'Cash' => 10},
        'Moderate' => new Map<String, Decimal>{'Equity' => 55, 'Fixed' => 35, 'Cash' => 10},
        'Growth' => new Map<String, Decimal>{'Equity' => 70, 'Fixed' => 20, 'Cash' => 10},
        'Aggressive' => new Map<String, Decimal>{'Equity' => 80, 'Fixed' => 15, 'Cash' => 5}
    };

    @InvocableMethod(
        label='Check Rebalancing Needs (Data Cloud)'
        description='Analyzes portfolio drift from target allocation based on risk profile from Data Cloud'
    )
    public static List<RebalanceOutput> checkRebalancing(List<RebalanceInput> inputs) {
        List<RebalanceOutput> outputs = new List<RebalanceOutput>();

        for (RebalanceInput input : inputs) {
            RebalanceOutput output = new RebalanceOutput();
            try {
                String cleanName = cleanClientName(input.clientName);

                // Find client
                ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                cq.sql = 'SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                if ((cr.data == null || cr.data.isEmpty()) && cleanName.contains(' ')) {
                    for (String part : cleanName.split('\\s+')) {
                        if (part.length() < 2) continue;
                        cq.sql = 'SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm ' +
                            'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(part) + '%\' LIMIT 1';
                        cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);
                        if (cr.data != null && !cr.data.isEmpty()) break;
                    }
                }

                if (cr.data == null || cr.data.isEmpty()) {
                    output.rebalancingAnalysis = 'No client found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                String clientId = safeStr(cr.data[0].rowData[0]);
                String clientName2 = safeStr(cr.data[0].rowData[1]);
                String hhId = safeStr(cr.data[0].rowData[2]);

                // Get risk profile from household
                ConnectApi.CdpQueryInput hq = new ConnectApi.CdpQueryInput();
                hq.sql = 'SELECT Name__c, Risk_Profile_c__c FROM WA_Household_c_Home__dlm WHERE Id__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                ConnectApi.CdpQueryOutputV2 hr = ConnectApi.CdpQuery.queryAnsiSqlV2(hq);

                String hhName = (hr.data != null && !hr.data.isEmpty()) ? safeStr(hr.data[0].rowData[0]) : 'Unknown';
                String riskProfile = (hr.data != null && !hr.data.isEmpty()) ? safeStr(hr.data[0].rowData[1]) : 'Moderate';

                Map<String, Decimal> targets = TARGET_ALLOCATIONS.containsKey(riskProfile)
                    ? TARGET_ALLOCATIONS.get(riskProfile)
                    : TARGET_ALLOCATIONS.get('Moderate');

                // Get accounts
                ConnectApi.CdpQueryInput aq = new ConnectApi.CdpQueryInput();
                aq.sql = 'SELECT Name__c, Type_c__c, Balance_c__c, Allocation_c__c FROM WA_Financial_Account_c_Home__dlm ' +
                    'WHERE Client_c__c = \'' + String.escapeSingleQuotes(clientId) + '\'';
                ConnectApi.CdpQueryOutputV2 ar = ConnectApi.CdpQuery.queryAnsiSqlV2(aq);

                String analysis = 'Rebalancing Analysis: ' + clientName2
                    + '\nHousehold: ' + hhName
                    + '\nRisk Profile: ' + riskProfile
                    + '\nTarget Allocation: ' + targets.get('Equity') + '% Equity / ' + targets.get('Fixed') + '% Fixed / ' + targets.get('Cash') + '% Cash';

                Boolean needsRebalancing = false;
                Integer flagCount = 0;

                if (ar.data != null && !ar.data.isEmpty()) {
                    analysis += '\n\nAccount Analysis:';
                    for (ConnectApi.CdpQueryV2Row row : ar.data) {
                        String acctName = safeStr(row.rowData[0]);
                        String acctType = safeStr(row.rowData[1]);
                        String allocation = safeStr(row.rowData[3]);

                        analysis += '\n\n  ' + acctName + ' (' + acctType + ')';
                        analysis += '\n    Current: ' + allocation;

                        // Parse allocation string
                        Map<String, Decimal> current = parseAllocation(allocation);
                        Boolean acctNeedsRebal = false;

                        for (String component : new List<String>{'Equity', 'Fixed', 'Cash'}) {
                            Decimal currentPct = current.containsKey(component) ? current.get(component) : 0;
                            Decimal targetPct = targets.get(component);
                            Decimal drift = currentPct - targetPct;

                            String driftStr = (drift >= 0 ? '+' : '') + drift.setScale(0) + '%';
                            String status = (Math.abs(drift) > 5) ? ' ⚠️ DRIFT' : ' ✓';

                            if (Math.abs(drift) > 5) {
                                acctNeedsRebal = true;
                                needsRebalancing = true;
                                flagCount++;
                            }

                            analysis += '\n    ' + component + ': ' + currentPct.setScale(0) + '% (target ' + targetPct.setScale(0) + '%, drift ' + driftStr + ')' + status;
                        }

                        analysis += '\n    Status: ' + (acctNeedsRebal ? '🔴 REBALANCING NEEDED' : '🟢 Within tolerance');
                    }
                } else {
                    analysis += '\n\nNo accounts found for this client.';
                }

                analysis += '\n\n=== SUMMARY ==='
                    + '\nOverall: ' + (needsRebalancing ? '🔴 REBALANCING RECOMMENDED (' + flagCount + ' drift flags)' : '🟢 ALL ACCOUNTS WITHIN TOLERANCE')
                    + '\nDrift Threshold: >5% from target';

                output.rebalancingAnalysis = analysis;
            } catch (Exception e) {
                output.rebalancingAnalysis = 'I was unable to perform the rebalancing analysis. Please try again or check the client name.';
            }

            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                DC_AuditLogAction.logInteraction(
                    'WA_P1to5_Advisor',
                    'rebalancing_alerts',
                    'check_rebalancing',
                    inputs[i].clientName,
                    outputs[i].rebalancingAnalysis,
                    inputs[i].clientName
                );
            } catch (Exception auditEx) {
                // Don't fail the action if audit logging fails
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        return outputs;
    }

    private static Map<String, Decimal> parseAllocation(String allocation) {
        Map<String, Decimal> result = new Map<String, Decimal>();
        if (String.isBlank(allocation)) return result;

        // Parse "60% Equity / 30% Fixed / 10% Cash" format
        List<String> parts = allocation.split('/');
        for (String part : parts) {
            part = part.trim();
            // Extract percentage and label
            Pattern p = Pattern.compile('(\\d+)%?\\s*(\\w+)');
            Matcher m = p.matcher(part);
            if (m.find()) {
                Decimal pct = Decimal.valueOf(m.group(1));
                String label = m.group(2);
                if (label.equalsIgnoreCase('Equity') || label.equalsIgnoreCase('Stock') || label.equalsIgnoreCase('Stocks')) {
                    result.put('Equity', pct);
                } else if (label.equalsIgnoreCase('Fixed') || label.equalsIgnoreCase('Bond') || label.equalsIgnoreCase('Bonds')) {
                    result.put('Fixed', pct);
                } else if (label.equalsIgnoreCase('Cash') || label.equalsIgnoreCase('Money')) {
                    result.put('Cash', pct);
                }
            }
        }
        return result;
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
