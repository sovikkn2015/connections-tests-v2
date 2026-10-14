# M13 FIX Bridge — COMPLETE

> Module: M13 FIX Bridge (Stateful FIX 4.4 TCP sessions as MCP tools)
> Phase: 4 (Tier 2/5 institutional)
> Status: COMPLETE
> Build date: 2026 build cycle

---

## 1. Gate evidence

| Gate | Target | Delivered |
|---|---|---|
| Self-LLMJ Review v2 | ≥ 8.0 GO | **8.575 / 10 GO** |
| M13 bundle tests | ≥ 80 passing | **126 passing** |
| 10× consecutive stable runs | 10/10 | **10/10 stable (126 passed each run, 0.69-1.19s)** |
| Full suite regression | ≥ 2081 passed, 0 regressions | **2127 passed, 0 regressions** (baseline 2001 → 2127 = +126) |
| Dockerfile security test | PASS | PASS (extended to include m13) |
| Helm lint | PASS | PASS |
| Helm template tests | PASS | PASS (all existing tests still green + M13 renders) |
| Helm egress allowlist test | PASS | PASS (M13 honors Wave-4 `egressMode=allowlist`) |

---

## 2. Deliverables

### 2.1 Spec + review artifacts

| File | Purpose |
|---|---|
| `.kiro/specs/m13-fix-bridge.md` | Spec v2 (post-v1-review fixes). Requirements + Design + Tasks + MsgType matrix. |
| `.kiro/specs/m13-fix-bridge-REVIEW.md` | Self-LLMJ v1: 6.95/10, 9 required + 4 recommended fixes identified. |
| `.kiro/specs/m13-fix-bridge-REVIEW-v2.md` | Self-LLMJ v2: 8.575/10 GO. All v1 fixes verified. |
| `.kiro/specs/m13-fix-bridge-COMPLETE.md` | This file. |

### 2.2 Source module

`src/m13_fix_bridge/` — 14 Python files, ~2,300 lines:

| File | Purpose |
|---|---|
| `__init__.py` | Public API exports |
| `__main__.py` | `python -m m13_fix_bridge` uvicorn entry |
| `app.py` | FastAPI factory with 3 endpoints (`/`, `/tools/list`, `/tools/call`) |
| `config.py` | Env-var settings (FixConfig + load_config) |
| `models.py` | Pydantic v2 strict models for 6 tools + VenueConfig + responses |
| `audit.py` | Stdout JSON audit emitter (module="m13", newline-atomic) |
| `drop_copy.py` | ExecReport/CancelReject canonicaliser with HMAC-salted account hash |
| `aid_verify.py` | AidVerifier protocol + StaticAidVerifier + HmacAidVerifier (HS256) |
| `dispatcher.py` | Tool dispatch + AID verify + role gate + kill-switch gate + audit |
| `health.py` | Health-check for `GET /` |
| `startup.py` | Vault-backed session config + SIGTERM handler |
| `client/protocol.py` | `FixEngineProtocol` (abstract) |
| `client/fake_engine.py` | `FakeFixEngine` (deterministic, in-memory, used in all tests) |
| `client/real_engine.py` | `RealFixEngine` stub (lazy `simplefix` import; `NotImplementedError` in v1) |
| `client/session.py` | `FixSession` + `FileSeqnumStore` (fsync on every bump, atomic replace) |
| `client/session_manager.py` | Multi-venue coordinator + inbound-callback bridge |
| `client/kill_switch.py` | Global + per-venue toggle, file-backed, survives restart |

### 2.3 Dockerfile

`deploy/docker/m13-fix-bridge/Dockerfile` — python:3.12-slim multi-stage:
- `USER 1000:1000` non-root
- `VOLUME /var/lib/m13` for seqnum + kill-switch state
- `HEALTHCHECK` against `GET /`
- OCI title label present
- No ADD-from-URL, no unpinned apt-get upgrade
- Pinned deps: `fastapi`, `uvicorn`, `pydantic 2.x`, `pyyaml 6.x`, `structlog 24.x`, `simplefix 1.0.17+`, `pyjwt[crypto] 2.8+`

### 2.4 Dockerfile security test extension

`deploy/tests/test_dockerfile_security.sh` extended to include `deploy/docker/m13-fix-bridge/Dockerfile`. Result: PASS.

### 2.5 Helm sub-chart

`deploy/helm/007-fsi/charts/m13-fix-bridge/` — **12 files**:

| File | Notes |
|---|---|
| `Chart.yaml` | version 0.1.0, appVersion 0.1.0 |
| `values.yaml` | `enabled: false`, `replicaCount: 1` HARD-CODED per Rule 11, PVC 10Gi |
| `templates/_helpers.tpl` | 007.fullname, labels, selectorLabels, headlessServiceName |
| `templates/statefulset.yaml` | `replicas:1`, `serviceName: {...}-headless`, `volumeClaimTemplates` for /var/lib/m13 |
| `templates/service.yaml` | ClusterIP (8443 → 8080) |
| `templates/service-headless.yaml` | `clusterIP: None` for stable pod DNS |
| `templates/serviceaccount.yaml` | IRSA/Workload-Identity annotations |
| `templates/networkpolicy.yaml` | Ingress from M6 only; Wave-4 `egressMode: allowlist` supported |
| `templates/pdb.yaml` | `maxUnavailable: 0` — single stateful replica |
| `templates/certificate.yaml` | cert-manager 24h duration, 2h renewBefore, CN + DNS names for headless |
| `templates/externalsecret.yaml` | Sessions YAML + hash salt + AID HMAC secret from Vault |
| `templates/configmap.yaml` | LOG_LEVEL, ADAPTER_NAME, VENDOR |

### 2.6 Umbrella wiring

- `deploy/helm/007-fsi/Chart.yaml`: added `m13-fix-bridge` dependency under Phase-4 section with `condition: m13-fix-bridge.enabled`.
- `deploy/helm/007-fsi/values-cloud.yaml`: added `m13-fix-bridge: { enabled: false }` + egress allowlist stub.
- `deploy/helm/007-fsi/values-hybrid.yaml`: added `m13-fix-bridge: { enabled: false }` (M13 runs on-prem in hybrid).
- `deploy/helm/007-fsi/Chart.lock` regenerated.
- `deploy/helm/007-fsi/charts/m13-fix-bridge-0.1.0.tgz` generated via `helm dep update`.

### 2.7 Tests

| File | Count | Min | Purpose |
|---|---|---|---|
| `tests/unit/test_m13_fix_config.py` | 8 | 7 | Env-var parsing + fail-closed |
| `tests/unit/test_m13_fix_models.py` | 33 | 25 | Pydantic validation — enums, cross-field, extra=forbid |
| `tests/unit/test_m13_fix_session.py` | 25 | 20 | FixSession + FileSeqnumStore (fsync, atomic, reset) + SessionManager |
| `tests/unit/test_m13_fix_client.py` | 22 | 20 | Dispatcher — tool dispatch, AID gate, kill-switch gate, audit, AdapterError |
| `tests/unit/test_m13_drop_copy.py` | 12 | 10 | ExecReport/CancelReject + HMAC account hashing + LRU + orphan |
| `tests/unit/test_m13_kill_switch.py` | 10 | 8 | Global + per-venue toggle + persistence + corrupt recovery |
| `tests/security/test_m13_boundary.py` | 4 | 4 | AST scan (Rule 33) + credential-shape grep |
| `tests/integration/test_m13_integration.py` | 12 | 8 | FastAPI TestClient end-to-end: health, tools/list, tools/call, kill-switch, drop-copy |
| **TOTAL M13** | **126** | 80 | |

---

## 3. Critical design decisions (implemented)

| # | Decision | Defense |
|---|---|---|
| D1 | StatefulSet + PVC, `replicas:1` hard-coded | Rule 11 — FIX sessions own sequence numbers. Two pods would race counterparty. Operators get per-venue pod split via separate releases (future overlay). |
| D2 | Seqnum file JSON w/ `os.fsync` + atomic `os.replace` | Tier 2 message rate (O(10-100 msg/s)) makes fsync-per-bump acceptable. Preserves counterparty-resume correctness on pod restart. |
| D3 | Drop-copy via stdout audit (no M10 import) | Rule 33 — M13 mirrors the M11 pattern. M10 sidecar tails and forwards. Boundary mechanically enforced by AST scan test. |
| D4 | Kill-switch file-backed, survives restart, role-gated by dispatcher | Rule 8 fail-closed — toggle requires role=trading_supervisor AID. Inbound ExecReports always recorded regardless of kill state. |
| D5 | FIX 4.4 only in v1 | ARCH-07 mentioned 4.2 historically; 4.4 is the 2026 equities default and the simplefix-native version. 4.2 is a v2 pin-swap. |
| D6 | ExecReport inbound only — no outbound webhook | v2 work. Keeps v1 scope tight. |
| D7 | All tests use `FakeFixEngine` | No live FIX in CI. Deterministic state transitions. `RealFixEngine.open()` raises `NotImplementedError` in v1 (production live integration is ops-hardening v2). |
| D8 | Per-venue isolation inside one pod | `SessionManager` keys by `(sender, target)`. Shared mutables: KillSwitch (threading.Lock), stdout audit (threading.Lock), trader-aid correlator (threading.Lock), per-venue seqnum files (async.Lock per venue). Documented in D8 of spec §2. |
| D9 | NO reuse of `m11_python_adapters_shared` | Rule 33 — M11 family infra is M11-scoped. M13 is separate family per Rule 11. ~80 lines of intentional duplication. AST scan enforces. |
| D10 | Tenant-salted HMAC-SHA256 account hash | Prevents rainbow-table reversal of the `account_hash` field in drop-copy audit. Salt from Vault (per-tenant). |

---

## 4. Steering rule compliance matrix

| Rule | M13 Implementation |
|---|---|
| 4 (M6 is single entry) | NetworkPolicy ingress only from `app.kubernetes.io/name=m6-mcp-gateway` |
| 6 (3-tier WORM audit) | Every tool call + every session event + every drop-copy emits stdout JSON; M10 sidecar forwards |
| 7 (No PII / MNPI to LLM) | Drop-copy replaces account with HMAC hash. No raw account leaves pod. |
| 8 (Fail-closed) | Invalid VenueConfig at startup → refuse-to-start. Drop-copy failure → synchronous `drop_copy_failed` event, never silent. Kill-switch inbound ExecReports still flow. |
| 11 (M13 separate, stateful) | StatefulSet + PVC + `replicas:1` + `maxUnavailable:0` |
| 20 (Zero credentials) | All secrets are Vault paths in env vars; ExternalSecret pulls them. Boundary test greps for literal credential patterns. |
| 22 (Egress narrowing) | NetworkPolicy supports Wave-4 `egressMode=allowlist` with per-venue host entries. |
| 23 (Per-tenant namespace) | NetworkPolicy + ServiceAccount + per-tenant Vault path pattern (`secret/data/007/m13-fix-bridge/...`) |
| 32 (pydantic v2 strict) | Every input model: `ConfigDict(extra="forbid", strict=True)` + 33 validation tests |
| 33 (No cross-module imports) | AST-scan test `test_m13_boundary.py` enforces. Confirms no imports of M1/M2/M4/M5/M6/M7/M8/M9/M10/M11/M12, including `m11_python_adapters_shared`. |

---

## 5. Known non-goals (documented in spec §5)

- Market-data-over-FIX (V/W/X/Y) — v2 separate module.
- Multi-leg orders (NewOrderList, MultilegOrderCancelReplace).
- Allocation messages (AllocationInstruction, AllocationReport).
- Outbound webhook forwarding of ExecReports to tenant EMS — v2.
- Live FIX socket (RealFixEngine.open) — v1 stub raises `NotImplementedError`; production wiring is ops-hardening v2 work.
- FIX 4.2 protocol version support — v1 pins 4.4.

---

## 6. Verification commands

```
# 1. M13 bundle
PYTHONPATH=src python3 -m pytest \
  tests/unit/test_m13_fix_config.py \
  tests/unit/test_m13_fix_models.py \
  tests/unit/test_m13_fix_session.py \
  tests/unit/test_m13_fix_client.py \
  tests/unit/test_m13_drop_copy.py \
  tests/unit/test_m13_kill_switch.py \
  tests/integration/test_m13_integration.py \
  tests/security/test_m13_boundary.py -q
# → 126 passed

# 2. Full suite
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
# → 2127 passed, 15 skipped, 5 xfailed, 1 xpassed

# 3. Deploy gates
bash deploy/tests/test_dockerfile_security.sh     # PASS
bash deploy/tests/test_helm_lint.sh               # PASS
bash deploy/tests/test_helm_template.sh           # PASS
bash deploy/tests/test_helm_template_hybrid.sh    # PASS
bash deploy/tests/test_helm_template_egress.sh    # PASS
bash deploy/tests/test_argocd_applicationset.sh   # PASS

# 4. Regenerate chart dependencies (after Chart.yaml changes)
helm dep update deploy/helm/007-fsi
# → charts/m13-fix-bridge-0.1.0.tgz + Chart.lock updated
```

---

## 7. Summary

M13 FIX Bridge delivered through the 7-step playbook:

1. Spec v1 written with Requirements + Design + Tasks + MsgType matrix.
2. Self-LLMJ Review v1: 6.95/10 CONDITIONAL GO, 9 required + 4 recommended fixes.
3. Spec v2 with all 13 fixes applied and cross-referenced in §0.
4. Self-LLMJ Review v2: **8.575/10 GO**.
5. Source + tests + Dockerfile + Helm sub-chart (12 files) + umbrella wiring built.
6. 10/10 stable M13 bundle runs (126 passed each). Full suite 2127 passed (≥ 2081 target, 0 regressions from 2001 baseline). All deploy tests green.
7. COMPLETE marker emitted here.

*M13 FIX Bridge is COMPLETE.*
