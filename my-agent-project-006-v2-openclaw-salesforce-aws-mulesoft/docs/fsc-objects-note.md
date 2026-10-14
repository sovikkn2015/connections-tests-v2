# Financial Services Cloud (FSC) Objects — Status Note

## Prerequisite: Salesforce Financial Services Cloud

The FSI Research Pipeline uses two managed-package objects from the **Salesforce Financial Services Cloud (FSC)** for client holdings data:

| Object | Purpose |
|--------|---------|
| `FinServ__FinancialAccount__c` | Client financial accounts (brokerage, retirement, trust) linked to standard `Account` |
| `FinServ__FinancialHolding__c` | Individual security positions within a financial account |

These are **managed package objects** — they ship with FSC and cannot be created via custom metadata. FSC must be enabled on the org for these objects to exist.

## Why Holdings Data Matters

The pipeline's Stage 2 (`_stage_2_crm_context`) queries holdings to answer questions like:
- "How many of our clients hold NVDA?"
- "Is TSLA a top holding across the book?"

This data feeds the research brief's CRM context section without exposing MNPI (dollar amounts, share quantities are stripped before any LLM prompt).

## Current Behavior

| Org Type | Behavior |
|----------|----------|
| **FSC-enabled org** | Stage 2 queries `FinServ__FinancialHolding__c`, returns holding count and top-holding flag. Seed script `seed-04-financial-holdings.apex` populates 60 holdings across 15 financial accounts. |
| **Standard org (no FSC)** | Stage 2 catches the 404/SOQL error, logs a warning, sets `holdings: []`, and continues. No pipeline failure. Seed script detects missing object and exits cleanly. |

## Objects Used and Field Mapping

### FinServ__FinancialAccount__c
- `FinServ__PrimaryOwner__c` → lookup to `Account`
- `Name` → account label (e.g., "Henderson Brokerage")
- `FinServ__FinancialAccountType__c` → Brokerage, Retirement, Trust, etc.
- `FinServ__Balance__c` → total account value (MNPI — never sent to LLM)

### FinServ__FinancialHolding__c
- `FinServ__FinancialAccount__c` → lookup to financial account
- `Name` → ticker symbol
- `FinServ__Shares__c` → share quantity (MNPI — never sent to LLM)
- `FinServ__Price__c` → price per share (MNPI — never sent to LLM)
- `FinServ__MarketValue__c` → total position value (MNPI — never sent to LLM)

## MNPI Enforcement

Per steering rule 26, the pipeline **never** sends these fields to LLM prompts or OpenClaw memory:
- `FinServ__Shares__c`
- `FinServ__Price__c`
- `FinServ__MarketValue__c`
- `FinServ__Balance__c`

Only aggregated, non-MNPI data is used: ticker, client count holding the security, and whether it qualifies as a "top holding" (by count, not value).

## How to Enable FSC

1. FSC is a paid Salesforce add-on. Contact your Salesforce AE to enable it on the org.
2. Once enabled, the `FinServ__*` objects appear automatically — no metadata deployment needed.
3. Run `sf apex run --file scripts/apex/seed-04-financial-holdings.apex` to populate test holdings.
4. The pipeline and seed scripts require zero code changes — they already handle both FSC and non-FSC orgs via try/catch.
