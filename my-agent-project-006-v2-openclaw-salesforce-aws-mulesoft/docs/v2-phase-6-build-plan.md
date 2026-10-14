# 006 v2: Phase 6 Build Plan — MuleSoft Action Execution

> 16-day Phase 6 breakdown. Mirrors the design-doc Phase 6 table but with
> mock-first sequencing so vendor approval is NOT on the critical path.

## Goals

1. End-to-end MuleSoft action flow (compliance → HITL → dual auth → MCP → audit) works in mock mode.
2. All 20 L5 eval queries (121–140) pass in mock mode.
3. One real vendor sandbox integrated (target: OMS first — Charles River or Schwab trade submission).
4. AgentCore is the default runtime. No localhost.

## Non-goals (Phase 6)

- Live production trades. v2 ships with sandbox + mock only.
- All 6 vendor sandboxes integrated. One is enough to prove the pattern. The rest follow in v2.1.
- Automatic retries on MuleSoft failures. Phase 6 surfaces failures to the user; retry is manual.

## Task Plan

| Task | Owner | Days | Dependency | Status |
|---|---|---|---|---|
| 6.1 Anypoint Connected App (sandbox) + client credentials in Secrets Manager | BD + eng | 1 | none | TODO |
| 6.2 Anypoint API Manager policies (client ID enforcement, rate limit, JSON threat, structured logging) | eng | 1 | 6.1 | TODO |
| 6.3 MCP tool: submit_order (mock + sandbox mode) | eng | 1.5 | 6.1 | SCAFFOLD DONE |
| 6.4 MCP tool: get_order_status | eng | 0.5 | 6.3 | SCAFFOLD DONE |
| 6.5 MCP tool: rebalance_portfolio | eng | 1 | 6.3 | SCAFFOLD DONE |
| 6.6 MCP tool: initiate_wire + get_settlement_status | eng | 1.5 | 6.1 | SCAFFOLD DONE |
| 6.7 MCP tool: run_kyc_screening | eng | 1 | 6.1 | SCAFFOLD DONE |
| 6.8 MCP tool: open_account | eng | 1 | 6.1 | SCAFFOLD DONE |
| 6.9 Skill: actions.py (single choke point, sequences compliance + HITL + dual auth + MCP + audit) | eng | 2 | 6.3–6.8 | SCAFFOLD DONE |
| 6.10 Skill: hitl.py (signed HMAC tokens, 5min TTL, WebSocket stream hitl event) | eng | 1.5 | 6.9 | SCAFFOLD DONE |
| 6.11 Skill: dual_auth.py (second approver routing, Senior_Compliance_Approver lookup) | eng | 1 | 6.10 | SCAFFOLD DONE |
| 6.12 Compliance pre-check integration (restricted list + MNPI + trading window + concentration) | eng | 1 | 6.9 | TODO |
| 6.13 Salesforce: IR_Pending_Approval__c SObject + Action__c picklist extension on IR_Audit_Log__c | eng | 0.5 | none | SCAFFOLD DONE |
| 6.14 Frontend: HitlPanel component + WebSocket stream hitl handler | eng | 1.5 | 6.10 | TODO |
| 6.15 Frontend: ApprovalHistoryTable (reads IR_Audit_Log__c via CRM MCP) | eng | 0.5 | 6.14 | TODO |
| 6.16 Eval: 006-v2-l5-eval.json with action_sequence ground truth | eng + QA | 1 | 6.9 | TODO |
| 6.17 Eval: run 20 L5 queries in mock mode, baseline scorecard | QA | 0.5 | 6.16 | TODO |
| 6.18 AgentCore promotion: flip openclaw.json to gateway.mode=deployed, update eval config to AgentCore URL | eng | 0.5 | 6.17 | DONE |
| 6.19 Vendor sandbox: OMS (first vendor — Charles River or Schwab) | eng + BD | 3 | 6.18 | BLOCKED (vendor app) |
| 6.20 L5 queries 121–131 re-run in sandbox mode (trades + rebalance) | QA | 1 | 6.19 | TODO |

Sum: 21 days of task estimate. Phase 6 budget is 16 days. The gap is absorbed by: vendor sandbox (6.19) runs IN PARALLEL with scaffold work, and 6.20 lands in Phase 7 if needed.

## Mock-First Sequencing Rationale

Vendor sandboxes take 4–8 weeks to approve (Charles River typical, Schwab 6–8). If Phase 6 blocked on vendor access, the team sits idle. The mock path lets every engineer work against a realistic MuleSoft response shape from day 1. When the first sandbox approval comes in, flip MULESOFT_MODE=sandbox for that one MCP tool handler and keep the rest mock.

## Definition of Done (Phase 6)

- [ ] 20/20 L5 queries pass in mock mode
- [ ] 1 vendor sandbox integrated end-to-end (any of the 6)
- [ ] Full trust pipeline documented in design-doc section "MuleSoft Compound Query Examples"
- [ ] AgentCore is the default runtime (no localhost in eval config)
- [ ] HITL approval flow tested with a real human on Slack + web UI
- [ ] Dual auth tested with two distinct Salesforce users
- [ ] Zero credentials in git (verified by .kiro/hooks/006-no-credentials.kiro.hook)
- [ ] Approval token replay attack test passes (token rejected outside 5min TTL)
- [ ] Compliance DENY hard-stops action (no override flag, verified in eval)

## Risk Register

| Risk | Likelihood | Mitigation |
|---|---|---|
| Vendor sandbox denied/delayed | HIGH | Mock mode means scaffold ships without it; vendor = incremental add |
| HITL timeout misconfigured → trader waits | MED | 5min TTL is default; ops playbook for after-hours |
| Dual approver offline at 4pm Friday | MED | IR_Pending_Approval__c queue + on-call escalation list |
| Approval token replay | LOW | HMAC + plan_hash binding + TTL; attack-tested in 6.10 |
| MNPI in HITL plan summary leaking to LLM later | LOW | Plan summaries are render-only to humans; no re-prompting |
| Compliance DENY bypass attempt | LOW | Hard-coded no-override in actions.py; no config flag |
