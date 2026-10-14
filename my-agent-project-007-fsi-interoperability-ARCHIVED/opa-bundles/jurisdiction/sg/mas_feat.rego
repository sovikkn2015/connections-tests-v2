# METADATA
# title: MAS FEAT Principles Enforcement
# description: Deterministic OPA rules for MAS FEAT (Fairness, Ethics,
#   Accountability, Transparency) compliance per Veritas Consortium principles.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   jurisdiction: "SG"
#   severity: "BLOCK"
package jurisdiction.sg.mas_feat

import rego.v1

# ── Fairness — bias testing required before deployment ───────────

# METADATA
# title: FEAT Fairness — bias testing required
# description: AI systems must undergo bias testing before deployment.
#   Fairness score must meet minimum threshold (0.7).
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_fairness := result if {
	input.jurisdiction == "SG"
	input.ai_system.bias_tested == false
	result := {
		"decision": "BLOCK",
		"reason": "FEAT Fairness: bias testing required before AI deployment.",
		"rule": "jurisdiction/sg/mas_feat.rego:check_fairness",
		"wsp_section": "10.2",
		"pillar": "fairness",
	}
}

# METADATA
# title: FEAT Fairness — score below threshold
# description: AI fairness score must be >= 0.7 to pass FEAT assessment.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_fairness_score := result if {
	input.jurisdiction == "SG"
	input.ai_system.bias_tested == true
	input.ai_system.fairness_score < 0.7
	result := {
		"decision": "BLOCK",
		"reason": sprintf("FEAT Fairness: score %.2f below threshold 0.7.", [input.ai_system.fairness_score]),
		"rule": "jurisdiction/sg/mas_feat.rego:check_fairness_score",
		"wsp_section": "10.2",
		"pillar": "fairness",
		"score": input.ai_system.fairness_score,
		"threshold": 0.7,
	}
}

# ── Ethics — ethical review board sign-off required ──────────────

# METADATA
# title: FEAT Ethics — review board sign-off
# description: Ethical review board must sign off on AI systems before deployment.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_ethics := result if {
	input.jurisdiction == "SG"
	input.ai_system.ethics_reviewed == false
	result := {
		"decision": "BLOCK",
		"reason": "FEAT Ethics: ethical review board sign-off required before deployment.",
		"rule": "jurisdiction/sg/mas_feat.rego:check_ethics",
		"wsp_section": "10.2",
		"pillar": "ethics",
	}
}

# ── Accountability — designated AI risk owner required ───────────

# METADATA
# title: FEAT Accountability — AI risk owner
# description: A designated AI risk owner must be assigned for each AI system.
#   Clear escalation paths and client recourse mechanisms required.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_accountability := result if {
	input.jurisdiction == "SG"
	input.ai_system.accountability_owner == ""
	result := {
		"decision": "BLOCK",
		"reason": "FEAT Accountability: designated AI risk owner required.",
		"rule": "jurisdiction/sg/mas_feat.rego:check_accountability",
		"wsp_section": "10.2",
		"pillar": "accountability",
	}
}

# ── Transparency — AI use disclosure required ────────────────────

# METADATA
# title: FEAT Transparency — AI use disclosure
# description: AI use must be disclosed to clients for material decisions.
#   Meaningful explanations must be available on request.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_transparency := result if {
	input.jurisdiction == "SG"
	input.ai_system.transparency_disclosed == false
	input.decision_type == "material"
	result := {
		"decision": "BLOCK",
		"reason": "FEAT Transparency: AI use must be disclosed for material decisions.",
		"rule": "jurisdiction/sg/mas_feat.rego:check_transparency",
		"wsp_section": "10.2",
		"pillar": "transparency",
	}
}
