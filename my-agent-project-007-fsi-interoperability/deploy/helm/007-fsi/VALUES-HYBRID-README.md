# values-hybrid.yaml — Operator Guide

Wave 4 Phase 4 deliverable. Spec: `.kiro/specs/ops-hardening-wave4-hybrid-topology.md`.

## When to use this file

Tier 2 asset managers whose vendor systems live on-prem (internal
trading OMS, private CRM) but who want the trust layer and intelligence
layer (gateway, OPA, WORM audit, Bedrock-backed specialists) in cloud.

Do NOT use for:

- Tier 3/4 RIAs — use `values-cloud.yaml` alone.
- Tier 1 banks requiring fully on-prem deployment — deferred to Phase 5
  (Steering Rule 27).

## Install

```bash
helm install 007-fsi deploy/helm/007-fsi \
  -f deploy/helm/007-fsi/values-cloud.yaml \
  -f deploy/helm/007-fsi/values-hybrid.yaml
```

Both files must be supplied. `values-cloud.yaml` carries the
production module-level defaults; `values-hybrid.yaml` overlays the
hybrid deltas.

## Bridge assumption

Hybrid requires a cross-cluster service-mesh bridge. The chart does
NOT install the bridge. Two stacks are supported:

| Stack | What the operator installs |
|-------|----------------------------|
| Istio east-west | `IstioOperator` with `meshConfig.eastWestGateway` enabled, cross-cluster ServiceEntry per mirrored service, multicluster root CA. |
| Linkerd multicluster | `linkerd multicluster install` + service mirror per namespace. |

Firms on a different mesh (Consul, Cilium Cluster Mesh, custom
solutions) are out of scope — the chart makes no claims of support.

## On-prem identity handoff

cert-manager cannot run in a firm's data center without a K8s cluster.
Instead:

1. Firm's PKI issues a short-lived (<=90 day) mTLS cert per on-prem
   adapter.
2. Operator creates the Kubernetes Secret named `firm-onprem-mtls`
   in the cloud cluster (alongside M6) with `tls.crt`, `tls.key`,
   `ca.crt`.
3. `values-hybrid.yaml` references that Secret via
   `onPrem.certBundle.secretName`.
4. Rotation SLA: firm rotates on-prem certs every <=90 days; operator
   updates the Secret and triggers an ArgoCD resync so the CA bundle
   is re-read.

## Adapter-tier relay pattern

On-prem adapters PUSH to a cloud-side ingest endpoint (the M6 gateway
Service). The cloud gateway NEVER initiates connections to on-prem —
this removes the need for inbound firewall holes on the firm side.

Flow:

```
[on-prem adapter] --mTLS over VPN/Direct Connect--> [M6 gateway]
                                                           |
                                      [M1 AID verify, M2/M4 OPA, M4 MNPI filter]
                                                           |
                                                  [M10 audit WORM]
```

Every call still passes through the Trust Layer pipeline (Steering
Rule 4). The hybrid topology does not bypass it.

## Audit bucket convention

Operator-enforced (not chart-enforced) — when provisioning the M10
WORM bucket for hybrid, prefix keys with `topology=hybrid/` so hybrid
records are separable from cloud in mixed-deployment firms. Cloud
mode uses `topology=cloud/`. The chart accepts the same
`bucket_name` regardless of topology.

## Node-group placement (opt-in)

Some Tier 2 firms want the gateway on a dedicated private-subnet
node group. The hybrid values file exposes two pass-through knobs:

```yaml
global:
  nodeSelector:
    workload: trust-layer
  tolerations:
    - key: trust-layer
      operator: Exists
      effect: NoSchedule
```

Default is empty (no selector, no tolerations) so the hybrid
install behaves like cloud-only unless explicitly overridden.

## Tests

`deploy/tests/test_helm_template_hybrid.sh` renders the umbrella with
both values files and asserts:

- `global.topology: hybrid` is set.
- Strands SDK runtime annotations are present.
- Exactly 4 cloud-side trust-layer Deployments (M1, M2/M4, M6, M10)
  render.
- No M7 or M11 resources render cloud-side in hybrid mode.
- The on-prem adapter ingest FQDN appears in the M6 egress allowlist.

Skips gracefully when `helm` isn't on PATH. Always runs a pure-Python
YAML contract check regardless.
