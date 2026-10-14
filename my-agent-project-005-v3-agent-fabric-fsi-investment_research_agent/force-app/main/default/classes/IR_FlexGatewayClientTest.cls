@isTest
private class IR_FlexGatewayClientTest {

    // --- Mock helpers -------------------------------------------------------

    /**
     * Scriptable mock. Records each request it sees so we can assert on headers
     * and body content later. Supports a queue of responses so retry paths can
     * be exercised (first = 503, second = 200, etc.).
     */
    private class ScriptedMock implements HttpCalloutMock {
        public List<HttpRequest> seenRequests = new List<HttpRequest>();
        public List<Integer> statuses = new List<Integer>();
        public List<String> bodies = new List<String>();
        public Integer callIndex = 0;

        public HttpResponse respond(HttpRequest req) {
            // Snapshot a copy of the request so assertions see each call independently.
            HttpRequest snap = new HttpRequest();
            snap.setEndpoint(req.getEndpoint());
            snap.setMethod(req.getMethod());
            snap.setBody(req.getBody());
            for (String h : new List<String>{
                'Content-Type', 'Accept',
                'X-Correlation-Id', 'X-Agent-Id', 'X-Tool-Name'
            }) {
                String v = req.getHeader(h);
                if (v != null) {
                    snap.setHeader(h, v);
                }
            }
            seenRequests.add(snap);

            Integer i = Math.min(callIndex, statuses.size() - 1);
            HttpResponse resp = new HttpResponse();
            resp.setStatusCode(statuses[i]);
            resp.setBody(bodies[i]);
            resp.setHeader('Content-Type', 'application/json');
            callIndex++;
            return resp;
        }
    }

    private class FailingTransportMock implements HttpCalloutMock {
        public Integer attempts = 0;
        public Integer failUntilAttempt;
        public FailingTransportMock(Integer failUntilAttempt) {
            this.failUntilAttempt = failUntilAttempt;
        }
        public HttpResponse respond(HttpRequest req) {
            attempts++;
            if (attempts <= failUntilAttempt) {
                throw new CalloutException('simulated transport failure #' + attempts);
            }
            HttpResponse resp = new HttpResponse();
            resp.setStatusCode(200);
            resp.setBody('{"ok":true,"attempt":' + attempts + '}');
            return resp;
        }
    }

    // --- Tests --------------------------------------------------------------

    @isTest
    static void callMcpTool_happyPath_returns200AndInjectsRequiredHeaders() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(200);
        mock.bodies.add('{"jsonrpc":"2.0","id":"abc","result":{"filings":[]}}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            'sec-edgar', 'get_10k', new Map<String, Object>{ 'ticker' => 'NVDA' }
        );
        Test.stopTest();

        System.assertEquals(200, resp.getStatusCode(), 'Happy path should return 200');
        System.assertEquals(1, mock.seenRequests.size(), 'Exactly one HTTP call');

        HttpRequest req = mock.seenRequests[0];
        System.assert(req.getEndpoint().endsWith('/sec-edgar'),
            'Endpoint should route to /sec-edgar on the Flex Gateway');
        System.assertEquals('POST', req.getMethod());
        System.assertEquals('application/json', req.getHeader('Content-Type'));

        // FINRA audit headers required on every request.
        System.assertNotEquals(null, req.getHeader('X-Correlation-Id'), 'X-Correlation-Id must be set');
        System.assert(String.isNotBlank(req.getHeader('X-Correlation-Id')), 'X-Correlation-Id must be non-blank');
        System.assertEquals('IR_Research_Agent', req.getHeader('X-Agent-Id'));
        System.assertEquals('sec-edgar.get_10k', req.getHeader('X-Tool-Name'));

        // JSON-RPC shape.
        Map<String, Object> sent = (Map<String, Object>) JSON.deserializeUntyped(req.getBody());
        System.assertEquals('2.0', sent.get('jsonrpc'));
        System.assertEquals('tools/call', sent.get('method'));
        Map<String, Object> params = (Map<String, Object>) sent.get('params');
        System.assertEquals('get_10k', params.get('name'));
        Map<String, Object> argsOut = (Map<String, Object>) params.get('arguments');
        System.assertEquals('NVDA', argsOut.get('ticker'));
    }

    @isTest
    static void callMcpTool_429_retriesOnceThenReturnsStatus() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(429);  // first attempt throttled
        mock.statuses.add(200);  // retry succeeds
        mock.bodies.add('{"error":"rate_limited"}');
        mock.bodies.add('{"jsonrpc":"2.0","result":"ok"}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            'market-data', 'get_quote', new Map<String, Object>{ 'ticker' => 'AAPL' }
        );
        Test.stopTest();

        System.assertEquals(200, resp.getStatusCode(), 'Retry after 429 should succeed');
        System.assertEquals(2, mock.seenRequests.size(), 'Client should retry once on 429');

        // Correlation ID should be identical across retry (same transaction).
        String cid1 = mock.seenRequests[0].getHeader('X-Correlation-Id');
        String cid2 = mock.seenRequests[1].getHeader('X-Correlation-Id');
        System.assertEquals(cid1, cid2, 'Retry must reuse the same X-Correlation-Id');
    }

    @isTest
    static void callMcpTool_503_isPassedThroughNoRetry() {
        // 503 = gateway circuit-breaker is open. Client must NOT retry —
        // it returns immediately so the caller sees the real gateway decision.
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(503);
        mock.bodies.add('{"error":"circuit_open","retry_after":30}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            'news-search', 'get_news_sentiment', new Map<String, Object>{ 'ticker' => 'NVDA' }
        );
        Test.stopTest();

        System.assertEquals(503, resp.getStatusCode(), '503 must pass through unchanged');
        System.assertEquals(1, mock.seenRequests.size(),
            'Client must not retry on 503 — gateway owns the circuit breaker');
    }

    @isTest
    static void callMcpTool_500_retriesUpToMaxThenReturns() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(500);  // attempt 1
        mock.statuses.add(500);  // retry 1
        mock.statuses.add(500);  // retry 2 (max)
        mock.bodies.add('{"error":"server_error"}');
        mock.bodies.add('{"error":"server_error"}');
        mock.bodies.add('{"error":"server_error"}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            'sec-edgar', 'get_10q', new Map<String, Object>{ 'ticker' => 'NVDA' }
        );
        Test.stopTest();

        System.assertEquals(500, resp.getStatusCode());
        System.assertEquals(3, mock.seenRequests.size(),
            'Client should make initial + 2 retries on 5xx');
    }

    @isTest
    static void callMcpTool_500_thenRecovers_returns200() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(500);  // attempt 1 fails
        mock.statuses.add(200);  // retry succeeds
        mock.bodies.add('{"error":"transient"}');
        mock.bodies.add('{"jsonrpc":"2.0","result":{"quote":{"price":100}}}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            'market-data', 'get_quote', new Map<String, Object>{ 'ticker' => 'AAPL' }
        );
        Test.stopTest();

        System.assertEquals(200, resp.getStatusCode());
        System.assertEquals(2, mock.seenRequests.size());
    }

    @isTest
    static void callMcpTool_setCorrelationId_threadsThroughAllCalls() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(200);
        mock.bodies.add('{"jsonrpc":"2.0","result":{}}');
        IR_FlexGatewayClient.testMock = mock;
        IR_FlexGatewayClient.setCorrelationId('test-session-12345');

        Test.startTest();
        IR_FlexGatewayClient.callMcpTool(
            'sec-edgar', 'get_8k', new Map<String, Object>{ 'ticker' => 'NVDA' }
        );
        Test.stopTest();

        System.assertEquals('test-session-12345',
            mock.seenRequests[0].getHeader('X-Correlation-Id'),
            'Caller-supplied correlation id must be honoured');
        System.assertEquals('test-session-12345', IR_FlexGatewayClient.getCorrelationId());

        IR_FlexGatewayClient.setCorrelationId(null);
    }

    @isTest
    static void callAgent_routesToAgentEndpointWithPromptAndContext() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(200);
        mock.bodies.add('{"response":"DCF complete","fair_value":150.0}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callAgent(
            'financial-analysis',
            'Run DCF on NVDA',
            new Map<String, Object>{ 'ticker' => 'NVDA', 'wacc' => 0.09 }
        );
        Test.stopTest();

        System.assertEquals(200, resp.getStatusCode());
        HttpRequest req = mock.seenRequests[0];
        System.assert(req.getEndpoint().endsWith('/financial-analysis/agent'),
            'Agent calls must route to /<agentId>/agent');
        System.assertEquals('financial-analysis', req.getHeader('X-Tool-Name'));

        Map<String, Object> body = (Map<String, Object>) JSON.deserializeUntyped(req.getBody());
        System.assertEquals('Run DCF on NVDA', body.get('prompt'));
        Map<String, Object> ctx = (Map<String, Object>) body.get('context');
        System.assertEquals('NVDA', ctx.get('ticker'));
    }

    @isTest
    static void callAgent_sentimentAgent_routesCorrectly() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(200);
        mock.bodies.add('{"sentiment":"positive","score":0.72}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callAgent(
            'sentiment-analysis',
            'Score news sentiment for NVDA',
            new Map<String, Object>{ 'ticker' => 'NVDA' }
        );
        Test.stopTest();

        System.assertEquals(200, resp.getStatusCode());
        System.assert(mock.seenRequests[0].getEndpoint().endsWith('/sentiment-analysis/agent'));
    }

    @isTest
    static void callMcpTool_blankServerName_throws() {
        Boolean caught = false;
        try {
            IR_FlexGatewayClient.callMcpTool('', 'get_10k', new Map<String, Object>());
        } catch (IR_FlexGatewayClient.IllegalArgumentException e) {
            caught = true;
        }
        System.assert(caught, 'Blank serverName must throw IllegalArgumentException');
    }

    @isTest
    static void callMcpTool_blankToolName_throws() {
        Boolean caught = false;
        try {
            IR_FlexGatewayClient.callMcpTool('sec-edgar', '', new Map<String, Object>());
        } catch (IR_FlexGatewayClient.IllegalArgumentException e) {
            caught = true;
        }
        System.assert(caught, 'Blank toolName must throw IllegalArgumentException');
    }

    @isTest
    static void callAgent_blankAgentId_throws() {
        Boolean caught = false;
        try {
            IR_FlexGatewayClient.callAgent('', 'prompt', new Map<String, Object>());
        } catch (IR_FlexGatewayClient.IllegalArgumentException e) {
            caught = true;
        }
        System.assert(caught, 'Blank agentId must throw IllegalArgumentException');
    }

    @isTest
    static void callMcpTool_nullArgs_defaultsToEmptyArguments() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(200);
        mock.bodies.add('{"jsonrpc":"2.0","result":{}}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        IR_FlexGatewayClient.callMcpTool('sec-edgar', 'get_10k', null);
        Test.stopTest();

        Map<String, Object> sent = (Map<String, Object>) JSON.deserializeUntyped(
            mock.seenRequests[0].getBody()
        );
        Map<String, Object> params = (Map<String, Object>) sent.get('params');
        Map<String, Object> argsOut = (Map<String, Object>) params.get('arguments');
        System.assertNotEquals(null, argsOut, 'arguments must be an empty object, not null');
        System.assertEquals(0, argsOut.size());
    }

    @isTest
    static void callMcpTool_customAgentId_overridesHeader() {
        ScriptedMock mock = new ScriptedMock();
        mock.statuses.add(200);
        mock.bodies.add('{"jsonrpc":"2.0","result":{}}');
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        IR_FlexGatewayClient.callMcpTool(
            'market-data', 'get_quote',
            new Map<String, Object>{ 'ticker' => 'MSFT' },
            'IR_Compliance_Agent'
        );
        Test.stopTest();

        System.assertEquals('IR_Compliance_Agent',
            mock.seenRequests[0].getHeader('X-Agent-Id'),
            'Custom caller agent id must propagate');
    }

    @isTest
    static void buildJsonRpcBody_isValidJsonRpc20Envelope() {
        String body = IR_FlexGatewayClient.buildJsonRpcBody(
            'get_headlines', new Map<String, Object>{ 'ticker' => 'NVDA', 'limit' => 5 }
        );
        Map<String, Object> parsed = (Map<String, Object>) JSON.deserializeUntyped(body);
        System.assertEquals('2.0', parsed.get('jsonrpc'));
        System.assertEquals('tools/call', parsed.get('method'));
        System.assertNotEquals(null, parsed.get('id'));
        Map<String, Object> params = (Map<String, Object>) parsed.get('params');
        System.assertEquals('get_headlines', params.get('name'));
    }

    @isTest
    static void transportException_isRetriedThenRecovers() {
        FailingTransportMock mock = new FailingTransportMock(1); // fail attempt 1 only
        IR_FlexGatewayClient.testMock = mock;

        Test.startTest();
        HttpResponse resp = IR_FlexGatewayClient.callMcpTool(
            'sec-edgar', 'get_10k', new Map<String, Object>{ 'ticker' => 'NVDA' }
        );
        Test.stopTest();

        System.assertEquals(200, resp.getStatusCode());
        System.assertEquals(2, mock.attempts,
            'Transport failures should retry up to the 5xx retry budget');
    }

    @isTest
    static void transportException_exceedsRetries_bubblesUp() {
        FailingTransportMock mock = new FailingTransportMock(10); // always fail
        IR_FlexGatewayClient.testMock = mock;

        Boolean caught = false;
        Test.startTest();
        try {
            IR_FlexGatewayClient.callMcpTool(
                'sec-edgar', 'get_10k', new Map<String, Object>{ 'ticker' => 'NVDA' }
            );
        } catch (CalloutException e) {
            caught = true;
        }
        Test.stopTest();

        System.assert(caught, 'Persistent transport failures must surface as CalloutException');
        System.assertEquals(3, mock.attempts,
            'Initial + 2 retries = 3 total attempts before giving up');
    }
}
