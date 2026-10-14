# M6 Trust-Aware MCP Gateway — Spec (v2)

> Module: M6 MCP Gateway
> Phase: 1 (Trust Layer — final module of Phase 1)
> Agent: 007-gateway-agent
> Status: v2 (post-LLMJ-review v1, addresses F1..F14 + R1..R6 + G1..G8)
> Source docs: ARCH-09 (M6 row + full call flow), ARCH-07 (stack),
>              007-consolidated-design-and-plan.md Part 3 ("THE CORE OF 007"),
>              IMPL-06, steering rule 4

---

## 0. CONTEXT AND SCOPE

M6 is the central trust hub of Project 007. It is the only path a vendor
MCP call may legitimately take. Every request enters M6, flows through
the trust pipeline (M1 identity → M2 authority → M4 request MNPI filter →
vendor call → M4 response MNPI filter → Gap 6 leakage scan → M10 audit),
and only then returns to the caller.

If any stage fails, the request is DENIED, a LiabilityReport is built,
and an AuditEntry is written before control returns to the caller. There
is no degraded mode.

M6 calls M1, M2, M4, M10, compliance.gap2, compliance.gap6. It is called
by specialist agents. In Phase 2 it will front M7 (schema translators)
and M11 (vendor adapters). In Phase 1 the vendor tier is ABSTRACTED
behind a `VendorAdapter` Protocol.

### 0.1 Phase 1 scope

- `TrustAwareGateway` class orchestrates the full pipeline.
- `VendorAdapter` Protocol is the seam where M11/M7 plug in later.
- `StubVendorAdapter` is the deterministic test implementation.
- `CircuitBreaker` + `RateLimiter` are local, in-process implementations
  with an injectable clock for deterministic tests. Phase 2 moves state
  to Redis; the public surface is unchanged.

FastAPI middleware (the httpx-based HTTP surface) is DEFERRED to Phase 2.
Phase 1 is pure library — integration-tested through the full trust
pipeline against real M1/M2/M4/M10/Gap2/Gap6 instances.

### 0.2 Non-goals (Phase 1)

- No httpx, requests, boto3, FastAPI, Redis, OpenTelemetry.
- No import of M7 / M11 / M8 / M9 / M12 / M13.
- No LangGraph / specialist orchestration.
- No retry (tenacity — Phase 2).
- No bulkhead pools (asyncio semaphores — Phase 2).
- No rate-limit queueing. Over-limit → immediate raise.
- No validation of `AuditEntry.module` values (M3 does that).
- No input mutation. Every filtered payload is a `model_copy`.
- No adapter resolution by name. Caller injects adapter per call.
- No LLM calls (steering rule 14).
- No `float(...)` on monetary values.
- No mid-request AID revocation re-check (Phase 1 is synchronous).

### 0.3 Upstream contract

The caller supplies:

- An AID token (JWT string).
- An MCP tool name and requested action (dotted catalog action).
- The request payload (`None`, dict, list, or Pydantic `BaseModel`).
- A vendor adapter (Protocol instance).
- A `trace_id` (str) tying this call to an upstream request.
- A `firm_id` (str) for multi-tenant audit routing.
- Separate `target` and `context` mappings for PolicyInput.
- Optional `session_id` for multi-agent traceability.

M6 returns a `GatewayResponse` on success. On denial/failure, M6 raises
`GatewayError` with a reason from the frozen vocabulary. In every case
(success AND failure), M6 writes an AuditEntry with a LiabilityReport
before returning control.

### 0.4 Source-of-truth integrations (exact symbols)

M6 depends on these PUBLIC `__init__`-exported symbols:

- `m1_identity.IdentityService.verify(token) -> AidClaims`
- `m1_identity.InvalidAidError` (frozen reason vocabulary)
- `m1_identity.AidClaims`, `Role`
- `m2_m4_policy_engine.AuthorityPolicy.evaluate(PolicyInput) -> PolicyDecision`
- `m2_m4_policy_engine.MnpiPolicy.filter(claims, instance, strict=bool)`
- `m2_m4_policy_engine.UnsupportedTypeForFilterError`
- `m2_m4_policy_engine.Decision` (`ALLOW` / `DENY` / `ESCALATE`)
- `m2_m4_policy_engine.PolicyInput`, `PolicyDecision`
- `m2_m4_policy_engine.DECISION_TO_COMPLIANCE_DECISION`
- `m10_audit_logger.AuditLogger.write(entry) -> AuditEntry`
- `m10_audit_logger.AuditWriteError`
- `m10_audit_logger.ProvenanceChainBuilder`
- `m3_schema_registry.AuditEntry`, `ProvenanceStage`
- `compliance.gap2_liability_provenance.LiabilityReport`
- `compliance.gap2_liability_provenance.ErrorCategory`
- `compliance.gap2_liability_provenance.ErrorAttribution`
- `compliance.gap2_liability_provenance.WarrantyBoundary`
- `compliance.gap6_mnpi_leakage_scan.MnpiLeakageScanner`
- `compliance.gap6_mnpi_leakage_scan.ScanDecision`
- `compliance.gap6_mnpi_leakage_scan.ScanResult`

Forbidden imports (enforced by AST scan — `src/m6_mcp_gateway/` AND
`tests/unit/test_m6_mcp_gateway.py`):

- `m7_*`, `m8_*`, `m9_*`, `m11_*`, `m12_*`, `m13_*`.
- `openai`, `anthropic`, `langchain`, `boto3`, `httpx`, `requests`,
  `fastapi`, `redis`.
- Any `m10_audit_logger.<submodule>._<name>` private symbol — no
  internal access, even in tests.

Allowed stdlib: `__future__`, `dataclasses`, `datetime`, `decimal`,
`enum`, `hashlib`, `json`, `re`, `time`, `typing`, `uuid`,
`collections`.
Allowed third-party: `pydantic`.

### 0.5 Trust pipeline — definitive sequence

```
GatewayRequest(token, action, tool_name, mcp_server, payload, trace_id,
               firm_id, target, context, session_id=None, vendor_adapter)
    |
 0. GatewayRequest validation → GatewayError("invalid_request") on
    any violation. No chain writes yet.
 1. append provenance  m6.identity  module="m6"
      SUCCESS payload: {"verified": True, "sub": claims.sub,
                        "jti": claims.jti, "firm_id": claims.firm_id}
      FAILURE payload: {"verified": False,
                        "error_reason": invalid_aid_reason}
    M1.verify(token) → AidClaims (InvalidAidError → DENY)
 2. append provenance  m6.authority  module="m6"
      payload: {"decision": decision.value,
                "rule": pd.rule_applied,
                "wsp": pd.wsp_section}
    M2.evaluate(PolicyInput)
    if decision != ALLOW → DENY path
 3. append provenance  m6.mnpi_request_filter  module="m6"
      payload: {"input_hash": h(raw), "output_hash": h(filtered),
                "strict": bool}
    M4.filter(claims, payload, strict=<BaseModel-only>)
 4. append provenance  m6.resilience  module="m6"
      payload: {"circuit": state, "key": rl_key}
    CircuitBreaker.check(mcp_server)      (OPEN → DENY "circuit_open")
    RateLimiter.check(rl_key)             (over → DENY "rate_limited")
 5. append provenance  m6.vendor_call  module="m6"
      payload: {"tool": tool_name, "server": mcp_server, "ok": bool}
    vendor_adapter.call(tool_name=, payload=)
    on success: circuit.record_success
    on VendorAdapterError: circuit.record_failure → DENY
 6. append provenance  m6.translate  module="m6"
      payload: {"pass_through": true}
 7. append provenance  m6.mnpi_response_filter  module="m6"
      payload: {"input_hash": h(raw_r),
                "output_hash": h(filt_r), "strict": bool}
    M4.filter(claims, vendor_response, strict=<BaseModel-only>)
 8. append provenance  m6.leakage_scan  module="m6"
      payload: {"layer": result.layer,
                "decision": result.decision.value}
    MnpiLeakageScanner.scan(canonical_text(filtered_response))
    on DENY → DENY path ("mnpi_leakage_scan")
 9. LiabilityReport.build(...) with error=None (ALLOW) or attr (DENY)
10. AuditLogger.write(AuditEntry(...))
    if AuditWriteError:
      append provenance  m6.audit_attempt  module="m6"
      payload: {"decision": decision_label,
                "original_reason": pre_audit_reason}
      raise GatewayError("audit_failed")
11. return GatewayResponse(...)
```

### 0.6 Fail-closed invariants

1. `m6.identity` is appended whether verify succeeds or fails (F13).
   The chain is never empty on a DENY path.
2. Each later stage appends to the chain BEFORE its external call. On
   DENY, the failing stage is the LAST stage in the chain.
3. `LiabilityReport` is built for EVERY request (ALLOW and DENY).
4. If `AuditLogger.write` raises, M6 raises `audit_failed` — but only
   after appending `m6.audit_attempt` naming the pre-audit reason.
5. Gap 6 scan runs AFTER M4 response filter. Defense in depth.
6. Circuit open / rate-limit exceeded → raise without calling vendor.
7. Vendor adapter failures bump circuit failure count; success resets.
8. Decimal values round-trip through canonical_json as strings. No
   `float(...)` in `src/`.
9. The raw token NEVER appears in AuditEntry, provenance payloads,
   or exception messages.

---

## 1. REQUIREMENTS

### R0. Glossary

- **Stage** — entry in `ProvenanceChainBuilder`, identified by `stage`
  name (e.g., `m6.identity`) and `module="m6"`.
- **Payload** (provenance) — bounded metadata dict hashed into the
  stage outer hash. Never includes caller request bytes, AID token, or
  vendor response contents.
- **Reason** — short machine string drawn from a frozen vocabulary.
  AuditEntry.reason is `reason[:200]` with no ellipsis.
- **Canonical JSON** — see §R12.

### R1. `GatewayRequest` / `GatewayResponse` (frozen dataclasses)

M6 defines two frozen dataclasses (not Pydantic — immutable call-site
values, not schema entities).

#### R1.1 `GatewayRequest` fields

| field | type | constraints |
|------|------|-------------|
| `token` | `str` | non-empty; `1 <= len <= 8192` (G4). |
| `action` | `str` | regex `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]+)+$` (G7). |
| `tool_name` | `str` | non-empty; `<= 200`; `^[a-zA-Z][a-zA-Z0-9_.\-]*$`. |
| `mcp_server` | `str` | non-empty; `<= 100`; `^[a-z][a-z0-9_-]*$`. |
| `payload` | `Optional[Any]` | `None`/dict/list/`BaseModel`. Else `TypeError("invalid_payload_type")`. |
| `trace_id` | `str` | `8 <= len <= 200`. |
| `firm_id` | `str` | non-empty; `<= 100`. |
| `target` | `Mapping[str, Any]` | default `{}`. Passed to `PolicyInput.target`. (F2) |
| `context` | `Mapping[str, Any]` | default `{}`. Passed to `PolicyInput.context`. (F2) |
| `session_id` | `Optional[str]` | default `None`. Flows to AuditEntry. (F1) |
| `vendor_adapter` | `VendorAdapter` | non-None; has `.call(*,tool_name,payload)` and `.name`. |

Validation in `__post_init__`:

- All string length / regex checks per table.
- `payload` size: `len(canonical_json(payload).encode("utf-8")) <= 1_048_576`
  (1 MiB). Over → `ValueError("payload_too_large")`. (G2)
- `vendor_adapter`: has callable `call`; has `name: str`.

#### R1.2 `GatewayRequest.__repr__` / `__str__` (S1, R6)

```
GatewayRequest(action='client.read', tool_name='sfdc.fetch',
               mcp_server='salesforce', trace_id='trace-001',
               firm_id='acme', token=<redacted>, payload=<omitted>,
               session_id=None)
```

Token never appears. Payload never appears.

#### R1.3 `GatewayResponse` fields

| field | type | notes |
|------|------|-------|
| `decision` | `Literal["ALLOW", "DENY", "ESCALATE"]` | |
| `result` | `Optional[Any]` | filtered canonical response; `None` when decision != ALLOW. |
| `liability_report` | `LiabilityReport` | always populated. |
| `trace_id` | `str` | MUST equal `request.trace_id`. |
| `latency_ms` | `int` | `>= 0`. |
| `provenance_head` | `str` | matches `^[0-9a-f]{64}$`. |
| `rule_applied` | `Optional[str]` | from M2 PolicyDecision. |
| `wsp_section` | `Optional[str]` | from M2 PolicyDecision. |
| `reason` | `Optional[str]` | from PolicyDecision.reason. |

Frozen (`@dataclass(frozen=True)`).

#### R1.4 `GatewayResponse.__repr__` / `__str__`

```
GatewayResponse(decision='ALLOW', trace_id='trace-001', latency_ms=12,
                provenance_head='abc123...', result=<omitted>,
                rule_applied='authority/...', wsp_section='WSP-...')
```

Result never appears.

#### R1.5 Acceptance criteria (R1)

- **AC-R1-1:** Valid GatewayRequest constructs.
- **AC-R1-2:** Empty required `str` → `ValueError`.
- **AC-R1-3:** `trace_id` len 5 → `ValueError("trace_id_too_short")`.
- **AC-R1-4:** `payload=42` → `TypeError("invalid_payload_type")`.
- **AC-R1-5:** `GatewayResponse(latency_ms=-1, ...)` → `ValueError`.
- **AC-R1-6:** `provenance_head` matches `^[0-9a-f]{64}$`.
- **AC-R1-7:** `GatewayResponse.trace_id == request.trace_id`.
- **AC-R1-8:** `repr(request)` contains `<redacted>` and does NOT
  contain raw token.
- **AC-R1-9:** `repr(response)` contains `<omitted>`.
- **AC-R1-10:** `action="not dotted"` →
  `ValueError("invalid_action_format")`.
- **AC-R1-11:** token length > 8192 → `ValueError("token_too_long")`.
- **AC-R1-12:** payload canonical-json > 1MiB →
  `ValueError("payload_too_large")`.

### R2. `GatewayError` — frozen reason vocabulary

```python
VALID_GATEWAY_REASONS = frozenset({
    "invalid_identity",
    "authority_denied",
    "authority_escalated",
    "mnpi_filter_error",
    "circuit_open",
    "rate_limited",
    "vendor_unavailable",
    "vendor_error",
    "mnpi_leakage_scan",
    "audit_failed",
    "invalid_request",
})
```

`GatewayError(reason)` validates against this set (`ValueError` else).
`str(exc) == exc.reason`.

#### R2.1 Acceptance criteria (R2)

- **AC-R2-1:** `GatewayError("invalid_identity").reason == "invalid_identity"`.
- **AC-R2-2:** `GatewayError("made_up")` → `ValueError`.
- **AC-R2-3:** `str(GatewayError("rate_limited")) == "rate_limited"`.
- **AC-R2-4:** `VALID_GATEWAY_REASONS` is a `frozenset`.

### R3. `VendorAdapter` Protocol

#### R3.1 Protocol

```python
class VendorAdapter(Protocol):
    name: str
    def call(self, *, tool_name: str, payload: Any) -> Any: ...
```

Returns a canonical Pydantic `BaseModel` OR JSON-serializable dict.
Raises `VendorAdapterError` on failure.

#### R3.2 `VendorAdapterError`

```python
VALID_VENDOR_KINDS = frozenset({"unavailable", "error"})
class VendorAdapterError(Exception):
    def __init__(self, *, kind: str): ...
    kind: str
```

Kind validated in `__init__`. `args[0]` is opaque and is NEVER
embedded in `GatewayError`, `AuditEntry.reason`, or
`LiabilityReport.error_attribution.reason` (S2).

M6 translations:

- `kind="unavailable"` → `GatewayError("vendor_unavailable")`, circuit
  failure +=1.
- `kind="error"` → `GatewayError("vendor_error")`, circuit failure +=1.

#### R3.3 `StubVendorAdapter`

```python
class StubVendorAdapter:
    name: str
    call_count: int
    def __init__(
        self,
        *,
        name: str = "stub",
        response_factory: Callable[[str, Any], Any] = _DEFAULT_FACTORY,
        fail: Optional[VendorAdapterError] = None,
        fail_after: Optional[int] = None,
    ) -> None: ...
    def call(self, *, tool_name: str, payload: Any) -> Any: ...
```

`_DEFAULT_FACTORY = lambda tool, p: {"tool": tool, "echo": p}`.
With `fail_after=N`: first N calls succeed, then `fail` raises (or
default `VendorAdapterError(kind="unavailable")`).

#### R3.4 Acceptance criteria (R3)

- **AC-R3-1:** Default stub returns echo dict.
- **AC-R3-2:** `VendorAdapterError(kind="bogus")` → `ValueError`.
- **AC-R3-3:** `StubVendorAdapter(fail=VendorAdapterError(kind="unavailable"))`
  raises on `call`.
- **AC-R3-4:** `fail_after=2` — 1st+2nd succeed; 3rd raises.
- **AC-R3-5:** `isinstance(stub, VendorAdapter)` via runtime_checkable
  OR an attribute/callable duck check.
- **AC-R3-6:** `VALID_VENDOR_KINDS` is frozenset.

### R4. `CircuitBreaker`

#### R4.1 States

`CLOSED`, `OPEN`, `HALF_OPEN`.

#### R4.2 Parameters and rationale

- `failure_threshold: int = 5` (validated `>= 1`).
- `recovery_seconds: float = 30.0` (validated `> 0.0`).
- `clock: Callable[[], float] = time.monotonic`.

Keyed by `mcp_server`, not per-tool (F9): circuit breaker protects
the downstream server from cascading calls. One failing server → one
tripped breaker; all its tools share the bulkhead. Matches Hystrix /
Resilience4j. Per-tool would hide downtime.

Phase 1 is NOT thread-safe. Phase 2 migrates state to Redis.

#### R4.3 Contract

```python
class CircuitBreaker:
    def __init__(self, *, failure_threshold=5, recovery_seconds=30.0,
                 clock=time.monotonic) -> None: ...
    def check(self, key: str) -> None: ...    # raises circuit_open
    def record_success(self, key: str) -> None: ...
    def record_failure(self, key: str) -> None: ...
    def state(self, key: str) -> str: ...     # "CLOSED"|"OPEN"|"HALF_OPEN"
```

Semantics:

- Unknown key → `CLOSED`.
- `record_failure` in `CLOSED` increments; at `>= failure_threshold`
  → `OPEN`, `opened_at = clock()`.
- `check` in `OPEN`: raise if `clock() - opened_at < recovery_seconds`,
  else transition to `HALF_OPEN` (allow one probe).
- `record_success` in `HALF_OPEN` → `CLOSED`, failures=0.
- `record_failure` in `HALF_OPEN` → `OPEN`, reset `opened_at`.
- `record_success` in `CLOSED` → failures=0.

#### R4.4 Acceptance criteria (R4)

- **AC-R4-1:** 5 failures → `check` raises `GatewayError("circuit_open")`.
- **AC-R4-2:** After `recovery_seconds`, `check` transitions to
  `HALF_OPEN` (injected clock).
- **AC-R4-3:** `HALF_OPEN` + `record_success` → `CLOSED`.
- **AC-R4-4:** `HALF_OPEN` + `record_failure` → `OPEN` with fresh
  cooldown.
- **AC-R4-5:** `record_success` in `CLOSED` resets failures.
- **AC-R4-6:** Unknown key has state `"CLOSED"`.
- **AC-R4-7:** `failure_threshold=0` → `ValueError`.
- **AC-R4-8:** Two keys have independent state.

### R5. `RateLimiter`

Token bucket, one bucket per key.

#### R5.1 Parameters

- `capacity: int >= 1`.
- `refill_per_second: float >= 0.0` (`0` = hard cap).
- `clock: Callable[[], float] = time.monotonic`.

Phase 1 default construction in M6: `capacity=60,
refill_per_second=1.0` (F8). Phase 2 reads from EnterpriseConfig.

#### R5.2 Key scheme (F10)

M6 computes:

```
rl_key = f"{claims.firm_id}:{claims.sub}:{tool_name}"
```

Phase 1 "per user per tool" = per-AID-holder-per-tool within a firm.
Phase 2 may prepend `session_id` when principal review workflows
require per-human limits.

#### R5.3 Contract

```python
class RateLimiter:
    def __init__(self, *, capacity: int, refill_per_second: float,
                 clock=time.monotonic) -> None: ...
    def check(self, key: str) -> None: ...  # raises rate_limited
    def tokens(self, key: str) -> float: ...
```

`check`:

```
elapsed = clock() - last
tokens = min(capacity, tokens + elapsed * refill_per_second)
if tokens < 1.0: raise GatewayError("rate_limited")
tokens -= 1.0
last = clock()
```

Bucket starts full.

#### R5.4 Acceptance criteria (R5)

- **AC-R5-1:** `capacity=2, refill=0` → 2 pass, 3rd raises.
- **AC-R5-2:** After `1 / refill_per_second` s (injected), 1 token
  restored.
- **AC-R5-3:** Distinct keys don't share state.
- **AC-R5-4:** `capacity=0` → `ValueError`.
- **AC-R5-5:** `refill_per_second=-0.1` → `ValueError`.
- **AC-R5-6:** Tokens never exceed `capacity`.
- **AC-R5-7:** Burst+sustained: `capacity=2, refill=1.0`; 3rd
  immediate call raises; after 1s (injected clock), 1 succeeds. (G8)

### R6. `TrustAwareGateway`

#### R6.1 Constructor

```python
class TrustAwareGateway:
    def __init__(
        self,
        *,
        identity: IdentityService,
        authority: AuthorityPolicy,
        mnpi: MnpiPolicy,
        audit: AuditLogger,
        leakage_scanner: MnpiLeakageScanner,
        circuit_breaker: CircuitBreaker,
        rate_limiter: RateLimiter,
        warranty_boundary: Optional[WarrantyBoundary] = None,
        clock: Callable[[], datetime] = _default_utcnow,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None: ...
```

Any required dep None → `ValueError("gateway_missing_dependency")`.

#### R6.2 Public API

```python
def call(self, request: GatewayRequest) -> GatewayResponse: ...
def health(self) -> dict: ...
```

#### R6.3 Pipeline — provenance payload table

| Stage | ALLOW payload | DENY payload overrides |
|-------|---------------|------------------------|
| `m6.identity` | `{"verified": True, "sub": ..., "jti": ..., "firm_id": ...}` | `{"verified": False, "error_reason": invalid_aid_reason}` |
| `m6.authority` | `{"decision": "ALLOW", "rule": ..., "wsp": ...}` | same shape; decision `"DENY"`/`"ESCALATE"` |
| `m6.mnpi_request_filter` | `{"input_hash": h(raw), "output_hash": h(filt), "strict": bool}` | same |
| `m6.resilience` | `{"circuit": state, "key": rl_key}` | `{"circuit": state, "key": rl_key, "error": "circuit_open"\|"rate_limited"}` |
| `m6.vendor_call` | `{"tool": ..., "server": ..., "ok": True}` | `{"tool": ..., "server": ..., "ok": False, "error": "vendor_unavailable"\|"vendor_error"}` |
| `m6.translate` | `{"pass_through": true}` | N/A |
| `m6.mnpi_response_filter` | `{"input_hash": ..., "output_hash": ..., "strict": bool}` | N/A |
| `m6.leakage_scan` | `{"layer": result.layer, "decision": "ALLOW"}` | `{"layer": result.layer, "decision": "DENY", "match_codes": list(...)[:10]}` |
| `m6.audit_attempt` | N/A | `{"decision": decision_label, "original_reason": pre_audit_reason}` (F4) |

Hashes: SHA-256 over `canonical_json(payload)` (§R12).

#### R6.4 Latency

`start = monotonic()` AFTER `GatewayRequest.__post_init__`.
`latency_ms = int((monotonic() - start) * 1000)`.
Reported in both `GatewayResponse.latency_ms` and
`AuditEntry.latency_ms`.

#### R6.5 Acceptance criteria (R6)

- **AC-R6-1 (happy):** valid AID + ALLOW + clean MNPI + stub canonical
  → `GatewayResponse(decision="ALLOW", ...)`.
- **AC-R6-2 (M1 fail):** malformed token →
  `GatewayError("invalid_identity")`.
- **AC-R6-3 (M2 DENY):** policy DENY →
  `GatewayError("authority_denied")`.
- **AC-R6-4 (M2 ESCALATE):** policy ESCALATE →
  `GatewayError("authority_escalated")`. AuditEntry.decision ==
  `"escalate"`.
- **AC-R6-5 (M4 filter):** SSN/DOB on a `Client` payload redacted
  before vendor adapter invocation.
- **AC-R6-6 (circuit open):** 5 consecutive vendor failures → 6th
  raises `circuit_open` WITHOUT invoking adapter (`call_count`
  unchanged).
- **AC-R6-7 (rate limit):** over-capacity → `rate_limited`.
- **AC-R6-8 (vendor unavailable):**
  `VendorAdapterError(kind="unavailable")` → `vendor_unavailable`.
- **AC-R6-9 (leakage):** Gap 6 DENY → `mnpi_leakage_scan`.
- **AC-R6-10 (audit fail):** AuditLogger raises → gateway raises
  `audit_failed`; chain last stage is `m6.audit_attempt`.
- **AC-R6-11 (ALLOW chain):** chain length = 8. `builder.verify() == True`.
- **AC-R6-12 (liability always):** GatewayResponse on ALLOW and
  AuditEntry.liability on DENY both carry a LiabilityReport.
  `is_clean()` True on ALLOW, False on DENY.
- **AC-R6-13 (no mutation):** Pydantic payloads are not mutated in
  place.
- **AC-R6-14 (decision mapping):** AuditEntry.decision in
  `{"allow","deny","escalate"}`.
- **AC-R6-15 (DENY chain length):** authority_denied → chain length 2
  (identity, authority). (F4)
- **AC-R6-16 (invalid_identity chain):** chain length 1 (identity,
  verified=False). (F13)
- **AC-R6-17 (circuit_open chain):** chain length 4 (identity,
  authority, mnpi_request_filter, resilience).
- **AC-R6-18 (circuit bump):** after one
  `VendorAdapterError(kind="error")`, breaker reports one failure.
- **AC-R6-19 (ErrorAttribution.reason in vocab):** on every DENY,
  `liability_report.error_attribution.reason` ∈
  `VALID_GATEWAY_REASONS`. (S3)
- **AC-R6-20 (VendorAdapterError args isolation):** the string
  `"sensitive-hint-XYZ"` from `VendorAdapterError(kind="error")`
  args does NOT appear in repr/str of GatewayError, AuditEntry, or
  `LiabilityReport.to_canonical_json()`.

### R7. AuditEntry construction

M6 builds the `AuditEntry` on both ALLOW and DENY paths.

#### R7.1 Field mapping

| Field | Value |
|-------|-------|
| `canonical_id` | fresh `uuid4()` |
| `trace_id` | `request.trace_id` |
| `timestamp` | `clock()` (UTC-aware) |
| `actor_id` | claims available: `sha256(claims.sub + ":" + claims.firm_id).hex()` — else: `sha256("unverified:" + token_fingerprint).hex()` where `token_fingerprint = sha256(token.encode("utf-8")).hex()[:16]`. Full 64-char hex. (F6) |
| `action` | `request.action` |
| `module` | `"m6"` |
| `target_type` | `request.target.get("target_type")` (F2) |
| `target_id` | `request.target.get("target_id")`; if missing AND `session_id` provided → `f"session:{session_id}"` (F1) |
| `decision` | `"allow"` / `"deny"` / `"escalate"` lowercase |
| `reason` | `PolicyDecision.reason[:200]` (ALLOW / ESCALATE) OR `GatewayError.reason[:200]` (DENY). No ellipsis. No caller-supplied text. (F5) |
| `input_hash` | `sha256(canonical_json(raw_payload)).hex()` |
| `output_hash` | `sha256(canonical_json(filtered_response)).hex()` for ALLOW; `sha256(canonical_json(None)).hex()` for DENY (S4) |
| `policy_bundle_version` | `None` (Phase 1) |
| `rule_applied` | `PolicyDecision.rule_applied` (M2 stages) or `f"m6/gateway/{reason}"` (M6-owned denials) |
| `wsp_section` | `PolicyDecision.wsp_section` or `"WSP-M6-1"` |
| `data_sources_used` | `[request.mcp_server]` |
| `latency_ms` | measured |
| `archetype` | `claims.archetype` if available else None |
| `role` | `claims.role.value` if available else None |
| `firm_id` | `request.firm_id` (must match `claims.firm_id` when present) |
| `jurisdiction` | `None` (Phase 1) |
| `provenance_chain` | from builder |
| `worm_record_id` | `request.trace_id` |
| `sha256_integrity` | `""` (M10 attaches) |
| `langfuse_trace_url` | `None` |
| `crm_record_id` | `None` |
| `retention_years` | `6` |

#### R7.2 Hashing rule

All hashes are SHA-256 over UTF-8 encoded canonical JSON, returned as
64-char lowercase hex.

#### R7.3 Acceptance criteria (R7)

- **AC-R7-1:** AuditEntry passes `AuditEntry.model_validate`.
- **AC-R7-2:** `input_hash` / `output_hash` are 64-char hex.
- **AC-R7-3:** `actor_id` on M1-fail path does NOT contain any
  substring of the raw token.
- **AC-R7-4:** `provenance_chain` length matches §R6.3.
- **AC-R7-5:** `retention_years == 6`.
- **AC-R7-6:** `reason` length `<= 200`.
- **AC-R7-7:** `session_id="sess-abc"` → `target_id` either equals
  `target.target_id` or falls back to `"session:sess-abc"`.

### R8. LiabilityReport attachment

M6 builds a `LiabilityReport` on every request.

- `trace_id = request.trace_id`.
- `chain = builder.chain()`.
- `chain_verified = builder.verify()`.
- `generated_at = clock()`.
- `error = None` for ALLOW; `ErrorAttribution.attribute_from_chain(...)`
  for DENY.
- `boundary = self._warranty_boundary`.

#### R8.1 Reason → ErrorCategory mapping

| Reason | ErrorCategory | Rationale |
|--------|---------------|-----------|
| `invalid_identity` | `policy_evaluation_error` | Identity precondition. |
| `authority_denied` | `policy_evaluation_error` | M2 DENY. |
| `authority_escalated` | `policy_evaluation_error` | M2 ESCALATE. |
| `mnpi_filter_error` | `compliance_rule_error` | M4 subsystem failure. |
| `mnpi_leakage_scan` | `compliance_rule_error` | Gap 6 subsystem DENY. |
| `circuit_open` | `source_data_error` | Downstream source unhealthy. |
| `rate_limited` | `policy_evaluation_error` | Governance policy decision. |
| `vendor_unavailable` | `source_data_error` | Downstream outage. |
| `vendor_error` | `source_data_error` | Downstream vendor failure. |
| `audit_failed` | `compliance_rule_error` | Audit sink failure. |
| `invalid_request` | `policy_evaluation_error` | Request validation. |

#### R8.2 Failing stage selection

- `invalid_identity` → `m6.identity`.
- `authority_denied` / `authority_escalated` → `m6.authority`.
- `mnpi_filter_error` on request → `m6.mnpi_request_filter`.
- `mnpi_filter_error` on response → `m6.mnpi_response_filter`.
- `circuit_open` / `rate_limited` → `m6.resilience`.
- `vendor_unavailable` / `vendor_error` → `m6.vendor_call`.
- `mnpi_leakage_scan` → `m6.leakage_scan`.
- `audit_failed` → `m6.audit_attempt`.
- `invalid_request` — may occur pre-chain (GatewayRequest validation)
  in which case NO LiabilityReport is built (the request is rejected
  at the door before entering the pipeline). This is the ONLY
  exception to "LiabilityReport built for every request" (§0.6 #3),
  and it is documented explicitly here.

#### R8.3 Acceptance criteria (R8)

- **AC-R8-1:** ALLOW → `error_attribution is None`.
- **AC-R8-2:** DENY → `error_attribution.stage` equals last chain
  stage per §R8.2.
- **AC-R8-3:** `is_clean()` True on ALLOW, False on DENY.
- **AC-R8-4:** §R8.1 mapping complete — every reason in
  `VALID_GATEWAY_REASONS` has a row.

### R9. Health

`TrustAwareGateway.health()`:

```python
{
    "status": "ok",
    "circuit_states": { "<mcp_server>": "CLOSED"|..., ... },
    "dependencies_ready": bool,
}
```

`dependencies_ready = True` iff all injected modules are non-None
AND `audit.health()["status"] == "ok"`. (F14)

### R10. Security invariants

- **SI-1:** Zero credentials in any source file (grep test).
- **SI-2:** Zero forbidden imports in `src/m6_mcp_gateway/` AND
  `tests/unit/test_m6_mcp_gateway.py` (AST scan).
- **SI-3:** `VALID_GATEWAY_REASONS`, `VALID_VENDOR_KINDS` are frozensets.
- **SI-4:** `GatewayRequest.__repr__` redacts token; `GatewayResponse.__repr__`
  omits result.
- **SI-5:** No `print(...)` in src; no `logging` calls with payload
  contents (grep).
- **SI-6:** Audit write is the LAST step on ALLOW; source-order test
  on `gateway.py`.
- **SI-7:** `VendorAdapterError.args[0]` never appears in GatewayError,
  AuditEntry.reason, or LiabilityReport.
- **SI-8:** Raw `token` string never in AuditEntry or provenance
  payloads.
- **SI-9:** No `float(` substring in `src/m6_mcp_gateway/`.

### R11. Phase 1 → Phase 2 migration (R1)

| Area | Phase 1 | Phase 2 |
|------|---------|---------|
| Vendor adapter | StubVendorAdapter | M11-REST / BLPAPI / gRPC |
| Circuit state | in-memory dict | Redis |
| Rate limit state | in-memory buckets | Redis |
| Rate-limit config | hardcoded defaults | EnterpriseConfig (M5) |
| Multi-tenant CB key | `mcp_server` | `firm_id:mcp_server` (G1) |
| HTTP surface | library-only | FastAPI middleware + httpx |
| Translators | pass-through | M7 vendor→canonical call |
| Tracing | chain only | + OpenTelemetry spans |
| Retry | none | tenacity 1s→2s→4s |
| Bulkhead | none | asyncio semaphores per category |

### R12. Canonical JSON (F3, F7, F12)

M6 self-defines canonical JSON. No M10 private imports, even in tests.

```python
def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, default=_json_default)

def _json_default(v: Any) -> Any:
    if isinstance(v, decimal.Decimal): return str(v)
    if isinstance(v, datetime):        return v.isoformat()
    if isinstance(v, UUID):            return str(v)
    if isinstance(v, Enum):            return v.value
    if isinstance(v, BaseModel):       return v.model_dump(mode="json")
    raise TypeError(f"not serializable: {type(v).__name__}")

def canonical_text(obj: Any) -> str:
    if isinstance(obj, str):          return obj
    if isinstance(obj, BaseModel):    return obj.model_dump_json()
    if isinstance(obj, (dict, list)): return canonical_json(obj)
    if obj is None:                   return "null"
    raise TypeError(f"canonical_text: unsupported type {type(obj).__name__}")
```

Golden-hex pinned in test file:

```
canonical_json({"a": 1, "b": [2, 3], "c": Decimal("1.20")})
    == '{"a":1,"b":[2,3],"c":"1.20"}'
```

#### R12.1 Acceptance criteria (R12)

- **AC-R12-1:** `canonical_json({"a": 1, "b": Decimal("1.23")}) ==
  '{"a":1,"b":"1.23"}'`.
- **AC-R12-2:** `canonical_json({"a": Decimal("1.23")})` hash !=
  `canonical_json({"a": Decimal("1.230")})` hash.
- **AC-R12-3:** Stable across runs (golden hex pinned).
- **AC-R12-4:** Unsupported type → `TypeError`.
- **AC-R12-5:** `canonical_text(BaseModel)` uses `model_dump_json`;
  `canonical_text(dict)` uses `canonical_json`; `canonical_text("abc")
  == "abc"`; `canonical_text(42)` → `TypeError`.

### R13. MNPI filter interop (F11)

- `payload` is `BaseModel` → `MnpiPolicy.filter(claims, payload,
  strict=True)`. On `UnsupportedTypeForFilterError` →
  `GatewayError("mnpi_filter_error")`.
- `payload` is dict/list/None → `strict=False`, M4 passes through
  unchanged.
- Any other type → rejected at `GatewayRequest.__post_init__` with
  `invalid_payload_type`.

Response filter follows the same rule (step 7).

Acceptance:

- **AC-R13-1:** dict payload passes through filter unchanged.
- **AC-R13-2:** BaseModel payload with no rules for its type (strict)
  → `mnpi_filter_error`.
- **AC-R13-3:** BaseModel with applicable rules → redacted fields on
  returned copy; input object unchanged.

---

## 2. DESIGN

### 2.1 Directory layout

```
src/m6_mcp_gateway/
    __init__.py              # public API
    adapters.py              # VendorAdapter Protocol, VendorAdapterError,
                             #   VALID_VENDOR_KINDS, StubVendorAdapter
    resilience.py            # CircuitBreaker, RateLimiter
    policy_adapter.py        # verify_identity, evaluate_authority,
                             #   filter_request, filter_response
    audit_builder.py         # canonical_json, canonical_text, h(),
                             #   build_audit_entry, reason→category,
                             #   WSP fallback.
    gateway.py               # TrustAwareGateway, GatewayRequest,
                             #   GatewayResponse, GatewayError,
                             #   VALID_GATEWAY_REASONS.
tests/unit/
    test_m6_mcp_gateway.py   # ≥70 tests covering R1..R13 + integration.
```

### 2.2 Public API (`__init__.py`)

```python
from m6_mcp_gateway.gateway import (
    GatewayError, GatewayRequest, GatewayResponse,
    TrustAwareGateway, VALID_GATEWAY_REASONS,
)
from m6_mcp_gateway.adapters import (
    StubVendorAdapter, VALID_VENDOR_KINDS,
    VendorAdapter, VendorAdapterError,
)
from m6_mcp_gateway.resilience import CircuitBreaker, RateLimiter
```

### 2.3 Module boundaries

M6 imports only public `__init__` symbols from M1, M2/M4, M10, M3,
and compliance. No internal imports. Enforced by AST scan.

### 2.4 Error path structure

`TrustAwareGateway.call(request)` is a straight-line method invoking
stage helpers. Each helper returns a value or raises `GatewayError`.
A single `try` surrounds stages 1–8.

On failure:

1. Ensure the current stage is appended (each stage helper is
   responsible for appending BEFORE its external call; see §0.6 #2).
2. Build `ErrorAttribution.attribute_from_chain(chain,
   failing_stage_name=chain[-1].stage, category, reason, occurred_at)`.
3. Build `LiabilityReport` with that error.
4. Build `AuditEntry` with decision="deny"|"escalate",
   reason=exc.reason.
5. `AuditLogger.write(entry)`:
   - success → raise `GatewayError` with the original reason.
   - `AuditWriteError` → append `m6.audit_attempt` with
     `{"decision": decision_label, "original_reason": exc.reason}`,
     raise `GatewayError("audit_failed")`.

Unknown exceptions (not GatewayError) inside the `try` → caught by a
single `except Exception` → converted to
`GatewayError("invalid_request")` via the same failure handler.

### 2.5 StubVendorAdapter (§R3.3)

`call_count: int` for tests. Fixtures in tests use factories that
return canonical Pydantic types (e.g., `Client`) to exercise the
response filter.

### 2.6 CircuitBreaker internals

```python
@dataclass
class _BreakerState:
    state: str
    consecutive_failures: int
    opened_at: Optional[float]
```

`_states: dict[str, _BreakerState]`. `check` may transition OPEN →
HALF_OPEN. `record_*` writes.

### 2.7 RateLimiter internals

```python
@dataclass
class _BucketState:
    tokens: float
    last: float
```

Starts full.

### 2.8 policy_adapter.py

```python
def verify_identity(identity, token) -> AidClaims
def evaluate_authority(authority, policy_input) -> PolicyDecision
def filter_request(mnpi, claims, payload) -> Any
def filter_response(mnpi, claims, response) -> Any
```

Each catches native exceptions and raises `GatewayError` with the
correct reason. `filter_*` picks strict=True/False per §R13.

### 2.9 audit_builder.py

```python
def canonical_json(obj: Any) -> str
def canonical_text(obj: Any) -> str
def h(obj: Any) -> str

REASON_TO_ERROR_CATEGORY: dict[str, ErrorCategory]
WSP_FALLBACK = "WSP-M6-1"

def build_audit_entry(*, request, claims, decision, reason,
                      policy_decision, input_payload, output_payload,
                      provenance_chain, latency_ms, now, mcp_server,
                      session_id) -> AuditEntry
```

### 2.10 Clock injection

- `clock: Callable[[], datetime]` wall clock.
- `monotonic: Callable[[], float]` elapsed-time clock.

Both injectable via `TrustAwareGateway.__init__`. Tests use
`FakeClock` and `FakeMonotonic` for determinism.

### 2.11 Thread safety

Phase 1 single-threaded. CircuitBreaker and RateLimiter NOT thread-safe.
A `test_not_thread_safe_documented` test asserts module docstrings
contain the "not thread-safe" marker.

### 2.12 Money precision

Decimal via `str(value)` in canonical_json. No `float(` in src.

### 2.13 AST scan specifics

```python
FORBIDDEN_IMPORT_PREFIXES = (
    "m7_", "m8_", "m9_", "m11_", "m12_", "m13_",
    "openai", "anthropic", "langchain", "boto3",
    "httpx", "requests", "fastapi", "redis",
)
FORBIDDEN_M10_PRIVATE = (
    "m10_audit_logger.logger._canonical_json",
    "m10_audit_logger.logger._compute_integrity_hash",
    "m10_audit_logger.provenance._stage_hash",
    "m10_audit_logger.provenance._compute_payload_hash",
)
```

`test_no_forbidden_imports` walks every `.py` in
`src/m6_mcp_gateway/` and `tests/unit/test_m6_mcp_gateway.py`,
parses AST, rejects `ast.Import` / `ast.ImportFrom` hitting the
prefixes or exact M10 private names.

---

## 3. TASKS

Each task delivers implementation + tests together. Tests live in
`tests/unit/test_m6_mcp_gateway.py`. All ACs map to tasks.

### T1. Skeleton + public API

Create `src/m6_mcp_gateway/` modules + `__init__.py`.
Smoke test `test_imports` asserts `__all__` exports.

### T2. `VALID_GATEWAY_REASONS` + `GatewayError`

AC-R2-1..AC-R2-4.

### T3. `VendorAdapter` Protocol + `VendorAdapterError`

AC-R3-2, AC-R3-5, AC-R3-6.

### T4. `StubVendorAdapter`

AC-R3-1, AC-R3-3, AC-R3-4.

### T5. `CircuitBreaker`

AC-R4-1..AC-R4-8.

### T6. `RateLimiter`

AC-R5-1..AC-R5-7.

### T7. `GatewayRequest` / `GatewayResponse`

AC-R1-1..AC-R1-12.

### T8. `policy_adapter.py`

AC-R13-1..AC-R13-3.

### T9. `audit_builder.py`

AC-R12-1..AC-R12-5, AC-R7-1..AC-R7-7.

### T10. `TrustAwareGateway.__init__` + `health`

Missing dep → `ValueError("gateway_missing_dependency")`. `health()`
reports per §R9.

### T11. `TrustAwareGateway.call` — happy path

AC-R6-1, AC-R6-5, AC-R6-11, AC-R6-13, AC-R6-14, AC-R6-18, AC-R8-1,
AC-R8-3, AC-R1-7.

### T12. DENY — identity / authority / MNPI filter error

AC-R6-2, AC-R6-3, AC-R6-4, AC-R6-15, AC-R6-16, AC-R6-19.

### T13. DENY — circuit / rate

AC-R6-6, AC-R6-7, AC-R6-17.

### T14. DENY — vendor failures

AC-R6-8, AC-R6-18, AC-R6-20.

### T15. DENY — Gap 6 leakage

AC-R6-9.

### T16. DENY — audit_failed

AC-R6-10.

### T17. Security tests (R10)

- `test_no_forbidden_imports` (SI-2, §2.13).
- `test_no_credentials` (SI-1, SI-5).
- `test_request_repr_redacts_token` (SI-4).
- `test_response_repr_omits_result` (SI-4).
- `test_no_float_conversion` (SI-9).
- `test_vendor_error_args_never_surface` (SI-7, AC-R6-20).
- `test_token_never_in_audit` (SI-8).

### T18. Drift / reconciliation tests

- Canonical JSON golden hex (§R12).
- Reason→category parity (§R8.1 ↔ VALID_GATEWAY_REASONS).
- Provenance stage ordering regex on gateway.py source.
- `test_not_thread_safe_documented` (§2.11).

### T19. Integration — Phase 1 trust pipeline

Real M1/M2/M4/M10/Gap6 + 3 `InMemoryAuditBackend(tier=...)` + stub
vendor returning canonical `Client` with SSN/DOB. Verify ALLOW,
filter, seal, liability is_clean.

### T20. Public docstring / README

`__init__.py` docstring with usage + pointer to this spec.

---

## 4. TRACEABILITY — Review fix → Spec section

| Fix | Addressed in |
|-----|--------------|
| F1. session_id linkage | R1.1, R7.1 |
| F2. target + context split | R1.1, §0.3 |
| F3. Canonical JSON self-defined | R12, §2.13 |
| F4. audit_attempt payload + DENY chain ACs | R6.3, AC-R6-15..17 |
| F5. reason truncation + source | R7.1, AC-R7-6 |
| F6. token_fingerprint pinned | R7.1 |
| F7. Decimal serializer | R12, AC-R12-2 |
| F8. Rate-limiter defaults | R5.1 |
| F9. CB keying rationale | R4.2 |
| F10. Rate-limit key scheme | R5.2 |
| F11. MNPI filter strict toggle | R13 |
| F12. canonical_text | R12, AC-R12-5 |
| F13. Identity stage on failure | §0.6 #1, R6.3, AC-R6-16 |
| F14. health(dependencies_ready) | R9 |
| R1. Phase 2 migration | R11 |
| R2. ErrorCategory rationale | R8.1 |
| R3. Thread-safety doc check | §2.11, T18 |
| R4. AC trace_id echo | AC-R1-7 |
| R5. AST scan scope | §2.13, T17 |
| R6. Repr spec | R1.2, R1.4 |
| S1. Safe __repr__ | R1.2, R1.4, SI-4 |
| S2. VendorAdapterError.args isolation | R3.2, SI-7, AC-R6-20 |
| S3. ErrorAttribution.reason in vocab | AC-R6-19 |
| S4. output_hash on DENY | R7.1 |
| G1. Multi-tenant CB note | R11 |
| G2. Payload size cap | R1.1, AC-R1-12 |
| G3. Half-open concurrency | §2.11, R4.2 |
| G4. Token length cap | R1.1, AC-R1-11 |
| G5. Audit in health() | R9 |
| G6. Mid-request revocation non-goal | §0.2 |
| G7. Action format regex | R1.1, AC-R1-10 |
| G8. Burst+sustained rate-limit AC | AC-R5-7 |

---

## 5. OUT-OF-SCOPE (Phase 2+)

See §R11 table.

---

*`.kiro/specs/m6-mcp-gateway.md` — v2, Project 007 FSI Interoperability Platform.*
