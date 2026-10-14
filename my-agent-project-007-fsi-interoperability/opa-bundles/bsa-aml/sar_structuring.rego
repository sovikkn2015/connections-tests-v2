# METADATA
# title: SAR structuring detection
# description: Detects 3+ mid-band cash transactions in 7 days (31 USC 5324).
# custom:
#   wsp_section: "WSP-BSA-8.1"
#   gap: 4
#   severity: "ESCALATE"
#   oracle: "compliance.gap4_bsa_aml_monitoring.monitors.SarStructuringMonitor"
package authority.bsa_aml.sar_structuring

import rego.v1

# -----------------------------------------------------------------------------
# input contract (same shape as CashTransaction + window_transactions from last 7d):
#   {
#     "txn_id":       "<uuid>",
#     "client_id":    "<uuid>",
#     "category":     "cash_deposit" | "cash_withdrawal" | ...,
#     "amount_usd":   8000.00,
#     "occurred_at":  "RFC3339",
#     "window_transactions": [ <same shape, last 7d> ],
#     "config": {"ctr_threshold": 10000, "sar_structuring_threshold": 7000}
#   }
#
# Anti-tipping-off: route_to is always "compliance_officer". Advisors
# and clients MUST NOT be notified (31 USC 5318(g)(2)).
# -----------------------------------------------------------------------------

# METADATA
# title: Structuring alert
# custom:
#   wsp_section: "WSP-BSA-8.1"
default structuring_alert := false

structuring_alert if {
    lower := input.config.sar_structuring_threshold
    upper := input.config.ctr_threshold
    lower < upper
    # Current txn must be in the mid-band.
    input.category in {"cash_deposit", "cash_withdrawal"}
    input.amount_usd >= lower
    input.amount_usd < upper
    # Mid-band historical txns in window.
    midband := [t |
        t := input.window_transactions[_]
        t.category in {"cash_deposit", "cash_withdrawal"}
        t.amount_usd >= lower
        t.amount_usd < upper
    ]
    # Current txn + historical >= 3.
    count(midband) + 1 >= 3
}

# METADATA
# title: SAR structuring decision
# custom:
#   wsp_section: "WSP-BSA-8.1"
structuring_decision := result if {
    structuring_alert
    result := {
        "decision": "ESCALATE",
        "alert_type": "sar_structuring",
        "reason_code": "structuring_pattern_detected",
        "severity": "critical",
        "route_to": "compliance_officer",
        "do_not_notify": ["advisor", "client"],
        "wsp_section": "WSP-BSA-8.1",
        "rule_applied": "authority/bsa_aml/sar_structuring.v1",
        "legal_ref": "31 USC 5324"
    }
}

structuring_decision := result if {
    not structuring_alert
    result := {
        "decision": "ALLOW",
        "wsp_section": "WSP-BSA-8.1",
        "rule_applied": "authority/bsa_aml/sar_structuring.v1"
    }
}
