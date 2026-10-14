# M12 Execution Specialist — Decision Log

## v0.1.0 — Phase 3 (initial)

### D-1. Specialist reaches trust modules via Protocol, never direct import

M12's `src/m12_supervisor/` has a strict import allowlist enforced by
`tests/security/test_m12_module_boundary.py` (positive list: M1, M5,
M8, M9 only). The execution specialist needs M2 (policy), M4 (MNPI),
M6 (gateway), and M10 (audit) — which the boundary test forbids.

Precedent: M8 solved the same problem with duck-typed `Protocol`
clients (see `m8_pipeline_engine/gateway_client.py` and
`audit_client.py`). We copy the pattern. The specialist depends on
`PolicyClient`, `MnpiSanitizer`, `GatewayClient`, `AuditClient`,
`LLMProvider`, `HitlApprovalVerifier` Protocols defined in
`specialists/_clients.py`. Concrete adapters (wrapping real M2/M4/M6
/M10 objects) live in the test suite or future wiring code — never
inside `specialists/`.

A sibling test `tests/security/test_m12_specialists_module_boundary.py`
enforces the specialist-subtree boundary: forbid imports of
`m2_*`, `m3_*`, `m4_*`, `m6_*`, `m7_*`, `m10_*`, `m11_*`, `m13_*`,
`compliance.*` under `src/m12_supervisor/specialists/`.

### D-2. HITL reuses M8's HMAC helpers verbatim

Steering Rule 3 requires `SHA-256(gate_id + approver_id + timestamp)`
tamper-proof approval tokens. M8 already implemented this scheme in
`m8_pipeline_engine/hitl.py` (`build_approval_token`,
`verify_approval_token`, `build_gate_payload`). We wrap those helpers
in `DefaultHitlApprovalVerifier` rather than re-implementing. M8 is
on the specialist's positive-allowlist so the import is legal.

M8 gates 1/2/3 map to stages 7/13/21 (research pipeline). The
execution specialist re-uses `gate_id=1` semantics (review-before-
commit) for its HITL gate so the payload shape is identical.

### D-3. Autonomous submit is forbidden in Phase 3

Per ARCH-09 "Execution Specialist — HITL: MANDATORY before any order
submission. No autonomous trades." AID issuance MAY (in future)
include `order.submit_without_hitl` for automated-rebalance scenarios;
in Phase 3 that scope is explicitly in the specialist's
`_AUTHORITY_SCOPE_FORBIDDEN` set — presence denies unconditionally.

### D-4. LLM is stub for Phase 3

Haiku (`_HAIKU_MODEL_ID`) is invoked for telemetry parity with other
specialists, but the free-text-to-ticket draft path is deferred. The
channel is expected to supply `proposed_ticket` via a structured UI
form (WhatsApp/Slack card, web form). `_draft_via_llm` returns
`(None, "exec_llm_failed")` when no proposed ticket is supplied —
tests that cover the LLM path will gain a real Haiku mock when the
channel wiring lands in Phase 3.5.

### D-5. BD principal review: fail-closed when threshold is None

Per Rule 17, BD/dual-registered firms need a principal review on any
retail communication. Execution inherits this: if the AID's
`registration_type` is BD and `principal_review_threshold_usd` is
`None`, we trigger the review unconditionally. This is strictly
conservative — a firm that wants a higher threshold sets it in the
`ExecutionRequest`. RIA firms skip the gate entirely.

### D-6. Audit dict shape, not AuditEntry

The `AuditClient` Protocol takes a `Mapping[str, Any]` rather than an
`m3_schema_registry.AuditEntry`. This keeps the boundary tight (M3
is forbidden in `specialists/`). Production adapters map the dict to
a real AuditEntry at the M10 call site.

### D-7. reason_code is the sole error surface

No exception message, stack-trace string, or user input flows into
any `ExecutionDecision` field (other than `reason_code` which is
drawn from the closed `VALID_EXECUTION_REASONS` vocabulary). Audit
entries likewise carry only `reason_code`. Enforced by
`test_error_surface_hygiene` (unit).

### D-8. Idempotency-key is SHA-256 of canonical JSON

Appendix A.1 defines the exact payload: sorted keys, compact
separators, Decimal as str, symbol upper-cased, side lower-cased,
timestamp bucketed to the minute. `build_idempotency_key(...)` helper
ships in `models.py` — the channel is expected to use it rather than
build the key ad-hoc.

### Known gaps (future versions)

- v0.2.0 will add a real Haiku draft-path for free-text utterances.
- v0.2.0 will carry a `cancel_order(...)` entry point for the T+0
  cancel / T+1 allocation workflow described in ARCH-09.
- v0.3.0 will wire the state-machine described in ARCH-09 (DRAFT →
  COMPLIANCE_CHECK → PENDING_APPROVAL → APPROVED → SUBMITTED →
  CONFIRMED → SETTLED) across multiple calls; today each call is a
  single-shot prepare_order.
