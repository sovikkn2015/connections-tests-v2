# v3 MuleSoft Deploy — Step-by-Step Runbook

This is the authoritative MuleSoft-specific deploy runbook for Project 006
v3. It picks up where the top-level `RUNBOOK.md` Section 3 ends and walks
through the five Mule phases end to end.

**Companion docs:**
- `RUNBOOK.md` — overall project deploy (AWS + Salesforce + Mule + frontend)
- `docs/v3-mulesoft-gotchas.md` — the 4 Mule 4.9 boot-crash classes and
  how `make verify-mule` catches them

**Time estimate:** ~25 min once AWS + Anypoint credentials exist.

---

## Prerequisites

You already ran `bash scripts/0-preflight.sh` and it passed. That means:

- `mvn` ≥ 3.9.0 on PATH
- `JAVA_HOME` points at JDK 17
- `MULESOFT_ORG_ID`, `MULESOFT_CLIENT_ID`, `MULESOFT_CLIENT_SECRET` are in
  your local `.env`
- `bash scripts/seed-secrets.sh` has been run at least once — this pushes
  the Anypoint creds and all 3 Mule vendor secrets to AWS. Verify:

  ```bash
  aws ssm get-parameter --name /006-v3/mulesoft/client-id \
    --region us-east-1 --query Parameter.Name --output text
  # expect: /006-v3/mulesoft/client-id

  aws secretsmanager list-secrets --region us-east-1 \
    --query "SecretList[?starts_with(Name,'/006-v3/vendors/')].Name" \
    --output text
  # expect:  /006-v3/vendors/alpaca  /006-v3/vendors/dwolla  /006-v3/vendors/alpaca-webhook
  ```

If any are missing, run `bash scripts/seed-secrets.sh` and re-check.

---

## The five phases

```
 1. verify-mule                    local checks, no network           ~10 s
 2. mule-package                   mvn clean package × 3 apps         ~3 min
 3. mule-deploy                    publish to Exchange + CloudHub     ~10 min
 4. set-mule-secure-properties     PATCH Runtime Manager per-app       ~2 min
 5. mule-health                    curl each /api/health               ~10 s
```

Phase 4 is the step that's *not* in the Makefile — it's a separate script
in `scripts/set-mule-secure-properties.sh`. Everything else is a `make`
target.

---

## Phase 1 — verify-mule

Run this before every deploy cycle. It catches the 4 Mule 4.9 gotchas
locally so you don't waste a CloudHub build slot.

```bash
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft
make verify-mule
```

Passing output:

```
==> 1/4  checking mule-artifact.json exportedResources is non-empty...
    OK: submit-order lists 4 exported resources
    OK: initiate-wire lists 5 exported resources
    OK: order-status-webhook lists 3 exported resources

==> 2/4  checking all config.yaml values are quoted strings...
    OK: submit-order config.yaml all strings
    OK: initiate-wire config.yaml all strings
    OK: order-status-webhook config.yaml all strings

==> 3/4  checking all config.yaml ${*.host} values are resolvable hostnames...
    OK: submit-order hosts resolvable
    OK: initiate-wire hosts resolvable
    OK: order-status-webhook hosts resolvable

==> 4/4  checking no XML uses the nonexistent dw::core::Binaries::toHex function...
    OK: no toHex references

==> ALL CHECKS PASSED. Safe to run: make mule-package && make mule-deploy
```

If any check fails, fix the referenced source before continuing. Full
syntax references: `docs/v3-mulesoft-gotchas.md`.

---

## Phase 2 — mule-package

```bash
make mule-package
```

What it does, per app:

1. `mvn -B -e clean package -DskipTests`
2. Asserts the packaged jar contains `config.yaml`
3. Asserts the jar's `mule-artifact/mule-artifact.json` has a non-empty
   `exportedResources` list (catches Gotcha 1 at jar-seal time)

Output on success:

```
==> Packaging submit-order
    jar: mulesoft/process-apis/submit-order/target/submit-order-process-api-3.0.x-mule-application.jar
    OK: 4 resources exported in jar
==> Packaging initiate-wire
    ...
==> Packaging order-status-webhook
    ...
```

---

## Phase 3 — mule-deploy

```bash
# These three env vars are required by the mule-maven-plugin.
# Source them from AWS SSM (never paste into shell history).
export ANYPOINT_CONNECTED_APP_ID=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mulesoft/client-id --with-decryption \
  --query 'Parameter.Value' --output text)
export ANYPOINT_CONNECTED_APP_SECRET=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mulesoft/client-secret --with-decryption \
  --query 'Parameter.Value' --output text)
export ANYPOINT_ORG_ID=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mulesoft/org_id \
  --query 'Parameter.Value' --output text)

# JDK 17 required for Mule 4.9 mule-maven-plugin
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

make mule-deploy
```

Two maven phases per app, back to back:

```
==> submit-order: publishing to Anypoint Exchange...
    mvn -B deploy -DskipTests -DskipMunitTests=true
==> submit-order: deploying to CloudHub Sandbox...
    mvn -B mule:deploy -DmuleDeploy -DskipTests
==> initiate-wire: ...
==> order-status-webhook: ...
```

Each `mule:deploy` uploads the jar to CloudHub Sandbox and registers a
new deployment. The apps go into `APPLYING` immediately and then usually
enter `APPLIED` within 90 seconds. But — and this is critical — they
**will crash-loop** until Phase 4 finishes, because they need the
per-app secure properties to boot.

A fresh crash-loop during this window is expected. Don't panic.

---

## Phase 4 — set-mule-secure-properties (THE step that used to be manual)

This is the step that, up until April 2026, we did by hand via raw `curl`
PATCH against the Anypoint API. It's now a single idempotent script.

```bash
bash scripts/set-mule-secure-properties.sh
```

What it does:

1. Reads `ANYPOINT_CLIENT_ID`, `ANYPOINT_CLIENT_SECRET`,
   `MULE_SECURE_PROPERTIES_KEY` from AWS SSM
2. Reads Alpaca / Dwolla / webhook vendor secrets from AWS Secrets Manager
3. Auto-detects your API Gateway host (for the webhook's `mcp.endpoint_host`)
4. OAuths with the Anypoint Connected App → bearer token
5. Resolves your `organizationId` and Sandbox `environmentId`
6. For each of the three apps:
   - Resolves the CloudHub 2.0 deployment id
   - GETs the current deployment object
   - Merges in the correct `properties` (plain) + `secureProperties` (secret)
   - PATCHes the deployment
   - Polls the app's status every 10 s (up to 10 min) until it reaches
     RUNNING

Passing output:

```
[set-mule-props] Reading sources from AWS...
[set-mule-props] Sources OK.
[set-mule-props] Authenticating with Anypoint Connected App...
[set-mule-props] Org: 2dc8acc5-...  Env(Sandbox): 3d6484f8-...
[set-mule-props] --- openclaw-v3-submit-order ---
[set-mule-props] PATCH openclaw-v3-submit-order accepted (HTTP 202)
[set-mule-props] openclaw-v3-submit-order: RUNNING ✓
[set-mule-props] --- openclaw-v3-initiate-wire ---
...
[set-mule-props] All requested apps updated and reached RUNNING.
```

### Flags

| Flag | Meaning |
|---|---|
| `--dry-run` | Read AWS + Anypoint, build the patch body, print the property shape, **do not PATCH**. Use this the first time to confirm everything resolves. |
| `--no-wait` | PATCH but skip the RUNNING poll (useful in CI where a separate stage checks health) |
| `submit-order` / `initiate-wire` / `order-status-webhook` | Target one app |

### What properties get set per app

Derived from the `${...}` placeholders in the Mule XML flows. If you add
a new placeholder, add it to `build_plain_props` / `build_secure_props`
in the script.

| App | Plain properties | Secure properties |
|---|---|---|
| `openclaw-v3-submit-order` | `alpaca.endpoint_host`, `alpaca.endpoint_path`, `mock_mode` | `alpaca.key_id`, `alpaca.secret` |
| `openclaw-v3-initiate-wire` | `dwolla.endpoint_host`, `dwolla.endpoint_path`, `dwolla.token_host`, `dwolla.token_path`, `ofac.sdn_url`, `wire.dual_auth_threshold_usd`, `mock_mode` | `dwolla.client_id`, `dwolla.client_secret` |
| `openclaw-v3-order-status-webhook` | `mcp.endpoint_host`, `mcp.endpoint_path`, `mock_mode` | `webhook.hmac_secret`, `mcp.api_key` |

### Where the values come from

No hardcoded creds live in the repo. Every value traces back to one of:

| Value | Source |
|---|---|
| `alpaca.key_id` / `alpaca.secret` | Secrets Manager `/006-v3/vendors/alpaca` (keys `APCA_API_KEY_ID`, `APCA_API_SECRET_KEY`) |
| `dwolla.client_id` / `dwolla.client_secret` | Secrets Manager `/006-v3/vendors/dwolla` (keys `client_id`, `client_secret`) |
| `webhook.hmac_secret` | Secrets Manager `/006-v3/vendors/alpaca-webhook` (key `hmac_secret`) |
| `mcp.api_key` | Secrets Manager `/006-v3/vendors/alpaca-webhook` (key `mcp_bearer_token`), falls back to SSM `/006-v3/mcp/api-key` |
| `mule.secure.properties.key` | SSM `/006-v3/mulesoft/secure-properties-key` |
| `mcp.endpoint_host` | auto-detected from API Gateway `006-v3-mcp-api`, falls back to SSM `/006-v3/api-gateway/host` |

Rotating any vendor credential is a two-step:

```bash
# 1. Update the secret in AWS (manual or via seed-secrets.sh)
aws secretsmanager put-secret-value --secret-id /006-v3/vendors/alpaca \
  --secret-string '{"APCA_API_KEY_ID":"NEW","APCA_API_SECRET_KEY":"NEW","endpoint":"https://paper-api.alpaca.markets","mode":"paper"}' \
  --region us-east-1

# 2. Re-run the script to PATCH Runtime Manager
bash scripts/set-mule-secure-properties.sh submit-order
```

---

## Phase 5 — mule-health

```bash
make mule-health
```

What it does: `curl` each app's `/api/health` endpoint and print the
response body. Each app returns a JSON blob that names its current mode:

```
==> submit-order ===
{"status":"ok","mode":"alpaca-paper","api":"submit-order-process-api","version":"v3"}

==> initiate-wire ===
{"status":"ok","mode":"dwolla-sandbox","api":"initiate-wire-process-api","version":"v3"}

==> order-status-webhook ===
{"status":"ok","mode":"live","api":"order-status-webhook-process-api","version":"v3"}
```

Expected modes:

| App | `mode` value | Meaning |
|---|---|---|
| submit-order | `alpaca-paper` | Live; routes POST /api/orders to the Alpaca paper API |
| submit-order | `mock` | Runtime Manager property `mock_mode=true` (not a demo config) |
| initiate-wire | `dwolla-sandbox` | Live; routes to Dwolla Sandbox |
| initiate-wire | `mock` | Runtime Manager property `mock_mode=true` |
| order-status-webhook | `live` | Live; inbound webhooks forward to the MCP gateway |

If any endpoint returns `(unreachable)`:

1. Run `make mule-health` again — Runtime Manager occasionally rate-limits
   the first probe after a deploy.
2. Check the app status in Runtime Manager UI. If it shows `NOT_RUNNING`,
   Phase 4 did not converge — rerun `bash scripts/set-mule-secure-properties.sh`.

### Dynamic URL discovery (opt-in)

The URLs in the Makefile `mule-health` target are the ones from this
account's CloudHub business group (`5sc6y6-3.usa-e2.cloudhub.io`). If you
deployed into a different business group, the URLs will differ and you'll
get "unreachable" for all three.

For a fully-dynamic health check, use the Anypoint API to look up each
app's `publicUrl`:

```bash
BEARER=$(curl -s -X POST https://anypoint.mulesoft.com/accounts/api/v2/oauth2/token \
  -H 'Content-Type: application/json' \
  -d "$(jq -cn --arg ci "$ANYPOINT_CONNECTED_APP_ID" --arg cs "$ANYPOINT_CONNECTED_APP_SECRET" \
         '{grant_type:"client_credentials",client_id:$ci,client_secret:$cs}')" \
  | jq -r .access_token)

ORG_ID=$(curl -s -H "Authorization: Bearer $BEARER" \
  https://anypoint.mulesoft.com/accounts/api/me | jq -r .user.organization.id)
ENV_ID=$(curl -s -H "Authorization: Bearer $BEARER" \
  "https://anypoint.mulesoft.com/accounts/api/organizations/$ORG_ID/environments" \
  | jq -r '.data[] | select(.name=="Sandbox") | .id')

for app in openclaw-v3-submit-order openclaw-v3-initiate-wire openclaw-v3-order-status-webhook; do
  URL=$(curl -s -H "Authorization: Bearer $BEARER" \
    -H "X-ANYPNT-ORG-ID: $ORG_ID" -H "X-ANYPNT-ENV-ID: $ENV_ID" \
    "https://anypoint.mulesoft.com/amc/application-manager/api/v2/organizations/$ORG_ID/environments/$ENV_ID/deployments?name=$app" \
    | jq -r '.items[0].application.publicUrl // empty')
  echo "== $app =="
  curl -fsS --max-time 10 "${URL}/api/health" || echo "  (unreachable)"
  echo ""
done
```

---

## End-to-end one-liner

After everything above is wired, a full Mule deploy from cold is:

```bash
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft
make verify-mule && make mule-package && make mule-deploy \
  && bash scripts/set-mule-secure-properties.sh \
  && make mule-health
```

With a warm JVM + cached maven deps, total wall time is ~15 min.

`scripts/deploy-all.sh` runs the same sequence inside its `step_mulesoft`
function — you should never need to run these phases manually after the
first time.

---

## Known failure modes and fixes

| Symptom | Likely cause | Fix |
|---|---|---|
| `mvn deploy` fails with `Unauthorized` | Connected App creds wrong | Verify `ANYPOINT_CONNECTED_APP_ID` / `_SECRET` match what's in Anypoint → Access Management → Connected Apps |
| App status stuck `APPLYING` > 5 min | Secure properties not set | Run `bash scripts/set-mule-secure-properties.sh <app>` |
| App `NOT_RUNNING` after Phase 4 | Wrong `mule.secure.properties.key` — can't decrypt secrets | Confirm the key in `/006-v3/mulesoft/secure-properties-key` is the same one used when the app was first deployed. If you rotated the key mid-deploy, re-package and re-deploy. |
| `/api/health` returns `mode: mock` when you want live | `mock_mode=true` in Runtime Manager | Edit `build_plain_props` in `scripts/set-mule-secure-properties.sh` (set `"mock_mode":"false"`) and re-run the script |
| Webhook health OK, but inbound POSTs return 502 | `mcp.endpoint_host` not reachable from CloudHub | Check API Gateway `006-v3-mcp-api` exists in us-east-1 and the host printed during Phase 4 dry-run is correct |
| Script prints `No deployment found for <app>` | App was never deployed to CloudHub, or a different name | Run `make mule-deploy` first, then Phase 4 |

For any boot-time failure that looks like a Mule 4.9 config issue, re-run
`make verify-mule` — Gotchas 1–4 catch most of them. Full reference:
`docs/v3-mulesoft-gotchas.md`.
