/**
 * IR_MnpiCheckAction — InvocableMethod for MNPI checks.
 *
 * V3 note: The authoritative MNPI classification + enforcement has moved to the
 * Flex Gateway (agent-fabric/policies/mnpi-filter.yaml). This Apex action is kept
 * for the IR_Compliance_Agent so existing GenAiFunction registrations still work,
 * but it now delegates classification to a local heuristic and reports that the
 * gateway is the source of truth. Output shape (mnpiResult, isAllowed, classification)
 * is unchanged from V2 so the agent topics don't break.
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

    private static final String PUBLIC_DATA = 'PUBLIC';
    private static final String INTERNAL_DATA = 'INTERNAL';
    private static final String CONFIDENTIAL_DATA = 'CONFIDENTIAL';
    private static final String RESTRICTED_DATA = 'RESTRICTED';

    @InvocableMethod(
        label='Check MNPI Status'
        description='Reports MNPI classification for a ticker. Authoritative enforcement lives in the Flex Gateway.'
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

                String classification = classify(dataType);
                Boolean hasFlags = hasLocalMnpiFlags(ticker);
                Boolean allowed = classification == PUBLIC_DATA || classification == INTERNAL_DATA;

                String report = '=== MNPI CHECK REPORT ===';
                report += '\nTicker: ' + ticker;
                report += '\nData Type: ' + dataType;
                report += '\nClassification: ' + classification;
                report += '\nRequesting Agent: ' + agent;
                report += '\nActive MNPI Flags (local audit scan): ' + (hasFlags ? 'YES' : 'None');
                report += '\nAuthoritative policy source: Flex Gateway (mnpi-filter.yaml)';
                report += '\n\n--- ACCESS DECISION ---';

                if (hasFlags) {
                    report += '\n  WARNING — Local audit flag for ' + ticker + ' within last 30 days.';
                    report += '\n  The Flex Gateway will apply enhanced restrictions. Compliance review recommended.';
                    if (classification != PUBLIC_DATA) {
                        allowed = false;
                    }
                }

                if (allowed) {
                    report += '\n\n PERMITTED — Access allowed for ' + dataType + ' (' + classification + ').';
                    report += '\n Final enforcement decision is performed by the Flex Gateway at call time.';
                } else {
                    report += '\n\n BLOCKED — Access denied at report-time. Classification: ' + classification + '.';
                    report += '\n Any actual callout will also be blocked by the Flex Gateway.';
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
                    UserInfo.getName(), 'Flex Gateway policy (reported)', traceId, 'Salesforce', durationMs
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

    // Lightweight classification helper. The Flex Gateway mnpi-filter.yaml holds the
    // authoritative mapping; this mirrors it only for user-facing reporting.
    private static String classify(String dataType) {
        if (String.isBlank(dataType)) {
            return INTERNAL_DATA;
        }
        String dt = dataType.toLowerCase().trim();
        if (dt == 'holdings' || dt == 'client_holdings' || dt == 'portfolio') {
            return CONFIDENTIAL_DATA;
        }
        if (dt == 'mnpi' || dt == 'insider' || dt == 'restricted_list') {
            return RESTRICTED_DATA;
        }
        if (dt == 'company_info' || dt == 'market_data' || dt == 'sec_filings') {
            return PUBLIC_DATA;
        }
        return INTERNAL_DATA;
    }

    private static Boolean hasLocalMnpiFlags(String ticker) {
        if (String.isBlank(ticker)) {
            return false;
        }
        DateTime cutoff = DateTime.now().addDays(-30);
        String upperTicker = ticker.toUpperCase();
        List<IR_Audit_Log__c> candidates = [
            SELECT Id, Query__c
            FROM IR_Audit_Log__c
            WHERE Action__c = 'mnpi_flag'
              AND Timestamp__c >= :cutoff
            LIMIT 200
        ];
        for (IR_Audit_Log__c c : candidates) {
            if (c.Query__c != null && c.Query__c.toUpperCase().contains(upperTicker)) {
                return true;
            }
        }
        return false;
    }
}
