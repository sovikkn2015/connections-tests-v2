# LLMJ Review v2 — Ops Hardening Wave 2 (v0.2.0)

**Reviewer**: Pipeline and Intent Specialist (LLMJ mode)
**Target**: `.kiro/specs/ops-hardening-wave2-intelligence-layer.md` v0.2.0
**Date**: 2026-05-02
**Mode**: Harsh. Must score 8.0+/10 for unconditional GO per task prompt.

---

## RF Verification Against v0.2.0

| v1 Fix | Resolved? | Evidence |
|---|---|---|
| RF1 StatefulSet/Deployment kind | YES | R9.2 table explicit `kind: StatefulSet` (M8) + `kind: Deployment` (M9, M12) |
| RF2 PriorityClass | YES | R9.2 both patterns listed; R7 sets the values |
| RF3 Probes | YES | R9.2 both `readinessProbe:` and `livenessProbe:` required across M8/M9/M12 |
| RF4 HPA 70 literal | YES | R9.2 literal `averageUtilization: 70` |
| RF5 Pod securityContext | YES | R5.6 pod-level + container-level; R9.2 grep on `runAsNonRoot: true` + `readOnlyRootFilesystem: true` |
| RF6 Image digest fallback | YES | §2.3 explicit Go template branching |
| RF7 Checkpointer DSN wiring | YES | §2.4 ExternalSecret contract documented; Wave 3 ships actual CRD |
| RF8 Credential grep pattern | YES | R9.4 regex + exclusion list |
| RF9 M12 extraIngressFrom | YES | §2.5 values schema + template range loop |
| RF10 Append-safe sentinel | YES | §2.7 grep -qF idempotency logic |
| RF11 SKIP banner | YES | R9.1 + §2.7 |
| RF12 M12 imports justification | YES | §4.8 references M12 v0.2.0 COMPLETE spec SPECIALIST_DISPATCH |
| RF13 M6-only ingress test | YES | R9.2 podSelector grep |
| RF14 Resources | YES | R5.7 concrete defaults |
| RF15 Python YAML fallback | YES | R9.5 + T8.4 |
| RF16 COMPLETE marker schema | YES | §2.8 six-section schema |
| RecF1 Chart version semver | YES | §2.3 note |
| RecF2 Dispatch mode flag | YES | R3.25 + §4.9 |

**All 16 required fixes resolved. 3 of 5 recommended fixes addressed; 3 deferred to Wave 3 with explicit documentation.**

---

## Scorecard v2

| Dimension | Weight | Raw | Weighted | Notes |
|---|---|---|---|---|
| Completeness | 25% | 8.8 | 2.20 | All 16 RF resolved; R9.2 table exhaustively covers verification gates |
| Accuracy | 20% | 8.8 | 1.76 | Env vars, model IDs, Vault paths all match existing `.env.example`s; SCHEMA_VERSION values correct (M8=1.0.0, M9=1.1.0, M12=0.2.0) |
| Security | 20% | 9.0 | 1.80 | Pod securityContext complete (runAsNonRoot, readOnlyRootFilesystem, drop ALL caps, seccomp RuntimeDefault, fsGroup), IRSA+Vault path design, NetworkPolicy default-deny, credential grep with explicit exclusions |
| Testability | 15% | 8.5 | 1.275 | R9.2 14-row assertion table; credential regex spelled out; Python YAML fallback for dev boxes; SKIP semantics distinguishable |
| Design Alignment | 10% | 9.0 | 0.90 | M7-as-library decision tied to Rule 9; M8 StatefulSet rationale tied to HITL 4h state; M9 system-node-critical tied to request path; KYC URL ConfigMap/key Vault split tied to task prompt |
| Gaps | 10% | 7.5 | 0.75 | Minor: template `_helpers.tpl` absent by design (acknowledged for Wave 3); ServiceMonitor/ topologySpread/ PodAntiAffinity deferred but documented |

**Total: 8.685/10 → GO** (target 8.0+, clears threshold)

---

## Residual Minor Items (non-blocking, address during build)

### M1 — `yq` dependency in §2.7 test script
The illustrative test script uses `yq` to slice values fragment per sub-chart. Build should use pure `awk/sed` or a `--set`-based helm template call instead, to avoid adding `yq` as a tool dependency. Document chosen approach in the actual script. Non-blocking.

### M2 — CN / SAN for cert-manager Certificate
The Certificate resource should declare `dnsNames: [m{N}-*.{{ .Release.Namespace }}.svc.cluster.local]` for SAN. Obvious implementation detail but worth noting. Non-blocking.

### M3 — PDB `.spec.selector.matchLabels`
Must match the workload's `.spec.template.metadata.labels`. Explicit label convention in §2.3 adequate; implementation must be correct. Non-blocking.

### M4 — NetworkPolicy port protocol
NetworkPolicy ports should be `protocol: TCP` (default is TCP but explicit is better). Non-blocking.

### M5 — ConfigMap immutable + annotations
Consider `immutable: true` on the ConfigMap to prevent accidental edits. Use `apiVersion: v1`. Ensure all env-var keys also reflected in the Deployment's `envFrom`. Non-blocking.

### M6 — Chart.yaml `dependencies` — N/A for sub-charts
Sub-charts don't declare dependencies; they are dependencies of the umbrella. Make sure Chart.yaml does NOT accidentally include a `dependencies:` block. Non-blocking.

### M7 — M9 `<tenant_id>` placeholder in Vault path template
`M9_TENANT_HMAC_KEY_VAULT_PATH=secret/data/m9/tenants/<tenant_id>/hmac_key` — the `<tenant_id>` is a template placeholder, but some ConfigMap parsers may choke on angle brackets. Document that the library substitutes the tenant_id at lookup time, not the ConfigMap. Non-blocking.

---

## Verdict

**8.69/10 → GO.**

All 16 RF resolved. Security posture complete. Verification gates enforced by explicit grep table. 7 minor items for build-time attention (none block progress).

Proceed to Step 5: Build.
