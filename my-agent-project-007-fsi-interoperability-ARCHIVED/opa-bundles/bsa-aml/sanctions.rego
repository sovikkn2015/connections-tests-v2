# bsa-aml/sanctions.rego — Sanctions & PEP Screening Rules (Gap 4)
#
# Deterministic OPA rules for OFAC/EU/UN sanctions screening and
# Politically Exposed Person (PEP) checks.
#
# Sanctions hit = BLOCK + escalate. PEP match = WARN + enhanced due diligence.
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package bsa_aml.sanctions

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# RULE 1: Sanctions List Screening
# Name matches OFAC/EU/UN sanctions list — BLOCK + escalate
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Sanctions list screening
# description: Screens counterparty and client names against OFAC, EU, and
#   UN sanctions lists. Exact match triggers immediate block and escalation
#   to compliance officer. All transactions with sanctioned entities are
#   prohibited under IEEPA and Executive Orders.
# custom:
#   wsp_section: "8.3"
#   gap: 4
#   severity: "BLOCK"
check_sanctions := result if {
	# Match input name against sanctions entries
	some entry in input.sanctions_list
	upper(input.name) == upper(entry.name)

	result := {
		"decision": "BLOCK",
		"alert_type": "SANCTIONS_HIT",
		"severity": "CRITICAL",
		"reason": sprintf(
			"Sanctions match: '%s' found on %s sanctions list",
			[input.name, entry.list_source],
		),
		"rule": "bsa-aml/sanctions.rego:check_sanctions",
		"wsp_section": "8.3",
		"route_to": "compliance_officer",
		"do_not_notify": ["advisor", "client"],
		"escalate": true,
		"matched_entity": entry.name,
		"list_source": entry.list_source,
		"match_confidence": 1.0,
	}
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: Politically Exposed Person (PEP) Check
# PEP match — WARN + enhanced due diligence required
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Politically Exposed Person screening
# description: Screens client names against PEP lists. PEP status does not
#   prohibit the relationship but requires Enhanced Due Diligence (EDD),
#   senior management approval, and ongoing monitoring per FATF guidance.
# custom:
#   wsp_section: "8.3"
#   gap: 4
#   severity: "WARN"
check_pep := result if {
	# Match input name against PEP entries
	some entry in input.pep_list
	upper(input.name) == upper(entry.name)

	result := {
		"decision": "WARN",
		"alert_type": "PEP_MATCH",
		"severity": "HIGH",
		"reason": sprintf(
			"PEP match: '%s' — enhanced due diligence required (role: %s, jurisdiction: %s)",
			[input.name, entry.role, entry.jurisdiction],
		),
		"rule": "bsa-aml/sanctions.rego:check_pep",
		"wsp_section": "8.3",
		"route_to": "compliance_officer",
		"do_not_notify": ["advisor", "client"],
		"escalate": false,
		"enhanced_due_diligence": true,
		"matched_entity": entry.name,
		"pep_role": entry.role,
		"pep_jurisdiction": entry.jurisdiction,
	}
}
