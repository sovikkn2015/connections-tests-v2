# 006 Query Routing: Pipeline vs Direct MCP Tools

> Date: April 22, 2026
> Scope: How queries are routed in the 006 OpenClaw agent — which go through the 23-stage AutoResearchClaw pipeline and which go directly to MCP tools

---

## The Routing Rule

Not all queries go through the 23-stage AutoResearchClaw pipeline. The agent's system prompt defines the split:

> For research briefs (L3+), route through the 23-stage pipeline with HITL gates at 7/13/21.

**~80% of daily queries (L1-L2) skip the pipeline entirely** and go straight to MCP tools via OpenClaw skills. Only deep analysis and research brief queries trigger the full pipeline.

---

## Query Levels

| Level | Type | Example | Path | Pipeline? | LLM Model |
|-------|------|---------|------|-----------|-----------|
| L1 | Simple lookup | "What's NVDA trading at?" | Agent → `get_quote` (market-data MCP) → response | No | Haiku 4.5 |
| L1 | CRM lookup | "Who covers NVDA?" | Agent → `run_soql_query` (salesforce-crm MCP) → response | No | Haiku 4.5 |
| L1 | Filing lookup | "NVDA latest 10-K" | Agent → `get_10k` (sec-edgar MCP) → response | No | Haiku 4.5 |
| L2 | Multi-source assembly | "What's happening with NVIDIA ahead of earnings?" | Agent → multiple MCP tools → synthesized response | No | Sonnet 4.6 |
| L2 | Comparison | "Side-by-side: AAPL vs MSFT — P/E, margins" | Agent → multiple `get_quote` + `run_soql_query` calls → table | No | Sonnet 4.6 |
| L3 | Deep analysis | "DCF valuation for NVDA" | Agent → pipeline stages 8-12 (financial modeling) | Partial | Sonnet 4.6 |
| L3 | Filing deep dive | "Summarize risk factors from Apple's latest 10-K" | Agent → pipeline (data collection + synthesis) | Partial | Sonnet 4.6 |
| L4 | Full research brief | "Deep dive on NVIDIA ahead of earnings" | Agent → full 23-stage pipeline with 3 HITL gates | Yes, full | Sonnet 4.6 |
| L4 | Coverage initiation | "Initiate coverage on PLTR" | Agent → full 23-stage pipeline | Yes, full | Sonnet 4.6 |
| L5 | Action execution | "Trim Client F's NVDA by 30%" | Agent → pipeline + MuleSoft action + HITL approval | Yes + MuleSoft | Sonnet 4.6 |

---

## Architecture Path by Level

### L1: Direct Tool Call (No Pipeline)

```
User → OpenClaw Agent → Claude Haiku 4.5 (intent + response)
                       → MCP Tool (1 call)
                       → Response
```

Latency: 1-3 seconds. Cost: ~$0.001-0.005 per query.

### L2: Multi-Tool Assembly (No Pipeline)

```
User → OpenClaw Agent → Claude Sonnet 4.6 (reasoning)
                       → MCP Tool 1 (market-data)
                       → MCP Tool 2 (salesforce-crm)
                       → MCP Tool 3 (news-search)
                       → Synthesized Response
```

Latency: 3-8 seconds. Cost: ~$0.01-0.05 per query.

### L3-L4: AutoResearchClaw Pipeline

```
User → OpenClaw Agent → Intent Router → AutoResearchClaw Pipeline
                                         │
                                         ├── Phase A: Scoping (stages 1-2)
                                         ├── Phase B: Data Collection (stages 3-6)
                                         ├── Phase C: Validation + HITL Gate (stage 7)
                                         ├── Phase D: Analysis (stages 8-12)
                                         ├── Phase E: Review + HITL Gate (stage 13)
                                         ├── Phase F: Synthesis (stages 14-18)
                                         ├── Phase G: Output (stages 19-20)
                                         └── Phase H: Delivery + HITL Gate (stage 21-23)
                                         │
                                         → Research Brief → IR_Research_Note__c
                                         → Audit Trail → IR_Audit_Log__c
```

Latency: 30-120 seconds (+ HITL wait time). Cost: $1-5 per brief.

### L5: Pipeline + MuleSoft Action

```
Same as L3-L4, plus:
  → MuleSoft skill → submit_order / initiate_wire / run_kyc
  → HITL approval required for every action
  → Dual auth for wire >$100K or trade >$500K
```

---

## How the Agent Decides

The routing is not hardcoded — it's LLM-driven. The agent's system prompt instructs it to:

1. Use MCP tools directly for factual lookups (price, filings, CRM data, news)
2. Route to the pipeline when the user asks for analysis, research briefs, or deep dives
3. The trigger keywords are: "deep dive", "research brief", "research note", "initiate coverage", "earnings preview", "full analysis"

The intent router in OpenClaw classifies query complexity and selects the model:
- L1-L2 → Haiku 4.5 (fast, cheap, handles tool use well)
- L3-L5 → Sonnet 4.6 (best reasoning for multi-step analysis)

---

## Cost Implications

| Level | Queries/Day (est.) | Cost/Query | Daily Cost |
|-------|-------------------|------------|------------|
| L1 | 50-100 | $0.001-0.005 | $0.05-0.50 |
| L2 | 20-40 | $0.01-0.05 | $0.20-2.00 |
| L3 | 5-10 | $0.50-2.00 | $2.50-20.00 |
| L4 | 2-5 | $1.00-5.00 | $2.00-25.00 |
| L5 | 0-2 | $2.00-5.00 | $0-10.00 |
| **Total** | **77-157** | | **$4.75-57.50** |

The tiered routing keeps costs manageable — 80% of queries run on the cheap model with no pipeline overhead.

---

## Pipeline Trigger Examples

Queries that DO trigger the pipeline:
- "Deep dive on NVIDIA ahead of earnings"
- "Research note on Costco — same-store sales, membership economics"
- "Full research brief on JPM"
- "Initiate coverage on PLTR"
- "Earnings preview for LLY"

Queries that do NOT trigger the pipeline:
- "What's NVDA trading at?"
- "Who covers AAPL?"
- "Latest news on Tesla"
- "NVDA latest 10-K filing"
- "Show my watchlist"
- "Is NVDA on the restricted list?"
