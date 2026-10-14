---
name: Compliance Screening
slug: compliance-screening
version: 1.0.0
description: >-
  FINRA compliance checks — restricted list, MNPI detection, trading windows,
  concentration limits. Must run before any trade recommendation or action.
trigger-keywords:
  - compliance
  - restricted
  - can I trade
  - MNPI
  - trading window
  - concentration
  - pre-trade
applicable-stages:
  - 5
  - 9
  - 20
  - 22
  - 23
metadata:
  requires:
    env:
      - SF_ACCESS_TOKEN
      - SF_INSTANCE_URL
---

# Compliance Screening

## Checks (run in order)

### 1. Restricted List Check

Query IR_Audit_Log__c for RESTRICTED_LIST_ADD entries:

```bash
curl "$SF_INSTANCE_URL/services/data/v66.0/query/?q=SELECT+Action__c,Query__c,Timestamp__c+FROM+IR_Audit_Log__c+WHERE+Action__c='RESTRICTED_LIST_ADD'+AND+Query__c+LIKE+'%25TICKER%25'+ORDER+BY+Timestamp__c+DESC+LIMIT+1" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN"
```

If result found: BLOCK the action. Log Compliance_Status__c = 'FAIL'.

### 2. MNPI Check

Query IR_Audit_Log__c for recent MNPI flags:

```bash
curl "$SF_INSTANCE_URL/services/data/v66.0/query/?q=SELECT+MNPI_Flag__c,Query__c,Timestamp__c+FROM+IR_Audit_Log__c+WHERE+MNPI_Flag__c=true+AND+Query__c+LIKE+'%25TICKER%25'+AND+Timestamp__c>=LAST_N_DAYS:30+ORDER+BY+Timestamp__c+DESC" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN"
```

If MNPI flags found: WARN and require compliance officer review.

> **Limitation:** The 30-day lookback for MNPI flags (`LAST_N_DAYS:30`) is a
> default. MNPI restrictions persist until public disclosure, which may exceed
> 30 days. For production use, replace `LAST_N_DAYS:30` with a query against a
> dedicated MNPI tracking object that tracks disclosure dates explicitly.

### 3. Trading Window Check

Check if the company is in a blackout period (typically 2 weeks before earnings):

- Query IR_Watchlist__c for Earnings_Date__c
- If earnings date is within 14 days: WARN about blackout period

### 4. Concentration Check

- Query client holdings for the ticker
- Calculate position as % of total portfolio
- If > 10% single-stock concentration: WARN
- If > 25% sector concentration: WARN

## Response Format

Always return structured compliance result:

```json
{
  "ticker": "NVDA",
  "restricted_list": "CLEAR",
  "mnpi_check": "CLEAR",
  "trading_window": "OPEN",
  "concentration": "WITHIN_LIMITS",
  "overall": "PASS",
  "warnings": [],
  "blocks": []
}
```

## Audit

Log every compliance check to IR_Audit_Log__c with Action__c = 'COMPLIANCE_CHECK'.

```bash
curl -X POST "$SF_INSTANCE_URL/services/data/v66.0/sobjects/IR_Audit_Log__c" \
  -H "Authorization: Bearer $SF_ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "Agent__c": "OpenClaw-IR",
    "Action__c": "COMPLIANCE_CHECK",
    "Query__c": "compliance screening for TICKER",
    "Analyst__c": "analyst name",
    "Timestamp__c": "2026-04-08T12:00:00Z",
    "Data_Sources_Used__c": "IR_Audit_Log__c, IR_Watchlist__c",
    "Trace_Id__c": "langfuse-trace-id",
    "Compliance_Status__c": "PASS",
    "MNPI_Flag__c": false
  }'
```
