public with sharing class IR_CoverageCheckAction {

    public class CoverageInput {
        @InvocableVariable(label='Query' description='Analyst name, ticker symbol, or sector to search coverage' required=true)
        public String query;
    }

    public class CoverageOutput {
        @InvocableVariable(label='Coverage Info' description='Formatted analyst coverage details')
        public String coverageInfo;
    }

    @InvocableMethod(
        label='Get Coverage Info'
        description='Returns analyst coverage details — who covers what, ratings, and target prices'
    )
    public static List<CoverageOutput> getCoverageInfo(List<CoverageInput> inputs) {
        List<CoverageOutput> outputs = new List<CoverageOutput>();
        Long startTime = System.currentTimeMillis();

        // Langfuse tracing
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'coverage_check',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (CoverageInput input : inputs) {
            CoverageOutput output = new CoverageOutput();
            try {
                String searchTerm = input.query != null ? input.query.trim() : '';
                if (String.isBlank(searchTerm)) {
                    output.coverageInfo = 'Please provide an analyst name, ticker, or sector to search.';
                    outputs.add(output);
                    continue;
                }

                List<IR_Coverage__c> coverages = findCoverage(searchTerm);

                if (coverages.isEmpty()) {
                    output.coverageInfo = 'No coverage found matching "' + searchTerm + '". Try an analyst name, ticker, or sector.';
                    outputs.add(output);
                    continue;
                }

                String info = 'Coverage Results for "' + searchTerm + '":\n';
                info += coverages.size() + ' record(s) found\n';

                for (IR_Coverage__c cov : coverages) {
                    info += '\n' + safeStr(cov.Analyst__c)
                        + ' | ' + safeStr(cov.Company__r.Name)
                        + ' (' + safeStr(cov.Company__r.Ticker__c) + ')'
                        + ' | Rating: ' + safeStr(cov.Rating__c)
                        + ' | Target: ' + formatCurrency(cov.Target_Price__c)
                        + ' | Updated: ' + formatDate(cov.Last_Updated__c);
                }

                output.coverageInfo = info;
            } catch (Exception e) {
                output.coverageInfo = 'Unable to retrieve coverage information. Please try again.';
            }
            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'coverage_check', inputs[i].query,
                    null, 'CRM', null, 'Salesforce',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        // Langfuse span
        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].coverageInfo != null ? outputs[0].coverageInfo : '');
                IR_LangfuseTracer.addSpan(
                    traceId,
                    'get_coverage_info',
                    inputs[0].query,
                    spanOutput.length() > 500 ? spanOutput.substring(0, 500) : spanOutput,
                    System.currentTimeMillis() - startTime,
                    null,
                    'Salesforce'
                );
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }

        return outputs;
    }

    private static List<IR_Coverage__c> findCoverage(String searchTerm) {
        String escaped = String.escapeSingleQuotes(searchTerm);
        String upperTerm = escaped.toUpperCase();

        // Try ticker match first
        List<IR_Coverage__c> results = [
            SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Coverage__c
            WHERE Company__r.Ticker__c = :upperTerm
            ORDER BY Analyst__c
        ];
        if (!results.isEmpty()) return results;

        // Try company name match
        String likePattern = '%' + escaped + '%';
        results = [
            SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Coverage__c
            WHERE Company__r.Name LIKE :likePattern
            ORDER BY Analyst__c
        ];
        if (!results.isEmpty()) return results;

        // Try analyst name match
        results = [
            SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Coverage__c
            WHERE Analyst__c LIKE :likePattern
            ORDER BY Company__r.Ticker__c
        ];
        if (!results.isEmpty()) return results;

        // Try sector match
        results = [
            SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Coverage__c
            WHERE Company__r.Sector__c = :escaped
            ORDER BY Company__r.Ticker__c, Analyst__c
        ];
        return results;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }

    private static String formatCurrency(Decimal value) {
        if (value == null) return 'N/A';
        return '$' + value.setScale(2);
    }

    private static String formatDate(Date d) {
        return d != null ? String.valueOf(d) : 'N/A';
    }
}
