/**
 * IR_MnpiCheckAction — InvocableMethod for MNPI checks.
 * Used by the IR_Compliance_Agent to check MNPI flags and data access permissions.
 */
public with sharing class IR_MnpiCheckAction {

    public class MnpiInput {
        @InvocableVariable(label='Ticker' description='Stock ticker to check for MNPI flags' required=true)
        public String ticker;
        @InvocableVariable(label='Data Type' description='Type of data being accessed (e.g., holdings, company_info)')
        public String dataType;
        @InvocableVariable(label='Requesting Agent' description='Agent or system requesting the data')
        public String requestingAgent;
    }

    public class MnpiOutput {
        @InvocableVariable(label='MNPI Result' description='Formatted MNPI check result')
        public String mnpiResult;
        @InvocableVariable(label='Is Allowed' description='Whether data access is permitted')
        public Boolean isAllowed;
        @InvocableVariable(label='Classification' description='Data classification level')
        public String classification;
    }

    @InvocableMethod(
        label='Check MNPI Status'
        description='Checks MNPI flags and data access permissions for a ticker'
    )
    public static List<MnpiOutput> checkMnpi(List<MnpiInput> inputs) {
        List<MnpiOutput> outputs = new List<MnpiOutput>();
        Long startTime = System.currentTimeMillis();
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'mnpi_check', inputs[0].ticker,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Compliance_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (MnpiInput input : inputs) {
            MnpiOutput output = new MnpiOutput();
            try {
                String ticker = input.ticker != null ? input.ticker.trim().toUpperCase() : '';
                String dataType = input.dataType != null ? input.dataType.trim() : 'company_info';
                String agent = input.requestingAgent != null ? input.requestingAgent.trim() : 'IR_Research_Agent';

                if (String.isBlank(ticker)) {
                    output.mnpiResult = 'No ticker provided for MNPI check.';
                    output.isAllowed = false;
                    output.classification = '';
                    outputs.add(output);
                    continue;
                }

                String classification = IR_MnpiGuard.getClassification(dataType);
                Boolean hasFlags = IR_MnpiGuard.hasActiveMnpiFlags(ticker);
                Boolean allowed = IR_MnpiGuard.isDataAllowed(ticker, classification, agent);

                String report = '=== MNPI CHECK REPORT ===';
                report += '\nTicker: ' + ticker;
                report += '\nData Type: ' + dataType;
                report += '\nClassification: ' + classification;
                report += '\nRequesting Agent: ' + agent;
                report += '\nActive MNPI Flags: ' + (hasFlags ? 'YES' : 'None');
                report += '\n\n--- ACCESS DECISION ---';

                if (hasFlags) {
                    report += '\n  WARNING — Active MNPI flags detected for ' + ticker + '.';
                    report += '\n  Enhanced restrictions apply. Compliance review required.';
                    if (classification == IR_MnpiGuard.PUBLIC_DATA) {
                        report += '\n  Public data access: PERMITTED (with MNPI awareness).';
                        allowed = true;
                    } else {
                        report += '\n  Non-public data access: BLOCKED pending compliance clearance.';
                        allowed = false;
                    }
                }

                if (allowed) {
                    report += '\n\n PERMITTED — Data access allowed for ' + dataType + ' (' + classification + ').';
                } else {
                    report += '\n\n BLOCKED — Data access denied. Classification: ' + classification + '.';
                }

                output.mnpiResult = report;
                output.isAllowed = allowed;
                output.classification = classification;
            } catch (Exception e) {
                output.mnpiResult = 'MNPI check failed: ' + e.getMessage();
                output.isAllowed = false;
                output.classification = '';
            }
            outputs.add(output);
        }

        Long durationMs = System.currentTimeMillis() - startTime;
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Compliance_Agent', 'mnpi_check', inputs[i].ticker,
                    UserInfo.getName(), 'MNPI Guard', traceId, 'Salesforce', durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        if (traceId != null) {
            try {
                String spanOut = outputs.isEmpty() ? '' : (outputs[0].mnpiResult != null ? outputs[0].mnpiResult : '');
                IR_LangfuseTracer.addSpan(
                    traceId, 'check_mnpi', inputs[0].ticker,
                    spanOut.length() > 500 ? spanOut.substring(0, 500) : spanOut,
                    durationMs, null, 'Salesforce'
                );
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }

        return outputs;
    }
}
