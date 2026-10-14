# Deploy the submit-order Process API to CloudHub 2.0

Project 006 v2 - Phase 6. End-to-end runbook for getting the first MuleSoft Process API live and wired into the `mulesoft-actions` Lambda.

> **Zero credentials in git.** Every secret in this guide goes through AWS Secrets Manager or the Anypoint UI. Nothing in this repo points at a real CloudHub URL until you inject it via `aws secretsmanager update-secret`.

---

## Prerequisites

- **Anypoint Code Builder** installed (VS Code extension or desktop app). Sign in with your MuleSoft org account.
- **Browser** signed into https://anypoint.mulesoft.com with the same org.
- **AWS CLI** authenticated to the account that owns the `/006-v2/mulesoft/credentials` secret.
- **Maven 3.8+** and **JDK 17** for local runs.
- The Lambda VPC stack deployed so a NAT EIP exists (needed for the IP allowlist policy).

Source files you will use:

```
mulesoft/process-apis/submit-order/submit-order.raml
mulesoft/process-apis/submit-order/submit-order.xml
mulesoft/process-apis/submit-order/transforms/submit-order-request.dwl
mulesoft/process-apis/submit-order/transforms/submit-order-response.dwl
mulesoft/policies/process-api-policies.json
```

---

## 1. Import the project into Anypoint Code Builder

Two paths, pick one:

**Path A - Clone the repo folder (recommended).**

1. Open Anypoint Code Builder.
2. `File > Open Folder` -> select `my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/mulesoft/process-apis/submit-order/`.
3. Code Builder prompts to create a Mule Project wrapper. Accept, naming it `submit-order-process-api`.
4. Let Code Builder wire up `pom.xml` and `mule-artifact.json` from the XML flow it detects.

**Path B - Use "Import from XML".**

1. `Cmd/Ctrl + Shift + P` -> `MuleSoft: New Project from Existing Flow`.
2. Point it at `submit-order.xml` from this repo.
3. Code Builder scaffolds the project.

Either path, the result is a standard Mule 4 project with `src/main/mule/submit-order.xml` and `src/main/resources/` for DataWeave.

---

## 2. Run locally

```bash
cd <code-builder-project-root>
mvn clean install
mvn mule:run
```

In a second terminal:

```bash
# health
curl -s http://localhost:8081/api/health | jq

# happy path (precompute a fake hash)
HASH=$(echo -n "fake-approval-token" | shasum -a 256 | awk '{print $1}')
curl -s -X POST http://localhost:8081/api/orders \
  -H "Content-Type: application/json" \
  -d "{
    \"ticker\": \"AAPL\",
    \"side\": \"BUY\",
    \"quantity\": 100,
    \"order_type\": \"MARKET\",
    \"client_id\": \"CLI-0001\",
    \"account_id\": \"ACC-0001\",
    \"approval_token_hash\": \"${HASH}\"
  }" | jq

# 403 gate (missing approval_token_hash)
curl -s -X POST http://localhost:8081/api/orders \
  -H "Content-Type: application/json" \
  -d '{"ticker":"AAPL","side":"BUY","quantity":100,"client_id":"C","account_id":"A"}' | jq
```

Expected happy path response:

```json
{
  "order_id": "MULE-ORDER-a1b2c3d4",
  "status": "SUBMITTED",
  "ticker": "AAPL",
  "side": "BUY",
  "quantity": 100,
  "submitted_at": 1735689600,
  "mulesoft_reference": "MS-REF-a1b2c3d4e5f6"
}
```

Stop the local run with `Ctrl+C`.

---

## 3. Deploy to CloudHub 2.0

1. In Code Builder: `MuleSoft: Deploy to CloudHub 2.0`.
2. Fill in:
   - **App name:** `YOUR-APP-NAME` (e.g. `006-v2-trade-process-api`). Must be globally unique in the MuleSoft org.
   - **Environment:** Sandbox.
   - **Region:** `us-east-2` (match the Lambda region).
   - **Runtime:** Mule 4.4.x or newer.
   - **Replicas:** 1 (bump later).
   - **vCores per replica:** 0.1 is plenty for mock-mode eval.
3. Click **Deploy**. Wait until the status in Runtime Manager shows **STARTED** (2-4 min).
4. Grab the deployed URL from Runtime Manager. Format:

   ```
   https://{app-name}.{region}.cloudhub.io
   ```

   For example: `https://006-v2-trade-process-api.us-e2.cloudhub.io`.

---

## 4. Smoke-test the deployed API

```bash
BASE_URL="https://YOUR-APP-NAME.us-e2.cloudhub.io"

# health
curl -s "${BASE_URL}/api/health" | jq

# happy path
HASH=$(echo -n "smoke-test-token" | shasum -a 256 | awk '{print $1}')
curl -s -X POST "${BASE_URL}/api/orders" \
  -H "Content-Type: application/json" \
  -d "{
    \"ticker\": \"NVDA\",
    \"side\": \"BUY\",
    \"quantity\": 50,
    \"client_id\": \"CLI-SMOKE\",
    \"account_id\": \"ACC-SMOKE\",
    \"approval_token_hash\": \"${HASH}\"
  }" | jq
```

If both return 200, the Mule side is done.

---

## 5. Apply API Manager policies

1. Anypoint UI -> **API Manager** -> locate the auto-registered API for your deployed app.
2. Click **Policies** tab.
3. For each block under `mulesoft/policies/process-api-policies.json`:
   - Click **Apply new policy**.
   - Pick the matching policy by `name`.
   - Paste the `config` object from the JSON into the policy form.
4. For the `ip-allowlist` policy, replace `REPLACE_WITH_LAMBDA_NAT_EIP/32` with the real NAT EIP from the Lambda VPC stack output:

   ```bash
   aws cloudformation describe-stacks \
     --stack-name mulesoft-actions-vpc \
     --query "Stacks[0].Outputs[?OutputKey=='NatGatewayEip'].OutputValue" \
     --output text
   ```

5. Click **Apply**. Policies go live immediately.

After this, calling the API without a valid `x-mulesoft-client-id` header returns 401, and non-allowlisted IPs get 403.

---

## 6. Store the deployed URL in Secrets Manager

The Lambda reads `process_api_base_url` from the existing `/006-v2/mulesoft/credentials` secret. Merge the new key without overwriting existing values:

```bash
# 1. Read current secret
aws secretsmanager get-secret-value \
  --secret-id /006-v2/mulesoft/credentials \
  --query SecretString --output text > /tmp/creds.json

# 2. Patch with the deployed URL (use jq to merge, not manual edit)
DEPLOYED_URL="https://YOUR-APP-NAME.us-e2.cloudhub.io"
jq --arg url "$DEPLOYED_URL" '. + {process_api_base_url: $url}' \
   /tmp/creds.json > /tmp/creds-new.json

# 3. Update
aws secretsmanager update-secret \
  --secret-id /006-v2/mulesoft/credentials \
  --secret-string file:///tmp/creds-new.json

# 4. Shred local copy
shred -u /tmp/creds.json /tmp/creds-new.json
```

Verify:

```bash
aws secretsmanager get-secret-value \
  --secret-id /006-v2/mulesoft/credentials \
  --query SecretString --output text | jq 'keys'
# should include "process_api_base_url"
```

---

## 7. Flip the Lambda to sandbox mode

```bash
aws lambda update-function-configuration \
  --function-name mulesoft-actions \
  --environment "Variables={MULESOFT_MODE=sandbox,MULESOFT_SECRET_NAME=/006-v2/mulesoft/credentials}"
```

Smoke test through the API Gateway in front of the Lambda:

```bash
# Replace with the actual MCP server URL
MCP_URL="https://<api-gateway-id>.execute-api.us-east-2.amazonaws.com"

curl -s -X POST "${MCP_URL}/tools/call" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "submit_order",
    "arguments": {
      "ticker": "AAPL",
      "side": "BUY",
      "quantity": 10,
      "client_id": "CLI-0001",
      "account_id": "ACC-0001",
      "approval_token": "test-token-not-validated-in-mock"
    }
  }' | jq
```

Expect a `MULE-ORDER-*` id in the result block, coming straight from CloudHub.

---

## Rollback

If the Lambda misbehaves, flip the mode back:

```bash
aws lambda update-function-configuration \
  --function-name mulesoft-actions \
  --environment "Variables={MULESOFT_MODE=mock,MULESOFT_SECRET_NAME=/006-v2/mulesoft/credentials}"
```

Lambda returns mock responses again while you debug. The Process API on CloudHub stays live (it is cheap and stateless), so nothing to tear down.

---

## What NOT to do

- Do not hardcode `process_api_base_url` in `app.py` or `mulesoft_client.py`. Always read from the secret.
- Do not commit your local `/tmp/creds*.json` files. They are shredded in step 6.
- Do not apply the policies to a production endpoint before the eval run completes (L5 queries 121-140).
- Do not skip the `ip-allowlist` policy. The Lambda NAT EIP is the only legitimate caller.

---

## Deploying the other 5 Process APIs

The same deploy flow applies to each of the other 5 Mule Process APIs. Pick a distinct CloudHub app name per API (must be globally unique in the MuleSoft org), then follow sections 1-5 exactly as written for `submit-order`.

| Action | Source folder | Endpoint | Suggested app name |
|---|---|---|---|
| `initiate_wire` | `mulesoft/process-apis/initiate-wire/` | `POST /api/wires` | `006-v2-wire-process-api` |
| `rebalance_portfolio` | `mulesoft/process-apis/rebalance-portfolio/` | `POST /api/rebalances` | `006-v2-rebalance-process-api` |
| `run_kyc_screening` | `mulesoft/process-apis/run-kyc-screening/` | `POST /api/kyc` | `006-v2-kyc-process-api` |
| `open_account` | `mulesoft/process-apis/open-account/` | `POST /api/accounts` | `006-v2-account-open-process-api` |
| `close_account` | `mulesoft/process-apis/close-account/` | `POST /api/accounts/close` | `006-v2-account-close-process-api` |

All 5 follow the same structural pattern as `submit-order`:

- HTTP listener on `0.0.0.0:8081` with `/api/*` paths.
- Inbound logger with redacted `approval_token_hash` prefix (first 8 chars).
- Validation choice: 403 on missing `approval_token_hash`, 400 on missing required fields. `initiate_wire`, `rebalance_portfolio`, and `close_account` also return 403 `dual_approval_required` under their respective rules (see the RAML in each folder).
- DataWeave normalize -> DataWeave response builder that mints a `MULE-{ACTION}-{hex}` id and `MS-REF-{12-hex}` reference.
- `GET /api/health` probe.

Apply the same 4 policies from `mulesoft/policies/process-api-policies.json` to each deployed app. Store each app's deployed URL under a distinct key in the `/006-v2/mulesoft/credentials` secret - suggested naming below - so the Lambda can route per-action:

```
process_api_base_url              # submit-order (existing)
wire_process_api_base_url         # initiate-wire
rebalance_process_api_base_url    # rebalance-portfolio
kyc_process_api_base_url          # run-kyc-screening
account_open_process_api_base_url # open-account
account_close_process_api_base_url # close-account
```

Each API's dual-auth behavior in brief:

- `initiate_wire` — 403 `dual_approval_required` when `amount > 100000` and `dual_approval_token_hash` is missing.
- `rebalance_portfolio` — 403 `dual_approval_required` when `len(trades) > 10` or `sum(quantity) > 5000` and `dual_approval_token_hash` is missing.
- `close_account` — 403 `dual_approval_required` when **either** `approval_token_hash` or `dual_approval_token_hash` is missing. Closure always needs both per v2 steering rule 5.
- `run_kyc_screening` and `open_account` — single approval only.

After each app is deployed and its URL is in Secrets Manager, the Lambda calls it through `client.request_process_api(...)` the same way `submit_order` does today — see `aws/mcp-servers/mulesoft-actions/app.py` for the shared helper.

---

## Deploying submit-order with live Alpaca backend

The `submit-order` Process API has been upgraded from mock-response to **live Alpaca paper trading** (`paper-api.alpaca.markets`). This section is the runbook for promoting it.

Nothing about sections 1–7 above changes. This is an additional step that replaces the mock-mode response with a real Alpaca call — so after Section 7 the Lambda hits CloudHub, and now CloudHub in turn hits Alpaca.

### Prerequisites for the Alpaca variant

- The Alpaca paper-trading credentials already exist in AWS Secrets Manager under the fixed ARN:

  ```
  arn:aws:secretsmanager:us-east-1:875460787302:secret:/006-v2/vendors/alpaca-kHFwDm
  (the trailing -kHFwDm is the ARN suffix AWS auto-appends; the secret NAME
   — i.e. what you pass to --secret-id — is /006-v2/vendors/alpaca)
  ```

  Secret shape:

  ```json
  {
    "key_id": "PK...",
    "secret": "...",
    "endpoint": "https://paper-api.alpaca.markets",
    "mode": "paper",
    "account_number": "PA..."
  }
  ```

- The CloudHub app (`006-v2-trade-process-api` or whatever you named it in Section 3) is already deployed from the previous mock build.
- You are the operator doing the deploy — **not** a CI job. CI does not touch live vendor credentials.

### Step A — Read the Alpaca credentials from Secrets Manager

```bash
aws secretsmanager get-secret-value \
  --secret-id /006-v2/vendors/alpaca \
  --region us-east-1 \
  --query SecretString --output text > /tmp/alpaca-creds.json

# Extract the two values we need into shell variables (do NOT echo them).
ALPACA_KEY_ID=$(jq -r .key_id /tmp/alpaca-creds.json)
ALPACA_SECRET=$(jq -r .secret /tmp/alpaca-creds.json)

# Sanity check without revealing the values.
echo "key_id length:  ${#ALPACA_KEY_ID}"   # expect ~20
echo "secret length:  ${#ALPACA_SECRET}"   # expect ~40
```

### Step B — Paste them into CloudHub Secure Properties

1. Anypoint → **Runtime Manager** → your `006-v2-trade-process-api` app → **Settings** → **Properties** tab.
2. Toggle **Show secure properties** = ON.
3. Click **Add Property** and add both:

   | Property name | Value |
   |---|---|
   | `alpaca.key_id` | contents of `$ALPACA_KEY_ID` |
   | `alpaca.secret` | contents of `$ALPACA_SECRET` |

4. Leave `alpaca.endpoint_host`, `alpaca.endpoint_path`, and `mock_mode` at the values from the committed `src/main/resources/config.yaml`. You do NOT need to override those in the UI — `config.yaml` ships them. Only the two secrets are injected here.
5. Click **Apply Changes**. CloudHub restarts the app; watch Runtime Manager until status is **STARTED** again (60–90 seconds).

> **NEVER** paste the key/secret into `src/main/resources/config.yaml` in git. That file stays on `PLACEHOLDER_SET_VIA_SECURE_PROPERTIES_AT_DEPLOY` forever. Zero credentials in git, per v2 steering rule 18.

### Step C — Shred the local secret copy

```bash
shred -u /tmp/alpaca-creds.json
unset ALPACA_KEY_ID ALPACA_SECRET
history -d $(history 1 | awk '{print $1}')  # optional: drop last shell-history entry
```

### Step D — Redeploy the app with the new XML

The Mule XML now references the Alpaca request-config and the two new DataWeave transforms under `transforms/`. Redeploy via Anypoint Code Builder so the new flow ships:

1. Anypoint Code Builder → open the `submit-order-process-api` project folder (same one used in Section 1).
2. Pull the latest XML from git (`git pull` in the project root) so Code Builder picks up `submit-order.xml` with the Alpaca HTTP request and both `transforms/alpaca-*.dwl` files.
3. Command Palette → **MuleSoft: Deploy to CloudHub 2.0** → same app name as before.
4. Wait for **STARTED** status in Runtime Manager.

### Step E — Test with curl

```bash
BASE_URL="https://006-v2-trade-process-api.us-e2.cloudhub.io"

HASH=$(echo -n "alpaca-smoke-token" | shasum -a 256 | awk '{print $1}')

curl -s -X POST "${BASE_URL}/api/orders" \
  -H "Content-Type: application/json" \
  -d "{
    \"ticker\": \"AAPL\",
    \"side\": \"BUY\",
    \"quantity\": 1,
    \"order_type\": \"MARKET\",
    \"client_id\": \"CLI-SMOKE-ALPACA\",
    \"account_id\": \"ACC-SMOKE\",
    \"approval_token_hash\": \"${HASH}\"
  }" | jq
```

Expected response shape (note the `ALPACA-` prefix on `order_id`, not `MULE-ORDER-`):

```json
{
  "order_id": "ALPACA-abc12345-6789-def0-1234-56789abcdef0",
  "status": "accepted",
  "ticker": "AAPL",
  "side": "BUY",
  "quantity": 1,
  "submitted_at": 1735689600,
  "mulesoft_reference": "MS-REF-a1b2c3d4e5f6"
}
```

Health check should also flip over:

```bash
curl -s "${BASE_URL}/api/health" | jq
# -> {"status":"ok","mode":"alpaca-paper","api":"submit-order-process-api"}
```

### Step F — Verify in the Alpaca dashboard

1. Sign in to https://app.alpaca.markets/paper/dashboard/overview
2. Click **Orders**.
3. Find the order matching the `order_id` from Step E (minus the `"ALPACA-"` prefix).
4. Confirm the `symbol`, `qty`, `side`, `type`, and `time_in_force=day` fields match what Mule sent.
5. Account `PA...` (whichever paper-account number is in the Secrets Manager blob) should be the one the order landed on.

If the order shows up in the dashboard, the full chain — Lambda → CloudHub → Alpaca — is live.

### Errors you might see, and what they mean

| HTTP out of Mule | Most likely cause | Fix |
|---|---|---|
| `502 upstream_error` | Alpaca returned 401/403 (bad credentials) or 422 (bad order shape). | Double-check the two Secure Properties (Step B). Check CloudHub logs for `[submit-order] Alpaca error`. |
| `504 upstream_timeout` | Alpaca did not respond within 15s, or CloudHub egress blocked. | Confirm CloudHub app's outbound internet works. Retry — paper API occasionally slow. |
| `403 approval_required` | `approval_token_hash` missing from the POST body. | Caller (the Lambda) must hash the token first. Not an Alpaca issue. |
| `400 missing_fields` | One of `ticker / side / quantity / client_id / account_id` is empty. | Caller bug, nothing vendor-side. |

CloudHub log lines to look for:

```
[submit-order] inbound ticker=... token_hash_prefix=abcdef01
[submit-order] SUBMITTED order_id=ALPACA-... ref=MS-REF-... status=accepted
[submit-order] Alpaca error - returning 502. error=HTTP:UNAUTHORIZED ...
```

### Rollback

Roll back the Mule XML to the previous green revision:

```bash
git log --oneline -- mulesoft/process-apis/submit-order/submit-order.xml
git checkout <PREVIOUS_GREEN_SHA> -- \
  mulesoft/process-apis/submit-order/submit-order.xml
```

Redeploy the app from Anypoint Code Builder (same app name). The old XML does not read `alpaca.key_id` / `alpaca.secret`, so you can leave the Secure Properties in place — they become dormant.

If you need to fall back to mock responses without redeploying, set CloudHub property `mock_mode=true` via the Properties tab and apply. The flow will skip the Alpaca HTTP call and return the legacy `MULE-ORDER-*` canned payload.

### What is intentionally out of scope here

- Only the `submit-order` Process API is wired to Alpaca. `initiate-wire`, `run-kyc-screening`, `open-account`, `close-account`, and `rebalance-portfolio` remain on their mock-response branches until their respective vendor sandboxes are onboarded.
- The Lambda (`aws/mcp-servers/mulesoft-actions/app.py`) is vendor-agnostic and unchanged — it calls the Mule endpoint regardless of backend.
- The canonical RAML (`submit-order.raml`) and the canonical request normalizer (`submit-order-request.dwl`) are unchanged. Downstream consumers (the Lambda, the mulesoft-api skill, the audit log) see the same shape they always saw.
