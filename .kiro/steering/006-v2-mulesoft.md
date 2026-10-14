---
inclusion: fileMatch
fileMatchPattern: "my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/**"
---

# Project 006 v2: MuleSoft Phase 6 — Steering

v2 inherits ALL rules from v1 steering (`.kiro/steering/006-openclaw-fsi.md`).
This file adds Phase 6 (MuleSoft) specifics. When the two conflict, v2 wins
for files in the v2 tree.

## Design Documents (Source of Truth)
- #[[file:my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/docs/v2-design-doc.md]]
- #[[file:my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/docs/v2-mulesoft-integration-plan.md]]
- #[[file:my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/docs/v2-phase-6-build-plan.md]]
- #[[file:my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/docs/v2-vendor-onboarding-tracker.md]]
- #[[file:my-agent-project-006-v2-openclaw-salesforce-aws-mulesoft/docs/v2-eval-l5-ground-truth.md]]

## Phase 6 Non-Negotiable Rules

### Single choke point
1. All MuleSoft calls go through `openclaw/skills/mulesoft-api/actions.py`. NEVER call the mulesoft-actions MCP server from anywhere else. Approval token plumbing depends on this.

### HITL
2. Every MuleSoft write action (submit_order, rebalance_portfolio, initiate_wire, run_kyc_screening, open_account) requires a valid ApprovalToken (5 min TTL, HMAC-SHA256 signed).
3. The token is bound to a specific plan_hash — it cannot be reused across actions.
4. Timeouts = ACTION ABORTED. No silent skip.

### Dual auth
5. Wire > $100K, trade notional > $500K, any account closure → dual approval required.
6. Second approver MUST be distinct from first approver.
7. Second approver MUST hold Senior_Compliance_Approver permission set.

### Compliance pre-check
8. Before ANY action reaches HITL, run compliance-screening skill. DENY = hard stop. No override.
9. Compliance DENY writes an IR_Audit_Log__c record with Action__c = COMPLIANCE_BLOCKED even though no MuleSoft call was made.

### Audit
10. Every attempt (approved, rejected, timed out, compliance-blocked) writes to IR_Audit_Log__c.
11. Dual-auth waiting states additionally write to IR_Pending_Approval__c.
12. Action__c picklist must be extended in v2: TRADE_SUBMITTED, TRADE_REJECTED, WIRE_INITIATED, WIRE_BLOCKED, KYC_SCREENING, ACCOUNT_OPENED, COMPLIANCE_BLOCKED.
13. MuleSoft_Reference__c captured from MCP server response. Approved_By__c and Dual_Approver__c required where applicable.

### Mock mode
14. MCP server defaults to MULESOFT_MODE=mock until vendor sandbox approval.
15. Mock mode must return realistic shapes (order IDs, refs) so the full pipeline is eval-covered before any live vendor call.
16. All 20 L5 eval queries (121-140) must pass in mock mode BEFORE the first vendor sandbox call.

### Deployment
17. AgentCore is required for v2. NO localhost gateway for Phase 6. The openclaw.json gateway mode must be deployed, not local.
18. MULESOFT_CLIENT_ID, MULESOFT_CLIENT_SECRET, MULESOFT_BASE_URL only in AWS Secrets Manager. Zero credentials in git.
19. Lambda for mulesoft-actions runs in a VPC with NAT egress. Anypoint allowlists the NAT EIP.

### Security
20. Bedrock Guardrail topic "financial_actions" added to flag attempts to bypass HITL ("execute without approval", "skip compliance", etc.).
21. MNPI still never reaches the LLM. Action plan summaries shown in HITL are allowed — HITL goes to a human, not a prompt.
22. Approval tokens NEVER logged to Langfuse in raw form — hash only.

## 005/v1 Mistakes to Avoid (Phase 6 specific)
- DO NOT skip HITL with a config flag. There is no "autopilot mode" for trades.
- DO NOT let the LLM synthesize MuleSoft arguments from user text directly — structured ActionPlan first, user reviews, then signed token.
- DO NOT call the mulesoft-actions MCP server from AutoResearchClaw pipeline stages. Pipelines recommend, the skill executes.
- DO NOT log approval tokens. Log the plan hash, approver id, and timestamp only.
- DO NOT mix mock mode and sandbox responses in a single eval run.
