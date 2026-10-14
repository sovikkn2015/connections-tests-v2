# ArgoCD ApplicationSet — Per-Tenant Rollout

Wave 4 deliverable. Spec: `.kiro/specs/ops-hardening-wave4-argocd-applicationset.md`.

## What this is

A single `ApplicationSet` resource (`applicationset.yaml`) that uses a
git-directory generator to iterate over `config/tenants/*/` and
provision one ArgoCD `Application` per tenant. GitOps per Steering
Rule 26.

## Onboarding a new tenant (5 steps)

1. Clone the infra repo.
2. Copy the example tenant directory:
   ```bash
   cp -r config/tenants/example-tenant-tier4-ria config/tenants/<tenant-id>
   ```
3. Edit `config/tenants/<tenant-id>/values.yaml`:
   - Replace every `REPLACE_ME` placeholder.
   - Set IAM role ARN, domain, KMS key ARN.
   - Select topology (`tenant.topologyFile: values-cloud.yaml` or
     `values-hybrid.yaml`).
   - Toggle feature flags (which sub-charts, which specialists).
4. Open a PR. CI runs `test_argocd_applicationset.sh` (YAML schema
   + helm dry-run).
5. Merge. ArgoCD ApplicationSet generator discovers the new
   directory on next poll (<3 minutes default) and creates the
   `Application` with `007-fsi-<tenant-id>` name in the `argocd`
   namespace, targeting namespace `<tenant-id>` in the target
   cluster.

## Offboarding a tenant (rename-first)

Direct deletion of a tenant values directory is DANGEROUS: the
generator will stop emitting the Application and `automated.prune:
true` will begin deleting every resource in the tenant namespace.
If the directory removal was a mistake, there is no window to
recover.

Safe workflow:

1. Rename the directory to add a `.deprecated-` prefix:
   ```bash
   git mv config/tenants/<tenant-id> config/tenants/.deprecated-<tenant-id>
   ```
2. Commit + push. The ApplicationSet's `exclude: true` rule on the
   `.deprecated-*` path drops the Application from the generated list.
3. ArgoCD removes the Application resource itself (the
   `resources-finalizer` on the Application requires a human to
   remove it first if you want to preserve the backing resources).
4. Manually inspect the target cluster to confirm prune worked as
   expected.
5. THEN delete the `.deprecated-<tenant-id>` directory in a
   separate commit.

## targetRevision pinning

The ApplicationSet pins `targetRevision: v0.5.0`. Tenants who need a
different version:

- Preferred: wait for the next platform release and upgrade in
  lockstep with all tenants.
- Emergency: override the ApplicationSet's `spec.template.spec.source.
  targetRevision` directly (requires platform-team approval).

Per-tenant `targetRevision` is a Wave-4 follow-up.

## SyncWave ordering

ArgoCD's built-in ordering is sufficient for Wave 4:

1. Namespaces (CreateNamespace=true creates them first).
2. CRDs + ExternalSecret resources.
3. Secrets (synced from Vault via ExternalSecrets Operator).
4. cert-manager Certificates.
5. Deployments / StatefulSets / Services.
6. NetworkPolicies / PDBs / HPAs.

Explicit `argocd.argoproj.io/sync-wave` annotations on individual
resources are a follow-up wave. They would tighten the guarantees but
are not required for the baseline.

## Drift detection

`automated.selfHeal: true` auto-corrects drift. `allowEmpty: false`
prevents accidental full-prune. `ignoreDifferences: []` means all
drift on all resources is flagged (including ExternalSecret,
Certificate, NetworkPolicy).

## Single ArgoCD Project

All tenants share the `007-fsi` ArgoCD Project. Per-tenant RBAC
inside ArgoCD is a follow-up; for Wave 4, RBAC is enforced downstream
in target-cluster namespaces (Kubernetes RoleBindings + per-tenant
IAM role ARN via IRSA).

## Tests

`deploy/tests/test_argocd_applicationset.sh` asserts:

- `applicationset.yaml` is parseable YAML.
- Example tenant values file renders the umbrella chart cleanly
  (helm dry-run).
- `kubectl --dry-run=client --validate=true` passes on the
  ApplicationSet if kubectl is on PATH.
- `argocd appset render` passes if the argocd CLI is installed.

Skips gracefully if neither tool is available.
