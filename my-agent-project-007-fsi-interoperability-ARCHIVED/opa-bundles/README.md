# OPA Policy Bundles — Project 007

Status: STUB (directory structure created, production rules need compliance SME validation)

## Bundle Structure

```
opa-bundles/
  authority/                    Authorization rules
    restricted_list.rego        Restricted securities check (ARCH-06 Gap 3 sample)
    execution.rego              HITL gate enforcement
    client_access.rego          Advisor-to-client access control
    communication_review.rego   FINRA 2210 principal review classification
  mnpi/                         MNPI filtering rules
    tier3_wealth_management.rego  Tier 3 field-level filtering
    tier4_independent_ria.rego    Tier 4 field-level filtering
  account_type/                 ERISA/IRA/trust rules (ARCH-06 Gap 5)
    erisa.rego                  Prohibited transactions, concentration
    ira.rego                    RMD tracking, Roth 5-year rule
    trust.rego                  Duty of impartiality
  bsa_aml/                      BSA/AML monitoring (ARCH-06 Gap 4)
    sar_triggers.rego           Structuring, velocity, geography
    ctr.rego                    $10K+ threshold
  jurisdiction/                 Per-jurisdiction overlays (ARCH-06 Gap 7)
    us/                         Reg BI, FINRA, SEC rules
    eu/                         MiFID II, GDPR, DORA (Phase 5)
    uk/                         FCA Consumer Duty (Phase 5)
  data/                         Rule data (restricted lists, thresholds)
    restricted_list.json        Sample restricted securities
    high_risk_jurisdictions.json  BSA/AML geographic risk
```

## Current State

Design-phase code samples exist in ARCH-06 (v3 Compliance Gap Designs).
These need to be extracted into production .rego files and validated by compliance SME.

Production rules will be written in Phase 1 (Weeks 4-18) with compliance SME co-design.
