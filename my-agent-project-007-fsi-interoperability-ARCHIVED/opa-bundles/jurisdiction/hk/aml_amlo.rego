# METADATA
# title: Hong Kong AMLO — Anti-Money Laundering and Counter-Terrorist Financing
# description: Deterministic OPA rules for AMLO compliance — Customer Due
#   Diligence (CDD), Suspicious Transaction Reports (STR) to JFIU,
#   Politically Exposed Person (PEP) enhanced due diligence, and
#   ongoing monitoring for Hong Kong licensed intermediaries.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   jurisdiction: "HK"
#   severity: "BLOCK"
package jurisdiction.hk.aml_amlo

import rego.v1

# ── Customer Due Diligence (CDD) — AMLO Schedule 2 ──────────────

# METADATA
# title: AMLO CDD — identity verification required
# description: AMLO Schedule 2 requires financial institutions to verify the
#   identity of customers before establishing a business relationship.
#   BLOCK if customer identity has not been verified.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_cdd_identity_verification := result if {
	input.jurisdiction == "HK"
	input.new_business_relationship == true
	input.identity_verified == false
	result := {
		"decision": "BLOCK",
		"reason": "AMLO Schedule 2: customer identity must be verified before establishing business relationship.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_cdd_identity_verification",
		"wsp_section": "10.5",
		"requirement": "cdd_identity_verification",
	}
}

# METADATA
# title: AMLO CDD — beneficial ownership identification
# description: AMLO Schedule 2 requires identification and verification of
#   beneficial owners of corporate and trust clients. BLOCK if beneficial
#   ownership has not been identified for non-individual clients.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_cdd_beneficial_ownership := result if {
	input.jurisdiction == "HK"
	input.client_type != "individual"
	input.beneficial_owners_identified == false
	result := {
		"decision": "BLOCK",
		"reason": "AMLO Schedule 2: beneficial owners must be identified for non-individual clients.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_cdd_beneficial_ownership",
		"wsp_section": "10.5",
		"requirement": "cdd_beneficial_ownership",
		"client_type": input.client_type,
	}
}

# METADATA
# title: AMLO CDD — ongoing due diligence
# description: AMLO Schedule 2 requires ongoing due diligence including
#   monitoring of transactions to ensure consistency with the institution's
#   knowledge of the customer. BLOCK if CDD review is overdue (exceeds
#   12 months for high-risk, 36 months for standard).
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_cdd_ongoing_review := result if {
	input.jurisdiction == "HK"
	input.client_risk_rating == "high"
	input.months_since_last_cdd_review > 12
	result := {
		"decision": "BLOCK",
		"reason": "AMLO Schedule 2: high-risk client CDD review overdue. Maximum 12 months between reviews.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_cdd_ongoing_review",
		"wsp_section": "10.5",
		"requirement": "cdd_ongoing_review_high_risk",
		"months_since_review": input.months_since_last_cdd_review,
		"max_months": 12,
	}
}

# METADATA
# title: AMLO CDD — standard risk ongoing review
# description: Standard risk clients require CDD review at least every 36
#   months per AMLO Schedule 2. WARN if approaching deadline (>30 months).
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "WARN"
check_cdd_ongoing_review_standard := result if {
	input.jurisdiction == "HK"
	input.client_risk_rating == "standard"
	input.months_since_last_cdd_review > 30
	result := {
		"decision": "WARN",
		"reason": sprintf("AMLO Schedule 2: standard risk client CDD review approaching deadline (%d months, max 36).", [input.months_since_last_cdd_review]),
		"rule": "jurisdiction/hk/aml_amlo.rego:check_cdd_ongoing_review_standard",
		"wsp_section": "10.5",
		"requirement": "cdd_ongoing_review_standard",
		"months_since_review": input.months_since_last_cdd_review,
		"max_months": 36,
	}
}

# ── Suspicious Transaction Reports (STR) — JFIU reporting ───────

# METADATA
# title: AMLO STR — suspicious transaction detected
# description: AMLO s.25A requires financial institutions to file Suspicious
#   Transaction Reports (STR) with the Joint Financial Intelligence Unit
#   (JFIU) when there are grounds to suspect money laundering or terrorist
#   financing. STR must be filed as soon as reasonably practicable.
#   BLOCK transaction pending STR filing. Anti-tipping-off applies —
#   STR alerts route to compliance officer ONLY.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_str_filing := result if {
	input.jurisdiction == "HK"
	input.suspicious_transaction_detected == true
	input.str_filed_with_jfiu == false
	result := {
		"decision": "BLOCK",
		"reason": "AMLO s.25A: suspicious transaction detected — STR must be filed with JFIU. Transaction blocked pending filing.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_str_filing",
		"wsp_section": "10.5",
		"requirement": "str_jfiu_filing",
		"alert_routing": "compliance_officer_only",
		"anti_tipping_off": true,
	}
}

# METADATA
# title: AMLO STR — anti-tipping-off obligation
# description: AMLO s.25A(4) prohibits tipping off — no person shall disclose
#   to any other person information that is likely to prejudice an
#   investigation. STR alerts MUST route to compliance officer ONLY.
#   BLOCK if STR alert is routed to non-compliance personnel.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_str_anti_tipping_off := result if {
	input.jurisdiction == "HK"
	input.str_alert == true
	input.alert_recipient_role != "compliance_officer"
	result := {
		"decision": "BLOCK",
		"reason": "AMLO s.25A(4): anti-tipping-off — STR alerts must route to compliance officer ONLY. Disclosure to non-compliance personnel is a criminal offence.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_str_anti_tipping_off",
		"wsp_section": "10.5",
		"requirement": "str_anti_tipping_off",
		"alert_recipient_role": input.alert_recipient_role,
		"required_role": "compliance_officer",
	}
}

# ── PEP Enhanced Due Diligence ───────────────────────────────────

# METADATA
# title: AMLO PEP — enhanced due diligence required
# description: AMLO Schedule 2 s.4 requires enhanced due diligence for
#   Politically Exposed Persons (PEPs), their family members, and close
#   associates. Senior management approval is required to establish or
#   continue a business relationship with a PEP. BLOCK if EDD not
#   completed for PEP client.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_pep_enhanced_due_diligence := result if {
	input.jurisdiction == "HK"
	input.pep_status == true
	input.pep_enhanced_due_diligence_completed == false
	result := {
		"decision": "BLOCK",
		"reason": "AMLO Schedule 2 s.4: enhanced due diligence required for PEP client.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_pep_enhanced_due_diligence",
		"wsp_section": "10.5",
		"requirement": "pep_edd",
		"pep_category": input.pep_category,
	}
}

# METADATA
# title: AMLO PEP — senior management approval required
# description: AMLO Schedule 2 s.4 requires senior management approval to
#   establish or continue a business relationship with a PEP. BLOCK if
#   senior management approval has not been obtained.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_pep_senior_management_approval := result if {
	input.jurisdiction == "HK"
	input.pep_status == true
	input.senior_management_approved == false
	result := {
		"decision": "BLOCK",
		"reason": "AMLO Schedule 2 s.4: senior management approval required for PEP business relationship.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_pep_senior_management_approval",
		"wsp_section": "10.5",
		"requirement": "pep_senior_management_approval",
	}
}

# METADATA
# title: AMLO PEP — source of wealth verification
# description: AMLO Schedule 2 s.4 requires reasonable measures to establish
#   the source of wealth and source of funds of PEP clients. BLOCK if
#   source of wealth has not been verified.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_pep_source_of_wealth := result if {
	input.jurisdiction == "HK"
	input.pep_status == true
	input.source_of_wealth_verified == false
	result := {
		"decision": "BLOCK",
		"reason": "AMLO Schedule 2 s.4: source of wealth must be verified for PEP client.",
		"rule": "jurisdiction/hk/aml_amlo.rego:check_pep_source_of_wealth",
		"wsp_section": "10.5",
		"requirement": "pep_source_of_wealth",
	}
}
