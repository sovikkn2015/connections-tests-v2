---
name: Audit Logging
slug: audit-logging
version: 1.0.0
description: >-
  Writes audit trail records to Salesforce IR_Audit_Log__c for FINRA compliance.
  Every agent action must be logged. Dual-write to Langfuse (engineering) and
  Salesforce (regulatory).
trigger-keywords:
  - audit
  - log
  - trace
  - compliance record
applicable-stages:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 8
  - 9
  - 10
  - 11
  - 12
  - 13
  - 14
  - 15
  - 16
  - 17
  - 18
  - 19
  - 20
  - 21
  - 22
  - 23
metadata:
  requires:
    env:
      - SF_ACCESS_TOKEN
      - SF_INSTANCE_URL
      - LANGFUSE_SECRET_KEY
      - LANGFUSE_PUBLIC_KEY
      - LANGFUSE_BASE_URL
---

# Audit Logging

## Dual-Write Strategy

Every action writes to TWO systems:

1. **Langfuse** — engineering observability (traces, spans, costs, latency)
2. **IR_Audit_Log__c** — regulatory compliance (who, what, when, approved by — FINRA 7-year retention)

Shared trace_id links both systems.

## Langfuse Integration

```python
from langfuse import Langfuse
import os

langfuse = Langfuse(
    secret_key=os.environ["LANGFUSE_SECRET_KEY"],
    public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
    host=os.environ["LANGFUSE_BASE_URL"]
)

# Create trace for each agent run
trace = langfuse.trace(name="agent-query", metadata={"analyst": "Sarah Chen"})
span = trace.span(name="tool-call", metadata={"tool": "get_quote", "ticker": "NVDA"})
span.end()
```

## Salesforce Audit Record

```bash
curl -X POST "$SF_INSTANCE_URL/services/data/v66.0/sobjects/IR_Audit_Log__c" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "Agent__c": "OpenClaw-IR",
    "Action__c": "ACTION_TYPE",
    "Query__c": "original user query",
    "Analyst__c": "analyst name from session",
    "Timestamp__c": "ISO-8601 timestamp",
    "Data_Sources_Used__c": "comma-separated list of tools/objects used",
    "Pipeline_Stage__c": "stage name if in pipeline",
    "Decision_Rationale__c": "why this action was taken",
    "Trace_Id__c": "langfuse trace ID",
    "Compliance_Status__c": "PASS or FAIL",
    "MNPI_Flag__c": false
  }'
```

## Action Types

- `QUERY` — standard data retrieval
- `RESEARCH_BRIEF` — pipeline-generated brief
- `COMPLIANCE_CHECK` — pre-trade or periodic check
- `TRADE_REVIEW` — trade recommendation review
- `DATA_ACCESS` — external data source access
- `RESTRICTED_LIST_ADD` — ticker added to restricted list
- `RESTRICTED_LIST_REMOVE` — ticker removed
- `TRADE_SUBMITTED` — MuleSoft trade execution (Phase 6)
- `WIRE_INITIATED` — MuleSoft wire transfer (Phase 6)
- `KYC_SCREENING` — MuleSoft KYC check (Phase 6)
- `ACCOUNT_OPENED` — MuleSoft account creation (Phase 6)

## Rules

- EVERY agent action gets an audit record. No exceptions.
- Trace_Id__c must link to the Langfuse trace for the same action.
- MNPI_Flag__c = true if the action touched material non-public information.
- Compliance_Status__c = 'FAIL' if any compliance check failed.
