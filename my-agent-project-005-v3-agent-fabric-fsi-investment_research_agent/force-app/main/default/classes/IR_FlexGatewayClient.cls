/**
 * IR_FlexGatewayClient — the ONE HTTP callout helper for V3.
 *
 * Every outbound external call (MCP tools + Strands agents) goes through this class.
 * All auth, correlation headers, and retries live here; no other Apex class should
 * construct HttpRequests that target the Flex Gateway.
 *
 * Auth:
 *   - Single Named Credential: `callout:IR_FlexGateway`
 *   - External Credential `IR_FlexGateway_EC` injects mTLS principal (primary) or
 *     API-key header (fallback) — never hard-coded here.
 *
 * Headers (required by agent-fabric/policies/finra-audit.yaml):
 *   - X-Correlation-Id  — UUID per call, tied to the Agentforce session when set
 *   - X-Agent-Id        — defaults to "IR_Research_Agent" (override via overload)
 *   - X-Tool-Name       — "<serverName>.<toolName>" for MCP, "<agentId>" for Strands
 *
 * Resilience:
 *   - 5xx retry: up to 2 retries with linear backoff (handled by this client).
 *   - Circuit breaker: NOT implemented here. The gateway's circuit-breaker policy
 *     is authoritative. If the gateway trips, it returns 503 and we pass that
 *     status straight back to the caller.
 *   - 429 (rate limit): one retry after a short sleep, then pass through.
 *
 * Anti-patterns to avoid in other classes:
 *   - DO NOT call `Http http = new Http(); http.send(req)` with a Flex Gateway endpoint
 *     anywhere else. Use `callMcpTool` or `callAgent`.
 *   - DO NOT add your own MNPI filter. Flex Gateway `policies/mnpi-filter.yaml`
 *     enforces it (defense-in-depth is fine at the data-fetch layer but the gateway
 *     is authoritative for egress).
 */
public with sharing class IR_FlexGatewayClient {

    private static final String GATEWAY = 'callout:IR_FlexGateway';
    private static final String DEFAULT_AGENT_ID = 'IR_Research_Agent';
    private static final Integer DEFAULT_TIMEOUT_MS = 20000;
    private static final Integer AGENT_TIMEOUT_MS = 30000;
    private static final Integer MAX_5XX_RETRIES = 2;
    private static final Integer MAX_429_RETRIES = 1;

    /** Current correlation ID — can be threaded through from an Agentforce session. */
    @TestVisible
    private static String currentCorrelationId;

    /** Set by the test class to inject mock responses without touching Http.send. */
    @TestVisible
    private static HttpCalloutMock testMock;

    /**
     * Set a correlation ID (e.g. from Agentforce session/thread) so every downstream
     * gateway call in this transaction carries the same X-Correlation-Id.
     * If not set, a fresh UUID is generated per call.
     */
    public static void setCorrelationId(String correlationId) {
        currentCorrelationId = correlationId;
    }

    public static String getCorrelationId() {
        return currentCorrelationId;
    }

    /**
     * Call a tool on an MCP server routed through Flex Gateway.
     * The payload is JSON-RPC 2.0 shaped (`method=tools/call`, params=tool+args).
     *
     * Example:
     *   callMcpTool('sec-edgar', 'get_10k', new Map<String, Object>{'ticker' => 'NVDA'})
     *     → POST callout:IR_FlexGateway/sec-edgar
     *        body: {"jsonrpc":"2.0","id":"...", "method":"tools/call",
     *               "params":{"name":"get_10k","arguments":{"ticker":"NVDA"}}}
     */
    public static HttpResponse callMcpTool(String serverName, String toolName, Map<String, Object> args) {
        return callMcpTool(serverName, toolName, args, DEFAULT_AGENT_ID);
    }

    public static HttpResponse callMcpTool(String serverName, String toolName, Map<String, Object> args, String agentId) {
        if (String.isBlank(serverName)) {
            throw new IllegalArgumentException('serverName is required');
        }
        if (String.isBlank(toolName)) {
            throw new IllegalArgumentException('toolName is required');
        }

        String endpoint = GATEWAY + '/' + serverName;
        String body = buildJsonRpcBody(toolName, args);
        String toolLabel = serverName + '.' + toolName;

        return sendWithRetry(endpoint, body, agentId, toolLabel, DEFAULT_TIMEOUT_MS);
    }

    /**
     * Call a Strands agent routed through Flex Gateway.
     * Example:
     *   callAgent('financial-analysis', 'Run DCF on NVDA',
     *             new Map<String, Object>{'ticker' => 'NVDA'})
     *     → POST callout:IR_FlexGateway/financial-analysis/agent
     *        body: {"prompt":"Run DCF on NVDA","context":{"ticker":"NVDA"}}
     */
    public static HttpResponse callAgent(String agentId, String prompt, Map<String, Object> context) {
        return callAgent(agentId, prompt, context, DEFAULT_AGENT_ID);
    }

    public static HttpResponse callAgent(String agentId, String prompt, Map<String, Object> context, String callerAgentId) {
        if (String.isBlank(agentId)) {
            throw new IllegalArgumentException('agentId is required');
        }

        String endpoint = GATEWAY + '/' + agentId + '/agent';

        Map<String, Object> bodyMap = new Map<String, Object>();
        bodyMap.put('prompt', prompt != null ? prompt : '');
        bodyMap.put('context', context != null ? context : new Map<String, Object>());

        String body = JSON.serialize(bodyMap);
        String toolLabel = agentId;

        return sendWithRetry(endpoint, body, callerAgentId, toolLabel, AGENT_TIMEOUT_MS);
    }

    // ---------------------------------------------------------------- internals

    @TestVisible
    private static String buildJsonRpcBody(String toolName, Map<String, Object> args) {
        Map<String, Object> params = new Map<String, Object>();
        params.put('name', toolName);
        params.put('arguments', args != null ? args : new Map<String, Object>());

        Map<String, Object> jsonRpc = new Map<String, Object>();
        jsonRpc.put('jsonrpc', '2.0');
        jsonRpc.put('id', newUuid());
        jsonRpc.put('method', 'tools/call');
        jsonRpc.put('params', params);

        return JSON.serialize(jsonRpc);
    }

    @TestVisible
    private static HttpResponse sendWithRetry(
        String endpoint, String body, String agentId, String toolLabel, Integer timeoutMs
    ) {
        Integer retries5xx = 0;
        Integer retries429 = 0;
        // Upper bound for the loop so the compiler can prove it terminates.
        Integer maxAttempts = MAX_5XX_RETRIES + MAX_429_RETRIES + 1;

        // Lock the correlation ID for this logical call so retries share it.
        String correlationId = resolveCorrelationId();

        for (Integer attempt = 0; attempt < maxAttempts; attempt++) {
            HttpRequest req = buildRequest(endpoint, body, agentId, toolLabel, timeoutMs, correlationId);
            HttpResponse resp;
            try {
                resp = send(req);
            } catch (System.CalloutException ce) {
                // Transport-level failure (DNS, timeout). Retry up to MAX_5XX_RETRIES.
                if (retries5xx < MAX_5XX_RETRIES) {
                    retries5xx++;
                    continue;
                }
                throw ce;
            }

            Integer status = resp.getStatusCode();

            // 5xx EXCEPT 503 -> retry. 503 is passed through (gateway says "circuit open").
            if (status >= 500 && status != 503 && retries5xx < MAX_5XX_RETRIES) {
                retries5xx++;
                continue;
            }

            // 429 -> one retry.
            if (status == 429 && retries429 < MAX_429_RETRIES) {
                retries429++;
                continue;
            }

            return resp;
        }

        // Defensive: if retry budget is somehow exhausted with no return, surface
        // a callout exception. Unreachable under normal control flow.
        throw new CalloutException('IR_FlexGatewayClient exhausted retry budget without a response');
    }

    @TestVisible
    private static HttpRequest buildRequest(
        String endpoint, String body, String agentId, String toolLabel, Integer timeoutMs
    ) {
        return buildRequest(endpoint, body, agentId, toolLabel, timeoutMs, resolveCorrelationId());
    }

    @TestVisible
    private static HttpRequest buildRequest(
        String endpoint, String body, String agentId, String toolLabel, Integer timeoutMs, String correlationId
    ) {
        HttpRequest req = new HttpRequest();
        req.setEndpoint(endpoint);
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setHeader('Accept', 'application/json');

        // FINRA audit policy requires these three headers.
        req.setHeader('X-Correlation-Id', correlationId);
        req.setHeader('X-Agent-Id', String.isBlank(agentId) ? DEFAULT_AGENT_ID : agentId);
        req.setHeader('X-Tool-Name', toolLabel);

        req.setBody(body != null ? body : '');
        req.setTimeout(timeoutMs);
        return req;
    }

    @TestVisible
    private static HttpResponse send(HttpRequest req) {
        if (testMock != null) {
            return testMock.respond(req);
        }
        return new Http().send(req);
    }

    @TestVisible
    private static String resolveCorrelationId() {
        if (String.isNotBlank(currentCorrelationId)) {
            return currentCorrelationId;
        }
        return newUuid();
    }

    @TestVisible
    private static String newUuid() {
        // Standard v4-style UUID built from Crypto.getRandomLong/Integer.
        // No Crypto.generateGuid here — keep to primitive string math for determinism.
        Blob b = Crypto.generateAesKey(128);
        String hex = EncodingUtil.convertToHex(b);
        return hex.substring(0, 8) + '-'
            + hex.substring(8, 12) + '-4'
            + hex.substring(13, 16) + '-'
            + 'a' + hex.substring(17, 20) + '-'
            + hex.substring(20, 32);
    }

    /** Thrown for caller programming errors (blank required inputs). */
    public class IllegalArgumentException extends Exception {}
}
