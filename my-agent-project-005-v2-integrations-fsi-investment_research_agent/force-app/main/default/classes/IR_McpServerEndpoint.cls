/**
 * IR_McpServerEndpoint — Exposes Salesforce CRM data as an MCP-like server.
 * GET  /ir-mcp/tools        — tool catalog
 * POST /ir-mcp/tools/invoke — invoke a tool by name
 * Tools: get_analyst_coverage, get_client_holdings, get_meeting_history, get_company_info
 */
@RestResource(urlMapping='/ir-mcp/*')
global with sharing class IR_McpServerEndpoint {

    private static final Map<String, Map<String, Object>> TOOL_CATALOG = new Map<String, Map<String, Object>>{
        'get_analyst_coverage' => new Map<String, Object>{
            'name' => 'get_analyst_coverage',
            'description' => 'Returns analyst coverage data for a ticker or analyst name',
            'parameters' => new Map<String, Object>{
                'identifier' => new Map<String, String>{'type' => 'string', 'description' => 'Ticker or analyst name'}
            }
        },
        'get_client_holdings' => new Map<String, Object>{
            'name' => 'get_client_holdings',
            'description' => 'Returns client holdings (MNPI-filtered, requires compliance clearance)',
            'parameters' => new Map<String, Object>{
                'ticker' => new Map<String, String>{'type' => 'string', 'description' => 'Stock ticker'}
            }
        },
        'get_meeting_history' => new Map<String, Object>{
            'name' => 'get_meeting_history',
            'description' => 'Returns meeting history for a company or contact',
            'parameters' => new Map<String, Object>{
                'identifier' => new Map<String, String>{'type' => 'string', 'description' => 'Company or contact name'}
            }
        },
        'get_company_info' => new Map<String, Object>{
            'name' => 'get_company_info',
            'description' => 'Returns company master data',
            'parameters' => new Map<String, Object>{
                'identifier' => new Map<String, String>{'type' => 'string', 'description' => 'Company name or ticker'}
            }
        }
    };

    @HttpGet
    global static void handleGet() {
        RestResponse res = RestContext.response;
        res.addHeader('Content-Type', 'application/json');
        String path = RestContext.request.requestURI;
        if (path != null && path.endsWith('/tools')) {
            res.statusCode = 200;
            res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, Object>{
                'tools' => TOOL_CATALOG.values(), 'server' => 'IR_McpServerEndpoint', 'version' => '1.0.0'
            }));
        } else {
            res.statusCode = 404;
            res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, String>{
                'error' => 'Use GET /ir-mcp/tools or POST /ir-mcp/tools/invoke'
            }));
        }
    }

    @HttpPost
    global static void handlePost() {
        RestResponse res = RestContext.response;
        res.addHeader('Content-Type', 'application/json');
        Long startTime = System.currentTimeMillis();
        try {
            Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(
                RestContext.request.requestBody.toString()
            );
            String toolName = (String) body.get('tool');
            Map<String, Object> params = (Map<String, Object>) body.get('parameters');
            String callerAgent = body.containsKey('caller') ? (String) body.get('caller') : 'external_mcp_client';

            if (String.isBlank(toolName)) {
                res.statusCode = 400;
                res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, String>{
                    'error' => 'Missing required field: tool'
                }));
                return;
            }
            if (!TOOL_CATALOG.containsKey(toolName)) {
                res.statusCode = 404;
                res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, String>{
                    'error' => 'Unknown tool: ' + toolName
                }));
                return;
            }

            String result = invokeTool(toolName, params, callerAgent);
            Long durationMs = System.currentTimeMillis() - startTime;

            try {
                IR_AuditLogAction.logInteraction(
                    callerAgent, 'mcp_tool_invoke:' + toolName,
                    JSON.serialize(params), UserInfo.getName(),
                    'IR_McpServerEndpoint', null, 'Salesforce', durationMs
                );
            } catch (Exception auditEx) {
                System.debug('Audit log failed: ' + auditEx.getMessage());
            }

            res.statusCode = 200;
            res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, Object>{
                'tool' => toolName, 'result' => result, 'durationMs' => durationMs
            }));
        } catch (Exception e) {
            res.statusCode = 500;
            res.responseBody = Blob.valueOf(JSON.serialize(new Map<String, String>{
                'error' => 'Tool invocation failed: ' + e.getMessage()
            }));
        }
    }

    private static String invokeTool(String toolName, Map<String, Object> params, String callerAgent) {
        String identifier = params != null && params.containsKey('identifier')
            ? (String) params.get('identifier') : '';
        String ticker = params != null && params.containsKey('ticker')
            ? (String) params.get('ticker') : identifier;

        switch on toolName {
            when 'get_analyst_coverage' { return getAnalystCoverage(identifier); }
            when 'get_client_holdings' { return getClientHoldings(ticker, callerAgent); }
            when 'get_meeting_history' { return getMeetingHistory(identifier); }
            when 'get_company_info' { return getCompanyInfo(identifier); }
            when else { return 'Unknown tool: ' + toolName; }
        }
    }

    private static String getAnalystCoverage(String identifier) {
        String escaped = String.escapeSingleQuotes(identifier);
        String upper = escaped.toUpperCase();
        String likePattern = '%' + escaped + '%';
        List<IR_Coverage__c> coverages = [
            SELECT Analyst__c, Rating__c, Target_Price__c, Last_Updated__c,
                   Company__r.Name, Company__r.Ticker__c
            FROM IR_Coverage__c
            WHERE Company__r.Ticker__c = :upper OR Analyst__c LIKE :likePattern
            ORDER BY Company__r.Ticker__c LIMIT 50
        ];
        if (coverages.isEmpty()) {
            return 'No analyst coverage found for "' + identifier + '".';
        }
        String result = 'Analyst Coverage:\n';
        for (IR_Coverage__c cov : coverages) {
            result += '\n  ' + safeStr(cov.Analyst__c)
                + ' | ' + safeStr(cov.Company__r.Name) + ' (' + safeStr(cov.Company__r.Ticker__c) + ')'
                + ' | ' + safeStr(cov.Rating__c)
                + ' | Target: $' + (cov.Target_Price__c != null ? String.valueOf(cov.Target_Price__c.setScale(2)) : 'N/A');
        }
        return result;
    }

    private static String getClientHoldings(String ticker, String callerAgent) {
        String filtered = IR_MnpiGuard.filterForExternalCaller(ticker, 'holdings', '', callerAgent);
        if (filtered.startsWith('[REDACTED]')) {
            return filtered;
        }
        String upper = String.escapeSingleQuotes(ticker).toUpperCase();
        List<IR_Company__c> companies = [
            SELECT Name, Ticker__c, Sector__c, Market_Cap__c, Last_Price__c
            FROM IR_Company__c WHERE Ticker__c = :upper LIMIT 10
        ];
        if (companies.isEmpty()) {
            return 'No holdings data for "' + ticker + '".';
        }
        String result = 'Holdings for ' + ticker + ':\n';
        for (IR_Company__c c : companies) {
            result += '\n  ' + safeStr(c.Name) + ' (' + safeStr(c.Ticker__c) + ')'
                + ' | Sector: ' + safeStr(c.Sector__c)
                + ' | Price: $' + (c.Last_Price__c != null ? String.valueOf(c.Last_Price__c.setScale(2)) : 'N/A');
        }
        return result;
    }

    private static String getMeetingHistory(String identifier) {
        String likePattern = '%' + String.escapeSingleQuotes(identifier) + '%';
        List<Event> meetings = [
            SELECT Subject, StartDateTime, Who.Name
            FROM Event WHERE Subject LIKE :likePattern
            ORDER BY StartDateTime DESC LIMIT 20
        ];
        if (meetings.isEmpty()) {
            return 'No meeting history for "' + identifier + '".';
        }
        String result = 'Meeting History:\n';
        for (Event evt : meetings) {
            result += '\n  ' + safeStr(evt.Subject)
                + ' | ' + (evt.StartDateTime != null ? evt.StartDateTime.format('yyyy-MM-dd') : 'N/A')
                + ' | ' + safeStr(evt.Who != null ? evt.Who.Name : null);
        }
        return result;
    }

    private static String getCompanyInfo(String identifier) {
        IR_CompanyLookupAction.LookupInput inp = new IR_CompanyLookupAction.LookupInput();
        inp.companyName = identifier;
        List<IR_CompanyLookupAction.LookupOutput> out =
            IR_CompanyLookupAction.getCompanyInfo(new List<IR_CompanyLookupAction.LookupInput>{ inp });
        return out.isEmpty() ? 'No company found.' : out[0].companyInfo;
    }

    private static String safeStr(Object value) {
        return value != null ? String.valueOf(value) : 'N/A';
    }
}
