# 006 v2: How MuleSoft Stitches to OpenClaw

> Date: April 2026
> Audience: architects, engineers, auditors
> Purpose: plain-English + diagram + file-by-file map of how a user message becomes a MuleSoft action

---

## TL;DR

- OpenClaw sees a trade/wire/KYC intent in the user's message
- The mulesoft-api skill (`openclaw/skills/mulesoft-api/actions.py`) is the single choke point for EVERYTHING that changes enterprise state
- The skill sequences: compliance pre-check, HITL approval, optional dual-auth, MCP call, audit write
- The mulesoft-actions MCP server (Lambda: `aws/mcp-servers/mulesoft-actions/app.py`) is the HTTP endpoint that actually calls MuleSoft, with a `MULESOFT_MODE` switch (mock / sandbox / production)
- Nothing else in 006 — not the pipeline, not the LLM prompt, not the frontend — can bypass the skill

---

## The stitch diagram

```
+------------------------------------------------------------------+
| 1. USER (on Slack / web UI)                                      |
|    "Trim Client Henderson's NVDA position by 30%"                |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
| 2. OPENCLAW AGENT (on AgentCore)                                 |
|    Claude Sonnet 4.6 reads the message, decides:                 |
|    "This is an L5 trade action, I need the mulesoft-api skill"   |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
| 3. mulesoft-api SKILL  (openclaw/skills/mulesoft-api/actions.py) |
|    The single choke point (v2 steering rule 1)                   |
|                                                                  |
|    Step A: gather context                                        |
|      -> salesforce-crm skill: get Henderson's NVDA position      |
|      -> market-data MCP: current NVDA price                      |
|                                                                  |
|    Step B: compliance pre-check                                  |
|      -> compliance-screening skill                               |
|      -> returns ALLOW / DENY / ESCALATE                          |
|      -> if DENY: write audit, stop, NO MuleSoft call             |
|                                                                  |
|    Step C: build ActionPlan                                      |
|      -> {ticker: NVDA, side: SELL, qty: 540, client: Henderson}  |
|      -> compute plan_hash = sha256(ActionPlan)                   |
|                                                                  |
|    Step D: present HITL plan (hitl.py)                           |
|      -> OpenClaw WebSocket emits stream="hitl" event             |
|      -> user sees plan in HitlPanel component                    |
|      -> user clicks [Approve]                                    |
|      -> hitl.py returns ApprovalToken (HMAC, 5min TTL)           |
|                                                                  |
|    Step E: dual auth check (dual_auth.py)                        |
|      -> notional = 540 * $135 = $72,900                          |
|      -> under $500K trade threshold -> no dual approval needed   |
|      -> SKIP to Step F                                           |
|      (if over: request_second_approval blocks until senior signs)|
|                                                                  |
|    Step F: call MCP tool with approval_token in args             |
|      -> POST /mulesoft-actions/tools/call                        |
|         name=submit_order,                                       |
|         arguments={ticker, side, quantity, approval_token, ...}  |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
| 4. mulesoft-actions MCP SERVER (Lambda)                          |
|    Checks MULESOFT_MODE env var:                                 |
|    - mock       -> returns canned response with order_id, ref    |
|    - sandbox    -> real MuleSoft API call                        |
|        mulesoft_client.py: bearer token from Secrets Manager     |
|        POST https://anypoint.mulesoft.com/api/process/orders     |
|        MuleSoft process API maps canonical -> broker-specific    |
|        process API fans out to actual OMS (Alpaca, Schwab, ...)  |
|        returns {order_id, mulesoft_reference, status}            |
|    - production -> same as sandbox, just a different base URL    |
|                                                                  |
|    Returns structuredContent with order details to the skill     |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
| 5. BACK IN mulesoft-api SKILL                                    |
|                                                                  |
|    Step G: audit write (audit-logging skill)                     |
|      -> IR_Audit_Log__c record:                                  |
|         Action__c = TRADE_SUBMITTED                              |
|         Decision_Rationale__c = compliance notes + plan summary  |
|         Approved_By__c = user SF ID                              |
|         MuleSoft_Reference__c = MS-REF-abc123                    |
|         Trace_Id__c = Langfuse trace id                          |
|                                                                  |
|    Step H: return ActionResult to OpenClaw agent                 |
+------------------------------------------------------------------+
                            |
                            v
+------------------------------------------------------------------+
| 6. OPENCLAW AGENT responds to user                               |
|    "Order submitted. Sell 540 NVDA at market. ID MOCK-ORDER-A3.  |
|     I will notify you when it fills."                            |
+------------------------------------------------------------------+
```

---

## File-by-file map of the stitch

| Step | File | What it does |
|---|---|---|
| 2 | `agentcore/openclaw.json` | Registers the mulesoft-api skill with the agent, exposes trigger keywords (trade, buy, sell, wire, rebalance, KYC, open account) |
| 3 | `openclaw/skills/mulesoft-api/SKILL.md` | Skill manifest — Claude reads this to decide when to invoke |
| 3 | `openclaw/skills/mulesoft-api/actions.py` | The choke point. Public functions: submit_order, initiate_wire, rebalance_portfolio, run_kyc_screening, open_account, get_order_status, get_settlement_status |
| 3B | `openclaw/skills/compliance-screening/screening.py` | check_restricted_list, check_trading_window, check_concentration, check_mnpi_flags — all called by actions.py in Step B |
| 3D | `openclaw/skills/mulesoft-api/hitl.py` | request_approval(plan_summary, plan_hash) — emits WebSocket event, blocks until user responds, returns signed ApprovalToken |
| 3E | `openclaw/skills/mulesoft-api/dual_auth.py` | threshold_requires_dual_auth(), request_second_approval() — SF permission set check, second approver routing |
| 3F | `aws/mcp-servers/mulesoft-actions/app.py` | Lambda handler — MCP protocol (GET /, POST /tools/list, POST /tools/call) |
| 4 | `aws/mcp-servers/mulesoft-actions/mulesoft_client.py` | OAuth token fetch + cache, authenticated HTTPS requests to Anypoint |
| 4 | `mulesoft/process-apis/*.raml` | MuleSoft process API specs — map canonical 006 schemas to broker-specific formats |
| 4 | `mulesoft/policies/*.json` | API Manager policies — rate limit, client-id enforcement, JSON threat protection |
| 5G | `openclaw/skills/audit-logging/logger.py` | write_audit_log() — inserts IR_Audit_Log__c record |
| 5G | `force-app/.../objects/IR_Audit_Log__c` | SObject with Action__c picklist including TRADE_SUBMITTED, WIRE_INITIATED, etc. |
| 5G | `force-app/.../objects/IR_Pending_Approval__c` | Dual-auth waiting queue |
| 6 | `frontend/src/components/HitlPanel.tsx` | React component that renders the ActionPlan and [Approve][Reject][Edit] buttons |

---

## The three integrity properties

### 1. The skill is the only door

Nothing else can call the mulesoft-actions MCP server. Enforcement:

- `openclaw.json` does NOT expose the mulesoft-actions tools directly to the agent. Only the skill is exposed.
- The AutoResearchClaw pipeline has no reference to mulesoft-actions (v2 steering rule on 005/v1 mistakes).
- The frontend has no direct MuleSoft API calls; all writes go through the agent.
- The MCP server itself requires a valid approval_token in every write-action request. No token = no call.

### 2. The approval token is plan-bound

When the user approves, the returned token contains plan_hash = sha256(canonical_json(ActionPlan)). The MCP server verifies the token's plan_hash matches the current action's hash. If the skill or agent tries to change any field (ticker, quantity, account) between approval and submission, the hash diverges and the token becomes invalid.

This defends against: a compromised agent that gets approval for a small trade then tries to submit a big one.

### 3. Audit is immutable AND happens regardless of outcome

Every branch writes to IR_Audit_Log__c:

- Compliance DENY -> Action__c = COMPLIANCE_BLOCKED
- HITL REJECT -> Action__c = TRADE_REJECTED
- HITL TIMEOUT -> Action__c = TRADE_TIMEOUT
- Dual-auth missing -> stays in IR_Pending_Approval__c with SLA tracker
- MuleSoft 4xx -> Action__c = TRADE_FAILED_VALIDATION
- MuleSoft 5xx -> Action__c = TRADE_FAILED_UPSTREAM
- Success -> Action__c = TRADE_SUBMITTED

Auditors can reconstruct: WHO asked for WHAT, WHEN it was approved, by WHOM, with which COMPLIANCE rationale, against which VENDOR reference.

---

## MULESOFT_MODE switch

| Mode | Target | Used for | Safety |
|---|---|---|---|
| mock | None | L5 eval in CI/CD, local dev without vendor access | Zero side effects, canned order_ids |
| sandbox | Anypoint anypoint.mulesoft.com | Integration tests with first vendor onboarded (Alpaca paper, Dwolla sandbox, Plaid sandbox) | Real MuleSoft auth, but process APIs route to vendor sandboxes only |
| production | Anypoint production env | Live customer demos and real trades | Real MuleSoft + real vendor prod APIs. Gated behind deploy-all.sh prompt |

The flip is a single CloudFormation parameter: `MuleSoftMode=mock|sandbox|production`. Agent code does NOT change.

---

## End-to-end call sequence (text form)

```
User        Agent       Skill      Compl.  MCP      MuleSoft    Audit
 |           |           |           |       |         |          |
 |--message->|           |           |       |         |          |
 |           |--plan---->|           |       |         |          |
 |           |           |-check---->|       |         |          |
 |           |           |<--ALLOW---|       |         |          |
 |           |           |--hash--.  |       |         |          |
 |           |<---hitl---|           |       |         |          |
 |<---plan---|           |           |       |         |          |
 |--Approve->|           |           |       |         |          |
 |           |-approved->|           |       |         |          |
 |           |           |--token--->|       |         |          |
 |           |           |-POST tool/call---->         |          |
 |           |           |           |       |-POST--->|          |
 |           |           |           |       |<-resp---|          |
 |           |           |<----resp--|       |         |          |
 |           |           |--write-------------------------------->|
 |           |<--result--|           |       |         |          |
 |<---done---|           |           |       |         |          |
```

---

## What the user sees (concrete example)

User (Slack): `Trim Client Henderson's NVIDIA position by 30%`

Agent (streaming, on Slack):

```
Looking at Client Henderson's NVDA position...
Current holding: 1,800 shares @ avg cost $82.15
Current price: $135.00
30% trim = 540 shares @ market

Compliance check:
  Restricted list: PASS
  Trading window: PASS (open)
  Concentration: PASS (post-trade 18.4%)
  MNPI: PASS

Proposed order:
+------------------------------------+
| Client:    Henderson               |
| Action:    SELL NVDA               |
| Quantity:  540 shares              |
| Type:      Market order            |
| Est. proceeds: $72,900             |
| Commission:    $0                  |
+------------------------------------+

[Approve]  [Reject]  [Edit]
```

User clicks [Approve]

Agent:

```
Order submitted to OMS.
  Order ID:    MOCK-ORDER-A3F2B1C9
  Reference:   MS-REF-9dfe8c2a4b7e1f03
  Audit log:   IR-AL-20260415-00037

I will notify you when it fills.
```

Meanwhile in Salesforce:

```
IR_Audit_Log__c record IR-AL-20260415-00037:
  Action__c:              TRADE_SUBMITTED
  Agent__c:               mulesoft-api
  Query__c:               Trim Client Henderson's NVIDIA position by 30%
  Analyst__c:             <user id>
  Timestamp__c:           2026-04-15 14:32:11 UTC
  Data_Sources_Used__c:   SF (Henderson holdings), Market Data (NVDA quote)
  Decision_Rationale__c:  Compliance ALLOW; HITL approved; notional $72,900
                          below $500K dual-auth threshold
  Approved_By__c:         <user id>
  Dual_Approver__c:       null (not required)
  MuleSoft_Reference__c:  MS-REF-9dfe8c2a4b7e1f03
  Trace_Id__c:            <Langfuse trace id>
```

---

## What happens in mock mode vs sandbox vs production

### Mock mode (default)

- Step F POST /mulesoft-actions/tools/call hits Lambda
- Lambda sees MULESOFT_MODE=mock, returns canned {order_id: MOCK-ORDER-..., mulesoft_reference: MS-REF-..., status: SUBMITTED, mode: mock}
- All other steps (compliance, HITL, audit) still run for real
- L5 eval uses this

### Sandbox mode (after vendor onboarded)

- Step F hits Lambda
- Lambda sees MULESOFT_MODE=sandbox, calls mulesoft_client.request(POST, /api/process/orders, args)
- mulesoft_client reads creds from Secrets Manager /006-v2/mulesoft/credentials
- Fetches OAuth token from anypoint.mulesoft.com/accounts/api/v2/oauth2/token
- POSTs to the deployed process API
- Process API (deployed as a Mule app in Anypoint) maps submit_order canonical -> Alpaca paper trading API shape
- Alpaca responds, Mule responds, Lambda responds, skill responds, agent responds to user

### Production mode

- Same code path as sandbox
- Different CloudFormation parameter (MuleSoftMode=production) and different Secrets Manager value pointing at Anypoint production env
- Process API routes to real OMS (Alpaca real account, or Schwab, or Charles River)
- Dual-auth threshold strictly enforced
- deploy-all.sh has a confirmation prompt before flipping any stack to production mode

---

## Why this design survives the 005/v1 mistakes list

From v2 steering:

| v1 mistake | How this design avoids it |
|---|---|
| Skip HITL with a config flag | No config flag exists. actions.py hardcoded to call hitl.request_approval before every write |
| LLM synthesizes args directly | ActionPlan is structured, shown to user verbatim, plan_hash is bound |
| Pipeline calls MuleSoft | Pipeline has no access to the mulesoft-api skill. Skill is agent-level only |
| Log approval tokens | hitl.py logs plan_hash + approver_id + timestamp. Tokens never cross the Langfuse boundary |
| Mix mock and sandbox | MULESOFT_MODE is per-deployment. Eval runs one mode at a time |
| Hardcoded creds | Secrets Manager only. IAM policy scoped to /006-v2/mulesoft/* |
| Bypass agent with direct API calls | Frontend has no mulesoft-actions endpoint in its API client |

---

## Current state (April 2026)

| Component | Status |
|---|---|
| mulesoft-actions MCP server (mock mode) | Working locally |
| mulesoft-actions MCP server (sandbox mode auth) | Working against real Anypoint |
| mulesoft_client.py OAuth + Secrets Manager | Tested |
| SAM template (Lambda + IAM + API Gateway routes) | Written |
| actions.py skill (HITL + compliance sequence) | Scaffolded, implementations next |
| hitl.py (WebSocket event + HMAC tokens) | Scaffolded |
| dual_auth.py (second approver routing) | Scaffolded |
| Frontend HitlPanel | Pending |
| L5 eval ground truth (queries 121-140) | Pending |
| scripts/test-mulesoft-mock.py | Pending |
| Process APIs (RAML + DataWeave) | Pending (requires vendor choice) |
| IR_Audit_Log__c Action__c picklist extension | Pending |

---

See also:

- docs/v2-phase-6-build-plan.md — task-level breakdown
- docs/v2-mulesoft-onboarding-steps.md — Anypoint Connected App setup
- docs/design-doc.md (v1 base) — the 006 architecture this extends
- .kiro/steering/006-v2-mulesoft.md — the non-negotiable rules
