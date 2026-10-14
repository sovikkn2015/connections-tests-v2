# Independent Evaluation Scenario Assessment — 006 V3 (Strictest Judge)

**Assessor:** Independent AI reviewer (not the builder)  
**Date:** 2026-05-02  
**Scope:** All 62 scenarios from `scripts/eval-scenarios.json`  
**Backend:** openclaw orchestration (Python, Bedrock Converse, MCP)  
**Frontend:** src/v6 (React, Playwright E2E)  
**Last eval run:** `eval-results-20260502T064758.json` — 61 PASS, 1 SKIP

---

## EXECUTIVE VERDICT

**The eval runner reports 61/62 PASS. This is deeply misleading.**

The system is architecturally sophisticated — real orchestrators, real Bedrock Converse calls, real deterministic compliance logic. But the "PASS" verdicts hide massive mock/fallback paths that make most tests prove "didn't crash" rather than "exercised the claimed integration end-to-end."

### Critical Fakery Summary

| # | What's Faked | Where | Impact |
|---|-------------|-------|--------|
| 1 | **MCP tool calls** default to `MockMCPRouter` with canned JSON | `_mcp_client.py:get_shared_mock_client()` | All market data, filings, news, CRM reads may be fake |
| 2 | **Salesforce writes** silently degrade to hash-based fake IDs | `rm_handoff`, `audit_logging`, `publish_brief` | Every SObject "write" may be a no-op |
| 3 | **Gates 4-7 never execute** in eval | `advisor_orchestrator.py` DRAFT_ONLY mode | HITL, dual_auth, MuleSoft, audit never tested |
| 4 | **Memory is unimplemented** | No memory store anywhere in codebase | M01/M02 are fake passes |
| 5 | **Multimodal is unimplemented** | No PDF/image processing code | R13 is a fake pass |
| 6 | **RAG citations may be hallucinated** | KB retrieval goes through mock MCP | R09/R10 citations unverifiable |
| 7 | **Queue updates are ephemeral JSON** | Never persisted to any store | Liaison escalations vanish after response |
| 8 | **Frontend E2E tests verify UI shell only** | No content/correctness assertions | 44 "passes" prove rendering, not function |

---

## FULL SCENARIO TABLE

### Legend

| Symbol | Meaning |
|--------|---------|
| ✅ REAL | Genuinely exercises the claimed capability with real logic |
| ⚠️ CONDITIONAL | Real IF environment variables are configured; mock otherwise |
| 🟡 PARTIAL | Some logic is real but key parts are mocked/skipped |
| 🔴 FAKE PASS | Test "passes" but does NOT verify the claimed capability |
| 🔴 SUSPECT | Cannot confirm the claimed behavior actually occurred |
| ⏭️ SKIP | Intentionally skipped |

---

## PERSONA 1: Sarah Chen — FSI Research Analyst (19 scenarios)

### Narrative: Multi-specialist parallel research with cited briefs

