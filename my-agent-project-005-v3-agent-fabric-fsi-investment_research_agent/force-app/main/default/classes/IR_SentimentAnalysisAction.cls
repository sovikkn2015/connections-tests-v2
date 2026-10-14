public with sharing class IR_SentimentAnalysisAction {

    public class SentimentInput {
        @InvocableVariable(label='Query' description='Sentiment analysis query — e.g. "NVDA sentiment" or "AAPL earnings call tone"' required=true)
        public String query;
    }

    public class SentimentOutput {
        @InvocableVariable(label='Sentiment Result' description='Formatted sentiment analysis results')
        public String sentimentResult;
    }

    private static final String FALLBACK_MSG =
        'Sentiment analysis callout to Flex Gateway failed. Check Named Credential IR_FlexGateway and Custom Label FlexGatewayUrl.';

    @InvocableMethod(
        label='Analyze Sentiment'
        description='Analyzes sentiment from earnings transcripts and news via Strands agent through Flex Gateway'
    )
    public static List<SentimentOutput> analyzeSentiment(List<SentimentInput> inputs) {
        List<SentimentOutput> outputs = new List<SentimentOutput>();
        Long startTime = System.currentTimeMillis();

        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'sentiment_analysis',
                inputs[0].query,
                new Map<String, Object>{'platform' => 'Both', 'agent' => 'IR_Research_Agent'}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (SentimentInput input : inputs) {
            SentimentOutput output = new SentimentOutput();
            try {
                String rawQuery = input.query != null ? input.query.trim() : '';
                if (String.isBlank(rawQuery)) {
                    output.sentimentResult = 'Please provide a query — e.g. "NVDA sentiment" or "AAPL earnings call tone".';
                    outputs.add(output);
                    continue;
                }

                Map<String, String> parsed = parseQuery(rawQuery);
                String ticker = parsed.get('ticker');
                String toolName = parsed.get('toolName');

                output.sentimentResult = callGateway(ticker, toolName);
            } catch (Exception e) {
                output.sentimentResult = FALLBACK_MSG;
                System.debug('IR_SentimentAnalysisAction error: ' + e.getMessage());
            }
            outputs.add(output);
        }

        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'sentiment_analysis', inputs[i].query,
                    null, 'Flex Gateway: sentiment-analysis', null, 'Both',
                    System.currentTimeMillis() - startTime
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }

        if (traceId != null) {
            try {
                String spanOutput = outputs.isEmpty() ? '' : (outputs[0].sentimentResult != null ? outputs[0].sentimentResult : '');
                IR_LangfuseTracer.addSpan(
                    traceId, 'analyze_sentiment', inputs[0].query,
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

        String toolName = 'aggregate_sentiment';
        if (upper.contains('TRANSCRIPT') || upper.contains('EARNINGS CALL') || upper.contains('CALL ANALYSIS')) {
            toolName = 'analyze_transcript';
        } else if (upper.contains('NEWS') || upper.contains('HEADLINE')) {
            toolName = 'score_news_sentiment';
        } else if (upper.contains('TONE') || upper.contains('SHIFT') || upper.contains('LANGUAGE')) {
            toolName = 'detect_tone_shifts';
        }

        String ticker = '';
        for (String word : rawQuery.split('\\s+')) {
            String cleaned = word.replaceAll('[^A-Za-z]', '').toUpperCase();
            if (cleaned.length() >= 1 && cleaned.length() <= 5 && !isSentimentKeyword(cleaned)) {
                ticker = cleaned;
                break;
            }
        }

        result.put('ticker', ticker);
        result.put('toolName', toolName);
        return result;
    }

    private static Boolean isSentimentKeyword(String word) {
        Set<String> keywords = new Set<String>{
            'GET', 'THE', 'FOR', 'AND', 'SHOW', 'FIND', 'WHAT', 'HOW',
            'SENTIMENT', 'TONE', 'SHIFT', 'NEWS', 'HEADLINE', 'ANALYZE',
            'ANALYSIS', 'EARNINGS', 'CALL', 'TRANSCRIPT', 'LANGUAGE',
            'FEELING', 'MARKET', 'MOOD', 'SCORE'
        };
        return keywords.contains(word);
    }

    private static String callGateway(String ticker, String toolName) {
        try {
            HttpResponse resp = IR_FlexGatewayClient.callAgent(
                'sentiment-analysis',
                'Run ' + toolName + ' on ' + ticker,
                new Map<String, Object>{ 'ticker' => ticker, 'tool' => toolName }
            );
            if (resp.getStatusCode() == 200) {
                return formatResponse(resp.getBody(), toolName, ticker);
            }
            return 'Flex Gateway returned status ' + resp.getStatusCode() + ' for sentiment-analysis. ' + FALLBACK_MSG;
        } catch (System.CalloutException e) {
            return FALLBACK_MSG;
        }
    }

    private static String formatResponse(String jsonBody, String toolName, String ticker) {
        Map<String, Object> data = (Map<String, Object>) JSON.deserializeUntyped(jsonBody);

        if (data.containsKey('error')) {
            return (String) data.get('error');
        }

        if (toolName == 'analyze_transcript') {
            Map<String, Object> analysis = (Map<String, Object>) data.get('analysis');
            if (analysis == null) {
                return 'Transcript analysis completed for ' + ticker + '.';
            }
            return ticker + ' Earnings Call Analysis:\n'
                + '  Sentiment: ' + safeStr(analysis.get('overall_sentiment')) + '\n'
                + '  Confidence: ' + safeStr(analysis.get('confidence')) + '\n'
                + '  Management Tone: ' + safeStr(analysis.get('management_tone')) + '\n'
                + '  Forward Guidance: ' + safeStr(analysis.get('forward_guidance')) + '\n'
                + '  Details: ' + safeStr(analysis.get('guidance_details'));
        }

        if (toolName == 'score_news_sentiment') {
            Map<String, Object> analysis = (Map<String, Object>) data.get('analysis');
            if (analysis == null) {
                return 'News sentiment scored for ' + ticker + '.';
            }
            return ticker + ' News Sentiment:\n'
                + '  Overall: ' + safeStr(analysis.get('overall_sentiment')) + '\n'
                + '  Score: ' + safeStr(analysis.get('sentiment_score')) + '\n'
                + '  Reasoning: ' + safeStr(analysis.get('reasoning')) + '\n'
                + '  News Volume: ' + safeStr(analysis.get('news_volume'));
        }

        if (toolName == 'detect_tone_shifts') {
            Map<String, Object> analysis = (Map<String, Object>) data.get('analysis');
            if (analysis == null) {
                return 'Tone shift analysis completed for ' + ticker + '.';
            }
            return ticker + ' Tone Analysis:\n'
                + '  Dominant Tone: ' + safeStr(analysis.get('dominant_tone')) + '\n'
                + '  Consistency: ' + safeStr(analysis.get('overall_consistency'));
        }

        if (toolName == 'aggregate_sentiment') {
            Map<String, Object> synthesis = (Map<String, Object>) data.get('synthesis');
            if (synthesis == null) {
                return 'Aggregate sentiment completed for ' + ticker + '.';
            }
            return ticker + ' Sentiment Report:\n'
                + '  Overall Sentiment: ' + safeStr(synthesis.get('overall_sentiment')) + '\n'
                + '  Confidence: ' + safeStr(synthesis.get('confidence')) + '\n'
                + '  Summary: ' + safeStr(synthesis.get('executive_summary')) + '\n'
                + '  Recommendation: ' + safeStr(synthesis.get('recommendation'));
        }

        return 'Sentiment analysis completed for ' + ticker + '.';
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
