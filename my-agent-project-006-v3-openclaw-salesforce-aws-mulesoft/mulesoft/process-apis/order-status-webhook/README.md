# order-status-webhook Process API — V3

Public HTTPS endpoint that receives Alpaca order-lifecycle callbacks and fans them out to the mulesoft-actions MCP server (`order_status_webhook` tool), which updates Salesforce positions and writes `IR_Audit_Log__c`.

This is the only Mule app in V3 that takes inbound traffic from outside our infrastructure. Security model:

1. **HMAC-SHA256 signature verification** on every request — 401 on mismatch
2. **Shape validation** — 400 on malformed body
3. **MCP fan-out** with Bearer token + `X-Principal-Id: mulesoft-webhook`
4. **IP allowlist policy** should be disabled or widened to Alpaca's published source CIDRs (not the Lambda NAT EIP) — see `mulesoft/policies/process-api-policies.json`

## Flow summary

```
POST /api/webhooks/orders  (public internet)
  -> read X-Alpaca-Signature header
  -> recompute HMAC-SHA256(rawBody, webhook.hmac_secret)
  -> 401 if missing or mismatch
  -> 400 on malformed body
  -> translate to MCP JSON-RPC tools/call order_status_webhook
  -> POST <mcp.endpoint_host>/mcp/tools/call with Bearer <mcp.bearer_token>
  -> 200 { received, event_id, mulesoft_reference }
  -> 502 on MCP error, 504 on timeout
```

## Build, test, deploy

```bash
mvn test

mvn mule:run -Dmock_mode=true

export ANYPOINT_CONNECTED_APP_ID="<from Anypoint Access Mgmt>"
export ANYPOINT_CONNECTED_APP_SECRET="<from the same screen>"
export ANYPOINT_ORG_ID="<business-group id>"
mvn clean deploy -Pcloudhub-sandbox -DskipTests
```

Secure properties:

| Property | Source |
|---|---|
| `webhook.hmac_secret` | `/006-v3/vendors/alpaca-webhook` -> `hmac_secret` |
| `mcp.endpoint_host` | API Gateway invoke URL of the `mulesoft-actions` Lambda, host only |
| `mcp.bearer_token` | JWT / bearer token recognized by that Lambda |

## Wire-up

After deploy, copy the CloudHub public URL and paste it into the Alpaca account dashboard under **Integrations -> Webhooks**. Alpaca will POST to `<your-cloudhub-url>/api/webhooks/orders` with X-Alpaca-Signature on every order event.

## Non-goals

- **No retry / dedup.** Alpaca retries with the same event-id on 5xx; downstream (the MCP) is idempotent.
- **No audit write here.** The MCP server + the skill layer handle the Salesforce audit per steering rule 10.
