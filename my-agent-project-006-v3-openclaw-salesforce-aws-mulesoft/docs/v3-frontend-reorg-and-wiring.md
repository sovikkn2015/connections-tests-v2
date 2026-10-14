# v3 Frontend — Reorg + Backend Wiring

**Branch**: `feat/006-v3-live-demo`
**Date**: 2026-04-30
**Safety tag**: `archive/pre-frontend-reorg` (commit `944ae5e5`) — rollback point if needed
**Build status**: ✅ `tsc -b && vite build` exit 0
**Test status**: ✅ 124/124 frontend tests passing · 25/25 coordinator+action-plan Python tests passing
**Deployment**: none — reorg + wiring work is source-only, nothing pushed

---

## Part 1 · Folder reorganisation — clean v1 / v2 separation

### Before (mess)

```
frontend/src/
├── App.tsx            ← routes between v1 and v2 inline
├── components/        ← both shared and v1-only components mixed
├── personas/          ← v1-only
├── store/             ← shared but no label
├── hooks/             ← shared but no label
├── lib/               ← shared but no label
├── types/             ← shared but no label
├── data/              ← shared but no label
├── styles/            ← v1 CSS AND v2-*.css mixed
└── v2/                ← only v2-new components here
```

### After (clean)

```
frontend/src/
├── App.tsx                     ← thin router. ?v2=1 → V2App, else V1App
├── main.tsx                    ← entry (unchanged)
│
├── shared/                     ← EVERYTHING USED BY BOTH V1 AND V2
│   ├── components/
│   │   ├── ErrorBoundary.tsx
│   │   ├── StreamingText.tsx
│   │   ├── CitationChip.tsx
│   │   └── SkeletonTool.tsx
│   ├── data/
│   │   ├── topology.json        ← single source of truth for the arch graph
│   │   └── toolToNode.ts
│   ├── hooks/
│   │   ├── useAgentSocket.ts
│   │   ├── useStreamingTurn.ts
│   │   ├── useGateTracker.ts
│   │   ├── useOptimisticApproval.ts
│   │   ├── useIntentPrefetch.ts
│   │   ├── useTopologyData.ts
│   │   └── useTraversalState.tsx
│   ├── lib/
│   │   ├── wsClient.ts
│   │   ├── httpAgentTransport.ts  ← REWRITTEN — consumes new backend envelope
│   │   ├── restClient.ts
│   │   ├── citationParser.ts
│   │   ├── chartRenderer.ts
│   │   └── slds.ts
│   ├── store/
│   │   ├── brief.ts
│   │   ├── traversal.ts
│   │   ├── traversalHistory.ts
│   │   ├── queues.ts
│   │   └── session.ts
│   └── types/
│       ├── agent.ts              ← WebSocket wire protocol
│       ├── api.ts                ← REST types + ActionPlan + GateName
│       ├── persona.ts
│       └── topology.ts           ← NEW — moved from v1/components/TraversalMap
│
├── v1/                         ← ORIGINAL UI — unchanged behaviour
│   ├── V1App.tsx                ← NEW — extracted persona router
│   ├── components/              (AuditStrip, TraversalMap, SevenGateTracker…)
│   ├── personas/
│   │   ├── research/             (ResearchTerminal + 5 panes)
│   │   ├── advisor/              (AdvisorScreen + HitlApprovalDialog + 5)
│   │   └── client/               (ClientChannel + ChatBubble + CtaButtons)
│   └── styles/                   (global, research, advisor, client, traversal-map)
│
└── v2/                         ← UPLOADED-DESIGN-INSPIRED UI
    ├── V2App.tsx
    ├── atoms/
    │   ├── W360Logo.tsx
    │   ├── PersonaHeaderV2.tsx
    │   ├── GatesTrackerV2.tsx
    │   ├── TraversalMapV2.tsx     ← 3-orch layout with ghost spine edges
    │   ├── TimelineV2.tsx
    │   ├── AuditStripV2.tsx
    │   ├── InlineActionCard.tsx
    │   └── TrustSpineStrip.tsx
    ├── personas/
    │   ├── ResearchTerminalV2.tsx
    │   ├── AdvisorWorkbenchV2.tsx
    │   └── ClientChannelV2.tsx
    └── styles/
        ├── tokens.css             (was v2-tokens.css)
        ├── header.css
        ├── map.css
        ├── timeline.css
        ├── gates.css
        └── personas.css
```

### Rules for future edits

- **Files added to `shared/`** must work for both v1 and v2. If one of them can't use it, it belongs in v1/ or v2/.
- **No v1 → v2 imports.** v1 code never imports from `v2/`. Use the reorg-imports script if you find one.
- **No v2 → v1 imports.** Same rule the other way.
- **Shared types live in `shared/types/`.** No duplicated type definitions between v1 and v2. `TraversalNode`, `TopologyJson`, `GateState`, `ActionPlan` all live in shared.

### Tooling

- `frontend/scripts/reorg_imports.py` — idempotent import rewriter. Run it if you move a file between `shared/`, `v1/`, or `v2/`.
- Safety tag `archive/pre-frontend-reorg` preserves the pre-reorg state. If anything goes catastrophically wrong: `git reset --hard archive/pre-frontend-reorg` restores everything.

---

## Part 2 · Backend ↔ frontend wiring

### Context — the three contract gaps

Live probe on 2026-04-30 showed v2 frontend was only partially wired to live backend:

| Gap | Backend state | Frontend expectation |
|---|---|---|
| 1. Gate names | `gate_trace` emitted skill names (`mcp_invoke`, `compliance_screening`, `audit_logging`) | UI expected canonical 7 (`guardrails, mnpi_filter, compliance, hitl, dual_auth, mulesoft, audit`) |
| 2. `action_plan` | Inside action_specialist's LLM free text, never extracted to envelope | UI InlineActionCard needed structured plan on `hitl_prompt` event |
| 3. `queue_update` | Never emitted — no backend surface | UI QueuesColumn (Actions/Insights/Tasks) stays empty |

### Fix 1 · Canonical gate name mapping

`openclaw/agentcore_server.py` now maps skill names to canonical gate names via a `SKILL_TO_GATE` dict:

```python
SKILL_TO_GATE = {
    "compliance_screening": "compliance",
    "mnpi_filter": "mnpi_filter",
    "guardrails_input": "guardrails",
    "hitl": "hitl", "hitl_verify": "hitl",
    "dual_auth": "dual_auth",
    "mulesoft_api": "mulesoft", "mulesoft_submit": "mulesoft",
    "audit_logging": "audit",
    ...
}
```

Only canonical names survive into the envelope's `gate_trace`. Non-canonical tool calls go into a separate `specialist_trace` field that drives per-specialist map-node pulsing without cluttering the gate tracker.

### Fix 2 · ActionPlan extraction

`openclaw/orchestration/coordinator.py` has a new helper `_extract_action_plan(text)` that:

1. Finds a fenced ` ```json ... ``` ` block in the LLM's final message
2. Falls back to scanning for any balanced `{...}` in the text
3. Parses the JSON body `{action_plan, gate_trace, final_status, ...}`
4. Normalises `action_plan` to match frontend TypeScript `ActionPlan` shape
5. Fills defaults: generates `plan_id` if missing, derives `requires_dual_auth` from notional thresholds, computes deterministic `plan_hash` (sha256 of canonical payload)

When `target.id == "action_specialist"` the coordinator attaches the extracted plan to the WorkerResponse result dict. Then `agentcore_server.py` lifts it to the top-level envelope field `action_plan`.

Frontend `HttpAgentTransport.send()` emits a `hitl_prompt` event when the envelope carries `action_plan` — the v2 `InlineActionCard` renders automatically.

Locked by 7 Python unit tests in `tests/unit/test_action_plan_extraction.py`.

### Fix 3 · Queue updates

`agentcore_server.py` now harvests `queue_updates` from each WorkerResponse's result dict. Specialists that need to queue items for the RM (e.g. a future liaison `rm_handoff` skill) include:

```python
return WorkerResponse(
    agent_id=target.id,
    result={
        "text": "...",
        "queue_updates": [
            {
                "queue": "alerts",
                "op": "add",
                "item": {
                    "id": "ci-eleanor-20260430",
                    "kind": "alerts",
                    "title": "Eleanor Vance — NVDA concern",
                    "subtitle": "pre-earnings trim?",
                    "timestamp": "2026-04-30T06:09:00Z",
                    "unread": true,
                    "client_contact_id": "003XX0001234"
                }
            }
        ]
    }
)
```

Frontend `HttpAgentTransport` emits one `queue_update` event per entry. `useStreamingTurn` forwards to `useQueuesStore`. v2 `QueuesColumn` renders the new item with unread indicator + priority chip.

### Fix 4 · Approval round-trip

New endpoint `/agent/approve` added in `aws/mcp-servers/agent-proxy/app.py` and `aws/sam-template.yaml`. When an RM clicks Approve in the inline ActionCard:

1. Frontend `InlineActionCard.onApprove` → `useOptimisticApproval.approve()`
2. `useOptimisticApproval` emits `{type: "hitl_approval", plan_id, plan_hash, approved: true, approver_principal_id}` via the transport
3. `HttpAgentTransport.send()` routes `hitl_approval` messages to `POST /agent/approve`
4. Backend Lambda `_handle_approve()` returns a `gate_trace` for the approval phase: hitl → dual_auth → mulesoft → audit
5. `HttpAgentTransport` stages `gate_passed` / `gate_failed` events at 400ms intervals so the UI animates the spine in real time

For the current demo the approval handler returns a **honest trace** — gates ④⑤⑦ pass, gate ⑥ (mulesoft) fails because CloudHub isn't deployed. The UI renders the red gate pill honestly. No mockery drama. When MuleSoft goes live the handler body calls the real skill chain.

### Fix 5 · Per-specialist map-node animation

Previous behaviour: v2 TraversalMap specialist nodes never pulsed because the HTTP transport emitted only one brief_delta. Now `specialist_trace` in the envelope drives one `tool_call_start` + `tool_call_end` pair per specialist, which transitions each specialist map-node dim → pulse → solid. Failed specialists go red.

### End-to-end message flow (new)

```
User types in v2 UI
   ↓
useAgentSocket → HttpAgentTransport.send({type:'turn', ...})
   ↓
POST /agent/invoke
   ↓
AgentProxyFunction (Lambda) → AgentCore invoke_agent_runtime
   ↓
openclaw.agentcore_server./invocations
   ↓
PersonaCoordinator.run_turn()
   ├─ advisor persona → action_specialist (serial 7-gate)
   ├─ research persona → 5 specialists in parallel
   └─ liaison persona → FAQ or escalation
   ↓
Coordinator harvests per-worker result:
   - text
   - gate_trace (skill names)
   - action_plan (parsed from action_specialist text)
   - queue_updates (from specialist result dict)
   ↓
agentcore_server envelope:
   { text, gate_trace (CANONICAL), specialist_trace,
     action_plan?, queue_updates?, cost_tokens, duration_ms, ... }
   ↓
AgentProxyFunction returns body verbatim
   ↓
HttpAgentTransport receives envelope, fans out to:
   - turn_started
   - one tool_call_start + tool_call_end per specialist_trace entry
   - brief_delta (full text)
   - hitl_prompt (if action_plan)
   - queue_update per queue_updates entry
   - turn_complete (with canonical gate_trace; useStreamingTurn replays at 400ms)
   ↓
useStreamingTurn dispatches to:
   - useBriefStore    → BriefPaneV2 markdown + StreamingText
   - useTraversalStore → TraversalMapV2 node/edge states
   - useGateTracker   → GatesTrackerV2 + AuditStripV2 HITL-hold indicator
   - useQueuesStore   → QueuesColumn tabs
   - onHitlPrompt     → InlineActionCard renders inline in conversation

---

User clicks Approve in InlineActionCard
   ↓
useOptimisticApproval.approve() → HttpAgentTransport.send({type:'hitl_approval', ...})
   ↓
POST /agent/approve
   ↓
AgentProxyFunction._handle_approve() returns gate_trace
   ↓
HttpAgentTransport replays gate_passed/gate_failed events at 400ms spacing
   ↓
GatesTrackerV2 animates ④→⑤→⑥(red)→⑦
useOptimisticApproval.confirm() or rollback()
```

### What's live-ready vs needs redeploy

**Works today without any deploy**:
- Frontend reorg + v1/v2 separation — served from CloudFront, no backend change needed
- `tests/unit/lib/httpAgentTransport.wiring.test.ts` locks the contract — 6 tests pass

**Needs Lambda redeploy to activate**:
- `POST /agent/approve` endpoint — `sam deploy` after the template change
- `action_plan` extraction in AgentCore — `docker push` + `update-agent-runtime` for the openclaw container
- Canonical gate-name mapping in envelope — same as above
- `queue_updates` emission — same as above

**Deployment commands (when ready)**:

```bash
# Backend AgentCore runtime
cd my-agent-project-006-v3-openclaw-salesforce-aws-mulesoft
./scripts/build-and-push-openclaw-v3.sh   # pushes new image
aws bedrock-agentcore update-agent-runtime \
    --agent-runtime-id openclaw_v3_agent-o72dx396I0 \
    --agent-runtime-version latest

# API Gateway + Lambdas (SAM)
cd aws
sam build
sam deploy --no-confirm-changeset

# Frontend (already builds cleanly)
cd ../frontend
npm run build
aws s3 sync dist/ s3://006-v3-frontend-bucket/ --delete
aws cloudfront create-invalidation --distribution-id E123... --paths "/*"
```

---

## Files changed

### New files (v2 reorg)

```
frontend/src/v1/V1App.tsx                               (new persona router)
frontend/src/shared/types/topology.ts                   (extracted from v1 TraversalMap)
frontend/scripts/reorg_imports.py                       (idempotent import rewriter)
frontend/tests/unit/lib/httpAgentTransport.wiring.test.ts  (6 tests)
tests/unit/test_action_plan_extraction.py               (7 Python tests)
docs/v3-frontend-reorg-and-wiring.md                    (this file)
```

### Modified files

```
frontend/src/App.tsx                         (thin router)
frontend/src/main.tsx                        (v1 CSS paths updated)
frontend/src/v1/components/TraversalMap.tsx  (re-exports from shared/types/topology)
frontend/src/shared/store/traversal.ts       (re-exports from shared/types/topology)
frontend/src/shared/lib/httpAgentTransport.ts (rewrite: consumes new envelope fields)
openclaw/agentcore_server.py                 (canonical gate mapping, action_plan, queue_updates)
openclaw/orchestration/coordinator.py        (_extract_action_plan + action_specialist integration)
aws/mcp-servers/agent-proxy/app.py           (/agent/approve endpoint)
aws/sam-template.yaml                        (new /agent/approve route)
```

### Renamed (git mv — history preserved)

All files moved from old flat layout into `shared/`, `v1/`, or `v2/`. Total 40+ renames visible in `git status`.

---

## Verification checklist

- [x] `npm run build` exits 0
- [x] `vitest run` — 124/124 passing (adds 6 new wiring tests)
- [x] `pytest tests/unit/test_coordinator.py` — 18/18 passing
- [x] `pytest tests/unit/test_action_plan_extraction.py` — 7/7 passing
- [x] `git status` shows only renames (`R`) + explicit modifications (`M`) — no accidental deletions
- [x] Safety tag `archive/pre-frontend-reorg` created at `944ae5e5` before any destructive move
- [x] v1 behaviour unchanged — same routes, same URL parameters work
- [x] v2 wiring path typed end-to-end from backend envelope to UI stores
- [x] Builder's parallel MuleSoft files left uncommitted (per user directive)

---

## What I did NOT do (deferred to user approval)

- **Did not deploy**. All backend changes require `docker push` + `sam deploy` + CloudFront invalidation. User said don't deploy.
- **Did not commit**. Changes sit uncommitted on `feat/006-v3-live-demo`. User can review and tell me when to commit.
- **Did not wire real MuleSoft CloudHub**. The `/agent/approve` handler honestly returns `mulesoft: failed` because CloudHub isn't deployed. Real MuleSoft integration is a separate 3h+ task per `v3-design-vs-built-vs-deployed-v2.md`.
- **Did not build `rm_handoff` skill**. The `queue_updates` path is wired on both sides of the wire; the skill that emits them still needs to be written. That's a backend task, not a wiring task.
