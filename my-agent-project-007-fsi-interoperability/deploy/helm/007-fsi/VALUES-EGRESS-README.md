# Egress NetworkPolicy Narrowing — Operator Migration Guide

Wave 4 Phase 4 deliverable. Spec: `.kiro/specs/ops-hardening-wave4-egress-narrowing.md`.

## What changed

Before Wave 4, every sub-chart's NetworkPolicy shipped with
`egress: [{}]` — an allow-all posture that failed SOC 2 CC6.1.

Wave 4 replaces it with an explicit per-destination allowlist:

- `global.networkPolicy.egressMode: allow-all | allowlist` knob.
- Per-sub-chart `egressAllowlist: [...]` values field.
- Synthesised DNS egress rule (kube-dns) — mandatory, not configurable.
- Bedrock PrivateLink shortcut for M8 + M9 via
  `awsPrivateLink.bedrockRuntime.enabled`.

## Defaults per values file

| File | `egressMode` default |
|------|----------------------|
| `values.yaml` (helm default) | `allow-all` (Wave 1 compat) |
| `values-cloud.yaml` | `allowlist` (SOC 2 CC6.1) |
| `values-hybrid.yaml` | inherits via CLI `-f` merge (`allowlist`) |

## Migration — MUST READ before upgrading

If you run `helm upgrade` against an existing deployment and the
rendered manifests flip to `allowlist` mode without a matching
`egressAllowlist`, `helm template` will fail fast with a clear error
pointing at this README. No silent blackouts.

Migration checklist:

1. `helm diff upgrade` against your current values to see the new
   NetworkPolicy egress rules.
2. For every destination your pods currently reach (vendor APIs,
   intra-cluster services, Vault, PrivateLink endpoints), add an
   `egressAllowlist` entry on the appropriate sub-chart.
3. Review the production defaults in `values-cloud.yaml`; most firms
   override the placeholder CIDRs (`10.0.0.10`, `10.0.0.20`, ...) with
   their actual VPC endpoint addresses.
4. For M8 / M9 Bedrock access, set
   `global.privateLinkCidrs.bedrockRuntime` to the VPC endpoint CIDR.
   Default `10.100.0.0/16` is a placeholder.
5. Test in a non-prod cluster first. Verify with `kubectl exec <pod> --
   wget -O- https://<destination>` that every required destination
   still resolves.
6. Roll forward in prod with `automated.selfHeal: false` temporarily
   so a mistake doesn't auto-apply.

## Rollback

Set `<sub-chart>.networkPolicy.egressMode: allow-all` on the offending
module to restore Wave 1 behaviour without reverting the chart.
Per-sub-chart override wins over the global setting.

## Allowlist entry shape

```yaml
egressAllowlist:
  # Non-cluster destination (vendor API, Vault, PrivateLink endpoint)
  - host: <cidr-or-resolved-ip>
    port: <port>
    protocol: TCP            # default TCP
  # Intra-cluster destination
  - namespace: <k8s-namespace>
    podLabels:
      app.kubernetes.io/name: <pod-name>
    port: <port>
    protocol: TCP
```

Exactly one of (`host`, `namespace`) must be set per entry; the
template fails fast otherwise.

## FQDN resolution

Kubernetes NetworkPolicy does not support FQDNs natively. Operators
either:

- Resolve FQDNs to IP CIDRs at provisioning time and pass the CIDR via
  the `host:` field, OR
- Install an FQDN-aware policy engine (Cilium, Calico Enterprise) and
  wire it to honour these CIDRs. Out of scope for this wave.

## Tests

`deploy/tests/test_helm_template_egress.sh` asserts:

- With `values-cloud.yaml`, no rendered NetworkPolicy contains
  `- {}` (allowlist mode is effective).
- With `values-cloud.yaml`, every NetworkPolicy has a kube-dns egress
  rule.
- Without any values files, the rendered trust-layer NetworkPolicies
  still carry `- {}` (Wave 1 compat).
- Negative: empty `egressAllowlist` with `allowlist` mode causes
  `helm template` to fail with the expected message.

Skips gracefully when `helm` is not on PATH.
