# METADATA
# title: MAS AI Risk Governance (AIRG) Guidelines
# description: Deterministic OPA rules for MAS AIRG compliance — AI inventory,
#   materiality assessment, pre-deployment testing, and ongoing monitoring.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   jurisdiction: "SG"
#   severity: "BLOCK"
package jurisdiction.sg.mas_airg

import rego.v1

# ── AI inventory — all AI systems must be registered ─────────────

# METADATA
# title: AIRG AI system inventory registration
# description: All AI systems must be registered in the firm AI inventory
#   before deployment per MAS AIRG Guidelines.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_ai_inventory := result if {
	input.jurisdiction == "SG"
	input.ai_system.registered == false
	result := {
		"decision": "BLOCK",
		"reason": "AIRG: AI system must be registered in inventory before deployment.",
		"rule": "jurisdiction/sg/mas_airg.rego:check_ai_inventory",
		"wsp_section": "10.2",
		"system_name": input.ai_system.name,
	}
}

# ── Materiality assessment — required before deployment ──────────

# METADATA
# title: AIRG risk materiality assessment
# description: Risk materiality assessment required for all AI systems before
#   deployment. Assesses impact, complexity, and reliance dimensions.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_materiality_assessment := result if {
	input.jurisdiction == "SG"
	input.ai_system.materiality_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "AIRG: risk materiality assessment required before AI deployment.",
		"rule": "jurisdiction/sg/mas_airg.rego:check_materiality_assessment",
		"wsp_section": "10.2",
		"system_name": input.ai_system.name,
	}
}

# ── Pre-deployment testing — required for HIGH materiality ───────

# METADATA
# title: AIRG pre-deployment testing for HIGH materiality
# description: HIGH materiality AI systems must complete pre-deployment testing
#   including bias testing, explainability validation, and human oversight checks.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_pre_deployment_testing := result if {
	input.jurisdiction == "SG"
	input.ai_system.materiality == "high"
	input.ai_system.pre_deployment_tested == false
	result := {
		"decision": "BLOCK",
		"reason": "AIRG: pre-deployment testing required for HIGH materiality AI systems.",
		"rule": "jurisdiction/sg/mas_airg.rego:check_pre_deployment_testing",
		"wsp_section": "10.2",
		"system_name": input.ai_system.name,
		"materiality": "high",
	}
}

# ── Ongoing monitoring — required for HIGH and MEDIUM ────────────

# METADATA
# title: AIRG ongoing monitoring for HIGH/MEDIUM materiality
# description: HIGH and MEDIUM materiality AI systems must have ongoing
#   monitoring enabled for drift detection, performance, and fairness.
# custom:
#   wsp_section: "10.2"
#   gap: 7
#   severity: "BLOCK"
check_monitoring := result if {
	input.jurisdiction == "SG"
	input.ai_system.materiality in {"high", "medium"}
	input.ai_system.monitoring_enabled == false
	result := {
		"decision": "BLOCK",
		"reason": sprintf("AIRG: ongoing monitoring required for %s materiality AI systems.", [input.ai_system.materiality]),
		"rule": "jurisdiction/sg/mas_airg.rego:check_monitoring",
		"wsp_section": "10.2",
		"system_name": input.ai_system.name,
		"materiality": input.ai_system.materiality,
	}
}
