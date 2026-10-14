# METADATA
# title: EU AI Act Compliance
# description: Deterministic OPA rules for EU AI Act (Regulation 2024/1689) —
#   high-risk AI system conformity assessment and transparency obligations
#   for AI-generated content in financial services.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   jurisdiction: "EU"
#   severity: "BLOCK"
package jurisdiction.eu.ai_act

import rego.v1

# ── High-risk AI — conformity assessment required ────────────────

# METADATA
# title: EU AI Act — high-risk AI conformity assessment
# description: EU AI Act Article 43 requires high-risk AI systems to undergo
#   conformity assessment before deployment. Financial services AI used
#   for creditworthiness or risk assessment is classified as high-risk
#   per Annex III. BLOCK if conformity assessment not completed.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_high_risk_ai := result if {
	input.jurisdiction == "EU"
	input.ai_system.risk_classification == "high"
	input.ai_system.conformity_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "EU AI Act Art. 43: high-risk AI system requires conformity assessment before deployment.",
		"rule": "jurisdiction/eu/ai_act.rego:check_high_risk_ai",
		"wsp_section": "10.3",
		"risk_classification": "high",
		"requirement": "conformity_assessment",
		"annex": "III",
	}
}

# METADATA
# title: EU AI Act — high-risk AI documentation
# description: High-risk AI systems must maintain technical documentation per
#   EU AI Act Article 11. WARN if documentation is incomplete.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_high_risk_documentation := result if {
	input.jurisdiction == "EU"
	input.ai_system.risk_classification == "high"
	input.ai_system.conformity_assessed == true
	input.ai_system.technical_documentation_complete == false
	result := {
		"decision": "WARN",
		"reason": "EU AI Act Art. 11: high-risk AI system technical documentation incomplete.",
		"rule": "jurisdiction/eu/ai_act.rego:check_high_risk_documentation",
		"wsp_section": "10.3",
		"risk_classification": "high",
		"requirement": "technical_documentation",
	}
}

# ── Transparency — AI-generated content disclosure ───────────────

# METADATA
# title: EU AI Act — transparency obligation for AI-generated content
# description: EU AI Act Article 50 requires that AI-generated content be
#   clearly disclosed to recipients. Financial communications produced
#   by AI must include disclosure. WARN if AI disclosure not present.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_transparency_obligation := result if {
	input.jurisdiction == "EU"
	input.ai_generated_content == true
	input.ai_disclosure_present == false
	input.decision_type != "material"
	result := {
		"decision": "WARN",
		"reason": "EU AI Act Art. 50: AI-generated content must be disclosed to recipients.",
		"rule": "jurisdiction/eu/ai_act.rego:check_transparency_obligation",
		"wsp_section": "10.3",
		"requirement": "ai_content_disclosure",
		"content_type": input.content_type,
	}
}

# METADATA
# title: EU AI Act — transparency for material decisions
# description: AI-generated content used for material financial decisions
#   requires explicit disclosure. BLOCK if material decision content
#   lacks AI disclosure.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_transparency_material := result if {
	input.jurisdiction == "EU"
	input.ai_generated_content == true
	input.ai_disclosure_present == false
	input.decision_type == "material"
	result := {
		"decision": "BLOCK",
		"reason": "EU AI Act Art. 50: AI disclosure mandatory for material financial decision content.",
		"rule": "jurisdiction/eu/ai_act.rego:check_transparency_material",
		"wsp_section": "10.3",
		"requirement": "ai_content_disclosure_material",
		"decision_type": "material",
	}
}
