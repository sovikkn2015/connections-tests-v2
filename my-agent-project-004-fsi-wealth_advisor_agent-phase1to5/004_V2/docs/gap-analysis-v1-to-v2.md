# Gap Analysis: 004 V1 → V2

## Summary

Project 004 has extensive documentation (12 docs, 5 phases) but significant gaps between what's documented and what's actually implemented and working. The deployment-status.md is the most honest document — it clearly tracks what's deployed vs pending.

## Critical Gaps (Blocking Functionality)

### GAP-1: MCP Market Data & News — Apex Classes Exist But Not Wired to Agent
- **Doc says**: Phase 3 adds market_data and market_news topics
- **Reality**: `DC_MarketDataAction.cls` and `DC_NewsSearchAction.cls` are deployed to the org, but the agent script (`WA_P1to5_Advisor.agent`) only has 10 topics — market_data and market_news topics are NOT in the agent bundle
- **Impact**: Queries like "What's the S&P 500?" or "Any news about Apple?" go to off_topic or client_lookup instead of the market/news actions
- **Fix**: Add market_data and market_news topics to the .agent file, redeploy

### GAP-2: Audit Logging Not Wired Into Actions
- **Doc says**: Phase 5B — every agent interaction logged to WA_Audit_Log__c
- **Reality**: `DC_AuditLogAction.cls` exists and is deployed, but NONE of the 8 DC_* action classes actually call it. The audit log table is empty.
- **Impact**: Zero compliance trail. The audit infrastructure exists but isn't connected.
- **Fix**: Add `DC_AuditLogAction.logInteraction(...)` call to each DC_* class

### GAP-3: Knowledge Articles Not Published
- **Doc says**: Phase 5A — 5 FSI knowledge articles for RAG
- **Reality**: Articles were created as drafts but never published. Knowledge search returns nothing.
- **Impact**: "What's our margin policy?" returns no results
- **Fix**: Publish articles via Knowledge tab (UI-only) or Apex script

### GAP-4: Data Cloud Streams Missing for New Objects
- **Doc says**: WA_Transaction__c and WA_Referral__c synced to Data Cloud
- **Reality**: Streams not created. Transaction History and Referral Tracking topics fail with "No data found"
- **Impact**: 2 of 10 topics are broken
- **Fix**: Create Data Cloud streams (UI-only)

## Structural Gaps (Design vs Implementation)

### GAP-5: Agent Script Missing 2 Topics
- **Doc says**: 12 topics (10 original + market_data + market_news)
- **Reality**: Agent script has 10 topics. market_data and market_news are documented but not in the .agent file
- **Impact**: Agent can't handle market/news queries through the Agentforce routing

### GAP-6: RBAC Not Enforced
- **Doc says**: Phase 5C — OWD Private, sharing rules, advisor-to-client assignment
- **Reality**: 3 permission sets deployed but OWD is still Public. No sharing rules. No advisor assignment. All users see all data.
- **Impact**: No data isolation between advisors. Acceptable for dev, not for production.

### GAP-7: Experience Cloud Chat Widget Not Working
- **Doc says**: Phase 4 — Embedded Service chat widget on Experience Cloud portal
- **Reality**: Site exists, AI Experiences configured, but chat widget doesn't render. ESW deployment points to its own auto-generated site, not the portal.
- **Impact**: The primary deployment channel (web chat) doesn't work
- **Workaround**: VF Workbench page (`/apex/WA_Workbench`) works as alternative

### GAP-8: No Actual Performance Test Results
- **Doc says**: Phase 5D — k6 load tests, Apex perf tests, SLA validation
- **Reality**: Test scripts documented but never executed. No baseline metrics exist.
- **Impact**: No performance data for production readiness assessment

### GAP-9: LLM-as-Judge Not Executed
- **Doc says**: 32 golden answers, judge prompt template, batch eval script
- **Reality**: Framework documented but never run against live agent
- **Impact**: No quality scores for agent responses

## UI/UX Gaps

### GAP-10: VF Workbench Created But Not Documented
- **Reality**: WA_Workbench.page exists and works at `/apex/WA_Workbench` but README doesn't mention it
- **Fix**: Add to README as a deployment option

### GAP-11: React Frontend Not Documented in README
- **Reality**: `frontend/` directory exists with a full React app but README doesn't reference it
- **Fix**: Add frontend section to README

## File Organization Gaps

### GAP-12: Stale Retrieved Metadata in Project Root
- **Reality**: `esw-retrieve/` directory contains retrieved ExperienceBundle metadata that shouldn't be in the project
- **Fix**: Add to .gitignore or delete

### GAP-13: No Subfolder Organization for Apex Classes
- **Reality**: All 12 Apex classes in a flat `classes/` directory with no grouping
- **Impact**: Hard to tell which classes belong to which phase

### GAP-14: WA_WorkbenchController Not in grant-permissions.apex
- **Reality**: The new VF controller needs Apex class access granted to users
- **Fix**: Add to grant-permissions script

## V2 Action Plan

| Priority | Gap | Action | Effort |
|----------|-----|--------|--------|
| P0 | GAP-1 | Wire market_data + market_news topics into agent script | Small |
| P0 | GAP-2 | Add audit logging calls to all 8 DC_* actions | Medium |
| P0 | GAP-5 | Update agent script to 12 topics | Small |
| P0 | GAP-14 | Add WA_WorkbenchController to permissions | Small |
| P1 | GAP-10,11 | Update README with VF Workbench + React frontend docs | Small |
| P1 | GAP-12 | Clean up stale files, organize project structure | Small |
| P2 | GAP-3 | Publish knowledge articles (UI-only) | Manual |
| P2 | GAP-4 | Create Data Cloud streams (UI-only) | Manual |
| P2 | GAP-7 | Document VF Workbench as primary UI, deprioritize ESW chat | Doc |
| P3 | GAP-6 | RBAC enforcement (production concern) | Large |
| P3 | GAP-8 | Run performance tests | Medium |
| P3 | GAP-9 | Run LLM-as-Judge evaluation | Medium |
