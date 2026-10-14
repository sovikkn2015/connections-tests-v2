# Phase 3 — Apex Refactor Summary

All 005 V2 Apex external callouts now route through the Flex Gateway Named
Credential (`IR_FlexGateway`). This doc captures the diff of V3 vs V2 force-app.

## Headline metrics

| Metric | Count |
|--------|-------|
| Apex classes copied from V2 (no change) | 13 |
| Apex classes modified | 10 |
| Apex classes deleted | 1 (`IR_MnpiGuard`, 171 lines) |
| Named Credentials deleted | 1 (`AWS_IR_API`) |
| Named Credentials created | 1 (`IR_FlexGateway`) |
| External Credentials deleted | 1 (`AWS_IR_API_Credential`) |
| External Credentials created | 1 (`IR_FlexGateway_mTLS`) |
| Custom Labels deleted | 2 (`IR_AWS_API_URL`, `IR_AWS_API_KEY`) |
| Custom Labels created | 2 (`FlexGatewayUrl`, `McpApiKey`) |
| Labels file replaced | 1 (`IR_AWS_API_URL.labels-meta.xml` → `FlexGateway.labels-meta.xml`) |
| Custom circuit-breaker / resilience Apex removed | 0 files (V2 never had any) |
| Lines of custom MNPI logic removed from Apex | ~235 (IR_MnpiGuard 171 + call-sites 60+) |

## What was copied vs what was excluded

### Copied over (identical)

All `aiAuthoringBundles/`, `aiEvaluationDefinitions/`, `connectedApps/`,
`corsWhitelistOrigins/`, `permissionsets/`, `objects/`, `scripts/apex/` + the
following Apex classes with no changes:

- IR_AgentApiProxy
- IR_AuditLogAction
- IR_CompanyLookupAction
- IR_ComplianceAgentAction
- IR_CoverageCheckAction
- IR_DetailedTestRunner
- IR_EarningsCalendarAction
- IR_LangfuseTracer (keeps its own Langfuse Named Credential)
- IR_SeedDataRunner
- IR_TestRunner
- IR_VerifyData
- IR_WatchlistAction

Plus `Langfuse_API` Named Credential, `Langfuse_API_Credential` External
Credential, `Langfuse_API.remoteSite-meta.xml`, and `AWS_IR_MCP_API.remoteSite-meta.xml`
(kept, re-pointable to the Flex Gateway host).

### Excluded from the V3 copy

- `IR_MnpiGuard.cls` + meta — replaced by Flex Gateway `policies/mnpi-filter.yaml`
- `AWS_IR_API.namedCredential-meta.xml` — replaced by `IR_FlexGateway`
- `AWS_IR_API_Credential.externalCredential-meta.xml` — replaced by `IR_FlexGateway_mTLS`
- `IR_AWS_API_URL.labels-meta.xml` — replaced by `FlexGateway.labels-meta.xml`

No custom circuit-breaker or resilience-helper Apex existed in V2 so there
was nothing to exclude there. The Flex Gateway `policies/circuit-breaker.yaml`
handles retries and backoff now.

## Per-class changes

### Modified (Flex Gateway routing, 5 files)

Each of these five had the same 4-edit pattern:
1. Replace `System.Label.IR_AWS_API_URL` / `System.Label.IR_AWS_API_KEY`
   constants with a single `GATEWAY = 'callout:IR_FlexGateway'` constant.
2. Change `req.setEndpoint(AWS_BASE_URL + '/<svc>/...')` to
   `req.setEndpoint(GATEWAY + '/<svc>/...')`.
3. Remove the inline `req.setHeader('x-api-key', AWS_API_KEY)` line (the header
   is now injected by the External Credential).
4. Update fallback messages + audit log source strings to reference "Flex Gateway".

All class signatures and `@InvocableVariable` labels are unchanged — agent
topics bound to these actions continue to work without re-registration.

| Class | Route (V2) | Route (V3) |
|-------|-----------|-----------|
| `IR_MarketDataAction` | `AWS_BASE_URL + '/market-data/*'` | `callout:IR_FlexGateway/market-data/*` |
| `IR_SecFilingsAction` | `AWS_BASE_URL + '/sec-edgar/*'` | `callout:IR_FlexGateway/sec-edgar/*` |
| `IR_NewsSearchAction` | `AWS_BASE_URL + '/news-search/*'` | `callout:IR_FlexGateway/news-search/*` |
| `IR_FinancialAnalysisAction` | `AWS_BASE_URL + '/financial-analysis/*'` | `callout:IR_FlexGateway/financial-analysis/*` |
| `IR_SentimentAnalysisAction` | `AWS_BASE_URL + '/sentiment-analysis/*'` | `callout:IR_FlexGateway/sentiment-analysis/*` |

### Modified (MNPI-guard removal, 5 files)

- `IR_DataCloudAction` — removed `IR_MnpiGuard.isDataAllowed(...)` gate in
  `queryClientHoldings`. Comment points to `policies/mnpi-filter.yaml`.
- `IR_McpServerEndpoint` — removed `IR_MnpiGuard.filterForExternalCaller(...)`
  gate in `getClientHoldings`. Comment explains the gateway is now the enforcement
  point for inbound MCP callers.
- `IR_ResearchBriefAction` — removed the egress redaction line on the assembled
  brief. Flex Gateway egress policy handles it.
- `IR_ComplianceScreeningAction` — inlined a minimal 30-day audit scan for the
  MNPI section of the screening report (previously called `IR_MnpiGuard.hasActiveMnpiFlags`).
  Output shape of the screening report is unchanged.
- `IR_ExperienceCloudHelper` — updated the doc comment to reference the
  `policies/mnpi-filter.yaml` as the MNPI enforcement point.

### Rewritten (MNPI reporting action)

- `IR_MnpiCheckAction` — previously called `IR_MnpiGuard.getClassification`,
  `.hasActiveMnpiFlags`, and `.isDataAllowed`. V3 version keeps the exact
  `MnpiInput` / `MnpiOutput` shape (`mnpiResult`, `isAllowed`, `classification`)
  so the IR_Compliance_Agent topic still binds to it, but delegates the
  classification to a local constant map and labels the report with
  "Authoritative policy source: Flex Gateway (mnpi-filter.yaml)". Actual access
  enforcement happens at the gateway, not here.

### Deleted

- `IR_MnpiGuard.cls` (171 lines) + `.cls-meta.xml` — all behaviour moved into
  `my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent/agent-fabric/policies/mnpi-filter.yaml`.

## Flex Gateway wiring

### `force-app/main/default/labels/FlexGateway.labels-meta.xml`

- `FlexGatewayUrl` — `https://PLACEHOLDER.flex-gateway.invalid` (overridden per-env)
- `McpApiKey` — `REPLACE_WITH_FALLBACK_API_KEY` (protected; used only by the
  fallback named principal during the mTLS cutover window)

### `force-app/main/default/namedCredentials/IR_FlexGateway.namedCredential-meta.xml`

- Endpoint: `https://flex-gateway.internal.ir-v3.local`
  (placeholder per the Phase 3 brief — `FlexGatewayUrl` label drives per-env override)
- `generateAuthorizationHeader`: `false` (auth is handled by the linked External Credential)
- `externalCredential`: `IR_FlexGateway_mTLS`

### `force-app/main/default/externalCredentials/IR_FlexGateway_mTLS.externalCredential-meta.xml`

Principals:
1. `IR_FlexGateway_mTLS_Principal` (primary — mTLS client cert identity)
2. `IR_FlexGateway_Fallback_Principal` (secondary — API key via `McpApiKey`,
   for the migration period before every caller has a client cert)

HTTP headers injected per callout:
- `x-api-key` → `{!$Label.McpApiKey}` (fallback principal only)
- `x-sf-origin` → `salesforce-ir-v3` (Flex Gateway uses this to attribute the source)

## Validation status

- `sf project convert source --source-dir force-app` → **PASS**
  (all V3 metadata parses cleanly against the Salesforce metadata registry)
- `sf project deploy preview --source-dir force-app` → failed at source-tracking
  stage only (the local-org step requires an authenticated source-tracked scratch
  org, which is out of scope for this artifacts-only phase)
- `sf project deploy validate` → pending. Requires an authenticated target org
  + network connectivity. Run after the Mulesoft team has a real Flex Gateway
  endpoint and the org is ready.
- One V2-baseline bug fixed in passing:
  `AWS_IR_MCP_API.remoteSiteSetting-meta.xml` → `AWS_IR_MCP_API.remoteSite-meta.xml`
  (wrong extension in V2 was blocking `sf project deploy preview` even before
  any Phase 3 edits).

## What's next

1. Mulesoft team supplies the real Flex Gateway URL → update the `FlexGatewayUrl`
   label value.
2. Add mTLS client certificate to the `IR_FlexGateway_mTLS_Principal` principal
   in the target org.
3. Run `sf project deploy validate --source-dir force-app --test-level RunLocalTests`
   against a scratch org to confirm real deploy cleanliness.
4. Monitor gateway policy hits (rate-limit, circuit-breaker, mnpi-filter) for a
   sprint before retiring the `IR_FlexGateway_Fallback_Principal`.
