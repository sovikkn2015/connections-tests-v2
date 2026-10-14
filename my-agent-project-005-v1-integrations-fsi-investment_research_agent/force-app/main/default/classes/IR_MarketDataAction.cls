public with sharing class IR_MarketDataAction {

    public class MarketInput {
        @InvocableVariable(label='Query' description='Market data query — e.g. "NVDA quote" or "AAPL price history 60"' required=true)
        public String query;
    }

    public class MarketOutput {
        @InvocableVariable(label='Market Data' description='Formatted market data results')
        public String marketData;
    }

    private static final String NAMED_CREDENTIAL = 'callout:AWS_IR_API';
    private static final String FALLBACK_MSG =
        'Market data integration requires AWS MCP server configuration. ' +
        'Please set up the Named Credential \'AWS_IR_API\' with your API Gateway URL.';

    @InvocableMethod(
        label='Get Market Data'
        description='Fetches real-time stock quotes and market data via MCP server'
    )
    public static List<MarketOutput> getMarketData(List<MarketInput> inputs) {
        List<MarketOutput> outputs = new List<MarketOutput>();
        Long startTime = System.currentTimeMillis();

        // Langfuse tracing
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'market_data',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Both', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (MarketInput input : inputs) {
            MarketOutput output = new MarketOutput();
            try {
                String rawQuery = input.query != null ? input.query.trim() : '';
                if (String.isBlank(rawQuery)) {
                    output.marketData = 'Please provide a query — e.g. "NVDA quote" or "AAPL price history".';
                    outputs.add(output);
                    continue;
                }

                Map<String, String> parsed = parseQuery(rawQuery);
                String ticker = parsed.get('ticker');
                String toolName = parsed.get('toolName');
                String period = parsed.get('period');

                output.marketData = callMcpServer(ticker, toolName, period);
            } catch (Exception e) {
                output.marketData = FALLBACK_MSG;
                System.debug('IR_MarketDataAction error: ' + e.getMessage());
            }
            outputs.add(output);
        }

        // Audit logging
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'market_data', inputs[i].query,
                    null, 'Market Data MCP', null, 'Salesforce',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        // Langfuse span
        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].marketData != null ? outputs[0].marketData : '');
                IR_LangfuseTracer.addSpan(
                    traceId,
                    'get_market_data',
                    inputs[0].query,
                    spanOutput.length() > 500 ? spanOutput.substring(0, 500) : spanOutput,
                    System.currentTimeMillis() - startTime,
                    null,
                    'Both'
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

        // Detect tool type
        String toolName = 'get_quote'; // default
        if (upper.contains('HISTORY') || upper.contains('HISTORICAL') || upper.contains('CHART')) {
            toolName = 'get_price_history';
        } else if (upper.contains('ANALYST') || upper.contains('CONSENSUS') || upper.contains('ESTIMATE')) {
            toolName = 'get_analyst_consensus';
        } else if (upper.contains('OPTION') || upper.contains('CHAIN') || upper.contains('PUT') || upper.contains('CALL')) {
            toolName = 'get_options_chain';
        }

        // Extract period for price history (look for a number)
        String period = '30';
        if (toolName == 'get_price_history') {
            Pattern p = Pattern.compile('(\\d+)');
            Matcher m = p.matcher(rawQuery);
            if (m.find()) {
                period = m.group(1);
            }
        }

        // Extract ticker — first word that looks like a ticker
        String ticker = '';
        for (String word : rawQuery.split('\\s+')) {
            String cleaned = word.replaceAll('[^A-Za-z]', '').toUpperCase();
            if (cleaned.length() >= 1 && cleaned.length() <= 5 &&
                !isMarketKeyword(cleaned)) {
                ticker = cleaned;
                break;
            }
        }

        result.put('ticker', ticker);
        result.put('toolName', toolName);
        result.put('period', period);
        return result;
    }

    private static Boolean isMarketKeyword(String word) {
        Set<String> keywords = new Set<String>{
            'GET', 'THE', 'FOR', 'AND', 'SHOW', 'FIND', 'QUOTE', 'PRICE',
            'HISTORY', 'HISTORICAL', 'CHART', 'ANALYST', 'CONSENSUS',
            'ESTIMATE', 'OPTION', 'OPTIONS', 'CHAIN', 'PUT', 'CALL',
            'DATA', 'MARKET', 'STOCK', 'DAYS', 'DAY'
        };
        return keywords.contains(word);
    }

    private static String callMcpServer(String ticker, String toolName, String period) {
        try {
            HttpRequest req = new HttpRequest();
            req.setEndpoint(NAMED_CREDENTIAL + '/market-data/' + toolName);
            req.setMethod('POST');
            req.setHeader('Content-Type', 'application/json');

            Map<String, Object> bodyMap = new Map<String, Object>{ 'ticker' => ticker };
            if (toolName == 'get_price_history') {
                bodyMap.put('period', Integer.valueOf(period));
            }
            req.setBody(JSON.serialize(bodyMap));
            req.setTimeout(20000);

            Http http = new Http();
            HttpResponse resp = http.send(req);

            if (resp.getStatusCode() == 200) {
                return formatResponse(resp.getBody(), toolName, ticker);
            } else {
                return 'Market Data API returned status ' + resp.getStatusCode() + '. ' + FALLBACK_MSG;
            }
        } catch (System.CalloutException e) {
            return FALLBACK_MSG;
        }
    }

    private static String formatResponse(String jsonBody, String toolName, String ticker) {
        Map<String, Object> data = (Map<String, Object>) JSON.deserializeUntyped(jsonBody);

        if (data.containsKey('message')) {
            return (String) data.get('message');
        }

        if (toolName == 'get_quote') {
            Map<String, Object> quote = (Map<String, Object>) data.get('quote');
            if (quote == null || quote.isEmpty()) {
                return 'No quote data available for ' + ticker + '.';
            }
            return ticker + ' Quote:\n'
                + '  Price: $' + safeStr(quote.get('price')) + '\n'
                + '  Change: ' + safeStr(quote.get('change'))
                + ' (' + safeStr(quote.get('change_percent')) + ')\n'
                + '  Volume: ' + safeStr(quote.get('volume')) + '\n'
                + '  Day Range: $' + safeStr(quote.get('low'))
                + ' - $' + safeStr(quote.get('high')) + '\n'
                + '  Previous Close: $' + safeStr(quote.get('previous_close'));
        }

        if (toolName == 'get_price_history') {
            List<Object> prices = (List<Object>) data.get('prices');
            if (prices == null || prices.isEmpty()) {
                return 'No price history available for ' + ticker + '.';
            }
            String result = ticker + ' Price History (' + data.get('period_days') + ' days):\n';
            Integer count = Math.min(prices.size(), 10);
            for (Integer i = 0; i < count; i++) {
                Map<String, Object> day = (Map<String, Object>) prices[i];
                result += '  ' + safeStr(day.get('date'))
                    + ' | Close: $' + safeStr(day.get('close'))
                    + ' | Vol: ' + safeStr(day.get('volume')) + '\n';
            }
            if (prices.size() > 10) {
                result += '  ... and ' + (prices.size() - 10) + ' more days';
            }
            return result;
        }

        if (toolName == 'get_analyst_consensus') {
            Map<String, Object> consensus = (Map<String, Object>) data.get('consensus');
            if (consensus == null || consensus.isEmpty()) {
                return 'No analyst consensus data available for ' + ticker + '.';
            }
            return ticker + ' Analyst Consensus:\n'
                + '  Target Price: $' + safeStr(consensus.get('analyst_target_price')) + '\n'
                + '  P/E Ratio: ' + safeStr(consensus.get('pe_ratio')) + '\n'
                + '  Forward P/E: ' + safeStr(consensus.get('forward_pe')) + '\n'
                + '  EPS: $' + safeStr(consensus.get('eps')) + '\n'
                + '  Profit Margin: ' + safeStr(consensus.get('profit_margin')) + '\n'
                + '  Beta: ' + safeStr(consensus.get('beta')) + '\n'
                + '  52W Range: $' + safeStr(consensus.get('52_week_low'))
                + ' - $' + safeStr(consensus.get('52_week_high'));
        }

        if (toolName == 'get_options_chain') {
            Map<String, Object> opts = (Map<String, Object>) data.get('options_summary');
            if (opts == null || opts.isEmpty()) {
                return 'No options data available for ' + ticker + '.';
            }
            return ticker + ' Options Summary:\n'
                + '  Beta: ' + safeStr(opts.get('beta')) + '\n'
                + '  52W High: $' + safeStr(opts.get('52_week_high')) + '\n'
                + '  52W Low: $' + safeStr(opts.get('52_week_low')) + '\n'
                + '  50D MA: $' + safeStr(opts.get('50_day_moving_avg')) + '\n'
                + '  200D MA: $' + safeStr(opts.get('200_day_moving_avg')) + '\n'
                + '  Short Ratio: ' + safeStr(opts.get('short_ratio'));
        }

        return 'Market data retrieved for ' + ticker + '.';
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
