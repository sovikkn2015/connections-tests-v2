# submit-order Process API — V3

Mule 4.9.x Maven project. Three POST endpoints + health:

- `POST /api/orders` — submit a new order
- `POST /api/orders/{orderId}/cancel` — cancel an in-flight order
- `POST /api/orders/{orderId}/modify` — modify the limit price of an in-flight order
- `GET  /api/health` — liveness probe

All three write paths forward to Alpaca paper trading at `paper-api.alpaca.markets/v2`.

## V3 contract

Every inbound write request carries:

| Field | Required | Notes |
|---|---|---|
| `plan_hash` | yes | SHA-256 hex of canonical ActionPlan |
| `approval_token_hash` | yes | SHA-256 hex of raw HMAC approval token |
| `ticker`, `side`, `quantity`, `account_id` | submit only | `side` is lowercase `buy`/`sell` |
| `order_id` | cancel/modify | path param + body must match |
| `limit_price` | modify only | positive number |

Validation outcomes:
- **403** if `plan_hash` or `approval_token_hash` is missing - mimics the upstream HITL gate
- **400** on any other schema failure
- **502** if Alpaca returns a 4xx/5xx
- **504** on Alpaca timeout / connectivity failure

## Build, test, deploy

```bash
# hermetic MUnit tests (6 tests, zero network)
mvn test

# local dev in mock mode (no Alpaca calls)
mvn mule:run -Dmock_mode=true

# package + deploy to CloudHub 2.0
export ANYPOINT_CONNECTED_APP_ID="<from Anypoint Access Mgmt, Connected Apps>"
export ANYPOINT_CONNECTED_APP_SECRET="<from the same screen>"
export ANYPOINT_ORG_ID="<your business-group id>"
mvn clean deploy -Pcloudhub-sandbox -DskipTests
```

Then inject Alpaca creds via Runtime Manager -> Settings -> Properties -> Show secure properties:

| Property name | Source |
|---|---|
| `alpaca.key_id` | `/006-v3/vendors/alpaca` -> `key_id` |
| `alpaca.secret` | `/006-v3/vendors/alpaca` -> `secret` |

## What this flow does NOT do

- **No LLM calls.** Pure routing + mapping.
- **No audit writes.** `IR_Audit_Log__c` writes happen in the `openclaw/skills/mulesoft_api/actions.py` skill after this Mule app returns. Steering rule 10.
- **No raw tokens logged.** `approval_token_hash` and `plan_hash` are truncated to first 8 hex chars in log lines. Steering rule 22.
- **No MNPI to LLM.** No LLM involved at this layer at all.
