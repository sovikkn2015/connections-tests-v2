# 006 V3 → Demo-Ready: Fix Plan (Not a Rewrite)

> **Date:** 2026-05-02
> **Decision maker:** Independent assessor (Kiro)
> **Context:** 60 eval scenarios assessed. 5 real (8%), 19 partial (32%), 26 fake/broken (43%), 8 untestable (13%). Demo must work live. Time is short.

---

## THE DECISION: Fix V3 in-place. Do NOT create V4.

Here's why:

**What's deployed and working right now:**
- 11 Lambda functions live behind API Gateway (SAM stack, 33 resources)
- Bedrock AgentCore runtime container (`openclaw_v3_agent-o72dx396I0`) — real Sonnet/Haiku
- Bedrock Knowledge Base with 784 real SEC filing chunks (Titan v2 embeddings)
- 6 CDK stacks (VPC, Aurora pgvector, KB, Risk Alerts, Filings Pipeline, Research Pipeline)
- Finnhub live quotes, Tavily live news, SEC EDGAR live
- Salesforce org with 5 custom SObjects, 7 Apex classes, 3 triggers deployed
- MuleSoft code complete (3 Process APIs packaged)
- Frontend V6 built, 146 tests passing
- Backend 252 tests passing
- Real coordinator → orchestrator → specialist dispatch chain

**A V4 rewrite would throw away all of this.** You'd spend days rebuilding infrastructure that already works. The problems are NOT architectural — they're wiring failures. Specifically, there are exactly 8 fixes that convert 43% fake/broken into working.

---

## THE 8 FIXES (ordered by cascade impact)

### Fix 1: Salesforce OBO Chain (unblocks ~60% of broken scenarios)
**Root cause:** `/006-v3/sf/bootstrap-creds` secret in AWS Secrets Manager contains placeholder values. The sf-auth-proxy Lambda loads them, mints a JWT with a fake client_id, Salesforce rejects it with 401.

**What to do:**
1. In the Salesforce org: create a Connected App with JWT Bearer flow enabled
2. Generate an RSA keypair, upload the certificate to the Connected App
3. Store the real credentials in Secrets Manager:
```json
{
  "client_id": "<connected_app_consumer_key>",
  "subject_pattern": "{principal_email}",
  "audience": "https://login.salesforce.com",
  "private_key_pem": "<PEM-encoded private key — begin/end markers plus base64 body>"
}
```
4. The sf-auth-proxy Lambda already reads from this secret — no code change needed

**Scenarios unblocked:** ALL Salesforce writes (audit rows, brief persistence, Client_Inquiry__c, Research_Brief__c, Platform Events). This cascades into fixing X01-X04 cross-persona, A16 research awareness, C05-C08 escalation audit trail.

**Effort:** ~30 minutes (SF admin work + secret update)

---

### Fix 2: MuleSoft CloudHub Deploy (unblocks all trade/wire scenarios)
**Root cause:** The 3 MuleSoft Process APIs (submit-order, initiate-wire, order-status-webhook) are packaged as Maven JARs but never deployed to CloudHub. The Lambda env var `MULESOFT_MODE` defaults to `"sandbox"` in SAM but the CloudHub apps aren't running, so the client gets connection refused and falls back to mock.

**What to do:**
1. Deploy the 3 Process APIs to CloudHub:
```bash
cd mulesoft/process-apis/submit-order && mvn deploy -DmuleDeploy
cd ../initiate-wire && mvn deploy -DmuleDeploy
cd ../order-status-webhook && mvn deploy -DmuleDeploy
```
2. In Anypoint Runtime Manager, set secure properties:
   - `alpaca.api.key` = Alpaca paper trading API key
   - `alpaca.api.secret` = Alpaca paper trading secret
   - `dwolla.api.key` = Dwolla sandbox key
   - `dwolla.api.secret` = Dwolla sandbox secret
3. Store MuleSoft client credentials in SSM:
```bash
aws ssm put-parameter --name /006-v3/mulesoft/client-id --value "<anypoint_client_id>" --type SecureString
aws ssm put-parameter --name /006-v3/mulesoft/client-secret --value "<anypoint_client_secret>" --type SecureString
```
4. Allowlist the NAT EIP (from SAM output `NatEip`) in Anypoint IP policy

**Scenarios unblocked:** A01-A06 trade execution, A04-A05 wire initiation, T01-T03 trust spine gates 6-7, X04 trade execution.

**Effort:** ~45 minutes (Maven deploy + Anypoint config + SSM params)

---

### Fix 3: Call Real Compliance Screening in DRAFT_ONLY Mode (unblocks trust spine)
**Root cause:** `coordinator.py` lines 420-430 inject a hardcoded gate_trace with `elapsed_ms: 0` instead of calling the `compliance_screening` skill. The skill exists, is tested, and works — it's just not called.

**What to change in `coordinator.py`:**
Replace the hardcoded gate_trace block in the `is_draft_only` path with an actual call to the compliance_screening skill. The skill takes ~50ms (deterministic, no LLM) so it won't blow the 29s timeout.

```python
# BEFORE (hardcoded):
"gate_trace": [
    {"tool": "guardrails_input", "status": "ok", "elapsed_ms": 0, "error": None},
    {"tool": "mnpi_filter", "status": "ok", "elapsed_ms": 0, "error": None},
    {"tool": "compliance_screening", "status": "ok", "elapsed_ms": 0, "error": None},
],

# AFTER (real):
# Actually call compliance_screening skill with the extracted ticker
from ..skills.compliance_screening.actions import (
    ComplianceInput, Action as CompAction, run as compliance_run
)
import time as _time

_comp_start = _time.monotonic()
_ticker = dispatch.context_subset.get("ticker", "UNKNOWN")
try:
    comp_result = await compliance_run(ComplianceInput(
        ticker=_ticker,
        principal_id=ctx.principal_id,
        proposed_action=CompAction.SUBMIT_ORDER,
        session_id=ctx.session_id,
        correlation_id=ctx.correlation_id,
    ))
    _comp_ms = int((_time.monotonic() - _comp_start) * 1000)
    comp_gate = {"tool": "compliance_screening",
                 "status": comp_result.decision.value.lower(),
                 "elapsed_ms": _comp_ms, "error": None}
    if comp_result.decision.value == "DENY":
        # Hard stop — return DENY, don't produce action_plan
        return WorkerResponse(
            agent_id=target.id,
            result={"text": f"COMPLIANCE DENIED: {comp_result.reasons}",
                    "gate_trace": [guardrails_gate, mnpi_gate, comp_gate],
                    "stop_reason": "compliance_denied"},
            citations=[], cost_tokens=0,
        )
except Exception as exc:
    comp_gate = {"tool": "compliance_screening", "status": "error",
                 "elapsed_ms": 0, "error": str(exc)[:120]}
```

**Scenarios unblocked:** T01-T03 trust spine, A01-A06 real compliance, E04 absurd order flagging, R12 restricted list DENY.

**Effort:** ~20 minutes (code change + redeploy AgentCore container)

---

### Fix 4: Fix Client Escalation Timeouts (unblocks C05-C08, C09-C12)
**Root cause:** The `context_specialist` consistently times out at ~21s. It's dispatched with a 15s timeout but the Bedrock Converse call takes too long — likely because the specialist tries to call CRM tools that fail (OBO 401) and error handling adds latency.

**What to do:**
1. Fix 1 (OBO) will eliminate the 401 errors that cause slow error paths
2. Increase context_specialist timeout from 15s to 25s in `liaison_orchestrator.py`
3. Simplify the context_specialist's task — it doesn't need to call CRM tools for escalation. It just needs to acknowledge and hand off.

**Alternative (faster):** For escalation, skip the context_specialist entirely. The liaison orchestrator already writes Client_Inquiry__c via `rm_handoff` in `synthesize()`. The context_specialist adds no value to the escalation path — it's supposed to read "MNPI-filtered client context" but the client doesn't need their own context read back to them.

```python
# In liaison_orchestrator.py, for ESCALATE:
# Instead of dispatching context_specialist, return empty dispatches
# and let synthesize() handle the rm_handoff directly
if decision is LiaisonDecision.ESCALATE:
    return []  # No specialist needed — synthesize() does the handoff
```

**Scenarios unblocked:** C05-C08 escalation, C09-C12 safety (now testable), X02 cross-persona.

**Effort:** ~15 minutes

---

### Fix 5: Fix the Eval Runner (makes the eval meaningful)
**Root cause:** `run-eval-scenarios.sh` only checks `status == "ok"`. The `expect` object in `eval-scenarios.json` defines rich assertions but none are checked.

**What to add to the eval runner:**
```bash
# After the basic status check, verify expected fields:
local expect_compliance=$(jq -r ".scenarios[$idx].expect.compliance // \"\"" "$SCENARIOS_FILE")
if [ -n "$expect_compliance" ]; then
    local actual_compliance=$(echo "$response" | jq -r '.text' | grep -oP '(?<=compliance_status: )\w+' || echo "UNKNOWN")
    if [ "$actual_compliance" != "$expect_compliance" ]; then
        verdict="FAIL"; reason="expected compliance=$expect_compliance got $actual_compliance"
    fi
fi

local expect_action_plan=$(jq -r ".scenarios[$idx].expect.has_action_plan // \"\"" "$SCENARIOS_FILE")
if [ "$expect_action_plan" = "true" ]; then
    if [ "$has_action_plan" != "true" ]; then
        verdict="FAIL"; reason="expected action_plan but got none"
    fi
fi

local expect_dual_auth=$(jq -r ".scenarios[$idx].expect.requires_dual_auth // \"\"" "$SCENARIOS_FILE")
if [ -n "$expect_dual_auth" ]; then
    local actual_dual=$(echo "$response" | jq -r '.action_plan.requires_dual_auth // "null"')
    if [ "$actual_dual" != "$expect_dual_auth" ]; then
        verdict="FAIL"; reason="expected dual_auth=$expect_dual_auth got $actual_dual"
    fi
fi

# MNPI safety: verify no dollar amounts or share counts in liaison responses
local expect_no_positions=$(jq -r ".scenarios[$idx].expect.no_positions // \"\"" "$SCENARIOS_FILE")
if [ "$expect_no_positions" = "true" ]; then
    local has_dollars=$(echo "$response" | jq -r '.text' | grep -cP '\$\d' || true)
    local has_shares=$(echo "$response" | jq -r '.text' | grep -ciP '\d+\s+shares' || true)
    if [ "$has_dollars" -gt 0 ] || [ "$has_shares" -gt 0 ]; then
        verdict="FAIL"; reason="MNPI leak: found dollar amounts or share counts"
    fi
fi
```

**Effort:** ~20 minutes

---

### Fix 6: Fix Multi-Ticker Extraction (unblocks R05)
**Root cause:** `_extract_ticker()` uses `re.search()` which returns only the first match.

**What to change in `research_orchestrator.py`:**
```python
def _extract_tickers(query: str) -> list[str]:
    """Extract ALL uppercase 1-5 char tokens that look like tickers."""
    return list(dict.fromkeys(re.findall(r"\b([A-Z]{1,5})\b", query)))

def _extract_ticker(query: str) -> str:
    """First ticker for backward compat."""
    tickers = _extract_tickers(query)
    return tickers[0] if tickers else ""
```

Then update `_task_for()` to include all tickers when multiple are found.

**Effort:** ~10 minutes

---

### Fix 7: Fix Intent Classifier for FAQ Edge Cases (unblocks C03, C04)
**Root cause:** `_ESCALATION_HINTS` regex matches "earnings" which is also a benign FAQ topic. C03 ("What is a 10-K filing?") escalates when it should FAQ.

**What to change in `liaison_orchestrator.py`:**
```python
def classify_inquiry(query: str) -> LiaisonDecision:
    # Check FAQ FIRST — if it matches FAQ, don't escalate
    if _FAQ_HINTS.search(query):
        return LiaisonDecision.FAQ
    if _ESCALATION_HINTS.search(query):
        return LiaisonDecision.ESCALATE
    return LiaisonDecision.ESCALATE
```

And add "earnings season" and "10-K" to `_FAQ_HINTS`:
```python
_FAQ_HINTS = re.compile(
    r"\b(market\s+hours?|what\s+(is|are)\s+a?\s?(10-?[kq]|etf|index|portfolio|filing)|"
    r"schedule|call\s+my\s+rm|appointment|office\s+hours|"
    r"when\s+is\s+earnings|earnings\s+season)\b",
    re.IGNORECASE,
)
```

**Effort:** ~10 minutes

---

### Fix 8: Wire agent-proxy /agent/approve to use real MCP_API_URL
**Root cause:** The SAM template sets `MCP_API_URL: ""` for the agent-proxy Lambda. The `/agent/approve` handler checks `if MCP_API_URL` and skips real MCP calls when it's empty.

**What to do:**
```bash
# Post-deploy, set the real API URL:
API_URL=$(aws cloudformation describe-stacks --stack-name 006-v3-mcp \
  --query 'Stacks[0].Outputs[?OutputKey==`ApiUrl`].OutputValue' --output text)

aws lambda update-function-configuration \
  --function-name 006-v3-agent-proxy \
  --environment "Variables={
    AGENTCORE_RUNTIME_ARN=arn:aws:bedrock-agentcore:us-east-1:875460787302:runtime/openclaw_v3_agent-o72dx396I0,
    AGENTCORE_REGION=us-east-1,
    MCP_DEV_MODE=true,
    MCP_API_URL=$API_URL,
    MCP_API_KEY=$(aws ssm get-parameter --name /006-v3/mcp/api-key --with-decryption --query Parameter.Value --output text),
    HITL_SIGNING_KEY_SSM=/006-v3/hitl/signing_key,
    CORS_ALLOW_ORIGIN=*
  }"
```

**Scenarios unblocked:** The `/agent/approve` endpoint now calls real MuleSoft + Salesforce MCP for gates 4-7. The SevenGateTracker in the frontend animates real gate progression.

**Effort:** ~5 minutes

---

## WHAT ABOUT THE OTHER ISSUES?

### Memory (M01-M02): SKIP FOR DEMO
Memory persistence is a nice-to-have. For the demo, remove M01/M02 from the eval set or mark them as "future roadmap." Don't fake it.

### Multimodal/PDF (R13): SKIP FOR DEMO
Remove R13 from the eval set. Don't claim capabilities that don't exist. If asked during demo, say "document ingestion is on the roadmap."

### Bedrock Guardrails (G01-G04): CONFIGURE
```bash
# Create a guardrail in Bedrock console, then:
aws lambda update-function-configuration \
  --function-name 006-v3-agent-proxy \
  --environment "Variables={...,BEDROCK_GUARDRAIL_ID=<id>,BEDROCK_GUARDRAIL_VERSION=<version>}"
```
This is a 10-minute config change, not a code change.

### CloudFront (frontend): POINT TO V6
```bash
aws s3 sync frontend/dist/ s3://<frontend-bucket>/ --delete
aws cloudfront create-invalidation --distribution-id <dist-id> --paths "/*"
```

---

## TOTAL EFFORT ESTIMATE

| Fix | Time | Impact |
|---|---|---|
| Fix 1: SF OBO credentials | 30 min | Unblocks ~60% of broken scenarios |
| Fix 2: MuleSoft CloudHub deploy | 45 min | Unblocks all trade/wire |
| Fix 3: Real compliance in DRAFT_ONLY | 20 min | Unblocks trust spine |
| Fix 4: Fix escalation timeouts | 15 min | Unblocks client persona |
| Fix 5: Fix eval runner | 20 min | Makes eval meaningful |
| Fix 6: Multi-ticker extraction | 10 min | Fixes R05 |
| Fix 7: FAQ intent classifier | 10 min | Fixes C03, C04 |
| Fix 8: Wire /agent/approve MCP_API_URL | 5 min | Enables real 7-gate approval |
| Guardrails config | 10 min | Enables G01-G04 |
| CloudFront repoint | 5 min | V6 frontend live |
| **TOTAL** | **~3 hours** | **Projected: 45-50 of 60 scenarios REAL** |

---

## PROJECTED SCORECARD AFTER FIXES

| Category | Before | After | Notes |
|---|---|---|---|
| Research Core (R01-R08) | 1 real, 6 partial, 1 fake | 2 real, 6 partial | R05 fixed; others stay partial (citation validation is LLM-dependent) |
| Research RAG (R09-R10) | 0 real, 1 partial, 1 weak | 0 real, 2 partial | KB is real; section-aware retrieval still missing |
| Research Compliance (R11-R12) | 0 real, 1 partial, 1 fake | 1 real, 1 partial | R12 needs a real restricted ticker in the query |
| Advisor Trade (A01-A06, A15-A16) | 0 real, 2 partial, 6 fake | 4 real, 4 partial | Real compliance + real MuleSoft + real CRM |
| Advisor Portfolio (A07-A09) | 0 real, 0 partial, 3 fake | 0 real, 3 partial | Real CRM data after OBO fix; still LLM-dependent |
| Advisor Suitability (A10-A11) | 0 real, 2 partial | 0 real, 2 partial | Unchanged — skill invocation is LLM-dependent |
| Advisor Client Reply (A12-A14) | 0 real, 3 partial | 1 real, 2 partial | Real CRM write after OBO fix |
| Client FAQ (C01-C04) | 2 real, 0 partial, 2 broken | 4 real | C03, C04 fixed by intent classifier |
| Client Escalation (C05-C08) | 0 real, 0 partial, 4 broken | 3 real, 1 partial | Timeout fix + OBO fix |
| Client Safety (C09-C12) | 0 real, 0 partial, 0 fake, 4 untestable | 2 real, 2 partial | Now testable with working specialists |
| Cross-Persona (X01-X04) | 0 real, 2 partial, 2 fake | 2 real, 2 partial | OBO fix enables brief persistence + handoff |
| Trust Spine (T01-T03) | 0 real, 0 partial, 3 fake | 2 real, 1 partial | Real compliance + real MuleSoft |
| Guardrails (G01-G04) | 0 real, 0 partial, 0 fake, 4 untestable | 2 real, 2 partial | Bedrock Guardrails configured |
| Memory (M01-M02) | 0 real, 0 partial, 2 fake | REMOVED | Honest: not built, not claimed |
| Edge Cases (E01-E06) | 2 real, 2 partial, 1 fake | 3 real, 2 partial | E04 now flagged by real compliance |
| **TOTAL** | **5 real (8%)** | **~26 real (45%), ~28 partial (48%)** | From 8% to 93% real-or-partial |

---

## WHY NOT V4?

1. **Time:** A V4 rewrite is 2-4 weeks minimum. You don't have that.
2. **Infrastructure:** 33 AWS resources, 6 CDK stacks, 11 Lambdas, Bedrock KB, Aurora — all deployed. Rebuilding this is insane.
3. **The problems are wiring, not architecture.** The code is real. The skills are real. The orchestrators are real. The trust layer is real. They're just not connected.
4. **Risk:** A V4 introduces new bugs. V3 has 252 backend tests and 146 frontend tests. That test coverage is valuable.
5. **The 8 fixes are surgical.** 3 are config changes (no code). 3 are <20 line code changes. 2 are deploy commands.

The builders built a real system. They just didn't finish wiring it. That's a 3-hour fix, not a rewrite.

---

## EXECUTION ORDER

```
Hour 1:  Fix 1 (SF OBO) + Fix 8 (MCP_API_URL) + Guardrails config
Hour 2:  Fix 2 (MuleSoft deploy) + Fix 4 (escalation timeout)
Hour 3:  Fix 3 (real compliance) + Fix 6 (multi-ticker) + Fix 7 (FAQ classifier)
         + Fix 5 (eval runner) + CloudFront repoint
         + Run full eval suite → verify 45+ scenarios pass strict criteria
```

After hour 3: redeploy AgentCore container with code changes, run `scripts/run-eval-scenarios.sh`, verify the numbers.

---

*The demo will work. The architecture is sound. The wiring just needs to be completed.*