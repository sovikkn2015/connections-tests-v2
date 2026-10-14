/**
 * IR_ComplianceAgentAction — Delegates compliance screening to the separate IR_Compliance_Agent.
 * Used by the main IR_Research_Agent's compliance_screening topic.
 */
public with sharing class IR_ComplianceAgentAction {

    public class ComplianceInput {
        @InvocableVariable(label='Ticker' description='Stock ticker to screen' required=true)
        public String ticker;
        @InvocableVariable(label='Check Type' description='all, restricted_list, trading_window, or mnpi (default: all)')
        public String checkType;
    }

    public class ComplianceOutput {
        @InvocableVariable(label='Compliance Result' description='Full compliance screening result')
        public String complianceResult;
        @InvocableVariable(label='Overall Status' description='PASS, FAIL, or FLAGGED')
        public String overallStatus;
    }

    @InvocableMethod(
        label='Run Compliance Agent'
        description='Delegates compliance screening to the separate IR_Compliance_Agent'
    )
    public static List<ComplianceOutput> runComplianceAgent(List<ComplianceInput> inputs) {
        List<ComplianceOutput> outputs = new List<ComplianceOutput>();
        Long startTime = System.currentTimeMillis();
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'compliance_agent_delegation', inputs[0].ticker,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent',
                    'delegateTo' => 'IR_Compliance_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (ComplianceInput input : inputs) {
            ComplianceOutput output = new ComplianceOutput();
            try {
                String ticker = input.ticker != null ? input.ticker.trim().toUpperCase() : '';
                String checkType = input.checkType != null ? input.checkType.trim().toLowerCase() : 'all';
                if (String.isBlank(ticker)) {
                    output.complianceResult = 'No ticker provided for compliance screening.';
                    output.overallStatus = 'FAIL';
                    outputs.add(output);
                    continue;
                }
                // Try ConnectApi to invoke the Compliance Agent
                String agentResult = tryConnectApiComplianceAgent(ticker, checkType);
                // Fallback: direct Apex routing
                if (agentResult == null) {
                    agentResult = runDirectCompliance(ticker, checkType);
                }
                output.complianceResult = agentResult;
                output.overallStatus = deriveStatus(agentResult);
            } catch (Exception e) {
                output.complianceResult = 'Compliance agent delegation failed: ' + e.getMessage();
                output.overallStatus = 'FAIL';
            }
            outputs.add(output);
        }

        Long durationMs = System.currentTimeMillis() - startTime;
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'compliance_agent_delegation', inputs[i].ticker,
                    UserInfo.getName(), 'IR_Compliance_Agent', traceId, 'Salesforce', durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }
        if (traceId != null) {
            try {
                String spanOut = outputs.isEmpty() ? '' : (outputs[0].complianceResult != null ? outputs[0].complianceResult : '');
                IR_LangfuseTracer.addSpan(traceId, 'compliance_agent_delegation', inputs[0].ticker,
                    spanOut.length() > 500 ? spanOut.substring(0, 500) : spanOut, durationMs, null, 'Salesforce');
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }
        return outputs;
    }

    private static String tryConnectApiComplianceAgent(String ticker, String checkType) {
        try {
            Type copilotType = Type.forName('ConnectApi', 'CopilotService');
            if (copilotType == null) {
                return null;
            }
            // In production: invoke IR_Compliance_Agent via ConnectApi.CopilotService
            return null;
        } catch (Exception e) {
            System.debug('ConnectApi not available for Compliance Agent: ' + e.getMessage());
            return null;
        }
    }

    private static String runDirectCompliance(String ticker, String checkType) {
        String fullReport = '';

        if (checkType == 'all' || checkType == 'restricted_list' || checkType == 'trading_window') {
            IR_ComplianceScreeningAction.ScreeningInput screenInput = new IR_ComplianceScreeningAction.ScreeningInput();
            screenInput.ticker = ticker;
            List<IR_ComplianceScreeningAction.ScreeningOutput> screenOutputs =
                IR_ComplianceScreeningAction.checkCompliance(
                    new List<IR_ComplianceScreeningAction.ScreeningInput>{ screenInput }
                );
            if (!screenOutputs.isEmpty() && screenOutputs[0].complianceResult != null) {
                fullReport += screenOutputs[0].complianceResult;
            }
        }

        if (checkType == 'all' || checkType == 'mnpi') {
            IR_MnpiCheckAction.MnpiInput mnpiInput = new IR_MnpiCheckAction.MnpiInput();
            mnpiInput.ticker = ticker;
            mnpiInput.dataType = 'company_info';
            mnpiInput.requestingAgent = 'IR_Research_Agent';
            List<IR_MnpiCheckAction.MnpiOutput> mnpiOutputs =
                IR_MnpiCheckAction.checkMnpi(
                    new List<IR_MnpiCheckAction.MnpiInput>{ mnpiInput }
                );
            if (!mnpiOutputs.isEmpty() && mnpiOutputs[0].mnpiResult != null) {
                if (String.isNotBlank(fullReport)) {
                    fullReport += '\n\n';
                }
                fullReport += mnpiOutputs[0].mnpiResult;
            }
        }

        return String.isNotBlank(fullReport) ? fullReport : 'No compliance checks executed for ' + ticker + '.';
    }

    private static String deriveStatus(String result) {
        if (String.isBlank(result)) {
            return 'FAIL';
        }
        String upper = result.toUpperCase();
        if (upper.contains('BLOCKED') || upper.contains('FAIL') || upper.contains('RESTRICTED')) {
            return 'FAIL';
        }
        if (upper.contains('FLAGGED') || upper.contains('QUIET PERIOD') || upper.contains('WARNING')) {
            return 'FLAGGED';
        }
        return 'PASS';
    }
}
