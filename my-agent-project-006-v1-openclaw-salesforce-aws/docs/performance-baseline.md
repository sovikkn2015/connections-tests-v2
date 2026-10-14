# Performance Baseline — Project 006

## Status: TEMPLATE (fill after running evaluation suite)

Record latency, cost, and throughput metrics here after running the 25-query evaluation suite (`evaluation/run_suite.py`).

---

## Response Time by Query Level

| Level | Description | Target | Measured (p50) | Measured (p95) | Date |
|-------|-------------|--------|----------------|----------------|------|
| L1 | Simple CRM lookup (e.g., "Who covers NVIDIA?") | < 3s | _pending_ | _pending_ | — |
| L2 | Multi-source query (CRM + 1 MCP server) | < 8s | _pending_ | _pending_ | — |
| L3 | Analytical query (CRM + MCP + financial model) | < 20s | _pending_ | _pending_ | — |
| L4 | Full pipeline (AutoResearchClaw 23-stage brief) | < 15 min | _pending_ | _pending_ | — |

---

## MCP Server Cold Start Times

| MCP Server | Lambda Memory | Cold Start | Warm Invocation | Date |
|------------|---------------|------------|-----------------|------|
| SEC EDGAR | 256 MB | _pending_ | _pending_ | — |
| Market Data | 256 MB | _pending_ | _pending_ | — |
| News Search | 256 MB | _pending_ | _pending_ | — |

---

## Bedrock LLM Latency

| Model | Metric | Value | Date |
|-------|--------|-------|------|
| Claude Sonnet 4 (us.anthropic.claude-sonnet-4-6) | Time to first token | _pending_ | — |
| Claude Sonnet 4 (us.anthropic.claude-sonnet-4-6) | Total generation time (1K tokens) | _pending_ | — |
| Claude Haiku 4.5 (us.anthropic.claude-haiku-4-5-20251001-v1:0) | Time to first token | _pending_ | — |
| Claude Haiku 4.5 (us.anthropic.claude-haiku-4-5-20251001-v1:0) | Total generation time (1K tokens) | _pending_ | — |

---

## Cost per Query by Level

| Level | LLM Cost (input) | LLM Cost (output) | MCP Calls | Total Est. Cost | Date |
|-------|-------------------|--------------------|-----------|-----------------|------|
| L1 | _pending_ | _pending_ | 0 | _pending_ | — |
| L2 | _pending_ | _pending_ | 1-2 | _pending_ | — |
| L3 | _pending_ | _pending_ | 2-4 | _pending_ | — |
| L4 | _pending_ | _pending_ | 10-20 | _pending_ | — |

---

## Pipeline Throughput (L4)

| Metric | Value | Date |
|--------|-------|------|
| Total pipeline duration (23 stages, no HITL wait) | _pending_ | — |
| Total pipeline duration (23 stages, with HITL wait) | _pending_ | — |
| Stages with longest latency | _pending_ | — |
| Total LLM calls per pipeline run | _pending_ | — |
| Total MCP calls per pipeline run | _pending_ | — |
| Total SF API calls per pipeline run | _pending_ | — |

---

## Evaluation Suite Summary

| Metric | Value | Date |
|--------|-------|------|
| Queries run | 0 / 25 | — |
| Pass rate (correctness) | _pending_ | — |
| Pass rate (completeness) | _pending_ | — |
| Pass rate (safety — no PII leak) | _pending_ | — |
| Average Langfuse score (5-dim rubric) | _pending_ | — |
| Queries with anti-fabrication violations | _pending_ | — |

---

## How to Fill This Template

1. Deploy the full stack (OpenClaw + MCP servers + SF org)
2. Run the evaluation suite:
   ```bash
   cd evaluation
   pip install -r requirements.txt
   python run_suite.py --config ../openclaw/openclaw.json
   ```
3. Collect metrics from Langfuse traces
4. Fill in the tables above with measured values
5. Record the date for each measurement
6. Re-run after significant changes to track regressions
