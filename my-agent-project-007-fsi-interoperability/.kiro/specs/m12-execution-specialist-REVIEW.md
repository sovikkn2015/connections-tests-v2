# M12 Execution Specialist Spec — LLMJ Review v1

**Reviewer persona**: harsh specialist reviewer. Score: 6 dimensions, weighted.

## Scores (v1)

| Dimension | Weight | Score | Notes |
|-----------|--------|-------|-------|
| Completeness | 25% | 7.0 | Covers trust chain, HITL, audit. MISSING: retry policy, circuit-breaker pass-through, idempotency-key hashing contract. |
| Accuracy | 20% | 7.5 | M8 HitlApproval import path is correct (models.py). Reason-code namespace prefix `exec_` is consistent. One issue: R2.6 says "import from M8 via injected Protocol" but also mentions HMAC key is resolved by the verifier — the verifier's key lookup path MUST be made explicit so tests can bypass Vault. |
| Security | 20% | 7.5 | MNPI sanitised before LLM: good. Audit on every terminal: good. Fail-closed: good. GAPS: spec doesn't explicitly say the LLM prompt is capped in token length (prompt-injection vector); doesn't say the `reason_code` is the ONLY error surface (no stack traces leak). |
| Testability | 15% | 8.0 | Every AC mapped to a test. Need one more: reason_code vocabulary frozen-ness test. |
| Design alignment | 10% | 8.0 | Matches ARCH-09 Phase 3 + M8 precedent pattern. |
| Gaps | 10% | 6.0 | M9 intent gap is correctly flagged. BUT: `dispatch_to_specialist` helper shape not nailed down. BD principal review threshold source not specified. |

**Weighted: 7.23/10 — CONDITIONAL GO**. Blocked on the below.

## Required fixes

1. **Add §2.10 — Idempotency-key contract**: the 64-hex-char shape is a
   SHA-256 of canonical JSON of `{client_id, instrument, side, quantity,
   timestamp_bucket_minute}`. Specify the builder helper so tests have
   a golden vector.
2. **R2.6 — HITL key resolution**: explicitly state that the
   `HitlApprovalVerifier` wraps M8's `_resolve_hitl_hmac_key` +
   `verify_approval_token` so the tests can monkeypatch M8's helper,
   not the specialist. Add a `DefaultHitlApprovalVerifier` impl.
3. **Error surface** — add explicit invariant: NO exception text appears
   in any audit payload, ExecutionDecision field, or log line. The
   `reason_code` IS the error surface.
4. **Prompt-length cap** — add R3.4: LLM prompt bytes ≤ 4096.
5. **§6 — clarify the "supervisor-level helper"** shape:
   `get_specialist(name) -> type` returns the class; caller constructs
   with injected clients. Register in `SPECIALIST_DISPATCH: Mapping[str, type]`.
6. **R4.1 — principal-review threshold source**: comes from
   `ExecutionRequest.principal_review_threshold_usd` (already in the
   model); if None, BD principal review is unconditional for BD
   registration types. Document the default.
7. **Add §7 — Retry policy**: NONE. Every failure is terminal.
   Retries are the channel's responsibility (per M12's D-1 "M12 is
   glue, not orchestrator").

## Recommended (non-blocking)

- Consider adding a test proving `VALID_EXECUTION_REASONS` is a
  frozenset and of exact cardinality.
- Add a golden-vector test for the audit entry SHA-256 input_hash.
- Add a test that the specialist survives `gateway.call` raising
  a BaseException subclass (should re-raise, not convert).
