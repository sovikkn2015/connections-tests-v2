# M12 Onboarding Specialist Spec — LLMJ Review v1

## Scores (v1)

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Completeness | 25% | 7.0 | KYC / CIP / BSA 326 covered. MISSING: sanctions-list source, exact SSN format regex, age-over-18 boundary. |
| Accuracy | 20% | 7.5 | BSA 326 requirement mapping correct. Adapter Protocol + stub shape matches the pattern in m8_pipeline_engine. |
| Security | 20% | 8.0 | MNPI fields (SSN, DOB, address) never leak into LLM nor into the BSA alert payload. |
| Testability | 15% | 8.0 | AC mapping is tight. Missing: age=17.999 boundary test. |
| Design alignment | 10% | 8.0 | Matches ARCH-09 Phase 3. Re-uses shared Protocol clients. |
| Gaps | 10% | 6.5 | KYC vendor absence flagged. Missing: how the specialist consumes an M5 ComplianceConfig for the CTR/SAR thresholds (not used in onboarding but should be referenced). |

**Weighted: 7.40/10 — CONDITIONAL GO**.

## Required fixes

1. **Add §2.8 — CIP check exact validators**:
   - `name`: non-empty, non-digit-only, len ≥ 2.
   - `dob`: age ≥ 18 at `now_date` (UTC).
   - `address`: non-empty, len ≥ 10 chars, contains at least one digit.
   - `tax_id`: US SSN (9 digits with optional dashes) OR ITIN (9xx-xx-xxxx)
     OR EIN (2 digits-7 digits). Non-US country_code skips SSN format
     and checks length ≥ 5.
2. **Sanctions list source**: Phase 3 uses a hard-coded-in-test empty
   list. The production adapter is `sanctions.screen` called through
   M6 gateway (same pattern as KYC). Add a Protocol method on
   `KycAdapterProtocol.screen_sanctions(name, dob, country) -> bool`.
   In the stub, `tax_id` starting with "SAN" → sanctions hit.
3. **R2.4 BSA payload**: explicit list of permitted fields in the
   alert:
   `{firm_id, client_reference, failed_checks, trace_id, timestamp, actor_id, decision, reason, source="m12.onboarding", event_type="bsa_326_cip_failure"}`.
   Anything else is a bug.
4. **§2.5 ordering**: sanctions screen should run BEFORE the KYC
   vendor call so a sanctions hit is cheaper than a vendor round-trip.
   Update diagram.
5. **R4.2 gate_payload thread_id source**: thread_id is the
   `client_reference` prefixed with `"onb-"` for determinism. Tests
   reference this.
6. **Error surface invariant** (same as execution): no exception text
   in any audit payload or decision field. `reason_code` IS the
   error surface.
7. **Token budget cap enforced at call-site**, not trusted to the
   LLM. Specialist truncates prompt to 4096 bytes before provider call.

## Recommended

- Add `OnboardingDecision.bsa_326_alert_emitted` bool (already in
  the model — good, but emphasise it's checked by tests).
- Document that `status="kyc_pending"` is reserved for future async
  flow; Phase 3 never returns it.
