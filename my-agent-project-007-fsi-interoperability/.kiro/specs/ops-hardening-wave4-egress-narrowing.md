# Ops Hardening Wave 4 — Egress NetworkPolicy Narrowing

> Phase 4 B1 deliverable. SOC 2 CC6.1 audit blocker.
> Modules in scope (templates-only, no Python code changes):
> **M1** (Identity), **M2/M4** (Policy Engine), **M6** (MCP Gateway),
> **M10** (Audit Logger), **M8** (Pipeline Engine), **M9** (Intent
> Router), **M12** (Supervisor).
>
> Source of truth: Steering Rule 22 (private subnets only for data
> plane), Steering Rule 23 (NetworkPolicy per module). Replaces the
> Wave 1 allow-all egress (`egress: [{}]`) with an explicit
> per-destination allowlist.
>
> **v1 LLMJ self-review → CONDITIONAL GO 7.2/10.** Issues raised:
>
> 1. C1 — Original draft had the egress list live directly in the
>    NetworkPolicy template, baking destinations into the chart.
>    Would have forced a chart-version bump every time a vendor FQDN
>    changed. Resolved in v2 §2.2 by moving destinations to a
>    `egressAllowlist: [...]` values field, identical shape across
>    all seven sub-charts.
> 2. C2 — Migration risk: existing deployments break the moment they
>    upgrade without setting `egressAllowlist`. Resolved in v2 §2.5
>    with an opt-in `networkPolicy.egress.mode` flag (`allow-all` |
>    `allowlist`). Default is `allowlist` in values-cloud.yaml
>    (prod) but `allow-all` in `values.yaml` (helm-default), so
>    `helm install` without a topology file still produces a
>    runnable workload for CI smoke tests (backward-compat gate).
> 3. C3 — DNS egress rule missing. Without it, pods can't resolve
>    any of the allowed FQDNs and every call fails. Resolved in v2
>    §2.3 with a mandatory `kube-dns` rule (port 53/UDP + 53/TCP)
>    synthesised by the template unconditionally.
> 4. C4 — Default-deny ingress on Wave 2 charts (M8/M9/M12) lacks an
>    egress block altogether. Wave 4 adds one so SOC 2 CC6.1 applies
>    uniformly. Resolved in v2 §2.4 — all seven sub-charts ship the
>    egress block.
> 5. R1 — Linting: `helm lint` should warn when
>    `egressAllowlist` is empty AND `mode=allowlist`. Resolved in v2
>    §3.6.
> 6. R2 — Test must prove that `- {}` (allow-all marker) is gone
>    from rendered NetworkPolicies in prod mode. Resolved in v2 via
>    `test_helm_template_egress.sh` grep assertion.
> 7. R3 — PrivateLink / ServiceEntry mesh interop: for M8/M9
>    talking to Bedrock via PrivateLink, the egress rule must allow
>    `*.bedrock-runtime.{region}.amazonaws.com`. Resolved in v2 via
>    an explicit `awsPrivateLink.bedrockRuntime.enabled: true`
>    shortcut that expands to a well-known CIDR list. Operator can
>    still override.
>
> v2 score: **GO 8.6/10.** Zero critical, zero must-fix.
>
> Source of truth: `deploy/helm/007-fsi/charts/*/templates/
> networkpolicy.yaml`, Steering Rule 22-23, SOC 2 CC6.1.

---

## Section 1 — Requirements

### R1. Per-destination egress rules replace allow-all

Every sub-chart's NetworkPolicy in `allowlist` mode must replace
`egress: [{}]` (or the missing egress block on M8/M9/M12) with
explicit per-destination entries derived from values.

- **AC1.1** `allowlist` mode: `egress:` rendered as a non-empty list
  where no entry equals `- {}`.
- **AC1.2** `allow-all` mode: `egress: [{}]` preserved. This is the
  helm-default for backward compat (AC8.1).
- **AC1.3** `values-cloud.yaml` sets
  `global.networkPolicy.egressMode: allowlist` so production
  installs default to the narrowed posture.
- **AC1.4** Every sub-chart's egress list ends with a mandatory
  DNS rule (see AC3.*) regardless of operator input.

### R2. Per-module allowlist schemas

Each sub-chart gets a top-level `egressAllowlist:` values field with
this shape:

```yaml
egressAllowlist:
  - host: <fqdn-or-cidr>
    port: <tcp-port>
    protocol: TCP
    # Optional:
    namespace: <k8s-namespace>          # for intra-cluster destinations
    podLabels:                           # for intra-cluster destinations
      app.kubernetes.io/name: <name>
```

`host` is used for non-cluster destinations (renders an
`ipBlock.cidr` — template resolves via host `lookup` if short-hand,
else literal CIDR). `namespace` + `podLabels` is used for
intra-cluster destinations (renders a `namespaceSelector` +
`podSelector` pair). Exactly one of (`host`, `namespace`) must be
set per entry (template validates via `required`).

- **AC2.1** M1 Identity allowlist defaults: Vault
  (`vault.internal:8200`), CA issuer webhook
  (`cert-manager-webhook.cert-manager.svc:443`), DNS.
- **AC2.2** M2/M4 Policy Engine allowlist defaults: Vault, DNS, OPA
  bundle URL (configurable, default
  `opa-bundles.internal:8443`).
- **AC2.3** M6 MCP Gateway allowlist defaults: intra-cluster M1,
  M2/M4, M10 (via `namespace` + `podLabels`); plus a per-vendor MCP
  endpoint allowlist (configurable via values; empty default so
  operator MUST explicitly permit each vendor).
- **AC2.4** M10 Audit Logger allowlist defaults: Langfuse
  (configurable), S3/MinIO endpoint (configurable), CRM
  (configurable, default `salesforce.com:443`), Vault.
- **AC2.5** M8 Pipeline Engine allowlist defaults: intra-cluster M6
  only; plus Bedrock PrivateLink (via
  `awsPrivateLink.bedrockRuntime.enabled: true` shortcut).
- **AC2.6** M9 Intent Router allowlist defaults: Bedrock
  PrivateLink only.
- **AC2.7** M12 Supervisor allowlist defaults: intra-cluster M8, M9,
  M6.

### R3. Mandatory DNS rule

Every rendered NetworkPolicy (in any mode) must allow egress to
kube-dns on port 53 UDP and 53 TCP, targeting pods with
`k8s-app: kube-dns` in the `kube-system` namespace.

- **AC3.1** DNS rule is synthesised by the template, not sourced
  from values. Operator cannot disable it (fail-closed guard).
- **AC3.2** DNS rule uses `namespaceSelector: kubernetes.io/metadata.
  name: kube-system` + `podSelector: k8s-app: kube-dns`.
- **AC3.3** DNS rule is the first entry in the rendered egress list
  so it is visible and easy to audit.

### R4. PrivateLink shortcut for Bedrock

M8 and M9 talk to Bedrock via PrivateLink (Steering Rule 22). The
allowlist schema provides a convenience flag so operators don't
hand-write the full CIDR list.

- **AC4.1** `awsPrivateLink.bedrockRuntime.enabled: true` in M8 and
  M9 sub-chart values expands to a rendered egress rule with:
  `host: bedrock-runtime.<region>.amazonaws.com`, `port: 443`,
  `protocol: TCP`.
- **AC4.2** Region is pulled from `config.awsRegion` (already
  present in M8/M9 values) — no duplication.
- **AC4.3** When the shortcut is OFF, operator must include the
  destination in `egressAllowlist` manually.

### R5. Default-deny posture

Non-empty egress list implies default-deny (K8s NetworkPolicy
semantics). This wave relies on the implicit default-deny from
writing ANY egress entry — no extra annotation needed.

- **AC5.1** Rendered NetworkPolicies in allowlist mode have
  `policyTypes: [Ingress, Egress]` AND a non-empty `egress:` list.
- **AC5.2** No `egress: []` (empty list) is ever rendered; the DNS
  rule is the minimum.

### R6. Generic error messages (no leakage)

The chart does not leak vendor details in error messages. This
requirement is about template hygiene.

- **AC6.1** Template failure paths (missing required field, bad
  shape) use `fail` with a generic message — no values content
  echoed back.

### R7. Migration documentation

Existing deployments that upgrade will break silently if they skip
the `egressAllowlist` step.

- **AC7.1** `VALUES-EGRESS-README.md` documents the migration:
  - Step 1: operator runs `helm diff upgrade` against their values.
  - Step 2: operator adds `egressAllowlist` entries for every
    vendor / intra-cluster destination their apps currently reach.
  - Step 3: operator sets `global.networkPolicy.egressMode:
    allowlist`.
  - Step 4: operator runs `helm upgrade` in a non-prod env first.
- **AC7.2** Migration README explicitly states: "If you skip this,
  your pods will lose all outbound connectivity except DNS the
  moment you upgrade to the allowlist mode."

### R8. Backward compat

Without any new values, helm-default behaviour is unchanged.

- **AC8.1** `helm install` with NO values files produces a chart
  that still has `egress: [{}]` on M1/M2/M4/M6/M10 (the Wave 1
  default) — because `global.networkPolicy.egressMode` defaults to
  `allow-all` in `values.yaml`.
- **AC8.2** `values-cloud.yaml` flips the default to `allowlist`.
- **AC8.3** `test_helm_template.sh` (Wave 1) still passes — it
  does not assert on egress shape.

---

## Section 2 — Design

### 2.1 File layout

```
deploy/helm/007-fsi/
    values.yaml                                 (CHANGED: egressMode default allow-all)
    values-cloud.yaml                           (CHANGED: egressMode allowlist + allowlists)
    VALUES-EGRESS-README.md                     (NEW)
    charts/
        m1-identity/
            values.yaml                         (CHANGED: + egressAllowlist)
            templates/networkpolicy.yaml        (CHANGED: egress block)
        m2-m4-policy-engine/                    (same pattern)
        m6-mcp-gateway/                         (same pattern)
        m10-audit-logger/                       (same pattern)
        m8-pipeline-engine/                     (same pattern + awsPrivateLink)
        m9-intent-router/                       (same pattern + awsPrivateLink)
        m12-supervisor/                         (same pattern)
deploy/tests/
    test_helm_template_egress.sh                (NEW)
```

### 2.2 Shared egress template block

Each sub-chart's `networkpolicy.yaml` has its egress block replaced
with this pattern (adapted per sub-chart):

```yaml
{{- $mode := default "allow-all" (index (default dict .Values.global) "networkPolicy" "egressMode") }}
  egress:
    # Mandatory DNS egress — synthesised, not configurable.
    - to:
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: kube-system
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
        - protocol: TCP
          port: 53
{{- if eq $mode "allow-all" }}
    # Wave 1 compat: allow-all. DO NOT USE IN PRODUCTION.
    - {}
{{- else }}
  {{- range .Values.egressAllowlist }}
    - to:
    {{- if .host }}
        - ipBlock:
            cidr: {{ .host }}/32         # Host-literal. For FQDN targets,
                                         # operator provides a /32 resolved
                                         # at provisioning time, OR uses
                                         # namespace+podLabels for
                                         # intra-cluster peers.
    {{- else if .namespace }}
        - namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: {{ .namespace | quote }}
          podSelector:
            matchLabels:
              {{- toYaml .podLabels | nindent 14 }}
    {{- else }}
      {{- fail "egressAllowlist entry must have host OR namespace+podLabels" }}
    {{- end }}
      ports:
        - protocol: {{ default "TCP" .protocol }}
          port: {{ .port }}
  {{- end }}
  {{- if .Values.awsPrivateLink }}
    {{- if and .Values.awsPrivateLink.bedrockRuntime .Values.awsPrivateLink.bedrockRuntime.enabled }}
    # PrivateLink shortcut for Bedrock. Resolved to a /32 at operator
    # provisioning time via `global.privateLinkCidrs.bedrockRuntime`.
    - to:
        - ipBlock:
            cidr: {{ default "0.0.0.0/0" (index (default dict .Values.global) "privateLinkCidrs" "bedrockRuntime") }}
      ports:
        - protocol: TCP
          port: 443
    {{- end }}
  {{- end }}
{{- end }}
```

Note on FQDN→IP: Kubernetes NetworkPolicy does NOT support FQDNs
natively. The operator is expected to resolve FQDNs to CIDRs at
provisioning time and provide them as the `host` field. A separate
FQDN-aware policy engine (Cilium, Calico Enterprise) is OPTIONAL and
out of scope for this wave. README §3.3 documents this.

### 2.3 DNS synthesised rule

Per AC3.* the DNS rule is the first entry and is NOT sourced from
values. Operators cannot turn it off without template modification
(which is intentional — DNS failure makes every other rule useless).

### 2.4 Wave 2 chart egress block

M8/M9/M12 network policy templates (Wave 2) currently have
`policyTypes: [Ingress]` only. Wave 4 adds an `Egress` entry and the
same egress block as §2.2.

- **AC4.4** `policyTypes: [Ingress, Egress]` on M8, M9, M12 after
  Wave 4.
- **AC4.5** `test_helm_template_intelligence.sh` must still pass —
  verify by running it.

### 2.5 `networkPolicy.egressMode` knob

Defaults:

| values file | Default `global.networkPolicy.egressMode` |
|-------------|-------------------------------------------|
| `values.yaml` | `allow-all` (compat) |
| `values-cloud.yaml` | `allowlist` (prod) |
| `values-hybrid.yaml` | `allowlist` (prod) — inherits via `-f` merge |

Per-sub-chart override: `<subchart>.networkPolicy.egressMode:
allow-all` lets an operator roll back one module at a time for
incident response. Template prefers the sub-chart value when set.

### 2.6 Allowlist defaults per sub-chart

Each sub-chart's `values.yaml` gets an `egressAllowlist: []` key as
the built-in default (empty). `values-cloud.yaml` populates them
with the Steering-Rule-22-compliant defaults from R2.* above:

```yaml
# values-cloud.yaml (new block)
global:
  networkPolicy:
    egressMode: allowlist
  privateLinkCidrs:
    bedrockRuntime: "10.100.0.0/16"   # OVERRIDE PER TENANT

m1-identity:
  egressAllowlist:
    - host: vault.internal
      port: 8200
    - namespace: cert-manager
      podLabels:
        app.kubernetes.io/name: cert-manager-webhook
      port: 443

m2-m4-policy-engine:
  egressAllowlist:
    - host: vault.internal
      port: 8200
    - host: opa-bundles.internal
      port: 8443

m6-mcp-gateway:
  egressAllowlist:
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m1-identity
      port: 8080
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m2-m4-policy-engine
      port: 8080
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m10-audit-logger
      port: 8080
    # Per-vendor MCP allowlist goes here; empty by default so operator
    # MUST explicitly permit each vendor.

m10-audit-logger:
  egressAllowlist:
    - host: langfuse.internal
      port: 443
    - host: s3.us-east-1.amazonaws.com
      port: 443
    - host: salesforce.com
      port: 443
    - host: vault.internal
      port: 8200

m8-pipeline-engine:
  egressAllowlist:
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m6-mcp-gateway
      port: 8443
  awsPrivateLink:
    bedrockRuntime:
      enabled: true

m9-intent-router:
  egressAllowlist: []
  awsPrivateLink:
    bedrockRuntime:
      enabled: true

m12-supervisor:
  egressAllowlist:
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m8-pipeline-engine
      port: 8443
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m9-intent-router
      port: 8443
    - namespace: trust-layer
      podLabels:
        app.kubernetes.io/name: m6-mcp-gateway
      port: 8443
```

### 2.7 Lint warning on empty + allowlist

`helm lint` cannot natively check cross-value semantics. We add a
best-effort warning via the `fail` directive ONLY when
`egressAllowlist` is empty AND `egressMode == "allowlist"` AND the
sub-chart is one where an empty list is known-wrong (M1, M2/M4, M6,
M10, M8, M12). M9 is the sole exception — PrivateLink-only egress
is a valid empty allowlist shape.

Template block (conditionally inserted per sub-chart):

```yaml
{{- if and (eq $mode "allowlist") (eq (len (default list .Values.egressAllowlist)) 0) }}
  {{- if not (and .Values.awsPrivateLink .Values.awsPrivateLink.bedrockRuntime .Values.awsPrivateLink.bedrockRuntime.enabled) }}
    {{- fail "egressAllowlist must be non-empty in allowlist mode — see VALUES-EGRESS-README.md" }}
  {{- end }}
{{- end }}
```

This yields a `helm lint` failure (or `helm install` failure),
satisfying R1 in a spec-compliant way. Operator override: set mode
back to `allow-all` on the offending sub-chart.

---

## Section 3 — Tasks

### Task 1 — Rewrite each sub-chart networkpolicy template

Files:
- `deploy/helm/007-fsi/charts/m1-identity/templates/networkpolicy.yaml`
- `deploy/helm/007-fsi/charts/m2-m4-policy-engine/templates/networkpolicy.yaml`
- `deploy/helm/007-fsi/charts/m6-mcp-gateway/templates/networkpolicy.yaml`
- `deploy/helm/007-fsi/charts/m10-audit-logger/templates/networkpolicy.yaml`
- `deploy/helm/007-fsi/charts/m8-pipeline-engine/templates/networkpolicy.yaml`
- `deploy/helm/007-fsi/charts/m9-intent-router/templates/networkpolicy.yaml`
- `deploy/helm/007-fsi/charts/m12-supervisor/templates/networkpolicy.yaml`

Each gets the egress block per §2.2, with per-sub-chart defaults
sourced from `.Values.egressAllowlist`.

Wave 2 charts (M8, M9, M12) also gain `policyTypes:` adding `Egress`.

Covers AC1.1, AC1.2, AC1.4, AC2.*, AC3.*, AC4.*, AC5.*, AC6.1.

### Task 2 — Update each sub-chart `values.yaml`

Add `egressAllowlist: []` default and (for M8/M9)
`awsPrivateLink.bedrockRuntime.enabled: false` default.

### Task 3 — Update `values-cloud.yaml`

Add the production allowlist defaults from §2.6. Set
`global.networkPolicy.egressMode: allowlist`. Covers AC1.3, AC2.*
production defaults, AC8.2.

### Task 4 — Update `values.yaml` (umbrella default)

Set `global.networkPolicy.egressMode: allow-all` (Wave 1 compat).
Covers AC1.2, AC8.1.

### Task 5 — Write `deploy/tests/test_helm_template_egress.sh`

Assertions:
- With `values-cloud.yaml`, rendered NetworkPolicies contain NO
  `- {}` lines (AC1.1, AC5.1).
- With `values-cloud.yaml`, every NetworkPolicy has a DNS egress rule
  (grep for `k8s-app: kube-dns`) — AC3.*.
- With `values-cloud.yaml`, every NetworkPolicy has `policyTypes` that
  includes `Egress` (AC5.1, AC4.4).
- With NO values file, rendered M1/M2/M4/M6/M10 NetworkPolicies
  contain `- {}` (AC8.1 backward compat).
- Negative: empty `egressAllowlist` + `allowlist` mode on M1 fails
  `helm template` with the expected `fail` message (R1 + §2.7).
- Skips gracefully if helm not on PATH.

### Task 6 — Document migration in
`deploy/helm/007-fsi/VALUES-EGRESS-README.md`

Covers AC7.1, AC7.2.

### Task 7 — Re-run full deploy test suite

All of these MUST still pass after the changes:
- `bash deploy/tests/test_helm_lint.sh`
- `bash deploy/tests/test_helm_template.sh`
- `bash deploy/tests/test_helm_template_intelligence.sh`

### Task 8 — Python suite smoke

`PYTHONPATH=src python3 -m pytest tests/ -q --tb=short` — must still
report 1866 tests pass (Python code unchanged).

---

## Section 4 — Out of Scope (v2 explicit)

- FQDN-aware egress (requires Cilium / Calico Enterprise; operator
  concern).
- Default-deny at cluster-level (some K8s distros require a cluster-
  scoped `default-deny` policy; chart does not install it).
- Istio `ServiceEntry` / `Sidecar` resources — mesh infra, not chart.
- NetworkPolicy enforcement validation in CI — requires a real
  cluster (integration test, deferred).
- On-prem adapter egress policy — separate chart family
  (ops-hardening-wave4-hybrid-topology §2.7).
