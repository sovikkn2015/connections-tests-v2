# METADATA
# title: DORA ICT Incident Reporting
# description: Deterministic OPA rules for EU Digital Operational Resilience Act
#   (DORA) — initial notification deadlines and intermediate report
#   requirements for major ICT-related incidents.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   jurisdiction: "EU"
#   severity: "BLOCK"
package jurisdiction.eu.dora_incident

import rego.v1

# ── Initial notification — 4-hour deadline ───────────────────────

# METADATA
# title: DORA initial incident notification — 4-hour deadline
# description: DORA Article 19 requires financial entities to submit an initial
#   notification to the competent authority within 4 hours of classifying
#   a major ICT-related incident. BLOCK if deadline exceeded without
#   notification.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_initial_notification := result if {
	input.jurisdiction == "EU"
	input.incident_classified == true
	input.incident_severity == "major"
	input.hours_since_classification > 4
	input.initial_notification_sent == false
	result := {
		"decision": "BLOCK",
		"reason": "DORA Art. 19: initial notification required within 4 hours of major ICT incident classification. Deadline exceeded.",
		"rule": "jurisdiction/eu/dora_incident.rego:check_initial_notification",
		"wsp_section": "10.3",
		"deadline_hours": 4,
		"hours_elapsed": input.hours_since_classification,
		"incident_severity": "major",
	}
}

# ── Intermediate report — 72-hour deadline ───────────────────────

# METADATA
# title: DORA intermediate incident report — approaching deadline
# description: DORA Article 19 requires an intermediate report within 72 hours
#   of the initial notification. WARN if approaching deadline (>48 hours
#   elapsed).
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_intermediate_report_approaching := result if {
	input.jurisdiction == "EU"
	input.incident_classified == true
	input.incident_severity == "major"
	input.initial_notification_sent == true
	input.hours_since_initial_notification > 48
	input.hours_since_initial_notification <= 72
	input.intermediate_report_sent == false
	result := {
		"decision": "WARN",
		"reason": sprintf("DORA Art. 19: intermediate report deadline approaching. %d of 72 hours elapsed.", [input.hours_since_initial_notification]),
		"rule": "jurisdiction/eu/dora_incident.rego:check_intermediate_report_approaching",
		"wsp_section": "10.3",
		"deadline_hours": 72,
		"hours_elapsed": input.hours_since_initial_notification,
		"hours_remaining": 72 - input.hours_since_initial_notification,
	}
}

# METADATA
# title: DORA intermediate incident report — deadline exceeded
# description: DORA Article 19 intermediate report deadline exceeded (>72 hours).
#   BLOCK further operations until report is submitted.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_intermediate_report_overdue := result if {
	input.jurisdiction == "EU"
	input.incident_classified == true
	input.incident_severity == "major"
	input.initial_notification_sent == true
	input.hours_since_initial_notification > 72
	input.intermediate_report_sent == false
	result := {
		"decision": "BLOCK",
		"reason": "DORA Art. 19: intermediate report deadline exceeded (72 hours). Submit report immediately.",
		"rule": "jurisdiction/eu/dora_incident.rego:check_intermediate_report_overdue",
		"wsp_section": "10.3",
		"deadline_hours": 72,
		"hours_elapsed": input.hours_since_initial_notification,
		"incident_severity": "major",
	}
}

# ── ICT third-party register — must be maintained ────────────────

# METADATA
# title: DORA ICT third-party register — not current
# description: DORA Article 28 requires financial entities to maintain a register
#   of all ICT third-party service providers. The register must be kept
#   current and reported to competent authorities annually. WARN if the
#   register has not been updated within the required period.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_ict_register := result if {
	input.jurisdiction == "EU"
	input.ict_register_maintained == true
	input.ict_register_days_since_update > 90
	result := {
		"decision": "WARN",
		"reason": sprintf("DORA Art. 28: ICT third-party register not updated in %d days. Quarterly update required.", [input.ict_register_days_since_update]),
		"rule": "jurisdiction/eu/dora_incident.rego:check_ict_register",
		"wsp_section": "10.3",
		"requirement": "ict_register_update",
		"days_since_update": input.ict_register_days_since_update,
		"update_frequency": "quarterly",
	}
}

# METADATA
# title: DORA ICT third-party register — missing
# description: DORA Article 28 requires an ICT third-party register. BLOCK if
#   no register is maintained.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_ict_register_missing := result if {
	input.jurisdiction == "EU"
	input.ict_register_maintained == false
	result := {
		"decision": "BLOCK",
		"reason": "DORA Art. 28: ICT third-party register must be maintained. No register found.",
		"rule": "jurisdiction/eu/dora_incident.rego:check_ict_register_missing",
		"wsp_section": "10.3",
		"requirement": "ict_register",
	}
}
