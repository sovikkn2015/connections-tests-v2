# Ops Hardening Wave 2 — Intelligence Layer — COMPLETE

**Wave**: Ops Hardening Wave 2 (intelligence layer)
**Modules covered**: M7 (documented as library, no deployment), M8 Pipeline Engine, M9 Intent Router, M12 Supervisor
**Phase**: Phase 2 (Intelligence Layer — RIA lighthouse) + ops hardening for customer GA
**Date**: 2026-05-02
**Playbook**: 7 steps complete
**Coordination**: Wave 1 (gateway-agent) landed umbrella Chart.yaml + values-cloud.yaml + Wave 1 sub-charts (M1 visible, M2/M4/M6/M10 arriving). Wave 2 contributes three intelligence-layer sub-charts and a values fragment.

---

## Scorecard

| Step | Status | Result |
|------|--------|--------|
| 1. Spec v0.1.0 | done | 1 file, ~350 lines |
| 2. LLMJ Review v1 | done | **7.30/10 CONDITIONAL GO** — 16 required fixes + 5 recommended |
| 3. Fix | done | v0.2.0 full rewrite, all 16 RF addressed + 2 RecF adopted |
| 4. LLMJ Review v2 | done | **8.69/10 GO** (+1.39 delta) |
| 5. Build | done | 3 Dockerfiles + 3 FastAPI shims + 3 Helm sub-charts + values fragment + 2 test scripts |
| 6. Verify | done | Python 1757/1757 green (10/10 stable), shell gates 10/10 stable |
| 7. Complete | done | This marker |

---

## Delivered Artifacts

### Specs (.kiro/specs/)

| File | Purpose |
|---|---|
| `ops-hardening-wave2-intelligence-layer.md` | v0.2.0 GO spec |
| `ops-hardening-wave2-REVIEW.md` | v1 LLMJ review (7.30/10 CONDITIONAL GO) |
| `ops-hardening-wave2-REVIEW-v2.md` | v2 LLMJ review (8.69/10 GO) |
| `ops-hardening-wave2-COMPLETE.md` | This marker |

### Dockerfiles (deploy/docker/)

| File | Base | Entrypoint |
|---|---|---|
| `m8-pipeline-engine/Dockerfile` | python:3.12-slim | `uvicorn service.main:app --host 0.0.0.0 --port 8443 --workers 2` |
| `m8-pipeline-engine/app/main.py` | — | FastAPI shim: GET /health, GET /ready, POST /pipelines |
| `m9-intent-router/Dockerfile` | python:3.12-slim | `uvicorn service.main:app --host 0.0.0.0 --port 8443 --workers 4` |
| `m9-intent-router/app/main.py` | — | FastAPI shim: GET /health, GET /ready, POST /route |
| `m12-supervisor/Dockerfile` | python:3.12-slim | `uvicorn service.main:app --host 0.0.0.0 --port 8443 --workers 2` |
| `m12-supervisor/app/main.py` | — | FastAPI shim: GET /health, GET /ready, POST /dispatch |

### Helm sub-charts (deploy/helm/007-fsi/charts/)

Per sub-chart: Chart.yaml + values.yaml + templates/.

**M8 Pipeline Engine** (`m8-pipeline-engine/`)
- `Chart.yaml` appVersion 1.0.0
- `values.yaml` (replicas 2, resources 500m/1Gi → 2000m/4Gi, priorityClass system-cluster-critical, persistence gp3/10Gi, HPA disabled)
- `templates/serviceaccount.yaml` (IRSA annotation)
- `templates/configmap.yaml` (11 non-secret keys + schemaVersion 1.0.0)
- `templates/statefulset.yaml` (StatefulSet, volumeClaimTemplates, probes, securityContext)
- `templates/service.yaml` (headless)
- `templates/networkpolicy.yaml` (M6-only ingress)
- `templates/pdb.yaml` (minAvailable 1)
- `templates/certificate.yaml` (24h/2h rotation)

**M9 Intent Router** (`m9-intent-router/`)
- `Chart.yaml` appVersion 1.1.0
- `values.yaml` (replicas 3, resources 200m/256Mi → 1000m/1Gi, priorityClass system-node-critical, HPA min 2 max 10 70%)
- `templates/serviceaccount.yaml` (IRSA)
- `templates/configmap.yaml` (7 non-secret keys + schemaVersion 1.1.0)
- `templates/deployment.yaml`
- `templates/service.yaml` (ClusterIP)
- `templates/networkpolicy.yaml`
- `templates/pdb.yaml`
- `templates/hpa.yaml` (averageUtilization 70)
- `templates/certificate.yaml`

**M12 Supervisor** (`m12-supervisor/`)
- `Chart.yaml` appVersion 0.2.0
- `values.yaml` (replicas 2, resources 300m/512Mi → 1500m/2Gi, priorityClass system-cluster-critical, HPA min 2 max 10 70%)
- `templates/serviceaccount.yaml` (IRSA)
- `templates/configmap.yaml` (7 non-secret keys including M12_KYC_ADAPTER_URL)
- `templates/deployment.yaml` (M12_KYC_ADAPTER_URL via configMapKeyRef)
- `templates/service.yaml`
- `templates/networkpolicy.yaml` (M6 + extraIngressFrom loop)
- `templates/pdb.yaml`
- `templates/hpa.yaml`
- `templates/certificate.yaml`

### Values fragment (deploy/helm/007-fsi/)

- `values-cloud.wave2.yaml` — three top-level keys (`m8-pipeline-engine`, `m9-intent-router`, `m12-supervisor`) with image repo/tag/digest placeholders, IRSA role ARN placeholders, resources, priorityClass, HPA toggles, persistence (M8), dispatch mode (M12 local).

### Tests (deploy/tests/)

- `test_helm_lint.sh` — append-safe with `### WAVE2_LINT_BLOCK ###` sentinel. Strict on Wave 2 charts (M8/M9/M12), warning-only on Wave 1/other charts (their umbrella values handle it). Graceful skip if helm missing.
- `test_helm_template_intelligence.sh` — renders each Wave 2 sub-chart, asserts 14 verification gates via grep + R9.4 credential-shape scan + R9.5 Python YAML syntax fallback. Graceful skip if helm missing.

---

## Test Results

### Python suite

```
PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60
1757 passed, 5 skipped, 5 xfailed, 1 xpassed, 100 warnings in 10.53s
```

Baseline before Wave 2 build: 1707 passed (collection count drift, no test regressions). 10/10 consecutive runs stable, zero flakes.

### Shell tests

```
test_helm_lint.sh                  → OK: Wave 2 sub-charts lint clean
test_helm_template_intelligence.sh → OK: all Wave 2 verification gates passed
```

10/10 consecutive runs stable.

### Verification gate evidence

| Gate | Evidence |
|---|---|
| No credentials in Dockerfile/ConfigMap/values | R9.4 regex scan: zero matches after exclusions (vault_path, secretName, secretKeyRef, configMapKeyRef, serviceAccountToken) |
| M8 StatefulSet | `kind: StatefulSet` present in M8 render; absent in M9+M12 |
| M9 + M12 Deployment | `kind: Deployment` present in M9+M12 |
| readinessProbe + livenessProbe on every workload | grep confirmed in all three renders |
| HPA target CPU ≤ 70 | `averageUtilization: 70` literal in M9 + M12 HPAs |
| Bedrock via IAM role annotation | `eks.amazonaws.com/role-arn` in all three ServiceAccounts |
| M12 KYC URL via ConfigMap | awk extraction around `name: M12_KYC_ADAPTER_URL` confirmed `configMapKeyRef` (not secretKeyRef) |
| PriorityClass | M8+M12 system-cluster-critical, M9 system-node-critical |
| Pod securityContext | `runAsNonRoot: true` + `readOnlyRootFilesystem: true` in all three |
| NetworkPolicy M6-only | `app: m6-mcp-gateway` appears in all three NetworkPolicies |

---

## Non-Negotiables Verified

- [x] No credentials in any Dockerfile, ConfigMap, or values fragment
- [x] M8 uses StatefulSet; M9 + M12 use Deployment
- [x] Every Deployment/StatefulSet has readinessProbe + livenessProbe
- [x] HPA target CPU utilization ≤ 70%
- [x] Bedrock access via IAM role annotation (IRSA), never hard-coded keys
- [x] M12 sub-chart wires KYC adapter URL via env from ConfigMap, not a Secret
- [x] PriorityClass: system-cluster-critical for M8 + M12, system-node-critical for M9
- [x] Pod securityContext: runAsNonRoot, readOnlyRootFilesystem, drop ALL caps, seccomp RuntimeDefault
- [x] cert-manager Certificate per module with 24h duration + 2h renewBefore
- [x] NetworkPolicy default-deny ingress; only M6 allowed (M12 extraIngressFrom documented for M1 identity)
- [x] PodDisruptionBudget (minAvailable 1) per module
- [x] Sub-charts lint cleanly (Wave 2: strict pass)
- [x] Full Python suite green (10/10 stable, 1757 passed)

---

## Known Blockers / Wave 3 Handoff

| Id | Item | Owner |
|---|---|---|
| HO1 | Umbrella Chart.yaml `dependencies:` list must add m8-pipeline-engine, m9-intent-router, m12-supervisor (file://charts/*) | Wave 1 (merge with Wave 2 sub-charts landed) |
| HO2 | ExternalSecret CRDs for M8 checkpointer DSN / M9 HMAC keys / M12 HITL HMAC keys — contract documented in spec §2.4, actual resources ship in Wave 3 with the operator install | Wave 3 |
| HO3 | M12_DISPATCH_MODE flip from `local` to `remote` once M9 + M8 pod network paths are verified end-to-end | Wave 3 |
| HO4 | Image digests (`REPLACE_ME_SHA256`) filled by CI/CD at deploy time from registry manifest digests | Ops/CI |
| HO5 | IRSA role ARNs (`arn:aws:iam::REPLACE_ME:role/project-007-mN-bedrock`) replaced with real account IDs per-tenant | Ops/IaC |
| HO6 | ServiceMonitor for Prometheus scraping `/metrics` — deferred | Future hardening wave |
| HO7 | topologySpreadConstraints + PodAntiAffinity for M9/M12 HPA scale-out | Future hardening wave |
| HO8 | M11-REST polyglot TypeScript containers (separate language/build) | Wave 3 |
| HO9 | Auth middleware + OpenTelemetry + request signing on the FastAPI shims | Future hardening wave |

---

## Design Decisions Recorded

- **M7 has no Dockerfile / Helm chart**: M7 is a pure Python library imported in-process by M6, M8, M11. Making it a service would add a network hop to what is currently a function call and inflate latency for every adapter response. Module boundary Rule 9 is satisfied at the import graph, not the process boundary. See spec §4.1.
- **FastAPI shims live under deploy/docker/, not src/**: library `__all__` assertions would break if a FastAPI entrypoint were added to the library. Shim is container-owned infra. See spec §4.2.
- **M8 StatefulSet, M12 Deployment**: M8 benefits from stable pod identity for checkpointer overflow PVC (4h HITL state). M12 is stateless supervisor glue — any pod can resume any session from M10. See spec §4.3.
- **PriorityClass split**: M9 on critical request path gets system-node-critical; M8/M12 are async/glue and tolerate rescheduling, get system-cluster-critical. See spec §4.4.
- **KYC URL in ConfigMap, not Secret**: URL is service discovery (not secret); only the API key behind it is secret (in Vault). Split minimizes secret surface. See spec §4.5.
- **M12 library imports M8+M9 (permitted)**: M12 is supervisor glue module; library-level import is by design (SPECIALIST_DISPATCH). Runtime path uses HTTP in `remote` mode. See spec §4.8.
