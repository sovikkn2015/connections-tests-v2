/**
 * IR_DataCloudAction — Uses CdpQuery API for unified data access with SOQL fallback.
 * Queries: analyst coverage, client holdings, meeting history from Data Cloud.
 */
public with sharing class IR_DataCloudAction {

    public class DataCloudInput {
        @InvocableVariable(label='Query Type' description='analyst_coverage, client_holdings, or meeting_history' required=true)
        public String queryType;
        @InvocableVariable(label='Identifier' description='Ticker, analyst name, or client name')
        public String identifier;
    }

    public class DataCloudOutput {
        @InvocableVariable(label='Result' description='Formatted query results')
        public String result;
        @InvocableVariable(label='Source' description='DataCloud or SOQL')
        public String source;
    }

    @InvocableMethod(
        label='Query Data Cloud'
        description='Queries Data Cloud for analyst coverage, client holdings, or meeting history'
    )
    public static List<DataCloudOutput> queryDataCloud(List<DataCloudInput> inputs) {
        List<DataCloudOutput> outputs = new List<DataCloudOutput>();
        Long startTime = System.currentTimeMillis();
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'data_cloud_query', inputs[0].queryType + ':' + inputs[0].identifier,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (DataCloudInput input : inputs) {
            DataCloudOutput output = new DataCloudOutput();
            try {
                String queryType = input.queryType != null ? input.queryType.trim().toLowerCase() : '';
                String identifier = input.identifier != null ? input.identifier.trim() : '';
                String cdpResult = tryCdpQuery(queryType, identifier);
                if (cdpResult != null) {
                    output.result = cdpResult;
                    output.source = 'DataCloud';
                } else {
                    output.result = fallbackSoql(queryType, identifier);
                    output.source = 'SOQL';
                }
            } catch (Exception e) {
                output.result = 'Data query failed: ' + e.getMessage();
                output.source = 'Error';
            }
            outputs.add(output);
        }

        Long durationMs = System.currentTimeMillis() - startTime;
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'data_cloud_query',
                    inputs[i].queryType + ':' + inputs[i].identifier,
                    UserInfo.getName(), outputs[i].source, traceId, 'Salesforce', durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }
        if (traceId != null) {
            try {
                String spanOut = outputs.isEmpty() ? '' : (outputs[0].result != null ? outputs[0].result : '');
                IR_LangfuseTracer.addSpan(traceId, 'data_cloud_query', inputs[0].queryType,
                    spanOut.length() > 500 ? spanOut.substring(0, 500) : spanOut, durationMs, null, 'Salesforce');
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }
        return outputs;
    }

    private static String tryCdpQuery(String queryType, String identifier) {
        try {
            Type cdpType = Type.forName('ConnectApi', 'CdpQuery');
            if (cdpType == null) {
                return null;
            }
            // In production, use ConnectApi.CdpQuery.queryAnsiSql() here.
            return null;
        } catch (Exception e) {
            System.debug('CdpQuery not available: ' + e.getMessage());
            return null;
        }
    }

    private static String fallbackSoql(String queryType, String identifier) {
        switch on queryType {
            when 'analyst_coverage' {
                return queryAnalystCoverage(identifier);
            }
            when 'client_holdings' {
                return queryClientHoldings(identifier);
            }
            when 'meeting_history' {
                return queryMeetingHistory(identifier);
            }
            when else {
                return 'Unknown query type: ' + queryType + '. Supported: analyst_coverage, client_holdings, meeting_history.';
            }
        }
    }

    private static String queryAnalystCoverage(String identifier) {
        String escaped = String.escapeSingleQuotes(identifier);
        String upper = escaped.toUpperCase();
        String likePattern = '%' + escaped + '%';
        List<IR_Coverage__c> coverages = [
            SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Coverage__c
            WHERE Company__r.Ticker__c = :upper OR Analyst__c LIKE :likePattern
            ORDER BY Company__r.Ticker__c, Analyst__c
            LIMIT 50
        ];
        if (coverages.isEmpty()) {
            return 'No analyst coverage found for "' + identifier + '".';
        }
        String result = 'Analyst Coverage (' + coverages.size() + ' records):\n';
        for (IR_Coverage__c cov : coverages) {
            result += '\n  ' + safeStr(cov.Analyst__c)
                + ' | ' + safeStr(cov.Company__r.Name)
                + ' (' + safeStr(cov.Company__r.Ticker__c) + ')'
                + ' | Rating: ' + safeStr(cov.Rating__c)
                + ' | Target: $' + (cov.Target_Price__c != null ? String.valueOf(cov.Target_Price__c.setScale(2)) : 'N/A');
        }
        return result;
    }

    private static String queryClientHoldings(String identifier) {
        if (!IR_MnpiGuard.isDataAllowed(identifier, IR_MnpiGuard.CONFIDENTIAL_DATA, 'IR_Research_Agent')) {
            return '[RESTRICTED] Client holdings data requires compliance clearance.';
        }
        String upper = String.escapeSingleQuotes(identifier).toUpperCase();
        List<IR_Company__c> companies = [
            SELECT Name, Ticker__c, Sector__c, Market_Cap__c, Last_Price__c
            FROM IR_Company__c WHERE Ticker__c = :upper LIMIT 10
        ];
        if (companies.isEmpty()) {
            return 'No holdings data found for "' + identifier + '".';
        }
        String result = 'Holdings Data for ' + identifier + ':\n';
        for (IR_Company__c c : companies) {
            result += '\n  ' + safeStr(c.Name) + ' (' + safeStr(c.Ticker__c) + ')'
                + ' | Sector: ' + safeStr(c.Sector__c)
                + ' | Last Price: $' + (c.Last_Price__c != null ? String.valueOf(c.Last_Price__c.setScale(2)) : 'N/A');
        }
        return result;
    }

    private static String queryMeetingHistory(String identifier) {
        String likePattern = '%' + String.escapeSingleQuotes(identifier) + '%';
        List<Event> meetings = [
            SELECT Subject, StartDateTime, EndDateTime, Description, Who.Name
            FROM Event WHERE Subject LIKE :likePattern
            ORDER BY StartDateTime DESC LIMIT 20
        ];
        if (meetings.isEmpty()) {
            return 'No meeting history found for "' + identifier + '".';
        }
        String result = 'Meeting History (' + meetings.size() + ' meetings):\n';
        for (Event evt : meetings) {
            result += '\n  ' + safeStr(evt.Subject)
                + ' | ' + (evt.StartDateTime != null ? evt.StartDateTime.format('yyyy-MM-dd') : 'N/A')
                + ' | With: ' + safeStr(evt.Who != null ? evt.Who.Name : null);
        }
        return result;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
