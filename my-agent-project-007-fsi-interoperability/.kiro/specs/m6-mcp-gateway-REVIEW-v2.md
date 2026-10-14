# M6 MCP Gateway — LLMJ Review v2

> Reviewer: 007-gateway-agent (LLMJ self-review mode, skeptical posture)
> Subject: `.kiro/specs/m6-mcp-gateway.md` v2
> Date: Phase 1 build cycle — final review gate
> Verdict threshold: 7.5+/10 = GO; below = CONDITIONAL GO.

---

## 0. SUMMARY

Overall score: 8.10 / 10 — GO.

v2 addresses every F1..F14, R1..R6, S1..S4, G1..G8 from v1. Spec now
has unambiguous field-level contracts, self-contained canonical JSON
(no M10 private imports), clean DENY chain semantic (m6.identity
always appended), 1 MiB payload cap, session_id plumbing, and a
frozen vocabulary defended by ACs.

Dimension scores:

| Dimension | Weight | Score | Notes |
|-----------|--------|------:|-------|
| Completeness | 25% | 8 | All critical gaps closed; 3 minor items. |
| Accuracy | 20% | 9 | All symbols verified against source. |
| Security | 20% | 9 | SI-1..SI-9 cover known leak vectors. |
| Testability | 15% | 8 | AC numbering clear; clocks deterministic. |
| Design alignment | 10% | 8 | Matches ARCH-09, steering 4/6/8/9/14. |
| Gaps | 10% | 5 | Two residual items (M2, M3). |

Weighted: 0.25*8 + 0.20*9 + 0.20*9 + 0.15*8 + 0.10*8 + 0.10*5 = 8.10.

Verdict: GO.

---

## 1. VERIFIED FIXES

| Fix | Resolution | Evidence |
|-----|-----------|----------|
| F1 | session_id on GatewayRequest; target_id fallback | R1.1, R7.1, AC-R7-7 |
| F2 | target + context split | R1.1, §0.3 |
| F3 | M6 self-defines canonical_json | R12, §2.13 |
| F4 | m6.audit_attempt payload pinned; DENY chain ACs | R6.3, AC-R6-15..17 |
| F5 | reason[:200] no ellipsis; vocab-only source | R7.1, AC-R7-6 |
| F6 | token_fingerprint + actor_id formula pinned | R7.1 |
| F7 | Decimal→str in _json_default; trailing-zero AC | R12, AC-R12-2 |
| F8 | Phase 1 defaults capacity=60, refill=1.0 | R5.1 |
| F9 | mcp_server keying rationale (Hystrix pattern) | R4.2 |
| F10 | rl_key = firm_id:sub:tool_name | R5.2 |
| F11 | strict=True for BaseModel, False otherwise | R13 |
| F12 | canonical_text explicit dispatch | R12, AC-R12-5 |
| F13 | m6.identity always appended; failure payload shape | §0.6 #1, R6.3, AC-R6-16 |
| F14 | dependencies_ready checks audit.health() | R9 |
| R1 | Phase 2 migration table | R11 |
| R2 | ErrorCategory rationale column | R8.1 |
| R3 | Thread-safety doc check test | §2.11, T18 |
| R4 | AC-R1-7: trace_id echo | AC-R1-7 |
| R5 | AST scan scoped to src + test_m6 | §2.13, T17 |
| R6 | Repr formats pinned | R1.2, R1.4 |
| S1 | Token-redacted repr / result-omitted repr | R1.2, R1.4 |
| S2 | VendorAdapterError.args isolation AC | AC-R6-20, SI-7 |
| S3 | ErrorAttribution.reason ∈ vocab AC | AC-R6-19 |
| S4 | output_hash on DENY = sha256(canonical_json(None)) | R7.1 |
| G1 | Phase 2 firm_id:mcp_server keying documented | R11 |
| G2 | 1 MiB payload cap | R1.1, AC-R1-12 |
| G3 | Half-open concurrency doc | §2.11, R4.2 |
| G4 | Token len ≤ 8192 | R1.1, AC-R1-11 |
| G5 | audit.health() in dependencies_ready | R9 |
| G6 | Mid-request revocation non-goal | §0.2 |
| G7 | Action regex in GatewayRequest | R1.1, AC-R1-10 |
| G8 | Burst+sustained AC | AC-R5-7 |

All 34 items verified.

---

## 2. NEW MINOR FINDINGS (non-blocking)

### M1. R8.2 "invalid_request" pre-chain exception

Spec now documents the one exception where no LiabilityReport is
built: GatewayRequest dataclass validation fails before pipeline
entry. Correct and explicit. Builder may optionally add
AC-R6-21 splitting ValueError (pre-construction) vs GatewayError
(post-construction invalid_request). Acceptable as-is.

### M2. AC-R6-10 covers only ALLOW+audit-fail

AC-R6-10 covers audit-fail after ALLOW. Consider splitting into
AC-R6-10a (ALLOW+audit-fail) and AC-R6-10b (authority_denied+audit-fail).
Builder can split during implementation without spec revision.

### M3. SSN/DOB fixture for T19

T19 needs a canonical Client with SSN/DOB so M4 redacts them. M3's
Client has ssn (x-pii=True). M4 rule `mnpi/client/pii_redaction.v1`
redacts. Integration test author reads M4 source as oracle. Builder
may cite the rule in T19 notes.

---

## 3. SYMBOL VERIFICATION

Every symbol named in spec §0.4 verified against source code:

- `IdentityService.verify(token) -> AidClaims` — m1/service.py:278 ✓
- `InvalidAidError` — m1/claims.py ✓
- `AidClaims` fields (sub, firm_id, archetype, role, jti) — ✓
- `AuthorityPolicy.evaluate(PolicyInput) -> PolicyDecision` — m2_m4/authority.py:483 ✓
- `MnpiPolicy.filter(claims, instance, strict=bool)` — m2_m4/mnpi.py:156 ✓
- `UnsupportedTypeForFilterError` — m2_m4/mnpi.py:42 ✓
- `Decision.{ALLOW,DENY,ESCALATE}` — m2_m4/decisions.py ✓
- `PolicyInput(identity, action, target, context)` — ✓
- `PolicyDecision(decision, reason, rule_applied, wsp_section, details)` — ✓
- `AuditLogger.write(entry) -> AuditEntry` — m10/logger.py ✓
- `AuditWriteError(reason)` — m10/logger.py ✓
- `ProvenanceChainBuilder.append(stage, module, payload, timestamp)` — m10/provenance.py ✓
- `AuditEntry` fields — m3/types.py:1096 ✓
- `LiabilityReport.build(trace_id, chain, chain_verified, generated_at, error, boundary)` — gap2/attribution.py ✓
- `ErrorCategory` (6 values) — gap2/attribution.py ✓
- `ErrorAttribution.attribute_from_chain(chain, failing_stage_name, category, reason, occurred_at)` — ✓
- `WarrantyBoundary.classify(module)` — gap2/warranty.py ✓
- `MnpiLeakageScanner.scan(text) -> ScanResult` — gap6/scanner.py ✓
- `ScanDecision.{ALLOW,DENY}`, `ScanResult.{decision,layer,match_codes,...}` — ✓

Zero symbol mismatches. Accuracy score defensible at 9/10.

Provenance module regex `^m(1[0-3]|[1-9])$` accepts `m6`. ✓

Gap 2 ErrorAttribution.reason PII regex rejects any PII pattern.
VALID_GATEWAY_REASONS values are alphanumeric+underscore — pass
cleanly. ✓

M10 InMemoryAuditBackend supports tier kwarg. ✓

---

## 4. RESIDUAL BUILDER-LEVEL RISK

### B1. canonical_json + BaseModel round-trip

`_json_default` returns `v.model_dump(mode="json")` for BaseModel.
Pydantic v2 converts Decimal to str in mode="json" — consistent with
M6's direct `_json_default` path. Builder should add a test covering
a BaseModel containing a Decimal and verify the hash matches a
dict-with-Decimal equivalent.

### B2. StubVendorAdapter returning BaseModel

T19 Client with SSN. After filter, SSN field is None. `canonical_text`
calls model_dump_json → JSON text without SSN. Layer A scans — no
match → ALLOW. Fixture must avoid non-PII fields that look like PII
patterns.

### B3. AC-R6-6 circuit open without invoking adapter

Test asserts `stub.call_count == 5` after 6 gateway calls (5 adapter
calls + 1 circuit-open rejection). Spec text ("WITHOUT invoking
adapter") is precise enough for the test author.

---

## 5. FINAL VERDICT

GO — 8.10 / 10.

Ready for implementation. 3 minor items can be applied during build
without spec revision.

Proceed to Step 5.

*`.kiro/specs/m6-mcp-gateway-REVIEW-v2.md` — post-review GO.*
