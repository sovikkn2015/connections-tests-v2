# V3-B GO-LIVE — Operator Checklist

One page. Literal commands. For per-phase internals, rotation,
troubleshooting see `docs/v3-gateway-runbook.md`. For what's live vs
on-hold, see `docs/v3-b-architecture.md`. Run from the project root:

```bash
cd my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent
```

---

## Pre-flight

1. **AWS auth** — profile authenticated against account `875460787302`,
   region `us-east-1`:
   ```bash
   aws sts get-caller-identity
   aws configure get region   # expect us-east-1
   ```
2. **Secrets Manager** contains the MuleSoft client credentials:
   ```bash
   aws secretsmanager describe-secret \
       --secret-id /006-v2/mulesoft/credentials --region us-east-1
   ```
   Shared with 006 v2 — do not fork.
3. **Salesforce CLI** configured with the target org alias:
   ```bash
   sf org list
   export SF_ORG_ALIAS=ir-research-prod   # or whatever your alias is
   ```
4. **Tools present:** `anypoint-cli-v4 >= 1.6.14`, `docker`, `jq`,
   `python3`, `node` 18+, `sf` (Salesforce CLI).

---

## Phase 1 — Deploy gateway infra (~10 min)

```bash
bash scripts/deploy-all.sh
```

Orchestrates: verify-entitlement → deploy-flex-gateway → register API +
policies → deploy-agent-network (auto-skips on Developer/Trial).

Expected:
- Exits 0.
- `agent-fabric/.gateway-url.txt` exists.
- `agent-fabric/.build-receipts/gateway.json :: overall_status: pass`
  with `entitlement_path: B-fallback`.
- Three acceptance tests may report `failed` on first run — that's the
  degraded-but-shipped receipt. Phase 2 fixes it.

---

## Phase 2 — Apply Flex self-managed config

```bash
bash scripts/apply-flex-config.sh
```

Uploads `agent-fabric/flex-config/*.yaml` to
`s3://ir-flex-gateway-config-875460787302/v3-b/`, registers a new ECS
task definition with a config-sync init container, forces a service
redeploy.

Expected:
- `agent-fabric/.flex-config-applied.json` shows
  `mode: self-managed-static-config` and a new task definition revision.
- ALB probe should return a non-5xx within 2-3 min after task stable.

---

## Phase 3 — Deploy Apex

Deploy the single-choke-point client + its test + both credential
metadata types:

```bash
sf project deploy start \
  -d force-app/main/default/classes/IR_FlexGatewayClient.cls \
  -d force-app/main/default/classes/IR_FlexGatewayClientTest.cls \
  -d force-app/main/default/namedCredentials \
  -d force-app/main/default/externalCredentials \
  -o "$SF_ORG_ALIAS"
```

Then run the test:
```bash
sf apex run test --class-names IR_FlexGatewayClientTest \
  --result-format human --code-coverage --synchronous -o "$SF_ORG_ALIAS"
```

Expected: 16/16 pass, 96 % coverage on `IR_FlexGatewayClient`.

---

## Phase 4 — Point Apex at the live ALB

The `IR_FlexGateway` Named Credential's endpoint is driven by the
`FlexGatewayUrl` custom label. Grab the ALB URL and update the label:

```bash
GATEWAY_URL="$(cat agent-fabric/.gateway-url.txt)"
echo "$GATEWAY_URL"

sf data update record --sobject CustomLabel \
  --where "Name='FlexGatewayUrl'" \
  --values "Value='$GATEWAY_URL'" \
  -o "$SF_ORG_ALIAS"
```

If the `data update record` path is locked down in your org, use the
Salesforce Setup UI: Setup → Custom Labels → `FlexGatewayUrl` → edit
value → paste `$GATEWAY_URL` → Save.

Clear the Agentforce action cache by redeploying the agent bundle:
```bash
sf project deploy start -d force-app/main/default/aiAuthoringBundles -o "$SF_ORG_ALIAS"
```

---

## Phase 5 — Build and deploy the frontend

```bash
bash scripts/build-and-deploy.sh ir-research-v3
```

Reads `.gateway-url.txt` and (if present) `.registered-agents.json`,
writes `frontend/.env.local`, runs
`npm ci && npm run lint && npm test -- --run && npm run build`, syncs
`dist/` to the V3 SAM stack's S3 bucket, invalidates CloudFront.

Expected: `.build-receipts/frontend.json :: status: success` with a
real `cloudFrontUrl`.

---

## Phase 6 — Apex smoke test

```bash
sf apex run --file scripts/apex/smoke-gateway-callout.apex -o "$SF_ORG_ALIAS"
```

Probes 9 MCP tools + 2 Strands agents under one correlation id. Any
non-500 from the gateway counts as PASS (200, 429, 503 are all fine —
they mean the gateway is reachable and enforcing policy).

---

## Phase 7 — Run the 30-query eval

```bash
# 1. populate .env.eval at repo root:
cat > .env.eval <<'ENV'
V3_AGENT_QUERY_URL=https://<cloudfront-from-phase-5>/agent/query
V3_SF_USERNAME=$SF_ORG_ALIAS
V3_BEDROCK_REGION=us-east-1
V3_BEDROCK_JUDGE_MODEL=us.anthropic.claude-haiku-4-5-20251001-v1:0
V3_EVAL_TIMEOUT_S=60
ENV

# 2. run:
python scripts/eval/run_eval.py

# 3. (optional) compare to V2 + threshold gate:
python scripts/eval/compare_to_v2.py
python scripts/eval/threshold_check.py
```

Thresholds (from `scripts/eval/threshold_check.py`): pass rate
>= 74.67 % (V2 baseline minus 2 %), p95 <= 5485 ms, FINRA audit coverage
100 %, all 4 synthetic tests green.

---

## Rollback to V2

Flip one label + toggle one Named Credential. No AWS changes needed —
the V2 API Gateway (`ir-research-mcp`) keeps serving regardless.

```bash
# 1. disable the V3 gateway Named Credential
sf data update record --sobject NamedCredential \
  --where "DeveloperName='IR_FlexGateway'" \
  --values "CalloutOptions_AllowCallouts=false" \
  -o "$SF_ORG_ALIAS"

# 2. point the gateway label at a known-invalid placeholder
sf data update record --sobject CustomLabel \
  --where "Name='FlexGatewayUrl'" \
  --values "Value='https://PLACEHOLDER.flex-gateway.invalid'" \
  -o "$SF_ORG_ALIAS"

# 3. redeploy the agent bundle to clear the cache
sf project deploy start -d force-app/main/default/aiAuthoringBundles -o "$SF_ORG_ALIAS"
```

All 5 invocable actions carry a `FALLBACK_MSG` Apex constant pointing at
`IR_FlexGateway` + `FlexGatewayUrl` — so if the redeploy is skipped, the
failure mode is a clear error, not a silent outage.

Flipping forward after repair: reverse steps 1 and 2, redeploy once,
run Phase 6 smoke.

If V2 metadata itself has been removed from the org (check with
`sf data query -q "SELECT DeveloperName FROM NamedCredential" -o "$SF_ORG_ALIAS"`),
redeploy V2 from
`../my-agent-project-005-v2-integrations-fsi-investment_research_agent/force-app/`
before attempting rollback.
