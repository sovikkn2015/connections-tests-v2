---
name: MuleSoft Action Execution
slug: mulesoft-api
version: 1.0.0
description: >-
  Execute financial actions via MuleSoft Anypoint — trade execution, wire transfers,
  KYC screening, account opening, portfolio rebalancing. ALL actions require HITL
  approval before execution.
trigger-keywords:
  - trade
  - buy
  - sell
  - trim
  - wire
  - transfer
  - rebalance
  - open account
  - KYC
  - execute
applicable-stages: []
metadata:
  requires:
    env:
      - MULESOFT_CLIENT_ID
      - MULESOFT_CLIENT_SECRET
      - MULESOFT_BASE_URL
      - SF_ACCESS_TOKEN
      - SF_INSTANCE_URL
---

# MuleSoft Action Execution

## CRITICAL: HITL Required for ALL Actions

Every MuleSoft action MUST follow this flow:
1. Gather context (SF skill + MCP servers)
2. Run compliance pre-check (compliance-screening skill)
3. Present action plan to user with [Approve] [Reject] [Edit] options
4. WAIT for explicit human approval
5. Only execute after approval
6. Log everything to IR_Audit_Log__c
7. Monitor for completion and update CRM

NEVER execute a MuleSoft action without human approval. This is a FINRA requirement.

## Authentication

OAuth2 client_credentials flow:
```bash
# Get access token
curl -X POST "$MULESOFT_BASE_URL/oauth/token" \
  -d "grant_type=client_credentials" \
  -d "client_id=$MULESOFT_CLIENT_ID" \
  -d "client_secret=$MULESOFT_CLIENT_SECRET"
```

## Available Actions

### submit_order
Submit a trade order to the OMS.
```bash
curl -X POST "$MULESOFT_BASE_URL/api/v1/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "ticker": "NVDA",
    "side": "SELL",
    "quantity": 1800,
    "orderType": "MARKET",
    "clientId": "CLIENT_F",
    "accountId": "F-BROKERAGE-001"
  }'
```
Returns: orderId, status, estimatedProceeds

### get_order_status
Check order fill status.
```bash
curl "$MULESOFT_BASE_URL/api/v1/orders/{orderId}" \
  -H "Authorization: Bearer $TOKEN"
```
Returns: status (SUBMITTED/PARTIAL/FILLED/CANCELLED), avgPrice, filledQty

### rebalance_portfolio
Submit a basket of rebalancing trades.
```bash
curl -X POST "$MULESOFT_BASE_URL/api/v1/rebalance" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "CLIENT_D",
    "trades": [
      {"ticker": "NVDA", "side": "SELL", "quantity": 55},
      {"ticker": "JNJ", "side": "BUY", "quantity": 215}
    ]
  }'
```

### initiate_wire
Submit a wire transfer.
```bash
curl -X POST "$MULESOFT_BASE_URL/api/v1/wires" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "CLIENT_A",
    "fromAccount": "A-BROKERAGE-001",
    "toAccount": "CHASE-****4821",
    "amount": 250000.00,
    "currency": "USD",
    "priority": "SAME_DAY"
  }'
```
Dual auth required for wires > $100K.

### run_kyc_screening
Run KYC/AML screening on a prospect.
```bash
curl -X POST "$MULESOFT_BASE_URL/api/v1/kyc" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientName": "Jane Smith",
    "level": "ENHANCED",
    "checks": ["sanctions", "pep", "adverse_media"]
  }'
```

### open_account
Open a new account in core banking + custodian.
```bash
curl -X POST "$MULESOFT_BASE_URL/api/v1/accounts" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "JANE_SMITH",
    "accountType": "MANAGED",
    "jurisdiction": "US",
    "riskProfile": "MODERATE"
  }'
```

## Audit Trail

Every MuleSoft action creates an IR_Audit_Log__c record with:
- Action__c: TRADE_SUBMITTED / WIRE_INITIATED / KYC_SCREENING / ACCOUNT_OPENED
- Decision_Rationale__c: includes compliance pre-check results and HITL approval
- Trace_Id__c: links to Langfuse trace

## Dual Authorization

Required for:
- Wire transfers > $100,000
- Trade orders > $500,000
- Account closures

Two separate approvals required before execution.
