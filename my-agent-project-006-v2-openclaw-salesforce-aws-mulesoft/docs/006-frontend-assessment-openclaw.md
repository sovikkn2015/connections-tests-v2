# 006 Frontend Assessment: Reusing 005 V2 UI with OpenClaw

> Assessment date: April 8, 2026

---

## 1. What 005 V2 Built (Baseline)

The 005 V2 frontend is a React + TypeScript SPA (Vite, Zustand, Recharts, SLDS) that serves as an **Investment Research Workbench**. It connects to Salesforce as the backend.

### UI Components

| Component | What It Does |
|-----------|-------------|
| GlobalHeader | Blue SF-style header bar, user avatar, sign-out |
| ChatPanel | Left 40% — conversational interface with streaming responses, sample query pills |
| ResearchPanel | Right 60% — tabbed research output (Company, Coverage, Analysis, Filings) |
| CompanyCard | Price header, 8-metric grid, 52-week range bar, moving averages, sentiment badge, earnings countdown |
| CoverageTable | Consensus distribution bar (Buy/Hold/Sell), target-price range visual, analyst table with rating/action badges |
| FinancialChart | Metric-toggle chart (Revenue/Margins/EPS/FCF via Recharts), DCF fair value card, Monte Carlo range bar, peer comparison table |
| TracePanel | Bottom collapsible — Langfuse link for observability |
| LoginButton | SF OAuth2 PKCE login |
| SampleQueries | Quick-action pill buttons for common queries |

### Tech Stack

| Layer | Technology |
|-------|-----------|
| Framework | React 19 + TypeScript |
| Build | Vite 6 |
| State | Zustand 5 |
| Charts | Recharts 2.15 |
| Design System | Salesforce Lightning Design System (SLDS) 2.25 |
| Auth | Salesforce OAuth2 PKCE (via `react-oauth2-code-pkce`) |
| Hosting | S3 + CloudFront |

### Backend Connection (005 V2)

The frontend connects to **two backends** with automatic fallback:

1. **Salesforce Agent API** (`api.salesforce.com/einstein/ai-agent/v1`) — real Agentforce sessions with SSE streaming
2. **Apex Invocable Actions fallback** (`/services/data/v66.0/actions/custom/apex/{ActionName}`) — direct REST calls to 10 Apex actions, with simulated streaming (word-by-word chunking)

Key patterns:
- `startSession()` → creates Agent API session or synthetic fallback session
- `sendStreamingMessage()` → SSE streaming (Agent API) or chunked simulation (Apex)
- `routeMessage()` → keyword-based intent routing to specific Apex actions
- Auth token flows through Zustand store → every API call
- `responseParser.ts` → extracts tickers from chat, auto-loads seed data, detects relevant tab

### Data Flow

```
User types query
  → ChatPanel.handleSend()
  → extractTickers() → loadTickerData() (hydrates research panel from seed data)
  → agentApi.sendStreamingMessage()
    → Agent API SSE stream OR Apex action + simulated stream
  → onChunk() updates Zustand → ChatPanel re-renders incrementally
  → Research panel shows structured data for detected ticker
```

---

## 2. OpenClaw's API Surface (What 006 Offers)

OpenClaw exposes a **Gateway API** on port 18789 with two transport mechanisms:

### WebSocket (Primary — Real-Time)

| Method | Purpose |
|--------|---------|
| `agent` | Send message, get streamed response |
| `agent.wait` | Wait for run completion |
| `agent.abort` | Cancel in-progress run |
| `agent.identity.get` | Get agent metadata |
| `agents.list` | List all configured agents |

Streaming events arrive as WebSocket frames:
- `stream: "assistant"` → text chunks (equivalent to SSE `data:` in 005)
- `stream: "tool"` → tool invocations (start, result, error) — **new capability vs 005**
- `stream: "lifecycle"` → execution phases (start, thinking, end, error)

### REST (Secondary)

| Endpoint | Purpose |
|----------|---------|
| `/v1/chat/completions` | OpenAI-compatible chat |
| `/v1/responses` | OpenResponses API (OpenAI Responses API compatible) |
| `/hooks/*` | Webhook endpoints |
| `/api/tools/invoke` | HTTP tool invocation |
| `/api/channels/*` | Channel-specific endpoints |

### OpenResponses API (Custom Backend Pattern)

OpenClaw can also call an external backend via `POST /v1/responses` — meaning the AutoResearchClaw pipeline (or any agent) can be exposed as an OpenClaw backend. The frontend doesn't need to know about this; it talks to OpenClaw, OpenClaw routes to the pipeline.

### Authentication

Bearer token authentication on all requests. Rate-limited (20 failed attempts / 60s window).

---

## 3. Compatibility Assessment: 005 UI → 006 OpenClaw

### 3.1 What Maps Directly (Reusable As-Is)

| 005 V2 Component | 006 Reuse | Notes |
|-------------------|-----------|-------|
| GlobalHeader | ✅ Rename to "FSI Research Workbench" | Cosmetic change only |
| ChatPanel | ✅ Core chat UX identical | Message list, input, streaming — same pattern |
| ResearchPanel | ✅ All tabs reusable | Company, Coverage, Analysis, Filings — data-driven, backend-agnostic |
| CompanyCard | ✅ No changes needed | Renders from `CompanyData` type — source doesn't matter |
| CoverageTable | ✅ No changes needed | Renders from `CoverageData[]` + `ConsensusSummary` |
| FinancialChart | ✅ No changes needed | Recharts renders from `ChartDataPoint[]` + `ValuationData` |
| TracePanel | ✅ Already points to Langfuse | Same observability stack in 006 |
| SampleQueries | ✅ Update query text for 006 use cases | Different sample queries (pipeline-oriented) |
| Zustand store | ✅ State shape unchanged | Research data types are backend-agnostic |
| Types (index.ts) | ✅ All types reusable | `CompanyData`, `CoverageData`, `ChartDataPoint`, etc. |
| responseParser.ts | ✅ Ticker extraction, tab detection | Works on any text response |
| SLDS styling | ✅ No changes | Design system is backend-independent |

### 3.2 What Must Change (agentApi.ts + authService.ts)

These two files are the **only hard coupling** to Salesforce as backend. Everything else is data-driven.

#### Auth: Salesforce OAuth2 PKCE → OpenClaw Bearer Token

| Aspect | 005 V2 (Salesforce) | 006 (OpenClaw) |
|--------|---------------------|----------------|
| Auth flow | OAuth2 PKCE via SF login page | Bearer token (pre-configured or SF OAuth2 PKCE for CRM access) |
| Token source | SF Connected App | OpenClaw Gateway config |
| User info | SF `/services/oauth2/userinfo` | OpenClaw `agent.identity.get` or SF userinfo (if SF auth retained) |
| Token storage | Session storage (via react-oauth2-code-pkce) | Session storage (same) |

**Decision point:** 006 still needs Salesforce for CRM data (audit logs, research notes, client data). Three options:

- **Option A: Dual auth** — SF OAuth2 PKCE for CRM identity + OpenClaw Bearer token for agent. Frontend authenticates with SF first (same as 005), then uses a separate token for OpenClaw Gateway. More complex but preserves SF identity for audit trail.
- **Option B: SF auth → OpenClaw proxy** — Frontend authenticates with SF (same as 005). OpenClaw's `salesforce-api` skill already has its own OAuth connection to SF. The frontend sends the SF access token to OpenClaw, which validates the user identity and proxies CRM calls. Simpler frontend, but requires OpenClaw to trust the SF token.
- **Option C: OpenClaw-only auth** — Drop SF login entirely. OpenClaw handles auth via its own Bearer token. CRM access happens server-side only (OpenClaw → SF via skill). Simplest frontend, but loses SF user identity in the UI.

**Recommendation: Option A (dual auth)** — keeps SF identity for FINRA audit trail (who asked what), adds OpenClaw token for agent communication. The `authService.ts` changes are minimal: add a second token fetch for OpenClaw alongside the existing SF PKCE flow.

#### Agent API: Salesforce Agent API → OpenClaw WebSocket

This is the core change. The entire `agentApi.ts` must be rewritten.

| Aspect | 005 V2 (Salesforce) | 006 (OpenClaw) |
|--------|---------------------|----------------|
| Transport | HTTP (REST + SSE) | WebSocket (primary) + REST fallback |
| Session model | `POST /agents/{id}/sessions` → sessionId | WebSocket `connect` → persistent connection, `sessionKey` per user |
| Send message | `POST /sessions/{id}/messages/stream` (SSE) | WebSocket `agent` method with `sessionKey` |
| Streaming | SSE `data:` lines parsed manually | WebSocket `event: "agent"` frames with `stream` field |
| Tool visibility | None — agent responses are opaque | Full tool invocation events (`stream: "tool"`) — **new** |
| Abort | `DELETE /sessions/{id}` | WebSocket `agent.abort` with `runId` |
| Fallback | Apex Invocable Actions (keyword routing) | REST `/v1/chat/completions` or `/v1/responses` |

**New `openclawApi.ts` structure:**

```typescript
// Connection
connectWebSocket(gatewayUrl: string, token: string): WebSocket
authenticate(ws: WebSocket, token: string): Promise<void>

// Agent interaction
sendMessage(ws: WebSocket, message: string, sessionKey: string): string  // returns runId
onStream(ws: WebSocket, callback: StreamCallback): void  // handles assistant + tool + lifecycle
abortRun(ws: WebSocket, runId: string): Promise<void>

// Agent metadata
getAgentIdentity(ws: WebSocket, agentId?: string): Promise<AgentIdentity>
listAgents(ws: WebSocket): Promise<Agent[]>

// Types
interface StreamCallback {
  onText: (chunk: string) => void;
  onToolStart: (name: string, input: unknown) => void;
  onToolResult: (name: string, result: unknown) => void;
  onLifecycle: (phase: 'start' | 'thinking' | 'end' | 'error') => void;
}
```

### 3.3 What's New in 006 (Additions to 005 UI)

OpenClaw's architecture enables features that 005 couldn't offer:

#### A. Pipeline Stage Tracker (New Component)

AutoResearchClaw runs 23 stages. The `stream: "tool"` events expose every stage transition. 005 had no visibility into what the agent was doing internally.

```
New component: PipelineTracker
  - Shows current stage (1-23) with progress bar
  - Stage names: Scoping → Data Collection → Synthesis → ... → Publish
  - HITL gates highlighted (stages 5, 8, 9, 17, 20)
  - Approve/Reject/Collaborate buttons at gate stages
  - Estimated time remaining
  - Data source: OpenClaw WebSocket `stream: "tool"` events
```

#### B. HITL Approval Panel (New Component)

005 had no human-in-the-loop. 006's pipeline pauses at 5 gates requiring analyst input.

```
New component: HitlPanel
  - Renders when pipeline hits a gate stage
  - Shows: what the pipeline produced so far, what it's asking for
  - Actions: Approve, Reject, Edit (co-pilot mode), Add Context
  - Sends approval back via WebSocket `agent` method
  - Integrates with Slack notifications (OpenClaw handles this server-side)
```

#### C. Tool Execution Timeline (Enhanced TracePanel)

005's TracePanel was just a Langfuse link. OpenClaw streams tool invocations in real-time.

```
Enhanced TracePanel:
  - Real-time tool execution log (not just a link)
  - Shows: tool name, input, output, duration, status
  - Expandable details for each tool call
  - Links to Langfuse trace for full observability
  - Data source: OpenClaw WebSocket `stream: "tool"` events
```

#### D. Multi-Agent Selector (New Component)

OpenClaw supports multiple agents (`agents.list`). 006 could expose agent selection.

```
New component: AgentSelector (optional)
  - Dropdown in header: "Research Agent" | "Compliance Agent" | "Meeting Prep"
  - Calls `agents.list` on connect
  - Switches `agentId` in `agent` method params
```

#### E. Research Brief Viewer (New Component)

006 produces full research briefs (rating, target price, thesis, catalysts, risks, valuation). 005 showed raw chat text.

```
New component: BriefViewer
  - Structured display of completed research brief
  - Sections: Executive Summary, Thesis, Catalysts, Risks, Valuation, Recommendation
  - PDF export button
  - "Publish to Salesforce" button (triggers OpenClaw skill)
  - Data source: parsed from final pipeline output
```

---

## 4. Architecture: How the 006 Frontend Connects

```
┌─────────────────────────────────────────────────────────────────────────┐
│  BROWSER (React SPA on S3 + CloudFront)                                 │
│                                                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────────┐  │
│  │ Auth Layer   │  │ Chat + HITL  │  │ Research Panels              │  │
│  │              │  │              │  │                              │  │
│  │ SF OAuth2    │  │ ChatPanel    │  │ CompanyCard                  │  │
│  │ PKCE         │  │ HitlPanel   │  │ CoverageTable                │  │
│  │ (identity)   │  │ PipelineTrack│  │ FinancialChart               │  │
│  │              │  │              │  │ BriefViewer                  │  │
│  │ OpenClaw     │  │ AgentSelector│  │ FilingsList                  │  │
│  │ Bearer Token │  │              │  │                              │  │
│  │ (agent)      │  │              │  │                              │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────────────────────────┘  │
│         │                 │                                             │
│         │    Zustand Store (single source of truth)                     │
│         │    ┌─────────────────────────────────────┐                   │
│         │    │ auth: { sfToken, ocToken, userInfo } │                   │
│         │    │ agent: { ws, runId, sessionKey }     │                   │
│         │    │ chat: { messages[] }                  │                   │
│         │    │ pipeline: { stage, gates[], status }  │                   │
│         │    │ research: { company, coverage, ... }  │                   │
│         │    └─────────────────────────────────────┘                   │
│         │                 │                                             │
└─────────┼─────────────────┼─────────────────────────────────────────────┘
          │                 │
          │                 │ WebSocket (wss://)
          │                 ▼
          │    ┌──────────────────────────────────────┐
          │    │ OpenClaw Gateway (AgentCore)          │
          │    │ ws://gateway:18789                    │
          │    │                                      │
          │    │ connect → auth (Bearer token)        │
          │    │ agent → send message, get stream     │
          │    │ agent.abort → cancel run             │
          │    │                                      │
          │    │ Events:                              │
          │    │   stream: "assistant" → chat text    │
          │    │   stream: "tool" → pipeline stages   │
          │    │   stream: "lifecycle" → start/end    │
          │    └──────────────┬───────────────────────┘
          │                   │
          │                   ▼
          │    ┌──────────────────────────────────────┐
          │    │ OpenClaw Agent (Orchestrator)         │
          │    │ → Intent Router                      │
          │    │ → SF CRM Skill (SOQL, CRUD)          │
          │    │ → MCP Servers (SEC, Market, News)    │
          │    │ → AutoResearchClaw Pipeline           │
          │    │ → Financial Analysis Skills           │
          │    └──────────────────────────────────────┘
          │
          │ SF OAuth2 PKCE (for user identity only)
          ▼
     ┌──────────────────────────────────────┐
     │ Salesforce (login.salesforce.com)     │
     │ /services/oauth2/authorize            │
     │ /services/oauth2/userinfo             │
     │                                      │
     │ (CRM access happens server-side      │
     │  via OpenClaw salesforce-api skill)   │
     └──────────────────────────────────────┘
```

---

## 5. What Changes, What Stays — File-by-File

| File | Change | Effort |
|------|--------|--------|
| `App.tsx` | Add OpenClaw WebSocket connection after SF auth | Small |
| `authService.ts` | Keep SF PKCE, add OpenClaw token config | Small |
| `agentApi.ts` | **Rewrite entirely** → `openclawApi.ts` (WebSocket) | Medium |
| `agentStore.ts` | Add pipeline state, HITL state, WebSocket ref | Medium |
| `types/index.ts` | Add `PipelineStage`, `HitlGate`, `ToolEvent`, `BriefData` types | Small |
| `responseParser.ts` | Keep ticker extraction, add pipeline output parser | Small |
| `Layout.tsx` | Add PipelineTracker slot, adjust panel ratios | Small |
| `ChatPanel.tsx` | Minor — add HITL inline prompts | Small |
| `ResearchPanel.tsx` | Add "Brief" tab | Small |
| `CompanyCard.tsx` | No change | None |
| `CoverageTable.tsx` | No change | None |
| `FinancialChart.tsx` | No change | None |
| `GlobalHeader.tsx` | Rename, add AgentSelector dropdown | Small |
| `TracePanel.tsx` | Enhance with real-time tool events | Medium |
| `SampleQueries.tsx` | Update sample queries for 006 | Trivial |
| **New: PipelineTracker.tsx** | 23-stage progress visualization | Medium |
| **New: HitlPanel.tsx** | Approval/reject/collaborate UI | Medium |
| **New: BriefViewer.tsx** | Structured research brief display | Medium |
| **New: AgentSelector.tsx** | Multi-agent dropdown | Small |
| `seedData.ts` | Update for 006 companies/tickers | Trivial |
| `package.json` | No new dependencies needed | None |

---

## 6. Key Technical Decisions

### 6.1 WebSocket vs REST for Agent Communication

**Use WebSocket.** OpenClaw's primary protocol is WebSocket. It provides:
- Real-time bidirectional streaming (no SSE parsing hacks)
- Tool invocation visibility (impossible with REST)
- Pipeline stage tracking (lifecycle events)
- Connection persistence (no session management overhead)
- Abort capability (instant, not HTTP DELETE)

REST (`/v1/chat/completions`) is the fallback if WebSocket fails, but it loses tool visibility and pipeline tracking.

### 6.2 Seed Data vs Live Data

005 V2 used `seedData.ts` to hydrate the research panel immediately when a ticker is mentioned. This was necessary because Apex actions return text, not structured data.

In 006, OpenClaw's tool events expose structured data from MCP servers and skills. The frontend can parse tool results directly:

```
stream: "tool" → phase: "result" → name: "get_quote" → result: { price: 135.40, ... }
```

**Recommendation:** Keep seed data as instant fallback (same UX), but progressively replace with live data from tool events as they arrive. This gives the user immediate visual feedback while the agent works.

### 6.3 HITL Implementation

OpenClaw's HITL co-pilot pauses the pipeline and sends a message to the user's channel. In the web frontend:

1. Pipeline hits gate stage → OpenClaw sends a `stream: "lifecycle"` event with `phase: "thinking"` (or a custom HITL event)
2. Frontend renders HitlPanel with the gate context
3. User approves/rejects/edits
4. Frontend sends approval back via `agent` method with a structured response
5. Pipeline resumes

This is the biggest UX difference from 005. The chat becomes interactive at gate stages — not just Q&A, but collaborative decision-making.

### 6.4 Auth Token Flow

```
1. User clicks "Sign In" → SF OAuth2 PKCE flow (same as 005)
2. SF returns access_token + instance_url + user_info
3. Frontend stores SF token in Zustand (for identity display)
4. Frontend opens WebSocket to OpenClaw Gateway
5. Authenticates with OpenClaw Bearer token (from env config)
6. All agent communication goes through WebSocket
7. CRM reads/writes happen server-side (OpenClaw → SF via skill)
8. SF token is NOT sent to OpenClaw (separation of concerns)
```

### 6.5 Deployment

Same as 005: `vite build` → S3 + CloudFront. No changes to hosting.

OpenClaw Gateway needs to be accessible from the browser (WebSocket). On AgentCore, this means:
- API Gateway WebSocket API in front of AgentCore
- Or: ALB with WebSocket support → AgentCore container
- TLS termination at the load balancer (wss://)
- CORS: allow CloudFront origin

---

## 7. Effort Estimate

| Category | Files | Days |
|----------|-------|------|
| OpenClaw API layer (`openclawApi.ts` + WebSocket) | 1 | 2 |
| Auth updates (dual auth) | 2 | 1 |
| Store updates (pipeline + HITL state) | 2 | 1 |
| New components (PipelineTracker, HitlPanel, BriefViewer, AgentSelector) | 4 | 3 |
| Enhanced TracePanel (real-time tool events) | 1 | 1 |
| Minor updates (Layout, ChatPanel, ResearchPanel, GlobalHeader, SampleQueries) | 5 | 1 |
| Types + parsers | 2 | 0.5 |
| Testing + integration | — | 2 |
| **Total** | **~17 files** | **~11.5 days** |

For context, 005 V2 frontend was ~15 files. 006 adds ~4 new components and rewrites 1 file (`agentApi.ts` → `openclawApi.ts`). Everything else is incremental.

---

## 8. Verdict

The 005 V2 frontend is **highly reusable** for 006. The UI components (CompanyCard, CoverageTable, FinancialChart, FilingsList) are completely backend-agnostic — they render from typed data in Zustand, and they don't care whether that data came from Salesforce Apex actions or OpenClaw tool events.

The only hard coupling is in two files: `agentApi.ts` (Salesforce Agent API / Apex fallback) and `authService.ts` (SF OAuth2 PKCE). The agent API file gets rewritten to use OpenClaw's WebSocket protocol. The auth file gets a small addition for the OpenClaw Bearer token.

The real win is what OpenClaw **adds**: tool invocation visibility, pipeline stage tracking, and HITL gates. These are new UI capabilities that 005 couldn't offer because Salesforce's Agent API treats the agent as a black box. OpenClaw's WebSocket streaming exposes the agent's reasoning process, which enables PipelineTracker, HitlPanel, and a real-time TracePanel — features that make the 006 frontend significantly more powerful than 005.

**Bottom line:** ~70% reuse from 005 V2, ~30% new (OpenClaw API layer + pipeline/HITL components). No new dependencies. Same hosting. ~11.5 days of frontend work, fitting cleanly into Phase 5 of the 006 build plan.
