/**
 * IR_MnpiGuard — Utility class that enforces MNPI (Material Non-Public Information) isolation.
 *
 * Data classifications:
 *   PUBLIC       — freely shareable, can cross platform boundaries
 *   INTERNAL     — internal use only, can be sent to AWS with audit trail
 *   CONFIDENTIAL — never crosses platform boundary (never sent to AWS)
 *   RESTRICTED   — only accessible by compliance role, never leaves Salesforce
 *
 * Used by:
 *   - IR_McpServerEndpoint to filter data before returning to external callers
 *   - IR_ResearchBriefAction to ensure MNPI data stays in Salesforce
 *   - IR_ComplianceScreeningAction for MNPI flag checks
 */
public with sharing class IR_MnpiGuard {

    public static final String PUBLIC_DATA = 'PUBLIC';
    public static final String INTERNAL_DATA = 'INTERNAL';
    public static final String CONFIDENTIAL_DATA = 'CONFIDENTIAL';
    public static final String RESTRICTED_DATA = 'RESTRICTED';

    private static final Set<String> VALID_CLASSIFICATIONS = new Set<String>{
        PUBLIC_DATA, INTERNAL_DATA, CONFIDENTIAL_DATA, RESTRICTED_DATA
    };

    private static final String COMPLIANCE_PERMISSION = 'IR_Compliance_Access';

    /**
     * Determines whether data of a given classification is allowed for the requesting agent.
     */
    public static Boolean isDataAllowed(String ticker, String dataClassification, String requestingAgent) {
        if (String.isBlank(dataClassification)) {
            return false;
        }
        String classification = dataClassification.toUpperCase().trim();
        if (!VALID_CLASSIFICATIONS.contains(classification)) {
            return false;
        }

        Boolean isExternalCaller = isExternalAgent(requestingAgent);
        Boolean hasComplianceRole = hasComplianceAccess();

        if (classification == PUBLIC_DATA) {
            return true;
        }
        if (classification == INTERNAL_DATA) {
            return true;
        }
        if (classification == CONFIDENTIAL_DATA) {
            if (isExternalCaller) {
                logMnpiBlock(ticker, classification, requestingAgent,
                    'CONFIDENTIAL data cannot cross platform boundary');
                return false;
            }
            return true;
        }
        if (classification == RESTRICTED_DATA) {
            if (isExternalCaller) {
                logMnpiBlock(ticker, classification, requestingAgent,
                    'RESTRICTED data cannot leave Salesforce');
                return false;
            }
            if (!hasComplianceRole) {
                logMnpiBlock(ticker, classification, requestingAgent,
                    'RESTRICTED data requires compliance role');
                return false;
            }
            return true;
        }
        return false;
    }

    /**
     * Check if a ticker has any active MNPI flags in the audit log.
     */
    public static Boolean hasActiveMnpiFlags(String ticker) {
        if (String.isBlank(ticker)) {
            return false;
        }
        DateTime cutoff = DateTime.now().addDays(-30);
        String upperTicker = ticker.toUpperCase();
        // Query__c is LongTextArea (not filterable). Use Action__c + Timestamp__c filter,
        // then check Query__c in Apex.
        List<IR_Audit_Log__c> candidates = [
            SELECT Id, Query__c
            FROM IR_Audit_Log__c
            WHERE Action__c = 'mnpi_flag'
              AND Timestamp__c >= :cutoff
            LIMIT 200
        ];
        List<IR_Audit_Log__c> flags = new List<IR_Audit_Log__c>();
        for (IR_Audit_Log__c c : candidates) {
            if (c.Query__c != null && c.Query__c.toUpperCase().contains(upperTicker)) {
                flags.add(c);
                break;
            }
        }
        return !flags.isEmpty();
    }

    /**
     * Get the data classification for a given data type.
     */
    public static String getClassification(String dataType) {
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

    /**
     * Filter a response based on MNPI rules before sending to external callers.
     */
    public static String filterForExternalCaller(
        String ticker, String dataType, String response, String requestingAgent
    ) {
        String classification = getClassification(dataType);
        if (isDataAllowed(ticker, classification, requestingAgent)) {
            return response;
        }
        return '[REDACTED] This data is classified as ' + classification
            + ' and cannot be shared with external agent: ' + requestingAgent + '.';
    }

    @TestVisible
    private static Boolean isExternalAgent(String requestingAgent) {
        if (String.isBlank(requestingAgent)) {
            return false;
        }
        String agent = requestingAgent.toLowerCase().trim();
        return agent.contains('aws') || agent.contains('bedrock')
            || agent.contains('mcp') || agent.contains('external')
            || agent.contains('lambda');
    }

    @TestVisible
    private static Boolean hasComplianceAccess() {
        try {
            return FeatureManagement.checkPermission(COMPLIANCE_PERMISSION);
        } catch (Exception e) {
            String profileName = [
                SELECT Name FROM Profile WHERE Id = :UserInfo.getProfileId() LIMIT 1
            ].Name;
            return profileName != null && profileName.containsIgnoreCase('Compliance');
        }
    }

    private static void logMnpiBlock(
        String ticker, String classification, String requestingAgent, String reason
    ) {
        try {
            IR_AuditLogAction.logInteraction(
                requestingAgent, 'mnpi_block',
                ticker + ' | ' + classification + ' | ' + reason,
                UserInfo.getName(), 'MNPI Guard', null, 'Salesforce', 0
            );
        } catch (Exception e) {
            System.debug('MNPI block audit log failed: ' + e.getMessage());
        }
    }
}
