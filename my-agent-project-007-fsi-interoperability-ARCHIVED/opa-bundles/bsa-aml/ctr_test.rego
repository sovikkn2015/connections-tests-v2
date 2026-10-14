# bsa-aml/ctr_test.rego — OPA native tests for CTR rules
#
# Tests both CTR rules:
#   1. Single cash transaction >$10,000
#   2. Same-day aggregate cash >$10,000
#
# Per 31 CFR §1010.311.

package bsa_aml.ctr_test

import rego.v1

import data.bsa_aml.ctr

# ═══════════════════════════════════════════════════════════════════
# TEST: Single transaction CTR threshold
# ═══════════════════════════════════════════════════════════════════

test_ctr_single_triggers if {
	result := ctr.check_ctr_threshold with input as {
		"transaction": {
			"client_id": "C-001",
			"type": "cash",
			"amount": 15000.0,
		},
	}
	result.action == "GENERATE_CTR"
	result.wsp_section == "8.2"
	result.filing_data.client_id == "C-001"
	result.filing_data.amount == 15000.0
	result.filing_data.transaction_count == 1
	result.filing_data.filing_status == "pending"
}

test_ctr_single_no_trigger_below_threshold if {
	not ctr.check_ctr_threshold with input as {
		"transaction": {
			"client_id": "C-001",
			"type": "cash",
			"amount": 9500.0,
		},
	}
}

test_ctr_single_no_trigger_non_cash if {
	not ctr.check_ctr_threshold with input as {
		"transaction": {
			"client_id": "C-001",
			"type": "wire_in",
			"amount": 15000.0,
		},
	}
}

test_ctr_single_no_trigger_at_exact_threshold if {
	not ctr.check_ctr_threshold with input as {
		"transaction": {
			"client_id": "C-001",
			"type": "cash",
			"amount": 10000.0,
		},
	}
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Aggregate same-day CTR threshold
# ═══════════════════════════════════════════════════════════════════

test_ctr_aggregate_triggers if {
	result := ctr.check_aggregate_ctr with input as {
		"client_id": "C-001",
		"transaction_date": "2024-01-15",
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 4000.0, "transaction_date": "2024-01-15"},
			{"client_id": "C-001", "type": "cash", "amount": 4000.0, "transaction_date": "2024-01-15"},
			{"client_id": "C-001", "type": "cash", "amount": 4000.0, "transaction_date": "2024-01-15"},
		],
	}
	result.action == "GENERATE_CTR"
	result.wsp_section == "8.2"
	result.filing_data.aggregate_amount == 12000.0
	result.filing_data.transaction_count == 3
	result.filing_data.filing_status == "pending"
}

test_ctr_aggregate_no_trigger_below_threshold if {
	not ctr.check_aggregate_ctr with input as {
		"client_id": "C-001",
		"transaction_date": "2024-01-15",
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 3000.0, "transaction_date": "2024-01-15"},
			{"client_id": "C-001", "type": "cash", "amount": 3000.0, "transaction_date": "2024-01-15"},
		],
	}
}

test_ctr_aggregate_ignores_other_clients if {
	not ctr.check_aggregate_ctr with input as {
		"client_id": "C-001",
		"transaction_date": "2024-01-15",
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 3000.0, "transaction_date": "2024-01-15"},
			{"client_id": "C-002", "type": "cash", "amount": 9000.0, "transaction_date": "2024-01-15"},
		],
	}
}

test_ctr_aggregate_ignores_other_dates if {
	not ctr.check_aggregate_ctr with input as {
		"client_id": "C-001",
		"transaction_date": "2024-01-15",
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 6000.0, "transaction_date": "2024-01-15"},
			{"client_id": "C-001", "type": "cash", "amount": 6000.0, "transaction_date": "2024-01-16"},
		],
	}
}
