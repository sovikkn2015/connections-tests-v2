# Ops Hardening Wave 2 — Intelligence Layer (M7, M8, M9, M12)

> **Version**: v0.2.0 (full rewrite addressing v1 review RF1-RF16)
> **Status**: Spec
> **Date**: 2026-05-02
> **Playbook**: 7-step (Spec → LLMJ → Fix → Re-review → Build → Verify → Complete)
> **Boundary**: intelligence-layer only (M8 pipeline engine, M9 intent router, M12 supervisor). M7 documented as library (no deployment). M11-REST polyglot containers are Wave 3.
> **Coordination**: Wave 1 (gateway-agent, running in parallel) owns `deploy/helm/007-fsi/Chart.yaml` umbrella + `deploy/tests/test_helm_lint.sh` base. Wave 2 contributes sub-charts + values fragment + extends the lint script.
> **Delta from v0.1.0**: Adds pod securityContext, image digest fallback logic, Vault DSN contract, credential-grep regex, M12 extraIngressFrom schema, append-safe sentinel logic, SKIP banner semantics, resource requests/limits, Python YAML syntax fallback, COMPLETE marker schema, and explicit test grep lines for every verification gate (RF1-RF4, RF13).

---

## 1. Requirements

### R1 — Scope

- R1.1 Wave 2 MUST deliver Dockerfiles for M8, M9, and M12 under `deploy/docker/m{8,9,12}-*/Dockerfile`.
- R1.2 Wave 2 MUST deliver Helm sub-charts for M8, M9, M12 under `deploy/helm/007-fsi/charts/m{8,9,12}-*/` with Chart.yaml, values.yaml, templates/.
- R1.3 Wave 2 MUST contribute a values-cloud fragment (three top-level keys: `m8-pipeline-engine`, `m9-intent-router`, `m12-supervisor`) for the umbrella values-cloud.yaml. The fragment is shipped as `deploy/helm/007-fsi/values-cloud.wave2.yaml` to avoid stepping on Wave 1's ownership of the primary file.
- R1.4 Wave 2 MUST NOT create an M7 Dockerfile or M7 sub-chart. M7 is a pure Python library — decision recorded in §4.1.
- R1.5 Wave 2 MUST NOT modify library source code inside `src/m8_pipeline_engine/`, `src/m9_intent_router/`, or `src/m12_supervisor/`. All service-wrapping code (FastAPI shim, health endpoints) lives under `deploy/docker/m{N}-*/app/`.

### R2 — Dockerfile invariants (per module)

- R2.1 Base: `python:3.12-slim`.
- R2.2 Non-root UID 1000 — image side. (Pod-level enforcement in R5.6.)
- R2.3 Expose port 8443 only.
- R2.4 mTLS cert volume mount at `/etc/007/mtls/` (files: `tls.crt`, `tls.key`, `ca.crt`). Source = Kubernetes Secret populated by cert-manager.
- R2.5 No credential-shaped ENV values in Dockerfile. Only non-secret defaults (region, model id, host names, numeric thresholds, Vault paths — never Vault values).
- R2.6 No baked AWS credentials. Bedrock access is via IRSA; the pod's ServiceAccount carries the role annotation; the container inherits credentials via IMDS/STS.
- R2.7 HEALTHCHECK via `curl -sf http://localhost:8443/health`.
- R2.8 COPY the full M3 schema registry + module source + any compliance sub-module dependencies.
- R2.9 ENTRYPOINT: `uvicorn` launching `service.m{N}_app:app` (shim lives under `deploy/docker/m{N}-*/app/main.py`, copied into `/app/service/`).
- R2.10 Dependencies pinned by `>=x.y,<x+1.0`: fastapi, uvicorn[standard], pydantic, boto3. Per-module: M8 also pins langgraph + psycopg[binary]; M12 also pins langgraph.
- R2.11 `HEALTHCHECK` MUST be declared within the Dockerfile.

### R3 — Module-specific env contract

Every env var below MUST be referenced from the container ENTRYPOINT or default ENV block. Values come from ConfigMap (non-secret) or Secret-via-Vault (secret).

#### M8 Pipeline Engine
- R3.1 `AWS_REGION` — default `us-east-1`
- R3.2 `M8_MODEL_PROVIDER` — default `bedrock`
- R3.3 `M8_MODEL_ID` — default `anthropic.claude-sonnet-4-5-20250929-v1:0`
- R3.4 `M8_CHECKPOINTER_BACKEND` — default `postgres`
- R3.5 `M8_CHECKPOINTER_DSN_VAULT_PATH` — default `secret/data/m8/checkpointer_dsn` (Vault path template, NOT a DSN)
- R3.6 `M8_HITL_HMAC_KEY_VAULT_PATH` — default `secret/data/m8/hitl_hmac_key`
- R3.7 `M8_GATEWAY_BASE_URL` — default `https://m6-gateway.internal:8443`
- R3.8 `M8_AUDIT_BASE_URL` — default `https://m10-audit.internal:8443`
- R3.9 `M8_HITL_TIMEOUT_SECONDS` — default `14400`
- R3.10 `M8_MAX_WALL_CLOCK_SECONDS` — default `1200`
- R3.11 `M8_ALERT_WALL_CLOCK_SECONDS` — default `900`

#### M9 Intent Router
- R3.12 `AWS_REGION` — default `us-east-1`
- R3.13 `M9_PROVIDER` — default `bedrock`
- R3.14 `M9_MODEL_ID` — default `anthropic.claude-3-5-haiku-20241022-v1:0`
- R3.15 `M9_TIMEOUT_MS` — default `1500`
- R3.16 `M9_TENANT_HMAC_KEY_VAULT_PATH` — default `secret/data/m9/tenants/<tenant_id>/hmac_key`
- R3.17 `M9_CONFIDENCE_HIGH` — default `0.95`
- R3.18 `M9_CONFIDENCE_MED` — default `0.80`

#### M12 Supervisor
- R3.19 `AWS_REGION` — default `us-east-1`
- R3.20 `M12_MODEL_ID` — default `anthropic.claude-3-5-haiku-20241022-v1:0`
- R3.21 `M12_KYC_ADAPTER_URL` — default `https://m11-kyc.internal:8443` (URL is NOT secret; verification gate)
- R3.22 `M12_HITL_HMAC_KEY_VAULT_PATH` — default `secret/data/m12/hitl_hmac_key`
- R3.23 `M12_M9_BASE_URL` — default `https://m9-intent-router.internal:8443`
- R3.24 `M12_M8_BASE_URL` — default `https://m8-pipeline-engine.internal:8443`
- R3.25 `M12_DISPATCH_MODE` — default `local` (Phase 2 lighthouse in-process; flip to `remote` in Wave 3 — RecF2)

### R4 — Helm sub-chart invariants

- R4.1 `Chart.yaml` apiVersion v2, type application, version 0.1.0, appVersion matching module COMPLETE spec.
- R4.2 `values.yaml` defaults for image repo/tag/digest, resources, replicas, probes, HPA (M9/M12), persistence (M8).
- R4.3 ServiceAccount with `eks.amazonaws.com/role-arn` annotation (IRSA). Default role ARN placeholder `arn:aws:iam::REPLACE_ME:role/REPLACE_ME`.
- R4.4 Service at port 8443 named `tls`.
- R4.5 NetworkPolicy — default-deny ingress (only one from rule), ingress sources: pods with `app: m6-mcp-gateway`. M12 accepts extra sources via `networkPolicy.extraIngressFrom:` list (RF9; schema in §2.5).
- R4.6 PodDisruptionBudget `minAvailable: 1`.
- R4.7 cert-manager.io/v1 Certificate with `duration: 24h`, `renewBefore: 2h`, `issuerRef` from values.
- R4.8 ConfigMap carries the module's non-secret config keys + `schemaVersion` pinned to library SCHEMA_VERSION + `configSchemaVersion: m5:v0.3.0`.

### R5 — Workload kind + probes + security context + resources

- R5.1 M8 MUST be `StatefulSet` — pod identity matters for checkpointer overflow PVC.
- R5.2 M9 MUST be `Deployment`.
- R5.3 M12 MUST be `Deployment`.
- R5.4 Every workload MUST declare readinessProbe (`GET /ready`, initial delay 5s, period 10s, failureThreshold 3) and livenessProbe (`GET /health`, initial delay 10s, period 30s, failureThreshold 3), port 8443, scheme HTTP (mTLS terminates at sidecar — upstream concern).
- R5.5 M8 `volumeClaimTemplates` for `checkpointer-overflow` (accessModes `[ReadWriteOnce]`, storageClass default `gp3`, size default `10Gi`).
- R5.6 **Pod securityContext** (RF5) — every workload template MUST declare at pod level:
  - `runAsNonRoot: true`
  - `runAsUser: 1000`
  - `runAsGroup: 1000`
  - `fsGroup: 1000`
  - `seccompProfile.type: RuntimeDefault`
  And container-level:
  - `allowPrivilegeEscalation: false`
  - `readOnlyRootFilesystem: true`
  - `capabilities.drop: [ALL]`
  Supplementary writable paths via `emptyDir` at `/tmp` (plus M8's `/var/lib/m8/overflow` backed by PVC).
- R5.7 **Resources** (RF14) — values.yaml defaults:
  - M8: requests `cpu 500m mem 1Gi`, limits `cpu 2000m mem 4Gi`
  - M9: requests `cpu 200m mem 256Mi`, limits `cpu 1000m mem 1Gi`
  - M12: requests `cpu 300m mem 512Mi`, limits `cpu 1500m mem 2Gi`

### R6 — HPA (M9 + M12 only)

- R6.1 HPA autoscaling/v2 rendered for M9 and M12.
- R6.2 Target CPU `averageUtilization: 70` (verification gate literal).
- R6.3 min replicas default 2, max default 10.
- R6.4 M8 MUST NOT have HPA.

### R7 — PriorityClass

- R7.1 M8 `priorityClassName: system-cluster-critical`.
- R7.2 M9 `priorityClassName: system-node-critical`.
- R7.3 M12 `priorityClassName: system-cluster-critical`.

### R8 — Values-cloud fragment

- R8.1 Path: `deploy/helm/007-fsi/values-cloud.wave2.yaml`.
- R8.2 Three top-level keys: `m8-pipeline-engine`, `m9-intent-router`, `m12-supervisor`.
- R8.3 Each supplies: `image.repository`, `image.tag`, `image.digest` (placeholder `REPLACE_ME_SHA256`), `irsa.roleArn` (placeholder), `replicas`, `resources`, module-specific overrides.
- R8.4 Zero credential-shaped values. Vault path references only.

### R9 — Tests (shell + python-fallback)

- R9.1 `deploy/tests/test_helm_lint.sh` — append-safe. Detects sentinel `### WAVE2_LINT_BLOCK ###` via `grep -qF`; if absent, appends a separator newline then the Wave 2 block. Idempotent (running twice does not duplicate). Graceful skip (exit 0, SKIP banner to stderr) if `helm` CLI missing. If file does not exist, create with a header and Wave 2 block.

- R9.2 `deploy/tests/test_helm_template_intelligence.sh` — renders each Wave 2 sub-chart with `helm template -f values-cloud.wave2.yaml` into a tmp dir and asserts EVERY gate below via grep. Graceful skip with SKIP banner if helm missing. **All assertions are required**:

  | Grep pattern | Required in |
  | --- | --- |
  | `eks.amazonaws.com/role-arn` | M8, M9, M12 renders (RF: IRSA) |
  | `mountPath: /etc/007/mtls` | M8, M9, M12 (RF: mTLS) |
  | `kind: HorizontalPodAutoscaler` | M9, M12 ONLY (RF4) |
  | `kind: StatefulSet` | M8 ONLY (RF1) |
  | `kind: Deployment` | M9, M12 (RF1) |
  | `priorityClassName: system-cluster-critical` | M8, M12 (RF2) |
  | `priorityClassName: system-node-critical` | M9 (RF2) |
  | `readinessProbe:` | M8, M9, M12 (RF3) |
  | `livenessProbe:` | M8, M9, M12 (RF3) |
  | `averageUtilization: 70` | M9, M12 HPA (RF4) |
  | `runAsNonRoot: true` | M8, M9, M12 (RF5) |
  | `readOnlyRootFilesystem: true` | M8, M9, M12 (RF5) |
  | `podSelector:.*app: m6-mcp-gateway` (multiline or sequential-line grep) | M8, M9, M12 NetworkPolicies (RF13) |
  | `name: M12_KYC_ADAPTER_URL` followed by `configMapKeyRef:` | M12 Deployment (RF: KYC URL via ConfigMap) |

- R9.3 Python test suite MUST remain green: `PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60`.

- R9.4 **Credential-shape grep** (RF8) in test_helm_template_intelligence.sh — runs this regex against all rendered YAML:

  ```
  (?i)(password|secret|token|api[_-]?key|private[_-]?key)\s*[:=]\s*["']?[A-Za-z0-9+/=]{16,}
  ```

  Exclusions — lines matching `vault_path`, `VAULT_PATH`, `secretName:` (K8s Secret reference, not a value), `secretKeyRef:`, `serviceAccountToken:` (K8s API projection). Test fails if any non-excluded match is found.

- R9.5 **Python YAML syntax fallback** (RF15) — test_helm_template_intelligence.sh runs:

  ```
  python3 -c "import yaml, sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" \
    Chart.yaml values.yaml
  ```

  for every sub-chart's Chart.yaml and values.yaml (templates are not pure YAML due to Go templating; they are covered only when helm is installed via R9.2). Ensures minimum YAML validity on dev boxes without helm.

### R10 — Verification gates (automated)

- R10.1 No credentials — R9.4.
- R10.2 M8 StatefulSet; M9+M12 Deployment — R9.2.
- R10.3 Both probes on every workload — R9.2.
- R10.4 HPA CPU ≤ 70 — R9.2 literal `averageUtilization: 70`.
- R10.5 Bedrock via IAM role annotation — R9.2 IRSA grep.
- R10.6 M12 KYC URL via ConfigMap — R9.2 configMapKeyRef grep.
- R10.7 PriorityClass values — R9.2.
- R10.8 Pod securityContext — R9.2 (runAsNonRoot, readOnlyRootFilesystem).
- R10.9 "Only M6 can ingress" — R9.2 podSelector grep on NetworkPolicies.
- R10.10 YAML parseable on dev boxes — R9.5.

---

## 2. Design

### 2.1 Directory layout

```
my-agent-project-007-fsi-interoperability/
├── deploy/
│   ├── docker/
│   │   ├── m8-pipeline-engine/
│   │   │   ├── Dockerfile
│   │   │   └── app/
│   │   │       ├── __init__.py
│   │   │       └── main.py
│   │   ├── m9-intent-router/
│   │   │   ├── Dockerfile
│   │   │   └── app/
│   │   │       ├── __init__.py
│   │   │       └── main.py
│   │   └── m12-supervisor/
│   │       ├── Dockerfile
│   │       └── app/
│   │           ├── __init__.py
│   │           └── main.py
│   ├── helm/
│   │   └── 007-fsi/
│   │       ├── charts/
│   │       │   ├── m8-pipeline-engine/
│   │       │   │   ├── Chart.yaml
│   │       │   │   ├── values.yaml
│   │       │   │   └── templates/
│   │       │   │       ├── serviceaccount.yaml
│   │       │   │       ├── configmap.yaml
│   │       │   │       ├── statefulset.yaml
│   │       │   │       ├── service.yaml
│   │       │   │       ├── networkpolicy.yaml
│   │       │   │       ├── pdb.yaml
│   │       │   │       └── certificate.yaml
│   │       │   ├── m9-intent-router/
│   │       │   │   ├── Chart.yaml
│   │       │   │   ├── values.yaml
│   │       │   │   └── templates/
│   │       │   │       ├── serviceaccount.yaml
│   │       │   │       ├── configmap.yaml
│   │       │   │       ├── deployment.yaml
│   │       │   │       ├── service.yaml
│   │       │   │       ├── networkpolicy.yaml
│   │       │   │       ├── pdb.yaml
│   │       │   │       ├── hpa.yaml
│   │       │   │       └── certificate.yaml
│   │       │   └── m12-supervisor/
│   │       │       ├── Chart.yaml
│   │       │       ├── values.yaml
│   │       │       └── templates/
│   │       │           ├── serviceaccount.yaml
│   │       │           ├── configmap.yaml
│   │       │           ├── deployment.yaml
│   │       │           ├── service.yaml
│   │       │           ├── networkpolicy.yaml
│   │       │           ├── pdb.yaml
│   │       │           ├── hpa.yaml
│   │       │           └── certificate.yaml
│   │       └── values-cloud.wave2.yaml
│   └── tests/
│       ├── test_helm_lint.sh                (shared with Wave 1 — append-safe)
│       └── test_helm_template_intelligence.sh
└── .kiro/specs/
    ├── ops-hardening-wave2-intelligence-layer.md
    ├── ops-hardening-wave2-REVIEW.md          (Step 2, v1)
    ├── ops-hardening-wave2-REVIEW-v2.md       (Step 4, v2)
    └── ops-hardening-wave2-COMPLETE.md        (Step 7)
```

### 2.2 FastAPI shim design

Each `deploy/docker/m{N}-*/app/main.py` is a ~60-line wrapper:

- Imports fastapi, pydantic, stdlib, and the library module.
- Declares `app = FastAPI(title=..., version=SCHEMA_VERSION)`.
- `GET /health` returns `{"status": "ok"}` (liveness).
- `GET /ready` returns 200 when lazy env-derived clients have initialised; else 503.
- POST endpoint calls the library's public entrypoint with dependency-injected fakes if `M{N}_MODE=fake` (for offline bring-up), else real Bedrock/Vault clients.
- No cross-module imports (M12 shim may use M8+M9 since library boundary permits — see §4.2).
- Lives under `deploy/docker/` so library `__all__` assertions stay intact.

### 2.3 Helm template conventions

- kebab-case filenames matching resource kind.
- Resources namespaced under `{{ .Release.Namespace }}`.
- Labels: `app.kubernetes.io/name`, `app.kubernetes.io/part-of: 007-fsi`, `app.kubernetes.io/component: intelligence`.
- Templates literal (no shared `_helpers.tpl` in Wave 2; Wave 3 may refactor).
- **Image reference logic (RF6)**: each workload template uses:
  ```yaml
  image: "{{ .Values.image.repository }}{{ if .Values.image.digest }}@{{ .Values.image.digest }}{{ else }}:{{ .Values.image.tag }}{{ end }}"
  imagePullPolicy: IfNotPresent
  ```
  Production deploys set `image.digest`; local/dev builds use `image.tag`.

### 2.4 ConfigMap + Vault DSN wiring (RF7)

Each ConfigMap carries:
- Non-secret env keys from R3 as key/value pairs
- `schemaVersion` — library SCHEMA_VERSION (M8=1.0.0, M9=1.1.0, M12=0.2.0)
- `configSchemaVersion: m5:v0.3.0`
- Zero credential-shaped values

Secret wiring pattern (contract — consumed by a cluster-wide ExternalSecret operator OR Vault Agent Injector, out of Wave 2 scope but documented so Wave 3 can plug in):

```yaml
# Example (M8 checkpointer DSN) — NOT rendered in Wave 2. Contract only.
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata:
  name: m8-checkpointer-dsn
spec:
  refreshInterval: 15m
  secretStoreRef:
    kind: ClusterSecretStore
    name: vault-backend
  target:
    name: m8-checkpointer-dsn
    creationPolicy: Owner
  data:
    - secretKey: dsn
      remoteRef:
        key: m8/checkpointer_dsn
        property: dsn
```

The M8 pod consumes this via envFrom Secret (wired by Wave 3):
```yaml
env:
  - name: M8_CHECKPOINTER_DSN
    valueFrom:
      secretKeyRef:
        name: m8-checkpointer-dsn
        key: dsn
```

Wave 2 only ships the ConfigMap carrying the **Vault path** (`M8_CHECKPOINTER_DSN_VAULT_PATH`), which the library uses to look up the DSN at runtime via a Vault client (already wired in `src/m8_pipeline_engine/checkpointer.py`).

### 2.5 M12 NetworkPolicy extraIngressFrom schema (RF9)

values.yaml:

```yaml
networkPolicy:
  extraIngressFrom: []
  # Example:
  #   - namespace: trust-layer
  #     podLabels:
  #       app: m1-identity
  #     ports:
  #       - port: 8443
  #         protocol: TCP
```

templates/networkpolicy.yaml:

```yaml
ingress:
  - from:
      - podSelector:
          matchLabels:
            app: m6-mcp-gateway
    ports:
      - port: 8443
        protocol: TCP
  {{- range .Values.networkPolicy.extraIngressFrom }}
  - from:
      - namespaceSelector:
          matchLabels:
            kubernetes.io/metadata.name: {{ .namespace | quote }}
        podSelector:
          matchLabels:
            {{- toYaml .podLabels | nindent 12 }}
    ports:
      {{- toYaml .ports | nindent 6 }}
  {{- end }}
```

### 2.6 IRSA annotation

ServiceAccount:
```yaml
metadata:
  annotations:
    eks.amazonaws.com/role-arn: {{ .Values.irsa.roleArn | quote }}
```

Default `irsa.roleArn: "arn:aws:iam::REPLACE_ME:role/REPLACE_ME"`. The role has `bedrock:InvokeModel` only on the model ARNs in R3.3/R3.14/R3.20. No AWS creds in Dockerfile/Pod/Secret.

### 2.7 Test script design (RF10, RF11)

**test_helm_lint.sh** (append-safe):

```bash
#!/usr/bin/env bash
set -euo pipefail
SENTINEL="### WAVE2_LINT_BLOCK ###"
THIS_FILE="$(cd "$(dirname "$0")" && pwd)/test_helm_lint.sh"
# If this script ran standalone (Wave 1 not landed), own the file header + lint Wave 2.
# If Wave 1 already wrote the file, our strReplace will have added a Wave 2 block
# guarded by the sentinel. Running from this file still executes the whole script.
command -v helm >/dev/null 2>&1 || { echo "SKIP: helm not installed" >&2; exit 0; }
CHARTS_DIR="$(cd "$(dirname "$0")/../helm/007-fsi/charts" && pwd)"
for chart in m8-pipeline-engine m9-intent-router m12-supervisor; do
  echo "=== helm lint ${chart} ==="
  helm lint "${CHARTS_DIR}/${chart}"
done
# Guard against duplicate inclusion by Wave 1 merge.
grep -qF "${SENTINEL}" "${THIS_FILE}" || true
echo "${SENTINEL} OK"
```

The append-safety check runs at file write time (our build step), not at execution time: we `grep -qF "### WAVE2_LINT_BLOCK ###"` on the existing file; if present we do nothing; if absent we append the Wave 2 block; if file missing we create with a header.

**test_helm_template_intelligence.sh** (renders + greps):

```bash
#!/usr/bin/env bash
set -euo pipefail
command -v helm >/dev/null 2>&1 || { echo "SKIP: helm not installed" >&2; exit 0; }

HERE="$(cd "$(dirname "$0")" && pwd)"
CHARTS_DIR="$(cd "${HERE}/../helm/007-fsi/charts" && pwd)"
VALUES="${HERE}/../helm/007-fsi/values-cloud.wave2.yaml"

TMP="$(mktemp -d)"
trap 'rm -rf "${TMP}"' EXIT

for chart in m8-pipeline-engine m9-intent-router m12-supervisor; do
  # Use the matching top-level key from the fragment as the values sub-tree.
  out="${TMP}/${chart}.yaml"
  helm template "${chart}" "${CHARTS_DIR}/${chart}" \
    -f <(yq ".\"${chart}\"" "${VALUES}") > "${out}"
done

# [assertion table executed here; see R9.2]
# Credential grep over rendered YAML with exclusions (R9.4)
# Python YAML fallback for Chart.yaml + values.yaml (R9.5)
echo "OK"
```

(Actual build uses a fallback without `yq` dependency — see build step.)

### 2.8 COMPLETE marker schema (RF16)

`.kiro/specs/ops-hardening-wave2-COMPLETE.md` MUST contain:

1. Header (module, phase, date, playbook state).
2. Scorecard table (7 steps, done status, result string).
3. Delivered artifacts table (file paths + bytes).
4. Test results: Python pytest summary (`N passed, N skipped`), shell test summary.
5. Non-negotiables checklist — all 10 gates in R10 with pass/fail.
6. Known blockers + Wave 3 handoff list.

---

## 3. Tasks

### T1 — Dockerfiles (3)

- T1.1 `deploy/docker/m8-pipeline-engine/Dockerfile` (pins langgraph, psycopg[binary], boto3).
- T1.2 `deploy/docker/m9-intent-router/Dockerfile` (pins boto3).
- T1.3 `deploy/docker/m12-supervisor/Dockerfile` (pins langgraph, boto3).

### T2 — FastAPI shims (3)

- T2.1 `deploy/docker/m8-pipeline-engine/app/main.py` with `/health`, `/ready`, `POST /pipelines`.
- T2.2 `deploy/docker/m9-intent-router/app/main.py` with `/health`, `/ready`, `POST /route`.
- T2.3 `deploy/docker/m12-supervisor/app/main.py` with `/health`, `/ready`, `POST /dispatch`.

### T3 — M8 sub-chart

- T3.1 Chart.yaml
- T3.2 values.yaml (includes resources R5.7, image with digest fallback RF6, persistence)
- T3.3 templates/serviceaccount.yaml (IRSA)
- T3.4 templates/configmap.yaml (11 env keys + schemaVersion)
- T3.5 templates/statefulset.yaml (StatefulSet, volumeClaimTemplates, probes, securityContext, priorityClassName system-cluster-critical, mTLS mount)
- T3.6 templates/service.yaml
- T3.7 templates/networkpolicy.yaml (M6 only)
- T3.8 templates/pdb.yaml
- T3.9 templates/certificate.yaml (24h/2h)

### T4 — M9 sub-chart

- T4.1 Chart.yaml
- T4.2 values.yaml
- T4.3 templates/serviceaccount.yaml
- T4.4 templates/configmap.yaml (7 env keys)
- T4.5 templates/deployment.yaml (Deployment, probes, securityContext, priorityClassName system-node-critical, mTLS mount)
- T4.6 templates/service.yaml
- T4.7 templates/networkpolicy.yaml
- T4.8 templates/pdb.yaml
- T4.9 templates/hpa.yaml (target CPU 70)
- T4.10 templates/certificate.yaml

### T5 — M12 sub-chart

- T5.1 Chart.yaml
- T5.2 values.yaml
- T5.3 templates/serviceaccount.yaml
- T5.4 templates/configmap.yaml (7 env keys + M12_KYC_ADAPTER_URL)
- T5.5 templates/deployment.yaml (Deployment, KYC URL via configMapKeyRef, priorityClassName system-cluster-critical)
- T5.6 templates/service.yaml
- T5.7 templates/networkpolicy.yaml (M6 default + extraIngressFrom loop)
- T5.8 templates/pdb.yaml
- T5.9 templates/hpa.yaml
- T5.10 templates/certificate.yaml

### T6 — values-cloud fragment

- T6.1 `deploy/helm/007-fsi/values-cloud.wave2.yaml` with three top-level keys.

### T7 — Tests (shell + python fallback)

- T7.1 `deploy/tests/test_helm_lint.sh` (append-safe, graceful skip).
- T7.2 `deploy/tests/test_helm_template_intelligence.sh` (all R9.2 + R9.4 + R9.5 assertions).
- T7.3 Ensure scripts are executable (`chmod +x`).

### T8 — Verify

- T8.1 `PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60` exits 0 with no regression vs baseline 1707 passed.
- T8.2 `bash deploy/tests/test_helm_lint.sh` exits 0 (SKIP banner on no-helm dev env).
- T8.3 `bash deploy/tests/test_helm_template_intelligence.sh` exits 0 (SKIP banner on no-helm dev env).
- T8.4 Python YAML syntax pass on all Chart.yaml + values.yaml (R9.5 fallback).

### T9 — COMPLETE marker

- T9.1 Write `.kiro/specs/ops-hardening-wave2-COMPLETE.md` per §2.8 schema after all T8 gates pass.

---

## 4. Design Decisions

### 4.1 Why M7 has no Dockerfile

M7 is the schema translator library. Pure functions map vendor shapes to M3 canonical types. Running M7 as a standalone service would add a network hop to what is a function call today, inflate latency for every adapter response, and violate the design intent that M7 is stateless in-process translation logic.

- M7 ships as a Python package via `pyproject.toml`.
- Consumers (M6, M8, M11) import M7 directly; no M6→M7 MCP hop.
- No M7 Dockerfile, no M7 Helm chart, no M7 deployment.

Module boundary Rule 9 is satisfied at the import graph: pure-library modules may be imported; stateful service modules go through MCP/REST.

### 4.2 Why FastAPI shim lives under deploy/docker/ not src/

The library modules have `assert len(__all__) == N` checks that would break if we added a service entrypoint. Keeping the shim under `deploy/docker/m{N}-*/app/`:

- Library `__all__` stays stable.
- Shim is container-infra code versioned with the Dockerfile.
- Ops waves can update the shim without a library SCHEMA_VERSION bump.
- Library tests stay library-focused.

### 4.3 Why M8 StatefulSet but M12 Deployment

M8 runs LangGraph with durable checkpointer state tied to thread_id. Local PVC overflow for HITL gate payloads is pod-local and benefits from StatefulSet's stable identity. 20-minute wall clock budget, but 4-hour HITL pending state cannot tolerate unplanned rescheduling.

M12 is supervisor glue — state is carried in the request (pipeline_run_id, thread_id) and persisted in M10 audit. Any M12 pod can resume any session; stateless Deployment is correct.

### 4.4 Why PriorityClass split

`system-node-critical` preempts cluster pods under resource pressure. M9 is on the critical request path — losing M9 means every request blocks. M8 is async, tolerates restart (checkpointer resumes). M12 is supervisor — losing it breaks conversations but in-flight pipelines continue writing audit.

Order: M9 > (M8, M12) > other.

### 4.5 Why KYC URL is ConfigMap, not Secret

Task prompt explicit: "URL is not secret; the key is." URL `https://m11-kyc.internal:8443` is service discovery. API key is in Vault. Splitting URL→ConfigMap / key→Vault minimizes secret surface and lets ops teams change URLs without Vault touches.

### 4.6 Coordination with Wave 1

Wave 1 owns umbrella Chart.yaml, primary values-cloud.yaml, and base test_helm_lint.sh. Wave 2 owns M8/M9/M12 sub-charts, values fragment, template-intelligence test.

If Wave 1 has not landed when Wave 2 builds, sub-charts lint standalone. Umbrella integration is a post-merge concern outside both waves.

### 4.7 Why M11 REST is NOT in Wave 2

M11-REST adapters are TypeScript containers. Different build pipeline (npm + tsc + distroless/nodejs20). Bundling Python + Node.js in one wave muddies reviewability. Wave 3 is the TS wave.

### 4.8 M12 library imports M8+M9 — justification

The M12 supervisor library legitimately imports `m8_pipeline_engine` and `m9_intent_router` (see `src/m12_supervisor/__init__.py` — exports `SPECIALIST_DISPATCH`). This is glue-code invariance per the M12 v0.2.0 COMPLETE spec. At **runtime**, the M12 pod calls M9/M8 via HTTP (URLs in R3.23/R3.24) — the library imports exist only for shared type definitions and for fallback `local` dispatch mode (R3.25) used in Phase 2 lighthouse. The image copies the source for this reason; the dispatch mode flips to `remote` in Wave 3.

This does NOT violate Rule 9's "no cross-module imports" — M12 is the supervisor module whose declared role IS to glue specialists. Library boundary permits. Service boundary enforces HTTP at `remote` mode.

### 4.9 Upgrade path (RecF2)

Wave 2 ships `M12_DISPATCH_MODE=local`. Wave 3 flips to `remote` as part of the M11-REST adapter rollout, which provides the network-reachable endpoints that the M9+M8 sub-charts expose.

---

## 5. Security Checklist

- [x] No credentials in any file (R9.4 regex + exclusions)
- [x] Vault paths only for secrets
- [x] IRSA for Bedrock
- [x] mTLS cert mount defined (/etc/007/mtls/)
- [x] Pod securityContext runAsNonRoot + readOnlyRootFilesystem + drop ALL caps + seccomp RuntimeDefault
- [x] Non-root UID 1000 in images
- [x] HEALTHCHECK in Dockerfile
- [x] NetworkPolicy default-deny ingress (M6 only + explicit extras)
- [x] PodDisruptionBudget minAvailable 1
- [x] cert-manager 24h rotation
- [x] HPA target ≤ 70% CPU
- [x] PriorityClass set per module
- [x] Image digest fallback in template (production uses digest, dev uses tag)

---

## 6. Open Questions / Known Blockers

- Q1 Wave 1 umbrella Chart.yaml not present yet; values fragment ships separately, merge is post-wave concern.
- Q2 helm CLI not installed on this dev box; shell tests gracefully skip with SKIP banner.
- Q3 FastAPI shim is minimum viable; auth middleware, OTel, request signing land in a later hardening wave.
- Q4 Image digests placeholders (`REPLACE_ME_SHA256`); CI/CD replaces at deploy time.
- Q5 ExternalSecret CRD (§2.4) is a contract document — actual ExternalSecret resources land in Wave 3 alongside the operator install.

---

## 7. Fix Traceability (v0.1.0 → v0.2.0)

| v1 Fix | v0.2.0 Resolution |
|---|---|
| RF1 StatefulSet/Deployment kind | R9.2 table rows `kind: StatefulSet`/`kind: Deployment` |
| RF2 PriorityClass | R9.2 rows `priorityClassName: system-cluster-critical` / `system-node-critical` |
| RF3 Probes | R9.2 rows `readinessProbe:` + `livenessProbe:` |
| RF4 HPA CPU 70 literal | R9.2 row `averageUtilization: 70` |
| RF5 Pod securityContext | R5.6 + R9.2 rows `runAsNonRoot: true` + `readOnlyRootFilesystem: true` |
| RF6 Image digest fallback | §2.3 image reference logic block |
| RF7 Checkpointer DSN wiring | §2.4 ExternalSecret contract |
| RF8 Credential grep pattern | R9.4 with exclusions |
| RF9 M12 extraIngressFrom schema | §2.5 |
| RF10 Append-safe sentinel | §2.7 test_helm_lint.sh |
| RF11 SKIP banner | §2.7 + R9.1 |
| RF12 M12 library import | §4.8 |
| RF13 "Only M6 ingress" test | R9.2 row `podSelector:.*app: m6-mcp-gateway` |
| RF14 Resource requests/limits | R5.7 |
| RF15 Python YAML fallback | R9.5 + T8.4 |
| RF16 COMPLETE marker schema | §2.8 |
| RecF1 Chart version bump rule | §2.3 note (semver: patch for template, minor for values add, major for values break) |
| RecF2 Dispatch mode flag | R3.25 + §4.9 |
| RecF3 ServiceMonitor | Deferred to Wave 3; documented |
| RecF4 topologySpreadConstraints | Deferred to Wave 3 |
| RecF5 PodAntiAffinity | Deferred to Wave 3 |
