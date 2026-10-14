public with sharing class DC_ComplianceCheckAction {

    public class ComplianceInput {
        @InvocableVariable(label='Client Name' description='Name of the client or household to check compliance for' required=true)
        public String clientName;
    }

    public class ComplianceOutput {
        @InvocableVariable(label='Compliance Report' description='Suitability and compliance check results from Data Cloud')
        public String complianceReport;
    }

    private static final Map<String, Map<String, Decimal>> TARGET_ALLOCATIONS = new Map<String, Map<String, Decimal>>{
        'Conservative' => new Map<String, Decimal>{'Equity' => 30, 'Fixed' => 60, 'Cash' => 10},
        'Moderate' => new Map<String, Decimal>{'Equity' => 55, 'Fixed' => 35, 'Cash' => 10},
        'Growth' => new Map<String, Decimal>{'Equity' => 70, 'Fixed' => 20, 'Cash' => 10},
        'Aggressive' => new Map<String, Decimal>{'Equity' => 80, 'Fixed' => 15, 'Cash' => 5}
    };

    @InvocableMethod(
        label='Run Compliance Check (Data Cloud)'
        description='Checks suitability, concentration risk, and allocation compliance from Data Cloud'
    )
    public static List<ComplianceOutput> runComplianceCheck(List<ComplianceInput> inputs) {
        List<ComplianceOutput> outputs = new List<ComplianceOutput>();

        for (ComplianceInput input : inputs) {
            ComplianceOutput output = new ComplianceOutput();
            try {
                String cleanName = cleanClientName(input.clientName);

                // Find client
                ConnectApi.CdpQueryInput cq = new ConnectApi.CdpQueryInput();
                cq.sql = 'SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm ' +
                    'WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                ConnectApi.CdpQueryOutputV2 cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);

                // Fallback: try household name to find a client
                if (cr.data == null || cr.data.isEmpty()) {
                    ConnectApi.CdpQueryInput hq2 = new ConnectApi.CdpQueryInput();
                    hq2.sql = 'SELECT Id__c FROM WA_Household_c_Home__dlm WHERE Name__c LIKE \'%' + String.escapeSingleQuotes(cleanName) + '%\' LIMIT 1';
                    ConnectApi.CdpQueryOutputV2 hr2 = ConnectApi.CdpQuery.queryAnsiSqlV2(hq2);
                    if (hr2.data != null && !hr2.data.isEmpty()) {
                        String tmpHhId = safeStr(hr2.data[0].rowData[0]);
                        cq.sql = 'SELECT Id__c, Name__c, Household_c__c FROM WA_Client_c_Home__dlm WHERE Household_c__c = \'' + String.escapeSingleQuotes(tmpHhId) + '\' LIMIT 1';
                        cr = ConnectApi.CdpQuery.queryAnsiSqlV2(cq);
                    }
                }

                // Fallback: try name parts
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
                    output.complianceReport = 'No client found matching "' + input.clientName + '".';
                    outputs.add(output);
                    continue;
                }

                String clientId = safeStr(cr.data[0].rowData[0]);
                String clientName2 = safeStr(cr.data[0].rowData[1]);
                String hhId = safeStr(cr.data[0].rowData[2]);

                // Get household risk profile
                ConnectApi.CdpQueryInput hq = new ConnectApi.CdpQueryInput();
                hq.sql = 'SELECT Name__c, Risk_Profile_c__c FROM WA_Household_c_Home__dlm WHERE Id__c = \'' + String.escapeSingleQuotes(hhId) + '\'';
                ConnectApi.CdpQueryOutputV2 hr = ConnectApi.CdpQuery.queryAnsiSqlV2(hq);

                String hhName = (hr.data != null && !hr.data.isEmpty()) ? safeStr(hr.data[0].rowData[0]) : 'Unknown';
                String riskProfile = (hr.data != null && !hr.data.isEmpty()) ? safeStr(hr.data[0].rowData[1]) : 'Moderate';

                Map<String, Decimal> targets = TARGET_ALLOCATIONS.containsKey(riskProfile)
                    ? TARGET_ALLOCATIONS.get(riskProfile)
                    : TARGET_ALLOCATIONS.get('Moderate');

                // Get all accounts for clients in this household
                ConnectApi.CdpQueryInput aq = new ConnectApi.CdpQueryInput();
                aq.sql = 'SELECT Name__c, Type_c__c, Balance_c__c, Allocation_c__c FROM WA_Financial_Account_c_Home__dlm ' +
                    'WHERE Client_c__c IN (SELECT Id__c FROM WA_Client_c_Home__dlm WHERE Household_c__c = \'' + String.escapeSingleQuotes(hhId) + '\')';
                ConnectApi.CdpQueryOutputV2 ar = ConnectApi.CdpQuery.queryAnsiSqlV2(aq);

                String report = '=== COMPLIANCE CHECK ==='
                    + '\nHousehold: ' + hhName
                    + '\nRisk Profile: ' + riskProfile
                    + '\nTarget: ' + targets.get('Equity').setScale(0) + '% Equity / ' + targets.get('Fixed').setScale(0) + '% Fixed / ' + targets.get('Cash').setScale(0) + '% Cash';

                List<String> violations = new List<String>();
                Boolean overallPass = true;

                if (ar.data != null && !ar.data.isEmpty()) {
                    report += '\n\nAccount Checks:';
                    for (ConnectApi.CdpQueryV2Row row : ar.data) {
                        String acctName = safeStr(row.rowData[0]);
                        String allocation = safeStr(row.rowData[3]);
                        Map<String, Decimal> current = parseAllocation(allocation);

                        report += '\n\n  ' + acctName + ' (' + safeStr(row.rowData[1]) + ')';
                        report += '\n    Allocation: ' + allocation;

                        // Check 1: Suitability — is allocation appropriate for risk profile?
                        Decimal equityPct = current.containsKey('Equity') ? current.get('Equity') : 0;
                        if (riskProfile == 'Conservative' && equityPct > 50) {
                            String v = acctName + ': Equity at ' + equityPct.setScale(0) + '% exceeds conservative limit (50% max)';
                            violations.add(v);
                            report += '\n    ⚠️ SUITABILITY: ' + v;
                            overallPass = false;
                        } else if (riskProfile == 'Moderate' && equityPct > 70) {
                            String v = acctName + ': Equity at ' + equityPct.setScale(0) + '% exceeds moderate limit (70% max)';
                            violations.add(v);
                            report += '\n    ⚠️ SUITABILITY: ' + v;
                            overallPass = false;
                        }

                        // Check 2: Concentration risk — any single component >80%
                        for (String component : current.keySet()) {
                            if (current.get(component) > 80) {
                                String v = acctName + ': ' + component + ' concentration at ' + current.get(component).setScale(0) + '% (>80% threshold)';
                                violations.add(v);
                                report += '\n    ⚠️ CONCENTRATION: ' + v;
                                overallPass = false;
                            }
                        }

                        // Check 3: Drift from target
                        for (String component : new List<String>{'Equity', 'Fixed', 'Cash'}) {
                            Decimal currentPct = current.containsKey(component) ? current.get(component) : 0;
                            Decimal targetPct = targets.get(component);
                            Decimal drift = Math.abs(currentPct - targetPct);
                            if (drift > 15) {
                                String v = acctName + ': ' + component + ' drift of ' + drift.setScale(0) + '% from target (>15% threshold)';
                                violations.add(v);
                                report += '\n    ⚠️ DRIFT: ' + v;
                                overallPass = false;
                            }
                        }

                        if (overallPass || !report.contains('⚠️')) {
                            report += '\n    ✓ Compliant';
                        }
                    }
                }

                report += '\n\n=== RESULT ==='
                    + '\nStatus: ' + (overallPass ? '✅ PASS — All accounts compliant' : '❌ FAIL — ' + violations.size() + ' violation(s) found');

                if (!violations.isEmpty()) {
                    report += '\n\nViolations:';
                    for (Integer i = 0; i < violations.size(); i++) {
                        report += '\n  ' + (i + 1) + '. ' + violations[i];
                    }
                }

                output.complianceReport = report;
            } catch (Exception e) {
                output.complianceReport = 'I was unable to run the compliance check. Please try again or check the client name.';
            }

            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                DC_AuditLogAction.logInteraction(
                    'WA_P1to5_Advisor',
                    'compliance_check',
                    'run_compliance',
                    inputs[i].clientName,
                    outputs[i].complianceReport,
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
        List<String> parts = allocation.split('/');
        for (String part : parts) {
            part = part.trim();
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
