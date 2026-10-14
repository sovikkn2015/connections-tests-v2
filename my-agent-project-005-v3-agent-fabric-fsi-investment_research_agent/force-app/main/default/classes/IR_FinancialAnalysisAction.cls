public with sharing class IR_FinancialAnalysisAction {

    public class AnalysisInput {
        @InvocableVariable(label='Query' description='Financial analysis query — e.g. "NVDA fair value" or "AAPL DCF" or "MSFT comps"' required=true)
        public String query;
    }

    public class AnalysisOutput {
        @InvocableVariable(label='Analysis Result' description='Formatted financial analysis results')
        public String analysisResult;
    }

    private static final String FALLBACK_MSG =
        'Financial analysis callout to Flex Gateway failed. Check Named Credential IR_FlexGateway and Custom Label FlexGatewayUrl.';

    @InvocableMethod(
        label='Run Financial Analysis'
        description='Runs financial analysis (DCF, comps, Monte Carlo, fair value) via Strands agent through Flex Gateway'
    )
    public static List<AnalysisOutput> runAnalysis(List<AnalysisInput> inputs) {
        List<AnalysisOutput> outputs = new List<AnalysisOutput>();
        Long startTime = System.currentTimeMillis();

        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'financial_analysis',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Both', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (AnalysisInput input : inputs) {
            AnalysisOutput output = new AnalysisOutput();
            try {
                String rawQuery = input.query != null ? input.query.trim() : '';
                if (String.isBlank(rawQuery)) {
                    output.analysisResult = 'Please provide a query — e.g. "NVDA fair value" or "AAPL DCF".';
                    outputs.add(output);
                    continue;
                }

                Map<String, String> parsed = parseQuery(rawQuery);
                String ticker = parsed.get('ticker');
                String toolName = parsed.get('toolName');

                output.analysisResult = callGateway(ticker, toolName);
            } catch (Exception e) {
                output.analysisResult = FALLBACK_MSG;
                System.debug('IR_FinancialAnalysisAction error: ' + e.getMessage());
            }
            outputs.add(output);
        }

        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'financial_analysis', inputs[i].query,
                    null, 'Flex Gateway: financial-analysis', null, 'Both',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].analysisResult != null ? outputs[0].analysisResult : '');
                IR_LangfuseTracer.addSpan(
                    traceId, 'run_financial_analysis', inputs[0].query,
                    spanOutput.length() > 500 ? spanOutput.substring(0, 500) : spanOutput,
                    System.currentTimeMillis() - startTime, 'claude-sonnet-4', 'Both'
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

        String toolName = 'fair_value';
        if (upper.contains('DCF') || upper.contains('DISCOUNTED CASH')) {
            toolName = 'run_dcf';
        } else if (upper.contains('COMP') || upper.contains('PEER') || upper.contains('RELATIVE')) {
            toolName = 'run_comps';
        } else if (upper.contains('MONTE CARLO') || upper.contains('SIMULATION') || upper.contains('DISTRIBUTION')) {
            toolName = 'monte_carlo';
        }

        String ticker = '';
        for (String word : rawQuery.split('\\s+')) {
            String cleaned = word.replaceAll('[^A-Za-z]', '').toUpperCase();
            if (cleaned.length() >= 1 && cleaned.length() <= 5 && !isAnalysisKeyword(cleaned)) {
                ticker = cleaned;
                break;
            }
        }

        result.put('ticker', ticker);
        result.put('toolName', toolName);
        return result;
    }

    private static Boolean isAnalysisKeyword(String word) {
        Set<String> keywords = new Set<String>{
            'GET', 'THE', 'FOR', 'AND', 'SHOW', 'FIND', 'RUN', 'WHAT',
            'FAIR', 'VALUE', 'DCF', 'COMPS', 'MONTE', 'CARLO',
            'ANALYSIS', 'FINANCIAL', 'MODEL', 'SIMULATION',
            'DISCOUNTED', 'CASH', 'FLOW', 'PEER', 'RELATIVE',
            'OF', 'ON', 'IN', 'AT', 'TO', 'IS', 'A', 'AN', 'MY',
            'ME', 'DO', 'IF', 'OR', 'SO', 'UP', 'BY', 'NO', 'BE',
            'VS', 'HOW', 'CAN', 'ALL', 'ITS', 'HAS', 'HAD', 'NOT',
            'BUT', 'ARE', 'WAS', 'WHO', 'WHY', 'USE', 'NEW', 'OLD',
            'OUR', 'HIS', 'HER', 'ANY', 'MAY', 'NOW', 'SET', 'TRY',
            'TELL', 'GIVE', 'LOOK', 'MAKE', 'TAKE', 'WANT', 'NEED',
            'DOES', 'WILL', 'WITH', 'FROM', 'THAT', 'THIS', 'HAVE',
            'BEEN', 'EACH', 'SOME', 'THEM', 'THAN', 'THEN', 'ALSO',
            'JUST', 'OVER', 'ONLY', 'VERY', 'WHEN', 'MOST', 'MUCH',
            'ABOUT', 'PRICE', 'STOCK', 'TRADE', 'QUOTE'
        };
        return keywords.contains(word);
    }

    private static String callGateway(String ticker, String toolName) {
        try {
            // Strands agent invocation — delegated to the single choke-point client.
            // We pass the tool name as a context hint so the agent can dispatch.
            HttpResponse resp = IR_FlexGatewayClient.callAgent(
                'financial-analysis',
                'Run ' + toolName + ' on ' + ticker,
                new Map<String, Object>{ 'ticker' => ticker, 'tool' => toolName }
            );
            if (resp.getStatusCode() == 200) {
                return formatResponse(resp.getBody(), toolName, ticker);
            }
            return 'Flex Gateway returned status ' + resp.getStatusCode() + ' for financial-analysis. ' + FALLBACK_MSG;
        } catch (System.CalloutException e) {
            return FALLBACK_MSG;
        }
    }

    private static String formatResponse(String jsonBody, String toolName, String ticker) {
        Map<String, Object> data = (Map<String, Object>) JSON.deserializeUntyped(jsonBody);

        if (data.containsKey('error')) {
            return (String) data.get('error');
        }

        if (toolName == 'run_dcf') {
            return ticker + ' DCF Analysis:\n'
                + '  Fair Value: $' + safeStr(data.get('fair_value_per_share')) + '\n'
                + '  Current Price: $' + safeStr(data.get('current_price')) + '\n'
                + '  Upside: ' + safeStr(data.get('upside_pct')) + '%\n'
                + '  Enterprise Value: $' + safeStr(data.get('enterprise_value_bn')) + 'B';
        }

        if (toolName == 'run_comps') {
            String compResult = ticker + ' Comparable Analysis (' + safeStr(data.get('sector')) + '):\n';
            Map<String, Object> relVal = (Map<String, Object>) data.get('relative_valuation');
            if (relVal != null) {
                compResult += '  P/E vs Peers: ' + safeStr(relVal.get('pe_vs_peers')) + '\n';
                compResult += '  EV/EBITDA vs Peers: ' + safeStr(relVal.get('ev_ebitda_vs_peers')) + '\n';
                compResult += '  P/S vs Peers: ' + safeStr(relVal.get('ps_vs_peers'));
            }
            return compResult;
        }

        if (toolName == 'monte_carlo') {
            Map<String, Object> pcts = (Map<String, Object>) data.get('percentiles');
            return ticker + ' Monte Carlo Simulation:\n'
                + '  Current Price: $' + safeStr(data.get('current_price')) + '\n'
                + '  5th Percentile: $' + safeStr(pcts != null ? pcts.get('p5') : null) + '\n'
                + '  25th Percentile: $' + safeStr(pcts != null ? pcts.get('p25') : null) + '\n'
                + '  Median (50th): $' + safeStr(pcts != null ? pcts.get('p50') : null) + '\n'
                + '  75th Percentile: $' + safeStr(pcts != null ? pcts.get('p75') : null) + '\n'
                + '  95th Percentile: $' + safeStr(pcts != null ? pcts.get('p95') : null);
        }

        if (toolName == 'fair_value') {
            String narrative = safeStr(data.get('narrative'));
            return ticker + ' Fair Value Summary:\n'
                + '  DCF Fair Value: $' + safeStr(data.get('dcf_fair_value')) + '\n'
                + '  Monte Carlo Median: $' + safeStr(data.get('monte_carlo_median')) + '\n'
                + '  Current Price: $' + safeStr(data.get('current_price')) + '\n\n'
                + narrative;
        }

        return 'Financial analysis completed for ' + ticker + '.';
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
