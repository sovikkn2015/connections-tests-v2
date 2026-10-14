# M12 Execution Specialist — Spec (v0.1.0)

**Module**: `src/m12_supervisor/specialists/execution/`
**Phase**: 3 (per ARCH-09 "Phase 3: Execution Specialist + Onboarding Specialist")
**Role in system**: 4th of the 5 M12 specialists. Haiku-driven order-ticket drafting with MANDATORY HITL before any `order.submit` call through M6.

---

## 1. Requirements

### R1 — Public API surface

1.1 The specialist MUST expose exactly one entry point per instance:
```python
def prepare_order(self, request: ExecutionRequest, aid_claims: AidClaims,
                  trace_id: str) -> ExecutionDecision
```
1.2 `ExecutionDecision.status` is a Literal from
`{"drafted", "compliance_denied", "hitl_required", "submitted", "rejected", "failed"}`.
1.3 The specialist MUST NOT raise on any failure path — every terminal
state is returned via `ExecutionDecision.status` + a reason_code drawn
from a closed vocabulary `VALID_EXECUTION_REASONS`.
1.4 Fresh-construct per request: the specialist is stateless between
calls; all context lives on `ExecutionRequest`.

### R2 — Trust chain (Rules 4–8)

2.1 Every compliance check MUST use the injected `PolicyClient` Protocol
(duck-typed over M2). NO LLM performs the compliance decision (Rule 5).
2.2 Any denial from the policy client MUST be treated as terminal —
`status="compliance_denied"`, no further action (Rule 8 fail-closed).
2.3 The `order.submit` AID authority scope MUST be verified before any
gateway call:
  - The AID MUST carry `"order.submit_with_hitl"` in `authority_scope`, AND
  - The AID MUST NOT carry `"order.submit_without_hitl"` in `authority_scope`
    (autonomous-submit is always forbidden in Phase 3 per ARCH-09).
  - Any violation yields `status="compliance_denied"`, `reason_code="exec_authority_scope_denied"`.
2.4 Order-ticket drafts are MNPI-sanitised through the injected
`MnpiSanitizer` Protocol (duck-typed over M4) BEFORE any value is
passed to the Haiku LLM (Rule 7).
2.5 HITL is MANDATORY before `order.submit`. A request without a valid
`HitlApproval` token returns `status="hitl_required"` with the
`gate_payload` populated (Rule 8). No request MAY reach the gateway's
`order.submit` tool without a verified token.
2.6 The approval token scheme is HMAC-SHA-256 over
`f"{gate_id}|{approver_aid_sub}|{iso_timestamp}|{thread_id}"` using a
key resolved from `IntentRouterConfig`-shaped `hitl_hmac_key_vault_path`.
Exactly the M8 scheme — import the helper from M8 via the injected
`HitlApprovalVerifier` Protocol (no direct M8 import).
2.7 Every terminal outcome MUST emit exactly one audit entry through
the injected `AuditClient` Protocol (duck-typed over M10) — on
`drafted`, `compliance_denied`, `hitl_required`, `submitted`, `rejected`,
and `failed`. Missing audit = `status="failed"`,
`reason_code="exec_audit_failed"`.
2.8 All MCP tool calls MUST go through the `GatewayClient` Protocol
(duck-typed over M6) — never a direct vendor call (Rule 4).

### R3 — LLM usage (Rules 13, 15)

3.1 Haiku (via the injected `LLMProvider` Protocol) is used ONLY for
order-intent extraction and natural-language-to-ticket rendering. It
is never consulted for a compliance decision.
3.2 The LLM MUST receive only an MNPI-sanitised ticket draft. The
specialist asserts this invariant at the sanitization boundary and
fails closed (`reason_code="exec_mnpi_sanitize_failed"`) if the
sanitizer raises.
3.3 LLM token budget for execution is capped at 2,000 tokens per call
(matches M9 Intent-Classification budget — execution is
conversational/routing, not deep reasoning).

### R4 — BD principal review (Rule 17)

4.1 If the caller's AID `registration_type` is `bd_only` or
`dual_registered` AND the order amount exceeds the principal-review
threshold from the injected `ComplianceConfig` (shape of
`m5_config_loader.ComplianceConfig`), the specialist returns
`status="hitl_required"` with `gate_payload.gate_kind="principal_review"`
(rather than the default `"execution_hitl"`).
4.2 The principal review queue is a separate gate, not a substitute
for the advisor HITL approval. A BD order requires BOTH gates cleared
in sequence.

### R5 — Concurrency + idempotency

5.1 The specialist MUST be safe to invoke concurrently — no module-level
mutable state.
5.2 The `ExecutionRequest.idempotency_key` (SHA-256 of client_id +
instrument + side + quantity + timestamp_bucket) is passed verbatim to
M6 so the gateway + M11 adapter can de-duplicate.

### R6 — No hardcoded credentials (Rule 16, 20)

6.1 No API keys, tokens, or DSNs appear in source code. The HITL HMAC
key is resolved via `HitlApprovalVerifier` which goes through
Vault/Secrets Manager (M8's existing mechanism).

---

## 2. Design

### 2.1 Directory layout

```
src/m12_supervisor/specialists/
├── __init__.py                     # re-exports ExecutionSpecialist, OnboardingSpecialist
├── _clients.py                     # shared Protocol + Fake* clients (re-used by both specialists)
├── execution/
│   ├── __init__.py                 # public surface: ExecutionSpecialist, models, VALID_EXECUTION_REASONS
│   ├── specialist.py               # ExecutionSpecialist class (main logic, ~350 lines)
│   ├── models.py                   # ExecutionRequest, ExecutionDecision, OrderTicket, HitlGatePayload
│   └── DECISION-LOG.md
```

### 2.2 Public API (execution)

```python
# execution/__init__.py exports:
ExecutionSpecialist
ExecutionRequest
ExecutionDecision
OrderTicket
VALID_EXECUTION_REASONS
SPECIALIST_NAME  # "execution"
```

### 2.3 Pydantic models

```python
class OrderTicket(BaseModel):
    """Draft ticket — produced by Haiku after MNPI sanitisation."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    client_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    instrument_symbol: str = Field(min_length=1, max_length=32)
    side: Literal["buy", "sell"]
    quantity: Decimal = Field(gt=0)
    order_type: Literal["market", "limit", "stop", "stop_limit"]
    limit_price: Optional[Decimal] = None
    time_in_force: Literal["day", "gtc", "ioc", "fok"] = "day"
    notes: Optional[str] = Field(default=None, max_length=500)

class ExecutionRequest(BaseModel):
    """Input to ExecutionSpecialist.prepare_order."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    user_utterance: str = Field(min_length=1, max_length=2000)
    client_id: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    proposed_ticket: Optional[OrderTicket] = None  # None => LLM drafts
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    firm_id: str = Field(min_length=1)
    hitl_approval: Optional["HitlApproval"] = None  # from M8 models
    restricted_list: list[str] = Field(default_factory=list)
    trading_window_open: bool = True
    principal_review_threshold_usd: Optional[Decimal] = None

class ExecutionDecision(BaseModel):
    """Public return of prepare_order. Frozen."""
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["drafted", "compliance_denied", "hitl_required",
                    "submitted", "rejected", "failed"]
    order_ticket: Optional[OrderTicket] = None
    gate_payload: Optional["HitlGatePayload"] = None
    mcp_order_id: Optional[str] = None
    trace_id: str
    tenant_id: str
    reason_code: Optional[str] = None
    latency_ms: int = Field(ge=0)
    rule_applied: Optional[str] = None
    wsp_section: Optional[str] = None
```

### 2.4 Closed reason-code vocabulary

```python
VALID_EXECUTION_REASONS: frozenset[str] = frozenset({
    "exec_invalid_request",
    "exec_invalid_aid",
    "exec_authority_scope_denied",   # Rule 8 — missing order.submit_with_hitl
    "exec_mnpi_sanitize_failed",
    "exec_llm_failed",
    "exec_policy_denied",
    "exec_policy_escalated",
    "exec_hitl_required",
    "exec_hitl_token_invalid",
    "exec_hitl_token_expired",
    "exec_principal_review_required",
    "exec_gateway_unavailable",
    "exec_gateway_denied",
    "exec_audit_failed",
    "exec_unknown",
})
```

### 2.5 State machine

```
Entry
  │
  ▼
[1. Validate AidClaims + scope]  ── fail ──► compliance_denied
  │
  ▼
[2. MNPI-sanitise request via M4 protocol]  ── fail ──► failed/mnpi
  │
  ▼
[3. If no proposed_ticket: LLM draft via Haiku]  ── fail ──► failed/llm
  │
  ▼
[4. Policy check: order.draft via M2 protocol]  ── deny ──► compliance_denied
  │
  ▼
[5. Principal review gate (BD only)]  ── trigger ──► hitl_required/principal
  │
  ▼
[6. HITL gate: verify approval token (M8 verifier)]  ── missing ──► hitl_required/execution
                                                      ── bad ──► compliance_denied/token
  │
  ▼
[7. Gateway call: order.submit via M6 protocol]  ── deny ──► compliance_denied
                                                  ── down ──► failed/gateway
  │
  ▼
[8. Audit emit (success)]  ── fail ──► failed/audit
  │
  ▼
submitted
```

At every terminal (including failed), an audit emit is attempted.

### 2.6 Protocol clients (duck-typed over M2/M4/M6/M10)

All Protocols live in `specialists/_clients.py` to avoid duplicating
across execution/onboarding. Each is `@runtime_checkable`.

```python
class PolicyClient(Protocol):
    def evaluate(self, *, action: str, aid_claims, target, context) -> "PolicyResultShape": ...

class MnpiSanitizer(Protocol):
    def sanitize(self, claims, instance) -> Any: ...

class GatewayClient(Protocol):
    def call(self, *, tool_name: str, action: str, payload: dict,
             aid_token: str, trace_id: str, firm_id: str,
             target: dict, context: dict) -> "GatewayResultShape": ...

class AuditClient(Protocol):
    def emit(self, entry: dict) -> None: ...

class HitlApprovalVerifier(Protocol):
    def verify(self, approval, *, gate_id: int, thread_id: str) -> Optional[str]: ...
    def build_gate_payload(self, *, gate_id: int, pipeline_run_id: str,
                           thread_id: str, summary: dict) -> "HitlGatePayload": ...

class LLMProvider(Protocol):
    def generate(self, *, prompt: str, max_tokens: int, model: str) -> str: ...
```

Fake implementations (`FakePolicyClient`, `FakeMnpiSanitizer`,
`FakeGatewayClient`, `FakeAuditClient`, `FakeHitlVerifier`,
`FakeLLMProvider`) live in the same module for test reuse.

### 2.7 Module boundaries

`specialists/execution/` may ONLY import from:
- Python stdlib
- `pydantic`
- `m1_identity` (AidClaims, Role)
- `m5_config_loader` (Archetype, RegistrationType enums only)
- `m8_pipeline_engine.models` (HitlApproval, HitlGatePayload shapes)
- `m12_supervisor.specialists._clients`
- `m12_supervisor.specialists.execution.*` (siblings)

FORBIDDEN (duck-typed via Protocol instead):
- `m2_m4_policy_engine`, `m3_schema_registry`, `m4_*`, `m6_mcp_gateway`,
  `m7_schema_translators`, `m10_audit_logger`, `m11_rest_adapters`,
  `m13_*`, `compliance.*`

This is enforced by `tests/security/test_m12_specialists_module_boundary.py`
(new file).

### 2.8 Registration in supervisor

`m12_supervisor/__init__.py` gains:
```python
from m12_supervisor.specialists.execution import ExecutionSpecialist
from m12_supervisor.specialists.onboarding import OnboardingSpecialist

SPECIALIST_DISPATCH: Mapping[str, type] = MappingProxyType({
    "execution": ExecutionSpecialist,
    "onboarding": OnboardingSpecialist,
    # client_service / research / compliance added in later commits
})
```

### 2.9 Instrumentation + limits

- Wall-clock cap: 5 seconds per call (Haiku budget + HMAC verify +
  gateway round-trip). Exceeding → `reason_code="exec_unknown"`,
  `status="failed"`.
- Every audit entry carries `trace_id`, `tenant_id`, `firm_id`,
  `actor_id` (AID `sub`), `action="execution.prepare_order"`,
  `decision`, `reason`, `rule_applied`, `wsp_section`,
  `input_hash`, `output_hash`, `latency_ms`.

---

## 3. Tasks

1. **Models** (`execution/models.py`): Pydantic v2 frozen models
   per §2.3. Unit tests for frozen-ness, extra=forbid, validators.
   ACs: R1.2, R1.3, §2.3.
2. **Shared clients** (`specialists/_clients.py`): Protocol defs +
   Fake* implementations. Unit tests for the Fake*'s fail modes.
   ACs: §2.6.
3. **Specialist** (`execution/specialist.py`): `ExecutionSpecialist`
   class with `prepare_order`. Internal helpers kept private.
   ACs: R1, R2, R3, R4, §2.5.
4. **Packaging** (`execution/__init__.py`, `specialists/__init__.py`):
   Re-exports and `SPECIALIST_NAME` constant.
5. **Supervisor registration** (`m12_supervisor/__init__.py` +
   `dispatch.py`): add `SPECIALIST_DISPATCH` dict, do NOT touch
   existing `dispatch()` signature (M9 is unchanged per "do not
   invent intents"). Add new public helper
   `get_specialist(name, clients) -> BaseSpecialist | None`.
6. **Unit tests** (`tests/unit/test_m12_execution_specialist.py` +
   `..._models.py`): cover every AC, every reason_code.
7. **Boundary + credentials tests**
   (`tests/security/test_m12_specialists_module_boundary.py`,
   `..._no_hardcoded_creds.py`): allowlist, forbidden imports, no
   secrets.
8. **Integration test**
   (`tests/integration/test_m12_execution_trust_chain.py`): full
   AID → M2 policy check → M4 MNPI filter → specialist → M6 gateway
   → M10 audit path. Uses REAL M1/M2/M4/M6/M10 at module boundaries
   per Rule 34 (this is a cross-module integration test; it lives
   in tests/, not in src/m12_supervisor/, so the boundary rule
   doesn't block it). Adapts real objects to the Protocol shape via
   thin adapter classes defined in the test file.
9. **DECISION-LOG** entry v0.1.0 in `execution/DECISION-LOG.md`.

---

## 4. Known Blockers

- **M9 does NOT have a TRADE_EXECUTION intent** (confirmed by reading
  `src/m9_intent_router/taxonomy.py`). The user's prompt assumed it
  does; it doesn't. The specialist is therefore exposed via the new
  `SPECIALIST_DISPATCH` map (§2.8), not via M9 routing. The channel
  invokes the specialist directly — M9's 11-intent taxonomy is
  untouched in this commit.
- **Gap 4 BSA/AML is not yet built** (compliance-agent is building it
  in parallel). Execution does NOT import from any gap4 module. If
  onboarding needs a CIP alert it uses the `AuditClient.emit` with a
  payload `event_type="bsa_326_alert"`; the compliance module will
  consume that.
- **Real M6/M10 adapter for the integration test**: we need a
  ProtocolAdapter in the test file that converts
  `GatewayClient.call(...)` → `TrustAwareGateway.call(GatewayRequest)`.

---

## 5. Acceptance mapping

| AC | Test | File |
|----|------|------|
| R1.1-R1.4 | `test_public_api_shape` | unit |
| R2.1-R2.2 | `test_policy_deny_is_terminal` | unit |
| R2.3 | `test_authority_scope_enforced` | unit |
| R2.4 | `test_mnpi_sanitise_before_llm` | unit |
| R2.5 | `test_hitl_required_when_no_token` | unit |
| R2.6 | `test_hitl_token_hmac_verified` | unit |
| R2.7 | `test_audit_emitted_on_every_terminal` | unit |
| R2.8 | `test_all_tool_calls_through_gateway` | unit + boundary |
| R3 | `test_llm_budget_and_mnpi_invariant` | unit |
| R4 | `test_bd_principal_review_gate` | unit |
| R5 | `test_idempotency_key_passed_verbatim` | unit |
| R6 | `test_no_hardcoded_creds_in_src` | security |
| Full trust chain | `test_m12_execution_trust_chain` | integration |

---

## 6. Size targets

- `execution/specialist.py` — ~350-400 lines
- `execution/models.py` — ~150 lines
- `_clients.py` (shared) — ~250 lines
- Tests — ~650 lines unit, ~250 lines integration

Total ~1,400–1,600 lines (within the "~800 lines" plus shared-clients overhead).


---

## APPENDIX A — v0.1.1 fixes applied from REVIEW v1

### A1. §2.10 Idempotency-key contract
`idempotency_key` is SHA-256 of canonical JSON:
```
{"account_id":..., "client_id":..., "instrument_symbol":...,
 "quantity":"<decimal-string>", "side":..., "timestamp_bucket_minute":<int>}
```
(sorted keys, compact separators). Exposed as
`build_idempotency_key(...)` in `execution/models.py`.

### A2. HITL key resolution
`DefaultHitlApprovalVerifier` wraps M8's `verify_approval_token` and
`build_gate_payload` (imported from `m8_pipeline_engine.hitl`). Test
bypass: monkeypatch `m8_pipeline_engine.hitl._resolve_hitl_hmac_key`
(the existing M8 bypass hook) — no specialist-specific patching.

### A3. Error-surface invariant
No exception text, stack trace, or user-supplied string appears in
any `ExecutionDecision` field (other than `reason_code`) or any audit
payload value. The `reason_code` IS the error surface. Enforced by
`test_error_surface_hygiene`.

### A4. Prompt-length cap (R3.4)
LLM prompt bytes (UTF-8) ≤ 4096. Specialist truncates deterministically
before provider call. Exceeded payloads do not fail — they are
truncated with an `[…truncated]` marker.

### A5. Supervisor helper shape
```python
def get_specialist(name: str) -> Optional[type]:
    """Return specialist CLASS; caller constructs with injected clients."""
    return SPECIALIST_DISPATCH.get(name)
```
Exported as `m12_supervisor.get_specialist`.

### A6. Principal-review threshold default
If `ExecutionRequest.principal_review_threshold_usd is None` AND the
AID's `registration_type` is `bd_only` or `dual_registered`, the
principal-review gate is triggered unconditionally (conservative
fail-closed default).

### A7. Retry policy
**None**. Every terminal is final. Retries are the channel's
responsibility (per M12 D-1). Exception: a 5xx audit write retries
ONCE internally (mirrors M8's `M10AuditClient` behaviour) — the
Protocol may implement retry but it's transparent to the specialist.

### A8. Recommended items folded in
- `test_valid_execution_reasons_frozen` — covers frozenset + cardinality.
- `test_audit_input_hash_golden_vector` — one golden vector.
- `test_specialist_reraises_keyboard_interrupt` — BaseException passthrough.
