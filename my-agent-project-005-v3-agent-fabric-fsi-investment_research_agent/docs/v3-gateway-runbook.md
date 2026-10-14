# V3 Gateway Runbook

Operational guide for the V3 Agent Fabric Flex Gateway layer. Keep this
document next to the scripts in `scripts/`. All commands assume:

- AWS profile authenticated against account `875460787302`, region `us-east-1`
- `anypoint-cli-v4` >= 1.6.14 installed globally
- MuleSoft creds live in Secrets Manager at `/006-v2/mulesoft/credentials`

## Table of contents

1. [Quick health check](#1-quick-health-check)
2. [Rotating gateway credentials](#2-rotating-gateway-credentials)
3. [Redeploying a single policy](#3-redeploying-a-single-policy)
4. [Rolling back to V2 Named Credential](#4-rolling-back-to-v2-named-credential)
5. [Full redeploy from scratch](#5-full-redeploy-from-scratch)
6. [Troubleshooting FAQ](#6-troubleshooting-faq)
7. [Decommission / teardown](#7-decommission--teardown)

---

## 1. Quick health check

```bash
cd my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent

# ALB reachable?
curl -I "$(cat agent-fabric/.gateway-url.txt)"

# ECS task running?
aws ecs describe-services --cluster ir-flex-gateway-cluster \
    --services ir-flex-gateway-svc \
    --query 'services[0].{desired:desiredCount,running:runningCount,status:status}'

# Gateway connected to Anypoint RTM control plane?
anypoint-cli-v4 runtime-mgr gateways managed list --output table

# Container logs (last 50 lines):
aws logs tail /ecs/ir-flex-gateway --since 10m --format short | tail -50

# API + policies registered?
anypoint-cli-v4 api-mgr api list --output table | grep fsi-mcp-servers
anypoint-cli-v4 api-mgr policy list <api-instance-id>
```

What you want to see:

- `runningCount = 1`, `status = ACTIVE`
- ALB curl returns 1xx–4xx (anything non-5xx)
- `gateways managed list` shows one entry in `Connected` state
- `api list` shows `fsi-mcp-servers` with 5 policies

---

## 2. Rotating gateway credentials

The Flex Gateway authenticates to Anypoint with a client-credentials pair
stored in Secrets Manager. Rotation is a two-step operation.

### 2a. Generate a new Connected App secret in Anypoint

1. Anypoint → Access Management → Connected Apps → select the existing
   `openclaw-006-v2-mulesoft-mcp` app
2. Click **Rotate secret**, copy the new `client_secret`
3. Do NOT revoke the old secret yet — the ECS task needs it until the
   deployment rolls

### 2b. Update Secrets Manager and force a new task deployment

```bash
# Write the new secret version
aws secretsmanager put-secret-value \
    --secret-id /006-v2/mulesoft/credentials \
    --region us-east-1 \
    --secret-string '{
      "client_id":"<same as before>",
      "client_secret":"<NEW>",
      "base_url":"<same>",
      "organization_id":"<same>",
      "environment_id":"<same>"
    }'

# Force ECS service to pull the new secret
aws ecs update-service \
    --cluster ir-flex-gateway-cluster \
    --service ir-flex-gateway-svc \
    --force-new-deployment \
    --region us-east-1

# Watch the rollout (~3 min)
aws ecs wait services-stable \
    --cluster ir-flex-gateway-cluster \
    --services ir-flex-gateway-svc

# Verify the new task is Connected
anypoint-cli-v4 runtime-mgr gateways managed list --output table
```

### 2c. Revoke old secret in Anypoint

Once the new task is Connected and `runningCount=1`, go back to the Anypoint
UI and revoke the previous secret. If you skip this step you leave a valid
pair exposed from any prior backups.

> **Do NOT** commit the new secret to git. Secrets Manager is the only copy.

---

## 3. Redeploying a single policy

Policies are stored as YAML bindings in `agent-fabric/policies/`. Edit the
YAML, then re-run the registration for just that one policy.

```bash
cd my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent

# 1. Edit the binding
vi agent-fabric/policies/rate-limit.yaml

# 2. Dry-run: inspect what will change
API_ID="$(jq -r .api_instance_id agent-fabric/.registered-apis.json)"
anypoint-cli-v4 api-mgr policy list $API_ID --output json | jq '.'

# 3. Remove the old binding, reapply
# (replace <policy-id> with the id from the list above)
anypoint-cli-v4 api-mgr policy remove $API_ID <policy-id>

# 4. Re-apply only the changed policy (short single-file re-run):
bash scripts/register-api-and-policies.sh
```

The register script is idempotent — it reuses the existing `fsi-mcp-servers`
API instance and only applies policies. Already-applied policies pass
through thanks to `--allowDuplicated`, so existing bindings for the other
4 policies are untouched.

---

## 4. Rolling back to V2 Named Credential

If the gateway is degraded and you need Agentforce back on the V2 direct
path immediately, the rollback is **a Salesforce-side config flip**, not an
AWS change. The V2 API Gateway (stack: `ir-research-mcp`) keeps serving
traffic regardless of V3 state.

### Procedure (takes 2-3 minutes)

1. In Salesforce, open Setup → Named Credentials → `V3_Flex_Gateway`
2. Toggle **Callout Options → Allow Callouts** off
3. In Setup → Custom Metadata → `Agent_MCP_Routing__mdt`:
   - Set `active_path` = `V2_DIRECT`
4. Clear the Agentforce action cache: Setup → Agent Studio →
   `IR_Research_Agent` → Deploy (no changes needed, just redeploy metadata)

The orchestrator agent will now route to `https://og256a1neb.execute-api.us-east-1.amazonaws.com/prod`
using the `V2_API_Gateway` Named Credential. V3 can then be repaired without
user-facing downtime.

### Flip back forward after repair

Reverse the same three steps. Validate with one L1 query against the
UI before announcing all-clear.

---

## 5. Full redeploy from scratch

```bash
cd my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent

# One-shot orchestrator — runs all 4 phases + acceptance tests
bash scripts/deploy-all.sh

# Expected runtime: ~8-12 min
#   Phase 0 (entitlement):   ~5s
#   Phase 1 (gateway):       ~5-8 min (docker pull + ECR push + ECS start)
#   Phase 2 (api+policies):  ~30s
#   Phase 3 (agent network): ~10s (or skipped in B-fallback)
#   Acceptance tests:        ~15s
```

Final artifacts:

- `agent-fabric/.build-receipts/gateway.json` — machine-readable pass/fail
- `agent-fabric/.build-receipts/gateway-summary.md` — human summary
- `agent-fabric/.gateway-url.txt` — stable ALB URL for Named Credential

---

## 6. Troubleshooting FAQ

### FAQ 6.1 — ALB returns 502

**Symptom:** `curl http://<alb-dns>/` → `HTTP/1.1 502 Bad Gateway`.

**Most common causes (in order):**

1. **ECS task not yet healthy.** After `aws ecs update-service` or the
   initial create, the ALB target group takes 2–4 min to register the task.
   Check:
   ```bash
   aws elbv2 describe-target-health \
       --target-group-arn "$(jq -r .target_group_arn agent-fabric/.gateway-deploy.json)"
   ```
   Look for `targetHealth.state=healthy`. If `state=draining` or `unhealthy`
   check the target group health check path. The default is `/` and Flex
   Gateway returns 200 on `/` once connected.
2. **Flex container stuck in startup.** Runtime Manager token-exchange
   hasn't completed. Logs will show `waiting for connection to control plane`:
   ```bash
   aws logs tail /ecs/ir-flex-gateway --since 5m --format short
   ```
   If credentials are valid but no connection, the issue is usually that the
   ECS task is in a subnet without outbound internet. Default VPC subnets
   have an IGW route — if you moved the service to private subnets, add a
   NAT gateway.
3. **Security group mismatch.** The ALB SG must allow port 80 from
   `0.0.0.0/0`, and the task SG must allow port `8081` from the ALB SG.
   `scripts/deploy-flex-gateway.sh` reuses one SG for both (idempotent
   self-referencing rule) — if you tightened it, re-add:
   ```bash
   aws ec2 authorize-security-group-ingress \
       --group-id <sg-id> --protocol tcp --port 8081 --source-group <sg-id>
   ```

### FAQ 6.2 — `gateway-not-connected` in Anypoint UI

**Symptom:** ECS task is running, container has no errors, but Anypoint
shows the gateway as `Disconnected` or never appears in
`runtime-mgr gateways managed list`.

**Root cause:** The Flex Gateway `latest` image ships with a runtime-manager
binary that **requires a one-time token-exchange** before it can register
with a specific Anypoint org. The ECS container env vars
(`FLEX_RTMGR_CLIENT_ID`, `FLEX_RTMGR_CLIENT_SECRET`) are sufficient for
ongoing registration but not for the initial bootstrap.

**Fix (one-time manual step):**

```bash
# 1. Exec into the running container
CLUSTER=ir-flex-gateway-cluster
TASK_ID=$(aws ecs list-tasks --cluster $CLUSTER --service-name ir-flex-gateway-svc \
            --query 'taskArns[0]' --output text | awk -F/ '{print $NF}')
aws ecs execute-command --cluster $CLUSTER --task $TASK_ID \
    --container flex-gateway --command "/bin/sh" --interactive

# 2. Inside the container, run the registration CLI baked into the image:
flexctl register \
    --organization "$FLEX_RTMGR_ORG" \
    --environment  "$FLEX_RTMGR_ENV" \
    --client-id    "$FLEX_RTMGR_CLIENT_ID" \
    --client-secret "$FLEX_RTMGR_CLIENT_SECRET" \
    --gateway-name  "ir-flex-gateway-ecs"

# 3. Exit, then kill the task so ECS rolls a fresh one with the
#    registration token cached in the ECR image layer:
aws ecs stop-task --cluster $CLUSTER --task $TASK_ID
```

After this one-time bootstrap, future rotations via
`aws ecs update-service --force-new-deployment` will keep the registration.

### FAQ 6.3 — `api-mgr policy apply` fails with `policy not found`

**Symptom:**
```
ERROR Policy content-filter version 2.0.3 not found in Exchange
```

**Cause:** The Anypoint marketplace policy naming varies by Mule runtime
version. Our YAML bindings use MuleSoft's canonical names, but the CLI
expects the Exchange asset id under your org's group.

**Fix:** query for the asset id the org actually has access to:

```bash
anypoint-cli-v4 api-mgr policy list -m \
    --client_id "$CLIENT_ID" --client_secret "$SECRET" \
    --organization "$ORG" --environment "$ENV" \
    --output json | jq '.[] | {assetId:.["Asset ID"], version:.["Version"]}'
```

Take the matching `assetId`/`version` pair and update the `case` statement
in `scripts/register-api-and-policies.sh :: apply_policy()`. Re-run the
script.

### FAQ 6.4 — Agentforce calls fail with `Named Credential not configured`

**Symptom:** Salesforce Agent traces show `V3_Flex_Gateway` → 404.

**Cause:** The Named Credential in Salesforce points to a stale ALB URL
(the ALB was recreated with a different DNS name during a redeploy).

**Fix:**

```bash
NEW_URL="$(cat agent-fabric/.gateway-url.txt)"
sf org:login:web --alias ir-research-prod
sf data:record:update --sobject NamedCredential \
    --where "DeveloperName='V3_Flex_Gateway'" \
    --values "Endpoint=$NEW_URL"
```

### FAQ 6.5 — Entitlement check says Agent Fabric = false

**Symptom:** `scripts/verify-entitlement.sh` exits with code 2; the receipt
shows `"agent_fabric": false`.

**Cause:** The Anypoint subscription tier is Developer/Trial, which includes
Flex Gateway but NOT the Agent Fabric registry.

**Expected behaviour:** `deploy-all.sh` recognises this as the B-fallback
path. It deploys the gateway + policies (phases 1 and 2) and skips the
agent network push. Agentforce calls still flow, just via Named Credential
rather than via Agent Fabric's central broker.

**If you need full Agent Fabric:** upgrade the MuleSoft subscription. There
is no script-side workaround.

---

## 7. Decommission / teardown

Use only if shutting down V3 entirely (e.g. pivoting to pure V2).

```bash
REGION=us-east-1

# 1. Drain ECS service
aws ecs update-service --cluster ir-flex-gateway-cluster \
    --service ir-flex-gateway-svc --desired-count 0 --region $REGION
aws ecs delete-service --cluster ir-flex-gateway-cluster \
    --service ir-flex-gateway-svc --force --region $REGION

# 2. Delete listener + ALB + target group
LB=$(aws elbv2 describe-load-balancers --names ir-flex-gateway-alb \
        --query 'LoadBalancers[0].LoadBalancerArn' --output text --region $REGION)
aws elbv2 describe-listeners --load-balancer-arn $LB \
    --query 'Listeners[].ListenerArn' --output text --region $REGION \
    | xargs -n1 aws elbv2 delete-listener --region $REGION --listener-arn
aws elbv2 delete-load-balancer --load-balancer-arn $LB --region $REGION
aws elbv2 delete-target-group \
    --target-group-arn "$(aws elbv2 describe-target-groups --names ir-flex-gateway-tg \
        --query 'TargetGroups[0].TargetGroupArn' --output text --region $REGION)" \
    --region $REGION

# 3. Delete cluster + log group
aws ecs delete-cluster --cluster ir-flex-gateway-cluster --region $REGION
aws logs delete-log-group --log-group-name /ecs/ir-flex-gateway --region $REGION

# 4. Delete ECR repo
aws ecr delete-repository --repository-name ir-flex-gateway --force --region $REGION

# 5. Remove API + policies from Anypoint
anypoint-cli-v4 api-mgr api delete "$(jq -r .api_instance_id agent-fabric/.registered-apis.json)"

# 6. Flip Salesforce back to V2 Named Credential (section 4 above)
```

> **Do not** delete the Secrets Manager secret — it's shared with 006 v2.
> Let that project own the lifecycle.

### FAQ 6.6 — `register-api-and-policies.sh` exits with code 3 / "no asset matching given parameters"

**Symptom:** The script prints
```
Error while trying to retrieve asset. Reason: There is no asset matching given parameters.
REST fallback failed — API instance requires a pre-published Exchange asset.
```
and exits 3.

**Root cause:** Anypoint API Manager requires every managed API instance to
be backed by a published Exchange asset (RAML / OAS / HTTP / MCP). The
`anypoint-cli-v4 v1.6.14` does **not** ship an `exchange asset upload`
sub-command (only `copy`, `delete`, `deprecate`). Without the asset the
`api-mgr api manage` CLI call and the `POST /apimanager/api/v1/.../apis`
REST call both return 400.

**Fix (one-time manual step, ~3 min):**

1. Open Anypoint Exchange → https://anypoint.mulesoft.com/exchange/
2. Click **Publish new asset** → **HTTP API** (not RAML, not OAS)
3. Fill in:
   - Asset name: `fsi-mcp-servers`
   - Asset ID: `fsi-mcp-servers`
   - Version: `1.0.0`
   - API Type: `HTTP`
   - Description: `Front door for FSI MCP servers (V3 Agent Fabric)`
4. Save. Do not promote to public — private is fine.
5. Re-run:
   ```bash
   bash scripts/register-api-and-policies.sh
   ```
   The CLI `api-mgr api manage` call now finds the asset and creates the
   Flex-bound API instance; the 5 policies apply in the same run.

**Alternative (if you have the mule-maven-plugin installed):** publish via
Maven:

```bash
cat > fsi-mcp-servers.json <<JSON
{"name":"fsi-mcp-servers","apiSpec":"http","endpoint":"/"}
JSON
mvn deploy:deploy-file \
    -DgroupId=${ANYPOINT_ORG_ID} \
    -DartifactId=fsi-mcp-servers \
    -Dversion=1.0.0 \
    -Dpackaging=json \
    -Dfile=fsi-mcp-servers.json \
    -DrepositoryId=exchange \
    -Durl=https://maven.anypoint.mulesoft.com/api/v3/organizations/${ANYPOINT_ORG_ID}/maven
```

**If upgrading CLI is feasible:** `anypoint-cli-v4 v2.x` (Salesforce Spring
'25 release+) adds `exchange asset publish` which removes this manual step
entirely. Verify with `npm info anypoint-cli-v4 version`.
