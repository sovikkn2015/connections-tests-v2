---
name: Salesforce CRM for FSI
slug: salesforce-crm-fsi
version: 1.0.0
description: >-
  Query and manage Salesforce CRM data for FSI investment research.
  SOQL queries, record CRUD, coverage data, watchlists, research notes,
  and audit logging.
trigger-keywords:
  - client
  - portfolio
  - holdings
  - coverage
  - watchlist
  - research note
  - audit
  - account
  - who covers
  - analyst
applicable-stages:
  - 1
  - 2
  - 3
  - 4
  - 5
  - 6
  - 7
  - 22
  - 23
metadata:
  requires:
    env:
      - SF_ACCESS_TOKEN
      - SF_INSTANCE_URL
---

# Salesforce CRM for FSI

## Authentication

Bearer token auth: `Authorization: Bearer $SF_ACCESS_TOKEN`
Instance URL: `$SF_INSTANCE_URL`
API Version: v66.0

## Available Objects

### IR_Company__c

Company master data.
Fields: Name, Ticker__c, Sector__c, Exchange__c, Market_Cap__c, Description__c.

```bash
# Get company by ticker
curl "$SF_INSTANCE_URL/services/data/v66.0/query/?q=SELECT+Id,Name,Ticker__c,Sector__c,Exchange__c,Market_Cap__c,Description__c+FROM+IR_Company__c+WHERE+Ticker__c='NVDA'" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN"
```

### IR_Coverage__c

Analyst-stock assignments.
Fields: Company__c, Analyst__c, Rating__c, Target_Price__c, Last_Updated__c, Last_Action__c.

```bash
# Get coverage for a ticker
curl "$SF_INSTANCE_URL/services/data/v66.0/query/?q=SELECT+Analyst__c,Rating__c,Target_Price__c,Last_Updated__c,Last_Action__c+FROM+IR_Coverage__c+WHERE+Company__r.Ticker__c='NVDA'" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN"
```

### IR_Watchlist__c

Stocks being tracked.
Fields: Company__c, Reason__c, Priority__c, Added_Date__c, Earnings_Date__c.

### IR_Research_Note__c

Published research briefs.
Fields: Company__c, Ticker__c, Analyst__c, Rating__c, Target_Price__c, Summary__c,
Full_Brief__c, Thesis__c, Catalysts__c, Risks__c, Generated_Date__c, Pipeline_Run_Id__c.

### IR_Audit_Log__c

FINRA compliance trail.
Fields: Agent__c, Action__c, Query__c, Analyst__c, Timestamp__c, Data_Sources_Used__c,
Pipeline_Stage__c, Decision_Rationale__c, Trace_Id__c, Compliance_Status__c, MNPI_Flag__c.

## MNPI Rules

- NEVER include holdings amounts, trade intentions, or wire details in LLM prompts
- NEVER store MNPI data in OpenClaw memory
- Filter MNPI fields before sending to any external service
- If a query touches MNPI data, log MNPI_Flag__c = true in audit

## Audit Logging

EVERY agent action must create an IR_Audit_Log__c record:

```bash
curl -X POST "$SF_INSTANCE_URL/services/data/v66.0/sobjects/IR_Audit_Log__c" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "Agent__c": "OpenClaw-IR",
    "Action__c": "QUERY",
    "Query__c": "user query text",
    "Analyst__c": "analyst name",
    "Timestamp__c": "2026-04-08T12:00:00Z",
    "Data_Sources_Used__c": "IR_Company__c, IR_Coverage__c",
    "Trace_Id__c": "langfuse-trace-id",
    "Compliance_Status__c": "PASS",
    "MNPI_Flag__c": false
  }'
```
