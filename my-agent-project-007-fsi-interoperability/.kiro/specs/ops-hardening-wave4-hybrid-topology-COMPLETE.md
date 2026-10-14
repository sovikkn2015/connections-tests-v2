# ops-hardening-wave4-hybrid-topology — COMPLETE

Spec: `.kiro/specs/ops-hardening-wave4-hybrid-topology.md` (v2 GO 8.3/10).

## Artifacts shipped

| Path | Purpose |
|------|---------|
| `deploy/helm/007-fsi/values-hybrid.yaml` | Hybrid-topology overlay |
| `deploy/helm/007-fsi/VALUES-HYBRID-README.md` | Operator guide |
| `deploy/tests/test_helm_template_hybrid.sh` | Contract test + helm-rendered assertions |

## Verification gates

- `bash deploy/tests/test_helm_template_hybrid.sh` — **PASS**
  - YAML contract ON (topology=hybrid, runtime=strands_sdk, onPrem,
    adapters list, M6 egress allowlist with the on-prem ingest FQDN).
  - helm template: 2205 lines rendered.
  - 4 trust-layer Deployments + 1 StatefulSet (M8) + 2 intelligence
    Deployments (M9, M12).
  - No `m7-*` / `m11-*` resources rendered cloud-side.
  - On-prem adapter ingest FQDN appears in M6 NetworkPolicy egress.
- `bash deploy/tests/test_helm_template.sh` (Wave 1 regression) — **PASS**
- `bash deploy/tests/test_helm_template_intelligence.sh` (Wave 2
  regression) — **PASS**
- `bash deploy/tests/test_helm_lint.sh` — **PASS**
- Python suite — **1994 passed, 15 skipped, 5 xfailed, 1 xpassed**
  (hybrid delta is Helm-only; no Python changes).
- No credentials grep — **clean** (values-hybrid.yaml + README).

## Contract summary

- `global.topology: hybrid`.
- `global.runtime: strands_sdk` (Steering Rule 1).
- Cloud-side modules unchanged (M1, M2/M4, M6, M8, M9, M10, M12).
- On-prem modules (M7 shim, M11 REST family) documented via
  `onPrem.adapters: [...]`; NOT rendered cloud-side.
- Adapter-tier relay pattern: on-prem adapters push to cloud
  ingest over mTLS. Cloud never initiates inbound to on-prem.
- Service-mesh bridge (Istio east-west OR Linkerd multi-cluster) is
  assumed; chart does NOT install it.
- Per-tenant IAM role ARN preserved for cloud-side pods. On-prem
  adapters use static mTLS cert identities via
  `onPrem.certBundle.secretName` (firm's PKI, rotation <=90 days).

## Deferred (per spec §4)

- The mesh bridge itself (cluster infra).
- `values-onprem.yaml` (Steering Rule 27).
- M7 / M11 on-prem Helm charts (separate chart family, future wave).
