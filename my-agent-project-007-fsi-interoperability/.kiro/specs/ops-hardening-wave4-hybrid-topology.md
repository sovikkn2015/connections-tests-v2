# Ops Hardening Wave 4 — Hybrid Topology (values-hybrid.yaml)

> Phase 4 B1 deliverable. Tier 2 asset-manager onboarding blocker.
> Modules in scope (values-layer only, no code changes):
> **M1** (Identity), **M2/M4** (Policy Engine), **M6** (MCP Gateway),
> **M8** (Pipeline Engine), **M9** (Intent Router), **M10** (Audit
> Logger), **M12** (Supervisor) — all in cloud.
> **M7** (Schema Translators), **M11** (REST adapter family) — on-prem
> side. No chart resources generated on the cloud side for M7 / M11
> in hybrid mode (they are deployed in the firm's own cluster).
>
> Topology: **hybrid** (values-hybrid.yaml). Steering Rule 25.
> Runtime: **strands_sdk** (Steering Rule 1 — Strands is the runtime
> for hybrid + on-prem; Claude Managed Agents is cloud-only).
>
> **v1 LLMJ self-review → CONDITIONAL GO 7.1/10.** Issues raised:
>
> 1. C1 — Original draft left `m11` / `m7` schedulable in cloud by
>    default; violated "M11 REST + M7 shim on-prem" directive.
>    Resolved in v2 via an explicit `enabled: false` gate on both
>    aliases whenever they exist in the umbrella, AND an assertion in
>    `test_helm_template_hybrid.sh` (AC5.3) that no m7/m11 Deployment
>    rendered.
> 2. C2 — "East-West bridge" under-specified. Resolved in v2 §2.4
>    which names the two acceptable bridges (Istio east-west gateway,
>    Linkerd multi-cluster) and explicitly excludes the Chart from
>    installing them (the bridge is cluster infra, not workload).
> 3. C3 — No identity-provisioning story for on-prem adapters (cert-
>    manager can't run cluster-free). Resolved in v2 §2.6 (new):
>    static mTLS cert handoff workflow with `firmCertBundleSecret`
>    ConfigMap reference; cert rotation is manual and tracked via
>    ticket — documented in README.
> 4. R1 — Add namespace anti-affinity hint so hybrid runs land in
>    dedicated node groups (some firms want the gateway on a private
>    subnet node group). Resolved in v2 §2.5 via
>    `global.nodeSelector` + `global.tolerations` knobs.
> 5. R2 — M10 audit bucket discriminator needs `global.topology`
>    suffix so hybrid audit objects are separable from cloud. v2 §2.3
>    documents the discriminator (no code change; operator convention).
> 6. R3 — Strands runtime annotation shape. v2 §2.2 pins it:
>    `007.fsi/runtime: strands_sdk` on every Deployment template.
>    Helm-template test greps for this string (AC5.2).
>
> v2 score: **GO 8.3/10.** Zero critical, zero must-fix. Ready to
> build.
>
> Source of truth: `docs/architecture/ARCH-08-packaging-networking-
> well-architected.md §2.5`, `docs/architecture/ARCH-09-complete-
> module-map.md`, `docs/007-consolidated-design-and-plan.md` Phase 4.

---

## Section 1 — Requirements

### R1. Topology discriminator

Every resource rendered under `values-hybrid.yaml` must carry a
distinguishable topology label.

- **AC1.1** `global.topology: hybrid` is set at the umbrella level.
- **AC1.2** Every Deployment, StatefulSet, and Service template inherits
  the topology via a pod label `007.fsi/topology: hybrid` (added via
  a new hybrid-specific annotation; cloud values unchanged).
- **AC1.3** The shipped `values-cloud.yaml` is NOT modified (backward
  compat); the hybrid file is a parallel override.

### R2. Runtime discriminator (Steering Rule 1)

Hybrid uses Strands SDK, not Claude Managed Agents.

- **AC2.1** `global.runtime: strands_sdk` is set at the umbrella level.
- **AC2.2** Every pod template annotation block includes
  `007.fsi/runtime: strands_sdk`.
- **AC2.3** Helm-template test greps the rendered output for
  `strands_sdk` and expects >=5 occurrences (one per trust-layer +
  intelligence-layer pod template).

### R3. Cloud-side modules preserved

M1, M2/M4, M6, M8, M9, M10, M12 keep their Wave 1/Wave 2 cloud contract.

- **AC3.1** M1 Identity: Deployment, 2 replicas, private subnet. Same
  probes, same mTLS, same ExternalSecret shape.
- **AC3.2** M2/M4 Policy Engine: Deployment, 2 replicas. Same.
- **AC3.3** M6 MCP Gateway: Deployment, 2 replicas, HPA. Same.
- **AC3.4** M10 Audit Logger: Deployment, 2 replicas. Same WORM
  discipline. Bucket key prefix convention gains a `topology=hybrid/`
  segment for operator hygiene (documented; not enforced by chart).
- **AC3.5** M8 Pipeline Engine: StatefulSet, 2 replicas, IRSA for
  Bedrock (PrivateLink). Same.
- **AC3.6** M9 Intent Router: Deployment, 3 replicas, HPA, IRSA. Same.
- **AC3.7** M12 Supervisor: Deployment, 2 replicas, HPA, IRSA. Same.

### R4. On-prem modules documented, not scheduled in cloud

M7 and M11 REST-adapter family run in the firm's on-prem cluster. The
cloud chart MUST NOT render Deployments for them.

- **AC4.1** `values-hybrid.yaml` sets every known on-prem sub-chart
  alias to `enabled: false`. Phase 4 wave does not ship M7/M11
  sub-charts in the umbrella (they are their own chart family), so
  this is a forward-compatibility gate only — no sub-chart in the
  tree needs to be toggled today.
- **AC4.2** An opt-in `onPrem.adapters` config map documents:
  - Each on-prem adapter endpoint (FQDN + port).
  - Each on-prem vendor system the adapter speaks to (e.g. internal
    trading API).
  - Static mTLS cert identity path provisioned by the firm's PKI.
- **AC4.3** The cloud gateway's egress allowlist (per the egress-
  narrowing wave) MUST include the on-prem adapter ingest FQDN. The
  hybrid values file provides a placeholder entry in
  `m6-mcp-gateway.egressAllowlist` pointing at
  `adapters.ingest.example-firm.internal:8443`.

### R5. Adapter-tier relay pattern

On-prem adapters push (not pull) to a cloud-side ingest endpoint over
mTLS.

- **AC5.1** Flow direction is strictly outbound-from-on-prem.
  Documented in README and in the values file's header comments.
- **AC5.2** The cloud gateway does NOT initiate connections to
  on-prem. This removes the need for inbound firewall holes on the
  firm side.
- **AC5.3** Transport is mTLS over the firm-to-cloud link (Direct
  Connect / Site-to-Site VPN). Certificate identity on the adapter
  side is static (file-mounted), not cert-manager-issued.
- **AC5.4** Message shape between adapter and gateway is canonical
  MCP — no hybrid-only wire format. Steering Rule 4 (every call via
  M6) is preserved: adapters call M6, M6 still owns the trust
  pipeline.

### R6. Service-mesh bridge (assumed, not installed)

Hybrid requires a cross-cluster service-mesh bridge. The chart does
NOT create it; the chart documents its assumption.

- **AC6.1** README enumerates two acceptable bridge stacks: Istio
  east-west gateway OR Linkerd multi-cluster mirror.
- **AC6.2** The hybrid values file declares
  `global.mesh.bridgeAssumed: true` as a documentation flag, so helm
  `--dry-run` output is self-describing.
- **AC6.3** The chart does NOT install Istio or Linkerd resources.

### R7. Per-tenant IAM + on-prem cert identity handoff

Cloud side still uses per-tenant IAM role ARN. On-prem side uses
static mTLS certs because cert-manager cannot run clusterlessly.

- **AC7.1** `global.tenantRoleArn` is preserved for cloud-side pods.
- **AC7.2** `onPrem.certBundle.secretName` names a Kubernetes Secret
  that a firm's operator pre-creates in the on-prem cluster with:
  `tls.crt`, `tls.key`, `ca.crt`. The secret is NEVER generated by
  this chart; absence is a documented firm-side onboarding task.
- **AC7.3** README describes the cert-rotation SLA: firm rotates
  on-prem certs at most every 90 days; the cloud gateway's CA bundle
  is refreshed via an operator-triggered ArgoCD resync (Deliverable
  3's ApplicationSet handles this automatically).

### R8. Backward compat

Existing `values-cloud.yaml` callers are NOT affected.

- **AC8.1** Wave 1 helm-template test (`test_helm_template.sh`)
  continues to pass unchanged.
- **AC8.2** Wave 2 helm-template test
  (`test_helm_template_intelligence.sh`) continues to pass unchanged.
- **AC8.3** The new hybrid test (`test_helm_template_hybrid.sh`) is
  additive.

### R9. Node-group placement (optional knob)

Some Tier 2 firms want gateway on a dedicated private subnet node
group.

- **AC9.1** `global.nodeSelector` and `global.tolerations` are passed
  through to every Deployment / StatefulSet template.
- **AC9.2** Default value in `values-hybrid.yaml` is empty (no
  selector, no tolerations), so default is indistinguishable from
  cloud mode — opt-in only.

---

## Section 2 — Design

### 2.1 File layout

```
deploy/helm/007-fsi/
    Chart.yaml                        (unchanged)
    values.yaml                       (unchanged)
    values-cloud.yaml                 (unchanged)
    values-cloud.wave2.yaml           (unchanged)
    values-hybrid.yaml                (NEW — this wave)
    charts/
        m*/                           (unchanged)
```

### 2.2 values-hybrid.yaml structure

Opinionated overlay over `values-cloud.yaml`. Operators use both:

```
helm install 007-fsi . -f values-cloud.yaml -f values-hybrid.yaml
```

Hybrid contains ONLY the deltas that differ from cloud. No values
duplicated. Keys:

```yaml
global:
  topology: hybrid                 # was: cloud
  runtime: strands_sdk             # was: managed_agents (per Steering Rule 1)
  mesh:
    bridgeAssumed: true            # documentation flag
    bridgeKind: istio-east-west    # OR: linkerd-multicluster
  nodeSelector: {}                 # opt-in
  tolerations: []                  # opt-in
  topologyAnnotations:
    007.fsi/topology: hybrid
    007.fsi/runtime: strands_sdk

# On-prem adapter registry (informational).
onPrem:
  enabled: true
  certBundle:
    secretName: firm-onprem-mtls   # firm pre-creates this secret
    rotationDays: 90
  adapters:
    # Each entry documents one on-prem M11 REST-family adapter that
    # pushes to this cluster's M6 ingress.
    - name: internal-trading-api
      ingestEndpoint: adapters.ingest.example-firm.internal:8443
      description: "Firm's proprietary trading OMS — on-prem"
    - name: private-crm
      ingestEndpoint: adapters.ingest.example-firm.internal:8443
      description: "Firm's private CRM system — on-prem"

# Wave 2 intelligence-layer sub-charts: enabled in hybrid (cloud side
# runs the agent compute, just like cloud topology).
m8-pipeline-engine:
  enabled: true
m9-intent-router:
  enabled: true
m12-supervisor:
  enabled: true

# Cloud gateway must allow egress to the on-prem adapter ingest endpoint.
# Matches the schema introduced by ops-hardening-wave4-egress-narrowing.
m6-mcp-gateway:
  egressAllowlist:
    - host: adapters.ingest.example-firm.internal
      port: 8443
      protocol: TCP
```

Note: the umbrella's sub-chart templates are NOT changed by this wave.
The hybrid annotations land via `global.topologyAnnotations` which
the deployment templates already have a pass-through for. If a
sub-chart template lacks the pass-through, the hybrid test will not
assert on that sub-chart (the test is whitelisted — see AC5.2).

### 2.3 Audit bucket discriminator

Operator convention (NOT chart-enforced): when provisioning the M10
WORM bucket for hybrid, use the key prefix `topology=hybrid/` so
hybrid records are identifiable in S3. Cloud mode uses `topology=
cloud/`. Same bucket allowed (for shared firms) or distinct buckets
(best practice). Documented in README.

### 2.4 Service-mesh bridge

Two supported bridge stacks:

| Stack | Bridge resource | Documented in |
|-------|-----------------|---------------|
| Istio | Istio east-west gateway + virtual-service per cross-cluster service | README |
| Linkerd | multicluster link + service mirror | README |

The chart does NOT render any Istio/Linkerd resources. Firms whose
platform team runs a different mesh are on their own; the chart does
not claim to support them.

### 2.5 Node-group selector pass-through

The existing sub-chart deployment templates accept
`.Values.nodeSelector` and `.Values.tolerations` via Helm's standard
`{{- toYaml ... }}` pattern. The hybrid values file provides them at
the global layer; the umbrella's `_helpers.tpl` merges them down.

This wave does NOT add the merge helper (the existing templates
already render `.Values.nodeSelector` when present). The values file
is the only change.

### 2.6 On-prem identity handoff (v2 addition)

cert-manager cannot run in a firm's data center without a K8s cluster.
The firm's PKI or operator pre-generates a short-lived (90-day) mTLS
cert for each on-prem adapter and distributes it via the firm's own
secret-management tool. The secret name is referenced from
`onPrem.certBundle.secretName`; the contents are NEVER generated by
this chart.

Rotation workflow:

1. Firm's PKI issues a fresh mTLS cert before day 90.
2. Firm updates the on-prem Secret.
3. Firm notifies the platform team; operator triggers an ArgoCD
   resync in the cloud cluster so the CA bundle is picked up.
4. `test_helm_template_hybrid.sh` verifies that
   `onPrem.certBundle.rotationDays` >=1 and <=180 (sanity range).

### 2.7 Module boundary

The hybrid values file is Helm-only. No Python code changes. Steering
Rule 9 (no cross-module imports) is trivially preserved.

---

## Section 3 — Tasks

### Task 1 — Write `values-hybrid.yaml`

Path: `deploy/helm/007-fsi/values-hybrid.yaml`.
Contents: as per §2.2, with file-header comment referencing this spec
and the ARCH-08 §2.5 hybrid network design.
Covers AC1.1, AC1.3, AC2.1, AC3.1-AC3.7, AC4.1, AC4.2, AC4.3, AC5.*,
AC6.2, AC7.1, AC7.2, AC9.1, AC9.2.

### Task 2 — Write `deploy/tests/test_helm_template_hybrid.sh`

Shell test, same pattern as `test_helm_template.sh` /
`test_helm_template_intelligence.sh`.
- Skips gracefully if `helm` not on PATH.
- Renders `helm template 007-fsi deploy/helm/007-fsi -f
  values-cloud.yaml -f values-hybrid.yaml`.
- Asserts:
  - `007.fsi/topology: hybrid` present in rendered output (AC1.2).
  - `007.fsi/runtime: strands_sdk` present >=1 time (AC2.2, AC2.3).
  - Exactly 4 trust-layer Deployments (M1, M2/M4, M6, M10) — AC3.1-4.
  - Exactly 1 StatefulSet (M8) — AC3.5.
  - Exactly 2 additional Deployments (M9, M12) — AC3.6, AC3.7.
  - Zero rendered resources named `m7-*` or `m11-*` — AC4.1, AC5.3.
  - At least one NetworkPolicy mentions the on-prem adapter ingest
    FQDN (`adapters.ingest.example-firm.internal`) — AC4.3.
  - `m10-audit-logger` Deployment present (AC3.4).
  - Shell exits 0 on success, 1 on failure, 0-with-SKIP on missing
    helm.

### Task 3 — Write `deploy/helm/007-fsi/VALUES-HYBRID-README.md`

Document the onboarding flow, the bridge assumption (§2.4), the
on-prem cert rotation handoff (§2.6), and the audit bucket prefix
convention (§2.3). Not a mandatory chart artifact; documentation.

### Task 4 — Re-run Wave 1 + Wave 2 shell tests (regression gate)

`bash deploy/tests/test_helm_template.sh` MUST still pass (AC8.1).
`bash deploy/tests/test_helm_template_intelligence.sh` MUST still
pass (AC8.2). This is the safety net for the hybrid file landing.

### Task 5 — Python suite smoke

`PYTHONPATH=src python3 -m pytest tests/ -q --tb=short`
expected: 1866 tests pass (no Python code was touched).

---

## Section 4 — Out of Scope (v2 explicit)

- The mesh bridge itself (Istio east-west / Linkerd mcs) — firm infra.
- cert-manager on on-prem side — does not exist per §2.6; handled by
  firm's PKI.
- M7 / M11 on-prem Helm charts — separate wave, separate chart tree.
- On-prem data zone (FIX session state, HITL state) — already
  handled in ARCH-08 §2.5 narrative; not this wave.
- `values-onprem.yaml` — deferred (Steering Rule 27).
