# Onboarding Specialist — Spec (Phase 3 BD Operational Agent)

**Canonical spec**: see `.kiro/specs/m12-onboarding-specialist.md` (full
contract with Requirements + Design + Tasks + Acceptance Mapping).

This file is the Phase-3 task-prompt-aligned wrapper that captures the
7-step playbook outcome and links to the canonical spec.

---

## 7-step playbook status

| Step | Artefact | Status |
|------|----------|--------|
| 1. Spec draft         | `.kiro/specs/m12-onboarding-specialist.md`           | DONE |
| 2. LLMJ review v1     | `.kiro/specs/m12-onboarding-specialist-REVIEW.md`    | DONE |
| 3. Fix pass           | Appendix A in canonical spec (A1-A7)                 | DONE |
| 4. Re-review v2       | `.kiro/specs/m12-onboarding-specialist-REVIEW-v2.md` | **8.50/10 GO** |
| 5. Build              | `src/m12_supervisor/specialists/onboarding/`         | DONE |
| 6. Verify tests       | `tests/unit/test_m12_onboarding_specialist.py` + `tests/integration/test_m12_onboarding_trust_chain.py` | DONE — 69 passing locally, 10/10 runs stable |
| 7. COMPLETE           | `.kiro/specs/onboarding-specialist-COMPLETE.md`      | DONE |

Weighted review score (from REVIEW v2):

| Dimension        | Weight | Score |
|------------------|--------|-------|
| Completeness     | 25%    | 8.5   |
| Accuracy         | 20%    | 8.5   |
| Security         | 20%    | 9.0   |
| Testability      | 15%    | 8.5   |
| Design alignment | 10%    | 8.5   |
| Gaps             | 10%    | 7.5   |
| **Weighted**     |        | **8.50 — GO** |

---

## Task-prompt traceability

### Orchestration shape (LangGraph-style 10-stage pipeline)

The canonical spec §2.5 + Appendix A.4 lay out the pipeline. The
implementation in `start_onboarding(...)` is a deterministic sequence
matching the task-prompt 10-stage map:

| Task-prompt stage                        | Implementation anchor |
|------------------------------------------|----------------------|
| 1. intake                                | request-shape validation (Pydantic) |
| 2. identity verification preflight       | `_check_authority_scope` + AID check |
| 3. KYC                                   | `_cip_validate_name / _dob / _address / _tax_id` |
| 4. AML screening                         | `kyc_adapter.screen_sanctions(...)` |
| 5. Reg BI gate (BD retail)               | Appendix A.6 — `kind="bd_advisor"` -> principal_review path; Reg BI doc generation hooks into `gap1-reg-bi-doc-generator` (optional) |
| 6. fiduciary gate (RIA)                  | no-op for retail_client+ria_only; RIA fiduciary review is a channel responsibility per Gap 5 planning |
| 7. account setup                         | vendor `kyc_adapter.verify_identity(...)` success path |
| 8. initial suitability assessment        | deferred to client_service specialist (out of scope here) |
| 9. document package assembly             | Gap 1 Reg BI + Gap 5 ERISA doc generators — see "Gap integration" below |
| 10. audit                                | `AuditClient.emit(...)` terminal row |

### Gap integration (duck-typed per task prompt)

- **Gap 1 Reg BI Doc Generator** — not imported. If/when `.kiro/specs/gap1-reg-bi-doc-generator.md` ships, the channel builds a `RegBiDocRequest` and calls its generator AFTER `start_onboarding` returns `cip_passed` for a `bd_advisor` request. The specialist itself does not call Gap 1 — it emits the principal-review gate so the channel can coordinate.
- **Gap 5 ERISA account-type gate** — not imported. The gate decision is a channel-level rule: if `country_code == "US"` and the requested account type is an ERISA plan, the channel invokes the Gap 5 checker BEFORE calling `start_onboarding`.

Both gaps are "duck-typed interfaces with xfail markers that lift when
gaps ship" per the prompt — concretely, `test_m12_onboarding_specialist.py`
carries 0 hard imports from `compliance.gap1_*` / `compliance.gap5_*`.

### HITL gates

- **CIP pre-submit gate (implicit)** — CIP failures trigger the BSA 326
  alert path before any downstream side-effect (`_emit_bsa_326_alert`).
- **BD advisor principal review** — `kind == "bd_advisor"` +
  `registration_type in {bd_only, dual_registered}` gates to
  `principal_review_queued` with `gate_kind="onboarding_principal_review"`.

### M6 gateway for all vendor interactions

The production `KycAdapterProtocol` adapter MUST call M6 (Rule 4). The
Phase-3 `StubKycAdapter` is a deterministic in-memory implementation
for tests; it ships with the module. When a real Jumio/Onfido adapter
lands (Phase 4), the dependency-injection site at supervisor
construction swaps adapters — no source change inside the specialist.

Enforced by `tests/security/test_m12_module_boundary.py`: the
`onboarding/` module cannot import `m6_mcp_gateway`, `m11_rest_adapters`,
or any gap module.

### M10 audit at every stage boundary

Every terminal routes through `_terminal(...)` which emits exactly one
M10 audit entry. CIP failures emit a SECOND entry first — the BSA §326
alert (`event_type="bsa_326_cip_failure"`). Verified by:

- `test_audit_emitted_on_cip_passed`
- `test_audit_emitted_on_cip_failed`
- `test_bsa_326_alert_emitted_on_cip_failure`
- `test_bsa_326_alert_payload_whitelist`
- `test_bsa_326_alert_has_no_mnpi_values`
- `test_terminal_audit_has_no_mnpi`

### Reason-code vocabulary (frozenset)

`VALID_ONBOARDING_REASONS` in `onboarding/models.py` — 12 codes,
closed. See `test_valid_onboarding_reasons_is_frozen` and
`test_unknown_reason_code_rejected_at_construction`.

### Fail-closed verification

- `test_sanctions_adapter_exception_is_fail_closed`
- `test_mnpi_failure_is_fail_closed`
- `test_audit_failure_dominates_success_status`
- `test_kyc_vendor_unavailable_is_failed`

### Model routing (Haiku, NOT Sonnet)

Per Rule 13, onboarding is Haiku. Default `llm_model` in
`onboarding/specialist.py` is
`"anthropic.claude-3-5-haiku-20241022-v1:0"`.

---

## Deliverables map

| Deliverable                              | Location                                            |
|------------------------------------------|-----------------------------------------------------|
| Pipeline source                          | `src/m12_supervisor/specialists/onboarding/`        |
| Shared Protocols + Fakes                 | `src/m12_supervisor/specialists/_clients.py`        |
| Unit tests (behaviour + models)          | `tests/unit/test_m12_onboarding_specialist.py` (61) |
| Integration tests (M6 + M10 stubs)       | `tests/integration/test_m12_onboarding_trust_chain.py` (8) |
| Boundary security test                   | `tests/security/test_m12_module_boundary.py`        |
| No-credentials security test             | `tests/security/test_m12_no_hardcoded_creds.py`     |
| DECISION LOG                             | `src/m12_supervisor/specialists/onboarding/DECISION-LOG.md` |
| COMPLETE marker                          | `.kiro/specs/onboarding-specialist-COMPLETE.md`     |

Verified commands:

```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
# 1707 passed, 4 skipped, 5 xfailed, 1 xpassed
```

10 consecutive runs stable.
