public with sharing class IR_EarningsCalendarAction {

    public class CalendarInput {
        @InvocableVariable(label='Query' description='Ticker, "this month", "next week", or "all" to filter earnings calendar' required=true)
        public String query;
    }

    public class CalendarOutput {
        @InvocableVariable(label='Earnings Calendar' description='Formatted upcoming earnings dates for covered companies')
        public String earningsCalendar;
    }

    @InvocableMethod(
        label='Get Earnings Calendar'
        description='Returns upcoming earnings dates for covered companies'
    )
    public static List<CalendarOutput> getEarningsCalendar(List<CalendarInput> inputs) {
        List<CalendarOutput> outputs = new List<CalendarOutput>();
        Long startTime = System.currentTimeMillis();

        // Langfuse tracing
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'earnings_calendar',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (CalendarInput input : inputs) {
            CalendarOutput output = new CalendarOutput();
            try {
                String searchTerm = input.query != null ? input.query.trim().toLowerCase() : '';
                if (String.isBlank(searchTerm)) {
                    searchTerm = 'all';
                }

                List<IR_Company__c> companies = findEarnings(searchTerm);

                if (companies.isEmpty()) {
                    output.earningsCalendar = 'No upcoming earnings found for "' + input.query + '".';
                    outputs.add(output);
                    continue;
                }

                String cal = 'Earnings Calendar';
                if (searchTerm != 'all') {
                    cal += ' for "' + input.query + '"';
                }
                cal += ':\n';

                for (IR_Company__c c : companies) {
                    Long daysUntil = Date.today().daysBetween(c.Earnings_Date__c);
                    String daysLabel = daysUntil == 0 ? 'TODAY' :
                        (daysUntil == 1 ? 'Tomorrow' : daysUntil + ' days');
                    cal += '\n' + String.valueOf(c.Earnings_Date__c)
                        + ' | ' + safeStr(c.Name)
                        + ' (' + safeStr(c.Ticker__c) + ')'
                        + ' | ' + daysLabel;
                }

                output.earningsCalendar = cal;
            } catch (Exception e) {
                output.earningsCalendar = 'Unable to retrieve earnings calendar. Please try again.';
            }
            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'earnings_calendar', inputs[i].query,
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
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].earningsCalendar != null ? outputs[0].earningsCalendar : '');
                IR_LangfuseTracer.addSpan(
                    traceId,
                    'get_earnings_calendar',
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

    private static List<IR_Company__c> findEarnings(String searchTerm) {
        Date today = Date.today();

        // Specific ticker
        String upperTerm = searchTerm.toUpperCase();
        List<IR_Company__c> results = [
            SELECT Name, Ticker__c, Earnings_Date__c
            FROM IR_Company__c
            WHERE Ticker__c = :upperTerm AND Earnings_Date__c != null
            LIMIT 1
        ];
        if (!results.isEmpty()) return results;

        // "this month" or month name
        if (searchTerm.contains('this month') || searchTerm.contains('month')) {
            Date startOfMonth = today.toStartOfMonth();
            Date endOfMonth = startOfMonth.addMonths(1).addDays(-1);
            return [
                SELECT Name, Ticker__c, Earnings_Date__c
                FROM IR_Company__c
                WHERE Earnings_Date__c >= :startOfMonth
                    AND Earnings_Date__c <= :endOfMonth
                ORDER BY Earnings_Date__c
            ];
        }

        // "next week"
        if (searchTerm.contains('next week') || searchTerm.contains('week')) {
            Date weekEnd = today.addDays(7);
            return [
                SELECT Name, Ticker__c, Earnings_Date__c
                FROM IR_Company__c
                WHERE Earnings_Date__c >= :today
                    AND Earnings_Date__c <= :weekEnd
                ORDER BY Earnings_Date__c
            ];
        }

        // Default: next 10 upcoming
        return [
            SELECT Name, Ticker__c, Earnings_Date__c
            FROM IR_Company__c
            WHERE Earnings_Date__c >= :today
            ORDER BY Earnings_Date__c
            LIMIT 10
        ];
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
