# METADATA
# title: MAS Technology Risk Management (TRM) Guidelines
# description: Deterministic OPA rules for MAS TRM compliance — incident reporting,
#   penetration testing, and privileged access management for Singapore-regulated FIs.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   jurisdiction: "SG"
#   severity: "BLOCK"
package jurisdiction.sg.mas_trm

import rego.v1

# ── Incident reporting — 1-hour initial notification ─────────────

# METADATA
# title: MAS TRM incident reporting — 1-hour deadline
# description: Significant ICT incidents must be reported to MAS within 1 hour
#   of detection. Stricter than DORA (4 hours).
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_incident_reporting := result if {
	input.jurisdiction == "SG"
	input.incident_detected == true
	input.hours_since_detection > 1
	input.mas_notified == false
	result := {
		"decision": "BLOCK",
		"reason": "MAS TRM requires incident notification within 1 hour. Deadline exceeded.",
		"rule": "jurisdiction/sg/mas_trm.rego:check_incident_reporting",
		"wsp_section": "10.2",
		"deadline_hours": 1,
		"hours_elapsed": input.hours_since_detection,
	}
}

# ── Penetration testing — annual requirement ─────────────────────

# METADATA
# title: MAS TRM annual penetration testing
# description: All financial institutions must conduct penetration testing
#   at least annually per MAS TRM Guidelines.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_penetration_testing := result if {
	input.jurisdiction == "SG"
	input.days_since_last_pen_test > 365
	result := {
		"decision": "BLOCK",
		"reason": "MAS TRM requires annual penetration testing. Last test exceeds 365 days.",
		"rule": "jurisdiction/sg/mas_trm.rego:check_penetration_testing",
		"wsp_section": "10.2",
		"days_since_test": input.days_since_last_pen_test,
		"max_days": 365,
	}
}

# ── Privileged access management ─────────────────────────────────

# METADATA
# title: MAS TRM privileged access controls
# description: Privileged access management required for all critical systems.
#   CIO/CISO must report to board.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_access_controls := result if {
	input.jurisdiction == "SG"
	input.privileged_access_managed == false
	result := {
		"decision": "BLOCK",
		"reason": "MAS TRM requires privileged access management for critical systems.",
		"rule": "jurisdiction/sg/mas_trm.rego:check_access_controls",
		"wsp_section": "10.2",
	}
}
