# ops-hardening-wave4-argocd-applicationset — COMPLETE

Spec: `.kiro/specs/ops-hardening-wave4-argocd-applicationset.md` (v2 GO 8.2/10).

## Artifacts shipped

| Path | Purpose |
|------|---------|
| `deploy/argocd/applicationset.yaml` | Git-directory-generator ApplicationSet (1 per tenant) |
| `deploy/argocd/README.md` | Onboarding + offboarding workflow |
| `config/tenants/example-tenant-tier4-ria/values.yaml` | Reference tenant values (Tier 4 RIA, cloud topology) |
| `deploy/tests/test_argocd_applicationset.sh` | 3-phase test (YAML contract + kubectl + helm dry-render) |

## Verification gates

- `bash deploy/tests/test_argocd_applicationset.sh` — **PASS**
  - Phase 1 (YAML contract): applicationset + example tenant
    validated (apiVersion, kind, generators, template source path,
    destination, syncPolicy {prune, selfHeal, allowEmpty:false}).
  - Phase 2 (kubectl dry-run): SKIPS on this machine (no kubeconfig;
    skip-graceful per AC7.3).
  - Phase 3 (helm dry-render): 2229 lines rendered cleanly using
    values-cloud.yaml + example-tenant-tier4-ria/values.yaml.
- Existing deploy tests unchanged — **PASS**.
- Python suite — **1994 passed** (no Python changes).

## Contract summary

- Single `ApplicationSet` in the `argocd` namespace.
- Git-directory generator over `config/tenants/*/` (excludes
  `.deprecated-*` for offboarding rename-first).
- One `Application` per tenant: name `007-fsi-<tenant-id>`,
  namespace = tenant id (Steering Rule 23), project `007-fsi`.
- `automated.prune: true`, `selfHeal: true`, `allowEmpty: false`
  (Rule 26 + prune safety).
- `CreateNamespace=true`, `PruneLast=true`, `ApplyOutOfSyncOnly=true`,
  `ServerSideApply=true`.
- `resources-finalizer.argocd.argoproj.io` on every generated
  Application (human must clear it before ArgoCD prunes the
  Application resource).
- Pinned `targetRevision: v0.5.0`. `HEAD` opt-in per tenant
  (`tenant.allowHead: true`).

## Deferred (per spec §4)

- Per-tenant ArgoCD Project (single shared project this wave).
- Per-tenant RBAC inside ArgoCD.
- SyncWave annotations on every template.
- Per-tenant `targetRevision` injection (currently shared pin).
