/**
 * IR_ResearchBriefAction — Orchestrates ALL actions into a comprehensive IR_Research_Note__c.
 */
public with sharing class IR_ResearchBriefAction {

    public class BriefInput {
        @InvocableVariable(label='Query' description='e.g. "NVDA research brief"' required=true)
        public String query;
    }

    public class BriefOutput {
        @InvocableVariable(label='Brief Result' description='Formatted research brief')
        public String briefResult;
        @InvocableVariable(label='Research Note Id' description='Id of created IR_Research_Note__c')
        public String researchNoteId;
    }

    @InvocableMethod(
        label='Generate Research Brief'
        description='Orchestrates all research actions into a comprehensive research brief'
    )
    public static List<BriefOutput> generateBrief(List<BriefInput> inputs) {
        List<BriefOutput> outputs = new List<BriefOutput>();
        Long startTime = System.currentTimeMillis();
        String traceId = null;
        try {
            traceId = IR_LangfuseTracer.createTrace(
                'research_brief', inputs[0].query,
                new Map<String, Object>{'platform' => 'Salesforce', 'agent' => 'IR_Research_Agent', 'orchestration' => true}
            );
        } catch (Exception traceEx) {
            System.debug('Langfuse createTrace failed: ' + traceEx.getMessage());
        }

        for (BriefInput input : inputs) {
            BriefOutput output = new BriefOutput();
            try {
                String rawQuery = input.query != null ? input.query.trim() : '';
                String ticker = extractTicker(rawQuery);
                if (String.isBlank(ticker)) {
                    output.briefResult = 'Please provide a ticker — e.g. "NVDA research brief".';
                    outputs.add(output);
                    continue;
                }
                Map<String, String> sections = orchestrateResearch(ticker, traceId, startTime);
                String brief = assembleBrief(ticker, sections);
                brief = IR_MnpiGuard.filterForExternalCaller(ticker, 'company_info', brief, 'IR_Research_Agent');
                String noteId = createResearchNote(ticker, brief, sections);
                output.briefResult = brief;
                output.researchNoteId = noteId;
            } catch (Exception e) {
                output.briefResult = 'Research brief generation failed: ' + e.getMessage();
                output.researchNoteId = '';
            }
            outputs.add(output);
        }

        Long durationMs = System.currentTimeMillis() - startTime;
        for (Integer i = 0; i < inputs.size(); i++) {
            try {
                IR_AuditLogAction.logInteraction(
                    'IR_Research_Agent', 'research_brief', inputs[i].query,
                    UserInfo.getName(), 'Orchestration', traceId, 'Salesforce', durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }
        }
        if (traceId != null) {
            try {
                String spanOut = outputs.isEmpty() ? '' : (outputs[0].briefResult != null ? outputs[0].briefResult : '');
                IR_LangfuseTracer.endTrace(traceId,
                    spanOut.length() > 500 ? spanOut.substring(0, 500) : spanOut,
                    JSON.serialize(new Map<String, Object>{'durationMs' => durationMs}));
            } catch (Exception spanEx) {
                System.debug('Langfuse endTrace failed: ' + spanEx.getMessage());
            }
        }
        return outputs;
    }

    private static Map<String, String> orchestrateResearch(String ticker, String traceId, Long overallStart) {
        Map<String, String> sections = new Map<String, String>();

        // 1. Company Lookup
        Long s1 = System.currentTimeMillis();
        try {
            IR_CompanyLookupAction.LookupInput inp = new IR_CompanyLookupAction.LookupInput();
            inp.companyName = ticker;
            List<IR_CompanyLookupAction.LookupOutput> out =
                IR_CompanyLookupAction.getCompanyInfo(new List<IR_CompanyLookupAction.LookupInput>{ inp });
            sections.put('company', out.isEmpty() ? 'N/A' : out[0].companyInfo);
        } catch (Exception e) { sections.put('company', 'Company lookup failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_company_lookup', ticker, sections.get('company'), s1);

        // 2. Coverage
        Long s2 = System.currentTimeMillis();
        try {
            IR_CoverageCheckAction.CoverageInput inp = new IR_CoverageCheckAction.CoverageInput();
            inp.query = ticker;
            List<IR_CoverageCheckAction.CoverageOutput> out =
                IR_CoverageCheckAction.getCoverageInfo(new List<IR_CoverageCheckAction.CoverageInput>{ inp });
            sections.put('coverage', out.isEmpty() ? 'N/A' : out[0].coverageInfo);
        } catch (Exception e) { sections.put('coverage', 'Coverage check failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_coverage', ticker, sections.get('coverage'), s2);

        // 3. SEC Filings
        Long s3 = System.currentTimeMillis();
        try {
            IR_SecFilingsAction.FilingInput inp = new IR_SecFilingsAction.FilingInput();
            inp.query = ticker + ' 10-K';
            List<IR_SecFilingsAction.FilingOutput> out =
                IR_SecFilingsAction.getSecFilings(new List<IR_SecFilingsAction.FilingInput>{ inp });
            sections.put('sec_filings', out.isEmpty() ? 'N/A' : out[0].filingInfo);
        } catch (Exception e) { sections.put('sec_filings', 'SEC filings failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_sec_filings', ticker, sections.get('sec_filings'), s3);

        // 4. Market Data
        Long s4 = System.currentTimeMillis();
        try {
            IR_MarketDataAction.MarketInput inp = new IR_MarketDataAction.MarketInput();
            inp.query = ticker + ' quote';
            List<IR_MarketDataAction.MarketOutput> out =
                IR_MarketDataAction.getMarketData(new List<IR_MarketDataAction.MarketInput>{ inp });
            sections.put('market_data', out.isEmpty() ? 'N/A' : out[0].marketData);
        } catch (Exception e) { sections.put('market_data', 'Market data failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_market_data', ticker, sections.get('market_data'), s4);

        // 5. Financial Analysis
        Long s5 = System.currentTimeMillis();
        try {
            IR_FinancialAnalysisAction.AnalysisInput inp = new IR_FinancialAnalysisAction.AnalysisInput();
            inp.query = ticker + ' fair value';
            List<IR_FinancialAnalysisAction.AnalysisOutput> out =
                IR_FinancialAnalysisAction.runAnalysis(new List<IR_FinancialAnalysisAction.AnalysisInput>{ inp });
            sections.put('financial_analysis', out.isEmpty() ? 'N/A' : out[0].analysisResult);
        } catch (Exception e) { sections.put('financial_analysis', 'Financial analysis failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_financial_analysis', ticker, sections.get('financial_analysis'), s5);

        // 6. Sentiment
        Long s6 = System.currentTimeMillis();
        try {
            IR_SentimentAnalysisAction.SentimentInput inp = new IR_SentimentAnalysisAction.SentimentInput();
            inp.query = ticker + ' sentiment';
            List<IR_SentimentAnalysisAction.SentimentOutput> out =
                IR_SentimentAnalysisAction.analyzeSentiment(new List<IR_SentimentAnalysisAction.SentimentInput>{ inp });
            sections.put('sentiment', out.isEmpty() ? 'N/A' : out[0].sentimentResult);
        } catch (Exception e) { sections.put('sentiment', 'Sentiment analysis failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_sentiment', ticker, sections.get('sentiment'), s6);

        // 7. Compliance
        Long s7 = System.currentTimeMillis();
        try {
            IR_ComplianceAgentAction.ComplianceInput inp = new IR_ComplianceAgentAction.ComplianceInput();
            inp.ticker = ticker;
            inp.checkType = 'all';
            List<IR_ComplianceAgentAction.ComplianceOutput> out =
                IR_ComplianceAgentAction.runComplianceAgent(new List<IR_ComplianceAgentAction.ComplianceInput>{ inp });
            sections.put('compliance', out.isEmpty() ? 'N/A' : out[0].complianceResult);
        } catch (Exception e) { sections.put('compliance', 'Compliance check failed: ' + e.getMessage()); }
        logSpan(traceId, 'brief_compliance', ticker, sections.get('compliance'), s7);

        return sections;
    }

    private static void logSpan(String traceId, String name, String ticker, String result, Long sectionStart) {
        if (traceId != null) {
            try {
                Long dur = System.currentTimeMillis() - sectionStart;
                String spanOut = result != null && result.length() > 300 ? result.substring(0, 300) : result;
                IR_LangfuseTracer.addSpan(traceId, name, ticker, spanOut, dur, null, 'Salesforce');
            } catch (Exception e) {
                System.debug('Langfuse span failed for ' + name + ': ' + e.getMessage());
            }
        }
    }

    private static String assembleBrief(String ticker, Map<String, String> sections) {
        String brief = '========================================\n';
        brief += '  INVESTMENT RESEARCH BRIEF: ' + ticker + '\n';
        brief += '  Generated: ' + DateTime.now().format('yyyy-MM-dd HH:mm:ss z') + '\n';
        brief += '  Analyst: ' + UserInfo.getName() + '\n';
        brief += '========================================\n\n';
        brief += '--- COMPANY OVERVIEW ---\n' + safeSection(sections.get('company')) + '\n\n';
        brief += '--- ANALYST COVERAGE ---\n' + safeSection(sections.get('coverage')) + '\n\n';
        brief += '--- SEC FILINGS ---\n' + safeSection(sections.get('sec_filings')) + '\n\n';
        brief += '--- MARKET DATA ---\n' + safeSection(sections.get('market_data')) + '\n\n';
        brief += '--- FINANCIAL ANALYSIS ---\n' + safeSection(sections.get('financial_analysis')) + '\n\n';
        brief += '--- SENTIMENT ANALYSIS ---\n' + safeSection(sections.get('sentiment')) + '\n\n';
        brief += '--- COMPLIANCE SCREENING ---\n' + safeSection(sections.get('compliance')) + '\n\n';
        brief += '========================================\n';
        brief += '  END OF RESEARCH BRIEF\n';
        brief += '========================================';
        return brief;
    }

    private static String createResearchNote(String ticker, String brief, Map<String, String> sections) {
        try {
            IR_Research_Note__c note = new IR_Research_Note__c(
                Name = ticker + ' Research Brief - ' + Date.today().format(),
                Ticker__c = ticker,
                Full_Brief__c = brief.length() > 131072 ? brief.substring(0, 131072) : brief,
                Analyst__c = UserInfo.getName(),
                Generated_Date__c = DateTime.now(),
                Status__c = 'Draft'
            );
            insert note;
            return note.Id;
        } catch (Exception e) {
            System.debug('Failed to create IR_Research_Note__c: ' + e.getMessage());
            return '';
        }
    }

    private static String extractTicker(String query) {
        if (String.isBlank(query)) return '';
        for (String word : query.split('\\s+')) {
            String cleaned = word.replaceAll('[^A-Za-z]', '').toUpperCase();
            if (cleaned.length() >= 1 && cleaned.length() <= 5 && !isBriefKeyword(cleaned)) {
                return cleaned;
            }
        }
        return '';
    }

    private static Boolean isBriefKeyword(String word) {
        Set<String> keywords = new Set<String>{
            'GET', 'THE', 'FOR', 'AND', 'SHOW', 'FULL', 'BRIEF', 'RESEARCH',
            'NOTE', 'ANALYSIS', 'GENERATE', 'CREATE', 'RUN', 'BUILD'
        };
        return keywords.contains(word);
    }

    private static String safeSection(String value) {
        return String.isNotBlank(value) ? value : 'Data not available.';
    }
}
