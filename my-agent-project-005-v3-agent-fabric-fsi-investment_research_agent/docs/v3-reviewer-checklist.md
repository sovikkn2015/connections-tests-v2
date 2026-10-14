# 005 V3 — Reviewer Checklist (machine-gradable)

This is the review-loop threshold. Seven items, each with an exact command, the expected output, and a pass/fail rule. The reviewer subagent runs this in the next phase; a human can run it too.

Every item emits a line to stdout of the form:
```
[N] <title>: PASS | FAIL | SKIP
```
The reviewer considers V3 cut-over-ready only when all 7 items report PASS.

Prerequisites — exports used by every item:

```bash
export WORKDIR="$(pwd)/my-agent-project-005-v3-agent-fabric-fsi-investment_research_agent"
export SF_TARGET_ORG="ir-prod"
export FLEX_GW_URL="$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT Value FROM CustomLabel WHERE Name='IR_FlexGatewayUrl' LIMIT 1" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["records"][0]["Value"])')"
export ANYPOINT_ENV="Production"
```

---

## 1. Flex Gateway healthy

**What it proves:** The gateway container is alive, reachable, and has all 5 policies applied.

**Command:**
```bash
http_code=$(curl -sS -o /tmp/flex-health.json -w "%{http_code}" "$FLEX_GW_URL/health")
policy_count=$(anypoint-cli-v4 api-mgr policy list --environment "$ANYPOINT_ENV" \
  --target "fsi-mcp-servers" --output json | python3 -c 'import sys,json;print(len(json.load(sys.stdin)))')
echo "http_code=$http_code policy_count=$policy_count"
```

**Expected output:** `http_code=200 policy_count=5`

**Pass rule:** `http_code` is `200` AND `policy_count` is `5`.

---

## 2. Agent Registry populated

**What it proves:** All 4 agents and 3 MCP servers from `agent-network.yaml` are registered and discoverable.

**Command:**
```bash
anypoint-cli-v4 agent-fabric network list-components fsi-investment-research-v3 \
  --output json > /tmp/registry.json
agent_count=$(python3 -c 'import json;d=json.load(open("/tmp/registry.json"));print(sum(1 for c in d if c["type"] in ("agentforce","strands")))')
mcp_count=$(python3 -c 'import json;d=json.load(open("/tmp/registry.json"));print(sum(1 for c in d if c["type"]=="mcp"))')
echo "agents=$agent_count mcp_servers=$mcp_count"
```

**Expected output:** `agents=4 mcp_servers=3`

**Pass rule:** `agents` is exactly `4` AND `mcp_servers` is exactly `3`.

---

## 3. Apex refactor deployed

**What it proves:** Phase 3 deliverables landed in the org — new Custom Label exists, refactored classes deployed, tests pass.

**Command:**
```bash
label_exists=$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT COUNT() FROM CustomLabel WHERE Name='IR_FlexGatewayUrl'" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["totalSize"])')
broker_class=$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT COUNT() FROM ApexClass WHERE Name='IR_AgentBrokerClient'" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["totalSize"])')
last_test=$(sf apex run test --target-org "$SF_TARGET_ORG" \
  --class-names IR_AgentBrokerClientTest --synchronous --result-format json \
  | python3 -c 'import sys,json;d=json.load(sys.stdin)["result"]["summary"];print(f"{d[\"outcome\"]}:{d[\"testsRan\"]}:{d[\"passing\"]}")')
echo "label=$label_exists broker=$broker_class tests=$last_test"
```

**Expected output:** `label=1 broker=1 tests=Passed:N:N` (testsRan == passing, both > 0)

**Pass rule:** `label` is `1` AND `broker` is `1` AND `tests` starts with `Passed:` AND `testsRan == passing`.

---

## 4. 30-query eval pass rate >= 90%

**What it proves:** Apples-to-apples regression against V2's 30 queries. V3 must do at least as well.

**Command:**
```bash
# Assumes SF_AGENT_API_URL, SF_AGENT_TOKEN, SF_AGENT_ID, SF_ORG_ENDPOINT are set.
python3 "$WORKDIR/scripts/run-v3-eval.py"
eval_rc=$?
pass_rate=$(grep -E "^\*\*Pass rate:" "$WORKDIR/docs/phase5-eval-results.md" \
  | sed -E 's/.*Pass rate:\*\* ([0-9.]+)%.*/\1/')
echo "exit=$eval_rc pass_rate=$pass_rate"
```

**Expected output:** `exit=0 pass_rate=90.0` (or higher)

**Pass rule:** `exit` is `0` AND `pass_rate` is a number >= 90.

---

## 5. MNPI policy proven end-to-end

**What it proves:** A request carrying `FinServ__Shares__c` gets that field redacted by the gateway before it reaches the downstream tool. Value never appears in audit logs.

**Command:**
```bash
bash "$WORKDIR/scripts/v3-smoke-test.sh" --only mnpi
smoke_rc=$?
# verify the audit row has the redacted marker, not the value
redacted_ok=$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY AND Query__c LIKE '%REDACTED%'" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["totalSize"])')
# and verify no audit row leaked the raw sentinel value (12345)
leaked=$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY AND Query__c LIKE '%12345%'" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["totalSize"])')
echo "smoke=$smoke_rc redacted=$redacted_ok leaked=$leaked"
```

**Expected output:** `smoke=0 redacted>=1 leaked=0`

**Pass rule:** `smoke` is `0` AND `redacted` is `>= 1` AND `leaked` is exactly `0`.

---

## 6. Rate-limit policy proven

**What it proves:** Hammering the gateway above 25 req/s produces a 429 with retry-after.

**Command:**
```bash
bash "$WORKDIR/scripts/v3-smoke-test.sh" --only rate-limit
rl_rc=$?
# the smoke test records the observed 429 count in /tmp/v3-smoke-ratelimit.log
observed=$(grep -c "^429 " /tmp/v3-smoke-ratelimit.log 2>/dev/null || echo 0)
echo "exit=$rl_rc observed_429=$observed"
```

**Expected output:** `exit=0 observed_429>=1`

**Pass rule:** `exit` is `0` AND `observed_429` is `>= 1`.

---

## 7. FINRA audit writes visible

**What it proves:** Every gateway-origin call landed in `IR_Audit_Log__c` via the `finra-audit-logging` policy. This is the compliance-facing artifact that matters most.

**Command:**
```bash
audit_rows=$(sf data query --target-org "$SF_TARGET_ORG" \
  --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE Pipeline_Stage__c='gateway' AND CreatedDate = TODAY" --json \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["result"]["totalSize"])')
echo "audit_rows=$audit_rows"
```

**Expected output:** `audit_rows>=15` (matches the 15 gateway-crossing calls from the 30-query eval)

**Pass rule:** `audit_rows` is `>= 15`.

---

## Aggregated pass script (what the reviewer subagent runs)

```bash
#!/usr/bin/env bash
# Runs all 7 checks and exits 0 only if all pass.
set -u
pass=0; fail=0
for item in 1 2 3 4 5 6 7; do
  out=$(bash "$WORKDIR/scripts/verify-reviewer-check-${item}.sh" 2>&1) && rc=0 || rc=$?
  if [ $rc -eq 0 ]; then echo "[$item] PASS"; pass=$((pass+1)); \
  else echo "[$item] FAIL — $out" >&2; fail=$((fail+1)); fi
done
echo "summary: $pass/7 passing"
[ "$fail" -eq 0 ]
```

---

## How the reviewer subagent grades

- All 7 PASS — V3 is cut-over-ready. Write `.phase5-result.json` with `ready_for_review=true`, close out the review loop.
- Any FAIL — Reviewer captures the failing item's stdout/stderr, tags the owning phase (1-4), and opens a remediation task. Does not pass the threshold until the re-run is green.
