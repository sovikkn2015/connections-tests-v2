# METADATA
# title: GDPR Right to Erasure (Art. 17)
# description: Deterministic OPA rules for GDPR right to erasure — balancing
#   data subject rights against regulatory record retention obligations.
#   Regulated records are exempt per Art. 17(3)(b).
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   jurisdiction: "EU"
#   severity: "BLOCK"
package jurisdiction.eu.gdpr_erasure

import rego.v1

# ── Regulated records — DENY erasure per Art. 17(3)(b) ───────────

# METADATA
# title: GDPR erasure — regulated records exempt
# description: GDPR Article 17(3)(b) exempts erasure when processing is required
#   for compliance with a legal obligation (e.g., SEC 17a-4, MiFID II
#   record retention). Regulated records stored in WORM cannot be erased.
#   DENY erasure request.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_erasure_regulated := result if {
	input.jurisdiction == "EU"
	input.erasure_requested == true
	input.record_type in {"trade_record", "order_ticket", "account_statement", "compliance_record", "audit_trail", "reg_bi_document"}
	result := {
		"decision": "DENY",
		"reason": sprintf("GDPR Art. 17(3)(b): erasure denied — %s is a regulated record subject to retention obligations.", [input.record_type]),
		"rule": "jurisdiction/eu/gdpr_erasure.rego:check_erasure_regulated",
		"wsp_section": "10.3",
		"record_type": input.record_type,
		"exemption": "Art. 17(3)(b) — legal obligation",
		"retention_required": true,
	}
}

# ── Non-regulated PII — ALLOW erasure within 30 days ─────────────

# METADATA
# title: GDPR erasure — non-regulated PII allowed
# description: Non-regulated personal data (marketing preferences, browsing
#   history, non-essential PII) must be erased within 30 days of a valid
#   erasure request per GDPR Article 17(1). ALLOW erasure.
# custom:
#   wsp_section: "10.3"
#   gap: 7
#   severity: "BLOCK"
check_erasure_non_regulated := result if {
	input.jurisdiction == "EU"
	input.erasure_requested == true
	not input.record_type in {"trade_record", "order_ticket", "account_statement", "compliance_record", "audit_trail", "reg_bi_document"}
	result := {
		"decision": "ALLOW",
		"reason": sprintf("GDPR Art. 17(1): erasure allowed for non-regulated record type '%s'. Must complete within 30 days.", [input.record_type]),
		"rule": "jurisdiction/eu/gdpr_erasure.rego:check_erasure_non_regulated",
		"wsp_section": "10.3",
		"record_type": input.record_type,
		"deadline_days": 30,
		"erasure_scope": "all_processing_systems",
	}
}
