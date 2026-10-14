# 004 UI/UX Decision: Salesforce vs AWS (S3 + CloudFront)

## The Problem

Project 004 currently has **three UI options**, and none of them work well:

| UI Option | Status | Problem |
|-----------|--------|---------|
| VF Workbench (`/apex/WA_Workbench`) | Broken | `WA_WorkbenchController` not granted to users; Visualforce Remoting is a dead-end technology |
| Experience Cloud chat widget | Broken | Widget not rendering despite CORS/CSP deployed; requires 6+ manual UI config steps |
| React frontend (`frontend/`) | Built but not deployed | Connects to Salesforce Agent API (SSE) — never been hosted anywhere |

Meanwhile, 005 and 006 have a working React SPA on **S3 + CloudFront** that looks professional and works reliably.

---

## Decision: Deploy 004 React Frontend to S3 + CloudFront

**Abandon the Salesforce-native UI. Deploy the existing React frontend to AWS like 005/006.**

---

## Why

### Salesforce UI is a dead end for 004

1. **VF Workbench** — Visualforce Remoting (`invokeAction`) is legacy tech. No streaming, no real-time updates, no modern UX. Even if you fix the permission gap, you get a 2015-era chat box with inline CSS and `<apex:page>` rendering. Not demo-worthy.

2. **Experience Cloud chat widget** — Requires 6 manual UI steps (Experience Builder branding, AI Experiences config, publish). The widget is a small floating bubble — not a workbench. It's designed for customer support, not for a wealth advisor doing portfolio reviews with structured data panels.

3. **Both Salesforce options** are constrained by Salesforce's rendering pipeline. You can't control the layout, can't add Recharts visualizations, can't show structured advisor panels (Clients/Portfolio/Goals/Activity tabs), and can't do real streaming.

### The React frontend already exists and is good

004 already has a React frontend in `frontend/` with:
- React 19 + TypeScript + Vite 6 + Zustand 5 + Recharts + SLDS
- ChatPanel (left 40%) + AdvisorPanel (right 60%) + TracePanel (bottom)
- SF OAuth2 PKCE authentication
- Agent API with SSE streaming + Apex fallback
- SLDS styling (looks like Salesforce, runs on AWS)

This is the **same tech stack** as 005/006. It just needs hosting.

### 005/006 prove the pattern works

| Aspect | 005/006 (proven) | 004 (proposed) |
|--------|-----------------|----------------|
| Tech stack | React 19 + Vite + SLDS + Zustand | Same (already built) |
| Hosting | S3 + CloudFront | Same |
| Auth | SF OAuth2 PKCE | Same (already wired) |
| Backend | SF Agent API + Apex fallback | Same (already wired) |
| Deploy | `npm run build` → S3 sync → CF invalidate | Same |

---

## What Changes

### Keep as-is
- All Salesforce metadata (objects, Apex classes, agent script, Data Cloud)
- The agent itself (WA_P1to5_Advisor) — unchanged
- SF OAuth2 PKCE flow in the React app — unchanged
- `agentApi.ts` (Agent API + Apex fallback) — unchanged

### Add
- **SAM template resources** for S3 bucket + CloudFront distribution (copy from 005)
- **`scripts/deploy-frontend.sh`** — builds React app, syncs to S3, invalidates CF cache
- **SF Connected App update** — add CloudFront callback URL alongside localhost
- **`.env` configuration** — `VITE_SF_CLIENT_ID`, `VITE_SF_REDIRECT_URI` (CloudFront URL)

### Remove (optional cleanup)
- VF Workbench page (`WA_Workbench.page`, `WA_WorkbenchController.cls`) — dead code
- Experience Cloud CORS/CSP configs — no longer needed if not using the portal

---

## Effort Estimate

| Task | Time | Notes |
|------|------|-------|
| Add S3 + CloudFront to SAM template | 1 hour | Copy from 005's `sam-template.yaml` |
| Create `deploy-frontend.sh` script | 30 min | Copy from 005, update stack name |
| Update Connected App callback URLs | 15 min | Add CloudFront domain |
| Configure `.env` with real values | 15 min | Client ID, redirect URI, agent ID |
| Test end-to-end (build → deploy → login → query) | 1 hour | Verify OAuth + Agent API + Apex fallback |
| **Total** | **~3 hours** | |

---

## What About 006 (Future)?

When 004 eventually migrates to the 006 architecture (OpenClaw on AgentCore), the frontend change is minimal:

- Replace `agentApi.ts` (Salesforce Agent API) → `openclawApi.ts` (WebSocket)
- Add OpenClaw Bearer token alongside SF OAuth2 PKCE
- Add PipelineTracker, HitlPanel components (006-specific)

The 006 frontend assessment already documents this migration path. The React components (ChatPanel, AdvisorPanel, TracePanel, etc.) are backend-agnostic — they render from Zustand state, not from API-specific types. Moving to 006 later is a ~2-day frontend change, not a rewrite.

---

## Summary

| | Salesforce UI (current) | S3 + CloudFront (proposed) |
|---|---|---|
| Works today | No | Yes (005/006 prove it) |
| Modern UX | No (VF/Experience Cloud) | Yes (React + SLDS) |
| Structured panels | No | Yes (Clients/Portfolio/Goals/Activity) |
| Streaming | No (VF Remoting is sync) | Yes (SSE + simulated) |
| Charts/visualizations | No | Yes (Recharts) |
| Demo-worthy | No | Yes |
| Effort to deploy | Debugging broken SF UI (unknown hours) | ~3 hours (proven path) |
| 006 migration path | Rewrite | Swap `agentApi.ts` → `openclawApi.ts` |

**Stop fighting Salesforce's UI limitations. The React app is built. Put it on CloudFront.**
