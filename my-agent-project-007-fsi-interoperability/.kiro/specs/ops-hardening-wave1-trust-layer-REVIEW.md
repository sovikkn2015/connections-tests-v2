# LLMJ Review v1 — ops-hardening-wave1-trust-layer.md

> Reviewer: **gateway-specialist** (self-review, per task instructions).
> Reviewed: `.kiro/specs/ops-hardening-wave1-trust-layer.md`
> Scoring dimensions and weights per `docs/007-module-build-playbook.md`.

## Scoring

| Dimension | Weight | Score (/10) | Weighted |
|-----------|-------:|------------:|---------:|
| Completeness       | 25% | 7.0 | 1.75 |
| Accuracy           | 20% | 7.5 | 1.50 |
| Security           | 20% | 8.0 | 1.60 |
| Testability        | 15% | 7.0 | 1.05 |
| Design alignment   | 10% | 8.5 | 0.85 |
| Gaps               | 10% | 6.0 | 0.60 |
| **Overall**        |     |     | **7.35 / 10 — CONDITIONAL GO** |

## Critical Issues (blocking GO)

### C1. Helm v4 vs v3 template semantics not specified.
Helm 4.x was released Q3 2025 and has breaking changes in how
`dependencies:` resolve local `file://` paths and in chart schema
validation. The spec says `apiVersion: v2` but never names the minimum
helm binary version. If CI runs `helm lint` on v3.14 and local dev on
v4.x, template rendering may diverge. **Required fix**: state
"`helm lint` is validated against helm ≥ 3.14. helm v4 is also
supported but not the lint baseline." Add a note that local `file://`
subchart refs work in both.

### C2. Port 8080 vs 8443 — application contract ambiguity.
The spec says M6 and M10 currently ship with a single 8443 port whose
HEALTHCHECK probes 8443. The new deploy/docker variant adds 8080 for
liveness. If the Helm probes hit 8080 but the FastAPI process only
listens on 8443, probes fail and pods crash-loop. **Required fix**:
either (a) run two uvicorn processes (one per port) via an entrypoint
script, (b) run a single uvicorn bound to `0.0.0.0:8080` for dev/probes
and rely on the service-mesh sidecar to forward mTLS traffic from 8443
down to 8080, or (c) bind a single listener to 8080 and document that
mTLS termination happens upstream **onto** 8080. Pick one and write it
in. Option (c) is simplest and aligns with the existing M6 Dockerfile
(which already only listens on its single port) — just rename the
logical "app port" from 8443 to 8080 at the container level, and keep
`service.port: 8443` at the Service layer with `targetPort: 8080`.

### C3. ExternalSecret CRD version not pinned.
`ExternalSecret` has two popular CRD groups: `external-secrets.io/v1beta1`
(external-secrets.io) and older `kubernetes-client.io/v1` (GoDaddy
operator, deprecated). `helm lint` will happily render either. **Required
fix**: pin `apiVersion: external-secrets.io/v1beta1` in the spec and
the templates.

### C4. cert-manager Certificate CRD + issuer reference.
`duration: 24h` is valid on `cert-manager.io/v1`, but the spec doesn't
specify the issuer reference type (`ClusterIssuer` vs `Issuer`) or the
issuer name. If values-cloud.yaml is missing the issuer, `helm template`
still renders but the resource fails to reconcile in-cluster. **Required
fix**: values-cloud.yaml must set `certManager.issuerName` and
`certManager.issuerKind: ClusterIssuer` with documented defaults.

### C5. Python test-count invariant is off-by-4.
AC6.1 says "≥ 1707 passed". The current suite reports
"1707 passed, 4 skipped, 5 xfailed, 1 xpassed". The stable invariant
is the full line, not just the passed count — if a new test is added
inadvertently as skipped it still passes the "≥ 1707" check. **Required
fix**: change AC6.1 to assert the exact shape
"1707 passed, 4 skipped, 5 xfailed, 1 xpassed", OR state explicitly
that the invariant is "the existing 1707 all remain passing and no
existing test moves to skipped/xfailed". Pick the latter — the former
is brittle if later waves add tests.

## Recommended Issues (non-blocking but should address)

### R1. No explicit mention of OCI image-spec labels spec.
AC2.8 says "standard OCI labels" but doesn't cite the `LABEL`
requirement per [OCI image-spec §annotations](https://github.com/opencontainers/image-spec/blob/main/annotations.md).
Add the URL + the exact label set.

### R2. `ClusterSecretStore` name not pinned.
AC3.6 and the ExternalSecrets pattern don't name the specific
ClusterSecretStore. Add `externalSecrets.storeName: vault-cluster-store`
as the default in values-cloud.yaml.

### R3. Missing mention of Pod Security Standards.
Cloud clusters increasingly enforce Pod Security Admission at the
namespace level (`restricted` profile). The Deployment templates should
set `securityContext: {runAsNonRoot: true, runAsUser: 1000,
allowPrivilegeEscalation: false, capabilities: {drop: [ALL]}}` and
`seccompProfile: {type: RuntimeDefault}`. Add this as AC3.9.

### R4. HorizontalPodAutoscaler `apiVersion` drift.
HPAs moved through three API versions (v1, v2beta2, v2). Pin
`autoscaling/v2`.

### R5. docker-compose network exposure.
AC4.4 says "default bridge network". Consider explicitly scoping a
named network `007-trust-layer` so the compose file can be stacked
under other compose files later without port-scope collisions.

### R6. Helm v4 lint strictness.
Helm 4 lint is stricter about ChartLabelMissing warnings. Add a
`.helmignore` stating what to ignore, and ensure each Chart.yaml carries
`keywords:`, `maintainers:`, `icon:` at the umbrella level so v4 lint
stays at 0 warnings for the umbrella.

### R7. No rollback plan documented.
If ops hardening ships a broken Dockerfile, rollback is "revert the
PR". Document this explicitly — especially that the in-source M6 +
M10 Dockerfiles remain authoritative for laptop dev and that the
deploy/docker variants can be rolled back independently.

## Gaps (must mention, lower severity)

### G1. No explicit test for "both apps import without touching network".
AC1.8 says apps must not touch network at import time. No test covers
this. Consider adding a pytest that imports `m1_identity.app` and
`m2_m4_policy_engine.app` under a socket-disabled fixture. Out of
scope for Wave 1 (would add tests, ambiguous re: count invariant), but
note it as follow-up.

### G2. 3-topology rule (Steering 25) acknowledgement.
Spec correctly defers hybrid + onprem. Call out explicitly in Section 4
that `values-hybrid.yaml` and `values-onprem.yaml` will ship in
Phase 4 and that this wave does not ship empty placeholders (which
would fail grep-gates silently).

### G3. No documented way to run `test_dockerfile_security.sh` from
the project root vs from `deploy/tests/`. Make the script path-resilient
with `cd "$(dirname "$0")/.."` pattern or document required cwd.

### G4. `imagePullPolicy` logic ambiguity.
AC3.5 says `:latest` → Always, pinned → IfNotPresent. But
values-cloud.yaml defaults to `:latest`. In real prod we'd pin to a
digest. Document that pinning is per-tenant overlay responsibility,
not the chart's default.

## Strengths

- Module boundary and scope are crisp. No drift into intelligence-layer
  or compliance-gap modules.
- The in-source Dockerfiles for M6 + M10 are preserved and the new
  deploy/docker variants are explicitly additive. Zero regression risk
  on existing tests.
- Security posture table (2.7) maps directly to Steering Rules 20–23.
- Test shell scripts are specified with exact grep targets — easy to
  implement deterministically, easy to re-run in CI.
- Per-tenant KMS and namespace isolation are surfaced via ServiceAccount
  annotations rather than hard-coded, which matches Steering Rule 23.

## Required fixes for GO

- **C1** — name minimum helm lint baseline.
- **C2** — resolve the port 8080/8443 contract. Recommend single-listener
  on 8080 with Service `targetPort: 8080, port: 8443`.
- **C3** — pin `external-secrets.io/v1beta1`.
- **C4** — values-cloud.yaml must specify issuer name + kind.
- **C5** — rewrite AC6.1 to "all existing 1707 remain passing, no
  existing test flips to skipped/xfailed".

Plus the R1..R7 recommendations should be folded in — they are cheap
and all reduce future audit surface.

Re-review after fixes.

---

*Reviewer: gateway-specialist, Project 007.*
