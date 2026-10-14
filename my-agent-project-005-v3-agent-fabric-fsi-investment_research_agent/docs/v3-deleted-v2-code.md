# V3 — V2 Code NOT Brought Forward

This document enumerates every V2 file that was intentionally dropped during
the V3 Agent Fabric migration, and explains why. The policy behind every drop
is the single-choke-point rule from `.kiro/steering/006-v2-mulesoft.md`:
**one Named Credential, one HTTP helper, one enforcement layer**. In V3 the
Flex Gateway is that enforcement layer, so Apex helpers that duplicate what
the gateway now does are redundant — or worse, they create a second
enforcement point that can silently drift out of sync with the gateway.

## Files deleted (with explicit reason)

### `IR_MnpiGuard.cls` + `.cls-meta.xml`

- **V2 role:** 171-line utility that classified data (`PUBLIC` / `INTERNAL` /
  `CONFIDENTIAL` / `RESTRICTED`), decided whether a caller was external,
  and redacted responses for external agents.
- **Why removed:** the Flex Gateway's `policies/mnpi-filter.yaml` is now the
  authoritative MNPI egress control. Keeping the Apex class would mean two
  places to update MNPI rules (the gateway policy YAML *and* the Apex
  classifier). The first rule of the gateway-centric architecture is that
  policy lives in the gateway.
- **Compensating control:** `IR_MnpiCheckAction` (V3) still returns a
  screening report, but it explicitly labels the policy source as
  `Flex Gateway (mnpi-filter.yaml)` and does not try to enforce anything
  itself. The gateway rejects any response that would leak MNPI; Apex never
  sees it.
- **Risk if this were re-added:** any change to the gateway's MNPI rules
  would be bypassed by the Apex classifier, producing false negatives
  (over-permissive Apex vs. restrictive gateway) that compliance would
  never detect in testing.

### Custom circuit-breaker / retry helper classes

- **V2 had none.** Grepped V2 for `CircuitBreaker`, `Resilience*`, and any
  retry/backoff helpers. The V2 action classes used a plain
  `try { http.send(req); } catch (CalloutException) { fallback }` pattern
  with no custom circuit-breaker logic.
- **Why this is documented anyway:** the brief called out "custom
  circuit-breaker implementation somewhere in V2" as a candidate for
  removal. That implementation does not exist. The Flex Gateway's
  `policies/circuit-breaker.yaml` is the only circuit breaker in the V3
  architecture, which matches the single-choke-point rule.
- **Compensating control:** `IR_FlexGatewayClient.sendWithRetry` does
  retry `5xx` (except `503` which the gateway reserves for "circuit
  open"), but it is NOT a circuit breaker — it has no state across
  transactions. The gateway owns the breaker.

### Custom correlation-ID threading classes

- **V2 had none.** V2 actions individually constructed `traceId` values
  via `IR_LangfuseTracer.createTrace` and never threaded them into the
  outbound HTTP requests. No class named `CorrelationContext` /
  `RequestContext` / `TraceThreader` exists in V2.
- **V3 replacement:** `IR_FlexGatewayClient` owns correlation ID creation
  and injection (`X-Correlation-Id` header). Callers that want to thread
  an Agentforce session id through a multi-call research flow set it with
  `IR_FlexGatewayClient.setCorrelationId(sessionId)`.

## Metadata deleted

### `namedCredentials/AWS_IR_API.namedCredential-meta.xml`

- **V2 role:** Named Credential pointing at the raw Lambda/API Gateway URLs.
- **Why removed:** V3 uses a single Named Credential `IR_FlexGateway` that
  points at the Flex Gateway ALB. Every outbound request goes through that
  one NC. Keeping `AWS_IR_API` would allow callers to bypass the gateway,
  which defeats the single-choke-point design.

### `externalCredentials/AWS_IR_API_Credential.externalCredential-meta.xml`

- **V2 role:** External Credential that backed `AWS_IR_API`.
- **Why removed:** replaced by `IR_FlexGateway_EC`
  (`externalCredentials/IR_FlexGateway_EC.externalCredential-meta.xml`)
  which uses a custom auth protocol supporting both mTLS principals
  (primary) and an API-key fallback (`McpApiKey` label) during the
  migration window.

### `labels/IR_AWS_API_URL.labels-meta.xml`

- **V2 role:** `IR_AWS_API_URL` custom label held the raw Lambda URL;
  `IR_AWS_API_KEY` held an inline API key.
- **Why removed:** credentials belong in the External Credential, not in
  metadata labels where they end up in source control. V3 uses
  `labels/FlexGateway.labels-meta.xml` which contains only a gateway URL
  *placeholder* (`FlexGatewayUrl`) and a protected-visibility fallback
  label (`McpApiKey`). The real values are never committed.

## Files kept but modified (for completeness)

These are NOT deletions; they are listed here so the review checklist is
complete. Diff details live in `docs/phase3-apex-refactor.md`.

| Class | Change |
|-------|--------|
| `IR_MarketDataAction` | Routes callouts through `IR_FlexGatewayClient.callMcpTool` instead of building HttpRequests inline. |
| `IR_SecFilingsAction` | Same. |
| `IR_NewsSearchAction` | Same. |
| `IR_FinancialAnalysisAction` | Routes via `IR_FlexGatewayClient.callAgent` (Strands agent, not MCP). |
| `IR_SentimentAnalysisAction` | Same. |
| `IR_DataCloudAction` | `IR_MnpiGuard.isDataAllowed` gate removed (gateway enforces it). |
| `IR_McpServerEndpoint` | `IR_MnpiGuard.filterForExternalCaller` gate removed (gateway enforces). |
| `IR_ResearchBriefAction` | Egress redaction line removed (gateway enforces). |
| `IR_ComplianceScreeningAction` | Inlined a small 30-day `IR_Audit_Log__c` scan to keep the MNPI section of the screening report; previously called `IR_MnpiGuard.hasActiveMnpiFlags`. |
| `IR_MnpiCheckAction` | Labels the policy source as "Flex Gateway (mnpi-filter.yaml)". Still returns the same `MnpiOutput` shape so the Agentforce topic binding is unchanged. |
| `IR_ExperienceCloudHelper` | Doc comment updated to point at the gateway policy. |

## Files added

- `classes/IR_FlexGatewayClient.cls` — the single HTTP helper.
- `classes/IR_FlexGatewayClientTest.cls` — ≥75 % coverage with HttpCalloutMock.
- `scripts/apex/smoke-gateway-callout.apex` — post-deploy smoke.
- `namedCredentials/IR_FlexGateway.namedCredential-meta.xml` — single NC.
- `externalCredentials/IR_FlexGateway_EC.externalCredential-meta.xml` — EC for the gateway.
- `labels/FlexGateway.labels-meta.xml` — URL + fallback API key labels.

## Verification pointers for the REVIEW subagent

- Grep V3 for `new HttpRequest()` that target the gateway. The ONLY file
  allowed to construct a gateway-bound HttpRequest is `IR_FlexGatewayClient`.
  Every other file should call through it.
- Grep V3 for `IR_MnpiGuard`. Zero hits expected.
- Grep V3 for `System.Label.IR_AWS_API_URL` / `IR_AWS_API_KEY`. Zero hits expected.
- Confirm `IR_FlexGateway.namedCredential-meta.xml` references
  `IR_FlexGateway_EC` (not the older `IR_FlexGateway_mTLS`).
- Confirm `FlexGatewayUrl` is the only gateway-URL merge field in labels.
