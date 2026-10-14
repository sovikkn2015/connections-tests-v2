---
name: FSI Research Pipeline
slug: fsi-research
version: 1.0.0
description: >-
  23-stage AutoResearchClaw pipeline for FSI equity research. Produces
  compliance-screened research briefs with ratings, target prices, DCF
  valuations, comps analysis, and Monte Carlo simulations. Publishes to
  Salesforce IR_Research_Note__c with full audit trail.
trigger-keywords:
  - deep dive
  - research brief
  - research
  - initiation
  - full analysis
  - comprehensive
applicable-stages: [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23]
metadata:
  requires:
    env:
      - SF_ACCESS_TOKEN
      - SF_INSTANCE_URL
      - MCP_GATEWAY_URL
      - MCP_API_KEY
      - LANGFUSE_SECRET_KEY
      - LANGFUSE_PUBLIC_KEY
      - LANGFUSE_BASE_URL
    skills:
      - financial-analysis
      - compliance-screening
      - audit-logging
      - salesforce-crm
---

# FSI Research Pipeline

## Overview

The pipeline orchestrator (`pipeline.py`) is the core of Project 006's
AutoResearchClaw adaptation. It runs 23 stages sequentially, calling MCP
tools, financial models, LLM synthesis, and Salesforce CRM to produce a
structured equity research brief.

## Invocation

```python
from pipeline import FSIResearchPipeline

pipeline = FSIResearchPipeline(
    ticker="NVDA",
    query="Deep dive on NVIDIA ahead of earnings",
    analyst="Sarah Chen",
    config=config,  # parsed from config.arc.yaml
)

# Run all 23 stages (pauses at HITL gates)
result = await pipeline.run()

# If paused at a HITL gate, resume after analyst approval
if result["status"] == "paused":
    result = await pipeline.resume(
        from_stage=result["paused_at_stage"] + 1,
        approval={"approved": True, "notes": "Looks good", "analyst": "Sarah Chen"},
    )
```

## Pipeline Stages

| Phase | Stages | Description | Tools / Skills |
|-------|--------|-------------|----------------|
| A — Intake | 1-2 | Parse query, fetch CRM context | Regex, SF SOQL |
| B — Data Collection | 3-6 | Market data, news, SEC filings, transcript | MCP servers, LLM |
| C — Validation | 7 | **HITL**: Data quality gate | — |
| D — Analysis | 8-12 | Financial modeling, DCF, comps, Monte Carlo, sentiment | dcf.py, comps.py, monte_carlo.py, LLM |
| E — Review | 13 | **HITL**: Analysis review gate | — |
| F — Synthesis | 14-18 | Thesis, catalysts, risks, rating, target price | LLM |
| G — Output | 19-20 | Brief assembly, compliance check | compliance-screening |
| H — Delivery | 21-23 | **HITL**: Final approval, CRM write-back, notify | SF REST API |

## HITL Gates

Three stages pause for analyst approval:

- **Stage 7** — Data Quality Gate: verify data completeness before analysis
- **Stage 13** — Analysis Review Gate: review model outputs before synthesis
- **Stage 21** — Final Approval Gate: approve brief before publishing

When a gate is reached, `run()` returns `{"status": "paused", "gate": {...}}`.
The caller presents the gate context to the analyst and calls `resume()`.

## Anti-Fabrication

Every number in the final brief traces to a tool result in `self.data_sources`.
The compliance check (stage 20) runs `_verify_anti_fabrication()` to confirm:

- Target price is backed by at least one model output (DCF, comps, or Monte Carlo)
- Sufficient data sources were recorded (minimum 3)
- Financial model outputs exist

## Data Flow

```
Query → Intake → CRM → MCP (market, news, SEC) → LLM transcript
  → [HITL Gate 7]
  → Model inputs → DCF → Comps → Monte Carlo → LLM sentiment
  → [HITL Gate 13]
  → LLM thesis → LLM catalysts → LLM risks → LLM rating → Target price
  → Brief assembly → Compliance check
  → [HITL Gate 21]
  → IR_Research_Note__c → IR_Audit_Log__c → Notify
```

## Observability

Dual-write strategy:

1. **Langfuse** — every stage is a span, every MCP/LLM call is traced
2. **IR_Audit_Log__c** — every stage writes an audit record (FINRA 7-year retention)

Shared `Trace_Id__c` links both systems.

## Configuration

The pipeline reads from `config.arc.yaml`:

- `llm.primary_model` — Bedrock model ID (default: `anthropic.claude-sonnet-4-6`)
- `experiment.repair.enabled` — auto-retry failed stages (default: true, max 3 cycles)
- `hitl.enabled` — enable HITL gates (default: true)
- `hitl.cost_budget_usd` — cost cap per run

## Dependencies

See `requirements.txt`. Key dependencies:

- `requests` — HTTP client for MCP and Salesforce REST
- `langfuse` — observability
- `numpy`, `pandas`, `scipy` — financial modeling (via financial-analysis skill)
- `pyyaml` — config parsing
