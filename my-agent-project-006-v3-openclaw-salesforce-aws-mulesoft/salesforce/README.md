# 006 V3 Salesforce metadata

Deployable via:

```bash
sf project deploy start -d force-app -o <scratch-or-sandbox-alias>
```

## SObjects (4)

| Object | Sharing | Purpose |
|---|---|---|
| `Research_Brief__c` | ReadWrite | Canonical Sarah-authored research. Cross-persona handoff. |
| `Client_Inquiry__c` | ReadWrite | Client- or system-originated queue item for RM. Narratives 2/3/4 via `Type__c`. |
| `IR_Audit_Log__c` | Read (OWD) | Immutable audit. V3 adds `Research_Brief_Id__c` + `Client_Contact_Id__c`. |
| `IR_Pending_Approval__c` | ReadWrite | Dual-auth waiting queue. One row per action plan tripping thresholds. |

## Platform Event

`Research_Brief_Published__e` — fires from `ResearchBriefTrigger` when a brief flips to `Rm_Consumable__c = true` with MNPI cleared. Consumed by AWS EventBridge for CDC into Aurora/BKB.

## Apex (5 classes + 5 tests)

- `AuditLogTrigger` — insert guard (raw approval-token regex reject), immutability (non-senior cannot update/delete).
- `ResearchBriefTrigger` — blocks RM-consumable publish without MNPI-cleared; emits Platform Event.
- `MnpiValidator` — server-side regex validator for MNPI leakage.
- `SoqlSafe` — identifier + literal safety helpers, Apex mirror of Python `_soql_safe`.
- `SuitabilityCheckDeterministic` — server-side suitability rules matching the Python skill.

Each has a matching `*Test.cls`. `@isTest` coverage target >85% on trigger/class line count.

## Permission sets (3)

- **Senior_Compliance_Approver** — dual-auth second-signer; edit on `IR_Pending_Approval__c`, modify-all on `IR_Audit_Log__c`.
- **Research_Analyst** — Sarah's persona.
- **Wealth_Advisor** — RM persona.

Assign via `sf org assign permset -n <name> -o <alias>`.

## Data Cloud DLM

`dataCloudDataStreams/Research_Brief_Stream` points a DLM at `Research_Brief__c`. The DLM then joins:

```
Research_Brief__c.Ticker__c  <->  Position.Security
Position.AccountId           <->  Account.Id        (Household)
Account.Id                   <->  Contact.AccountId (Client)
```

This is the query the `research-awareness` skill runs (Query 2 of Narrative 1):

```sql
SELECT c.Id AS contact_id, c.Name AS client_name,
       p.Portfolio_Pct, rb.Id AS brief_id, rb.Thesis__c
  FROM Contact c
  JOIN Position__dlm p ON p.AccountId = c.AccountId
  JOIN Research_Brief__dlm rb ON rb.Ticker__c = p.Security
 WHERE p.Portfolio_Pct > 5 AND c.LastActivityDate < LAST_N_DAYS:7
```

The salesforce-crm MCP server applies MNPI redaction before returning — raw shares/market values never cross into the LLM.

## Scaffolder scripts

- `_scaffold_fields.py` — regenerates all field `-meta.xml` from one Python table.
- `_scaffold_apex.py` — regenerates Apex classes, permission sets, data stream.

Both idempotent. Re-run whenever schema or permissions shift.
