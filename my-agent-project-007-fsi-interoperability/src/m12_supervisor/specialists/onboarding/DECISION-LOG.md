# M12 Onboarding Specialist — Decision Log

## v0.1.0 — Phase 3 (initial)

### D-1. Same Protocol-client pattern as Execution

Shares `specialists/_clients.py`. No direct imports of M2/M4/M6/M10 —
the same boundary rule enforced by
`tests/security/test_m12_specialists_module_boundary.py`.

### D-2. KycAdapterProtocol ships with StubKycAdapter

No real KYC vendor is wired in Phase 3 (rule 34: build against the
protocol, ship the stub). `StubKycAdapter` returns deterministic
results based on tax_id_hash prefix + country code — enough for
integration tests. Real adapter (Jumio / Onfido / Trulioo) lands in
Phase 4 as an M11 container; the Protocol contract stays stable.

The KYC adapter runs OUTSIDE the M6 gateway in v0.1.0 because M6
speaks MCP (tool_name + payload) and the KYC stub is a plain Python
callable. When the real vendor adapter lands in Phase 4 it MUST go
through M6 — at that point we convert `kyc_adapter` from a
Protocol to a tool_name and route through the injected
`GatewayClient` (shared from `_clients.py`). The migration is a
single call-site change in `specialist.py` and does not break the
Protocol contract.

### D-3. BSA §326 alert payload whitelist (Appendix A.3)

Only these fields appear in the alert:
`source, event_type, module, action, trace_id, tenant_id, firm_id,
actor_id, client_reference, failed_checks, decision, reason, role,
archetype, timestamp`. No MNPI. `test_bsa_alert_has_no_mnpi` asserts
key-set equality to prevent drift.

### D-4. Tax ID never reaches the LLM or audit

The raw `tax_id` is used only by the CIP regex validator and the
`tax_id_hash()` helper (fed to the KYC vendor as a SHA-256 digest).
The LLM is called AFTER MNPI-sanitisation removes these fields; the
audit entry hashes a whitelist payload that excludes them entirely.

### D-5. Gap 4 BSA/AML integration is one-way

The compliance-agent is building Gap 4 (BSA/AML monitoring) in
parallel. Onboarding does NOT import from any gap4 module. It emits
the BSA §326 alert via `AuditClient.emit` with
`event_type="bsa_326_cip_failure"`. Gap 4 consumes the audit stream
downstream — the contract is the `event_type` + payload shape, not a
Python import.

### D-6. State-machine reorder: sanctions BEFORE vendor

Appendix A.4 reorders the state machine so sanctions screen runs
before the KYC vendor round-trip. Cheap check first, expensive call
only if necessary. Matches production CIP workflow sequencing.

### D-7. BD advisor triggers principal review after CIP pass

Per Rule 17 (FINRA 2210), onboarding a BD-registered advisor routes
to principal review. Onboarding emits `status="principal_review_queued"`
with a HitlGatePayload if a HitlApprovalVerifier is injected; the
channel forwards the gate to the compliance specialist / principal
queue.

### D-8. Why a separate sanctions check vs folding into vendor

The stub adapter exposes `screen_sanctions` as a distinct method so
the specialist can short-circuit on a hit without paying for an
identity-verification round-trip. The real vendor adapter
(`JumioAdapter`) will likely bundle sanctions + identity into a
single API call; the Protocol permits either shape because the
specialist treats them as two sequential steps with independent
results.

### Known gaps (future versions)

- v0.2.0 adds multi-session state (the onboarding flow typically
  spans days — today each call is a single-shot CIP evaluation).
- v0.2.0 adds DocuSign step 7 from ARCH-09 spec
  (KYC → sanctions → risk profile → account open → DocuSign →
  compliance review HITL).
- v0.3.0 wires the real Jumio/Onfido/Trulioo adapter through M6.
