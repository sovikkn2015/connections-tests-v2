# M12 Onboarding Specialist — Spec (v0.1.0)

**Module**: `src/m12_supervisor/specialists/onboarding/`
**Phase**: 3 (per ARCH-09)
**Role in system**: 5th of the 5 M12 specialists. Haiku-driven KYC + CIP
workflow orchestrator. BSA 326 Customer Identification Program.

---

## 1. Requirements

### R1 — Public API surface

1.1 Exactly one entry point:
```python
def start_onboarding(self, request: OnboardingRequest,
                     aid_claims: AidClaims, trace_id: str) -> OnboardingDecision
```
1.2 `OnboardingDecision.status`:
`{"kyc_pending", "cip_pending", "cip_passed", "cip_failed", "principal_review_queued", "failed"}`.
1.3 The specialist MUST NOT raise — all terminals returned via
`OnboardingDecision.status` + `reason_code`.
1.4 Stateless between calls.

### R2 — KYC + CIP workflow (BSA §326)

2.1 Customer Identification Program — 4 mandatory checks:
  - **name** (non-empty)
  - **date-of-birth** (over 18)
  - **address** (US or non-US residential)
  - **tax id** (SSN / ITIN / EIN validated format)
2.2 Each failed CIP check yields `KycResult.failed_checks += [field]`.
2.3 If ANY CIP check fails, the specialist:
  - Sets `CipResult.passed = False`
  - Emits a **BSA 326 alert** audit with
    `event_type="bsa_326_cip_failure"` through the injected AuditClient
  - Returns `status="cip_failed"`,
    `reason_code="onb_cip_failed"`
2.4 The BSA 326 alert payload contains:
  `firm_id`, `client_reference`, `failed_checks[]`, `trace_id`,
  `timestamp`, `actor_id` (aid sub), `decision="deny"`. No MNPI
  fields (SSN etc.) are included — only metadata and the list of
  which fields failed (the values themselves are dropped).

### R3 — Trust chain (Rules 4–8)

3.1 `tax_id`, `date_of_birth`, `address` in `OnboardingRequest` are
MNPI. They MUST pass through the injected `MnpiSanitizer` Protocol
before any Haiku LLM sees them (Rule 7). The sanitiser redacts these
fields to `None` before the LLM call (the specialist still uses the
raw values server-side for deterministic KYC checks — those checks
are OPA-shaped via `PolicyClient`, never LLM).
3.2 KYC vendor calls (if any — Phase 3 the real vendor is not yet
available; see Known Blockers) MUST go through the injected
`GatewayClient` Protocol (M6, Rule 4). The tool name is `kyc.verify`.
3.3 Every terminal status emits an audit entry through `AuditClient`
(Rule 6). Missing audit = `status="failed"`,
`reason_code="onb_audit_failed"`.
3.4 AID authority scope MUST include `"onboarding.start"` — absence
yields `status="failed"`, `reason_code="onb_authority_scope_denied"`.

### R4 — BD principal review (Rule 17)

4.1 If the prospective client is a BD-registered advisor (new IAR/RR
hire, `OnboardingRequest.kind == "bd_advisor"`), the specialist
queues a principal review AFTER CIP passes:
`status="principal_review_queued"`,
`reason_code="onb_bd_principal_review"`.
4.2 The principal review payload carries
`gate_kind="onboarding_principal_review"`. This is Rule 17's
FINRA 2210 path applied to onboarding communications.

### R5 — KYC adapter protocol

5.1 No concrete KYC vendor (Jumio/Onfido/etc.) is currently present
in `m11_rest_adapters/`. The spec SHIPS a `KycAdapterProtocol` ABC /
Protocol defining the exact contract:
```python
class KycAdapterProtocol(Protocol):
    vendor_name: str  # e.g. "jumio"
    def verify_identity(self, *, name: str, dob: date, address: str,
                        tax_id_hash: str) -> KycVendorResult: ...
```
5.2 For Phase 3 a built-in `StubKycAdapter` is provided that
returns deterministic results based on trivial patterns
(tax_id starting with "FAIL" → failure; all others → pass). The
real adapter will be a TypeScript M11 container wired in Phase 4;
the Protocol contract stays stable.
5.3 The specialist MUST NOT import from `m11_rest_adapters` —
adapter selection happens via dependency injection
(`specialist = OnboardingSpecialist(kyc_adapter=StubKycAdapter(), ...)`).

### R6 — No hardcoded credentials (Rules 16, 20)

6.1 No API keys, tokens, or DSNs in source. Adapter credentials
resolved via Vault at the injection site (outside the specialist).

### R7 — LLM budget

7.1 Haiku is used for form-filling clarification turns only
(no CIP or BSA decisions). Capped at 2,000 tokens per call.

---

## 2. Design

### 2.1 Directory layout

```
src/m12_supervisor/specialists/onboarding/
├── __init__.py                    # public surface
├── specialist.py                  # OnboardingSpecialist class (~350 lines)
├── models.py                      # OnboardingRequest, OnboardingDecision,
│                                   # KycResult, CipResult, KycAdapterProtocol,
│                                   # StubKycAdapter, KycVendorResult
└── DECISION-LOG.md
```

`specialists/_clients.py` (shared with execution) continues to host
`PolicyClient`, `MnpiSanitizer`, `GatewayClient`, `AuditClient`,
`LLMProvider` Protocols.

### 2.2 Public API (onboarding)

```python
# onboarding/__init__.py exports:
OnboardingSpecialist
OnboardingRequest
OnboardingDecision
KycResult
CipResult
KycAdapterProtocol
StubKycAdapter
KycVendorResult
VALID_ONBOARDING_REASONS
SPECIALIST_NAME  # "onboarding"
```

### 2.3 Pydantic models

```python
class OnboardingRequest(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    kind: Literal["retail_client", "bd_advisor"]
    client_reference: str = Field(min_length=1, max_length=64)  # firm-assigned ID
    legal_name: str = Field(min_length=1, max_length=200)
    date_of_birth: date
    residential_address: str = Field(min_length=1, max_length=500)
    tax_id: str = Field(min_length=1, max_length=64)  # MNPI
    country_code: str = Field(min_length=2, max_length=3)  # ISO 3166-1
    firm_id: str = Field(min_length=1)
    user_utterance: Optional[str] = Field(default=None, max_length=2000)

class CipResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    passed: bool
    failed_checks: list[str] = Field(default_factory=list)
    # Whitelist of check names that may appear in failed_checks:
    #   {"name", "dob", "address", "tax_id", "sanctions"}

class KycVendorResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    vendor_name: str = Field(min_length=1)
    vendor_status: Literal["approved", "manual_review", "denied"]
    vendor_reference_id: str = Field(min_length=1)

class KycResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    cip: CipResult
    vendor: Optional[KycVendorResult] = None
    sanctions_hit: bool = False

class OnboardingDecision(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")
    status: Literal["kyc_pending", "cip_pending", "cip_passed",
                    "cip_failed", "principal_review_queued", "failed"]
    kyc_result: Optional[KycResult] = None
    gate_payload: Optional[HitlGatePayload] = None
    trace_id: str
    tenant_id: str
    reason_code: Optional[str] = None
    latency_ms: int = Field(ge=0)
    bsa_326_alert_emitted: bool = False
```

### 2.4 Closed reason-code vocabulary

```python
VALID_ONBOARDING_REASONS: frozenset[str] = frozenset({
    "onb_invalid_request",
    "onb_invalid_aid",
    "onb_authority_scope_denied",
    "onb_mnpi_sanitize_failed",
    "onb_cip_failed",
    "onb_kyc_vendor_unavailable",
    "onb_kyc_vendor_denied",
    "onb_sanctions_hit",
    "onb_bd_principal_review",
    "onb_audit_failed",
    "onb_bsa_alert_failed",
    "onb_unknown",
})
```

### 2.5 State machine

```
Entry
  │
  ▼
[1. Validate AID + authority scope]  ── fail ──► failed/scope
  │
  ▼
[2. Deterministic CIP checks (name/dob/address/tax_id format)]
  │                                               ── any fail ──►
  ▼                                                  ├── emit BSA 326 alert audit
[3. MNPI-sanitise for LLM only]                      └── cip_failed
  │
  ▼
[4. KYC adapter.verify_identity (via injected adapter)]
  │                                               ── down ──► failed/vendor
  │                                               ── denied ──► cip_failed
  ▼
[5. Sanctions screen (stub: empty list)]  ── hit ──► cip_failed/sanctions
  │
  ▼
[6. If kind == bd_advisor and CIP passed:]  ──► principal_review_queued
  │
  ▼
[7. Audit emit (success)]  ── fail ──► failed/audit
  │
  ▼
cip_passed
```

### 2.6 Module boundaries

Same as execution: `onboarding/` may ONLY import stdlib / pydantic /
`m1_identity` / `m5_config_loader` enums / `m8_pipeline_engine.models`
(HitlGatePayload) / `m12_supervisor.specialists._clients` / siblings.

Enforced by `tests/security/test_m12_specialists_module_boundary.py`.

### 2.7 Supervisor registration

See execution spec §2.8. `SPECIALIST_DISPATCH` gains `"onboarding"` → class.

---

## 3. Tasks

1. **Models** (`onboarding/models.py`) — incl. KycAdapterProtocol +
   StubKycAdapter. Unit tests.
2. **Specialist** (`onboarding/specialist.py`) — full state machine.
3. **Packaging** (`onboarding/__init__.py`) — re-exports.
4. **Supervisor registration** — `SPECIALIST_DISPATCH["onboarding"]`.
5. **Unit tests**
   (`tests/unit/test_m12_onboarding_specialist.py` + models).
6. **Integration test**
   (`tests/integration/test_m12_onboarding_trust_chain.py`):
   real M1/M2/M4/M10 at boundaries, Protocol-adapter thin wrappers.
7. **DECISION-LOG** — `onboarding/DECISION-LOG.md`.

---

## 4. Known Blockers

- **No concrete KYC M11 adapter yet**. SHIP `KycAdapterProtocol` +
  `StubKycAdapter` today. Real vendor (Jumio/Onfido) Phase 4, wired
  via injection — Protocol contract stays stable.
- **Gap 4 BSA/AML is built in parallel by compliance-agent**. The
  onboarding specialist does NOT import from any gap4 module. It
  emits a BSA 326 alert via the AuditClient's `emit(entry)` call
  with `event_type="bsa_326_cip_failure"`; gap4 consumes that from
  the audit stream.

---

## 5. Acceptance mapping

| AC | Test | File |
|----|------|------|
| R1 | `test_public_api_shape` | unit |
| R2.1-R2.4 | `test_cip_four_checks`, `test_bsa_326_alert_emitted_on_fail`, `test_bsa_alert_has_no_mnpi` | unit |
| R3 | `test_mnpi_sanitise_before_llm`, `test_audit_emitted_on_every_terminal`, `test_authority_scope_enforced` | unit |
| R4 | `test_bd_advisor_triggers_principal_review` | unit |
| R5 | `test_kyc_adapter_protocol_shape`, `test_stub_kyc_deterministic` | unit |
| R6 | `test_no_hardcoded_creds_in_src` | security |
| R7 | `test_llm_budget_cap` | unit |
| Full trust chain | `test_m12_onboarding_trust_chain` | integration |

---

## 6. Size targets

- `onboarding/specialist.py` — ~300 lines
- `onboarding/models.py` — ~200 lines (with Protocol + stub adapter)
- Tests — ~550 lines unit, ~200 lines integration

Total ~1,200-1,400 lines (within the "~700 lines" plus shared KYC plumbing).


---

## APPENDIX A — v0.1.1 fixes applied from REVIEW v1

### A1. CIP exact validators (§2.8)

```python
def _cip_validate_name(name: str) -> bool:
    s = name.strip()
    return len(s) >= 2 and not s.isdigit()

def _cip_validate_dob(dob: date, now_date: date) -> bool:
    years = (now_date - dob).days / 365.25
    return years >= 18.0

def _cip_validate_address(addr: str) -> bool:
    s = addr.strip()
    return len(s) >= 10 and any(c.isdigit() for c in s)

_US_SSN_RE = re.compile(r"^\d{3}-?\d{2}-?\d{4}$")
_US_ITIN_RE = re.compile(r"^9\d{2}-?\d{2}-?\d{4}$")
_US_EIN_RE = re.compile(r"^\d{2}-?\d{7}$")

def _cip_validate_tax_id(tax_id: str, country_code: str) -> bool:
    s = tax_id.strip()
    if country_code.upper() == "US":
        return bool(_US_SSN_RE.match(s) or _US_ITIN_RE.match(s)
                    or _US_EIN_RE.match(s))
    return len(s) >= 5
```

### A2. Sanctions screen (Protocol extended)

```python
class KycAdapterProtocol(Protocol):
    vendor_name: str
    def verify_identity(self, *, name: str, dob: date,
                        address: str, tax_id_hash: str) -> KycVendorResult: ...
    def screen_sanctions(self, *, name: str, dob: date,
                         country: str) -> bool: ...
```

`StubKycAdapter.screen_sanctions`: returns True if `tax_id_hash`
starts with `"SAN"` (tests pass a hash that starts with "SAN" for the
positive-match case).

### A3. BSA 326 alert payload — whitelist

Allowed fields ONLY:
`{source: "m12.onboarding", event_type: "bsa_326_cip_failure",
  firm_id, client_reference, failed_checks, trace_id, timestamp,
  actor_id, decision: "deny", reason}`.

Any other field in the alert payload is a bug — enforced by
`test_bsa_alert_has_no_mnpi` which asserts the key-set exactly.

### A4. State-machine re-ordering (§2.5 updated)

Sanctions screen runs BEFORE the KYC vendor call:

```
[2. Deterministic CIP format checks]
[3. Sanctions screen (adapter.screen_sanctions)]
[4. KYC vendor identity verification]
[5. Principal review (BD only)]
[6. Audit emit]
```

### A5. Thread-ID for gate payload

`gate_payload.thread_id = "onb-" + request.client_reference`. Max
length 64; client_reference is already ≤ 64, prefix is 4 chars — safe.

### A6. Error-surface invariant

Same as execution: no exception text in any field except
`reason_code`. Enforced by `test_error_surface_hygiene`.

### A7. Prompt truncation

Same 4096-byte UTF-8 cap as execution; specialist truncates before
provider call.
