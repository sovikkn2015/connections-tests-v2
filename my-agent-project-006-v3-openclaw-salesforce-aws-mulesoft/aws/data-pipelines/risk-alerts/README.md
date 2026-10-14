# Risk Alerts Pipeline — V3 Narrative 3

Async price-shock detection that fans out compliance sweeps through the
OpenClaw AgentCore coordinator. Runs fully inside AWS (EventBridge →
Lambda → SQS → Lambda → AgentCore). No human is in the hot path.

## Flow

```
EventBridge (cron */5 13-21 UTC, Mon-Fri)
   │
   ▼
MarketPriceMonitor Lambda  ──── SSM /006-v3/watchlist/tickers
   │                      ──── Secrets: finnhub api key
   │                      ──── Finnhub /quote (1 req/sec pacing)
   │
   ├── |pct change| < threshold ────► (no-op)
   │
   └── |pct change| >= threshold
          │
          ▼
     DynamoDB PriceShockEvents  (idempotency on ticker-{5min bucket})
          │ already-present?  → skip
          │ new?              → put_item + enqueue
          ▼
     SQS ComplianceSweepQueue  (DLQ after 5 retries)
          │
          ▼
     SweepDispatcher Lambda (batch size 1)
          │
          ├── DynamoDB ComplianceSweepEvents (dedup on event_id)
          │
          └── POST {AGENTCORE_URL}
                 Authorization: Bearer <secrets manager token>
                 body: { skill: "compliance_sweep", principal_id: "system-risk-monitor", ... }
```

## Environment variables

### MarketPriceMonitor
| Var | Default | Purpose |
| --- | --- | --- |
| `WATCHLIST_SSM_PARAM` | `/006-v3/watchlist/tickers` | CSV of tickers |
| `FINNHUB_API_KEY_SECRET` | _(required)_ | Secrets Manager ARN for Finnhub key |
| `PRICE_SHOCK_THRESHOLD_PCT` | `3.0` | Abs % move that fires a sweep |
| `SHOCK_EVENTS_TABLE` | _(required)_ | DynamoDB dedup table name |
| `COMPLIANCE_SWEEP_QUEUE_URL` | _(required)_ | SQS queue URL |

### SweepDispatcher
| Var | Default | Purpose |
| --- | --- | --- |
| `AGENTCORE_URL` | _(required)_ | HTTPS endpoint of AgentCore coordinator |
| `AGENTCORE_TOKEN_SECRET` | _(required)_ | Secrets Manager ARN for system bearer token |
| `SWEEP_EVENTS_TABLE` | _(required)_ | DynamoDB event-log + dedup table |

## Idempotency guarantees

Two independent dedup layers protect against duplicate sweeps:

1. **Market side (5-min bucket).** Key = `f"{ticker}-{int(now.timestamp() // 300)}"`.
   Same ticker + same 5-min UTC window = same shock, dedup'd before it hits SQS.
   Records have 24h TTL.
2. **Dispatch side (event_id).** Sweep dispatcher checks the `event_id` in
   `ComplianceSweepEvents` before invoking AgentCore. Covers the rare case
   where SQS redrives a message whose original invocation succeeded but
   acked late. Records have 24h TTL.

## Rate limits

- **Finnhub free tier:** 60 calls/min. The monitor paces at `time.sleep(1.0)`
  between tickers, giving exactly 60 calls/min headroom for ~50 tickers
  per 5-minute cycle.
- **Market hours gate:** monitor short-circuits outside 09:30-16:00 ET
  and on weekends, so EventBridge firings outside market hours cost only
  one idle Lambda invocation (≈ 50ms billable).

## Cost estimate (us-east-1, monthly)

Assuming a 50-ticker watchlist, 5-minute schedule, 6.5h × 252 trading days/yr:

| Line | Monthly | Notes |
| --- | --- | --- |
| Lambda invocations | < $1 | ~1,700 monitor calls/mo, 512 MB, <5s each |
| EventBridge | $0 | Scheduled rule, under free tier |
| Finnhub | $0 | Free tier handles ~50 tickers at 60/min |
| DynamoDB | < $1 | On-demand, tiny write volume |
| SQS | < $0.01 | Only fires on actual shocks |
| Secrets Manager | $0.80 | 2 secrets × $0.40 |
| **Total** | **< $3/mo** | Before sweep-side AgentCore costs |

Sweep-side cost depends on how often the compliance_sweep skill runs;
in quiet markets, essentially zero.

## Tuning `PRICE_SHOCK_THRESHOLD_PCT`

| Value | Behavior | When to use |
| --- | --- | --- |
| `1.0` | Very chatty — most large caps trip daily | Dev only |
| `3.0` _(default)_ | Fires on real moves, not noise | Prod baseline |
| `5.0` | Only fires on major news-driven moves | Conservative teams |
| `10.0` | Circuit-breaker territory only | Extreme events only |

Update via Lambda console or `cdk deploy` — monitor re-reads the env var
on every invocation, no warm-container sticky values.

## Local sanity check

```
python3 -m py_compile aws/data-pipelines/risk-alerts/lambdas/monitor.py \
                     aws/data-pipelines/risk-alerts/lambdas/sweep_dispatcher.py
```

The CDK stack lives at `aws/cdk/stacks/risk_alerts_stack.py`
(`Openclaw006V3-RiskAlerts`).
