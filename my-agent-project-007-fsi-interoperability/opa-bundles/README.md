# OPA Bundles — Phase 2 Placeholder

> This directory is reserved for Phase 2 Rego bundles.
> Phase 1 ships the M2/M4 Policy Engine as a Python library
> (see `src/m2_m4_policy_engine/`).

## Phase 2 migration plan (see spec §R12)

Each Phase-1 Python rule will be transcribed to a single Rego package.
Rule IDs are chosen to match OPA/Rego rule paths:

| Phase 1 rule_applied                                 | Phase 2 Rego path                                      | WSP             |
|------------------------------------------------------|--------------------------------------------------------|-----------------|
| `authority/meta/excludes_check.v1`                   | `authority.meta.excludes_check` rule `v1`              | WSP-META-0.2    |
| `authority/advisor/restricted_list.v1`               | `authority.advisor.restricted_list` rule `v1`          | WSP-TRD-3.1     |
| `authority/advisor/trading_window.v1`                | `authority.advisor.trading_window` rule `v1`           | WSP-TRD-3.2     |
| `authority/advisor/chinese_wall.v1`                  | `authority.advisor.chinese_wall` rule `v1`             | WSP-CWL-4.1     |
| `authority/advisor/pod_isolation.v1`                 | `authority.advisor.pod_isolation` rule `v1`            | WSP-POD-5.1     |
| `authority/advisor/read_other_advisor_clients.v1`    | `authority.advisor.read_other_advisor_clients` rule `v1` | WSP-ADV-1.2   |
| `authority/advisor/read_own_clients.v1`              | `authority.advisor.read_own_clients` rule `v1`         | WSP-ADV-1.1     |
| `authority/advisor/concentration_limit.v1`           | `authority.advisor.concentration_limit` rule `v1`      | WSP-RISK-2.1    |
| `authority/principal/review_required.v1`             | `authority.principal.review_required` rule `v1`        | WSP-FINRA-2210  |
| `authority/meta/default_deny.v1`                     | `authority.meta.default_deny` rule `v1`                | WSP-META-0.1    |
| `authority/meta/unknown_action.v1`                   | `authority.meta.unknown_action` rule `v1`              | WSP-META-0.0    |
| `mnpi/client/ssn_visibility.v1`                      | `mnpi.client.ssn_visibility` rule `v1`                 | WSP-MNPI-1.1    |
| `mnpi/client/dob_visibility.v1`                      | `mnpi.client.dob_visibility` rule `v1`                 | WSP-MNPI-1.2    |
| `mnpi/client/tax_id_visibility.v1`                   | `mnpi.client.tax_id_visibility` rule `v1`              | WSP-MNPI-1.3    |
| `mnpi/payment/account_visibility.v1`                 | `mnpi.payment.account_visibility` rule `v1`            | WSP-MNPI-2.1    |
| `mnpi/security/mnpi_check.v1`                        | `mnpi.security.mnpi_check` rule `v1`                   | WSP-MNPI-3.1    |

Each `.rego` file in this directory MUST carry the `wsp_section` as a
metadata annotation (OPA `# METADATA` block) per steering rule 19.

## Planned tree (Phase 2)

```
opa-bundles/
  tier1/          # investment_bank
  tier2/          # asset_manager
  tier3/          # broker_dealer
  tier4/          # independent_ria
  tier5/          # hedge_fund
  common/         # shared rules across tiers
```

## Oracle pattern

The Phase-1 Python engine remains as a contract test oracle during
migration:
1. Feed the same input to the Python engine and the OPA sidecar.
2. Assert the outputs are structurally equal.
3. Drift -> test fails.

No Phase-2 code lives in this directory in Phase 1.
