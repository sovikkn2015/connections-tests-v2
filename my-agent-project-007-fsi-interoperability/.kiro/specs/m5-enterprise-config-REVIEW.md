# LLMJ Review: M5 Enterprise Config Loader — First Pass

> Reviewer: Trust Layer Specialist (LLMJ mode)
> Spec Reviewed: `.kiro/specs/m5-enterprise-config.md`
> Date: Review v1
> Verdict: **CONDITIONAL GO** — 6.95/10
> Action: Fix required issues, then re-review

---

## Scoring

| Dimension | Weight | Score | Weighted | Notes |
|-----------|--------|-------|----------|-------|
| COMPLETENESS | 25% | 7.0 | 1.75 | Missing enum definitions for inline constraints, no config versioning |
| ACCURACY | 20% | 7.5 | 1.50 | Mostly matches design docs; LEI validation incomplete |
| SECURITY | 20% | 7.0 | 1.40 | validate_no_secrets good but pattern list incomplete |
| TESTABILITY | 15% | 7.0 | 1.05 | ACs testable but AC8.6 "emits a warning" is vague |
| DESIGN ALIGNMENT | 10% | 7.0 | 0.70 | Matches ARCH-07/ARCH-09; minor runtime enum note needed |
| GAPS | 10% | 5.5 | 0.55 | Several gaps identified below |
| **TOTAL** | **100%** | | **6.95** | **CONDITIONAL GO** |

---

## REQUIRED Fixes (Must address before GO)

### FIX-1: Runtime enum value format note (ACCURACY)
**Issue:** Spec defines `Runtime` enum with `managed_agents` and `strands_sdk` (underscores). The ARCHIVED config files used `managed-agents` (hyphens). The spec should explicitly note that the canonical format uses underscores per project convention (all enums use snake_case), and this is a deliberate correction from the ARCHIVED format.
**Fix:** Add a note in the Design section documenting the underscore convention.

### FIX-2: Missing `SuitabilityStandard` enum definition (COMPLETENESS)
**Issue:** AC8.1 references `suitability_standard` as `enum: fiduciary, reg_bi` but this enum is not in the Enum Registry table. It should be a proper enum like the others.
**Fix:** Add `SuitabilityStandard` enum with 2 values to the Enum Registry.

### FIX-3: Missing `PrincipalReviewMode` and `TimeoutAction` enum definitions (COMPLETENESS)
**Issue:** AC8.3 references `mode` as `enum: pre_use, post_use` and `timeout_action` as `enum: block, escalate` but these are not in the Enum Registry.
**Fix:** Add `PrincipalReviewMode` (2 values) and `TimeoutAction` (2 values) to the Enum Registry. Total: 8 enums.

### FIX-4: LEI validation regex missing (ACCURACY)
**Issue:** AC4.3 says "20-character alphanumeric (ISO 17442 format)" but doesn't specify the regex. ISO 17442 LEIs are 18 alphanumeric chars + 2 check digits: `^[A-Z0-9]{18}[0-9]{2}$`.
**Fix:** Add the exact regex pattern to AC4.3.

### FIX-5: AC8.6 warning mechanism not testable (TESTABILITY)
**Issue:** AC8.6 says "a validator emits a warning" but doesn't specify how. Python `warnings.warn()`? A log? A field?
**Fix:** Specify: "a `model_validator` raises `UserWarning` via `warnings.warn()` capturable with `pytest.warns(UserWarning)`".

### FIX-6: validate_no_secrets pattern list incomplete (SECURITY)
**Issue:** Missing patterns: PEM private key headers (`-----BEGIN`), GitHub PATs (`ghp_`), Slack tokens (`xoxb-`), connection strings (`postgresql://`, `mongodb://`, `redis://`).
**Fix:** Expand the pattern list in the Security Constraints section.

### FIX-7: No config version field (GAPS)
**Issue:** M3 has `SCHEMA_VERSION`. M5 should have `config_version` for forward/backward compatibility as config schema evolves. Consumers need to know which config format they're loading.
**Fix:** Add `config_version: str` (required, semver) to `EnterpriseConfig`. Add `CONFIG_VERSION = "0.1.0"` constant.

### FIX-8: ChannelConfig validation too loose (COMPLETENESS)
**Issue:** AC7.3 says "include but are not limited to" — open-ended. For a strict config loader, unknown channels should be rejected. Prevents injection of arbitrary channel names.
**Fix:** Define a `VALID_CHANNELS` frozenset and validate against it. New channels require a code update.

---

## RECOMMENDED Improvements (Not blocking)

### REC-1: Add config file hash for provenance
Per ARCH-06 Gap 2, the loaded config should include a `config_hash` (SHA-256 of raw YAML) so M10 audit can reference which config was active during a request.

### REC-2: Add `get_opa_bundle_prefix()` helper
Helper method returning OPA bundle path prefix for the archetype. Useful for M2/M4 consumers.

---

## Summary

Solid first pass. Core model structure is correct, field definitions are comprehensive, security constraints are appropriate. Main gaps: missing enum definitions for inline constraints (FIX-2/3), incomplete LEI validation (FIX-4), untestable warning (FIX-5), missing config versioning (FIX-7), loose channel validation (FIX-8).

Score: **6.95/10 — CONDITIONAL GO**. Fix the 8 required issues, then re-review.
