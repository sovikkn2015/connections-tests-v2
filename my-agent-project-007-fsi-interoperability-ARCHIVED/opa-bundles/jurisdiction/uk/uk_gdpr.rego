# METADATA
# title: UK GDPR Data Protection
# description: Deterministic OPA rules for UK GDPR (Data Protection Act 2018) —
#   LLM processing consent and regulated record retention requirements
#   for UK-regulated firms post-Brexit.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   jurisdiction: "UK"
#   severity: "BLOCK"
package jurisdiction.uk.uk_gdpr

import rego.v1

# ── UK LLM processing consent — explicit consent required ────────

# METADATA
# title: UK GDPR LLM processing consent
# description: UK GDPR (DPA 2018) requires explicit consent for processing
#   personal data through LLM systems. Mirrors EU GDPR Article 6/9
#   requirements under UK domestic law. BLOCK if consent not obtained.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "BLOCK"
check_uk_llm_consent := result if {
	input.jurisdiction == "UK"
	input.processing_type == "llm"
	input.personal_data_included == true
	input.explicit_consent == false
	result := {
		"decision": "BLOCK",
		"reason": "UK GDPR (DPA 2018): explicit consent required for LLM processing of personal data.",
		"rule": "jurisdiction/uk/uk_gdpr.rego:check_uk_llm_consent",
		"wsp_section": "10.4",
		"requirement": "llm_processing_consent",
		"legal_basis": "DPA 2018 Schedule 1",
		"data_subject_rights": ["right_to_object", "right_to_explanation"],
	}
}

# ── UK data retention — 5-year minimum for regulated records ─────

# METADATA
# title: UK GDPR regulated record retention — 5 years
# description: FCA SYSC 9 and MiFID II (as retained in UK law) require regulated
#   records to be retained for a minimum of 5 years. BLOCK if retention
#   period is configured below the minimum.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "BLOCK"
check_uk_data_retention := result if {
	input.jurisdiction == "UK"
	input.record_type in {"trade_record", "order_ticket", "account_statement", "compliance_record", "audit_trail", "client_communication"}
	input.retention_years < 5
	result := {
		"decision": "BLOCK",
		"reason": sprintf("UK GDPR / FCA SYSC 9: %s requires minimum 5-year retention. Configured: %d years.", [input.record_type, input.retention_years]),
		"rule": "jurisdiction/uk/uk_gdpr.rego:check_uk_data_retention",
		"wsp_section": "10.4",
		"record_type": input.record_type,
		"required_years": 5,
		"configured_years": input.retention_years,
	}
}

# ── Data Protection Impact Assessment — required for high-risk ───

# METADATA
# title: UK GDPR data protection impact assessment
# description: UK GDPR (DPA 2018 Section 64) requires a Data Protection Impact
#   Assessment (DPIA) for processing that is likely to result in a high
#   risk to data subjects. LLM processing of personal financial data is
#   classified as high-risk. WARN if DPIA not completed.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "WARN"
check_uk_data_protection := result if {
	input.jurisdiction == "UK"
	input.processing_risk == "high"
	input.dpia_completed == false
	result := {
		"decision": "WARN",
		"reason": "UK GDPR (DPA 2018 s.64): Data Protection Impact Assessment required for high-risk processing.",
		"rule": "jurisdiction/uk/uk_gdpr.rego:check_uk_data_protection",
		"wsp_section": "10.4",
		"requirement": "dpia",
		"processing_risk": "high",
		"legal_basis": "DPA 2018 Section 64",
	}
}

# METADATA
# title: UK GDPR DPIA — high-risk LLM processing without DPIA blocked
# description: High-risk LLM processing of personal data without a completed
#   DPIA must be blocked per ICO guidance on AI and data protection.
# custom:
#   wsp_section: "10.4"
#   gap: 7
#   severity: "BLOCK"
check_uk_data_protection_llm := result if {
	input.jurisdiction == "UK"
	input.processing_type == "llm"
	input.processing_risk == "high"
	input.personal_data_included == true
	input.dpia_completed == false
	result := {
		"decision": "BLOCK",
		"reason": "UK GDPR: DPIA mandatory before high-risk LLM processing of personal data. ICO enforcement action risk.",
		"rule": "jurisdiction/uk/uk_gdpr.rego:check_uk_data_protection_llm",
		"wsp_section": "10.4",
		"requirement": "dpia_llm",
		"processing_type": "llm",
		"processing_risk": "high",
	}
}
