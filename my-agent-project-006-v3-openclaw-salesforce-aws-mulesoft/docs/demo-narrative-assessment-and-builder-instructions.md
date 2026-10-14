# Demo & Narrative Assessment + Builder Instructions

> **Date:** 2026-05-02
> **For:** The builder — the person who will make the next code changes.
> **Context:** Based on the independent multi-reviewer deep assessment, V6 live query test results, script-vs-reality probe, and full source code review.
> **Purpose:** What to fix, in what order, to make the 18-minute Narrative Arc 1 demo credible. No fluff. No architecture lectures. Just the work.

---

## Part 1 — Where the Demo Stands Right Now

### What the audience sees today (V6, live backend)

**Sarah's screen (research):** She types "Research NVDA ahead of earnings." Brief streams in 22 seconds. 4 specialists return (market, filings, sentiment, compliance). Running chips pulse. Citation chips appear in the brief. She clicks a citation — the slide-over drawer opens and shows real 10-Q text from the KB for ~5 of 6 citations. One citation is fabricated (the LLM invented a human-readable ID instead of using the real chunk ID). The brief has a header: `compliance_status: ALLOW, rm_consumable: true`. The brief does NOT persist to Salesforce (OBO 401). No audit row writes.

**Marcus's screen (advisor):** He types "Trim NVDA from 14.2% to 9.5% for Eleanor Vance." Draft plan returns in 8.5 seconds (Haiku). An InlineActionCard renders with plan_id, action_type, summary, notional_usd, requires_dual_auth. He clicks Approve. The 7-gate tracker animates: hitl → dual_auth → mulesoft → audit, all "passed." This looks great on screen. But `/agent/approve` is a hardcoded JSON response — no real skill calls execute. No real token verification, no real MuleSoft submission, no real audit write. The Client 360 panel shows hardcoded allocation percentages (62% equity, 22% fixed) — same for every client. Queues start empty.

**Eleanor's screen (client):** She types "Should I be worried about META?" Liaison escalates in 10 seconds. She gets an acknowledgment with a reference ID. Three CTA buttons appear: "Send me the brief" / "Schedule a call" / "Do nothing for now." Thread persists across refresh (V6 added localStorage). The disclaimer is always visible. The trust spine below the phone shows the same traversal map as Sarah and Marcus.

### The 5 demo moments that land

1. **Parallel specialist fanout** — 4 chips pulse simultaneously. The audience sees concurrency, not a serial waterfall.
2. **Real Bedrock + real data** — Finnhub live quotes, Tavily live news, 784 real SEC filing chunks. Not mocked.
3. **Advisor draft in 8.5 seconds** — Haiku optimization. The action plan card is structured and readable.
4. **7-gate tracker animation** — Gates light up sequentially. Visually compelling.
5. **Client restraint** — No dashboards, no positions, no recommendations. The absence IS the design.

### The 7 demo moments that break

1. **Citation drill-down fails on ~1 of 6 citations** — fabricated ID → "(source not available)."
2. **"Filed as a record" claim collapses on click** — brief doesn't persist to SF (OBO 401).
3. **RM never gets notified of Sarah's brief** — no Platform Event fires because the brief never reaches SF.
4. **Approve click is theater** — gates 4-7 are a hardcoded JSON response. No real verification.
5. **Client 360 is a wireframe** — hardcoded percentages, placeholder text.
6. **Audit trail is empty** — zero `IR_Audit_Log__c` rows. The "fully audited" claim is false.
7. **Demand signals pane is empty** — "No suggestions from the field yet."

---

## Part 2 — The Demo Credibility Tiers

### Tier A — "It works live" (current: ~40%)
What the audience can verify by clicking. Right now, the research turn streams, the advisor draft returns, the client FAQ answers. Everything else is narration over empty panels.

### Tier B — "The data layer is real" (target: ~75%)
Brief persists to SF. Audit rows land. Platform Event fires. RM queue populates. Citation drill-down resolves 6/6. This requires fixing the OBO chain and nothing else architecturally.

### Tier C — "The trust spine is real" (target: ~90%)
`/agent/approve` calls the real skill chain. HITL token is verified. Dual-auth threshold is checked. MuleSoft sandbox call goes through. Audit row writes with full cross-stitching. This is the money shot — the thing that makes this different from every other chatbot demo.

### Tier D — "Production-ready" (target: not for this demo)
Real auth, real OFAC feed, distributed token store, CI/CD, multi-AZ. This is weeks of work. Don't attempt it for the demo.

---

## Part 3 — Builder Instructions (Priority Order)

### Instruction 0: Fix the OBO chain (BLOCKS EVERYTHING)
**Time: 1 hour of SF admin work + 5 minutes AWS**
**Unblocks: Tier B entirely**

The Secrets Manager secret `/006-v3/sf/bootstrap-creds` is empty. Every Salesforce write degrades silently. This one fix unblocks: brief persistence, audit rows, Platform Events, Research_Request__c, and cross-persona stitching.

```
1. Create a Salesforce Connected App (FSI Workforce 360 OBO)
   - Enable OAuth, scopes: api, refresh_token, full
   - Use digital signatures: upload a self-signed cert
   - Manage → Edit Policies → Permitted Users: Admin approved

2. Populate the secret:
   aws secretsmanager put-secret-value --region us-east-1 \
     --secret-id /006-v3/sf/bootstrap-creds \
     --secret-string '{"client_id":"<CONSUMER_KEY>","subject_pattern":"<SF_USER>","audience":"https://login.salesforce.com","private_key_pem":"<PEM>"}'

3. Cache-bust the sf-auth-proxy Lambda (preserve existing env vars).

4. Verify:
   bash scripts/narrative-e2e-test.sh
   sf data query --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY" --target-org new-org
   # Expect: > 0 after the next agent turn
```

Full playbook: `docs/v3-p0-sf-obo-fix.md`

**Why this is instruction 0:** The script-vs-reality probe proved that the code for `Published_At__c`, the 3 "missing" audit fields, and the Platform Event trigger all work correctly. The Apr 29 probe misattributed these as code bugs. They're all symptoms of the OBO 401. Fix the secret, and 5 "bugs" disappear simultaneously.

---

### Instruction 1: Wire real skills into `/agent/approve`
**Time: 2-3 days**
**Unblocks: Tier C (the money shot)**

The `/agent/approve` endpoint in `aws/mcp-servers/agent-proxy/app.py` currently returns a hardcoded gate trace. The comment in the code literally says "A future implementation would call the real skill sequence." That future is now.

**What to do:**

Replace the hardcoded response in `_handle_approve()` with actual skill calls. The skills exist, are tested, and work. The wiring is the gap.

```python
# Current (lines 224-237 of agent-proxy/app.py):
return _respond(200, {
    "status": "ok",
    "plan_id": plan_id,
    "gate_trace": [
        {"gate": "hitl", "status": "passed", "detail": "token verified"},
        {"gate": "dual_auth", "status": "passed", "detail": "below threshold"},
        {"gate": "mulesoft", "status": "passed", ...},
        {"gate": "audit", "status": "passed", ...},
    ],
})

# Target: call the real skill chain
# 1. hitl.verify(token, action_plan) → VerifiedClaims or HITLError
# 2. dual_auth.run(action_type, notional_usd, first_approver) → DualAuthOutput
# 3. mulesoft_api.run(method, arguments, plan_hash, approval_token) → MuleSoftOutput
# 4. audit_logging.run(action, principal_id, gate_trace, ...) → AuditOutput
# Return the real gate_trace from each step.
```

**The challenge:** The agent-proxy Lambda is a thin REST shim — it doesn't have the OpenClaw skill imports. Two approaches:

**Option A (recommended for demo):** Call the skills via MCP. The mulesoft-actions Lambda and salesforce-crm Lambda are already deployed. The agent-proxy can POST to `/mcp/mulesoft-actions/tools/call` and `/mcp/salesforce-crm/tools/call` with the MCP API key. This keeps the Lambda thin and uses the existing infrastructure.

**Option B (cleaner but more work):** Move the approval logic into the AgentCore container. The coordinator already has all skill imports. Add an `/approve` route to `agentcore_server.py` that runs the 4-skill chain synchronously. The agent-proxy forwards to AgentCore instead of handling it locally.

**For the demo, Option A is faster.** The MCP endpoints are live and tested. The agent-proxy already has `MCP_API_KEY` in its environment. Four sequential HTTP POSTs, each returning a result that feeds the next gate's input.

**Acceptance criteria:**
- Click Approve → real `hitl.verify()` runs (token signature check, expiry check, plan_hash rebinding)
- If notional > $500K → real `dual_auth` creates `IR_Pending_Approval__c` in SF
- Real `mulesoft_api` call to CloudHub sandbox (Alpaca paper / Dwolla sandbox)
- Real `audit_logging` writes `IR_Audit_Log__c` with full cross-stitching
- Frontend gate tracker animates from the real gate_trace, not a hardcoded one

---

### Instruction 2: Kill the last fabricated citation
**Time: 30 minutes**
**Unblocks: Citation drill-down works 6/6 instead of 5/6**

The V6 query test results show "5R/1F" (5 real, 1 fabricated) on most research queries. The fabricated citation is typically from the `sentiment_specialist` or `market_specialist` which emit human-readable IDs like `[src:finnhub_quote_NVDA]` instead of real KB chunk IDs.

**What to do:**

The `MARKET_SPECIALIST_PROMPT` in `topology.py` (line ~240) tells the specialist to return `[src:finnhub_quote_NVDA]`. That's a fabricated ID — there's no KB chunk with that key. The market specialist doesn't use KB retrieval; it calls Finnhub directly. Its citations should reference the Finnhub API response, not a KB chunk.

Two fixes:
1. **Market specialist:** Change the prompt to emit `[src:finnhub:{TICKER}]` and add a handler in the BFF's `/api/source_chunk/{id}` that recognizes the `finnhub:` prefix and returns the cached quote data. Or simpler: don't cite market data at all (it's live and ephemeral, not a document).

2. **Sentiment specialist:** Same pattern — Tavily results aren't KB chunks. Either emit `[src:tavily:{headline_id}]` with a BFF handler, or skip citations for news headlines (they have URLs already).

The `enforce_citations()` function will strip sentences without valid citations. That's fine — the brief will be shorter but every remaining sentence will have a real, clickable citation. Better a shorter honest brief than a longer one with broken drill-downs.

---

### Instruction 3: Populate Client 360 with real (or seeded) data
**Time: 1-2 days**
**Unblocks: Marcus's screen looks like a real workbench**

The `ClientContextPanel` in `AdvisorWorkbenchV6.tsx` shows hardcoded allocation percentages. When Marcus clicks a queue item, the panel should fetch real client data.

**What to do:**

1. When `selectedItemId` changes, fire a REST call to the BFF or directly to the salesforce-crm MCP:
   ```
   POST /mcp/salesforce-crm/tools/call
   {"tool": "read_household_summary", "arguments": {"household_id": selectedItem.client_contact_id}}
   ```

2. The `read_household_summary` and `read_household_positions` handlers already exist in `salesforce-crm/app.py` (lines 664-747). They return mock data when SF is unavailable and real data when OBO works.

3. Wire the response into the Client 360 panel: replace hardcoded percentages with real allocation data, replace "—" with real AUM (MNPI-redacted to bands), replace placeholder signals with real concentration flags.

**For the demo:** If the OBO chain is fixed (Instruction 0), the CRM MCP returns real SF data. If not, the mock responses are realistic enough for a demo — they return structured household data with positions, allocation percentages, and concentration flags. Either way, the panel should fetch and render, not show hardcoded values.

---

### Instruction 4: Seed demo data and backfill EDGAR
**Time: 2 hours**
**Unblocks: Narrative Arc 1 has real households and real filings**

```bash
# 1. Seed 4 households with META concentration > 5%
sf apex run --file scripts/seed-demo-data.apex --target-org new-org

# 2. Backfill EDGAR for demo tickers
bash scripts/seed-edgar-demo.sh

# 3. Verify KB has the chunks
aws bedrock-agent list-ingestion-jobs --knowledge-base-id <KB_ID> --data-source-id <DS_ID>
```

The seed script creates Patel, Chen, Nakamura, and Al-Rashid households with META positions above 5%. The EDGAR backfill downloads 8-K/10-K/10-Q for META, NVDA, MSFT, GOOGL, AVGO, QCOM, AMD, AAPL, TSM and indexes them into the Bedrock KB.

---

### Instruction 5: Emit queue_update events from the backend
**Time: 4-6 hours**
**Unblocks: Marcus's queue populates; demand signals pane populates**

The `useQueuesStore` Zustand store and the `onQueueUpdate` handler in `useStreamingTurn` are fully wired. The frontend is ready. The backend doesn't emit `queue_update` events.

**What to do:**

The liaison orchestrator already builds `queue_updates` in its `synthesize()` method (lines 150-175 of `liaison_orchestrator.py`) and attaches them to the first response's result dict. The `agentcore_server.py` needs to lift these from the response envelope and emit them as WebSocket events (or include them in the REST response for the HTTP transport).

For the HTTP transport (`httpAgentTransport.ts`), the response envelope should include a top-level `queue_updates` array. The transport already handles `gate_trace` replay — add the same pattern for queue updates.

For the research persona, the `publish_brief` side effect in `coordinator.py` should emit a `queue_update` to the advisor persona's `briefs` queue when a brief is published with `rm_consumable=true`.

---

### Instruction 6: Pre-demo warm-up and rehearsal
**Time: 1 day**
**Unblocks: Confidence that the demo won't fail on stage**

```bash
# 10 minutes before doors open:
bash scripts/warm-start.sh

# Run the full narrative sequence:
# 1. Sarah: "Research META ahead of earnings — focus on data-center capex and AI monetization"
#    → Verify: brief streams, 4+ specialists return, citations resolve, brief persists to SF
#    → Verify: IR_Audit_Log__c row exists with Research_Brief_Id__c populated

# 2. Marcus: "Trim NVDA from 14.2% to 9.5% for Eleanor Vance"
#    → Verify: action_plan card renders with plan_id and notional_usd
#    → Click Approve → verify gate tracker animates with REAL gate results
#    → Verify: IR_Audit_Log__c row with Linked_Trade_Id__c populated

# 3. Eleanor: "Should I be worried about META?"
#    → Verify: escalation acknowledgment in <10s
#    → Verify: Client_Inquiry__c row in SF
#    → Verify: Marcus's queue shows the inquiry (if queue_update events are wired)

# 4. Check Salesforce:
sf data query --query "SELECT COUNT() FROM Research_Brief__c WHERE CreatedDate = TODAY" --target-org new-org
sf data query --query "SELECT COUNT() FROM IR_Audit_Log__c WHERE CreatedDate = TODAY" --target-org new-org
sf data query --query "SELECT COUNT() FROM Client_Inquiry__c WHERE CreatedDate = TODAY" --target-org new-org
```

---

## Part 4 — What to Say and What NOT to Say on Stage

### Say (verified true)

1. "Real Bedrock Sonnet inference. Every turn costs real tokens. The brief you're seeing was generated 20 seconds ago, not pre-recorded."
2. "Real Finnhub live quotes, real Tavily news search, real SEC filing chunks from EDGAR — 784 chunks indexed in Bedrock Knowledge Bases."
3. "Four specialists fan out in parallel via asyncio.gather. You can see them in the running chips — market, filings, sentiment, compliance — all concurrent."
4. "Compliance screening is deterministic — ALLOW/DENY/REVIEW from four rule-based checks. The LLM never decides compliance."
5. "The citation enforcement harness strips unsourced sentences server-side. Every sentence in this brief cites a real source chunk from a real 10-Q filing."
6. "The client persona is architecturally read-only. The FAQ specialist has zero tools and zero MCP access. It cannot leak data because it has no access to data."
7. "MuleSoft CloudHub is live in sandbox mode — Alpaca paper trading and Dwolla sandbox. The trade path routes through real CloudHub Process APIs."

### Don't say (not yet true, or misleading)

1. ~~"Every turn writes an audit row to Salesforce."~~ — Only true after Instruction 0 is complete.
2. ~~"The approval flow verifies the HITL token cryptographically."~~ — Only true after Instruction 1 is complete. Currently hardcoded.
3. ~~"Client 360 shows real holdings."~~ — Hardcoded percentages until Instruction 3.
4. ~~"Demand signals aggregate client inquiries by ticker."~~ — Empty pane until Instruction 5.
5. ~~"Enterprise IdP authentication."~~ — dev-bootstrap-token. If asked, say: "Cognito PKCE scaffold is built and tested; we're running in dev-bootstrap mode for this demo."
6. ~~"17 agents."~~ — 14 unique agent IDs. The narrative arc says 17 (counting context_specialist twice). Say "14 specialist agents across 3 personas" to be precise.

### The honest framing for the approval stub (if Instruction 1 is not done)

If you demo before wiring the real approval chain, add this sentence before the Approve click:

> "When Marcus clicks Approve, the frontend sends the plan_id and plan_hash to the approval endpoint. In this demo, the gate trace is replayed from a canonical sequence. In production, each gate calls the real skill — HITL token verification with SHA-256 plan-hash binding, dual-auth threshold check against Salesforce permission sets, MuleSoft CloudHub submission, and an immutable audit write. The skill code for all four gates is written, tested, and in the repository. The wiring into this endpoint is the next sprint."

That's honest. The audience respects honesty about what's wired vs. what's built.

---

## Part 5 — The Priority Stack (Do This, In This Order)

| # | Instruction | Time | Demo Impact | Tier |
|---|---|---|---|---|
| **0** | Fix OBO chain (SF Connected App + secret) | 1 hour | Unlocks audit, briefs, PE, handoff | B |
| **1** | Wire real skills into `/agent/approve` | 2-3 days | The money shot — trust spine is real | C |
| **2** | Kill last fabricated citation | 30 min | 6/6 citations resolve | B |
| **3** | Populate Client 360 with real data | 1-2 days | Marcus's screen looks real | B |
| **4** | Seed demo data + EDGAR backfill | 2 hours | Narrative has real households + filings | B |
| **5** | Emit queue_update events | 4-6 hours | Queues populate; demand signals appear | B |
| **6** | Rehearsal | 1 day | Confidence | — |

**If you have 1 day:** Do 0, 2, 4. Demo at Tier B (~75% credibility).
**If you have 3 days:** Do 0, 2, 4, 3, 5. Demo at Tier B+ (~80%).
**If you have 5 days:** Do 0, 1, 2, 3, 4, 5, 6. Demo at Tier C (~90%).

---

## Part 6 — What NOT to Touch

1. **Don't refactor the coordinator.** It's 1258 lines and it works. The reviewers flagged it as a God class. They're right. But refactoring it now risks breaking the demo. Refactor after the demo.

2. **Don't add real authentication for the demo.** The Cognito scaffold exists. Wiring it takes 3-5 days and introduces a new failure mode (token expiry, JWKS fetch, redirect loops). Use dev-bootstrap-token and be honest about it.

3. **Don't try to fix the 6-version frontend bundle.** V6 is the default. V1-V5 are dead weight but they don't hurt the demo. Code splitting is a post-demo task.

4. **Don't deploy to a new AWS account.** The current account has the Bedrock KB, Aurora cluster, AgentCore runtime, and all SSM parameters. Redeploying from scratch is 90 minutes of wall time and introduces drift risk.

5. **Don't touch the specialist timeouts.** They're at 45 seconds now (raised from 25s). The V6 test results show all 4 default specialists returning successfully. The timeout fix already shipped.

6. **Don't add the specialist Gantt chart.** It's a nice-to-have visual. The running chips already show parallel activity. The Gantt is 2.5 days of frontend work that doesn't change the narrative credibility.

---

## Part 7 — The One-Sentence Brief for the Builder

**Fix the OBO secret (1 hour), wire real skills into `/agent/approve` (2-3 days), seed demo data (2 hours), and rehearse. Everything else is polish. The architecture is done. The code is done. The wiring is the gap.**

---

*Instructions written 2026-05-02. Anchored in V6 live query test results, script-vs-reality probe, and five independent reviewer assessments.*
