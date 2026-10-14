/**
 * DC_AuditLogAction — Logs agent interactions to WA_Audit_Log__c for SEC/FINRA compliance.
 *
 * Callable from:
 *   - Agent actions (via @InvocableMethod)
 *   - Flows (via the same invocable interface)
 *   - Other Apex classes (via the static logInteraction helper)
 *
 * Each log entry captures: who asked, what topic, which action ran,
 * the original query, a summary of the response, and which client
 * data was accessed.
 */
public with sharing class DC_AuditLogAction {

    // ── Invocable Input ──────────────────────────────────────────
    public class AuditInput {
        @InvocableVariable(label='Agent Name' description='Name of the agent' required=true)
        public String agentName;

        @InvocableVariable(label='Topic' description='Agent topic that handled the request' required=false)
        public String topic;

        @InvocableVariable(label='Action' description='Action/method that was executed' required=false)
        public String action;

        @InvocableVariable(label='Query' description='Original user query' required=true)
        public String query;

        @InvocableVariable(label='Response Summary' description='Summary of the agent response' required=false)
        public String responseSummary;

        @InvocableVariable(label='Client Accessed' description='Client or household name accessed' required=false)
        public String clientAccessed;
    }

    // ── Invocable Output ─────────────────────────────────────────
    public class AuditOutput {
        @InvocableVariable(label='Log Id' description='Id of the created audit log record')
        public String logId;

        @InvocableVariable(label='Status' description='Success or error message')
        public String status;
    }

    // ── Invocable Entry Point ────────────────────────────────────
    @InvocableMethod(
        label='Log Agent Interaction'
        description='Creates an audit log record for an agent interaction. Required for SEC/FINRA compliance tracking.'
    )
    public static List<AuditOutput> logInteractions(List<AuditInput> inputs) {
        List<AuditOutput> outputs = new List<AuditOutput>();
        List<WA_Audit_Log__c> logsToInsert = new List<WA_Audit_Log__c>();

        for (AuditInput input : inputs) {
            WA_Audit_Log__c log = new WA_Audit_Log__c();
            log.Agent_Name__c      = input.agentName;
            log.User__c            = UserInfo.getName();
            log.Topic__c           = input.topic;
            log.Action__c          = input.action;
            log.Query__c           = input.query;
            log.Response_Summary__c = truncate(input.responseSummary, 32768);
            log.Client_Accessed__c = input.clientAccessed;
            log.Timestamp__c       = Datetime.now();
            log.Session_Id__c      = UserInfo.getSessionId();
            logsToInsert.add(log);
        }

        try {
            insert logsToInsert;
            for (WA_Audit_Log__c log : logsToInsert) {
                AuditOutput output = new AuditOutput();
                output.logId  = log.Id;
                output.status = 'Success';
                outputs.add(output);
            }
        } catch (DmlException e) {
            for (AuditInput input : inputs) {
                AuditOutput output = new AuditOutput();
                output.logId  = null;
                output.status = 'Error: ' + e.getMessage();
                outputs.add(output);
            }
        }

        return outputs;
    }

    // ── Static Helper (callable from other Apex) ─────────────────
    public static Id logInteraction(
        String agentName,
        String topic,
        String action,
        String query,
        String responseSummary,
        String clientAccessed
    ) {
        WA_Audit_Log__c log = new WA_Audit_Log__c();
        log.Agent_Name__c      = agentName;
        log.User__c            = UserInfo.getName();
        log.Topic__c           = topic;
        log.Action__c          = action;
        log.Query__c           = query;
        log.Response_Summary__c = truncate(responseSummary, 32768);
        log.Client_Accessed__c = clientAccessed;
        log.Timestamp__c       = Datetime.now();
        log.Session_Id__c      = UserInfo.getSessionId();
        insert log;
        return log.Id;
    }

    // ── Utility ──────────────────────────────────────────────────
    private static String truncate(String value, Integer maxLength) {
        if (value == null) return null;
        return value.length() > maxLength ? value.substring(0, maxLength) : value;
    }
}