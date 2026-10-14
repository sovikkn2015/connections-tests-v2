# ops-hardening-wave4-egress-narrowing — COMPLETE

Spec: `.kiro/specs/ops-hardening-wave4-egress-narrowing.md` (v2 GO 8.6/10).

## Artifacts shipped

| Path | Change |
|------|--------|
| `deploy/helm/007-fsi/values.yaml` | `global.networkPolicy.egressMode: allow-all` (helm default) |
| `deploy/helm/007-fsi/values-cloud.yaml` | `egressMode: allowlist` + per-module production allowlists |
| `deploy/helm/007-fsi/charts/m1-identity/templates/networkpolicy.yaml` | Rewritten (Egress, DNS rule, allowlist) |
| `deploy/helm/007-fsi/charts/m2-m4-policy-engine/templates/networkpolicy.yaml` | Rewritten |
| `deploy/helm/007-fsi/charts/m6-mcp-gateway/templates/networkpolicy.yaml` | Rewritten |
| `deploy/helm/007-fsi/charts/m10-audit-logger/templates/networkpolicy.yaml` | Rewritten |
| `deploy/helm/007-fsi/charts/m8-pipeline-engine/templates/networkpolicy.yaml` | + Egress block, PrivateLink shortcut |
| `deploy/helm/007-fsi/charts/m9-intent-router/templates/networkpolicy.yaml` | + Egress block, PrivateLink shortcut |
| `deploy/helm/007-fsi/charts/m12-supervisor/templates/networkpolicy.yaml` | + Egress block |
| `deploy/helm/007-fsi/charts/*/values.yaml` | Default `egressAllowlist: []` on all 7 sub-charts; `awsPrivateLink.bedrockRuntime.enabled: false` on M8/M9 |
| `deploy/helm/007-fsi/VALUES-EGRESS-README.md` | Operator migration guide |
| `deploy/tests/test_helm_template_egress.sh` | Multi-phase egress verification test |

## Verification gates

- `bash deploy/tests/test_helm_template_egress.sh` — **PASS**
  - Phase A (helm default): trust-layer NetworkPolicies still
    contain `- {}` (Wave 1 compat preserved).
  - Phase B (values-cloud.yaml): all 4 rendered NetworkPolicies
    have narrowed egress (no `- {}`), each has a kube-dns rule,
    each has `policyTypes: [Ingress, Egress]`.
  - Phase C (negative): empty allowlist + allowlist mode causes
    `helm template` to fail with the expected message.
- `bash deploy/tests/test_helm_template.sh` (Wave 1 regression) — **PASS**
- `bash deploy/tests/test_helm_template_intelligence.sh` (Wave 2
  regression) — **PASS**
- `bash deploy/tests/test_helm_lint.sh` — **PASS**
- `bash deploy/tests/test_helm_template_hybrid.sh` — **PASS** (hybrid's
  on-prem ingest FQDN now renders into the M6 NetworkPolicy).
- Python suite — **1994 passed** (no Python changes).

## Contract summary

- DNS egress rule is synthesised by every template (not configurable).
- `global.networkPolicy.egressMode: allow-all | allowlist` knob.
  Default: `allow-all` in `values.yaml`; `allowlist` in
  `values-cloud.yaml`.
- Per-sub-chart `egressAllowlist: [...]` consumed by the template.
- `awsPrivateLink.bedrockRuntime.enabled: true` shortcut for M8/M9.
- Empty allowlist in allowlist mode → `helm template` fails fast with
  a clear message pointing at `VALUES-EGRESS-READ ME.md` (backward-
  compat migration gate).

## Deferred (per spec §4)

- FQDN-aware egress (Cilium / Calico Enterprise).
- Cluster-level default-deny policy.
- Istio `ServiceEntry` / `Sidecar` resources.
- In-cluster NetworkPolicy enforcement validation (integration).
