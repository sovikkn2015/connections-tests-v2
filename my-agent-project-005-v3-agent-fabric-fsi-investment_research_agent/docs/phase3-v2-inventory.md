# Phase 3 — V2 Apex Inventory (baseline for V3 refactor)

Generated as Step 1 of the V3 Salesforce Apex refactor. This enumerates every V2
Apex class, named credential, external credential, and custom label so the V3
refactor has a clear starting map.

Source tree: `my-agent-project-005-v2-integrations-fsi-investment_research_agent/force-app/main/default/`

---

## 1. Apex Classes (`classes/`)

Total: **24 classes** (paired `.cls` + `.cls-meta.xml`).

| # | Class | Category | Direct HTTP callout? | References IR_MnpiGuard? | V3 fate |
|---|-------|----------|----------------------|--------------------------|---------|
| 1 | `IR_AgentApiProxy` | Service-layer REST proxy | No | No | Copy as-is |
| 2 | `IR_AuditLogAction` | Invocable — audit write | No | No | Copy as-is |
| 3 | `IR_CompanyLookupAction` | Invocable — SOQL lookup | No | No | Copy as-is |
| 4 | `IR_ComplianceAgentAction` | Invocable — composite | No | No | Copy as-is |
| 5 | `IR_ComplianceScreeningAction` | Invocable — restricted/quiet/MNPI | No | **Yes** (`hasActiveMnpiFlags`) | Modify — drop MNPI block (gateway owns it) |
| 6 | `IR_CoverageCheckAction` | Invocable — SOQL | No | No | Copy as-is |
| 7 | `IR_DataCloudAction` | Invocable — CDP + SOQL | No | **Yes** (`isDataAllowed`, `CONFIDENTIAL_DATA`) | Modify — drop MNPI block |
| 8 | `IR_DetailedTestRunner` | Test helper | No | No | Copy as-is |
| 9 | `IR_EarningsCalendarAction` | Invocable — SOQL | No | No | Copy as-is |
| 10 | `IR_ExperienceCloudHelper` | Doc helper | No | Comment only | Modify — strip `IR_MnpiGuard` comment |
| 11 | `IR_FinancialAnalysisAction` | Invocable — **Lambda callout** | **Yes** (`/financial-analysis/*`) | No | Modify — route via Flex Gateway |
| 12 | `IR_LangfuseTracer` | Tracing | Yes (Langfuse NC) | No | Copy as-is (Langfuse NC stays) |
| 13 | `IR_MarketDataAction` | Invocable — **Lambda callout** | **Yes** (`/market-data/*`) | No | Modify — route via Flex Gateway |
| 14 | `IR_McpServerEndpoint` | Inbound REST (`/ir-mcp/*`) | No | **Yes** (`filterForExternalCaller`) | Modify — drop MNPI filter |
| 15 | `IR_MnpiCheckAction` | Invocable — MNPI report | No | **Yes** (heavy) | Modify — return "governed by gateway" report |
| 16 | **`IR_MnpiGuard`** | **Utility — MNPI classifier** | No | — | **DELETE** (Flex Gateway `mnpi-filter.yaml` replaces it) |
| 17 | `IR_NewsSearchAction` | Invocable — **Lambda callout** | **Yes** (`/news-search/*`) | No | Modify — route via Flex Gateway |
| 18 | `IR_ResearchBriefAction` | Invocable — orchestrator | No | **Yes** (`filterForExternalCaller`) | Modify — drop MNPI filter |
| 19 | `IR_SecFilingsAction` | Invocable — **Lambda callout** | **Yes** (`/sec-edgar/*`) | No | Modify — route via Flex Gateway |
| 20 | `IR_SeedDataRunner` | Anonymous-apex helper | No | No | Copy as-is |
| 21 | `IR_SentimentAnalysisAction` | Invocable — **Lambda callout** | **Yes** (`/sentiment-analysis/*`) | No | Modify — route via Flex Gateway |
| 22 | `IR_TestRunner` | Test helper | No | No | Copy as-is |
| 23 | `IR_VerifyData` | Anonymous-apex helper | No | No | Copy as-is |
| 24 | `IR_WatchlistAction` | Invocable — DML | No | No | Copy as-is |

### 1a. Custom circuit-breaker / resilience helpers

None found. No `IR_CircuitBreaker*.cls` or `IR_ResilienceHelper*.cls` exists in V2.
Each action class uses a plain `try { http.send(req); } catch (CalloutException e)` pattern
with a string fallback message — no custom retry/backoff logic. The Flex Gateway
`circuit-breaker.yaml` policy replaces this at the network edge.

### 1b. Invocable classes that call Lambda / external URLs

Five classes use `System.Label.IR_AWS_API_URL` + `/<path>` for direct Lambda callouts:

1. `IR_MarketDataAction` → `POST {AWS_BASE_URL}/market-data/<tool>` → V3: `callout:IR_FlexGateway/market-data/<tool>`
2. `IR_SecFilingsAction` → `POST {AWS_BASE_URL}/sec-edgar/<tool>` → V3: `callout:IR_FlexGateway/sec-edgar/<tool>`
3. `IR_NewsSearchAction` → `POST {AWS_BASE_URL}/news-search/<tool>` → V3: `callout:IR_FlexGateway/news-search/<tool>`
4. `IR_FinancialAnalysisAction` → `POST {AWS_BASE_URL}/financial-analysis/<tool>` → V3: `callout:IR_FlexGateway/financial-analysis/<tool>`
5. `IR_SentimentAnalysisAction` → `POST {AWS_BASE_URL}/sentiment-analysis/<tool>` → V3: `callout:IR_FlexGateway/sentiment-analysis/<tool>`

All five previously injected `x-api-key` header inline from `System.Label.IR_AWS_API_KEY`.
In V3 the header is injected by the Named Credential's External Credential, so
the Apex no longer references the key directly.

---

## 2. Named Credentials (`namedCredentials/`)

| File | V3 fate |
|------|---------|
| `AWS_IR_API.namedCredential-meta.xml` | **Delete** — replaced by `IR_FlexGateway` |
| `Langfuse_API.namedCredential-meta.xml` | Keep — Langfuse observability path unchanged |

## 3. External Credentials (`externalCredentials/`)

| File | V3 fate |
|------|---------|
| `AWS_IR_API_Credential.externalCredential-meta.xml` | **Delete** — replaced by `IR_FlexGateway_mTLS` |
| `Langfuse_API_Credential.externalCredential-meta.xml` | Keep |

## 4. Custom Labels (`labels/IR_AWS_API_URL.labels-meta.xml`)

Single file, holds two labels:

| Label | V3 fate |
|-------|---------|
| `IR_AWS_API_URL` | **Delete** — URL now hardcoded in Named Credential endpoint, parameterised via `FlexGatewayUrl` |
| `IR_AWS_API_KEY` | **Delete** — moved into External Credential (fallback principal only) |

V3 adds:
- `FlexGatewayUrl` — placeholder `https://PLACEHOLDER.flex-gateway.invalid`, overridden per-env
- `McpApiKey` — retained for fallback principal during mTLS migration window

## 5. Remote Site Settings (`remoteSiteSettings/`)

| File | V3 fate |
|------|---------|
| `AWS_IR_MCP_API.remoteSiteSetting-meta.xml` | Keep (covers the Flex Gateway hostname too, can be re-pointed) |
| `Langfuse_API.remoteSite-meta.xml` | Keep |

## 6. Other metadata

- `objects/` — 5 custom objects (`IR_Audit_Log__c`, `IR_Company__c`, `IR_Coverage__c`, `IR_Research_Note__c`, `IR_Watchlist__c`) — copy as-is
- `aiAuthoringBundles/` — 2 bundles (`IR_Research_Agent`, `IR_Compliance_Agent`) — copy as-is
- `aiEvaluationDefinitions/` — 3 eval definitions — copy as-is
- `connectedApps/`, `corsWhitelistOrigins/`, `permissionsets/` — copy as-is

---

## Summary of planned diffs

- **Delete:** 1 class (`IR_MnpiGuard`), 1 Named Credential, 1 External Credential, 1 Labels file
- **Create:** 1 Named Credential (`IR_FlexGateway`), 1 External Credential (`IR_FlexGateway_mTLS`), 1 Labels file (`FlexGateway.labels-meta.xml`)
- **Modify:** 10 classes — 5 for Flex Gateway routing, 6 for MNPI-guard removal (`IR_ComplianceScreeningAction` is in both groups; `IR_MnpiCheckAction` stays as a stub action that reports "governed by Flex Gateway")

No V2 tree is touched. All changes land under
`my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent/`.
