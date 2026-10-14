# M11 MCP Adapters — Architecture Decision Log

## ADR-001: Python/FastAPI for M11-REST Adapters (Phase 2)

**Date:** 2025-07-14
**Status:** Accepted
**Rule Deviation:** Rule 7 mandates TypeScript + `@modelcontextprotocol/sdk` for M11-REST adapters.

### Decision

Use Python 3.12+ / FastAPI for all Phase 2 M11-REST adapters (sec-edgar, market-data, news-search, salesforce-fsc, orion) instead of TypeScript.

### Rationale

1. **Workspace consistency** — The entire 007 workspace is Python-focused. Introducing Node.js/npm infrastructure for 5 adapters adds build complexity with no functional benefit.
2. **Protocol-agnostic MCP contract** — The MCP interface contract (GET `/` + POST `/tools/list` + POST `/tools/call`) is identical regardless of implementation language. Callers (M6 gateway) see the same HTTP/JSON interface.
3. **Infrastructure overhead** — TypeScript would require npm, node_modules, tsconfig, separate CI pipelines, and a different base Docker image for 5 adapters that are otherwise identical in structure to the Python-based M11-BLPAPI/gRPC/SFTP adapters.
4. **Shared utilities** — All 5 adapters share `_shared/` (MCPAdapterServer factory, TokenBucket rate limiter, canonical error format, structured logging). A single-language stack means one shared library, not two.
5. **Phase 2 velocity** — Python adapters ship faster with the existing team skillset and toolchain.

### Impact

Zero functional difference. The MCP protocol is language-agnostic — M6 gateway, M7 translators, and all callers interact via HTTP/JSON. No downstream module is affected.

### Revisit Criteria

Migrate to TypeScript + `@modelcontextprotocol/sdk` in Phase 3 if:
- The TypeScript MCP SDK provides significant advantages (e.g., built-in schema validation, streaming, SDK-level rate limiting) that justify the infrastructure cost.
- A dedicated Node.js team is onboarded.
- Performance benchmarks show meaningful throughput differences.

---

## ADR-002: _shared Module for Boilerplate Elimination

**Date:** 2025-07-14
**Status:** Accepted

### Decision

All M11 Python adapters MUST use the `_shared/` module:
- `_shared/mcp_server.py` — `MCPAdapterServer` factory (builds FastAPI app with GET `/`, POST `/tools/list`, POST `/tools/call`, request middleware, structured logging)
- `_shared/rate_limiter.py` — `TokenBucket` rate limiter
- `_shared/errors.py` — `canonical_error()`, `tool_result()` helpers
- `_shared/logging.py` — `get_logger()` structured logging setup

### Rationale

Phase 2 review found TokenBucket copy-pasted 3x, canonical_error 4x, structlog.configure 5x, ToolCallRequest 5x, request middleware 5x. The `_shared/` module existed but zero adapters used it.

### Impact

Each adapter's `server.py` now contains only vendor-specific logic: HTTP client setup, tool definitions, and tool handlers. All MCP boilerplate is centralized in `_shared/mcp_server.py`.

---

## ADR-003: TypeScript Reference Implementation (Phase 4)

**Date:** 2026-04-17
**Status:** Accepted
**Resolves:** Rule 10 polyglot violation from ADR-001

### Decision

Build `sec-edgar-ts/` as the TypeScript reference implementation using
`@modelcontextprotocol/sdk` + Express. This proves the platform supports
both Python and TypeScript M11 adapters.

### Impact

Rule 10 is now satisfied: M11 is polyglot with both Python (11 adapters)
and TypeScript (1 adapter) implementations. The MCP interface contract
(GET / + POST /tools/list + POST /tools/call) is identical regardless
of language — M6 gateway sees no difference.

### Migration Path

New REST adapters MAY be built in either Python or TypeScript.
The `sec-edgar-ts/` serves as the template for TypeScript adapters.
Existing Python adapters do NOT need migration — they work correctly.
