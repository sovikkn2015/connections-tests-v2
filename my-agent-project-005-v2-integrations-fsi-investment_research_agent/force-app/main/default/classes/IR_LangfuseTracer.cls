public with sharing class IR_LangfuseTracer {

    private static final String NAMED_CREDENTIAL = 'callout:Langfuse_API';
    private static final String INGESTION_PATH = '/api/public/ingestion';

    /**
     * Create a new Langfuse trace. Returns a trace ID for correlating spans.
     */
    public static String createTrace(String name, String input, Map<String, Object> metadata) {
        String traceId = generateTraceId();
        // Store trace data for deferred send — avoids @future before callout
        traceBuffer.add(new Map<String, Object>{
            'id' => traceId,
            'name' => name,
            'input' => input,
            'metadata' => metadata != null ? metadata : new Map<String, Object>()
        });
        return traceId;
    }

    // Buffer for deferred trace creation (sent via @future after callouts complete)
    private static List<Map<String, Object>> traceBuffer = new List<Map<String, Object>>();

    /**
     * Flush buffered traces to Langfuse. Call AFTER all callouts are done.
     */
    @future(callout=true)
    public static void flushTraces(String bufferedJson) {
        try {
            List<Object> items = (List<Object>) JSON.deserializeUntyped(bufferedJson);
            List<Map<String, Object>> events = new List<Map<String, Object>>();
            for (Object item : items) {
                events.add(buildEvent('trace-create', (Map<String, Object>) item));
            }
            postToIngestion(JSON.serialize(events));
        } catch (Exception e) {
            System.debug(LoggingLevel.WARN, 'IR_LangfuseTracer.flushTraces failed: ' + e.getMessage());
        }
    }

    /**
     * Add a span to an existing trace (e.g. a callout, a query, a processing step).
     */
    @future(callout=true)
    public static void addSpan(
        String traceId,
        String spanName,
        String input,
        String output,
        Long durationMs,
        String model,
        String platform
    ) {
        try {
            Map<String, Object> spanBody = new Map<String, Object>{
                'id' => generateEventId(),
                'traceId' => traceId,
                'name' => spanName,
                'input' => input,
                'output' => output,
                'metadata' => new Map<String, Object>{
                    'model' => model,
                    'platform' => platform,
                    'durationMs' => durationMs
                }
            };
            if (durationMs != null) {
                spanBody.put('startTime', DateTime.now().addSeconds(-(Integer)(durationMs / 1000)).formatGmt('yyyy-MM-dd\'T\'HH:mm:ss.SSS\'Z\''));
                spanBody.put('endTime', DateTime.now().formatGmt('yyyy-MM-dd\'T\'HH:mm:ss.SSS\'Z\''));
            }

            String payload = JSON.serialize(new List<Map<String, Object>>{
                buildEvent('span-create', spanBody)
            });
            postToIngestion(payload);
        } catch (Exception e) {
            System.debug(LoggingLevel.WARN, 'IR_LangfuseTracer.addSpan failed: ' + e.getMessage());
        }
    }

    /**
     * Add a generation event to a trace (for LLM calls — Bedrock, Einstein, etc.).
     */
    @future(callout=true)
    public static void addGeneration(
        String traceId,
        String name,
        String model,
        String input,
        String output,
        Integer promptTokens,
        Integer completionTokens
    ) {
        try {
            Map<String, Object> genBody = new Map<String, Object>{
                'id' => generateEventId(),
                'traceId' => traceId,
                'name' => name,
                'model' => model,
                'input' => input,
                'output' => output
            };

            if (promptTokens != null || completionTokens != null) {
                Map<String, Object> usage = new Map<String, Object>();
                if (promptTokens != null) {
                    usage.put('promptTokens', promptTokens);
                }
                if (completionTokens != null) {
                    usage.put('completionTokens', completionTokens);
                }
                if (promptTokens != null && completionTokens != null) {
                    usage.put('totalTokens', promptTokens + completionTokens);
                }
                genBody.put('usage', usage);
            }

            String payload = JSON.serialize(new List<Map<String, Object>>{
                buildEvent('generation-create', genBody)
            });
            postToIngestion(payload);
        } catch (Exception e) {
            System.debug(LoggingLevel.WARN, 'IR_LangfuseTracer.addGeneration failed: ' + e.getMessage());
        }
    }

    /**
     * End a trace by updating it with output and final metadata.
     */
    @future(callout=true)
    public static void endTrace(String traceId, String output, String metadataJson) {
        try {
            Map<String, Object> metadata = String.isNotBlank(metadataJson)
                ? (Map<String, Object>) JSON.deserializeUntyped(metadataJson)
                : new Map<String, Object>();
            Map<String, Object> updateBody = new Map<String, Object>{
                'id' => traceId,
                'output' => output,
                'metadata' => metadata != null ? metadata : new Map<String, Object>()
            };

            String payload = JSON.serialize(new List<Map<String, Object>>{
                buildEvent('trace-create', updateBody)
            });
            postToIngestion(payload);
        } catch (Exception e) {
            System.debug(LoggingLevel.WARN, 'IR_LangfuseTracer.endTrace failed: ' + e.getMessage());
        }
    }

    // ---- Private helpers ----

    /**
     * Fire-and-forget async POST for trace creation (avoids blocking the main thread).
     */
    @future(callout=true)
    private static void sendEventAsync(String batchJson) {
        try {
            postToIngestion(batchJson);
        } catch (Exception e) {
            System.debug(LoggingLevel.WARN, 'IR_LangfuseTracer.sendEventAsync failed: ' + e.getMessage());
        }
    }

    /**
     * POST a batch payload to the Langfuse ingestion endpoint via Named Credential.
     */
    private static void postToIngestion(String batchJson) {
        Map<String, Object> requestBody = new Map<String, Object>{
            'batch' => (List<Object>) JSON.deserializeUntyped(batchJson),
            'metadata' => new Map<String, Object>{
                'sdk_name' => 'salesforce-apex',
                'sdk_version' => '1.0.0'
            }
        };

        HttpRequest req = new HttpRequest();
        req.setEndpoint(NAMED_CREDENTIAL + INGESTION_PATH);
        req.setMethod('POST');
        req.setHeader('Content-Type', 'application/json');
        req.setBody(JSON.serialize(requestBody));
        req.setTimeout(10000);

        Http http = new Http();
        HttpResponse res = http.send(req);

        if (res.getStatusCode() < 200 || res.getStatusCode() >= 300) {
            System.debug(LoggingLevel.WARN,
                'Langfuse ingestion returned ' + res.getStatusCode() + ': ' + res.getBody());
        }
    }

    /**
     * Build a Langfuse batch event envelope.
     */
    private static Map<String, Object> buildEvent(String eventType, Map<String, Object> body) {
        return new Map<String, Object>{
            'id' => generateEventId(),
            'type' => eventType,
            'timestamp' => DateTime.now().formatGmt('yyyy-MM-dd\'T\'HH:mm:ss.SSS\'Z\''),
            'body' => body
        };
    }

    /**
     * Generate a unique trace ID prefixed with ir- for easy filtering in Langfuse.
     */
    private static String generateTraceId() {
        return 'ir-' + String.valueOf(Math.abs(Crypto.getRandomLong())).substring(0, 12)
            + '-' + String.valueOf(DateTime.now().getTime());
    }

    /**
     * Generate a unique event/span ID.
     */
    private static String generateEventId() {
        return String.valueOf(Math.abs(Crypto.getRandomLong())).substring(0, 16)
            + String.valueOf(DateTime.now().getTime());
    }
}
