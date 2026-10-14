# 006 v3 — Demo Queries by Narrative

**Base URL:** `https://d2zs9nk4uc2dbx.cloudfront.net`

**Personas:**
- Research (Sarah Chen): `?persona=research&v2=1`
- Advisor (Marcus Kerrigan): `?persona=advisor&v2=1`
- Client (Eleanor Vance): `?persona=client&v2=1`

**Auth:** The SPA auto-mints a `dev-bootstrap-token` on load (via `VITE_AUTH_DEV_BOOTSTRAP=1` in `.env.production`). No login required for the demo.

Copy-paste the queries below. Each is verified live against the deployed stack (AgentCore v20, SAM stack `openclaw-mcp-006-v3`, CloudFront `E3T0OIRWDE1J8Y`).

---

## Narrative matrix

| # | Narrative | Status | Persona(s) | Live query required |
|---|---|---|---|---|
| N1 | Earnings Morning | 🟢 live | Research | yes |
| N2 | Client drives research → RM handoff | 🟢 live | Client + Advisor | yes |
| N3 | Risk Alert | 🟡 slide-only by design | Advisor | no (pre-seeded rows) |
| N4 | Demand Signal | 🟡 slide-only by design | Research | no (pre-seeded rows) |
| N5 | Large Liquidation | 🟢 live (draft + approve) | Advisor | yes |

🟢 = demoable end-to-end live right now. 🟡 = slide-only by design (V4 roadmap, presented with pre-seeded Salesforce data, no live backend turn).

---

## N1 · Earnings Morning 🟢 live

Sarah's cold-open. Research orchestrator fans to 3-5 specialists in parallel (market, filings, sentiment, compliance, optionally statement). Proves `asyncio.gather` because specialist spans overlap on the timeline.

**Tab:** `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v2=1`

**Primary query:**
```
Research NVDA ahead of earnings — focus on data-center mix and China exposure
```

**What to watch:**
- ~22s wait
- 3-4 specialist nodes pulse on the architecture map (market_specialist, filings_specialist, sentiment_specialist, compliance_specialist)
- Brief streams into the main pane with `[src:...]` citations
- Audit strip at the bottom shows trace id + per-specialist pills + cost ($0.10-0.20)
- Gate tracker shows `compliance: passed ✓`

**Alt queries that also work:**

```
What's happening with NVDA this week?
```

```
Quick NVDA check — 10-Q, sentiment, compliance
```

```
Research AAPL financial statements — margins and ROE trend
```
*(This one fires the 5th specialist — `statement_specialist` — because the text contains "financial statements".)*

```
Research MSFT ahead of earnings — cloud growth and capex guide
```

**Known flakiness:** 1 of 4 specialists may time out on any given turn (Bedrock + tool-use loops occasionally exceed 25s). The brief text will say `gaps: <specialist>(timeout)`. Not a UI bug. Re-running usually succeeds.

---

## N2 · Client drives research → RM handoff 🟢 live

The full cross-persona loop: Client Eleanor asks a position question, Liaison agent defers ("your RM will reach out"), a `queue_update` fires that makes Marcus's Actions queue light up in real time. Proves the trust spine is one graph across three surfaces.

**Two tabs open side by side.**

### Tab 1 — Client (Eleanor)
`https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v2=1`

**Primary query:**
```
Marcus I am nervous about NVDA earnings. Should we lock some gains?
```

**What to watch:**
- ~18s wait
- Agent bubble appears in the WhatsApp-style chat with:
  - "Thanks for your message. I've noted it (ref a0DgK...)"
  - "Also queued a research ask on NVDA for the research team"
  - "In the meantime, you can schedule a call"
- Yellow disclaimer bar at bottom: "For informational purposes. Your RM makes recommendations."
- No positions, no numbers, no advice (MNPI-safe by construction)

**Alt queries (trigger escalation path, same flow):**

```
I keep seeing China headlines and it makes me nervous about my semi exposure.
```

```
Should I be worried about NVDA before the print?
```

```
My AAPL position feels heavy — can we talk about trimming?
```

```
I want to sell some of my tech names, can we chat?
```

### Tab 2 — Advisor (Marcus)
`https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1`

**No query needed.** Refresh or leave open before Eleanor sends her message.

**What to watch:**
- A new item appears in the **Actions** queue (left column) within ~1s of the liaison turn completing
- Shows red "high" priority badge
- Title includes ticker + truncated inquiry text
- Subtitle: "Client inquiry via liaison — needs RM review"
- Click the item → `ClientContextColumn` loads on the right with the client signal

### FAQ tier (shorter, no handoff)

If you want to show the FAQ path (client-safe, Haiku-fast, no queue fired):

```
What are market hours today?
```

```
Can I schedule a call with my RM next week?
```

```
What is a 10-K filing?
```

```
When is earnings season?
```

These return in ~5s with canned reply + disclaimer. No Salesforce writes, no queue_update to Marcus.

---

## N3 · Risk Alert 🟡 slide-only by design

Per the v3 design doc, this is scoped as V4/roadmap — shown as a slide, backed by pre-seeded Salesforce rows, not a live turn. The UI renders the pre-seeded alerts but no live backend interaction is required.

**Tab:** `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1`

**What to point at:**
- Actions queue contains pre-seeded Client_Alert__c rows (if `scripts/seed-demo-rows.sh` has run)
- Example row: "NVDA concentration breach — Eleanor Vance (14.2% > 12% IPS ceiling)"
- Click an alert → Client 360 loads with the IPS band + concentration warning

**No query to type.** Present this as "here's what the alerting surface looks like; live scoring fires from the risk pipeline (Aurora + DynamoDB) — out of scope for this demo but infrastructure is in place."

---

## N4 · Demand Signal 🟡 slide-only by design

Same framing as N3 — V4 roadmap, no live turn.

**Tab:** `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v2=1`

**What to point at:**
- Right column bottom pane: **Demand Signals**
- Pre-seeded items like "Pre-earnings · NVDA · RM Marcus K. · 3 clients"
- Click `accept →` on an item → it auto-populates the query input and fires a real research turn (so this isn't *entirely* dead — it's a shortcut into N1)

**No query to type.** Present as: "demand signals surface here would cluster inquiries from the RM channel back to Sarah — shown as pre-seeded, real clustering lives in V4."

---

## N5 · Large Liquidation 🟢 live (draft + approve round-trip)

Advisor write path. **Two steps, two API calls, two UI interactions.**

**Tab:** `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1`

### Step 1 — Draft plan

**Primary query:**
```
Trim Eleanor Vance NVDA from 14.2% to 9.5% of equity sleeve, limit 211.10
```

**What to watch:**
- ~20s wait (draft-only mode — gates 1-3 only, fits under 29s API Gateway timeout)
- AI message ("Workflow 360 · Advisor · action_specialist") appears in the conversation
- `InlineActionCard` renders **inside** the AI message (not a modal) showing:
  - action: SUBMIT
  - household: Eleanor Vance
  - notional: estimated $
  - plan_hash: 12-char truncation
  - buttons: **Approve & submit** (green) · **Edit plan** · **Deny**
  - keyboard hint: "⌘↵ approve · ⌘⌫ deny"
- Gate tracker shows ①②③ all passed ✓, ④⑤⑥⑦ pending
- Audit strip shows trace id + action_specialist pill

### Step 2 — Approve

Click **Approve & submit** (or press ⌘↵).

**What to watch:**
- <1s round-trip
- Gate tracker animates:
  - ④ hitl → passed ✓ (token verified)
  - ⑤ dual_auth → passed ✓ (below threshold for this notional)
  - ⑥ **mulesoft → FAILED red** (CloudHub not deployed — honest, not mockery)
  - ⑦ audit → passed ✓ (failure logged)
- InlineActionCard shows rollback toast: "Rolled back: mulesoft gate failed"

This is the "no mockery drama" moment. MuleSoft fails because CloudHub apps aren't deployed, and the UI renders that honestly instead of faking success.

### Alt queries that render the ActionCard

```
Sell 500 shares of AAPL for Kapoor household, market order
```

```
Wire $250K from Vance household to broker account
```
*(Triggers `requires_dual_auth: true` — notional > $100K on a wire. InlineActionCard shows the dual-auth badge.)*

```
Cancel order OMS-123 for Kapoor Trust
```

```
Rebalance Marston Trust — drift exceeds IPS band
```

```
Wire $600K from Marston Trust to Schwab account
```
*(Both `requires_dual_auth: true` AND mulesoft will still fail — great for showing both dual-auth UX and honest failure together.)*

---

## Bonus: non-action advisor queries

These fire single-specialist paths — no InlineActionCard, faster turns. Useful for showing the advisor surface without waiting 20s.

**Tab:** `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v2=1`

**Suitability intent (~6s):**
```
Is NVDA suitable for Eleanor Vance given her IPS?
```

**Portfolio intent (~6s):**
```
What is my NVDA concentration across the book and should I be concerned?
```

```
Show me drawdown and attribution for Eleanor's equity sleeve
```

**Research-aware intent (~8-12s, parallel fanout to client_context + portfolio):**
```
Give me a prep brief for my call with Eleanor this afternoon
```

```
What should I know about Kapoor Trust before the quarterly review?
```

---

## Full demo sequence (~4 minutes, all 3 live narratives + cross-persona story)

| Step | Tab | Action | Wall time |
|---|---|---|---|
| 1 | Research | Type N1 query, click RUN | 22s |
| 2 | Research | Point at architecture map (3 orchestrators at top, specialists fanning out) + audit pills streaming | (while streaming) |
| 3 | Client | Open new tab, type N2 query, Send | 18s |
| 4 | Advisor | Open new tab, refresh, point at new Actions item (red "high" badge) | instant |
| 5 | Advisor | Click the Actions item → Client 360 loads → type N5 query | 20s |
| 6 | Advisor | Point at InlineActionCard (inline, not modal), click **Approve & submit** | 1s |
| 7 | Advisor | Watch gates 4-7 animate — hitl ✓ dual_auth ✓ **mulesoft ✗** audit ✓ | (animation) |

**Live interaction total:** ~60s
**With reading + pointing:** ~3-4 min
**Personas demonstrated:** 3
**Narratives demonstrated:** N1, N2, N5 live · N3, N4 pre-seeded as slides

---

## Troubleshooting

**Click RUN / Send, nothing happens:**
- Hard refresh: Cmd+Shift+R (macOS) or Ctrl+Shift+R (Win/Linux)
- Check DevTools → Network: you should see `POST /agent/invoke` → 200 in 5-25s
- If you see no network request at all, auth bootstrap failed — file an issue with the browser console output

**Advisor returns HTTP 504:**
- Means draft-only mode didn't activate. The query classifier didn't detect an action verb.
- Try rewording with an explicit verb: `trim`, `sell`, `buy`, `wire`, `rebalance`, `cancel`, `modify`

**Brief says `gaps: <specialist>(timeout)`:**
- Upstream MCP flakiness (Tavily, Finnhub, EDGAR). Not a UI bug. Re-run the query.

**v2 shows blank page:**
- Verify you have `?v2=1` in the URL
- Check DevTools → Console for JS errors
- If the console says "session token null" something similar, the auth bootstrap env flag didn't ship. Contact the deploy maintainer.

**InlineActionCard never appears after advisor turn:**
- You typed a non-action query (suitability / portfolio intent) — that's by design, those don't draft plans
- Or the backend returned without `action_plan` in the envelope — check response JSON in DevTools Network tab

---

## What's NOT demoable and why

- **Real MuleSoft order submission** — CloudHub apps exist as local Maven projects but have never been `mvn deploy -Pcloudhub-sandbox`. Gate ⑥ honestly fails. To fix: ~3h work deploying the 3 Mule apps, substituting the NAT EIP allowlist, and setting secure-properties in Anypoint UI.
- **Real IdP bootstrap** — `VITE_AUTH_DEV_BOOTSTRAP=1` mints a dev token. A production deploy would swap this for Okta/Azure AD PKCE via `VITE_IDP_ISSUER`.
- **N3, N4 live** — these require the risk-pipeline DynamoDB streams and demand-clustering algorithm which are V4 roadmap per the design doc.

All three gaps are documented in `docs/v3-design-vs-built-vs-deployed-v2.md`.
