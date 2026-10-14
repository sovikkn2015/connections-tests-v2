# METADATA
# title: Hong Kong Personal Data (Privacy) Ordinance (PDPO)
# description: Deterministic OPA rules for PDPO compliance — Data Protection
#   Principles 1 (purpose and collection), 3 (use limitation), 6 (access
#   and correction), and cross-border transfer requirements for Hong Kong
#   regulated entities.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   jurisdiction: "HK"
#   severity: "BLOCK"
package jurisdiction.hk.pdpo

import rego.v1

# ── DPP1 — Purpose and manner of collection ─────────────────────

# METADATA
# title: PDPO DPP1 — purpose of collection not stated
# description: Data Protection Principle 1 requires that personal data shall
#   not be collected unless the data is collected for a lawful purpose
#   directly related to a function of the data user, and the purpose is
#   stated to the data subject at or before the time of collection.
#   BLOCK if collection purpose is not stated.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_collection_purpose := result if {
	input.jurisdiction == "HK"
	input.personal_data_collected == true
	input.collection_purpose_stated == false
	result := {
		"decision": "BLOCK",
		"reason": "PDPO DPP1: purpose of personal data collection must be stated to data subject at or before collection.",
		"rule": "jurisdiction/hk/pdpo.rego:check_collection_purpose",
		"wsp_section": "10.5",
		"requirement": "dpp1_collection_purpose",
	}
}

# METADATA
# title: PDPO DPP1 — excessive data collection
# description: Data Protection Principle 1 requires that personal data
#   collected shall be adequate but not excessive in relation to the
#   stated purpose. WARN if fields collected exceed those necessary
#   for the stated purpose.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "WARN"
check_excessive_collection := result if {
	input.jurisdiction == "HK"
	input.personal_data_collected == true
	count(input.collected_fields) > count(input.purpose_required_fields)
	excessive := {f | some f in input.collected_fields; not f in input.purpose_required_fields}
	count(excessive) > 0
	result := {
		"decision": "WARN",
		"reason": sprintf("PDPO DPP1: %d fields collected exceed those necessary for stated purpose.", [count(excessive)]),
		"rule": "jurisdiction/hk/pdpo.rego:check_excessive_collection",
		"wsp_section": "10.5",
		"requirement": "dpp1_data_minimization",
		"excessive_fields": excessive,
		"excessive_count": count(excessive),
	}
}

# ── DPP3 — Use of personal data (purpose limitation) ────────────

# METADATA
# title: PDPO DPP3 — use beyond original purpose
# description: Data Protection Principle 3 requires that personal data shall
#   not be used for a new purpose incompatible with the original purpose
#   of collection without the prescribed consent of the data subject.
#   BLOCK if data is used for a purpose not covered by original consent.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_purpose_limitation := result if {
	input.jurisdiction == "HK"
	input.personal_data_used == true
	input.current_use_purpose != input.original_collection_purpose
	input.consent_for_new_purpose == false
	result := {
		"decision": "BLOCK",
		"reason": "PDPO DPP3: personal data must not be used for purpose incompatible with original collection purpose without consent.",
		"rule": "jurisdiction/hk/pdpo.rego:check_purpose_limitation",
		"wsp_section": "10.5",
		"requirement": "dpp3_purpose_limitation",
		"original_purpose": input.original_collection_purpose,
		"current_purpose": input.current_use_purpose,
	}
}

# METADATA
# title: PDPO DPP3 — LLM processing purpose limitation
# description: Personal data processed through LLM systems must be within
#   the scope of the original collection purpose. Using client data for
#   LLM training or purposes beyond the stated advisory purpose is
#   prohibited without explicit consent. BLOCK if LLM processing exceeds
#   stated purpose.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_llm_purpose_limitation := result if {
	input.jurisdiction == "HK"
	input.processing_type == "llm"
	input.personal_data_included == true
	input.llm_processing_within_purpose == false
	result := {
		"decision": "BLOCK",
		"reason": "PDPO DPP3: LLM processing of personal data must be within scope of original collection purpose.",
		"rule": "jurisdiction/hk/pdpo.rego:check_llm_purpose_limitation",
		"wsp_section": "10.5",
		"requirement": "dpp3_llm_purpose",
	}
}

# ── DPP6 — Access and correction rights ─────────────────────────

# METADATA
# title: PDPO DPP6 — data access request handling
# description: Data Protection Principle 6 requires that a data subject shall
#   be able to ascertain whether a data user holds personal data of which
#   they are the subject, and to request access to such data. Access
#   requests must be complied with within 40 days. BLOCK if access
#   request mechanism is not available.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_data_access_rights := result if {
	input.jurisdiction == "HK"
	input.data_access_request == true
	input.access_request_mechanism_available == false
	result := {
		"decision": "BLOCK",
		"reason": "PDPO DPP6: data access request mechanism must be available. Compliance within 40 days required.",
		"rule": "jurisdiction/hk/pdpo.rego:check_data_access_rights",
		"wsp_section": "10.5",
		"requirement": "dpp6_access_rights",
		"compliance_deadline_days": 40,
	}
}

# METADATA
# title: PDPO DPP6 — data correction request
# description: Data Protection Principle 6 also provides data subjects the
#   right to request correction of inaccurate personal data. Correction
#   requests must be complied with within 40 days. BLOCK if correction
#   mechanism is not available.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_data_correction_rights := result if {
	input.jurisdiction == "HK"
	input.data_correction_request == true
	input.correction_request_mechanism_available == false
	result := {
		"decision": "BLOCK",
		"reason": "PDPO DPP6: data correction request mechanism must be available. Compliance within 40 days required.",
		"rule": "jurisdiction/hk/pdpo.rego:check_data_correction_rights",
		"wsp_section": "10.5",
		"requirement": "dpp6_correction_rights",
		"compliance_deadline_days": 40,
	}
}

# ── Cross-border transfer — adequate protection required ─────────

# METADATA
# title: PDPO cross-border transfer — adequate protection
# description: Section 33 of the PDPO (when commenced) prohibits transfer of
#   personal data outside Hong Kong unless the destination jurisdiction
#   provides adequate data protection or the data subject has given
#   explicit consent. BLOCK if neither condition is met.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "BLOCK"
check_cross_border_transfer := result if {
	input.jurisdiction == "HK"
	input.cross_border_transfer == true
	input.destination_adequate_protection == false
	input.data_subject_consent_for_transfer == false
	result := {
		"decision": "BLOCK",
		"reason": "PDPO s.33: cross-border transfer requires adequate protection in destination or explicit data subject consent.",
		"rule": "jurisdiction/hk/pdpo.rego:check_cross_border_transfer",
		"wsp_section": "10.5",
		"requirement": "cross_border_adequate_protection",
		"destination": input.destination_jurisdiction,
	}
}

# METADATA
# title: PDPO cross-border transfer — transfer to mainland China
# description: Transfers of personal data to mainland China require specific
#   contractual safeguards given the different legal framework. WARN if
#   supplementary contractual measures are not in place.
# custom:
#   wsp_section: "10.5"
#   gap: 7
#   severity: "WARN"
check_cross_border_china := result if {
	input.jurisdiction == "HK"
	input.cross_border_transfer == true
	input.destination_jurisdiction == "CN"
	input.supplementary_contractual_measures == false
	result := {
		"decision": "WARN",
		"reason": "PDPO: transfer to mainland China — supplementary contractual measures recommended.",
		"rule": "jurisdiction/hk/pdpo.rego:check_cross_border_china",
		"wsp_section": "10.5",
		"requirement": "cross_border_china_safeguards",
		"destination": "CN",
	}
}
