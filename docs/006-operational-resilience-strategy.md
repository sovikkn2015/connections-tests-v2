# 006 Operational Resilience Strategy: Managing 4 Platforms

> Date: April 22, 2026
> Audience: Engineering leads, architects, SRE
> Problem: 4 platforms (Salesforce + AWS + OpenClaw + MuleSoft), 7+ integration boundaries, 23-stage pipeline. When something breaks, you're hunting across four systems.

---

## The Core Problem

The complexity of 006 isn't in the code — it's in the space between the systems. A single research brief touches:

```
User (Slack) → OpenClaw Gateway → Bedrock (LLM) → MCP Lambda (SEC EDGAR)
                                                  → MCP Lambda (Market Data)
                                                  → MCP Lambda (News)
                                → Salesforce (CRM query via REST)
                                → Salesforce (audit log write)
                                → Langfuse (trace write)
                                → MuleSoft (trade execution)
                                → Slack (HITL notification)
```

When stage 14 of the pipeline fails, the root cause could be in any of these systems. Without a deliberate operational strategy, debugging becomes a multi-tab, multi-console, multi-log-format scavenger hunt.

This document defines five layers of operational resilience:

1. **Unified Correlation** — one ID that follows a request across all 4 platforms
2. **Centralized Observability** — one place to see everything
3. **Circuit Breakers** — fail fast, not slow
4. **Health Checks** — know what's broken before users tell you
5. **Runbooks** — when it breaks, here's what to do

---

## Layer 1: Unified Correlation ID

The single most impactful operational improvement. Every request gets a UUID at the OpenClaw gateway, and that ID propagates to every system it touches.

### How It Works

```
User sends "Deep dive on NVIDIA" via Slack
  │
  ▼
OpenClaw Gateway generates: correlation_id = "006-abc123-def456"
  │
  ├── Bedrock call: x-correlation-id header
  ├── MCP Lambda call: x-correlation-id header → Lambda logs it
  ├── Salesforce REST call: X-Correlation-Id header
  │   → stored in IR_Audit_Log__c.Correlation_Id__c
  ├── Langfuse trace: trace_id = correlation_id (or metadata tag)
  ├── MuleSoft call: X-Correlation-Id header → MuleSoft logs it
  └── Slack HITL notification: includes correlation_id in message metadata
```

### Implementation

**OpenClaw side** — generate at gateway entry:
```python
import uuid

def generate_correlation_id():
    """Generate a correlation ID for cross-platform tracing."""
    return f"006-{uuid.uuid4().hex[:12]}"

# Attach to every outbound call
headers = {
    "X-Correlation-Id": correlation_id,
    "Content-Type": "application/json"
}
```

**MCP Lambda side** — extract and log:
```python
def lambda_handler(event, context):
    correlation_id = event.get("headers", {}).get(
        "x-correlation-id", "unknown"
    )
    logger.info(f"[{correlation_id}] MCP call received", extra={
        "correlation_id": correlation_id,
        "tool": event.get("tool_name"),
        "stage": event.get("pipeline_stage")
    })
    # ... process request ...
    return {
        "statusCode": 200,
        "headers": {"X-Correlation-Id": correlation_id},
        "body": result
    }
```

**Salesforce side** — store in audit log:
```
IR_Audit_Log__c:
  Correlation_Id__c: "006-abc123-def456"   ← new field
  Agent__c: "fsi-research"
  Action__c: "CRM_QUERY"
  Pipeline_Stage__c: "4"
  Timestamp__c: 2026-04-22T10:30:00Z
```

**Langfuse side** — tag traces:
```python
from langfuse import Langfuse

langfuse = Langfuse()
trace = langfuse.trace(
    name="research-brief",
    metadata={"correlation_id": correlation_id},
    tags=["pipeline", f"stage-{stage_number}"]
)
```

### The Payoff

When something breaks, you search ONE ID across all systems:
- CloudWatch Logs Insights: `filter @message like "006-abc123-def456"`
- Langfuse: search by metadata.correlation_id
- Salesforce: `SELECT * FROM IR_Audit_Log__c WHERE Correlation_Id__c = '006-abc123-def456'`
- MuleSoft: search API analytics by X-Correlation-Id

One ID. Four platforms. One search.

---

## Layer 2: Centralized Observability

### The Problem Today

006 has observability scattered across:
- **Langfuse** — LLM traces, pipeline stages, token costs
- **CloudWatch** — Lambda logs, API Gateway metrics, Bedrock metrics
- **Salesforce** — IR_Audit_Log__c records, debug logs
- **MuleSoft** — API analytics (if Phase 6 is active)

Four dashboards, four query languages, four auth models.

### The Solution: Two-Tier Model

Don't try to centralize everything into one tool. Instead:

**Tier 1: Langfuse (Agent-level observability)**
- Every pipeline stage is a Langfuse span
- Every MCP tool call is a child span with latency + result
- Every Salesforce query is a child span
- Every LLM call has token count, cost, model, latency
- Pipeline-level metrics: total cost, total time, pass/fail, HITL wait time

**Tier 2: CloudWatch (Infrastructure observability)**
- Lambda errors, cold starts, duration, memory
- API Gateway 4xx/5xx rates, latency p50/p95/p99
- Bedrock throttling events, model latency
- AgentCore health, container restarts

### Langfuse Trace Structure for a Research Brief

```
Trace: "Deep dive on NVIDIA" (correlation_id: 006-abc123)
│
├── Span: "Phase A: Scoping" (2.1s)
│   ├── Generation: intent-classification (Haiku, 340 tokens, $0.002)
│   └── Generation: query-decomposition (Sonnet, 1200 tokens, $0.02)
│
├── Span: "Phase B: Data Collection" (8.4s)
│   ├── Span: "MCP: sec-edgar/get_10k" (3.2s, success)
│   ├── Span: "MCP: market-data/get_quote" (1.1s, success)
│   ├── Span: "MCP: news-search/search" (2.8s, success)
│   └── Span: "SF: CRM query (coverage)" (1.3s, success)
│
├── Span: "Phase C: Synthesis" (12.3s)
│   ├── Generation: bull-case (Sonnet, 3400 tokens, $0.06)
│   ├── Generation: bear-case (Sonnet, 3100 tokens, $0.05)
│   ├── Generation: base-case (Sonnet, 2800 tokens, $0.05)
│   └── Generation: thesis-merge (Sonnet, 4200 tokens, $0.07)
│
├── Span: "HITL Gate 1" (waiting: 45s, approved)
│
├── Span: "Phase D-E: Analysis" (15.7s)
│   ├── Span: "DCF model" (sandbox, 4.2s, success)
│   ├── Span: "Comps model" (sandbox, 2.1s, success)
│   ├── Span: "Monte Carlo" (sandbox, 6.8s, success)
│   └── Generation: narrative (Sonnet, 5100 tokens, $0.09)
│
├── Span: "HITL Gate 2" (waiting: 120s, approved with edits)
│
├── Span: "Phase F-G: Writing + Review" (8.9s)
│   ├── Generation: brief-draft (Sonnet, 8200 tokens, $0.14)
│   ├── Generation: anti-fabrication-check (Sonnet, 2100 tokens, $0.04)
│   └── Generation: peer-review (Sonnet, 1800 tokens, $0.03)
│
├── Span: "HITL Gate 3" (waiting: 30s, approved)
│
├── Span: "Phase H: Publish" (2.1s)
│   ├── Span: "SF: write IR_Research_Note__c" (1.2s, success)
│   ├── Span: "SF: write IR_Audit_Log__c" (0.6s, success)
│   └── Span: "Langfuse: finalize trace" (0.3s)
│
└── Summary:
    Total time: 52.5s (+ 195s HITL wait)
    Total tokens: 32,240
    Total cost: $0.55
    Pipeline result: PASS
    Stages completed: 23/23
```

### CloudWatch Dashboard (Infrastructure)

Single dashboard with key widgets:

```
┌─────────────────────────────────────────────────────────────┐
│  006 Operations Dashboard                                    │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ MCP Lambdas  │  │ Bedrock      │  │ AgentCore    │      │
│  │ Error Rate   │  │ Throttles    │  │ Health       │      │
│  │ [0.2%]       │  │ [0/hr]       │  │ [healthy]    │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │ API Gateway  │  │ Lambda       │  │ Secrets Mgr  │      │
│  │ 5xx Rate     │  │ Cold Starts  │  │ Rotation     │      │
│  │ [0%]         │  │ [3/hr]       │  │ [OK]         │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Lambda Duration by Function (p50 / p95 / p99)       │    │
│  │ sec-edgar:    120ms / 450ms / 2100ms                │    │
│  │ market-data:  80ms  / 200ms / 800ms                 │    │
│  │ news-search:  150ms / 500ms / 1800ms                │    │
│  │ sf-crm:       200ms / 600ms / 1500ms                │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ Bedrock Token Usage (last 24h)                      │    │
│  │ Sonnet: 1.2M input / 340K output = $8.70            │    │
│  │ Haiku:  800K input / 120K output = $1.40            │    │
│  │ Total: $10.10                                       │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

---

## Layer 3: Circuit Breakers

### The Problem

The 23-stage pipeline calls external services at multiple stages. If the Market Data MCP server is down, the pipeline shouldn't retry 5 times per stage across 6 data-collection stages — that's 30 failed calls burning tokens on retry prompts.

### Three-Level Circuit Breaker

```
Level 1: Tool-Level Circuit Breaker
  Tracks: individual MCP tool failures (e.g., market-data/get_quote)
  Threshold: 3 consecutive failures in 60 seconds
  Action: OPEN → return cached/fallback data → log to Langfuse
  Recovery: HALF-OPEN after 120 seconds → test with 1 request

Level 2: Service-Level Circuit Breaker
  Tracks: entire MCP server failures (e.g., all market-data tools)
  Threshold: 5 failures across any tools in 120 seconds
  Action: OPEN → skip all market-data stages → notify analyst
  Recovery: HALF-OPEN after 300 seconds

Level 3: Platform-Level Circuit Breaker
  Tracks: entire platform failures (e.g., Salesforce REST API down)
  Threshold: 3 consecutive Salesforce call failures
  Action: OPEN → pipeline pauses → HITL notification
  Recovery: Manual reset required (platform outage is not transient)
```

### Implementation Pattern

```python
import time
from dataclasses import dataclass
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing, reject calls
    HALF_OPEN = "half_open" # Testing recovery

@dataclass
class CircuitBreaker:
    name: str
    failure_threshold: int = 3
    recovery_timeout: int = 120  # seconds
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0
    
    def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitOpenError(f"{self.name} circuit is OPEN")
        
        try:
            result = func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise

# One breaker per integration boundary
mcp_market_data = CircuitBreaker("market-data", failure_threshold=3)
mcp_sec_edgar = CircuitBreaker("sec-edgar", failure_threshold=3)
mcp_news = CircuitBreaker("news-search", failure_threshold=3)
sf_breaker = CircuitBreaker("salesforce", failure_threshold=3, recovery_timeout=300)
mulesoft_breaker = CircuitBreaker("mulesoft", failure_threshold=2, recovery_timeout=600)
```

### Graceful Degradation

When a circuit opens, the pipeline doesn't crash — it degrades:

| Circuit Open | Degradation | User Impact |
|-------------|-------------|-------------|
| Market Data MCP | Skip real-time pricing, use last-known from CRM | Brief says "pricing data unavailable, using last close" |
| SEC EDGAR MCP | Skip filing analysis stages | Brief omits filing section, notes the gap |
| News MCP | Skip news sentiment | Brief omits news section |
| Salesforce | Pipeline pauses, HITL notification | Analyst notified "CRM unavailable, pipeline paused" |
| Bedrock | Pipeline stops | Fatal — no LLM, no agent. Alert fires. |
| MuleSoft | Trade execution blocked | Research works, execution doesn't. Analyst notified. |

---

## Layer 4: Health Checks

### Proactive Health Check Script

A single script that tests every integration boundary before you discover it's broken from a user complaint.

```python
#!/usr/bin/env python3
"""006 Health Check — tests all 7+ integration boundaries."""

import requests, boto3, time, os

CHECKS = []

def check(name):
    def decorator(func):
        CHECKS.append((name, func))
        return func
    return decorator

@check("MCP: SEC EDGAR")
def check_sec_edgar():
    r = requests.get(
        f"{os.environ['MCP_GATEWAY_URL']}/sec-edgar",
        headers={"x-api-key": os.environ['MCP_API_KEY']},
        timeout=10
    )
    assert r.status_code == 200, f"Status {r.status_code}"

@check("MCP: Market Data")
def check_market_data():
    r = requests.get(
        f"{os.environ['MCP_GATEWAY_URL']}/market-data",
        headers={"x-api-key": os.environ['MCP_API_KEY']},
        timeout=10
    )
    assert r.status_code == 200, f"Status {r.status_code}"

@check("MCP: News Search")
def check_news():
    r = requests.get(
        f"{os.environ['MCP_GATEWAY_URL']}/news-search",
        headers={"x-api-key": os.environ['MCP_API_KEY']},
        timeout=10
    )
    assert r.status_code == 200, f"Status {r.status_code}"

@check("Salesforce REST API")
def check_salesforce():
    r = requests.get(
        f"{os.environ['SF_INSTANCE_URL']}/services/data/v66.0/limits",
        headers={"Authorization": f"Bearer {os.environ['SF_ACCESS_TOKEN']}"},
        timeout=10
    )
    assert r.status_code == 200, f"Status {r.status_code}"

@check("Bedrock: Sonnet 4.6")
def check_bedrock_sonnet():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = client.converse(
        modelId="us.anthropic.claude-sonnet-4-6",
        messages=[{"role": "user", "content": [{"text": "ping"}]}],
        inferenceConfig={"maxTokens": 5}
    )
    assert resp["stopReason"] in ["end_turn", "max_tokens"]

@check("Bedrock: Haiku 4.5")
def check_bedrock_haiku():
    client = boto3.client("bedrock-runtime", region_name="us-east-1")
    resp = client.converse(
        modelId="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        messages=[{"role": "user", "content": [{"text": "ping"}]}],
        inferenceConfig={"maxTokens": 5}
    )
    assert resp["stopReason"] in ["end_turn", "max_tokens"]

@check("Langfuse")
def check_langfuse():
    r = requests.get(
        f"{os.environ['LANGFUSE_BASE_URL']}/api/public/health",
        timeout=10
    )
    assert r.status_code == 200

@check("OpenClaw Gateway")
def check_openclaw():
    r = requests.get("http://localhost:18789/health", timeout=5)
    assert r.status_code == 200

def run_all():
    results = []
    for name, func in CHECKS:
        try:
            start = time.time()
            func()
            ms = int((time.time() - start) * 1000)
            results.append({"check": name, "status": "PASS", "ms": ms})
        except Exception as e:
            results.append({"check": name, "status": "FAIL", "error": str(e)})
    
    for r in results:
        icon = "✅" if r["status"] == "PASS" else "❌"
        detail = f'{r.get("ms", "?")}ms' if r["status"] == "PASS" else r["error"]
        print(f'{icon} {r["check"]}: {detail}')
    
    failed = [r for r in results if r["status"] == "FAIL"]
    if failed:
        print(f"\n⚠️  {len(failed)} check(s) failed")
        return 1
    print(f"\n✅ All {len(results)} checks passed")
    return 0

if __name__ == "__main__":
    exit(run_all())
```

### Scheduled Health Checks

Run every 5 minutes via EventBridge → Lambda. When a check fails, fire CloudWatch alarm → SNS → Slack notification.

---

## Layer 5: Runbooks

### Runbook 1: Pipeline Fails at Stage N

```
1. Get the correlation_id from the error message or Langfuse
2. Search Langfuse: find the trace, identify which span failed
3. Check the span error:
   - MCP timeout? → Check Lambda CloudWatch logs for that correlation_id
   - Bedrock throttle? → Check Bedrock CloudWatch metrics
   - Salesforce error? → Check IR_Audit_Log__c for that correlation_id
   - Sandbox error? → Check the code execution span in Langfuse
4. If MCP Lambda timed out:
   - Check if the external API (SEC EDGAR, Alpha Vantage, Tavily) is down
   - Check Lambda memory/duration metrics — did it OOM?
   - Check API Gateway logs for 504 Gateway Timeout
5. If Bedrock throttled:
   - Check current token usage vs account limits
   - Consider switching to Haiku for that stage temporarily
   - If persistent, request limit increase via AWS Support
6. If self-healing retry also failed:
   - Pipeline will pause at the next HITL gate
   - Analyst sees the partial brief with gaps noted
   - Fix the underlying issue, then re-run from the failed stage
```

### Runbook 2: Salesforce Token Expired

```
1. Symptom: All SF REST calls return 401
2. Check: sf org display --target-org my-org
3. If token expired:
   - Re-authenticate: sf org login web --alias my-org
   - Update Secrets Manager: aws secretsmanager update-secret ...
   - Restart OpenClaw to pick up new token
4. If Connected App revoked:
   - Re-create in SF Setup → App Manager
   - Update client_id/client_secret in Secrets Manager
5. Prevention: Set up Secrets Manager auto-rotation (quarterly)
```

### Runbook 3: Slack HITL Notification Not Arriving

```
1. Check OpenClaw logs for channel delivery errors
2. Verify SLACK_BOT_TOKEN is valid:
   curl -H "Authorization: Bearer $TOKEN" https://slack.com/api/auth.test
3. If token expired:
   - Regenerate in Slack App settings
   - Update in Secrets Manager
   - Restart OpenClaw
4. If Slack API is down:
   - Pipeline will wait at HITL gate indefinitely
   - Manually approve via OpenClaw API or web interface
5. Prevention: Add Slack token expiry check to health check script
```

### Runbook 4: MuleSoft Action Fails

```
1. Get correlation_id from the HITL approval message
2. Check MuleSoft API analytics for that correlation_id
3. Common failures:
   - 401: OAuth token expired → refresh via Secrets Manager
   - 429: Rate limited → back off, retry in 60s
   - 500: Downstream OMS/core banking error → escalate to ops
   - Timeout: MuleSoft gateway timeout → check API policy SLAs
4. The agent will NOT retry MuleSoft actions automatically (HITL required)
5. Analyst must re-approve after the issue is resolved
```

---

## Implementation Priority

| Priority | Layer | Effort | Impact |
|----------|-------|--------|--------|
| 1 (do first) | Correlation ID | 2 days | Transforms debugging from hours to minutes |
| 2 | Health Check Script | 1 day | Catches issues before users do |
| 3 | Langfuse Trace Structure | 2 days | Makes pipeline failures visible and costed |
| 4 | Circuit Breakers | 3 days | Prevents cascade failures and token waste |
| 5 | CloudWatch Dashboard | 1 day | Infrastructure visibility at a glance |
| 6 | Runbooks | 1 day | Reduces MTTR for known failure modes |
| 7 | Scheduled Health Checks | 1 day | Proactive monitoring |
| **Total** | | **~11 days** | |

---

## What This Doesn't Solve

1. **Salesforce governor limits.** If you hit SOQL query limits or API call limits, that's a Salesforce capacity problem, not an observability problem. Monitor via SF Event Monitoring.
2. **LLM quality degradation.** If Bedrock starts returning worse responses (model update, prompt drift), that's an eval problem. Use Langfuse scoring + the 25-query eval suite.
3. **Cost runaway.** If token usage spikes unexpectedly, you need budget alerts (Bedrock) and Langfuse cost tracking — not circuit breakers.
4. **Security incidents.** MNPI leakage, prompt injection, unauthorized access — these need the dual trust layer (Bedrock Guardrails + SF Models API), not operational tooling.

---

## Summary

The operational strategy for 006 is: **one correlation ID, two observability tiers, three circuit breaker levels, proactive health checks, and runbooks for known failure modes.**

The correlation ID alone transforms debugging from "which of 4 platforms broke?" to "search this ID everywhere." The circuit breakers prevent the cascade scenario (Lambda timeout → Bedrock throttle → Slack token expired) by failing fast at the first boundary. The health checks catch issues before users do.

Total implementation effort: ~11 engineering days. The payoff is the difference between a 2-hour incident investigation across 4 consoles and a 5-minute Langfuse trace lookup.

---

## Sources

- Salesforce correlation IDs: [developer.salesforce.com](https://developer.salesforce.com/blogs/2026/03/set-up-cross-system-observability-with-correlation-ids)
- OpenTelemetry for AI agents: [uptrace.dev](https://uptrace.dev/blog/opentelemetry-ai-systems), [ag2.ai](https://docs.ag2.ai/latest/docs/blog/2026/02/08/AG2-OpenTelemetry-Tracing/)
- Langfuse OpenTelemetry integration: [langfuse.com](https://langfuse.com/docs/opentelemetry/)
- Agent circuit breaker pattern: [agentic-patterns.com](https://www.agentic-patterns.com/patterns/agent-circuit-breaker)
- CloudWatch composite alarms: [AWS docs](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/Create_Composite_Alarm.html)
- Content was rephrased for compliance with licensing restrictions.
