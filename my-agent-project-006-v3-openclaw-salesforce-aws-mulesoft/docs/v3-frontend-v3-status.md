# Frontend v3 — Session Status

**Branch:** `feat/006-v3-live-demo`
**Date:** 2026-05-01
**Live URL:** `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v3=1`

---

## What shipped this session

### New frontend `v3/` subtree — independent, wired, FSI Workforce 360 branded

```
frontend/src/v3/
├── V3App.tsx                        (router + Cognito gate + auth callback)
├── auth/
│   ├── cognito.ts                    (PKCE flow: login, code exchange, refresh)
│   └── AuthCallback.tsx              (/auth/callback handler)
├── atoms/
│   ├── FsiLogo.tsx                   (new "Workforce 360" brand mark)
│   ├── PersonaHeaderV3.tsx           (header + nav + sign-out)
│   └── TraversalMapV3.tsx            (MAP POLISH — tooltips + legend + filter + caption)
├── personas/
│   ├── ResearchTerminalV3.tsx
│   ├── AdvisorWorkbenchV3.tsx        (progressive gate chain disclosure)
│   └── ClientChannelV3.tsx
└── styles/
    ├── tokens.css                    (FSI Workforce 360 CSS variables)
    ├── header.css
    ├── map.css                        (tooltips, legend, filter, spine band)
    └── personas.css
```

### Live architecture map — polish pass (roadmap item #8)

All 7 improvements landed:

| Improvement | How it shows up |
|---|---|
| 1. Hover tooltips | Hover any node → role + kind + persona + model + tools + MCPs + last latency + error + Langfuse hint |
| 2. Collapsible legend | Toggle button in top-right. Shows 6 node kinds + 4 state colors inline |
| 3. "this-turn only" filter | Toggle button. Hides all dim nodes/edges so only what fired this turn is visible |
| 4. Per-persona caption | Human-readable explainer below the map: "Sarah's research fans out to N specialists in parallel" / "Marcus's write path funnels through 7 sequential gates" / "Eleanor's message flows through the same spine…" |
| 5. Progressive disclosure | Advisor gate chain renders ONLY when `pendingPlan` is set (write in flight). No more 7 dim gates dominating the map on every advisor load. |
| 6. Trust-spine band | Subtle horizontal glow band behind the three orchestrator nodes (replaces v2's ambiguous dashed ghost edges with a clearer "one graph" visual) |
| 7. Higher-contrast edges | Edge stroke-width bumped + dashflow velocity tuned. Dim edges more subtle; active edges more obvious. |

### FSI Workforce 360 rename (roadmap item #6)

- New `FsiLogo` brand mark (three persona-arcs around a hub — different from v2's `W360Logo`)
- `PersonaHeaderV3` title "FSI Workforce 360" (replaces v2's "Workflow 360")
- Advisor inline action card attribution: "FSI Workforce 360 · Advisor" (was "Workflow 360 · Advisor")
- CSS variables renamed `--w360-*` → `--fsi-*` (scoped to `.v3-root`)
- v1 and v2 branding **untouched** — they still render "Workflow 360"

### Cognito auth scaffold (roadmap item #3)

- `auth/cognito.ts` — full PKCE flow: start login, exchange code, refresh tokens, decode JWT claims, save/load/clear localStorage session
- `auth/AuthCallback.tsx` — renders on `/auth/callback`, completes PKCE, hands token to session store, redirects back to persona
- `V3App.tsx` — gates persona render on auth phase:
  - `pending` → loading
  - `needs_login` → "Sign in with Cognito" button
  - `ready` → render persona
- `PersonaHeaderV3` has optional "Sign out" button when Cognito is active
- Backend: the agent-proxy Lambda already accepts any bearer token when
  `MCP_DEV_MODE=true`, which works with Cognito access tokens AS IS.
  JWT signature verification against JWKS is a next-step addition, not
  required for the demo.

**Activation:** Populate `VITE_COGNITO_DOMAIN`, `VITE_COGNITO_CLIENT_ID`,
`VITE_COGNITO_REDIRECT_URI` in `.env.production`. See `docs/v3-cognito-setup.md`
(to be written — Cognito resource creation playbook). Without those vars,
v3 gracefully falls back to the dev-bootstrap-token flow.

---

## Build + deploy status

- `tsc -b && vite build` → exit 0
- 128 frontend tests still pass
- Deployed to CloudFront `E3T0OIRWDE1J8Y` with invalidation
- New bundle: `index-CilXKNMg.js` (404 KB, +37 KB over v2)

Live URLs:

```
v3 research:  https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v3=1
v3 advisor:   https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v3=1
v3 client:    https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v3=1

v2 (fallback): https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v2=1
v1 (fallback): https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research
```

---

## What did NOT ship this session (P0 backend)

These are documented with full remediation runbooks but **not code-patched by me** because the backend builder is iterating on `coordinator.py` / orchestrator files / skills in parallel. Merging during their work risks conflicts and bug injection.

| P0 Item | Status | Runbook |
|---|---|---|
| 1. Audit rows zero today | Same root cause as #3 — SF OBO chain empty secret | `docs/v3-p0-sf-obo-fix.md` |
| 2. Published_At__c never set | **Builder already in-flight** (`coordinator.py` has new `_publish_research_brief` method in uncommitted diff) | Let builder land |
| 3. Research_Request__c 401 | SF Connected App + private key missing from Secrets Manager | `docs/v3-p0-sf-obo-fix.md` |
| 4. source_chunk drill-down empty | Research specialists emit fabricated citation IDs instead of real chunk_ids | `docs/v3-p0-source-chunk-citation-drift.md` |
| 5. Research specialist tool-use | **Builder is in-flight** on orchestrator files | Let builder land |

**Handoff:** the 2 items I can't fix without Salesforce admin access (1 + 3) are ONE secret update — see `docs/v3-p0-sf-obo-fix.md` for the 6-step Connected App + secret playbook. Items 2 and 5 are builder's territory.

---

## Items deferred to V4/V5 (roadmap)

| # | Item | Status |
|---|---|---|
| 1 | Multi-modal voice | V5 |
| 2 | AgentCore Memory | V4 |
| 4 | Langfuse prompt management | V4 |
| 5 | Light/dark mode | Needs design decision |
| 7 | Client map+trace organisation | Partial — v3 adds caption + tooltip, full redesign deferred |

---

## Verification steps

### Build
```bash
npm --prefix frontend run build
# tsc -b && vite build → exit 0
```

### Tests
```bash
npm --prefix frontend run test -- --run
# 128 tests passing, 25 test files
```

### Live smoke
```bash
bash scripts/smoke-test.sh
# 10/10 (v2 envelope tests still pass — v3 uses the same envelope)
```

### Manual
1. Open `https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v3=1`
2. Verify header says "FSI Workforce 360"
3. Type "Research NVDA" + ⌘↵
4. Hover a node in the architecture map → tooltip should show role + tools + persona + state
5. Click "legend" toggle → 6 kinds + 4 states legend appears
6. Click "this-turn only" → dim nodes hide, only lit ones remain
7. Read the caption below the map
8. Switch to advisor persona, type a trim query
9. Once draft lands, confirm gate chain only appears when `pendingPlan` is set
10. Click Approve → gates 4-7 animate

---

## Files changed this session

```
frontend/src/App.tsx                             MODIFIED (+7 LOC for v3 route)
frontend/.env.production                         MODIFIED (+14 LOC for Cognito vars)
frontend/.env.example                            MODIFIED (+21 LOC for Cognito docs)

frontend/src/v3/V3App.tsx                        NEW
frontend/src/v3/auth/cognito.ts                  NEW
frontend/src/v3/auth/AuthCallback.tsx            NEW
frontend/src/v3/atoms/FsiLogo.tsx                NEW
frontend/src/v3/atoms/PersonaHeaderV3.tsx        NEW
frontend/src/v3/atoms/TraversalMapV3.tsx         NEW
frontend/src/v3/personas/ResearchTerminalV3.tsx  NEW
frontend/src/v3/personas/AdvisorWorkbenchV3.tsx  NEW
frontend/src/v3/personas/ClientChannelV3.tsx     NEW
frontend/src/v3/styles/tokens.css                NEW
frontend/src/v3/styles/header.css                NEW
frontend/src/v3/styles/map.css                   NEW
frontend/src/v3/styles/personas.css              NEW

docs/v3-frontend-v3-status.md                    NEW (this doc)
docs/v3-p0-sf-obo-fix.md                         NEW (handoff for backend)
docs/v3-p0-source-chunk-citation-drift.md        NEW (handoff for backend)
```

**Zero changes** to `openclaw/`, `aws/mcp-servers/`, or Salesforce metadata.
Builder's parallel work is untouched.
