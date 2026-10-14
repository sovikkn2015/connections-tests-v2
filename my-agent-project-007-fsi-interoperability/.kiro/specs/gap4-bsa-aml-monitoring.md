# Gap 4 — BSA/AML Ongoing Monitoring — Spec (v2, post-review)

> Sub-module: Gap 4 BSA/AML Monitoring
> Parent module: M2 (Authority Policy) + M10 (Audit Logger)
> Phase: 3 (BD onboarding — after Execution Specialist per ARCH-06 §P2)
> Agent: 007-compliance-agent
> Source docs: ARCH-06 v3 (Gap 4), ARCH-09 (compliance sub-modules),
>   007-consolidated-design-and-plan.md (Part 9, Gap 4),
>   IMPL-06 (blocker matrix), 31 CFR §1010.311 (CTR threshold),
>   31 U.S.C. §5318(g)(2) (anti-tipping-off), steering rules
>   5 (OPA-only), 6 (fail-closed), 19 (wsp_section), 23 (SAR
>   confidentiality).
> Related: M5 `BsaAmlConfig` (already built — `src/m5_config_loader/
>   loader.py` line 232), M3 `Transaction` + `TransactionType`,
>   M10 `AuditLogger` + `AuditEntry`, M2 `PolicyRule` Protocol.
> Status: v2 — addresses F1..F9, R1..R8 from v1 review.

---

## 0. CONTEXT AND SCOPE

The Bank Secrecy Act (31 U.S.C. §5311 et seq.) and FinCEN
regulations require every broker-dealer to file:

- **CTR (Currency Transaction Report)** for any cash transaction or
  aggregate of same-day cash transactions per customer exceeding
  $10,000 (31 CFR §1010.311).
- **SAR (Suspicious Activity Report)** when a pattern suggests
  structuring — multiple deposits just below the CTR threshold
  designed to evade reporting (31 CFR §1023.320).

Project 007's v2 Onboarding Specialist handles KYC and sanctions
screening at account opening. Gap 4 adds **ongoing** post-trade
monitoring: every cash transaction that reaches M6's post-trade
hook is evaluated by deterministic OPA rules; alerts are emitted
to the compliance officer ONLY (steering rule 23 / 31 U.S.C.
§5318(g)(2)).

Gap 4 lives in `src/compliance/gap4_bsa_aml_monitoring/`. Python
3.12+, Pydantic v2. NO LLM calls for classification. Rego rules
in `opa-bundles/bsa-aml/` are the canonical authority; the Python
engine is a deterministic, test-oracle-style evaluator that mirrors
the Rego logic bit-for-bit (Phase 3 keeps Python as the runtime
while Phase 4 promotes OPA to the runtime per the M2 playbook).

### 0.1 Non-goals

- Does NOT evaluate non-BSA/AML rules (M2 authority rules remain
  separate; Gap 4 is a bolt-on rule pack).
- Does NOT call external OFAC APIs (sanctions list is a loaded
  `frozenset[str]` owned by a caller-supplied data provider).
- Does NOT parse or render XML CTR filings (Phase 4).
- Does NOT persist state across process restarts in Phase 3
  (in-memory `WindowStore`). Redis adapter is a **stub** with a
  clearly labelled `NotImplementedError` (Phase 4 wires real
  Redis).
- Does NOT emit alerts to advisors or clients. Compliance officer
  ONLY. See steering rule 23.
- Does NOT call out to M10 synchronously from OPA logic; alert
  emission is an explicit Python-side step after rule evaluation.
- Does NOT route on archetype when `BsaAmlConfig.enabled=False` —
  the whole sub-module short-circuits (R6.1).

**Phase 4 forward-compat:**
- `WindowStore` Protocol ships with `InMemoryWindowStore`. Phase
  4 adds `RedisWindowStore` behind the same interface. No Gap 4
  caller changes required.
- `BsaAmlAlert.schema_version: Literal["1.0.0"]`. Phase 4 adds
  `ofac_list_version` + `cdd_refresh_due` under bumped schema.
- Rego rules with `wsp_section` annotations are already the
  Phase-4 authority; the Python engine is a temporary runtime.

### 0.2 Directory layout

```
src/compliance/gap4_bsa_aml_monitoring/
  __init__.py          # public API re-exports
  models.py            # Pydantic v2: BsaAmlAlert, CashTransaction, ...
  window_store.py      # WindowStore Protocol + InMemory + Redis stub
  monitors.py          # CtrMonitor + SarStructuringMonitor
  rules.py             # M2 PolicyRule adapters (CTR + SAR)
  audit_emitter.py     # M10 AuditEntry construction + write hook
  config.py            # BsaAmlConfig wiring (reads M5 + short-circuits)

opa-bundles/bsa-aml/
  ctr.rego             # Currency Transaction Report rule
  sar_structuring.rego # SAR structuring detection rule
  bundle.yaml          # OPA bundle manifest (phase 4 build target)
  README.md            # rule inventory + wsp_section table
```

### 0.3 Allowed imports

- stdlib: `__future__`, `collections`, `dataclasses`, `enum`,
  `hashlib`, `json`, `re`, `typing`, `datetime`, `decimal`,
  `threading`.
- `pydantic` (v2 only).
- `m3_schema_registry` (for `Transaction`, `TransactionType`,
  `AuditEntry`, `ProvenanceStage`).
- `m5_config_loader` (for `BsaAmlConfig`).
- `m10_audit_logger` (for `AuditLogger`, `AuditWriteError`).
- `m2_m4_policy_engine` (for `PolicyRule`, `PolicyDecision`,
  `PolicyInput`, `Decision`, `RULE_APPLIED_RE`, `WSP_SECTION_RE`).

FORBIDDEN: any other `m*_` module, LLM SDKs, `boto3`, `httpx`,
`requests`, network libs.

### 0.4 Threading

`InMemoryWindowStore` is **thread-safe**: every mutating method
takes `threading.Lock()` (R4.3). Monitors are stateless over the
store. Pydantic models are frozen.

### 0.5 Line budget

ARCH-06 target: ~1,100 lines (Python 600 + Rego 400 + fixtures 100).

- `models.py`: ~160
- `window_store.py`: ~120
- `monitors.py`: ~190
- `rules.py`: ~130
- `audit_emitter.py`: ~110
- `config.py`: ~55
- `__init__.py`: ~60
- Tests: ~900
- Rego rules: ~180 (ctr.rego + sar_structuring.rego + bundle.yaml)

Python source ≈ 825. Rego ≈ 180. On target.

---

## 1. REQUIREMENTS

### R1. Cash transaction model

**R1.1** `CashTransactionCategory` enum with 4 values:
- `cash_deposit` — physical currency deposit
- `cash_withdrawal` — physical currency withdrawal
- `wire_in` — incoming wire transfer
- `wire_out` — outgoing wire transfer

**R1.2** `CashTransaction` frozen Pydantic model
(`ConfigDict(frozen=True, extra="forbid")`):

| Field           | Type                      | Notes                                   |
|-----------------|---------------------------|-----------------------------------------|
| `txn_id`        | `UUID`                    | Primary key.                            |
| `client_id`     | `UUID`                    | Canonical client ID (M3).               |
| `account_id`    | `UUID`                    | Canonical account ID (M3).              |
| `category`      | `CashTransactionCategory` | Enum.                                   |
| `amount_usd`    | `Decimal`                 | Min 0, max 1e12. USD only.              |
| `occurred_at`   | `datetime` (tz-aware)     | UTC. Naive → ValueError.                |
| `firm_id`       | `str` (min 1, max 100)    | For multi-tenant isolation.             |
| `source_txn_ref`| `str` (min 1, max 200)    | Custodian/bank txn ID.                  |
| `trace_id`      | `str` (min 1, max 200)    | M10 audit link.                         |

**R1.3** `amount_usd` uses `decimal.Decimal` (not float) to avoid
$10_000.00 boundary float drift. Comparison uses `>=` / `>` with
Decimal constants (`CTR_THRESHOLD_USD = Decimal("10000.00")`,
`SAR_STRUCTURING_UPPER = Decimal("10000.00")`,
`SAR_STRUCTURING_LOWER = Decimal("7000.00")`).

**R1.4** `CashTransaction.from_m3(txn: Transaction) -> CashTransaction`
adapter — derives `category` from M3 `TransactionType`:
- `wire_in` → `wire_in`
- `wire_out` → `wire_out`
- `contribution` AND `source_transaction_type == "cash_deposit"`
  → `cash_deposit`
- `distribution` AND `source_transaction_type == "cash_withdrawal"`
  → `cash_withdrawal`
- Else → `NotACashTransactionError` (typed exception, caller skips).

`amount_usd` is `Decimal(str(txn.amount))` — string conversion
prevents float→Decimal drift.

### R2. Alert model

**R2.1** `AlertSeverity` enum: `low`, `medium`, `high`, `critical`.

**R2.2** `AlertType` enum: `ctr_threshold`, `ctr_aggregate`,
`sar_structuring`.

**R2.3** `BsaAmlAlert` frozen Pydantic model
(`ConfigDict(frozen=True, extra="forbid")`):

| Field                  | Type                        | Notes                                 |
|------------------------|-----------------------------|---------------------------------------|
| `schema_version`       | `Literal["1.0.0"]`          | Pinned.                               |
| `alert_id`             | `UUID`                      |                                       |
| `rule_id`              | `str` pattern M2 regex      | `"authority/bsa_aml/ctr.v1"` etc.     |
| `alert_type`           | `AlertType`                 |                                       |
| `severity`             | `AlertSeverity`             |                                       |
| `client_id`            | `UUID`                      |                                       |
| `firm_id`              | `str`                       |                                       |
| `threshold_type`       | `str` (min 1, max 80)       | `"ctr_single"`, `"ctr_aggregate_24h"` |
| `threshold_value_usd`  | `Decimal`                   |                                       |
| `matched_transactions` | `tuple[UUID, ...]`          | Min 1. Each element unique.           |
| `matched_amount_usd`   | `Decimal`                   | Sum of matched tx amounts.            |
| `wsp_section`          | `str` pattern M2 regex      | From OPA rule annotation.             |
| `rule_applied`         | `str` pattern M2 regex      |                                       |
| `route_to`             | `Literal["compliance_officer"]` | IMMUTABLE. Steering rule 23.      |
| `do_not_notify`        | `tuple[str, ...]`           | Always contains `"advisor"`, `"client"`. |
| `detected_at`          | `datetime` (tz-aware UTC)   |                                       |
| `reason_code`          | `str` pattern `[a-z_]+`     | Frozen reason vocabulary (R2.4).      |
| `reason_detail`        | `str` (max 500, no PII)     | Rejects SSN/email/account/IBAN.       |

**R2.4** Frozen reason vocabulary:
```python
ALERT_REASONS: frozenset[str] = frozenset({
    "ctr_threshold_exceeded",
    "ctr_aggregate_exceeded",
    "structuring_pattern_detected",
})
```

Any other reason → ValidationError at construction.

**R2.5** Invariants enforced in `model_validator(mode="after")`:
- `route_to == "compliance_officer"` — always.
- `"advisor"` in `do_not_notify` — always.
- `"client"` in `do_not_notify` — always.
- `matched_transactions` elements unique (`len(set) == len(tuple)`).
- `len(matched_transactions) >= 1`.
- `matched_amount_usd > 0`.

### R3. Deterministic monitors

**R3.1** `CtrMonitor` — deterministic detector. Public API:

```python
class CtrMonitor:
    RULE_ID: str = "authority/bsa_aml/ctr.v1"
    WSP_SECTION: str = "WSP-BSA-8.2"

    def __init__(
        self,
        *,
        store: WindowStore,
        config: BsaAmlConfig,
        clock: Callable[[], datetime],
    ) -> None: ...

    def evaluate(
        self, txn: CashTransaction
    ) -> tuple[BsaAmlAlert, ...]: ...
```

Behavior:
1. If `config.enabled is False` → return empty tuple. No store
   write. No side effect. (R6.1)
2. Record `txn` in `store` under key `(firm_id, client_id)` with
   `occurred_at`.
3. Single-transaction check: `txn.amount_usd >=
   config.ctr_threshold` AND `txn.category in {cash_deposit,
   cash_withdrawal}` → emit `ctr_single` alert.
4. 24h aggregate check: `sum(store.within(
   (firm_id, client_id), txn.occurred_at - 24h, txn.occurred_at,
   categories={cash_deposit, cash_withdrawal})) >
   config.ctr_threshold` → emit `ctr_aggregate_24h` alert (the
   **boundary** is `>` strict, matching FinCEN guidance that
   exactly $10,000 is a single-txn CTR trigger but the aggregate
   rule applies when the day total **exceeds** $10,000).

**R3.2** `SarStructuringMonitor` — deterministic structuring
detector. Public API mirrors `CtrMonitor`:

```python
class SarStructuringMonitor:
    RULE_ID: str = "authority/bsa_aml/sar_structuring.v1"
    WSP_SECTION: str = "WSP-BSA-8.1"
```

Behavior:
1. If `config.enabled is False` → return empty tuple.
2. Record `txn`.
3. 7-day rolling window: count cash transactions for
   `(firm_id, client_id)` where `amount_usd >=
   config.sar_structuring_threshold` AND `amount_usd <
   config.ctr_threshold` AND `category in {cash_deposit,
   cash_withdrawal}`.
4. If count >= 3 → emit `sar_structuring` alert with
   `severity=critical` (structuring is a felony under 31 U.S.C.
   §5324).

Thresholds: `sar_structuring_threshold = 7000.00`,
`ctr_threshold = 10000.00`. Per user request: detect "3+ cash
deposits between $7k-$10k in 7 days." The upper bound is **strict
less-than** `10000.00` to exclude transactions that are already
CTR-triggering.

**R3.3** `CtrMonitor.evaluate()` and `SarStructuringMonitor.evaluate()`
MUST be called in this order by the orchestrator (Gap 4
`BsaAmlEngine.evaluate_post_trade`). Ordering guarantees:
- CTR alert fires first for single transactions that breach $10K
  (structuring check would ignore them because they are at/above
  the CTR threshold).
- Structuring alert fires for aggregate patterns — never
  suppressed by an earlier CTR alert (the same txn CAN trigger
  both; alerts are independent).

### R4. Window store

**R4.1** `WindowStore` Protocol:

```python
class WindowStore(Protocol):
    def record(self, key: tuple[str, UUID], txn: CashTransaction) -> None: ...
    def within(
        self,
        key: tuple[str, UUID],
        *,
        start: datetime,
        end: datetime,
        categories: frozenset[CashTransactionCategory] | None = None,
    ) -> tuple[CashTransaction, ...]: ...
    def purge_before(self, threshold: datetime) -> int: ...
```

**R4.2** `InMemoryWindowStore` implementation:
- Backing store: `dict[tuple[str, UUID], list[CashTransaction]]`.
- `record` appends and keeps list sorted by `occurred_at` ASC
  (bisect.insort for determinism).
- `within` filters by time range `(start, end]` inclusive on end,
  exclusive on start (R4.5), optional category filter.
- `purge_before` removes any txn with `occurred_at < threshold`;
  returns removed count.
- Thread-safe via `threading.Lock()` (R4.3).

**R4.3** Every mutating method takes a lock. Read methods (`within`)
also take the lock to avoid iteration-during-mutation.

**R4.4** `RedisWindowStore` stub: constructor accepts a `redis_url:
str`, every method raises `NotImplementedError("redis backend is
Phase 4 — see spec 0.1")`. The stub exists so imports do not break
Phase 4 adapters.

**R4.5** Window boundary semantics:
- `within(start, end)` returns transactions with
  `start < occurred_at <= end`. Half-open, end-inclusive.
- Rationale: the "current" transaction at `now` is always included
  in its own lookup; the far edge (exactly 24h ago) is excluded.

### R5. M2 `PolicyRule` adapters

**R5.1** `CtrPolicyRule` implements the `PolicyRule` Protocol from
`m2_m4_policy_engine.rules`:
- `name = "authority.bsa_aml.ctr"`
- `rule_applied = "authority/bsa_aml/ctr.v1"`
- `wsp_section = "WSP-BSA-8.2"`
- `archetypes = frozenset()` (all)
- `actions = frozenset({"order.submit", "payment.draft"})`
- `rule_kind = "authority_gate"`
- `decision_kinds = frozenset({"ESCALATE"})`

**R5.2** `.evaluate(inp: PolicyInput) -> PolicyDecision | None`:
- Read `CashTransaction` from `inp.context["cash_transaction"]`
  via `_require` (fail-closed if missing).
- Read `BsaAmlEngine` from `inp.context["bsa_aml_engine"]` via
  `_require`.
- If `engine.config.enabled is False` → `None` (abstain — R6.1).
- Call `engine.evaluate_post_trade(cash_txn)` — returns
  `tuple[BsaAmlAlert, ...]`.
- If any alert → return `PolicyDecision(ESCALATE,
  reason="ctr_alert_triggered", rule_applied=RULE_ID,
  wsp_section=WSP_SECTION, details={"alert_ids": [...] })`.
- Else → `None`.

**R5.3** `SarStructuringPolicyRule` — identical shape with SAR
values.

**R5.4** Both adapters pass the M2 `PolicyRule` Protocol check:
`assert isinstance(CtrPolicyRule(engine), PolicyRule)`.

### R6. Config short-circuit

**R6.1** `BsaAmlEngine.__init__` reads `BsaAmlConfig`. If
`config is None` OR `config.enabled is False`:
- `evaluate_post_trade(txn)` returns empty tuple.
- `record(txn)` is a **no-op** (store is not touched).
- `PolicyRule.evaluate` returns `None`.
- No audit entries are emitted.
- No imports of Redis, no background threads, no network I/O.

**R6.2** "no side effects" invariant is verified by T4.22 — the
test constructs an engine with `enabled=False`, feeds 100 txns,
asserts the underlying store has zero records AND no `AuditEntry`
was written.

**R6.3** Runtime toggle: caller may re-instantiate the engine with
a new `BsaAmlConfig` — Gap 4 does NOT hot-reload config. Config is
immutable per engine instance.

### R7. M10 audit emission

**R7.1** `AuditEmitter` wraps an `AuditLogger`. Every alert path
emits one `AuditEntry`:

```python
class AuditEmitter:
    def __init__(self, *, audit: AuditLogger, firm_id: str) -> None: ...

    def emit(
        self,
        *,
        alert: BsaAmlAlert,
        actor_id: str,
        cash_txn: CashTransaction,
    ) -> AuditEntry: ...
```

**R7.2** `AuditEntry` field population:
- `canonical_id` — `uuid4()` (caller supplies clock/id separately
  for determinism; see R7.5).
- `trace_id` — `cash_txn.trace_id`.
- `timestamp` — `alert.detected_at`.
- `actor_id` — injected (e.g., `"system:bsa_aml_engine"`).
- `action` — `"bsa_aml.alert_emitted"`.
- `module` — `"m10"` (the emitter runs alongside M10).
- `target_type` — `"cash_transaction"`.
- `target_id` — `str(cash_txn.txn_id)`.
- `decision` — `"ESCALATE"`.
- `reason` — `alert.reason_code`.
- `input_hash` — SHA-256 of `cash_txn.model_dump_json()`.
- `output_hash` — SHA-256 of `alert.model_dump_json()`.
- `policy_bundle_version` — `"bsa-aml/1.0.0"`.
- `rule_applied` — `alert.rule_applied`.
- `wsp_section` — `alert.wsp_section`.
- `latency_ms` — 0 (Phase 3; Phase 4 adds real timing).
- `firm_id` — `alert.firm_id`.
- `worm_record_id` — `f"bsa-aml/{alert.alert_id}"`.
- `sha256_integrity` — `""` (M10 attaches on write).
- `retention_years` — 6 (SEC 17a-4 floor).

**R7.3** Anti-tipping-off invariants (31 U.S.C. §5318(g)(2)):
- `AuditEntry.reason` never contains the verbatim SAR narrative.
- `AuditEntry.target_type` is `"cash_transaction"`, NOT
  `"sar_filing"` (no indication to a log reader that a SAR is
  about to be filed; only compliance officers with WORM access
  see the full chain).
- `AuditEntry.action` is `"bsa_aml.alert_emitted"` for ALL alert
  types (CTR, SAR aggregate, SAR structuring) — uniform action
  string prevents information leakage to log observers who lack
  the reason-code vocabulary.

**R7.4** If `AuditLogger.write` raises `AuditWriteError`, the
emitter re-raises as `AlertEmitFailed(reason)` with frozen reason
`"audit_write_failed"`. The alert is NOT silently dropped. Fail-
closed.

**R7.5** Determinism: the emitter accepts a `canonical_id: UUID |
None` parameter (default `None` → `uuid4()`) so tests can pin IDs.
Clock is taken from `alert.detected_at`, not from the emitter.

### R8. Rego rules

**R8.1** `opa-bundles/bsa-aml/ctr.rego` implements `ctr_required`
and `ctr_aggregate_required` deterministic rules. Every rule MUST
carry a `# METADATA` block with:
```rego
# METADATA
# title: CTR threshold check
# description: Flags cash transactions >= $10,000 per 31 CFR §1010.311
# custom:
#   wsp_section: "WSP-BSA-8.2"
#   gap: 4
#   severity: "ESCALATE"
```

**R8.2** `opa-bundles/bsa-aml/sar_structuring.rego` implements
`structuring_alert` with `wsp_section: "WSP-BSA-8.1"`.

**R8.3** `bundle.yaml` manifest lists both rule files + the Python
oracle reference + the Phase-4 promotion status.

**R8.4** CI hook (Gap 3 `scan_rego_file`) verifies every Rego rule
in this bundle has a `wsp_section` annotation. Build fails if any
are missing.

### R9. Security

**R9.1** PII regex on `BsaAmlAlert.reason_detail` — same regex
set as Gap 2/6. Match → ValidationError.

**R9.2** No credentials, no secrets. `RedisWindowStore` accepts a
`redis_url` string but never parses embedded credentials (Phase 4
uses Vault).

**R9.3** Alerts routed to compliance_officer ONLY. Route field is
`Literal["compliance_officer"]` — type-system enforced, not runtime.

**R9.4** No logging of PII. Alert `reason_detail` is capped at 500
chars and PII-filtered.

**R9.5** Thread safety — every mutating path on
`InMemoryWindowStore` is inside `threading.Lock()`.

---

## 2. DESIGN

### 2.1 Wiring diagram

```
M3 Transaction (from M7 translator)
      │
      ▼
CashTransaction.from_m3  (raises NotACashTransactionError for non-cash)
      │
      ▼
M6 post-trade hook ──► BsaAmlEngine.evaluate_post_trade(cash_txn)
                              │
                              ├─ if config.enabled is False → () [no-op]
                              │
                              ├─ WindowStore.record(txn)
                              │
                              ├─ CtrMonitor.evaluate(txn) ─► [alerts...]
                              │
                              └─ SarStructuringMonitor.evaluate(txn)
                                           │
                                           ▼
                                   [alerts...]
                                           │
      ┌────────────────────────────────────┘
      ▼
AuditEmitter.emit(alert, ...)  ── one AuditEntry per alert
      │
      ▼
M10 AuditLogger.write  → Langfuse + WORM + CRM (compliance partition)
      │
      ▼
(Phase 4) SAR filing queue ── compliance officer only
```

### 2.2 File layout (repeats §0.2 with line estimates)

```
src/compliance/gap4_bsa_aml_monitoring/
  __init__.py           # ~60
  models.py             # ~160
  window_store.py       # ~120
  monitors.py           # ~190
  rules.py              # ~130
  audit_emitter.py      # ~110
  config.py             # ~55   (BsaAmlEngine orchestrator lives here)

opa-bundles/bsa-aml/
  ctr.rego              # ~70
  sar_structuring.rego  # ~80
  bundle.yaml           # ~30
  README.md             # ~40

tests/unit/
  test_gap4_bsa_aml_monitoring.py  # ~900
tests/integration/
  test_gap4_m2_policy_engine_roundtrip.py  # ~120
```

### 2.3 Orchestrator — `BsaAmlEngine`

```python
class BsaAmlEngine:
    def __init__(
        self,
        *,
        config: BsaAmlConfig | None,
        store: WindowStore,
        clock: Callable[[], datetime],
        audit_emitter: AuditEmitter | None = None,
    ) -> None:
        self._config = config
        self._store = store
        self._clock = clock
        self._emitter = audit_emitter
        self._ctr = CtrMonitor(store=store, config=config, clock=clock)
        self._sar = SarStructuringMonitor(store=store, config=config, clock=clock)

    @property
    def config(self) -> BsaAmlConfig | None: ...

    def evaluate_post_trade(
        self, cash_txn: CashTransaction
    ) -> tuple[BsaAmlAlert, ...]:
        if self._config is None or not self._config.enabled:
            return ()
        alerts = (*self._ctr.evaluate(cash_txn),
                  *self._sar.evaluate(cash_txn))
        if self._emitter is not None:
            for a in alerts:
                self._emitter.emit(alert=a, actor_id="system:bsa_aml_engine",
                                   cash_txn=cash_txn)
        return alerts
```

### 2.4 Rego rule sketch (ctr.rego)

```rego
# METADATA
# title: CTR threshold check
# description: Flags cash transactions >= $10,000 per 31 CFR §1010.311
# custom:
#   wsp_section: "WSP-BSA-8.2"
#   gap: 4
#   severity: "ESCALATE"
package authority.bsa_aml.ctr

import rego.v1

default ctr_required := false

ctr_required if {
    input.category in {"cash_deposit", "cash_withdrawal"}
    input.amount_usd >= 10000
}

aggregate_ctr_required if {
    sum([t.amount_usd |
        t := input.window_transactions[_];
        t.category in {"cash_deposit", "cash_withdrawal"}
    ]) > 10000
}
```

### 2.5 Module boundary

- IMPORTS: listed in §0.3. Every import is to a module that is
  already Phase-3-complete.
- DOES NOT IMPORT: other gaps (Gap 1/2/3/5/6/7), Gap 4 is
  self-contained.
- DOES NOT MUTATE: any data owned by another module. Only reads
  `BsaAmlConfig` + `AuditLogger`.

### 2.6 Test fixtures

- `make_cash_txn(amount, category, occurred_at)` factory.
- `make_bsa_aml_config(enabled=True, ctr=10000, sar=7000)` factory.
- `DeterministicClock` — `Callable[[], datetime]` backed by a list
  of timestamps.
- `RecordingAuditLogger` — `InMemoryAuditBackend` × 3 + DLQ, wired
  into a real `AuditLogger`. Captures every written entry for
  assertions.

---

## 3. TASKS

T4.1  — `CashTransactionCategory`, `AlertSeverity`, `AlertType`
         enums; value snapshots.

T4.2  — `CashTransaction` frozen Pydantic; naive datetime →
         ValueError; negative amount → ValueError.

T4.3  — `CashTransaction.from_m3` happy path for wire_in /
         wire_out / cash_deposit contribution / cash_withdrawal
         distribution.

T4.4  — `CashTransaction.from_m3` raises `NotACashTransactionError`
         for BUY / SELL / DIVIDEND / INTEREST transactions.

T4.5  — `BsaAmlAlert` frozen; invariants enforced
         (`route_to="compliance_officer"`, `"advisor" in
         do_not_notify`); ValidationError on violation.

T4.6  — `BsaAmlAlert` PII regex on `reason_detail`
         (SSN / email / 12-digit acct / IBAN / clean).

T4.7  — `BsaAmlAlert.reason_code` must be in `ALERT_REASONS`
         frozen set (R2.4).

T4.8  — `BsaAmlAlert.matched_transactions` uniqueness invariant.

T4.9  — `WindowStore` Protocol — `InMemoryWindowStore` satisfies
         it (`isinstance(store, WindowStore)`).

T4.10 — `InMemoryWindowStore.record` keeps list sorted by
         `occurred_at` (property test over shuffled timestamps).

T4.11 — `InMemoryWindowStore.within` boundary semantics (R4.5) —
         start-exclusive, end-inclusive. Parametrized over the
         boundary microsecond.

T4.12 — `InMemoryWindowStore.within` category filter.

T4.13 — `InMemoryWindowStore.purge_before` removes old txns.

T4.14 — `InMemoryWindowStore` thread safety — 100 concurrent
         `record` calls from 10 threads → all recorded, no data
         race (smoke + `threading.Lock()` presence assertion).

T4.15 — `RedisWindowStore` stub — every method raises
         `NotImplementedError`.

T4.16 — `CtrMonitor.evaluate` single-transaction happy path:
         $10,001 cash_deposit → 1 alert with `threshold_type=
         "ctr_single"`.

T4.17 — `CtrMonitor.evaluate` aggregate path: three $4,000 cash
         deposits within 24h → aggregate alert on the third txn.

T4.18 — `CtrMonitor.evaluate` boundary: exactly $10,000 →
         `ctr_single` alert (>= threshold).

T4.19 — `CtrMonitor.evaluate` aggregate boundary: three txns
         summing to exactly $10,000 → NO aggregate alert (> is
         strict). The third one at $1 extra → alert fires.

T4.20 — `SarStructuringMonitor.evaluate` happy path: three $8,000
         deposits in 7 days → 1 structuring alert with
         `severity=critical`.

T4.21 — `SarStructuringMonitor.evaluate` below threshold: three
         $6,999 deposits in 7 days → NO alert (< lower bound).

T4.22 — `SarStructuringMonitor.evaluate` above CTR: three $10,001
         deposits in 7 days → NO structuring alert (CTR rule
         fires separately; structuring is mid-band only).

T4.23 — `SarStructuringMonitor.evaluate` window boundary: two
         $8,000 deposits in 7 days, third at day 7 + 1 second
         → NO alert (sliding window excluded the oldest).

T4.24 — `BsaAmlEngine.evaluate_post_trade` with `config.enabled=
         False` → empty tuple; `InMemoryWindowStore` empty;
         `RecordingAuditLogger` writes == 0 (R6.1, R6.2).

T4.25 — `BsaAmlEngine.evaluate_post_trade` with `config=None` →
         empty tuple; same invariants as T4.24.

T4.26 — `CtrPolicyRule` is `isinstance(_, PolicyRule)` (M2
         Protocol).

T4.27 — `CtrPolicyRule.evaluate` happy path: `PolicyInput` with
         `cash_transaction` triggering CTR → ESCALATE decision
         with correct `rule_applied` and `wsp_section`.

T4.28 — `CtrPolicyRule.evaluate` missing `cash_transaction` in
         context → DENY (`missing_context:cash_transaction`),
         fail-closed per M2 `_require`.

T4.29 — `CtrPolicyRule.evaluate` with `enabled=False` → None
         (abstain).

T4.30 — `SarStructuringPolicyRule.evaluate` happy path + missing
         context + enabled=False variants.

T4.31 — `AuditEmitter.emit` populates every required AuditEntry
         field per R7.2; `rule_applied`, `wsp_section`,
         `reason` match the alert.

T4.32 — `AuditEmitter.emit` anti-tipping-off invariants (R7.3):
         `action == "bsa_aml.alert_emitted"` regardless of alert
         type; `target_type == "cash_transaction"` (not
         `sar_filing`).

T4.33 — `AuditEmitter.emit` when `AuditLogger.write` raises →
         `AlertEmitFailed("audit_write_failed")`. Alert is NOT
         silently dropped.

T4.34 — Rego rule presence: `ctr.rego` and `sar_structuring.rego`
         exist in `opa-bundles/bsa-aml/`. Each contains a `# METADATA`
         block with `wsp_section`. Parsed via Gap 3
         `scan_rego_file`.

T4.35 — WSP section values match Python side: `ctr.rego` carries
         `WSP-BSA-8.2`; `sar_structuring.rego` carries `WSP-BSA-8.1`;
         Python monitors declare the same constants.

T4.36 — AST import scan: Gap 4 source imports only the 6 allowed
         module groups (R0.3). No LLM SDK imports anywhere.

T4.37 — `extra="forbid"` on every Pydantic model
         (CashTransaction, BsaAmlAlert) — one negative param-test
         per model.

T4.38 — Schema version — `BsaAmlAlert.schema_version="2.0.0"` →
         ValidationError.

T4.39 — Integration: full M2 round-trip — register
         `CtrPolicyRule` + `SarStructuringPolicyRule` as extra
         rules alongside an `AuthorityPolicy()` rule table, feed
         a `PolicyInput` with CTR-triggering context → ESCALATE
         decision via the Phase-3 evaluation order semantics
         (oracle test).

T4.40 — Integration: M10 audit emission end-to-end — engine
         produces alert → `AuditEmitter` calls real
         `AuditLogger.write` (3-tier in-memory) → all three
         backends have the entry; `sha256_integrity` verifies.

T4.41 — Integration: archetype-gated disable — BsaAmlConfig with
         `enabled=False` is built from a tier4 (RIA) EnterpriseConfig
         via M5 loader; engine behavior matches T4.24.

---

## 4. TRACEABILITY

| AC    | Task(s)                                       |
|-------|-----------------------------------------------|
| R1.1  | T4.1                                          |
| R1.2  | T4.2, T4.37                                   |
| R1.3  | T4.16, T4.17, T4.18, T4.19                    |
| R1.4  | T4.3, T4.4                                    |
| R2.1  | T4.1                                          |
| R2.2  | T4.1                                          |
| R2.3  | T4.5                                          |
| R2.4  | T4.7                                          |
| R2.5  | T4.5, T4.8                                    |
| R3.1  | T4.16, T4.17, T4.18, T4.19                    |
| R3.2  | T4.20, T4.21, T4.22, T4.23                    |
| R3.3  | T4.16, T4.20                                  |
| R4.1  | T4.9                                          |
| R4.2  | T4.9, T4.10, T4.11, T4.12, T4.13              |
| R4.3  | T4.14                                         |
| R4.4  | T4.15                                         |
| R4.5  | T4.11                                         |
| R5.1  | T4.26                                         |
| R5.2  | T4.27, T4.28, T4.29                           |
| R5.3  | T4.30                                         |
| R5.4  | T4.26                                         |
| R6.1  | T4.24, T4.29, T4.30                           |
| R6.2  | T4.24, T4.25                                  |
| R6.3  | T4.24                                         |
| R7.1  | T4.31                                         |
| R7.2  | T4.31                                         |
| R7.3  | T4.32                                         |
| R7.4  | T4.33                                         |
| R7.5  | T4.31                                         |
| R8.1  | T4.34, T4.35                                  |
| R8.2  | T4.34, T4.35                                  |
| R8.3  | T4.34                                         |
| R8.4  | T4.34                                         |
| R9.1  | T4.6                                          |
| R9.2  | T4.15                                         |
| R9.3  | T4.5                                          |
| R9.4  | T4.6                                          |
| R9.5  | T4.14                                         |

---

## 5. REVIEW FIX TRACEABILITY (v1 — v2)

| Review item | v2 section                                  |
|-------------|---------------------------------------------|
| F1 (Decimal vs float for thresholds) | R1.3                 |
| F2 (anti-tipping-off invariants)     | R7.3 + T4.32         |
| F3 (route_to Literal)                | R2.3 + T4.5          |
| F4 (reason vocabulary frozen)        | R2.4 + T4.7          |
| F5 (matched_transactions uniqueness) | R2.5 + T4.8          |
| F6 (config disable no-op guarantee)  | R6.2 + T4.24, T4.25  |
| F7 (window boundary semantics)       | R4.5 + T4.11, T4.23  |
| F8 (Rego wsp_section annotations)    | R8.1 + T4.34         |
| F9 (fail-closed audit write error)   | R7.4 + T4.33         |
| R1 (wiring diagram)                  | §2.1                 |
| R2 (line budget)                     | §0.5                 |
| R3 (Phase 4 forward-compat)          | §0.1                 |
| R4 (thread safety)                   | R4.3 + T4.14         |
| R5 (M2 PolicyRule Protocol)          | R5 + T4.26           |
| R6 (module boundary AST)             | §2.5 + T4.36         |
| R7 (archetype gate via M5)           | T4.41                |
| R8 (SAR structuring 7-day boundary)  | R3.2 + T4.23         |
