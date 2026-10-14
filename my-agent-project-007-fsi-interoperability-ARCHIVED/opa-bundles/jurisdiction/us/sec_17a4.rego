# METADATA
# title: SEC Rule 17a-4 Record Retention
# description: Deterministic OPA rules for SEC Rule 17a-4 record retention —
#   minimum retention periods and WORM storage requirements for
#   broker-dealer books and records.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   jurisdiction: "US"
#   severity: "BLOCK"
package jurisdiction.us.sec_17a4

import rego.v1

# ── Retention period — trade records 6 years ─────────────────────

# METADATA
# title: SEC 17a-4 trade record retention — 6 years minimum
# description: Trade blotters, order tickets, and account statements must be
#   retained for a minimum of 6 years per SEC Rule 17a-4(a).
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_retention_period := result if {
	input.jurisdiction == "US"
	input.record_type in {"trade_blotter", "order_ticket", "account_statement"}
	input.retention_years < 6
	result := {
		"decision": "BLOCK",
		"reason": sprintf("SEC Rule 17a-4(a): %s requires minimum 6-year retention. Configured: %d years.", [input.record_type, input.retention_years]),
		"rule": "jurisdiction/us/sec_17a4.rego:check_retention_period",
		"wsp_section": "10.1",
		"record_type": input.record_type,
		"required_years": 6,
		"configured_years": input.retention_years,
	}
}

# METADATA
# title: SEC 17a-4 correspondence retention — 3 years minimum
# description: General correspondence must be retained for a minimum of
#   3 years per SEC Rule 17a-4(b)(4).
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_retention_period_correspondence := result if {
	input.jurisdiction == "US"
	input.record_type == "correspondence"
	input.retention_years < 3
	result := {
		"decision": "BLOCK",
		"reason": sprintf("SEC Rule 17a-4(b)(4): correspondence requires minimum 3-year retention. Configured: %d years.", [input.retention_years]),
		"rule": "jurisdiction/us/sec_17a4.rego:check_retention_period_correspondence",
		"wsp_section": "10.1",
		"record_type": "correspondence",
		"required_years": 3,
		"configured_years": input.retention_years,
	}
}

# ── WORM storage — required for trade records ────────────────────

# METADATA
# title: SEC 17a-4 WORM storage requirement
# description: Trade blotters, order tickets, account statements, and customer
#   complaints must be stored in WORM (Write Once Read Many) storage
#   per SEC Rule 17a-4(f).
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_worm_required := result if {
	input.jurisdiction == "US"
	input.record_type in {"trade_blotter", "order_ticket", "account_statement", "customer_complaint"}
	input.worm_enabled == false
	result := {
		"decision": "BLOCK",
		"reason": sprintf("SEC Rule 17a-4(f): %s requires WORM storage. WORM not enabled.", [input.record_type]),
		"rule": "jurisdiction/us/sec_17a4.rego:check_worm_required",
		"wsp_section": "10.1",
		"record_type": input.record_type,
	}
}
