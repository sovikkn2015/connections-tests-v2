#!/usr/bin/env bash
# Pre-seed Salesforce new-org with rows needed for narrative demos:
#  - Narrative 2 (RM takes client inquiry, routes to Sarah): 1 Client_Inquiry__c
#  - Narrative 3 (Risk alert flow): 2 Research_Brief__c rows
#
# Idempotent: skips rows that already exist by External Id / unique field.
# Zero credentials printed.

set -e

TARGET="${TARGET_ORG:-new-org}"

echo "==> Seeding Client_Inquiry__c..."
sf data create record --target-org "$TARGET" --sobject Client_Inquiry__c \
  --values "Status__c=Open Channel__c=Email Inquiry_Text__c='Can you brief me on NVDA before earnings?' Ticker__c=NVDA Severity__c=Normal" \
  --json 2>&1 | head -3 || true

echo ""
echo "==> Seeding Research_Brief__c for NVDA..."
sf data create record --target-org "$TARGET" --sobject Research_Brief__c \
  --values "Ticker__c=NVDA Thesis__c='Data center revenue up 59% on Blackwell ramp.' Author_Agent_Id__c=research_orchestrator Compliance_Status__c=ALLOW Mnpi_Cleared__c=true Rm_Consumable__c=true Sentiment_Score__c=0.82 Client_Demand__c='Pre-earnings coverage' Risk_Factors__c='Supply chain, export controls, H20 inventory charge'" \
  --json 2>&1 | head -3 || true

echo ""
echo "==> Seeding Research_Brief__c for MSFT..."
sf data create record --target-org "$TARGET" --sobject Research_Brief__c \
  --values "Ticker__c=MSFT Thesis__c='Azure acceleration + Copilot monetization driving double-digit growth.' Author_Agent_Id__c=research_orchestrator Compliance_Status__c=ALLOW Mnpi_Cleared__c=true Rm_Consumable__c=true Sentiment_Score__c=0.71 Client_Demand__c='Cloud infrastructure coverage' Risk_Factors__c='AI capex cycle, regulatory scrutiny'" \
  --json 2>&1 | head -3 || true

echo ""
echo "==> Seeding IR_Audit_Log__c (narrative anchor row)..."
sf data create record --target-org "$TARGET" --sobject IR_Audit_Log__c \
  --values "Agent_Id__c=research_orchestrator Principal_Id__c=sarah@demo.com Action__c=RESEARCH_PUBLISHED Compliance_Status__c=ALLOW Session_Id__c=seed-demo-001 Correlation_Id__c=seed-demo-001 Timestamp__c=$(date -u +%Y-%m-%dT%H:%M:%S.000Z)" \
  --json 2>&1 | head -3 || true

echo ""
echo "Done."
