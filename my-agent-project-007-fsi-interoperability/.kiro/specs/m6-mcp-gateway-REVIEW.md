# M6 MCP Gateway — LLMJ Review v1 (harsh)

> Reviewer: 007-gateway-agent (LLMJ self-review mode)
> Subject: `.kiro/specs/m6-mcp-gateway.md` v1
> Date: Phase 1 build cycle
> Instruction: Review as if this will be the ONLY chance to get the spec right before a 3-6 week build. Be harsh.

---

## 0. SUMMARY

Overall score: 6.4 / 10 — CONDITIONAL GO.

Structurally solid. Covers the full trust pipeline, names concrete
Python symbols, defines the error vocabulary. But there are real gaps
in field-level contracts (GatewayRequest validation edge cases),
provenance on failure paths, concurrency contracts, money-type
handling, and canonical-JSON drift enforcement. Two design decisions
(m6.audit_attempt stage, actor_id on M1-fail path) need explicit
justification or removal.

Dimension scores:

| Dimension | Weight | Score | Notes |
|-----------|--------|------:|-------|
| Completeness | 25% | 6 | 8 gaps (G1-G8). |
| Accuracy | 20% | 7 | Symbols correct; one contract mismatch (F3). |
| Security | 20% | 7 | MNPI flow right, but 3 leaks possible (S1-S3). |
| Testability | 15% | 6 | Two ACs ambiguous; clocking vague. |
| Design alignment | 10% | 7 | Matches ARCH-09 + steering. |
| Gaps | 10% | 4 | Rate-limiter config sourcing missing. |

Weighted: 0.25*6 + 0.20*7 + 0.20*7 + 0.15*6 + 0.10*7 + 0.10*4 = 6.40.

Required fixes: F1..F14. Recommended: R1..R6.

---

## 1. REQUIRED FIXES

### F1. GatewayRequest missing session/principal linkage

Specialist agent routing under its own AID loses the originating human
advisor. Even an optional `session_id: Optional[str]` on GatewayRequest,
plumbed to audit, closes this. v1 silently drops that linkage.

### F2. target_context shape is ambiguous

One mapping used as both PolicyInput.target AND PolicyInput.context
AND as an audit dict source. Split into `target: Mapping[str, Any]`
and `context: Mapping[str, Any]`. Document that `target.target_type`
and `target.target_id` are the audit-fill keys.

### F3. Canonical JSON contract is self-contradictory

§2.9 says M6 defines its own canonical_json. T9 says a test accesses
M10's private _canonical_json via importlib. That's a cross-module
internal import even in tests — violates steering rule 9.

Pick exactly one: M6 self-defines canonical_json per its own spec,
tests use a hardcoded golden hex. Drop the M10 internal import.
Document full rules inside M6: sorted keys, compact separators,
ensure_ascii=False, Decimal→str, datetime→isoformat, UUID→str,
Enum→.value.

### F4. Provenance chain on failure paths — 2 inconsistencies

- m6.audit_attempt stage is introduced in §2.4 but its canonical
  payload is not defined in §R6.3 table. Pin to
  `{"decision": str, "original_reason": str}`.
- AC-R6-11 asserts ALLOW chain length = 8. No AC for DENY chain
  length. Add AC-R6-15 plus a concrete case (authority_denied →
  exactly 2 stages: identity, authority).

### F5. AuditEntry.reason truncation and source

§R7.1 says "truncated to 200". Commit to `reason[:200]` no ellipsis.
Add an AC. Add: M6 NEVER concatenates caller payload into reason.
Reason is one of: GatewayError.reason, PolicyDecision.reason, or a
fixed English string. No free-form.

### F6. actor_id on M1-fail path is handwaved

`token_fingerprint` is undefined. Pin to
`sha256(token.encode("utf-8")).hex()[:16]` → feed into
`sha256("unverified:" + tf).hex()` (full 64). No arbitrary
truncation. Note raw token never enters AuditEntry.

### F7. Money precision requires explicit serializer rule

json.dumps(Decimal) raises TypeError without a default. Spec must
commit to `_json_default` that handles Decimal→str, datetime→isoformat,
UUID→str, Enum→.value, BaseModel→model_dump(mode="json"). Add test
asserting Decimal("1.23") and Decimal("1.230") hash differently.

### F8. Rate limiter capacity/refill sourcing

Not specified. Pick Phase 1 defaults: capacity=60, refill_per_second=1.0.
Phase 2 reads from EnterpriseConfig. Add AC for defaults.

### F9. Circuit breaker key rationale missing

Keying on `mcp_server` (not per-tool) is correct but needs explicit
rationale in spec to forestall misinterpretation.

### F10. Rate limiter key semantics

Current: `sub + "|" + tool_name`. But in multi-agent topologies, the
AID sub IS the agent, not the human. Revise to
`firm_id + ":" + sub + ":" + tool_name`. Document "per user per tool"
in Phase 1 = per-AID-holder-per-tool. Phase 2 may add session_id.

### F11. MNPI filter error handling on dicts

M4.filter(strict=True) raises on non-BaseModel. StubVendorAdapter
may return dicts in Phase 1. Decide: use strict=False for dict
payloads (M4 passes through unchanged); strict=True only for
BaseModel. Add ACs: dict → no-op; int → invalid_request at request
validation.

### F12. Gap 6 input text — canonical_text is undefined

Commit to:
- BaseModel → `filtered_response.model_dump_json()`.
- dict → `canonical_json(filtered_response)`.
- str → pass-through.
- Other → TypeError → `invalid_request`.

### F13. Identity stage provenance on failure

`ErrorAttribution.attribute_from_chain` raises on empty chain. If
verify fails BEFORE we append m6.identity, the chain is empty and
attribution throws.

Fix: append m6.identity FIRST (placeholder payload `{"verified": False}`),
then call verify. On failure, overwrite logical payload via a second
append? No — simpler: always append AFTER verify succeeds or fails,
using `{"verified": bool, "error_reason": optional}`. That means
m6.identity is appended even on failure. Update §R6.3 table to have
two payload shapes.

### F14. dependencies_ready is vacuous

§R9 field must be defined: `dependencies_ready` = True iff
`audit.health()["status"] == "ok"` AND injected modules have list_rules
callable. Document.

---

## 2. RECOMMENDED FIXES

### R1. Phase 1 → Phase 2 migration section

Collect deferrals into §5.1 — public APIs that stay stable, new
config fields that appear.

### R2. ErrorCategory mapping rationale

Add one-line rationale per row in §R8.1.

### R3. Concurrency doc test

Add a doc-check test asserting "Phase 1 is single-threaded".

### R4. AC for trace_id echo

Add AC-R1-7: `GatewayResponse.trace_id == request.trace_id`.

### R5. AST scan scope

Scope scan to `src/m6_mcp_gateway/` only; separately verify tests
don't import forbidden modules either.

### R6. Repr specification

Specify what GatewayRequest / GatewayResponse reprs show. Never show
token; never show result.

---

## 3. SECURITY REVIEW

### S1. Token leakage via __repr__

GatewayRequest.__repr__ must not include token. Add
`token=<redacted>`.

### S2. VendorAdapterError message leakage

VendorAdapterError.args[0] must NEVER land in GatewayError.reason
or AuditEntry.reason. Add test.

### S3. LiabilityReport reason

Gap 2 ErrorAttribution.reason is PII-regex-checked. M6 passes
GatewayError.reason (alphanumeric_underscore, from frozen vocab).
Add AC: "ErrorAttribution.reason on every DENY is in
VALID_GATEWAY_REASONS".

### S4. Output hash on DENY

canonical_json(None) = "null". Hash is stable. Document it.

---

## 4. TESTABILITY REVIEW

### T-Issue-1. Clock injection ambiguity

Tests need frozen monotonic to get deterministic latency_ms. Add a
FakeMonotonic fixture in T10 that advances by a fixed delta per call.

### T-Issue-2. AST scan — concrete blocklist

Name the test function (`test_no_forbidden_imports`) and pin the
FORBIDDEN_MODULES frozenset in the spec so it's copy-pasteable.

### T-Issue-3. Integration test — backend wiring

Confirm `InMemoryAuditBackend(tier="langfuse")` supports the tier
kwarg (yes — per M10 source).

### T-Issue-4. Gap 6 DENY stub

Implement a test double conforming to the layer Protocol that
always returns DENY with a fixed match_codes tuple. Document
pattern.

---

## 5. GAP ANALYSIS

### G1. Multi-tenant isolation

Circuit breaker keyed on `mcp_server` only. Add Phase 2 note:
"Phase 2 MUST key on `firm_id:mcp_server`."

### G2. Request size limit

Cap payload canonical_json at ≤1MB. Exceeding → `invalid_request`.

### G3. Half-open concurrency

Document Phase 1 single-thread assumption (see R3).

### G4. Token length limit

len(token) ≤ 8192. Beyond → `invalid_identity`.

### G5. Audit health in health()

If M10 down, `dependencies_ready=False`.

### G6. Mid-request revocation

Not handled; synchronous anyway. Non-goal, documented.

### G7. Action format validation

`re.match(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]+)+$", action)` in
GatewayRequest validation. M2 has `_UnknownActionRule` but defense-
in-depth says reject at the door.

### G8. Burst vs sustained rate-limit AC

Add AC: "capacity=2, refill=1/sec; immediate 3rd call fails; after
1 sec, 1 succeeds."

---

## 6. DESIGN ALIGNMENT

- ARCH-09 M6 row (600-1200 lines): spec targets this band.
- ARCH-09 dependencies (M1, M2, M4, M10, M11, M13): M11/M13 via
  VendorAdapter Protocol in Phase 1.
- Steering rule 4 (all calls through M6): T19 verifies.
- Steering rule 6 (3-tier audit): T19 wires 3 backends.
- Steering rule 8 (fail-closed): T12-T16 cover.
- Steering rule 16 (cost_basis never null): M6 forwards only; N/A.
- IMPL-06 Blocker 1 (minimal archiving on M10): orthogonal.

---

## 7. VERDICT

CONDITIONAL GO. Score 6.40/10. 14 required, 6 recommended.

Projected v2 score after fixes: 7.8–8.2.

*`.kiro/specs/m6-mcp-gateway-REVIEW.md` — harsh LLMJ review, v1.*
