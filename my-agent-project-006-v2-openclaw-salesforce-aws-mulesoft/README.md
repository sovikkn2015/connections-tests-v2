# Project 006 v2: OpenClaw + Salesforce + AWS + MuleSoft

> Version 2 of 006. Adds Phase 6: MuleSoft action execution with HITL.
> v1 baseline: `../my-agent-project-006-v1-openclaw-salesforce-aws/`
> Date: April 2026

## What's different vs v1

| Area | v1 (Phases 1–5) | v2 (adds Phase 6) |
|---|---|---|
| Research briefs | Yes | Yes (unchanged) |
| CRM queries | Yes | Yes (unchanged) |
| Trade execution | Recommendation only | Full submission via MuleSoft + HITL |
| Wire transfers | N/A | Via MuleSoft + dual auth |
| KYC screening | N/A | Via MuleSoft to World-Check/Refinitiv |
| Account opening | N/A | Via MuleSoft + compliance HITL |
| Rebalancing | Calculates trades only | Submits basket via MuleSoft |
| MCP servers | 4 (SEC EDGAR, Market Data, News, SF-CRM) | 5 (adds MuleSoft Actions) |
| Skills | 6 | 6 (mulesoft-api skill is fully implemented) |
| Audit objects | IR_Audit_Log__c | + IR_Pending_Approval__c for dual auth |
| Deployment | AgentCore optional | AgentCore required (no localhost for trade orders) |

## Inheritance

v2 starts from v1's exact state. Production code, compliance rules, AutoResearchClaw pipeline, MCP servers, and the frontend are copied as baseline. Phase 6 layers on top. It does not modify Phase 1–5 behavior.

This project is self-contained. All code is copied, not symlinked, so v1 remains frozen as the no-action-execution reference.

## Directory Layout

```
my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/
├── aws/
│   ├── mcp-servers/
│   │   ├── mulesoft-actions/     <- NEW: Phase 6 MCP server
│   │   ├── sec-edgar/            (copied from v1)
│   │   ├── market-data/          (copied from v1)
│   │   ├── news-search/          (copied from v1)
│   │   ├── salesforce-crm/       (copied from v1)
│   │   └── shared/
│   ├── sam-template.yaml         (extended with MuleSoftActionsFunction)
│   └── secrets-rotation.yaml
├── openclaw/
│   ├── skills/
│   │   ├── mulesoft-api/         <- NEW: implementation (was SKILL.md only in v1)
│   │   ├── audit-logging/        (copied from v1)
│   │   ├── compliance-screening/ (copied from v1)
│   │   ├── financial-analysis/   (copied from v1)
│   │   ├── fsi-research/         (copied from v1)
│   │   └── salesforce-crm/       (copied from v1)
│   └── openclaw.json             (gateway mode: deployed)
├── force-app/
│   └── main/default/objects/
│       └── IR_Pending_Approval__c/   <- NEW: dual auth queue
├── mulesoft/                     <- NEW: Anypoint artifacts
│   ├── process-apis/             <- DataWeave transforms, RAML specs
│   └── policies/                 <- API Manager policies
├── frontend/                     (copied from v1, adds HitlPanel)
├── docs/
│   ├── v2-design-doc.md
│   ├── v2-mulesoft-integration-plan.md
│   ├── v2-phase-6-build-plan.md
│   ├── v2-vendor-onboarding-tracker.md
│   └── v2-eval-l5-ground-truth.md
├── evaluation/
│   └── 006-v2-l5-eval.json       <- L5 queries 121–140 with action_sequence ground truth
├── scripts/
│   ├── deploy-mulesoft-mcp.sh    <- NEW
│   └── test-mulesoft-mock.py     <- NEW
└── sfdx-project.json
```

## Phase 6 Build Status

See `docs/v2-phase-6-build-plan.md` for the 16-day task breakdown.

- [ ] 6.1 MuleSoft Connected App (sandbox)
- [ ] 6.2 Anypoint API policies
- [ ] 6.3 submit_order process API + MCP tool
- [ ] 6.4 get_order_status process API + MCP tool
- [ ] 6.5 rebalance_portfolio process API + MCP tool
- [ ] 6.6 initiate_wire process API + MCP tool
- [ ] 6.7 get_settlement_status process API + MCP tool
- [ ] 6.8 run_kyc_screening process API + MCP tool
- [ ] 6.9 open_account process API + MCP tool
- [ ] 6.10 HITL approval flow in skill + frontend HitlPanel
- [ ] 6.11 Dual auth (wire >$100K, trade >$500K)
- [ ] 6.12 Compliance pre-check integration
- [ ] 6.13 Audit: IR_Pending_Approval__c + Action__c picklist extension
- [ ] 6.14 L5 queries 121–140 pass in mock mode
- [ ] 6.15 Vendor sandbox integration (one at a time)

## Mock Mode

Until vendor sandboxes are approved (4–8 weeks), the MuleSoft MCP server runs in
MULESOFT_MODE=mock and returns canned orderIds, wire refs, KYC results. This
unblocks the Phase 6 critical path: end-to-end HITL flow is testable and eval-covered
before a single real vendor API call.

## Rules (same as v1, plus Phase 6 specifics)

1. All MuleSoft actions require HITL approval. No autonomous execution.
2. Dual auth required for wire >$100K and trade >$500K.
3. Every action writes to IR_Audit_Log__c with Approved_By__c, Dual_Approver__c, MuleSoft_Reference__c.
4. AgentCore is the default runtime. No localhost gateway for Phase 6 operations.
5. Mock mode is the default for eval. Vendor sandbox only after L5 suite passes in mock.
