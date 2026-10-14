# Vendor Schema Drift Playbook

Spec AC15.6. 48-hour SLA workflow.

## Trigger

1. `emoney.raw_plan_rejected` — eMoney returned a top-level field not in `EMoneyPlanSummaryOutput`.
2. `orion.path_unverified` — Orion returned 404 on an assumed path.
3. `vendor_invalid_json` twice in a row (schema malformation).
4. `Retry-After` header format change.

## Step-by-Step

### 1. Fail-Closed (Automatic)
Adapter refuses payload. Callers see `emoney_raw_plan_forbidden` or similar. No MNPI leakage.

### 2. Capture Field Names (Automatic)
Pino event `{vendor}.raw_field_observed` — NAMES only (AC15.6). M10 sidecar forwards to compliance queue.

### 3. Compliance SME Review (48h SLA)
SME classifies:
- **(a) Safe summary** — benign display field, belongs on allow-list.
- **(b) MNPI-like** — PII / MNPI / privileged. Stay BLOCKED.
- **(c) Unknown** — escalate to vendor account manager.

### 4. Resolution Path (a) — Expand Allow-List
1. Adapter spec bump (MINOR).
2. Add to Zod output schema.
3. Regression test (new field accepted + non-allow-listed field rejected).
4. Update `DECISION-LOG.md` with SME name + rationale.
5. Update `tests/integration/test_m7_emoney_allowlist.py`.
6. Coordinate with M7 owner for same release train.
7. GitOps deploy via ArgoCD.

### 4b. Resolution Path (b) — Stay Blocked
1. Log decision in `DECISION-LOG.md`.
2. File vendor ticket.
3. Escalate repeated occurrences.

### 4c. Resolution Path (c) — Escalate
1. Keep BLOCKED.
2. 30-day SLA; default at day 30 = Path (b).

## Roles

| Role | Responsibility |
|------|----------------|
| Adapter Specialist | Allow-list changes + regression tests. |
| Compliance SME | Classification (a/b/c). |
| M7 Owner | Canonical type expansion. |
| Firm Operator | GitOps deploy + monitoring. |

## Audit Trail

Every invocation generates one M10 audit entry:

```json
{
  "event": "vendor_schema_drift_resolved",
  "vendor": "emoney",
  "field_names": ["newField"],
  "path": "a",
  "sme": "[SME-name-placeholder]",
  "decided_at": "2026-05-05T14:22:00Z"
}
```

## References

- Spec AC15.6 + Appendix E row 25.
- §Observability Hand-Off to M10.
