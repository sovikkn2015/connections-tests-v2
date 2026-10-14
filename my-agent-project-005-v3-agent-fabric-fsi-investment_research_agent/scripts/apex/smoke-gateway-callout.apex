// =============================================================================
// smoke-gateway-callout.apex
// -----------------------------------------------------------------------------
// Post-deploy smoke test for V3 Apex -> Flex Gateway integration.
//
// Preconditions:
//   1. GATEWAY subagent has deployed the Flex Gateway ALB (URL exists).
//   2. The FlexGatewayUrl custom label has been updated to that URL (or
//      IR_FlexGateway named credential endpoint has been set).
//   3. The External Credential IR_FlexGateway_EC has a valid principal
//      (mTLS client cert OR fallback x-api-key).
//   4. The running user has the IR_Compliance_Access / Apex class access
//      permission set applied.
//
// Run it:
//   sf apex run --file scripts/apex/smoke-gateway-callout.apex -o <alias>
//
// Expected: every tool returns a non-500 status. 200 means the tool
// responded with data; 429/503 mean the gateway applied its own policy
// (rate-limit / circuit-breaker) -- those are still "PASS" from the
// Apex side because we reached the gateway.
// =============================================================================

System.debug('=== V3 Flex Gateway smoke test - START ===');

// Use a stable correlation id so all calls in this run can be grouped in the
// FINRA audit stream.
String runId = 'smoke-' + System.now().getTime();
IR_FlexGatewayClient.setCorrelationId(runId);
System.debug('Correlation-Id for this run: ' + runId);

Integer passed = 0;
Integer failed = 0;
List<String> results = new List<String>();

// ------------------------------------------------------------ MCP tool probes

List<Map<String, Object>> mcpProbes = new List<Map<String, Object>>{
    new Map<String, Object>{ 'server' => 'sec-edgar',   'tool' => 'get_10k',              'args' => new Map<String, Object>{ 'ticker' => 'NVDA' } },
    new Map<String, Object>{ 'server' => 'sec-edgar',   'tool' => 'get_10q',              'args' => new Map<String, Object>{ 'ticker' => 'AAPL' } },
    new Map<String, Object>{ 'server' => 'sec-edgar',   'tool' => 'get_8k',               'args' => new Map<String, Object>{ 'ticker' => 'MSFT' } },
    new Map<String, Object>{ 'server' => 'market-data', 'tool' => 'get_quote',            'args' => new Map<String, Object>{ 'ticker' => 'NVDA' } },
    new Map<String, Object>{ 'server' => 'market-data', 'tool' => 'get_price_history',    'args' => new Map<String, Object>{ 'ticker' => 'NVDA', 'period' => 30 } },
    new Map<String, Object>{ 'server' => 'market-data', 'tool' => 'get_analyst_consensus','args' => new Map<String, Object>{ 'ticker' => 'NVDA' } },
    new Map<String, Object>{ 'server' => 'news-search', 'tool' => 'search_financial_news','args' => new Map<String, Object>{ 'ticker' => 'NVDA' } },
    new Map<String, Object>{ 'server' => 'news-search', 'tool' => 'get_headlines',        'args' => new Map<String, Object>{ 'ticker' => 'NVDA' } },
    new Map<String, Object>{ 'server' => 'news-search', 'tool' => 'get_news_sentiment',   'args' => new Map<String, Object>{ 'ticker' => 'NVDA' } }
};

for (Map<String, Object> probe : mcpProbes) {
    String label = probe.get('server') + '.' + probe.get('tool');
    try {
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            (String) probe.get('server'),
            (String) probe.get('tool'),
            (Map<String, Object>) probe.get('args')
        );
        Integer status = resp.getStatusCode();
        Boolean ok = status < 500;
        if (ok) {
            passed++;
            results.add('PASS ' + label + ' -> ' + status);
        } else {
            failed++;
            String snippet = resp.getBody() != null && resp.getBody().length() > 200
                ? resp.getBody().substring(0, 200) : resp.getBody();
            results.add('FAIL ' + label + ' -> ' + status + ' body: ' + snippet);
        }
    } catch (Exception e) {
        failed++;
        results.add('FAIL ' + label + ' -> exception: ' + e.getMessage());
    }
}

// -------------------------------------------------------- Strands agent probes

List<Map<String, Object>> agentProbes = new List<Map<String, Object>>{
    new Map<String, Object>{ 'agent' => 'financial-analysis', 'prompt' => 'Run DCF on NVDA',
                             'context' => new Map<String, Object>{ 'ticker' => 'NVDA' } },
    new Map<String, Object>{ 'agent' => 'sentiment-analysis', 'prompt' => 'Score news sentiment for NVDA',
                             'context' => new Map<String, Object>{ 'ticker' => 'NVDA' } }
};

for (Map<String, Object> probe : agentProbes) {
    String label = 'agent:' + probe.get('agent');
    try {
        HttpResponse resp = IR_FlexGatewayClient.callAgent(
            (String) probe.get('agent'),
            (String) probe.get('prompt'),
            (Map<String, Object>) probe.get('context')
        );
        Integer status = resp.getStatusCode();
        Boolean ok = status < 500;
        if (ok) {
            passed++;
            results.add('PASS ' + label + ' -> ' + status);
        } else {
            failed++;
            results.add('FAIL ' + label + ' -> ' + status);
        }
    } catch (Exception e) {
        failed++;
        results.add('FAIL ' + label + ' -> exception: ' + e.getMessage());
    }
}

// --------------------------------------------------------------- summary debug

System.debug('=== V3 Flex Gateway smoke test - RESULTS ===');
for (String line : results) {
    System.debug(line);
}
System.debug('TOTAL: ' + (passed + failed) + ' | PASS: ' + passed + ' | FAIL: ' + failed);

if (failed > 0) {
    System.debug('SMOKE FAILED - check the debug log lines above.');
} else {
    System.debug('SMOKE PASSED - every tool returned a non-500 status.');
}

System.debug('=== V3 Flex Gateway smoke test - END ===');
