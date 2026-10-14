# Ops Hardening Wave 1 — Trust-Layer Deployment Artifacts

> Phase 1 B2 gate deliverable. Customer-GA blocker.
> Modules in scope: **M1** (Identity), **M2/M4** (Policy Engine), **M6** (MCP Gateway),
> **M10** (Audit Logger). No intelligence-layer modules, no compliance gap modules.
> Topology in scope: **cloud** only. Hybrid / on-prem are Phase 4.
> Source of truth: `docs/architecture/ARCH-04-v2-tech-stack-decisions.md`,
> `docs/architecture/ARCH-07-definitive-tech-stack.md`,
> `docs/architecture/ARCH-09-complete-module-map.md`,
> `docs/007-consolidated-design-and-plan.md`.
>
> **v2 rewrite notes (post LLMJ v1 CONDITIONAL GO 7.35/10).** All five
> critical issues (C1–C5) and all seven recommendations (R1–R7) are
> addressed. Fix traceability:
>
> | Review ID | Section that addresses it |
> |-----------|---------------------------|
> | C1 helm baseline    | §2.8 Tooling baselines |
> | C2 port contract    | §2.2 Service-port contract (rewrote: single listener 8080, Service maps 8443 → 8080) |
> | C3 ES CRD pin       | AC3.3 + §2.6 (pins `external-secrets.io/v1beta1`) |
> | C4 issuer pin       | AC3.2 + §2.3 (pins `certManager.issuerKind: ClusterIssuer`, `issuerName`) |
> | C5 test invariant   | AC6.1 (rewritten; exact existing-test preservation wording) |
> | R1 OCI labels       | AC2.8 (explicit label list + URL) |
> | R2 store name       | §2.6 + values-cloud.yaml default `vault-cluster-store` |
> | R3 Pod security     | AC3.9 (new) |
> | R4 HPA apiVersion   | AC3.4 (pins `autoscaling/v2`) |
> | R5 compose network  | AC4.4 (named `007-trust-layer`) |
> | R6 helm v4 warnings | §2.8 + umbrella Chart.yaml keywords/maintainers |
> | R7 rollback plan    | §2.9 (new) |
> | G1..G4              | §4 Out of Scope + inline notes |

---

## Section 1 — Requirements

The four trust-layer modules currently run only on developer laptops via
`PYTHONPATH=src python3 -m pytest ...`. This wave produces the minimum set of
deployment artifacts that lets the trust layer ship as a customer-GA cloud
workload against Steering Rules 20–27. No intelligence-layer work and no
code refactors beyond thin FastAPI wrappers required so Dockerfiles have an
entrypoint.

### R1. FastAPI service wrappers for M1 and M2/M4

M1 and M2/M4 currently export only in-process Python APIs. For containerised
deployment they need thin FastAPI surfaces mirroring the pattern already
shipped for M6 (`src/m6_mcp_gateway/app.py`) and M10 (`src/m10_audit_logger/app.py`).

Acceptance criteria:

- **AC1.1** `src/m1_identity/app.py` exports `create_app()` and a
  module-level `app: FastAPI` instance for `uvicorn` to import.
- **AC1.2** `src/m1_identity/app.py` routes:
  - `GET /health` → `{"status":"ok","version":<str>}` with status 200.
  - `GET /ready` → 200 when signing key material is loadable, 503 otherwise.
  - `POST /aid/verify` → body `{"token":<jwt>}`; on success 200 with a
    compact claim summary (sub, firm_id, exp, jti); on `InvalidAidError`
    401 with `{"error":{"reason":<frozen-vocab>}}`. No stack traces on
    the wire (Gateway Rule 9 parity).
- **AC1.3** `src/m2_m4_policy_engine/app.py` exports `create_app()` and
  a module-level `app: FastAPI`.
- **AC1.4** `src/m2_m4_policy_engine/app.py` routes:
  - `GET /health` → 200.
  - `GET /ready` → 200 after the rule registry has been loaded, 503 otherwise.
  - `POST /authority/check` → wraps `AuthorityPolicy.evaluate`. Body keys:
    `identity_claims` (dict, AID shape), `action`, `target`, `context`.
    On success returns the `PolicyDecision` as JSON. On malformed body
    returns 400 with a generic reason.
  - `POST /mnpi/filter` → wraps `MnpiPolicy.filter`. Body keys:
    `identity_claims`, `canonical_type`, `payload`, `strict`. On success
    returns the filtered payload. 400 on malformed body.
- **AC1.5** Neither app imports the stdlib `logging` module. Structured
  access logging goes to stdout via `sys.stdout.write` with only
  `{phase, method, path, status_code, latency_ms, trace_id}` — no bodies,
  no credentials, no MNPI.
- **AC1.6** Neither app reads credentials from config defaults or env-var
  fallbacks. Signing keys come only from `os.environ` at request time.
- **AC1.7** Each app exposes one uvicorn listener on port `8080` inside
  the container. mTLS terminates upstream in the service mesh: Kubernetes
  Services map external `port: 8443` → `targetPort: 8080`. Kubelet
  liveness/readiness probes hit the same `8080` inside the pod. (See
  §2.2 for the rationale — this single-listener contract fixes review
  finding C2.)
- **AC1.8** FastAPI app construction must not perform network calls at
  import time (otherwise `uvicorn --check-only` and image-build smoke
  tests break).

### R2. Dockerfiles — multi-stage, distroless-or-minimal, non-root

Four Dockerfiles at `deploy/docker/{m1-identity,m2-m4-policy-engine,m6-mcp-gateway,m10-audit-logger}/Dockerfile`.
`m6-mcp-gateway` and `m10-audit-logger` Dockerfiles already exist inside
their module directories — this wave **audits** them, lifts the family-
standard version into `deploy/docker/`, and keeps the in-source variants
untouched so the existing test wiring continues to work.

Acceptance criteria:

- **AC2.1** Every Dockerfile is multi-stage: a `builder` stage installs
  dependencies, a `runtime` stage carries only the application.
- **AC2.2** The runtime stage is based on `python:3.12-slim` (Debian
  slim is the project's agreed minimal-runtime base per
  `ARCH-07 §Infrastructure`). Distroless was evaluated and rejected for
  Phase 1: the python-distroless variants ship only a single CPython
  binary without `pip`, and an image-level HEALTHCHECK would need either
  `curl` (missing) or a Python one-liner. `python:3.12-slim` + `apt-get`
  cleanup in the same layer is the family standard that M6 + M10 already
  use (`src/m6_mcp_gateway/Dockerfile`).
- **AC2.3** Every Dockerfile ends with `USER 1000` (numeric UID) to satisfy
  the grep-gate `test_dockerfile_security.sh` (`USER root` forbidden).
- **AC2.4** Every Dockerfile defines a `HEALTHCHECK` hitting
  `http://localhost:8080/health` (the single container listener).
- **AC2.5** Every Dockerfile installs only pinned dependencies with upper
  bounds (`fastapi>=0.111,<1.0`, etc.) — no open-ended version ranges.
- **AC2.6** Every Dockerfile creates the mTLS mount path in the image:
  certificate at `/etc/007/mtls/tls.crt`, key at `/etc/007/mtls/tls.key`,
  CA bundle at `/etc/007/mtls/ca.crt`. The directory is owned by UID 1000
  so projected volume mounts land on a known owner.
- **AC2.7** Every Dockerfile creates the Vault token mount path at
  `/var/run/secrets/vault` (same UID 1000 ownership).
- **AC2.8** Every Dockerfile emits the core set of OCI image-spec
  annotations (see
  https://github.com/opencontainers/image-spec/blob/main/annotations.md):
  `org.opencontainers.image.title`, `org.opencontainers.image.version`,
  `org.opencontainers.image.source`, `org.opencontainers.image.licenses`,
  `org.opencontainers.image.vendor`. A grep-gate fails the build if
  `org.opencontainers.image.title` is missing from any of the four
  Dockerfiles.
- **AC2.9** No Dockerfile uses `ADD` with a URL (grep-gate).
- **AC2.10** No Dockerfile runs `apt-get upgrade` (unpinned rolling
  upgrade). `apt-get install --no-install-recommends` is allowed; the
  installed package list must be explicit and each install paired with
  `rm -rf /var/lib/apt/lists/*` in the same layer.
- **AC2.11** No Dockerfile contains credentials or references to
  credentials (`PASSWORD=`, `SECRET=`, `TOKEN=` = hardcoded value) —
  grep-gate.
- **AC2.12** `docker build` (or `finch build`) completes cleanly for all
  four Dockerfiles. Where full dependency resolution is impractical in
  the test environment, the test harness runs `docker build
  --target=builder --no-cache` so the `pip install` step is exercised
  without pulling the full runtime image. The TypeScript adapters are
  out of scope for this wave.

### R3. Helm umbrella chart `deploy/helm/007-fsi/`

One umbrella chart referencing four sub-charts. No values-hybrid,
values-onprem, or intelligence-layer sub-charts are produced in this wave
(Steering Rule 25 — cloud-only for this pass).

Acceptance criteria:

- **AC3.1** `deploy/helm/007-fsi/Chart.yaml` declares
  `apiVersion: v2`, chart name `007-fsi`, version `0.1.0`,
  appVersion `0.3.0`, four `dependencies:` entries pointing at the
  local sub-charts (`file://charts/m1-identity`, etc.), plus
  `keywords:`, `maintainers:`, and `description:` so helm v4 lint
  produces zero warnings.
- **AC3.2** `deploy/helm/007-fsi/values-cloud.yaml` is the only values
  file committed. It sets:
  - `global.topology: cloud`
  - `global.imageRegistry: <placeholder>` (documented placeholder, not
    a secret)
  - `global.tenantRoleArn: <placeholder>` (per-tenant IAM role)
  - `certManager.issuerName: letsencrypt-prod` (placeholder)
  - `certManager.issuerKind: ClusterIssuer`
  - `externalSecrets.storeName: vault-cluster-store`
  - per-module image tags (default `:latest` with
    `imagePullPolicy: Always`).
- **AC3.3** Each sub-chart (`charts/m1-identity`, `charts/m2-m4-policy-engine`,
  `charts/m6-mcp-gateway`, `charts/m10-audit-logger`) ships:
  - `Chart.yaml` (apiVersion v2, name, version `0.1.0`, appVersion `0.3.0`).
  - `values.yaml` (defaults: replicas, resources, image tag, ports).
  - `templates/_helpers.tpl` with a name/label block.
  - `templates/deployment.yaml` with a single container listener on
    `containerPort: 8080`, a `readinessProbe` and `livenessProbe` on
    `8080 /health`, mTLS cert volumes mounted at `/etc/007/mtls`, and
    Vault token volume at `/var/run/secrets/vault`.
  - `templates/service.yaml` (ClusterIP) mapping `port: 8443` →
    `targetPort: 8080` plus `port: 8080` → `targetPort: 8080` for probes
    from within the namespace.
  - `templates/serviceaccount.yaml` with a per-tenant KMS key annotation
    (`eks.amazonaws.com/role-arn` sourced from `global.tenantRoleArn`).
  - `templates/networkpolicy.yaml` — **default-deny ingress plus an
    explicit allow from M6 only** (for M1/M2-M4/M10). M6's own
    NetworkPolicy allows ingress from any pod labelled
    `app.kubernetes.io/part-of: 007-fsi` on the application port.
  - `templates/poddisruptionbudget.yaml` with `minAvailable: 1`.
  - `templates/certificate.yaml` — `cert-manager.io/v1` `Certificate`
    resource with `duration: 24h` and `renewBefore: 2h`
    (Steering Rule 21). IssuerRef uses
    `{kind: {{ .Values.certManager.issuerKind }},
      name: {{ .Values.certManager.issuerName }}}`.
  - `templates/externalsecret.yaml` — `external-secrets.io/v1beta1`
    `ExternalSecret` referencing the ClusterSecretStore
    `{{ .Values.externalSecrets.storeName }}` (Vault backend) and
    using the `secret/data/007/<module>/` path convention.
- **AC3.4** The M6 sub-chart additionally ships
  `templates/horizontalpodautoscaler.yaml` pinned to `autoscaling/v2`
  (M6 is the only horizontally-scaled service in this wave — M1, M2/M4,
  M10 are low-volume trust infrastructure with stable 2-replica
  baselines).
- **AC3.5** Every sub-chart's Deployment honours both image-pull-policy
  modes: for `:latest` dev tags `imagePullPolicy: Always`, for any
  pinned tag (regex `^sha256:` OR `^v\d` OR `@sha256:`)
  `imagePullPolicy: IfNotPresent`. The logic sits in `_helpers.tpl` and
  is driven by values.
- **AC3.6** No raw secrets appear in any values file, chart, or template.
  Secrets arrive only via ExternalSecret → Vault, referenced by name.
  Grep-gate: no `password:`, `apiKey:`, `token:` with a hardcoded value.
- **AC3.7** `helm lint` passes (exit 0) on the umbrella chart and on
  each of the four sub-charts.
- **AC3.8** `helm template -f values-cloud.yaml` renders without error.
  A grep over the rendered output shows: all four Deployments, all four
  Services with `port: 8443` + `targetPort: 8080`, all four
  NetworkPolicy objects, the cert-manager `Certificate` resources with
  `duration: 24h`, the ExternalSecret resources using `secret/data/007/`
  prefixes.
- **AC3.9** Every Deployment sets a restrictive Pod Security context:
  `securityContext` at pod level with `runAsNonRoot: true`,
  `runAsUser: 1000`, `runAsGroup: 1000`, `fsGroup: 1000`, and at
  container level with `allowPrivilegeEscalation: false`,
  `readOnlyRootFilesystem: true`, `capabilities.drop: [ALL]`,
  `seccompProfile.type: RuntimeDefault`. This aligns with Pod Security
  Admission `restricted` profile and lets cloud clusters admit the pod
  without exceptions.

### R4. docker-compose.yml for local development

`deploy/compose/docker-compose.yml` — one file, opinionated for laptop
dev.

Acceptance criteria:

- **AC4.1** Services: `vault-dev` (Vault 1.15 in dev mode, auto-unsealed),
  `postgres` (15-alpine, used by M8 checkpointer in later waves — shipped
  here to stabilise local ports), `m1-identity`, `m2-m4-policy-engine`,
  `m6-mcp-gateway`, `m10-audit-logger`.
- **AC4.2** Each module service uses `build: ../docker/<module>` so local
  `docker compose build` uses the same Dockerfiles as prod.
- **AC4.3** mTLS is disabled for local dev (`ENABLE_MTLS: "false"`).
  A `FAKE_SECRETS: "true"` env-var signals Vault dev-mode mode so the
  services skip production secret validation.
- **AC4.4** Container-to-container networking uses a named compose
  network `007-trust-layer` (bridge driver). No host-network mode. The
  named network makes the compose file stackable with future waves
  without port-scope collisions.
- **AC4.5** No credentials in the compose file. Vault dev root token is
  set to `dev-only-root` via env-var `VAULT_DEV_ROOT_TOKEN_ID`, which is
  explicitly called out as "local-dev only — never used in prod" in a
  header comment and is safe because Vault is launched with `-dev` and
  listens on the compose network only (not host-network).
- **AC4.6** All four module services have `healthcheck:` pointing at
  `http://localhost:8080/health`.

### R5. Deploy-layer tests

Three shell scripts at `deploy/tests/`:

- **AC5.1** `test_helm_lint.sh` runs `helm lint` on the umbrella chart
  plus each of the four sub-charts individually. Exits non-zero if any
  lint fails. Exits with a skip message (exit 0) if `helm` is not on PATH,
  so CI jobs without Kubernetes tooling still pass — the Python suite
  covers Python-level invariants separately.
- **AC5.2** `test_helm_template.sh` runs `helm template -f values-cloud.yaml`
  then greps for: four `Deployment`s, four `Service`s each with
  `port: 8443` and `targetPort: 8080`, four `NetworkPolicy`s with
  default-deny-ingress shape, four `Certificate`s with `duration: 24h`,
  four `ExternalSecret`s using `secret/data/007/`. Exits non-zero on
  any grep miss.
- **AC5.3** `test_dockerfile_security.sh` greps each of the four
  `deploy/docker/*/Dockerfile` files for forbidden patterns:
  - `^USER +root\b` → fail
  - `^ADD +https?://` → fail
  - `apt-get +upgrade` (unpinned rolling upgrade) → fail
  - Required: at least one `org.opencontainers.image.title` label.
  - Required: at least one `USER ` directive with a numeric UID.
  - Required: at least one `HEALTHCHECK ` directive.
  Exits non-zero on any violation.
- **AC5.4** All three scripts start with `set -euo pipefail` and a usage
  comment. They are `chmod +x`-ed. They are path-resilient: the first
  executable line is `cd "$(dirname "$0")/.."` so the script works from
  any cwd.

### R6. Test-suite regression invariant

- **AC6.1** Every test that exists in the suite before this wave
  (1707 passed + 4 skipped + 5 xfailed + 1 xpassed as reported by
  `PYTHONPATH=src python3 -m pytest tests/ -q --timeout=60`) remains in
  the same pytest status after the wave. No existing test is flipped
  to skipped / xfailed, no existing test is deleted. New tests may be
  added only if they pass and only in `tests/unit/deploy/` (this wave
  does not add any — the deploy surface is validated by the three shell
  scripts in `deploy/tests/`).
- **AC6.2** Added FastAPI wrappers do not break the existing in-process
  import pattern. `from m1_identity import IdentityService` and
  `from m2_m4_policy_engine import AuthorityPolicy` continue to work
  without any transitive FastAPI import.

### R7. Grep-gate verification invariants

- **AC7.1** `grep -RIn "password\|apiKey\|BEGIN RSA\|BEGIN PRIVATE KEY" deploy/` returns no hits.
- **AC7.2** Every Dockerfile contains exactly one `USER` line and it is `USER 1000`.
- **AC7.3** Every sub-chart has a `NetworkPolicy` template with at least
  one rule matching `from: []` (default-deny) **or** with a named allow
  rule targeting only `app.kubernetes.io/name: m6-mcp-gateway`.
- **AC7.4** All four `Certificate` templates contain literally
  `duration: 24h` and `renewBefore: 2h`.
- **AC7.5** All four `ExternalSecret` templates contain a `remoteRef.key`
  matching `^secret/data/007/`.
- **AC7.6** All four Deployments contain both `readinessProbe` and
  `livenessProbe` wired to path `/health` on port `8080`.

---

## Section 2 — Design

### 2.1 Directory layout

```
my-agent-project-007-fsi-interoperability/
├─ .kiro/specs/
│  ├─ ops-hardening-wave1-trust-layer.md                    (this spec)
│  ├─ ops-hardening-wave1-trust-layer-REVIEW.md             (step 2)
│  ├─ ops-hardening-wave1-trust-layer-REVIEW-v2.md          (step 4)
│  └─ ops-hardening-wave1-COMPLETE.md                       (step 7)
├─ src/
│  ├─ m1_identity/
│  │  └─ app.py                                             (new, R1)
│  └─ m2_m4_policy_engine/
│     └─ app.py                                             (new, R1)
└─ deploy/
   ├─ docker/
   │  ├─ m1-identity/Dockerfile
   │  ├─ m2-m4-policy-engine/Dockerfile
   │  ├─ m6-mcp-gateway/Dockerfile                          (audited copy, single 8080 listener)
   │  └─ m10-audit-logger/Dockerfile                        (audited copy, single 8080 listener)
   ├─ helm/
   │  └─ 007-fsi/
   │     ├─ Chart.yaml
   │     ├─ values-cloud.yaml
   │     ├─ .helmignore
   │     └─ charts/
   │        ├─ m1-identity/
   │        │  ├─ Chart.yaml
   │        │  ├─ values.yaml
   │        │  └─ templates/
   │        │     ├─ _helpers.tpl
   │        │     ├─ deployment.yaml
   │        │     ├─ service.yaml
   │        │     ├─ serviceaccount.yaml
   │        │     ├─ networkpolicy.yaml
   │        │     ├─ poddisruptionbudget.yaml
   │        │     ├─ certificate.yaml
   │        │     └─ externalsecret.yaml
   │        ├─ m2-m4-policy-engine/                         (same 8 template files)
   │        ├─ m6-mcp-gateway/                              (+ horizontalpodautoscaler.yaml)
   │        └─ m10-audit-logger/                            (same 8 template files)
   ├─ compose/
   │  └─ docker-compose.yml
   └─ tests/
      ├─ test_helm_lint.sh
      ├─ test_helm_template.sh
      └─ test_dockerfile_security.sh
```

### 2.2 Service-port contract (rewritten — fixes review C2)

The container exposes exactly **one** listener: `0.0.0.0:8080`. Both
application traffic and liveness/readiness probes land on this port.
mTLS terminates upstream in the service mesh. Kubernetes Services
expose two ports externally:

| Service port | Target port | Purpose |
|-------------:|------------:|---------|
| 8443         | 8080        | mTLS-terminated application ingress |
| 8080         | 8080        | Kubelet / in-cluster probes |

Kubelet probes use the `probe` port (`8080 → 8080`). In-cluster callers
(e.g. M6 → M1) use the `app` port (`8443 → 8080`) which routes through
the mesh sidecar. This matches the existing in-source M6 + M10 Dockerfile
pattern (single uvicorn listener) and requires no entrypoint script.

### 2.3 mTLS + secret mount contract

- Cert: `/etc/007/mtls/tls.crt` (0644, owner 1000:1000)
- Key:  `/etc/007/mtls/tls.key` (0400, owner 1000:1000)
- CA:   `/etc/007/mtls/ca.crt`  (0644, owner 1000:1000)
- Vault token: `/var/run/secrets/vault/token` (0400, owner 1000:1000)

Mount points are read-only in all Deployments. cert-manager renders the
cert+key into a K8s Secret; a projected volume mounts it at the path
above. `values-cloud.yaml` pins `certManager.issuerKind: ClusterIssuer`
and `certManager.issuerName: letsencrypt-prod` as placeholders that
per-tenant overlays override.

### 2.4 NetworkPolicy topology

```
client ----> [M6-gateway] ----> [M1-identity]
                           \--> [M2-M4-policy-engine]
                           \--> [M10-audit-logger]
```

Only M6 receives ingress from outside the trust-layer namespace (via the
service mesh). M1, M2/M4, M10 each accept ingress **only** from pods
labelled `app.kubernetes.io/name: m6-mcp-gateway` on port 8080, and from
the kubelet for probes on 8080. Default-deny ingress on all four.

Egress: M6 needs egress to M1, M2/M4, M10, Redis, and downstream vendor
MCPs (outside the cluster). M1/M2-M4/M10 need egress to their backends
(Keycloak/Postgres, S3, Langfuse). Per-module egress rules are modelled
but use `{}` (allow-all egress) in this wave's values-cloud.yaml; the
follow-up wave on egress hardening narrows them. Documented explicitly
so it shows up in audits.

### 2.5 Per-tenant KMS key reference

The ServiceAccount templates carry an annotation
`eks.amazonaws.com/role-arn: "{{ .Values.global.tenantRoleArn }}"`. The
IAM role under that ARN owns a per-tenant KMS CMK (Steering Rule 23).
The Helm chart does not create the IAM role or KMS key — those are
Terraformed per-tenant — but it documents the annotation pattern so
every pod running under the chart assumes the right role. A comment in
values-cloud.yaml calls out that `global.tenantRoleArn` must be set per
tenant.

### 2.6 ExternalSecrets pattern (pinned CRD)

Every module reads its secrets via a single `ExternalSecret` referencing
the cluster-wide `ClusterSecretStore` named
`{{ .Values.externalSecrets.storeName }}` (default `vault-cluster-store`).
API version pinned to `external-secrets.io/v1beta1`.

Vault path convention:

```
secret/data/007/m1-identity/signing
secret/data/007/m2-m4-policy-engine/opa-auth
secret/data/007/m6-mcp-gateway/redis-auth
secret/data/007/m10-audit-logger/s3-writer
```

The ExternalSecret writes into a K8s Secret of the same name as the
Deployment, which the Deployment mounts as env vars (never as files,
never logged).

### 2.7 Security posture summary

| Control                 | Where | Rule |
|-------------------------|-------|------|
| Non-root container       | Dockerfile `USER 1000` | Steering Rule 22 |
| Pod Security `restricted` | Deployment `securityContext` (AC3.9) | Rule 22 |
| mTLS, 24h rotation       | Certificate template (AC3.3) | Rule 21 |
| Private subnet only      | NetworkPolicy default-deny ingress | Rule 22 |
| Per-tenant KMS           | ServiceAccount annotation | Rule 23 |
| Namespace isolation      | Chart installs into per-tenant namespace via values | Rule 23 |
| NetworkPolicy per module | Each sub-chart ships its own | Rule 23 |
| No credentials in git    | ExternalSecrets → Vault | Rule 20 |

### 2.8 Tooling baselines (new — fixes review C1, R6)

- `helm lint` baseline: **helm ≥ 3.14**. Helm 4.x (4.1.4 tested locally)
  is supported but its stricter warnings are informational, not
  blocking. The in-scope sub-charts lint clean under both.
- `kubectl` API versions referenced in templates:
  - `apps/v1` (Deployment)
  - `v1` (Service, ServiceAccount)
  - `networking.k8s.io/v1` (NetworkPolicy)
  - `policy/v1` (PodDisruptionBudget)
  - `autoscaling/v2` (HorizontalPodAutoscaler)
  - `cert-manager.io/v1` (Certificate)
  - `external-secrets.io/v1beta1` (ExternalSecret, ClusterSecretStore)

### 2.9 Rollback plan (new — fixes review R7)

If a Dockerfile or sub-chart ships broken:

- The in-source Dockerfiles (`src/m6_mcp_gateway/Dockerfile`,
  `src/m10_audit_logger/Dockerfile`) remain authoritative for laptop
  dev. Reverting a broken `deploy/docker/*` file restores the deploy
  layer without touching module code.
- The umbrella chart and each sub-chart are versioned independently
  (`0.1.0` initial). A broken sub-chart can be rolled back via ArgoCD
  by pinning to the previous chart version; the other three sub-charts
  continue to reconcile.
- No schema migrations. No stateful backends updated. Rollback is
  strictly a redeploy.

---

## Section 3 — Tasks

All tasks are atomic. Each task is considered done when its AC set is
covered by a passing test.

### Task 3.1 — Minimal FastAPI wrappers for M1 and M2/M4
Produces `src/m1_identity/app.py` and `src/m2_m4_policy_engine/app.py`.
Covers R1 (AC1.1–AC1.8). Verified by running the existing test suite
(must stay green) plus the new `/health` + `/ready` probe stubs.

### Task 3.2 — deploy/docker Dockerfiles
Produces four Dockerfiles at `deploy/docker/<module>/Dockerfile`. For
M6 and M10, the in-source Dockerfiles remain as-is; the deploy variant is
lifted, fixed for the single-listener 8080 contract, and documented as
the canonical one. Covers R2 (AC2.1–AC2.12).

### Task 3.3 — Helm umbrella + four sub-charts
Produces the tree under `deploy/helm/007-fsi/`. Covers R3 (AC3.1–AC3.9).

### Task 3.4 — docker-compose
Produces `deploy/compose/docker-compose.yml`. Covers R4 (AC4.1–AC4.6).

### Task 3.5 — Deploy-layer shell tests
Produces the three scripts under `deploy/tests/`. Covers R5 (AC5.1–AC5.4).

### Task 3.6 — Regression + grep gates
Runs the full Python suite (R6) and the three deploy-layer scripts (R7).
Covers R6 + R7.

### Task 3.7 — 10/10 stress run + COMPLETE marker
Runs the full Python suite ten times sequentially to confirm stability
(no flake). Writes `.kiro/specs/ops-hardening-wave1-COMPLETE.md` with
LOC totals, file paths, LLMJ score, and the 10/10 evidence.

---

## Section 4 — Out of Scope (explicit)

- M7, M8, M9, M11, M12, M13 ops artifacts. Separate wave.
- Compliance gap modules (gap1..gap7) — consumed by M2/M4 at runtime,
  no standalone Deployments.
- `values-hybrid.yaml` and `values-onprem.yaml` — Phase 4. This wave
  does NOT ship empty placeholder files (silent grep-gate misses).
- ArgoCD ApplicationSets — separate wave.
- Egress hardening (narrowing NetworkPolicy egress) — separate wave.
- Full OPA sidecar wiring to M2/M4 — the M2/M4 engine runs Python-only
  in Phase 1 per the spec.
- Actual per-tenant IAM/KMS Terraform. The chart documents the
  annotation pattern; infra is provisioned upstream.
- A `tests/unit/deploy/` pytest suite (note from review G1). Deferred:
  the deploy surface in this wave is validated by the three shell
  scripts in `deploy/tests/` and by the Python-suite regression
  invariant AC6.1.

---

*ops-hardening-wave1-trust-layer.md — Project 007 FSI Interoperability Platform*
*v2 (post LLMJ v1 fix).*
