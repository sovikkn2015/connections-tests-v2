# LLMJ Review — Ops Hardening Wave 2 (v0.1.0)

**Reviewer**: Pipeline and Intent Specialist (LLMJ mode)
**Target**: `.kiro/specs/ops-hardening-wave2-intelligence-layer.md` v0.1.0
**Date**: 2026-05-02
**Mode**: Harsh. Every gap called out. No benefit of the doubt.

---

## Scorecard (weighted)

| Dimension | Weight | Raw | Weighted | Notes |
|---|---|---|---|---|
| Completeness | 25% | 7.5 | 1.875 | Covers scope but misses a few verification gate specifics |
| Accuracy | 20% | 8.0 | 1.60 | Env vars match .env.examples; pin versions reasonable |
| Security | 20% | 7.0 | 1.40 | Good IRSA/Vault posture, gaps in pod security context, image digest strategy vague |
| Testability | 15% | 6.5 | 0.975 | Shell tests defined but shallow; no assertion on PriorityClass, no assertion on StatefulSet/Deployment kind |
| Design Alignment | 10% | 8.0 | 0.80 | Matches ARCH-09 roles; M7-as-library decision well-justified |
| Gaps | 10% | 6.5 | 0.65 | Missing: M8 checkpointer DSN strategy, M12 specialists unpacking, ImagePullSecret |

**Total: 7.30/10 → CONDITIONAL GO** (need 7.5+ for unconditional GO)

---

## Required Fixes (must address before build)

### RF1 — StatefulSet / Deployment kind check missing from test_helm_template_intelligence.sh
R10.2 says "M8 uses StatefulSet; M9+M12 use Deployment — verified via grep kind:". But R9.2 only enumerates three grep assertions (IRSA annotation, mTLS mount, HPA presence). Add a fourth: grep `^kind: StatefulSet` against M8 render and `^kind: Deployment` against M9+M12 renders.

### RF2 — PriorityClass not tested
R7 defines PriorityClass per module and R10.7 claims a verification gate, but no test script line enforces it. Add grep assertion: `priorityClassName: system-cluster-critical` in M8+M12 renders, `priorityClassName: system-node-critical` in M9 render.

### RF3 — readinessProbe/livenessProbe not tested
R5.4 requires both probes on every workload and R10.3 cites a gate, but test_helm_template_intelligence.sh has no grep for `readinessProbe:` and `livenessProbe:`. Add explicit assertions.

### RF4 — HPA target CPU utilization ≤ 70% not tested literally
R10.4 says "Grep averageUtilization: 70 in rendered HPA" but R9.2 only checks HPA presence. Add a literal grep on `averageUtilization: 70`.

### RF5 — Pod securityContext omitted
Non-root UID 1000 is set in Dockerfile (R2.2), but the Pod spec MUST also declare:
- `runAsNonRoot: true`
- `runAsUser: 1000`
- `runAsGroup: 1000`
- `allowPrivilegeEscalation: false`
- `readOnlyRootFilesystem: true`
- `capabilities.drop: [ALL]`
- `seccompProfile.type: RuntimeDefault`

Without these, a compromised image could still be scheduled as root. Add a Pod-level `securityContext` and container-level `securityContext` to each workload template and add a grep assertion in the test.

### RF6 — Image pull strategy undefined
`image.digest` placeholder is mentioned but the deployment template must use `image: {{ .repo }}@{{ .digest }}` when digest is present, else `{{ .repo }}:{{ .tag }}`. Spec must state this fallback logic explicitly. Also declare `imagePullPolicy: IfNotPresent` default.

### RF7 — M8 checkpointer DSN secret wiring not described
R3.5 defines `M8_CHECKPOINTER_DSN_VAULT_PATH` as a Vault path, but the spec does not show how the pod actually gets the DSN. Options: (a) Vault Agent Injector sidecar, (b) Secrets Store CSI Driver, (c) external-secrets-operator. Pick one and document the envFrom/valueFrom pattern. Recommended: external-secrets-operator with ExternalSecret CRD (out of Wave 2 scope but document the contract the ConfigMap/env assumes).

### RF8 — Credential-shape grep check underspecified
§5 lists "No credentials in any file (verified by grep)" but the grep pattern is not defined. Define the sentinel regex that will be run against all Wave 2 files: `(?i)(password|secret|token|api[_-]?key)\s*[:=]\s*['\"]?[A-Za-z0-9+/=]{16,}`. Exclude Vault paths (`vault_path`, `VAULT_PATH`) from match.

### RF9 — M12 NetworkPolicy "extra ingress" mechanism not shown
R4.5 says M12 accepts ingress from m1-identity "via values extraIngressFrom list" but does not show the values.yaml structure or the template loop. Provide the explicit schema: `networkPolicy.extraIngressFrom: [{namespace: ..., podLabels: {...}, ports: [...]}, ...]` and the matching `range` block.

### RF10 — Append-safe test script sentinel collision risk
R9.1 uses sentinel `### WAVE2_LINT_BLOCK ###`. If Wave 1 creates the file with a trailing EOF before the sentinel location, the append logic must handle that. Spec must state: "detect sentinel with `grep -qF`; if absent, append `\n` separator then the sentinel block". Also, the append path must be idempotent — running the script twice must not duplicate the block.

### RF11 — Graceful skip semantics vague
"Exit 0 if helm is not installed" is stated but if the shell test exits 0 without asserting anything, it provides false positives. Require the script to emit `SKIP: helm not installed` to stderr AND exit with a distinguishable code — since standard shell test runners treat exit 0 as pass, keep exit 0 but require the SKIP banner to stderr so CI can grep it.

### RF12 — M12 supervisor pulls M8+M9 into one image (T1.3) — justify
T1.3 copies both `src/m8_pipeline_engine` and `src/m9_intent_router` into the M12 image "in-process for Phase 2 lighthouse". This contradicts Rule 9 "strict module boundaries — no cross-module imports". Clarify: in Phase 2 the M12 supervisor library IS permitted to import M9 and M8 because the supervisor is glue (see M12 spec v0.2.0). In a production container, however, the image copies are bundled for the library's test/fallback code paths; the runtime call is HTTP to M9/M8 services via the URLs in R3.23/R3.24. Explicitly state: "Library import permitted for SUPERVISOR; runtime calls are HTTP. Image bundles source for offline/fallback tests but the live path uses the remote service."

### RF13 — No test for "only M6 can ingress"
R4.5 requires NetworkPolicy sources M6 only, but the test script does not grep for it. Add: `podSelector.*app:\s*m6-mcp-gateway` must appear in each rendered NetworkPolicy.

### RF14 — resources requests/limits not specified numerically
Each workload must declare `resources.requests` and `resources.limits`. Add defaults to values.yaml:
- M8 (heavy, Sonnet calls): requests cpu 500m mem 1Gi, limits cpu 2000m mem 4Gi
- M9 (fast, Haiku routing): requests cpu 200m mem 256Mi, limits cpu 1000m mem 1Gi
- M12 (mid, fan-out orchestration): requests cpu 300m mem 512Mi, limits cpu 1500m mem 2Gi

### RF15 — Shell scripts not tested on this machine — verify YAML renders parse
Since helm is not installed on this machine, the spec MUST include a Python-level fallback check: for each chart directory, `python3 -c "import yaml; yaml.safe_load(open(f))"` on every `Chart.yaml`, `values.yaml`, and `templates/*.yaml` (ignoring Go template directives via a minimal pre-processor or only testing Chart.yaml + values.yaml which are pure YAML). Add this as a test step so the build is verifiable on dev boxes.

### RF16 — COMPLETE marker gate criteria underspecified
T9 says "written only after T8 gates pass" but does not enumerate the markdown contents. Require the COMPLETE marker to include:
- The scorecard
- List of delivered artifacts with file paths
- Test results (Python pytest summary line + shell test summary)
- Non-negotiables checklist (all 10 verification gates)

---

## Recommended Fixes (nice to have)

### RecF1 — Add a `chart.version` bump rule
Future revisions should bump chart `version:` in Chart.yaml. Note the semver convention: patch for template-only changes, minor for values schema additions, major for values schema breaks.

### RecF2 — Document upgrade path from Phase 2 in-process to Phase 3 network
M12 calls M9/M8 in-process today. Phase 3 moves to HTTP. Note the flip flag: `M12_DISPATCH_MODE=local|remote`, default `local` for Wave 2, flip to `remote` in Wave 3.

### RecF3 — Add ServiceMonitor stub for Prometheus
Prometheus Operator ServiceMonitor for `/metrics` scraping. Deferred to a future wave but note the chart will add it.

### RecF4 — Add a `topologySpreadConstraints` block
Spread pods across zones for HA. Add to values.yaml as optional.

### RecF5 — Add PodAntiAffinity for M9 + M12
Since HPA scales these horizontally, prefer PodAntiAffinity so replicas land on different nodes.

---

## Fix Traceability Table

| Fix | Addressed in v0.2.0 § |
|---|---|
| RF1 StatefulSet/Deployment kind check | §R9.2 + §Design 2.7 |
| RF2 PriorityClass tested | §R9.2 |
| RF3 Probes tested | §R9.2 |
| RF4 HPA CPU 70 literal | §R9.2 |
| RF5 Pod securityContext | new §R5.6 + R9.2 |
| RF6 Image digest fallback | §Design 2.3 |
| RF7 Checkpointer DSN wiring | §Design 2.4 |
| RF8 Credential grep pattern | §R9.4 |
| RF9 M12 extraIngressFrom schema | §Design 2.5 |
| RF10 Append-safe sentinel | §Design 2.7 |
| RF11 SKIP banner | §R9 |
| RF12 M12 import justification | §Design 4.2 + 4.8 |
| RF13 "Only M6 ingress" test | §R9.2 |
| RF14 Resource requests/limits | new §R5.7 + values.yaml |
| RF15 YAML Python fallback | new §T7 addition |
| RF16 COMPLETE marker contents | §T9 + §7 |

---

## Verdict

**7.30/10 CONDITIONAL GO.**

Spec has the right scaffolding but misses enforcement teeth on verification gates. 16 required fixes. Fix and re-review; expect 8.0+ after fixes land.
