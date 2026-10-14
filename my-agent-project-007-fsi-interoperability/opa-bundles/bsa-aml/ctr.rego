# METADATA
# title: CTR threshold check
# description: Flags cash deposits/withdrawals >= $10,000 per 31 CFR §1010.311
# custom:
#   wsp_section: "WSP-BSA-8.2"
#   gap: 4
#   severity: "ESCALATE"
#   oracle: "compliance.gap4_bsa_aml_monitoring.monitors.CtrMonitor"
package authority.bsa_aml.ctr

import rego.v1

# -----------------------------------------------------------------------------
# input contract (same shape as compliance.gap4_bsa_aml_monitoring.models.CashTransaction):
#   {
#     "txn_id":       "<uuid>",
#     "client_id":    "<uuid>",
#     "category":     "cash_deposit" | "cash_withdrawal" | "wire_in" | "wire_out",
#     "amount_usd":   10000.00,
#     "occurred_at":  "RFC3339",
#     "window_transactions": [ <same shape, last 24h> ],
#   }
# -----------------------------------------------------------------------------

# METADATA
# title: Single transaction CTR trigger
# custom:
#   wsp_section: "WSP-BSA-8.2"
default ctr_single := false

ctr_single if {
    input.category in {"cash_deposit", "cash_withdrawal"}
    input.amount_usd >= 10000
}

# METADATA
# title: 24h aggregate CTR trigger
# custom:
#   wsp_section: "WSP-BSA-8.2"
default ctr_aggregate := false

ctr_aggregate if {
    some total
    total := sum([t.amount_usd |
        t := input.window_transactions[_]
        t.category in {"cash_deposit", "cash_withdrawal"}
    ])
    total > 10000
}

# METADATA
# title: CTR decision (composite)
# custom:
#   wsp_section: "WSP-BSA-8.2"
ctr_decision := result if {
    ctr_single
    result := {
        "decision": "ESCALATE",
        "alert_type": "ctr_threshold",
        "reason_code": "ctr_threshold_exceeded",
        "severity": "high",
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "WSP-BSA-8.2",
        "rule_applied": "authority/bsa_aml/ctr.v1"
    }
}

ctr_decision := result if {
    not ctr_single
    ctr_aggregate
    result := {
        "decision": "ESCALATE",
        "alert_type": "ctr_aggregate",
        "reason_code": "ctr_aggregate_exceeded",
        "severity": "high",
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "WSP-BSA-8.2",
        "rule_applied": "authority/bsa_aml/ctr.v1"
    }
}

ctr_decision := result if {
    not ctr_single
    not ctr_aggregate
    result := {
        "decision": "ALLOW",
        "wsp_section": "WSP-BSA-8.2",
        "rule_applied": "authority/bsa_aml/ctr.v1"
    }
}
