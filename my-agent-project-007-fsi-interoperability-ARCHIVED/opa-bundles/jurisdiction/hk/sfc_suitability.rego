# METADATA
# title: SFC Suitability and Know Your Client
# description: Deterministic OPA rules for Hong Kong SFC Code of Conduct —
#   know your client (Para 5.2), suitability (Para 5.3), derivative
#   suitability, risk profiling, and Professional Investor exemptions
#   for SFC-licensed intermediaries.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   jurisdiction: "HK"
#   severity: "BLOCK"
package jurisdiction.hk.sfc_suitability

import rego.v1

# ── Know Your Client — Para 5.2 assessment required ──────────────

# METADATA
# title: SFC Code of Conduct Para 5.2 — Know Your Client
# description: SFC Code of Conduct Para 5.2 requires intermediaries to assess
#   the client's financial situation, investment experience, and investment
#   objectives before making any recommendation. BLOCK if KYC assessment
#   is incomplete.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_kyc_assessment := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.kyc_financial_situation_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC Code of Conduct Para 5.2: client financial situation must be assessed before recommendation.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_kyc_assessment",
		"wsp_section": "10.5",
		"requirement": "kyc_financial_situation",
	}
}

# METADATA
# title: SFC Code of Conduct Para 5.2 — investment experience
# description: SFC Code of Conduct Para 5.2 requires assessment of client
#   investment experience. BLOCK if investment experience has not been
#   assessed prior to recommendation.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_kyc_investment_experience := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.kyc_investment_experience_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC Code of Conduct Para 5.2: client investment experience must be assessed before recommendation.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_kyc_investment_experience",
		"wsp_section": "10.5",
		"requirement": "kyc_investment_experience",
	}
}

# METADATA
# title: SFC Code of Conduct Para 5.2 — investment objectives
# description: SFC Code of Conduct Para 5.2 requires assessment of client
#   investment objectives. BLOCK if investment objectives have not been
#   assessed prior to recommendation.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_kyc_investment_objectives := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.kyc_investment_objectives_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC Code of Conduct Para 5.2: client investment objectives must be assessed before recommendation.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_kyc_investment_objectives",
		"wsp_section": "10.5",
		"requirement": "kyc_investment_objectives",
	}
}

# ── Suitability — Para 5.3 recommendation must be suitable ──────

# METADATA
# title: SFC Code of Conduct Para 5.3 — suitability obligation
# description: SFC Code of Conduct Para 5.3 requires that recommendations
#   are suitable for the client having regard to the client's financial
#   situation, investment experience, and investment objectives. BLOCK
#   if suitability assessment has not been performed.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_suitability := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.suitability_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC Code of Conduct Para 5.3: suitability assessment required before recommendation.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_suitability",
		"wsp_section": "10.5",
		"requirement": "suitability_assessment",
	}
}

# ── Risk profiling — conservative clients and high-risk products ─

# METADATA
# title: SFC suitability — risk profile mismatch
# description: Conservative risk profile clients must not be recommended
#   high-risk products. SFC Code of Conduct Para 5.3 requires the
#   recommendation to be suitable for the client's risk tolerance.
#   BLOCK if product risk exceeds client risk tolerance.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_risk_profile_mismatch := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.client_risk_profile == "conservative"
	input.product_risk_level == "high"
	result := {
		"decision": "BLOCK",
		"reason": "SFC Code of Conduct Para 5.3: high-risk product unsuitable for conservative risk profile client.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_risk_profile_mismatch",
		"wsp_section": "10.5",
		"requirement": "risk_profile_match",
		"client_risk_profile": input.client_risk_profile,
		"product_risk_level": input.product_risk_level,
	}
}

# METADATA
# title: SFC suitability — moderate client with high-risk product
# description: Moderate risk profile clients receiving high-risk product
#   recommendations require enhanced suitability justification and
#   documented rationale per SFC Code of Conduct Para 5.3.
#   WARN if enhanced justification is not documented.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "WARN"
check_risk_profile_elevated := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.client_risk_profile == "moderate"
	input.product_risk_level == "high"
	input.enhanced_suitability_justification == false
	result := {
		"decision": "WARN",
		"reason": "SFC Code of Conduct Para 5.3: enhanced suitability justification required for moderate client with high-risk product.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_risk_profile_elevated",
		"wsp_section": "10.5",
		"requirement": "enhanced_suitability_justification",
		"client_risk_profile": input.client_risk_profile,
		"product_risk_level": input.product_risk_level,
	}
}

# ── Derivative suitability — additional assessment required ──────

# METADATA
# title: SFC derivative suitability — additional assessment
# description: SFC Code of Conduct Para 5.1A requires additional suitability
#   assessment for derivative products. Intermediaries must ensure the
#   client understands the nature and risks of derivatives before
#   recommending. BLOCK if derivative assessment not completed.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_derivative_suitability := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.product_type == "derivative"
	input.derivative_knowledge_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC Code of Conduct Para 5.1A: derivative knowledge assessment required before recommending derivative products.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_derivative_suitability",
		"wsp_section": "10.5",
		"requirement": "derivative_knowledge_assessment",
		"product_type": input.product_type,
	}
}

# METADATA
# title: SFC derivative suitability — risk disclosure
# description: SFC requires that clients receive and acknowledge derivative
#   risk disclosure statements before transacting in derivative products.
#   BLOCK if risk disclosure not acknowledged.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_derivative_risk_disclosure := result if {
	input.jurisdiction == "HK"
	input.product_type == "derivative"
	input.derivative_risk_disclosure_acknowledged == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC: derivative risk disclosure must be acknowledged by client before transaction.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_derivative_risk_disclosure",
		"wsp_section": "10.5",
		"requirement": "derivative_risk_disclosure",
		"product_type": input.product_type,
	}
}

# ── Professional Investor exemption ──────────────────────────────

# METADATA
# title: SFC Professional Investor exemption — reduced suitability
# description: Professional Investors (as defined in SFO Schedule 1) are
#   exempt from certain suitability requirements under SFC Code of
#   Conduct Para 15.3A. When PI status is confirmed, suitability
#   requirements are reduced but KYC still applies. ALLOW with note.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "WARN"
check_professional_investor_exemption := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.professional_investor == true
	input.pi_status_verified == true
	result := {
		"decision": "ALLOW",
		"reason": "SFC Code of Conduct Para 15.3A: Professional Investor exemption applies — reduced suitability requirements.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_professional_investor_exemption",
		"wsp_section": "10.5",
		"requirement": "professional_investor_exemption",
		"pi_category": input.pi_category,
		"note": "KYC obligations under Para 5.2 still apply to Professional Investors.",
	}
}

# METADATA
# title: SFC Professional Investor — PI status not verified
# description: If a client claims Professional Investor status but verification
#   is incomplete, full suitability requirements apply. BLOCK if PI status
#   is claimed but not verified and suitability is not assessed.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_professional_investor_unverified := result if {
	input.jurisdiction == "HK"
	input.recommendation == true
	input.professional_investor == true
	input.pi_status_verified == false
	input.suitability_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "SFC: Professional Investor status not verified — full suitability requirements apply.",
		"rule": "jurisdiction/hk/sfc_suitability.rego:check_professional_investor_unverified",
		"wsp_section": "10.5",
		"requirement": "pi_verification",
	}
}
