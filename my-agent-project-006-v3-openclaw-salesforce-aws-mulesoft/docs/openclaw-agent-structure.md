# 006 V3 — OpenClaw Agent Structure

Three personas. 14 unique agents in the registry (3 orchestrators + 11 specialists).
Source of truth: `openclaw/orchestration/topology.py` (Pydantic-validated, integrity-asserted at import time).

## Topology

```
                        006 V3 — OPENCLAW AGENT TOPOLOGY
               3 personas · 14 unique agents (3 orchestrators + 11 specialists)

┌─────────────────────────────────────────────────────────────────────────────────┐
│                          COORDINATOR (openclaw/coordinator.py)                  │
│                   intent-classify → route to persona orchestrator               │
└──────────┬──────────────────────┬────────────────────────┬──────────────────────┘
           │                      │                        │
           ▼                      ▼                        ▼
 ╔══════════════════╗   ╔══════════════════╗   ╔══════════════════════╗
 ║  fsi_research    ║   ║   fsi_advisor    ║   ║  fsi_client_liaison  ║
 ║    (Sarah)       ║   ║     (RM)         ║   ║    (end-client)      ║
 ║  6 agents        ║   ║   5 agents       ║   ║    3 agents          ║
 ╚═════════╤════════╝   ╚═════════╤════════╝   ╚══════════╤═══════════╝
           │                      │                       │
           ▼                      ▼                       ▼
┌──────────────────────┐ ┌──────────────────────┐ ┌────────────────────────┐
│ research_orchestr.   │ │ advisor_orchestrator │ │ liaison_orchestrator   │
│  Sonnet · planner    │ │  Sonnet · router     │ │  Haiku · FAQ/escalate  │
│  parallel fan-out    │ │  parallel reads /    │ │  single dispatch       │
│  asyncio.gather      │ │  SERIAL writes       │ │  read-only+rm-handoff  │
│  t=120s              │ │  t=300s              │ │  t=30s                 │
└──────┬───────────────┘ └─────────┬────────────┘ └────────┬───────────────┘
       │ (parallel 5)              │ (read: ∥ / write: 1)  │ (one of 2)
       │                           │                       │
       ├─► market_specialist       ├─► portfolio_spec.     ├─► faq_specialist
       │   Sonnet · market-data    │   Sonnet              │   Haiku · bounded
       │   MCP (Finnhub/AV)        │   portfolio_analytics │   no tools, no MCP
       │   rag_retrieve            │   scenario_modeling   │   disclaimer+CTA
       │   t=25s                   │   t=25s               │   t=15s
       │                           │                       │
       ├─► filings_specialist      ├─► suitability_spec.   └─► context_specialist
       │   Sonnet · sec-edgar MCP  │   Sonnet · determin.      Sonnet · read-only
       │   rag_retrieve            │   suitability_check       client_summary
       │   financial_stmt_analysis │   PASS/FAIL/REVIEW        MNPI filter
       │   t=25s                   │   t=20s                   t=20s
       │                           │
       ├─► sentiment_specialist    ├─► client_context_spec.
       │   Sonnet · news-search    │   Sonnet · MNPI-filt.
       │   MCP (Tavily)            │   client_summary
       │   in-prompt scoring       │   research_awareness
       │   t=20s                   │   t=25s
       │                           │
       ├─► compliance_specialist   └─► action_specialist  ◄── SERIAL BY DESIGN
       │   Sonnet                      Sonnet · write path
       │   compliance_screening        ┌──────────────────────────────────┐
       │   ALLOW/DENY/REVIEW           │ 7-gate spine (sequential):       │
       │   t=20s                       │ 1. Guardrails (input)            │
       │                               │ 2. MNPI filter                   │
       └─► statement_specialist        │ 3. compliance_screening          │
           Sonnet · sec-edgar MCP      │ 4. hitl (HMAC-SHA256, 5m TTL)    │
           financial_stmt_analysis     │ 5. dual_auth (>$100K / >$500K)   │
           deterministic calcs         │ 6. mulesoft_api (ONLY write path)│
           t=30s                       │ 7. audit_logging (always)        │
                                       └──────────────────────────────────┘
                                         t=300s · never parallelizes
```

## Cross-cutting layers

```
  ┌─────────────────────────────────────────────────────────────────────────┐
  │  TRUST LAYER  (openclaw/trust/)                                         │
  │    idp_session · gate_enforcer · mnpi_filter                            │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  SKILLS REGISTRY (openclaw/skills/ — 13 skills)                         │
  │    research: rag_retrieve · financial_statement_analysis ·              │
  │              research_awareness                                         │
  │    advisor:  portfolio_analytics · scenario_modeling ·                  │
  │              suitability_check · client_summary                         │
  │    action:   compliance_screening · hitl · dual_auth ·                  │
  │              mulesoft_api · audit_logging                               │
  │    shared:   publish_brief                                              │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  MEMORY SCOPES   session · user · artifact (SObject) · read_only        │
  ├─────────────────────────────────────────────────────────────────────────┤
  │  MCP SERVERS     salesforce-crm · market-data · sec-edgar ·             │
  │                  news-search · mulesoft-actions                         │
  └─────────────────────────────────────────────────────────────────────────┘
```

## Notes

- The narrative says "17 agents" but the actual unique-ID registry is 14 (3 orchestrators + 11 specialists). `assert_topology_integrity()` in `topology.py` enforces exactly that. The "17" double-counts specialists that conceptually exist in two personas (e.g. "context" framed for both research and liaison) but only one `context_specialist` ID is registered.
- `action_specialist` is the only agent marked `serial_by_design=True` — steering rule 1 says the write path never parallelizes.
- `faq_specialist` and `liaison_orchestrator` are the only Haiku agents; everything else is Sonnet.
- Orchestrators never call MCP tools directly — they only `dispatch_specialist` / `synthesize_*` / `rm_handoff`.
- Per-agent system prompts, tool allowlists, MCP allowlists, and memory scopes live in `openclaw/orchestration/topology.py`. The YAML files in `openclaw/agents/` carry structured metadata for runtime introspection.
