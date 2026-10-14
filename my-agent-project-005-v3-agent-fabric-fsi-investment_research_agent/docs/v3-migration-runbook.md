# 005 V3 Migration Runbook — V2 → V3 Cutover

**Owner:** IR Platform Team
**Duration:** ~6 hours deploy + 48 hours parallel-run + 2-hour cutover
**Rollback time:** ~5 minutes (Custom Label / Custom Metadata swap)

This is the definitive playbook. Run it top to bottom. Every step lists the exact command, the expected output, and the rollback.

---

## Prerequisites

All must be green before starting step 1. If any prereq fails, stop and remediate — do not proceed.

| # | Check | Command | Expected |
|---|---|---|---|
| P1 | AWS CLI authenticated | `aws sts get-caller-identity` | JSON with Account, Arn |
| P2 | Anypoint CLI authenticated | `anypoint-cli-v4 account user` | current user + org |
| P3 | SF CLI authenticated to target org | `sf org display --target-org ir-prod` | Connected + access token |
| P4 | Docker daemon running | `docker info \| head -1` | non-error line |
| P5 | Phase 0 verified (V2 baseline healthy) | `python3 scripts/run-v3-eval.py` in DRY_RUN mode | exit 0, eval suite structure valid |
| P6 | Feature flag `V3_Cutover__mdt` record exists | `sf data query --query "SELECT DeveloperName, Value__c FROM V3_Cutover__mdt"` | 1 row with Value__c = "0" |
| P7 | Langfuse still writable (kept during V3) | `curl -sS -o /dev/null -w "%{http_code}" $LANGFUSE_HOST/api/public/health` | `200` |

```bash
export WORKDIR="$(pwd)/my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent"
export SF_TARGET_ORG="ir-prod"
export AWS_REGION="us-east-1"
export ANYPOINT_ENV="Production"
export FLEX_GW_RUNTIME_FABRIC="ir-flex-rtf-prod"
```

---

## Step 1 — Deploy Flex Gateway (Phase 1 artifact)

Flex Gateway sits between Salesforce and the Lambda MCP servers. It runs as a container in your own AWS account and is managed from Anypoint Platform.

```bash
# 1a. Register the gateway with Anypoint Platform (one-time per env)
anypoint-cli-v4 runtime-fabric register \
  --name "$FLEX_GW_RUNTIME_FABRIC" \
  --organization "$ANYPOINT_ORG_ID" \
  --environment "$ANYPOINT_ENV"
# expected: "Registration token: <JWT>" — capture as FLEX_REG_TOKEN

# 1b. Launch the gateway container on ECS Fargate
aws ecs update-service \
  --cluster ir-flex-cluster \
  --service ir-flex-gateway \
  --force-new-deployment \
  --region "$AWS_REGION"
# expected: deployments[0].status = "PRIMARY", rolloutState = "IN_PROGRESS"

# 1c. Wait for healthy
aws ecs wait services-stable \
  --cluster ir-flex-cluster \
  --services ir-flex-gateway \
  --region "$AWS_REGION"
# expected: returns 0 within ~4 min

# 1d. Verify gateway is reporting in
anypoint-cli-v4 runtime-fabric describe "$FLEX_GW_RUNTIME_FABRIC"
# expected: status "Active", connectedReplicas >= 1

# 1e. Apply the 5 policies from agent-fabric/policies/
for policy in mnpi-filter rate-limit circuit-breaker finra-audit auth-mtls; do
  anypoint-cli-v4 api-mgr policy apply \
    --policy-file "$WORKDIR/agent-fabric/policies/${policy}.yaml" \
    --environment "$ANYPOINT_ENV"
done
# expected per policy: "Policy <name> applied. PolicyBindingId: <uuid>"
```

**Rollback for Step 1:**
```bash
aws ecs update-service --cluster ir-flex-cluster --service ir-flex-gateway \
  --desired-count 0 --region "$AWS_REGION"
```
Zero desired count takes the gateway down without removing the registration. V2 Custom Label `IR_AWS_API_URL` still points at the legacy API Gateway, so all traffic continues to work.

---

## Step 2 — Deploy Agent Registry (Phase 2 artifact)

The Registry tells every agent in the org what other agents and MCP servers exist. Without it, the Broker cannot route.

```bash
# 2a. Validate the network definition
anypoint-cli-v4 agent-fabric network validate \
  --file "$WORKDIR/agent-fabric/agent-network.yaml"
# expected: "Validation successful. 4 agents, 3 mcpServers, 3 routing policies"

# 2b. Register the network
anypoint-cli-v4 agent-fabric network apply \
  --file "$WORKDIR/agent-fabric/agent-network.yaml" \
  --environment "$ANYPOINT_ENV"
# expected: "Agent network 'fsi-investment-research-v3' created (revision 1)"

# 2c. Verify all 7 components are discoverable
anypoint-cli-v4 agent-fabric network list-components fsi-investment-research-v3
# expected: exactly 7 rows —
#   ir-research-orchestrator (agentforce)
#   ir-compliance-agent (agentforce)
#   financial-analysis-agent (strands)
#   sentiment-analysis-agent (strands)
#   sec-edgar (mcp)
#   market-data (mcp)
#   news-search (mcp)
```

**Rollback for Step 2:**
```bash
anypoint-cli-v4 agent-fabric network delete fsi-investment-research-v3 \
  --environment "$ANYPOINT_ENV"
```
Flex Gateway still works standalone; Broker routing reverts to manual Apex routing in V2 Custom Labels.

---

## Step 3 — Deploy Apex refactor (Phase 3 artifact)

The refactored Apex actions stop calling Named Credentials directly and start calling the Flex Gateway URL (which becomes the Agent Broker endpoint). They read the new Custom Label `IR_FlexGatewayUrl`.

```bash
# 3a. Deploy Custom Label IR_FlexGatewayUrl — points to the new gateway.
#     IMPORTANT: do NOT remove IR_AWS_API_URL yet. Both coexist during the 48h
#     parallel run so rollback is instant.
sf project deploy start \
  --source-dir "$WORKDIR/force-app/main/default/labels" \
  --target-org "$SF_TARGET_ORG" \
  --wait 10
# expected: "Deploy succeeded" + Components Deployed includes IR_FlexGatewayUrl

# 3b. Deploy refactored Apex classes (IR_AgentBrokerClient, refactored IR_*Action classes)
sf project deploy start \
  --source-dir "$WORKDIR/force-app/main/default/classes" \
  --target-org "$SF_TARGET_ORG" \
  --test-level RunLocalTests \
  --wait 20
# expected: "Deploy succeeded" + 100% tests passing (>=75% coverage)

# 3c. Verify the new label is readable
sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT Name, Value FROM CustomLabel WHERE Name IN ('IR_FlexGatewayUrl','IR_AWS_API_URL')"
# expected: 2 rows. IR_FlexGatewayUrl -> Flex Gateway URL; IR_AWS_API_URL -> legacy API Gateway

# 3d. Smoke-test one Apex action with the broker off (cutover pct = 0)
sf apex run --target-org "$SF_TARGET_ORG" --file "$WORKDIR/scripts/apex/smoke-company-lookup.apex"
# expected: successful lookup, routes via V2 path because V3_CUTOVER_PCT = 0
```

**Rollback for Step 3:**
```bash
# revert by re-deploying the pre-refactor tag
sf project deploy start --source-dir "$WORKDIR/force-app/main/default/classes" \
  --target-org "$SF_TARGET_ORG" --predestructive-changes \
  --manifest "$WORKDIR/scripts/rollback/pre-v3-manifest.xml"
```
Or simply leave the refactor deployed and keep `V3_CUTOVER_PCT = 0`: the new classes fall back to the V2 path when the cutover pct is 0.

---

## Step 4 — Activate routing (Phase 4 artifact)

Flip the cutover percentage in Custom Metadata. The Apex actions read this on every call and route a percentage of traffic through the Broker. Everyone else keeps using V2.

```bash
# 4a. 10% traffic to V3
sf data update record --sobject V3_Cutover__mdt \
  --where "DeveloperName='Default'" \
  --values "Value__c='10'" \
  --target-org "$SF_TARGET_ORG"
# expected: "Successfully updated record of type V3_Cutover__mdt"

# 4b. Soak for 2 hours. Watch the dashboard.
echo "Visit: https://anypoint.mulesoft.com/visualizer/dashboards/fsi-ir-v3-dashboard"

# 4c. If green after 2h, ramp to 50%
sf data update record --sobject V3_Cutover__mdt \
  --where "DeveloperName='Default'" --values "Value__c='50'" \
  --target-org "$SF_TARGET_ORG"

# 4d. Soak for 2 more hours, then ramp to 100%
sf data update record --sobject V3_Cutover__mdt \
  --where "DeveloperName='Default'" --values "Value__c='100'" \
  --target-org "$SF_TARGET_ORG"
```

**Rollback for Step 4 (the big red button):**
```bash
# Single command. Takes ~5 minutes to propagate (CustomMetadata cache).
sf data update record --sobject V3_Cutover__mdt \
  --where "DeveloperName='Default'" --values "Value__c='0'" \
  --target-org "$SF_TARGET_ORG"
```
All traffic returns to the V2 path immediately.

---

## Step 5 — Run Phase 5 eval + smoke test

```bash
# 5a. Smoke test the gateway
bash "$WORKDIR/scripts/v3-smoke-test.sh"
# expected: exit 0, all 4 checks pass

# 5b. 30-query eval against the V3 path
export SF_AGENT_API_URL="https://api.salesforce.com/einstein/ai-agent/v1"
export SF_AGENT_TOKEN="$(curl -s -X POST "$IR_ECA_TOKEN_URL" \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["access_token"])')"
export SF_AGENT_ID="$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT Id FROM BotDefinition WHERE DeveloperName='IR_Research_Agent' LIMIT 1" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["records"][0]["Id"])')"
export SF_ORG_ENDPOINT="$(sf org display --target-org "$SF_TARGET_ORG" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["instanceUrl"])')"
python3 "$WORKDIR/scripts/run-v3-eval.py"
# expected: exit 0, PASS rate >= 90%, results at docs/phase5-eval-results.md

# 5c. Verify reviewer checklist items 1-7 (see docs/v3-reviewer-checklist.md)
```

**Rollback for Step 5:**
Nothing to roll back — this is verification only. If eval fails, execute the Step 4 rollback.

---

## Cutover strategy

48-hour parallel run, then 3-stage ramp. Rollback via one Custom Metadata change.

```
Hour  0 — Deploy Flex Gateway (Step 1). V3 path exists but carries 0% traffic.
Hour  1 — Deploy Agent Registry (Step 2).
Hour  2 — Deploy Apex refactor (Step 3). Still 0% to V3.
Hour  4 — Feature-flag 10%. V2 carries 90%. Watch dashboards for 2h.
Hour  6 — Ramp to 50%. Watch for 2h.
Hour  8 — Ramp to 100%.
Hour 48 — Decom V2 API Gateway (separate change — not in this runbook).
```

**Rollback trigger conditions — any one is enough:**

- V3 error rate > 2% over 5 minutes on any tool
- Circuit breaker opens on any MCP server
- MNPI redaction count spikes unexpectedly (would indicate agents leaking holdings)
- p95 latency on L2 queries > 5s
- Eval pass rate drops below 90%

**Rollback (one command, ~5 min propagation):**
```bash
sf data update record --sobject V3_Cutover__mdt \
  --where "DeveloperName='Default'" --values "Value__c='0'" \
  --target-org "$SF_TARGET_ORG"
```
That single Custom Metadata change flips every Apex action back to the legacy `IR_AWS_API_URL` path. The V2 API Gateway never left the air during the parallel run.

---

## Done-criteria checklist (the 7 items from the parent task)

These mirror `docs/v3-reviewer-checklist.md`. All must be green for V3 to be considered cut over.

- [ ] 1. Flex Gateway healthy — `/health` returns 200, all 5 policies applied
- [ ] 2. Agent Registry populated — 4 agents + 3 MCP servers discoverable
- [ ] 3. Apex refactor deployed — `IR_FlexGatewayUrl` label exists, classes deployed, tests green
- [ ] 4. 30-query eval pass rate ≥ 90% — `run-v3-eval.py` exits 0
- [ ] 5. MNPI policy proven — smoke test confirms `FinServ__Shares__c` is redacted end-to-end
- [ ] 6. Rate-limit policy proven — smoke test forces a throttle and observes a 429
- [ ] 7. FINRA audit writes visible — `IR_Audit_Log__c` has ≥ 15 gateway-origin rows from the eval run

---

## Reference: file map

| Artifact | Path | Produced by phase |
|---|---|---|
| Flex Gateway policies (5) | `agent-fabric/policies/*.yaml` | Phase 1 |
| Agent network definition | `agent-fabric/agent-network.yaml` | Phase 2 |
| Refactored Apex classes | `force-app/main/default/classes/IR_*.cls` | Phase 3 |
| Cutover metadata | `force-app/main/default/customMetadata/V3_Cutover.Default.md-meta.xml` | Phase 4 |
| New Flex Gateway label | `force-app/main/default/labels/IR_FlexGatewayUrl.labels-meta.xml` | Phase 3 |
| 30-query eval suite | `docs/30-query-eval-suite.md` | Phase 5 |
| Eval runner | `scripts/run-v3-eval.py` | Phase 5 |
| Dashboard | `agent-fabric/visualizer-dashboard.json` | Phase 5 |
| Smoke test | `scripts/v3-smoke-test.sh` | Phase 5 |
| Reviewer checklist | `docs/v3-reviewer-checklist.md` | Phase 5 |
| This runbook | `docs/v3-migration-runbook.md` | Phase 5 |
