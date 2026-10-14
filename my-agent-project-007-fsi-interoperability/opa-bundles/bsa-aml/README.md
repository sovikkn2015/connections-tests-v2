# Gap 4 — BSA/AML OPA Bundle

Phase 3 status: Python monitors in
`src/compliance/gap4_bsa_aml_monitoring/` are the runtime. These
Rego files are oracle-parity targets for Phase 4.

## Rule inventory

| File                     | Package                                | rule_applied                         | wsp_section    |
|--------------------------|----------------------------------------|--------------------------------------|----------------|
| `ctr.rego`               | `authority.bsa_aml.ctr`                | `authority/bsa_aml/ctr.v1`           | `WSP-BSA-8.2`  |
| `sar_structuring.rego`   | `authority.bsa_aml.sar_structuring`    | `authority/bsa_aml/sar_structuring.v1`| `WSP-BSA-8.1` |

Every `.rego` file in this directory MUST carry a `wsp_section`
annotation in a `# METADATA` block per steering rule 19.

## Anti-tipping-off (31 USC §5318(g)(2))

Every decision output MUST set:

```
"route_to": "compliance_officer"
"do_not_notify": ["advisor", "client"]
```

Tipping off the subject of a SAR is a federal felony. Do not
modify these invariants.

## Oracle parity

The Phase-1/2 Python engine remains the test oracle during
migration:

1. Feed the same `input` (CashTransaction + window_transactions)
   to the Python monitor and the OPA sidecar.
2. Assert the outputs are structurally equal for the `decision`
   field.
3. Drift → test fails.
