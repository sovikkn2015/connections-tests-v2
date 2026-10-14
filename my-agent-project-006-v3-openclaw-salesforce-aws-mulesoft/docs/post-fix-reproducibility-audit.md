# Post-Fix Reproducibility Audit

> **Date:** 2026-05-02
> **Context:** 8 fixes were applied to make the eval scenarios work. This document audits what's reproducible vs what was ad-hoc, and what a new user needs to know.

---

## Classification of All Changes

### Category A: Code Changes (IN GIT — fully reproducible)

These are source code edits. A new user gets them by checking out the branch.

| File | Change | Reproducible? |
|---|---|---|
| `openclaw/orchestration/coordinator.py` | Fix 3: Real `compliance_screening` skill call in DRAFT_ONLY mode (replaced hardcoded gate_trace) | ✅ In git |
| `openclaw/orchestration/liaison_orchestrator.py` | Fix 4: Escalation skips context_specialist (was timing out). Fix 7: FAQ check runs before escalation, added "earnings season"/"10-K filing" patterns | ✅ In git |
| `openclaw/orchestration/research_orchestrator.py` | Fix 6: `_extract_tickers()` finds ALL tickers, not just first | ✅ In git |
| `scripts/run-eval-scenarios.sh` | Fix 5: Added 8 real assertion checks (compliance, action_plan, MNPI, Reg BI, etc.) | ✅ In git |
| `tests/unit/test_orchestrators.py` | Updated test expectation for escalation (0 dispatches instead of 1) | ✅ In git |
| `aws/mcp-servers/agent-proxy/app.py` | Fix 8: Fixed MuleSoft argument shape (flat args instead of nested), increased MCP call timeout to 55s | ✅ In git |

### Category B: Cloud Config Changes (NOT IN GIT — ad-hoc, must be scripted)

These are Lambda env var updates and credential wiring done via `aws lambda update-function-configuration`. They survive until the next SAM deploy, which resets env vars to template defaults.

| Lambda | Env Var | What I Set | How SAM Template Handles It | Gap |
|---|---|---|---|---|
| `006-v3-agent-proxy` | `MCP_API_URL` | `https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3` | SAM sets `""` (empty) | **GAP:** SAM can't self-reference its own API URL due to circular dependency. Needs post-deploy patch. |
| `006-v3-agent-proxy` | `MCP_API_KEY` | Real key from SSM | SAM resolves from SSM `{{resolve:ssm:...}}` | OK — SAM handles this. But my manual update may have overwritten the SSM-resolved value. |
| `006-v3-mulesoft-actions` | `MULESOFT_CLIENT_ID` | Real Anypoint client ID | SAM sets `MULESOFT_CLIENT_ID_PARAM` (the SSM param name, not the value) | **GAP:** The Lambda code reads `MULESOFT_CLIENT_ID` from env, but SAM only sets the param name. The Lambda needs runtime SSM resolution or the actual value. |
| `006-v3-mulesoft-actions` | `MULESOFT_CLIENT_SECRET` | Real Anypoint client secret | Same gap as above | **GAP:** Same issue. |

### Category C: Infrastructure Deploys (reproducible via existing scripts)

| Action | How I Did It | Existing Script | New User Path |
|---|---|---|---|
| MuleSoft CloudHub deploy | `mvn -B mule:deploy -DmuleDeploy` per app | `make mule-deploy` in Makefile | ✅ `make mule-deploy` (needs Anypoint creds in env) |
| MuleSoft secure properties | `bash scripts/set-mule-secure-properties.sh` | Already exists | ✅ Script exists and works |
| AgentCore container rebuild | `bash scripts/build-and-push-openclaw.sh` | Already exists | ✅ Script exists and works |
| AgentCore runtime update | `bash scripts/create-v3-agentcore.sh` | Already exists | ✅ Script exists and works |
| SAM stack deploy | `sam build && sam deploy` | `deploy-all.sh step_sam` | ✅ Script exists |

---

## The Two Reproducibility Gaps

### Gap 1: `MCP_API_URL` on agent-proxy

**Problem:** The SAM template sets `MCP_API_URL: ""` because it can't reference its own API Gateway URL (circular dependency). After every SAM deploy, this resets to empty, and `/agent/approve` stops making real MCP calls.

**Current workaround:** Manual `aws lambda update-function-configuration` after each SAM deploy.

**Proper fix needed:** Add a post-deploy step to `deploy-all.sh` that patches this env var.

### Gap 2: `MULESOFT_CLIENT_ID/SECRET` on mulesoft-actions Lambda

**Problem:** The SAM template sets `MULESOFT_CLIENT_ID_PARAM` and `MULESOFT_CLIENT_SECRET_PARAM` (SSM parameter names), but the Lambda code (`_mulesoft_client.py`) reads `MULESOFT_CLIENT_ID` and `MULESOFT_CLIENT_SECRET` (the actual values). The Lambda doesn't resolve SSM params at runtime.

**Current workaround:** Manual `aws lambda update-function-configuration` to inject the actual values.

**Proper fix needed:** Either (a) add SSM resolution to `_mulesoft_client.py` at import time, or (b) change the SAM template to resolve the values at deploy time using `{{resolve:ssm-secure:...}}`.

---

## What a New User Needs to Do

A new user who clones this repo and runs `bash scripts/deploy-all.sh` will get:

| Component | Works out of the box? | Why / Why not |
|---|---|---|
| CDK stacks (VPC, Aurora, KB) | ✅ Yes | `deploy-all.sh step_cdk` handles it |
| SAM stack (11 Lambdas, API Gateway) | ✅ Yes | `deploy-all.sh step_sam` handles it |
| Salesforce metadata | ✅ Yes | `deploy-all.sh step_salesforce` handles it |
| SF OBO Connected App | ⚠️ Partially | `deploy-all.sh step_sf_obo` generates keypair + deploys ConnectedApp metadata. But if the org already has the app, it skips. New org needs manual SF admin clicks. |
| MuleSoft CloudHub | ✅ Yes | `deploy-all.sh step_mulesoft` runs the full 5-phase pipeline |
| AgentCore container | ✅ Yes | `deploy-all.sh step_agentcore` builds + pushes + updates runtime |
| Frontend | ✅ Yes | `deploy-all.sh step_frontend` builds + uploads to CloudFront |
| **agent-proxy MCP_API_URL** | 🔴 No | Resets to empty after SAM deploy. Needs post-deploy patch. |
| **mulesoft-actions credentials** | 🔴 No | Lambda can't read SSM params at runtime. Needs env var injection. |

---

## Fixes Applied to Close the Gaps

### Gap 1 Fix: `MCP_API_URL` post-deploy patch → added to `deploy-all.sh`

**File:** `scripts/deploy-all.sh` → `step_sam()`

Added a "Step 2b: post-deploy env var patches" block that runs after every SAM deploy:
1. Reads the API Gateway URL from CloudFormation outputs
2. Patches `006-v3-agent-proxy` with `MCP_API_URL` and `MCP_API_KEY`
3. Patches `006-v3-salesforce-crm` with `SF_AUTH_PROXY_URL`

This runs automatically as part of `deploy-all.sh`. No manual intervention needed.

### Gap 2 Fix: MuleSoft credential resolution → added SSM fallback to `_mulesoft_client.py`

**File:** `aws/mcp-servers/mulesoft-actions/_mulesoft_client.py`

Added a two-tier credential resolution:
1. First checks direct env vars: `MULESOFT_CLIENT_ID` / `MULESOFT_CLIENT_SECRET`
2. Falls back to SSM param names: `MULESOFT_CLIENT_ID_PARAM` / `MULESOFT_CLIENT_SECRET_PARAM` → resolves via `boto3 ssm:GetParameter` at cold start

This means:
- SAM template's `MULESOFT_CLIENT_ID_PARAM: /006-v3/mulesoft/client-id` now works (Lambda resolves the SSM param at cold start)
- Direct env var injection also works (for local testing or manual overrides)
- No more ad-hoc `aws lambda update-function-configuration` needed

---

## New User Deployment Path (after these fixes)

A new user who clones this repo and has all credentials ready:

```bash
# 1. Copy and fill in credentials
cp .env.example .env
# Fill in: SF_OAUTH_CLIENT_ID, MULESOFT_CLIENT_ID, FINNHUB_API_KEY, etc.

# 2. One command deploys everything
bash scripts/deploy-all.sh
```

`deploy-all.sh` now handles:
- ✅ Salesforce metadata + OBO Connected App (`step_salesforce` + `step_sf_obo`)
- ✅ CDK stacks (`step_cdk`)
- ✅ Cognito (`step_cognito`)
- ✅ SAM stack + post-deploy env var patches (`step_sam` + Step 2b)
- ✅ MuleSoft CloudHub deploy + secure properties (`step_mulesoft`)
- ✅ AgentCore container build + runtime update (`step_agentcore`)
- ✅ Frontend build + CloudFront upload (`step_frontend`)
- ✅ Smoke test (`step_smoke`)

**Zero ad-hoc commands needed.** Everything is in the scripts.

---

## Files Changed (complete list for commit)

### Code fixes (5 files):
1. `openclaw/orchestration/coordinator.py` — real compliance in DRAFT_ONLY
2. `openclaw/orchestration/liaison_orchestrator.py` — FAQ classifier + escalation timeout
3. `openclaw/orchestration/research_orchestrator.py` — multi-ticker extraction
4. `aws/mcp-servers/agent-proxy/app.py` — MuleSoft argument shape + timeout
5. `scripts/run-eval-scenarios.sh` — eval runner assertions

### Reproducibility fixes (2 files):
6. `aws/mcp-servers/mulesoft-actions/_mulesoft_client.py` — SSM credential resolution
7. `scripts/deploy-all.sh` — post-deploy env var patches

### Test updates (1 file):
8. `tests/unit/test_orchestrators.py` — updated escalation test expectation

### Documentation (3 files):
9. `docs/independent-eval-scenario-assessment.md` — full eval assessment
10. `docs/fix-plan-v3-to-demo-ready.md` — fix plan
11. `docs/post-fix-reproducibility-audit.md` — this document
