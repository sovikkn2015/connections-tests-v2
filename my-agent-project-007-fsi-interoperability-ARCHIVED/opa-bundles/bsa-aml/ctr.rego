# bsa-aml/ctr.rego — Currency Transaction Report Rules (Gap 4)
#
# Deterministic OPA rules for CTR filing requirements.
# Per 31 CFR §1010.311: CTR required for cash transactions >$10,000.
#
# Default: no CTR generated unless threshold exceeded.
# Every rule includes wsp_section annotation (steering rule 19).
# OPA/Rego ONLY — no LLM for compliance decisions.

package bsa_aml.ctr

import rego.v1

# ═══════════════════════════════════════════════════════════════════
# CONSTANTS — per 31 CFR §1010.311
# ═══════════════════════════════════════════════════════════════════

ctr_threshold := 10000.0

# ═══════════════════════════════════════════════════════════════════
# RULE 1: Single Cash Transaction CTR
# Single cash transaction >$10,000 requires CTR filing
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Single transaction CTR threshold
# description: A single cash transaction exceeding $10,000 requires a
#   Currency Transaction Report filing per 31 CFR §1010.311.
# custom:
#   wsp_section: "8.2"
#   gap: 4
#   severity: "BLOCK"
check_ctr_threshold := result if {
	input.transaction.type == "cash"
	input.transaction.amount > ctr_threshold

	result := {
		"action": "GENERATE_CTR",
		"reason": sprintf(
			"Cash transaction of $%.2f exceeds $10,000 CTR threshold",
			[input.transaction.amount],
		),
		"rule": "bsa-aml/ctr.rego:check_ctr_threshold",
		"wsp_section": "8.2",
		"filing_data": {
			"client_id": input.transaction.client_id,
			"amount": input.transaction.amount,
			"aggregate_amount": input.transaction.amount,
			"transaction_count": 1,
			"filing_status": "pending",
		},
	}
}

# ═══════════════════════════════════════════════════════════════════
# RULE 2: Aggregate Same-Day CTR
# Same-day aggregate cash transactions >$10,000 require CTR filing
# ═══════════════════════════════════════════════════════════════════

# METADATA
# title: Aggregate same-day CTR threshold
# description: Multiple cash transactions by the same client on the same
#   business day that aggregate more than $10,000 require a CTR filing.
# custom:
#   wsp_section: "8.2"
#   gap: 4
#   severity: "BLOCK"
check_aggregate_ctr := result if {
	# Filter to same-day cash transactions for the client
	day_cash := [t |
		some t in input.transactions
		t.client_id == input.client_id
		t.type == "cash"
		t.transaction_date == input.transaction_date
	]

	count(day_cash) > 0

	# Sum all same-day cash
	total := sum([t.amount | some t in day_cash])
	total > ctr_threshold

	# Find the largest single transaction
	max_amount := max([t.amount | some t in day_cash])

	result := {
		"action": "GENERATE_CTR",
		"reason": sprintf(
			"Same-day aggregate cash of $%.2f exceeds $10,000 CTR threshold (%d transactions)",
			[total, count(day_cash)],
		),
		"rule": "bsa-aml/ctr.rego:check_aggregate_ctr",
		"wsp_section": "8.2",
		"filing_data": {
			"client_id": input.client_id,
			"amount": max_amount,
			"aggregate_amount": total,
			"transaction_count": count(day_cash),
			"filing_status": "pending",
		},
	}
}
