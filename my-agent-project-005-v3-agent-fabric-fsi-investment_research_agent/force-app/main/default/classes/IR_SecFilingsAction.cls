public with sharing class IR_SecFilingsAction {

    public class FilingInput {
        @InvocableVariable(label='Query' description='Filing query — e.g. "NVDA 10-Q" or "Apple latest filing"' required=true)
        public String query;
    }

    public class FilingOutput {
        @InvocableVariable(label='Filing Info' description='Formatted SEC filing results')
        public String filingInfo;
    }

    private static final String FALLBACK_MSG =
        'SEC filings callout to Flex Gateway failed. Check Named Credential IR_FlexGateway and Custom Label FlexGatewayUrl.';

    @InvocableMethod(
        label='Get SEC Filings'
        description='Fetches SEC filings (10-K, 10-Q, 8-K) for a company via Flex Gateway'
    )
    public static List<FilingOutput> getSecFilings(List<FilingInput> inputs) {
        List<FilingOutput> outputs = new List<FilingOutput>();
        Long startTime = System.currentTimeMillis();

        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'sec_filings',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Both', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (FilingInput input : inputs) {
            FilingOutput output = new FilingOutput();
            try {
                String rawQuery = input.query != null ? input.query.trim() : '';
                if (String.isBlank(rawQuery)) {
                    output.filingInfo = 'Please provide a query — e.g. "NVDA 10-K" or "Apple 8-K".';
                    outputs.add(output);
                    continue;
                }

                Map<String, String> parsed = parseQuery(rawQuery);
                String ticker = parsed.get('ticker');
                String filingType = parsed.get('filingType');

                String toolName = getToolName(filingType);
                output.filingInfo = callGateway(ticker, toolName);
            } catch (Exception e) {
                output.filingInfo = FALLBACK_MSG;
                System.debug('IR_SecFilingsAction error: ' + e.getMessage());
            }
            outputs.add(output);
        }

        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'sec_filings', inputs[i].query,
                    null, 'Flex Gateway: sec-edgar', null, 'Salesforce',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].filingInfo != null ? outputs[0].filingInfo : '');
                IR_LangfuseTracer.addSpan(
                    traceId, 'get_sec_filings', inputs[0].query,
                    spanOutput.length() > 500 ? spanOutput.substring(0, 500) : spanOutput,
                    System.currentTimeMillis() - startTime, null, 'Both'
                );
            } catch (Exception spanEx) {
                System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
            }
        }

        return outputs;
    }

    private static Map<String, String> parseQuery(String rawQuery) {
        Map<String, String> result = new Map<String, String>();
        String upper = rawQuery.toUpperCase();

        String filingType = '10-K';
        if (upper.contains('10-Q') || upper.contains('10Q')) {
            filingType = '10-Q';
        } else if (upper.contains('8-K') || upper.contains('8K')) {
            filingType = '8-K';
        } else if (upper.contains('INSIDER') || upper.contains('TRANSACTION')) {
            filingType = 'INSIDER';
        } else if (upper.contains('10-K') || upper.contains('10K') || upper.contains('ANNUAL')) {
            filingType = '10-K';
        }

        String ticker = '';
        for (String word : rawQuery.split('\\s+')) {
            String cleaned = word.replaceAll('[^A-Za-z]', '').toUpperCase();
            if (cleaned.length() >= 1 && cleaned.length() <= 5 && !isFilingKeyword(cleaned)) {
                ticker = cleaned;
                break;
            }
        }

        result.put('ticker', ticker);
        result.put('filingType', filingType);
        return result;
    }

    private static Boolean isFilingKeyword(String word) {
        Set<String> keywords = new Set<String>{
            'GET', 'THE', 'FOR', 'AND', 'LATEST', 'RECENT', 'SHOW',
            'FIND', 'FILING', 'FILINGS', 'ANNUAL', 'QUARTERLY',
            'INSIDER', 'TRANSACTION', 'TRANSACTIONS', 'REPORT'
        };
        return keywords.contains(word);
    }

    private static String getToolName(String filingType) {
        if (filingType == '10-Q') return 'get_10q';
        if (filingType == '8-K') return 'get_8k';
        if (filingType == 'INSIDER') return 'get_insider_transactions';
        return 'get_10k';
    }

    private static String callGateway(String ticker, String toolName) {
        try {
            HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
                'sec-edgar', toolName,
                new Map<String, Object>{ 'ticker' => ticker }
            );
            if (resp.getStatusCode() == 200) {
                return formatResponse(resp.getBody(), toolName, ticker);
            }
            return 'Flex Gateway returned status ' + resp.getStatusCode() + ' for sec-edgar. ' + FALLBACK_MSG;
        } catch (System.CalloutException e) {
            return FALLBACK_MSG;
        }
    }

    private static String formatResponse(String jsonBody, String toolName, String ticker) {
        Map<String, Object> data = (Map<String, Object>) JSON.deserializeUntyped(jsonBody);

        if (data.containsKey('message')) {
            return (String) data.get('message');
        }

        String label = toolName.replace('get_', '').replace('_', ' ').toUpperCase();
        String result = 'SEC ' + label + ' for ' + ticker + ':\n';

        String listKey = toolName == 'get_insider_transactions' ? 'transactions' : 'filings';
        List<Object> items = (List<Object>) data.get(listKey);
        if (items == null || items.isEmpty()) {
            return 'No ' + label + ' filings found for ' + ticker + '.';
        }

        for (Object item : items) {
            Map<String, Object> filing = (Map<String, Object>) item;
            result += '\n  - ' + safeStr(filing.get('form_type'))
                + ' | Filed: ' + safeStr(filing.get('filing_date'))
                + ' | ' + safeStr(filing.get('company_name'));
            if (filing.containsKey('description') && filing.get('description') != null) {
                String descVal = String.valueOf(filing.get('description'));
                if (descVal.length() > 0) {
                    result += '\n    ' + (descVal.length() > 200 ? descVal.substring(0, 200) + '...' : descVal);
                }
            }
        }

        return result;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
