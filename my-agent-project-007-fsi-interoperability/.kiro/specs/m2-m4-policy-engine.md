# M2/M4 Policy Engine — Spec (v2)

> Module: M2 Authority Policy + M4 MNPI Policy
> Phase: 1 (Trust Layer — third module, after M1 and M10)
> Agent: 007-trust-agent
> Status: v2 (post-review — addresses F1..F30 from REVIEW v1)
> Source docs: ARCH-09 (M2 + M4 rows), ARCH-07 (stack), 007-consolidated-design-and-plan.md (Part 3 Trust Layer, Part 6 Archetypes), IMPL-06, steering rules 5 and 19

---

## 0. CONTEXT AND SCOPE

M2/M4 is THE MOAT. Every request through M6 gateway is gated by two
deterministic evaluations:

- M2 Authority Policy — "ARE THEY ALLOWED to perform this action on
  this target?" -> ALLOW / DENY / ESCALATE
- M4 MNPI Policy — "WHAT FIELDS can they see?" -> returns a filtered
  copy of a canonical instance with PII/MNPI fields redacted per
  archetype + role

Both are OPA/Rego conceptually; Phase 1 ships a Python policy engine
with Rego-style rule metadata (rule name, wsp_section, archetype, action)
that produces IDENTICAL decisions to the future Rego bundle.

This spec covers:
- M2: 9 Authority business/meta rules (1 authority_excludes check +
  8 business rules) plus 2 meta rules (default_deny, unknown_action)
- M4: 5 MNPI rules (4 field-filter + 1 access-gate)

### 0.1 Phase 1 scope (Python policy engine, library, no OPA sidecar)

- Phase 1: Python rules with wsp_section annotation. Rules are classes
  implementing PolicyRule. Rule registry is a tuple. Policy classes
  (AuthorityPolicy, MnpiPolicy) own their rule sets.
- Phase 2: Port Python rules to Rego. Policy classes become thin
  wrappers around an OPA sidecar. Public API stable.

The ARCH-07 row "M2/M4 Policy Engine | Rego + Python | OPA + FastAPI"
describes the Phase 2 deployment, not Phase 1. Phase 1 is library-only
with Python rules acting as the Phase 2 test oracle. (F25)

### 0.2 Non-goals

- M2/M4 does NOT call an LLM. Ever. (Steering rule 5.)
- M2/M4 does NOT read config files from disk.
- M2/M4 does NOT cache decisions.
- M2/M4 does NOT write to M10. M6 audits the decision.
- M2/M4 does NOT mutate its inputs. MNPI filter returns a NEW instance.
- M2/M4 does NOT perform identity verification (M1 does).
- M2/M4 does NOT expose a FastAPI surface in Phase 1.
- M2/M4 does NOT support rule hot-reload in Phase 1.
- M2/M4 does NOT import any other `m*_` module except:
  - `m1_identity` (AidClaims, Role)
  - `m5_config_loader` (Archetype, Jurisdiction, RegistrationType)
  - `m3_schema_registry` (Client, SecurityProfile, PaymentInstruction,
    ComplianceCheck, ComplianceAlert, Beneficiary)
- M2/M4 does NOT implement Gap 6 (MNPI Leakage Scan). M4 filters
  INPUTS (pre-LLM). Gap 6 scans OUTPUTS (post-LLM) and is an M6
  sub-module. (F30)
- M2/M4 does NOT implement payment.draft authority in Phase 1. Caller
  gets DENY / no_rule_matched. Phase 2 adds a BSA/AML + sanctions
  gate. (F29)
- M2/M4 does NOT post-validate reason strings returned by rules for
  PII content. Phase 1 rules are all internal; the engine constructs
  every reason itself. Phase 2 adds a post-validator. (F16)

### 0.3 Fail-closed

ANY unhandled exception during rule evaluation -> DENY with
reason="evaluation_error". Never ALLOW on error. Never skip a rule
silently.

The reason on evaluation_error is the LITERAL string
"evaluation_error" — the original exception message is DISCARDED and
not included anywhere in the PolicyDecision. (F15)

### 0.4 Determinism

Given the same PolicyInput or the same (AidClaims, instance) pair, the
decision is identical on every call. No randomness, no time drift, no
side effects. Semantics is DENY-OVERRIDES with ALLOW-records (R2.2).

### 0.5 Transport-agnostic

Phase 1 has no HTTP surface. Phase 2 may front the engine with FastAPI
and OPA. Public Python API is stable.

### 0.6 Upstream caller contract (REQUIRED reading for M6 spec)

When AuthorityPolicy.evaluate(input) returns DENY, the caller (M6
gateway) MUST:
1. Halt the request immediately.
2. Return an error to the client.
3. Write the decision (with rule_applied and wsp_section) to M10.
4. NOT retry or fall back to a relaxed policy.

When ESCALATE is returned, the caller MUST route to the Principal
Review Queue (IMPL-06 Blocker 4). Do NOT auto-approve.

When MnpiPolicy.filter(claims, instance) returns a filtered instance,
the caller MUST use ONLY the filtered instance downstream. The raw
(unfiltered) instance MUST NOT be passed to an LLM, to memory, or to
a response body. (Steering rule 7.)

Non-mutation is a MODULE GUARANTEE, not an END-TO-END GUARANTEE.
After filter(claims, client), the ORIGINAL client still has the SSN
populated. Callers MUST drop the original reference after filter().
M6's wrapper enforces this via a single-use pass-through. (F18)

### 0.7 M1/M3/M5 version pinning

A drift test asserts:
- Role.compliance_officer exists in M1 (removal -> test fails).
- Archetype.tier1_investment_bank and Archetype.tier5_hedge_fund exist
  in M5 (removal -> test fails).
- RegistrationType.bd_only and RegistrationType.dual_registered exist
  in M5 (removal -> test fails).
- Client.ssn_last_four, Client.date_of_birth, Client.tax_id are fields
  on M3 Client (removal/rename -> test fails).
- Beneficiary.account_number is a field on M3 Beneficiary
  (removal/rename -> test fails).
- PaymentInstruction.beneficiary is a field on M3 PaymentInstruction.
- SecurityProfile.mnpi_flag is a field on M3 SecurityProfile.

The drift check for Beneficiary.account_number is ALSO performed in
MnpiPolicy.__init__ — if the attribute is missing, construction
raises AttributeError. (F13)

---

## 1. REQUIREMENTS

### R1. Decisions and Input Contracts

#### R1.1 Decision enum + ComplianceDecision mapping

```python
class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"
```

Mapping to M3 ComplianceDecision (5 values): (F11)

| M2/M4 Decision | M3 ComplianceDecision | Semantics |
|----------------|-----------------------|-----------|
| ALLOW          | ALLOW                 | Permit |
| DENY           | DENY                  | Hard block |
| ESCALATE       | REQUIRE_APPROVAL      | Route to HITL |

M3's WARN and ESCALATE members are Phase 2. M6 translates on audit
write. The constant `DECISION_TO_COMPLIANCE_DECISION` lives in
`decisions.py` for M6 import.

#### R1.2 PolicyDecision dataclass

```python
@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str                # <=200 chars, no PII
    rule_applied: str
    wsp_section: str           # steering rule 19
    details: Mapping[str, Any] = field(default_factory=dict)
```

- reason bounded at MAX_REASON_LEN=200, no raw PII/MNPI.
- rule_applied format: authority/<area>/<rule>.<version> for M2,
  mnpi/<area>/<rule>.<version> for M4.
- wsp_section non-empty, matches WSP-<AREA>-<N>(.<N>)?
- details holds safe-to-log context only.

frozen=True — immutable.

#### R1.3 PolicyInput dataclass

```python
@dataclass(frozen=True)
class PolicyInput:
    identity: AidClaims
    action: str
    target: Mapping[str, Any] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)
```

Concrete literal examples per action: (F8)

```python
# client.read
PolicyInput(
    identity=aid_sarah_advisor,
    action="client.read",
    target={"client_id": "CLT-123",
            "advisor_id": "sarah.chen@acmewm.com",
            "mnpi_flag": False},
    context={},
)

# order.submit
PolicyInput(
    identity=aid_sarah_advisor,
    action="order.submit",
    target={"security_id": "SEC-ACME", "ticker": "ACME",
            "side": "buy", "quantity": 100.0,
            "client_id": "CLT-123"},
    context={"restricted_list": ["ACME"],
             "trading_window_open": True,
             "concentration_pct": 0.05,
             "crossing_wall": False,
             "crossing_pod": False},
)

# comm.send_retail (BD advisor)
PolicyInput(
    identity=aid_bob_bd_advisor,  # registration_type=bd_only
    action="comm.send_retail",
    target={"client_id": "CLT-999", "content_ref": "DRAFT-42"},
    context={"recipient_type": "retail"},
)
```

#### R1.4 Action catalog (Phase 1)

| Action | Meaning | Note |
|--------|---------|------|
| client.read      | Read a Client | |
| client.list      | List advisor's clients | |
| portfolio.view   | View holdings | |
| security.lookup  | Look up a security profile | |
| order.draft      | Draft an order | |
| order.submit     | Submit an order | |
| payment.draft    | Draft a payment | Phase 1: no rule -> DENY / no_rule_matched. Phase 2 adds BSA/AML gate. (F29) |
| comm.send_retail | Retail communication | |

Unknown action ->
DENY / "unknown_action" / "authority/meta/unknown_action.v1" /
"WSP-META-0.0".

#### R1.5 Missing target/context keys (FAIL-CLOSED) (F4)

When a rule requires a key that is absent or None from either `target`
or `context`:
- M2: return DENY with reason="missing_target:<key>" or
  reason="missing_context:<key>" depending on source dict.
- M4: None treated as "sensitive" (mnpi_flag missing -> DENY).

Both handled by private helper `_require(mapping, key, mapping_name,
rule_applied, wsp_section)` returning (value, None) or
(None, DENY-decision).

#### R1.6 Acceptance criteria (R1)

- **AC-R1-1:** Decision has exactly three members. len(Decision)==3.
- **AC-R1-2:** PolicyDecision is frozen (FrozenInstanceError on set).
- **AC-R1-3:** PolicyInput is frozen.
- **AC-R1-4:** reason="x"*201 -> ValueError.
- **AC-R1-5:** wsp_section="" -> ValueError.
- **AC-R1-6:** rule_applied="" -> ValueError.
- **AC-R1-7:** PolicyInput(action="") -> ValueError.
- **AC-R1-8:** Unknown action -> DENY /
  "authority/meta/unknown_action.v1" / "WSP-META-0.0".
- **AC-R1-9:** Missing context[restricted_list] on order.submit ->
  DENY / "missing_context:restricted_list".
- **AC-R1-10:** Missing target[advisor_id] on client.read ->
  DENY / "missing_target:advisor_id".
- **AC-R1-11:** identity not AidClaims -> TypeError.
- **AC-R1-12 (F11):** DECISION_TO_COMPLIANCE_DECISION exists and maps
  ALLOW->"ALLOW", DENY->"DENY", ESCALATE->"REQUIRE_APPROVAL".

### R2. PolicyRule protocol and engine semantics

#### R2.1 PolicyRule Protocol

```python
class PolicyRule(Protocol):
    name: str
    wsp_section: str
    rule_applied: str
    archetypes: frozenset[Archetype]
    actions: frozenset[str]
    rule_kind: str   # authority_gate | authority_meta | mnpi_filter | mnpi_access
    decision_kinds: frozenset[str]

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]: ...
```

#### R2.2 DENY-OVERRIDES semantics (F1, F2)

```
first_allow = None
for rule in self._rules:
    if rule.archetypes and inp.identity.archetype not in {a.value for a in rule.archetypes}:
        continue
    if rule.actions and inp.action not in rule.actions:
        continue
    try:
        decision = rule.evaluate(inp)
    except Exception:
        # Engine swallows exception. Construct LITERAL evaluation_error.
        return PolicyDecision(
            decision=Decision.DENY,
            reason="evaluation_error",
            rule_applied=rule.rule_applied,
            wsp_section=rule.wsp_section,
            details={},
        )
    if decision is None:
        continue
    if decision.decision in (Decision.DENY, Decision.ESCALATE):
        # TERMINAL — overrides any prior ALLOW.
        return decision
    if first_allow is None:
        first_allow = decision   # ALLOW — keep scanning for a later override.
if first_allow is not None:
    return first_allow
return _META_DEFAULT_DENY
```

Worked example (F2): advisor reading own client with concentration 12%:
1. Hard-DENY rules abstain (restricted list empty, trading window
   open, no walls).
2. advisor.read_own_clients returns ALLOW — recorded as first_allow.
3. advisor.concentration_limit returns ESCALATE — TERMINAL. Engine
   returns ESCALATE. The recorded ALLOW is DISCARDED.

#### R2.3 Rule registration

AuthorityPolicy constructor takes no rules. MnpiPolicy same.
`list_rules() -> list[tuple[str, str]]` returns (rule_applied,
wsp_section) tuples.

#### R2.4 Acceptance criteria (R2)

- **AC-R2-1:** AuthorityPolicy().list_rules() returns exactly 11
  tuples (1 excludes_check meta + 8 business rules + 1 default_deny
  meta + 1 unknown_action meta).
- **AC-R2-2:** MnpiPolicy().list_rules() returns exactly 5 tuples.
- **AC-R2-3:** Every rule_applied matches
  `^(authority|mnpi)/[a-z_]+/[a-z_]+\.v\d+$`.
- **AC-R2-4:** Every wsp_section matches
  `^WSP-[A-Z]+-\d+(\.\d+)?$`.
- **AC-R2-5:** A rule raising RuntimeError("client@example.com") ->
  engine returns DENY / "evaluation_error" — no email substring. (F15)
- **AC-R2-6:** All rules abstain on a KNOWN action ->
  DENY / "no_rule_matched" / "authority/meta/default_deny.v1" /
  "WSP-META-0.1".
- **AC-R2-7:** Rule ordering is stable across instances.
- **AC-R2-8 (F2):** Crafted inputs so advisor.read_own_clients ALLOWs
  and advisor.concentration_limit ESCALATEs -> final decision
  ESCALATE.

### R3. AuthorityPolicy — public API

```python
class AuthorityPolicy:
    def __init__(self) -> None: ...
    def evaluate(self, inp: PolicyInput) -> PolicyDecision: ...
    def list_rules(self) -> list[tuple[str, str]]: ...
    def rule_table(self) -> list[dict]: ...
```

#### R3.1 Acceptance criteria

- **AC-R3-1:** evaluate(non_PolicyInput) raises TypeError.
- **AC-R3-2:** evaluate(valid).decision is a Decision value.
- **AC-R3-3:** 100 consecutive calls produce equal PolicyDecision
  (structural ==, not identity). (F20)

### R4. M2 Authority Rules

#### R4.1 Evaluation order

1. authority/meta/excludes_check.v1          WSP-META-0.2  (F27)
2. authority/advisor/restricted_list.v1      WSP-TRD-3.1
3. authority/advisor/trading_window.v1       WSP-TRD-3.2
4. authority/advisor/chinese_wall.v1         WSP-CWL-4.1
5. authority/advisor/pod_isolation.v1        WSP-POD-5.1
6. authority/advisor/read_other_advisor_clients.v1  WSP-ADV-1.2
7. authority/advisor/read_own_clients.v1     WSP-ADV-1.1
8. authority/advisor/concentration_limit.v1  WSP-RISK-2.1
9. authority/principal/review_required.v1    WSP-FINRA-2210
10. authority/meta/default_deny.v1           WSP-META-0.1

Plus authority/meta/unknown_action.v1 (WSP-META-0.0) applied BEFORE
the loop when action is not in the catalog.

#### R4.2 authority.meta.excludes_check (NEW — F27)

- **Purpose:** DENY if action is in identity.authority_excludes. The
  AID's own negative-authority assertion overrides all other rules.
- **Applies when:** all actions, all archetypes.
- **DENY if:** `inp.action in inp.identity.authority_excludes`
- **Otherwise:** None
- rule_applied: authority/meta/excludes_check.v1
- wsp_section: WSP-META-0.2
- rule_kind: authority_meta

- **AC-R4-2-1:** authority_excludes=["order.submit"] + action=order.submit
  -> DENY / "excluded_by_aid" / ...
- **AC-R4-2-2:** authority_excludes=["order.submit"] + action=client.read
  -> None.
- **AC-R4-2-3:** empty authority_excludes -> None.

authority_scope is NOT consumed in Phase 1 — Phase 2 adds
authority.meta.scope_check.v1. (F12)

#### R4.3 advisor.read_own_clients

- **Purpose:** Advisor reads a client assigned to them.
- **Applies when:** action in {client.read, client.list, portfolio.view}
- **ALLOW if:** (identity.role in {Role.advisor,
  Role.compliance_officer}) AND (target[advisor_id] == identity.sub OR
  identity.role == Role.compliance_officer)
- **Otherwise:** None
- rule_applied: authority/advisor/read_own_clients.v1
- wsp_section: WSP-ADV-1.1
- rule_kind: authority_gate

- **AC-R4-3-1:** advisor Sarah reading Sarah's client -> ALLOW.
- **AC-R4-3-2:** Missing target[advisor_id] -> DENY /
  "missing_target:advisor_id".
- **AC-R4-3-3:** compliance_officer reading any client -> ALLOW.
- **AC-R4-3-4:** advisor Sarah reading Tom's client -> None (defers);
  downstream default-deny fires.

#### R4.4 advisor.read_other_advisor_clients

- **Applies when:** action in {client.read, client.list,
  portfolio.view} (F6)
- **DENY if:** target[advisor_id] != identity.sub AND
  identity.role != Role.compliance_officer
- **Otherwise:** None
- rule_applied: authority/advisor/read_other_advisor_clients.v1
- wsp_section: WSP-ADV-1.2
- rule_kind: authority_gate

- **AC-R4-4-1:** Sarah reading Tom's client, role=advisor -> DENY.
- **AC-R4-4-2:** Sarah reading Tom's client, role=compliance_officer
  -> None; downstream read_own_clients ALLOWs.
- **AC-R4-4-3:** Sarah reading Sarah's client -> None.
- **AC-R4-4-4:** Cross-advisor client.list, role=advisor -> DENY. (F6)

#### R4.5 advisor.restricted_list_check

- **Applies when:** action in {order.draft, order.submit}
- **DENY if:** target[ticker] in context[restricted_list]
- **Otherwise:** None
- rule_applied: authority/advisor/restricted_list.v1
- wsp_section: WSP-TRD-3.1
- rule_kind: authority_gate

- **AC-R4-5-1:** ticker "ACME" on list -> DENY.
- **AC-R4-5-2:** ticker "MSFT" not on list -> None.
- **AC-R4-5-3:** Missing context[restricted_list] -> DENY /
  "missing_context:restricted_list".
- **AC-R4-5-4:** context[restricted_list]=[] + any ticker -> None.

#### R4.6 advisor.trading_window_check

- **Applies when:** action in {order.draft, order.submit}
- **DENY if:** context[trading_window_open] is False
- **Otherwise:** None
- rule_applied: authority/advisor/trading_window.v1
- wsp_section: WSP-TRD-3.2
- rule_kind: authority_gate

- **AC-R4-6-1:** trading_window_open=False -> DENY.
- **AC-R4-6-2:** trading_window_open=True -> None.
- **AC-R4-6-3:** Missing -> DENY /
  "missing_context:trading_window_open".

#### R4.7 advisor.concentration_limit (ESCALATE)

- **Applies when:** action in {order.draft, order.submit}
- **Type check (F14):** context[concentration_pct] MUST be a float
  (not bool, not int, not str) in [0.0, 1.0]. Anything else is
  treated as missing.
- **ESCALATE if:** context[concentration_pct] > 0.10 (strict >).
- **Otherwise:** None
- rule_applied: authority/advisor/concentration_limit.v1
- wsp_section: WSP-RISK-2.1
- rule_kind: authority_gate

- **AC-R4-7-1:** 0.12 -> ESCALATE.
- **AC-R4-7-2:** 0.05 -> None.
- **AC-R4-7-3:** 0.10 -> None (strict >).
- **AC-R4-7-4:** Missing -> DENY /
  "missing_context:concentration_pct".
- **AC-R4-7-5:** "12%" (str) -> DENY / "missing_context:concentration_pct".
- **AC-R4-7-6:** 1 (int) -> DENY / "missing_context:concentration_pct".
- **AC-R4-7-7:** 1.5 (out of range) -> DENY /
  "missing_context:concentration_pct".

#### R4.8 advisor.chinese_wall

- **Applies when:** identity.archetype == tier1_investment_bank
- **DENY if:** context[crossing_wall] is True
- **Otherwise:** None
- rule_applied: authority/advisor/chinese_wall.v1
- wsp_section: WSP-CWL-4.1
- rule_kind: authority_gate
- archetypes: frozenset({Archetype.tier1_investment_bank})

- **AC-R4-8-1:** Tier1 + crossing_wall=True -> DENY.
- **AC-R4-8-2:** Tier1 + crossing_wall=False -> None.
- **AC-R4-8-3:** Tier4 + crossing_wall=True -> rule skipped.
- **AC-R4-8-4:** Tier1 + missing crossing_wall -> DENY /
  "missing_context:crossing_wall".

#### R4.9 advisor.pod_isolation

- **Applies when:** identity.archetype == tier5_hedge_fund
- **DENY if:** context[crossing_pod] is True
- **Otherwise:** None
- rule_applied: authority/advisor/pod_isolation.v1
- wsp_section: WSP-POD-5.1
- rule_kind: authority_gate
- archetypes: frozenset({Archetype.tier5_hedge_fund})

- **AC-R4-9-1:** Tier5 + crossing_pod=True -> DENY.
- **AC-R4-9-2:** Tier5 + crossing_pod=False -> None.
- **AC-R4-9-3:** Tier3 + crossing_pod=True -> rule skipped.
- **AC-R4-9-4:** Tier5 + missing -> DENY /
  "missing_context:crossing_pod".

#### R4.10 principal.review_required (ESCALATE)

- **Applies when:** action==comm.send_retail AND
  identity.registration_type in {bd_only, dual_registered}
- **ESCALATE if:** context[recipient_type] == "retail"
- **Otherwise:** None
- rule_applied: authority/principal/review_required.v1
- wsp_section: WSP-FINRA-2210
- rule_kind: authority_gate

F3 note: dual_registered firms INTENTIONALLY trigger this rule for
BD-side activity. Dual-registered firms comply with BD rules under
FINRA. Not a bug.

F28 note: Phase 1 classifies based on recipient_type only. IMPL-06
Blocker 4 prescribes content-type + channel + archetype classification
as Phase 2 extensions that reuse the same rule_applied and
wsp_section.

- **AC-R4-10-1:** BD + retail -> ESCALATE.
- **AC-R4-10-2:** BD + institutional -> None.
- **AC-R4-10-3:** RIA-only + retail -> rule skipped.
- **AC-R4-10-4:** Dual-registered + retail -> ESCALATE.
- **AC-R4-10-5:** BD + missing recipient_type -> DENY /
  "missing_context:recipient_type".

#### R4.11 Role.system and Role.agent handling (F7)

Role.system and Role.agent are internal service identities. Phase 1:
they go through authority.meta.excludes_check first but will fall
through to advisor.read_other_advisor_clients which DENIES on
role != compliance_officer. Net effect: Phase 1 system/agent
identities get DENY for every client/order-scoped action.

In Phase 1 callers wanting a system identity to access client data
must use role=compliance_officer. Phase 2 adds
authority.meta.scope_check.v1 for scope-based access.

The Phase 1 implementation requires role in {Role.advisor,
Role.compliance_officer} in advisor.read_own_clients (R4.3).

- **AC-R4-11-1:** Role.system + client.read + matching advisor_id ->
  DENY.
- **AC-R4-11-2:** Role.agent + client.read -> DENY.
- **AC-R4-11-3:** Role.advisor + matching advisor_id -> ALLOW.

### R5. MnpiPolicy — M4 MNPI Filter Rules (5 rules)

#### R5.1 API

```python
class MnpiPolicy:
    def __init__(self) -> None: ...
    def filter(self, claims: AidClaims, instance: BaseModel,
               *, strict: bool = False) -> BaseModel: ...
    def check_mnpi_access(self, claims: AidClaims,
                          security: SecurityProfile) -> PolicyDecision: ...
    def list_rules(self) -> list[tuple[str, str]]: ...
    def rule_table(self) -> list[dict]: ...
```

- filter is a pure function of (claims.role, type(instance), strict).
- filter is type-stable — returned instance is exact same Pydantic class.
- strict=False (default): unsupported type returns input unchanged.
- strict=True: unsupported type raises UnsupportedTypeForFilterError
  (TypeError subclass). (F17)
- check_mnpi_access is the security.mnpi_check rule.

M6 (gateway) MUST pass strict=True in trust-critical path.

#### R5.2 Role predicate (F5)

Phase 1 predicate is LITERALLY:
```python
_IS_COMPLIANCE_OFFICER = lambda role: role == Role.compliance_officer
```

The description ">= senior_advisor" is documentation-only for Phase 2.
A constant MNPI_VISIBILITY_PREDICATE_DOC in mnpi.py documents the
choice.

#### R5.3 Filter rules (4 field-filter + 1 access)

| Rule | Kind | Type | Field | Authorized | WSP |
|------|------|------|-------|------------|-----|
| mnpi/client/ssn_visibility.v1     | filter | Client             | ssn_last_four              | compliance_officer only | WSP-MNPI-1.1 |
| mnpi/client/dob_visibility.v1     | filter | Client             | date_of_birth              | compliance_officer only (Phase 1) | WSP-MNPI-1.2 |
| mnpi/client/tax_id_visibility.v1  | filter | Client             | tax_id                     | compliance_officer only | WSP-MNPI-1.3 |
| mnpi/payment/account_visibility.v1 | filter | PaymentInstruction | beneficiary.account_number | compliance_officer only (Phase 1) | WSP-MNPI-2.1 |
| mnpi/security/mnpi_check.v1       | access | SecurityProfile    | (mnpi_flag gate)           | compliance_officer if mnpi_flag=True | WSP-MNPI-3.1 |

Phase 1 does NOT filter email/phone on Client. Phase 2 adds them.

#### R5.4 Field paths

- Client.ssn_last_four — top-level Optional[str].
- Client.date_of_birth — top-level Optional[date].
- Client.tax_id — top-level Optional[str].
- PaymentInstruction.beneficiary.account_number — nested on
  Beneficiary sub-model. Chained model_copy.

If beneficiary is None, rule is no-op.

MnpiPolicy.__init__ verifies Beneficiary.model_fields contains
account_number and raises AttributeError if not. (F13)

#### R5.5 security.mnpi_check (access rule)

```python
MnpiPolicy().check_mnpi_access(claims, security_profile) -> PolicyDecision
```

- DENY if security.mnpi_flag is True AND role != compliance_officer.
- DENY if mnpi_flag is None (treated as True — fail-closed).
- ALLOW otherwise.
- rule_applied: mnpi/security/mnpi_check.v1
- wsp_section: WSP-MNPI-3.1

#### R5.6 Acceptance criteria

- **AC-R5-1 (ssn, advisor):** filter(advisor, client_with_ssn) returns
  Client with ssn_last_four=None, all other fields preserved. Input
  client's ssn_last_four still its original value (value
  comparison ==). (F19)
- **AC-R5-2 (ssn, compliance):** unchanged.
- **AC-R5-3 (dob, advisor):** filtered date_of_birth=None.
- **AC-R5-4 (dob, compliance):** unchanged.
- **AC-R5-5 (tax_id, advisor):** filtered tax_id=None.
- **AC-R5-6 (tax_id, compliance):** unchanged.
- **AC-R5-7 (payment, advisor):** filter returns PaymentInstruction
  with beneficiary.account_number=None, beneficiary.name unchanged.
- **AC-R5-8 (payment, compliance):** unchanged.
- **AC-R5-9 (payment, null beneficiary):** beneficiary is None ->
  filter is no-op (no exception).
- **AC-R5-10 (non-mutation F19):** Input value checks:
  - original.ssn_last_four == original_value (str comparison)
  - original.beneficiary.account_number == original_value (value check)
- **AC-R5-11 (type-stable):** type(filter(claims, c)) is Client;
  type(filter(claims, p)) is PaymentInstruction.
- **AC-R5-12 (unsupported strict=False):** filter(claims, Holding(...))
  returns unchanged.
- **AC-R5-13 (unsupported strict=True, F17):** filter(claims,
  Holding(...), strict=True) raises UnsupportedTypeForFilterError.
- **AC-R5-14 (mnpi_check allow):** compliance + mnpi_flag=True -> ALLOW.
- **AC-R5-15 (mnpi_check deny):** advisor + mnpi_flag=True ->
  DENY / "mnpi_flag_set" / mnpi/security/mnpi_check.v1 / WSP-MNPI-3.1.
- **AC-R5-16 (mnpi_check no-flag):** advisor + mnpi_flag=False -> ALLOW.
- **AC-R5-17 (mnpi_check missing):** mnpi_flag=None + advisor -> DENY.
- **AC-R5-18 (drift, F13):** Remove Beneficiary.account_number via
  monkeypatch -> MnpiPolicy() raises AttributeError.

### R6. Determinism and Purity

#### R6.1 Determinism

Same PolicyInput -> equal PolicyDecision (==).
Same (claims, instance) -> equal model_dump().

#### R6.2 Purity (no side effects)

No env reads, no disk, no network, no logs, no datetime.now, no
mutation of inputs, no mutation of globals beyond __init__, no imports
outside the allow-list.

#### R6.3 Acceptance criteria

- **AC-R6-1:** 100 evaluate calls equal via == (structural, not
  identity; dict details compare by ==). (F20)
- **AC-R6-2:** 100 filter calls produce instances with identical
  model_dump() outputs.
- **AC-R6-3:** AST scan of authority.py and mnpi.py shows no forbidden
  imports.
- **AC-R6-4:** AST scan finds no datetime.now / time.time / random /
  open / Path.read / print / logging calls.

### R7. Fail-Closed on Evaluation Error

- Rule raises -> DENY / "evaluation_error" (LITERAL string).
- Rule returns wrong type -> same outcome.
- Engine NEVER returns None.

- **AC-R7-1:** ValueError("bad") -> DENY / "evaluation_error".
- **AC-R7-2:** RuntimeError("client@example.com") -> reason exactly
  "evaluation_error", no email in reason OR details.
- **AC-R7-3:** Engine NEVER returns None.
- **AC-R7-4:** Rule returning "ALLOW" (str) -> DENY /
  "evaluation_error".

### R8. Security Constraints

- Zero credentials in any file.
- No PII / MNPI in PolicyDecision.reason or details.
- No logging.
- No eval/exec/compile/__import__.
- model_copy used for non-mutation.

- **AC-R8-1:** grep for password|secret|api_key|AKIA|sk-|Bearer in
  src and test files returns zero matches.
- **AC-R8-2:** AST scan: no eval/exec/compile/__import__.
- **AC-R8-3:** After filter, input client's ssn_last_four value
  unchanged.
- **AC-R8-4:** With fixture client populated (email="test@example.com",
  ssn_last_four="1234", date_of_birth=date(1980,1,1),
  tax_id="TAX-EIN-1234"), engine-constructed PolicyDecision.reason
  and details values contain none of those substrings.

### R9. Module Boundary

Allowed imports:
- stdlib: __future__, dataclasses, enum, typing, re
- pydantic
- m1_identity -> AidClaims, Role
- m5_config_loader -> Archetype, Jurisdiction, RegistrationType
- m3_schema_registry -> Client, SecurityProfile,
  PaymentInstruction, ComplianceCheck, ComplianceAlert,
  Beneficiary (F10)

Forbidden:
- All other m*_ modules.
- os, requests, httpx, boto3, openai, anthropic, langchain,
  langfuse.

- **AC-R9-1:** AST scan of every src file asserts allow-list.
- **AC-R9-2:** AST scan of test file asserts allow-list.
- **AC-R9-3:** AST helper defined locally in test file.

### R10. Rule Traceability Table

```python
{
    "rule_applied": "authority/advisor/restricted_list.v1",
    "wsp_section": "WSP-TRD-3.1",
    "archetypes": ["ALL"],
    "actions": ["order.draft", "order.submit"],
    "rule_kind": "authority_gate",      # (F24)
    "decision_kinds": ["DENY"],
}
```

- **AC-R10-1:** AuthorityPolicy().rule_table() has 11 entries.
- **AC-R10-2:** MnpiPolicy().rule_table() has 5 entries.
- **AC-R10-3:** Every wsp_section matches the regex.
- **AC-R10-4:** decision_kinds subset of {ALLOW, DENY, ESCALATE}.
- **AC-R10-5 (F22):** Golden-vector test pins EXACT rule_table
  contents (rule_applied, wsp_section, sorted actions, sorted
  archetypes, rule_kind, sorted decision_kinds). Expected list
  declared as test constant.
- **AC-R10-6:** MNPI rule_table entries carry rule_kind in
  {mnpi_filter, mnpi_access}.

### R11. Public API Surface

```python
# src/m2_m4_policy_engine/__init__.py
from m2_m4_policy_engine.decisions import (
    Decision, PolicyDecision, PolicyInput, MAX_REASON_LEN,
    DECISION_TO_COMPLIANCE_DECISION,
)
from m2_m4_policy_engine.rules import (
    PolicyRule, RULE_APPLIED_RE, WSP_SECTION_RE,
)
from m2_m4_policy_engine.authority import AuthorityPolicy
from m2_m4_policy_engine.mnpi import MnpiPolicy, UnsupportedTypeForFilterError

__all__ = [
    "Decision", "PolicyDecision", "PolicyInput", "MAX_REASON_LEN",
    "DECISION_TO_COMPLIANCE_DECISION",
    "PolicyRule", "RULE_APPLIED_RE", "WSP_SECTION_RE",
    "AuthorityPolicy", "MnpiPolicy", "UnsupportedTypeForFilterError",
]
```

- **AC-R11-1:** Public import succeeds.
- **AC-R11-2:** __all__ contains exactly the names above.

### R12. Extensibility (Phase 2 OPA port)

Rule IDs match OPA package paths:
- authority/advisor/restricted_list.v1 -> authority.advisor.restricted_list / v1
- mnpi/security/mnpi_check.v1 -> mnpi.security.mnpi_check / v1

Phase 2 migration:
1. Transcribe each Python rule into .rego files under
   opa-bundles/<tier>/<package>.rego.
2. Each .rego carries the same wsp_section as # METADATA.
3. Python engine remains oracle — same input, same output.

- **AC-R12-1:** Every rule_applied matches the regex.
- **AC-R12-2:** authority.py and mnpi.py module-level docstrings
  identify each rule with its future Rego package path.

---

## 2. DESIGN

### 2.1 Directory structure

```
src/m2_m4_policy_engine/
  __init__.py                 # public API re-exports (~40 lines)
  decisions.py                # Decision, PolicyDecision, PolicyInput,
                              # DECISION_TO_COMPLIANCE_DECISION (~140 lines)
  rules.py                    # PolicyRule protocol, regex constants,
                              # _require() helper (~100 lines)
  authority.py                # AuthorityPolicy + 11 rules (~450 lines)
  mnpi.py                     # MnpiPolicy + 5 rules (~270 lines)

tests/unit/
  test_m2_m4_policy_engine.py # ~900 lines

opa-bundles/
  README.md                   # Phase 2 migration (~25 lines)
```

~1,000 lines implementation + ~900 lines tests.

### 2.2 decisions.py surface

```python
MAX_REASON_LEN: int = 200

class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    ESCALATE = "ESCALATE"

DECISION_TO_COMPLIANCE_DECISION: dict[Decision, str] = {
    Decision.ALLOW:    "ALLOW",
    Decision.DENY:     "DENY",
    Decision.ESCALATE: "REQUIRE_APPROVAL",
}

@dataclass(frozen=True)
class PolicyDecision:
    decision: Decision
    reason: str
    rule_applied: str
    wsp_section: str
    details: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.decision, Decision):
            raise TypeError("decision must be Decision")
        if not self.reason or len(self.reason) > MAX_REASON_LEN:
            raise ValueError("reason must be non-empty and <=200 chars")
        if not self.rule_applied:
            raise ValueError("rule_applied must be non-empty")
        if not self.wsp_section:
            raise ValueError("wsp_section must be non-empty")

@dataclass(frozen=True)
class PolicyInput:
    identity: AidClaims
    action: str
    target: Mapping[str, Any] = field(default_factory=dict)
    context: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.identity, AidClaims):
            raise TypeError("identity must be AidClaims")
        if not self.action:
            raise ValueError("action must be non-empty")
```

### 2.3 rules.py surface

```python
RULE_APPLIED_RE = re.compile(r"^(authority|mnpi)/[a-z_]+/[a-z_]+\.v\d+$")
WSP_SECTION_RE  = re.compile(r"^WSP-[A-Z]+-\d+(\.\d+)?$")

_VALID_RULE_KINDS = frozenset({
    "authority_gate", "authority_meta", "mnpi_filter", "mnpi_access"
})

@runtime_checkable
class PolicyRule(Protocol):
    name: str
    rule_applied: str
    wsp_section: str
    archetypes: frozenset
    actions: frozenset
    rule_kind: str
    decision_kinds: frozenset

    def evaluate(self, inp: PolicyInput) -> Optional[PolicyDecision]: ...


def _require(mapping, key, mapping_name, rule_applied, wsp_section):
    """Fetch key from mapping. Return (value, None) or (None, DENY-decision)."""
    if key not in mapping or mapping[key] is None:
        return None, PolicyDecision(
            decision=Decision.DENY,
            reason=f"missing_{mapping_name}:{key}",
            rule_applied=rule_applied,
            wsp_section=wsp_section,
            details={},
        )
    return mapping[key], None
```

### 2.4 authority.py class surface

```python
class AuthorityPolicy:
    def __init__(self) -> None:
        self._unknown_action_rule = _UnknownActionRule()
        self._default_deny_rule   = _DefaultDenyRule()
        self._rules: tuple[PolicyRule, ...] = self._build_rules()

    def _build_rules(self) -> tuple[PolicyRule, ...]: ...
    def evaluate(self, inp: PolicyInput) -> PolicyDecision: ...
    def list_rules(self) -> list[tuple[str, str]]: ...
    def rule_table(self) -> list[dict]: ...
```

list_rules() order (11 entries):
1. authority/meta/excludes_check.v1
2. authority/advisor/restricted_list.v1
3. authority/advisor/trading_window.v1
4. authority/advisor/chinese_wall.v1
5. authority/advisor/pod_isolation.v1
6. authority/advisor/read_other_advisor_clients.v1
7. authority/advisor/read_own_clients.v1
8. authority/advisor/concentration_limit.v1
9. authority/principal/review_required.v1
10. authority/meta/default_deny.v1
11. authority/meta/unknown_action.v1

### 2.5 mnpi.py class surface

```python
class UnsupportedTypeForFilterError(TypeError):
    """Raised when filter(..., strict=True) receives an unknown instance type."""

class MnpiPolicy:
    def __init__(self) -> None:
        if "account_number" not in Beneficiary.model_fields:
            raise AttributeError(
                "M3 drift: Beneficiary.account_number field missing. "
                "M4 mnpi/payment/account_visibility.v1 depends on it."
            )
        self._field_rules = _FIELD_RULES
        self._access_rules = _ACCESS_RULES

    def filter(self, claims, instance, *, strict=False): ...
    def check_mnpi_access(self, claims, security): ...
    def list_rules(self): ...
    def rule_table(self): ...
```

### 2.6 Security invariants (code-enforced)

| Invariant | How enforced |
|-----------|-------------|
| No credentials | Test greps source + test files |
| No LLM imports | AST scan |
| No other m*_ imports | AST scan |
| No side effects | AST scan for datetime.now, open(, etc. |
| Input non-mutation | Value-equality test |
| Decision immutability | frozen dataclass + __post_init__ |
| wsp_section on every rule | AC-R2-4 regex test |
| evaluation_error reason LITERAL | AC-R7-2 |
| Beneficiary drift fails construction | AC-R5-18 |

### 2.7 Imports table

| File | Allowed |
|------|---------|
| __init__.py | re-exports only |
| decisions.py | stdlib; m1_identity.AidClaims |
| rules.py | stdlib; m5_config_loader.Archetype; local decisions |
| authority.py | stdlib; m1_identity.{AidClaims,Role}; m5_config_loader.{Archetype,RegistrationType}; local decisions+rules |
| mnpi.py | stdlib; pydantic.BaseModel; m1_identity.{AidClaims,Role}; m5_config_loader.Archetype; m3_schema_registry.{Client,SecurityProfile,PaymentInstruction,Beneficiary}; local decisions |

---

## 3. TASKS

Each task produces implementation AND tests.

### T1. Scaffold module layout.
- Create src/m2_m4_policy_engine/__init__.py with stub exports.
- Create decisions.py, rules.py, authority.py, mnpi.py empty with
  docstrings.
- Create opa-bundles/README.md with Phase 2 migration text.

### T2. Implement Decision, PolicyDecision, PolicyInput,
DECISION_TO_COMPLIANCE_DECISION.
Covers AC-R1-1..AC-R1-12.

### T3. Implement PolicyRule protocol + regex constants + _require().
Covers AC-R10-3, AC-R12-1.

### T4. Implement AuthorityPolicy skeleton + 3 meta rules
(excludes_check, default_deny, unknown_action) + engine loop.
Covers AC-R1-8, AC-R2-6, AC-R4-2-*.

### T5. advisor.read_own_clients + advisor.read_other_advisor_clients.
Covers AC-R4-3-*, AC-R4-4-*.

### T6. advisor.restricted_list_check.
Covers AC-R4-5-*.

### T7. advisor.trading_window_check.
Covers AC-R4-6-*.

### T8. advisor.concentration_limit (ESCALATE, strict float check).
Covers AC-R4-7-*.

### T9. advisor.chinese_wall (tier1-gated).
Covers AC-R4-8-*.

### T10. advisor.pod_isolation (tier5-gated).
Covers AC-R4-9-*.

### T11. principal.review_required (ESCALATE, BD-gated).
Covers AC-R4-10-*.

### T12. Engine DENY-OVERRIDES semantics.
- restricted-list DENY beats downstream ALLOW.
- ALLOW followed by ESCALATE returns ESCALATE (AC-R2-8).
- list_rules() returns 11 tuples in order (AC-R2-1, AC-R2-7).
- Determinism (AC-R3-2, AC-R3-3, AC-R6-1).

### T13. Exception handling (R7).
Test subclass injection via _build_rules override.
Covers AC-R7-1..AC-R7-4.

### T14. Role.system and Role.agent handling (F7).
Covers AC-R4-11-*.

### T15. AuthorityPolicy.rule_table() + golden-vector.
Covers AC-R10-1, AC-R10-3..5.

### T16. MnpiPolicy + 3 Client field rules + drift check in __init__.
Covers AC-R5-1..AC-R5-6, AC-R5-18.

### T17. MnpiPolicy nested PaymentInstruction rule.
Covers AC-R5-7..AC-R5-9.

### T18. Non-mutation + type-stability + strict mode.
Covers AC-R5-10..AC-R5-13.

### T19. check_mnpi_access (R5.5).
Covers AC-R5-14..AC-R5-17.

### T20. MnpiPolicy.rule_table() + list_rules() + golden-vector.
Covers AC-R10-2, AC-R10-6.

### T21. Determinism + purity battery (R6).
- 100-call determinism (AC-R6-1, AC-R6-2).
- AST scan forbidden imports (AC-R6-3).
- AST scan forbidden calls (AC-R6-4).

### T22. Security invariants (R8).
- grep for secrets (AC-R8-1).
- AST scan for eval/exec/compile (AC-R8-2).
- Non-mutation proof (AC-R8-3).
- PII-in-reason audit (AC-R8-4).

### T23. Module boundary AST scan (R9).
Covers AC-R9-1..AC-R9-3.

### T24. Public API surface test (R11).
Covers AC-R11-1, AC-R11-2.

### T25. Integration smoke test (F23).
- Real AidClaims from M1 + real Client from M3.
- Assert evaluate + filter with exact rule_applied, wsp_section, and
  filtered field values.

### T26. M1/M3/M5 drift tests (§0.7).
Concrete assertions: Role.compliance_officer, Archetype.tier1/tier5,
RegistrationType.bd_only/dual_registered, Client fields, Beneficiary
field, SecurityProfile field.

---

## 4. CROSS-REFERENCES

- ARCH-09 M2/M4 rows.
- ARCH-07 Tech Stack: Phase 2 FastAPI+OPA; Phase 1 library-only.
- 007-consolidated-design-and-plan.md: Part 3, Part 6.
- IMPL-06 Blocker 4: principal review queue.
- ARCH-06 Gap 3 WSP-to-YAML: rule_table() is the Python side.
- Steering rules 5, 7, 8, 9, 17, 19, 20.

---

## 5. NON-GOALS SUMMARY

- No LLM.
- No OPA sidecar in Phase 1.
- No Rego files in Phase 1.
- No caching.
- No FastAPI surface in Phase 1.
- No M10 writes.
- No config reads.
- No network I/O.
- No rule hot-reload.
- No email/phone field filters on Client (Phase 2).
- No senior_advisor role (Phase 2 adds to M1).
- No authority_scope enforcement (Phase 2).
- No payment.draft rule (Phase 2).
- No Gap 6.
- No post-validation of user rule reason (Phase 2).

---

## 6. REVIEW FIX TRACEABILITY

| REVIEW item | v2 fix location |
|-------------|-----------------|
| F1 R2.2 ordering semantics | §2.2 deny-overrides block + worked example |
| F2 T12 ALLOW+ESCALATE | AC-R2-8 |
| F3 dual_registered intentional | R4.10 F3 note |
| F4 missing target/context unified | R1.5 + _require() |
| F5 Phase 1 predicate literal | R5.2 _IS_COMPLIANCE_OFFICER |
| F6 client.list in read_other | R4.4 + AC-R4-4-4 |
| F7 Role.system/agent | R4.11 + AC-R4-11-* |
| F8 literal examples | R1.3 |
| F9 meta rules distinguished | R1.4 + R4.1 |
| F10 Beneficiary allow-listed | R9 |
| F11 Decision mapping | R1.1 table + AC-R1-12 |
| F12 authority_scope Phase 2 | R4.2 |
| F13 Beneficiary drift at __init__ | §0.7 + R5.4 + AC-R5-18 |
| F14 concentration_pct type | R4.7 + AC-R4-7-5..7 |
| F15 reason LITERAL | §0.3 + R7 + AC-R7-2 |
| F16 post-validation Phase 2 | §0.2 + R7 |
| F17 strict mode | R5.1 + AC-R5-13 |
| F18 module vs E2E guarantee | §0.6 |
| F19 identity vs value semantics | AC-R5-10 |
| F20 structural equality | AC-R6-1 |
| F21 test subclass injection | T13 |
| F22 golden-vector rule_table | AC-R10-5 |
| F23 smoke test executable | T25 |
| F24 rule_kind | R10 + AC-R10-6 |
| F25 FastAPI Phase 2 only | §0.1 |
| F26 drift-test concrete cases | §0.7 |
| F27 authority_excludes rule | R4.2 |
| F28 principal Phase 2 extensions | R4.10 F28 note |
| F29 payment.draft Phase 2 | §0.2 + R1.4 |
| F30 Gap 6 boundary | §0.2 |

All 17 REQUIRED fixes LANDED.
All 13 RECOMMENDED fixes LANDED.

---

*m2-m4-policy-engine.md — v2 — Project 007 FSI Interoperability Platform*
