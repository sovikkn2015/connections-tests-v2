# Execution Specialist — Spec (Phase 3 BD Operational Agent)

**Canonical spec**: see `.kiro/specs/m12-execution-specialist.md` (full
contract with Requirements + Design + Tasks + Acceptance Mapping).

This file is the Phase-3 task-prompt-aligned wrapper that captures the
7-step playbook outcome and links to the canonical spec.

---

## 7-step playbook status

| Step | Artefact | Status |
|------|----------|--------|
| 1. Spec draft         | `.kiro/specs/m12-execution-specialist.md`           | DONE |
| 2. LLMJ review v1     | `.kiro/specs/m12-execution-specialist-REVIEW.md`    | DONE |
| 3. Fix pass           | Appendix A in canonical spec (A1-A8)                | DONE |
| 4. Re-review v2       | `.kiro/specs/m12-execution-specialist-REVIEW-v2.md` | **8.40/10 GO** |
| 5. Build              | `src/m12_supervisor/specialists/execution/`         | DONE |
| 6. Verify tests       | `tests/unit/test_m12_execution_specialist{,_models}.py` + `tests/integration/test_m12_execution_trust_chain.py` | DONE — 64 passing locally, 10/10 runs stable |
| 7. COMPLETE           | `.kiro/specs/execution-specialist-COMPLETE.md`      | DONE |

Weighted review score (from REVIEW v2):

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 8.5   |
| Testability      | 15%    | 8.5   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |
| **Weighted**     |        | **8.40 — GO** |

---

## Task-prompt traceability

This section maps the Phase-3 task prompt bullets to spec / code
artefacts.

### Orchestration shape (LangGraph-style 8-stage pipeline)

The canonical spec §2.5 lays out an 8-step state machine identical in
spirit to M8's stage graph; the concrete implementation is a single
`prepare_order(...)` method whose body is the explicit stage
progression (matching §2.5 exactly):

1. `intake`                        -> `_check_authority_scope` / AID shape validation
2. `suitability`                   -> policy `action="order.draft"` with concentration / wall flags
3. `compliance`                    -> OPA ALLOW/DENY/ESCALATE branching
4. HITL preflight                  -> `exec_hitl_required` gate (Rule 8 fail-closed)
5. `order construction`            -> LLM-extracted OR channel-supplied `OrderTicket`
6. `principal review` (BD only)    -> `_bd_principal_review_gate` per §R4 + A6
7. `submit`                        -> `GatewayClient.call(tool="broker.order_submit")`
8. `audit`                         -> `AuditClient.emit(...)` every terminal

### HITL gates (two gates per task prompt)

- **Gate 1** — compliance preflight / `exec_hitl_required` (default M8 gate 1 semantics).
- **Gate 2** — BD principal review / `exec_principal_review_required`.

Both map onto `HitlGatePayload.gate_id=1` for simplicity (stage 7
stage-number semantics) with `summary.gate_kind` distinguishing
`"execution_hitl"` vs `"principal_review"`.

### Order types (Phase 3 scope)

The canonical spec §2.3 `OrderTicket.order_type` is `Literal["market",
"limit", "stop", "stop_limit"]`. These cover the four task-prompt
families:

| Prompt family         | OrderTicket mapping                          |
|-----------------------|----------------------------------------------|
| `equity_market`       | `order_type="market"`                         |
| `equity_limit`        | `order_type="limit"` with `limit_price`       |
| `mutual_fund_trade`   | `order_type="market"` with `time_in_force="day"` (mutual funds price at NAV, day order) |
| `rebalance_basket`    | Channel issues N `ExecutionRequest`s, one per leg; the specialist stays single-ticket |

FIX bridge (Phase 4) is not invoked here — the MCP tool name is the
neutral `broker.order_submit` that any broker adapter can implement.

### M6 gateway for all vendor interactions

Enforced by `tests/security/test_m12_module_boundary.py`:
`m12_supervisor.specialists.execution.*` cannot import `m6_mcp_gateway`.
All gateway calls go through `GatewayClient.call(...)` (Protocol) via
dependency injection. The production adapter bridging this Protocol to
`TrustAwareGateway` lives at the supervisor construction site (not
inside the specialist module).

### M10 audit at every stage boundary

Every return path in `ExecutionSpecialist.prepare_order` flows through
`_terminal(...)` which invokes `AuditClient.emit(...)` exactly once
(Rule 6, fail-closed). Verified by:

- `test_audit_emitted_on_drafted_terminal`
- `test_audit_emitted_on_compliance_denied`
- `test_audit_emitted_on_submitted`
- `test_audit_failure_dominates_submitted_status`

### Reason-code vocabulary (frozenset)

`VALID_EXECUTION_REASONS` in `execution/models.py` — 15 codes, closed.
See `test_valid_execution_reasons_frozen` and
`test_execution_decision_rejects_unknown_reason_code`.

### Fail-closed verification

- `test_error_surface_hygiene_no_exception_text`
- `test_mnpi_failure_is_fail_closed`
- `test_audit_failure_dominates_submitted_status`
- `test_policy_deny_is_terminal`

### Model routing (Haiku, NOT Sonnet)

Per Rule 13, execution is Haiku. The default `llm_model` constant in
`execution/specialist.py` is
`"anthropic.claude-3-5-haiku-20241022-v1:0"`.  Asserted by
`test_llm_invoked_with_haiku_budget_when_drafting`.

---

## Deliverables map

| Deliverable                              | Location                                           |
|------------------------------------------|----------------------------------------------------|
| Pipeline source                          | `src/m12_supervisor/specialists/execution/`        |
| Shared Protocols + Fakes                 | `src/m12_supervisor/specialists/_clients.py`       |
| Unit tests (models)                      | `tests/unit/test_m12_execution_specialist_models.py` (24) |
| Unit tests (behaviour)                   | `tests/unit/test_m12_execution_specialist.py` (34) |
| Integration tests (M6 + M10 stubs)       | `tests/integration/test_m12_execution_trust_chain.py` (6) |
| Boundary security test                   | `tests/security/test_m12_module_boundary.py`       |
| No-credentials security test             | `tests/security/test_m12_no_hardcoded_creds.py`    |
| DECISION LOG                             | `src/m12_supervisor/specialists/execution/DECISION-LOG.md` |
| COMPLETE marker                          | `.kiro/specs/execution-specialist-COMPLETE.md`     |

Verified commands:

```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
# 1707 passed, 4 skipped, 5 xfailed, 1 xpassed
```

10 consecutive runs stable.
