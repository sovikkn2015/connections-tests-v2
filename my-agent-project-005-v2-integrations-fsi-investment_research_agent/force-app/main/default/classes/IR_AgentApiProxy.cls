/**
 * IR_AgentApiProxy — Apex REST endpoint that wraps the Agentforce agent invocation.
 *
 * Provides a single POST endpoint for the frontend to call instead of invoking
 * individual Apex actions directly. Tries ConnectApi.CopilotService first,
 * then falls back to keyword-based routing to the appropriate action class.
 *
 * Endpoint: POST /services/apexrest/ir-agent/chat/
 * Request:  {"query": "...", "sessionId": "..."}
 * Response: {"response": "...", "topic": "...", "action": "...", "traceId": "..."}
 */
@RestResource(urlMapping='/ir-agent/chat/*')
global with sharing class IR_AgentApiProxy {

    private static final Map<String, String> TOPIC_KEYWORDS = new Map<String, String>{
        'company' => 'company_lookup', 'lookup' => 'company_lookup', 'info' => 'company_lookup',
        'coverage' => 'coverage_check', 'analyst' => 'coverage_check', 'rating' => 'coverage_check',
        'earnings' => 'earnings_calendar', 'calendar' => 'earnings_calendar',
        'watchlist' => 'watchlist', 'tracked' => 'watchlist', 'watch' => 'watchlist',
        'compliance' => 'compliance_screening', 'restricted' => 'compliance_screening',
        'trade' => 'compliance_screening', 'mnpi' => 'compliance_screening',
        'filing' => 'sec_filings', 'sec' => 'sec_filings',
        '10-k' => 'sec_filings', '10-q' => 'sec_filings', '8-k' => 'sec_filings',
        'quote' => 'market_data', 'price' => 'market_data', 'market' => 'market_data',
        'option' => 'market_data', 'consensus' => 'market_data',
        'news' => 'news_search', 'headline' => 'news_search',
        'dcf' => 'financial_analysis', 'fair value' => 'financial_analysis',
        'comps' => 'financial_analysis', 'monte carlo' => 'financial_analysis',
        'valuation' => 'financial_analysis',
        'sentiment' => 'sentiment_analysis', 'tone' => 'sentiment_analysis',
        'transcript' => 'sentiment_analysis',
        'research brief' => 'research_brief', 'brief' => 'research_brief',
        'research note' => 'research_brief'
    };

    @HttpPost
    global static void handlePost() {
        RestRequest req = RestContext.request;
        RestResponse res = RestContext.response;
        res.addHeader('Content-Type', 'application/json');
        Long startTime = System.currentTimeMillis();
        String traceId = null;

        try {
            Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(
                req.requestBody.toString()
            );
            String query = (String) body.get('query');
            String sessionId = (String) body.get('sessionId');

            if (String.isBlank(query)) {
                res.statusCode = 400;
                res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, String>{
                    'error' => 'Missing required field: query'
                }));
                return;
            }

            // Langfuse trace
            try {
                traceId = IR_LangfuseTracer.createTrace(
                    'agent_api_proxy',
                    query,
                    new Map<String, Object>{
                        'platform' => 'Salesforce',
                        'sessionId' => sessionId,
                        'agent' => 'IR_AgentApiProxy'
                    }
                );
            } catch (Exception traceEx) {
                System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
            }

            // Try ConnectApi.CopilotService first
            String agentResponse = tryConnectApiAgent(query, sessionId);
            String topic = 'copilot_service';
            String action = 'ConnectApi.CopilotService';

            // Fallback to keyword-based routing
            if (agentResponse == null) {
                topic = routeToTopic(query);
                action = topic;
                agentResponse = executeAction(topic, query);
            }

            Long durationMs = System.currentTimeMillis() - startTime;

            // Audit log
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_AgentApiProxy', action, query,
                    UserInfo.getName(), topic, traceId, 'Salesforce', durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }

            // Langfuse span
            if (traceId != null) {
                try {
                    String spanOut = agentResponse != null && agentResponse.length() > 500
                        ? agentResponse.substring(0, 500) : agentResponse;
                    IR_LangfuseTracer.addSpan(
                        traceId, 'agent_proxy_route', query,
                        spanOut, durationMs, null, 'Salesforce'
                    );
                } catch (Exception spanEx) {
                    System.debug('Langfuse addSpan failed: ' + spanEx.getMessage());
                }
            }

            res.statusCode = 200;
            res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, Object>{
                'response' => agentResponse,
                'topic' => topic,
                'action' => action,
                'traceId' => traceId != null ? traceId : ''
            }));

        } catch (Exception e) {
            res.statusCode = 500;
            res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, String>{
                'error' => 'Internal error: ' + e.getMessage()
            }));
        }
    }

    /**
     * Attempt to invoke the agent via ConnectApi.CopilotService.
     * Returns null if the API is not available or fails.
     */
    private static String tryConnectApiAgent(String query, String sessionId) {
        try {
            // ConnectApi.CopilotService may not be available in all orgs.
            // Uses dynamic type check to avoid compile-time dependency.
            Type copilotType = Type.forName('ConnectApi', 'CopilotService');
            if (copilotType == null) {
                return null;
            }
            // In production, replace with actual ConnectApi.CopilotService invocation:
            //   ConnectApi.CopilotInput input = new ConnectApi.CopilotInput();
            //   input.query = query;
            //   ConnectApi.CopilotOutput output = ConnectApi.CopilotService.invoke(agentId, input);
            //   return output.response;
            return null;
        } catch (Exception e) {
            System.debug('ConnectApi.CopilotService not available: ' + e.getMessage());
            return null;
        }
    }

    /**
     * Route a natural language query to the best-matching topic using keyword matching.
     */
    @TestVisible
    private static String routeToTopic(String query) {
        if (String.isBlank(query)) {
            return 'company_lookup';
        }
        String lower = query.toLowerCase();

        // Check multi-word keywords first (longer matches win)
        for (String keyword : TOPIC_KEYWORDS.keySet()) {
            if (keyword.contains(' ') && lower.contains(keyword)) {
                return TOPIC_KEYWORDS.get(keyword);
            }
        }
        // Then single-word keywords
        for (String keyword : TOPIC_KEYWORDS.keySet()) {
            if (!keyword.contains(' ') && lower.contains(keyword)) {
                return TOPIC_KEYWORDS.get(keyword);
            }
        }
        return 'company_lookup';
    }

    /**
     * Execute the appropriate action class based on the routed topic.
     */
    private static String executeAction(String topic, String query) {
        switch on topic {
            when 'company_lookup' {
                IR_CompanyLookupAction.LookupInput inp = new IR_CompanyLookupAction.LookupInput();
                inp.companyName = query;
                List<IR_CompanyLookupAction.LookupOutput> out =
                    IR_CompanyLookupAction.getCompanyInfo(new List<IR_CompanyLookupAction.LookupInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].companyInfo;
            }
            when 'coverage_check' {
                IR_CoverageCheckAction.CoverageInput inp = new IR_CoverageCheckAction.CoverageInput();
                inp.query = query;
                List<IR_CoverageCheckAction.CoverageOutput> out =
                    IR_CoverageCheckAction.getCoverageInfo(new List<IR_CoverageCheckAction.CoverageInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].coverageInfo;
            }
            when 'earnings_calendar' {
                IR_EarningsCalendarAction.CalendarInput inp = new IR_EarningsCalendarAction.CalendarInput();
                inp.query = query;
                List<IR_EarningsCalendarAction.CalendarOutput> out =
                    IR_EarningsCalendarAction.getEarningsCalendar(new List<IR_EarningsCalendarAction.CalendarInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].earningsCalendar;
            }
            when 'watchlist' {
                IR_WatchlistAction.WatchlistInput inp = new IR_WatchlistAction.WatchlistInput();
                inp.query = query;
                List<IR_WatchlistAction.WatchlistOutput> out =
                    IR_WatchlistAction.getWatchlist(new List<IR_WatchlistAction.WatchlistInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].watchlistInfo;
            }
            when 'compliance_screening' {
                IR_ComplianceScreeningAction.ScreeningInput inp = new IR_ComplianceScreeningAction.ScreeningInput();
                inp.ticker = query;
                List<IR_ComplianceScreeningAction.ScreeningOutput> out =
                    IR_ComplianceScreeningAction.checkCompliance(new List<IR_ComplianceScreeningAction.ScreeningInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].complianceResult;
            }
            when 'sec_filings' {
                IR_SecFilingsAction.FilingInput inp = new IR_SecFilingsAction.FilingInput();
                inp.query = query;
                List<IR_SecFilingsAction.FilingOutput> out =
                    IR_SecFilingsAction.getSecFilings(new List<IR_SecFilingsAction.FilingInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].filingInfo;
            }
            when 'market_data' {
                IR_MarketDataAction.MarketInput inp = new IR_MarketDataAction.MarketInput();
                inp.query = query;
                List<IR_MarketDataAction.MarketOutput> out =
                    IR_MarketDataAction.getMarketData(new List<IR_MarketDataAction.MarketInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].marketData;
            }
            when 'news_search' {
                IR_NewsSearchAction.NewsInput inp = new IR_NewsSearchAction.NewsInput();
                inp.query = query;
                List<IR_NewsSearchAction.NewsOutput> out =
                    IR_NewsSearchAction.searchNews(new List<IR_NewsSearchAction.NewsInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].newsResults;
            }
            when 'financial_analysis' {
                IR_FinancialAnalysisAction.AnalysisInput inp = new IR_FinancialAnalysisAction.AnalysisInput();
                inp.query = query;
                List<IR_FinancialAnalysisAction.AnalysisOutput> out =
                    IR_FinancialAnalysisAction.runAnalysis(new List<IR_FinancialAnalysisAction.AnalysisInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].analysisResult;
            }
            when 'sentiment_analysis' {
                IR_SentimentAnalysisAction.SentimentInput inp = new IR_SentimentAnalysisAction.SentimentInput();
                inp.query = query;
                List<IR_SentimentAnalysisAction.SentimentOutput> out =
                    IR_SentimentAnalysisAction.analyzeSentiment(new List<IR_SentimentAnalysisAction.SentimentInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].sentimentResult;
            }
            when 'research_brief' {
                IR_ResearchBriefAction.BriefInput inp = new IR_ResearchBriefAction.BriefInput();
                inp.query = query;
                List<IR_ResearchBriefAction.BriefOutput> out =
                    IR_ResearchBriefAction.generateBrief(new List<IR_ResearchBriefAction.BriefInput>{ inp });
                return out.isEmpty() ? 'No results.' : out[0].briefResult;
            }
            when else {
                return 'I could not determine the right action for your query. Please try rephrasing.';
            }
        }
    }
}
