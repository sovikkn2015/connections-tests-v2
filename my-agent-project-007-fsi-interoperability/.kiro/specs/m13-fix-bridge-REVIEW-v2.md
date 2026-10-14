# M13 FIX Bridge — LLMJ Review v2

> Reviewer: Self-LLMJ (harsh, specific, scored)
> Spec version reviewed: v2 (post-REVIEW-v1 fixes)
> Requires: score ≥ 8.0 for GO

---

## Summary per-dimension scoring

| Dim | Weight | Score v1 | Score v2 | Weighted v2 |
|---|---|---|---|---|
| Completeness | 25% | 6.5 | 8.5 | 2.125 |
| Accuracy vs steering rules | 20% | 7.0 | 8.5 | 1.700 |
| Security (creds/MNPI/boundary) | 20% | 7.0 | 8.5 | 1.700 |
| Testability | 15% | 7.5 | 9.0 | 1.350 |
| Design alignment (ARCH-09 + Rule 11) | 10% | 8.0 | 9.0 | 0.900 |
| Gaps called out | 10% | 6.0 | 8.0 | 0.800 |
| **TOTAL** | | **6.95** | | **8.575 / 10** |

**Verdict: GO.** 8.575 > 8.0 threshold.

---

## v1-fix verification (all 9 required)

| # | v1 Issue | v2 Status |
|---|---|---|
| Q1 | FakeFixEngine ExecReport hook | FIXED — §2.3 `simulate_inbound_exec_report`, `set_inbound_callback` in protocol |
| Q2 | KillSwitchInput model | FIXED — R10 defines the model with scope/venue/state/reason + cross-field rule |
| Q3 | AID header + claims mechanics | FIXED — R13.1-R13.6 spells out header, claims, role gate, modes; every tool requires AID; only kill_switch requires role |
| Q4 | HMAC-salted account hash | FIXED — R6.3 + D10, Vault-backed salt, tests inject static |
| Q5 | Helm template inventory | FIXED — §6.2 explicitly lists 11 files + explains why |
| Q6 | session_status error cases | FIXED — R2.5 spells out unknown-venue, known-not-connected, disabled-mode |
| Q7 | FIX_ENABLED=false behavior | FIXED — R4.1 + R2.5 + dispatcher step 6 + GET / health |
| Q8 | Concurrency callout | FIXED — D8 enumerates 4 shared-state sources + locks |
| Q9 | Test filename consistency | FIXED — renamed to `test_m13_fix_config.py` in §3.1 |

## v1 recommended (4 items)

| # | Issue | v2 Status |
|---|---|---|
| Q10 | trader_aid correlation | FIXED — R6.1 defines cl_ord_id correlation + orphan handling |
| Q11 | VenueConfig pydantic model | FIXED — R4.1 explicit field list |
| Q12 | FIX 4.4 vs 4.2 | FIXED — R3 header + §5 non-goal |
| Q13 | Vault-to-session integration test | FIXED — §4 traceability R4.1 → test_m13_integration.py |

---

## What's strong in v2

- **Rule 11 compliance** is defended in D1 (StatefulSet rationale) and §6.2 (single-replica + PDB maxUnavailable:0).
- **Rule 33 discipline**: D9 explicitly rejects m11_python_adapters_shared reuse and calls out the tradeoff. The AST-scan test (T12) enforces this mechanically.
- **Rule 8 fail-closed**: R4.1 refuses startup on invalid VenueConfig; R6.4 won't silently drop drop-copy failures; R7.4 keeps inbound ExecReports flowing regardless of kill state.
- **Rule 6 three-tier audit**: stdout → M10 sidecar (Rule 33-safe) for both tool_audit and session_event kinds. Explicit kind vocabulary in R8.
- **Rule 20 zero credentials**: every secret is a Vault path (session config, sender/target ComIDs, mTLS, AID verify secret, HMAC salt).
- **Rule 23 isolation**: D8 shows in-pod per-venue isolation is safe + multi-pod-per-venue is the overlay path.
- **Rule 32 strict validation**: R10 lists every model with `extra="forbid", strict=True`, enum values, regex patterns, cross-field rules.
- **FIX MsgType matrix** in R3 is comprehensive — every in-scope type has a note; out-of-scope types are explicit.
- **Test budget** has 35% headroom above the 80-test floor (114 target).
- **Design decisions are defended, not asserted** (D1-D10).

## Remaining minor items (non-blocking)

1. `__init__.py` public surface for `m13_fix_bridge` package not explicitly listed — builder should expose `create_app`, `FixConfig`, `FakeFixEngine`, `StaticAidVerifier` for import convenience. (Build-time concern.)
2. Wave-4 allowlist template rendering pattern for `networkpolicy.yaml` — the existing m11-grpc-adapter chart uses `- {}` wildcard egress; for Wave-4 we mirror the egress-narrowing pattern from values-cloud.yaml. Builder tackles in T15.
3. `simplefix` import version not pinned in the spec — Dockerfile T13 should pin `simplefix>=1.0.17,<2.0`. (Build-time concern.)

None of these block the spec review. They are implementation notes for the builder.

---

## Final verdict: GO at 8.575/10

Proceed to BUILD (T2-T19).
