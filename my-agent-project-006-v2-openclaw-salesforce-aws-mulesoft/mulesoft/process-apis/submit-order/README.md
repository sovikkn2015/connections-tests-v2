# submit-order Process API — LIVE ALPACA variant

Project 006 v2 · Phase 6

This is the **live Alpaca paper-trading** variant of the submit-order Mule Process API. It replaces the old mock-response branch with a real HTTPS call to `paper-api.alpaca.markets/v2/orders`.

- Upstream caller: the `mulesoft-actions` Lambda (MCP server).
- Downstream vendor: [Alpaca paper trading](https://alpaca.markets/docs/api-references/trading-api/orders/).
- Canonical contract (unchanged): `submit-order.raml` + the RAML-defined `SubmitOrderResponse`.

The 400 and 403 validation branches are identical to the previous mock version. Only the happy path now speaks to Alpaca.

---

## Files in this folder (Mule 4 Maven layout)

| File | Role |
|---|---|
| `pom.xml` | Mule 4.4.x Maven descriptor. Java 17. `cloudhub-sandbox` profile for CloudHub 2.0 deploy. Zero creds (env vars only). |
| `mule-artifact.json` | Mule runtime descriptor (`minMuleVersion`, declared secure properties). |
| `.gitignore` | Standard Mule build ignores (`target/`, `.mule/`, `*.jar`). |
| `src/main/mule/submit-order.xml` | Main flow. Validation, normalize, HTTP call, response mapping. |
| `src/main/resources/api/submit-order.raml` | Canonical contract (unchanged from mock variant). |
| `src/main/resources/config.yaml` | Endpoint host/path + credential placeholders. Zero secrets. |
| `src/main/resources/transforms/submit-order-request.dwl` | Canonical request normalizer (unchanged). |
| `src/main/resources/transforms/submit-order-response.dwl` | Legacy mock response builder (kept for reference / mock fallback). |
| `src/main/resources/transforms/alpaca-request.dwl` | Canonical → Alpaca POST body. |
| `src/main/resources/transforms/alpaca-response.dwl` | Alpaca response → canonical `SubmitOrderResponse`. |
| `src/test/munit/submit-order-test-suite.xml` | MUnit tests: 403 (missing token), 400 (missing ticker), 200 happy-path (mock mode, zero Alpaca calls). |

> The XML uses `resource="transforms/foo.dwl"` for DataWeave lookups. Since `src/main/resources/` is on the Mule classpath, those references resolve to `src/main/resources/transforms/foo.dwl` without any XML edits.

---

## Build, test, run, deploy

All commands run from this folder (`mulesoft/process-apis/submit-order/`).

| Command | What it does |
|---|---|
| `mvn clean install` | Compile + package the Mule app into `target/submit-order-process-api-1.0.0-mule-application.jar`. Runs MUnit as part of the `test` phase. |
| `mvn mule:run -Dmock_mode=true` | Boot the app locally on `http://localhost:8081` in **mock mode** — returns `MULE-ORDER-*` canned responses, never calls Alpaca. For offline dev, L5 eval, demo. |
| `mvn mule:run` | Boot locally in **live** mode. Requires Alpaca `key_id` / `secret` to be supplied via Mule's Secure Properties file (`-Dmule.key=...`) or via JVM args. Not recommended on a laptop — use CloudHub for live. |
| `mvn test` | Run the MUnit suite (3 tests). Hermetic — no network. |
| `mvn deploy -Pcloudhub-sandbox` | Package + deploy to CloudHub 2.0 under app name `006-v2-trade-process-api`, region `us-east-2`, 0.1 vCores, 1 replica. Reads all auth from env vars (below). |

### Environment variables required for `mvn deploy -Pcloudhub-sandbox`

Zero credentials in git, per v2 steering rule 18. The operator sets these in their shell (or the CI secret store) before running `mvn deploy`.

**Option A — Connected App (REQUIRED for CI/automation):**

```bash
export ANYPOINT_CONNECTED_APP_ID="<from Anypoint Access Management → Connected Apps>"
export ANYPOINT_CONNECTED_APP_SECRET="<from the same screen>"
export ANYPOINT_ORG_ID="<your business-group / organization id>"
```

**Option B — Platform login (local dev only):**

```bash
export ANYPOINT_USERNAME="<your Anypoint login>"
export ANYPOINT_PASSWORD="<your Anypoint password>"
export ANYPOINT_ORG_ID="<your business-group / organization id>"
```

Either pair is enough. CI pipelines must use Option A — Platform password auth is disabled in all automated contexts per steering.

**Alpaca credentials are NOT set via Maven.** They flow into CloudHub via the Runtime Manager → Secure Properties UI after the app is deployed (see next section).

### First-deploy walkthrough

```bash
# 1. Sanity check
mvn clean install

# 2. Set the env vars above

# 3. Ship it
mvn deploy -Pcloudhub-sandbox

# 4. Wait until Runtime Manager shows STARTED (2–4 min)

# 5. Inject Alpaca creds via the Anypoint UI (see section below)
```

After step 5 the app is fully live. Subsequent redeploys only need steps 1–3; Secure Properties persist across deploys.

---

## How it wires up

```
Lambda (mulesoft-actions)
        │  POST {base_url}/api/orders
        │  { ticker, side, quantity, order_type, client_id, account_id, approval_token_hash, ... }
        ▼
[Mule] validate (400/403 branches unchanged)
        │
        ▼
[Mule] normalize  ->  vars.normalized
        │
        ▼
[Mule] mock_mode == "true"  ─yes─▶  canned response  ──▶  return
        │ no
        ▼
[Mule] alpaca-request.dwl   ->   Alpaca POST body
        │
        ▼
[Mule] http:request  →  https://paper-api.alpaca.markets/v2/orders
        │                      Headers: APCA-API-KEY-ID, APCA-API-SECRET-KEY
        ▼
[Mule] alpaca-response.dwl  ->  canonical SubmitOrderResponse
        │
        ▼
return { order_id: "ALPACA-...", status, ticker, side, quantity, submitted_at, mulesoft_reference }
```

Alpaca 4xx / auth errors are remapped to **HTTP 502** out of this flow. Alpaca timeouts / connectivity failures become **HTTP 504**. The Lambda never sees a raw Alpaca error code.

---

## Setting the secure properties at deploy time

Credentials live in AWS Secrets Manager under `/006-v2/vendors/alpaca-*`. They are NEVER committed to this repo — `config.yaml` only contains placeholders.

1. Read the secret locally (the operator running the deploy — not CI):

   ```bash
   aws secretsmanager get-secret-value \
     --secret-id /006-v2/vendors/alpaca \
     --query SecretString --output text
   ```

   You get back a JSON blob with `key_id` and `secret` fields.

2. In Anypoint → **Runtime Manager** → select the deployed app → **Settings** → **Properties** → **Show secure properties** → **Add property** twice:

   | Property name | Source |
   |---|---|
   | `alpaca.key_id` | the `key_id` value from the secret |
   | `alpaca.secret` | the `secret` value from the secret |

3. Click **Apply Changes**. CloudHub restarts the app (about 60–90 seconds).

4. Delete the shell history line that contained the secret value:

   ```bash
   history -d $(history | tail -2 | head -1 | awk '{print $1}')
   ```

Full step-by-step runbook in [`docs/v2-mulesoft-process-api-deploy.md`](../../../docs/v2-mulesoft-process-api-deploy.md) → section **Deploying submit-order with live Alpaca backend**.

---

## Running in mock mode for local dev

Sometimes you want the legacy canned-response behavior — e.g. running the L5 eval suite offline, or debugging the flow without burning paper-account activity. Set the Mule property `mock_mode=true`:

```bash
# Local dev via Anypoint Code Builder / mvn
cd <code-builder-project-root>
mvn mule:run -Dmock_mode=true
```

In mock mode:

- The `http:request` to Alpaca is skipped entirely.
- Response `order_id` starts with `MULE-ORDER-` (not `ALPACA-`).
- `GET /api/health` reports `"mode": "mock"`.

CloudHub deploys should leave `mock_mode` unset (or explicitly `false`). Mixing mock and live responses in a single eval run violates v2 steering rule 16.

---

## Expected happy-path output

A successful call against the paper account looks like:

```json
{
  "order_id": "ALPACA-abc12345-6789-def0-1234-56789abcdef0",
  "status": "accepted",
  "ticker": "AAPL",
  "side": "BUY",
  "quantity": 10,
  "submitted_at": 1735689600,
  "mulesoft_reference": "MS-REF-a1b2c3d4e5f6"
}
```

- `status` is Alpaca's order-lifecycle state. Immediately after submission it is usually `"accepted"` or `"new"`. A market order on a liquid name flips to `"filled"` within seconds. All three are valid per the canonical contract — the Lambda treats anything that's not an error as success.
- `order_id` is `"ALPACA-" + <alpaca order uuid>`. The prefix lets the audit log distinguish live orders from legacy `MULE-ORDER-*` mock ids.
- `submitted_at` is unix seconds, converted from Alpaca's ISO 8601 `created_at`.
- `mulesoft_reference` is our own minted `MS-REF-<12hex>`. The Lambda stores this in `IR_Audit_Log__c.MuleSoft_Reference__c`.

Verify the order also shows up in the Alpaca dashboard:

```
https://app.alpaca.markets/paper/dashboard/overview
```

→ **Orders** tab → your new order by `order_id`.

---

## Rollback

If the live variant misbehaves in production, roll back to the previous Mule app revision:

1. Find the last green revision in git:

   ```bash
   git log --oneline -- mulesoft/process-apis/submit-order/submit-order.xml
   ```

2. Check out the XML only (leave the rest of your working tree alone):

   ```bash
   git checkout <PREVIOUS_GREEN_SHA> -- \
     mulesoft/process-apis/submit-order/submit-order.xml
   ```

3. Redeploy the app from Anypoint Code Builder → **Deploy to CloudHub 2.0** → pick the same app name. CloudHub performs a zero-downtime replica swap.

4. Flip the Lambda back to mock mode if you also want to stop trusting the Mule app entirely:

   ```bash
   aws lambda update-function-configuration \
     --function-name mulesoft-actions \
     --environment "Variables={MULESOFT_MODE=mock,MULESOFT_SECRET_NAME=/006-v2/mulesoft/credentials}"
   ```

Rolling the XML back does not require changing the Secure Properties — the old XML simply never reads `alpaca.key_id` / `alpaca.secret`, so leaving them set is harmless.

---

## What this flow does NOT do

Per v2 steering:

- **No LLM calls.** This is pure routing + mapping (v2 Phase 6 non-negotiables).
- **No audit writes.** `IR_Audit_Log__c` writes happen in the mulesoft-api skill, *after* the Lambda returns. Doing it here would double-count and skip the skill's dual-auth / timeout branches.
- **No approval-token validation logic changes.** The 403-on-missing-hash branch is identical to the mock variant. The raw token never reaches this flow — it is SHA-256'd in the Lambda before the HTTP call.
- **Logs are redacted.** Token hash is truncated to the first 8 hex chars on log lines. `order_id` is logged in full only on success.
