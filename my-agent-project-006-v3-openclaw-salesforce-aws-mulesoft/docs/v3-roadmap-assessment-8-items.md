# 006 v3 — Assessment of 8 Proposed Roadmap Items

**Date:** 2026-05-01
**Scope:** Assessment only. No code changes made.
**Source of truth:** live codebase at `feat/006-v3-live-demo` + deployed stack (AgentCore v21, CloudFront bundle `index-y3nrRVYc.js`).

Each item is scored on 4 axes:
- **Code in repo today** — is there any scaffolding?
- **Deployed today** — does it work live?
- **Design fit** — does the existing v3 architecture support it?
- **Effort to land** — estimated work to reach demo-ready

---

## 1. Multi-modal data for AnalystVoice (RM + Client)

### What it means
Voice-mode for RM (Marcus) and Client (Eleanor) surfaces. Let Eleanor speak into WhatsApp, let Marcus dictate orders, generate TTS brief narration for Sarah's research.

### Current state

| Axis | Reality |
|---|---|
| Code | **None**. Zero references to Polly, Nova Sonic, Whisper, TTS, multimodal, audio in openclaw or frontend source. |
| Deployed | Not applicable — nothing shipped. |
| Design fit | **Additive**. Bedrock Nova Sonic (speech-to-speech) or Polly + Whisper sit cleanly as a new MCP server. AgentCore supports multimodal input. No orchestrator changes needed. |
| Effort | **2-3 weeks**. New MCP (speech-io) + frontend `<audio>` recording/playback + backend transcription hook. Client persona is the natural entry point (WhatsApp pattern already native to voice). |

### Risks
- **Regulatory**: voice transcripts are MNPI-class content. MNPI filter needs to run on transcript BEFORE it hits the LLM, not after.
- **Latency**: adds 1-3s to every turn for STT/TTS round-trip. Already at 10-25s — budget pressure.
- **Hallucinated voice output**: LLM-generated voice narration of a brief could mis-speak numbers. Prefer deterministic TTS of the already-cited text, not a voice-specific LLM generation.

### Recommendation
**Deferred. High strategic value, but the existing v3 has unresolved P0 gaps (audit rows, Published_At__c, Research_Request__c 401) that should close first.** Start with client-side STT only (Whisper in the browser or Polly streaming) — don't add LLM-side multimodal reasoning in v3.

---

## 2. AgentCore Memory

### What it means
AWS's managed Memory service for AgentCore runtimes — persistent short-term (session scratchpad) and long-term (user profile) memory with automatic summarization and PII filtering.

### Current state

| Axis | Reality |
|---|---|
| Code | **Scaffolding only**. `openclaw/orchestration/topology.py` defines a `MemoryScope` enum (SESSION, USER, ARTIFACT, READ_ONLY) and every agent has a `memory_scope` list. **But there is ZERO integration with AgentCore's actual Memory service.** No `create_memory`, no `invoke_memory`, no memory client. The enum is a type-level annotation, not wired. |
| Deployed | Not deployed. No memory resources in CloudFormation/CDK. |
| Design fit | **Strong**. The `MemoryScope` enum was designed specifically for this — plumbing exists. `gate_enforcer.py` reads `memory_scope` for read-only enforcement but doesn't persist anything. |
| Effort | **1-2 weeks**. Create AgentCore Memory resource (CDK), wire a MemoryClient into the coordinator, populate the `SESSION` scope from each turn, populate `USER` scope per `principal_id`, add memory-read calls to specialists that declare `MemoryScope.USER`. |

### Risks
- **Cost**: per-turn memory write + summarization is a real $ line item. Need to measure.
- **Leakage**: USER memory crossing personas is the whole point, but MNPI must not leak into client-safe context from USER memory. Trust layer needs to re-apply MNPI filter on memory read.
- **Consistency with Salesforce as system of record**: memory becomes a second source of truth. Design decision: which wins?

### Recommendation
**Good fit for v4.** The plumbing is already in topology.py — that was forward-looking. Light lift compared to voice. Would demo well via Narrative 2 (liaison remembers Eleanor's previous inquiry across sessions).

---

## 3. Authorization — Cognito

### What it means
Replace `dev-bootstrap-token` with AWS Cognito hosted UI for OAuth 2.0 PKCE. Real IdP, real user pool, real JWT.

### Current state

| Axis | Reality |
|---|---|
| Code | **None beyond SDK presence**. Cognito only appears in AWS SDK boto3 data files (endpoints.json) as a side-effect of the Lambda layer. No `cognito_client`, no UserPool resource, no hosted UI config. |
| Deployed | **Not deployed**. Current auth is `VITE_AUTH_DEV_BOOTSTRAP=1` → mints `dev-bootstrap-token` client-side. agent-proxy Lambda accepts any Bearer when `MCP_DEV_MODE=true`. |
| Design fit | **Clean**. `App.tsx` has a `shouldUseDevBootstrap()` guard — when `VITE_AUTH_DEV_BOOTSTRAP=0` the SPA will try to call the channel adapter (PKCE). That channel adapter doesn't exist yet, but the split is intentional. Session HMAC mint/verify logic already exists in agent-proxy app.py. |
| Effort | **3-5 days**. (1) Create Cognito User Pool via CDK. (2) Enable hosted UI. (3) Add `/auth/callback` route in the SPA that exchanges code for token via PKCE. (4) Have agent-proxy verify Cognito JWT via `cognito-idp.VerifyToken` instead of accepting any bearer in dev mode. |

### Risks
- **Demo flow**: auto-login via PKCE adds a sign-in page to the demo. For a 5-min cold-open, dev-bootstrap is actually nicer. Consider keeping both behind an env flag.
- **Per-user OBO chain integrity**: Cognito JWT carries the `sub` claim. sf-auth-proxy's OBO needs that sub to map to a Salesforce user. Today the mapping is principal_id → hardcoded sf_user — won't scale beyond demo. Needs a Cognito attribute → Salesforce user mapping table.
- **Token lifetime**: Cognito default 1hr. Existing session HMAC logic needs to respect Cognito expiry.

### Recommendation
**High strategic value. Do this AFTER the P0 backend fixes from `v3-pending-mock-vs-real.md` close.** Keep the dev-bootstrap mode as an `&auth=dev` override for panel demos. Real auth is a boundary-1 promise that's been undefined-deferred twice now — time to cash it.

---

## 4. Langfuse Prompt Management

### What it means
Use Langfuse's prompt-management feature (versioning, A/B testing, hot-reload) instead of the hardcoded system prompts in `openclaw/orchestration/topology.py`.

### Current state

| Axis | Reality |
|---|---|
| Code | **Prompts are hardcoded Python strings in topology.py**. Each specialist has a ~500-word system prompt baked in. Zero references to `langfuse.prompts` or `PromptLabel`. |
| Deployed | Langfuse US cloud project exists and collects traces (cost + span capture). But **prompt management feature not used** — only tracing. |
| Design fit | **Good**. Swap `target.system_prompt` resolution from topology constants to `langfuse_client.get_prompt(name, version="production")` with local fallback to the hardcoded string. Hot-reload without container redeploy is a strong operational win. |
| Effort | **2-4 days**. Seed Langfuse with current 14 prompts. Add a `PromptResolver` in coordinator.py. Add cache + TTL. Handle the case where Langfuse is unreachable — fall back to hardcoded. |

### Risks
- **Tests**: unit tests depend on fixed prompts. Need to mock the resolver.
- **Audit trail**: prompt versions used in a turn should land in Langfuse trace tags for reproducibility.
- **Bedrock Converse with cached prompts**: Bedrock has its own prompt-cache feature. Using Langfuse's prompt-management doesn't conflict, but the stacking deserves thought.

### Recommendation
**Nice-to-have, not a demo blocker.** Strong for post-demo iteration (tweak compliance specialist prompt, A/B test, watch Langfuse dashboards). Worth 3 days in v4 or an iteration sprint.

---

## 5. UI two color modes — light and dark

### What it means
Add a light-mode/dark-mode toggle to v2 UI.

### Current state

| Axis | Reality |
|---|---|
| Code | **Per-surface, not per-mode**. v2 has three *surfaces* hardcoded per persona: Research = forensic dark, Advisor = SLDS light, Client = WhatsApp green. Not a user-toggleable theme — each persona has one fixed look. |
| Deployed | Current UI serves exactly that — persona-determined colors, not user-choice. |
| Design fit | **Requires design decision before code**. Does "light/dark" mean: (a) global system-wide light vs dark that overrides the three surface choices? (b) Add a light-mode variant of the research terminal only? (c) A different visual theme entirely? The uploaded UIUX design did NOT include light/dark toggle — it was explicit persona-surface-per-persona. |
| Effort | **2 days if just research light-mode + toggle**. **1 week if full system-wide theme engine** (tokens need to branch by `data-theme="light\|dark"` on `.v2-root`). |

### Risks
- **Brand/identity conflict**: forensic-dark IS part of Sarah's "terminal feel" identity. Losing it for a light mode may weaken the persona differentiation.
- **SLDS conflict**: SLDS has its own dark-mode system. Using it alongside our own theme tokens could produce inconsistent light/dark surfaces.
- **Accessibility is not what this is about** — both modes already pass contrast checks. This is a preference toggle, not an a11y fix.

### Recommendation
**Clarify the intent first.** If it's user-preference (night work), it's a 2-3 day nice-to-have. If it's brand flexibility (different customer visual), it's a full theming engine — 1+ week. Ask: "is Sarah on a dark terminal or does she get a choice?"

---

## 6. FSI Workforce 360

### What it means
The brand name. All user-facing strings + docs use "Workflow 360" today. User intent appears to be renaming to "FSI Workforce 360" across UI, docs, audit logs, branding.

### Current state

| Axis | Reality |
|---|---|
| Code | **Workflow 360 is baked in**. Brand mark = `W360Logo`. Header says "Workflow 360". `v2-tokens.css` has `--w360-brand-*` variables. Agent message in advisor conversation says "Workflow 360 · Advisor". |
| Deployed | Same — live bundle has "Workflow 360" everywhere. |
| Design fit | **Simple rename**. No architecture change. Just a find+replace across a known set of strings + SVG update. |
| Effort | **2-4 hours**. Files to change: `W360Logo.tsx` label (if rendering text), `PersonaHeaderV2.tsx` brand string, `v2-tokens.css` variable names (or leave `--w360-` as internal shorthand), `AdvisorWorkbenchV2.tsx` agent-message attribution, docs (`v3-frontend-*`, `RUNBOOK.md`). |

### Risks
- **External references**: is anything OUTSIDE the repo using "Workflow 360" (e.g. a brand partner deck)? Do those need to update simultaneously?
- **Logo**: "FSI Workforce 360" doesn't abbreviate to W360 — do you want a different mark? `W360Logo` SVG is a small circle + cross. The new name might warrant a different icon.
- **Audit log Agent_Id__c values**: if any persist strings include "Workflow 360" they'll be out of sync with the new name after rename (old audit rows keep old label — fine, but note the generation cutoff in docs).

### Recommendation
**Cheap, do it. 2-4 hours.** Batched with any CSS iteration. Clarify logo treatment separately.

---

## 7. Organize Client Architecture Map and Trace

### What it means
The client surface (Eleanor Vance's phone bezel) has the architecture map + timeline in the right column caption. Currently the TraversalMapV2 + TimelineV2 are stacked but not visually organised — map shows research-persona specialists when Sarah is not actually active; timeline shows... what? Needs layout cleanup.

### Current state

| Axis | Reality |
|---|---|
| Code | `ClientChannelV2.tsx` renders `<TraversalMapV2 fallbackPersona="fsi_client_liaison" />` and `<TimelineV2 persona="fsi_client_liaison" />` inside a `v2-client-tracestack` div. The map + timeline are side-by-side or stacked depending on `@media` breakpoints. |
| Deployed | Ships. |
| Design fit | The map is **correctly driven by the client persona**. But two known visual issues: (1) when Eleanor hasn't sent a message, the map has no active nodes and looks static — the "what am I looking at" question dominates the right panel. (2) The client persona has only 3 specialists (context, faq, handoff), so the fan-out looks sparse compared to research. |
| Effort | **1-2 days polish**. Options: (a) add a caption strip "Behind the scenes" with a one-liner explaining what the map represents. (b) move map+timeline to a collapsible `<details>` that's collapsed by default, reveal on click. (c) replace the full map with a simplified 3-node representation (client→liaison→RM) that's more legible at small size. |

### Risks
- **Losing the "one trust spine, three surfaces" payoff shot**: the whole point of having the map on the client surface is to show the same spine lights up here too. Collapsing it defeats that.
- **Bedrock Nova/voice integration would add a "voice" node** on the map — coordinate with item #1.

### Recommendation
**Do it as UX polish.** Lowest-cost option: add the caption text "Behind the scenes" + shrink the map to compact mode + add tooltip explanations. Don't remove it.

---

## 8. Live Architecture Map not clear

### What it means
Even on research + advisor surfaces, the live map is hard to parse. Nodes light up, edges animate, but **users can't tell what they're looking at without explanation**. It reads as decoration, not as diagnostic.

### Current state — what's wrong

| Issue | Evidence |
|---|---|
| **Too many nodes at once** | Full topology has 43 nodes (1 coord + 3 orch + 11 specialists + 13 skills + 5 MCPs + 7 gates + 3 trust). `TraversalMapV2` shows all 3 orchestrators always + fans out active persona + shows gate chain on advisor = ~20 visible nodes. Dense. |
| **No explanatory legend** | Legend shows 4 colors (dim/pulse/solid/error) but doesn't explain what "node kinds" mean. A user seeing a coordinator vs orchestrator vs specialist vs skill vs MCP has no way to tell which is which without training. |
| **Ghost spine edges unclear** | Dashed horizontal edges between orchestrators are meant to show "one graph, three personas". A user doesn't know that's what they mean. |
| **Only 3-4 specialist nodes pulse per turn** | And often only 1-2 gates fire (compliance). Whole swaths of the map never light up. User wonders "is that broken?" |
| **Edge states (dashed-flow animation) subtle** | Active edges use dashflow; dim edges are static. Visual distinction is present but low contrast. |
| **No hover tooltips** | Node click deep-links to Langfuse. Node hover should show agent detail (model tier, allowed tools, memory scope). Currently hovering does nothing. |
| **No progressive disclosure** | Always shows everything. No "show me just what fired this turn" mode. |

### Current state — axis scoring

| Axis | Reality |
|---|---|
| Code | Map is complex. `TraversalMapV2.tsx` is 619 lines (largest v2 atom). Layout logic is deterministic but the visual vocabulary isn't documented for users. |
| Deployed | Ships. |
| Design fit | The map's *purpose* is correct (show the trust spine lit up per turn). The execution is too maximalist. |
| Effort | **3-5 days for a real polish pass.** |

### What would fix it

Ranked by impact:

1. **Add hover tooltips** on every node showing: role, model tier, tools allowed, memory scope, last-firing timestamp. **2 hours.**
2. **Add a collapsible legend** with icon + text for each node kind (coordinator / orchestrator / specialist / skill / MCP / gate / trust). **3 hours.**
3. **Add a "this turn only" toggle** that hides nodes/edges that haven't fired. Default = everything visible, toggle to focus. **1 day.**
4. **Replace ghost-edge dashed lines with a clear visual: a subtle "trust spine" band behind the three orchestrators** that gets highlighted per turn. **1 day.**
5. **Animate "lit paths" on the active edges during a turn** — instead of just dashflow, show a colored pulse traversing the edge from source to target, like packets moving. **1-2 days.**
6. **Progressive disclosure**: on the advisor surface during a normal read-only turn, hide the gate chain. Only show gates when an action_write is in flight. **4 hours.**
7. **Add a caption below the map** that changes per-persona explaining what's happening: "Sarah's research query fans out to 4 specialists in parallel" / "Marcus's write path funnels through 7 sequential gates". **2 hours.**

### Recommendation

**This is the highest-leverage item on the list.** It's cheap, it's polish-only, it doesn't touch backend at all, and it's the single most likely moment in a demo where a panelist asks "wait, what's happening?"

**Budget 1 week for the full 7-item pass. Budget 1 day if only 1+2 (tooltips + legend).**

---

## Matrix summary

| # | Item | Effort | Strategic value | Demo blocker? | Recommended phase |
|---|---|---|---|---|---|
| 1 | Multi-modal AnalystVoice | 2-3 weeks | High | No | V5 — after backend P0 closes |
| 2 | AgentCore Memory | 1-2 weeks | High | No | V4 |
| 3 | Cognito auth | 3-5 days | High (enterprise credibility) | No (if dev-bootstrap stays as override) | V4 |
| 4 | Langfuse prompt management | 2-4 days | Operational win | No | V4 or iteration sprint |
| 5 | Light/dark mode | 2 days–1 week | Depends on scope | No | Needs design decision first |
| 6 | FSI Workforce 360 rename | 2-4 hours | Branding only | No | Immediate, batch with CSS work |
| 7 | Organize client map+trace | 1-2 days | UX polish | No | Batch with #8 |
| 8 | **Live Architecture Map clarity** | **3-5 days** | **Very high (core demo moment)** | **Yes — this is the "is anything real?" moment** | **Before next demo** |

---

## What I'd do first (if I were you)

1. **Close P0 backend gaps** from `v3-pending-mock-vs-real.md` (audit, Published_At, Research_Request 401, source_chunk stub, research specialist tool-use). ~4-6 hours. These are all "mockery drama" risks.
2. **Item 8 — architecture map polish** (1-2 days minimum; tooltips + legend at a minimum). Single biggest demo-credibility lever.
3. **Item 6 — rename to FSI Workforce 360** while I'm in the v2 CSS files anyway.
4. **Item 3 — Cognito** as the next major item after that. Auth boundary has been hand-waved long enough.
5. Items 1, 2, 4, 5, 7 get sequenced into V4/V5.

Items 1 and 2 are architecturally clean but have significant surface area. They deserve their own design passes, not retrofits.
