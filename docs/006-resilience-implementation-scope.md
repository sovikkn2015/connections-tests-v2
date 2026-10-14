# 006 Resilience Implementation Scope — Code Change Estimate

> Date: April 22, 2026
> Scope: Exact files, line counts, and changes needed to implement the 5-layer operational resilience strategy
> Codebase: ~13,700 lines across 32 Python files

---

## Summary

~400–500 new/modified lines across ~15 files. 3–4% of the codebase. Not a rewrite — surgical additions threading through existing plumbing.

---

## Layer 1: Correlation ID (~80 new, ~40 modified)

| File | Action | Lines | Notes |
|------|--------|-------|-------|
| `openclaw/skills/fsi-research/pipeline.py` | Modify | ~35 | Add `correlation_id` to `__init__`, pass to every `_mcp_call`, `_sf_soql`, `_log_audit`, Langfuse trace metadata. Already has `run_id` — same pattern. |
| `aws/mcp-servers/shared/mcp_protocol.py` | Modify | ~15 | Extract `x-correlation-id` from headers in `_handle_tools_call`, add to response headers, add to logger extra. |
| `openclaw/skills/audit-logging/logger.py` | Modify | ~15 | Add `Correlation_Id__c` to the SF record dict. Already has `Trace_Id__c` — same pattern. |
| `openclaw/mcp-rest-bridge.mjs` | Modify | ~10 | Forward `x-correlation-id` header from OpenClaw to MCP Lambda. |
| `force-app/.../IR_Audit_Log__c/fields/Correlation_Id__c.field-meta.xml` | New | ~15 | New text(255) field on IR_Audit_Log__c. |
| `openclaw/openclaw.json` | Modify | ~3 | Hook config for correlation_id injection (if supported natively). |

**Why it's small:** `pipeline.py` already threads `run_id` and `self.trace` through every stage. Correlation ID piggybacks on the same plumbing. `logger.py` already dual-writes to SF + Langfuse with a shared `trace_id`. One more field.

---

## Layer 2: Circuit Breakers (~120 new, ~30 modified)

| File | Action | Lines | Notes |
|------|--------|-------|-------|
| `openclaw/skills/fsi-research/circuit_breaker.py` | **New** | ~80 | Standalone `CircuitBreaker` class with CLOSED/OPEN/HALF_OPEN states, failure counting, recovery timeout. |
| `openclaw/skills/fsi-research/pipeline.py` | Modify | ~40 | Import circuit breakers. Wrap `_mcp_call` and `_sf_soql` with `.call()`. Add fallback returns when circuit is OPEN. |
| `aws/mcp-servers/shared/mcp_protocol.py` | Modify | ~30 | Add timeout tracking and structured error responses for circuit breaker consumption. |

**Why it's small:** The circuit breaker is a standalone module. Existing `_mcp_call` and `_sf_soql` methods in `pipeline.py` are the only two call sites that need wrapping — not every stage, just the two helper methods all stages use.

---

## Layer 3: Health Check Script (~100 new, 0 modified)

| File | Action | Lines | Notes |
|------|--------|-------|-------|
| `scripts/health-check.py` | **New** | ~100 | Standalone script. Tests all 8 integration boundaries (3 MCP servers, Salesforce, Bedrock Sonnet, Bedrock Haiku, Langfuse, OpenClaw gateway). Zero changes to existing code. |

**Why it's small:** Pure addition. Calls existing endpoints. No coupling to application code.

---

## Layer 4: Langfuse Trace Enrichment (~40 new, ~30 modified)

| File | Action | Lines | Notes |
|------|--------|-------|-------|
| `openclaw/skills/fsi-research/pipeline.py` | Modify | ~70 | Enrich existing spans with: token counts, cost, model name, tool latency. `_llm_generate` and `_mcp_call` each need ~5–10 lines for richer span metadata. Already creates spans per stage — just adding attributes. |

**Why it's small:** `pipeline.py` already creates a Langfuse span for every stage in `_execute_stages`. The change is adding `metadata={"tokens": ..., "cost": ..., "model": ...}` to existing `span.end()` calls.

---

## Layer 5: CloudWatch Dashboard (~60 new, 0 modified)

| File | Action | Lines | Notes |
|------|--------|-------|-------|
| `aws/cloudwatch-dashboard.json` | **New** | ~60 | Dashboard definition with widgets for Lambda errors, Bedrock throttles, API Gateway 5xx, cold starts, token usage. Declarative JSON, no app code changes. |

---

## Layer 6: Runbooks (0 code changes)

Already written in `docs/006-operational-resilience-strategy.md`. Pure documentation.

---

## Totals

| Layer | New Files | New Lines | Modified Lines | Total |
|-------|-----------|-----------|----------------|-------|
| Correlation ID | 1 | ~15 | ~78 | ~93 |
| Circuit Breakers | 1 | ~80 | ~70 | ~150 |
| Health Check | 1 | ~100 | 0 | ~100 |
| Langfuse Enrichment | 0 | ~40 | ~30 | ~70 |
| CloudWatch Dashboard | 1 | ~60 | 0 | ~60 |
| Runbooks | 0 | 0 | 0 | 0 |
| **Total** | **4 new files** | **~295** | **~178** | **~473** |

Against a codebase of ~13,700 lines, that's a **3.5% change**.

---

## Files NOT Touched

These files don't need any changes:

- All 7 financial analysis skill files (dcf.py, comps.py, monte_carlo.py, etc.)
- compliance-screening/screening.py and mnpi_filter.py
- salesforce-crm/trust_layer.py
- metaclaw.py
- All 4 MCP server app.py files (sec-edgar, market-data, news-search, salesforce-crm)
- All frontend code (React, TypeScript, CSS)
- All Salesforce metadata except the one new field
- All SKILL.md files
- AGENTS.md, IDENTITY.md, TOOLS.md

The resilience layer wraps existing code — it doesn't rewrite it.

---

## Implementation Order

| Step | What | Effort | Depends On |
|------|------|--------|------------|
| 1 | Correlation_Id__c field on IR_Audit_Log__c | 0.5 day | Nothing |
| 2 | Correlation ID threading (pipeline → logger → mcp_protocol → bridge) | 1.5 days | Step 1 |
| 3 | health-check.py | 1 day | Nothing |
| 4 | circuit_breaker.py + pipeline wrapping | 2 days | Nothing |
| 5 | Langfuse trace enrichment | 1.5 days | Step 2 |
| 6 | CloudWatch dashboard | 0.5 day | Nothing |
| **Total** | | **~7 days** | |

Steps 1+2, 3, 4, and 6 can run in parallel. Critical path is Steps 1 → 2 → 5 (3.5 days).
