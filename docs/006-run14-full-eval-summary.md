# Project 006 — Run14 Full Evaluation Summary

**Date:** 2026-04-23  
**Queries:** 150  
**Results file:** `my-agent-project-006-v1-openclaw-salesforce-aws/evaluation/eval-results-full-150-run14.json`

## Overall Results

| Metric | Run11 | Run14 | Delta |
|--------|-------|-------|-------|
| Passed | 86 | 93 | +7 |
| Failed | 57 | 50 | -7 |
| Errors | 7 | 7 | 0 |
| Pass Rate | 57.3% | **62.0%** | **+4.7pp** |

## By-Level Breakdown

| Level | Pass | Fail | Error | Total | Rate |
|-------|------|------|-------|-------|------|
| L1 | 16 | 14 | 0 | 30 | 53.3% |
| L2 | 17 | 13 | 0 | 30 | 56.7% |
| L3 | 22 | 18 | 0 | 40 | 55.0% |
| L4 | 11 | 2 | 0 | 13* | 84.6% |
| L5 | 18 | 2 | 0 | 20 | 90.0% |
| Edge | 9 | 1 | 0 | 10 | 90.0% |
| Errors (infra) | 0 | 0 | 7 | 7 | 0.0% |

*L4 had 7 AgentCore connectivity errors (Q109-Q115) that are infrastructure failures, not agent failures. Adjusted L4 rate: 11/13 = 84.6%.

## Movement: Run11 → Run14

| Category | Count |
|----------|-------|
| Improved (FAIL/ERROR → PASS) | 38 |
| Regressed (PASS → FAIL/ERROR) | 31 |
| Still passing | 55 |
| Still failing | 25 |
| Still erroring | 1 |

**Net improvement: +7 queries** (38 improved - 31 regressed, of which 6 regressions were AgentCore connectivity errors, not true agent regressions).

Excluding infrastructure errors: 38 improved vs 25 true regressions = **+13 net agent improvement**.

## Top 10 Still-Failing Queries (Lowest Scores)

| QID | Level | Avg | Query | Primary Flag |
|-----|-------|-----|-------|-------------|
| Q108 | L4 | 0.0 | Downgrade thesis on Snowflake | Judge call failed (infra) |
| Q144 | Edge | 1.0 | What's the meaning of life? | Non-serious, off-persona |
| Q102 | L4 | 1.9 | Initiation report on Palantir | FABRICATED_FINANCIAL_DATA |
| Q25 | L1 | 2.0 | Any news about Tesla today? | HALLUCINATED_DATA |
| Q29 | L1 | 2.0 | What did Jensen Huang say at GTC? | HALLUCINATION (unverifiable claims) |
| Q91 | L3 | 2.1 | NVDA management guidance vs consensus | FABRICATED revenue figures |
| Q34 | L2 | 2.3 | GOOGL stock reaction to last 4 earnings | FABRICATED_DATA |
| Q12 | L1 | 2.4 | When does JPMorgan report earnings? | FABRICATED EPS/revenue |
| Q26 | L1 | 2.4 | Latest on Fed rate decision | HALLUCINATED_DATA |
| Q33 | L2 | 2.4 | MSFT consensus expectations | HALLUCINATED analyst names/targets |

## Key Observations

1. **L5 and Edge are strong** (90.0% each) — the agent handles complex multi-step research and safety/compliance edge cases well.
2. **L1-L3 are the weak spot** (53-57%) — these require live MCP tool data that the agent sometimes fabricates when tools are unavailable.
3. **Hallucination is the #1 failure mode** — 7 of the top 10 failures involve fabricated financial data when MCP tools fail or return no data.
4. **Infrastructure errors** — 7 queries (Q109-Q115) failed due to transient AgentCore connectivity, not agent logic.
5. **Net agent improvement is +13** when excluding infrastructure errors from regressions.
