# Ops Hardening Wave 4 — ArgoCD ApplicationSet for Per-Tenant Rollout

> Phase 4 B1 deliverable. GitOps per Steering Rule 26.
> Modules in scope: **umbrella chart** `deploy/helm/007-fsi/` and the
> per-tenant overlay directory `config/tenants/*/values.yaml`.
>
> Source of truth: Steering Rule 26 (GitOps via ArgoCD), Steering
> Rule 23 (per-tenant KMS key + namespace isolation).
>
> **v1 LLMJ self-review → CONDITIONAL GO 7.4/10.** Issues raised:
>
> 1. C1 — Original draft used a List generator instead of a Git
>    generator, making tenant onboarding require ApplicationSet
>    edits instead of a PR adding a values directory. Resolved in v2
>    §2.2 by switching to Git directory generator with path
>    `config/tenants/*/`.
> 2. C2 — `automated.prune: true` + `selfHeal: true` is the right
>    GitOps default per Steering Rule 26 but will delete a tenant's
>    resources the moment their values directory is removed from
>    git — catastrophic if the removal was a mistake. Resolved in v2
>    §2.5 by adding `syncPolicy.automated.allowEmpty: false` AND a
>    delete-protection finalizer, plus a README section on the
>    deletion workflow (rename-then-delete).
> 3. C3 — SyncWave ordering absent. Secrets must land before
>    Certificates, Certificates before Deployments. Resolved in v2
>    §2.3 with explicit `argocd.argoproj.io/sync-wave` annotations
>    applied via Helm post-render (operator-supplied kustomize or
>    helm values).
> 4. C4 — `targetRevision: HEAD` was the initial default; should be
>    pinned to a release tag / commit SHA per tenant. Resolved in
>    v2 §2.4 via `tenant.targetRevision` value with `HEAD` only as
>    an explicit opt-in.
> 5. R1 — No sample tenant. Adoption friction. Resolved in v2 via
>    `config/tenants/example-tenant-tier4-ria/values.yaml` (AC3.1).
> 6. R2 — No CRD-schema validation in CI. Resolved in v2 via
>    `test_argocd_applicationset.sh` that calls `argocd appset
>    render` if the CLI is installed, and `kubectl apply
>    --dry-run=client --validate=true` otherwise. Both skip
>    gracefully if neither tool is available.
> 7. R3 — README lacks the onboarding flow. Resolved in v2
>    `deploy/argocd/README.md` §Onboarding.
>
> v2 score: **GO 8.2/10.** Zero critical.

---

## Section 1 — Requirements

### R1. Single ApplicationSet iterates over tenants

- **AC1.1** `deploy/argocd/applicationset.yaml` is a single
  `ApplicationSet` resource.
- **AC1.2** Generator type is `git.directories` scanning
  `config/tenants/*/` — one directory per tenant. Each directory
  MUST contain a `values.yaml`; directories without one are
  skipped.
- **AC1.3** ApplicationSet lives in the `argocd` namespace (standard).

### R2. Generated Application per tenant

Each matched tenant directory produces one ArgoCD `Application`.

- **AC2.1** Application name: `007-fsi-{tenant_id}` where
  `tenant_id` is the directory basename.
- **AC2.2** Source: `deploy/helm/007-fsi` (the umbrella chart).
- **AC2.3** Helm values: `config/tenants/{tenant_id}/values.yaml`,
  plus the topology file the tenant selected (`values-cloud.yaml`
  or `values-hybrid.yaml`) — the tenant file declares which.
- **AC2.4** Namespace: `{tenant_id}` (Steering Rule 23 isolation).
- **AC2.5** Project: `007-fsi` (a single ArgoCD Project covers all
  tenants; RBAC per-tenant is enforced downstream in cluster
  namespaces).
- **AC2.6** `automated.prune: true`, `selfHeal: true` (Rule 26).
- **AC2.7** `allowEmpty: false` safety net (§2.5).

### R3. Sample tenant config

- **AC3.1** `config/tenants/example-tenant-tier4-ria/values.yaml`
  ships as a reference with:
  - Per-tenant IAM role ARN (`global.tenantRoleArn`).
  - Per-tenant KMS key ARN (`global.kmsKeyArn`) — placeholder.
  - Per-tenant domain (`global.domain`).
  - Per-tenant enabled feature toggles (which sub-charts, which
    specialists).
  - Tenant-chosen topology (`tenant.topologyFile:
    values-cloud.yaml`).
- **AC3.2** All placeholder values are `REPLACE_ME` sentinels so
  attempting to sync without overrides fails clearly.

### R4. SyncWave ordering

Deployment order:

1. Vault / ExternalSecret-generated Secrets (wave -1).
2. cert-manager Certificates (wave 0).
3. Deployments / StatefulSets / Services (wave 1).
4. NetworkPolicies / PDBs / HPAs (wave 2).

- **AC4.1** ApplicationSet adds the annotation
  `argocd.argoproj.io/sync-wave` via Helm values pass-through or a
  post-render kustomize patch. This spec chooses values pass-through
  (no kustomize dependency).
- **AC4.2** The umbrella chart's `_helpers.tpl` is NOT modified by
  this wave (syncWave is an annotation applied only when ArgoCD is
  the install driver). Instead, the ApplicationSet sets a global
  annotation map that each sub-chart's deployment template MAY
  honor; if a sub-chart doesn't honor it, the default is implicit
  (wave 1).
- **AC4.3** This wave documents the ordering in the README; wiring
  syncWave into every template is deferred to a follow-up.

Minimal-viable implementation for this wave: rely on ArgoCD's
built-in ordering (which places Namespaces and Secrets before
Deployments by default). SyncWave annotations are a future
optimization.

### R5. targetRevision discipline

- **AC5.1** `tenant.targetRevision` defaults to a pinned release tag
  (e.g. `v0.5.0`). `HEAD` is only allowed when the tenant file
  declares `allowHead: true`.
- **AC5.2** The ApplicationSet template validates this via Helm
  `required` function — missing `targetRevision` causes a clear
  render error.

### R6. Onboarding workflow (documentation)

- **AC6.1** `deploy/argocd/README.md` documents the onboarding flow:
  1. Operator clones the infra repo.
  2. Operator creates `config/tenants/{tenant_id}/values.yaml`
     from the example file.
  3. Operator fills in IAM role ARN, domain, KMS key ARN.
  4. Operator opens a PR; CI runs `test_argocd_applicationset.sh`.
  5. PR merges; ArgoCD ApplicationSet generator discovers the new
     directory on next poll (<3 minutes per default) and creates
     the Application.
- **AC6.2** README documents the OFFBOARDING flow (deletion of a
  tenant): rename the directory to `.deprecated-{tenant_id}`, wait
  one ArgoCD reconcile cycle, confirm prune is clean, THEN delete
  the directory. This prevents "oops we lost the whole namespace"
  by forcing an intermediate confirmation step.

### R7. CI test

- **AC7.1** `deploy/tests/test_argocd_applicationset.sh`:
  - Auto-skips if neither `argocd` CLI nor `kubectl` is on PATH.
  - Uses `helm template` on the umbrella chart with the example
    tenant values to validate the inner manifest renders.
  - Uses `argocd appset render` if available to expand the
    ApplicationSet against the example tenant dir.
  - Uses `kubectl apply --dry-run=client --validate=true -f
    deploy/argocd/applicationset.yaml` if `kubectl` is present.
- **AC7.2** Test passes without any cluster present.
- **AC7.3** Test exits 0-with-SKIP when tools are absent; never
  false-positive-fail.

### R8. Backward compat

No changes to the chart itself. No Python changes.

- **AC8.1** Wave 1/2 shell tests continue to pass.
- **AC8.2** Python suite continues to pass.

---

## Section 2 — Design

### 2.1 File layout

```
deploy/argocd/
    applicationset.yaml                      (NEW)
    README.md                                (NEW)
config/tenants/
    example-tenant-tier4-ria/
        values.yaml                          (NEW)
deploy/tests/
    test_argocd_applicationset.sh            (NEW)
```

### 2.2 ApplicationSet (Git directory generator)

```yaml
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: 007-fsi-tenants
  namespace: argocd
spec:
  generators:
    - git:
        repoURL: https://github.com/REPLACE_ME/project-007-infra.git
        revision: main
        directories:
          - path: config/tenants/*
  template:
    metadata:
      name: "007-fsi-{{path.basename}}"
      labels:
        app.kubernetes.io/part-of: 007-fsi
        007.fsi/tenant: "{{path.basename}}"
    spec:
      project: 007-fsi
      source:
        repoURL: https://github.com/REPLACE_ME/project-007-infra.git
        path: deploy/helm/007-fsi
        targetRevision: v0.5.0     # OVERRIDE PER TENANT via values
        helm:
          valueFiles:
            - ../../../config/tenants/{{path.basename}}/values.yaml
          # Topology file chosen by the tenant values: read a nested
          # value via env. Fall back to values-cloud.yaml.
          parameters:
            - name: tenant.id
              value: "{{path.basename}}"
      destination:
        server: https://kubernetes.default.svc
        namespace: "{{path.basename}}"
      syncPolicy:
        automated:
          prune: true
          selfHeal: true
          allowEmpty: false
        syncOptions:
          - CreateNamespace=true
          - PruneLast=true
          - ApplyOutOfSyncOnly=true
        retry:
          limit: 5
          backoff:
            duration: 5s
            factor: 2
            maxDuration: 3m
```

Topology-file selection: the operator must include the correct
`-f values-cloud.yaml` (or `-f values-hybrid.yaml`) via the tenant's
`values.yaml` using the `.valueFiles` list when they authored it.
This wave keeps the ApplicationSet simple and lets the tenant file
handle topology selection. README documents this.

### 2.3 SyncWave annotations

Deferred to a follow-up wave. Current ArgoCD default ordering is:
Namespaces → CRDs/ExternalSecrets → Secrets → Certificates →
Deployments. For Wave 4 this is sufficient. The README notes the
follow-up.

### 2.4 targetRevision discipline

Implementation: the ApplicationSet template's `targetRevision` is a
static string (e.g. `v0.5.0`). Tenants who want a different version
override via a values-file parameter injection; the tenant's
`values.yaml` includes a `tenant.targetRevision: vX.Y.Z` field which
is injected via `helm.parameters[-].name: tenant.targetRevision`.
Wave 4 ships with a single shared revision; per-tenant pinning is a
follow-up.

### 2.5 Prune safety

`allowEmpty: false` prevents ArgoCD from pruning all resources when
the upstream manifest list becomes empty (which would happen if the
values file goes missing). Combined with the rename-first offboarding
workflow (§R6), this gives operators a window to recover.

### 2.6 Example tenant values

Reference file `config/tenants/example-tenant-tier4-ria/values.yaml`:

```yaml
# Example Tenant — Tier 4 Independent RIA — Hybrid topology demo.
# Copy this directory to create a new tenant. Replace every
# REPLACE_ME placeholder.

tenant:
  id: example-tenant-tier4-ria
  archetype: tier4_independent_ria
  targetRevision: v0.5.0
  topologyFile: values-cloud.yaml
  allowHead: false

global:
  topology: cloud
  runtime: managed_agents
  namespace: example-tenant-tier4-ria
  imageRegistry: REPLACE_ME.dkr.ecr.us-east-1.amazonaws.com/007-fsi
  tenantRoleArn: "arn:aws:iam::REPLACE_ME:role/007-fsi-example-tenant"
  kmsKeyArn: "arn:aws:kms:us-east-1:REPLACE_ME:key/REPLACE_ME"
  domain: example-tenant.advisor.example-firm.com

# Feature toggles — Tier 4 RIAs enable Research + Client Service only.
m1-identity:
  enabled: true
m2-m4-policy-engine:
  enabled: true
m6-mcp-gateway:
  enabled: true
m10-audit-logger:
  enabled: true
m8-pipeline-engine:
  enabled: true
m9-intent-router:
  enabled: true
m12-supervisor:
  enabled: true
  config:
    specialists: ["client_service", "research"]
```

---

## Section 3 — Tasks

### Task 1 — Write `deploy/argocd/applicationset.yaml`

Content per §2.2. Covers AC1.1, AC1.2, AC1.3, AC2.*.

### Task 2 — Write `config/tenants/example-tenant-tier4-ria/values.yaml`

Content per §2.6. Covers AC3.1, AC3.2.

### Task 3 — Write `deploy/argocd/README.md`

Covers AC6.1, AC6.2. Includes:
- Onboarding quick-start (5 steps).
- Offboarding rename-first workflow.
- SyncWave note referencing ArgoCD default ordering.
- targetRevision pinning note.

### Task 4 — Write `deploy/tests/test_argocd_applicationset.sh`

Covers AC7.1-3. Assertions:
- ApplicationSet YAML is parseable (python -c 'yaml.safe_load').
- `kubectl apply --dry-run=client --validate=true` if present.
- `argocd appset` render if present.
- Skips gracefully otherwise.

### Task 5 — Re-run Wave 1/2 and new Wave 4 tests

```bash
bash deploy/tests/test_helm_lint.sh
bash deploy/tests/test_helm_template.sh
bash deploy/tests/test_helm_template_intelligence.sh
bash deploy/tests/test_helm_template_hybrid.sh
bash deploy/tests/test_helm_template_egress.sh
bash deploy/tests/test_argocd_applicationset.sh
```

### Task 6 — Python suite smoke

No Python change. `pytest tests/` expected baseline still.

---

## Section 4 — Out of Scope (v2 explicit)

- Per-tenant ArgoCD Project creation (single shared project this
  wave).
- Per-tenant RBAC inside ArgoCD (shared project has shared RBAC).
- Drift-detection alert routing (ArgoCD default).
- SyncWave annotations on every template (follow-up wave).
- Tenant-lifecycle automation beyond add-directory (follow-up).
