# bsa-aml/sar_triggers_test.rego — OPA native tests for SAR trigger rules
#
# Tests all 4 SAR pattern detection rules:
#   1. Structuring: 3+ cash txns $8K-$10K in 5-day window >$25K
#   2. Rapid movement: wire in >$50K, wire out >80% in 3 days
#   3. Geographic risk: wire to high-risk jurisdiction >$5K
#   4. Unusual volume: current month >3x monthly average
#
# CRITICAL: Every result must include route_to=compliance_officer
# and do_not_notify=["advisor","client"] (anti-tipping-off).

package bsa_aml.sar_triggers_test

import rego.v1

import data.bsa_aml.sar_triggers

# ═══════════════════════════════════════════════════════════════════
# TEST: Structuring detection — triggers on 3+ suspect transactions
# ═══════════════════════════════════════════════════════════════════

test_structuring_triggers if {
	result := sar_triggers.check_structuring with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 9500.0, "timestamp_epoch": 1699950000},
			{"client_id": "C-001", "type": "cash", "amount": 9200.0, "timestamp_epoch": 1699960000},
			{"client_id": "C-001", "type": "cash", "amount": 8800.0, "timestamp_epoch": 1699970000},
		],
	}
	result.decision == "BLOCK"
	result.alert_type == "STRUCTURING"
	result.wsp_section == "8.1"
	result.route_to == "compliance_officer"
	result.do_not_notify == ["advisor", "client"]
	result.transaction_count == 3
	result.total_amount > 25000.0
}

test_structuring_no_trigger_below_count if {
	not sar_triggers.check_structuring with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 9500.0, "timestamp_epoch": 1699950000},
			{"client_id": "C-001", "type": "cash", "amount": 9200.0, "timestamp_epoch": 1699960000},
		],
	}
}

test_structuring_no_trigger_below_total if {
	not sar_triggers.check_structuring with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 8100.0, "timestamp_epoch": 1699950000},
			{"client_id": "C-001", "type": "cash", "amount": 8100.0, "timestamp_epoch": 1699960000},
			{"client_id": "C-001", "type": "cash", "amount": 8100.0, "timestamp_epoch": 1699970000},
		],
	}
}

test_structuring_no_trigger_outside_window if {
	not sar_triggers.check_structuring with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 9500.0, "timestamp_epoch": 1699000000},
			{"client_id": "C-001", "type": "cash", "amount": 9200.0, "timestamp_epoch": 1699010000},
			{"client_id": "C-001", "type": "cash", "amount": 9800.0, "timestamp_epoch": 1699020000},
		],
	}
}

test_structuring_ignores_other_clients if {
	not sar_triggers.check_structuring with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "cash", "amount": 9500.0, "timestamp_epoch": 1699950000},
			{"client_id": "C-002", "type": "cash", "amount": 9200.0, "timestamp_epoch": 1699960000},
			{"client_id": "C-002", "type": "cash", "amount": 9800.0, "timestamp_epoch": 1699970000},
		],
	}
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Rapid fund movement — triggers on wire in/out pattern
# ═══════════════════════════════════════════════════════════════════

test_rapid_movement_triggers if {
	result := sar_triggers.check_rapid_movement with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "wire_in", "amount": 75000.0, "timestamp_epoch": 1699900000},
			{"client_id": "C-001", "type": "wire_out", "amount": 65000.0, "timestamp_epoch": 1699950000},
		],
	}
	result.decision == "BLOCK"
	result.alert_type == "RAPID_MOVEMENT"
	result.wsp_section == "8.1"
	result.route_to == "compliance_officer"
	result.do_not_notify == ["advisor", "client"]
	result.wire_in == 75000.0
	result.wire_out == 65000.0
}

test_rapid_movement_no_trigger_low_inbound if {
	not sar_triggers.check_rapid_movement with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "wire_in", "amount": 40000.0, "timestamp_epoch": 1699900000},
			{"client_id": "C-001", "type": "wire_out", "amount": 35000.0, "timestamp_epoch": 1699950000},
		],
	}
}

test_rapid_movement_no_trigger_low_outbound_ratio if {
	not sar_triggers.check_rapid_movement with input as {
		"client_id": "C-001",
		"reference_epoch": 1700000000,
		"transactions": [
			{"client_id": "C-001", "type": "wire_in", "amount": 75000.0, "timestamp_epoch": 1699900000},
			{"client_id": "C-001", "type": "wire_out", "amount": 20000.0, "timestamp_epoch": 1699950000},
		],
	}
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Geographic risk — triggers on high-risk country wire
# ═══════════════════════════════════════════════════════════════════

test_geographic_risk_triggers if {
	result := sar_triggers.check_geographic_risk with input as {
		"transaction": {
			"client_id": "C-001",
			"destination_country": "IR",
			"amount": 15000.0,
		},
	}
	result.decision == "BLOCK"
	result.alert_type == "GEOGRAPHIC_RISK"
	result.wsp_section == "8.1"
	result.route_to == "compliance_officer"
	result.do_not_notify == ["advisor", "client"]
	result.destination_country == "IR"
}

test_geographic_risk_no_trigger_safe_country if {
	not sar_triggers.check_geographic_risk with input as {
		"transaction": {
			"client_id": "C-001",
			"destination_country": "GB",
			"amount": 15000.0,
		},
	}
}

test_geographic_risk_no_trigger_below_threshold if {
	not sar_triggers.check_geographic_risk with input as {
		"transaction": {
			"client_id": "C-001",
			"destination_country": "IR",
			"amount": 3000.0,
		},
	}
}

test_geographic_risk_no_trigger_null_country if {
	not sar_triggers.check_geographic_risk with input as {
		"transaction": {
			"client_id": "C-001",
			"destination_country": null,
			"amount": 15000.0,
		},
	}
}

# ═══════════════════════════════════════════════════════════════════
# TEST: Unusual volume — triggers on 3x monthly average
# ═══════════════════════════════════════════════════════════════════

test_unusual_volume_triggers if {
	result := sar_triggers.check_unusual_volume with input as {
		"client_id": "C-001",
		"avg_monthly_volume": 10000.0,
		"transactions": [
			{"client_id": "C-001", "type": "wire_out", "amount": 35000.0},
		],
	}
	result.decision == "WARN"
	result.alert_type == "UNUSUAL_PATTERN"
	result.wsp_section == "8.1"
	result.route_to == "compliance_officer"
	result.do_not_notify == ["advisor", "client"]
	result.current_total == 35000.0
}

test_unusual_volume_no_trigger_below_multiplier if {
	not sar_triggers.check_unusual_volume with input as {
		"client_id": "C-001",
		"avg_monthly_volume": 10000.0,
		"transactions": [
			{"client_id": "C-001", "type": "wire_out", "amount": 25000.0},
		],
	}
}

test_unusual_volume_no_trigger_zero_avg if {
	not sar_triggers.check_unusual_volume with input as {
		"client_id": "C-001",
		"avg_monthly_volume": 0,
		"transactions": [
			{"client_id": "C-001", "type": "wire_out", "amount": 50000.0},
		],
	}
}
