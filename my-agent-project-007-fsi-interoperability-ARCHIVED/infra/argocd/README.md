# ArgoCD Deployment — Project 007 FSI Platform

## Prerequisites

1. ArgoCD installed in the target cluster (`argocd` namespace)
2. Git repository credentials configured in ArgoCD
3. Target namespace `fsi-007` will be auto-created via `CreateNamespace=true`

## Usage

```bash
# Apply the ArgoCD Application manifest
kubectl apply -f application.yaml

# Verify sync status
argocd app get 007-fsi-platform
```

## Topology Overrides

Edit `application.yaml` to switch topology:

| Topology | valueFiles |
|----------|-----------|
| Cloud (default) | `values.yaml`, `values-cloud.yaml` |
| Hybrid / on-prem | `values.yaml`, `values-hybrid.yaml` |

## Sync Policy

- Automated sync with `prune: true` and `selfHeal: true`
- Retry: 5 attempts with exponential backoff (5s → 3m)
- Server-side apply enabled for large CRD manifests

## Notes

- Replace `<REPO_URL>` in `application.yaml` with your actual Git repository URL
- No credentials are stored in manifests — configure repo access via ArgoCD CLI or UI
- mTLS is controlled by `tls.enabled` in Helm values (default `false` for cloud, `true` for hybrid)
