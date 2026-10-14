# METADATA
# title: FINRA Rule 2210 Communication Review
# description: Deterministic OPA rules for FINRA Rule 2210 — communication
#   classification and principal review requirements for retail,
#   institutional, and correspondence communications.
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   jurisdiction: "US"
#   severity: "BLOCK"
package jurisdiction.us.finra_2210

import rego.v1

# ── Retail communication — principal pre-use review required ─────

# METADATA
# title: FINRA 2210 retail communication — pre-use principal review
# description: Retail communications require principal pre-use approval
#   before distribution. Filing with FINRA may also be required for
#   certain categories per FINRA Rule 2210(c).
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_retail_communication := result if {
	input.jurisdiction == "US"
	input.communication_type == "retail"
	input.principal_approved == false
	result := {
		"decision": "BLOCK",
		"reason": "FINRA Rule 2210(b)(1): retail communication requires principal pre-use approval.",
		"rule": "jurisdiction/us/finra_2210.rego:check_retail_communication",
		"wsp_section": "10.1",
		"communication_type": "retail",
		"review_type": "pre_use",
	}
}

# ── Institutional communication — post-use review sufficient ─────

# METADATA
# title: FINRA 2210 institutional communication — post-use review
# description: Institutional communications require post-use review by a
#   principal. Pre-approval is not required but supervisory procedures
#   must include post-use review per FINRA Rule 2210(b)(2).
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_institutional_communication := result if {
	input.jurisdiction == "US"
	input.communication_type == "institutional"
	input.post_use_reviewed == false
	input.days_since_distribution > 30
	result := {
		"decision": "BLOCK",
		"reason": "FINRA Rule 2210(b)(2): institutional communication must be reviewed post-use within 30 days.",
		"rule": "jurisdiction/us/finra_2210.rego:check_institutional_communication",
		"wsp_section": "10.1",
		"communication_type": "institutional",
		"review_type": "post_use",
	}
}

# ── Correspondence — spot-check basis ────────────────────────────

# METADATA
# title: FINRA 2210 correspondence — spot-check review
# description: Correspondence is subject to supervisory review on a spot-check
#   basis. No pre-approval required. Firm must maintain procedures for
#   review per FINRA Rule 2210(b)(3).
# custom:
#   wsp_section: "10.1"
#   gap: 7
#   severity: "BLOCK"
check_correspondence := result if {
	input.jurisdiction == "US"
	input.communication_type == "correspondence"
	input.spot_check_procedures_enabled == false
	result := {
		"decision": "BLOCK",
		"reason": "FINRA Rule 2210(b)(3): correspondence spot-check review procedures must be enabled.",
		"rule": "jurisdiction/us/finra_2210.rego:check_correspondence",
		"wsp_section": "10.1",
		"communication_type": "correspondence",
		"review_type": "spot_check",
	}
}
