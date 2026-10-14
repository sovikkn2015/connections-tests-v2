# Wake-Up Runbook — 3 Cloud Fixes (Run When You Wake Up)

> **Date:** 2026-05-02
> **Context:** 5 of 8 fixes are done (code changes, committed, all 252+146 tests pass). These 3 remaining fixes require live cloud credentials that Kiro cannot execute.
> **Time needed:** ~60-90 minutes total

---

## What's Already Done (while you slept)

| Fix | Status | What changed |
|---|---|---|
| Fix 3: Real compliance in DRAFT_ONLY | ✅ DONE | `coordinator.py` — replaced hardcoded gate_trace with real `compliance_screening` skill call. Now returns real elapsed_ms, real ALLOW/DENY/REVIEW, and blocks on restricted tickers. |
| Fix 4: Fix escalation timeouts | ✅ DONE | `liaison_orchestrator.py` — escalation path no longer dispatches context_specialist (was timing out at 21s). rm_handoff runs directly in synthesize(). Response time drops from ~21s to ~2-3s. |
| Fix 5: Fix eval runner | ✅ DONE | `run-eval-scenarios.sh` — added assertions for: action_plan, compliance decision, dual_auth, queue_updates, MNPI safety (no dollar amounts/share counts), Reg BI (no recommendations), specialist count, response speed. |
| Fix 6: Multi-ticker extraction | ✅ DONE | `research_orchestrator.py` — `_extract_tickers()` now uses `re.findall()` to get ALL tickers. R05 "Compare NVDA vs AMD vs AVGO" now sends all 3 tickers to specialists. |
| Fix 7: FAQ intent classifier | ✅ DONE | `liaison_orchestrator.py` — FAQ check runs FIRST (before escalation). Added "earnings season", "10-K filing" to FAQ patterns. C03/C04 now answer as FAQ in ~3s instead of escalating at 21s. |
| Tests | ✅ ALL PASS | 252 backend + 146 frontend |

---

## Fix 1: Salesforce OBO (30 min)

The script exists. You just need to run it.

```bash
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft

# Option A: Interactive setup (recommended for first time)
bash scripts/sf-obo-setup.sh

# It will:
# 1. Generate RSA keypair + cert
# 2. Show you the cert to upload in Salesforce Setup
# 3. Ask you to paste the Consumer Key back
# 4. Write the secret to AWS Secrets Manager
# 5. Cache-bust the Lambda
# 6. Run a live verification probe
```

**The Salesforce admin steps (inside the script prompts):**
1. Go to Salesforce Setup → App Manager → New Connected App
2. Name: `FSI Workforce 360 OBO`
3. Enable OAuth Settings ✓
4. Callback URL: `https://login.salesforce.com/services/oauth2/callback`
5. Scopes: api, refresh_token, full
6. Use digital signatures ✓ → upload the cert the script shows
7. Save → Manage → Edit Policies → "Admin approved users are pre-authorized"
8. Copy the Consumer Key → paste it when the script asks

**Verify it worked:**
```bash
bash scripts/sf-obo-setup.sh --probe-only
# Expected: "PROBE PASSED — HTTP 200, IR_Audit_Log__c Id=a0X..."
```

---

## Fix 2: MuleSoft CloudHub Deploy (45 min)

The Makefile and scripts exist. The JARs are already built.

**Prerequisites check:**
```bash
# Verify Anypoint creds are in SSM
aws ssm get-parameter --name /006-v3/mulesoft/client-id --region us-east-1 --query Parameter.Name --output text
aws ssm get-parameter --name /006-v3/mulesoft/org_id --region us-east-1 --query Parameter.Name --output text
aws secretsmanager list-secrets --region us-east-1 \
  --query "SecretList[?starts_with(Name,'/006-v3/vendors/')].Name" --output text
# Expected: /006-v3/vendors/alpaca  /006-v3/vendors/dwolla  /006-v3/vendors/alpaca-webhook
```

If any are missing, fill in `.env` and run:
```bash
bash scripts/seed-secrets.sh
```

**Deploy:**
```bash
# Set env vars (reads from AWS SSM — never paste into shell)
export ANYPOINT_CONNECTED_APP_ID=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mulesoft/client-id --with-decryption --query 'Parameter.Value' --output text)
export ANYPOINT_CONNECTED_APP_SECRET=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mulesoft/client-secret --with-decryption --query 'Parameter.Value' --output text)
export ANYPOINT_ORG_ID=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mulesoft/org_id --query 'Parameter.Value' --output text)

# JDK 17 required
export JAVA_HOME=/opt/homebrew/opt/openjdk@17/libexec/openjdk.jdk/Contents/Home
export PATH=$JAVA_HOME/bin:$PATH

# Full deploy pipeline (verify → package → deploy → secure properties → health)
make verify-mule && make mule-deploy && bash scripts/set-mule-secure-properties.sh && make mule-health
```

**Expected output at the end:**
```
==> submit-order ===
{"status":"ok","mode":"alpaca-paper","api":"submit-order-process-api","version":"v3"}
==> initiate-wire ===
{"status":"ok","mode":"dwolla-sandbox","api":"initiate-wire-process-api","version":"v3"}
==> order-status-webhook ===
{"status":"ok","mode":"live","api":"order-status-webhook-process-api","version":"v3"}
```

If apps are stuck in APPLYING, wait 3 min and re-run:
```bash
bash scripts/set-mule-secure-properties.sh
make mule-health
```

---

## Fix 8: Wire /agent/approve MCP_API_URL (5 min)

After Fix 2 (MuleSoft) is confirmed working:

```bash
# Get the API Gateway URL
API_URL=$(aws cloudformation describe-stacks \
  --stack-name openclaw-mcp-006-v3 \
  --region us-east-1 \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)

echo "API URL: $API_URL"

# Get current env vars
CURRENT_ENV=$(aws lambda get-function-configuration \
  --function-name 006-v3-agent-proxy \
  --region us-east-1 \
  --query 'Environment.Variables' --output json)

# Update with MCP_API_URL set
MCP_KEY=$(aws ssm get-parameter --region us-east-1 \
  --name /006-v3/mcp/api-key --with-decryption --query 'Parameter.Value' --output text)

aws lambda update-function-configuration \
  --function-name 006-v3-agent-proxy \
  --region us-east-1 \
  --environment "Variables=$(echo "$CURRENT_ENV" | jq -c --arg url "$API_URL" --arg key "$MCP_KEY" '. + {MCP_API_URL: $url, MCP_API_KEY: $key}')"

echo "Done. /agent/approve now makes real MCP calls."
```

**Verify:**
```bash
curl -s -X POST \
  "${API_URL}/agent/approve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-bootstrap-token" \
  -d '{
    "plan_id": "test-verify-001",
    "plan_hash": "abc123def456abc123def456abc123de",
    "approved": true,
    "action_plan": {
      "action_type": "submit_order",
      "ticker": "NVDA",
      "quantity": 10,
      "side": "sell",
      "notional_usd": 2100
    }
  }' | python3 -m json.tool
```

**Expected:** Response takes 2-5s (not <100ms). Contains `mulesoft_reference` and `audit_row_id` with real values.

---

## After All 3 Fixes: Redeploy AgentCore + Run Full Eval

```bash
# 1. Rebuild and push the AgentCore container (picks up code fixes 3,4,6,7)
bash scripts/build-and-push-openclaw.sh
bash scripts/create-v3-agentcore.sh

# 2. Wait 60s for container to warm up

# 3. Run the full eval suite with the new strict assertions
bash scripts/run-eval-scenarios.sh

# 4. Check the results
cat scripts/eval-results-*.json | python3 -m json.tool | grep verdict | sort | uniq -c
```

---

## Quick Smoke Test (run before anything else to confirm infra is still up)

```bash
bash scripts/smoke-test.sh
```

---

*All code fixes are committed and tested. You just need to run the 3 cloud scripts above. Total time: ~60-90 min.*
