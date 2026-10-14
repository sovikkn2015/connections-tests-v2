# METADATA
# title: MiFID II Suitability and Best Execution
# description: Deterministic OPA rules for MiFID II compliance — knowledge
#   assessment, best execution venue selection, and research unbundling
#   requirements for EU-regulated investment firms.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   jurisdiction: "EU"
#   severity: "BLOCK"
package jurisdiction.eu.mifid2_suitability

import rego.v1

# ── Knowledge assessment — required before recommendation ────────

# METADATA
# title: MiFID II knowledge and experience assessment
# description: MiFID II Article 25(2) requires firms to assess client knowledge
#   and experience before making a personal recommendation. BLOCK if the
#   client has not been assessed.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_knowledge_assessment := result if {
	input.jurisdiction == "EU"
	input.recommendation == true
	input.client_knowledge_assessed == false
	result := {
		"decision": "BLOCK",
		"reason": "MiFID II Art. 25(2): client knowledge and experience assessment required before recommendation.",
		"rule": "jurisdiction/eu/mifid2_suitability.rego:check_knowledge_assessment",
		"wsp_section": "10.3",
		"requirement": "knowledge_assessment",
	}
}

# ── Best execution — venue selection rationale required ───────────

# METADATA
# title: MiFID II best execution — rationale missing
# description: MiFID II Article 27 requires firms to take sufficient steps to
#   obtain the best possible result for clients. Execution venue selection
#   rationale must be recorded. BLOCK if rationale is missing.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_best_execution := result if {
	input.jurisdiction == "EU"
	input.order_type != ""
	input.venue_selection_rationale == ""
	result := {
		"decision": "BLOCK",
		"reason": "MiFID II Art. 27: execution venue selection rationale must be recorded for best execution.",
		"rule": "jurisdiction/eu/mifid2_suitability.rego:check_best_execution",
		"wsp_section": "10.3",
		"requirement": "best_execution",
	}
}

# METADATA
# title: MiFID II best execution — rationale recorded
# description: When venue selection rationale is present, ALLOW with
#   additional requirement to include venue rationale in client report.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_best_execution_reporting := result if {
	input.jurisdiction == "EU"
	input.order_type != ""
	input.venue_selection_rationale != ""
	input.venue_rationale_in_report == false
	result := {
		"decision": "WARN",
		"reason": "MiFID II Art. 27: venue selection rationale must be included in annual best execution report.",
		"rule": "jurisdiction/eu/mifid2_suitability.rego:check_best_execution_reporting",
		"wsp_section": "10.3",
		"requirement": "best_execution_reporting",
		"additional_requirements": ["include_venue_rationale_in_annual_report"],
	}
}

# ── Research unbundling — separate research costs ────────────────

# METADATA
# title: MiFID II research unbundling — bundled payments blocked
# description: MiFID II requires separation of research costs from execution
#   costs. Research payments must be made from a Research Payment Account
#   (RPA) or the firm's own resources. BLOCK if bundled.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_research_unbundling := result if {
	input.jurisdiction == "EU"
	input.research_payment_bundled == true
	result := {
		"decision": "BLOCK",
		"reason": "MiFID II: research costs must be unbundled from execution costs. Use RPA or firm resources.",
		"rule": "jurisdiction/eu/mifid2_suitability.rego:check_research_unbundling",
		"wsp_section": "10.3",
		"requirement": "research_unbundling",
	}
}

# METADATA
# title: MiFID II research unbundling — cost transparency
# description: When research is unbundled, additional requirement to disclose
#   research costs to clients per MiFID II cost transparency rules.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "WARN"
check_research_cost_disclosure := result if {
	input.jurisdiction == "EU"
	input.research_payment_bundled == false
	input.research_cost_disclosed == false
	result := {
		"decision": "WARN",
		"reason": "MiFID II: research costs must be disclosed to clients for cost transparency.",
		"rule": "jurisdiction/eu/mifid2_suitability.rego:check_research_cost_disclosure",
		"wsp_section": "10.3",
		"requirement": "research_cost_disclosure",
		"additional_requirements": ["disclose_research_costs_to_client"],
	}
}
