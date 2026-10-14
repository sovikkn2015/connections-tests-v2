# bsa-aml/sar_triggers.rego — SAR Pattern Detection Rules (Gap 4)
#
# Deterministic OPA rules for Suspicious Activity Report triggers.
# Matches Python BSAAMLMonitor logic in src/compliance/bsa-aml-monitoring/monitor.py.
#
# CRITICAL: All SAR alerts route to compliance_officer ONLY.
# Anti-tipping-off: advisor and client NEVER notified (31 USC §5318(g)(2)).
# Violation of anti-tipping-off is a federal felony.
#
# Default: DENY (fail-closed). No fallback. No degraded mode.
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package bsa_aml.sar_triggers

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS — match Python BSAAMLMonitor thresholds exactly
# ═══════════════════════════════════════════════════════════════════

structuring_low := 8000.0

structuring_high := 10000.0

structuring_min_count := 3

structuring_window_days := 5

structuring_total_min := 25000.0

rapid_movement_min_in := 50000.0

rapid_movement_out_ratio := 0.80

rapid_movement_window_days := 3

geographic_risk_min := 5000.0

unusual_volume_multiplier := 3.0

# High-risk jurisdictions (FATF grey/black list)
high_risk_countries := {
	"IR", "KP", "MM", "SY", "YE",
	"AF", "LY", "SO", "SD", "VE",
}

# ═══════════════════════════════════════════════════════════════════
# RULE 1: Structuring Detection
# 3+ cash transactions $8K-$10K in 5-day window totaling >$25K
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Structuring detection
# description: Detects potential structuring — 3+ cash transactions between
#   $8,000 and $10,000 within a 5-day window totaling more than $25,000.
#   Structuring is deliberately breaking transactions to evade CTR reporting.
# custom:
#   wsp_section: "8.1"
#   gap: 4
#   severity: "BLOCK"
check_structuring := result if {
	# Filter to cash transactions in the structuring band ($8K-$10K)
	suspect := [t |
		some t in input.transactions
		t.client_id == input.client_id
		t.type == "cash"
		t.amount >= structuring_low
		t.amount < structuring_high
		_within_window(t.timestamp_epoch, input.reference_epoch, structuring_window_days)
	]

	# Must have 3+ suspect transactions
	count(suspect) >= structuring_min_count

	# Total must exceed $25K
	total := sum([t.amount | some t in suspect])
	total > structuring_total_min

	result := {
		"decision": "BLOCK",
		"alert_type": "STRUCTURING",
		"severity": "HIGH",
		"reason": sprintf(
			"Potential structuring: %d cash transactions totaling $%.0f in %d-day window",
			[count(suspect), total, structuring_window_days],
		),
		"rule": "bsa-aml/sar_triggers.rego:check_structuring",
		"wsp_section": "8.1",
		"route_to": "compliance_officer",
		"do_not_notify": ["advisor", "client"],
		"transaction_count": count(suspect),
		"total_amount": total,
		"client_id": input.client_id,
	}
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: Rapid Fund Movement
# Wire in >$50K and wire out >80% within 3 days
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Rapid fund movement detection
# description: Detects rapid fund movement — wire in exceeding $50,000 with
#   more than 80% wired out within 3 days. Indicates potential layering or
#   pass-through money laundering.
# custom:
#   wsp_section: "8.1"
#   gap: 4
#   severity: "BLOCK"
check_rapid_movement := result if {
	# Sum wire-in amounts within window
	wire_in_txns := [t |
		some t in input.transactions
		t.client_id == input.client_id
		t.type == "wire_in"
		_within_window(t.timestamp_epoch, input.reference_epoch, rapid_movement_window_days)
	]
	wire_in := sum([t.amount | some t in wire_in_txns])

	# Must exceed $50K inbound
	wire_in > rapid_movement_min_in

	# Sum wire-out amounts within window
	wire_out_txns := [t |
		some t in input.transactions
		t.client_id == input.client_id
		t.type == "wire_out"
		_within_window(t.timestamp_epoch, input.reference_epoch, rapid_movement_window_days)
	]
	wire_out := sum([t.amount | some t in wire_out_txns])

	# Wire out must exceed 80% of wire in
	wire_out > wire_in * rapid_movement_out_ratio

	result := {
		"decision": "BLOCK",
		"alert_type": "RAPID_MOVEMENT",
		"severity": "HIGH",
		"reason": sprintf(
			"Rapid fund movement: $%.0f in, $%.0f out within %d days",
			[wire_in, wire_out, rapid_movement_window_days],
		),
		"rule": "bsa-aml/sar_triggers.rego:check_rapid_movement",
		"wsp_section": "8.1",
		"route_to": "compliance_officer",
		"do_not_notify": ["advisor", "client"],
		"wire_in": wire_in,
		"wire_out": wire_out,
		"client_id": input.client_id,
	}
}

# ═══════════════════════════════════════════════════════════════════
# RULE 3: Geographic Risk
# Wire to high-risk jurisdiction >$5K
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Geographic risk detection
# description: Detects wires exceeding $5,000 to high-risk jurisdictions
#   (FATF grey/black list countries). Triggers SAR review.
# custom:
#   wsp_section: "8.1"
#   gap: 4
#   severity: "BLOCK"
check_geographic_risk := result if {
	input.transaction.destination_country != null
	input.transaction.destination_country in high_risk_countries
	input.transaction.amount > geographic_risk_min

	result := {
		"decision": "BLOCK",
		"alert_type": "GEOGRAPHIC_RISK",
		"severity": "MEDIUM",
		"reason": sprintf(
			"Wire of $%.0f to high-risk jurisdiction: %s",
			[input.transaction.amount, input.transaction.destination_country],
		),
		"rule": "bsa-aml/sar_triggers.rego:check_geographic_risk",
		"wsp_section": "8.1",
		"route_to": "compliance_officer",
		"do_not_notify": ["advisor", "client"],
		"amount": input.transaction.amount,
		"destination_country": input.transaction.destination_country,
		"client_id": input.transaction.client_id,
	}
}

# ═══════════════════════════════════════════════════════════════════
# RULE 4: Unusual Volume
# Current month wire volume >3x monthly average
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Unusual volume detection
# description: Detects when current month wire volume exceeds 3x the
#   historical monthly average. Indicates potential suspicious activity.
# custom:
#   wsp_section: "8.1"
#   gap: 4
#   severity: "WARN"
check_unusual_volume := result if {
	input.avg_monthly_volume > 0

	# Sum current month transactions for client
	client_txns := [t |
		some t in input.transactions
		t.client_id == input.client_id
	]
	current_total := sum([t.amount | some t in client_txns])

	# Must exceed 3x monthly average
	current_total > input.avg_monthly_volume * unusual_volume_multiplier

	result := {
		"decision": "WARN",
		"alert_type": "UNUSUAL_PATTERN",
		"severity": "MEDIUM",
		"reason": sprintf(
			"Wire volume $%.0f exceeds 3x monthly avg of $%.0f",
			[current_total, input.avg_monthly_volume],
		),
		"rule": "bsa-aml/sar_triggers.rego:check_unusual_volume",
		"wsp_section": "8.1",
		"route_to": "compliance_officer",
		"do_not_notify": ["advisor", "client"],
		"current_total": current_total,
		"avg_monthly_volume": input.avg_monthly_volume,
		"multiplier": unusual_volume_multiplier,
		"client_id": input.client_id,
	}
}

# ═══════════════════════════════════════════════════════════════════
# HELPER: Window check using epoch seconds
# ═══════════════════════════════════════════════════════════════════

_within_window(ts_epoch, ref_epoch, window_days) if {
	cutoff := ref_epoch - (window_days * 86400)
	ts_epoch >= cutoff
}
