public with sharing class IR_NewsSearchAction {

    public class NewsInput {
        @InvocableVariable(label='Query' description='News search query — e.g. "NVDA news" or "Apple sentiment"' required=true)
        public String query;
    }

    public class NewsOutput {
        @InvocableVariable(label='News Results' description='Formatted news search results')
        public String newsResults;
    }

    private static final String FALLBACK_MSG =
        'News search callout to Flex Gateway failed. Check Named Credential IR_FlexGateway and Custom Label FlexGatewayUrl.';

    @InvocableMethod(
        label='Search Financial News'
        description='Searches financial news and sentiment via Flex Gateway'
    )
    public static List<NewsOutput> searchNews(List<NewsInput> inputs) {
        List<NewsOutput> outputs = new List<NewsOutput>();
        Long startTime = System.currentTimeMillis();

        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'news_search',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Both', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (NewsInput input : inputs) {
            NewsOutput output = new NewsOutput();
            try {
                String rawQuery = input.query != null ? input.query.trim() : '';
                if (String.isBlank(rawQuery)) {
                    output.newsResults = 'Please provide a query — e.g. "NVDA news" or "Apple sentiment".';
                    outputs.add(output);
                    continue;
                }

                Map<String, String> parsed = parseQuery(rawQuery);
                String ticker = parsed.get('ticker');
                String toolName = parsed.get('toolName');

                output.newsResults = callGateway(ticker, toolName);
            } catch (Exception e) {
                output.newsResults = FALLBACK_MSG;
                System.debug('IR_NewsSearchAction error: ' + e.getMessage());
            }
            outputs.add(output);
        }

        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'news_search', inputs[i].query,
                    null, 'Flex Gateway: news-search', null, 'Salesforce',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].newsResults != null ? outputs[0].newsResults : '');
                IR_LangfuseTracer.addSpan(
                    traceId, 'search_news', inputs[0].query,
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

        String toolName = 'search_financial_news';
        if (upper.contains('HEADLINE') || upper.contains('TOP')) {
            toolName = 'get_headlines';
        } else if (upper.contains('SENTIMENT') || upper.contains('TONE') || upper.contains('BULLISH') || upper.contains('BEARISH')) {
            toolName = 'get_news_sentiment';
        }

        String ticker = '';
        for (String word : rawQuery.split('\\s+')) {
            String cleaned = word.replaceAll('[^A-Za-z]', '').toUpperCase();
            if (cleaned.length() >= 1 && cleaned.length() <= 5 && !isNewsKeyword(cleaned)) {
                ticker = cleaned;
                break;
            }
        }

        result.put('ticker', ticker);
        result.put('toolName', toolName);
        return result;
    }

    private static Boolean isNewsKeyword(String word) {
        Set<String> keywords = new Set<String>{
            'GET', 'THE', 'FOR', 'AND', 'SHOW', 'FIND', 'NEWS', 'SEARCH',
            'HEADLINE', 'HEADLINES', 'TOP', 'LATEST', 'RECENT',
            'SENTIMENT', 'TONE', 'BULLISH', 'BEARISH', 'ABOUT'
        };
        return keywords.contains(word);
    }

    private static String callGateway(String ticker, String toolName) {
        try {
            HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
                'news-search', toolName,
                new Map<String, Object>{ 'ticker' => ticker }
            );
            if (resp.getStatusCode() == 200) {
                return formatResponse(resp.getBody(), toolName, ticker);
            }
            return 'Flex Gateway returned status ' + resp.getStatusCode() + ' for news-search. ' + FALLBACK_MSG;
        } catch (System.CalloutException e) {
            return FALLBACK_MSG;
        }
    }

    private static String formatResponse(String jsonBody, String toolName, String ticker) {
        Map<String, Object> data = (Map<String, Object>) JSON.deserializeUntyped(jsonBody);

        if (data.containsKey('message')) {
            return (String) data.get('message');
        }

        if (toolName == 'search_financial_news') {
            List<Object> articles = (List<Object>) data.get('articles');
            if (articles == null || articles.isEmpty()) {
                return 'No recent financial news found for ' + ticker + '.';
            }
            String result = 'Financial News for ' + ticker + ':\n';
            for (Object article : articles) {
                Map<String, Object> a = (Map<String, Object>) article;
                result += '\n  - ' + safeStr(a.get('title'));
                if (a.containsKey('published_date') && a.get('published_date') != null) {
                    result += ' (' + safeStr(a.get('published_date')) + ')';
                }
                result += '\n    ' + safeStr(a.get('url'));
            }
            return result;
        }

        if (toolName == 'get_headlines') {
            List<Object> headlines = (List<Object>) data.get('headlines');
            if (headlines == null || headlines.isEmpty()) {
                return 'No headlines found for ' + ticker + '.';
            }
            String result = 'Headlines for ' + ticker + ':\n';
            for (Object headline : headlines) {
                Map<String, Object> h = (Map<String, Object>) headline;
                result += '\n  - ' + safeStr(h.get('title'));
            }
            return result;
        }

        if (toolName == 'get_news_sentiment') {
            String sentiment = safeStr(data.get('sentiment'));
            String result = ticker + ' News Sentiment: ' + sentiment + '\n'
                + '  Positive signals: ' + safeStr(data.get('positive_signals')) + '\n'
                + '  Negative signals: ' + safeStr(data.get('negative_signals'));

            List<Object> posArticles = (List<Object>) data.get('positive_articles');
            if (posArticles != null && !posArticles.isEmpty()) {
                result += '\n\n  Bullish indicators:';
                for (Object a : posArticles) {
                    Map<String, Object> article = (Map<String, Object>) a;
                    result += '\n    + ' + safeStr(article.get('title'));
                }
            }

            List<Object> negArticles = (List<Object>) data.get('negative_articles');
            if (negArticles != null && !negArticles.isEmpty()) {
                result += '\n\n  Bearish indicators:';
                for (Object a : negArticles) {
                    Map<String, Object> article = (Map<String, Object>) a;
                    result += '\n    - ' + safeStr(article.get('title'));
                }
            }

            return result;
        }

        return 'News data retrieved for ' + ticker + '.';
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
