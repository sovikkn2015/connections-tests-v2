# LLMJ Review v2 — ops-hardening-wave1-trust-layer.md

> Reviewer: **gateway-specialist** (self-review, v2 pass).
> Reviewed: `.kiro/specs/ops-hardening-wave1-trust-layer.md` after the v2
> rewrite addressing all issues from REVIEW v1 (CONDITIONAL GO 7.35/10).

## Verification — v1 fixes

| Review ID | v1 Finding | v2 Verification |
|-----------|-----------|-----------------|
| **C1** helm baseline  | v1 flagged no min helm version | **FIXED** §2.8 pins `helm ≥ 3.14` baseline, notes v4 supported |
| **C2** port contract   | v1 flagged 8080/8443 contradiction | **FIXED** §2.2 rewritten: single uvicorn listener on 8080, Service maps 8443→8080. AC1.7, AC2.4, AC3.3, AC3.8 all aligned. |
| **C3** ES CRD pin      | v1 flagged unpinned ExternalSecret CRD | **FIXED** §2.6 + AC3.3 pin `external-secrets.io/v1beta1` |
| **C4** issuer pin      | v1 flagged missing issuer ref | **FIXED** AC3.2 + AC3.3 + §2.3 pin `certManager.issuerKind: ClusterIssuer` + `issuerName` |
| **C5** test invariant  | v1 flagged brittle count | **FIXED** AC6.1 rewritten to "existing tests remain in same pytest status; no flips, no deletions" |
| **R1** OCI labels      | v1 asked for explicit list + URL | **FIXED** AC2.8 lists 5 labels + OCI URL |
| **R2** store name      | v1 asked for named ClusterSecretStore | **FIXED** AC3.2 + §2.6 pin `vault-cluster-store` |
| **R3** PodSecurity     | v1 asked for restricted PSA | **FIXED** AC3.9 added: runAsNonRoot, readOnlyRootFilesystem, caps drop ALL, seccomp RuntimeDefault |
| **R4** HPA apiVersion  | v1 asked for `autoscaling/v2` | **FIXED** AC3.4 pins `autoscaling/v2` |
| **R5** compose network | v1 asked for named net | **FIXED** AC4.4 named `007-trust-layer` |
| **R6** helm v4 warnings | v1 asked for v4 cleanliness | **FIXED** AC3.1 + §2.8 cover keywords/maintainers + baseline |
| **R7** rollback        | v1 asked for rollback doc | **FIXED** §2.9 added |
| **G1** no import test  | v1 noted gap | **ACKNOWLEDGED** §4 out-of-scope |
| **G2** 3-topology ack  | v1 asked for explicit out-of-scope | **FIXED** §4 explicitly says no placeholder files |
| **G3** script cwd      | v1 asked for path-resilience | **FIXED** AC5.4 requires `cd "$(dirname "$0")/.."` |
| **G4** pull-policy doc | v1 asked for per-tenant overlay note | **FIXED** AC3.5 + values defaults documented |

All 12 items from REVIEW v1 are either fixed in the v2 spec or
explicitly pushed to Out of Scope with a rationale. No regressions
introduced.

## Scoring (v2)

| Dimension | Weight | v1 | v2 | Weighted v2 | Comment |
|-----------|-------:|---:|---:|------------:|---------|
| Completeness       | 25% | 7.0 | 8.5 | 2.125 | Every AC now references a concrete API version / CRD / mount path. |
| Accuracy           | 20% | 7.5 | 8.5 | 1.70  | Port contract and CRD versions now match helm lint reality. |
| Security           | 20% | 8.0 | 9.0 | 1.80  | AC3.9 adds restricted PSA; §2.6 pins ExternalSecret CRD; Vault path convention pinned. |
| Testability        | 15% | 7.0 | 8.5 | 1.275 | AC6.1 now deterministic (status preservation) rather than count threshold. |
| Design alignment   | 10% | 8.5 | 9.0 | 0.90  | §2.2 now matches the existing M6/M10 Dockerfile single-listener reality instead of introducing a second listener. |
| Gaps               | 10% | 6.0 | 7.5 | 0.75  | G1–G4 either resolved or explicitly deferred. The remaining gap is the deferred in-process import test — acknowledged. |
| **Overall**        |     |     |     | **8.55 / 10** | **GO** |

**Verdict: GO.** Score 8.55/10 > 8.0 threshold. All five C-blockers fixed, all seven R-recommendations folded in, the four G-gaps either closed or explicitly deferred with rationale.

## Remaining minor items (non-blocking, fold into build)

- **M1** Add a one-line comment at the top of each new FastAPI `app.py`
  noting "mTLS terminates upstream; single 8080 listener" so the
  on-call engineer reading the file in isolation knows the port story.
- **M2** The three shell scripts should echo their own name + cwd on
  startup so CI logs tell you exactly where they ran from.
- **M3** When writing the four `NetworkPolicy` templates, the M6
  variant differs (allows inbound from `part-of: 007-fsi`), so the
  helpers library should factor the "allow from M6" block but let M6
  override. Low-risk but saves duplication.
- **M4** `values-cloud.yaml` placeholder strings (`letsencrypt-prod`,
  `vault-cluster-store`) should be called out as `# OVERRIDE PER TENANT`
  in inline comments so a per-tenant overlay author can grep them.
- **M5** The docker-compose file should bind its Postgres and Vault
  ports to `127.0.0.1:*` not `0.0.0.0:*` so a laptop dev's open
  network doesn't expose Vault dev-mode.

None of M1–M5 block the build. All are implementation-time reminders.

## Approval

Spec is **GO for build**. Proceed to Step 5.

Reviewer: gateway-specialist, Project 007. v2 complete.
