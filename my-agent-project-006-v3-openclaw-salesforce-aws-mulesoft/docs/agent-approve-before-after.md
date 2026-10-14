# /agent/approve — Before vs After

> **What changed:** The approve endpoint was a hardcoded stub that returned fake gate results. Now it makes real MCP calls to MuleSoft and Salesforce.
> **Files changed:** `aws/mcp-servers/agent-proxy/app.py`, `aws/sam-template.yaml`

---

## Before (hardcoded stub)

**File:** `aws/mcp-servers/agent-proxy/app.py` `_handle_approve()`

**What the code did:**

```python
# The comment literally said:
# "A future implementation would call the real skill sequence"

return _respond(200, {
    "status": "ok",
    "plan_id": plan_id,
    "gate_trace": [
        {"gate": "hitl",      "status": "passed", "detail": "token verified"},
        {"gate": "dual_auth", "status": "passed", "detail": "below threshold"},
        {"gate": "mulesoft",  "status": "passed", "detail": "CloudHub live"},
        {"gate": "audit",     "status": "passed", "detail": "all gates passed, logged"},
    ],
})
```

**What actually happened when Marcus clicked Approve:**

```
Browser clicks Approve
  → POST /agent/approve
  → Lambda returns hardcoded JSON instantly (<100ms)
  → No HMAC token verification
  → No dual-auth threshold check
  → No MuleSoft call (no order submitted to Alpaca)
  → No Salesforce write (no IR_Audit_Log__c row)
  → Frontend animates 4 green checkmarks
  → Nothing real happened
```

**Consequences:**
- Alpaca never received an order
- Dwolla never received a wire instruction
- Salesforce has zero audit rows for the approval
- A regulator asking "show me the trade record" gets nothing
- The gate animation was a lie — pure theater

---

## After (real MCP calls)

**What the code does now:**

```
Browser clicks Approve
  → POST /agent/approve {plan_id, plan_hash, approved, action_plan}
  → Lambda runs 4 gates sequentially:

  Gate ④ HITL
    → Accepts the approval (token was minted during draft turn)
    → Records in gate_trace

  Gate ⑤ Dual-auth
    → Reads notional_usd from action_plan
    → wire > $100K → status: "in_progress" (needs 2nd approver)
    → trade > $500K → status: "in_progress" (needs 2nd approver)
    → below threshold → status: "passed"
    → If in_progress: skips MuleSoft (awaiting 2nd approver)

  Gate ⑥ MuleSoft (REAL HTTP call)
    → POST to mulesoft-actions MCP Lambda /tools/call
    → MCP Lambda calls CloudHub submit-order → Alpaca paper API
    → Returns: mulesoft_reference: "MS-TRD-a8f3c2e1"
    → Or returns error (Alpaca rejected, CloudHub down, etc.)
    → Gate status reflects REAL outcome (passed or failed)

  Gate ⑦ Audit (REAL HTTP call)
    → POST to salesforce-crm MCP Lambda /tools/call
    → Writes IR_Audit_Log__c to Salesforce with:
        Action__c = TRADE_SUBMITTED (or WIRE_INITIATED)
        Principal_Id__c = marcus@demo.com
        Agent_Id__c = action_specialist
        Approved_By__c = marcus@demo.com
        Mulesoft_Reference__c = MS-TRD-a8f3c2e1
        Gate_Trace__c = full JSON trace
    → Returns real Salesforce record Id

  → Returns real gate_trace to frontend
  → Frontend animates gates with REAL outcomes
  → If MuleSoft fails → gate ⑥ shows RED honestly
  → Audit row exists in Salesforce — queryable by regulators
```

**What's different:**

| Aspect | Before | After |
|--------|--------|-------|
| MuleSoft call | None | Real HTTP → mulesoft-actions MCP → CloudHub → Alpaca/Dwolla |
| Audit write | None | Real HTTP → salesforce-crm MCP → IR_Audit_Log__c in Salesforce |
| Dual-auth check | Hardcoded "passed" | Real threshold check against notional_usd |
| Gate ⑥ failure | Never fails | Fails honestly if Alpaca rejects or CloudHub is down |
| Audit trail | Empty | Real Salesforce record with Id, gate trace, MuleSoft reference |
| Response time | <100ms (instant fake) | 2-5s (real network calls) |
| FINRA auditable | No | Yes — IR_Audit_Log__c row with cross-stitch fields |

---

## Code changes

### 1. `aws/mcp-servers/agent-proxy/app.py`

- Added `MCP_API_URL`, `MCP_API_KEY`, `HITL_SIGNING_KEY` env var reads
- Added `_mcp_call()` helper — makes real HTTP POST to MCP server tools/call endpoint
- Rewrote `_handle_approve()`:
  - Gate ④: records HITL acceptance
  - Gate ⑤: real threshold check against `action_plan.notional_usd`
  - Gate ⑥: real `_mcp_call("mulesoft-actions", method, args)` — returns real reference or real error
  - Gate ⑦: real `_mcp_call("salesforce-crm", "write_audit_log", record)` — writes real SF row
  - Rejection path also writes audit row (rejection is an auditable event)

### 2. `aws/sam-template.yaml`

- Added 3 env vars to AgentProxyFunction:
  - `MCP_API_URL` — resolves to the API Gateway URL at deploy time
  - `MCP_API_KEY` — resolves from SSM `/006-v3/mcp/api-key`
  - `HITL_SIGNING_KEY` — resolves from SSM `/006-v3/hitl/signing-key`

---

## To deploy

```bash
cd aws
sam build --template-file sam-template.yaml
sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name openclaw-mcp-006-v3 \
  --region us-east-1 \
  --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
  --no-confirm-changeset --no-fail-on-empty-changeset \
  --resolve-s3
```

Or just run `bash scripts/deploy-all.sh --skip-sf --skip-cdk --skip-mulesoft --skip-agentcore --skip-frontend` to redeploy only the SAM stack.

---

## To verify

```bash
# Approve a plan — should take 2-5s (real calls), not <100ms (fake)
curl -s -X POST \
  "https://e5zbqnkmx8.execute-api.us-east-1.amazonaws.com/v3/agent/approve" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer dev-bootstrap-token" \
  -d '{
    "plan_id": "test-plan-001",
    "plan_hash": "abc123def456abc123def456abc123de",
    "approved": true,
    "approver_principal_id": "marcus@demo.com",
    "action_plan": {
      "action_type": "submit_order",
      "ticker": "NVDA",
      "quantity": 100,
      "side": "sell",
      "notional_usd": 21000
    }
  }' | python3 -m json.tool
```

**Expected:** Response includes `mulesoft_reference` (real) and `audit_row_id` (real SF Id). Gate ⑥ shows real status. Takes 2-5 seconds.

**If MuleSoft fails:** Gate ⑥ shows `"status": "failed"` with the real error message. Gate ⑦ still fires (audit logs failures too).

---

*Written 2026-05-02. The stub existed since 2026-04-29. Should have been fixed the first time MuleSoft was confirmed live.*
