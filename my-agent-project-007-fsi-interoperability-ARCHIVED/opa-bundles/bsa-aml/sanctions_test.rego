# bsa-aml/sanctions_test.rego — OPA native tests for sanctions & PEP rules
#
# Tests both sanctions rules:
#   1. Sanctions list screening (OFAC/EU/UN) — BLOCK + escalate
#   2. PEP check — WARN + enhanced due diligence
#
# CRITICAL: Every result must include route_to=compliance_officer
# and do_not_notify=["advisor","client"] (anti-tipping-off).

package bsa_aml.sanctions_test

import rego.v1

import data.bsa_aml.sanctions

# ═══════════════════════════════════════════════════════════════════
# TEST: Sanctions list screening — BLOCK on match
# ═══════════════════════════════════════════════════════════════════

test_sanctions_hit_ofac if {
	result := sanctions.check_sanctions with input as {
		"name": "John Doe",
		"sanctions_list": [
			{"name": "John Doe", "list_source": "OFAC"},
		],
	}
	result.decision == "BLOCK"
	result.alert_type == "SANCTIONS_HIT"
	result.severity == "CRITICAL"
	result.wsp_section == "8.3"
	result.route_to == "compliance_officer"
	result.do_not_notify == ["advisor", "client"]
	result.escalate == true
	result.list_source == "OFAC"
	result.match_confidence == 1.0
}

test_sanctions_hit_case_insensitive if {
	result := sanctions.check_sanctions with input as {
		"name": "jane smith",
		"sanctions_list": [
			{"name": "JANE SMITH", "list_source": "EU"},
		],
	}
	result.decision == "BLOCK"
	result.list_source == "EU"
}

test_sanctions_no_hit if {
	not sanctions.check_sanctions with input as {
		"name": "Clean Client",
		"sanctions_list": [
			{"name": "Bad Actor", "list_source": "OFAC"},
			{"name": "Another Bad Actor", "list_source": "UN"},
		],
	}
}

test_sanctions_no_hit_empty_list if {
	not sanctions.check_sanctions with input as {
		"name": "Anyone",
		"sanctions_list": [],
	}
}

# ═══════════════════════════════════════════════════════════════════
# TEST: PEP screening — WARN + enhanced due diligence
# ═══════════════════════════════════════════════════════════════════

test_pep_match if {
	result := sanctions.check_pep with input as {
		"name": "Political Figure",
		"pep_list": [
			{"name": "Political Figure", "role": "Minister of Finance", "jurisdiction": "XX"},
		],
	}
	result.decision == "WARN"
	result.alert_type == "PEP_MATCH"
	result.severity == "HIGH"
	result.wsp_section == "8.3"
	result.route_to == "compliance_officer"
	result.do_not_notify == ["advisor", "client"]
	result.escalate == false
	result.enhanced_due_diligence == true
	result.pep_role == "Minister of Finance"
}

test_pep_match_case_insensitive if {
	result := sanctions.check_pep with input as {
		"name": "important person",
		"pep_list": [
			{"name": "IMPORTANT PERSON", "role": "Governor", "jurisdiction": "YY"},
		],
	}
	result.decision == "WARN"
	result.enhanced_due_diligence == true
}

test_pep_no_match if {
	not sanctions.check_pep with input as {
		"name": "Regular Client",
		"pep_list": [
			{"name": "Some Official", "role": "Senator", "jurisdiction": "ZZ"},
		],
	}
}

test_pep_no_match_empty_list if {
	not sanctions.check_pep with input as {
		"name": "Anyone",
		"pep_list": [],
	}
}
