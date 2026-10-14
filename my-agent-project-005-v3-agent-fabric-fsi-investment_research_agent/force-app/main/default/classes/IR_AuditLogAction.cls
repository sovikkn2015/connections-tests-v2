public with sharing class IR_AuditLogAction {

    public class LogInput {
        @InvocableVariable(label='Agent Name' description='Name of the agent performing the action' required=true)
        public String agentName;

        @InvocableVariable(label='Action' description='The action being performed' required=true)
        public String action;

        @InvocableVariable(label='Query' description='The original user query')
        public String query;

        @InvocableVariable(label='Analyst' description='Name of the analyst')
        public String analyst;

        @InvocableVariable(label='Data Sources' description='Comma-separated list of data sources used')
        public String dataSources;
    }

    public class LogOutput {
        @InvocableVariable(label='Log Id' description='The Id of the created audit log record')
        public String logId;
    }

    @InvocableMethod(
        label='Log Agent Interaction'
        description='Logs an agent interaction to the audit trail for compliance'
    )
    public static List<LogOutput> logAgentInteraction(List<LogInput> inputs) {
        List<LogOutput> outputs = new List<LogOutput>();

        for (LogInput input : inputs) {
            LogOutput output = new LogOutput();
            try {
                IR_Audit_Log__c log = new IR_Audit_Log__c(
                    Agent__c = safeStr(input.agentName),
                    Action__c = safeStr(input.action),
                    Query__c = safeStr(input.query),
                    Analyst__c = safeStr(input.analyst),
                    Data_Sources_Used__c = safeStr(input.dataSources),
                    Timestamp__c = DateTime.now(),
                    Platform__c = 'Salesforce'
                );
                insert log;
                output.logId = log.Id;
            } catch (Exception e) {
                output.logId = 'Error: Unable to create audit log entry. Please contact your administrator.';
            }
            outputs.add(output);
        }

        return outputs;
    }

    /**
     * Static helper method for other actions to log interactions programmatically.
     * Uses @future to avoid blocking callouts in the same transaction.
     */
    @future
    public static void logInteraction(
        String agent,
        String action,
        String query,
        String analyst,
        String dataSources,
        String traceId,
        String platform,
        Long durationMs
    ) {
        try {
            IR_Audit_Log__c log = new IR_Audit_Log__c(
                Agent__c = safeStr(agent),
                Action__c = safeStr(action),
                Query__c = safeStr(query),
                Analyst__c = safeStr(analyst),
                Data_Sources_Used__c = safeStr(dataSources),
                Trace_Id__c = safeStr(traceId),
                Platform__c = String.isNotBlank(platform) ? platform : 'Salesforce',
                Duration_Ms__c = durationMs,
                Timestamp__c = DateTime.now()
            );
            insert log;
        } catch (Exception e) {
            System.debug('Audit log failed: ' + e.getMessage());
        }
    }

    private static String safeStr(String value) {
        return String.isNotBlank(value) ? value.trim() : '';
    }
}
