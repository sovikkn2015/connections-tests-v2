# Ops Hardening Wave 1 — COMPLETE

> Wave: **Wave 1 — Trust-layer deployment artefacts** (M1 Identity, M2/M4 Policy Engine, M6 MCP Gateway, M10 Audit Logger).
> Topology: **cloud only** (Steering Rule 25; hybrid + on-prem deferred to Phase 4).
> Playbook: 7-step (`docs/007-module-build-playbook.md`).
> Spec: `.kiro/specs/ops-hardening-wave1-trust-layer.md`
> Reviewer: **gateway-specialist** (self-reviewed per task instructions).

---

## 1. LLMJ Score

| Review | Verdict | Score |
|--------|---------|------:|
| v1 review (`ops-hardening-wave1-trust-layer-REVIEW.md`)    | CONDITIONAL GO | 7.35 / 10 |
| v2 review (`ops-hardening-wave1-trust-layer-REVIEW-v2.md`) | **GO**         | **8.55 / 10** |

v2 rewrite resolved all five C-blockers (helm baseline pinned, port contract rewritten to single-listener 8080, ExternalSecret CRD pinned to `external-secrets.io/v1beta1`, cert-manager issuer kind + name pinned, regression invariant rewritten from brittle count to exact-preservation) plus the seven R-recommendations (OCI label set, ClusterSecretStore name, Pod Security `restricted` profile, HPA `autoscaling/v2`, named compose network `007-trust-layer`, helm-v4 lint cleanliness, rollback plan). All four G-gaps either closed or explicitly deferred in §4 of the spec.

---

## 2. Artefacts shipped

### 2.1 FastAPI wrappers (Phase 1 B2 gate prerequisite)

| Path                                          | Lines |
|-----------------------------------------------|------:|
| `src/m1_identity/app.py`                      |  ~220 |
| `src/m2_m4_policy_engine/app.py`              |  ~440 |

Both expose `create_app()` plus a module-level `app: FastAPI` for the uvicorn entrypoint. Single uvicorn listener on `:8080`. Routes: `/health`, `/ready`, plus `/aid/verify` (M1) and `/authority/check` + `/mnpi/filter` (M2/M4). No stdlib `logging`. No credentials. No network calls at import time. Generic error bodies only.

**FastAPI wrappers total: 662 LOC**

### 2.2 Dockerfiles

| Path                                                     | Lines |
|----------------------------------------------------------|------:|
| `deploy/docker/m1-identity/Dockerfile`                   |  ~88  |
| `deploy/docker/m2-m4-policy-engine/Dockerfile`           |  ~83  |
| `deploy/docker/m6-mcp-gateway/Dockerfile`                |  ~96  |
| `deploy/docker/m10-audit-logger/Dockerfile`              |  ~81  |

All four:
- Multi-stage (builder + runtime).
- `python:3.12-slim` runtime; no distroless (see spec §R2 rationale).
- `USER 1000` numeric non-root.
- mTLS mount points at `/etc/007/mtls/{tls.crt,tls.key,ca.crt}`, Vault token at `/var/run/secrets/vault/token`.
- `HEALTHCHECK` probes `http://localhost:8080/health`.
- OCI image-spec labels declared at runtime layer.
- No `apt-get upgrade`, no `ADD` from URL, no credentials.

Pre-existing in-source Dockerfiles (`src/m6_mcp_gateway/Dockerfile`, `src/m10_audit_logger/Dockerfile`) remain authoritative for laptop dev. The `deploy/docker/` variants are canonical for Helm + docker-compose.

**Dockerfiles total: 364 LOC**

### 2.3 Helm umbrella chart `deploy/helm/007-fsi/`

| Path | Purpose |
|------|---------|
| `Chart.yaml`        | v2 chart, 4 Wave 1 deps + 3 conditional intelligence-layer deps (disabled by default) |
| `values-cloud.yaml` | cloud topology defaults (EKS/GKE compatible) |
| `values.yaml`       | helm-defaults fallback |
| `.helmignore`       | packaging exclusions |

Sub-charts under `charts/`:
- `m1-identity/` — Deployment, Service, ServiceAccount, NetworkPolicy, PodDisruptionBudget, Certificate, ExternalSecret, _helpers.tpl (8 template files + Chart.yaml + values.yaml).
- `m2-m4-policy-engine/` — idem.
- `m6-mcp-gateway/` — idem **plus** `horizontalpodautoscaler.yaml` (M6 is the only horizontally-scaled service in Wave 1).
- `m10-audit-logger/` — idem.

Every Certificate has `duration: 24h` and `renewBefore: 2h` (Steering Rule 21). Every ExternalSecret uses the `secret/data/007/<module>/` Vault path convention and pins `apiVersion: external-secrets.io/v1beta1`. Every Deployment carries a `restricted`-profile Pod Security context. Every NetworkPolicy is default-deny ingress; M1/M2-M4/M10 allow only from `app.kubernetes.io/name: m6-mcp-gateway`, M6 allows from `app.kubernetes.io/part-of: 007-fsi`.

**Helm umbrella + 4 sub-charts total: 188 + 364 + 360 + 415 + 367 = 1694 LOC**

### 2.4 docker-compose for local dev

| Path | Lines |
|------|------:|
| `deploy/compose/docker-compose.yml` | 168 |

Services: `vault-dev` (dev mode, auto-unsealed), `postgres` (15-alpine), `m1-identity`, `m2-m4-policy-engine`, `m6-mcp-gateway`, `m10-audit-logger`. Named network `007-trust-layer`. mTLS disabled (`ENABLE_MTLS=false`, `FAKE_SECRETS=true`). No host-port publishing. Health-checks on `:8080/health`. Local-only `dev-only-root` Vault token disclosed in header comment.

### 2.5 Deploy-layer shell tests

| Path | Purpose |
|------|---------|
| `deploy/tests/test_helm_lint.sh`           | Lints umbrella + 4 sub-charts. Skip-on-no-helm (exit 0). |
| `deploy/tests/test_helm_template.sh`       | Renders `values-cloud.yaml`, counts resource kinds + verifies port contracts, certificate duration, Vault path prefix. |
| `deploy/tests/test_dockerfile_security.sh` | Greps each of the 4 Dockerfiles for forbidden patterns + required directives. |

All three are `chmod +x`, start with `set -euo pipefail`, and are path-resilient via `cd "$(dirname "$0")/../.."`.

**Deploy-tests total: 277 LOC**

---

## 3. Verification evidence

### 3.1 `helm lint` pass

```
$ helm lint deploy/helm/007-fsi/charts/m1-identity
1 chart(s) linted, 0 chart(s) failed

$ helm lint deploy/helm/007-fsi/charts/m2-m4-policy-engine
1 chart(s) linted, 0 chart(s) failed

$ helm lint deploy/helm/007-fsi/charts/m6-mcp-gateway
1 chart(s) linted, 0 chart(s) failed

$ helm lint deploy/helm/007-fsi/charts/m10-audit-logger
1 chart(s) linted, 0 chart(s) failed

$ helm lint deploy/helm/007-fsi -f deploy/helm/007-fsi/values-cloud.yaml
1 chart(s) linted, 0 chart(s) failed
```

Validated against both helm **v3.17.4** (baseline) and helm **v4.1.4** (forward-compat). Zero ERROR-level findings; only informational "icon is recommended" on sub-chart `Chart.yaml` files (the icon field is present on the umbrella).

### 3.2 `helm template` render, contract checks

```
$ bash deploy/tests/test_helm_template.sh
[test_helm_template] OK -- 4 Deployments (count=4)
[test_helm_template] OK -- 4 Services (count=4)
[test_helm_template] OK -- 4 NetworkPolicies (count=4)
[test_helm_template] OK -- 4 Certificates (count=4)
[test_helm_template] OK -- 4 ExternalSecrets (count=4)
[test_helm_template] OK -- 4 PodDisruptionBudgets (count=4)
[test_helm_template] OK -- 4 ServiceAccounts (count=4)
[test_helm_template] OK -- 1 HorizontalPodAutoscaler (M6 only) (count=1)
[test_helm_template] OK -- 4 x duration 24h (count=4)
[test_helm_template] OK -- 4 x renewBefore 2h (count=4)
[test_helm_template] OK -- 4 x targetPort 8080 (count=8)
[test_helm_template] OK -- 4 x port 8443 (count=4)
[test_helm_template] OK -- 4 x readinessProbe (count=4)
[test_helm_template] OK -- 4 x livenessProbe (count=4)
[test_helm_template] OK -- secret/data/007 prefix (>=4) (count=11, >= 4)
[test_helm_template] OK -- part-of: 007-fsi (>=4) (count=34, >= 4)
RESULT: PASS
```

### 3.3 Dockerfile security grep gate

```
$ bash deploy/tests/test_dockerfile_security.sh
[test_dockerfile_security] scanning: deploy/docker/m1-identity/Dockerfile
[test_dockerfile_security] scanning: deploy/docker/m2-m4-policy-engine/Dockerfile
[test_dockerfile_security] scanning: deploy/docker/m6-mcp-gateway/Dockerfile
[test_dockerfile_security] scanning: deploy/docker/m10-audit-logger/Dockerfile
RESULT: PASS
```

### 3.4 Dockerfile build smoke (finch)

The builder stage of each of the four Dockerfiles compiles cleanly on a local finch (Docker API compatible):

```
007-fsi/m1-identity:builder-test            done
007-fsi/m2-m4-policy-engine:builder-test    done
007-fsi/m6-mcp-gateway:builder-test         done
007-fsi/m10-audit-logger:builder-test       done
```

The runtime stage is not smoke-built in CI because it requires the full apt/pip graph; builder-stage success is the sufficient invariant for Wave 1 (spec AC2.12).

### 3.5 Python regression (10/10 stress run)

Full pytest suite run ten times sequentially. Every run produced the identical result:

```
run=1  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.07s
run=2  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 8.83s
run=3  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.11s
run=4  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.90s
run=5  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.23s
run=6  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.25s
run=7  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 8.88s
run=8  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.62s
run=9  1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.56s
run=10 1757 passed, 12 skipped, 5 xfailed, 1 xpassed, 100 warnings in 9.83s
```

**10/10 stable.** No flakes. No regressions vs the task-stated 1707-pass baseline; the Wave 1 additions do not add any pytest tests, the observed +50 passing delta comes from a concurrent Wave 3 MinIO-WORM work-in-progress that appeared in the working tree during this session and is orthogonal to Wave 1 scope.

### 3.6 Grep-gate spot checks (spec AC7.*)

| AC | Check | Result |
|----|-------|--------|
| AC7.1 | No credentials in `deploy/` | PASS — the only `password` hits are (a) a disclosed `dev-postgres` comment in docker-compose.yml, (b) a credential-detection regex in another wave's test script, and (c) a `property: password` ExternalSecret reference (field name, not a value) |
| AC7.2 | Exactly one `USER 1000` per Dockerfile | PASS (all 4) |
| AC7.3 | NetworkPolicy default-deny + m6 allow | PASS (M1/M2-M4/M10 allow from `name: m6-mcp-gateway`, M6 allows from `part-of: 007-fsi`) |
| AC7.4 | Certificate duration 24h + renewBefore 2h | PASS (all 4) |
| AC7.5 | ExternalSecret `secret/data/007/` prefix | PASS (11 matches across rendered output) |
| AC7.6 | Deployments have readiness + liveness probes on `/health:8080` | PASS (4 readinessProbe + 4 livenessProbe) |

---

## 4. LOC totals

| Category              | Lines |
|-----------------------|------:|
| FastAPI wrappers      |   662 |
| Dockerfiles           |   364 |
| Helm umbrella         |   188 |
| Helm sub-chart: m1    |   364 |
| Helm sub-chart: m2/m4 |   360 |
| Helm sub-chart: m6    |   415 |
| Helm sub-chart: m10   |   367 |
| docker-compose        |   168 |
| Deploy-layer tests    |   277 |
| **Grand total**       | **3,165** |

Specs are additional (not counted against build-artefact total):
- Spec v2: 547 lines
- Review v1: 167 lines
- Review v2: 70 lines
- This COMPLETE marker: ~300 lines

---

## 5. Scope boundaries respected

- **Modules**: M1, M2/M4, M6, M10 only. M7, M8, M9, M11, M12 intelligence-layer and compliance-gap modules are explicitly out-of-scope in Wave 1 (see spec §4).
- **Topology**: cloud only. `values-hybrid.yaml` + `values-onprem.yaml` **not shipped** (no empty placeholders that would silently pass grep-gates).
- **No secrets in git**: verified by grep-gates in AC7.1 and the Dockerfile security script.
- **No cross-wave contamination**: the pre-existing intelligence-layer sub-charts (`m8-pipeline-engine`, `m9-intent-router`, `m12-supervisor`) were discovered in the tree and declared in the umbrella `Chart.yaml` as **conditional dependencies disabled by default**. They do not install under `values-cloud.yaml`. This is the non-destructive way to keep helm v4 happy about charts-dir completeness without modifying another wave's work.

---

## 6. Follow-up items (tracked, not blocking)

- **Egress hardening wave**: narrow the `egress: [{}]` allow-all on the four NetworkPolicies to explicit backend endpoints.
- **Phase 4**: ship `values-hybrid.yaml` + `values-onprem.yaml`.
- **Import-time socket-disabled pytest**: verify FastAPI `app.py` modules truly avoid any network I/O at import. Low-value / high-setup; deferred.
- **Per-tenant overlay examples**: document how a tenant overlays `global.tenantRoleArn` + `certManager.issuerName` etc.
- **ArgoCD ApplicationSet**: wire the umbrella into a GitOps ApplicationSet for per-tenant rollout.

---

## 7. Ship sign-off

All 7 spec tasks done:

- [x] Task 3.1 — FastAPI wrappers for M1 and M2/M4 (`src/*/app.py`)
- [x] Task 3.2 — four deploy/docker Dockerfiles
- [x] Task 3.3 — Helm umbrella + 4 sub-charts, all lint clean
- [x] Task 3.4 — docker-compose for local dev
- [x] Task 3.5 — three deploy-layer shell tests, all passing
- [x] Task 3.6 — regression + grep gates (Python suite 10/10 stable; AC7.1–AC7.6 all pass)
- [x] Task 3.7 — COMPLETE marker (this file)

**Wave 1 — Ops Hardening Trust Layer: READY TO SHIP.**

LLMJ GO score: **8.55 / 10**.
10/10 stress run: **stable**.
Test count: 1707 baseline preserved (1757 observed — orthogonal wave-3 tests).
helm lint: **PASS** across 5 charts on helm 3 and helm 4.

---

*ops-hardening-wave1-COMPLETE.md — Project 007 FSI Interoperability Platform*
*Reviewer / builder: gateway-specialist. Wave 1 trust-layer ops hardening.*
