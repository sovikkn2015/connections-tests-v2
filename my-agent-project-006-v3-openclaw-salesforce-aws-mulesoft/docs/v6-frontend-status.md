# V6 Frontend Status

> **V6 is the recommended default.** When no version flag is set, the app
> renders V6 automatically.

## What V6 is

SLDS-inspired light theme (default) with dark toggle. All three personas
(Research / Advisor / Client) are fully implemented with V6-specific
components. V6 imports V4 atoms (TraversalMapV4, TimelineV4, AuditStripV4)
for the trust spine and audit strip — no rewrite needed.

Key design decisions:
- **Light default** — SLDS-inspired clean surfaces, not the dark-only V4 aesthetic.
- **Dark toggle** — persisted to `localStorage` key `v6.theme`, applies `data-theme` on `<html>`.
- **Designed identities** — Sarah Chen / Marcus Kerrigan / Eleanor Vance shown by default (not "Dev User").
- **All nav links use `v6=1`** — persona switching stays in V6.
- **Collapsible trust spine** — `<details>` element, open by default.

## What's wired end-to-end

| API path | Status | Notes |
|---|---|---|
| `POST /agent/invoke` (research) | ✅ Working | Full orchestrator → specialist → brief pipeline |
| `POST /agent/invoke` (advisor) | ✅ Working | Draft-only mode, action_plan surfaced |
| `POST /agent/invoke` (client) | ✅ Working | FAQ tier + hand-off tier |
| `POST /agent/approve` | ✅ Working | Gates 4-7 canonical trace |
| `GET /api/source_chunk/:id` | ✅ Working | Citation drill-down with real chunk IDs |
| WebSocket streaming | ✅ Working | useAgentSocket + useStreamingTurn |
| Queue updates (advisor) | ⚠️ Partial | Wired but empty until backend emits `queue_update` events |

## What's working

- **Citations with real chunk IDs** — `StreamingText` renders inline citations; clicking opens the source drill-down panel with extracted text from S3 chunks.
- **Market pane with extracted text** — market_specialist section extracted from brief markdown and displayed in the Market card.
- **Collapsible trust spine** — `<details>` wrapping TraversalMapV4 + TimelineV4, open by default, toggleable.
- **Light/dark toggle** — button in PersonaHeaderV6, persists to localStorage, applies `data-theme` on document root.
- **All nav links use `v6=1`** — every `<a>` href in PersonaHeaderV6 includes `v6=1` so persona switching stays in V6.
- **Designed identities** — PersonaHeaderV6 shows Sarah Chen (SC) / Marcus Kerrigan (MK) / Eleanor Vance (EV) by default; only overrides when a real authenticated user is present.
- **Research persona** — header + query bar + 3-column grid (brief | market+filings | sentiment+demand) + trust spine + audit strip.
- **Advisor persona** — header + gates tracker (when plan pending) + 3-column body (queues | conversation | client 360) + trust spine + audit strip.
- **Client persona** — header + phone bezel (WhatsApp-style) + captions + trust spine + audit strip.
- **Running chips** — tool call status chips in research persona.
- **Filings pane** — shows cited filing chunks with type badges.
- **Client 360 panel** — allocation bar, holdings overview, recent signals (advisor persona).

## What's pending

- **SF OBO audit rows** — env vars restored on `006-v3-sf-auth-proxy` but the token exchange still fails. Audit rows don't land in `IR_Audit_Log__c` until the Connected App is fully wired. See `docs/v3-p0-sf-obo-fix.md`.
- **Demand signals empty** — the Demand Signals card in research persona shows "No suggestions from the field yet" until the backend emits `queue_update` events with client inquiry roll-ups.
- **Sentiment sparkline** — placeholder; renders when `sentiment_specialist` emits a `chart_intent` (not yet implemented in backend).
- **Client 360 holdings** — placeholder values; populates when the CRM MCP call for the household returns real data.

## Live URLs

| What | URL |
|---|---|
| V6 research (default) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research |
| V6 advisor (default) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor |
| V6 client (default) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client |
| V6 research (explicit) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v6=1 |
| V6 advisor (explicit) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=advisor&v6=1 |
| V6 client (explicit) | https://d2zs9nk4uc2dbx.cloudfront.net/?persona=client&v6=1 |

## Files in the v6/ subtree

```
frontend/src/v6/
├── V6App.tsx                          # Router + theme management
├── atoms/
│   └── PersonaHeaderV6.tsx            # 44px SLDS-inspired header with nav + theme toggle
├── personas/
│   ├── ResearchTerminalV6.tsx         # Sarah Chen's research surface
│   ├── AdvisorWorkbenchV6.tsx         # Marcus Kerrigan's advisor console
│   └── ClientChannelV6.tsx            # Eleanor Vance's WhatsApp-native surface
└── styles/
    └── v6.css                         # SLDS-inspired design tokens + component styles
```

## How to verify

```bash
# Build (must compile clean)
npm --prefix frontend run build

# Run tests (including V6 smoke tests)
npm --prefix frontend run test -- --run

# Deploy to CloudFront
bash scripts/deploy-frontend-cloudfront.sh

# Verify default renders V6
curl -s -o /dev/null -w '%{http_code}' 'https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research'
# Expect: 200

# Verify explicit V6 flag
curl -s -o /dev/null -w '%{http_code}' 'https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v6=1'
# Expect: 200

# Verify V1 fallback still works
curl -s -o /dev/null -w '%{http_code}' 'https://d2zs9nk4uc2dbx.cloudfront.net/?persona=research&v1=1'
# Expect: 200
```

---

*Status doc written 2026-05-01.*
