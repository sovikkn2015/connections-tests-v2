# Phase 5D: Performance Testing Guide

## Overview

This guide covers load testing the WA_P1to5_Advisor agent, measuring key performance metrics, and establishing SLAs for production deployment. Agentforce agents have unique performance characteristics due to the LLM inference + Data Cloud query chain.

---

## Performance Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│  User Query: "Tell me about the Johnson household"               │
│                                                                  │
│  ┌─────────┐   ┌──────────┐   ┌──────────┐   ┌──────────────┐  │
│  │ Channel  │──▶│  Topic   │──▶│  Apex    │──▶│  Data Cloud  │  │
│  │ Routing  │   │ Selector │   │  Action  │   │  CdpQuery    │  │
│  │          │   │ (LLM)    │   │          │   │              │  │
│  │ ~100ms   │   │ ~1-3s    │   │ ~200ms   │   │ ~500ms-2s    │  │
│  └─────────┘   └──────────┘   └──────────┘   └──────────────┘  │
│                                                                  │
│  Total expected latency: 2-6 seconds per query                   │
└──────────────────────────────────────────────────────────────────┘
```

## Key Metrics to Measure

### 1. Response Time (End-to-End)

| Metric | Target | Acceptable | Degraded |
|--------|--------|------------|----------|
| P50 (median) | < 3 seconds | < 5 seconds | > 5 seconds |
| P90 | < 5 seconds | < 8 seconds | > 8 seconds |
| P99 | < 8 seconds | < 12 seconds | > 12 seconds |
| Max | < 15 seconds | < 20 seconds | > 20 seconds |

### 2. Component Latency Breakdown

| Component | Target | How to Measure |
|-----------|--------|---------------|
| Channel routing | < 200ms | Messaging platform logs |
| Topic selection (LLM) | < 2s | Agent debug logs |
| Apex action execution | < 500ms | Apex debug logs (`Limits.getCpuTime()`) |
| Data Cloud query (CdpQuery) | < 1s | CdpQuery response metadata |
| Response formatting | < 200ms | Agent debug logs |

### 3. Throughput

| Metric | Target |
|--------|--------|
| Concurrent users | 100+ |
| Queries per minute | 200+ |
| Sustained load (1 hour) | No degradation |

### 4. Error Rates

| Metric | Target |
|--------|--------|
| Agent error rate | < 1% |
| Topic misrouting rate | < 5% |
| Data Cloud timeout rate | < 2% |
| Action failure rate | < 1% |

## Testing Approaches

### Approach 1: Salesforce Agent Test Framework (Built-in)

Use the `sf agent test` CLI to run test suites repeatedly:

```bash
# Run the full test suite
sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --verbose

# Run multiple times in sequence to measure consistency
for i in {1..10}; do
  echo "Run $i:"
  sf agent test run --api-name WA_P1to5_Advisor_Test --wait 10 --result-format json \
    | jq '.result.testCases[] | {query: .utterance, topicMatch: .topicSequenceMatch, duration: .duration}'
  sleep 2
done
```

**Pros:** Native, no setup, tests real agent behavior
**Cons:** Sequential only, can't simulate concurrent users

### Approach 2: Salesforce API Load Testing

Use a load testing tool (k6, JMeter, Locust) to hit the Agentforce API:

#### k6 Script Example

```javascript
// perf-test/agent-load-test.js
import http from 'k6/http';
import { check, sleep } from 'k6';
import { Rate, Trend } from 'k6/metrics';

const errorRate = new Rate('errors');
const responseTrend = new Trend('agent_response_time');

export const options = {
  stages: [
    { duration: '2m', target: 10 },   // Ramp up to 10 users
    { duration: '5m', target: 50 },   // Ramp up to 50 users
    { duration: '10m', target: 100 }, // Sustain 100 users
    { duration: '2m', target: 0 },    // Ramp down
  ],
  thresholds: {
    'agent_response_time': ['p(95)<8000'],  // 95% under 8s
    'errors': ['rate<0.01'],                 // <1% error rate
  },
};

const BASE_URL = __ENV.SF_INSTANCE_URL;
const ACCESS_TOKEN = __ENV.SF_ACCESS_TOKEN;

const queries = [
  'Tell me about the Johnson household',
  'How is Wei Chen\'s portfolio doing?',
  'What are the Patels\' financial goals?',
  'Prep me for my meeting with Carlos Martinez',
  'What\'s our policy on margin accounts?',
];

export default function () {
  const query = queries[Math.floor(Math.random() * queries.length)];

  const res = http.post(
    `${BASE_URL}/services/data/v66.0/einstein/agent/conversations`,
    JSON.stringify({
      agentName: 'WA_P1to5_Advisor',
      message: query,
    }),
    {
      headers: {
        'Authorization': `Bearer ${ACCESS_TOKEN}`,
        'Content-Type': 'application/json',
      },
      timeout: '20s',
    }
  );

  responseTrend.add(res.timings.duration);
  errorRate.add(res.status !== 200);

  check(res, {
    'status is 200': (r) => r.status === 200,
    'response has content': (r) => r.body.length > 0,
    'response time < 8s': (r) => r.timings.duration < 8000,
  });

  sleep(Math.random() * 3 + 1); // 1-4 second think time
}
```

**Run:**
```bash
SF_INSTANCE_URL=https://yourorg.my.salesforce.com \
SF_ACCESS_TOKEN=$(sf org display --json | jq -r '.result.accessToken') \
k6 run perf-test/agent-load-test.js
```

### Approach 3: Apex-Level Performance Testing

Measure individual action performance directly:

```apex
// scripts/apex/perf-test-actions.apex

Integer iterations = 50;
List<Long> durations = new List<Long>();

for (Integer i = 0; i < iterations; i++) {
    Long startTime = System.currentTimeMillis();
    
    DC_ClientLookupAction.LookupInput input = new DC_ClientLookupAction.LookupInput();
    input.clientName = 'Johnson';
    DC_ClientLookupAction.getClient360(new List<DC_ClientLookupAction.LookupInput>{ input });
    
    Long duration = System.currentTimeMillis() - startTime;
    durations.add(duration);
}

// Calculate stats
durations.sort();
Long p50 = durations[durations.size() / 2];
Long p90 = durations[(Integer)(durations.size() * 0.9)];
Long p99 = durations[(Integer)(durations.size() * 0.99)];

System.debug('DC_ClientLookupAction Performance (' + iterations + ' iterations):');
System.debug('  P50: ' + p50 + 'ms');
System.debug('  P90: ' + p90 + 'ms');
System.debug('  P99: ' + p99 + 'ms');
System.debug('  Min: ' + durations[0] + 'ms');
System.debug('  Max: ' + durations[durations.size() - 1] + 'ms');
```

### Approach 4: Data Cloud Query Performance

Isolate Data Cloud query latency:

```apex
// scripts/apex/perf-test-cdpquery.apex

Integer iterations = 20;
List<Long> durations = new List<Long>();

for (Integer i = 0; i < iterations; i++) {
    Long startTime = System.currentTimeMillis();
    
    ConnectApi.CdpQueryInput q = new ConnectApi.CdpQueryInput();
    q.sql = 'SELECT Name__c, Total_AUM_c__c, Risk_Profile_c__c FROM WA_Household_c_Home__dlm LIMIT 5';
    ConnectApi.CdpQueryOutputV2 r = ConnectApi.CdpQuery.queryAnsiSqlV2(q);
    
    Long duration = System.currentTimeMillis() - startTime;
    durations.add(duration);
    
    // Avoid rate limiting
    // Note: In production, add appropriate delays
}

durations.sort();
System.debug('CdpQuery Performance (' + iterations + ' iterations):');
System.debug('  P50: ' + durations[durations.size() / 2] + 'ms');
System.debug('  P90: ' + durations[(Integer)(durations.size() * 0.9)] + 'ms');
System.debug('  Max: ' + durations[durations.size() - 1] + 'ms');
```

---

## SLA Recommendations

### Tier 1: Internal Advisor Use (Recommended Starting Point)

| Metric | SLA |
|--------|-----|
| Availability | 99.5% during business hours (8am-6pm ET) |
| Response time (P95) | < 8 seconds |
| Error rate | < 2% |
| Topic accuracy | > 90% |
| Action accuracy | > 85% |
| Planned maintenance window | Weekends 2am-6am ET |

### Tier 2: Client-Facing Portal

| Metric | SLA |
|--------|-----|
| Availability | 99.9% (24/7) |
| Response time (P95) | < 5 seconds |
| Error rate | < 0.5% |
| Topic accuracy | > 95% |
| Action accuracy | > 90% |
| Escalation to human | < 30 seconds |

### Tier 3: Regulatory/Compliance

| Metric | SLA |
|--------|-----|
| Audit log completeness | 100% (every interaction logged) |
| Data accuracy | 100% (matches source of record) |
| Access control enforcement | 100% (no unauthorized data access) |
| Log retention | 7 years minimum |

---

## Monitoring and Alerting

### Key Dashboards

1. **Agent Performance Dashboard**
   - Response time distribution (histogram)
   - Error rate over time
   - Queries per hour
   - Topic distribution (pie chart)

2. **Data Cloud Performance Dashboard**
   - CdpQuery latency over time
   - Query volume by DLM object
   - Cache hit rate
   - Failed queries

3. **Compliance Dashboard**
   - Audit log volume
   - Access denied events
   - Client data access by advisor
   - Unusual access patterns

### Alert Thresholds

| Alert | Condition | Severity | Action |
|-------|-----------|----------|--------|
| High latency | P95 > 10s for 5 min | Warning | Investigate Data Cloud performance |
| Error spike | Error rate > 5% for 2 min | Critical | Page on-call engineer |
| Topic misrouting | Accuracy < 80% for 1 hour | Warning | Review agent instructions |
| Audit gap | Missing logs for > 5 min | Critical | Investigate logging pipeline |
| Unauthorized access | Any access denied event | Info | Log for compliance review |

---

## Performance Optimization Tips

1. **Data Cloud Query Optimization**
   - Add indexes to frequently queried DLM fields (Name__c, Household_c__c)
   - Use `LIMIT` clauses on all queries
   - Avoid `SELECT *` — specify only needed fields
   - Cache frequently accessed household data in Platform Cache

2. **Apex Action Optimization**
   - Batch multiple CdpQuery calls where possible
   - Use `@future` for audit logging (non-blocking)
   - Implement Platform Cache for repeat lookups (TTL: 5 minutes)

3. **Agent Configuration**
   - Keep topic descriptions concise and distinct (faster routing)
   - Limit the number of topics (< 15 for optimal routing)
   - Use specific action descriptions (reduces LLM ambiguity)

4. **Infrastructure**
   - Use a sandbox close to your Data Cloud region
   - Monitor Salesforce Trust (status.salesforce.com) for platform issues
   - Schedule load tests during off-peak hours

---

## Test Execution Checklist

- [ ] Baseline: Run 10 sequential agent tests, record response times
- [ ] Apex perf: Run perf-test-actions.apex for each DC_* action
- [ ] CdpQuery perf: Run perf-test-cdpquery.apex, record P50/P90/P99
- [ ] Load test: Run k6 script with 10 → 50 → 100 concurrent users
- [ ] Sustained load: Run 100 users for 10 minutes, check for degradation
- [ ] Error analysis: Review all errors from load test, categorize root causes
- [ ] SLA validation: Confirm metrics meet Tier 1 SLAs
- [ ] Document results: Record baseline metrics for future comparison
