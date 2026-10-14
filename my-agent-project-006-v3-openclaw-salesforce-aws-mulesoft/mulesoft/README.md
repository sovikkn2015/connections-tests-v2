# V3 MuleSoft Layer — Write Path Only

Three Process APIs on Mule 4.9.x deployed to CloudHub 2.0. MuleSoft is scoped **writes only** in V3: trades (submit / cancel / modify) and wires. Reads (quotes, KYC, corporate actions) go direct to vendors via the MCP servers in `aws/mcp-servers/` — bypassing MuleSoft avoids paying latency + cost for a policy layer that adds no value on reads.

## Projects

| Folder | Purpose | Downstream | Mode default |
|---|---|---|---|
| `process-apis/submit-order/` | POST `/api/orders` + cancel/modify subpaths — writes to Alpaca paper trading | `paper-api.alpaca.markets/v2/orders` | live |
| `process-apis/initiate-wire/` | POST `/api/wires` — writes to Dwolla sandbox after OFAC SDN screen | `api-sandbox.dwolla.com/transfers` | live |
| `process-apis/order-status-webhook/` | POST `/api/webhooks/orders` — Alpaca order lifecycle callback fan-out | mulesoft-actions Lambda `order_status_webhook` MCP tool | live (public HTTPS) |

Each project is a self-contained Maven module with its own pom, DWL transforms, MUnit tests, and RAML contract. Deploy them independently to CloudHub 2.0 via `mvn deploy -Pcloudhub-sandbox`.

## Contracts (shared across all three)

- Every write request carries `plan_hash` (SHA-256 of canonical ActionPlan) + `approval_token_hash` (SHA-256 of raw HMAC approval token). Raw token never crosses the MCP -> Mule boundary — the skill layer hashes before the MCP call and the MCP layer hashes again before the Mule POST.
- Wires > $100,000 additionally require `dual_approval_token_hash` (steering rule 5).
- 403 = approval missing or HITL failed upstream. 400 = schema failure. 502 = vendor returned error. 504 = vendor timeout. The Lambda never sees raw vendor error codes.
- All happy-path responses include `mulesoft_reference` = `MS-REF-{12hex}` minted inside the flow. The Lambda writes this to `IR_Audit_Log__c.MuleSoft_Reference__c` after the call returns (steering rule 13).

## Policies (API Manager)

The 4-policy stack from `mulesoft/policies/process-api-policies.json` applies to all three apps:

1. **client-id-enforcement** — every inbound request must carry `x-mulesoft-client-id` + `x-mulesoft-client-secret` matching the mulesoft-actions Lambda's Connected App
2. **rate-limiting** — 60 req/min (writes are human-paced; higher caught as automation bug)
3. **json-threat-protection** — max 5 levels deep, 1000-char strings, 50 keys, 100 array items
4. **ip-allowlist** — only the Lambda's NAT EIP is allowed; replace `REPLACE_WITH_LAMBDA_NAT_EIP/32` in API Manager UI after VPC provisioning

## Zero credentials

No secrets in git. The deployer sets `ANYPOINT_CONNECTED_APP_ID` + `ANYPOINT_CONNECTED_APP_SECRET` + `ANYPOINT_ORG_ID` in the shell for `mvn deploy`. Alpaca / Dwolla vendor creds are injected at runtime via the CloudHub Runtime Manager -> Secure Properties UI, sourced from AWS Secrets Manager `/006-v3/vendors/alpaca` and `/006-v3/vendors/dwolla`.

## Test

```bash
# hermetic MUnit — no network
cd process-apis/submit-order        && mvn test
cd ../initiate-wire                 && mvn test
cd ../order-status-webhook          && mvn test
```

## Deploy

```bash
# one-time per machine
export ANYPOINT_CONNECTED_APP_ID="<from Anypoint Access Mgmt, Connected Apps>"
export ANYPOINT_CONNECTED_APP_SECRET="<from the same screen>"
export ANYPOINT_ORG_ID="<your business-group / organization id>"

# ship all three
cd process-apis/submit-order        && mvn clean deploy -Pcloudhub-sandbox -DskipTests
cd ../initiate-wire                 && mvn clean deploy -Pcloudhub-sandbox -DskipTests
cd ../order-status-webhook          && mvn clean deploy -Pcloudhub-sandbox -DskipTests
```

Then inject vendor creds into Runtime Manager -> Settings -> Properties -> Show secure properties for each app. See `process-apis/*/README.md` for the exact property names per app.
