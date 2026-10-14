# METADATA
# title: GDPR Consent Management
# description: Deterministic OPA rules for GDPR consent — LLM processing consent,
#   cross-border data transfer, and data minimization requirements for
#   EU-regulated entities.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   jurisdiction: "EU"
#   severity: "BLOCK"
package jurisdiction.eu.gdpr_consent

import rego.v1

# ── LLM processing consent — explicit consent required ───────────

# METADATA
# title: GDPR LLM processing consent
# description: GDPR Article 6/Article 9 requires explicit consent for processing
#   personal data through LLM systems. Legitimate interest is insufficient
#   for automated profiling. BLOCK if consent not obtained.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_llm_processing_consent := result if {
	input.jurisdiction == "EU"
	input.processing_type == "llm"
	input.personal_data_included == true
	input.explicit_consent == false
	result := {
		"decision": "BLOCK",
		"reason": "GDPR Art. 6/9: explicit consent required for LLM processing of personal data.",
		"rule": "jurisdiction/eu/gdpr_consent.rego:check_llm_processing_consent",
		"wsp_section": "10.3",
		"requirement": "llm_processing_consent",
		"data_subject_rights": ["right_to_object", "right_to_explanation"],
	}
}

# ── Cross-border data transfer — consent + SCC required ──────────

# METADATA
# title: GDPR cross-border data transfer
# description: GDPR Chapter V requires adequate safeguards for cross-border
#   transfers of personal data. Standard Contractual Clauses (SCC) or
#   adequacy decision required. BLOCK if neither consent nor SCC in place.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_cross_border_transfer := result if {
	input.jurisdiction == "EU"
	input.cross_border_transfer == true
	input.destination_adequate == false
	input.scc_in_place == false
	result := {
		"decision": "BLOCK",
		"reason": "GDPR Chapter V: cross-border transfer requires adequacy decision or SCC safeguards.",
		"rule": "jurisdiction/eu/gdpr_consent.rego:check_cross_border_transfer",
		"wsp_section": "10.3",
		"requirement": "cross_border_transfer",
		"destination": input.destination_country,
	}
}

# METADATA
# title: GDPR cross-border transfer — consent missing with SCC
# description: Even with SCC in place, explicit data subject consent is
#   recommended for LLM processing transfers. BLOCK if no consent.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_cross_border_transfer_consent := result if {
	input.jurisdiction == "EU"
	input.cross_border_transfer == true
	input.processing_type == "llm"
	input.explicit_consent == false
	result := {
		"decision": "BLOCK",
		"reason": "GDPR: explicit consent required for cross-border LLM processing of personal data.",
		"rule": "jurisdiction/eu/gdpr_consent.rego:check_cross_border_transfer_consent",
		"wsp_section": "10.3",
		"requirement": "cross_border_consent",
	}
}

# ── Data minimization — only collect minimum required ────────────

# METADATA
# title: GDPR data minimization
# description: GDPR Article 5(1)(c) requires data minimization — only collect
#   and process the minimum personal data necessary for the stated purpose.
#   WARN if excessive fields are requested beyond the stated purpose.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_data_minimization := result if {
	input.jurisdiction == "EU"
	input.personal_data_included == true
	count(input.requested_fields) > count(input.required_fields)
	excessive := {f | some f in input.requested_fields; not f in input.required_fields}
	count(excessive) > 0
	result := {
		"decision": "WARN",
		"reason": sprintf("GDPR Art. 5(1)(c): data minimization — %d excessive fields requested beyond purpose.", [count(excessive)]),
		"rule": "jurisdiction/eu/gdpr_consent.rego:check_data_minimization",
		"wsp_section": "10.3",
		"requirement": "data_minimization",
		"excessive_fields": excessive,
		"excessive_count": count(excessive),
	}
}
