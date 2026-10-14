# M13 FIX Bridge — Spec v2 (post-REVIEW-v1 fixes)

> Module: M13 FIX Bridge
> Phase: 4 (Tier 2/5 institutional)
> Scope: Stateful FIX 4.4 TCP sessions exposed as MCP tools through M6 trust gateway
> Status: v2 — 9 required + 4 recommended fixes from REVIEW-v1 applied
> Steering rule touchpoints: 4, 6, 8, 11, 20, 23, 32, 33

---

## 0. Fix traceability (v1 → v2)

| Review item | Status | Spec section fixed |
|---|---|---|
| Q1 FakeFixEngine ExecReport simulate hook | DONE | 2.3, 2.9 |
| Q2 KillSwitchInput pydantic model | DONE | R10, 2.1 models.py list |
| Q3 AID header + claim + role gate mechanics | DONE | R13 |
| Q4 HMAC-based account hashing w/ Vault salt | DONE | R6.3, D10 |
| Q5 Helm template inventory (10 + _helpers) | DONE | §6 Deployables |
| Q6 session_status error cases | DONE | R2.5 |
| Q7 FIX_ENABLED=false behavior | DONE | R4.1 + R2.* |
| Q8 Concurrency callout (KillSwitch + emitter locks) | DONE | D8 |
| Q9 Test filename rename test_m13_config → test_m13_fix_config | DONE | §3.1 |
| Q10 trader_aid correlation | DONE | R6.1 |
| Q11 VenueConfig pydantic model | DONE | R4.1 |
| Q12 FIX 4.4 vs 4.2 note | DONE | §5 + R3 header |
| Q13 Vault-to-session integration test | DONE | §3.1 |

---

## 1. Requirements

### R1. MCP surface (3-endpoint contract)

- R1.1 `GET /` returns JSON `{name,version,vendor,capabilities,status,checks}`. Status is `ok` (HTTP 200) when at least one configured session is authorized OR `FIX_ENABLED=false` (graceful-disabled mode). Status is `degraded` (HTTP 503) when `FIX_ENABLED=true` AND no session is authorized.
- R1.2 `POST /tools/list` returns the tool catalog with JSON schemas via pydantic v2 `model_json_schema()`.
- R1.3 `POST /tools/call` dispatches to the named tool with validated arguments. Returns MCP envelope `{isError, content, ...}`. HTTP 200 on success + known failure; HTTP 500 on `adapter_internal_error`.

### R2. Tools (6 tools)

- R2.1 `fix.order_new` — NewOrderSingle (MsgType `D`). Inputs per R10 for `NewOrderSingleInput`. Returns `OrderResponse`.
- R2.2 `fix.order_cancel` — OrderCancelRequest (MsgType `F`). Inputs per R10 for `OrderCancelInput`. Returns `OrderResponse`.
- R2.3 `fix.order_cancel_replace` — OrderCancelReplaceRequest (MsgType `G`). Inputs per R10 for `OrderCancelReplaceInput`.
- R2.4 `fix.order_status` — OrderStatusRequest (MsgType `H`). Inputs require exactly one of `{cl_ord_id, order_id}`.
- R2.5 `fix.session_status` — returns session state. Input: `venue`. Error semantics:
  - Unknown venue (not in config) → `session_not_found` via MCP envelope.
  - Known-but-not-connected venue → success with `{logon_status:"DISCONNECTED", seq_num_in:0, seq_num_out:0, last_heartbeat_ts:null, sender_comp_id, target_comp_id}`.
  - `FIX_ENABLED=false` → always returns DISCONNECTED for known venues; `session_not_found` for unknown.
- R2.6 `fix.kill_switch` — admin-only, role `trading_supervisor`. Input per R10 for `KillSwitchInput`. Returns `{scope, venue, state, set_at, actor_aid}`.

### R3. FIX 4.4 MsgType coverage matrix

Module pins FIX protocol version **4.4** (BeginString `FIX.4.4`). ARCH-07 mentions "FIX 4.2" historically; 4.4 is the 2026 industry default for equities order-entry. 4.2 support is a v2 pin-swap (out of scope).

| MsgType | Name | Direction | In scope | Notes |
|---|---|---|---|---|
| A | Logon | Out/In | YES | session layer |
| 5 | Logout | Out/In | YES | session layer, SIGTERM sends |
| 0 | Heartbeat | Out/In | YES | session layer, interval from config |
| 1 | TestRequest | Out/In | YES | after 1.5× heartbeat silence |
| 2 | ResendRequest | Out/In | YES | session layer, gap-fill |
| 4 | SequenceReset | Out/In | YES | gap-fill mode + reset mode |
| 3 | Reject | In | YES | parsed + surfaced as `venue_rejected` |
| D | NewOrderSingle | Out | YES | R2.1 |
| F | OrderCancelRequest | Out | YES | R2.2 |
| G | OrderCancelReplaceRequest | Out | YES | R2.3 |
| H | OrderStatusRequest | Out | YES | R2.4 |
| 8 | ExecutionReport | In | YES | drop-copy to audit |
| 9 | OrderCancelReject | In | YES | drop-copy to audit |
| j | BusinessMessageReject | In | YES | surfaced as canonical error |
| V/W/X/Y | Market Data | — | **NO** | OUT OF SCOPE v1 |
| e | NewOrderList | — | **NO** | OUT OF SCOPE v1 |
| AB | NewOrderMultileg | — | **NO** | OUT OF SCOPE v1 |

### R4. Session lifecycle

- R4.1 `FIX_ENABLED=true`: on startup pull session config YAML from Vault path `FIX_SESSIONS_CONFIG_VAULT_PATH`. Parse into list of `VenueConfig` (pydantic v2, `extra="forbid"`); each entry has:
  - `venue: str` (matches `^[a-z0-9_\-]{1,32}$`)
  - `sender_comp_id_vault_path: str` (Vault path for SenderCompID string; M13 resolves at open time)
  - `target_comp_id_vault_path: str`
  - `host: str` (DNS name or IP)
  - `port: int` (1..65535)
  - `heartbeat_interval_s: int` (>=5, <=120)
  - `reset_on_logon: bool`
  - `use_tls: bool`
  - `cert_path_vault_path: str | None` (mTLS cert PEM path; required when `use_tls=true`)
  - `key_path_vault_path: str | None`
  - `ca_path_vault_path: str | None`
  Invalid config (pydantic failure or required-field missing given use_tls) → refuse-to-start (fail-closed Rule 8). Open one `FixSession` per `(venue, sender, target)`.
  `FIX_ENABLED=false`: no sessions opened. `session_status` returns DISCONNECTED for known venues. Order tools return error `fix_enabled_false`.
- R4.2 Logon(A) with `HeartBtInt = heartbeat_interval_s`, `ResetSeqNumFlag=Y` iff `reset_on_logon=true`; otherwise use persisted `seq_num_out`.
- R4.3 Heartbeat loop: Heartbeat(0) every `heartbeat_interval_s` of outbound silence; TestRequest(1) after 1.5× inbound silence; disconnect after 2.5× unanswered TestRequest.
- R4.4 Inbound `MsgSeqNum > expected`: send ResendRequest(2) BeginSeqNo=expected, EndSeqNo=0.
- R4.5 Inbound `MsgSeqNum < expected`: if `PossDupFlag=Y` ignore; else disconnect (protocol violation) and audit.
- R4.6 SIGTERM: send Logout(5) on every ACTIVE session; wait ≤5s for counterparty; fsync seqnums; exit 0.

### R5. Sequence-number persistence

- R5.1 File-backed JSON at `FIX_SEQNUM_STORE_DIR/<sender_comp_id>.<target_comp_id>.json`.
- R5.2 Write-through + `os.fsync()` on every increment. No batching.
- R5.3 Startup: read `(seq_num_in, seq_num_out)`; missing file → start at 1.
- R5.4 `reset_on_logon=true` → truncate file on startup + Logon `ResetSeqNumFlag=Y`.

### R6. Drop-copy

- R6.1 Every inbound ExecutionReport (MsgType 8) emits `fix.exec_report` audit event with fields:
  `{venue, cl_ord_id, order_id, exec_type, ord_status, last_qty, last_px, cum_qty, avg_px, transact_time, trader_aid, tenant_id, account_hash}`.
  `trader_aid` is the AID of the trader who submitted the parent order (correlated via `cl_ord_id`). If no parent found (inbound ExecReport on unknown cl_ord_id), `trader_aid=null` and a `fix.drop_copy_orphan` warning is emitted.
- R6.2 Inbound OrderCancelReject (MsgType 9) emits `fix.cancel_reject` event.
- R6.3 **No PII, no MNPI (Rule 7).** Account reference is HMAC-SHA256(account, tenant_salt) first 16 hex chars. Tenant salt from Vault path `FIX_ACCOUNT_HASH_SALT_VAULT_PATH`. Tests inject a static salt. Raw account never leaves the pod.
- R6.4 If drop-copy emitter raises, emit synchronous `fix.drop_copy_failed` event (Rule 8 — no silent drop), then continue processing next message.

### R7. Kill switch

- R7.1 Global + per-venue toggles persisted at `FIX_KILL_SWITCH_STATE_PATH` (default `/var/lib/m13/kill_switch.json`). Survives restart. JSON shape:
  `{"global":{"on":bool,"reason":str,"actor_aid":str,"set_at":iso},"venues":{"<venue>":{same}}}`.
- R7.2 Global active → order tools return `kill_switch_active`; Logout(5) sent to all active sessions.
- R7.3 Per-venue active → order tools for that venue return `kill_switch_active`; no Logout.
- R7.4 Inbound ExecReports ALWAYS recorded regardless of kill state (Rule 8).
- R7.5 Toggle via `POST /tools/call name=fix.kill_switch` with input `KillSwitchInput` (see R10). AID role gate: `role == "trading_supervisor"` required (extracted from JWT claims of `X-Agent-AID`, §R13).

### R8. Audit (Rule 6)

Every tool call emits one event to stdout (M10 sidecar forwards). Shape:
```json
{"module":"m13","kind":"fix.tool_audit","ts":"ISO-Z","tool":"fix.order_new",
 "outcome":"success|failure","firm_id":"...","tenant_id":"...","trader_aid":"...",
 "venue":"...","cl_ord_id":"...","seq_num_out":123,"duration_ms":47,
 "error_code":"...optional..."}
```
Session events emit as:
```json
{"module":"m13","kind":"fix.session_event","ts":"...","event":"logon_received",
 "venue":"...","sender_comp_id":"...","target_comp_id":"...",
 "seq_num_in":1,"seq_num_out":1}
```
Kinds: `logon_sent`, `logon_received`, `logout_sent`, `logout_received`, `heartbeat_timeout`, `test_request_sent`, `resend_request_sent`, `seqnum_gap`, `protocol_violation`, `disconnect`, `kill_switch_toggled`, `drop_copy_failed`, `drop_copy_orphan`.

### R9. Security (Rules 20, 22, 23)

- R9.1 Zero credentials in code/tests/Docker/Helm/values. Every secret referenced by Vault path only.
- R9.2 FIX sockets TLS 1.2+ when `use_tls=true`. mTLS cert/key from Vault.
- R9.3 NetworkPolicy: ingress from M6 only on MCP port. Egress to Vault + FIX venue hosts/ports + DNS. Wave-4 allowlist mode supported.
- R9.4 Per-tenant namespace isolation. In-pod per-venue isolation by `(sender,target)` key with session-local state (see D8).

### R10. Pydantic v2 strict models (Rule 32)

All input models: `model_config = ConfigDict(extra="forbid", strict=True)`.

Enums (validated as raw strings matching FIX tag values):
- `FixSide`: `"1"=Buy, "2"=Sell, "5"=SellShort, "6"=SellShortExempt`
- `FixOrdType`: `"1"=Market, "2"=Limit, "3"=Stop, "4"=StopLimit`
- `FixTimeInForce`: `"0"=Day, "1"=GTC, "2"=OPG, "3"=IOC, "4"=FOK, "6"=GTD`
- `FixExecType` (inbound): `"0"=New, "1"=PartialFill, "2"=Fill, "4"=Canceled, "5"=Replace, "8"=Rejected, "C"=Expired`
- `FixOrdStatus` (inbound): `"0"=New, "1"=PartiallyFilled, "2"=Filled, "4"=Canceled, "5"=Replaced, "8"=Rejected, "C"=Expired`

Common field validators:
- `symbol`: `^[A-Z0-9][A-Z0-9.\-/]{0,31}$`
- `cl_ord_id`, `orig_cl_ord_id`, `order_id`: `^[A-Za-z0-9._\-:]{1,64}$`
- `venue`: `^[a-z0-9_\-]{1,32}$`
- `account`: `^[A-Za-z0-9._\-]{1,32}$`
- `order_qty`: `Decimal > 0`, max 20 integer digits, max 8 decimal
- `price`: `Decimal > 0`; REQUIRED when `ord_type=="2"` (Limit) or `"4"` (StopLimit); FORBIDDEN when `ord_type=="1"` (Market); optional for Stop
- `transact_time`: tz-aware UTC datetime

Model inventory:
- `NewOrderSingleInput`: `{cl_ord_id, venue, symbol, side, ord_type, order_qty, price, time_in_force, transact_time, account}`
- `OrderCancelInput`: `{orig_cl_ord_id, cl_ord_id, venue, symbol, side, transact_time}`
- `OrderCancelReplaceInput`: `{orig_cl_ord_id, cl_ord_id, venue, symbol, side, ord_type, order_qty, price, time_in_force, transact_time}`
- `OrderStatusInput`: `{cl_ord_id?, order_id?, venue, symbol, side}` with exactly-one-of cross-field rule
- `SessionStatusInput`: `{venue}`
- `KillSwitchInput`: `{scope: Literal["global","venue"], venue: Optional[str], state: Literal["on","off"], reason: str (min_length=8)}` with `venue` required iff `scope=="venue"` and forbidden when `scope=="global"`
- `OrderResponse` (output): `{cl_ord_id, venue, sender_comp_id, target_comp_id, seq_num_out, accepted_at, bridge_status: Literal["sent","rejected_local"]}`
- `ExecReport` (output/internal): `{venue, cl_ord_id, order_id, exec_type, ord_status, last_qty, last_px, cum_qty, avg_px, transact_time, account_hash}`
- `SessionStatusResponse`: `{venue, logon_status, seq_num_in, seq_num_out, last_heartbeat_ts, sender_comp_id, target_comp_id}`
- `KillSwitchResponse`: `{scope, venue, state, set_at, actor_aid, reason}`
- `VenueConfig`: see R4.1 fields

### R11. Module boundary (Rule 33)

- R11.1 `src/m13_fix_bridge/**` MUST NOT import from `m1_*`, `m2_m4_*`, `m5_*`, `m6_*`, `m7_*`, `m8_*`, `m9_*`, `m10_*`, `m11_*`, `m12_*`, `compliance*`.
- R11.2 Allowed: stdlib, `pydantic`, `typing_extensions`, `fastapi`, `starlette`, `uvicorn` (runtime only), `simplefix` (lazy in `real_engine.py`).
- R11.3 `tests/security/test_m13_boundary.py` AST-scans all imports + credential-shape grep.

### R12. Scope boundaries (OUT OF SCOPE v1)

- Market-data-over-FIX (V/W/X/Y).
- Multi-leg orders.
- Allocation messages.
- Webhook forwarding of ExecReports to tenant EMS.
- Live production smoke tests.
- FIX 4.2 protocol version (4.4 only in v1).

### R13. AID verification (every tool call)

- R13.1 Every MCP call through `/tools/call` MUST carry `X-Agent-AID: <jwt>` header. Missing → MCP envelope `{isError:true, errorCode:"unauthorized"}` HTTP 200.
- R13.2 JWT claim shape: `{sub: str, aid: str, role: str, tenant_id: str, firm_id: str, iat: int, exp: int}`. Decode failure or expired token → `unauthorized`.
- R13.3 `tenant_id` and `firm_id` extracted from verified claims are authoritative for audit — any client-supplied `X-Firm-ID` header is ignored.
- R13.4 Role gate: only `fix.kill_switch` requires `role == "trading_supervisor"`. Other tools accept any valid AID.
- R13.5 Verification modes (offline):
  - **HMAC mode (tests & dev)**: HS256 with shared secret from Vault `FIX_AID_VERIFY_SHARED_SECRET_VAULT_PATH`.
  - **RSA mode (prod)**: RS256 with public key PEM from `FIX_AID_VERIFY_PUBLIC_KEY_PATH`.
- R13.6 `StaticAidVerifier(claim_map)` in `aid_verify.py` is used by tests: `{token_string: claims_dict}`.

---

## 2. Design

### 2.1 Directory layout

```
src/m13_fix_bridge/
  __init__.py
  __main__.py                # python -m m13_fix_bridge
  app.py                     # FastAPI factory
  models.py                  # pydantic v2 models (R10)
  config.py                  # env-var settings (BaseSettings-like)
  audit.py                   # stdout JSON emitter (module="m13")
  drop_copy.py               # ExecReport/CancelReject → audit w/ account hash
  aid_verify.py              # JWT + Static verifier (R13)
  startup.py                 # Vault → sessions; SIGTERM wiring
  dispatcher.py              # tool dispatch + kill-switch + role gate + audit
  health.py                  # health-check for GET /
  client/
    __init__.py
    protocol.py              # FixEngineProtocol (abstract)
    fake_engine.py           # FakeFixEngine (in-memory, deterministic)
    real_engine.py           # RealFixEngine (simplefix lazy)
    session.py               # FixSession state + FileSeqnumStore
    session_manager.py       # multi-session coordinator
    kill_switch.py           # KillSwitch file-backed
```

### 2.2 app.create_app signature

```python
def create_app(
    *,
    engine: FixEngineProtocol | None = None,
    audit: StdoutAuditEmitter | None = None,
    config: FixConfig | None = None,
    verify_aid: AidVerifier | None = None,
) -> FastAPI
```
Defaults: `FakeFixEngine()`, `StdoutAuditEmitter()`, `FixConfig.from_env()`, `StaticAidVerifier.empty()`.

### 2.3 FixEngineProtocol (§R + tests)

```python
class FixEngineProtocol(Protocol):
    async def open(self, venue_configs: Sequence[VenueConfig]) -> None: ...
    async def close(self) -> None: ...
    async def send_order_new(self, venue: str, msg: dict) -> OrderResponse: ...
    async def send_order_cancel(self, venue: str, msg: dict) -> OrderResponse: ...
    async def send_order_cancel_replace(self, venue: str, msg: dict) -> OrderResponse: ...
    async def send_order_status(self, venue: str, msg: dict) -> OrderResponse: ...
    def session_state(self, venue: str) -> SessionStatusResponse: ...
    def venues(self) -> list[str]: ...
    # Test hook for drop-copy path (FakeFixEngine only; RealFixEngine raises)
    async def simulate_inbound_exec_report(self, venue: str, report: dict) -> None: ...
    async def simulate_inbound_cancel_reject(self, venue: str, reject: dict) -> None: ...
    def set_inbound_callback(self, callback: Callable[[str, dict], Awaitable[None]]) -> None: ...
```

`FakeFixEngine` keeps per-venue seqnums in memory, pre-populated from `VenueConfig`, and invokes the inbound callback when `simulate_inbound_*` is called. Deterministic: seqnum 1 on first Logon, increments by 1.

`RealFixEngine` stub: lazy-imports `simplefix` on first `.open()`. Message-building helpers use `simplefix.FixMessage`. The asyncio socket-pair reader loop is wired via `asyncio.open_connection`. Calling `.open()` while live raises `NotImplementedError` in this v1 build (production live-session integration is out of scope per R12).

### 2.4 State machine (FixSession)

```
DISCONNECTED --open()--> LOGON_SENT
LOGON_SENT --Logon(A) in--> ACTIVE
ACTIVE --SIGTERM|kill_global--> LOGOUT_SENT
LOGOUT_SENT --Logout in | 5s timeout--> DISCONNECTED
ACTIVE --heartbeat_timeout--> DISCONNECTED
ACTIVE --protocol_violation--> DISCONNECTED
```

Invariants:
- `seq_num_out` strictly increases per outbound.
- `seq_num_in` strictly increases per accepted inbound (skip `PossDupFlag=Y`).
- Kill switch active ⇒ no new outbound business (session layer still allowed for clean shutdown).

### 2.5 FileSeqnumStore

- `load(sender, target) -> (seq_in, seq_out)` — reads JSON; missing → (1, 1).
- `bump_out(sender, target) -> new_seq_out` — increments atomically, fsyncs.
- `bump_in(sender, target, new_seq_in) -> None` — writes + fsync.
- `reset(sender, target)` — truncate to (1, 1) + fsync.

JSON: `{"seq_num_in":N,"seq_num_out":M,"updated_at":"..."}`.

### 2.6 KillSwitch

```python
class KillSwitch:
    def is_blocked(self, venue: str) -> bool  # True if global or per-venue on
    def set_global(self, on: bool, *, reason: str, actor_aid: str) -> None
    def set_venue(self, venue: str, on: bool, *, reason: str, actor_aid: str) -> None
    def snapshot(self) -> dict
```
State JSON written atomically via `os.replace(tmp, final)`. Single `threading.Lock` covers all writes.

### 2.7 AID verify

- `HmacAidVerifier(secret: bytes, algorithm: str = "HS256")` — verifies + returns claims dict.
- `RsaAidVerifier(public_key_pem: str)` — RS256.
- `StaticAidVerifier({token_str: claims_dict})` — tests.
All expose `.verify(token: str) -> AidClaims`. `AidClaims` is a pydantic model with all fields from R13.2; `exp` checked against `now_utc`.

### 2.8 Dispatcher

```python
class Dispatcher:
    def __init__(self, *, engine, kill_switch, audit, verify_aid, config, drop_copy): ...
    async def call(self, *, tool: str, arguments: dict, aid_token: str) -> dict: ...
```
Flow per call:
1. Verify AID via `verify_aid.verify(aid_token)` → `claims` or `unauthorized`.
2. Resolve tool handler or `unknown_tool`.
3. Validate arguments via pydantic → `invalid_arguments` on `ValidationError`.
4. If tool is `fix.kill_switch`: check `claims.role == "trading_supervisor"` → `unauthorized` if not.
5. If tool is order_* and kill switch blocks: return `kill_switch_active`.
6. If `FIX_ENABLED=false` and tool is order_*: return `fix_enabled_false`.
7. Invoke handler. Catch `AdapterError` → canonical envelope. Catch bug → `adapter_internal_error`.
8. Emit audit event with extracted `tenant_id`, `firm_id`, `trader_aid`, `venue`, `cl_ord_id`, `seq_num_out`, outcome, error_code, duration_ms.

### 2.9 Drop-copy path (test hook)

FakeFixEngine calls `engine.simulate_inbound_exec_report(venue, report_dict)` in tests. This invokes the callback set by `session_manager.on_inbound_exec_report`, which calls `drop_copy.emit(venue, report_dict, trader_aid_map)`. `trader_aid_map[cl_ord_id]` is populated by the dispatcher on each outbound order (keyed by cl_ord_id, TTL 24h by LRU eviction capped at 10k entries).

### D8. Concurrency callout

Shared mutable state in the pod:
1. `KillSwitch` — guarded by a single `threading.Lock` around JSON state writes. Atomic via `os.replace`.
2. `StdoutAuditEmitter` — guarded by a single `threading.Lock` around `sys.stdout.write + flush` (same pattern as `m11_python_adapters_shared/audit_emitter.py`).
3. `trader_aid_map` LRU — `threading.Lock` (get/set).
4. `FakeFixEngine` per-venue seqnum dict — `asyncio.Lock` per venue.

Each `FixSession` is otherwise async-task-private. Cross-venue interference prevented by: (a) separate seqnum files, (b) async task per session, (c) no shared mutable state except §1-4 above.

### D9. m11_python_adapters_shared reuse: REJECTED

Rule 33 says no cross-module imports. `m11_python_adapters_shared` is M11 family infra (per its own `__init__.py` docstring). M13 is a separate family per Rule 11. We copy the ~80 lines of overlap (`AuditEvent` shape, `AdapterError`, stdout-lock pattern, FakeVault) into `m13_fix_bridge/` — documented in `DECISION-LOG.md`. The benefit: strict module boundary, compiled in the AST-scan test. The cost: minor duplication, considered acceptable.

### D10. Account hashing (tenant-salted HMAC-SHA256)

- Hash = `hmac.new(salt, account.encode(), hashlib.sha256).hexdigest()[:16]`.
- Salt from Vault at startup. 32+ bytes. Tests inject static salt.
- This value is called `account_hash` in all drop-copy events.
- Raw account never written to audit or logs.

---

## 3. Tasks

Ordered, atomic. TDD per Steering Rule 31.

- [x] T1 Spec v1 + LLMJ Review v1 + Fix to v2 (this document).
- [ ] T2 Source skeleton: `__init__.py`, `__main__.py`, `config.py`, `audit.py`. Tests: `tests/unit/test_m13_fix_config.py` (≥ 7 cases).
- [ ] T3 `models.py` — all pydantic models. Tests: `tests/unit/test_m13_fix_models.py` (≥ 25 cases).
- [ ] T4 `client/protocol.py` + `client/session.py` (FixSession + FileSeqnumStore) + `client/fake_engine.py`. Tests subset of T5.
- [ ] T5 `client/session_manager.py` + heartbeat/timeouts/seqnum-gap handling. Tests: `tests/unit/test_m13_fix_session.py` (≥ 20 cases).
- [ ] T6 `client/kill_switch.py`. Tests: `tests/unit/test_m13_kill_switch.py` (≥ 8 cases).
- [ ] T7 `aid_verify.py` + claims model. Tests covered in dispatcher + integration.
- [ ] T8 `dispatcher.py` + `health.py`. Tests: `tests/unit/test_m13_fix_client.py` (≥ 20 cases).
- [ ] T9 `drop_copy.py` with account hashing. Tests: `tests/unit/test_m13_drop_copy.py` (≥ 10 cases).
- [ ] T10 `app.py` + `startup.py`. Tests: `tests/integration/test_m13_integration.py` (≥ 8 cases).
- [ ] T11 `client/real_engine.py` stub (simplefix lazy import + NotImplementedError path).
- [ ] T12 `tests/security/test_m13_boundary.py` AST scan + credential grep.
- [ ] T13 Dockerfile `deploy/docker/m13-fix-bridge/Dockerfile`.
- [ ] T14 Extend `deploy/tests/test_dockerfile_security.sh` list.
- [ ] T15 Helm sub-chart `deploy/helm/007-fsi/charts/m13-fix-bridge/` — 11 files (see §6).
- [ ] T16 Umbrella wiring — Chart.yaml dep entry (conditional), values-cloud + values-hybrid entries, regenerate Chart.lock + .tgz.
- [ ] T17 LLMJ Review v2 (require ≥ 8.0 GO).
- [ ] T18 10× stable pytest runs on bundle + full suite regression check (≥ 2081 passed).
- [ ] T19 COMPLETE marker at `.kiro/specs/m13-fix-bridge-COMPLETE.md`.

### 3.1 Test count budget (target ≥ 80)

| File | Min | Target |
|---|---|---|
| test_m13_fix_config.py | 7 | 8 |
| test_m13_fix_models.py | 25 | 28 |
| test_m13_fix_session.py | 20 | 22 |
| test_m13_fix_client.py | 20 | 22 |
| test_m13_drop_copy.py | 10 | 11 |
| test_m13_kill_switch.py | 8 | 10 |
| test_m13_boundary.py | 4 | 4 |
| test_m13_integration.py | 8 | 10 |
| **Total (M13 only)** | **102** | **115** |

Above the 80-test floor. All bundle tests run via:

```
pytest \
  tests/unit/test_m13_fix_config.py \
  tests/unit/test_m13_fix_models.py \
  tests/unit/test_m13_fix_session.py \
  tests/unit/test_m13_fix_client.py \
  tests/unit/test_m13_drop_copy.py \
  tests/unit/test_m13_kill_switch.py \
  tests/integration/test_m13_integration.py \
  tests/security/test_m13_boundary.py \
  -q
```

---

## 4. Acceptance criteria traceability

| Req | Test file | Brief |
|---|---|---|
| R1.1 | test_m13_integration.py | GET / healthy + disabled-mode ok + degraded 503 |
| R1.2 | test_m13_integration.py | POST /tools/list returns 6 tools with schemas |
| R1.3 | test_m13_integration.py, test_m13_fix_client.py | MCP envelope shapes |
| R2.1-R2.6 | test_m13_fix_client.py | Tool dispatch + success + validation |
| R3 | test_m13_fix_session.py | Session-layer MsgTypes behavior |
| R4 | test_m13_fix_session.py | State machine + SIGTERM + heartbeat |
| R4.1 | test_m13_integration.py | Vault YAML → sessions |
| R5 | test_m13_fix_session.py | FileSeqnumStore |
| R6 | test_m13_drop_copy.py | ExecReport + CancelReject + account hashing + PII absence + orphan |
| R7 | test_m13_kill_switch.py | Toggle + persistence + block + role gate |
| R8 | all unit + integration | Audit events shape |
| R9 | test_m13_boundary.py + test_dockerfile_security.sh | No creds + netpolicy via helm |
| R10 | test_m13_fix_models.py | Every enum + cross-field + extra=forbid |
| R11 | test_m13_boundary.py | AST scan imports |
| R13 | test_m13_fix_client.py + test_m13_integration.py | Header + role + claims |

---

## 5. Non-goals (for reviewer clarity)

- No market-data-over-FIX.
- No live FIX sockets in CI or tests.
- No direct M10 import. Drop-copy → stdout.
- No multi-replica StatefulSet (`replicas:1` hard-coded per Rule 11).
- No shared-infra import from `m11_python_adapters_shared` (D9).
- No production smoke gate in CI.
- No FIX 4.2 support in v1 (4.4 only).
- No multi-leg or allocation messages.

---

## 6. Deployables

### 6.1 Dockerfile at `deploy/docker/m13-fix-bridge/Dockerfile`

- `python:3.12-slim` base, multi-stage.
- Builder installs: `fastapi`, `uvicorn[standard]`, `pydantic`, `structlog`, `typing-extensions`, `simplefix`, `pyjwt[crypto]`.
- Runtime copies site-packages + `uvicorn` entry.
- `USER 1000:1000`, HEALTHCHECK against `GET /`.
- OCI title label `007-fsi/m13-fix-bridge`.
- `VOLUME /var/lib/m13` declared.
- No `ADD from URL`. No unpinned `apt-get upgrade`. No literal creds.
- Must pass `deploy/tests/test_dockerfile_security.sh` after T14 extends its list.

### 6.2 Helm sub-chart at `deploy/helm/007-fsi/charts/m13-fix-bridge/` — **11 files**

1. `Chart.yaml` (version 0.1.0, appVersion 0.1.0)
2. `values.yaml` (`enabled: false` default, `replicaCount: 1` hardcoded, PVC 10Gi, mTLS config)
3. `templates/_helpers.tpl` (007.fullname / 007.labels / 007.image / 007.serviceAccountName)
4. `templates/statefulset.yaml` (`replicas:1`, `serviceName: m13-fix-bridge-headless`, volumeClaimTemplates for `/var/lib/m13`)
5. `templates/service.yaml` (ClusterIP for MCP HTTP 8443→8080)
6. `templates/service-headless.yaml` (clusterIP: None for stable pod DNS)
7. `templates/serviceaccount.yaml`
8. `templates/networkpolicy.yaml` (ingress from M6, egress: Vault + DNS + per-venue allowlist; Wave-4 egressMode:allowlist supported)
9. `templates/pdb.yaml` (`maxUnavailable: 0` — single stateful replica)
10. `templates/certificate.yaml` (cert-manager, duration 24h, renewBefore 2h)
11. `templates/externalsecret.yaml` (session config YAML + mTLS certs + HMAC salt + AID secret)
12. `templates/configmap.yaml` (non-secret tunables: LOG_LEVEL, ADAPTER_NAME, VENDOR)

(11 files in `templates/` + Chart.yaml + values.yaml + _helpers.tpl = Helm structural count of 12. Task spec says "9-11"; we deliver 12 because configmap + externalsecret are standard patterns across the other charts and splitting service+headless service is required for StatefulSet DNS.)

### 6.3 Umbrella Chart.yaml changes

Add dep under `# ---- Phase 4 institutional adapters ----`:
```yaml
- name: m13-fix-bridge
  version: 0.1.0
  repository: "file://charts/m13-fix-bridge"
  condition: m13-fix-bridge.enabled
```

### 6.4 values-cloud.yaml and values-hybrid.yaml entries

`values-cloud.yaml`:
```yaml
m13-fix-bridge:
  enabled: false
  egressAllowlist: []  # operator-supplied FIX venue CIDRs
```

`values-hybrid.yaml`:
```yaml
m13-fix-bridge:
  # M13 runs on-prem in hybrid mode; cloud partition disables it.
  enabled: false
```

### 6.5 Chart.lock + tgz regeneration

Run `helm dep update deploy/helm/007-fsi` after editing Chart.yaml. Regenerate `.tgz` for `m13-fix-bridge` + update `Chart.lock`.

---

## 7. Environment variables (config.py)

| Var | Default | Description |
|---|---|---|
| FIX_ENABLED | "false" | Gate live sessions. Tests set false. |
| FIX_SESSIONS_CONFIG_VAULT_PATH | "" | Required when enabled=true. YAML list. |
| FIX_SEQNUM_STORE_DIR | "/var/lib/m13/seqnums" | Seqnum JSON dir. |
| FIX_DROP_COPY_ENABLED | "true" | Toggle ExecReport→audit |
| FIX_KILL_SWITCH_STATE_PATH | "/var/lib/m13/kill_switch.json" | Kill switch JSON |
| FIX_ACCOUNT_HASH_SALT_VAULT_PATH | "" | HMAC salt path (required when enabled=true) |
| FIX_AID_VERIFY_MODE | "static" | static / hmac / rsa |
| FIX_AID_VERIFY_SHARED_SECRET_VAULT_PATH | "" | For hmac mode |
| FIX_AID_VERIFY_PUBLIC_KEY_PATH | "" | For rsa mode |
| FIX_SECRETS_BACKEND | "vault" | vault / fake (test) |
| HTTP_PORT | "8080" | uvicorn port |
| LOG_LEVEL | "info" | |

*End spec v2.*
