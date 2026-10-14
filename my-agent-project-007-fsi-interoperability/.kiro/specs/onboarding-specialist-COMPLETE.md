# Onboarding Specialist — COMPLETE

**Phase**: 3 (BD Operational Agents)
**Date**: v0.1.1 — 2025-01
**Playbook step**: 7 — COMPLETE (passed step 6 verification)

---

## Summary

- Canonical spec: `.kiro/specs/m12-onboarding-specialist.md`
  (Appendix A v0.1.1 fixes folded in)
- Canonical spec review: `.kiro/specs/m12-onboarding-specialist-REVIEW-v2.md`
  — **8.50/10 weighted, GO**
- Wrapper spec (this folder): `.kiro/specs/onboarding-specialist.md`
  (Phase-3 task-prompt alignment)
- Source: `src/m12_supervisor/specialists/onboarding/` + shared
  `src/m12_supervisor/specialists/_clients.py`
- Unit tests: 61 (covers every AC + model + stub adapter + validators)
- Integration tests: 8 (full trust-chain happy/BD-principal-review/
  dual-registered/CIP-fail+BSA-alert/KYC-deny/sanctions-hit/
  MNPI-before-vendor/audit-fail-closed)
- Security tests: 8 (module boundary + no-hardcoded-creds, shared)

---

## Verification gates

| Gate | Evidence |
|------|----------|
| Every stage emits M10 audit | `_terminal` + `_emit_bsa_326_alert` contracts + 6 test coverage |
| HITL gates respect M5 ComplianceConfig.hitl_timeout_hours | gate payload built via `DefaultHitlApprovalVerifier.build_gate_payload` (M8 canonical helper, same TTL knob) |
| Reg BI / Fiduciary gate branching by archetype | `kind == "bd_advisor"` + `registration_type in {bd_only, dual_registered}` -> `principal_review_queued` with `gate_kind="onboarding_principal_review"` — `test_bd_advisor_triggers_principal_review_queued`, `test_dual_registered_bd_advisor_triggers_principal_review` |
| KYC failure / AML hit branching | `test_kyc_vendor_denied_triggers_cip_failed`, `test_sanctions_hit_produces_cip_failed`, `test_sanctions_adapter_exception_is_fail_closed` |
| BSA §326 alert on CIP failure | `test_bsa_326_alert_emitted_on_cip_failure`, `test_bsa_326_alert_payload_whitelist`, `test_bsa_326_alert_has_no_mnpi_values` |
| No credentials in code | `test_no_hardcoded_creds_in_src`, `test_no_secret_value_patterns_in_src` |
| No direct vendor API calls — everything through M6 | `test_m12_never_imports_m6` (boundary); Phase-3 `StubKycAdapter` is a deterministic stand-in — production adapter wires through M6 at construction |
| M4 MNPI filter invoked BEFORE vendor calls | `test_mnpi_sanitizer_called`, `test_mnpi_failure_is_fail_closed`, `test_full_trust_chain_mnpi_invoked_before_kyc_vendor` (integration) |
| Fail-closed on compliance / KYC failure | `test_sanctions_adapter_exception_is_fail_closed`, `test_audit_failure_dominates_success_status`, `test_kyc_vendor_unavailable_is_failed` |
| Reason-code vocabulary (frozen set) | `VALID_ONBOARDING_REASONS` frozenset + `test_valid_onboarding_reasons_is_frozen` + `test_unknown_reason_code_rejected_at_construction` |

---

## Gap integration status (per task prompt)

| Gap | Status | Hook |
|-----|--------|------|
| Gap 1 Reg BI Doc Gen | Duck-typed (no hard import) | Channel builds `RegBiDocRequest` post-`cip_passed` for `bd_advisor` returns. No change required inside specialist when Gap 1 ships. |
| Gap 5 ERISA account-type gate | Duck-typed (no hard import) | Channel invokes Gap 5 checker BEFORE calling `start_onboarding`. Specialist stays ERISA-agnostic by design. |

No test file in this module imports from either gap; adding their
interfaces later is a purely additive change at the supervisor
construction site.

---

## Suite status

```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
1707 passed, 4 skipped, 5 xfailed, 1 xpassed, 101 warnings in 8-9s
```

Repeated 10 times — **10/10 stable green**.

---

## Out of scope (documented)

- Production Jumio/Onfido adapter is Phase 4. `StubKycAdapter` ships
  today; the real vendor adapter lands via DI at supervisor
  construction when the M11 TypeScript container is available.
- Initial-suitability assessment belongs to the client_service
  specialist; onboarding stops at `cip_passed` (or escalation).
- BSA §326 alert consumer is `compliance.gap4_bsa_aml_monitoring`
  (built in parallel by the compliance agent). Onboarding emits via
  `AuditClient.emit(event_type="bsa_326_cip_failure")` — the
  consumer reads from the audit stream.
