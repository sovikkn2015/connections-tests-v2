public with sharing class IR_WatchlistAction {

    public class WatchlistInput {
        @InvocableVariable(label='Query' description='"all", "high priority", analyst name, or ticker to filter watchlist' required=true)
        public String query;
    }

    public class WatchlistOutput {
        @InvocableVariable(label='Watchlist Info' description='Formatted analyst watchlist — stocks being actively tracked')
        public String watchlistInfo;
    }

    @InvocableMethod(
        label='Get Watchlist'
        description='Returns the analyst watchlist — stocks being actively tracked'
    )
    public static List<WatchlistOutput> getWatchlist(List<WatchlistInput> inputs) {
        List<WatchlistOutput> outputs = new List<WatchlistOutput>();
        Long startTime = System.currentTimeMillis();

        // Langfuse tracing
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'watchlist',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (WatchlistInput input : inputs) {
            WatchlistOutput output = new WatchlistOutput();
            try {
                String searchTerm = input.query != null ? input.query.trim().toLowerCase() : '';
                if (String.isBlank(searchTerm)) {
                    searchTerm = 'all';
                }

                List<IR_Watchlist__c> entries = findWatchlistEntries(searchTerm);

                if (entries.isEmpty()) {
                    output.watchlistInfo = 'No watchlist entries found for "' + input.query + '".';
                    outputs.add(output);
                    continue;
                }

                String info = 'Watchlist';
                if (searchTerm != 'all') {
                    info += ' for "' + input.query + '"';
                }
                info += ' (' + entries.size() + ' entries):\n';

                for (IR_Watchlist__c w : entries) {
                    info += '\n' + safeStr(w.Priority__c)
                        + ' | ' + safeStr(w.Company__r.Name)
                        + ' (' + safeStr(w.Company__r.Ticker__c) + ')'
                        + ' | Analyst: ' + safeStr(w.Analyst__c)
                        + ' | Reason: ' + safeStr(w.Reason__c)
                        + ' | Added: ' + formatDate(w.Added_Date__c);
                }

                output.watchlistInfo = info;
            } catch (Exception e) {
                output.watchlistInfo = 'Unable to retrieve watchlist. Please try again.';
            }
            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'watchlist_check', inputs[i].query,
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
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].watchlistInfo != null ? outputs[0].watchlistInfo : '');
                IR_LangfuseTracer.addSpan(
                    traceId,
                    'get_watchlist',
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

    private static List<IR_Watchlist__c> findWatchlistEntries(String searchTerm) {
        // High priority filter
        if (searchTerm.contains('high') || searchTerm.contains('priority')) {
            return [
                SELECT Priority__c, Analyst__c, Reason__c, Added_Date__c,
                       Company__r.Name, Company__r.Ticker__c
                FROM IR_Watchlist__c
                WHERE Priority__c = 'High'
                ORDER BY Added_Date__c DESC
            ];
        }

        // Ticker match
        String upperTerm = searchTerm.toUpperCase();
        List<IR_Watchlist__c> results = [
            SELECT Priority__c, Analyst__c, Reason__c, Added_Date__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Watchlist__c
            WHERE Company__r.Ticker__c = :upperTerm
            ORDER BY Priority__c, Added_Date__c DESC
        ];
        if (!results.isEmpty()) return results;

        // Analyst name match
        String escaped = String.escapeSingleQuotes(searchTerm);
        String likePattern = '%' + escaped + '%';
        results = [
            SELECT Priority__c, Analyst__c, Reason__c, Added_Date__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Watchlist__c
            WHERE Analyst__c LIKE :likePattern
            ORDER BY Priority__c, Added_Date__c DESC
        ];
        if (!results.isEmpty()) return results;

        // Default: all entries
        return [
            SELECT Priority__c, Analyst__c, Reason__c, Added_Date__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Watchlist__c
            ORDER BY Priority__c, Added_Date__c DESC
        ];
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }

    private static String formatDate(Date d) {
        return d != null ? String.valueOf(d) : 'N/A';
    }
}
